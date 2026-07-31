### Task 6: gen_batches 三车道

**Files:**
- Create: `tools/gen_batches.py`
- Test: `tests/test_gen_batches.py`

**Interfaces:**
- Produces: `gen_batches.plan(timeline, ledger_rows, extra_rows, budget_chars=9000) -> list[dict]`（batches 行 schema 见接口总表；lane 顺序：main 全部→每章 extra→ambient）；CLI 写 `data/batches.jsonl` 并打印统计。切批规则：预算超限（cut_reason=budget）、遇 marker（cut_reason=branch）、unit 换章（cut_reason=chapter）。ambient 车道按 `(file,func)` 分组贪心装批；extra 车道读 `data/ledger_extra.jsonl` 按 file 章别成批。**注意：main/ambient 车道 ids 为 int（vms id），extra 车道 ids 为 str（ledger_extra 的 key）——下游按 lane 区分处理。**

- [ ] **Step 1: Write the failing test**

```python
from tools.gen_batches import plan

TL = [
    {"type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
     "title": "一", "ids": [1, 2]},
    {"type": "marker", "text": "【回溯】", "recap": ""},
    {"type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_30",
     "title": "三", "ids": [3]},
    {"type": "unit", "unit_kind": "scene", "src": "snr_b_10_s", "state": "b_10",
     "title": "换章", "ids": [4]},
]
LED = [
    {"id": 1, "jp": "あ" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    {"id": 2, "jp": "い" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    {"id": 3, "jp": "う" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f2"},
    {"id": 4, "jp": "え" * 30, "chapter": "b", "kind": "narrative", "file": "snr_b_10_s", "func": "f3"},
    {"id": 9, "jp": "お" * 10, "chapter": "sys", "kind": "ambient", "file": "snr_common", "func": "u1"},
]
EXTRA = [{"key": "snr_a_10_s:5", "jp": "题", "kind": "scene_title", "file": "snr_a_10_s"}]

def test_marker_and_chapter_cut():
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    main = [r for r in rows if r["lane"] == "main"]
    assert [r["ids"] for r in main] == [[1, 2], [3], [4]]
    assert main[0]["cut_reason"] == "branch" and main[1]["cut_reason"] == "chapter"

def test_budget_cut_and_lanes():
    rows = plan(TL, LED, EXTRA, budget_chars=40)
    main = [r for r in rows if r["lane"] == "main"]
    assert [r["ids"] for r in main][:2] == [[1], [2]]      # 30字/行，40 预算下逐行成批
    assert any(r["lane"] == "ambient" and r["ids"] == [9] for r in rows)
    assert any(r["lane"] == "extra" for r in rows)

def test_batch_numbering_is_global_and_stable():
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    assert [r["batch"] for r in rows] == list(range(1, len(rows) + 1))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gen_batches.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

```python
"""timeline+ledger → data/batches.jsonl（main/extra/ambient 三车道）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl, write_jsonl


def plan(timeline, ledger_rows, extra_rows, budget_chars=9000):
    led = {r["id"]: r for r in ledger_rows}
    rows, cur_ids, cur_chars, cur_ch = [], [], 0, None

    def flush(reason):
        nonlocal cur_ids, cur_chars
        if cur_ids:
            rows.append({"lane": "main", "ids": cur_ids, "jp_chars": cur_chars,
                         "chapter": cur_ch, "cut_reason": reason})
            cur_ids, cur_chars = [], 0

    for ev in timeline:
        if ev["type"] == "marker":
            flush("branch")
            continue
        ch = led[ev["ids"][0]]["chapter"] if ev["ids"] else cur_ch
        if cur_ch is not None and ch != cur_ch:
            flush("chapter")
        cur_ch = ch
        for i in ev["ids"]:
            n = len(led[i]["jp"])
            if cur_ids and cur_chars + n > budget_chars:
                flush("budget")
            cur_ids.append(i)
            cur_chars += n
    flush("tail")

    by_file = {}
    for r in extra_rows:
        by_file.setdefault(r["file"], []).append(r["key"])
    for f in sorted(by_file):
        rows.append({"lane": "extra", "ids": by_file[f], "jp_chars": 0,
                     "chapter": f, "cut_reason": "extra"})

    amb, chars = [], 0
    for r in ledger_rows:
        if r["kind"] != "ambient":
            continue
        n = len(r["jp"])
        if amb and chars + n > budget_chars:
            rows.append({"lane": "ambient", "ids": amb, "jp_chars": chars,
                         "chapter": "sys", "cut_reason": "budget"})
            amb, chars = [], 0
        amb.append(r["id"]); chars += n
    if amb:
        rows.append({"lane": "ambient", "ids": amb, "jp_chars": chars,
                     "chapter": "sys", "cut_reason": "tail"})

    for n, r in enumerate(rows, 1):
        r["batch"] = n
    return rows


def main():
    tl = read_jsonl(DATA / "timeline.jsonl")
    led = read_jsonl(DATA / "ledger.jsonl")
    extra = read_jsonl(DATA / "ledger_extra.jsonl")
    rows = plan(tl, led, extra)
    write_jsonl(DATA / "batches.jsonl", rows)
    lanes = {}
    for r in rows:
        lanes[r["lane"]] = lanes.get(r["lane"], 0) + 1
    print("batches:", len(rows), lanes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes** → `uv run pytest tests/test_gen_batches.py -v`
- [ ] **Step 5: 真实数据生成、人工过目批次表后提交（spec：开翻前冻结）**

```bash
uv run python tools/gen_batches.py && uv run python - <<'EOF'
from tools.pipelib import DATA, read_jsonl
rows = read_jsonl(DATA / "batches.jsonl")
ids = [i for r in rows for i in r["ids"] if isinstance(i, int)]
assert len(ids) == len(set(ids)), "批次间 id 重复"
print("main 批均字数:", sum(r["jp_chars"] for r in rows if r["lane"]=="main") //
      max(1, sum(1 for r in rows if r["lane"]=="main")))
EOF
git add tools/gen_batches.py tests/test_gen_batches.py data/batches.jsonl
git commit -m "data: 批次规划三车道生成并冻结"
```

---

