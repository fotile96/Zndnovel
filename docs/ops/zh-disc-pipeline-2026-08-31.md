# 中文化测试盘管线首次贯通（2026-08-31）

`译文注入 → luac 回编 → 字体替换 → 烤字回填 → DATA.BIN 重封包 → PPSSPP 目录引导`
全链路跑通，游戏内确认中文正文、中文 UI 图、中文字体渲染，模拟器日志零异常
（仅剩 2 条原版同样存在的 HLE 噪声）。

**2026-09-01 追加 `iso` 阶段**（原版 ISO 到位后）：`tools/umdiso.py` 就地替换产出
`build/dist/game_zh.iso`，PPSSPP 直接引导该 ISO 成功（游戏 ID `NPJH50279` 识别正常、
ERROR 日志 1 条与原盘同源）。详见本文末节。

## 一条命令

```bash
uv run python tools/build_disc.py            # 全阶段
uv run python tools/build_disc.py --stage lua,stage,pack,disc   # 只改译文时
uv run python tools/emu/playthrough.py --disc build/game --out build/emu/play_zh
```

阶段：`lua`（注入+回编）→ `gim`（烤字回填）→ `font`（字体）→ `stage`（组装封包树）
→ `pack`（回封）→ `disc`（刷盘目录）→ `boot`（引导冒烟）。

## 各环节实况

| 环节 | 工具 | 实测结果 |
|---|---|---|
| 译文注入 | `tools/inject_lua.py` | vms 16749/16749、extra 826/829（3 条裁定留空），行号不变 |
| lua 回编 | `~/pyluadec-refactor/build/luac_sz4 -s` | 229/229 编译通过，头字节 = PSP ABI |
| 字体 | `tools/build_font.py` + pgftool | 3382 码位裁剪版 17px=490KB / 9px=274KB |
| 烤字 | `tools/build_disc.py --stage gim` | 573 张模板回填，量化损耗 MSE 中位数个位数 |
| 回封 | `tools/databin.py pack` | 9232 成员，396MB |
| 引导 | `tools/emu/` | 中文渲染正常，ERROR 日志 2 条（与原版同） |

## 三个关键发现（都花了实测代价）

### 1. 封包文件表必须严格按名有序——引擎二分查找

原包 9231 项文件表**严格按成员名升序**。新增成员若破坏有序性，引擎按名查找落空，
现象是 `sceFontOpenUserMemory(addr=0, size=-1)` 连报（169 次）、字体不生效而正文
退化到后备渲染。三次对照实验定论：

| 实验 | 新成员位置 | 结果 |
|---|---|---|
| E1 | 追加表尾（9232） | ✗ 字体错误 ×169 |
| E2 | 插到 `pgf/tsukuminpro_e_17.pgf` 处（1557） | ✗ 同样失败——该位仍破坏有序性 |
| E2' | 不新增成员，改用既有成员名承载新字体 | ✓ 零错误（可作应急退路） |
| E3 | **按名排序位（1556）** | ✓ 零错误，中文正常 |

`build_disc.py` 现按 `bisect` 插入并在写盘前断言全表有序。**谢幕章新增
`crd_201..207`/`title_14_a`/`snr_finale.lua` 时同理适用**。

### 2. arm64 Mac 上可以直接产 PSP ABI 字节码

`~/pyluadec-refactor/build/luac_sz4` = 打了序列化宽度补丁（`native/patches/0001-serial-sizet.patch`，
`size_t`→`lua_SerialSizet`）的 vanilla Lua 5.1.5，在 64 位宿主上输出 32 位宽度的
luac。头字节 `1b4c 7561 5100 0104 0404 0800` 与原包逐字节一致。无需 32 位 Linux、
无需 docker、无需 wasm。路径可用 `SNDL_LUAC` 覆盖。

### 3. 字体体积与渲染

全字库 43478 字形的 17px PGF 有 5.3MB；按语料裁剪（译文全字集 ∪ 原文残留字 ∪
ASCII ∪ 全角形 ∪ 假名 ∪ 拼音声调 ∪ 控制符 = 3382 码位）后 490KB。裁剪本身不是
E1 故障的原因（E3 证明位置才是），但体积回到原字体量级更稳妥，且 `build_font.py`
可复跑。

## 模拟器侧新增能力

- `tools/emu/client.py`：`vram_screenshot()`——**`gpu.buffer.screenshot` 在本机
  两种后端都答 `Could not download output`**（CPU 断住时 GE 线程不服务回读），
  改为软渲染下直读模拟 VRAM `0x04000000`（stride 512、RGBA8888），稳定可用。
  `break_cpu()` 加了「已断住直接返回」的短路（否则空等广播必超时）。
- `tools/emu/playthrough.py`：固定操作脚本逐帧存图，同一脚本对两张盘各跑一次
  即得可逐帧对照的中日 A/B 组（软渲染 + 无随机源，可复现）。

### 4. ruby 注音：机制与居中规律（游戏内像素实测定论）

CLAUDE.md 悬置的两个前提都已验证：

**① ruby 用哪个字体槽 → 槽 1。** 探针把同一串文字分别用 `fontPrint(0,…)` 与
`fontPrint(1,…)` 画出来对照：槽 0（LXGW 正文）汉字/拼音声调/控制符全有；槽 1
原配日文 `tsukuminpro_e_09.pgf` 的简体字与声调元音**全是空白**。此时 ruby 里的
`jì yì` 显示成 `t oi` 式残缺——证明 ruby 走槽 1。故 `inject_lua.py` 在注入期把
`fontLoad(1,…)` 改指中文 9px 字体，拼音注音随即正常。

**② 声调元音有没有字形 → 有**，`āáǎà ēéěè īíǐì ōóǒò ūúǔù ǖǘǚǜ` 全部渲染。

**③ 居中规律（新发现，比前两条更要命）**：ruby 的水平定位由 C 侧 stub 计算，
实测规律是 **起点 x = 底字中心 − 注音字符数 × 全角步进 / 2**——按「每个注音字符
占一个全角格」估算，完全不看实际字形步进。于是半角拉丁必然左偏。

以底字「记忆」（x 8..37，中心 22.5）实测中心偏移：

| 注音串 | LXGW Regular 9px | LXGW **Mono** 9px | Mono + **全角步进派生** |
|---|---|---|---|
| `jìyì`（半角 4 字符） | −13.5 | −10.0 | **−0.5** ✓ |
| `jì yì`（含半角空格 5 字符） | −17.5 | −14.0 | −4.5 |
| `きおく`（全角假名） | −2.0 | −2.0 | −2.0 |
| `ｊｉｙｉ`（全角拉丁） | +3.5 | +3.5 | +3.5 |
| 前导 1/2/3 个半角空格 | −17.5 / −20.5 / −22.5 | 同左 | −4.5 / −9.5 / −9.5 |

两条结论：

- **补空格是反的**。空格计入字符数、起点继续左移，而空格不产生墨迹，所以整串
  越补越往左跑；补到 3 个时注音已被屏幕左缘截断。这条做了 4 个梯度，方向一致。
- **正解是让拼音字母的步进等于全角步进**。`tools/build_font.py` 的 `widen_latin()`
  用 fontTools 派生一份 TTF，把 80 个拉丁/声调码位的 `hmtx` 步进撑成 em 并把字形
  在框内居中，再喂给 `ttf_pgf`。9px 槽实测偏移 −13.5 → **−0.5**，注音恰好铺满
  两个底字的宽度。全库无任何 `fontPrint(1,…)` 调用，故加宽只影响 ruby，无副作用。

**给翻译轨的写法约定**：拼音注音**音节之间不要加空格**（`<记忆,jìyì>` 而非
`<记忆,jì yì>`）——空格步进仍是半角，一个空格就偏 4.5px。

## 5. 实机盘：ISO 就地替换（2026-09-01）

`uv run python tools/build_disc.py --stage iso` → `build/dist/game_zh.iso`。

**不重建镜像，只替换 DATA.BIN 并平移尾部**（为什么：模拟器递归走目录记录、不读
path table，而实机固件 isofs 按规范读 PVD+path table 且只认主卷名字，通用刻录
工具的 Joliet 改名/LBA 重排会造成"模拟器好好的、实机黑屏"——机理见
`umd-iso-repack-research-2026-08-31.md`）。

原盘布局（`umdiso.py list --gaps`）：DATA.BIN 在 LBA 80784、147774 扇区，其后还有
SOUND.BIN 等 6 个文件；盘内多处 padding 空隙（最大 37227 扇区）。新封包因回封不
压缩而涨到 396MB（+45831 扇区），故尾部必须平移。

验收证据：

| 检验 | 结果 |
|---|---|
| 恒等替换（用原内容替换 DATA.BIN） | 输出与原盘**逐字节相同** |
| 结构自检（PVD/目录树/path table 三方互证） | 通过（22 记录、4 表 28 条） |
| 全 16 个盘内文件内容比对 | 未动者 sha256 不变、DATA.BIN = 新封包 |
| 与原盘差异区间 | **只有 5 段**：PVD、3 个含移位记录的目录区、DATA.BIN 及其后 |
| PPSSPP 引导该 ISO | 进入运行态，ERROR 日志 1 条（与原盘同源） |

尾部平移量精确（SOUND.BIN 228560→274391 等全部 +45831），path table 本轮 0 处改动
（目录都在盘首、LBA 小于替换点），这是预期而非遗漏——`umdiso.py` 对目录在替换点
之后的一般情形也会改，合成盘测试覆盖了该路径。

**尚未做**：实机 CFW 验证（最终裁判）。另：若在意 ISO 体积（548MB→642MB），可让
`databin.py` 对未改动的 gim 成员沿用原包压缩字节（当年 `--reuse-original` 思路），
能把增量压到约 1/4；当前不做，因为"回封不压缩"是既定验收口径。

## 当前状态与已知缺口

- `build/game`（中文化盘目录）与 `build/game_orig`（原版对照盘）均可引导。
- **槽 1（9px ruby/小字）仍是日文字体**：`snr_common.lua:5009` 未改，
  `build/font/lxgw09.pgf` 已产出但未注入——中文拼音 ruby 未验证。
- 39 条 tr_line 字符串无译文（探索场景 sceneName 18、章节 sectionName 8、
  `snr_novel:557` 一条、s5/s7f 动态 id vms 约 24 行），游戏内仍显示日文。
- 谢幕章新资产（新 lua/新 gim）尚未纳入 `build_disc.py`。
- 烤字量化：212 张 MSE>15，最大 55（cutin/tut_*，16 色板），需目检定夺。
- 行宽溢出：中文长行是否溢出消息窗尚无机械检查，需逐章目检或加检测器。
