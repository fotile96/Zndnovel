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

未测（留作后续）：原片 48k ED（`ed.mp4`，s7f 调用 `playMovie(…, false)`、s8f `playMovie(…, true)` 可跳过）在新版上
没有单独测；同一播放器、同一模块，且 iOS 盘的 44.1k ED 在新版上实测正常（见「产品化」），预期同样可播。发布 ISO 自然流程
（crd_2 做卡后）进 OP 未走。

## ⚠ 未决：新版 PPSSPP 的字体

新 master 在 NAND 字库齐全时 sceFont 默认改跑**盘上真 `libfont.prx`**（09-03 a641305c / 09-11 039ffc68），
而固件现在会自动安装——所以新版开本作几乎必走 LLE 字体。已有玩家反馈「很高版本的 PPSSPP 文字显示不正常」。
本次只做了一轮 font 探针（`--mode font`）新旧对比：两版都在不同页出现「文字发粗」的帧，疑为截图撞上过渡中间态，
**结论未定**，需稳定帧对比、IR 核心（iOS）与具体反馈版本号后再判。在此之前，玩家指南不宜无条件推荐开发版。

## 给玩家指南的事实要点（待字体结论后定稿）

- 正式版 ≤ v1.20.4（Windows/Android/iOS 当前全部正式版，iOS 商店版 1.20.4 / 2026-05-19）：OP/ED 自动跳过，不影响游戏。
- 能播的版本：**开发版 ≥ v1.20.4-1841**（ppsspp.org/devbuilds，只有 Windows zip/安装包、Android APK，
  含 legacy/VR/UWP；无 macOS、无 iOS）；或下一个正式版（PR 称约两个月后）。iOS：商店版 1.20.4 用下文「iOS 变体盘」
  `game_zh_ios.iso`（2026-09-24 已产品化，见「产品化」一节的玩家说明要点）。
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
| E2 | EBOOT 0x624C8（`sceGumLookAt`，零引用死代码）+ 调用点 0xB470 | 47 字加载例程：`bal` 取 PC、`addiu` 算导入桩地址 `jalr`，依次 `sceKernelLoadModule/StartModule` `disc0:/PSP_GAME/USRDIR/module/{mp4msv,libmp4}.prx`；0xB470 的 `jal sceUtilityLoadModule(0x308)` 改跳这里；**重定位条目 file 0x84188/0x84198 改 R_MIPS_NONE**（产品化时另把 0x84190 也改 NONE，见下文） | 1.20.4 不从 flash0 装固件模块；插件目录也不行（插件加载器等 module_start 线程返回，这两个库没有 module_start → 开机死锁） |
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

### 产品化（2026-09-24 落地）

用户裁定（2026-09-24）：①产品化；②接受随 iOS 盘分发改过的 Sony 固件模块；③两个平行版本——hack 版
`game_zh_ios.iso` 只推荐 iOS 商店版 PPSSPP，其余平台模拟器与实机一律用现行版 `game_zh.iso`；④（同日追加）以正式模式
重出 `game_zh.iso` 时总是一并重出 `game_zh_ios.iso`——做进 `build_disc.py`，不靠 runbook 提醒。
实施计划 `docs/superpowers/plans/2026-09-24-ios-movie-variant.md`，执行台账（含全部偏离计划的决定）
`.superpowers/sdd/2026-09-24-ios-movie-variant/progress.md`。

**命令面**（管线说明见 `docs/ops/disc-pipeline.md`「iOS 变体盘」）：

```bash
uv run python tools/build_disc.py              # 现行盘 build/dist/game_zh.iso 与 iOS 盘 game_zh_ios.iso 总是同出
uv run python tools/build_disc.py --profile test --mode movie [--movie ed --skippable] --ios   # 目录盘 build/test/game_ios/
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 2 --movie op --seconds 225 --disc build/test/game_ios
```

| 部件 | 工具 / 落点 | 钉住方式 |
|---|---|---|
| M1–M3 固件模块 | `tools/ios_fwmod.py`（type-B 重定位解码、改库名、AAC 跳板、GP 桩兜底）；原件 `assets/fw/{libmp4,mp4msv}.dec.prx`（不入库） | 输入/输出 sha256 是该工具常量 |
| E1–E4 EBOOT | `tools/ios_eboot.py` 生成 `layers/eboot/ios-movie.toml`（层 `profile = "ios"`，只在 `build_disc.py` 的 ios 阶段施加：release 出盘随 iso 必跑，test 要 `--ios`） | `tests/test_ios_eboot.py`：重生成逐字相同、现行 EBOOT 指纹不变、洞内重定位全 NONE、无悬空 HI16 |
| V1 44.1k 影片 | `tools/ios_movie.py`（原盘抽 op/ed → FFmpeg `-c:v copy -c:a aac -ar 44100 -b:a 160k -brand MSNV` + bitexact） | 产物 sha256 钉 `layers/manifest.toml [ios.movies]`；FFmpeg 升级字节变了硬失败，先在 1.20.4 上跑 `movie_probe` 复测再改指纹 |
| 往 ISO 加文件 | `tools/umdiso.py add`（数据追加卷尾、克隆兄弟目录记录格式、按名插入；目录区放不下/重名硬失败） | `tests/test_umdiso.py` |
| 驾驶 | `tools/emu/drives/movie_probe.py`（DumpAudio + fb0/fb1 截帧 → `tools/emu/movielab.py` 判定）、`tools/emu/legacy.py`（1.20.x 的 ini 调试器会话） | `tests/test_movielab.py` |

实验期临时脚本 `build/movie_debug/{prx_relocs,patch_libmp4,cave_loader,cave_avcwrap,cave_createwrap,ppsspp1204,
movie_sync_probe,movie_sync_analyze,audio_local_align,skip1204}.py`（不入库）已由上表工具取代，只作考古用。

**与实验盘的两处差别**：①产品化驾驶时发现原重定位表是 `[HI16 0x62570, HI16 0x62B74, LO16 0x62574]`——两个 HI16
共用一个 LO16。实验只 NONE 了洞内的 0x62570/0x62574，死代码里的 HI16 0x62B74（表项 0x84190）就没了配对 LO16：
PPSSPP 1.20.4 开机记 `ELF relocation HI16/0 pair (instead of LO16)`（`ERROR_LOG_REPORT`）并拿后面别的 LO16 凑进位，
实机装载器怎么处理未知；实机验证过的现行 EBOOT 一个悬空 HI16 都没有。产品化把它一并 NONE（死代码字不重定位，无害），
iOS EBOOT 与实验盘因此只差 0x84194 这一个字节。②影片加了 bitexact（去 encoder 标签、AAC 码率 162033→162114 bps），
字节与实验版不同，下表是产品本身的实测。

**实测**（本机 v1.20.4 `~/ppsspp-1204` 与 master f65598c6 `~/ppsspp-new`；「分段相关/漂移」不计落在片尾最后几秒的末段）：

| 场景 | 可判定帧 | 分段相关 / 漂移 | 音画差中位（范围） |
|---|---|---|---|
| OP，1.20.4 JIT | 45 | 1.000 / 0 | −0.109 s（−0.133…−0.068） |
| OP，1.20.4 IR 解释器（iOS 默认同类） | 45 | 1.000 / 0 | −0.115 s（−0.138…−0.049） |
| ED 可跳过调法，1.20.4 JIT；sceMpegCreate 调用点 `$a6` = 0x10000000（E3 走假 ringbuffer） | 55 | 1.000 / 0 | −0.085 s（−0.167…−0.065） |
| ED 按键跳过（1.20.4） | 按键前停在片中 13.21 s → 0.3 s 后黑屏 → 重播后 +10/+15/+20/+25 s 对上片中 8.74/13.81/18.89/23.89 s | — | — |
| ED，最新 master；`$a6` = 0x08C00000（E3 原样传 NULL） | 16 | 1.000 / 0 | −0.115 s（−0.161…−0.065） |
| 修悬空 HI16 后复测：OP 1.20.4 JIT / ED master | 44 / 16 | 1.000 / 0 | −0.076 s / −0.112 s |
| `build_disc.py --ios` 两次：现行 `game_zh.iso` sha256 `d65fb800…` 逐字节不变；iOS 盘 648171520 B 结构自检过 | — | — | — |
| iOS 发布盘在 1.20.4 开机：模块 `secondnovel`/`mp4msv_module`/`sceMp4_library` 在位，45–60 s 标题画面正常 | — | — | — |

以上 ERROR 日志只剩已知噪声：macOS 版不装异常处理器、PPSSPP 自带 `/font/zh_gb.pgf` 缺失、`sceKernelWaitThreadEnd`
的 ILLEGAL/UNKNOWN_THID（片尾等一个已退出的线程；片子照常循环）。1.20.4 IR 核心与 ED 跳过是修悬空 HI16 之前测的——
那一处只改了一个死代码字的装载期重定位，与 CPU 核心和影片无关，故未重跑。

**固件模块的取得**（`assets/fw/*.dec.prx` 是版权物，不入库；换机器要重取）：

1. 用新版 PPSSPP（开发版 ≥ v1.20.4-1841）开一次本作：自动从盘内 6.20 升级包把固件装进 NAND
   （`~/.config/ppsspp/PSP/NAND/flash0/kd/` 出现 libmp4.prx/mp4msv.prx，均为加密件）。
2. `ppsspp.ini` 临时设 `DumpFileTypes = 2`，开本作一路到影片起播，PPSSPP 把解密后的 PRX 写到
   `~/.config/ppsspp/PSP/SYSTEM/DUMP/`。
3. 坑：dump 文件按 `~PSP` 头里的模块名命名，mp4msv/libmp4/mpeg 三者这一栏都是空白，会互相覆盖。本机做法是临时把
   `Core/HLE/sceKernelModule.cpp` 里 PRX dump 的命名改成「文件名_模块名」重编一次（`NPJH50279_libmp4.prx_ .prx`
   这样），取完即还原源码与 ini。
4. 改名为 `assets/fw/libmp4.dec.prx`、`assets/fw/mp4msv.dec.prx`，sha256 必须等于 `tools/ios_fwmod.py` 的
   `LIBMP4_IN_SHA`（`ffa4c7e4…240e`）/`MP4MSV_IN_SHA`（`f9639c74…0bf5`）；任何能解密 6.20 固件 PRX 的工具产物都行，
   以指纹为准。

**CFW 实机行为评估**（静态分析 + 新版 PPSSPP 的 LLE 实测，**未上实机**；iOS 盘不面向实机，用户会另行亲测）：

- 明文 EBOOT：现行盘本来就是明文 EBOOT，实机正常（用户实测）。明文用户态 PRX（两个模块都是用户态：libmp4 属性
  0x0006、mp4msv 0x0000）：主流 CFW（PRO/ME/ARK，及 Vita 的 Adrenaline）的模块加载补丁接受明文 PRX，汉化补丁常用
  ——预期可加载，**待实测**。
- 迟绑定：本作本来就在运行时从 disc0 加载 `libfont.prx`（Lua 配置 `libfontModule = "disc0:/PSP_GAME/USRDIR/module/libfont.prx"`），
  EBOOT 的 7 个 `sceLibFont` 导入由此才接上——实机支持「导入库晚于 EBOOT 注册」，`zndMp4` 的 24 个导入同理。
- 依赖顺序（反汇编核对）：初始化段先调 `sub_CD68`（0xAAD8；`sceUtilityLoadModule` 0x300 avcodec / 0x302 / 0x301），
  再调 `sub_B444`（0xAAE8；0x305 vaudio、0x303 mpegbase，然后 0xB470 原本的 0x308 → 现在是加载例程）。libmp4 导入的
  `sceAudiocodec`（0x300）与 `sceMpegbase`（0x303）加载时都已就位。
- E3：实机的 `sceMpegAvcResourceGetAvcDecTopAddr` 返回真实地址（新版 PPSSPP LLE 实测 `$a6` = 0x08C00000）→ 条件包装走原样
  NULL 分支，与原版一致。E4、M2、M3：新版 PPSSPP 下 libmp4/mpeg 跑的就是 Sony 原代码（LLE），带着这三处补丁 ED 全程
  音画正常——强证据。其中 M2 只写输出字段 0x1C（真解码器会覆盖），M3 让 libmp4 取当前 gp 调回调。
  E4 包装只开 16 字节栈帧、把 pts/s0/ra 存在 0–12(sp)：若按 o32 约定，被调方可把参数溢出到调用方这段「参数保存区」而
  冲掉 ra（终审提出）。但 PSP 用 EABI：游戏调 `sceMpegAvcDecode` 时第 5 参数走 `$t0`（0xEA88 `addiu a4, sp, 4`，
  o32 下该放 16(sp)），EABI 没有调用方预留的参数保存区；游戏自己的 `sub_E9DC` 也把活数据放在 0(sp)/4(sp)、跨多次
  固件调用后再读（0xEAC8、0xEAEC）——固件若往调用方 0–15(sp) 写，原版在实机上就坏了。故 E4 的栈帧在实机上同样安全。
- 44.1k MP4：新版 PPSSPP 用真 libmp4 正常解复用本变体影片；vaudio 本就支持 44.1k（游戏按音轨采样率开通道）。
- 重定位表：iOS EBOOT 有 3 条 NONE（现行盘 1 条、实机正常）、0 个悬空 HI16。
- 风险点：libmp4 属性 0x0006（独占加载/启动），本变体只在开机加载一次（`sub_B444` 唯一调用点 0xAAE8）；
  退出清理 0xB58C 的 `sceUtilityUnloadModule(0x308)` 此时会返回错误，下一条指令就是下一个卸载调用、不查返回值。
  两个模块改由游戏自己加载，体积与原来经 sceUtility 加载的同一对模块相同，内存占用应相当（未实测）。
- 用户亲测清单：①开机到标题；②新游戏走到做完第一张卡（crd_2）看 OP——有无声音、有无破音/花屏；③回标题再走一次；
  ④有 s7f/s8f 进度的存档看 ED，s8f 的 ED 按任意键可跳过；⑤若第 ① 步就黑屏/回 XMB，先换现行版确认是本变体的问题，
  再记下 CFW 名称与版本。

**玩家说明要点**：

- 两个平行版本：`game_zh.iso`（Windows/Android/macOS 的 PPSSPP、实机、Vita Adrenaline）与 `game_zh_ios.iso`
  （**只推荐 iOS 商店版 PPSSPP**，即 1.20.4 正式版；更早的正式版实测放不出影片，见下 2026-09-27）。其余平台一律用现行版。
- iOS 版在 PPSSPP 升到含 LLE 的新版（开发版 ≥ v1.20.4-1841，将来的 1.21）后照样能播（最新 master 实测），
  届时仍推荐换回现行版。
- iOS 版不依赖固件：两个模块在盘里，NAND 空着也能播；压缩成 CSO 时去掉 UPDATE 目录也不影响 iOS 版放影片。
- 两版 DATA.BIN 相同、存档结构未动，存档应可互通（同一游戏 ID；未实测）。
- iOS 版影片的音轨是 44.1k（为绕开 1.20.x 混音器 48k 重采样破音）：ED 由原片重采样、画面原样；OP 两版都是中文字幕版（2026-09-26）。
- 用户 2026-09-26 实测：iOS 版在各平台 PPSSPP stable release 与 PSP 6.20 CFW 上 OP/ED 都正常播放（当时的 OP 为原片 44.1k 重采样版）；用户在考虑最终只发 iOS 版一版。
- 用户 2026-09-27 实测：Windows 上一台**旧版**正式版 PPSSPP 放不出 iOS 盘的 OP（字幕版第三版进盘后发现；版本号未记），更新到 stable 1.20.4 后正常。故 iOS 盘的推荐版本写 **1.20.4**，不是泛泛的 1.20.x。排查时先核实过：盘内 op.mp4 sha 与素材一致、`umdiso verify` 结构自检过、第三版与第二版容器/x264 参数逐项相同（只差字幕行的画面数据）；本机 1.20.4 JIT 目录盘驾驶第三版 PASS（见下节）。

### 中文字幕版 OP（2026-09-26 进盘）

用户压制的字幕版 OP（歌词原文＋译文，文字卡「「…うそ。」」配译）经 `manifest.toml [[movies]]` 进**两张盘**（素材
`assets/movie/op_zh.mp4` 不入库，sha256 `4da553b2…`）；ED 不变（现行盘原片、iOS 盘 44.1k 重采样）。iOS 盘直接用素材，
`tools/ios_movie.py` 只再重采样 ED。

- 第一版（x264 通用参数）被退回：`bframes=3`+B 金字塔、`weightp=2`、CRF18 无 VBV。原片 2010 年按 PSP 压制：Main L2.1、
  ref=3、**无 B 帧**、**wpredp=0**、ABR 900k 带 VBV 2000k/2000k。B 帧会让 iOS 层 E4 的 pts 写回对错帧（解码输出有重排延迟），
  weightp/B 金字塔是 PSP 这类老硬件解码器的雷区（模拟器用 FFmpeg 解码测不出）。
- 第二版按原片参数重压（`bframes=0`、`weightp=0`、CRF18+VBV 2000k/2000k；moov 在文件头），画面逐帧、音频零偏移对齐原片；
  换进 iOS 目录盘驾驶：1.20.4 JIT PASS（45 帧，音画差中位 −0.093 s）、最新 master PASS（44 帧，−0.088 s），分段相关 1.000、零漂移。
- 第三版（进盘版）只调了字幕描边：容器与编码参数同第二版，音轨逐包相同，画面差异只在字幕行；进盘时按用户意见未驾驶，2026-09-27 排查 Windows 旧版不播时补驾驶：`build_disc.py --profile test --mode movie --ios` 目录盘 + 1.20.4 JIT PASS（44 帧，音画差中位 −0.059 s，范围 −0.099…−0.044，分段相关最低 0.897、零漂移）。
- 版式留作用户裁量：约 40.5 s 左下「夏。」文字卡被字幕压住、约 80.5 s 上方日文压在人物眼睛上。
- 以后换 OP 素材：编码照上面的参数，换文件＋改 `[[movies]]` 的 sha256，`layers.py check` 会核指纹与 44.1k。
