#!/usr/bin/env python3
"""PGF 字体检视：打印头部量度与指定字符的字形量度（纯 stdlib，可直接 python3 跑）。

用途：核对 build_font 产物（lxgw17/lxgw09.pgf）与原字体（tsukuminpro_e_*.pgf）的
ascender/descender/advance/bitmap top 等值——引擎 `font_draw_string`（EBOOT 0x5698）
按 `y + (maxAscender>>6) - bitmapTop + 1` 摆字形、按 `advanceH>>6` 推进，这些数决定
ruby 与正文的实际落点（见 docs/ops/eboot-kinsoku-research-2026-09-04.md §6）。

版式依据 PPSSPP Core/Font/PGF.{h,cpp}（PGFHeader 392 B；rev3 追加 20 B；
表序：dimension / xAdjust / yAdjust / advance / shadowCharMap / (rev3 压缩表) /
charMap / charPointers / fontData；位序 LSB-first；字形头：14 位长度、w7、h7、
left7(有符号)、top7(有符号)、flags6、shadow 2+2+3、shadowID 9，随后四组量度按 flags
位决定是 8 位表索引还是 32+32 位直接值）。

用法：python3 tools/pgf_inspect.py <font.pgf> [字符...]
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

DIM_IDX, BX_IDX, BY_IDX, ADV_IDX = 0x04, 0x08, 0x10, 0x20


def _bits(buf: bytes, pos: int, n: int) -> int:
    """LSB-first 取位，与 PPSSPP getBits 等价。"""
    byte, off = divmod(pos, 8)
    chunk = int.from_bytes(buf[byte:byte + (off + n + 7) // 8 + 1], "little")
    return (chunk >> off) & ((1 << n) - 1)


def _padded(bits: int) -> int:
    return ((bits + 31) & ~31) // 8


def f26(v: int) -> float:
    if v >= 1 << 31:
        v -= 1 << 32
    return v / 64.0


class PGF:
    def __init__(self, data: bytes):
        self.data = data
        (self.header_off, self.header_size, magic, self.revision, self.version,
         self.charmap_len, self.charptr_len, self.charmap_bpe, self.charptr_bpe) = \
            struct.unpack_from("<HH4siiiiii", data, 0)
        assert magic == b"PGF0", magic
        self.bpp = data[0x22]
        self.h_size, self.v_size = struct.unpack_from("<ii", data, 0x24)
        self.font_name = data[0x35:0x75].split(b"\0")[0].decode(errors="replace")
        self.first_glyph, self.last_glyph = struct.unpack_from("<HH", data, 0xB6)
        (self.max_ascender, self.max_descender, self.max_left_x, self.max_base_y,
         self.min_center_x, self.max_top_y, self.max_adv_h, self.max_adv_v,
         self.max_size_h, self.max_size_v) = struct.unpack_from("<10i", data, 0xD4)
        self.max_glyph_w, self.max_glyph_h = struct.unpack_from("<HH", data, 0xFC)
        dim_n, bx_n, by_n, adv_n = data[0x102:0x106]
        self.shadow_len, self.shadow_bpe = struct.unpack_from("<ii", data, 0x16C)
        p = 0x188
        comp1 = comp2 = 0
        if self.revision == 3:
            _, comp1, _, comp2, _ = struct.unpack_from("<iiiiI", data, p)
            p += 20
        def table(n):
            nonlocal p
            t = [(struct.unpack_from("<ii", data, p + 8 * i)) for i in range(n)]
            p += 8 * n
            return t
        self.dim, self.bx, self.by, self.adv = table(dim_n), table(bx_n), table(by_n), table(adv_n)
        p += _padded(self.shadow_len * self.shadow_bpe)
        self.ranges: list[tuple[int, int]] = []
        if self.revision == 3:
            for i in range(comp1):
                self.ranges.append(struct.unpack_from("<HH", data, p + 4 * i))
            p += 4 * (comp1 + comp2)
        else:
            self.ranges = [(self.first_glyph, self.charmap_len)]
        self.charmap_buf = data[p:p + _padded(self.charmap_len * self.charmap_bpe)]
        p += len(self.charmap_buf)
        self.charptr_buf = data[p:p + _padded(self.charptr_len * self.charptr_bpe)]
        p += len(self.charptr_buf)
        self.fontdata = data[p:]

    def char_index(self, code: int) -> int:
        idx = 0
        for start, length in self.ranges:
            if start <= code < start + length:
                return idx + code - start
            idx += length
        return -1

    def glyph(self, code: int) -> dict | None:
        ci = self.char_index(code)
        if ci < 0 or ci >= self.charmap_len:
            return None
        gi = _bits(self.charmap_buf, ci * self.charmap_bpe, self.charmap_bpe)
        if gi >= self.charptr_len:
            return None
        pos = _bits(self.charptr_buf, gi * self.charptr_bpe, self.charptr_bpe) * 32
        fd = self.fontdata
        pos += 14
        def take(n):
            nonlocal pos
            v = _bits(fd, pos, n)
            pos += n
            return v
        w, h = take(7), take(7)
        left, top = take(7), take(7)
        left = left - 128 if left >= 64 else left
        top = top - 128 if top >= 64 else top
        flags = take(6)
        take(2); take(2); take(3); take(9)
        def metric(flag, tbl):
            if flags & flag:
                i = take(8)
                return tbl[i] if i < len(tbl) else (0, 0)
            return (take(32), take(32))
        dim = metric(DIM_IDX, self.dim)
        bxv = metric(BX_IDX, self.bx)
        byv = metric(BY_IDX, self.by)
        advv = metric(ADV_IDX, self.adv)
        return {"glyph": gi, "w": w, "h": h, "left": left, "top": top, "flags": flags,
                "dim": (f26(dim[0]), f26(dim[1])), "bearing_x": f26(bxv[0]),
                "bearing_y": f26(byv[0]), "advance_h": f26(advv[0]), "advance_v": f26(advv[1])}


def advance_px(advance_h: float) -> int:
    """引擎推进用 advanceH>>6（26.6 定点截断）：4.25→4、5.75→5、17.0→17。"""
    return int(advance_h * 64) >> 6


def export_advances(pgf_bytes: bytes, font_name: str, default: int = 17) -> dict:
    """遍历 BMP 全部码位，导出 ≠ default 的字形步进（截断后整数 px），键为字符本身。"""
    pgf = PGF(pgf_bytes)
    adv: dict[str, int] = {}
    for code in range(0x20, 0x10000):
        g = pgf.glyph(code)
        if g is None:
            continue
        px = advance_px(g["advance_h"])
        if px != default:
            adv[chr(code)] = px
    return {"font": font_name, "default": default, "adv": adv}


def main(argv: list[str]) -> int:
    if argv[1:2] == ["export-advances"]:
        import json
        src, dst = Path(argv[2]), Path(argv[3])
        table = export_advances(src.read_bytes(), src.name)
        dst.write_text(json.dumps(table, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"{src.name}: {len(table['adv'])} 个码位步进 ≠ {table['default']} px -> {dst}")
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    pgf = PGF(open(argv[1], "rb").read())
    print(f"{argv[1]}: {pgf.font_name!r} rev {pgf.revision} size {f26(pgf.h_size)}x{f26(pgf.v_size)} "
          f"ascender {f26(pgf.max_ascender):.3f} (>>6 = {pgf.max_ascender >> 6}) "
          f"descender {f26(pgf.max_descender):.3f} maxAdvH {f26(pgf.max_adv_h):.3f} "
          f"glyphs {pgf.charptr_len} charmap {pgf.charmap_len} ranges {len(pgf.ranges)}")
    for ch in argv[2:]:
        for c in ch:
            g = pgf.glyph(ord(c))
            if g is None:
                print(f"  U+{ord(c):04X} {c!r}: 缺字")
            else:
                print(f"  U+{ord(c):04X} {c!r}: w={g['w']:2} h={g['h']:2} left={g['left']:3} top={g['top']:3} "
                      f"advH={g['advance_h']:6.2f} bearingX={g['bearing_x']:5.2f} bearingY={g['bearing_y']:5.2f} "
                      f"flags={g['flags']:#04x}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
