#!/usr/bin/env python3
"""用字难度扫描：找出译文里超出低龄读者字表的汉字，供 ruby 注音（`<汉字,pīn yīn>`）判定。

背景：`glossary/style.md`「绘本段」节要求用字限学龄前／小学低年级，不得已的生僻字用引擎 ruby
注汉语拼音。此前该判定纯靠译者眼力，实测会漏（b123 绘本段译者只扫出 4 个候选就收手，
自评「无一处需注音」，而实际文本里 囔/勒/渗/逞/漆/跺 等一批字都在表外）。本工具把判定机械化。

字表放在 `config/charlists/*.txt`（一行一字，`#` 开头为注释），来源见该目录 README。
默认闸门 = 义务教育「识字写字教学基本字表」300 ∪ GF 0025-2021 初等（一～三级）900，
合计约 1000 字量级，对应「刚上小学的孩子」口径（用户裁决 2026-08-04）。

用法：
  # 扫某批已入线译文里某个场景的用字
  python tools/check_charlevel.py --batch 123 --lane-dir pilot/lanes/opus --func scene_s3fc_90
  # 扫草稿
  python tools/check_charlevel.py --batch 123 --lane-dir pilot/lanes/opus --source draft
  # 换闸门 / 加白名单
  python tools/check_charlevel.py --batch 123 --lane-dir pilot/lanes/opus \
      --gate jiaoyu-changyong1-2500 --extra-known 妖怪

纯 stdlib，系统 python3（≥3.9）可直接跑。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARLIST_DIR = os.path.join(REPO, "config", "charlists")
DEFAULT_GATE = "jiaoyu-jibenzi-300,gf0025-chudeng-900"

# 引擎 ruby 标记：<汉字,注音>——base 段已注音的字视为已处置
RUBY_RE = re.compile(r"<([^<>,]+),([^<>,]+)>")
CJK_RE = re.compile(r"[一-鿿]")


def load_charlist(name: str) -> set[str]:
    path = os.path.join(CHARLIST_DIR, name if name.endswith(".txt") else name + ".txt")
    if not os.path.exists(path):
        avail = sorted(f[:-4] for f in os.listdir(CHARLIST_DIR) if f.endswith(".txt"))
        sys.exit(f"字表不存在：{path}\n可用字表：{', '.join(avail)}")
    out = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line)
    return out


def load_gate(spec: str) -> tuple[set[str], list[str]]:
    names = [n.strip() for n in spec.split(",") if n.strip()]
    known: set[str] = set()
    for n in names:
        known |= load_charlist(n)
    return known, names


def read_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def batch_ids(repo: str, batch: int, lane: str | None) -> list:
    path = os.path.join(repo, "data", "batches.jsonl")
    for row in read_jsonl(path):
        if row.get("batch") == batch and (lane is None or row.get("lane") == lane):
            return list(row["ids"])
    sys.exit(f"batches.jsonl 里没有 batch={batch}"
             + (f" lane={lane}" if lane else ""))


def load_zh(args, ids: set) -> dict:
    """取译文。source=forward 时后出现的行覆盖先出现的，再叠加 patches。"""
    zh = {}
    if args.source == "draft":
        path = os.path.join(args.lane_dir or ".", "work", "out",
                            f"batch_{args.batch}.draft.jsonl")
        for r in read_jsonl(path):
            zh[r["id"]] = r["zh"]
        return zh
    data_dir = os.path.join(args.lane_dir, "data") if args.lane_dir else os.path.join(REPO, "data")
    fwd = os.path.join(data_dir, "forward.jsonl")
    for r in read_jsonl(fwd):
        if not ids or r["id"] in ids:
            zh[r["id"]] = r["zh"]
    patches = os.path.join(data_dir, "patches.jsonl")
    if os.path.exists(patches):
        for r in read_jsonl(patches):
            if r["id"] in zh:
                zh[r["id"]] = r["zh"]
    return zh


def scan(zh: dict, known: set[str], extra: set[str]) -> dict:
    known = known | extra
    per_id = {}
    tok_total = tok_bad = 0
    uniq_all: Counter = Counter()
    uniq_bad: Counter = Counter()
    for i, text in zh.items():
        annotated = set()
        for m in RUBY_RE.finditer(text):
            annotated |= set(CJK_RE.findall(m.group(1)))
        bad = []
        for ch in CJK_RE.findall(text):
            uniq_all[ch] += 1
            tok_total += 1
            if ch in known or ch in annotated:
                continue
            bad.append(ch)
            uniq_bad[ch] += 1
            tok_bad += 1
        if bad:
            per_id[i] = sorted(set(bad), key=lambda c: -uniq_bad[c])
    return {
        "per_id": per_id,
        "uniq_total": len(uniq_all),
        "uniq_bad": len(uniq_bad),
        "tok_total": tok_total,
        "tok_bad": tok_bad,
        "lines_total": len(zh),
        "lines_bad": len(per_id),
        "bad_counter": uniq_bad,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描译文用字，列出超出低龄字表的汉字")
    ap.add_argument("--batch", type=int, help="批次号（与 --file 二选一）")
    ap.add_argument("--lane", default="main", help="batches.jsonl 的 lane 过滤，默认 main")
    ap.add_argument("--lane-dir", help="车道根，如 pilot/lanes/opus")
    ap.add_argument("--source", choices=["forward", "draft"], default="forward")
    ap.add_argument("--file", help="直接扫一个 jsonl（含 id/zh 字段）")
    ap.add_argument("--func", help="只看 ledger 里该 func 的行，如 scene_s3fc_90")
    ap.add_argument("--gate", default=DEFAULT_GATE,
                    help=f"闸门字表，逗号分隔，默认 {DEFAULT_GATE}")
    ap.add_argument("--extra-known", default="", help="额外视为已掌握的字（直接写字符串）")
    ap.add_argument("--json", dest="as_json", help="把明细写到该 json 文件")
    ap.add_argument("--top", type=int, default=40, help="终端最多列几个字")
    args = ap.parse_args()

    known, names = load_gate(args.gate)
    extra = set(CJK_RE.findall(args.extra_known))

    if args.file:
        zh = {r["id"]: r["zh"] for r in read_jsonl(args.file)}
    elif args.batch is not None:
        ids = set(batch_ids(REPO, args.batch, args.lane))
        zh = load_zh(args, ids)
        zh = {i: t for i, t in zh.items() if i in ids}
        missing = ids - set(zh)
        if missing:
            print(f"⚠ 有 {len(missing)} 个 id 在 {args.source} 里找不到译文", file=sys.stderr)
    else:
        sys.exit("须给 --batch 或 --file")

    if args.func:
        keep = set()
        for r in read_jsonl(os.path.join(REPO, "data", "ledger.jsonl")):
            if r.get("func") == args.func:
                keep.add(r["id"])
        zh = {i: t for i, t in zh.items() if i in keep}
        if not zh:
            sys.exit(f"--func {args.func} 在本批里没有命中任何 id")

    res = scan(zh, known, extra)
    scope = f"batch {args.batch}" if args.batch is not None else args.file
    if args.func:
        scope += f" / {args.func}"
    print(f"用字扫描：{scope}  闸门={'+'.join(names)}"
          + (f" +白名单{len(extra)}字" if extra else ""))
    print(f"  行数        {res['lines_bad']}/{res['lines_total']} 含表外字"
          f"  ({pct(res['lines_bad'], res['lines_total'])})")
    print(f"  不同汉字    {res['uniq_bad']}/{res['uniq_total']} 在表外"
          f"  ({pct(res['uniq_bad'], res['uniq_total'])})")
    print(f"  字符出现次数 {res['tok_bad']}/{res['tok_total']} 在表外"
          f"  ({pct(res['tok_bad'], res['tok_total'])})")
    if res["bad_counter"]:
        top = res["bad_counter"].most_common(args.top)
        print("  表外字（按出现次数）：")
        print("    " + "  ".join(f"{c}×{n}" for c, n in top))
        if len(res["bad_counter"]) > args.top:
            print(f"    …… 另有 {len(res['bad_counter']) - args.top} 字")

    if args.as_json:
        out = {
            "scope": scope,
            "gate": names,
            "extra_known": sorted(extra),
            "lines_total": res["lines_total"],
            "lines_bad": res["lines_bad"],
            "uniq_total": res["uniq_total"],
            "uniq_bad": res["uniq_bad"],
            "tok_total": res["tok_total"],
            "tok_bad": res["tok_bad"],
            "chars": [{"char": c, "count": n} for c, n in res["bad_counter"].most_common()],
            "per_id": {str(k): v for k, v in sorted(res["per_id"].items())},
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.as_json)) or ".", exist_ok=True)
        with open(args.as_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"  明细 → {args.as_json}")
    return 0


def pct(a: int, b: int) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


if __name__ == "__main__":
    sys.exit(main())
