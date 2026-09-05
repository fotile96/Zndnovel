# EBOOT 逆向：存档机制——sceUtilitySavedata 与 Pluto 协程序列化（2026-09-05）

问题：前身项目做「中日双语」版时把几乎所有 `vms()` 翻倍，之后在较大的剧情单元里呼出
菜单存档会崩溃；当时判断是引擎里一块定长缓冲被序列化后的 Lua 状态挤爆，但机制没有摸透、
修补也没有严格的验证手段。本文从头逆向存档链路，给出结构布局、容量、溢出后果、实测数字、
静态估算器与出盘闸门。方法与工具面沿用 `docs/ops/eboot-hacking-runbook.md`。

## 0. 结论

- 游戏存档 = **Pluto**（Lua 5.1 的 heavy-duty persistence 库）把两样东西序列化进一个
  **406120 B（0x63268）的 bss 定长结构**，再整块交给 `sceUtilitySavedata`（LISTSAVE）写成
  `ms0:/PSP/SAVEDATA/NPJH50279GAMEnn/DATA.BIN`：
  1. `gameSave` 表 → 结构 +0x480 起，**容量 30720 B（0x7800）**；
  2. `mainThread` 协程（挂起中的章节脚本线程）→ 结构 +0x7C84 起，**容量 327680 B（0x50000）**。
- 协程栈上挂着正在跑的脚本的 `main` 闭包，它的 upvalue 指向全部 `scene_*` 局部闭包，Pluto 会把
  这些闭包的 **Proto 树整棵写进去（全部指令 + 全部常量字符串 = 整份脚本正文）**。所以线程
  blob 的大小 ≈ 该脚本字节码的 1.15 倍，与"当前在哪个场景"几乎无关。
- 写入回调 `pluto_writer_membuf`（0x5FF8）逐字节 `base[pos++] = *p`，**没有任何容量检查**。
  超过 0x50000 就依次砸掉：线程 size 字段 → wait 计数 → 12×100 功能键表 → 100×336 层表 →
  字体打印项 → 当前 msg → BGM 名 → 结构之外的全局（消息对话框状态、icon 缓冲指针、
  savedataTitle 缓冲……）。前一段会被随后 memcpy 覆盖回来（存档内容坏而不立刻崩），
  超出结构以后就是随机崩溃。
- 实测（PPSSPP，本项目 release 脚本）：s1s_20 处存档线程 blob **232615 B（71.0%）**，
  s2s_10 处 204838 B（62.5%），s7f-10 处 128240 B（39.1%）；gameSave blob 约 21.2 KB（69%）。
  原版日文脚本按同一估算器算，最大的 s1s 章 **≈255 KB（78%）**——把 vms 翻倍必然超过
  320 KiB，这就是当年崩溃的根因；中文版只替换不追加，比原版还小 9%。
- 新工具：`tools/pluto_size.py`（按字节码估算 / 解析转储，与实测误差 0.7%–2.7%）、
  `tools/emu/drives/save_probe.py`（模拟器实测 + 转储）；`build_disc.py` 的 members 阶段
  现在按编出的字节码估算，release 超容量拒绝出盘（`_check_save_size`）。
- 顺带纠正一条 runbook 事实：**IDB 里 bss 对象的地址比链接时 VA 高 0x6DA40**（IDA 处理指向
  段 1 的 lui/addiu 重定位时把段基址加了两次）；运行时 = IDA 地址 − 0x6DA40 + 0x08804000。
  本文的地址除特别说明外都是 IDB 里的写法。

## 1. 取材

- IDB：`build/eboot/EBOOT.dec.elf.i64`（MCP 会话 `eboot`）。本次新命名：198 个导入桩
  （解析 `.lib.stub`，NID 对照 `~/ppsspp/Core/HLE/*.cpp` 的 HLE 表，脚本见 §1.1）、存档链路
  全部函数、Pluto 全部 persist 函数、23 个 Lua API（`lua_settop/yield/resume/newthread/…`）。
- 反编译对照 Pluto 源码（hoelzro/pluto master `pluto.c`）逐函数核对，`persist()` 的头部、
  `persistproto` 的字段顺序（含 `linedefined/lastlinedefined`）、`persistthread` 的栈/CallInfo/
  upvalue 三段全部一致；差异只有一处：引擎版对**所有类型**（含 number/boolean）都做 reftbl
  去重，master 只对非简单类型做。
- 模拟器：test 剖面 `--mode scene` 直入场景，`save_probe.py` 按 SQUARE → ↓↓ → CIRCLE 走暂停菜单
  的「保存」项，在 0xCB50（`jal gamedata_persist_or_apply` 返回处）断住读 size 字段并转储整个结构。

### 1.1 导入桩命名脚本（可复用）

```python
import struct, re, glob, json
d = open('assets/EBOOT.dec.elf','rb').read()
phoff = struct.unpack_from('<I', d, 28)[0]
_, poff, _, ppaddr, *_ = struct.unpack_from('<8I', d, phoff)
mi = ppaddr & 0x7fffffff                       # PH0.p_paddr → SceModuleInfo 文件偏移
gp, ent_top, ent_end, stub_top, stub_end = struct.unpack_from('<5I', d, mi + 0x20)
nid = {}
for f in glob.glob('/Users/fotile96/ppsspp/Core/HLE/*.cpp'):
    for m in re.finditer(r'\{0[xX]([0-9A-Fa-f]{8})\s*,\s*[^,]+,\s*"([A-Za-z0-9_]+)"', open(f).read()):
        nid.setdefault(int(m.group(1), 16), m.group(2))
cur = stub_top
while cur < stub_end:                            # SceLibraryStubTable：name,ver,attr,len,vcount,fcount,nids,funcs
    nameptr, ver, attr, entlen, vcount, fcount, fnids, funcs = struct.unpack_from('<IHHBBHII', d, cur + poff)
    lib = d[nameptr + poff:].split(b'\0')[0].decode()
    for i in range(fcount):
        n = struct.unpack_from('<I', d, fnids + poff + 4 * i)[0]
        print(f'{funcs + 8 * i:#x} {lib} {n:08X} {nid.get(n, "?")}')
    cur += entlen * 4
```

## 2. Lua 侧接口

`lua_register_natives`（0x9040）注册 60 个原语，与存档相关的 11 个：

| 原语 | C 函数 | 行为 |
|---|---|---|
| `savedataTitle(a, b)` | 0x6C40 | `sprintf` 进两个 128 B 全局缓冲（IDA 0x390D68 / 0x390DE8），**无长度检查**；a 进 SFO 的 `savedataTitle`，b 进 `detail`（后接换行 + `プレイ時間 %4d:%02d:%02d`） |
| `runListSave()` | 0x6CF8 | 置 `byte_257D55 = 1`，`lua_yield`。**不做别的** |
| `runListLoad()` | 0x6CBC | `savedata_req_listload_game`（LISTLOAD 进同一结构），yield |
| `runAutoSave()` | 0x6D78 | `savedata_req_autosave_system`：先 `systemdata_persist_apply_config(1)` 序列化 `systemSave`，再 AUTOSAVE 到 `NPJH50279SYSTEM`，yield |
| `runAutoLoad()` | 0x6D3C | AUTOLOAD `SYSTEM` 进系统缓冲，yield |
| `existSystemdata()` | 0x6DB4 | `sceIoGetstat("ms0:/PSP/SAVEDATA/NPJH50279SYSTEM")` 是目录 |
| `succeedLoadGamedata()` | 0x6E00 | 返回 `byte_326297`（上次 LOAD 的 result==0） |
| `succeedLoadSystemdata()` | 0x6E3C | 返回 `byte_326298` |
| `applyGamedata()` | 0x7618 | 若 `byte_326297`：清零并 `gamedata_persist_or_apply(0)`（反序列化 + 恢复引擎状态），yield |
| `applySystemdata()` | 0x766C | `systemdata_persist_apply_config(2)`：把 `systemSave` 表的 19 个字段读进 C 侧变量 |
| `functionButton(btn, fn)` | 0x6798 | 把函数名字符串写进 12×100 B 表（按键名序：SELECT…）；每帧由 `savedata_dialog_tick` 末尾轮询 |

`config.lua` 的两张表就是 Pluto 的 permanents：

```lua
permsPersist   = {[run]="run", [wait]="wait", [waitLoading]="waitLoading", [msg]="msg", [msgQuit]="msgQuit",
                  [pageScreen]="pageScreen", [switchScreen]="switchScreen", [runListLoad]="runListLoad",
                  [runListSave]="runListSave", [runAutoLoad]="runAutoLoad", [runAutoSave]="runAutoSave",
                  [playMovie]="playMovie"}
permsUnpersist = {run=run, wait=wait, ...}      -- 反向
```

正是这 12 个会 `lua_yield` 的 C 函数：协程挂起时它们的 C 闭包在栈上，Pluto 不允许持久化
C 函数（"Attempt to persist a C function"），只能以 permanent 名字代替，反序列化时再按名换回。

暂停菜单（`systemConfig.Config`，snr_common 3300 行起）里的存档路径：

```lua
elseif l2_1 == 3 then
    l1_0.blackIn(); if l2_0 == true then advPart(true) end
    runListSave()            -- 置标志 + yield；引擎在下一次 script_step 里序列化并弹 LISTSAVE 对话框
    autoSystemSave(1)        -- 对话框结束后再存系统数据（AUTOSAVE）
```

`Config` 本身跑在**第二条协程** `functionThread` 上（§3.2），此时 `mainThread` 仍挂在
`msg`/`wait` 的 yield 里——这正是它能被 Pluto 持久化的前提（"Can't persist currently
running thread" 检查的是 `pi->L == L2`，这里 `pi->L` 是主状态机 L，不是任一协程）。

## 3. 引擎侧流程

### 3.1 脚本装载与步进

- `script_run_file(path)` 0x5B20：读文件进 heap16（`lzss` 头则 `lzss_decode` 到
  `dword_257D58`）；若已有 `mainThread` 先 `lua_settop(L,0)` + `lua_gc(L, COLLECT)`；
  `lua_newthread` → setglobal `mainThread`；`luaL_loadbuffer(thread, buf, size, NULL)`
  （chunkname NULL → 所有 Proto 的 `source` = `"=?"`）；`lua_resume(thread)` 跑完主 chunk
  （定义各 `scene_*` 局部函数与全局 `main`）；`lua_getfield(thread, GLOBALS, "main")` 压栈——
  之后每帧 `lua_resume` 就是以 `main` 为协程主体在跑。清 `dword_257D50`（wait 计数）、
  `byte_257D54`（异步装载等待）、`byte_257CFC`（待切脚本）、`byte_257D55`（存档请求）。
- `script_step()` 0x5CCC（每帧）：wait 计数递减 → 等异步装载 → `lua_resume(functionThread
  若存在，否则 mainThread)` → `byte_257CFC` 置位则 `script_run_file(unk_257D00)` 切脚本 →
  **`byte_257D55` 置位则清零并 `savedata_req_listsave_game()`** → 返回 0（yield 继续）/1（结束）/−1（错误）。
- `lua_msg` 0x6890：`msg_set_text(id, text)` 后 `lua_settop(L,0); lua_yield(L,0)`。对白期间
  `mainThread` 的栈顶就是 `msg` 这个 permanent。

### 3.2 功能键与第二协程

`savedata_dialog_tick` 0x6F8 末尾每帧 `sceCtrlReadBufferPositive` 后遍历 12 个键名：
无影片、无转场（`byte_28FF68`）、无对话框（`byte_1DD346`）、ADV 窗可用（`byte_1DD358`）且该键
绑定了函数名时，`script_call_function_button(name)` 0x5EE8：`lua_newthread` → setglobal
`functionThread`（`dword_257CF8`），按 `.` 拆名字逐级 `lua_getfield` 取到函数压栈；此后
`script_step` 优先 resume 它。函数返回（resume 得 0）后 `lua_settop`、`lua_gc(COLLECT)`、
`dword_257CF8 = 0`，下一帧回到 `mainThread`。`functionThread` 只是全局表里的一个值，
`_G` 不会被持久化（闭包 fenv 等于 `_G` 时 Pluto 写 nil），所以它不进存档。

### 3.3 LISTSAVE 请求（`savedata_req_listsave_game` 0xCB1C）

1. `gamedata_persist_or_apply(1)` 0x6E78（§4 的写法）。
2. 填 `SceUtilitySavedataParam`（IDA 0x3251E8，0x600 B，`savedata_init` 0xC3DC 在
   `main_loop` 启动时已填好常量部分）：

| 偏移 | 字段 | 值 |
|---|---|---|
| +0x00 | size | 1536 |
| +0x0C..+0x18 | graphics/access/font/soundThread | 18 / 20 / 19 / 16 |
| +0x30 | mode | **5 LISTSAVE**（LISTLOAD 4、AUTOSAVE 1、AUTOLOAD 0；`savedata_req_listload_game`/`_autosave_system`/`_autoload_system` 各填其一；0xCC9C 还有 mode 7 DELETE 的路径） |
| +0x38 | overwriteMode | 1 |
| +0x3C | gameName | `NPJH50279` |
| +0x4C | saveName | `""`（列表模式）/ `SYSTEM`（系统数据） |
| +0x60 | saveNameList | `GAME00`…`GAME99`（100 槽 × 20 B，IDA 0x325AB0） |
| +0x64 | fileName | `DATA.BIN` |
| +0x74/+0x78/+0x7C | dataBuf / dataBufSize / dataSize | 存档结构 0x32DAA8 / 0x63268 / 0x63268（系统数据：0x3262A0 / 0x7804 / 0x7804） |
| +0x80 | sfo.title | `セカンドノベル　～彼女の夏、15分の記憶～` |
| +0x100 | sfo.savedataTitle | `savedataTitle()` 第 1 参（系统数据：`システムデータ`） |
| +0x180 | sfo.detail | 第 2 参 + `\n` + `プレイ時間 %4d:%02d:%02d`（秒数取自结构外全局 IDA 0x390D0C） |
| +0x580 | parentalLevel | 5 |
| +0x584 | icon0 | `icon/savedata_game.png`（系统：`savedata_system.png`；从 DATA.BIN 读进 heap16） |
| +0x5C4 | newData | IDA 0x390D50：icon `icon/savedata_new.png` + title 指针（游戏名） |
| +0x5DC | key[16] | `61Mnq8aob347gdwF` |
| +0x5EC | secureVersion | 0 |

3. `sceUtilitySavedataInitStart(&param)`；`byte_326294 = 1`（对话框活动）、`byte_326296 = 0`
   （0 = 游戏数据，1 = 系统数据）、`byte_326295 = 0`（0 = 存，1 = 读）。

### 3.4 对话框状态机（`savedata_dialog_tick` 0x6F8，每帧）

`sceUtilitySavedataGetStatus` = 3（FINISHED）时 `ShutdownStart`，看 `param.result`（+0x1C）：
0 → 成功（LOAD 则 `byte_326297 = 1`；系统数据 LOAD 成功则立即 `systemdata_persist_apply_config(0)`
反序列化 + `(2)` 读配置）；`0x80110307`（LOAD_NO_DATA）/`0x80110301`（LOAD_NO_MS）/
`0x80110381`（SAVE_NO_MS）视为正常取消；其余负值 → 记进 IDA 0x390D14 并弹
`sceUtilityMsgDialog` 显示错误码（0xCD28）。`abortStatus`（+0x5CC）== 1 时按 IDA 0x390D18
的重试码（1..4）下一帧重新发起 LISTLOAD/LISTSAVE/AUTOLOAD/AUTOSAVE。

### 3.5 LOAD 之后（`gamedata_persist_or_apply(0)`）

`lua_createtable` 空 perms → `pluto_unpersist` gameSave → setglobal；`permsUnpersist` →
`pluto_unpersist` 线程 → setglobal `mainThread`；`dword_257CF4 = lua_tothread(-1)`——**当前
协程被替换成存档里那条**；恢复 wait 计数、功能键表、100 层（按名字重新 `layerLoad`，路径
补回 `disc0:/PSP_GAME/USRDIR/` 前缀）、字体打印项、BGM/SE、`msg_set_text(id, text)` 重贴
当前对白；最后 `doScriptScene = gameSave.sceneId`。下一帧 `script_step` resume 这条协程，
就从存档时那句 `msg` 的 yield 处继续。

推论：**存档里带着当时脚本的全部 Proto**。用日文版存档进中文版，读档后会继续跑存档里的
日文脚本代码与文本，直到下一次 `run()` 换脚本才切到盘上的新版本；反之亦然。

## 4. 存档结构布局（IDA 0x32DAA8，链接 VA 0x2C0068，运行时 0x08AC4068；0x63268 B）

`gamedata_persist_or_apply(1)` 先 `memset` 整个结构为 0，再按下表写入：

| 偏移 | 长度 | 内容 | 写法 |
|---|---|---|---|
| 0x00000 | 128 | `savedataTitle()` 第 1 参 | 最后 `strcpy` |
| 0x00080 | 128 | 第 2 参（章节名） | 同上 |
| 0x00100 | 0x380 | 未使用（保持 0） | |
| **0x00480** | **≤ 0x7800** | **`gameSave` 表的 Pluto 流**（perms = 空表） | 第 1 步 |
| 0x07C80 | 4 | 上项字节数 | 第 1 步末 |
| **0x07C84** | **≤ 0x50000** | **`mainThread` 协程的 Pluto 流**（perms = `permsPersist`） | 第 2 步 |
| 0x57C84 | 4 | 上项字节数 | 第 2 步末 |
| 0x57C88 | 4 | wait 计数 `dword_257D50` | 之后依次 memcpy/sprintf |
| 0x57C8C | 0x4B0 | 12×100 B 功能键→函数名表（含 `SQUARE→systemConfig.Config`） | |
| 0x5813C | 0x8340 | 100 层 × 336 B 的层表（文件名去掉 `disc0:/PSP_GAME/USRDIR/` 前缀） | |
| 0x6047C | 0x2AF8 | 字体打印项（每项 220 B） | |
| 0x62F74 | 4 | 打印项数 | |
| 0x62F78 | 4 | 当前 msg id | |
| 0x62F7C | 500 | 当前 msg 文本 | |
| 0x63170 | 80 | 当前 SE/语音名 | |
| 0x631C0 | 2×80 | BGM 槽文件名 | |
| 0x63260..0x63267 | | BGM 标志 2 B、`byte_1DD341`、`byte_1DD345`、`dword_25776C` 低字节… | |

两个 size 字段是在各自 Pluto 流写完之后才写的，所以：
- 线程流超过 0x50000 时，先越过 0x57C84 的 size（随后被正确值覆盖）、wait 计数与功能键表、
  层表……这些字段随后又被 memcpy 覆盖成正确内容，**结果是存档文件里线程流的尾巴被
  引擎状态盖掉——存档可写出，但读档时 unpersist 读到错位数据即出错/崩溃**；
- 再多出 0x5AE4 B（超过 0x55AE4 ≈ 351 KB）就写到结构外：紧接着的 IDA 0x390D10 起是
  对话框状态、错误码、三张 icon 的 heap16 指针与长度（0x390D20..0x390D5C）、newData、
  `savedataTitle` 缓冲——**icon 指针被砸后 `sceUtilitySavedataInitStart` 直接读坏地址**，
  这就是"存档瞬间崩溃"。翻倍后的 s1s 章估算 ≈ 2 × 255 KB ≫ 351 KB，必崩；较小的章节
  可能只是存档损坏。
- `gameSave` 流超过 0x7800 会先盖住自己的 size 字段所在处，再盖进线程流区——线程流随后
  从 0x7C84 起重写，把溢出部分覆盖掉，但 0x7C80 的 size 是在溢出后写的、值仍正确，于是
  读档时 unpersist 会越过 0x7C80 读到线程流开头 → 报错。当前 gameSave 流 21.2 KB（69%），
  内容是 `storyRoute[99]`/`myCard[195]`/tutorial 等固定表，与翻译无关。

系统数据缓冲（IDA 0x3262A0，0x7804 B）：`[0x0000 systemSave 表 Pluto 流 ≤ 0x5000][0x5000 size]
[0x5004 起 0x2800 B：msg 已读位图]`。`msg_read_flag_set(id)` 0x9B58 在 `id ≤ 80000` 时置
第 id 位；本地化新增的 17300–18207 号远在其内。`systemSave` 序列化只 memset 前 0x5000，
位图保留。

## 5. Pluto 流格式（引擎版，`pluto_persist_value` 0x39A08 及各 persist）

`pluto_persist(L, writer, ud)` 0x39D00：栈 [perms, root] → 建弱键 reftbl → `persist`。
`ud = {int pos; char *base}`，`pluto_writer_membuf` 0x5FF8 只做 `base[pos++] = *p`。

每个值的 `persist`：
- 已在 reftbl（**任何类型**，string/number/boolean 按值、其余按身份）→ `int 0, int ref`（8 B）；
- nil → `0, 0`（8 B）；
- 否则 `int 1, int counter, int type`（12 B）+ payload；若值在 perms 表里，type 写 101 并递归
  `persist(permkey)`（键是字符串，通常已见 → 8 B）。

payload：boolean 4；lightuserdata 4；number 8（double）；string `int len` + bytes；
table `int special(0)` + persist(metatable|nil) + Σ(persist(k)+persist(v)) + persist(nil)；
function `u8 nups` + persist(proto) + Σ persist(upval) + persist(fenv|nil)；upval = persist(value)；
thread `int n` + n×persist(栈项，自栈底起) + `int frames` + frames×20 B（base/func/top/nresults/savedpc）
+ status 1 B + base/top/errfunc 12 B + Σ(persist(开放 upval) + int stackpos) + persist(nil)；
**proto**：`int sizek` + Σpersist(k) + `int sizep` + Σpersist(子 proto) + `int sizecode` +
**4×sizecode** + `int sizeupvalues` + Σpersist(名) + `int sizelocvars` + Σ(persist(名)+8) +
persist(source) + `int sizelineinfo` + 4×sizelineinfo + linedefined 4 + lastlinedefined 4 +
nups/numparams/is_vararg/maxstacksize 各 1。

因此对 `luac -s` 剥过调试信息的脚本，一个 Proto 的代价 ≈ 12 + 4 + Σ常量 + 4 + Σ子 + 4 + 4·指令数
+ 4 + 4 + 8（source `"=?"` 全库只付一次 18 B）+ 4 + 8 + 4；字符串常量首次 16 + len，
再次出现 8（Lua 全部字符串内部化，跨 Proto 的相同串也只付一次）；数字首次 20、再次 8。

`tools/pluto_size.py estimate` 就是这套规则对字节码 Proto 树的逐字节实现；`parse-dump`
是同一格式的读回器，用来核对转储。

## 6. 实测（PPSSPP，`save_probe.py`，2026-09-05）

| 场景 | 脚本 | 字节码 B | 估算 Proto 树 B | 实测线程 blob B | 差 | 占容量 | gameSave B |
|---|---|---|---|---|---|---|---|
| s1s_20 | snr_s1_10_s | 198257 | 230941 | **232615** | +1674 | 71.0% | 21230 |
| s2s_10 | snr_s2_10_s | 175219 | 199385 | **204838** | +5453 | 62.5% | 21269 |
| s7f-10 | snr_s7_10_f | 112027 | 126409 | **128240** | +1831 | 39.1% | 21179 |

- `parse-dump` 对三份转储的流长与 size 字段逐字节一致（✓），s1s_20 的线程流：栈项 12、
  CallInfo 5、Proto 82；栈项（栈底→栈顶）= nil 8、**闭包 232053**（`main`：其 upvalue 指向全部
  `scene_*` 闭包，连带整棵 Proto 树，指令 48952 B、字符串常量 136869 B）、4 个引用、
  闭包 29（proto 已见的 `scene_s1s_20`）、闭包 308（`vms`，来自 snr_common）、3 个引用
  （id/语音 id/文本——都是已见常量）、permanent 20（`msg`）。
- s2s_10 的差值大些（5453 B）：栈项 53、CallInfo 4，多出一个 3079 B 的闭包（带自己 Proto 树的
  snr_common 辅助函数）、一张 372 B 的表和几十个 nil/引用槽位——差值取决于存档瞬间栈上挂着
  哪些 snr_common 闭包与局部值，量级是几 KB。估算器缺省余量 `DEFAULT_EXTRA = 16384`（≈5%）。
- 翻倍复盘：s1s 章若 JP+ZH 并存，Proto 树 ≈ 254 KB（原版）+ 113 KB（中文串）+ 每条 vms 多出
  的 5 条指令 ≈ 60 KB ≈ 427 KB，越过 351 KB 的结构边界砸到 icon 指针 → 存档瞬间崩溃；
  s3s（约 342 KB）则停在结构内——存档写坏但不立刻崩。与"某些较长剧情单元才崩"的现象一致。
- 原版日文脚本（`build/databin/script`）估算：s1s 253785 + 余量 → **≈78%**；s2s 66%、
  s3s 62%。中文 release 全部脚本：s1s 70.5%、s2s 60.8%、s3s 56.9%、s4s 46.9%、e2f 44.2%……
  （`uv run python tools/pluto_size.py estimate --members build/release/members/script`）。

## 7. 工具与闸门

- `tools/pluto_size.py estimate [--members DIR] [--extra N]`：逐脚本给出字节码大小、Proto 树
  持久化字节数、占线程区百分比，超容量退出码 1。`parse-dump <savestruct.bin>`：核对 size、
  分类占比、线程栈项分解。测试 `tests/test_pluto_size.py`（用 luac_sz4 编最小 chunk 精确
  对账；手拼 Pluto 流验证读回器）。
- `tools/emu/drives/save_probe.py [--presses N] [--tag T] [--no-dump]`：前置
  `build_disc.py --profile test --mode scene --scene <id>`；开场用 `SceUtilitySavedataParam`
  的 size/gameName 自检 bss 地址换算；断点 0xCB50；输出 `result_<tag>.json` 与
  `savestruct_<tag>.bin`（406120 B，含游戏文本，不入库）。
- `build_disc.py` members 阶段 `_check_save_size`：编译完 `lua/final` 后立即估算，打印最大值，
  release 超容量 `die`，test 告警。`msg_layout_check` 之外的第二道"引擎会坏"闸。

## 8. 若将来需要更大的余量

按代价从小到大：
1. **不动引擎**：保持替换式翻译；新增文本走独立脚本（谢幕章 `snr_finale.lua` 即如此，
   只有 fin 章自己的 Proto 树进存档）；大章节可拆成多个脚本文件用 `run()` 串联（存档只含
   当前文件）。
2. **给写入回调加上限**（3–4 条指令）：`pluto_writer_membuf` 的 `ud` 只有 pos/base，可在
   回调里把 pos 与 0x50000 比较、超限即停写——存档变成"损坏但不崩"，读档时 Pluto 会报错
   （`lua_error` 在无 pcall 的主状态里同样致命），只是把崩溃从存档挪到读档，价值有限。
3. **扩大线程区**：结构是 bss 定长数组，其后紧跟别的全局；扩容要把 `gamedata_persist_or_apply`
   两条路径里 0x385730 起十几处偏移常量、`dataBufSize/dataSize` 的 0x63268、以及
   `sceUtilitySavedata` 对 DATA.BIN 长度的读写全部改掉，并把数组挪到一块新申请的堆内存
   （`heap16_alloc`）。可行但要改二三十个字，且改变存档文件长度、失去与原版存档的互读。
4. **减少被持久化的东西**：让 `main` 不再以 upvalue 持有全部 `scene_*`（改成全局函数由
   `main` 按名查找），Pluto 就只会带上当前场景的 Proto——这是脚本层改动（反编译基座只读，
   须走层），收益最大（线程 blob 从整份脚本降到单场景），但改变了 229 个脚本的结构，
   与"基座逐字节等价"的纪律相悖，仅作备案。

## 8a. 扩容方案的具体依据（同日补记，回答"当年搬 bss 尾部到底搬错了什么"）

### bss 尾部到底有什么

用 `tools/eboot_relscan.py scan --range 0x390D10 0x39DCE0` 把重定位表里指向存档结构之后
53200 B（raw 0x2B5890..0x2C2860）的引用全部数出来：218 处 LO16 站点、30 个目标、分属 12
个以上函数，且**没有任何 R_MIPS_32 数据指针**指向这里或存档结构。按归属：

| IDA 地址（raw = −0xDB480） | 大小 | 内容 | 谁在用 |
|---|---|---|---|
| 0x390D10..0x390D1F | 0x10 | 存档对话框状态：活动/出错/错误码/重试码 | `savedata_dialog_tick`、`savedata_init`、0xCD28 |
| 0x390D20/30/40 | 3×0x10 | 三张 icon 的 PspUtilitySavedataFileData（heap16 指针+长度） | `savedata_init`、各 `savedata_req_*` |
| 0x390D50 | 0x14 | newData（icon + 标题指针 0x390D60） | 同上 |
| 0x390D68 / 0x390DE8 | 2×0x80 | `savedataTitle()` 两参缓冲 | `lua_savedataTitle`、persist、listsave |
| 0x390E68..0x3911E7 | 0x380 | 无重定位引用（疑为 SFO detail 类的备用缓冲或填充） | — |
| 0x3911E8 / 0x391210 / 0x391234 | ≈0x70 | DATA.BIN / SOUND.BIN ×2 三个封包描述符 | `sub_EC8`、`pack_*`、`sub_1AE8` |
| 0x391258 / 0x39125C | 8 | 文件装载线程 id、忙标志 | 同上 |
| 0x391260 | 0x79E0 | 装载器表（`sub_EC8` 开机 memset） | 同上 |
| 0x398C40..0x398C49 | 0x10 | 装载器状态字 | 同上、`font_lib_init`、`main_loop` |
| 0x398C50 | 3×0x50 | config.lua 的 libfontModule / bootScript / selectButtonScript 路径 | `lua_register_natives` |
| 0x398D40..0x398D48 | 0xC | mpeg 句柄/缓冲 | `sub_B444`（影片初始化） |
| 0x398DC8 | 0x40F0 | mpeg/mp4 工作区（`sub_B444` memset） | 影片播放函数族 0xB5B0/0xBB10/0xBE74 |
| 0x39CEB8..0x39CEBA | 3 | 影片状态标志 | 同上、`main_loop` |
| 0x39CEBC | 4 | errno 式出错码（`sub_175A4` 包装 I/O 调用时回填） | Lua 库、0x5179C 族 |
| 0x39CEC0..0x39DCDF | 0xE20 | SAS（音效混音）状态，bss 最后一个对象 | 0x54420 起 37 处 |

结论：尾部不是"一小块"，而是封包装载器、影片解码工作区、混音器状态等**九个子系统的活动
数据**，引用散在几十个函数里，其中影片/装载器的表还被 memset 整块清零。**把它们整体后移**
需要改 218 处引用外加所有 memset 长度，任何一处漏改都表现为"某个子系统偶尔用到旧地址"——
这正是当年"不确定漏搬/多搬"的根源。而存档结构本身只被 4 个函数、38 处 LO16 站点引用。

### 推荐做法：搬存档结构，不搬尾部（`eboot_relscan.py move-plan`）

- 位移取 0x10000 的整数倍，则每处引用只改 **lui 的立即数**，`%lo` 立即数与重定位表一字
  不动（装载器仍按 HI16/LO16 加基址）。干跑结果：结构被 **40 处 LO16 站点、22 个目标**引用，
  归 **37 个 lui 字**（`gamedata_persist_or_apply` 34、`savedata_req_listload_game` 1、
  `savedata_req_listsave_game` 2）——线程区之前的字段只加位移，之后的字段再加 Δ；无任何 lui
  同时服务两侧或结构内外（脚本会断言）。
- ⚠ 扫描器第一版只回溯"未被改写的 lui 寄存器"，漏掉了两处 **`lui + addu 索引`** 的循环访问
  （0x721C `lbu` / 0x753C `sb`，BGM 标志字节 +0x63260，各自的 lui 在 0x7204 / 0x7518），
  IDA 的列表同样漏掉（它显示成 `+0x390000` 的基址算术）。少改这两个字的后果很隐蔽：存档写出的
  BGM 标志落到废弃的旧区域、读档时 BGM 恢复错——正是"漏搬一个变量"的典型形态。现版扫描器
  让 addu/or/move 传播 lui 值后才找齐；任何搬迁清单都必须**用三种独立方法（寄存器流扫描、
  IDA 列表、运行时 0xEE 毒化探针）互相印证**，不能只信一种。
- 常量 0x63268（memset 长度、dataBufSize、dataSize）有三处物化，都是 `lui r,6 ; addiu r,0x3268`：
  lui 在 0x7350、0xCAA0、0xCB64，改成新尺寸的高半即可（Δ = 0x40000 时 6 → 0xA）。
- ELF 头 PH1.p_memsz（文件偏移 0x68）：0x2C2860 → 新结构末。Δ = 0x40000 时新结构落在
  raw 0x2D2628..0x375890，bss 共增 716 KB（含 65 KB 对齐间隙与 406 KB 废弃的旧结构）。
- 旧结构区域不再被任何代码引用（scan 可复核），可顺手让 `savedata_init` 把它填 0xEE 作
  探针：跑一遍存/读档若旧区域被写过即说明漏改。
- 代价：存档文件变长 Δ、与原版/旧版存档互不兼容（读旧档时 unpersist 会读到错位数据）；
  内存少 716 KB（见下）。

### 落地：`layers/eboot/savebuf.toml`（test 剖面）与红/绿实测（同日）

层由 `tools/eboot_relscan.py move-plan --delta 0x40000 --emit-toml` 生成：37 个 lui 字 + 3 个常量
高半字 + PH1.p_memsz（文件偏移 0x68）共 41 条补丁；`tests/test_eboot_relscan.py` 从纯净 ELF
重新推导并与入库文件逐字对账，打补丁后的 ELF 再扫一遍：旧结构区间 0 处引用、新区间 40 处。
估算器/出盘闸的容量改为从层里两条 lui 反推（`pluto_size.savebuf_layout`），层不生效时回到 0x50000。

复现材料：`build_disc.py --profile test --mode scene --scene s1s_20 --bloat` 把 s1s 章 1433 条 vms
翻倍（原句前插一条带 `＊` 标记的 NONVOICE 副本，常量各不相同），复刻"中日双语"盘；估算器报
线程 blob 394076 B。

| 盘 | 引擎布局 | 实测线程 blob | 结果 |
|---|---|---|---|
| 翻倍 s1s | 原版（kinsoku+ruby 层，无 savebuf） | **379366 B / 327680 B（116%）** | 溢出 51686 B：越过结构末，盖掉对话框状态、icon 指针、`savedataTitle` 缓冲（读回标题成乱码 `�=`）直到 DATA.BIN 封包描述符——文件句柄变成 −603957247，装载线程随即刷出 8184 条 `sceIoReadAsync … bad file descriptor`，存档对话框没能弹出、游戏停摆。转储里线程流在 0x50464 处被随后 memcpy 的引擎状态盖断（`parse-dump` 解析失败） |
| 翻倍 s1s | savebuf 层（Δ = 0x40000） | **379366 B / 589824 B（64%）** | 标题/章节完好，错误日志只有开机固定的 1 条，对话框正常 |

估算器在超容量区间同样准：估算 377692 + 实测差 1674 B（与未翻倍的 s1s_20 完全一致）。

**往返验证**（`tools/emu/drives/save_roundtrip.py --patched`，翻倍 s1s + savebuf 层）：开机后把旧
结构区 0x63268 B 填 0xEE → 存档（LISTSAVE 对话框 result 0，写出 681 KB 的 DATA.BIN）→ Lua 的系统
数据确认 → 推进两句 → 读档（LISTLOAD result 0 → AUTOLOAD → applyGamedata）→ 读回 `msg_text_buf`
与存档瞬间完全一致（「○蝉声回响，讴歌着这短暂的夏天。」，读档前已是下一句）→ 旧结构区 0 B 被改动。
三项判据 saved/resumed/poison 全过。前两轮失败都在 PPSSPP 对话框按键语义（覆盖确认默认 No、
「Save completed」只认 ✕），已按其源码改成按引擎活动标志驱动。

### 内存预算（扩 bss 会不会挤到别的东西）

用户区 0x08800000..0x0A000000（24 MB，PARAM.SFO 无 MEMSIZE 大内存标志）。实测（PPSSPP，
s2s_10 场景内快照 heap16 块表 IDA 0x257D60 与 sbrk 指针 IDA 0x1DB4B8/BC/C0）：

| 区段 | 地址 | 大小 | 说明 |
|---|---|---|---|
| 模块（text+data+bss） | 0x08804000..0x08B342A0 | 3.19 MB | bss 末 = PH1.p_memsz |
| `UserSbrk`（newlib 堆） | 0x08B35000..0x08F35000 | 4 MB 固定（`.data` 0x6CD80 = `sce_newlib_heap_kb` 4096） | `sub_109E0` 在第一次 malloc 时 `sceKernelAllocPartitionMemory(2,"UserSbrk",LowAligned,…)`，**紧跟模块之后、低地址对齐分配**，扩 bss 后会自动后移；Lua 状态机住在这里，场景内只用了 636 KB |
| 空隙 | 0x08F35000..0x09676B00 | **≈7.3 MB** | 扩 bss 的余地 |
| heap16（`sceKernelAllocMemoryBlock` type High） | 0x09676B00..0x0A000000 | 9.5 MB，244–252 块 | 字体、层像素、封包索引、音频等，自顶向下 |

所以 +716 KB 绰绰有余。**带 savebuf 层实测**（`--mode movie` OP 循环播放，`mem_probe.py`
12 次快照）：C 堆末从 0x08F35000 后移到 0x08FE8000（恰好 +716 KB），heap16 仍自 0x09676B00 起
（mpeg 工作区在开机 `sub_B444` 里已分配，播放本身不再要内存），空隙稳定 **6715 KB**。
⚠ PPSSPP 没有实现 sceMp4（日志 `sceMp4GetSampleInfo(): UNIMPL` 等），本作 op.mp4 在模拟器里
其实解不出画面，所以影片解码的真实峰值只能在实机核对（下面清单第 3 条）。
正常 s1s_20 盘 + 层的回归往返同样三项全过（线程 blob 232615 B / 589824 B）。

### 实机（CFW）验证清单——模拟器验不到的三件事

1. **内核对扩大的 p_memsz 的处理**：`build_disc.py --profile test --mode scene --scene s1s_20 --bloat`
   出的盘（含 savebuf 层）在实机开机进场景、SQUARE 存档；崩溃/黑屏 = 装载器没按 p_memsz 分配。
2. **savedata 真实写卡**：存档文件 `ms0:/PSP/SAVEDATA/NPJH50279GAME00/DATA.BIN` 应为 668264 B；
   读档回到同一句；再拿 PPSSPP 生成的同名存档拷到卡上读一次（跨平台一致性）。
3. **影片与峰值内存**：翻倍盘从头玩到 OP 播放；`heap16_alloc` 失败会在 stdout 打
   `NG! sceKernelAllocMemoryBlock`（实机看不到，只能看现象：影片黑屏/贴图缺失）。
启用到发布盘前还要做：删除测试者的旧布局存档（读旧档必崩），发布说明写明。

### 备选

- **只加边界检查**：`pluto_writer_membuf` 里比较 pos 与上限，超限停写——存档不崩但读档必坏，
  只值得作为扩容方案的兜底而非替代。
- **整体后移尾部再原地扩容**：改 218 处 + memset 长度，收益与搬结构相同、风险高一个量级，不推荐。
- **不改引擎**：拆脚本 / 独立新增脚本，线程 blob 只含当前文件；本项目现状（71%）不需要扩容。

## 9. 附带发现

- `savedataTitle` 两参各 128 B 缓冲无检查：现译文最长 61 B（`plotTitle` 39 B、章节名 41 B），安全。
- IDB 中 bss 地址偏差 0x6DA40 已写进 runbook §1；本次探针第一版按 `VA + 0x08804000` 读到的
  是 Lua 堆（一堆 `Table` 对象），"线程 blob 1163585 B" 的假读数就是这么来的。
- 探针误区：`--mode scene` 直入后场景开场有约 20 秒演出，按 3 次 CIRCLE 时 ADV 窗还没开、
  SQUARE 不响应（`byte_1DD358`），需 8 次以上并逐帧截图确认对白已出现。
- PPSSPP 日志里每次探针都有 `ILLEGAL_THID=sceKernelWaitThreadEnd(0, 0)` 一条，与存档无关
  （引擎启动时的固定噪声）。
