### Task 9: tools/polish_amplify.py（意图归纳 + 放大扫描装配）

**Files:**
- Create: `tools/polish_amplify.py`
- Test: `tests/test_polish_amplify.py`

**Interfaces:**
- Consumes: `decisions.jsonl`（reason_code）、`triage.json`、candidates、frozen
- Produces:
  - `digest(label) -> str`：意图纪要 markdown——原因码分布表 + 每码 ≤3 个代表例（jp/opus/候选/最终 zh/裁决语），追加写入 `frozen/../rulings.md`（**追加**，不覆盖）并返回文本
  - `scan_prompt(label) -> str`：纪要 + 整 SEG 四桶结果全景（含桶 3 落选句全文）+ 输出契约（同 Task 4，channel 固定 amplify、raw 落 `raw/amplify/`）
  - 轮数闸：`rulings.md` 里已有本 SEG 放大标记 → 拒绝再装配（`amplify_rounds: 1`）
- CLI: `--seg <label> --digest` / `--seg <label> --scan-prompt --out <path>`
- 放大产物回炉：直接复用 `polish_ingest --channel amplify` + `polish_triage`（amplify 恒不 autoclear，Task 7 已保证）→ 追加小裁决 → `polish_commit`。

- [ ] **Step 1: 失败测试**：3 条 decisions（两码）→ digest 含分布表与代表例；二次调用 scan 装配被轮数闸拒绝。
- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：轮数闸恒放行 → 测试红。
- [ ] **Step 5: Commit** — `feat: polish_amplify——裁决意图纪要+放大扫描装配（每段一轮）`

---

