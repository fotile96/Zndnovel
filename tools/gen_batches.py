"""timeline+ledger → data/batches.jsonl（main/extra/ambient 三车道）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl, write_jsonl


def plan(timeline, ledger_rows, extra_rows, budget_chars=9000):
    led = {r["id"]: r for r in ledger_rows}
    rows, cur_ids, cur_chars, cur_ch, cur_seqs = [], [], 0, None, set()

    def flush(reason):
        nonlocal cur_ids, cur_chars, cur_seqs
        if cur_ids:
            rows.append({"batch": -1, "lane": "main", "ids": cur_ids, "seqs": sorted(cur_seqs),
                         "jp_chars": cur_chars, "chapter": cur_ch, "cut_reason": reason})
            cur_ids, cur_chars, cur_seqs = [], 0, set()

    for ev in timeline:
        if ev["type"] == "marker":
            flush("branch")
            continue
        ch = led[ev["ids"][0]]["chapter"] if ev["ids"] else cur_ch
        if cur_ch is not None and ch != cur_ch:
            flush("chapter")
        cur_ch = ch
        current_seq = ev.get("seq")
        for i in ev["ids"]:
            n = len(led[i]["jp"])
            if cur_ids and cur_chars + n > budget_chars:
                flush("budget")
            # 重要不变量：任何批次的 ids ⊆ ⋃{ timeline[s].ids : s ∈ seqs }
            # 在添加 id 时确保该 unit 的 seq 已在 cur_seqs 里（无论是首次还是续批）
            if current_seq is not None:
                cur_seqs.add(current_seq)
            cur_ids.append(i)
            cur_chars += n
    flush("tail")

    # extra 车道：按 file 分组，计算真实 jp_chars
    by_file = {}
    for r in extra_rows:
        by_file.setdefault(r["file"], []).append(r)
    for f in sorted(by_file):
        keys_and_chars = [(r["key"], len(r["jp"])) for r in by_file[f]]
        total_chars = sum(c for _, c in keys_and_chars)
        rows.append({"batch": -1, "lane": "extra", "ids": [k for k, _ in keys_and_chars],
                     "seqs": [], "jp_chars": total_chars, "chapter": f, "cut_reason": "extra"})

    # ambient 车道：按 (file, func) 分组，贪心装批（同组不跨批，除非单组超预算）
    by_filefunc = {}
    for r in ledger_rows:
        if r["kind"] != "ambient":
            continue
        key = (r["file"], r["func"])
        by_filefunc.setdefault(key, []).append((r["id"], len(r["jp"])))

    amb_groups = []
    for key in sorted(by_filefunc.keys()):
        group_ids = [gid for gid, _ in by_filefunc[key]]
        group_chars = sum(c for _, c in by_filefunc[key])
        amb_groups.append((group_ids, group_chars))

    cur_amb, cur_amb_chars = [], 0
    for group_ids, group_chars in amb_groups:
        # 同组尽量不跨批
        if cur_amb and cur_amb_chars + group_chars > budget_chars:
            rows.append({"batch": -1, "lane": "ambient", "ids": cur_amb, "seqs": [],
                         "jp_chars": cur_amb_chars, "chapter": "sys", "cut_reason": "budget"})
            cur_amb, cur_amb_chars = [], 0
        # 将该组加入当前批（即便单组超预算也一次性加入，符合"允许在组内切"的实现）
        cur_amb.extend(group_ids)
        cur_amb_chars += group_chars

    if cur_amb:
        rows.append({"batch": -1, "lane": "ambient", "ids": cur_amb, "seqs": [],
                     "jp_chars": cur_amb_chars, "chapter": "sys", "cut_reason": "tail"})

    for n, r in enumerate(rows, 1):
        r["batch"] = n
    return rows


def main():
    tl = read_jsonl(DATA / "timeline.jsonl")
    led = read_jsonl(DATA / "ledger.jsonl")
    extra = read_jsonl(DATA / "ledger_extra.jsonl")
    rows = plan(tl, led, extra)
    write_jsonl(DATA / "batches.jsonl", rows)
    lanes = {}
    for r in rows:
        lanes[r["lane"]] = lanes.get(r["lane"], 0) + 1
    print("batches:", len(rows), lanes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
