### Task 1: 提案预聚类 helper `tools/cluster_notes.py`

**Files:**
- Create: `tools/cluster_notes.py`
- Test: `tests/test_cluster_notes.py`

**Interfaces:**
- Consumes: 车道 `data/notes/<chapter>.md`（格式：`## batch N` 分节，`### 序号. 标题` 提案块，标题主形态 `<jp> → <zh>（注）`，变体有多词 `A / B / C → x / y / z`、无箭头、`★存疑` 前缀）；`tools.saturation.saturation(term, ledger_rows, done_ids)`；`tools.resolve.resolve_map`。
- Produces: `parse_notes(text, chapter) -> list[dict(chapter, batch, num, title, terms, starred, body)]`；`cluster(proposals) -> dict[term_key, list[proposal]]`（多词提案进多个簇；无箭头/无词项归 `"（未归词）"` 簇）；CLI `uv run python tools/cluster_notes.py --lane-dir <lane> [--gate 0.8] [--out FILE]` 输出裁决卷宗 markdown（按词族聚合、附饱和度判定）。段末小裁决会话（runbook §5）用它把散提案变成卷宗。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_cluster_notes.py`：

```python
"""提案预聚类：notes/*.md 散提案 → 按词族聚合的裁决卷宗（P3 spec §4 新工具）。"""
from tools.cluster_notes import parse_notes, cluster, extract_terms

NOTES = """# 术语提案 · s1s（opus 车道）

> 说明行。

## batch 4

### 1. 寝癖 → 睡翘的头发（**跨轨复现**）
- id 7327、7329
- 理由：略。

### 2. 菜单名的拉丁形态需要一条形态判据
- id 6632

### 3. 『ことば』(7302) → 『话语』
- 建议沿用。

## batch 7

### 1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质
- id 6351

### 2. ★存疑（非术语）：7374 的行宽警告
- 不是术语。

### 3. 寝癖 → 头发睡翘了
- 又一处。
"""


def test_parse_notes_blocks_and_batches():
    ps = parse_notes(NOTES, "s1s")
    assert len(ps) == 6
    assert [p["batch"] for p in ps] == [4, 4, 4, 7, 7, 7]
    assert ps[0]["chapter"] == "s1s" and ps[0]["num"] == 1
    assert "id 7327" in ps[0]["body"]
    assert ps[4]["starred"] is True


def test_extract_terms_variants():
    assert extract_terms("1. 寝癖 → 睡翘的头发（**跨轨复现**）") == ["寝癖"]
    assert extract_terms("3. 『ことば』(7302) → 『话语』") == ["ことば"]
    assert extract_terms("1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质") == ["海馬", "内嗅皮質"]
    assert extract_terms("2. 菜单名的拉丁形态需要一条形态判据") == []


def test_cluster_merges_across_batches_and_buckets_unkeyed():
    ps = parse_notes(NOTES, "s1s")
    c = cluster(ps)
    assert len(c["寝癖"]) == 2                       # batch 4 与 batch 7 合簇
    assert len(c["海馬"]) == 1 and len(c["内嗅皮質"]) == 1
    assert len(c["（未归词）"]) == 2                  # 无箭头 + ★存疑


def test_main_renders_dossier(tmp_path, capsys):
    import json
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(NOTES, encoding="utf-8")
    (lane / "data" / "ledger.jsonl").write_text(json.dumps(
        {"id": 7327, "jp": "寝癖がなおらない", "chapter": "s1s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 7327, "zh": "x"}), encoding="utf-8")
    rc = main(["--lane-dir", str(lane), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "寝癖" in out and "可裁决" in out          # 1/1 覆盖 → ratio 1.0 ≥ gate
    assert "（未归词）" in out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_cluster_notes.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.cluster_notes`）。

- [ ] **Step 3: 写实现**

写入 `tools/cluster_notes.py`：

```python
"""提案预聚类：把车道 notes/*.md 的散条提案按词族聚合成裁决卷宗（P3 spec §2/§4）。
段末小裁决会话的输入整理器——聚合跨批/跨章的同词提案，并对每个词族附
saturation 饱和度判定（≥gate 可裁决，否则滚存）。只读，不改任何 notes 文件。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import read_jsonl
from tools.resolve import resolve_map
from tools.saturation import saturation

BATCH_RE = re.compile(r"^## batch (\d+)\s*$")
PROP_RE = re.compile(r"^### (\d+)\.\s*(.+)$")
# 标题里包裹词项的装饰：markdown 粗体、引号、括号注（含 (7302) 这类 id 注）
STRIP_RE = re.compile(r"\*\*|[『』「」]|[（(][^）)]*[）)]")
UNKEYED = "（未归词）"


def extract_terms(title: str) -> list:
    t = re.sub(r"^\d+\.\s*", "", title)
    if "→" not in t:
        return []
    left = STRIP_RE.sub("", t.split("→", 1)[0]).replace("★", "")
    return [w.strip() for w in left.split("/") if w.strip()]


def parse_notes(text: str, chapter: str) -> list:
    props, batch, cur = [], None, None
    for line in text.splitlines():
        if m := BATCH_RE.match(line):
            batch = int(m.group(1))
            continue
        if m := PROP_RE.match(line):
            if cur:
                props.append(cur)
            title = m.group(2)
            cur = {"chapter": chapter, "batch": batch, "num": int(m.group(1)),
                   "title": title, "terms": extract_terms(title),
                   "starred": "★" in title, "body": ""}
            continue
        if cur is not None and not line.startswith("## "):
            cur["body"] += line + "\n"
        elif cur is not None:
            props.append(cur)
            cur = None
    if cur:
        props.append(cur)
    return props


def cluster(proposals: list) -> dict:
    c = {}
    for p in proposals:
        for key in (p["terms"] or [UNKEYED]):
            c.setdefault(key, []).append(p)
    return c


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane-dir", required=True)
    ap.add_argument("--gate", type=float, default=0.8)
    ap.add_argument("--out", help="省略则打印 stdout")
    a = ap.parse_args(argv)
    lane = Path(a.lane_dir)
    data = lane / "data"
    props = []
    for p in sorted((data / "notes").glob("*.md")):
        props += parse_notes(p.read_text(encoding="utf-8"), p.stem)
    ledger = read_jsonl(data / "ledger.jsonl")
    extra = data / "ledger_extra.jsonl"
    if extra.exists():
        ledger += read_jsonl(extra)
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    done = set(resolve_map(fwd, pat))
    c = cluster(props)
    lines = [f"# 术语提案裁决卷宗（{lane.name} 车道，共 {len(props)} 条提案 / {len(c)} 个词族）",
             ""]
    def _order(item):
        # 多提案词族在前（跨批冲突优先裁），未归词殿后
        key, ps = item
        return (key == UNKEYED, -len(ps), key)
    for key, ps in sorted(c.items(), key=_order):
        if key == UNKEYED:
            head = f"## {UNKEYED}（{len(ps)} 条，逐条人工过目）"
        else:
            s = saturation(key, ledger, done)
            verdict = ("无出现" if s["ratio"] is None
                       else "可裁决" if s["ratio"] >= a.gate else "滚存")
            ratio = "-" if s["ratio"] is None else f"{s['ratio']:.3f}"
            head = (f"## {key}（{len(ps)} 条提案 | 饱和度 {s['covered']}/{s['total']}"
                    f"={ratio} → **{verdict}**）")
        lines.append(head)
        for p in ps:
            lines.append(f"### [{p['chapter']} b{p['batch']} #{p['num']}] {p['title']}")
            lines.append(p["body"].rstrip())
            lines.append("")
    text = "\n".join(lines)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"卷宗已写 {a.out}（{len(props)} 提案 / {len(c)} 词族）")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_cluster_notes.py -v` → 4 passed。

- [ ] **Step 5: 真实数据冒烟**

Run: `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/dossier.md`
Expected: 汇总行显示约 216 条提案（P2 全量）；抽看 `寝癖`（应为多条合簇、饱和度 1.000 可裁决）与 `（未归词）` 段。把汇总行与两个抽样写进报告。**只读操作，notes 文件不得有任何变动**（`git status` 验证）。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 238 passed。

```bash
git add tools/cluster_notes.py tests/test_cluster_notes.py
git commit -m "feat: 提案预聚类卷宗生成器（段末裁决输入整理）"
```

---

