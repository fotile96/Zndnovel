# DS-T5 执行报告：手记审计步骤 2/3 —— 履行核对与报告

**状态**：完成。`uv run pytest -q` 基线 392 passed → **408 passed**（+16：plan Step1 给的 4 条
逐字采用 + 三条机械闸各自的正/边界测试 6 条 + 报告分母/信息位/main() 循环测试 6 条）。

## 0. 过时签名的处理

按 brief §0 改写：`verify_promise` 内部消费 `_ask_json` 的 3 元组返回
（`data, res, parse_ok`）；`main()` 循环改为先取 `extract_promises(prop)` 的
dict，检查 `extracted["ok"]` 再决定是遍历 `extracted["promises"]` 还是记一条
「抽取失败」，不再是 `for pr in extract_promises(prop):` 一笔带过。

## 1. 三条机械闸（实现要点各一行）

1. `stopped_reason != "finished"` → 强制「无法判断」，`reason` 写
   `"机械闸：stopped_reason=<值>，结论不完整"`（测试：
   `test_gate_stopped_reason_not_finished_forces_cannot_tell`）。
2. `tool_errors != 0`（`res.get("tool_errors", 0)`，缺键按 0 处理，不崩不误判）
   → 强制「无法判断」，`reason` 写明 `tool_errors` 值（测试：
   `test_gate_tool_errors_forces_cannot_tell` / `test_gate_missing_tool_errors_key_defaults_to_zero`）。
3. `used_tools_path (ids 为空) and not tool_calls` → 强制「无法判断」，措辞
   「开了工具但模型一次都没调用」；**只在 `ids` 为空、真正开了工具时判定**，
   预拼路径（`ids` 齐全、不给工具）`tool_calls` 为空是正常状态，不触发
   （测试：`test_gate_tools_opened_but_never_called_forces_cannot_tell` 与其边界对照
   `test_gate3_does_not_fire_when_ids_prewired_even_if_no_tool_calls`）。

三闸都在“采信模型结论之前”做，不静默通过、不抛异常中止整轮审计——命中即把
`verdict` 强改为「无法判断」并把闸名写进 `reason`，其余字段（`evidence_ids`、
`used_tools` 等）原样保留供人复核。

## 2. 报告分母问题的处置（brief §3，阻断级）

`extract_promises` 返回 `ok=False`（模型没读懂该提案）时，`main()` 不再跳过
不记，而是把该提案连同失败原因记入独立列表 `extraction_failures`，与
`verify_promise` 产出的 `results` **分开传给** `render_report(results,
extraction_failures)`。

处置形状：**不**把抽取失败并入下面的「未履行/已履行/无法判断」三态统计——
那统计回答的是「对已读懂的承诺，证据是否够判」；抽取失败回答的是另一个问题
「这条提案压根没读懂，连有没有硬承诺都不知道」，混在一起会让读者分不清是
哪个阶段出的故障。改为在报告最顶部单独一行给出计数（`抽取失败提案 N 条`），
并在专门小节列出具体是哪些提案（章/批次/序号/标题+失败原因），同时明确写
「不计入下面任何一项三态统计」——读者一眼就能看出「有多少提案根本没被审到」，
也不会被误算进「已履行」。`render_report` 的 `extraction_failures` 参数默认
`None`（等价空列表），向后兼容 plan 给的旧调用方式（`render_report(results)`
单参数）。

`main()` 的打印行也同步报告三个数字：提案数、硬承诺数、抽取失败数。

测试：`test_extraction_failures_are_visible_and_not_counted_as_clean`、
`test_render_report_defaults_extraction_failures_to_empty`、
`test_main_records_extraction_failures_separately`（后者直接跑一遍
`main()`，monkeypatch 掉 `extract_promises`/`verify_promise`，用两条合成提案
断言失败的那条进了报告、成功的那条不受影响）。

## 3. 三个信息位的决定（brief §4，逐一显式处理，不沉默）

- **`quote_verified`**：不用于过滤/改判承诺（沿用 T4 的克制——它可能是模型对
  原话做了合理省略号截断，不该被机械闸误伤）。决定：**只在明确为 `False`
  时**，在报告该条目的“承诺原话”后追加一句留痕提示「（⚠ 未在提案正文中
  逐字核验到，留痕不代表承诺不存在）」；字段缺失（旧数据/测试桩）不触发，
  避免把“未检测”误报成“检测失败”。测试：`test_report_warns_when_quote_not_verified`、
  `test_report_does_not_warn_when_quote_verified_field_missing`。
- **`ids_source` / `prewire_ids`（是否回退）**：**不回退**。`verify_promise`
  只看 `promise["ids"]`，当 `ids_source == "model"` 且 `ids == []`（模型确认
  「本承诺不针对具体行」）时，既不静默接回 `promise["prewire_ids"]`，也不用
  它拼上下文——直接进入工具兜底路径。理由：T4 的抽取阶段已经刻意避免让
  「通则声明」类承诺被同一提案里其他子句的 id 污染（回归测试
  `test_explicit_empty_model_ids_is_not_overridden_by_prewire`），T5 若在这里
  再做一次回填等于绕开 T4 划定的边界，重新把跨子句的 id 接回来。测试
  `test_verify_does_not_fall_back_to_prewire_ids_when_model_says_none` 直接
  断言：这一路走了工具兜底（`tool_names` 非空）而不是预拼，且拼给模型的
  `user` 文本里不含 `prewire_ids` 的具体数字。
- **`ids_invalid`**：不用于改判（非法 id 项不代表这条承诺不成立，可能只是
  模型输出有点杂质而承诺本身仍清晰）。决定：原样透传进 `verify_promise` 的
  返回值，`render_report` 对非空的 `ids_invalid` 逐条列出（「⚠ 模型给出的 id
  含非法项已丢弃：[...]」），作为质量信号留给人工复核，不影响 verdict。
  测试：`test_report_flags_invalid_ids_from_promise`。

## 4. 小样真实跑（brief §5，唯一允许发真实请求的步骤）

```
uv run python tools/audit_notes_promises.py --chapter s0f --limit 5 --out <scratchpad>/audit-smoke.md
```

输出：`审计报告已写 ...（5 条提案 → 2 条硬承诺，0 条提案抽取阶段失败未被审到）`

报告全文：

```markdown
# 手记「承诺-履行」审计报告（2 条硬承诺）

- **抽取失败提案 0 条** —— 模型没读懂对应提案，零条承诺，不计入下面任何一项三态统计
- 未履行 **0** ｜ 已履行 2 ｜ 无法判断 0
- **无法判断占比 0%**（相对已成功抽取的 2 条硬承诺）—— 该比例本身是可信度指标，偏高说明材料或判据不足

## [已履行] s0f b1 #1 · 已按「杏仁核」译出
- 承诺原话：本批已按「杏仁核」译出。
- 依据行：[6351]
- 理由：id 6351 的译文将原文「扁桃体」译作「杏仁核」，与承诺一致。
- 用了工具：否

## [已履行] s0f b1 #3 · 本批按指定译法处理
- 承诺原话：本批按「操场角落……眺望着场地」处理。
- 依据行：[6130]
- 理由：译文将「グラウンド」处理为「场地」，与承诺相符，句子大意也符合「操场角落……眺望着场地」的指定译法。
- 用了工具：否
```

**三点观察（如实记录，不美化）**：

1. **抽出的硬承诺是否确实是硬承诺**：`--chapter s0f --limit 5` 对应
   `pilot/lanes/opus/data/notes/s0f.md` batch 1 的前 5 条提案（#1 扁桃体、
   #2 海馬族、#3 校庭/グラウンド、#4 直哉クン、#5 職員室）。人工核对原文：
   #2/#4/#5 全文都是「建议」「宜」措辞（例如 #4 结尾是「建议升格为定译」），
   抽取器**正确地把它们判为无硬承诺**、只从 #1 与 #3 里各挑出一条硬承诺——
   而且 #3 本身是一条以「建议」为主的提案，但其中确实嵌了一句「本批按……
   处理」的既成事实陈述，抽取器只挑出了这一句而非整条提案，边界拿捏准确。
   没有观察到把「建议」错当承诺的情况。
2. **判定的依据行是否真的支持结论**：自行用
   `uv run python tools/agent_tools.py get_lines --args '{"ids":[6351,6130]}'`
   复算（未看模型说什么，直接读 ledger+现行译文）：
   - id 6351：`jp="【直哉】「<扁桃体,へんとうたい>、<内嗅皮質,ないきゅうひしつ>」"`，
     `zh="【直哉】「杏仁核、内嗅皮质」"`——译文确实是「杏仁核」，与承诺一致。
   - id 6130：`jp` 含「グラウンドを校庭の隅……眺めていた」，`zh="一个少女独自
     一人，从操场角落里社团室旁的水泥台沿上眺望着场地。"`——「グラウンド」
     确实处理成了「场地」，与承诺「操场角落……眺望着场地」逐字对得上。
   两条「已履行」判定的依据行都真实支持结论，未发现张冠李戴或断章取义。
3. **「无法判断」的比例**：本次 5 条提案 → 2 条硬承诺，比例 0%（0/2）。
   样本极小（只测了一章一批的前 5 条、且巧合两条都清晰可判），**不能据此
   推断全量分布**——这正是 Task 6 播种检验 + 全量真实跑要处理的问题；这里
   如实记录「小样恰好很干净」，不代表全量也会这么干净。

## 5. 验收

- `uv run pytest -q` → **408 passed**（基线 392 + 16）
- `uv run pytest tests/test_audit_notes_promises.py -v` → 29 passed
- commit：见 git log（`feat: 手记审计步骤 2/3——履行核对与报告`）

## 6. 顾虑

- 小样样本量太小（2 条硬承诺），三态分布与「无法判断」占比都不能代表全量，
  Task 6 的全量真实跑（约 100 条硬承诺）才是真正的信号来源。
- `used_tools_path` 命名与 `verify_promise` 返回的 `used_tools` 字段语义略有
  重叠（前者是「本该走哪条路径」，后者是「实际是否用了工具」），当前用注释
  说明区分，未来若有第三条路径（例如跨提案检索）需要重新审视这两个概念是否
  该合并成一个更清晰的状态机。
- `render_report` 目前把「无法判断占比」的分母限定为“已成功抽取的硬承诺数”，
  没有再算一个「相对全部提案」的第二分母；如果全量跑里抽取失败的提案占比
  很高，报告顶部的两行（抽取失败计数 + 三态占比）需要读者自己心算合并——
  没有做成单一数字，是刻意的（避免把两种不同性质的失败强行拧成一个假的
  综合指标），但留意 Task 6 人工抽核时是否会觉得这个呈现方式不够直观。
- 另一个会话仍在同一工作树写 `pilot/lanes/opus/data/notes/*.md` 与
  `data/api_ledger.jsonl`；本任务未触碰这两类文件（只读取用于小样真跑），
  `git status` 里它们的改动不属于本次提交范围。
