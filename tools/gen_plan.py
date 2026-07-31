"""章翻译执行计划生成器：data/batches.jsonl 里选中的批次 → 可被
superpowers:executing-plans 直接执行的 docs/superpowers/plans/translate-<chapter>.md。

render() 是纯字符串模板函数（不碰文件系统）；main() 负责读 batches.jsonl、
按 --lane/--chapter 过滤、把结果写盘。
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


def _header(chapter, lane, every, count, glossary_v):
    return f"""# {chapter} 章（{lane} 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 {chapter} 章（lane={lane}）的全部 {count} 个批次逐批译出、校验、入库到 `data/forward.jsonl`，章末完成骨架一致性自检与人工评审 gate。

**Architecture:** 每个批次一个任务，走「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → append_forward 入库并提交」四步流水线（P1b 已建成，签名见下）；每 {every} 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；章末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- 运行 `uv run python tools/<x>.py`；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: {chapter} 批次N 译文入线`，main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `data/notes/{chapter}.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 试点期固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v {glossary_v}`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（Step 4）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。

---"""


def _batch_task(tnum, batch, baseline, glossary_v):
    n, ch, ids = batch["batch"], batch["chapter"], batch["ids"]
    return f"""### Task {tnum}: {ch} 批次 {n} 译文入库（{len(ids)} 条，约 {batch["jp_chars"]} 日文字）

**Files:**
- Produces: `work/ctx/batch_{n}/{{context.md,source.jsonl,manifest.json}}`（Step 1）、`work/out/batch_{n}.draft.jsonl`（Step 2 产出、Step 3 校验）、`data/forward.jsonl` 追加本批 {len(ids)} 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 {n} 批（`lane={batch["lane"]} chapter={ch}`，{len(ids)} 条 id）
- Produces: `data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch {n} --profile cc --baseline {baseline}`
Expected: 生成 `work/ctx/batch_{n}/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 {n}），产出 `work/out/batch_{n}.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `uv run python tools/check_batch.py --batch {n}`
Expected: `batch_{n}: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/out/batch_{n}.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成 Step 2 实际执行翻译子代理所用的模型 ID；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`uv run python tools/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v {glossary_v}`

```bash
git add data/forward.jsonl
git commit -m "data: {ch} 批次{n} 译文入线"
```"""


def _checkpoint_task(tnum, first, last, chapter):
    return f"""### Task {tnum}: CHECKPOINT——批次 {first}–{last} 术语提案裁决 + 抽查

到这里已完成 {chapter} 章批次 {first}–{last} 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `data/notes/{chapter}.md`（若这几批翻译中子代理追加过内容——文件不存在说明本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。逐条裁决是否采纳；采纳的词条走新一版 `glossary/glossary.vN.yaml`（N = 当前最高版本号 + 1）与召回令流程（`CLAUDE.md`「术语层」节），不要直接改 `glossary/active.json`。裁决可以滞后到下一个检查点，但不要让提案一直悬空。

- [ ] **Step 2: 抽查**

从批次 {first}–{last} 已入库的译文里随机抽 2–3 条，对照对应 `work/ctx/batch_*/source.jsonl` 的原文与 `data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `data/forward.jsonl`——它是 append-only 正向线）。"""


def _final_task(tnum, chapter, lane, first, last, count):
    return f"""### Task {tnum}: 章末——梗概回译自检 + 人工评审 gate

{chapter} 章 {lane} 车道全部 {count} 个批次（{first}–{last}）已入库 `data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本章对应的章节梗概卡（`skeleton/cards.zh/`，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本章刚入库的 `data/forward.jsonl` 正文译文：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否和 `skeleton/anchors.yaml` 一致，尤其检查有没有在本章尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。

- [ ] **Step 2: 人工评审 gate**

把本章相关的 `data:` commit（`git log --oneline` 过滤 `{chapter}`）交给人工复核。**不要自动放行**——人工确认无误后本章翻译才算完成，之后才能对下一章跑 `tools/gen_plan.py` 生成新计划。"""


def render(batches, chapter, lane, every=5, baseline="none", glossary_v=GLOSSARY_V) -> str:
    sel = sorted((b for b in batches if b["chapter"] == chapter and b["lane"] == lane),
                 key=lambda b: b["batch"])
    parts = [_header(chapter, lane, every, len(sel), glossary_v)]
    if not sel:
        parts.append(f"（`data/batches.jsonl` 中没有 lane={lane} chapter={chapter} 的批次，无事可做。）")
        return "\n\n".join(parts)
    tnum = 1
    chunk = []
    for b in sel:
        parts.append(_batch_task(tnum, b, baseline, glossary_v))
        tnum += 1
        chunk.append(b["batch"])
        if len(chunk) == every:
            parts.append(_checkpoint_task(tnum, chunk[0], chunk[-1], chapter))
            tnum += 1
            chunk = []
    parts.append(_final_task(tnum, chapter, lane, sel[0]["batch"], sel[-1]["batch"], len(sel)))
    return "\n\n".join(parts)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--checkpoint-every", type=int, default=5)
    args = ap.parse_args(argv)
    batches = read_jsonl(DATA / "batches.jsonl")
    md = render(batches, chapter=args.chapter, lane=args.lane, every=args.checkpoint_every,
                glossary_v=glossary_version(REPO))
    out_path = REPO / "docs" / "superpowers" / "plans" / f"translate-{args.chapter}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    n_tasks = md.count("### Task")
    print(f"{out_path}: {n_tasks} 个任务")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
