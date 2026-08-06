### Task 10: tools/polish_calibrate.py（通道准入小考）

**Files:**
- Create: `tools/polish_calibrate.py`
- Test: `tests/test_polish_calibrate.py`

**Interfaces:**
- Consumes: opus 车道 `patches.jsonl`（金标池：reason∈{review, recall} 的 id 的**现行文本**）、frozen/source.jsonl、frozen/opus.jsonl、polishlib
- Produces:
  - `make(label, n_gold=10, n_norm=10) -> Path`：确定性抽样（种子同 Task 7），产 `calib/<label>.batch.jsonl`（混排、**不带锁标**、格式同生产批正文行）+ `calib/<label>.truth.json`（id→{is_gold}，**此文件不进任何 prompt**）
  - `score(label, raw_path) -> dict`：`{"gold_unchanged": x, "gold_minor": y, "gold_substantive": z, "pass": z/(x+y+z) < CFG["calib_fail"]}`（三档按 edit_distance vs minor_edit/autoclear_limit）；结果写 `channel_state.json` 的 `{channel: {"autoclear": pass}}`
- CLI: `--seg <label> --make` / `--seg <label> --score --channel <ch> --raw <path>`
- 金标已知偏差（spec §8）在工具输出里原样播报：「金标为曾出问题的非随机子集，本考只做门槛」。

- [ ] **Step 1: 失败测试**：金标 10 句中 4 句实质改写 → pass=False、channel_state 关闭 autoclear；0 句 → True 开启。truth 文件绝不出现在 make 产出的 batch 文件内容里。
- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：①三档阈值互换；②truth 混进 batch（测试抓）。
- [ ] **Step 5: Commit** — `feat: polish_calibrate——金标准入小考（门槛制，播报已知偏差）`

---

