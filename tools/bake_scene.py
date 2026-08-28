#!/usr/bin/env python3
"""Bake Chinese card-title captions into png/scene/scene_{1,2}_a.png (the
"scene name" corner-banner strip: a small single-line "current card title"
tag shown at (330,5) during Story mode playback -- see comSectionStoryStart
-- and reused as the Fragment mode "cardLabel1" via comSectionCardStart, both
in lua_scripts/snr_common.lua).

## Domain: identical to png/plot/, NOT the "scene_title" pipeline dataset

The grid-fill algorithm (lua_scripts/snr_common.lua:955-984, `sceneState`)
is structurally the same recipe as `plotState` (see build/plot_layout_spec.md
and tools/bake_plot.py): row-major, 3 cols/page here (vs 6 for plot), new
sheet every 102 cards (vs 60), for cards 1..195 -- SAME 195-card domain as
plotTitle[1..195] / skeleton/cards.zh.yaml, not the separate "kind=scene_title"
454-row dataset that another pipeline derived from literal `scene_X(id,
"title")` call-site strings scattered across all 229 lua_scripts/*.lua files.

That 454-row dataset is real and used at runtime, but for a DIFFERENT purpose:
comSectionStoryBegin(p0, p1) (snr_common.lua:2373) stores p1 (the scene()
call's title string) into gameSave.sceneName and passes it to
savedataTitle(p1, ...) -- the save-file-list UI text, rendered live by the
engine's own font, never baked into any PNG. It is NOT consumed by
sceneState at all: comSectionStoryStart(p0, p1, p2) (snr_common.lua:2012)
resolves the STRIP CELL exclusively via `sceneState[sceneId2aCard[p0]]`
(scene id -> CARD NUMBER via sceneId2aCard, never via p1/gameSave.sceneName),
and comSectionCardStart's fragment-mode bake-lookup (~snr_common.lua:2489)
uses `sceneState[p1]` where p1 is already a bare card number (used in the
same call alongside `plotTitle[p1]` for the savedataTitle line right above
it). Confirmed empirically too: 23 spot-checked cells spanning the entire
1..195 range (including cells the OTHER dataset's jp-string fuzzy-matcher
failed to associate with any card -- e.g. cards 74/95/96/97/109/114/130/133/
140/145) all show baked text pixel-identical to plotTitle[N], 23/23, zero
mismatches. See .superpowers/sdd/2026-08-07-p4-polish-pass/bake-scene-report.md
section 2 for the full evidence chain and the 454/393/204/195 reconciliation.

So this module reuses tools.bake_plot.load_titles_zh() -- the exact same
skeleton/cards.zh.yaml source bake_plot.py already uses -- rather than reading
any "scene_title"-kind derivation file.

## Layout: measured, not guessed (see build/scene_layout_spec.md)

- Two real sheets, 435x510, P mode w/ tRNS (same palette shape as plot/).
  Grid: 145x15 cells, 3 cols x 34 rows = 102 cells/sheet, 204 total capacity,
  195 used (cards 1..195), 9 blank tail cells on sheet 2 (alpha=0, confirmed
  identical -- see the blank-tail test).
- Background is NOT photographic like plot/'s cells -- it's a flat template:
  solid RGB (0,0,0) throughout every cell's interior, with only ALPHA
  varying (~153 flat "bar", dipping toward 0 in four small corner notches
  confined to columns x<5 and x>=140 -- confirmed byte-identical between
  cards 1, 2, and 150 outside that region, across BOTH sheets). This means
  (unlike bake_plot's ink-detection-sized hard/soft band, needed there to
  avoid over-covering unique per-cell artwork) the safe redraw box can be a
  FIXED rectangle for every cell: there is no artwork to lose by covering
  more of it, because "more of it" is the exact same flat bar.
- TEXT_BOX = (5, 0, 140, 15): full cell height, 5px margin left/right.
  Evidence: real JP ink measured across all 195 real cells never starts
  before x=5 or ends past x=139, and the corner notches never reach x>=5 --
  so this box (a) never touches the decorative notches and (b) fully
  contains 195/195 real captions with zero exceptions (see
  collect_ink_outliers / the spec doc's measurement table).
- FONT_SIZE=9 (original v1 baseline): LXGWWenKai renders at exactly N px
  advance/char and N px glyph-cell height at size N (verified directly), and
  the real JP captions' measured per-char advance is ~9px (145px-wide cells;
  e.g. card180's 15-char title spans exactly 135px -> 9.0px/char) -- a
  visual-weight match, same method bake_plot used to pick its own font size.

## v2 update: FONT_SIZE 9->10, TEXT_BOX margin 5->3px (user-requested enlarge)

After reviewing the v1 (9px) output side by side with a size comparison
sheet, the user asked for a slightly bigger font for readability and picked
**10px** as the size to ship. At 10px with the original 5px margin
(TEXT_BOX width 135px), 2/195 real captions overflow (card182 needs ~138px,
card180 needs ~136px) -- so the margin was tightened from 5px to 3px
(TEXT_BOX width 139px) *together with* the font bump, which brings real
overflow back to 0/195 (re-verified by collect_overflow() on every run, not
assumed -- see .superpowers/sdd/2026-08-07-p4-polish-pass/bake-scene-report.md
for the measured table this is based on). Font-size and margin are changed
together; changing only one would leave 2 titles clipped.

This margin change also changes the pixel-preservation gate's coverage
rectangle (find_outside_box_diffs/bake_cell both key off TEXT_BOX): the 2px
strip on each side (x=3-4 and x=140-141) that used to sit *outside* TEXT_BOX
(v1: (5,0,140,15), fully protected/untouched) is now *inside* TEXT_BOX (v2:
(3,0,142,15)) and gets unconditionally overwritten by the flat band fill.
Per build/scene_layout_spec.md section 4, that 2px strip falls within the
corner notch decoration's column range (x in [0,4] union [140,144]) -- so
those two edge columns' alpha-gradient notch pixels (at the notch's active
rows, roughly y in {1..4} union {10..13}) are now part of the redraw area
and are no longer preservation-gate-protected. This is the one real safety-
surface change from the margin edit; see the report for the exact measured
delta.

## v3 update: FONT_SIZE (single value) -> FONT_SIZE_CASCADE (per-cell ladder)

After shipping v2 (10px), the user reviewed it and asked to try 11px, with
"the few titles that would overflow falling back to the 10px version" --
i.e. per-cell (not global) font size, biggest-first, only stepping down as
far as each individual title actually needs. Real measurement at 11px with
the *unchanged* TEXT_BOX=(3,0,142,15) (139px usable width -- the box is
independent of font size, see below): 4/195 titles overflow (cards 2, 90,
180, 182); at 10px all 195 fit (re-confirmed every run, not assumed -- see
the report's "measured fallback list").

**The cascade is a list, not a hardcoded two-step**: FONT_SIZE_CASCADE =
[11, 10, 9] below. build_render_plan() walks it largest-to-smallest per
card and stops at the first size whose single-line wrap doesn't need to
drop any characters. Today no real title needs the 9px tier (10px already
fits all 4 overflow cases) -- but the machinery doesn't assume that; a
title that still doesn't fit even at the *smallest* configured tier is a
**hard failure**: build_render_plan() reports it in `hard_failures`, and
run() raises rather than baking a silently-truncated line (see
"zero truncation" in the module's safety-gate list below). Nothing about
the ladder length or its specific sizes is hardcoded into the stepping
logic itself -- add a 4th tier by editing this one list.

**TEXT_BOX does NOT depend on font size.** The redraw/coverage rectangle
was, and remains, the fixed (3,0,142,15) from v2 -- it was picked from the
*background template's* geometry (the flat band + corner notches, see v2
section above), not from any font metric. Changing which font size gets
used for a given cell changes what gets drawn *inside* that same box; it
never changes the box itself, so the pixel-preservation gate's coverage
rectangle is unaffected by this update (verified: TEXT_BOX is untouched by
this diff, and find_outside_box_diffs/bake_cell still key off the same
module-level constant).

**Every fallback must be visible, not just correct.** A per-cell cascade
that silently drops font size is itself a form of "silent regression" (see
CLAUDE.md's "静默回落是恒绿的一种" principle) -- looking at "195/195 baked
OK" would hide that a handful of cells quietly shipped at a smaller size
than the rest. So every card that lands on anything other than
FONT_SIZE_CASCADE[0] is surfaced in three places: the CLI printout, the
`manifest.json` (`"fallbacks"` list, each entry naming the card, the size
it landed on, and which larger sizes it overflowed at first), and run()'s
returned report dict (same structure, in-memory).
"""
import argparse, json, os, sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.bake_plot import load_titles_zh
from tools.zh_wrap import wrap as _zh_wrap
from tools.ui_font import resolve as _resolve_font
from tools.bake_out import out_dir as _out_dir
from tools.ui_font import truetype as _ui_truetype
from tools.ui_font import size_cascade as _size_cascade

SCENE_DIR = os.path.join(REPO, "png", "scene")
#: 字体按面可换：`ZND_UI_FONT_SCENE` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷
#: Regular。面名＝scene。详见 tools/ui_font.py——那里也记着
#: 「换字体后金标夹具会红，这是对的」。
FONT_PATH = str(_resolve_font("scene"))
OUT_DIR = str(_out_dir("scene_zh"))

# ---------------------------------------------------------------------------
# Grid geometry -- measured + confirmed against lua_scripts/snr_common.lua's
# `sceneState` construction loop (:955-984) and pixel evidence. See
# build/scene_layout_spec.md section 1-2 for the full writeup.
# ---------------------------------------------------------------------------
SHEET_W, SHEET_H = 435, 510
CELL_W, CELL_H = 145, 15
GRID_COLS, GRID_ROWS = 3, 34          # 435/145=3, 510/15=34
CARDS_PER_SHEET = GRID_COLS * GRID_ROWS  # 102
NUM_SHEETS = 2
NUM_CARDS = 195

# ---------------------------------------------------------------------------
# Text layout -- see build/scene_layout_spec.md section 4 for the measured
# evidence behind every value here.
# ---------------------------------------------------------------------------
# v3: FONT_SIZE (single global value) -> FONT_SIZE_CASCADE (per-cell ladder,
# biggest-first, see module docstring "v3 update"). TEXT_BOX is UNCHANGED
# from v2 and does NOT vary by font size -- it is derived from the
# background template's fixed geometry (flat band + corner notches), not
# from any font metric. This is a genuine invariant, not an oversight: see
# the report section on "保全闸的矩形与字号无关".
#: 从大到小逐档试，只降到该格真正需要的那一档为止。默认 [11,10,9] 对着霞鹜文楷
#: 实测选定（S4：用户看过 9/10/11 三版对照后取 11 打底）。换字体可用
#: `ZND_UI_SIZE_CASCADE_SCENE=…` 覆盖——档位随字体而变，见 tools/ui_font.py。
FONT_SIZE_CASCADE = _size_cascade("scene", [11, 10, 9])
TEXT_BOX = (3, 0, 142, 15)   # (x0, y0, x1, y1); redraw + coverage rectangle
MAX_TEXT_W = TEXT_BOX[2] - TEXT_BOX[0]   # 139
MAX_LINES = 1                # cell height (15px) structurally forces one line
                              # -- the original never uses 2 lines for any of
                              # the 195 real captions (measured y-extent is
                              # always a single ~8px-tall line), and there is
                              # no room for a second 9px-pitch line inside a
                              # 15px-tall cell without touching the corner
                              # chrome. See spec section 4.
FILL_COLOR = (255, 255, 255, 255)
STROKE_COLOR = (0, 0, 0, 255)
STROKE_WIDTH = 1
ELLIPSIS = "…"

# Flat background fill for the redraw box. Measured: across all 195 cells,
# sampling every TEXT_BOX pixel NOT within 1px of that cell's own detected
# ink bbox, 98.9% are exactly (0,0,0,153); the remaining 1.1% are a handful
# of antialiasing-transition pixels at rows y=1/13, columns x=5-7/137-139
# (the corner notch's blend ramp bleeding 1px into the box) -- since our box
# unconditionally overwrites its whole interior, those transition pixels are
# legitimately part of what we replace, not something we owe preservation to.
# See build/scene_layout_spec.md section 3.
BAND_COLOR = (0, 0, 0)
BAND_ALPHA = 153


def cell_position(card):
    """card (1..195) -> (sheet 1..2, row 0..33, col 0..2).

    Mirrors lua_scripts/snr_common.lua:955-984 (`sceneState` construction)
    exactly: row-major within a sheet (col 0->2 then wrap), new sheet every
    102 cards. Structurally the same recipe as tools.bake_plot.cell_position,
    with GRID_COLS=3 and CARDS_PER_SHEET=102 in place of plot's 6/60.
    """
    if not (1 <= card <= NUM_CARDS):
        raise ValueError(f"card out of range 1..{NUM_CARDS}: {card}")
    idx0 = card - 1
    sheet = idx0 // CARDS_PER_SHEET + 1
    within = idx0 % CARDS_PER_SHEET
    row = within // GRID_COLS
    col = within % GRID_COLS
    return sheet, row, col


def cell_box(card):
    """card -> (sheet, (x0,y0,x1,y1)) pixel rect within that sheet's image."""
    sheet, row, col = cell_position(card)
    x0, y0 = col * CELL_W, row * CELL_H
    return sheet, (x0, y0, x0 + CELL_W, y0 + CELL_H)


def sheet_path(sheet_num):
    return os.path.join(SCENE_DIR, f"scene_{sheet_num}_a.png")


# ---------------------------------------------------------------------------
# Ink detection -- used only as a defensive sanity check (does every real JP
# caption actually fit inside TEXT_BOX, as measured during layout analysis?),
# NOT to size the coverage band (which is fixed -- see module docstring for
# why a fixed box is correct here, unlike bake_plot's dynamic one).
#
# Unlike bake_plot's joint bright+dark-neighbor criterion (needed there
# because plot/'s cells are photographic and bright sky/pool/uniform content
# would otherwise false-positive as ink), a simple brightness threshold is
# sufficient and safe here: scene/'s cell backgrounds are measured to be
# ALWAYS RGB (0,0,0) (only alpha varies -- see BAND_ALPHA above), so nothing
# in the background can ever be bright. There is no photographic content
# that could be mistaken for ink.
# ---------------------------------------------------------------------------
INK_BRIGHT_THRESH = 200
INK_MIN_ALPHA = 200
INK_MIN_ROW_PIXELS = 1   # rows are short (15px) and captions can be as thin
                          # as a single kanji ("春", card 118) -- unlike
                          # plot's photographic cells, there's no bright-photo
                          # false-positive risk here to guard against with a
                          # higher threshold (see module-level note above).


def ink_bbox_of_cell(cell, bright_thresh=INK_BRIGHT_THRESH,
                      min_alpha=INK_MIN_ALPHA, min_row_px=INK_MIN_ROW_PIXELS):
    """Return (x0,y0,x1,y1) inclusive bbox of near-white ink pixels in
    `cell`, or None if no row met the density threshold anywhere."""
    rgba = cell.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    xs, ys = [], []
    for y in range(h):
        row_hits = []
        for x in range(w):
            r, g, b, a = px[x, y]
            if min(r, g, b) >= bright_thresh and a >= min_alpha:
                row_hits.append(x)
        if len(row_hits) >= min_row_px:
            xs.extend(row_hits)
            ys.extend([y] * len(row_hits))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def collect_ink_outliers(box=TEXT_BOX):
    """Scan every real cell (1..195) in png/scene/ and return
    [(card, reason, bbox_or_None), ...] for any cell whose detected ink does
    NOT fit inside `box` (or has no detectable ink at all). MUST be called
    and its result surfaced -- never discarded -- exactly the same
    never-silent principle as bake_plot's collect_ink_fallbacks. Measured
    empirically to be [] for the real png/scene/ data (see the report), but
    this function re-verifies it every run rather than hard-coding "0"."""
    out = []
    sheets = {n: Image.open(sheet_path(n)).convert("RGBA") for n in range(1, NUM_SHEETS + 1)}
    for card in range(1, NUM_CARDS + 1):
        sheet_num, cbox = cell_box(card)
        cell = sheets[sheet_num].crop(cbox)
        bbox = ink_bbox_of_cell(cell)
        if bbox is None:
            out.append((card, "no_ink_detected", None))
            continue
        x0, y0, x1, y1 = bbox
        if x0 < box[0] or x1 >= box[2] or y0 < box[1] or y1 >= box[3]:
            out.append((card, "ink_exceeds_text_box", bbox))
    return out


# ---------------------------------------------------------------------------
# Wrap / overflow (defensive -- measured to be 0/195 today, see the report,
# but must be recomputed and surfaced every run, never assumed).
# ---------------------------------------------------------------------------

def _measurer_for(font):
    probe = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(probe)
    return lambda s: d.textlength(s, font=font)


def collect_overflow(titles, font, max_width=MAX_TEXT_W, max_lines=MAX_LINES):
    """titles: {card: text}. Returns sorted [(card, text, lines, dropped), ...]
    for every title whose wrap() call had to fall back to the truncate step.
    MUST be surfaced -- never discarded. See tools/zh_wrap.py's retreat-chain
    docstring for what "truncated" means precisely."""
    measurer = _measurer_for(font)
    out = []
    for card in sorted(titles):
        lines, info = _zh_wrap(titles[card], max_width, max_lines=max_lines, measurer=measurer)
        if info["truncated"]:
            out.append((card, titles[card], lines, info["dropped"]))
    return out


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------

def render_text_layer(text, font, size=(CELL_W, CELL_H), box=TEXT_BOX):
    """A cell-sized RGBA layer, transparent except where glyphs were drawn,
    centered (both axes) in `box` -- matches the original's measured
    center-aligned layout (see spec section 4: a single kanji like card 118's
    "春" sits dead-centered in the cell, and the longest real captions span
    the box near-symmetrically)."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    d.text((cx, cy), text, font=font, fill=FILL_COLOR, anchor="mm",
           stroke_width=STROKE_WIDTH, stroke_fill=STROKE_COLOR)
    return layer


def bake_cell(cell, text, font, box=TEXT_BOX):
    """cell: CELL_W x CELL_H RGBA image (one card's title strip cell).
    Returns new_cell: `box` is fully overwritten (a hard, non-blended
    rectangle fill to BAND_COLOR+BAND_ALPHA -- direct pixel replacement, not
    alpha-composited over the original ink, precisely so the original JP
    glyphs (opaque white fill / opaque black stroke) cannot ghost through a
    translucent composite -- see module docstring's "why direct-set, not
    blend" reasoning) with the new zh caption drawn on top; every pixel
    outside `box` is byte-identical to `cell`."""
    new_cell = cell.convert("RGBA").copy()
    d = ImageDraw.Draw(new_cell)
    # -1 on the far edges: ImageDraw.rectangle's second point is inclusive.
    d.rectangle([box[0], box[1], box[2] - 1, box[3] - 1],
                fill=(BAND_COLOR[0], BAND_COLOR[1], BAND_COLOR[2], BAND_ALPHA))
    text_layer = render_text_layer(text, font, size=cell.size, box=box)
    new_cell = Image.alpha_composite(new_cell, text_layer)
    return new_cell


def find_outside_box_diffs(orig_cell, new_cell, box):
    """Return [(x,y), ...] pixels OUTSIDE `box` where orig_cell != new_cell.
    Empty == the non-covered-region-preserved invariant holds. This is the
    pixel-preservation safety gate; it must actually be called (and asserted
    empty) by the baking pipeline, not just exist unused."""
    x0, y0, x1, y1 = box
    w, h = orig_cell.size
    opx = orig_cell.load()
    npx = new_cell.load()
    diffs = []
    for y in range(h):
        for x in range(w):
            if x0 <= x < x1 and y0 <= y < y1:
                continue
            if opx[x, y] != npx[x, y]:
                diffs.append((x, y))
    return diffs


def bake_sheet(sheet_num, titles, fonts_by_card):
    """fonts_by_card: {card: ImageFont} -- the per-cell cascade result (see
    build_render_plan/resolve_fonts_by_card below); each card can use a
    different font object, which is the whole point of the v3 cascade.
    Return (new_sheet_image, per_cell_diffs). per_cell_diffs maps
    card -> list of outside-box pixel diffs (must be [] for every card)."""
    sheet = Image.open(sheet_path(sheet_num)).convert("RGBA")
    new_sheet = sheet.copy()
    diffs = {}
    lo = (sheet_num - 1) * CARDS_PER_SHEET + 1
    hi = min(sheet_num * CARDS_PER_SHEET, NUM_CARDS)
    for card in range(lo, hi + 1):
        _, box = cell_box(card)
        cell = sheet.crop(box)
        new_cell = bake_cell(cell, titles[card], fonts_by_card[card])
        d = find_outside_box_diffs(cell, new_cell, TEXT_BOX)
        diffs[card] = d
        new_sheet.paste(new_cell, box)
    return new_sheet, diffs


# ---------------------------------------------------------------------------
# Per-cell font-size cascade (v3). See module docstring "v3 update" for the
# rationale. This is the mechanism that must never silently downgrade a
# card's font size without it showing up in fallbacks/hard_failures below --
# both are surfaced by run() into the CLI printout, manifest.json, and the
# returned report dict (see CLAUDE.md's "静默回落是恒绿的一种" principle).
# ---------------------------------------------------------------------------

def load_fonts(cascade=FONT_SIZE_CASCADE):
    """{size: ImageFont} for every size in `cascade`, loaded once up front
    so build_render_plan doesn't reopen the font file per card per tier."""
    return {size: _ui_truetype("scene", size) for size in cascade}


def build_render_plan(titles, fonts_by_size, cascade=FONT_SIZE_CASCADE,
                       max_width=MAX_TEXT_W, max_lines=MAX_LINES):
    """titles: {card: text}. fonts_by_size: {size: ImageFont}, must cover
    every size named in `cascade`.

    For each card, walks `cascade` largest-to-smallest and stops at the
    first size whose single-line tools.zh_wrap.wrap() call does NOT need to
    drop any characters (info["truncated"] is False) -- i.e. the biggest
    size that still fits this specific title inside `max_width`. Nothing
    about the stepping loop assumes a particular cascade length or that a
    card falls at most one tier -- a card may walk past several tiers
    before landing (see tests/test_bake_scene.py's synthetic
    3-tier-fallback regression), and the ladder itself is just the
    module-level FONT_SIZE_CASCADE list, editable independently of this
    function.

    Returns (plans, fallbacks, hard_failures):
      plans: {card: {"font_size": int, "lines": [str], "info": dict}} --
        one entry per card that found *some* fitting tier.
      fallbacks: sorted [(card, chosen_size, [sizes_that_overflowed_first])]
        -- non-empty only for cards NOT rendered at cascade[0]; this is the
        list that MUST be surfaced (CLI/manifest/report), never silently
        dropped.
      hard_failures: sorted [(card, text, smallest_size, info_at_smallest)]
        -- non-empty only for a card that still needs to drop characters
        even at the SMALLEST configured tier (cascade[-1]). The caller
        (run()) must treat this as fatal and refuse to bake -- never fall
        back to baking a truncated line. Today this is always [] for the
        real 195 titles (10px already absorbs all 4 real overflow cases,
        so the 9px tier is never actually exercised by real data), but the
        check runs fresh every call rather than being assumed.
    """
    plans = {}
    fallbacks = []
    hard_failures = []
    for card in sorted(titles):
        text = titles[card]
        info = None
        chosen = None
        overflowed_at = []
        for size in cascade:
            font = fonts_by_size[size]
            measurer = _measurer_for(font)
            lines, info = _zh_wrap(text, max_width, max_lines=max_lines, measurer=measurer)
            if not info["truncated"]:
                chosen = (size, lines, info)
                break
            overflowed_at.append(size)
        if chosen is None:
            # Every configured tier, including the smallest, still needed
            # to drop characters -- this is the "zero truncation" gate:
            # refuse to silently ship a truncated line (see run()).
            hard_failures.append((card, text, cascade[-1], info))
            continue
        size, lines, chosen_info = chosen
        plans[card] = {"font_size": size, "lines": lines, "info": chosen_info}
        if size != cascade[0]:
            fallbacks.append((card, size, overflowed_at))
    return plans, fallbacks, hard_failures


def resolve_fonts_by_card(plans, fonts_by_size):
    """plans: {card: {"font_size": int, ...}} (build_render_plan's output).
    Returns {card: ImageFont} for direct use by bake_sheet/
    build_cellzoom_image -- the flattened per-card font lookup the cascade
    plan resolves to."""
    return {card: fonts_by_size[p["font_size"]] for card, p in plans.items()}


def measure_vertical_extent(text, font, box=TEXT_BOX, pad=20):
    """Render `text` centered the same way bake_cell/render_text_layer would
    (anchor="mm" on `box`'s geometry), but onto a canvas padded well beyond
    the cell's real CELL_H, then return the ink's (y0, y1) extent translated
    back into the cell's own coordinate frame (or None if no ink at all).

    Why not just measure on the real CELL_W x CELL_H canvas: PIL silently
    drops any pixel it's asked to draw outside the image it was given --
    an over-tall glyph at a bigger font size would simply vanish at the top
    and/or bottom rather than raising or even being visibly cropped, so a
    same-size render can never reveal this failure mode by construction.
    Padding turns "clips silently" into "ink measured outside
    [box[1], box[3])", which this function can detect and report -- this is
    the empirical check behind the "11px glyph height vs 15px cell, is
    there a clipping risk" question flagged in this round's task.
    """
    w = (box[2] - box[0]) + 2 * pad
    h = (box[3] - box[1]) + 2 * pad
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = pad + (box[2] - box[0]) / 2
    cy = pad + (box[3] - box[1]) / 2
    d.text((cx, cy), text, font=font, fill=FILL_COLOR, anchor="mm",
           stroke_width=STROKE_WIDTH, stroke_fill=STROKE_COLOR)
    bbox = layer.split()[-1].getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return (y0 - pad + box[1], y1 - pad + box[1])


def collect_vertical_clip_risks(titles, fonts_by_card, box=TEXT_BOX):
    """For every card in `fonts_by_card` (i.e. every card that made it
    through build_render_plan), measure its actual rendered ink y-extent at
    its RESOLVED cascade size via measure_vertical_extent's padded-canvas
    trick, and flag any card whose extent falls outside [box[1], box[3]) --
    meaning the real CELL_H-sized render would have silently clipped its
    top and/or bottom. MUST be surfaced -- never discarded (same
    never-silent principle as collect_ink_outliers/collect_overflow)."""
    out = []
    for card in sorted(fonts_by_card):
        extent = measure_vertical_extent(titles[card], fonts_by_card[card], box=box)
        if extent is None:
            continue
        y0, y1 = extent
        if y0 < box[1] or y1 >= box[3]:
            out.append((card, y0, y1))
    return out


def build_compare_image(pairs):
    """pairs: [(orig_sheet_img, new_sheet_img), ...] (len NUM_SHEETS).
    Stacks orig-over-new per sheet, sheets left-to-right."""
    gap = 6
    label_h = 16
    col_w = SHEET_W
    canvas_w = len(pairs) * col_w + (len(pairs) + 1) * gap
    canvas_h = label_h + SHEET_H + gap + SHEET_H + gap * 2
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (32, 32, 32, 255))
    d = ImageDraw.Draw(canvas)
    x = gap
    for i, (orig, new) in enumerate(pairs, start=1):
        d.text((x, gap), f"scene_{i}_a  JP(top) / ZH(bottom)", fill=(255, 255, 255, 255))
        y = gap + label_h
        canvas.paste(orig.convert("RGBA"), (x, y))
        y += SHEET_H + gap
        canvas.paste(new.convert("RGBA"), (x, y))
        x += col_w + gap
    return canvas


# Cells hand-picked for human review. As of the v3 font-size cascade, the
# picks are the 4 real cards that fall back below FONT_SIZE_CASCADE[0]
# (2, 90, 180, 182) PLUS their real same-row neighbours in the actual
# png/scene/ grid (1&3 / 88&89 / 178&179 / 181&183) -- listed here in the
# same left-to-right, row-by-row order they occupy on the real sheet, so
# that build_cellzoom_image's cols=3 layout below reproduces each real row
# as one displayed row. This is deliberate, not incidental: the user's ask
# this round is specifically to judge "does a fallback cell look jarring
# NEXT TO its real neighbour" (a same-screen font-size mismatch), which
# requires actual grid adjacency, not just any dozen interesting cards --
# see tests/test_bake_scene.py::
# test_cellzoom_cards_include_fallback_cards_and_real_row_neighbors for the
# regression pin (computed from cell_position(), not hardcoded pairs).
CELLZOOM_CARDS = [1, 2, 3, 88, 89, 90, 178, 179, 180, 181, 182, 183]
CELLZOOM_SCALE = 8
CELLZOOM_COLS = 3   # matches the 3-cards-per-real-row grouping above


def build_cellzoom_image(titles, fonts_by_card, plans, cards=CELLZOOM_CARDS,
                          scale=CELLZOOM_SCALE, cols=CELLZOOM_COLS):
    """Two rows per card: original cell (top) and baked cell (bottom), each
    scaled up `scale`x with nearest-neighbor, labeled with the card number,
    title, and its ACTUAL resolved font size -- with a visible [FALLBACK]
    tag for any card not rendered at FONT_SIZE_CASCADE[0], so the size
    mismatch this round is about is legible in the image itself, not just
    inferable from position.

    fonts_by_card/plans: build_render_plan()'s resolved per-card font
    (resolve_fonts_by_card()) and its plan dict (for font_size labels)."""
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
    n = len(cards)
    rows = (n + cols - 1) // cols
    canvas_w = cols * col_w + gap
    canvas_h = rows * row_h + gap
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)

    for i, card in enumerate(cards):
        sheet_num, box = cell_box(card)
        cell = get_sheet(sheet_num).crop(box)
        new_cell = bake_cell(cell, titles[card], fonts_by_card[card])

        col = i % cols
        row = i // cols
        x = gap + col * col_w
        y = gap + row * row_h

        size = plans[card]["font_size"]
        tag = "" if size == FONT_SIZE_CASCADE[0] else " [FALLBACK]"
        d.text((x, y), f"#{card} {titles[card][:10]} @{size}px{tag}",
               fill=(255, 255, 0, 255))
        y2 = y + label_h
        canvas.paste(cell.resize((cell_disp_w, cell_disp_h), Image.NEAREST), (x, y2))
        canvas.paste(new_cell.resize((cell_disp_w, cell_disp_h), Image.NEAREST),
                     (x, y2 + cell_disp_h))
        for dy_off in (0, cell_disp_h):
            bx0 = x + TEXT_BOX[0] * scale
            bx1 = x + TEXT_BOX[2] * scale
            by = y2 + dy_off
            d.rectangle([bx0, by, bx1, by + cell_disp_h - 1], outline=(0, 255, 255, 200))

    return canvas


def run(write=True, with_cellzoom=None):
    if with_cellzoom is None:
        with_cellzoom = write
    fonts_by_size = load_fonts()
    all_titles = load_titles_zh()
    titles = {c: all_titles[c] for c in range(1, NUM_CARDS + 1)}

    plans, fallbacks, hard_failures = build_render_plan(titles, fonts_by_size)
    if hard_failures:
        # Zero-truncation invariant: a card that overflows even the
        # smallest configured cascade tier must stop the whole run, not be
        # silently baked with a truncated caption. Raise BEFORE any file is
        # touched (no os.makedirs/save happens above this point).
        detail = "; ".join(
            f"card {c} ({t!r}) still overflows at the smallest configured "
            f"tier ({sz}px)"
            for c, t, sz, _info in hard_failures
        )
        raise RuntimeError(
            f"font-size cascade {FONT_SIZE_CASCADE} exhausted without "
            f"fitting {len(hard_failures)} title(s) -- refusing to "
            f"silently truncate (zero-truncation invariant): {detail}"
        )

    fonts_by_card = resolve_fonts_by_card(plans, fonts_by_size)
    ink_outliers = collect_ink_outliers()
    vertical_clip_risks = collect_vertical_clip_risks(titles, fonts_by_card)

    new_sheets = []
    orig_sheets = []
    all_diffs = {}
    for sheet_num in range(1, NUM_SHEETS + 1):
        new_sheet, diffs = bake_sheet(sheet_num, titles, fonts_by_card)
        new_sheets.append(new_sheet)
        orig_sheets.append(Image.open(sheet_path(sheet_num)).convert("RGBA"))
        all_diffs.update(diffs)

    bad_cells = [c for c, d in all_diffs.items() if d]

    fallback_records = [
        {
            "card": c,
            "font_size": size,
            "overflowed_at": tried,
            "reason": (
                f"title overflowed the {MAX_TEXT_W}px TEXT_BOX at "
                f"{'/'.join(str(s) for s in tried)}px; stepped down to "
                f"{size}px"
            ),
        }
        for c, size, tried in fallbacks
    ]

    report = {
        "num_cards": NUM_CARDS,
        "font_size_cascade": list(FONT_SIZE_CASCADE),
        "font_size_default": FONT_SIZE_CASCADE[0],
        "cell_font_sizes": {str(c): plans[c]["font_size"] for c in sorted(plans)},
        "fallbacks": fallback_records,
        # "overflow" == hard_failures -- always [] here (a non-empty list
        # would already have raised above). Kept as its own field (rather
        # than folded into fallbacks) because it's a categorically
        # different, more severe event: fallbacks still bake cleanly at a
        # smaller size; overflow means NOTHING in the cascade fit.
        "overflow": [
            {"card": c, "title_zh": t, "smallest_font_size": sz}
            for c, t, sz, _info in hard_failures
        ],
        "pixel_preservation_violations": bad_cells,
        "ink_outliers": [{"card": c, "reason": r, "bbox": b} for c, r, b in ink_outliers],
        "vertical_clip_risks": [
            {"card": c, "y_extent": [y0, y1]} for c, y0, y1 in vertical_clip_risks
        ],
        "text_box": list(TEXT_BOX),
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        for i, sheet in enumerate(new_sheets, start=1):
            sheet.convert("RGBA").save(os.path.join(OUT_DIR, f"scene_{i}_a.png"))
        compare = build_compare_image(list(zip(orig_sheets, new_sheets)))
        compare.save(os.path.join(OUT_DIR, "_compare.png"))
        if with_cellzoom:
            cellzoom = build_cellzoom_image(titles, fonts_by_card, plans)
            cellzoom.save(os.path.join(OUT_DIR, "_cellzoom.png"))
        with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="bake in-memory only, don't write files")
    args = ap.parse_args()
    try:
        report = run(write=not args.check)
    except RuntimeError as e:
        # Zero-truncation invariant tripped (a title overflows even the
        # smallest cascade tier) -- stop, don't bake a truncated caption.
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"cards: {report['num_cards']}")
    print(f"font size cascade: {report['font_size_cascade']} "
          f"(default {report['font_size_default']}px)")

    # Fallbacks MUST be visible here -- a per-cell cascade that silently
    # downgrades a card's font size is itself a silent-regression pattern
    # ("看起来 195 条全渲好了" while some quietly shipped smaller). Never
    # collapse this to just a count.
    print(f"fallbacks (cards NOT rendered at {report['font_size_default']}px): "
          f"{len(report['fallbacks'])}")
    for fb in report["fallbacks"]:
        print(f"  card {fb['card']}: -> {fb['font_size']}px "
              f"(overflowed at {fb['overflowed_at']}px each)")

    print(f"overflow (cascade exhausted -- would need real truncation): "
          f"{len(report['overflow'])}")
    for o in report["overflow"]:
        print(f"  card {o['card']}: {o['title_zh']!r} still overflows at "
              f"smallest tier {o['smallest_font_size']}px")

    print(f"ink outliers (real JP caption not fitting TEXT_BOX, or undetected): "
          f"{len(report['ink_outliers'])}")
    for o in report["ink_outliers"]:
        print(f"  card {o['card']}: {o['reason']} bbox={o['bbox']}")

    print(f"vertical clip risks (ink would extend outside the cell's real "
          f"canvas bounds): {len(report['vertical_clip_risks'])}")
    for c in report["vertical_clip_risks"]:
        print(f"  card {c['card']}: y_extent={c['y_extent']}")

    print(f"pixel-preservation violations: {len(report['pixel_preservation_violations'])}")
    if report["pixel_preservation_violations"]:
        print(f"  cards: {report['pixel_preservation_violations']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
