# Hotfix B 报告：发卡语义三处补齐（B1/B2/B3）

## 实现内容

### B1 — `tools/build_dag.py::parse_crds`：新增 `gets` 字段

```python
"gets": sorted({int(x) for x in GET_RE.findall(t)}),
```

复用已有的模块级 `GET_RE = re.compile(r'gameSave\.myCard\[(\d+)\]\.hold = 1')`（`parse_scene_meta`
已在用同一正则），未按 brief 原文另起一条字面量正则——两者对全部真实 crd 文本产出结果
完全一致（已用 grep 核实全库 crd 里没有不带 `gameSave.` 前缀的 `myCard[N].hold = 1` 写法），
复用避免同义正则抄两份。`crds` 字典键顺序仍由 `json.dumps(..., sort_keys=True)` 自动排序，
未手动调整。

该卡自身的授予写作 `gameSave.myCard[fragmentDoCardId].hold = 1`（变量下标），`\d+` 分组天
然不命中，符合 brief"这正是我们要的"的预期。

**实测命中**（对全部 196 个 crd 脚本跑一遍，仅列非空）：

| crd | gets |
|---|---|
| 10 | [126] |
| 51 | [115] |
| 56 | [97] |
| 177 | [93, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 195] |

与 brief 举例的 crd_10/51/56 三处精确吻合；额外发现 crd_177（サクラさん，日记章解锁）
一次性字面量发出 16 张日记卡（178-191 + 93 + 195），与 CLAUDE.md「crd_177 向彩野上交全部
章节梗概后一次性解锁」的描述完全对应——同一条正则规则自然覆盖了这个更大的真实场景，
不需要为它单独写代码。

### B2 — `tools/gen_timeline.py::Expander.fragment_sweep`：生效两类发卡

```python
self.held.add(cid)
self.held.update(crd.get("gets", []))          # 新增：crd 自身附带发出的别的卡
for runf in crd.get("runs", []):
    fs = sorted({fn for (f, fn) in self.by_filefunc if f == runf})
    self.emit_unit("fscene", runf, None, runf, fs)
    for fn in fs:
        self._apply_meta(fn)                     # 新增：_f 章全部函数的 scene_meta.gets
```

两处都在 `for state in list(self.route)` 循环内、紧随该卡 `emit_unit` 之后立即写入
`self.held`，满足 brief"循环内即时生效"的顺序要求（同一次 sweep 里 route 序靠后的卡能
立刻用上刚发的卡）。顺手把 `self.dag["crds"].get(str(cid), {})` 从两次查询合并成一次
`crd = ...` 局部变量复用（`gets`/`runs` 各用一次），非额外重构，是新增 `gets` 读取的自然
产物。

### B3 — `tools/check_timeline.py`：抽出 `_grant` 共用辅助函数

```python
def _grant(held, unit, dag, scene2card, file_funcs):
    kind = unit.get("unit_kind")
    state = unit.get("state")
    if kind == "scene":
        for ev in dag["states"].get(state or "", {}).get("seq", []):
            if "play" in ev:
                held.update(dag["scene_meta"].get(ev["play"], {}).get("gets", []))
            elif "subcall" in ev:
                held.update(dag["scene_meta"].get(ev["subcall"], {}).get("gets", []))
    elif kind == "card":
        cid = scene2card.get(state)
        held.add(cid)
        held.update(dag["crds"].get(str(cid), {}).get("gets", []))
    elif kind == "fscene":
        for fn in file_funcs.get(unit.get("src"), ()):
            held.update(dag["scene_meta"].get(fn, {}).get("gets", []))
```

签名与 brief 建议完全一致：`_grant(held, unit, dag, scene2card, file_funcs)`。`file_funcs`
（narrative 的 file→{func,…} 反查表）在 `check()` 里从 `ledger_rows` 建一次，B 段
（`for pos, u in enumerate(timeline)` 循环内顺序累积）与 C 段（门控表对 `timeline[:pos]`
重扫）都调它，不再各自维护一份 held 推导逻辑。

原 C 段的问题不只是"缺 fscene 分支"，还有一处隐藏的冗余/歪差：旧代码对**每一种** unit
（包括 card/script/pool）都无条件执行 `dag["states"].get(u.get("state") or "", {})...`，
对 card unit 而言这会把它继承自原场景的 `state` 再查一遍 `play` 事件的 gets——与该场景
自己的 scene unit 重复计算（`set.update` 幂等所以不算错，但是浪费且掩盖了"fscene 完全
没处理"这个真正的洞）。重构后 card 分支只经手卡本身与 `crds[cid]["gets"]`，scene 的
play/subcall gets 只由对应的 scene unit 贡献一次，逻辑更干净。

`check()` 对外签名 `check(timeline, ledger_rows, dag, scene2card, gates) -> list[str]`、
四个中文错误关键词（重复/缺失/门控/req）、A 段覆盖断言、`config/gates.yaml` 均未触碰
（已用 grep 核对，见下文"验收"）。

## TDD 证据

### 测试 1 — `parse_crds` 字面量 vs 自身变量授予（`tests/test_build_dag.py`）

放在 `test_build_dag.py` 而非 brief 标题句提到的 `test_gen_timeline.py`/`test_check_timeline.py`
二选一——`parse_crds` 本身定义在 `build_dag.py`，其单测天然归属 `test_build_dag.py`（该文件
已有 `parse_states`/`parse_scene_meta` 的同类单测），标题句的两文件列举与编号列表第 1 条
的实际内容（build_dag.py 的函数）不一致，判断为 brief 的措辞疏漏，按内容而非标题句归档；
未就此打断去问，因为落哪个文件不影响判别性与验收标准，损益很小、可判断，符合 auto 模式
"该做判断就做判断"的指引。

RED（先加测试，未加产码）：
```
$ uv run pytest tests/test_build_dag.py -k test_parse_crds_captures_literal_gets_but_not_self_grant_variable -v
FAILED tests/test_build_dag.py::test_parse_crds_captures_literal_gets_but_not_self_grant_variable
E       assert crds["10"]["gets"] == [126]
E       KeyError: 'gets'
1 failed, 10 deselected in 0.05s
```

GREEN（加 B1 产码后）：
```
$ uv run pytest tests/test_build_dag.py -k test_parse_crds_captures_literal_gets_but_not_self_grant_variable -v
tests/test_build_dag.py::test_parse_crds_captures_literal_gets_but_not_self_grant_variable PASSED
1 passed, 10 deselected in 0.03s
```

判别性复核（把 `"gets": sorted(...)` 那一行从 `parse_crds` 删掉，只留其余字段）：
```
$ uv run pytest tests/test_build_dag.py -k test_parse_crds_captures_literal_gets_but_not_self_grant_variable -v
FAILED ... KeyError: 'gets'
1 failed, 10 deselected in 0.04s
```
删产码行 → 变红，确认判别性成立；随即恢复该行。

### 测试 2 — crd 自身 `gets` 在同一次 sweep 内解锁依赖卡（`tests/test_gen_timeline.py`）

构造：crd 30 的 `gets=[99]` 恰是 crd 40 的 `req`，两张卡在同一条 route（`x_10`→`x_20`）上，
只调用一次 `fragment_sweep()`。

RED：
```
$ uv run pytest tests/test_gen_timeline.py -k test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep -v
FAILED tests/test_gen_timeline.py::test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep
E       AssertionError: 两张卡都应同批做成，得 ['x_10']
E       assert ['x_10'] == ['x_10', 'x_20']
1 failed, 15 deselected in 0.06s
```

GREEN（加 B2 的 `self.held.update(crd.get("gets", []))` 后）：
```
$ uv run pytest tests/test_gen_timeline.py -k test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep -v
PASSED
1 passed, 15 deselected in 0.02s
```

判别性 + 隔离性复核（只删 `self.held.update(crd.get("gets", []))` 这一行，保留 fscene 那段）：
```
$ uv run pytest tests/test_gen_timeline.py -k "test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep or test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets" -v
tests/test_gen_timeline.py::test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep FAILED
tests/test_gen_timeline.py::test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets PASSED
1 failed, 1 passed, 14 deselected in 0.03s
```
测 2 单独变红、测 3 保持绿——证明测 2 精确锚定这一行，不受另一条 fscene 逻辑影响；随即恢复。

### 测试 3 — fscene 令 `_f` 文件的 `scene_meta.gets` 生效（`tests/test_gen_timeline.py`）

构造：crd 50 的 `runs=["snr_y_10_f"]`，该文件的 `scene_yf_complete` 函数 `gets=[133]`。

RED：
```
$ uv run pytest tests/test_gen_timeline.py -k test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets -v
FAILED tests/test_gen_timeline.py::test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets
E       assert 133 in {50}
1 failed, 15 deselected in 0.06s
```

GREEN（加 B2 的 `for fn in fs: self._apply_meta(fn)` 后）：
```
$ uv run pytest tests/test_gen_timeline.py -k test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets -v
PASSED
1 passed, 15 deselected in 0.02s
```

判别性 + 隔离性复核（只删 `for fn in fs: self._apply_meta(fn)` 两行，保留 crd-gets 那行）：
```
$ uv run pytest tests/test_gen_timeline.py -k "test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep or test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets" -v
tests/test_gen_timeline.py::test_fragment_sweep_crd_gets_unblocks_dependent_card_in_same_sweep PASSED
tests/test_gen_timeline.py::test_fragment_sweep_fscene_applies_f_chapter_scene_meta_gets FAILED
1 failed, 1 passed, 14 deselected in 0.04s
```
测 3 单独变红、测 2 保持绿——两条互不干扰、各自精确锚定自己的产码行；随即恢复。

### 测试 4 — `check()` 认可 crd/fscene/subcall 三路发卡满足的 req（`tests/test_check_timeline.py`）

手写 timeline（不经 `Expander`，保持模块 docstring 所说的"独立于展开器重放验证"）：卡 70
的 `req=[201,202,203]` 分别来自 scene 的 subcall（201）、crd60 自身 `gets`（202）、
crd60.runs 触发的 `_f` 章 fscene `gets`（203）。

RED（B3 之前，即便 B1/B2 已落地，`check()` 自己的独立推导仍不认这三路）：
```
$ uv run pytest tests/test_check_timeline.py -k test_check_accepts_req_satisfied_by_crd_and_fscene_and_subcall_grants -v
FAILED tests/test_check_timeline.py::test_check_accepts_req_satisfied_by_crd_and_fscene_and_subcall_grants
E       AssertionError: assert ['card unit z_20: req [201, 202, 203] 未满足（held 缺 [201, 202, 203]）'] == []
1 failed, 4 deselected in 0.03s
```

GREEN（加 `_grant` 并让 B/C 两段都用它之后）：
```
$ uv run pytest tests/test_check_timeline.py -v
tests/test_check_timeline.py::test_clean_timeline_passes PASSED
tests/test_check_timeline.py::test_missing_and_duplicate_ids_detected PASSED
tests/test_check_timeline.py::test_gate_violation_detected PASSED
tests/test_check_timeline.py::test_crd_req_violation_detected PASSED
tests/test_check_timeline.py::test_check_accepts_req_satisfied_by_crd_and_fscene_and_subcall_grants PASSED
5 passed in 0.02s
```
手工推演过：held 缺 [201,202,203] 三个值同时缺失，任意一路发卡机制（scene subcall /
card 自身 gets / fscene）失效都会让 `errs` 非空——故此测试对 B3 整体是判别性的（B3 是
brief 明确给出的单一原子改法，未再拆子项各自独立测试，符合 brief 编号列表的粒度）。

## `data/dag.json` 前后差异摘要

```
$ git diff --stat 65b7d35 3c7c609 -- data/dag.json
 data/dag.json | 219 +++++++++++++++++++++++++++++++++++++++++++++
 1 file changed, 219 insertions(+)
```

全部为新增行（0 删除、0 修改其他字段）——`sort_keys=True` 下 `gets` 键排在
`answers`/`gets`/`req`/`runs`/`stub` 字母序第 2 位，196 个 crd 条目全部新增该键；192 个空
`gets: []` 各占 1 行（pretty-print 空容器不换行），4 个非空条目按元素个数各占
`2 + len(gets)` 行（10→3 行、51→3 行、56→3 行、177→18 行）。算术核对：
`192×1 + 3+3+3+18 = 192+27 = 219`，与 diff 行数精确一致，佐证改动确为"只加一个字段、不
动其他内容"。

抽样（`crds` 里 `gets` 非空的全部 4 条，即全量，无需再抽）：见上文 B1 小节的表格。

## 双跑确定性验证

先用 sha256 核对同一目录连续两次写出字节完全相同：
```
$ sha256sum data/dag.json
$ uv run python tools/build_dag.py
$ sha256sum data/dag.json
IDENTICAL across repeated runs
```

提交后按 brief 验收命令字面重跑一次（此时 `git diff` 是相对刚提交的 HEAD，理应为空）：
```
$ uv run python tools/build_dag.py && uv run python tools/build_dag.py && git diff --stat data/dag.json
states=405 scene_meta=527 crds=196
states=405 scene_meta=527 crds=196
（无输出，diff 为空）
```

`tests/test_build_dag.py::test_cli_double_run_is_byte_identical`（既有测试，覆盖两个独立
`--out-dir` 的字节级比较）与 `test_cli_check_matches_committed_dag`（`--check` 子命令）均
在全套里保持绿。

## 全套测试结果

提交前（B1+B2+B3 代码与全部 4 条新测试都已落地）：
```
$ uv run pytest -q
..................................................................       [100%]
66 passed in 2.0s左右
```
基线 62 passed（本次工作开始前确认过），净增 4（测试 1/2/3/4），无回归、无 warning。

提交后复跑（工作区干净，仅剩不属于本次任务的两个未跟踪文件）：
```
$ uv run pytest -q
..................................................................       [100%]
66 passed in 1.96s
```

## 真实数据冒烟验证（额外确认，非任务硬性要求，未落盘任何产物）

用 `data/dag.json` + `data/ledger.jsonl` + 现算的 `parse_scene2card(snr_common.lua)`
（全部只读，未写 `data/timeline.jsonl`/`data/scene2card.json`）直接驱动 `Expander`：

1. **crd51/56 真实依赖链**：`sceneId2aCard` 反查确认 crd51↔`s2s_340_sel`（req=[97]）、
   crd56↔`s2s_420`（gets=[97]，req=[57]）。手工把 `ex.route=["s2s_420","s2s_340_sel"]`、
   `ex.held={57}` 后跑一次 `fragment_sweep()`：两张卡同批做成，`held` 里 56/97/51/115 全部
   到手——与 brief"卡 97 在全库没有任何其他获得途径…不补这条第 2 章半数卡片做不成"的
   描述完全对应，证明修复解决的是真实存在的问题而不只是构造场景。
2. **crd30 → snr_s1_10_f → 卡 133**：`crd 30` 是 `req=[1,2,10,19,21,28,29]`、
   `runs=["snr_s1_10_f"]` 的真实终章卡（对应 CLAUDE.md"各章终卡"列表里的 30）。把前置
   卡喂满后跑 `fragment_sweep()`：`133 in ex.held` 为真，且 `fscene` unit 精确带出
   `snr_s1_10_f` 全部 527 条左右 narrative id 中属于该文件的那一段（`scene_s1f_complete`
   等）。验证了"章梗概卡 133-145 由各 _f 章 *_complete 场景授予"这条链路在真实数据下
   已经打通。

## Self-Review

- **完整性**：B1/B2/B3 三处均已改动并各自验证；4 条新测试逐条做过"删产码行必红"的
  判别性复核（测 2/测 3 额外做了互相隔离的交叉验证，确认二者精确锚定各自的产码行、互不
  掩盖）。`data/dag.json` 已重新生成入库，双跑确定性（同目录连续两次 + 独立目录字节比较
  + `--check`）三种方式都验证过。
- **质量**：`_grant` 命名与参数顺序与 brief 建议逐字一致，职责单一（对一个 unit 施加它
  带来的发卡，不掺入 route/prefix 校验等其他逻辑），docstring 写清了三种 unit_kind 各自
  的口径来源，方便下一步 Hotfix C 按其 brief 描述的方式在此基础上扩展（读过
  `hotfix-c-brief.md`：C3 明确说"就是 Hotfix B 已经抽好的那个共用辅助函数，只是把它的
  推导换成四路的并集"——当前 `_grant` 的签名与两处调用点结构与该期望吻合）。B1 复用既有
  `GET_RE` 而非按 brief 示例另起一条同义正则，减少重复。B2 顺手把 crds 查询去重为一个
  局部变量，是新增字段读取的自然产物，不算额外重构。
- **纪律**：`config/route_plan.yaml`、`config/unit_funcs.yaml`、`config/gates.yaml`、
  `data/timeline.jsonl`、`data/scene2card.json` 全程未写入（已用 `git diff --stat` 核对
  前四者为空、后两者仍为未跟踪状态）。未提前实现 `hotfix-c-brief.md` 里已经预告"会替换
  掉 B 的 fscene 特例"的统一化改法——那是另一个子代理的任务范围，本次严格只做 brief 给定
  的 B1/B2/B3。commit message 未使用 `git add -A`/`.`，两次提交均用显式路径列表，避免
  误收主会话并发写入的 `config/route_plan.yaml` 等文件（提交时确认过这些文件已被主会话
  自己的 commit `65b7d35` 收掉，与本次改动无交集）。
- **测试**：4 条新测试全部测真实行为（不是"调用了某函数"这类空测），每条都有独立的
  RED/GREEN 证据；全套 `uv run pytest -q` 输出干净，无 warning、无 skip。测试 1 的文件
  归属与 brief 标题句字面不完全一致，已在"TDD 证据"小节说明改判依据。

## 遗留顾虑

1. **测试 1 的文件归属**：brief 正文"在 `tests/test_gen_timeline.py` 与
   `tests/test_check_timeline.py` 各补最小用例"这句话字面只提了两个文件，但编号列表第 1
   条测的是 `build_dag.py::parse_crds`，按函数归属放进了 `tests/test_build_dag.py`。判断
   这是 brief 措辞疏漏，未就此打断确认（影响面小、方向明确）；若与预期不符，改动位置容易
   调整，不影响判别性本身。
2. **B3 测试的粒度**：brief 编号列表第 4 条把 crd/fscene/subcall 三路发卡合并成一个场景
   测试（而不是三条独立测试），照此实现。若后续希望把三路拆成三条独立判别性测试（每条
   只锚定 `_grant` 的一个 `elif` 分支），目前的单测尚未覆盖"只删 `_grant` 里某一个分支、
   其余分支仍工作"这种更细粒度的隔离——但这已超出 brief 给出的验收粒度，未主动扩做。
3. **已知会被 Hotfix C 覆盖的部分**：读到 `hotfix-c-brief.md` 后得知，B2 里 `fragment_sweep`
   新增的 `for fn in fs: self._apply_meta(fn)`（fscene 的 `_apply_meta` 循环）在 Hotfix C
   落地后会被删除、改为 `emit_unit` 内部对"实际匹配到的全部函数"统一施加——这是 brief 已
   预告的既定计划，非本次实现的缺陷，此处仅作说明性记录，未提前改动（不在本次任务范围）。
   `_grant` 的 C3 部分同理预期会被 Hotfix C 替换推导口径（四路并集），当前实现是 B3
   brief 明确要求的版本，未越权预实现 C3。
4. **并发环境**：实施期间主会话并发提交了 `65b7d35`（全书 route_plan 等内容资产），已
   核实与本次改动的 7 个文件（`tools/build_dag.py`、`tools/gen_timeline.py`、
   `tools/check_timeline.py`、`data/dag.json`、三个测试文件）无交集，两次提交均基于最新
   HEAD 顺利完成，无冲突。
