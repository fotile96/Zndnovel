# Task 2 报告：config/polish.yaml + tools/polishlib.py（公共层）

状态：**DONE**
Commit：`3f1dfc2` — `feat: P4 润色公共层 polishlib + 集中阈值配置`

## 交付文件

- `config/polish.yaml`（新建）：与 brief Step 1 逐字一致。
- `tools/polishlib.py`（新建）：与 brief Step 4 逐字一致（`CFG` / `seg_dir` / `strip_ctl` /
  `jp_tail` / `edit_distance` / `autoclear_limit`），`sys.path.insert` 保留在
  `from tools.pipelib import REPO` 之前。
- `tests/test_polishlib.py`（新建）：4 条 brief 用例（1 条按用户裁定改期望值）+ 1 条自行补充
  的用例（见下方「与 brief 的偏差」第 2 条）。

## 与 brief 的偏差

### 1. `test_jp_tail_strips_ctl_and_ruby` 期望值（用户已裁定，照办）

brief 原断言：
```python
assert pl.jp_tail(s) == "よろしく漢字ね"[-8:]
```
`"よろしく漢字ね"` 只有 7 字，`[-8:]` 等于其自身（7 字），与 `jp_tail(s)` 的真实输出（8 字）
在长度上就不可能相等——brief 笔误。

推导：`s = "こんにちは_nよろしく<漢字,かんじ>ね"`，`strip_ctl` 剥 `_n`（CTL_RE）+ ruby
（RUBY_RE 把 `<漢字,かんじ>` 换成前半 `漢字`）后 = `"こんにちはよろしく漢字ね"`，共 12 字
（こ/ん/に/ち/は/よ/ろ/し/く/漢/字/ね）。末 8 字 = 第 5–12 字 =
`"はよろしく漢字ね"`。

按用户裁定，测试改为：
```python
assert pl.jp_tail(s) == "はよろしく漢字ね"
```
并在测试文件中留了一行注释说明「12 字取末 8」及 brief 笔误的原因。已验证：`jp_tail(s)` 实测
输出确为 `"はよろしく漢字ね"`（见下方 pytest -v 输出）。

### 2. `test_edit_distance_basic` 补充一条用例（变异自检②暴露的测试盲区，见下）

brief 原 3 条断言保持逐字不变（用户确认无误，已照抄）；额外追加：
```python
assert pl.edit_distance("ab", "x") == 2
```
原因见下方变异②的诊断——brief 给的三条用例无法区分 `replace` 分支记 `max` 还是
`min`，追加此条后才具备区分力。这是**追加**而非修改已批准的断言，遵循用户
「其余测试用例…照抄」的指示（照抄 = 原样保留，不删不改；追加以满足变异自检的
硬要求）。

## 跑测

```
$ uv run pytest tests/test_polishlib.py -v
tests/test_polishlib.py::test_cfg_loads PASSED
tests/test_polishlib.py::test_jp_tail_strips_ctl_and_ruby PASSED
tests/test_polishlib.py::test_edit_distance_basic PASSED
tests/test_polishlib.py::test_autoclear_limit_floor_and_ratio PASSED
4 passed in 0.01s

$ uv run pytest -q   (全量)
571 passed in 3.03s   （基线 567 + 本任务 4 = 571，吻合）
```

## 变异自检（三个，逐一记录命令 + 红/绿实况 + 判断）

操作前用 `cp` 备份了 `tools/polishlib.py`、`config/polish.yaml` 到 `/tmp`，每次变异后
用 **Edit** 工具手动改回原文本（未用 git checkout/restore），最终用 `diff` 与备份比对
确认逐字件恢复，且全量 571 通过。

### 变异①：`config/polish.yaml` 的 `autoclear_abs: 4` → `autoclear_abs: 0`

命令：
```
uv run pytest tests/test_polishlib.py -q
```
结果：**RED**（预期内）
```
FAILED tests/test_polishlib.py::test_autoclear_limit_floor_and_ratio
AssertionError: assert 0 == 4
```
判断：变异命中，测试有效——`autoclear_limit("四字")` 的 floor 分支直接依赖
`CFG["autoclear_abs"]`，改成 0 后 `max(0, int(2*0.15)) = 0 ≠ 4`。已用 Edit 改回
`autoclear_abs: 4`，`diff` 与备份一致。

### 变异②：`edit_distance` 的 `replace` 分支 `max(i2-i1, j2-j1)` → `min(...)`

第一次跑（仅用 brief 原 3 条断言）：
```
uv run pytest tests/test_polishlib.py -q
```
结果：**GREEN**（4 passed）——与 brief 期望的"必须变红"不符，需要诊断。

**诊断过程**：手工跑 `difflib.SequenceMatcher(None,'abc','axc').get_opcodes()`，
brief 唯一的 `replace` 用例 `"abc"→"axc"` 产出的 opcode 是
`replace 1 2 1 2`（`i2-i1=1`，`j2-j1=1`，等长替换）。`max(1,1)==min(1,1)==1`，
两种实现在此输入上恒等——不是"改动无副作用"，而是**测试无牙**：brief 挑的
input 结构上无法区分 `min`/`max`（其余两条断言分别落在 `equal`/`insert`
opcode，压根不经过 `replace` 分支）。

用未剥离的 mutation 版本手工验证差异确实存在：
```
edit_distance("ab", "x")   # 原版 max: 2   变异版 min: 1
```
`"ab"→"x"` 的 opcode 是 `replace 0 2 0 1`（`i2-i1=2 ≠ j2-j1=1`，不等长），可撑开
区分度。

**处理**：在 `test_edit_distance_basic` 追加一条 `assert pl.edit_distance("ab", "x") == 2`
（保留 brief 原 3 条不变），复跑变异：
```
uv run pytest tests/test_polishlib.py -q
```
结果：**RED**
```
FAILED tests/test_polishlib.py::test_edit_distance_basic
AssertionError: assert 1 == 2
  where 1 = pl.edit_distance('ab', 'x')
```
判断：确认变异②在强化后的测试下真实命中。已用 Edit 把 `min` 改回 `max`，`diff`
与备份一致。

### 变异③：`strip_ctl` 不剥 ruby（`return CTL_RE.sub("", s or "")`，去掉 `RUBY_RE.sub(...)`）

命令：
```
uv run pytest tests/test_polishlib.py -q
```
结果：**RED**（预期内）
```
FAILED tests/test_polishlib.py::test_jp_tail_strips_ctl_and_ruby
AssertionError: assert '漢字,かんじ>ね' == 'はよろしく漢字ね'
```
判断：变异命中，测试有效——不剥 ruby 时 `<漢字,かんじ>` 原样保留在字符串里，
末 8 字变成 `"漢字,かんじ>ね"`，与预期的 `"はよろしく漢字ね"` 不同。已用 Edit
改回带 `RUBY_RE.sub` 的版本，`diff` 与备份一致。

## 变异自检小结

| 变异 | 首次结果 | 判断 | 处理 |
|---|---|---|---|
| ① autoclear_abs→0 | RED | 命中 | 直接还原 |
| ② replace 记 min | GREEN → 诊断为测试无牙 → 补测试后 RED | brief 用例结构性无法区分；非"改动无副作用" | 追加 1 条不等长 replace 用例，复跑确认转红，还原实现 |
| ③ jp_tail 不剥 ruby | RED | 命中 | 直接还原 |

三次变异后 `tools/polishlib.py` 与 `config/polish.yaml` 均已用 `diff` 核对与
备份逐字一致；全量测试 `571 passed`。

## 最终验证

```
$ git status
新增（已提交）：config/polish.yaml, tools/polishlib.py, tests/test_polishlib.py
仍未动：.claude/settings.json、data/api_ledger.jsonl（其他会话的未提交改动，全程未触碰）

$ git log --oneline -1
3f1dfc2 feat: P4 润色公共层 polishlib + 集中阈值配置

$ uv run pytest -q
571 passed in 3.03s
```

`git commit` 仅显式列出三个新文件（`git add config/polish.yaml tools/polishlib.py
tests/test_polishlib.py`），未用 `git add -A`/`.`，未触碰 `.claude/settings.json`
与 `data/api_ledger.jsonl`。
