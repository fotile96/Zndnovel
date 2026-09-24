#!/usr/bin/env python3
"""PSP UMD ISO 就地替换——把改后的文件塞回原盘，其余字节一律不动。

**为什么不用通用刻录工具重建**（UltraISO/hdiutil 等，机理见
`docs/ops/umd-iso-repack-research-2026-08-31.md`）：PPSSPP 挂载时递归走目录记录、
**不读 path table**，所以结构半坏的 ISO 在模拟器里照跑；实机上真正解析文件系统的
是 Sony 固件的 isofs，它按规范读 PVD + path table，且**只认主卷里的名字**。通用
工具会把真实文件名塞进 Joliet 补充卷、把主卷改成 8.3 大写名，或重排 LBA 而不同步
path table——于是"模拟器好好的，实机黑屏"。

本工具反过来做：**不重建，只替换**。除被替换文件的数据区、以及 ISO9660 里
仅有的三类扇区号引用（PVD 卷大小 / path table / 目录记录）外，输出与原盘逐字节
相同（`verify --against` 可证）。算法出处 CUE 的 UMD-replace（其开源后继
UMDReplaceK 已通读核对），按格式知识重写。

尺寸变化时：新数据按 2048 对齐写入原位，**ISO 尾部整体平移** diff 个扇区，随后
把所有 > 目标 LBA 的扇区号引用加上 diff。ISO9660 中只有那三类结构引用扇区号，
故平移是闭合安全的。

用法::

    python3 tools/umdiso.py list    <iso> [--gaps]
    python3 tools/umdiso.py extract <iso> <盘内路径> <输出文件>
    python3 tools/umdiso.py replace <iso> <输出iso> <盘内路径> <新文件> [<路径> <文件> ...]
    python3 tools/umdiso.py add     <iso> <盘内路径> <本地文件> [...]   # 就地追加新文件
    python3 tools/umdiso.py verify  <iso> [--against <原iso>]

盘内路径形如 `/PSP_GAME/USRDIR/DATA.BIN`（大小写敏感，`;1` 版本号可省）。
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

SECTOR = 2048
PVD_LBA = 16               # 系统区占 LBA 0..15，主卷描述符固定在 16
CHUNK = 1 << 22            # 流式拷贝块大小

#: 本作资源包在盘内的路径（`build_disc.py` 的 iso 阶段替换的就是它）
DATA_BIN_PATH = "/PSP_GAME/USRDIR/DATA.BIN"

# PVD 内偏移
PVD_VOL_SPACE = 80         # 卷总扇区数（LE 4 + BE 4）
PVD_PT_SIZE = 132          # path table 字节数（LE 4 + BE 4）
PVD_PT_L = 140             # L 型 path table LBA（LE），+4 为可选第二份
PVD_PT_M = 148             # M 型（BE），+4 为可选第二份
PVD_ROOT = 156             # 根目录记录（34 字节）

# 目录记录内偏移
DR_EXTENT = 2              # 数据区 LBA（LE 4 + BE 4）
DR_SIZE = 10               # 数据长度（LE 4 + BE 4）
DR_FLAGS = 25
DR_NAMELEN = 32
DR_NAME = 33


def _be32(v: int) -> int:
    return struct.unpack("<I", struct.pack(">I", v))[0]


def _put_both(buf: bytearray, off: int, value: int) -> None:
    """写 ISO9660 的「双端序对」：LE 4 字节 + 紧随其后的 BE 4 字节。"""
    struct.pack_into("<I", buf, off, value)
    struct.pack_into(">I", buf, off + 4, value)


class DirRecord:
    """一条目录记录及其在 ISO 中的**字节位置**（用于回写补丁）。"""

    __slots__ = ("name", "path", "lba", "size", "flags", "pos", "dir_lba")

    def __init__(self, name, path, lba, size, flags, pos, dir_lba):
        self.name = name        # 记录里的原始名（可能带 ";1"）
        self.path = path        # 规范化全路径，如 /PSP_GAME/USRDIR/DATA.BIN
        self.lba = lba
        self.size = size
        self.flags = flags
        self.pos = pos          # 该记录首字节在 ISO 中的绝对偏移
        self.dir_lba = dir_lba  # 所在目录区的 LBA（平移时该位置本身也会动）

    @property
    def is_dir(self) -> bool:
        return bool(self.flags & 2)

    @property
    def sectors(self) -> int:
        return (self.size + SECTOR - 1) // SECTOR


class Iso:
    """只读解析：PVD、目录树、path table。"""

    def __init__(self, path: str):
        self.path = path
        self.size = os.path.getsize(path)
        self.f = open(path, "rb")
        pvd = self._read_at(PVD_LBA * SECTOR, SECTOR)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise ValueError("LBA16 不是主卷描述符（不是 ISO9660 镜像）")
        self.pvd = pvd
        block = struct.unpack_from("<H", pvd, 128)[0]
        if block != SECTOR:
            raise ValueError(f"逻辑块 {block} 字节，本工具只支持 2048")
        self.volume_sectors = struct.unpack_from("<I", pvd, PVD_VOL_SPACE)[0]
        self.pt_size = struct.unpack_from("<I", pvd, PVD_PT_SIZE)[0]
        self.pt_lbas = [                       # (LBA, 是否 BE 型)，0 表示不存在
            (struct.unpack_from("<I", pvd, PVD_PT_L)[0], False),
            (struct.unpack_from("<I", pvd, PVD_PT_L + 4)[0], False),
            (struct.unpack_from(">I", pvd, PVD_PT_M)[0], True),
            (struct.unpack_from(">I", pvd, PVD_PT_M + 4)[0], True),
        ]
        self.root_lba = struct.unpack_from("<I", pvd, PVD_ROOT + DR_EXTENT)[0]
        self.root_size = struct.unpack_from("<I", pvd, PVD_ROOT + DR_SIZE)[0]
        self.records: list[DirRecord] = []
        self._walk(self.root_lba, self.root_size, "")

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _read_at(self, off: int, n: int) -> bytes:
        self.f.seek(off)
        return self.f.read(n)

    def _walk(self, lba: int, length: int, prefix: str) -> None:
        data = self._read_at(lba * SECTOR, length)
        off = 0
        subdirs = []
        while off < len(data):
            rlen = data[off]
            if rlen == 0:  # 本扇区剩余为填充，跳到下一扇区
                nxt = (off // SECTOR + 1) * SECTOR
                if nxt >= len(data):
                    break
                off = nxt
                continue
            nlen = data[off + DR_NAMELEN]
            raw = data[off + DR_NAME:off + DR_NAME + nlen]
            rec_lba = struct.unpack_from("<I", data, off + DR_EXTENT)[0]
            rec_size = struct.unpack_from("<I", data, off + DR_SIZE)[0]
            flags = data[off + DR_FLAGS]
            if not (nlen == 1 and raw in (b"\x00", b"\x01")):  # 跳过 "." 与 ".."
                name = raw.decode("ascii", "replace")
                path = f"{prefix}/{name.split(';')[0]}"
                rec = DirRecord(name, path, rec_lba, rec_size, flags,
                                lba * SECTOR + off, lba)
                self.records.append(rec)
                if rec.is_dir:
                    subdirs.append((rec_lba, rec_size, path))
            off += rlen
        for sub in subdirs:
            self._walk(*sub)

    # ------------------------------------------------------------ 查询

    def find(self, path: str) -> DirRecord:
        want = "/" + path.strip("/").split(";")[0]
        for rec in self.records:
            if rec.path == want and not rec.is_dir:
                return rec
        raise KeyError(f"盘内找不到文件: {path}")

    def files(self) -> list[DirRecord]:
        return sorted((r for r in self.records if not r.is_dir),
                      key=lambda r: r.lba)

    def path_tables(self) -> list[tuple[int, bool, bytes]]:
        """返回 [(LBA, 是否BE, 原始字节)]，只含存在的表。"""
        out = []
        for lba, be in self.pt_lbas:
            if lba:
                out.append((lba, be, self._read_at(lba * SECTOR, self.pt_size)))
        return out


# ---------------------------------------------------------------- 替换

def _patch_path_table(buf: bytearray, be: bool, threshold: int,
                      diff: int) -> int:
    """把 path table 里 > threshold 的目录 LBA 加上 diff，返回改动条数。"""
    fmt = ">I" if be else "<I"
    off = n = 0
    while off + 8 <= len(buf):
        dlen = buf[off]
        if dlen == 0:
            break
        lba = struct.unpack_from(fmt, buf, off + 2)[0]
        if lba > threshold:
            struct.pack_into(fmt, buf, off + 2, lba + diff)
            n += 1
        off += 8 + dlen + (dlen & 1)
    return n


def replace(src: str, dst: str, pairs: list[tuple[str, str]],
            log=print) -> None:
    """把 pairs=[(盘内路径, 本地新文件)] 逐个替换后写出新 ISO。

    多文件时按盘内 LBA **从后往前**处理，这样每一轮的平移都不影响尚未处理的
    目标位置——省掉逐轮重解析。
    """
    with Iso(src) as iso:
        todo = []
        for path, newfile in pairs:
            rec = iso.find(path)
            todo.append((rec, newfile, os.path.getsize(newfile)))
        todo.sort(key=lambda t: t[0].lba, reverse=True)

        # 逐个算平移量：靠后的文件先处理，其 diff 不影响靠前文件的 LBA。
        total_diff = 0
        for rec, newfile, newsize in todo:
            new_sectors = (newsize + SECTOR - 1) // SECTOR
            diff = new_sectors - rec.sectors
            total_diff += diff
            log(f"  {rec.path}: {rec.size} → {newsize} 字节"
                f"（{rec.sectors} → {new_sectors} 扇区，diff {diff:+d}）")

        out_sectors = iso.volume_sectors + total_diff
        log(f"  卷总扇区 {iso.volume_sectors} → {out_sectors}")

        # ---- 1) 流式写出数据：原盘片段 + 新文件数据（按 LBA 从前往后拼）
        segments = sorted(todo, key=lambda t: t[0].lba)
        with open(dst, "wb") as out:
            pos = 0  # 已从原盘拷到的字节位置
            for rec, newfile, newsize in segments:
                _copy_range(iso.f, out, pos, rec.lba * SECTOR)
                with open(newfile, "rb") as g:
                    written = _copy_stream(g, out)
                pad = (-written) % SECTOR
                if pad:
                    out.write(b"\0" * pad)
                pos = (rec.lba + rec.sectors) * SECTOR
            _copy_range(iso.f, out, pos, iso.size)

        # ---- 2) 回写三类扇区号引用（含被替换文件自身的大小字段）
        shifts = [(rec.lba, (newsize + SECTOR - 1) // SECTOR - rec.sectors)
                  for rec, _, newsize in segments]

        def shifted(lba: int) -> int:
            """某个原始 LBA 在新盘中的位置。"""
            return lba + sum(d for base, d in shifts if lba > base)

        with open(dst, "r+b") as out:
            # 2a) PVD 卷总扇区数
            pvd = bytearray(iso.pvd)
            _put_both(pvd, PVD_VOL_SPACE, out_sectors)
            out.seek(PVD_LBA * SECTOR)
            out.write(pvd)

            # 2b) path table（4 份都要）——只有目录 LBA，且目录一般在盘首
            n_pt = 0
            for lba, be, raw in iso.path_tables():
                buf = bytearray(raw)
                for base, d in shifts:
                    if d:
                        n_pt += _patch_path_table(buf, be, base, d)
                out.seek(shifted(lba) * SECTOR)
                out.write(buf)

            # 2c) 全部目录记录：LBA 平移 + 被替换文件的大小
            replaced = {rec.pos: newsize for rec, _, newsize in segments}
            n_dr = 0
            dirty: dict[int, bytearray] = {}   # 目录区 LBA → 内容
            extents = {}
            for rec in iso.records:
                extents.setdefault(rec.dir_lba, None)
            # 根目录区也可能含记录（records 已含其条目，dir_lba=root_lba）
            for dir_lba in extents:
                length = SECTOR
                for r in iso.records:
                    if r.is_dir and r.lba == dir_lba:
                        length = r.size
                if dir_lba == iso.root_lba:
                    length = iso.root_size
                dirty[dir_lba] = bytearray(
                    iso._read_at(dir_lba * SECTOR, length))
            for rec in iso.records:
                buf = dirty[rec.dir_lba]
                off = rec.pos - rec.dir_lba * SECTOR
                new_lba = shifted(rec.lba)
                if new_lba != rec.lba:
                    _put_both(buf, off + DR_EXTENT, new_lba)
                    n_dr += 1
                if rec.pos in replaced:
                    _put_both(buf, off + DR_SIZE, replaced[rec.pos])
            for dir_lba, buf in dirty.items():
                out.seek(shifted(dir_lba) * SECTOR)
                out.write(buf)

            # 2d) PVD 里的根目录记录（根若在被替换文件之后也要跟着动）
            new_root = shifted(iso.root_lba)
            if new_root != iso.root_lba:
                pvd2 = bytearray(pvd)
                _put_both(pvd2, PVD_ROOT + DR_EXTENT, new_root)
                out.seek(PVD_LBA * SECTOR)
                out.write(pvd2)

        log(f"  引用更新：目录记录 LBA {n_dr} 处、path table 条目 {n_pt} 处")
    log(f"写出 {dst}（{os.path.getsize(dst)} 字节）")


# ---------------------------------------------------------------- 追加

def _clone_record(template: bytes, name: bytes, lba: int, size: int) -> bytes:
    """按兄弟文件记录的格式造一条新记录：日期/标志/卷序号/系统使用区（XA 尾）照抄，只换名字、LBA、大小。"""
    tnlen = template[DR_NAMELEN]
    sys_use = template[DR_NAME + tnlen + ((tnlen + 1) & 1):]      # 名字后的对齐填充之后
    body = bytearray(template[:DR_NAME]) + name
    if len(body) % 2:
        body += b"\0"
    body += sys_use
    _put_both(body, DR_EXTENT, lba)
    _put_both(body, DR_SIZE, size)
    body[DR_NAMELEN] = len(name)
    body[0] = len(body)
    return bytes(body)


def add_files(iso_path: str, adds: list[tuple[str, str]], log=print) -> None:
    """就地往既有目录追加新文件：数据按 2048 对齐追加到卷尾，父目录（单扇区）插入按名排序的新记录，
    PVD 卷总扇区相应增加。其余字节一律不动——追加在卷尾，不需要平移任何扇区号引用。

    任何检查不过（父目录不存在、重名、目录区放不下）都在动笔之前抛 ValueError，原盘不受影响。
    """
    with Iso(iso_path) as iso:
        vol = iso.volume_sectors
        if iso.size != vol * SECTOR:
            raise ValueError(f"文件大小 {iso.size} 与卷总扇区 {vol} 不符，拒绝追加")
        by_dir: dict[tuple[int, int], list[bytes]] = {}
        plan = []
        next_lba = vol
        for inner, local in adds:
            inner = "/" + inner.strip("/").split(";")[0]                # 与 find() 同一规范化
            parent, _, leaf = inner.rpartition("/")
            parent = parent or "/"
            if parent == "/":
                dir_lba, dir_size = iso.root_lba, iso.root_size
            else:
                d = [r for r in iso.records if r.is_dir and r.path == parent]
                if not d:
                    raise ValueError(f"父目录不存在: {parent}")
                dir_lba, dir_size = d[0].lba, d[0].size
            present = [r for r in iso.records if r.dir_lba == dir_lba]   # 文件与子目录都算重名
            if any(r.path == inner for r in present) or \
               any(p[0] == inner for p in plan):
                raise ValueError(f"盘内已存在: {inner}")
            siblings = [r for r in present if not r.is_dir]
            if not siblings:
                raise ValueError(f"{parent} 里没有可克隆格式的兄弟文件记录")
            size = os.path.getsize(local)
            style_v1 = siblings[0].name.endswith(";1")
            name = (leaf + (";1" if style_v1 else "")).encode("ascii")
            rlen = iso._read_at(siblings[0].pos, 1)[0]
            template = iso._read_at(siblings[0].pos, rlen)
            plan.append((inner, local, size, next_lba))
            by_dir.setdefault((dir_lba, dir_size), []).append(
                _clone_record(template, name, next_lba, size))
            next_lba += (size + SECTOR - 1) // SECTOR

        new_dirs = {}
        for (dir_lba, dir_size), new_recs in by_dir.items():
            if dir_size != SECTOR:
                raise ValueError(f"目录区 LBA {dir_lba} 占 {dir_size} 字节，本工具只支持单扇区目录")
            data = iso._read_at(dir_lba * SECTOR, SECTOR)
            recs, off = [], 0
            while off < SECTOR and data[off]:
                recs.append(data[off:off + data[off]])
                off += data[off]
            dots, entries = recs[:2], recs[2:]
            merged = sorted(entries + new_recs, key=lambda r: r[DR_NAME:DR_NAME + r[DR_NAMELEN]])
            blob = b"".join(dots + merged)
            if len(blob) > SECTOR:
                raise ValueError(f"目录区 LBA {dir_lba} 放不下新记录（需要 {len(blob)} 字节）")
            new_dirs[dir_lba] = blob.ljust(SECTOR, b"\0")
        pvd = bytearray(iso.pvd)
        _put_both(pvd, PVD_VOL_SPACE, next_lba)

    with open(iso_path, "r+b") as out:
        out.seek(vol * SECTOR)
        for inner, local, size, lba in plan:
            assert out.tell() == lba * SECTOR
            with open(local, "rb") as g:
                written = _copy_stream(g, out)
            out.write(b"\0" * ((-written) % SECTOR))
            log(f"  + {inner}: {size} 字节 @ LBA {lba}")
        for dir_lba, blob in new_dirs.items():
            out.seek(dir_lba * SECTOR)
            out.write(blob)
        out.seek(PVD_LBA * SECTOR)
        out.write(pvd)
    log(f"  卷总扇区 {vol} → {next_lba}")


def _copy_range(fin, fout, start: int, end: int) -> None:
    fin.seek(start)
    remain = end - start
    while remain > 0:
        chunk = fin.read(min(CHUNK, remain))
        if not chunk:
            raise IOError("源镜像提前结束")
        fout.write(chunk)
        remain -= len(chunk)


def _copy_stream(fin, fout) -> int:
    total = 0
    while True:
        chunk = fin.read(CHUNK)
        if not chunk:
            return total
        fout.write(chunk)
        total += len(chunk)


# ---------------------------------------------------------------- 子命令

def cmd_list(args):
    with Iso(args.iso) as iso:
        print(f"系统标识 {iso.pvd[8:40].decode('ascii','replace').rstrip()!r}  "
              f"应用标识 {iso.pvd[574:702].decode('ascii','replace').rstrip()!r}")
        print(f"卷总扇区 {iso.volume_sectors}（文件 {iso.size // SECTOR}）  "
              f"根目录 LBA {iso.root_lba}  path table {len(iso.path_tables())} 份")
        prev_end = None
        for rec in iso.files():
            gap = ""
            if args.gaps and prev_end is not None and rec.lba != prev_end:
                gap = f"   ← 空隙 {rec.lba - prev_end} 扇区"
            print(f"{rec.lba:>8} {rec.sectors:>7}扇区 {rec.size:>12}  "
                  f"{rec.path}{gap}")
            prev_end = rec.lba + rec.sectors
        if args.gaps and prev_end is not None:
            print(f"尾部余 {iso.volume_sectors - prev_end} 扇区")


def cmd_extract(args):
    with Iso(args.iso) as iso:
        rec = iso.find(args.path)
        with open(args.out, "wb") as g:
            iso.f.seek(rec.lba * SECTOR)
            remain = rec.size
            while remain > 0:
                chunk = iso.f.read(min(CHUNK, remain))
                g.write(chunk)
                remain -= len(chunk)
    print(f"{args.path} → {args.out}（{rec.size} 字节）")


def cmd_replace(args):
    if len(args.pairs) % 2:
        raise SystemExit("替换参数必须成对：<盘内路径> <新文件>")
    pairs = [(args.pairs[i], args.pairs[i + 1])
             for i in range(0, len(args.pairs), 2)]
    print(f"就地替换 {args.iso} → {args.out}")
    replace(args.iso, args.out, pairs)


def cmd_add(args):
    if len(args.items) % 2:
        raise SystemExit("add 需要成对的 <盘内路径> <本地文件>")
    pairs = list(zip(args.items[::2], args.items[1::2]))
    print(f"就地追加 {args.iso}")
    add_files(args.iso, pairs)
    if not verify(args.iso):
        raise SystemExit(1)


def verify(iso_path: str, against: str | None = None, log=print) -> bool:
    """结构自检：卷大小、目录树、path table 三方一致。给了原盘则报差异区间。"""
    ok = True
    with Iso(iso_path) as iso:
        actual = iso.size // SECTOR
        if iso.volume_sectors != actual:
            log(f"✗ PVD 卷总扇区 {iso.volume_sectors} ≠ 实际 {actual}")
            ok = False
        else:
            log(f"✓ 卷总扇区与文件实际大小一致（{actual}）")

        for rec in iso.records:
            end = rec.lba + rec.sectors
            if rec.lba < PVD_LBA or end > iso.volume_sectors:
                log(f"✗ {rec.path} 数据区越界（LBA {rec.lba}+{rec.sectors}）")
                ok = False
        else:
            log(f"✓ {len(iso.records)} 条目录记录数据区均在卷内")

        # path table 的目录 LBA 必须都能在目录树里找到
        tree_dirs = {r.lba for r in iso.records if r.is_dir} | {iso.root_lba}
        n_entries = 0
        for lba, be, raw in iso.path_tables():
            fmt = ">I" if be else "<I"
            off = 0
            while off + 8 <= len(raw):
                dlen = raw[off]
                if dlen == 0:
                    break
                d_lba = struct.unpack_from(fmt, raw, off + 2)[0]
                n_entries += 1
                if d_lba not in tree_dirs:
                    log(f"✗ path table@{lba} 的目录 LBA {d_lba} 在目录树中不存在")
                    ok = False
                off += 8 + dlen + (dlen & 1)
        log(f"✓ path table {len(iso.path_tables())} 份、共 {n_entries} 条"
            f"与目录树互证" if ok else "✗ path table 与目录树不一致")

        if against:
            with Iso(against) as old:
                _report_diff(old, iso, log)
    return ok


def _report_diff(old: Iso, new: Iso, log) -> None:
    """按扇区比对两张盘，把差异归并成区间并标注落在谁身上。"""
    owner = []
    for rec in new.files():
        owner.append((rec.lba, rec.lba + rec.sectors, rec.path))

    def who(lba: int) -> str:
        if lba < PVD_LBA:
            return "系统区"
        if lba == PVD_LBA:
            return "PVD"
        for a, b, name in owner:
            if a <= lba < b:
                return name
        for rec in new.records:
            if rec.is_dir and rec.lba == lba:
                return f"{rec.path}/ 目录区"
        if lba == new.root_lba:
            return "根目录区"
        for pt_lba, _, _ in new.path_tables():
            if lba == pt_lba:
                return "path table"
        return "空隙/填充"

    n = min(old.size, new.size) // SECTOR
    runs = []
    cur = None
    old.f.seek(0)
    new.f.seek(0)
    lba = 0
    per_chunk = CHUNK // SECTOR
    while lba < n:
        take = min(per_chunk, n - lba)
        a = old.f.read(take * SECTOR)
        b = new.f.read(take * SECTOR)
        if a != b:  # 只有整块不同才逐扇区细分
            for k in range(take):
                s = k * SECTOR
                if a[s:s + SECTOR] != b[s:s + SECTOR]:
                    if cur and cur[1] == lba + k:
                        cur[1] = lba + k + 1
                    else:
                        cur = [lba + k, lba + k + 1]
                        runs.append(cur)
        lba += take
    log(f"\n与原盘的差异（共 {len(runs)} 段）：")
    for a, b in runs:
        log(f"  扇区 {a}..{b - 1}（{b - a} 个）  {who(a)}")
    if new.size != old.size:
        log(f"  尾部：新盘多 {(new.size - old.size) // SECTOR} 扇区")


def cmd_verify(args):
    if not verify(args.iso, args.against):
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="列出盘内文件")
    p.add_argument("iso")
    p.add_argument("--gaps", action="store_true", help="显示扇区空隙")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("extract", help="取出盘内文件")
    p.add_argument("iso")
    p.add_argument("path")
    p.add_argument("out")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("replace", help="就地替换并写出新 ISO")
    p.add_argument("iso")
    p.add_argument("out")
    p.add_argument("pairs", nargs="+", metavar="盘内路径 新文件")
    p.set_defaults(func=cmd_replace)

    p = sub.add_parser("add", help="就地往既有目录追加新文件（数据追加卷尾）")
    p.add_argument("iso")
    p.add_argument("items", nargs="+", metavar="盘内路径 本地文件")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("verify", help="结构自检（可与原盘比对差异区间）")
    p.add_argument("iso")
    p.add_argument("--against", metavar="原iso")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
