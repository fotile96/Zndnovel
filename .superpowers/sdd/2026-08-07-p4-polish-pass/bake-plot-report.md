# 烤字回填试片报告：`png/plot/`（卡名缩略图集）

状态：**DONE**（PNG + 规格文档产出，不含 `.gim` 回转——本轮用户已明确限定范围）

这不是本 SDD 台账（`2026-08-07-p4-polish-pass`）计划内的任务编号，是并行的
「烤字回填第一块试片」独立交办，报告按用户指定路径落在这里。

## 一句话摘要

`png/plot/` 4 张卡名缩略图集（195 张卡，6×10 网格/张，共 240 格）全部替换为
`skeleton/cards.zh.yaml` 的中文定稿，格号↔卡号映射从 lua 引擎源码直接反推
（非猜测，见第 2 节），非文字区域像素逐字节保真（自动闸 + 3 组变异全部
证实有牙），0 条超长卡名被截断。产物：`build/plot_zh/plot_{1..4}_a.png` +
`_compare.png`（对照图）+ `manifest.json`；工具 `tools/bake_plot.py`；
测试 `tests/test_bake_plot.py`（21 条，随全量套件跑，854 passed）。

## 1. 版面测绘：方法与结论

**基础网格**：`PIL Image.open().size` 读出 4 张图均 492×480、`P` 模式（带逐
调色板项 alpha 的满 tRNS 表，非单索引透明）。492/82=6、480/48=10 整除只是
必要条件，**真正的权威证据是** `lua_scripts/snr_common.lua:925-954` 的
`plotState` 构造循环——它把 `clipX=col*82, clipY=row*48` 写死为字面量，且
`snr_story_main.lua:97` / `snr_fragment_main.lua:87` 的 `layerClip(...,
clipX, clipY, clipX+82, clipY+48)` 直接消费这套坐标做运行时裁切。**82×48、
6 列×10 行不是从图片反推出来的，是游戏引擎自己写死的**。

配色/风格：每格背景是**该卡对应场景的暗化缩略截图**（不是共享的单一渐变，
见 6 个随机样本 `card1/2/9/20/50/100/150/190` 交叉核对：卡1 是纯渐变无场景，
卡2/9/20/50/100/150/190 各自都是不同场景截图）。文字风格是**白色填充
`(238,238,238)`+黑色描边 `(1,1,1)` 的 caption 字**，任意背景明暗下都测出
可读（深色渐变的卡1、亮天空的卡2 都核对过）。

日文原排版：顶部对齐（不随行数垂直居中，单行标题也贴顶）、行高 12px、单行
字高约 9px、左边距约 4px、**换行点固定落在第 7 个字符**（6 个样本
`卡1/2/20/100/195/180` 全部验证，含最长的 15 字标题卡180「サクラの日記：
７月（書きかけ）」→ 7+8 两行）。**这条「第 7 字符换行」是测出来的日文原版
规律，本工具没有复刻它**（详见第 6 节／spec 第 4-6 节）——一个重要的排除项：
最初怀疑 `cBrStr()`（`snr_common.lua:365`，每 24 UTF-8 字节即 8 全角字换行）
是候选算法，8≠7，实测直接证伪，且 `cBrStr` 本来就只作用于 `plotTitle[]`
供其他 UI 使用，不参与这批烤图的排版——两条管线本就独立，不必吻合。

完整测绘方法、每条结论的像素坐标证据、以及「测不出来的」清单（换行算法是
字符数硬切还是像素宽度巧合、原生描边精确 px 值、原始美术生产流程）都写在
`build/plot_layout_spec.md`（本报告不重复摘抄，避免两处文档漂移）。

## 2. 格号↔卡号映射：证据链与把握程度

**结论**：卡号 1..195 按**行优先（从左到右填满一行再换行）**顺序铺进
每张 sheet 的 6×10 网格，每 60 张卡换一张 sheet（sheet1=1-60，sheet2=61-120，
sheet3=121-180，sheet4=181-195+45 空格）。

**三层独立证据**（缺一不可信，这里三层都做了，互相吻合无矛盾）：

1. **一手：lua 源码算法**（`snr_common.lua:925-954`）。见上节引用的循环体，
   col 0→5 后归零换行、row 递增，`i0*60<=i4` 触发时清零 col/row 并切到下一张
   sheet 的 `layerName`。这是运行时真正吃这份坐标表的代码路径，不是本工具
   自己的假设。
2. **二手：像素读取核对**。裁出预测坐标格并肉眼读出格内文字，与
   `plotTitle[N]`（`snr_common.lua:598-792`）比对：卡1→(1,0,0)「ある子が
   学校にくる物語」、卡2→(1,0,1)「夏の朝、高校までの通学路」、卡60→
   (1,9,5)「プラネタリウム」（sheet1 换页前最后一格）、卡195→(4,2,2)
   「セクション５：アヤノ」（4 张卡横跨 sheet1 首格到 sheet4 内部，逐一
   命中）。
3. **三手：反向验证空白区**。195 张卡填不满 240 格，预测多出的 45 格
   （sheet4 的 row2 col3 起到 row9 col5）逐像素核对 **alpha 全 0**（完全
   透明），与「多余格应为空白模板」的预期吻合，且被 `tests/test_bake_plot.py::
   test_real_sheet4_tail_cells_are_blank_beyond_card_195` 钉成回归测试。

**把握程度：高**。不是从图像反推的猜测，是游戏引擎自身在 3 个独立 lua 文件
里写死的同一套坐标算法（构造方 `snr_common.lua` + 两个消费方
`snr_story_main.lua`/`snr_fragment_main.lua`），再用 4 个像素样本 + 45 格
空白区三重交叉核对，全部吻合、无一处矛盾。

## 3. 字号与排版取值依据

- **字体/字号**：`third_party/LXGWWenKai-Regular.ttf` @ **10px**。依据：该
  字号下单字 bbox 高约 9px、字符前进量约 10px/字（`PIL ImageFont` 实测），
  与原文测出的单字高约 9px、前进量约 10.3px/字**视觉当量几乎重合**——不是
  拍脑袋取的字号。
- **左边距 4px、行高 12px、顶部起笔 y=2**：直接照抄第 1 节测出的原版参数。
- **换行宽度预算 76px**（82 格宽 − 左右各约 3px 安全边）：贪心逐字符/逐
  ASCII-数字块填充，196 条 `title_zh`（195 张卡）在此预算下**全部 ≤2 行**
  （125 条 1 行 + 70 条 2 行 + 0 条截断，`collect_overflow` 全量跑实测，
  钉在 `test_real_titles_two_line_count_matches_spec`）。
- **换行的一处质量修复**：初版按字符逐一贪心换行时，会把连续 ASCII 数字切
  断在行边界（如「10月3日」被切成「1」/「0月3日」，「11月12日」同理）。
  测出后加了 `_tokenize()`：把 `[A-Za-z0-9]+` 当一个不可切分原子，
  `test_wrap_title_never_splits_inside_a_number` 钉住这条不回归。
- **文字风格**：白色填充+黑色描边（`stroke_width=1`），直接复刻第 1 节
  测出的原版 caption 风格。
- **输出色彩模式：RGBA，不强制量化回原图的 `P` 调色板**。理由三点（详见
  spec 第 6 节）：①原调色板大概率是 `.gim`→`.png` 工具按每图内容自动生成
  （4 张图调色板前几项互不相同），本来就不是共享固定调色板；②本轮明确不
  做 `.gim` 回转，现在量化只会现在就丢保真度，换不来本轮用得上的好处；
  ③回转时调色板选择本身有未探明的约束（CLAUDE.md 已提示），该决策应留给
  回转步骤自己做，不该被本工具提前锁死——这是刻意不挖坑的选择，已在 spec
  里写明。

## 4. 超长卡名清单与处置

195 条 `title_zh` 中 **70 条**需要 2 行显示，**0 条**触发截断（2 行预算全部
够用）。完整 70 条清单见 `build/plot_layout_spec.md` 第 7 节（挑了 6 条最值
得单独看的：卡180/182 两条 15 字最长标题、卡188/189/191 三条日期格式验证
数字未被切断、卡90 验证「行首孤立标点」的已知小瑕疵未处理）。⚠ 未触发不等
于机制没做：`wrap_title(max_lines=2)` 遇到真正超预算的输入会正确产出
`truncated=True` + 省略号收尾的最后一行（`test_wrap_title_truncates_and_
flags_when_it_does_not_fit` 用一个 34 字的合成超长串验证），且
`collect_overflow` 会把它收进结果、写进 `manifest.json`——**不会静默吞字**，
这条路径当前 195 条真实数据没走到，但machinery 在、有测试盯着。

## 5. 非文字区域校验的实现

`find_outside_box_diffs(orig_cell, new_cell, box=TEXT_BOX)`：逐像素比较
`TEXT_BOX=(0,0,82,28)`**之外**的区域，返回不一致坐标列表（空列表=通过）。
`bake_sheet()` 对每一格调用它，结果收进 `manifest.json.
pixel_preservation_violations`；`main()` CLI 若发现非空列表会以退出码 1
失败（不是静默打印一下就算了）。本次真实产出跑批：**0 违规**（195 格全部
通过）。

`TEXT_BOX` 高度取 28px 是「测出的原文双行高度（y3-23）+ 安全边」倒推的固定
值，不是逐格动态算的——`test_bake_cell_touches_only_text_box_on_synthetic_
cell` 用真实渲染管线（`reconstruct_box`+`render_text_layer`+
`alpha_composite`）在一个合成格子上跑一遍，独立复现同一断言（不依赖对内部
实现的信任）。额外验证了这个安全边**是承重的**：把 `TEXT_BOX` 临时改小到
20px（模拟"选错安全边"的错误），这条属性测试立刻抓到 148 个越界像素——
证明它不是摆设。

## 6. 擦除策略：两版尝试记录（诚实记录被放弃的路径）

目标：`TEXT_BOX` 内必须把原日文字**完全擦除**再画新中文字，`TEXT_BOX` 外
必须逐字节不变。

- **第一版（已放弃）**：按像素颜色特征（近白色填充 / 近黑色描边）识别"墨迹"
  像素，只重绘这些像素（尝试过局部模糊填补、以及 BFS 最近邻非墨迹像素
  取色两种重建方式）。**实测都失败**：小字号下抗锯齿边缘产生大量中间灰阶
  像素密布在字形四周，导致"非墨迹"像素判定过于稀疏且紧贴字形边界——两种
  重建方式都在原字形轮廓处留下清晰可辨的残影（模糊版留下发糊的字形亮斑；
  BFS 最近邻版更糟，因为字形边缘本身就密布可用的"非墨迹"取色源，等于就地
  重建出一份轻微模糊的原字形拷贝，与新绘中文字直接叠在一起——肉眼核对时
  第一眼就能看出"两层字叠在一起"）。
- **实际采用**：不做逐像素墨迹判定，`TEXT_BOX` 内**整体按列**从 box 下边界
  （y=28 那一行）取色，纵向铺满替换整列。100% 消除残影（不依赖对旧字形的
  识别，无论多复杂的旧字形都能干净擦除），代价是丢失 box 内原有的纵向背景
  细节（人物特写类格子的衣物褶皱等），换成从下边界拉伸出的纵向条纹——对
  多数格子（背景偏均匀）影响很小，对少数细节丰富的格子有一定简化，全部
  195 格的效果都在 `_compare.png` 里，供人工逐格复核。`test_reconstruct_
  box_erases_entire_box_deterministically` 钉住这个「按列取 box 下边界颜色」
  的具体算法行为。

## 7. 变异红绿实况

三组必做变异全部按「关闭闸→测试变红→复原→测试变绿」的流程跑过：

| # | 变异内容 | 改动位置 | 结果 |
|---|---|---|---|
| A | 非文字区域像素校验被关掉（`find_outside_box_diffs` 恒返回 `[]`） | `tools/bake_plot.py` | **红**：`test_find_outside_box_diffs_detects_change_outside_box` 失败（`(5,31) not in []`） |
| B | 格号→卡号映射错位一格（`cell_position` 的 col 恒 +1） | `tools/bake_plot.py` | **红**：`test_cell_position_matches_lua_ground_truth`（卡1 预期(1,0,0)得(1,0,1)）+ `test_cell_box_pixel_rect_matches_grid` 两条同时失败 |
| C | 超长卡名截断不进报告（`collect_overflow` 恒返回 `[]`） | `tools/bake_plot.py` | **红**：`test_collect_overflow_surfaces_truncated_titles` 失败（预期 `[2]` 得 `[]`） |
| D（额外，非必做） | `TEXT_BOX` 高度改小到 20px（模拟选错安全边） | `tools/bake_plot.py` | **红**：`test_bake_cell_touches_only_text_box_on_synthetic_cell` 抓到 148 个越界像素 |

四组变异均为**真红**（不是「测试无牙」的假绿），且每次都在确认变红后立即
用 Edit 精确复原对应代码块（未使用任何 git 回滚命令），复原后重跑
`tests/test_bake_plot.py` 确认恢复 21 passed。这里没有出现"绿变异"，故
不需要做"测试无牙 vs 变异没打中"的二选一诊断——四条改动全部被至少一条测试
命中，且命中的测试断言内容与变异描述精确对应（不是碰巧被别的无关测试
连带打死）。

## 8. 测试结果

- `tests/test_bake_plot.py` 单独跑：**21 passed**。
- 全量套件 `uv run pytest -q`：**854 passed**（基线 833 + 新增 21，无其他
  回归）。
- 无 skip、无 xfail。

## 9. 目视产物

`build/plot_zh/_compare.png`：4 张 sheet 逐张原图(上)/中文版(下) 并排对照，
`492×(16+480+6+480)` 每列，4 列横排。已逐格抽查多组（含最长标题卡180/182、
片假名混排卡195、章节卡卡150/158、行首标点卡90），未见错位/溢出/字被切；
sheet4 的 45 空格与原图完全一致（透明）。已用 `SendUserFile` 一并发送
`build/plot_zh/plot_{1..4}_a.png` 与 `_compare.png` 供人工复核（`build/`
本身 gitignore，本报告和这些 PNG 都不会随 commit 入库，只能靠此渠道让人
看到）。

## 10. 下一块（`scene/`，145×15 单行格）预计会遇到的不同问题

- **单行格没有换行决策空间**：`scene/` 是 145×15 的场景名条集（CLAUDE.md
  记载 3 列），15px 高度大概率只放得下 1 行小字——`plot/` 的「换行预算/
  行高/顶部对齐」这套参数需要整体重新测（不能照抄 82×48 的取值，格子形状
  完全不同，尤其 15px 高度可能连本工具用的 10px 字号单行都放不下，需要
  重新做一次「字号视觉当量匹配」）。
- **超长标题的处置策略会更硬**：`plot/` 还能靠两行救急；`scene/` 大概率
  只能靠缩字号或截断+省略号（且 15px 高度下缩字号的空间也很有限），
  「超长名单」清单的意义会比 `plot/` 更大——预计会有一批标题必须真正触发
  截断而非像本次一样 0 条命中，`collect_overflow` 这套「必须显式报出来」
  的机制会被真正用上，需要提前想清楚截断后的可读性（15px 字体本来就已经
  很小，省略号可能进一步挤占本就紧张的宽度）。
- **格号→卡号映射需要重新走一遍同样的三层证据链**，不能因为 `plot/` 验证
  过一次「lua 源码算法可信」就跳过对 `scene/` 自己的 `sceneState` 循环
  （`snr_common.lua:955-984`，本次分析时顺带看到，结构与 `plotState` 几乎
  同构：3 列×？行、每 102 张卡换页）的独立核实——两份表是分别构造的，不能
  假设参数（尤其是"多少列换页"这类具体数字）能直接套用。
  （粗查：`sceneState` 循环里 `3 < v9` 触发换行、`i4*102 <= i8` 触发换页，
  对应 145/? 列宽——数字与 `plotState` 不同，说明确实需要独立重测，不能
  照搬本轮参数，这里只是顺手记一笔，未展开验证，留给下一块任务。）
- **背景重建策略可能需要不同权衡**：`plot/` 每格背后是独立缩略场景图，
  「按列拉伸擦除」丢的是纵向细节；`scene/` 如果背景更简单（比如纯色/简单
  渐变的场景名条，不一定像 `plot/` 那样嵌照片），擦除可能反而更简单干净，
  但也可能因为格子更矮（15px vs 48px）导致「按列取 box 下边界颜色」这个
  技巧的下边界样本行离文字太近、被文字自身干扰——需要先重复本次 §1 的
  实测流程确认 `scene/` 的背景形态，不能预设。

## 复核用命令

```bash
uv run pytest tests/test_bake_plot.py -q      # 21 passed
uv run pytest -q                               # 854 passed（全量）
uv run python3 tools/bake_plot.py              # 重新生成 build/plot_zh/*
```

---

## 追记（2026-08-08）：背景处理方案 v2 —— 逐格墨迹实测色带，废除固定 `TEXT_BOX`

**状态：DONE**（`build/plot_zh/plot_{1..4}_a.png` + `_compare.png` + 新增
`_cellzoom.png` 重新生成；`tools/bake_plot.py`、`tests/test_bake_plot.py`
均已改写；`uv run pytest -q` 871 passed）。

### 0. 对上一版说法的更正

第 6 节把旧方案（`TEXT_BOX=(0,0,82,28)` 固定框、按列取下边界颜色平铺擦除）
的代价记作「loses within-box vertical background texture」——**这个说法把
代价说轻了**。`plot/` 每格背后是场景/CG 缩略截图，48 行的格子里 `TEXT_BOX`
吃掉了 28 行，也就是**每格插图 58% 的面积**，不是「丢一点纵向细节」，是
「一大半插图被平铺纹理盖掉」。本节记录的新方案把这个代价从「固定 58%」
降到「逐格按实际墨迹/译文需要动态计算，195 格里最矮 18 行（37.5%）、最高
32 行（66.7%，且只有 1 格触发，见下）」，绝大多数单行标题格只需要 18-19
行（约 38-40%），比旧方案省下将近三分之一格高的插图。

### 1. 墨迹检测判据的最终形态

**判据**：一个像素只有在同时满足以下两条时才算「墨迹」——
①`min(r,g,b) >= 200`（接近原文描边字白色填充芯部 `(238,238,238)`）；
②其 Chebyshev 半径 2 像素内存在一个 `max(r,g,b) <= 90` 的像素（接近描边
黑色 `(0,0,1)`）。行内合格像素数 `>= 3` 才算「墨迹行」，取墨迹行的
最小/最大行号为该格墨迹纵向范围。

**为什么要联合判据、不能只看亮度**：明亮背景（泳池水面、天空、白色校服）
本身就有大片高于 200 的像素，单看亮度会把整张亮背景误判成墨迹，色带反而
比旧的固定 28px 拉得更深——比"没有改进"更糟。联合判据要求亮像素邻近有
描边黑，这是白芯黑边描边字的结构性特征，绝大多数照片内容里没有这种
紧邻搭配（见下 195 格实测，最亮的几格全部正确处理）。

实现上，「邻域内存在暗像素」用**可分离方形膨胀**（先按行膨胀暗色掩码，
再按列膨胀），把原本 O(w·h·r²) 的暴力邻域搜索降到 O(w·h)，195 格全量跑
（含墨迹检测 + 中文渲染 + 色带合成 + 逐格逐像素校验）合计约 1.2 秒。

### 2. 195 格实测统计（判据实测行为）

对 `png/plot/` 全部 195 格用最终判据跑一遍（`ink_bbox_of_cell`，参数即
`tools/bake_plot.py` 里的默认值）：

- **检测成功 194/195，检测失败（无法测出墨迹）1/195**：card 162。
- **合理性上限（`INK_MAX_PLAUSIBLE_BOTTOM=30`）触发次数：0**——195 格
  没有一格的墨迹检测结果荒谬地深，这条安全网目前是纯防御性代码（见
  `test_decide_band_implausible_ink_falls_back` 用合成格子专门验证它确实
  有牙，不依赖真实数据触发）。
- **墨迹高度分布**（`max-min+1`，195 格里 194 个非回退格）：
  `{8: 3格, 9: 79格, 17: 1格, 19: 3格, 20: 21格, 21: 87格}`——单行标题
  聚集在 8-9 行（`y3-11` 一类），双行标题聚集在 19-21 行（`y3-23` 一类），
  与 `build/plot_layout_spec.md` 第 4 节人工量出的参照值完全吻合
  （`test_ink_bbox_matches_spec_measured_reference_cards` 钉住 6 张参照卡）。
  **17 行的那一格是 card 170**「選択：アヤノを――」——第二行只有破折号
  `――`，笔画本来就比假名矮，色带因此比其他双行卡矮了 4 行，这是判据
  如实反映真实笔画高度的证据，不是误差。
- **顶部起笔分布**：`{y=3: 167格, y=4: 27格}`——与 spec 记载的「顶部对齐、
  起笔约 y3」一致，27 格起笔稍晚到 y4 属于正常字形差异（如 card 80/115/118，
  墨迹高度也相应缩到 8 行）。
- **亮背景误判排查**：把 195 格按整体平均亮度排序，最亮的 15 格
  （均值 85.6–121.0，含泳池 card 59、天空/走廊 card 195/36/74/20/68/147、
  病房白墙 card 115 的对照组等）逐一核对检测结果——**除 card 162 外全部
  测出合理的 8/9 或 19-21 行范围，没有一格因为背景亮就被拉出异常大的
  色带**。这是联合判据（而非单纯亮度阈值）真正发挥作用的直接证据：
  `test_ink_bbox_rejects_uniform_bright_background` /
  `test_ink_bbox_rejects_bright_and_dark_regions_that_are_not_adjacent`
  用合成格子把这条防线单独钉住。

### 3. 回退格清单与处置

**唯一回退：card 162**（`plotTitle[162]="セカンドノベル"`，游戏本体标题，
`title_zh="第二物语"`）。原因：这一格的背景**不是**「场景截图+白芯黑边
描边字」的标准格式，而是游戏标题画面本身的 logo 美术（灰蓝色扁平描边字，
`〜彼女の夏、15分の記憶〜` 副标题同色系），不满足"白色填充+黑色描边"的
联合判据，`ink_bbox_of_cell` 如实返回 `None`。

**处置**：`decide_band` 对回退格采用两条保守规则——①色带高度退回
`FALLBACK_BAND_BOTTOM=28`（旧方案的固定值，测出的"双行标题+安全边"）；
②因为不知道真实墨迹在哪，**整个 28 行区域都按 `hard_range` 处理**（强制
不透明，见下节），不给它任何软透明区域——不透明是"不知道时的安全默认"，
不是"好看时的默认"。

**已知局限（明说，不蒙混）**：card 162 的原始 logo 副标题
`〜彼女の夏、15分の記憶〜` 延伸到约 y40，**超出 28 行回退高度**，在
`_cellzoom.png` 里清晰可见——回退区域下方仍残留原文副标题的下半截。这不
是本方案能在当前"逐格测量"框架内解决的（没有测量依据来决定该拉多深），
按硬约束"静默回退就是恒绿"，此格已作为 `ink_fallback_cards` 显式播报
（CLI + `manifest.json` + `run()` 返回的 report 字典三处都能看到），需要
人工判断——建议：整卡单独处理（比如整格直接按旧的不透明满铺，或干脆手绘
一版专属底图），不适合套用本工具的通用规则。

### 4. 色带高度 = max(墨迹, 中文需要)——两个方向都有真实数据佐证

`decide_band()`：`content_bottom = max(ink_bottom_used, zh_bottom_used)`，
其中 `zh_bottom_used` 不是公式估算，是**真的渲染一遍新中文文字层，读它的
alpha 通道 bbox**（`measure_rendered_text_bottom`，用 `PIL` 官方
`getbbox()`，不是自造循环）。

两个方向都能在真实卡片里各自找到确凿证据（不是只造合成用例）：
- **墨迹主导**：card 6「約束を思い出せない」原文墨迹 2 行（y3-23），中文
  「想不起约定」只需 1 行——如果只看中文，色带会明显不够深，露出原文墨迹
  下半截。`test_real_card6_ink_dominates_over_short_zh` 钉住
  `content_bottom == ink_bottom_used`。
- **中文主导**：card 25「選択：声の主」原文墨迹只有 1 行（y3-11），中文
  「选择：声音的主人」要 2 行——如果只看墨迹，色带会不够深，中文第二行
  「人」字会被裁到色带外面。`test_real_card25_zh_dominates_over_short_ink`
  钉住 `content_bottom == zh_bottom_used`。

另外两条合成用例（`test_decide_band_ink_dominates_when_zh_is_short` /
`test_decide_band_zh_dominates_when_ink_is_short`）用可控构造的"亮块嵌暗
描边"格子复现同样的两个方向，不依赖任何具体卡片译文，防止未来
`skeleton/cards.zh.yaml`（虽然已冻结）之外的场景下这条逻辑失守。

### 5. 色带视觉参数：一次被数据推翻的直觉，和最终方案

**最初方案（已放弃）**：单一 `alpha` 常量，整个色带区域统一半透明度。
用户给的起点是 150；本轮先按"195 格最坏残留像素值"这个量化指标调参：

| alpha | 195 格里最坏残留（排除顶部羽化区，`banded` 与原图逐像素比较） |
|---|---|
| 150 | 98/255（38%） |
| 190 | 61/255（24%） |
| 225 | 28/255（11%） |
| 235 | 19/255（7.5%，card 1） |
| 250 | 5/255（2%） |
| 255 | 0/255（排除新绘中文字自身像素后，精确为 0） |

**这个量化指标具有误导性**——alpha=235（残留仅 7.5%）在孤立单格渲染里
仍然能**肉眼读出**原文假名/汉字的完整字形（如 card 6 的「出せない」、
card 195 的「アヤノ」），甚至 alpha=250（残留 2%）都仍隐约可辨。原因：
原文是接近满对比度的白芯黑边描边字，哪怕只剩 2-7% 的亮度差，在几乎纯黑
的背景上，人眼对这种"熟悉字形"的模式识别能穿透很低的绝对对比度——这个
现象量化指标（单点最大残留值）测不出来，只有肉眼复核才能发现。

**一个方法论陷阱记录**：中途曾怀疑"肉眼看到的残影"是查看工具把多格拼成
大图后、传输环节的有损缩放/重压缩引入的振铃伪影（不是真实产物里的内容）
——用一张**纯色合成格子**（无任何原文墨迹）跑同一套色带+文字渲染管线，
在同一查看链路下检查：结果完全干净、无任何伪影。这排除了"查看工具在
撒谎"的可能，证明肉眼看到的残影确实是产物本身的内容，不是查看链路的
假象。这个对照测试本身没有对应的自动化测试用例（它是一次性诊断，不是
产物行为），但过程和结论记在这里供复核。

**最终采用（写进代码的实现）**：单一 alpha 放弃，改成**逐行 hard/soft
双档**：
- `decision.hard_range`（真正测出墨迹的行范围，或回退格的整个区间）
  强制 `HARD_ALPHA=255`（完全不透明）——这不是"选择"，是被数据逼出来的
  结论：只有完全不透明才能让原文描边字的残影降到人眼下真正不可辨（上表
  alpha=255 那一行，孤立渲染核对干净，见 `_cellzoom.png`）。
- `hard_range` 之外、但仍在 `content_bottom` 内的行（例如 card 25 中文
  第二行"人"所在的那一行，原文根本没有墨迹）使用 `BAND_ALPHA=200`
  （约 78% 不透明）——这里没有东西要藏，半透明可以放心用，肉眼核对
  （card 25、card 170 的 `_cellzoom.png` 格子）确认背景确实透出来。
- 色带上边缘 2px、下边缘 4px 做 cosmetic-only 羽化（`BAND_TOP_FEATHER_PX`
  /`BAND_BOTTOM_FEATHER_PX`），**羽化区严格加在 `content_bottom` 之外**，
  不吃进任何测出来的墨迹/译文范围——早期一版曾经把羽化直接切在
  `band_bottom` 尾部、覆盖了实际墨迹所在行，导致 2 行标题格出现残影，
  被 `_cellzoom.png` 目视核对抓到并改掉（教训：像素保真闸只查
  "框外"，框内的"覆盖不足"不会被那道闸抓到，只能靠目视复核）。
- `hard_range` 与四周软区之间另加 2px 短渡（`HARD_TRANSITION_PX`），
  避免硬/软两档在色带内部出现肉眼可辨的生硬分界线。

`test_render_band_layer_hard_zone_is_fully_opaque_soft_zone_is_not` 用
合成格子同时钉住"hard 区确实是 255"与"软区确实小于 255"两条断言。

### 6. 扩展后的像素保真闸

`find_outside_box_diffs(orig, new, box)` 函数签名不变（仍是纯函数，逐
像素比较 `box` 之外的区域），但**调用方式变了**：`box` 不再是模块级常量
`TEXT_BOX`，而是 `bake_sheet()` 对每一格用该格自己的
`decision.band_bottom` 现算的 `(0, 0, 82, band_bottom)`——`band_bottom`
本身逐格不同（18 到 32 之间，见下），闸也就随之逐格不同。真实产物跑批
`0` 违规（`manifest.json.pixel_preservation_violations`）。

`TEXT_BOX` 这个固定框常量**已从代码里删除**（不是"保留但不用"）。唯一
存活的"固定值"概念是 `FALLBACK_BAND_BOTTOM=28`，且明确降级为"墨迹检测
失败时的保守回退"，不再是任何格子的默认路径。

`test_bake_cell_band_bottom_varies_with_real_content_not_fixed` 用两张
真实卡片（card 59 短标题 vs card 6 深墨迹）钉住"`band_bottom` 确实随
内容变化，不恒等于任何旧的固定值"这条行为。

### 7. 变异红绿实况（本轮新增，Edit 应用+还原，未使用任何 git 回滚命令）

三组必做变异全部按「关闭闸→跑测试确认真红→Edit 精确复原→跑测试确认恢复
绿」的流程做过，过程记录如下（均为 `tests/test_bake_plot.py -q` 的真实
输出摘录）：

| # | 变异内容 | 改动位置 | 结果 |
|---|---|---|---|
| A | 色带区域外像素校验被关掉（`find_outside_box_diffs` 在循环前提前 `return []`） | `tools/bake_plot.py::find_outside_box_diffs` | **红**：`test_find_outside_box_diffs_detects_change_outside_box` 失败，`assert (5, 31) in []` |
| B | 墨迹回退静默不播报（`collect_ink_fallbacks` 提前 `return []`） | `tools/bake_plot.py::collect_ink_fallbacks` | **红**：两条测试同时失败——合成用例 `test_collect_ink_fallbacks_surfaces_fallback_decisions`（`assert [] == [(2, 'no_ink_detected')]`）与真实数据端到端用例 `test_real_run_report_flags_card_162_as_ink_fallback`（`assert [] == [162]`） |
| C | 色带高度不取"墨迹高度、中文需要高度"的较大者，改成只取中文高度（`content_bottom = min(max(ink_bottom, zh_bottom), CELL_H)` → `min(zh_bottom, CELL_H)`） | `tools/bake_plot.py::decide_band` | **红**：三条测试同时失败——合成用例 `test_decide_band_ink_dominates_when_zh_is_short`（`22 <= 14` 断言失败）、真实数据用例 `test_real_card6_ink_dominates_over_short_zh`（`24 == 15` 断言失败）、以及连带命中的 `test_decide_band_fallback_marks_whole_zone_hard`（回退格的 `content_bottom` 本该等于 `FALLBACK_BAND_BOTTOM=28`，因为这条路径也经过同一个 `max()`，变异后变成 14） |

三组均为**真红**、且命中的断言内容与变异描述精确对应（不是被无关测试
连带打死）。每次确认变红后立即用 `Edit` 精确复原对应代码行，复原后
`tests/test_bake_plot.py -q` 与全量 `pytest -q` 均恢复通过，无一遗留。

### 8. 测试结果

- `tests/test_bake_plot.py`：从上一版的 21 条**全面改写为 38 条**（旧的
  「按列取 box 下边界颜色平铺擦除」相关测试已随实现一起废弃，替换为墨迹
  检测判据、`decide_band` 双向 max 逻辑、hard/soft 色带渲染、墨迹回退
  播报四组新测试；格号映射、换行/超长截断、真实素材健全性等与本轮改动
  无关的测试原样保留）。单独跑：**38 passed**。
- 全量套件 `uv run pytest -q`：本轮改动前 **854 passed**（任务交办时的
  基线），改动后 **871 passed**，净增 17 条 = `test_bake_plot.py` 的
  38 条新测试 − 21 条被替换掉的旧测试，与全量增量精确对齐，无其他文件的
  测试受影响。
- 无 skip、无 xfail。

### 9. `_cellzoom.png`：人工复核用的挑难格子集

10 格，2 排 × 5 列，每格上下两排对照（原图 / 新产物），每排各画两条标线
（青色=`content_bottom`，粉色=`band_bottom`）：

| 卡号 | 标题（zh） | 挑选理由 |
|---|---|---|
| 162 | 第二物语 | 195 格里唯一的墨迹检测失败（回退），且回退高度仍盖不住原 logo 副标题——已知局限的直接展示 |
| 6 | 想不起约定 | 墨迹主导 max() 的真实证据（JP 2 行, zh 1 行） |
| 25 | 选择：声音的主人 | 中文主导 max() 的真实证据（JP 1 行, zh 2 行），且软区透明度在此格清晰可见 |
| 59 | 游泳池 | 高亮度背景（泳池水面）+ 短标题——联合判据抗亮背景误判 + 高度回收的双重展示 |
| 195 | 章节 5：アヤノ | 高亮度背景（天空/走廊）+ 2 行标题 |
| 101 | サクラ的来信 | 中等亮度人物特写背景，细节丰富格子的效果参照 |
| 115 | アヤノ | 195 格里平均亮度最低（几乎全黑的夜景），检测在极端另一端是否稳健 |
| 170 | 选择：将アヤノ―― | 墨迹高度实测异常值（17 行，非典型的 9/21），第二行只有破折号，展示判据如实反映真实笔画而非套模板 |
| 180 | サクラ的日记：7月（未写完） | 15 字最长标题之一，2 行长文本的最坏情况覆盖需求 |
| 9 | 早晨的教室 | 短标题、中等背景——对照旧方案固定 28 行 vs 新方案 19 行，展示插图回收效果最直观的一格 |

选格刻意避开"好看"的格子，覆盖：回退、双向 max 各一个真实证据、亮背景
×2、暗背景、异常墨迹高度、最长标题、以及一个直观对比新旧方案差异的
普通格子。

### 复核用命令

```bash
uv run pytest tests/test_bake_plot.py -q      # 38 passed
uv run pytest -q                               # 871 passed（全量）
uv run python3 tools/bake_plot.py              # 重新生成 build/plot_zh/*
                                                # （含新增 _cellzoom.png）
```

---

## 追记（2026-08-08 第二次）：用户裁定后的收尾修正——卡 162 回退格色带瘦身

**状态：DONE**（`build/plot_zh/plot_{1..4}_a.png` + `_compare.png` +
`_cellzoom.png` + `manifest.json` 全部重新生成；`tools/bake_plot.py`、
`tests/test_bake_plot.py` 均已改写；`uv run pytest -q` **877 passed**）。

### 0. 用户裁定原文与本轮范围

用户看过 v2 版实物（上一节）后明确裁定：

> 「卡162 在 plot_3_a.png 中的效果我可以接受（指只渲染『第二物语』四个字，
> 副标题就放弃了），不过此时只需一行字了，黑色背景色带 vertical 方向宽度
> 似乎太宽（留出了第二行），修正这一点以后我觉得应该就可以满意了。」

即：**接受**"副标题 `〜彼女の夏、15分の記憶〜` 不被覆盖、仍部分可见"这个
代价（这本来就是 v2 版已明说的已知局限，见上一节第 3 节）；**要修**的只有
"回退格色带高度不该再是固定值，该按中文实际只需的行数算"这一点。本轮只动
`decide_band` 的 fallback 分支，非回退的 194 格正常分支不得受影响。

### 1. 改法：fallback 分支从"写死高度"改成"照实测中文渲染高度走"

**改之前**（v2 版 `decide_band`）：不管 ink 检测是失败（`no_ink_detected`）
还是判定不合理（`implausible_ink_bottom_N`），一律把 `ink_bottom` 赋值成
模块常量 `FALLBACK_BAND_BOTTOM=28`，再和 `zh_bottom`（中文实测渲染高度）
取 `max()`——但因为 `FALLBACK_BAND_BOTTOM=28` 是按"2 行日文 + 安全边"倒推
的固定值，几乎总是比任何 1 行中文标题的 `zh_bottom` 大，`max()` 名存实亡，
实质上永远是这个固定 28。

**改之后**：回退分支不再有任何"填充候选值"参与 `max()`——因为墨迹位置
根本不可信/未知，没有东西可以拿来 `max()`。`content_bottom` 直接等于
`min(zh_bottom, CELL_H)`，`zh_bottom` 是 `measure_rendered_text_bottom()`
真实渲染中文行文字后读出的 alpha bbox（行数 × 行高 + `ZH_BOTTOM_MARGIN`
安全边，不是公式估算）。`BandDecision.ink_bottom_used` 在回退时改为
`None`（明确表示"这一侧没有可信测量值"，不再是一个被悄悄当真的假数字）。
`hard_range` 仍然是整个 `(0, content_bottom)` 全部强制不透明——这条不变，
只是这个区间本身现在更矮了。

非回退分支（`else` 分支：`ink_bottom = ink[1] + INK_BOTTOM_MARGIN`；
`content_bottom = min(max(ink_bottom, zh_bottom), CELL_H)`）**逐字节未改
一行代码**，见下第 4 节的专门回归钉子。

### 2. `FALLBACK_BAND_BOTTOM` 常量的处置：删除，不留"看起来还在用"的空壳

按用户方原文硬约束（"限了什么就要说出来"+"别让常量看起来还在用、实际
已不起作用"），`FALLBACK_BAND_BOTTOM = 28` 这一行**已从代码里整体删除**
（不是注释掉、不是改名保留）。原定义处换成一段说明性注释，交代：
①这个常量曾经是什么、为什么现在没有了；②新回退高度改成了什么；③这是
一次刻意的保守性削弱而非中性重构，未检测到的日文墨迹在回退格上可能残留
可见；④这个削弱必须被 `collect_ink_fallbacks`/`run()`/`main()` 全程播报，
不能静默发生。所有引用点（`decide_band` 内部两处赋值、`main()` 的 CLI
打印、`collect_ink_fallbacks` 的 docstring）同步改写，代码库里已**没有
任何位置**再引用这个名字（仅剩的 3 处是纯注释里提及"这个常量曾经存在过"
这一历史事实，供后来人查证，不是代码路径）。

### 3. 卡 162 修正前后的色带行数对比（用户诉求的直接量化答复）

| | 改前（v2 版，本节改动之前） | 改后（本次改动） |
|---|---|---|
| `content_bottom`（必须覆盖区） | 28 | 14 |
| `band_bottom`（含羽化，可见色带总高） | **32**（y0–31，共 32 行） | **18**（y0–17，共 18 行） |
| `hard_range`（强制不透明区） | (0, 28) | (0, 14) |
| `ink_bottom_used` | 28（其实是 `FALLBACK_BAND_BOTTOM` 顶替的假值） | `None`（如实标记"未测出"） |

中文标题「第二物语」只需 1 行，`measure_rendered_text_bottom` 实测其渲染
高度为 13px（不含安全边）+ `ZH_BOTTOM_MARGIN=1` = 14，这就是新
`content_bottom`；`band_bottom = min(14 + BAND_BOTTOM_FEATHER_PX(4), 48)
= 18`。可见色带从 32 行砍到 18 行，砍掉的 14 行不再是"空出一大片纯黑、
像故障"，而是——按用户已接受的代价——副标题 `〜彼女の夏、15分の記憶〜`
的上半部分重新可见（`_cellzoom.png` 卡 162 格子肉眼可核）。

副作用（全 195 格的 `band_bottom` 范围）：`manifest.json` 的
`band_bottom_max` 从改前的 32（正是卡 162 自己顶到的，其余 194 格实测
最大值只有 31）降到改后的 31（卡 162 不再是全场最高，退回到其余非回退
格的正常范围内）；`band_bottom_min` 两版都是 18（非回退格里本来就有格子
落在这个值，卡 162 现在恰好也落进这个区间，纯属巧合不是特意对齐）。

### 4. 告警措辞：CLI / manifest.json / `run()` 报告三处同步

**问题**：v2 版的回退播报只说"这些卡回退了、原因是什么"，没有说清楚
"回退之后色带覆盖能力本身也变了"这件事——这次改动把回退格的覆盖收窄了，
必须把"收窄"本身当成一条新的、独立的告警说出来，不能只延用旧播报机制
默认盖过去。

**实现**：新增 `build_ink_fallback_coverage_note(fallbacks)`（独立可测
的纯函数，不内联在 `run()` 里，理由见其 docstring：要能脱离"今天
`png/plot/` 恰好有卡 162 这一个回退格"这个具体前提单独测试）。没有回退
时返回 `None`；有回退时返回一句明确点名以下三件事的英文说明：①有几张卡、
哪几张卡回退；②这些卡的色带高度现在只按中文渲染需要的高度算，不再是
固定保守值；③原文日文墨迹的真实范围未知，**可能在色带下方残留可见**
（"MAY REMAIN PARTIALLY VISIBLE"）。

三处落地：
1. **CLI**（`main()`）：`fallback cards` 清单打印之后新增一行
   `  ⚠ {report['ink_fallback_coverage_note']}`，本轮真实跑批实际输出：
   ```
   ink detection: 194/195 cells detected, 1 fell back to caption-only band coverage
     fallback cards (MUST be reviewed by a human -- band height for these was never measured against real ink, only against the zh caption's own rendered height):
       card 162: no_ink_detected
     ⚠ 1 card(s) fell back to caption-only band coverage (ink location could not be measured): [162]. For these cards ONLY, the band height is sized to the zh caption's own rendered height (line count x line height + margin), NOT to a fixed conservative height -- the true extent of the original Japanese ink is unknown, so any of that ink extending below the zh-sized band MAY REMAIN PARTIALLY VISIBLE. Human review required for each card listed in ink_fallback_cards.
   ```
2. **`manifest.json`**：新增顶层字段 `ink_fallback_coverage_note`（本轮
   真实产物里就是上面那句话，`null` 当且仅当没有任何回退）。
3. **`run()` 的 report 字典**：同一个字段，`test_ink_fallback_coverage_note_names_the_reduced_guarantee`
   钉住其内容必须同时出现卡号、"caption"、"visible"、"unknown" 四类关键词，
   不能被弱化成一句不痛不痒的状态说明。

### 5. 变异红绿实况（本轮新增，Edit 应用+还原，未使用任何 git 回滚命令）

三组必做变异全部按「关闭闸→跑测试确认真红→Edit 精确复原→跑测试确认恢复
绿」的流程做过：

| # | 变异内容 | 改动位置 | 结果 |
|---|---|---|---|
| A | 回退格色带高度改回固定值（`content_bottom = min(zh_bottom, CELL_H)` → `content_bottom = min(28, CELL_H)`） | `tools/bake_plot.py::decide_band` fallback 分支 | **红**：2 条测试失败——`test_decide_band_fallback_marks_whole_zone_hard`（`assert 28 == 14`）、`test_real_card162_fallback_band_sized_to_zh_caption_not_fixed_height`（同样 `assert 28 == 14`，真实卡 162 素材端到端复现） |
| B | 「回退格只覆盖文字高度」告警不播报（`build_ink_fallback_coverage_note` 提前 `return None`） | `tools/bake_plot.py::build_ink_fallback_coverage_note` | **红**：3 条测试同时失败——`run()` 报告层 `test_ink_fallback_coverage_note_names_the_reduced_guarantee`（`assert None is not None`）、纯函数单测 `test_build_ink_fallback_coverage_note_names_cards_and_risk`（同上）、CLI 层 `test_cli_check_mode_prints_ink_fallback_coverage_warning`（打印出的 `⚠ None`，`"PARTIALLY VISIBLE" not in out`）——三个播报出口全部各自被独立测试覆盖，不是只测了其中一处就当作全测 |
| C | 回退逻辑波及了正常格的高度（`decide_band` 的 `if fallback / else` 分支被合并成不管三七二十一都只用 `content_bottom = min(zh_bottom, CELL_H)`，`ink_bottom` 只在非回退时才算但不再参与 `content_bottom`） | `tools/bake_plot.py::decide_band` | **红**：3 条测试同时失败——专门为本次改动新增的回归钉子 `test_decide_band_nonfallback_cells_unaffected_by_fallback_refactor`（用改动前的生产代码跑出的 13 张真实非回退卡金标准数据，`card 6 content_bottom: assert 15 == 24`）、以及连带命中两条 v2 版就有的既有测试 `test_decide_band_ink_dominates_when_zh_is_short`（`assert 14 >= 22` 失败）、`test_real_card6_ink_dominates_over_short_zh`（`assert 15 == 24` 失败）——证明"正常格必须保留墨迹主导"这条性质有双重覆盖（新钉子 + 老测试），不是只靠一条新测试孤立扛着 |

三组均为**真红**、且命中断言内容与变异描述精确对应；每次确认变红后立即
用 `Edit` 精确复原对应代码块，复原后 `tests/test_bake_plot.py -q` 与全量
`pytest -q` 均恢复通过，全程未使用任何 `git checkout`/`stash`/`restore`
等回滚类命令。

### 6. 测试结果

- `tests/test_bake_plot.py`：从上一版的 38 条增至 **44 条**（新增 6 条：
  卡 162 端到端回归钉子 1 条、告警内容测试 2 条（`run()` 层 + 纯函数层，
  含"没有回退时 note 必须是 None"的反向确认）、CLI 播报测试 1 条、正常格
  不受影响的回归钉子 1 条；另外把 2 条引用了已删除常量
  `FALLBACK_BAND_BOTTOM` 的既有测试原地改写为不依赖任何写死数字的独立
  实测断言，未净增未净减条目）。单独跑：**44 passed**。
- 全量套件 `uv run pytest -q`：本轮改动前 **871 passed**（任务交办时的
  基线），改动后 **877 passed**，净增 6 条，与
  `tests/test_bake_plot.py` 的净增条数精确对齐，无其他文件的测试受影响。
- 无 skip、无 xfail。

### 7. 产物重新生成

`uv run python3 tools/bake_plot.py` 重新生成 `build/plot_zh/`：
`plot_{1..4}_a.png`、`_compare.png`、`_cellzoom.png`（`CELLZOOM_CARDS` 表
里卡 162 本来就排第一位，本轮沿用不必新增）、`manifest.json`。已用 Read
工具目视核对 `_cellzoom.png`：卡 162 格子（左上角第一格）的青/粉标线明显
比其余格子更贴近文字底部，黑色色带只压住「第二物语」一行，副标题
`〜彼女の夏、15分の記憶〜` 的上半部分在色带下方重新透出——与用户裁定的
预期完全吻合。

### 复核用命令

```bash
uv run pytest tests/test_bake_plot.py -q      # 44 passed
uv run pytest -q                               # 877 passed（全量）
uv run python3 tools/bake_plot.py              # 重新生成 build/plot_zh/*
                                                # （卡 162 在 _cellzoom.png 里排第一格）
```
