# 中文题名 logo 配色后处理（一次性研究，2026-09-12）

`sysgim/title_01_c`（谢幕读完后显示的中文题名，见 CLAUDE.md 谢幕章一节）的源图由生成式
模型出图，**配色比日文原版 `png/sysgim/title_01_a.png` 更深、更浓蓝**，直接进游戏与原版
标题画面的色调不搭。这里是把它按原版校准回去的脚本与参数。

**入库的 `docs/finale/assets/title_01_c.src.png` 已经是这套处理的成品。不要再对它跑一次
调色**——会二次处理。调色前的输入在 git `52abe46`，`snapshot_inputs.py` 从那里取。

归档理由：调色结果入库了，配方原本只在临时目录里，重启即丢；将来想微调配色就得从头
重来。归档后 `recolor_title.py` 实测能逐字节重现入库素材（见下「复跑验证」）。

## 结论

选定 **C**：`strength=1, halo_strength=1, gradient_strength=1`（三项分别是墨色/暖色迁移、
描边光晕、随高度的高光修正强度，取值 0..1）。备选 A=0.55/0.35/0、B=0.85/0.8/0.55 更保守，
用户目检后选了最贴近原版的 C。

大标题笔画指标（在 405×89 游戏尺寸上量，样本为 alpha>0.95 ∧ B−R>0.075 ∧ Oklab L<0.65）：

| | 日文参照 | 未调整中文 | C |
|---|---:|---:|---:|
| 明度中位数 L | 0.506 | 0.394 | 0.502 |
| 色彩浓度中位数 C | 0.091 | 0.136 | 0.091 |
| 色相中位数（度） | 256.0 | 258.9 | 256.3 |

做法：Oklab 明度曲线 + 色彩浓度缩放 + 色相旋转，按大标题/副标题/金线/橙色/描边光晕分区
做连续软蒙版，保留渐变；亮部超 sRGB 时固定明度与色相、二分压低浓度回到色域，不截断单通道。
Oklab 矩阵取自 <https://bottosson.github.io/posts/oklab/>（公有领域实现）。
**只改 RGB**：高清源与 405×89 产物的 alpha 都与调色前逐像素相同，字形、几何、版面未动。

分区与软蒙版是针对这两张图的工程选择，不是通用字体识别；换一张源图要重新校准。

## 文件

| 文件 | 说明 |
|---|---|
| `recolor_title.py` | 调色主脚本。`--strength/--halo-strength/--gradient-strength/--label/--out` |
| `probe.py` | 色彩空间与统计辅助；`ROOT/REPO/IN` 路径也在这里 |
| `validate.py` | 校验：alpha 恒等、透明像素 RGB 不变、色域、Oklab 往返、GIM 编码后解码一致、零强度恒等 |
| `snapshot_inputs.py` | 填 `inputs/`（4 张输入，逐张核对 sha256） |
| `calibration.json` | C 的校准参数 |
| `measurements.json` | 日文参照/未调整/C 的分区指标 |
| `validation.json` | `validate.py` 当时的输出 |
| `requirements.txt` | 临时 venv 的精确依赖 |

`inputs/`、`venv/`、`round*/` 由 `.gitignore` 忽略——都能重建。

## 复跑

依赖 numpy + scipy，**不在仓库的 uv 依赖里**（为一次性研究给主项目加 scipy 不值当），
用一次性 venv：

```sh
cd tools/research/title_recolor
uv venv venv && venv/bin/python -m pip install -r requirements.txt
uv run python snapshot_inputs.py                    # 填 inputs/（从 git 取调色前的输入）
PYTHONDONTWRITEBYTECODE=1 venv/bin/python recolor_title.py \
    --strength 1 --halo-strength 1 --gradient-strength 1 --label C --out /tmp/title-recolor-out
```

输出**必须在仓库外**（脚本自带 guard，指向仓库内会直接报错）——QA 图和候选图不该进仓库。
不带 `--strength` 则一次出 A/B/C 三个候选与对照图，供重新挑选。

改完配色后要把新成品接回正式流程：成品覆盖 `docs/finale/assets/title_01_c.{src,}png`，
再 `cp` 一份 405×89 到 `build/finale_title/title_01_c.png`，然后按 `docs/ops/disc-pipeline.md`
出盘；`tools/bake_finale_title.py` 的 `fit_logo()` 是降采样那一步，调色脚本内部也调它。

## 复跑验证（2026-09-12）

用本目录这份归档代码、C 参数重跑，产物与入库素材**逐字节相同**：

- `C_source.png` → `2825feee…03af2` = `docs/finale/assets/title_01_c.src.png`
- `C_405x89.png` → `0cd1eab4…6a1e14` = `docs/finale/assets/title_01_c.png`

## 归档时做的唯一代码改动

`probe.py` 里 `REPO` 原本硬编码作者本机绝对路径，改为按脚本位置推导
（`parents[3]`，`SNDL_REPO` 可覆盖）。其余脚本逐字节照搬。

`probe.py` 的 `paths` 表记的是输入原本来自仓库哪个文件，但其中
`chinese_source/baked` **不能**照它从工作区取（现在是调色成品），必须走
`snapshot_inputs.py`；表旁已加警告注释。

## 模拟器预览的边界

当时为快速看配色，另有一份临时预览盘把日文/中文两个题名槽都换成候选图，那份盘
**不能**当正式产物（日文初始标题会被替换）。正式盘由 `build_disc.py` 出，已核对
发布 `DATA.BIN` 里 `title_01_a`/`title_01_b` 与原包逐字节一致、只新增 `title_01_c`。
