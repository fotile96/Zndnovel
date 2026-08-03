# seg3-s4（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 seg3-s4 段（lane=main）的全部 19 个批次逐批译出、校验、入库到 `pilot/lanes/opus/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 4 个真实章别：crd、s4fa、s4fb、s4s。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；段末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- **cwd 恒为主仓**；按批四件套（`build_context`/`check_batch`/`detect_collapse`/`append_forward`）用各 Task Run 行内嵌的生产 worktree 绝对路径 `/Users/fotile96/Zndnovel-prod/tools/…`，其余工具（`lane_setup`/`gen_plan`/`saturation`/`resolve`）与全部 git 操作用主仓 `uv run python tools/<x>.py`（详见「段开场自检」）；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `pilot/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 本段固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 9`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
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

本计划属于检查段 **seg3-s4**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

> ⚠ **本计划仅覆盖 seg3-s4 的子区间 99–117**（`--batches` 限定，断点续跑用）。本段其余批次不在本计划内；段末流程只在**整段**批次全部入线后才执行。

1. **cwd 与工具树划分**（本节全部命令、以及本计划的全部 git 操作，一律在**主仓**执行，cwd 恒为主仓，**不要 `cd` 到生产 worktree**）：
   - 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` 走**生产 worktree 的绝对路径**——各批 Task 的 Run 行已内嵌 `/Users/fotile96/Zndnovel-prod/tools/…`，逐字照抄，不要改回相对形态；
   - `lane_setup` / `gen_plan` / `saturation` / `resolve` 与全部 git 操作走**主仓 `tools/`**（它们不参与段内冻结语义；lane_setup 在生产树里会因 `__file__` 推出的车道根为空而必然报「冻结文件缺失」，git 也会因主仓路径 outside repository 而失败）。
2. **工具树版本**：`git -C /Users/fotile96/Zndnovel-prod describe --tags` 应等于 runbook「当前生产 tag」行记录的值。
3. **车道冻结**（本命令在主仓执行）：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
4. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。

### Task 1: 会话组 批次 99, 100, 101, 102, 103, 104, 105, 106, 107, 108（10 批 / 575 条 / 约 13282 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 575 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 99, 100, 101, 102, 103, 104, 105, 106, 107, 108（章别 crd/s4s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 10 批**，不是 10 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 99 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 100 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 101 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 102 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 103 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 104 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 105 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 106 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 107 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 108 --profile cc --baseline none --repo pilot/lanes/opus`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`；记下每批 `manifest.json` 的 `ctx_sha`（入库要用）。

**开工前硬检查**：确认 99, 100, 101, 102, 103, 104, 105, 106, 107, 108 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 10 批**

注入：车道根、批次序列 99, 100, 101, 102, 103, 104, 105, 106, 107, 108、以及「首批 99 读全量 `pilot/lanes/opus/work/ctx/batch_99/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_100/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_101/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_102/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_103/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_104/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_105/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_106/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_107/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_108/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.99: 批次 99 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 99 --lane-dir pilot/lanes/opus`
Expected: `batch_99: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_99.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 99 --lane-dir pilot/lanes/opus`
Expected: `batch_99: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_99.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 99 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次99 译文入线"
```

- [ ] **Step 3.100: 批次 100 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 100 --lane-dir pilot/lanes/opus`
Expected: `batch_100: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_100.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 100 --lane-dir pilot/lanes/opus`
Expected: `batch_100: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_100.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 100 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次100 译文入线"
```

- [ ] **Step 3.101: 批次 101 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 101 --lane-dir pilot/lanes/opus`
Expected: `batch_101: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_101.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 101 --lane-dir pilot/lanes/opus`
Expected: `batch_101: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_101.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 101 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次101 译文入线"
```

- [ ] **Step 3.102: 批次 102 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 102 --lane-dir pilot/lanes/opus`
Expected: `batch_102: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_102.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 102 --lane-dir pilot/lanes/opus`
Expected: `batch_102: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_102.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 102 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次102 译文入线"
```

- [ ] **Step 3.103: 批次 103 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 103 --lane-dir pilot/lanes/opus`
Expected: `batch_103: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_103.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 103 --lane-dir pilot/lanes/opus`
Expected: `batch_103: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_103.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 103 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次103 译文入线"
```

- [ ] **Step 3.104: 批次 104 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 104 --lane-dir pilot/lanes/opus`
Expected: `batch_104: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_104.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 104 --lane-dir pilot/lanes/opus`
Expected: `batch_104: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_104.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 104 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次104 译文入线"
```

- [ ] **Step 3.105: 批次 105 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 105 --lane-dir pilot/lanes/opus`
Expected: `batch_105: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_105.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 105 --lane-dir pilot/lanes/opus`
Expected: `batch_105: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_105.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 105 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次105 译文入线"
```

- [ ] **Step 3.106: 批次 106 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 106 --lane-dir pilot/lanes/opus`
Expected: `batch_106: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_106.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 106 --lane-dir pilot/lanes/opus`
Expected: `batch_106: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_106.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 106 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次106 译文入线"
```

- [ ] **Step 3.107: 批次 107 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 107 --lane-dir pilot/lanes/opus`
Expected: `batch_107: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_107.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 107 --lane-dir pilot/lanes/opus`
Expected: `batch_107: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_107.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 107 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次107 译文入线"
```

- [ ] **Step 3.108: 批次 108 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 108 --lane-dir pilot/lanes/opus`
Expected: `batch_108: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_108.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 108 --lane-dir pilot/lanes/opus`
Expected: `batch_108: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_108.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 108 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次108 译文入线"
```

### Task 2: CHECKPOINT——批次 99–108 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4s 章批次 99–108 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 99–108 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 3: 会话组 批次 109, 110, 111（3 批 / 494 条 / 约 12365 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 494 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 109, 110, 111（章别 crd/s4fa/s4s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 109 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 110 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 111 --profile cc --baseline none --repo pilot/lanes/opus`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`；记下每批 `manifest.json` 的 `ctx_sha`（入库要用）。

**开工前硬检查**：确认 109, 110, 111 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 109, 110, 111、以及「首批 109 读全量 `pilot/lanes/opus/work/ctx/batch_109/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_110/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_111/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.109: 批次 109 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 109 --lane-dir pilot/lanes/opus`
Expected: `batch_109: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_109.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 109 --lane-dir pilot/lanes/opus`
Expected: `batch_109: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_109.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 109 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次109 译文入线"
```

- [ ] **Step 3.110: 批次 110 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 110 --lane-dir pilot/lanes/opus`
Expected: `batch_110: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_110.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 110 --lane-dir pilot/lanes/opus`
Expected: `batch_110: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_110.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 110 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次110 译文入线"
```

- [ ] **Step 3.111: 批次 111 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 111 --lane-dir pilot/lanes/opus`
Expected: `batch_111: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_111.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 111 --lane-dir pilot/lanes/opus`
Expected: `batch_111: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_111.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 111 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fa 批次111 译文入线"
```

### Task 4: 会话组 批次 112, 113, 114（3 批 / 530 条 / 约 12378 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 530 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 112, 113, 114（章别 crd/s4fa/s4s）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 112 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 113 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 114 --profile cc --baseline none --repo pilot/lanes/opus`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`；记下每批 `manifest.json` 的 `ctx_sha`（入库要用）。

**开工前硬检查**：确认 112, 113, 114 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 112, 113, 114、以及「首批 112 读全量 `pilot/lanes/opus/work/ctx/batch_112/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_113/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_114/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.112: 批次 112 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 112 --lane-dir pilot/lanes/opus`
Expected: `batch_112: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_112.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 112 --lane-dir pilot/lanes/opus`
Expected: `batch_112: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_112.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 112 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fa 批次112 译文入线"
```

- [ ] **Step 3.113: 批次 113 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 113 --lane-dir pilot/lanes/opus`
Expected: `batch_113: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_113.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 113 --lane-dir pilot/lanes/opus`
Expected: `batch_113: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_113.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 113 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4s 批次113 译文入线"
```

- [ ] **Step 3.114: 批次 114 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 114 --lane-dir pilot/lanes/opus`
Expected: `batch_114: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_114.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 114 --lane-dir pilot/lanes/opus`
Expected: `batch_114: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_114.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 114 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次114 译文入线"
```

### Task 5: CHECKPOINT——批次 109–114 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**（在主仓执行）

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止本段**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s4fa、s4s 章批次 109–114 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s4fa.md`、`s4s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到本计划末尾「段末流程」指向的段末小裁决会话。

- [ ] **Step 2: 抽查**

从批次 109–114 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 6: 会话组 批次 115, 116, 117（3 批 / 449 条 / 约 11023 日文字）

**Files:**
- Produces: 各批 `pilot/lanes/opus/work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`、`pilot/lanes/opus/work/out/batch_N.draft.jsonl`、`pilot/lanes/opus/data/forward.jsonl` 追加共 449 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 115, 116, 117（章别 crd/s4fb）
- Produces: `pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行

> **本任务是一条长对话连做 3 批**，不是 3 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**

Run（逐批执行，ctx 照常入档）：

`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 115 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 116 --profile cc --baseline none --repo pilot/lanes/opus`
`uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 117 --profile cc --baseline none --repo pilot/lanes/opus`

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`；记下每批 `manifest.json` 的 `ctx_sha`（入库要用）。

**开工前硬检查**：确认 115, 116, 117 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 3 批**

注入：车道根、批次序列 115, 116, 117、以及「首批 115 读全量 `pilot/lanes/opus/work/ctx/batch_115/context.md`，其余批只读 `pilot/lanes/opus/work/ctx/batch_116/source.jsonl`、`pilot/lanes/opus/work/ctx/batch_117/source.jsonl` + `pilot/lanes/opus/glossary/style.md` + `pilot/lanes/opus/glossary/active.json`」。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。

- [ ] **Step 3.115: 批次 115 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 115 --lane-dir pilot/lanes/opus`
Expected: `batch_115: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_115.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 115 --lane-dir pilot/lanes/opus`
Expected: `batch_115: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_115.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 115 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fb 批次115 译文入线"
```

- [ ] **Step 3.116: 批次 116 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 116 --lane-dir pilot/lanes/opus`
Expected: `batch_116: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_116.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 116 --lane-dir pilot/lanes/opus`
Expected: `batch_116: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_116.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 116 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s4fb 批次116 译文入线"
```

- [ ] **Step 3.117: 批次 117 校验与入库**

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 117 --lane-dir pilot/lanes/opus`
Expected: `batch_117: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `pilot/lanes/opus/work/out/batch_117.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py --batch 117 --lane-dir pilot/lanes/opus`
Expected: `batch_117: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `pilot/lanes/opus/work/out/batch_117.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供段末流程汇总参考。

Run: `ZND_WORK=pilot/lanes/opus/work ZND_DATA=pilot/lanes/opus/data uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py --batch 117 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 9`

```bash
git add pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次117 译文入线"
```

### Task 7: 段末——梗概回译自检 + 人工评审 gate

crd、s4fa、s4fb、s4s 章 main 车道全部 19 个批次（99–117）已入库 `pilot/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s4fa、s4fb、s4s 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `pilot/lanes/opus/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 19 个 `data: <chapter> 批次N 译文入线` commit（批号 99–117，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。



## 段末流程（本段全部批次入线后执行，缺一不可）

以下命令与 git 操作全部在**主仓**执行（cwd 恒为主仓，工具用主仓 `tools/`）。本清单与 `docs/ops/p3-production-runbook.md` §5 逐项对齐。

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. （tag 前，可选但强烈建议）跑**彩野测试**作额外验收：`uv run python tools/ayano_test.py --segment seg3-s4 --qa config/ayano_qa/seg3-s4.yaml --lane-dir pilot/lanes/opus`（零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，`config/ayano_qa/seg3-s4.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过即记进段末台账，不必人工先 `ls` 探路径。**不得拿别段的题库顶替**——题库自带 `segment` 绑定，段名不符工具会直接报错退出（rc=1）；上一段的题目其答案往往整张躺在本段前缀卡里，跑出来必是恒绿假信号）。报告落 `work/out/ayano-seg3-s4.md`，判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。
4. 打段完成 tag：`git tag prod-opus-seg3-s4-done`。
5. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-seg3-s4.md` 把本段提案按词族聚成卷宗，再对可裁词族跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`（**`--data-dir` 必须带**——漏传会读仓库根 `data/`，那里没有车道 forward.jsonl，结果是一张全列「滚存」的合理假表；工具会在表头前打印 `done=N 条已入线译文`，N 为 0 即说明漏传），可裁决词族当场裁，滚存词族聚类归档（runbook §5「裁决会话清单」）。裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。