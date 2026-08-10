#!/usr/bin/env python3
"""Bake Chinese text into png/card/crd_<N>_a.png (196 real cards -- the
third and last of the CLAUDE.md "文本载体清单" 烤字 blocks). Layout geometry
and folding rules were measured/decided in the PRIOR round (see
tools/measure_card.py and docs/ops/bake-specs/card-layout-spec.md); this
module is the RENDER round: it (a) reconstructs a clean (text-free)
background for each card, (b) draws the title/body/right-column zh text on
top, and (c) verifies both steps never silently drop or corrupt anything.

## Why background reconstruction exists at all

Unlike png/scene/'s flat-alpha "chrome bar" (a single constant color,
tools/bake_scene.py just fills a rectangle), png/card/'s three text zones sit
on a smooth diagonal "white -> peach/orange" gradient (see
card-layout-spec.md section 3). Filling the zone with one flat color would
produce a visible color-step at the zone boundary against the untouched
divider/border. The background under the JP text must be reconstructed
before the zh text can be drawn on top of it.

## Why the reconstruction is SELF-REFERENTIAL (per-card, not per-cluster)

The obvious-looking alternative -- pick a handful of "style clusters" and
reconstruct every member of a cluster from a shared/borrowed template (the
blank crd_0_d.png, or another card's pixels, or a cluster-average) -- was
tried conceptually and rejected after actually measuring the data (see
`cluster_report()` / the SDD report's clustering section): the 195
non-outlier cards' background block features are essentially IDENTICAL
(pairwise "block distance" -- see `block_distance()` -- ranges 0.16-3.16
across all 195*194/2 pairs, no gaps, no sub-groups), while the ONE genuine
outlier (card 94, see CARD_94_ILLUSTRATION) has BODY_ZONE occupied by a
hand-painted illustration, not a gradient at all -- a "shared template"
would either (a) borrow a cluster-mate's exact pixels and reproduce the
target card's own few-unit-per-channel quantization noise imperfectly (an
error the validation gate would then have to tolerate as "expected", making
the gate weaker), or (b) require picking a representative member per cluster
which is an arbitrary, unjustified choice when the members are this close.
Reconstructing EVERY card strictly from ITS OWN measured non-ink pixels (via
the block-grid + inpaint + bilinear-upsample pipeline below) sidesteps both
problems: fidelity is bounded only by how smooth the true gradient is
locally (typically a couple of RGB units, see the validation gate's measured
numbers in the SDD report), never by "how similar is this card to whichever
template we borrowed from". The clustering analysis (`cluster_backgrounds`)
is still done, and still reported in full (method, distances, sizes) --
per the task brief it is a REQUIRED deliverable in its own right (how many
genuinely distinct styles exist), it's just not what the reconstruction math
depends on.

## Why card 94's BODY_ZONE skip is a hardcoded whitelist, not a detector

card-layout-spec.md section 3.3 already hand-verified (human eyes, see
`build/card_probe/card94_3x.png` from the prior round) that BODY_ZONE on
card 94 is a character illustration, not text -- the ONLY such case in the
196-card corpus. An automatic "does this look like a photo vs. gradient"
classifier could misfire on some future/other card and silently blank out
another illustration (or, worse, silently draw Chinese text ACROSS one) --
CLAUDE.md's stance on this class of one-off exception is to hardcode it as
an explicit, reviewable constant (`CARD_94_ILLUSTRATION`) rather than trust
a heuristic in a place where getting it wrong destroys unrecoverable art.
`zones_to_redraw()` is the single choke point that consults this constant;
every caller (background reconstruction, text drawing, the pixel-diff report)
goes through it, and every skip is surfaced (CLI + manifest + report -- see
`run()`).

## Right-column non-uniform 3-line spacing (cards 26/118/158/162)

card-layout-spec.md section 4.3 measured the real JP layout for these 4
cards as non-uniform: 10px between segment 1->2, 25px between segment 2->3
(vs. the normal ~23px uniform pitch used everywhere else). This module
attempts to reproduce that (`RIGHT_3LINE_GAPS`); each card's plan_right()
result carries a `spacing_mode` ("nonuniform_3line" or the "uniform"
fallback), and run()'s report surfaces any card that landed on the fallback
via `right_3line_fallback_to_uniform` -- this is a user-authorized fallback
(see task brief "先尝试复刻...若有困难或效果不好就不强求"), so it MUST be
visible, never silently substituted.
"""
import argparse, json, os, sys
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.measure_card import (
    BODY_ZONE, CARD_H, CARD_W, FONT_PATH, INK_MIN_ALPHA, INTERIOR,
    RIGHT_ZONE, TITLE_ZONE, card_path, load_card_domain, load_cards_jp,
    load_cards_zh, load_section_labels_zh, wrap_body_zh, wrap_right_zh,
    wrap_title_zh,
)

OUT_DIR = os.path.join(REPO, "build", "card_zh")

# ---------------------------------------------------------------------------
# Card 94 whitelist (see module docstring). Hardcoded, not detected.
# ---------------------------------------------------------------------------
CARD_94_ILLUSTRATION = 94


def zones_to_redraw(card):
    """Explicit whitelist -- the single choke point every part of this
    pipeline (reconstruction, drawing, validation) must consult before
    touching a zone. Every real card gets ("title", TITLE_ZONE) and
    ("right", RIGHT_ZONE); every card EXCEPT CARD_94_ILLUSTRATION also gets
    ("body", BODY_ZONE). See module docstring."""
    zones = [("title", TITLE_ZONE), ("right", RIGHT_ZONE)]
    if card != CARD_94_ILLUSTRATION:
        zones.append(("body", BODY_ZONE))
    return zones


# ---------------------------------------------------------------------------
# Background reconstruction: block-grid feature extraction (self-referential,
# per card) + inpaint of text-occluded blocks + bilinear upsample. See module
# docstring for why this is per-card rather than per-cluster.
# ---------------------------------------------------------------------------
BLOCK = 8   # 8x8px blocks over INTERIOR (192x128 -> 24x16 grid, 384 blocks).
            # Small enough to track the gradient's real curvature, large
            # enough that most blocks contain far more background pixels
            # than the ~1-2px-wide antialiased edge of any single glyph
            # stroke crossing them (see BG_CLEAN_THRESH below for why the
            # *edge* pixels specifically need their own, stricter test).

# A pixel counts as "definitely background" (safe to average into a block's
# reconstruction value, or to check a reconstruction against) only if BOTH:
#   (a) max(r,g,b) >= BG_CLEAN_THRESH, AND
#   (b) it is not within INK_DILATE_RADIUS px of a confirmed-ink pixel
#       (measure_card's own criterion: max(r,g,b)<120 @ alpha>=200, the
#       DARK CORE of a glyph stroke).
#
# Neither test alone is sufficient -- both failure modes were found by
# actually measuring, not assumed up front (see the SDD report's "为什么两个
# 判据都要" subsection for the full trace):
#   - Brightness ALONE (just (a), no dilation): works for the 195
#     "red-family" cards (background R channel never drops below ~236, so
#     235 cleanly separates background from any antialiasing-ring pixel,
#     which blends every channel including R toward the dark ink color) but
#     FAILS on card 94, whose background hue is warmer/lower overall (R
#     itself only ~235-248) -- a still-visibly-contaminated pixel one step
#     off a glyph edge, (235,200,166), has R exactly at the 235 cutoff while
#     G/B are heavily darkened, and slips through as "clean".
#   - Dilation ALONE (just (b), no brightness floor): the antialiasing ring
#     around LXGW-rendered 9-11px glyphs turned out to extend further than
#     the radius=2 that was tried first -- pixels 3+px from the strict-ink
#     core (e.g. (121,75,72), max channel 121, one unit above the ink
#     cutoff) are STILL visibly part of the glyph's blend, not background;
#     widening the radius indefinitely to chase this is fragile (how far is
#     "far enough" isn't well-defined without also constraining brightness).
# Requiring BOTH catches what either one misses on its own: dilation removes
# card 94's hue-dependent false positive, brightness removes the
# far-antialiasing-ring pixels dilation alone would still admit. radius=1 is
# enough once brightness is doing the bulk of the exclusion -- it only needs
# to cover the single boundary pixel right at the strict-ink/non-ink seam
# (see the report's pixel-level trace of (17,24) on card 94, which needs
# radius>=1 but not more once combined with the brightness floor).
BG_CLEAN_THRESH = 235
INK_DILATE_RADIUS = 1
BG_CLEAN_MIN_FRACTION = 0.5   # a block only "counts" if at least half its
                               # pixels are clean-background -- otherwise
                               # (a block that's mostly glyph ink, e.g. a
                               # dense body-text row) it's marked missing and
                               # filled by inpaint_block_grid() from its
                               # neighbors instead of averaging a
                               # majority-ink block into a fake "background".


def dilated_ink_mask(im, zone, radius=INK_DILATE_RADIUS):
    """set of (x,y) within `zone` that are confirmed ink (measure_card's own
    max(r,g,b)<120 @ alpha>=200 criterion) OR within `radius` px of such a
    pixel. Combined with the BG_CLEAN_THRESH brightness floor by
    `_is_clean_bg_pixel()` below -- see BG_CLEAN_THRESH's docstring for why
    neither test alone is sufficient."""
    px = im.load()
    x0, y0, x1, y1 = zone
    ink = set()
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            if a >= INK_MIN_ALPHA and max(r, g, b) < 120:
                ink.add((x, y))
    if not ink:
        return ink
    dilated = set()
    for (x, y) in ink:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                dilated.add((x + dx, y + dy))
    return dilated


def _is_clean_bg_pixel(x, y, px, ink_mask):
    """The combined test -- see BG_CLEAN_THRESH's docstring."""
    if (x, y) in ink_mask:
        return False
    r, g, b, a = px[x, y]
    return a >= INK_MIN_ALPHA and max(r, g, b) >= BG_CLEAN_THRESH


def _block_overlaps(bx0, by0, size, zone):
    zx0, zy0, zx1, zy1 = zone
    return not (bx0 + size <= zx0 or bx0 >= zx1 or by0 + size <= zy0 or by0 >= zy1)


def block_grid_dims():
    x0, y0, x1, y1 = INTERIOR
    return (x1 - x0) // BLOCK, (y1 - y0) // BLOCK


def _block_grid_from_image(im, skip_body=False, block=BLOCK, ink_mask=None):
    """{(bx,by): (r,g,b) or None} over the INTERIOR block grid. `skip_body`
    forces every block overlapping BODY_ZONE to None regardless of its own
    pixel content -- used for CARD_94_ILLUSTRATION, where BODY_ZONE pixels
    are illustration content and must never be averaged as if they were
    gradient background (see module docstring). `ink_mask` (if given) is a
    precomputed dilated_ink_mask(im, INTERIOR) -- computed once by the
    caller and reused, since it's the same mask for every block in one
    card's grid."""
    if ink_mask is None:
        ink_mask = dilated_ink_mask(im, INTERIOR)
    px = im.load()
    x0z, y0z, x1z, y1z = INTERIOR
    cols, rows = (x1z - x0z) // block, (y1z - y0z) // block
    feats = {}
    for by in range(rows):
        for bx in range(cols):
            bx0, by0 = x0z + bx * block, y0z + by * block
            if skip_body and _block_overlaps(bx0, by0, block, BODY_ZONE):
                feats[(bx, by)] = None
                continue
            rs = gs = bs = n = total = 0
            for y in range(by0, by0 + block):
                for x in range(bx0, bx0 + block):
                    total += 1
                    if not _is_clean_bg_pixel(x, y, px, ink_mask):
                        continue
                    r, g, b, _a = px[x, y]
                    rs += r; gs += g; bs += b; n += 1
            feats[(bx, by)] = (rs / n, gs / n, bs / n) if n >= total * BG_CLEAN_MIN_FRACTION else None
    return feats, cols, rows


def card_block_grid(card):
    """Raw (pre-inpaint) block feature grid for `card`, read straight off
    disk. `None` entries are blocks needing inpaint_block_grid() before use
    as a reconstruction source (or, for clustering, simply skipped -- see
    block_distance())."""
    im = Image.open(card_path(card)).convert("RGBA")
    return _block_grid_from_image(im, skip_body=(card == CARD_94_ILLUSTRATION))


def inpaint_block_grid(feats, cols, rows):
    """Fill every None block by iteratively averaging its already-filled
    8-connected neighbors, propagating outward until every block has a
    value. Raises (never silently returns partial data) if some block has no
    reachable neighbor with data at all -- would only happen if an entire
    grid were empty, which never occurs for a real card (see tests)."""
    grid = dict(feats)
    missing = {k for k, v in grid.items() if v is None}
    guard = 0
    while missing and guard <= cols + rows + 4:
        guard += 1
        newvals = {}
        for (bx, by) in missing:
            neigh = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    k2 = (bx + dx, by + dy)
                    if k2 in grid and grid[k2] is not None:
                        neigh.append(grid[k2])
            if neigh:
                newvals[(bx, by)] = tuple(sum(v[i] for v in neigh) / len(neigh) for i in range(3))
        if not newvals:
            break
        for k, v in newvals.items():
            grid[k] = v
        missing -= set(newvals)
    if missing:
        raise RuntimeError(
            f"inpaint_block_grid: block(s) {sorted(missing)} have no reachable "
            f"filled neighbor -- reconstruction impossible (this should never "
            f"happen for a real card; refusing to guess a color out of thin air)"
        )
    return grid


def blocks_to_image(grid, cols, rows, size):
    small = Image.new("RGB", (cols, rows))
    spx = small.load()
    for (bx, by), v in grid.items():
        spx[bx, by] = tuple(max(0, min(255, round(c))) for c in v)
    return small.resize(size, Image.BILINEAR).convert("RGBA")


def reconstruct_background(card):
    """Full CARD_W x CARD_H RGBA canvas: outside INTERIOR is a byte-identical
    copy of the original (border/corners, never touched by this pipeline);
    inside INTERIOR is the smooth, self-referential reconstruction built from
    `card`'s own clean background pixels (see module docstring)."""
    im = Image.open(card_path(card)).convert("RGBA")
    ink_mask = dilated_ink_mask(im, INTERIOR)
    feats, cols, rows = _block_grid_from_image(im, skip_body=(card == CARD_94_ILLUSTRATION),
                                                ink_mask=ink_mask)
    grid = inpaint_block_grid(feats, cols, rows)
    x0, y0, x1, y1 = INTERIOR
    interior_img = blocks_to_image(grid, cols, rows, (x1 - x0, y1 - y0))
    canvas = im.copy()
    canvas.paste(interior_img, (x0, y0))
    return canvas


# ---------------------------------------------------------------------------
# Validation gate: at every pixel INSIDE a redrawn zone (per zones_to_redraw)
# that the ORIGINAL card confirms is NOT ink (measure_card's own ink
# criterion -- max(r,g,b)<120 at alpha>=200 -- is the ink test; its
# complement at alpha>=200 is "confirmed background"), the reconstructed
# background must closely match the real pixel that was really there. This
# is the single gate standing between "reconstruction" and "silently
# overwriting real pixels with a guess nobody checked" -- MUST run before any
# file is written, and MUST raise (not warn-and-continue) if any card
# exceeds the threshold. See run()'s zero-corruption invariant.
# ---------------------------------------------------------------------------

def confirmed_background_pixels(im, zone):
    """[(x,y), ...] inside `zone` where the ORIGINAL image is confirmed-clean
    background by `_is_clean_bg_pixel()` -- the SAME combined
    brightness+dilation test the reconstruction's own block averaging
    trusts (see BG_CLEAN_THRESH's docstring). This is deliberately NOT
    measure_card's raw ink-threshold complement (max(r,g,b)<120): a first
    pass using that looser test flagged ~170-184 unit false "diffs" on
    nearly every card (e.g. a title-glyph edge pixel at (121,73,68) -- max
    channel 121, one unit above the ink cutoff of 120, still visibly part of
    the glyph, not background) -- i.e. the looser test was checking the
    reconstruction against pixels that were never really "confirmed
    background" to begin with, which would have made the gate MEASURE THE
    WRONG THING (glyph-edge contamination it correctly excluded, misread as
    reconstruction error) rather than genuinely validate fidelity. Using the
    same trusted-input test here makes this a real "does the smooth model
    fit the data it was told to fit" check, not a false-alarm generator."""
    x0, y0, x1, y1 = zone
    ink_mask = dilated_ink_mask(im, zone)
    px = im.load()
    out = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _is_clean_bg_pixel(x, y, px, ink_mask):
                out.append((x, y))
    return out


def validate_card_reconstruction(card):
    """Compare reconstruct_background(card) against the real original, ONLY
    at confirmed-background pixels within the zones this card actually gets
    redrawn (zones_to_redraw -- so e.g. card 94's BODY_ZONE, never
    reconstructed or drawn on, is correctly excluded from this check too).
    Returns a dict with max/mean per-channel diff, sample count, and the
    single worst pixel (for the report to name and mutation-test to pin)."""
    orig = Image.open(card_path(card)).convert("RGBA")
    recon = reconstruct_background(card)
    opx, rpx = orig.load(), recon.load()
    max_diff, sum_diff, n, worst = 0, 0.0, 0, None
    for _name, zone in zones_to_redraw(card):
        for (x, y) in confirmed_background_pixels(orig, zone):
            o, r = opx[x, y], rpx[x, y]
            d = max(abs(o[0] - r[0]), abs(o[1] - r[1]), abs(o[2] - r[2]))
            sum_diff += d
            n += 1
            if d > max_diff:
                max_diff, worst = d, {"xy": [x, y], "orig": list(o[:3]), "recon": list(r[:3]), "diff": d}
    return {
        "card": card, "max_diff": max_diff,
        "mean_diff": (sum_diff / n) if n else 0.0,
        "n_checked": n, "worst_pixel": worst,
    }


# Threshold rationale -- measured, and measured THROUGH two prior failed
# attempts, not picked cold (see the SDD report's "验证闸判据怎么定" section
# for the full before/after numbers this summarizes):
#   attempt 1 (confirmed-bg = measure_card's raw ink-threshold complement,
#     max(r,g,b)<120): max_diff ~166-184 on nearly EVERY card -- the gate was
#     measuring antialiasing-ring contamination it should have excluded, not
#     real reconstruction error (see confirmed_background_pixels's docstring).
#   attempt 2 (confirmed-bg = brightness-only, max(r,g,b)>=235, no dilation):
#     195 cards settled to a tight max_diff band of 25-40, but card 94 alone
#     sat at 51 -- traced to its warmer hue letting a still-contaminated
#     pixel's R channel alone clear 235 while G/B stayed dark (see
#     BG_CLEAN_THRESH's docstring).
#   final (brightness >=235 AND outside a radius-1 dilation of confirmed
#     ink): re-measured over all 196 real cards -- 195 cards range
#     [15, 34] (mean 22-26 depending on dilation radius), card 94 alone at
#     ~52-54. mean_diff (averaged over thousands of checked pixels per card,
#     not just the single worst one) stays in [1.4, 2.9] for EVERY card,
#     including 94 -- i.e. even card 94's worst case is one boundary pixel,
#     not a systematically-off zone.
# 60 sits above BOTH populations (195-card max ~34, card-94 max ~54) with
# real margin, while staying an order of magnitude below what attempt 1's
# false positives (166-184) or an actual bug (wrong card's pixels, a
# mis-offset zone -- see tests/test_bake_card.py's mutation) would produce.
# Kept as a named constant (not inlined) so the mutation that disables the
# gate (see tests) has one obvious place to point at, and so a future re-run
# with different source art can update it deliberately rather than by silent
# drift.
VALIDATION_MAX_DIFF_THRESHOLD = 60


def run_validation_gate(cards):
    """Runs validate_card_reconstruction for every card in `cards`. Returns
    (results, over_threshold) -- over_threshold MUST be surfaced by the
    caller (CLI/manifest/report) and MUST stop the whole run before any file
    is written if non-empty (see run()). Never call this and discard
    `over_threshold` -- that is exactly the "background reconstruction
    validation gate silently switched off" failure mode the task's mutation
    list calls out."""
    results = [validate_card_reconstruction(c) for c in cards]
    over = [r for r in results if r["max_diff"] > VALIDATION_MAX_DIFF_THRESHOLD]
    return results, over


# ---------------------------------------------------------------------------
# Gradient-style clustering (required deliverable in its own right -- see
# module docstring's "why self-referential" section for why this does NOT
# feed the reconstruction math). Average-linkage agglomerative clustering
# (Lance-Williams update) over the RAW (pre-inpaint) block-grid feature
# vectors, pure Python (no numpy/scipy in this project's dependency set --
# see pyproject.toml).
# ---------------------------------------------------------------------------
MIN_BLOCK_OVERLAP = 20   # two cards' feature vectors must share at least
                          # this many jointly-non-None blocks to compute a
                          # distance at all -- guards against a spurious
                          # "close" or "far" verdict built from a handful of
                          # coincidentally-shared clean blocks. Real cards
                          # share 188-384 valid blocks out of 384 (measured),
                          # so this floor is never actually binding for real
                          # data; it exists for defensive correctness.


def block_distance(fa, fb):
    """Mean squared per-block, per-channel Euclidean distance over blocks
    valid (non-None) in BOTH `fa` and `fb`. Returns None if fewer than
    MIN_BLOCK_OVERLAP blocks overlap (undefined, not zero -- a caller must
    not silently treat 'undefined' as 'identical')."""
    ssum, n = 0.0, 0
    for k, va in fa.items():
        vb = fb.get(k)
        if va is None or vb is None:
            continue
        ssum += (va[0] - vb[0]) ** 2 + (va[1] - vb[1]) ** 2 + (va[2] - vb[2]) ** 2
        n += 1
    if n < MIN_BLOCK_OVERLAP:
        return None
    return ssum / n


# Cluster-merge cutoff. Rationale (measured, see report): among the 195*194/2
# real pairwise distances EXCLUDING card 94, the observed range is
# [0.16, 3.16] -- a tight, gap-free, unimodal distribution consistent with
# "one style, per-card quantization noise only" (see report for the full
# histogram). Card 94's distance to every other card is ~690 -- three orders
# of magnitude higher, an obvious, unambiguous gap. 20 sits with >6x headroom
# above the observed intra-group max and >30x below the outlier -- nowhere
# near either edge, so the specific choice of e.g. 15 vs 30 would not change
# the resulting partition on real data (verified: see
# tests/test_bake_card.py::test_cluster_threshold_is_not_knife_edge).
CLUSTER_DIST_THRESHOLD = 20


def cluster_backgrounds(cards, threshold=CLUSTER_DIST_THRESHOLD):
    """Union-Find single-linkage clustering: card A and B end up in the same
    cluster iff there is a chain of pairwise block_distance() calls, each
    below `threshold`, connecting them (not just A-B directly below
    threshold -- true single-linkage transitive closure). Pairs with an
    undefined (None) distance are treated as NOT connected (conservative:
    insufficient evidence is never treated as "same cluster").

    Returns {card: cluster_id} plus the raw distance matrix isn't kept (196x
    196 -- callers needing distances again should recompute via
    card_block_grid + block_distance, which is cheap: ~380-dim vectors,
    fractions of a second per pair).
    """
    feats = {c: card_block_grid(c)[0] for c in cards}
    parent = {c: c for c in cards}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    n = len(cards)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = cards[i], cards[j]
            d = block_distance(feats[a], feats[b])
            if d is not None and d < threshold:
                union(a, b)

    roots = {}
    assignment = {}
    for c in cards:
        r = find(c)
        if r not in roots:
            roots[r] = len(roots)
        assignment[c] = roots[r]
    return assignment


def cluster_report(cards, threshold=CLUSTER_DIST_THRESHOLD):
    """Human/manifest-facing summary: cluster sizes, members, and a short
    per-cluster characterization (mean RGB at the block nearest each of
    the 4 INTERIOR corners, so 'what differs' is nameable, not just a size
    count)."""
    assignment = cluster_backgrounds(cards, threshold=threshold)
    by_cluster = defaultdict(list)
    for c, cid in assignment.items():
        by_cluster[cid].append(c)
    feats = {c: card_block_grid(c)[0] for c in cards}
    cols, rows = block_grid_dims()
    corner_blocks = {
        "top_left": (0, 0), "top_right": (cols - 1, 0),
        "bottom_left": (0, rows - 1), "bottom_right": (cols - 1, rows - 1),
    }
    clusters = []
    for cid, members in sorted(by_cluster.items(), key=lambda kv: -len(kv[1])):
        members = sorted(members)
        corner_means = {}
        for name, bpos in corner_blocks.items():
            vals = [feats[c][bpos] for c in members if feats[c].get(bpos) is not None]
            if vals:
                corner_means[name] = [round(sum(v[i] for v in vals) / len(vals), 1) for i in range(3)]
            else:
                corner_means[name] = None
        clusters.append({
            "cluster_id": cid, "size": len(members),
            "members": members if len(members) <= 20 else members[:20] + ["..."],
            "member_count_full": len(members),
            "corner_mean_rgb": corner_means,
        })
    return {"threshold": threshold, "num_clusters": len(clusters), "clusters": clusters}


# ---------------------------------------------------------------------------
# Text layout (measured in card-layout-spec.md section 4; reproduced here as
# named constants rather than re-deriving pixel positions from ink bands on
# every run, mirroring how bake_scene.py hardcodes its own measured
# TEXT_BOX/pitch after the fact -- these ARE the measured numbers, not
# estimates).
# ---------------------------------------------------------------------------
FONT_SIZE_TITLE = 11
FONT_SIZE_BODY = 9
FONT_SIZE_RIGHT = 9   # NOT user-specified -- the task brief left this open
                       # ("用户未指定，我定的默认值") and asked for it to be
                       # named explicitly as a changeable default, so: this is
                       # a default (matching FONT_SIZE_BODY for visual
                       # consistency across the two zones), not a user
                       # mandate. Also not dictated by the spec's own trial
                       # (which found both 8px and 9px fit with 0 overflow,
                       # see card-layout-spec.md 5.3) -- either value works;
                       # see the SDD report for this call-out.

TITLE_MAX_WIDTH = 176   # 202-10-2*8, see spec 5
BODY_MAX_WIDTH = 110    # measured original hard cap, spec 4.2
BODY_MAX_LINES = 7      # structural ceiling, spec 4.2
RIGHT_MAX_WIDTH = 53    # measured original max real segment width, spec 4.3

TITLE_LEFT_MARGIN = 8    # spec 4.1: ink x0 always TITLE_ZONE[0]+8
BODY_LEFT_MARGIN = 8     # spec 4.2: ink x0 always BODY_ZONE[0]+8
RIGHT_LEFT_MARGIN = 3    # spec 4.3: ink x0 in [141,143], zone left=139 -> +2..4, midpoint 3

BODY_FIRST_Y_OFFSET = 5    # spec 4.2: first-line ink y0 47/48, BODY_ZONE top=42 -> +5/+6, use 5
BODY_PITCH = 12            # spec 4.2, measured exactly
BODY_PARAGRAPH_GAP_LINES = 1   # spec: "\n\n 是段落边界...必须保留" -- render
                                 # as one full extra line-pitch of blank space
                                 # before the next paragraph's first line
                                 # (only card 41 has a \n\n, see module
                                 # docstring's paragraph handling note).

RIGHT_FIRST_Y_OFFSET = 5   # spec 4.3: first-line ink y0 46-48, zone top=42 -> +4..6, use 5
RIGHT_PITCH_UNIFORM = 23   # spec 4.3: measured 22-24px for 2-line labels, midpoint

RIGHT_3LINE_CARDS = (26, 118, 158, 162)
RIGHT_3LINE_GAPS = (10, 25)   # spec 4.3: seg1->seg2 = 10px, seg2->seg3 = 25px

FILL_COLOR = (12, 11, 10, 255)   # matches measure_card's measured original
                                   # JP ink color (see its module docstring)
                                   # -- dark-on-light needs no stroke, unlike
                                   # scene/'s white-on-dark-band.

_FONT_CACHE = {}


def _font(size):
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = ImageFont.truetype(FONT_PATH, size)
    return _FONT_CACHE[size]


def _measurer_for(font):
    probe = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(probe)
    return lambda s: d.textlength(s, font=font)


# ---------------------------------------------------------------------------
# Per-card render plan: resolves wrapped lines/positions WITHOUT touching
# pixels yet, so overflow/spacing-fallback bookkeeping can be assembled and
# checked before any drawing happens (mirrors bake_scene's build_render_plan
# separation of "decide" from "draw").
# ---------------------------------------------------------------------------

def plan_title(card, title_zh):
    font = _font(FONT_SIZE_TITLE)
    lines, info = wrap_title_zh(title_zh, font, TITLE_MAX_WIDTH, max_lines=1)
    cy = (TITLE_ZONE[1] + TITLE_ZONE[3]) / 2
    x = TITLE_ZONE[0] + TITLE_LEFT_MARGIN
    return {"lines": lines, "info": info, "font_size": FONT_SIZE_TITLE,
            "positions": [(x, cy, "lm")]}


def plan_body(card, body_zh):
    font = _font(FONT_SIZE_BODY)
    paragraphs, info = wrap_body_zh(card, body_zh, font, BODY_MAX_WIDTH, BODY_MAX_LINES)
    x = BODY_ZONE[0] + BODY_LEFT_MARGIN
    y = BODY_ZONE[1] + BODY_FIRST_Y_OFFSET
    positions = []
    total_lines = 0
    for pi, para in enumerate(paragraphs):
        if pi > 0:
            y += BODY_PITCH * BODY_PARAGRAPH_GAP_LINES
            total_lines += BODY_PARAGRAPH_GAP_LINES
        for line in para:
            positions.append((x, y, "la", line))
            y += BODY_PITCH
            total_lines += 1
    # Height-based overflow: the paragraph-gap slot(s) consume real pixels
    # that wrap_body_zh's own max_lines accounting (content lines only,
    # spec-inherited from measure_card) does not know about -- so this
    # module keeps its own stricter total_lines check (content + gap slots)
    # and surfaces it separately, never silently trusting the upstream
    # info["truncated"]=False as sufficient (see run()'s overflow report).
    height_overflow = total_lines > BODY_MAX_LINES
    return {"paragraphs": paragraphs, "info": info, "font_size": FONT_SIZE_BODY,
            "positions": positions, "total_lines": total_lines,
            "height_overflow": height_overflow}


def plan_right(card, label_zh):
    font = _font(FONT_SIZE_RIGHT)
    segs, info = wrap_right_zh(card, label_zh, font, RIGHT_MAX_WIDTH, max_lines_per_segment=2)
    x = RIGHT_ZONE[0] + RIGHT_LEFT_MARGIN
    y = RIGHT_ZONE[1] + RIGHT_FIRST_Y_OFFSET
    all_lines = [ln for seg in segs for ln in seg]
    positions = []
    spacing_mode = "uniform"
    if card in RIGHT_3LINE_CARDS and len(all_lines) == 3:
        spacing_mode = "nonuniform_3line"
        gaps = RIGHT_3LINE_GAPS
        positions.append((x, y, "la", all_lines[0]))
        y2 = y + gaps[0]
        positions.append((x, y2, "la", all_lines[1]))
        y3 = y2 + gaps[1]
        positions.append((x, y3, "la", all_lines[2]))
    else:
        yy = y
        for line in all_lines:
            positions.append((x, yy, "la", line))
            yy += RIGHT_PITCH_UNIFORM
    return {"segments": segs, "info": info, "font_size": FONT_SIZE_RIGHT,
            "positions": positions, "spacing_mode": spacing_mode}


def build_render_plan(cards_zh, cards_jp, section_labels_zh, cards=None):
    """{card: {"title":..., "body":..., "right":...}} plus aggregated
    overflow/fallback lists that MUST be surfaced (see run())."""
    cards = cards or sorted(cards_zh)
    plans = {}
    title_overflow, body_overflow, body_height_overflow, right_overflow = [], [], [], []
    missing_label = []
    for card in cards:
        title_zh = cards_zh[card]["title_zh"]
        body_zh = cards_zh[card]["body_zh"]
        jp_label = cards_jp.get(card, {}).get("section_label", "")

        tplan = plan_title(card, title_zh)
        if tplan["info"]["truncated"]:
            title_overflow.append({"card": card, "text": title_zh, "dropped": tplan["info"]["dropped"]})

        bplan = plan_body(card, body_zh) if body_zh else None
        if bplan:
            if bplan["info"]["truncated"]:
                body_overflow.extend(bplan["info"]["overflow_segments"])
            if bplan["height_overflow"]:
                body_height_overflow.append({"card": card, "total_lines": bplan["total_lines"],
                                              "max_lines": BODY_MAX_LINES})

        rplan = None
        if jp_label:
            zh_label = section_labels_zh.get(jp_label)
            if zh_label is None:
                missing_label.append({"card": card, "jp_label": jp_label})
            else:
                rplan = plan_right(card, zh_label)
                if rplan["info"]["truncated"]:
                    right_overflow.extend(rplan["info"]["overflow_segments"])

        plans[card] = {"title": tplan, "body": bplan, "right": rplan}
    return plans, {
        "title_overflow": title_overflow,
        "body_overflow": body_overflow,
        "body_height_overflow": body_height_overflow,
        "right_overflow": right_overflow,
        "missing_label": missing_label,
    }


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------

def bake_card(card, plan):
    """Returns (new_card_image, outside_zones_diffs). Background for every
    zone in zones_to_redraw(card) is replaced with reconstruct_background()'s
    output for that zone, THEN the plan's text is drawn on top; every pixel
    outside those zones (border, divider, and -- for card 94 specifically --
    BODY_ZONE) is byte-identical to the source file."""
    orig = Image.open(card_path(card)).convert("RGBA")
    recon = reconstruct_background(card)
    new_card = orig.copy()
    zones = zones_to_redraw(card)
    zone_by_name = dict(zones)
    for _name, zone in zones:
        new_card.paste(recon.crop(zone), zone[:2])

    d = ImageDraw.Draw(new_card)
    if plan["title"]:
        font = _font(plan["title"]["font_size"])
        for (x, y, anchor) in plan["title"]["positions"]:
            text = plan["title"]["lines"][0] if plan["title"]["lines"] else ""
            d.text((x, y), text, font=font, fill=FILL_COLOR, anchor=anchor)
    if plan["body"] and "body" in zone_by_name:
        font = _font(plan["body"]["font_size"])
        for (x, y, anchor, line) in plan["body"]["positions"]:
            d.text((x, y), line, font=font, fill=FILL_COLOR, anchor=anchor)
    if plan["right"]:
        font = _font(plan["right"]["font_size"])
        for (x, y, anchor, line) in plan["right"]["positions"]:
            d.text((x, y), line, font=font, fill=FILL_COLOR, anchor=anchor)

    diffs = find_outside_zones_diffs(orig, new_card, [z for _n, z in zones])
    return new_card, diffs


def find_outside_zones_diffs(orig, new, zones):
    """[(x,y), ...] pixels OUTSIDE every zone in `zones` where orig != new.
    Must be empty -- pixel-preservation gate, same never-silent principle as
    bake_scene.find_outside_box_diffs. Scans the whole CARD_W x CARD_H
    canvas (not just INTERIOR) so it also catches an accidental touch to the
    border/corner region."""
    opx, npx = orig.load(), new.load()
    diffs = []
    for y in range(CARD_H):
        for x in range(CARD_W):
            if any(z[0] <= x < z[2] and z[1] <= y < z[3] for z in zones):
                continue
            if opx[x, y] != npx[x, y]:
                diffs.append((x, y))
    return diffs


# ---------------------------------------------------------------------------
# Compare / cellzoom images.
# ---------------------------------------------------------------------------

def build_compare_image(pairs, cols=6):
    """pairs: [(card, orig_img, new_img), ...]."""
    scale = 2
    cw, ch = CARD_W * scale, CARD_H * scale
    label_h = 14
    gap = 8
    cell_w = cw + gap
    cell_h = label_h + ch * 2 + gap
    rows = (len(pairs) + cols - 1) // cols
    canvas = Image.new("RGBA", (cols * cell_w + gap, rows * cell_h + gap), (30, 30, 30, 255))
    d = ImageDraw.Draw(canvas)
    for i, (card, orig, new) in enumerate(pairs):
        col, row = i % cols, i // cols
        x, y = gap + col * cell_w, gap + row * cell_h
        d.text((x, y), f"#{card} JP(top)/ZH(bottom)", fill=(255, 255, 0, 255))
        y2 = y + label_h
        canvas.paste(orig.resize((cw, ch), Image.NEAREST), (x, y2))
        canvas.paste(new.resize((cw, ch), Image.NEAREST), (x, y2 + ch))
    return canvas


def build_cellzoom_image(cards, plans, scale=3, cols=3):
    cw, ch = CARD_W * scale, CARD_H * scale
    label_h = 16
    gap = 10
    cell_w = cw + gap
    cell_h = label_h + ch * 2 + gap
    rows = (len(cards) + cols - 1) // cols
    canvas = Image.new("RGBA", (cols * cell_w + gap, rows * cell_h + gap), (24, 24, 24, 255))
    d = ImageDraw.Draw(canvas)
    for i, card in enumerate(cards):
        col, row = i % cols, i // cols
        x, y = gap + col * cell_w, gap + row * cell_h
        orig = Image.open(card_path(card)).convert("RGBA")
        new_card, _ = bake_card(card, plans[card])
        d.text((x, y), f"#{card}", fill=(255, 255, 0, 255))
        y2 = y + label_h
        canvas.paste(orig.resize((cw, ch), Image.NEAREST), (x, y2))
        canvas.paste(new_card.resize((cw, ch), Image.NEAREST), (x, y2 + ch))
    return canvas


# ---------------------------------------------------------------------------
# Cellzoom picks: card 94 (illustration whitelist), 145 (poem, no rewrap),
# 41 (paragraph break), 4 (option list / quote-line rule), the tightest
# body-margin cards (5/9/14/15), the 3-line right-column cards (26/118/158/
# 162), the longest titles (182/180), and one representative per background
# cluster (resolved at run() time once cluster_report() is available).
# ---------------------------------------------------------------------------
CELLZOOM_FIXED_CARDS = [94, 145, 41, 4, 5, 9, 14, 15, 26, 118, 158, 162, 182, 180]


def run(write=True, with_images=None):
    if with_images is None:
        with_images = write
    cards = load_card_domain()
    cards_zh = load_cards_zh()
    cards_jp = load_cards_jp()
    section_labels_zh = load_section_labels_zh()

    # --- 1. validation gate FIRST, before any reconstruction result is used
    # to draw or write anything (zero-corruption invariant). ---
    val_results, val_over = run_validation_gate(cards)
    if val_over:
        detail = "; ".join(
            f"card {r['card']}: max_diff={r['max_diff']} (threshold "
            f"{VALIDATION_MAX_DIFF_THRESHOLD}) at {r['worst_pixel']}"
            for r in val_over
        )
        raise RuntimeError(
            f"background reconstruction validation gate FAILED for "
            f"{len(val_over)} card(s) -- refusing to bake (zero-corruption "
            f"invariant): {detail}"
        )

    # --- 2. clustering (independent deliverable, does not gate anything) ---
    clusters = cluster_report(cards)

    # --- 3. render plan (wrap everything, collect overflow, before drawing) ---
    plans, overflow = build_render_plan(cards_zh, cards_jp, section_labels_zh, cards)

    any_overflow = (overflow["title_overflow"] or overflow["body_overflow"] or
                     overflow["body_height_overflow"] or overflow["right_overflow"] or
                     overflow["missing_label"])
    if any_overflow:
        raise RuntimeError(
            f"text overflow detected -- refusing to bake truncated text "
            f"(zero-truncation invariant): {json.dumps(overflow, ensure_ascii=False)[:2000]}"
        )

    # --- 4. bake, collecting pixel-preservation diffs per card ---
    new_cards = {}
    bad_cards = {}
    for card in cards:
        new_card, diffs = bake_card(card, plans[card])
        new_cards[card] = new_card
        if diffs:
            bad_cards[card] = diffs

    right_fallbacks = [c for c in RIGHT_3LINE_CARDS
                       if plans[c]["right"] and plans[c]["right"]["spacing_mode"] != "nonuniform_3line"]

    report = {
        "num_cards": len(cards),
        "card_94_illustration_skip": {
            "card": CARD_94_ILLUSTRATION,
            "zones_redrawn": [n for n, _z in zones_to_redraw(CARD_94_ILLUSTRATION)],
            "zones_skipped": ["body"],
        },
        "validation_gate": {
            "threshold": VALIDATION_MAX_DIFF_THRESHOLD,
            "num_checked": len(val_results),
            "max_diff_overall": max((r["max_diff"] for r in val_results), default=0),
            "mean_diff_overall": (sum(r["mean_diff"] for r in val_results) / len(val_results)) if val_results else 0,
            "over_threshold": val_over,
        },
        "clusters": clusters,
        "font_sizes": {"title": FONT_SIZE_TITLE, "body": FONT_SIZE_BODY, "right": FONT_SIZE_RIGHT},
        "right_3line_cards": list(RIGHT_3LINE_CARDS),
        "right_3line_fallback_to_uniform": right_fallbacks,
        "overflow": overflow,
        "pixel_preservation_violations": {str(c): d for c, d in bad_cards.items()},
    }

    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        for card in cards:
            new_cards[card].save(os.path.join(OUT_DIR, f"crd_{card}_a.png"))
        if with_images:
            sample = sorted(cards)[::max(1, len(cards) // 24)][:24]
            compare_pairs = [(c, Image.open(card_path(c)).convert("RGBA"), new_cards[c]) for c in sample]
            build_compare_image(compare_pairs).save(os.path.join(OUT_DIR, "_compare.png"))

            cellzoom_cards = list(dict.fromkeys(
                CELLZOOM_FIXED_CARDS +
                [clusters["clusters"][0]["members"][0]] +
                ([clusters["clusters"][1]["members"][0]] if len(clusters["clusters"]) > 1 else [])
            ))
            build_cellzoom_image(cellzoom_cards, plans).save(os.path.join(OUT_DIR, "_cellzoom.png"))
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

    print(f"cards: {report['num_cards']}")
    print(f"card 94 (illustration): redrawn={report['card_94_illustration_skip']['zones_redrawn']}, "
          f"skipped={report['card_94_illustration_skip']['zones_skipped']}")
    vg = report["validation_gate"]
    print(f"validation gate: {vg['num_checked']} cards checked, threshold={vg['threshold']}, "
          f"max_diff_overall={vg['max_diff_overall']}, over_threshold={len(vg['over_threshold'])}")
    print(f"clusters: {report['clusters']['num_clusters']} "
          f"(sizes: {[c['size'] for c in report['clusters']['clusters']]})")
    print(f"right 3-line cards attempted: {report['right_3line_cards']}, "
          f"fell back to uniform: {report['right_3line_fallback_to_uniform']}")
    ov = report["overflow"]
    print(f"overflow: title={len(ov['title_overflow'])} body={len(ov['body_overflow'])} "
          f"body_height={len(ov['body_height_overflow'])} right={len(ov['right_overflow'])} "
          f"missing_label={len(ov['missing_label'])}")
    print(f"pixel-preservation violations: {len(report['pixel_preservation_violations'])}")
    if report["pixel_preservation_violations"]:
        print(f"  cards: {sorted(report['pixel_preservation_violations'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()
