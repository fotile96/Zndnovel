## Task 1: 叠加操作引擎

**Files:**
- Create: `tools/layers.py`
- Test: `tests/test_layers.py`

**Interfaces:**
- Produces:
  - `class OverlayError(SystemExit)`
  - `apply_op(text: str, op: dict) -> str` — 施加单个操作，失败抛 `OverlayError`
  - `apply_overlay(text: str, overlay: dict) -> str` — 按 `overlay["ops"]` 顺序施加
  - `find_all(text: str, needle: str) -> list[int]` — 自左向右非重叠查找，返回起点列表
  - `select_indices(hits: list[int], count: int, occurrence) -> list[int]`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_layers.py`：

```python
"""叠加操作引擎的封闭单元测试。

这些测试不碰真实语料，只验引擎语义：五种操作、count/occurrence 的每种失败
路径、多行逐字匹配与缩进保真。真语料上的命中由 tests/test_layers_corpus.py 守。
"""
import pytest

from tools.layers import OverlayError, apply_op, apply_overlay, find_all, select_indices


def test_find_all_is_non_overlapping():
    assert find_all("aaaa", "aa") == [0, 2]


def test_replace_single_hit():
    out = apply_op("x = key3[i]\n", {"op": "replace", "find": "key3", "with": "keyCur"})
    assert out == "x = keyCur[i]\n"


def test_replace_count_mismatch_is_hard_failure():
    with pytest.raises(OverlayError) as e:
        apply_op("a a a\n", {"op": "replace", "count": 2, "find": "a", "with": "b"})
    assert "命中 3" in str(e.value)


def test_replace_zero_hit_is_hard_failure():
    with pytest.raises(OverlayError) as e:
        apply_op("hello\n", {"op": "replace", "find": "nope", "with": "x"})
    assert "命中 0" in str(e.value)


def test_replace_all_occurrences_by_default():
    out = apply_op("a a a\n", {"op": "replace", "count": 3, "find": "a", "with": "b"})
    assert out == "b b b\n"


def test_occurrence_negative_selects_from_end():
    out = apply_op("a a a\n",
                   {"op": "replace", "count": 3, "occurrence": -1, "find": "a", "with": "Z"})
    assert out == "a a Z\n"


def test_occurrence_out_of_range_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("a a\n", {"op": "replace", "count": 2, "occurrence": 3, "find": "a", "with": "b"})


def test_insert_before_keeps_indentation_verbatim():
    text = "        else\n            l0_1 = 1\n"
    out = apply_op(text, {"op": "insert_before",
                          "anchor": "        else\n",
                          "text": "        elseif cond then\n            body()\n"})
    assert out == ("        elseif cond then\n            body()\n"
                   "        else\n            l0_1 = 1\n")


def test_insert_after_places_text_after_anchor():
    out = apply_op("line1\nline2\n",
                   {"op": "insert_after", "anchor": "line1\n", "text": "mid\n"})
    assert out == "line1\nmid\nline2\n"


def test_delete_span_removes_start_through_end_inclusive():
    text = "keep\nSTART\nmiddle\nEND\ntail\n"
    out = apply_op(text, {"op": "delete_span", "start": "START\n", "end": "END\n"})
    assert out == "keep\ntail\n"


def test_replace_span_substitutes_region():
    text = "keep\nSTART\nmiddle\nEND\ntail\n"
    out = apply_op(text, {"op": "replace_span",
                          "start": "START\n", "end": "END\n", "with": "NEW\n"})
    assert out == "keep\nNEW\ntail\n"


def test_span_end_before_start_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("END\nSTART\n", {"op": "delete_span", "start": "START\n", "end": "END\n"})


def test_span_anchor_must_hit_exactly_once():
    with pytest.raises(OverlayError):
        apply_op("START\nx\nSTART\nEND\n",
                 {"op": "delete_span", "start": "START\n", "end": "END\n"})


def test_unknown_op_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("x\n", {"op": "frobnicate", "find": "x", "with": "y"})


def test_ops_apply_in_order_and_see_previous_results():
    overlay = {"ops": [{"op": "replace", "find": "A", "with": "B"},
                       {"op": "replace", "find": "B", "with": "C"}]}
    assert apply_overlay("A\n", overlay) == "C\n"
```

- [ ] **Step 2: 跑测试确认全红**

Run: `uv run pytest tests/test_layers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.layers'`

- [ ] **Step 3: 写最小实现**

创建 `tools/layers.py`：

```python
#!/usr/bin/env -S uv run python
"""层系统：基座 + 层 + 剖面的加载、校验、施加与取证。

设计见 docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md。

核心约束：叠加层在**译文注入之后**施加（账本按 (file, line) 锚定，注入必须先跑
且行号不变），故锚点只准是代码文本，不准是可译文本，不准是行号。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class OverlayError(SystemExit):
    """叠加层施加失败。继承 SystemExit：正确性问题一律硬失败，不给静默机会。"""


def find_all(text: str, needle: str) -> list[int]:
    """自左向右非重叠查找，返回全部起点。"""
    if not needle:
        raise OverlayError("锚点为空串——叠加层写错了")
    hits, i = [], 0
    while (j := text.find(needle, i)) >= 0:
        hits.append(j)
        i = j + len(needle)
    return hits


def select_indices(hits: list[int], count: int, occurrence) -> list[int]:
    """按 count 断言总命中数，按 occurrence 选出要作用的那几处。"""
    if len(hits) != count:
        raise OverlayError(
            f"锚点期望命中 {count} 处，实际命中 {len(hits)} 处——"
            f"基座变了或叠加层写错了。用 `uv run python tools/layers.py diff <层名>` 核对")
    if occurrence == "all":
        return hits
    if not isinstance(occurrence, int) or occurrence == 0:
        raise OverlayError(f"occurrence 必须是 \"all\" 或非零整数，收到 {occurrence!r}")
    idx = occurrence - 1 if occurrence > 0 else count + occurrence
    if not 0 <= idx < count:
        raise OverlayError(f"occurrence={occurrence} 越界（命中 {count} 处）")
    return [hits[idx]]


def _need(op: dict, *keys: str) -> tuple:
    missing = [k for k in keys if k not in op]
    if missing:
        raise OverlayError(f"操作 {op.get('op')!r} 缺字段 {missing}")
    return tuple(op[k] for k in keys)


def _apply_point_op(text: str, op: dict, anchor: str, render) -> str:
    """replace / insert_before / insert_after 共用：定位 → 选点 → 自后向前改写。"""
    picks = select_indices(find_all(text, anchor), op.get("count", 1),
                           op.get("occurrence", "all"))
    for start in reversed(picks):        # 自后向前，前面的下标不受影响
        end = start + len(anchor)
        text = text[:start] + render(text[start:end]) + text[end:]
    return text


def _apply_span_op(text: str, op: dict, replacement: str) -> str:
    start_s, end_s = _need(op, "start", "end")
    if "count" in op or "occurrence" in op:
        raise OverlayError("span 类操作不接受 count / occurrence——两个锚各须恰好命中一次")
    starts, ends = find_all(text, start_s), find_all(text, end_s)
    if len(starts) != 1:
        raise OverlayError(f"start 锚点须恰好命中 1 次，实际 {len(starts)} 次")
    if len(ends) != 1:
        raise OverlayError(f"end 锚点须恰好命中 1 次，实际 {len(ends)} 次")
    if ends[0] < starts[0]:
        raise OverlayError("end 锚点在 start 之前——区间无效")
    return text[:starts[0]] + replacement + text[ends[0] + len(end_s):]


def apply_op(text: str, op: dict) -> str:
    """施加单个操作。五种：replace / insert_before / insert_after / delete_span / replace_span。"""
    kind = op.get("op")
    if kind == "replace":
        find, with_ = _need(op, "find", "with")
        return _apply_point_op(text, op, find, lambda _: with_)
    if kind == "insert_before":
        anchor, ins = _need(op, "anchor", "text")
        return _apply_point_op(text, op, anchor, lambda hit: ins + hit)
    if kind == "insert_after":
        anchor, ins = _need(op, "anchor", "text")
        return _apply_point_op(text, op, anchor, lambda hit: hit + ins)
    if kind == "delete_span":
        return _apply_span_op(text, op, "")
    if kind == "replace_span":
        (with_,) = _need(op, "with")
        return _apply_span_op(text, op, with_)
    raise OverlayError(f"未知操作 {kind!r}（可选 replace / insert_before / insert_after / "
                       f"delete_span / replace_span）")


def apply_overlay(text: str, overlay: dict) -> str:
    """按声明顺序依次施加全部操作；每个操作看到的都是前序操作之后的文本。"""
    for i, op in enumerate(overlay.get("ops", []), 1):
        try:
            text = apply_op(text, op)
        except OverlayError as exc:
            name = overlay.get("_name", "?")
            raise OverlayError(f"叠加层 {name} 第 {i} 个操作失败：{exc}") from None
    return text
```

- [ ] **Step 4: 跑测试确认全绿**

Run: `uv run pytest tests/test_layers.py -q`
Expected: PASS（16 passed）

- [ ] **Step 5: 提交**

```bash
git add tools/layers.py tests/test_layers.py
git commit -m "feat: 叠加操作引擎——五种锚定文本操作 + count/occurrence 硬断言

层系统的第一块：apply_op 支持 replace / insert_before / insert_after /
delete_span / replace_span，count 断言全文命中总数、occurrence 选作用点（支持负数
自末尾计）。任一不符即 OverlayError（继承 SystemExit）——基座变了就当场炸，
不给静默偏移的机会。逐字匹配、零空白归一化，多行锚点因此按行对齐。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

