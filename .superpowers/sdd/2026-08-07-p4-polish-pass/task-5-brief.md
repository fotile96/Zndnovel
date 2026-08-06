### Task 5: tools/polish_ingest.py（唯一入仓）

**Files:**
- Create: `tools/polish_ingest.py`
- Test: `tests/test_polish_ingest.py`

**Interfaces:**
- Consumes: `raw/<channel>/b<N>.out`（模型输出契约见 Task 4）、frozen/source.jsonl、frozen/opus.jsonl、frozen/locked.json、plan.json（prompt_hash）
- Produces:
  - `ingest(label, channel, batch) -> dict`：`{"ok": bool, "added": int, "dead": [...], "reason": str}`
  - 成功 → append `candidates.<channel>.jsonl`，每行补齐 `jp_hash`（sha256(frozen jp)）、`opus_hash`、`channel`、`batch`、`prompt_hash`、`ts`
  - **判死**（记入返回值并打印，不入仓）：id 不在批内；jp_tail 与 frozen 不符；锁定 id 出稿（额外计入 `discipline.<channel>.json` 纪律画像）
  - **整批失败**（不入仓任何行）：raw 不是合法 JSONL；批内非锁定 id 覆盖不完整（截断特征）
  - **幂等**：`ingested.<channel>.json` 记录已入仓批号；重复调用同批 = no-op（打印提示）
- CLI: `--seg <label> --channel <ch> --batch N`（或 `--all` 扫 raw 目录）

- [ ] **Step 1: 失败测试**（mini 段 + 手造 raw）

```python
def test_ingest_ok_and_receipt(mini):
    r = pi.ingest("segX", "chA", 1)
    assert r["ok"] and r["added"] == 3
    rows = list(read_jsonl(mini.d / "candidates.chA.jsonl"))
    assert rows[0]["jp_hash"] == sha256_text(mini.jp[10])

def test_bad_tail_kills_line_not_batch(mini):
    mini.corrupt_tail(id=11)
    r = pi.ingest("segX", "chA", 1)
    assert r["ok"] and r["added"] == 2 and r["dead"][0]["id"] == 11

def test_locked_id_killed_and_disciplined(mini):
    mini.add_locked_line(id=13)
    r = pi.ingest("segX", "chA", 1)
    assert 13 in [d["id"] for d in r["dead"]]
    assert json.loads((mini.d / "discipline.chA.json").read_text())["locked_hits"] == 1

def test_incomplete_coverage_fails_whole_batch(mini):
    mini.drop_line(id=12)                          # 截断特征
    r = pi.ingest("segX", "chA", 1)
    assert not r["ok"]
    assert not (mini.d / "candidates.chA.jsonl").exists()

def test_idempotent(mini):
    pi.ingest("segX", "chA", 1); r2 = pi.ingest("segX", "chA", 1)
    assert r2["added"] == 0 and len(list(read_jsonl(...))) == 3
```

- [ ] **Step 2: 失败** → **Step 3: 实现**（解析→三查→原子决定整批入/不入→append→记 ingested）。

- [ ] **Step 4: 通过 + 变异**：①尾串核验恒真；②覆盖不完整仍入仓；③幂等标记不写。三变异各红。

- [ ] **Step 5: Commit** — `feat: polish_ingest——回执核验+锁定判死+批级幂等的唯一入仓口`

---

