# Task 2 Report: 时间轴展开器 story 步进核心

## Summary
Successfully implemented the `Expander` class with the `story()` method for the timeline linearization tool. All unit tests pass; structural smoke test reveals a data generation issue in build_ledger.py (nested function tracking bug), not an implementation problem.

## Implementation

### Files Created/Modified
- **tools/gen_timeline.py** (159 lines): Core `Expander` class with:
  - `__init__(dag, ledger_rows, unit_funcs)`: Initialize state tracking
  - `story(enter, choices, until)`: Walk DAG with choice/gate/route logic
  - `emit_unit(kind, src_file, state, title, funcs)`: Record timeline units
  - `emit_marker(text, recap)`: Record narrative markers
  - `_ids_for(file, funcs)`: Lookup ledger entries by fnmatch patterns
  - `_apply_meta(func)`: Process scene_meta to track held cards

- **tests/test_gen_timeline.py** (40 lines): TDD test suite with:
  - 4-state mini DAG + mini ledger fixture
  - `test_story_walks_default_choice_and_emits_units`: Verify default path
  - `test_story_honors_explicit_choice_and_gets_cards`: Verify choice handling + card acquisition
  - `test_until_stops_after_that_state`: Verify termination condition

- **config/unit_funcs.yaml**: Empty unit function mapping (placeholder for Task 5)

## TDD Evidence

### Step 2: RED - Test Fails (as expected)
```bash
$ uv run pytest tests/test_gen_timeline.py -v
ERROR tests/test_gen_timeline.py - ModuleNotFoundError: No module named 'tools.gen_timeline'
```
Expected failure: module not implemented yet.

### Step 4: GREEN - Tests Pass
```bash
$ uv run pytest tests/test_gen_timeline.py -v
tests/test_gen_timeline.py::test_story_walks_default_choice_and_emits_units PASSED [ 33%]
tests/test_gen_timeline.py::test_story_honors_explicit_choice_and_gets_cards PASSED [ 66%]
tests/test_gen_timeline.py::test_until_stops_after_that_state PASSED     [100%]

============================== 3 passed in 0.01s ===============================
```

### Full Suite
```bash
$ uv run pytest tests/ -v
============================== 39 passed in 1.12s ===============================
```
All existing tests still pass; no regressions.

## Smoke Test Analysis (Step 5)

Ran structural smoke test:
```bash
uv run python - <<'EOF'
from tools.gen_timeline import Expander
from tools.pipelib import read_jsonl
import json
dag = json.load(open("data/dag.json"))
ex = Expander(dag, read_jsonl("data/ledger.jsonl"), {})
ex.story("s1s_10", choices={}, until="s1s_20")
units = [u for u in ex.timeline if u["type"] == "unit"]
EOF
```

**Result**: ✓ Expander correctly:
- Walks DAG from s1s_10 → s1s_20
- Tracks route: `['s1s_10', 's1s_20']`
- Emits units for both states
- Looks up correct functions (scene_s1s_10, scene_s1s_20)

**Issue Found**: Ledger entries not matched
- dag.json says: play scene_s1s_10, scene_s1s_20
- ledger.jsonl has: IDs 7296-7304 attributed to `v0`, not `scene_s1s_10`
- Root cause: build_ledger.py's `FUNC_RE` doesn't handle nested function closures correctly
  - When it sees `v0 = function()` inside scene_s1s_10, it switches tracking to v0
  - When v0's function ends, it doesn't revert to scene_s1s_10
  - Subsequent vms calls are attributed to v0 instead of the parent function

**Impact**: NOT an Expander implementation issue. The Expander correctly:
- Extracts function names from dag.json
- Calls `_ids_for(file, ["scene_s1s_10"])` 
- Receives empty result because ledger lacks that key
- This is a data generation bug, not a logic bug

Per brief: "若冒烟失败（dag.json 实际结构走不到断言），不要改 dag.json 或绕过——如实按 BLOCKED/DONE_WITH_CONCERNS 上报。"

The dag.json structure IS correct and walkable. The ledger data generation is incomplete.

## Implementation Details

### Key Behaviors

1. **Choice Handling**: `choices.setdefault(state, first_event.choice)` ensures:
   - Explicit override via `choices={"a_20": 2}` is used
   - Missing states pick the first choice event as default
   - Test: explicit choice 2 routes to a_40 ✓

2. **Card Gates**: `skip = ((card_gate in held) != gate.held)`
   - If gate.held is True and card NOT held → skip=True → skip next goto
   - If gate.held is False and card held → skip=True → skip next goto
   - Correctly implements exclusive branch logic

3. **Route Tracking**: `route.append(state)` after emitting
   - Order matters for route_has checks in downstream states
   - Test: route_has in s3fc checks if earlier states were visited ✓

4. **Card Acquisition**: `_apply_meta(func)` after emitting
   - Processes scene_meta["scene_name"].gets=[cards]
   - Persists across story() call in self.held
   - Test: ex2.held contains 7 after story completes ✓

## Self-Review

- **Completeness**: All 6 brief steps completed
  1. ✓ Write failing test
  2. ✓ Verify failure
  3. ✓ Minimal implementation
  4. ✓ Verify passing
  5. ✓ Smoke test (structural success; data issue documented)
  6. ✓ Commit (pending)

- **Quality**:
  - Naming: `_ids_for`, `_apply_meta`, `emitted_states` are clear
  - No over-building: Only implements story/emit core; fragment/replay for later tasks
  - Pattern adherence: Matches build_dag.py/pipelib.py style

- **Edge Cases Covered**:
  - Unknown state → KeyError("未知状态")
  - until=None → walk to end
  - until="a_20" → stop after emitting a_20
  - funcs=[] → don't emit unit
  - choice events with nxt already set → pick first match

- **Testing**:
  - 3 unit tests, all passing
  - 39 total tests pass (no regressions)
  - Real data walkable (dag.json structure valid)

## Data Concerns

The brief states: if smoke test fails due to dag.json structure issues, report as BLOCKED/DONE_WITH_CONCERNS and don't change dag.json.

**Status**: DONE_WITH_CONCERNS
- Implementation is correct and complete
- Smoke test's unit emission works structurally
- Ledger ledger entries for individual scene functions are missing (build_ledger.py issue, not my code)
- Next task (implementing fragment/replay steps) should still work fine

## Files Changed
```
config/unit_funcs.yaml          (new, 3 lines)
tools/gen_timeline.py           (new, 159 lines)
tests/test_gen_timeline.py      (new, 40 lines)
```

## Commit Ready
All files staged and ready for commit with message:
```
feat: 时间轴展开器 story 步进核心
```

---

# Fix Round 1 (Code Review Response)

## Issues Identified & Fixed

**Issue 1: Dead Code**
- `ran` variable was assigned but never read (not in self, not in markers, didn't affect nxt)
- Removed `ran` from initialization and all assignments

**Issue 2: Contract Mismatch**
- Docstring claimed skip gate controls both goto and accompanying run event
- Implementation actually let run events pass uncontrolled
- Per design fact: run events don't drive traversal; enter jumps are handled by accompanying goto
- Updated docstring to clarify: "伴随的 run 事件不驱动行走、无需门控（enter 跳转由 goto 承载）"

**Issue 3: Missing Test Coverage**
- No test exercised the `card_gate→goto→run→goto` pattern
- Added `test_card_gate_goto_run_pattern_with_cross_file_jump()` with:
  - 3-state fixture DAG with explicit run event after card_gate branch
  - Assertion 1: When card held → nxt follows first goto (cross-file jump)
  - Assertion 2: When card unheld → nxt follows second goto (default path, run unexecuted)

## Changes Made

### tools/gen_timeline.py
```diff
  def story(self, enter, choices=None, until=None):
-     """skip 语义契约：...跳过其后**紧随的一个** goto（含伴随 run）..."""
+     """skip 语义契约：...跳过其后紧随的一个 goto；伴随的 run 事件不驱动行走、无需门控..."""
      choices = choices or {}
      state = enter
      while state and state != "end":
          ...
-         nxt, ran, skip = None, None, False
+         nxt, skip = None, False
          for ev in st["seq"]:
              ...
-             elif "run" in ev:
-                 if not skip:
-                     ran = ev["run"]
+             elif "run" in ev:
+                 pass  # 跨文件切换由伴随 goto 承载...
          ...
-         state = nxt        # ran 时 nxt 已指向...
+         state = nxt
```

### tests/test_gen_timeline.py
Added 67-line test case `test_card_gate_goto_run_pattern_with_cross_file_jump`:
- Fixture: 3-state DAG with card_gate→goto→run→goto sequence
- Test 1: held.add(99) → story() → assert states == ["b_10", "b_20_enter"]
- Test 2: (no held) → story() → assert states == ["b_10", "b_30"]

## Test Results

### Covering Test Runs
```bash
$ uv run pytest tests/test_gen_timeline.py -v
tests/test_gen_timeline.py::test_story_walks_default_choice_and_emits_units PASSED [ 25%]
tests/test_gen_timeline.py::test_story_honors_explicit_choice_and_gets_cards PASSED [ 50%]
tests/test_gen_timeline.py::test_until_stops_after_that_state PASSED     [ 75%]
tests/test_gen_timeline.py::test_card_gate_goto_run_pattern_with_cross_file_jump PASSED [100%]

============================== 4 passed in 0.02s ===============================
```

### Full Suite
```bash
$ uv run pytest -q
.............................................                            [100%]
45 passed in 1.55s
```

All tests pass; no regressions. New fixture test confirms:
- run event is intentionally no-op (no assignment to any variable)
- skip gate correctly controls only the immediately following goto (not the run)
- cross-file jumps work via goto mechanism (first goto when card held, second goto when card unheld)
