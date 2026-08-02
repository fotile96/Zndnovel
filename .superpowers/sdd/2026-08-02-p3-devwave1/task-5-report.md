# Task 5: 测试补漏束（deferred minors 清账） - 完成报告

## 执行摘要

**状态**: DONE  
**Commit**: a22a9a5  
**测试结果**: 258 passed（↑ 255 → 258）  
**三条测试**: 全部一次通过  
**顾虑**: 无

## 详细执行过程

### Step 1: 三条补锁测试追加

#### 1.1 test_saturation.py
**文件**: `tests/test_saturation.py`  
**修改**: 在文件尾添加新测试 `test_extra_rows_use_key_field_not_id()`

```python
def test_extra_rows_use_key_field_not_id():
    rows = [{"key": "snr_crd_0:35", "jp": "寝癖の話", "kind": "card_msg", "file": "snr_crd_0"}]
    r = saturation("寝癖", rows, done_ids={"snr_crd_0:35"})
    assert r["total"] == 1 and r["covered"] == 1
```

**验证**: ✓ PASSED
- 锁定 saturation() 对 ledger_extra 的 `key` 字段兼容性
- 用例：传入带 `key` 而非 `id` 的行，验证计算结果正确

#### 1.2 test_canary.py
**文件**: `tests/test_canary.py`  
**修改**: 在文件尾添加新测试 `test_cli_diff_exit_codes()`

```python
def test_cli_diff_exit_codes(tmp_path):
    import json, subprocess, sys
    a = tmp_path / "a.json"; b = tmp_path / "b.json"
    a.write_text(json.dumps({"1": {"check": {"hard": [], "warn": []}, "collapse": []}}),
                 encoding="utf-8")
    b.write_text(json.dumps({"1": {"check": {"hard": [], "warn": [{"id": 9}]}, "collapse": []}}),
                 encoding="utf-8")
    same = subprocess.run([sys.executable, "tools/canary.py", "--diff", str(a), str(a)])
    diff = subprocess.run([sys.executable, "tools/canary.py", "--diff", str(a), str(b)])
    assert same.returncode == 0 and diff.returncode == 1
```

**验证**: ✓ PASSED
- 锁定 CLI --diff 子进程的 exit code：一致时 0，有差异时 1
- 用例：同一文件比对返回 0；有差异的文件比对返回 1

#### 1.3 test_gen_plan.py
**文件**: `tests/test_gen_plan.py`  
**修改**: 在文件末尾添加新测试 `test_render_empty_sel_with_segment_has_head_and_tail()`

```python
def test_render_empty_sel_with_segment_has_head_and_tail():
    md = render([], label="x", lane="main", segment="seg1-s2")
    assert "段开场自检" in md and "段末流程" in md
```

**验证**: ✓ PASSED
- 锁定 render() 在 segment 模式下即使传空批次列表也生成头尾自检块
- 用例：空 sel + segment 组合必须输出段开场自检和段末流程

### Step 2: 头注措辞修正

**文件**: `tools/canary.py`  
**修改**: 更新文件头 docstring 措辞

**原文**:
```python
"""陷阱批回验：对已入线批次用当前工具树重算 check_batch + detect_collapse 判定，
输出规范化 JSON。工具升级流程（P3 spec §3）：旧 tag worktree 与新 main 各跑一次
--out（同一车道数据），--diff 一致才允许滚动生产 tag。draft 取 forward.jsonl 中
每 id 的末次出现（＝入线原稿；patches 不参与，判定对齐的是入线时刻）。"""
```

**修改后**:
```python
"""陷阱批回验：对已入线批次用当前工具树重算 check_batch + detect_collapse 判定，
输出规范化 JSON（`dumps` 输出确定性来自固定的字典插入顺序，非 sort_keys）。工具升级流程
（P3 spec §3）：旧 tag worktree 与新 main 各跑一次 --out（同一车道数据），--diff 一致
才允许滚动生产 tag。draft 取 forward.jsonl 中每 id 的末次出现（＝入线原稿；patches 不
参与，判定对齐的是入线时刻）。"""
```

**说明**: 添加关于 `dumps` 确定性的精准说明，与 `pipelib.dumps` 实现一致（无 sort_keys 参数，依赖字典插入顺序）。

### Step 3: 全量测试验证

**命令**: `uv run pytest -q`

**输出**:
```
........................................................................ [ 27%]
........................................................................ [ 55%]
........................................................................ [ 83%]
..........................................                               [100%]
258 passed in 1.54s
```

**验证**: ✓ 258 passed（基线 255 + 新增 3 = 258）

### Step 4: Git 提交

**命令**:
```bash
git add tests/test_saturation.py tests/test_canary.py tests/test_gen_plan.py tools/canary.py
git commit -m "chore: 点火遗留测试补锁三条 + canary 头注措辞订正"
```

**结果**:
```
[main a22a9a5] chore: 点火遗留测试补锁三条 + canary 头注措辞订正
 4 files changed, 27 insertions(+), 3 deletions(-)
```

## 执行事实表

| 项目 | 状态 | 说明 |
|------|------|------|
| test_extra_rows_use_key_field_not_id() | ✓ PASSED | 一次通过，锁 saturation() 的 key 字段兼容 |
| test_cli_diff_exit_codes() | ✓ PASSED | 一次通过，锁 CLI exit code 行为 |
| test_render_empty_sel_with_segment_has_head_and_tail() | ✓ PASSED | 一次通过，锁段模式空批的头尾生成 |
| canary.py 头注修正 | ✓ 完成 | dumps 确定性说明已补充 |
| 全量测试 | 258 passed | 完全符合预期（255 + 3） |

## 无偏差、无顾虑

三条测试符合预期直接绿的特性，canary.py 措辞订正顺利完成，全量测试无失败。
