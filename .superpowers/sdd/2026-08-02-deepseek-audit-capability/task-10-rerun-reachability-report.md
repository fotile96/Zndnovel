# Task 10：异常兜底的「无法判断」可被重跑捞到 执行报告

状态：**完成**。改动文件：`tools/audit_notes_promises.py` +
`tests/test_audit_notes_promises.py` + 本报告。

## 缺陷回顾（一行）

`main()`/`rerun_gated()` 对 `verify_promise` 抛出的未预见异常用
`_forced_cannot_tell` 兜底时，reason（`"核对阶段异常：..."`/
`"重跑核对阶段异常：..."`）唯独不带 `GATE_MARK`（`"机械闸"`），而 `is_gated`
判定「是否可重跑」完全靠 `GATE_MARK in reason` 的字面匹配——全库 3 条这样的
条目（s1s/s2s/s3s 各 1 条，均为真实 `TimeoutError`）连 `--rerun-gates all` 都
捞不到，只能靠整章全量重跑（s3s 2h48m）找回。复评定性：不是「静默丢弃」，是
「可见但打不动」，恒绿闸的近亲。

## (a) 设计与理由

新增独立标记 `EXC_MARK = "核对阶段异常"`（与 `GATE_MARK = "机械闸"` 并列，
定义于 `tools/audit_notes_promises.py` 的 `GATE_MARK`/`BUDGET_MARK` 旁）。
`main()`/`rerun_gated()` 两处异常兜底的 reason 文案本来就含 `"核对阶段异常"`
这个子串（`"重跑核对阶段异常：..."` 前面多了「重跑」两字，仍是超串关系），
**不改文案本身**，只是把它确立为一个受纪律约束的锚点（改文案前必须先看
`EXC_MARK` 定义处的说明，否则该条目会从「all」里静默漏选——重演本次要修的
同一种缺陷）。

`is_gated` 改为：
```python
is_gate = GATE_MARK in reason
is_exc = EXC_MARK in reason
if not is_gate and not is_exc:
    return False
if gates == "all":
    return True
return is_gate and BUDGET_MARK in reason   # max_rounds 档：异常兜底不算预算问题，不选
```

**理由（为什么不直接给异常兜底打「机械闸」前缀）**：机械闸是「模型给出了结论，
但结构性证据不足，程序主动把它降级」；异常兜底是「核对流程本身崩溃，压根没
跑出结论」——语义不同。硬套同一前缀等于把「崩溃」谎报成「主动判定」，是错误
的标注（复评原话点名了这一点）。用独立标记 `EXC_MARK` 与 `GATE_MARK` 并列，
两者在 `is_gated` 里各自可查、各自可测，同时在「是否可重跑」这个行为判据上
归入同一路径——形状上是「两个独立信号，一个合并出口」。

`--rerun-gates` 保留现有两值，不新增第三个值：`all` 的语义扩展为「五条机械闸
+ 核对阶段异常兜底 全选（即所有非语料原因的无法判断）」，`max_rounds` 语义不变
（只选预算耗尽那一类，异常兜底不算预算问题，默认档不选）。没有增加第三个值的
必要——调用方要的是「预算问题」vs「所有非语料问题」两级颗粒度，异常兜底自然
落进后者，不需要单独一档。

## (b) 测试改造：喂真实生产者输出

新增 `_verify_reason(monkeypatch, scenario)`：实际调用 `verify_promise`
（`scenario` 覆盖五条机械闸各自的真实触发路径：`stopped_reason`/
`tool_errors`/`no_tool_call`/`prewire_call_tool_raises`/`prewire_all_empty`），
返回它真实产出的 `reason` 字符串，不手写判定文案。

`test_is_gated_recognizes_all_five_real_gate_reasons`：喂五条真实机械闸
reason + 一条模型自判「无法判断」的真实 reason（复用
`test_unparseable_verdict_becomes_cannot_tell` 已验证过的真实产出
`"（模型未给出可解析的判定，或输出不是合法 JSON）"`），验证默认档只选中
`stopped_reason` 那一条，`all` 档选中全部五条机械闸、但仍不选模型自判那条。

`test_is_gated_recognizes_real_exception_fallback_reason`：用 `rerun_gated`
真实抛出 `TimeoutError` 时的产出（不是手写字符串）驱动 `is_gated`，验证默认档
不选、`all` 档选中——这条直接对应复评点名的缺陷。

`test_main_rerun_gates_all_reaches_real_exception_fallback_row`：端到端复现。
先让 `main()` 真的跑一遍（第 2 条提案的 `verify_promise` 抛 `TimeoutError`），
从产出的真实 sidecar 里取出那条「无法判断」，确认其 `reason` 含
`"TimeoutError"` 且不含 `"机械闸"`；再对这份真实 sidecar 跑
`--rerun-gates all`，确认该条被选中重验（`calls == [2]`）。这是最贴近复评
描述场景的一条测试：production 代码路径产出 → 真实文件落盘 → 重跑命令读取 →
命中。

保证方式：这三条新测试没有一处手写 `"机械闸：..."`/`"核对阶段异常：..."` 这类
判定文案本身用于驱动 `is_gated`（`_row` 仍用于构造结构外壳如
`proposal`/`promise`，但 `reason` 字段全部来自真实调用），从根上堵住
「拿手写仿制品测生产者输出」的复发路径。原有 `test_is_gated_selects_only_
budget_exhaustion_by_default`（手写字符串版本）已被上述真实版本替代删除。

`test_main_rerun_gates_all_widens_selection` 等既有的合并/落盘类测试保留手写
`_row` 输入——这些测试验证的是「选中后如何合并/持久化」而非「reason 匹配逻辑
本身」，其正确性不依赖 reason 文案是否真实，予以保留不动。

## (c) 机械闸实际数量核实

实际数量：**5 处** `机械闸：` reason 生成点，全部在 `verify_promise` 内：
- 主体 3 处：`stopped_reason != "finished"`、`tool_errors != 0`、开工具未调用
- 预拼路径早退闸 2 处：取材阶段异常、取回行全部无译文

`"四条机械闸"` 是错误计数，出现在：`verify_promise` docstring（`--max-rounds`
说明段）、旧 `is_gated` docstring、`--rerun-gates` CLI help、测试文件一处注释——
四处全部改为「五条机械闸」，并在提到 `--rerun-gates all` 的地方统一表述为
「五条机械闸 + 核对阶段异常兜底 全选（即所有非语料原因的无法判断）」。
`verify_promise` docstring 里原有的「三条机械闸」/「两条早退闸」两个局部小标题
本身是自洽的（3+2=5，只是从未在同一处显式相加过），保留不动，只在提到全局
总数的地方补充口径。复评的猜测得到印证：`"四条"`与实际 5 处的错位大概率正是
第 6 类（异常兜底）长期没打标记而无人发现的原因之一——数错的地方本身就说明
没人把 5 个生成点逐一点过名。

## 变异自检

把 `is_gated` 里 `is_exc = EXC_MARK in reason` 强改为 `is_exc = False`
（恒假），运行 `tests/test_audit_notes_promises.py`：**精确 2 个测试变红**——
`test_is_gated_recognizes_real_exception_fallback_reason`（`gates="all"`
断言从 True 变 False）与 `test_main_rerun_gates_all_reaches_real_exception_
fallback_row`（同一断言），其余 77 个测试保持绿。改回后 `uv run pytest -q`
恢复 477 passed 全绿。变异命中且范围精确，不是恒绿闸。

## 真实数据核实

只读扫描 `work/out/fullrun-v1/*.jsonl`（未碰任何 `rr-*` 前缀的在跑重跑文件），
用 `load_sidecar` + 本次修复后的 `is_gated` 核对：

```
work/out/fullrun-v1/audit-s1s.jsonl  gated(default)=False gated(all)=True
  reason=核对阶段异常：TimeoutError: The read operation timed out
work/out/fullrun-v1/audit-s2s.jsonl  gated(default)=False gated(all)=True
  reason=核对阶段异常：TimeoutError: The read operation timed out
work/out/fullrun-v1/audit-s3s.jsonl  gated(default)=False gated(all)=True
  reason=核对阶段异常：TimeoutError: The read operation timed out
```

全库确认 3 条异常兜底条目，均为 `TimeoutError`，分布在 s1s/s2s/s3s 各 1 条。
修复后 `is_gated(row, gates="all")` 对三条全部返回 `True`，默认档
（`gates="max_rounds"`）全部返回 `False`（符合预期：异常不是预算问题）。核实
过程只读取文件，未写入/修改 `work/out/` 下任何内容。

## 测试

`uv run pytest -q` → **477 passed**（HEAD 从 6248c57 推进到 45161a4——中途另一
并发任务提交了 Task 9 的改动，本任务的改动落在其之上；477 = 463 基线 + Task 9
新增 + 本任务净新增 3 条测试）。

## 已知边界 / 顾虑

- 本次只处理了 `main()`/`rerun_gated()` 里 `verify_promise` 抛异常的兜底。
  `extract_promises` 抛异常走的是 `extraction_failures` 列表（不同的下游、
  不参与 `is_gated`/`--rerun-from` 这套重跑机制），未在本次范围内改动，也不
  在复评点名的缺陷范围内。
- `EXC_MARK` 与 `GATE_MARK` 是纯字面子串匹配，若未来有人往某条机械闸 reason
  的文案里写入包含 `"核对阶段异常"` 五个字的自然语言说明（或反过来），可能
  造成误判——概率低（现有 5 条机械闸文案与 2 条异常兜底文案已核对过，互不
  包含对方标记），但值得在改动任一处 reason 文案时留意，两处的 `is_gated`
  测试也会在字面冲突时报错提醒。
