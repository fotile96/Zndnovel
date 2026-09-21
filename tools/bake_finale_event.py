#!/usr/bin/env python3
"""谢幕章文化祭 CG 变体 eve_74_z——用户改图降采样到 event 模板尺寸（480×272）并预量化 256 色。

来龙去脉：fin-40『文化祭』里那位「谁都没见过、却谁都不觉得面生」的客人，2026-09-21 用户
定为 DeepSeek 拟人化的鲸少女（代表全部 AI 朋友），并提供高清源图
docs/finale/assets/eve_74_z.src.png（1665×944 RGB，原 eve_74_x 的变体创作：直哉转身与
抱着一摞册子的客人攀谈，其余人物与构图不变）。演出上先白入原图 eve_74_x，客人到场时
同层交叉溶解到本图（docs/finale/draft-finale-v3.md）。e2f_340 仍用原图。

做法：
1. 中心裁到 480:272 的精确纵横比（源图只差万分之五，裁 1 px 量级），LANCZOS 降采样；
2. **在烤图阶段就量化到 256 色**（event 模板 eve_74_x 是 index8/256 色）：分别试
   MEDIANCUT / MAXCOVERAGE / FASTOCTREE，按感知 MSE 取最优。这样 build_disc 的
   quantize_for_template 见到 ≤256 色的图走无损精确调色板路径，量化器由本工具选定而不是
   交给缺省，产物像素在这里就定稿、可目检；
3. 产物：docs/finale/assets/eve_74_z.png（入库成品）＋ build/finale_event/eve_74_z.png
   （进包件；layers/manifest.toml [gim].new 以 event/eve_74_x.gim 为模板编成新成员
   event/eve_74_z.gim）＋ QA 图 _ab_2x.png（原 eve_74_x / 降采样 / 量化后 三联，2 倍）。
不触碰 png/event/ 原件。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.bake_out import out_dir  # noqa: E402

FACE = "finale_event"
NAME = "eve_74_z"
SRC = REPO / "docs" / "finale" / "assets" / f"{NAME}.src.png"
OUT_SRC = REPO / "docs" / "finale" / "assets" / f"{NAME}.png"
TEMPLATE_PNG = REPO / "png" / "event" / "eve_74_x.png"      # 模板尺寸与对照图
W, H = 480, 272
COLORS = 256                                                # event 模板 index8 色板容量
METHODS = ("MEDIANCUT", "MAXCOVERAGE", "FASTOCTREE")


def crop_to_aspect(im: Image.Image, size: tuple[int, int] = (W, H)) -> Image.Image:
    """中心裁剪到目标纵横比（只裁不缩），偏差在 1 px 内时原样返回。"""
    w, h = im.size
    tw, th = size
    target = tw / th
    if w / h > target:            # 太宽：裁宽
        nw = round(h * target)
        if abs(nw - w) <= 1:
            return im
        left = (w - nw) // 2
        return im.crop((left, 0, left + nw, h))
    nh = round(w / target)        # 太高：裁高
    if abs(nh - h) <= 1:
        return im
    top = (h - nh) // 2
    return im.crop((0, top, w, top + nh))


def downsample(im: Image.Image, size: tuple[int, int] = (W, H)) -> Image.Image:
    """裁到纵横比 → LANCZOS 缩到模板尺寸（RGB，不透明 CG 无 alpha 顾虑）。"""
    return crop_to_aspect(im.convert("RGB"), size).resize(size, Image.LANCZOS)


def _mse_rgb(a: Image.Image, b: Image.Image) -> float:
    from tools.emu.imgdiff import mse
    return mse(a.convert("RGB"), b.convert("RGB"))


def quantize_best(im: Image.Image, colors: int = COLORS) -> tuple[Image.Image, str, float]:
    """按感知 MSE 从几种量化器里挑最优；返回 (P 图, 方法名, MSE)。

    不抖动：赛璐璐风 CG 的平涂面在抖动下会起噪点，且抖动会抬高 MSE 却未必更好看；
    渐变处的色阶由 QA 图目检。
    """
    im = im.convert("RGB")
    best = None
    for name in METHODS:
        q = im.quantize(colors=colors, method=getattr(Image.Quantize, name), dither=Image.Dither.NONE)
        err = _mse_rgb(q, im)
        if best is None or err < best[2]:
            best = (q, name, err)
    return best


def to_rgba_palette(q: Image.Image) -> Image.Image:
    """P 图的调色板补成 RGBA（alpha 255），与 quantize_for_template 的精确路径同型。"""
    pal = q.getpalette()[: 3 * COLORS]
    n = len(pal) // 3
    rgba = []
    for i in range(n):
        rgba.extend((pal[3 * i], pal[3 * i + 1], pal[3 * i + 2], 255))
    out = q.copy()                      # 像素索引原样复制，只换调色板
    out.info.pop("transparency", None)
    out.putpalette(rgba, rawmode="RGBA")
    return out


def compose_ab(orig: Image.Image, mid: Image.Image, final: Image.Image, scale: int = 2) -> Image.Image:
    """三联对照：原 eve_74_x / 降采样 / 量化后，各放大 scale 倍竖排。"""
    gap = 8
    canvas = Image.new("RGB", (W * scale, (H * scale + gap) * 3 - gap), (60, 60, 60))
    for i, im in enumerate((orig, mid, final)):
        canvas.paste(im.convert("RGB").resize((W * scale, H * scale), Image.NEAREST), (0, i * (H * scale + gap)))
    return canvas


def main() -> None:
    tpl = Image.open(TEMPLATE_PNG)
    assert tpl.size == (W, H), f"eve_74_x 模板尺寸变了：{tpl.size}"
    src = Image.open(SRC)
    mid = downsample(src)
    q, method, err = quantize_best(mid)
    final = to_rgba_palette(q)
    assert len(final.convert("RGBA").getcolors(COLORS) or []) <= COLORS

    OUT_SRC.parent.mkdir(parents=True, exist_ok=True)
    final.save(OUT_SRC)
    dbg = out_dir(FACE)
    dbg.mkdir(parents=True, exist_ok=True)
    final.save(dbg / f"{NAME}.png")
    compose_ab(tpl, mid, final).save(dbg / "_ab_2x.png")
    print(f"源 {src.size[0]}x{src.size[1]} → 裁 {crop_to_aspect(src).size} → {W}x{H}；"
          f"量化 {COLORS} 色：{method} MSE={err:.2f}")
    print(f"final -> {OUT_SRC} ＋ {dbg}/{NAME}.png（QA: _ab_2x.png）")


if __name__ == "__main__":
    main()
