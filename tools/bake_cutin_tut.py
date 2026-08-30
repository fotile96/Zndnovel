"""Bake Chinese text onto cutin/tut_* tutorial overlay images.

These are palette-indexed PNG overlays composited at runtime on game screenshots.
The text sits on semi-transparent black panels with per-row alpha gradients.
Approach: convert to RGBA, erase old text by filling with local background,
render new Chinese text with warm orange glow, save as RGBA PNG.

    uv run python tools/bake_cutin_tut.py [--check]
"""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from ui_font import truetype

SRC_DIR = Path("png/cutin")
DATA = Path("data/cutin_tut_text.jsonl")
OUT_DIR = Path("build/cutin_tut_zh")
FONT_FACE = "CARD"

# ── glow ramps: colour as a function of distance from the glyph core ──
#
# Measured, not invented. For each block the original's ink core was taken as
# the pixels at >=80% of peak luminance, an exact Euclidean distance field was
# built from it, and the median RGBA recorded per distance bin.
#
# Two things the first (guessed) ramp got wrong, both visible:
#   * The scene titles in tut_4_b are RED (d=1 is 187,47,43 — G≈B), not the
#     orange the other blocks use. They were being rendered orange.
#   * Real glow dies by d≈5-6. The guessed ramp ran to d=9 and was applied as
#     a stack of Gaussian blurs, which spread it much wider and washed the
#     colour out. The falloff is also far steeper than a Gaussian: the very
#     first ring already drops from ~250 to ~180.
#
# Entry = (R, G, B, dA) at that integer distance; the last entry is the dead
# end of the glow. dA is the alpha *above the local panel background*, so the
# same ramp is safe on rows whose background alpha differs (these panels are
# a vertical gradient). Final alpha = row background + dA.
GLOW_RAMPS = {
    # tut_2_* body text, 18px
    "orange_lg": [(250, 239, 225, 18), (200, 90, 24, 14), (127, 50, 0, 9),
                  (93, 37, 0, 7), (46, 18, 0, 4), (21, 8, 0, 3), (0, 0, 0, 0)],
    # tut_1_a body, 14px
    "orange_md": [(247, 235, 223, 29), (176, 85, 27, 20), (113, 45, 0, 12),
                  (67, 27, 0, 6), (30, 11, 0, 3), (11, 4, 0, 1), (0, 0, 0, 0)],
    # tut_4_b subtitle and explanation lines, 11-13px
    "orange_sm": [(240, 219, 208, 18), (158, 78, 27, 11), (81, 32, 0, 4),
                  (40, 15, 0, 2), (12, 4, 0, 0), (0, 0, 0, 0)],
    # tut_4_b scene titles — a different hue entirely
    "red": [(249, 235, 231, 22), (187, 47, 43, 15), (82, 0, 0, 8),
            (45, 0, 0, 5), (10, 0, 0, 3), (0, 0, 0, 0)],
}


def _layout(text_lines, font, box_w, box_h, align, pad_left, pad_top,
            line_pitch=None):
    """Draw origins that place the **real ink** where we want it.

    `draw.text()` origins are ascender-left, so a glyph's ink sits at an
    offset given by `getbbox()`. Centring the origin instead of the ink is
    the same mistake as `anchor="mm"` (decision L11): it centres the font's
    design metrics, which drift per face and per string. Subtract the
    bearing so the *ink* lands centred.
    """
    line_height = line_pitch or font.size + 4
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


def _offsets(radius):
    """Disc offsets sorted by exact Euclidean distance."""
    out = []
    r = int(math.ceil(radius))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = math.hypot(dx, dy)
            if d <= radius:
                out.append((dx, dy, d))
    return out


def _ramp_at(ramp, d):
    """Linear interpolation into a ramp at fractional distance."""
    i = int(d)
    if i >= len(ramp) - 1:
        return ramp[-1]
    f = d - i
    a, b = ramp[i], ramp[i + 1]
    return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(4))


def _draw_glow(img, box, text_lines, font, ramp, align="center",
               pad_left=16, pad_top=None, line_pitch=None):
    """Paint text into `box` colouring each pixel by its distance to the ink.

    The glow is not a blur: it is the measured ring profile in `ramp`, applied
    over an exact Euclidean distance field. `box` must already be erased to the
    panel background — the row background alpha is read back from it so the
    ramp's dA can sit on top of the panel's own vertical gradient.

    Nothing outside `box` is written, so the surrounding frames stay untouched.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    radius = len(ramp) - 1

    # glyph mask, padded so glyphs near the edge still get a correct field
    pad = radius + 2
    mask_img = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    md = ImageDraw.Draw(mask_img)
    for (ox, oy), line in zip(
            _layout(text_lines, font, w, h, align, pad_left, pad_top,
                    line_pitch),
            text_lines):
        md.text((ox + pad, oy + pad), line, font=font, fill=255)
    mask = mask_img.load()
    mw, mh = mask_img.size

    # distance field, splatted from the solid core outwards
    INF = float("inf")
    dist = [[INF] * mw for _ in range(mh)]
    offs = _offsets(radius)
    for my in range(mh):
        for mx in range(mw):
            if mask[mx, my] >= 128:
                for dx, dy, d in offs:
                    nx, ny = mx + dx, my + dy
                    if 0 <= nx < mw and 0 <= ny < mh and d < dist[ny][nx]:
                        dist[ny][nx] = d

    px = img.load()
    for y in range(y0, y1):
        # panel background alpha for this row (box is already erased to it)
        bg_a = px[x0, y][3]
        for x in range(x0, x1):
            mx, my = x - x0 + pad, y - y0 + pad
            m = mask[mx, my]
            if m >= 128:
                d = 0.0
            else:
                d = dist[my][mx]
                if d is INF or d > radius:
                    continue
                # anti-aliased edge: partial coverage pulls toward the core
                d = max(0.0, d - m / 255.0)
            r, g, b, da = _ramp_at(ramp, d)
            px[x, y] = (r, g, b, min(255, bg_a + da))


def _find_bg_alpha_by_row(img, box, margin=None):
    """Per-row panel alpha = modal alpha of dark pixels in the box's margins.

    Two earlier versions of this were wrong in instructive ways:

    * A single hand-picked `sample_x` — fragile, any column can be crossed by
      a glyph stroke.
    * The mode over the *whole* row — which assumes the only thing inside the
      box is panel plus text. It is not: tut_1_a's box also holds a dark
      rectangle (alpha ~175 against the panel's ~229). On text rows that
      rectangle outnumbers the visible panel, so the mode returned the
      rectangle, and because it won on some rows and lost on others the fill
      alternated between the two populations — visible as horizontal banding.

    The margins are the one part of the box that is reliably panel: every
    block here has horizontal padding between the frame and the text.
    """
    px = img.load()
    x0, y0, x1, y1 = box
    if margin is None:
        margin = max(3, min(8, (x1 - x0) // 8))
    cols = (list(range(x0, min(x0 + margin, x1)))
            + list(range(max(x0, x1 - margin), x1)))

    result = {}
    for y in range(y0, y1):
        counts = {}
        for x in cols:
            r, g, b, a = px[x, y]
            if r < 20 and g < 20 and b < 20:
                counts[a] = counts.get(a, 0) + 1
        if not counts:  # margins fully covered by ink — fall back to the row
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


# ──────────────────────────── tut_2 ────────────────────────────
# All five share the same rounded-rect text box.
# Border: top y=37-38, bottom y=131-132, left x=130, right x=465.
# Interior: (132, 39) to (464, 130).
# Original text: left-aligned, core starts 15px in and 9px down from the
# interior origin, line pitch 19 (all five sheets measured identical). It is
# TOP-aligned, not centred — centring put tut_2_a 26px too low.

TUT2_INTERIOR = (132, 39, 464, 130)


def process_tut_2(name, zh_text, font_size=18):
    img = Image.open(SRC_DIR / f"{name}.png").convert("RGBA")
    _erase_box(img, TUT2_INTERIOR)
    _draw_glow(img, TUT2_INTERIOR, zh_text.split("\n"),
               truetype(FONT_FACE, font_size), GLOW_RAMPS["orange_lg"],
               align="left", pad_left=15, pad_top=9, line_pitch=19)
    return img


# ──────────────────────────── tut_1_a ────────────────────────────
# Text box with orange border. Border: top y=96-97, bottom y=145-146.
# Interior: (98, 99) to (266, 144). Text centered.

TUT1_INTERIOR = (98, 99, 266, 144)


def process_tut_1_a(zh_text, font_size=14):
    img = Image.open(SRC_DIR / "tut_1_a.png").convert("RGBA")
    _erase_box(img, TUT1_INTERIOR)
    _draw_glow(img, TUT1_INTERIOR, zh_text.split("\n"),
               truetype(FONT_FACE, font_size), GLOW_RAMPS["orange_md"],
               align="center", pad_top=5, line_pitch=20)
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
    0: {"box": (113, 32, 398, 53), "font_size": 13, "ramp": "orange_sm", "align": "center"},
    1: {"box": (87, 66, 152, 87), "font_size": 18, "ramp": "red", "align": "center"},
    2: {"box": (165, 66, 281, 86), "font_size": 18, "ramp": "red", "align": "center"},
    3: {"box": (293, 66, 420, 86), "font_size": 18, "ramp": "red", "align": "center"},
    4: {"box": (216, 95, 456, 116), "font_size": 11, "ramp": "orange_sm", "align": "left",
        "pad_left": 4},
    5: {"box": (87, 133, 152, 154), "font_size": 18, "ramp": "red", "align": "center"},
    6: {"box": (216, 133, 456, 154), "font_size": 11, "ramp": "orange_sm", "align": "left",
        "pad_left": 4},
}


def process_tut_4_b(entries):
    img = Image.open(SRC_DIR / "tut_4_b.png").convert("RGBA")

    for entry in entries:
        row = entry["row"]
        if row not in TUT4B_BLOCKS:
            continue
        blk = TUT4B_BLOCKS[row]
        _erase_box(img, blk["box"])
        _draw_glow(
            img, blk["box"], entry["zh"].split("\n"),
            truetype(FONT_FACE, blk["font_size"]), GLOW_RAMPS[blk["ramp"]],
            align=blk.get("align", "center"),
            pad_left=blk.get("pad_left", 8),
        )

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
