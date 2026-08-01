# Task 3 Report: 陷阱批回验 `tools/canary.py`

## 执行摘要

实现了「陷阱批回验」工具 `tools/canary.py`：对已入线批次，用当前工具树重新跑一遍
`check_batch.check` + `detect_collapse.scan` 两个校验器，输出规范化 JSON；并提供
`--diff OLD NEW` 比对模式，供工具升级时「旧工具树 vs 新工具树」回归闸使用。
brief 给出的代码逐字采用，未做修改。

## 实现步骤

### Step 1: 写失败测试
写入 `tests/test_canary.py`（brief 原文逐字），含 3 个测试：
- `test_draft_takes_last_occurrence`：验证 `_draft_from_forward` 对同一 id 多次出现取末次
- `test_batch_verdicts_structure`：验证 `batch_verdicts` 返回结构 `{"1": {"check":..., "collapse":...}}`，且该 fixture 数据下 hard 为空
- `test_diff_detects_change`：验证 `diff_verdicts` 对相同输入返回空、对有差异输入返回以 `"batch 1"` 开头的摘要

### Step 2: 确认失败
```
uv run pytest tests/test_canary.py -v
```
输出：`ModuleNotFoundError: No module named 'tools.canary'`（符合预期）。

### Step 3: 写实现
写入 `tools/canary.py`（brief 原文逐字）。核对了它依赖的三个既有接口签名，确认与 brief 描述一致，未改动：
- `tools/pipelib.py`：`dumps`、`read_jsonl`
- `tools/check_batch.py`：`check(source_rows, draft_rows, speakers=None, glossary=None) -> {"hard":[...], "warn":[...]}`
- `tools/detect_collapse.py`：`scan(source_rows, draft_rows, names=(), ...) -> [hits]`、`retained_names(path)`、`_glossary_max(root)`

核心逻辑：
- `_draft_from_forward(forward_rows, ids)`：按 forward.jsonl 中每 id 的末次出现取 zh，只保留 `ids` 里出现过的
- `_ensure_ctx(lane_dir, n, regen)`：ctx 缺失或 `--regen-ctx` 时子进程调用 `build_context.py --batch N --profile cc --repo <lane_dir>`
- `batch_verdicts(lane_dir, nums, regen_ctx=False)`：对每个批号读 ctx source、取对应 draft，跑 check+scan，汇总为 `{str(n): {"check":..., "collapse":...}}`
- `diff_verdicts(old, new)`：按批号排序比对，不同则生成 `"batch K: hard a->b, warn c->d, collapse e->f"` 摘要
- CLI：`--lane-dir --batches --out [--regen-ctx]` 生成模式；`--diff OLD NEW` 比对模式（一致 exit 0，有差异打印摘要 + exit 1）

### Step 4: 确认单测通过
```
uv run pytest tests/test_canary.py -v
```
结果：
```
tests/test_canary.py::test_draft_takes_last_occurrence PASSED
tests/test_canary.py::test_batch_verdicts_structure PASSED
tests/test_canary.py::test_diff_detects_change PASSED
3 passed in 0.01s
```

### Step 5: 真实数据冒烟（P2 全段基线）

车道 `pilot/lanes/opus`：`data/batches.jsonl` 339 行、`data/forward.jsonl` 4282 行；
`work/ctx/` 在冒烟前**完全不存在**（车道是本机重建的，未带 ctx 产物），因此全部
35 批的 ctx 均由 `--regen-ctx`（实际是缺失自动触发）重生。

先用单批做时序/正确性探针：
```
time uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 1-1 \
  --out .../canary-test1.json
```
0.21s 完成（build_context.py 单批很快，不是 brief 担心的"数分钟"量级——该车道
批次内容量不大）。产物 hard=[]，warn 有 1 条 W3，collapse 有 4 条 C3，结构符合预期。

随后跑全 35 批：
```
time uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 1-35 \
  --out /private/tmp/.../scratchpad/canary-p2.json
```
输出：`canary: 35 批判定已写 .../canary-p2.json`，耗时 4.26s（35 批 ctx 全部现场重生 + 校验，
远低于 brief 预警的"数分钟"，说明本车道单批数据量较小，build_context 很快）。

**统计结果**（对生成的 `canary-p2.json` 做汇总）：
- 批次数：35
- **hard 总数：0**（全部 35 批 hard 均为空数组，符合"P2 全程 hard=0"的预期）
- warn 总数：30（W2=15，W3=15）
- collapse 总数：45（C1=21，C2=2，C3=22）

自比对：
```
uv run python tools/canary.py --diff .../canary-p2.json .../canary-p2.json
```
输出：
```
canary diff: 一致
exit code: 0
```
符合预期——同一文件跟自己 diff 无差异，exit 0。

### Step 6: 全量测试 + commit
```
uv run pytest -q
```
结果：**217 passed**（符合预期基线 214 + 3 新测试）。

```
git add tools/canary.py tests/test_canary.py
git commit -m "feat: canary 陷阱批回验（工具升级回归闸）"
```
Commit hash: `e4e8378`

`git status` 确认提交前后除这两个新文件外无其他改动；冒烟过程中在
`pilot/lanes/opus/work/ctx/` 下生成的产物落在 `.gitignore` 覆盖范围
（`pilot/lanes/*/work/`），未被 git 追踪，未纳入 commit。`.superpowers/sdd/` 下
本计划工作文件未触碰（本报告文件除外，属交付物）。

## 偏差与处理

无实质偏差。唯一与 brief 预期不完全一致之处：brief 提示"缺 ctx 的批次会自动调
build_context 重生，耗时可能数分钟"，实际 35 批合计仅约 4 秒——这是车道数据规模
的客观差异（本车道各批规模小），不是工具逻辑问题；已如实记录，未做任何"让它看起来
更像预期"的调整。

## 自查结论

- 代码与测试均为 brief 原文逐字写入，未修改任何既有接口（`pipelib.py`、
  `check_batch.py`、`detect_collapse.py`、`build_context.py` 均未触碰）
- 单元测试 3/3 通过，全量测试 217 passed（211 基线 + Task2 的 3 + Task3 的 3）
- 真实数据冒烟：hard=0（全 35 批），自比对「一致」+ exit 0，均符合预期
- commit 仅包含 `tools/canary.py` 与 `tests/test_canary.py` 两个文件

**状态**：DONE
