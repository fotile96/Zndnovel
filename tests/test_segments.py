"""config/segments.yaml 与 data/batches.jsonl 的锁定测试：
分割必须恰好覆盖 b1–339 各一次（2026-08-07 补 seg1-s0-s1 覆盖此前遗漏的
b1–35 之后，覆盖范围从 b36–339 扩到 b1–339），jp_chars 与实算一致，
label/seg 唯一有序。"""
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def _load():
    segs = yaml.safe_load((REPO / "config" / "segments.yaml").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in
            (REPO / "data" / "batches.jsonl").read_text(encoding="utf-8").splitlines() if l]
    return segs, {r["batch"]: r for r in rows}


def test_segments_partition_b1_to_339():
    segs, by = _load()
    covered = []
    for s in segs:
        lo, hi = s["batches"]
        covered.extend(range(lo, hi + 1))
    assert covered == list(range(1, 340))


def test_segments_jp_chars_match_batches():
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        assert s["jp_chars"] == sum(by[b]["jp_chars"] for b in range(lo, hi + 1)), s["label"]


def test_each_segment_covers_exactly_one_lane():
    """终审 I4：`gen_plan.select()` 只按单一 lane 过滤——一个段若横跨两个 lane，
    生成计划时必然静默漏掉另一条 lane 的批次（原 SEG-8 = b174–339 里 b339 是
    ambient、其余是 extra，`--lane extra` 产出 165 批、漏 b339）。"""
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        lanes = {by[b]["lane"] for b in range(lo, hi + 1)}
        assert len(lanes) == 1, f"{s['label']} 横跨 lane {sorted(lanes)}"


def test_segments_chapters_match_actual_chapters():
    """终审 M5：chapters 是用户抽读时的范围认知来源，必须等于该段实算章别集合
    （原表全段漏 crd、SEG-8 直接是空列表）。"""
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        actual = {by[b]["chapter"] for b in range(lo, hi + 1)}
        assert len(s["chapters"]) == len(set(s["chapters"])), f"{s['label']} chapters 有重复"
        assert set(s["chapters"]) == actual, (
            f"{s['label']} chapters 与实算不符：多 {sorted(set(s['chapters']) - actual)}"
            f" 缺 {sorted(actual - set(s['chapters']))}")


def test_segments_labels_unique_and_ordered():
    segs, _ = _load()
    labels = [s["label"] for s in segs]
    assert len(labels) == len(set(labels))
    assert [s["seg"] for s in segs] == list(range(1, len(segs) + 1))
    assert all(s["review_focus"].strip() for s in segs)


def test_segments_lane_field_matches_batches():
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        lanes = {by[b]["lane"] for b in range(lo, hi + 1)}
        assert lanes == {s["lane"]}, s["label"]


def test_seg1_s0_s1_covers_b1_to_35_prologue_and_chapter1():
    """显式钉死新增段本身（2026-08-07 P4 seg2-prep）——不是只靠上面几条通用
    循环测试"顺带"覆盖它：b1–35 是 P2 试点批次遗留、P3 建段表时"只切余下
    304 批"而从未纳入 config/segments.yaml 的开头整块（序章 + 第1章 + 相关
    卡片剧情），此前任何一份检查段计划都不包含它。这条测试独立锁定其身份
    （label/seg 编号/批号区间/实算 jp_chars），防止未来有人"顺手"把它从
    段表里删掉或改错编号却让上面的通用分区/唯一性测试碰巧继续通过
    （比如误删这一段、同时把 test_segments_partition_b1_to_339 的下界也
    错改回 36——那种双重误改才会被这条测试之外的机制放过，故这条测试只
    钉一半：真正的"分区不能有洞"仍然靠 partition 测试兜底，这条测试钉的
    是"这一段的身份没被张冠李戴"）。"""
    segs, by = _load()
    hit = next((s for s in segs if s["label"] == "seg1-s0-s1"), None)
    assert hit is not None, "config/segments.yaml 里找不到 label=seg1-s0-s1"
    assert hit["seg"] == 1
    assert hit["batches"] == [1, 35]
    assert hit["lane"] == "main"
    assert hit["jp_chars"] == sum(by[b]["jp_chars"] for b in range(1, 36))
    assert hit["jp_chars"] == 116282
    actual_chapters = {by[b]["chapter"] for b in range(1, 36)}
    assert set(hit["chapters"]) == actual_chapters
    assert actual_chapters == {"s0f", "crd", "s1s", "sys", "s1f", "s2s"}
