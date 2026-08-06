### Task 7: tools/polish_triage.py（四桶分流 + 自动清关判定 + 抽检）

**Files:**
- Create: `tools/polish_triage.py`
- Test: `tests/test_polish_triage.py`

**Interfaces:**
- Consumes: 全部 `candidates.*.jsonl`、frozen/opus.jsonl、frozen/locked.json、`gates.*.json`、polishlib（edit_distance/autoclear_limit/CFG）
- Produces:
  - `triage(label) -> dict` 并写 `triage.json`：每候选一条
    `{id, channel, bucket, edit, autoclear: bool, sampled: bool}`
    - bucket 判定顺序：locked→0（理论上 ingest 已判死，此处兜底再判死）；`zh == opus`（逐字）→1；其余按（`adjudicate` 显式请裁优先，再按 `edit 大→小`、同 edit 按 `score 低→高`）排序，前 K−抽检占用 名→2；其余→3
    - autoclear：bucket∈{2,3} 且 `edit ≤ autoclear_limit(opus)` 且 gates hard 空 且 channel 自动清关权开启（`channel_state.json`，准入小考写入，缺省关闭）→ 从桶中摘出为 autoclear；其中按 `sample_rate` 抽 `sampled=true` 塞回裁决队列（占 K）
    - **channel=="amplify" 恒不 autoclear**
    - 抽样与排序**确定性**：random.Random(int(manifest["files"]["source.jsonl"][:8], 16))
  - `queue.md`：裁决队列（K 内，多通道同 id 并排：jp / opus / 各候选 zh+score+note）
- CLI: `--seg <label>`

- [ ] **Step 1: 失败测试**

```python
def test_buckets(mini):                            # 造 4 类候选
    t = pt.triage("segX")
    assert by_id(t, 10)["bucket"] == 1             # zh==opus
    assert by_id(t, 11)["bucket"] == 2             # 大改，配额内
    assert by_id(t, 12)["bucket"] == 3             # 配额 K=1 挤出
    assert by_id(t, 13)["bucket"] == 0             # locked 兜底

def test_autoclear_requires_gate_green_and_right(mini):
    mini.enable_autoclear("chA")
    t = pt.triage("segX")
    assert by_id(t, 14)["autoclear"]               # 小改+绿
    mini.make_gate_hard(14)
    assert not by_id(pt.triage("segX"), 14)["autoclear"]

def test_amplify_never_autoclears(mini):
    mini.enable_autoclear("amplify")
    assert not by_id(pt.triage("segX"), 15, ch="amplify")["autoclear"]

def test_deterministic_sampling(mini):
    assert pt.triage("segX") == pt.triage("segX")  # 两跑逐字段一致
```

- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：①autoclear 无视 hard；②配额排序丢显式请裁优先；③抽样用系统随机（两跑不一致测试抓）。
- [ ] **Step 5: Commit** — `feat: polish_triage——四桶分流+条件自动清关+确定性抽检`

---

