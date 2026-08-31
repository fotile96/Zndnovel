# tools/emu — PPSSPP 模拟器 e2e 管线

对《セカンドノベル》中文化产物做游戏内自动化验证的工具层。设计依据
`docs/research/ppsspp-e2e-feasibility-2026-08-31.md`，环境验收
`docs/ops/ppsspp-local-setup-2026-08-31.md`。

## 组成

| 文件 | 职责 |
|---|---|
| `client.py` | PPSSPP WebSocket 调试器异步客户端（ticket 请求/广播游标/断点/输入/内存/截图/调速） |
| `launcher.py` | headless/app 进程生命周期 + 端口冲突重试 + 日志落盘（`build/emu/logs/`）+ `session()` 一体化上下文 |
| `imgdiff.py` | 与 PPSSPPHeadless 同款 MSE 公式的截图比对 + 可视化 diff |
| `probe.py` | 手工探针（握手 + 任意事件 + 广播监听），临场调试用 |
| `fetch_testdata.sh` | 下载 pspautotests 替身二进制与官方 GE 帧转储到 `build/emu/testdata/`（GPL/版权物，不入库） |

前置：本机 PPSSPP master 双构建（见 ops 验收文档；路径可用
`SNDL_PPSSPP_HEADLESS` / `SNDL_PPSSPP_APP` 覆盖）。

## 跑测试

```bash
bash tools/emu/fetch_testdata.sh   # 一次性
uv run pytest tests/emu/ -v        # 活体套件（约 5 秒）
uv run pytest -m "not emu"         # 排除模拟器用例
```

构建或素材缺失时自动整体 skip（云端/CI 无害）。

已实测覆盖（不依赖游戏 ISO，用 pspautotests 替身）：
- 传输：起进程→连 `/debugger`→version 握手（校验 pid）→放行→全程输出捕获；
- **日志断点跟踪**（未来 vms msg-oracle 同款机制）：log-only 断点 + `logFormat`
  表达式，`cpu.breakpoint.hit` 广播 + log 广播双通道，全程不停机；
- **输入注入**：开局断住预置按键→放行，`sceCtrl` 侧读到 CROSS 位掩码；
- **像素通路**：官方 GE 帧转储软渲染双跑逐像素一致（`--screenshot-save`），
  WS `gpu.buffer.screenshot` 语义正确。

## 游戏 ISO 到位后

```bash
export SNDL_GAME_DIR=/path/to/解包目录   # 含 PSP_GAME/，DATA.BIN 已覆入
uv run pytest tests/emu/test_game_boot.py -v
```

`test_game_boot.py` 即 M0 剩余项入口（引导→`game.start`→截图→无 ERROR 日志）；
之后按调研报告 L1（msg-oracle 文本流回归）/ L2（golden 视觉回归）在此扩展。

## 库内关键坑（详见 ops 文档）

- 广播匹配要用 `seq_mark()`/`after_seq` 排除陈旧事件（开局 startBreak 的
  `cpu.stepping` 会滞留在历史里）；
- CPU 断住时不推帧 → 不产生 `input.*` 广播（预置后放行再等回声）；
- headless 引导路径必须绝对路径；`--graphics=software`；`-l` 才有 log 广播；
- pspautotests 的 PRX 在 fast-forward 下瞬间跑完，不能当"持续绘制目标"。
