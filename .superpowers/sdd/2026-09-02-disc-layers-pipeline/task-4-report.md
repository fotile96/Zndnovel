# Task 4 报告：基座纯净化与叠加承接

commit `f9b4b40` — `refactor: 基座纯净化——lua_scripts 回到与原字节码等价，改动全部成层`（单个 commit，含全部改动）。

## 实施内容

1. **Step 1（基线）**：已由控制器预先捕获，跳过，未触碰 `/tmp/layers_baseline/script` 与
   `gate-baseline-script/` 两份副本。
2. **四个层文件**：
   - `layers/overlays/fonts.toml`：2 个 `replace`，槽 0/槽 1 字体路径。
   - `layers/overlays/encore-menu.toml`：7 个操作，见下方「brief 缺陷」——第 4 个操作的锚点与
     count/occurrence 与 brief 表格不同，已按实测修正。
   - `layers/overlays/strip-ipl.toml`、`layers/overlays/boot-handoff.toml`：与 brief 给出内容一致，
     锚点已对纯净基座逐一实测（count 1/1、8）。
3. **`layers/manifest.toml`**：照 spec §6.1 全文写出；`layers/vms_ids.toml`：登记 `scripts/snr_finale.lua`
   的 vms 17300–17481、card_msg 18201–18207。
4. **`git mv docs/finale/snr_finale.lua layers/scripts/snr_finale.lua`**，`lua_scripts/snr_common.lua`
   与 `lua_scripts/snr_mainmenu.lua` 用 `tools.migrate_base.add_tr_line_markers` 对
   `~/pyluadec-refactor/corpus/final/` 重生成，覆盖今天的手工改动。
5. **`tools/luac_norm.py`**：抽出 `compare_dirs(a, b) -> (same, diff, err, names)`，`main()` 改为调用它。
6. **`tools/migrate_base.py`**：删 `FONT_PATCH` 常量与其重放逻辑（三行 + 常量定义），换成一行注释指向
   `layers/overlays/fonts.toml`；加 `--check`（断言 `lua_scripts == 语料 + tr_line 标记`，不落盘）。
7. **`tools/layers.py`** 新增 `build_final_sources()`、CLI（`check`/`diff`/`ids`）、`_compare_compiled()`，
   以及 brief 之外新增的 `_injected_sources()`（见下方「brief 缺陷」第 2 条）。
8. **两个新测试文件**：`tests/test_layers_corpus.py`（真语料，7 个测试，含 1 个我加的
   `test_injected_sources_translates_and_skips_old_font_patch`）、`tests/test_base_fidelity.py`
   （`local_assets`，3 个测试）。`pyproject.toml` 追加 `local_assets` marker。
9. **Ruling 1**：`tools/build_disc.py:94` 的 `FINALE_LUA` 改指 `layers/scripts/snr_finale.lua`，文件
   其余部分未动（已用 `git diff tools/build_disc.py` 核对，仅这一处 + 两行注释）。

## 硬闸——本任务唯一验收判据

```
$ uv run python tools/layers.py check --profile release
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 全部层命中 ✓

$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同
```

退出码均为 0。对第二份基线副本（`.superpowers/sdd/2026-09-02-disc-layers-pipeline/gate-baseline-script`）
重跑结果相同；对同一目录重复跑两次结果稳定；commit 之后又重跑一次确认不受提交动作影响，仍
230/230。

## brief 缺陷（本任务发现并修正的两处）

**1. encore-menu.toml 第 4 个操作的锚点在基座里命中 2 次，不是 brief 表格写的 1 次。**
用 `grep -n "elseif l1_0 == l0_1.library then" lua_scripts/snr_mainmenu.lua`（对纯净基座）实测：
第 662 行（菜单形态 2，无 140）与第 838 行（形态 2+140，section7 分支之后）两处缩进相同、文本
完全相同。若照 brief 表格写 `count=1` 直接跑，`select_indices` 会在 `len(hits) != count` 处硬失败
（不是静默错位——这点值得肯定，闸设计得住）。修法：保留 brief 给的 `insert_before` op 类型与锚点
文本，改 `count=2, occurrence=-1`，钉住"最后一处"，也就是紧跟在 section7 CIRCLE 分支之后、真正
要插入 finale 分发的那一处；形态 2（无 140）的那处从未被今日手工改动触碰，不该被殃及。

验证方法：在写死 TOML 之前，先用 Python 直接构造两版 overlay dict 跑 `apply_overlay`——第一版
（brief 原样，`insert_before` 锚点为 `run(...) + quit() + elseif...library then` 三行合一）验证时发现
把 finale 分发块插到了错误位置（在 `run(s7_10_f)` 之前而非之后），改用 `count=2, occurrence=-1`
后，比对"注入真译文后 apply_overlay 的输出" 与"当年手工改动 + 注入"编译出的字节码，
`luac_norm.normalize()` 与**原始未归一化字节**都逐字节相同（后者更强，证明连行号都没有偏移）。

**2. `check --compare-compiled` 按 brief 原样实现（`build_final_sources(args.profile)` 不传
`injected`）不可能达到 230/230。** 诊断：`/tmp/layers_baseline/script` 是**真实发布链路**编出的
字节码——实测其 `snr_s1_10_s.lua` 含"那个人""就是我偶尔会空想出来的"等中文译文，不是日文原文。
而 `build_final_sources` 缺省 `injected=None` 时读的是 `lua_scripts/` 原文（日文，未翻译）——两者
直接比对，凡含对白的文件必然不同。空手编译一份基座原文的 `snr_s1_10_s.lua` 与基线逐字节比对，
证实二者天差地别（221411 字节 vs 198257 字节，`compare_dirs` 判定不同）。

修法：新增 `_injected_sources(manifest, ledger_rows)`，复用（不重新实现）`tools/inject_lua.py` 已经
在用的 `load_translations()`/`inject_text()`，在内存里把基座原文换成真译文，且刻意**不**重放
`inject_lua.py` 里那段槽 1 字体补丁（`FONT_SLOT1_FROM/TO`）——那一步已转交 `fonts.toml`；两处都做的
话，fonts 层的 `find` 锚点在注入后就找不到了（会被 `select_indices` 的 count 断言硬拦下，不会静默
叠两次）。CLI 只在 `--compare-compiled` 时调用它换出真译文源；`check`（不带 compare-compiled）、
`diff`、`ids` 三条路径不需要这份较重的依赖（要读 `pilot/lanes/opus/data/*` 三个车道文件），仍走
`build_final_sources(profile)` 缺省的快速路径——这与 `build_final_sources` 文档字符串里"缺省时读基座
原文（只验层用，不产盘）"的定位一致，没有改变那个函数本身的契约，只是让 CLI 在需要"产出能验证的
真实内容"时明确供料。

顺带在 `build_final_sources` 里修了一个真值判断的边界 bug：`dict(injected) if injected else {...}`
——传空字典 `{}` 会被当成"没传"而悄悄退回读基座原文，与调用方的预期不符（空字典也是"调用方给了
sources，只是恰好为空"）。改成 `injected is not None else`。今天没有调用方会传空字典，但这与本文件
到处可见的"正确性问题硬失败、不留歧义分支"的写法不一致，顺手一并修了。

## 测试

### `uv run pytest tests/test_layers.py tests/test_layers_corpus.py tests/test_base_fidelity.py -q`

```
.......................................................                  [100%]
55 passed in 1.61s
```

45（既有）+ 10（新增：corpus 7 个、base_fidelity 3 个）= 55，全绿，0 skip。

### TDD 证据（新测试文件）

RED：用 `git stash push --keep-index -- tools/layers.py` 把 `tools/layers.py` 临时退回本任务开始前
（无 `build_final_sources`/`_injected_sources`），跑新测试文件：

```
$ uv run pytest tests/test_layers_corpus.py tests/test_base_fidelity.py -q
ERROR collecting tests/test_layers_corpus.py
E   ImportError: cannot import name 'build_final_sources' from 'tools.layers'
ERROR collecting tests/test_base_fidelity.py
E   ImportError: cannot import name 'build_final_sources' from 'tools.layers'
2 errors in 0.06s
```

GREEN：`git stash pop` 还原后重跑：

```
$ uv run pytest tests/test_layers_corpus.py tests/test_base_fidelity.py -q
..........                                                               [100%]
10 passed in 1.41s
```

stash/pop 全程只动 `tools/layers.py`（新增的 TOML/测试文件本身不受影响，`git mv` 的暂存态用
`--keep-index` 保住）；`pop` 之后逐函数核对 `grep -n "def build_final_sources\|def _injected_sources"`
确认还原完整，再重跑三件套测试与硬闸各一次，结果与 stash 前一致（55 passed；230/230）。

### `uv run python tools/luac_norm.py /tmp/base_compiled build/databin/script`

```
归一化后相同 229；不同 0；解析失败 0
```

（`/tmp/base_compiled` = 用 `~/pyluadec-refactor/build/luac_sz4` 编译 `lua_scripts/` 全部 229 个文件
的产物；此命令等价于 `tests/test_base_fidelity.py::test_base_is_byte_identical_to_original_bytecode`
内部做的事，该测试同样通过。）

### `uv run python tools/build_ledger.py --check`

```
check: OK
```

符合预期——两个改动文件的全部 hand-edit 区域都在最高账本锚点行之后（progress.md 记录：snr_common
插入点 4022 > 最大锚 3573；snr_mainmenu 改动区 L177+ 仅 L79 键在前），还原基座不影响任何 (file,line)
→id 映射。

### `python3 tools/extract_dag.py | diff -q - analysis/dag_all.txt` / 同理 `extract_crd.py`

两条 diff 均无输出，退出码 0——DAG 与卡片谜题分析产物不受本次基座还原影响（谢幕入口本就不进
storyRoute、不产生卡片谜题）。

### `uv run pytest -q -m "not emu"`

```
1730 passed, 3 skipped, 6 deselected in 300.27s (0:05:00)
```

exit 0。3 个 skip 与本任务无关（`SourceHanSansSC-VF.ttf` 缺失、`ZND_*_FULL` 环境变量未设等既有
条件跳过，抽查 `grep -rn "pytest.skip(\|skipif" tests/` 确认，均在本任务未触碰的测试文件里）。
Ruling 2 提到的 `build_font` 测试确实不在这次全套里——符合预期，非缺口。

### `uv run python tools/migrate_base.py --check`

```
[migrate] 新基座 229 文件 / 现有 229 文件
[migrate] 基座纯净 ✓（229 文件 == 语料 + tr_line 标记）
```

## 文件改动

```
 layers/manifest.toml                           |  35 ++++++
 layers/overlays/boot-handoff.toml              |  12 ++
 layers/overlays/encore-menu.toml               | 123 ++++++++++++++++++++
 layers/overlays/fonts.toml                     |  16 +++
 layers/overlays/strip-ipl.toml                 |  11 ++
 {docs/finale => layers/scripts}/snr_finale.lua |   0   (git mv, 内容不变)
 layers/vms_ids.toml                            |   6 +
 lua_scripts/snr_common.lua                     |   2 +-
 lua_scripts/snr_mainmenu.lua                   |  65 ++---------
 pyproject.toml                                 |   1 +
 tests/test_base_fidelity.py                    |  66 +++++++++++
 tests/test_layers_corpus.py                    |  87 +++++++++++++++
 tools/build_disc.py                            |   4 +-
 tools/layers.py                                | 148 +++++++++++++++++++++++++
 tools/luac_norm.py                             |  20 ++--
 tools/migrate_base.py                          |  25 +++--
 16 files changed, 546 insertions(+), 75 deletions(-)
```

未触碰任何其他基座文件（`git diff --cached --stat` 确认只有 `snr_common.lua`/`snr_mainmenu.lua` 两个
`lua_scripts/*.lua`）。五个"另一 session 遗留改动"文件（`.claude/settings.json`、
`data/api_ledger.jsonl`、`data/event_op_text.jsonl`、`pilot/read-edits/opus.draft.jsonl`、
`tools/bake_event_op.py`）与 `progress.md` 均未 `git add`，commit 后 `git status --short` 确认仍是
仅剩这六个文件处于未暂存状态。

## 自我审查

- **基座是否真的纯净**：`tools/migrate_base.py --check` 与 `luac_norm.compare_dirs`（229/229）双重
  确认；额外用 `diff -u` 逐字对比过 `~/pyluadec-refactor/corpus/final/{snr_common,snr_mainmenu}.lua`
  经 `add_tr_line_markers` 处理后的产物与还原后的 `lua_scripts/` 同名文件，逐字节相同。`git diff --cached
  --stat` 确认没有第三个基座文件被误touch。
- **每个叠加层的 `why` 是否讲清楚未来维护者需要的理由**：四个层都写了；`encore-menu.toml` 额外用
  一整段解释了 op4 的 `count=2/occurrence=-1`（否则未来维护者看到"就 2 处一样的文本却只改一处"会
  很困惑，必须讲清楚为什么另一处不能碰）。
- **新测试是否验证行为而非复述实现**：`test_layers_corpus.py` 的新增测试断言"确实翻译了"（
  `injected["snr_s1_10_s.lua"] != pristine`，用重头故事章节而非挑一个可能零覆盖的文件）与"确实没有
  重放槽 1 补丁"（`fontLoad(1, "pgf/tsukuminpro_e_09.pgf")` 原样在场，这是它还没被两次改写的证据，
  不是抄实现的字面判断）；`test_base_fidelity.py` 三个测试全部来自 brief，逐一核对过其断言确实在测
  行为（编译成功、字节码等价、CLI 退出码）而非纯结构。
- **测试输出是否干净**：全部命令实测过，附在报告里的输出块是逐字复制的终端输出，没有警告/deprecation
  噪音。
- **是否有 brief 未预料的改动**：`tools/build_disc.py`（Ruling 1 明确要求，只改一行 + 两行注释，
  已用 `git diff` 核对无旁溢）；`tools/layers.py` 里的 `_injected_sources()` 与 `build_final_sources`
  的真值判断修正（brief 之外新增，理由见上「brief 缺陷」第 2 条，已在报告与 commit message 里如实
  说明，未悄悄埋进 diff）。

## 顾虑

1. **`tools/build_disc.py` 的真实发布管线目前尚未接入 `layers/`**：这是本任务刻意的范围边界（spec
   §8 步骤 3 才做"build_disc 剖面化"），但意味着**如果现在有人不经改造直接跑一次
   `uv run python tools/build_disc.py`**，产出的盘会退步——`lua_scripts/snr_common.lua` 不再硬编码
   槽 0 中文字体路径（已纯净化），而 `tools/inject_lua.py` 从未负责槽 0（它只有槽 1 的
   `FONT_SLOT1_FROM/TO`），也完全不知道 `encore-menu.toml`。也就是说，此刻若跑真实构建，会拿到一个
   **槽 0 是日文字体、且没有 encore 菜单入口**的盘。Ruling 1 只要求我改 `FINALE_LUA` 那一行（否则
   连 `snr_finale.lua` 都找不到，是立即的崩溃），并明确"不要动这个文件的其他部分"——所以这个 gap
   是已知且刻意留给下一任务的，我没有去补，只在此处标注清楚，供编排方决定是否需要在下一任务落地前
   暂停真实构建。
2. **`_injected_sources()` 是本任务在 brief 之外新增的函数**：我认为这是必要的缺陷修正而非范围蔓延
   （没有它，Step 9 的硬闸原样跑不出 230/230，已用空跑实测证实），但它确实让 `tools/layers.py` 的
   CLI 多了一条依赖真实车道数据的路径。已把推理过程、诊断证据、和为什么不作为 `build_final_sources`
   默认行为的理由都写进代码注释与本报告，供复核。

---

## Fix round 1（2026-09-03，回应 review 的四个 Important 发现）

commit `a054ac5` — `fix: 硬化 --compare-compiled 闸 + 更正 fonts why + 钉住 op4 落点 + 迁移期 guard`。

Review 结论是 Approved，独立验证了两处 brief 缺陷修正（occurrence=-1 落点、复用 inject_lua 的理由），
同时指出四个 Important。四个都真实存在，逐条修复如下。

### Finding 1（闸能在没测的情况下打印"通过"）——`tools/layers.py:_compare_compiled`

**(a) 缺 luac 静默跳过。** 原代码 `if not luac.exists(): print("跳过比对"); return 0`——退出码 0
正是自动化唯一读的信号，静默跳过让"本任务唯一验收判据"在没装编译器的机器上变成永远绿灯。改为
`sys.exit(...)`：硬失败，消息里给出补救办法（设 `SNDL_LUAC` 或装编译器）。

**(b) 比对只单向查名字。** 原代码只按 `sources` 里已有的名字去 `ref_dir` 查（`for name, text in
sorted(sources.items())`），从未检查 `ref_dir` 里有没有 `sources` 缺的名字。具体失效场景：
`manifest.toml` 的 `[[scripts]]` 若把 `profile` 手滑写成 `"test"`，`build_final_sources` 会在 release
剖面悄悄跳过 `snr_finale.lua`（`tools/layers.py:441-442` 的 `if spec.get("profile", "release") ==
"test" and profile != "test": continue`），`sources` 从 230 降到 229；旧代码的分母 `len(sources)`
跟着降到 229，"229/229 相同"照样打印、退出码照样 0——盘会丢整个谢幕章，闸却说过了。

修法：改成先算 `ref_names = {p.name for p in ref_dir.glob("*.lua")}` 与 `src_names = set(sources)`
的双向集合差，任何一侧独有的名字都计入 `bad`（分别标注"参照目录有、新链路缺失"与"新链路有、参照
目录没有"，方向不同、原因不同，消息分开写）；分母改成 `len(src_names | ref_names)`（并集，不再用
可能已经缩水的 `len(sources)`），分子 `same` 只在真正逐字节相同时才计数（不再用减法反推）。

**验证（Finding 1 要求的证据，硬化后的闸确实在该失败时失败）：**

```
$ rm /tmp/layers_baseline_missing_one/snr_finale.lua   # 从基线副本删掉一个文件，模拟漏收成员
$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline_missing_one
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] ✗ 新链路有、参照目录没有: ['snr_finale.lua']
[layers] 逐字节比对：229/230 相同
exit=1
```

```
$ cp .../snr_finale.lua .../zzz_phantom_member.lua   # 基线副本里塞一个新链路没有的文件
$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline_extra_one
[layers] ✗ 参照目录有、新链路缺失（漏收了整份文件）: ['zzz_phantom_member.lua']
[layers] 逐字节比对：230/231 相同
exit=1
```

```
$ SNDL_LUAC=/tmp/nonexistent_luac_binary uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 缺 /tmp/nonexistent_luac_binary，--compare-compiled 无法比对——这是迁移期唯一验收判据，不许静默跳过（设 SNDL_LUAC 指到别处，或按 docs 装上编译器）
exit=1
```

三个场景全部正确失败（exit 1），且消息点名具体原因，不再有"看起来过了"的假阳性路径。硬化之后正常
路径仍是 230/230、exit 0（见下方复验）。

### Finding 2（fonts.toml 的 why 断言了假话）——`layers/overlays/fonts.toml`

原 `why` 说"槽 1 由 inject_lua 改写……现在合并到这一个层里"——只有槽 0 那半是真的。实测
`tools/inject_lua.py:209-211` 的 `FONT_SLOT1_FROM/TO` 这次改动完全没碰，槽 1 至今仍由它在**真实
发布链路**（`build_disc.py` 调用 `inject_lua.py` 的那条路径）里改写；这个层的槽 1 操作现在只在
`tools/layers.py` 的 `_injected_sources()`（`--compare-compiled` 专用，刻意绕过 `inject_lua.main()`
只调 `inject_text()`）里生效。

重写 `why`：明确槽 0 已完整转移（`migrate_base.py` 的 `FONT_PATCH` 已删），槽 1 此刻仍是
`inject_lua.py` 独占、这个层只在验证路径里生效，等瘦身 `inject_lua` 的任务删掉
`FONT_SLOT1_FROM/TO` 并把 `build_disc` 接入 `layers/` 之后才真正移交；并写明两者当前不能对同一份
源都跑一遍（后跑的那个 `find` 会因锚点已被替换而命中 0 次，被 `count` 断言硬拦，不是静默叠加）。

验证：`tomllib` 重新解析该文件确认仍合法（`why` 长度从 133 字增到 774 字）；`tests/test_layers.py`
与 `tests/test_layers_corpus.py` 全部重跑，硬闸重跑，均无变化（见下方复验）。

### Finding 3（op4 落点没有不依赖临时基线的证据）——`tests/test_layers_corpus.py`

新增 `test_finale_dispatch_lands_in_the_card_140_menu_form`：断言 `elseif l1_0 == l0_1.finale then`
在装配出的 `snr_mainmenu.lua` 里只出现 1 次，且其字符串下标必须大于 `doScriptScene = "s7f-10"` 的
下标（后者只存在于卡 140∧144 那条 CIRCLE 链路里，形态 2 没有 section7 分发）。不依赖
`/tmp/layers_baseline` 或 SDD 工作区那份 gitignore 副本——两者都会随环境销毁而永久消失，届时唯一
还钉在仓库里的证据就是这条断言。

顺手核对了 review 引用的两个具体锚点是否与代码一致：`grep -n` 确认无卡 140 的形态在
`/tmp/pristine_dryrun/snr_mainmenu.lua:668` 确实用 `for l1_7 = 1, #l0_0.layerKey2, 1 do` 退场，
卡 140∧144 形态在 `:845` 确实用写死的 `for l1_7 = 1, 11, 1 do`（op5 改的正是这一行）——与 review
的描述一致。

**TDD 证据（这条测试真的会抓到装错形态，不是摆设）：**

```
$ sed -i 's/occurrence = -1/occurrence = 1/' layers/overlays/encore-menu.toml   # 故意选错第一处
$ uv run pytest tests/test_layers_corpus.py::test_finale_dispatch_lands_in_the_card_140_menu_form -v
...
>       assert finale_at > s7f_at, (
E       AssertionError: finale 分发出现在 section7 分发（doScriptScene = "s7f-10"）之前——说明 op4 把它插进了没有 section7 的菜单形态（形态 2，无卡 140），而不是卡 140∧144 那条唯一持有 layerKey4/finale 枚举的分支；去查 encore-menu.toml的 count/occurrence 是不是又选中了第一处而非最后一处
E       assert 31618 > 39855
FAILED
```

```
$ cp /tmp/encore-menu.toml.bak layers/overlays/encore-menu.toml   # 复原
$ uv run pytest tests/test_layers_corpus.py::test_finale_dispatch_lands_in_the_card_140_menu_form -v
tests/test_layers_corpus.py::test_finale_dispatch_lands_in_the_card_140_menu_form PASSED
$ git diff layers/overlays/encore-menu.toml   # 确认复原后与已提交版本逐字节相同
（无输出）
```

### Finding 4（退步构建路径没有护栏）——`tools/build_disc.py:stage_lua`

`build_disc.py` 至今仍直接读 `lua_scripts/`、对 `layers/` 一无所知。此刻若有人跑
`uv run python tools/build_disc.py`，会拿到槽 0 是日文字体、没有 encore 菜单入口的盘，且不会有
任何报错——"看起来正常的盘，其实是错的"是本任务范围内能造成的最坏后果。在 `stage_lua()`（inject
阶段的入口，`STAGES` 字典里 `"lua"` 阶段的处理函数）开头加 `die(...)`，讲清楚：现状（已迁移到
`layers/` 但本文件未接入）、后果（槽 0 日文字体、无 encore 入口、零报错）、解除条件（"build_disc
剖面化"任务接好 `layers/` 后删除，附 design doc §8 步骤 3 的路径）。除这几行外未碰该文件其余部分
（`git diff` 确认，只有 `stage_lua` 内部新增 14 行）。

踩过一个坑：第一次实现时在**外层 Python 补丁脚本**的三引号字符串里直接写了 `"\n".join(...)`——
外层脚本自己的三引号字符串会把其中的 `\n` 解释成真实换行符，而不是字面的反斜杠+n 两个字符，导致
写进 `build_disc.py` 的源码里出现了一个裸露的真实换行、把 `die("` 和 `.join([` 断成两行、字符串
字面量提前截断——`python3 -c "import ast; ast.parse(...)"` 当场报
`SyntaxError: unterminated string literal`。改法：`git checkout -- tools/build_disc.py` 撤回，换成
在外层脚本里用一个 Python **列表**拼多行源码文本（每行是完整的 `"..."` 字面量，不在任何三引号
字符串内部含 `\n` 转义），再 `"\n".join(...)` 得到要写入的文本——这次 `\n` 是外层脚本自己
真正需要的换行，不是要原样保留的字符序列，二者不再混淆。

验证：

```
$ uv run python -c "
from tools import build_disc
build_disc.stage_lua()
"
[退出，SystemExit，消息见下]
[build_disc] 错误: build_disc.py 处于管线迁移中期，尚未接入 layers/。lua_scripts/ 已纯净化
（2026-09-02 commit f9b4b40）：槽 0 中文字体行、主菜单谢幕直达项都已经从 lua_scripts/ 搬进
layers/overlays/*.toml，这个文件还在直接读 lua_scripts/，对 layers/ 一无所知。现在跑这条管线
会静默产出一张退步的盘：槽 0 是日文字体、没有 encore 菜单入口，且不会有任何报错或警告——盘看起来
正常，其实是错的。等「build_disc 剖面化」任务把 layers/ 接进来后，删掉这段 guard 即可（design doc
§8 步骤 3：docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md）。
```

`grep -rn "stage_lua\|build_disc" tests/` 确认没有任何既有测试调用这个函数，guard 不会破坏
既有测试（也确实没有——见下方全套复验）。

### 顺带清理（同一文件里顺手做）

- `tests/test_layers_corpus.py`：删掉未用的 `overlays_for` 导入；两个从不读 `manifest` 参数的测试
  函数改成无参；`test_finale_ids_are_inside_declared_range` 改成从 `layers/vms_ids.toml` 现读
  `[17300, 17481]`，不再字面写死——含义变成"脚本没有越出登记表声明的段"而不是"这两个具体数字"，
  日后正当扩段不会反过来打这条测试的脸。
- `tests/test_base_fidelity.py`：`LUAC` 补 `SNDL_LUAC` 环境变量覆盖（与 `provenance()`/
  `_compare_compiled()` 同惯例）——原先硬编码路径，会导致"只能靠 `SNDL_LUAC` 才找得到编译器"的
  机器上，全库最强的保真测试反而 skip，而同样吃这个变量的 CLI 却能正常跑；新增
  `PSP_LUAC_HEADER = bytes.fromhex(_MANIFEST["compiler"]["header_hex"])`，从
  `layers/manifest.toml` 读，不再和 manifest 里已经声明过的同一个头字面量二次写死一份。
  两处都手工验证过 override 确实生效（`SNDL_LUAC` 指向真编译器/指向不存在的路径，分别得到
  3 passed / 3 skipped，而不是硬编码路径下恒定的行为）。

### 复验（全部命令与输出）

```
$ uv run python tools/layers.py check --profile release
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 全部层命中 ✓

$ uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同

$ uv run python tools/layers.py check --profile release --compare-compiled .superpowers/sdd/2026-09-02-disc-layers-pipeline/gate-baseline-script
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 逐字节比对：230/230 相同
```

均退出码 0；commit 前后各跑一遍结果一致。

```
$ uv run pytest tests/test_layers.py tests/test_layers_corpus.py tests/test_base_fidelity.py -q
..........................................................
56 passed in 1.57s
```

45（既有）+ 8（corpus，含新增的 op4 落点断言）+ 3（base_fidelity）= 56。

```
$ uv run pytest -q -m "not emu"
1731 passed, 3 skipped, 6 deselected in 300.11s (0:05:00)
```

exit 0；1731 = fix round 之前的 1730 + 本轮新增的 1 个测试。3 个 skip 与本轮改动无关（沿用 fix
round 之前已核实过的 `ZND_*_FULL`/字体文件缺失等既有条件跳过）。

```
$ uv run python tools/luac_norm.py /tmp/base_compiled build/databin/script
归一化后相同 229；不同 0；解析失败 0

$ uv run python tools/build_ledger.py --check
check: OK

$ python3 tools/extract_dag.py | diff -q - analysis/dag_all.txt   # 无输出
$ python3 tools/extract_crd.py | diff -q - analysis/crd_summary.txt   # 无输出
```

lua_scripts/ 本轮完全未改动，这几项理应不变，实测确认不变。

### 文件改动（fix round 1）

```
 layers/overlays/fonts.toml  | 18 +++++++++++++++--
 tests/test_base_fidelity.py | 16 ++++++++++++---
 tests/test_layers_corpus.py | 47 +++++++++++++++++++++++++++++++++++++++++----
 tools/build_disc.py         | 14 ++++++++++++++
 tools/layers.py             | 45 ++++++++++++++++++++++++++++++++++---------
 5 files changed, 122 insertions(+), 18 deletions(-)
```

五个"另一 session 遗留改动"文件与 `progress.md` 本轮同样未 `git add`；`git status --short` 复核确认
commit 后仅剩这六个文件处于未暂存状态，与 fix round 之前一致。

### 遗留顾虑（未变化，仍然成立）

Finding 4 的 guard 只是挡住"现在跑会静默产出错盘"，没有让 `build_disc.py` 变得能用——它下一次被
正确调用仍要等"build_disc 剖面化"那个任务把 `layers/` 真正接进去。这在原报告里已经作为顾虑写明，
本轮只是把"知道会错但没挡住"变成"知道会错、而且直接挡住"，范围边界本身没有变。
