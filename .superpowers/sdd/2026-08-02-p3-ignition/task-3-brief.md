### Task 3: 陷阱批回验 `tools/canary.py`

**Files:**
- Create: `tools/canary.py`
- Test: `tests/test_canary.py`

**Interfaces:**
- Consumes: `tools.check_batch.check(source_rows, draft_rows, speakers, glossary) -> {"hard":[…],"warn":[…]}`；`tools.detect_collapse.scan(source_rows, draft_rows, names, …) -> [hits]`、`retained_names(path)`、`_glossary_max(root)`；`tools/build_context.py --batch N --profile cc --repo <lane_dir>`（缺 ctx 时子进程重生，产物在 `<lane_dir>/work/ctx/batch_N/source.jsonl`，P2 已验证逐字节确定性）。
- Produces: CLI 两模式——`--lane-dir L --batches 1-35 --out F [--regen-ctx]` 输出规范化判定 JSON；`--diff OLD NEW` 比对两份判定，无差异 exit 0、有差异打印每批差异摘要并 exit 1。**用法（runbook 引用）**：工具升级时旧 worktree 与新 main 各跑一次 `--out`（同一车道数据、同一时刻），`--diff` 通过才允许滚动生产 tag；若升级触及 `build_context.py` 本身，两边都加 `--regen-ctx`。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_canary.py`：

```python
"""canary：同一车道数据上重算校验判定并成对比对——工具升级的回归闸（P3 spec §3）。"""
import json
from pathlib import Path

from tools.canary import batch_verdicts, diff_verdicts, _draft_from_forward


def _mk_lane(tmp_path: Path) -> Path:
    lane = tmp_path / "lane"
    (lane / "data").mkdir(parents=True)
    (lane / "glossary").mkdir()
    (lane / "work" / "ctx" / "batch_1").mkdir(parents=True)
    (lane / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [10, 11], "chapter": "s1s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text("\n".join([
        json.dumps({"id": 10, "zh": "【直哉】「旧译」"}, ensure_ascii=False),
        json.dumps({"id": 10, "zh": "【直哉】「新译」"}, ensure_ascii=False),  # 重译：取末次
        json.dumps({"id": 11, "zh": "旁白行"}, ensure_ascii=False),
    ]), encoding="utf-8")
    (lane / "work" / "ctx" / "batch_1" / "source.jsonl").write_text("\n".join([
        json.dumps({"id": 10, "jp": "【直哉】「もとの文」"}, ensure_ascii=False),
        json.dumps({"id": 11, "jp": "地の文"}, ensure_ascii=False),
    ]), encoding="utf-8")
    (lane / "glossary" / "speakers.json").write_text(
        json.dumps({"直哉": "直哉"}, ensure_ascii=False), encoding="utf-8")
    (lane / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (lane / "glossary" / "glossary.v1.yaml").write_text(
        "version: 1\ncharacters: []\nterms: []\n", encoding="utf-8")
    return lane


def test_draft_takes_last_occurrence():
    fwd = [{"id": 10, "zh": "A"}, {"id": 10, "zh": "B"}]
    assert _draft_from_forward(fwd, [10]) == [{"id": 10, "zh": "B"}]


def test_batch_verdicts_structure(tmp_path):
    v = batch_verdicts(_mk_lane(tmp_path), [1])
    assert set(v) == {"1"}
    assert set(v["1"]) == {"check", "collapse"}
    assert v["1"]["check"]["hard"] == []          # 说话人对齐、无 hard


def test_diff_detects_change(tmp_path):
    lane = _mk_lane(tmp_path)
    a = batch_verdicts(lane, [1])
    b = json.loads(json.dumps(a))
    b["1"]["check"]["warn"].append({"id": 11, "rule": "W2", "msg": "x"})
    assert diff_verdicts(a, a) == []
    d = diff_verdicts(a, b)
    assert d and d[0].startswith("batch 1")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_canary.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.canary`）。

- [ ] **Step 3: 写实现**

写入 `tools/canary.py`：

```python
"""陷阱批回验：对已入线批次用当前工具树重算 check_batch + detect_collapse 判定，
输出规范化 JSON。工具升级流程（P3 spec §3）：旧 tag worktree 与新 main 各跑一次
--out（同一车道数据），--diff 一致才允许滚动生产 tag。draft 取 forward.jsonl 中
每 id 的末次出现（＝入线原稿；patches 不参与，判定对齐的是入线时刻）。"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import dumps, read_jsonl
from tools.check_batch import check
from tools.detect_collapse import _glossary_max, retained_names, scan


def _draft_from_forward(forward_rows, ids):
    m = {}
    for r in forward_rows:
        if r["id"] in ids:
            m[r["id"]] = r["zh"]
    return [{"id": i, "zh": m[i]} for i in ids if i in m]


def _ensure_ctx(lane_dir: Path, n: int, regen: bool) -> Path:
    src = lane_dir / "work" / "ctx" / f"batch_{n}" / "source.jsonl"
    if regen or not src.exists():
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "build_context.py"),
             "--batch", str(n), "--profile", "cc", "--repo", str(lane_dir)],
            check=True)
    return src


def batch_verdicts(lane_dir: Path, nums, regen_ctx: bool = False) -> dict:
    lane_dir = Path(lane_dir)
    fwd = read_jsonl(lane_dir / "data" / "forward.jsonl")
    speakers = json.loads(
        (lane_dir / "glossary" / "speakers.json").read_text(encoding="utf-8"))
    glossary = json.loads(
        (lane_dir / "glossary" / "active.json").read_text(encoding="utf-8"))
    names = retained_names(_glossary_max(lane_dir))
    out = {}
    for n in nums:
        source = read_jsonl(_ensure_ctx(lane_dir, n, regen_ctx))
        draft = _draft_from_forward(fwd, [r["id"] for r in source])
        out[str(n)] = {"check": check(source, draft, speakers, glossary),
                       "collapse": scan(source, draft, names)}
    return out


def diff_verdicts(old: dict, new: dict) -> list:
    msgs = []
    for k in sorted(set(old) | set(new), key=int):
        if old.get(k) != new.get(k):
            o, n = old.get(k, {}), new.get(k, {})
            msgs.append(
                f"batch {k}: hard {len(o.get('check', {}).get('hard', []))}"
                f"->{len(n.get('check', {}).get('hard', []))}, "
                f"warn {len(o.get('check', {}).get('warn', []))}"
                f"->{len(n.get('check', {}).get('warn', []))}, "
                f"collapse {len(o.get('collapse', []))}->{len(n.get('collapse', []))}")
    return msgs


def _parse_range(s: str):
    lo, hi = s.split("-")
    return list(range(int(lo), int(hi) + 1))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane-dir")
    ap.add_argument("--batches", help="闭区间，形如 1-35")
    ap.add_argument("--out")
    ap.add_argument("--regen-ctx", action="store_true",
                    help="强制重生 ctx（升级触及 build_context 时两边都要加）")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"))
    args = ap.parse_args(argv)
    if args.diff:
        old = json.loads(Path(args.diff[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(args.diff[1]).read_text(encoding="utf-8"))
        msgs = diff_verdicts(old, new)
        for m in msgs:
            print(m)
        print(f"canary diff: {'一致' if not msgs else f'{len(msgs)} 批有差异'}")
        return 1 if msgs else 0
    if not (args.lane_dir and args.batches and args.out):
        raise SystemExit("生成模式需 --lane-dir --batches --out；比对模式用 --diff OLD NEW")
    v = batch_verdicts(Path(args.lane_dir), _parse_range(args.batches), args.regen_ctx)
    Path(args.out).write_text(dumps(v), encoding="utf-8")
    print(f"canary: {len(v)} 批判定已写 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

注：`dumps` 来自 pipelib（排序确定性输出），两棵树产出的 JSON 可直接文本比对。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_canary.py -v`
Expected: 3 passed。

- [ ] **Step 5: 真实数据冒烟（P2 全段基线）**

```bash
uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 1-35 \
  --out /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/canary-p2.json
uv run python tools/canary.py --diff \
  /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/canary-p2.json \
  /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/canary-p2.json
```
Expected: 第一条生成 35 批判定（缺 ctx 的批次自动重生，耗时数分钟）；hard 应全空（P2 全程 hard=0）；自比对输出「一致」exit 0。**注意**：此时车道 glossary 仍是 v6 冻结（Task 5 才切 v7），warn 数与 P2 台账同基准可对照；若 hard 非空，停下核查 `_draft_from_forward` 的 id 类型匹配（int vs str）。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 217 passed。

```bash
git add tools/canary.py tests/test_canary.py
git commit -m "feat: canary 陷阱批回验（工具升级回归闸）"
```

---

