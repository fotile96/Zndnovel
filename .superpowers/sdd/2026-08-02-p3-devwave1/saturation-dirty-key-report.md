# saturation.py 脏键判据补齐 —— 报告

## 任务

`tools/saturation.py::main()` 此前没有 `is_clean_key` 判据，同一个「脏键→伪装成
0/0 正常词族」的误读能绕过 `cluster_notes.py` 已经修好的口子，直接从
`saturation.py` 手抄词表这条路再次进来。本次把判据（`is_clean_key` /
`ASCII_RE` / `WORDCHAR_RE` / 由 ledger 构造 `corpus_chars` 的逻辑）从
`tools/cluster_notes.py` 搬到 `tools/saturation.py`，`cluster_notes.py` 改为
`from tools.saturation import saturation, is_clean_key, corpus_chars_from_ledger,
DIRTY_KEY_VERDICT`，两个消费方共用同一份判据与同一句措辞常量
`DIRTY_KEY_VERDICT`。

## 改动文件

- `tools/saturation.py`：新增 `ASCII_RE`/`WORDCHAR_RE`/`is_clean_key`/
  `corpus_chars_from_ledger`/`DIRTY_KEY_VERDICT`（原样迁移 is_clean_key 的实现
  与全部注释，未改动判据逻辑本身）；`main()` 补 `ledger.jsonl` 存在性判断
  （此前缺失文件会在 `read_jsonl` 里直接 `FileNotFoundError` 崩溃）、对每个词
  计算 `clean` 标记、脏键判**「未匹配到该词键（可能提取不干净，请人工核对）」**
  而非「无出现」、ledger 为空/缺失时打印同口径告警（点名
  `<data-dir>/ledger.jsonl`，说明「全部词键将被判脏」，rc 仍为 0）。
- `tools/cluster_notes.py`：删除本地 `ASCII_RE`/`WORDCHAR_RE`/`is_clean_key`
  定义与语料字符集构造代码，改为从 `tools.saturation` 导入并复用；脏键措辞
  改用 `DIRTY_KEY_VERDICT` 常量（字面值未变）。行为完全不变（见下方比对）。
- `tests/test_cluster_notes.py`：仅改 import（`is_clean_key` 现在
  `from tools.saturation import is_clean_key`），未动任何断言。
- `tests/test_saturation.py`：
  - `LEDGER` 夹具追加一行 `{"id": 5, "jp": "ナポリタンとハンバーガーのメニュー", ...}`
    ——让「ナハメ」在 `corpus_chars` 里凑齐 ナ/ハ/メ 三字（不连续拼成
    「ナハメ」，`total` 相关断言不受影响），使既有的
    `test_main_reads_data_dir_and_gates` 里「ナハメ 报无出现」的断言在新判据下
    仍然成立（它现在是「干净键 + 真零出现」的例子，而不是碰巧漏判）。
  - 新增 5 条测试（见下）。
- `docs/ops/p3-production-runbook.md` §5：裁决会话清单第 2 步（saturation.py
  那条）补充一句，说明本工具现在也跑同一份脏键判据、给出与代码一致的措辞。
  同时新增测试 `test_runbook_step2_wording_matches_dirty_key_verdict_constant`
  把文案与 `DIRTY_KEY_VERDICT` 常量钉在一起，防止未来两处再次分家（本仓库刚
  吃过「跨文件一致性靠注释约束不可靠」的亏，这次直接用断言钉住而不是只写注释）。

## cluster_notes.py 零回归比对（硬要求 1）

用 `git show HEAD:tools/cluster_notes.py`（连同同版本 `saturation.py`/
`pipelib.py`/`resolve.py`/`__init__.py`）取到 scratchpad 的隔离副本
`orig_tools/`，工作树完全未动。分别对真实车道跑：

```
uv run python <scratchpad>/orig_tools/tools/cluster_notes.py --lane-dir pilot/lanes/opus --out <scratchpad>/dossier_before.md
uv run python tools/cluster_notes.py                          --lane-dir pilot/lanes/opus --out <scratchpad>/dossier_after.md
```

结果：

- `dossier_before.md` 与 `dossier_after.md` **md5 完全一致**
  （`f21c2451e074ab1d4247cc52f90e4675`，两者相同），382 提案 / 112 词族。
- 两次运行的 stdout 逐行比对，唯一差异是回显的输出文件名本身
  （`dossier_before.md` vs `dossier_after.md`，即命令行参数带来的文本差异），
  刨除这一行后 stdout **逐字节相同**。

**结论：cluster_notes.py 在真实 opus 车道上零回归。**

## 五个基准案例改动后的判定（`tests/test_cluster_notes.py::test_five_review_cases_shape_check`，逐字未改，全绿）

| 案例 | total | 判定（改动后不变） |
|---|---|---|
| `いつか きみが みる お話。` | 3 | clean（total>0 短路） |
| `ＴｒｕｅＣｏｌｕｒ`（全角） | 1 | clean（total>0 短路，ASCII 门不命中全角字符） |
| `12`（命中「12時」） | 1 | dirty（ASCII 硬门，不被 total>0 豁免） |
| `882` / `2470` | 0 | dirty（ASCII 硬门） |
| `【】` | 0 | dirty（纯标点，WORDCHAR 不命中） |
| 含空白且 total==0（`いつか きみが みる お話。`, total=0 变体） | 0 | dirty（空白判据，短路不生效） |

五案例 + 变异守护测试（`test_is_clean_key_ascii_gate_not_bypassed_by_total`、
`test_is_clean_key_total_gt_zero_short_circuits_whitespace_key`、
`test_is_clean_key_whitespace_key_zero_total_stays_dirty`）全部保持原断言、
仅调整了 import 路径，全绿。

## saturation.py 新输出实际样例（真实 opus 车道，`pilot/lanes/opus/data`）

```
uv run python tools/saturation.py --term "意識" --term "はい" \
  --term "首译定名：意識" --term "はい／いいえ" --term "ナハメ" --term "2470" \
  --data-dir pilot/lanes/opus/data --gate 0.8
```

```
done=6278 条已入线译文（data-dir=pilot/lanes/opus/data）
| 词 | 出现 | 已覆盖 | 饱和度 | 判定 | 未覆盖分布 |
|---|---|---|---|---|---|
| ナハメ | 36 | 0 | 0.000 | 滚存 | s3fc:36 |
| はい | 396 | 167 | 0.422 | 滚存 | ... |
| 意識 | 55 | 28 | 0.509 | 滚存 | ... |
| はい／いいえ | 0 | 0 | - | 无出现 | - |
| 首译定名：意識 | 0 | 0 | - | 未匹配到该词键（可能提取不干净，请人工核对） | - |
| 2470 | 0 | 0 | - | 未匹配到该词键（可能提取不干净，请人工核对） | - |
```

要点：
- `首译定名：意識`（描述性前缀没剥）与裸 id `2470` 都判**未匹配到该词键**，
  不再被误读成「无出现」——即便真词 `意識` 在同一份 ledger 里出现 55 次、
  `はい` 出现 396 次。
- `はい／いいえ`（全角斜杠并列串）在 `saturation.py` 直接传入时本身逐字都在
  语料字符集内（全角斜杠本身也出现在原文标点里），判「干净但真零出现」＝
  「无出现」——这与 `cluster_notes.py` 的行为并不矛盾：`cluster_notes.py`
  的 `extract_terms` 会先把 `はい／いいえ` 拆成 `はい`/`いいえ` 两个词键再各自
  判定（各自命中 396/若干次），`is_clean_key` 本身只负责「这个键长得像不像
  词」，不负责拆分；`saturation.py` 是直接给词表，拆分与否是调用方（人工抄
  词表）的责任，工具已经在 runbook 里提醒「手抄需干净」。

## 测试结果

`uv run python -m pytest -q` → **323 passed**（318 基线 + 本次新增 5 条：
`test_main_reports_dirty_key_as_unmatched_not_no_occurrence`、
`test_main_clean_key_zero_total_still_reports_no_occurrence`、
`test_main_warns_on_missing_ledger_file`、
`test_main_warns_on_empty_ledger_file`、
`test_runbook_step2_wording_matches_dirty_key_verdict_constant`）。

## 顾虑

- `saturation.py --term` 是直接给词表，不经过 `cluster_notes.py` 的
  `extract_terms` 拆分逻辑；若未来有人往词表里塞进未拆分的并列串
  （如 `はい／いいえ`），`is_clean_key` 不会挡住它（因为逐字都在语料内），
  仍会算出一个看似合理但语义上是"两个词合并"的饱和度。这不在本次任务范围
  （任务只要求补齐脏键判据，不要求词表层面的拆分），但裁决会话第 2 步的
  操作纪律（词表应逐词干净地手抄）仍需人工把关，runbook 已有提示但未做
  强制校验。
