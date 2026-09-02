# Task 7 报告：testboot 生成器化

commit（见文末）—— `refactor: make_test_boot 改为层生成器 testboot.py`。
BASE: Task 6 完成点。分支 `feat/finale-stage`。

## 做了什么

1. `git mv tools/make_test_boot.py tools/testboot.py`（历史随 rename 保留）。
2. 删除：`LUAC`、`INJECT`、`OUT_SRC` 常量；`IPL_BLOCK_HEAD`/`IPL_BLOCK_TAIL`；
   `strip_ipl()`；`BOOT_HANDOFF`；旧 `main()` 里 `emitted.json` 记账-还原逻辑
   （读 `build/inject_src` 用 luac 把上一轮改过的成员编回译文版）；旧 `emit()`
   （写明文源 + 调 luac 编译进 `build/inject/script`）。这些功能已被
   `layers/overlays/strip-ipl.toml`、`layers/overlays/boot-handoff.toml`（Task 4）
   与「成员树每次重建」（新架构不再需要"记账再还原"）取代，不是重新发明。
3. 新增 `generate(mode: str, out_dir: Path, **opts) -> dict`：唯一对外接口。写
   `out_dir/scripts/snr_test.lua`；card 模式额外写
   `out_dir/overlays/card-short-circuit.toml`。返回
   `{"scripts": [...], "overlays": [...]}`（相对 `out_dir` 的路径）。
4. 原 `main()` 里那串 `if args.mode == ...` 的 8 分支 if/elif 链抽成
   `_render_mode(mode, **opts) -> str`：`font`/`ruby`/`scene`/`card`/`cutin`/
   `mainmenu`/`choices`/`map` 全部保留（不是只做测试覆盖的 3 种），未知模式
   `sys.exit`（不再依赖 argparse 的 `choices=` 把关，因为 `generate()` 现在是库
   接口，可以绕过 CLI 直接调用）。
5. 保留全部模板常量（`FONT_PAGES`、`RUBY_VARIANTS`、8 个 `*_TEMPLATE`/`*_PAGE`）
   与扫描函数（`scan_cutins`、`scan_calls`、`story_route`、`card_answer`、
   `card_scene`、`scene_to_script`、`short_circuit_card`）——逐条核对见下方
   「自查」。模板里 `-- 自动生成（tools/make_test_boot.py）：...` 的自我指涉注释
   同步改成 `tools/testboot.py`（机械改名，8 处）。
6. CLI `main()` 保留，去掉 `--no-fast-boot`（IPL 剥离已是 build_disc 侧的层开关，
   不再是本工具的事），新增 `--out`（层文件输出目录，缺省
   `build/test/generated/`）。
7. 修了 brief 没提到、我自己在改造中踩到的一个真实 bug：`_injected_source()`
   要 `from tools import inject_lua`，直接跑脚本（`uv run python tools/testboot.py`）
   时 `sys.path[0]` 是 `tools/` 不是仓库根，会 `ModuleNotFoundError: No module
   named 'tools'`。补了与 `tools/layers.py` 同款的
   `if str(REPO) not in sys.path: sys.path.insert(0, str(REPO))`。

## Brief 代码块的缺陷（本任务分内的"读critically"环节）

**发现**：brief Step 3 的 `_count_select_calls(card)` 按其自身文字说明「读
`lua_scripts/snr_crd_<card>.lua` 数 `oCard.selectCardObj()` 出现次数」——即读**基座
原文（日文，未译）**。但 `tools/layers.py` 模块 docstring 定的核心约束是「叠加层在
**译文注入之后**施加（账本按 (file, line) 锚定，注入必须先跑且行号不变），故锚点
只准是代码文本」；`build_final_sources()` 的 `injected` 参数缺省才读基座原文，真实
构建路径（`layers.py` 的 `check --compare-compiled` 已验证、Task 8 brief 里
`stage_lua` 的设计段也明确写着）永远把 `injected=<inject_lua 产出的译文源>` 传进去。
也就是说，`card-short-circuit.toml` 这条 `[[ops]]` 的 `find_all()` 真正扫描的是
**译文注入后**的 `snr_crd_<card>.lua`，不是 `lua_scripts/` 里的日文原文——brief 给的
`count` 算的却是后者。两份文本"理应"在 `oCard.selectCardObj()` 这个具体调用上不受
译文影响（它是纯 Lua 代码、不是 vms() 字符串），但"理应"不是"保证"：任务描述原话
——"establish what that source is in the new arrangement and make the count right
for it, rather than assuming"——正是冲着这处"理应等价"的隐藏假设去的。

`tools/make_test_boot.py` 里能确认这条线索的旁证：**改造前**的 `short_circuit_card()`
读的是 `build/inject_src/snr_crd_{card}.lua`——那正是**注入译文后**的明文源（`tools/
build_disc.py` 注释：「译文注入的明文源；发布自检拿它当基准重编译一遍逐字节对」），
不是 `lua_scripts/`。也就是说改造前的工具本就是照译文注入后的源数的；brief 给的
`_count_select_calls` 若照字面实现（读 `lua_scripts/`），反而是本次改造引入的倒退，
只是 `build/inject_src` 目录本身已经不存在（Task 5 的遗留 stale 路径），不会在这条
分支上直接报错——它会"成功"地数出一个来源不对、恰好可能凑巧相同的数字，把一次本该
在生成期被抓住的错误配置，悄悄推迟到构建期的 `OverlayError`（如果哪天两个数字不再
巧合相等）。

**修复**：新增 `_injected_source(stem)`，复用 `tools.inject_lua` 已被信赖的
`load_translations()` + `inject_text()`（按 (file,line) 纯函数替换，不落盘、只对
单文件现算，不像 `tools.layers._injected_sources()` 那样把整棵基座都注入一遍）。
`short_circuit_card()` 改用它取源（不再读已不存在的 `build/inject_src/`），
`_count_select_calls(card)` 直接复用 `short_circuit_card()` 的计数——**同一份源**
数两件事（"count 是多少"与"替换后长什么样"），避免两处各自现算、未来译文管线一旦
真的改变这份源的字面内容就可能悄悄分叉出两个不同的数。

## 顺带发现并处理：card 模式对"多步骤大谜题"的已知局限（非本任务引入，但予以补救）

**发现**：全库扫描（`lua_scripts/snr_crd_*.lua` 全部 103 个含 `oCard.selectCardObj()`
的文件 × `data/dag.json` 的 `answers` 字段交叉核对）显示：23 张卡（含 brief 自己选作
测试样例的 crd_103『選択：ノート』与 crd_104『True Color』）在同一文件里多次调用
`oCard.selectCardObj()`，且**每处比较的是不同的卡号**（如 crd_103 的 10 处
while-loop 依次比较 192/133/134/…/146；crd_35 的 2 处分别比较 63 与 23）。而无论是
brief 给的实现还是改造前的原实现，短路都只产**一条** `replace` op、**一个** `with`
值——会把全部 `count` 处**统一**换成同一张卡（`answers` 里数值最小的那个）。编译后
第一步之外的每个 `while l1_x < 1 do local l1_4 = <常量>; if l1_4 == 目标 then break
end end` 循环里 `l1_4` 永远是那个常量、`目标` 永远对不上，循环永不 `break`——测试盘
会在这类卡上**死循环卡死**，而不是报错，比"手动翻页找答案"更糟。

**为什么不能加硬失败拦截**：brief 给定的 `tests/test_testboot.py`
（`test_card_mode_emits_short_circuit_overlay` 与 `test_generated_overlays_are_never
_release`）显式要求 `generate("card", tmp_path, card=103)` **成功返回**并产出
overlay——card=103 恰恰是这 23 张多步骤卡之一。若按"多答案就硬失败"实现，会直接
炸穿 brief 指定必须通过的验收测试，属于用一个更严格的正确性挡住了任务本身的验收
标准，不是本任务该做的取舍。

**处理**：不拦截（保持 `generate()` 成功返回，兼容既定测试），但不再让这个已知会
死循环的产物完全沉默——加了 `_dag_answers(card)`（暴露 dag.json 该卡的**完整**去重
答案集合，`card_answer()` 本身不动、仍只取第一个当替换值），在 `count > 1 且
不同答案数 > 1` 时：①`print()` 一条控制台告警；②把同一句话写进生成的 overlay
`why` 字段（供以后任何人打开这份 `.toml` 也能看到）。两处都清楚点名"这类卡请手动
过牌，不要拿这份 overlay 给 QA 用"，并在代码注释里记下真正的修法（按调用点顺序拆成
多条 `occurrence=` 专属 op，需要 `dag.json` 补充调用点顺序信息，非本次生成器化范围）。
这不是"修复"（工具依然做不到多步骤卡的正确短路），而是把一个此前完全沉默、只会在
QA 实机测试时表现为"莫名卡死、像是游戏引擎坏了"的陷阱，变成生成期就看得见的已知
限制——即"每处正确性问题都是硬失败，不许静默跳过"这条全局约束在"不能真拦"时能做到
的最大让步。详见下方「Concerns」。

## 测试

### TDD 证据

RED（Step 2）：
```
$ uv run pytest tests/test_testboot.py -q
==================================== ERRORS ====================================
___________________ ERROR collecting tests/test_testboot.py ____________________
ImportError while importing test module '.../tests/test_testboot.py'.
tests/test_testboot.py:6: in <module>
    from tools.testboot import generate
E   ModuleNotFoundError: No module named 'tools.testboot'
=========================== short test summary info ============================
ERROR tests/test_testboot.py
1 error in 0.05s
```

GREEN（Step 4，改造后）：
```
$ uv run pytest tests/test_testboot.py -v
tests/test_testboot.py::test_mainmenu_mode_emits_test_script PASSED      [ 20%]
tests/test_testboot.py::test_scene_mode_targets_the_right_chapter_script PASSED [ 40%]
tests/test_testboot.py::test_card_mode_emits_short_circuit_overlay PASSED [ 60%]
tests/test_testboot.py::test_generated_overlays_are_never_release PASSED [ 80%]
tests/test_testboot.py::test_unknown_mode_is_hard_failure PASSED         [100%]
5 passed in 0.79s
```

### count 缺陷的实证验证（不只是逻辑推理）

对全部 103 个含 `oCard.selectCardObj()` 的 crd 脚本，逐一对比「`lua_scripts/`
原文计数」与「`_injected_source()` 译文注入后计数」：

```
checked 103 card scripts with selectCardObj() calls
mismatches (pristine count vs injected count): []
```

103/103 一致——证明今日语料下两个数字巧合相同，但机制本身（`_count_select_calls`
现在照哪份源数）已经改成"必然对得上构建时真实命中数"，不再是"巧合对得上"。另外
用 `tools.layers.load_overlay` + `apply_overlay` 对 card=103、card=104 生成的
overlay 做真实施加验证：

```
apply_overlay succeeded, no OverlayError
occurrences of literal 133 inserted: 10
remaining selectCardObj calls: 0
pristine count: 10 / injected count: 10 / pristine == injected text? False
```

（`pristine == injected text? False` 说明这不是"两份文本本来就一样所以数哪个都行"
的退化情况——注入确实改写了该文件里其他 vms() 对白，只是没碰这一个调用点。）

### 全部 8 种模式冒烟（不止 brief 测试覆盖的 3 种）

```
font       lines=  38 overlays=[]
ruby       lines=  16 overlays=[]
[testboot] 扫到 24 张章节 cutin（13 张叠在 CG 上，11 张在黑底上）
cutin      lines= 249 overlays=[]
[testboot] 串起 79 组选择肢按钮
choices    lines= 562 overlays=[]
[testboot] 串起 5 处探索地图
map        lines=  28 overlays=[]
[testboot] 全解锁主菜单（195 卡 + startMenuState=2 + 预置记忆路线）
mainmenu   lines=  31 overlays=[]
scene(s1s_20 / fin-10) 均 OK
[testboot] 递卡短路 7 处 → 答案卡 2，场景 s1s_330
card(card=30) OK, overlays=['overlays/card-short-circuit.toml']
```
"串起 79 组选择肢按钮"与源码注释「实测 79 处 comDlgSelectItem 全是字面量参数」
吻合，确认改造没有破坏扫描函数。

CLI 直跑也验证过（含前面提到的 sys.path bug 修复前后对照）：
`uv run python tools/testboot.py --mode card --card 103 --out /tmp/x`
产出 `scripts/snr_test.lua` + `overlays/card-short-circuit.toml`，`--help` 正常。

### 相关既有测试套件

```
$ uv run pytest tests/test_testboot.py tests/test_layers.py tests/test_inject_lua.py \
      tests/test_build_dag.py tests/test_layers_corpus.py -q
92 passed in 1.35s
```

### 全量测试（改造前后各跑一次全仓库）

- 改造前基线：`1753 passed, 4 skipped in 303.31s`
- 改造后（本文件加入后）：`1758 passed, 4 skipped in 303.55s`（+5 恰好是新增的
  `tests/test_testboot.py`，无既有测试变红、跳过数不变）

## 两道闸

Gate 1（release 剖面，与冻结基线逐字节比对——本任务不该动 release 产物，回归检查）：
```
$ uv run python tools/layers.py check --profile release --compare-compiled \
      .superpowers/sdd/2026-09-02-disc-layers-pipeline/gate-baseline-script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同
exit=0
```

Gate 2（test 剖面，验证两个静态 test 层仍可用）：
```
$ uv run python tools/layers.py check --profile test
[layers] test: 施加 4 层（fonts, encore-menu, strip-ipl, boot-handoff），新增成员 1
[layers] 全部层命中 ✓
exit=0
```

两道闸在改造前后各跑过一次，结果完全一致——本任务只改了 `tools/testboot.py`
一个此前未接入 `layers/` 管线的独立工具，不触碰 `lua_scripts/`、`layers/`，故对
两道闸理应零影响，实测确认。

`lua_scripts/` 只读核对：`git status --short lua_scripts/` 全程为空。

## count 问题怎么解的，为什么这么解是对的

**问题**：递卡短路是一条 `replace` 类型的 `[[ops]]`，其 `count` 字段必须等于
`find`（`oCard.selectCardObj()`）在**叠加层实际施加时看到的那份文本**里出现的
次数——多了少了都会在 `tools/layers.py` 的 `select_indices()` 里触发
`OverlayError`（`len(hits) != count`）。brief 字面上让 `_count_select_calls`
读 `lua_scripts/snr_crd_<card>.lua`（基座日文原文）来数。

**这份源是什么**：`tools/layers.py` 模块 docstring 定的硬约束——「叠加层在译文
注入之后施加……锚点只准是代码文本」——不是这个任务临时定的规则，是整条层管线的
设计前提；`build_final_sources()` 的真实调用（`check --compare-compiled` 已验证，
Task 8 brief 的 `stage_lua` 设计段落也写明）永远传入译文注入后的 `injected` 源。
`card-short-circuit.toml` 的 `target` 是 `snr_crd_<card>.lua`，它在构建时被
`apply_overlay()` 处理的文本，就是这份**译文注入后**的版本，不是 `lua_scripts/`
里的日文原文。

**为什么这个答案是对的而不是"随便选一个反正数字一样"**：①改造前的工具本就是这么
做的（读 `build/inject_src`，即注入后的明文源），brief 给的写法反而是相对改造前的
倒退，只是碰巧指向了一个已经不存在的目录，不会在功能上被立刻察觉；②`oCard.
selectCardObj()` 不是可译字符串，注入不会改写这个调用本身，所以"两份源在这个调用点
上数目相同"目前是真的——但这是**巧合成立**而不是**结构保证**，把 count 算成"结果
碰巧一样"而不是"照实际施加对象数"，正是任务描述点名要避免的"assuming"；③已用全部
103 个含该调用的 crd 脚本做过穷举验证（见上），确认当前语料下两种算法数值一致，
但机制上已经切换成"必然对"而非"恰好对"。

## Files changed

- `tools/testboot.py`（rename from `tools/make_test_boot.py`，含改造）
- `tests/test_testboot.py`（新增，5 个测试，brief 给定内容原样落地）

## 自查（对照任务给的自查清单逐条过）

- **每个被删函数是否都有替身，还是有什么东西悄悄没了家？**
  `strip_ipl()` → `layers/overlays/strip-ipl.toml`（Task 4 已产，逐字核对其
  `[[ops]]` 的 `start`/`end` 与原 `IPL_BLOCK_HEAD`/`IPL_BLOCK_TAIL` 常量值完全
  相同）。`BOOT_HANDOFF` 改写逻辑 → `layers/overlays/boot-handoff.toml`（`count=8,
  occurrence=-1` 的推理原文照抄进了它的 `why`，与原代码注释逐句对应）。`emit()`
  的编译职责 → 不再需要（生成器只写明文层文件，编译是 build_disc/layers 的事）。
  `emitted.json` 记账-还原 → 不需要替身，新架构「成员树每次重建」使其失去存在
  意义（brief 原话，已核实符合新架构语义：build_disc 每次都从 `layers.
  build_final_sources()` 现算最终源，不存在"上一轮遗留"需要清理）。
- **生成的 overlay 是否能过 `load_overlay` 校验——键对不对、`why` 非空、profile
  对不对？** 用 `tools.layers.load_overlay()` 直接加载过 card=103/104/30/10 生成的
  文件，均通过（无 `OverlayError`）；键集合 `{target, profile, why, ops}` 与
  `_OVERLAY_KEYS` 匹配；`why` 非空（触发过要求非空的检查路径，因为最初手滑漏过
  一次校验就会在这里报错，未发生）；`profile` 恒 `"test"`。
- **profile 恒为 test？** `test_generated_overlays_are_never_release` 覆盖
  mainmenu/card/scene 三种模式；代码里 `profile = "test"` 是硬编码字面量，没有
  任何分支能让它变成别的值。
- **每个测试是否在行为回退时真的会红？** `test_mainmenu_mode_emits_test_script`
  锚定的两处字符串若模板被误改会直接不匹配；`test_scene_mode_targets_the_right_
  chapter_script` 用 `fin-30`（`scene_to_script` 里唯一一条特判分支）钉住谢幕章
  路由不会被通用规则覆盖掉；`test_card_mode_emits_short_circuit_overlay` 断言
  `find` 字面量，若把 `SELECT_CALL` 改错会红；`test_generated_overlays_are_never_
  release` 若哪天手滑把 `profile` 写死成别的值会红；`test_unknown_mode_is_hard_
  failure` 若 `_render_mode` 的兜底分支被删掉、退回"未知模式当 scene 处理"的旧
  行为，会因为不再抛 `SystemExit` 而红。
- **模块 docstring 是否说清楚了这个工具现在是什么？** 已重写：讲清楚原理不变
  （测试脚本仍是新增成员 + 改引导交接）、讲清楚哪部分现在归静态层管、讲清楚
  `generate()` 的产物形状与落点、列全 8 种模式（原 docstring 只写了
  font/scene 两种，是本次顺手订正的既有文档缺口，不是本任务要求但顺手做了）。
- **测试输出是否干净？** `pytest -q`/`-v` 全程无警告；`generate()`/`_render_mode()`
  里保留的诊断 `print()`（如"扫到 N 张章节 cutin"）会被 pytest 默认捕获，不会
  污染 `-q` 输出（已用 `-q` 与 `-v` 两种方式确认）。
- **有没有哪句"用实战验证过的经验之谈"注释在搬家过程中弄丢了？** 用脚本对全部
  8 个模板常量、`SELECT_CALL` 注释块、`card_answer`、`card_scene`、`scan_cutins`
  及其正则、`scan_calls` 及其正则、`story_route`、`scene_to_script` 做过逐字节
  diff（规范化掉唯一一处刻意改动——模板内 `tools/make_test_boot.py` →
  `tools/testboot.py` 的自我指涉文件名），全部逐字节相同，见下方证据。

```
$ uv run python3 - <<'PY'
... (对比脚本，见任务过程) ...
PY
OK   'FONT_PAGES = [' .. next
OK   'RUBY_VARIANTS = [' .. next
OK   "CUTIN_TEMPLATE = '''" .. next
OK   "CUTIN_PAGE = '''" .. next
OK   "MAINMENU_TEMPLATE = '''" .. next
OK   "CHOICES_TEMPLATE = '''" .. next
OK   "CHOICES_PAGE = '''" .. next
OK   "MAP_TEMPLATE = '''" .. next
OK   "MAP_PAGE = '''" .. next
OK   "CARD_TEMPLATE = '''" .. next
OK   "SCENE_TEMPLATE = '''" .. next
OK   'SELECT_CALL ='
OK   'card_answer identical: True'
OK   '# 章节首尾 cutin 的真实几何'
OK   'def scan_cutins'
OK   '# 选择肢与地图'
OK   'def scan_calls'
OK   'def story_route'
OK   'def scene_to_script'
```
（`def card_scene` 那一段单独核对时显示"DIFF"，但那正是我在其后插入
`_injected_source`/新版 `short_circuit_card`/`_count_select_calls` 的地方——
`card_scene` 函数体本身另行核对为逐字节相同，插入内容不影响既有代码。）

## Concerns

1. **card 模式的多步骤大谜题局限（详见上文专节）**：crd_103/104 等 23 张卡的
   递卡短路目前只会正确处理第一步，之后每一步都会在真机/模拟器上死循环卡死。
   这是重构前就存在的行为，非本任务引入，但也未被本任务修复——真正修好需要
   `dag.json` 补充"调用点顺序"信息、`generate()` 按 `occurrence=` 拆成多条
   op，属于比"生成器化"更大的设计变更，建议另开任务。现状：generate() 成功、
   打印告警、写进 overlay 的 `why`；不拦截（拦截会与 brief 指定必须通过的
   `card=103` 测试冲突）。人工使用 `--mode card` 时请留意控制台告警。
2. **`_render_mode` 的诊断 `print()` 在 `generate()`/库调用路径下也会触发**
   （不止 CLI）：`tests/test_testboot.py` 的 5 个测试全程会打印若干 `[testboot]`
   行（如"扫到 24 张章节 cutin"），pytest 默认捕获不显示，不影响测试结果，但
   若未来这个模块被更高频调用（比如 Task 8 的 `build_disc.stage_lua` 每次构建
   都调 `testboot.generate()`），这些 print 会成为构建日志的一部分——如果那不是
   期望行为，Task 8 实现时可能需要考虑是否要给 `_render_mode`/`generate()` 加
   一个 `verbose`/`quiet` 开关。本任务未加，因为 brief 与全局约束都没有对输出
   静默性提要求，且现状与改造前工具的行为一致（原工具同样在这些分支里
   `print()`）。
3. **`_injected_source()` 每次调用都重新读取 `data/ledger.jsonl`（16749 行）与
   车道的 `forward.jsonl`/`patches.jsonl`（合计几百万字符）**：单次调用在这台
   机器上是毫秒级，不构成当前问题；但如果 Task 8 的 `stage_lua` 在同一次构建里
   对多张卡分别调用 `generate("card", ...)`，会重复这份 I/O。目前 `--mode card`
   一次只处理一张卡，暂无实际触发场景，标记出来供后续任务留意即可，未做提前
   优化（YAGNI）。

## 结论

Task 7 完成：`tools/testboot.py` 已是纯生成器，`generate()` 是唯一对外接口，
产物是层文件而不是字节码；8 种模式与全部扫描函数/模板常量逐字节保留；brief
代码块里"count 照哪份源数"的缺陷（六选六，第七次复现同一模式）已定位并修复，
用全库穷举 + 真实 overlay 施加验证过；顺带发现并妥善处理（告警而非静默、不
擅自拦截以免与既定验收测试冲突）一个更早就存在的"多步骤大谜题短路不完整"限制；
两道闸与全仓库测试改造前后结果一致。

## Fix round 1（回应 review 的 4 项 Important 发现）

Review 结论：rename、接口、count 缺陷修复三项均独立复核通过——`_injected_source()`
被逐行比对过 `tools/layers.py` 自己的 `_injected_sources()`（闸背后那个函数），
判定是结构忠实的复现而非"看起来像"；8 个模板/扫描函数逐字节复核全部存活；
`multi_step` 探测器不会误报，因为 `build_dag.py` 在源头就把 answers 去重了。
warn-vs-fail 的判断被认可为正确——这是个既有 bug、brief 指定的验收测试要求
card=103 必须成功、产物是 QA 工具而不是出货产品，硬失败不是正确选项。

同时给了 4 项 Important 发现，裁决全部要修。逐条处理如下。

### Finding 1：告警要有结构化通道，不能只有 print()

**改法**：`generate()` 返回值新增 `warnings` 键（list，缺省空），承载与 print
同源的告警文本（重构为单一 `msg` 变量，print/`why` 字段/`warnings` 三处引用
同一份文本，不再各自维护一份相近但不完全相同的措辞）。`print()` 与 `why` 字段
原样保留，这是新增不是替换。

### Finding 2：`generate()` 不清 `out_dir`，旧层会在磁盘上存活

**改法**：重排 `generate()` 内部顺序——先做完 `_render_mode()` 与 card 模式的全部
校验/计算（一个字节都不碰磁盘，任何 `sys.exit` 都在这一步之前触发完），确认
不会失败后，才在函数末尾一次性 `shutil.rmtree()` 清空 `out_dir/scripts`、
`out_dir/overlays`（只清这两个，不碰 `out_dir` 里其他内容——若调用方把 `out_dir`
指到一个还放着别的东西的目录，那些东西不受影响），再写入本次产物。这样磁盘
只经过"旧的没了、新的写齐"一次跳变，不会有"清了一半、写到一半失败"的中间态，
调用后 `scripts/`、`overlays/` 的磁盘实况与返回值严格一致。

`generate()` docstring 新增"契约"段落说明这一保证；模块顶部 docstring 同步一句。

### Finding 3：count 修复没有回归测试

**改法**：`test_card_mode_emits_short_circuit_overlay` 新增
`assert ov["ops"][0]["count"] == 10` 与 `assert ov["ops"][0]["with"] == "133"`，
并加注释说明这两条具体保护什么。

**诚实说明（没有回避 review 原话里一个站不住脚的推论）**：review 的原文说
"a future refactor reverting to the pristine source would leave the suite fully
green, because the two sources coincide for all 103 cards today"——这句话在字面
意义上其实同时说明了这两条断言**不能**单独证明"count 是照哪份源算的"：既然
crd_103 在 lua_scripts/ 原文与译文注入后的源里 count 恰好都是 10（已用全库
103 个文件穷举验证，见 Task 7 首次实施时的记录），一次把 `_count_select_calls`
悄悄改回读 `lua_scripts/` 的回归，对 crd_103 这一个用例产出的 count 数值不会
变——这两条断言对**这一种特定回归**其实不构成充分的独立验证，真正保证"count
照哪份源算"这件事本身的，是 `_injected_source`/`short_circuit_card` 的实现
机制，不是这条测试。

但这两条断言仍然值得加，且已用故障注入验证了它们的真实保护范围——这不是它们
"完全没用"，而是"用处比 review 原文那句话字面暗示的更窄"：此前 `find`/`target`/
`profile` 之外的字段完全不受保护，`count`/`with` 算错、算漏、甚至互换都会全绿
通过。已实测验证：临时把 `with = "{answer}"` 改成 `with = "{answer + 1}"`
（模拟"答案算错了 1"这类具体错误），断言在这里报
`AssertionError: assert '134' == '133'`，而不是静默放行；改回后恢复绿。这才是
这两条断言实际钉住的东西——把它写进了测试文件的注释里，不让下一个读到这条
测试的人继承 review 原文里那个不完全准确的因果推论。

### Finding 4：profile 钉子测试枚举不穷尽

**改法**：`test_generated_overlays_are_never_release` 改为遍历
`tools.testboot._MODES`（模块自己的模式表，8 个）而不是手写的三元组（原来只
覆盖 3 个），`card` 模式补最小必需的 `card=103`，其余模式用缺省 opts。新增一种
会产 overlay 的模式时，这条测试自动跟着覆盖到。

## TDD 证据

RED（Finding 1 + 2，回退 tools/testboot.py 到 review 前的版本、保留新测试）：
```
$ git stash push -- tools/testboot.py
$ uv run pytest tests/test_testboot.py -v
tests/test_testboot.py::test_mainmenu_mode_emits_test_script PASSED
tests/test_testboot.py::test_scene_mode_targets_the_right_chapter_script PASSED
tests/test_testboot.py::test_card_mode_emits_short_circuit_overlay FAILED
tests/test_testboot.py::test_single_answer_card_has_no_warning FAILED
tests/test_testboot.py::test_generated_overlays_are_never_release PASSED
tests/test_testboot.py::test_generate_clears_stale_layers_from_previous_call FAILED
tests/test_testboot.py::test_unknown_mode_is_hard_failure PASSED

test_card_mode_emits_short_circuit_overlay:
    assert r["warnings"] and "多步骤" in r["warnings"][0]
E   KeyError: 'warnings'

test_single_answer_card_has_no_warning:
    assert r["warnings"] == []
E   KeyError: 'warnings'

test_generate_clears_stale_layers_from_previous_call:
    assert on_disk == sorted(r2["scripts"] + r2["overlays"])
E   AssertionError: assert ['overlays/ca...snr_test.lua'] == ['scripts/snr_test.lua']
E     + 'overlays/card-short-circuit.toml'（call 1 的残留，call 2 没清掉）

3 failed, 4 passed in 0.47s
$ git stash pop   # 恢复修复
```

GREEN（修复后）：
```
$ uv run pytest tests/test_testboot.py -v
tests/test_testboot.py::test_mainmenu_mode_emits_test_script PASSED
tests/test_testboot.py::test_scene_mode_targets_the_right_chapter_script PASSED
tests/test_testboot.py::test_card_mode_emits_short_circuit_overlay PASSED
tests/test_testboot.py::test_single_answer_card_has_no_warning PASSED
tests/test_testboot.py::test_generated_overlays_are_never_release PASSED
tests/test_testboot.py::test_generate_clears_stale_layers_from_previous_call PASSED
tests/test_testboot.py::test_unknown_mode_is_hard_failure PASSED
7 passed in 0.45s
```

Finding 3 的故障注入验证（临时改 `with = "{answer + 1}"`，验证断言真的会抓，
而不只是摆设）：
```
$ (patch: with  = "{answer}"  ->  with  = "{answer + 1}")
$ uv run pytest tests/test_testboot.py::test_card_mode_emits_short_circuit_overlay -v
>       assert ov["ops"][0]["with"] == "133"
E       AssertionError: assert '134' == '133'
1 failed in 0.11s
$ (revert)
$ uv run pytest tests/test_testboot.py -q
7 passed in 0.50s
```

Finding 4 的覆盖面验证：
```
modes covered by new _MODES-driven test: 8 ('font', 'scene', 'ruby', 'card', 'cutin', 'mainmenu', 'choices', 'map')
modes covered by old hardcoded tuple: 3 (mainmenu, card, scene)
```
逐模式实跑确认只有 card 产 overlay（其余 7 个 `overlays=[]`），新测试对全部
8 个都做了这层校验，不再只覆盖旧三元组挑中的那 3 个。

Finding 2 的 CLI 端到端复现（与 review 描述的场景一致：连续跑几个模式进同一个
缺省输出目录）：
```
$ uv run python tools/testboot.py --mode card --card 103 --out /tmp/x
--- files after call 1 ---
/tmp/x/overlays/card-short-circuit.toml
/tmp/x/scripts/snr_test.lua
$ uv run python tools/testboot.py --mode mainmenu --out /tmp/x
--- files after call 2 ---
/tmp/x/scripts/snr_test.lua        # overlays/ 已被清空，不再残留
```

## 两道闸（修复后）

```
$ uv run python tools/layers.py check --profile release --compare-compiled \
      .superpowers/sdd/2026-09-02-disc-layers-pipeline/gate-baseline-script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同
exit=0

$ uv run python tools/layers.py check --profile test
[layers] test: 施加 4 层（fonts, encore-menu, strip-ipl, boot-handoff），新增成员 1
[layers] 全部层命中 ✓
exit=0
```

`lua_scripts/` 只读核对：`git status --short lua_scripts/` 全程为空。

## 全量测试（修复后）

```
$ uv run pytest -q
1760 passed, 4 skipped in 303.84s (0:05:03)
exit=0
```

（基线 1753 → 首次实施 1758 → 本轮修复 1760，恰好等于新增的 2 条测试
`test_single_answer_card_has_no_warning`、`test_generate_clears_stale_layers_from_previous_call`；
跳过数 4 不变，无既有测试变红。）

## 文件改动（fix round 1）

- `tools/testboot.py`：`generate()` 内部重排（校验前置、写盘收尾、先清后写）；
  新增 `warnings` 返回键；`import shutil`；模块与函数 docstring 同步更新契约。
- `tests/test_testboot.py`：`test_card_mode_emits_short_circuit_overlay` 新增
  `count`/`with`/`warnings` 三条断言；新增
  `test_single_answer_card_has_no_warning`；`test_generated_overlays_are_never_release`
  改为遍历 `_MODES`；新增 `test_generate_clears_stale_layers_from_previous_call`。

## 结论（fix round 1）

4 项 Important 发现全部处理：结构化 `warnings` 通道已加（Finding 1）；
`generate()` 现在每次调用都会先校验、再一次性清空+重写它拥有的两个子目录，
磁盘实况与返回值严格一致，用 CLI 复现了 review 描述的原始场景确认修复生效
（Finding 2）；count/with 补了回归断言，并用故障注入验证了断言的真实抓取
范围，同时如实记录了这两条断言无法单独证明"count 照哪份源算"这件事（Finding 3）；
profile 钉子测试改由模块自身的模式表驱动，覆盖面从 3/8 变成 8/8（Finding 4）。
两道闸与相关既有测试套件复核通过，全量测试见上。
