### Task 10: add_patch 与 recall 召回查询

**Files:**
- Create: `tools/add_patch.py`、`tools/recall.py`
- Test: `tests/test_patch_recall.py`

**Interfaces:**
- `add_patch.py --id N --zh 文本 --reason review|recall|polish --glossary-v K [--data-dir]`：追加 patches.jsonl（append-only；schema 见 P1a 接口表；ts 可注入）
- `recall.py --glossary-v K --term 手帳 [--data-dir]`：列出 forward 中 `glossary_v < K` 且 ledger.jp 含 term 的行（id、旧译、章别），退出码 0；`--emit-batch` 时把命中行写 `work/recall/<term>.jsonl`（旁路小上下文批的输入）

- [ ] **Step 1: Write the failing test**

```python
import json
from tools.add_patch import add
from tools.recall import find
from tools.pipelib import write_jsonl, read_jsonl

def test_add_patch_appends(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    add(5, "新译", "review", 4, ts="t", data=d / "data")
    add(5, "更新译", "review", 4, ts="t2", data=d / "data")
    rows = read_jsonl(d / "data" / "patches.jsonl")
    assert [r["zh"] for r in rows] == ["新译", "更新译"]

def test_recall_finds_stale_rows(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"},
        {"id": 2, "jp": "無関係の行", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "看了她的手帐", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"},
        {"id": 2, "zh": "无关", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    hits = find(term="手帳", glossary_v=2, data=d / "data")
    assert [h["id"] for h in hits] == [1]
```

- [ ] **Step 2: Run** → FAIL；**Step 3: 实现**（两个 ~40 行脚本，签名如上）；**Step 4: Run** → passed
- [ ] **Step 5: Commit** → `git commit -m "feat: add_patch 与 recall 召回查询"`

---

