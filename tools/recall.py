"""召回查询工具：术语升版后，找旧版本的相关行做补丁。"""
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, WORK, read_jsonl, write_jsonl


def safe_name(term: str) -> str:
    """术语名 → 安全文件名：非词字符折成 _，防止 term 里的 / 或 .. 把产物
    写到 work/recall/ 之外（write_jsonl 会自建父目录，不净化则可越界落盘）。
    常规术语（日文/中文/英数）全是词字符，文件名保持原样。"""
    name = re.sub(r"\W+", "_", term).strip("_")
    return name or hashlib.sha256(term.encode("utf-8")).hexdigest()[:16]


def find(term, glossary_v, data=None):
    """找**生效译文**的术语表版本 < K 且原文含 term 的行（id、生效译文 zh、
    章别）。

    "生效版本/生效译文"与 tools.resolve 的覆盖语义一致：forward 先铺、patches
    （若存在）后写覆盖，同 id 多条 patch 取最后一条（append-only）。一个 id
    只要被更高版本术语表 patch 过，就按 patch 的 glossary_v/zh 判断陈旧——不
    会因为首译版本旧而对更高的 K 反复召回；返回的 zh 同样是这份生效译文（有
    patch 取 patch 的，没有则取 forward 的），因为那才是拿来对照重译的对象。
    """
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

    # 生效译文：forward 先铺，patches（若存在）后写覆盖，同 id 多条取最后一条
    # ——与 resolve.resolve_map 同一份覆盖语义，这里各自维护一份（而非直接调用
    # resolve_map）是因为 resolve_map 只保留 zh，这里还需要与之配对的
    # glossary_v 一起覆盖，两者必须来自同一条（forward 或 patch）行，不能
    # 分别取「最新版本号」与「最新 zh」错配。
    effective = {}
    for row in read_jsonl(fwd_path):
        effective[row["id"]] = {"zh": row["zh"], "glossary_v": row["glossary_v"]}
    patches_path = data / "patches.jsonl"
    if patches_path.exists():
        for row in read_jsonl(patches_path):
            effective[row["id"]] = {"zh": row["zh"], "glossary_v": row["glossary_v"]}

    # 查询
    hits = []
    for id_, eff in effective.items():
        # glossary_v 旧版本（小于指定的 K）
        if eff["glossary_v"] >= glossary_v:
            continue

        # 对应的原文行
        ledger_row = ledger_by_id.get(id_)
        if not ledger_row:
            continue

        # 原文包含术语
        if term not in ledger_row["jp"]:
            continue

        # 命中
        hits.append({
            "id": id_,
            "zh": eff["zh"],
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
        write_jsonl(recall_dir / f"{safe_name(args.term)}.jsonl", hits)

    # 列出命中（简单格式）
    for hit in hits:
        print(f"id={hit['id']} zh={hit['zh']} chapter={hit['chapter']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
