# 烤字回填 —— 总进度台账

> 一页看清「哪些面做完了、哪些卡在哪、哪些等我裁」。
> 逐条裁决理由在 `bake-decisions.md`（G/P/S/C/L/Y 共 43 条），
> `sysgim/` 的逐张情况在 `bake-sysgim-inventory.md`，版面规格快照在 `bake-specs/`。
>
> **范围提醒**：`.gim` 回转链路本轮不做（用户 2026-08-08 明示），所有面做到
> **正确的 PNG + 版面规格**为止。产物落 `build/`（gitignore），由「工具 + 冻结骨架 +
> 只读原图」一条命令确定性再生。

最后更新：2026-08-28

## 一览

| 面 | 总数 | 已烤 | 暂缓/跳过 | 待做 | 工具 |
|---|---:|---:|---:|---:|---|
| `png/plot/` | 4 | **4** | — | — | `bake_plot.py` |
| `png/scene/` | 2 | **2** | — | — | `bake_scene.py` |
| `png/card/` | 197 | **196** | 1（空白模板） | — | `bake_card.py` |
| `png/select/` | 278 | **134 按钮 + 地图** | 22 孤儿 + 3 异形 | — | `bake_select.py` / `bake_select_map.py` |
| `png/sysgim/` | 61（处理面） | **59** | 2 | — | `bake_sysgim_outline.py` / `bake_sysgim_glow.py` / `bake_panel.py` / `bake_sysgim_title.py` / `bake_sysgim_note.py` |
| `png/novel/` | 993 | — | — | 993 | 建议单独立项 |

### ✅ 那五个「从未清点过」的目录已清点（2026-08-28，详见 `bake-misc-inventory.md`）

缺口是用户点出来的：先发现 `event/op_*` 6 张与三张模式画面含字，顺线把五个目录
全扫了一遍，**又翻出 60 余张**。

| 目录 | 总数 | 含字 | 要做 | 不做（用户裁定） |
|---|---:|---:|---:|---|
| `event/` | 121 | **6**（`op_*` 序章题词） | 6 | — |
| `music/` | 4 | **4** | 1（框） | 3（BGM 曲目表不译） |
| `graphic/` | 18 | **6** | 4 | 2 |
| `cutin/` | 73 | **≥45** | **40** | `cut_nv_*` 5 + `cut_N` 28 |
| `bg/` | 81 | **0** | — | 目录闭合 |
| 合计 | 297 | ≈61 | **51** | |

**要做的 51 张，比 sysgim 剩下的 19 张多两倍半。**（这句写于 2026-08-28；到
**2026-08-30 这 51 张只剩 `cutin/tut_*` 16 张**，sysgim 那 19 张也已清零。）其中：

- `cutin/cut_e_*` 10 + `cut_s_*` 14 ＝ 章节起止字幕卡。**`cut_s_*` 带片假名人名**
  （アヤノ／ユウイチ／サクラ／ユカリ），是 glossary v19 C1 罗马音化的对象——
  与 select 按钮同一笔挂账，只是当时没人知道有这 14 张。
- `cutin/tut_*` 16 ＝ 教程说明图，**本批文本量最大、版面最复杂**（段落正文压在
  游戏截图上，背景重建难度高于 sysgim C 类）。
- `event/op_*` 6 张实为 **3 段文本**——`_b` 是 `_a` 的虚化版（实测高斯 r=1.5，
  alpha 平均残差 0.4），机器可推导，不必单独译。且这是**叙事文本**（序章题词式独白），
  该按正文轨的口吻处理，不是按标签处理。

⚠ **方法教训**：台账里写「少量」「个别」的那几格，等于**从没被清点过**。
数字才是清点，形容词不是。另有 CLAUDE.md 的一处记错顺带查实——「`bg/` 少量含字
（黑板板书等）」的黑板板书在 `cutin/cut_54`，`bg/` 81 张一张烤字也没有。

## 2026-08-28：与正文轨重新对齐（v19/v20）

8-19 的 `skeleton-v2`（glossary v19 C1）把故事层片假名人名整体改成罗马音，
`skeleton/cards.zh.yaml` 的 **62 条 title_zh + 120 条 body_zh（合计 139/196 张卡）**
随之变化。烤字产物是 8-08~8-10 生成的，**四个面的 PNG 因此全部过期**并已重烤：

| 面 | 受影响 | 结果 |
|---|---|---|
| `card/` | 139/196 张文本变化 | 已重烤，validation gate max_diff 52 / 阈值 60，0 超阈 |
| `plot/` | 62 条卡名（同源 `cards.zh.yaml`） | 已重烤，0 溢出；卡 162 仍是唯一墨迹回退格 |
| `scene/` | 同上 | 已重烤，**回落从 4 条变 3 条**（见 bake-decisions S5 的追记） |
| `select/` | 9 个按钮（8 罗马音化 + 1 天象馆） | 已重烤，**回落从 20 条变 14 条**（见 L5 追记） |
| `sysgim/` | 输入 jsonl 未动 | 不受影响，重跑结果一致 |

glossary v19 的召回令原文：「图片轨（select 按钮、卡面烤字、plot/scene 缩略）**登记不
实施**，随烤字工程处理」——本次即是兑现这笔挂账。

### 顺带查出并修掉的两处

1. **UI 术语闸反向运行了 9 天。** `config/ui_terms.yaml` 里 `ユウイチ → ユウイチ`
   那三条是 v19 之前的规则，而 evidence 是**冻结字符串**，正文改了它不会自己动。
   后果是双向的：select/ 那 8 条真该改的一条没报，extra 车道 11 条**已经改对**的
   反被报成 mismatch。已按现行译文（forward + patches）全表重算，并补上漏登的
   `ユカリ→Yukari`（同族三条都在，唯独缺它）、给 `作成` 加 `exempt_jp: [物語]`
   （占比跌破门槛不是用词混乱，是「あらすじ→制作／物語→创作」的语义分层）。
   **新增 `tools/measure_ui_terms.py`**：拿现行译文重算每条占比并报漂移，
   把「静默反转」变成「跑一下就红」。此后 glossary 每次升版都该跑它。
2. **`sel_s2s_193c_sel_b`「元にした物がニセ物」→「原作本身是假货」。** 这是骨架
   卡 41 的 `tr_note` 里白纸黑字挂了很久的图片轨待办：正文 v8 定 `贋作→赝品`（7/7）、
   `ニセモノ/ニセ物→假货`；旧译「赝品」与正文轨反向。

## `png/sysgim/` 细分（**全部完工**，2026-08-30；`sys_1_i` 已于同日解烤）

103 张全部逐张读过。按**重建方式**分五类；类的边界是实测出来的，不是按文件名分的。

| 类 | 张数 | 已烤 | 状态 |
|---|---:|---:|---|
| A 描边字（白填充+褐描边，透明底） | 21 | 20 | ✅ 完成（`sys_22_c` 零引用孤儿不烤） |
| B 发光字（字芯+外发光） | 17 | 17 | ✅ 完成（`sys_1_i` 由 geo 两步法解烤，见下） |
| C 全屏正文（发光字压在不透明底上） | 4 | 4 | ✅ 完成 |
| D 面板内文字 | 2 | 2 | ✅ 完成（`bake_panel.py`，裁决 M 族） |
| E 英文大词 + 片假名小注 | 17 | 17 | ✅ 完成。`title_02..13_a` 12 张走**两步遮盖**（`bake_sysgim_title.py`，裁决 E1–E7）；`sys_2_a`/`sys_3_a`/`sys_12_a/b/c` 5 张走**几何足迹 + 幽灵晕剥离**（`bake_sysgim_note.py`，裁决 E8–E19）。⚠ 这 5 张原记的模型归属是错的（不是 A 族描边、`sys_12_b` 的底是照片），更正见 inventory |

清单外含日文但**刻意不动**：`sys_10_a`、`title_01_a/b`（题名 logo）、`IPL01/02`（厂牌 logo）。

## 卡住的与它们卡在哪

### ✅ 已解：环模型推广为「相对底色」（`3436387`，2026-08-10）

发光工具原先的前提是「字浮在透明底上」，`sys_2_b/c`（暗面板）、`sys_11_a`（半透明黑带）
因此被挡在外面，C 类（不透明纯色底）更无从谈起。实测表明那道限制是多余的——这些盒的底
都只有一个取值，把环从「相对透明」改成「相对底色」，同一个模型就成立。
**发光族 13→16 张，暂缓 4→1。C 类的路随之打通，是现在最顺手的一块。**

（这一步做完时台账没跟着改，于是 8-10~8-28 之间台账一直少记 3 张。教训与
`ui_terms.yaml` 那条同源：**状态写在两个地方，就一定会有一个是旧的**。）

### 单独一张：`sys_1_i`（✅ 已解烤，2026-08-30）

原暂缓原因「红晕与文字晕连成一片，无干净切口」在 geo 两步法下不复存在：
按到箭头的距离分层（白测像素 d=7–12 为零），箭头作硬保护组（r=6），文字擦除区
与红晕重叠的左缘条带由拉普斯拉重建（`photo`）。另修正两处数据事故：三个盒的
左缘都切掉了真墨迹（行1 从 x=35 起，旧盒 52）；行1 是暗棕墨（174,69,0 族），
`drop_extra=brown` 让字芯判据认得它。详见 `bake-decisions.md` E20、
`data/sysgim_note_text.jsonl`。

## 等你裁的

1. **`sys_1_g` 的字号**：全族最紧的一张，3 行塞进 37px ＝ **每行 12px**。中文在这个
   尺寸上可读性存疑，可能要缩短译文或改 2 行。落地前想给你看图。
2. **A 类字形偏细**（你 2026-08-10 已提出）：等你补 Bold TTF。设施已就绪——
   `ZND_UI_FONT=…/Bold.ttf ZND_UI_FILL_GAIN=1.0` 重跑即可，两个工具通用。
   增益 2.2 是补 Regular 细笔调的补偿，**粗体上必须调回 1.0**，否则字腔被糊死。

## 等你看图再定的（新增，2026-08-28）

3. **`s6s_110` 六条座席按钮的标号与名之间要不要隔开。** 罗马音化后成了
   `ASakura BAyano CYuichi`——原文 `Aサクラ` 靠「拉丁 vs 片假名」天然有分界，
   现在两边都是拉丁，`A` 和 `Sakura` 黏成一个词。glossary v19 对这一处的原话是
   「全角标号并置暂按机械结果，**游戏内实测后再定间隔**」，现已有实测：

   | 写法 | 18px | 17px | 16px | 备注 |
   |---|---|---|---|---|
   | `ASakura BAyano CYuichi`（现状，机械） | ✓ | ✓ | ✓ | 无分界 |
   | `ＡSakura ＢAyano ＣYuichi`（全角标号） | ✗ | **✓** | ✓ | 与正文 15589「ＡAyano、ＢSakura、ＣYuichi」逐字同形 |
   | `A.Sakura B.Ayano C.Yuichi`（点分隔） | ✗ | ✗ | **✓** | 需给 `bake_select` 开第三档 |
   | `A Sakura` / `A:Sakura` | ✗ | ✗ | ✓ | 同上 |

   **对照片：`build/select_zh/_seat_ab.png`**（`tools/bake_select_seat_ab.py` 生成，
   六条按钮 × 原图／现状 18px／点分隔 16px／全角标号 17px，4 倍放大）。

   看图后的观察，供参考不作结论：
   - **点分隔 16px 的分界最清楚**，`A.Sakura` 一眼就是「标号 + 名」，代价是字号掉两档、
     比原图明显小一圈，且现行级联 `[18,17]` 放不下它，要开第三档。
   - **全角标号 17px 的间隔反而有点尴尬**：`Ａ` 后面留的空当与词组之间的空当宽度接近，
     远看会读成「Ａ　Sakura　Ｂ　Ayano」四段而非三组——分界是有了，分组反而糊了。
   - 三版都比原图那行**细一档**，这是字体本身的问题，不是这几种写法的问题（见下节）。

   现状是机械结果、与冻结的 glossary 一致，故先按现状落地，等你定夺。

## 卡面字色修正（2026-08-28，裁决 C8）

用户指出原图卡面的字**不是纯黑**，而带着与卡片外框同色的晕。实测确认并已修：

- 全库 195 张字芯稳定在 `(56–60, 0, 0–1)` 暗红，与外框 `(18,0,1,243)` 同色系；
  卡 94 的框是褐 `(34,19,8,243)`，字芯相应是 `(80,47,17)`。方向 cos = 0.95–0.999，
  **零离群**。旧实现写死 `(12,11,10)` 近乎中性黑。
- 那圈「晕」量下来只有约 2px（α: 0.95 / 0.36 / 0.03 / 0），**就是"有颜色的字"的
  抗锯齿边**，不需要另加距离场——把字色改对，边缘自然就对。
- 改为**逐卡实测**（`measure_ink_color`，与 C4 背景重建同样的自参照做法），
  取值与回退情况全部进 `manifest.json` 的 `ink_color`。

**字芯色距（越小越像原图）**：旧固定色 69.2 → 逐卡实测 42.3 → **换思源黑体后 0.0**。
最后这一跳说明「字色取对」与「取对了能落到像素上」是两件事：霞鹜文楷在 9–11px 下
笔画细到没有一个像素达到满覆盖，纯字色根本不会出现在产物里。

逐张放大对照：`build/font_ab/_ink_zoom.png`。两条方法教训（均值误读、双峰是门槛的
边界效应）与那道守不到字色的闸缺口，记在 `bake-decisions.md` 的 C8。

## ✅ 字体已定（2026-08-28）：card/plot/scene/select = 思源黑体 SC Medium

用户看过四路对照后裁定，落在 **`config/bake_fonts.yaml`**——该文件是「最后用了哪套
字」的持久记录，环境变量只作临时试验用。裁决理由见 `bake-decisions.md` 的 F1–F4。

**`sysgim` 未定**，配置里保留了**逐张覆盖**位（用户明示「可能需要分别指定最后使用
的字体」）。写法：

```yaml
faces:
  sysgim:
    font: third_party/LXGWWenKai-Regular.ttf     # 面默认
    sheets:
      sys_20_c: {font: third_party/SourceHanSansSC-VF.ttf, weight: Bold}
```

键＝不带扩展名的文件名，与 `data/sysgim_*_text.jsonl` 的 `file` 字段一致。
⚠ 换成笔画更实的字体时 `ZND_UI_FILL_GAIN` 要从 2.2 调回 1.0（Y6/Y14）。

### ✅ cutin 已定（2026-08-28）：华文仿宋 STFangsong（F5–F7）

用户指霞鹜文楷「衬线的感觉不明显」，八路对照（`build/font_ab/cutin.png`）后裁定。
**这一面不能在别的机器上复现**——华文仿宋是 Apple 随系统分发的商业字体，不能入库，
是裁决 G1 的明示例外（F6）。路径带哈希、系统更新后可能变，重新定位：

```bash
ls /System/Library/AssetsV2/com_apple_MobileAsset_Font7/*/AssetData/STFANGSO.ttf
```

`event/op_*` 仍是霞鹜文楷（叙事文本，未定）。填充增益维持 2.2：仿宋与霞鹜文楷同属
细笔画，不触 Y6/Y14。

⚠ **同轮推翻的一条**：上一轮记的「候选九款全部零缺字」是错的。按真实待烤文本
（370 字）逐字与 `.notdef` 位图比对：儷宋缺 43 字、蘋果儷細宋缺 100 字（都是繁体
字库），`章节` 的「节」就在其中，对照图上是豆腐块——两款出局。其余五款只缺 `・`，
它仅出现在 sysgim 的 `sys_21_a`。**PIL 渲染缺字时静默画豆腐块，不抛异常、不返回空
墨迹**，所以「渲染没报错」不能当缺字判据。详见 `bake-decisions.md` F5–F7。

### ✅ cutin 两个旋钮已定（2026-08-29）：`slant: 0.10` + `size_bias: 1`（F8–F10）

用户看过五档倾斜 × 字号 ±1 的对照后裁定。两个都是**主动偏离原图**的风格选择，
不是复现——**原图实测并未被切变**（残差中位 +0.008，n=23，详见 `bake-decisions.md`
的更正节）。实测代价：字号降档 0 张、宽度退回 0 条、纵向余量 5px→4px 未越界。

```bash
# 试别的档（环境变量压过配置）
ZND_UI_SLANT_CUTIN=0.15 ZND_UI_SIZE_BIAS_CUTIN=2 ZND_BUILD_TAG=t \
    uv run python tools/bake_cutin_title.py
uv run python tools/bake_font_ab.py --faces cutin --tag t
```

⚠ **`size_bias` 打破了一个原本成立的不变量**：`choose_size` 保证 `核高 ≤ 原行墨迹高`，
而 `bake_file` 的纵向落位 `gy = top + (own_h − core_h)//2` 正是靠它才不越出盒
（横向有夹取，**纵向没有任何检查**）。当前 +1 到 +6 实测都没越界（最坏余量 4px），
但这是个真实空档——若日后把加成开大，或用到盒更紧的面，先补纵向闸。

### 字体集合（.ttc）怎么指

`tools/ui_font.py` 认 `路径#N`，环境变量与配置文件同一套解析：

```bash
ZND_UI_FONT_CUTIN=/System/Library/Fonts/Supplemental/Songti.ttc#6 \
    ZND_BUILD_TAG=songtiR uv run python tools/bake_cutin_title.py
```

**集合不写索引会报错**（F7）：`Songti.ttc` 8 款里第 0 款是 Songti SC **Black**，
静默取 0 与「变量字体默认实例是 ExtraLight」（F3）是同一种错。索引越界也自己判——
Pillow 只会抛 `OSError: invalid argument`，看不出是索引的事。已知索引：
`#3` Songti SC Light、`#4` STSong、`#6` Songti SC Regular；`SimSong.ttc` 只有 `#0/#1`。

### 同时修掉的两处判据缺陷（都是换字体才照出来的）

1. **`select` 的居中**（裁决 L11）：`anchor="mm"` 按字体**设计度量**居中，把思源系
   整体压低 3px，134 个按钮里 118 个"越界"——越的是定位的界，不是字的界。
   改按**真实墨迹**居中后：霞鹜 14→3、Regular 118→1、Medium 116→2，级联 `[18,17]`
   原样够用；`sel_map` 1→0。L6 反而对得更准（墨迹中心偏移 −0.50→0.00，σ 减半）。
2. **`scene` 的切顶判据**：`y1 >= box[3]` 拿排他上界比排他边界，差一像素。换 Medium
   后 165 张报警，而逐格实证真被切的是 **0 张**。已修，并把「贴边未越界」单列
   `vertical_zero_margin`。

### 现在的实测状态（默认配置）

| 面 | 字号回落 | 溢出 | 盒外像素改动 |
|---|---|---|---|
| `select` | 2 / 134 | 0 | 0 |
| `sel_map` | 0 / 10 | 0 | 0 |
| `scene` | 3 / 195（11px×192） | 0 | 0 |
| `card` | — | 0（闸 52/60） | 0 |
| `plot` | — | 0 | 0 |

## 换字体（2026-08-28 起可做）

字体不再写死。优先级 `ZND_UI_FONT_<面>` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷
Regular，五个面 `PLOT` / `SCENE` / `CARD` / `SELECT` / `SYSGIM` 各自可指。
解析器在 `tools/ui_font.py`。

```bash
# 全库换一套试
ZND_UI_FONT=/path/to/Other.ttf uv run python tools/bake_card.py

# 只给 card 换，其余照旧
ZND_UI_FONT_CARD=/path/to/Other.ttf uv run python tools/bake_card.py
```

- 路径打错**当场炸**，不会悄悄回落到默认字体——悄悄回落时你以为在评估新字体，
  看到的却仍是霞鹜文楷，而两次输出的差别恰好是零，最像「这字体没救了」的那种零。
- **换字体后金标夹具会红，这是对的**：墨迹尺寸、字号回落集、溢出判定全是对着默认
  字体实测出来的。换字评估看图与看 `manifest.json`，不看测试绿不绿。
- 换 Bold 时 sysgim 两个工具的 `ZND_UI_FILL_GAIN` 要一并调回 1.0（裁决 Y6/Y14）。

**为什么值得按面分开选。** 各面的字号档位差得很远——`select/` 18/17px 带描边、
`sysgim/` 12–17px 带描边或发光、`scene/` 11/10/9px、`card/` 正文 9px 且最紧的行只余
2px。同一套字在 18px 和 9px 上不是一回事：霞鹜文楷 Regular 在 15px 以下笔干到不了
一个像素，整行发灰（sysgim 为此加了 2.2 的填充增益补偿）。`scene_zh/_cellzoom.png`
里中文条比原文日文明显更细更灰，就是这个成因在另一个面上的同一副面孔。

另有一条 v19 之后才显形的：**霞鹜文楷的拉丁字形偏手写、偏轻、偏宽**，与它自己的
汉字不是一种气质。以前拉丁字符罕见，这条无关紧要；罗马音化之后每张卡面、每个按钮、
每条 scene 标题都躲不开（`card_zh/_cellzoom.png` 里 `Sakura的日记` 一眼可见）。

## 思源黑体 SC 试烤（2026-08-28）

`third_party/SourceHanSansSC-VF.ttf`（用户提供）全五面已烤一版，产物在
`build/<面>__shs/`；对照图 `build/font_ab/{card,select,scene,plot,sysgim}.png`
与数字差异 `build/font_ab/summary.md`（`tools/bake_font_ab.py` 生成）。

复现：

```bash
export ZND_UI_FONT="$PWD/third_party/SourceHanSansSC-VF.ttf" ZND_BUILD_TAG=shs
uv run python tools/bake_plot.py && uv run python tools/bake_scene.py
uv run python tools/bake_card.py
ZND_UI_SIZE_CASCADE_SELECT=18,17,16,15,14 uv run python tools/bake_select.py
ZND_UI_SIZE_CASCADE_SELECT=18,17,16,15,14 uv run python tools/bake_select_map.py
ZND_UI_FILL_GAIN=1.0 uv run python tools/bake_sysgim_outline.py
ZND_UI_FILL_GAIN=1.0 uv run python tools/bake_sysgim_glow.py
uv run python tools/bake_font_ab.py --tag shs
```

### 三个必须先知道的坑

1. **变量字体的默认实例是 ExtraLight(250)，不是 Regular。** 那是权重轴的最小值。
   裸调 `ImageFont.truetype()` 会拿到它，于是两千多张图会在发丝级字重下烤出来——
   与换字动机恰好相反，而且**看起来是正常的**（不报错、不缺字，只是更灰一点）。
   `tools/ui_font.py` 因此把变量字体默认钉在 `Regular`，另可用
   `ZND_UI_FONT_WEIGHT[_<面>]` 指定（18px 实测纯白核：ExtraLight 4.9% →
   Regular 24.7% → Medium 36.1% → Bold 47.0%）。
2. **sysgim 的 `ZND_UI_FILL_GAIN` 要调回 1.0。** 2.2 是补霞鹜文楷细笔调的，
   思源黑体笔画本就实，再叠增益会糊字腔（裁决 Y6/Y14 早已写明）。
3. **`select/` 的字号级联撑不住，要加档。** 默认 `[18,17]` 下 134 个按钮里 **118 个**
   撞文字框——但**原因不是字体太大，是居中方式**，见下。

### `select/` 那 118 个越界：是定位，不是字体

`render_text_layer` 用 `anchor="mm"`，即按**字体的设计度量**（ascender/descender）
居中。思源黑体的设计度量比霞鹜文楷大得多，墨迹因此被整体压低。实测（文字框
`(15,3,235,23)`，高 20px）：

| 字号 | 文本 | 墨迹自身高 | mm 锚定实测 y | 判定 |
|---:|---|---:|---|---|
| 17px | `AAyano BSakura CYuichi` | **20px** | y[6,26] | 墨迹装得下，定位越界 3px |
| 16px | 同上 | 19px | y[6,25] | 同上 |
| 14px | 同上 | 16px | y[7,23] | 碰巧落进框里 |

**17px 的墨迹正好等于框高，本来装得下。** 按墨迹居中即可，一路降到 14px 完全是
定位方式的代价。本轮**没有改**——`anchor="mm"` 的居中是裁决 L6 对着原图验过的，
改了会连带移动已入线的霞鹜文楷版全部 268 张按钮，不该顺手做。故 SHS 版的 select
按现行管线落在 14–16px，对照图里它比霞鹜文楷版小一圈，**那一圈是管线欠的，不是字体欠的**。

### 看图结论（我的观察，供你复核）

- **`scene/` 差别最大。** 9–11px 下霞鹜文楷灰而糊，思源黑体是实白的，接近原图。
  9px 回落的卡 180/182 尤其明显——那两张在霞鹜文楷下已接近不可读。
- **`card/` 正文 9px 同向**，思源黑体更实、气质也更贴原图的日文黑体。
- **`select/` 即便字号小两三档，思源黑体仍比霞鹜文楷更清楚**——这条最能说明问题：
  「更小但更清楚」意味着现在的可读性瓶颈是**笔画密度**而不是字号。
- **拉丁字形**：思源黑体的拉丁与其汉字同族同气质；霞鹜文楷的拉丁偏手写、偏轻、偏宽，
  与汉字并置时明显是两套东西（`章节 5：Sakura` 一眼可见）。v19 罗马音化之后
  这条的权重很大。
- 反面：思源黑体是**黑体**，霞鹜文楷是**楷体**。原作日文用的是黑体系，故思源在
  「像原作」这一维上占优；但如果中文版想要更柔的调子，那是另一种取舍，不是本对照能回答的。

### 又一版：Medium 字重（`shsm`，2026-08-28）

`ZND_UI_FONT_WEIGHT=Medium ZND_BUILD_TAG=shsm`，五面全烤，产物 `build/<面>__shsm/`。
对照图现在是四路并排（原图 / 霞鹜文楷 / shs Regular / shsm Medium）：

```bash
uv run python tools/bake_font_ab.py --tag shs shsm
```

**Medium 没有付出档位代价，反而略省。** select 的字号分布：

| 版本 | 18px | 17px | 16px | 14px | 回落数 |
|---|---:|---:|---:|---:|---:|
| 霞鹜文楷 | 120 | 14 | — | — | 14 |
| shs Regular | 16 | — | 111 | 7 | 118 |
| shsm Medium | **18** | — | 109 | 7 | **116** |

（Regular 与 Medium 的档位差异只有 2 格，都受上面那条 `anchor="mm"` 的定位问题拖累；
`scene` 三版档位分布完全相同：11px×192 / 10px×1 / 9px×2。）

**「加重会不会糊死字腔」是量过的，不是看过的。** 卡面正文 9px 是全库最紧的一处，
判据取「被墨迹完整围住、连不到边界的背景连通块数」（字腔糊死则该数下降），16 张
代表卡实测：

| | 霞鹜文楷 | shs Regular | shsm Medium |
|---|---:|---:|---:|
| 字腔总数 | 198 | 304 | **378** |

Medium **不降反升 24%**——这不是反常：霞鹜文楷 9px 下笔画淡到很多地方越不过墨迹
阈值，字腔直接漏到背景里，所以数得少。**字腔数低在这里等于"笔画没成形"，不等于
"字腔通透"。** 16 张里只有卡 115 少了 2 个（噪声量级）。故 Medium 在 9px 上仍有余量。

**看图**：三个面上 Medium 都最接近原图的字重（原作日文本就是较重的黑体）。
`select/` 的 `Yukari老师`、`想不起约定` 在 Medium 下比 Regular 明显更立得住；
`scene/` 11px 同向；`card/` 正文 9px 更黑但字腔仍开。

**取舍**：Medium 是三者里最重的。若中文版想要比原作更柔的调子，那是另一个方向的
选择，本对照回答不了——它只能回答「哪一版最像原作、最清楚」。

### 数字差异

| 面 | 字号回落（霞鹜 / Regular / Medium） | 溢出 | 盒外像素改动 |
|---|---|---|---|
| `select` | 14 / **118** / **116** | 全 0 | 全 0 |
| `scene` | 3 / 3 / 3 | 全 0 | 全 0 |
| `card` / `plot` | — | 全 0 | 全 0 |

回落数暴涨仅因上面那条定位问题；溢出与盒外像素改动三版都是 0，**三套字都没有真缺陷**，
差的是观感与档位。

## 本轮顺带产出的、跨面通用的东西

- **`tools/check_ui_terms.py` + `config/ui_terms.yaml`（62 条术语）**：UI／标签译文与
  已入线正文的用词一致性闸。判据不是语感，是正文实测用法（每条带命中行数与分布）。
  首跑即抓出 extra 车道 31 处不一致（`物語→物语` 15、`ゲームオーバー→Game Over` 16），
  用户 2026-08-10 裁定全改，已落地。**此后每一面的新译都该过这道闸。**
- **`tools/measure_ui_terms.py`（2026-08-28 新增）**：上面那张表的**自校准闸**。
  evidence 是人手写的冻结字符串，正文一改它就悄悄作废——v19 之后它整整反向运行了
  9 天而没有任何东西变红。本工具拿现行译文（forward + patches）重算每条占比，
  漂移与「数字过期」都会红。`--write` 只刷数字、**从不改 zh**，且只要还有条目在漂移
  就拒绝执行（定译改成什么是人的裁决）。**glossary 每次升版都该跑它。**
- **`tools/measure_sysgim.py`**：族归属与版面测绘，判据可复算。

## 复跑

```bash
uv run python tools/bake_plot.py && uv run python tools/bake_scene.py
uv run python tools/bake_card.py && uv run python tools/bake_select.py
uv run python tools/bake_select_map.py
uv run python tools/bake_sysgim_outline.py
uv run python tools/bake_sysgim_glow.py --verify

# 两道闸。顺序有讲究：先校准表，再拿表去检标签——反过来是拿旧规则检新译文。
uv run python tools/measure_ui_terms.py
uv run python tools/check_ui_terms.py \
  data/card_section_labels.jsonl data/select_buttons_zh.jsonl \
  data/select_map_zh.jsonl data/select_options_zh.jsonl \
  data/sysgim_glow_text.jsonl data/sysgim_outline_text.jsonl \
  data/extra_translated.jsonl
```

⚠ 原先这里写的是 `check_ui_terms.py data/*.jsonl`，**现在会直接崩**——`data/` 后来多了
`api_ledger.jsonl`、`ledger.jsonl` 等没有 jp/zh 字段的文件，闸拒绝解析（这是对的行为）。
故此处**显式列出**七个标签文件，而不是靠通配。
