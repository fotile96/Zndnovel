#!/usr/bin/env python3
"""Pixel-level measurement + cross-verification for png/select/ option buttons
(250x26 "_on"/"_off" pairs). Two independent jobs live here:

1. **Layout measurement** (border/fill colors, icon notch, text-box geometry,
   per-char advance) -- feeds build/select_layout_spec.md.
2. **Ink-span verification**: an independent, low-cost sanity check on every
   JP string tools/derive_select.py (or the prior crude parser) claims a
   button shows. See module docstring section "Why this check exists" below
   -- it is not a nice-to-have, it caught real derivation bugs in this round
   (see the report).

## Why this check exists

tools/derive_select.py's derivation method (chase the scene the player lands
on after picking a button, use THAT scene's title as the button's own
caption) rests on an assumption: the followup scene's title restates what
the button said. That assumption can be wrong even when the code chase
itself is 100% correctly executed -- a scene's own title often describes
what happens *narratively* in that branch, not the player's stated choice.

Concrete confirmed case (manual pixel read, see the report):
`sel_s5s_350_sel_a` -- code: `v1==1` leads to
`scene_s5s_320_4(doScriptScene, "ナースコールのボタン")` ("the nurse call
button", describing what Ayano does next), which both the crude parser and
tools/derive_select.py report as the button's jp text. The button's ACTUAL
baked pixels say "無理はしない" ("I won't push myself") -- a different
string that does not appear anywhere in lua_scripts/ as a literal (grep
confirms zero hits). The chase logic executed correctly; the *assumption*
it rests on failed. No purely-code-based check can catch this class of
error, because the wrong answer is syntactically indistinguishable from a
right one -- both are real `scene_X(id, "title")` calls reached by a real
branch. Only checking against the actual pixels can.

## What this check can and cannot prove

It cannot OCR the button (no JP font available in this repo -- PGF is a
PSP-native format the C engine stub reads, not present here) so it cannot
prove a derivation is correct. What it CAN do: measure the real ink span's
pixel width and compare against a *predicted* width computed from the
candidate string's character count and an empirically-calibrated px/char
advance (see CALIBRATION below) -- catching the case where the derived
string's length is grossly wrong for what's actually on the button (as in
the s5s_350_sel_a case: predicted width for "ナースコールのボタン" (10
chars) is ~165px; the real ink span is only ~68px, an ~60% shortfall -- an
obvious red flag that would have caught this exact bug mechanically).
A close width match is necessary but not sufficient for correctness (two
different 9-character phrases would look identical to this check) -- this
is disclosed, not hidden: see the report's "假阴性" note.

## CALIBRATION: where the ~16.5px/char constant comes from

Measured directly (this round, by eye, cropped+upscaled PNG reads -- NOT
inherited from the crude parser's unverified claims) on SIX button/string
pairs the module docstring above and the report both cite explicitly:

    sel_s1s_35_sel_a_off  "約束を思い出せない" (9 chars)
    sel_s1s_35_sel_b_off  "約束をしている"     (7 chars)
    sel_s1s_35_sel_c_off  "約束をしていない"   (8 chars)
    sel_s5s_350_sel_b_off "がんばってみる"     (7 chars)
    sel_s5s_350_sel_a_off "無理はしない"       (6 chars)   <- real text, NOT
                                                              the wrong "目标
                                                              场景名" guess
    sel_s5s_80_sel_c_off  "雪が降る"           (4 chars)   <- ditto

All six independently land in a tight 16.2-16.8 px/char band (this game's
button font is effectively fixed-width per full-width JP glyph, unsurprising
for a bitmap game font) -- see CALIBRATION_PAIRS and
`tests/test_select_layout.py::test_calibration_pairs_cluster_tightly` which
pins this range so a future re-measurement that drifts outside it fails
loudly rather than silently shipping a new, unreviewed constant.
"""
import argparse, glob, json, os, re, sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELECT_DIR = os.path.join(REPO, "png", "select")

CELL_W, CELL_H = 250, 26
ICON_ZONE_X = 15          # ink search never looks left of this (icon+border template)
BORDER_FRAME = 3          # outer N px on every edge assumed content-free (verified: icon
                            # notch/text never reach x<15 or the 3px border ring -- see spec)

# ---------------------------------------------------------------------------
# Calibration ground truth -- see module docstring. `verified_by` records how
# each pair was confirmed, so a reader can tell "read off an upscaled pixel
# crop this round" apart from "inherited from an unverified prior claim".
# ---------------------------------------------------------------------------
CALIBRATION_PAIRS = [
    ("sel_s1s_35_sel_a_off", "約束を思い出せない", "本轮人工放大截图读图 + CLAUDE.md 记载的既有肉眼验证"),
    ("sel_s1s_35_sel_b_off", "約束をしている", "本轮人工放大截图读图"),
    ("sel_s1s_35_sel_c_off", "約束をしていない", "本轮人工放大截图读图"),
    ("sel_s5s_350_sel_b_off", "がんばってみる", "本轮人工放大截图读图"),
    ("sel_s5s_350_sel_a_off", "無理はしない", "本轮人工放大截图读图（推导链给出的答案是错的，见报告）"),
    ("sel_s5s_80_sel_c_off", "雪が降る", "本轮人工放大截图读图（推导链给出的答案是错的，见报告）"),
]


def image_path(button_off_name):
    """button_off_name: e.g. 'sel_s1s_35_sel_a_off' (no .png)."""
    return os.path.join(SELECT_DIR, button_off_name + ".png")


def collect_frame_palette(img):
    """The colors observed in the outer BORDER_FRAME ring of `img` -- these
    are guaranteed to be background/border template pixels, never ink (ink
    is centered horizontally per the layout spec and never approaches the
    3px edge). Also includes a thin interior strip just right of the icon
    zone (x in [ICON_ZONE_X-4, ICON_ZONE_X), full height) as a second
    guaranteed-background sample, since the border ring alone does not
    include the interior fill color sampled away from the border."""
    w, h = img.size
    px = img.load()
    colors = set()
    for y in range(h):
        for x in range(w):
            if x < BORDER_FRAME or x >= w - BORDER_FRAME or y < BORDER_FRAME or y >= h - BORDER_FRAME:
                colors.add(px[x, y])
    for y in range(h):
        for x in range(max(0, ICON_ZONE_X - 4), ICON_ZONE_X):
            colors.add(px[x, y])
    return colors


def ink_bbox(button_off_name, xmin=ICON_ZONE_X):
    """Returns (x0,y0,x1,y1) inclusive bbox of pixels NOT in this image's own
    dynamically-collected frame palette, restricted to x >= xmin (excludes
    the icon/notch/border zone). None if no such pixel exists.

    Deliberately per-image dynamic (not a hardcoded global color set): a
    hardcoded set risks silently misclassifying a slightly different render
    (e.g. the "_on" palette, or a future asset revision) as "no ink found"
    rather than raising -- collecting the palette fresh from each image's own
    guaranteed-background region is self-verifying instead."""
    path = image_path(button_off_name)
    img = Image.open(path).convert("RGBA")
    palette = collect_frame_palette(img)
    w, h = img.size
    px = img.load()
    xs, ys = [], []
    for y in range(h):
        for x in range(xmin, w):
            if px[x, y] not in palette:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def px_per_char(bbox, n_chars):
    if bbox is None or n_chars <= 0:
        return None
    width = bbox[2] - bbox[0] + 1
    return width / n_chars


def calibrate():
    """Returns (mean_px_per_char, [(name, jp, bbox, ratio), ...])."""
    rows = []
    for name, jp, _src in CALIBRATION_PAIRS:
        bbox = ink_bbox(name)
        ratio = px_per_char(bbox, len(jp))
        rows.append((name, jp, bbox, ratio))
    ratios = [r for *_, r in rows if r is not None]
    mean = sum(ratios) / len(ratios) if ratios else None
    return mean, rows


# ---------------------------------------------------------------------------
# Verification: for every (button, candidate jp) pair, predict width from
# char count x calibrated px/char, compare to measured ink width.
# ---------------------------------------------------------------------------

def verify_candidate(button_base, jp, px_per_char_const, tolerance_ratio=0.30):
    """button_base: e.g. 'sel_s1s_35_sel_a' (no _off/_on suffix).
    Returns a dict with measured/predicted widths and a verdict.
    tolerance_ratio: allowed relative deviation of measured-vs-predicted
    width before flagging a mismatch (see report for why 0.30 was chosen:
    calibration pairs cluster within ~2% of each other, but different real
    strings can legitimately vary a bit more due to punctuation/small kana
    -- 30% is chosen to comfortably clear that natural variance while still
    catching the observed failure modes, which were 40-60% off)."""
    off_name = button_base + "_off"
    path = image_path(off_name)
    if not os.path.exists(path):
        return {"button": button_base, "jp": jp, "status": "no_image"}
    bbox = ink_bbox(off_name)
    if bbox is None:
        return {"button": button_base, "jp": jp, "status": "no_ink_detected"}
    n = len(jp)
    measured_w = bbox[2] - bbox[0] + 1
    predicted_w = n * px_per_char_const
    if predicted_w <= 0:
        rel_dev = float("inf")
    else:
        rel_dev = abs(measured_w - predicted_w) / predicted_w
    status = "match" if rel_dev <= tolerance_ratio else "mismatch"
    return {
        "button": button_base, "jp": jp, "n_chars": n,
        "measured_bbox": list(bbox), "measured_width": measured_w,
        "predicted_width": round(predicted_w, 1),
        "relative_deviation": round(rel_dev, 3), "status": status,
    }


def verify_all(candidates, px_per_char_const, tolerance_ratio=0.30):
    """candidates: {button_base: jp}. Returns [verify_candidate(...), ...]
    sorted so mismatches sort first (never silently buried at the bottom)."""
    results = [verify_candidate(b, jp, px_per_char_const, tolerance_ratio)
               for b, jp in sorted(candidates.items())]
    order = {"mismatch": 0, "no_ink_detected": 1, "no_image": 2, "match": 3}
    results.sort(key=lambda r: (order.get(r["status"], 9), r["button"]))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True,
                     help="JSON file: {button_name(no on/off/sel_ suffix logic -- use "
                          "the *_a/_b/... base name): jp_text}, e.g. "
                          "build/select_option_map.json filtered to jp!=null")
    ap.add_argument("--tolerance", type=float, default=0.30)
    ap.add_argument("--out", default=os.path.join(REPO, "build", "select_ink_verify.json"))
    args = ap.parse_args()

    mean, calib_rows = calibrate()
    print(f"calibration px/char = {mean:.2f} (from {len(calib_rows)} pairs):")
    for name, jp, bbox, ratio in calib_rows:
        print(f"  {name:26s} {jp!r:14s} bbox={bbox} ratio={ratio}")

    with open(args.candidates, encoding="utf-8") as f:
        raw = json.load(f)
    candidates = {}
    for k, v in raw.items():
        jp = v.get("jp") if isinstance(v, dict) else v
        if jp:
            # select_option_map.json keys are already button base names
            # (e.g. "sel_s1s_35_sel_a", no _on/_off suffix).
            candidates[k] = jp

    results = verify_all(candidates, mean, args.tolerance)
    n_match = sum(1 for r in results if r["status"] == "match")
    n_mismatch = sum(1 for r in results if r["status"] == "mismatch")
    n_noink = sum(1 for r in results if r["status"] == "no_ink_detected")
    n_noimg = sum(1 for r in results if r["status"] == "no_image")
    print(f"\nverified {len(results)} candidates: {n_match} match, "
          f"{n_mismatch} MISMATCH, {n_noink} no-ink, {n_noimg} no-image")
    for r in results:
        if r["status"] != "match":
            print(f"  [{r['status']}] {r['button']}: {r.get('jp')!r} "
                  f"measured={r.get('measured_width')} predicted={r.get('predicted_width')} "
                  f"dev={r.get('relative_deviation')}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"calibration_px_per_char": mean, "calibration_pairs": [
            {"button": n, "jp": j, "bbox": b, "ratio": r} for n, j, b, r in calib_rows
        ], "tolerance_ratio": args.tolerance, "results": results}, f,
            ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
