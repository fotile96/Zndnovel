# EBOOT 逆向：消息窗禁则（kinsoku）处理与中文标点行首问题（2026-09-04）

问题：中文译文里 `，……：）` 等标点会出现在消息窗行首。原因在引擎（EBOOT）——
`vms()`→`msg()` 之后的排版由 C 侧完成，其行头/行末禁则表只收日文标点。本文记录
取得可分析 EBOOT 的步骤、IDA 定位结果、排版规则全貌与修补方案候选。

## 1. 取得解密 EBOOT

- ISO 内 `PSP_GAME/SYSDIR/BOOT.BIN`（584689 B）是全零占位，不能用；`EBOOT.BIN`
  （585040 B）是 `~PSP` 加密容器（modname `secondnovel`，tag `0xD91613F0`，
  decrypt_mode 28，elf_size 584689）。
- 用 PPSSPP 的 dump 功能：**只能用 SDL App 构建**（headless 在 `Headless.cpp` 里硬置
  `g_Config.iDumpFileTypes = 0` 且不读 ini）。步骤：
  1. `~/.config/ppsspp/PSP/SYSTEM/ppsspp.ini` 的 `[General]` 里 `DumpFileTypes = 3`
     （bit0 = EBOOT，bit1 = PRX；`Core/ConfigValues.h` 的 `DumpFileType`）；
  2. `~/ppsspp/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL --graphics=software assets/orig.iso`
     跑十几秒后结束（模块加载时即落盘，同名文件已存在则跳过）；
  3. 产物 `~/.config/ppsspp/PSP/SYSTEM/DUMP/NPJH50279_EBOOT.BIN`、`NPJH50279_libfont.prx`；
  4. 改回 `DumpFileTypes = 0`。
- 产物是解密后的 **PRX 型 ELF**：`e_type=0xFFA0`、MIPS Allegrex（`e_flags=0x10A23001`）、
  段基址 0、PH0 text+rodata+data `0..0x6DA10`、bss `0x6DA40+0x2C2860`、PSP 重定位段
  `0x700000A0`；节名表已剥离。文件尾部多出 351 字节是 PPSSPP 按原文件长度 dump 出的
  加密容器残渣，`head -c 584689` 截掉即纯净 ELF。实机/模拟器装载基址 `0x08804000`，
  **IDA 里的地址 + 0x08804000 = PPSSPP 调试器地址**。
- 本机副本（gitignore）：`build/eboot/EBOOT.dec.elf`（原 dump）、`EBOOT.dec.trunc.elf`
  （截断版，md5 b857597a…）、`libfont.dec.prx`、IDA 库 `EBOOT.dec.elf.i64`（已命名下文
  全部符号，MCP 会话名 `eboot`）。VA 与文件偏移关系：`file = va + 0xC0`。

## 2. 消息管线（IDA 命名）

| VA | 名 | 作用 |
|---|---|---|
| 0x9040 | `lua_register_natives` | 用 `lua_pushcclosure`+`lua_setfield(GLOBALS)` 逐个注册 60 个原语（run/wait/msg/…/fontPrint/quit），名字表就在这里 |
| 0x6890 | `lua_msg` | `msg(id, text)`：id 取 double→u32；`msg_set_text(id, text, 0)`；`lua_yield` 交回主循环 |
| 0x9C64 | `msg_set_text` | ① 非回想模式时 `sprintf(&backlog[500*count], "%s", text)`——**backlog 每槽 500 B、共 999 槽、无长度检查**；② `sprintf(msg_text_buf, "%s", text)`——**正文缓冲 0x1DD440..0x1DD634 = 500 B**；③ 文本首字符为 `【` 时解析到 `】` 作说话人名（`/` 分成两段），名牌另行 `font_draw_string(0, 5, 2, …)`，正文从 `】` 之后起算列 0 |
| 0xAA28 | `main_loop` | 每帧：输入/自动/跳过/backlog 状态机；`msg_active` 时调 `msg_layout_step(0)`；backlog 翻页时用同一函数重排 500 B 槽 |
| 0xA114 | `msg_layout_step` | **打字机+排版**（见 §3） |
| 0x9AA4 | `msg_read_utf8_char` | 按首字节取 1/2/3/4 字节（`&0xC0==0xC0`→2，`&0xE0==0xE0`→3，`&0xF8==0xF0`→4）拷到栈上小缓冲 |
| 0x11800 | `strstr_` | 禁则判定就是 `strstr(表, 单字)`——子串查找，表是一条 UTF-8 长串 |
| 0x5698 | `font_draw_string` | UTF-8→UTF-16 后逐字 `sceFontGetCharInfo/GetCharGlyphImage` 画到 text 层，再 3×3 膨胀写到 outline 层；字内推进用 PGF 的 `advanceH>>6`（**比例宽**）；**ASCII 空格 0x20 直接跳过、不推进**；`\n` 换行 |
| 0x1FBC | 图形初始化 | 名牌层 `192×22` ×2、正文层 `msg_text_layer`/`msg_outline_layer` 各 **512×111** |
| 0x3180 | 合成 | 名牌层贴到屏幕 (0,142)，正文层贴到 **(0,165)** |

## 3. 排版规则（`msg_layout_step` 逐条）

状态：`msg_text_pos`（字节游标）、`msg_col`（列）、`msg_line`（行）。每帧取一个字符：

1. `_n` → 置 `msg_page_wait`，停下等键（翻页）；`_r` → `col=0, line++`。
2. `<base,ruby>` → base 串用字体槽 0 画在 `x=17*col+4, y=26*line+10`，ruby 串用
   **字体槽 1** 画在 `x=17*col+(17*n_base-9*n_ruby)/2+4, y=26*line+1`；`col += n_base`。
   （回答了 CLAUDE.md 里"ruby 用哪个字体槽"的存疑：槽 1，即 fonts.toml 改写后的
   `LXGWWenKai-Regular-09.pgf`；声调元音字形是否存在仍待实测。）
3. **行末禁则**：`if col == 24 and strstr(kinsoku_line_tail, ch): col=0, line++`——
   开括号不能落在第 25 格（最后一格），提前换行。
4. **行头禁则**：`if col >= 25: if not strstr(kinsoku_line_head, ch): col=0, line++`——
   行已满时，不在表内的字换行；**在表内的字不换行，直接画在第 26/27… 格（ぶら下げ悬挂）**。
5. `if line >= 4`：不再绘制、不消费字符——第 5 行以后的文字**静默丢失/停滞**，脚本必须
   保证每页 ≤ 4 行（原作靠作者手工 `_n`）。
6. 正文字符：字体槽 0，`x=17*col+4, y=26*line+10`，`col++`。**每个 UTF-8 字符恒占一格
   17 px**（含 ASCII、空格），行距 26 px；25 格 = 4..429 px；悬挂格 26/27/28 =
   429..480 px，仍在 512 宽的层内、也在屏幕内（原作 `。」` 就会悬挂两格）。

禁则表（.rodata，只有 `msg_layout_step` 引用，指针由 0xA290/0xA298+0xA2A0 的
`lui/addiu` 生成，带 PSP HI16/LO16 重定位，装载时只是加基址）：

| VA | 文件偏移 | 内容 | 容量 |
|---|---|---|---|
| 0x663E0 | 0x664A0 | 行头禁则 `｝〕〉》」』】〟’”ヽヾーァィゥェォッャュョヮヵヶぁぃぅぇぉっゃゅょゎ‐＝～？！・、。`（43 字 ×3 B = 129 B + NUL） | 到 0x66461 止，**129 B** |
| 0x66462 | 0x66522 | 行末禁则 `｛〔〈《「『【〝‘“`（10 字 = 30 B + NUL，后补 3 B 零） | 到 0x66483 止，**33 B** |

0x66484 起是别的数据（文字颜色表），不可越界。

## 4. 中文语料对照（`load_translations()` 全部 16749 条正文 + 878 条 extra）

- 高频且**不在行头禁则表**：`，`13850、`…`10890、`―`(U+2015)3010、`—`(U+2014)1290、
  `：`290、`）`174、`·`11、`；`5、`．`3。→ 这些正是行首出现的标点。
- 高频且**不在行末禁则表**：`（`173。
- 表内但中文全库从未出现（可回收 24 项 = 72 B）：`｝〕〉〟’ヽヾァィゥォャュョヮヵヶぁぃぅぇぉっゅょゎ‐～`。
- 表内且中文用到：`」』】”？！・、。》ー` 及零星 `ェッゃ＝`（各 1–2 次）。
- 游戏自定义括号 `≪≫`(190 对)、`≦≧`(568 对) 原作也不在表内，行首可出现 `≫`——是否
  纳入由我们定。
- 长度：中文正文最长 228 B（日文原文最长 279 B），远低于 500 B 上限；含 `_r` 165 条、
  `_n` 369 条、ruby 36 条。
- 附带发现：`―` 与 `—` 两种破折号在译文里混用（3010 vs 1290），宜统一；拼音 ruby 若含
  ASCII 空格会被 `font_draw_string` 吞掉（`pīn yīn` 显示为 `pīnyīn`），改用全角空格
  U+3000 可保留间距。

## 5. 修补方案候选

**A. 数据表原位置换（推荐，零代码改动）**：把 0x663E0 的 129 B 与 0x66462 的 33 B
改写成面向中文的表，多余部分补零（strstr 遇 NUL 即止）。草案：
- 行头禁则（≤43 字）：保留 `〉》」』】’”ー？！・、。` + 零星 `ェッゃ＝`，新增
  `，：；）…—―．·`（可选 `≫≧`），约 28–30 字，宽裕。
- 行末禁则（≤11 字）：`〈《「『【‘“（`（可选 `≪≦`，恰好 10 字）。
- 效果与原作日文体验同构：行满时中文标点悬挂到第 26/27 格，`……」` 最坏悬挂三格
  （x 到 480，仍在层内，需目检窗体贴图是否盖到那里）。
- 落地：`layers/` 新增 EBOOT 补丁清单（VA、原字节锚点、新字节），`build_disc.py`
  加 `eboot` 阶段：截断 dump → 校验锚点 → 写入 → `umdiso.py replace /PSP_GAME/SYSDIR/EBOOT.BIN`
  （286 扇区不变）。解密 EBOOT 属版权物，与 `assets/orig.iso` 同样不入库。
  **实机前提**：ISO 里放解密 EBOOT 要求 CFW（PRO/ME/ARK 均可；跑 ISO 本就需要 CFW），
  PPSSPP 直接可用。
- 验证：PPSSPP 用 `tools/emu` 截图，构造 `，` 恰落第 26 格、`……」` 落行尾的用例。

**B. 管线预折行（不改 EBOOT）**：在注入前按 §3 规则模拟排版，插入 `_r` 使每行 ≤25 格且
行首无标点（追い出し，把前一字挤到下一行），并顺带校验 ≤4 行/≤500 B。优点：实机无
CFW 顾虑、可做中文式追い出し而非悬挂、可禁止拆开 `……`/`——`；缺点：排版逻辑在
Python 里复制一份，必须与引擎逐格一致；运行时拼接的动态文本（少量系统提示、卡消息
模板）覆盖不到。

**C. 改代码判定**（把 strstr 改成 Unicode 区段判断）：无必要，A 的容量已足够。

推荐 A + 一个轻量校验器（B 的"校验"部分：≤4 行、≤500 B、悬挂 ≥3 格时告警）。
