from tools.build_dag import parse_states, parse_scene_meta, parse_crds
import json

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
