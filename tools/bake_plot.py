#!/usr/bin/env python3
"""Bake Chinese card-name text into png/plot/plot_{1..4}_a.png thumbnails.

png/plot/ holds 4 sheets (492x480, RGBA-in-P PNG) of 6-col x 10-row, 82x48px
cells. Cards 1..195 are laid out row-major (left-to-right, top-to-bottom)
across the 4 sheets in strict card-number order, 60 cards/sheet, per the
authoritative grid-fill loop in lua_scripts/snr_common.lua:925-954 (the same
math snr_story_main.lua / snr_fragment_main.lua use via `plotState[n]` to
layerClip() these thumbnails at runtime). See build/plot_layout_spec.md for
the full measurement writeup and evidence chain.

Usage:
    uv run python3 tools/bake_plot.py            # write build/plot_zh/*
    uv run python3 tools/bake_plot.py --check     # bake in-memory, run the
                                                   # pixel-preservation self
                                                   # check, print report, but
                                                   # do not write files

png/, skeleton/ are read-only inputs. All output goes to build/ (gitignored).
"""
import argparse, json, os, re, sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLOT_DIR = os.path.join(REPO, "png", "plot")
CARDS_ZH_PATH = os.path.join(REPO, "skeleton", "cards.zh.yaml")
FONT_PATH = os.path.join(REPO, "third_party", "LXGWWenKai-Regular.ttf")
OUT_DIR = os.path.join(REPO, "build", "plot_zh")

# ---------------------------------------------------------------------------
# Grid geometry (measured + confirmed against lua_scripts/snr_common.lua and
# pixel evidence -- see build/plot_layout_spec.md section 1-2).
# ---------------------------------------------------------------------------
SHEET_W, SHEET_H = 492, 480
CELL_W, CELL_H = 82, 48
GRID_COLS, GRID_ROWS = 6, 10          # 492/82=6, 480/48=10
CARDS_PER_SHEET = GRID_COLS * GRID_ROWS  # 60
NUM_SHEETS = 4
NUM_CARDS = 195

# ---------------------------------------------------------------------------
# Text layout (measured from original baked JP text -- see spec section 4).
# ---------------------------------------------------------------------------
FONT_SIZE = 10          # visual match: LXGW size 10 single-glyph height ~9px,
                         # advance ~10px/char, same order as the original's
                         # measured ~9px ink height / ~10.3px advance.
TEXT_X = 4               # left margin, matches original left ink edge (x=4).
TEXT_Y = 2                # top of line 1, matches original ink top (y~3).
LINE_HEIGHT = 12          # baseline pitch, matches original line1->line2 gap.
MAX_TEXT_W = 76           # content width budget (82 cell - ~2*3px margin).
MAX_LINES = 2             # empirically sufficient for all 195 title_zh at
                           # FONT_SIZE/MAX_TEXT_W above -- see collect_overflow.
FILL_COLOR = (255, 255, 255, 255)
STROKE_COLOR = (0, 0, 0, 255)
STROKE_WIDTH = 1

# Region that gets fully erased + redrawn per cell. Must comfortably contain
# MAX_LINES lines at the metrics above (line2 bottom ~= TEXT_Y + LINE_HEIGHT
# + glyph height + stroke ~= 2+12+11+1 = 26) with a small safety margin, and
# must stay clear of the original's own max ink row (~23, measured) too.
TEXT_BOX = (0, 0, CELL_W, 28)

ELLIPSIS = "…"


def cell_position(card):
    """card (1..195) -> (sheet 1..4, row 0..9, col 0..5).

    Mirrors the fill loop in lua_scripts/snr_common.lua:925-954 exactly:
    row-major within a sheet, 6 cols x 10 rows, new sheet every 60 cards.
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


def load_titles_zh(path=CARDS_ZH_PATH):
    """card(int) -> title_zh(str), for cards 1..195, from skeleton/cards.zh.yaml.

    skeleton/ is the frozen (git tag skeleton-v1) translation baseline and is
    read-only; this only parses it. Uses a tiny line-scanner instead of
    pyyaml's full parser semantics beyond what's needed, but pyyaml is a
    project dependency so we just use it directly for correctness.
    """
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    titles = {}
    for row in data:
        card = row.get("card")
        if isinstance(card, int) and 1 <= card <= NUM_CARDS:
            titles[card] = row["title_zh"]
    missing = sorted(set(range(1, NUM_CARDS + 1)) - set(titles))
    if missing:
        raise ValueError(f"cards.zh.yaml missing title_zh for cards: {missing}")
    return titles


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|.")


def _tokenize(text):
    """Split text into wrap atoms: runs of ASCII letters/digits stay whole
    (so a line break never lands inside a number like "10"), every other
    character (CJK, punctuation, kana) is its own atom."""
    return _TOKEN_RE.findall(text)


def wrap_title(text, font, max_width=MAX_TEXT_W, max_lines=MAX_LINES, measurer=None):
    """Greedy-wrap text into at most max_lines lines, each <= max_width px.

    Returns (lines, truncated). The first max_lines-1 lines are filled
    normally (one line break per width overflow); the LAST line absorbs
    everything left over. If even the last line can't fit what remains,
    it's trimmed and an ellipsis appended, and truncated=True is returned
    -- callers MUST surface this (see collect_overflow) rather than let it
    pass silently.
    """
    if measurer is None:
        _probe = Image.new("RGBA", (1, 1))
        _d = ImageDraw.Draw(_probe)
        measurer = lambda s: _d.textlength(s, font=font)

    atoms = _tokenize(text)
    lines = []
    cur = ""
    i = 0
    # Fill all but the last line normally.
    while i < len(atoms) and len(lines) < max_lines - 1:
        atom = atoms[i]
        trial = cur + atom
        if measurer(trial) > max_width and cur:
            lines.append(cur)
            cur = atom
        else:
            cur = trial
        i += 1

    # Last line absorbs everything remaining (cur so far + atoms[i:]).
    remaining = atoms[i:]
    last = cur
    j = 0
    while j < len(remaining):
        atom = remaining[j]
        trial = last + atom
        if measurer(trial) > max_width and last:
            break
        last = trial
        j += 1
    truncated = j < len(remaining)
    if truncated:
        while last and measurer(last + ELLIPSIS) > max_width:
            last = last[:-1]
        last = (last + ELLIPSIS) if last else ELLIPSIS
    lines.append(last)
    return lines, truncated


def collect_overflow(titles, font, max_width=MAX_TEXT_W, max_lines=MAX_LINES):
    """titles: {card: text}. Returns sorted [(card, text, lines), ...] for
    every title that needed truncation. MUST be called and its result
    surfaced (report/manifest) -- never discarded -- so a too-long title
    never silently loses characters."""
    out = []
    for card in sorted(titles):
        lines, truncated = wrap_title(titles[card], font, max_width, max_lines)
        if truncated:
            out.append((card, titles[card], lines))
    return out


def reconstruct_box(cell, box=TEXT_BOX):
    """Return a new image for `box`'s region with the original JP text fully
    erased: each column is flat-filled with the pixel color sampled from the
    cell just below the box (box's bottom row). This is a deliberately
    simple, deterministic, ghost-free technique -- see
    build/plot_layout_spec.md section 6 for why (per-pixel ink-detection +
    blur/nearest-fill inpainting were tried first and left visible ghosting
    of the old glyphs due to anti-aliasing) and its trade-off (loses
    within-box vertical background texture)."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    out = cell.crop(box)
    opx = out.load()
    src = cell.load()
    sample_y = min(y1, cell.height - 1)
    for x in range(w):
        color = src[x0 + x, sample_y]
        for y in range(y1 - y0):
            opx[x, y] = color
    return out


def render_text_layer(size, lines, font, x=TEXT_X, y=TEXT_Y, line_height=LINE_HEIGHT):
    """A cell-sized RGBA layer, transparent except where glyphs were drawn."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cy = y
    for line in lines:
        d.text((x, cy), line, font=font, fill=FILL_COLOR,
                stroke_width=STROKE_WIDTH, stroke_fill=STROKE_COLOR)
        cy += line_height
    return layer


def bake_cell(cell, lines, font):
    """cell: CELL_W x CELL_H RGBA image (one card's thumbnail+title).
    Returns a new image: TEXT_BOX region fully replaced (erased original +
    new Chinese text drawn on top); every pixel outside TEXT_BOX is
    byte-identical to `cell`."""
    recon = reconstruct_box(cell, TEXT_BOX)
    new_cell = cell.copy()
    new_cell.paste(recon, TEXT_BOX)
    layer = render_text_layer(cell.size, lines, font)
    return Image.alpha_composite(new_cell, layer)


def find_outside_box_diffs(orig_cell, new_cell, box=TEXT_BOX):
    """Return list of (x,y) pixels OUTSIDE box where orig_cell != new_cell.
    Empty list == the non-text-region-preserved invariant holds for this
    cell. This is the pixel-preservation safety gate; it must actually be
    called (and asserted empty) by the baking pipeline, not just exist."""
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
    """Return (new_sheet_image, per_cell_diffs) where per_cell_diffs maps
    card -> list of outside-box pixel diffs (should be [] for every card)."""
    path = os.path.join(PLOT_DIR, f"plot_{sheet_num}_a.png")
    sheet = Image.open(path).convert("RGBA")
    new_sheet = sheet.copy()
    diffs = {}
    lo = (sheet_num - 1) * CARDS_PER_SHEET + 1
    hi = min(sheet_num * CARDS_PER_SHEET, NUM_CARDS)
    for card in range(lo, hi + 1):
        _, box = cell_box(card)
        cell = sheet.crop(box)
        lines, truncated = wrap_title(titles[card], font)
        new_cell = bake_cell(cell, lines, font)
        d = find_outside_box_diffs(cell, new_cell)
        diffs[card] = d
        new_sheet.paste(new_cell, box)
    return new_sheet, diffs


def build_compare_image(pairs):
    """pairs: [(orig_sheet_img, new_sheet_img), ...] (len 4).
    Stacks orig-over-new per sheet, sheets left-to-right, with a thin
    separator and small labels."""
    gap = 6
    label_h = 16
    n = len(pairs)
    col_w = SHEET_W
    col_h = label_h + SHEET_H + gap + SHEET_H
    canvas_w = n * col_w + (n + 1) * gap
    canvas_h = col_h + gap * 2
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (32, 32, 32, 255))
    d = ImageDraw.Draw(canvas)
    x = gap
    for i, (orig, new) in enumerate(pairs, start=1):
        d.text((x, gap), f"plot_{i}_a  JP(top) / ZH(bottom)", fill=(255, 255, 255, 255))
        y = gap + label_h
        canvas.paste(orig.convert("RGBA"), (x, y))
        y += SHEET_H + gap
        canvas.paste(new.convert("RGBA"), (x, y))
        x += col_w + gap
    return canvas


def run(write=True):
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    titles = load_titles_zh()
    overflow = collect_overflow(titles, font)

    new_sheets = []
    orig_sheets = []
    all_diffs = {}
    for sheet_num in range(1, NUM_SHEETS + 1):
        new_sheet, diffs = bake_sheet(sheet_num, titles, font)
        new_sheets.append(new_sheet)
        orig_sheets.append(Image.open(os.path.join(PLOT_DIR, f"plot_{sheet_num}_a.png")).convert("RGBA"))
        all_diffs.update(diffs)

    bad_cells = [c for c, d in all_diffs.items() if d]
    report = {
        "num_cards": NUM_CARDS,
        "overflow": [{"card": c, "title_zh": t, "lines": l} for c, t, l in overflow],
        "pixel_preservation_violations": bad_cells,
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        for i, sheet in enumerate(new_sheets, start=1):
            sheet.convert("RGBA").save(os.path.join(OUT_DIR, f"plot_{i}_a.png"))
        compare = build_compare_image(list(zip(orig_sheets, new_sheets)))
        compare.save(os.path.join(OUT_DIR, "_compare.png"))
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
        print(f"  card {o['card']}: {o['title_zh']!r} -> {o['lines']!r}")
    print(f"pixel-preservation violations: {len(report['pixel_preservation_violations'])}")
    if report["pixel_preservation_violations"]:
        print(f"  cards: {report['pixel_preservation_violations']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
