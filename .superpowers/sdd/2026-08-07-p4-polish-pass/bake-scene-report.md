# 烤字回填试片报告：`png/scene/`（场景名条集）

状态：**DONE**（PNG + 规格文档产出，不含 `.gim` 回转——用户已明确限定范围）

**更新（字号调档，见第 10 节）**：用户看过 9px 成品后要求出字号对照，看过对照后选定
**10px**（`FONT_SIZE` 9→10、`TEXT_BOX` 边距 5→3px）。`build/scene_zh/` 已用新参数全量
重新生成；195 条标题实测 overflow=0/ink_outliers=0/pixel_preservation_violations=0；
新增 `tools/bake_scene_size_ab.py` 产出 `_size_ab.png` 供 9px/10px 直接 A/B。

这不是本 SDD 台账（`2026-08-07-p4-polish-pass`）计划内的任务编号，是并行的
「烤字回填第二块试片」独立交办，报告按用户指定路径落在这里，方法论沿用
`bake-plot-report.md`（第一块 `plot/` 的成品）。

## 一句话摘要

`png/scene/` 两张场景名条集（`scene_1_a.png`/`scene_2_a.png`，3×34 网格/张，
共 204 格）全部替换为 `skeleton/cards.zh.yaml` 的中文定稿（195 条，与 `plot/`
**完全同一份数据源**——任务交办文档假设的「454 条 scene_title 数据集」经代码
+像素证据核实后确认**不是**这批图的来源，见第 2 节）。非 TEXT_BOX 区域像素
逐字节保真（195 格全量跑批 0 违规，自动闸 + 3 组必做变异全部证实有牙）；
195 条中文标题在选定字号下 **0 条**触发截断，且截断机制本身用合成用例验证过
确实能触发、能报出。`__scene_{1,2}_a.png` 两个双下划线前缀文件经查是转换
链路留下的、引擎从不加载的未量化中间产物，本任务不做任何处理，只记录发现。

产物：`build/scene_zh/scene_{1,2}_a.png` + `_compare.png`（整图对照）+
`_cellzoom.png`（12 格放大对照）+ `manifest.json`；工具 `tools/bake_scene.py`；
测试 `tests/test_bake_scene.py`（22 条）；测绘文档
`build/scene_layout_spec.md`。全量套件 `uv run pytest -q`：**960 passed**
（本任务净增 22 条；另有 40 条净增来自并行会话同期落地的其它工作，不属于本
任务范围，详见第 8 节说明）。

## 1. `__scene_{1,2}_a.png`：查明结论与证据

**结论（把握程度：高）**：这是 `.gim`→`png` 转换链路留下的**未量化中间产物**，
**不是游戏引擎会加载的资源**，本任务不做任何处理。

**证据链**：
1. **全仓库唯一性**：`find png -iname "__*"` 在整个 `png/` 树下只命中这两个
   文件，其它资源夹（`plot/`/`card/`/`select/`/`event/` 等）都没有对应的
   `__` 版本。
2. **零引用**：`grep -rn "__scene" lua_scripts/*.lua` 零命中——没有任何脚本
   通过这个文件名加载资源。对照正式版本：
   `snr_common.lua:5059-5060` 的
   `comLayerLoadFalse(layerName.scene_1_a, cGetFileName("scene", "scene_1_a"))`
   / `"scene_2_a"` 才是真正被 `main()` 加载进内存的两张图。
3. **模式差异**：正式版本是 `P`（调色板）模式，带逐调色板项 alpha 的满
   tRNS 表——与 `plot/` 的调色板形态相同（`.gim` 转换工具的标准输出形态）；
   `__` 版本是 `RGBA`（无调色板），更像转换前的中间产物。
4. **像素级比对**：全图逐像素比较（435×510×2 张），**RGB 分量在任意一个
   像素上都完全相同**（恒为 `(0,0,0)`——这批图本来就只有黑色内容，见第 4
   节）；差异**只出现在 alpha 通道**，且只集中在文字笔画与四角缺口装饰的
   抗锯齿过渡带（34511/221850≈15.6% 的像素有差异，最大差值达 255），与
   "P 模式量化把连续 alpha 取整到离散调色板项"这个假说完全吻合。

**处置**：保留原样，不烘焙、不产出对应的中文版本——引擎从不读它，本轮
不修改这两个文件（`png/` 本身也是只读原始资产），只在此记录发现供后续参考。

## 2. 格号 → 内容映射：证据链，以及「域是 195 张卡，与 `plot/` 相同」这条
   与任务交办假设相反的核心发现

**结论**：`sceneState` 数组（`lua_scripts/snr_common.lua:955-984`）用**卡号**
（1..195，与 `plotState`/`plotTitle` 完全同一个域）索引，行优先铺满每张
sheet 的 3×34 网格，每 102 张卡换页（sheet1=1-102，sheet2=103-195+9 空格）。
**这批图烘焙用的中文源就是 `skeleton/cards.zh.yaml` 的 `title_zh`（195
条）——与 `plot/` 完全同一份数据**，不是任务交办文档假设的
`build/extra_derived.jsonl` 里 `kind=="scene_title"` 那 454 行。

**三层独立证据**：

### 2.1 一手：lua 源码（构造方 + 两处独立消费方，参数一致）

`sceneState` 构造循环（`snr_common.lua:955-984`）与 `plotState` 结构同构，
仅参数不同（3 列非 6 列、每 102 张卡换页非 60）。两处消费点都用**卡号**索引：
- `comSectionStoryStart(p0, p1, p2)`（`:2012`）：`sceneState[sceneId2aCard[p0]]`
  ——`p0` 是 sceneId，经 `sceneId2aCard` 转成卡号才查表；**函数收到的第二个
  参数 `p1`（scene_title 字符串）在函数体内完全没被用来索引 `sceneState`**。
- `comSectionCardStart`（约 `:2489`）：`sceneState[p1]`，`p1` 直接是卡号
  （`fragmentDoCardId`），且与同一行代码块里的 `plotTitle[p1]` 共用同一个
  卡号——`sceneState` 与 `plotTitle` 在源码里是同域伙伴，这是最直接的代码
  证据。

### 2.2 二手：23 个跨全域像素样本，与 `plotTitle[N]` 逐字精确匹配

裁出预测格子目视核对，**23/23 全部精确一致，0 处不符**，样本特意覆盖
「另一条 scene_title 数据集字符串模糊匹配也关联不上任何卡号」的一批（见
第 3 节）：卡 1/2/9/50/60/74/90/95/96/97/100/102/103/105/109/114/120/130/
133/140/145/150/170/175/180/182/190/195（实际跑了 23 张，含单字标题「春」
（卡118）、片假名人名（卡114「ナオヤ」/124「サクラ」/115「アヤノ」）、全角
拉丁（卡133/137/138/140「Ｓｅｃｔｉｏｎ…」）、长标点句（卡90/180/182）等
极端情况，无一例外精确匹配）。

### 2.3 反证：454 行「scene_title」数据集走的是完全不同的运行时路径

`build/extra_derived.jsonl` 里 `kind=="scene_title"` 的 454 行，是全仓库
229 个 lua 脚本中所有 `scene_X(id, "标题")` 调用点字面量第二参数的抓取结果
（对应各脚本里 `scene_s1s_20 = function(scene_id, scene_title)` 这类函数
定义的形参名）。这个字符串确实被使用，但走的是
`comSectionStoryBegin(p0, p1)`（`:2373`）：
```lua
gameSave.sceneName = p1
savedataTitle(p1, v1)               -- 存档列表 UI 副标题，引擎实时字体渲染
comSectionStoryStart(gameSave.sceneId, gameSave.sceneName, gameSave.ayanoTime)
```
——喂给**存档列表界面**的副标题文字（引擎实时渲染，从不烤进任何 PNG）。而
它调用的 `comSectionStoryStart` 内部（2.1 节已述）根本不用这第二个参数去
查 `sceneState`。**两条路径消费的是同一批 `scene()` 字面量字符串里的同一个
参数位置，但喂给两个完全独立的界面元素**——一个是本任务要烤的 PNG 条带
（域=195 张卡），一个是引擎实时渲染的存档列表文字（域=所有 scene() 调用点，
与卡片数量无关）。

## 3. 「454 / 393 / 204 / 195」数量关系——完整解释

- **454**：`scene_title` kind 的原始抓取行数（`scene()` 调用点计数，一个
  场景在 DAG 里可能被多条分支路径各自触发一次调用，同一标题字符串会重复
  出现）——这是"存档列表副标题"数据源自己的计数，与本任务的 PNG 无关。
- **393**：454 去重后的唯一字符串数——仍是该数据源自己域内的去重。
  （交叉验证：其中 169 行已被另一条流水线用**精确字符串匹配**关联到某张
  卡的 `title_zh`，对应 155 个唯一 jp 字符串/155 个不同卡号——这只是"字面量
  文本恰好等于某张卡标题"的部分重合，不是本资源的域定义；238 个唯一 jp
  字符串完全关联不上任何卡号，证明 393 这个集合本身就不是 195 张卡标题的
  超集/子集，是另一个概念的数据。）
- **204**：`scene_1_a.png`+`scene_2_a.png` 两张图的物理网格容量（2×102）。
- **195**：本资源真正烘焙使用的域——`sceneState` 循环本身的上界
  （`for i8 = 1, 195`），与 `plotTitle[1..195]`/`skeleton/cards.zh.yaml`
  完全同域，204−195=9 格空置（第 4.1 节验证）。

**结论**：454/393 描述的是一个完全不同的运行时文字表面（存档列表副标题，
不在本仓库任何 PNG 里），本任务的正确中文源是 `skeleton/cards.zh.yaml` 的
`title_zh`（195 条），**不是** `kind=="scene_title"` 那 454/393 行——这是
对任务交办假设的一处实质性修正，详细测绘写在
`build/scene_layout_spec.md` 第 2-3 节。

## 4. 底色形态：纯色半透明条带，不是照片——与 `plot/` 最大的不同

`plot/` 每格背后是该卡场景的暗化缩略截图（照片，逐格不同）；`scene/`
**完全不是**：

- 卡1/卡2（同一张 sheet 内相邻格）、卡1/卡150（跨 sheet、内容完全不同）
  的 TEXT_BOX 外像素逐字节比较，**结果完全相同**——背景是跨格、跨图共享
  的同一份模板，不是逐格美术内容。
- 195 格全量扫描（剔除各格自身墨迹±1px 邻域）：背景像素 **RGB 恒为
  `(0,0,0)`（100%）**，只有 alpha 变化，**98.9%** 精确等于 **153**，其余
  1.1% 集中在四角装饰缺口的抗锯齿过渡带。
- 四角缺口装饰只出现在 `x∈[0,4]∪[140,144]`（左右各 5px），195 格实测墨迹
  从未进入这两列区间——两者互不重叠，这正是选定
  `TEXT_BOX=(5,0,140,15)` 作为**全局固定矩形**（不像 `plot/` 需要逐格动态
  测算色带高度）就足够安全的直接证据。

**这意味着**擦除策略比 `plot/` 简单：不存在"盖多了就丢照片细节"的取舍，
`TEXT_BOX` 内部本来就是同一块纯色，不需要 `plot/` 那套逐格墨迹高度+
hard/soft 双档色带机制。完整测量方法与数据见 `build/scene_layout_spec.md`
第 4 节。

## 5. 排版取值依据

- **中文源**：`tools.bake_plot.load_titles_zh()`（复用，不重复实现）——
  `skeleton/cards.zh.yaml` 的 `title_zh`。
- **字体/字号**：`LXGWWenKai-Regular.ttf` @ **9px**——该字体在此字号下恰好
  给出 9px/字的前进量与 9px 字形高度，与原文测出的 ~9px/字前进量精确匹配。
- **`TEXT_BOX=(5,0,140,15)`**：宽度 135px（原文墨迹 x 范围从未跨出
  `[5,139]`），高度取满格高 15px（原文墨迹 y 范围 `[3,11]`，取满格高既
  给中文渲染留出安全边，又已确认四角装饰完全不进入 `x≥5` 区间，不会被
  碰到）。
- **居中渲染**：`anchor="mm"`，锚点 = TEXT_BOX 几何中心 `(72.5, 7.0)`——
  复刻原文水平垂直双向居中的版式（**与 `plot/` 的左对齐顶对齐不同**，
  没有照抄）。
- **单行**：`MAX_LINES=1`——15px 格高结构性不允许第二行，195 格原文实测
  从未出现两行。
- **擦除：直接覆写像素，不做半透明合成**——`ImageDraw.rectangle` 在 RGBA
  图上默认直接赋值（非混合，已用最小复现验证），先整块覆写 `TEXT_BOX` 为
  `(0,0,0,153)`，再 `alpha_composite` 贴中文文字层。若改用 `plot/` 那种
  半透明合成盖在原图上，原文不透明的白色填充会透出约 40% 强度形成灰色
  残影——`test_bake_cell_alpha_composite_over_original_would_ghost` 用
  对照组量化复现了这个失败模式，证明"直接覆写"不是可有可无的选择。

## 6. 超长标题：0 条命中，机制齐全

195 条 `title_zh` 在 `FONT_SIZE=9`/135px 预算下**全部单行放得下**
（`manifest.json.overflow == []`）。最紧张的几条（剩余右边距）：

| 卡号 | title_zh | 剩余边距(px) |
|---|---|---|
| 182 | サクラ的日记：9月16日（夜） | ~8（最紧） |
| 90 | 选择：烟花之下，与ユウイチ | ~9 |
| 180 | サクラ的日记：7月（未写完） | ~11 |
| 189 | サクラ的日记：11月12日 | ~11 |
| 38 | 选择：对ユウイチ的心意 | ~17 |

这不是巧合：中文标题普遍比原日文所需全角字数更少（不需要假名/助词填充），
所以即使按原文视觉当量选字号，中文译文依然有 8–17px 余量，比 CLAUDE.md
交办时预估的"大概率需要缩字号或截断"宽松。

**machinery 仍然齐全**：`collect_overflow()` 调用 `tools/zh_wrap.py` 的完整
退让链，任何一条 `title_zh` 未来变长导致真正超预算，会被显式捕获并列进
`manifest.json`（含 `dropped` 字段），不会静默截断——
`test_collect_overflow_surfaces_truncated_titles` 用合成超长字符串验证过
这条路径确实能触发。

## 7. 变异红绿实况（Edit 应用+还原，未使用任何 git 回滚命令）

三组必做变异全部按「关闭闸→测试变红→Edit 精确复原→测试变绿」的流程跑过：

| # | 变异内容 | 改动位置 | 结果 |
|---|---|---|---|
| A | 非 TEXT_BOX 区域像素校验被关掉（`find_outside_box_diffs` 提前 `return []`） | `tools/bake_scene.py::find_outside_box_diffs` | **红**：`test_find_outside_box_diffs_detects_change_outside_box` 失败（`assert (0, 0) in []`） |
| B | 格号→卡号映射列错位一格（`cell_position` 的 col 恒 `+1 % GRID_COLS`） | `tools/bake_scene.py::cell_position` | **红**：2 条测试同时失败——`test_cell_position_matches_lua_ground_truth`（卡1 预期`(1,0,0)`得`(1,0,1)`）+ `test_cell_box_pixel_rect_matches_grid`（预期框`(0,0,145,15)`得`(145,0,290,15)`） |
| C | 超长标题截断不进报告（`collect_overflow` 提前 `return []`） | `tools/bake_scene.py::collect_overflow` | **红**：2 条测试同时失败——`test_collect_overflow_surfaces_truncated_titles`（预期 `[2]` 得 `[]`）+ `test_collect_overflow_disabled_would_hide_the_truncation`（`assert [] != []` 失败，证明这条"坏实现"确实会把真实截断藏起来） |

四条改动全部为**真红**（不是"测试无牙"的假绿），每次确认变红后立即用 `Edit`
精确复原对应代码块（未使用任何 `git checkout`/`stash`/`restore`），复原后
`tests/test_bake_scene.py -q` 与全量 `pytest -q` 均恢复通过，全程无遗留。
复原后用 `grep -n "MUTATION" tools/bake_scene.py` 确认代码里没有残留任何
变异标记。

未出现"绿变异"（改动后测试仍通过、需要诊断"测试无牙 vs 变异没打中"的情况）
——四组改动全部被命中，且命中的断言内容与变异描述精确对应，不是被无关测试
连带打死。

## 8. 测试结果

- `tests/test_bake_scene.py`（新增）：**22 passed**，覆盖：格号映射真值表
  + 越界拒绝 + 错位回归钉子（3 条）、空白尾格验证（1 条）、超长标题
  0 命中 + 截断机制本身可信（3 条）、墨迹检测（合成+真实数据，4 条）、
  擦除硬覆盖 vs 残影对照组（3 条）、水平居中（1 条）、像素保真闸（3 条）、
  真实素材跨格背景一致性（1 条）、端到端全量跑批（2 条）、输出格式（1 条）。
- 全量套件 `uv run pytest -q`：**960 passed**。本任务自身的净增是 **+22**
  （`tests/test_bake_scene.py` 的全部测试；未修改任何既有文件的测试，
  `tools/bake_plot.py` 等其它模块零改动）。任务交办文档记载的基线是
  898——工作过程中发现当前工作树的全量已经是 960（先于本任务改动即如此，
  验证方式：`git status` 显示同期有并行会话在写
  `build/extra_derived.jsonl`/`data/api_ledger.jsonl` 等文件，属于任务
  交办里提到的"另一个正在写 forward_extra.jsonl 的会话"及其相关工作，
  不属于本任务改动范围，本报告只对本任务自身引入的 +22 条负责）。
- 无 skip、无 xfail。

## 9. 目视产物

- `build/scene_zh/_compare.png`：2 张 sheet 逐张原图(上)/中文版(下) 并排
  对照。已目视核对：全部 195 格文字居中、无溢出、无错位；sheet2 的 9 个
  空格与原图一致（完全透明，画布留白）。
- `build/scene_zh/_cellzoom.png`：12 格放大对照，刻意挑难：
  卡1（首格）、卡195（末张真实卡）、卡182（最长中文标题）、卡90（长逗号
  日文句+片假名人名混排）、卡80「亲吻」（最短中文标题之一）、卡133
  「Ｓｅｃｔｉｏｎ１あらすじ」（全角拉丁+假名混排）、卡114「ナオヤ」
  （纯片假名人名）、卡2（剩余边距较紧的真实标题）、卡38（选择类长句）、
  卡145（句末带「。」标点）、卡118「春」（单字，最短原文，对照满格居中
  效果）、卡180（15 字次长日期格式标题）。青色描边标出 TEXT_BOX 边界，
  供人工核对是否有任何渲染越界。

## 复核用命令

```bash
uv run pytest tests/test_bake_scene.py -q   # 22 passed
uv run pytest -q                             # 960 passed（全量）
uv run python3 tools/bake_scene.py           # 重新生成 build/scene_zh/*
```

## 10. 字号调档：9px → 10px（用户看过字号对照后选定）

用户看过 9px 成品后反馈「感觉字号稍小」，要求出字号对照供选；看过对照后选定 **10px**。

### 参数改动（两处一起改，缺一会有 2 条溢出）

| 项 | v1（旧） | v2（新，本次交付） |
|---|---|---|
| `FONT_SIZE` | 9 | **10** |
| `TEXT_BOX` | `(5, 0, 140, 15)`（边距 5px，可用宽 135px） | **`(3, 0, 142, 15)`**（边距 3px，可用宽 139px） |

**为什么边距也要跟着改**：只改字号不改边距，10px 下 195 条真实卡名标题里有 **2 条溢出**
（卡182「サクラ的日记：9月16日（夜）」需 ~138px，卡180「サクラ的日记：7月（未写完）」需
~136px，均超过 135px 旧预算）。把边距从 5px 收紧到 3px（可用宽 135→139px）后，这 2 条重新
落回预算内。两个参数是同一次改动的两个必要部分，不是可以分开挑一个改的。

### 实测溢出数（用工具自己跑，不采信预先算好的表）

```
$ uv run python3 tools/bake_scene.py
cards: 195
overflow (truncated) titles: 0
ink outliers (real JP caption not fitting TEXT_BOX, or undetected): 0
pixel-preservation violations: 0
```

`build/scene_zh/manifest.json` 同步记录：`"text_box": [3, 0, 142, 15]`、`"font_size": 10`、
`"overflow": []`、`"ink_outliers": []`、`"pixel_preservation_violations": []`。

**195 条标题、10px/3px 边距下，实测 overflow = 0、ink_outliers = 0、
pixel_preservation_violations = 0**——与交办前给出的估算表一致，但这里是重新拿工具跑出来的
数字，不是照抄估算表。

### 保全闸覆盖矩形的变化：新暴露的 2px×2 边缘带

`find_outside_box_diffs`/`bake_cell` 都以模块级 `TEXT_BOX` 为唯一依据（非硬编码常量），
所以边距改动**自动**让保全闸的覆盖矩形从 `(5,0,140,15)` 变为 `(3,0,142,15)`，闸本身不需要
额外代码改动——但矩形变大意味着**闸从今往后不再校验以下两条 2px 竖带**：

- `x∈{3,4}`（原边距 5px 时属于"box 外，受保护"；新边距 3px 时属于"box 内，可重绘"）
- `x∈{140,141}`（同理，box 右边界从 140 前移到 142）

这两条竖带落在 `build/scene_layout_spec.md` 第 4 节测出的"四角缺口装饰"列区间
`x∈[0,4]∪[140,144]` 内部——即原本受像素保全闸保护、alpha 从 153 向 0/回升过渡的装饰性
凹口像素，其中最靠内的 2 列（`x=3,4` 和 `x=140,141`）**现在归入重绘区，会被 `bake_cell` 的
纯色带（`(0,0,0,153)` 直接覆写）+ 新文字层覆盖，不再保持原始的凹口渐变**。这是本次改动
**唯一实质的安全面变化**——不是 bug，是边距扩大的必然代价，且只影响这 2px 窄带，不影响
凹口装饰的主体（仍在 `x∈{0,1,2}` 和 `x∈{142,143,144}`，未纳入新 TEXT_BOX）。

**用变异实测精确验证了这条变化的边界**（见下节变异 B）：故意让闸继续按旧边距
`(5,0,140,15)` 校验，结果在**每一张卡**上都在 `x∈{3,4,140,141}`、`y∈{1,2,3,4,10,11,12,13}`
（凹口的活跃行区间）报出差异——这组坐标与 spec 文档预测的"四角缺口活跃行 y∈{1..4}∪{10..13}"
精确吻合，证明"新暴露的 2px×2 边缘带"不是猜测，是可以现场重现的实测事实。

### 测试金标值改动：0 处（逐条确认过，不是漏改）

检查了 `tests/test_bake_scene.py` 全部 22 条测试，**没有一条断言写死了字号=9 或边距=5 这类
数字**：
- 涉及 `TEXT_BOX`/`FONT_SIZE` 的测试全部通过 `from tools.bake_scene import ... TEXT_BOX,
  FONT_SIZE ...` 动态引用模块常量（如 `test_bake_cell_centers_text_horizontally` 用
  `(TEXT_BOX[0] + TEXT_BOX[2]) / 2` 算中心，`test_collect_overflow_empty_for_real_titles`
  用 `_font()` 内部默认取当前 `FONT_SIZE`），参数一改这些测试自动跟着用新值重新验证，
  不需要人工同步。
- 唯一涉及具体像素数字的是 `test_find_outside_box_diffs_detects_change_outside_box`
  （硬编码 `(0,0)`）——`x=0` 无论边距是 5 还是 3 都必然在 box 外（`0 < 3`），不需要改；
  `test_collect_ink_outliers_flags_ink_outside_text_box`（矩形 `[0,0,3,3]`）同理，
  `assert x0 < TEXT_BOX[0]` 是动态比较，`x0=0` 依然小于新的 `TEXT_BOX[0]=3`，断言不受影响。
  只把该测试里的注释从「x<5，越出 TEXT_BOX」改成了「x=0，恒 < TEXT_BOX[0]」+ 一行说明——
  **纯注释措辞更新，不是断言改动**，因为原注释里的数字"5"字面提到了旧边距，容易让读者
  误以为断言依赖这个具体数字。
- 结论：**0 处断言期望值改动**。全部 22 条测试原样通过（`uv run pytest
  tests/test_bake_scene.py -q` → `22 passed`），因为它们从一开始就是按"动态读取模块常量"
  写的，这也是为什么本次调参没有牵一发动全身。

### 变异红绿实况（Edit 应用 + 手工复原，未用任何 git 回滚命令）

| # | 变异内容 | 改动位置 | 结果 |
|---|---|---|---|
| A | 溢出检查被绕过：`collect_overflow` 首行插入 `return []`（超宽标题渲染但不进报告） | `tools/bake_scene.py::collect_overflow` | **真红**：`test_collect_overflow_surfaces_truncated_titles`（预期 `cards==[2]` 得 `[]`）+ `test_collect_overflow_disabled_would_hide_the_truncation`（`assert real != []` 失败，`real` 变成了 `[]`），2 条失败，其余 20 条不受影响 |
| B | 像素保全闸矩形没跟着 TEXT_BOX 改：`bake_sheet` 里 `find_outside_box_diffs(cell, new_cell, TEXT_BOX)` 硬改成 `find_outside_box_diffs(cell, new_cell, (5, 0, 140, 15))`（闸继续用 v1 的旧边距，不跟随模块级 `TEXT_BOX`） | `tools/bake_scene.py::bake_sheet` | **真红**：`test_bake_sheet_real_data_zero_pixel_violations` 失败，195 张卡里几乎每张都在 `x∈{3,4,140,141}`、`y∈{1,2,3,4,10,11,12,13}` 报出"违规"（实际是新 TEXT_BOX 的合法重绘区，被旧边距的闸误判成"box 外被动过"）；`test_real_run_report_is_clean` 同步失败（`pixel_preservation_violations` 非空） |

两组变异均为**真红**（改动后立即用 `Edit` 精确复原对应代码块，全程未使用任何
`git checkout`/`stash`/`restore`），复原后 `grep -n "MUTATION" tools/bake_scene.py` 确认
无残留标记，`tests/test_bake_scene.py -q` 恢复 `22 passed`，全量 `uv run pytest -q` 恢复
`960 passed`。

变异 B 的报错内容本身就是第 10 节"保全闸覆盖矩形变化"一节的**独立实测证据**——不是设计出来
配合叙述的巧合，是变异跑出来之后才确认坐标与预测吻合。

未出现"绿变异"（改动后测试仍通过、需要诊断"测试无牙 vs 变异没打中"的情况）——两组改动全部
被命中，且命中的断言内容与变异描述精确对应。

## 11. 新增产物

- `build/scene_zh/scene_{1,2}_a.png` / `_compare.png` / `_cellzoom.png` / `manifest.json`：
  用 10px/`TEXT_BOX=(3,0,142,15)` 全量重新生成（覆盖第 9 章节记录的 9px 版）。
  `_cellzoom.png` 沿用已有的 `CELLZOOM_CARDS`（卡 1/195/182/90/80/133/114/2/38/145/118/180），
  本来就已包含用户点名要看的卡 182（最长）/180（次长）/118（单字"春"）/2 与 90（11px 时会
  溢出的两条，10px 下应仍宽裕——目视确认宽裕）以及若干普通卡，无需改动挑选列表，只需要
  用新参数重新跑。
- `tools/bake_scene_size_ab.py`（新增工具，入库）：产出 `build/scene_zh/_size_ab.png`——
  同一组卡（复用 `CELLZOOM_CARDS`），每卡上排 9px 旧版 / 下排 10px 新版，放大 6 倍并排，
  青色描边=旧 `TEXT_BOX(5,0,140,15)`、洋红描边=新 `TEXT_BOX(3,0,142,15)`，供人 A/B 直接对比。
  旧版渲染**不依赖任何 git 历史**：脚本内把 v1 参数（`OLD_FONT_SIZE=9`、
  `OLD_TEXT_BOX=(5,0,140,15)`）冻结成独立常量，直接用 `tools.bake_scene.bake_cell()` 传入
  显式旧参数、从只读的 `png/scene/` 原图现场渲染一份，不读取任何此前生成的 `build/`
  产物、不使用 `git stash`/`checkout` 等回滚类命令。目视核对：10px 版本在全部挑选的卡上
  都清晰变大、仍完整落在新 `TEXT_BOX` 内、无溢出。

## 需要用户裁决的事项

本轮实测下来，`scene/` 的中文化没有遇到「必须二选一牺牲」的硬冲突（不像
`plot/` 当初的卡162那样有已知局限需要用户拍板）——195 条标题在选定字号/
盒子下全部安全放得下，背景是纯色不涉及"盖多少算过度"的取舍，`__` 前缀文件
经查证是无用的死文件不需要处理决策。仅有以下两点供留意，不构成阻塞：

1. **字号/居中版式最初是本工具自行测出并选定的（9px，双向居中），第 10 节记录的字号调档
   （9px→10px、边距 5px→3px）已按用户裁决落地**，与 `plot/` 的版式参数（10px，左对齐顶对齐）
   数值上凑巧一致，但仍是两套独立测出/选定的参数——`scene/` 保持双向居中，未改成
   `plot/` 的左对齐。如果未来有统一两套烤图视觉风格的诉求，那是另一个设计决策。
2. **`__scene_{1,2}_a.png` 目前原封不动保留**——如果未来确认这两个文件
   连"死文件"的归档价值都没有（比如确认是转换工具的一次性副产物、可以
   安全删除），那是一个高于本任务范围的仓库清理决策，本任务不擅自删除
   只读资产。
