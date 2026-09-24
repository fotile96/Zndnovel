### Task 8: 文档、CFW 评估与收尾

**Files:**
- Modify: `docs/ops/movie-playback-ppsspp-2026-09-24.md`（「产品化」一节：命令面、Task 7 实测表、固件模块的取得、CFW 评估、玩家说明要点）
- Modify: `docs/ops/disc-pipeline.md`（新增「iOS 变体」一节：`--ios` 两剖面行为、产物路径、断言、层 profile=ios）
- Modify: `CLAUDE.md`（「已知坑」该条改为「已产品化：`build_disc.py --ios` → game_zh_ios.iso」，并在常用操作里加一行）
- Modify: memory `ppsspp-movie-lle.md`

- [ ] **Step 1: 固件模块的取得（写进 movie 文档）**

内容要点：①新版 PPSSPP（≥ v1.20.4-1841）开一次本作，自动从盘内 6.20 升级包装固件到 NAND；②`ppsspp.ini` 临时 `DumpFileTypes = 2`，开本作到影片播放；③PPSSPP 以 `~PSP` 头的模块名命名 dump，mp4msv/libmp4/mpeg 三者同为空白名会互相覆盖——本机做法是临时把 `Core/HLE/sceKernelModule.cpp` 的 PRX dump 名改成「文件名_模块名」重编一次（改完还原）；④产物改名为 `assets/fw/{libmp4,mp4msv}.dec.prx`，sha256 须等于 `tools/ios_fwmod.py` 的 `*_IN_SHA`。

- [ ] **Step 2: CFW 实机行为评估（写进 movie 文档，结论 + 用户亲测清单）**

逐项写明依据：
- 明文 EBOOT 与明文用户 PRX：现行盘已是明文 EBOOT；CFW 的模块加载补丁接受明文 PRX（汉化补丁常见做法）→ 预期可加载，**待实测**。
- 迟绑定：本作 EBOOT 本就在运行时 `sceKernelLoadModule` 加载 `libfont.prx` 并由此接上 7 个 `sceLibFont` 导入 → 实机支持「导入库晚于 EBOOT 注册」，`zndMp4` 同理。
- libmp4 的依赖：`sceMpegbase`、`sceAudiocodec` 由游戏原有的 `sceUtilityLoadModule(0x303)`（及其依赖）提供；本变体只替换了 0x308 这一次加载。
- E3 在实机：`sceMpegAvcResourceGetAvcDecTopAddr` 返回真实地址（新版 PPSSPP LLE 实测 `$a6 != 0x10000000`，Task 7 Step 3）→ 走原样 NULL 分支；E4 恢复的 pts 与实机解码器写回值同源，无副作用。
- 44.1k MP4：新版 PPSSPP 跑的就是固件真 libmp4 代码、已正常解复用本变体影片 → 实机 libmp4 同样可接受（强证据）。
- M2 跳板：实机 ME 解码器按 0x2C 定输入长度，0x1C 是输出字段、会被覆盖 → 无副作用；M3：返回 −1 → libmp4 取当前 gp 调回调，EBOOT 回调不用 gp → 无副作用。
- 风险：`libmp4` 模块属性 0x0006（独占加载/启动），本变体只在开机加载一次（`sub_B444` 仅由 main_loop 初始化段调用一次）；退出时 `sub_B560`/`sub_CEB8` 会 `sceUtilityUnloadModule(0x308)`，而 0x308 从未加载 → 返回错误、游戏不检查。
- 用户亲测清单：开机到标题 → 新游戏走到做完第一张卡（crd_2）看 OP → 有无声、有无破音/花屏 → 回标题再进一次；有 s7f/s8f 进度的存档看 ED；s8f 的 ED 按任意键可跳过。

- [ ] **Step 3: 玩家说明要点（写进 movie 文档）**

两个平行版本：`game_zh.iso`（Windows/Android/macOS 的 PPSSPP 与实机）与 `game_zh_ios.iso`（仅 iOS 商店版 PPSSPP，1.20.x）；iOS 版在 PPSSPP 升级到 1.21+ 后也能播（Task 7 Step 3 实测），但仍推荐届时换回现行版；两版存档互通（游戏 ID 与存档格式相同）；iOS 版的影片音轨为 44.1k 重采样，画面无改动。

- [ ] **Step 4: 全量测试与闸**

Run: `uv run pytest -q && uv run python tools/layers.py check --profile release`
Expected: 全 PASS；闸通过。

- [ ] **Step 5: 提交**

```bash
git add docs/ops/movie-playback-ppsspp-2026-09-24.md docs/ops/disc-pipeline.md CLAUDE.md
git commit -m "docs: iOS 变体盘产品化——命令面、实测、固件模块取得、CFW 行为评估与玩家说明要点

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
