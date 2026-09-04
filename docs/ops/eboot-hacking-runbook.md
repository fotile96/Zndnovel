# EBOOT 逆向与补丁 runbook（写给后续 Claude 会话，不是给人读的）

目标读者是一个新开的会话：没有本次对话的记忆，但有同样的工具（IDA MCP、PPSSPP 双构建、
本仓库工具链）。按本文走，可以在几十分钟内回到"能读引擎代码、能改字节、能在模拟器里
验证"的状态。事实依据与推导过程在 `docs/ops/eboot-kinsoku-research-2026-09-04.md`
（下称"研究记录"），本文只讲**怎么做**与**哪里会翻车**。

## 0. 三条硬规矩（先读）

1. **Allegrex 没有整数 `mul`**（SPECIAL2 只有 `halt`）。乘常数用 `sll`+`addu`/`subu` 拼；
   ISA 的权威是 `~/ppsspp/Core/MIPS/MIPSTables.cpp`，改指令前 `grep -n '"movn"'` 之类
   确认存在。有的：`movz/movn`（SPECIAL 0x0A/0x0B）、`madd/msub`、`clz/clo`、`ext/ins`、
   `seb/seh`、`max/min`。IDA 拒绝解码 ≠ 实机一定没有，但两者都拒绝就别用。
2. **替换带重定位条目的字必须同时改重定位表**。PRX 型 ELF 装载时按重定位段
   （section type 0x700000A0）改写 `jal/j`（R_MIPS_26）与 `lui/addiu` 对（HI16/LO16）
   所在的字——你把 `jal` 换成别的指令，装载器照样往低 26 位加基址（实测把
   `subu s2,s2,t4` 变成 `subu s4,v1,t4`）。枚举脚本见 §5.3；处理办法是把该条目类型
   改成 R_MIPS_NONE(0)（`layers/eboot/*.toml` 的 `off =` 补丁）。反过来：新增一条 `jal`
   而没有重定位条目，目标就是未加基址的地址 → 跳飞。**新代码只能用 PC 相对分支
   （`b/beq/bne…`）和现成的 `jal` 位置。**
3. **字形推进 `advanceH>>6` 截断成整数像素**（`font_draw_string` 0x5A60）。任何"半像素"
   设计都不存在；字体步进与引擎常数都取整数 px。

## 1. 取得可分析的 EBOOT（一次性，已做，本机有）

- 纯净解密源：`assets/EBOOT.dec.elf`（584689 B，sha256 `8737f1d3…`，登记在
  `layers/manifest.toml [eboot].sha256`）。不在 git 里。丢了按下面重做。
- 重做：ISO 里 `BOOT.BIN` 是全零，`EBOOT.BIN` 是 `~PSP` 加密容器。**只能用 PPSSPP SDL App
  构建 dump**（headless 硬置 `iDumpFileTypes = 0` 且不读 ini）：
  ```bash
  INI=~/.config/ppsspp/PSP/SYSTEM/ppsspp.ini
  sed -i '' 's/^DumpFileTypes = .*/DumpFileTypes = 3/' $INI      # bit0 EBOOT, bit1 PRX
  ~/ppsspp/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL --graphics=software $PWD/assets/orig.iso
  # 十几秒后 pkill -x PPSSPPSDL；产物 ~/.config/ppsspp/PSP/SYSTEM/DUMP/NPJH50279_EBOOT.BIN
  sed -i '' 's/^DumpFileTypes = .*/DumpFileTypes = 0/' $INI
  head -c 584689 ~/.config/ppsspp/PSP/SYSTEM/DUMP/NPJH50279_EBOOT.BIN > assets/EBOOT.dec.elf
  ```
  dump 按原文件长度写出，尾部 351 B 是容器残渣，截到 `~PSP` 头里的 `elf_size`（584689）。
- 三套地址：**IDA/ELF VA**（基址 0）；**文件偏移 = VA + 0xC0**（PH0 offset 0xC0，vaddr 0，
  只对 PT_LOAD 内容成立，重定位表等段外字节用文件偏移）；**运行时 = VA + 0x08804000**
  （PPSSPP 调试器、断点、`cpu.getReg` 看到的都是这个）。
- 随盘 `module/libfont.prx`（`assets/`/`build/eboot/libfont.dec.prx`）是 Sony sceLibFont，
  游戏用 `sceKernelLoadModule` 显式装载并从它导入 8 个 `sceFont*`；PPSSPP 对它一律 HLE
  （`Core/HLE/HLE.cpp` 的 `g_moduleMeta`），要跑真模块设 ini `DisableHLEFlags = 1`（bit0）。

## 2. 打开 IDA（MCP idalib）

```
idb_open input_path=/Users/fotile96/Zndnovel/build/eboot/EBOOT.dec.elf preferred_session_id=eboot idle_ttl_sec=3600
```
IDB `build/eboot/EBOOT.dec.elf.i64` 已带全部命名与注释（不在 git；丢了就重开、按 §3 的表
重命名）。**注意 IDB 里的字节不是纯净的**：2026-09-04 把 ruby-p5 层的 A/B/C 三段直接打在
IDB 里验证（a4dc–a504、a508、5810–581b），0x5808 已还原；禁则表没打。要看纯净字节用
`assets/EBOOT.dec.elf` 或 `eboot_patch.py check`。

MCP 工具的脾气（实测）：
- `patch_asm` 不会汇编 MIPS（一律 "Failed to assemble"）。改字用 `patch`（十六进制字节）；
  然后 `define_code`（尤其原字是别的东西时）、`force_recompile` 再 `decompile`。
- `decompile` 把跨调用存活的 `$t*` 当作被破坏（显示成未初始化的 vN）——是反编译器的
  ABI 假设，不是你的错；实机语义看 `disasm` 与 §5.1 的调用者寄存器表。
- 字符串缓存不含 UTF-8 中日文串：`find_regex`/`get_string` 对 `」`、禁则表都失败。找 UTF-8
  常量用 Python 读文件（§5.3 的 `dump()` 例子），再 `xrefs_to` VA。
- `xrefs_to` 对 `lui/addiu` 生成的地址引用有效（PSP 重定位没处理但基址 0 自洽）。
- `search_text` 是对渲染后的列表做正则，慢但可用；`insn_query mnem=` 是前缀匹配
  （`mul` 会匹到 `mul.s`）。
- `disasm` 按函数 + 指令偏移分页：`offset = (目标VA − 函数起点)/4`。

## 3. 引擎地图（都已在 IDB 命名）

消息管线：`lua_msg` 0x6890 → `msg_set_text` 0x9C64（backlog 500 B/槽 ×999、正文缓冲
`msg_text_buf` 0x1DD440 共 500 B、`【名】` 解析）→ 每帧 `main_loop` 0xAA28 →
`msg_layout_step` 0xA114（打字机+禁则+ruby，规则见研究记录 §3）→ `font_draw_string` 0x5698
（UTF-8→UTF-16、sceFont 逐字、3×3 描边到 outline 层、advance>>6 推进、空格跳过+推进 5 px）。

| VA | 名 | 备注 |
|---|---|---|
| 0x9040 | `lua_register_natives` | 60 个 Lua 原语的名字→函数表；找任何原语从这里 |
| 0x9AA4 | `msg_read_utf8_char` | 按首字节取 1–4 B |
| 0x11800 | `strstr_` | 禁则判定 |
| 0x663E0 / 0x66462 | `kinsoku_line_head` / `_tail` | 130 B / 34 B 区间，现由 layers/eboot/kinsoku.toml 覆盖 |
| 0x1DD638/63C/640 | `msg_text_pos` / `msg_col` / `msg_line` | 打字机状态 |
| 0x1DD634/635/636 | `msg_active` / `msg_text_end` / `msg_page_wait` | |
| 0x1DD648 | `backlog_entries_500b` | |
| 0x28FF88 | `font_slots_4x300` | 4 槽 × 300 B：[0] sceFont 句柄 [1] 内存 [2] 长度 [3..] SceFontInfo |
| 0x28FF84 | `font_lib_handle` | `font_lib_init` 0x4E3C：sceFontNewLib numFonts=4，alloc 回调 `sub_50BC`→`heap16_alloc` 0x4D1C |
| 0x4FC4 / 0x50F4 / 0x4A5C | `font_slot_load` / `font_print_layers` / `font_clear_layers` | fontLoad/fontPrint/fontClear 的实现 |
| 0x1124 / 0x1248 / 0x1380 | `pack_index_lookup` / `pack_file_size` / `pack_read_async` | DATA.BIN 索引 60 B/项 strcmp 二分；找不到回退散文件 |
| 0x1EF0 / 0x2F40 | `layer_create(w,h)` / `layer_blit_color` | 正文层 512×111 贴 (0,165)，名牌 192×22 贴 (0,142) |
| 0x65280–0x652B0 | `sceFontGetFontInfo` … `sceFontGetCharInfo` | 导入桩（`jr ra; nop`），NID 见研究记录 §6.2 |

版面常数：格 17 px、行距 26 px、25 格/行、4 行/消息（第 5 行起停滞）、ruby 起点
`17·col + (17·nb − 5·units)/2 + 4`（P=5 来自 `build_font.RUBY_PITCH_PX`）。

## 4. 改引擎的正规通道：`layers/eboot/*.toml`

```toml
why     = """必填：为什么改"""
profile = "release"            # 两剖面都打；test 只在 test
[[patches]]
va   = "0xA508"                # 段内字节用 VA
from = "c0 30 12 00"           # 原字节锚点（长度=区间）
to   = "80 30 12 00"           # 或 str = '…'（UTF-8 + NUL，零填充到区间长）
note = "一句话"
[[patches]]
off  = "0x735F0"               # 段外字节（重定位表）用文件偏移
from = "f8 a4 00 00 04 00 00 00"
to   = "f8 a4 00 00 00 00 00 00"
```
登记：`layers/manifest.toml [eboot].order`（与目录文件一一对应，区间不得重叠）。命令：
```bash
uv run python tools/eboot_patch.py show
uv run python tools/eboot_patch.py check assets/EBOOT.dec.elf     # 全 pristine
uv run python tools/eboot_patch.py apply assets/EBOOT.dec.elf /tmp/x.elf
uv run python tools/layers.py check                                 # 锚点闸 + 排版校验闸
uv run python tools/build_disc.py --profile test --mode font --stage eboot,disc   # 只换引擎
```
`build_disc.py` 的 `eboot` 阶段产 `build/<profile>/EBOOT.BIN`，`disc` 覆入 game 目录，
`iso` 断言④重算核对后与 DATA.BIN 一起就地替换进 ISO。测试：`tests/test_eboot_patch.py`
（合成 ELF + 真源锚点 + 常数与字体钉合）。

## 5. 一次 hack 的标准流程

### 5.1 定位与读懂
1. 从**字符串/原语名**进：`lua_register_natives` 里 `xrefs_to` 原语名串得到 C 函数；UTF-8
   常量用 Python 扫文件（file = va + 0xC0）再 `xrefs_to`。
2. `decompile` 目标函数，立即 `rename` 关键函数/全局并 `set_comments`，`idb_save`。
   反编译里 `byte_270000[v + (__int16)&xxx]` 这种是 PSP 编译器的 gp/hi16 寻址假象，看
   真实全局用 `disasm`。
3. 被调函数的寄存器使用要**逐条看 disasm**（`strcat_` 只碰 a0–a5/s0/v0/ra，`strcpy`
   只碰 a0–a6），决定哪些 `$t*` 能跨调用存活。PSP 寄存器名：`$8–$11 = a4–a7`，
   `$12–$15 = t4–t7`（IDA 与 PPSSPP 一致）。

### 5.2 设计补丁（先纸上）
- 只在现有指令槽里腾挪：合并重复路径（如两条 strcat 分支用 `movn` 选缓冲）、把 `move`
  折进别的指令、分支延迟槽放有用指令、利用"下一块的第一条指令"当延迟槽（要求它无害）。
- 常量改法优先（`sll` 移位量、`addiu` 立即数、表字符串）；需要新逻辑再重排一段直线代码。
- 算式要按引擎的整数语义重算：`>>6` 截断、带符号 `/2` 是 `sra;srl 31;addu;sra` 惯用式。
- 校验器（`tools/msg_layout_check.py`）的模型必须同步改：它复刻的就是这些规则。

### 5.3 重定位与编码
枚举补丁区间内的重定位条目（改 `ranges`）：
```python
import struct
d=open('assets/EBOOT.dec.elf','rb').read()
shoff=struct.unpack_from('<I',d,32)[0]; shentsize,shnum=struct.unpack_from('<HH',d,46)
ranges={'A':(0xa4dc,0xa508)}
for i in range(shnum):
    _,t,_,_,off,size=struct.unpack_from('<6I',d,shoff+i*shentsize)
    if t!=0x700000A0: continue
    for j in range(size//8):
        r_off,r_info=struct.unpack_from('<II',d,off+8*j)
        for n,(lo,hi) in ranges.items():
            if lo<=r_off<hi: print(n,f'entry@file {off+8*j:#x} r_offset={r_off:#x} type={r_info&0xff}')
```
类型 4=R_MIPS_26、5=HI16、6=LO16、2=32。段内 UTF-8 常量表区间没有条目（实测）。

手工编码（小端，写进 toml 时按字节顺序）：
- R 型：`(rs<<21)|(rt<<16)|(rd<<11)|(sa<<6)|funct`。`addu 0x21`、`subu 0x23`、`or 0x25`、
  `sll 0x00`（rs=0）、`srl 0x02`、`sra 0x03`、`movz 0x0A`、`movn 0x0B`。
- I 型：`(op<<26)|(rs<<21)|(rt<<16)|imm16`。`addiu 9`、`sltiu 0x0B`、`xori 0x0E`、`ori 0x0D`、
  `lw 0x23`、`lb 0x20`、`lhu 0x25`、`sw 0x2B`、`beq 4`、`bne 5`；分支偏移 = (目标 − (pc+4))/4；
  `b` = `beq zero,zero` = `0x1000xxxx`。
- **每个编码都拿同形原指令反证**：`get_bytes` 取原文件里同 mnemonic/同寄存器形状的字，
  用公式算一遍必须相等（本次 9 条全中才放行）。IDA `disasm` 二次核对，PPSSPP
  `memory.disasm`（`cli.disasm(addr, n)`）三次核对——最后这个才是装载后的真相。
- 本次已验证过的字：`sll a2,s2,2 = 80 30 12 00`、`addiu s6,s6,5 = 05 00 d6 26`、
  `b +145 = 91 00 00 10`、`move a0,zero(or) = 25 20 00 00`、`movn a0,s4,s0 = 0b 20 90 02`、
  `movz t4,zero,s0 = 0a 60 10 00`、`sltiu t4,v0,3 = 03 00 4c 2c`、`subu s2,s2,t4 = 23 90 4c 02`、
  `xori t5,s0,1 = 01 00 0d 3a`、`addu s1,s1,t5 = 21 88 2d 02`。

### 5.4 IDB 内验证
`patch` 字节 → `define_code` 区间 → `force_recompile` → `decompile` 看算式是否如愿 →
`set_comments` 记下"已打补丁/原字节在哪"。这一步只证明**静态语义**，证明不了重定位与
实机行为。

### 5.5 模拟器验证
1. 写探针页：`tools/testboot.py` 的 `FONT_PAGES`（每页一条 msg，`[label] ` 前缀占格；
   `_n` 只等键不换行；**每页 ≤ 4 行**，否则引擎停滞、后面的页全丢——探针 K3 初版踩过）。
   列数用 Python 数好，语料外字会画成 `_`（alt char），不影响格数。
2. 建盘并驾驶：
   ```bash
   uv run python tools/build_disc.py --profile test --mode font       # 首次全量；只改引擎时 --stage eboot,disc
   uv run python tools/emu/drives/font_probe.py                       # 每页截图 build/emu/drives/font_probe/pNN.png
   ```
   看图用 Read 工具；小字先用 PIL 裁 (0,160,480,272) 放大 3 倍再看。
3. **PPSSPP 宿主崩溃（SIGSEGV）= 客体访问了坏地址**：本机 fastmem 没有异常处理器
   （日志 "Exception handler not implemented"）。临时把 ini 的 `FastMemoryAccess = False`、
   `IgnoreBadMemAccess = False` 再跑，就不崩了、可以下断点；跑完改回 True。崩溃栈在
   `~/Library/Logs/DiagnosticReports/PPSSPPSDL-*.ips`（frame 0 在 JIT 区、x0 = 基址+客体地址）。
4. 断点/单步/读寄存器：`tools/emu/drives/regtrace.py`（§5.6）。要点：`cpu.stepInto/stepOver`
   **没有票据回包**，得 `fire` + `wait_broadcast("cpu.stepping")`；`memory.read` 对无效地址
   抛 `EmuError("Invalid address")`——这本身就是"寄存器被砸"的证据。
5. 若怀疑某段补丁：`eboot_patch.load_layer` 取各 patch 自己组合子集写临时 ELF，直接
   覆盖 `build/test/game/PSP_GAME/SYSDIR/EBOOT.BIN` 复跑（不必重建盘）。

### 5.6 regtrace 用法
```bash
uv run python tools/emu/drives/regtrace.py --bp 0xA4DC --cond "s0 == 1" \
    --regs pc,a0,v0,s0,s1,s2,s4,t4,t5 --read s5:16 --read s4:24 --steps 12
```
先按 CIRCLE 推进到断点命中（`--presses`），打印寄存器、按 `--read` 转储内存，再单步
`--steps` 条（jal 自动 stepOver），每步打印下一条反汇编——一次跑完就能对照 §5.3 的编码
看每条指令实际做了什么。

### 5.7 收尾
- 研究记录追加一节（发现、地址、原字节、教训），`CLAUDE.md` 只放硬规矩与指针。
- `uv run pytest tests/test_eboot_patch.py tests/test_msg_layout_check.py -q` 与
  `tools/layers.py check` 过；提交按"工具 / 层 / 文档"分开。
- 实机（CFW）验证仍是最后一道：真 libfont 与 PPSSPP HLE 不是同一份代码。

## 6. 已知陷阱清单（每条都实际踩过）

| 现象 | 根因 | 处理 |
|---|---|---|
| IDA 不认新指令、实机保留指令异常 | Allegrex 无 `mul` | 用 sll/addu 拼；查 MIPSTables.cpp |
| 补丁后 ruby 全无、fastmem 崩溃、单步看到指令"变了" | 替换了带 R_MIPS_26 的 `jal` 字 | 重定位条目改 R_MIPS_NONE（`off =` 补丁） |
| 含空格的串在空格处截断 | 空格走字形路径 → `sceFontGetCharInfo` 以 0 字节调分配回调失败 | 空格保持跳过，改为 `addiu s6,s6,P` 推进 |
| 4.5 px 步进"不生效" | `advanceH>>6` 截断 | 步进取整数 px，字体与引擎常数一致 |
| 探针后半页全部丢失 | 某页 > 4 行，引擎停滞 | 页设计 ≤ 4 行；校验器 page-overflow |
| `find_regex`/`get_string` 找不到日文串 | IDA 字符串缓存不含 UTF-8 | Python 扫文件 |
| `patch_asm` 全失败 | 后端不支持 MIPS | 手工编码 + 反证 |
| headless dump 出不来 EBOOT | headless 硬置 dump 位 0 | 用 SDL App |
| `cpu.stepInto` 超时 | 无票据回包 | fire + wait_broadcast |

## 7. 相关文件索引

- 研究记录：`docs/ops/eboot-kinsoku-research-2026-09-04.md`（§1 dump、§2 管线、§3 规则、
  §6 ruby/字体、§7 补丁与三次实测、§8 校验器）
- 补丁层：`layers/eboot/kinsoku.toml`、`layers/eboot/ruby-p5.toml`；工具 `tools/eboot_patch.py`
- 校验器：`tools/msg_layout_check.py`（`--show <id>` 看版面）
- 字体：`tools/build_font.py`（`RUBY_PITCH_PX`、`RECIPE`）、`tools/pgf_inspect.py`
- 模拟器：`tools/emu/drives/{font_probe,regtrace}.py`、`tools/emu/client.py`、
  `docs/ops/ppsspp-local-setup-2026-08-31.md`
- 管线：`docs/ops/disc-pipeline.md`（eboot 阶段、各道闸）
