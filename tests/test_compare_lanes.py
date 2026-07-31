import json
from tools.compare_lanes import (anchor_compliance, divergence, blind_pairs,
                                 stratified_sample, main)


def test_anchor_compliance_counts_verbatim_reuse():
    anchors = {1: "定译一", 2: "定译二"}
    fwd = [{"id": 1, "zh": "定译一"}, {"id": 2, "zh": "我自己重译的"}]
    r = anchor_compliance(fwd, anchors)
    assert r["total"] == 2 and r["verbatim"] == 1
    assert r["rate"] == 0.5 and r["violations"] == [2]


def test_divergence_excludes_anchor_ids():
    """锚点行两模型必然同串，混进区分度统计会制造"两模型很接近"的假阳性。"""
    zh_a = {1: "同", 2: "甲说法", 3: "同样"}
    zh_b = {1: "同", 2: "乙说法", 3: "同样"}
    r = divergence(zh_a, zh_b, exclude_ids={1, 3})
    assert r["compared"] == 1 and r["differing"] == 1 and r["rate"] == 1.0


def test_divergence_only_counts_ids_present_in_both():
    zh_a = {1: "甲", 2: "甲二"}
    zh_b = {1: "乙"}
    r = divergence(zh_a, zh_b, exclude_ids=set())
    assert r["compared"] == 1


def test_blind_pairs_alternate_lane_positions_by_id_parity():
    """位置锚定消除：奇数 id 甲=A，偶数 id 甲=B。"""
    ledger = {1: "原文一", 2: "原文二"}
    zh_a, zh_b = {1: "A译一", 2: "A译二"}, {1: "B译一", 2: "B译二"}
    pairs, key = blind_pairs([1, 2], zh_a, zh_b, ledger, "opus", "fable")
    p1 = next(p for p in pairs if p["id"] == 1)
    p2 = next(p for p in pairs if p["id"] == 2)
    assert p1["甲"] == "A译一" and p1["乙"] == "B译一"
    assert p2["甲"] == "B译二" and p2["乙"] == "A译二"
    assert key == {"odd_id_甲": "opus", "even_id_甲": "fable"}


def test_blind_pairs_carry_source_text():
    ledger = {1: "原文一"}
    pairs, _ = blind_pairs([1], {1: "a"}, {1: "b"}, ledger, "x", "y")
    assert pairs[0]["jp"] == "原文一"


def test_stratified_sample_covers_every_unit_kind():
    timeline = [
        {"type": "unit", "unit_kind": "scene", "ids": [1, 2, 3]},
        {"type": "unit", "unit_kind": "card", "ids": [4, 5]},
        {"type": "marker", "text": "x"},
        {"type": "unit", "unit_kind": "script", "ids": [6]},
    ]
    s = stratified_sample([1, 2, 3, 4, 5, 6], timeline, per_kind=2)
    assert set(s) == {1, 2, 4, 5, 6}, "每类取前 2 个，script 只有 1 个也要取到"


def test_main_writes_summary_and_blind_material(tmp_path, monkeypatch):
    import tools.compare_lanes as cl
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir()
    (repo / "data" / "ledger.jsonl").write_text("\n".join(
        json.dumps({"id": i, "jp": f"原文{i}", "chapter": "s0f", "kind": "narrative",
                    "file": "f", "func": "g", "voice": "NONVOICE", "literal": True},
                   ensure_ascii=False) for i in (1, 2, 3)), encoding="utf-8")
    (repo / "data" / "timeline.jsonl").write_text(json.dumps(
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "f", "state": None,
         "title": "一", "ids": [1, 2, 3]}, ensure_ascii=False), encoding="utf-8")
    (repo / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n  items:\n    - {id: 1, jp: 原文1, zh: 定译一, recall: x}\n",
        encoding="utf-8")
    for lane, zh in (("opus", "甲译"), ("fable", "乙译")):
        d = tmp_path / "lanes" / lane / "data"
        d.mkdir(parents=True)
        d.joinpath("forward.jsonl").write_text("\n".join(
            json.dumps({"id": i, "zh": ("定译一" if i == 1 else f"{zh}{i}"),
                        "batch": 1, "backend": "cc", "model": "m", "ctx": "c",
                        "glossary_v": 6, "ts": "t"}, ensure_ascii=False)
            for i in (1, 2, 3)), encoding="utf-8")
    monkeypatch.setattr(cl, "REPO", repo)
    out = tmp_path / "compare"
    assert main(["--lane-a", str(tmp_path / "lanes" / "opus"),
                 "--lane-b", str(tmp_path / "lanes" / "fable"),
                 "--out", str(out)]) == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["anchor"]["opus"]["verbatim"] == 1
    assert summary["divergence"]["compared"] == 2, "锚点 id 1 必须被排除"
    assert (out / "blind.md").exists()
    key = json.loads((out / "blind-key.json").read_text(encoding="utf-8"))
    assert key["odd_id_甲"] == "opus"
