#!/usr/bin/env python3
"""tools/bake_scene_size_ab2.py -- A/B sheet for the v2 (10px, uniform) vs
v3 (11px cascade, per-cell fallback to 10px) font-size decision
(build/scene_zh/_size_ab2.png).

Context: v2 shipped a single uniform 10px (see
.superpowers/sdd/2026-08-07-p4-polish-pass/bake-scene-report.md section 10,
and tools/bake_scene_size_ab.py's 9px-vs-10px comparison). The user then
reviewed 10px and asked to try 11px, accepting that "the few titles that
would overflow can fall back to the 10px version" -- i.e. NOT a second
uniform size, but a per-cell cascade (see tools/bake_scene.py's "v3 update"
docstring section and FONT_SIZE_CASCADE = [11, 10, 9]). This script renders
BOTH versions in memory for the cards most relevant to judging that
decision: the 4 real cards that fall back under the v3 cascade (2, 90, 180,
182) plus their ACTUAL same-row neighbours in the real png/scene/ grid (1,
3, 88, 89, 178, 179, 181, 183) -- reusing tools.bake_scene.CELLZOOM_CARDS,
which the v3 update already curated for exactly this adjacency (see that
module's docstring and tests/test_bake_scene.py::
test_cellzoom_cards_include_fallback_cards_and_real_row_neighbors).

Top row per card: the OLD v2 rendering -- uniform 10px, frozen explicitly
as NEW_FONT_SIZE/NEW_TEXT_BOX in tools/bake_scene_size_ab.py's naming
scheme is reused here as OLD_FONT_SIZE/OLD_TEXT_BOX (this script's "old" is
that script's "new") -- NOT read from the live module (which has moved on
to the cascade), so this script keeps meaning "what did the 10px-uniform
version look like" even if the cascade's tiers change again later.

Bottom row per card: the NEW v3 rendering -- each card's ACTUAL resolved
cascade font size (11px normally, 10px for the 4 fallback cards),
computed by calling the SAME build_render_plan()/resolve_fonts_by_card()
machinery tools/bake_scene.py's run() uses -- not hand-simulated -- so a
fallback cell in this image is exactly what ships, not an approximation.
Cards that fell back are tagged "[FALLBACK]" in the per-card label so the
mismatch is legible in the image itself, not just inferable from which
card number it is.

Neither row touches git history or any checked-in PNG: both are rendered
in memory from the read-only png/scene/ originals -- no git stash/checkout/
restore, and no dependency on any previously-baked build/ output.
"""
import os, sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.ui_font import truetype as _ui_truetype
from tools.bake_scene import (
    CELL_H, CELL_W, CELLZOOM_CARDS, FONT_PATH, FONT_SIZE_CASCADE, OUT_DIR,
    TEXT_BOX, bake_cell, build_render_plan, cell_box, load_fonts,
    resolve_fonts_by_card, sheet_path,
)
from tools.bake_plot import load_titles_zh

# Frozen v2 baseline: uniform 10px. TEXT_BOX is unchanged between v2 and v3
# (see tools/bake_scene.py's "v3 update" docstring -- the redraw/coverage
# rectangle is derived from the background template's geometry, not from
# font size), so OLD_TEXT_BOX and the live module's TEXT_BOX are the same
# value; still named separately here so this script does not implicitly
# depend on that invariant holding forever.
OLD_FONT_SIZE = 10
OLD_TEXT_BOX = (3, 0, 142, 15)
OLD_BOX_OUTLINE = (0, 255, 255, 200)     # cyan
NEW_BOX_OUTLINE = (255, 0, 255, 200)     # magenta

SCALE = 6
CARDS = CELLZOOM_CARDS  # the 4 fallback cards + their real same-row neighbours
COLS = 3                 # matches CELLZOOM_CARDS' 3-per-real-row grouping


def build_size_ab2_image(titles, old_font, fonts_by_card, plans, cards=CARDS,
                          scale=SCALE, cols=COLS):
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
    rows = (len(cards) + cols - 1) // cols
    canvas_w = cols * col_w + gap
    canvas_h = rows * row_h + gap + 24  # +24 for a legend line at the bottom
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)

    for i, card in enumerate(cards):
        sheet_num, box = cell_box(card)
        cell = get_sheet(sheet_num).crop(box)
        old_cell = bake_cell(cell, titles[card], old_font, box=OLD_TEXT_BOX)
        new_size = plans[card]["font_size"]
        new_cell = bake_cell(cell, titles[card], fonts_by_card[card], box=TEXT_BOX)

        col = i % cols
        row = i // cols
        x = gap + col * col_w
        y = gap + row * row_h

        fb_tag = "" if new_size == FONT_SIZE_CASCADE[0] else " [FALLBACK]"
        d.text((x, y),
               f"#{card} {titles[card][:10]}  {OLD_FONT_SIZE}px(top)/"
               f"{new_size}px(bottom){fb_tag}",
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
           f"cyan = TEXT_BOX {OLD_TEXT_BOX} ({OLD_FONT_SIZE}px, v2 uniform)   "
           f"magenta = TEXT_BOX {TEXT_BOX} (v3 cascade {FONT_SIZE_CASCADE}, "
           f"[FALLBACK] = card stepped down below {FONT_SIZE_CASCADE[0]}px)",
           fill=(200, 200, 200, 255))
    return canvas


def run(write=True):
    all_titles = load_titles_zh()
    titles = {c: all_titles[c] for c in range(1, 196)}
    old_font = _ui_truetype("scene", OLD_FONT_SIZE)

    fonts_by_size = load_fonts()
    plans, _fallbacks, hard_failures = build_render_plan(titles, fonts_by_size)
    if hard_failures:
        raise RuntimeError(
            f"font-size cascade exhausted for {len(hard_failures)} title(s) "
            f"-- refusing to render an A/B sheet off a truncated result: "
            f"{hard_failures}")
    fonts_by_card = resolve_fonts_by_card(plans, fonts_by_size)

    img = build_size_ab2_image(titles, old_font, fonts_by_card, plans)
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        out_path = os.path.join(OUT_DIR, "_size_ab2.png")
        img.save(out_path)
        return out_path
    return img


if __name__ == "__main__":
    path = run(write=True)
    print(f"wrote {path}")
