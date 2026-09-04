#!/usr/bin/env python3
"""EBOOT 重定位扫描：枚举指向 bss（段 1）的全部 lui/addiu(lw/sw…) 引用，并为「搬迁存档结构」类补丁干跑。

    python3 tools/eboot_relscan.py scan                       # 所有 bss 引用（IDA 地址）按目标聚合
    python3 tools/eboot_relscan.py scan --range 0x32DAA8 0x390D10   # 只看某区间（IDA 地址）
    python3 tools/eboot_relscan.py move-plan --delta 0x40000  # 存档结构搬到 bss 新尾部、线程区 +256 KiB 的改字清单

原理（docs/ops/eboot-savedata-research-2026-09-05.md §8）：PRX 里指向 bss 的地址由 R_MIPS_HI16/LO16
成对重定位，代码里的常量是"段内偏移"，装载时加段基址。IDA 把这类引用多加了一次段基址
（IDB 地址 = 段内偏移 + 2×0x6DA40），本工具统一按 IDA 地址打印以便对照 IDB。
LO16 站点的 lui 用寄存器流回溯（站点前 400 条指令线性前向模拟，lui 后寄存器被改写即作废），
比 PPSSPP 装载器"HI16 配下一条 LO16"的做法更接近真实数据流；未能回溯的站点单独列出。

move-plan 的前提：位移取 0x10000 的整数倍，于是只改 lui 的立即数、LO16 立即数一律不动，
共享同一条 lui 的多个站点也天然一致；若某条 lui 同时服务结构内外或线程区两侧的字段，
干跑会直接报错（现有 EBOOT 无此情况）。
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ELF = REPO / "assets" / "EBOOT.dec.elf"
IDA_SHIFT = 2 * 0x6DA40            # IDB 里 bss 对象地址 − 段内偏移
STRUCT_RAW = 0x252628              # 存档结构段内偏移（IDA 0x32DAA8）
STRUCT_SIZE = 0x63268
THREAD_END = 0x57C84               # 线程 blob 区末（size 字段偏移）；此后字段随 delta 后移


def s16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v


def written_reg(w: int) -> int | None:
    op = w >> 26
    if op == 0:
        if (w & 0x3F) == 8:           # jr
            return None
        return (w >> 11) & 31
    if op == 3:
        return 31
    if op in (8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26):
        return (w >> 16) & 31
    if op == 0x1C:
        return (w >> 11) & 31
    if op == 0x1F:
        return (w >> 16) & 31
    return None


class Elf:
    def __init__(self, path: Path):
        self.d = path.read_bytes()
        d = self.d
        self.phoff = struct.unpack_from("<I", d, 28)[0]
        self.ph = [struct.unpack_from("<8I", d, self.phoff + i * 32) for i in range(3)]
        self.text_off = self.ph[0][1]
        self.text_size = self.ph[0][4]
        self.bss_size = self.ph[1][5]
        shoff = struct.unpack_from("<I", d, 32)[0]
        shentsize, shnum = struct.unpack_from("<HH", d, 46)
        self.rels: list[tuple[int, int, int, int]] = []
        for i in range(shnum):
            _, t, _, _, off, size = struct.unpack_from("<6I", d, shoff + i * shentsize)
            if t != 0x700000A0:
                continue
            for j in range(size // 8):
                r_off, r_info = struct.unpack_from("<II", d, off + 8 * j)
                self.rels.append((r_off, r_info & 0xFF, (r_info >> 8) & 0xFF, (r_info >> 16) & 0xFF))

    def word(self, va: int) -> int:
        return struct.unpack_from("<I", self.d, va + self.text_off)[0]

    def scan(self) -> tuple[list[dict], list[int]]:
        refs, nolui = [], []
        for r_off, typ, ofs, ab in self.rels:
            if ofs != 0:
                continue
            if typ == 6:                       # LO16
                insn = self.word(r_off)
                rs = (insn >> 21) & 31
                lo = s16(insn & 0xFFFF)
                hi = lui_at = None
                a = max(0, r_off - 4 * 400)
                while a < r_off:
                    w = self.word(a)
                    if (w >> 26) == 0x0F and ((w >> 16) & 31) == rs:
                        hi, lui_at = w & 0xFFFF, a
                    elif written_reg(w) == rs and rs != 0:
                        hi = lui_at = None
                    a += 4
                if hi is None:
                    nolui.append(r_off)
                    continue
                refs.append({"kind": "LO16", "at": r_off, "X": ((hi << 16) + lo) & 0xFFFFFFFF,
                             "ab": ab, "lui": lui_at})
            elif typ == 2:                     # R_MIPS_32
                refs.append({"kind": "W32", "at": r_off, "X": self.word(r_off), "ab": ab, "lui": None})
        return refs, nolui


def cmd_scan(a: argparse.Namespace) -> int:
    elf = Elf(Path(a.elf))
    refs, nolui = elf.scan()
    bss = [r for r in refs if r["ab"] == 1]
    lo, hi = (int(a.range[0], 0) - IDA_SHIFT, int(a.range[1], 0) - IDA_SHIFT) if a.range else (0, elf.bss_size)
    sel = [r for r in bss if lo <= r["X"] < hi]
    by_target: dict[int, list[dict]] = defaultdict(list)
    for r in sel:
        by_target[r["X"]].append(r)
    print(f"bss 段内 {elf.bss_size:#x} B；bss 引用 {len(bss)}（LO16 无法回溯 lui 的站点 {len(nolui)}）；"
          f"区间内 {len(sel)} 处、{len(by_target)} 个目标")
    for X in sorted(by_target):
        rs = by_target[X]
        sites = " ".join(f"{r['at']:#x}" for r in sorted(rs, key=lambda r: r["at"])[:10])
        print(f"  IDA {X + IDA_SHIFT:#x} (raw {X:#x}) ×{len(rs)} @ {sites}{' …' if len(rs) > 10 else ''}")
    if a.json:
        Path(a.json).write_text(json.dumps({"refs": refs, "nolui": nolui}))
    return 0


def cmd_move_plan(a: argparse.Namespace) -> int:
    elf = Elf(Path(a.elf))
    refs, _ = elf.scan()
    delta = int(a.delta, 0)
    if delta % 0x10000:
        sys.exit("--delta 必须是 0x10000 的倍数（这样只改 lui 立即数）")
    new_base = STRUCT_RAW + ((elf.bss_size - STRUCT_RAW + 0xFFFF) // 0x10000) * 0x10000
    shift = new_base - STRUCT_RAW
    new_size = STRUCT_SIZE + delta
    new_bss = new_base + new_size
    print(f"旧结构 raw {STRUCT_RAW:#x}..{STRUCT_RAW + STRUCT_SIZE:#x}（IDA {STRUCT_RAW + IDA_SHIFT:#x}）"
          f" → 新结构 raw {new_base:#x}..{new_bss:#x}，位移 {shift:#x}，线程区 +{delta:#x}")
    print(f"PH1.p_memsz 文件偏移 {elf.phoff + 32 + 20:#x}：{elf.bss_size:#x} → {new_bss:#x}"
          f"（bss +{new_bss - elf.bss_size:#x} = {(new_bss - elf.bss_size) / 1024:.0f} KB）")
    sref = [r for r in refs if r["ab"] == 1 and STRUCT_RAW <= r["X"] < STRUCT_RAW + STRUCT_SIZE]
    w32 = [r for r in sref if r["kind"] == "W32"]
    if w32:
        print("⚠ 存在指向结构的 R_MIPS_32 数据字，需另行处理：", [hex(r["at"]) for r in w32])
    by_lui: dict[int, list[dict]] = defaultdict(list)
    for r in sref:
        if r["kind"] == "LO16":
            by_lui[r["lui"]].append(r)
    patches = []
    for lui, rs in sorted(by_lui.items()):
        offs = sorted({r["X"] - STRUCT_RAW for r in rs})
        regions = {"tail" if f >= THREAD_END else "head" for f in offs}
        if len(regions) != 1:
            sys.exit(f"lui@{lui:#x} 同时服务线程区两侧字段 {offs}，不能只改 lui")
        sh = shift + (delta if regions == {"tail"} else 0)
        w = elf.word(lui)
        assert (w >> 26) == 0x0F
        w2 = (w & 0xFFFF0000) | ((w & 0xFFFF) + (sh >> 16))
        patches.append((lui, w, w2))
        print(f"  va {lui:#06x}: {w:08x} → {w2:08x}   字段 {' '.join(f'+{o:#x}' for o in offs)}"
              f"   站点 {' '.join(f'{r['at']:#x}' for r in rs)}")
    print(f"共 {len(patches)} 个 lui 字；LO16 立即数不变。另需改常量 0x63268 → {new_size:#x} 的全部物化点"
          f"（memset 长度、dataBufSize、dataSize；用 `lui x,6 ; addiu x,0x3268` 形式）：")
    lo_half, hi_half = STRUCT_SIZE & 0xFFFF, STRUCT_SIZE >> 16
    for va in range(0, elf.text_size - 4, 4):
        w = elf.word(va)
        if (w >> 26) not in (9, 0xD) or (w & 0xFFFF) != lo_half:
            continue                       # addiu/ori rt, rs, lo_half（rs 是 lui 的寄存器，rt 可不同）
        reg = (w >> 21) & 31
        for k in range(1, 32):             # 往回找 lui reg, hi_half（延迟槽等重排：允许隔几条）
            w1 = elf.word(va - 4 * k)
            if (w1 >> 26) == 0x0F and ((w1 >> 16) & 31) == reg:
                if (w1 & 0xFFFF) == hi_half:
                    print(f"  va {va - 4 * k:#06x}: lui {w1:08x} → {(w1 & 0xFFFF0000) | (new_size >> 16):08x}"
                          f"（addiu 在 {va:#x}）")
                break
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elf", default=str(DEFAULT_ELF))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--range", nargs=2, metavar=("IDA_LO", "IDA_HI"))
    s.add_argument("--json", help="把全部引用写成 JSON")
    s.set_defaults(fn=cmd_scan)
    m = sub.add_parser("move-plan")
    m.add_argument("--delta", default="0x40000")
    m.set_defaults(fn=cmd_move_plan)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
