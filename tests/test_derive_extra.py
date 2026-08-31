import json

import pytest

from tools.derive_extra import (
    build_card_indexes,
    template_of,
    bracket_name,
    paren_content_after_quote,
    zen2han_alnum,
    resolve_section_label,
    resolve_exact_title,
    resolve_quote_content,
    resolve_paren_content,
    derive_plot_title,
    derive_scene_title,
    derive_card_msg,
    derive_savedata,
    derive_all,
    build_report,
    main,
    OPTION_TABLE,
    CARD_MSG_TEMPLATES,
    TITLE_ALIASES,
)
from tools.pipelib import read_jsonl, write_jsonl, REPO


# ---------------------------------------------------------------------------
# 夹具：小规模但覆盖真实结构的卡表——含一个「标题相同的两张卡」（模拟真实库里的
# 卡20/74「探索：放課後の学校」、85/119「屋上」现象）与一张「标题自带括号」的卡
# （模拟真实库里的卡180「サクラの日記：７月（書きかけ）」，用于测试 card_msg 的
# （…）槽位解析不会被卡名内嵌的括号带偏）。
# ---------------------------------------------------------------------------

CARDS_JP = [
    {"card": 0, "title_jp": ""},
    {"card": 1, "title_jp": "ある子が学校にくる物語"},
    {"card": 2, "title_jp": "夏の朝、高校までの通学路"},
    {"card": 20, "title_jp": "探索：放課後の学校"},
    {"card": 74, "title_jp": "探索：放課後の学校"},   # 同名多卡
    {"card": 6, "title_jp": "サクラの日記：７月（書きかけ）"},   # 标题自带括号
    {"card": 145, "title_jp": "いつかきみがみるお話。"},   # 绘本标题（无空格无分かち書き）
]
CARDS_ZH = [
    {"card": 1, "title_zh": "有个孩子来学校的故事"},
    {"card": 2, "title_zh": "夏日清晨，通往高中的上学路"},
    {"card": 20, "title_zh": "探索：放学后的学校"},
    {"card": 74, "title_zh": "探索：放学后的学校"},
    {"card": 6, "title_zh": "サクラ的日记：7月（未写完）"},
    {"card": 145, "title_zh": "总有一天你会看到的故事。"},
]


@pytest.fixture
def idx():
    return build_card_indexes(CARDS_JP, CARDS_ZH)


# ---------------------------------------------------------------------------
# template_of / bracket_name
# ---------------------------------------------------------------------------

def test_template_of_normalizes_quote_and_paren():
    assert template_of("『サクラからの手紙』のあらすじを作成しました。") == \
        "『…』のあらすじを作成しました。"
    assert template_of("『選択：どこで読む』の選択肢（図書室で読む）を作成しました。") == \
        "『…』の選択肢（…）を作成しました。"


def test_bracket_name_extracts_first_quote():
    assert bracket_name("『サクラからの手紙』のあらすじを作成しました。") == "サクラからの手紙"
    assert bracket_name("no brackets here") is None


# ---------------------------------------------------------------------------
# resolve_exact_title：精确匹配 + 同名多卡
# ---------------------------------------------------------------------------

def test_resolve_exact_title_hit(idx):
    _, zh_by_card, title_to_cards = idx
    cards, zh, ambiguous = resolve_exact_title("ある子が学校にくる物語", title_to_cards, zh_by_card)
    assert cards == [1]
    assert zh == "有个孩子来学校的故事"
    assert ambiguous is False


def test_resolve_exact_title_miss_returns_empty(idx):
    _, zh_by_card, title_to_cards = idx
    cards, zh, ambiguous = resolve_exact_title("不存在的标题", title_to_cards, zh_by_card)
    assert cards == []
    assert zh is None


def test_resolve_exact_title_duplicate_titles_with_identical_zh_still_resolves(idx):
    _, zh_by_card, title_to_cards = idx
    cards, zh, ambiguous = resolve_exact_title("探索：放課後の学校", title_to_cards, zh_by_card)
    assert sorted(cards) == [20, 74]
    assert zh == "探索：放学后的学校"
    assert ambiguous is True


# ---------------------------------------------------------------------------
# derive_plot_title：安全闸①——卡号对得上但 jp 不逐字相同，必须标 none。
# ---------------------------------------------------------------------------

def test_derive_plot_title_exact_match(idx):
    jp_by_card, zh_by_card, _ = idx
    row = {"key": "plotTitle:1", "jp": "ある子が学校にくる物語", "kind": "plot_title"}
    result, anomaly = derive_plot_title(row, jp_by_card, zh_by_card)
    assert result["confidence"] == "exact"
    assert result["zh"] == "有个孩子来学校的故事"
    assert result["source"] == "cards.zh:card=1"
    assert anomaly is None


def test_derive_plot_title_jp_mismatch_must_not_derive(idx):
    """安全闸①核心用例：卡号 1 存在，但 ledger 的 jp 和 cards.jp 的 title_jp 不同——
    必须标 none，绝不能"卡号对得上就派生"。这条测试要能抓住"只按卡号取值、不校验
    jp 逐字相同"的变异（把 derive_plot_title 里的 jp_title != jp 校验删掉）。"""
    jp_by_card, zh_by_card, _ = idx
    row = {"key": "plotTitle:1", "jp": "这是被改动过的日文标题", "kind": "plot_title"}
    result, anomaly = derive_plot_title(row, jp_by_card, zh_by_card)
    assert result["confidence"] == "none"
    assert result["zh"] == ""
    assert anomaly is not None and "不逐字相同" in anomaly


def test_derive_plot_title_unknown_card_number(idx):
    jp_by_card, zh_by_card, _ = idx
    row = {"key": "plotTitle:999", "jp": "无中生有", "kind": "plot_title"}
    result, anomaly = derive_plot_title(row, jp_by_card, zh_by_card)
    assert result["confidence"] == "none"
    assert "不在 cards.jp.yaml" in anomaly


# ---------------------------------------------------------------------------
# derive_scene_title：安全闸②——必须逐字相同，不能用「包含」。
# ---------------------------------------------------------------------------

def test_derive_scene_title_exact_match(idx):
    jp_by_card, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:1", "jp": "夏の朝、高校までの通学路", "kind": "scene_title"}
    result, anomaly = derive_scene_title(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "exact"
    assert result["zh"] == "夏日清晨，通往高中的上学路"
    assert result["source"] == "cards.zh:card=2"


def test_derive_scene_title_substring_must_not_match(idx):
    """安全闸②核心用例：'放課後の学校' 是卡20/74标题「探索：放課後の学校」的**真子串**，
    但不逐字相同——必须标 none。这条测试要能抓住"用 `in` 判断包含关系代替 `==` 判断
    逐字相同"的变异（判据过宽=张冠李戴，本项目文化明确列为反面案例）。"""
    jp_by_card, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:2", "jp": "放課後の学校", "kind": "scene_title"}
    result, anomaly = derive_scene_title(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "none"
    assert result["zh"] == ""


def test_derive_scene_title_superset_must_not_match(idx):
    """反向包含也不能命中：jp 比某卡标题更长（该标题是 jp 的真子串）。"""
    jp_by_card, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:3", "jp": "探索：放課後の学校です", "kind": "scene_title"}
    result, anomaly = derive_scene_title(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "none"


def test_derive_scene_title_duplicate_title_notes_anomaly_but_still_resolves(idx):
    jp_by_card, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:4", "jp": "探索：放課後の学校", "kind": "scene_title"}
    result, anomaly = derive_scene_title(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "exact"
    assert result["zh"] == "探索：放学后的学校"
    assert anomaly is not None and "同名" in anomaly


# ---------------------------------------------------------------------------
# paren_content_after_quote：安全闸③——卡名自带括号时不能被误当成槽位括号。
# ---------------------------------------------------------------------------

def test_paren_content_after_quote_skips_embedded_parens_in_card_name():
    """核心用例（本轮踩过的坑）：卡名『サクラの日記：７月（書きかけ）』自带括号，
    真正的模板槽位括号在『…』闭合**之后**。若用全局搜索找第一个（…），会命中卡名里的
    「（書きかけ）」而不是真正的槽位内容——这条测试要能抓住这种"退化成全局搜索"的变异。"""
    jp = "『サクラの日記：７月（書きかけ）』の選択肢（羨ましがる）を作成しました。"
    assert paren_content_after_quote(jp) == "羨ましがる"


def test_paren_content_after_quote_no_quote_falls_back_to_whole_string():
    assert paren_content_after_quote("no quote here（内容）") == "内容"


def test_paren_content_after_quote_no_paren_returns_none():
    assert paren_content_after_quote("『名前』のあらすじを作成しました。") is None


# ---------------------------------------------------------------------------
# zen2han_alnum / resolve_section_label：セクション<X>→章节 <X> 兜底规则。
# ---------------------------------------------------------------------------

def test_zen2han_alnum_converts_fullwidth_digits_and_letters_only():
    assert zen2han_alnum("３Ａ") == "3A"
    assert zen2han_alnum("ＥＸ１") == "EX1"
    assert zen2han_alnum("８") == "8"
    # 非拉丁/数字字符（如全角冒号、假名）原样保留，规则明确只转「拉丁/数字」。
    assert zen2han_alnum("１：アヤノ") == "1：アヤノ"


def test_resolve_section_label_basic():
    assert resolve_section_label("セクション１") == "章节 1"
    assert resolve_section_label("セクションＥＸ１") == "章节 EX1"
    assert resolve_section_label("セクション３Ａ") == "章节 3A"


def test_resolve_section_label_non_section_prefix_returns_none():
    assert resolve_section_label("何か別の文字列") is None
    assert resolve_section_label("セクション") is None  # 无后缀 X，不成立


# ---------------------------------------------------------------------------
# resolve_quote_content / resolve_paren_content：card_msg 两个槽位的解析优先级。
# ---------------------------------------------------------------------------

def test_resolve_quote_content_exact_card_match_wins(idx):
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_quote_content("ある子が学校にくる物語", title_to_cards, zh_by_card)
    assert zh == "有个孩子来学校的故事"
    assert src == "cards.zh:card=1"


def test_resolve_quote_content_section_fallback(idx):
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_quote_content("セクション１", title_to_cards, zh_by_card)
    assert zh == "章节 1"
    assert src == "rule:セクション→章节"


def test_resolve_quote_content_ehon_alias(idx):
    """TITLE_ALIASES：绘本标题分かち書き空格形『いつか きみが みる お話』要对上冻结卡
    145 的 title_jp『いつかきみがみるお話。』（无空格、带句号）——精确匹配对不上，
    走别名表；取值时去掉冻结 title_zh 的尾句号。"""
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_quote_content("いつか きみが みる お話", title_to_cards, zh_by_card)
    assert zh == "总有一天你会看到的故事"   # 已去掉尾句号
    assert src == "cards.zh:card=145（空格形）"


def test_resolve_quote_content_no_match_returns_none_none(idx):
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_quote_content("完全无关的字符串", title_to_cards, zh_by_card)
    assert zh is None and src is None


def test_resolve_paren_content_card_name_match(idx):
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_paren_content("ある子が学校にくる物語", title_to_cards, zh_by_card)
    assert zh == "有个孩子来学校的故事"
    assert src.startswith("cards.zh:card=1")


def test_resolve_paren_content_option_table(idx):
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_paren_content("羨ましがる", title_to_cards, zh_by_card)
    assert zh == "表示羡慕"
    assert src == "ruling:选项文本"


def test_resolve_paren_content_no_match_returns_none_none(idx):
    _, zh_by_card, title_to_cards = idx
    zh, src = resolve_paren_content("完全无关的字符串", title_to_cards, zh_by_card)
    assert zh is None and src is None


# ---------------------------------------------------------------------------
# OPTION_TABLE：14 条选项文本定译表——内容与用户裁定逐字核对。
# ---------------------------------------------------------------------------

def test_option_table_has_exactly_14_entries_matching_ruling():
    assert OPTION_TABLE == {
        "羨ましがる": "表示羡慕",
        "受け入れる": "接受",
        "興味を惹かれた": "被勾起了兴趣",
        "机を調べる": "检查课桌",
        "ノートを調べる": "翻看笔记本",
        "腕を掴む": "抓紧她的手",
        "家に帰る": "回家",
        "行く": "去",
        "両思いになるオマジナイ": "两情相悦的咒语",
        "適当に濁す": "含糊带过",
        "約束をしていない、している": "没有约定、有约定",
        "絶対に効く": "绝对灵验",
        "教えて": "告诉我",
        "聞かない": "不听",
    }


def test_title_aliases_has_ehon_entry():
    assert TITLE_ALIASES == {"いつか きみが みる お話": 145}


def test_card_msg_templates_has_exactly_12_entries():
    assert len(CARD_MSG_TEMPLATES) == 12
    # {0} 槽位必须都存在；含（…）的模板骨架必须都带 {1}。
    for skeleton, zh_tmpl in CARD_MSG_TEMPLATES.items():
        assert "{0}" in zh_tmpl
        if "（…）" in skeleton:
            assert "{1}" in zh_tmpl


# ---------------------------------------------------------------------------
# derive_card_msg：模板 + 槽位解析全链路。confidence=template（不再恒 none）。
# ---------------------------------------------------------------------------

def test_derive_card_msg_known_card_name_resolves_to_template(idx):
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_crd_1:1", "jp": "『ある子が学校にくる物語』のあらすじを作成しました。",
           "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "template"
    assert result["zh"] == "已写下『有个孩子来学校的故事』的梗概。"
    assert "cards.zh:card=1" in result["source"]
    assert "template:" in result["source"]
    assert anomaly is None


def test_derive_card_msg_choice_slot_with_option_table(idx):
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_crd_1:2",
           "jp": "『ある子が学校にくる物語』の選択肢（羨ましがる）を作成しました。",
           "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "template"
    assert result["zh"] == "已写下『有个孩子来学校的故事』的选项（表示羡慕）。"
    assert "ruling:选项文本" in result["source"]
    assert anomaly is None


def test_derive_card_msg_choice_slot_with_card_name_in_parens(idx):
    """（…）槽位内容本身也是一个冻结卡名时，走卡名匹配而不是 OPTION_TABLE。"""
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_crd_1:3",
           "jp": "『ある子が学校にくる物語』の選択肢（夏の朝、高校までの通学路）を作成しました。",
           "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "template"
    assert result["zh"] == "已写下『有个孩子来学校的故事』的选项（夏日清晨，通往高中的上学路）。"
    assert result["source"].count("cards.zh:card=") == 2


def test_derive_card_msg_embedded_parens_in_card_name_not_confused_with_slot(idx):
    """端到端回归：卡名『サクラの日記：７月（書きかけ）』自带括号，真正的选项槽位在
    卡名闭合之后——译文里必须出现「表示羡慕」（真槽位），不能出现「未写完」（卡名里
    误抓到的括号内容）。"""
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_crd_6:1",
           "jp": "『サクラの日記：７月（書きかけ）』の選択肢（羨ましがる）を作成しました。",
           "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "template"
    assert result["zh"] == "已写下『サクラ的日记：7月（未写完）』的选项（表示羡慕）。"
    assert "表示羡慕" in result["zh"]
    assert anomaly is None


def test_derive_card_msg_section_fallback_resolves(idx):
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:5", "jp": "『セクション１』のあらすじを作成しました。", "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "template"
    assert result["zh"] == "已写下『章节 1』的梗概。"
    assert anomaly is None


def test_derive_card_msg_ehon_alias_resolves(idx):
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:7", "jp": "『いつか きみが みる お話』のあらすじを作成しました。",
           "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "template"
    assert result["zh"] == "已写下『总有一天你会看到的故事』的梗概。"


def test_derive_card_msg_unknown_slot_content_flagged_as_anomaly(idx):
    """『…』槽位内容既不是冻结卡名、也不匹配 TITLE_ALIASES/セクション 兜底规则——
    必须单列为异常，不能悄悄放过，confidence 仍是 none。"""
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:8", "jp": "『完全无关的字符串』のあらすじを作成しました。", "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "none"
    assert result["zh"] == ""
    assert anomaly is not None
    assert "既不是冻结卡名" in anomaly


def test_derive_card_msg_unknown_paren_content_flagged_as_anomaly(idx):
    """『…』能解出，但（…）槽位内容既不是卡名也不在 OPTION_TABLE 里——同样必须
    confidence=none 且单列异常，不能"quote 解出来就凑合拼一半"。"""
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:9",
           "jp": "『ある子が学校にくる物語』の選択肢（完全无关的字符串）を作成しました。",
           "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "none"
    assert result["zh"] == ""
    assert anomaly is not None
    assert "OPTION_TABLE" in anomaly


def test_derive_card_msg_unknown_template_skeleton_flagged_not_crashed(idx):
    """不在 12 种定稿模板表内的骨架（未来若 lua 冒出新句式）——不能崩溃，也不能假装
    能拼，必须 confidence=none 并单列异常。"""
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:10", "jp": "『ある子が学校にくる物語』を削除しました。", "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "none"
    assert anomaly is not None
    assert "未知模板骨架" in anomaly


def test_derive_card_msg_no_bracket_flagged(idx):
    _, zh_by_card, title_to_cards = idx
    row = {"key": "snr_x:6", "jp": "没有书名号的文本", "kind": "card_msg"}
    result, anomaly = derive_card_msg(row, title_to_cards, zh_by_card)
    assert result["confidence"] == "none"
    assert anomaly is not None


# ---------------------------------------------------------------------------
# derive_savedata：安全闸③——空串不能被当成缺失而跳过。
# ---------------------------------------------------------------------------

def test_derive_savedata_nonempty():
    row = {"key": "snr_mainmenu:190:1", "jp": "タイトル", "kind": "savedata"}
    result, anomaly = derive_savedata(row)
    assert result["confidence"] == "none"
    assert result["zh"] == ""
    assert result["key"] == "snr_mainmenu:190:1"


def test_derive_savedata_empty_string_still_produces_a_row():
    """安全闸③核心用例：jp=='' 必须仍然输出一条结果（key/kind 保留），
    不能因为 falsy 就 return None / 被上层过滤掉。"""
    row = {"key": "snr_mainmenu:190:2", "jp": "", "kind": "savedata"}
    result, anomaly = derive_savedata(row)
    assert result is not None
    assert result["key"] == "snr_mainmenu:190:2"
    assert result["jp"] == ""
    assert result["confidence"] == "none"


def test_derive_all_never_drops_rows_including_empty_savedata(idx):
    """端到端：derive_all 对「空 jp 的 savedata」也必须原样计入结果条数，
    不能因为 jp 是空字符串就在聚合层被过滤。"""
    jp_by_card, zh_by_card, title_to_cards = idx
    rows = [
        {"key": "a:1", "jp": "タイトル", "kind": "savedata", "file": "x"},
        {"key": "a:2", "jp": "", "kind": "savedata", "file": "x"},
        {"key": "a:3", "jp": "", "kind": "savedata", "file": "x"},
    ]
    results, anomalies = derive_all(rows, jp_by_card, zh_by_card, title_to_cards)
    assert len(results) == 3
    assert {r["key"] for r in results} == {"a:1", "a:2", "a:3"}


def test_derive_all_unknown_kind_does_not_crash(idx):
    jp_by_card, zh_by_card, title_to_cards = idx
    rows = [{"key": "a:1", "jp": "??", "kind": "mystery_kind", "file": "x"}]
    results, anomalies = derive_all(rows, jp_by_card, zh_by_card, title_to_cards)
    assert len(results) == 1
    assert results[0]["confidence"] == "none"
    assert anomalies  # 未知 kind 也要报出来，不能悄悄吞掉


# ---------------------------------------------------------------------------
# build_report：至少要覆盖总览表与模板定稿表存在。
# ---------------------------------------------------------------------------

def test_build_report_contains_overview_and_template_table(idx):
    jp_by_card, zh_by_card, title_to_cards = idx
    rows = [
        {"key": "plotTitle:1", "jp": "ある子が学校にくる物語", "kind": "plot_title", "file": "x"},
        {"key": "snr_crd_1:1", "jp": "『ある子が学校にくる物語』のあらすじを作成しました。",
         "kind": "card_msg", "file": "x"},
        {"key": "a:1", "jp": "", "kind": "savedata", "file": "x"},
    ]
    results, anomalies = derive_all(rows, jp_by_card, zh_by_card, title_to_cards)
    report = build_report(rows, results, anomalies)
    assert "## 总览" in report
    assert "card_msg 12 种模板定稿表" in report
    assert "plotTitle:1" in report


# ---------------------------------------------------------------------------
# main()：文件级集成测试，跑在 tmp_path 上的最小夹具，验证不落任何生产数据目录。
# ---------------------------------------------------------------------------

def test_main_writes_jsonl_and_report_and_matches_row_count(tmp_path):
    ledger_p = tmp_path / "ledger_extra.jsonl"
    write_jsonl(ledger_p, [
        {"key": "plotTitle:1", "jp": "ある子が学校にくる物語", "kind": "plot_title", "file": "x"},
        {"key": "a:1", "jp": "", "kind": "savedata", "file": "x"},
    ])
    cards_jp_p = tmp_path / "cards.jp.yaml"
    cards_zh_p = tmp_path / "cards.zh.yaml"
    cards_jp_p.write_text(
        "- card: 1\n  title_jp: ある子が学校にくる物語\n", encoding="utf-8")
    cards_zh_p.write_text(
        "- card: 1\n  title_zh: 有个孩子来学校的故事\n", encoding="utf-8")
    out_jsonl = tmp_path / "out.jsonl"
    out_report = tmp_path / "out.md"

    rc = main([
        "--ledger", str(ledger_p),
        "--cards-jp", str(cards_jp_p),
        "--cards-zh", str(cards_zh_p),
        "--out-jsonl", str(out_jsonl),
        "--out-report", str(out_report),
    ])
    assert rc == 0
    rows = read_jsonl(out_jsonl)
    assert len(rows) == 2
    plot_row = next(r for r in rows if r["key"] == "plotTitle:1")
    assert plot_row["zh"] == "有个孩子来学校的故事"
    assert plot_row["confidence"] == "exact"
    save_row = next(r for r in rows if r["key"] == "a:1")
    assert save_row["confidence"] == "none"
    assert out_report.exists()
    assert "总览" in out_report.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 真实数据冒烟：对着已冻结的 skeleton/ + 真实 ledger_extra.jsonl 跑一遍，钉住
# 已实测核对过的关键不变量，防止未来 lua/skeleton 改动悄悄破坏这些前提。
# ---------------------------------------------------------------------------

def test_real_data_plot_title_all_195_exact_match():
    """已实测核对：extra 轨 195 条 plot_title 的 jp 与 cards.jp.yaml 逐字吻合 195/195。
    此测试钉住这一前提；若未来骨架或 ledger 改动打破它，测试会先叫出来，而不是让
    derive_extra.py 静默产出变少的 exact 数。"""
    ledger = read_jsonl(REPO / "pilot/lanes/opus/data/ledger_extra.jsonl")
    import yaml
    cards_jp = yaml.safe_load((REPO / "skeleton/cards.jp.yaml").read_text(encoding="utf-8"))
    cards_zh = yaml.safe_load((REPO / "skeleton/cards.zh.yaml").read_text(encoding="utf-8"))
    jp_by_card, zh_by_card, title_to_cards = build_card_indexes(cards_jp, cards_zh)
    pt_rows = [r for r in ledger if r["kind"] == "plot_title"]
    assert len(pt_rows) == 195
    results, anomalies = derive_all(pt_rows, jp_by_card, zh_by_card, title_to_cards)
    exact = [r for r in results if r["confidence"] == "exact"]
    assert len(exact) == 195, (
        f"预期 195/195 exact，实得 {len(exact)}；差异说明 skeleton 或 ledger_extra 有变动，"
        f"需要重新核对，不能假设旧结论仍成立")
    assert anomalies == []


def test_real_data_card_msg_all_172_resolve_to_template():
    """已实测核对：extra 轨 172 条 card_msg 全部能靠模板+槽位解析拼出 zh
    （172/172 confidence=template，0 异常）。此测试钉住这一前提——它同时覆盖了
    12 种模板全部收录、OPTION_TABLE 14 条全部命中、TITLE_ALIASES 与 セクション
    兜底规则都跑得通这几件事，任一环节退化都会让这个数字掉下来。"""
    ledger = read_jsonl(REPO / "pilot/lanes/opus/data/ledger_extra.jsonl")
    import yaml
    cards_jp = yaml.safe_load((REPO / "skeleton/cards.jp.yaml").read_text(encoding="utf-8"))
    cards_zh = yaml.safe_load((REPO / "skeleton/cards.zh.yaml").read_text(encoding="utf-8"))
    jp_by_card, zh_by_card, title_to_cards = build_card_indexes(cards_jp, cards_zh)
    cm_rows = [r for r in ledger if r["kind"] == "card_msg"]
    assert len(cm_rows) == 172
    results, anomalies = derive_all(cm_rows, jp_by_card, zh_by_card, title_to_cards)
    tmpl_ok = [r for r in results if r["confidence"] == "template"]
    assert len(tmpl_ok) == 172, (
        f"预期 172/172 template，实得 {len(tmpl_ok)}；差异说明 skeleton/ledger_extra 有变动"
        f"或某条派生规则退化了，需要重新核对，不能假设旧结论仍成立")
    assert anomalies == []
    assert all(r["zh"] for r in tmpl_ok), "template 命中的行不能有空 zh"


def test_real_data_derive_never_drops_a_row_and_writes_nothing_to_pilot_dir(tmp_path):
    """端到端跑一次真实 ledger_extra.jsonl，只写到 tmp_path，绝不碰
    pilot/lanes/opus/data/。同时钉住"逐条派生、不丢行"这一硬约束。"""
    out_jsonl = tmp_path / "extra_derived.jsonl"
    out_report = tmp_path / "extra_derive_report.md"
    rc = main([
        "--ledger", str(REPO / "pilot/lanes/opus/data/ledger_extra.jsonl"),
        "--cards-jp", str(REPO / "skeleton/cards.jp.yaml"),
        "--cards-zh", str(REPO / "skeleton/cards.zh.yaml"),
        "--out-jsonl", str(out_jsonl),
        "--out-report", str(out_report),
    ])
    assert rc == 0
    ledger = read_jsonl(REPO / "pilot/lanes/opus/data/ledger_extra.jsonl")
    results = read_jsonl(out_jsonl)
    # 827：换基座后 extra 轨条数（旧基座 829，多出的 2 条是反编译冗余）
    assert len(results) == len(ledger) == 827
