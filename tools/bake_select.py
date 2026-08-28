#!/usr/bin/env python3
"""Bake Chinese captions into png/select/ option buttons (250x26 "_on"/"_off"
pairs, 134 distinct buttons = 268 real files).

## Domain

CLAUDE.md's "Story/Fragment 交替" flow shows these buttons at every branch
point (comDlgSelectItem in lua_scripts/snr_common.lua). Each button is a
flat-colour template (see LAYOUT below) baked once per game build with the
option's own caption -- there is no live text layer at runtime, so this is a
one-shot re-bake, same shape as tools/bake_scene.py's cell-baking.

## Coverage: recomputed from scratch every run, never trusted from a cache

The zh text for a button comes from up to three independently-produced
sources (see compute_coverage() below for the exact precedence and why each
layer exists):

  1. data/select_buttons_zh.jsonl -- 92 button-level rows, each hand-verified
     against the actual baked pixels (button -> jp -> zh).
  2. data/select_options_zh.jsonl -- 61 option-level rows (jp -> zh ->
     [buttons]); empirically a strict subset of (1)'s button coverage this
     round (69/69 option-covered buttons already appear in (1) with
     byte-identical jp/zh -- verified in compute_coverage()'s own consistency
     check, not assumed), but the precedence logic does not rely on that
     coincidence holding forever: any button (2) covers that (1) does not is
     still picked up.
  3. The remaining buttons: build/select_option_map.json gives a jp string
     derived from lua control-flow chasing (tools/derive_select.py), but that
     derivation method has a ~46% real error rate on its own (see
     build/select_ink_verify.json's report) -- so only jp strings whose
     predicted-vs-measured ink width independently cleared the ink-span
     check (status=="match" in that file) are used at all here. For each such
     jp, the zh translation is looked up in data/extra_translated.jsonl or
     build/extra_derived.jsonl (confidence=="exact" rows only) -- both are
     jp->zh corpora built for a different purpose (savedata/card-message
     strings) that happen to also cover many scene-title strings reused
     verbatim as button captions elsewhere in the game.

A button not resolved by any of the three layers is reported in `missing`,
never silently skipped -- run() refuses to bake anything if `missing` is
non-empty (see run()'s docstring "hard stop" note). This mirrors this
round's task instruction verbatim: "若你算出的覆盖率不是 134/134，停下来
报告，不要渲染缺字的按钮。"

## Layout: measured this round in build/select_layout_spec.md, re-verified
   here against the real assets (not copy-pasted blind)

- 250x26 canvas. A 3px picture-frame border on all four edges (measured:
  rows y in {0,1,2} and {23,24,25} and columns x in {0,1,2} and
  {247,248,249} carry the two-ring border palette across the ENTIRE width/
  height, not just a 1px hairline -- see test_border_frame_is_3px_all_sides
  for the byte-level proof). Interior (x in [3,246], y in [3,22]) is flat
  fill: off=(0,0,0,129), on=(235,164,128,255), confirmed byte-identical
  across every sampled button outside the ink region.
- A shared, non-unique transparent icon-notch at x in [5,10], y in [5,6]
  (alpha=0 in both variants, identical across every button -- see
  build/select_layout_spec.md section 1). Sits INSIDE the flat interior but
  OUTSIDE TEXT_BOX (see below), so it is preserved automatically by the
  pixel-preservation gate without needing special-case code.
- Text is horizontal+vertical centered (measured median ink-center
  (124.5, 12.5) across all 134 real buttons, sigma 0.72px -- see the spec).
  TEXT_BOX here is centered EXACTLY on that measured point and sized so a
  worst-case symmetric render can never reach the border or the icon notch:
  half-width = min(124.5-15, 246-124.5) rounds to 110px on the tighter
  (left) side -> width 220, matching the spec's own "220px 可用宽度"
  recommendation. TEXT_BOX = (15, 3, 235, 23).

## Font-size cascade: [18, 17], both tiers zero-overflow-verified against
   ACTUAL rendered ink (not just character-count estimates)

Unlike tools/bake_scene.py (whose overflow check is textlength-based, i.e.
estimates width from character advance without accounting for the drawn
stroke), this module's authoritative overflow decision is the REAL rendered
ink bounding box -- fill+stroke, same styling as the final bake -- measured
on a padded canvas (see measure_ink_extent(), same anti-clipping trick as
bake_scene.measure_vertical_extent but generalized to both axes). This
matters here specifically because TEXT_BOX's width (220px) is much closer to
the longest real candidate's width than scene/'s box was: the tightest case,
sel_s6s_110_sel_*'s "Aサクラ Bアヤノ Cユウイチ"-shaped strings (15 chars,
mixed ASCII+full-width katakana -- see the module docstring's "s6s_110"
section below), measures 217px at 18px font (already over: real measured
ink is what's checked, not the textlength estimate) and 217px... -- see the
report for the exact numbers; the point is a purely character-count-based
estimate is not precise enough here to trust without a pixel measurement.

At 18px, 20/134 buttons (all 6 s6s_110_sel_* plus 14 short-but-tall CJK
strings that clip TEXT_BOX's 20px height, not its width) fail the real-ink
check and fall back to 17px; at 17px ALL 134 buttons pass both axes with
ZERO overflow (re-verified fresh every run by build_render_plan(), never
assumed -- see run()'s hard_failures handling, same "refuse to silently
truncate" contract as tools/bake_scene.py).

## s6s_110: half-width JP source, full-width zh render -- documented, not
   silently handled

data/select_options_zh.jsonl's notes for sel_s6s_110_sel_{a..f} record that
the ORIGINAL png baked these captions in half-width (半角) katakana to save
horizontal space, and recommend the same for a re-bake; the zh field
actually stored in that jsonl, however, is standard full-width (全角)
Unicode katakana (U+30xx block, confirmed by codepoint inspection -- see the
report). This module renders exactly the zh string it is given (no
implicit half-width conversion) and lets the real-ink overflow check decide
whether that's safe -- it is, at the 17px fallback tier (measured, not
assumed) -- rather than silently substituting half-width glyphs the font may
or may not even contain. See the report for the full writeup and why this
is flagged as a candidate follow-up rather than fixed silently here.

## Pixel preservation gate

Same contract as tools/bake_scene.py's find_outside_box_diffs: every pixel
OUTSIDE TEXT_BOX must be byte-identical between the original real PNG and
the baked output. bake_button() achieves this by direct (non-blended)
rectangle overwrite of TEXT_BOX's interior, never touching anything outside
it -- see that function's docstring for why alpha_composite over the
original ink would ghost instead (same reasoning as bake_scene.bake_cell).
"""
import argparse, glob, json, os, sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.zh_wrap import wrap as _zh_wrap
from tools.ui_font import resolve as _resolve_font

SELECT_DIR = os.path.join(REPO, "png", "select")
#: 字体按面可换：`ZND_UI_FONT_SELECT` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷
#: Regular。面名＝select（bake_select_map.py 从本模块 import FONT_PATH）。详见 tools/ui_font.py——那里也记着
#: 「换字体后金标夹具会红，这是对的」。
FONT_PATH = str(_resolve_font("select"))
OUT_DIR = os.path.join(REPO, "build", "select_zh")

DATA_BUTTONS_ZH = os.path.join(REPO, "data", "select_buttons_zh.jsonl")
DATA_OPTIONS_ZH = os.path.join(REPO, "data", "select_options_zh.jsonl")
DATA_EXTRA_TRANSLATED = os.path.join(REPO, "data", "extra_translated.jsonl")
BUILD_EXTRA_DERIVED = os.path.join(REPO, "build", "extra_derived.jsonl")
BUILD_OPTION_MAP = os.path.join(REPO, "build", "select_option_map.json")
BUILD_INK_VERIFY = os.path.join(REPO, "build", "select_ink_verify.json")

CELL_W, CELL_H = 250, 26

# ---------------------------------------------------------------------------
# Geometry -- see module docstring "Layout" section for the measured
# evidence. BORDER_FRAME/ICON_ZONE_X match tools/select_layout.py's own
# constants (independently re-derived here, not imported, so a change to
# that module's measurement constants cannot silently drift this one without
# the cross-check tests in tests/test_bake_select.py noticing).
# ---------------------------------------------------------------------------
BORDER_FRAME = 3           # 3px picture-frame border on all four edges
ICON_ZONE_X = 15           # shared transparent icon-notch never reaches here
TEXT_BOX = (15, 3, 235, 23)   # (x0, y0, x1, y1); centered on measured (124.5,12.5)
MAX_TEXT_W = TEXT_BOX[2] - TEXT_BOX[0]   # 220
MAX_LINES = 1               # every real button caption is a single short line

FONT_SIZE_CASCADE = [18, 17]   # biggest first; see module docstring for the
                                 # measured 20/134 fallback set at 18px and
                                 # the 0/134 overflow re-check at 17px.

TEXT_FILL_COLOR = (255, 255, 255, 255)   # white, both variants -- measured
                                            # (see measure_ink_colors(); both
                                            # off/on samples show (255,255,
                                            # 255,255) as the ink-region's
                                            # second-most-frequent opaque
                                            # colour after the stroke tone).
STROKE_WIDTH = 1

# Flat interior fill -- measured: every sampled pixel in the interior
# (x in [3,246], y in [3,22]) OUTSIDE the detected ink region is exactly this
# constant, for every button sampled (see test_interior_fill_is_flat_*).
FILL_BY_VARIANT = {
    "off": (0, 0, 0, 129),
    "on": (235, 164, 128, 255),
}

# ---------------------------------------------------------------------------
# Stroke colour: measured from real assets at import time, NOT hardcoded --
# see measure_ink_colors() below. A small curated sample (not all 268 files,
# for speed) is scanned; if the measured colour ever drifted enough to flip
# "blue-leaning" (off) / "red-leaning" (on) to the opposite tendency, that
# would be a real asset change worth noticing, so tests pin the qualitative
# property (blue channel > red channel for off; red channel > blue channel
# for on) rather than the exact RGB triple, while still using the exact
# measured triple for rendering.
# ---------------------------------------------------------------------------
STROKE_SAMPLE_BUTTONS = [
    "sel_s1s_35_sel_a", "sel_s5s_350_sel_b", "sel_s2s_190_sel_a",
    "sel_s6s_280_sel_b", "sel_s3s_580_sel_a", "sel_s4s_100_sel_a",
]


def _button_image_path(button_base, variant):
    return os.path.join(SELECT_DIR, f"{button_base}_{variant}.png")


def measure_ink_colors(variant, sample_buttons=STROKE_SAMPLE_BUTTONS,
                        box=TEXT_BOX):
    """Scan `sample_buttons`' real `variant` ({'off','on'}) images inside
    TEXT_BOX, count every fully-opaque pixel colour that is not this
    variant's known flat interior fill, and return (fill_color,
    stroke_color): fill_color is the fixed white ink fill (verified to be
    the case, not assumed -- see the assertion below), stroke_color is the
    single most frequent remaining opaque colour (the outline around every
    glyph, which -- because outlines have more edge pixels than a thin
    CJK/kana glyph's solid interior -- consistently outnumbers the pure-white
    fill pixels in the counts, confirmed across every sample checked this
    round). Returns real measured RGBA tuples, never a hardcoded guess."""
    bg = FILL_BY_VARIANT[variant]
    counter = Counter()
    for button in sample_buttons:
        path = _button_image_path(button, variant)
        img = Image.open(path).convert("RGBA")
        px = img.load()
        for y in range(box[1], box[3]):
            for x in range(box[0], box[2]):
                c = px[x, y]
                if c[3] == 255 and c != bg:
                    counter[c] += 1
    if not counter:
        raise RuntimeError(
            f"measure_ink_colors({variant!r}): no opaque non-background "
            f"pixels found in any sample button -- cannot measure stroke "
            f"colour from real data")
    white = TEXT_FILL_COLOR
    non_white = Counter({c: n for c, n in counter.items() if c != white})
    if not non_white:
        raise RuntimeError(
            f"measure_ink_colors({variant!r}): every opaque ink pixel "
            f"sampled was pure white -- no stroke colour present in the "
            f"sample, cannot measure it (widen STROKE_SAMPLE_BUTTONS)")
    stroke_color = non_white.most_common(1)[0][0]
    return white, stroke_color


def _load_variant_colors():
    off_fill, off_stroke = measure_ink_colors("off")
    on_fill, on_stroke = measure_ink_colors("on")
    assert off_fill == TEXT_FILL_COLOR == on_fill, (
        f"measured ink fill colour is not pure white in both variants: "
        f"off={off_fill} on={on_fill}")
    return {"off": off_stroke, "on": on_stroke}


STROKE_BY_VARIANT = _load_variant_colors()


# ---------------------------------------------------------------------------
# 1. Coverage: recomputed fresh from the three source layers every run.
# ---------------------------------------------------------------------------

def real_button_bases():
    """The 134 distinct button base names (no _on/_off/.png), read fresh
    from png/select/ every call -- never trusts any cached count."""
    files = sorted(glob.glob(os.path.join(SELECT_DIR, "*.png")))
    bases = set()
    for f in files:
        im = Image.open(f)
        if im.size != (CELL_W, CELL_H):
            continue
        name = os.path.splitext(os.path.basename(f))[0]
        if name.endswith("_off"):
            bases.add(name[: -len("_off")])
        elif name.endswith("_on"):
            bases.add(name[: -len("_on")])
        else:
            raise ValueError(f"250x26 image with unexpected suffix: {f}")
    return bases


def _load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_coverage():
    """Returns (covered: {button: {"zh","jp","source"}}, missing: [button],
    evidence: {...}). Never trusts build/_select_coverage.json (a prior
    round's cached snapshot) -- recomputes every layer from its own source
    file each call, per this round's task instruction to independently
    re-verify the 134/134 claim before baking anything."""
    buttons = real_button_bases()

    src1 = _load_jsonl(DATA_BUTTONS_ZH)
    cov1 = {}
    for r in src1:
        b = r["button"]
        if b not in buttons:
            raise ValueError(
                f"{DATA_BUTTONS_ZH} references unknown button {b!r} -- "
                f"not among the {len(buttons)} real 250x26 assets")
        cov1[b] = {"zh": r["zh"], "jp": r["jp"], "source": "select_buttons_zh.jsonl"}

    src2 = _load_jsonl(DATA_OPTIONS_ZH)
    cov2 = {}
    for r in src2:
        for b in r["buttons"]:
            if b not in buttons:
                raise ValueError(
                    f"{DATA_OPTIONS_ZH} references unknown button {b!r}")
            cov2[b] = {"zh": r["zh"], "jp": r["jp"], "source": "select_options_zh.jsonl"}

    # Defensive consistency check: where src1 and src2 both cover the same
    # button, they must agree (they are two different rounds' outputs over
    # the same underlying corpus) -- a silent divergence here would mean one
    # of the two files drifted out of sync with the other without anyone
    # noticing.
    conflicts = []
    for b in set(cov1) & set(cov2):
        if cov1[b]["zh"] != cov2[b]["zh"] or cov1[b]["jp"] != cov2[b]["jp"]:
            conflicts.append(b)
    if conflicts:
        raise ValueError(
            f"select_buttons_zh.jsonl and select_options_zh.jsonl disagree "
            f"on {len(conflicts)} button(s): {sorted(conflicts)}")

    covered = dict(cov1)
    for b, rec in cov2.items():
        covered.setdefault(b, rec)

    remaining = buttons - set(covered)

    # Third layer: ink-verified-match derived jp + exact zh lookup.
    option_map = json.load(open(BUILD_OPTION_MAP, encoding="utf-8"))
    ink_verify = json.load(open(BUILD_INK_VERIFY, encoding="utf-8"))
    match_jp = {r["button"]: r["jp"] for r in ink_verify["results"]
                if r["status"] == "match" and r["button"] in remaining}

    jp2zh = {}
    for r in _load_jsonl(DATA_EXTRA_TRANSLATED):
        jp2zh.setdefault(r["jp"], set()).add(r["zh"])
    for r in _load_jsonl(BUILD_EXTRA_DERIVED):
        if r.get("confidence") == "exact":
            jp2zh.setdefault(r["jp"], set()).add(r["zh"])

    derived_conflicts = []
    for b, jp in match_jp.items():
        zh_options = jp2zh.get(jp)
        if not zh_options:
            continue  # left in `remaining` -> reported as missing below
        if len(zh_options) > 1:
            derived_conflicts.append((b, jp, sorted(zh_options)))
            continue
        covered[b] = {"zh": next(iter(zh_options)), "jp": jp,
                       "source": "derive_select.py+ink_verify.match+extra_lookup"}
    if derived_conflicts:
        raise ValueError(
            f"{len(derived_conflicts)} derived button(s) have CONFLICTING "
            f"zh candidates across extra_translated/extra_derived, refusing "
            f"to silently pick one: {derived_conflicts}")

    missing = sorted(buttons - set(covered))
    evidence = {
        "total_buttons": len(buttons),
        "src1_button_level_rows": len(src1),
        "src1_distinct_buttons": len(cov1),
        "src2_option_level_rows": len(src2),
        "src2_distinct_buttons": len(cov2),
        "src1_src2_overlap": len(set(cov1) & set(cov2)),
        "remaining_after_src1_src2": len(remaining),
        "ink_verify_match_total": sum(1 for r in ink_verify["results"] if r["status"] == "match"),
        "resolved_via_derived_layer": len(covered) - len(cov1) - sum(
            1 for b in cov2 if b not in cov1),
    }
    return covered, missing, evidence


# ---------------------------------------------------------------------------
# 2. Ink-extent measurement (both axes) -- the authoritative overflow check.
# ---------------------------------------------------------------------------

def measure_ink_extent(text, font, box=TEXT_BOX, stroke_width=STROKE_WIDTH, pad=120):
    """Render `text` centered on `box` (same anchor="mm" convention
    bake_button/render_text_layer use) onto a canvas padded well beyond any
    realistic overflow, then return the REAL rendered ink's (x0,x1,y0,y1) in
    the cell's own absolute coordinate frame, or None if no ink at all.

    Padding is deliberately generous (120px each side -- box width is only
    220px, so this comfortably covers even a wildly-oversized font used by
    accident) for the same reason bake_scene.measure_vertical_extent pads:
    PIL silently drops pixels drawn outside the canvas it was given, so an
    under-padded canvas could hide a real overflow instead of revealing it
    (see that function's docstring for the fuller explanation) -- this
    module extends the same trick to the horizontal axis too, which
    bake_scene's version does not need (its box is wide relative to any
    real title) but this module's tighter box does."""
    bw = (box[2] - box[0]) + 2 * pad
    bh = (box[3] - box[1]) + 2 * pad
    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = pad + (box[2] - box[0]) / 2
    cy = pad + (box[3] - box[1]) / 2
    d.text((cx, cy), text, font=font, fill=TEXT_FILL_COLOR, anchor="mm",
           stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255))
    bbox = layer.split()[-1].getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return (x0 - pad + box[0], x1 - pad + box[0],
            y0 - pad + box[1], y1 - pad + box[1])


def _measurer_for(font):
    probe = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(probe)
    return lambda s: d.textlength(s, font=font)


def _fits(text, font, box, max_width, max_lines):
    """A candidate (text, font) tier passes iff BOTH:
    (a) tools.zh_wrap.wrap() finds a single-line arrangement that needs no
        character-dropping (architectural consistency with every other bake_*
        module's overflow contract), AND
    (b) the REAL rendered ink (fill+stroke, same styling as the final bake)
        fits inside `box` on both axes -- the authoritative check, see
        measure_ink_extent's docstring for why (a) alone is not precise
        enough here.
    Returns (ok: bool, info: dict) where info always has enough detail to
    explain a rejection (never just a bare False)."""
    measurer = _measurer_for(font)
    lines, wrap_info = _zh_wrap(text, max_width, max_lines=max_lines, measurer=measurer)
    if wrap_info["truncated"]:
        return False, {"reason": "zh_wrap truncated", "wrap_info": wrap_info}
    extent = measure_ink_extent(text, font, box)
    if extent is None:
        return False, {"reason": "no ink detected at all"}
    x0, x1, y0, y1 = extent
    if x0 < box[0] or x1 > box[2] or y0 < box[1] or y1 > box[3]:
        return False, {
            "reason": "real ink extent exceeds TEXT_BOX",
            "extent": [x0, x1, y0, y1], "box": list(box),
        }
    return True, {"extent": [x0, x1, y0, y1]}


def load_fonts(cascade=FONT_SIZE_CASCADE):
    return {size: ImageFont.truetype(FONT_PATH, size) for size in cascade}


def build_render_plan(texts, fonts_by_size, cascade=FONT_SIZE_CASCADE,
                       box=TEXT_BOX, max_width=MAX_TEXT_W, max_lines=MAX_LINES):
    """texts: {button: str}. Walks `cascade` largest-to-smallest per button,
    same "stop at the first tier that truly fits" contract as
    tools.bake_scene.build_render_plan, but using _fits()'s real-ink check
    (see above) instead of a textlength-only estimate.

    Returns (plans, fallbacks, hard_failures) -- same shape/semantics as
    tools.bake_scene.build_render_plan (see that module for the full
    contract this mirrors): hard_failures is fatal and must stop the run
    (zero-truncation invariant), fallbacks must be surfaced everywhere
    (CLI/manifest/report), never silently absorbed into "just worked"."""
    plans, fallbacks, hard_failures = {}, [], []
    for button in sorted(texts):
        text = texts[button]
        chosen = None
        overflowed_at = []
        last_info = None
        for size in cascade:
            ok, info = _fits(text, fonts_by_size[size], box, max_width, max_lines)
            last_info = info
            if ok:
                chosen = (size, info)
                break
            overflowed_at.append(size)
        if chosen is None:
            hard_failures.append((button, text, cascade[-1], last_info))
            continue
        size, info = chosen
        plans[button] = {"font_size": size, "info": info}
        if size != cascade[0]:
            fallbacks.append((button, size, overflowed_at))
    return plans, fallbacks, hard_failures


def resolve_fonts_by_button(plans, fonts_by_size):
    return {b: fonts_by_size[p["font_size"]] for b, p in plans.items()}


# ---------------------------------------------------------------------------
# 3. Rendering.
# ---------------------------------------------------------------------------

def render_text_layer(text, font, variant, size=(CELL_W, CELL_H), box=TEXT_BOX):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    d.text((cx, cy), text, font=font, fill=TEXT_FILL_COLOR, anchor="mm",
           stroke_width=STROKE_WIDTH, stroke_fill=STROKE_BY_VARIANT[variant])
    return layer


def bake_button(cell, text, font, variant, box=TEXT_BOX):
    """cell: a real CELL_W x CELL_H RGBA crop of one button's `variant`
    image. Returns a new image: `box`'s interior is a hard (non-blended)
    rectangle overwrite to this variant's flat fill colour with the new zh
    caption drawn on top -- direct pixel replacement, not alpha-composited
    over the original ink, so the original opaque JP glyph pixels cannot
    ghost through a translucent composite (identical reasoning to
    tools.bake_scene.bake_cell). Every pixel outside `box` is byte-identical
    to `cell`."""
    new_cell = cell.convert("RGBA").copy()
    d = ImageDraw.Draw(new_cell)
    fill = FILL_BY_VARIANT[variant]
    d.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=fill)
    text_layer = render_text_layer(text, font, variant, size=cell.size, box=box)
    return Image.alpha_composite(new_cell, text_layer)


def find_outside_box_diffs(orig, new, box=TEXT_BOX):
    """Pixel-preservation safety gate: [(x,y), ...] pixels OUTSIDE `box`
    where orig != new. Must be [] for every real button/variant baked."""
    x0, y0, x1, y1 = box
    w, h = orig.size
    opx, npx = orig.load(), new.load()
    diffs = []
    for y in range(h):
        for x in range(w):
            if x0 <= x < x1 and y0 <= y < y1:
                continue
            if opx[x, y] != npx[x, y]:
                diffs.append((x, y))
    return diffs


# ---------------------------------------------------------------------------
# 4. Comparison / cellzoom images.
# ---------------------------------------------------------------------------

# Hand-picked for human review (see module docstring's rationale): the
# longest normal CJK caption, the shortest (1-char), the punctuation example
# named explicitly in this round's task ("多半吧……"), and all 6 of the
# s6s_110 half-width-JP-source buttons (the round's flagged risk case).
CELLZOOM_BUTTONS = [
    "sel_s2s_80_sel_a",       # shortest: 1 char, "去"
    "sel_s4s_170_sel_a",      # longest normal CJK incl. punctuation, 8 chars
    "sel_s2s_340_sel_b",      # punctuation example named in the task, "多半吧……"
    "sel_s6s_110_sel_a", "sel_s6s_110_sel_b", "sel_s6s_110_sel_c",
    "sel_s6s_110_sel_d", "sel_s6s_110_sel_e", "sel_s6s_110_sel_f",
]
CELLZOOM_SCALE = 8


def build_cellzoom_image(texts, fonts_by_button, plans, cards=CELLZOOM_BUTTONS,
                          scale=CELLZOOM_SCALE):
    """For each button: original off/on (top row) and baked off/on (bottom
    row), scaled up, labeled with the resolved font size and a [FALLBACK]
    tag if it landed below FONT_SIZE_CASCADE[0] -- both variants shown for
    every button (satisfies this round's "on/off 同一按钮的两态并排"
    requirement for the whole curated set, not just one pair)."""
    cell_w, cell_h = CELL_W * scale, CELL_H * scale
    label_h = 14
    gap = 10
    col_w = cell_w * 2 + gap * 3   # off + on side by side
    row_h = label_h + cell_h * 2 + gap
    canvas_w = col_w + gap
    canvas_h = len(cards) * row_h + gap
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)

    for i, button in enumerate(cards):
        y = gap + i * row_h
        size = plans[button]["font_size"]
        tag = "" if size == FONT_SIZE_CASCADE[0] else " [FALLBACK]"
        d.text((gap, y), f"{button}  {texts[button]!r} @{size}px{tag}",
               fill=(255, 255, 0, 255))
        y2 = y + label_h
        for j, variant in enumerate(("off", "on")):
            orig = Image.open(_button_image_path(button, variant)).convert("RGBA")
            new = bake_button(orig, texts[button], fonts_by_button[button], variant)
            x = gap + j * (cell_w + gap)
            canvas.paste(orig.resize((cell_w, cell_h), Image.NEAREST), (x, y2))
            canvas.paste(new.resize((cell_w, cell_h), Image.NEAREST), (x, y2 + cell_h))
            bx0, bx1 = x + TEXT_BOX[0] * scale, x + TEXT_BOX[2] * scale
            for dy in (0, cell_h):
                d.rectangle([bx0, y2 + dy, bx1, y2 + dy + cell_h - 1],
                            outline=(0, 255, 255, 200))
    return canvas


COMPARE_SAMPLE_BUTTONS = [
    "sel_s1s_35_sel_a", "sel_s1s_35_sel_b", "sel_s1s_170_sel_a",
    "sel_s2s_80_sel_a", "sel_s2s_340_sel_b", "sel_s3s_580_sel_a",
    "sel_s4s_100_sel_a", "sel_s5s_350_sel_b", "sel_s6s_150_sel_b",
    "sel_s6s_110_sel_e",
]


def build_compare_image(texts, fonts_by_button, buttons=COMPARE_SAMPLE_BUTTONS,
                         scale=4):
    cell_w, cell_h = CELL_W * scale, CELL_H * scale
    label_h = 14
    gap = 8
    row_h = label_h + cell_h * 2 + gap
    col_w = cell_w * 2 + gap * 3
    canvas = Image.new("RGBA", (col_w + gap, len(buttons) * row_h + gap), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)
    for i, button in enumerate(buttons):
        y = gap + i * row_h
        d.text((gap, y), f"{button}  JP(top) / ZH(bottom)  \"{texts[button]}\"",
               fill=(255, 255, 255, 255))
        y2 = y + label_h
        for j, variant in enumerate(("off", "on")):
            orig = Image.open(_button_image_path(button, variant)).convert("RGBA")
            new = bake_button(orig, texts[button], fonts_by_button[button], variant)
            x = gap + j * (cell_w + gap)
            canvas.paste(orig.resize((cell_w, cell_h), Image.NEAREST), (x, y2))
            canvas.paste(new.resize((cell_w, cell_h), Image.NEAREST), (x, y2 + cell_h))
    return canvas


def build_size_ab_image(texts, small_font, small_size, big_fonts_by_button,
                         plans, buttons=CELLZOOM_BUTTONS, scale=6):
    """A/B sheet: LEFT = every button forced to a single small, zero-risk
    uniform size (FONT_SIZE_CASCADE[-1], i.e. the floor the cascade never
    needs to go below); RIGHT = the actual shipped cascade result (mixed
    18px/17px, [FALLBACK]-tagged) -- lets a human directly compare "safest
    possible" against "what actually ships" on the exact buttons this round
    flagged as the hard cases (CELLZOOM_BUTTONS), mirroring
    tools/bake_scene_size_ab.py's uniform-vs-uniform comparison shape."""
    cell_w, cell_h = CELL_W * scale, CELL_H * scale
    label_h = 14
    gap = 10
    row_h = label_h + cell_h + gap
    canvas_w = cell_w * 2 + gap * 3
    canvas_h = len(buttons) * row_h + gap + 20
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)
    for i, button in enumerate(buttons):
        y = gap + i * row_h
        small_cell = bake_button(
            Image.open(_button_image_path(button, "off")).convert("RGBA"),
            texts[button], small_font, "off")
        big_size = plans[button]["font_size"]
        big_cell = bake_button(
            Image.open(_button_image_path(button, "off")).convert("RGBA"),
            texts[button], big_fonts_by_button[button], "off")
        tag = "" if big_size == FONT_SIZE_CASCADE[0] else " [FALLBACK]"
        d.text((gap, y), f"{button}  {small_size}px(left) / {big_size}px{tag}(right)",
               fill=(255, 255, 0, 255))
        y2 = y + label_h
        canvas.paste(small_cell.resize((cell_w, cell_h), Image.NEAREST), (gap, y2))
        canvas.paste(big_cell.resize((cell_w, cell_h), Image.NEAREST),
                     (gap * 2 + cell_w, y2))
    legend_y = len(buttons) * row_h + gap
    d.text((gap, legend_y),
           f"left = uniform {small_size}px (cascade floor, zero fallback risk)   "
           f"right = shipped cascade {FONT_SIZE_CASCADE} (mostly 18px, "
           f"falls back to 17px only where needed)",
           fill=(200, 200, 200, 255))
    return canvas


# ---------------------------------------------------------------------------
# 5. Top-level run().
# ---------------------------------------------------------------------------

def run(write=True, with_extras=None):
    if with_extras is None:
        with_extras = write

    covered, missing, evidence = compute_coverage()
    if missing:
        raise RuntimeError(
            f"coverage recompute found {len(missing)}/134 buttons WITHOUT a "
            f"zh source -- refusing to bake (would silently skip untranslated "
            f"buttons): {missing}"
        )

    texts = {b: covered[b]["zh"] for b in covered}
    fonts_by_size = load_fonts()
    plans, fallbacks, hard_failures = build_render_plan(texts, fonts_by_size)
    if hard_failures:
        detail = "; ".join(
            f"{b} ({t!r}) still overflows TEXT_BOX at the smallest configured "
            f"tier ({sz}px): {info}"
            for b, t, sz, info in hard_failures
        )
        raise RuntimeError(
            f"font-size cascade {FONT_SIZE_CASCADE} exhausted without "
            f"fitting {len(hard_failures)} button(s) -- refusing to "
            f"silently truncate: {detail}"
        )

    fonts_by_button = resolve_fonts_by_button(plans, fonts_by_size)

    all_diffs = {}
    baked = {}
    for button in sorted(texts):
        for variant in ("off", "on"):
            orig = Image.open(_button_image_path(button, variant)).convert("RGBA")
            new = bake_button(orig, texts[button], fonts_by_button[button], variant)
            diffs = find_outside_box_diffs(orig, new)
            all_diffs[f"{button}_{variant}"] = diffs
            baked[(button, variant)] = new

    bad = {k: d for k, d in all_diffs.items() if d}

    fallback_records = [
        {"button": b, "font_size": size, "overflowed_at": tried,
         "reason": f"TEXT_BOX ({MAX_TEXT_W}px wide) overflow at "
                   f"{'/'.join(str(s) for s in tried)}px; stepped down to {size}px"}
        for b, size, tried in sorted(fallbacks)
    ]

    report = {
        "num_buttons": len(texts),
        "coverage_evidence": evidence,
        "font_size_cascade": list(FONT_SIZE_CASCADE),
        "font_size_default": FONT_SIZE_CASCADE[0],
        "button_font_sizes": {b: plans[b]["font_size"] for b in sorted(plans)},
        "fallbacks": fallback_records,
        "overflow": [
            {"button": b, "zh": t, "smallest_font_size": sz}
            for b, t, sz, _info in hard_failures
        ],
        "pixel_preservation_violations": sorted(bad),
        "text_box": list(TEXT_BOX),
        "stroke_colors": {"off": list(STROKE_BY_VARIANT["off"]),
                           "on": list(STROKE_BY_VARIANT["on"])},
        "fill_colors": {"off": list(FILL_BY_VARIANT["off"]),
                         "on": list(FILL_BY_VARIANT["on"])},
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        for (button, variant), img in baked.items():
            img.save(os.path.join(OUT_DIR, f"{button}_{variant}.png"))
        build_compare_image(texts, fonts_by_button).save(
            os.path.join(OUT_DIR, "_compare.png"))
        if with_extras:
            build_cellzoom_image(texts, fonts_by_button, plans).save(
                os.path.join(OUT_DIR, "_cellzoom.png"))
            small_size = FONT_SIZE_CASCADE[-1]
            build_size_ab_image(texts, fonts_by_size[small_size], small_size,
                                 fonts_by_button, plans).save(
                os.path.join(OUT_DIR, "_size_ab.png"))
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
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"buttons: {report['num_buttons']}")
    print(f"coverage evidence: {report['coverage_evidence']}")
    print(f"font size cascade: {report['font_size_cascade']} "
          f"(default {report['font_size_default']}px)")
    print(f"fallbacks (buttons NOT rendered at {report['font_size_default']}px): "
          f"{len(report['fallbacks'])}")
    for fb in report["fallbacks"]:
        print(f"  {fb['button']}: -> {fb['font_size']}px "
              f"(overflowed at {fb['overflowed_at']}px each)")
    print(f"overflow (cascade exhausted): {len(report['overflow'])}")
    for o in report["overflow"]:
        print(f"  {o['button']}: {o['zh']!r} still overflows at "
              f"smallest tier {o['smallest_font_size']}px")
    print(f"pixel-preservation violations: {len(report['pixel_preservation_violations'])}")
    if report["pixel_preservation_violations"]:
        print(f"  buttons: {report['pixel_preservation_violations']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
