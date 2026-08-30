"""Bake Chinese text onto cutin/tut_* tutorial overlay images.

These are palette-indexed PNG overlays composited at runtime on game screenshots.
The text sits on semi-transparent black panels with per-row alpha gradients.
Approach: convert to RGBA, erase old text by filling with local background,
render new Chinese text with warm orange glow, save as RGBA PNG.

    uv run python tools/bake_cutin_tut.py [--check]
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ui_font import truetype

SRC_DIR = Path("png/cutin")
DATA = Path("data/cutin_tut_text.jsonl")
OUT_DIR = Path("build/cutin_tut_zh")
FONT_FACE = "CARD"

# Warm orange glow ramp (from measurement of original tut_2_a text).
# Core is warm cream (not pure white), fading through salmon → orange → black.
GLOW_RAMP = [
    (0, (250, 235, 210, 255)),   # warm cream core
    (1, (230, 180, 130, 254)),   # salmon
    (2, (210, 130, 60, 252)),    # deep salmon
    (3, (180, 80, 10, 250)),     # orange
    (4, (140, 56, 0, 245)),      # dark orange
    (5, (100, 40, 1, 242)),
    (6, (66, 26, 0, 238)),
    (7, (40, 15, 0, 234)),
    (8, (20, 8, 0, 230)),
    (9, (9, 3, 0, 226)),
]


def _layout(text_lines, font, box_w, box_h, align, pad_left, pad_top):
    """Draw origins that place the **real ink** where we want it.

    `draw.text()` origins are ascender-left, so a glyph's ink sits at an
    offset given by `getbbox()`. Centring the origin instead of the ink is
    the same mistake as `anchor="mm"` (decision L11): it centres the font's
    design metrics, which drift per face and per string. Subtract the
    bearing so the *ink* lands centred.
    """
    line_height = font.size + 4
    boxes = [font.getbbox(ln) for ln in text_lines]

    # vertical: centre the whole block's ink span
    tops = [i * line_height + bb[1] for i, bb in enumerate(boxes)]
    bots = [i * line_height + bb[3] for i, bb in enumerate(boxes)]
    ink_top, ink_bot = min(tops), max(bots)
    if pad_top is not None:
        y_start = pad_top - ink_top
    else:
        y_start = (box_h - (ink_bot - ink_top)) // 2 - ink_top

    origins = []
    for i, (ln, bb) in enumerate(zip(text_lines, boxes)):
        if align == "center":
            x = (box_w - (bb[2] - bb[0])) // 2 - bb[0]
        else:
            x = pad_left - bb[0]
        origins.append((x, y_start + i * line_height))
    return origins


def _render_glow_text(text_lines, font, box_w, box_h, align="center",
                      pad_left=16, pad_top=None):
    """Render multi-line text with warm orange glow on transparent canvas."""
    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    origins = _layout(text_lines, font, box_w, box_h, align, pad_left, pad_top)

    for layer_d in range(len(GLOW_RAMP) - 1, -1, -1):
        d, (cr, cg, cb, ca) = GLOW_RAMP[layer_d]
        layer = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        for (x, y), line in zip(origins, text_lines):
            draw.text((x, y), line, font=font, fill=(cr, cg, cb, ca))

        if d > 0:
            layer = layer.filter(ImageFilter.GaussianBlur(radius=d * 0.7))

        canvas = Image.alpha_composite(canvas, layer)

    return canvas


def _find_bg_alpha_by_row(img, box):
    """Per-row background alpha = modal alpha among that row's dark pixels.

    Robust to where the old text sits: it reads the panel, not a hand-picked
    column. A single `sample_x` was the earlier approach and it was fragile —
    any column can be crossed by a glyph stroke.
    """
    px = img.load()
    x0, y0, x1, y1 = box
    result = {}
    for y in range(y0, y1):
        counts = {}
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            if r < 20 and g < 20 and b < 20:
                counts[a] = counts.get(a, 0) + 1
        result[y] = max(counts, key=counts.get) if counts else None
    # rows that were entirely covered by ink inherit from a neighbour
    known = [y for y in range(y0, y1) if result[y] is not None]
    for y in range(y0, y1):
        if result[y] is None:
            result[y] = result[min(known, key=lambda k: abs(k - y))] if known else 230
    return result


def _erase_box(img, box):
    """Fill a box with black at per-row background alpha."""
    bg_alpha = _find_bg_alpha_by_row(img, box)
    px = img.load()
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        a = bg_alpha[y]
        for x in range(x0, x1):
            px[x, y] = (0, 0, 0, a)


def _paste_glow(img, glow, x0, y0):
    """Composite glow onto image at given offset."""
    sub = img.crop((x0, y0, x0 + glow.width, y0 + glow.height))
    merged = Image.alpha_composite(sub, glow)
    img.paste(merged, (x0, y0))


# ──────────────────────────── tut_2 ────────────────────────────
# All five share the same rounded-rect text box.
# Border: top y=37-38, bottom y=131-132, left x=130, right x=465.
# Interior: (132, 39) to (464, 130).
# Original text: left-aligned, ~16px left padding from border, core ~17px tall.

TUT2_INTERIOR = (132, 39, 464, 130)


def process_tut_2(name, zh_text, font_size=18):
    img = Image.open(SRC_DIR / f"{name}.png").convert("RGBA")
    x0, y0, x1, y1 = TUT2_INTERIOR

    _erase_box(img, TUT2_INTERIOR)

    font = truetype(FONT_FACE, font_size)
    lines = zh_text.split("\n")
    bw, bh = x1 - x0, y1 - y0
    glow = _render_glow_text(lines, font, bw, bh, align="left", pad_left=16)
    _paste_glow(img, glow, x0, y0)

    return img


# ──────────────────────────── tut_1_a ────────────────────────────
# Text box with orange border. Border: top y=96-97, bottom y=145-146.
# Interior: (98, 99) to (266, 144). Text centered.

TUT1_INTERIOR = (98, 99, 266, 144)


def process_tut_1_a(zh_text, font_size=14):
    img = Image.open(SRC_DIR / "tut_1_a.png").convert("RGBA")
    x0, y0, x1, y1 = TUT1_INTERIOR

    _erase_box(img, TUT1_INTERIOR)

    font = truetype(FONT_FACE, font_size)
    lines = zh_text.split("\n")
    bw, bh = x1 - x0, y1 - y0
    glow = _render_glow_text(lines, font, bw, bh, align="center")
    _paste_glow(img, glow, x0, y0)

    return img


# ──────────────────────────── tut_4_b ────────────────────────────
# Complex layout with multiple text blocks. Precise positions from
# row-by-row pixel scan of the original image.
#
# The layout is NESTED: a pink container wraps the three scene-title boxes,
# and each title has its own orange frame inside it. The explanation lines
# have olive frames (142,140,113) of their own — missing that was the bug
# behind two rounds of "the box is still clipped".
#
# Frames traced by "row/col is >60% frame-coloured" (see git history of this
# file for the probe). Interiors below are exclusive-end and exact.
#
#   "information" title:  y=8-22   — KEEP, not translated
#   row0 subtitle  frame: rows 30,31 / 53,54   cols 111,112 / 398,399  (orange)
#   pink container frame: rows 60,61 / ...     cols 80,81             (pink)
#   row1 title1    frame: rows 64,65 / 87,88   cols 85,86  / 152,153   (orange)
#   row2 title2    frame: rows 64,65 / 86,87   cols 163,164/ 281,282   (orange)
#   row3 title3    frame: rows 64,65 / 86,87   cols 291,292/ 420,421   (orange)
#   row4 expl      frame: rows 93,94 / 116,117 cols 214,215/ 456,457   (olive)
#   arrow + rules:        y=115-127            — KEEP
#   row5 lowertitle frame:rows 131,132/154,155 cols 85,86  / 152,153   (orange)
#   row6 expl      frame: rows 131,132/154,155 cols 214,215/ 456,457   (olive)

# Scene titles are anchored on the original ink height (decision Y7): the
# original is 17px of ink, and Source Han Sans at size N gives roughly N px of
# kanji ink, so 18 lands there (ink 18, 「上学路」 54px wide — the original
# 「通学路」 is 54 too). The subtitle (row0) and the two explanation lines
# (rows 4/6) keep the sizes the user signed off on; only their centring moved.
TUT4B_BLOCKS = {
    0: {"box": (113, 32, 398, 53), "font_size": 13, "align": "center"},
    1: {"box": (87, 66, 152, 87), "font_size": 18, "align": "center"},
    2: {"box": (165, 66, 281, 86), "font_size": 18, "align": "center"},
    3: {"box": (293, 66, 420, 86), "font_size": 18, "align": "center"},
    4: {"box": (216, 95, 456, 116), "font_size": 11, "align": "left",
        "pad_left": 4},
    5: {"box": (87, 133, 152, 154), "font_size": 18, "align": "center"},
    6: {"box": (216, 133, 456, 154), "font_size": 11, "align": "left",
        "pad_left": 4},
}


def process_tut_4_b(entries):
    img = Image.open(SRC_DIR / "tut_4_b.png").convert("RGBA")

    for entry in entries:
        row = entry["row"]
        if row not in TUT4B_BLOCKS:
            continue
        blk = TUT4B_BLOCKS[row]
        x0, y0, x1, y1 = blk["box"]

        _erase_box(img, blk["box"])

        font = truetype(FONT_FACE, blk["font_size"])
        glow = _render_glow_text(
            entry["zh"].split("\n"), font, x1 - x0, y1 - y0,
            align=blk.get("align", "center"),
            pad_left=blk.get("pad_left", 8),
        )
        _paste_glow(img, glow, x0, y0)

    return img


# ──────────────────────────── main ────────────────────────────

def run(check=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA) as f:
        entries = [json.loads(line) for line in f]

    by_file = {}
    for e in entries:
        by_file.setdefault(e["file"], []).append(e)

    for name, file_entries in sorted(by_file.items()):
        zh = file_entries[0]["zh"]

        if name == "tut_1_a":
            img = process_tut_1_a(zh)
        elif name.startswith("tut_2_"):
            img = process_tut_2(name, zh)
        elif name == "tut_4_b":
            img = process_tut_4_b(file_entries)
        else:
            print(f"  skip {name}: no handler")
            continue

        out_path = OUT_DIR / f"{name}.png"
        if not check:
            img.save(out_path)
        print(f"  {name} → {out_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    run(check=args.check)
