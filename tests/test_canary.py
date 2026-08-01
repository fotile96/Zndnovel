"""canary：同一车道数据上重算校验判定并成对比对——工具升级的回归闸（P3 spec §3）。"""
import json
from pathlib import Path

from tools.canary import batch_verdicts, diff_verdicts, _draft_from_forward


def _mk_lane(tmp_path: Path) -> Path:
    lane = tmp_path / "lane"
    (lane / "data").mkdir(parents=True)
    (lane / "glossary").mkdir()
    (lane / "work" / "ctx" / "batch_1").mkdir(parents=True)
    (lane / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [10, 11], "chapter": "s1s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text("\n".join([
        json.dumps({"id": 10, "zh": "【直哉】「旧译」"}, ensure_ascii=False),
        json.dumps({"id": 10, "zh": "【直哉】「新译」"}, ensure_ascii=False),  # 重译：取末次
        json.dumps({"id": 11, "zh": "旁白行"}, ensure_ascii=False),
    ]), encoding="utf-8")
    (lane / "work" / "ctx" / "batch_1" / "source.jsonl").write_text("\n".join([
        json.dumps({"id": 10, "jp": "【直哉】「もとの文」"}, ensure_ascii=False),
        json.dumps({"id": 11, "jp": "地の文"}, ensure_ascii=False),
    ]), encoding="utf-8")
    (lane / "glossary" / "speakers.json").write_text(
        json.dumps({"直哉": "直哉"}, ensure_ascii=False), encoding="utf-8")
    (lane / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (lane / "glossary" / "glossary.v1.yaml").write_text(
        "version: 1\ncharacters: []\nterms: []\n", encoding="utf-8")
    return lane


def test_draft_takes_last_occurrence():
    fwd = [{"id": 10, "zh": "A"}, {"id": 10, "zh": "B"}]
    assert _draft_from_forward(fwd, [10]) == [{"id": 10, "zh": "B"}]


def test_batch_verdicts_structure(tmp_path):
    v = batch_verdicts(_mk_lane(tmp_path), [1])
    assert set(v) == {"1"}
    assert set(v["1"]) == {"check", "collapse"}
    assert v["1"]["check"]["hard"] == []          # 说话人对齐、无 hard


def test_diff_detects_change(tmp_path):
    lane = _mk_lane(tmp_path)
    a = batch_verdicts(lane, [1])
    b = json.loads(json.dumps(a))
    b["1"]["check"]["warn"].append({"id": 11, "rule": "W2", "msg": "x"})
    assert diff_verdicts(a, a) == []
    d = diff_verdicts(a, b)
    assert d and d[0].startswith("batch 1")
