### Task 9: gen_plan（CC 后端批次计划生成器）

**Files:**
- Create: `tools/gen_plan.py`
- Test: `tests/test_gen_plan.py`

**Interfaces:**
- Produces: CLI `uv run python tools/gen_plan.py --lane main --chapter s1s [--checkpoint-every 5]` → `docs/superpowers/plans/translate-<chapter>.md`；函数 `gen_plan.render(batches, chapter, lane, every) -> str`。每批一个任务（build_context cc/revise? 试点期 baseline=none → 参数化 `--baseline`）：①build_context ②按 prompts/translator_cc.md 派翻译子代理 ③check_batch ④append_forward+commit `data: <ch> 批次N 译文入线`；每 every 批插检查点任务（术语提案裁决+抽查）；章末任务=梗概回译自检+人工评审 gate。

- [ ] **Step 1: Write the failing test**

```python
from tools.gen_plan import render

BATCHES = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
            "chapter": "s1s", "cut_reason": "budget"} for i in range(1, 8)]

def test_render_contains_tasks_and_checkpoints():
    md = render(BATCHES, chapter="s1s", lane="main", every=3)
    assert md.count("### Task") >= 7 + 2          # 7 批任务+至少 2 检查点
    assert "build_context.py --batch 1" in md
    assert "check_batch.py --batch 1" in md
    assert "append_forward.py --batch 1" in md
    assert "梗概回译自检" in md and "CHECKPOINT" in md

def test_only_selected_chapter_and_lane():
    extra = BATCHES + [{"batch": 99, "lane": "ambient", "ids": [99], "jp_chars": 1,
                        "chapter": "sys", "cut_reason": "tail"}]
    md = render(extra, chapter="s1s", lane="main", every=5)
    assert "--batch 99" not in md
```

- [ ] **Step 2: Run** → FAIL（ModuleNotFoundError）
- [ ] **Step 3: 实现**（纯字符串模板函数 + main() 读 batches.jsonl 过滤写文件；模板含 executing-plans 头注、每任务 4 步 checkbox、检查点任务文案）
- [ ] **Step 4: Run** → 2 passed
- [ ] **Step 5: Commit** → `git commit -m "feat: gen_plan CC 批次计划生成器"`

---

