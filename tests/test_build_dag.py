from tools.build_dag import parse_states, parse_scene_meta

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
