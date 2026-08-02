### Task 5: 测试补漏束（deferred minors 清账）

**Files:**
- Test: `tests/test_saturation.py`、`tests/test_canary.py`、`tests/test_gen_plan.py`（各追加）
- Modify: `tools/canary.py`（仅头注措辞）

**Interfaces:** 全部为对既有行为**补锁**，零行为变更。

- [ ] **Step 1: 三个补锁测试（预期直接绿——它们锁的是现状）**

`tests/test_saturation.py` 追加（锁 ledger_extra 的 `key` 字段兼容，点火台账 Task 2 deferred）：

```python
def test_extra_rows_use_key_field_not_id():
    rows = [{"key": "snr_crd_0:35", "jp": "寝癖の話", "kind": "card_msg", "file": "snr_crd_0"}]
    r = saturation("寝癖", rows, done_ids={"snr_crd_0:35"})
    assert r["total"] == 1 and r["covered"] == 1
```

（若该断言红：说明实现读的不是 `key`——那是回归，按 Task 2 点火评审结论修实现使其兼容 `id`/`key` 双形态。）

`tests/test_canary.py` 追加（CLI 子进程级 exit code，点火台账 Task 3 deferred）：

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

`tests/test_gen_plan.py` 追加（空 sel + segment 组合，点火台账 Task 4 deferred）：

```python
def test_render_empty_sel_with_segment_has_head_and_tail():
    md = render([], label="x", lane="main", segment="seg1-s2")
    assert "段开场自检" in md and "段末流程" in md
```

- [ ] **Step 2: 头注措辞修正**

`tools/canary.py` 文件头 docstring 中「（`dumps` 排序确定性输出）」类表述改为「（`dumps` 输出确定性来自固定的字典插入顺序，非 sort_keys）」——与 `pipelib.dumps` 实际实现一致（点火台账 Task 3 deferred 笔误）。

- [ ] **Step 3: 全量测试 + commit**

Run: `uv run pytest -q` → 251 passed。

```bash
git add tests/test_saturation.py tests/test_canary.py tests/test_gen_plan.py tools/canary.py
git commit -m "chore: 点火遗留测试补锁三条 + canary 头注措辞订正"
```

---

