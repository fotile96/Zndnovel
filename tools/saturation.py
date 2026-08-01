"""词族饱和度：全书 ledger 中某日文词的出现次数里，已被译过批次覆盖的比例。
段末小裁决的证据闸门（P3 spec §2）：ratio >= gate 才允许裁决，否则聚类滚存。
读 DATA/ledger.jsonl（+ ledger_extra.jsonl 若存在）与 resolve_map（forward+patches）。"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl
from tools.resolve import resolve_map


def saturation(term: str, ledger_rows, done_ids) -> dict:
    total = covered = 0
    uncov = Counter()
    for r in ledger_rows:
        n = r.get("jp", "").count(term)
        if not n:
            continue
        total += n
        # 优先用 id，备选 key（ledger_extra.jsonl 格式）
        rid = r.get("id") if "id" in r else r.get("key")
        if rid is None:
            continue
        if rid in done_ids:
            covered += n
        else:
            uncov[r.get("chapter", "?")] += n
    return {"term": term, "total": total, "covered": covered,
            "ratio": covered / total if total else None,
            "uncovered_by_chapter": dict(uncov)}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--term", action="append", default=[])
    ap.add_argument("--terms-file", help="每行一个日文词，# 开头为注释")
    ap.add_argument("--data-dir", default=None,
                    help="覆盖 DATA（默认 ZND_DATA 或仓库根 data/）")
    ap.add_argument("--gate", type=float, default=0.8)
    args = ap.parse_args(argv)
    data = Path(args.data_dir) if args.data_dir else DATA
    terms = list(args.term)
    if args.terms_file:
        for line in Path(args.terms_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    if not terms:
        raise SystemExit("至少给一个 --term 或 --terms-file")
    ledger = read_jsonl(data / "ledger.jsonl")
    extra = data / "ledger_extra.jsonl"
    if extra.exists():
        ledger += read_jsonl(extra)
    # 「已入线译文」为空是本工具唯一的失败开方向：漏传 --data-dir 时 DATA 落到
    # 仓库根 data/（那里没有车道 forward.jsonl），输出一张全列 0.000/「滚存」的
    # 完全合理的表——闸门失效却毫无痕迹（终审 I2；runbook 里那条命令还是折行
    # 两行、极易漏抄第二行）。故：表头前自述统计口径，forward 缺失时醒目告警。
    fwd_path, pat_path = data / "forward.jsonl", data / "patches.jsonl"
    missing_forward = not fwd_path.exists()
    fwd = read_jsonl(fwd_path) if not missing_forward else []
    pat = read_jsonl(pat_path) if pat_path.exists() else []
    done = set(resolve_map(fwd, pat))
    rows = [saturation(t, ledger, done) for t in terms]
    rows.sort(key=lambda r: (r["ratio"] is None, r["ratio"] if r["ratio"] is not None else 0))
    print(f"done={len(done)} 条已入线译文（data-dir={data}）")
    if missing_forward:
        print(f"!! 告警：{fwd_path} 不存在——本次按「零条已译」计算，全部词族必然"
              f"判为「滚存」，闸门等于失效。是否漏传 --data-dir？"
              f"（车道数据在 pilot/lanes/<lane>/data）")
    print("| 词 | 出现 | 已覆盖 | 饱和度 | 判定 | 未覆盖分布 |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if r["ratio"] is None:
            verdict, ratio_s = "无出现", "-"
        elif r["ratio"] >= args.gate:
            verdict, ratio_s = "可裁决", f"{r['ratio']:.3f}"
        else:
            verdict, ratio_s = "滚存", f"{r['ratio']:.3f}"
        dist = " ".join(f"{c}:{n}" for c, n in
                        sorted(r["uncovered_by_chapter"].items())) or "-"
        print(f"| {r['term']} | {r['total']} | {r['covered']} | {ratio_s} | {verdict} | {dist} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
