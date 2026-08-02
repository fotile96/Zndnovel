"""语义崩溃探测：check_batch 只管结构，拦不住"结构合法但语义垮掉"的批次，
而那种批次会成为后续所有批次的可信前缀。三条顾问级规则（不阻断流水线）：

  C1 残留假名——译文里出现（剔除术语表规定原样保留的片假名人名后的）假名，
     典型成因是整行原文照抄；这类行的长度比恰好正常，只有本规则抓得住。
  C2 中日长度比离群——译文相对原文过短/过长。
  C3 复读循环——行内子串连续重复，或同一句译文在批内重复出现；两个半边都
     **以原文的重复程度为基线**，只报「译文比原文更重复」的行（见 C3 一节）。

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

# v2（F12）：片假名段起点从 ゠(U+30A0) 收窄到 ァ(U+30A1)、止于 ヺ(U+30FA)，
# 再补 ヽ-ヿ；即剔除 ゠(U+30A0)/・(U+30FB)/ー(U+30FC) 三个片假名标点——它们
# 不是假名，此前误把项目符号「・」「ー」等计入残留假名比（P2 batch 31 实测
# 4/6 行因 ・ 误报）。
# 已知遗留（评审记账，暂不处理）：
#   - 平假名段 ぀-ゟ 仍含 U+3099/309A（浊/半浊音结合符）与 309B゛/309C゜
#     （非结合形式的浊/半浊音符）、309D゛/309E゛（假名重复符ゝ/ゞ）；这些
#     不是"假名"本身但混在区间里，与片假名侧已单独摘除标点的处理不对称。
#     实务影响极小（正文极少单独出现这几个码位），故不动正则，仅记录。
#   - 剔除 ー(U+30FC) 会让"未译的长音片假名词"（如 スーパー）少计 1/3 的
#     假名字符，残留假名比相应偏低、C1 灵敏度略降；方向与本次 F12 的目标
#     （不把标点当假名）一致，代价可接受，此处留痕。
KANA_RE = re.compile(r"[぀-ゟァ-ヺヽ-ヿ]")
# ── C3 判据（v2，F4 重做）─────────────────────────────────────────────
# 原则：**拿译文的重复程度对比原文的重复程度**。原文自己就重复到同样程度的，
# 是忠实翻译；只有译文比原文更重复才可疑。
# 重做动机（SEG-1 b36–62 实测）：旧判据只看译文，该段 53 条 collapse 里 C3 占
# 46 条（87%），逐条核查后 43 条（93%）是「原文在分支重演里本就以同样次数重复、
# 译者给出同样译文」的纯误报；行内重复那半边全库 6278 行只命中 1 条（id 6242
# 「ぱつ、_nぱつ、_nぱつ、_n」→「啪嗒、_n啪嗒、_n啪嗒、_n」），同样是拟声词的
# 忠实复现。顾问工具一旦这种比例的误报，人就不再看它了。
#
# 行内重复的对比方式（为什么不能比子串本身）：原文与译文的重复单元必然字面不同
# （「ぱつ、」↔「啪嗒、」），无从对齐；所以比的是**重复这一性质的强度**——两侧
# 各取「任一子串连续重复的最大次数」（`_max_repeat_run`），仅当 zh 的最大次数
# **严格大于** jp 的最大次数才报。取「次数」而非「有无」，是为了仍能抓住"原文
# 重复 3 次、译文滚成 8 次"的放大型退化（要求 2：不得削弱对真退化的探测）。
# 两侧的最小单元长度**故意不同**：
#   - zh 侧沿用 4（LOOP_RE，见下方定值依据），它决定「这行值不值得考察」；
#   - jp 侧放宽到 2（JP_LOOP_MIN_UNIT），它只决定「原文是否也在重复」。原文的
#     重复单元可能比译文短（拟声词「ぺた」、应答「はい、」），若两侧同用 4，
#     原文侧会系统性漏检"原文本就重复"，对比也就形同虚设。
#     标定（6278 行已入线原文实测）：max_run≥3 的行占比 min_unit=1 → 0.99%、
#     2 → 0.11%、3 → 0.03%、4 → 0.02%。取 1 会把「……………………」这类省略号/
#     长音连排整片判成"原文重复"（近 1% 的行成为盲区，且正是译文合法镜像的
#     地方）；取 2 只让 0.11% 的原文行获得豁免资格，盲区可忽略。
#     方向性偏差是有意的：顾问工具成本非对称——把"原文本身就重复"判宽一点，
#     最多少报一条本就忠实的行；反之（43 条误报）会让整个规则被无视。
#
# 行内连续重复（zh 侧门槛）：长度≥4 的子串连续出现≥3 次（即总重复跨度≥12 字符）。
# 定值依据（控制器+评审实测三类语料对比，见 task-6-report.md 修复记录）：
# {2,}/{3,} 都会把视觉小说里合法的情绪表达（"哈哈哈哈哈哈""……………………"、
# 本作大量的"对不起对不起对不起""为什么为什么为什么"式三字/双字复读台词）
# 当作退化告警——顾问工具一旦大面积误报就等于被无视。{4,} 是唯一在退化
# 样本（LLM 复读循环，通常整句/长短语级）、视觉小说常见叠字表达、本作三字
# 情绪重复台词、120+194 条已定稿语料四类样本上都零误报、且仍 4/4 抓住退化
# 样本的取值。
ZH_LOOP_MIN_UNIT = 4
JP_LOOP_MIN_UNIT = 2
LOOP_RE = re.compile(r"(.{4,}?)\1{2,}")   # ≡ _max_repeat_run(zh, ZH_LOOP_MIN_UNIT) >= 3


def _max_repeat_run(s: str, min_unit: int) -> int:
    """s 中任一长度≥min_unit 的子串「连续重复」的最大次数（无重复时为 1）。
    只在 LOOP_RE 已命中（全库 6278 行仅 1 行）时才调用，故 O(n²) 可接受。"""
    best, n = 1, len(s)
    for L in range(min_unit, n // 2 + 1):
        for i in range(n - 2 * L + 1):
            u, k, j = s[i:i + L], 1, i + L
            while s[j:j + L] == u:
                k, j = k + 1, j + L
            best = max(best, k)
    return best

# 实测依据（skeleton/anchors.yaml 120 对 + cards.jp/zh 194 对已定稿语料）：
# zh/jp 字符比锚点 0.48–1.20（中位 0.85）、卡面 p5 0.62–p95 1.00 → 阈值取更宽的
# [0.40, 1.50]，保证已定稿水准的译文零误报；残留假名比定稿实测最大 0.0000 →
# 取 0.02 留余量。试点 batch 1–2 硬停时重新标定。
RATIO_LO = 0.40
RATIO_HI = 1.50
KANA_MAX = 0.02
# 批内同句的**纳入门槛**：完全相同且长度≥8 的译文出现≥3 次才进入考察；
# 纳入后还须过「zh 出现次数 > 对应 jp 出现次数」这一关（v2）。本作大量场景在
# 分支重演里原样重播同一句台词，同一批内原文重复 3–5 次是常态而非退化。
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


# F9：作品内引用的日文原文（钱仙拼字、五十音教学等）在译文中合法保留假名。
# 判据（三重门槛，逐条收紧，任一不过则不豁免）：
#   1) zh != jp 廉价短路——整行未译时 zh 与 jp 逐字相同，直接跳过豁免。
#      注意：这道短路本身**不足以防住"近似复制"伪装**（二轮评审实测：把
#      jp 逐字复制后只在句尾加一个「。」，或把日文标点换成中文标点，就能
#      让 zh != jp 成立、从而放行下面的逐段豁免，最终把残留假名比整体洗
#      成 0——漏报率高达 63.7%），必须叠加判据 2/3 才成立防线。
#   2) 预算：被豁免的假名字符总数 / len(zh) ≤ JP_QUOTE_BUDGET——防止豁免
#      机制替整行"背书"。一旦被豁免的假名占了译文相当比例，这行更可能是
#      "近似复制的整行漏译"而非"作品内引用"。
#   3) 换新：zh 中「jp 里根本不存在的字符」占比 ≥ JP_QUOTE_MIN_NOVEL——要求
#      确有翻译动作发生的实证据，而不只是动了一个标点。
# 长串（单个连段 > JP_QUOTE_MAX_LEN）本身即不进入豁免候选，不受判据 2/3 影响
# ——整行未译（zh≈jp）正是 C1 的目标，不因预算/换新达标而破例。
# JP_QUOTE_BUDGET=0.40、JP_QUOTE_MIN_NOVEL=0.05 标定依据：P3 devwave1
# task-2 二轮实测（1–35 批 4282 行真实译文 + 全 ledger 16101 行含假名原文
# 构造的"复制+句尾加句号"伪装集，见 task-2-report.md 标定表）——0.32/0.40/
# 0.50 三档对真实译文的 C1 命中数（成本）相同均为 4（零新增误报）；已知
# 合法豁免占比最高的真实样本为 0.316（batch19 id8300），0.32 对它只有 1.3%
# 余量太薄，0.40 有 ≥25% 相对余量且对伪装集的漏报率仍优于 0.50（13.1% vs
# 18.0%，越低越好），故取 0.40。
JP_QUOTE_MAX_LEN = 6
JP_QUOTE_BUDGET = 0.40
JP_QUOTE_MIN_NOVEL = 0.05
KANA_RUN_RE = re.compile(r"[぀-ゟァ-ヺヽ-ヿ]+")


def _kana_ratio(zh: str, names, jp: str = "") -> float:
    s = zh
    # 按长度降序替换：防止短名字（如「ユカリ」）先替换切碎长名字子串导致
    # 长名字剩余部分被误判为残留假名。
    for n in sorted(names, key=len, reverse=True):
        s = s.replace(n, "")
    if jp and zh != jp:
        runs = [m.group() for m in KANA_RUN_RE.finditer(s)
                if len(m.group()) <= JP_QUOTE_MAX_LEN and m.group() in jp]
        novel = sum(1 for c in zh if c not in jp) / max(len(zh), 1)
        if (sum(map(len, runs)) <= JP_QUOTE_BUDGET * len(zh)
                and novel >= JP_QUOTE_MIN_NOVEL):
            s = KANA_RUN_RE.sub(
                lambda m: "" if len(m.group()) <= JP_QUOTE_MAX_LEN and m.group() in jp
                else m.group(), s)
    return len(KANA_RE.findall(s)) / max(len(zh), 1)


def scan(source_rows, draft_rows, names=(), kana_max=KANA_MAX,
         ratio_lo=RATIO_LO, ratio_hi=RATIO_HI,
         dup_min_len=DUP_MIN_LEN, dup_min_count=DUP_MIN_COUNT) -> list:
    src = {r["id"]: r["jp"] for r in source_rows}
    hits = []
    # 两个计数器必须建在**同一批行**上（有对应原文的那些），否则 zh/jp 次数不可比。
    paired = [r for r in draft_rows if r["id"] in src]
    zh_counts = Counter(r["zh"] for r in paired)
    jp_counts = Counter(src[r["id"]] for r in paired)
    for r in draft_rows:
        i, zh = r["id"], r["zh"]
        jp = src.get(i)
        if jp is None:
            continue
        kr = _kana_ratio(zh, names, jp)
        if kr > kana_max:
            hits.append({"id": i, "rule": "C1",
                         "msg": f"残留假名比 {kr:.3f} > {kana_max}（疑似原文未译）"})
        ratio = len(zh) / max(len(jp), 1)
        if not (ratio_lo <= ratio <= ratio_hi):
            hits.append({"id": i, "rule": "C2",
                         "msg": f"中日长度比 {ratio:.2f} 越界 [{ratio_lo}, {ratio_hi}]"})
        # C3 上半：行内重复。译文的最大连续重复次数须严格超过原文的，才算可疑
        # ——原文自己就重复到同样次数时（拟声词「ぱつ、ぱつ、ぱつ」）是忠实翻译。
        looped = False
        if LOOP_RE.search(zh):
            zr = _max_repeat_run(zh, ZH_LOOP_MIN_UNIT)
            jr = _max_repeat_run(jp, JP_LOOP_MIN_UNIT)
            if zr > jr:
                looped = True
                hits.append({"id": i, "rule": "C3",
                             "msg": f"行内子串连续重复 {zr} 次，而对应原文最多"
                                    f"只连续重复 {jr} 次"})
        # C3 下半：批内同句。同理，仅当译文的批内重复次数超过其原文的批内重复
        # 次数时才报——次数相等意味着"相同原文给出相同译文"，是忠实而非复读。
        # 两个次数都写进消息，让人一眼看出可疑点在哪（次数相同则根本不到这里）。
        if (not looped and len(zh) >= dup_min_len
                and zh_counts[zh] >= dup_min_count
                and zh_counts[zh] > jp_counts[jp]):
            hits.append({"id": i, "rule": "C3",
                         "msg": f"同一句译文在批内出现 {zh_counts[zh]} 次，"
                                f"而对应原文只出现 {jp_counts[jp]} 次"})
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
    ap.add_argument("--dup-min-len", type=int, default=DUP_MIN_LEN)
    ap.add_argument("--dup-min-count", type=int, default=DUP_MIN_COUNT)
    a = ap.parse_args(argv)
    work = Path(a.lane_dir) / "work" if a.lane_dir else Path(WORK)
    groot = Path(a.lane_dir) if a.lane_dir else Path(REPO)
    src = read_jsonl(work / "ctx" / f"batch_{a.batch}" / "source.jsonl")
    drf = read_jsonl(work / "out" / f"batch_{a.batch}.draft.jsonl")
    hits = scan(src, drf, names=retained_names(_glossary_max(groot)),
                kana_max=a.kana_max, ratio_lo=a.ratio_lo, ratio_hi=a.ratio_hi,
                dup_min_len=a.dup_min_len, dup_min_count=a.dup_min_count)
    out = work / "out" / f"batch_{a.batch}.collapse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(hits), encoding="utf-8")
    by_rule = Counter(h["rule"] for h in hits)
    print(f"batch_{a.batch}: 崩溃探测 {len(hits)} 条 "
          f"(C1={by_rule['C1']} C2={by_rule['C2']} C3={by_rule['C3']}) → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
