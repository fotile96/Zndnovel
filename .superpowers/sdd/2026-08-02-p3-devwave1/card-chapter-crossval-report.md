# card_chapter.yaml 全量交叉校验补漏（P3 devwave1，SEG-2 开工前必修）

## 背景

`config/card_chapter.yaml` 196 条 card→章节短码 映射是手工推导的，供
`tools/ayano_test.py` 的反剧透闸使用。此前 `tests/test_ayano_test.py::
test_real_card_chapter_data_gate` 只硬编码断言了 8 个卡号（41/44/45/46/58/
134/141/142，Critical 原始证据）。终审的变异测试证明：把清单外的卡改早
（实测卡 140，`s6f`→`s1s`）全套测试仍全绿——泄题口重新打开而机检不响。

本次补一条**读真实配置、覆盖全部 196 条**的交叉校验，用独立事实源验证，不
重写 `assemble_context` 的过滤逻辑本身（避免同义反复）。

## 独立事实源与覆盖分类

推导逻辑集中在新增的 `tools/verify_card_chapter.py`（可独立重跑：
`uv run python tools/verify_card_chapter.py`），断言在
`tests/test_card_chapter_crossval.py`。四类独立源恰好精确覆盖全部 196 条，
无缺口：

| 类别 | 卡号范围 | 条数 | 独立源 |
|---|---|---|---|
| A. 场景/选择卡 | 157 张（散布全表） | 157 | `data/scene2card.json`（sceneId→card 的流水线独立产物）。章节短码 = sceneId 第一个下划线前的部分（`s2s_390`→`s2s`），`sof`→`s0f` 特例（sceneId 字面拼写与章节短码不一致，CLAUDE.md 已记载，两者同为段 0，无行为差异）。 |
| B. 章节梗概卡 | 133–145 | 13 | `lua_scripts/` 里 `gameSave.myCard[N].hold = 1` 的**赋值**语句（正则要求字面单个 `=`，排除 `== 1`/`== -1` 判断行——判断行在本仓库风格里恒以 `then` 收尾，赋值行不会，已用此差异消歧）所在文件；文件名按 `snr_<章号>_10_<模式>.lua` → `<章号><模式>` 规则换算章节短码（与 CLAUDE.md `comSectionUID2ScriptFileName` 一致）。 |
| C. 关键词卡 | 95-97/105-107/109/114-117/119-132 | 25 | 22 张同 B 的赋值定位法，落在对应 `_s` 故事脚本里；3 张（97/115/126）查无直接闭包，改走"crd 主卡侧生"路径：`snr_crd_<主卡号>.lua`（crd 文件号即其主卡号）内对 `myCard[97/115/126].hold = 1` 的侧生赋值，定位到主卡号（56/51/10），再用 scene2card.json **独立换算**主卡的章节（不信任 card_chapter.yaml 自己对这 3 张卡的说法，也不信任对主卡的说法——全部重新推导）。 |
| D. 编外卡 200 | 200 | 1 | 全仓库 `lua_scripts/` 唯一一处提及：`snr_e2_10_f.lua` 内 `oCard.show(cGetFileName("card", "crd_200_a"), ...)`（EX2 章节完成时展示）。按文件名规则换算得 `e2f`。**只能单源确认，无法多源交叉**——如实记录，未编造第二个源。 |

157+13+25+1 = 196，与 `config/card_chapter.yaml` 现有条数精确一致，测试
`test_full_196_coverage_by_independent_sources` 断言了这一点（多则报多余、
少则报缺口，不静默通过）。

`data/scene2card.json` 形态核实：157 条，无 `keyword` 噪声键（CLAUDE.md 记载
的 `sceneId2aCard.keyword=N` 反编译噪声已被这份独立产物滤除），已用
`test_scene2card_is_clean_no_keyword_noise` 固化这一前提。

## 无法独立验证的卡

无。四类独立源合计精确覆盖全部 196 条，没有任何一条只能靠"人工裁定、无独立
源"这种降级断言。原文件头注释里"97/115/126 查无直接闭包"的说法属实，但通过
crd 主卡侧生路径 + scene2card 独立换算，仍能给出不依赖 card_chapter.yaml 自
证的期望值；编外卡 200 虽只有单一独立引用（无法多源交叉），但该引用本身就
是与 card_chapter.yaml 完全无关的独立数据点，故仍计入"可验证"而非"无法验证"。

## 变异自检（硬要求 1）

对内存中的 `card_chapter.yaml` 副本做变异（不改磁盘文件），调用
`crossval()`：

- 卡 140 由 `s6f` 改为 `s1s`（终审证明能让原套件恒绿的那个变异）：
  `crossval()` 报出 `卡140：card_chapter.yaml 写 's1s'，独立源推出 's6f'`——
  **被捕获**。断言见 `test_crossval_catches_card_140_mutation`。
- 补充做了卡 41（A 类，场景卡）的同类变异（`s2s`→`s1s`）与整表清空
  （`{}`）两个变异，均被捕获（分别见
  `test_crossval_catches_arbitrary_scene_card_mutation`、
  `test_crossval_catches_wholesale_clear`，后者报出 196 条不一致）。

手动复核（非 pytest，交互式验证独立函数行为）：
```
mutated = dict(cc); mutated[140] = 's1s'
crossval(mutated) == ["卡140：card_chapter.yaml 写 's1s'，独立源推出 's6f'"]
```
实测输出与上述一致。

## 反向校验（硬要求 2）：196 条现行映射 vs 独立源

`test_real_card_chapter_yaml_has_zero_mismatches_against_independent_sources`
对当前入库的 196 条逐一比对四类独立源，**结果：零不一致**。逐类明细：
- A 类 157 条：全部匹配（`test_scene_cards_cover_157_and_match_card_chapter`）。
- B 类 13 条：全部匹配，含卡 140（`test_chapter_summary_cards_cover_13_and_match_card_chapter`）。
- C 类 25 条：全部匹配，含侧生路径的 97/115/126（`test_keyword_cards_cover_25_and_match_card_chapter`）。
- D 类 1 条（200）：匹配（`test_card_200_single_independent_reference_matches`）。

**未发现真错误**——当前入库的 `config/card_chapter.yaml` 在可独立验证的全部
196 条上都是对的。未改动该文件的任何数据。

## 交付物

- `tools/verify_card_chapter.py`（新增，可复用/可手动重跑）：独立推导四类
  期望映射 + `crossval()` 比对函数 + CLI 报告（`main()`，非零退出码表示发现
  不一致）。
- `tests/test_card_chapter_crossval.py`（新增，10 条测试）：形态核实、四类
  分别覆盖与匹配、全量 196 覆盖、反向零不一致、三个变异自检（卡140/卡41/
  整表清空）。
- 未改动 `config/card_chapter.yaml`、`lua_scripts/`、`data/scene2card.json`、
  `analysis/`、`skeleton/`（全部只读）。
- 未触碰 `pilot/lanes/`、`prompts/`、SEG-1/SEG-2 相关 SDD 计划文件。

## 验证

`uv run pytest -q` → 354 passed（基线 344 + 新增 10，全绿，无回归）。
