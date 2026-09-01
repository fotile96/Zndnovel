"""tools/umdiso.py（UMD ISO 就地替换）的测试。

合成一张最小但结构完整的 ISO9660（系统区 + PVD + 终止符 + 4 份 path table +
根目录 + 子目录 + 3 个文件）跑全流程：恒等替换必须逐字节还原、变大/变小时
尾部平移且每个未动文件内容不变、多文件一次替换、verify 能抓出人为破坏。

真盘（assets/orig.iso，gitignore 资产）另有门控测试；548MB 全量往返以
ZND_ISO_FULL=1 再开一层门。
"""
from __future__ import annotations

import hashlib
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from tools.umdiso import SECTOR, Iso, replace, verify

REPO = Path(__file__).resolve().parents[1]
ORIG_ISO = REPO / "assets" / "orig.iso"

needs_iso = pytest.mark.skipif(
    not ORIG_ISO.exists(), reason="assets/orig.iso 不在（gitignore 资产）")


# ---------------------------------------------------------------- 合成 ISO

def _dir_record(name: bytes, lba: int, size: int, is_dir: bool) -> bytes:
    rec = bytearray(33 + len(name))
    rec[1] = 0
    struct.pack_into("<I", rec, 2, lba)
    struct.pack_into(">I", rec, 6, lba)
    struct.pack_into("<I", rec, 10, size)
    struct.pack_into(">I", rec, 14, size)
    rec[18:25] = bytes([126, 1, 1, 0, 0, 0, 0])  # 2026-01-01
    rec[25] = 2 if is_dir else 0
    struct.pack_into("<H", rec, 28, 1)
    struct.pack_into(">H", rec, 30, 1)
    rec[32] = len(name)
    rec[33:] = name
    if len(rec) % 2:
        rec += b"\0"
    rec[0] = len(rec)
    return bytes(rec)


def _path_table(entries, be: bool) -> bytes:
    """entries = [(名字bytes, LBA, 父序号)]，父序号从 1 起。"""
    out = bytearray()
    for name, lba, parent in entries:
        rec = bytearray(8 + len(name))
        rec[0] = len(name)
        rec[1] = 0
        struct.pack_into(">I" if be else "<I", rec, 2, lba)
        struct.pack_into(">H" if be else "<H", rec, 6, parent)
        rec[8:] = name
        if len(rec) % 2:
            rec += b"\0"
        out += rec
    return bytes(out)


def make_iso(path: Path, sizes=(3000, 100, 500)) -> dict[str, bytes]:
    """造一张 28 扇区的合法 ISO，返回 {盘内路径: 内容}。"""
    a_sz, b_sz, c_sz = sizes
    a_sec = (a_sz + SECTOR - 1) // SECTOR
    b_sec = (b_sz + SECTOR - 1) // SECTOR
    c_sec = (c_sz + SECTOR - 1) // SECTOR
    root_lba, sub_lba = 22, 23
    a_lba = 24
    b_lba = a_lba + a_sec
    c_lba = b_lba + b_sec
    total = c_lba + c_sec

    contents = {
        "/FILE_A.BIN": bytes((i * 7 + 1) % 256 for i in range(a_sz)),
        "/SUB/FILE_B.BIN": bytes((i * 13 + 2) % 256 for i in range(b_sz)),
        "/FILE_C.BIN": bytes((i * 29 + 3) % 256 for i in range(c_sz)),
    }

    root = bytearray()
    root += _dir_record(b"\x00", root_lba, SECTOR, True)
    root += _dir_record(b"\x01", root_lba, SECTOR, True)
    root += _dir_record(b"SUB", sub_lba, SECTOR, True)
    root += _dir_record(b"FILE_A.BIN;1", a_lba, a_sz, False)
    root += _dir_record(b"FILE_C.BIN;1", c_lba, c_sz, False)
    root += b"\0" * (SECTOR - len(root))

    sub = bytearray()
    sub += _dir_record(b"\x00", sub_lba, SECTOR, True)
    sub += _dir_record(b"\x01", root_lba, SECTOR, True)
    sub += _dir_record(b"FILE_B.BIN;1", b_lba, b_sz, False)
    sub += b"\0" * (SECTOR - len(sub))

    pt_entries = [(b"\x00", root_lba, 1), (b"SUB", sub_lba, 1)]
    pt_l = _path_table(pt_entries, False)
    pt_m = _path_table(pt_entries, True)

    pvd = bytearray(b"\0" * SECTOR)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"PSP GAME".ljust(32)
    pvd[40:72] = b"TEST".ljust(32)
    struct.pack_into("<I", pvd, 80, total)
    struct.pack_into(">I", pvd, 84, total)
    struct.pack_into("<H", pvd, 128, SECTOR)
    struct.pack_into(">H", pvd, 130, SECTOR)
    struct.pack_into("<I", pvd, 132, len(pt_l))
    struct.pack_into(">I", pvd, 136, len(pt_l))
    struct.pack_into("<I", pvd, 140, 18)
    struct.pack_into("<I", pvd, 144, 19)
    struct.pack_into(">I", pvd, 148, 20)
    struct.pack_into(">I", pvd, 152, 21)
    pvd[156:156 + 34] = _dir_record(b"\x00", root_lba, SECTOR, True)
    pvd[574:702] = b"PSP GAME".ljust(128)

    term = bytearray(b"\0" * SECTOR)
    term[0] = 255
    term[1:6] = b"CD001"
    term[6] = 1

    img = bytearray(b"\0" * (16 * SECTOR))          # 系统区
    img += pvd + term
    for raw in (pt_l, pt_l, pt_m, pt_m):            # LBA 18..21
        img += raw.ljust(SECTOR, b"\0")
    img += root + sub
    for key, sec in (("/FILE_A.BIN", a_sec), ("/SUB/FILE_B.BIN", b_sec),
                     ("/FILE_C.BIN", c_sec)):
        img += contents[key].ljust(sec * SECTOR, b"\0")
    assert len(img) == total * SECTOR
    path.write_bytes(bytes(img))
    return contents


def read_file(iso_path: Path, inner: str) -> bytes:
    with Iso(str(iso_path)) as iso:
        rec = iso.find(inner)
        iso.f.seek(rec.lba * SECTOR)
        return iso.f.read(rec.size)


def all_files(iso_path: Path) -> dict[str, bytes]:
    with Iso(str(iso_path)) as iso:
        out = {}
        for rec in iso.files():
            iso.f.seek(rec.lba * SECTOR)
            out[rec.path] = iso.f.read(rec.size)
        return out


# ---------------------------------------------------------------- 解析

def test_parse_synthetic(tmp_path):
    iso_path = tmp_path / "t.iso"
    contents = make_iso(iso_path)
    with Iso(str(iso_path)) as iso:
        assert iso.volume_sectors == iso.size // SECTOR
        assert len(iso.path_tables()) == 4
        got = {r.path: (r.lba, r.size) for r in iso.files()}
        assert set(got) == set(contents)
        assert got["/FILE_A.BIN"] == (24, 3000)
        assert got["/SUB/FILE_B.BIN"] == (26, 100)
        assert got["/FILE_C.BIN"] == (27, 500)
    assert all_files(iso_path) == contents


def test_verify_synthetic(tmp_path):
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    assert verify(str(iso_path), log=lambda *a: None)


def test_find_missing_raises(tmp_path):
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    with Iso(str(iso_path)) as iso:
        with pytest.raises(KeyError):
            iso.find("/NOPE.BIN")


def test_parse_rejects_non_iso(tmp_path):
    bad = tmp_path / "bad.iso"
    bad.write_bytes(b"\0" * (20 * SECTOR))
    with pytest.raises(ValueError, match="主卷描述符"):
        Iso(str(bad))


# ---------------------------------------------------------------- 替换

def test_replace_identity_is_byte_exact(tmp_path):
    src = tmp_path / "t.iso"
    contents = make_iso(src)
    same = tmp_path / "a.bin"
    same.write_bytes(contents["/FILE_A.BIN"])
    dst = tmp_path / "out.iso"
    replace(str(src), str(dst), [("/FILE_A.BIN", str(same))],
            log=lambda *a: None)
    assert dst.read_bytes() == src.read_bytes()


@pytest.mark.parametrize("newsize,label", [
    (9000, "变大跨扇区"), (3000, "同尺寸"), (2500, "同扇区数变小"),
    (100, "缩到 1 扇区"), (0, "空文件"),
])
def test_replace_resizes_and_shifts(tmp_path, newsize, label):
    src = tmp_path / "t.iso"
    contents = make_iso(src)
    new = tmp_path / "new.bin"
    payload = bytes((i * 3 + 5) % 256 for i in range(newsize))
    new.write_bytes(payload)
    dst = tmp_path / "out.iso"
    replace(str(src), str(dst), [("/FILE_A.BIN", str(new))],
            log=lambda *a: None)

    assert verify(str(dst), log=lambda *a: None), label
    got = all_files(dst)
    assert got["/FILE_A.BIN"] == payload, label
    assert got["/SUB/FILE_B.BIN"] == contents["/SUB/FILE_B.BIN"], label
    assert got["/FILE_C.BIN"] == contents["/FILE_C.BIN"], label

    old_sec = (3000 + SECTOR - 1) // SECTOR
    new_sec = (newsize + SECTOR - 1) // SECTOR
    diff = new_sec - old_sec
    with Iso(str(src)) as a, Iso(str(dst)) as b:
        amap = {r.path: r.lba for r in a.files()}
        bmap = {r.path: r.lba for r in b.files()}
        assert bmap["/FILE_A.BIN"] == amap["/FILE_A.BIN"]
        assert bmap["/SUB/FILE_B.BIN"] == amap["/SUB/FILE_B.BIN"] + diff
        assert bmap["/FILE_C.BIN"] == amap["/FILE_C.BIN"] + diff
        assert b.volume_sectors == a.volume_sectors + diff


def test_replace_multiple_files_at_once(tmp_path):
    src = tmp_path / "t.iso"
    contents = make_iso(src)
    big_a = tmp_path / "a.bin"
    big_a.write_bytes(b"A" * 7000)
    big_b = tmp_path / "b.bin"
    big_b.write_bytes(b"B" * 5000)
    dst = tmp_path / "out.iso"
    replace(str(src), str(dst),
            [("/FILE_A.BIN", str(big_a)), ("/SUB/FILE_B.BIN", str(big_b))],
            log=lambda *a: None)

    assert verify(str(dst), log=lambda *a: None)
    got = all_files(dst)
    assert got["/FILE_A.BIN"] == b"A" * 7000
    assert got["/SUB/FILE_B.BIN"] == b"B" * 5000
    assert got["/FILE_C.BIN"] == contents["/FILE_C.BIN"]  # 未动者内容不变


def test_replace_then_replace_back_restores_original(tmp_path):
    """来回替换回到原内容：结构与数据都应复原（尺寸字段随之回落）。"""
    src = tmp_path / "t.iso"
    contents = make_iso(src)
    big = tmp_path / "big.bin"
    big.write_bytes(b"X" * 9000)
    mid = tmp_path / "mid.iso"
    replace(str(src), str(mid), [("/FILE_A.BIN", str(big))],
            log=lambda *a: None)
    orig_a = tmp_path / "orig_a.bin"
    orig_a.write_bytes(contents["/FILE_A.BIN"])
    back = tmp_path / "back.iso"
    replace(str(mid), str(back), [("/FILE_A.BIN", str(orig_a))],
            log=lambda *a: None)
    assert back.read_bytes() == src.read_bytes()


def test_replace_in_subdir(tmp_path):
    src = tmp_path / "t.iso"
    contents = make_iso(src)
    new = tmp_path / "b.bin"
    new.write_bytes(b"Z" * 6000)
    dst = tmp_path / "out.iso"
    replace(str(src), str(dst), [("/SUB/FILE_B.BIN", str(new))],
            log=lambda *a: None)
    assert verify(str(dst), log=lambda *a: None)
    got = all_files(dst)
    assert got["/SUB/FILE_B.BIN"] == b"Z" * 6000
    assert got["/FILE_A.BIN"] == contents["/FILE_A.BIN"]
    assert got["/FILE_C.BIN"] == contents["/FILE_C.BIN"]


# ---------------------------------------------------------------- verify 抓错

def test_verify_catches_wrong_volume_size(tmp_path):
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    raw = bytearray(iso_path.read_bytes())
    struct.pack_into("<I", raw, 16 * SECTOR + 80, 99999)
    iso_path.write_bytes(bytes(raw))
    assert not verify(str(iso_path), log=lambda *a: None)


def test_verify_catches_path_table_desync(tmp_path):
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    raw = bytearray(iso_path.read_bytes())
    # 把 L path table 里 SUB 的 LBA 改成目录树里不存在的值
    struct.pack_into("<I", raw, 18 * SECTOR + 10 + 2, 999)
    iso_path.write_bytes(bytes(raw))
    assert not verify(str(iso_path), log=lambda *a: None)


# ---------------------------------------------------------------- CLI

def test_cli_list_extract_replace(tmp_path):
    src = tmp_path / "t.iso"
    contents = make_iso(src)

    def cli(*argv):
        r = subprocess.run([sys.executable, "tools/umdiso.py", *argv],
                           cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout

    out = cli("list", str(src), "--gaps")
    assert "/FILE_A.BIN" in out and "/SUB/FILE_B.BIN" in out

    got = tmp_path / "got.bin"
    cli("extract", str(src), "/FILE_A.BIN", str(got))
    assert got.read_bytes() == contents["/FILE_A.BIN"]

    new = tmp_path / "new.bin"
    new.write_bytes(b"Q" * 4096)
    dst = tmp_path / "out.iso"
    cli("replace", str(src), str(dst), "/FILE_A.BIN", str(new))
    assert all_files(dst)["/FILE_A.BIN"] == b"Q" * 4096
    assert "✓" in cli("verify", str(dst), "--against", str(src))


# ---------------------------------------------------------------- 真盘

@needs_iso
def test_real_iso_shape():
    with Iso(str(ORIG_ISO)) as iso:
        assert iso.pvd[8:40].rstrip() == b"PSP GAME"
        assert iso.volume_sectors == iso.size // SECTOR == 267760
        assert len(iso.path_tables()) == 4
        paths = {r.path: r for r in iso.files()}
        data = paths["/PSP_GAME/USRDIR/DATA.BIN"]
        assert (data.lba, data.size) == (80784, 302639689)
        assert "/PSP_GAME/SYSDIR/EBOOT.BIN" in paths
        assert "/UMD_DATA.BIN" in paths


@needs_iso
def test_real_iso_verifies():
    assert verify(str(ORIG_ISO), log=lambda *a: None)


@needs_iso
@pytest.mark.skipif(not os.environ.get("ZND_ISO_FULL"),
                    reason="548MB 真盘往返需 ZND_ISO_FULL=1")
def test_real_iso_identity_replace(tmp_path):
    """用盘内原样内容替换 DATA.BIN，输出必须与原盘逐字节相同。"""
    extracted = tmp_path / "DATA.BIN"
    with Iso(str(ORIG_ISO)) as iso:
        rec = iso.find("/PSP_GAME/USRDIR/DATA.BIN")
        iso.f.seek(rec.lba * SECTOR)
        with open(extracted, "wb") as g:
            remain = rec.size
            while remain:
                chunk = iso.f.read(min(1 << 22, remain))
                g.write(chunk)
                remain -= len(chunk)
    dst = tmp_path / "identity.iso"
    replace(str(ORIG_ISO), str(dst),
            [("/PSP_GAME/USRDIR/DATA.BIN", str(extracted))],
            log=lambda *a: None)
    h1 = hashlib.sha256(ORIG_ISO.read_bytes()).hexdigest()
    h2 = hashlib.sha256(dst.read_bytes()).hexdigest()
    assert h1 == h2
