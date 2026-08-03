"""patch 追加工具：单条修订 → patches.jsonl (append-only)。

**车道模式下必须显式指定数据目录**（2026-08-02 生产事故）：控制器发了 4 条译文
回改补丁，命令零报错、退出码 0，但 `--data-dir` 缺省落到主仓 `data/`——那个文件
当时甚至不存在，是被这条命令连同目录一起凭空创建的，而生产车道用的是
`pilot/lanes/opus/data/patches.jsonl`。四条回改一条都没生效，全靠事后 `get_lines`
回读才发现；若当时只看「命令没报错」就走人，下一轮手记审计还会把它们重新报成
「未履行」。

本项目的原则是**静默写错比报错更坏**。故：仓库一旦处于车道模式（存在
`pilot/lanes/*/data/`），调用方又没有显式选定数据目录（既没给 `--data-dir`，
环境里也没有 `ZND_DATA`），CLI 一律**拒绝执行并列出候选路径**，不写任何文件。
非车道仓库（没有 `pilot/lanes/*/data/`）行为完全不变，缺省照旧落 `DATA`。

闸只设在 CLI（`main`）这一层：`add()` 作为库函数保持原样，程序化调用方（测试、
其他工具）本来就一直显式传 `data=`，不受影响。
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, REPO, append_jsonl


def add(id, zh, reason, glossary_v, ts=None, data=None) -> None:
    """追加一条修订到 patches.jsonl"""
    data = Path(data or DATA)
    ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = {"id": id, "zh": zh, "reason": reason, "glossary_v": glossary_v, "ts": ts}
    append_jsonl(data / "patches.jsonl", [row])


def lane_data_dirs(repo=None):
    """仓库里所有车道的数据目录（`pilot/lanes/*/data/`），按名字排序。

    判据取**目录存在**而非 `patches.jsonl` 存在：还没落过补丁的车道恰恰是最危险
    的一个——第一条补丁若写错地方，连「文件本来就在那儿」这种事后线索都没有。
    """
    root = Path(repo or REPO) / "pilot" / "lanes"
    if not root.is_dir():
        return []
    return sorted((p / "data" for p in root.iterdir() if (p / "data").is_dir()),
                  key=lambda p: p.parent.name)


def resolve_data_dir(explicit=None, *, repo=None, env=None):
    """决定本次写入的数据目录；车道模式下缺省即拒绝。

    返回 `Path`。踩闸时抛 `SystemExit`（退出码 2）——**在任何文件被创建之前**。
    `explicit` 为 `--data-dir` 的值；`ZND_DATA` 视同显式选定（生产命令形态就是
    `ZND_DATA=<lane>/data uv run python tools/...`，此时 `DATA` 已指向车道）。
    """
    if explicit:
        return Path(explicit)
    env = os.environ if env is None else env
    if env.get("ZND_DATA"):
        return Path(DATA)
    lanes = lane_data_dirs(repo)
    if not lanes:
        return Path(DATA)
    hint = "\n".join(f"    --data-dir {d}" for d in lanes)
    raise SystemExit(
        "拒绝执行：本仓库处于车道模式，但没有显式指定数据目录。\n"
        f"缺省会写进主仓 {DATA / 'patches.jsonl'}——生产补丁写在那里不会生效，\n"
        "而且不会有任何报错（2026-08-02 已经这样丢过 4 条回改）。\n"
        "请显式选择其一：\n"
        f"{hint}\n"
        f"  或用环境变量：ZND_DATA=<车道>/data uv run python tools/add_patch.py ...\n"
        f"  确实要写主仓请显式写出：--data-dir {DATA}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="追加一条译文修订到 patches.jsonl（append-only）",
        epilog="⚠ 车道模式（存在 pilot/lanes/*/data/）下必须显式给 --data-dir "
               "或设 ZND_DATA，否则拒绝执行——缺省写主仓 data/ 是静默失效。")
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--zh", required=True)
    ap.add_argument("--reason", choices=["review", "recall", "polish"], required=True)
    ap.add_argument("--glossary-v", type=int, required=True)
    ap.add_argument("--ts")
    ap.add_argument("--data-dir", type=Path,
                    help="写入哪个 data/ 目录；车道模式下缺省即拒绝执行")
    args = ap.parse_args(argv)
    data = resolve_data_dir(args.data_dir)
    add(args.id, args.zh, args.reason, args.glossary_v, ts=args.ts, data=data)
    print(f"已追加 1 条 patch（id={args.id}）→ {data / 'patches.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
