"""config/segments.yaml 与 data/batches.jsonl 的锁定测试：
分割必须恰好覆盖 b36–339 各一次，jp_chars 与实算一致，label/seg 唯一有序。"""
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


def _load():
    segs = yaml.safe_load((REPO / "config" / "segments.yaml").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in
            (REPO / "data" / "batches.jsonl").read_text(encoding="utf-8").splitlines() if l]
    return segs, {r["batch"]: r for r in rows}


def test_segments_partition_b36_to_339():
    segs, by = _load()
    covered = []
    for s in segs:
        lo, hi = s["batches"]
        covered.extend(range(lo, hi + 1))
    assert covered == list(range(36, 340))


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
