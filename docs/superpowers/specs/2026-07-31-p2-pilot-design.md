# P2 试点设计：双模型独立双链对照（batch 1–35）

> 承 `docs/superpowers/specs/2026-07-30-translation-pipeline-design.md` §8 路线图的 **P2**。
> 上游状态：P0 骨架已冻结（`git tag skeleton-v1`）、P1a/P1b 基建全部落地并评审通过、P1c 硬化完成（commit b03d6cc）。

**Goal:** 用玩家开局到第 2 章起步的连续段，验证翻译流水线端到端可用，并让 opus5-max 与 fable5-high 各产出一份完整译文供人工对照，选出 v1 译者。

**Architecture:** 两条互不可见的独立车道，各自积累自己的中文前缀链；只读资产共享同一冻结快照，术语层在试点期间锁死；机器分层打分 + 人工三栏 rubric；范围跨过压缩边界一次，以观测窗口机制。

---

## 0. 决策日志

| 决策 | 结论 | 依据 |
|---|---|---|
| 对照形态 | **独立双链全镜像** | 用户裁决（2026-07-31）。选 v1 译者最该看的是误差累积与风格自洽，共享前缀方案测不到 |
| 试点范围 | **batch 1–35**（非 1–32） | 实测压缩边界在 seq 100；延伸 3 批即可观测窗口触发，成本增加 <5% |
| 车道隔离 | `build_context --repo <lane>` + `ZND_DATA/ZND_WORK` | 实测 `build()` 的 `repo=` 参数已提供完整隔离，CLI 未暴露 |
| 术语层 | 试点期**冻结**，提案照收、裁决全部推迟 | glossary 走仓库固定路径，不冻结则先跑完的车道修的术语被后跑车道白捡 |
| 派发机制 | **Workflow**（非 Agent 工具） | Agent 工具无法指定 reasoning effort；effort 是本次对照的自变量之一 |
| 批量策略 | 沿用冻结的 `batches.jsonl`，不重切 | 重切会使对照失去可比性；微批浪费记为 P3 输入 |

### 本设计规避的六个陷阱（ADHD 发散 + 实证）

1. **伪双车道**：两条车道共读 `data/forward.jsonl` → A/B 退化为"同前缀换模型翻一批"，误差累积与风格自洽完全测不到。**对策**见 §3，验收方式：跑完 batch 1 后核对两边 `forward.jsonl` 内容确实不同。
2. **术语泄漏**：`gen_plan` 默认每 5 批一次术语裁决会升 glossary 版本，且 glossary 不受 `ZND_DATA` 隔离 → "谁更好"退化成"谁先跑"。**对策**：§3 拷贝冻结 + §5 提案不裁决。
3. **effort 静默降档**：Agent 工具设不了 effort，任何一次手工重试都会回落到会话默认档，无报错。**对策**：§5 车道配置锁 + 唯一派发路径。
4. **锚点行污染统计**：32 条锚点句规定逐字沿用骨架定稿，两模型必然输出同一字符串；混入区分度统计会制造"两模型很接近"的假阳性。**对策**：§6.1 分层（锚点覆盖层单列，剔出区分度统计）。
5. **把 `check_batch` 输出当质量指标**：它只管结构，且自认有盲区；两模型真正拉开差距的地方最可能正落在结构校验覆盖不到的角落。**对策**：§6 语义崩溃探测 + 人工 rubric。
6. **过度外推窗口结论**：见 §1 边界声明。

---

## 1. 试点回答与不回答的问题

**能回答：**
- 流水线端到端是否可用（build_context → 译者 → check_batch → append_forward → commit 的完整闭环，35 批 × 2 车道）。
- opus5-max 与 fable5-high 在**开局段**的译文高下，含 35 批跨度上的术语/口调漂移。
- 压缩机制触发瞬间是否丢信息（batch 32→33 的窗口跃迁 + §6.4 窗口对撞）。

**不能回答（禁止在结论中外推）：**
- **深层前缀下的表现**。试点段全部 32 批的窗口起点实测**恒为 0**（段外 batch 33–40 为 100、batch 170–173 为 507），即压缩机制在 seq<100 内一次都不触发。跑通此段**不构成**"窗口机制已验证"。
- **长程术语漂移**。35 批仅占全书 339 批的约 10%，且术语层在试点期冻结。
- 两条深层探针留待 P3 前专项设计。

---

## 2. 试点范围（精确定义）

`data/batches.jsonl` 中 **batch 1–35**，全部 `lane=main`，连号无缺口。

- 规模：**4282 行 / 116,282 日文字**。
- 章别构成：s0f 序章 2 批、crd 做卡剧情 12 批、s1s 故事 14 批、sys 系统 2 批、s1f 现实层 3 批、s2s 第 2 章起步 2 批。
- 时间轴覆盖：seq 1–105，含 42 个场景单元、28 个卡面单元、19 个整脚本单元、1 个 `_f` 章单元、2 个文本池单元。
- 边界依据：第一个章梗概卡（`snr_crd_133`）单元位于 seq 100；batch 33（seq 101 起）是压缩生效后的第一批。
- 上下文实测（`--jp-fallback`，字符数）：batch 1 = 45,577；batch 32 = 170,783（前缀占 80%）；**batch 33 = 36,098**（压缩触发，降至 1/4.7）；batch 34 = 37,368；batch 35 = 41,045。

**已知浪费（不在本试点修复）**：段内 6 个微批（b3 = 1 行 9 字、b31 = 6 行、b5 = 13 行、b32 = 17 行、b24 = 25 行、b18 = 30 行）与大批付同样的前缀成本，约占预算 18%。修法属 `gen_batches` 的批量下限策略，但 `batches.jsonl` 已冻结、重切会破坏可比性 → **记为 P3 全量前的输入**。

---

## 3. 车道隔离机制

### 3.1 目录结构

每条车道一个目录（建议置于仓库外或 gitignore 的 `work/lanes/` 下）：

```
<lane>/
  data/
    ledger.jsonl  ledger_extra.jsonl  timeline.jsonl        → 符号链接到仓库 data/
    batches.jsonl  dag.json  scene2card.json                → 符号链接到仓库 data/
    forward.jsonl                                           → 本车道独有（append-only）
    patches.jsonl                                           → 本车道独有（试点期应为空）
  skeleton/                                                 → 【拷贝】自仓库，冻结快照
  glossary/                                                 → 【拷贝】自仓库，冻结快照
  work/ctx/  work/out/                                      → 本车道产物
```

只读数据用**符号链接**（省空间、保证同源）；`skeleton/` 与 `glossary/` 用**拷贝**——拷贝即冻结，从机制上杜绝试点中途仓库侧术语升版泄漏进任一车道。

### 3.2 调用形态

```bash
LANE=work/lanes/opus            # 或 work/lanes/fable
uv run python tools/build_context.py --batch N --profile cc --baseline none --repo $LANE
ZND_WORK=$LANE/work ZND_DATA=$LANE/data uv run python tools/check_batch.py --batch N
ZND_WORK=$LANE/work ZND_DATA=$LANE/data uv run python tools/append_forward.py \
    --batch N --backend cc --model $APPEND_MODEL_ID --ctx <ctx_sha> --glossary-v 6
# $APPEND_MODEL_ID 取车道配置的 append_model_id（§5.1）：claude-opus-5 或 claude-fable-5
# <ctx_sha> 取本批 work/ctx/batch_N/manifest.json 的 ctx_sha 字段
```

依据（已实测）：`build_context.build()` 的 `repo` 参数同时决定 `data/`、`skeleton/`、`glossary/` 三处读取路径与 `work/` 落点，指向车道目录即完整隔离；`check_batch`/`append_forward` 走 `pipelib` 的 `ZND_*` 覆盖。

### 3.3 冻结哈希与开跑前验收

试点启动时记录并写入 `work/lanes/pilot-manifest.json`：`batches.jsonl`、两车道 `skeleton/cards.zh.yaml`、`glossary/active.json`、`glossary/glossary.v6.yaml` 的 sha256。任一批次派发前校验未漂移，漂移则拒绝派发。

**隔离验收（batch 1 完成后立即执行，不通过则停止试点）**：两条车道的 `data/forward.jsonl` 内容必须不同；两条车道 batch 2 的 `context.md` 第二节前缀正文必须各自含本车道 batch 1 的译文。

### 3.4 子代理隔离纪律（指令层，机制挡不住）

目录隔离只保证工具默认读写不串台，**挡不住子代理主动去看**——译者子代理有完整的文件系统读取权限，一次 `ls work/lanes/` 就能看到另一条车道的译文，而"看到对方译法"对本次对照的破坏远大于译错一句。因此每份派发 prompt 必须包含明令：

- 禁止读取、列出或以任何方式窥探 `work/lanes/` 下除本车道外的任何目录；
- 禁止读取仓库根的 `data/forward.jsonl`（试点期该文件不参与，读它只会造成混淆）；
- 查既有译法一律走本车道的 `<lane>/data/forward.jsonl`。

违反即该批次作废重跑（换一个子代理）。此项与 §5.1 的车道配置锁同属"靠纪律而非机制"的约束，需在试点报告中如实记录是否发生过。

---

## 4. 工具改动（试点前置，三项）

### 4.1 `tools/build_context.py`：暴露 `--repo`

`build()` 已有 `repo` 参数，仅需在 `main()` 的 argparse 中加一项并透传：

```python
ap.add_argument("--repo", help="车道根目录（含 data/skeleton/glossary，产物落其 work/）；默认仓库根")
...
build(args.batch, args.profile, args.baseline, repo=args.repo, jp_fallback=args.jp_fallback)
```

测试：新增一例——在 tmp_path 造一个含 `data/forward.jsonl`（内含标记串）+ 符号链接只读资产 + 拷贝 skeleton/glossary 的车道目录，断言 `--repo` 产出的 `context.md` 前缀含该标记、且仓库 `work/` 未被写入。

### 4.2 `tools/gen_plan.py`：连续段模式

现状 `render()` 内部按 `chapter == chapter and lane == lane` 硬编码选批。改为**选批与渲染分离**：

- `render(sel, label, lane, every=5, baseline="none", glossary_v=GLOSSARY_V)` — `sel` 为调用方选好的批次列表（已排序），`label` 为计划标题用的名字（如 `pilot-opus`）。
- `main()` 新增互斥参数组：`--chapter <ch>`（原行为）或 `--batches <a-b>`（连续段，如 `1-35`）。`--batches` 模式下 `label` 取 `--label` 参数值（必填）。
- 计划头部新增**车道配置块**（见 §5.1），由 `--lane-dir`、`--model`、`--effort` 三个参数注入。

测试：断言 `--batches 1-35` 选出的批次编号恰为 1..35；断言原 `--chapter` 行为逐字不变（回归）。

---

### 4.3 `prompts/translator_cc.md`：新增「路径基准」节

模板现有全部路径均为仓库相对（`work/ctx/batch_N/`、`work/out/batch_N.draft.jsonl`、`data/forward.jsonl`、`data/notes/<chapter>.md`），车道模式下这些都在 `<lane>/` 下。**不改模板则每份派发 prompt 都要贴一张路径覆盖表，重复且易漏。**

在模板开头新增一节：声明所有产出/译文线路径以派发方注入的**车道根**为基准（未注入时即仓库根，保持现有行为不变），并明确哪些路径**不**随车道走（`CLAUDE.md`、`prompts/`、`analysis/text_digest/`、`png/` 恒为仓库根）。派发 prompt 只需给出车道根一个值。

同时把 §3.4 的隔离纪律写进模板的「不要做的事」节。

## 5. 执行流程

### 5.1 车道配置锁

每条车道一份配置，写进生成的计划头部，并且是**唯一允许的派发参数来源**：

```yaml
# 车道 A                          # 车道 B
lane:      opus                   lane:      fable
lane_dir:  work/lanes/opus        lane_dir:  work/lanes/fable
model:     opus                   model:     fable      # Workflow agent() 的 model 实参
effort:    max                    effort:    high       # Workflow agent() 的 effort 实参
append_model_id: claude-opus-5    append_model_id: claude-fable-5   # append_forward --model 实参
```

**硬约束：派发只能走 Workflow 的 `agent(prompt, {model, effort})`**。`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档并使该批次失去可比性。任何一次重试必须重新读取本配置。

### 5.2 分段与检查点

每条车道拆成 **3 个 workflow**：batch 1–12、13–24、25–35。段间为人工检查点。三段各自是**预声明的可交付对照切片**——某条车道半途失败，已完成的切片仍可与另一条车道的同切片对照。

每批任务沿用 `gen_plan` 现有四步（build_context → 派译者子代理 → check_batch → append+commit），译者子代理按 `prompts/translator_cc.md`。

**硬停点**：batch 1、batch 2 完成后各硬停一次，执行 §3.3 隔离验收 + §6.3 语义崩溃探测 + 人工抽读，通过后才放开无人值守。理由：串行链上的系统性缺陷会被无声复制进后续所有批次。

**术语提案**：译者/评审子代理照常向 `data/notes/<chapter>.md` 追加提案（该文件在车道目录下），但**试点期间一律不裁决、不升 glossary 版本**。检查点任务改为"清点提案并归档，不改 glossary"。两条车道的提案清单本身也是对照材料之一。

### 5.3 恢复

恢复位置一律从车道的 `data/forward.jsonl` 对照 `batches.jsonl` **重新推导第一个缺失批次**，不信任任何位置指针或进度文件。`forward.jsonl` 是 append-only 的，它与实际完成状态不可能失同步。

---

## 6. 评分与对照

### 6.1 分层（机器侧，先做）

行级分两层（互斥，用于统计）：

| 层 | 判定 | 规模 | 用途 |
|---|---|---|---|
| **锚点覆盖层** | id ∈ `skeleton/anchors.yaml` | 32 条 | 两模型**应当同串**（规定逐字沿用，且锚点在 context 第三节日中对照给出）→ 只统计**指令遵从率**（是否逐字沿用），**必须剔出模型区分度统计** |
| **自由层** | 其余全部 | 4250 行 | 真正的模型区分度样本 |

单元级另设一项独立校验（与上面两层有行交集，不参与行级统计）：**卡面回译自检**——段内 28 个卡面单元，各自仅凭该段中文重写卡面梗概，与 `skeleton/cards.zh/` 人工定稿 diff，人名/称谓/关键事件级分歧即为阻断项。

**抽样按单元类型分层**，不按位置——段内单元构成为场景 42 / 卡面 28 / 整脚本 19 / `_f` 章 1 / 文本池 2，不分层会过采样机械性强、模型差异最小的卡片 stub 类单元。

### 6.2 逐批机器指标（两车道并排记录）

- `check_batch` 的 hard/warn 明细（**仅作合规记录，禁止单独当质量代理指标**）。
- 锚点行逐字沿用率。
- 自由层的两车道字面差异率（作为"分歧热点"定位器，不作为优劣判据）。

### 6.3 语义崩溃探测（`check_batch` 之后新增一道）

结构合法但语义垮掉的批次会成为后续所有批次的可信前缀，现有硬规则拦不住。逐行检查并告警：

- **残留假名比**：译文中平/片假名字符占比超阈值（人名如 アヤノ/ユウイチ 为合法保留，需按 `glossary` 人名表白名单扣除后再计）。
- **中日长度比离群**：`len(zh)/len(jp)` 落在批内分布的极端尾部。
- **复读循环**：同一行内或相邻行间出现异常重复子串。

阈值在 batch 1–2 硬停时用真实数据标定，写入试点记录。

### 6.4 窗口对撞探针（回答"压缩是否丢信息"）

在 **batch 33**（压缩生效后的第一批）上，用**同一模型、同一批次**跑两版上下文：`--profile cc`（窗口前缀，36k 字符）与 `--profile api-A`（全前缀）。两版译文并排人工比对：若窗口版出现全前缀版没有的指代错误/前情误解，即为窗口丢信息的直接证据。成本仅一批。

### 6.5 人工对照 rubric（三栏，缺一不可）

| 栏 | 内容 |
|---|---|
| **中文可读性** | 是否像人写的中文台词；节奏、语气、标点 |
| **术语与口调一致性** | 对 `glossary/active.json` 与 `glossary/voices/*.md` 的贴合；跨批漂移 |
| **全知纪律** | 是否提前消歧、是否剧透。**必须由知晓 s7f 全部真相的人专项反查代词与称呼** |

第三栏是本作特有的必需项：`_render_skeleton` 从 batch 1 起就把全部 196 张卡面（含结局剧透）无条件渲染进上下文，译者知道的与当前该透露的落差在试点段达到峰值；只按"中文顺不顺"打分会**系统性偏爱更果断、因而更容易剧透**的译文。

对照材料的呈现顺序需**去锚定**：整段通读时两车道译文左右并排且**隐去车道标识**（盲评），评分记录完成后再揭示。

---

## 7. 成本预算

- 单车道：约 **3.3M 输入 token**（上下文字符总量约 3.35M，前缀为主要成本）；输出约 11 万汉字。
- 双车道全镜像：约 **6.6M 输入 token**。
- 其中约 18% 消耗在 6 个微批的前缀重复加载上（§2 已知浪费）。
- 窗口对撞探针（§6.4）额外约 1 批的全前缀成本。

---

## 8. 产出物与验收

**产出物：**
1. 两条车道的 `data/forward.jsonl`（各 4282 行译文）与逐批 commit 历史。
2. `work/lanes/pilot-manifest.json`：冻结哈希、车道配置、逐批机器指标。
3. 两份 `data/notes/*.md` 术语提案清单（未裁决）。
4. 人工对照评分记录（三栏 rubric × 分层抽样）+ 窗口对撞比对结论。
5. 试点报告：v1 译者选型结论、流水线缺陷清单、P3 输入（批量下限、探针设计）。

**验收门：**
- §3.3 隔离验收通过（两车道 forward 不同、前缀各读各的）。
- 35 × 2 = 70 个批次全部 `check_batch` hard=0 并入线。
- 章末回译自检对 `cards.zh` 无人名/称谓/关键事件级分歧。
- 试点报告明确写出 §1 的"不能回答"边界。

---

## 9. 已否决方案

| 方案 | 否决理由 |
|---|---|
| 共享前缀 + 分歧点对撞 | 测不到误差累积与风格自洽——正是选 v1 译者最该看的维度（用户裁决取独立双链） |
| 两模型按批号奇偶接力 | 产出搅成一锅，无法归因；且每个换手点都引入文风断层 |
| check_batch 失败批走返工支线、主线继续 | 串行链上等于把脏前缀焊死进后续所有批次 |
| 二分探针（只跑 1/16/32） | 省成本但拿不到可用译文，也测不到漂移 |
| 重切 batches.jsonl 以合并微批 | 破坏与已冻结批次规划的可比性；改到 P3 |
| 试点范围止于 batch 32 | 压缩机制一次都不触发，窗口问题结构上无法回答 |
