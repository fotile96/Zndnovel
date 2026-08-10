# `png/card/` 版面测绘报告（第三块烤字：测绘 only，不渲染）

任务：对 `png/card/`（197 张，196 张卡面 `crd_<N>_a.png` + 1 张空白模板
`crd_0_d.png`）做版面测绘，产出 `build/card_layout_spec.md`（体例照
`docs/ops/bake-specs/scene-layout-spec.md`），本轮**不渲染成品**。本文件
是过程报告（证据链、复核结果、变异红绿、测试结果），规格快照另见
`docs/ops/bake-specs/card-layout-spec.md`（同步落盘 `build/card_layout_spec.md`
一份，因为 `build/` 被 gitignore）。

工具：新增 `tools/measure_card.py`（测绘/复核函数，**没有渲染/烘焙函数**——
本轮任务边界明确要求"不渲染成品"，所以没有写 `bake_card.py`）与
`tests/test_measure_card.py`（18 个测试）。

## 一、坐标的证据链

### 1.1 先查代码：`ObjectCard` 里没有内部区块的裁切坐标

`grep -n "layerClip" lua_scripts/snr_common.lua` 在 `ObjectCard`
（`:4303-4950`）范围内**零命中**。`ObjectCard.show(p0, p1)`
（`:4315-4332`）只是：

```lua
layerLoad(v0.layerNo, p0)   -- 整张 212x148 图当一个 layer 加载
layerMovePosition(...)      -- 移动/淡入淡出整个 layer
```

这与 `plot/`/`scene/` 的精灵图集结构不同——那两处的格子边界来自
`snr_common.lua` 里写死的 `plotState`/`sceneState` 构造循环，是可引用行号
的一手代码证据；`card/` 每张图本身就是一个独立文件，标题/正文/右栏三块
文字是制作卡面美术时直接烤进图片的，**引擎从未在运行时对它做任何内部
切分**。所以本轮"卡面内部三区坐标"这条结论**没有代码可引**，唯一可用
方法是像素测量——这一点在 `docs/ops/bake-specs/card-layout-spec.md` 第 0
节里显式记录为"查过、确实查不到"，不是跳过纪律，是纪律执行的结果之一。

（唯一容易张冠李戴的地方：`cardModeSet`/`cardModeSelect` 里确实有
`layerClip(i6, x, y, x+26, y+15)`，但那是 fragment 模式底部卡片选择器的
`sys_11_b/c/d` 图标网格，与 `png/card/` 无关——已在 spec 第 0 节写明防止
后续任务误用。）

### 1.2 像素测量出的坐标（可复算）

| 区块 | 坐标（半开区间） | 测法 |
|---|---|---|
| 内框 `INTERIOR` | `(10,10,202,138)` | `crd_0_d.png` 列/行扫描找黑色边框行/列 |
| 横分隔线 | `y=41`，色 `(187,174,165,255)` | 同上，颜色明显区别于渐变背景与黑边框 |
| 竖分隔线 | `x∈[136,138]`（中心 137） | 同上，纵向跨度 `y∈[41,133]` |
| `TITLE_ZONE` | `(10,10,202,41)` | 横线以上 |
| `BODY_ZONE` | `(10,42,136,138)` | 横线以下、竖线以左 |
| `RIGHT_ZONE` | `(139,42,202,138)` | 横线以下、竖线以右 |

墨迹交叉验证（`collect_ink_bbox`，判据 `max(r,g,b)<120 且 alpha>=200`）：
8 张抽样卡（1/2/3/90/145/180/182/200，覆盖最长标题/最多行正文/绘本体/
编外卡等边界情形）在三区的墨迹 bbox **全部落在对应区域内**，零越界
（`tests/test_measure_card.py::test_ink_never_exceeds_zone_bounds_for_sampled_real_cards`）。
标题区额外对**全部 196 张卡**（非抽样）验证恒为单行
（`test_all_196_real_cards_have_single_line_title_ink`，196/196 通过）。

## 二、底色形态判定

三次独立测量，逐步排除掉两种"照抄先例"的可能：

1. **不是 `scene/` 式字节级共享模板**：内容区中心点 `(105,74)` 在 196 张
   卡上取到 81 个不同 RGBA 值（若是共享模板应恒为 1 个值）。
2. **不是 `plot/` 式真照片内容**：明确不含文字的安全采样点
   （如横线下方留白 `(100,44)`）在 196 张卡上高度集中——R 跨度仅 9、
   G 跨度 12、B 跨度 18，是"同一条对角渐变、各自单独渲染/量化"的量级，
   不是"每格换一张完全不同照片"的量级。
3. **唯一真正的边框颜色异常：卡 94**
   （`find_border_color_outliers`，4 点采样红/粉判据 `r>150,g<60,b<60`，
   196 张卡里只有卡 94 落在判据外，采样值 `(208,125,46,59)` 明显偏橙）。
   目视核对该卡 BODY_ZONE 是一幅人物插画（`build/card_probe/card94_3x.png`），
   与 `skeleton/cards.jp.yaml` 该卡既有 note「卡框为橙色系配色…」的记录
   完全吻合——本次是**独立的像素复核**，不是照抄已有 note，两者互相印证。

**结论**：194/196 张卡（除卡 94、144，两者 `body_zh` 为空）的三个文字区
背景是同一套"渐变+边框"设计、各自单独渲染的产物，**没有需要保留的独特
美术内容**，可以安全覆盖重绘；**卡 94 的 BODY_ZONE 是例外，是真正的插画
内容，绝不能覆盖**；卡 144 的 BODY_ZONE 是真空白（无插画无文字），可覆盖
但因无 `body_zh` 无需渲染，实践中可以不碰。

## 三、试排结果——完整溢出清单

字体 `third_party/LXGWWenKai-Regular.ttf`（该字体在字号 N 时前进量精确为
N px/字，与 `plot/`/`scene/` 报告用的同一验证方法）。候选字号按第 4 节
测出的原文前进量选取：标题 11px/176px、正文 9px/110px（硬顶精确值）、
右栏 8px 与 9px 两档对照，均 53px 预算。

| 区块 | 字号/预算 | 溢出数 | 备注 |
|---|---|---|---|
| 标题 | 11px / 176px | **0 / 196** | 最紧余量 23px（卡182） |
| 正文（片段级） | 9px / 110px | **0 / 194** | 最紧余量仅 **2px**（卡5/9/14/15…多行），已在 spec 里标注风险 |
| 正文（行数级） | max_lines=7 | **0 / 194** | 最多行数卡（167、134）恰为 7 行，无冗余 |
| 右栏 | 8px / 53px | **0 / 196** | 最紧余量 21px（"物语梗概"系列） |
| 右栏 | 9px / 53px | **0 / 196** | 最紧余量 17px（同上），两档都不溢出 |

**全部五项溢出统计均为空列表，且是"检查过确实是空"，不是"没检查"**——
每个 `trial_wrap_*` 函数都实际调用 `tools.zh_wrap.wrap()` 并读取其
`info["truncated"]`，`tests/test_measure_card.py` 用合成超长输入验证过
这条路径会触发（见下第五节的变异②）。

**结构性折行规则复核（任务明确要求"自己复核"这个数字）**：
`find_structural_breaks()`（同一判据的独立重新实现，未复用旧报告脚本）
在全库跑出 **27 处**非宽度驱动断点（不含卡 145），quote-line 规则
**27/27 全覆盖**；卡 145 自身贡献第 28 处（"妖怪 纳哈梅"/"就要 找上门"
合并宽度 22≤24），但它不是 quote-line 形态，是独立的"绘本体整卡不重排"
例外覆盖的——**27（quote-line）+1（卡145专属）=28，与任务陈述的
"28 处结构性断点 28/28 全覆盖"完全吻合**。

## 四、方案建议

**不是简单照抄 `scene/` 或 `plot/` 任一先例，是两者的混合**：

- 像 `scene/`：三个文字区可以用**全局固定矩形**（不需要 `plot/` 那种
  逐格动态测墨迹高度），因为背景不含需要保留的独特美术内容（第二节）。
- 不像 `scene/`：背景是**位置相关的渐变**，不是单一常量色，硬编码一个
  `(r,g,b,a)` 填色会在文字区边界产生可辨色阶断层——需要重建渐变，倾向
  直接复用 `crd_0_d.png` 对应坐标的像素（比 `plot/` 的"按列取邻近像素
  延伸"更简单，且第二节的证据显示这么做产生的保真度损失很小）。
- 卡 94 需要单独的"跳过 BODY 覆盖"处理路径，是全库唯一需要它的卡。
- 字号选择（标题11/正文9/右栏8或9px）与原文视觉当量精确匹配，且试排
  证明全部放得下——但正文 9px 的 2px 最小余量意味着**回落机制仍值得预留
  接口**，即使今天的数据不触发它。

详细理由与被否决的备选方案见 `docs/ops/bake-specs/card-layout-spec.md`
第 8 节。

## 五、变异红绿实况

按任务要求，至少验证两处变异真红：

### 变异①：去掉"「…」独占一行不与相邻行合并"的保护

手工在 `tools/measure_card.py::wrap_body_zh` 里把

```python
if _QUOTE_LINE_RE.match(line):
    if buf: segments.append(("prose", "".join(buf))); buf = []
    segments.append(("quote", line))
else:
    buf.append(line)
```

替换为无条件 `buf.append(line)`（模拟"规则被删除，一切都当宽度驱动的
散文处理"），重跑相关测试：

```
FAILED test_wrap_body_zh_never_merges_a_standalone_quote_line_with_its_neighbor
FAILED test_wrap_body_zh_MUTATION_without_quote_guard_would_merge_options
2 failed, 2 passed（该子集 4 个测试内）
```

用户点名的真实案例（卡 4 的选项列表「想不起来」「约好了」「没有约」）
在变异后被合并重排成 `['「想不起来」「约好了」', '「没有约」有以上分支展开。']`
——两个引号选项在同一行黏在一起，正是这条规则要防止的失败模式。**真红
确认**，之后 `cp /tmp/measure_card.py.bak tools/measure_card.py` 还原
（未使用任何 git 回滚命令，纯文件级 Edit/覆盖还原）。

### 变异②：溢出统计被静默吞掉

手工在 `tools/measure_card.py::trial_wrap_titles` 里把

```python
if info["truncated"]:
    overflow.append({...})
```

替换为 `pass`（模拟"检查了但没上报"），重跑相关测试：

```
FAILED test_trial_wrap_titles_surfaces_a_synthetic_overflow
1 failed, 3 passed（该子集 4 个测试内）
```

用一条刻意超长的合成标题（`"测"*200`）验证：变异前能在 `overflow` 里
看到这条记录，变异后完全消失（`len(report["overflow"])` 从 1 变 0）。
**真红确认**，同样用文件覆盖还原（`diff` 确认与备份逐字节一致）。

## 六、测试结果

```
uv run pytest tests/test_measure_card.py -q
18 passed in 50.19s

uv run pytest -q   （全仓库回归）
991 passed in 80.45s   （基线 973 + 本轮新增 18，无回归）
```

## 七、需要用户裁决的事项（详见 spec 第 7 节，此处仅列条目）

1. 右栏 3 行特殊卡（26/118/158/162）的非均匀行距（10px+25px）怎么复刻：
   原样复刻 / 统一等距 / 考虑中文侧合并译成 2 行。
2. 正文 9px 最紧仅 2px 余量：接受现状，还是像 `scene/` 一样做字号回落
   阶梯留安全垫。
3. 右栏字号 8px vs 9px：两档都不溢出，纯观感选择，需要看实物。
4. 背景重建策略：复用 `crd_0_d.png` 像素直接贴入，还是逐卡自身边缘延伸
   重建（`plot/` 的技术）——本报告倾向前者但非定论。
5. 卡 94 的完整处理流程（跳过 BODY 覆盖的开关怎么在渲染管线里体现）需
   用户确认。

## 八、涉及文件

- `tools/measure_card.py`（新增，测绘/复核函数，无渲染函数）
- `tests/test_measure_card.py`（新增，18 个测试）
- `docs/ops/bake-specs/card-layout-spec.md`（新增，规格快照，入库）
- `build/card_layout_spec.md`（同内容副本，gitignore，供本轮交付路径）
- `build/card_probe/`（一次性像素核对截图，gitignore，未入库，佐证本报告
  第二节的目视核对——`card1_3x.png`/`card0_3x.png`/`card2_3x.png`/
  `card94_3x.png`/`card144_3x.png`/`card26_3x.png`）
