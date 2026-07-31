# Hotfix C 报告：unit 发卡口径统一到 emit_unit + timeline 全局 id 去重 + check_timeline 口径对齐

## 实现内容

### C1 — `Expander.emit_unit`：对「实际取到 id 的全部函数」生效 scene_meta 发卡

抽出共用方法 `_matched_funcs(file, funcs) -> set[str]`（原 `_ids_for` 内联的 fnmatch
匹配逻辑，原样搬出，行为不变）：

```python
def _matched_funcs(self, file, funcs):
    extra = self.unit_funcs.get(file, {})
    pats = list(funcs) + [p for p, tgt in extra.items() if tgt in funcs or tgt == "*"]
    return {fn for (f, fn) in self.by_filefunc
            if f == file and any(fnmatch.fnmatch(fn, p) for p in pats)}
```

`_ids_for` 改为基于它取 id；`emit_unit` 新增：对该 unit `_matched_funcs` 命中的
**全部**真实函数（含 unit_funcs 附挂的孤儿函数，如 `scene_s7f_dispatch_v52`）逐个
`_apply_meta`：

```python
def emit_unit(self, kind, src_file, state, title, funcs):
    matched = self._matched_funcs(src_file, funcs)
    ids = [i for i in self._ids_for(src_file, funcs) if i not in self._emitted_ids]
    self._emitted_ids.update(ids)
    self.timeline.append({...})
    for fn in matched:
        self._apply_meta(fn)
```

**删掉了 Hotfix B 留下的两处特例**（均已被 emit_unit 内的统一循环覆盖）：
1. `story()` 里 emit 之后的 `for f in funcs: self._apply_meta(f)`（对 nominal
   funcs 逐个发卡，遗漏 unit_funcs 附挂函数）；
2. `fragment_sweep()` 里 fscene emit 之后的 `for fn in fs: self._apply_meta(fn)`
   （Hotfix B 加的，同样只覆盖了 `fs` 里的名义函数，且现在这段计算方式与
   `emit_unit` 内部重复）。

`fragment_sweep()` 里「crd 自身发卡」`self.held.update(crd.get("gets", []))`
**原样保留**——它读的是 `crds[cid]["gets"]`，不是 `scene_meta`，emit_unit 覆盖不到。

真实数据验证：`scene_s7f_dispatch_v52` 是 `snr_s7_10_f` 里的带参 dispatcher 调用
（`scene_s7f_dispatch_v52("その『お話』の題名は――", 104, v1, 10)`），`PLAY_RE`/
`SUBCALL_RE` 都抓不到，全库任何状态的 `seq` 都不直接提它，只在
`config/unit_funcs.yaml` 里附挂到 `s7f-50`；其 `scene_meta.gets = [141, 111, 112,
113]`。改前 `dag.json`/`ledger.jsonl` 现算核实：该函数有 5 条 narrative ledger
行、`found nominally in states: []`（`grep` 全部 states 的 play/subcall 得空集）。

### C2 — `Expander.emit_unit`：全局 id 去重

`__init__` 新增 `self._emitted_ids = set()`；`emit_unit` 写入 timeline 前把已出现
过的 id 滤掉、再登记剩下的（见上面代码块）。unit 本身照常 emit（即便 ids 被滤
空）——不影响 `state`/`title`/`unit_kind`。

真实数据验证：`snr_s4_10_s` 里 `s4s_210_sel`/`s4s_450_sel` 共用
`scene_s4s_dispatch_v14..v27`，`s4s_300`/`s4s_310` 双方 play
`scene_s4s_dispatch_v34`（改前 `check_timeline` 报「重复 id: [628, 629, 630,
13702, ...]…共92」，改后清零，见下方验收输出）。

### C3 — `check_timeline._grant`：held 推导改为「从 timeline 自身可导出」的四路并集

`_grant` 新增形参 `id_func`（id→func 反查表，`check()` 里从 `ledger_rows` 建一次，
与既有的 `file_funcs` 并列）。四路取并集：

```python
def _grant(held, unit, dag, scene2card, file_funcs, id_func):
    kind = unit.get("unit_kind")
    state = unit.get("state")
    for i in unit.get("ids", []):                       # 1. 由 ids 反查
        fn = id_func.get(i)
        if fn:
            held.update(dag["scene_meta"].get(fn, {}).get("gets", []))
    if kind == "scene":                                  # 2. scene unit
        for ev in dag["states"].get(state or "", {}).get("seq", []):
            if "play" in ev:
                held.update(dag["scene_meta"].get(ev["play"], {}).get("gets", []))
            elif "subcall" in ev:
                held.update(dag["scene_meta"].get(ev["subcall"], {}).get("gets", []))
    elif kind == "card":                                  # 3. card unit
        cid = scene2card.get(state)
        held.add(cid)
        held.update(dag["crds"].get(str(cid), {}).get("gets", []))
    elif kind in ("fscene", "script"):                    # 4. fscene / script unit
        for fn in file_funcs.get(unit.get("src"), ()):
            held.update(dag["scene_meta"].get(fn, {}).get("gets", []))
```

与 Hotfix B 版本的差异：新增路径 1（ids 反查，覆盖 unit_funcs 附挂函数，check()
拿不到 unit_funcs 本身，只能靠这条路自动兜底）；路径 4 的判定条件从
`kind == "fscene"` 扩为 `kind in ("fscene", "script")`（brief 明确把这两种并列为
第 4 路：两者语义相同，都是「该文件被整体经历」）。路径 2/3 与 Hotfix B 一致，
未改动。

`check()` 里新增：

```python
id_func = {r["id"]: r["func"] for r in ledger_rows}
```

B 段（`for pos, u in enumerate(timeline)` 顺序累积）与 C 段（对 `timeline[:pos]`
重扫）两处调用点都改传 `id_func`，继续共用同一个 `_grant` 实现（Hotfix B 已抽好
的共用辅助，未拆分、未复制）。

`check()` 的对外签名 `check(timeline, ledger_rows, dag, scene2card, gates)`、四个
中文错误关键词（重复/缺失/门控/req）、A 段覆盖断言均未改动（已 grep 核对，见
「自评审」小节）。

真实数据验证：改前 `check_timeline` 报「门控: s8s_10 出现前缺卡 [141]」/
「门控: e1s_10 出现前缺卡 [142]」/「门控: e2s_10 出现前缺卡 [143]」，改后清零
（141 来自 C1 修复的 `scene_s7f_dispatch_v52`，142/143 是其下游链条：crd_94 需
141 → run `snr_s8_10_f` 发 142 → e1s_10 门控 142；crd_94 同时是 e2 链的上游，
143 同理打通）。

## TDD 证据

三条新判别性测试均按「先写测试确认 GREEN（生产代码已落地）→ 临时注释掉对应
产码行确认 RED → 恢复产码行再确认 GREEN」的顺序做的（生产代码三处改动是作为
一个整体先落地的，判别性验证通过「临时精确注释单一产码行」补齐，等价于
先红后绿；每次注释/恢复后都立刻用 `git diff`/`grep TEMP-RED` 核对已还原干净）。

### 测试 1 — unit_funcs 附挂函数的 scene_meta.gets 在 emit_unit 内生效（`tests/test_gen_timeline.py`）

`test_emit_unit_applies_scene_meta_gets_for_unit_funcs_attached_orphan`：复现
`scene_s7f_dispatch_v52` 的最小场景——状态 `d_10` 只 play `scene_d_10`（无
gets），孤儿函数 `scene_d_dispatch_v9` 不出现在 `d_10` 的 `seq` 里、只能靠
`unit_funcs={"snr_d_10_s": {"scene_d_dispatch_v9": "scene_d_10"}}` 附挂，其
`scene_meta.gets=[141]`。

GREEN（产码已落地，先确认测试本身可通过）：
```
$ uv run pytest -q tests/test_gen_timeline.py -k test_emit_unit_applies_scene_meta_gets_for_unit_funcs_attached_orphan -v
tests/test_gen_timeline.py::test_emit_unit_applies_scene_meta_gets_for_unit_funcs_attached_orphan PASSED
1 passed, 17 deselected in 0.05s
```

RED（临时把 `emit_unit` 里 `for fn in matched: self._apply_meta(fn)` 两行注释掉）：
```
$ uv run pytest -q tests/test_gen_timeline.py -k test_emit_unit_applies_scene_meta_gets_for_unit_funcs_attached_orphan -v
FAILED tests/test_gen_timeline.py::test_emit_unit_applies_scene_meta_gets_for_unit_funcs_attached_orphan
    assert unit["ids"] == [500, 501]   # 孤儿函数的 id 本就该在（_ids_for 既有行为）
>   assert 141 in ex.held              # Hotfix C1 要补的发卡缺口
E   assert 141 in set()
E    +  where set() = <tools.gen_timeline.Expander object at ...>.held
1 failed, 17 deselected in 0.04s
```
（`unit["ids"] == [500, 501]` 这一行仍然通过——证明 ids 侧本来就是对的，红的
精确落在发卡侧，测试判别性落在 C1 要修的那一点上，不是泛泛地测别的东西）。

恢复产码行后重跑，回到上面的 GREEN 输出；`grep TEMP-RED tools/gen_timeline.py`
确认无残留。

### 测试 2 — 两个状态共用同一函数时 ids 全局去重（`tests/test_gen_timeline.py`）

`test_emit_unit_dedups_ids_globally_across_units_sharing_a_func`：复现
`s4s_210_sel`/`s4s_450_sel` 共用 dispatch 函数的最小场景——`e_10`/`e_20` 都
`subcall scene_e_shared`。

GREEN：
```
$ uv run pytest -q tests/test_gen_timeline.py -k test_emit_unit_dedups_ids_globally_across_units_sharing_a_func -v
tests/test_gen_timeline.py::test_emit_unit_dedups_ids_globally_across_units_sharing_a_func PASSED
1 passed, 17 deselected in 0.03s
```

RED（临时把 `emit_unit` 的去重逻辑改回 `ids = self._ids_for(src_file, funcs)`，
不再过滤/登记 `_emitted_ids`）：
```
$ uv run pytest -q tests/test_gen_timeline.py -k test_emit_unit_dedups_ids_globally_across_units_sharing_a_func -v
FAILED tests/test_gen_timeline.py::test_emit_unit_dedups_ids_globally_across_units_sharing_a_func
    assert units[0]["ids"] == [600, 601]          # 第一个 unit 拿到共享函数的全部 ids
>   assert units[1]["ids"] == [602]               # 第二个 unit 里共享的 601 被滤空
E   assert [601, 602] == [602]
E     At index 0 diff: 601 != 602
E     Left contains one more item: 602
1 failed, 17 deselected in 0.04s
```
（第二个 unit 的 ids 变成 `[601, 602]`，601 被两个 unit 各拿一次——正是 C2 要
消灭的重复，判别性精确。）

恢复产码行后重跑，回到上面的 GREEN 输出；`grep TEMP-RED tools/gen_timeline.py`
确认无残留。

### 测试 3 — check() 认可「卡 X 的 req 由 unit_funcs 附挂函数发卡满足」（`tests/test_check_timeline.py`）

`test_check_accepts_req_satisfied_by_unit_funcs_attached_orphan_via_id_lookup`：
手写 timeline（不经 Expander）——`w_10` 的 `unit["ids"]=[700, 701]`，701 属于
`scene_w_dispatch_v9`（不在 `dag["states"]["w_10"]["seq"]` 里，模拟 unit_funcs
附挂后的真实产物），其 `scene_meta.gets=[141]`；卡 80 的 `req=[141]`。

GREEN：
```
$ uv run pytest -q tests/test_check_timeline.py -k test_check_accepts_req_satisfied_by_unit_funcs_attached_orphan_via_id_lookup -v
tests/test_check_timeline.py::test_check_accepts_req_satisfied_by_unit_funcs_attached_orphan_via_id_lookup PASSED
1 passed, 5 deselected in 0.02s
```

RED（临时把 `_grant` 里「由 ids 反查」的 4 行注释掉，只留 scene/card/fscene 三个
分支）：
```
$ uv run pytest -q tests/test_check_timeline.py -k test_check_accepts_req_satisfied_by_unit_funcs_attached_orphan_via_id_lookup -v
FAILED tests/test_check_timeline.py::test_check_accepts_req_satisfied_by_unit_funcs_attached_orphan_via_id_lookup
>   assert errs == []
E   AssertionError: assert ['card unit w_20: req [141] 未满足（held 缺 [141]）'] == []
E     Left contains one more item: 'card unit w_20: req [141] 未满足（held 缺 [141]）'
1 failed, 5 deselected in 0.03s
```
（item2 扫 `w_10` 的 `seq` 只看到 `scene_w_10`（gets=[]），看不到
`scene_w_dispatch_v9`，held 缺 141——证明「由 ids 反查」这一路是唯一能满足此
req 的路径，判别性精确锚定 C3 第 1 路。）

恢复产码行后重跑，回到上面的 GREEN 输出；`grep TEMP-RED tools/check_timeline.py`
确认无残留。

### 测试 4 — 回归：Hotfix B 补的 4 条用例保持绿

未修改这 4 条测试的任何断言（`git diff tests/test_build_dag.py` 为空；
`test_gen_timeline.py`/`test_check_timeline.py` 里这 4 条对应的用例原文未动）：

```
$ uv run pytest -q \
  "tests/test_build_dag.py::test_parse_crds_captures_literal_gets_but_not_self_grant_variable" \
  "tests/test_gen_timeline.py::test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep" \
  "tests/test_gen_timeline.py::test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets" \
  "tests/test_check_timeline.py::test_check_accepts_req_satisfied_by_crd_and_fscene_and_subcall_grants" \
  -v
tests/test_build_dag.py .                                                [ 25%]
tests/test_gen_timeline.py ..                                            [ 75%]
tests/test_check_timeline.py .                                           [100%]
4 passed in 0.03s
```

**唯一需要调整的既有断言**（不属于 Hotfix B 的 4 条，是 Task 3/5 阶段的
`test_run_plan_dispatches_all_move_kinds_in_order`，在 `test_gen_timeline.py`）：
该测试串联 `story→fragment_sweep→pool→script→replay` 五种移动，其中
`fragment_sweep()` 对 crd 11 emit 的 card 单元与随后 `script("snr_crd_11")` emit
的 script 单元命中同一个 `(snr_crd_11, card_11_main)`、原断言两处都是 `ids=[51]`
——这正是 C2 要消灭的「同一条 vms 被两个 unit 各 emit 一次」的真实例子。改后
`script` 单元的 `ids` 变成 `[]`（51 已被前面的 card 单元领走），`unit_kind`/
`state`/`title` 不变。这是 C2 生效后的**必然**结果，不是放松断言——改动前该测试
在只加测试、未加 C2 产码时会失败（见下），加了注释说明原因：

```
$ uv run pytest -q tests/test_gen_timeline.py -k test_run_plan_dispatches_all_move_kinds_in_order -v
# （C2 产码落地前，断言仍是旧的 [51]）
FAILED ... At index 7 diff: ('unit', 'script', None, []) != ('unit', 'script', None, [51])
# 改断言为 [] 后：
tests/test_gen_timeline.py::test_run_plan_dispatches_all_move_kinds_in_order PASSED
```

## 验收命令输出

```
$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693

$ uv run python tools/check_timeline.py
OK
$ echo $?
0
```

与 brief 预告的目标数字完全一致（`unit=457 marker=76 covered_ids=16693`，
`check_timeline` OK/退出码 0）。额外核实 `covered_ids=16693` 恰好等于全部
narrative 行数：
```
$ uv run python3 -c "
import json
ledger = [json.loads(l) for l in open('data/ledger.jsonl', encoding='utf-8') if l.strip()]
print(len([r for r in ledger if r['kind']=='narrative']))
"
16693
```

改动前基线（记录对比）：
```
$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=450 marker=76 covered_ids=15533
$ uv run python tools/check_timeline.py
重复 id: [628, 629, 630, 13702, ...]…共92
缺失 narrative id: [635, 636, 966, 967, ...]…共1160
门控: s8s_10 出现前缺卡 [141]
门控: e1s_10 出现前缺卡 [142]
门控: e2s_10 出现前缺卡 [143]
```

## 双跑确定性验证

`data/timeline.jsonl`/`data/scene2card.json` 未入库（按 brief 要求不 `git add`），
用 sha256 前后比对两次独立运行：

```
$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
$ sha256sum data/timeline.jsonl data/scene2card.json
3e079359f06784d0e9e772ad9a11c3fe27b6193899c2bac2ddf38100622e2c65  data/timeline.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json

$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
$ sha256sum data/timeline.jsonl data/scene2card.json
3e079359f06784d0e9e772ad9a11c3fe27b6193899c2bac2ddf38100622e2c65  data/timeline.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json
```
两次运行字节完全一致。`git status --short data/timeline.jsonl data/scene2card.json`
全程只显示 `??`（未跟踪），未被本次任何 commit 收入。

## 全套测试结果

改动前基线：
```
$ uv run pytest -q
..................................................................       [100%]
66 passed in 2.05s
```

改动 + 新测试落地后：
```
$ uv run pytest -q
.....................................................................    [100%]
69 passed in 2.04s
```
净增 3（测试 1/2/3），Hotfix B 的 4 条与其余全部既有用例保持绿（含唯一按 C2
行为必然调整的那条断言），无回归、无 skip。

用 `-rw` 复核默认设置下无告警：
```
$ uv run pytest -q -rw
.....................................................................    [100%]
69 passed in 2.04s
```
（未打印任何 warnings 小结行。）

**探索性记录（非本次任务范围）**：另外用 `-W error` 跑过一次全套，发现
`tests/test_build_dag.py::test_real_data_all_choices_valid` 与
`::test_real_data_s2s_190_sel_targets` 在该非常规严格模式下失败——原因是这两条
既有测试用 `json.load(open("data/dag.json", ...))` 未走 `with`/未显式 `close()`，
垃圾回收时触发 `PytestUnraisableExceptionWarning`。已用 `git stash` 核实：这在
**改动前的 HEAD（3c7c609）上同样复现**，与本次三条改动无关，且不在验收命令
（`uv run pytest -q`，不带 `-W error`）覆盖范围内，未做任何改动（`test_build_dag.py`
不在本次允许触碰的 4 个文件之列）。

## 自评审

**完整性**：C1/C2/C3 三条均已落地；Hotfix B 遗留的两处特例（`story()` 的
`_apply_meta` 循环、`fragment_sweep()` 给 fscene 加的 `_apply_meta` 循环）均已
删除（`grep _apply_meta tools/gen_timeline.py` 确认全文件只剩定义处与
`emit_unit` 内的唯一调用点）；`fragment_sweep()` 里 crd 自身发卡那行原样保留。
三条新测试均做过「临时注释产码行 → 变红 → 恢复 → 变绿」的判别性验证，且红
的位置精确锚定各自要测的那一行/那一段（测试 1 甚至额外断言了 ids 侧不受
影响，确保红只落在发卡侧而不是笼统地哪里错了）。

**质量**：`_matched_funcs` 命名直接对应 brief 建议，docstring 说明了它是
`_ids_for`/`emit_unit` 的共用口径来源；`_grant` 的 docstring 按四路编号重写，
与 brief 原文顺序一致，便于日后对照。`emit_unit` 内部 `_matched_funcs` 被调用
两次（一次直接用于发卡循环，一次经由 `_ids_for` 用于收 id）——两次都是纯读
操作（遍历 `by_filefunc.items()`，量级为函数对，本仓库规模下开销可忽略），
换取的是 `_ids_for` 继续作为独立、可单测的方法存在，符合 brief「`_ids_for` 与
`emit_unit` 共用」的字面要求；未做进一步的性能取舍，因为真实全量跑（226 条
route_plan、16749+ 条 narrative 行）落地耗时仍在亚秒级（见验收输出）。

**纪律**：`config/route_plan.yaml`、`config/unit_funcs.yaml`、`config/gates.yaml`
全程未写入（`git diff --stat config/` 空输出）；`data/timeline.jsonl`、
`data/scene2card.json` 全程未 `git add`（保持 `??` 未跟踪状态）；`check()` 对外
签名与四个中文错误关键词（重复/缺失/门控/req）均未改动（已 grep 核对）；未
顺手重构任务外的代码（`test_build_dag.py`、`build_dag.py`、`pipelib.py` 等均
未触碰，`-W error` 探索发现的既有问题原样记录、未修）。`.superpowers/sdd/
2026-07-30-p1b-linearize-context/progress.md` 在本次工作开始前已有主会话的
未提交修改（`git diff` 可见），本次提交未包含它（brief「只提交产码与测试」，
未把它算进"产码"或"测试"）。

**测试**：4 条判别性要求（含回归）均满足；三条新测试都测真实行为（发卡结果、
ids 内容、unit 结构），不是空测；全套 `uv run pytest -q` 输出干净，无 warning、
无 skip。

## 遗留顾虑

1. **`_matched_funcs` 在 `emit_unit` 内被调用两次**（见上文"质量"小节）：一次
   直接用于发卡循环、一次经 `_ids_for` 用于收 id。对当前数据规模（约
   16700+ narrative 行、by_filefunc 键数量为其真子集）性能影响可忽略（全量
   `gen_timeline.py` 运行仍在亚秒级），未做进一步合并优化，因为那样会让
   `_ids_for` 依赖 `emit_unit` 传入已算好的 matched 集合，破坏它作为独立
   方法的可测性/brief 要求的「共用」结构。如果后续数据规模显著增长，这里
   有一个廉价的优化空间（把 `matched` 直接传给一个内部辅助来算 ids，不必
   重新扫 `by_filefunc`）。
2. **`.superpowers/sdd/.../progress.md` 的预置改动未提交**：开工前它就已经是
   `modified` 状态（内容是主会话记录 Hotfix B 完成与"控制器实测"发现的三条
   缺口，与本次任务描述的背景一致），本次未touch、未提交，留给主会话按其
   自己的时间点处理。
3. **探索性 `-W error` 发现的既有 ResourceWarning**（`test_build_dag.py` 两条
   `test_real_data_*` 用例，未加 `with` 直接 `open()`）：已确认改动前后
   HEAD 上表现一致、与本次三条改动无关，不在验收命令覆盖范围内，未做任何
   修改；仅作记录，供后续如需要「让 `-W error` 也干净」时参考。
4. **`_grant` 路径 1（ids 反查）对 card/pool 等 unit_kind 也无条件生效**：
   已用真实数据核对 crd 函数名（`card_N_*`）与 `scene_meta` 键（`scene_*`）
   全库零重名，不存在误发卡风险；这是有意的设计（brief 原文"对每个 unit"
   即不分 kind 全量适用第 1 路），非本次引入的隐患。

---

# 评审修复：Task 5 code review Finding 1 & 2

上述 Hotfix C 提交（`f640067`/`7bd3f27`）在 Task 5 全书验收评审里被判 spec ✅ /
quality Approved、零 Critical，但有两条 Important 需要修（第三条是检查点统计表
文档问题，控制器自行处理，见 commit `a2b75c8`）。本节记录这两条的修复过程。

期间发现工作区状态已变化：`data/timeline.jsonl`/`data/scene2card.json` 已被主
会话在并发提交 `3c3d884` 里正式入库（不再是未跟踪文件），本报告自身也已被
`15b7b5e` 提交入库——以下修复按当前实际状态（这两个文件已入库、本次改动需要
把 `data/timeline.jsonl` 的下游变化一并提交）处理，与本报告前半部分写作时的
「未入库」状态不再一致，特此说明，不回改前半部分的历史记录。

## Finding 1 — `replay` marker 文案与实际讲述历史不符（Important）

### 问题

`Expander.replay` 无条件发「【讲述指针回溯至 X，本次选 N】」+「重讲：上一轮在
X 走了默认分支。」，但 `config/route_plan.yaml` 把 `replay` 当通用的"在状态 X
续讲"原语用（文件头规约第 1 条：每章首讲用 story，其后一律 replay；story 会
重发文本、破坏 A 段覆盖断言，所以路线作者别无选择）。评审实测 76 条 marker 里
30 条的 `at` 状态在那一刻从未被讲过（如 `config/route_plan.yaml:40` 的
`s1s_60`、`:46` 的 `s1s_130`、`:85` 的 `s2s_60`），这些"我们上一轮已经讲过这里"
的假陈述会直接进翻译上下文前缀（`marker.recap` 的存在意义）。

### 修复

`tools/gen_timeline.py::Expander.replay` 按 `at in self.emitted_states` 分两种
marker（判据：任何一条 marker 的字面陈述都必须与该时刻的实际讲述历史相符）：

```python
if at in self.emitted_states:
    self.emit_marker(f"【讲述指针回溯至 {at}，本次选第 {pick} 项】",
                     recap=f"重讲：指针回到 {at}，本次改选第 {pick} 项。")
else:
    self.emit_marker(f"【讲述指针移至 {at}】",
                     recap=f"讲述从 {at} 继续。")
```

- 已讲过（真·重讲）：保留"回溯"语义，但按评审要求同时修掉「走了默认分支」这句
  同样常不成立的陈述（上一轮可能是显式选的某一支），改为不预设上一轮选了什么；
- 未讲过（首次讲到）：发首访 marker，不用"回溯"/"上一轮"这类词，`pick` 对此时
  的 `at` 没有"重选"的意义，不塞进文案。

### TDD 证据

新增判别性测试 `test_replay_marker_text_matches_actual_narration_history`
（`tests/test_gen_timeline.py`）：同一套 DAG2/LEDGER2/S2C 上分别验证已讲过/
未讲过两种情形的 marker 文案（`text`/`recap` 精确字符串比对，外加"回溯"/
"上一轮"字样的排除断言）。

GREEN（产码已落地）：
```
$ uv run pytest -q tests/test_gen_timeline.py -v
19 passed
```

RED（临时删掉 `if at in self.emitted_states` 分支判断，改为无条件走"回溯"分支）：
```
$ uv run pytest -q tests/test_gen_timeline.py -k test_replay_marker_text_matches_actual_narration_history -v
FAILED tests/test_gen_timeline.py::test_replay_marker_text_matches_actual_narration_history
    assert markers2[0]["text"] == "【讲述指针移至 b_40】"
E   AssertionError: assert '【讲述指针回溯至 b_40，本次选第 1 项】' == '【讲述指针移至 b_40】'
E     - 【讲述指针移至 b_40】
E     + 【讲述指针回溯至 b_40，本次选第 1 项】
1 failed, 18 deselected in 0.04s
```
（对未讲过的 `b_40` replay，若无分支判断会被打上"回溯"字样，与情形一"已讲过"
时的真实重讲混同——判别性精确落在分支判断本身。）恢复产码行后重跑回到 GREEN；
`grep TEMP-RED tools/gen_timeline.py` 确认无残留。

### 真实数据验证

回归后重跑 `tools/gen_timeline.py`，对 76 条 marker 按"移至"（首访型）/"回溯"
（重讲型）分类：

```
$ uv run python3 -c "
import json
tl = [json.loads(l) for l in open('data/timeline.jsonl', encoding='utf-8') if l.strip()]
markers = [r for r in tl if r['type'] == 'marker']
first_visit = [m for m in markers if '移至' in m['text']]
true_replay = [m for m in markers if '回溯' in m['text']]
print(f'total={len(markers)} first_visit={len(first_visit)} true_replay={len(true_replay)}')
"
total markers=76  first_visit=30  true_replay=46
```

`first_visit=30` 与评审给出的"30 条"精确吻合。评审举的三个例子逐一核实：

```
seq=25 (config/route_plan.yaml:40, at: s1s_60):   text='【讲述指针移至 s1s_60】'
seq=40 (config/route_plan.yaml:46, at: s1s_130):  text='【讲述指针移至 s1s_130】'
seq=104(config/route_plan.yaml:85, at: s2s_60):   text='【讲述指针移至 s2s_60】'
```
三处均已从"回溯"改为"移至"，与评审判定一致。

`git diff data/timeline.jsonl`（相对 `3c3d884` 入库版本）核对：76 处 `+`/76 处
`-`，全部是 `"type":"marker"` 行，其余 unit 行（ids/state/title 等）字节不变——
`unit=457 marker=76 covered_ids=16693` 三个统计数字不变，只有 marker 文案内容
变化，符合"只修文案、不动结构"的预期。

## Finding 2 — `gates.yaml` 的 `s2s_10` 门控恒真（Important）

### 问题

`s2s_10` 在 `dag.json` 里只有 `card_gate`/`goto`，无 `play`/`subcall`，永远不
产生 unit；`tools/check_timeline.py` 里 `first_pos.get("s2s_10")` 恒为 `None`，
旧代码静默 `continue`，导致「进入 s2 前需 Section1 梗概」这条门控无论路线怎么
写都恒过——是一条假的保险丝。

### 修复（两处）

1. `tools/check_timeline.py`：门控状态从未作为 unit 出现时不再静默跳过，改为
   显式报错（错误串仍含"门控"关键词，契约不变）：

   ```python
   if pos is None:
       errs.append(f"门控: {g['unit_state']} 从未作为 unit 出现（门控落空）")
       continue
   ```

2. `config/gates.yaml`：把该条门控从 `s2s_10` 改锚到 `s2s_40`（本路线第 1 个
   真正产生 unit 的 s2 场景：`s2s_10` 首讲无卡31 → 跳过日常段 → `s2s_20`
   同样无 play → `s2s_40`「また、いつもの生活」→ `s2s_50` GAMEOVER），并写
   注释说明换锚点的原因。所需卡 `133`、门控语义均未变。

   **改前先用脚本核对全部 8 条门控**，确认仅 `s2s_10` 一条 vacuous（其余 7 条
   的 `unit_state` 在 `dag.json` 里都有 `play`/`subcall`），避免新报错逻辑落地
   后意外牵出别的落空门控：
   ```
   s2s_10  exists=True  has_play_or_subcall=False   ← 唯一问题项
   s3s_10  exists=True  has_play_or_subcall=True
   s5s_20  exists=True  has_play_or_subcall=True
   s7f-10  exists=True  has_play_or_subcall=True
   s8s_10  exists=True  has_play_or_subcall=True
   e1s_10  exists=True  has_play_or_subcall=True
   e2s_10  exists=True  has_play_or_subcall=True
   s3fc-10 exists=True  has_play_or_subcall=True
   ```
   并额外核实 `s2s_40` 确实是真实生成的 timeline 里第一个 `s2s_*` unit
   （`seq=101`），锚点选择有真实数据支撑而非猜测。

### TDD 证据

新增判别性测试 `test_gate_reports_error_when_unit_state_never_appears`
（`tests/test_check_timeline.py`）：给 `check()` 传一个 timeline 里不存在的
`unit_state`，断言返回的错误列表里有含"门控"字样的那条。

GREEN（产码已落地）：
```
$ uv run pytest -q tests/test_check_timeline.py -v
7 passed
```

RED（临时把 `if pos is None: errs.append(...)` 改回纯 `continue`）：
```
$ uv run pytest -q tests/test_check_timeline.py -k test_gate_reports_error_when_unit_state_never_appears -v
FAILED tests/test_check_timeline.py::test_gate_reports_error_when_unit_state_never_appears
    errs = check(_full_timeline(), LEDGER2, DAG2, S2C,
                 gates=[{"unit_state": "nonexistent_state", "requires_cards": [1]}])
>   assert any("门控" in e and "nonexistent_state" in e for e in errs)
E   assert False
1 failed, 6 deselected in 0.04s
```
恢复产码行后重跑回到 GREEN；`grep TEMP-RED tools/check_timeline.py` 确认无残留。

## 验收命令输出（评审修复后）

```
$ uv run pytest -q
.......................................................................  [100%]
71 passed in 2.02s

$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
$ sha256sum data/timeline.jsonl data/scene2card.json
a064fdf69e88c9b31636a49c8153d558fe030dd4d1f657303c50a0a67af5ac25  data/timeline.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json

$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
$ sha256sum data/timeline.jsonl data/scene2card.json
a064fdf69e88c9b31636a49c8153d558fe030dd4d1f657303c50a0a67af5ac25  data/timeline.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json

$ uv run python tools/check_timeline.py
OK
$ echo $?
0
```

双跑字节完全一致（sha256 相同）；`data/scene2card.json` 哈希与评审前一致（gates/
marker 改动都不影响它，符合预期，未额外改动它）；`git status --short
data/timeline.jsonl data/scene2card.json` 在两次 `gen_timeline.py` 重跑后均为
空——说明已提交的 `data/timeline.jsonl` 正是本次修复后的确定性产物，无残留
差异。`unit=457 marker=76 covered_ids=16693` 三项统计与评审前完全一致（两条
Finding 的修复都不改变展开结构，只改文案/门控判定）。

净增 2 条测试（Finding 1 一条、Finding 2 一条）：69 → 71 passed，无回归。

## 本次改动涉及的提交

- `4f730be` `fix: replay marker 文案按讲述历史分首访/重讲两型（Task 5 评审 Finding 1）`
  （`tools/gen_timeline.py` + `tests/test_gen_timeline.py` + `data/timeline.jsonl`）
- `a072f42` `fix: 门控落空态报错，s2s_10 门控改锚到真实产生 unit 的 s2s_40（Task 5 评审 Finding 2）`
  （`tools/check_timeline.py` + `tests/test_check_timeline.py` + `config/gates.yaml`）

`data/scene2card.json` 未改动（两条 Finding 均不影响它），未 `git add`。
`config/route_plan.yaml`、`config/unit_funcs.yaml` 未触碰；`config/gates.yaml`
仅改了 Finding 2 指定的那一条锚点（`s2s_10`→`s2s_40`），其余 7 条门控原样保留。

## 自评审（评审修复部分）

**完整性**：两条 Important 均已按评审给出的改法落地；Finding 1 的两处文案
（"回溯"分支的"走了默认分支"、首访分支的措辞）都改了，不是只改了一半；
Finding 2 的两处（check_timeline 报错 + gates.yaml 换锚点）都做了。两条新测试
均做过"临时去掉判断/报错逻辑 → 变红 → 恢复 → 变绿"的判别性验证。

**质量**：`replay()` 的 docstring 更新为说明两种 marker 的选择依据，并注明
出处（Task 5 评审 Finding 1）；`gates.yaml` 新增注释解释换锚点原因，附带
`s2s_10`/`s2s_20` 均无 play 的具体调用链，便于日后不再犯同样的错。错误消息
`f"门控: {X} 从未作为 unit 出现（门控落空）"` 严格采用评审给出的文案。

**纪律**：`config/route_plan.yaml`、`config/unit_funcs.yaml` 未碰；
`config/gates.yaml` 仅改了指定的那一条（用 `git diff config/gates.yaml` 核对
过，diff 只含 s2s_10→s2s_40 那一处替换 + 新增注释，其余 7 行未动）；`check()`
对外签名、四个中文错误关键词未变（"门控"关键词在新增错误消息里继续出现）；
按coordinator 指示把 `data/timeline.jsonl` 一并提交（现已入库，属于 Finding 1
改动的下游产物），`data/scene2card.json` 因无变化未动。

**测试**：两条新测试都测真实行为（marker 精确文案、错误列表内容），非空测；
全套 `uv run pytest -q` 输出干净，71 passed，无 warning、无回归。

## 遗留顾虑（评审修复部分）

1. **改前 7 条非 `s2s_10` 门控的 vacuous 排查是脚本一次性核对**，不是新增
   自动化测试——若未来 `dag.json` 因 lua 源变化导致某条门控的 `unit_state`
   变得不再产生 unit，`check_timeline` 现在会显式报错（Finding 2 的核心修复
   目的正是防止这种情况被静默吞掉），因此这个风险已经被结构性地兜住，无需
   额外测试。
2. **本报告前半部分（Hotfix C 原始实现）里"`data/timeline.jsonl`/
   `data/scene2card.json` 未入库"的表述已过时**——两文件已被主会话并发提交
   `3c3d884` 正式入库；本次 Finding 1/2 修复按当前实际状态操作（`data/
   timeline.jsonl` 已 `git add` 提交，`data/scene2card.json` 因无变化未动），
   未回改前半部分的历史记录，两处状态描述的时间点不同，均如实反映当时情况。

---

# 评审修复轮 2：重讲 marker 编造"选第 N 项"（Finding 1 / Finding 2 均判 ADDRESSED，本轮是修复 diff 自身引入的新 Important）

Finding 1、Finding 2 的独立复核结论：**ADDRESSED**（评审者独立重放 timeline，
首访/重讲两型归类 0 处错分；"默认分支"字样全库归零；门控落空分支与重锚均核过，
`check_timeline` 仍 OK）。但评审同时发现修复 diff 自身引入了一条新 Important，
本节记录其修复过程。

## 问题

`tools/gen_timeline.py` 里 Finding 1 加的"已讲过"分支无条件写"本次选第 {pick}
项"/"本次改选第 {pick} 项"，但从未检查 `at` 在 `dag.json` 里是否真的存在
`choice` 事件。评审对照 `data/dag.json` 核实：`s2s_380`、`s3s_375`、`s3s_410`、
`s3s_600`、`s4s_70` 这几个状态的 `seq` 里一个 `choice` 事件都没有（只有线性
`goto`，或 `card_gate`/`route_has` 这类由引擎而非玩家解的条件分支）；已入库
的 `data/timeline.jsonl` 里 46 条"回溯"marker 中有 7 条（seq 157、229、252、
254、262、346、500，来源 `config/route_plan.yaml:100,131,139,140,142,173,233`）
正好指向这些状态却声称"本次选第 1 项"——凭空捏造了游戏脚本里根本不存在的
玩家选择，与 Finding 1 自己写下的验收判据不符。

复现验证（改前）：

```
$ uv run python3 -c "
import json
dag = json.loads(open('data/dag.json', encoding='utf-8').read())
for s in ('s2s_380','s3s_375','s3s_410','s3s_600','s4s_70'):
    st = dag['states'].get(s)
    print(s, 'has_choice=', any('choice' in ev for ev in (st or {}).get('seq', [])))
"
s2s_380 has_choice= False
s3s_375 has_choice= False
s3s_410 has_choice= False
s3s_600 has_choice= False
s4s_70  has_choice= False

$ uv run python3 -c "
import json
tl = [json.loads(l) for l in open('data/timeline.jsonl', encoding='utf-8') if l.strip()]
by_seq = {r['seq']: r for r in tl}
for seq in (157,229,252,254,262,346,500):
    print(seq, by_seq[seq]['text'])
"
157 【讲述指针回溯至 s2s_380，本次选第 1 项】
229 【讲述指针回溯至 s3s_375，本次选第 1 项】
252 【讲述指针回溯至 s3s_375，本次选第 1 项】
254 【讲述指针回溯至 s3s_410，本次选第 1 项】
262 【讲述指针回溯至 s3s_600，本次选第 1 项】
346 【讲述指针回溯至 s3s_600，本次选第 1 项】
500 【讲述指针回溯至 s4s_70，本次选第 1 项】
```
逐条与评审指出的 5 个状态、7 个 seq 精确吻合。

## 修复

`replay()` 的"已讲过"分支再按 `dag["states"][at]["seq"]` 是否含 `choice` 事件
拆一层：

```python
seq = self.dag["states"].get(at, {}).get("seq", [])
has_choice = any("choice" in ev for ev in seq)
if at in self.emitted_states and has_choice:
    self.emit_marker(f"【讲述指针回溯至 {at}，本次选第 {pick} 项】",
                     recap=f"重讲：指针回到 {at}，本次改选第 {pick} 项。")
elif at in self.emitted_states:
    self.emit_marker(f"【讲述指针回溯至 {at}】",
                     recap=f"重讲：指针回到 {at}，从这里再讲一遍。")
else:
    self.emit_marker(f"【讲述指针移至 {at}】",
                     recap=f"讲述从 {at} 继续。")
```

- 已讲过 且有 `choice`：保留"选第 N 项"（玩家在游戏里真实能做的选择）；
- 已讲过 但无 `choice`：改用不声称选项的说法（评审建议文案，原样采用）；
- 未讲过（首访型）：不变，Finding 1 已经处理过。

顺带按评审要求把 `dag["states"][at]` 的取值方式改成 `self.dag["states"].get(at,
{})`——`at` 不在 `dag["states"]` 里时这里不再抛 `KeyError`，留给随后
`self.story(at, ...)` 内部 `if st is None: raise KeyError(...)` 抛出语义更清楚
的异常（该行为未变，`replay()` 本来就会调用 `story()`，这里只是不在 marker
文案组装这一步提前抛错）。

## TDD 证据

新增 2 条判别性测试（`tests/test_gen_timeline.py`）：

1. `test_replay_marker_omits_pick_claim_for_state_without_choice_event`：用
   DAG2 的 `b_10`（已讲过、`seq` 只有 `play`+`goto`，无 `choice`）复现最小
   场景，断言 marker 的 `text`/`recap` 都不含"选"字。
2. `test_replay_marker_keeps_pick_claim_for_true_choice_state`：对照组，
   `b_20_sel`（已讲过、`seq` 里确有 `choice`）重讲时文案仍要有"选第 N 项"，
   确认两条测试精确隔离、互不掩盖。

GREEN（产码已落地）：
```
$ uv run pytest -q tests/test_gen_timeline.py -k "test_replay_marker_omits_pick_claim_for_state_without_choice_event or test_replay_marker_keeps_pick_claim_for_true_choice_state or test_replay_marker_text_matches_actual_narration_history" -v
3 passed
```

RED（临时删掉 `has_choice` 这层判断，让"已讲过"分支无条件走"选第 N 项"文案）：
```
$ uv run pytest -q tests/test_gen_timeline.py -k "test_replay_marker_omits_pick_claim_for_state_without_choice_event or test_replay_marker_keeps_pick_claim_for_true_choice_state" -v
tests/test_gen_timeline.py::test_replay_marker_omits_pick_claim_for_state_without_choice_event FAILED
tests/test_gen_timeline.py::test_replay_marker_keeps_pick_claim_for_true_choice_state PASSED
    assert markers[0]["text"] == "【讲述指针回溯至 b_10】"
E   AssertionError: assert '【讲述指针回溯至 b_10，本次选第 1 项】' == '【讲述指针回溯至 b_10】'
E     - 【讲述指针回溯至 b_10】
E     + 【讲述指针回溯至 b_10，本次选第 1 项】
1 failed, 1 passed, 19 deselected in 0.04s
```
测 1（无 choice 场景）精确变红，测 2（对照组，有 choice 场景）保持绿——证明
两条测试各自精确锚定自己的场景，`has_choice` 判断被删掉时只有"该声明但不该
声明选项"的场景会出错，判别性成立、互不掩盖。恢复产码行后重跑回到 GREEN；
`grep TEMP-RED tools/gen_timeline.py tools/check_timeline.py` 确认无残留。

## 全量核对（按 coordinator 要求，对全部 76 条 marker 逐条核实两项判据）

直接驱动真实全书 `Expander`（`config/route_plan.yaml` 的 226 条移动），用一个
包一层日志的 `replay` 方法记录每次调用时的 `at`/`was_emitted`/`has_choice`，
与实际产出的 marker 逐一交叉核对——核对的是"真实运行代码产出的文案"，不是
"重新实现一遍判定逻辑再自我比对"（脚本存于 scratchpad，未入库）：

```
$ uv run python audit_markers.py
replay() 调用总数（= marker 总数）: 76
(a) 首访/重讲归类违例: 0
(b) 选项声明违例（声明选项但 at 无 choice 事件）: 0

首访型: 30
重讲型（合计）: 46
  其中 at 有 choice 事件（应声明 pick）: 39
  其中 at 无 choice 事件（不应声明 pick）: 7
marker 文案里实际声明了 pick 的条数: 39
总违例数: 0
```

两项判据（a 首访/重讲归类是否与实际讲述历史相符、b 凡声明选项的 at 是否确有
choice 事件）在全部 76 条 marker 上均为 **0 违例**。"重讲型里 7 条无 choice"
与评审指出的"7 条"精确吻合（即上文复现验证里的 7 个 seq）；逐条复核这 7 个
seq 现在的文案：

```
157 【讲述指针回溯至 s2s_380】       | 重讲：指针回到 s2s_380，从这里再讲一遍。
229 【讲述指针回溯至 s3s_375】       | 重讲：指针回到 s3s_375，从这里再讲一遍。
252 【讲述指针回溯至 s3s_375】       | 重讲：指针回到 s3s_375，从这里再讲一遍。
254 【讲述指针回溯至 s3s_410】       | 重讲：指针回到 s3s_410，从这里再讲一遍。
262 【讲述指针回溯至 s3s_600】       | 重讲：指针回到 s3s_600，从这里再讲一遍。
346 【讲述指针回溯至 s3s_600】       | 重讲：指针回到 s3s_600，从这里再讲一遍。
500 【讲述指针回溯至 s4s_70】        | 重讲：指针回到 s4s_70，从这里再讲一遍。
```
均已不再声明"选第 N 项"。

## 验收命令输出

```
$ uv run pytest -q
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 1.94s

$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
$ sha256sum data/timeline.jsonl data/scene2card.json
23933e9bf3c2dfac45aba7f33f509ea44dec3e98611a9b5a85e0be91f3cd995f  data/timeline.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json

$ uv run python tools/gen_timeline.py
scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
$ sha256sum data/timeline.jsonl data/scene2card.json
23933e9bf3c2dfac45aba7f33f509ea44dec3e98611a9b5a85e0be91f3cd995f  data/timeline.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json

$ uv run python tools/check_timeline.py
OK
$ echo $?
0
```

双跑字节完全一致；`data/scene2card.json` 哈希与修复前一致（未受影响，未动）；
`unit=457 marker=76 covered_ids=16693` 三项统计不变（只改了 7 条 marker 的
文案内容，不影响展开结构）。`git diff --stat data/timeline.jsonl`（相对
`2ef6e0e` 之前的已入库版本）为 `7 insertions(+), 7 deletions(-)`，且全部 14
行都是 `"type":"marker"` 行（`grep -vc` 核对非 marker 行改动为 0），其余 unit
行字节不变。

净增 2 条测试：71 → 73 passed，无回归。

## 本轮改动涉及的提交

- `2ef6e0e` `fix: 重讲 marker 只在 at 真有 choice 事件时才声称"选第 N 项"（Task 5 评审修复轮 2）`
  （`tools/gen_timeline.py` + `tests/test_gen_timeline.py` + `data/timeline.jsonl`）

`data/scene2card.json`、`config/route_plan.yaml`、`config/unit_funcs.yaml`、
`config/gates.yaml` 均未触碰。

## 自评审（修复轮 2）

**完整性**：`has_choice` 判断已加在"已讲过"分支内部，首访分支未受影响（评审
未要求改它）；`.get(at, {})` 的防御性取值已按要求落地；全量核对脚本证明全部
76 条 marker（不只是新增测试覆盖的最小场景）在真实数据上两项判据均 0 违例。

**质量**：docstring 更新为三分支说明（已讲过+有choice / 已讲过+无choice /
未讲过），并标注"修复轮 2"以便追溯；错误场景的判别性测试与对照组测试成对
出现，互相印证边界不被误伤。

**纪律**：`config/route_plan.yaml`、`config/unit_funcs.yaml`、
`config/gates.yaml` 未碰；`data/scene2card.json` 因未受影响未动；只提交了
本轮实际改动的 3 个文件。

**测试**：2 条新测试 + 1 条独立于单测的全量核对脚本（直接驱动真实 Expander，
不是重新实现判定逻辑后自证），三者共同覆盖"最小场景判别性"与"全量数据
无遗漏"两个维度。

## 遗留顾虑（修复轮 2）

1. **全量核对脚本 `audit_markers.py` 未入库**：按"scratchpad 临时脚本"的
   惯例处理（类似 Hotfix B 报告里"真实数据冒烟验证...未落盘任何产物"的先例），
   其逻辑已完整记录在本报告（直接驱动真实 `Expander.replay`，日志式核对，
   非重新实现判定逻辑），如需要可随时按此记录重新写出复跑。
2. **`has_choice` 只检查 `at` 状态自身的 `seq`，不检查其下游状态**：这与
   `replay(at, pick, until)` 的语义一致——`pick` 参数本来就只对 `at` 这一个
   状态的 `choice` 事件生效（`story()` 里 `choices.setdefault(state, ...)`
   只在 `state == at` 且该状态有 `choice` 事件时起作用），若未来 route_plan
   出现"pick 打算作用于 at 下游某个选择点"的用法，当前实现会认为 `at` 无
   choice 从而不声明 pick——这是符合当前 DSL 语义的正确行为，不是遗漏。
