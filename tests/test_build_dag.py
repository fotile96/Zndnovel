from tools.build_dag import (parse_states, parse_scene_meta, parse_crds,
                             inline_cost_consts)
import json
import re

FIX = '''\
scene_x_20 = function(scene_id, scene_title)
    local v0
    v0 = function()
        gameSave.myCard[128].hold = 1
        comSectionStoryEnd(gameSave.sceneId, gameSave.sceneName, 25)
    end
end
main = function()
    while v48 == 0 do
        if doScriptScene == "end" then
            v48 = 1
        elseif doScriptScene == "x_20" then
            scene_x_20(doScriptScene, "夏の朝")
            doScriptScene = "x_30"
        elseif doScriptScene == "x_30_sel" then
            if gameSave.myCard[133].hold == 1 then
                doScriptScene = "y_10"
                run(cGetFileName("script", "snr_y_10_s"))
            end
            v49 = comDlgSelectItem(false, true, false, true, 1, "none", 0, 0, "sel_a", 115, 140, 1)
            if v49 == 1 then
                doScriptScene = "x_40"
            elseif v49 == 2 then
                doScriptScene = "x_50"
            end
            scene_x_dispatch_v20()
        end
    end
end
'''

def test_states_capture_flow_in_order():
    st = parse_states("snr_x_10_s", FIX)
    ev = st["x_20"]["seq"]
    assert st["x_20"]["scene"] == "scene_x_20"
    assert st["x_20"]["title"] == "夏の朝"
    assert {"goto": "x_30"} in ev

def test_states_capture_gate_choice_run_subcall():
    st = parse_states("snr_x_10_s", FIX)
    ev = st["x_30_sel"]["seq"]
    assert {"card_gate": 133, "held": True} in ev
    assert {"run": "snr_y_10_s"} in ev
    assert {"choice": 1, "goto": "x_40"} in ev and {"choice": 2, "goto": "x_50"} in ev
    assert {"subcall": "scene_x_dispatch_v20"} in ev

def test_scene_meta_costs_and_gets():
    m = parse_scene_meta("snr_x_10_s", FIX)
    assert m["scene_x_20"]["cost"] == [25]
    assert m["scene_x_20"]["gets"] == [128]


# Hotfix B1: crd 脚本自身发出的「别的卡」（字面量下标）要收进 gets；
# 自身授予用变量下标 gameSave.myCard[fragmentDoCardId] 不应被算作 gets。
CRD_FIX = '''\
main = function()
    local v2
    comSectionCardStart(gameSave.fragmentDoSceneId, gameSave.fragmentDoCardId)
    if gameSave.myCard[9].hold == -1 then
        oCard.mesNot()
    end
    if not (gameSave.myCard[gameSave.fragmentDoCardId].hold == 1) then
        gameSave.myCard[126].hold = 1
        gameSave.myCard[gameSave.fragmentDoCardId].hold = 1
        comAyanoTimeRefresh()
    end
end
'''


def test_parse_crds_captures_literal_gets_but_not_self_grant_variable(tmp_path):
    (tmp_path / "snr_crd_10.lua").write_text(CRD_FIX, encoding="utf-8")
    crds = parse_crds(tmp_path)
    assert crds["10"]["gets"] == [126]
    assert crds["10"]["req"] == [9]              # 既有字段不受影响


# Test fixture for choice variable tracking
PUZZLE = '''\
scene_puzzle = function(scene_id, scene_title)
end
main = function()
    while v48 == 0 do
        elseif doScriptScene == "puzzle_main" then
            v60 = comDlgSelectItem(false, true, false, true, 1, "none", 0, 0, "sel_puzzle", 115, 140, 1)
            if v60 == 1 then
                doScriptScene = "puzzle_ok"
            elseif v60 == 2 then
                doScriptScene = "puzzle_fail"
            end
        elseif doScriptScene == "puzzle_logic" then
            if v51 == 0 then
                doScriptScene = "puzzle_continue"
            end
            if v62 == 2 then
                doScriptScene = "puzzle_end"
            end
        end
    end
end
'''

def test_internal_if_blocks_not_marked_choice():
    """Internal if blocks (v51, v62) not assigned from comDlgSelectItem should not mark goto as choice."""
    st = parse_states("snr_puzzle", PUZZLE)
    logic_ev = st["puzzle_logic"]["seq"]
    # v51 and v62 are internal variables, not choice variables
    # Their if blocks should not cause following gotos to be marked with choice
    assert {"goto": "puzzle_continue"} in logic_ev
    assert {"goto": "puzzle_end"} in logic_ev
    # Ensure no spurious choice events with internal variable values
    for ev in logic_ev:
        if "choice" in ev:
            assert ev["choice"] >= 1, f"Invalid choice value: {ev}"

def test_choice_cleared_after_consumption():
    """pend_choice should be cleared after being consumed by a goto."""
    st = parse_states("snr_puzzle", PUZZLE)
    main_ev = st["puzzle_main"]["seq"]
    # v60 is assigned from comDlgSelectItem, so if v60 == N creates pending choice
    # First goto should be marked with choice
    assert {"choice": 1, "goto": "puzzle_ok"} in main_ev
    assert {"choice": 2, "goto": "puzzle_fail"} in main_ev

def test_real_data_all_choices_valid():
    """Regression test: all choice events in real data should have value >= 1."""
    dag = json.load(open("data/dag.json", encoding="utf-8"))
    for state_id, state in dag["states"].items():
        for event in state["seq"]:
            if "choice" in event:
                assert event["choice"] >= 1, f"Invalid choice value {event['choice']} in state {state_id}"

def test_real_data_s2s_190_sel_targets():
    """Regression test: s2s_190_sel should have exactly two choice targets: s2s_208 and s2s_209."""
    dag = json.load(open("data/dag.json", encoding="utf-8"))
    state = dag["states"].get("s2s_190_sel", {})
    choice_targets = {}
    for event in state.get("seq", []):
        if "choice" in event and "goto" in event:
            choice_num = event["choice"]
            target = event["goto"]
            choice_targets[choice_num] = target
    # Should have exactly 2 choices pointing to the two expected targets
    targets = set(choice_targets.values())
    assert targets == {"s2s_208", "s2s_209"}, f"Expected {{s2s_208, s2s_209}}, got {targets}"


import subprocess
import sys

from tools.pipelib import REPO


def test_cli_check_matches_committed_dag():
    # data/dag.json 是入库生成物，必须始终与 lua 源同步（冒烟/CI 的防线）
    out = subprocess.run([sys.executable, "tools/build_dag.py", "--check"],
                         cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "check: OK" in out.stdout


def test_cli_check_detects_mismatch(tmp_path):
    (tmp_path / "dag.json").write_text('{"states":{}}\n', encoding="utf-8")
    out = subprocess.run([sys.executable, "tools/build_dag.py", "--check",
                          "--out-dir", str(tmp_path)],
                         cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 1
    assert "MISMATCH" in out.stdout


def test_cli_double_run_is_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        subprocess.run([sys.executable, "tools/build_dag.py", "--out-dir", str(d)],
                       cwd=REPO, check=True, capture_output=True)
    assert (a / "dag.json").read_bytes() == (b / "dag.json").read_bytes()


# ---------------------------------------------------------------------------
# 现基座（pyluadec-refactor corpus/final，2026-08-31 换入）的文本形状回归
# ---------------------------------------------------------------------------
# 局部名 l<depth>_<reg>、`local NAME = function`、elseif 合并、cost 走局部常量。
# 这些形状一旦重新失配，build_dag 不会报错——它会**静默降级**（scene_meta 归零、
# choice/cost 全丢），而 check_timeline 只打告警 exit 0 拦不住。故此处全部以
# 「实测计数」立闸。
NEWBASE_FIX = '''\
local scene_x_20 = function(scene_id, scene_title)
    local l1_2 = function()
        gameSave.myCard[128].hold = 1
        local l2_0 = 25
        comSectionStoryEnd(gameSave.sceneId, gameSave.sceneName, l2_0)
    end
    l1_2()
end
main = function()
    local l1_0 = 0
    while l1_0 == 0 do
        if doScriptScene == "end" then
            l1_0 = 1
        elseif doScriptScene == "x_20" then
            scene_x_20(doScriptScene, "夏の朝")
            doScriptScene = "x_30_sel"
        elseif doScriptScene == "x_30_sel" then
            local l1_1 = sceneId2aCard.x_30_sel
            local l1_2 = 0
            if gameSave.myCard[133].hold == 1 then
                l1_2 = comDlgSelectItem(false, true, false, true, 1, "none", 0, 0, "sel_a", 115, 80, 1)
            end
            if l1_2 == 1 then
                doScriptScene = "x_40"
            elseif l1_2 == 2 then
                doScriptScene = "x_50"
            else
                local l1_4 = 0
                while l1_4 == 0 do
                    local l1_5 = 0
                    l1_5 = comDlgSelectItem(false, true, false, true, 1, "none", 0, 0, "sel_p", 115, 80, 1)
                    if l1_5 == 1 then
                        l1_4 = 1
                        break
                    end
                    scene_x_puzzle()
                end
                if l1_5 == 1 then
                    doScriptScene = "x_60"
                end
            end
        end
    end
end
'''


def test_newbase_scene_meta_reads_local_decl_and_const_cost():
    m = parse_scene_meta("snr_x_10_s", NEWBASE_FIX)
    assert "scene_x_20" in m, "`local NAME = function` 声明没被 scene_meta 认出来"
    assert m["scene_x_20"]["cost"] == [25], "cost 的局部常量没回溯出来"
    assert m["scene_x_20"]["gets"] == [128]


def test_newbase_choice_topology():
    st = parse_states("snr_x_10_s", NEWBASE_FIX)
    ev = st["x_30_sel"]["seq"]
    assert {"card_gate": 133, "held": True} in ev
    assert {"choice": 1, "goto": "x_40"} in ev
    assert {"choice": 2, "goto": "x_50"} in ev
    # while 内的 comDlgSelectItem 是谜题循环，不是场景级选项：其后的 goto 不得被标 choice。
    # 且 l1_5 在新基座是**寄存器复用名**，绝不能因为循环内出现过就把循环外的比较也算上。
    assert {"goto": "x_60"} in ev
    assert not any(ev_.get("goto") == "x_60" and "choice" in ev_ for ev_ in ev)


def test_inline_cost_consts_refuses_to_invent_dynamic_cost():
    """首个赋值不是整数字面量（s5 的 dispatch 累加器）时必须放弃解析，
    不能顺着往上抓 `local l1_1 = 0` 编出一个假的 cost=0。"""
    src = ('    local l1_1 = 0\n'
           '    l1_1 = scene_s5s_dispatch_v42("...", 180, l1_1, 30, true)\n'
           '    comSectionStoryEndForce(gameSave.sceneId, gameSave.sceneName, l1_1)\n')
    assert inline_cost_consts(src) == src


def _real_lua_end_calls():
    from tools.pipelib import REPO
    call = re.compile(r'comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, '
                      r'gameSave\.sceneName, ([A-Za-z_]\w*|\d+)\)')
    tot = lit = 0
    for p in sorted((REPO / "lua_scripts").glob("*.lua")):
        text = p.read_text(encoding="utf-8")
        tot += len(call.findall(text))
        lit += len([x for x in call.findall(inline_cost_consts(text)) if x.isdigit()])
    return tot, lit


def test_real_data_cost_resolution_rate():
    """175 个 comSectionStoryEnd 里 162 个能回溯到整数字面量；余 13 个是 s5 的
    运行期累加器（旧基座同样取不到）。掉到 0 就是换基座后的静默降级。"""
    tot, lit = _real_lua_end_calls()
    assert (tot, lit) == (175, 162), f"comSectionStoryEnd 解析率变了：{lit}/{tot}"


def test_real_data_counts_no_silent_degradation():
    """dag.json 四个易静默归零的计数（数字取自与换基座前产物的逐项对账）。"""
    dag = json.load(open("data/dag.json", encoding="utf-8"))
    assert len(dag["states"]) == 405
    assert len(dag["scene_meta"]) == 527
    assert len(dag["crds"]) == 196

    choice = [e for s in dag["states"].values() for e in s["seq"] if "choice" in e]
    n_choice_states = len({sid for sid, s in dag["states"].items()
                           if any("choice" in e for e in s["seq"])})
    assert (len(choice), n_choice_states) == (76, 33)

    # 2026-09-13 由 (101, 168) 上修为 (103, 171)：parse_crd_answers 去掉了旧松正则时代遗留的
    # `- {0, 1}`，卡 1 不再被误当哨兵滤掉。逐项对账 = 101+2（crd_2/108 由「无答案」变为 [1]）
    # 与 168+3（crd_2/30/108 各多一个卡 1）。这不是退化，是补回三处漏检。
    with_ans = [c for c in dag["crds"].values() if c["answers"]]
    assert (len(with_ans), sum(len(c["answers"]) for c in with_ans)) == (103, 171)

    meta_cost = sum(len(m["cost"]) for m in dag["scene_meta"].values())
    state_cost = sum(1 for s in dag["states"].values()
                     for e in s["seq"] if "end_cost" in e)
    assert (meta_cost, state_cost) == (162, 29)


def test_real_data_choice_numbers_are_declared_options():
    """每个 choice 序号都必须是该 state 的 comDlgSelectItem 真的声明过的选项号——
    这是防「正则串号把无关的 if 当成分支」的拓扑闸，与计数闸互为独立证据。"""
    from tools.build_dag import STATE_RE, SEL_ASSIGN_RE, WHILE_RE
    from tools.pipelib import REPO
    opt = re.compile(r'"(sel_[\w]+)", *(-?\d+), *(-?\d+), *(\d+)')
    declared = {}
    for p in sorted((REPO / "lua_scripts").glob("snr_[se]*_10_*.lua")):
        text = p.read_text(encoding="utf-8")
        main = text[text.rfind("\nmain = function()"):]
        cur, whiles = None, []
        for line in main.splitlines():
            s = line.strip()
            if m := STATE_RE.match(s):
                cur, whiles = m.group(1), []
                declared.setdefault(cur, set())
                continue
            if cur is None:
                continue
            ind = len(line) - len(line.lstrip())
            if s == "end":
                while whiles and ind <= whiles[-1]:
                    whiles.pop()
            elif WHILE_RE.match(s):
                whiles.append(ind)
                continue
            if not whiles and SEL_ASSIGN_RE.search(s):
                declared[cur].update(int(m.group(4)) for m in opt.finditer(s))

    dag = json.load(open("data/dag.json", encoding="utf-8"))
    for sid, st in dag["states"].items():
        picks = {e["choice"] for e in st["seq"] if "choice" in e}
        if picks:
            assert picks <= declared.get(sid, set()), \
                f"{sid} 的 choice {sorted(picks)} 不在声明的选项号 {sorted(declared.get(sid, ()))} 里"
