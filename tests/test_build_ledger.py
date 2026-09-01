import re

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

def test_func_tracking_bubbles_past_bare_vn_to_named_opener():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert rows[0]["func"] == "scene_x1_10"
    assert rows[2]["func"] == "scene_x1_10"      # 裸 vN 闭包穿透，归最近非裸 vN 祖先（嵌套栈追踪）

# --- Hotfix A: 嵌套栈追踪（brief hotfix-a-brief.md 四组用例）---

CASE1_PARENT_REBOUND = '''\
scene_s1s_10 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    vms(7296, "NONVOICE", "…") -- tr_line:3
end
'''

def test_case1_parent_body_rebounds_after_closure_end():
    # brief 背景示例原型：空闭包 v0 结束后，父体内的 vms 应归 scene_s1s_10，
    # 而非（平面实现下）一直停留在 v0。
    rows = parse_vms_lines("snr_s1_10_s", CASE1_PARENT_REBOUND)
    assert [r["id"] for r in rows] == [7296]
    assert rows[0]["func"] == "scene_s1s_10"

CASE2_CLOSURE_PASSTHROUGH = '''\
scene_s1s_20 = function(scene_id, scene_title)
    local v0
    v0 = function()
        vms(7300, "NONVOICE", "closure body text")
    end
    v0()
end
'''

def test_case2_vms_inside_bare_vn_closure_bubbles_to_parent():
    rows = parse_vms_lines("snr_s1_10_s", CASE2_CLOSURE_PASSTHROUGH)
    assert rows[0]["id"] == 7300
    assert rows[0]["func"] == "scene_s1s_20"     # 最近非裸 vN 祖先

CASE3_DOTTED_NAME_OWNS_ITSELF = '''\
scene_s1s_30 = function(scene_id, scene_title)
    local v0
    v0 = {}
    v0.mesNot = function()
        vms(7310, "NONVOICE", "dotted-owner text")
    end
end
'''

def test_case3_dotted_name_keeps_own_ownership():
    # v0.mesNot 不匹配 ^v\\d+$，按自身名字归属（snr_common 的 v0.mesNot/v0.mesNG 依赖此行为）。
    rows = parse_vms_lines("snr_s1_10_s", CASE3_DOTTED_NAME_OWNS_ITSELF)
    assert rows[0]["id"] == 7310
    assert rows[0]["func"] == "v0.mesNot"

CASE4_TOPLEVEL_RESET = '''\
scene_s1s_40 = function(scene_id, scene_title)
    vms(7320, "NONVOICE", "inside a")
end
vms(7321, "NONVOICE", "toplevel, no owner")
scene_s1s_50 = function(scene_id, scene_title)
    vms(7322, "NONVOICE", "inside b")
end
'''

def test_case4_toplevel_vms_after_function_end_has_empty_func():
    rows = parse_vms_lines("snr_s1_10_s", CASE4_TOPLEVEL_RESET)
    by_id = {r["id"]: r["func"] for r in rows}
    assert by_id[7320] == "scene_s1s_40"
    assert by_id[7321] == ""                     # 弹栈后顶层复位
    assert by_id[7322] == "scene_s1s_50"

def test_literal_flag_false_for_concatenation():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert rows[0]["literal"] is True
    assert rows[3]["literal"] is False
    assert '.. v7 ..' in rows[3]["jp"]           # 非字面量保留原始表达式

# --- F7: lua 行号 line 字段 ---

def test_rows_carry_lua_line_numbers():
    text = 'v0 = function()\n  vms(10, "NONVOICE", "甲")\n  vms(11, "NONVOICE", "乙")\nend\n'
    rows = parse_vms_lines("snr_test", text)
    assert [r["line"] for r in rows] == [2, 3]


def test_global_sort_still_by_id_line_is_additive(tmp_path):
    # id 逆序出现在文件里（后补行的形态）：全局排序仍按 id（行序不变约定），
    # line 忠实记录原行号。brief 里的 build_from_text 助手不存在，改用 build()
    # 直接吃一个临时 lua 目录——与该文件既有的「跑真仓库」风格一致。
    from tools.build_ledger import build
    (tmp_path / "snr_test.lua").write_text(
        'v0 = function()\n  vms(20, "NONVOICE", "乙")\n  vms(19, "NONVOICE", "甲")\nend\n',
        encoding="utf-8")
    ledger, _ = build(tmp_path)
    assert [r["id"] for r in ledger] == [19, 20]
    assert [r["line"] for r in ledger] == [3, 2]


def test_line_is_lua_file_line_not_vms_ordinal():
    # F7 例证形态：注释/空行让 vms 序号与行号脱钩，line 必须是文件行号。
    text = '-- c1\n\n-- c2\nvms(5, "NONVOICE", "甲")\n'
    rows = parse_vms_lines("snr_test", text)
    assert rows[0]["line"] == 4


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

def test_parse_extra_covers_the_four_shapes_added_2026_09_01():
    """`gameSave.sceneName/sectionName`、dispatch 首参、单参 `msg` 四类。

    这四类此前**整整漏在账本外**：51 行带着 `-- tr_line:` 标记，却因为
    `parse_extra` 没有对应规则而拿不到键，于是永远不会被翻译，其中 41 行是玩家
    真能看到的日文（第 4 章场景名、第 5 章彩野台词、第 7 章递卡旁白、文库空提示）。
    """
    src = "\n".join([
        'gameSave.sceneName = "放課後の教室" -- tr_line:1',
        'gameSave.sectionName = "１：Ｓｔｏｒｙ" -- tr_line:2',
        'l1_1 = scene_s7f_dispatch_v52("その『お話』の題名は――", 104, l1_1, 10) -- tr_line:3',
        'msg("まだ一冊も取得していません。") -- tr_line:4',
    ])
    rows = parse_extra("snr_x", src)
    assert [(r["kind"], r["key"], r["jp"]) for r in rows] == [
        ("scene_name", "snr_x:1", "放課後の教室"),
        ("section_name", "snr_x:2", "１：Ｓｔｏｒｙ"),
        ("dispatch_text", "snr_x:3", "その『お話』の題名は――"),
        ("msg_text", "snr_x:4", "まだ一冊も取得していません。"),
    ]


def test_msg_rule_does_not_swallow_vms():
    """`msg_text` 的 `(?<![A-Za-z0-9_])` 前瞻必须挡住 `vms(`——正文轨不归 extra 管。"""
    assert parse_extra("snr_x", 'vms(1, "NONVOICE", "あ")') == []
    assert parse_extra("snr_x", 'xmsg("あ")') == []
    assert len(parse_extra("snr_x", 'msg("あ")')) == 1


def test_every_tr_line_mark_gets_a_ledger_key():
    """**标记与账本的口径必须一致**，这是 51 行漏译的直接成因。

    `migrate_base.should_mark`（含全角串、非 vms、不在排除文件）比 `parse_extra`
    的规则**更宽**，宽出来的部分就是黑洞：注入期只会报「账本里的键缺译」，
    账本里压根没有的键**报不出来**，于是整条管线一声不吭地漏掉那些文字。

    这条对全仓库跑，不用夹具——夹具证明不了「没有第 9 种形状」。
    """
    from tools.build_ledger import uncovered_tr_lines
    holes = []
    for p in sorted((REPO / "lua_scripts").glob("*.lua")):
        holes += [f"{p.stem}:{n}  {s[:60]}"
                  for n, s in uncovered_tr_lines(p.stem, p.read_text(encoding="utf-8"))]
    assert holes == [], f"{len(holes)} 行标了 tr_line 却没有账本键：\n" + "\n".join(holes[:10])


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

def test_real_repo_no_bare_vn_func_residue(tmp_path):
    # Hotfix A 回归断言：嵌套栈追踪修复后，全库几乎不应再有 vms 行的 func 落在裸 vN 名字上。
    # 已知且经调查确认的唯一例外：snr_crd_102 的 v0/v1/v2——三个文件顶层（indent 0）的
    # 兄弟局部闭包（推理クイズ题面/两种误答提示），由 card_102_s6s_110_intro 以
    # v0()/v1()/v2() 调用，但并未词法嵌套在其内部。嵌套栈在它们体内找不到任何非裸 vN
    # 祖先，命中 brief 规则本身的兜底分支（"全是裸 vN 时取最外层名字"），只能停留在自身。
    # 这不是实现缺陷——修复调用图追踪超出"嵌套栈追踪"范围，属过度设计——固定为已知清单，
    # 而非放宽规则掩盖：出现清单之外的新残留、或这 24 行本身发生变化，都应让测试失败并复查。
    out = subprocess.run(
        [sys.executable, "tools/build_ledger.py", "--out-dir", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    # 2026-08-31 换反编译基座后，裸名的**形态**从 v\d+ 变成 l<depth>_<reg>，
    # 但残留的**位置与数量完全不变**：同样是 snr_crd_102 的三个函数、同样 24 行。
    # 这正说明上面那段根因分析（调用而非词法嵌套）与基座无关，是语料本身的形状。
    rows = read_jsonl(tmp_path / "ledger.jsonl")
    bare = [(r["file"], r["id"], r["func"]) for r in rows
            if re.match(r'^(?:v\d+|p\d+|l\d+_\d+|u\d+)$', r["func"])]
    known = {("snr_crd_102", "l0_0"), ("snr_crd_102", "l0_1"), ("snr_crd_102", "l0_2")}
    unexpected = [b for b in bare if (b[0], b[2]) not in known]
    assert unexpected == [], f"出现未知裸名残留，需要按同样方法调查根因：{unexpected[:5]}"
    assert len(bare) == 24, f"已知的 snr_crd_102 残留数量变化（现为 {len(bare)}），该文件是否被改动？"

def test_double_run_is_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        subprocess.run([sys.executable, "tools/build_ledger.py", "--out-dir", str(d)],
                       cwd=REPO, check=True, capture_output=True)
    assert (a / "ledger.jsonl").read_bytes() == (b / "ledger.jsonl").read_bytes()
    assert (a / "ledger_extra.jsonl").read_bytes() == (b / "ledger_extra.jsonl").read_bytes()

def test_narrative_exception_wins(monkeypatch):
    import tools.build_ledger as bl
    monkeypatch.setattr("tools.build_ledger.NARRATIVE_FUNC_EXCEPTIONS",
                        {"snr_common:comSectionStoryEndAyanoTime": "时间轴事件"},
                        raising=False)
    row = bl.classify({"file": "snr_common", "func": "comSectionStoryEndAyanoTime"})
    assert row["kind"] == "narrative"
