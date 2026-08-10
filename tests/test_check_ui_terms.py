"""`tools/check_ui_terms.py` 的测试。

除了常规行为，重点是**变异自检**：把判据/数据改坏，闸必须响。一道只在
「一切正常」时验证过的闸，和一道恒绿的闸在测试里长得一模一样。
"""

from __future__ import annotations

import json
import textwrap

import pytest

from tools import check_ui_terms as m


@pytest.fixture
def repo(tmp_path):
    """一个最小仓库：术语表 + jp 语料。"""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "ui_terms.yaml").write_text(
        textwrap.dedent(
            """
            terms:
              - jp: 物語
                zh: 故事
                evidence: 测试用
                exempt_jp: [セカンドノベル]
              - jp: カード
                zh: 卡片
                evidence: 测试用
            not_terms:
              - jp: 学校
                measured: 学校 100%
                why: 同形词，无误译风险
            """
        ),
        encoding="utf-8",
    )
    d = tmp_path / "pilot" / "lanes" / "opus" / "data"
    d.mkdir(parents=True)
    # 让 discovery 里的候选词有足够的正文命中
    lines = [{"id": i, "jp": "屋上でカードを見た。学校の物語。"} for i in range(50)]
    d.joinpath("ledger.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in lines), encoding="utf-8"
    )
    return tmp_path


def labels(tmp_path, rows, name="labels.jsonl"):
    p = tmp_path / name
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
    )
    return p


def kinds(vs):
    return sorted(v.kind for v in vs)


# ── 基本行为 ──────────────────────────────────────────────────


def test_mismatch_is_reported(repo):
    p = labels(repo, [{"jp": "夏の物語", "zh": "夏天的物语"}])
    v = m.run([p], repo=repo)
    assert kinds(v) == ["mismatch"]
    assert "故事" in v[0].detail


def test_correct_rendering_passes(repo):
    p = labels(repo, [{"jp": "夏の物語", "zh": "夏天的故事"}])
    assert m.run([p], repo=repo) == []


def test_exempt_jp_skips_the_term(repo):
    """专有书名另有定译，不该被「物語→故事」牵连。"""
    p = labels(repo, [{"jp": "セカンドノベルの物語", "zh": "第二物语"}])
    assert m.run([p], repo=repo) == []


def test_pairs_missing_fields_rejected(repo):
    p = labels(repo, [{"jp": "夏の物語"}])
    with pytest.raises(ValueError, match="缺 jp/zh"):
        m.run([p], repo=repo)


# ── discovery 的两道门槛 ──────────────────────────────────────


def test_discovery_needs_repeat_use_in_labels(repo):
    """只出现一次的词是散文，不是术语——不该报。"""
    p = labels(repo, [{"jp": "屋上の風", "zh": "天台的风"}])
    assert m.run([p], repo=repo, min_hits=1) == []


def test_discovery_fires_on_repeated_unregistered_term(repo):
    p = labels(
        repo,
        [{"jp": "屋上の風", "zh": "天台的风"}, {"jp": "屋上の空", "zh": "天台的天空"}],
    )
    v = m.run([p], repo=repo, min_hits=1)
    assert kinds(v) == ["unregistered"]
    assert "屋上" in v[0].detail


def test_discovery_needs_corpus_presence(repo):
    """正文里没有的词，谈不上「与正文对齐」，不该报。"""
    p = labels(
        repo,
        [{"jp": "宇宙船の窓", "zh": "宇宙船的窗"}, {"jp": "宇宙船の扉", "zh": "宇宙船的门"}],
    )
    assert m.run([p], repo=repo, min_hits=1) == []


def test_not_terms_silences_discovery(repo):
    p = labels(
        repo, [{"jp": "学校の朝", "zh": "学校的早晨"}, {"jp": "学校の夜", "zh": "学校的夜"}]
    )
    assert m.run([p], repo=repo, min_hits=1) == []


# ── 配置自身的完整性 ──────────────────────────────────────────


def test_empty_term_table_refuses_to_run(repo):
    """一张空表会让闸恒绿。宁可报错，不可静默通过。"""
    (repo / "config" / "ui_terms.yaml").write_text("terms: []\n", encoding="utf-8")
    p = labels(repo, [{"jp": "夏の物語", "zh": "夏天的物语"}])
    with pytest.raises(ValueError, match="恒绿"):
        m.run([p], repo=repo)


def test_not_term_without_reason_refuses(repo):
    (repo / "config" / "ui_terms.yaml").write_text(
        "terms:\n  - {jp: 物語, zh: 故事}\nnot_terms:\n  - {jp: 学校}\n",
        encoding="utf-8",
    )
    p = labels(repo, [{"jp": "夏の物語", "zh": "夏天的故事"}])
    with pytest.raises(ValueError, match="理由"):
        m.run([p], repo=repo)


def test_suppression_without_reason_refuses(repo):
    (repo / "config" / "ui_term_suppressions.yaml").write_text(
        "suppress:\n  - {jp: 夏の物語, term: 物語}\n", encoding="utf-8"
    )
    p = labels(repo, [{"jp": "夏の物語", "zh": "夏天的物语"}])
    with pytest.raises(ValueError, match="why"):
        m.run([p], repo=repo)


def test_suppression_is_per_case_not_per_term(repo):
    """抑制一处，不该让同一术语在别处也失效。"""
    (repo / "config" / "ui_term_suppressions.yaml").write_text(
        "suppress:\n  - {jp: 夏の物語, term: 物語, why: 测试}\n", encoding="utf-8"
    )
    p = labels(
        repo,
        [{"jp": "夏の物語", "zh": "夏天的物语"}, {"jp": "冬の物語", "zh": "冬天的物语"}],
    )
    v = m.run([p], repo=repo)
    assert [x.jp for x in v] == ["冬の物語"]


# ── 变异自检：真实配置 + 真实数据 ─────────────────────────────


def test_real_config_loads_and_has_teeth():
    """真表能加载，且对一条已知的错译确实报警。"""
    terms = m.load_terms()
    assert len(terms) > 30
    bad = [{"jp": "夏の物語", "zh": "夏天的物语"}]
    v = m.check_mismatches(bad, terms, "x")
    assert any(t.jp == "物語" for t in terms)
    assert len(v) == 1


def test_real_config_每条术语都有证据():
    for t in m.load_terms():
        assert t.evidence, f"术语 {t.jp} 没有 evidence——判据必须可追溯到正文实测"


def test_mutating_a_term_breaks_clean_data(repo):
    """把定译改成别的词，本来干净的数据必须开始报警。

    这条不是在测功能，是在测「闸有没有牙」：若改判据而结果不变，
    说明这条术语根本没被用上。
    """
    p = labels(repo, [{"jp": "夏の物語", "zh": "夏天的故事"}])
    assert m.run([p], repo=repo) == []
    (repo / "config" / "ui_terms.yaml").write_text(
        "terms:\n  - {jp: 物語, zh: 传说, evidence: 变异}\n", encoding="utf-8"
    )
    assert kinds(m.run([p], repo=repo)) == ["mismatch"]


def test_landed_label_files_are_checked_by_ci(repo):
    """闸至少要被真正的产物文件跑过一次——否则它检的是空气。"""
    from pathlib import Path

    for name in (
        "data/card_section_labels.jsonl",
        "data/select_buttons_zh.jsonl",
    ):
        f = m.REPO / name
        assert f.exists(), f"{name} 不在了——闸的检查面缺了一块"
        assert m.load_pairs(f), f"{name} 是空的"
