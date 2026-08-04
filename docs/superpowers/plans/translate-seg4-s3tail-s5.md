# seg4-s3tail-s5（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 seg4-s3tail-s5 段（lane=main）的全部 21 个批次逐批译出、校验、入库到 `pilot/lanes/opus/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 6 个真实章别：crd、s3fb、s3fc、s3s、s5f、s5s。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；段末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- **cwd 恒为主仓**；按批四件套（`build_context`/`check_batch`/`detect_collapse`/`append_forward`）用各 Task Run 行内嵌的生产 worktree 绝对路径 `/Users/fotile96/Zndnovel-prod/tools/…`，其余工具（`lane_setup`/`gen_plan`/`saturation`/`resolve`）与全部 git 操作用主仓 `uv run python tools/<x>.py`（详见「段开场自检」）；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `pilot/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 本段固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 10`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（Step 5）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。


## 车道配置（本计划专属，派发时逐字遵守）

| 项 | 值 |
|---|---|
| lane | opus |
| lane_dir | pilot/lanes/opus |
| model | opus |
| effort | max |
| append_model_id | claude-opus-5 |

- **派发只能走 Workflow 的 `agent(prompt, {"model": "opus", "effort": "max"})`**——`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档，使该批次失去可比性。任何一次重试都必须重新读取本表。
- **隔离纪律**：禁止读取、列出 `pilot/lanes/` 下除 `opus` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `pilot/lanes/opus/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：本段进行中提案只追加进 `pilot/lanes/opus/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `pilot/lanes/opus/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。
---



## 段开场自检（P3 生产会话必做，缺一不可）

本计划属于检查段 **seg4-s3tail-s5**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

1. **cwd 与工具树划分**（本节全部命令、以及本计划的全部 git 操作，一律在**主仓**执行，cwd 恒为主仓，**不要 `cd` 到生产 worktree**）：
   - 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` 走**生产 worktree 的绝对路径**——各批 Task 的 Run 行已内嵌 `/Users/fotile96/Zndnovel-prod/tools/…`，逐字照抄，不要改回相对形态；
   - `lane_setup` / `gen_plan` / `saturation` / `resolve` 与全部 git 操作走**主仓 `tools/`**（它们不参与段内冻结语义；lane_setup 在生产树里会因 `__file__` 推出的车道根为空而必然报「冻结文件缺失」，git 也会因主仓路径 outside repository 而失败）。
2. **工具树版本**：`git -C /Users/fotile96/Zndnovel-prod describe --tags` 应等于 runbook「当前生产 tag」行记录的值。
3. **车道冻结**（本命令在主仓执行）：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
4. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。

### Task 1: 会话组 批次 118, 119, 120（3 批 / 84 条 / 约 1919 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 84 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 118, 119, 120（章别 crd/s3s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 118 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 119 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 120 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 118 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 118, 119, 120 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 118, 119, 120、以及「首批 118 读全量 `pilot/lanes/opus/work/ctx/batch_118/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_119/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_120/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.118: 批次 118 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 118 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 118 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 118 --lane-dir pilot/lanes/opus`
Expected: `batch_118: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_118.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 118 --lane-dir pilot/lanes/opus`
Expected: `batch_118: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_118.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 118 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次118 译文入线"
```

- [ ] **Step 3.119: 批次 119 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 119 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 119 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 119 --lane-dir pilot/lanes/opus`
Expected: `batch_119: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_119.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 119 --lane-dir pilot/lanes/opus`
Expected: `batch_119: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_119.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 119 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3s 批次119 译文入线"
```

- [ ] **Step 3.120: 批次 120 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 120 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 120 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 120 --lane-dir pilot/lanes/opus`
Expected: `batch_120: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_120.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 120 --lane-dir pilot/lanes/opus`
Expected: `batch_120: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_120.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 120 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次120 译文入线"
```

### Task 2: 会话组 批次 121, 122（2 批 / 265 条 / 约 6392 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 265 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 121, 122（章别 crd/s3fb）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 2 批**，不是 2 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 121 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 122 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 121 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 121, 122 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 2 批**

注入：车道根、批次序列 121, 122、以及「首批 121 读全量 `pilot/lanes/opus/work/ctx/batch_121/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_122/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.121: 批次 121 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 121 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 121 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 121 --lane-dir pilot/lanes/opus`
Expected: `batch_121: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_121.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 121 --lane-dir pilot/lanes/opus`
Expected: `batch_121: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_121.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 121 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3fb 批次121 译文入线"
```

- [ ] **Step 3.122: 批次 122 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 122 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 122 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 122 --lane-dir pilot/lanes/opus`
Expected: `batch_122: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_122.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 122 --lane-dir pilot/lanes/opus`
Expected: `batch_122: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_122.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 122 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次122 译文入线"
```

### Task 3: CHECKPOINT——批次 118–122 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3fb、s3s 章批次 118–122 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3fb.md`、`s3s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 118–122 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 4: s3fc 批次 123 译文入库（281 条，约 8064 日文字）

**Files:**
- Produces: `pilot/lanes/opus/work/ctx/batch_123/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/opus/work/out/batch_123.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/opus/data/forward.jsonl` 追加本批 281 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 123 批（`lane=main chapter=s3fc`，281 条 id）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 123 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: 生成 `pilot/lanes/opus/work/ctx/batch_123/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 123，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/opus/work/out/batch_123.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 123 --lane-dir pilot/lanes/opus`
Expected: `batch_123: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_123.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 123 --lane-dir pilot/lanes/opus`
Expected: `batch_123: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/opus/work/out/batch_123.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 123 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s3fc 批次123 译文入线"
```

### Task 5: 会话组 批次 124, 125, 126（3 批 / 258 条 / 约 7359 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 258 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 124, 125, 126（章别 crd/s5s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 124 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 125 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 126 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 124 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 124, 125, 126 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 124, 125, 126、以及「首批 124 读全量 `pilot/lanes/opus/work/ctx/batch_124/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_125/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_126/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.124: 批次 124 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 124 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 124 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 124 --lane-dir pilot/lanes/opus`
Expected: `batch_124: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_124.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 124 --lane-dir pilot/lanes/opus`
Expected: `batch_124: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_124.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 124 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次124 译文入线"
```

- [ ] **Step 3.125: 批次 125 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 125 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 125 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 125 --lane-dir pilot/lanes/opus`
Expected: `batch_125: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_125.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 125 --lane-dir pilot/lanes/opus`
Expected: `batch_125: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_125.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 125 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次125 译文入线"
```

- [ ] **Step 3.126: 批次 126 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 126 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 126 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 126 --lane-dir pilot/lanes/opus`
Expected: `batch_126: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_126.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 126 --lane-dir pilot/lanes/opus`
Expected: `batch_126: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_126.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 126 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次126 译文入线"
```

### Task 6: 会话组 批次 127, 128, 129（3 批 / 248 条 / 约 6584 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 248 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 127, 128, 129（章别 crd/s5s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 127 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 128 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 129 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 127 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 127, 128, 129 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 127, 128, 129、以及「首批 127 读全量 `pilot/lanes/opus/work/ctx/batch_127/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_128/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_129/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.127: 批次 127 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 127 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 127 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 127 --lane-dir pilot/lanes/opus`
Expected: `batch_127: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_127.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 127 --lane-dir pilot/lanes/opus`
Expected: `batch_127: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_127.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 127 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次127 译文入线"
```

- [ ] **Step 3.128: 批次 128 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 128 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 128 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 128 --lane-dir pilot/lanes/opus`
Expected: `batch_128: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_128.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 128 --lane-dir pilot/lanes/opus`
Expected: `batch_128: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_128.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 128 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次128 译文入线"
```

- [ ] **Step 3.129: 批次 129 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 129 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 129 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 129 --lane-dir pilot/lanes/opus`
Expected: `batch_129: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_129.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 129 --lane-dir pilot/lanes/opus`
Expected: `batch_129: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_129.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 129 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次129 译文入线"
```

### Task 7: CHECKPOINT——批次 123–129 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s3fc、s5s 章批次 123–129 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s3fc.md`、`s5s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 123–129 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 8: 会话组 批次 130, 131, 132, 133（4 批 / 289 条 / 约 6606 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 289 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 130, 131, 132, 133（章别 s5s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 4 批**，不是 4 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 130 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 131 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 132 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 133 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 130 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 130, 131, 132, 133 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 4 批**

注入：车道根、批次序列 130, 131, 132, 133、以及「首批 130 读全量 `pilot/lanes/opus/work/ctx/batch_130/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_131/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_132/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_133/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.130: 批次 130 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 130 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 130 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 130 --lane-dir pilot/lanes/opus`
Expected: `batch_130: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_130.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 130 --lane-dir pilot/lanes/opus`
Expected: `batch_130: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_130.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 130 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次130 译文入线"
```

- [ ] **Step 3.131: 批次 131 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 131 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 131 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 131 --lane-dir pilot/lanes/opus`
Expected: `batch_131: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_131.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 131 --lane-dir pilot/lanes/opus`
Expected: `batch_131: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_131.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 131 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次131 译文入线"
```

- [ ] **Step 3.132: 批次 132 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 132 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 132 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 132 --lane-dir pilot/lanes/opus`
Expected: `batch_132: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_132.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 132 --lane-dir pilot/lanes/opus`
Expected: `batch_132: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_132.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 132 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次132 译文入线"
```

- [ ] **Step 3.133: 批次 133 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 133 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 133 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 133 --lane-dir pilot/lanes/opus`
Expected: `batch_133: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_133.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 133 --lane-dir pilot/lanes/opus`
Expected: `batch_133: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_133.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 133 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次133 译文入线"
```

### Task 9: 会话组 批次 134, 135, 136（3 批 / 173 条 / 约 3954 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 173 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 134, 135, 136（章别 crd/s5s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 134 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 135 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 136 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 134 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 134, 135, 136 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 134, 135, 136、以及「首批 134 读全量 `pilot/lanes/opus/work/ctx/batch_134/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_135/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_136/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.134: 批次 134 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 134 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 134 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 134 --lane-dir pilot/lanes/opus`
Expected: `batch_134: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_134.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 134 --lane-dir pilot/lanes/opus`
Expected: `batch_134: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_134.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 134 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次134 译文入线"
```

- [ ] **Step 3.135: 批次 135 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 135 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 135 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 135 --lane-dir pilot/lanes/opus`
Expected: `batch_135: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_135.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 135 --lane-dir pilot/lanes/opus`
Expected: `batch_135: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_135.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 135 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5s 批次135 译文入线"
```

- [ ] **Step 3.136: 批次 136 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 136 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 136 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 136 --lane-dir pilot/lanes/opus`
Expected: `batch_136: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_136.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 136 --lane-dir pilot/lanes/opus`
Expected: `batch_136: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_136.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 136 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次136 译文入线"
```

### Task 10: CHECKPOINT——批次 130–136 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s5s 章批次 130–136 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s5s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 130–136 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 11: 会话组 批次 137, 138（2 批 / 240 条 / 约 6421 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 240 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 137, 138（章别 crd/s5f）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 2 批**，不是 2 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 137 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 138 --profile cc --baseline none --repo pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 137 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 137, 138 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 2 批**

注入：车道根、批次序列 137, 138、以及「首批 137 读全量 `pilot/lanes/opus/work/ctx/batch_137/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_138/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.137: 批次 137 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 137 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 137 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 137 --lane-dir pilot/lanes/opus`
Expected: `batch_137: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_137.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 137 --lane-dir pilot/lanes/opus`
Expected: `batch_137: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_137.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 137 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s5f 批次137 译文入线"
```

- [ ] **Step 3.138: 批次 138 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 138 --profile cc --baseline none --repo pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 138 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 138 --lane-dir pilot/lanes/opus`
Expected: `batch_138: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_138.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 138 --lane-dir pilot/lanes/opus`
Expected: `batch_138: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_138.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 138 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 10`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次138 译文入线"
```

### Task 12: 段末——梗概回译自检 + 人工评审 gate

crd、s3fb、s3fc、s3s、s5f、s5s 章 main 车道全部 21 个批次（118–138）已入库 `pilot/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s3fb、s3fc、s3s、s5f、s5s 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `pilot/lanes/opus/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 21 个 `data: <chapter> 批次N 译文入线` commit（批号 118–138，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。



## 段末流程（本段全部批次入线后执行，缺一不可）

以下命令与 git 操作全部在**主仓**执行（cwd 恒为主仓，工具用主仓 `tools/`）。本清单与 `docs/ops/p3-production-runbook.md` §5 逐项对齐。

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. （tag 前，可选但强烈建议）跑**彩野测试**作额外验收：`uv run python tools/ayano_test.py --segment seg4-s3tail-s5 --qa config/ayano_qa/seg4-s3tail-s5.yaml --lane-dir pilot/lanes/opus`（零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，`config/ayano_qa/seg4-s3tail-s5.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过即记进段末台账，不必人工先 `ls` 探路径。**不得拿别段的题库顶替**——题库自带 `segment` 绑定，段名不符工具会直接报错退出（rc=1）；上一段的题目其答案往往整张躺在本段前缀卡里，跑出来必是恒绿假信号）。报告落 `work/out/ayano-seg4-s3tail-s5.md`，判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。
4. 打段完成 tag：`git tag prod-opus-seg4-s3tail-s5-done`。
5. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-seg4-s3tail-s5.md` 把本段提案按词族聚成卷宗，再对可裁词族跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`（**`--data-dir` 必须带**——漏传会读仓库根 `data/`，那里没有车道 forward.jsonl，结果是一张全列「滚存」的合理假表；工具会在表头前打印 `done=N 条已入线译文`，N 为 0 即说明漏传），可裁决词族当场裁，滚存词族聚类归档（runbook §5「裁决会话清单」）。裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。