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
| `finale_full.py` | 谢幕全章 fin-10..50 跑通回主菜单（v3 后约 290 条消息，约 22 分钟） | `--profile test --mode mainmenu` | p010..p560 每 10 句一帧；end* 回主菜单 |
| `finale_scene.py` | 直入谢幕某场景逐句截图（`FIN_PRESSES`/`FIN_EVERY`/`FIN_SLEEP` 环境变量控制按键数/截帧间隔/间隔秒） | `--profile test --mode scene --scene fin-30`（或 fin-35/40/50） | 2026-09-22 fin-30 起 330 按：七张卡+空白卡→fin-35 右侧 mini 位七张卡→fin-40 p133 溶解到鲸客人 CG→fin-50 尾巴对话→p226 回主菜单（题名已换中文） |
| `bgm_probe.py` | 新曲探针：开 `DumpAudio` 直入场景静置 → 录音与 `at3p encode` 的 44.1k 参照做包络互相关，报首次对齐/整曲回绕/ncc，ppsspp.ini 用 try/finally 还原 | `--profile test --mode scene --scene fin-30`（含 sound 阶段） | `PASS`：full_pass_ncc ≥ 0.9、wrap_delta ≈ 曲长、无 E[Atrac] |
| `title_logo.py` | 题名 logo 双态：开机日文 → 跑完谢幕章回主菜单换中文 `title_01_c` → 重启仍中文（`finaleReadFlag` 已随 autoSystemSave 写进 NPJH50279SYSTEM）；logo 区与合成期望图按 MSE 判态；跑前备份、跑完恢复模拟器系统数据（`--keep-save` 保留） | 同上 | `判定: {'before_ja': True, 'after_zh': True, 'reboot_zh': True, …}`；ERROR 只有 `ILLEGAL_THID=sceKernelWaitThreadEnd` 这条 HLE 噪声（开机 1 条、谢幕全章约 8 条） |
| `glyph.py` | 直入场景逐句截图；缺省验 fin-10 的 7 个曾缺字 | `--profile test --mode scene --scene fin-10` | p05「啥」、p11「颁…奖」有字形 |
| `release_iso.py` | 发布 ISO 完整开场五卡开机链、标题初始形态；全程不按键（2026-09-21 起：菜单就位后按 CIRCLE 会直接开序章） | `--profile release`（到 iso） | 00/01/02 帧（45/50/55 s）至少两帧是 Prologue/load/option 三项（约每 10 s 一帧白闪盖住菜单项）；ERROR 0 或 1 条 ILLEGAL_THID 噪声 |
| `boot_dedication.py` | 开机五卡顺序与新增第五卡 `IPL03`（汉化组署名＋献词）：逐帧直读 VRAM，与本盘 stage 里五张卡的解码图按 MSE 判满亮帧，得首次命中序列 | `--profile test --mode mainmenu --no-fast-boot`（没有 `--no-fast-boot` 整段开场被剥掉）；或 `--disc build/dist/game_zh.iso` | `判定: {'order_ok': True, 'ipl03_held': True, …}`，seq 恰为 IPL01→IPL02→sys_1_a→IPL03→autosave；退出码 0 |
| `font_probe.py` | 字体/ruby/禁则探针逐页截图（`testboot.py` 的 `FONT_PAGES`，含 K1–K4/R1） | `--profile test --mode font` | K 帧标点悬挂/提前换行；R1 帧注音居中不裁 |
| `regtrace.py` | 断点 + 寄存器/内存转储 + 单步（研究 EBOOT 补丁用，见 `docs/ops/eboot-hacking-runbook.md` §5.6） | 同上 | 命中断点后逐条打印寄存器 |
| `save_roundtrip.py` | 存档往返：毒化旧结构区 → 暂停菜单「保存」走完 PSP 对话框（覆盖确认 ←○、完成 ✕）→ 推进两句 → 「读取」→ 核对恢复到存档那句、旧区仍全 0xEE；判据 saved/resumed/poison 三项 | `--profile test --mode scene --scene <id> [--bloat]`，用 `--patched` 读 savebuf 扩容布局 | `判定: {'saved_ok': True, 'resumed_ok': True, 'poison_ok': True}` |
| `mem_probe.py` | 定时快照 heap16 块表与 UserSbrk 指针，算模块+C 堆与 heap16 之间的空隙（扩 bss 的余地） | `--profile test --mode movie`（OP 循环播放，峰值场合）或任意盘 | 打印每次快照与最小空隙 |
| `save_probe.py` | 直入场景 → SQUARE 暂停菜单 → 「保存」→ 在 Pluto 序列化完成处断住，读出 gameSave/mainThread blob 真实大小并转储 406120 B 存档结构（`tools/pluto_size.py parse-dump` 解析） | `--profile test --mode scene --scene <id>` | 打印 `mainThread blob = N B / 327680 B`；05 帧是 PPSSPP 存档对话框 |
| `map.py` | 探索地图底栏 `select/sel_map_0_a` 的中文提示：五处 comSelectMap 逐页截图 | `--profile test --mode map` | 00–05 帧底栏「请选择要前往的地点。」红晕白字、`- MAP SELECT -` 原样、「当前位置」；01 帧为 00 帧按 DOWN 后光标态；ERROR 0 |

跑法：

```bash
uv run python tools/build_disc.py --profile test --mode mainmenu
uv run python tools/emu/drives/menu.py
uv run python tools/emu/drives/library.py
uv run python tools/emu/drives/finale_full.py
uv run python tools/emu/drives/title_logo.py

uv run python tools/build_disc.py --profile test --mode scene --scene fin-10
uv run python tools/emu/drives/glyph.py

uv run python tools/build_disc.py --profile test --mode mainmenu --no-fast-boot
uv run python tools/emu/drives/boot_dedication.py

uv run python tools/build_disc.py --profile release
uv run python tools/emu/drives/release_iso.py
uv run python tools/emu/drives/boot_dedication.py --disc build/dist/game_zh.iso

uv run python tools/build_disc.py --profile test --mode map
uv run python tools/emu/drives/map.py
```

看图：截图是 480×272 PNG，直接打开；`finale_full.py` 一次几十帧，可先拼缩略马赛克。
`menu.py`/`finale_full.py` 的光标判定按颜色（亮态深蓝核心像素占比 ≈0.35，暗态 ≈0.1，
2026-09-02 实测校准）；换了菜单图要重校 `BANDS`。

前置环境：本机 PPSSPP master 双构建（`SNDL_PPSSPP_APP` / `SNDL_PPSSPP_HEADLESS` 可覆盖），
见 `docs/ops/ppsspp-local-setup-2026-08-31.md` 与 `tools/emu/README.md`。
