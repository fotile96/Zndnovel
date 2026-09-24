#!/usr/bin/env python3
"""Bake Chinese text into the voice-selection CG pair:

- ``eve_0_i``: "あなたの「声」を選択してください。" → instruction prompt
- ``eve_0_h``: "※音声設定はオプションからいつでも変更することができます。" → hint

Both are opaque CGs (not transparent overlays).

``eve_0_h`` uses the ``measure_glow``/``render_glow`` pipeline (the glow
converges within MAX_DIST).  ``eve_0_i``'s glow is too wide for that pipeline,
so it uses ``eve_0_g`` (the text-free version of the same CG composition) to
patch over the Japanese text, then renders Chinese text via GaussianBlur.

    uv run python tools/bake_event_voice.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_out import out_dir as _out_dir  # noqa: E402

REPO = Path(_REPO)
EVENT_DIR = REPO / "png" / "event"
OUT_DIR = _out_dir("event_zh")

# eve_0_h hint text: small, use same font as other event text
FONT_WENKAI = REPO / "third_party" / "LXGWWenKai-Regular.ttf"
# eve_0_i instruction text: original is sans-serif, use Source Han Sans
FONT_SHS = REPO / "third_party" / "SourceHanSansSC-VF.ttf"

# ---------------------------------------------------------------------------
# eve_0_h: hint text at bottom, glow model works
# Original: "※音声設定はオプションからいつでも変更することができます。"
# Box measured: (52, 238, 428, 256), bg=(112,87,58)
# ---------------------------------------------------------------------------
EVE_0_H_BOX = (52, 238, 428, 256)
EVE_0_H_ZH = "※语音设定可随时从选项中更改。"
EVE_0_H_SIZE = 11   # ink height ~12px → font size 11

# ---------------------------------------------------------------------------
# eve_0_i: instruction text centered, glow extends beyond MAX_DIST
# Original: "あなたの「声」を選択してください。"
# Text region: y=[127,145], x=[63,415], centered
# Rendering: white text with soft glow (brightening effect on sepia CG)
# Base: patch from eve_0_g (text-free version, max pixel diff 28)
# ---------------------------------------------------------------------------
EVE_0_I_ZH = "请选择你的「声音」。"
EVE_0_I_TEXT_Y = (127, 146)    # y range of original text
EVE_0_I_PATCH_Y = (120, 153)   # wider patch for seamless blending
EVE_0_I_SIZE = 20
EVE_0_I_GLOW_COLOR = (237, 130, 108)  # warm salmon/red — outer glow
EVE_0_I_CORE_COLOR = (255, 255, 255)  # white — stroke center


def _interpolate_bg(img, box, feather=0):
    """Reconstruct CG background under text by vertical interpolation.

    Uses rows just above and below `box` as anchors.  This avoids the
    flat-fill artifact that ``measure_glow.bg`` produces on gradient CGs.
    feather>0：框的左右各 feather 像素内把插值结果与原像素线性混合（越靠框边原像素越多），
    消掉竖向接缝；上下边靠真实锚行本就无缝。缺省 0＝原行为（eve_0_h 产物不变）。
    """
    bx0, by0, bx1, by1 = box
    w = img.size[0]
    out = img.copy()
    anchor_above = max(0, by0 - 4)
    anchor_below = min(img.size[1] - 1, by1 + 3)
    span = anchor_below - anchor_above
    if span <= 0:
        return out
    for y in range(by0, by1):
        t = (y - anchor_above) / span
        for x in range(bx0, bx1):
            pa = img.getpixel((x, anchor_above))
            pb = img.getpixel((x, anchor_below))
            interp = tuple(int(pa[c] * (1 - t) + pb[c] * t) for c in range(4))
            if feather > 0:
                d = min(x - bx0 + 1, bx1 - x)          # 距左/右框边的像素数（1 起）
                if d <= feather:
                    k = d / (feather + 1)              # 靠边→更多原像素
                    po = img.getpixel((x, y))
                    interp = tuple(int(po[c] * (1 - k) + interp[c] * k) for c in range(4))
            out.putpixel((x, y), interp)
    return out


def _toned_patch(img, src, box, feather=0, ring=12):
    """用无字底图 src 的逐通道线性映射（a·src+b）替换 box 内像素；a、b 按框外一圈 ring 像素最小二乘拟合。

    eve_0_h 是 eve_0_g 统一压暗的同一张 CG（≈0.556 倍，框外拟合残差均值 <1），所以这样重建的底图
    连背景的斜向光带都在，竖向插值（_interpolate_bg）则会把光带抹成一块平涂。feather 同 _interpolate_bg：
    框的左右各 feather 像素内与原像素线性混合。
    """
    bx0, by0, bx1, by1 = box
    w, h = img.size
    rx0, ry0, rx1, ry1 = max(0, bx0 - ring), max(0, by0 - ring), min(w, bx1 + ring), min(h, by1 + ring)
    fits = []
    for c in range(3):
        n = sx = sy = sxx = sxy = 0.0
        for y in range(ry0, ry1):
            for x in range(rx0, rx1):
                if bx0 <= x < bx1 and by0 <= y < by1:
                    continue
                a, b = src.getpixel((x, y))[c], img.getpixel((x, y))[c]
                n += 1
                sx += a
                sy += b
                sxx += a * a
                sxy += a * b
        k = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        fits.append((k, (sy - k * sx) / n))
    out = img.copy()
    for y in range(by0, by1):
        for x in range(bx0, bx1):
            ps = src.getpixel((x, y))
            po = img.getpixel((x, y))
            px = tuple(min(255, max(0, round(k * ps[c] + b))) for c, (k, b) in enumerate(fits)) + (po[3],)
            if feather > 0:
                d = min(x - bx0 + 1, bx1 - x)          # 距左/右框边的像素数（1 起）
                if d <= feather:
                    k = d / (feather + 1)              # 靠边→更多原像素
                    px = tuple(int(po[c] * (1 - k) + px[c] * k) for c in range(4))
            out.putpixel((x, y), px)
    return out


EVE_0_H_CORE_COLOR = (242, 239, 238)   # measured warm-white core
EVE_0_H_GLOW_BLUR = 2.0
EVE_0_H_GLOW_ALPHA = 0.50
EVE_0_H_CORE_BLUR = 0.3


def bake_eve_0_h(write, report, *, text=EVE_0_H_ZH, out_name="eve_0_h", out_dir=None, box=EVE_0_H_BOX, feather=0,
                 patch_src=None):
    """Bake eve_0_h: erase JP text by interpolation (or toned patch from patch_src), render zh via blur."""
    img = Image.open(EVENT_DIR / "eve_0_h.png").convert("RGBA")

    # Erase old text: interpolate CG gradient, or rebuild from a text-free source (eve_0_g) tone-mapped to eve_0_h
    if patch_src is None:
        out = _interpolate_bg(img, box, feather)
    else:
        out = _toned_patch(img, Image.open(patch_src).convert("RGBA"), box, feather)

    # Render Chinese text as transparent overlay (core + glow)
    font = ImageFont.truetype(str(FONT_WENKAI), EVE_0_H_SIZE)
    probe_d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = probe_d.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    pad = 20
    mask = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(mask).text((pad - l, pad - t), text,
                              font=font, fill=EVE_0_H_CORE_COLOR + (255,))

    glow = mask.filter(ImageFilter.GaussianBlur(radius=EVE_0_H_GLOW_BLUR))
    glow = _scale_alpha(glow, EVE_0_H_GLOW_ALPHA)
    core = mask.filter(ImageFilter.GaussianBlur(radius=EVE_0_H_CORE_BLUR))
    text_layer = Image.alpha_composite(glow, core)

    # Center in original text box
    bx0, by0, bx1, by1 = box
    bbox = text_layer.getbbox()
    if bbox:
        ink_cx = (bbox[0] + bbox[2]) / 2
        ink_cy = (bbox[1] + bbox[3]) / 2
        box_cx = (bx0 + bx1) / 2
        box_cy = (by0 + by1) / 2
        px = int(box_cx - ink_cx)
        py = int(box_cy - ink_cy)
        out.alpha_composite(text_layer, (px, py))

    out_path = (out_dir or OUT_DIR) / f"{out_name}.png"
    if write:
        out.save(str(out_path))
    bw = bbox[2] - bbox[0] if bbox else 0
    bh = bbox[3] - bbox[1] if bbox else 0
    report.append(f"  {out_name}: {'toned' if patch_src else 'interp'}+blur, {EVE_0_H_SIZE}px, ink {bw}x{bh}")
    return 0


def bake_eve_0_i(write, report, *, text=EVE_0_I_ZH, out_name="eve_0_i", out_dir=None):
    """Bake eve_0_i by patching from eve_0_g then rendering new text."""
    img_i = Image.open(EVENT_DIR / "eve_0_i.png").convert("RGBA")
    img_g = Image.open(EVENT_DIR / "eve_0_g.png").convert("RGBA")
    W, H = img_i.size

    out = img_i.copy()

    # Patch text region from eve_0_g (text-free version)
    py0, py1 = EVE_0_I_PATCH_Y
    # Blend edges for seamless transition (3px feather)
    FEATHER = 3
    for y in range(py0, py1):
        blend = 1.0
        if y < py0 + FEATHER:
            blend = (y - py0) / FEATHER
        elif y >= py1 - FEATHER:
            blend = (py1 - 1 - y) / FEATHER
        for x in range(W):
            pi = img_i.getpixel((x, y))
            pg = img_g.getpixel((x, y))
            merged = tuple(int(pi[c] * (1 - blend) + pg[c] * blend) for c in range(4))
            out.putpixel((x, y), merged)

    # Two-pass transparent overlay: soft glow halo + readable core, both salmon.
    # Composited onto CG so the glow lightens the surrounding background naturally.
    font = ImageFont.truetype(str(FONT_SHS), EVE_0_I_SIZE)
    try:
        font.set_variation_by_name("Regular")
    except Exception:
        pass

    probe_d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = probe_d.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t

    orig_cy = (EVE_0_I_TEXT_Y[0] + EVE_0_I_TEXT_Y[1]) / 2
    text_x = int(W / 2 - tw / 2 - l)
    text_y = int(orig_cy - (b + t) / 2)

    pad = 20
    glyph_w = tw + pad * 2
    glyph_h = th + pad * 2
    draw_x = pad - l
    draw_y = pad - t

    # Alpha mask from text rendering
    alpha_mask = Image.new("L", (glyph_w, glyph_h), 0)
    ImageDraw.Draw(alpha_mask).text((draw_x, draw_y), text, font=font,
                                    fill=255)

    # Glow: salmon/red, wide blur (alpha-only to avoid dark fringe)
    glow_alpha = alpha_mask.filter(ImageFilter.GaussianBlur(radius=3.5))
    glow = Image.new("RGBA", (glyph_w, glyph_h), EVE_0_I_GLOW_COLOR + (255,))
    glow.putalpha(glow_alpha)

    # Core: white, sharp (native AA only)
    core = Image.new("RGBA", (glyph_w, glyph_h), EVE_0_I_CORE_COLOR + (255,))
    core.putalpha(alpha_mask)

    # Composite glow + core
    text_layer = Image.alpha_composite(glow, core)

    # Paste onto CG
    paste_x = text_x + l - pad
    paste_y = text_y + t - pad
    out.alpha_composite(text_layer, (paste_x, paste_y))

    out_path = (out_dir or OUT_DIR) / f"{out_name}.png"
    if write:
        out.save(str(out_path))
    report.append(f"  {out_name}: direct draw, {EVE_0_I_SIZE}px, w={tw}")
    return 0


def _scale_alpha(img, factor):
    r, g, b, a = img.split()
    a = a.point(lambda p: min(255, int(p * factor)))
    return Image.merge("RGBA", (r, g, b, a))


def run(write=True):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    errors = 0
    errors += bake_eve_0_h(write, report)
    errors += bake_eve_0_i(write, report)
    print(f"event_voice: 2 CGs, {errors} errors")
    for line in report:
        print(line)
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(write=not a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
