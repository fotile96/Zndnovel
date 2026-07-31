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
    """按 timeline 单元类型分层，每类取 per_kind 个样本。

    每层内**等距取样并强制含端点**（id 最小与最大都各自入选），而不是旧版
    "按 id 升序取前 N 个"——旧版会让样本系统性地只覆盖段内靠前的少数批次，
    压缩窗口触发瞬间（段内最晚批次）永远进不了盲评材料，而"压缩触发瞬间是否
    丢信息"正是试点要回答的问题之一（终审 I1）。id 在本仓库里按脚本/时间轴
    出现顺序单调递增分配，故"该层内 id 最小/最大"即约等于"该层内最早/最晚
    批次"，等距+端点覆盖足以解决位置退化，不需要额外传入 batch 信息。
    """
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
        bucket = buckets[kind]
        n = len(bucket)
        if n <= per_kind or per_kind <= 1:
            out.extend(bucket[:per_kind] if per_kind >= 1 else [])
            continue
        step = (n - 1) / (per_kind - 1)
        idxs = sorted({round(i * step) for i in range(per_kind)})
        out.extend(bucket[i] for i in idxs)
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
    # 锚点必须按车道自己的冻结快照读，不是仓库当前状态：遵从率考的是"译者当时
    # 看到的锚点表，是否被逐字沿用"，仓库锚点若在试点期间被修订，用仓库当前
    # 值判会文不对题（终审 I4）。两条车道的冻结快照理应彼此相同（lane_setup
    # 的 verify() 有跨车道一致性检查）——这里独立复核一次：不同就直接拒绝
    # 出对照材料，因为分母不同、遵从率不可比。
    anchors_a = anchor_ids(la / "skeleton" / "anchors.yaml")
    anchors_b = anchor_ids(lb / "skeleton" / "anchors.yaml")
    if anchors_a != anchors_b:
        raise SystemExit(
            f"{la.name} 与 {lb.name} 两条车道的锚点冻结快照不同——遵从率对两"
            f"车道不是同一把尺子，不可比。拒绝生成对照材料，请先用 "
            f"tools/lane_setup.py --verify 排查漂移。")
    anchors = anchors_a
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
