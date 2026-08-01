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


def test_segments_labels_unique_and_ordered():
    segs, _ = _load()
    labels = [s["label"] for s in segs]
    assert len(labels) == len(set(labels))
    assert [s["seg"] for s in segs] == list(range(1, len(segs) + 1))
    assert all(s["review_focus"].strip() for s in segs)
