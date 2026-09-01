#!/usr/bin/env python3
"""Bake Chinese captions into the 4 voice-mode selection buttons
(``png/select/sel_voice{1,2}_sel_a_{on,off}.png``).

These buttons appear exactly once, in ``snr_s0_10_f.lua:143`` (prologue),
letting the player choose whether 直哉 thinks or speaks "忘れないよ"
(toggles ``systemSave.voiceNaoya``).

They are completely different from the 134 standard 250×26 select buttons
handled by ``bake_select.py``:

- 480×82 canvas, fully transparent background (no border frame, no fill)
- ``_off`` (unselected): one soft-glow title line, max alpha ≈152
- ``_on`` (selected): bright title (white core + red glow) + smaller subtitle

The glow model in ``bake_sysgim_glow`` does not work here — it requires
convergence to a flat background within ``MAX_DIST`` pixels, but transparent
backgrounds taper indefinitely.  Instead this module uses PIL GaussianBlur
to approximate the soft-glow effect, measured against the originals.

Source data: ``data/select_voice_zh.jsonl`` (2 logical buttons × 2 variants).

    uv run python tools/bake_select_voice.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_out import out_dir as _out_dir  # noqa: E402

REPO = Path(_REPO)
SELECT_DIR = REPO / "png" / "select"
DATA = REPO / "data" / "select_voice_zh.jsonl"
OUT_DIR = _out_dir("select_voice_zh")

CANVAS_W, CANVAS_H = 480, 82

# select 面的其余 134 个按钮用思源黑体，但这 4 张 voice 按钮原图是有衬线的字体，
# 用霞鹜文楷风格更接近。直接指向随仓库分发的 BUNDLED 字体，不走 ui_font 的面配置。
FONT_PATH = REPO / "third_party" / "LXGWWenKai-Regular.ttf"

# ---------------------------------------------------------------------------
# Measured rendering parameters from originals:
#
# _off:
#   Single title block, y=[4,33] (h=30), cx≈239, max alpha=152
#   Primary ink color: rgb(204,51,0)
#   Soft/blurry — no fully opaque pixels
#
# _on title:
#   Block y=[4,33] (h=30), cx≈239, max alpha=255
#   Core: white/near-white (alpha>200 = 485px out of 5406)
#   Glow: rgb(255,0,0) at medium alpha (50–150)
#
# _on subtitle:
#   Block y=[38,56] (h=19), cx≈239
#   Primary ink: rgb(102,51,51)
#
# Title size ≈ 18–20px (ink h=30 includes glow bleed)
# Subtitle size ≈ 12–13px (ink h=19 includes glow bleed)
# ---------------------------------------------------------------------------

TITLE_SIZE = 20
SUB_SIZE = 13

# Text origin y-coordinates.  The text origin is the (0,0) point passed to
# ImageDraw.text(); the visible ink starts a few pixels below (font-dependent).
# These values are set so the visible ink top lands at y≈5 (title) and y≈39
# (subtitle), matching the original Japanese images.
TITLE_ORIGIN_Y = 3     # → ink top ≈ y=5 (original: y=4–5)
SUB_ORIGIN_Y = 37      # → ink top ≈ y=39 (original: y=38–39)

# All three text styles share the same structure measured from originals:
#   white/near-white core (highest alpha) + colored glow (lower alpha).
#
# _off title: core=white@152 + glow=rgb(204,51,0)  (capped alpha, fainter)
# _on title:  core=white@255 + glow=rgb(255,0,0)   (full alpha, bright)
# _on subtitle: core=warm-white@255 + glow=rgb(102,51,51)

CORE_COLOR = (255, 255, 255)

OFF_GLOW_COLOR = (204, 51, 0)
OFF_GLOW_BLUR = 2.0
OFF_GLOW_ALPHA_SCALE = 0.65
OFF_CORE_BLUR = 0.3
OFF_ALPHA_SCALE = 0.60      # cap max alpha ≈ 152/255

ON_GLOW_COLOR = (255, 0, 0)
ON_GLOW_BLUR = 4.0
ON_GLOW_ALPHA_SCALE = 0.75
ON_CORE_BLUR = 0.3

ON_SUB_GLOW_COLOR = (102, 51, 51)
ON_SUB_GLOW_BLUR = 2.0
ON_SUB_GLOW_ALPHA_SCALE = 0.65
ON_SUB_CORE_BLUR = 0.3


def _render_text(text, size, pad=30):
    """Render text on an oversized transparent canvas. Returns (image, offset).

    `offset` is (ox, oy) — the top-left of the text origin within the canvas,
    so callers can position the rendered result correctly.
    """
    font = ImageFont.truetype(str(FONT_PATH), size)
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    cw, ch = tw + pad * 2, th + pad * 2
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.text((pad - l, pad - t), text, font=font, fill=(255, 255, 255, 255))
    return canvas, (pad - l, pad - t), font


def _tint(mask, color):
    """Apply a solid RGB color to an RGBA image, keeping its alpha channel."""
    r_ch, g_ch, b_ch, a_ch = mask.split()
    solid = Image.new("RGBA", mask.size, color + (255,))
    solid.putalpha(a_ch)
    return solid


def _scale_alpha(img, factor):
    """Multiply all alpha values by a factor (0..1)."""
    r, g, b, a = img.split()
    a = a.point(lambda p: min(255, int(p * factor)))
    return Image.merge("RGBA", (r, g, b, a))


def _render_glow_text(text, size, glow_color, glow_blur, glow_alpha_scale,
                      core_blur, pad=40, alpha_scale=1.0):
    """White-core + colored-glow rendering shared by all three text styles.

    Returns (image, text_origin) where text_origin is (ox, oy) — the position
    of the text drawing origin within the image, used for alignment.
    """
    mask, origin, font = _render_text(text, size, pad=pad)

    glow_layer = _tint(mask, glow_color)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_blur))
    glow_layer = _scale_alpha(glow_layer, glow_alpha_scale)

    core_layer = _tint(mask, CORE_COLOR)
    core_layer = core_layer.filter(ImageFilter.GaussianBlur(radius=core_blur))

    result = Image.alpha_composite(glow_layer, core_layer)
    if alpha_scale < 1.0:
        result = _scale_alpha(result, alpha_scale)
    return result, origin


def _render_off_title(text):
    """Render _off title: white core + orange glow, capped alpha."""
    return _render_glow_text(text, TITLE_SIZE,
                             OFF_GLOW_COLOR, OFF_GLOW_BLUR, OFF_GLOW_ALPHA_SCALE,
                             OFF_CORE_BLUR, alpha_scale=OFF_ALPHA_SCALE)


def _render_on_title(text):
    """Render _on title: white core + red glow, full alpha."""
    return _render_glow_text(text, TITLE_SIZE,
                             ON_GLOW_COLOR, ON_GLOW_BLUR, ON_GLOW_ALPHA_SCALE,
                             ON_CORE_BLUR, pad=50)


def _render_on_subtitle(text):
    """Render _on subtitle: white core + dark-red glow."""
    return _render_glow_text(text, SUB_SIZE,
                             ON_SUB_GLOW_COLOR, ON_SUB_GLOW_BLUR,
                             ON_SUB_GLOW_ALPHA_SCALE, ON_SUB_CORE_BLUR,
                             pad=25)


def _paste_anchored(canvas, glyph, text_origin, target_cx, target_origin_y):
    """Paste glyph so the text origin lands at (target_cx, target_origin_y).

    `text_origin` is (ox, oy) within glyph — the point where ImageDraw.text()
    drew (0,0) of the text.  This is invariant across glow radii, so _on and
    _off variants align perfectly even though their glow extents differ.
    """
    ox, oy = text_origin
    # Measure text ink width for horizontal centering
    probe = glyph.crop((0, 0, glyph.size[0], glyph.size[1]))
    bbox = probe.getbbox()
    if not bbox:
        return
    ink_cx = (bbox[0] + bbox[2]) / 2
    x = int(target_cx - ink_cx)
    y = int(target_origin_y - oy)
    # Clip source region to fit canvas
    src_x0 = max(0, -x)
    src_y0 = max(0, -y)
    src_x1 = min(glyph.size[0], canvas.size[0] - x)
    src_y1 = min(glyph.size[1], canvas.size[1] - y)
    if src_x1 <= src_x0 or src_y1 <= src_y0:
        return
    cropped = glyph.crop((src_x0, src_y0, src_x1, src_y1))
    canvas.alpha_composite(cropped, (max(0, x) , max(0, y)))


def bake_one(title_zh, sub_zh, variant, report, button_name):
    """Bake one button variant. Returns the baked RGBA image."""
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    cx = CANVAS_W / 2

    if variant == "off":
        title_img, title_origin = _render_off_title(title_zh)
        _paste_anchored(canvas, title_img, title_origin, cx, TITLE_ORIGIN_Y)
        report.append(f"  {button_name}_off: title {title_img.size[0]}x{title_img.size[1]}")
    else:
        title_img, title_origin = _render_on_title(title_zh)
        _paste_anchored(canvas, title_img, title_origin, cx, TITLE_ORIGIN_Y)

        sub_img, sub_origin = _render_on_subtitle(sub_zh)
        _paste_anchored(canvas, sub_img, sub_origin, cx, SUB_ORIGIN_Y)

        report.append(f"  {button_name}_on: title {title_img.size[0]}x{title_img.size[1]}"
                      f" + sub {sub_img.size[0]}x{sub_img.size[1]}")

    return canvas


def load_data():
    """Load button definitions from select_voice_zh.jsonl."""
    rows = []
    for line in DATA.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run(write=True):
    """Bake all 4 voice selection button images. Returns error count."""
    rows = load_data()
    if not rows:
        print("ERROR: no data in select_voice_zh.jsonl")
        return 1

    report = []
    errors = 0

    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    for row in rows:
        button = row["button"]
        title_zh = row["title_zh"]
        sub_zh = row["sub_zh"]

        for variant in ("off", "on"):
            try:
                baked = bake_one(title_zh, sub_zh, variant, report, button)
            except Exception as e:
                report.append(f"  ERROR {button}_{variant}: {e}")
                errors += 1
                continue

            out_path = OUT_DIR / f"{button}_{variant}.png"
            if write:
                baked.save(str(out_path))
                report.append(f"  → {out_path.name}")

    print(f"select_voice: {len(rows)} buttons × 2 variants = "
          f"{len(rows) * 2} images, {errors} errors")
    for line in report:
        print(line)

    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(write=not a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
