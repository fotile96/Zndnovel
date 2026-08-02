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
    # ・（U+30FB）项目符号、ー（U+30FC）、゠（U+30A0）不再计入假名比。
    # zh 长度刻意比 jp*1.50 的 C2 上限留出余量（11/8=1.375），避免日后
    # 微调 RATIO_HI 时本测试因触碰 C2 边界而以"F12 失败"的假象报红。
    src = [{"id": 1, "jp": "・項目一・項目二"}]
    drf = [{"id": 1, "zh": "・条目一・条目二—ー゠"}]
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


def test_f9_approx_copy_with_trailing_period_still_caught():
    """近似复制伪装 1：整行照抄 jp 后仅在句尾多加一个「。」。zh != jp 依然
    成立，但豁免预算门槛（F9 二轮修复）必须挡住它——不能因为"动了一个
    标点"就把整行漏译洗成 0。"""
    src = [{"id": 1, "jp": "彼女は静かに笑った。"}]
    drf = [{"id": 1, "zh": "彼女は静かに笑った。。"}]
    hits = scan(src, drf)
    assert any(h["rule"] == "C1" and h["id"] == 1 for h in hits)


def test_f9_approx_copy_with_punct_swap_still_caught():
    """近似复制伪装 2：整行照抄 jp，把日文读点「、」换成中文逗号「，」
    ——这是 LLM 退化时最典型的输出形态之一，同样必须仍报 C1。"""
    src = [{"id": 2, "jp": "ずっとまえから、すきでした。ほんとうです。"}]
    drf = [{"id": 2, "zh": "ずっとまえから，すきでした。ほんとうです。"}]
    hits = scan(src, drf)
    assert any(h["rule"] == "C1" and h["id"] == 2 for h in hits)


def test_f9_known_recall_gap_copy_wrapped_in_chinese_phrases():
    """**已知召回缺口，非期望行为**——见 `docs/ops/p3-production-runbook.md` §4
    的 A/B 召回表。

    「整行照抄 + 前后各加一句中文」是 LLM 最自然的偷懒形态，也正是 F9 豁免
    （JP_QUOTE_BUDGET/JP_QUOTE_MIN_NOVEL）净损最大的一档：全 ledger 16101 行
    含假名原文的伪装集实测，旧码 C1 召回 98.5%，新码约 50–54%（净损 ≈ −44～
    −48pp，随包裹短语长短浮动）。包裹的中文既拉低了「被豁免假名 / len(zh)」的
    预算占比，又把「换新率」抬到门槛之上，于是整行漏译被当成「作品内引用」放掉。

    本用例断言的是**当前的实际行为**（漏报），目的是让这个缺口在 CI 上可见而
    不是隐形。**不要为了让它变绿去改实现或放宽阈值**——F9 的收益侧是真实的
    （已入线 6146 行真实译文 C1 命中 27→8、消 19 新增 0），召回与误报之间的
    取舍必须由人显式做出并留痕（runbook §4），canary 结构上看不到这一侧。
    若哪天它失败了，说明有人改了取舍：请同步更新 runbook §4 的 A/B 表和本注释。

    jp 取自真实 ledger（探索场景 アヤノ 的到场台词），不是为了复现数字而捏造的
    夹具。"""
    jp = "【アヤノ】「靴を履き替えて、中庭に出たよ」"
    wrapped = "他沉默了一会儿，" + jp + "，语气里带着落寞。"
    assert [h for h in scan([{"id": 1, "jp": jp}], [{"id": 1, "zh": wrapped}])
            if h["rule"] == "C1"] == [], "召回缺口已变化——请重跑 A/B 并更新 runbook §4"
    # 对照组：同一行不加中文包裹时照样抓得住（F9 的 zh==jp 短路与预算 gate 仍在），
    # 证明上面的漏报确实来自「中文包裹」这一维，而不是这行本身就抓不到。
    assert [h["id"] for h in scan([{"id": 1, "jp": jp}], [{"id": 1, "zh": jp}])
            if h["rule"] == "C1"] == [1]
    assert [h["id"] for h in scan([{"id": 1, "jp": jp}], [{"id": 1, "zh": jp + "。"}])
            if h["rule"] == "C1"] == [1]


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
