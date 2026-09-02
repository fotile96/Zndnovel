# Task 6 报告：build_font 改造与 fonttools 依赖

commit `834a438` — `refactor: build_font 改为按给定字集构建 + fonttools 入依赖`（单个提交）。
BASE: f450584（Task 5 完成点）。分支 `feat/finale-stage`。

## 做了什么

1. **`uv add fonttools`**：`pyproject.toml` 新增 `fonttools>=4.64.0`，`uv.lock` 同步。之前
   venv 里没有它，`widen_latin()` 一跑就 `ModuleNotFoundError`。
2. **`tools/build_font.py` 重构**：
   - 删 `corpus_chars()`、`LANE` 常量、`from tools.pipelib import read_jsonl`、
     `from tools.resolve import resolve_map`。`ALWAYS` 保留（供 `tools/layers.py` 未来引用）。
   - 新增 `build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]`：
     把原 `main()` 的产 PGF 循环体抽出来，字集不再自己算，直接读调用方给的文件。
   - `main()` 改为纯 CLI 外壳：解析 `--charset`（缺省 `build/release/charset.txt`）、`--out`
     （缺省 `build/font`）、`--sizes`、`--ruby-size`，转换类型后调 `build()`。
   - `widen_latin()`/`embolden_diacritics()`/`PINYIN_CHARS`/`DIACRITIC_*`/`TTF_BY_SIZE`/
     `WIDEN_SIZES` 等未动。
3. **`layers/overlays/fonts.toml` 的 `why` 字段更正**（brief 之外、任务描述明确列入范围）：
   Task 5 删掉了 `inject_lua.py` 的 `FONT_SLOT1_FROM/TO`，槽 1 从此只有这一个层在改写；
   原 `why` 里「此刻仍由 inject_lua.py 执行」的表述随之作废，本次改写讲清楚现状。只动
   `why` 文本，`[[ops]]` 两个 `replace` 操作原样未碰。

## Brief 代码块的缺陷（本任务分内的"读critically"环节）

**发现**：Step 4 给的 `build()` 只检查了 `TTF_PGF.exists()` 与 `ttf.exists()`（字体源），
唯独没检查 `charset_path` 本身是否存在、是否为空。2026-09-03 用仓库里真实的
`/tmp/pgftool/ttf_pgf` 二进制实测两种输入：

```
$ /tmp/pgftool/ttf_pgf <ttf> out.pgf /tmp/does_not_exist.txt 17
（无输出，无报错）
$ echo $?
0
$ ls -la out.pgf
-rw-r--r--  1 fotile96  wheel  5319396 ...

$ : > /tmp/empty.txt
$ /tmp/pgftool/ttf_pgf <ttf> out.pgf /tmp/empty.txt 17
Load list from /tmp/empty.txt : 0
$ echo $?
0
$ ls -la out.pgf
-rw-r--r--  1 fotile96  wheel  5319396 ...
```

两种情况都是 exit code 0、产物照常落盘——`ttf_pgf` 遇到缺失/空字集会**静默退化成
渲染整个字库**（43478 字形、5,319,396 字节），不是"漏几个字"，而是模块 docstring 开头
那次 `sceFontOpenUserMemory` 引擎崩溃的原样复现。brief 给的
`proc.returncode != 0 or not out.exists()` 那道闸对这种输入完全失明。

这是本计划第 6 次在 brief 代码块里找到缺陷（前 5 次分别在 Task 1–5），性质与
"missing input validation → 静默产出错误但看似成功的结果"一致，直接撞上任务的全局约束
"Every correctness problem is a hard failure. No silent skips."。

**修复**：在 `build()` 里、`TTF_PGF` 检查之后加：

```python
if not charset_path.exists() or charset_path.stat().st_size == 0:
    sys.exit(f"字集文件缺失或为空: {charset_path}"
             f"（ttf_pgf 遇到这种输入会静默退化成全字库 5.3MB，撑爆引擎字体缓冲，"
             f"不是变小而是更危险，不能放行）")
```

并补一条回归测试 `test_build_font_rejects_missing_or_empty_charset`（见下方 TDD 证据），
用假 `ttf_pgf`（一个 touch 脚本）确认 Python 层的守卫本身会触发，不依赖真二进制。

**次要说明**：Step 4 docstring 原文写「2026-08-31 的缺字事故……6 个字进了盘却没有
字形」——日期照抄了字体最初裁剪的日期（8/31），但缺字事故本身发生在 **2026-09-02**
（谱系：spec 文档 `docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`
§12「2026-09-02 现状梳理」明确记录「7 个字空白——谢幕章 6 个……与 s7f 递卡旁白 1 个」，
且 `build/font/*.pgf` 的 mtime 也是 2026-09-02 23:32）。"6 个字"这个数字本身没错（就是
谢幕章那部分），但日期错了一天多、且省略了事故还有第 7 个字（s7f 的"挚"）。已在写入
`build()` docstring 时把日期改成 2026-09-02，其余不动（brief 没要求改这处，是我转录时
顺手核对发现的，量级比 charset 校验那个缺陷小得多，不算本任务主线发现，只在此存档）。

## 顺带处理：line 39 的 `os.environ.get` 双参数陷阱

任务描述里明确指名的最后一处遗留实例：`TTF_PGF = Path(os.environ.get("SNDL_TTF_PGF", ...))`。
`export SNDL_TTF_PGF=`（空串）时键存在、拿到 `""`，`Path("").expanduser()` 归一化成当前
目录 `.`，一个真实存在的目录，`exists()` 判断被这个假阳性骗过。改成
`Path(os.environ.get("SNDL_TTF_PGF") or "/tmp/pgftool/ttf_pgf")`，与
`tools/layers.py::provenance`、`tools/inject_lua.py` 同一惯例（那两处已在 Task 3/5 修过）。

## 测试

### TDD 证据

**RED**（brief Step 2 给的测试，实现前）：

```
$ uv run pytest tests/test_layers.py -q -k build_font
F                                                                        [100%]
...
E       AttributeError: module 'tools.build_font' has no attribute 'build'
1 failed, 45 deselected in 0.05s
```

**GREEN**（实现后）：

```
$ uv run pytest tests/test_layers.py -q -k build_font
..                                                                       [100%]
2 passed, 45 deselected in 0.79s
```

**第二条测试（我自己补的回归钉子，`test_build_font_rejects_missing_or_empty_charset`）
的 RED/GREEN**：先确认它在"有守卫"的实现上通过，再临时摘掉刚加的守卫代码块验证它会
失败（证明测试真的钉住了这个缺陷，不是摆设），再原样恢复。

RED（守卫摘掉后）：
```
$ uv run pytest tests/test_layers.py -q -k test_build_font_rejects_missing_or_empty_charset
F                                                                        [100%]
...
    missing = tmp_path / "missing.txt"
>       with pytest.raises(SystemExit):
E       Failed: DID NOT RAISE SystemExit
----------------------------- Captured stdout call -----------------------------
[font] 17px(渲染 17px) <- LXGWWenKai-Regular.ttf -> .../out1/lxgw17.pgf (0 B)
1 failed, 46 deselected in 0.16s
```

GREEN（守卫恢复后，用 `cmp` 确认恢复的文件与恢复前逐字节相同）：
```
$ uv run pytest tests/test_layers.py -q -k build_font
..                                                                       [100%]
2 passed, 45 deselected in 0.17s
```

### 字节级对比（本任务最重要的验证）

```
$ rm -rf /tmp/font_check
$ uv run python tools/build_font.py --charset build/font/ucs.txt --out /tmp/font_check --sizes 17
[font] 17px(渲染 17px) <- LXGWWenKai-Regular.ttf -> /tmp/font_check/lxgw17.pgf (490,956 B)
$ cmp /tmp/font_check/lxgw17.pgf build/font/lxgw17.pgf && echo "与现役字体逐字节相同 ✓"
与现役字体逐字节相同 ✓
```

`build/font/lxgw17.pgf` 大小同为 490,956 字节，`cmp` 无差异输出，退出码 0。

额外做了 brief 没要求、但覆盖 Task 8 将来会用到的默认路径（`sizes=(17, 9)`）的诊断性
复核——9px 槽（会触发 `widen_latin` 真跑一遍 fontTools）也逐字节相同：

```
$ rm -rf /tmp/font_check_9
$ uv run python tools/build_font.py --charset build/font/ucs.txt --out /tmp/font_check_9 --sizes 9
[font] 派生 ruby 字体: 步进撑全角 80 个，声调加粗 30 个 -> _widened09.ttf
[font] 9px(渲染 9px) <- _widened09.ttf -> /tmp/font_check_9/lxgw09.pgf (273,952 B)
$ cmp /tmp/font_check_9/lxgw09.pgf build/font/lxgw09.pgf && echo "9px 与现役字体逐字节相同 ✓"
9px 与现役字体逐字节相同 ✓
```

（中间派生的 `_widened09.ttf` 本身不是字节相同——用 fontTools 读出两份的 `head.modified`
时间戳不同，`TTFont.save()` 会把该字段写成保存时的当前时间，级联改变 `checkSumAdjustment`；
这只是 TTF 容器的保存时间戳，不含字形/度量信息，且从不进入最终 pgf、从不进包、从不是
Step 5 或本任务闸要求比对的对象，已用 fontTools 逐字段核实过差异确实只在这两个时间戳
相关字段，其余一致，故不视为需要处理的问题。）

**始终未触碰**：`build/font/lxgw17.pgf`、`build/font/lxgw09.pgf`、`build/font/ucs.txt`
三个文件的 mtime 全程未变（Aug 31 / Sep 2），只在 `/tmp/font_check*` 下产出对照副本。

### 闸

```
$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同
```
退出码 0。改动前后各跑一遍，结果一致——本任务没有改变闸覆盖的任何产物。

### 全量测试

- `tests/test_layers.py`：47/47（45 旧 + 2 新）
- `tests/test_layers.py` + `tests/test_layers_corpus.py`：55/55
- 全库 `uv run pytest -q`：**1749 passed, 4 skipped**（Task 5 完成点是 1747 passed/4 skipped；
  +2 对应本任务新增的两条测试；4 个 skip 与本次改动无关，是既有的"本机缺某资产/字体"跳过）

## 涉及文件

- `tools/build_font.py`（改）— 见上
- `tests/test_layers.py`（改）— 追加两条测试，共 +34 行
- `pyproject.toml`（改）— `+ "fonttools>=4.64.0"`
- `uv.lock`（改）— fonttools 及其记录同步
- `layers/overlays/fonts.toml`（改）— 只动 `why` 字段文本，`[[ops]]` 未动

未触碰、按要求保持原样：
- `build/font/lxgw17.pgf`、`build/font/lxgw09.pgf`、`build/font/ucs.txt`
- `.claude/settings.json`、`data/api_ledger.jsonl`、`data/event_op_text.jsonl`、
  `pilot/read-edits/opus.draft.jsonl`、`tools/bake_event_op.py`（另一会话的未提交改动）
- `tools/build_disc.py` 顶部的迁移期 `die()` guard（Task 4 加的，不归本任务处理）

## 自查（对照任务给的自查清单逐条过）

1. **`corpus_chars()` 是否真的连同专属依赖一起删干净了？** 是。`LANE`、
   `from tools.pipelib import read_jsonl`、`from tools.resolve import resolve_map` 三处
   一并删除；`grep -rn "import build_font\|from tools.build_font\|from tools import build_font"`
   确认改动前仓库里没有任何模块导入过 `tools.build_font`，删除没有产生悬空引用。
   `tools/migrate_base.py`、`tools/mine_dump.py`、`tools/saturation.py`、
   `tools/cluster_notes.py` 里同名的 `LANE`/`corpus_chars_from_ledger` 是各自模块独立
   定义的同名标识符，与本文件删掉的两个毫无关系，未被误动。
2. **`ALWAYS` 是否还在，因为 `tools/layers.py` 要引用它？** 在，一字未改。当前
   `tools/layers.py` 尚未真的导入它（那条线归 Task 8 的 `stage_font` 接线），已用
   `grep -n "ALWAYS" tools/layers.py` 确认——这与 brief"保留供引用"的措辞一致，不是我漏接。
3. **模块 docstring 是否还准确描述本模块现在做什么？** 已重写第三段：不再写"字集 = 译文
   ∪ 原文 ∪ ……"（那是 `corpus_chars()` 的算法，已不存在），改写为"字集不再由本模块自己算，
   现由 tools/layers.py 从 release 最终源机械算出"，并把日期更正为 2026-09-02（见上文
   "次要说明"）。
4. **测试验证的是行为还是复述实现？** brief 给的 `test_build_font_reads_charset_file_not_lane`
   端到端跑 `build()`（真实文件系统 + 假 ttf_pgf 子进程），断言产物文件名与
   `corpus_chars` 属性消失，是行为断言不是转述源码；我新加的
   `test_build_font_rejects_missing_or_empty_charset` 用摘掉/恢复守卫的方式证明了自己
   确实在钉一个真实缺陷（见上方 RED/GREEN），不是摆设断言。
5. **测试输出是否干净？** 是——过程中一度出现的 `DID NOT RAISE SystemExit` 失败是我特意
   制造的验证步骤（摘掉守卫验证 RED），不是遗留的失败状态；最终态全绿，附在报告里的
   两段输出已如实标注哪段是"预期失败"、哪段是"实现后通过"。

## 发现但不在本任务范围内处理的问题

- `tools/layers.py::_injected_sources()` 的 docstring 里仍写着"刻意不叠 inject_lua.main()
  里那段槽 1 字体补丁（FONT_SLOT1_FROM/TO）……两处都做会 count 断言拦下"——这段话描述的
  前提（inject_lua 还有槽 1 补丁可叠）在 Task 5 之后已不成立（inject_lua 现在哪个入口都
  不碰字体），属于同一种"散文与代码脱节"，但任务原文明确写"Change only the why text
  [of fonts.toml]. Do not touch the operations"，未把这处included 在范围内，故只记录、
  不改动。功能上无害：该函数行为不受影响，只是解释性注释的前提已经过期。

## 结论

- 测试：47/47（test_layers.py），全库 1749 passed / 4 skipped。
- 字节级对比：17px、9px 均与 `build/font/` 现役字体逐字节相同。
- 闸：`--compare-compiled` 230/230，exit 0（改动前后一致）。
- brief 代码块缺陷：找到并修复（`charset_path` 未校验 → 静默退化成全字库的隐患），
  补了会真的失败的回归测试。
- 任务指名的遗留缺陷（line 39 `os.environ.get` 双参数陷阱）：已修。
- 任务指名的文档漂移（`fonts.toml` 的 `why`）：已修，只动该字段文本。

---

## Fix round 1（回应 review 的 Important 发现）

commit `8c39932` — `fix: build_font 字集校验改按内容而非字节数——堵住 review 抓到的两个漏网案例`。
BASE: `61863ed`（`5b6cb75` 之后、controller 补齐 SDD 台账的那次 docs commit）。

### Review 说了什么

Important 发现：`build()` 的守卫 `not charset_path.exists() or charset_path.stat().st_size == 0`
查的是字节数，不是内容。Review 用真实 `/tmp/pgftool/ttf_pgf` 复现了两个近似漏网案例：

1. 全空白字集文件（`printf '\n\n'`，`st_size==2`）——过旧 guard，`ttf_pgf` 解析出 0 个码位后
   静默退化成全字库（43478 字形、5,319,396 字节），exit code 0。
2. 截断到只剩 5 个合规码位的字集文件——过旧 guard（字节数非零），`ttf_pgf` 照单全收，产出
   一份体积正常、看着人畜无害、实则漏掉几乎全部字符的 pgf——2026-09-02 事故的失败模式本身。

要求的修复分三部分（均已落实）：
1. 按 `write_charset()` 的行格式在 Python 里解析字集文件，数出真正解析成功的码位数；
   解析出 0 个直接硬失败，消息里带读了几行、解析出几个。
2. 解析出的码位数低于 `ALWAYS` 的码位数就硬失败——原则性下限，因为 `ALWAYS` 无条件并入
   `charset_of()` 算出的每一份字集。
3. 每次 `ttf_pgf` 调用后解析它自报的 `Load list from ... : N`，与 Python 侧解析出的码位数
   核对；核对不上或找不到这行都硬失败。

### 我做了什么

**新增 `_read_charset(charset_path) -> tuple[int, list[int]]`**（`tools/build_font.py:170-180`）：
按 `_UCS_LINE_RE = re.compile(r"^[0-9a-f]{4}$")`（`write_charset()` 唯一会产出的行形状）逐行
解析，返回 `(物理行数, 解析出的码位列表)`。这个正则比 `ttf_pgf` 自己的 C 侧解析器
（`/tmp/pgftool/libpgf.c::load_ucs_list()`）严格得多——读过它的源码后确认：它只要一行的
首字节不是 `#`/`\n`/`\r`/NUL 就把这一行计入返回的行数 `i`，哪怕 `sscanf(lbuf, "%x", &ucs)`
根本没解析出东西（`ucs` 留在初值 0，仍会 `list[0]=0`、`i++`）。两边"合规"标准不同是刻意的：
Python 侧从严，第三道检查兜底两边分歧。

**`build()` 里的三道检查**（`tools/build_font.py:190-220`、`235-249`）：
- 第零道（沿用，未变）：`charset_path.exists()`。
- 第一道：`_read_charset()` 解析出 0 个码位 → `sys.exit`，消息含"读到 N 行，没有一行合规"。
- 第二道：解析出的码位数 < `len(set(ALWAYS))` → `sys.exit`，消息含解析出几个、下限是多少。
- 第三道（在 `for size in sizes:` 循环内、`ttf_pgf` 调用之后）：`_LOAD_LIST_RE.search(proc.stderr)`
  抓 `Load list from ... : N`；抓不到本身就硬失败（"输出格式可能变了，不能假装通过"）；
  抓到但 `N != len(codes)` 也硬失败。

**关于 stdout vs stderr（实测，不是猜的）**：用 `subprocess.run(..., capture_output=True)`
分流 `proc.stdout`/`proc.stderr` 实测确认 `Load list from ... : N` 打在 **stderr**——
与 `/tmp/pgftool/libpgf.c:256` 的 `fprintf(stderr, "Load list from %s : %d\n", ...)` 一致。
用 `2>&1` 混流时（我第一轮报告里的手工探测就是这么做的）看不出这个区别，容易记错，
所以特意在 `_LOAD_LIST_RE` 旁边写了一句注释存证。

```
$ uv run python3 -c "
import subprocess
proc = subprocess.run(
    ['/tmp/pgftool/ttf_pgf', '.../third_party/LXGWWenKai-Regular.ttf',
     '/tmp/probe_out.pgf', '/tmp/probe_empty.txt', '17'],
    capture_output=True, text=True)
print('STDOUT repr:', repr(proc.stdout))
print('STDERR repr:', repr(proc.stderr))
"
STDOUT repr: ''
STDERR repr: 'Load list from /tmp/probe_empty.txt : 0\n'
```

### 一处主动偏离 review 字面表述，并说明理由

Review 原话："Reject when the parsed count is below `len(ALWAYS)`... any legitimate set
contains at least those 495 code points." 我在实现前用 `uv run python3` 核实了这个数字：

```
$ uv run python3 -c "
import tools.build_font as bf
print('len(ALWAYS):', len(bf.ALWAYS))
print('len(set(ALWAYS)):', len(set(bf.ALWAYS)))
"
len(ALWAYS): 495
len(set(ALWAYS)): 472
```

`ALWAYS` 列表本身有 23 个重复码位（如全角括号"（）"，同时出现在手写符号串
`"≪≫≦≧【】…（）…"` 与 `range(0xFF01, 0xFF5F)` 全角形区段里）。而 `tools/layers.py::charset_of()`
构造字集时是 `chars: set[int] = set(always)` ——**经过集合去重**。这意味着 review 陈述的
理由本身（"any legitimate set contains at least those code points"）成立的前提是「去重后
的码位数」，而 495 是未去重的列表长度。若字面按 495 当下限，一份恰好只包含 ALWAYS、
不多不少的合法字集（`len(codes)==472`）会被这道检查错误地拒绝——这本身就是一个会拒绝
合法输入的 bug，方向是"过严"而不是本任务反复强调的"宁滥勿缺"。

所以实现里用的是 `min_codes = len(set(ALWAYS))`（472），并在代码注释里完整写出这段推理
（`tools/build_font.py:209-215`），没有默默改数字了事。实践中这个差异几乎不会被触发
（真实字集有几千个码位，472 与 495 的差别毫无意义），但既然 review 明确要求"把推理写进
注释里，因为推理才是这道下限站得住脚的原因"，我认为把推理做对、而不是照抄一个和推理本身
对不上的数字，是对这个要求更忠实的回应。

### Optional 建议（6 个字 vs 7 个字）的处理

Review 的 optional 建议是把 `build()` 文档字符串里的"6 个字"直接改成"7"，与模块开头段
对齐。我核实后发现两个数字本来就不是同一件事：模块开头段的"7"是**事故总数**（谢幕章 6 字
+ s7f 递卡旁白"挚"字 1 个）；`build()` 文档字符串的"6"指的是**"编外源不在视野里"这一条
结构性根因单独造成的数量**——s7f 的"挚"是另一个原因（字体在 8/31 裁剪后，译文又
改了两轮，没人重新跑 `build_font.py`，纯粹是过期，和 `corpus_chars()` 看不看得见编外源
无关）。把"6"直接改成"7"会让这句话变得不准确（暗示全部 7 个空白都是结构性根因造成的）。
改为让两处数字的范围各自明确、互相呼应而不是表面对齐：

```
⚠ 不再自己算字集：2026-09-02 缺字事故（共 7 处空白，见模块开头段）里，
「编外的谢幕章源不在视野里」这一条根因单独造成了其中 6 字——这正是
corpus_chars() 必须删除的原因。
```

### TDD 证据：四条新回归测试，均先证明 RED

用 `git show 834a438:tools/build_font.py` 取出**修复前**（本任务第一轮提交、review 之前）
的 `build()`，临时换上，跑新加的四条测试，确认全部失败：

```
$ cp tools/build_font.py /tmp/build_font_new_fixed.py
$ git show 834a438:tools/build_font.py > /tmp/build_font_old.py
$ cp /tmp/build_font_old.py tools/build_font.py
$ uv run pytest tests/test_layers.py -q -k "test_build_font_rejects_whitespace_only_charset or test_build_font_rejects_truncated_charset or test_build_font_rejects_ttf_pgf_load_count_mismatch or test_build_font_rejects_when_load_list_line_missing" -v
...
FAILED tests/test_layers.py::test_build_font_rejects_whitespace_only_charset
FAILED tests/test_layers.py::test_build_font_rejects_truncated_charset - Perm...
FAILED tests/test_layers.py::test_build_font_rejects_ttf_pgf_load_count_mismatch
FAILED tests/test_layers.py::test_build_font_rejects_when_load_list_line_missing
4 failed, 47 deselected in 0.31s
```

（`truncated` 那条报 `PermissionError` 而不是"DID NOT RAISE"：旧 `build()` 没有前两道检查，
会一路走到 `subprocess.run()` 试图执行测试夹具里那个只 `write_text("")`、没 `chmod +x`
的占位文件——这本身就是**因为旧代码完全没有校验、直接冲到子进程调用**的证据，效果上仍是
"这条测试在旧代码上失败"。）

恢复修复后的版本，确认全部转绿：

```
$ cp /tmp/build_font_new_fixed.py tools/build_font.py
$ diff /tmp/build_font_new_fixed.py tools/build_font.py && echo "restored OK, identical to fixed version"
restored OK, identical to fixed version
$ uv run pytest tests/test_layers.py -q -k build_font -v
collected 51 items / 45 deselected / 6 selected
tests/test_layers.py ......                                              [100%]
6 passed, 45 deselected in 0.34s
```

六条测试（2 条既有 + 4 条新增）：
- `test_build_font_reads_charset_file_not_lane`（brief 原有）——夹具从 2 个码位改成
  `sorted(set(bf.ALWAYS))`（真实场景不会踩中新下限），fake ttf_pgf 换成会在 stderr 报
  正确 N 的版本（否则会被自己加的第三道检查拦下）。
- `test_build_font_rejects_missing_or_empty_charset`（本任务第一轮新增）——未改动，
  缺失文件走"不存在"分支、0 字节文件走"0 个码位"分支（Part 1），两者在新实现下依然
  各自成立，不需要动。
- `test_build_font_rejects_whitespace_only_charset`（新增）——钉 review 案例 1。
- `test_build_font_rejects_truncated_charset`（新增）——钉 review 案例 2。
- `test_build_font_rejects_ttf_pgf_load_count_mismatch`（新增）——钉第三道检查的"数字对
  不上"分支。
- `test_build_font_rejects_when_load_list_line_missing`（新增）——钉第三道检查的"这行
  根本找不到"分支。

新增了一个测试辅助 `_fake_ttf_pgf(path, honest=True)`：`honest=True`（默认）时用
`wc -l < "$3" | tr -d ' '` 动态数字集文件的行数，在 stderr 打印匹配的
`Load list from $3 : $n`，供"正常路径"的测试复用而不必每次手写；`honest=False` 时只
`touch` 不打印，专供"ttf_pgf 没吐这行"的测试用。

### 字节级对比（复核）

```
$ rm -rf /tmp/font_check_review && uv run python tools/build_font.py \
    --charset build/font/ucs.txt --out /tmp/font_check_review --sizes 17
[font] 17px(渲染 17px) <- LXGWWenKai-Regular.ttf -> /tmp/font_check_review/lxgw17.pgf (490,956 B)
$ cmp /tmp/font_check_review/lxgw17.pgf build/font/lxgw17.pgf && echo "17px 与现役字体逐字节相同 ✓"
17px 与现役字体逐字节相同 ✓

$ rm -rf /tmp/font_check_review9 && uv run python tools/build_font.py \
    --charset build/font/ucs.txt --out /tmp/font_check_review9 --sizes 9
[font] 派生 ruby 字体: 步进撑全角 80 个，声调加粗 30 个 -> _widened09.ttf
[font] 9px(渲染 9px) <- _widened09.ttf -> /tmp/font_check_review9/lxgw09.pgf (273,952 B)
$ cmp /tmp/font_check_review9/lxgw09.pgf build/font/lxgw09.pgf && echo "9px 与现役字体逐字节相同 ✓"
9px 与现役字体逐字节相同 ✓
```

两次都用真实 `build/font/ucs.txt`（16945 字节、真实生产字集）跑通了新加的第三道检查
（`ttf_pgf` 自报的 N 与 Python 侧解析出的码位数一致，未触发 sys.exit）——这不只是单元
测试用假脚本验证，是新校验逻辑在真实二进制、真实大字集上的一次端到端确认。
`build/font/{lxgw17.pgf,lxgw09.pgf,ucs.txt}` 全程未被写入。

### 闸与全量测试

```
$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同

$ uv run pytest tests/test_layers.py -q
51 passed in 1.22s

$ uv run pytest -q
1753 passed, 4 skipped in 306.21s (0:05:06)
```

（Fix round 前是 1749 passed；+4 条新测试 = 1753，4 skipped 不变，与本轮改动无关。）

### 文件改动

- `tools/build_font.py`——新增 `import re`、`_UCS_LINE_RE`/`_LOAD_LIST_RE`/`_read_charset()`，
  `build()` 的字集校验从"存在且非空字节"改为三道内容级检查，docstring 的"6/7"措辞调整。
- `tests/test_layers.py`——新增 `_fake_ttf_pgf()` 辅助、4 条新回归测试；修复 2 条既有测试
  的夹具以适配新的下限检查。

未触碰、按要求保持原样：`build/font/lxgw17.pgf`、`build/font/lxgw09.pgf`、`build/font/ucs.txt`；
另外 5 个另一会话的未提交文件。

### 结论

- Important 发现：三部分均已实现，均按 review 给的方案；下限数值一处从 495 主动改为
  472（`len(set(ALWAYS))`），理由已写进代码注释与本报告。
- 四条新回归测试全部完成 RED（对 834a438 的修复前实现）→ GREEN（对修复后实现）的完整
  闭环验证。
- 字节级对比：17px、9px 仍与 `build/font/` 现役字体逐字节相同（含新校验逻辑在真实
  二进制上的端到端验证）。
- 闸：`--compare-compiled` 230/230，exit 0。
- 全库：1753 passed（+4），4 skipped（不变）。
- Optional 建议（6→7）：未照字面执行，采用了保留精确性的改法，理由已详述。
