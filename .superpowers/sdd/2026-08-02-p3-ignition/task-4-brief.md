### Task 4: gen_plan 段模式 `--segment`

**Files:**
- Modify: `tools/gen_plan.py`（`render()` 加 `segment=None` 参数；`main()` 加 `--segment`）
- Test: `tests/test_gen_plan.py`（追加两个测试，不动既有测试）

**Interfaces:**
- Consumes: 既有 `render(sel, label, lane, every=5, baseline="none", glossary_v=GLOSSARY_V, lane_cfg=None, …)` 返回 markdown 字符串；`main()` 的 `--batches A-B --label L` 模式。
- Produces: `render(..., segment="seg1-s2")` 在计划头部（`_header` 之后）插入「段开场自检」节、在尾部追加「段末流程」节；`main()` 新增 `--segment LABEL`（仅 `--batches` 模式下有意义）。Task 7 消费。

- [ ] **Step 1: 写失败测试**

在 `tests/test_gen_plan.py` 追加（沿用该文件既有的 sel/lane_cfg fixture 构造方式；下面 `_small_sel()` 指代该文件已有的最小批次列表构造，如无同名 helper 则内联一个两批的列表，字段齐 `batch/ids/chapter/jp_chars`）：

```python
def test_render_segment_blocks_present():
    sel = _small_sel()
    md = render(sel, label="seg1-s2", lane="main", segment="seg1-s2")
    assert "## 段开场自检" in md
    assert "lane_setup.py --lane opus --verify" in md
    assert "## 段末流程" in md
    assert "prod-opus-seg1-s2-done" in md
    assert "tools/saturation.py" in md
    # 自检在正文批次任务之前、段末流程在其后
    assert md.index("## 段开场自检") < md.index("## 段末流程")


def test_render_without_segment_unchanged():
    sel = _small_sel()
    md = render(sel, label="x", lane="main")
    assert "段开场自检" not in md and "段末流程" not in md
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_gen_plan.py -v -k segment`
Expected: FAIL（`render() got an unexpected keyword argument 'segment'`）。

- [ ] **Step 3: 实现**

`tools/gen_plan.py` 三处修改：

(a) 新增模板函数（放在 `_lane_block` 之后）：

```python
def _segment_head(segment):
    return f"""

## 段开场自检（P3 生产会话必做，缺一不可）

本计划属于检查段 **{segment}**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：

1. **工具树**：本会话执行的 `tools/` 必须来自生产 worktree——`git -C <生产worktree> describe --tags` 应等于 runbook 记录的当前生产 tag；主仓 main 上的工具**不得**用于生产批次。
2. **车道冻结**：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
3. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。"""


def _segment_tail(segment):
    return f"""

## 段末流程（本段全部批次入线后执行，缺一不可）

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. 打段完成 tag：`git tag prod-opus-{segment}-done`。
4. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`，可裁决词族当场裁，滚存词族聚类归档（runbook「段末小裁决」节）。
5. 裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。"""
```

(b) `render()` 签名加 `segment=None`，并在 parts 组装处：header 之后插入 `if segment: parts.append(_segment_head(segment))`，`return` 前 `if segment: parts.append(_segment_tail(segment))`（以该函数实际组装结构为准，保持其余 parts 顺序不变）。

(c) `main()`：`ap.add_argument("--segment", help="检查段 label（config/segments.yaml），生成段自检/段末流程块")`，并把 `segment=args.segment` 传给 `render()`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_gen_plan.py -v`
Expected: 全 passed（含既有测试——render 默认行为必须不变）。

- [ ] **Step 5: 全量测试 + commit**

Run: `uv run pytest -q` → 219 passed。

```bash
git add tools/gen_plan.py tests/test_gen_plan.py
git commit -m "feat: gen_plan 段模式——生产计划内嵌段开场自检与段末流程"
```

---

