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
  含 legacy/VR/UWP；无 macOS、无 iOS）；或下一个正式版（PR 称约两个月后）。iOS：商店版 1.20.4 可用下文「iOS 变体盘」
  （实验已通、待产品化），否则只能等商店正式版。
- 固件：首次开游戏自动从本作盘内装 6.20（屏上有进度条），无需另找固件。若 ISO 被「去除 UPDATE」压缩过
  （部分 CSO 工具有此选项），需在 设置 › 工具 › PSP Firmware 手动安装。
- Android：开发版 APK 包名 `org.ppsspp.ppsspp` 与商店免费版相同，签名不同可能装不上 → 先备份存档再卸载商店版；
  或装 legacy APK（包名 `org.ppsspp.ppsspplegacy`，可与商店版共存）。
- 实机：本来就正常。

## 复现材料

临时探针与分析脚本在 `build/movie_debug/`（不入库）：`probe_movie*.py`、`movie_sync_probe.py`（DumpAudio + 定时截 fb0/fb1
+ 记录录音长度）、`movie_sync_analyze.py`（`uv run --with numpy`；逐帧匹配 + 包络互相关）、`elf_imports.py`（EBOOT 导入表）。

## 追记：iOS（商店版 1.20.4）——改库名走 LLE，实验已跑通（2026-09-24）

> 同日早先的源码核查结论「没有补 prx 走 LLE 的路」**已被推翻**：它漏看了一点——真 libmp4 自己就导入
> `sceMpegbase::sceMpegBasePESpacketCopy`，用 LLI 链把 AU 交给解码器；而 1.20.4 的 HLE 恰好在
> `PESpacketCopy` 记下 LLI、在 `sceMpegAvcDecode` 里走「PMP 路径」用 FFmpeg 直接解。所以真 libmp4 一旦在
> 1.20.4 下跑起来，画面自动走通，缺的 sceVideocodec 根本用不到。

**思路（用户提出）**：两侧同时改库名，让 1.20.4 不把 EBOOT 的 sceMp4 导入钉死在 HLE 空桩上。`ImportFuncSymbol`
遇到 HLE 表里没有的库名会「暂存待解析」，真模块加载后 `ExportFuncSymbol` 自动补绑——自造名即可，不必借现成系统库名。

### 实测通过的全部改动（实验盘 `build/movie_debug/iosdisc`）

| # | 位置 | 改动 | 为什么 |
|---|---|---|---|
| M1 | libmp4 / mp4msv（取自本作 UMD 自带 6.20 升级包，解密） | 导出库名 `sceMp4`→`zndMp4`；libmp4 导入与 mp4msv 导出 `mp4msv`→`zndmsv`（同长度原地改） | 1.20.4 的 HLE 表里有这两个库（空桩），不改名就被 HLE 优先绑定 |
| M2 | libmp4 0x487c / 0x6054 | `jal sceAudiocodecDecode` 改指向跳板（放在游戏不用的导出 `sceMp4GetAvcAuWithoutSampleBuf` 入口，前 14 字无重定位）：`srcBytesRead(0x1C) = byte[0x2C] ? 0x609 : 0x600` 后 `b` 回导入桩 | 1.20.4 拿输出字段 0x1C 当 AAC 输入长度，首帧为 0 → 永远静音；规则同上游 b561de3f，新版不读 0x1C 无副作用 |
| M3 | libmp4 导入表 | `ModuleMgrForUser::0xD2FBC957`（取回调 gp，1.20.4 缺）计数清零，桩改 `jr ra; li v0,-1` | 缺函数的桩不设 v0 → gp 槽得垃圾；返回负值让 libmp4 走自带兜底（取当前 gp） |
| E1 | EBOOT VA 0x657D0 | 导入库名 `sceMp4`→`zndMp4` | 与 M1 配对 |
| E2 | EBOOT 0x624C8（`sceGumLookAt`，零引用死代码）+ 调用点 0xB470 | 47 字加载例程：`bal` 取 PC、`addiu` 算导入桩地址 `jalr`，依次 `sceKernelLoadModule/StartModule` `disc0:/PSP_GAME/USRDIR/module/{mp4msv,libmp4}.prx`；0xB470 的 `jal sceUtilityLoadModule(0x308)` 改跳这里；**重定位条目 file 0x84188/0x84198 改 R_MIPS_NONE** | 1.20.4 不从 flash0 装固件模块；插件目录也不行（插件加载器等 module_start 线程返回，这两个库没有 module_start → 开机死锁） |
| E3 | EBOOT 0x6262C + 调用点 0xB4F4 | `sceMpegCreate` 条件包装：仅当 `$a6`（DecTopAddr）== 0x10000000（1.20.x HLE 伪值）时 ringbuffer 参数 = mpeg 工作区 +0x7000 | 1.20.x `sceMpegAvcDecode` 无 ringbuffer 报 Bogus 返回 −1；新版/实机原样传 NULL |
| E4 | EBOOT 0x625D8 + 调用点 0xEA94 | `sceMpegAvcDecode` 保 pts 包装：调用前存 AU 前 8 字节、调用后写回 | PMP 路径解码后把 AU.pts 改写为 0，`sub_E9DC` 随后按 pts 登记帧 → 画面卡在首帧 |
| V1 | `movie/op.mp4`、`ed.mp4` | 音轨重采样为 AAC-LC 44.1k 160k，视频流原样拷贝（`ffmpeg -c:v copy -c:a aac -ar 44100 -b:a 160k -brand MSNV`） | 1.20.4 混音器 SRC 重采样 bug：每块 128 值弹出 `128×48000/44100=139`（截断且为奇数）→ 慢 0.229%、每 1.45 ms 左右声道错位＝破音。游戏按音轨采样率开 vaudio（全局 IDA 0x39CE3C 实测随之变为 44100），44.1k 时不走重采样 |

踩过的坑：E2 第一次没清洞里的重定位条目，装载器把 `lw s1,20(sp)`/`lw s0,24(sp)` 改成 `0x894(sp)`/`0x4018(sp)`
→ 越过 0x0A000000 → JIT/IR 下宿主进程段错误（1.20.4 macOS 没装内存异常处理器）；纯解释器（CPUCore=0）吞掉越界
访问才看得到解码日志，内存断点（`memory.breakpoint.add`）一次定位到出错 PC。

### 实测（本机 v1.20.4 fa50bb19 构建 `~/ppsspp-1204`；1.20.4 调试器靠 ini `RemoteDebuggerOnStartup/RemoteISOPort`）

| 场景 | 画面 | 声音（分段互相关 / 漂移） | 音画差中位（范围） |
|---|---|---|---|
| OP，1.20.4 JIT | 45 帧逐帧对上原片 | 1.000 / 0 | −0.067 s（−0.098…−0.031） |
| OP，1.20.4 IR 解释器（iOS 默认同类） | 同上 | 1.000 / 0 | −0.095 s（−0.171…−0.036） |
| ED（可跳过调法），1.20.4 JIT | 56 帧 | 1.000 / 0 | −0.086 s（−0.126…−0.040） |
| ED 跳过 | 任意键即跳（按键名为空串 = 任意键）；重播后正常推进 | — | — |
| 同一 iOS 盘，最新 master（LLE sceMpeg） | 正常 | 1.000 / 0 | −0.053 s |

未改音轨时（48k）的对照：画面正常但声音破音（分段相关 0.3–0.76、慢 0.23%）；未修 M2 时全程静音。用户在本机
PPSSPP 1.20.4 窗口人工盯完 OP 与 ED 全程，确认音画正常。

### 产品化待办（尚未开工，待用户确认）

- iOS 变体出盘：EBOOT 层（E1–E4，含重定位条目改 NONE）、两个模块（解密原件放 `assets/`、sha256 钉 manifest，
  补丁工具入库）、44.1k 影片、`umdiso.py` 增加「新增文件」能力（`module/` 目录加两条记录、数据追加卷尾）。
- 模块来源：本作 UMD 自带 6.20 升级包内的 Sony 固件模块（解密后改名打补丁随 iOS 盘分发）——分发形态需用户定夺。
- 中文字幕版 OP 若落地，iOS 变体应用同一母带重采样 44.1k。
- 实机未测（iOS 盘不面向实机）。

临时脚本：`build/movie_debug/{prx_relocs,patch_libmp4,cave_loader,cave_avcwrap,cave_createwrap,ppsspp1204,
movie_sync_probe,movie_sync_analyze,audio_local_align,skip1204}.py`（不入库）。

附：若做中文字幕版 OP，仍须是 libmp4 能吃的 MP4——建议沿用原片参数（H.264 Main L2.1、480×272、29.97fps、
AAC-LC 48k 立体声、MSNV 品牌），出片后在新 PPSSPP（LLE）与实机各验一遍。
