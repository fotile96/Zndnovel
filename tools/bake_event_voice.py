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


def _interpolate_bg(img, box):
    """Reconstruct CG background under text by vertical interpolation.

    Uses rows just above and below `box` as anchors.  This avoids the
    flat-fill artifact that ``measure_glow.bg`` produces on gradient CGs.
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
            out.putpixel((x, y), tuple(int(pa[c] * (1 - t) + pb[c] * t) for c in range(4)))
    return out


EVE_0_H_CORE_COLOR = (242, 239, 238)   # measured warm-white core
EVE_0_H_GLOW_BLUR = 2.0
EVE_0_H_GLOW_ALPHA = 0.50
EVE_0_H_CORE_BLUR = 0.3


def bake_eve_0_h(write, report):
    """Bake eve_0_h: erase JP text by interpolation, render zh via blur."""
    img = Image.open(EVENT_DIR / "eve_0_h.png").convert("RGBA")

    # Erase old text by interpolating CG gradient
    out = _interpolate_bg(img, EVE_0_H_BOX)

    # Render Chinese text as transparent overlay (core + glow)
    font = ImageFont.truetype(str(FONT_WENKAI), EVE_0_H_SIZE)
    probe_d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = probe_d.textbbox((0, 0), EVE_0_H_ZH, font=font)
    tw, th = r - l, b - t
    pad = 20
    mask = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(mask).text((pad - l, pad - t), EVE_0_H_ZH,
                              font=font, fill=EVE_0_H_CORE_COLOR + (255,))

    glow = mask.filter(ImageFilter.GaussianBlur(radius=EVE_0_H_GLOW_BLUR))
    glow = _scale_alpha(glow, EVE_0_H_GLOW_ALPHA)
    core = mask.filter(ImageFilter.GaussianBlur(radius=EVE_0_H_CORE_BLUR))
    text_layer = Image.alpha_composite(glow, core)

    # Center in original text box
    bx0, by0, bx1, by1 = EVE_0_H_BOX
    bbox = text_layer.getbbox()
    if bbox:
        ink_cx = (bbox[0] + bbox[2]) / 2
        ink_cy = (bbox[1] + bbox[3]) / 2
        box_cx = (bx0 + bx1) / 2
        box_cy = (by0 + by1) / 2
        px = int(box_cx - ink_cx)
        py = int(box_cy - ink_cy)
        out.alpha_composite(text_layer, (px, py))

    out_path = OUT_DIR / "eve_0_h.png"
    if write:
        out.save(str(out_path))
    bw = bbox[2] - bbox[0] if bbox else 0
    bh = bbox[3] - bbox[1] if bbox else 0
    report.append(f"  eve_0_h: interp+blur, {EVE_0_H_SIZE}px, ink {bw}x{bh}")
    return 0


def bake_eve_0_i(write, report):
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
    l, t, r, b = probe_d.textbbox((0, 0), EVE_0_I_ZH, font=font)
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
    ImageDraw.Draw(alpha_mask).text((draw_x, draw_y), EVE_0_I_ZH, font=font,
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

    out_path = OUT_DIR / "eve_0_i.png"
    if write:
        out.save(str(out_path))
    report.append(f"  eve_0_i: direct draw, {EVE_0_I_SIZE}px, w={tw}")
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
