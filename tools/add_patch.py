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
from tools.pipelib import DATA, REPO, append_jsonl, read_jsonl


def existing_patches(id, data) -> list:
    """该 id 已有的 patch（按文件顺序）。**用 JSON 解析，不用 grep。**

    历史教训：交接件里曾把「是否已被裁过」的固定动作写成
    `grep '"id":<N>,' patches.jsonl`。实测 146 条里有 **17 条是带空格体**
    （`{"id": 10662,`），grep 对它们**恒返回 0**——据此判「没被裁过」再补一条
    patch，就是 SEG-5 那次 id 1600 误覆盖已裁定稿的同一失败模式。
    ⚠ 顺带更正两处流传的错误归因：①带空格体**不是 `add_patch.py` 写的**，它一直走
    `pipelib.dumps`（紧凑体）；②那 17 条**不是「最近裁决的」而是最老的**
    （全部 glossary_v 8–9），v10 起全部紧凑。归因错了会导致去「统一分隔符」
    这种什么也修不到的改法——**正确的修法是别用文本匹配判 JSON**。
    """
    p = Path(data) / "patches.jsonl"
    if not p.exists():
        return []
    return [r for r in read_jsonl(p) if r["id"] == id]


def add(id, zh, reason, glossary_v, ts=None, data=None, *, announce=True) -> list:
    """追加一条修订到 patches.jsonl；返回**追加之前**该 id 已有的 patch 列表。

    追加前把既有 patch 播报出来（`announce=True`），是为了把「先 grep 查一下有没有
    被裁过」这条**靠记忆的纪律**换成工具自己出声。重复 patch 本身是合法的（同一行
    可以被多轮裁决层层修订），所以这里**不拒绝执行**——要防的是「以为没被裁过」。
    """
    data = Path(data or DATA)
    prior = existing_patches(id, data)
    if prior and announce:
        last = prior[-1]
        print(f"⚠ id {id} 已有 {len(prior)} 条 patch，本次将成为第 {len(prior) + 1} 条"
              f"（覆盖它们）。最近一条：reason={last.get('reason')} "
              f"glossary_v={last.get('glossary_v')} ts={last.get('ts')}\n"
              f"   现行译文：{last.get('zh', '')[:60]}\n"
              f"   **若你以为这一行没被裁过，请先停下来核对**——文本匹配式的查重"
              f"（grep）对 17 条带空格体的老 patch 恒返回 0，不可信。", file=sys.stderr)
    ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = {"id": id, "zh": zh, "reason": reason, "glossary_v": glossary_v, "ts": ts}
    append_jsonl(data / "patches.jsonl", [row])
    return prior


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
    ap.add_argument("--zh")
    ap.add_argument("--reason", choices=["review", "recall", "polish"])
    ap.add_argument("--glossary-v", type=int)
    ap.add_argument("--has-patch", action="store_true",
                    help="只查该 id 已有的 patch 并退出，不写任何东西。"
                         "退出码 0＝有、1＝没有。**判「是否已被裁过」用这个，不要 grep**")
    ap.add_argument("--ts")
    ap.add_argument("--data-dir", type=Path,
                    help="写入哪个 data/ 目录；车道模式下缺省即拒绝执行")
    args = ap.parse_args(argv)
    data = resolve_data_dir(args.data_dir)
    if args.has_patch:
        prior = existing_patches(args.id, data)
        if not prior:
            print(f"id {args.id}：没有 patch（{data / 'patches.jsonl'}）")
            return 1
        print(f"id {args.id}：已有 {len(prior)} 条 patch")
        for r in prior:
            print(f"  reason={r.get('reason')} glossary_v={r.get('glossary_v')} "
                  f"ts={r.get('ts')}\n    {r.get('zh', '')}")
        return 0
    if not (args.zh and args.reason and args.glossary_v is not None):
        raise SystemExit("追加 patch 需同时给 --zh/--reason/--glossary-v"
                         "（只想查询请用 --has-patch）")
    add(args.id, args.zh, args.reason, args.glossary_v, ts=args.ts, data=data)
    print(f"已追加 1 条 patch（id={args.id}）→ {data / 'patches.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
