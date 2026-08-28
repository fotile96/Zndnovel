"""`tools/measure_ui_terms.py` —— UI 术语表的**自校准闸**。

它防的是 2026-08-19～08-28 真实发生过的那件事：glossary v19 把故事层人名改成罗马音，
而 `config/ui_terms.yaml` 里 `ユウイチ → ユウイチ` 那条纹丝不动。`check_ui_terms.py`
照常运行、照常"绿"，只不过它守的是**一条已经作废的规则**——还反过来把已经改对的
extra 车道报成 10 条 mismatch。

冻结的 evidence 字符串没有任何机制会因正文变化而失效，所以必须有人主动去量。
本模块就是那个"人"。
"""

import json

import pytest

from tools.measure_ui_terms import (
    Measurement,
    corpus_pairs,
    measure_all,
    measure_term,
)


# ---------------------------------------------------------------------------
# 1. 语料装配：patches 覆盖 forward，卡面按 (card, variant) 对齐
# ---------------------------------------------------------------------------


def _write(p, rows):
    p.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


@pytest.fixture
def fake_repo(tmp_path):
    (tmp_path / "data").mkdir()
    lane = tmp_path / "pilot" / "lanes" / "opus" / "data"
    lane.mkdir(parents=True)
    (tmp_path / "skeleton").mkdir()

    _write(
        tmp_path / "data" / "ledger.jsonl",
        [
            {"id": 1, "jp": "ユウイチは笑った"},
            {"id": 2, "jp": "アヤノの物語"},
            {"id": 3, "jp": "訳されていない行"},
        ],
    )
    _write(lane / "forward.jsonl", [{"id": 1, "zh": "ユウイチ笑了"}, {"id": 2, "zh": "アヤノ的故事"}])
    _write(lane / "patches.jsonl", [{"id": 1, "zh": "Yuichi笑了"}])

    (tmp_path / "skeleton" / "cards.jp.yaml").write_text(
        "- card: 1\n  variant: a\n  title_jp: ユウイチ\n  body_jp: アヤノとサクラ\n",
        encoding="utf-8",
    )
    (tmp_path / "skeleton" / "cards.zh.yaml").write_text(
        "- card: 1\n  variant: a\n  title_zh: Yuichi\n  body_zh: Ayano与Sakura\n",
        encoding="utf-8",
    )
    return tmp_path


def test_patches_override_forward(fake_repo):
    """id 1 在 forward 里还是片假名，patches 里已罗马音——必须取 patches。

    取错这一头，量出来的就是**上一个版本的正文**，校准的意义全失。
    """
    pairs = corpus_pairs(fake_repo)
    zh_of_1 = [zh for jp, zh in pairs if jp == "ユウイチは笑った"]
    assert zh_of_1 == ["Yuichi笑了"]


def test_untranslated_ledger_lines_are_excluded(fake_repo):
    """ledger 有 3 行、译文只有 2 行；没有 zh 的行不能进分母。

    否则每条术语都会被那 56 条 ambient 行无差别地稀释。
    """
    pairs = corpus_pairs(fake_repo)
    assert all(jp != "訳されていない行" for jp, _ in pairs)


def test_card_title_and_body_both_enter_corpus(fake_repo):
    pairs = corpus_pairs(fake_repo)
    assert ("ユウイチ", "Yuichi") in pairs
    assert ("アヤノとサクラ", "Ayano与Sakura") in pairs


# ---------------------------------------------------------------------------
# 2. 逐条测量
# ---------------------------------------------------------------------------


def test_measure_term_counts_hits_over_jp_occurrences():
    pairs = [("ユウイチだ", "Yuichi"), ("ユウイチと", "还是ユウイチ"), ("無関係", "无关")]
    m = measure_term("ユウイチ", "Yuichi", pairs)
    assert (m.hits, m.total) == (1, 2)
    assert m.pct == pytest.approx(50.0)


def test_measure_term_honours_exempt_jp():
    """`作成` 那条的真实形状：排除「物語」语境后占比才达标。

    没有 exempt 这一层，语义分层会被读成用词混乱，好好的术语被误判成该除名。
    """
    pairs = [
        ("あらすじを作成", "制作梗概"),
        ("あらすじを作成した", "制作了梗概"),
        ("物語を作成", "创作故事"),
    ]
    assert measure_term("作成", "制作", pairs).pct == pytest.approx(2 / 3 * 100)
    assert measure_term("作成", "制作", pairs, exempt_jp=("物語",)).pct == 100.0


def test_measure_term_with_no_occurrences_is_not_a_division_error():
    m = measure_term("存在しない語", "无", [("あ", "啊")])
    assert (m.hits, m.total, m.pct) == (0, 0, 0.0)


def test_drifted_flags_only_terms_below_threshold():
    pairs = [("ユウイチ", "Yuichi")] * 99 + [("ユウイチ", "ユウイチ")]
    good = measure_term("ユウイチ", "Yuichi", pairs)
    bad = measure_term("ユウイチ", "ユウイチ", pairs)
    assert not good.drifted(85.0)
    assert bad.drifted(85.0)


def test_zero_occurrence_term_is_drift_not_silently_ok():
    """一条术语在正文里一次都不出现，说明它管的东西已经不在了。

    `pct == 0` 若被当成"没数据所以跳过"，表就会攒下一堆僵尸条目。
    """
    assert measure_term("存在しない語", "无", [("あ", "啊")]).drifted(85.0)


# ---------------------------------------------------------------------------
# 3. 对真仓库：校准后必须零漂移
# ---------------------------------------------------------------------------


def test_real_config_has_zero_drift_against_current_translations():
    """**本文件的主张就在这一条上。**

    `config/ui_terms.yaml` 的每条定译，都必须仍是现行译文里的压倒性用法。
    这条一旦红，意味着 glossary 又升版了而这张表没跟上——去跑
    `uv run python tools/measure_ui_terms.py` 看是哪几条。
    """
    ms = measure_all()
    drifted = [m for m in ms if m.drifted()]
    assert drifted == [], "\n".join(
        f"{m.jp} -> {m.zh}: {m.hits}/{m.total}（{m.pct:.1f}%）" for m in drifted
    )


def test_real_config_evidence_strings_match_measured_numbers():
    """evidence 写的数字必须**就是**现在量出来的数字。

    这是本工具存在的理由：evidence 是人手写的字符串，写完就冻住了。
    只查占比不查数字，表会慢慢变成一份看着很权威的考古记录。
    """
    ms = measure_all()
    stale = [m for m in ms if not m.evidence_matches()]
    assert stale == [], "\n".join(
        f"{m.jp}: 记 {m.evidence!r}，实测 {m.hits}/{m.total}（{m.pct:.1f}%）" for m in stale
    )


def test_rewrite_evidence_keeps_prose_after_the_numbers():
    from tools.measure_ui_terms import rewrite_evidence

    src = "terms:\n  - jp: 屋上\n    zh: 天台\n    evidence: 465 行中 465 行（100%）；「屋顶」是常见误译\n"
    m = Measurement(jp="屋上", zh="天台", evidence="", hits=467, total=467)
    assert "467 行中 467 行（100%）；「屋顶」是常见误译" in rewrite_evidence(src, [m])


def test_rewrite_evidence_refuses_unparsable_rather_than_eating_the_prose():
    """`砂時計` 的旧写法「2 行 2 中（唯一取值；…）」不合规范格式。

    整行覆盖会把后面那句理由一并吞掉，而且**没有任何人会发现**——所以宁可报错。
    """
    from tools.measure_ui_terms import rewrite_evidence

    src = "terms:\n  - jp: 砂時計\n    zh: 沙漏\n    evidence: 2 行 2 中（唯一取值；教程原文如此）\n"
    m = Measurement(jp="砂時計", zh="沙漏", evidence="", hits=2, total=2)
    with pytest.raises(ValueError, match="砂時計"):
        rewrite_evidence(src, [m])


def test_measure_all_covers_every_registered_term():
    import yaml

    from tools.measure_ui_terms import CONFIG

    n = len(yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["terms"])
    assert len(measure_all()) == n
    assert all(isinstance(m, Measurement) for m in measure_all())
