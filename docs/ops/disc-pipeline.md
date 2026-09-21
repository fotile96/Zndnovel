# 中文化盘构建管线

唯一现行说明，不带日期、随管线演进原地更新。历史实测数据与故障机理见带日期的
`docs/ops/zh-disc-pipeline-2026-08-31.md`、`release-2026-09-01-volunteer-build.md`、
`finale-stage-impl-2026-09-02.md`、`decompiler-base-migration-2026-08-31.md`——那四份
已加取代声明，命令面照抄会失败，但里面的实测结论（三个封包插入实验、ruby 居中规律、
ISO 就地替换机理等）仍然成立，值得作为背景读。设计依据
`docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`。

## 一条命令

```bash
uv run python tools/build_disc.py                     # release 剖面，缺省跑到 iso
uv run python tools/build_disc.py --profile test --mode mainmenu   # test 剖面，全解锁主菜单
```

第一条产 `build/dist/game_zh.iso`（发布断言全过才写盘）；第二条产
`build/test/game/`，供模拟器直接目录引导，见下文「验证」一节。

## 三个概念

**基座**（`lua_scripts/`）：只读纯净基座，与原始游戏字节码逐字节等价——`tools/luac_norm.py`
把 `linedefined`/`lastlinedefined` 两个行号字段归零后比对，229/229 全同（`tests/test_base_fidelity.py`
钉住，`local_assets` 标记，缺 `luac_sz4`/`build/databin` 自动 skip）。**绝不直接改这个目录**：
一切本地化改动——译文、字体、菜单结构、测试捷径、编外新章——都以 `layers/` 下的层的形式存在，
构建时按剖面装配出最终源，基座本身永远保持能被 `tools/migrate_base.py --check` 断言为「等于
上游语料 corpus/final + `add_tr_line_markers()` 重生成的 `-- tr_line:N` 标记」的状态。

**层**（`layers/`）：

| 文件/目录 | 内容 |
|---|---|
| `layers/manifest.toml` | 基座路径、账本路径、车道路径、编译器路径、`[overlays].order`（施加顺序）、`[[scripts]]`（编外新增脚本，如 `snr_finale.lua`）、`[gim]`（烤字面 replace/new 两张映射表）、`[[fonts]]`（字体成员） |
| `layers/vms_ids.toml` | 每个「所有者」声明的 vms/卡消息 id 区段，供 id 登记检查用 |
| `layers/overlays/*.toml` | 静态叠加层：对某个基座文件做一组 `replace`/`insert_before`/`insert_after`/`delete_span` 操作，每条操作都带 `find`/`anchor` 文本锚点，命中次数用 `count`（缺省 1）断言、用 `occurrence`（缺省 `"all"`）选定具体作用哪几处 |
| `layers/scripts/*.lua` | 编外新增的完整脚本（目前只有 `snr_finale.lua`），装配时作为**新增成员**并入最终源集合，不套用任何 `replace` 逻辑 |

叠加层在**译文注入之后**施加（账本按 `(file, line)` 锚定，注入必须先跑且行号不变），故
锚点只准是**代码文本**——不准是可译文本（会被译文替换掉，锚点失效），不准是行号（换基座
会漂移）。`layers/overlays/*.toml` 每份文件头部的 `why` 字段是该层存在理由与踩过的坑的
完整记录，本文档不重复转述，改层前先读它。

**剖面**（`--profile release|test`）：`manifest.toml` 的 `[overlays].order` 列出的每层都在自己
的 `.toml` 里声明 `profile = "release"` 或 `"test"`；release 层两个剖面都施加，test 层只在
test 剖面施加。release 与 test 从 `lua`
阶段起就是两棵完全独立的输出树（`build/release/` 与 `build/test/`，`lua/injected`、
`lua/final`、`members/`、`stage/`、`game/`、`DATA.BIN`、`provenance.json` 各自一份），
test 的任何产物结构上不可能落进 release 的树，也不可能落进 `build/dist/`——那是仅 release
使用的最终交付位置，且 `iso` 阶段本身拒绝在 test 剖面运行。这条隔离是 2026-09-02 管线
规范化要解决的核心事故（此前两个剖面共用同一棵注入与组装产物树，一次测试盘构建就把
发布产物换成了带探针的封包）。

## 五类改动各自的落点与命令

| 改动 | 落点 | 命令 |
|---|---|---|
| 改一行译文 | `pilot/lanes/opus/data/patches.jsonl`（`read_commit.py --apply` 写入） | `uv run python tools/read_commit.py --data-dir pilot/lanes/opus/data --apply` 后 `build_disc.py` |
| 改谢幕章台词/演出 | `layers/scripts/snr_finale.lua` | 直接改文件，再 `build_disc.py` |
| 新增本地化文本（选项按钮、地图点名、系统提示等新文案） | 新建 `layers/overlays/<名>.toml`；在 `manifest.toml` 的 `[overlays].order` 排位；若引入新的 `vms`/`msg` 数字 id，在 `vms_ids.toml` 登记区段 | `uv run python tools/layers.py check` 过闸后 `build_disc.py` |
| 测试捷径（跳 IPL、直入场景、全解锁主菜单等） | 不改任何文件——`tools/testboot.py` 在 test 剖面按 `--mode` 现场生成 | `build_disc.py --profile test --mode {font,scene,ruby,card,cutin,mainmenu,choices,map} [--scene ID] [--card N]` |
| 新增音频（BGM/环境音进 SOUND.BIN） | 用户 PCM 放 `assets/audio/`（不入库）→ `tools/at3p.py encode` 产 `layers/audio/<名>.at3`（AT3+ 128 kbps、本作同款 RIFF 头、必带 smpl；入库）→ `manifest.toml` 的 `[[sound.tracks]]` 登记成员名/两侧 sha256/循环起点/裁尾/响度；Lua 侧 `cPlayBGMWrap(cGetFileName("bgm", "<名>"))` 即可。原 99 成员不改、不能撞名（名单 `data/sound_members.json`）。编码器 `tools/build_atracdenc.sh` 构建 | `uv run python tools/at3p.py encode assets/audio/x.wav layers/audio/x.at3 --loop-start 0 --trim-end 196 --lufs -21`；`at3p.py verify` 对照；`layers.py check` 过闸后 `build_disc.py`（`sound` 阶段）；模拟器 `tools/emu/drives/bgm_probe.py` 听回绕 |
| 改引擎行为（EBOOT 二进制：禁则表、ruby 算式等） | 新建 `layers/eboot/<名>.toml`（原字节锚点 + 新字节/字符串，`why` 必填）；在 `manifest.toml` 的 `[eboot].order` 排位。源是 PPSSPP dump 的解密 EBOOT `assets/EBOOT.dec.elf`（版权物不入库，指纹钉在 `[eboot].sha256`；取得步骤见 `docs/ops/eboot-kinsoku-research-2026-09-04.md` §1） | `uv run python tools/eboot_patch.py check assets/EBOOT.dec.elf` / `layers.py check` 过闸后 `build_disc.py`（`eboot` 阶段） |

烤字图（卡面/选项/系统 UI 等新增或替换的 PNG）不在上表——那条链路是「先跑对应
`tools/bake_*.py` 产 `build/<面>_zh/*.png`」，再由 `manifest.toml` 的 `[gim].replace`/`[gim].new`
两张表在 `members` 阶段拾取编码，与「层」无关，不需要碰 `layers/`。
两者兼有的例子是开机第五卡（2026-09-21）：`tools/bake_boot_dedication.py` 纯排版产
`build/boot_dedication/IPL03.png`，`[gim].new` 以 `sysgim/IPL01.gim` 为模板编成新成员 `sysgim/IPL03.gim`，
而把它插进 `snr_common.main()` 开场链（版权页之后、自动存档告知之前，工作层 4）的是叠加层
`layers/overlays/boot-dedication.toml`——它必须排在 `strip-ipl` 之前，test 剖面快启动才会连它一起剥掉；
验证用 `tools/emu/drives/boot_dedication.py`（test 盘须 `--no-fast-boot`）。

## 阶段表

`--stage` 逗号分隔，缺省 `all`（release 到 `iso`、test 到 `disc`，均不含 `boot`）：

| 阶段 | 做什么 |
|---|---|
| `lua` | 译文注入 `lua_scripts` → 按剖面施加叠加层（release 层两剖面都施加，test 层只在 test；test 剖面先跑 `testboot.generate()` 产 `root/generated/`，其 `snr_test.lua` 与递卡短路等层随后一并施加）→ id 登记检查 → 写 `build/<profile>/lua/final/` |
| `font` | 从**本剖面 + release** 两棵 `lua/final` 的并集算字集（2026-09-21 起；此前只看 release 那棵、test 盘新层的字会漏。test 复用 release 字体产物，探针文本随之计入字集——字集只许变大）→ 与 `build/font/ucs.txt` 比对内容，不等或 pgf 缺失才重建 → `build/font/{lxgw17,lxgw09}.pgf`（跨剖面共享） |
| `members` | `build/<profile>/members/`：先清空再重建。编译 `lua/final/*.lua`（校 PSP ABI 头）；gim 按 `manifest.toml` 的 `[gim]` 两表编码（经 `build/cache/gim/` 内容哈希缓存，`--force` 绕过）；字体拷入 |
| `stage` | `build/databin` --APFS clone--> `build/<profile>/stage`，覆入 members，新成员按名排序位插入（引擎二分查找依赖有序性） |
| `pack` | `databin pack stage` → `build/<profile>/DATA.BIN`，记下这次打包对应的 stage 树指纹到 `build/<profile>/stage_fingerprint.txt`。**不碰 `build/dist/`**——发布产物只能由通过发布断言的 `iso` 阶段写入 |
| `sound` | 按 `manifest.toml` 的 `[sound]`：原版 SOUND.BIN（首次自 `assets/orig.iso` 解出到 `build/sound/orig/`）+ `layers/audio/*.at3` 按名有序插入（原成员逐字节不动）→ `build/<profile>/SOUND.BIN`。先过 `layers._check_sound`（指纹/固件头部规则/循环起点/撞名）。无曲目则空转 |
| `eboot` | 按 `manifest.toml` 的 `[eboot]` 给解密引擎 ELF 施加 `layers/eboot/*.toml` 的字节补丁（`tools/eboot_patch.py`：逐补丁核对原字节锚点，幂等，任一不中整体失败）→ `build/<profile>/EBOOT.BIN`。没有 `[eboot]` 节则空转，盘里沿用原加密 EBOOT |
| `disc` | 刷新 `build/<profile>/game/`（首次自 `assets/orig.iso` 解出）+ 覆入 `DATA.BIN` 与（有 `[eboot]` 时）`EBOOT.BIN`、（有 `[sound]` 曲目时）`SOUND.BIN`，供 PPSSPP 目录引导 |
| `iso` | 仅 release：三道断言（有 `[eboot]` 时四道，有 `[sound]` 曲目时五道——SOUND.BIN 须逐字节等于「原版 + 当前音频层重新装配」）全过，才把 `DATA.BIN`/`EBOOT.BIN`/`SOUND.BIN` 拷到 `build/dist/`、`umdiso` 就地替换这些文件 → `build/dist/game_zh.iso` + provenance 副本；任一断言不过就拒绝出盘，不写任何 `build/dist/` 文件（见下「各道闸」） |
| `boot` | PPSSPP 引导冒烟 + 截图序列，opt-in，不在缺省阶段集合内 |

不论这次跑了哪些阶段，结束时都会写 `build/<profile>/provenance.json`。

## 加一个新层的完整走查（示例：文库入口中文说明）

文库（`snr_novel.lua`）入口的中文说明——告知玩家 `png/novel/` 那 993 张竖排页图小说不烤字、
只读日文原图，指引民间译本——**已于 2026-09-21 实施**，就是 `layers/overlays/novel-notice-entry.toml`
（入口，一次性）与 `novel-notice-s1f.toml`（章节 1 读完、原作介绍 novel 模式处，八条）。方案、措辞、
模拟器目检与踩到的字集坑见 `docs/ops/novel-notice-2026-09-21.md`。下面按它走一遍流程。

1. **确定锚点与操作类型**。目标文件 `snr_novel.lua`，`main()` 里 `systemConfig.unsetConfigButton()`
   在全文件唯一出现一次，位于「一本也没有」早退之后、`advPart(false)` 之前——原作在同一位置用 `msg()`
   显示空列表提示，证明此时消息窗可用，适合作 `insert_before` 锚点：

   ```toml
   # layers/overlays/novel-notice-entry.toml（节录）
   target  = "snr_novel.lua"
   profile = "release"

   [[ops]]
   op     = "insert_before"
   anchor = '''
       systemConfig.unsetConfigButton()
   '''
   text   = '''
       if systemSave.novelNoticeSeen ~= true then
           vms(17510, "NONVOICE", "【■汉化说明】游戏内小说未作翻译，以下为日文原版页面。")
           vms(17511, "NONVOICE", "【■汉化说明】中文社区早有网友译出的版本，欢迎自行检索阅读；也欢迎学会日语后再来重温。")
           systemSave.novelNoticeSeen = true   -- persisted by the autoSystemSave(0) at the end of main()
       end
   '''
   ```

   锚点是**代码文本**而不是字符串字面量：`layers.py check` 在纯净基座上验层、`build_disc.py` 在注入译文后的源上
   施加层，含日文串的锚点只能命中其中一边。新起的 vms id 必须落在账本 `1..17220` 与卡消息保留段
   `18001..18195` 之外，取号前先看 `vms_ids.toml` 已占段（谢幕章 17300–17481、本层 17500–17511）。
   一次性显示靠**新系统键** `systemSave.novelNoticeSeen`：旧系统数据缺键读 nil，`~= true` 即显示一次，
   由脚本末尾原有的 `autoSystemSave(0)` 落盘——同 `finaleReadFlag` 的 nil 守卫做法，刻意不改 `snr_common`
   的 systemSave 字面表（那个锚点已被 `finale-read-flag` 层占用，再叠一层会让两层耦合）。

2. **在 `manifest.toml` 排位**。`[overlays].order` 加 `"novel-notice-entry"`——`load_manifest()`
   会校验 `order` 与 `layers/overlays/` 目录下实际文件一一对应，漏加或错拼直接报错。
   施加顺序是语义的一部分，一般排在末尾即可，除非新层与已有层改动同一文件的重叠区域。

3. **在 `vms_ids.toml` 登记区段**：

   ```toml
   [[ranges]]
   owner = "overlays/novel-notice-entry.toml"
   vms   = [[17510, 17511]]
   ```

   `layers.py check`（`check_ids()`）现在同时扫描两类来源：`manifest.toml` 的
   `[[scripts]]` 里登记的独立脚本文件（如 `snr_finale.lua`），以及
   `manifest.toml` 的 `[overlays].order` 列出的**每个叠加层** `ops[].text`/`with`
   字段里新引入的 id——两者用同一套区段/两两不交/撞账本判定，登记键分别是脚本的
   `file` 路径与 `f"overlays/{层名}.toml"`。**不含任何 id 的叠加层不必登记**（现有
   四个层——`fonts`/`encore-menu`/`strip-ipl`/`boot-handoff`——都不含 id，登记与否
   对它们是无操作）；一旦某层的 `text`/`with` 里出现 `vms(`/`msg(` 调用而
   `vms_ids.toml` 没有对应 `owner = "overlays/<层名>.toml"` 的 `[[ranges]]`，
   `check_ids()` 会硬失败。仍建议仿照
   `tests/test_layers_corpus.py::test_finale_ids_are_inside_declared_range` 的写法给
   引入新 id 的层加一条真语料测试作为文档化证据，但拦截本身不再依赖它。

4. **`layers.py check`**：

   ```bash
   uv run python tools/layers.py check --profile release
   ```

   校验清单模式、`order` 与磁盘一致、id 登记表自洽（两两不交、不与保留集相交）、
   全部 release 层在真实基座上精确命中——不产盘，秒级。锚点写错（count 不符）、
   `order` 漏加、id 区段自相矛盾，这一步都会在这里硬失败，不必等到 `build_disc.py`
   跑完 `lua` 阶段才发现。

5. **`build_disc.py`**：

   ```bash
   uv run python tools/build_disc.py --profile test --mode mainmenu   # 先在 test 剖面走查
   uv run python tools/build_disc.py --profile release                # 确认后再出发布盘
   ```

   `lua` 阶段会把这层实际施加到注入后的 `snr_novel.lua`，其余阶段按前面的阶段表照常走。
   test 盘全解锁，主菜单进 library 子列选 novel 即可看到新说明是否正确渲染——驾驶脚本
   `tools/emu/drives/novel_notice.py`（进两次，第二次不该再提示）；s1f 那层用 `--mode scene --scene s1f-complete`
   + `novel_notice_s1f.py`。⚠ 新文本带来全库没出现过的字时，字集靠 `lua,font` 两阶段连跑才会更新
   （2026-09-21 「译」画成下划线的坑，`39e27cb` 已让 test 剖面并入自己的 final）。

## 各道闸防的是什么

| 闸 | 在哪 | 防什么 |
|---|---|---|
| 锚点命中数断言 | `layers.py` 施加每个 `op` 时 | 基座或前序改动让锚点文本不再是期望的次数（0 次=锚点消失，N 次=锚点被复制/新增），静默 no-op 或错位改写 |
| id 登记检查（`check_ids`） | `layers.py check` / `build_disc.py` 的 `lua` 阶段 | 编外脚本用到的 vms/卡消息 id 越出自己声明的区段、与账本或卡消息保留段（`18001..18195`）冲突、不同所有者声明的区段互相重叠 |
| 字体新鲜度比对 | `build_disc.py` 的 `font` 阶段 | 字集变化（新增本地化文本、编外脚本改了用字）后忘记重建字体，导致新增字符在成片渲染成空白；比对的是字集**内容**而非文件字节数，避免「凑巧同大小」的假阴性 |
| gim 成员对应检查 | `build_disc.py` 的 `members` 阶段 | 烤字工具产出的 PNG 在 `manifest.toml` 的 `[gim]` 两表里找不到对应封包成员——多半是烤字面写错了目标目录名，或成员名拼写与原包不一致 |
| 烤字面完整性（`_require_bake_face`） | `build_disc.py` 的 `members` 阶段 | release 剖面下某个 `build/<face>/` 目录整个不存在（对应 bake 工具没跑过）——硬失败，不允许发布盘缺整面烤字；test 剖面日志告警后跳过整面（局部走查合法） |
| 封包表有序性 | `build_disc.py` 的 `stage` 阶段（`assemble_stage`，`bisect` 插入） | 新增成员插入位置破坏「成员名严格升序」——引擎二分查找找不到、字体/新图直接不生效（2026-08-31 曾实测三次插入位置对照实验，见 `zh-disc-pipeline-2026-08-31.md`） |
| stage 树指纹核对 | `build_disc.py` 的 `iso` 阶段 | `build/<profile>/DATA.BIN` 不是从**当前**这棵 stage 树打出来的（例如重新跑过 `stage` 但漏跑 `pack`），防止发布一份与「当前源码状态」对不上的旧包 |
| 独立重编译逐字节核对 | `build_disc.py` 的 `iso` 阶段 | `stage/script/*.lua` 与译文管线**独立重新编译** `lua/final/*.lua` 的结果不一致——不查特征串，直接拿译文管线产物当基准整体比对，测试引导无论改了什么，只要与管线产物不一致就会被抓住 |
| 成员集合与测试引导成员检查 | `build_disc.py` 的 `iso` 阶段（`release_assertions`） | 封包树里出现未声明的成员（测试引导残留）、或缺了 manifest 声明的新增成员、或混入了 `script/snr_test.lua`——志愿者拿到的盘绝不能带测试探针 |
| `--profile != release` 拒绝 `iso` | `build_disc.py` 的 `iso` 阶段入口 | test 剖面的产物结构上到不了 `build/dist/`，但入口仍显式挡一道，报错比「凭空找不到文件」更明确 |
| EBOOT 源指纹与补丁锚点 | `layers.py check`、`build_disc.py` 的 `eboot` 阶段 | 拿来打补丁的不是登记的纯净解密 EBOOT（sha256 不符）、或某条补丁的原字节锚点不中（源换了、与别的补丁冲突、区间重叠）——静默打错一个字节就是一份行为未知的引擎 |
| 消息窗排版校验（`tools/msg_layout_check.py`） | `layers.py check`（硬失败）、`build_disc.py` 的 `lua` 阶段（release 硬失败，test 只告警） | 译文在引擎里会出可见故障：整条消息排到第 5 行（引擎停滞、消息永远结束不了）、文本 ≥ 500 B（缓冲写穿）、注音组缺 `>`/超 100 B（读穿/砸栈）、注音组越过第 25 格或起点为负（被裁）；另告警悬挂到第 3 格、注音重叠、非拼音半角 ruby 等排版难看项。`--show <id>` 打印模拟版面 |
| EBOOT 重算核对（断言④） | `build_disc.py` 的 `iso` 阶段 | 要出盘的 `build/release/EBOOT.BIN` 与「对纯净源重新施加当前 `layers/eboot`」的结果不一致——`eboot` 阶段漏跑拿到旧产物、或层改了产物没跟上 |
| `migrate_base.py --check` | 独立命令，建议随 `pytest` 一起跑 | 基座本身被意外改动（手滑改了 `lua_scripts/` 原件），让「基座=纯净等价」这条全局假设失守 |

## 故障排查

- **锚点不中**（`OverlayError: 锚点期望命中 N 处，实际命中 M 处`）：先
  `uv run python tools/layers.py diff <层名>` 看这层在基座上原本要打在哪、打成什么样；
  常见原因是账本/车道改了那一行的**日文原文**（不该发生——原文只读）、或基座重新迁移过
  （行号/局部名整体变化，但代码文本本不该受影响，除非改动落在锚点串本身）、或另一个层
  的施加顺序排在这层之前、动过了同一段代码。锚点只能是代码文本不是巧合——可译文本会被
  译文替换，行号会随基座迁移漂移，两者都不配当锚点。
- **id 撞号**：`check_ids` 的报错文本会指出具体是哪一类——「与账本冲突」「与保留段
  `18001..18195` 相交」「两个 owner 的区段重叠」「同一个 id 被两个 owner 同时使用」「没有
  在 layers/vms_ids.toml 登记 id 区段」。处理方式都是去 `layers/vms_ids.toml` 改/加区段，
  不要去改冲突的另一侧（账本 id 是已发布的已读标记锚点，绝不能挪）。`check_ids` 同时扫描
  `[[scripts]]` 里的编外脚本与每个叠加层 `ops[].text`/`with` 字段新引入的 id（登记键
  `f"overlays/{层名}.toml"`）——两者受同一套检查，叠加层不再是这道闸的盲区。
- **字体过期**：`build_disc.py --stage font` 报「字集有变化或字体产物缺失，需要重建，
  但缺 ttf_pgf」——去 `docs/ops/pgf-font-research-2026-08-31.md` 按其生产管线装
  `ttf_pgf`（或设 `SNDL_TTF_PGF` 指到已有安装），然后重跑同一条命令即可，脚本会自己
  判断需要重建还是复用现役字体，不需要手工删 `build/font/`。
- **成员集合不符**（`iso` 阶段 `release_assertions` 报「封包树有未声明的成员」）：多半是
  上一轮 test 剖面的产物混进了 release 的 `build/release/`（结构上不该发生，若发生了检查
  是不是手动改过 `build/` 下的文件）。
- **烤字面整个缺失**（`members` 阶段硬失败，报「release 剖面：`<face>/` 不存在」）：
  `manifest.toml` 新加了 `[[scripts]]`/`[gim].new`/`[gim].replace` 条目、或某个既有 face
  目录被误删，但没有先跑对应的 `tools/bake_*.py` 产出源文件。**这不是在 `iso` 阶段才
  发现的**——`_require_bake_face` 在 release 剖面下于 `members` 阶段就直接 `die()`，
  不会走到发布断言那一步（旧行为是 `members` 悄悄打日志跳过整面、`release_assertions`
  测不出这个缺失，缺整面烤字的 release 盘能一路放行；这道差距已经堵上）。补跑
  `tools/bake_*.py`（缺哪个 face 就搜该工具源码里的 `out_dir("<face>")` 定位是哪一个），
  重跑 `--stage members,stage,pack,iso` 即可。test 剖面仍然允许局部烤字面缺失，只告警
  跳过整面，便于分阶段走查。

## 验证

新层/新脚本改完，先 `uv run python tools/layers.py check` 与相关单元测试
（`tests/test_layers.py`、`tests/test_layers_corpus.py`）过一遍——这些不产盘，秒级。
需要**游戏内**验证时，走 `tools/emu/drives/` 下的模拟器驾驶脚本；具体哪个脚本验什么、
要先建哪种盘（menu/library/no_card144/finale_full 四个驾驶脚本只能跑在 **test** 剖面的
全解锁存档盘，`release_iso.py` 才是唯一验证 release 发布盘、走原版开机链的脚本）见
`tools/emu/drives/README.md`，本文不重复。
