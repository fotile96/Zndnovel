#!/usr/bin/env python3
"""Bake Chinese captions into png/select/sel_map_1_a.png -- the 探索地图
10-location x on/off label grid (comSelectMap's `v0` table, see
lua_scripts/snr_common.lua:2631-2640).

## Domain

CLAUDE.md's "探索场景" section: `comSelectMap` shows a school map with 10
clickable points (美術室/音楽室/保健室/職員室/中庭/校庭/教室/屋上/廊下/
図書室). `sel_map_1_a.png` is the single baked-text asset backing all 10
points' on/off (selected/unselected) label chips -- unlike png/select/'s 134
250x26 buttons (one file per button per state), this is ONE 240x260 sheet
containing all 20 cells (10 locations x 2 states) in a fixed grid, so this
module -- unlike tools/bake_select.py -- bakes one composite image, not a
directory of same-shaped files.

## Reuse note (this round's instruction: "尽量复用 tools/bake_select.py 的
   既有机制，不要另起一套")

The overflow/wrap/plan machinery in tools.bake_select is already
box-parametrized (measure_ink_extent, _fits, build_render_plan,
find_outside_box_diffs all take `box`/`max_width` as arguments, not baked-in
globals) -- this module imports and reuses those functions directly with its
own grid geometry passed in, rather than reimplementing the cascade/overflow
logic. Only render_text_layer/bake_button are NOT reused: those two read
tools.bake_select's own STROKE_BY_VARIANT/FILL_BY_VARIANT module globals
(measured from 250x26 *button* assets), which this module's own fresh
measurement (see MEASURE below) found to be numerically different for this
asset (off fill alpha 128 here vs 129 there, border ring alpha 192 vs 193,
and -- more importantly -- this asset's OFF-variant stroke pixels never
reach alpha==255 at all, see MEASURE below) -- so this module has its own
small local render_text_layer/bake_cell using its own measured colors,
following the identical direct-overwrite-not-alpha-composited pattern as
tools.bake_scene.bake_cell / tools.bake_select.bake_button (same reasoning:
alpha-compositing new text over the old JP glyph's opaque pixels would ghost
the old ink through instead of replacing it).

## Grid: measured fresh this round, not copied from
   build/select_layout_spec.md's un-gridded content-only read

build/select_layout_spec.md section 4.3 (prior round) read the 10 location
names off this file but explicitly did NOT do pixel-level grid measurement
("本轮未做像素级网格测绘，只完成了内容读图"). This module supplies that
missing measurement:

- 240x260 P-mode image, RGBA after convert.
- 2 columns (GRID_COLS) x 10 rows (GRID_ROWS) of 120x26 cells (measured:
  120*2==240, 26*10==260 exactly, no remainder/padding row).
- Each cell has the SAME 3px picture-frame border + flat interior fill as
  tools.bake_select's 250x26 buttons (measured independently on THIS file,
  see MAP_FILL/MAP_BORDER below) -- interior x in [x0+3, x0+116] i.e. 114px
  wide, y in [y0+3, y0+22] i.e. 20px tall, identical proportions to the
  button asset because this is the same template engine, just a narrower
  cell.
- Row parity IS the on/off state: even row index (0,2,4,6,8) = "on"
  (selected, orange/red), odd row index (1,3,5,7,9) = "off" (unselected,
  translucent-black/blue) -- verified against the real fill colors for
  every one of the 20 real cells (test_bake_select_map.py pins this).
- loc_idx = row // 2 picks WHICH of the column's 5 locations; column 0 =
  GRID_LOCATIONS_LEFT, column 1 = GRID_LOCATIONS_RIGHT (5 each). This mapping
  is the module's single highest-stakes constant -- see "MAPPING GROUND
  TRUTH" below for how it is independently pinned, not just asserted.

## MAPPING GROUND TRUTH: two independent checks, not one

A row/column mis-mapping here silently swaps which Chinese caption lands on
which real location (e.g. "美术室" baked where "音乐室" should be) --
CLAUDE.md's task brief calls this out explicitly as the "承重点" (load-
bearing point) of this whole asset. Two independent proofs back
GRID_LOCATIONS_LEFT/RIGHT:

1. **Visual**: this round's agent directly read an upscaled crop of the real
   asset (all 20 cells) and confirmed, character by character, left column
   top-to-bottom = 美術室/音楽室/保健室/職員室/中庭, right column =
   校庭/教室/屋上/廊下/図書室 -- this is what GRID_LOCATIONS_LEFT/RIGHT
   below encode.
2. **Mechanical, regression-proof**: `lua_order_from_source()` re-parses
   `lua_scripts/snr_common.lua`'s `v0.<key> = <N>` assignments (the actual
   `comSelectMap` location table CLAUDE.md documents) fresh every call, and
   `tests/test_bake_select_map.py::test_grid_locations_match_lua_v0_table`
   asserts GRID_LOCATIONS_LEFT+RIGHT (in order) equals that freshly-parsed
   N=1..10 order. This is the check that actually re-runs on every test
   invocation and would fail loudly if this module's hardcoded list ever
   drifted from the lua source of truth (or was mutated) -- the human visual
   read above cannot re-run itself automatically, this can.

A third, weaker corroboration (real-ink-width vs predicted-width for each
of the 10 known jp strings, same technique as tools/select_layout.py) is
also computed by verify_ink_widths() and asserted in the tests, but is
DISCLOSED as weak here: several of the 10 words share the same character
count (美術室/音楽室/保健室/職員室 are all 3 chars; 中庭/校庭/教室/屋上/廊下
are all 2 chars), so a same-length swap within either group would NOT be
caught by width alone. It is kept as a sanity net for length-changing
mistakes (e.g. a full row-pair shift), not relied on as the sole guard.

## MEASURE: colors, all read from THIS file, not inherited from bake_select

- MAP_FILL: on=(235,164,128,255), off=(0,0,0,128) -- close to but NOT
  byte-identical to tools.bake_select's button constants (129 vs 128 alpha
  for off) -- measured fresh, per this round's "no assuming" rule.
- MAP_STROKE: on=(209,89,85,255) (fully opaque, red-leaning); off=
  (84,89,144,236) (alpha 236, NOT 255 -- see measure_stroke_colors()'s
  docstring for why this module does not require alpha==255 the way
  tools.bake_select.measure_ink_colors does: doing so here would find ZERO
  qualifying off-variant pixels and raise, because this asset's off-state
  stroke genuinely never reaches full opacity anywhere in the real file).
- Ink fill (glyph interior): pure white (255,255,255,255), both variants,
  fully opaque -- asserted, matches tools.bake_select's convention.

## TEXT_BOX: derived by the same formula as tools.bake_select's button
   TEXT_BOX, independently re-run on this cell's own measured geometry

Interior is x in [3,116] (114px), y in [3,22] (20px) per cell (local coords,
origin = cell's own top-left). Real JP ink across all 20 cells clusters
tightly: x in [30,38]..[77,88] (well inside interior), y in [3,3]..[22,22]
(every single one of the 20 real cells hits EXACTLY y0=3,y1=22 -- tighter
than tools.bake_select's button spread, because these are all dense
info/kanji-heavy short labels). Horizontal ink-center clusters at
x in [59.0,60.0] (mean 59.2), matching the interior's own geometric center
(3+116)/2=59.5 -- so, following tools.bake_select's exact derivation
recipe: half-width = min(59.5 - ICON_LEFT_BOUND, 116 - 59.5) where
ICON_LEFT_BOUND=15 (5px clear of the real transparent icon notch at
x in [5,10], same absolute pixel range as tools.bake_select's button icon
notch -- same template). min(44.5, 56.5) = 44.5 -> MAP_TEXT_BOX =
(15, 3, 104, 23), width 89px (cell-local coordinates; add col*120 for the
absolute box of a given cell).

## Font-size cascade: [18, 17], same tiers as the button module, picked
   independently from THIS box's real-ink measurement (not inherited)

All 10 zh candidates measured via measure_ink_extent() at [18,17]: 9/10 fit
at 18px; 走廊 ("corridor") overflows the box's TOP edge by 1px at 18px
(y0=2 < box y0=3) and falls back to 17px, where all 10 fit with margin. See
the report for the full per-candidate numbers.
"""
import argparse, json, os, re, sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.bake_select import (
    FONT_PATH, STROKE_WIDTH, TEXT_FILL_COLOR, _fits, build_render_plan,
    find_outside_box_diffs, load_fonts, measure_ink_extent,
    resolve_fonts_by_button,
)

SELECT_DIR = os.path.join(REPO, "png", "select")
OUT_DIR = os.path.join(REPO, "build", "select_zh")
DATA_MAP_ZH = os.path.join(REPO, "data", "select_map_zh.jsonl")
LUA_COMMON = os.path.join(REPO, "lua_scripts", "snr_common.lua")

SOURCE_IMAGE = os.path.join(SELECT_DIR, "sel_map_1_a.png")
SHEET_W, SHEET_H = 240, 260

GRID_CELL_W, GRID_CELL_H = 120, 26
GRID_COLS, GRID_ROWS = 2, 10

# See module docstring "MAPPING GROUND TRUTH" -- pinned by an independent
# lua-source cross-check in tests, not just eyeballed once and trusted.
GRID_LOCATIONS_LEFT = ["art", "music", "health", "staffRoom", "court"]
GRID_LOCATIONS_RIGHT = ["ground", "class", "roof", "corridor", "library"]

BORDER_FRAME = 3
ICON_LEFT_BOUND = 15   # 5px clear of the real transparent icon notch (x in [5,10])

# Cell-local (add col*GRID_CELL_W for the absolute box of a given cell).
# See module docstring "TEXT_BOX" section for the derivation.
MAP_TEXT_BOX = (15, 3, 104, 23)
MAP_MAX_TEXT_W = MAP_TEXT_BOX[2] - MAP_TEXT_BOX[0]   # 89
MAP_MAX_LINES = 1

MAP_FONT_CASCADE = [18, 17]

MAP_FILL_BY_VARIANT = {
    "on": (235, 164, 128, 255),
    "off": (0, 0, 0, 128),
}


def location_for(col, row):
    idx = row // 2
    return (GRID_LOCATIONS_LEFT if col == 0 else GRID_LOCATIONS_RIGHT)[idx]


def variant_for(row):
    return "on" if row % 2 == 0 else "off"


def cell_origin(col, row):
    return col * GRID_CELL_W, row * GRID_CELL_H


def absolute_box(col, row, box=MAP_TEXT_BOX):
    x0, y0 = cell_origin(col, row)
    return (x0 + box[0], y0 + box[1], x0 + box[2], y0 + box[3])


def all_cells():
    """[(col, row, location_key, variant), ...] for all 20 real cells."""
    return [
        (col, row, location_for(col, row), variant_for(row))
        for row in range(GRID_ROWS)
        for col in range(GRID_COLS)
    ]


# ---------------------------------------------------------------------------
# 0. Ground truth: lua v0 table order, re-parsed fresh every call.
# ---------------------------------------------------------------------------

def lua_order_from_source(lua_path=LUA_COMMON):
    """Re-parses `v0.<key> = <N>` assignments (comSelectMap's location
    table, CLAUDE.md's 探索场景 section) from the real lua source, returns
    the 10 keys sorted by N (1..10). Never trusts a cached/prior-round
    transcription -- reads the file fresh every call, per this round's "no
    assuming, no trusting caches" rule, and is the check that actually
    re-runs on every test invocation (see module docstring)."""
    expected_keys = set(GRID_LOCATIONS_LEFT) | set(GRID_LOCATIONS_RIGHT)
    with open(lua_path, encoding="utf-8") as f:
        src = f.read()
    # Restricted to the 10 known comSelectMap location keys, NOT a bare
    # "v0\.\w+ = \d+" scan -- snr_common.lua has other unrelated `v0.X = N`
    # assignments elsewhere (e.g. `v0.startMenuState = 0` at line ~1160)
    # that would otherwise pollute a positional "first 10 matches" read.
    pairs = re.findall(r"v0\.(\w+)\s*=\s*(\d+)", src)
    by_n = {}
    for key, n in pairs:
        if key in expected_keys:
            by_n[int(n)] = key
    missing = [n for n in range(1, 11) if n not in by_n]
    if missing:
        raise RuntimeError(
            f"lua_order_from_source: v0 table missing N={missing} in its "
            f"first 10 assignments -- cannot derive a total order")
    return [by_n[n] for n in range(1, 11)]


# ---------------------------------------------------------------------------
# 1. Coverage.
# ---------------------------------------------------------------------------

def load_zh_source(path=DATA_MAP_ZH):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def compute_coverage():
    """Returns (covered: {key: {"jp","zh"}}, missing: [key]). All 10 keys
    from GRID_LOCATIONS_LEFT+RIGHT must be covered by data/select_map_zh.jsonl
    or this is a hard failure -- mirrors tools.bake_select.compute_coverage's
    "never silently skip" contract."""
    expected = set(GRID_LOCATIONS_LEFT) | set(GRID_LOCATIONS_RIGHT)
    # NOTE: pass DATA_MAP_ZH explicitly (module-global lookup at call time)
    # rather than relying on load_zh_source's own default argument -- default
    # argument values are bound once at function-definition time, so a test
    # that monkeypatches bsm.DATA_MAP_ZH afterwards would otherwise silently
    # have no effect here.
    rows = load_zh_source(DATA_MAP_ZH)
    covered = {}
    for r in rows:
        k = r["key"]
        if k not in expected:
            raise ValueError(
                f"{DATA_MAP_ZH} references unknown location key {k!r} -- "
                f"not among the 10 real comSelectMap locations")
        covered[k] = {"zh": r["zh"], "jp": r["jp"]}
    missing = sorted(expected - set(covered))
    return covered, missing


# ---------------------------------------------------------------------------
# 2. Render-plan (reuses tools.bake_select's box-parametrized machinery).
# ---------------------------------------------------------------------------

def build_map_render_plan(texts, fonts_by_size):
    return build_render_plan(
        texts, fonts_by_size, cascade=MAP_FONT_CASCADE, box=MAP_TEXT_BOX,
        max_width=MAP_MAX_TEXT_W, max_lines=MAP_MAX_LINES)


# ---------------------------------------------------------------------------
# 3. Stroke-color measurement -- real full population (all 5 on-cells / all
#    5 off-cells of the real, still-untouched source image), not a sample.
# ---------------------------------------------------------------------------

def measure_stroke_colors(img):
    """Scans every real cell's MAP_TEXT_BOX region (5 "on" cells, 5 "off"
    cells -- the TRUE full population for this single-sheet asset, not a
    subsample as tools.bake_select.measure_ink_colors uses for its 134-file
    button set) and returns {"on": stroke_rgba, "off": stroke_rgba}.

    Deliberately does NOT require alpha==255 the way
    tools.bake_select.measure_ink_colors does: this asset's "off" variant
    stroke pixels never reach full opacity anywhere in the real file (most
    common opaque-ish off stroke color measured is (84,89,144,236), alpha
    236) -- requiring alpha==255 here would find zero qualifying pixels and
    (correctly) raise, so instead this only excludes alpha==0 (fully
    transparent) and the known fill/ink-white colors, keeping the semi-
    transparent stroke pixels that are this asset's genuine ink."""
    from collections import Counter
    px = img.load()
    counters = {"on": Counter(), "off": Counter()}
    for col, row, _key, variant in all_cells():
        bx0, by0, bx1, by1 = absolute_box(col, row)
        bg = MAP_FILL_BY_VARIANT[variant]
        for y in range(by0, by1):
            for x in range(bx0, bx1):
                c = px[x, y]
                if c[3] == 0 or c == bg or c == TEXT_FILL_COLOR:
                    continue
                counters[variant][c] += 1
    result = {}
    for variant, counter in counters.items():
        if not counter:
            raise RuntimeError(
                f"measure_stroke_colors: no ink pixels found for variant "
                f"{variant!r} across all 5 real cells -- cannot measure "
                f"stroke colour from real data")
        result[variant] = counter.most_common(1)[0][0]
    return result


def measure_fill_colors(img):
    """Verifies MAP_FILL_BY_VARIANT against the real image (background-only
    sample point outside any real ink, per the module docstring's measured
    ink-extent bound of x<=88 local -- x=112 is always background)."""
    px = img.load()
    measured = {}
    for col, row, _key, variant in all_cells():
        x0, y0 = cell_origin(col, row)
        c = px[x0 + 112, y0 + 10]
        measured.setdefault(variant, set()).add(c)
    for variant, colors in measured.items():
        if colors != {MAP_FILL_BY_VARIANT[variant]}:
            raise RuntimeError(
                f"measure_fill_colors: variant {variant!r} background "
                f"sample points are not uniformly {MAP_FILL_BY_VARIANT[variant]}: "
                f"found {colors}")
    return measured


# ---------------------------------------------------------------------------
# 4. Rendering.
# ---------------------------------------------------------------------------

def render_text_layer_map(text, font, fill_color, stroke_color, size, box):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    d.text((cx, cy), text, font=font, fill=fill_color, anchor="mm",
           stroke_width=STROKE_WIDTH, stroke_fill=stroke_color)
    return layer


def bake_cell(sheet, col, row, text, font, stroke_by_variant,
              box=MAP_TEXT_BOX):
    """Direct (non-blended) rectangle overwrite of one cell's MAP_TEXT_BOX
    interior on the shared `sheet` image, in place -- same reasoning as
    tools.bake_select.bake_button (alpha-compositing over the old opaque JP
    ink would ghost it through instead of replacing it)."""
    variant = variant_for(row)
    abx0, aby0, abx1, aby1 = absolute_box(col, row, box)
    fill = MAP_FILL_BY_VARIANT[variant]
    d = ImageDraw.Draw(sheet)
    d.rectangle([abx0, aby0, abx1 - 1, aby1 - 1], fill=fill)
    local_size = (GRID_CELL_W, GRID_CELL_H)
    text_layer_local = render_text_layer_map(
        text, font, TEXT_FILL_COLOR, stroke_by_variant[variant],
        local_size, box)
    x0, y0 = cell_origin(col, row)
    sheet.alpha_composite(text_layer_local, (x0, y0))


# ---------------------------------------------------------------------------
# 5. Pixel-preservation gate (per-cell, aggregated).
# ---------------------------------------------------------------------------

def find_all_outside_box_diffs(orig, new, box=MAP_TEXT_BOX):
    """[(col,row,x,y), ...] for every real cell where a pixel OUTSIDE that
    cell's own MAP_TEXT_BOX differs between orig and new. Must be [] for a
    correct bake."""
    diffs = []
    opx, npx = orig.load(), new.load()
    for col, row, _key, _variant in all_cells():
        x0, y0 = cell_origin(col, row)
        bx0, by0, bx1, by1 = box
        for y in range(GRID_CELL_H):
            for x in range(GRID_CELL_W):
                if bx0 <= x < bx1 and by0 <= y < by1:
                    continue
                ax, ay = x0 + x, y0 + y
                if opx[ax, ay] != npx[ax, ay]:
                    diffs.append((col, row, ax, ay))
    return diffs


# ---------------------------------------------------------------------------
# 6. Zoom / compare image.
# ---------------------------------------------------------------------------

def build_zoom_image(orig, new, scale=6):
    """orig (top) vs new (bottom), all 20 real cells, labeled -- satisfies
    this round's "原图 vs 中文版，20 格全出，便于逐格核对" requirement."""
    cell_w, cell_h = GRID_CELL_W * scale, GRID_CELL_H * scale
    label_h = 12
    gap = 6
    row_h = label_h + cell_h * 2 + gap
    canvas_w = GRID_COLS * (cell_w + gap) + gap
    canvas_h = GRID_ROWS * row_h + gap
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)
    for col, row, key, variant in all_cells():
        x0, y0 = cell_origin(col, row)
        oc = orig.crop((x0, y0, x0 + GRID_CELL_W, y0 + GRID_CELL_H))
        nc = new.crop((x0, y0, x0 + GRID_CELL_W, y0 + GRID_CELL_H))
        cx = gap + col * (cell_w + gap)
        cy = row * row_h + gap
        d.text((cx, cy), f"{key} ({variant})", fill=(255, 255, 0, 255))
        cy2 = cy + label_h
        canvas.paste(oc.resize((cell_w, cell_h), Image.NEAREST), (cx, cy2))
        canvas.paste(nc.resize((cell_w, cell_h), Image.NEAREST),
                     (cx, cy2 + cell_h))
    return canvas


# ---------------------------------------------------------------------------
# 7. Top-level run().
# ---------------------------------------------------------------------------

def run(write=True):
    lua_order = lua_order_from_source()
    expected_order = GRID_LOCATIONS_LEFT + GRID_LOCATIONS_RIGHT
    if lua_order != expected_order:
        raise RuntimeError(
            f"GRID_LOCATIONS_LEFT+RIGHT {expected_order} does not match "
            f"the lua source's v0 table order {lua_order} -- refusing to "
            f"bake with a possibly-mismapped grid (this is the asset's "
            f"承重点, see module docstring)")

    covered, missing = compute_coverage()
    if missing:
        raise RuntimeError(
            f"data/select_map_zh.jsonl missing zh for {len(missing)}/10 "
            f"locations -- refusing to bake: {missing}")

    orig = Image.open(SOURCE_IMAGE).convert("RGBA")
    if orig.size != (SHEET_W, SHEET_H):
        raise RuntimeError(
            f"sel_map_1_a.png is {orig.size}, expected {(SHEET_W, SHEET_H)} "
            f"-- geometry assumptions in this module would silently misfire")

    stroke_by_variant = measure_stroke_colors(orig)
    measure_fill_colors(orig)   # raises on mismatch; return value unused here

    texts = {key: covered[key]["zh"] for key in covered}
    fonts_by_size = load_fonts(MAP_FONT_CASCADE)
    plans, fallbacks, hard_failures = build_map_render_plan(texts, fonts_by_size)
    if hard_failures:
        detail = "; ".join(
            f"{k} ({t!r}) still overflows MAP_TEXT_BOX at the smallest "
            f"configured tier ({sz}px): {info}"
            for k, t, sz, info in hard_failures
        )
        raise RuntimeError(
            f"font-size cascade {MAP_FONT_CASCADE} exhausted without "
            f"fitting {len(hard_failures)} location(s) -- refusing to "
            f"silently truncate: {detail}")

    fonts_by_key = resolve_fonts_by_button(plans, fonts_by_size)

    new_sheet = orig.copy()
    for col, row, key, _variant in all_cells():
        bake_cell(new_sheet, col, row, texts[key], fonts_by_key[key],
                  stroke_by_variant)

    diffs = find_all_outside_box_diffs(orig, new_sheet)

    fallback_records = [
        {"location": k, "font_size": size, "overflowed_at": tried,
         "reason": f"MAP_TEXT_BOX ({MAP_MAX_TEXT_W}px wide) overflow at "
                   f"{'/'.join(str(s) for s in tried)}px; stepped down to {size}px"}
        for k, size, tried in sorted(fallbacks)
    ]

    report = {
        "num_locations": len(texts),
        "grid": {"cols": GRID_COLS, "rows": GRID_ROWS,
                 "cell_w": GRID_CELL_W, "cell_h": GRID_CELL_H},
        "lua_order_check": {"expected": expected_order, "lua_order": lua_order,
                             "match": lua_order == expected_order},
        "font_size_cascade": list(MAP_FONT_CASCADE),
        "font_size_default": MAP_FONT_CASCADE[0],
        "location_font_sizes": {k: plans[k]["font_size"] for k in sorted(plans)},
        "fallbacks": fallback_records,
        "overflow": [
            {"location": k, "zh": t, "smallest_font_size": sz}
            for k, t, sz, _info in hard_failures
        ],
        "pixel_preservation_violation_count": len(diffs),
        "text_box_local": list(MAP_TEXT_BOX),
        "stroke_colors": {v: list(c) for v, c in stroke_by_variant.items()},
        "fill_colors": {v: list(c) for v, c in MAP_FILL_BY_VARIANT.items()},
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        new_sheet.save(os.path.join(OUT_DIR, "sel_map_1_a.png"))
        build_zoom_image(orig, new_sheet).save(
            os.path.join(OUT_DIR, "_map1_zoom.png"))
        with open(os.path.join(OUT_DIR, "map_manifest.json"), "w",
                  encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report, new_sheet, orig, diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                     help="bake in-memory only, don't write files")
    args = ap.parse_args()
    try:
        report, _new, _orig, diffs = run(write=not args.check)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"locations: {report['num_locations']}")
    print(f"lua order check: {report['lua_order_check']}")
    print(f"font size cascade: {report['font_size_cascade']}")
    print(f"fallbacks: {len(report['fallbacks'])}")
    for fb in report["fallbacks"]:
        print(f"  {fb['location']}: -> {fb['font_size']}px "
              f"(overflowed at {fb['overflowed_at']}px each)")
    print(f"overflow (cascade exhausted): {len(report['overflow'])}")
    for o in report["overflow"]:
        print(f"  {o['location']}: {o['zh']!r} still overflows at "
              f"smallest tier {o['smallest_font_size']}px")
    print(f"pixel-preservation violations: {report['pixel_preservation_violation_count']}")
    if diffs:
        print(f"  sample: {diffs[:5]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
