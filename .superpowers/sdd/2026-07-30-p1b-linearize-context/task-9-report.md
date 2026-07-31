# Task 9: gen_plan（CC 后端批次计划生成器）- 报告

## 实现摘要

实现了 `tools/gen_plan.py`：把 `data/batches.jsonl` 里某个 `(lane, chapter)` 组合下的批次，渲染成一份可被 `superpowers:executing-plans` 直接执行的实施计划 md（`docs/superpowers/plans/translate-<chapter>.md`）。

- `render(batches, chapter, lane, every=5, baseline="none") -> str`：纯字符串模板函数，不碰文件系统。先按 `chapter`/`lane` 过滤并按 `batch` 号排序，再依次生成：每批一个「4 步」翻译入库任务（①build_context ②派译者子代理 ③check_batch ④append_forward+commit），每满 `every` 批插一个 CHECKPOINT 任务（术语提案裁决 + 抽查），末尾插一个章末任务（梗概回译自检 + 人工评审 gate，不自动放行）。
- `main()`：解析 `--lane`/`--chapter`/`--checkpoint-every`（默认 5），读 `data/batches.jsonl`，调用 `render()`，写到 `docs/superpowers/plans/translate-<chapter>.md`。

### 关于 `--baseline` 的参数化（brief 原文「试点期 baseline=none → 参数化 `--baseline`」）

brief 给的函数签名是 `render(batches, chapter, lane, every) -> str`（4 个位置概念），未提及 baseline。我的处理：给 `render()` 加了一个**有默认值的第 5 个关键字参数** `baseline="none"`，只在内部拼 `build_context.py` 的命令行时使用，不破坏已给签名（两条测试都用关键字调用 `chapter=/lane=/every=`，加一个带默认值的尾部参数完全向后兼容）。CLI 层**没有**加 `--baseline` 开关——brief 给出的 CLI 接口原文只列了 `--lane`/`--chapter`/`[--checkpoint-every]` 三项，我没有编造这份清单之外的开关。这样「参数化」体现在 `render()` 是一个变量而不是写死在模板字符串里的字面量，试点期该变量固定传 `"none"`（与 `build_context.py --baseline` 的默认值一致）；未来若要支持 `ref`/`revise`/`judge`，只需要给 CLI 加一个透传开关，`render()` 本身不用改。这是我在需求有轻微歧义处做出的解读，写在这里供复核。

同理 `GLOSSARY_V = 6` 做成模块常量而非动态扫描 `glossary/*.yaml`：`render()` 要求是不碰文件系统的纯函数（brief Step 3：「纯字符串模板函数」），扫描逻辑只能放进 `main()`，但 brief 对 `main()` 的描述只有「读 batches.jsonl 过滤写文件」，没提术语库版本探测；权衡之下选择用 brief 直接告知的事实（「当前 glossary 最高版本是 v6」）写成一个顶部常量 + 注释说明，而不是给 `main()` 加一段任务描述之外的文件系统扫描。代价是 glossary 升到 v7 后这个常量需要手动同步——已记入下方「遗留顾虑」。

## 文件清单

### 新建
- `tools/gen_plan.py`（172 行）
- `tests/test_gen_plan.py`（15 行，Step 1 原文照抄，一字未改）

### 修改
无——`git diff --stat HEAD` 在提交前确认为空（两个新文件均为 untracked，没有触碰任何既有文件）。

## TDD 循环过程

### RED 阶段
```
$ uv run pytest tests/test_gen_plan.py -v
============================= test session starts ==============================
...
tests/test_gen_plan.py:1: in <module>
    from tools.gen_plan import render
E   ModuleNotFoundError: No module named 'tools.gen_plan'
=========================== short test summary info ============================
ERROR tests/test_gen_plan.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.11s ===============================
```
符合预期（brief Step 2：FAIL / ModuleNotFoundError）。

### GREEN 阶段
```
$ uv run pytest tests/test_gen_plan.py -v
============================= test session starts ==============================
collected 2 items

tests/test_gen_plan.py::test_render_contains_tasks_and_checkpoints PASSED [ 50%]
tests/test_gen_plan.py::test_only_selected_chapter_and_lane PASSED       [100%]

============================== 2 passed in 0.02s ===============================
```

### 全套回归检查
```
$ uv run pytest -q
........................................................................ [ 78%]
....................                                                     [100%]
92 passed in 2.05s
```
无回归（基线 90 → 92，新增的 2 个正是本任务的测试；输出干净，无 warning）。

## 真实数据冒烟

### 1) `uv run python tools/gen_plan.py --lane main --chapter s1s`（默认 `--checkpoint-every 5`）

```
$ uv run python tools/gen_plan.py --lane main --chapter s1s
/home/user/Zndnovel/docs/superpowers/plans/translate-s1s.md: 17 个任务
```

- **任务数**：17 = 14 批任务 + 2 检查点 + 1 章末任务。`data/batches.jsonl` 里 `lane=="main" and chapter=="s1s"` 恰好 14 批（batch 号 `[4,7,8,9,11,13,15,17,19,21,22,23,25,26]`），与生成结果的批任务数一致；每 5 批插一个 CHECKPOINT：第 1 组 `[4,7,8,9,11]` 满 5 触发一次（Task 6，批次 4–11），第 2 组 `[13,15,17,19,21]` 满 5 再触发一次（Task 12，批次 13–21），剩余 `[22,23,25,26]`（4 个，不满 5）不再触发，末尾固定追加 1 个章末任务（Task 17）——数字全部对得上。
- **文件行数**：`wc -l docs/superpowers/plans/translate-s1s.md` = **530 行**。
- **批号无串号**：程序化核对了全部 14 个批任务块，每块内 Step1/Step3/Step4 的 `--batch N` 与 commit message 里的批号完全一致（`grep -o -- '--batch [0-9]*'` 去重排序后正好是上面那 14 个数字，无遗漏无多余；逐块解析确认没有一个任务块出现两个不同批号）。

**第一个批次任务（Task 1）完整正文**：

````markdown
### Task 1: s1s 批次 4 译文入库（84 条，约 2180 日文字）

**Files:**
- Produces: `work/ctx/batch_4/{context.md,source.jsonl,manifest.json}`（Step 1）、`work/out/batch_4.draft.jsonl`（Step 2 产出、Step 3 校验）、`data/forward.jsonl` 追加本批 84 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 4 批（`lane=main chapter=s1s`，84 条 id）
- Produces: `data/forward.jsonl` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch 4 --profile cc --baseline none`
Expected: 生成 `work/ctx/batch_4/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 4），产出 `work/out/batch_4.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `uv run python tools/check_batch.py --batch 4`
Expected: `batch_4: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `work/out/batch_4.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成 Step 2 实际执行翻译子代理所用的模型 ID；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`uv run python tools/append_forward.py --batch 4 --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6`

```bash
git add data/forward.jsonl
git commit -m "data: s1s 批次4 译文入线"
```
````

CHECKPOINT 任务（Task 6）与章末任务（Task 17）实例见下方「模板与真实 CLI 对照」之后的补充摘录。

### 2) `--checkpoint-every` 生效证据

按任务指示原样跑了一次：
```
$ uv run python tools/gen_plan.py --lane main --chapter s0f --checkpoint-every 3
/home/user/Zndnovel/docs/superpowers/plans/translate-s0f.md: 3 个任务
```
`data/batches.jsonl` 里 `lane=main chapter=s0f` 只有 2 批（batch 1、2），2 < 3，所以按 `i % every == 0` 的规则一次都不触发 CHECKPOINT，输出是「2 批任务 + 0 检查点 + 1 章末」= 3。这个结果本身没问题（逻辑正确），但因为 s0f 批次太少，光看这一次跑不出「改变 `every` 数值会改变输出」的对照证据。为了不止是"跑了命令、没报错"这种弱证据，我额外用批次数更多的 s1s（14 批）对比了三个不同的 `--checkpoint-every` 值，观察 CHECKPOINT 任务数量随之变化：

| `--checkpoint-every` | 触发的 CHECKPOINT | 总任务数 | 校验 |
|---|---|---|---|
| 5（默认，不传参） | 2 个（批次 4–11、13–21） | 17 | 14+2+1=17 ✓ |
| 3 | 4 个（4–8、9–13、15–19、21–23） | 19 | 14+4+1=19 ✓ |
| 1（每批后都插一个） | 14 个 | 29 | 14+14+1=29 ✓ |

```
$ uv run python tools/gen_plan.py --lane main --chapter s1s --checkpoint-every 3
/home/user/Zndnovel/docs/superpowers/plans/translate-s1s.md: 19 个任务
(grep 到的 4 个 CHECKPOINT 标题：批次 4–8 / 9–13 / 15–19 / 21–23)

$ uv run python tools/gen_plan.py --lane main --chapter s1s --checkpoint-every 1
/home/user/Zndnovel/docs/superpowers/plans/translate-s1s.md: 29 个任务
(CHECKPOINT 标题数 = 14，等于批次数，即每批后都插一个)
```
三组数字与「每满 `every` 批插一个检查点、按批次在过滤集合里的顺序累计」的设计逐一吻合，`--checkpoint-every` 确认生效。

**清理**：以上生成的 `docs/superpowers/plans/translate-s1s.md`、`translate-s0f.md` 均为工具产物，冒烟结束后已 `rm` 删除，`git status --short` 确认工作树只剩 `tools/gen_plan.py`/`tests/test_gen_plan.py` 两个新文件，未 `git add` 生成物。

## 模板命令与真实 CLI 签名对照

| 生成的命令（模板片段） | 真实 CLI 签名（源码核对） | 结论 |
|---|---|---|
| `uv run python tools/build_context.py --batch {n} --profile cc --baseline {baseline}` | `--batch`(int,必填) `--profile`(必填,choices含`cc`) `--baseline`(choices含`none`,默认`none`) `--jp-fallback`(可选flag) | 一致；`--jp-fallback` 未使用（试点期不需要） |
| `uv run python tools/check_batch.py --batch {n}` | 只有 `--batch`(int,必填) | 一致，无多余参数 |
| `uv run python tools/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v 6` | `--batch`(int,必填) `--backend`(必填) `--model`(必填) `--ctx`(必填) `--glossary-v`(int,必填) `--ts`(可选) | 一致，四个 required 全部给出；`--ts` 未用（脚本内部会取当前时间兜底） |

`<model>`、`<ctx_sha>` 两处留给执行者在跑完 Step 1/Step 2 后填入真实值（`ctx_sha` 是 `build_context.py` 运行时才算出的文件哈希，`model` 是执行子代理时才确定的模型 ID，两者在计划生成时刻本就不可能是静态字面量——这不是「占位符敷衍」，而是指明了具体从哪一步的哪个文件/事实里取值）。

## CHECKPOINT / 章末任务实例（来自真实 s1s 冒烟，`--checkpoint-every` 默认 5）

```markdown
### Task 6: CHECKPOINT——批次 4–11 术语提案裁决 + 抽查

到这里已完成 s1s 章批次 4–11 的翻译入库。继续下一批之前做两件事：

- [ ] **Step 1: 术语提案裁决**

查看 `data/notes/s1s.md`（若这几批翻译中子代理追加过内容——文件不存在说明本轮没有提案，跳过即可）：…

- [ ] **Step 2: 抽查**

从批次 4–11 已入库的译文里随机抽 2–3 条，对照对应 `work/ctx/batch_*/source.jsonl` 的原文与 `data/forward.jsonl` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核……
```

```markdown
### Task 17: 章末——梗概回译自检 + 人工评审 gate

s1s 章 main 车道全部 14 个批次（4–26）已入库 `data/forward.jsonl`。收尾前做两件事：

- [ ] **Step 1: 梗概回译自检**

对照本章对应的章节梗概卡（`skeleton/cards.zh/`，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本章刚入库的 `data/forward.jsonl` 正文译文：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否和 `skeleton/anchors.yaml` 一致，尤其检查有没有在本章尚不该点破的地方提前泄露后续真相（全知纪律，`glossary/style.md`）。

- [ ] **Step 2: 人工评审 gate**

把本章相关的 `data:` commit（`git log --oneline` 过滤 `s1s`）交给人工复核。**不要自动放行**——人工确认无误后本章翻译才算完成，之后才能对下一章跑 `tools/gen_plan.py` 生成新计划。
```

## 提交信息

```
Commit: 0731f93
Message: feat: gen_plan CC 批次计划生成器
Files:
  - tools/gen_plan.py (172 lines)
  - tests/test_gen_plan.py (15 lines)
```

## 自评审

### 完整性
brief 接口原文逐条核对：
- CLI `--lane`/`--chapter`/`[--checkpoint-every 5]` → docs/superpowers/plans/translate-<chapter>.md：✅ 已实现，`--checkpoint-every` 默认值 5。
- `render(batches, chapter, lane, every) -> str`：✅ 签名兼容（额外的 `baseline` 是有默认值的尾部关键字参数，两条测试均按关键字调用，不受影响）。
- 每批 4 步：①build_context（`--profile cc`，`--baseline` 走参数，试点期传 `"none"`）②派译者子代理（引用 `prompts/translator_cc.md` 路径）③check_batch ④append_forward + commit `data: <ch> 批次N 译文入线`：✅ 全部落地，commit message 格式逐字核对与 brief 模板一致。
- 每 `every` 批插检查点任务（术语提案裁决 + 抽查）：✅，且用 s1s 真实数据验证了 5/3/1 三种 `every` 值都产出了数量正确的 CHECKPOINT。
- 章末任务 = 梗概回译自检 + 人工评审 gate：✅，且明确写了「不要自动放行」。
- executing-plans 头注：✅ 逐字复制自 `writing-plans` SKILL.md 的模板行（也是 `docs/superpowers/plans/2026-07-30-p1b-linearize-context.md` 第 3 行用的同一句）。

### 质量
- 生成的 md 能否被 executing-plans 直接吃：结构上具备 `# 标题`、头注 REQUIRED SUB-SKILL 行、Goal/Architecture/Tech Stack/Global Constraints、`### Task N:` + `- [ ]` checkbox 步骤——与本仓库既有三份实施计划（`docs/superpowers/plans/2026-07-30-p1b-linearize-context.md` 等）用的是同一套版式约定。
- 批号有没有串：写了一段一次性核对脚本，逐个解析 14 个批任务块，确认每块内 `--batch` 出现的所有数字都相同、且与 commit message 里的批号一致，结果零异常。
- 用真实 `data/batches.jsonl`（339 行）而不是玩具数据做了冒烟，覆盖了「有检查点」（s1s，14 批）和「批次数小于 every，无检查点」（s0f，2 批）两种边界。

### 纪律
- YAGNI：没有加 `--baseline` CLI 开关（brief 的 CLI 接口原文没列这一项）；`render()` 只加了一个有默认值、brief 明确要求"参数化"的 `baseline` 关键字参数，没有引入模板引擎或额外抽象。
- 没有复述 `prompts/translator_cc.md` / `reviewer_cc.md` 的内容——模板里两处只引用路径 + 说明"要产出什么文件"，没有转述控制码规则、全知纪律细则等具体规则内容。
- 没有编造不存在的 CLI 参数——三条生成命令逐一和 `build_context.py`/`check_batch.py`/`append_forward.py` 的 argparse 源码核对过，见上表。
- 没有碰任何既有文件：`git diff --stat HEAD` 全程为空，只新增了 brief 指定的两个文件；未改动 `tools/`、`tests/`、`config/`、`data/`、`prompts/`、`skeleton/`、`glossary/`、`docs/superpowers/plans/` 下已有文件。
- 冒烟产物已清理，未 `git add`。

### 测试
- 两条测试测的是真实渲染行为（任务计数算术、CHECKPOINT/章末文案是否出现、跨 chapter/lane 过滤是否生效），不是重复实现细节的空断言。
- `uv run pytest tests/test_gen_plan.py -v` 单跑 2 passed；`uv run pytest -q` 全套 92 passed（基线 90 + 本任务 2），干净无告警。

## 遗留顾虑

1. **`GLOSSARY_V = 6` 是硬编码常量**，不是像 `build_context.py` 那样动态扫描 `glossary/glossary.v*.yaml` 取最大版本号。原因见上方"实现摘要"末段（`render()` 按 brief 要求必须是不碰文件系统的纯函数，动态扫描只能塞进 `main()`，但 brief 对 `main()` 的描述里没有这项，为避免超出任务范围没有加）。**影响**：glossary 升到 v7 及以后，如果不手动同步这个常量，`gen_plan.py` 生成的计划里 `append_forward.py --glossary-v` 那一格还会写 6，需要执行计划的人肉眼纠正，或者由下一次改动 `gen_plan.py` 时顺手改掉。这是我在"纯函数 vs 自动跟随"之间选择前者时留下的已知技术债，未做成 CLI 开关是因为 brief 的 CLI 接口原文没有提供这个入口。
2. **`--model <model>`／`--ctx <ctx_sha>` 是执行时才能填的两个空位**，不是可以直接复制粘贴无脑执行的字面量命令（原因见"模板命令与真实 CLI 签名对照"表格下方说明）。这是该流水线本身的性质决定的（`ctx_sha` 要等 `build_context.py` 跑完才算得出来），不是本工具偷懒；但如果 executing-plans 的执行者比较机械，可能需要在 Task 描述里再加粗提醒一次——目前 Step 4 的说明文字里已经用括号显式点出了两处替换点，认为足够，但没有做更强的格式约束（比如把 `<model>`/`<ctx_sha>` 换成更显眼的占位符语法）。
3. 未对 `main()` 的 CLI 解析路径（`argparse` 部分）单独写测试——检查了仓库里其余全部工具脚本（`check_batch.py`/`append_forward.py`/`build_context.py` 等）都只测核心函数、不测 `main()`/argparse，本次沿用同一惯例，真实数据冒烟已经过手动跑通 CLI 三次（默认 every、`--checkpoint-every 3`、`--checkpoint-every 1`），认为覆盖足够。
