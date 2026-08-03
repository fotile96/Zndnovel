# Task 11 执行报告：长对话会话模式（Task 1–3）

计划：`docs/superpowers/plans/2026-08-03-long-conversation-batching.md`
spec：`docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`
起点 HEAD `743798e`（477 passed）。**Task 4（滚生产 tag）按指示未做。**

## 状态：三个 Task 全部完成

| Task | commit | 内容 |
|---|---|---|
| 1 | `fa4d045` | `feat: gen_plan 支持会话组（--session-size/--session-lines 双重上限，默认 1 行为不变）` |
| 2 | `995ca13` | `docs: 译者指令增加长对话会话模式契约` |
| 3 | `ba7b512` | `docs: runbook 增补长对话会话模式条款` |

**测试：477 → 485 passed**（新增 8 条，`tests/test_gen_plan.py` 由 62 → 70；既有 62 条一字未改）。

## 双重上限的实现要点

`_group_sessions(sel, size, lines_cap)` 单趟顺序扫描，仅在 `cur` 非空时判 `len(cur) >= size or n + L > lines_cap` 两个条件之一即切组——「cur 非空」这一前置条件正是「单批自身超 `lines_cap` 时独占一组」的实现方式（批不可再分，不会死循环也不会丢批）；`size <= 1` 直接短路成 `[[b] for b in sel]`，是默认路径逐字不变的保证。`SESSION_MAX=10` 在 `main()` 的 `parse_args` 之后立即校验（早于任何文件读写），`--session-lines` 默认 600。

真实数据佐证上限单位必须是「行」而非只有「批」：`--batches 105-120` 在 `size=10, cap=600` 下切成 `[105–110] [111,112] [113,114] [115–120]`——b111=364 行、b115=374 行，全部四组都是**被行数切开的，一组也没等到 10 批**。

## 两次变异自检（Task 1 Step 6，逐条执行）

| 变异 | 命令 | 结果 |
|---|---|---|
| ① `main()` 里 `if args.session_size > SESSION_MAX:` → `if False:` | `pytest -k over_10` | **精确变红**：`test_session_size_over_10_is_refused` FAILED，全文件跑仅此 1 红、69 绿。改回后 70 绿。 |
| ② `_group_sessions` 的 `n + L > lines_cap` → 恒假 | `pytest -k line_cap` | **变红**：`test_line_cap_splits_before_batch_cap` FAILED；全文件跑 2 红——另一条是 `test_single_oversized_batch_becomes_its_own_group`，同一代码路径，属预期连带。改回后 70 绿。 |

两个闸都有牙，不是恒绿。

副产物清理：变异 ① 让 `main()` 跑完，写出了 `docs/superpowers/plans/translate-x.md`（未跟踪），已 `rm`；这也顺带说明该测试确实走到了 `main()` 的真实执行路径。

## 「默认 `--session-size 1` 逐字不变」的核实

除计划要求的 `test_session_size_1_is_byte_identical_to_before`（自比）外，另做了**对改造前实现的**外部核对：把 `HEAD:tools/gen_plan.py` 取到 scratchpad 按模块加载，与新模块在 **5 组真实 `data/batches.jsonl` 配置**上比对 `render()` 输出——非车道模式、车道模式（含两个硬停任务）、含 batch 33 的窗口对撞探针区间、段模式（`seg3-s4` + `--tools-root`）、extra 车道 165 批。**5/5 逐字相同，0 mismatch**（`old == new(默认) == new(session_size=1)`）。

## Task 2「只追加不修改」的核实方式

`git diff --numstat prompts/translator_cc.md` → **`33  0`（33 增 0 删）**；另跑 `git diff -U0 | grep -c '^-[^-]'` → **0**。节序核对：新节位于第 39 行，正在「## 开工前：读三件材料」（26）与「## 全知纪律」（72）之间，既有 10 个 `## ` 节标题的相对顺序与文字全部不变。Task 4 的判定记录可直接用 `git diff prod-run-v4..HEAD -- prompts/` 复核该性质（本次是 `HEAD~2..HEAD~1` 上的同一结论）。

Task 3 同样是纯插入：`docs/ops/p3-production-runbook.md` `14 0`，新节「四·五」落在「四、段边界工具升级流程」与「五、段末流程」之间。

## 与计划的偏差（1 处，必要修正）

计划 Task 1 Step 3 给出的 `_session_task` 正文里，Step 2 的注入行写的是通配路径 `{p['ctx']}/batch_N/source.jsonl`，而首批只写「首批 {first['batch']} 读全量 `context.md`」（不带路径）。**这与计划 Step 1 自己的测试直接冲突**——`test_session_task_first_batch_reads_full_ctx_rest_read_delta` 断言 `"batch_7/context.md" in t` 与 `"batch_8/source.jsonl" in t`，两者在原文里都不会字面出现。测试是 Step 1 逐字给定的验收面，故按测试修实现：注入行改为**逐批点名具体路径**（首批 `…/batch_7/context.md`、其余批逐个列出 `…/batch_8/source.jsonl`）。这同时更符合意图——派发方要照抄该行注入子代理，通配符等于让子代理自己猜批号。`- Produces:` 那行仍保留 `batch_N` 通配（是文件清单不是指令），故 `"batch_8/context.md" not in t` 仍成立。

附带一处小加固：`lane_root` 在非车道模式（`lane_dir_arg` 为空）下取 `"."` 而非空串，避免渲染出形似绝对路径的 `/glossary/style.md`。

`_group_sessions` 的 docstring、`_session_task` 的 docstring、Task 2/3 的全部契约文本均**逐字采用计划原文**。

## 顾虑（交给控制器）

1. **Task 4 的 canary 判定面不覆盖本次主要风险**。canary 比的是 `check`/`collapse` 输出，而本次 `tools/gen_plan.py` 的改动**不参与四件套判定面**——`--session-size 1` 路径的不变性由上面那组「新旧模块 5 组真实配置逐字比对」承担，建议把这一条写进 v5 判定记录，否则该风险面在记录上是空的。`prompts/` 同样不参与 canary，其人工核对判据（只增不删）已在上文给出。
2. **会话组模式下检查点语义变松**。`len(chunk) == every` 改成 `>= every` 后，会话组模式的 CHECKPOINT 会在「≥5 批」处插入而非精确 5 批（逐批模式下二者恒等，故默认路径无影响）。这是计划指定的行为，但意味着会话组计划里 CHECKPOINT 的批次跨度会随分组浮动，段内抽查密度略降。
3. **硬停任务在 `--session-size > 1` 时不生成**（计划指定，因模板里硬编码 batch_1/2 字面量）。这意味着若有人对 **P2 试点模式**（`segment is None` + `lane_cfg`）用会话组，就会静默失去 batch 1/2 两道隔离验收门。当前 P3 生产走段模式、本就不生成硬停，无实际影响；但工具层没有拦这个组合，值得知道。
4. **组内 `glossary_v` 一致性只在计划文本里写成「开工前硬检查」，没有机械闸**。`_group_sessions` 只看批数与行数，不知道 glossary 版本；跨段分组时靠人不越界。spec §4.3 称「段边界天然对齐」，但工具不阻止 `--batches` 跨段 + `--session-size N` 的组合。
5. spec §5.5（手记里写进虚构规则）仍是已知审计缺口，计划明示不在范围内，本次未触及。
