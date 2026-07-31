# pilot-opus 章（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 pilot-opus 章（lane=main）的全部 35 个批次逐批译出、校验、入库到 `work/lanes/opus/data/forward.jsonl`，章末完成骨架一致性自检与人工评审 gate。

**Architecture:** 每个批次一个任务，走「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → append_forward 入库并提交」四步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；章末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- 运行 `uv run python tools/<x>.py`；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `work/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 试点期固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 6`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（Step 4）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。


## 车道配置（本计划专属，派发时逐字遵守）

| 项 | 值 |
|---|---|
| lane | opus |
| lane_dir | work/lanes/opus |
| model | opus |
| effort | max |
| append_model_id | claude-opus-5 |

- **派发只能走 Workflow 的 `agent(prompt, {"model": "opus", "effort": "max"})`**——`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档，使该批次失去可比性。任何一次重试都必须重新读取本表。
- **隔离纪律**：禁止读取、列出 `work/lanes/` 下除 `opus` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `work/lanes/opus/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：试点期间提案只追加进 `work/lanes/opus/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `work/lanes/opus/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。
---

### Task 1: s0f 批次 1 译文入库（339 条，约 8989 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_1/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_1.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 339 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 1 批（`lane=main chapter=s0f`，339 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 1 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_1/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 1，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_1.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 1`
Expected: `batch_1: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_1.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 1 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s0f 批次1 译文入线"
```

### Task 2: s0f 批次 2 译文入库（229 条，约 6069 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_2/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_2.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 229 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 2 批（`lane=main chapter=s0f`，229 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 2 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_2/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 2，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_2.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 2`
Expected: `batch_2: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_2.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 2 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s0f 批次2 译文入线"
```

### Task 3: crd 批次 3 译文入库（1 条，约 9 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_3/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_3.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 1 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 3 批（`lane=main chapter=crd`，1 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 3 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_3/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 3，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_3.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 3`
Expected: `batch_3: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_3.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 3 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次3 译文入线"
```

### Task 4: s1s 批次 4 译文入库（84 条，约 2180 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_4/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_4.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 84 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 4 批（`lane=main chapter=s1s`，84 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 4 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_4/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 4，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_4.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 4`
Expected: `batch_4: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_4.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 4 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次4 译文入线"
```

### Task 5: sys 批次 5 译文入库（13 条，约 326 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_5/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_5.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 13 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 5 批（`lane=main chapter=sys`，13 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 5 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_5/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 5，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_5.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 5`
Expected: `batch_5: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_5.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 5 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: sys 批次5 译文入线"
```

### Task 6: CHECKPOINT——批次 1–5 术语提案裁决 + 抽查

到这里已完成 crd、s0f、s1s、sys 章批次 1–5 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s0f.md`、`s1s.md`、`sys.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 1–5 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 7: crd 批次 6 译文入库（272 条，约 6978 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_6/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_6.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 272 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 6 批（`lane=main chapter=crd`，272 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 6 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_6/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 6，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_6.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 6`
Expected: `batch_6: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_6.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 6 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次6 译文入线"
```

### Task 8: s1s 批次 7 译文入库（90 条，约 2659 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_7/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_7.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 90 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 7 批（`lane=main chapter=s1s`，90 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 7 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_7/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 7，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_7.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 7`
Expected: `batch_7: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_7.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 7 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次7 译文入线"
```

### Task 9: s1s 批次 8 译文入库（22 条，约 576 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_8/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_8.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 22 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 8 批（`lane=main chapter=s1s`，22 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 8 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_8/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 8，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_8.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 8`
Expected: `batch_8: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_8.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 8 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次8 译文入线"
```

### Task 10: s1s 批次 9 译文入库（27 条，约 748 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_9/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_9.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 27 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 9 批（`lane=main chapter=s1s`，27 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 9 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_9/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 9，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_9.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 9`
Expected: `batch_9: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_9.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 9 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次9 译文入线"
```

### Task 11: crd 批次 10 译文入库（202 条，约 7492 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_10/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_10.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 202 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 10 批（`lane=main chapter=crd`，202 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 10 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_10/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 10，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_10.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 10`
Expected: `batch_10: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_10.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 10 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次10 译文入线"
```

### Task 12: CHECKPOINT——批次 6–10 术语提案裁决 + 抽查

到这里已完成 crd、s1s 章批次 6–10 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 6–10 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 13: s1s 批次 11 译文入库（159 条，约 4500 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_11/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_11.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 159 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 11 批（`lane=main chapter=s1s`，159 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 11 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_11/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 11，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_11.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 11`
Expected: `batch_11: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_11.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 11 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次11 译文入线"
```

### Task 14: crd 批次 12 译文入库（164 条，约 4410 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_12/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_12.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 164 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 12 批（`lane=main chapter=crd`，164 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 12 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_12/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 12，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_12.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 12`
Expected: `batch_12: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_12.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 12 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次12 译文入线"
```

### Task 15: s1s 批次 13 译文入库（29 条，约 739 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_13/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_13.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 29 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 13 批（`lane=main chapter=s1s`，29 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 13 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_13/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 13，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_13.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 13`
Expected: `batch_13: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_13.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 13 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次13 译文入线"
```

### Task 16: crd 批次 14 译文入库（44 条，约 1105 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_14/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_14.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 44 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 14 批（`lane=main chapter=crd`，44 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 14 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_14/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 14，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_14.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 14`
Expected: `batch_14: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_14.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 14 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次14 译文入线"
```

### Task 17: s1s 批次 15 译文入库（46 条，约 1422 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_15/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_15.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 46 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 15 批（`lane=main chapter=s1s`，46 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 15 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_15/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 15，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_15.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 15`
Expected: `batch_15: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_15.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 15 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次15 译文入线"
```

### Task 18: CHECKPOINT——批次 11–15 术语提案裁决 + 抽查

到这里已完成 crd、s1s 章批次 11–15 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 11–15 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 19: crd 批次 16 译文入库（153 条，约 3820 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_16/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_16.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 153 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 16 批（`lane=main chapter=crd`，153 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 16 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_16/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 16，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_16.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 16`
Expected: `batch_16: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_16.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 16 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次16 译文入线"
```

### Task 20: s1s 批次 17 译文入库（204 条，约 6257 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_17/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_17.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 204 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 17 批（`lane=main chapter=s1s`，204 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 17 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_17/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 17，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_17.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 17`
Expected: `batch_17: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_17.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 17 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次17 译文入线"
```

### Task 21: sys 批次 18 译文入库（30 条，约 679 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_18/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_18.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 30 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 18 批（`lane=main chapter=sys`，30 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 18 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_18/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 18，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_18.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 18`
Expected: `batch_18: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_18.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 18 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: sys 批次18 译文入线"
```

### Task 22: s1s 批次 19 译文入库（228 条，约 5388 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_19/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_19.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 228 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 19 批（`lane=main chapter=s1s`，228 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 19 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_19/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 19，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_19.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 19`
Expected: `batch_19: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_19.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 19 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次19 译文入线"
```

### Task 23: crd 批次 20 译文入库（46 条，约 1100 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_20/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_20.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 46 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 20 批（`lane=main chapter=crd`，46 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 20 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_20/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 20，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_20.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 20`
Expected: `batch_20: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_20.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 20 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次20 译文入线"
```

### Task 24: CHECKPOINT——批次 16–20 术语提案裁决 + 抽查

到这里已完成 crd、s1s、sys 章批次 16–20 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`、`sys.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 16–20 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 25: s1s 批次 21 译文入库（118 条，约 2523 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_21/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_21.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 118 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 21 批（`lane=main chapter=s1s`，118 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 21 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_21/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 21，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_21.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 21`
Expected: `batch_21: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_21.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 21 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次21 译文入线"
```

### Task 26: s1s 批次 22 译文入库（38 条，约 1011 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_22/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_22.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 38 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 22 批（`lane=main chapter=s1s`，38 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 22 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_22/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 22，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_22.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 22`
Expected: `batch_22: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_22.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 22 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次22 译文入线"
```

### Task 27: s1s 批次 23 译文入库（70 条，约 2228 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_23/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_23.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 70 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 23 批（`lane=main chapter=s1s`，70 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 23 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_23/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 23，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_23.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 23`
Expected: `batch_23: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_23.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 23 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次23 译文入线"
```

### Task 28: crd 批次 24 译文入库（25 条，约 518 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_24/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_24.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 25 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 24 批（`lane=main chapter=crd`，25 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 24 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_24/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 24，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_24.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 24`
Expected: `batch_24: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_24.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 24 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次24 译文入线"
```

### Task 29: s1s 批次 25 译文入库（105 条，约 2784 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_25/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_25.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 105 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 25 批（`lane=main chapter=s1s`，105 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 25 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_25/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 25，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_25.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 25`
Expected: `batch_25: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_25.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 25 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次25 译文入线"
```

### Task 30: CHECKPOINT——批次 21–25 术语提案裁决 + 抽查

到这里已完成 crd、s1s 章批次 21–25 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 21–25 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 31: s1s 批次 26 译文入库（213 条，约 5795 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_26/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_26.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 213 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 26 批（`lane=main chapter=s1s`，213 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 26 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_26/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 26，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_26.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 26`
Expected: `batch_26: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_26.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 26 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1s 批次26 译文入线"
```

### Task 32: crd 批次 27 译文入库（350 条，约 8985 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_27/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_27.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 350 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 27 批（`lane=main chapter=crd`，350 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 27 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_27/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 27，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_27.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 27`
Expected: `batch_27: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_27.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 27 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次27 译文入线"
```

### Task 33: crd 批次 28 译文入库（99 条，约 2964 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_28/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_28.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 99 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 28 批（`lane=main chapter=crd`，99 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 28 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_28/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 28，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_28.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 28`
Expected: `batch_28: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_28.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 28 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次28 译文入线"
```

### Task 34: s1f 批次 29 译文入库（311 条，约 8994 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_29/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_29.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 311 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 29 批（`lane=main chapter=s1f`，311 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 29 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_29/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 29，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_29.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 29`
Expected: `batch_29: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_29.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 29 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1f 批次29 译文入线"
```

### Task 35: s1f 批次 30 译文入库（335 条，约 8978 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_30/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_30.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 335 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 30 批（`lane=main chapter=s1f`，335 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 30 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_30/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 30，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_30.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 30`
Expected: `batch_30: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_30.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 30 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1f 批次30 译文入线"
```

### Task 36: CHECKPOINT——批次 26–30 术语提案裁决 + 抽查

到这里已完成 crd、s1f、s1s 章批次 26–30 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s1f.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 26–30 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 37: s1f 批次 31 译文入库（6 条，约 296 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_31/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_31.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 6 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 31 批（`lane=main chapter=s1f`，6 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 31 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_31/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 31，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_31.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 31`
Expected: `batch_31: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_31.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 31 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s1f 批次31 译文入线"
```

### Task 38: crd 批次 32 译文入库（17 条，约 170 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_32/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_32.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 17 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 32 批（`lane=main chapter=crd`，17 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 32 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_32/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 32，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_32.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 32`
Expected: `batch_32: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_32.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 32 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次32 译文入线"
```

### Task 39: s2s 批次 33 译文入库（66 条，约 1656 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_33/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_33.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 66 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 33 批（`lane=main chapter=s2s`，66 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 33 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_33/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 33，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_33.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 33`
Expected: `batch_33: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_33.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 33 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次33 译文入线"
```

### Task 40: crd 批次 34 译文入库（41 条，约 1041 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_34/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_34.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 41 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 34 批（`lane=main chapter=crd`，41 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 34 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_34/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 34，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_34.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 34`
Expected: `batch_34: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_34.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 34 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次34 译文入线"
```

### Task 41: s2s 批次 35 译文入库（106 条，约 2893 日文字）

**Files:**
- Produces: `work/lanes/opus/work/ctx/batch_35/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/lanes/opus/work/out/batch_35.draft.jsonl`（Step 2 产出、Step 3 校验）、`work/lanes/opus/data/forward.jsonl` 追加本批 106 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 35 批（`lane=main chapter=s2s`，106 条 id）
- Produces: `work/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 35 --profile cc --baseline none --repo work/lanes/opus`
Expected: 生成 `work/lanes/opus/work/ctx/batch_35/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 35，并按本计划头部「车道配置」注入车道根），产出 `work/lanes/opus/work/out/batch_35.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/check_batch.py --batch 35`
Expected: `batch_35: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/lanes/opus/work/out/batch_35.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data uv run python tools/append_forward.py --batch 35 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add work/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次35 译文入线"
```

### Task 42: CHECKPOINT——批次 31–35 术语提案裁决 + 抽查

到这里已完成 crd、s1f、s2s 章批次 31–35 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `work/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s1f.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 31–35 已入库的译文里随机抽 2–3 条，对照对应 `work/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `work/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `work/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 43: 章末——梗概回译自检 + 人工评审 gate

pilot-opus 章 main 车道全部 35 个批次（1–35）已入库 `work/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本章对应的章节梗概卡（`skeleton/cards.zh/`，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本章刚入库的 `work/lanes/opus/data/forward.jsonl` 正文译文：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否和 `skeleton/anchors.yaml` 一致，尤其检查有没有在本章尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 35 个 `data: <chapter> 批次N 译文入线` commit（批号 1–35，`<chapter>` 各批不同，见各批 Task 的 Step 4）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。