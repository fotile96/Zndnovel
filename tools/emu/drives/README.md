# tools/emu/drives — 模拟器驾驶脚本

对 `build_disc.py` 产出的盘做固定按键序列 + 逐帧截图的人读验证。全部走软渲染、
直读 VRAM，可复现。每个脚本 `--disc` 指定引导对象、`--out` 指定截图目录
（缺省 `build/emu/drives/<脚本名>/`，每次先清空）。跑完打印 ERROR 日志条数。

**先建盘，再驾驶。** 多数脚本要的是 **test 剖面**的盘（探针/全解锁/直入场景），
只有 `release_iso.py` 引导发布 ISO 本体。剖面产物互相隔离，见 `docs/ops/disc-pipeline.md`。

| 脚本 | 验什么 | 前置构建 | 期望 |
|---|---|---|---|
| `menu.py` | 12 项菜单版面、encore 亮暗态、CIRCLE 进谢幕章 | `--profile test --mode mainmenu` | 00 帧 12 项；03 帧 encore 亮；04 帧已进 fin-10 |
| `library.py` | library 子列展开/收合四项齐全（`#layerKeyCur` 修正） | 同上 | 01 帧四子项；02 帧收合 |
| `no_card144.py` | 无卡 144 时回到原版 11 项形态 | 同上，但需在 `build/test/lua/final/snr_test.lua` 全卡循环后补 `gameSave.myCard[144].hold = -1`，再跑 `--profile test --stage members,stage,pack,disc`（跳过 lua，否则被重新生成覆盖） | 00 帧 11 项；下 4 次到 option |
| `finale_full.py` | 谢幕全章 fin-10..50 跑通回主菜单（约 15 分钟） | `--profile test --mode mainmenu` | p010..p350 每 10 句一帧；end* 回主菜单 |
| `glyph.py` | 直入场景逐句截图；缺省验 fin-10 的 7 个曾缺字 | `--profile test --mode scene --scene fin-10` | p05「啥」、p11「颁…奖」有字形 |
| `release_iso.py` | 发布 ISO 完整 IPL 开机链、标题初始形态 | `--profile release`（到 iso） | 02 帧 Prologue/load/option 三项 |
| `font_probe.py` | 字体/ruby/禁则探针逐页截图（`testboot.py` 的 `FONT_PAGES`，含 K1–K4/R1） | `--profile test --mode font` | K 帧标点悬挂/提前换行；R1 帧注音居中不裁 |
| `regtrace.py` | 断点 + 寄存器/内存转储 + 单步（研究 EBOOT 补丁用，见 `docs/ops/eboot-hacking-runbook.md` §5.6） | 同上 | 命中断点后逐条打印寄存器 |

跑法：

```bash
uv run python tools/build_disc.py --profile test --mode mainmenu
uv run python tools/emu/drives/menu.py
uv run python tools/emu/drives/library.py
uv run python tools/emu/drives/finale_full.py

uv run python tools/build_disc.py --profile test --mode scene --scene fin-10
uv run python tools/emu/drives/glyph.py

uv run python tools/build_disc.py --profile release
uv run python tools/emu/drives/release_iso.py
```

看图：截图是 480×272 PNG，直接打开；`finale_full.py` 一次几十帧，可先拼缩略马赛克。
`menu.py`/`finale_full.py` 的光标判定按颜色（亮态深蓝核心像素占比 ≈0.35，暗态 ≈0.1，
2026-09-02 实测校准）；换了菜单图要重校 `BANDS`。

前置环境：本机 PPSSPP master 双构建（`SNDL_PPSSPP_APP` / `SNDL_PPSSPP_HEADLESS` 可覆盖），
见 `docs/ops/ppsspp-local-setup-2026-08-31.md` 与 `tools/emu/README.md`。
