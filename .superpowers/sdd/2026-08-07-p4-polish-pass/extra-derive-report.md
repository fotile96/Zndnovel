# extra 轨机械派生——实现与验收报告

任务：`extra` 轨（`data/batches.jsonl` 里 `lane=="extra"`，b174–338，829 条，当前 0 条已译）里
"能从已冻结的 `skeleton/` 骨架机械派生出来"的中文，先派生 + 出报告，**本轮不写生产数据**。

产物：
- `tools/derive_extra.py`（新增，纯 stdlib + pyyaml）
- `tests/test_derive_extra.py`（新增，23 条用例）
- `build/extra_derived.jsonl`（829 行，gitignore，不入库）
- `build/extra_derive_report.md`（逐条复核报告，gitignore，不入库）

## 派生规则的实现与理由

`extra` 轨 4 种 kind，键格式统一为 `"<file>:<line>[:idx]"` 字符串（非数字 id），ledger 是
`pilot/lanes/opus/data/ledger_extra.jsonl`。

### plot_title（195 条）
key 形如 `plotTitle:N`，`N` 即卡号。**先校验** `skeleton/cards.jp.yaml` 里卡 `N` 的
`title_jp` 是否与 ledger 的 `jp` **逐字相同**，通过才取 `skeleton/cards.zh.yaml` 卡 `N` 的
`title_zh`。这是任务里明确点名的第一处安全闸——"卡号对得上"不等于"文本对得上"，只按卡号
取值是恒绿形态。`derive_plot_title()` 校验失败（卡号未知 / jp 不逐字相同 / 卡号在 jp 里
但不在 zh 里）三种情况分别给出可读的异常原因字符串，全部标 `confidence=none`。

### scene_title（454 条，去重 393 种）
按 **jp 全文** 去 `cards.jp.yaml` 里找 `title_jp` **逐字相同** 的卡（`resolve_exact_title()`
用 dict 精确键查找，不用任何 `in`/子串手段），命中就取该卡 `title_zh`。这是第二处安全闸：
若改用「包含」匹配，"放課後の学校"（卡20/74标题「探索：放課後の学校」的真子串）之类的短
标题就会被张冠李戴地命中——判据过宽比不判更坏。

**发现的边界情形**：库里有且仅有两组"jp 全文逐字相同、但对应两张不同卡"的重复——
卡 20/74「探索：放課後の学校」、卡 85/119「屋上」。核实二者各自的 `title_zh` 完全相同
（"探索：放学后的学校"、"天台"），因此仍能给出确定的派生结果，但在报告与代码里都显式记录
了这个"同名多卡"事实（`ambiguous` 标志 + 报告异常区单列），不是悄悄吞掉。

### card_msg（172 条，12 种模板）
用正则把 `『…』`（卡名槽）与 `（…）`（分支说明槽）归一为占位符，得到模板骨架；172 条实测
恰好聚成 12 种（`template_of()`）。**本轮不决定模板本身怎么翻**——`zh` 恒留空、
`confidence` 恒 `none`（这是任务明确要求，不是遗漏）。但仍然验证 `『…』` 槽位内容是否为
一个真实冻结卡名：能对上的，`source` 写成 `template:<模板> + cards.zh:card=N（卡名已有
定稿）`，模板译文一旦定下即可机械拼接；对不上的单列为异常。

**发现的异常**：172 条里有 **14 条** 的 `『…』` 槽位不是卡名，而是章节梗概占位符
（`セクション１`…`セクション８`、`セクションＥＸ１`、`セクションＥＸ２`、以及
`いつか きみが みる お話`——注意这条与冻结卡 145 的标题 `いつかきみがみるお話。`
在空格与句号上都不同，不是同一字符串）。这些槽位装的是"章节代号/绘本篇名的另一种写法"，
不是 `plotTitle` 系统里的卡名，故派生不出，需人工核实后再定。

### savedata（8 条，3 条空串）
全部标 `none`，但**逐条输出**——空串是合法内容（如 `snr_fragment_main:372:2` 的 jp 就是
`""`），绝不能因为 `not row["jp"]` 之类的 falsy 判断被静默跳过。这是第三处安全闸，也是本
轮唯一一个"正确行为=什么都不做但仍要出现在输出里"的规则，最容易被写成"提前 return /
continue"而悄悄漏行。

## 实跑总览数字（对真实 `ledger_extra.jsonl` 829 条）

| kind | exact | template | none | 小计 |
|---|---:|---:|---:|---:|
| card_msg | 0 | 0 | 172 | 172 |
| plot_title | 195 | 0 | 0 | 195 |
| savedata | 0 | 0 | 8 | 8 |
| scene_title | 169 | 0 | 285 | 454 |
| **合计** | **364** | **0** | **465** | **829** |

`card_msg` 的 `template` 列本轮恒为 0——这是设计使然（12 种模板本身的译文本轮不定），不是
bug；等 12 句模板定稿后即可把 172 条从 `none` 机械升到 `template`。

## 异常一览（18 条）

- **14 条** `card_msg`：`『…』` 槽位内容不是任何冻结卡名（章节梗概占位符，见上）。
- **4 条** `scene_title`：jp 全文命中"同名多卡"（卡20/74、卡85/119 各 2 条出现），派生
  结果本身不受影响（两卡 zh 一致），仅作记录以备核查。

完整明细见 `build/extra_derive_report.md`（`## 异常一览` 节）与 `## card_msg 12 种模板
待定表` 节（12 种模板 + 出现次数 + 举例，供人定稿）。

## 测试与变异实况

`uv run pytest -q`：**833 passed**（基线 810 + 本轮新增 23，无回归）。

变异按"会不会在最该响的时候不响"设计，任务要求的三处安全闸全部配变异，用 Edit 应用/还原
（未使用任何 git 回滚类命令），每次变异后单独跑 `tests/test_derive_extra.py`，还原后用
`diff` 与预先保存在 scratchpad 的原始文件逐字节比对确认无残留：

| # | 变异内容 | 命中测试 | 结果 |
|---|---|---|---|
| 1 | `derive_plot_title` 删除 `jp_title != jp` 校验，只按卡号取值 | `test_derive_plot_title_jp_mismatch_must_not_derive` | 红（1 failed） |
| 2 | `resolve_exact_title` 改成"jp 是 title 子串即命中"（正向包含） | `test_derive_scene_title_substring_must_not_match` | 红（1 failed） |
| 2b | 同上，反向包含（"title 是 jp 子串即命中"） | `test_derive_scene_title_superset_must_not_match` | 红（1 failed） |
| 3 | `derive_savedata` 对空串 jp `return None`（当缺失跳过） | `test_derive_savedata_empty_string_still_produces_a_row` 等 5 条 | 红（5 failed，含 2 处 `TypeError` 崩溃） |

三处安全闸变异全部由测试单独抓住（非"测试无牙"，也非"变异没打中"——每处变异都精确对应
被删除/放宽的那一行判据，命中测试的失败原因与变异内容一一对应，无旁的测试意外变红或意外
仍绿的情况）。变异 2 额外验证了"包含"判据的两个方向（jp⊂title 与 title⊂jp）各有独立测试
把关，因为只测一个方向会漏掉另一方向的判据放宽。

还原后核对：
```
diff derive_extra.py.orig tools/derive_extra.py   # IDENTICAL
diff test_derive_extra.py.orig tests/test_derive_extra.py  # 未改动
git diff --stat   # 只剩 .claude/settings.json 与 data/api_ledger.jsonl（他会话未提交改动，未触碰）
uv run pytest -q  # 833 passed
```

## 其他测试覆盖

除三处安全闸的定向变异用例外，`tests/test_derive_extra.py` 还包括：
- 纯函数单测（`template_of`/`bracket_name`/`resolve_exact_title` 的正常路径与未命中路径）；
- `derive_all` 端到端不丢行的断言（含空 savedata 混合场景）；
- 未知 `kind` 不崩溃、但仍报异常（防止未来 ledger 出现第 5 种 kind 时被静默吞掉）；
- `build_report` 结构性检查（总览表、模板待定表存在）；
- `main()` 的 tmp_path 文件级集成测试（不落生产目录）；
- **对真实数据的冒烟测试**（`test_real_data_plot_title_all_195_exact_match`、
  `test_real_data_derive_never_drops_a_row_and_writes_nothing_to_pilot_dir`）：钉住
  "195/195 exact"这一已实测核对过的前提，未来 skeleton 或 ledger_extra 若有变动，测试会
  先叫出来，而不是让 `derive_extra.py` 静默产出变少的 `exact` 数。

## 硬约束核对

- `git status --short pilot/lanes/opus/data/` → 空，未写任何生产译文文件。
- `build/extra_derived.jsonl`、`build/extra_derive_report.md` 均落在已 gitignore 的 `build/`。
- `skeleton/`、`data/batches.jsonl`、`analysis/`、`lua_scripts/`、`png/` 全程只读（脚本内
  仅 `open(..., encoding="utf-8")` 读取，无写入调用）。
- 未触碰 `.claude/settings.json`、`data/api_ledger.jsonl`（工作树里这两个文件的既有改动
  来自其他并行会话，`git diff --stat` 显示其内容与本轮改动前完全一致）。
- 变异测试全程用 Edit 应用/还原，未使用任何 `git checkout`/`reset`/`stash` 等命令。
