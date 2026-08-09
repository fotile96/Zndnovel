#!/usr/bin/env python3
"""tools/bake_scene_size_ab.py -- one-off A/B comparison sheet for the scene/
caption font-size decision (build/scene_zh/_size_ab.png).

Context: tools/bake_scene.py shipped a 9px baseline (build/scene_layout_spec.md
section 6). The user reviewed it, asked for a slightly bigger font, was shown
a size-comparison sheet, and picked 10px to ship (see
.superpowers/sdd/2026-08-07-p4-polish-pass/bake-scene-report.md for the full
before/after writeup). This script renders BOTH versions in memory --
old (9px, TEXT_BOX=(5,0,140,15)) on top, new (10px, TEXT_BOX=(3,0,142,15))
below -- for a handful of representative cards, scaled up for a direct
side-by-side look. It does NOT touch git history or any checked-in PNG: the
"old" render is reproduced by calling the same bake_cell()/render_text_layer()
machinery with explicit old-parameter arguments, sourced from the real
png/scene/ sheets (which are untouched, read-only originals) -- not from any
previously-baked build/ output.

The OLD_* constants below are a frozen historical snapshot (the v1 baseline
that shipped before this decision), intentionally NOT read from
tools.bake_scene's current module-level FONT_SIZE/TEXT_BOX (those now hold
the v2/10px values -- see that module's docstring "v2 update" section).
"""
import os, sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.bake_scene import (
    CELL_H, CELL_W, CELLZOOM_CARDS, FONT_PATH, FONT_SIZE, OUT_DIR, TEXT_BOX,
    bake_cell, cell_box, sheet_path,
)
from tools.bake_plot import load_titles_zh

# Frozen v1 baseline -- NOT tools.bake_scene.FONT_SIZE/TEXT_BOX (those are
# v2/current). Deliberately hardcoded here so this script keeps working as a
# permanent "what did the old one look like" reference even after the module
# moves on to a v3/v4 size in the future.
OLD_FONT_SIZE = 9
OLD_TEXT_BOX = (5, 0, 140, 15)
OLD_BOX_OUTLINE = (0, 255, 255, 200)   # cyan, matches _cellzoom.png's convention
NEW_BOX_OUTLINE = (255, 0, 255, 200)   # magenta, so the two boxes are visually distinct

SCALE = 6
CARDS = CELLZOOM_CARDS  # same hand-picked set as _cellzoom.png (182/180/118/2/90 + ordinary ones)


def build_size_ab_image(titles, old_font, new_font, cards=CARDS, scale=SCALE):
    sheets_cache = {}

    def get_sheet(n):
        if n not in sheets_cache:
            sheets_cache[n] = Image.open(sheet_path(n)).convert("RGBA")
        return sheets_cache[n]

    cell_disp_w = CELL_W * scale
    cell_disp_h = CELL_H * scale
    label_h = 14
    gap = 10
    col_w = cell_disp_w + gap
    row_h = label_h + cell_disp_h * 2 + gap
    cols = 4
    rows = (len(cards) + cols - 1) // cols
    canvas_w = cols * col_w + gap
    canvas_h = rows * row_h + gap + 20  # +20 for a legend line at the bottom
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)

    for i, card in enumerate(cards):
        sheet_num, box = cell_box(card)
        cell = get_sheet(sheet_num).crop(box)
        old_cell = bake_cell(cell, titles[card], old_font, box=OLD_TEXT_BOX)
        new_cell = bake_cell(cell, titles[card], new_font, box=TEXT_BOX)

        col = i % cols
        row = i // cols
        x = gap + col * col_w
        y = gap + row * row_h

        d.text((x, y), f"#{card} {titles[card][:10]}  9px(top) / 10px(bottom)",
               fill=(255, 255, 0, 255))
        y2 = y + label_h

        old_disp = old_cell.resize((cell_disp_w, cell_disp_h), Image.NEAREST)
        new_disp = new_cell.resize((cell_disp_w, cell_disp_h), Image.NEAREST)
        canvas.paste(old_disp, (x, y2))
        canvas.paste(new_disp, (x, y2 + cell_disp_h))

        bx0 = x + OLD_TEXT_BOX[0] * scale
        bx1 = x + OLD_TEXT_BOX[2] * scale
        d.rectangle([bx0, y2, bx1, y2 + cell_disp_h - 1], outline=OLD_BOX_OUTLINE)

        nx0 = x + TEXT_BOX[0] * scale
        nx1 = x + TEXT_BOX[2] * scale
        by2 = y2 + cell_disp_h
        d.rectangle([nx0, by2, nx1, by2 + cell_disp_h - 1], outline=NEW_BOX_OUTLINE)

    legend_y = rows * row_h + gap
    d.text((gap, legend_y),
           f"cyan = old TEXT_BOX {OLD_TEXT_BOX} (9px)   "
           f"magenta = new TEXT_BOX {TEXT_BOX} ({FONT_SIZE}px)",
           fill=(200, 200, 200, 255))
    return canvas


def run(write=True):
    all_titles = load_titles_zh()
    old_font = ImageFont.truetype(FONT_PATH, OLD_FONT_SIZE)
    new_font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    img = build_size_ab_image(all_titles, old_font, new_font)
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        out_path = os.path.join(OUT_DIR, "_size_ab.png")
        img.save(out_path)
        return out_path
    return img


if __name__ == "__main__":
    path = run(write=True)
    print(f"wrote {path}")
