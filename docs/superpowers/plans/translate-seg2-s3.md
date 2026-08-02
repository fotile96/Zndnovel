# seg2-s3（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 seg2-s3 段（lane=main）的全部 28 个批次逐批译出、校验、入库到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 3 个真实章别：crd、s3fa、s3s。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；段末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- **cwd 恒为主仓**；按批四件套（`build_context`/`check_batch`/`detect_collapse`/`append_forward`）用各 Task Run 行内嵌的生产 worktree 绝对路径 `/Users/fotile96/Zndnovel-prod/tools/…`，其余工具（`lane_setup`/`gen_plan`/`saturation`/`resolve`）与全部 git 操作用主仓 `uv run python tools/<x>.py`（详见「段开场自检」）；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 本段固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 8`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（Step 5）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。


## 车道配置（本计划专属，派发时逐字遵守）

| 项 | 值 |
|---|---|
| lane | opus |
| lane_dir | /Users/fotile96/Zndnovel/pilot/lanes/opus |
| model | opus |
| effort | max |
| append_model_id | claude-opus-5 |

- **派发只能走 Workflow 的 `agent(prompt, {"model": "opus", "effort": "max"})`**——`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档，使该批次失去可比性。任何一次重试都必须重新读取本表。
- **隔离纪律**：禁止读取、列出 `/Users/fotile96/Zndnovel/pilot/lanes/` 下除 `opus` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：本段进行中提案只追加进 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。
---



## 段开场自检（P3 生产会话必做，缺一不可）

本计划属于检查段 **seg2-s3**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

1. **cwd 与工具树划分**（本节全部命令、以及本计划的全部 git 操作，一律在**主仓**执行，cwd 恒为主仓，**不要 `cd` 到生产 worktree**）：
   - 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` 走**生产 worktree 的绝对路径**——各批 Task 的 Run 行已内嵌 `/Users/fotile96/Zndnovel-prod/tools/…`，逐字照抄，不要改回相对形态；
   - `lane_setup` / `gen_plan` / `saturation` / `resolve` 与全部 git 操作走**主仓 `tools/`**（它们不参与段内冻结语义；lane_setup 在生产树里会因 `__file__` 推出的车道根为空而必然报「冻结文件缺失」，git 也会因主仓路径 outside repository 而失败）。
2. **工具树版本**：`git -C /Users/fotile96/Zndnovel-prod describe --tags` 应等于 runbook「当前生产 tag」行记录的值。
3. **车道冻结**（本命令在主仓执行）：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
4. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。

### Task 1: s3s 批次 63 译文入库（69 条，约 1760 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_63/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_63.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 69 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 63 批（`lane=main chapter=s3s`，69 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 63 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_63/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 63，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_63.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 63 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_63: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_63.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 63 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_63: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_63.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 63 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次63 译文入线"
```

### Task 2: s3s 批次 64 译文入库（8 条，约 187 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_64/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_64.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 8 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 64 批（`lane=main chapter=s3s`，8 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 64 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_64/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 64，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_64.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 64 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_64: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_64.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 64 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_64: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_64.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 64 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次64 译文入线"
```

### Task 3: s3s 批次 65 译文入库（5 条，约 134 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_65/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_65.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 5 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 65 批（`lane=main chapter=s3s`，5 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 65 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_65/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 65，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_65.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 65 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_65: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_65.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 65 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_65: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_65.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 65 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次65 译文入线"
```

### Task 4: s3s 批次 66 译文入库（77 条，约 1906 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_66/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_66.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 77 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 66 批（`lane=main chapter=s3s`，77 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 66 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_66/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 66，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_66.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 66 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_66: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_66.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 66 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_66: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_66.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 66 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次66 译文入线"
```

### Task 5: crd 批次 67 译文入库（81 条，约 2083 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_67/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_67.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 81 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 67 批（`lane=main chapter=crd`，81 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 67 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_67/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 67，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_67.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 67 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_67: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_67.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 67 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_67: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_67.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 67 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次67 译文入线"
```

### Task 6: CHECKPOINT——批次 63–67 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3s 章批次 63–67 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 63–67 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 7: s3s 批次 68 译文入库（86 条，约 2402 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_68/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_68.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 86 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 68 批（`lane=main chapter=s3s`，86 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 68 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_68/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 68，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_68.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 68 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_68: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_68.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 68 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_68: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_68.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 68 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次68 译文入线"
```

### Task 8: s3s 批次 69 译文入库（11 条，约 318 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_69/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_69.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 11 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 69 批（`lane=main chapter=s3s`，11 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 69 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_69/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 69，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_69.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 69 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_69: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_69.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 69 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_69: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_69.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 69 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次69 译文入线"
```

### Task 9: s3s 批次 70 译文入库（11 条，约 284 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_70/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_70.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 11 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 70 批（`lane=main chapter=s3s`，11 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 70 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_70/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 70，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_70.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 70 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_70: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_70.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 70 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_70: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_70.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 70 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次70 译文入线"
```

### Task 10: crd 批次 71 译文入库（38 条，约 950 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_71/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_71.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 38 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 71 批（`lane=main chapter=crd`，38 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 71 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_71/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 71，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_71.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 71 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_71: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_71.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 71 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_71: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_71.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 71 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次71 译文入线"
```

### Task 11: s3s 批次 72 译文入库（199 条，约 5651 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_72/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_72.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 199 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 72 批（`lane=main chapter=s3s`，199 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 72 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_72/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 72，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_72.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 72 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_72: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_72.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 72 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_72: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_72.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 72 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次72 译文入线"
```

### Task 12: CHECKPOINT——批次 68–72 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3s 章批次 68–72 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 68–72 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 13: crd 批次 73 译文入库（40 条，约 1089 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_73/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_73.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 40 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 73 批（`lane=main chapter=crd`，40 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 73 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_73/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 73，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_73.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 73 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_73: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_73.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 73 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_73: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_73.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 73 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次73 译文入线"
```

### Task 14: s3s 批次 74 译文入库（92 条，约 2606 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_74/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_74.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 92 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 74 批（`lane=main chapter=s3s`，92 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 74 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_74/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 74，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_74.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 74 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_74: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_74.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 74 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_74: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_74.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 74 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次74 译文入线"
```

### Task 15: s3s 批次 75 译文入库（63 条，约 1219 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_75/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_75.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 63 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 75 批（`lane=main chapter=s3s`，63 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 75 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_75/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 75，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_75.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 75 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_75: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_75.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 75 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_75: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_75.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 75 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次75 译文入线"
```

### Task 16: crd 批次 76 译文入库（86 条，约 2202 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_76/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_76.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 86 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 76 批（`lane=main chapter=crd`，86 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 76 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_76/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 76，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_76.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 76 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_76: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_76.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 76 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_76: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_76.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 76 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次76 译文入线"
```

### Task 17: s3s 批次 77 译文入库（118 条，约 3027 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_77/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_77.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 118 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 77 批（`lane=main chapter=s3s`，118 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 77 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_77/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 77，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_77.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 77 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_77: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_77.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 77 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_77: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_77.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 77 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次77 译文入线"
```

### Task 18: CHECKPOINT——批次 73–77 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3s 章批次 73–77 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 73–77 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 19: crd 批次 78 译文入库（9 条，约 209 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_78/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_78.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 9 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 78 批（`lane=main chapter=crd`，9 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 78 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_78/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 78，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_78.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 78 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_78: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_78.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 78 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_78: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_78.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 78 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次78 译文入线"
```

### Task 20: s3s 批次 79 译文入库（35 条，约 869 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_79/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_79.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 35 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 79 批（`lane=main chapter=s3s`，35 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 79 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_79/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 79，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_79.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 79 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_79: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_79.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 79 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_79: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_79.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 79 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次79 译文入线"
```

### Task 21: crd 批次 80 译文入库（44 条，约 1198 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_80/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_80.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 44 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 80 批（`lane=main chapter=crd`，44 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 80 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_80/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 80，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_80.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 80 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_80: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_80.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 80 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_80: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_80.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 80 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次80 译文入线"
```

### Task 22: s3s 批次 81 译文入库（38 条，约 1021 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_81/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_81.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 38 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 81 批（`lane=main chapter=s3s`，38 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 81 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_81/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 81，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_81.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 81 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_81: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_81.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 81 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_81: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_81.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 81 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次81 译文入线"
```

### Task 23: crd 批次 82 译文入库（71 条，约 1722 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_82/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_82.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 71 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 82 批（`lane=main chapter=crd`，71 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 82 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_82/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 82，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_82.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 82 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_82: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_82.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 82 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_82: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_82.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 82 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次82 译文入线"
```

### Task 24: CHECKPOINT——批次 78–82 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3s 章批次 78–82 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 78–82 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 25: s3s 批次 83 译文入库（64 条，约 1353 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_83/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_83.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 64 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 83 批（`lane=main chapter=s3s`，64 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 83 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_83/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 83，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_83.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 83 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_83: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_83.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 83 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_83: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_83.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 83 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次83 译文入线"
```

### Task 26: s3s 批次 84 译文入库（117 条，约 2756 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_84/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_84.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 117 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 84 批（`lane=main chapter=s3s`，117 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 84 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_84/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 84，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_84.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 84 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_84: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_84.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 84 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_84: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_84.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 84 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次84 译文入线"
```

### Task 27: crd 批次 85 译文入库（101 条，约 2324 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_85/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_85.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 101 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 85 批（`lane=main chapter=crd`，101 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 85 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_85/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 85，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_85.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 85 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_85: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_85.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 85 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_85: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_85.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 85 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次85 译文入线"
```

### Task 28: s3s 批次 86 译文入库（49 条，约 1046 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_86/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_86.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 49 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 86 批（`lane=main chapter=s3s`，49 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 86 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_86/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 86，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_86.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 86 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_86: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_86.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 86 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_86: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_86.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 86 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次86 译文入线"
```

### Task 29: crd 批次 87 译文入库（71 条，约 1753 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_87/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_87.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 71 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 87 批（`lane=main chapter=crd`，71 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 87 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_87/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 87，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_87.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 87 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_87: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_87.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 87 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_87: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_87.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 87 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次87 译文入线"
```

### Task 30: CHECKPOINT——批次 83–87 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3s 章批次 83–87 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 83–87 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 31: s3fa 批次 88 译文入库（394 条，约 8983 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_88/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_88.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 394 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 88 批（`lane=main chapter=s3fa`，394 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 88 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_88/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 88，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_88.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 88 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_88: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_88.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 88 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_88: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_88.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 88 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3fa 批次88 译文入线"
```

### Task 32: s3fa 批次 89 译文入库（29 条，约 623 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_89/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_89.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 29 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 89 批（`lane=main chapter=s3fa`，29 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 89 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_89/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 89，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_89.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 89 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_89: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_89.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 89 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_89: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_89.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 89 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3fa 批次89 译文入线"
```

### Task 33: crd 批次 90 译文入库（1 条，约 10 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_90/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_90.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 1 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 90 批（`lane=main chapter=crd`，1 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 90 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_90/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 90，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_90.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 90 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_90: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_90.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 90 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_90: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_90.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 90 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 8`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次90 译文入线"
```

### Task 34: 段末——梗概回译自检 + 人工评审 gate

crd、s3fa、s3s 章 main 车道全部 28 个批次（63–90）已入库 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s3fa、s3s 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 28 个 `data: <chapter> 批次N 译文入线` commit（批号 63–90，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。



## 段末流程（本段全部批次入线后执行，缺一不可）

以下命令与 git 操作全部在**主仓**执行（cwd 恒为主仓，工具用主仓 `tools/`）。本清单与 `docs/ops/p3-production-runbook.md` §5 逐项对齐。

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. （tag 前，可选但强烈建议）跑**彩野测试**作额外验收：`uv run python tools/ayano_test.py --segment seg2-s3 --qa config/ayano_qa/seg2-s3.yaml --lane-dir pilot/lanes/opus`（零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，`config/ayano_qa/seg2-s3.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过即记进段末台账，不必人工先 `ls` 探路径。**不得拿别段的题库顶替**——题库自带 `segment` 绑定，段名不符工具会直接报错退出（rc=1）；上一段的题目其答案往往整张躺在本段前缀卡里，跑出来必是恒绿假信号）。报告落 `work/out/ayano-seg2-s3.md`，判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。
4. 打段完成 tag：`git tag prod-opus-seg2-s3-done`。
5. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-seg2-s3.md` 把本段提案按词族聚成卷宗，再对可裁词族跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`（**`--data-dir` 必须带**——漏传会读仓库根 `data/`，那里没有车道 forward.jsonl，结果是一张全列「滚存」的合理假表；工具会在表头前打印 `done=N 条已入线译文`，N 为 0 即说明漏传），可裁决词族当场裁，滚存词族聚类归档（runbook §5「裁决会话清单」）。裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。