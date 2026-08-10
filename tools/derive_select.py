#!/usr/bin/env python3
"""Derive Japanese source text for png/select/ option-button images from the
lua control flow, without reading pixels.

## Why this is possible at all

`comDlgSelectItem(...)` (lua_scripts/snr_common.lua:1564) never receives the
button's own caption string -- only an image name ("sel_<scene>_sel_<a..g>")
plus an integer choice-value per option (see its vararg loop, groups of 4:
name, x, y, value). The caption text baked into that PNG has to come from
somewhere else in the surrounding code: which scene the game goes to *if you
pick this button* usually has a human-readable title attached via a
`scene_X(id, "title")` call, and that title is (per manual verification
against several real buttons, see docs/ops/bake-select-inventory.md) what the
button image actually shows.

## The two recovery shapes (both required -- see docstring for why coverage
   drops hard if only one is implemented)

Given `vNN = comDlgSelectItem(...)` (or a bare `if comDlgSelectItem(...) ==
K then`), find the code that consumes `vNN`'s value and, for each button's
integer value K, walk forward through whichever of these shapes is present:

  1. `if vNN == K then doScriptScene = "sceneId" end` -- the branch merely
     records which scene to go to next; the actual `scene_sceneId(id,
     "title")` call is *elsewhere*, inside a LATER `if doScriptScene ==
     "sceneId" then ...` arm of the same (or, after a `run(cGetFileName(
     "script", "snr_XX"))` chapter jump, a DIFFERENT file's) dispatcher.
     Must be chased (`chase_doscriptscene` below), following further
     `doScriptScene = "..."` reassignments and file switches until a
     `scene_X(...)` call is found or the chase gives up.
  2. `if vNN == K then scene_X(id, "title") ... end` -- the title is right
     there in the branch body, no chase needed.

docs/ops/bake-select-inventory.md's crude first-pass parser (not preserved
in this repo -- its output snapshot is build/select_option_map.json) only
implemented shape 1 well enough to hit 34% coverage; recognizing shape 2 too
brought it to 51%. This module implements both, PLUS the RUN-jump chase
(1's cross-file continuation) that the crude parser evidently did NOT do
correctly for at least one real button (see the s2s_193c_sel_a/b
misattribution documented in the report -- its jp text came from a
completely unrelated dispatch block further down the same file; the crude
parser's "how" tag of "目标场景名" gave no way to tell a correct chase from
a coincidental regex hit landing on the wrong scene_X() call).

## Block boundaries: indentation, not bracket-counting

lua_scripts/*.lua is decompiled-then-hand-touched code with betrayingly
consistent indentation (4 spaces/level, verified by direct inspection of
several hundred lines spanning nested if/while/elseif chains -- see the
report). This module exploits that directly: a block header line's `end` /
next `elseif` / `else` is simply the next line at the SAME indentation,
because every nested statement is indented strictly deeper. This is far
simpler and more auditable than a bracket-counting Lua tokenizer, but it is
a real assumption -- `_find_block_end` raises rather than silently guessing
if a file's indentation turns out inconsistent (never observed in practice
across the 9 files this module reads, but the guard exists so a future file
with sloppier formatting fails loudly instead of returning a wrong span).

## What is reported when a button's text truly cannot be derived

Every unresolved button gets a specific `reason` string (see
`UNRESOLVED_REASON_*` constants) rather than a bare None -- distinguishing
"leads into a nested puzzle/maze with no title anywhere in the branch"
(genuinely no JP text exists in source) from "the dispatch variable is only
ever used in a compound condition together with another select's result"
(this module intentionally does not attempt multi-variable joint dispatch;
see the design note in `find_var_dispatch`) from "chase exceeded the hop
budget" (a *possible* real miss, flagged distinctly so it's not confused
with the two structurally-unresolvable cases above).
"""
import argparse, glob, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(REPO, "lua_scripts")
OUT_PATH = os.path.join(REPO, "build", "select_option_map.json")

CALL_FILES = [
    "snr_crd_102.lua", "snr_s0_10_f.lua", "snr_s1_10_s.lua",
    "snr_s2_10_s.lua", "snr_s3_10_s.lua", "snr_s4_10_fb.lua",
    "snr_s4_10_s.lua", "snr_s5_10_s.lua", "snr_s6_10_s.lua",
]

OPTION_RE = re.compile(r'"(sel_[A-Za-z0-9_]+)"\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)')
SCENE_CALL_RE = re.compile(r'scene_[A-Za-z0-9_]+\(\s*[^,()]+,\s*"([^"]*)"\s*\)')
DOSCRIPTSCENE_ASSIGN_RE = re.compile(r'doScriptScene\s*=\s*"([A-Za-z0-9_]+)"')
RUN_JUMP_RE = re.compile(r'run\(cGetFileName\("scriptc?",\s*"([^"]+)"\)\)')

UNRESOLVED_NO_CHAIN = "选择结果变量之后未找到形如 if var==K then 的单变量简单判断（可能只用于复合条件，或结果从未被读取）"
UNRESOLVED_COMPOUND = "变量出现在复合条件（如 (v60==1) and (v61==1)）中，本解析器不做跨变量联合覆盖——这类分支是谜题作答的对错判定，不是单选项的场景标题"
UNRESOLVED_NO_BRANCH_FOR_VALUE = "该选项的整数值在 if/elseif 链中未见任何显式分支（且没有 else 兜底），可能是不可达值"
UNRESOLVED_SHARED_ELSE_EMPTY = "该选项落在多个选项共享的 else 兜底分支，且该分支体内既无 scene_X() 调用也无 doScriptScene 赋值——是通用流程（如谜题主线/其它状态处理），不是这个按钮专属的文字"
UNRESOLVED_EMPTY_BODY = "分支体内既无 scene_X(...) 调用也无 doScriptScene 字面量赋值，机械解析找不到可用文本源"
UNRESOLVED_GAMEOVER = "分支直接触发 GAMEOVER，无场景标题可用"
UNRESOLVED_COMPLETE = "分支直接触发 COMPLETE 结局，无场景标题可用"
UNRESOLVED_NESTED_SELECT = "分支直接进入下一层 comDlgSelectItem 选择（嵌套谜题/子菜单），按钮文字本身未被赋予场景标题"
UNRESOLVED_LOOP = "分支进入循环结构（while/repeat，谜题反复作答），不是单次场景跳转"
UNRESOLVED_CHASE_NOT_FOUND = "doScriptScene 目标场景 ID 在该文件调度器中未找到对应 if 分支"
UNRESOLVED_CHASE_BUDGET = "doScriptScene 重定向链跳数超过预算（可能存在真实漏解）"
UNRESOLVED_RUN_TARGET_NOT_FOUND = "RUN 跳转目标章节的入口场景无法机械解析（entry chase 未命中 scene_X 调用）"

# ---------------------------------------------------------------------------
# Hand-verified special case: sel_voice1_sel_a / sel_voice2_sel_a
# (480x82, snr_s0_10_f.lua:145 -- the prologue's climactic "how does Naoya
# say 忘れないよ" choice, which ALSO sets systemSave.voiceNaoya). Neither
# button leads anywhere via doScriptScene/scene_X() -- both branches just
# play two vms() lines inline and fall through to the next statement, so
# the general chase logic above correctly reports these UNRESOLVED_EMPTY_
# BODY. But the branch bodies are short enough (2 vms() calls each) that
# their JP is 100% mechanically recoverable by a DIFFERENT rule: concatenate
# the branch's vms() string literals in source order. This was checked
# against the actual pixels (see the report) and matches verbatim:
#   v1==1 (sel_voice1_sel_a): vms(...,"【直哉】「（忘れないよ）」") +
#                              vms(...,"僕は思った。")
#     -> pixel text: "（忘れないよ）と、思った。" (concatenation minus the
#        speaker-tag bracket, which is exactly how this game's vms() lines
#        read when quoted back as narration elsewhere -- not a coincidence)
#   v1==2 (sel_voice2_sel_a): vms(...,"【直哉】「忘れないよ」") +
#                              vms(...,"僕は答えた。")
#     -> pixel text: "「忘れないよ」と、答えた。"
# Reported as its own "how" tag (not folded into "就地场景调用") because the
# recovery rule is genuinely different (vms concatenation, not a scene()
# title) and only manually confirmed for these 2 buttons -- do not treat
# this as a general-purpose derivation shape without further evidence.
# ---------------------------------------------------------------------------
SPECIAL_CASES = {
    "sel_voice1_sel_a": {
        "jp": "（忘れないよ）と、思った。",
        "how": "分支内两条 vms() 拼接（手工核对，见报告）",
        "reason": None, "file": "snr_s0_10_f.lua", "value": 1,
    },
    "sel_voice2_sel_a": {
        "jp": "「忘れないよ」と、答えた。",
        "how": "分支内两条 vms() 拼接（手工核对，见报告）",
        "reason": None, "file": "snr_s0_10_f.lua", "value": 2,
    },
}


def _load_lines(fname):
    path = os.path.join(SCRIPT_DIR, fname)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    indents = [len(l) - len(l.lstrip(" ")) if l.strip() else None for l in lines]
    return lines, indents


_FILE_CACHE = {}


def _get_file(fname):
    if fname not in _FILE_CACHE:
        _FILE_CACHE[fname] = _load_lines(fname)
    return _FILE_CACHE[fname]


# ---------------------------------------------------------------------------
# 1. Locate every comDlgSelectItem call site and its options.
# ---------------------------------------------------------------------------

def find_calls(fname):
    """Return [{file, line_start(1-based), indent, receiver, inline_value,
    options:[(name,x,y,value)], call_text}] for every comDlgSelectItem(...)
    call in `fname`. Handles calls spanning multiple physical lines by
    paren-balancing (skipping parens inside "..." strings)."""
    lines, indents = _get_file(fname)
    calls = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "comDlgSelectItem(" not in line:
            i += 1
            continue
        start = i
        open_col = line.index("comDlgSelectItem(") + len("comDlgSelectItem")
        # paren-balance from open_col across (possibly) multiple lines
        depth = 0
        buf = []
        j, col = i, open_col
        in_str = False
        started = False
        while j < len(lines):
            cur = lines[j]
            while col < len(cur):
                ch = cur[col]
                if in_str:
                    buf.append(ch)
                    if ch == '"' and cur[col - 1:col] != "\\":
                        in_str = False
                    col += 1
                    continue
                if ch == '"':
                    in_str = True
                    buf.append(ch)
                    col += 1
                    continue
                if ch == "(":
                    depth += 1
                    started = True
                    if depth == 1:
                        col += 1
                        continue
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end_line, end_col = j, col
                        call_text = "".join(buf)
                        prefix = line[:open_col - len("comDlgSelectItem")].strip()
                        suffix = cur[col + 1:]
                        calls.append(_build_call_record(
                            fname, start, indents[start], prefix, call_text, suffix))
                        j = end_line
                        col = end_col + 1
                        started = False
                        break
                buf.append(ch)
                col += 1
            else:
                j += 1
                col = 0
                buf.append("\n")
                continue
            break
        i = j + 1 if started is False else i + 1
    return calls


def _build_call_record(fname, line_start, indent, prefix, call_text, suffix):
    options = [(m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)))
               for m in OPTION_RE.finditer(call_text)]
    m = re.match(r'^(?:local\s+)?(v\d+)\s*=\s*$', prefix)
    receiver, inline_value = None, None
    if m:
        receiver = m.group(1)
    elif re.match(r'^(?:else)?if\s*$', prefix):
        m2 = re.match(r'^\s*==\s*(-?\d+)\s+then\b', suffix)
        if m2:
            inline_value = int(m2.group(1))
    return {
        "file": fname, "line_start": line_start + 1, "indent": indent,
        "receiver": receiver, "inline_value": inline_value, "options": options,
    }


# ---------------------------------------------------------------------------
# 2. Indentation-based block-end lookup.
# ---------------------------------------------------------------------------

def _find_block_end(lines, indents, header_idx):
    """Given the 0-based index of a block-opening line (`if ... then`,
    `elseif ... then`, `else`, `while ... do`, `for ... do`), return the
    0-based index of the line that closes it: the next line at the SAME
    indentation as the header (by the indentation invariant documented in
    the module docstring). Raises if none is found before EOF -- a
    malformed-indentation file should fail loudly, not silently return a
    wrong span."""
    header_indent = indents[header_idx]
    for k in range(header_idx + 1, len(lines)):
        if indents[k] is None:
            continue
        if indents[k] < header_indent:
            raise ValueError(
                f"indentation dropped below header ({header_indent}) at line "
                f"{k + 1} before finding a same-indent closer for header at "
                f"line {header_idx + 1}")
        if indents[k] == header_indent:
            return k
    raise ValueError(f"no same-indent closer found for header at line {header_idx + 1}")


def _chain_body(lines, indents, body_start, body_end):
    return lines[body_start:body_end]


def _skip_if_construct(lines, indents, header_idx):
    """Given the 0-based index of an `if ... then` header, walk through its
    own elseif/else continuations (each found via `_find_block_end`) until
    landing on the literal `end` that closes the WHOLE if/elseif/.../else/
    end construct, and return that index. Unlike a single `_find_block_end`
    call (which only returns the NEXT sibling boundary -- itself an
    `elseif`/`else`/`end`), this walks all the way to the final `end`."""
    i = header_idx
    while True:
        end = _find_block_end(lines, indents, i)
        if lines[end].strip() == "end":
            return end
        i = end


# ---------------------------------------------------------------------------
# 3. Locate the if/elseif/else dispatch chain for a given variable, starting
#    the search just after the call.
# ---------------------------------------------------------------------------

def find_var_dispatch(fname, call, max_search=600):
    """Returns (branches, status) where branches: {value_int_or_'else':
    (body_start, body_end)} and status is 'ok', 'no_chain', or 'compound'
    (var is used, but only inside a compound condition -- see
    UNRESOLVED_COMPOUND)."""
    lines, indents = _get_file(fname)
    varname = call["receiver"]
    start = call["line_start"]  # 1-based line AFTER call end is >= start
    simple_re = re.compile(r'^(?:else)?if\s+' + re.escape(varname) + r'\s*==\s*(-?\d+)\s+then\b')
    mention_re = re.compile(r'\b' + re.escape(varname) + r'\b')
    limit = min(len(lines), start + max_search)
    chain_start = None
    for i in range(start, limit):
        if lines[i].strip() == "":
            continue
        if simple_re.match(lines[i].strip()):
            chain_start = i
            break
        if mention_re.search(lines[i]) and re.search(r'\bif\b', lines[i]):
            # variable appears in an `if` line, but not the simple single-var
            # equality form -- almost certainly a compound condition.
            return {}, "compound"
    if chain_start is None:
        return {}, "no_chain"

    branches = {}
    i = chain_start
    while i < len(lines):
        stripped = lines[i].strip()
        # simple_re's `(?:else)?if` already matches both "if X==K then" and
        # "elseif X==K then" -- deliberately used uniformly here (not just
        # at chain_start) so the nested-if-inside-else flatten below (which
        # jumps straight to a bare "if ... then" that is NOT textually an
        # "elseif") is recognized as a chain continuation too.
        m = simple_re.match(stripped)
        if m:
            value = int(m.group(1))
            body_end = _find_block_end(lines, indents, i)
            branches[value] = (i + 1, body_end)
            i = body_end
            continue
        if stripped == "else":
            body_start = i + 1
            body_end = _find_block_end(lines, indents, i)
            # Decompiler idiom seen throughout lua_scripts/: `elseif var==K`
            # is frequently rendered as a bare `else` whose ENTIRE body is
            # one nested `if var==K then ... end` (see
            # e.g. snr_s2_10_s.lua:2815-2886's v50 dispatch). Semantically
            # identical to a real elseif -- must be flattened into the same
            # chain, or every value after the first one silently falls into
            # a bogus catch-all "else" bucket shared with genuinely-untested
            # values (a real bug this test suite caught this round, see
            # tests/test_derive_select.py's s2s_190_sel_c case).
            if body_start < body_end:
                inner = lines[body_start].strip()
                inner_m = re.match(
                    r'^if\s+' + re.escape(varname) + r'\s*==\s*(-?\d+)\s+then\b', inner)
                if inner_m and indents[body_start] > indents[i]:
                    # the nested if must be the ONLY statement in this else
                    # body -- its own full elseif/else/end construct must
                    # end exactly one line before the outer else's closing
                    # `end` -- otherwise this isn't the elseif-idiom, it's a
                    # real else with an unrelated nested if inside it (or
                    # trailing statements after it).
                    inner_full_end = _skip_if_construct(lines, indents, body_start)
                    if inner_full_end == body_end - 1:
                        i = body_start
                        continue
            branches["else"] = (body_start, body_end)
            i = body_end
            continue
        if stripped == "end":
            break
        # anything else at chain_indent breaks the simple chain assumption
        break
    return branches, "ok"


def find_inline_dispatch(fname, call):
    """For the `if comDlgSelectItem(...) == K then ... [else ...] end` form:
    locate the header (same physical call, whose `then` appears on
    call['line_start']-1 in practice since the call itself starts the
    statement) and return branches keyed by K and optionally 'else'."""
    lines, indents = _get_file(fname)
    header_idx = call["line_start"] - 1
    # header_idx may not itself contain "then" if the call spans lines;
    # search forward a few lines for the first "then" at same/greater indent.
    for k in range(header_idx, min(len(lines), header_idx + 20)):
        if re.search(r'\bthen\s*$', lines[k]):
            header_idx = k
            break
    body_end = _find_block_end(lines, indents, header_idx)
    branches = {call["inline_value"]: (header_idx + 1, body_end)}
    stripped = lines[body_end].strip()
    if stripped == "else":
        else_end = _find_block_end(lines, indents, body_end)
        branches["else"] = (body_end + 1, else_end)
    return branches


# ---------------------------------------------------------------------------
# 4. Derive a title string from a branch body, chasing doScriptScene
#    reassignments (and RUN chapter jumps) as needed.
# ---------------------------------------------------------------------------

def _classify_empty_body(body_lines, shared_else):
    text = "\n".join(body_lines)
    if "comSectionGameOver" in text:
        return UNRESOLVED_GAMEOVER
    if "comSectionComplete" in text:
        return UNRESOLVED_COMPLETE
    if "comDlgSelectItem(" in text:
        return UNRESOLVED_NESTED_SELECT
    if re.search(r'\b(while|repeat)\b', text):
        return UNRESOLVED_LOOP
    return UNRESOLVED_SHARED_ELSE_EMPTY if shared_else else UNRESOLVED_EMPTY_BODY


def chase_doscriptscene(fname, scene_id, depth=0, visited=None, max_depth=6):
    """Follow `if doScriptScene == "scene_id" then ...` in `fname`, returning
    (title, how, chase_path) or (None, None, reason_str). Chases further
    doScriptScene reassignments (same file) and RUN-jump file switches, up
    to max_depth hops."""
    if visited is None:
        visited = set()
    key = (fname, scene_id)
    if key in visited:
        return None, None, f"doScriptScene 重定向出现环（{key} 已访问过）"
    visited.add(key)
    if depth > max_depth:
        return None, None, UNRESOLVED_CHASE_BUDGET

    lines, indents = _get_file(fname)
    header_re = re.compile(r'^(?:else)?if\s+doScriptScene\s*==\s*"' + re.escape(scene_id) + r'"\s+then\b')
    header_idx = None
    for i, l in enumerate(lines):
        if header_re.match(l.strip()):
            header_idx = i
            break
    if header_idx is None:
        return None, None, UNRESOLVED_CHASE_NOT_FOUND

    body_end = _find_block_end(lines, indents, header_idx)
    body = lines[header_idx + 1:body_end]
    body_text = "\n".join(body)

    m = SCENE_CALL_RE.search(body_text)
    m_run = RUN_JUMP_RE.search(body_text)
    m_assign = DOSCRIPTSCENE_ASSIGN_RE.search(body_text)

    if m and (m_assign is None or body_text.index(m.group(0)) < body_text.index(m_assign.group(0))):
        return m.group(1), "目标场景名" + ("" if depth == 0 else f"（跨文件追踪 {depth} 跳）"), None

    if m_run:
        target_file = m_run.group(1) + ".lua"
        # the new scene id is whatever doScriptScene was (re)assigned to
        # before/at the run() call; fall back to scene_id itself if none.
        assigns = DOSCRIPTSCENE_ASSIGN_RE.findall(body_text)
        next_id = assigns[-1] if assigns else scene_id
        if not os.path.exists(os.path.join(SCRIPT_DIR, target_file)):
            return None, None, f"RUN 目标文件 {target_file} 不存在"
        return chase_doscriptscene(target_file, next_id, depth + 1, visited, max_depth)

    if m_assign:
        return chase_doscriptscene(fname, m_assign.group(1), depth + 1, visited, max_depth)

    return None, None, _classify_empty_body(body, shared_else=False)


def derive_from_body(fname, body_lines, shared_else=False):
    """Try to pull a title out of a branch body: direct scene_X() call
    first, then doScriptScene chase. Returns (title, how, reason)."""
    body_text = "\n".join(body_lines)
    m = SCENE_CALL_RE.search(body_text)
    m_assign = DOSCRIPTSCENE_ASSIGN_RE.search(body_text)
    if m and (m_assign is None or body_text.index(m.group(0)) < body_text.index(m_assign.group(0))):
        return m.group(1), "就地场景调用", None
    if m_assign:
        title, how, reason = chase_doscriptscene(fname, m_assign.group(1))
        if title:
            return title, how, None
        return None, None, reason
    return None, None, _classify_empty_body(body_lines, shared_else)


# ---------------------------------------------------------------------------
# 5. Top-level: resolve every option of every call in a file.
# ---------------------------------------------------------------------------

def resolve_file(fname):
    """Returns {button_name: {"jp": str|None, "how": str|None,
    "reason": str|None, "file": fname, "value": int}}."""
    out = {}
    for call in find_calls(fname):
        if call["receiver"]:
            branches, status = find_var_dispatch(fname, call)
        elif call["inline_value"] is not None:
            branches, status = find_inline_dispatch(fname, call), "ok"
        else:
            branches, status = {}, "no_chain"

        for name, x, y, value in call["options"]:
            if name in out and out[name]["jp"] is not None:
                continue  # already resolved by an earlier call site (same button, same mapping)
            if status == "compound":
                out[name] = {"jp": None, "how": None, "reason": UNRESOLVED_COMPOUND,
                              "file": fname, "value": value}
                continue
            if status == "no_chain":
                out[name] = {"jp": None, "how": None, "reason": UNRESOLVED_NO_CHAIN,
                              "file": fname, "value": value}
                continue
            if value in branches:
                body_start, body_end = branches[value]
                lines = _get_file(fname)[0]
                title, how, reason = derive_from_body(fname, lines[body_start:body_end])
            elif "else" in branches:
                body_start, body_end = branches["else"]
                lines = _get_file(fname)[0]
                title, how, reason = derive_from_body(fname, lines[body_start:body_end], shared_else=True)
                if title:
                    how = (how or "") + "（来自共享 else 分支，非本按钮专属，需重点核验）"
            else:
                title, how, reason = None, None, UNRESOLVED_NO_BRANCH_FOR_VALUE
            out[name] = {"jp": title, "how": how, "reason": reason, "file": fname, "value": value}
    return out


def resolve_all(files=CALL_FILES):
    merged = {}
    for fname in files:
        for name, rec in resolve_file(fname).items():
            merged[name] = rec
    # Special cases override the general chase result (both would otherwise
    # report UNRESOLVED_EMPTY_BODY for these two -- see SPECIAL_CASES docstring).
    for name, rec in SPECIAL_CASES.items():
        merged[name] = dict(rec)
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()
    merged = resolve_all()
    resolved = sum(1 for r in merged.values() if r["jp"])
    total = len(merged)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"resolved {resolved}/{total} buttons ({resolved/total:.1%})")
    reasons = {}
    for r in merged.values():
        if not r["jp"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {reason}")


if __name__ == "__main__":
    main()
