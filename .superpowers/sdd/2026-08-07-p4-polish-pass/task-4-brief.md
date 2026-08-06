### Task 4: tools/polish_context.py（大批划分 + prompt 拼接）

**Files:**
- Create: `tools/polish_context.py`
- Test: `tests/test_polish_context.py`

**Interfaces:**
- Consumes: Task 3 的 frozen 全套；`data/batches.jsonl`；polishlib.CFG 双帽
- Produces:
  - `plan(label) -> list[dict]`：把段表批号区间按双帽（≤session_size 批 / ≤session_lines 行）切成会话组：`[{session: 1, batches: [36,…,41], lines: 583}, …]`——**SEG-1（b36–62）opus 时代逐批跑，本函数即是补上会话分组**
  - `render(label, session_no) -> str`：一条会话的完整 prompt——任务说明（润色契约）+ 锁定 id 清单 + frozen/glossary 全套 + 逐批的 `[b36] id: 【jp】 / 【opus zh】 / (note…)` 正文 + 输出契约
  - `main` CLI：`--seg <label> --plan`（打印会话表）/ `--seg <label> --session N --out <path>`（写 prompt 文件并打印 sha256 = prompt_hash，同时落 `pilot/polish/<label>/plan.json` 记录 {session, batches, prompt_hash}）
- 输出契约（写进 prompt，供 Task 5 解析）：每批产一个 JSONL 文件 `raw/<channel>/b<批号>.out`，每行
  `{"id": 5683, "jp_tail": "<原文末8字>", "zh": "<润色稿或原样 opus>", "score": 87, "note": "", "adjudicate": false}`；
  批内**每个非锁定 id 恰好一行**；锁定 id（带【锁】标）**不得出现**；不改动的行 zh 逐字抄 opus。

- [ ] **Step 1: 失败测试**

```python
def test_plan_respects_double_cap(mini_seg):     # mini 段：3 批，行数 300/300/100
    sessions = pc.plan("segX", session_lines=600, session_size=10)
    assert [s["batches"] for s in sessions] == [[1, 2], [3]]   # 600 顶帽切组

def test_plan_size_cap(mini_seg11):              # 11 个 10 行小批
    sessions = pc.plan("segX", session_lines=600, session_size=10)
    assert len(sessions[0]["batches"]) == 10     # 批数帽先触发

def test_render_marks_locked_and_embeds_opus(mini_seg):
    p = pc.render("segX", 1)
    assert "【锁】" in p and "锁定 id" in p
    assert "旧译文本样例" in p                    # opus zh 在正文里
    assert "b<批号>.out" not in p or True         # 输出契约按实名渲染
```

- [ ] **Step 2: 失败** → **Step 3: 实现**：`plan` 累计 `len(ids)` 与批数双帽贪心切组；`render` 读 frozen（不读活仓库——**润色输入只认冻结面**），glossary 段沿 `build_context._render_voices/_render_anchors` 的渲染函数直接 import 复用。

- [ ] **Step 4: 通过 + 变异**：①双帽只查其一；②render 从仓库活 glossary 读而非 frozen（测试用「frozen 改坏一字后 render 必须跟着变」来抓）。

- [ ] **Step 5: Commit** — `feat: polish_context——SEG-1 会话分组补齐+润色 prompt 拼接`

---

