"""陷阱批回验：对已入线批次用当前工具树重算 check_batch + detect_collapse 判定，
输出规范化 JSON（`dumps` 输出确定性来自固定的字典插入顺序，非 sort_keys）。工具升级流程
（P3 spec §3）：旧 tag worktree 与新 main 各跑一次 --out（同一车道数据），--diff 一致
才允许滚动生产 tag。draft 取 forward.jsonl 中每 id 的末次出现（＝入线原稿；patches 不
参与，判定对齐的是入线时刻）。"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import dumps, read_jsonl
from tools.check_batch import check
from tools.detect_collapse import _glossary_max, retained_names, scan


def _draft_from_forward(forward_rows, ids):
    m = {}
    for r in forward_rows:
        if r["id"] in ids:
            m[r["id"]] = r["zh"]
    return [{"id": i, "zh": m[i]} for i in ids if i in m]


def _ensure_ctx(lane_dir: Path, n: int, regen: bool) -> Path:
    src = lane_dir / "work" / "ctx" / f"batch_{n}" / "source.jsonl"
    if regen or not src.exists():
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "build_context.py"),
             "--batch", str(n), "--profile", "cc", "--repo", str(lane_dir)],
            check=True)
    return src


def batch_verdicts(lane_dir: Path, nums, regen_ctx: bool = False) -> dict:
    lane_dir = Path(lane_dir)
    fwd = read_jsonl(lane_dir / "data" / "forward.jsonl")
    speakers = json.loads(
        (lane_dir / "glossary" / "speakers.json").read_text(encoding="utf-8"))
    glossary = json.loads(
        (lane_dir / "glossary" / "active.json").read_text(encoding="utf-8"))
    names = retained_names(_glossary_max(lane_dir))
    out = {}
    for n in nums:
        source = read_jsonl(_ensure_ctx(lane_dir, n, regen_ctx))
        draft = _draft_from_forward(fwd, [r["id"] for r in source])
        out[str(n)] = {"check": check(source, draft, speakers, glossary),
                       "collapse": scan(source, draft, names)}
    return out


def diff_verdicts(old: dict, new: dict) -> list:
    msgs = []
    for k in sorted(set(old) | set(new), key=int):
        if old.get(k) != new.get(k):
            o, n = old.get(k, {}), new.get(k, {})
            msgs.append(
                f"batch {k}: hard {len(o.get('check', {}).get('hard', []))}"
                f"->{len(n.get('check', {}).get('hard', []))}, "
                f"warn {len(o.get('check', {}).get('warn', []))}"
                f"->{len(n.get('check', {}).get('warn', []))}, "
                f"collapse {len(o.get('collapse', []))}->{len(n.get('collapse', []))}")
    return msgs


def _parse_range(s: str):
    lo, hi = s.split("-")
    return list(range(int(lo), int(hi) + 1))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane-dir")
    ap.add_argument("--batches", help="闭区间，形如 1-35")
    ap.add_argument("--out")
    ap.add_argument("--regen-ctx", action="store_true",
                    help="强制重生 ctx（升级触及 build_context 时两边都要加）")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"))
    args = ap.parse_args(argv)
    if args.diff:
        old = json.loads(Path(args.diff[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(args.diff[1]).read_text(encoding="utf-8"))
        msgs = diff_verdicts(old, new)
        for m in msgs:
            print(m)
        print(f"canary diff: {'一致' if not msgs else f'{len(msgs)} 批有差异'}")
        return 1 if msgs else 0
    if not (args.lane_dir and args.batches and args.out):
        raise SystemExit("生成模式需 --lane-dir --batches --out；比对模式用 --diff OLD NEW")
    v = batch_verdicts(Path(args.lane_dir), _parse_range(args.batches), args.regen_ctx)
    Path(args.out).write_text(dumps(v), encoding="utf-8")
    print(f"canary: {len(v)} 批判定已写 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
