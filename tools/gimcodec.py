#!/usr/bin/env python3
"""GIM（PSP 纹理格式）编解码：gim↔png 双向 + 模板回填式编码。

格式实测依据 assets/DATA.BIN 解包出的 2153 张 gim 全量普查：
- 2150 张小端（magic ``MIG.00.1PSP\\0``）+ 3 张大端老版（``.GIM1.00\\0PSP``，effect/）；
- 像素格式：index4/index8（swizzled，RGBA8888 调色板 16/256 色）为主，
  少量 RGBA8888 直彩（order 0/1 皆有）；全部单 picture 单 image 层。

结构（与 PuyoTools GimSharp 交叉验证）::

    文件头 16 字节 magic
    块链: u16 id | u16 0 | u32 块长 | u32 next | u32 dataoff（容器块 2/3 只占 16 字节头，
          叶子块 4=image 5=palette 255=fileinfo 整块前进）
    image/palette 块 payload: 16 字节块头 + 64 字节 info + 数据
    info: u16 infosz(48) | u16 0 | u16 fmt | u16 order | u16 w | u16 h | u16 bpp
          | u16 strideAlign | u16 heightAlign | ...；数据自块头起 +0x50
    fmt: 0=RGBA5650 1=RGBA5551 2=RGBA4444 3=RGBA8888 4=index4 5=index8
    order 1 = swizzled：按 16 字节 × 8 行的 tile 重排，stride 按 strideAlign
    对齐、高按 heightAlign 对齐；index4 低半字节在前

编码走**模板回填**：不从零构造 GIM，而是拿原包同名 gim 当模板，只替换调色板
与像素数据两段 payload，头部/对齐/未知字段全部原样保留——引擎兼容性最稳，
且未改动图的 encode(decode(x)) == x 逐字节成立（见 verify-identity）。

用法::

    uv run python tools/gimcodec.py decode  <in.gim> <out.png>
    uv run python tools/gimcodec.py encode  <template.gim> <in.png> <out.gim>
    uv run python tools/gimcodec.py verify-pngdir  <gim树根> <png树根>   # 全量像素比对
    uv run python tools/gimcodec.py verify-identity <gim树根>            # 回填幂等自检

png 输出与 png/ 目录同规格：索引图存 P 模式（保留调色板顺序）+ tRNS alpha。
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

MAGIC_LE = b"MIG.00.1PSP\x00"
MAGIC_BE = b".GIM1.00\x00PSP"
FMT_RGBA8888 = 3
FMT_INDEX4 = 4
FMT_INDEX8 = 5
TILE_W, TILE_H = 16, 8  # swizzle tile：16 字节 × 8 行
_NIBBLE_LUT = [bytes((b & 0x0F, b >> 4)) for b in range(256)]  # index4 低半字节在前


def _roundup(x: int, align: int) -> int:
    return -(-x // align) * align


def _unswizzle(data: bytes, stride: int, height: int) -> bytes:
    out = bytearray(len(data))
    rowtiles = stride // TILE_W
    src = 0
    for ty in range(height // TILE_H):
        for tx in range(rowtiles):
            col = tx * TILE_W
            for iy in range(TILE_H):
                dst = (ty * TILE_H + iy) * stride + col
                out[dst:dst + TILE_W] = data[src:src + TILE_W]
                src += TILE_W
    return bytes(out)


def _swizzle(data: bytes, stride: int, height: int) -> bytes:
    out = bytearray(len(data))
    rowtiles = stride // TILE_W
    dst = 0
    for ty in range(height // TILE_H):
        for tx in range(rowtiles):
            col = tx * TILE_W
            for iy in range(TILE_H):
                src = (ty * TILE_H + iy) * stride + col
                out[dst:dst + TILE_W] = data[src:src + TILE_W]
                dst += TILE_W
    return bytes(out)


class _Block:
    __slots__ = ("bid", "off", "size", "fmt", "order", "w", "h", "bpp",
                 "stride_align", "height_align", "data_off", "data_size",
                 "frames", "frame_offs")


class Gim:
    """解析后的 GIM。持有原始字节，image/palette 只记录 payload 位置。"""

    def __init__(self, raw: bytes):
        self.raw = raw
        if raw.startswith(MAGIC_LE):
            self.endian = "<"
        elif raw.startswith(MAGIC_BE):
            self.endian = ">"
        else:
            raise ValueError("不是 GIM（magic 不符）")
        self.image: _Block | None = None
        self.palette: _Block | None = None
        e = self.endian
        off, end = 16, len(raw)
        while off + 16 <= end:
            bid, _, bsz, _, _ = struct.unpack_from(e + "HHIII", raw, off)
            if bid in (2, 3):  # 容器块：进入 payload
                off += 16
                continue
            if bid in (4, 5):
                blk = self._parse_leaf(bid, off, bsz)
                if bid == 4:
                    if self.image is not None:
                        raise ValueError("多 image 块（本作不存在，未支持）")
                    self.image = blk
                else:
                    if self.palette is not None:
                        raise ValueError("多 palette 块（本作不存在，未支持）")
                    self.palette = blk
            if bsz == 0:
                raise ValueError("块长为 0")
            off += bsz
        if self.image is None:
            raise ValueError("没有 image 块")

    def _parse_leaf(self, bid: int, off: int, bsz: int) -> _Block:
        e = self.endian
        base = off + 16  # info 及其内部偏移都以块头之后为原点
        (infosz, _, fmt, order, w, h, bpp, stride_align, height_align,
         _) = struct.unpack_from(e + "10H", self.raw, base)
        if infosz != 48:
            raise ValueError(f"info 头长 {infosz} != 48")
        table_off, data_start, data_end = struct.unpack_from(
            e + "III", self.raw, base + 24)
        frames, = struct.unpack_from(e + "H", self.raw, base + 46)
        blk = _Block()
        blk.bid, blk.off, blk.size = bid, off, bsz
        blk.fmt, blk.order, blk.w, blk.h, blk.bpp = fmt, order, w, h, bpp
        blk.stride_align, blk.height_align = stride_align, height_align
        stride = _roundup(-(-w * bpp // 8), stride_align)
        height = _roundup(h, height_align)
        blk.data_size = stride * height
        blk.frames = frames
        # 帧偏移表在 info 之后（table_off 通常=48），条目相对 base；
        # 帧间距必须恰为一帧数据大小，帧 0 起点须与 data_start 字段一致
        blk.frame_offs = [base + o for (o,) in struct.iter_unpack(
            e + "I", self.raw[base + table_off:base + table_off + 4 * frames])]
        if len(blk.frame_offs) != frames or frames < 1:
            raise ValueError(f"块 {bid} 帧偏移表不完整（frames={frames}）")
        if blk.frame_offs[0] != base + data_start:
            raise ValueError(f"块 {bid} 帧 0 偏移 {blk.frame_offs[0]-base:#x} "
                             f"与 data_start {data_start:#x} 不符")
        for a, b in zip(blk.frame_offs, blk.frame_offs[1:]):
            if b - a != blk.data_size:
                raise ValueError(f"块 {bid} 帧间距 {b-a} != 帧大小 {blk.data_size}")
        if blk.frame_offs[-1] + blk.data_size > base + data_end or \
                base + data_end > off + bsz:
            raise ValueError(f"块 {bid} 数据越界")
        blk.data_off = blk.frame_offs[0]
        return blk

    # ------------------------------------------------------------ 解码

    def _stride(self, blk: _Block) -> tuple[int, int]:
        return (_roundup(-(-blk.w * blk.bpp // 8), blk.stride_align),
                _roundup(blk.h, blk.height_align))

    def _payload(self, blk: _Block, frame: int = 0) -> bytes:
        stride, height = self._stride(blk)
        start = blk.frame_offs[frame]
        data = self.raw[start:start + blk.data_size]
        if blk.order == 1:
            data = _unswizzle(data, stride, height)
        return data

    def palette_rgba(self) -> list[tuple[int, int, int, int]] | None:
        if self.palette is None:
            return None
        p = self.palette
        if p.fmt != FMT_RGBA8888 or p.order != 0:
            raise ValueError(f"未支持的调色板格式 fmt={p.fmt} order={p.order}")
        data = self._payload(p)
        n = p.w * p.h
        return [tuple(data[i * 4:i * 4 + 4]) for i in range(n)]

    def pixels(self, frame: int = 0) -> tuple[str, bytes]:
        """返回 ("P", 每像素 1 字节索引) 或 ("RGBA", 每像素 4 字节)，已去 padding。"""
        blk = self.image
        stride, _ = self._stride(blk)
        data = self._payload(blk, frame)
        rows = []
        if blk.fmt == FMT_INDEX8:
            for y in range(blk.h):
                rows.append(data[y * stride:y * stride + blk.w])
            return "P", b"".join(rows)
        if blk.fmt == FMT_INDEX4:
            lut = _NIBBLE_LUT
            for y in range(blk.h):
                line = data[y * stride:(y + 1) * stride]
                row = b"".join(map(lut.__getitem__, line))
                rows.append(row[:blk.w])
            return "P", b"".join(rows)
        if blk.fmt == FMT_RGBA8888:
            for y in range(blk.h):
                rows.append(data[y * stride:y * stride + blk.w * 4])
            return "RGBA", b"".join(rows)
        raise ValueError(f"未支持的像素格式 fmt={blk.fmt}")

    def to_pil(self, frame: int = 0):
        from PIL import Image
        mode, data = self.pixels(frame)
        blk = self.image
        if mode == "RGBA":
            return Image.frombytes("RGBA", (blk.w, blk.h), data)
        im = Image.frombytes("P", (blk.w, blk.h), data)
        pal = self.palette_rgba()
        if pal is None:
            raise ValueError("索引图却没有调色板块")
        im.putpalette(b"".join(bytes(c) for c in pal), rawmode="RGBA")
        return im

    # ------------------------------------------------------------ 模板回填编码

    def encode_from_pil(self, im) -> bytes:
        """把 PIL 图按本 GIM 的格式参数回填，返回新 GIM 字节。

        索引格式要求 im 为 P 模式且尺寸一致、索引不超容量——调色板顺序由
        im 自带调色板决定（喂回 to_pil() 的产物即得逐字节还原）。
        """
        blk = self.image
        if im.size != (blk.w, blk.h):
            raise ValueError(f"尺寸不符: 模板 {blk.w}x{blk.h}, 图 {im.size}")
        stride, height = self._stride(blk)
        out = bytearray(self.raw)

        if blk.fmt in (FMT_INDEX4, FMT_INDEX8):
            if im.mode != "P":
                raise ValueError("索引格式模板需要 P 模式图（先量化）")
            cap = self.palette.w * self.palette.h
            lo, hi = im.getextrema()
            if hi >= cap:
                raise ValueError(f"索引 {hi} 超出调色板容量 {cap}")
            idx = im.tobytes()
            rows = bytearray()
            for y in range(height):
                if y < blk.h:
                    line = idx[y * blk.w:(y + 1) * blk.w]
                else:
                    line = b""
                if blk.fmt == FMT_INDEX8:
                    row = bytearray(line)
                else:
                    row = bytearray()
                    for x in range(0, len(line), 2):
                        a = line[x]
                        b = line[x + 1] if x + 1 < len(line) else 0
                        row.append(a | (b << 4))
                row.extend(b"\0" * (stride - len(row)))
                rows.extend(row)
            data = bytes(rows)
            if blk.order == 1:
                data = _swizzle(data, stride, height)
            out[blk.data_off:blk.data_off + blk.data_size] = data

            pal = im.getpalette(rawmode="RGBA")
            if pal is None:
                raise ValueError("P 模式图没有调色板")
            entries = [tuple(pal[i * 4:i * 4 + 4]) for i in range(len(pal) // 4)]
            entries = entries[:cap] + [(0, 0, 0, 0)] * max(0, cap - len(pal) // 4)
            pdata = b"".join(bytes(c) for c in entries)
            p = self.palette
            pstride, pheight = self._stride(p)
            if len(pdata) != pstride * pheight:
                raise ValueError("调色板数据长度与模板不符")
            out[p.data_off:p.data_off + p.data_size] = pdata
        elif blk.fmt == FMT_RGBA8888:
            rgba = im.convert("RGBA").tobytes()
            rows = bytearray()
            for y in range(height):
                line = rgba[y * blk.w * 4:(y + 1) * blk.w * 4] if y < blk.h else b""
                rows.extend(line)
                rows.extend(b"\0" * (stride - len(line)))
            data = bytes(rows)
            if blk.order == 1:
                data = _swizzle(data, stride, height)
            out[blk.data_off:blk.data_off + blk.data_size] = data
        else:
            raise ValueError(f"未支持的像素格式 fmt={blk.fmt}")
        return bytes(out)


# ---------------------------------------------------------------- CLI

def _walk_gims(root: str):
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if fn.endswith(".gim"):
                yield os.path.join(dp, fn)


def cmd_decode(args):
    gim = Gim(open(args.gim, "rb").read())
    im = gim.to_pil()
    os.makedirs(os.path.dirname(os.path.abspath(args.png)), exist_ok=True)
    im.save(args.png)
    blk = gim.image
    print(f"{args.gim}: fmt={blk.fmt} order={blk.order} "
          f"{blk.w}x{blk.h} → {args.png} ({im.mode})")


def cmd_encode(args):
    from PIL import Image
    gim = Gim(open(args.template, "rb").read())
    im = Image.open(args.png)
    out = gim.encode_from_pil(im)
    with open(args.out, "wb") as f:
        f.write(out)
    print(f"{args.png} 按模板 {args.template} 回填 → {args.out}（{len(out)} 字节）")


def cmd_verify_pngdir(args):
    """gim 树全量解码，与 png 树逐像素（RGBA 展开）比对。"""
    from PIL import Image
    n_ok = n_diff = n_missing = n_err = 0
    diffs = []
    for path in _walk_gims(args.gimroot):
        rel = os.path.relpath(path, args.gimroot)[:-4]
        png_path = os.path.join(args.pngroot, rel + ".png")
        if not os.path.exists(png_path):
            n_missing += 1
            print(f"MISSING {rel}.png")
            continue
        try:
            im_gim = Gim(open(path, "rb").read()).to_pil().convert("RGBA")
        except Exception as exc:
            n_err += 1
            print(f"ERROR   {rel}.gim: {exc}")
            continue
        im_png = Image.open(png_path).convert("RGBA")
        if im_gim.size != im_png.size:
            n_diff += 1
            diffs.append(rel)
            print(f"SIZE    {rel}: gim {im_gim.size} png {im_png.size}")
        elif im_gim.tobytes() != im_png.tobytes():
            n_diff += 1
            diffs.append(rel)
            print(f"PIXELS  {rel}")
        else:
            n_ok += 1
    print(f"一致 {n_ok} / 不一致 {n_diff} / 缺 png {n_missing} / 解码失败 {n_err}")
    if n_diff or n_err:
        raise SystemExit(1)


def cmd_verify_identity(args):
    """decode→to_pil→模板回填 后与原 gim 逐字节比对（幂等自检）。"""
    n_ok = n_diff = n_skip = 0
    for path in _walk_gims(args.gimroot):
        rel = os.path.relpath(path, args.gimroot)
        raw = open(path, "rb").read()
        try:
            gim = Gim(raw)
            out = gim.encode_from_pil(gim.to_pil())
        except ValueError as exc:
            n_skip += 1
            print(f"SKIP {rel}: {exc}")
            continue
        if out == raw:
            n_ok += 1
        else:
            n_diff += 1
            print(f"DIFF {rel}")
    print(f"逐字节还原 {n_ok} / 不还原 {n_diff} / 跳过 {n_skip}")
    if n_diff:
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("decode", help="gim → png")
    p.add_argument("gim")
    p.add_argument("png")
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("encode", help="png 按模板 gim 回填 → 新 gim")
    p.add_argument("template")
    p.add_argument("png")
    p.add_argument("out")
    p.set_defaults(func=cmd_encode)

    p = sub.add_parser("verify-pngdir", help="gim 树 vs png 树全量像素比对")
    p.add_argument("gimroot")
    p.add_argument("pngroot")
    p.set_defaults(func=cmd_verify_pngdir)

    p = sub.add_parser("verify-identity", help="模板回填幂等自检（逐字节）")
    p.add_argument("gimroot")
    p.set_defaults(func=cmd_verify_identity)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
