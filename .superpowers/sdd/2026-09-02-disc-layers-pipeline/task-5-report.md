# Task 5 报告：inject_lua 瘦身与补测试

commit `f450584` — `refactor: inject_lua 收缩为纯注入——字体改写与编译各归其位`（单个
commit，含 `tools/inject_lua.py` + 新建 `tests/test_inject_lua.py`）。

## 实施内容

1. **`tests/test_inject_lua.py`（新建）**：brief Step 1 给出的 8 个测试逐字抄入，另加 3 个
   （见下方「brief 缺陷」）：`inject_tree` 的多文件分组 + 统计聚合、`inject_tree` 的纯函数性
   （不写盘、`stats` 不再含 `font_slot1`）、`load_translations` 改从
   `layers/manifest.toml` 的 `[lane].dir` 取车道目录的回归测试。共 11 个测试。
2. **`tools/inject_lua.py` 瘦身**：
   - 删 `FONT_SLOT1_FROM`/`FONT_SLOT1_TO` 两个常量 + `main()` 里那三行槽 1 改写——
     `layers/overlays/fonts.toml` 的第二个 `replace` 操作现在是槽 1 改写的唯一实现。
   - 删 `compile_bytecode()` 函数 + `LANE`/`OUT_SRC`/`OUT_BC`/`LUAC`/`PSP_LUAC_HEADER`
     五个常量；`import json/os/shutil/subprocess` 一并删（编译逻辑走后不再有调用点）。
   - 新增 `inject_tree(base_dir, ledger_rows, zh, extra) -> (dict[str,str], dict)`：按
     brief Step 3 给出的实现原样落地（分组、聚合统计、逐文件调 `inject_text`），是纯函数
     ——不读全局、不写盘、不编译。
   - `main()` 重写：`load_translations()` → `inject_tree()` → 按 `--only` 过滤后写到
     `--out`（缺省 `build/release/lua/injected`）。保留 `--only`（语义改为「只写这些文件，
     统计仍覆盖全部文件」，见下方「关注点」），去掉 `--no-compile`（编译已不在本文件）。
   - `load_translations()` 改为从 `tools.layers.load_manifest()` 的 `[lane].dir` 取车道
     目录，不再是本文件写死的 `LANE` 常量——这是 brief 未交代、我自行发现并补上的一处缺口
     （见下方「brief 缺陷」第 2 条）。
   - 模块 docstring 重写：反映「纯注入，字体/编译/车道路径各归其位」的新职责边界。
3. **未改动**：`inject_text`/`_inject_body`/`_sub_extra`/`_replace_span`/`merge_adjacent_ruby`/
   `lua_quote`/`ADJACENT_RUBY` 全部字节不变（`git diff` 可查——这些函数完全没出现在 diff 里）。

## 测试与结果

**目标测试**：
```
$ uv run pytest tests/test_inject_lua.py -q
...........                                                              [100%]
11 passed in 0.03s
```

**相邻套件**（layers 引擎 + 真语料 + build_ledger，因为本次改动新增了 inject_lua → layers
的模块依赖，且 `_injected_sources()` 直接消费 `load_translations`/`inject_text`）：
```
$ uv run pytest tests/test_layers.py tests/test_layers_corpus.py tests/test_inject_lua.py tests/test_build_ledger.py -q
........................................................................ [ 84%]
.............                                                            [100%]
85 passed in 2.52s
```

**全库**（后台跑，验证跨模块新依赖没有连带破坏其他任何测试）：
```
$ uv run pytest -q
1747 passed, 4 skipped in 302.59s (0:05:02)
```
4 个 skip 是既有的「这台机器缺某面字体/资产」跳过（`tests/conftest.py` 的
`needs_face_font`/`local_assets` 一类机制），与本次改动无关；0 failed，exit 0。

**CLI 真语料跑一遍**（brief Step 4 的验收口径）：
```
$ rm -rf /tmp/inj_check && uv run python tools/inject_lua.py --out /tmp/inj_check
[inject] 译文 vms=16749 extra=878
[inject] vms 替换 16749（缺译 0，账本外 0）；extra 替换 875（缺译/留空 0）；ruby 合并 6 次
[inject] 写出 229/229 个文件 → /tmp/inj_check
```
与 brief 期望的「vms 替换 16749（缺译 0，账本外 0）；extra 替换 875」逐字一致。
（875 而非 878：3 条 `savedataTitle` 第二参裁定留空，不计入替换也不计入缺译，是既有规则，
非本次改动引入。）

**`--only` 冒烟**（确认写盘过滤生效、统计仍是全树口径）：
```
$ uv run python tools/inject_lua.py --out /tmp/inj_only --only snr_common,snr_s1_10_s
[inject] vms 替换 16749（缺译 0，账本外 0）；extra 替换 875（缺译/留空 0）；ruby 合并 6 次
[inject] 写出 2/229 个文件 → /tmp/inj_only
$ ls /tmp/inj_only
snr_common.lua  snr_s1_10_s.lua
```

**槽 1 交接点验证**（task 描述里点名要求的证据）：
```
$ grep -n 'fontLoad(1,\|fontLoad(0,' /tmp/inj_only/snr_common.lua
4006:    fontLoad(0, "pgf/tsukuminpro_e_17.pgf")
4007:    fontLoad(1, "pgf/tsukuminpro_e_09.pgf")
```
两行都还是原始日文字体名——`inject_lua.py` 现在完全不碰字体行，`fonts.toml` 的两个 `replace`
操作在纯净基座上各自仍能找到锚点。

## 硬闸——本任务唯一验收判据

```
$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同
```
退出码 0。对工作区内的第二份基线副本
（`.superpowers/sdd/2026-09-02-disc-layers-pipeline/gate-baseline-script/`）重跑结果相同，
230/230，退出码 0。两份基线均只读，`git status`/`ls -la` 核对未被写入。

这条闸正是 task 描述点名的验证路径：`_injected_sources()` 直接 `from tools import inject_lua`
后调 `inject_lua.load_translations()`/`inject_lua.inject_text()`，两个名字签名未变，闸绿即
证明这条调用链完好；同时也证明 `fonts.toml` 第二个操作的锚点在「inject_lua 不再碰槽 1」之后
确实还能找到——如果我漏删了 `main()` 里的槽 1 改写，或者 `inject_text` 本身意外碰了字体行，
`_injected_sources()` 产出的源就会让 `fonts.toml` 的 `count=1` 断言撞见 0 命中，硬失败，闸
不可能绿。

## TDD Evidence

**RED**（写测试文件、跑，此时 `inject_lua.py` 还是修改前的样子）：
```
$ uv run pytest tests/test_inject_lua.py -q
ERROR collecting tests/test_inject_lua.py
ImportError: cannot import name 'inject_tree' from 'tools.inject_lua'
```
这是我在 brief 给的 8 个测试之外又加了 3 个（其中 2 个直接调用 `inject_tree`）之后的真实
collection 失败——`inject_tree` 在旧实现里确实不存在。

为了确认 brief 原有 8 个测试本身没有问题（不是它们侥幸被这次 ImportError 掩盖了潜在失败），
另外单独跑了一遍不经过 pytest collection、直接函数调用的等价检查，针对**修改前**的
`inject_text`/`lua_quote`/`merge_adjacent_ruby`：
```
$ uv run python -c "<8 个断言，见下方>"
PASS line_count_never_changes
PASS id_mismatch_hard_failure
PASS missing_translation_untouched
PASS non_literal_whole_expr
PASS tr_line_preserved
PASS lua_quote_escapes
PASS merge_ruby_joins
PASS merge_ruby_separated
ALL PASS
```
即 brief Step 2 预告的「大部分 PASS（这些函数已存在）」在这里是「全部 PASS」——这几个函数
本身没有缺陷，缺陷只在于 `inject_tree` 尚未被产出、以及 `load_translations` 的车道路径写死
（下面「brief 缺陷」详述）。

**GREEN**（Step 3 重构后）：
```
$ uv run pytest tests/test_inject_lua.py -q
...........                                                              [100%]
11 passed in 0.03s
```

## Files changed

- `tools/inject_lua.py`（修改，47 insertions / 62 deletions）
- `tests/test_inject_lua.py`（新建，111 行，11 个测试）

## 自评发现

1. **`inject_tree` 是真正的纯函数**：读了一遍最终 diff，函数体内没有引用任何模块级全局
   （不碰 `SRC`/`DEFAULT_OUT`/`REPO`），入参决定一切输出，唯一的副作用是从 `base_dir` 读盘
   （不写盘、不编译、不 print）。`test_inject_tree_is_pure_no_disk_writes_no_compile` 钉住
   「跑完 `base_dir` 目录下没多出任何文件」这一点。
2. **测试是否会真的抓到回归**：逐条自问「如果实现被改坏，这条测试会不会红」——
   - `test_inject_tree_walks_base_dir_and_aggregates_stats` 用两个不同文件、不同 id 的
     ledger 行：如果有人把 `by_file` 错写成不按 `row["file"]` 分组（比如全局拉平成
     `{line: row}`），这里两个文件会互相串用对方的 ledger 行，要么 id 不符触发
     `SystemExit`，要么 stats 数字对不上——两种坏法这条测试都会红。
   - `test_load_translations_reads_lane_dir_from_manifest` 用 `monkeypatch` 换一份指向
     `tmp_path` 假车道的假 manifest，断言读到的是假车道的译文而不是仓库真车道的——如果
     `load_translations` 退回硬编码路径，这条测试会因为读到完全不同（或者报错：假路径不存在
     真实车道文件）的数据而红，不会因为巧合撞对而绿。
3. **测试输出干净**：`-q` 跑法无 warning、无 print 残留；11/11、85/85 两轮都是干净的点号。
4. **没有遗留死常量/死 import**：`git diff` 通读一遍确认 `FONT_SLOT1_*`/`OUT_SRC`/`OUT_BC`/
   `LANE`/`LUAC`/`PSP_LUAC_HEADER`/`compile_bytecode` 全部消失，`json`/`os`/`shutil`/
   `subprocess` 四个只为这些死掉的代码服务的 import 一并删除（`json` 其实在改动前就已经是
   死 import，顺手一并清掉）。`grep -n` 复核仓库里再没有任何地方引用这些名字（除了我新写的
   docstring 里提到「不再是 LANE 常量」这句解释性文字本身）。
5. **模块 docstring 与实际职责一致**：重写后的开头段落明确写「纯注入」「字体槽改写归
   fonts.toml」「编译与出盘归 build_disc」「车道路径随 manifest.toml 走」——与代码现状对得上。

## brief 缺陷（本任务发现并修正的一处，另一处按 task 描述的指引直接生效）

**1.（本任务自行发现）Step 3 只交代「删掉 `LANE` 常量」，没交代 `load_translations()` 删完
`LANE` 之后怎么找车道目录——照抄会当场 `NameError`，而 `load_translations()` 是
`tools/layers.py::_injected_sources()` 直接调用的两个「契约函数」之一，一旦炸掉，本任务
唯一的验收判据（硬闸）就没法跑。**

设计稿 `docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md` §6.7 与
`§12` 第 9 条早已把「车道路径在 inject_lua / build_font / migrate_base 三处写死」列为
待解决的已知问题，且 `layers/manifest.toml` 本就有 `[lane] dir = "pilot/lanes/opus/data"`
——这条基础设施已经在 Task 2/4 里建好，只是没人在 inject_lua 这边接上。我把
`load_translations()` 改成 `lane = REPO / load_manifest()["lane"]["dir"]`（`tools.layers`
新增的模块级 import），行为对生产环境完全不变（manifest 里写的就是同一个
`pilot/lanes/opus/data`），但车道路径不再是本文件独有的硬编码副本。用
`monkeypatch.setattr(inject_lua_mod, "load_manifest", ...)` 补了回归测试
（`test_load_translations_reads_lane_dir_from_manifest`）钉住这条改线本身。

`tools.inject_lua` 在模块级 `import` `tools.layers`，`tools.layers._injected_sources()`
在函数体内才 `from tools import inject_lua`（延迟导入）——两个方向都检查过，确认不构成
循环导入（`layers.py` 顶层没有任何地方在模块加载时就需要 `inject_lua`）。

**2.（按 task 描述指引处理，未独立发现）`LUAC` 常量的空串环境变量脆弱性
（`os.environ.get("SNDL_LUAC", 默认值)` 两参形式，`SNDL_LUAC=""` 时会绕过默认值拿到
`Path("")` → 归一化成当前目录）——本次把 `LUAC`/`compile_bytecode()` 整个删除（编译职责
搬去 build_disc），问题随常量一起消失，不需要在本文件里改成 `os.environ.get(key) or
default` 的写法。** `tools/build_font.py:39` 仍有同款写法，按 task 描述明确交代「不要碰
build_font.py，后续任务处理」，未动。

## LUAC 常量是否存活

**没有存活**——随 `compile_bytecode()` 一起整体删除（编译已不是本文件职责，搬去
`tools/build_disc.py`，该文件已有自己独立的 `LUAC` 常量且不共享本文件的实例）。空串环境
变量的隐患因此不复存在于本文件；`tools/build_font.py:39` 的同款隐患仍在，按要求未处理，
留给后续任务（progress.md 已有「Task 5（inject_lua）与 Task 6（build_font）派工时须一并
带上」的转达记录，Task 6 那边应该会处理 build_font 自己的实例）。

## 关注点

1. **`--only` 的语义发生了变化**（不影响任何测试或下游工具，但如实记录）：改动前，
   `--only` 过滤的是「对哪些文件跑 `inject_text`」，未选中的文件仍会被写到输出目录（只是
   保留日文原文）；改动后，`inject_tree()` 总是对整棵基座跑完整注入（它本就该是一次性、
   全量的纯函数调用），`--only` 只过滤「最终写哪些文件到 `--out`」，未选中的文件根本不落盘。
   统计口径不受影响（`stats` 永远是全树聚合，不随 `--only` 变化，这点比改动前更准确——改动
   前 `--only` 会让被排除文件的 vms 行全部计入 `vms_unledgered`，是噪声）。仓库内没有任何
   代码或文档依赖旧语义（已 grep 确认），纯属这个调试参数自身行为的微调。
2. **`tools/make_test_boot.py:504` 硬编码读 `build/inject_src/snr_common.lua`**（旧
   `OUT_SRC` 路径），而 `inject_lua.py` 的默认 `--out` 现在是
   `build/release/lua/injected`。这个文件不在本任务范围内（design doc 里它是 Task 7
   `make_test_boot.py → testboot.py` 的整体改造对象，且没有任何测试跑到这条路径——已用
   `grep -rln` 确认 `tests/` 下没有文件引用 `make_test_boot`），但如实记录：现在手工跑
   `uv run python tools/make_test_boot.py ...` 之前，需要先手工 `uv run python
   tools/inject_lua.py --out build/inject_src` 把老路径的文件产出来，不能再依赖
   `inject_lua.py` 不带参数的默认行为。留给 Task 7 处理（或者谁先手动用到 make_test_boot
   就得知道这一点）。
3. **`layers/overlays/fonts.toml` 的 `why` 字段现在部分过期**：它写着「等瘦身 inject_lua
   的任务把 FONT_SLOT1_FROM/TO 删掉……之后，这个层才真正独占槽 1 的改写权」——这个条件现在
   已经满足，但 `why` 里描述"两者不能同时跑一遍"的过渡期警告文字还留着没更新。`layers/`
   下的文件不在本任务「Files: Modify」范围内，没有动它；留给下一个碰这个文件的任务顺手
   更新几句话（不影响任何机器可读的行为，`why` 只是校验非空，不校验内容）。
4. **`_injected_sources()`（`tools/layers.py`）没有改成调用新增的 `inject_tree()`**——
   两者现在逻辑重复（都是「按 (file,line) 分组 ledger 行，逐文件调 inject_text」），但
   `tools/layers.py` 不在本任务「Files: Modify」范围内，task 描述也只要求「两个名字的签名
   不变」，没有要求重构调用方。如实记录，留给后续任务判断是否值得去重（progress.md 里
   Task 4 已经记过一条相关的 deferred minor：「_injected_sources 每文件新建 stats 并
   丢弃」）。
