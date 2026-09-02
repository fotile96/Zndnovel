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
