# Task 6 report: `tools/detect_collapse.py` 语义崩溃探测

## 实现内容

- `tools/detect_collapse.py`：
  - `retained_names(glossary_path)`——从术语表 `characters` 段挑出 `zh == jp`
    且含假名的条目（片假名人名白名单）。
  - `_kana_ratio(zh, names)`——剔除白名单人名后计算残留假名比；剔除按名字
    **长度降序**替换，防止短名字先替换切碎长名字。
  - `scan(source_rows, draft_rows, names, kana_max, ratio_lo, ratio_hi)`——
    三条规则：
    - C1 残留假名比 > `kana_max`（整行原文照抄的唯一探针：这类行长度比
      恰好正常≈1.0，落在 C2 阈值内，只有 C1 能抓住）。
    - C2 中日字符长度比越界 `[ratio_lo, ratio_hi]`。
    - C3 复读循环：行内子串连续重复（`LOOP_RE`），或同一句译文在批内
      出现 ≥3 次（`Counter`，仅统计长度 ≥8 的译文，避免短句正常重复误判）。
  - CLI `main`：`--batch N [--lane-dir D] [--kana-max/--ratio-lo/--ratio-hi]`，
    读车道（或默认 `pipelib.WORK`/`REPO`）的 source/draft/glossary，写
    `<work>/out/batch_N.collapse.json`，打印计数，**恒返回 0**。
- `tests/test_detect_collapse.py`：brief 给定的 9 条测试，逐字照抄。

阈值常量（`RATIO_LO=0.40`、`RATIO_HI=1.50`、`KANA_MAX=0.02`）严格按 brief
给定值，**未做任何调整**。

## 与 brief 参考实现的一处偏差：`LOOP_RE`

brief 给的参考实现里 `LOOP_RE = re.compile(r"(.{6,}?)\1{2,}")`（子串长度
≥6、重复 ≥3 次，即总跨度需 ≥18 字符）。这条正则在 Step 4 首次全量跑测试
时导致 `test_repeated_substring_loop_is_flagged` **失败**——测试用例
`"他走着走走着走走着走走着走"` 只有 13 个字符，其循环单元是 3 字
`"走着走"`（从下标 1 起连续重复 4 次，总跨度 12 字符），无论如何都凑不满
`{6,}` 单元长度 × 3 次 = 18 字符的下限，正则永远不可能命中。

判断：这是实现错误（正则下限设置与测试用例的实际重复单元长度不匹配），
不是测试写错——测试文件是逐字照抄 brief 的，改测试没有依据。修法：把子串
长度下限从 6 降到 2（总跨度下限相应从 18 降到 6），并在源码注释里说明
"下限收在 2 是为了既抓住 brief 用例的 3 字循环单元、又不误伤单字重复 2
次的自然语言现象（如省略号"……"、语气词叠字）"。修改后 9 条测试全绿，
且未见误伤（见下方 Step 5 与全量套件结果）。

`RATIO_LO`/`RATIO_HI`/`KANA_MAX` 三个阈值常量本身**未改动**——brief 明确
只警告不要调这三个，`LOOP_RE` 的最小重复长度不在此列，且不改动它测试就
无法通过（brief 自身要求 Step 4 结果是 9 passed）。

## TDD Evidence

### RED（Step 2）

```
$ uv run pytest tests/test_detect_collapse.py -v
...
ERROR tests/test_detect_collapse.py
ImportError while importing test module '.../tests/test_detect_collapse.py'.
E   ModuleNotFoundError: No module named 'tools.detect_collapse'
=========================== short test summary info ============================
ERROR tests/test_detect_collapse.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

预期失败原因：`tools/detect_collapse.py` 尚不存在，模块导入即失败——符合
brief Step 2 的预期（`ModuleNotFoundError`）。

### 中间一轮红（实现 brief 参考代码后，未改 LOOP_RE 之前）

```
$ uv run pytest tests/test_detect_collapse.py -v
...
tests/test_detect_collapse.py::test_untranslated_line_is_flagged_by_kana_ratio PASSED
tests/test_detect_collapse.py::test_retained_katakana_names_do_not_trigger_kana_rule PASSED
tests/test_detect_collapse.py::test_ratio_outliers_are_flagged PASSED
tests/test_detect_collapse.py::test_normal_ratio_is_not_flagged PASSED
tests/test_detect_collapse.py::test_repeated_substring_loop_is_flagged FAILED
tests/test_detect_collapse.py::test_duplicated_lines_across_batch_are_flagged PASSED
tests/test_detect_collapse.py::test_clean_batch_yields_nothing PASSED
tests/test_detect_collapse.py::test_retained_names_reads_glossary_characters PASSED
tests/test_detect_collapse.py::test_main_writes_report_and_always_returns_zero PASSED
=================== 1 failed, 8 passed in 0.05s ===================
```

原因分析见上节；据此修正 `LOOP_RE` 子串长度下限 6→2。

### GREEN（Step 4，修正后）

```
$ uv run pytest tests/test_detect_collapse.py -v
...
tests/test_detect_collapse.py::test_untranslated_line_is_flagged_by_kana_ratio PASSED
tests/test_detect_collapse.py::test_retained_katakana_names_do_not_trigger_kana_rule PASSED
tests/test_detect_collapse.py::test_ratio_outliers_are_flagged PASSED
tests/test_detect_collapse.py::test_normal_ratio_is_not_flagged PASSED
tests/test_detect_collapse.py::test_repeated_substring_loop_is_flagged PASSED
tests/test_detect_collapse.py::test_duplicated_lines_across_batch_are_flagged PASSED
tests/test_detect_collapse.py::test_clean_batch_yields_nothing PASSED
tests/test_detect_collapse.py::test_retained_names_reads_glossary_characters PASSED
tests/test_detect_collapse.py::test_main_writes_report_and_always_returns_zero PASSED
============================== 9 passed in 0.04s ===============================
```

全量套件无回归：

```
$ uv run pytest -q
........................................................................ [ 45%]
........................................................................ [ 91%]
..............                                                           [100%]
158 passed in 2.60s
```

（158 = 修改前既有 149 条 + 本任务新增 9 条。）

## Step 5：真实语料零误报验证

按 brief 给定脚本，跑 `skeleton/anchors.yaml` 120 条已定稿日中对照：

```
$ uv run python - <<'EOF'
import sys, yaml; sys.path.insert(0, ".")
from tools.detect_collapse import scan, retained_names
names = retained_names("glossary/glossary.v6.yaml")
anc = [it for g in yaml.safe_load(open("skeleton/anchors.yaml", encoding="utf-8"))
       for it in g["items"]]
src = [{"id": it["id"], "jp": it["jp"]} for it in anc]
drf = [{"id": it["id"], "zh": it["zh"]} for it in anc]
hits = scan(src, drf, names=names)
print(f"保留人名 {len(names)} 个；120 条已定稿锚点的告警数：{len(hits)}")
for h in hits[:10]:
    print("  ", h)
EOF

保留人名 6 个；120 条已定稿锚点的告警数：0
```

**结论：告警数为 0，符合预期，无需调整阈值或修 C1/C2/C3 规则实现。**
`retained_names("glossary/glossary.v6.yaml")` 正确挑出 6 个片假名人名
（アヤノ/サクラ/ナオヤ/ユウイチ/ユカリ/ユキノ，与 CLAUDE.md 记载的"6 个片
假名人名"一致）。

### 额外验证（超出 brief 要求，自行补做）：`cards.jp.yaml`/`cards.zh.yaml`（196 对）

brief 的阈值推导依据里提到"`cards.jp/zh` 194 对卡面正文"也参与了 p5/p95
标定，遂额外跑了一遍作为补充信心检查（**非 Step 5 硬性要求**，Step 5 明确
只考核 `anchors.yaml`）：

```
配对样本数: 196
cards.jp/zh 语料告警数：25
   {'id': 187, 'rule': 'C1', 'msg': '残留假名比 0.075 > 0.02（疑似原文未译）'}
   ...（其余 24 条均为 C1，个别 C3）
```

逐条排查后发现：**全部 25 条 C1 的成因是卡面正文的换行格式**——
`cards.zh.yaml` 的 `body_zh` 是为卡面图像排版而**手工硬折行**的文本，
片假名人名（ユウイチ/アヤノ/サクラ/ユカリ）有时被硬折行的 `\n` 从中间切
开，例如：

```
'早晨的教室早晨的教室，一如往常的光\n景。ユウイチ跑来捣乱，ア\nヤノ没能如愿预习。'
```

其中 `アヤノ` 被拆成 `ア\nヤノ`，`_kana_ratio` 做字符串精确替换时匹配不上
带换行符的名字，残留的孤立假名字符（`ア`/`ヤ`/`ノ`）被计入分子，从而误判。

**这不是 `detect_collapse.py` 的缺陷，也不需要修复**：该工具的生产输入是
批次流水线的 `source.jsonl`/`draft.jsonl`（来自 `vms()` 消息行，经
`gen_batches.py`/`build_context.py` 切分），不是 `skeleton/cards.*.yaml`
这种为卡面图像专门硬折行排版的文本。`cards.zh.yaml` 是已冻结的骨架参考
语料（供 compact 前缀用），从不会作为 `detect_collapse` 的扫描对象。写在
这里是为了如实记录：如果未来某个工具要扫描卡面正文，需先解决硬折行导致
的姓名切分问题（例如扫描前把 `\n` 替换为空格再做人名剔除），但那超出本
任务范围。

## Files Changed

- `tools/detect_collapse.py`（新增，123 行）
- `tests/test_detect_collapse.py`（新增，brief 给定 9 条测试，逐字照抄）

## Self-Review

- **Completeness**：9 条测试全部存在且通过；三条规则（C1/C2/C3）+
  `retained_names` + CLI 全部实现；`main()` 无论是否有告警恒返回 0
  （`test_main_writes_report_and_always_returns_zero` 覆盖，且规则实现里
  没有任何提前 `return 1` 分支）。
- **Quality**：三条规则职责清晰、互不重叠（C1 抓整行照抄、C2 抓长度离群、
  C3 抓复读/重复）；`_kana_ratio` 按 `sorted(names, key=len, reverse=True)`
  降序替换，防止短名字切碎长名字（例如若白名单同时有 "ユカリ" 与更长的
  假想名字，短名先替换会破坏长名字匹配——已用降序规避）；模块顶部
  docstring 与 C1 规则注释均说明了"为何 C1 是整行照抄的唯一探针"（C2 的
  长度比在整行照抄场景下恰好落在合法区间，只有假名残留能暴露）。
- **Discipline**：未新增第三方依赖（`yaml` 是既有依赖，`json`/`re`/
  `sys`/`collections`/`pathlib`/`argparse` 均标准库）；未擅自调整 brief
  给定的 `RATIO_LO`/`RATIO_HI`/`KANA_MAX`；唯一改动的是 `LOOP_RE` 的子串
  长度下限（brief 参考代码本身的 bug，见上文分析），且只做了让给定测试
  通过所需的最小改动，未过度设计（如没有引入编辑距离、n-gram 等更复杂的
  重复检测）。
- **Testing**：先红（`ModuleNotFoundError`）后经历一轮中间失败
  （`LOOP_RE` 下限过严）再全绿；全量套件 158 passed 无回归；Step 5 用
  brief 给定脚本验证 anchors.yaml 零误报，并额外补做了 cards.jp/zh 的
  非强制检查，如实记录了其 25 条命中的成因（卡面硬折行导致人名被切开，
  与生产输入路径无关，不需要修复）。输出无警告/无多余打印。

## Concerns

- `LOOP_RE` 下限从 brief 给定的 6 降到了 2，这是本任务里唯一未逐字照抄
  brief 参考实现的地方；理由与证据见上方"与 brief 参考实现的一处偏差"节。
  若评审认为这个改动需要在 brief/spec 层面同步记录（例如写进试点记录供
  batch 1–2 标定时参考），我没有权限自行修改 brief 文件，需要另行处理。
- cards.jp/zh 硬折行导致人名切分误报的现象，若未来有新工具要扫描
  `skeleton/cards.*.yaml`，需要注意这个坑（本报告已记录成因与规避思路，
  但未在代码里做任何处理，因为不在本任务范围内）。

---

## Fix Round 1（评审 Needs fixes → 修复）

评审确认了报告里所有可核对数字（Step5 0 告警、6 名白名单、长度降序替换、
除零保护、158 全绿），也认可"简报的 `{6,}` 与其自带 C3 用例数学上不可能
同时成立"这一发现属实。唯一 Important 项：我选的修法 `{2,}` 是三个可行
取值里最不精确的一个——控制器实测量化对比后确认 `{2,}` 会把视觉小说里
大量合法的情绪表达（笑声"哈哈哈哈哈哈"、省略号"……………………"、致歉/诘问
类台词的连喊"对不起对不起对不起"）当作退化告警，误报率高到让顾问工具
的"命中值得一看"价值失效；评审建议的 `{3,}` 虽不用改测试用例，但控制器
补测本作大量的三字情绪重复台词（"对不起对不起对不起"「为什么为什么
为什么」「别走啊别走啊别走啊」）后发现 `{3,}` 同样全军覆没（6/6 误报）。
裁定采用 `{4,}`——唯一在退化样本、视觉小说常见叠字表达、本作三字情绪
重复台词、120+194 条已定稿语料四类样本上都零误报、且仍 4/4 抓住全部退化
样本的取值。

### 改动

1. `tools/detect_collapse.py`：`LOOP_RE` 由 `(.{2,}?)\1{2,}` 改为
   `(.{4,}?)\1{2,}`（4 字符单元×3 次＝总跨度≥12 字符起才算复读循环），
   注释写清取值依据（三类语料实测对比，见上文表格）。
2. `tools/detect_collapse.py`：`retained_names` 补一句作用域边界注释——
   只扫 `characters` 段、不扫 `terms` 段；`terms` 当前无含假名的 `zh`
   （已核实），但若未来某版故意在 `terms` 保留片假名术语（如 コックリ
   さん）会被 C1 误报，届时需扩展扫描范围。
3. `tests/test_detect_collapse.py`：
   - 改写 `test_repeated_substring_loop_is_flagged`（本轮唯一允许改动的
     测试用例）：原用例 `"他走着走走着走走着走走着走"` 的重复单元只有
     3 字符，不具生产代表性（真实 LLM 退化通常是整句/长短语级复读）；
     换成 `"我不知道我不知道我不知道"`（4 字单元×3 次），对应日文源改
     为 `"分からない、分からない、分からない。"`。其余 8 条 brief 给定
     测试**未改动**。
   - 新增 `test_short_emotive_repetition_is_not_flagged`：断言
     `"对不起对不起对不起"`（3 字单元×3）、`"哈哈哈哈哈哈"`（2 字单元×3）、
     `"……………………"`（1 字单元×10）均不触发 C3。这是本轮问题的判别点，
     钉住后可防止未来再退化回 `{2,}`/`{3,}` 那种大面积误报。

### 验证

全量套件：

```
$ uv run pytest -q
........................................................................ [ 45%]
........................................................................ [ 90%]
...............                                                          [100%]
159 passed in 2.55s
```

（159 = fix 前 158 + 新增 1 条反向用例；改写的用例不增加计数。）

Step 5 重跑（`{4,}` 定值下，120 条已定稿锚点）：

```
保留人名 6 个；120 条已定稿锚点的告警数：0
```

**双侧突变验证**（验证 `{4,}` 确实被两侧夹住，不是偶然通过；均为临时改动，
未提交）：

突变 1——临时改回 `{2,}`，确认新增的反向用例转红（其余测试不受影响，证明
`{2,}` 对合法叠字/情绪表达误报）：

```
$ sed -i 's/LOOP_RE = re.compile(r"(.{4,}?)\\1{2,}")/LOOP_RE = re.compile(r"(.{2,}?)\\1{2,}")/' tools/detect_collapse.py
$ uv run pytest tests/test_detect_collapse.py -v
...
tests/test_detect_collapse.py::test_repeated_substring_loop_is_flagged PASSED
tests/test_detect_collapse.py::test_short_emotive_repetition_is_not_flagged FAILED
...
E   AssertionError: assert not [{'id': 11, 'rule': 'C3', ...}, {'id': 12, 'rule': 'C3', ...}, {'id': 13, 'rule': 'C3', ...}]
========================= 1 failed, 9 passed in 0.06s ==========================
```

突变 2——临时改为 `{6,}`（brief 原始下限），确认改写后的正向用例转红
（证明 `{6,}` 会漏检 4 字单元级退化）：

```
$ sed -i 's/LOOP_RE = re.compile(r"(.{2,}?)\\1{2,}")/LOOP_RE = re.compile(r"(.{6,}?)\\1{2,}")/' tools/detect_collapse.py
$ uv run pytest tests/test_detect_collapse.py -v
...
tests/test_detect_collapse.py::test_repeated_substring_loop_is_flagged FAILED
tests/test_detect_collapse.py::test_short_emotive_repetition_is_not_flagged PASSED
...
E   assert False
E    +  where False = any(<generator object ...>)
========================= 1 failed, 9 passed in 0.05s ==========================
```

还原为 `{4,}` 后复跑全量套件，159 passed，`git status` 干净（除本轮改动
的两个文件与本报告外，无残留改动）。

### 修复后 Self-Review 补充

- **Completeness**：10 条测试全部存在且通过（brief 给定 9 条 + 本轮新增
  反向用例 1 条）；`LOOP_RE` 定值有据可查（三类语料实测表格）、有双侧
  突变验证钉住边界。
- **Discipline**：仍未新增依赖；`RATIO_LO`/`RATIO_HI`/`KANA_MAX` 三个阈值
  常量全程未动；只改了 brief 允许范围内的那一条 C3 测试用例，其余 8 条
  逐字保留。
- **Testing**：GREEN 证据、Step 5 复验、双侧突变验证三项证据均完整记录
  在案。
