"""语义崩溃探测：check_batch 只管结构，拦不住"结构合法但语义垮掉"的批次，
而那种批次会成为后续所有批次的可信前缀。三条顾问级规则（不阻断流水线）：

  C1 残留假名——译文里出现（剔除术语表规定原样保留的片假名人名后的）假名，
     典型成因是整行原文照抄；这类行的长度比恰好正常，只有本规则抓得住。
  C2 中日长度比离群——译文相对原文过短/过长。
  C3 复读循环——行内子串连续重复，或同一句译文在批内重复出现。

阈值初值由已定稿语料实测得出（见 spec §6.3 与本文件常量注释），batch 1–2
硬停时用真实译文重新标定。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, WORK, dumps, read_jsonl

KANA_RE = re.compile(r"[぀-ゟ゠-ヿ]")
# 行内连续重复：长度≥4 的子串连续出现≥3 次（即总重复跨度≥12 字符）。
# 定值依据（控制器+评审实测三类语料对比，见 task-6-report.md 修复记录）：
# {2,}/{3,} 都会把视觉小说里合法的情绪表达（"哈哈哈哈哈哈""……………………"、
# 本作大量的"对不起对不起对不起""为什么为什么为什么"式三字/双字复读台词）
# 当作退化告警——顾问工具一旦大面积误报就等于被无视。{4,} 是唯一在退化
# 样本（LLM 复读循环，通常整句/长短语级）、视觉小说常见叠字表达、本作三字
# 情绪重复台词、120+194 条已定稿语料四类样本上都零误报、且仍 4/4 抓住退化
# 样本的取值。
LOOP_RE = re.compile(r"(.{4,}?)\1{2,}")

# 实测依据（skeleton/anchors.yaml 120 对 + cards.jp/zh 194 对已定稿语料）：
# zh/jp 字符比锚点 0.48–1.20（中位 0.85）、卡面 p5 0.62–p95 1.00 → 阈值取更宽的
# [0.40, 1.50]，保证已定稿水准的译文零误报；残留假名比定稿实测最大 0.0000 →
# 取 0.02 留余量。试点 batch 1–2 硬停时重新标定。
RATIO_LO = 0.40
RATIO_HI = 1.50
KANA_MAX = 0.02
# 批内完全相同且长度≥8 的译文出现≥3 次即视为复读
DUP_MIN_LEN = 8
DUP_MIN_COUNT = 3


def retained_names(glossary_path) -> set:
    """术语表 characters 中「原样保留」（zh == jp）且含假名的条目——这些假名
    是合法的，计算残留假名比前必须先剔除。
    作用域边界：只扫 characters 段，不扫 terms 段（当前 terms 里没有含假名
    的 zh，已核实）；若未来某版故意在 terms 保留片假名术语（如 コックリ
    さん），C1 会对它误报，届时需扩展本函数的扫描范围。"""
    import yaml
    doc = yaml.safe_load(Path(glossary_path).read_text(encoding="utf-8")) or {}
    return {c["jp"] for c in (doc.get("characters") or [])
            if c.get("zh") == c.get("jp") and KANA_RE.search(c.get("jp", ""))}


def _kana_ratio(zh: str, names) -> float:
    s = zh
    # 按长度降序替换：防止短名字（如「ユカリ」）先替换切碎长名字子串导致
    # 长名字剩余部分被误判为残留假名。
    for n in sorted(names, key=len, reverse=True):
        s = s.replace(n, "")
    return len(KANA_RE.findall(s)) / max(len(zh), 1)


def scan(source_rows, draft_rows, names=(), kana_max=KANA_MAX,
         ratio_lo=RATIO_LO, ratio_hi=RATIO_HI) -> list:
    src = {r["id"]: r["jp"] for r in source_rows}
    hits = []
    zh_counts = Counter(r["zh"] for r in draft_rows
                        if len(r["zh"]) >= DUP_MIN_LEN)
    for r in draft_rows:
        i, zh = r["id"], r["zh"]
        jp = src.get(i)
        if jp is None:
            continue
        kr = _kana_ratio(zh, names)
        if kr > kana_max:
            hits.append({"id": i, "rule": "C1",
                         "msg": f"残留假名比 {kr:.3f} > {kana_max}（疑似原文未译）"})
        ratio = len(zh) / max(len(jp), 1)
        if not (ratio_lo <= ratio <= ratio_hi):
            hits.append({"id": i, "rule": "C2",
                         "msg": f"中日长度比 {ratio:.2f} 越界 [{ratio_lo}, {ratio_hi}]"})
        if LOOP_RE.search(zh):
            hits.append({"id": i, "rule": "C3", "msg": "行内子串连续重复≥3 次"})
        elif zh_counts[zh] >= DUP_MIN_COUNT:
            hits.append({"id": i, "rule": "C3",
                         "msg": f"同一句译文在批内出现 {zh_counts[zh]} 次"})
    return hits


def _glossary_max(root: Path) -> Path:
    cands = [(int(re.search(r"v(\d+)", p.stem).group(1)), p)
             for p in (root / "glossary").glob("glossary.v*.yaml")]
    return max(cands)[1]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--lane-dir", default=None,
                    help="车道根；省略时用 pipelib.WORK 与仓库 glossary/")
    ap.add_argument("--kana-max", type=float, default=KANA_MAX)
    ap.add_argument("--ratio-lo", type=float, default=RATIO_LO)
    ap.add_argument("--ratio-hi", type=float, default=RATIO_HI)
    a = ap.parse_args(argv)
    work = Path(a.lane_dir) / "work" if a.lane_dir else Path(WORK)
    groot = Path(a.lane_dir) if a.lane_dir else Path(REPO)
    src = read_jsonl(work / "ctx" / f"batch_{a.batch}" / "source.jsonl")
    drf = read_jsonl(work / "out" / f"batch_{a.batch}.draft.jsonl")
    hits = scan(src, drf, names=retained_names(_glossary_max(groot)),
                kana_max=a.kana_max, ratio_lo=a.ratio_lo, ratio_hi=a.ratio_hi)
    out = work / "out" / f"batch_{a.batch}.collapse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(hits), encoding="utf-8")
    by_rule = Counter(h["rule"] for h in hits)
    print(f"batch_{a.batch}: 崩溃探测 {len(hits)} 条 "
          f"(C1={by_rule['C1']} C2={by_rule['C2']} C3={by_rule['C3']}) → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
