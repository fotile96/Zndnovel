"""tools/derive_select.py -- lua-driven JP text recovery for png/select/
option buttons.

Coverage strategy: real lua_scripts/*.lua data is the fixture (this module
is a code-flow reverse-engineering tool; a synthetic mini-lua fixture would
not exercise the real indentation/nesting shapes this depends on). Every
test pins a fact independently cross-checked this round -- either against
lua_scripts/ line numbers quoted in the report, or (for a few) against the
actual png/select/*.png pixels (see tools/select_layout.py's docstring for
why pixel cross-checking matters: this module's chase logic can execute
with zero bugs and still land on the wrong string, because the underlying
assumption -- "the scene you land on is titled with what the button said"
-- is only sometimes true).
"""
import pytest

from tools.derive_select import (
    SPECIAL_CASES,
    UNRESOLVED_COMPOUND,
    UNRESOLVED_EMPTY_BODY,
    UNRESOLVED_NESTED_SELECT,
    UNRESOLVED_SHARED_ELSE_EMPTY,
    chase_doscriptscene,
    derive_from_body,
    find_calls,
    find_var_dispatch,
    resolve_all,
    resolve_file,
)


# ---------------------------------------------------------------------------
# 1. find_calls: raw comDlgSelectItem parsing.
# ---------------------------------------------------------------------------

def test_find_calls_s1s_35_has_three_options_with_receiver():
    """lua_scripts/snr_s1_10_s.lua ~2755-2762: the very first 3-way choice
    in the game (CLAUDE.md: "s1s_35_sel 三选：约束/想不起/没约"). Two call
    sites (card-held branches), both must expose the same 3 (name, value)
    pairs and a v-register receiver (not an inline compare)."""
    calls = find_calls("snr_s1_10_s.lua")
    matches = [c for c in calls
               if any(name == "sel_s1s_35_sel_c" for name, *_ in c["options"])]
    assert matches, "expected at least one call site offering sel_s1s_35_sel_c"
    call = matches[0]
    names = [n for n, *_ in call["options"]]
    assert "sel_s1s_35_sel_a" in names
    assert "sel_s1s_35_sel_b" in names
    assert "sel_s1s_35_sel_c" in names
    values = {n: v for n, _x, _y, v in call["options"]}
    assert values["sel_s1s_35_sel_a"] == 1
    assert values["sel_s1s_35_sel_b"] == 2
    assert values["sel_s1s_35_sel_c"] == 3
    assert call["receiver"] is not None and call["receiver"].startswith("v")


def test_find_calls_inline_compare_form_s2s_193c():
    """lua_scripts/snr_s2_10_s.lua:2864 -- `if comDlgSelectItem(...) == 2
    then` -- the bare-inline-compare shape (no `vNN =` receiver), distinct
    from the assignment shape every other call in this codebase uses.
    Regression: if the paren-balancing scanner in find_calls mishandles
    this, receiver stays None AND inline_value stays None, which would
    silently degrade this call to "no_chain" instead of resolving via
    find_inline_dispatch."""
    calls = find_calls("snr_s2_10_s.lua")
    matches = [c for c in calls
               if any(name == "sel_s2s_193c_sel_a" for name, *_ in c["options"])]
    assert matches
    call = matches[0]
    assert call["receiver"] is None
    assert call["inline_value"] == 2


# ---------------------------------------------------------------------------
# 2. End-to-end resolution -- known-good cases (matches independently
#    confirmed this round, see the report).
# ---------------------------------------------------------------------------

def test_resolve_s1s_35_all_three_options_exact():
    """The one example CLAUDE.md/the inventory doc explicitly says was
    manually eyeballed against the real pixels: sel_s1s_35_sel_a ==
    "約束を思い出せない" verbatim. b/c are cross-checked against
    card_msg's "『放課後の約束』の分岐（約束をしていない、している）"."""
    result = resolve_file("snr_s1_10_s.lua")
    assert result["sel_s1s_35_sel_a"]["jp"] == "約束を思い出せない"
    assert result["sel_s1s_35_sel_b"]["jp"] == "約束をしている"
    assert result["sel_s1s_35_sel_c"]["jp"] == "約束をしていない"
    for name in ("sel_s1s_35_sel_a", "sel_s1s_35_sel_b", "sel_s1s_35_sel_c"):
        assert result[name]["how"] is not None
        assert result[name]["reason"] is None


def test_resolve_cross_file_run_jump_s1s_260_sel_a():
    """sel_s1s_260_sel_a: v49==1 -> doScriptScene="s1s_270" (same file) ->
    that branch itself reassigns doScriptScene="s5s_10" and RUN-jumps to
    snr_s5_10_s.lua -- the chase must follow the file switch and keep
    going, landing on snr_s5_10_s.lua's "s5s_10"->"s5s_20" dispatch chain,
    whose scene_s5s_20(...) call is titled "サクラさん"
    (lua_scripts/snr_s5_10_s.lua:2352). This is the one case in the current
    real-data run that needs BOTH a same-file doScriptScene re-chase AND a
    RUN file switch, back to back -- see derive_select.py's module
    docstring "1." for why this two-hop shape has to be handled, not just
    single-hop same-file chases."""
    result = resolve_file("snr_s1_10_s.lua")
    rec = result["sel_s1s_260_sel_a"]
    assert rec["jp"] == "サクラさん"
    assert "跨文件" in rec["how"]


# ---------------------------------------------------------------------------
# 3. Structurally-unresolvable cases -- must report a SPECIFIC reason, not
#    just None, and must never fabricate a wrong-length guess.
# ---------------------------------------------------------------------------

def test_resolve_compound_condition_is_reported_not_guessed():
    """sel_s2s_192a_sel_a/b/c (lua_scripts/snr_s2_10_s.lua:2830): the
    dispatch is `if (v60 == 1) and (v61 == 1) then`, a joint two-variable
    condition, not a simple `if v60 == K then` chain. This module
    deliberately does not attempt joint-variable dispatch (see
    find_var_dispatch's docstring) -- these are nazotoki answer-correctness
    checks, not per-option scene titles. Must resolve to None with the
    UNRESOLVED_COMPOUND reason, not silently fall through to some other
    (wrong) branch."""
    result = resolve_file("snr_s2_10_s.lua")
    for name in ("sel_s2s_192a_sel_a", "sel_s2s_192a_sel_b", "sel_s2s_192a_sel_c"):
        assert result[name]["jp"] is None
        assert result[name]["reason"] == UNRESOLVED_COMPOUND


def test_resolve_shared_else_with_title_is_flagged_low_confidence():
    """sel_s2s_190_sel_c: v50's dispatch only tests ==1 and ==2 EXPLICITLY
    as top-level branches; button c's value (3) -- and the "card not held"
    default v50=0 -- both fall through to the final implicit `else`, which
    leads straight into the nazotoki maze (scene_s2s_190_sel_2(...,
    "ナゾトキ１")). That title is real, derivable text -- but it is NOT
    button c's own caption (it describes the maze scene that follows,
    shared by every value that isn't 1 or 2), so it must be flagged as a
    shared/low-confidence attribution, not presented with the same
    confidence as a value that got its own explicit branch. This is
    exactly the button the round's ink-span check independently flags as a
    MISMATCH (measured ink width 114px vs a 5-char "ナゾトキ１" prediction
    of 83px) -- the low-confidence flag and the pixel check agree."""
    result = resolve_file("snr_s2_10_s.lua")
    rec = result["sel_s2s_190_sel_c"]
    assert rec["jp"] == "ナゾトキ１"
    assert "共享" in rec["how"]


def test_resolve_shared_else_with_no_title_is_still_reported_unresolved():
    """sel_s3s_230h_sel_b/c (lua_scripts/snr_s3_10_s.lua:2694-2701): both
    fall into a shared `else` whose body is a plain vms()-only scene with
    no scene_X()/doScriptScene literal at all -- genuinely no text to
    recover, must stay None with a specific reason, not silently guessed
    from button a's branch."""
    result = resolve_file("snr_s3_10_s.lua")
    for name in ("sel_s3s_230h_sel_b", "sel_s3s_230h_sel_c"):
        rec = result[name]
        assert rec["jp"] is None
        assert rec["reason"] in (UNRESOLVED_SHARED_ELSE_EMPTY, UNRESOLVED_EMPTY_BODY,
                                  UNRESOLVED_NESTED_SELECT)


# ---------------------------------------------------------------------------
# 4. Coverage-shape regression: BOTH recovery shapes must be implemented.
#    This directly encodes the round's "解析器只认一种分支形态" mutation.
# ---------------------------------------------------------------------------

def test_direct_scene_call_in_body_resolves_without_chase():
    """derive_from_body must recognize the "title right there in the
    branch" shape (scene_X(id, "title") as the FIRST hit in the body) and
    NOT require a doScriptScene chase for it -- this is shape 2 from the
    module docstring. Uses a minimal literal body so this test does not
    depend on which real branch happens to use this shape today."""
    body = ['                    scene_foo_bar(doScriptScene, "选项直接标题")']
    title, how, reason = derive_from_body("snr_s1_10_s.lua", body)
    assert title == "选项直接标题"
    assert how == "就地场景调用"
    assert reason is None


def test_doscriptscene_only_body_requires_chase():
    """The other shape: body only sets doScriptScene, title lives
    elsewhere. chase_doscriptscene must be invoked (not skipped) --
    verified end-to-end via a real chain: sel_s2s_190_sel_a
    (lua_scripts/snr_s2_10_s.lua:2815-2822, `v50==1` ->
    doScriptScene="s2s_208" -> scene_s2s_208(...,"ナゾトキの正解"))."""
    result = resolve_file("snr_s2_10_s.lua")
    rec = result["sel_s2s_190_sel_a"]
    assert rec["jp"] == "ナゾトキの正解"
    assert rec["how"] == "目标场景名"


def test_full_run_coverage_floor_needs_both_shapes():
    """Coverage-floor regression for the mutation "解析器只认一种分支形态
    （覆盖率应显著下降）": resolve_all() must clear a floor that is NOT
    reachable with only one of the two shapes. Measured this round: 81/114
    resolved with both shapes; form-2-only (direct scene_X in body) or
    form-1-only (doScriptScene chase) each individually resolve
    meaningfully fewer (per the inventory doc's own account, "只认第一种
    覆盖率 34%，两种都认 51%" for the prior crude parser -- this module's
    stricter/indentation-based version resolves more per-shape than that,
    but the same ordering must hold: both > either alone). This test pins
    the CURRENT full-both-shapes count as a floor; a change that silently
    disables either shape will drop well below it."""
    merged = resolve_all()
    resolved = sum(1 for r in merged.values() if r["jp"])
    assert resolved >= 79, (
        f"only {resolved}/{len(merged)} resolved with both recovery shapes "
        f"enabled -- expected >=75 (measured 81 this round); a regression "
        f"here likely means one of the two shapes (direct scene_X() call, "
        f"or doScriptScene chase) stopped firing")


def test_special_cases_present_in_resolve_all():
    """sel_voice1_sel_a/sel_voice2_sel_a (480x82 prologue voice-choice
    buttons) are not reachable via the general chase (both branches just
    play two vms() lines inline, no scene_X()/doScriptScene at all -- see
    SPECIAL_CASES' docstring) but ARE mechanically recoverable via a
    different, manually-confirmed rule. Must appear in resolve_all()'s
    output with the documented text, not silently dropped because the
    general chase found nothing."""
    merged = resolve_all()
    for name, expected in SPECIAL_CASES.items():
        assert merged[name]["jp"] == expected["jp"]


# ---------------------------------------------------------------------------
# 5. find_var_dispatch: compound vs simple detection in isolation (does not
#    depend on which real branch currently uses which shape).
# ---------------------------------------------------------------------------

def test_nested_if_inside_else_is_flattened_like_elseif():
    """Regression for a real bug this round's tests caught: lua_scripts/
    snr_s2_10_s.lua:2814-2886 renders what is semantically `if v50==1 then
    ... elseif v50==2 then ... else ... end` as a BARE `else` whose entire
    body is one nested `if v50==2 then ... else ... end` -- a decompiler
    idiom used throughout this codebase (unluac-style output does not
    always fold cascading conditions back into `elseif`). Before the fix,
    find_var_dispatch treated the whole nested construct as one opaque
    'else' bucket, so value 2 (sel_s2s_190_sel_b) silently inherited value
    3's/the-maze's shared-else text instead of its OWN explicit branch's
    "ナゾトキの間違い" (lua_scripts/snr_s2_10_s.lua:2819-2821). This
    specifically checks that a value with its own nested-if arm is NOT
    lumped into the outer 'else' bucket."""
    result = resolve_file("snr_s2_10_s.lua")
    rec_b = result["sel_s2s_190_sel_b"]
    assert rec_b["jp"] == "ナゾトキの間違い"
    assert "共享" not in (rec_b["how"] or "")


def test_find_var_dispatch_reports_compound_status():
    calls = find_calls("snr_s2_10_s.lua")
    call = next(c for c in calls
                if any(n == "sel_s2s_192a_sel_a" for n, *_ in c["options"]))
    branches, status = find_var_dispatch("snr_s2_10_s.lua", call)
    assert status == "compound"
    assert branches == {}
