# pilot-fable（main 车道）翻译执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `data/batches.jsonl` 里 pilot-fable 段（lane=main）的全部 35 个批次逐批译出、校验、入库到 `pilot/lanes/fable/data/forward.jsonl`，段末完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段（非单一章节），横跨 6 个真实章别：crd、s0f、s1f、s1s、s2s、sys。**

**Architecture:** 每个批次一个任务，走 「build_context 生成上下文包 → 按 `prompts/translator_cc.md` 派译者子代理 → check_batch 机械校验 → detect_collapse 语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线（P1b 已建成，签名见下）；每 5 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；章末插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- 运行 `uv run python tools/<x>.py`；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `pilot/lanes/fable/data/notes/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` 试点期固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v 6`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（Step 5）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。


## 车道配置（本计划专属，派发时逐字遵守）

| 项 | 值 |
|---|---|
| lane | fable |
| lane_dir | pilot/lanes/fable |
| model | fable |
| effort | high |
| append_model_id | claude-fable-5 |

- **派发只能走 Workflow 的 `agent(prompt, {"model": "fable", "effort": "high"})`**——`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档，使该批次失去可比性。任何一次重试都必须重新读取本表。
- **隔离纪律**：禁止读取、列出 `pilot/lanes/` 下除 `fable` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `pilot/lanes/fable/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：试点期间提案只追加进 `pilot/lanes/fable/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `pilot/lanes/fable/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。
---

### Task 1: s0f 批次 1 译文入库（339 条，约 8989 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_1/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_1.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 339 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 1 批（`lane=main chapter=s0f`，339 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 1 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_1/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 1，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_1.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 1 --lane-dir pilot/lanes/fable`
Expected: `batch_1: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_1.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 1 --lane-dir pilot/lanes/fable`
Expected: `batch_1: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_1.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 1 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s0f 批次1 译文入线"
```

### Task 2: 硬停——batch 1 隔离验收（不通过则停止试点）

批次 1 已入库。**在继续 batch 2 之前必须做完以下检查，任一项不通过就停止试点、报告人工，不要往下派发**：

- [ ] **① 隔离验收——两条车道确实互不可见**

Run: `diff pilot/lanes/fable/data/forward.jsonl <对方车道根——pilot/lanes/ 下除 fable 外的另一条车道目录，执行时按当次试点实际车道配置填入>/data/forward.jsonl`
Expected：**有差异**（`diff` 非零退出码，即两个文件不完全相同）。若输出为空，说明两条车道读到了同一份译文，双车道对照已经退化——立即停止试点。

再 Run（仅为核验隔离而提前生成一次，产物会被下面「batch 2 译文入库」任务的 Step 1 正常覆盖，无副作用）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/build_context.py --batch 2 --profile cc --baseline none --repo pilot/lanes/fable`

然后核对：从 `pilot/lanes/fable/data/forward.jsonl` 里挑本车道 batch 1 译出的任意一行 zh 片段，`grep` 能在 `pilot/lanes/fable/work/ctx/batch_2/context.md` 第二节「前缀正文」里找到。
Expected：能找到；找不到说明本车道下一批的前缀没有正确读到本车道自己的译文。

- [ ] **② 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。

- [ ] **③ 人工抽读**

从本车道 batch 1 的译文里抽 3–5 条对照原文通读，粗筛是否符合中文可读性/术语口调/全知纪律基本水准（正式三栏 rubric 见 spec §6.5，这里只做粗筛，不必按盲评格式）。

- [ ] **④ 门禁**

**①②③任一项不通过，立即停止试点、报告人工裁决，不要继续派发 batch 2。** 全部通过才能继续下一个任务。

### Task 3: s0f 批次 2 译文入库（229 条，约 6069 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_2/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_2.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 229 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 2 批（`lane=main chapter=s0f`，229 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 2 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_2/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 2，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_2.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 2 --lane-dir pilot/lanes/fable`
Expected: `batch_2: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_2.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 2 --lane-dir pilot/lanes/fable`
Expected: `batch_2: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_2.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 2 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s0f 批次2 译文入线"
```

### Task 4: 硬停——batch 1–2 崩溃阈值标定 + 人工抽读（不通过则停止试点）

批次 1–2 已入库，两批都已跑过各自 Task 里的语义崩溃探测步骤。**在继续 batch 3 之前完成以下三项**：

- [ ] **① 用真实译文标定 detect_collapse 三个阈值**

对照 `pilot/lanes/fable/work/out/batch_1.collapse.json` 与 `pilot/lanes/fable/work/out/batch_2.collapse.json` 的命中，结合两批真实译文，人工判断 `--kana-max`/`--ratio-lo`/`--ratio-hi` 三个阈值（默认值见 `tools/detect_collapse.py` 常量注释）是否需要针对本次试点重新标定。把最终使用值写入 `pilot/lanes/pilot-manifest.json`（保留其余键，只加/改 `collapse_thresholds` 这一段）：

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

`uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-fable --lane-dir pilot/lanes/fable --model fable --effort high --append-model-id claude-fable-5 --kana-max <值> --ratio-lo <值> --ratio-hi <值>`

用新计划覆盖当前文件（同一 `--label` 会写回同一路径 `docs/superpowers/plans/translate-pilot-fable.md`），从 batch 3 对应的任务继续执行——新计划里 batch 3 起的 Step 4 检测命令会带上标定值。**batch 1、2 已入库的译文不受影响**（`pilot/lanes/fable/data/forward.jsonl` 是 append-only 正向线，重出计划不会动它）。

- [ ] **② 人工抽读**

同 batch 1 硬停的抽读粒度，这次对 batch 2 抽 3–5 条。

- [ ] **③ 崩溃探测命中逐条过目**

`pilot/lanes/fable/work/out/batch_1.collapse.json` 与 `pilot/lanes/fable/work/out/batch_2.collapse.json` 里的每一条命中（不论 C1/C2/C3）都要人眼确认是误报还是真崩溃；真崩溃需回对应批次的 Step 2 重新出译文、重跑 Step 3–4。

- [ ] **④ 门禁**

**①②③任一项发现真实问题且未处理，立即停止试点、报告人工裁决。** 全部通过才能继续下一个任务。

### Task 5: crd 批次 3 译文入库（1 条，约 9 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_3/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_3.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 1 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 3 批（`lane=main chapter=crd`，1 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 3 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_3/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 3，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_3.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 3 --lane-dir pilot/lanes/fable`
Expected: `batch_3: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_3.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 3 --lane-dir pilot/lanes/fable`
Expected: `batch_3: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_3.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 3 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次3 译文入线"
```

### Task 6: s1s 批次 4 译文入库（84 条，约 2180 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_4/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_4.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 84 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 4 批（`lane=main chapter=s1s`，84 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 4 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_4/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 4，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_4.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 4 --lane-dir pilot/lanes/fable`
Expected: `batch_4: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_4.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 4 --lane-dir pilot/lanes/fable`
Expected: `batch_4: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_4.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 4 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次4 译文入线"
```

### Task 7: sys 批次 5 译文入库（13 条，约 326 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_5/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_5.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 13 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 5 批（`lane=main chapter=sys`，13 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 5 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_5/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 5，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_5.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 5 --lane-dir pilot/lanes/fable`
Expected: `batch_5: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_5.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 5 --lane-dir pilot/lanes/fable`
Expected: `batch_5: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_5.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 5 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: sys 批次5 译文入线"
```

### Task 8: CHECKPOINT——批次 1–5 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s0f、s1s、sys 章批次 1–5 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s0f.md`、`s1s.md`、`sys.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 1–5 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 9: crd 批次 6 译文入库（272 条，约 6978 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_6/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_6.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 272 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 6 批（`lane=main chapter=crd`，272 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 6 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_6/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 6，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_6.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 6 --lane-dir pilot/lanes/fable`
Expected: `batch_6: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_6.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 6 --lane-dir pilot/lanes/fable`
Expected: `batch_6: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_6.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 6 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次6 译文入线"
```

### Task 10: s1s 批次 7 译文入库（90 条，约 2659 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_7/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_7.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 90 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 7 批（`lane=main chapter=s1s`，90 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 7 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_7/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 7，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_7.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 7 --lane-dir pilot/lanes/fable`
Expected: `batch_7: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_7.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 7 --lane-dir pilot/lanes/fable`
Expected: `batch_7: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_7.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 7 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次7 译文入线"
```

### Task 11: s1s 批次 8 译文入库（22 条，约 576 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_8/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_8.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 22 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 8 批（`lane=main chapter=s1s`，22 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 8 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_8/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 8，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_8.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 8 --lane-dir pilot/lanes/fable`
Expected: `batch_8: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_8.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 8 --lane-dir pilot/lanes/fable`
Expected: `batch_8: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_8.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 8 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次8 译文入线"
```

### Task 12: s1s 批次 9 译文入库（27 条，约 748 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_9/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_9.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 27 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 9 批（`lane=main chapter=s1s`，27 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 9 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_9/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 9，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_9.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 9 --lane-dir pilot/lanes/fable`
Expected: `batch_9: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_9.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 9 --lane-dir pilot/lanes/fable`
Expected: `batch_9: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_9.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 9 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次9 译文入线"
```

### Task 13: crd 批次 10 译文入库（202 条，约 7492 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_10/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_10.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 202 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 10 批（`lane=main chapter=crd`，202 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 10 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_10/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 10，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_10.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 10 --lane-dir pilot/lanes/fable`
Expected: `batch_10: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_10.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 10 --lane-dir pilot/lanes/fable`
Expected: `batch_10: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_10.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 10 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次10 译文入线"
```

### Task 14: CHECKPOINT——批次 6–10 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s1s 章批次 6–10 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 6–10 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 15: s1s 批次 11 译文入库（159 条，约 4500 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_11/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_11.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 159 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 11 批（`lane=main chapter=s1s`，159 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 11 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_11/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 11，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_11.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 11 --lane-dir pilot/lanes/fable`
Expected: `batch_11: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_11.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 11 --lane-dir pilot/lanes/fable`
Expected: `batch_11: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_11.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 11 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次11 译文入线"
```

### Task 16: crd 批次 12 译文入库（164 条，约 4410 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_12/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_12.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 164 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 12 批（`lane=main chapter=crd`，164 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 12 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_12/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 12，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_12.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 12 --lane-dir pilot/lanes/fable`
Expected: `batch_12: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_12.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 12 --lane-dir pilot/lanes/fable`
Expected: `batch_12: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_12.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 12 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次12 译文入线"
```

### Task 17: s1s 批次 13 译文入库（29 条，约 739 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_13/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_13.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 29 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 13 批（`lane=main chapter=s1s`，29 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 13 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_13/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 13，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_13.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 13 --lane-dir pilot/lanes/fable`
Expected: `batch_13: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_13.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 13 --lane-dir pilot/lanes/fable`
Expected: `batch_13: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_13.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 13 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次13 译文入线"
```

### Task 18: crd 批次 14 译文入库（44 条，约 1105 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_14/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_14.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 44 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 14 批（`lane=main chapter=crd`，44 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 14 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_14/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 14，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_14.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 14 --lane-dir pilot/lanes/fable`
Expected: `batch_14: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_14.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 14 --lane-dir pilot/lanes/fable`
Expected: `batch_14: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_14.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 14 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次14 译文入线"
```

### Task 19: s1s 批次 15 译文入库（46 条，约 1422 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_15/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_15.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 46 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 15 批（`lane=main chapter=s1s`，46 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 15 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_15/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 15，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_15.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 15 --lane-dir pilot/lanes/fable`
Expected: `batch_15: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_15.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 15 --lane-dir pilot/lanes/fable`
Expected: `batch_15: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_15.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 15 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次15 译文入线"
```

### Task 20: CHECKPOINT——批次 11–15 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s1s 章批次 11–15 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 11–15 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 21: crd 批次 16 译文入库（153 条，约 3820 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_16/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_16.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 153 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 16 批（`lane=main chapter=crd`，153 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 16 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_16/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 16，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_16.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 16 --lane-dir pilot/lanes/fable`
Expected: `batch_16: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_16.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 16 --lane-dir pilot/lanes/fable`
Expected: `batch_16: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_16.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 16 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次16 译文入线"
```

### Task 22: s1s 批次 17 译文入库（204 条，约 6257 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_17/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_17.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 204 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 17 批（`lane=main chapter=s1s`，204 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 17 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_17/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 17，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_17.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 17 --lane-dir pilot/lanes/fable`
Expected: `batch_17: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_17.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 17 --lane-dir pilot/lanes/fable`
Expected: `batch_17: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_17.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 17 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次17 译文入线"
```

### Task 23: sys 批次 18 译文入库（30 条，约 679 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_18/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_18.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 30 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 18 批（`lane=main chapter=sys`，30 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 18 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_18/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 18，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_18.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 18 --lane-dir pilot/lanes/fable`
Expected: `batch_18: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_18.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 18 --lane-dir pilot/lanes/fable`
Expected: `batch_18: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_18.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 18 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: sys 批次18 译文入线"
```

### Task 24: s1s 批次 19 译文入库（228 条，约 5388 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_19/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_19.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 228 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 19 批（`lane=main chapter=s1s`，228 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 19 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_19/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 19，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_19.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 19 --lane-dir pilot/lanes/fable`
Expected: `batch_19: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_19.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 19 --lane-dir pilot/lanes/fable`
Expected: `batch_19: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_19.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 19 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次19 译文入线"
```

### Task 25: crd 批次 20 译文入库（46 条，约 1100 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_20/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_20.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 46 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 20 批（`lane=main chapter=crd`，46 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 20 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_20/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 20，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_20.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 20 --lane-dir pilot/lanes/fable`
Expected: `batch_20: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_20.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 20 --lane-dir pilot/lanes/fable`
Expected: `batch_20: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_20.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 20 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次20 译文入线"
```

### Task 26: CHECKPOINT——批次 16–20 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s1s、sys 章批次 16–20 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`、`sys.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 16–20 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 27: s1s 批次 21 译文入库（118 条，约 2523 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_21/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_21.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 118 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 21 批（`lane=main chapter=s1s`，118 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 21 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_21/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 21，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_21.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 21 --lane-dir pilot/lanes/fable`
Expected: `batch_21: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_21.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 21 --lane-dir pilot/lanes/fable`
Expected: `batch_21: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_21.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 21 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次21 译文入线"
```

### Task 28: s1s 批次 22 译文入库（38 条，约 1011 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_22/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_22.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 38 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 22 批（`lane=main chapter=s1s`，38 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 22 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_22/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 22，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_22.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 22 --lane-dir pilot/lanes/fable`
Expected: `batch_22: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_22.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 22 --lane-dir pilot/lanes/fable`
Expected: `batch_22: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_22.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 22 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次22 译文入线"
```

### Task 29: s1s 批次 23 译文入库（70 条，约 2228 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_23/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_23.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 70 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 23 批（`lane=main chapter=s1s`，70 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 23 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_23/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 23，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_23.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 23 --lane-dir pilot/lanes/fable`
Expected: `batch_23: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_23.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 23 --lane-dir pilot/lanes/fable`
Expected: `batch_23: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_23.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 23 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次23 译文入线"
```

### Task 30: crd 批次 24 译文入库（25 条，约 518 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_24/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_24.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 25 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 24 批（`lane=main chapter=crd`，25 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 24 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_24/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 24，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_24.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 24 --lane-dir pilot/lanes/fable`
Expected: `batch_24: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_24.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 24 --lane-dir pilot/lanes/fable`
Expected: `batch_24: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_24.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 24 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次24 译文入线"
```

### Task 31: s1s 批次 25 译文入库（105 条，约 2784 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_25/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_25.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 105 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 25 批（`lane=main chapter=s1s`，105 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 25 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_25/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 25，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_25.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 25 --lane-dir pilot/lanes/fable`
Expected: `batch_25: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_25.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 25 --lane-dir pilot/lanes/fable`
Expected: `batch_25: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_25.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 25 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次25 译文入线"
```

### Task 32: CHECKPOINT——批次 21–25 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s1s 章批次 21–25 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 21–25 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 33: s1s 批次 26 译文入库（213 条，约 5795 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_26/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_26.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 213 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 26 批（`lane=main chapter=s1s`，213 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 26 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_26/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 26，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_26.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 26 --lane-dir pilot/lanes/fable`
Expected: `batch_26: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_26.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 26 --lane-dir pilot/lanes/fable`
Expected: `batch_26: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_26.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 26 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1s 批次26 译文入线"
```

### Task 34: crd 批次 27 译文入库（350 条，约 8985 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_27/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_27.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 350 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 27 批（`lane=main chapter=crd`，350 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 27 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_27/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 27，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_27.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 27 --lane-dir pilot/lanes/fable`
Expected: `batch_27: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_27.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 27 --lane-dir pilot/lanes/fable`
Expected: `batch_27: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_27.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 27 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次27 译文入线"
```

### Task 35: crd 批次 28 译文入库（99 条，约 2964 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_28/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_28.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 99 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 28 批（`lane=main chapter=crd`，99 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 28 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_28/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 28，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_28.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 28 --lane-dir pilot/lanes/fable`
Expected: `batch_28: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_28.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 28 --lane-dir pilot/lanes/fable`
Expected: `batch_28: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_28.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 28 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次28 译文入线"
```

### Task 36: s1f 批次 29 译文入库（311 条，约 8994 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_29/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_29.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 311 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 29 批（`lane=main chapter=s1f`，311 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 29 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_29/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 29，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_29.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 29 --lane-dir pilot/lanes/fable`
Expected: `batch_29: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_29.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 29 --lane-dir pilot/lanes/fable`
Expected: `batch_29: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_29.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 29 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1f 批次29 译文入线"
```

### Task 37: s1f 批次 30 译文入库（335 条，约 8978 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_30/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_30.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 335 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 30 批（`lane=main chapter=s1f`，335 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 30 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_30/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 30，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_30.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 30 --lane-dir pilot/lanes/fable`
Expected: `batch_30: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_30.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 30 --lane-dir pilot/lanes/fable`
Expected: `batch_30: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_30.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 30 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1f 批次30 译文入线"
```

### Task 38: CHECKPOINT——批次 26–30 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s1f、s1s 章批次 26–30 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s1f.md`、`s1s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 26–30 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 39: s1f 批次 31 译文入库（6 条，约 296 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_31/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_31.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 6 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 31 批（`lane=main chapter=s1f`，6 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 31 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_31/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 31，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_31.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 31 --lane-dir pilot/lanes/fable`
Expected: `batch_31: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_31.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 31 --lane-dir pilot/lanes/fable`
Expected: `batch_31: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_31.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 31 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s1f 批次31 译文入线"
```

### Task 40: crd 批次 32 译文入库（17 条，约 170 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_32/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_32.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 17 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 32 批（`lane=main chapter=crd`，17 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 32 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_32/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 32，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_32.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 32 --lane-dir pilot/lanes/fable`
Expected: `batch_32: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_32.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 32 --lane-dir pilot/lanes/fable`
Expected: `batch_32: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_32.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 32 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次32 译文入线"
```

### Task 41: s2s 批次 33 译文入库（66 条，约 1656 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_33/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_33.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 66 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 33 批（`lane=main chapter=s2s`，66 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 33 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_33/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 33，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_33.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 33 --lane-dir pilot/lanes/fable`
Expected: `batch_33: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_33.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 33 --lane-dir pilot/lanes/fable`
Expected: `batch_33: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_33.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 33 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s2s 批次33 译文入线"
```

### Task 42: crd 批次 34 译文入库（41 条，约 1041 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_34/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_34.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 41 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 34 批（`lane=main chapter=crd`，41 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 34 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_34/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 34，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_34.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 34 --lane-dir pilot/lanes/fable`
Expected: `batch_34: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_34.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 34 --lane-dir pilot/lanes/fable`
Expected: `batch_34: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_34.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 34 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: crd 批次34 译文入线"
```

### Task 43: s2s 批次 35 译文入库（106 条，约 2893 日文字）

**Files:**
- Produces: `pilot/lanes/fable/work/ctx/batch_35/{context.md,source.jsonl,manifest.json}`（Step 1）、`pilot/lanes/fable/work/out/batch_35.draft.jsonl`（Step 2 产出、Step 3 校验）、`pilot/lanes/fable/data/forward.jsonl` 追加本批 106 行（Step 5）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 35 批（`lane=main chapter=s2s`，106 条 id）
- Produces: `pilot/lanes/fable/data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 35 --profile cc --baseline none --repo pilot/lanes/fable`
Expected: 生成 `pilot/lanes/fable/work/ctx/batch_35/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 5 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 35，并按本计划头部「车道配置」注入车道根），产出 `pilot/lanes/fable/work/out/batch_35.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/check_batch.py --batch 35 --lane-dir pilot/lanes/fable`
Expected: `batch_35: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `pilot/lanes/fable/work/out/batch_35.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/detect_collapse.py --batch 35 --lane-dir pilot/lanes/fable`
Expected: `batch_35: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `pilot/lanes/fable/work/out/batch_35.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的检查点/硬停任务汇总参考。

- [ ] **Step 5: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`ZND_WORK=pilot/lanes/fable/work ZND_DATA=pilot/lanes/fable/data uv run python tools/append_forward.py --batch 35 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add pilot/lanes/fable/data/forward.jsonl
git commit -m "data: s2s 批次35 译文入线"
```

### Task 44: CHECKPOINT——批次 31–35 术语提案裁决 + 抽查

- [ ] **Step 0: 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，**立即停止试点**，报告人工裁决，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。

到这里已完成 crd、s1f、s2s 章批次 31–35 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `pilot/lanes/fable/data/notes/` 下本段涉及的 `crd.md`、`s1f.md`、`s2s.md`（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。

- [ ] **Step 2: 抽查**

从批次 31–35 已入库的译文里随机抽 2–3 条，对照对应 `pilot/lanes/fable/work/ctx/batch_*/source.jsonl` 的原文与 `pilot/lanes/fable/data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `pilot/lanes/fable/data/forward.jsonl`——它是 append-only 正向线）。

### Task 45: 探针——batch 33 窗口对撞（cc vs api-A 前缀对比，回答"压缩是否丢信息"）

batch 33 是压缩窗口生效后的第一批（spec §2），此刻已随正常流程入库。用**同一模型、同一 effort**在**临时车道副本**上分别以窗口前缀（`--profile cc`）与全前缀（`--profile api-A`）各出一版上下文，人工并排比对两版译文，回答"压缩触发瞬间是否丢信息"。

**必须用临时副本、不得覆盖正式车道产物**（`build_context.py` 的 `ctx_dir` 不含 profile，若 `--repo` 直接指到正式车道 `pilot/lanes/fable`，`--profile api-A` 会原地覆盖 `pilot/lanes/fable/work/ctx/batch_33/context.md`，写进 `pilot/lanes/fable/data/forward.jsonl` 的 `ctx_sha` 会记错——I6）：

- [ ] **Step 1: 建临时副本**

Run: `cp -r pilot/lanes/fable /tmp/lane-probe-fable-33`

- [ ] **Step 2: 两版上下文**

```bash
uv run python tools/build_context.py --batch 33 --profile cc --baseline none --repo /tmp/lane-probe-fable-33
cp /tmp/lane-probe-fable-33/work/ctx/batch_33/context.md /tmp/lane-probe-fable-33-cc.md
uv run python tools/build_context.py --batch 33 --profile api-A --baseline none --repo /tmp/lane-probe-fable-33
cp /tmp/lane-probe-fable-33/work/ctx/batch_33/context.md /tmp/lane-probe-fable-33-api-a.md
```

- [ ] **Step 3: 两版译文**

按 `prompts/translator_cc.md` 分别用两份 context.md（`/tmp/lane-probe-fable-33-cc.md` 与 `/tmp/lane-probe-fable-33-api-a.md`）派子代理各出一版译文（同一模型、同一 effort，只换上下文）。**不要把任一版写回 `pilot/lanes/fable/data/forward.jsonl`**——这是探针，不是正式批次产出，不参与入库。

- [ ] **Step 4: 并排人工比对 + 清理**

对照两版译文：窗口版（cc）出现全前缀版（api-A）没有的指代错误/前情误解，即为窗口丢信息的直接证据；若两版无实质差异，即为"压缩未丢信息"的证据。结论写进试点报告（含 §1 声明的"不能回答"边界：这仍只是段内唯一一次压缩跃迁的单点观测，不能外推到深层前缀）。完成后删除临时副本：`rm -rf /tmp/lane-probe-fable-33*`。

### Task 46: 章末——梗概回译自检 + 人工评审 gate

crd、s0f、s1f、s1s、s2s、sys 章 main 车道全部 35 个批次（1–35）已入库 `pilot/lanes/fable/data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s0f、s1f、s1s、s2s、sys 各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道刚入库的 `pilot/lanes/fable/data/forward.jsonl`：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 35 个 `data: <chapter> 批次N 译文入线` commit（批号 1–35，`<chapter>` 各批不同，见各批 Task 的 Step 5）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。