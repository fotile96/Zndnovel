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
| `png/sysgim/` | 61（处理面） | **36** | 2 | 23 | `bake_sysgim_outline.py` / `bake_sysgim_glow.py` |
| `png/novel/` | 993 | — | — | 993 | 建议单独立项 |

台账外**从未清点过**的面：`bg/` 81、`event/` 121、`cutin/` 73、`graphic/` 18、`music/` 4。
CLAUDE.md 说这几处「少量/个别含字」，但**具体是哪几张没有任何记录**——这是清点缺口，
不是工作量缺口，代价是一次逐张过眼。

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

## `png/sysgim/` 细分（唯一在做的面）

103 张全部逐张读过。按**重建方式**分五类；类的边界是实测出来的，不是按文件名分的。

| 类 | 张数 | 已烤 | 状态 |
|---|---:|---:|---|
| A 描边字（白填充+褐描边，透明底） | 21 | 20 | ✅ 完成（`sys_22_c` 零引用孤儿不烤） |
| B 发光字（字芯+外发光） | 17 | 16 | ✅ 完成（`sys_1_i` 1 张暂缓，见下） |
| C 全屏正文（发光字压在不透明底上） | 4 | 0 | 已测绘，**模型已通**，可直接烤 |
| D 面板内文字 | 2 | 0 | 已测绘，待烤（`sys_1_g` 等裁） |
| E 英文大词 + 片假名小注 | 17 | 0 | **唯一尚未测绘的一类** |

清单外含日文但**刻意不动**：`sys_10_a`、`title_01_a/b`（题名 logo）、`IPL01/02`（厂牌 logo）。

## 卡住的与它们卡在哪

### ✅ 已解：环模型推广为「相对底色」（`3436387`，2026-08-10）

发光工具原先的前提是「字浮在透明底上」，`sys_2_b/c`（暗面板）、`sys_11_a`（半透明黑带）
因此被挡在外面，C 类（不透明纯色底）更无从谈起。实测表明那道限制是多余的——这些盒的底
都只有一个取值，把环从「相对透明」改成「相对底色」，同一个模型就成立。
**发光族 13→16 张，暂缓 4→1。C 类的路随之打通，是现在最顺手的一块。**

（这一步做完时台账没跟着改，于是 8-10~8-28 之间台账一直少记 3 张。教训与
`ui_terms.yaml` 那条同源：**状态写在两个地方，就一定会有一个是旧的**。）

### 单独一张：`sys_1_i`

箭头的红晕与文字的晕连成一片，x41–45 是最细处但仍无零墨迹列，按盒清擦会削掉箭头右缘。
需先把箭头单独抠出再合成。译文已记在数据里。

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

   | 写法 | 18px | 17px | 备注 |
   |---|---|---|---|
   | `ASakura BAyano CYuichi`（现状，机械） | ✓ | ✓ | 无分界 |
   | `ＡSakura ＢAyano ＣYuichi`（全角标号） | ✗ | **✓** | 与正文 15589「ＡAyano、ＢSakura、ＣYuichi」逐字同形 |
   | `A Sakura` / `A:Sakura` / `A.Sakura` | ✗ | ✗ | 需新开 16px 档 |

   全角标号既恢复分界、又与正文先例一致、且落在**已有的** 17px 回落档内，不必新开档位。
   现状是机械结果、与冻结的 glossary 一致，故先按现状落地，等你看图定夺。
   放大样在 `build/select_zh/_cellzoom.png`。

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
