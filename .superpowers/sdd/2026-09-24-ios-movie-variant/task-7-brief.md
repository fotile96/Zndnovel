### Task 7: 端到端验证（驾驶）与 iOS 发布盘

**Files:** 无代码改动；产物 `build/dist/game_zh_ios.iso`。结果写进 Task 8 的文档。

- [ ] **Step 1: test 目录盘 OP，1.20.4 JIT 与 IR**

```bash
uv run python tools/build_disc.py --profile test --mode movie --ios
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 1 --movie op --seconds 225 --disc build/test/game_ios
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 2 --movie op --seconds 225 --disc build/test/game_ios
```
Expected: 两次都 `PASS`（实验值：相关 1.000、零漂移、音画差中位 −0.067/−0.095 s）。

- [ ] **Step 2: ED 可跳过调法 + 跳过**

```bash
uv run python tools/build_disc.py --profile test --mode movie --movie ed --skippable --ios
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --movie ed --seconds 262 --disc build/test/game_ios
```
Expected: `PASS`。跳过：照 `build/movie_debug/skip1204.py` 的做法（15 s 时按 CIRCLE，之后 +10/+15/+20 s 截帧应推进到片中约 8.7/13.9/18.9 s）手动跑一次并记录。

- [ ] **Step 3: 同一目录盘在最新 master 上（Review Focus 4）**

```bash
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp new --movie ed --seconds 70 --check-dectop --disc build/test/game_ios
```
Expected: `PASS`，且打印 `$a6 != 0x10000000`（条件包装走原样 NULL 分支）。

- [ ] **Step 4: 现行盘不变（Review Focus 1）+ 出 iOS 发布盘**

```bash
shasum -a 256 build/dist/game_zh.iso > /tmp/before.sha
uv run python tools/build_disc.py --ios
shasum -a 256 -c /tmp/before.sha
uv run python tools/umdiso.py verify --against assets/orig.iso build/dist/game_zh_ios.iso
uv run python tools/umdiso.py list build/dist/game_zh_ios.iso | grep -E "module/|movie/"
```
Expected: `game_zh.iso: OK`（现行盘逐字节不变）；iOS 盘 verify 通过；列表含 `module/libmp4.prx`、`module/mp4msv.prx` 与新尺寸的 op/ed。

- [ ] **Step 5: iOS 发布盘在 1.20.4 上开机冒烟**

用 `tools/emu/legacy.session` 引导 `build/dist/game_zh_ios.iso`，等 60 s 到标题画面：`hle.module.list` 须含 `sceMp4_library` 与 `mp4msv_module`，日志无 `Unknown syscall`、无崩溃；截图确认标题画面正常。

---

