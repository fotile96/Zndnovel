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
- FONT_SIZE=9: LXGWWenKai renders at exactly N px advance/char and N px
  glyph-cell height at size N (verified directly), and the real JP captions'
  measured per-char advance is ~9px (145px-wide cells; e.g. card180's 15-char
  title spans exactly 135px -> 9.0px/char) -- a visual-weight match, same
  method bake_plot used to pick its own font size.
"""
import argparse, json, os, sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.bake_plot import load_titles_zh
from tools.zh_wrap import wrap as _zh_wrap

SCENE_DIR = os.path.join(REPO, "png", "scene")
FONT_PATH = os.path.join(REPO, "third_party", "LXGWWenKai-Regular.ttf")
OUT_DIR = os.path.join(REPO, "build", "scene_zh")

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
FONT_SIZE = 9
TEXT_BOX = (5, 0, 140, 15)   # (x0, y0, x1, y1); redraw + coverage rectangle
MAX_TEXT_W = TEXT_BOX[2] - TEXT_BOX[0]   # 135
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


def bake_sheet(sheet_num, titles, font):
    """Return (new_sheet_image, per_cell_diffs). per_cell_diffs maps
    card -> list of outside-box pixel diffs (must be [] for every card)."""
    sheet = Image.open(sheet_path(sheet_num)).convert("RGBA")
    new_sheet = sheet.copy()
    diffs = {}
    lo = (sheet_num - 1) * CARDS_PER_SHEET + 1
    hi = min(sheet_num * CARDS_PER_SHEET, NUM_CARDS)
    for card in range(lo, hi + 1):
        _, box = cell_box(card)
        cell = sheet.crop(box)
        new_cell = bake_cell(cell, titles[card], font)
        d = find_outside_box_diffs(cell, new_cell, TEXT_BOX)
        diffs[card] = d
        new_sheet.paste(new_cell, box)
    return new_sheet, diffs


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


# Cells hand-picked to stress the riskiest parts of the pipeline for human
# review -- deliberately not "the nicest-looking cells".
CELLZOOM_CARDS = [1, 195, 182, 90, 80, 133, 114, 2, 38, 145, 118, 180]
CELLZOOM_SCALE = 8


def build_cellzoom_image(titles, font, cards=CELLZOOM_CARDS, scale=CELLZOOM_SCALE):
    """Two rows per card: original cell (top) and baked cell (bottom), each
    scaled up `scale`x with nearest-neighbor, labeled with the card number
    and title."""
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
    cols = 4
    rows = (n + cols - 1) // cols
    canvas_w = cols * col_w + gap
    canvas_h = rows * row_h + gap
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)

    for i, card in enumerate(cards):
        sheet_num, box = cell_box(card)
        cell = get_sheet(sheet_num).crop(box)
        new_cell = bake_cell(cell, titles[card], font)

        col = i % cols
        row = i // cols
        x = gap + col * col_w
        y = gap + row * row_h

        d.text((x, y), f"#{card} {titles[card][:10]}", fill=(255, 255, 0, 255))
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
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    all_titles = load_titles_zh()
    titles = {c: all_titles[c] for c in range(1, NUM_CARDS + 1)}

    overflow = collect_overflow(titles, font)
    ink_outliers = collect_ink_outliers()

    new_sheets = []
    orig_sheets = []
    all_diffs = {}
    for sheet_num in range(1, NUM_SHEETS + 1):
        new_sheet, diffs = bake_sheet(sheet_num, titles, font)
        new_sheets.append(new_sheet)
        orig_sheets.append(Image.open(sheet_path(sheet_num)).convert("RGBA"))
        all_diffs.update(diffs)

    bad_cells = [c for c, d in all_diffs.items() if d]

    report = {
        "num_cards": NUM_CARDS,
        "overflow": [{"card": c, "title_zh": t, "lines": l, "dropped": dr}
                      for c, t, l, dr in overflow],
        "pixel_preservation_violations": bad_cells,
        "ink_outliers": [{"card": c, "reason": r, "bbox": b} for c, r, b in ink_outliers],
        "text_box": list(TEXT_BOX),
        "font_size": FONT_SIZE,
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        for i, sheet in enumerate(new_sheets, start=1):
            sheet.convert("RGBA").save(os.path.join(OUT_DIR, f"scene_{i}_a.png"))
        compare = build_compare_image(list(zip(orig_sheets, new_sheets)))
        compare.save(os.path.join(OUT_DIR, "_compare.png"))
        if with_cellzoom:
            cellzoom = build_cellzoom_image(titles, font)
            cellzoom.save(os.path.join(OUT_DIR, "_cellzoom.png"))
        with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="bake in-memory only, don't write files")
    args = ap.parse_args()
    report = run(write=not args.check)
    print(f"cards: {report['num_cards']}")
    print(f"overflow (truncated) titles: {len(report['overflow'])}")
    for o in report["overflow"]:
        print(f"  card {o['card']}: {o['title_zh']!r} -> {o['lines']!r} dropped={o['dropped']!r}")
    print(f"ink outliers (real JP caption not fitting TEXT_BOX, or undetected): "
          f"{len(report['ink_outliers'])}")
    for o in report["ink_outliers"]:
        print(f"  card {o['card']}: {o['reason']} bbox={o['bbox']}")
    print(f"pixel-preservation violations: {len(report['pixel_preservation_violations'])}")
    if report["pixel_preservation_violations"]:
        print(f"  cards: {report['pixel_preservation_violations']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
