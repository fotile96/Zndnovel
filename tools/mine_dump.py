"""P5 预研：把整部作品（main 车道全量）按 batches.jsonl 顺序编织成
「原文+初译+人工润色痕迹+译者手记」紧密排布的阅读语料，切成若干
连续 chunk 供长上下文 reader（fable max）通读并提炼润色 pattern。

层次（每行 id 依序给出，缺省层省略）：
  ⊙        进过人工裁决队列（queue.md）——用户亲眼读过的行
  J｜       日文原文（ledger）
  译｜      P3 opus 初译（forward.jsonl）
  P3裁｜    P3 段末裁决改稿（patches reason=review，非最终层时列出）
  召回｜    术语召回改稿（patches reason=recall，非最终层时列出）
  P4裁｜    段末机器裁决 verdict(reason_code)；「→人复核:」为用户复核轮改判
  候补｜    裁决面上各通道候选（score、采纳与否、批注）
  终｜      现行落盘文本（resolve 终态）＋来源标注
批与批之间穿插该批锚定的译者手记节（notes/*.md 按 `## batch N` 拆分）。
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipelib import REPO, read_jsonl  # noqa: E402

LANE = REPO / "pilot" / "lanes" / "opus"
POLISH = REPO / "pilot" / "polish"
NOTES = LANE / "data" / "notes"

_BATCH_SEC_RE = re.compile(r"^##\s*(?:批次|batch)\s*(\d+)", re.M)


def load_segment_ranges():
    import yaml
    p = REPO / "config" / "segments.yaml"
    rows = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    out = []
    for r in rows:
        b = r.get("batches")
        if r.get("label") and isinstance(b, list) and len(b) == 2:
            out.append((r["label"], b[0], b[1]))
    return out


def batch2seg(ranges, bno):
    for label, lo, hi in ranges:
        if lo <= bno <= hi:
            return label
    return None


def split_notes():
    """notes/*.md → {batch_no: [text]} + {chapter: [无批号节]}。"""
    by_batch = defaultdict(list)
    by_chapter = defaultdict(list)
    for f in sorted(NOTES.glob("*.md")):
        chap = f.stem
        txt = f.read_text(encoding="utf-8")
        # 按二级节切；文件头（# 到首个 ##）归章
        parts = re.split(r"(?m)(?=^## )", txt)
        for part in parts:
            if not part.strip():
                continue
            m = _BATCH_SEC_RE.match(part)
            if m:
                by_batch[int(m.group(1))].append(part.rstrip() + "\n")
            else:
                by_chapter[chap].append(part.rstrip() + "\n")
    return by_batch, by_chapter


def load_queue_ids():
    qids = set()
    for f in POLISH.glob("seg*/queue.md"):
        for m in re.finditer(r"^## id (\d+)", f.read_text(encoding="utf-8"), re.M):
            qids.add(int(m.group(1)))
    return qids


def load_decisions():
    """{id: [decision,...]} 按 ts 排序；第 2 条起视为用户复核轮。"""
    d = defaultdict(list)
    for f in sorted(POLISH.glob("seg*/decisions.jsonl")):
        for r in read_jsonl(f):
            d[r["id"]].append(r)
    for v in d.values():
        v.sort(key=lambda r: r.get("ts") or "")
    return d


def load_candidates(decision_ids):
    """裁决面 id 的各通道候选：{(id): {channel: cand}}（同通道取最新 ts）。"""
    c = defaultdict(dict)
    for f in sorted(POLISH.glob("seg*/candidates.*.jsonl")):
        ch = f.name.split(".")[1]
        for r in read_jsonl(f):
            if r["id"] not in decision_ids:
                continue
            prev = c[r["id"]].get(ch)
            if prev is None or (r.get("ts") or "") > (prev.get("ts") or ""):
                c[r["id"]][ch] = r
    return c


def fmt_line(i, led, fwd, chains, decs, cands, qids):
    out = []
    mark = " ⊙" if i in qids else ""
    out.append(f"#{i}{mark} J｜{led[i]['jp']}")
    base = fwd.get(i)
    if base is not None:
        out.append(f" 译｜{base}")
    chain = chains.get(i, [])
    final = chain[-1] if chain else None
    for p in chain[:-1]:
        tag = {"review": "P3裁", "recall": "召回", "polish": "P4改"}.get(p.get("reason"), p.get("reason"))
        out.append(f" {tag}｜{p['zh']}")
    ds = decs.get(i, [])
    if ds:
        d0 = ds[0]
        s = f"机:{d0.get('verdict')}"
        if d0.get("reason_code"):
            s += f"({d0['reason_code']})"
        if d0.get("chosen_channel"):
            s += f"·{d0['chosen_channel']}"
        for d in ds[1:]:
            s += f" →人复核:{d.get('verdict')}"
            if d.get("chosen_channel"):
                s += f"·{d['chosen_channel']}"
            if d.get("edited_zh"):
                s += f"「{d['edited_zh']}」"
        if ds[0].get("edited_zh") and len(ds) == 1:
            s += f" 改写「{ds[0]['edited_zh']}」"
        out.append(f" P4裁｜{s}")
        for ch, cand in sorted(cands.get(i, {}).items()):
            note = f"〔批注：{cand['note']}〕" if cand.get("note") else ""
            out.append(f" 候补｜{ch}({cand.get('score')})：{cand['zh']}{note}")
    if final is not None:
        pr = final.get("prov") or {}
        src = final.get("reason")
        if pr:
            src = f"{pr.get('seg')}·{pr.get('channel')}"
        if final["zh"] != base:
            out.append(f" 终｜{final['zh']}〔{src}·gv{final.get('glossary_v')}〕")
        else:
            out.append(f" 终｜（＝初译；人工链最终退回原稿〔{src}〕）")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-chars", type=int, default=90000)
    ap.add_argument("--out", default=str(REPO / "work" / "ctx" / "p5mine"))
    args = ap.parse_args()

    led = {r["id"]: r for r in read_jsonl(REPO / "data" / "ledger.jsonl")}
    fwd = {r["id"]: r["zh"] for r in read_jsonl(LANE / "data" / "forward.jsonl")}
    pats = read_jsonl(LANE / "data" / "patches.jsonl")
    chains = defaultdict(list)
    for p in pats:
        chains[p["id"]].append(p)
    for v in chains.values():
        v.sort(key=lambda r: r.get("ts") or "")
    bats = [b for b in read_jsonl(REPO / "data" / "batches.jsonl") if b["lane"] == "main"]
    ranges = load_segment_ranges()
    qids = load_queue_ids()
    decs = load_decisions()
    cands = load_candidates(set(decs))
    nb, nc = split_notes()

    # 组装批级文本单元
    units = []  # (batch_no, text, chapters)
    seen_chap_intro = set()
    for b in bats:
        bno = b["batch"]
        seg = batch2seg(ranges, bno) or "?"
        chaps = []
        for i in b["ids"]:
            ch = led[i].get("chapter")
            if ch not in chaps:
                chaps.append(ch)
        buf = [f"━━━ 批 {bno}｜章 {'/'.join(chaps)}｜P4段 {seg} ━━━"]
        # 章总述手记（该章首次出现的批之前）
        for ch in chaps:
            if ch not in seen_chap_intro and nc.get(ch):
                seen_chap_intro.add(ch)
                buf.append(f"◇◇ 译者手记（章 {ch} 总述） ◇◇")
                buf.extend(nc[ch])
        for i in b["ids"]:
            buf.append(fmt_line(i, led, fwd, chains, decs, cands, qids))
        for sec in nb.get(bno, []):
            buf.append(f"◇◇ 译者手记（批 {bno}） ◇◇")
            buf.append(sec)
        units.append((bno, "\n".join(buf) + "\n", chaps))

    # 贪心切块（批边界）
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    chunks = []
    cur, cur_chars, cur_meta = [], 0, {"batches": [], "chapters": []}
    for bno, text, chaps in units:
        if cur and cur_chars + len(text) > args.target_chars:
            chunks.append((cur, cur_chars, cur_meta))
            cur, cur_chars, cur_meta = [], 0, {"batches": [], "chapters": []}
        cur.append(text)
        cur_chars += len(text)
        cur_meta["batches"].append(bno)
        for c in chaps:
            if c not in cur_meta["chapters"]:
                cur_meta["chapters"].append(c)
    if cur:
        chunks.append((cur, cur_chars, cur_meta))

    manifest = []
    for n, (texts, chars, meta) in enumerate(chunks, 1):
        p = outdir / f"chunk-{n:02d}.md"
        head = (f"<!-- p5mine chunk {n}/{len(chunks)}｜批 {meta['batches'][0]}–{meta['batches'][-1]}"
                f"｜章 {'/'.join(meta['chapters'])} -->\n\n")
        p.write_text(head + "\n".join(texts), encoding="utf-8")
        manifest.append({"chunk": n, "file": p.name, "chars": chars,
                         "batches": [meta["batches"][0], meta["batches"][-1]],
                         "chapters": meta["chapters"]})
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # rulings 标题目录
    rl = POLISH / "seg7-e2" / "frozen" / "rulings.md"
    toc = [m.group(0) for m in re.finditer(r"(?m)^#{1,4} .*$", rl.read_text(encoding="utf-8"))]
    (outdir / "rulings-toc.md").write_text(
        "# 既有裁决台账（seg7 冻结累计版）标题目录\n\n" + "\n".join(toc) + "\n",
        encoding="utf-8")

    total = sum(c for _, c, _ in chunks)
    print(f"chunks: {len(chunks)}  total chars: {total}  avg: {total//len(chunks)}")
    for m in manifest:
        print(f"  {m['file']}  {m['chars']:>7}  批{m['batches'][0]}-{m['batches'][1]}  {'/'.join(m['chapters'])}")


if __name__ == "__main__":
    main()
