"""召回查询工具：术语升版后，找旧版本的相关行做补丁。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, WORK, read_jsonl, write_jsonl


def find(term, glossary_v, data=None):
    """找 forward 中 glossary_v < K 且原文含 term 的行（id、旧译、章别）"""
    data = Path(data or DATA)

    # 优雅处理缺失的 forward.jsonl
    fwd_path = data / "forward.jsonl"
    if not fwd_path.exists():
        return []

    ledger_path = data / "ledger.jsonl"
    if not ledger_path.exists():
        return []

    # 构建 ledger 索引：id -> ledger row
    ledger_by_id = {}
    for row in read_jsonl(ledger_path):
        ledger_by_id[row["id"]] = row

    # 查询
    hits = []
    for row in read_jsonl(fwd_path):
        # glossary_v 旧版本（小于指定的 K）
        if row["glossary_v"] >= glossary_v:
            continue

        # 对应的原文行
        ledger_row = ledger_by_id.get(row["id"])
        if not ledger_row:
            continue

        # 原文包含术语
        if term not in ledger_row["jp"]:
            continue

        # 命中
        hits.append({
            "id": row["id"],
            "zh": row["zh"],
            "chapter": ledger_row["chapter"]
        })

    return hits


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--glossary-v", type=int, required=True)
    ap.add_argument("--term", required=True)
    ap.add_argument("--data-dir", type=Path)
    ap.add_argument("--emit-batch", action="store_true")
    args = ap.parse_args(argv)

    hits = find(term=args.term, glossary_v=args.glossary_v, data=args.data_dir)

    if args.emit_batch:
        work = Path(WORK)
        recall_dir = work / "recall"
        recall_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(recall_dir / f"{args.term}.jsonl", hits)

    # 列出命中（简单格式）
    for hit in hits:
        print(f"id={hit['id']} zh={hit['zh']} chapter={hit['chapter']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
