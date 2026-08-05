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
    # 此前本工具**只认 ZND_DATA 环境变量、连 --data-dir 都没有**，与 saturation.py /
    # check_batch.py 不一致；漏传就去读仓库根 data/——那里有 ledger.jsonl 却没有
    # forward.jsonl，于是算出一张「完全合理」的空表（final=0 missing=16749）并把空的
    # final.jsonl 写进仓库根。SEG-6 裁决会话实测踩到。补齐参数是一半，另一半见下面的告警。
    ap.add_argument("--data-dir", help="车道 data 目录；省略则用 ZND_DATA 环境变量，"
                                       "再省略则用仓库根 data/")
    args = ap.parse_args(argv)
    data = Path(args.data_dir) if args.data_dir else DATA
    fwd_p, pat_p = data / "forward.jsonl", data / "patches.jsonl"
    if not fwd_p.exists():
        # 「读不到译文线」与「这条线一条都没译」在数字上完全一样（都是 final=0），
        # 人眼分辨不出——这正是本项目反复吃亏的恒绿形态。故显式播报，并把最可能的
        # 原因写在第一句：仓库根 data/ 下**本来就没有** forward.jsonl，车道数据在别处。
        print(f"!! 告警：{fwd_p} 不存在——本次按「零条已译」计算。"
              f"若你以为这条线已经译过，那多半是**漏传 --data-dir / ZND_DATA**："
              f"车道译文线在 pilot/lanes/<lane>/data/，仓库根 data/ 下没有它。",
              file=sys.stderr)
    fwd = read_jsonl(fwd_p) if fwd_p.exists() else []
    pat = read_jsonl(pat_p) if pat_p.exists() else []
    m = resolve_map(fwd, pat)
    ledger_ids = [r["id"] for r in read_jsonl(data / "ledger.jsonl")]
    missing = [i for i in ledger_ids if i not in m]
    # extra 车道 id 是 str（如 "snr_x:5"），main/ambient 车道 id 是 int；混合后裸
    # sorted(m) 在 Python 3 下跨类型比较必抛 TypeError。key 按 (是否 str, 值本身)
    # 排：int 全部排在 str 之前，各自内部再按值排序，两边互不比较。
    write_jsonl(data / "final.jsonl",
                [{"id": i, "zh": m[i]} for i in sorted(m, key=lambda k: (isinstance(k, str), k))])
    print(f"final={len(m)}  missing={len(missing)}  (data-dir={data})", file=sys.stderr)
    return 1 if (args.require_complete and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
