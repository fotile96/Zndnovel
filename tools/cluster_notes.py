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
