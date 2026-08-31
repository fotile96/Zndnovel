"""tools/gimcodec.py（GIM 编解码）的测试。

合成 GIM 走全流程（LE/BE、index4/index8/RGBA8888、swizzle 开关、多帧、
模板回填幂等）；真实资产门控抽查（assets/DATA.BIN 解包树在则跑）覆盖
特殊样本：大端 effect 三张、多帧光标两张、index4 novel、RGBA 直彩。
全量两趟扫描（2153 张 vs png/ 与逐字节幂等）在 CLI 手工跑，测试里以
ZND_GIM_FULL=1 环境变量门控。
"""
from __future__ import annotations

import os
import random
import struct
from pathlib import Path

import pytest
from PIL import Image

from tools.gimcodec import (MAGIC_BE, MAGIC_LE, Gim, _roundup, _swizzle,
                            _unswizzle)

REPO = Path(__file__).resolve().parents[1]
GIMROOT = REPO / "build" / "databin"
PNGROOT = REPO / "png"

needs_gims = pytest.mark.skipif(
    not (GIMROOT / "bg").exists(),
    reason="build/databin 不在（先 databin.py unpack）")


# ---------------------------------------------------------------- 合成 GIM

def synth_gim(endian="<", fmt=5, order=1, w=20, h=10, frames=1,
              pix=None, pal=None) -> bytes:
    """按实测布局手工构造单 image（可选 palette）的最小 GIM。"""
    e = endian
    bpp = {3: 32, 4: 4, 5: 8}[fmt]
    stride = _roundup(-(-w * bpp // 8), 16)
    height = _roundup(h, 8)
    fsize = stride * height

    if pix is None:
        rng = random.Random(fmt * 100 + order)
        cap = 16 if fmt == 4 else 256
        if fmt == 3:
            pix = [bytes(rng.randrange(256) for _ in range(4))
                   for _ in range(w * h * frames)]
            pix = b"".join(pix)
        else:
            pix = bytes(rng.randrange(cap) for _ in range(w * h * frames))

    def frame_payload(k):
        rows = bytearray()
        for y in range(height):
            if y < h:
                if fmt == 3:
                    line = pix[(k * w * h + y * w) * 4:(k * w * h + y * w + w) * 4]
                elif fmt == 5:
                    line = pix[k * w * h + y * w:k * w * h + y * w + w]
                else:  # index4 低半字节在前
                    line = bytearray()
                    src = pix[k * w * h + y * w:k * w * h + y * w + w]
                    for x in range(0, w, 2):
                        a = src[x]
                        b = src[x + 1] if x + 1 < w else 0
                        line.append(a | (b << 4))
                    line = bytes(line)
            else:
                line = b""
            rows += line + b"\0" * (stride - len(line))
        data = bytes(rows)
        return _swizzle(data, stride, height) if order == 1 else data

    def leaf_block(bid, fmt_, order_, w_, h_, bpp_, halign, payloads):
        n = len(payloads)
        tbl_len = _roundup(48 + 4 * n, 16) - 48
        data_start = 48 + tbl_len
        table = b"".join(struct.pack(e + "I", data_start + i * len(payloads[0]))
                         for i in range(n))
        table += b"\0" * (tbl_len - 4 * n)
        body = b"".join(payloads)
        info = struct.pack(e + "10H", 48, 0, fmt_, order_, w_, h_, bpp_,
                           16, halign, 2)
        info += struct.pack(e + "IIIII", 0, 48, data_start,
                            data_start + len(body), 0)
        info += struct.pack(e + "4H", 1, 1, 3, n)
        assert len(info) == 48
        blk = info + table + body
        hdr = struct.pack(e + "HHIII", bid, 0, 16 + len(blk), 16, 16)
        return hdr + blk

    img = leaf_block(4, fmt, order, w, h, bpp, 8,
                     [frame_payload(k) for k in range(frames)])
    blocks = img
    if fmt in (4, 5):
        cap = 16 if fmt == 4 else 256
        if pal is None:
            rng = random.Random(99)
            pal = [tuple(rng.randrange(256) for _ in range(4))
                   for _ in range(cap)]
        pdata = b"".join(bytes(c) for c in pal)
        blocks += leaf_block(5, 3, 0, cap, 1, 32, 1, [pdata])
    magic = MAGIC_LE if e == "<" else MAGIC_BE
    magic = magic + b"\0" * (16 - len(magic))
    pic = struct.pack(e + "HHIII", 3, 0, 16 + len(blocks), 16, 16)
    root = struct.pack(e + "HHIII", 2, 0, 32 + len(blocks), 16, 16)
    return magic + root + pic + blocks


def test_swizzle_inverse():
    rng = random.Random(1)
    for stride, height in [(16, 8), (32, 24), (480, 272)]:
        data = bytes(rng.randrange(256) for _ in range(stride * height))
        assert _unswizzle(_swizzle(data, stride, height), stride, height) == data


@pytest.mark.parametrize("endian", ["<", ">"])
@pytest.mark.parametrize("fmt,order", [(5, 1), (5, 0), (4, 1), (3, 1), (3, 0)])
def test_synth_roundtrip(endian, fmt, order):
    raw = synth_gim(endian=endian, fmt=fmt, order=order)
    g = Gim(raw)
    assert g.image.fmt == fmt and g.image.frames == 1
    im = g.to_pil()
    assert im.size == (20, 10)
    assert g.encode_from_pil(im) == raw  # 逐字节幂等


def test_synth_modify_pixels():
    raw = synth_gim(fmt=5, order=1)
    g = Gim(raw)
    im = g.to_pil()
    im.putpixel((3, 4), 7)
    im.putpixel((19, 9), 15)
    out = Gim(g.encode_from_pil(im))
    im2 = out.to_pil()
    assert im2.getpixel((3, 4)) == 7
    assert im2.getpixel((19, 9)) == 15
    assert im2.tobytes() == im.tobytes()
    assert im2.getpalette("RGBA") == im.getpalette("RGBA")


def test_synth_multiframe():
    raw = synth_gim(fmt=5, order=1, frames=3)
    g = Gim(raw)
    assert g.image.frames == 3
    f0, f1, f2 = (g.to_pil(frame=k) for k in range(3))
    assert f0.tobytes() != f1.tobytes() != f2.tobytes()
    # 回填只动帧 0：喂回帧 0 则整文件逐字节还原
    assert g.encode_from_pil(f0) == raw
    # 改帧 0 不影响其他帧
    im = f0.copy()
    im.putpixel((0, 0), 9)
    out = Gim(g.encode_from_pil(im))
    assert out.to_pil(frame=0).getpixel((0, 0)) == 9
    assert out.to_pil(frame=1).tobytes() == f1.tobytes()
    assert out.to_pil(frame=2).tobytes() == f2.tobytes()


def test_encode_rejects_bad_input():
    g = Gim(synth_gim(fmt=5))
    with pytest.raises(ValueError, match="尺寸"):
        g.encode_from_pil(Image.new("P", (3, 3)))
    with pytest.raises(ValueError, match="P 模式"):
        g.encode_from_pil(Image.new("RGBA", (20, 10)))
    big = Image.new("P", (20, 10))
    big.putpixel((0, 0), 255)
    g4 = Gim(synth_gim(fmt=4))
    with pytest.raises(ValueError, match="容量"):
        g4.encode_from_pil(big)


def test_parse_rejects_garbage():
    with pytest.raises(ValueError, match="magic"):
        Gim(b"not a gim at all....")


# ---------------------------------------------------------------- 真实资产抽查

SPECIALS = [
    "sysgim/prg_cursor_1.gim",   # 多帧（6 帧 index8）
    "sysgim/prg_cursor_3.gim",   # 多帧（8 帧 RGBA8888）
    "effect/eff_1_a.gim",        # 大端老版 GIM
    "effect/eff_1_b.gim",
    "effect/eff_3_a.gim",
    "bg/bg_10_a_0.gim",          # index8 swizzled 480x272
    "novel/novel01_1.gim",       # index4
    "sysgim/title_01_a.gim",
]


@needs_gims
def test_real_specials_match_png_and_identity():
    for rel in SPECIALS:
        raw = (GIMROOT / rel).read_bytes()
        g = Gim(raw)
        im = g.to_pil().convert("RGBA")
        ref = Image.open(PNGROOT / rel.replace(".gim", ".png")).convert("RGBA")
        assert im.tobytes() == ref.tobytes(), rel
        assert g.encode_from_pil(g.to_pil()) == raw, rel


@needs_gims
def test_real_multiframe_counts():
    assert Gim((GIMROOT / "sysgim/prg_cursor_1.gim").read_bytes()).image.frames == 6
    assert Gim((GIMROOT / "sysgim/prg_cursor_3.gim").read_bytes()).image.frames == 8
    assert Gim((GIMROOT / "bg/bg_10_a_0.gim").read_bytes()).image.frames == 1


@needs_gims
def test_real_big_endian_parses():
    g = Gim((GIMROOT / "effect/eff_1_a.gim").read_bytes())
    assert g.endian == ">"


@needs_gims
@pytest.mark.skipif(not os.environ.get("ZND_GIM_FULL"),
                    reason="全量 2153 张双向扫描较慢，需 ZND_GIM_FULL=1")
def test_real_full_sweep():
    n = 0
    for dp, _, fns in os.walk(GIMROOT):
        for fn in sorted(fns):
            if not fn.endswith(".gim"):
                continue
            p = Path(dp) / fn
            raw = p.read_bytes()
            g = Gim(raw)
            im = g.to_pil().convert("RGBA")
            rel = p.relative_to(GIMROOT)
            ref = Image.open(PNGROOT / str(rel).replace(".gim", ".png"))
            assert im.tobytes() == ref.convert("RGBA").tobytes(), rel
            assert g.encode_from_pil(g.to_pil()) == raw, rel
            n += 1
    assert n == 2153
