# 中文盘构建管线规范化：基座 + 层 + 剖面（设计稿）

日期：2026-09-02　状态：待用户审阅　路线：A（用户 2026-09-02 裁定）

## 1. 背景与动机

`译文注入 → luac 回编 → 字体 → 烤图回填 → DATA.BIN 回封 → ISO` 全链路已于 2026-08-31
贯通、2026-09-01 出过志愿者盘、2026-09-02 接入谢幕章。项目进入收尾兼测试期，
lua 前半段的改动频繁且种类多，后半段（烤图、gim 编码、字体、封包、ISO）已固定。

2026-09-02 现状梳理（§12 附全文）发现一个**已验证的出货缺陷**：当前 `build/dist/game_zh.iso`
有 7 个字在游戏里是空白——谢幕章 6 个（仪啥奖恰永颁，vms 17305/17311/17330/17331/17356/
17357/17457）与 s7f 递卡旁白 1 个（挚，`snr_s7_10_f:2081`）。字体 8 月 31 日裁剪，此后译文
改过两次，谢幕章正文更是从未进过字集。根因是**依赖关系没有建模**：font 阶段只做拷贝，
字集来源只看车道与账本，编外源不在其视野。

更深一层的结构问题：lua 源有三个来源（反编译基座、基座上的手工改动、编外的
`docs/finale/snr_finale.lua`）与四处改写层（迁移期字体行、注入期槽 1 行、测试期补丁、
本分支菜单改动），没有单一清单说明「哪些文件进包、每个文件相对原字节码有哪些有意差异」。
新增本地化文本（如 novel 入口提示）**没有归宿**；测试产物与发布产物共用一棵 `build/inject`
树，只靠事后闸防串味；编排层零测试；编译器与字体工具是仓库外未版本化的二进制。

## 2. 目标与非目标

**目标**

1. 用户列出的四类高频改动各有一条命令、一个归宿，改完即可得到正确的盘：
   通读 UI 改译文；谢幕章打磨；新增本地化文本；测试捷径开关。
2. 过期字体、测试残留、无归宿文本这三类错误在结构上不可能发生，或在构建期硬失败。
3. `lua_scripts/` 回到与原始字节码逐字节等价的纯净态，并由测试钉住。
4. 每份产物可追溯到输入与工具的哈希。
5. 编排层有测试。

**非目标**

- 不改烤字工具内部、gim 编解码、databin/umdiso 格式、模拟器客户端、译文车道工具。
- 不在本设计内实现 novel 入口提示的内容，它只作为驱动用例（见 [[novel-menu-notice-todo]]）。
- 不做增量构建图；正确性靠闸，速度只靠 gim 内容哈希缓存。

## 3. 总体模型

三个概念：**基座**、**层**、**剖面**。

**基座** = `lua_scripts/` = 反编译语料（`~/pyluadec-refactor/corpus/final/`）+ `-- tr_line:N`
标记，与原始字节码等价（`tools/luac_norm.py` 行号归零后 229/229 相同）。只读；只随反编译器
重迁移变化；`migrate_base.py` 不再重放字体补丁。账本 `data/ledger*.jsonl` 仍从基座生成。
2026-09-02 实测：基座已是 228/229 纯净，差异只有本分支的 snr_mainmenu 谢幕改动；另有
snr_common 一行槽 0 字体路径。两者都搬成层。

**层** 四种，全部在 `layers/manifest.toml` 声明：

| 层 | 来源 | 施加方式 | 现有成员 |
|---|---|---|---|
| 译文层 | 账本 + 车道三文件 | 按 (file, line) 就地替换字符串参数，行数不变 | 16749 vms + 878 extra |
| 叠加层 overlay | `layers/overlays/*.toml` | 对基座某文件做锚定文本操作，**在译文注入之后** | fonts、encore-menu（release）；strip-ipl、boot-handoff（test） |
| 编外脚本层 authored | `layers/scripts/*.lua` | 整文件新成员，中文直写 | snr_finale.lua（自 docs/finale 移入）；test 剖面生成的 snr_test.lua |
| 资源层 | 烤字产物目录、字体 | 沿用 GIM_SOURCES / NEW_GIM_SOURCES / FONTS 三表，搬进清单，逻辑不变 | 587 gim + 2 pgf |

**剖面** release 与 test，各一棵独立输出树。test = release 层 + test 层；ISO 只有 release 能出。

**硬约束**：账本按行号锚定，所以叠加层一律在译文注入之后施加，锚点只准是代码文本，
不准是可译文本，不准是行号。

## 4. 目录布局

```
layers/
  manifest.toml          # 唯一清单：基座/车道/编译器路径、叠加层顺序、编外脚本、资源面表、字体成员
  vms_ids.toml           # 编外 vms / 卡消息 id 区段登记（账本 1..17220 派生，不手写）
  overlays/
    fonts.toml           # snr_common 槽 0 / 槽 1 两行 fontLoad（release）
    encore-menu.toml     # snr_mainmenu 谢幕直达项，今日 57+/8- 改动（release）
    strip-ipl.toml       # 剥 IPL 开场演出（test）
    boot-handoff.toml    # 引导交接 run(snr_mainmenu) → run(snr_test)（test）
  scripts/
    snr_finale.lua       # 谢幕章演出脚本，vms 17300–17481，卡消息 18201–18207
build/
  release/
    lua/injected/        # 译文注入后（行号不变）
    lua/final/           # 叠加层 + 编外脚本后（编译输入、字集输入）
    charset.txt          # release 字集（与 build/font/ucs.txt 同格式）
    members/             # 本次进包的全部替换/新增成员，每次从清单重建
    stage/               # 基座封包镜像 APFS 快照 + members 覆入
    game/                # PPSSPP 目录引导用盘目录
    provenance.json
  test/                  # 同上结构，另有 generated/{overlays,scripts}/（testboot 生成）
  dist/                  # 仅 release：DATA.BIN、game_zh.iso、game_zh.iso.provenance.json
  cache/gim/             # 内容哈希键的 gim 编码缓存
  font/                  # ucs.txt + lxgw17.pgf + lxgw09.pgf（build_font 产物，跨剖面共享）
  databin/               # 原包解包镜像（不变）
```

`docs/finale/snr_finale.lua` 以 `git mv` 移入 `layers/scripts/`；docs/finale 只留设计与文案。

## 5. 数据流与构建顺序

```
lua_scripts/ ──(ledger+lane 注入)──▶ lua/injected ──(叠加层)──▶ lua/final ◀── layers/scripts
                                                                    │
                     ┌──────────────────────────────────────────────┤
                     ▼                                              ▼
              charset.txt ──≠ ucs.txt?──▶ build_font ──▶ pgf    luac_sz4 ──▶ members/script
                                                          │              │
   build/<烤字目录>/*.png ──(cache/gim)──▶ members/<面>    ▼              ▼
                                            members/pgf ──▶ stage ──▶ pack ──▶ disc ──▶ iso(release)
                                                                                  └──▶ provenance.json
```

阶段名与顺序（`--stage` 逗号分隔）：

1. **lua**：注入译文；按剖面施加叠加层（release 层两个剖面都施加，test 层只在 test，
   生成的 test 叠加层在静态层之后按文件名序施加）；拷入编外脚本；跑 id 检查。
2. **font**：从 **release 剖面** `lua/final` 算字集，写 `charset.txt`；与 `build/font/ucs.txt`
   比对，不等或 pgf 缺失就调 `build_font.build(charset)`；缺 ttf_pgf 则硬失败并打印重建指令。
   test 剖面复用 release 字体，不把探针文本计入字集——否则「语料外字应空白」探针失效，
   且测的字体不再是出货的那份。
3. **members**：先清空再生成。编译 `lua/final/*.lua` → `members/script/`，校 PSP ABI 头；
   gim 面按清单三表编码（经缓存）→ `members/<面>/`；字体拷入 `members/pgf/`。
4. **stage**：`cp -Rc build/databin → stage`，覆入 members；新成员按名 `bisect` 插入；断言全表有序。
5. **pack**：`databin.py pack stage → <profile>/DATA.BIN`（release 同时落 `build/dist/DATA.BIN`）。
6. **disc**：刷 `<profile>/game/`（首次自 `assets/orig.iso` 解出）。
7. **iso**（release only）：成员集合断言（§6.5）通过后 `umdiso.replace` → `build/dist/game_zh.iso`
   + provenance 副本。
8. **boot**（opt-in）：PPSSPP 引导冒烟，不在缺省集合内。

缺省 `all` = release 到 iso、test 到 disc，均不含 boot。

## 6. 组件与接口

### 6.1 `layers/manifest.toml`

```toml
[base]
dir          = "lua_scripts"
ledger       = "data/ledger.jsonl"
ledger_extra = "data/ledger_extra.jsonl"

[lane]
dir = "pilot/lanes/opus/data"      # forward.jsonl / patches.jsonl / forward_extra.jsonl

[compiler]
luac       = "~/pyluadec-refactor/build/luac_sz4"   # 环境变量 SNDL_LUAC 覆盖
header_hex = "1b4c75615100010404040800"

[overlays]
order = ["fonts", "encore-menu", "strip-ipl", "boot-handoff"]   # 文件名去 .toml，施加顺序

[[scripts]]
file    = "scripts/snr_finale.lua"
member  = "script/snr_finale.lua"
profile = "release"

[gim]
replace = [["card_zh", "card"], ["select_zh", "select"], ["select_voice_zh", "select"],
           ["scene_zh", "scene"], ["plot_zh", "plot"], ["sysgim", "sysgim"],
           ["sysgim_title_zh", "sysgim"], ["sysgim_note_zh", "sysgim"], ["sysgim_panel_zh", "sysgim"],
           ["event_zh", "event"], ["cutin_zh", "cutin"], ["cutin_tut_zh", "cutin"],
           ["mode_zh", ""], ["memory_thumb_zh", ""]]           # (build 产物目录, 成员前缀)
new     = [["finale_cards", "card", "card/crd_1_a.gim"],
           ["finale_menu", "sysgim", "sysgim/title_13_a.gim"]]  # + 模板成员

[[fonts]]
size = 17
member = "pgf/LXGWWenKai-Regular.pgf"
[[fonts]]
size = 9
member = "pgf/LXGWWenKai-Regular-09.pgf"
```

未知键一律报错。`[gim]` 的语义与今天 `build_disc.GIM_SOURCES`/`NEW_GIM_SOURCES` 完全相同；
产物目录里 `_` 前缀 png 仍视为 QA 图不入包。

### 6.2 叠加层文件格式与操作语义

一文件一目标。顶层字段：`target`（基座内文件名，必须存在）、`profile`（`release` | `test`）、
`why`（非空，写依据）、可选 `switch`（开关名；带开关的层缺省施加，CLI `--no-<开关名>` 关掉它，
例：strip-ipl 声明 `switch = "fast-boot"`，`--no-fast-boot` 即保留 IPL 演出）。
`[[ops]]` 按文件内顺序依次作用于当前文本。

| op | 字段 | 语义 |
|---|---|---|
| `replace` | `find`, `with` | 自左向右非重叠查找 `find`，命中数必须等于 `count`，把 `occurrence` 选中的换成 `with` |
| `insert_before` / `insert_after` | `anchor`, `text` | 同上，把 `text` 插在选中锚点之前 / 之后 |
| `delete_span` | `start`, `end` | `start` 与 `end` 各恰好命中一次，`end` 须在 `start` 之后；删除 `[start 起点, end 终点)` |
| `replace_span` | `start`, `end`, `with` | 同上，区间替换为 `with` |

公共字段：`count`（≥1，缺省 1，断言全文命中总数）；`occurrence`（`"all"` 缺省，或整数，
1 起，负数自末尾计；`|occurrence| ≤ count`）。span 两种不接受 `count`/`occurrence`。

匹配一律**逐字**，作用于前序操作之后的文本。TOML `'''` 多行字面串保留缩进与反斜杠，
其开头紧随的换行由 TOML 剥去、结尾换行保留；约定多行值以换行收尾，替换即按行对齐。
引擎不做任何空白归一化。格式不含模板变量；参数化叠加（递卡短路）由 testboot 生成器
写成具体文件到 `build/test/generated/overlays/`。

示例（节选）：

```toml
target  = "snr_common.lua"
profile = "test"
why     = "引导交接改指测试脚本。全文 8 处 run(snr_mainmenu)，只有 main() 末尾那一处是交接"

[[ops]]
op = "replace"
count = 8
occurrence = -1
find = 'run(cGetFileName("script", "snr_mainmenu"))'
with = 'run(cGetFileName("script", "snr_test"))'
```

已知层的操作构成：fonts = 2 个 `replace`（槽 0、槽 1 各 1 处）；encore-menu ≈ 7 个操作
（首行表 `replace`、绘制函数 `insert_before` 新 elseif 块、`l0_0.layerKeyCur = …` 两处
`insert_after`、分发链 `insert_before`、`for l1_7 = 1, 11, 1 do` `replace`、
`l0_0.layerKey3[l1_1]` 与 `[l1_0]` 各 `replace count=3`）；strip-ipl = 1 个 `delete_span`
（`    layerMoveAlpha(0, 100, 120)\n` … `    layerMoveAlpha(3, 0, 120)\n    wait(120)\n`，
两锚各 1 处已实测）；boot-handoff 如上例。

### 6.3 `layers/vms_ids.toml` 与检查

```toml
# 账本 1..17220 由 data/ledger.jsonl 派生；oCard.show 动态 id = 18000 + 卡号，卡 1..195 → 18001..18195
[[ranges]]
owner    = "scripts/snr_finale.lua"
vms      = [[17300, 17481]]
card_msg = [[18201, 18207]]
```

检查（构建 lua 阶段与测试都跑）：从每个 release 层文件收集 id——脚本扫全文，叠加层扫
`with`/`text` 字段，正则 `\b(?:vms|msg)\((\d+),`——每个 id 必须落在 owner 声明的 `vms` 区段；
各 owner 区段两两不交；不与保留集相交，保留集 = 账本 id 集 ∪ [18001, 18195]；全部 release
最终源内 id 唯一。`card_msg` 区段是声明性保留（卡消息 id 由引擎按 18000 + 卡号动态生成，
lua 里没有字面 id），只参与两两不交与保留集检查。test 层免于与保留集比对（探针沿用 9000 段，
测试盘永不出货），但 test 层之间必须不交且各自声明区段。

### 6.4 字集与字体

字集 = release `lua/final/*.lua` 全部双引号字面串（含转义，正则 `"((?:[^"\\\n]|\\.)*)"`）中
ord > 0x7F 的字符 ∪ `data/ledger*.jsonl` 的 jp 全字集 ∪ `build_font.ALWAYS` 常驻表，
过滤到 BMP `0x20..0xFFFF`，按今日 `ucs.txt` 同格式写 `build/release/charset.txt`。
保留账本 jp 是「宁滥勿缺」：今日字集恒为新字集的子集，字体只会变大不会漏字。

`build_font.build(charset_path, out_dir)` 接受字集文件，不再读车道；`widen_latin` /
`embolden_diacritics` / 尺寸表不变。字体产物仍在 `build/font/`，跨剖面共享。

### 6.5 成员树、缓存、封包与发布断言

- `members/` 每次 members 阶段**先清空再生成**，杜绝累积。
- gim 缓存键 = sha256(png 字节 ‖ 模板 gim 字节) 前 16 位，`build/cache/gim/<key>.gim`；
  命中即拷贝，未中即编码并写缓存。`--force` 绕过缓存。量化损耗 MSE 仍按今日阈值告警。
- 烤字目录里有 png 却无对应封包成员，或 `new` 面的 png 撞上既有成员：**硬失败**（今日为跳过）。
- **发布断言**（iso 阶段前，替代 `check_release_clean`）：`stage/manifest.jsonl` 成员集合 ==
  `build/databin` 成员 ∪ 清单声明的新成员（release 编外脚本 + `new` 面 gim + 字体）；
  每个 `stage/script/*.lua` 逐字节等于本次 `members/script/` 同名文件；不得含 test 剖面
  编外脚本的成员名（`script/snr_test.lua`）。任一不符即拒绝出盘。

### 6.6 `provenance.json`

```json
{
  "profile": "release",
  "built_at": "2026-09-02T23:10:00+08:00",
  "git": {"head": "…", "branch": "…", "dirty": ["…"]},
  "inputs": {"pilot/lanes/opus/data/forward.jsonl": "sha256…", "…/patches.jsonl": "…",
             "…/forward_extra.jsonl": "…", "data/ledger.jsonl": "…", "data/ledger_extra.jsonl": "…",
             "layers/**": "<逐文件 sha256>", "lua_scripts": "<树 sha256>"},
  "tools": {"luac_sz4": "sha256…", "ttf_pgf": "sha256…|absent"},
  "layers_applied": [{"overlay": "fonts", "target": "snr_common.lua", "ops": 2}, "…"],
  "scripts_added": ["script/snr_finale.lua"],
  "members": {"replaced": 807, "added": 11},
  "outputs": {"DATA.BIN": "sha256…", "game_zh.iso": "sha256…"}
}
```

写在 `build/<profile>/provenance.json`；release 另拷 `build/dist/game_zh.iso.provenance.json`。

### 6.7 工具职责变化

| 工具 | 变化 |
|---|---|
| `tools/layers.py`（新） | 清单加载与校验、叠加引擎、id 检查、字集、provenance。CLI：`check [--profile]`、`diff <overlay>`（对注入后文本打印 unified diff）、`ids` |
| `tools/inject_lua.py` | 保留 `inject_text`/`_inject_body`/`merge_adjacent_ruby`/`lua_quote`；新 `inject_tree(base, ledger, lane, out)`；删 `FONT_SLOT1_*`、`LANE`、`OUT_*`、`compile_bytecode`；CLI 仅调试 |
| `tools/build_disc.py` | `--profile`；阶段改名 lua/font/members/stage/pack/disc/iso/boot；成员树重建；gim 缓存；发布断言；provenance；删 `GIM_SOURCES`/`NEW_GIM_SOURCES`/`FONTS`/`LUAC`/`FINALE_LUA`/`check_release_clean` |
| `tools/make_test_boot.py` → `tools/testboot.py` | 纯生成器：`generate(mode, …) → build/test/generated/{overlays/*.toml, scripts/snr_test.lua}`；模板与扫描函数（`scan_cutins`/`scan_calls`/`story_route`/`card_answer`/`card_scene`/`scene_to_script`）原样保留；删 `LUAC`、直接写 `build/inject/script`、`emitted.json` 还原逻辑 |
| `tools/build_font.py` | `build(charset_path, out_dir)`；删 `corpus_chars` 对车道的依赖（字集由 layers 算）；`ALWAYS` 保留并被 layers 引用 |
| `tools/migrate_base.py` | 删 `FONT_PATCH` 重放；加 `--check`：断言 `lua_scripts == corpus/final + add_tr_line_markers` |
| `tools/luac_norm.py` | 加 `compare_dirs(a, b) -> (same, diff, err, names)` 供测试调用 |

### 6.8 命令面

```
uv run python tools/build_disc.py                                          # release，到 iso
uv run python tools/build_disc.py --stage lua,font,members                 # 局部
uv run python tools/build_disc.py --profile test --mode scene --scene fin-30
uv run python tools/build_disc.py --profile test --mode card --card 103
uv run python tools/build_disc.py --profile test --mode mainmenu --boot
uv run python tools/layers.py check                                        # 只验层，秒级
uv run python tools/layers.py diff encore-menu
```

test 剖面参数与今日 `make_test_boot.py` 相同：`--mode font|scene|ruby|card|cutin|mainmenu|choices|map`，
`--scene`、`--card`、`--hold`、`--no-cards`、`--no-fast-boot`（后者等于不施加 strip-ipl）。

四类高频改动的落点与命令：

| 改动 | 归宿 | 命令 |
|---|---|---|
| 通读 UI 改译文 | `read_commit --apply` → 车道 patches.jsonl | `build_disc.py` |
| 谢幕章打磨 | 编辑 `layers/scripts/snr_finale.lua` | `build_disc.py` |
| 新增本地化文本 | 新建 `layers/overlays/<名>.toml`，在 `manifest.toml` 排序、`vms_ids.toml` 登记区段 | `layers.py check` 后 `build_disc.py` |
| 测试捷径 | 无需改文件 | `build_disc.py --profile test --mode …` |

### 6.9 错误处理

一切正确性问题都是硬失败（`SystemExit`，消息含可执行的下一步）：清单模式错误、锚点未中或
count 不符、id 越界或撞号、编译失败、字节码头不符、字体过期而缺 ttf_pgf、烤图无对应成员、
成员集合不符、缺 luac。只有 gim 量化损耗保留为警告。不再有「跳过」类的静默处置。

## 7. 测试策略

沿用仓库既有原则：缺环境就 skip，绝不 fail，绝不默默换料。

**封闭单元测试**（任何机器）：`tests/test_layers.py`（五种操作、count/occurrence 每种失败路径、
多行逐字匹配与缩进保真、TOML 往返、清单与 id 表模式校验、字集抽取含转义、provenance 字段）；
`tests/test_inject_lua.py`（行数不变、id 不符报错、literal=false 路径、ruby 合并——今日缺失）；
`tests/test_build_disc.py`（合成三成员的迷你 databin：成员树从零重建、按名插入、发布断言各失败路径、
gim 缓存命中/未中/`--force`）；`tests/test_testboot.py`（每种模式产出的层文件、锚点与 id、
永不带 release 标签）。

**真语料测试**（任何机器；基座、账本、车道、层都在仓库）：全部 release 叠加层在真实注入文本上
以精确 count 命中；id 登记与真账本不交；`snr_finale.lua` 的 id 落在声明区段；
`build_ledger --check` 等价断言（已有）。这是新增文本以后的日常守门员。

**本机资产测试**（标记 `local_assets`，缺 luac_sz4 / build/databin / ~/pyluadec-refactor 即 skip，
与 `tests/emu/conftest.py` 同一机制）：基座保真 229/229（`luac_norm.compare_dirs`）；
`migrate_base --check`；release 230 个脚本全部编译通过且头为 PSP ABI；引导冒烟沿用 `tests/emu`。

实现全程 TDD。`pyproject.toml` 注册 `local_assets` 标记。

## 8. 迁移路径

每步一个 commit，每步有闸。全部在 `feat/finale-stage` 上完成。

0. **字体热修**（可选，用户点头后执行）：`build_font.py` + `build_disc.py --stage font,stage,pack,iso`，
   让现在的 ISO 可用于实机验收。不做也行，第 3 步自然修掉。
1. **脚手架**：建 `layers/`，写 `tools/layers.py` 引擎与全部单元测试。构建行为不变。
2. **基座纯净化与叠加承接，合为一个 commit**（否则中间态的盘丢谢幕入口）：基座自语料加
   tr_line 重生成，去掉字体行与 snr_mainmenu 改动；写 `fonts.toml`、`encore-menu.toml`；
   `git mv docs/finale/snr_finale.lua layers/scripts/`；登记 id。已核实账本不受影响：
   snr_mainmenu 唯一的账本键在第 79 行，改动自 174 行起。
   **闸**：luac_norm 229/229；`layers check` 全中；新链路编出的 230 个脚本与当前
   `build/stage/script/` 逐字节相同——证明叠加层精确复现了今日手工改动。此时新 build_disc
   尚不存在，该闸由 `layers.py check --compare-compiled <dir>` 实现（注入 + 叠加 + 编外脚本 +
   luac 编译后与目录逐字节比对），步骤 3 之后由 build_disc 内建的发布断言接替。
3. **build_disc 剖面化**、成员树重建、gim 缓存、provenance；inject_lua 瘦身；build_font 改输入；
   testboot 改生成器。**闸**：release 全量成员与当前 stage 树逐成员比对，只有两个字体成员
   允许不同（若第 0 步已做则全等）。首轮 gim 缓存编 587 张，之后秒级。
4. **模拟器复验**：12 项菜单与 encore 亮暗态、library 子列、无 144 档回归、谢幕全章、
   发布 ISO 原版开机、test 剖面 scene 与 mainmenu 各一次。上一 session 的 8 个驾驶脚本
   （`/tmp/finale_smoke/drive*.py`，已确认仍在）收进 `tools/emu/drives/`。
5. **文档**：新建不带日期的 `docs/ops/disc-pipeline.md` 作为唯一现行说明；CLAUDE.md 改写
   仓库构成、常用操作、开发规约中的相关段落，核心一句「lua_scripts 只读且与原字节码等价，
   一切本地化改动是层」；`zh-disc-pipeline-2026-08-31.md`、`release-2026-09-01-volunteer-build.md`、
   `finale-stage-impl-2026-09-02.md`、`decompiler-base-migration-2026-08-31.md` 各加一行
   「已被 disc-pipeline.md 取代，保留为历史」；finale 文档更新 snr_finale 路径。
6. 模拟器复验通过即合并；实机清单不变。

## 9. 风险

- 反编译器再迁移可能让锚点或 count 失配——这是设计上的硬失败，届时改层即可。
- TOML 多行字面串不能含三个连续单引号；lua 里不会出现。
- 步骤 2 与 3 之间构建链处于半新半旧状态，期间不出盘。
- `count` 断言过严会让无关的基座变化触发失败——刻意如此，宁可多改一次层，不要静默偏移。

## 10. 验收标准

1. `uv run pytest -m "not emu"` 全绿，含全部新测试；`local_assets` 测试在本机全绿。
2. `lua_scripts/` 重编译、行号归零后与原包字节码 229/229 相同。
3. 从空 `build/`（仅保留 `assets/`）起 release 构建成功；脚本成员与今日逐字节相同；
   字体含 release 最终源全部字符（含今日缺的 7 个）；§8 第 4 步矩阵全过。
4. `--profile test --mode scene --scene fin-30` 在 PPSSPP 直入 fin-30；test 产物绝不出现在
   `build/dist/` 或 `build/release/`。
5. 文档按 §8 第 5 步更新。

## 11. 决策记录

| 决策 | 结论 | 由 |
|---|---|---|
| 规范化边界 | 整张盘，重点保障 lua 前半段快改 | 用户 2026-09-02 |
| 路线 | A：纯净基座 + 声明式叠加层 + 剖面 | 用户 2026-09-02 |
| 目录名 | `layers/` | Claude 提议，用户确认 |
| 字集来源 | 只按 release 最终源（∪ 账本 jp ∪ 常驻表） | 同上 |
| test 字体 | 复用 release 字体，探针文本不计入 | 同上 |
| 层文件格式 | TOML（缩进保真、标准库） | 同上 |
| test 层 id | 免于与账本比对，层间仍须不交 | 同上 |
| gim 速度 | 内容哈希缓存，成员树仍每次重建 | 同上 |
| snr_finale 归宿 | `layers/scripts/` | 同上 |

## 12. 附：2026-09-02 现状梳理清单

按对出货正确性的影响排序，均已实测核对：

1. 依赖关系没有建模：字体过期不被发现（7 个缺字，§1）。
2. lua 源无单一清单：三个源头、四处改写层；「差异 = 恰好两个有意改动」今日为真但无测试钉住。
3. 编排层零测试：inject_lua / build_disc / make_test_boot / migrate_base / luac_norm / build_font
   均无测试；底层 databin / gimcodec / umdiso / build_ledger 有。
4. 两个仓库外未版本化二进制：`~/pyluadec-refactor/build/luac_sz4`（8 月 11 日构建，三处硬编码、
   两种路径写法、仅 inject_lua 认 `SNDL_LUAC`）；`/tmp/pgftool/ttf_pgf`（重启即失）。哈希无记录。
5. `build/inject` 无清单累积目录：无人清理，stage 照单全收；QA 图靠 `_` 前缀约定散在 16 个目录。
6. 发布闸盲区：不核对 stage/script 多余成员，不看 gim / pgf 面。
7. 文档漂移：`zh-disc-pipeline` 「已知缺口」仍写 39 条漏译与槽 1 未换；`build_disc` 文件头写
   「v1 只注入既有成员」；`resolve.py` 称「下游只准读 final.jsonl」而 inject_lua 绕过它，
   车道 final.jsonl 停在 8 月 14 日。
8. `analysis/` 同步纯靠纪律，无 hook 或测试；当前同步。
9. 车道路径在 inject_lua / build_font / migrate_base 三处写死。

健康且保留的部分：账本 (file, line) 锚定与 id 双向核对；`SIMPLE_EXTRA` 单表 +
`uncovered_tr_lines` 断言；`luac_norm` 基座保真判据；发布闸的逐字节重编译比对思路；
封包按名排序插入并断言有序；databin / gimcodec / umdiso 的实测与测试。
