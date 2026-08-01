"""提案预聚类：notes/*.md 散提案 → 按词族聚合的裁决卷宗（P3 spec §4 新工具）。"""
from tools.cluster_notes import parse_notes, cluster, extract_terms

NOTES = """# 术语提案 · s1s（opus 车道）

> 说明行。

## batch 4

### 1. 寝癖 → 睡翘的头发（**跨轨复现**）
- id 7327、7329
- 理由：略。

### 2. 菜单名的拉丁形态需要一条形态判据
- id 6632

### 3. 『ことば』(7302) → 『话语』
- 建议沿用。

## batch 7

### 1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质
- id 6351

### 2. ★存疑（非术语）：7374 的行宽警告
- 不是术语。

### 3. 寝癖 → 头发睡翘了
- 又一处。
"""


def test_parse_notes_blocks_and_batches():
    ps = parse_notes(NOTES, "s1s")
    assert len(ps) == 6
    assert [p["batch"] for p in ps] == [4, 4, 4, 7, 7, 7]
    assert ps[0]["chapter"] == "s1s" and ps[0]["num"] == 1
    assert "id 7327" in ps[0]["body"]
    assert ps[4]["starred"] is True


def test_extract_terms_variants():
    assert extract_terms("1. 寝癖 → 睡翘的头发（**跨轨复现**）") == ["寝癖"]
    assert extract_terms("3. 『ことば』(7302) → 『话语』") == ["ことば"]
    assert extract_terms("1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质") == ["海馬", "内嗅皮質"]
    assert extract_terms("2. 菜单名的拉丁形态需要一条形态判据") == []


def test_extract_terms_multi_arrow_returns_empty():
    # 顿号分隔的多词小族：多个 → 不当成一个词键解析，直接归未归词待人工过目
    assert extract_terms("5. 押し入れ→壁橱、付箋紙→便签") == []
    assert extract_terms("5. 押し入れ→壁橱、付箋紙→便签、リビング→客厅") == []


def test_extract_terms_single_arrow_regression_unaffected():
    # 回归闸：单箭头（含 / 并列）不受多箭头 guard 影响，行为不变
    assert extract_terms("1. 寝癖 → 睡翘的头发（**跨轨复现**）") == ["寝癖"]
    assert extract_terms("1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质") == ["海馬", "内嗅皮質"]


def test_cluster_multi_arrow_title_buckets_unkeyed():
    ps = parse_notes(
        "## batch 1\n\n### 5. 押し入れ→壁橱、付箋紙→便签、リビング→客厅\n- 三词一并处理。\n",
        "s1s",
    )
    c = cluster(ps)
    assert ps[0]["terms"] == []
    assert len(c["（未归词）"]) == 1


def test_cluster_merges_across_batches_and_buckets_unkeyed():
    ps = parse_notes(NOTES, "s1s")
    c = cluster(ps)
    assert len(c["寝癖"]) == 2                       # batch 4 与 batch 7 合簇
    assert len(c["海馬"]) == 1 and len(c["内嗅皮質"]) == 1
    assert len(c["（未归词）"]) == 2                  # 无箭头 + ★存疑


def test_main_renders_dossier(tmp_path, capsys):
    import json
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(NOTES, encoding="utf-8")
    (lane / "data" / "ledger.jsonl").write_text(json.dumps(
        {"id": 7327, "jp": "寝癖がなおらない", "chapter": "s1s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 7327, "zh": "x"}), encoding="utf-8")
    rc = main(["--lane-dir", str(lane), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "寝癖" in out and "可裁决" in out          # 1/1 覆盖 → ratio 1.0 ≥ gate
    assert "（未归词）" in out
