"""tools/derive_select.py -- lua-driven JP text recovery for png/select/
option buttons.

Coverage strategy: real lua_scripts/*.lua data is the fixture (this module
is a code-flow reverse-engineering tool; a synthetic mini-lua fixture would
not exercise the real indentation/nesting shapes this depends on). Every
test pins a fact independently cross-checked -- either against
lua_scripts/ source quoted in the report, or (for a few) against the
actual png/select/*.png pixels (see tools/select_layout.py's docstring for
why pixel cross-checking matters: this module's chase logic can execute
with zero bugs and still land on the wrong string, because the underlying
assumption -- "the scene you land on is titled with what the button said"
-- is only sometimes true).

Two shapes this module tolerates have NO fixture in the 2026-08-31
decompiler base (`else` whose whole body is a nested `if var == K`, and the
bare `if comDlgSelectItem(...) == K then` inline-compare call form). They
are pinned by synthetic fixture files instead of being left untested --
see `_synthetic_file`.

**Line numbers are deliberately not asserted anywhere.** The 2026-08-31
base migration re-printed every file, so line numbers are not a stable
anchor across bases (docs/ops/decompiler-base-migration-2026-08-31.md);
button names, scene titles and function names are.
"""
import re

import pytest

import tools.derive_select as ds
from tools.derive_select import (
    SPECIAL_CASES,
    UNRESOLVED_COMPOUND,
    UNRESOLVED_EMPTY_BODY,
    UNRESOLVED_NESTED_SELECT,
    UNRESOLVED_NO_CHAIN,
    UNRESOLVED_SHARED_ELSE_EMPTY,
    chase_doscriptscene,
    derive_from_body,
    find_calls,
    find_inline_dispatch,
    find_var_dispatch,
    resolve_all,
    resolve_file,
)


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    """Write a synthetic lua file and point the module at it. Used ONLY for
    the two decompiler shapes that this base no longer emits -- the module
    still handles them, so they still get a red-able test."""
    def _write(name, body):
        (tmp_path / name).write_text(body, encoding="utf-8")
        monkeypatch.setattr(ds, "SCRIPT_DIR", str(tmp_path))
        ds.clear_caches()
        return name
    yield _write
    ds.clear_caches()


# ---------------------------------------------------------------------------
# 1. find_calls: raw comDlgSelectItem parsing.
# ---------------------------------------------------------------------------

def test_find_calls_s1s_35_has_three_options_with_receiver():
    """snr_s1_10_s.lua: the very first 3-way choice in the game (CLAUDE.md:
    "s1s_35_sel 三选：约束/想不起/没约"). Two call sites (card-held
    branches), both must expose the same 3 (name, value) pairs and a plain
    variable receiver.

    Receiver-shape regression for the 2026-08-31 base: names went from
    `v\\d+` to `l<depth>_<reg>`. The old `^(?:local )?(v\\d+) =$` receiver
    regex matched NOTHING in the new base, degrading all 114 buttons to
    "no_chain" (measured: 2/114 resolved). Assert a real identifier is
    captured -- not that it starts with any particular letter."""
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
    assert call["receiver"] is not None
    assert re.fullmatch(r"[A-Za-z_]\w*", call["receiver"]), call["receiver"]


def test_every_real_call_site_has_a_plain_variable_receiver():
    """The 2026-08-31 base assigns EVERY comDlgSelectItem result to a plain
    variable (76 x `l<depth>_<reg>`, 3 x the hand-named globals retSelect /
    retSelect2) -- the old base's bare `if comDlgSelectItem(...) == K then`
    inline-compare form is gone. Pinning this makes the receiver regex's
    generality load-bearing: if it ever narrows back to `v\\d+`, or starts
    accepting table fields like `gameSave.x`, this goes red."""
    seen = 0
    for fname in ds.CALL_FILES:
        for call in find_calls(fname):
            seen += 1
            assert call["receiver"] is not None, (fname, call["line_start"])
            assert "." not in call["receiver"]
            assert call["inline_value"] is None
    assert seen == 79, f"expected 79 real call sites in this base, saw {seen}"


def test_inline_compare_call_shape_is_still_understood(synthetic):
    """`if comDlgSelectItem(...) == K then ... else ... end` -- the shape the
    OLD base used for sel_s2s_193c (and which a future decompiler could emit
    again). No real fixture exists in this base, so pin the tolerance with a
    synthetic one rather than deleting the code path untested."""
    name = synthetic("fake_inline.lua", '\n'.join([
        'main = function()',
        '    if comDlgSelectItem(false, true, "sel_fake_sel_a", 1, 2, 1) == 1 then',
        '        scene_fake_yes(doScriptScene, "はい")',
        '    else',
        '        scene_fake_no(doScriptScene, "いいえ")',
        '    end',
        'end',
    ]))
    call = find_calls(name)[0]
    assert call["receiver"] is None
    assert call["inline_value"] == 1
    branches = find_inline_dispatch(name, call)
    assert set(branches) == {1, "else"}
    result = resolve_file(name)
    assert result["sel_fake_sel_a"]["jp"] == "はい"


# ---------------------------------------------------------------------------
# 2. End-to-end resolution -- known-good cases (matches independently
#    confirmed, and byte-identical across the 2026-08-31 base migration).
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
    """sel_s1s_260_sel_a: value 1 -> doScriptScene="s1s_270" (same file) ->
    that branch itself reassigns doScriptScene="s5s_10" and RUN-jumps to
    snr_s5_10_s.lua -- the chase must follow the file switch and keep
    going, landing on snr_s5_10_s.lua's "s5s_10"->"s5s_20" dispatch chain,
    whose scene_s5s_20(...) call is titled "サクラさん". This is the one
    case in the current real-data run that needs BOTH a same-file
    doScriptScene re-chase AND a RUN file switch, back to back -- see
    derive_select.py's module docstring "1." for why this two-hop shape has
    to be handled, not just single-hop same-file chases."""
    result = resolve_file("snr_s1_10_s.lua")
    rec = result["sel_s1s_260_sel_a"]
    assert rec["jp"] == "サクラさん"
    assert "跨文件" in rec["how"]


def test_chase_doscriptscene_direct_hit_and_miss():
    """The chase itself, in isolation: a scene id that IS in the dispatcher
    returns its title at hop 0; one that is not returns a reason, never a
    guess."""
    title, how, reason = chase_doscriptscene("snr_s2_10_s.lua", "s2s_208")
    assert title == "ナゾトキの正解"
    assert how == "目标场景名"
    assert reason is None
    title, _how, reason = chase_doscriptscene("snr_s2_10_s.lua", "s2s_not_a_scene")
    assert title is None
    assert reason is not None


# ---------------------------------------------------------------------------
# 3. Structurally-unresolvable cases -- must report a SPECIFIC reason, not
#    just None, and must never fabricate a wrong-length guess.
# ---------------------------------------------------------------------------

def test_resolve_joint_two_select_dispatch_is_reported_not_guessed():
    """sel_s2s_192a_* / sel_s2s_192b_* (and the 193a/193b pair): the
    nazotoki answer-correctness check, where TWO selects are issued
    back-to-back and their results tested together. The old base printed it
    as `if (v60 == 1) and (v61 == 1) then` -- a compound condition
    find_var_dispatch rejected on sight. The 2026-08-31 base prints the
    same bytecode as `if l1_5 == 1 then / if l1_6 == 1 then`, i.e. two
    textually ordinary single-variable dispatches.

    This is the single highest-stakes regression in the whole migration: a
    parser reading them at face value resolves all six buttons to the
    enclosing maze scene's title ("ナゾトキ１"), which is emphatically NOT
    what these puzzle-answer buttons say. They must stay None with the
    UNRESOLVED_COMPOUND reason."""
    result = resolve_file("snr_s2_10_s.lua")
    joint = [f"sel_s2s_192{grp}_sel_{sfx}"
             for grp in ("a", "b") for sfx in ("a", "b", "c")]
    joint += [f"sel_s2s_193{grp}_sel_{sfx}"
              for grp in ("a", "b") for sfx in ("a", "b", "c", "d")]
    assert len(joint) == 14
    for name in joint:
        assert result[name]["jp"] is None, name
        assert result[name]["reason"] == UNRESOLVED_COMPOUND, name


def test_nested_submenu_is_not_misread_as_joint_dispatch():
    """The other side of the joint-dispatch guard: it must not over-fire.
    sel_s2s_192c_* is the puzzle's THIRD question, issued only after the
    first two were answered -- its own `if l1_7 == 2 then` test is a plain
    single-variable dispatch that happens to sit inside the already-resolved
    tests of the first two. Every enclosing test comes BEFORE this select's
    own call, which is exactly what `_is_joint_dispatch` requires NOT to be
    the case; so 192c must go down the normal resolution path (value 2 gets
    its own branch, values 1/3 the shared fall-through), never
    UNRESOLVED_COMPOUND. A guard that fired here would cost 4 buttons."""
    result = resolve_file("snr_s2_10_s.lua")
    for name in ("sel_s2s_192c_sel_a", "sel_s2s_192c_sel_b", "sel_s2s_192c_sel_c"):
        assert result[name]["reason"] != UNRESOLVED_COMPOUND, name
    assert result["sel_s2s_192c_sel_b"]["reason"] == UNRESOLVED_EMPTY_BODY


def test_resolve_shared_else_with_title_is_flagged_low_confidence():
    """sel_s2s_190_sel_c: the dispatch tests ==1 and ==2 explicitly; button
    c's value (3) -- and the "card not held" default 0 -- both fall through
    to the final `else`, which leads straight into the nazotoki maze
    (scene_s2s_190_sel_2(..., "ナゾトキ１")). That title is real, derivable
    text -- but it is NOT button c's own caption (it describes the maze
    scene that follows, shared by every value that isn't 1 or 2), so it must
    be flagged as a shared/low-confidence attribution, not presented with
    the same confidence as a value that got its own explicit branch. This is
    exactly the button the ink-span check independently flags as a MISMATCH
    (measured ink width 114px vs a 5-char "ナゾトキ１" prediction of 83px)
    -- the low-confidence flag and the pixel check agree."""
    result = resolve_file("snr_s2_10_s.lua")
    rec = result["sel_s2s_190_sel_c"]
    assert rec["jp"] == "ナゾトキ１"
    assert "共享" in rec["how"]


def test_implicit_fallthrough_is_treated_as_a_shared_else():
    """sel_s2s_192c_sel_a/c: the 2026-08-31 base prints
    `if l1_7 == 2 then <win> end` with NO else -- the retry path that the
    old base printed as an `else` arm is now just the statements that follow,
    two block levels further out (`scene_s2s_190_sel_5(..., "ナゾトキ１")`).
    Same control flow, so the same answer AND the same low-confidence tag as
    before the migration: dropping this handling silently turns 4 buttons
    (192c a/c, 193c a/c) from "flagged low-confidence guess" into
    "unresolved", and mis-scoping it (e.g. refusing to walk out of the
    enclosing `if`s) does the same."""
    result = resolve_file("snr_s2_10_s.lua")
    for name in ("sel_s2s_192c_sel_a", "sel_s2s_192c_sel_c"):
        assert result[name]["jp"] == "ナゾトキ１", name
        assert "共享" in result[name]["how"], name
    for name in ("sel_s2s_193c_sel_a", "sel_s2s_193c_sel_c"):
        assert result[name]["jp"] == "ナゾトキ２", name
        assert "共享" in result[name]["how"], name


def test_fallthrough_does_not_escape_a_loop(synthetic):
    """`_fallthrough_region` must give up (None) rather than attribute the
    statements after a LOOP's `end` to the untested values: when the chain
    sits at the tail of a `while` body, the next thing that runs is another
    iteration, not those statements. Without this guard the maze-retry
    handling above would happily reach out of the loop and hand a button the
    title of whatever scene follows the puzzle."""
    name = synthetic("fake_loop.lua", '\n'.join([
        'main = function()',
        '    local l1_1 = 0',
        '    while l1_1 == 0 do',
        '        local l1_2 = 0',
        '        l1_2 = comDlgSelectItem(false, "sel_fake_sel_a", 1, 2, 1, "sel_fake_sel_b", 3, 4, 2)',
        '        if l1_2 == 1 then',
        '            l1_1 = 1',
        '        end',
        '    end',
        '    scene_after_loop(doScriptScene, "ループの外")',
        'end',
    ]))
    result = resolve_file(name)
    assert result["sel_fake_sel_b"]["jp"] is None
    assert result["sel_fake_sel_b"]["jp"] != "ループの外"


def test_sibling_if_statements_form_one_dispatch_chain():
    """sel_s5s_80_sel_a/b/c: three rumour options. The OLD base printed the
    dispatch as three sibling `if v46 == K then ... end` statements rather
    than an elseif chain, and the old chain walker stopped dead at the first
    `end` -- so b and c were reported "value has no explicit branch" (a real
    miss, not a real unresolvable). The chain walker now continues across a
    closing `end` when the next code line is another simple test on the same
    variable at the same indent, so all three values resolve to their OWN
    branch's scene title. (This base happens to print them as an elseif
    chain; the sibling-`if` form is still live elsewhere, e.g.
    sel_s3s_230h/230l.)"""
    result = resolve_file("snr_s5_10_s.lua")
    assert result["sel_s5s_80_sel_a"]["jp"] == "花が咲き乱れる"
    assert result["sel_s5s_80_sel_b"]["jp"] == "人が落ちてくる"
    assert result["sel_s5s_80_sel_c"]["jp"] == "雪が降るって言うウワサ"
    for name in ("sel_s5s_80_sel_a", "sel_s5s_80_sel_b", "sel_s5s_80_sel_c"):
        assert "共享" not in (result[name]["how"] or ""), name


def test_sibling_if_chain_keeps_each_value_separate_s3s_230h():
    """sel_s3s_230h_sel_a/b/c really are printed as three sibling `if
    l1_8 == K then ... end` statements in this base. Each value must get its
    OWN branch (all three bodies call an argument-less
    `scene_s3s_dispatch_vNN()` helper with no title, so all three are
    honestly unresolvable) -- never one value's text spread across the
    others."""
    result = resolve_file("snr_s3_10_s.lua")
    for name in ("sel_s3s_230h_sel_a", "sel_s3s_230h_sel_b", "sel_s3s_230h_sel_c"):
        rec = result[name]
        assert rec["jp"] is None, name
        assert rec["reason"] in (UNRESOLVED_SHARED_ELSE_EMPTY, UNRESOLVED_EMPTY_BODY,
                                 UNRESOLVED_NESTED_SELECT), (name, rec["reason"])


def test_sibling_if_statements_each_keep_their_own_title(synthetic):
    """Direct proof that the sibling-`if` chain walk is load-bearing, which
    the real fixtures cannot give: in lua_scripts/ every sibling-`if`
    dispatch happens to have title-less bodies, so removing the walk merely
    changes which "unresolved" reason is reported. Here each arm carries its
    own title, so a walker that stops at the first `end` gives values 2 and
    3 the WRONG text (the fall-through's) instead of their own."""
    name = synthetic("fake_siblings.lua", '\n'.join([
        'main = function()',
        '    local l1_2 = 0',
        '    l1_2 = comDlgSelectItem(false, "sel_fake_sel_a", 1, 2, 1, "sel_fake_sel_b", 3, 4, 2, "sel_fake_sel_c", 5, 6, 3)',
        '    if l1_2 == 1 then',
        '        scene_a(doScriptScene, "一番目")',
        '    end',
        '    if l1_2 == 2 then',
        '        scene_b(doScriptScene, "二番目")',
        '    end',
        '    if l1_2 == 3 then',
        '        scene_c(doScriptScene, "三番目")',
        '    end',
        '    scene_after(doScriptScene, "落ちてきた先")',
        'end',
    ]))
    result = resolve_file(name)
    assert result["sel_fake_sel_a"]["jp"] == "一番目"
    assert result["sel_fake_sel_b"]["jp"] == "二番目"
    assert result["sel_fake_sel_c"]["jp"] == "三番目"
    for sfx in ("a", "b", "c"):
        assert "共享" not in (result[f"sel_fake_sel_{sfx}"]["how"] or ""), sfx


def test_scope_bound_blocks_a_later_unrelated_reuse_of_the_name(synthetic):
    """Direct proof that `_scope_bound_indent` is load-bearing, which the
    real fixtures cannot give today (the only undispatched receivers are the
    `retSelect` confirms in snr_s4_10_fb.lua, a file with no other
    `if retSelect == K` to latch onto). The 2026-08-31 base reuses one name
    (`l1_2`) across ~56 unrelated call sites per file, so an unbounded
    forward search WILL eventually find a same-named test belonging to a
    different variable in a different block and attribute its scene title to
    this button."""
    name = synthetic("fake_reuse.lua", '\n'.join([
        'main = function()',
        '    if doScriptScene == "a" then',
        '        local l1_2 = 0',
        '        l1_2 = comDlgSelectItem(false, "sel_fake_sel_a", 1, 2, 1)',
        '    elseif doScriptScene == "b" then',
        '        local l1_2 = 0',
        '        l1_2 = comDlgSelectItem(false, "sel_other_sel_a", 1, 2, 1)',
        '        if l1_2 == 1 then',
        '            scene_other(doScriptScene, "別のブロックの見出し")',
        '        end',
        '    end',
        'end',
    ]))
    result = resolve_file(name)
    assert result["sel_other_sel_a"]["jp"] == "別のブロックの見出し"
    assert result["sel_fake_sel_a"]["jp"] is None
    assert result["sel_fake_sel_a"]["reason"] == UNRESOLVED_NO_CHAIN


def test_undispatched_result_stays_no_chain_not_a_far_away_match():
    """sel_s4fb_30_sel_a / sel_s4fb_50_sel_a are single-option confirm
    dialogs whose result is assigned to the global `retSelect` and then
    simply discarded. Scope-bound regression: with a generic receiver regex
    and no scope bound, the forward search would run on for hundreds of
    lines and could latch onto any later `if retSelect == 1 then` in the
    file, inventing a dispatch. Must stay UNRESOLVED_NO_CHAIN."""
    result = resolve_file("snr_s4_10_fb.lua")
    for name in ("sel_s4fb_30_sel_a", "sel_s4fb_50_sel_a"):
        assert result[name]["jp"] is None, name
        assert result[name]["reason"] == UNRESOLVED_NO_CHAIN, name


def test_global_receiver_dispatch_is_found_s5s_190():
    """The mirror of the test above: `retSelect` IS dispatched here, so it
    must resolve. These two buttons were unreachable for the old `v\\d+`-only
    receiver regex (reported no_chain) on BOTH bases -- fixing the regex is
    what recovered them."""
    result = resolve_file("snr_s5_10_s.lua")
    assert result["sel_s5s_190_sel_a"]["jp"] == "中庭のアヤノさん"
    assert result["sel_s5s_190_sel_b"]["jp"] == "もしかしたらアヤノさんが"


# ---------------------------------------------------------------------------
# 4. Coverage-shape regression: BOTH recovery shapes must be implemented.
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
    (`l1_2 == 1` -> doScriptScene="s2s_208" ->
    scene_s2s_208(..., "ナゾトキの正解"))."""
    result = resolve_file("snr_s2_10_s.lua")
    rec = result["sel_s2s_190_sel_a"]
    assert rec["jp"] == "ナゾトキの正解"
    assert rec["how"] == "目标场景名"


def test_full_run_coverage_floor_needs_both_shapes():
    """Coverage-floor regression for the mutation "解析器只认一种分支形态
    （覆盖率应显著下降）": resolve_all() must clear a floor that is NOT
    reachable with only one of the two shapes. Measured on the 2026-08-31
    base: 85/114 (was 81/114 on the pre-migration base -- +4 from the
    generalized receiver regex and the sibling-`if` chain walk, with all 81
    previously-derived jp strings byte-identical). Form-2-only (direct
    scene_X in body) or form-1-only (doScriptScene chase) each individually
    resolve meaningfully fewer (per the inventory doc's own account, "只认
    第一种覆盖率 34%，两种都认 51%" for the prior crude parser); the same
    ordering must hold: both > either alone. The floor is set just below the
    measured count so a change that silently disables either shape -- or the
    receiver/scope/joint/fall-through handling -- drops well below it."""
    merged = resolve_all()
    resolved = sum(1 for r in merged.values() if r["jp"])
    assert len(merged) == 114
    assert resolved >= 83, (
        f"only {resolved}/{len(merged)} resolved with both recovery shapes "
        f"enabled -- expected >=83 (measured 85 on this base, 81 before the "
        f"decompiler-base migration); a regression here likely means one of "
        f"the two shapes (direct scene_X() call, or doScriptScene chase) "
        f"stopped firing")


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
# 5. find_var_dispatch internals.
# ---------------------------------------------------------------------------

def test_elseif_arm_is_not_lumped_into_the_shared_else():
    """sel_s2s_190_sel_b's value (2) has its OWN arm in the chain, so it
    must get that arm's text ("ナゾトキの間違い") and NOT be lumped into the
    catch-all else bucket that value 3 falls into ("ナゾトキ１", flagged
    shared). On the pre-migration base this arm was printed as a bare `else`
    whose whole body was a nested `if v50 == 2 then ...` and the walker had
    to flatten it; this base prints a real `elseif`. Either way, a value
    with its own arm must never inherit the shared-else text."""
    result = resolve_file("snr_s2_10_s.lua")
    rec_b = result["sel_s2s_190_sel_b"]
    assert rec_b["jp"] == "ナゾトキの間違い"
    assert "共享" not in (rec_b["how"] or "")


def test_else_wrapping_a_nested_if_is_flattened_like_elseif(synthetic):
    """The unluac-style idiom the pre-migration base used everywhere:
    `if v==1 then A else if v==2 then B else C end end`. The 2026-08-31 base
    emits real `elseif` chains so there is no live fixture, but the walker
    still handles it -- if the flatten is removed, value 2 silently falls
    into the outer `else` bucket and inherits C's text instead of B's."""
    name = synthetic("fake_elseif.lua", '\n'.join([
        'main = function()',
        '    local l1_2 = 0',
        '    l1_2 = comDlgSelectItem(false, "sel_fake_sel_a", 1, 2, 1, "sel_fake_sel_b", 3, 4, 2, "sel_fake_sel_c", 5, 6, 3)',
        '    if l1_2 == 1 then',
        '        scene_a(doScriptScene, "選択肢Ａ")',
        '    else',
        '        if l1_2 == 2 then',
        '            scene_b(doScriptScene, "選択肢Ｂ")',
        '        else',
        '            scene_c(doScriptScene, "共有の受け皿")',
        '        end',
        '    end',
        'end',
    ]))
    result = resolve_file(name)
    assert result["sel_fake_sel_a"]["jp"] == "選択肢Ａ"
    assert result["sel_fake_sel_b"]["jp"] == "選択肢Ｂ"
    assert "共享" not in (result["sel_fake_sel_b"]["how"] or "")
    assert result["sel_fake_sel_c"]["jp"] == "共有の受け皿"
    assert "共享" in result["sel_fake_sel_c"]["how"]


def test_find_var_dispatch_reports_compound_status():
    """find_var_dispatch must surface the joint-dispatch verdict as a status
    (with NO branches at all), not as a silently-empty result that later
    code could paper over with an else/fall-through guess."""
    calls = find_calls("snr_s2_10_s.lua")
    call = next(c for c in calls
                if any(n == "sel_s2s_192a_sel_a" for n, *_ in c["options"]))
    branches, status = find_var_dispatch("snr_s2_10_s.lua", call)
    assert status == "compound"
    assert branches == {}


def test_find_var_dispatch_still_rejects_textual_and_conditions(synthetic):
    """The pre-migration guard (a line that mentions the variable inside an
    `if` but not in simple `var == K` form) must stay: the new base does
    still print `and`-conjunctions in places (see the s4 explore-map
    completion check in the migration report), and a joint condition is not
    a per-option scene title there either."""
    name = synthetic("fake_and.lua", '\n'.join([
        'main = function()',
        '    local l1_2 = 0',
        '    l1_2 = comDlgSelectItem(false, "sel_fake_sel_a", 1, 2, 1)',
        '    if l1_2 == 1 and gameSave.flag == 1 then',
        '        scene_a(doScriptScene, "共同条件")',
        '    end',
        'end',
    ]))
    call = find_calls(name)[0]
    branches, status = find_var_dispatch(name, call)
    assert status == "compound"
    assert branches == {}
    assert resolve_file(name)["sel_fake_sel_a"]["reason"] == UNRESOLVED_COMPOUND
