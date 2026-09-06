#!/usr/bin/env python3
"""Bake Chinese card-name text into png/plot/plot_{1..4}_a.png thumbnails.

NOTE (2026-09-07): the production path is now tools/bake_plot_plate.py (clean
plate reconstruction, decision P6); this module is its fallback for cells whose
plate recipe is `band`, and a library (grid, wrapping, text layer). Running it
directly still produces the all-band product for A/B comparison.

png/plot/ holds 4 sheets (492x480, RGBA-in-P PNG) of 6-col x 10-row, 82x48px
cells. Cards 1..195 are laid out row-major (left-to-right, top-to-bottom)
across the 4 sheets in strict card-number order, 60 cards/sheet, per the
authoritative grid-fill loop in lua_scripts/snr_common.lua:925-954 (the same
math snr_story_main.lua / snr_fragment_main.lua use via `plotState[n]` to
layerClip() these thumbnails at runtime). See build/plot_layout_spec.md for
the full measurement writeup and evidence chain.

Each cell's lower ~40% is a scene-thumbnail/CG background with the original
Japanese caption baked on top of it in the top area. There is no clean
background plate to fall back to (searched all of png/bg + png/event,
confirmed as a dead end -- see the report), so the caption region is covered
with a deliberately-translucent color band (not fully erased) sized to the
ACTUAL vertical extent of ink in that specific cell, not a fixed box -- see
decide_band()/ink_bbox_of_cell() below. This keeps as much of the original
artwork visible as each cell's real caption height allows, instead of the
old approach's flat 28px-tall opaque strip on every cell regardless of how
short its caption was.

Usage:
    uv run python3 tools/bake_plot.py            # write build/plot_zh/*
    uv run python3 tools/bake_plot.py --check     # bake in-memory, run the
                                                   # pixel-preservation self
                                                   # check, print report, but
                                                   # do not write files
    uv run python3 tools/bake_plot.py --cellzoom  # also write
                                                   # build/plot_zh/_cellzoom.png

png/, skeleton/ are read-only inputs. All output goes to build/ (gitignored).
"""
import argparse, json, os, re, sys
from collections import namedtuple

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:  # allow `python3 tools/bake_plot.py` direct invocation
    sys.path.insert(0, REPO)

from tools.zh_wrap import wrap as _zh_wrap
from tools.ui_font import resolve as _resolve_font
from tools.bake_out import out_dir as _out_dir
from tools.ui_font import truetype as _ui_truetype

PLOT_DIR = os.path.join(REPO, "png", "plot")
CARDS_ZH_PATH = os.path.join(REPO, "skeleton", "cards.zh.yaml")
CARDS_JP_PATH = os.path.join(REPO, "skeleton", "cards.jp.yaml")
#: 字体按面可换：`ZND_UI_FONT_PLOT` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷
#: Regular。面名＝plot。详见 tools/ui_font.py——那里也记着
#: 「换字体后金标夹具会红，这是对的」。
FONT_PATH = str(_resolve_font("plot"))
OUT_DIR = str(_out_dir("plot_zh"))

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

ELLIPSIS = "…"

# ---------------------------------------------------------------------------
# Ink detection (see build/plot_layout_spec.md addendum "band" section for
# the 195-cell empirical validation of every threshold below).
#
# A pixel counts as "ink" only if it is BOTH near-white (the glyph fill,
# matches the original's measured fill ~(238,238,238)) AND has a near-black
# pixel (the glyph stroke, matches the original's measured stroke
# ~(0,0,0)/(1,1,1)) within a small neighborhood. Brightness alone is NOT
# enough: bright photographic content (sky, white school uniforms, a pool)
# triggers the brightness test constantly but essentially never has a
# stroke-dark pixel immediately adjacent, so requiring the *pairing* is what
# keeps bright backgrounds from being misread as caption ink. This was
# validated over all 195 real cells, not assumed -- see the report.
# ---------------------------------------------------------------------------
INK_BRIGHT_THRESH = 200   # near-white fill core.
INK_DARK_THRESH = 90      # near-black stroke.
INK_NEIGHBOR_RADIUS = 2   # Chebyshev radius a dark pixel must be within.
INK_MIN_ROW_PIXELS = 3    # a row only counts as an "ink row" if at least
                           # this many qualifying (bright+dark-adjacent)
                           # pixels are found in it -- rejects one-off
                           # coincidental bright/dark photo edges.
INK_MAX_PLAUSIBLE_BOTTOM = 30  # sanity cap. The 195-cell survey's real max
                           # detected ink bottom is y=23 (a 2-line caption);
                           # nothing legitimate should ever measure past 30.
                           # A detection past this is treated as the
                           # detector having been fooled, not a giant
                           # caption -- falls back rather than trusting it.
INK_BOTTOM_MARGIN = 1     # tiny safety pad appended past the last detected
                           # ink row (anti-aliased stroke edges fade out a px
                           # past the hard threshold used to find them). This
                           # stays part of the FULL-alpha zone -- see
                           # decide_band -- specifically so the one thing
                           # that must never be under-covered (real ink)
                           # never lands inside the cosmetic feather ramp.
ZH_BOTTOM_MARGIN = 1      # same pad appended past the last actually-rendered
                           # zh glyph row, same full-alpha-zone reasoning.

# NOTE: there used to be a FALLBACK_BAND_BOTTOM=28 constant here, used as a
# fixed conservative band height whenever ink detection failed. It has been
# REMOVED (not merely unused) per user verdict on card 162 (the sole
# fallback cell, see decide_band): a fixed 2-JP-line-tall band massively
# over-covers a short zh caption -- card 162's "第二物语" needs 1 line but
# got a 32-row band, leaving a visibly empty black strip below the text that
# read as a bug, not a design. The fallback band height is now computed the
# same way non-fallback content height is measured on the zh side: the
# ACTUAL rendered height of the zh caption (see measure_rendered_text_bottom
# in decide_band's fallback branch below), never a fixed number.
#
# ⚠ This is a DELIBERATE reduction in fallback safety margin, not a neutral
# refactor: when ink detection fails, decide_band no longer has ANY
# candidate for where the untracked original Japanese ink actually sits, so
# it can no longer defend against it via a generous fixed height -- it only
# covers what the zh caption itself needs. Original ink extending below that
# height MAY REMAIN PARTIALLY VISIBLE (confirmed real case: card 162's own
# subtitle "〜彼女の夏、15分の記憶〜" extends to roughly y=40, well past the
# ~18px a single zh line now claims). This must be surfaced every time a
# fallback occurs -- see collect_ink_fallbacks, run()'s
# "ink_fallback_coverage_note", and the CLI output in main(). Never let this
# happen silently.

# ---------------------------------------------------------------------------
# Band visual parameters -- see build/plot_layout_spec.md addendum for the
# full quantitative sweep and the visual dead-end these were picked from.
#
# IMPORTANT, hard-won finding: a single UNIFORM alpha for the whole covered
# region cannot satisfy both goals at once. The original captions are
# near-maximum-contrast (white fill ~238 on black stroke ~0-1), and even a
# small residual of that after alpha blending (e.g. 19/255 = 7.5% at
# alpha=235, or 5/255 = 2% at alpha=250) still reads as LEGIBLE ghost text
# once your eye locks onto the familiar glyph shape against a near-black
# field -- confirmed both by a quantitative worst-case-residual sweep AND by
# isolated (non-downscaled) visual review; a uniform alpha only became
# genuinely clean at alpha=255, i.e. fully opaque, at which point it isn't
# translucent there at all. See the report for the full walk (including a
# methodological trap: viewing many cells tiled into one large PNG can
# itself introduce faint ringing/ghosting-looking artifacts from the image
# transport's own downscaling -- a flat synthetic-cell control ruled that
# out as the explanation here, but it's a real trap to watch for).
#
# The resolution actually used: a PER-ROW hard/soft alpha profile, not a
# single constant.
#   - Rows that DEMONSTRABLY HELD real ink (BandDecision.hard_range, from
#     the measured ink envelope, or the ENTIRE content_bottom zone when
#     ink detection fell back and the true location is simply unknown) are
#     forced to HARD_ALPHA=255 -- fully opaque, zero possible residual, no
#     exceptions. This is the one thing that must never be under-covered.
#   - Rows that never held ink (the top/bottom cosmetic feather, and any
#     "extra" rows a longer zh caption needs beyond what the JP ink
#     needed -- e.g. card 25, JP ink is 1 line but zh wraps to 2) use the
#     genuinely translucent BAND_ALPHA. There is nothing to hide there, so
#     translucency is free -- this is what keeps the band from being a
#     de-facto solid patch everywhere despite the hard zone.
# ---------------------------------------------------------------------------
BAND_COLOR = (0, 0, 0)
HARD_ALPHA = 255            # opacity forced over rows that actually held ink
                            # (or the whole zone, on fallback). Not a design
                            # choice so much as a measured necessity -- see
                            # the block comment above.
BAND_ALPHA = 200            # translucent alpha for rows that never held ink.
                            # Doesn't need the same rigor as HARD_ALPHA since
                            # there's no high-contrast content to leak
                            # through there in the first place -- 200 (~78%)
                            # was checked visually on the cells where it's
                            # actually used (card 25's second zh-only line,
                            # every card's feather edges) and reads as a
                            # clearly non-opaque dark band over the photo.
BAND_TOP_FEATHER_PX = 2    # top edge ramp (alpha 0 -> BAND_ALPHA). Small and
                           # safe: the 195-cell survey never found ink above
                           # y=3, so a 2px fade-in at the very top of the
                           # cell never eats into real content.
BAND_BOTTOM_FEATHER_PX = 4  # bottom edge ramp (alpha BAND_ALPHA -> 0), added
                           # strictly BEYOND content_bottom -- never carved
                           # out of it. An earlier version feathered the
                           # last few rows of band_bottom unconditionally,
                           # which silently ate into real 2nd-line ink
                           # coverage; caught by visual review, not by the
                           # pixel-preservation gate (which only checks
                           # OUTSIDE the box -- under-coverage INSIDE it is
                           # exactly what that bug produced).
HARD_TRANSITION_PX = 2      # short ramp between the hard (255) sub-range and
                           # the surrounding soft alpha, purely so the two
                           # zones don't meet at a visible hard seam.


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


def load_titles_jp(path=CARDS_JP_PATH):
    """card(int) -> title_jp(str), 1..195, from skeleton/cards.jp.yaml (variant a)."""
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    titles = {}
    for row in data:
        card = row.get("card")
        if isinstance(card, int) and 1 <= card <= NUM_CARDS and card not in titles:
            titles[card] = row["title_jp"]
    missing = sorted(set(range(1, NUM_CARDS + 1)) - set(titles))
    if missing:
        raise ValueError(f"cards.jp.yaml missing title_jp for cards: {missing}")
    return titles


#: 原图断行规则：第 7 字后断行，两行封顶。195 张里 ≤7 字的 79 张全是一行、≥8 字的 116 张
#: 全是两行，无一例外（2026-09-07 普查，docs/ops/plot-plate-research-2026-09-07.md §1）。
#: 像素检测在「第二行只有一个瘦假名」时会整行漏检（卡 7/42/86/161：每行合格像素 1–2 个，
#: 低于 INK_MIN_ROW_PIXELS=3），所以行数由字数决定，像素检测降为交叉核对。
JP_LINE_BREAK_AT = 7
#: 各行墨迹底（含端点）：line1 y3–11，line2 y15–23（spec §4 实测）。
JP_LINE_INK_BOTTOM = {1: 11, 2: 23}


def jp_line_count(title_jp):
    return 1 if len(title_jp) <= JP_LINE_BREAK_AT else 2


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|.")


def _tokenize(text):
    """Split text into wrap atoms: runs of ASCII letters/digits stay whole
    (so a line break never lands inside a number like "10"), every other
    character (CJK, punctuation, kana) is its own atom.

    Kept for backward compatibility (still imported directly by
    tests/test_bake_plot.py::test_tokenize_keeps_ascii_digit_runs_atomic).
    wrap_title() itself no longer uses this -- see tools/zh_wrap.py, which
    re-derives the same ASCII/digit-run atomicity guarantee at the
    character-position level (_ascii_digit_hard_positions)."""
    return _TOKEN_RE.findall(text)


def wrap_title(text, font, max_width=MAX_TEXT_W, max_lines=MAX_LINES, measurer=None):
    """Wrap text into at most max_lines lines, each <= max_width px, using
    the shared word-boundary-aware, globally-optimal wrapper in
    tools/zh_wrap.py (DP over penalty functions -- width imbalance, orphan
    single-char lines, word-internal breaks, kinsoku) instead of the old
    greedy fill-then-truncate algorithm.

    Returns (lines, truncated) -- same signature/semantics as before this
    migration (see tools/zh_wrap.py:wrap()'s docstring for the full `info`
    dict this discards; call tools.zh_wrap.wrap() directly for that).
    truncated=True means the retreat chain's last-resort step fired (text
    genuinely does not fit in max_lines lines even after every other
    concession) -- callers MUST surface this (see collect_overflow) rather
    than let it pass silently, exactly as before.
    """
    if measurer is None:
        _probe = Image.new("RGBA", (1, 1))
        _d = ImageDraw.Draw(_probe)
        measurer = lambda s: _d.textlength(s, font=font)

    lines, info = _zh_wrap(text, max_width, max_lines=max_lines, measurer=measurer)
    return lines, info["truncated"]


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


# ---------------------------------------------------------------------------
# Ink detection + band sizing.
# ---------------------------------------------------------------------------

def _is_bright(rgb, thresh=INK_BRIGHT_THRESH):
    r, g, b = rgb
    return min(r, g, b) >= thresh


def _is_dark(rgb, thresh=INK_DARK_THRESH):
    r, g, b = rgb
    return max(r, g, b) <= thresh


def ink_bbox_of_cell(cell, bright_thresh=INK_BRIGHT_THRESH,
                      dark_thresh=INK_DARK_THRESH, radius=INK_NEIGHBOR_RADIUS,
                      min_row_px=INK_MIN_ROW_PIXELS):
    """Find the vertical extent of the ORIGINAL caption glyphs baked into
    `cell`, using the joint bright+adjacent-dark criterion described above
    the module constants. Returns (top, bottom) row indices (inclusive,
    0-based within the cell) of the full ink extent, or None if no row met
    the density threshold anywhere in the cell.

    Implementation note: the "dark pixel within `radius`" test is done as a
    separable square-neighborhood dilation of the dark mask (row-pass then
    column-pass) so the whole cell (82x48) is O(w*h) rather than O(w*h*r^2)
    -- this runs in well under a second for all 195 real cells combined.
    """
    rgb = cell.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    dark = [[_is_dark(px[x, y], dark_thresh) for x in range(w)] for y in range(h)]
    row_dilated = [[False] * w for _ in range(h)]
    for y in range(h):
        row = dark[y]
        for x in range(w):
            lo, hi = max(0, x - radius), min(w, x + radius + 1)
            row_dilated[y][x] = any(row[lo:hi])
    dark_dilated = [[False] * w for _ in range(h)]
    for x in range(w):
        col = [row_dilated[y][x] for y in range(h)]
        for y in range(h):
            lo, hi = max(0, y - radius), min(h, y + radius + 1)
            dark_dilated[y][x] = any(col[lo:hi])

    ink_rows = []
    for y in range(h):
        cnt = 0
        for x in range(w):
            if dark_dilated[y][x] and _is_bright(px[x, y], bright_thresh):
                cnt += 1
        if cnt >= min_row_px:
            ink_rows.append(y)
    return (min(ink_rows), max(ink_rows)) if ink_rows else None


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


def measure_rendered_text_bottom(lines, font, size=(CELL_W, CELL_H), x=TEXT_X,
                                  y=TEXT_Y, line_height=LINE_HEIGHT):
    """Render `lines` exactly the way bake_cell will, and return the
    bottom-most row (inclusive) that actually has a non-transparent pixel.
    This is a real measurement of what OUR rendering needs, not a formula
    guess -- if font/metrics ever change this stays correct automatically."""
    layer = render_text_layer(size, lines, font, x=x, y=y, line_height=line_height)
    bbox = layer.split()[-1].getbbox()  # alpha channel bbox
    if bbox is None:
        return y
    return bbox[3] - 1  # getbbox()'s lower bound is exclusive


BandDecision = namedtuple("BandDecision", [
    "band_bottom",       # final total band height incl. cosmetic feather
                          # zone (rows [0, band_bottom))
    "content_bottom",     # coverage requirement: max(ink, zh), each with
                          # only its tiny anti-alias margin -- everything up
                          # to here is at least soft-covered (BAND_ALPHA),
                          # nothing here is allowed to fade to 0.
    "hard_range",         # (top, bottom): rows that MUST render at
                          # HARD_ALPHA=255 -- the measured ink envelope (+
                          # margin), or the WHOLE content_bottom zone when
                          # ink detection fell back and the true ink
                          # location is unknown. See the BAND_ALPHA comment
                          # block above the constants for why this exists.
    "ink_bbox",           # (top, bottom) detected in the ORIGINAL cell, or None
    "ink_bottom_used",    # ink-derived candidate bottom (post margin), or
                          # None on fallback -- there is no trustworthy ink
                          # measurement to report in that case (see decide_band).
    "zh_bottom_used",     # zh-render-derived candidate bottom (post margin)
    "fallback",           # bool: did ink detection fail/get rejected?
    "fallback_reason",    # str or None
    "line_rule",          # None (no jp title given) | "agree" | "override" |
                          # "detect>rule" | "fallback": how the title-length
                          # line rule interacted with pixel detection.
], defaults=(None,))


def decide_band(cell, lines, font, jp_title=None):
    """Decide how tall the translucent cover band needs to be for this cell.

    `jp_title` (the ORIGINAL Japanese caption baked into the cell) switches on
    the title-length line rule (see JP_LINE_BREAK_AT): the number of caption
    lines is decided by the title length, and the pixel ink detection is only
    a cross-check. When detection found fewer lines than the rule says -- or
    found the second line but stopped short of its measured bottom -- the ink
    envelope is extended to JP_LINE_INK_BOTTOM[lines] (`line_rule="override"`).
    Detection is never shortened by the rule. Without `jp_title` behaviour is
    exactly the pre-2026-09-07 one (`line_rule=None`).

    Normal path (ink detected and plausible): max(vertical extent of the
    ORIGINAL jp ink actually detected in the art, vertical extent OUR OWN zh
    rendering actually needs). Both are measured, not guessed, and the
    LARGER of the two is used -- using only the ink height would clip a zh
    caption that needs more lines than the original JP one did (real
    example: card 25, JP ink is a single line but the zh title wraps to 2
    lines); using only the zh height would leave original JP ink exposed
    below a too-short band on cells where the JP caption was taller than the
    zh one needs to be (real example: card 6, JP ink spans 2 lines but the
    zh title is a short single line). This max()-of-two-measurements
    behavior is UNCHANGED by the fallback path below and is pinned by
    test_decide_band_nonfallback_unaffected_by_fallback_path in
    tests/test_bake_plot.py.

    Fallback path (ink detection failed or was rejected as implausible --
    see ink_bbox_of_cell / INK_MAX_PLAUSIBLE_BOTTOM): there is no
    trustworthy ink measurement to max() against at all, so content_bottom
    is set to EXACTLY what the zh caption's own actual rendering needs
    (its real line count x line height + margin, via
    measure_rendered_text_bottom -- not a fixed guess). This is a
    DELIBERATE reduction of the coverage the old fixed-height fallback
    provided: on a cell where ink detection failed, the true location of
    the original Japanese ink is unknown, and a band sized only to the zh
    text may leave that original ink PARTIALLY VISIBLE below it (confirmed
    real case: card 162, see the module-level note above
    ink_bottom_used-adjacent code and collect_ink_fallbacks). Every
    fallback MUST be surfaced by the caller (collect_ink_fallbacks / run() /
    main()) precisely because of this reduced guarantee.

    content_bottom (each side measured with only its 1px anti-alias margin)
    is the region that MUST be at least soft-covered -- the visual
    bottom-edge feather (see render_band_layer) is added strictly BEYOND
    content_bottom, never carved out of it, so cosmetic softening can never
    under-cover real ink or clip real zh glyphs.

    hard_range additionally marks which part of that zone must be FULLY
    opaque rather than merely soft-covered: the measured ink envelope
    itself (a uniform BAND_ALPHA was tried and measured/viewed to leave the
    original high-contrast stroke text legibly visible underneath -- see
    the constants block -- so real ink gets forced opaque, full stop). On
    fallback (ink location unknown) the entire content_bottom zone is
    treated as hard, since there's no envelope to trust and "unknown" must
    default to the safe side (fully opaque over the zh-sized zone), not the
    pretty side -- this part is unchanged from before; only the SIZE of
    that zone changed.
    """
    ink = ink_bbox_of_cell(cell)
    fallback = False
    reason = None
    if ink is None:
        fallback = True
        reason = "no_ink_detected"
    elif ink[1] > INK_MAX_PLAUSIBLE_BOTTOM:
        fallback = True
        reason = f"implausible_ink_bottom_{ink[1]}"

    line_rule = None
    if jp_title is not None:
        if fallback:
            line_rule = "fallback"
        else:
            expected = jp_line_count(jp_title)
            detected = 2 if ink[1] >= JP_LINE_INK_BOTTOM[1] + 4 else 1
            rule_bottom = JP_LINE_INK_BOTTOM[expected]
            if detected > expected:
                line_rule = "detect>rule"       # never seen in the corpus; keep detection
            elif ink[1] < rule_bottom:
                line_rule = "override"
                ink = (ink[0], rule_bottom)
            else:
                line_rule = "agree"

    zh_bottom = measure_rendered_text_bottom(lines, font) + ZH_BOTTOM_MARGIN

    if fallback:
        # No trustworthy ink candidate at all -- content_bottom is exactly
        # the zh caption's own measured need, never padded with a fixed
        # guess. ink_bottom_used is None: there is nothing measured to
        # report on the ink side for this cell.
        ink_bottom = None
        content_bottom = min(zh_bottom, CELL_H)
    else:
        ink_bottom = ink[1] + INK_BOTTOM_MARGIN
        content_bottom = min(max(ink_bottom, zh_bottom), CELL_H)

    band_bottom = min(content_bottom + BAND_BOTTOM_FEATHER_PX, CELL_H)

    if fallback:
        hard_range = (0, content_bottom)
    else:
        hard_top = max(0, ink[0] - INK_BOTTOM_MARGIN)
        hard_bottom = min(ink[1] + INK_BOTTOM_MARGIN, content_bottom)
        hard_range = (hard_top, hard_bottom)

    return BandDecision(band_bottom, content_bottom, hard_range, ink,
                         ink_bottom, zh_bottom, fallback, reason, line_rule)


def collect_ink_fallbacks(decisions):
    """decisions: {card: BandDecision}. Returns sorted [(card, reason), ...]
    for every cell whose ink detection failed or was rejected as
    implausible and fell back to caption-only band coverage (see
    decide_band's fallback branch). MUST be called and its result surfaced
    (report/manifest/CLI) -- never discarded -- so a fallback never happens
    silently. A cell relying on the fallback got a height sized only to its
    zh caption, never actually measured against the real (unknown) ink
    location -- a human needs to know which cells those are, and that the
    coverage guarantee for them is weaker than normal cells (see
    run()'s ink_fallback_coverage_note)."""
    return sorted((c, d.fallback_reason) for c, d in decisions.items() if d.fallback)


def build_ink_fallback_coverage_note(fallbacks):
    """fallbacks: the [(card, reason), ...] list from collect_ink_fallbacks.
    Returns None if fallbacks is empty (nothing to warn about), otherwise a
    human-readable string naming the SPECIFIC reduced guarantee those cards
    now have: their band height is sized only to the zh caption's own
    rendered height, not to a fixed conservative height, so undetected
    original Japanese ink below that height may remain partially visible.

    This is a standalone function (not inlined in run()) specifically so it
    can be unit-tested in isolation -- see
    tests/test_bake_plot.py::test_ink_fallback_coverage_note_* -- separate
    from whether today's real png/plot/ data happens to contain a fallback
    card. MUST be called and its result surfaced (report/manifest/CLI) --
    never discarded -- this is the required warning for the coverage
    reduction described in decide_band's fallback branch and the
    FALLBACK_BAND_BOTTOM-removal note above it."""
    if not fallbacks:
        return None
    cards = [c for c, _ in fallbacks]
    return (
        f"{len(fallbacks)} card(s) fell back to caption-only band coverage "
        f"(ink location could not be measured): {cards}. For these cards "
        "ONLY, the band height is sized to the zh caption's own rendered "
        "height (line count x line height + margin), NOT to a fixed "
        "conservative height -- the true extent of the original Japanese "
        "ink is unknown, so any of that ink extending below the zh-sized "
        "band MAY REMAIN PARTIALLY VISIBLE. Human review required for each "
        "card listed in ink_fallback_cards."
    )


def _soft_alpha_at(y, content_bottom, band_bottom, alpha, top_feather, bottom_feather):
    """The cosmetic soft-coverage profile: 0 -> alpha ramp over the first
    `top_feather` rows, flat `alpha` through content_bottom, then alpha -> 0
    ramp over the trailing `bottom_feather` rows up to band_bottom."""
    if y >= content_bottom:
        bf = band_bottom - content_bottom
        return alpha * (band_bottom - y) / (bf + 1) if bf > 0 else 0
    tf = min(top_feather, content_bottom) if content_bottom > 0 else 0
    if tf > 0 and y < tf:
        return alpha * (y + 1) / (tf + 1)
    return alpha


def _hard_alpha_at(y, hard_top, hard_bottom, alpha, transition):
    """The mandatory-opaque profile: 0 outside [hard_top, hard_bottom),
    `alpha` (HARD_ALPHA) inside it, with a short ramp at each inner edge so
    the hard zone doesn't meet the surrounding soft zone at a visible hard
    seam. Never smaller than a flat 0/alpha step if the range is too short
    to fit both transitions."""
    if hard_bottom <= hard_top or not (hard_top <= y < hard_bottom):
        return 0
    span = hard_bottom - hard_top
    t = min(transition, span // 2) if span > 1 else 0
    if t > 0 and y < hard_top + t:
        return alpha * (y - hard_top + 1) / (t + 1)
    if t > 0 and y >= hard_bottom - t:
        return alpha * (hard_bottom - y) / (t + 1)
    return alpha


def render_band_layer(size, decision, color=BAND_COLOR, soft_alpha=BAND_ALPHA,
                       hard_alpha=HARD_ALPHA, top_feather=BAND_TOP_FEATHER_PX,
                       bottom_feather=BAND_BOTTOM_FEATHER_PX,
                       hard_transition=HARD_TRANSITION_PX):
    """A cell-sized RGBA layer covering rows [0, decision.band_bottom):
    per-row alpha is max(soft profile, hard profile) -- see
    _soft_alpha_at/_hard_alpha_at. Rows inside decision.hard_range (real
    detected ink, or the whole zone on fallback) render fully opaque
    (hard_alpha); every other row in [0, band_bottom) is genuinely
    translucent (soft_alpha, feathered at the very top/bottom edges).
    Everything at y >= band_bottom stays fully transparent, which is what
    keeps the pixel-preservation gate meaningful: nothing outside the box
    the gate checks is ever painted."""
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    px = layer.load()
    content_bottom = max(0, min(decision.content_bottom, h))
    band_bottom = max(content_bottom, min(decision.band_bottom, h))
    hard_top, hard_bottom = decision.hard_range
    hard_top = max(0, min(hard_top, content_bottom))
    hard_bottom = max(hard_top, min(hard_bottom, content_bottom))
    for y in range(band_bottom):
        soft = _soft_alpha_at(y, content_bottom, band_bottom, soft_alpha,
                               top_feather, bottom_feather)
        hard = _hard_alpha_at(y, hard_top, hard_bottom, hard_alpha, hard_transition)
        a = round(min(255, max(soft, hard)))
        for x in range(w):
            px[x, y] = (color[0], color[1], color[2], a)
    return layer


def bake_cell(cell, lines, font, jp_title=None):
    """cell: CELL_W x CELL_H RGBA image (one card's thumbnail+title).
    Returns (new_cell, decision): new_cell has a cover band composited over
    rows [0, decision.band_bottom) -- fully opaque over decision.hard_range
    (the real detected ink), genuinely translucent elsewhere in that span --
    with the new zh caption drawn on top; every pixel at
    y >= decision.band_bottom is byte-identical to `cell`."""
    decision = decide_band(cell, lines, font, jp_title=jp_title)
    band = render_band_layer(cell.size, decision)
    text = render_text_layer(cell.size, lines, font)
    new_cell = Image.alpha_composite(cell.convert("RGBA"), band)
    new_cell = Image.alpha_composite(new_cell, text)
    return new_cell, decision


def find_outside_box_diffs(orig_cell, new_cell, box):
    """Return list of (x,y) pixels OUTSIDE box where orig_cell != new_cell.
    Empty list == the non-covered-region-preserved invariant holds for this
    cell. `box` is the PER-CELL band region (0, 0, CELL_W, band_bottom) --
    dynamic, not a fixed constant -- this is the pixel-preservation safety
    gate; it must actually be called (and asserted empty) by the baking
    pipeline, not just exist."""
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


def bake_sheet(sheet_num, titles, font, titles_jp=None):
    """Return (new_sheet_image, per_cell_diffs, per_cell_decisions).
    `titles_jp` (card -> original jp caption) enables the title-length line
    rule in decide_band; loaded from skeleton/cards.jp.yaml when omitted.
    per_cell_diffs maps card -> list of outside-band-region pixel diffs
    (should be [] for every card). per_cell_decisions maps card ->
    BandDecision (used to build the ink-fallback report and band-height
    stats)."""
    if titles_jp is None:
        titles_jp = load_titles_jp()
    path = os.path.join(PLOT_DIR, f"plot_{sheet_num}_a.png")
    sheet = Image.open(path).convert("RGBA")
    new_sheet = sheet.copy()
    diffs = {}
    decisions = {}
    lo = (sheet_num - 1) * CARDS_PER_SHEET + 1
    hi = min(sheet_num * CARDS_PER_SHEET, NUM_CARDS)
    for card in range(lo, hi + 1):
        _, box = cell_box(card)
        cell = sheet.crop(box)
        lines, truncated = wrap_title(titles[card], font)
        new_cell, decision = bake_cell(cell, lines, font, jp_title=titles_jp[card])
        check_box = (0, 0, CELL_W, decision.band_bottom)
        d = find_outside_box_diffs(cell, new_cell, check_box)
        diffs[card] = d
        decisions[card] = decision
        new_sheet.paste(new_cell, box)
    return new_sheet, diffs, decisions


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


# Cells hand-picked to stress the riskiest parts of the new pipeline for
# human review -- see the report for why each one was picked. Intentionally
# NOT "the nicest-looking cells": card 162 is the one real ink-detection
# failure in the whole 195-card set (falls back), 6/25 are the two real
# cells that prove decide_band's max() actually matters in both directions,
# 59/195/101 are bright-background cells (pool water / sky / paper) chosen
# because bright backgrounds are the ink-detector's main false-positive
# risk, 115 is the darkest cell in the set (near-black scene, a different
# failure mode risk), 170 is a real cell whose second wrapped line is short
# enough that the ink band should visibly NOT reach the old fixed 28px, 180
# is the longest 2-line JP title (worst-case coverage need), 9 is a short
# single-line cell chosen to show how much background area a short caption
# now gets back compared to the old fixed-28 approach.
#
# 56 was prepended 2026-08-08 when wrap_title migrated to tools/zh_wrap.py's
# word-boundary-aware DP wrapper: it's the user-reported bad case (old
# greedy split "回荡在走廊的声" / "音" -- "声音" torn apart mid-word, with
# an orphan trailing "音"). Kept first for visibility. See
# build/plot_zh/_wrap_diff.md for the full before/after table across all
# 195 titles, and build/plot_zh/_card56_before_after.png for a dedicated
# side-by-side render of this specific card under the old vs new algorithm.
CELLZOOM_CARDS = [56, 162, 6, 25, 59, 195, 101, 115, 170, 180, 9]
CELLZOOM_SCALE = 6


def build_cellzoom_image(titles, font, cards=CELLZOOM_CARDS, scale=CELLZOOM_SCALE):
    """Two rows per card: original cell (top) and baked cell (bottom),
    each scaled up `scale`x with nearest-neighbor, labeled with the card
    number and its fallback status. This is the primary artifact a human
    reviews the band-sizing decisions against."""
    sheets_cache = {}

    def get_sheet(n):
        if n not in sheets_cache:
            sheets_cache[n] = Image.open(
                os.path.join(PLOT_DIR, f"plot_{n}_a.png")).convert("RGBA")
        return sheets_cache[n]

    cell_disp_w = CELL_W * scale
    cell_disp_h = CELL_H * scale
    label_h = 14
    gap = 8
    col_w = cell_disp_w + gap
    row_h = label_h + cell_disp_h * 2 + gap
    n = len(cards)
    cols = 5
    rows = (n + cols - 1) // cols
    canvas_w = cols * col_w + gap
    canvas_h = rows * row_h + gap
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)

    for i, card in enumerate(cards):
        sheet_num, box = cell_box(card)
        cell = get_sheet(sheet_num).crop(box)
        lines, _truncated = wrap_title(titles[card], font)
        new_cell, decision = bake_cell(cell, lines, font)

        col = i % cols
        row = i // cols
        x = gap + col * col_w
        y = gap + row * row_h

        tag = "FALLBACK" if decision.fallback else f"content={decision.content_bottom} band={decision.band_bottom}"
        d.text((x, y), f"#{card} {titles[card][:8]} [{tag}]", fill=(255, 255, 0, 255))
        y2 = y + label_h
        canvas.paste(cell.resize((cell_disp_w, cell_disp_h), Image.NEAREST), (x, y2))
        canvas.paste(new_cell.resize((cell_disp_w, cell_disp_h), Image.NEAREST),
                     (x, y2 + cell_disp_h))
        # marker lines on both rows: cyan = content_bottom (must-cover, full
        # alpha up to here), magenta = band_bottom (cosmetic feather ends
        # here) -- makes the two zones visible against the art.
        for dy_off in (0, cell_disp_h):
            cy = y2 + dy_off + decision.content_bottom * scale
            d.line([(x, cy), (x + cell_disp_w, cy)], fill=(0, 255, 255, 200), width=1)
            fy = y2 + dy_off + decision.band_bottom * scale
            d.line([(x, fy), (x + cell_disp_w, fy)], fill=(255, 0, 255, 160), width=1)

    return canvas


def run(write=True, with_cellzoom=None):
    if with_cellzoom is None:
        with_cellzoom = write
    font = _ui_truetype("plot", FONT_SIZE)
    titles = load_titles_zh()
    overflow = collect_overflow(titles, font)

    new_sheets = []
    orig_sheets = []
    all_diffs = {}
    all_decisions = {}
    for sheet_num in range(1, NUM_SHEETS + 1):
        new_sheet, diffs, decisions = bake_sheet(sheet_num, titles, font)
        new_sheets.append(new_sheet)
        orig_sheets.append(Image.open(os.path.join(PLOT_DIR, f"plot_{sheet_num}_a.png")).convert("RGBA"))
        all_diffs.update(diffs)
        all_decisions.update(decisions)

    bad_cells = [c for c, d in all_diffs.items() if d]
    fallbacks = collect_ink_fallbacks(all_decisions)
    band_bottoms = {c: d.band_bottom for c, d in all_decisions.items()}

    # MUST be surfaced whenever any fallback occurred -- see
    # build_ink_fallback_coverage_note's docstring and the
    # FALLBACK_BAND_BOTTOM-removal note above decide_band. Never let this go
    # silent.
    ink_fallback_coverage_note = build_ink_fallback_coverage_note(fallbacks)

    report = {
        "num_cards": NUM_CARDS,
        "overflow": [{"card": c, "title_zh": t, "lines": l} for c, t, l in overflow],
        "pixel_preservation_violations": bad_cells,
        "ink_fallback_cards": [{"card": c, "reason": r} for c, r in fallbacks],
        "ink_fallback_coverage_note": ink_fallback_coverage_note,
        "ink_detection_summary": {
            "total": NUM_CARDS,
            "detected": NUM_CARDS - len(fallbacks),
            "fallback": len(fallbacks),
        },
        "band_bottom_min": min(band_bottoms.values()),
        "band_bottom_max": max(band_bottoms.values()),
        # 行数规则纠正了像素检测的格（2026-09-07 起）：第二行漏检/半漏的卡
        "line_rule_overrides": sorted(c for c, d in all_decisions.items()
                                      if d.line_rule == "override"),
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        for i, sheet in enumerate(new_sheets, start=1):
            sheet.convert("RGBA").save(os.path.join(OUT_DIR, f"plot_{i}_a.png"))
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
        print(f"  card {o['card']}: {o['title_zh']!r} -> {o['lines']!r}")
    s = report["ink_detection_summary"]
    print(f"ink detection: {s['detected']}/{s['total']} cells detected, "
          f"{s['fallback']} fell back to caption-only band coverage")
    if report["ink_fallback_cards"]:
        print("  fallback cards (MUST be reviewed by a human -- band height "
              "for these was never measured against real ink, only against "
              "the zh caption's own rendered height):")
        for f in report["ink_fallback_cards"]:
            print(f"    card {f['card']}: {f['reason']}")
        print(f"  ⚠ {report['ink_fallback_coverage_note']}")
    print(f"band_bottom range: {report['band_bottom_min']}..{report['band_bottom_max']}")
    print(f"pixel-preservation violations: {len(report['pixel_preservation_violations'])}")
    if report["pixel_preservation_violations"]:
        print(f"  cards: {report['pixel_preservation_violations']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
