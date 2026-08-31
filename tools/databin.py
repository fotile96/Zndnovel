#!/usr/bin/env python3
"""DATA.BIN（PSP『セカンドノベル』资源包）打包/解包工具。

2018 年 C++ 工具 second-novel-toolkit 的 Python 重写（luac/protobuf 老翻译
路线已废弃，不迁移）。格式实测依据 assets/DATA.BIN（9231 成员）全量验证。

容器格式（全部小端）::

    +0x00  头部 20 字节: "pack" | u32 0 | u32 表偏移 | u32 表总长 | u32 成员数
    +0x14  成员数据体，按表序零间隙紧排
    表偏移: 每成员 60 字节 = char[52] 路径名(NUL 填充) + u32 偏移 + u32 长度

成员可为 lzss 压缩体（原包实测仅 .gim 如此，.at3/.vag/.lua/.pgf/... 原样存储）::

    "lzss" | u32 0 | u32 解压后大小 dsize | u32 压缩流大小 zsize
    flag 字节 + 00 00 00 | 压缩流（恰 zsize 字节，解码恰得 dsize 字节）

nislzs 压缩流：非 flag 字节为字面量；``flag flag`` 输出一个 flag 字面量；
``flag off len`` 从 256 字节环形缓冲（初值 0xff）回拷——off >= flag 时先减 1
（flag 值本身不可作距离编码），off == 0 表示距离 256。

**回封不压缩**（与当年 C++ do_pack 一致，引擎按成员开头 magic 自识别，
经实机验证可行；本工具不实现压缩编码）。验收标准：与 C++ 版输出逐字节
一致、幂等（unpack→pack→unpack→pack 收敛不动点）、**严格保持原封包的
成员顺序**（做卡在 manifest.jsonl 的行序里）。

用法::

    python3 tools/databin.py list   assets/DATA.BIN [--verbose]
    python3 tools/databin.py unpack assets/DATA.BIN build/databin
    python3 tools/databin.py pack   build/databin build/DATA.new.BIN
    python3 tools/databin.py verify assets/DATA.BIN [--full]

unpack 展开全部成员（lzss 自动解压）并写 manifest.jsonl（原始顺序/压缩
标记/解压内容 sha1）。pack 按 manifest 行序以 raw 存储重建容器。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys

PACK_HEADER = struct.Struct("<4sIIII")
FILE_META = struct.Struct("<52sII")
LZSS_HEADER = struct.Struct("<4sIII")
MANIFEST = "manifest.jsonl"


# ---------------------------------------------------------------- nislzs 解码

def nislzs_decode(data: bytes, expected_size: int | None = None) -> bytes:
    """解码一段完整压缩流（含开头的 flag + 00 00 00 共 4 字节）。"""
    if len(data) < 4 or data[1:4] != b"\x00\x00\x00":
        raise ValueError("nislzs 流头损坏（应为 flag 字节 + 3 个零）")
    flag = data[0]
    out = bytearray()
    i, n = 4, len(data)
    while i < n:
        j = data.find(flag, i)
        if j < 0:
            out += data[i:]
            break
        out += data[i:j]
        if j + 1 >= n:
            raise ValueError("流尾悬空的 flag 字节")
        c = data[j + 1]
        if c == flag:
            out.append(flag)
            i = j + 2
        else:
            if j + 2 >= n:
                raise ValueError("流尾截断的回拷指令")
            dist = c - 1 if c > flag else c
            if dist == 0:
                dist = 256  # 环形缓冲一整圈
            length = data[j + 2]
            i = j + 3
            avail = len(out)
            if dist <= avail:
                start = avail - dist
                if length <= dist:
                    out += out[start:start + length]
                else:  # 重叠回拷：以 dist 为周期铺开
                    seg = bytes(out[start:])
                    out += (seg * (length // dist + 1))[:length]
            else:  # 引用尚未写过的环形缓冲区域（初值 0xff）
                for _ in range(length):
                    d = len(out)
                    out.append(out[d - dist] if dist <= d else 0xFF)
    if expected_size is not None and len(out) != expected_size:
        raise ValueError(f"解压得 {len(out)} 字节，与声明的 {expected_size} 不符")
    return bytes(out)


def lzss_unwrap(member: bytes) -> bytes:
    """解开带 lzss 头的成员体；非 lzss 成员原样返回。"""
    if member[:4] != b"lzss":
        return member
    _, zero, dsize, zsize = LZSS_HEADER.unpack_from(member)
    if len(member) != 16 + 4 + zsize:
        raise ValueError(f"成员长度 {len(member)} != 16+4+zsize({zsize})")
    return nislzs_decode(member[16:], expected_size=dsize)


# ---------------------------------------------------------------- 容器读写

def read_toc(f) -> list[tuple[str, int, int]]:
    """读容器文件表，返回 [(名字, 偏移, 长度)]（保持原序）。"""
    f.seek(0)
    magic, zero, meta_off, meta_len, num = PACK_HEADER.unpack(f.read(20))
    if magic != b"pack" or zero != 0:
        raise ValueError("不是 pack 容器（magic 不符）")
    if meta_len != num * FILE_META.size:
        raise ValueError("文件表长度与成员数不一致")
    f.seek(meta_off)
    table = f.read(meta_len)
    entries = []
    for i in range(num):
        raw, off, length = FILE_META.unpack_from(table, i * FILE_META.size)
        entries.append((raw.split(b"\0", 1)[0].decode("ascii"), off, length))
    return entries


def write_container(entries, out) -> None:
    """把 [(名字, 成员体字节)] 按序写成完整容器（与 C++ do_pack 逐字节一致）。"""
    pos = PACK_HEADER.size
    metas = []
    for name, blob in entries:
        raw = name.encode("ascii")
        if len(raw) > 51:
            raise ValueError(f"成员名超过 51 字节: {name}")
        metas.append(FILE_META.pack(raw, pos, len(blob)))
        pos += len(blob)
    out.write(PACK_HEADER.pack(b"pack", 0, pos,
                               len(metas) * FILE_META.size, len(metas)))
    for _, blob in entries:
        out.write(blob)
    for m in metas:
        out.write(m)


def safe_join(root: str, name: str) -> str:
    parts = name.split("/")
    if name.startswith("/") or ".." in parts or "" in parts:
        raise ValueError(f"可疑成员路径: {name}")
    return os.path.join(root, *parts)


# ---------------------------------------------------------------- 子命令

def cmd_list(args):
    with open(args.databin, "rb") as f:
        entries = read_toc(f)
        for name, off, length in entries:
            if args.verbose:
                f.seek(off)
                tag = "lzss" if f.read(4) == b"lzss" else "raw "
                print(f"{tag} {off:>10} {length:>9}  {name}")
            else:
                print(name)
    print(f"# {len(entries)} 个成员", file=sys.stderr)


def cmd_unpack(args):
    os.makedirs(args.outdir, exist_ok=True)
    n_lzss = 0
    with open(args.databin, "rb") as f, \
         open(os.path.join(args.outdir, MANIFEST), "w", encoding="utf-8") as mf:
        entries = read_toc(f)
        for name, off, length in entries:
            f.seek(off)
            member = f.read(length)
            is_lzss = member[:4] == b"lzss"
            content = lzss_unwrap(member)
            n_lzss += is_lzss
            path = safe_join(args.outdir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as g:
                g.write(content)
            mf.write(json.dumps(
                {"name": name, "lzss": is_lzss,
                 "sha1": hashlib.sha1(content).hexdigest()},
                ensure_ascii=False) + "\n")
    print(f"展开 {len(entries)} 个成员（其中 lzss 解压 {n_lzss} 个）→ {args.outdir}")


def cmd_pack(args):
    """按 manifest 行序把 srcdir 下的成员文件以 raw 存储重建容器。"""
    manifest_path = os.path.join(args.srcdir, MANIFEST)
    with open(manifest_path, encoding="utf-8") as mf:
        order = [json.loads(line)["name"] for line in mf if line.strip()]

    with open(args.dst, "wb") as out:
        entries = []
        for name in order:
            with open(safe_join(args.srcdir, name), "rb") as g:
                entries.append((name, g.read()))
        write_container(entries, out)
    print(f"打包 {len(order)} 个成员 → {args.dst}"
          f"（{os.path.getsize(args.dst)} 字节，raw 存储）")


def cmd_verify(args):
    """自检：容器可由解析结果逐字节重建；lzss 成员解码长度与声明一致。"""
    with open(args.databin, "rb") as f:
        entries = read_toc(f)

        h_orig, h_rebuild = hashlib.sha256(), hashlib.sha256()
        f.seek(0)
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h_orig.update(chunk)

        pos = PACK_HEADER.size
        metas = []
        for name, off, length in entries:
            if off != pos:
                raise SystemExit(f"成员间存在间隙: {name} 偏移 {off} != {pos}")
            metas.append(FILE_META.pack(name.encode("ascii"), off, length))
            pos += length
        h_rebuild.update(PACK_HEADER.pack(
            b"pack", 0, pos, len(metas) * FILE_META.size, len(metas)))
        for name, off, length in entries:
            f.seek(off)
            remain = length
            while remain:
                chunk = f.read(min(remain, 1 << 20))
                h_rebuild.update(chunk)
                remain -= len(chunk)
        for m in metas:
            h_rebuild.update(m)
        ok_container = h_orig.digest() == h_rebuild.digest()
        print(f"容器重建逐字节一致: {'OK' if ok_container else 'FAIL'}")

        n_lzss = n_checked = 0
        for name, off, length in entries:
            f.seek(off)
            member = f.read(length)
            if member[:4] != b"lzss":
                continue
            n_lzss += 1
            if args.full or n_checked < 32:
                lzss_unwrap(member)  # 长度不符会抛异常
                n_checked += 1
        print(f"lzss 成员 {n_lzss} 个，解码校验 {n_checked} 个: OK")
        if not ok_container:
            raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="列出成员")
    p.add_argument("databin")
    p.add_argument("--verbose", "-v", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("unpack", help="展开全部成员并写 manifest.jsonl")
    p.add_argument("databin")
    p.add_argument("outdir")
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser("pack", help="按 manifest.jsonl 行序以 raw 存储重建容器")
    p.add_argument("srcdir")
    p.add_argument("dst")
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("verify", help="容器与压缩格式自检")
    p.add_argument("databin")
    p.add_argument("--full", action="store_true",
                   help="解码校验全部 lzss 成员（默认抽查 32 个）")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
