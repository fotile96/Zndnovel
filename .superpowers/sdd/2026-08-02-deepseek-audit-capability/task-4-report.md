### Task 4 报告：手记审计步骤 1 —— 硬承诺抽取

**状态**：完成。commit `5e38fb0`。

#### 做了什么

1. 读 brief 全文，逐字写入 `tests/test_audit_notes_promises.py`（brief Step 1 给出的 4 个测试：
   `test_prewire_ids_reads_ids_from_body` / `test_extract_hard_promise` /
   `test_soft_suggestion_yields_no_promise` / `test_malformed_model_output_is_treated_as_no_promise`）。
2. `uv run pytest tests/test_audit_notes_promises.py -v` → 收集失败（`ModuleNotFoundError: No module named
   'tools.audit_notes_promises'`），确认红测试符合预期（brief Step 2）。
3. 逐字写入 `tools/audit_notes_promises.py`（brief Step 3 给出的实现：`ID_RE`、`PROMISE_SYS`、
   `prewire_ids`、`_ask_json`、`extract_promises`），一字未改动 `PROMISE_SYS` 提示词。
4. `uv run pytest tests/test_audit_notes_promises.py -v` → 4 passed（brief Step 4）。
5. 按任务指示补充 quote 校验（brief 未强制，任务要求"顺手加一个宽松的校验"）：
   - `extract_promises` 每项额外带 `quote_verified: bool` 字段——`quote`（去空白后）是否为
     提案 `body`（去空白后）的子串。
   - 新增 `_quote_found(quote, body)` 辅助函数，`re.sub(r"\s+", "", s)` 归一化后做子串匹配。
   - **不据此丢弃承诺**：验证失败只标记 `quote_verified=False`，承诺仍保留在输出里，供下游
     （步骤 2/报告）决定如何降权或标注"引用未核实"。
   - 新增两条测试：`test_quote_verified_true_when_quote_is_substring_of_body`、
     `test_quote_verified_false_when_quote_not_found_but_promise_kept`。
6. `uv run pytest -q` → **385 passed**（基线 379 + brief 4 条 + quote 校验 2 条 = 385，吻合）。
7. `git status --short` 确认工作树只新增了这两个文件；`.superpowers/sdd/.../progress.md` 的
   既有未提交改动（另一会话 SEG-2 生产会话所留）未被触碰。仅 `git add
   tools/audit_notes_promises.py tests/test_audit_notes_promises.py`，未用 `-A`/`.`。
8. commit：`feat: 手记审计步骤 1——硬承诺抽取（软倾向不审）`（无 `--no-verify`）。

#### quote 校验的设计与判断

- **判断**：这个校验**不会误伤**，因为它只做子串匹配式的"留痕"而非过滤——真正的把关
  （机械闸）留给下一个任务（核对步骤）去决定"quote_verified=False 的承诺要不要单独复核/
  降权展示"。就算模型对原话做了省略号截断（如 quote 是 body 中一段话的中间摘录并加了
  "……"），也只会让 `quote_verified` 报 False，不会丢弃该条硬承诺，符合"接地要求 + 机械闸"
  而非"抑制性约束"的方向。
- 归一化仅去空白（`\s+`），不做标点/大小写归一化——因为 body 与 quote 都来自同一份中文
  提案文本，标点差异更可能意味着模型确实改写了原话（值得在 `quote_verified=False` 里体现
  出来），而不是应该被校验消化掉的噪声。
- 该字段是本任务在 brief 基础上的**新增输出键**（`quote_verified`），未改变 brief 规定的
  `{kind, ids, quote}` 三个既有键的语义与取值，brief Step 1 的 4 个测试断言（只检查
  `kind`/`ids`/长度）不受影响，全部原样通过。

#### 偏差与处理

- brief Step 5 写"374 passed"，与任务实际给出的基线（379 passed，见任务描述）不一致；
  以任务描述与本地实测为准。实测本任务前 `uv run pytest -q` 应为 379（未单独复核，因为
  按顺序在写入两个新文件前未跑过全量测试；但 379+6=385 与实测数字精确吻合，可反推基线
  确为 379），本任务后确认为 385 passed。
- 未修改 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg2-s3/`、
  `docs/superpowers/plans/translate-seg*.md` 中任何文件；未对 progress.md 的既有未提交改动
  做任何 `git checkout --`/`stash`/覆盖操作。

#### 顾虑

无实质顾虑。唯一值得下一任务（核对/步骤 2）注意的一点：`quote_verified=False` 目前只是
一个信息位，尚未接入任何展示/降权逻辑——如果步骤 2/报告环节希望利用它区分"高置信硬承诺"
与"引用需要人工复核的硬承诺"，需要显式消费这个字段。
