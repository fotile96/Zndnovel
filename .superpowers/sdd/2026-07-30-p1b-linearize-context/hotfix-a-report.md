# Hotfix A 报告：build_ledger.py 函数归属改为嵌套栈追踪

## 实现内容

`tools/build_ledger.py::parse_vms_lines` 的函数归属逻辑从"平面变量"改为"嵌套栈"：

- 新增 `END_RE = re.compile(r'^(\s*)end\b')`、`BARE_VN_RE = re.compile(r'^v\d+$')`。
- `FUNC_RE` 原样保留；匹配时改为 `stack.append((名字, m.start(1)))`——`m.start(1)` 就是
  `^\s*` 消耗掉的前导空白字符数，与手写 `len(前导空白)` 等价，省去二次计算。
- 新增 `END_RE` 匹配且栈非空且 `len(前导空白) == 栈顶.indent` 时 `stack.pop()`。
- 新增辅助函数 `_owner_func(stack)`：从栈顶向外找第一个不匹配 `^v\d+$` 的名字；全是裸
  vN 则取最外层（`stack[0][0]`）；栈空则 `""`。
- `vms` 行的 `func` 字段从 `func`（平面变量）改为 `_owner_func(stack)`。

`VMS_RE`/`TR_LINE_RE`/`parse_extra`/`classify`/`chapter_of`/`build`/`main` 未触碰，仅
`parse_vms_lines` 内部逻辑改动，符合 brief "只改函数归属逻辑" 的限定。

## TDD Evidence

### RED

先扩展 `tests/test_build_ledger.py`：
1. 修正了已被平面实现"带偏"的既有断言 `test_func_tracking_follows_nearest_function_opener`
   （原断言 `rows[2]["func"] == "v0"` 编码的正是要修的 bug；重命名为
   `test_func_tracking_bubbles_past_bare_vn_to_named_opener` 并改断言为
   `"scene_x1_10"`）。
2. 新增 brief 四组用例：`test_case1_parent_body_rebounds_after_closure_end`（父体回弹，
   直接取材 brief 背景示例的空闭包结构）、`test_case2_vms_inside_bare_vn_closure_bubbles_to_parent`
   （闭包内穿透）、`test_case3_dotted_name_keeps_own_ownership`（带点名字保留）、
   `test_case4_toplevel_vms_after_function_end_has_empty_func`（弹栈后顶层复位）。
3. 新增全库回归测试 `test_real_repo_no_bare_vn_func_residue`（详见下方"已知例外"）。

命令与输出（修复前，`tools/build_ledger.py` 仍是平面实现）：

```
$ uv run pytest tests/test_build_ledger.py -k "case1 or case2 or case4 or bubbles_past_bare_vn_to_named" -v
tests/test_build_ledger.py::test_func_tracking_bubbles_past_bare_vn_to_named_opener FAILED
tests/test_build_ledger.py::test_case1_parent_body_rebounds_after_closure_end FAILED
tests/test_build_ledger.py::test_case2_vms_inside_bare_vn_closure_bubbles_to_parent FAILED
tests/test_build_ledger.py::test_case4_toplevel_vms_after_function_end_has_empty_func FAILED
======================= 4 failed, 11 deselected in 0.04s =======================
```

四个失败均为 `AssertionError: assert 'v0' == 'scene_x1_10'`（或对称情形），失败原因是
"func 仍停在裸 vN / 停在已结束的子函数上"，与要修的缺陷完全对应，不是笔误或环境错误。

`test_case3_dotted_name_keeps_own_ownership` 在这一步是**通过**的（未红）——已在报告中
说明原因：平面实现下，`v0.mesNot = function()` 这一行本身就把 `func` 平面赋值为
`"v0.mesNot"`，而紧随其后的 vms 调用不涉及"跨越已结束的子函数回弹"，所以平面实现碰巧也
是对的。brief 原文也把这一条定性为"必须保持不变"的非回归项，而非要修的 bug，与此结果一致。

跑当时的全库残留统计（`test_real_repo_no_bare_vn_func_residue` 早期版本，断言严格
`== []`）：

```
AssertionError: 仍有 12042 行 func 落在裸 vN
```

### GREEN

实现嵌套栈追踪后：

```
$ uv run pytest tests/test_build_ledger.py -v
...
14 passed （当时残留断言严格 == []，此步骤该测试仍红，见下）
```

全库残留从 12042 降到 24（全部集中在 `snr_crd_102`，根因见下）。按 brief "不要为凑 0
而改规则" 的指示，没有改归属算法去消灭这 24 行，而是把 `test_real_repo_no_bare_vn_func_residue`
改写为"已知例外清单 + 计数钉死"的断言（同 repo 里 `AMBIENT_FUNC_EXCEPTIONS` /
`NARRATIVE_FUNC_EXCEPTIONS` 一样的写法），使其可解释、可复查、不再永久发红：

```
$ uv run pytest -q
............................................                             [100%]
44 passed in 1.65s
```

（44 = 修复前 39 个既有测试 + 新增 5 个：case1-4 共 4 个 + 全库裸 vN 残留回归 1 个；
1 个既有测试被重命名/改断言，不计入新增。）

## 全库回归断言的实际数字

跑 `uv run python tools/build_ledger.py` 重新生成前，先在内存里对比新旧两份 `ledger`
（旧 = 修复前 git HEAD 的 `data/ledger.jsonl`，新 = 用新 `parse_vms_lines` 现算），逐行核对：

| 断言 | 结果 |
|---|---|
| 行数 | 旧 16749 = 新 16749 |
| id 序列（排序后） | 完全一致 |
| `jp`/`voice`/`file`/`literal`/`chapter` 逐行逐字段对比 | **0 处变化**（16749 行 × 5 字段全部核对） |
| `func` 变化行数 | 12018 |
| `kind` 变化行数 | **0**（与 progress.md 里控制器"预期 kind 零变化"的判断一致） |
| `(file, kind)` 计数分布 | 完全一致，零变化 |
| `ledger_extra.jsonl` | 829 行，内容逐行相等（`OLD_EXTRA == new_extra` 为 `True`） |
| 裸 vN 残留 | 修复前 12042 → 修复后 24（全部 `snr_crd_102`：`v0`×13/`v1`×5/`v2`×6） |

`func` 变化行数 12018 与"裸 vN 残留从 12042 降到 24"完全自洽（12042 − 24 = 12018）：
每一行 `func` 发生变化的记录，都是"从裸 vN 迁到了非裸 vN 的真实归属"，没有任何行是从
非裸 vN 变成别的东西——这是实现正确性的一个强旁证。

实际重新生成落盘后用 `git diff` 复核：

```
$ uv run python tools/build_ledger.py
ledger=16749 (ambient=56)  extra=829

$ git diff --stat data/ledger.jsonl data/ledger_extra.jsonl
 data/ledger.jsonl | 24036 ++++++++++++++++++++++++++--------------------------
 1 file changed, 12018 insertions(+), 12018 deletions(-)
```

`data/ledger_extra.jsonl` 无 diff（字节级不变，`git diff --quiet` 为真）——按 brief
最后一句"若 ledger_extra.jsonl 字节不变则无需 add"，本次提交不包含它。

抽样几行实际迁移（`snr_e1_10_f` 的 `scene_e1f_10` 场景体，此前被误记为 `v0`）：

```
id=3890  file=snr_e1_10_f  'v0' -> 'scene_e1f_10'
...（共 9 行同一模式，e1f_10 场景体全部迁回）
```

### 裸 vN 残留 24 行调查（`snr_crd_102`）

读了完整文件（`lua_scripts/snr_crd_102.lua`，102 行）。结构：

```lua
local v0, v1, v2, card_102_s6s_110_intro, card_102_s6s_110_resolve, v5, v6
v0 = function() ... end          -- 顶层（indent 0），"推理クイズ"题面，13 条 vms
v1 = function() ... end          -- 顶层，误答提示 1，5 条 vms
v2 = function() ... end          -- 顶层，误答提示 2，6 条 vms
card_102_s6s_110_intro = function()
    ...
    v0()                          -- 在这里被调用，而不是被词法嵌套
    while ... do
        ...
        v0(); v2()
        v0(); v1()
        ...
    end
end
card_102_s6s_110_resolve = function() ... end
main = function() ... end
```

`v0`/`v1`/`v2` 是**文件顶层**（indent 0）的兄弟局部闭包，被 `card_102_s6s_110_intro`
以调用（`v0()`/`v1()`/`v2()`）的方式复用，但在**词法/缩进**上并不嵌套在任何命名函数
内部——它们自己就是最外层。嵌套栈处理它们体内的 vms 时，栈只有它们自己一个元素，且
这个元素本身就匹配 `^v\d+$`，命中 brief 归属规则自带的兜底分支："若全部匹配（全是
裸 vN），取最外层名字"——这里最外层就是自己，所以停在 `v0`/`v1`/`v2`。

这不是实现 bug，是"嵌套栈追踪"这个算法（按文本缩进定义归属）相对"调用图追踪"（按
`v0()` 调用点归属）的固有边界，brief 明确把修复范围限定在前者（"维护一个栈…行匹配
FUNC_RE 时 push…"），要覆盖这 24 行需要额外做调用点扫描，是完全不同的算法、超出本次
"嵌套栈追踪"的范围，按 YAGNI 没有做。

处理方式：没有放宽或改写归属规则去人为消灭这 24 行（那样才是"为凑 0 而改规则"）；而是把
`test_real_repo_no_bare_vn_func_residue` 写成"已知例外清单（`snr_crd_102` 的
`v0`/`v1`/`v2`）+ 精确计数 24 钉死"的断言——清单之外出现新的裸 vN，或这 24 行本身发生
变化，测试都会失败并要求复查，不会被静默放过。

**下游影响评估**：当前 `tools/gen_timeline.py::Expander` 只实现了 `story()`
（P1b Task 2 范围），`crds` 相关的 fragment/做卡步骤尚未实现；且 `data/dag.json` 的
`crds` 节点 schema 只有 `answers/req/runs/stub`，不做函数名匹配（不像 `states` 的
`play`/`subcall` 要靠 `(file, func)` 联结）。所以这 24 行残留目前**没有下游消费者**，
不阻塞冒烟或后续任务；未来若要给 crd 谜题的候选/误答分支做时间轴归属，需要专门设计
（大概率是按调用点而非词法嵌套）。

### 确定性

```
$ uv run python tools/build_ledger.py --out-dir <tmpA>
ledger=16749 (ambient=56)  extra=829
$ uv run python tools/build_ledger.py --out-dir <tmpB>
ledger=16749 (ambient=56)  extra=829
$ cmp <tmpA>/ledger.jsonl <tmpB>/ledger.jsonl && echo "ledger.jsonl 字节级相同"
ledger.jsonl 字节级相同
$ cmp <tmpA>/ledger_extra.jsonl <tmpB>/ledger_extra.jsonl && echo "ledger_extra.jsonl 字节级相同"
ledger_extra.jsonl 字节级相同
$ uv run python tools/build_ledger.py --check    # 对比刚落盘的 data/ledger.jsonl
check: OK
```

（既有测试 `test_double_run_is_byte_identical` 同样覆盖这条，44 项里已包含，此处是
按 brief 单独再跑一遍留痕。）

### 下游冒烟（brief 给的原始脚本，逐字跑）

```
$ uv run python - <<'EOF'
import json, sys; sys.path.insert(0, ".")
from tools.pipelib import read_jsonl
from tools.gen_timeline import Expander
dag = json.load(open("data/dag.json", encoding="utf-8"))
ex = Expander(dag, read_jsonl("data/ledger.jsonl"), {})
ex.story("s1s_10", choices={}, until="s1s_20")
units = [u for u in ex.timeline if u["type"] == "unit"]
assert [u["state"] for u in units] == ["s1s_10", "s1s_20"], units
assert all(u["ids"] for u in units), "s1s_10/20 都应有 vms 行"
print("smoke OK:", [(u["state"], len(u["ids"])) for u in units])
EOF
smoke OK: [('s1s_10', 9), ('s1s_20', 75)]
```

修复前这两个状态的 `ids` 都是空列表（Task 2 报告记录的正是这个断裂）；现在
`s1s_10` 联结到 9 条、`s1s_20` 联结到 75 条 vms，`(file, func)` 联结已经修复。

## Files Changed

- `tools/build_ledger.py`——`parse_vms_lines` 改嵌套栈追踪；新增 `END_RE`/`BARE_VN_RE`/
  `_owner_func`。净 +22/-6 行。
- `tests/test_build_ledger.py`——修正 1 个失真断言（原编码 bug 行为）、新增 brief 四组
  用例 + 1 个全库回归测试（已知例外清单写法）。
- `data/ledger.jsonl`——重新生成，12018 行 `func`（及其牵连的 `kind`——实测 0 处）字段
  变化，其余字段与行数逐字节核对不变。
- `data/ledger_extra.jsonl`——重新生成但字节级不变，未纳入本次提交（按 brief 指示）。

## Self-Review

- **Completeness**：brief 的 4 组单测、5 项数据断言（行数/字段/kind/裸vN/确定性）、
  冒烟、提交全部走完。
- **Quality**：`_owner_func` 单一职责、命名直述规则；`m.start(1)` 复用正则匹配位置
  代替重新计算前导空白，避免了 FUNC_RE/END_RE 两套缩进计算口径不一致的风险。未触碰
  `VMS_RE`/`TR_LINE_RE`/`parse_extra`/`classify`/`chapter_of` 等 brief 范围外的解析
  逻辑。
- **Discipline**：24 行残留没有为了让测试变绿而放宽归属算法去"贴合"数据，也没有实现
  调用图追踪去凑零——两者都超出"嵌套栈追踪"这一 hotfix 的范围；改为如实钉死为已知
  例外，是发现真实问题后没有硬改规则的体现。
- **Testing**：4 组 brief 用例中 3 组（case1/2/4 + 更新后的既有断言）先红后绿；case3
  在修复前后都是绿的，报告里解释了原因（对应 brief"必须保持不变"的非回归诉求，不是
  待修 bug）。全量 `uv run pytest -q`：44 passed，输出干净无 warning。

## Concerns

1. **`snr_crd_102` 的 24 行裸 vN 残留**——已按 brief 指示逐行调查、未硬改规则，详情见
   上文"裸 vN 残留 24 行调查"。评估为无下游影响（当前 `Expander` 未实现 crd/fragment
   步骤，`dag.json` 的 `crds` 节点也不做函数名匹配），本次不处理；如果后续任务需要给
   crd 谜题的分支话术做时间轴归属，需要专门设计（按调用点而非词法嵌套）。
2. 既有测试 `test_func_tracking_follows_nearest_function_opener` 的断言编码的正是
   P1a 的 bug 本身，本次连带重命名为 `test_func_tracking_bubbles_past_bare_vn_to_named_opener`
   并改了断言值——这是 brief 范围内必然的改动（否则该测试会在修复后一直失败），不是
   顺手扩权，但仍在此处提示评审注意这一处非纯新增的改动。
