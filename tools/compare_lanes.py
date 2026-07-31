"""双车道对照材料生成：分层统计 + 盲评并排 + 卡面回译自检素材。

分层的要点（spec §6.1）：锚点覆盖行规定逐字沿用骨架定稿，两模型应当输出同一
字符串——把它们混进"模型区分度"统计会制造"两模型很接近"的假阳性，故必须单列
并从区分度里剔除。盲评的要点：甲/乙 与车道的对应按 id 奇偶交替，消除"总是排在
左边的那个更好"的位置锚定。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl


def anchor_ids(anchors_path) -> dict:
    """锚点表 → {id: zh}。"""
    import yaml
    groups = yaml.safe_load(Path(anchors_path).read_text(encoding="utf-8")) or []
    return {it["id"]: it["zh"] for g in groups for it in g["items"]}


def anchor_compliance(forward_rows, anchors) -> dict:
    zh = {r["id"]: r["zh"] for r in forward_rows}
    present = [i for i in anchors if i in zh]
    bad = [i for i in present if zh[i] != anchors[i]]
    return {"total": len(present), "verbatim": len(present) - len(bad),
            "rate": (len(present) - len(bad)) / len(present) if present else 0.0,
            "violations": sorted(bad)}


def divergence(zh_a, zh_b, exclude_ids) -> dict:
    common = [i for i in zh_a if i in zh_b and i not in exclude_ids]
    diff = [i for i in common if zh_a[i] != zh_b[i]]
    return {"compared": len(common), "differing": len(diff),
            "rate": len(diff) / len(common) if common else 0.0,
            "ids": sorted(diff)}


def blind_pairs(ids, zh_a, zh_b, ledger, lane_a, lane_b):
    """并排材料 + 揭示 key。甲/乙 与车道的对应按 id 奇偶交替。"""
    pairs = []
    for i in sorted(ids):
        if i not in zh_a or i not in zh_b:
            continue
        first, second = (zh_a[i], zh_b[i]) if i % 2 == 1 else (zh_b[i], zh_a[i])
        pairs.append({"id": i, "jp": ledger.get(i, ""), "甲": first, "乙": second})
    return pairs, {"odd_id_甲": lane_a, "even_id_甲": lane_b}


def stratified_sample(ids, timeline, per_kind=20):
    """按 timeline 单元类型分层，每类按 id 升序取前 per_kind 个。
    段内单元构成极不均衡（场景/卡面/整脚本…），不分层会过采样机械性最强、
    模型差异最小的那一类。"""
    id_kind = {}
    for row in timeline:
        if row.get("type") != "unit":
            continue
        for i in row.get("ids", []):
            id_kind.setdefault(i, row["unit_kind"])
    buckets = {}
    for i in sorted(ids):
        buckets.setdefault(id_kind.get(i, "unknown"), []).append(i)
    out = []
    for kind in sorted(buckets):
        out.extend(buckets[kind][:per_kind])
    return sorted(out)


def _render_blind(pairs) -> str:
    lines = ["# 盲评并排材料",
             "",
             "> 甲/乙 与车道的对应关系已隐去（见 blind-key.json）。**打完分再看 key。**",
             "> 三栏评分：中文可读性 / 术语与口调一致性 / 全知纪律（剧透与提前消歧）。",
             ""]
    for p in pairs:
        lines += [f"## id {p['id']}", "", f"- 原文：{p['jp']}", f"- 甲：{p['甲']}",
                  f"- 乙：{p['乙']}", ""]
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane-a", required=True)
    ap.add_argument("--lane-b", required=True)
    ap.add_argument("--per-kind", type=int, default=20)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    repo = Path(REPO)
    la, lb = Path(a.lane_a), Path(a.lane_b)
    out = Path(a.out) if a.out else repo / "work" / "compare"
    out.mkdir(parents=True, exist_ok=True)

    fa = read_jsonl(la / "data" / "forward.jsonl")
    fb = read_jsonl(lb / "data" / "forward.jsonl")
    zh_a = {r["id"]: r["zh"] for r in fa}
    zh_b = {r["id"]: r["zh"] for r in fb}
    anchors = anchor_ids(repo / "skeleton" / "anchors.yaml")
    ledger = {r["id"]: r["jp"] for r in read_jsonl(repo / "data" / "ledger.jsonl")}
    timeline = read_jsonl(repo / "data" / "timeline.jsonl")

    summary = {
        "anchor": {la.name: anchor_compliance(fa, anchors),
                   lb.name: anchor_compliance(fb, anchors)},
        "divergence": divergence(zh_a, zh_b, exclude_ids=set(anchors)),
    }
    (out / "summary.json").write_text(dumps(summary), encoding="utf-8")

    sample = stratified_sample(
        [i for i in zh_a if i in zh_b and i not in anchors], timeline, a.per_kind)
    pairs, key = blind_pairs(sample, zh_a, zh_b, ledger, la.name, lb.name)
    (out / "blind.md").write_text(_render_blind(pairs), encoding="utf-8")
    (out / "blind-key.json").write_text(dumps(key), encoding="utf-8")
    print(f"{out}: 锚点遵从 {la.name}={summary['anchor'][la.name]['rate']:.3f} "
          f"{lb.name}={summary['anchor'][lb.name]['rate']:.3f}；"
          f"区分度样本 {summary['divergence']['compared']} 行、"
          f"分歧率 {summary['divergence']['rate']:.3f}；盲评 {len(pairs)} 组")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
