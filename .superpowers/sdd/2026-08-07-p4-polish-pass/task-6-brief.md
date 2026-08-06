### Task 6: tools/polish_check.py（保税仓机械闸）

**Files:**
- Create: `tools/polish_check.py`
- Test: `tests/test_polish_check.py`

**Interfaces:**
- Consumes: `check_batch.check`（R2a/R2b/R2c/W1/W2/W3 整体复用）、frozen/source.jsonl、candidates、`glossary/speakers.json`、frozen glossary active.json
- Produces: `gate(label, channel) -> dict`：对该通道全部候选跑 `check_batch.check(source_rows, draft_rows, speakers, glossary)`（draft=候选 zh），返回 `{id: {"hard": [...], "warn": [...]}}` 并写 `gates.<channel>.json`；**hard 非空的候选后续一切分流不得自动清关**（Task 7 消费）。W4 不在此跑（需全库兄弟索引，放清关后全段复检，见 Task 11 runbook）。
- CLI: `--seg <label> --channel <ch>`

- [ ] **Step 1: 失败测试**：候选丢【】说话人 → gate 报 R2b hard；候选行宽爆 → W3 warn；全绿候选 → 空。
- [ ] **Step 2: 失败** → **Step 3: 实现**（薄封装：组装 source_rows/draft_rows → check → 落盘）。
- [ ] **Step 4: 通过 + 变异**：gate 吞掉 hard 只留 warn → 测试必须红。
- [ ] **Step 5: Commit** — `feat: polish_check——候选级机械闸（复用 check_batch）`

---

