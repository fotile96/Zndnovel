# seg5-s6-s7f（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 seg5-s6-s7f 段（lane=main）的全部 16 个批次逐批译出、校验、入库到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 4 个真实章别：crd、s6f、s6s、s7f。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；段末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- **cwd 恒为主仓**；按批四件套（`build_context`/`check_batch`/`detect_collapse`/`append_forward`）用各 Task Run 行内嵌的生产 worktree 绝对路径 `/Users/fotile96/Zndnovel-prod/tools/…`，其余工具（`lane_setup`/`gen_plan`/`saturation`/`resolve`）与全部 git 操作用主仓 `uv run python tools/<x>.py`（详见「段开场自检」）；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 本段固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 11`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
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

本计划属于检查段 **seg5-s6-s7f**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

1. **cwd 与工具树划分**（本节全部命令、以及本计划的全部 git 操作，一律在**主仓**执行，cwd 恒为主仓，**不要 `cd` 到生产 worktree**）：
   - 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` 走**生产 worktree 的绝对路径**——各批 Task 的 Run 行已内嵌 `/Users/fotile96/Zndnovel-prod/tools/…`，逐字照抄，不要改回相对形态；
   - `lane_setup` / `gen_plan` / `saturation` / `resolve` 与全部 git 操作走**主仓 `tools/`**（它们不参与段内冻结语义；lane_setup 在生产树里会因 `__file__` 推出的车道根为空而必然报「冻结文件缺失」，git 也会因主仓路径 outside repository 而失败）。
2. **工具树版本**：`git -C /Users/fotile96/Zndnovel-prod describe --tags` 应等于 runbook「当前生产 tag」行记录的值。
3. **车道冻结**（本命令在主仓执行）：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
4. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。

### Task 1: 会话组 批次 139, 140, 141, 142, 143, 144, 145, 146, 147, 148（10 批 / 536 条 / 约 12260 日文字）

**Files:**
- Produces: 各批 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加共 536 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 139, 140, 141, 142, 143, 144, 145, 146, 147, 148（章别 crd/s6s）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 10 批**，不是 10 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 139 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 140 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 141 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 142 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 143 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 144 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 145 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 146 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 147 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 148 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 139 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 139, 140, 141, 142, 143, 144, 145, 146, 147, 148 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 10 批**

注入：车道根、批次序列 139, 140, 141, 142, 143, 144, 145, 146, 147, 148、以及「首批 139 读全量 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_139/context.md`，其余批只读 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_140/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_141/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_142/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_143/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_144/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_145/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_146/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_147/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_148/source.jsonl` + `/Users/fotile96/Zndnovel/pilot/lanes/opus/glossary/style.md` + `/Users/fotile96/Zndnovel/pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.139: 批次 139 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 139 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 139 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 139 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_139: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_139.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 139 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_139: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_139.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 139 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次139 译文入线"
```

- [ ] **Step 3.140: 批次 140 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 140 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 140 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 140 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_140: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_140.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 140 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_140: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_140.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 140 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次140 译文入线"
```

- [ ] **Step 3.141: 批次 141 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 141 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 141 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 141 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_141: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_141.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 141 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_141: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_141.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 141 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次141 译文入线"
```

- [ ] **Step 3.142: 批次 142 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 142 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 142 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 142 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_142: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_142.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 142 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_142: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_142.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 142 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次142 译文入线"
```

- [ ] **Step 3.143: 批次 143 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 143 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 143 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 143 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_143: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_143.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 143 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_143: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_143.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 143 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次143 译文入线"
```

- [ ] **Step 3.144: 批次 144 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 144 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 144 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 144 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_144: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_144.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 144 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_144: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_144.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 144 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次144 译文入线"
```

- [ ] **Step 3.145: 批次 145 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 145 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 145 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 145 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_145: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_145.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 145 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_145: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_145.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 145 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次145 译文入线"
```

- [ ] **Step 3.146: 批次 146 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 146 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 146 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 146 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_146: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_146.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 146 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_146: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_146.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 146 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次146 译文入线"
```

- [ ] **Step 3.147: 批次 147 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 147 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 147 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 147 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_147: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_147.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 147 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_147: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_147.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 147 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次147 译文入线"
```

- [ ] **Step 3.148: 批次 148 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 148 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 148 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 148 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_148: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_148.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 148 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_148: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_148.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 148 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6s 批次148 译文入线"
```

### Task 2: CHECKPOINT——批次 139–148 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s6s 章批次 139–148 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s6s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 139–148 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 3: 会话组 批次 149, 150, 151（3 批 / 306 条 / 约 7871 日文字）

**Files:**
- Produces: 各批 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加共 306 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 149, 150, 151（章别 crd/s6f）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 149 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 150 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 151 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 149 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 149, 150, 151 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 149, 150, 151、以及「首批 149 读全量 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_149/context.md`，其余批只读 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_150/source.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_151/source.jsonl` + `/Users/fotile96/Zndnovel/pilot/lanes/opus/glossary/style.md` + `/Users/fotile96/Zndnovel/pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.149: 批次 149 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 149 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 149 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 149 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_149: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_149.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 149 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_149: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_149.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 149 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次149 译文入线"
```

- [ ] **Step 3.150: 批次 150 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 150 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 150 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 150 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_150: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_150.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 150 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_150: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_150.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 150 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s6f 批次150 译文入线"
```

- [ ] **Step 3.151: 批次 151 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 151 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 151 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 151 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_151: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_151.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 151 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_151: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_151.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 151 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次151 译文入线"
```

### Task 4: s7f 批次 152 译文入库（377 条，约 9000 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_152/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_152.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 377 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 152 批（`lane=main chapter=s7f`，377 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 152 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_152/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 152，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_152.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 152 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_152: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_152.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 152 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_152: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_152.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/段末流程汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 152 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s7f 批次152 译文入线"
```

### Task 5: 会话组 批次 153, 154（2 批 / 286 条 / 约 7636 日文字）

**Files:**
- Produces: 各批 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加共 286 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 153, 154（章别 crd/s7f）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 2 批**，不是 2 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 153 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 154 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus --jp-fallback`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 153 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 153, 154 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 2 批**

注入：车道根、批次序列 153, 154、以及「首批 153 读全量 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_153/context.md`，其余批只读 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_154/source.jsonl` + `/Users/fotile96/Zndnovel/pilot/lanes/opus/glossary/style.md` + `/Users/fotile96/Zndnovel/pilot/lanes/opus/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.153: 批次 153 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 153 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 153 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），照跑即可——每批同形，免得临场判断哪批该跑。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 153 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_153: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_153.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 153 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_153: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_153.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 153 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s7f 批次153 译文入线"
```

- [ ] **Step 3.154: 批次 154 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 154 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 154 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 154 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_154: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_154.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 154 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_154: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_154.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 154 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 11`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次154 译文入线"
```

### Task 6: CHECKPOINT——批次 149–154 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s6f、s7f 章批次 149–154 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s6f.md`、`s7f.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 149–154 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 7: 段末——梗概回译自检 + 人工评审 gate

crd、s6f、s6s、s7f 章 main 车道全部 16 个批次（139–154）已入库 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s6f、s6s、s7f 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 16 个 `data: <chapter> 批次N 译文入线` commit（批号 139–154，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。



## 段末流程（本段全部批次入线后执行，缺一不可）

以下命令与 git 操作全部在**主仓**执行（cwd 恒为主仓，工具用主仓 `tools/`）。本清单与 `docs/ops/p3-production-runbook.md` §5 逐项对齐。

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. （tag 前，可选但强烈建议）跑**彩野测试**作额外验收：`uv run python tools/ayano_test.py --segment seg5-s6-s7f --qa config/ayano_qa/seg5-s6-s7f.yaml --lane-dir pilot/lanes/opus`（零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，`config/ayano_qa/seg5-s6-s7f.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过即记进段末台账，不必人工先 `ls` 探路径。**不得拿别段的题库顶替**——题库自带 `segment` 绑定，段名不符工具会直接报错退出（rc=1）；上一段的题目其答案往往整张躺在本段前缀卡里，跑出来必是恒绿假信号）。报告落 `work/out/ayano-seg5-s6-s7f.md`，判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。
4. 打段完成 tag：`git tag prod-opus-seg5-s6-s7f-done`。
5. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-seg5-s6-s7f.md` 把本段提案按词族聚成卷宗，再对可裁词族跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`（**`--data-dir` 必须带**——漏传会读仓库根 `data/`，那里没有车道 forward.jsonl，结果是一张全列「滚存」的合理假表；工具会在表头前打印 `done=N 条已入线译文`，N 为 0 即说明漏传），可裁决词族当场裁，滚存词族聚类归档（runbook §5「裁决会话清单」）。裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。