from tools.build_ledger import parse_vms_lines

FIXTURE = '''\
scene_x1_10 = function(scene_id, scene_title)
    local v0
    vms(100, "NONVOICE", "○_n通学路。") -- tr_line:3
    vms(101, "AYA00180", "【アヤノ】「教室に来たよ」")
    v0 = function()
        vms(102, "NORECORD", "≪入手済みカード≫")
    end
    vms(103, "NONVOICE", "これにより、『" .. v7 .. "』を読む。")
end
'''

def test_parse_extracts_ids_voice_and_text():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert [r["id"] for r in rows] == [100, 101, 102, 103]
    assert rows[0]["jp"] == "○_n通学路。"          # tr_line 注释被剥除，引号去壳
    assert rows[1]["voice"] == "AYA00180"
    assert rows[1]["file"] == "snr_x_10_s"

def test_func_tracking_follows_nearest_function_opener():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert rows[0]["func"] == "scene_x1_10"
    assert rows[2]["func"] == "v0"               # 嵌套闭包归最近的 opener

def test_literal_flag_false_for_concatenation():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert rows[0]["literal"] is True
    assert rows[3]["literal"] is False
    assert '.. v7 ..' in rows[3]["jp"]           # 非字面量保留原始表达式
