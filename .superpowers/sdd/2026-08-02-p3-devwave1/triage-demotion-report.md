# 彩野测试机械分诊标记降级报告

## 背景

`.superpowers/sdd/2026-08-02-p3-devwave1/progress.md`（搜「机械分诊标记不成立」，
约第 127–130 行）已记录 SEG-1（15 题）首次真实全跑的证伪数据：15 题打了 10 个
`⚠ 存疑：可能照抄未理解` 标记，全部落在判「对」的行上（对 10/13＝77%），两条
「部分对」零标记——与判分员自己的疑虑反相关，无区分力；且分诊标记当初就是为
q4 设计的，本轮同一题、更完整的上下文下反而零标记。根因是标记键控在模型
run-to-run 可变的私有推理文本（`reasoning_text`）上——这正是当初评审警告过的
「不该让分数挂钩不稳定私有产物」，被用在了判分上却没用在标记自身。本次任务
按 progress.md 的裁定建议（第 129 行）执行：**判定去掉，测量留下**。本报告不
重复台账，只记录本次代码改动。

## 删了什么

`tools/ayano_test.py`：

- 删除 `triage(verdict, answer, cot, ctx) -> str` 函数（判「对」时才生效，命中
  即返回 `⚠ 存疑：可能照抄未理解（…）` 这一带结论的判定字符串）。
- 报告生成里原来「只在 `flag` 非空时追加一行 `- **⚠ 存疑…**`」的条件分支去掉，
  改为对每一题无条件输出遥测行。

保留但改变职责的部分：

- `HESITATION_MARKERS`（犹豫词表）与 `VERBATIM_MIN`（逐字重合下限）两个常量
  **保留**，但不再驱动任何判定——只作为新函数 `cot_signals()` 的原始测量口径
  （词表用于报「命中了哪些词」，下限用于「低于此值一律报『无』」的噪声过滤，
  不再是「够了就打标」的阈值）。
- `_longest_verbatim_span()` 保留，算法不变（仍是 `cot_signals` 的底层测量）。
  `is_correct()` / `_verdict_head()` 保留——它们是判分文本格式容错工具，与
  已停用的分诊无关，本身仍有测试价值（`test_verdict_format_contract_tolerates_drift`）。

新增 `cot_signals(answer, cot, ctx) -> str`：只回报两个测量值，不做任何结论：

```python
def cot_signals(answer: str, cot: str, ctx: str) -> str:
    hits = [m for m in HESITATION_MARKERS if m in cot]
    hesitation = "、".join(hits) if hits else "无"
    span = _longest_verbatim_span(answer, ctx)
    verbatim = f"{span} 字" if span >= VERBATIM_MIN else "无"
    return f"犹豫词 {hesitation} ｜ 与上下文最长逐字重合 {verbatim}"
```

`main()` 里对每一题都调用 `cot_signals()` 并无条件写入报告行 `- CoT 信号：…`
（不再看判分是「对」「部分对」还是「错」）。

`HESITATION_MARKERS` 常量上方补了完整的降级记录（证伪数据、根因、n=15 重新
标定也救不回来的结论、指向 progress.md 的出处），明确写「看到这份现成的犹豫词
表/阈值，请不要凭直觉把判定加回去」，防止下一个人重蹈覆辙。

## 遥测行的实际形态（样例）

```
- CoT 信号：犹豫词 需确认 ｜ 与上下文最长逐字重合 无
```

没有命中犹豫词、也没有显著逐字重合时：

```
- CoT 信号：犹豫词 无 ｜ 与上下文最长逐字重合 无
```

两项都命中时（如同时含犹豫词又有长重合）：

```
- CoT 信号：犹豫词 需确认、大概 ｜ 与上下文最长逐字重合 19 字
```

不再出现「⚠」「存疑」「可能」等带结论的措辞，且这一行对判「对」「部分对」
「错」的题都会输出（原分诊只在「对」的行上触发）。

## 既有测试的改动逐条说明

`tests/test_ayano_test.py`：

1. `test_triage_flags_hesitation_and_verbatim_copy` → 改写为
   `test_cot_signals_measures_without_verdict`：断言 `cot_signals()` 只输出数字/
   词本身（不含「存疑」「可能」），且验证不带 verdict 参数时对「相当于原判分
   非『对』」的输入同样正常输出（原第 4 条「判分不是对时不打标」的语义在新
   函数里已不可能出现，因为函数根本不接收 verdict——改为断言这一点）。
2. `test_triage_threshold_boundary_and_no_bare_question_mark` → 改写为
   `test_cot_signals_verbatim_threshold_and_no_bare_question_mark`：保留原有的
   边界断言（差一个字报「无」、够了报具体字数）与裸问号断言（`？`/`?` 不在
   `HESITATION_MARKERS` 里），只是断言对象换成 `cot_signals()` 的输出字符串
   而非 `triage()` 的判定字符串。
3. `test_triage_marker_reaches_report` → 改写为 `test_cot_signal_line_reaches_report`：
   断言报告里出现 `- CoT 信号：犹豫词 需确认 ｜ 与上下文最长逐字重合 无`，且
   **不再出现** `⚠ 存疑` / `可能照抄未理解` 字样；判分行本身不变的断言保留。
4. 新增 `test_cot_signal_line_reaches_report_for_non_correct_verdicts`：按任务
   要求补的一条——判分为「部分对」时，遥测行同样输出（旧分诊只在「对」的行
   上触发，遥测没有理由只在「对」时给）。
5. `test_verdict_format_contract_tolerates_drift`：**未削弱**——`is_correct()` 的
   全部原有断言（8 个「对」的变体、5 个「非对」的变体）原样保留；只删除了该
   测试末尾对 `triage()` 的两条断言（因为函数已不存在），并在 docstring 里
   注明 `is_correct` 独立于已停用的分诊，继续保留继续测试。

## 测试与验证

- `uv run python -m pytest tests/test_ayano_test.py -v`：18 passed（原 17 条，
  净新增 1 条：删 3 条 triage 专用测试、加 4 条 cot_signals/遥测测试）。
- `uv run python -m pytest`：**336 passed**（基线 335 + 净增 1 条测试，全绿）。
- 零真实网络：全程走既有的 `stream_transport` 注入 fixture，未新增任何网络
  调用路径。

## 顾虑

无实质顾虑。唯一需要留意的一点：`is_correct()` / `_verdict_head()` 目前在
`tools/ayano_test.py` 生产代码里已无调用方（只被 `cot_signals` 之外的测试
`test_verdict_format_contract_tolerates_drift` 使用）——按任务要求「不得削弱
其他断言」予以保留，判分文本格式容错本身仍是独立、有价值的工具函数，未删除。
