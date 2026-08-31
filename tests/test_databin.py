"""tools/databin.py（DATA.BIN 打包/解包）的测试。

三层：
1. nislzs 解码单元测试——含 C++ 版 256 字节环形缓冲（初值 0xff、off==0 即距离
   256、off>=flag 减 1）的逐字节参考实现，与快速解码器交叉验证；
2. 容器读写——金样字节串按 C++ do_pack 的 struct 布局手工构造（验收标准：
   与 C++ 版输出逐字节一致）；CLI 全流程 unpack→pack→unpack→pack 幂等；
3. 真实 assets/DATA.BIN 的门控集成测试（文件不在则 skip；全量往返另设
   ZND_DATABIN_FULL=1 环境变量门）。
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from tools.databin import (FILE_META, LZSS_HEADER, MANIFEST, PACK_HEADER,
                           lzss_unwrap, nislzs_decode, read_toc, safe_join,
                           write_container)

REPO = Path(__file__).resolve().parents[1]
DATABIN = REPO / "assets" / "DATA.BIN"
FLAG = 0xFC

needs_databin = pytest.mark.skipif(
    not DATABIN.exists(), reason="assets/DATA.BIN 不在（gitignore 资产，仅本机）")


# ---------------------------------------------------------------- 参考实现与夹具

def ring_decode(data: bytes) -> bytes:
    """C++ nislzs_decode_fsm 的逐字节直译（环形缓冲语义的权威参照）。"""
    flag = data[0]
    assert data[1:4] == b"\x00\x00\x00"
    buf = bytearray(b"\xff" * 256)
    w = 0
    out = bytearray()

    def put(b):
        nonlocal w
        out.append(b)
        buf[w] = b
        w = (w + 1) & 255

    i = 4
    while i < len(data):
        c = data[i]; i += 1
        if c != flag:
            put(c)
            continue
        c = data[i]; i += 1
        if c == flag:
            put(flag)
            continue
        off = c - 1 if c >= flag else c
        ln = data[i]; i += 1
        for _ in range(ln):
            put(buf[(w + 256 - off) & 255])
    return bytes(out)


def trivial_encode(data: bytes, flag: int = FLAG) -> bytes:
    """当年 C++ nislzs_encode_trivial 的等价物，测试造 lzss 夹具用。"""
    esc = bytes([flag])
    return bytes([flag, 0, 0, 0]) + data.replace(esc, esc * 2)


def lzss_wrap_trivial(data: bytes) -> bytes:
    stream = trivial_encode(data)
    return LZSS_HEADER.pack(b"lzss", 0, len(data), len(stream) - 4) + stream


def cli(*argv, cwd=REPO):
    res = subprocess.run([sys.executable, "tools/databin.py", *argv],
                         cwd=cwd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return res


# ---------------------------------------------------------------- nislzs 解码

def test_decode_literals_and_flag_escape():
    payload = b"hello \xfc world \xfc\xfc!"
    assert nislzs_decode(trivial_encode(payload)) == payload


def test_decode_copy_basic():
    # "abc" + 回拷(dist=3, len=5) -> "abcabcab"
    stream = bytes([FLAG, 0, 0, 0]) + b"abc" + bytes([FLAG, 3, 5])
    assert nislzs_decode(stream) == b"abcabcab"
    assert ring_decode(stream) == b"abcabcab"


def test_decode_offset_above_flag_shifts_by_one():
    # 偏移字节 0xfd > flag(0xfc) => 实际距离 0xfc=252
    lits = b"A" * 252
    stream = bytes([FLAG, 0, 0, 0]) + lits + bytes([FLAG, 0xFD, 4])
    expect = lits + b"A" * 4
    assert nislzs_decode(stream) == expect
    assert ring_decode(stream) == expect


def test_decode_offset_zero_means_256():
    lits = bytes(range(130)) + bytes(range(130))  # 260 字节，不含 0xfc
    assert FLAG not in lits
    stream = bytes([FLAG, 0, 0, 0]) + lits + bytes([FLAG, 0, 5])
    out = nislzs_decode(stream)
    assert out == ring_decode(stream)
    assert out[260:] == out[260 - 256:260 - 256 + 5]


def test_decode_prehistory_reads_ff():
    # 输出为空时就回拷，命中环形缓冲初值 0xff
    stream = bytes([FLAG, 0, 0, 0, FLAG, 10, 3])
    assert nislzs_decode(stream) == b"\xff\xff\xff"
    assert ring_decode(stream) == b"\xff\xff\xff"


def test_decode_overlap_run():
    stream = bytes([FLAG, 0, 0, 0]) + b"x" + bytes([FLAG, 1, 255])
    out = nislzs_decode(stream)
    assert out == b"x" * 256
    assert ring_decode(stream) == out


def test_decode_malformed():
    with pytest.raises(ValueError):
        nislzs_decode(bytes([FLAG, 0, 0, 1]) + b"a")  # 流头非零
    with pytest.raises(ValueError):
        nislzs_decode(bytes([FLAG, 0, 0, 0, FLAG]))  # 悬空 flag
    with pytest.raises(ValueError):
        nislzs_decode(bytes([FLAG, 0, 0, 0, FLAG, 3]))  # 截断的回拷
    with pytest.raises(ValueError):
        nislzs_decode(trivial_encode(b"abc"), expected_size=4)  # 长度不符


def test_decode_fast_vs_ring_random_streams():
    rng = random.Random(20260831)
    for _ in range(40):
        stream = bytearray([FLAG, 0, 0, 0])
        for _ in range(rng.randrange(1, 120)):
            k = rng.random()
            if k < 0.55:  # 字面量段
                stream += bytes(rng.choices(
                    [b for b in range(256) if b != FLAG], k=rng.randrange(1, 20)))
            elif k < 0.7:  # 转义的 flag 字面量
                stream += bytes([FLAG, FLAG])
            else:  # 随机回拷（距离/长度全域，含越界读 0xff 与 off==0）
                off = rng.randrange(256)
                if off == FLAG:
                    continue
                stream += bytes([FLAG, off, rng.randrange(256)])
        stream = bytes(stream)
        assert nislzs_decode(stream) == ring_decode(stream)


# ---------------------------------------------------------------- 容器读写

def test_write_container_golden_bytes():
    """金样：与 C++ do_pack 的 struct 布局逐字节对齐。"""
    entries = [("a/b.bin", b"XY"), ("c.dat", b"12345")]
    import io
    out = io.BytesIO()
    write_container(entries, out)

    expect = struct.pack("<4sIIII", b"pack", 0, 20 + 2 + 5, 2 * 60, 2)
    expect += b"XY" + b"12345"
    expect += b"a/b.bin" + b"\0" * 45 + struct.pack("<II", 20, 2)
    expect += b"c.dat" + b"\0" * 47 + struct.pack("<II", 22, 5)
    assert out.getvalue() == expect


def test_read_toc_roundtrip():
    entries = [("x/1.bin", b"\x00\x01"), ("y/2.bin", b""), ("z.bin", b"Q" * 7)]
    import io
    out = io.BytesIO()
    write_container(entries, out)
    out.seek(0)
    assert read_toc(out) == [("x/1.bin", 20, 2), ("y/2.bin", 22, 0),
                             ("z.bin", 22, 7)]


def test_write_container_rejects_long_name():
    import io
    with pytest.raises(ValueError):
        write_container([("n" * 52, b"")], io.BytesIO())


def test_safe_join_rejects_traversal():
    for bad in ("../x", "/etc/passwd", "a//b", "a/../b"):
        with pytest.raises(ValueError):
            safe_join("root", bad)


# ---------------------------------------------------------------- CLI 全流程

def make_fixture_databin(path: Path):
    """两个 lzss 图 + 两个 raw 成员；gim 内容带 0xfc 与重复段落。"""
    rng = random.Random(7)
    gim1 = b"MIG.00.1PSP\0" + bytes(rng.randrange(256) for _ in range(3000)) * 2
    gim2 = b"MIG.00.1PSP\0" + b"\xfc" * 300 + bytes(range(256)) * 4
    lua = b"\x1bLuaQ\x00\x01\x04\x04\x04\x08\x00" + b"body"
    at3 = b"RIFF" + bytes(rng.randrange(256) for _ in range(500))
    entries = [("bg/one.gim", lzss_wrap_trivial(gim1)),
               ("script/a.lua", lua),
               ("card/two.gim", lzss_wrap_trivial(gim2)),
               ("voice/v.at3", at3)]
    with open(path, "wb") as f:
        write_container(entries, f)
    return {"bg/one.gim": gim1, "script/a.lua": lua,
            "card/two.gim": gim2, "voice/v.at3": at3}


def test_cli_unpack_pack_idempotent(tmp_path):
    orig = tmp_path / "DATA.BIN"
    contents = make_fixture_databin(orig)

    d1 = tmp_path / "d1"
    cli("unpack", str(orig), str(d1))
    manifest1 = [json.loads(l) for l in
                 (d1 / MANIFEST).read_text().splitlines()]
    assert [m["name"] for m in manifest1] == list(contents)  # 保持原封包顺序
    assert [m["lzss"] for m in manifest1] == [True, False, True, False]
    for m in manifest1:
        data = (d1 / m["name"]).read_bytes()
        assert data == contents[m["name"]]  # lzss 已解压、raw 原样
        assert hashlib.sha1(data).hexdigest() == m["sha1"]

    p1 = tmp_path / "p1.bin"
    cli("pack", str(d1), str(p1))
    with open(p1, "rb") as f:
        toc = read_toc(f)
        assert [n for n, _, _ in toc] == list(contents)  # 顺序不变
        for name, off, length in toc:  # 回封一律 raw 存储
            f.seek(off)
            member = f.read(length)
            assert member[:4] != b"lzss"
            assert member == contents[name]

    d2 = tmp_path / "d2"
    cli("unpack", str(p1), str(d2))
    for name, data in contents.items():
        assert (d2 / name).read_bytes() == data

    p2 = tmp_path / "p2.bin"
    cli("pack", str(d2), str(p2))
    assert p1.read_bytes() == p2.read_bytes()  # 幂等不动点


def test_cli_pack_order_follows_manifest(tmp_path):
    """成员写入顺序由 manifest 行序决定，与文件系统枚举顺序无关。"""
    src = tmp_path / "src"
    (src / "b").mkdir(parents=True)
    (src / "a").mkdir()
    (src / "b" / "1.bin").write_bytes(b"BBB")
    (src / "a" / "2.bin").write_bytes(b"AA")
    (src / MANIFEST).write_text(
        json.dumps({"name": "b/1.bin", "lzss": False}) + "\n" +
        json.dumps({"name": "a/2.bin", "lzss": False}) + "\n")
    dst = tmp_path / "out.bin"
    cli("pack", str(src), str(dst))
    with open(dst, "rb") as f:
        assert [n for n, _, _ in read_toc(f)] == ["b/1.bin", "a/2.bin"]


def test_cli_verify_fixture(tmp_path):
    orig = tmp_path / "DATA.BIN"
    make_fixture_databin(orig)
    res = cli("verify", str(orig), "--full")
    assert "OK" in res.stdout and "FAIL" not in res.stdout


# ---------------------------------------------------------------- 真实 DATA.BIN

@needs_databin
def test_real_toc_shape():
    with open(DATABIN, "rb") as f:
        entries = read_toc(f)
    assert len(entries) == 9231
    assert entries[0] == ("bg/bg_10_a_0.gim", 20, 86971)
    names = [n for n, _, _ in entries]
    assert len(set(names)) == len(names)
    pos = 20
    for _, off, length in entries:
        assert off == pos
        pos += length


@needs_databin
def test_real_container_rebuild_identity():
    """由解析结果重建的容器与原文件逐字节一致（写入端保真的金标准）。"""
    h_orig, h_rebuild = hashlib.sha256(), hashlib.sha256()
    with open(DATABIN, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h_orig.update(chunk)
        entries = read_toc(f)
        pos = 20
        metas = []
        for name, off, length in entries:
            metas.append(FILE_META.pack(name.encode(), off, length))
            pos += length
        h_rebuild.update(PACK_HEADER.pack(b"pack", 0, pos, len(metas) * 60,
                                          len(metas)))
        for _, off, length in entries:
            f.seek(off)
            h_rebuild.update(f.read(length))
        for m in metas:
            h_rebuild.update(m)
    assert h_orig.digest() == h_rebuild.digest()


@needs_databin
def test_real_first_gim_decode_and_ring_crosscheck():
    with open(DATABIN, "rb") as f:
        name, off, length = read_toc(f)[0]
        f.seek(off)
        member = f.read(length)
    _, _, dsize, zsize = LZSS_HEADER.unpack_from(member)
    content = lzss_unwrap(member)
    assert len(content) == dsize == 131792
    assert content.startswith(b"MIG.00.1PSP")
    assert ring_decode(member[16:]) == content  # 环形参考实现交叉验证


@needs_databin
@pytest.mark.skipif(not os.environ.get("ZND_DATABIN_FULL"),
                    reason="全量往返（~1.2GB 磁盘写）需 ZND_DATABIN_FULL=1")
def test_real_full_roundtrip_idempotent(tmp_path):
    d1 = tmp_path / "d1"
    cli("unpack", str(DATABIN), str(d1))
    p1 = tmp_path / "p1.bin"
    cli("pack", str(d1), str(p1))
    d2 = tmp_path / "d2"
    cli("unpack", str(p1), str(d2))
    p2 = tmp_path / "p2.bin"
    cli("pack", str(d2), str(p2))
    h1 = hashlib.sha256(p1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(p2.read_bytes()).hexdigest()
    assert h1 == h2
    m1 = (d1 / MANIFEST).read_text().splitlines()
    m2 = (d2 / MANIFEST).read_text().splitlines()
    assert [json.loads(a)["name"] for a in m1] == \
           [json.loads(b)["name"] for b in m2]
    assert all(json.loads(a)["sha1"] == json.loads(b)["sha1"]
               for a, b in zip(m1, m2))
