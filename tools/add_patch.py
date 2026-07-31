"""patch 追加工具：单条修订 → patches.jsonl (append-only)。"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, append_jsonl


def add(id, zh, reason, glossary_v, ts=None, data=None) -> None:
    """追加一条修订到 patches.jsonl"""
    data = Path(data or DATA)
    ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = {"id": id, "zh": zh, "reason": reason, "glossary_v": glossary_v, "ts": ts}
    append_jsonl(data / "patches.jsonl", [row])


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--zh", required=True)
    ap.add_argument("--reason", choices=["review", "recall", "polish"], required=True)
    ap.add_argument("--glossary-v", type=int, required=True)
    ap.add_argument("--ts")
    ap.add_argument("--data-dir", type=Path)
    args = ap.parse_args(argv)
    add(args.id, args.zh, args.reason, args.glossary_v, ts=args.ts, data=args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
