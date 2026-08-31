# 中文化测试盘管线首次贯通（2026-08-31）

`译文注入 → luac 回编 → 字体替换 → 烤字回填 → DATA.BIN 重封包 → PPSSPP 目录引导`
全链路跑通，游戏内确认中文正文、中文 UI 图、中文字体渲染，模拟器日志零异常
（仅剩 2 条原版同样存在的 HLE 噪声）。ISO 重打包按既定路线**不做**。

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

## 当前状态与已知缺口

- `build/game`（中文化盘目录）与 `build/game_orig`（原版对照盘）均可引导。
- **槽 1（9px ruby/小字）仍是日文字体**：`snr_common.lua:5009` 未改，
  `build/font/lxgw09.pgf` 已产出但未注入——中文拼音 ruby 未验证。
- 39 条 tr_line 字符串无译文（探索场景 sceneName 18、章节 sectionName 8、
  `snr_novel:557` 一条、s5/s7f 动态 id vms 约 24 行），游戏内仍显示日文。
- 谢幕章新资产（新 lua/新 gim）尚未纳入 `build_disc.py`。
- 烤字量化：212 张 MSE>15，最大 55（cutin/tut_*，16 色板），需目检定夺。
- 行宽溢出：中文长行是否溢出消息窗尚无机械检查，需逐章目检或加检测器。
