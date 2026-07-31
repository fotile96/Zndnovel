"""章翻译执行计划生成器：data/batches.jsonl 里选中的批次 → 可被
superpowers:executing-plans 直接执行的 docs/superpowers/plans/translate-<label>.md。

render() 是纯字符串模板函数（不碰文件系统）；select() 负责从全量批次里挑出
本次要生成计划的子集（按 lane + chapter 或 lane + 连续批号段）；main() 负责
读 batches.jsonl、解析 CLI、把 render() 的结果写盘。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, DATA, read_jsonl
from tools.build_context import glossary_version

# render() 的 glossary_v 参数默认值/测试兜底。真实运行由 main() 通过
# build_context.glossary_version() 动态扫描 glossary/ 目录求得，不再消费这个
# 常量——曾经两处各自维护一个真相源，计划文本会把这里的硬编码盖进 append-only
# 的 forward 行（Minor 修复）。
GLOSSARY_V = 6


def _paths(lane_cfg):
    """把计划文本里的全部路径按车道根改写。lane_cfg 为 None 时返回仓库相对路径，
    输出与车道感知改造前逐字一致（回归闸 test_no_lane_cfg_output_is_byte_identical
    _to_repo_mode 锁死这一点）。"""
    if lane_cfg is None:
        return {"ctx": "work/ctx", "out": "work/out", "forward": "data/forward.jsonl",
                "notes": "data/notes", "repo_arg": "", "env": ""}
    d = lane_cfg["lane_dir"]
    return {"ctx": f"{d}/work/ctx", "out": f"{d}/work/out",
            "forward": f"{d}/data/forward.jsonl", "notes": f"{d}/data/notes",
            "repo_arg": f" --repo {d}",
            "env": f"ZND_WORK={d}/work ZND_DATA={d}/data "}


def _lane_block(lane_cfg):
    if lane_cfg is None:
        return ""
    return f"""

## 车道配置（本计划专属，派发时逐字遵守）

| 项 | 值 |
|---|---|
| lane | {lane_cfg["lane"]} |
| lane_dir | {lane_cfg["lane_dir"]} |
| model | {lane_cfg["model"]} |
| effort | {lane_cfg["effort"]} |
| append_model_id | {lane_cfg["append_model_id"]} |

- **派发只能走 Workflow 的 `agent(prompt, {{"model": "{lane_cfg["model"]}", "effort": "{lane_cfg["effort"]}"}})`**——`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档，使该批次失去可比性。任何一次重试都必须重新读取本表。
- **隔离纪律**：禁止读取、列出 `work/lanes/` 下除 `{lane_cfg["lane"]}` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `{lane_cfg["lane_dir"]}/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：试点期间提案只追加进 `{lane_cfg["lane_dir"]}/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `{lane_cfg["lane_dir"]}/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。"""


def select(batches, *, lane, chapter=None, batch_range=None):
    """按 lane 过滤，再按 chapter 或 batch_range（闭区间 (lo, hi)）过滤，
    返回按 batch 升序的列表。两个过滤条件可同时为 None（取该 lane 全部）。"""
    sel = [b for b in batches if b["lane"] == lane]
    if chapter is not None:
        sel = [b for b in sel if b["chapter"] == chapter]
    if batch_range is not None:
        lo, hi = batch_range
        sel = [b for b in sel if lo <= b["batch"] <= hi]
    return sorted(sel, key=lambda b: b["batch"])


def _header(label, lane, every, count, glossary_v, lane_cfg):
    p = _paths(lane_cfg)
    return f"""# {label} 章（{lane} 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 {label} 章（lane={lane}）的全部 {count} 个批次逐批译出、校验、入库到 `{p["forward"]}`，章末完成骨架一致性自检与人工评审 gate。

**Architecture:** 每个批次一个任务，走「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → append_forward 入库并提交」四步流水线（P1b 已建成，签名见下）；每 {every} 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；章末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- 运行 `uv run python tools/<x>.py`；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: {label} 批次N 译文入线`，main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `{p["notes"]}/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 试点期固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v {glossary_v}`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（Step 4）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。
{_lane_block(lane_cfg)}
---"""


def _batch_task(tnum, batch, baseline, glossary_v, p):
    n, ch, ids = batch["batch"], batch["chapter"], batch["ids"]
    return f"""### Task {tnum}: {ch} 批次 {n} 译文入库（{len(ids)} 条，约 {batch["jp_chars"]} 日文字）

**Files:**
- Produces: `{p["ctx"]}/batch_{n}/{{context.md,source.jsonl,manifest.json}}`（Step 1）、`{p["out"]}/batch_{n}.draft.jsonl`（Step 2 产出、Step 3 校验）、`{p["forward"]}` 追加本批 {len(ids)} 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 {n} 批（`lane={batch["lane"]} chapter={ch}`，{len(ids)} 条 id）
- Produces: `{p["forward"]}` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch {n} --profile cc --baseline {baseline}{p["repo_arg"]}`
Expected: 生成 `{p["ctx"]}/batch_{n}/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 {n}，并按本计划头部「车道配置」注入车道根），产出 `{p["out"]}/batch_{n}.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `{p["env"]}uv run python tools/check_batch.py --batch {n}`
Expected: `batch_{n}: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `{p["out"]}/batch_{n}.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`{p["env"]}uv run python tools/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v {glossary_v}`

```bash
git add {p["forward"]}
git commit -m "data: {ch} 批次{n} 译文入线"
```"""


def _checkpoint_task(tnum, first, last, chapter, p):
    return f"""### Task {tnum}: CHECKPOINT——批次 {first}–{last} 术语提案裁决 + 抽查

到这里已完成 {chapter} 章批次 {first}–{last} 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `{p["notes"]}/{chapter}.md`（若这几批翻译中子代理追加过内容——文件不存在说明本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 {first}–{last} 已入库的译文里随机抽 2–3 条，对照对应 `{p["ctx"]}/batch_*/source.jsonl` 的原文与 `{p["forward"]}` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `{p["forward"]}`——它是 append-only 正向线）。"""


def _final_task(tnum, chapter, lane, first, last, count, p):
    return f"""### Task {tnum}: 章末——梗概回译自检 + 人工评审 gate

{chapter} 章 {lane} 车道全部 {count} 个批次（{first}–{last}）已入库 `{p["forward"]}`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本章对应的章节梗概卡（`skeleton/cards.zh/`，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本章刚入库的 `{p["forward"]}` 正文译文：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否和 `skeleton/anchors.yaml` 一致，尤其检查有没有在本章尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。

- [ ] **Step 2: 人工评审 gate**

把本章相关的 `data:` commit（`git log --oneline` 过滤 `{chapter}`）交给人工复核。**不要自动放行**——人工确认无误后本章翻译才算完成，之后才能对下一章跑 `tools/gen_plan.py` 生成新计划。"""


def render(sel, label, lane, every=5, baseline="none", glossary_v=GLOSSARY_V,
           lane_cfg=None) -> str:
    p = _paths(lane_cfg)
    parts = [_header(label, lane, every, len(sel), glossary_v, lane_cfg)]
    if not sel:
        parts.append(f"（`data/batches.jsonl` 中没有选中的批次，无事可做。）")
        return "\n\n".join(parts)
    tnum = 1
    chunk = []
    for b in sel:
        parts.append(_batch_task(tnum, b, baseline, glossary_v, p))
        tnum += 1
        chunk.append(b["batch"])
        if len(chunk) == every:
            parts.append(_checkpoint_task(tnum, chunk[0], chunk[-1], label, p))
            tnum += 1
            chunk = []
    parts.append(_final_task(tnum, label, lane, sel[0]["batch"], sel[-1]["batch"],
                             len(sel), p))
    return "\n\n".join(parts)


def _parse_range(s):
    m = __import__("re").fullmatch(r"(\d+)-(\d+)", s.strip())
    if not m:
        raise SystemExit(f"--batches 需形如 1-35，收到 {s!r}")
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo > hi:
        raise SystemExit(f"--batches 区间下界大于上界：{s!r}")
    return lo, hi


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--chapter")
    g.add_argument("--batches", help="连续段批号闭区间，形如 1-35")
    ap.add_argument("--label", help="--batches 模式下的计划名（必填）")
    ap.add_argument("--checkpoint-every", type=int, default=5)
    ap.add_argument("--lane-dir")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--append-model-id")
    args = ap.parse_args(argv)

    lane_params = [args.lane_dir, args.model, args.effort, args.append_model_id]
    if any(lane_params) and not all(lane_params):
        raise SystemExit("--lane-dir/--model/--effort/--append-model-id 要么全给要么全不给")
    lane_cfg = None if not all(lane_params) else {
        "lane": Path(args.lane_dir).name, "lane_dir": args.lane_dir,
        "model": args.model, "effort": args.effort,
        "append_model_id": args.append_model_id}

    if args.batches:
        if not args.label:
            raise SystemExit("--batches 模式必须同时给 --label")
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=args.lane,
                     batch_range=_parse_range(args.batches))
        label = args.label
    else:
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=args.lane,
                     chapter=args.chapter)
        label = args.chapter

    md = render(sel, label=label, lane=args.lane, every=args.checkpoint_every,
                glossary_v=glossary_version(REPO), lane_cfg=lane_cfg)
    out_path = REPO / "docs" / "superpowers" / "plans" / f"translate-{label}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"{out_path}: {md.count('### Task')} 个任务")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
