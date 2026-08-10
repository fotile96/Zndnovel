# 烤字回填 —— 总进度台账

> 一页看清「哪些面做完了、哪些卡在哪、哪些等我裁」。
> 逐条裁决理由在 `bake-decisions.md`（G/P/S/C/L/Y 共 43 条），
> `sysgim/` 的逐张情况在 `bake-sysgim-inventory.md`，版面规格快照在 `bake-specs/`。
>
> **范围提醒**：`.gim` 回转链路本轮不做（用户 2026-08-08 明示），所有面做到
> **正确的 PNG + 版面规格**为止。产物落 `build/`（gitignore），由「工具 + 冻结骨架 +
> 只读原图」一条命令确定性再生。

最后更新：2026-08-10

## 一览

| 面 | 总数 | 已烤 | 暂缓/跳过 | 待做 | 工具 |
|---|---:|---:|---:|---:|---|
| `png/plot/` | 4 | **4** | — | — | `bake_plot.py` |
| `png/scene/` | 2 | **2** | — | — | `bake_scene.py` |
| `png/card/` | 197 | **196** | 1（空白模板） | — | `bake_card.py` |
| `png/select/` | 278 | **269** | 22 孤儿 + 3 异形 | — | `bake_select.py` / `bake_select_map.py` |
| `png/sysgim/` | 103 | **33** | 5 | 23 | `bake_sysgim_outline.py` / `bake_sysgim_glow.py` |
| `png/novel/` | 993 | — | — | 993 | 建议单独立项 |
| **合计（不含 novel）** | 584 | **504** | 31 | 23 | |

## `png/sysgim/` 细分（唯一在做的面）

103 张全部逐张读过。按**重建方式**分五类；类的边界是实测出来的，不是按文件名分的。

| 类 | 张数 | 已烤 | 状态 |
|---|---:|---:|---|
| A 描边字（白填充+褐描边，透明底） | 21 | 20 | ✅ 完成（`sys_22_c` 零引用孤儿不烤） |
| B 发光字（字芯+外发光，透明底） | 17 | 13 | ✅ 完成（4 张暂缓，见下） |
| C 全屏正文（发光字压在不透明底上） | 4 | 0 | 已逐张测绘，待烤 |
| D 面板内文字 | 2 | 0 | 已逐张测绘，待烤 |
| E 英文大词 + 片假名小注 | 17 | 0 | 已逐张测绘，待烤 |

清单外含日文但**刻意不动**：`sys_10_a`、`title_01_a/b`（题名 logo）、`IPL01/02`（厂牌 logo）。

## 卡住的与它们卡在哪

### 一条推广能解掉三张暂缓件 + 整个 C 类

`bake_sysgim_glow.py` 现在的前提是**字浮在透明底上**（实测判据：盒内全透明像素占比
≥5%；可做的行 18–62%，压底的行 0.0%）。栽在这条上的：

| 张 | 底 |
|---|---|
| `sys_2_b` `sys_2_c` | 暗色面板 |
| `sys_11_a` | 覆盖全画面的半透明黑带 `(0,0,0,179)` |
| C 类 4 张（`autosave`/`sys_1_a`/`sys_1_e`/`sys_1_f`） | 不透明纯色底 |

它们的字**都是发光字**，模型完全相同，差别只在基线：现在是「相对透明」，
需要的是「相对底色」。**把环模型推广一次，这 7 张一起解决**——这是下一步性价比最高的动作。

### 单独一张：`sys_1_i`

箭头的红晕与文字的晕连成一片，x41–45 是最细处但仍无零墨迹列，按盒清擦会削掉箭头右缘。
需先把箭头单独抠出再合成。译文已记在数据里。

## 等你裁的

1. **`sys_1_g` 的字号**：全族最紧的一张，3 行塞进 37px ＝ **每行 12px**。中文在这个
   尺寸上可读性存疑，可能要缩短译文或改 2 行。落地前想给你看图。
2. **A 类字形偏细**（你 2026-08-10 已提出）：等你补 Bold TTF。设施已就绪——
   `ZND_UI_FONT=…/Bold.ttf ZND_UI_FILL_GAIN=1.0` 重跑即可，两个工具通用。
   增益 2.2 是补 Regular 细笔调的补偿，**粗体上必须调回 1.0**，否则字腔被糊死。

## 本轮顺带产出的、跨面通用的东西

- **`tools/check_ui_terms.py` + `config/ui_terms.yaml`（61 条术语）**：UI／标签译文与
  已入线正文的用词一致性闸。判据不是语感，是正文实测用法（每条带命中行数与分布）。
  首跑即抓出 extra 车道 31 处不一致（`物語→物语` 15、`ゲームオーバー→Game Over` 16），
  用户 2026-08-10 裁定全改，已落地。**此后每一面的新译都该过这道闸。**
- **`tools/measure_sysgim.py`**：族归属与版面测绘，判据可复算。

## 复跑

```bash
uv run python tools/bake_plot.py && uv run python tools/bake_scene.py
uv run python tools/bake_card.py && uv run python tools/bake_select.py
uv run python tools/bake_select_map.py
uv run python tools/bake_sysgim_outline.py
uv run python tools/bake_sysgim_glow.py --verify
uv run python tools/check_ui_terms.py data/*.jsonl
```
