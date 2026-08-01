import json
import pytest
from tools.detect_collapse import scan, retained_names, main


def test_untranslated_line_is_flagged_by_kana_ratio():
    """整行原文照抄：长度比正常（1.0，落在 C2 阈值内），只能靠假名比抓住。"""
    src = [{"id": 1, "jp": "彼女は静かに笑った。"}]
    drf = [{"id": 1, "zh": "彼女は静かに笑った。"}]
    hits = scan(src, drf)
    assert any(h["rule"] == "C1" and h["id"] == 1 for h in hits)


def test_retained_katakana_names_do_not_trigger_kana_rule():
    src = [{"id": 2, "jp": "【アヤノ】「ユウイチ、おはよう」"}]
    drf = [{"id": 2, "zh": "【アヤノ】「ユウイチ，早上好」"}]
    hits = scan(src, drf, names={"アヤノ", "ユウイチ"})
    assert not any(h["rule"] == "C1" for h in hits)


def test_ratio_outliers_are_flagged():
    src = [{"id": 3, "jp": "あ" * 100}, {"id": 4, "jp": "あ" * 10}]
    drf = [{"id": 3, "zh": "短"},                    # 比 0.01，过短
           {"id": 4, "zh": "长" * 40}]               # 比 4.0，过长
    hits = scan(src, drf)
    assert {h["id"] for h in hits if h["rule"] == "C2"} == {3, 4}


def test_normal_ratio_is_not_flagged():
    """已定稿译文的实测比区间 0.48–1.20 必须全部放行。"""
    src = [{"id": 5, "jp": "あ" * 100}]
    for zh_len in (48, 85, 120):
        drf = [{"id": 5, "zh": "中" * zh_len}]
        assert not [h for h in scan(src, drf) if h["rule"] == "C2"], \
            f"比 {zh_len/100} 是已定稿样本内的正常值，不该告警"


def test_repeated_substring_loop_is_flagged():
    """真实的 LLM 退化复读通常是整句/长短语级循环（4 字单元起，非 3 字
    以下的中文合法叠字/情绪重复，见下方 test_short_emotive_repetition_is_not_flagged）。"""
    src = [{"id": 6, "jp": "分からない、分からない、分からない。"}]
    drf = [{"id": 6, "zh": "我不知道我不知道我不知道"}]
    hits = scan(src, drf)
    assert any(h["rule"] == "C3" and h["id"] == 6 for h in hits)


def test_short_emotive_repetition_is_not_flagged():
    """视觉小说里 3 字及以下的重复多是合法情绪表达（笑声、省略号、致歉/
    诘问台词的连喊），不是模型退化，C3 不该对其告警——这是本工具唯一价值
    「命中值得一看」的判别点，必须钉住。"""
    src = [{"id": 11, "jp": "ごめん、ごめん、ごめん……"},
           {"id": 12, "jp": "あはははは"},
           {"id": 13, "jp": "……………………"}]
    drf = [{"id": 11, "zh": "对不起对不起对不起"},
           {"id": 12, "zh": "哈哈哈哈哈哈"},
           {"id": 13, "zh": "……………………"}]
    hits = scan(src, drf)
    assert not [h for h in hits if h["rule"] == "C3"]


def test_duplicated_lines_across_batch_are_flagged():
    src = [{"id": i, "jp": f"原文{i}あああああ"} for i in (7, 8, 9)]
    drf = [{"id": i, "zh": "完全相同的一整句译文内容"} for i in (7, 8, 9)]
    hits = scan(src, drf)
    assert len([h for h in hits if h["rule"] == "C3"]) >= 3


def test_clean_batch_yields_nothing():
    src = [{"id": 10, "jp": "遠くから『帰りの歌』が聞こえてきた。"}]
    drf = [{"id": 10, "zh": "远处传来了『回家的歌谣』。"}]
    assert scan(src, drf) == []


def test_f12_kana_punct_not_counted():
    # ・（U+30FB）项目符号、ー（U+30FC）、゠（U+30A0）不再计入假名比
    src = [{"id": 1, "jp": "・項目一・項目二"}]
    drf = [{"id": 1, "zh": "・条目一・条目二——ー゠"}]
    assert scan(src, drf) == []


def test_f9_quoted_jp_kana_exempt_but_untranslated_still_caught():
    src = [
        {"id": 1, "jp": "「に」「ん」「げ」「ん」――にんげん、と読めた。"},
        {"id": 2, "jp": "ずっとまえから、すきでした。ほんとうです。"},
    ]
    drf = [
        # 钱仙拼字：引用原文假名（短串，均在 jp 中）→ 不报 C1
        {"id": 1, "zh": "「に」「ん」「げ」「ん」――拼出来是「にんげん」，人类。"},
        # 整行未译（长假名串）→ 仍报 C1
        {"id": 2, "zh": "ずっとまえから、すきでした。ほんとうです。"},
    ]
    hits = scan(src, drf)
    assert [h["id"] for h in hits if h["rule"] == "C1"] == [2]


def test_f4_dup_thresholds_via_params():
    src = [{"id": i, "jp": "x" * 10} for i in (1, 2)]
    drf = [{"id": i, "zh": "同样的八字译文"} for i in (1, 2)]   # 7 字 ×2 次：默认不报
    assert [h for h in scan(src, drf) if h["rule"] == "C3"] == []
    hits = scan(src, drf, dup_min_len=6, dup_min_count=2)       # 收紧后报
    assert len([h for h in hits if h["rule"] == "C3"]) == 2


def test_retained_names_reads_glossary_characters(tmp_path):
    g = tmp_path / "glossary.v6.yaml"
    g.write_text(
        "characters:\n"
        "  - {jp: アヤノ, zh: アヤノ, layer: story}\n"
        "  - {jp: ユウイチ, zh: ユウイチ, layer: both}\n"
        "  - {jp: きくちゃん, zh: 小菊, layer: real}\n"
        "  - {jp: 直哉, zh: 直哉, layer: real}\n", encoding="utf-8")
    assert retained_names(g) == {"アヤノ", "ユウイチ"}


def test_main_writes_report_and_always_returns_zero(tmp_path, monkeypatch):
    import tools.detect_collapse as dc
    work = tmp_path / "work"
    (work / "ctx" / "batch_1").mkdir(parents=True)
    (work / "out").mkdir(parents=True)
    (work / "ctx" / "batch_1" / "source.jsonl").write_text(
        json.dumps({"id": 1, "jp": "彼女は静かに笑った。"}, ensure_ascii=False),
        encoding="utf-8")
    (work / "out" / "batch_1.draft.jsonl").write_text(
        json.dumps({"id": 1, "zh": "彼女は静かに笑った。"}, ensure_ascii=False),
        encoding="utf-8")
    (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v6.yaml").write_text("characters: []",
                                                            encoding="utf-8")
    monkeypatch.setattr(dc, "WORK", work)
    monkeypatch.setattr(dc, "REPO", tmp_path)
    assert main(["--batch", "1"]) == 0
    rep = json.loads((work / "out" / "batch_1.collapse.json").read_text(
        encoding="utf-8"))
    assert any(h["rule"] == "C1" for h in rep)
