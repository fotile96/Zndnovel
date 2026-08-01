# seg1-s2（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 seg1-s2 段（lane=main）的全部 27 个批次逐批译出、校验、入库到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 3 个真实章别：crd、s2f、s2s。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；章末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- 运行 `uv run python tools/<x>.py`；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 试点期固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 7`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
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
- **术语提案不裁决**：试点期间提案只追加进 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。
---



## 段开场自检（P3 生产会话必做，缺一不可）

本计划属于检查段 **seg1-s2**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

1. **工具树**：本会话执行的 `tools/` 必须来自生产 worktree——`git -C <生产worktree> describe --tags` 应等于 runbook 记录的当前生产 tag；主仓 main 上的工具**不得**用于生产批次。
2. **车道冻结**：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
3. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。

### Task 1: s2s 批次 36 译文入库（88 条，约 2269 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_36/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_36.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 88 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 36 批（`lane=main chapter=s2s`，88 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 36 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_36/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 36，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_36.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 36 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_36: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_36.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 36 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_36: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_36.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 36 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次36 译文入线"
```

### Task 2: 硬停——batch 1 隔离验收（不通过则停止试点）

批次 1 已入库。**在继续 batch 2 之前必须做完以下检查，任一项不通过就停止试点、报告人工，不要往下派发**：

- [ ] **① 隔离验收——两条车道确实互不可见**

Run: `diff /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl <对方车道根——/Users/fotile96/Zndnovel/pilot/lanes/ 下除 opus 外的另一条车道目录，执行时按当次试点实际车道配置填入>/data/forward.jsonl`
Expected：**有差异**（`diff` 非零退出码，即两个文件不完全相同）。若输出为空，说明两条车道读到了同一份译文，双车道对照已经退化——立即停止试点。

再 Run（仅为核验隔离而提前生成一次，产物会被下面「batch 2 译文入库」任务的 Step 1 正常覆盖，无副作用）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/build_context.py --batch 2 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`

然后核对：从 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里挑本车道 batch 1 译出的任意一行 zh 片段，`grep` 能在 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_2/context.md` 第二节「前缀正文」里找到。
Expected：能找到；找不到说明本车道下一批的前缀没有正确读到本车道自己的译文。

- [ ] **② 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。

- [ ] **③ 人工抽读**

从本车道 batch 1 的译文里抽 3–5 条对照原文通读，粗筛是否符合中文可读性/术语口调/全知纪律基本水准（正式三栏 rubric 见 spec §6.5，这里只做粗筛，不必按盲评格式）。

- [ ] **④ 门禁**

**①②③任一项不通过，立即停止试点、报告人工裁决，不要继续派发 batch 2。** 全部通过才能继续下一个任务。

### Task 3: s2s 批次 37 译文入库（64 条，约 1891 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_37/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_37.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 64 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 37 批（`lane=main chapter=s2s`，64 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 37 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_37/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 37，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_37.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 37 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_37: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_37.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 37 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_37: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_37.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 37 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次37 译文入线"
```

### Task 4: 硬停——batch 1–2 崩溃阈值标定 + 人工抽读（不通过则停止试点）

批次 1–2 已入库，两批都已跑过各自 Task 里的语义崩溃探测步骤。**在继续 batch 3 之前完成以下三项**：

- [ ] **① 用真实译文标定 detect_collapse 三个阈值**

对照 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_1.collapse.json` 与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_2.collapse.json` 的命中，结合两批真实译文，人工判断 `--kana-max`/`--ratio-lo`/`--ratio-hi` 三个阈值（默认值见 `tools/detect_collapse.py` 常量注释）是否需要针对本次试点重新标定。把最终使用值写入 `pilot/lanes/pilot-manifest.json`（保留其余键，只加/改 `collapse_thresholds` 这一段）：

```bash
uv run python -c "
import json
p = 'pilot/lanes/pilot-manifest.json'
d = json.load(open(p, encoding='utf-8'))
d['collapse_thresholds'] = {'kana_max': <值>, 'ratio_lo': <值>, 'ratio_hi': <值>}
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
"
```

若标定值与 `tools/detect_collapse.py` 默认值相同：无需其他动作，后续批次继续用当前命令行。
若不同：**必须重新生成本计划**——对本车道重跑（带上标定值；`--lane` 用本计划批次原本所属的 lane，通常是 `main`）：

`uv run python tools/gen_plan.py --lane main --batches 36-62 --label seg1-s2 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --model opus --effort max --append-model-id claude-opus-5 --kana-max <值> --ratio-lo <值> --ratio-hi <值>`

用新计划覆盖当前文件（同一 `--label` 会写回同一路径 `docs/superpowers/plans/translate-seg1-s2.md`），从 batch 3 对应的任务继续执行——新计划里 batch 3 起的 Step 4 检测命令会带上标定值。**batch 1、2 已入库的译文不受影响**（`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 是 append-only 正向线，重出计划不会动它）。

- [ ] **② 人工抽读**

同 batch 1 硬停的抽读粒度，这次对 batch 2 抽 3–5 条。

- [ ] **③ 崩溃探测命中逐条过目**

`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_1.collapse.json` 与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_2.collapse.json` 里的每一条命中（不论 C1/C2/C3）都要人眼确认是误报还是真崩溃；真崩溃需回对应批次的 Step 2 重新出译文、重跑 Step 3–4。

- [ ] **④ 门禁**

**①②③任一项发现真实问题且未处理，立即停止试点、报告人工裁决。** 全部通过才能继续下一个任务。

### Task 5: crd 批次 38 译文入库（75 条，约 2164 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_38/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_38.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 75 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 38 批（`lane=main chapter=crd`，75 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 38 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_38/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 38，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_38.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 38 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_38: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_38.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 38 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_38: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_38.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 38 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次38 译文入线"
```

### Task 6: s2s 批次 39 译文入库（16 条，约 505 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_39/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_39.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 16 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 39 批（`lane=main chapter=s2s`，16 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 39 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_39/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 39，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_39.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 39 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_39: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_39.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 39 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_39: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_39.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 39 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次39 译文入线"
```

### Task 7: s2s 批次 40 译文入库（81 条，约 2213 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_40/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_40.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 81 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 40 批（`lane=main chapter=s2s`，81 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 40 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_40/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 40，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_40.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 40 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_40: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_40.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 40 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_40: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_40.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 40 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次40 译文入线"
```

### Task 8: CHECKPOINT——批次 36–40 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s2s 章批次 36–40 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 36–40 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 9: s2s 批次 41 译文入库（28 条，约 597 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_41/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_41.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 28 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 41 批（`lane=main chapter=s2s`，28 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 41 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_41/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 41，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_41.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 41 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_41: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_41.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 41 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_41: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_41.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 41 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次41 译文入线"
```

### Task 10: crd 批次 42 译文入库（101 条，约 2786 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_42/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_42.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 101 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 42 批（`lane=main chapter=crd`，101 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 42 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_42/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 42，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_42.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 42 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_42: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_42.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 42 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_42: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_42.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 42 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次42 译文入线"
```

### Task 11: s2s 批次 43 译文入库（5 条，约 123 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_43/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_43.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 5 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 43 批（`lane=main chapter=s2s`，5 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 43 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_43/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 43，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_43.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 43 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_43: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_43.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 43 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_43: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_43.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 43 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次43 译文入线"
```

### Task 12: crd 批次 44 译文入库（7 条，约 214 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_44/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_44.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 7 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 44 批（`lane=main chapter=crd`，7 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 44 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_44/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 44，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_44.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 44 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_44: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_44.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 44 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_44: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_44.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 44 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次44 译文入线"
```

### Task 13: s2s 批次 45 译文入库（103 条，约 2790 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_45/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_45.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 103 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 45 批（`lane=main chapter=s2s`，103 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 45 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_45/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 45，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_45.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 45 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_45: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_45.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 45 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_45: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_45.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 45 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次45 译文入线"
```

### Task 14: CHECKPOINT——批次 41–45 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s2s 章批次 41–45 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 41–45 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 15: s2s 批次 46 译文入库（32 条，约 831 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_46/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_46.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 32 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 46 批（`lane=main chapter=s2s`，32 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 46 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_46/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 46，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_46.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 46 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_46: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_46.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 46 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_46: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_46.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 46 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次46 译文入线"
```

### Task 16: s2s 批次 47 译文入库（158 条，约 3684 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_47/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_47.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 158 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 47 批（`lane=main chapter=s2s`，158 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 47 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_47/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 47，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_47.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 47 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_47: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_47.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 47 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_47: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_47.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 47 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次47 译文入线"
```

### Task 17: crd 批次 48 译文入库（76 条，约 2217 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_48/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_48.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 76 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 48 批（`lane=main chapter=crd`，76 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 48 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_48/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 48，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_48.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 48 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_48: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_48.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 48 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_48: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_48.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 48 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次48 译文入线"
```

### Task 18: s2s 批次 49 译文入库（31 条，约 879 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_49/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_49.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 31 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 49 批（`lane=main chapter=s2s`，31 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 49 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_49/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 49，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_49.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 49 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_49: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_49.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 49 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_49: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_49.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 49 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次49 译文入线"
```

### Task 19: s2s 批次 50 译文入库（64 条，约 1574 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_50/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_50.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 64 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 50 批（`lane=main chapter=s2s`，64 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 50 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_50/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 50，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_50.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 50 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_50: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_50.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 50 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_50: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_50.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 50 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次50 译文入线"
```

### Task 20: CHECKPOINT——批次 46–50 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s2s 章批次 46–50 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 46–50 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 21: crd 批次 51 译文入库（71 条，约 1666 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_51/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_51.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 71 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 51 批（`lane=main chapter=crd`，71 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 51 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_51/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 51，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_51.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 51 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_51: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_51.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 51 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_51: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_51.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 51 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次51 译文入线"
```

### Task 22: s2s 批次 52 译文入库（2 条，约 54 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_52/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_52.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 2 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 52 批（`lane=main chapter=s2s`，2 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 52 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_52/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 52，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_52.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 52 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_52: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_52.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 52 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_52: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_52.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 52 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次52 译文入线"
```

### Task 23: crd 批次 53 译文入库（43 条，约 1089 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_53/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_53.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 43 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 53 批（`lane=main chapter=crd`，43 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 53 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_53/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 53，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_53.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 53 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_53: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_53.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 53 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_53: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_53.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 53 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次53 译文入线"
```

### Task 24: s2s 批次 54 译文入库（3 条，约 62 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_54/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_54.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 3 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 54 批（`lane=main chapter=s2s`，3 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 54 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_54/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 54，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_54.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 54 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_54: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_54.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 54 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_54: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_54.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 54 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次54 译文入线"
```

### Task 25: crd 批次 55 译文入库（8 条，约 292 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_55/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_55.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 8 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 55 批（`lane=main chapter=crd`，8 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 55 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_55/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 55，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_55.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 55 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_55: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_55.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 55 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_55: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_55.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 55 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次55 译文入线"
```

### Task 26: CHECKPOINT——批次 51–55 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s2s 章批次 51–55 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 51–55 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 27: s2s 批次 56 译文入库（233 条，约 5285 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_56/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_56.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 233 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 56 批（`lane=main chapter=s2s`，233 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 56 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_56/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 56，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_56.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 56 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_56: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_56.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 56 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_56: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_56.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 56 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次56 译文入线"
```

### Task 28: crd 批次 57 译文入库（138 条，约 4385 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_57/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_57.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 138 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 57 批（`lane=main chapter=crd`，138 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 57 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_57/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 57，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_57.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 57 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_57: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_57.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 57 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_57: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_57.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 57 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次57 译文入线"
```

### Task 29: s2f 批次 58 译文入库（326 条，约 8990 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_58/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_58.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 326 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 58 批（`lane=main chapter=s2f`，326 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 58 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_58/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 58，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_58.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 58 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_58: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_58.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 58 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_58: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_58.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 58 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2f 批次58 译文入线"
```

### Task 30: s2f 批次 59 译文入库（103 条，约 2796 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_59/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_59.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 103 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 59 批（`lane=main chapter=s2f`，103 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 59 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_59/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 59，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_59.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 59 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_59: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_59.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 59 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_59: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_59.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 59 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2f 批次59 译文入线"
```

### Task 31: s2s 批次 60 译文入库（8 条，约 175 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_60/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_60.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 8 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 60 批（`lane=main chapter=s2s`，8 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 60 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_60/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 60，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_60.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 60 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_60: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_60.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 60 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_60: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_60.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 60 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次60 译文入线"
```

### Task 32: CHECKPOINT——批次 56–60 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s2f、s2s 章批次 56–60 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/notes/` 下本段涉及的 `crd.md`、`s2f.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 56–60 已入库的译文里随机抽 2–3 条，对照对应 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_*/source.jsonl` 的原文与 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`——它是 append-only 正向线）。

### Task 33: s2s 批次 61 译文入库（57 条，约 1638 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_61/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_61.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 57 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 61 批（`lane=main chapter=s2s`，57 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 61 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_61/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 61，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_61.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 61 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_61: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_61.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 61 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_61: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_61.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 61 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: s2s 批次61 译文入线"
```

### Task 34: crd 批次 62 译文入库（75 条，约 2014 日文字）

**Files:**
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_62/{context.md,source.jsonl,manifest.json}`（Step 1）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_62.draft.jsonl`（Step 2 产出、Step 3 校验）、`/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 追加本批 75 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 62 批（`lane=main chapter=crd`，75 条 id）
- Produces: `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 62 --profile cc --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: 生成 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/ctx/batch_62/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 62，并按本计划头部「车道配置」注入车道根），产出 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_62.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/check_batch.py --batch 62 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_62: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_62.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/detect_collapse.py --batch 62 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus`
Expected: `batch_62: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `/Users/fotile96/Zndnovel/pilot/lanes/opus/work/out/batch_62.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=/Users/fotile96/Zndnovel/pilot/lanes/opus/work ZND_DATA=/Users/fotile96/Zndnovel/pilot/lanes/opus/data uv run python tools/append_forward.py --batch 62 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 7`

```bash
git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
git commit -m "data: crd 批次62 译文入线"
```

### Task 35: 章末——梗概回译自检 + 人工评审 gate

crd、s2f、s2s 章 main 车道全部 27 个批次（36–62）已入库 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s2f、s2s 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 27 个 `data: <chapter> 批次N 译文入线` commit（批号 36–62，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。



## 段末流程（本段全部批次入线后执行，缺一不可）

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. 打段完成 tag：`git tag prod-opus-seg1-s2-done`。
4. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`，可裁决词族当场裁，滚存词族聚类归档（runbook「段末小裁决」节）。
5. 裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。