# PPSSPP 本地 e2e 环境搭建验收（2026-08-31）

前情：可行性调研见 `docs/research/ppsspp-e2e-feasibility-2026-08-31.md`。本机（arm64 / macOS 15.2 / 10 核 16GB / Xcode 全量）**尚无可用游戏 ISO**（用户确认），故本次只搭建并验收"不依赖镜像"的全部环节。ISO 到位后按文末清单组装基底目录即可开跑 M0 剩余项。

## 已完成并实测通过

1. **PPSSPP master 源码构建**（commit `1ee9168`，2026-08-31 克隆，深度 1 含子模块，约 2.4GB）：
   - 位置 `~/ppsspp`；App 构建 `~/ppsspp/build/PPSSPPSDL.app`；Headless 构建 `~/ppsspp/build-headless/PPSSPPHeadless`。
   - 依赖：brew `sdl3` + `sdl3_ttf`（**master 已从 SDL2 迁到 SDL3**，装 sdl2 无用）；cmake；Xcode CLT。
   - 配方：`cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j10`；headless 加 `-DHEADLESS=ON` 用独立 build 目录。
2. **WebSocket 调试通道全链路验证**（App 构建，`--debugger=45678` 启动，无游戏亦可）：
   - `tools/e2e/probe.py`（`uv run --with websockets python tools/e2e/probe.py`）连接 `ws://127.0.0.1:45678/debugger`（子协议 `debugger.ppsspp.org`）成功；
   - `version` 握手回报 `{name: PPSSPP, version: 1ee9168, pid, path}`（pid/path 可校验附着对象）；`game.status` → `game: null`；`cpu.status` → `paused: true`；`input.analog` 广播正常流动。
3. **Headless golden 比对链路验证**：pspautotests 样例 `cpu_alu.prx`（curl 自官方 repo）
   `PPSSPPHeadless /abs/path/cpu_alu.prx --compare --timeout=60 --graphics=software` → **1 tests passed**。

## 本机实况与坑（后续脚本要遵守）

- **headless 传入路径必须是绝对路径**：裸相对文件名会被当作 host0: 根目录挂载（`Failed to load executable host0:/xxx.prx`），实测 master 如此。
- **headless 默认图形后端是 Vulkan 且本机装不出**（`No vulkan library found`）——一律显式 `--graphics=software`（e2e 本来就要它保像素确定性）。
- **两套存档根**：App（SDL）= `~/.config/ppsspp/PSP/`（savestate 在 `PSP/PPSSPP_STATE`）；Headless = `~/.ppsspp/`。写自动化时勿混淆；headless 也可用 `--memstick` 显式指定共享。
- App 冒烟启动/关闭：`~/ppsspp/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL --debugger=45678`（前台弹窗）；`pkill -x PPSSPPSDL`。
- brew 里多装了一个无用的 `sdl2`（当时按旧文档装的），可 `brew uninstall sdl2`（若无他物依赖）。
- 本机 node v26.7.0 满足 `mcp-ppsspp`（Node ≥22）要求，需要交互式探索时可 `npx` 起。

## 无 ISO 摸底成果（决定基底目录组装与测试导航设计）

1. **DATA.BIN（302MB，assets/）内容清点**（`databin.py list` 扩展名直方图）：at3×6689（语音+BGM）、gim×2153、lua×229、vag×154（SE）、png×3、**pgf×2（两份字体都在包内！）**、db×1。→ **内容侧资源全份在手**。
2. **ISO 须补清单**（引擎壳）：`PSP_GAME/SYSDIR/EBOOT.BIN`（引擎 ELF，msg 断点 oracle 的宿主）、`PSP_GAME/USRDIR/module/libfont.prx`（lua_scripts 全库唯一 disc0: 引用）、`movie/op.mp4` + `movie/ed.mp4`（playMovie 引用，不在 DATA.BIN）、PARAM.SFO/ICON 等盘面元数据。PPSSPP 支持解包目录直接引导（`PSP_DISC_DIRECTORY` → VirtualDiscFileSystem），**无需重封 ISO**。
3. **测试引导脚本配方确认**（读 `snr_lib.lua` 全文）：伪造任意进度 = `cInitGame()` 后置 `gameSave.myCard[1..195].hold`、`startMenuState=2`、`tutorial.*=1`、`ayanoTime`、`storyRoute[..]`，再 `run(cGetFileName("script", 目标脚本)); quit()`。章节内跳场景：`doScriptScene` 是裸全局，赋值后 `run` 章节脚本即从该场景续跑。`config.lua` 的 `config.bootScript` 决定引导入口（现指 snr_common.lua）。

## ISO 到位后的 M0 剩余项

1. 解包 ISO → `assets/game/`（含 PSP_GAME/），把 `assets/DATA.BIN` 覆入对应位置；
2. `PPSSPPSDL --debugger=45678 assets/game` 引导 → probe 确认 `game.start` 广播与 `path` 字段；
3. `memory.searchDisasm`/字符串引用定位 msg 原生函数地址（EBOOT 固定，一次性）→ 挂 `{log:true, logFormat:"MSG {a0}"}` 断点，翻两页对白验证 vms ID 流；
4. `gpu.buffer.screenshot` 存图（480×272）；`input.buttons.press` 翻页；
5. 全绿 → 按调研报告 L0/L1/L2 分层立 `tools/e2e/` 正式客户端库 + pytest。
