"""校验通过的批次草稿 → 追加 forward.jsonl（append-only 正向线）。"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import WORK, DATA, read_jsonl, append_jsonl, sha256_file


def run(batch, backend, model, ctx, glossary_v, ts=None, work=None, data=None) -> int:
    work, data = Path(work or WORK), Path(data or DATA)
    draft_path = work / "out" / f"batch_{batch}.draft.jsonl"
    pass_path = work / "out" / f"batch_{batch}.pass.json"
    if not pass_path.exists():
        print(f"batch_{batch}: 无 pass 标记，先跑 check_batch", file=sys.stderr)
        return 2
    marker = json.loads(pass_path.read_text(encoding="utf-8"))
    if marker["sha256"] != sha256_file(draft_path):
        print(f"batch_{batch}: draft 在校验后被改动（哈希不符）", file=sys.stderr)
        return 3
    fwd_path = data / "forward.jsonl"
    if fwd_path.exists() and any(
            r["batch"] == batch for r in read_jsonl(fwd_path)):
        print(f"batch_{batch}: 已在正向线，拒绝重复入库", file=sys.stderr)
        return 4
    ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [{"id": r["id"], "zh": r["zh"], "batch": batch, "backend": backend,
             "model": model, "ctx": ctx, "glossary_v": glossary_v, "ts": ts}
            for r in read_jsonl(draft_path)]
    append_jsonl(fwd_path, rows)
    print(f"batch_{batch}: +{len(rows)} 行入线")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--glossary-v", type=int, required=True)
    ap.add_argument("--ts")
    args = ap.parse_args(argv)
    return run(args.batch, args.backend, args.model, args.ctx,
               args.glossary_v, ts=args.ts)


if __name__ == "__main__":
    raise SystemExit(main())
