# Task 7 报告：生成首段（SEG-1）生产计划

## Step 1: 生成

命令（逐字按 brief 执行，`--lane main` 未改动）：

```bash
uv run python tools/gen_plan.py --lane main --batches 36-62 --label seg1-s2 \
  --segment seg1-s2 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus \
  --model opus --effort max --append-model-id claude-opus-5
```

输出：

```
/Users/fotile96/Zndnovel/docs/superpowers/plans/translate-seg1-s2.md: 35 个任务
```

事前核对 `data/batches.jsonl`：b36–62 共 27 条记录，`lane` 字段全部为 `main`（用 python 脚本枚举确认，`lanes={'main'}`, `count=27`）——证实 brief 所述「`--lane main` 是对的」，未误传。

生成物：`docs/superpowers/plans/translate-seg1-s2.md`（1270 行，35 个任务：27 个批次任务 + 5 个 CHECKPOINT + 2 个硬停 + 1 个章末评审 gate）。

## Step 2: 人工核验（五项，逐项附证据）

**① 头部车道配置表**

文件第 20–33 行「车道配置」表：

| 项 | 值 |
|---|---|
| lane | opus |
| lane_dir | /Users/fotile96/Zndnovel/pilot/lanes/opus |
| model | opus |
| effort | max |
| append_model_id | claude-opus-5 |

`model=opus`、`effort=max`、`append_model_id=claude-opus-5` 全部匹配；`lane_dir` 为本机绝对路径 `/Users/fotile96/Zndnovel/pilot/lanes/opus`。**通过。**

**② 段开场自检位置 / 段末流程位置 / tag 名**

- 「段开场自检」块位于第 38–44 行，紧接在车道配置块之后、**Task 1（第 46 行，第一个批次任务）之前**。**通过。**
- 「段末流程」块位于第 1264–1270 行，在 **Task 35（第 1250 行，最后一个任务）之后**，即全文最尾部。**通过。**
- tag 名：第 1268 行 `3. 打段完成 tag：`git tag prod-opus-seg1-s2-done`` —— 与要求的 `prod-opus-seg1-s2-done` 完全一致。**通过。**

**③ glossary_v=7**

`grep -c -- "--glossary-v 7"` 命中 27 次，对应 27 个批次任务的 `append_forward.py` 调用（batch 36–62 各一次），且 Global Constraints 段（第 16 行）声明 `--glossary-v 7`（当前最高 glossary 版本）固定。未发现任何 `--glossary-v 6` 或其他版本号。**通过，且与上一任务把车道冻结在 v7 的前提一致。**

**④ 批次区间**

`grep -n "^### Task"` 提取全部任务标题，批次任务覆盖的批号为：36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62 —— 连续、无缺漏、无越界，共 **27 批**，与 `config/segments.yaml` 里 SEG-1 定义 `batches: [36, 62]`（62-36+1=27）及 `data/batches.jsonl` 的枚举结果一致。**通过。**

**⑤ 隔离纪律块**

第 31 行（车道配置表下方）：
> **隔离纪律**：禁止读取、列出 `/Users/fotile96/Zndnovel/pilot/lanes/` 下除 `opus` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `/Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl`。违反即本批作废重跑。

块存在且措辞明确「禁止读取其他车道」。**通过。**

## 五项核验结论

全部 5 项通过，无偏差。

## Step 3: commit

```bash
git add docs/superpowers/plans/translate-seg1-s2.md
git status --short   # 仅这一个文件 A（新增），无其他改动被带入暂存区
git commit -m "docs: SEG-1（s2 完结段，b36-62）生产计划"
```

commit: `e8ef830e5392b7b6a90dfc5c14eb3f4e48d8b151`

`.superpowers/sdd/2026-08-02-p3-ignition/` 下的工作文件（progress.md 等）未触碰、未提交，符合要求。

## 偏差与处理

无。五项核验均逐项查证通过，未发现空计划、版本号错误、批次区间偏差、位置错乱或隔离纪律缺失等问题。

## 点火交接

产出 `docs/superpowers/plans/translate-seg1-s2.md` 即代表 P3 点火计划就绪。生产会话开工方式：新会话 + 按 `docs/ops/p3-production-runbook.md` 完成开场自检（工具树来自生产 worktree、`lane_setup.py --verify` 无漂移、额度余量确认）+ 执行 `translate-seg1-s2.md`（`superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 逐任务推进）。

---

## 追加：评审 Critical 修正（生成器缺陷 + 重新生成）

评审发现：`tools/gen_plan.py` 的 `render()` 在车道模式下无条件（`lane_cfg is not None` 即触发，未考虑 `segment`）于第 1、第 2 个批次任务后插入两个「硬停」任务模板（`_hardstop_after_batch1`/`_hardstop_after_batch2`），模板内硬编码了字面量 `--batch 2`、`work/ctx/batch_2/context.md`、`batch_1.collapse.json`、`batch_2.collapse.json`。其成立前提（原注释）是「试点计划恒从 batch 1 开始」，在 P3 段模式（本段从 batch 36 开始）下不成立——生成出的 Task 2 会让执行者对无关的全局 batch 2（序章 s0f）跑 `build_context`，Task 4 依赖根本不存在的 `batch_1/2.collapse.json`，触发误报的「停止试点」。这是通用缺陷，SEG-2 起的每个段计划都会复现。

### 改了什么

**`tools/gen_plan.py`**（`render()` 内，约第 439–449 行）：把两处硬停触发条件从

```python
if lane_cfg is not None and batch_task_count == 1:
elif lane_cfg is not None and batch_task_count == 2:
```

改为

```python
if segment is None and lane_cfg is not None and batch_task_count == 1:
elif segment is None and lane_cfg is not None and batch_task_count == 2:
```

并把上方注释从「试点计划恒从 batch 1 开始」的过时断言，改写为说明该等价关系只在 `segment is None`（P2 试点模式）下成立，段模式（`segment` 非 None）因硬编码字面量在段模式下指向不相关批次而必须跳过——段模式已有段开场自检/段末流程作为质量门。非段模式（`lane_cfg` 非 None、`segment is None`）行为一字不变。

**`tests/test_gen_plan.py`** 新增两个测试（插在 `test_non_lane_mode_has_no_hardstop_tasks` 之后）：

1. `test_segment_mode_with_lane_cfg_has_no_hardstop_tasks`——`render(_sel(), label="seg1-s2", lane="main", every=10, lane_cfg=LANE_CFG, segment="seg1-s2")`，断言 `sections` 里没有标题含「硬停」的任务段（`assert not [s for s in sections if "硬停" in s.split("\n", 1)[0]]`）。
2. `test_pilot_mode_lane_cfg_without_segment_still_has_hardstop_tasks`——`render(_sel(), label="pilot-opus", lane="main", every=10, lane_cfg=LANE_CFG, segment=None)`，断言恰好生成 2 个硬停任务段（回归闸，防止把硬停功能整个删掉）。

先加测试跑到 red（`test_segment_mode_with_lane_cfg_has_no_hardstop_tasks` 因旧代码未考虑 `segment` 而失败，见下方实际输出），再改 `render()` 使其转绿，符合仓库 TDD 惯例。

### pytest 实际输出

TDD red 阶段（改代码前）：

```
...........................F................                             [100%]
FAILED tests/test_gen_plan.py::test_segment_mode_with_lane_cfg_has_no_hardstop_tasks
1 failed, 43 passed in 0.13s
```

改 `render()` 后，全量套件：

```
uv run pytest -q
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 97%]
.....                                                                    [100%]
221 passed in 1.43s
```

221 = 原 219 + 新增 2 个测试，与预期一致；既有的 `test_hardstop_tasks_after_batch_1_and_2_in_lane_mode`（P2 试点模式硬停回归测试）继续通过，功能未被误删。

### 重新生成 SEG-1 计划：再核验实际证据

用与 Step 1 完全相同的命令重跑：

```
uv run python tools/gen_plan.py --lane main --batches 36-62 --label seg1-s2 \
  --segment seg1-s2 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus \
  --model opus --effort max --append-model-id claude-opus-5
```

输出：`.../translate-seg1-s2.md: 33 个任务`（原 35 个任务，减少 2 个硬停任务，其余不变）。

- **不再有硬停任务**：`grep -n "^### Task" translate-seg1-s2.md` 输出 Task 1–33，无任何标题含「硬停」的任务段（文件里仍残留 27 处字面量「硬停任务汇总参考」，但那是每批 Step 4 语义崩溃探测说明段落里的固定措辞，指向「检查点/硬停任务」这个泛称，不是实际生成的硬停任务标题——用 `grep -n "^### Task.*硬停"` 核对为 0 命中）。
- **任务编号连续无空洞**：Task 1 → Task 33 连续，批次任务覆盖 36,37,38,39,40,(CHECKPOINT),41,42,43,44,45,(CHECKPOINT),46,47,48,49,50,(CHECKPOINT),51,52,53,54,55,(CHECKPOINT),56,57,58,59,60,(CHECKPOINT),61,62,(章末评审 gate) —— 27 个批次任务 + 5 个 CHECKPOINT + 1 个终任务 = 33，与输出的「33 个任务」吻合。
- **① 批次区间**：仍为 36–62 共 27 批，逐一核对无缺漏（同上）。
- **② glossary_v=7**：`grep -c -- "--glossary-v 7"` 命中 28 次（27 批次各一次 + Global Constraints 声明一次），无 v6 残留。
- **③ 段开场自检/段末流程位置、tag 名**：`## 段开场自检` 在第 38 行、`### Task 1` 在第 46 行（自检在前）；`### Task 33`（末任务）在第 1184 行、`## 段末流程` 在第 1198 行（流程在后，全文尾部）；tag 名第 1201 行 `git tag prod-opus-seg1-s2-done` 与要求一致。
- **④ 车道配置表**：第 20–33 行「车道配置」表 model=opus/effort=max/append_model_id=claude-opus-5，lane_dir=`/Users/fotile96/Zndnovel/pilot/lanes/opus`（本机绝对路径），逐字确认。
- **⑤ 隔离纪律块**：第 31 行原样保留「禁止读取、列出 `/Users/fotile96/Zndnovel/pilot/lanes/` 下除 `opus` 外的任何目录……」，未受本次修复影响。

全部核验通过，无偏差。

### commit

两次 commit 分开：

1. `1fd107c2884648701acdeb1cdbe6acda3df25d66` —— `fix: 段模式不再生成 P2 试点专属的硬停任务`（`tools/gen_plan.py` + `tests/test_gen_plan.py`）
2. `972586451ae5e0b53a909544465b33696f3bf34e` —— `docs: SEG-1 生产计划重生成（修复后不再含试点硬停任务）`（仅 `docs/superpowers/plans/translate-seg1-s2.md`）

均以显式路径 `git add`，未使用 `git add -A`/`git add .`；`.superpowers/sdd/2026-08-02-p3-ignition/` 下工作文件未触碰、未提交。
