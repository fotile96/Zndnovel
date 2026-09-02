# Task 2 报告：清单与 id 登记的加载与校验

## 实现内容

按 brief 逐字追加到 `tools/layers.py`（`apply_overlay` 之后）与 `tests/test_layers.py`（16 个既有测试之后），未做任何改写：

- `load_overlay(path) -> dict`：读单个叠加层 TOML，校验未知键、`target`/`profile`/`why` 非空、`profile ∈ {release, test}`、`ops` 非空；设 `_name = path.stem`。
- `load_manifest(root=LAYERS) -> dict`：读 `manifest.toml`，校验未知顶层键、必需的 `[base]/[lane]/[compiler]/[overlays]` 四节存在、`overlays.order` 与 `layers/overlays/*.toml` 文件名集合完全一致（不一致时报错信息同时列出 order 与 on-disk 两个集合）；对 `scripts`/`gim`/`fonts` 三个可选节做 `setdefault`。
- `overlays_for(manifest, root, profile, switches) -> list[dict]`：按 `order` 顺序加载并过滤——`profile="test"` 的层只在剖面为 `test` 时施加；带 `switch` 字段的层默认施加，仅当调用方显式传 `{开关名: False}` 时跳过。
- `collect_ids(text) -> set[int]`：正则 `(?<![A-Za-z0-9_])(?:vms|msg)\((\d+),` 扫 `vms(N,`/`msg(N,` 调用，负向前瞻挡住 `xmsg(`/`debagMsg(` 一类的误命中。
- `check_ids(manifest, root, ledger_ids) -> None`：读 `vms_ids.toml` 的 `[[ranges]]`，做四道检查——owner 声明区段两两不交；owner 整段区间不与保留集（账本 id ∪ `CARD_MSG_RESERVED=range(18001,18196)`）相交；`manifest["scripts"]` 中 `profile=="release"`（缺省即 release）的脚本，其文本内每个字面 id 必须落在其 owner 声明区段内、不与账本冲突、且在本次调用范围内全局唯一（`seen` 字典）。

## 测试与结果

追加的 12 个测试覆盖：manifest 全节读取、未知顶层键报错、叠加层缺 `why`/`profile` 非法报错、`order` 与磁盘文件不一致报错、`overlays_for` 按 profile 与 switch 过滤、`collect_ids` 的正例与反例（普通局部变量赋值、`xmsg(` 前缀干扰不应误命中）、`check_ids` 对「与账本冲突」「超出声明区段」「owner 区段重叠」三种失败路径的断言。

全部使用 `_mk_layers(tmp_path, ...)` 夹具在 `tmp_path` 下现造 `layers/` 骨架，**没有创建真实的** `layers/manifest.toml` / `layers/vms_ids.toml`（按裁决，这两个文件归 Task 4）。

## TDD Evidence

**RED**

命令：
```
uv run pytest tests/test_layers.py -q -k "manifest or overlay or ids or switch or order"
```

输出（节选）：
```
==================================== ERRORS ====================================
____________________ ERROR collecting tests/test_layers.py _____________________
ImportError while importing test module '/Users/fotile96/Zndnovel/tests/test_layers.py'.
Traceback:
tests/test_layers.py:107: in <module>
    from tools.layers import (REPO, check_ids, collect_ids, load_manifest, load_overlay,
E   ImportError: cannot import name 'check_ids' from 'tools.layers' (/Users/fotile96/Zndnovel/tools/layers.py)
=========================== short test summary info ============================
ERROR tests/test_layers.py
1 error in 0.06s
```

为何符合预期：Step 1 只追加了测试代码，`tools/layers.py` 尚未有 Step 3 的实现，故导入即失败——测试根本无法收集，这是「假测试」的强证据（还没写实现就先看到红）。

一处与 brief 文字不完全一致但无实质影响：brief 的「Expected」写的是 `ImportError: cannot import name 'load_manifest'`，实际抛出的是 `'check_ids'`——因为 `from tools.layers import (REPO, check_ids, collect_ids, load_manifest, load_overlay, overlays_for)` 是按元组顺序逐名解析，`REPO` 已存在（Task 1 遗留），下一个 `check_ids` 才是真正缺失的第一个名字，Python 在此处即报错，不会继续检查后面的 `load_manifest`。同一条 import 语句、同一个根因（Step 3 尚未实现），只是报出的具体名字不同，不影响红态成立。

**GREEN**

命令：
```
uv run pytest tests/test_layers.py -q
```

输出：
```
............................                                             [100%]
28 passed in 0.21s
```

`-v` 复核 28 个测试名全部 PASSED，无 warning。另跑了一次不在 brief 要求内的全仓库回归：`uv run pytest -q -m "not emu"` → `1703 passed, 3 skipped, 6 deselected in 300.38s`，确认未影响仓库其余测试。

## Files changed

- `tools/layers.py`：追加 155 行（`load_overlay`/`load_manifest`/`overlays_for`/`collect_ids`/`check_ids`/`_check_ids_of`/`_ranges_of`/`_read_toml` 等，含 `LAYERS`/`PROFILES`/`CARD_MSG_RESERVED`/`_MANIFEST_KEYS`/`_OVERLAY_KEYS` 常量）。
- `tests/test_layers.py`：追加 148 行、12 个新测试 + `MINIMAL_MANIFEST`/`ALPHA_OVERLAY`/`_mk_layers` 夹具。
- 未创建 `layers/manifest.toml`、`layers/vms_ids.toml`（按裁决明确排除，归 Task 4）。
- 逐字节比对追加内容与 brief 给出的两段代码块（`diff` 结果 `IDENTICAL`），确认零转录漂移。

Commit: `e75590f` "feat: 清单与 id 登记的加载与校验"（brief 给定文案逐字，含 `Co-Authored-By` 行）。只 `git add` 了这两个文件；仓库里另外 5 个此前已存在的未暂存改动（`.claude/settings.json`、`data/api_ledger.jsonl`、`data/event_op_text.jsonl`、`pilot/read-edits/opus.draft.jsonl`、`tools/bake_event_op.py`，会话开始时的 git status 快照已显示为 modified）未触碰、未纳入本次提交。

## 自评（Self-review）

逐项核对了 brief 列出的 5 个公开接口，签名与文档字符串均逐字落地。四道 `check_ids` 检查路径分别用给定测试验证：

1. **超出声明区段**：`test_check_ids_rejects_id_outside_declared_range` 断言 `_check_ids_of` 里 `if not any(i in r for r in ranges)` 分支。
2. **与账本冲突**：`test_check_ids_rejects_collision_with_ledger` 触发的实际是 `check_ids` 主循环里 `hit = sorted(set(r) & (ledger_ids | set(CARD_MSG_RESERVED)))` 这一关（owner 整段区间与账本相交），先于逐脚本扫描就已经报错——这条路径覆盖了「id 冲突」的语义,但顺带说明 `_check_ids_of` 内 `if i in ledger_ids: raise ...` 那一行在当前调用顺序下是防御性的死代码（owner 整段已在此之前被挡下，不可能有单个 id 漏网到这一步）。不算错误，只是冗余；brief 给的是"完整实现"，未改动。
3. **owner 区段两两不交**：`test_check_ids_rejects_overlapping_owner_ranges` 直接命中 `check_ids` 里的嵌套 pairwise 比较。
4. **release 层间全局唯一**：给定测试集没有专门用例，但代码路径是真实的——`seen` 字典跨 `manifest["scripts"]` 的多次 `_check_ids_of` 调用累积；由于 owner 区段已保证两两不交、且每个 id 必须先落在自己 owner 的声明区段内，两个**不同**owner 用同一个数字 id 在结构上不可能发生（会先被「超出声明区段」拦下）。`seen` 实际防的是同一个 owner 被 `manifest["scripts"]` 重复登记（同一文件出现两次 spec）这类配置错误——是有效的兜底，不是摆设。

未添加 brief 未要求的任何函数/参数/测试（YAGNI）；未重排、未删改已有 16 个测试；中文注释/文档字符串逐字保留；两段追加内容与 brief 原文做过 `diff` 逐字节核对，确认 `IDENTICAL`。

## Concerns

一处仅供记录、未在本任务内处理的观察（不影响本任务任何测试或已知调用点，故未改代码，留给评审判断是否需要立案）：

`check_ids` 的 docstring 与 spec §6.3 都称"test 层免于与保留集比对（探针沿用 9000 段）……但 test 层之间必须不交且各自声明区段"，暗示 test-profile 的 owner 会在 `vms_ids.toml` 里登记区段、且这类区段应该被排除在"与保留集相交"检查之外。但读了给定实现后发现：`vms_ids.toml` 的 `[[ranges]]` 条目本身**不带 profile 字段**（`_ranges_of`/`check_ids` 主循环都只读 `owner`/`vms`/`card_msg`），第一段循环（owner 两两不交 + 与保留集相交）对 `owned` 里的**每一个**owner 一视同仁，没有任何 profile 分支——也就是说，如果真的有 test 探针把区段登记进 `vms_ids.toml`（哪怕用 9000 段），这段区间大概率会落进账本 1..17220 的稠密区（账本 16749/17220 已用），会被当场判"撞上保留 id"拒绝，与文档承诺的"免于比对"相反。

我通读了整份 10 任务计划文档（`docs/superpowers/plans/2026-09-02-disc-layers-pipeline.md`），确认全篇只有一次真实的 `vms_ids.toml` 写入（Task 4 Step 3，唯一 owner 是 `scripts/snr_finale.lua`，release 剖面），从未有 test-profile owner 真正登记过区段——这条"豁免"分支在当前 10 个任务的实际用法里从未被触发,是休眠状态,不是已验证生效的行为。因为：(a) 给定的 12 个测试都不覆盖这个场景；(b) 全篇计划里每处调用 `check_ids` 都是同样的三参数签名，没有额外传入 profile 信息；(c) 修它需要发明一个 spec example 里没出现过的 schema 字段（如给 `[[ranges]]` 加 `profile` 键），这超出了"逐字实现 brief"的授权范围——所以我没有动这段代码，只在此报告备案。如果未来任务真要给探针层登记 9000 段 id，这里会是第一个要回头补的地方。

---

## Fix round 1（task review：2 处 Important）

### Finding 1 — test 层豁免名不副实，按裁决实现

`tools/layers.py` 的 `check_ids`/`_check_ids_of` 改动：

1. `vms_ids.toml` 的 `[[ranges]]` 条目现读可选 `profile`（`entry.get("profile", "release")`）；
   `owned` 从 `dict[str, list[range]]` 改为 `dict[str, tuple[str, list[range]]]`（owner → (profile, ranges)）。
2. owner 两两不交检查对**全部** owner 无条件执行（不看 profile）；只有紧随其后的「与保留集
   （账本 ∪ 卡消息 18001..18195）相交」检查在 `profile == "test"` 时 `continue` 跳过。
3. `manifest["scripts"]` 循环不再按 `spec.get("profile") != "release"` 整体跳过——现在**每个**
   脚本都会被 `_check_ids_of` 扫描（区段内检查 + 判重都跑），只是"是否与账本比对"这一件事
   改由 `_check_ids_of` 内部按 owner 在 vms_ids.toml 里登记的 profile 判断
   （`if profile != "test" and i in ledger_ids: raise ...`）。
4. docstring 改写为准确描述：豁免只免保留集比对一项，两两不交与全局唯一两道对 test 层同样生效。

### Finding 2 — 二道防线保留 + 补注释 + 补测试

按裁决**未删除**`_check_ids_of` 里"撞账本"与"seen 判重"两处检查，只在各自位置加了注释，
说明它们是二道防线、通常由哪道更早的检查先行拦截、以及各自防的到底是什么场景（seen 真正防
的是"同一个 owner 被 `manifest["scripts"]` 重复登记"，不是"跨 owner 撞号"——后者已被区段
两两不交挡住）。

### 新增 4 个测试

- `test_check_ids_test_profile_range_exempt_from_ledger`：test 层区段（9000 段）与账本相交，
  `check_ids` 正常返回（不报错）。
- `test_check_ids_release_profile_range_not_exempt_from_ledger`：同一区段改 release，照常因
  撞账本被拒——对照组，证明豁免确实是 profile 驱动而非区段本身特殊。
- `test_check_ids_test_profile_owners_still_mutually_exclusive`：两个 test 层区段互相重叠，
  照常因「重叠」被拒——证明豁免不等于整层放行。
- `test_check_ids_rejects_same_owner_listed_twice_in_scripts`：同一 owner 的 spec 在
  `manifest["scripts"]` 里出现两次（同文件两条 spec），触发 `seen` 判重——这是 Finding 2
  要求补的、`seen` 字典真正能命中的场景。

### 测试与结果

**RED（验证新测试确实在测行为，不是空转）**

临时把 `tools/layers.py` 换回 fix 前的版本（`git show e75590f:tools/layers.py`），跑：

```
uv run pytest tests/test_layers.py -q -k "test_profile or same_owner_listed_twice" -v
```

结果：`1 failed, 2 passed, 29 deselected`——失败的是 `test_check_ids_test_profile_range_exempt_from_ledger`，
报错 `tools.layers.OverlayError: probe 声明的区段撞上保留 id [9010]（账本 1..17220 与卡消息
18001..18195 已占）`，即 Finding 1(a) 描述的那个 bug 本身。另外两个（`test_profile_owners_still
_mutually_exclusive`、`rejects_same_owner_listed_twice_in_scripts`）在旧代码下也通过——这是预期的，
不是漏网：前者测的两两不交检查在旧代码里本来就没有 profile 分支（一直对全部 owner 生效，
Finding 1(b) 的问题出在别处：脚本循环整体跳过 test 脚本，不是这条检查本身），后者是 Finding 2
的测试，Finding 2 的裁决本来就是「不改行为，只补注释与测试」，两个 spec 都写的 `profile="release"`，
新旧代码在这条路径上行为完全一致。真正需要行为改变、也真正验证了改变的，只有第一个。

之后原样复原 fix 后的 `tools/layers.py`（对比 `diff` 确认逐字节还原），重跑：

```
uv run pytest tests/test_layers.py -q
```
```
................................                                         [100%]
32 passed in 0.03s
```

**全量回归**

```
uv run pytest -q -m "not emu"
```
```
1707 passed, 3 skipped, 6 deselected in 298.44s (0:04:58)
```
（较 fix 前的 1703 恰好 +4，与新增测试数一致，无回归。）

### 可达性问题的回答

coordinator 问：Finding 1 的修复之后，`_check_ids_of` 里 `if profile != "test" and i in ledger_ids`
这一行，对"声明区段本身干净、但用了区段外的 id"这种 release 脚本，是否变得真正可达？

**结论：不可达，仍是纯防御性代码，Finding 1 的修复没有改变这一点。** 论证：

- 若某个 id 在其 owner 声明区段**之外**，`_check_ids_of` 会在更早的
  `if not any(i in r for r in ranges): raise ...` 处直接中断，根本走不到 ledger 判断那一行——
  区段外的 id 不可能触发这一行,不管是修复前还是修复后。
- 若某个 id 在其 owner 声明区段**之内**：`check_ids` 主循环对**每一个** profile != "test" 的
  owner，会在进入脚本扫描循环之前，把该 owner **整段**区间与 `ledger_ids | CARD_MSG_RESERVED`
  做交集检查（`hit = sorted(set(r) & (...))`），一旦非空立即 `raise`，且这个 `raise` 会中断
  整个 `check_ids` 调用——**脚本循环（进而 `_check_ids_of`）根本不会被执行到**。也就是说，
  只要代码执行流程能够走到 `_check_ids_of`，就已经隐含了"每一个 release owner 的整段区间
  都已验证与保留集无交集"这个前提——那么该区间内的任何单个 id 自然也不可能是账本 id。
  这条推理链在 Finding 1 修复前后完全一致，因为修复只是新增了"对 profile=="test" 的 owner
  跳过这一步"的分支，没有改变 release owner 那一分支本身的逻辑或顺序。
- 修复给这行代码新增的**唯一**行为变化是显式加了 `profile != "test"` 前置条件——这不是让它
  "变得可达"，而是明确地让它对 test owner **不可达**（即便 test owner 的整段区间本来就没有
  被上面的保留集检查验证过，这里也主动放弃比对，而不是"侥幸"没撞上）。

  一句话：release 分支——修复前后同样不可达（结构性保证，非巧合）；test 分支——修复后由
  `profile != "test"` 主动短路，不是"可达但没测到"，是设计上就不该比对。

## 自评（第二轮）

- 逐条核对了裁决给的 4 步（读 profile、两两不交对全体生效、保留集比对按 profile 跳过、
  脚本循环不再整体跳过）与 Finding 2 的 2 步（保留检查+注释、补 seen 的针对性测试），
  均已落地，未增删裁决之外的行为。
- import 清理按裁决执行：删 `tomllib`/`Path`/`REPO`（确认全文件搜索无其他引用），
  两条 `from tools.layers import (...)` 合并回文件顶部一条，未触碰其它内容。
- 新旧行为对比用了真实的"改回旧代码跑一遍"而不是纯人工推理，尤其是可达性问题——这类
  "结构上是否可达"的判断容易凭直觉出错，跑了实测（RED under old code）而不是只在报告里
  写论证。
- 未发现新的遗留问题；`manifest["scripts"]` 的 `profile` 字段在别处（`build_final_sources`，
  Task 4/8 领地）仍有独立用途，与本次改动的 `check_ids` 内部逻辑互不干扰，已用
  `grep` 核实该字段的另一处消费点不受影响。

## Concerns（更新）

无新增。原报告里记录的"未来若真有 test 探针层需要登记 9000 段"的观察，本轮已经是被要求
实现的那件事本身，不再是悬而未决的观察。

---

## Fix round 2（re-review：1 处 Important + 1 处 optional）

### Important — 二道防线注释自相矛盾

`_check_ids_of` 里撞账本检查的注释，test 分支原文说"是真会命中的分支，不是防御性
代码"，但它标注的行是 `if profile != "test" and i in ledger_ids:`——`profile ==
"test"` 时 `profile != "test"` 为 False，Python 短路，`i in ledger_ids` 根本不会
被求值，`raise` 永远不会因 test 层触发。这一点上一轮报告本身的可达性论证已经说对了
（"test 分支——修复后由 `profile != "test"` 主动短路……是设计上就不该比对"），只是
代码里的注释没跟着改，停留在写 guard 之前的旧说法上。

**改法**：release 半句原样保留（准确：owner 整段已在上面比对过一次，这里是二道
防线）；test 半句改写为说明 `profile != "test"` 这个前置条件本身的作用——它不是
可以删掉的冗余判断，删掉它 test 层刚被豁免放行的区段会在这里逐 id 重新比对一遍，
等于把 range 级豁免撤销。这是"这行代码故意做到不可达"，不是"忘了改的死代码"。

顺带核对了另一处二道防线注释（`seen` 判重那处）：`owner 区段两两不交对全部 profile
都生效` 这一句依据的不变量（pairwise 检查在 `if profile == "test": continue` 之前，
对所有 owner 无条件执行）没有变化，`seen` 只在"同一 owner 被 manifest["scripts"]
重复登记"时可达的结论也没有变化——复核后确认**未漂移**，未改动。

### Optional — vms_ids.toml 的 `[[ranges]]` 补 profile 合法性校验

此前 `profile = entry.get("profile", "release")` 对任意字符串照单全收，非法值
（如笔误 "tset"）会被当成"非 test"走 release 语义，不会被静默豁免（fail-safe），
但下游报错和真实问题（profile 打错了）无关，不好定位。比照 `load_overlay` 现成的
校验与措辞加了同规格检查：

```python
profile = entry.get("profile", "release")
if profile not in PROFILES:
    raise OverlayError(f"vms_ids.toml 里 {owner} 的 profile={profile!r} 非法"
                       f"（只能 {PROFILES}）")
```

新增测试 `test_check_ids_rejects_bad_range_profile`：`profile = "staging"`、
`ledger_ids=set()`（刻意留空，排除撞账本这条路径，确保捕获的确实是 profile 校验
本身），断言报错信息含 `"staging"`。

### 测试与结果

**RED（两处改动都做了真实的"改回去再跑"验证，不是只在报告里论证）**

1. 注释改动本身不影响可执行逻辑（纯文档），无需 RED；靠上一轮报告里的可达性论证
   + 这次 re-review 的复核确认其准确性。
2. profile 校验：临时用 `sed` 删掉新增的 3 行校验代码，跑：
   ```
   uv run pytest tests/test_layers.py -q -k "bad_range_profile"
   ```
   ```
   F
   E       Failed: DID NOT RAISE SystemExit
   1 failed, 32 deselected in 0.02s
   ```
   与预期一致：`ledger_ids=set()`、区段 `[9000,9050]` 不撞卡消息保留段，若不做
   profile 校验，"staging" 会被当 release 处理但因区段本身干净而**完全放行、不报
   任何错**——这正是 optional 项想堵的"确认应该报错的地方却没报错"。之后用 `diff`
   核对逐字节还原，重跑确认恢复。

**GREEN**

```
uv run pytest tests/test_layers.py -q
```
```
.................................                                        [100%]
33 passed in 0.02s
```

**全量回归**（本轮改了行为，非纯注释，按要求跑了一次全量）

```
uv run pytest -q -m "not emu"
```
```
1708 passed, 3 skipped, 6 deselected in 296.81s (0:04:56)
```
（较上一轮 1707 恰好 +1，与新增的 1 个测试一致，无回归。）

### 自评（第三轮）

- 重新通读了 `seen` 判重那处注释依赖的不变量链条，确认 pairwise 不交检查确实排在
  `if profile == "test": continue` 之前、对全部 owner 无条件执行，`seen` 的"仅同一
  owner 重复登记时可达"结论仍然成立，如实汇报"未漂移"而不是不查就假定没问题。
- profile 校验的错误信息措辞直接照抄 `load_overlay` 那句的结构（`{标识} 的
  profile={值!r} 非法（只能 {PROFILES}）`），只把 `path.name` 换成 `vms_ids.toml
  里 {owner}`，没有另造一套新话术。
- 没有借这次改动顺手碰其他代码——`check_ids`/`_check_ids_of` 之外的函数、
  `manifest["scripts"]` 那半句注释、`overlays_for` 等均未触碰。
- commit 只 `git add` 了 `tools/layers.py`、`tests/test_layers.py` 这两个文件，
  仓库里另外 5 个此前已存在的未暂存改动依旧原样未动。
