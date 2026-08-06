### Task 8: tools/polish_commit.py（唯一清关口）

**Files:**
- Create: `tools/polish_commit.py`
- Test: `tests/test_polish_commit.py`

**Interfaces:**
- Consumes: `triage.json`、`decisions.jsonl`、`candidates.*.jsonl`、`add_patch.resolve_data_dir`（车道模式显式 --data-dir 闸原样复用）、`build_context.glossary_version`
- Produces:
  - `commit(label, data_dir, dry_run=True) -> list[patch_row]`
    - 来源两路：①decisions 里 verdict∈{adopt, edit} 的（adopt 取 chosen_channel 候选 zh；edit 取 edited_zh）；②triage 里 `autoclear and not sampled` 的候选
    - patch 行：`{"id", "zh", "reason": "polish", "glossary_v", "ts", "prov": {"channel", "candidate_ts", "seg"}}`（resolve 只读已知键，向后兼容）
    - 自动清关的同时 append 一条 `decisions.jsonl` 记录 `verdict="auto"`（裁决面完备：每个落地 patch 都有 decision 可查）
    - **dry_run=True 是默认**：只打印将写入的 patch 与倒查链（id→candidate ts→prompt_hash），不落盘；`--apply` 才写
    - 写前逐 id 过 `add_patch.existing_patches` 播报（防误覆盖已有裁决——注意锁定面本就排除了冻结时点已有 patch 的 id，此处防的是**润色期间新落的** patch）
  - 幂等：`committed.json` 记录已清关 (id, decision_ts)；重复 `--apply` no-op
- CLI: `--seg <label> --data-dir <dir> [--apply]`

- [ ] **Step 1: 失败测试**：dry-run 不写文件但返回 2 行；apply 写入且 prov 回指正确；重复 apply 零新增；期间新出现的 patch 触发 stderr 播报。
- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：①dry_run 也落盘（测试抓文件不存在）；②autoclear sampled 的也清关；③prov 丢 channel。
- [ ] **Step 5: Commit** — `feat: polish_commit——保税仓唯一清关口（dry-run 默认+prov 倒查链）`

---

