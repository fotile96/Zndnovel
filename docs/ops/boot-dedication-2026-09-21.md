# 开机第五卡：汉化组署名与献词（2026-09-21）

用户提出在正式盘开场、原开发商版权页之后加一张图，两段文字：

- 全称量词汉化组
- 谨以此本地化作品献给盛夏、提前合上书页的年轻生命与被留在故事里的人们

本文记录裁定、施工与验证。命令面以 `docs/ops/disc-pipeline.md` 为准；决策表见 `bake-decisions.md` Y17。

## 裁定

| 项 | 取值 | 依据 |
|---|---|---|
| 位置 | 版权页 `sys_1_a`（层 2）之后、自动存档告知 `autosave`（层 3）之前，作第五卡，工作层 4 | 用户原话「原开发商版权页后」；层 4 在 `cInitGame` 前无人使用 |
| 节奏 | 淡入 120 / `keyWait(180)` / 淡出 120 / `wait(120)`，与前四卡逐帧相同；开机多约 7 秒 | 同族一致，圆钮同样只跳停留段 |
| 版式 | 黑底；IPL01 第 114 行的蓝→白分隔线**逐像素抄用**；署名 22 px 淡紫白 (201,205,254)、左缘 x=28、墨迹底行 y=107（三者皆同 IPL01 大字）；献词 15 px 浅灰 (215,215,215)、三行、右对齐到线右端 | 用户看过三版 mock（A 带 ∀ / A 不带 / B 暖光晕段落）选 A 不带，再看两行/三行对照取三行 |
| 分行 | 谨以此本地化作品献给 ／ 盛夏、提前合上书页的年轻生命 ／ 与被留在故事里的人们 | 首行动词短语，三个受献者占下两行，盛夏不再悬在行尾 |
| 署名记号 | **只写文字，不画 ∀** | 组名是对 Anthropic 的"A"转 180° 的梗，寓意"用 AI 多做好事少吵架"；画出来即破梗（用户）|
| 外部生图 | 不需要 | 整卡是纯排版，生成模型排不准小字号中文；若日后想加极淡底纹，只让它出无字底图、文字仍由脚本叠 |
| 厂牌卡 | IPL01/IPL02 不动 | bake-decisions Y3 不变 |

## 施工

| 件 | 路径 |
|---|---|
| 烤图工具（代码即源图，无外部素材） | `tools/bake_boot_dedication.py` → `build/boot_dedication/IPL03.png` + `_zoom3x` / `_quant_3x` / `_boot_strip` |
| 进包 | `layers/manifest.toml` `[gim].new` 加 `["boot_dedication", "sysgim", "sysgim/IPL01.gim"]`，新成员 `sysgim/IPL03.gim`，按名排序落在 IPL02 之后 |
| 插入 | `layers/overlays/boot-dedication.toml`（release 层，`insert_after` 层 2 淡出那两行；`layerLoad` 放块内，整块落在 `strip-ipl` 的 delete_span 里，故 order 中排在 `strip-ipl` 之前） |
| 测试 | `tests/test_bake_boot_dedication.py`（8 条：尺寸/不透明、分隔线逐像素、署名与献词落点、墨迹外全黑、≤256 色逐字节无损、覆盖率量化仍抗锯齿、文案与"无 ∀"）；`tests/test_layers_corpus.py` 加 3 条（落点与节奏、快启动连带剥除、清单登记与 why 留痕） |
| 驾驶 | `tools/emu/drives/boot_dedication.py`（逐帧 MSE 判五卡顺序）；`release_iso.py` 静置 35→45 s 且**不再按键**（见下） |

**文字走蒙版贴色而不是直接画**：直接抗锯齿 526 色，进包要 MEDIANCUT，虽只损 MSE 0.03 却把分隔线渐变
从 91 阶并成 30 阶。改为 L 蒙版覆盖率量化到 16 级后以纯色按蒙版贴——整卡 121 色，
`quantize_for_template` 走精确色板，进包像素与烤字图逐字节相同（测试钉住）。

## 验证

**test 盘**（`build_disc.py --profile test --mode mainmenu --no-fast-boot`，2026-09-21）：

```
  1.4s  帧 004  IPL01     6.7s  帧 020  IPL02    15.4s  帧 046  sys_1_a
 23.0s  帧 069  IPL03    31.0s  帧 093  autosave
判定: {'order_ok': True, 'ipl03_held': True, 'hits': {'IPL01': 14, 'IPL02': 17, 'sys_1_a': 12, 'IPL03': 13, 'autosave': 12}, 'frames': 107, 'errors': 0}
```

满亮帧对烤字图的 MSE 底线：IPL01 5 / IPL02 4 / sys_1_a 3 / IPL03 15 / autosave 9。IPL03 偏高不是渲染问题：
引擎把 `layerAlpha 100` 画成约 0.937 亮度（IPL01 的分隔线在模拟器里同为 (81,91,238) 对 (87,98,254)），
本卡亮像素比其他卡多，同一比例的衰减折成更大的均方差。图：`figures/boot-dedication-2026-09-21/`
（`IPL03.png` 烤字图、`emu-frame-IPL03.png` 模拟器满亮帧、`boot-strip.png` 五卡并排）。

**发布盘**（`build_disc.py --profile release` 四道断言全过 → `build/dist/game_zh.iso`，再以
`boot_dedication.py --disc build/dist/game_zh.iso` 驱动，2026-09-21）：

```
  1.7s  帧 005  IPL01     6.7s  帧 020  IPL02    15.3s  帧 046  sys_1_a
 23.3s  帧 070  IPL03    31.3s  帧 094  autosave
判定: {'order_ok': True, 'ipl03_held': True, 'hits': {'IPL01': 14, 'IPL02': 17, 'sys_1_a': 12, 'IPL03': 12, 'autosave': 12}, 'frames': 107, 'errors': 0}
```

**`release_iso.py` 顺手修正**：它原先在静置后按三次 CIRCLE 再截 01/02 帧、期望 02 帧是三项菜单。五卡后
静置改 45 s，此时菜单早已就位（无输入探针实测：自动存档卡到约 30 s，Now Loading 31–32 s，白闪 33 s，
35 s 起三项常驻、约每 10 s 一帧白闪盖住菜单项），CIRCLE 直接选中 Prologue 开了序章，01/02 帧成了序章旁白。
改为全程不按键、45/50/55 s 各截一帧标题，至少两帧应见三项。开场顺序本身由 `boot_dedication.py` 验。

实机尚未开机目检（PPSSPP 软渲染直读 VRAM 与实机像素等价，但 15 px 灰字在实屏上的观感、
以及献词字号 14/15 的取舍留给实机再定——都是 `tools/bake_boot_dedication.py` 顶部一个常量）。
