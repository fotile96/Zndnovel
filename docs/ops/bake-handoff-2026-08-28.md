# 烤字工程交接（2026-08-28）

> 新会话直接读这一份即可上手。**下面每一条数字都是实测的**，凡"大概/少量/个别"这类
> 词都已被清点替换——本轮最大的教训就是台账里的形容词等于那一格从没被清点过。

## 0. ~~手头没做完的那件事~~ ✅ 已完成（2026-08-28 当日）

**用户看了 `cutin/` 的成品，觉得「衬线的感觉不明显」，提出试仿宋，让先看 macOS 自带字体。**

**结果：`cutin` 定为华文仿宋 STFangsong**（用户看过八路对照 `build/font_ab/cutin.png`
后裁定）。已落 `config/bake_fonts.yaml`，`build/cutin_zh/` 24 张已用它重烤。
裁决 F5–F7 见 `bake-decisions.md`；`tools/ui_font.py` 已支持 `路径#N` 的 TTC 子字体索引。

**2026-08-29 续**：用户又提「原图感觉都有点像斜体」，逐档试后加了两个**主动偏离
原图**的旋钮——`slant: 0.10` + `size_bias: 1`（裁决 F8–F10）。⚠ 同轮实测证明
**原图并没有被切变**（残差中位 +0.008，n=23）：中途我报的「原图右倾 19°」是判据
错了，那把尺子量的是字形内容而非几何。详见 `bake-decisions.md` 的更正节。

⚠ **下表「九款全部零缺字」这句是错的，勿再引用。** 按真实待烤文本逐字与 `.notdef`
位图比对：**儷宋缺 43 字、蘋果儷細宋缺 100 字**（繁体字库，`章节` 的「节」即在其中），
两款已出局；其余七款对 cutin 零缺字，只缺 `・`（仅见于 sysgim 的 `sys_21_a`）。
当初的错法是拿手编测试串、以「渲染没报错」当判据——**PIL 渲染缺字时静默画豆腐块**。

已完成的调研：

| 候选 | 路径 | 字形覆盖 |
|---|---|---|
| 霞鹜文楷（cutin/sysgim 现用） | `third_party/LXGWWenKai-Regular.ttf` | ✓ |
| 思源黑体 Medium（其余四面现用） | `third_party/SourceHanSansSC-VF.ttf` | ✓ |
| **华文仿宋 STFangsong** | `/System/Library/AssetsV2/com_apple_MobileAsset_Font7/1821952872c81043711aab6910052b65da8edf2c.asset/AssetData/STFANGSO.ttf` | ✓ |
| 宋体 Songti SC Light | `/System/Library/Fonts/Supplemental/Songti.ttc` **index 3** | ✓ |
| 宋体 Songti SC Regular | 同上 **index 6** | ✓ |
| STSong | 同上 **index 4** | ✓ |
| 儷宋 LiSongPro | `…/5a3fc034…asset/AssetData/LiSongPro.ttf` | ✓ |
| 蘋果儷細宋 AppleLiSung-Light | `…/2ae839cb…asset/AssetData/AppleLiSung-Light.ttf` | ✓ |
| SimSong | `…/857d6c90…asset/AssetData/SimSong.ttc` | ✓ |

~~测试串 `章节 1：完 章节 5：Sakura 章节 EX2：雪乃 五年后 女学生 梗概跳过` 九款
**全部零缺字**。~~ ← **这句是错的，见本节开头的更正。**

~~**下一步（被打断处）**：`tools/ui_font.py` 不支持 TTC 子字体索引~~
✅ 已加：`路径#N`，环境变量与配置同一套解析，**集合不写索引报错**（F7）。
已知索引：`Songti.ttc` `#3` SC Light / `#4` STSong / `#6` SC Regular；`SimSong.ttc` 仅 `#0/#1`。

两条约束**已告知用户并被接受**：

1. **除霞鹜文楷与思源黑体外，上表全是 Apple 随系统分发的商业字体**，不是 SIL OFL。
   裁决 G1 把霞鹜文楷入库正是为了"换机器即开即用"；这些**不能入库**。用户选定华文
   仿宋，即**接受"cutin 只能在装了该字体的 mac 上复现"**（裁决 F6）。若日后要回到
   可移植方案，思源宋体 Source Han Serif 是最直接的 OFL 衬线候选（**本机未装**）。
2. **`AssetsV2` 下的路径带哈希**，是按需下载的字体资产，系统更新后可能变化。
   重新定位：`ls /System/Library/AssetsV2/com_apple_MobileAsset_Font7/*/AssetData/STFANGSO.ttf`。
   路径失效时 `resolve()` 抛 `FileNotFoundError`，不会悄悄换字。

---

## 1. 一句话现状

七个面里 **5 个已完工**（plot/scene/card/select + event），sysgim 完成 40/61，
cutin 完成 24/45+，另有 5 张模式画面/缩略图与 `tut_*` 16 张未开工。
**tests 1466 passed**，四道闸全绿。工作树只有三项与本工程无关的既存改动
（`.claude/settings.json`、`data/api_ledger.jsonl`、`pilot/polish/p5seg7-e2/decisions.draft.jsonl`）。

## 2. 各面进度

| 面 | 总数 | 已烤 | 状态 |
|---|---:|---:|---|
| `png/plot/` | 4 | 4 | ✅ 完工 |
| `png/scene/` | 2 | 2 | ✅ 完工 |
| `png/card/` | 197 | 196 | ✅ 完工（1 张空白模板不烤） |
| `png/select/` | 278 | 134 按钮 + 地图 | ✅ 完工（22 孤儿 + 3 异形不做） |
| `png/event/` | 121 | 6 | ✅ 完工（其余 115 张 `eve_` 是 CG，无字） |
| `png/sysgim/` | 61（处理面） | **40** | A/B/C 三族完工；**剩 D 2 张 + E 17 张** |
| `png/cutin/` | 73 | **24** | 字幕卡完工；**剩 `tut_*` 16 张** |
| `png/graphic/` | 18 | 0 | **剩 4 张**（`graphic_01_a`/`memory_01_a`/`memoryThumbnail_1_a`/`_2_a`） |
| `png/music/` | 4 | 0 | **剩 1 张**（`music_01_a`；曲目表 3 张用户裁定不译） |
| `png/bg/` | 81 | — | ✅ 清点闭合，**0 张含字** |
| `png/novel/` | 993 | 0 | 未立项（竖排小说整页，建议单独立项） |

## 3. 还要做的，按建议顺序

### ① 模式画面框 3 张 + memoryThumbnail 2 张（最轻）

- `music_01_a`「視聴曲を選択してください。」/ `graphic_01_a`「画像を選択してください。」/
  `memory_01_a`「シーンを選択してください。」——同一套模板，**各只有 1 行日文**，
  红色发光字，**glow 模型直接适用**，英文大词（`- MUSIC SELECT -` / `× Cancel` /
  `PAGE L button R`）原样保留。
- `memoryThumbnail_1_a`（360×204，9 格）/ `_2_a`（360×136，5 格）：**14 个章节名烤在
  缩略图上**——プロローグ／セクション1／2／3A／3B／いつかきみがみるお話／4A／4B／5／
  6／7／8／EX1／EX2。「いつかきみがみるお話」有冻结定译（骨架卡 145
  `总有一天你会看到的故事。`），`セクション N` 族与 `cutin/cut_s_*` 同源，可直接沿用。
- 用户 2026-08-28 明确：`graphic/` 其余文件（`graphic_02..07_a`、`thumbnail_*`）不做。

### ② sysgim D 类 2 张

- `sys_5_d`（239×74，米黄面板）：可直接做；正文与已入库的 `sys_2_b` 高度重合
  （「あらすじ作成済」族），译文有现成参照。
- `sys_1_g`（127×37）：**全族字号最紧**，3 行塞进 37px ＝每行 12px，
  **等用户看图裁定**（缩短译文还是改 2 行）。
- ⚠ 两张的重建方式是「保留面板、盒内替换」，**现有工具都不是**（outline 是描边字、
  glow 是发光字），需新工具，schema 也随之定。

### ③ sysgim E 类 17 张

**唯一还没做版面测绘的一类。** 只改假名层、英文原样保留（用户裁定）。

- `sys_2_a`（Story Mode）/`sys_3_a`（Fragment Mode）：英文大词 + 「-ストーリーモード-」小注
- `sys_12_a/b/c`：ゲームオーバー／タイムオーバー／セクションコンプリート +
  `- GAME OVER -` 等。⚠ 假名层压在半透明黑带上（顶部 26 行实测 `(0,0,0,242)`/`(0,0,0,204)`），
  与已解决的 `sys_11_a` 同类，**模型已通**。
- `title_02_a`…`title_13_a`（12 张）：每张含**暗态（纯英文）+ 亮态（英文+青色假名小注）
  上下叠放**，小注只在亮态。02 Prologue／03 Story／04 Fragment／05 library／06 option／
  13 Section 7 小注在英文下方；07 save／08 load／09 novel／10 memory／11 graphic／
  12 music 小注在右侧。
- 译文：一半有现成定译（ストーリー→故事目录、フラグメント→片段目录、オプション→设置、
  ストーリーモード→故事模式、ゲームオーバー→游戏结束、セクションコンプリート→章节全通），
  **缺 7 条**：プロローグ／セクション7／記録する／再開する／シーン回想／ミュージック／
  タイムオーバー（正文零命中）。

### ④ cutin `tut_*` 16 张（最重）

`tut_0_a`、`tut_1_a`、`tut_2_a..e`、`tut_3_a/b`、`tut_4_a/b`、`tut_5_a/b`、`tut_6_a`、
`tut_7_a`、`tut_8_a`。`information` 标题框 + **大段日文说明正文**，多张带游戏画面截图
与红框标注。**本批文本量最大、版面最复杂**——正文是段落且压在截图上，背景重建难度
高于 sysgim C 类。做之前需单独测绘。

### ⑤ 用户已裁定不做的

`music_02/03/04_a`（BGM 曲目表）、`graphic_02..07_a`、`thumbnail_01..08_a`、
`cutin/cut_nv_*` 5 张（小说封面）、`cutin/cut_N` 28 张（道具特写；其中确有日文的至少
`cut_51` 绘本页、`cut_53` 手帐、`cut_54` **黑板板书**、`cut_60`/`cut_61` 纸条、
`cut_63` 便签、`cut_64`）。sysgim 的 `sys_10_a`、`title_01_a/b`、`IPL01/02` 五张
（题名/厂牌 logo，裁决 Y3）。

⚠ CLAUDE.md 有一处**记错**：「`bg/` 少量含字（黑板板书等）」——黑板板书在
`cutin/cut_54`，`bg/` 81 张一张烤字也没有。（这条是看图判断，无机器判据，
可信度低于本文件其余结论。）

## 4. 工具与闸

### 烤字工具

| 工具 | 面 | 备注 |
|---|---|---|
| `bake_plot.py` / `bake_scene.py` / `bake_card.py` | plot/scene/card | |
| `bake_select.py` / `bake_select_map.py` | select | |
| `bake_sysgim_outline.py` / `bake_sysgim_glow.py` | sysgim A/B/C | |
| **`bake_para_glow.py`** | —— | **段落式发光烤字的共用核心** |
| `bake_event_op.py` / `bake_cutin_title.py` | event / cutin | 各只是一份 `Spec` |

**新面加一个 `Spec`，别复制一份工具。** `tut_*` 会是第三个消费者。

对照/测绘辅助：`bake_font_ab.py`（多字体并排 + 数字差异）、`bake_select_seat_ab.py`、
`bake_scene_size_ab.py`/`_ab2.py`、`measure_card.py`、`measure_sysgim.py`。

### 四道闸（改任何译文后都要跑）

```bash
uv run python tools/measure_ui_terms.py          # 术语表自校准：漂移 / evidence 过期
uv run python tools/check_ui_terms.py <各译文 jsonl>   # UI 用词与正文一致性
uv run python tools/check_bake_text.py           # 译文数据 schema + 待译计数
uv run python -m pytest tests/ -q                # 1466 passed
```

⚠ **顺序有讲究**：先 `measure_ui_terms` 校准表，再 `check_ui_terms` 拿表去检——
反过来是拿旧规则检新译文。

### 可换的环境开关

| 变量 | 作用 |
|---|---|
| `ZND_UI_FONT_<面>` / `ZND_UI_FONT` | 字体（面：PLOT/SCENE/CARD/SELECT/SYSGIM/EVENT/CUTIN） |
| `ZND_UI_FONT_WEIGHT_<面>` / `ZND_UI_FONT_WEIGHT` | 变量字体的重量实例 |
| `ZND_UI_SIZE_CASCADE_<面>` / `ZND_UI_SIZE_CASCADE` | 字号级联档位 |
| `ZND_UI_SLANT_<面>` / `ZND_UI_SLANT` | 倾斜斜率（tan 值，正＝右倾；<1，写角度会炸） |
| `ZND_UI_SIZE_BIAS_<面>` / `ZND_UI_SIZE_BIAS` | 在算出来的字号上加减几档（整数） |
| `ZND_BUILD_TAG` | 产物目录后缀（`build/<面>__<tag>`），多版本并存对比用 |
| `ZND_UI_FILL_GAIN` | sysgim 填充增益（默认 2.2） |

**持久决定写 `config/bake_fonts.yaml`**，环境变量只作临时试验。

### 译文数据

| 文件 | 面 |
|---|---|
| `data/sysgim_outline_text.jsonl` | sysgim A（`box` 可选，是「例外声明」） |
| `data/sysgim_glow_text.jsonl` | sysgim B/C（`box` 必填） |
| `data/event_op_text.jsonl` | event/op |
| `data/cutin_title_text.jsonl` | cutin 字幕卡 |
| `data/select_buttons_zh.jsonl` / `select_options_zh.jsonl` / `select_map_zh.jsonl` | select |
| `data/card_section_labels.jsonl` | card 右栏 |
| `data/extra_translated.jsonl` | 场景名/存档标题等衍生文本 |

新增数据文件要往 `tools/check_bake_text.py` 的 `SOURCES` 注册表加一行，**别新起一个闸**。

## 5. 已定的字体

`config/bake_fonts.yaml`：**card / plot / scene / select = 思源黑体 SC Medium**
（用户 2026-08-28 看过四路对照后裁定）；**cutin = 华文仿宋 STFangsong
+ 斜 0.10 + 字号 +1pt**（F5–F10；**机器本地商业字体，换机器不可复现**）。
sysgim 与 event **仍是霞鹜文楷，未定**，且 sysgim 保留了**逐张覆盖**位
（`faces.sysgim.sheets.<图名>`）。

⚠ 若把仿宋/宋体系推广到 sysgim，先查 `sys_21_a` 的 `・`——那五款系统字都缺它。

选 Medium 的实测依据：卡面 9px 正文的字腔数（被墨迹完整围住的背景连通块）
霞鹜 198 / Regular 304 / **Medium 378**——不降反升 24%。**字腔数低等于「笔画没成形」，
不等于「字腔通透」**。

⚠ **变量字体的默认实例是陷阱**：`SourceHanSansSC-VF` 的默认实例是 ExtraLight(250)
＝权重轴最小值。裸调 `ImageFont.truetype()` 拿到的就是它，两千多张图会在发丝级字重下
烤出来，而且**不报错、不缺字，只是更灰一点**。`ui_font.truetype()` 已把变量字体默认
钉在 Regular。

## 6. 这一轮攒下的方法教训（对后续几批直接适用）

1. **从原图量出来的数有两类，别混。** 几何约束（盒、行距、字芯高）必须复现；
   原文内容的副产物（左缘、块宽）**不该照搬**——它们是「日文有多长」的函数。
   中文普遍只有日文 55–70% 长，照搬左缘会让整块塌向一边。**复现重心，不是左缘。**
2. **合成图上的目视判断不可靠。** 本轮我三次目视误判（把并排图参照系搞错、
   把行数差当成偏移、把字间空隙当硬边），三次都是量了才纠正；而用户看图指出的
   两处（双重缩进 17px、重心偏左 49–73px）都是真的。**看图提怀疑、用尺子定案。**
3. **判据错了不等于素材错了。** 换字体后 `scene` 的切顶检查报 165 张，逐格实证
   （真实画布渲染与加垫画布渲染逐字节相同）表明真被切的是 **0 张**——判据把
   `getbbox()` 的排他上界拿去比排他边界，差一个像素。
4. **逐卡/逐行估计值出现分组时，先怀疑估计量。** 卡面字色取样门槛 0.92 时逐卡值呈
   双峰，看着像「卡片分两种字色」，实为门槛的边界效应；0.97 单峰且与独立证据吻合。
5. **均值会把重建偏差读成物理现象。** 卡面「晕」初测用均值看到长尾，差点去加一层
   距离场发光；换中位数后远场归零，真实衰减只有 2px——那就是抗锯齿边。
6. **两条独立来源必须互相校验，对不上就抛错。** 段落分行结果与人转写的行数不一致
   时，`bake_para_glow` 直接报错而不是将就——继续渲染只会把错误固化进产物。
7. **一个常数满足两面，别给单张开特例。** `LINE_MERGE_GAP` 从 4 改 3 是被
   `cut_s_ex2` 逼出来的，但逐档验过对 `event/op_*` 同样成立才改。
8. **「没报错」不是判据，尤其在渲染上。** 候选字体的缺字检查当初用手编测试串 +
   「渲染没报错」，得出"九款全部零缺字"——而 PIL 遇到缺字**静默画豆腐块**：不抛
   异常、不返回空墨迹、`getlength()` 照样非零。改用「按真正会被烤上去的那串文本
   逐字渲染，与 `.notdef` 位图逐字节比对」后，两款繁体字库分别缺 43 / 100 字。
   同族的坑：`_num_faces` 越界时 Pillow 只说 `OSError: invalid argument`。
9. **闸恒绿不可怕，闸反着绿才可怕。** `ui_terms.yaml` 的 evidence 是冻结字符串，
   glossary v19 改了正文而它没动，于是这道闸**反向运行了 9 天**——既漏报真问题，
   又把已改对的报成错。故有了 `measure_ui_terms.py` 这道自校准闸。

## 7. 关键裁决索引

- `docs/ops/bake-decisions.md`：G/P/S/C/L/Y/F 各族裁决，含本轮新增的
  **C8**（卡面字色逐卡实测）、**L11**（按真实墨迹居中）、**Y15**（段级对齐）、
  **Y16**（版权行不译但接受重渲）、**F1–F4**（字体定案）。
- `docs/ops/bake-progress.md`：总进度台账 + 复跑命令。
- `docs/ops/bake-sysgim-inventory.md`：sysgim 61 张的逐张情况与五族划分。
- `docs/ops/bake-misc-inventory.md`：event/music/graphic/cutin/bg 五个目录的清点与范围裁定。
- `docs/ops/bake-specs/`：plot/scene/card 的版面规格快照。

## 8. 未决的小事

- `select` 的 `s6s_110` 六条座席按钮：罗马音化后 `A` 与 `Sakura` 黏成一个词
  （`ASakura BAyano CYuichi`）。实测全角标号 `ＡSakura` 可恢复分界、与正文 15589
  「ＡAyano、ＢSakura、ＣYuichi」逐字同形、且落在已有的 17px 档内。
  现按机械结果落地，**等用户看图定夺**（对照片 `build/select_zh/_seat_ab.png`）。
- `sys_1_i`（sysgim B 族）：箭头红晕与文字晕连成一片，需先抠箭头再合成；译文已备
  在 `data/sysgim_glow_text.jsonl` 的 `deferred` 字段。
- **sysgim C 类的模型拟合明显弱于 B 族**（`--verify` 实测：回放平均偏差 27–32
  vs B 族 6–20，发光溢出 3258–4782 vs 30–1034）。症状是字间空隙被均匀填成
  `(101,68,50)`，成因是环模型的「发光只依赖到最近字芯的距离」在密排小字上偏弱。
  **不是一行代码的 bug，是模型适用范围的边界**，需单独立项；当前产物可读，已落地。
- `.gim` 回转链路**本轮不做**（用户 2026-08-08 明示），所有面做到正确的 PNG + 版面规格为止。
