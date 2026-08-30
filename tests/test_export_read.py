"""`tools/export_read.py`（通读导出）的测试。

盯的是四件**会静默出错**的事——出错时导出照样成文、照样退出码 0，人翻一遍
40 万字也未必看得出来：

1. **行序**必须是 `timeline.jsonl` 的路线序。弄成 id 序，读到的因果关系全是乱的，
   但每一行本身都对，模型只会读出"这书写得真跳"。
2. **卡面梗概的落点**必须是该卡首次作成的那个单元之后。往前挪一格就成了剧透
   （梗概写着这一场的结局），往后挪一格就与做卡剧情脱节。
3. **一条译文恰好一行、且不夹带原文**。这是本工具存在的全部理由；混进原文
   或提案，紧凑性和"只读定稿"两个前提同时失效。
4. **全部 ledger 行都要出现**。路线没覆盖到的挂附录——少几十行不会有任何报错。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.export_read import (HEADER_END, Exporter, chapter_key, chapter_title,
                               main)
from tools.pipelib import write_jsonl

CARDS_ZH = """\
- card: 6
  variant: a
  title_zh: 想不起约定
  body_zh: "Ayano总觉得，自己放学\\n后好像约了谁见面。"
  tr_note: ''
- card: 200
  variant: a
  title_zh: 章节 EX2
  body_zh: 我们的故事。
  tr_note: '编外卡'
"""


def _mini(tmp_path):
    """最小替身仓库。刻意做出四个陷阱：

    - 路线序与 id 序相反（scene 用 20/21 在前、10/11 在后）；
    - 同一章被做卡段打断两次，用来验「（续）」；
    - 一条 ambient 行不在任何单元里，只能靠附录兜住；
    - 一张卡（200）根本不在路线上，只能靠编外卡兜住。
    """
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    lane.mkdir(parents=True)

    write_jsonl(repo / "data" / "ledger.jsonl", [
        {"id": 10, "jp": "アヤノは笑った。", "voice": "NONVOICE", "file": "snr_s1_10_s",
         "func": "scene_a", "chapter": "s1s", "kind": "narrative", "line": 1},
        {"id": 11, "jp": "【彩野】「うん」", "voice": "AYA001", "file": "snr_s1_10_s",
         "func": "scene_a", "chapter": "s1s", "kind": "narrative", "line": 2},
        {"id": 20, "jp": "席につき、ふとアヤノは思った。", "voice": "NONVOICE",
         "file": "snr_s1_10_s", "func": "scene_sel", "chapter": "s1s",
         "kind": "narrative", "line": 3},
        {"id": 21, "jp": "でも、どうだったっけ？", "voice": "NONVOICE",
         "file": "snr_s1_10_s", "func": "scene_sel", "chapter": "s1s",
         "kind": "narrative", "line": 4},
        {"id": 30, "jp": "【直哉】「このカードだ」", "voice": "NAO001",
         "file": "snr_crd_6", "func": "card_6_main", "chapter": "crd",
         "kind": "narrative", "line": 1},
        {"id": 99, "jp": "【■おしらせ】", "voice": "NONVOICE", "file": "snr_common",
         "func": "sys", "chapter": "sys", "kind": "ambient", "line": 1},
    ])
    # 路线序：选择场景(20,21) → marker → 做卡(30) → 场景(10,11)。与 id 序相反。
    write_jsonl(repo / "data" / "timeline.jsonl", [
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "snr_s1_10_s",
         "state": "s1s_35_sel", "title": "選択：放課後の約束", "ids": [20, 21]},
        {"seq": 2, "type": "marker", "text": "【讲述指针回溯至 s1s_35_sel，本次选第 1 项】",
         "recap": "重讲：指针回到 s1s_35_sel，本次改选第 1 项。"},
        {"seq": 3, "type": "unit", "unit_kind": "card", "src": "snr_crd_6",
         "state": "s1s_37", "title": "約束を思い出せない", "ids": [30]},
        {"seq": 4, "type": "unit", "unit_kind": "scene", "src": "snr_s1_10_s",
         "state": "s1s_36", "title": "約束をしている", "ids": [10, 11]},
    ])
    write_jsonl(repo / "data" / "ledger_extra.jsonl", [
        {"key": "snr_s1_10_s:3", "jp": "選択：放課後の約束", "kind": "scene_title",
         "file": "snr_s1_10_s"},
        {"key": "snr_s1_10_s:9", "jp": "約束をしている", "kind": "scene_title",
         "file": "snr_s1_10_s"},
    ])
    write_jsonl(repo / "data" / "extra_translated.jsonl", [
        {"jp": "オープニング", "zh": "片头", "note": ""},
    ])
    write_jsonl(repo / "data" / "select_buttons_zh.jsonl", [
        {"button": "sel_s1s_35_sel_a", "jp": "約束をしている", "zh": "有约定",
         "source": "t"},
    ])
    write_jsonl(repo / "data" / "select_options_zh.jsonl", [
        {"jp": "約束を思い出せない", "zh": "想不起约定",
         "buttons": ["sel_s1s_35_sel_b"], "source": "t", "note": ""},
    ])
    (repo / "skeleton" / "cards.zh.yaml").write_text(CARDS_ZH, encoding="utf-8")

    write_jsonl(lane / "forward.jsonl", [
        {"id": 10, "zh": "Ayano 笑了。", "batch": 1, "glossary_v": 1, "ts": "t0"},
        {"id": 11, "zh": "【彩野】「嗯」", "batch": 1, "glossary_v": 1, "ts": "t0"},
        {"id": 20, "zh": "落座后，Ayano 忽然想到。", "batch": 1, "glossary_v": 1, "ts": "t0"},
        {"id": 21, "zh": "不过，是怎么来着？", "batch": 1, "glossary_v": 1, "ts": "t0"},
        {"id": 30, "zh": "【直哉】「就是这张卡」", "batch": 1, "glossary_v": 1, "ts": "t0"},
        {"id": 99, "zh": "【■通知】", "batch": 1, "glossary_v": 1, "ts": "t0"},
    ])
    write_jsonl(lane / "patches.jsonl", [
        # 控制码 `_n` 必须原样活到导出；顺带验「取补丁不取首译」
        {"id": 21, "zh": "不过_n是怎么来着？", "reason": "polish", "glossary_v": 2,
         "ts": "t1"},
    ])
    write_jsonl(lane / "forward_extra.jsonl", [
        {"key": "snr_s1_10_s:3", "kind": "scene_title", "zh": "选择：放学后的约定",
         "glossary_v": 1, "ts": "t0"},
        {"key": "snr_s1_10_s:9", "kind": "scene_title", "zh": "有约定",
         "glossary_v": 1, "ts": "t0"},
    ])
    return repo


@pytest.fixture
def text(tmp_path):
    return Exporter(repo=_mini(tmp_path)).render()


@pytest.fixture
def body(text):
    """去掉文件头导言的正文部分——导言里有解释性的日文记号说明，
    会干扰「不夹带原文」这类断言。"""
    return text.split("<!-- 导言结束 -->\n", 1)[1]


# ---- 1. 行序 ----

def test_order_follows_route_not_id(body):
    """替身仓库把路线序做成与 id 序相反——导出必须按路线走。"""
    pos = {t: body.index(t) for t in
           ("落座后，Ayano 忽然想到。", "【直哉】「就是这张卡」", "Ayano 笑了。")}
    assert pos["落座后，Ayano 忽然想到。"] < pos["【直哉】「就是这张卡」"] < pos["Ayano 笑了。"]


def test_marker_sits_between_its_neighbours(body):
    """讲述指针 marker 是路线非线性的唯一信号，位置错了就读成了顺叙。"""
    marker = "> 【讲述指针回溯至 s1s_35_sel，本次选第 1 项】"
    assert marker in body
    assert body.index("不过_n是怎么来着？") < body.index(marker) < body.index("【直哉】「就是这张卡」")


# ---- 2. 卡面梗概的落点 ----

def test_card_face_follows_its_unit(body):
    """卡面接在该卡作成单元的正文之后，且在下一个单元的标题之前。"""
    lines = body.splitlines()
    i = lines.index("【直哉】「就是这张卡」")
    assert lines[i + 1] == "〔卡面梗概〕"
    assert lines[i + 2] == "Ayano总觉得，自己放学"
    assert lines[i + 3] == "后好像约了谁见面。"
    rest = [x for x in lines[i + 4:] if x]       # 跳过标题前的空行分隔
    assert rest[0].startswith("#")               # 下一个单元/章段的标题


def test_card_unit_heading_uses_card_name(body):
    assert "### 卡 6『想不起约定』" in body


def test_offroute_card_lands_in_appendix(body):
    """卡 200 不在路线上（编外卡）。不兜住就会整张消失且无人报错。"""
    tail = body[body.index("## 附录"):]
    assert "卡 200『章节 EX2』" in tail
    assert "我们的故事。" in tail


# ---- 3. 一条一行、不夹带原文 ----

def test_one_line_per_translation(body):
    for zh in ("Ayano 笑了。", "【彩野】「嗯」", "落座后，Ayano 忽然想到。",
               "不过_n是怎么来着？", "【直哉】「就是这张卡」"):
        assert body.count("\n" + zh + "\n") == 1, zh


def test_no_source_text_leaks(body):
    """原文、首译、补丁理由都不该出现在正文里。"""
    for jp in ("アヤノは笑った。", "でも、どうだったっけ？", "【彩野】「うん」"):
        assert jp not in body
    assert "不过，是怎么来着？" not in body      # 被补丁取代的首译
    assert "polish" not in body                  # 补丁 reason


def test_control_codes_preserved(body):
    """`_n` 是引擎换行，摊平就与落盘译文对不上了。"""
    assert "不过_n是怎么来着？" in body


# ---- 4. 一行都不能少 ----

def test_every_ledger_line_present(body):
    for zh in ("Ayano 笑了。", "【彩野】「嗯」", "落座后，Ayano 忽然想到。",
               "不过_n是怎么来着？", "【直哉】「就是这张卡」", "【■通知】"):
        assert zh in body


def test_ambient_line_lands_in_appendix(body):
    assert "【■通知】" in body[body.index("## 附录"):]


def test_appendix_flags_decompiler_artifacts(tmp_path):
    """附录里混着 `vms` 第三参数不是字面量的行（拼接表达式）。不说明来历，
    读的人会把 `i0 .. "_rsceneId：" .. …` 当成一条待修的译文。"""
    repo = _mini(tmp_path)
    rows = [json.loads(l) for l in
            (repo / "data" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    for r in rows:
        if r["id"] == 99:
            r["literal"] = False
    write_jsonl(repo / "data" / "ledger.jsonl", rows)
    assert "1 行是反编译拼接表达式，非游戏文本" in Exporter(repo=repo).render()


# ---- 5. 标题与选项 ----

def test_headings_are_chinese(body):
    assert "## 第 1 章·故事层" in body
    assert "### 选择：放学后的约定" in body
    assert "### 有约定" in body
    assert "選択：放課後の約束" not in body


def test_repeated_chapter_run_marked_as_continuation(body):
    """同一章被做卡段打断后回来，标题带（续）——否则模型读到重复标题
    会以为自己绕回了开头。"""
    assert body.count("## 第 1 章·故事层\n") == 1
    assert "## 第 1 章·故事层（续）" in body


def test_select_options_line(body):
    """两个来源（buttons/options 两份 jsonl）都要并进同一行，按字母序。"""
    assert "〔本场选项〕有约定／想不起约定" in body


def test_partial_option_set_is_labelled_as_partial(tmp_path):
    """只核验过一部分按钮时，**必须**说明还缺几项。

    实测 34 个选择场景里有 12 个是残缺的（如 s2s_190_sel 只有 3 项中的 1 项有
    人工核验译文）。照直印出来，一份 1/3 的选项表读起来与完整的一模一样——
    模型会据此判断"这个节点只有一个选择"，而那是错的。
    """
    repo = _mini(tmp_path)
    sel = repo / "png" / "select"
    sel.mkdir(parents=True)
    # 该节点真实有三个按钮，但只有 a/b 有人工核验译文
    for letter in "abc":
        for variant in ("on", "off"):
            (sel / f"sel_s1s_35_sel_{letter}_{variant}.png").touch()

    exp = Exporter(repo=repo)
    assert "〔本场选项〕有约定／想不起约定（另 1 项按钮文本未核验）" in exp.render()
    assert exp.stats["sel_units_partial_options"] == 1


def test_complete_option_set_carries_no_caveat(tmp_path):
    repo = _mini(tmp_path)
    sel = repo / "png" / "select"
    sel.mkdir(parents=True)
    for letter in "ab":
        for variant in ("on", "off"):
            (sel / f"sel_s1s_35_sel_{letter}_{variant}.png").touch()

    exp = Exporter(repo=repo)
    assert "〔本场选项〕有约定／想不起约定\n" in exp.render()
    assert exp.stats["sel_units_partial_options"] == 0


def test_option_line_only_where_the_choice_happens(tmp_path):
    """做卡单元的 `state` 同样以 `_sel` 结尾（实测 34 个 scene 对 34 个 card），
    但玩家在那里是在**做卡**，选项按钮根本没出现。列在那儿等于谎报选择的位置，
    而且会让"没有按钮译文"的计数虚高一倍。"""
    repo = _mini(tmp_path)
    p = repo / "data" / "timeline.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    for r in rows:
        if r.get("unit_kind") == "card":
            r["state"] = "s1s_35_sel"          # 与选择场景同一个 state
    write_jsonl(p, rows)

    exp = Exporter(repo=repo)
    assert exp.render().count("〔本场选项〕有约定／想不起约定") == 1
    assert exp.stats["sel_units_without_options"] == 0


def test_select_line_omitted_when_captions_unknown(tmp_path):
    """没有人工核验过的按钮译文时，宁可不给这一行，也不编。"""
    repo = _mini(tmp_path)
    write_jsonl(repo / "data" / "select_buttons_zh.jsonl", [])
    write_jsonl(repo / "data" / "select_options_zh.jsonl", [])
    exp = Exporter(repo=repo)
    # 只看正文——导言里就写着 `〔本场选项〕` 这个记号本身的说明
    assert "〔本场选项〕" not in exp.render().split(HEADER_END + "\n", 1)[1]
    assert exp.stats["sel_units_without_options"] == 1


def test_degenerate_titles_never_fall_back_to_japanese(tmp_path):
    """三类单元在 timeline 里没有场景名——教程卡 0、演出池、整章 `_f`。

    它们的兜底**不能**按 timeline 的 title 原值查表：`Reader._titles` 已经把
    `snr_crd_0` 改写成「卡 0」、把 `snr_s1_10_f` 改写成「s1 现实层（f）」，
    按原值当键会静默落空、把 lua 文件名当标题印出去。演出池是唯一 title 被
    原样透传的一类，所以只有它按 title 兜底。
    """
    repo = _mini(tmp_path)
    ledger = [json.loads(l) for l in
              (repo / "data" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [json.loads(l) for l in
            (repo / "data" / "timeline.jsonl").read_text(encoding="utf-8").splitlines()]
    fwd = [json.loads(l) for l in
           (repo / "pilot" / "lanes" / "opus" / "data" / "forward.jsonl")
           .read_text(encoding="utf-8").splitlines()]
    edge = [("snr_crd_0", "script", "snr_crd_0"),
            ("snr_common", "pool", "snr_common:comSectionMapmoveAyanoIn"),
            ("snr_s1_10_f", "fscene", "snr_s1_10_f")]
    for n, (src, kind, title) in enumerate(edge, start=1):
        cid = 500 + n
        ledger.append({"id": cid, "jp": "テスト", "voice": "NONVOICE", "file": src,
                       "func": "f", "chapter": "x", "kind": "narrative", "line": 1})
        fwd.append({"id": cid, "zh": f"测试{cid}", "batch": 1, "glossary_v": 1, "ts": "t0"})
        rows.append({"seq": 10 + n, "type": "unit", "unit_kind": kind, "src": src,
                     "state": None, "title": title, "ids": [cid]})
    write_jsonl(repo / "data" / "ledger.jsonl", ledger)
    write_jsonl(repo / "data" / "timeline.jsonl", rows)
    write_jsonl(repo / "pilot" / "lanes" / "opus" / "data" / "forward.jsonl", fwd)

    out = Exporter(repo=repo).render()
    assert "### 卡 0（教程：做卡演示）" in out
    assert "### 探索途中彩野到场" in out
    assert "### 全章" in out
    for leaked in ("snr_crd_0", "snr_s1_10_f", "comSectionMapmoveAyanoIn"):
        assert leaked not in out.split(HEADER_END + "\n", 1)[1]


# ---- 6. 章段归类 ----

@pytest.mark.parametrize("src,key,title", [
    ("snr_s0_10_f", "s0/f", "序章·现实层"),
    ("snr_s1_10_s", "s1/s", "第 1 章·故事层"),
    ("snr_s2_10_f", "s2/f", "第 2 章·现实层"),
    ("snr_s3_10_fa", "s3/fa", "第 3 章·现实层（fa）"),
    ("snr_e1_10_s", "e1/s", "EX1·故事层"),
    ("snr_crd_137", "crd", "片段·做卡"),
    ("snr_common:comSectionMapmoveAyanoIn", "pool", "演出池"),
])
def test_chapter_classification(src, key, title):
    assert chapter_key(src) == key
    assert chapter_title(key) == title


# ---- 7. 统计与 CLI ----

def test_stats_report_real_numbers(tmp_path):
    st = Exporter(repo=_mini(tmp_path)).stats
    assert st["lines"] == 6                       # 5 条正文 + 1 条 ambient
    assert st["untranslated"] == 0
    assert st["card_faces"] == 1                  # 路线上的卡 6
    assert st["offroute_cards"] == 1              # 编外卡 200
    assert st["chapter_runs"] == 4                # s1/s → crd → s1/s → 附录


def test_deterministic(tmp_path):
    repo = _mini(tmp_path)
    assert Exporter(repo=repo).render() == Exporter(repo=repo).render()


def test_main_writes_file(tmp_path, capsys):
    repo = _mini(tmp_path)
    out = tmp_path / "read.md"
    assert main(["--repo", str(repo), "--out", str(out)]) == 0
    assert "Ayano 笑了。" in out.read_text(encoding="utf-8")
    assert "行" in capsys.readouterr().err          # 统计走 stderr


def test_main_stdout(tmp_path, capsys):
    assert main(["--repo", str(_mini(tmp_path)), "--out", "-"]) == 0
    assert "Ayano 笑了。" in capsys.readouterr().out


def test_untranslated_line_is_flagged_not_dropped(tmp_path):
    """缺译不能静默跳过——那会让"完整"变成假的，且计数对不上。"""
    repo = _mini(tmp_path)
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    rows = [json.loads(l) for l in
            (lane / "forward.jsonl").read_text(encoding="utf-8").splitlines()]
    write_jsonl(lane / "forward.jsonl", [r for r in rows if r["id"] != 10])
    exp = Exporter(repo=repo)
    assert "〔缺译：id 10〕" in exp.render()
    assert exp.stats["untranslated"] == 1
