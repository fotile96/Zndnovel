# OP/ED 影片在 PPSSPP 上不播放：根因、上游修复与实测（2026-09-24）

## 现象

原版 ISO 与我们所有发行版，在 PPSSPP 正式版（≤ v1.20.4）上都**不播 OP（`movie/op.mp4`）与 ED（`movie/ed.mp4`）**：
调 `playMovie` 后约 1 帧黑屏就返回，剧情照常继续，不崩溃、不影响进度。实机（CFW）一切正常。

## 根因

- 引擎的影片播放器（`lua_playMovie` 0x76A4 → 打开 `sub_B5B0` → 起播 `sub_BB10` → 每帧 tick `sub_BE74`，
  开机初始化 `sub_B444`）走 Sony **libmp4（sceMp4，24 个导入）解复用 + sceMpeg AVC 解码 + sceMp4AacDecode 解 AAC**，
  音频走 sceVaudio（48 kHz）。影片是 MSNV 品牌 MP4：H.264 Main L2.1 480×272 29.97fps + AAC-LC 48k 立体声
  （OP 203.04 s，ED 241.94 s）。
- PPSSPP ≤ v1.20.4 的 sceMp4 HLE **全部是空桩**（`Core/HLE/sceMp4.cpp`，只打 UNIMPL 返回 0）；
  sceMpegAvcDecode 只支持 ringbuffer（PSMF）路径。实测日志每次起播：sceMp4Create…GetAvcAu 全 UNIMPL →
  `sceMpegAvcDecode … Bogus mpegringbufferaddr` 返回 −1 → `sub_BE74` 置结束标志 → 清理返回。
- **没有任何 ini/兼容性设置能救**：PPSSPP 内置 FFmpeg 不含 MP4（mov）解复用器；当时的 `DisableHLEFlags`
  也不覆盖 sceMp4。只重编码 MP4 同样无效（空桩与文件内容无关）。
- 民间分支：唯一的 HLE 尝试是 sum2012 的 #20963「Implement sceMp4 by miniMax AI」（侧重 AAC 音乐），
  2026-06 未合并关闭。无可推荐分支。

## 上游修复（2026-09 系列 PR，已合并进 master）

| PR | 开发版号 | 内容 |
|---|---|---|
| #22252 | v1.20.4-1655（09-08） | 可选跑真 `libmp4.prx`/`mp4msv.prx`（LLE） |
| #22278 | v1.20.4-1735（09-10） | **开机时从游戏盘自带固件升级包自动安装固件**（`AutoUpgradeFirmware`，默认开） |
| #22286 | v1.20.4-1783（09-14） | 实现 sceVideocodec，sceMpeg 可 LLE |
| **#22309** | **v1.20.4-1841（09-18）** | **sceMpeg、sceMp4 默认改 LLE** |

LLE 需要 NAND 里有 `flash0:/kd/libmp4.prx` + `mp4msv.prx`（6.00 以上固件才有），缺则退回空桩并在屏上提示
「播放 MP4 需要安装 PSP 6.00 或更高版本的固件」。**本作 UMD 的 `PSP_GAME/SYSDIR/UPDATE/` 自带 6.20 升级包**
（游戏本身也要求 `PSP_SYSTEM_VER 6.20`），所以新版 PPSSPP 首次开本作就会自动装好 6.20，玩家无需操作。
我们的发布 ISO 与原盘相比 `SYSDIR/UPDATE/` 与 `movie/` 两段逐字节未动（`umdiso.py verify --against` 核过），
表现与原盘一致。

## 实测（本机 master f65598c6 = v1.20.4-1965，macOS arm64 JIT，软渲染）

构建：`~/ppsspp-new`（从 `~/ppsspp` clonefile 复制后 checkout，独立 build 目录；**e2e 基线 `~/ppsspp` 仍是 1ee9168，未动**）。
驾驶脚本经 `SNDL_PPSSPP_APP=~/ppsspp-new/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL` 切换。

1. NAND 原本为空 → 首次引导后自动装入 6.20（24 MB，`flash0/kd` 133 个模块含 libmp4/mp4msv/mpeg/videocodec_260）。
2. `build_disc.py --profile test --mode movie`（开机循环播 OP）全程 225 s：
   - 画面：影片帧出现在 **fb1（0x04088000）**，fb0 全黑——旧探针只读 fb0 会误判「黑屏」；
     45 个可判定截帧逐帧匹配原片（48×27 灰度 MSE≈3，无色偏/花屏）。
   - 声音：DumpAudio 录音与原片音轨全程包络 ncc **0.999**（覆盖 203.0 s），循环间隔 204.18 s（片长 + `wait(60)`）。
   - 音画差：中位 **−0.054 s**（范围 −0.110…−0.035 s），全程无漂移；无需上游的 `PaceVideocodecDecode` 兼容项。
3. 旧版 1ee9168 同盘对照：每次起播约 1 s 内失败返回（30 s 内循环 29 次），日志如「根因」所述。

未测（留作后续）：ED（`ed.mp4`，s7f 调用 `playMovie(…, false)`、s8f `playMovie(…, true)` 可跳过）——同一播放器、同一模块，
预期同样可播，但尚无实测记录；发布 ISO 自然流程（crd_2 做卡后）进 OP 未走。

## ⚠ 未决：新版 PPSSPP 的字体

新 master 在 NAND 字库齐全时 sceFont 默认改跑**盘上真 `libfont.prx`**（09-03 a641305c / 09-11 039ffc68），
而固件现在会自动安装——所以新版开本作几乎必走 LLE 字体。已有玩家反馈「很高版本的 PPSSPP 文字显示不正常」。
本次只做了一轮 font 探针（`--mode font`）新旧对比：两版都在不同页出现「文字发粗」的帧，疑为截图撞上过渡中间态，
**结论未定**，需稳定帧对比、IR 核心（iOS）与具体反馈版本号后再判。在此之前，玩家指南不宜无条件推荐开发版。

## 给玩家指南的事实要点（待字体结论后定稿）

- 正式版 ≤ v1.20.4（Windows/Android/iOS 当前全部正式版，iOS 商店版 1.20.4 / 2026-05-19）：OP/ED 自动跳过，不影响游戏。
- 能播的版本：**开发版 ≥ v1.20.4-1841**（ppsspp.org/devbuilds，只有 Windows zip/安装包、Android APK，
  含 legacy/VR/UWP；无 macOS、无 iOS）；或下一个正式版（PR 称约两个月后）。iOS 只能等商店正式版。
- 固件：首次开游戏自动从本作盘内装 6.20（屏上有进度条），无需另找固件。若 ISO 被「去除 UPDATE」压缩过
  （部分 CSO 工具有此选项），需在 设置 › 工具 › PSP Firmware 手动安装。
- Android：开发版 APK 包名 `org.ppsspp.ppsspp` 与商店免费版相同，签名不同可能装不上 → 先备份存档再卸载商店版；
  或装 legacy APK（包名 `org.ppsspp.ppsspplegacy`，可与商店版共存）。
- 实机：本来就正常。

## 复现材料

临时探针与分析脚本在 `build/movie_debug/`（不入库）：`probe_movie*.py`、`movie_sync_probe.py`（DumpAudio + 定时截 fb0/fb1
+ 记录录音长度）、`movie_sync_analyze.py`（`uv run --with numpy`；逐帧匹配 + 包络互相关）、`elf_imports.py`（EBOOT 导入表）。

## 追记：iOS（商店版 1.20.4）有没有办法（2026-09-24，源码核查）

结论：**没有「补 prx 走 LLE」的路**，iOS 玩家只能等商店正式版更新（下一个正式版）。依据（`git show v1.20.4:…`，本机 1ee9168 同）：

1. **视频解码层不存在**：v1.20.4 没有 sceVideocodec 的 HLE 实现（09-07 的 184c2cb4 才加），sceMpegbase 只有
   `PESpacketCopy`。真 `mpeg.prx` 靠这两层解 H.264，LLE sceMpeg 在 1.20.4 必然无画面；而 HLE 的
   `sceMpegAvcDecode` 只吃 PSMF ringbuffer（或 PMP 的 PESpacketCopy 路径），游戏的 MP4 路径两者都不走。
2. **HLE 优先绑定**：`ImportFuncSymbol` 对 HLE 已知库（`sceMp4` 在 HLE 表里）直接写 syscall；之后加载的真
   libmp4 导出被 `ExportFuncSymbol` 忽略（"already implemented in HLE"）。要绕开只能同时改 EBOOT 导入库名
   与 prx 导出库名。
3. **没有固件模块加载**：1.20.4 的 `sceUtilityLoadModule(0x308)` 只登记 HLE，不读 flash0 模块（09-12 的 4df01fd9 才加）；
   iOS 上 flash0 在 app 包内，玩家也放不进文件。
4. 即便 2 靠改名解决、libmp4 真跑起来，也只能得到解复用与（可能有问题的）AAC 音频，画面仍卡在 1。

唯一盘内可行路线是另写一个走 PSMF（sceMpeg ringbuffer 或 scePsmfPlayer HLE）的备用播放器（自编 PRX + EBOOT 钩子 +
重编码 .pmf + ISO 增文件），工作量大；**用户 2026-09-24 裁定：暂不做，万策尽了再说**。

附：若做中文字幕版 OP，仍须是 libmp4 能吃的 MP4——建议沿用原片参数（H.264 Main L2.1、480×272、29.97fps、
AAC-LC 48k 立体声、MSNV 品牌），出片后在新 PPSSPP（LLE）与实机各验一遍。
