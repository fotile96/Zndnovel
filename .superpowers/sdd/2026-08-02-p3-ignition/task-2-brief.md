### Task 2: 饱和度计算器 `tools/saturation.py`

**Files:**
- Create: `tools/saturation.py`
- Test: `tests/test_saturation.py`

**Interfaces:**
- Consumes: `DATA/ledger.jsonl`（行含 `id:int, jp:str, chapter:str`）、`DATA/ledger_extra.jsonl`（可选，id 为 str）、`tools.resolve.resolve_map(forward_rows, patch_rows)`。
- Produces: `saturation(term, ledger_rows, done_ids) -> dict(term, total, covered, ratio, uncovered_by_chapter)`；CLI `uv run python tools/saturation.py --term <jp> [--term …] [--terms-file F] [--data-dir D] [--gate 0.8]` 打印 markdown 表。段末裁决会话（runbook）按 `ratio >= gate` 判「可裁决/滚存」。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_saturation.py`：

```python
"""饱和度计算器：词族「全书出现数中已译批次覆盖比」——段末裁决的证据闸门（spec §2）。"""
from tools.saturation import saturation, main


LEDGER = [
    {"id": 1, "jp": "十円玉を置く", "chapter": "s1s"},
    {"id": 2, "jp": "十円玉と十円玉", "chapter": "s1s"},   # 一行两次，按次数计
    {"id": 3, "jp": "十円玉です", "chapter": "s6s"},
    {"id": 4, "jp": "無関係の行", "chapter": "s1s"},
]


def test_saturation_counts_occurrences_not_rows():
    r = saturation("十円玉", LEDGER, done_ids={1, 2})
    assert r["total"] == 4 and r["covered"] == 3
    assert r["ratio"] == 3 / 4
    assert r["uncovered_by_chapter"] == {"s6s": 1}


def test_saturation_zero_occurrence_term():
    r = saturation("ナハメ", LEDGER, done_ids={1})
    assert r["total"] == 0 and r["ratio"] is None


def test_main_reads_data_dir_and_gates(tmp_path, capsys):
    import json
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in LEDGER), encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}) + "\n" + json.dumps({"id": 2, "zh": "y"}),
        encoding="utf-8")
    rc = main(["--term", "十円玉", "--term", "ナハメ",
               "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0.750" in out and "滚存" in out   # 0.75 < 0.8 → 滚存
    assert "无出现" in out                     # total=0 单列
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_saturation.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.saturation`）。

- [ ] **Step 3: 写实现**

写入 `tools/saturation.py`：

```python
"""词族饱和度：全书 ledger 中某日文词的出现次数里，已被译过批次覆盖的比例。
段末小裁决的证据闸门（P3 spec §2）：ratio >= gate 才允许裁决，否则聚类滚存。
读 DATA/ledger.jsonl（+ ledger_extra.jsonl 若存在）与 resolve_map（forward+patches）。"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl
from tools.resolve import resolve_map


def saturation(term: str, ledger_rows, done_ids) -> dict:
    total = covered = 0
    uncov = Counter()
    for r in ledger_rows:
        n = r.get("jp", "").count(term)
        if not n:
            continue
        total += n
        if r["id"] in done_ids:
            covered += n
        else:
            uncov[r.get("chapter", "?")] += n
    return {"term": term, "total": total, "covered": covered,
            "ratio": covered / total if total else None,
            "uncovered_by_chapter": dict(uncov)}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--term", action="append", default=[])
    ap.add_argument("--terms-file", help="每行一个日文词，# 开头为注释")
    ap.add_argument("--data-dir", default=None,
                    help="覆盖 DATA（默认 ZND_DATA 或仓库根 data/）")
    ap.add_argument("--gate", type=float, default=0.8)
    args = ap.parse_args(argv)
    data = Path(args.data_dir) if args.data_dir else DATA
    terms = list(args.term)
    if args.terms_file:
        for line in Path(args.terms_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    if not terms:
        raise SystemExit("至少给一个 --term 或 --terms-file")
    ledger = read_jsonl(data / "ledger.jsonl")
    extra = data / "ledger_extra.jsonl"
    if extra.exists():
        ledger += read_jsonl(extra)
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    done = set(resolve_map(fwd, pat))
    rows = [saturation(t, ledger, done) for t in terms]
    rows.sort(key=lambda r: (r["ratio"] is None, r["ratio"] if r["ratio"] is not None else 0))
    print("| 词 | 出现 | 已覆盖 | 饱和度 | 判定 | 未覆盖分布 |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if r["ratio"] is None:
            verdict, ratio_s = "无出现", "-"
        elif r["ratio"] >= args.gate:
            verdict, ratio_s = "可裁决", f"{r['ratio']:.3f}"
        else:
            verdict, ratio_s = "滚存", f"{r['ratio']:.3f}"
        dist = " ".join(f"{c}:{n}" for c, n in
                        sorted(r["uncovered_by_chapter"].items())) or "-"
        print(f"| {r['term']} | {r['total']} | {r['covered']} | {ratio_s} | {verdict} | {dist} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_saturation.py -v`
Expected: 3 passed。

- [ ] **Step 5: 真实数据冒烟**

Run: `uv run python tools/saturation.py --term 十円玉 --term 消しゴム --term 浜千鳥 --data-dir pilot/lanes/opus/data`
Expected: 表格输出；`十円玉` 应为 12/12 出现、饱和度 1.000、可裁决（P2 段已覆盖其全部出现——若非 1.000 检查 done 集合的 resolve 逻辑）。把实际输出记入台账。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 214 passed。

```bash
git add tools/saturation.py tests/test_saturation.py
git commit -m "feat: 词族饱和度计算器（段末裁决证据闸门）"
```

---

