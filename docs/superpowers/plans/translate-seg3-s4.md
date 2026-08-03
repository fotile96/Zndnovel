# seg3-s4（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 seg3-s4 段（lane=main）的全部 27 个批次逐批译出、校验、入库到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 4 个真实章别：crd、s4fa、s4fb、s4s。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；段末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- **cwd 恒为主仓**；按批四件套（`build_context`/`check_batch`/`detect_collapse`/`append_forward`）用各 Task Run 行内嵌的生产 worktree 绝对路径 `/Users/fotile96/Zndnovel-prod/tools/…`，其余工具（`lane_setup`/`gen_plan`/`saturation`/`resolve`）与全部 git 操作用主仓 `uv run python tools/<x>.py`（详见「段开场自检」）；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 本段固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 9`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
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

本计划属于检查段 **seg3-s4**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

1. **cwd 与工具树划分**（本节全部命令、以及本计划的全部 git 操作，一律在**主仓**执行，cwd 恒为主仓，**不要 `cd` 到生产 worktree**）：
   - 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` 走**生产 worktree 的绝对路径**——各批 Task 的 Run 行已内嵌 `/Users/fotile96/Zndnovel-prod/tools/…`，逐字照抄，不要改回相对形态；
   - `lane_setup` / `gen_plan` / `saturation` / `resolve` 与全部 git 操作走**主仓 `tools/`**（它们不参与段内冻结语义；lane_setup 在生产树里会因 `__file__` 推出的车道根为空而必然报「冻结文件缺失」，git 也会因主仓路径 outside repository 而失败）。
2. **工具树版本**：`git -C /Users/fotile96/Zndnovel-prod describe --tags` 应等于 runbook「当前生产 tag」行记录的值。
3. **车道冻结**（本命令在主仓执行）：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
4. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。

### Task 1: s4s 批次 91 译文入库（50 条，约 1231 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_91/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_91.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 50 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 91 批（`lane=main chapter=s4s`，50 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 91 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_91/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 91，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_91.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 91 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_91: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_91.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 91 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_91: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_91.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 91 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次91 译文入线"
```

### Task 2: s4s 批次 92 译文入库（13 条，约 324 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_92/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_92.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 13 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 92 批（`lane=main chapter=s4s`，13 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 92 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_92/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 92，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_92.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 92 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_92: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_92.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 92 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_92: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_92.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 92 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次92 译文入线"
```

### Task 3: crd 批次 93 译文入库（30 条，约 813 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_93/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_93.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 30 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 93 批（`lane=main chapter=crd`，30 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 93 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_93/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 93，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_93.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 93 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_93: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_93.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 93 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_93: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_93.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 93 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次93 译文入线"
```

### Task 4: s4s 批次 94 译文入库（77 条，约 1752 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_94/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_94.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 77 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 94 批（`lane=main chapter=s4s`，77 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 94 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_94/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 94，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_94.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 94 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_94: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_94.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 94 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_94: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_94.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 94 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次94 译文入线"
```

### Task 5: s4s 批次 95 译文入库（49 条，约 857 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_95/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_95.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 49 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 95 批（`lane=main chapter=s4s`，49 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 95 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_95/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 95，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_95.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 95 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_95: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_95.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 95 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_95: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_95.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 95 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次95 译文入线"
```

### Task 6: CHECKPOINT——批次 91–95 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4s 章批次 91–95 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 91–95 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 7: s4s 批次 96 译文入库（103 条，约 2085 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_96/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_96.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 103 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 96 批（`lane=main chapter=s4s`，103 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 96 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_96/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 96，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_96.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 96 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_96: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_96.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 96 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_96: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_96.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 96 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次96 译文入线"
```

### Task 8: crd 批次 97 译文入库（129 条，约 3512 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_97/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_97.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 129 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 97 批（`lane=main chapter=crd`，129 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 97 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_97/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 97，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_97.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 97 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_97: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_97.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 97 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_97: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_97.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 97 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次97 译文入线"
```

### Task 9: s4s 批次 98 译文入库（80 条，约 1604 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_98/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_98.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 80 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 98 批（`lane=main chapter=s4s`，80 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 98 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_98/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 98，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_98.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 98 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_98: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_98.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 98 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_98: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_98.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 98 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次98 译文入线"
```

### Task 10: s4s 批次 99 译文入库（9 条，约 181 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_99/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_99.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 9 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 99 批（`lane=main chapter=s4s`，9 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 99 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_99/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 99，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_99.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 99 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_99: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_99.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 99 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_99: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_99.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 99 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次99 译文入线"
```

### Task 11: crd 批次 100 译文入库（67 条，约 1738 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_100/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_100.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 67 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 100 批（`lane=main chapter=crd`，67 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 100 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_100/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 100，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_100.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 100 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_100: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_100.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 100 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_100: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_100.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 100 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次100 译文入线"
```

### Task 12: CHECKPOINT——批次 96–100 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4s 章批次 96–100 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 96–100 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 13: s4s 批次 101 译文入库（33 条，约 484 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_101/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_101.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 33 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 101 批（`lane=main chapter=s4s`，33 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 101 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_101/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 101，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_101.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 101 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_101: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_101.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 101 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_101: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_101.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 101 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次101 译文入线"
```

### Task 14: s4s 批次 102 译文入库（5 条，约 66 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_102/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_102.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 5 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 102 批（`lane=main chapter=s4s`，5 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 102 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_102/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 102，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_102.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 102 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_102: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_102.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 102 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_102: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_102.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 102 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次102 译文入线"
```

### Task 15: crd 批次 103 译文入库（29 条，约 773 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_103/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_103.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 29 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 103 批（`lane=main chapter=crd`，29 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 103 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_103/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 103，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_103.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 103 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_103: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_103.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 103 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_103: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_103.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 103 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次103 译文入线"
```

### Task 16: s4s 批次 104 译文入库（90 条，约 1839 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_104/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_104.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 90 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 104 批（`lane=main chapter=s4s`，90 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 104 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_104/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 104，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_104.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 104 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_104: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_104.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 104 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_104: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_104.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 104 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次104 译文入线"
```

### Task 17: crd 批次 105 译文入库（161 条，约 4340 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_105/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_105.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 161 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 105 批（`lane=main chapter=crd`，161 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 105 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_105/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 105，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_105.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 105 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_105: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_105.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 105 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_105: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_105.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 105 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次105 译文入线"
```

### Task 18: CHECKPOINT——批次 101–105 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4s 章批次 101–105 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 101–105 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 19: s4s 批次 106 译文入库（48 条，约 936 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_106/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_106.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 48 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 106 批（`lane=main chapter=s4s`，48 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 106 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_106/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 106，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_106.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 106 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_106: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_106.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 106 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_106: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_106.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 106 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次106 译文入线"
```

### Task 20: crd 批次 107 译文入库（23 条，约 547 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_107/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_107.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 23 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 107 批（`lane=main chapter=crd`，23 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 107 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_107/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 107，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_107.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 107 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_107: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_107.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 107 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_107: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_107.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 107 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次107 译文入线"
```

### Task 21: s4s 批次 108 译文入库（110 条，约 2378 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_108/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_108.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 110 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 108 批（`lane=main chapter=s4s`，110 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 108 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_108/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 108，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_108.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 108 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_108: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_108.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 108 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_108: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_108.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 108 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次108 译文入线"
```

### Task 22: s4s 批次 109 译文入库（32 条，约 784 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_109/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_109.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 32 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 109 批（`lane=main chapter=s4s`，32 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 109 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_109/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 109，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_109.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 109 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_109: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_109.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 109 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_109: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_109.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 109 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次109 译文入线"
```

### Task 23: crd 批次 110 译文入库（98 条，约 2586 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_110/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_110.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 98 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 110 批（`lane=main chapter=crd`，98 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 110 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_110/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 110，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_110.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 110 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_110: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_110.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 110 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_110: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_110.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 110 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次110 译文入线"
```

### Task 24: CHECKPOINT——批次 106–110 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4s 章批次 106–110 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 106–110 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 25: s4fa 批次 111 译文入库（364 条，约 8995 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_111/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_111.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 364 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 111 批（`lane=main chapter=s4fa`，364 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 111 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_111/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 111，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_111.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 111 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_111: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_111.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 111 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_111: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_111.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 111 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fa 批次111 译文入线"
```

### Task 26: s4fa 批次 112 译文入库（236 条，约 5796 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_112/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_112.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 236 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 112 批（`lane=main chapter=s4fa`，236 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 112 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_112/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 112，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_112.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 112 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_112: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_112.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 112 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_112: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_112.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 112 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fa 批次112 译文入线"
```

### Task 27: s4s 批次 113 译文入库（207 条，约 4229 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_113/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_113.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 207 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 113 批（`lane=main chapter=s4s`，207 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 113 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_113/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 113，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_113.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 113 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_113: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_113.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 113 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_113: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_113.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 113 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次113 译文入线"
```

### Task 28: crd 批次 114 译文入库（87 条，约 2353 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_114/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_114.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 87 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 114 批（`lane=main chapter=crd`，87 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 114 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_114/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 114，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_114.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 114 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_114: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_114.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 114 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_114: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_114.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 114 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次114 译文入线"
```

### Task 29: s4fb 批次 115 译文入库（374 条，约 8974 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_115/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_115.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 374 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 115 批（`lane=main chapter=s4fb`，374 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 115 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_115/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 115，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_115.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 115 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_115: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_115.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 115 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_115: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_115.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 115 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fb 批次115 译文入线"
```

### Task 30: CHECKPOINT——批次 111–115 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4fa、s4fb、s4s 章批次 111–115 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4fa.md`、`s4fb.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 111–115 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 31: s4fb 批次 116 译文入库（73 条，约 2029 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_116/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_116.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 73 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 116 批（`lane=main chapter=s4fb`，73 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 116 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_116/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 116，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_116.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 116 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_116: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_116.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 116 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_116: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_116.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 116 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fb 批次116 译文入线"
```

### Task 32: crd 批次 117 译文入库（2 条，约 20 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_117/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_117.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 2 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 117 批（`lane=main chapter=crd`，2 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 117 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_117/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 117，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_117.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 117 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_117: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_117.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 117 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_117: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_117.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 117 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次117 译文入线"
```

### Task 33: 段末——梗概回译自检 + 人工评审 gate

crd、s4fa、s4fb、s4s 章 main 车道全部 27 个批次（91–117）已入库 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s4fa、s4fb、s4s 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 27 个 `data: <chapter> 批次N 译文入线` commit（批号 91–117，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。



## 段末流程（本段全部批次入线后执行，缺一不可）

以下命令与 git 操作全部在**主仓**执行（cwd 恒为主仓，工具用主仓 `tools/`）。本清单与 `docs/ops/p3-production-runbook.md` §5 逐项对齐。

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. （tag 前，可选但强烈建议）跑**彩野测试**作额外验收：`uv run python tools/ayano_test.py --segment seg3-s4 --qa config/ayano_qa/seg3-s4.yaml --lane-dir pilot/lanes/opus`（零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，`config/ayano_qa/seg3-s4.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过即记进段末台账，不必人工先 `ls` 探路径。**不得拿别段的题库顶替**——题库自带 `segment` 绑定，段名不符工具会直接报错退出（rc=1）；上一段的题目其答案往往整张躺在本段前缀卡里，跑出来必是恒绿假信号）。报告落 `work/out/ayano-seg3-s4.md`，判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。
4. 打段完成 tag：`git tag prod-opus-seg3-s4-done`。
5. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-seg3-s4.md` 把本段提案按词族聚成卷宗，再对可裁词族跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`（**`--data-dir` 必须带**——漏传会读仓库根 `data/`，那里没有车道 forward.jsonl，结果是一张全列「滚存」的合理假表；工具会在表头前打印 `done=N 条已入线译文`，N 为 0 即说明漏传），可裁决词族当场裁，滚存词族聚类归档（runbook §5「裁决会话清单」）。裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。