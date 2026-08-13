"""tools/polish_bench.py 的行为闸。

每条用例对应一个**评测口径上真会被搞错的点**，不是凑覆盖率。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_bench as pb


def _seg(tmp_path, rows, lane, *, prod_channels=()):
    """rows: [(id, jp, opus_zh)]；lane: {id: 现行译文}。"""
    root = tmp_path / "repo"
    d = root / "pilot" / "polish" / "segX"
    (d / "frozen").mkdir(parents=True)
    (d / "frozen" / "opus.jsonl").write_text(
        "\n".join(json.dumps({"id": i, "zh": z}, ensure_ascii=False) for i, _, z in rows) + "\n",
        encoding="utf-8")
    (d / "frozen" / "source.jsonl").write_text(
        "\n".join(json.dumps({"id": i, "jp": j}, ensure_ascii=False) for i, j, _ in rows) + "\n",
        encoding="utf-8")
    for c in prod_channels:                      # 只需存在即可（标 ※ 用）
        (d / f"candidates.{c}.jsonl").write_text("", encoding="utf-8")
    ld = root / "lane"
    ld.mkdir()
    (ld / "forward.jsonl").write_text(
        "\n".join(json.dumps({"id": i, "zh": z}, ensure_ascii=False) for i, z in lane.items()) + "\n",
        encoding="utf-8")
    return root, ld


def _ch(tmp_path, name, rows):
    p = tmp_path / f"{name}.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return str(p)


def test_precision_and_recall_use_the_final_lane_text_as_ground_truth(tmp_path):
    """需改行 = 车道现行 ≠ 冻结 opus。改对一条、改错一条、漏一条 → 50%/50%。"""
    root, ld = _seg(tmp_path, [(1, "あ", "甲"), (2, "い", "乙"), (3, "う", "丙")],
                    {1: "甲改", 2: "乙", 3: "丙改"})           # 需改 = {1,3}
    p = _ch(tmp_path, "t", [{"id": 1, "zh": "甲改"}, {"id": 2, "zh": "乙乱改"}, {"id": 3, "zh": "丙"}])
    r = pb.bench("segX", {"t": p}, lane_dir=ld, repo=root)["rows"][0]
    assert r["changed"] == 2 and r["hit"] == 1
    assert r["precision"] == 0.5 and r["recall"] == 0.5
    assert r["exact"] == 1          # 只有 id1 与定稿逐字相同


def test_in_segment_channels_are_flagged_because_they_have_circular_advantage(tmp_path):
    """参与过本段裁决的通道精确率天然虚高——必须能被识别出来，否则会被拿去横比。"""
    root, ld = _seg(tmp_path, [(1, "あ", "甲")], {1: "甲改"}, prod_channels=["fable-wf"])
    p1 = _ch(tmp_path, "a", [{"id": 1, "zh": "甲改"}])
    p2 = _ch(tmp_path, "b", [{"id": 1, "zh": "甲改"}])
    res = pb.bench("segX", {"fable-wf": p1, "外部通道": p2}, lane_dir=ld, repo=root)
    m = {r["channel"]: r["in_segment"] for r in res["rows"]}
    assert m["fable-wf"] is True and m["外部通道"] is False
    assert "※" in pb.render(res)


def test_missing_lines_are_counted_not_silently_ignored(tmp_path):
    """少交的行必须显性计数——否则一个只交一半的通道会显得精确率很高。"""
    root, ld = _seg(tmp_path, [(1, "あ", "甲"), (2, "い", "乙")], {1: "甲改", 2: "乙改"})
    p = _ch(tmp_path, "t", [{"id": 1, "zh": "甲改"}])
    r = pb.bench("segX", {"t": p}, lane_dir=ld, repo=root)["rows"][0]
    assert r["missing"] == 1 and r["lines"] == 1
    assert r["recall"] == 0.5      # 交了的那条命中，但分母仍是全部需改行


def test_gate_hits_counted_per_line(tmp_path):
    """丢【说话人】前缀这类硬伤要计数——一个「改得多」但满是硬伤的通道不该好看。"""
    root, ld = _seg(tmp_path, [(1, "【直哉】「あ」", "【直哉】「甲」")], {1: "【直哉】「甲」"})
    bad = _ch(tmp_path, "bad", [{"id": 1, "zh": "甲"}])       # 丢了【】
    ok = _ch(tmp_path, "ok", [{"id": 1, "zh": "【直哉】「甲」"}])
    res = pb.bench("segX", {"bad": bad, "ok": ok}, lane_dir=ld, repo=root)
    g = {r["channel"]: r["gate_hits"] for r in res["rows"]}
    assert g["bad"] == 1 and g["ok"] == 0


def test_zero_change_channel_gets_zero_recall_not_full_precision(tmp_path):
    """⚠ 一行不改的通道（antigravity 实测形态）：precision 是 None 而不是 100%。"""
    root, ld = _seg(tmp_path, [(1, "あ", "甲")], {1: "甲改"})
    p = _ch(tmp_path, "t", [{"id": 1, "zh": "甲"}])
    r = pb.bench("segX", {"t": p}, lane_dir=ld, repo=root)["rows"][0]
    assert r["changed"] == 0 and r["precision"] is None and r["recall"] == 0.0
    assert "—" in pb.render({"label": "segX", "batch_size": 1, "need": [1], "rows": [r]})
