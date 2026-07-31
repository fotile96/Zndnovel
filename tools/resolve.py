"""生效译文合并：resolve = 最新补丁 ∥ 正向线最后条。下游只准读本工具输出。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl, write_jsonl


def resolve_map(forward_rows, patch_rows) -> dict:
    m = {}
    for r in forward_rows:
        m[r["id"]] = r["zh"]
    for r in patch_rows:
        m[r["id"]] = r["zh"]
    return m


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-complete", action="store_true")
    args = ap.parse_args(argv)
    fwd = read_jsonl(DATA / "forward.jsonl") if (DATA / "forward.jsonl").exists() else []
    pat = read_jsonl(DATA / "patches.jsonl") if (DATA / "patches.jsonl").exists() else []
    m = resolve_map(fwd, pat)
    ledger_ids = [r["id"] for r in read_jsonl(DATA / "ledger.jsonl")]
    missing = [i for i in ledger_ids if i not in m]
    # extra 车道 id 是 str（如 "snr_x:5"），main/ambient 车道 id 是 int；混合后裸
    # sorted(m) 在 Python 3 下跨类型比较必抛 TypeError。key 按 (是否 str, 值本身)
    # 排：int 全部排在 str 之前，各自内部再按值排序，两边互不比较。
    write_jsonl(DATA / "final.jsonl",
                [{"id": i, "zh": m[i]} for i in sorted(m, key=lambda k: (isinstance(k, str), k))])
    print(f"final={len(m)}  missing={len(missing)}", file=sys.stderr)
    return 1 if (args.require_complete and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
