### Task 4: gen_plan 段模式收口（parked 两项）

**Files:**
- Modify: `tools/gen_plan.py`、`config/segments.yaml`
- Test: `tests/test_gen_plan.py`、`tests/test_segments.py`（各追加）

**Interfaces:**
- Consumes: 现有 `--segment`（从 segments.yaml 读批号）、`--tools-root`（默认空）、`--lane`（`required=True`）；`config/segments.yaml` 每段现有字段 `seg/label/batches/chapters/jp_chars/review_focus`（无 `lane`）。
- Produces: ①段模式下 `--tools-root` **必填**（缺失即 `SystemExit`，报错文案指向 runbook §3）；②`segments.yaml` 每段新增 `lane` 字段（seg1–7 `main`、seg8 `extra`、seg9 `ambient`），测试锁定「与 batches.jsonl 实算一致」；③段模式下 `--lane` 变为可选——省略时取段表值，显式给出且与段表不符时 `SystemExit`；非段模式 `--lane` 仍必填、行为一字不变。

- [ ] **Step 1: 写失败测试**

`tests/test_gen_plan.py` 追加（沿用既有 `_sel()`/`LANE_CFG` fixture 与 main 调用方式）：

```python
def test_segment_mode_requires_tools_root(tmp_path):
    with pytest.raises(SystemExit, match="tools-root"):
        main(["--segment", "seg1-s2", "--label", "x",
              "--lane-dir", str(tmp_path), "--model", "opus",
              "--effort", "max", "--append-model-id", "claude-opus-5"])


def test_segment_mode_lane_from_table_and_mismatch_errors(tmp_path):
    with pytest.raises(SystemExit, match="lane"):
        main(["--segment", "seg1-s2", "--lane", "extra", "--label", "x",
              "--tools-root", "/tmp/prod", "--lane-dir", str(tmp_path),
              "--model", "opus", "--effort", "max",
              "--append-model-id", "claude-opus-5"])


def test_nonsegment_mode_still_requires_lane():
    with pytest.raises(SystemExit):
        main(["--batches", "1-2", "--label", "x"])
```

`tests/test_segments.py` 追加：

```python
def test_segments_lane_field_matches_batches():
    segs, by = _load()
    for s in segs:
        lo, hi = s["batches"]
        lanes = {by[b]["lane"] for b in range(lo, hi + 1)}
        assert lanes == {s["lane"]}, s["label"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_gen_plan.py tests/test_segments.py -v -k 'tools_root or lane_from or still_requires or lane_field'`
Expected: 4 FAIL（segments.yaml 无 lane 字段；gen_plan 无这两道校验；`--lane` 仍 required 使报错形态不同——以实际失败形态为准，只要 4 条全红）。

- [ ] **Step 3: 实现**

- `config/segments.yaml`：9 段各加一行 `lane: main|extra|ambient`（按 Step 1 测试对 batches.jsonl 的实算——seg1–7 为 main，seg8 为 extra，seg9 为 ambient）。
- `tools/gen_plan.py` `main()`：`--lane` 改 `required=False`；解析后集中校验：
  - 段模式（`args.segment`）：读段表条目（现有逻辑），取其 `lane` 字段；`args.lane` 为 None 时用段表值，不为 None 且不等时 `raise SystemExit(f"--lane {args.lane} 与段表 {label} 的 lane={seg_lane} 不符")`；`args.tools_root` 为空时 `raise SystemExit("--segment 模式必须给 --tools-root（生产 worktree 绝对路径，见 docs/ops/p3-production-runbook.md §3）——漏传会产出未钉死的计划")`。
  - 非段模式：`args.lane` 为 None 时 `raise SystemExit("--lane 必填")`（保持既有必填语义）。

- [ ] **Step 4: 跑测试 + 非段模式逐字节回归**

Run: `uv run pytest tests/test_gen_plan.py tests/test_segments.py -v` → 全 passed。
再做逐字节回归（本仓库已两次用此法）：取 `git show HEAD:tools/gen_plan.py` 至临时目录，对 3 组**不传 segment** 的输入（含 `--lane main --batches 1-35` 车道模式）分别调用新旧 `render()`/`select()`，断言输出 sha256 相同；结果写报告。

- [ ] **Step 5: 全量测试 + commit**

Run: `uv run pytest -q` → 248 passed。

```bash
git add tools/gen_plan.py config/segments.yaml tests/test_gen_plan.py tests/test_segments.py
git commit -m "fix: 段模式强制 --tools-root 并由段表推导/校验 lane（点火终审 parked 两项）"
```

---

