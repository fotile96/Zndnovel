import json
import pytest
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
    """per_kind 上限内（card/script 两类)直接全取；scene 类 3>2 触发等距取样，
    新算法保证端点入选（id 最小=1、最大=3），不再是旧算法的"取前 N 个"。"""
    timeline = [
        {"type": "unit", "unit_kind": "scene", "ids": [1, 2, 3]},
        {"type": "unit", "unit_kind": "card", "ids": [4, 5]},
        {"type": "marker", "text": "x"},
        {"type": "unit", "unit_kind": "script", "ids": [6]},
    ]
    s = stratified_sample([1, 2, 3, 4, 5, 6], timeline, per_kind=2)
    assert set(s) == {1, 3, 4, 5, 6}, "scene 层必须同时含端点 1（首）与 3（尾）"


def test_stratified_sample_covers_head_and_tail_of_large_bucket():
    """I1 回归：旧算法 `buckets[kind][:per_kind]` 只取 id 升序最小的前 N 个——
    真实试点里最大批号（对应最晚批次）永远进不了盲评材料（终审实证：默认
    per_kind=20 出 100 行只覆盖 35 批中的 6 批、最大批号 29，batch 33–35
    压缩窗口生效后的数据在任何取值下都进不去）。新算法必须让每一层同时
    含有该层 id 最小和最大的行，不论 per_kind 取多小。"""
    ids = list(range(1, 1001))
    timeline = [{"type": "unit", "unit_kind": "scene", "ids": ids}]
    s = stratified_sample(ids, timeline, per_kind=20)
    assert 1 in s, "样本必须含首批对应的最小 id"
    assert 1000 in s, "样本必须含末批对应的最大 id"
    assert len(s) <= 20


ANCHORS_YAML = ("- chapter: global\n  items:\n    - {id: 1, jp: 原文1, zh: 定译一, "
                "recall: x}\n")


def _build_repo_and_lanes(tmp_path, *, lane_a_anchors=ANCHORS_YAML,
                          lane_b_anchors=ANCHORS_YAML):
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
    # 仓库根的 anchors.yaml 故意留空/不同——main() 现在必须从车道自己的冻结
    # 快照读锚点，而不是仓库当前状态（I4 修复）。留着这份文件只是确保测试若
    # 不小心退回旧代码路径（读 REPO）会明显失败，而不是意外读对。
    (repo / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n  items:\n    - {id: 1, jp: 原文1, zh: 仓库当前非冻结值, "
        "recall: x}\n", encoding="utf-8")
    lanes = {}
    for lane, zh, anchors_yaml in (("opus", "甲译", lane_a_anchors),
                                   ("fable", "乙译", lane_b_anchors)):
        lane_dir = tmp_path / "lanes" / lane
        d = lane_dir / "data"
        d.mkdir(parents=True)
        d.joinpath("forward.jsonl").write_text("\n".join(
            json.dumps({"id": i, "zh": ("定译一" if i == 1 else f"{zh}{i}"),
                        "batch": 1, "backend": "cc", "model": "m", "ctx": "c",
                        "glossary_v": 6, "ts": "t"}, ensure_ascii=False)
            for i in (1, 2, 3)), encoding="utf-8")
        (lane_dir / "skeleton").mkdir()
        (lane_dir / "skeleton" / "anchors.yaml").write_text(anchors_yaml,
                                                             encoding="utf-8")
        lanes[lane] = lane_dir
    return repo, lanes


def test_main_writes_summary_and_blind_material(tmp_path, monkeypatch):
    import tools.compare_lanes as cl
    repo, lanes = _build_repo_and_lanes(tmp_path)
    monkeypatch.setattr(cl, "REPO", repo)
    out = tmp_path / "compare"
    assert main(["--lane-a", str(lanes["opus"]),
                 "--lane-b", str(lanes["fable"]),
                 "--out", str(out)]) == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["anchor"]["opus"]["verbatim"] == 1
    assert summary["divergence"]["compared"] == 2, "锚点 id 1 必须被排除"
    assert (out / "blind.md").exists()
    key = json.loads((out / "blind-key.json").read_text(encoding="utf-8"))
    assert key["odd_id_甲"] == "opus"


def test_main_reads_anchors_from_lane_a_frozen_snapshot_not_repo(tmp_path, monkeypatch):
    """I4：anchors 必须从车道自己的冻结快照读，不是仓库当前状态——译者当时
    看到的是车道快照，按仓库当前值判遵从率会文不对题。仓库根的锚点值故意
    设成第三个值，若代码退回旧路径这条断言会失败。"""
    import tools.compare_lanes as cl
    repo, lanes = _build_repo_and_lanes(tmp_path)
    monkeypatch.setattr(cl, "REPO", repo)
    out = tmp_path / "compare"
    main(["--lane-a", str(lanes["opus"]), "--lane-b", str(lanes["fable"]),
          "--out", str(out)])
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    # forward id=1 的 zh 是 "定译一"，与车道冻结快照（ANCHORS_YAML）一致、
    # 与仓库当前值（"仓库当前非冻结值"）不同——verbatim=1 只有在按车道快照判
    # 才成立，按仓库当前值判会是 0。
    assert summary["anchor"]["opus"]["verbatim"] == 1


def test_main_refuses_when_lane_anchors_diverge(tmp_path, monkeypatch):
    """两条车道的锚点冻结快照若不同（例如分别在骨架修订前后 setup），遵从率
    对两车道就不是同一把尺子、不可比——main() 必须拒绝出对照材料并报错，
    而不是悄悄用其中一份继续算。"""
    import tools.compare_lanes as cl
    diverged = ("- chapter: global\n  items:\n    - {id: 1, jp: 原文1, "
                "zh: 车道B的不同定稿, recall: x}\n")
    repo, lanes = _build_repo_and_lanes(tmp_path, lane_b_anchors=diverged)
    monkeypatch.setattr(cl, "REPO", repo)
    out = tmp_path / "compare"
    with pytest.raises(SystemExit):
        main(["--lane-a", str(lanes["opus"]), "--lane-b", str(lanes["fable"]),
              "--out", str(out)])
    assert not (out / "summary.json").exists(), "拒绝时不该产出任何对照材料"
