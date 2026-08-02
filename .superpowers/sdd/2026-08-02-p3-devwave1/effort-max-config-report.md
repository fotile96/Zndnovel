# DeepSeek API 默认参数调整（effort=max, max_output_tokens=256K）——执行报告

2026-08-02

## 背景

用户口径（本次任务原话）：
1. `reasoning.effort` 长期默认改为 `max`（除非未来调用显式指定其他档）。
2. `max_output_tokens` 打到几百 K（用户曾提 1M，实测非法）。

用户已实测完成、本次直接采用、未重测：
- `max_output_tokens` 逐档探：65,536/131,072/262,144/393,216 OK；524,288/1,000,000
  返回 HTTP 400。真实 32,035 token 输入测过 393,216 仍 OK——说明这个上限是独立
  的输出上限，不作用在「输入＋输出」之和上，实际边界在 384K–512K 之间。
- `effort=max` 代价（真实 q5，48,294 字符上下文）：推理 tokens 1,699（medium）→
  2,655（max）；输出 1,815 → 2,854；单次墙钟 27.9s（medium 约 9s）。

## 改了什么

### A. `tools/api_client.py` 默认值

| 项 | 旧值 | 新值 | 理由 |
|---|---|---|---|
| `DEFAULT_EFFORT` | `"medium"` | `"max"` | 用户长期口径；注释里写了实测代价对比表（reasoning/输出 token、墙钟） |
| `chat()` 的 `max_tokens` 参数 | 硬写 `4096` | `None`（内部落到新常量） | 与 `timeout`/`retries` 既有的「None→常量」写法一致 |
| 新增 `DEFAULT_MAX_OUTPUT_TOKENS` | 无 | `262144`（256K） | 见下 |
| CLI `--max-tokens` default | `4096` | `None`（同样落到新常量） | 与库函数默认保持同源，不在 CLI 层重复写死数字 |

`DEFAULT_MAX_OUTPUT_TOKENS=262144` 的取值理由（已写入源码常量上方注释，含完整实测表）：
实测 393,216 通过、524,288 返回 400，真实上界在两者之间但未精确探到；取
262,144（256K）比确认可行的 393,216 保守一档，留出约 1.5 倍余量，不贴着未知边界
走——万一 DeepSeek 将来收紧这个上限，贴着走会整批失败。观测到的实际最大输出
（effort=max）仅 2,854 tokens，256K 相对它有约 90 倍冗余，`max_output_tokens`
今后不会再是截断原因。

`chat()` 函数体新增一行：`max_tokens = DEFAULT_MAX_OUTPUT_TOKENS if max_tokens is None else max_tokens`，
显式传值时以传入为准（已用测试覆盖）。

检索确认：仓库内除 `tools/api_client.py` 自身外，只有 `tools/ayano_test.py` 调用
`chat()`/涉及 `max_tokens`，而它的 CLI `--max-tokens`/`--effort` 早已是
`default=None` 且只在非 None 时才把 kwarg 传给 `chat()`——两个新默认值会**自动**
经由 `ayano_test.py` 生效，不需要改它。

### B. 长期政策固化（两处）

1. **`tools/api_client.py` 模块 docstring**（新增段落，紧跟在原有说明之后）：

   > **默认档位政策（用户长期口径，2026-08-02）**：走 `deepseek-v4-flash` 的调用
   > 一律用 `reasoning.effort=max`，除非调用方显式指定其他档。`DEFAULT_EFFORT`
   > 即此政策的落点，改动它等于改政策。

2. **`docs/ops/p3-production-runbook.md`** §五「段末流程与小裁决会话」第 3 项
   （彩野测试那一步）末尾追加一条引用块，记录同一政策 + 影响：effort=max 使彩野
   测试 15 题全跑从约 2 分 19 秒变为约 7–8 分钟、输出 token 约 1.6 倍，属预期；
   并注明 `api_client`/`ayano_test` 不在四件套内、不参与批次生产（引用 §4.1 既
   有判定表），这条改动不影响在产批次。

### C. 台账补记 `effort`

`_write_ledger` 新增可选形参 `effort=None`，有值才写入 `row["effort"]`（与既有
`partial`/`estimated` 两个可选列同样的写法）。`chat()` 内的两处 `_write_ledger`
调用（正常收尾 + 失败尝试的部分记账）均已传入当次实际使用的 `effort` 值。

**不改历史行**：`data/api_ledger.jsonl` 未做任何回填/重写。旧行没有 `effort`
键，消费侧沿用既有的「缺键即未知」机制（`ledger_token`/`summarize_ledger`）天然
兼容——`effort` 是字符串而非数值列，本就不在 `LEDGER_TOKEN_KEYS` 里参与求和；
`ledger_token(row, "effort")` 对缺键（`None`）与对字符串值都返回 `None`（非
`int/float`），不会 KeyError、也不会被误当数值汇总。未改 `LEDGER_TOKEN_KEYS`/
`summarize_ledger` 本体逻辑，因为现有的「非 int/float 或负值 → None」判据已经
安全覆盖了这个新列，属于「若需要才扩展」判断下的「不需要」。

## 测试

新增/改动均在 `tests/test_api_client.py`，全部走注入的 `stream_transport`，零真实网络：

1. `test_default_effort_is_max`——`chat()` 不传 `effort` 时 payload 里
   `reasoning.effort == "max"`。
2. `test_default_idle_timeout_and_max_output_tokens_when_unset`（改造）——`chat()`
   不传 `max_tokens` 时 payload 里 `max_output_tokens == DEFAULT_MAX_OUTPUT_TOKENS
   (262144)`；同一测试内追加显式传 `max_tokens=999` 的分支，确认传入值优先。
3. `test_ledger_records_effort`——台账行含 `effort` 字段，且如实记录调用时传入的
   档位（非写死的 `DEFAULT_EFFORT`）。
4. `test_dirty_summary_tolerates_rows_missing_effort_key`——`ledger_token`/
   `summarize_ledger` 对「旧行缺 `effort` 键」以及「新行 `effort` 是字符串值」
   均安全返回未知（`None`），不 KeyError、不误汇总。

`tests/test_api_client.py`：29 passed。全量：**335 passed**（基线 332 + 本次新增
3 个测试函数 = 335，全绿，无回归）。

## 纪律确认

- 只 `git add` 了实际改动的三个路径：`tools/api_client.py`、
  `tests/test_api_client.py`、`docs/ops/p3-production-runbook.md`，未用
  `git add -A`/`git add .`。
- 未触碰 `pilot/lanes/`、`prompts/`、
  `.superpowers/sdd/2026-08-02-p3-seg1-s2/`、
  `docs/superpowers/plans/translate-seg1-s2.md`。
- `tools/api_client.py`/`tools/ayano_test.py` **不在钉死的四件套内**（不参与按批
  生产、canary 不覆盖，见 `docs/ops/p3-production-runbook.md` §4.1 判定表），
  **本次未滚任何 tag**，也不需要——两工具的生产免跑判定不受本次改动影响。
- 未发出任何真实网络请求；未接触/打印任何 API key。

## 顾虑

- `max_output_tokens` 的真实上界仍只是「在 393,216 与 524,288 之间」的区间估计，
  没有二分到精确值；如果之后需要更贴近上限（比如真遇到长输出被截断），需要另
  外做一轮探测，而不是想当然地把 262,144 直接调大。
- 384 效力评估里彩野测试全跑变慢到 7–8 分钟是一次性成本变化，未来若还要再叠加
  别的高耗时验收步骤（如更大题库），段末流程的时间预算需要相应重新评估。
