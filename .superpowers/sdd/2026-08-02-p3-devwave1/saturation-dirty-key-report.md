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

  **【追加修正见下】上面这条顾虑被协调者实测证实为真——而且命中的正是当初
  那个 Critical 的头号例子，已在本轮补上，见下方追加章节。**

---

## 追加修正：并列词串探测（协调者复评后二轮）

### 问题实测

协调者对上面那条「顾虑」做了实测：

```
'はい／いいえ'（全角斜杠）  total=0  is_clean_key=True   ← 被报「无出现」
'はい/いいえ'（半角斜杠）    total=0  is_clean_key=False  ← 正确判脏
'意識'                      total=55 clean=True
全角 ／ 在语料字符集里吗：True | 半角 / ：False
```

根因：全角 `／` 本身出现在游戏原文标点里（所以在 `corpus_chars` 内），
`is_clean_key` 逐字检查因此放行了它；半角 `/` 不在语料里则被拦下——**判定
结果完全取决于抄词表的人用了哪个斜杠，这是巧合，不是判据**。而 `はい` 单独
查是 396 次（覆盖 167）、`いいえ` 是 18 次（覆盖 13）：整串抄 `はい／いいえ`
去查，会读到「原文里没这词、可以随便定」——这正是终审那个 Critical 修的
第一行例子，从 `saturation.py --term` 这条路又能进来一次。

### 修法

不改动 `is_clean_key` 本身（五案例语义保持不变），在 `tools/saturation.py`
新增一道**只在 `main()` 里生效**的并列词串探测，与脏键判据平行、互不影响：

- 新增 `COMPOUND_SPLIT_RE = re.compile(r"[/／、|｜]")`（全角/半角斜杠、顿号、
  竖线）与 `split_compound_candidates(term)`：按这些分隔符拆开、去空白、
  过滤空段，段数 ≤1（没真的拆出多段）则返回空列表，表示"不是并列词串"。
- `main()` 里：对每个词先算整词的 `saturation`；**仅当 `total == 0`** 时才
  尝试拆分（`total > 0` 时整词本身已有证据，不存在"证据被并列串掩盖"的
  问题）；拆出候选后对每个子串各算一次 `saturation`，只要**任一**子串
  `total > 0`，就把该行判为 `COMPOUND_VERDICT_PREFIX`
  （`"疑似并列词串，请拆开分别查"`），并把各子串的 `covered/total=ratio`
  拼进判定文字；否则（没有分隔符，或分隔符拆出的子串也全部零出现）维持
  原有的 clean/dirty 判定不变。
- 排序新增一档：有真实 ratio 的行最先、「疑似并列词串」次之、「无出现」
  （干净零出现）再次之、脏键（未匹配到该词键）殿后——并列词串虽然整词
  `total==0`，但已经摆出了子串的真实证据，理应比"无出现"更靠前提醒人工。

### `はい／いいえ` 修后的实际输出（真实 opus 车道）

```
uv run python tools/saturation.py --term "はい" --term "いいえ" \
  --term "はい／いいえ" --term "はい/いいえ" --term "はい、いいえ" \
  --data-dir pilot/lanes/opus/data --gate 0.8
```

```
| はい | 396 | 167 | 0.422 | 滚存 | ... |
| いいえ | 18 | 13 | 0.722 | 滚存 | ... |
| はい、いいえ | 2 | 2 | 1.000 | 可裁决 | - |
| はい／いいえ | 0 | 0 | - | 疑似并列词串，请拆开分别查（はい=167/396=0.422、いいえ=13/18=0.722） | - |
| はい/いいえ | 0 | 0 | - | 疑似并列词串，请拆开分别查（はい=167/396=0.422、いいえ=13/18=0.722） | - |
```

全角、半角两种抄法现在得到**完全相同**的提示与数字——不再取决于用了哪个
斜杠。（`はい、いいえ` 这个真实存在的顿号并列短语本身 total=2、covered=2，
不落入并列词串分支，走原有「可裁决」判定，符合预期：它本身就是有证据的
整词，不需要拆。）

### 五案例判定（未变）

`is_clean_key` 完全没有改动，五个基准案例的判定与上一轮报告一致：
`いつか きみが みる お話。`(3)→clean、`ＴｒｕｅＣｏｌｕｒ`(1)→clean、
`12`(1)→dirty、`882`/`2470`/`【】`(0)→dirty、含空白+total0→dirty，
`test_five_review_cases_shape_check` 断言未动，全绿。

### cluster_notes.py 零回归比对（二次验证）

`cluster_notes.py` 未改动一行（`extract_terms` 本来就按 `/`／`／` 拆分，
不会产出并列词键；本轮改动只落在 `saturation.py::main()`），但仍按上一轮
方法重新跑了一次真实车道对比：

```
uv run python <scratchpad>/orig_tools/tools/cluster_notes.py --lane-dir pilot/lanes/opus --out dossier_before.md
uv run python tools/cluster_notes.py                          --lane-dir pilot/lanes/opus --out dossier_after2.md
```

`dossier_before.md` 与 `dossier_after2.md` **md5 仍完全一致**
（`f21c2451e074ab1d4247cc52f90e4675`），stdout 逐字节比对（刨除输出文件名）
也一致。**结论：cluster_notes.py 二次验证零回归。**

### 新增测试

`tests/test_saturation.py` 追加 3 条（不改任何既有断言）：
- `test_main_flags_compound_term_with_real_lane_evidence`：直接读真实
  `pilot/lanes/opus/data`（只读），用实测的 `はい=167/396=0.422`、
  `いいえ=13/18=0.722` 钉住输出；同时验证全角 `／` 与半角 `/` 两种抄法
  得到完全相同的判定文字（各 2 次命中同一条真实证据）。
- `test_main_compound_split_all_zero_falls_back_to_existing_verdict`：
  构造 `タニ／バタ`——含分隔符，但拆开的子串 `タニ`/`バタ` 在语料里都是
  真零出现，不应误报「疑似并列词串」，仍走原有「无出现」判定。
- `test_runbook_step2_wording_matches_compound_verdict_constant`：把 runbook
  §5 第 2 步的新增文案与 `COMPOUND_VERDICT_PREFIX` 常量钉在一起，同上一轮
  `DIRTY_KEY_VERDICT` 的回归闸手法，防止文案与代码再次分家。

`docs/ops/p3-production-runbook.md` §5 第 2 步同步补充说明：词表不要整串抄
并列词，工具会自动拆分子串查证据、报「疑似并列词串，请拆开分别查」。

### 测试结果

`uv run python -m pytest -q` → **326 passed**（323 + 本轮新增 3 条）。

### 顾虑（本轮）

- 并列分隔符集合（`/ ／ 、 |｜`）是启发式列举，不是穷举——若未来遇到用
  其他符号（如 `・` 顿号变体、`,`、`；`）分隔的并列词误抄进词表，仍会退回
  「无出现」/「未匹配」的旧判定而不会触发并列词串提示。当前集合覆盖了
  终审报告点名的实况（全角/半角斜杠），足够堵住已知的头号例子，但不是
  100% 兜底；后续若再发现新的分隔符实况，按同样思路加进
  `COMPOUND_SPLIT_RE` 即可。
- `test_main_flags_compound_term_with_real_lane_evidence` 直接断言真实
  `pilot/lanes/opus/data` 里 `はい`/`いいえ` 的精确计数（167/396、13/18）；
  这是有意为之（协调者要求"不要编造，用真实语料值"），但意味着若该车道
  之后又有新的 ledger 行落入这两个词（不太可能——ledger 建自已冻结的原文
  lua 脚本、不随译文进度变化，但若段表/车道范围扩大仍有微小可能），这条
  测试需要同步更新计数。

  **【追加修正见下】这条顾虑被协调者复评判为 Important 并指出了分析缺口
  （只想到了 total 的分母冻结，没想到 covered 的分子在持续增长）——已在
  本轮替换掉该测试，见下方追加章节。**

---

## 追加修正（三轮）：`covered` 是移动靶，改用合成 fixture

### 问题

协调者复评指出：`test_main_flags_compound_term_with_real_lane_evidence`
断言的 `はい=167/396`、`いいえ=13/18` 里，**分母 396/18（ledger 里的原文出
现次数）确实冻结不变**（ledger 建自已冻结的原文 lua 脚本），但**分子
167/13（covered，来自 `pilot/lanes/opus/data/forward.jsonl`）是持续增长的
生产数据**——`はい` 的未覆盖分布横跨 `crd/e1f/e1s/e2f/e2s/s3fa/.../s8f`
几乎全部尚未完成翻译的章节，生产会话继续推进任何一段这两个数字就会变，
测试会**红在与被测逻辑（并列词串探测）完全无关的原因上**：探测本身没坏，
只是生产又译了几批。这类测试会训练人看到红灯就先怀疑"是不是环境/数据变了"
而不是先怀疑代码——反而削弱了测试的信号价值。

`・`（顿号变体）没有被建议加入 `COMPOUND_SPLIT_RE` 这一判断，协调者复评
支持维持原状：实测 `・` 在 ledger 里出现 22 次，全部是 `です・ます`、
`オ・ト・ナ` 这类原文书写惯例本身自带的中点，不是提案标题里"并列多个词"
的分隔符，加进去会把这些固定搭配拆开产生噪音而非价值。

### 修法

替换 `test_main_flags_compound_term_with_real_lane_evidence` 为两条：

1. **`test_main_flags_compound_term_with_synthetic_lane_evidence`**（合成
   fixture，与既有 `test_main_compound_split_all_zero_falls_back_to_existing_verdict`
   同一手法）：构造一个 3 行的小型 ledger——`アイス` 出现让子串 `アイ` 命中
   2 次（`{"id":1,...}` 覆盖、`{"id":2,...}` 未覆盖）、`ウエスト` 让子串
   `ウエ` 命中 1 次（未覆盖）；拼起来的整词 `アイ／ウエ` 本身从不以连续
   子串出现在任何一行，`total==0`。断言的输出是
   `疑似并列词串，请拆开分别查（アイ=1/2=0.500、ウエ=0/1=0.000）`——
   这个 ratio 直接由这份固定 fixture 现算得出，与生产数据完全解耦，
   `forward.jsonl` 只有一行手写的 `{"id":1}`，不受车道推进影响。
2. **`test_main_compound_detection_structural_on_real_lane_data`**（保留
   "至少一条测试真的踩过真实车道数据"这条独立价值，协调者认可保留）：
   仍读真实 `pilot/lanes/opus/data`（只读），但**只断言结构性质**——
   `疑似并列词串` 前缀出现、判定文字里含 `はい=`/`いいえ=` 两个子串词名、
   全角 `／` 与半角 `/` 两种抄法在**去掉词名列之后逐字相同**（比较两行输出
   彼此是否一致，不比较任何一行是不是等于某个写死的数字）。这三条性质
   —— 前缀、子串词名齐全、全角半角等价——都不随生产推进变化。

### `docs/ops/p3-production-runbook.md` 示例数字同步整改

上一轮追加的说明段落里把 `はい=167/396=0.422、いいえ=13/18=0.722` 写成了
具体示例数字——它不是断言、不会让测试红，但同样会随生产推进过时，读到的
人可能误当成当前基准。改为不带精确数字的格式示意
（`词A=覆盖/出现=比值、词B=覆盖/出现=比值`）并加一句「具体数字为示意格式、
非当前基准」的说明。检查过上一轮加的回归闸
（`test_runbook_step2_wording_matches_compound_verdict_constant`）：它只钉
`COMPOUND_VERDICT_PREFIX` 常量字符串在 step2 附近 800 字符内出现，不涉及
任何具体数字，本次改动不影响该闸的成立性，无需调整。

### cluster_notes.py 零回归比对（三次验证，改用任务开始前的真实基线）

本轮没有改动 `cluster_notes.py`/`is_clean_key` 一行，但仍重新核实：这次用
本次整个任务开始前的提交 `39a4a95`（`223f728` 的父提交）取
`cluster_notes.py`/`saturation.py`/`pipelib.py`/`resolve.py`/`__init__.py`
的隔离副本（因为最初两轮用的 scratchpad 临时文件已被环境回收），在真实
opus 车道分别跑：

```
uv run python <scratchpad>/orig_tools2/tools/cluster_notes.py --lane-dir pilot/lanes/opus --out dossier_baseline.md
uv run python tools/cluster_notes.py                          --lane-dir pilot/lanes/opus --out dossier_current.md
```

`dossier_baseline.md` 与 `dossier_current.md` **md5 仍完全一致**
（`f21c2451e074ab1d4247cc52f90e4675`）。**结论：对着任务开始前的原始基线
三次验证，cluster_notes.py 零回归。**

### 五案例判定（未变）

`is_clean_key` 本轮未改动一行，五个基准案例判定与前两轮报告一致：
`いつか きみが みる お話。`(3)→clean、`ＴｒｕｅＣｏｌｕｒ`(1)→clean、
`12`(1)→dirty、`882`/`2470`/`【】`(0)→dirty、含空白+total0→dirty，
`test_five_review_cases_shape_check` 断言未动，全绿。

### 测试结果

`uv run python -m pytest -q` → **327 passed**（326 − 1 条被替换 + 2 条新增）。

### 顾虑（三轮）

- 并列分隔符集合仍是启发式列举（`/ ／ 、 |｜`），非穷举；`・` 经复评实测
  确认不该加入（22 次实况全是原文书写惯例的固定搭配，不是并列分隔符）。
  若未来再发现新的真实并列分隔符实况，按同样思路加进 `COMPOUND_SPLIT_RE`
  即可。
- `test_main_compound_detection_structural_on_real_lane_data` 虽然不再断言
  具体数字，但仍依赖真实车道数据里 `はい`/`いいえ` 各自"确实有至少一个
  子串命中"这一事实性质（否则会落回"并列拆开全零"分支、断言会落空）。
  这个性质极难被生产推进打破（两词都是高频常用词，覆盖度增长不会让
  `total` 归零），风险远小于断言精确计数，可接受。
