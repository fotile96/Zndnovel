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

## 6. ruby 语法与字体槽 1 的具体机制（同日补记）

### 6.1 解析（`msg_layout_step` 0xA45C 起）

- 触发条件是**半角** `<`（0x3C，单字节）；随后逐字读入，遇**半角** `,` 切到 ruby 段
  （逗号本身不入串；再遇逗号仍是切换、也不入串，故 `<a,b,c>` = base `a` + ruby `bc`），
  遇**半角** `>` 结束。全角 `＜，＞` 不触发。
- base 与 ruby 各累进到一个 **100 字节栈缓冲**（`strcat` 无长度检查）：base 或 ruby
  ≥ 100 字节（≈34 个汉字）会砸栈。组内的 `_n`/`_r` 不被识别，按字面画出。
- 缺 `>` 时游标一路读过正文缓冲末尾（无边界检查，接着是 backlog 槽），直到撞见
  `>`，多半崩溃——**注入前必须校验 `<…,…>` 配对**（现语料 51 组全部配对）。
- 字符计数 `n_base`/`n_ruby` 按"字符个数"（多字节算 1）。
- 整组在**一帧内**画完（不逐字打字机），随后 `col += n_base`。**这条路径没有任何
  换行/禁则/第 4 行检查**：组起点若在 col ≥ 25 就画到悬挂区，跨行也不折。校验器规则：
  `col + n_base ≤ 25`。

### 6.2 落点（`font_draw_string` = EBOOT 0x5698，两槽共用）

| 项 | 公式 | 说明 |
|---|---|---|
| base | 槽 0，`x = 17·col + 4`，`y = 26·line + 10` | 整串一次画，串内按 PGF `advanceH>>6` 推进（LXGW 17px 汉字/全角 = 17，与格宽一致） |
| ruby | 槽 1，`x = 17·col + (17·n_base − 9·n_ruby)/2 + 4`，`y = 26·line + 1` | 按"每个 ruby 字符 9 px"居中；`build_font.widen_latin` 把拼音字母步进撑成 9 px 正是为了让此式成立 |
| 字形行 | `y_top = y + (maxAscender>>6) − bitmapTop + 1` | `maxAscender` 来自 PGF 头 0xD4（`sceFontGetFontInfo` 的 `maxGlyphAscenderI`），`bitmapTop` 来自字形头 |
| 字形列 | `x_left = x + pen + bitmapLeft + 1` | |
| 空格 | ASCII 0x20 **直接跳过、不推进** | 拼音里不能用半角空格；U+3000 现不在字集里（`build_font.ALWAYS` 无此码位） |
| 裁剪 | `sceFontGetCharGlyphImage_Clip(font, ch, img, 0, 0, bufW, bufH)` | 负坐标只被裁掉，不会写坏内存 |
| 描边 | 从 text 层回读字形 4bpp 像素，3×3 膨胀 OR 进 outline 层 | 合成时 outline 层先贴、text 层后贴，各配一种颜色 |

字体槽：`font_slots_4x300`（0x28FF88，**4 槽 × 300 B**，`sceFontNewLib` 的 `numFonts=4`）；
`fontLoad(slot, name)` 只把 `disc0:/PSP_GAME/USRDIR/<name>` 整文件读进 `heap16`
（`sceKernelAllocMemoryBlock`）并记下 ptr/len，真正的 `sceFontOpenUserMemory` 在
**第一次绘制时**惰性发生。Lua 侧 13 处 `cfontPrint` 全用槽 0，**槽 1 只有 ruby 用**。
文件查找：先在 DATA.BIN 索引里按去掉前缀后的路径 `strcmp` 二分（60 B/项：名 52 + 大小 +
偏移），查不到再回退 `sceIoOpen` 真实路径——即引擎也能从光盘散文件读资源。

> 顺带更正：2026-08-31 大字库失败时看到的 `sceFontOpenUserMemory(addr=0, size=-1)`
> 中的 `-1` 是 `pack_file_size` 的"索引与散文件都没找到"返回值，不是缓冲不够；分配
> 失败会走 `NG! sceKernelAllocMemoryBlock` 分支且 size 仍是文件长度。当时封包状态已不可
> 复核，但 build_font.py 开头段"引擎字体缓冲装不下"的归因不成立，裁剪字集仍然是对的
> （内存与加载时间），只是理由要改。

### 6.3 实际量度（`tools/pgf_inspect.py` 读 PGF 头与字形头）

| 字体 | maxAscender（>>6） | 代表字形 top/h | 引擎落点（行内 0 起） |
|---|---|---|---|
| 原 tsukuminpro_e_09（槽 1） | 7.906（7） | ア 7/8、ト 8/9 | ruby 行 2–9 |
| 原 tsukuminpro_e_17（槽 0） | 14.953（14） | 妖 15/17 | 正文行 10–26 |
| lxgw09（LXGW WenKai Mono，widen 后） | 9.000（9） | k 7/8、ā 8/9、g 5/7、妖 8/9 | ruby 行 3/4–11（g 到 12） |
| lxgw17（LXGW WenKai） | 16.000（16） | 妖 14/16、哐 13/15 | 正文行 13–28 |

结论：新字体整体**下沉 2–3 px**（ruby +2、正文 +3），ruby 与正文仍相邻不重叠，第 4 行
底到 106 < 层高 111，不越界；但正文底部伸进下一行 0–2 行，与下一行 ruby 的描边相碰
1–2 px。若要复原原版落点，只需把两份 PGF 头 0xD4 的 `maxAscender` 改回原值
（09 → 7.906，17 → 14.953；引擎不用 descender），正文落点即回到 11–26（差 1 px 来自
LXGW 字形 top 14 vs 原 15），ruby 回到 2–9。这与 `pgf-font-research` 文档"后补丁头部
对齐原值"的预案一致，现在有了精确依据。

步进：lxgw09 的 advance 表只有 3 个值——9.0（汉字、全角、被 widen 的拉丁/拼音）、
4.5（未 widen 的 ASCII 数字与标点）、0（零宽）；lxgw17 汉字/全角恒 17.0、拉丁比例宽
（a 9.75、A 11.5）。字集：两份字体各 3386 字形，拼音声调元音 30 个**全部在册**
（`ALWAYS` 表保证），`kuāng/哐/妖/咚/啪/扑/Ｓｔｏｒｙ` 均有字。

### 6.4 语料里的 ruby 与已知隐患

- 51 组：4 组标题菜单 `<Ｓｔｏｒｙ,故事>` 类（全角拉丁 base 5–8 字 + 2–3 字中文 ruby），
  47 组单字拼音（ruby 2–5 字符，无空格）。
- **5 组起点在 col 0 且 ruby 比 base 宽**（id 11141/11148/11151/11153/11274：`<咚,dōng>`
  x=−6、`<哐,kuāng>` x=−10）：按 6.2 公式起点为负，`k` 整个被左缘裁掉、只剩 `uāng`。
  出路三选一：管线不让这类组落在 col 0（前面垫一个字或调整断行）、改用双字 base、
  或补丁引擎把 ruby 起点钳到 ≥0。
- 右侧无此问题：col 24 的 5 字 ruby 到 x=443，仍在 512 宽的层内、480 宽的屏内。
- 校验器应加的规则：`<…,…>` 配对；base/ruby < 100 字节；`col + n_base ≤ 25`；
  ruby 不含半角空格；起点 `17·col + (17·n_base − 9·n_ruby)/2 + 4 ≥ 0`。

### 6.5 模拟器与实机的字体差异

PPSSPP 对 `sceFont_Library` 一律 HLE（`Core/HLE/HLE.cpp` 的 `g_moduleMeta`），本作随盘的
`module/libfont.prx`（游戏用 `sceKernelLoadModule` 显式加载，`sceLibFont` 的 8 个导入由它
解析）在模拟器里根本不执行，字形栅格化走 PPSSPP 自己的 `Core/Font/PGF.cpp`。要在模拟器
里跑真·libfont.prx 做保真对照，ppsspp.ini 设 `DisableHLEFlags = 1`（bit0 = sceFont）。
拼音 ruby 的 1:1 像素辨识度最终仍以实机为准。

## 7. ruby 使用清点与"半角等宽 ruby"算式补丁（同日第三次补记）

### 7.1 清点（账本 jp 38 组 / 33 条 vs 车道 zh 51 组）

| 来源 | 组数 | 内容 | 译文处理 |
|---|---|---|---|
| s0f 序章术语（彩野/直哉/海馬傍回/扁桃体/内嗅皮質/前向性健忘/逆向性健忘/長期記憶/短期記憶） | 10 | 汉字＋假名读音 | **全部去掉**，改为『』或直译 |
| s1f/s2f/s2s/s3fa/s3s/s4fb/s5s/s7f/e1s 零散难读字（躊躇/残滓/贋作/於/示唆/江口/拠/雹/何時/紡/朦朧/非道/触媒）＋ crd_103 `Ｔｒｕｅ Ｃｏｌｏｒ` ＋ s2s `ＳｈｅｅｐＭａｎ` | 17 | 同上 | 全部去掉 |
| s3fc 绘本（話/本/亡/父） | 7 | 童谣体注音 | 去掉原注音，**新增 45 组单字拼音**（ids 11126–11289，ruby 2–5 字符、无空格） |
| s5s 15069/15071 `<往,ゆ>く` `<逝,い>く` | 2 | 讨论日语"ゆく"的写法 | **原样保留假名 ruby**（是否有意需译者确认；算式改半角后全角 ruby 偏右 2 px，可忽略） |
| crd_6 标题菜单说明 17056/17057/17060/17062 | 4 | 英文菜单词＋片假名 | 保留为 `<Ｓｔｏｒｙ,故事>` 等：**全角拉丁 base ＋ 2–3 字中文 ruby** |

结论：除绘本拼音外，ruby 只剩 crd_6 的 4 组中文 ruby 和 s5s 的 2 组假名 ruby。

### 7.2 补丁：ruby 居中按每字符 4.5 px 估宽（已在 IDB 里打入并经反编译核对）

原式 `x = 17·col + (17·nb − 9·nr)/2 + 4`（每 ruby 字符按 9 px）→ 新式
`x = 17·col + (34·nb − 9·nr)/4 + 4`（= 每 ruby 字符按 4.5 px，即 LXGW Mono 9 px 的天然半角步进）。
反编译核对结果：`font_draw_string(1, 17 * msg_col + (34 * v17 - 9 * v18) / 4 + 4, 26 * msg_line + 1, …)`，
正文调用与 `msg_col += nb` 未动。

⚠ **Allegrex 没有整数 `mul`**（PPSSPP `tableSpecial2` 只有 `halt`，其余 INVALID；`madd/clz`
在 SPECIAL 表）——第一版用 `li 34; mul` 的 5 字补丁在 IDA 里就拒绝解码，实机会触发保留指令
异常，已撤回。现版只用 MIPS I 的 sll/subu/sra/srl/addu/lw/addiu，靠把 `move $a1,$a3` 挤掉
腾出一个槽位放 `sll $a0,1`（×2），除法改成带符号 ÷4 惯用式。块内 a508–a514、a554、a55c、
a560 未动；改写 16 个字（VA → 文件偏移 = VA + 0xC0）：

| VA | 原字（LE） | 原指令 | 新字（LE） | 新指令 |
|---|---|---|---|---|
| a518 | 23 20 86 00 | subu a0,a0,a2 | 40 20 04 00 | sll a0,a0,1（34·nb） |
| a51c | 00 39 05 00 | sll a3,a1,4 | 23 20 86 00 | subu a0,a0,a2 |
| a520 | 43 30 04 00 | sra a2,a0,1 | c3 37 04 00 | sra a2,a0,31 |
| a524 | 21 28 a7 00 | addu a1,a1,a3 | 82 37 06 00 | srl a2,a2,30 |
| a528 | c2 37 06 00 | srl a2,a2,31 | 21 20 86 00 | addu a0,a0,a2 |
| a52c | d0 02 67 8e | lw a3,0x2D0(s3) | 83 20 04 00 | sra a0,a0,2 |
| a530 | 21 20 86 00 | addu a0,a0,a2 | 00 39 05 00 | sll a3,a1,4 |
| a534 | 43 20 04 00 | sra a0,a0,1 | 21 28 a7 00 | addu a1,a1,a3（17·col） |
| a538 | c0 30 07 00 | sll a2,a3,3 | 21 20 a4 00 | addu a0,a1,a0 |
| a53c | 21 20 a4 00 | addu a0,a1,a0 | d0 02 67 8e | lw a3,0x2D0(s3)（line） |
| a540 | 21 28 e6 00 | addu a1,a3,a2 | 04 00 85 24 | addiu a1,a0,4（x） |
| a544 | 04 00 87 24 | addiu a3,a0,4 | c0 30 07 00 | sll a2,a3,3 |
| a548 | 21 20 c5 00 | addu a0,a2,a1 | 21 20 e6 00 | addu a0,a3,a2（9·line） |
| a54c | 21 20 85 00 | addu a0,a0,a1 | 21 30 c4 00 | addu a2,a2,a0（17·line） |
| a550 | 25 28 e0 00 | move a1,a3 | 21 30 c4 00 | addu a2,a2,a0（26·line） |
| a558 | 01 00 86 24 | addiu a2,a0,1 | 01 00 c6 24 | addiu a2,a2,1（y） |

编码已用块内 9 条原指令的实际字节逐一反证（预测值与编译器输出全部一致）。
一字替代方案：只把 a508 的 `sll a2,s2,3` 改成 `sll a2,s2,2`（c0 30 12 00 → 80 30 12 00），
得 `(17·nb − 5·nr)/2`，即每字符按 5 px；配 10 px 渲染的 Mono（500/1000 em = 5 px）或
556/1000 的 widen 值同样精确。

### 7.3 采用半角算式后的连带事项

- **字体管线**：`build_font.WIDEN_SIZES` 清空（拼音步进回到 500/1000 = 4.5 px），
  `embolden_diacritics` 的 `DIACRITIC_MAX_W` 需从 700 降到 ≈450，代价是阴平横线只能放大
  1.5 倍（≈0.9 px，仍偏淡）；二/三/四声不受影响。若嫌淡，走 5 px 方案（10 px 渲染）。
- **语料复核**（全部 51 组按新式重算）：拼音组居中误差 ≤ 0.75 px，起点最小 x = 2，
  §6.4 的 5 处负坐标裁切**全部消失**。
- **crd_6 四行**：中文 ruby 每字 9 px，被新式按 4.5 估宽会右偏 4–6 px。两种解法：
  ① 每个全角 ruby 字前补 1 个半角空格（空格计数不画：`<Ｓｔｏｒｙ,  故事>`、
  `<ｌｉｂｒａｒｙ,   资料库>`），误差回到 ≤ 0.5 px；② 改写成 `Ｓｔｏｒｙ（故事）` 不用 ruby。
- **s5s 两行**假名 ruby 右偏 2 px，可忽略；但保留日文假名本身是否为译者本意待确认。
- IDB（`build/eboot/EBOOT.dec.elf.i64`）当前**已含此补丁**（0xA518 处有注释），
  未写回任何 ELF 文件；落地仍走 §5 的 EBOOT 补丁清单机制。

### 7.4 更正与最终方案：整数步进 + 单位计数 + 不跳过空格（同日第四次补记）

**更正**：`font_draw_string` 的推进是 `advanceH >> 6`（0x5A60 `sra $a1,$a0,6`）后累加整数，
每个字形的小数步进被**截断**——500/1000 em 的 Mono 半角在 9 px 下 advance = 4.5，实际每字
只走 4 px。§7.2 那 16 字的 ÷4 算式追求的 4.5 px 在引擎里根本不存在，已从 IDB 撤回
（0xA518 处留有说明）。结论：ruby 的字符步进必须取**整数 P**（4 或 5 px），
算式常数 K = P。

**回答"是否要让 ruby 不跳过半角空格"**：要。统一半角模型下空格也应是 P px 的真空位，
这样多音节拼音（`<名字,míng zi>`）有词距，居中估算也把空格算进去（跳过时空格"计数不占位"
会让估算多算 P/2 px）。原作日文 ruby `トゥルー カラー` 用的正是 ASCII 空格，原引擎把它
吞成 `トゥルーカラー`，作者当年没管。**改成不跳过后，§7.3 的"补空格居中"手法随之失效**，
全角 ruby 改由引擎按"半角 1 单位 / 全角 2 单位"计数解决——这样 6 组全角 ruby 与拼音、
空格用同一套公式，无需任何文本手脚。

三段补丁（均已打入 IDB 并经反编译核对；VA → 文件偏移 = VA + 0xC0）：

**A. 单位计数**（`msg_layout_step` 0xA4DC–0xA504，11 字）。原来 base/ruby 两条分支各自
`strcat` 后 `+1`；改成合流：用 `movn` 选缓冲，`sltiu $t4,$v0,3` 在调用前从 UTF-8 字节数
算出"是否 1–2 字节"（`$t4` 跨 `strcat_`/`strcpy` 存活——两者只动 a0–a6、s0、v0、ra，
已逐条核对），调用后 `t4−2` 得 −单位数，`movz` 在 base 模式下清零，`subu` 加到 s2；
base 计数用 `xori t5,s0,1` + `addu`。

| VA | 原字（LE） | 原指令 | 新字（LE） | 新指令 |
|---|---|---|---|---|
| a4dc | 06 00 00 16 | bnez s0,loc_A4F8 | 25 20 a0 02 | move a0,s5 |
| a4e0 | 25 20 80 02 | move a0,s4 | 0b 20 90 02 | movn a0,s4,s0 |
| a4e4 | 25 20 a0 02 | move a0,s5 | 03 00 4c 2c | sltiu t4,v0,3 |
| a4e8 | 29 45 00 0c | jal strcat_ | 同 | jal strcat_ |
| a4ec | 25 28 a0 03 | move a1,sp | 同 | move a1,sp |
| a4f0 | e6 ff 00 10 | b loc_A48C | fe ff 8c 25 | addiu t4,t4,−2 |
| a4f4 | 01 00 31 26 | addiu s1,1 | 0a 60 10 00 | movz t4,zero,s0 |
| a4f8 | 29 45 00 0c | jal strcat_ | 23 90 4c 02 | subu s2,s2,t4 |
| a4fc | 25 28 a0 03 | move a1,sp | 01 00 0d 3a | xori t5,s0,1 |
| a500 | e2 ff 00 10 | b loc_A48C | 同 | b loc_A48C |
| a504 | 01 00 52 26 | addiu s2,1 | 21 88 2d 02 | addu s1,s1,t5 |

反编译结果：`v18 -= (t4 − 2) 或 0; v17 += (in_ruby ^ 1)`，`msg_col += v17` 不变。

**B. 常数 K = P**（原 ÷2 算式保留）：P = 5 → a508 `c0 30 12 00`（sll a2,s2,3）改
`80 30 12 00`（sll a2,s2,2），算式成 `(17·nb − 5·units)/2`（反编译已见
`17 * msg_col + (17 * v17 - 5 * v18) / 2 + 4`）；P = 4 → 再把 a514 `21 30 46 02`
（addu a2,s2,a2）改 `00 00 00 00`（nop）。

**C. 不跳过空格**（`font_draw_string` 0x5808）：`04 00 85 14`（bne a0,a1,loc_581C）改
`04 00 00 10`（b loc_581C），延迟槽 `move a1,a0` 照旧把字码送进 `sceFontGetCharInfo`。
空格字形 w=h=0，膨胀循环因 bitmapHeight=0 跳过，只推进 advance；两份字体都含 U+0020。
反编译已见 `if (v23 == 32)` 分支消失。原 5810–5818 三字成为死代码。

**字体侧配套**：P = 4 → 完全不 widen（Mono 天然 500 → 截断成 4 px，空格同），
`DIACRITIC_MAX_W` 降到 ≈400；P = 5 → 字母与空格步进撑到 556/1000，`MAX_W` ≈ 500。
两者阴平横线都只能放大约 1.3–1.7 倍（≈0.8–0.9 px），比现在 9 px 步进下的 1.3 px 淡。

**效果**（按 P=5、字母实际 5 px、全角 9 px 重算 51 组）：拼音精确居中；全角 ruby 每字
误差 0.5 px（估 10 vs 实 9）；`<哐,kuāng>` 25 px 宽在 col 0 起点 x = 0，不再被裁；
crd_6 与 s5s 六组不需任何补空格或改写。校验器规则不变：配对、<100 B、`col+nb ≤ 25`、
起点 ≥ 0，另加"ruby 内只允许半角空格作词距"。

**实机风险点**：C 依赖真·libfont 对 0×0 字形的 `sceFontGetCharGlyphImage_Clip` 返回 0
（PPSSPP 的 HLE 已确认无害）；若实机报错会让整串 ruby 消失。验证顺序：PPSSPP HLE →
PPSSPP `DisableHLEFlags=1` 跑随盘 libfont.prx → 实机。

### 7.5 落地实测：重定位陷阱（同日第五次补记）

三段补丁经 `tools/eboot_patch.py` 打进 EBOOT、走 test 盘探针（`--mode font`，新增
K1–K4/R1 页）后：禁则表**一次通过**（`，：……」≫——` 悬挂到第 26 格起、`（≦` 在
第 25 格前换行，截图 `build/emu/drives/font_probe/p22–p24`），但 ruby 全部消失，且
PPSSPP 开 fastmem 时宿主 SIGSEGV。条件断点 + 单步（`/tmp/ruby_step2.py`，走 WS
`cpu.stepInto/stepOver` 广播）抓到现场：a4f8 处执行的是 `subu s4,v1,t4`，不是写进
文件的 `subu s2,s2,t4`——**PRX 重定位表里 a4f8 那条 R_MIPS_26（原 `jal strcat_`）
仍在，装载器把基址 >>2 加进了新指令的低 26 位**，rd/rs 字段全变，s4（ruby 缓冲指针）
被砸成 1，strcat 往地址 1 写，ruby 串永远为空。

处理：`eboot_patch.py` 增加 `off =` 文件偏移补丁（重定位表不在任何 PT_LOAD 段里），
ruby-p5 层追加第四条——文件偏移 0x735F0 的条目 `f8a40000 04000000` → `f8a40000 00000000`
（类型 R_MIPS_26 → R_MIPS_NONE；a4e8 那条保留，因为那个字仍是 jal）。扫描确认 B、C、
禁则表区间没有其他重定位条目。教训写进 tools/eboot_patch.py 的模块注释与 CLAUDE.md：
**替换带重定位条目的字（jal/j、lui/addiu 对、绝对地址数据）必须同时处理该条目。**

顺带证实了 §3 的"第 5 行起停滞"：探针 K3 初版三行超出 4 行，消息永远结束不了，
CIRCLE 推不动，后续页全部丢失——校验器必须把"每页 ≤ 4 行"当硬错误。
