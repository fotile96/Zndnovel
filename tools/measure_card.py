#!/usr/bin/env python3
"""Layout measurement (NOT baking) for png/card/crd_<N>_<variant>.png -- the
197-file card-face image set (196 real cards "1..195,200" + one blank
template "0_d"). This is the third of the CLAUDE.md "文本载体清单" 烤字
blocks (after plot/ and scene/); see docs/ops/bake-decisions.md.

## Why this module has NO clip/grid geometry sourced from lua_scripts/

plot/ and scene/ are *sprite sheets*: multiple cards packed into one big PNG,
sliced at runtime via layerClip() using coordinates computed by a
lua_scripts/snr_common.lua loop (`plotState`/`sceneState`) -- see
build/plot_layout_spec.md and build/scene_layout_spec.md sections 1-2. That
is genuine "read the engine's own algorithm" evidence.

card/ is structurally different: each card is its OWN standalone 212x148
PNG file (`crd_<N>_<variant>.png`), loaded whole by filename. The only
runtime consumer is `ObjectCard.show(p0, p1)` (lua_scripts/snr_common.lua:
4315-4332): `layerLoad(v0.layerNo, p0)` loads the ENTIRE image as one
texture layer and moves/fades it as a single unit -- there is no
`layerClip()` call anywhere in `ObjectCard` that subdivides a card image
into title/body/right-column sub-rectangles. The three text blocks inside
a single card face (title / body paragraph / right-column section label)
are baked into the source art at production time, not composed by the
engine at runtime -- so unlike plot/scene, there is NO lua-code evidence
available for where those three internal regions sit. Pixel measurement is
the *only* available method here, not a fallback used because code-reading
"failed" -- this is stated explicitly (not glossed over) because CLAUDE.md's
"先去代码里找答案，别先去图上猜" principle is a *default*, not a directive
that applies when the very thing being measured was never expressed in
code to begin with. What IS confirmed from code: `oCard.show` receives the
whole-card filename with no sub-region clipping (grep for `layerClip` in
`ObjectCard` returns zero hits), and `cardModeSet`/`cardModeSelect`'s
`layerClip(i6, ..., ...+26, ...+15)` calls clip a DIFFERENT, unrelated
sprite sheet (`sys_11_b/c/d`, the card-picker grid icons at the bottom of
the fragment-mode card-select screen) -- not `png/card/` itself.

## Domain: 196 real cards, NOT a contiguous 1..195 range

png/card/ has 197 files: `crd_0_d.png` (a genuinely text-free blank
template -- see `is_blank_template()`/its docstring) plus 196
`crd_<N>_a.png` files for N in {1..195} UNION {200} (card 200 is an
"编外卡" outside the plotState/sceneState sprite-sheet domain -- it has no
counterpart in plot/scene at all, consistent with it being a standalone
image loaded directly by filename, never through a clip-indexed sheet).
`skeleton/cards.zh.yaml` has exactly these same 196 card numbers (verified
by `load_card_domain()`'s own assertion, not assumed) -- a clean 1:1
mapping, no orphans on either side.
"""
import argparse, glob, json, os, re, sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.zh_wrap import wrap as _zh_wrap
from tools.ui_font import resolve as _resolve_font
from tools.pipelib import display_width

CARD_DIR = os.path.join(REPO, "png", "card")
#: 字体按面可换：`ZND_UI_FONT_CARD` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷
#: Regular。面名＝card（bake_card.py 从本模块 import FONT_PATH）。详见 tools/ui_font.py——那里也记着
#: 「换字体后金标夹具会红，这是对的」。
FONT_PATH = str(_resolve_font("card"))
CARDS_ZH_PATH = os.path.join(REPO, "skeleton", "cards.zh.yaml")
CARDS_JP_PATH = os.path.join(REPO, "skeleton", "cards.jp.yaml")
SECTION_LABELS_PATH = os.path.join(REPO, "data", "card_section_labels.jsonl")
OUT_MD = os.path.join(REPO, "build", "card_layout_spec.md")

CARD_W, CARD_H = 212, 148

# ---------------------------------------------------------------------------
# Geometry -- PIXEL-MEASURED (see module docstring: no lua clip code exists
# for these internal regions). Method: scan lua_scripts/snr_common.lua's
# ObjectCard for a clip call (none found, confirmed above); then measure the
# blank template crd_0_d.png (genuinely text-free -- see is_blank_template)
# for the border/divider frame geometry, and cross-check against real cards'
# ink extents (collect_ink_bbox / line_bands below) to confirm text never
# strays outside these boxes. All half-open (x0,y0,x1,y1) with x1/y1
# exclusive, matching the scene/plot modules' convention.
# ---------------------------------------------------------------------------
# Outer black border: rows y in {8,9} (top) / {138,139} (bottom), cols
# x in {8,9} (left) / {202,203} (right) -- measured via crd_0_d.png column
# x=105 and row y=90 scans (both show (0,0,0,255) at exactly those
# coordinates, gradient background immediately inside/outside).
INTERIOR = (10, 10, 202, 138)

# Horizontal divider: a single row at y=41, color ~(187,174,165,255)
# (measured at crd_0_d.png column x=105) -- separates TITLE (above) from
# BODY+RIGHT (below). Row span measured at roughly x in [15,194] (tolerance
# +-25 per channel to account for antialiasing) -- decorative only, not used
# to derive TEXT_BOX (which is derived from ink extent instead, see below).
DIVIDER_H_Y = 41

# Vertical divider: ~3px wide band centered at x~137 (measured columns
# 136-138 all show the divider color at y=90), spanning y in [41,133]
# (stops short of the bottom border by ~5px) -- separates BODY (left) from
# RIGHT/section-label (right) column.
DIVIDER_V_X = 137

TITLE_ZONE = (10, 10, 202, DIVIDER_H_Y)         # (10,10,202,41)
BODY_ZONE = (10, DIVIDER_H_Y + 1, 136, 138)     # (10,42,136,138)
RIGHT_ZONE = (139, DIVIDER_H_Y + 1, 202, 138)   # (139,42,202,138)

# ---------------------------------------------------------------------------
# Ink detection. Text fill color measured on card 1's title as near-black
# ((12,11,10,255) is the single most common opaque dark pixel in the title
# region) -- much darker than the divider line (187,174,165) and the
# gradient background (always >=200 on at least one channel, see
# background-form section below), so a simple max(r,g,b)<thresh brightness
# gate cleanly separates ink from both background and divider without
# needing plot/'s "bright+dark-neighbor" joint criterion.
# ---------------------------------------------------------------------------
INK_DARK_THRESH = 120
INK_MIN_ALPHA = 200


def card_path(card, variant="a"):
    return os.path.join(CARD_DIR, f"crd_{card}_{variant}.png")


def load_card_domain(path=CARDS_ZH_PATH):
    """Return sorted list of card numbers from skeleton/cards.zh.yaml (the
    zh translation source of record), and separately assert it is IDENTICAL
    to the set of real crd_<N>_a.png files on disk -- never assume the two
    agree, always check (see module docstring's "clean 1:1" claim)."""
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    yaml_cards = sorted(row["card"] for row in data)

    disk_cards = sorted(
        int(m.group(1))
        for m in (re.match(r"crd_(\d+)_a\.png$", os.path.basename(p))
                   for p in glob.glob(os.path.join(CARD_DIR, "crd_*_a.png")))
        if m
    )
    if yaml_cards != disk_cards:
        only_yaml = sorted(set(yaml_cards) - set(disk_cards))
        only_disk = sorted(set(disk_cards) - set(yaml_cards))
        raise ValueError(
            f"cards.zh.yaml domain != png/card/*_a.png domain on disk: "
            f"only in yaml={only_yaml}, only on disk={only_disk}"
        )
    return yaml_cards


def is_blank_template(path=None):
    """crd_0_d.png: card 0 has NO real card face (`crd_0_a.png` does not
    exist -- card numbering in plotTitle[] starts at 1). This function
    verifies (rather than assumes) that crd_0_d.png is genuinely
    content-free: an ink scan over its TITLE/BODY/RIGHT zones must find
    zero ink pixels."""
    path = path or card_path(0, "d")
    im = Image.open(path).convert("RGBA")
    for zone in (TITLE_ZONE, BODY_ZONE, RIGHT_ZONE):
        if collect_ink_bbox(im, zone) is not None:
            return False
    return True


# ---------------------------------------------------------------------------
# Ink bbox / line-banding.
# ---------------------------------------------------------------------------

def collect_ink_bbox(im, zone, thresh=INK_DARK_THRESH, min_alpha=INK_MIN_ALPHA):
    """(x0,y0,x1,y1) inclusive bbox of dark, opaque pixels inside `zone`
    (x0,y0,x1,y1 half-open), or None if no ink pixel found."""
    x0, y0, x1, y1 = zone
    px = im.load()
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            if a >= min_alpha and max(r, g, b) < thresh:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def line_bands(im, zone, thresh=INK_DARK_THRESH, min_alpha=INK_MIN_ALPHA,
               empty_row_tolerance=1):
    """Split `zone`'s ink into horizontal line bands (rows of ink separated
    by >empty_row_tolerance fully-ink-free rows). Returns
    [(y0,y1,x0,x1), ...] in top-to-bottom order, one tuple per detected
    line/paragraph row-band. Used both to measure the original JP layout
    (pitch, per-line width) and, in tests, to sanity-check rendered output."""
    x0z, y0z, x1z, y1z = zone
    px = im.load()
    rows = []
    for y in range(y0z, y1z):
        xs = [x for x in range(x0z, x1z)
              if px[x, y][3] >= min_alpha and max(px[x, y][:3]) < thresh]
        rows.append((y, xs))
    bands, cur, empty_run = [], [], 0
    for y, xs in rows:
        if xs:
            cur.append((y, xs))
            empty_run = 0
        else:
            empty_run += 1
            if cur and empty_run > empty_row_tolerance:
                bands.append(cur)
                cur = []
    if cur:
        bands.append(cur)
    result = []
    for b in bands:
        ys = [t[0] for t in b]
        allxs = [x for t in b for x in t[1]]
        result.append((min(ys), max(ys), min(allxs), max(allxs)))
    return result


# ---------------------------------------------------------------------------
# Background-form classification. See report section on "底色形态" for the
# full evidence chain; this module keeps the two checks that must be
# re-verifiable by anyone re-running this tool, not just asserted in prose.
# ---------------------------------------------------------------------------

def border_glow_sample(im):
    """Sample 4 fixed points along the pink/red corner glow (measured on
    real cards to be alpha>0 there for every card) and return their RGB.
    Used to flag any card whose border uses a DIFFERENT hue (card 94 is the
    one known example: an orange/less-saturated glow, see
    find_border_color_outliers)."""
    px = im.load()
    pts = [(105, 5), (105, 143), (5, 74), (206, 74)]
    return [px[x, y] for x, y in pts]


def find_border_color_outliers(cards):
    """cards: iterable of card numbers. Returns [(card, sample_rgba), ...]
    for every card whose border-glow sample is NOT reasonably red/pink
    (r>150, g<60, b<60 at meaningful alpha) at at least one of the 4 sample
    points -- i.e. cards structurally different from the norm. MUST be
    surfaced, never silently dropped (same never-silent principle as
    scene/plot's ink-outlier / overflow collectors)."""
    out = []
    for card in cards:
        im = Image.open(card_path(card)).convert("RGBA")
        for r, g, b, a in border_glow_sample(im):
            if a > 30 and not (r > 150 and g < 60 and b < 60):
                out.append((card, (r, g, b, a)))
                break
    return out


# ---------------------------------------------------------------------------
# Text sources.
# ---------------------------------------------------------------------------

def load_cards_zh(path=CARDS_ZH_PATH):
    """card(int) -> {"title_zh":..., "body_zh":... (may be "")}"""
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    out = {}
    for row in data:
        out[row["card"]] = {
            "title_zh": row["title_zh"],
            "body_zh": row.get("body_zh") or "",
        }
    return out


def load_cards_jp(path=CARDS_JP_PATH):
    """card(int) -> {"title_jp":..., "body_jp":..., "section_label":...}
    for variant "a" rows only (skips card 0's "d" blank-template row)."""
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    out = {}
    for row in data:
        if row.get("variant") != "a":
            continue
        out[row["card"]] = {
            "title_jp": row["title_jp"],
            "body_jp": row.get("body_jp") or "",
            "section_label": row.get("section_label") or "",
        }
    return out


def load_section_labels_zh(path=SECTION_LABELS_PATH):
    """jp section_label string -> zh string, from data/card_section_labels.jsonl
    (20 distinct label strings, see module docstring's domain note)."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[row["jp"]] = row["zh"]
    return out


CARD_145_POEM = 145  # whole-card no-rewrap exception, see wrap_body_zh docstring


def cards_with_real_body(cards_zh):
    """Cards whose body_zh is non-empty (excludes 94, 144 -- illustration /
    blank-body special cases, see module docstring section on card 94/144)."""
    return sorted(c for c, d in cards_zh.items() if d["body_zh"])


# ---------------------------------------------------------------------------
# Wrap logic per zone. Each function returns (rendered_lines, info) where
# info always includes an "overflow" list that MUST be surfaced by callers
# -- collect_all_overflow() below is the single place that assembles every
# zone's overflow into one report structure; nothing here swallows it.
# ---------------------------------------------------------------------------
_QUOTE_LINE_RE = re.compile(r"^「[^「」]*」$")


def _measurer_for(font):
    probe = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(probe)
    return lambda s: d.textlength(s, font=font)


def wrap_title_zh(text, font, max_width, max_lines=1):
    """Title is always a single line in the source art (196/196 real cards
    show exactly one ink band in TITLE_ZONE -- see verify_title_always_single_line).
    Straight zh_wrap call, max_lines=1."""
    measurer = _measurer_for(font)
    lines, info = _zh_wrap(text, max_width, max_lines=max_lines, measurer=measurer)
    return lines, info


def wrap_body_zh(card, text, font, max_width, max_lines):
    """Body-paragraph wrap honoring the user-ruled structural exceptions
    (see module docstring / the report's "quote-line rule" section,
    independently re-verified against all 28 non-width-driven break points
    in skeleton/cards.zh.yaml -- 27/28 covered by the quote-line rule below,
    the 28th being card 145's own whole-card exception):

    1. Card 145 (nursery-rhyme meter): returned VERBATIM, split only on the
       existing `\\n`, never re-wrapped -- the three-beat lineation IS the
       content (see CLAUDE.md/task framing).
    2. Otherwise: split on `\\n\\n` into paragraphs (only card 41 has this;
       the blank line is a structural paragraph boundary and must survive).
    3. Within each paragraph, split on `\\n` into raw lines. Consecutive
       lines are merged into re-wrappable runs EXCEPT that any line
       matching `^「...」$` (a full option/quote line, e.g. "「想不起来」")
       is kept as its OWN standalone segment -- it never merges with a
       neighbor on either side. This is the rule the task asked to be
       re-verified; `tests/test_measure_card.py` pins it directly.
    4. Each run/segment is passed through tools.zh_wrap.wrap() at the given
       max_width/max_lines. Overflow (truncation) from any segment is
       reported, never dropped.

    Returns (list_of_paragraphs, info) where each paragraph is a list of
    rendered lines (already re-flowed), and info={"truncated": bool,
    "overflow_segments": [...]} -- truncated is True if ANY segment in ANY
    paragraph truncated.
    """
    if card == CARD_145_POEM:
        lines = text.split("\n")
        return [lines], {"truncated": False, "overflow_segments": [],
                          "verbatim_no_rewrap": True}

    measurer = _measurer_for(font)
    paragraphs_out = []
    truncated = False
    overflow_segments = []

    for para in text.split("\n\n"):
        raw_lines = para.split("\n")
        # Group raw_lines into segments: a quote-line is its own segment;
        # runs of non-quote lines get concatenated (their original \n was
        # width-driven, not structural) into one string to be re-wrapped.
        segments = []
        buf = []
        for line in raw_lines:
            if _QUOTE_LINE_RE.match(line):
                if buf:
                    segments.append(("prose", "".join(buf)))
                    buf = []
                segments.append(("quote", line))
            else:
                buf.append(line)
        if buf:
            segments.append(("prose", "".join(buf)))

        para_lines = []
        for kind, seg_text in segments:
            if not seg_text:
                continue
            lines, info = _zh_wrap(seg_text, max_width, max_lines=max_lines,
                                    measurer=measurer)
            para_lines.extend(lines)
            if info["truncated"]:
                truncated = True
                overflow_segments.append({
                    "card": card, "kind": kind, "text": seg_text,
                    "dropped": info["dropped"],
                })
        paragraphs_out.append(para_lines)

    return paragraphs_out, {"truncated": truncated,
                             "overflow_segments": overflow_segments}


def wrap_right_zh(card, label_zh, font, max_width, max_lines_per_segment=2):
    """Right-column section label: `label_zh` arrives PRE-SEGMENTED by `\\n`
    (from data/card_section_labels.jsonl, mirroring skeleton's jp
    section_label field 1:1) -- these are short structural units (chapter
    number / category word), not width-wrapped prose. Segments are NEVER
    merged with each other (same principle as the body's quote-line rule,
    applied to the whole zone since here every pre-existing line is
    structural, not incidentally width-fitting -- see the report's
    reasoning for why this differs from body_zh's "only quote-lines are
    structural" nuance). Each individual segment is independently passed
    through zh_wrap in case ITS OWN text overflows max_width (defensive:
    real jp segments are short, but zh could in principle run longer).

    Returns (list_of_segment_line_lists, info)."""
    measurer = _measurer_for(font)
    segments = [s for s in label_zh.split("\n") if s != ""]
    out = []
    truncated = False
    overflow_segments = []
    for seg in segments:
        lines, info = _zh_wrap(seg, max_width, max_lines=max_lines_per_segment,
                                measurer=measurer)
        out.append(lines)
        if info["truncated"]:
            truncated = True
            overflow_segments.append({"card": card, "text": seg,
                                       "dropped": info["dropped"]})
    return out, {"truncated": truncated, "overflow_segments": overflow_segments}


# ---------------------------------------------------------------------------
# Full-corpus trial-wrap passes. Each returns a report dict with an
# "overflow" list that is ALWAYS present (empty list, not an absent key,
# when nothing overflowed) -- see tests/test_measure_card.py's mutation pin
# for why this matters (a version that only populates the key when
# non-empty would silently look identical to "checked, found none" from a
# caller that does `report.get("overflow", [])`).
# ---------------------------------------------------------------------------

def trial_wrap_titles(cards_zh, font_size, max_width, cards=None):
    font = ImageFont.truetype(FONT_PATH, font_size)
    cards = cards or sorted(cards_zh)
    overflow = []
    for card in cards:
        text = cards_zh[card]["title_zh"]
        lines, info = wrap_title_zh(text, font, max_width)
        if info["truncated"]:
            overflow.append({"card": card, "text": text, "dropped": info["dropped"]})
    return {"font_size": font_size, "max_width": max_width,
            "num_cards": len(cards), "overflow": overflow}


def trial_wrap_bodies(cards_zh, font_size, max_width, max_lines, cards=None):
    font = ImageFont.truetype(FONT_PATH, font_size)
    cards = cards if cards is not None else cards_with_real_body(cards_zh)
    overflow = []
    line_count_overflow = []
    for card in cards:
        text = cards_zh[card]["body_zh"]
        paragraphs, info = wrap_body_zh(card, text, font, max_width, max_lines)
        overflow.extend(info["overflow_segments"])
        total_lines = sum(len(p) for p in paragraphs)
        if total_lines > max_lines:
            line_count_overflow.append({"card": card, "lines_used": total_lines,
                                         "max_lines": max_lines})
    return {"font_size": font_size, "max_width": max_width, "max_lines": max_lines,
            "num_cards": len(cards), "overflow": overflow,
            "line_count_overflow": line_count_overflow}


def trial_wrap_right_labels(cards_jp, section_labels_zh, font_size, max_width,
                             cards=None):
    font = ImageFont.truetype(FONT_PATH, font_size)
    cards = cards or sorted(cards_jp)
    overflow = []
    missing_label = []
    for card in cards:
        jp_label = cards_jp[card]["section_label"]
        if not jp_label:
            continue
        zh_label = section_labels_zh.get(jp_label)
        if zh_label is None:
            missing_label.append({"card": card, "jp_label": jp_label})
            continue
        _, info = wrap_right_zh(card, zh_label, font, max_width)
        overflow.extend(info["overflow_segments"])
    return {"font_size": font_size, "max_width": max_width,
            "num_cards": len(cards), "overflow": overflow,
            "missing_label": missing_label}


# ---------------------------------------------------------------------------
# Structural-break re-verification (the "28/28" claim in the task brief).
# ---------------------------------------------------------------------------

def find_structural_breaks(cards_zh, max_width_units=24, skip_cards=(CARD_145_POEM,)):
    """Independent re-derivation of build/cards_rewrap_report.md's method:
    for every card's body_zh, split on \\n\\n into paragraphs, then for
    every adjacent raw-line pair within a paragraph, flag it as a
    "structural" (non-width-driven) break if the two lines' DISPLAY WIDTHS
    (tools.pipelib.display_width, half-width=1/full-width=2 units -- NOT
    pixel width) sum to <= max_width_units: if they'd have fit on one line
    under the ORIGINAL 24-unit budget the skeleton was authored against,
    the fact that they're on separate lines in the source means a human
    chose to split them, not that the width forced it.

    `skip_cards`: cards excluded from this scan entirely (card 145's poem
    meter is its own documented exception, not part of the "27 covered by
    the quote-line rule" count -- see quote_line_rule_coverage())."""
    breaks = []
    for card, d in cards_zh.items():
        if card in skip_cards:
            continue
        body = d["body_zh"]
        if not body:
            continue
        for para in body.split("\n\n"):
            lines = para.split("\n")
            for i in range(len(lines) - 1):
                a, b = lines[i], lines[i + 1]
                if display_width(a) + display_width(b) <= max_width_units:
                    breaks.append({"card": card, "line_a": a, "line_b": b})
    return breaks


def quote_line_rule_coverage(breaks):
    """For each structural break found by find_structural_breaks(), check
    whether at least one side is a full `「...」` line. Returns
    (covered_count, not_covered_list) -- not_covered MUST be surfaced, never
    silently dropped (this is the exact number the task asked to be
    re-verified: expect 27 covered / 0 not-covered among the 21 non-145
    cards, i.e. 27/27 -- card 145 itself is excluded from this scan by
    find_structural_breaks's default skip_cards and handled as its own
    documented whole-card exception, together making the "28/28" total the
    task brief describes)."""
    covered = 0
    not_covered = []
    for b in breaks:
        if _QUOTE_LINE_RE.match(b["line_a"]) or _QUOTE_LINE_RE.match(b["line_b"]):
            covered += 1
        else:
            not_covered.append(b)
    return covered, not_covered


# ---------------------------------------------------------------------------
# Report assembly / CLI.
# ---------------------------------------------------------------------------

def run():
    cards = load_card_domain()
    cards_zh = load_cards_zh()
    cards_jp = load_cards_jp()
    section_labels_zh = load_section_labels_zh()

    blank_ok = is_blank_template()
    border_outliers = find_border_color_outliers(cards)

    breaks = find_structural_breaks(cards_zh)
    covered, not_covered = quote_line_rule_coverage(breaks)
    # card 145's own break (excluded from `breaks` by default skip_cards)
    # re-included here explicitly so the "28 total" figure is reproducible
    # from this one function rather than asserted in prose.
    poem_body = cards_zh[CARD_145_POEM]["body_zh"]
    poem_lines = poem_body.split("\n")
    poem_breaks = sum(
        1 for i in range(len(poem_lines) - 1)
        if display_width(poem_lines[i]) + display_width(poem_lines[i + 1]) <= 24
    )

    title_trial = trial_wrap_titles(cards_zh, font_size=11, max_width=176)
    body_trial = trial_wrap_bodies(cards_zh, font_size=9, max_width=110, max_lines=7)
    right_trial = trial_wrap_right_labels(cards_jp, section_labels_zh,
                                           font_size=8, max_width=53)
    right_trial_9 = trial_wrap_right_labels(cards_jp, section_labels_zh,
                                             font_size=9, max_width=53)

    report = {
        "num_cards": len(cards),
        "blank_template_verified_empty": blank_ok,
        "border_color_outliers": [{"card": c, "sample_rgba": list(rgba)}
                                   for c, rgba in border_outliers],
        "structural_breaks_total": len(breaks) + poem_breaks,
        "structural_breaks_quote_covered": covered,
        "structural_breaks_not_covered": not_covered,
        "structural_breaks_card145": poem_breaks,
        "title_trial": title_trial,
        "body_trial": body_trial,
        "right_trial_8px": right_trial,
        "right_trial_9px": right_trial_9,
    }
    return report


def _fmt_overflow_list(items, limit=50):
    if not items:
        return "（0 条）"
    lines = [f"- 卡 {it.get('card')}: {it}" for it in items[:limit]]
    if len(items) > limit:
        lines.append(f"... 其余 {len(items) - limit} 条省略（完整数据见 manifest 结构）")
    return "\n".join(lines)


def write_report_md(report, path=OUT_MD):
    md = []
    md.append("# `png/card/` 版面测绘（机械复核数据，人工报告见 SDD）\n")
    md.append(f"卡片总数: {report['num_cards']}\n")
    md.append(f"crd_0_d.png 验证为真空白模板: {report['blank_template_verified_empty']}\n")
    md.append(f"边框颜色异常卡: {report['border_color_outliers']}\n")
    md.append(f"结构性断点总数（含卡145）: {report['structural_breaks_total']}，"
              f"quote-line 规则覆盖: {report['structural_breaks_quote_covered']}，"
              f"未覆盖: {len(report['structural_breaks_not_covered'])}\n")
    md.append("## 标题溢出\n")
    md.append(_fmt_overflow_list(report["title_trial"]["overflow"]) + "\n")
    md.append("## 正文溢出\n")
    md.append(_fmt_overflow_list(report["body_trial"]["overflow"]) + "\n")
    md.append("## 正文行数超限\n")
    md.append(_fmt_overflow_list(report["body_trial"]["line_count_overflow"]) + "\n")
    md.append("## 右栏溢出 @8px\n")
    md.append(_fmt_overflow_list(report["right_trial_8px"]["overflow"]) + "\n")
    md.append("## 右栏溢出 @9px\n")
    md.append(_fmt_overflow_list(report["right_trial_9px"]["overflow"]) + "\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print full report as JSON")
    args = ap.parse_args()
    report = run()
    write_report_md(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"cards: {report['num_cards']}")
        print(f"blank template ok: {report['blank_template_verified_empty']}")
        print(f"border outliers: {report['border_color_outliers']}")
        print(f"structural breaks: {report['structural_breaks_total']} total, "
              f"{report['structural_breaks_quote_covered']} quote-covered, "
              f"{len(report['structural_breaks_not_covered'])} NOT covered")
        print(f"title overflow: {len(report['title_trial']['overflow'])}")
        print(f"body overflow (segment-level): {len(report['body_trial']['overflow'])}")
        print(f"body line-count overflow: {len(report['body_trial']['line_count_overflow'])}")
        print(f"right overflow @8px: {len(report['right_trial_8px']['overflow'])}")
        print(f"right overflow @9px: {len(report['right_trial_9px']['overflow'])}")
        print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
