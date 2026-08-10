"""tools/select_layout.py -- pixel-level measurement + ink-span
cross-verification for png/select/ option buttons.

Why this module's tests matter more than usual: this round's whole point
was proving that tools/derive_select.py's code-chase derivation can be
100% syntactically correct and still land on the wrong string (see that
module's report and tests/test_derive_select.py's shared-else cases). The
ink-span check is the ONLY independent signal this repo has for catching
that failure mode -- so a regression here (the check silently passing
everything, or the mismatch list getting dropped before it reaches a
human) is exactly the kind of "safety gate goes quiet at the moment it
matters most" failure CLAUDE.md warns about. Every test below is anchored
to a real, manually-confirmed png/select/*.png pixel fact (see the report
for how each was confirmed), not a synthetic fixture -- this module's job
is to measure real assets, so its tests should measure real assets.
"""
import pytest

from tools.select_layout import (
    CALIBRATION_PAIRS,
    calibrate,
    ink_bbox,
    px_per_char,
    verify_all,
    verify_candidate,
)


# ---------------------------------------------------------------------------
# 1. ink_bbox: pinned against real pixels (regression -- if the dynamic
#    frame-palette collection ever misclassifies border/fill as ink, or
#    vice versa, this catches the drift immediately).
# ---------------------------------------------------------------------------

def test_ink_bbox_s1s_35_sel_a_matches_measured_extent():
    """sel_s1s_35_sel_a_off.png: "約束を思い出せない" (9 chars), the one
    button independently eyeballed against the real pixels both by the
    original inventory doc AND this round (see the report). Bbox measured
    directly this round via a 6x-upscaled crop read."""
    bbox = ink_bbox("sel_s1s_35_sel_a_off")
    assert bbox == (50, 3, 198, 22)


def test_ink_bbox_excludes_icon_zone_not_text():
    """The icon/notch/border template (x<15) is IDENTICAL across every
    button (see the report's byte-equality check across sel_s1s_35_sel_a/
    b/c) -- ink_bbox must never report text starting inside that zone for
    a real button, or it would be conflating decorative template pixels
    with actual caption ink."""
    for name in ("sel_s1s_35_sel_a_off", "sel_s1s_35_sel_b_off", "sel_s1s_35_sel_c_off"):
        bbox = ink_bbox(name)
        assert bbox is not None
        assert bbox[0] >= 15


def test_ink_bbox_none_for_nonexistent_ink_zone_is_never_silently_wrong():
    """Sanity floor: every real off-image in the calibration set must
    detect SOME ink (a None here would mean the frame-palette collection
    swallowed the whole image as "background", the most dangerous failure
    mode for this module since it would silently make every verification
    downstream report 'no_ink_detected' instead of a real measurement)."""
    for name, _jp, _src in CALIBRATION_PAIRS:
        assert ink_bbox(name) is not None


# ---------------------------------------------------------------------------
# 2. Calibration: the px/char constant must stay in the tight band actually
#    measured this round. A drift here means either the font/asset changed
#    (real news, should be investigated) or ink_bbox regressed.
# ---------------------------------------------------------------------------

def test_calibration_pairs_cluster_tightly():
    mean, rows = calibrate()
    assert 16.0 <= mean <= 17.2
    for _name, _jp, _bbox, ratio in rows:
        assert ratio is not None
        assert 15.0 <= ratio <= 18.0, (
            f"calibration pair ratio {ratio} fell outside the tight band "
            f"measured this round -- see module docstring CALIBRATION_PAIRS")


def test_px_per_char_basic_arithmetic():
    assert px_per_char((10, 0, 109, 20), 5) == 20.0  # (109-10+1)/5
    assert px_per_char(None, 5) is None
    assert px_per_char((0, 0, 9, 9), 0) is None


# ---------------------------------------------------------------------------
# 3. verify_candidate / verify_all: the actual cross-check. Anchored to the
#    two confirmed-wrong derivations from this round (the code-chase landed
#    on the FOLLOWING scene's title, not the button's own caption) and one
#    confirmed-right one, so a regression that makes the check pass
#    everything (or fail everything) is caught either direction.
# ---------------------------------------------------------------------------

def test_verify_candidate_flags_known_wrong_derivation_s5s_350_sel_a():
    """The report's headline finding: sel_s5s_350_sel_a's code-chase
    derivation is "ナースコールのボタン" (the FOLLOWING scene's own title,
    lua_scripts/snr_s5_10_s.lua:2432) but the button's real pixels say
    "無理はしない" (confirmed by direct upscaled-crop reading this round;
    that exact string does not appear anywhere in lua_scripts/ per grep).
    Feeding the WRONG derived string in must flag 'mismatch'."""
    mean, _ = calibrate()
    result = verify_candidate("sel_s5s_350_sel_a", "ナースコールのボタン", mean)
    assert result["status"] == "mismatch"


def test_verify_candidate_accepts_known_right_derivation_s5s_350_sel_b():
    """The same scene's OTHER button (sel_s5s_350_sel_b) is a case where
    the code-chase answer happens to be correct ("がんばってみる" is both
    the branch's scene_X() title AND the real button text, confirmed by
    direct pixel read) -- must NOT be flagged."""
    mean, _ = calibrate()
    result = verify_candidate("sel_s5s_350_sel_b", "がんばってみる", mean)
    assert result["status"] == "match"


def test_verify_candidate_no_image_for_unknown_button():
    mean, _ = calibrate()
    result = verify_candidate("sel_does_not_exist_anywhere", "占位", mean)
    assert result["status"] == "no_image"


def test_verify_all_never_silently_drops_mismatches():
    """The core "safety gate must not go quiet" property: verify_all must
    surface EVERY mismatch in its returned list (not just a count, not
    just the first N) and sort them to the front so a caller printing only
    the first few results still sees them. Uses the two real confirmed
    cases (one wrong, one right) plus a synthetic clearly-wrong pair so
    this test doesn't depend on how many real buttons happen to mismatch
    today."""
    mean, _ = calibrate()
    candidates = {
        "sel_s5s_350_sel_a": "ナースコールのボタン",  # known wrong (long guess)
        "sel_s5s_350_sel_b": "がんばってみる",         # known right
        "sel_s1s_35_sel_a": "全然関係ない長い日本語の文章です",  # synthetic, obviously wrong length
    }
    results = verify_all(candidates, mean)
    statuses = {r["button"]: r["status"] for r in results}
    assert statuses["sel_s5s_350_sel_a"] == "mismatch"
    assert statuses["sel_s5s_350_sel_b"] == "match"
    assert statuses["sel_s1s_35_sel_a"] == "mismatch"
    # mismatches must sort before matches (never buried where a truncated
    # printout -- e.g. "print only the first 5" -- would hide them)
    mismatch_positions = [i for i, r in enumerate(results) if r["status"] == "mismatch"]
    match_positions = [i for i, r in enumerate(results) if r["status"] == "match"]
    assert max(mismatch_positions) < min(match_positions)


def test_verify_all_reports_every_candidate_exactly_once():
    """No silent truncation of the candidate set itself."""
    mean, _ = calibrate()
    candidates = {f"sel_s1s_35_sel_{c}": jp for c, jp in
                  zip("abc", ["約束を思い出せない", "約束をしている", "約束をしていない"])}
    results = verify_all(candidates, mean)
    assert len(results) == len(candidates)
    assert {r["button"] for r in results} == set(candidates)
