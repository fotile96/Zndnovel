# Task 1 Report: 叠加操作引擎

## Implementation Summary

Implemented the text overlay operation engine (`tools/layers.py`) with supporting test suite (`tests/test_layers.py`), providing the first core component of the disc layers pipeline.

**Delivered interfaces:**
- `class OverlayError(SystemExit)` — hard-failure exception for overlay failures
- `find_all(text, needle) -> list[int]` — non-overlapping left-to-right search
- `select_indices(hits, count, occurrence) -> list[int]` — count assertion + occurrence selection
- `apply_op(text, op) -> str` — single operation application
- `apply_overlay(text, overlay) -> str` — multi-operation orchestration

**Five operation types:**
1. `replace` — find/replace with optional count and occurrence controls
2. `insert_before` — anchor-based insertion before match
3. `insert_after` — anchor-based insertion after match
4. `delete_span` — remove region between start/end anchors
5. `replace_span` — substitute region between start/end anchors

## Test Results

### RED (Before Implementation)
```
Command: uv run pytest tests/test_layers.py -q

Output:
E   ModuleNotFoundError: No module named 'tools.layers'
======================== short test summary info ===========================
ERROR tests/test_layers.py
1 error in 0.05s

Expected: Module does not yet exist, import fails. ✓
```

### GREEN (After Implementation)
```
Command: uv run pytest tests/test_layers.py -q

Output:
...............                                                          [100%]
15 passed in 0.01s

Expected: All 15 tests pass, 0 warnings. ✓
```

## Test Coverage

15 unit tests covering all behaviors:

**Core functionality:**
- `test_find_all_is_non_overlapping` — validates non-overlapping search (0, 2 for "aa"/"aaaa")
- `test_replace_single_hit` — single substitution
- `test_replace_all_occurrences_by_default` — default "all" occurrence mode
- `test_insert_before_keeps_indentation_verbatim` — whitespace preservation
- `test_insert_after_places_text_after_anchor` — post-insertion placement
- `test_delete_span_removes_start_through_end_inclusive` — span removal
- `test_replace_span_substitutes_region` — span substitution

**Occurrence selection:**
- `test_occurrence_negative_selects_from_end` — negative indexing (-1 = last)
- `test_occurrence_out_of_range_is_hard_failure` — OOB detection

**Count assertion:**
- `test_replace_count_mismatch_is_hard_failure` — count != hits raises OverlayError
- `test_replace_zero_hit_is_hard_failure` — no matches raises OverlayError

**Span validation:**
- `test_span_end_before_start_is_hard_failure` — end < start rejects
- `test_span_anchor_must_hit_exactly_once` — duplicates rejected

**Error handling:**
- `test_unknown_op_is_hard_failure` — unknown operation type rejected

**Chaining:**
- `test_ops_apply_in_order_and_see_previous_results` — operations see prior mutations

## Files Changed

```
tests/test_layers.py        created, 95 lines
  - 15 pytest test cases
  - Exact copy of test code from brief
  
tools/layers.py             created, 110 lines (initial)
  - OverlayError class
  - 4 public functions (find_all, select_indices, apply_op, apply_overlay)
  - 3 private helpers (_need, _apply_point_op, _apply_span_op)
  - Exact copy of implementation code from brief
```

## TDD Evidence

### Step 1: Test File Created
✓ `tests/test_layers.py` transcribed verbatim from brief

### Step 2: RED Test Run
✓ Tests fail with `ModuleNotFoundError: No module named 'tools.layers'` — expected

### Step 3: Implementation Created
✓ `tools/layers.py` transcribed verbatim from brief

### Step 4: GREEN Test Run
✓ `15 passed in 0.01s` — all tests pass, no warnings

### Step 5: Commit Created
✓ Commit `8acd288` with exact message from brief

## Self-Review Findings

**Completeness:** ✓
- All 5 function/class signatures present and match brief
- All test cases present (15 tests)
- Implementation handles all 5 operation types
- Error paths all covered

**Correctness:** ✓
- Non-overlapping search uses `i = j + len(needle)` advance — correct
- Count assertion uses exact equality check `len(hits) != count` — correct
- Occurrence selection: positive `occurrence - 1`, negative `count + occurrence` — correct
- Point operations apply in reverse order to preserve indices — correct
- Span operations validate both anchors before modification — correct
- Error messages include diagnostic hints (`基座变了或叠加层写错了`) — helpful

**Code Quality:** ✓
- Chinese comments/docstrings preserved verbatim from brief
- Type hints present (Python 3.12+ compatible)
- `from __future__ import annotations` for forward compatibility
- sys.path insertion at module level (standard tools/ pattern)
- `OverlayError` extends `SystemExit` (hard failure intent)
- Private helpers prefixed with `_` (convention)

**Tests:** ✓
- Pristine pytest output (no stray warnings)
- 100% pass rate (15/15)
- Test names are descriptive and match their assertions
- Edge cases covered: empty hits, OOB, negative indexing, duplicates, ordering

**Scope (YAGNI):** ✓
- No extra features beyond brief spec
- No extra functions, classes, or modes
- No CLI, logging, or persistence (not requested)

**Commit:** ✓
- Exact message from brief
- Only relevant files added (`tools/layers.py`, `tests/test_layers.py`)
- No unrelated changes included

## Fix Report

**Issue Found by Reviewer:** `select_indices` did not validate `count >= 1`. With `count = 0` and a genuinely missing anchor, `len(hits) == 0 == count` passes the check, then `_apply_point_op` loops zero times and returns text unchanged — a silent no-op that violates the hard-failure contract.

**Example of the bug:**
```python
apply_op("hello world\n", {"op": "replace", "count": 0, "find": "nonexistent", "with": "X"})
# Returned "hello world\n" unchanged instead of raising OverlayError
```

**Fix Applied:**
1. Added validation guard in `select_indices` before count assertion:
   ```python
   if count < 1:
       raise OverlayError(f"count 必须 ≥1，收到 {count}——零命中的层等于没写")
   ```

2. Added covering test in `tests/test_layers.py`:
   ```python
   def test_count_zero_is_hard_failure_not_silent_noop():
       with pytest.raises(OverlayError) as e:
           apply_op("hello\n", {"op": "replace", "count": 0, "find": "nope", "with": "x"})
       assert "≥1" in str(e.value)
   ```

**Test Run After Fix:**
```
Command: uv run pytest tests/test_layers.py -q

Output:
................                                                         [100%]
16 passed in 0.01s

Expected: 16 tests (original 15 + 1 covering count=0), 0 warnings. ✓
```

**Commit Created:**
- `0660e54 fix: select_indices 必须挡住 count<1 防静默 no-op`

## Concerns

None. Fix is complete, all 16 tests pass, coverage is comprehensive.

## Next Steps

This task forms the foundation for Task 2 (layer manifest loading and integrity checking) and Task 3 (character set extraction). The engine is ready for integration with the full disc build pipeline.

---

**Status:** DONE (with fix)
**Test Summary:** 16 passed in 0.01s (100% pass rate, 0 warnings)
**Commits:** 
- `8acd288 feat: 叠加操作引擎——五种锚定文本操作 + count/occurrence 硬断言`
- `0660e54 fix: select_indices 必须挡住 count<1 防静默 no-op`
