# 谢幕章新增 BGM：PCM → ATRAC3+ → SOUND.BIN → Lua 消费 设计

> 调研日 2026-09-17。用户要提供 1–2 段 PCM 素材，作为谢幕章（encore，`layers/scripts/snr_finale.lua`）
> 的 BGM 播放。本 spec 是**调研 + 方案**：§1–§3 是用反编译与模拟器探针钉死的事实，§4–§6 是
> 管线设计，§8 是需要用户拍板的点。探针脚本与产物在 `build/sound/`（gitignore，一次性，
> 不入库）；本文所有数字都可按 §附 重跑复现。

> **实施状态（2026-09-22）**：已按 §9 落地——`tools/at3p.py`（encode/inspect/verify）、
> `tools/build_atracdenc.sh` + `tools/atracdenc-744.patch`、`manifest.toml` 的 `[sound]`/`[[sound.tracks]]`
> （比 §4.1 的写法多一层 `tracks`：TOML 里同名的表与表数组不能并存）、`layers.py check` 的
> `_check_sound`、`build_disc.py` 的 `sound` 阶段与断言⑤、`tools/emu/drives/bgm_probe.py`、
> `tests/test_at3p.py`/`test_build_disc_sound.py`。首曲 `bgm/bgm_fin_1.at3`（用户自供 `bgm_5_x` remix，
> 整曲循环、裁到 3:16、−21 LUFS）登记进包，用于谢幕章 fin-30/35。§8 的裁定见
> `docs/finale/draft-finale-v3.md` D4；实机（CFW）试听仍待用户。

---

## 0. 结论摘要

- **BGM 的唯一载体是 `SOUND.BIN`**（ISO 内 79.8 MB 独立文件），与 `DATA.BIN` **同一种 `pack`
  容器**，99 个成员（`bgm/*.at3` 31 首 + `se/loop_*.at3` 24 + `se/mus_*.at3` 44），`tools/databin.py`
  原样可用（unpack→pack 逐字节回环已验证）。加 BGM = 往 SOUND.BIN 插新成员 + `umdiso replace`
  多换一个文件，**不需要动 EBOOT**。
- **引擎只吃 ATRAC3+**：播放线程 `sceAtracGetAtracID(0x1000)` 把编解码器钉死为 AT3+，喂 ATRAC3
  会 `SCE_ERROR_ATRAC_WRONG_CODECTYPE`（模拟器实测）。且 `sceAtracSetLoopNum(loop ? -1 : 0)`
  **两种取值在文件无 `smpl` 块时都报错、线程直接退出**——新曲必须带 `smpl` 循环块（原版 99/99 都有）。
- **编码器：atracdenc**（LGPL，开源，macOS 可编）。其 AT3+ 编码器是"实验性"、帧长硬编码
  2048 B（352 kbps）；**改一个常量为 744 B 即得与原版逐帧同尺寸的 128 kbps**，ffmpeg 解码正常，
  与源 PCM 包络相关 0.998、响度一致。它自带的 RIFF 头**过不了固件校验**（fmt 块 40 B < 固件要求的
  52 B，且无 `smpl`）——所以只取它的裸帧流（`--container raw`），**RIFF 头由我们自己按原版模板写**。
- **原版头部算式已完全还原**（99/99 成员逐字节吻合）：设 T = 帧数×2048、d = 编码延迟、
  S = 循环起点（源 PCM 采样数，整曲循环为 0）：`fact = (T−d−368, d, d+184)`，
  `smpl.loop = (S+d+184, T−185)`。atracdenc 的 d 实测 4464（冲激响应法，744/2048 两种帧长相同）。
- **模拟器端到端已通**：把自制 at3 塞进 SOUND.BIN 替换 `bgm_19_x`，直入 fin-10，PPSSPP（其
  `AtracCtx2` 是照真机固件反写的解析器）播放全曲、在 53.10 s 精确回绕、零 sceAtrac 报错。
- **残余风险只有一个**：真机 ME 解码器对 atracdenc 实验性比特流的容忍度，PPSSPP 证明不了。对冲：
  早出一张测试 ISO 上实机听；若用户手上有 Sony `at3tool`（PSP SDK，Windows），用它编 128 kbps 是
  金标准，产物可直接替换、管线其余部分不变。

## 1. 引擎事实（IDA，`build/eboot/EBOOT.dec.elf.i64`，地址为 IDA VA）

| 项 | 事实 | 出处 |
|---|---|---|
| Lua 原语 | `playBGM(slot, path, loop)` / `stopBGM(slot, fadeFrames)`；snr_common 封装：slot 0 = BGM（`cPlayBGMWrap`/`cPlayBGMNotLoop`/`cStopBGMWrap`），slot 1 = 环境循环音与一次性曲（`cPlayLoopSeWrap`/`cPlayOneshotMusic`） | `snr_common.lua` L768–816 |
| 路径 | `cGetFileName("bgm", n)` → `bgm/n.at3`；`"loop"`/`"mus"` → `se/n.at3`；引擎前缀 `disc0:/PSP_GAME/USRDIR/` | `snr_common.lua` L822–866；`lua_playBGM` 0x8AF4 |
| 起播 | `lua_playBGM` → `sub_D058(slot, path, loop)`：填槽结构（`dword_292F40 + slot*size`，名字 +4、loop 字节 +0x54、音量 +0x58 = `dword_3251D8[slot]`）→ `sceKernelCreateThread("mgkThreadATRAC3", sub_D978, prio 0x11, stack 0x10000)` | 0xD058 |
| 寻径 | 线程 `sub_D978`：`pack_index_lookup(0x391210 + 36*slot, name)`——**两个槽各持一个 SOUND.BIN 句柄**（开机 `sub_EC8` 打开 DATA.BIN×1 + SOUND.BIN×2 三个描述符）；60 B/项 strcmp 二分（成员表必须严格升序）。**找不到则回退 `sceIoOpenAsync` 散文件** `disc0:/PSP_GAME/USRDIR/bgm/x.at3`（模拟器目录引导可用来免打包试听；ISO 发布不能用——`umdiso.py` 只替换不新增文件） | 0xD978 / 0x1124 / 0xEC8 |
| 解码 | 首读 min(size, 0x20000)；`sceAtracGetAtracID(0x1000)`（**AT3+ 专用**）→ `sceAtracSetData` → `sceAtracSetLoopNum(loop ? -1 : 0)` → `sceAtracGetRemainFrame` → 循环 `sceAtracDecodeData`，按 `sceAtracGetStreamDataInfo` 续读（每次 ≤ 0x10000）`sceAtracAddStreamData`；PCM 经 SAS 混音（`sub_536E8/sub_53828`）。任一 sceAtrac 调用失败 → 释放、线程退出、**无声无提示** | 0xDD28–0xE208 |
| 存档 | BGM 槽文件名存在系统数据（2×80 B，`0x631C0`）；谢幕章不进 storyRoute、不存档，新曲名 ≤ 80 B 无影响 | `eboot-savedata-research-2026-09-05.md` |
| 画廊 | `snr_music.lua` 的 22 首列表是硬编码表 + `music_NN_a` 图；新曲**不登记**（攻略/画廊不剧透 encore，与既有裁定一致） | `snr_music.lua` L1 |

## 2. 文件格式事实

### 2.1 SOUND.BIN

`pack` 容器（`databin.py` docstring 格式），99 成员全 raw 存储、无 lzss。表按名升序。
`databin.py verify --full` OK；unpack→pack 逐字节回环 OK。ISO 内位于 LBA 228560（38994 扇区），
后面还有 `module/libfont.prx`、ICON0/PIC0/PIC1、PARAM.SFO——变大时 `umdiso.replace` 的尾部平移
覆盖这些（多文件按 LBA 从后往前处理，已内建）。

### 2.2 原版 at3 头（99/99 一致，`bgm_20_b` 为模板）

```
RIFF/WAVE
fmt  (52 B) 0xFFFE 扩展格式: ch=2 sr=44100 avg=ceil(744*44100/2048)=16021 blockAlign=744 bps=0
            cbSize=0x22 validBits=2048 chanMask=3 GUID=bfaa23e9-58cb-7144-a119-fffa01e4ce62
            version=1(LE) codecParams=0x285C(BE: bit13 | chanId<<10 | (frame-8)/8)  + 8 B 零
fact (12 B) (T−d−368, d, d+184)
smpl (60 B) 标准 sampler 头(numLoops=1, samplerData=0x18) + 1 条 loop (start=S+d+184, end=T−185)
data        帧流，744 B/帧，2048 采样/帧
```

- 全库 98 首立体声 + 1 首单声道（`se/loop_22`，codecParams 0x245C）。**全部 44.1 kHz、128 kbps**。
- 原版 d 逐曲不同（2094–4089），S 主 BGM 多为"前奏 + 循环段"（如 `bgm_19_x` 从第 748009 采样
  ≈17 s 回绕），loop/mus 全是整曲循环。**固件解析**（PPSSPP `AtracTrack.cpp::ParseWaveAT3`，照
  真机反写）：fmt 必须 ≥ 0x34 B、GUID 命中、codecParams 高字节编码的声道数要与 ch 一致、
  sr 必须 44100；12 B 的 fact 走"扩展"分支：`firstSampleOffset = 第 3 字 − 0xB8`，`smpl` 两端也
  各减 0xB8——即最终起播点 = d、循环起点 = S+d。上述算式对 99 成员全部成立（脚本见 §附）。
- 原版曲目响度基线（供新曲对齐）：`bgm_19_x` −20.8 LUFS / 峰 −2.2 dBFS；`bgm_20_b` −22.4 / −7.8；
  `loop_6` −24.6 / −12.9。**新曲目标 ≈ −21 LUFS 综合响度**，峰值留 ≥ 1 dB 余量。

## 3. 编码器选型与探针结果

| 路线 | 结果 |
|---|---|
| ffmpeg | 只解不编 ATRAC 族（9.0.1 实测 encoders 无 atrac） |
| **atracdenc**（github dcherednik/atracdenc @ cb17070, 2026-09-08） | macOS arm64 可编（需 `brew install libsndfile`，CMake 里 `CMAKE_OSX_ARCHITECTURES` 强制 universal 要改成 `arm64`，子模块 `libgha` 要 `--recursive`）。AT3+：`-e atrac3plus`，`--bitrate` **对 AT3+ 无效**，帧长在 `src/atrac/at3p/at3p.cpp` `BitStream(out, 2048)` 硬编码 → 改 744 后输出 744 B/帧、ffmpeg 解码 128 kb/s、包络相关 0.998。输入限 44.1 kHz/16-bit WAV（重采样交给 ffmpeg）。自带 RIFF 头不合固件（fmt 40 B、无 smpl）——只用 `--container raw` |
| atracdenc ATRAC3 132 kbps | 编码成熟，但**引擎拒绝**（WRONG_CODECTYPE，见 §1）。要用得给 EBOOT 打补丁改 `li $a0,0x1000`→`0x1001`，不值得 |
| Sony at3tool（PSP SDK，Windows） | 原版即此工具产物，金标准；本机无 wine、SDK 属专有软件，**仅当用户自有**时作为可选路线：`-br 128` 编 AT3+，产物直接进管线（头部由我们的工具重写/校验，与 atracdenc 路线共用） |

模拟器探针（PPSSPP master，`--graphics=software`，`DumpAudio=True` 录混音输出，直入 fin-10，
连按 15 次 CIRCLE 走完 fin-0 递笔段，BGM 起播后静置 85 s，与源 PCM 做 50 ms 包络互相关）：

| 探针 | 内容 | 结果 |
|---|---|---|
| AT3+ 352 kbps（2048 B/帧，模板头，整曲循环） | 替换 `bgm_19_x` | 播放正确（ncc 0.94 全程），**53.10 s 回绕**（曲长 53.17 s），日志零 Atrac 报错 |
| ATRAC3 132 kbps（atracdenc 原生头 + 注入 smpl） | 同上 | **拒绝**：`sceAtracSetData: atracID uses different codec type than data`；录到的只有 loop_6 蝉声 |
| **AT3+ 128 kbps（744 B/帧，模板头，S = 10 s 局部循环）** | 同上 | 播放正确（ncc 0.937 全程），**曲末 104.62 s 回绕后从源曲第 10 s 续播**（该点与 src@10s 相关 0.827、与 src@0s 仅 0.697 且偏 0.65 s），零 Atrac 报错——推荐路线的起播、流式续读、局部循环三项全部在模拟器过 |

## 4. 管线设计

原则与现有层纪律一致：**基座只读、改动落 `layers/`、构建产物落 `build/`、发布断言把关**。

### 4.1 素材与清单

```
assets/audio/<name>.wav        用户 PCM 原件（任意采样率/位深/声道；/assets 已 gitignore）
layers/audio/<name>.at3        编码定稿（RIFF AT3+，几 MB；入库，理由见 §8 c）
layers/manifest.toml           新节：
  [[sound]]
  member   = "bgm/bgm_fin_1.at3"     # 成员名（决定 cGetFileName("bgm","bgm_fin_1")）
  source   = "assets/audio/fin_1.wav" # 原件；sha256 钉在下面
  sha256   = "…"
  artifact = "audio/bgm_fin_1.at3"    # layers/ 相对路径，管线用的就是它
  loop     = { start = 0.0 }          # 秒，源 PCM 时基；整曲循环 start=0；end 恒为曲末
  target_lufs = -21.0                 # 编码前响度归一目标；缺省 -21
  [sound]
  iso_path = "/PSP_GAME/USRDIR/SOUND.BIN"
  encoder  = "build/atracdenc/build/src/atracdenc"   # 环境变量 SNDL_ATRACDENC 覆盖
```

### 4.2 工具

- `tools/build_atracdenc.sh`：clone（钉 commit）→ `git submodule update --init --recursive` →
  `git apply tools/atracdenc-744.patch`（两处：arm64、`BitStream(out, 744)`）→ cmake/build →
  `build/atracdenc/`。幂等，可重跑。
- `tools/at3p.py`（纯 stdlib + 调 ffmpeg/atracdenc 子进程）：
  - `encode <wav> <out.at3> [--loop-start s] [--lufs -21] [--ch 2]`：ffmpeg 重采样到 44.1 kHz/s16/
    立体声（`aresample` 高精度 + 三角抖动）并做响度归一 → atracdenc raw → 按 §2.2 算式写 RIFF 头
    （d 缺省 4464，`--delay` 可覆盖；`--measure-delay` 用冲激往返自动测）。**loop-start 换算**：
    smpl.start = round(start×44100) + d + 184。
  - `inspect <at3>`：打印 fmt/fact/smpl/帧数，并按算式反推 (T, d, S)、校验固件规则（§2.2）。
  - `verify <at3> <src.wav>`：ffmpeg 解码 → 包络互相关 + LUFS/峰值 对照，输出 ncc 与响度差。
  - `pack`/`unpack` 不重复实现，复用 `databin.py`。
- `tools/emu/drives/bgm_probe.py`（把本次一次性 `probe_drive.py` + `analyze_dump.py` 正式化）：
  开 `DumpAudio` → 直入指定场景 → 按键序列 → 静置 → 关 `DumpAudio` → 互相关报告（含回绕时刻）。
  ppsspp.ini 改动务必 try/finally 还原。

### 4.3 build_disc 阶段

| 阶段 | 改动 |
|---|---|
| `sound`（新，排在 `pack` 之后） | ① 首次自 `assets/orig.iso` `umdiso extract` SOUND.BIN 到 `build/sound/orig/`，`databin unpack` 缓存；② 按 `[[sound]]` 校验 `layers/audio/*.at3`（`inspect` 规则 + sha256 与 source 对应）；③ APFS clone 到 `build/<profile>/sound_stage/`，按名 bisect 插入新成员（复用 `assemble_stage` 的有序插入）；④ `databin pack` → `build/<profile>/SOUND.BIN` + 指纹 |
| `disc` | 多拷一个 SOUND.BIN 进 `build/<profile>/game/PSP_GAME/USRDIR/` |
| `iso` | `pairs` 多一对 `(/PSP_GAME/USRDIR/SOUND.BIN, build/release/SOUND.BIN)`；新增断言⑤：SOUND.BIN 成员集合 = 原 99 + manifest 声明的新成员，**原成员逐字节未动**（本项目不改原曲），指纹与本次 sound 阶段一致 |
| `layers.py check` | 新增 `_check_sound`：artifact 存在、头部过 `inspect` 规则、成员名不与原 99 冲突、按名排序合法 |

无 `[[sound]]` 条目时 `sound` 阶段空转、`iso` 不替换 SOUND.BIN——与 `[eboot]` 缺省行为同型。

### 4.4 测试

- `tests/test_at3p.py`：头部生成函数对 (T, d, S) 的算式钉死；给定原版 `bgm_20_b` 的 (T, d, S) 能
  逐字节重建其 fmt/fact/smpl（`local_assets` 标记，缺 SOUND.BIN 自动 skip）；`inspect` 对 99 原曲
  全过、对故意坏头（fmt 40 B / 无 smpl / sr 48000）全拒。
- `tests/test_build_disc_sound.py`：有序插入位置、断言⑤在"原成员被改"时拒绝。

## 5. Lua 消费

- 谢幕章脚本 `layers/scripts/snr_finale.lua` 现用 `bgm_19_x`（fin-10 天台）、`bgm_20_c`（fin-40
  文化祭）、`bgm_20_b`（fin-50 结尾）、`loop_6`（蝉声环境音）。新曲就是把对应处的
  `cPlayBGMWrap(cGetFileName("bgm", "bgm_19_x"))` 换成 `cGetFileName("bgm", "bgm_fin_1")`——
  一行改动；`cPlayBGMWrap` 的同名去重、`cStopBGMWrap` 的 30 帧淡出、系统 BGM 音量都自动适用。
- 不循环的一次性曲用 `cPlayBGMNotLoop`（slot 0）或 `cPlayOneshotMusic`（slot 1，与蝉声互斥）；
  两者都仍要求文件带 `smpl`（loop=0 也查）。
- 不需要登记 vms id、不碰 snr_common、不改基座、不涉及存档兼容（无新持久化状态）。

## 6. 验证方案

1. 离线：`at3p.py verify`（ncc ≥ 0.95、响度差 ≤ 0.5 LU）+ `inspect` 规则全过。
2. 模拟器：`bgm_probe.py` 直入目标场景，确认起播、回绕时刻 = 预期（整曲：曲长；局部：曲长−S），
   日志无 `E[Atrac]`。发布 ISO 再跑一次 `release_iso.py` 冒烟。
3. **实机**：用户在 CFW PSP 上用测试 ISO 听一遍（起播、无爆音/断流、循环点）。这是 atracdenc
   比特流唯一无法在本机替代的验证；建议在正式接线前先出一张只换 `bgm_19_x` 的探针盘。

## 7. 风险与对冲

| 风险 | 对冲 |
|---|---|
| 真机 ME 解码器拒绝/劣化 atracdenc 实验性 AT3+ 流 | 早做实机探针（§6.3）；备选 at3tool（§8 b）；再备选 352 kbps 帧（同样已在模拟器过） |
| atracdenc 128 kbps 音质低于 at3tool | 试听 + 可按素材调 `--advanced` 参数；实在不行升 2048 B 帧（352 kbps，文件 ×2.75，引擎 128 KiB/64 KiB 流缓冲在模拟器无异常，真机 UMD 吞吐 1.4 MB/s 远高于 44 KB/s） |
| 编码延迟 d 估错 → 循环点偏移 ≤ d 采样（0.1 s） | `--measure-delay` 冲激法自动测；局部循环点用模拟器录音核对回绕时刻 |
| SOUND.BIN 变大 → ISO 尾部平移 | `umdiso` 已支持并 `verify --against`；DATA.BIN 早已如此 |
| 成员名排序破坏二分查找 | 复用 `assemble_stage` bisect + 断言⑤ |

## 8. 待用户拍板

- **a. 落点与循环形态**：哪 1–2 个场景换曲（fin-10 天台 / fin-40 文化祭 / fin-50 结尾 / 蝉声
  之外新增环境层？）；每段素材是整曲循环、还是"前奏 + 循环段"（给出循环起点秒数）、还是一次性不循环。
- **b. 编码器**：用户是否持有 Sony at3tool？有则金标准路线，无则 atracdenc-744（推荐，已验证到模拟器）。
- **c. 入库策略**：推荐 **PCM 原件不入库（`assets/audio/`）、编码定稿 `.at3` 入库（`layers/audio/`）**
  ——定稿是发布字节的唯一真源，不依赖编码器版本可复现；manifest 钉两边 sha256。替代：只入库
  WAV 的 sha256、`.at3` 每次重编（省仓库体积，但 atracdenc 升级会漂移）。
- **d. 实机**：是否有 CFW PSP 可听测试盘。
- **e. 素材本身**：采样率/位深/声道任意（ffmpeg 重采样）；若是单声道，建议编成单声道 AT3+（原版
  `loop_22` 先例），文件减半。

## 9. 实施步骤（供 writing-plans 展开）

1. `tools/build_atracdenc.sh` + `tools/atracdenc-744.patch`（钉 commit）。
2. `tools/at3p.py`（encode/inspect/verify）+ `tests/test_at3p.py`（含 99 原曲算式回归）。
3. `layers/manifest.toml` `[[sound]]`/`[sound]` + `layers.py check` 的 `_check_sound`。
4. `build_disc.py`：`sound` 阶段、`disc`/`iso` 接线、断言⑤、provenance 记 SOUND.BIN 指纹。
5. `tools/emu/drives/bgm_probe.py`。
6. 素材落地：编码 → `layers/audio/` → 改 `snr_finale.lua` 一行 → 模拟器探针 → 测试 ISO 实机听。
7. 文档：`docs/ops/disc-pipeline.md` 加"第五类改动：新增音频"与阶段表行；CLAUDE.md 一句话
   （SOUND.BIN 同构 pack、AT3+ 专用、smpl 必需）。

## 附：探针台账（`build/sound/`，全部一次性）

| 产物 | 命令/说明 |
|---|---|
| `SOUND.BIN` | `umdiso.py extract assets/orig.iso /PSP_GAME/USRDIR/SOUND.BIN` |
| `unpacked/` + `SOUND.repack.BIN` | `databin.py unpack/pack`，`cmp` 逐字节相同 |
| `bgm_19_x/20_b.at3`、`loop_6.at3` | 抽出的原曲；`ffprobe` 确认 atrac3p 44.1k 立体声 128 kb/s |
| 头部统计脚本（内联） | 99/99 fmt 一致（1 首单声道）；fact/smpl 算式 99/99 成立 |
| `../atracdenc/` | clone @ cb17070 + submodule + `CMAKE_OSX_ARCHITECTURES=arm64` + `BitStream(out, 744)` |
| `test_in.wav` | `bgm_20_b` 解码为 44.1k s16 立体声（编码器输入样本） |
| `test_at3p.raw` / `test_at3p_wrapped.at3` | 2048 B/帧；`wrap_at3p.py` 包头；ffmpeg 解码 352 kb/s，响度与输入一致 |
| `test_at3p_native.at3` | atracdenc 原生 RIFF：fmt 40 B（固件 <0x34 拒绝）、无 smpl |
| `test_at3.at3` / `test_at3_default.at3` | ATRAC3：`--bitrate 132` 出 424 B 帧 ffmpeg 不认；缺省 = 132300 bps/384 B 正确 |
| `impulse.wav` → `imp_*` | 冲激法：AT3+ 延迟 4464（2048 与 744 帧长相同），ATRAC3 延迟 1162 |
| `probe_at3p.at3` / `SOUND.at3p.BIN` / `probe_at3p/` | 352 kbps 探针：ncc 0.94、53.10 s 回绕、零报错 |
| `probe_at3.at3` / `SOUND.at3.BIN` / `probe_at3/` | ATRAC3 探针：`WRONG_CODECTYPE` |
| `test_744.raw` / `probe_744.at3` | 128 kbps：851880 B 与原 `bgm_20_b` 同大小；fmt 与原版逐字节相同（avg 取 ceil） |
| `probe_744_loop.at3` / `SOUND.744.BIN` / `probe_744/` | 128 kbps + S=10 s 局部循环模拟器探针：ncc 0.937，回绕点续播自第 10 s，零报错（§3 表末行） |
| `probe_drive.py` / `analyze_dump.py` / `wrap_at3p.py` | 驾驶、互相关分析、包头三个一次性脚本；正式化后进 `tools/` |

模拟器配置 `~/.config/ppsspp/PSP/SYSTEM/ppsspp.ini` 的 `DumpAudio` 探针后已复位为 False；
`build/test/game/…/SOUND.BIN` 已还原为原版；`~/.config/ppsspp/PSP/AUDIO/` 录音已清（副本在各 `probe_*/dump.wav`）。
