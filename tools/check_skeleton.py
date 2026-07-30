"""骨架 YAML 机械校验。用法见 --help。

- --range A-B 规定本批应覆盖的卡号（variant "a" 计数）；
- --extra N[,M…] 追加编外卡号（如 200）；
- 范围外的条目（如卡 0 的空白模板记录行）不做字段检查、不计覆盖。
"""
import argparse
import sys
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from tools.pipelib import display_width  # P1a 落地后共享同一实现
except ImportError:
    def display_width(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in "FWA" else 1 for c in s)


def load(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--jp"); ap.add_argument("--zh"); ap.add_argument("--against")
    ap.add_argument("--range", required=True)
    ap.add_argument("--extra", default="")
    args = ap.parse_args(argv)
    lo, hi = (int(x) for x in args.range.split("-"))
    want = set(range(lo, hi + 1))
    if args.extra:
        want |= {int(x) for x in args.extra.split(",")}
    errs = []
    if args.jp:
        rows = [r for r in load(args.jp) if r.get("card") in want]
        got = {r["card"] for r in rows if r.get("variant", "a") == "a"}
        if got != want:
            errs.append(f"jp 卡号缺漏: 缺{sorted(want-got)} 多{sorted(got-want)}")
        for r in rows:
            for k in ("card", "variant", "title_jp", "section_label", "body_jp", "note"):
                if k not in r:
                    errs.append(f"card {r.get('card')}: 缺字段 {k}")
            if not r.get("title_jp"):
                errs.append(f"card {r.get('card')}: title_jp 为空")
    if args.zh:
        zh = [r for r in load(args.zh) if r.get("card") in want]
        jp = load(args.against)
        jpk = {(r["card"], r.get("variant", "a")) for r in jp if r.get("card") in want}
        zhk = {(r["card"], r.get("variant", "a")) for r in zh}
        if zhk != jpk:
            errs.append(f"zh/jp 不对应: 缺{sorted(jpk-zhk)} 多{sorted(zhk-jpk)}")
        for r in zh:
            if not r.get("title_zh") or not r.get("body_zh"):
                errs.append(f"card {r['card']}: 译文字段为空")
            elif display_width(r["title_zh"]) > 28:
                errs.append(f"card {r['card']}: title_zh 超 14 汉字宽")
    print("\n".join(errs) if errs else "OK")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
