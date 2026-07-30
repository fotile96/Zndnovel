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

from tools.build_ledger import chapter_of, classify

def test_chapter_of_section_files():
    assert chapter_of("snr_s1_10_s") == "s1s"
    assert chapter_of("snr_s3_10_fa") == "s3fa"
    assert chapter_of("snr_s0_10_f") == "s0f"
    assert chapter_of("snr_e2_10_f") == "e2f"
    assert chapter_of("snr_crd_42") == "crd"
    assert chapter_of("snr_common") == "sys"

def test_classify_kind_by_file():
    sysrow = classify({"file": "snr_common", "func": "vms"})
    assert (sysrow["chapter"], sysrow["kind"]) == ("sys", "ambient")
    story = classify({"file": "snr_s1_10_s", "func": "scene_s1s_20"})
    assert (story["chapter"], story["kind"]) == ("s1s", "narrative")
    card = classify({"file": "snr_crd_2", "func": "card_2_s1s_20_intro"})
    assert (card["chapter"], card["kind"]) == ("crd", "narrative")

from tools.build_ledger import parse_extra

EXTRA_FIXTURE = '''\
plotTitle[1] = "ある子が学校にくる物語"
scene_s1s_20(doScriptScene, "夏の朝、高校までの通学路") -- tr_line:2
savedataTitle("オープニング", "フラグメント")
oCard.show(cGetFileName("card", "crd_1_a"), "書きとめました：『ある子』")
'''

def test_parse_extra_four_kinds():
    rows = parse_extra("snr_test", EXTRA_FIXTURE)
    kinds = {r["kind"] for r in rows}
    assert kinds == {"plot_title", "scene_title", "savedata", "card_msg"}
    byk = {r["kind"]: r for r in rows if r["kind"] != "savedata"}
    assert byk["plot_title"]["key"] == "plotTitle:1"
    assert byk["scene_title"]["jp"] == "夏の朝、高校までの通学路"
    assert byk["card_msg"]["jp"] == "書きとめました：『ある子』"
    savedata = [r for r in rows if r["kind"] == "savedata"]
    assert [r["jp"] for r in savedata] == ["オープニング", "フラグメント"]
    assert savedata[0]["key"].endswith(":1") and savedata[1]["key"].endswith(":2")

def test_parse_extra_card_msg_with_concat_first_arg():
    # 主流形态：首参含 cGetFileName 逗号与 .. 拼接，可译文本是最后一个字符串参数
    line = 'oCard.show(cGetFileName("card", "crd_" .. gameSave.fragmentDoCardId .. "_a"), "『約束をしている』のあらすじを作成しました。") -- tr_line:39'
    rows = parse_extra("snr_crd_1", line)
    assert [r["kind"] for r in rows] == ["card_msg"]
    assert rows[0]["jp"] == "『約束をしている』のあらすじを作成しました。"

import subprocess, sys
from tools.pipelib import REPO, read_jsonl

def test_real_repo_ledger_counts_and_uniqueness(tmp_path):
    out = subprocess.run(
        [sys.executable, "tools/build_ledger.py", "--out-dir", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    # 真实静态 vms 数 16749（grep 复核）：全仓库 vms( 共 16751 处，动态调用 2 处不入账
    # （snr_common oCard.show 的 vms(v1,…) 与 snr_s5_10_s:1975 的 vms(v0,…)，均为 18000+ 动态 ID）。
    # CLAUDE.md 所记 16750 只扣除了前者，系文档笔误。
    rows = read_jsonl(tmp_path / "ledger.jsonl")
    assert len(rows) == 16749
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == 16749
    assert rows == sorted(rows, key=lambda r: r["id"])
    kinds = {r["kind"] for r in rows}
    assert kinds == {"narrative", "ambient"}
    extra = read_jsonl(tmp_path / "ledger_extra.jsonl")
    assert sum(1 for r in extra if r["kind"] == "plot_title") == 195

def test_double_run_is_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        subprocess.run([sys.executable, "tools/build_ledger.py", "--out-dir", str(d)],
                       cwd=REPO, check=True, capture_output=True)
    assert (a / "ledger.jsonl").read_bytes() == (b / "ledger.jsonl").read_bytes()
    assert (a / "ledger_extra.jsonl").read_bytes() == (b / "ledger_extra.jsonl").read_bytes()
