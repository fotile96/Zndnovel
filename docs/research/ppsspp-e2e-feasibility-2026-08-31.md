# PPSSPP 自动化 E2E 测试可行性调研（2026-08-31）

结论：**完全可行，且不需要发明任何东西**。PPSSPP 内置一套 JSON/WebSocket 调试与自动化 API（官方定位就含 automation），覆盖内存读写、按键注入、日志断点、截图、调速、输入录放；社区已有一个直接基于它的 MCP（`dmang-dev/mcp-ppsspp`，2026-05 创建，活跃维护）。配合"DATA.BIN 由我们重打包→游戏内可植入测试引导脚本"这一本项目特有优势，可搭出三层 e2e：冒烟 / 文本流回归 / 视觉（烤字）回归。

本文证据来源：PPSSPP master 源码树（sparse clone 实读，含 `docs/WebSocketDebugger.md` 官方权威文档）、v1.20.4 tag 原文件比对、GitHub API、mcp-ppsspp 仓库。

## 一、社区现成 MCP：有

**[dmang-dev/mcp-ppsspp](https://github.com/dmang-dev/mcp-ppsspp)**（TypeScript / Node 22+ / MIT / npm 已发布；2026-05-16 创建，2026-08-28 仍有 push；6 star、6 open issues——新而小但在维护，有 CI）。

- 原理：直连 PPSSPP 内置 WebSocket 调试器（子协议 `debugger.ppsspp.org`），**无需给模拟器装任何插件**。
- 暴露 20+ 工具：`ppsspp_read8/16/32`、`read_range/write_range/read_string`、`write8/16/32`、`press_buttons`（持续按住）、`press_button`（按 N 帧自动松开）、`send_analog`、`pause/resume/step/reset`、`screenshot`、`get_registers`、`breakpoint_add/remove/list`、`ping/get_info`。
- 已知短板（README 自述）：无 savestate 工具（靠 PPSSPP 界面热键）；帧级步进要靠 vblank 断点模拟；摇杆状态是持久的不自动回中。
- 定位判断：**适合"Claude 交互式探索/调试"**（找 msg 函数地址、临场看内存、手动验证 ruby 渲染），不适合当回归测试的地基——那层我们自己写薄客户端更稳（见四）。

其余搜到的 emulator MCP（mobile-mcp、android emulator MCP 等）与 PSP 无关。

## 二、PPSSPP 官方自动化界面盘点

### 1. WebSocket 调试器（主界面，官方文档 `docs/WebSocketDebugger.md`）

- 传输：与 Remote ISO 共用的 HTTP 服务，路径 `/debugger`，JSON 双向 `{"event": ...}`，带 `ticket` 关联请求。开启方式三选一：
  - UI：Settings → Tools → Developer Tools → **Allow remote debugger**（端口 = Networking 的 Local Server Port，0=自动）；
  - `ppsspp.ini`：`RemoteDebuggerOnStartup=true`；
  - CLI：`--debugger=PORT`（master 起 app/headless 通用；headless 下额外**开局断住 CPU**，便于先埋断点再放行）。
- 浏览器打开 `http://localhost:PORT/debugger/` 即得内置图形调试器（React），适合人肉探索。
- 官方参考客户端：`Tools/wsdbg`（Rust REPL）、`scripts/websocket-test.py`（python + websocket-client）。

与本项目直接相关的命令子集（全量约 100 条，实测自 master 源码 `map["…"]` 注册表）：

| 能力 | 命令 | 备注 |
|---|---|---|
| 内存 | `memory.read/write(_u8/u16/u32)`、`memory.readString`、`memory.search`（Cheat Engine 式扫值/字节模式） | 找引擎全局、读当前文本 |
| 断点 | `cpu.breakpoint.add {address, log, condition, logFormat}` | **log-only 断点不停机**，`logFormat` 可带 `{a0}` 这类表达式 → 天然的调用跟踪器 |
| 输入 | `input.buttons.press {button, duration帧}`（完成后才回包=现成同步原语）、`input.buttons.send`（持续状态）、`input.analog.send` | 按键名 cross/circle/up/… 全套 |
| 截图 | `gpu.buffer.screenshot`、`gpu.buffer.renderColor/Depth/Stencil`、`gpu.buffer.texture/clut` | base64 PNG，480×272 原生分辨率，与窗口缩放无关 |
| 录放 | `replay.begin/flush/execute/status`、`replay.time.get/set` | 输入流录制为 base64 可存档回放；RTC 基准可固定 → 确定性重放 |
| 流程 | `game.reset`、`game.status`、`cpu.status/resume/stepping`、`cpu.runUntil` | |
| 日志 | `log` 广播（引擎日志全量推流）、`log.channel.set` | 崩溃/报错检测；日志断点的输出通道 |
| 广播 | `game.start/quit/pause/resume`、`cpu.stepping/resume`、`input.*` | `game.start` = "游戏引导完成"信号 |

**版本矩阵**（决定装哪个 PPSSPP）：

- 最新稳定 **v1.20.4**（2026-05-16）：上表全部**已有**（含日志断点三参数、replay、gpu.buffer——均实测 tag 原文件确认）。
- 仅 **master**（下一版才有）：`game.speed.set {fastForward:true}` 远程调速、`cpu.runUntilTime`（跑到指定模拟时刻）、`cpu.breakpoint.hit` 结构化广播（不用从 log 文本里抠）、`client.config.set {acknowledgeDeferred}`、app 端 `--debugger=PORT`/`--state=FILE` 统一 CLI（`Core/CmdLine.h`，v1.20.4 尚无此文件）、`docs/WebSocketDebugger.md` 本身。
- 建议：**直接 cmake 自编译 master**（mac arm64 顺利，且反正 headless 在 mac 只能自编译：`cmake -DHEADLESS=ON`）；退路是稳定版 1.20.4 + ini 开关，核心方案不受影响（调速可用游戏内跳过/快进机制代偿，hit 广播用 log 流解析代偿）。

### 2. PPSSPPHeadless（无头构建）

自动回归的原型参照（pspautotests/frametests 就是这么跑的）：`--timeout=秒`、`--screenshot=参照图 --max-mse=阈值 --screenshot-diff=可视化diff`、`--screenshot-save=`、`--graphics=software`（软渲染，**逐像素确定性**，官方推荐测试用）、`--debugger=PORT`（开局断 CPU）、`--state=FILE`、`-r`/`-m` 挂载。失败时自动落 `__testfailure.bmp` + `__testcompare.png`。MSE 截图对比、参照图生成、diff 可视化——**golden image 基建官方全带了**。
注意：headless 无显示无交互，适合"跑到某状态截一张比对"型用例；需要连续按键推进的用例用 app 构建 + WebSocket（headless 默认 fast-forward，master 上也接受 WS 输入注入，可作纯无头方案试点）。

### 3. 其他界面（了解即可）

- **Lua console**（Core/LuaContext.cpp）：还是雏形——全文 141 行，只注册了 print 族 + `r32`（读内存）。**现阶段不可用**，持续关注上游。
- **emu-api**（`docs/emu-api/`）：给*游戏侧代码*用的 `sceIoDevctl("emulator:")` 通道（`SEND_OUTPUT` 直打模拟器日志、`EMIT_SCREENSHOT`、`TOGGLE_FASTFORWARD`）。本作是固定商业 ELF，游戏内 lua 未暴露 devctl，**不适用**（除非未来改引擎原生层，不值得）。
- **文件夹直接引导**：`Core/Loaders.cpp` 识别 `PSP_DISC_DIRECTORY` → `VirtualDiscFileSystem`。**解包后的 UMD 目录（含 PSP_GAME/）可直接当游戏打开** → 改译文只需 `databin.py pack` 覆盖目录里的 DATA.BIN，**免重封 ISO**，迭代极快。
- CLI 常用（master）：`--fullscreen`/`--windowed`、`--graphics=software`、`--state=FILE`（开局载档）、`--appendConfig`、`--xres/--yres`、`--escape-exit`。

## 三、与本项目的独特契合点

1. **游戏内测试引导脚本（杀手锏）**：`config.lua` 的 `bootScript` 指向可换（现为 snr_common.lua；游戏自带 `snr_lib.lua` 调试菜单可直入 SEC7F/PROLOGUE/STORY/DEBUG）。DATA.BIN 由我们重打包 → 可生成 `snr_test.lua` 作 bootScript：预置 `gameSave.myCard/storyRoute`、设 `doScriptScene=目标场景`、直接 `run` 目标章节——**O(1) 跳到任意待验场景**，不依赖 savestate（savestate 会把旧版脚本文本冻结在 RAM 里，换译文后回放旧文本，有陈旧性陷阱——只在同一数据版本内当加速用）。
2. **msg 断点 = 文本流 oracle**：所有正文走 `vms(id,voice,text)` → C 侧 `msg(id, text)`。用调试器定位 msg 原生函数一次（`memory.searchDisasm`/字符串引用；EBOOT 固定，地址一劳永逸），挂 log-only 断点 `logFormat: "MSG {a0}"` → 一次自动游玩产出**按实际顺序的 vms ID 流**，与 `analysis/dag_all.txt` 的预期路线 diff——DAG 重建的机器验证、译文覆盖率、跳转门控回归，全在一个探针上。消息 ID 全局唯一恰好是主键（CLAUDE.md 既定）。
3. **烤字/排版视觉回归**：`gpu.buffer.screenshot` 拿 480×272 原生帧 → 对 `build/` 里的烤字产物做 golden diff。**首个用例现成**：CLAUDE.md 悬置的两个 ruby 实测问题（ruby 层用哪个字体、拼音声调元音 `ā á ǎ à` 是否有字形）——起一个含 `<汉字,pīn yīn>` 的测试场景截图即验。中文行溢出检测同理（截图右缘白名单区域像素检查，或人审图集）。
4. **推进策略**：外部 runner 以 `input.buttons.press {button:"circle", duration:2}` 节拍连打推进对白，同时收 msg 断点流做进度感知 + 看门狗（N 秒无新 msg = 卡死/待选择）；选择肢用方向键 + circle 按 DAG 指定路径走。全程 `game.speed.set fastForward`（master）提速。

## 四、建议架构与落地路线

**形态**：`tools/e2e/` 下一个 ~200 行 python WebSocket 客户端（`websockets` 库，uv 管理）+ pytest 用例层 + golden 图目录（`build/e2e-golden/`，gitignore 视情况）。MCP 不做地基：CI 型回归用 CLI/pytest 最顺；等交互式调试需求出现，`uv run fastmcp` 把同一客户端库包一层即可（或直接用现成 mcp-ppsspp 做临场探索）。

分层用例：
- **L0 冒烟**（每次重打包后）：headless 或 app 启动解包目录 → 等 `game.start` → 播到标题画面截图比对 → log 流无 ERROR。验证 DATA.BIN 回封完整性、字体加载。
- **L1 文本流回归**：test bootScript 直入指定章节 → 连打推进 → msg ID 流 diff 预期序列；崩溃/卡死看门狗。逐章跑通即是"中文化后全流程可玩"的机器证明。
- **L2 视觉回归**：关键画面（标题菜单、卡片、选择肢、ruby 样例、每章首场景）golden diff，`--graphics=software` 保确定性；阈值参照 headless 的 MSE 思路自实现（我们走 WS 截图，比较逻辑在 python 侧，Pillow 现成）。

**前置条件**（当前缺口）：
1. 本机未装 PPSSPP（`/Applications` 无、brew 无、headless 无）——需 `git clone` + cmake 编译 master（顺带 `-DHEADLESS=ON`），或先 `brew install --cask ppsspp`（1.20.4）快速起步。
2. `assets/` 只有 DATA.BIN——e2e 需要**完整游戏**（ISO 或解包目录含 EBOOT.BIN/module/pgf/voice 等）。需确认完整镜像在本机的位置，解包一份作为测试基底目录。
3. 调试端口只应本机监听期使用（它同时是 Remote ISO 共享端口，勿长开）。

**M0 验证清单**（半天，全部人工一次性）：装 PPSSPP → 解包目录引导本作 → 开 Allow remote debugger → 浏览器 `/debugger` 连上 → 手动 `memory.searchDisasm` 定位 msg 函数并挂 log 断点，翻两页对白看 ID 流 → `gpu.buffer.screenshot` 存图 → `input.buttons.press` 翻页成功。全绿则 L0–L2 无技术风险，进入工具化。

## 附：本次调研的判断依据

- master sparse clone 实读：`Core/Debugger/WebSocket/*.cpp`（命令注册表全量枚举）、`docs/WebSocketDebugger.md`、`docs/frametest.md`、`headless/README.md`、`Core/CmdLine.h`、`Core/LuaContext.cpp`、`Core/Loaders.cpp`（PSP_DISC_DIRECTORY）。
- v1.20.4 tag 原文件比对：GameSubscriber（无 speed.set）、SteppingSubscriber（无 runUntilTime）、BreakpointSubscriber（log/condition/logFormat 已有）、CmdLine.h（404，未引入）。
- [dmang-dev/mcp-ppsspp](https://github.com/dmang-dev/mcp-ppsspp)（README + GitHub API：2026-05-16 创建 / 2026-08-28 push / MIT / 6★）。
- [PPSSPP releases](https://github.com/hrydgard/ppsspp/releases)：latest = v1.20.4（2026-05-16）。
- 游戏侧：`lua_scripts/config.lua`（bootScript 可换）、`lua_scripts/snr_lib.lua`（调试引导菜单）。
