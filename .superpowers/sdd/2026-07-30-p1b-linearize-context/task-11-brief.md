### Task 11: 端到端 dry-run（无 API、无翻译）

**Files:**
- Create: `tests/test_e2e_dryrun.py`

- [ ] **Step 1: 写端到端测试**（真实 data/ 上运行，进默认测试套件；依赖 Task 5/6 产物已入库）：

```python
import json, subprocess, sys
from tools.pipelib import REPO, WORK, read_jsonl

def test_batch1_context_and_fake_roundtrip(tmp_path):
    r = subprocess.run([sys.executable, "tools/build_context.py",
                        "--batch", "1", "--profile", "cc", "--jp-fallback"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
    draft = [{"id": row["id"], "zh": "【占位】" + row["jp"]} for row in src]
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "batch_1.draft.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
        encoding="utf-8")
    r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                        cwd=REPO, capture_output=True, text=True)
    # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
    assert r2.returncode == 0, r2.stdout + r2.stderr
```

- [ ] **Step 2: Run** → `uv run pytest tests/test_e2e_dryrun.py -v` 通过；随后 `uv run pytest -q` 全套回归全绿
- [ ] **Step 3: work/ 产物不入库（已在 .gitignore）；Commit** → `git commit -m "test: 端到端 dry-run（context→假草稿→check_batch）"`

---

## 完成定义

- `uv run pytest -q` 全绿（含 e2e）；`check_timeline` OK；batches.jsonl 冻结入库。
- `build_context --batch 1 --profile cc` 产出可读 context.md（人工抽查一次）。
- P2 试点（CC 翻第 1 章 + 基线对照）所需全部工件就绪；成本模拟器与 API 客户端属 P2，不在本计划。

## 风险与对策

- **展开器状态机边角**（skip 语义、嵌套选择迷宫 s2s_190_sel）：以 check_timeline 全书覆盖断言兜底；个别复杂状态允许在 route_plan 用显式 `script`/多段 `story` 绕行，宁可路线文件啰嗦不写聪明代码。
- **孤儿函数清单膨胀**：unit_funcs.yaml 每条附一句归属理由；Task 5 检查点让用户抽查。
- **timeline 返工**：dag.json/timeline/batches 全部可重建且字节确定，重建后必须重跑 check_timeline + gen_batches 并重新人工过目批次表（append-only 的 forward 不受影响，但批次边界变更仅允许发生在未开翻区段——已开翻批次的边界冻结，见 spec §5.0）。
