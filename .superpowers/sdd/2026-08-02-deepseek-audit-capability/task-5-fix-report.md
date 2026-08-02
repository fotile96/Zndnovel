# DS-T5 复评修复报告

范围：`tools/audit_notes_promises.py`、`tests/test_audit_notes_promises.py`。
基线 `uv run pytest -q` 408 passed；修复后 415 passed（新增 7 条覆盖，
无删除、无 xfail）。

## 1. `main()` 无异常隔离（阻断级，本次主项）——已修

**(a) 逐条异常隔离**：`main()` 循环里 `extract_promises(prop)` 与
`verify_promise(pr, prop, ...)` 各自套 try/except。

- 抽取阶段异常 → 归入 `extraction_failures`（与既有 `parse_ok=False` 分支
  同一处置口径），`reason` 写 `"抽取阶段异常：{类型}: {消息}"`。
- 核对阶段异常 → 用新增的 `_forced_cannot_tell(promise, reason)` 构造一条
  `verdict="无法判断"` 的标准结果，`reason` 写 `"核对阶段异常：{类型}: {消息}"`，
  正常 `r.update({"proposal": prop, "promise": pr})` 后并入 `results`，走
  `render_report` 的常规统计/排序——不单开分支、不特殊豁免，异常结果与
  正常结果在下游看来只是一条 verdict 为「无法判断」的记录。

单条失败因此不再传播出循环：某一条 promise 抛异常时，同批次前面已经算出
的「已履行」等结果原样保留在 `results` 里，`render_report` 正常被调用，
报告文件正常写出，`rc == 0`。`_forced_cannot_tell` 同时被复用在 verify_promise
内部两条新早退闸（见第 2 节），保证三处「被拦下」的结果形状一致。

**(b) 增量落盘**：新增 `_append_jsonl(path, obj)`，每算出一条 `result` 或
`extraction_failure` 立即 `open(path, "a").write(...)` 落盘（不跨迭代持有
文件句柄，每条各自 open/write/close）。`main()` 里在 `--out` 同名、后缀换成
`.jsonl` 的 sidecar（如 `work/out/audit-notes-promises.jsonl`）里累积，每次
运行开始时先 `write_text("")` 清空，避免跨运行的行混在一起。这道防线覆盖的
是 try/except 也接不住的意外（例如被信号杀死、OOM）——(a) 已经让绝大多数
"单条错误"不再需要靠它兜底，但"已经发生且已计费的调用，其结论不能因为进
程后面才发生的意外而消失"这条纪律，光靠内存里的 `results` 列表撑不住进程
中途死亡，需要落盘这一层。

## 2. 预拼路径 `call_tool` 无异常隔离 + 无「材料为空」闸——已修

`verify_promise` 的 `if ids:` 分支新增两条早退闸，**都在调用模型之前短路
返回**（省下一次注定判不出东西的真实 API 调用）：

- **(a) 取材异常**：`call_tool("get_lines", ...)` 包 try/except，抛异常时
  返回 `_forced_cannot_tell`，`reason` 为
  `"机械闸：预拼取材阶段失败（{异常类型}: {消息}），模型未被调用"`，口径
  与既有机械闸②（`tool_errors`）一致。
- **(b) 材料为空闸**：取回的行经 `all(not (r.get("zh") or "").strip() for r
  in lines)` 判定——**全部**行都没有译文（`zh` 为 `None`/空字符串）时强制
  「无法判断」，`reason` 写明「材料不足以判定履行情况」。

**边界处理**：判据是 `all(...)`，只要有一行 `zh` 非空就不触发——单个提案
里部分行已译、部分未译是正常情形，不应被误判为「无法判断」（否则会把大量
本可判定的承诺误伤，把可信度指标搞脏）。两个方向各钉了一条测试：
`test_gate4_all_lines_without_translation_forces_cannot_tell`（全空开火，且
断言模型确实**未被调用**）与 `test_gate4_partial_translation_does_not_fire`
（一行有译文一行没有，模型结论正常生效，不开火）。

## 3. 顺手改名

按复评「可以顺手改名」的建议，把 `verify_promise` 内部局部变量
`used_tools_path` 改名为 `tool_fallback_path`（更准确描述其含义：「因 ids
缺失而走工具兜底」），与返回字段 `used_tools` 的命名不再重叠。这是纯内部
变量、不出现在任何返回值或测试断言里，改动范围仅限 `verify_promise` 函数
体内的三处引用，`grep -rn "used_tools_path"` 确认改后仓库内无残留引用。

## 复现-修复前后对比（`main()` 崩溃场景）

- **修复前**（复评实测）：让第 2 条提案的 `verify_promise` 抛 `RuntimeError`
  → 异常从 `main()` 循环里的 `for pr in extracted["promises"]` 一路冒出
  → `main()` 整体崩溃，`rc` 变量从未被赋值（`None`），`render_report` 从未
  被调用，`--out` 指向的报告文件根本不存在——连第 1 条已经算出的「已履行」
  结果也随着异常一起从存在中消失，且该结果对应的 API 调用已经在
  `data/api_ledger.jsonl` 里计过费。
- **修复后**（`test_main_survives_verify_promise_raising_and_still_writes_report`
  固化）：同样第 2 条抛 `RuntimeError`，`main()` 正常返回 `rc == 0`，报告
  文件存在，`已履行 1` 与 `无法判断 1` 同时出现在报告里，第 2 条的
  `reason` 里能看到 `RuntimeError` 与原始消息「网络异常」——异常没有被埋掉，
  是变成了一条可解释、可追责的可见结果。

## 顾虑

- sidecar `.jsonl` 目前只在 `main()` 单次运行内部使用（增量写入 + 每次运行
  清空），本次没有设计"崩溃后自动从 sidecar 续跑/合并进最终报告"的逻辑——
  T6 全量真跑如果真的中途死亡，需要人工读 sidecar 决定是否续跑，尚无自动
  化的续跑脚本。这属于纪律留痕，不是自愈能力，若 T6 需要断点续跑，建议在
  T6 阶段单独设计。
- `_forced_cannot_tell` 目前对 `main()` 里的核对异常与 `verify_promise` 内部
  两条早退闸复用同一形状；三者的 `reason` 前缀分别是「核对阶段异常」「机械
  闸：预拼取材阶段失败」「机械闸：预拼取回的行全部没有译文」，前者没有
  「机械闸」字样是刻意的——它不是三条既定机械闸之一，是 T5 复评新增的
  "循环层兜底"，用词上和 verify_promise 内部真正的机械闸做了区分，避免
  读报告的人误以为是四条/五条机械闸而非"三条闸 + 两条早退 + 一层循环兜底"。
- 本次修复未触碰 `pilot/lanes/`、`prompts/`、
  `.superpowers/sdd/2026-08-02-p3-seg2-s3/`、
  `docs/superpowers/plans/translate-seg*.md`；`git status` 显示两份
  `progress.md` 与 `data/api_ledger.jsonl` 有非本次改动的未提交改动（其他
  会话/控制器所留，SEG-2 生产翻译仍在同一工作树运行），本次 `git add`
  严格只包含 `tools/audit_notes_promises.py`、
  `tests/test_audit_notes_promises.py` 与本报告文件。未使用
  `git checkout`/`stash`/`restore`，未碰任何真实 API key。
