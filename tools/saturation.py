"""词族饱和度：全书 ledger 中某日文词的出现次数里，已被译过批次覆盖的比例。
段末小裁决的证据闸门（P3 spec §2）：ratio >= gate 才允许裁决，否则聚类滚存。
读 DATA/ledger.jsonl（+ ledger_extra.jsonl 若存在）与 resolve_map（forward+patches）。

`is_clean_key`（连同 ASCII_RE/WORDCHAR_RE/corpus_chars_from_ledger）本来长在
tools/cluster_notes.py 里，随 P3 devwave1 一起搬到这里：它回答的问题是「这个
词键值不值得拿去 count」，这在语义上属于饱和度这一层——不是卷宗渲染层的事。
`cluster_notes.py` 与本文件的 `main()` 都要用同一份判据（此前只有 cluster_notes
有这道判据，saturation.py 自己的 main() 没有，于是同一个「脏键→伪装成 0/0
正常词族」的误读能从这道门直接进来），两个消费方共用一份判据才不会再分家；
若反过来让本文件导入 cluster_notes 就是循环导入（cluster_notes 已经
`from tools.saturation import saturation`）。"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl
from tools.resolve import resolve_map

ASCII_RE = re.compile(r"[0-9A-Za-z]")
# 假名或汉字——词键至少得有一个「字」。`★【（ヒント）】→【（提示）】` 被括号注
# 规则吃掉内容后只剩 `【】`，那是标点不是词。
WORDCHAR_RE = re.compile(r"[぀-ゟァ-ヺヽ-ヿ々一-鿿]")

# main() 与 cluster_notes.main() 共用同一句措辞：脏键判定不是「无出现」而是
# 「没匹配到」——docs/ops/p3-production-runbook.md §5 第 2 步引用的正是这句，
# 两处都从这个常量取值，避免文案改动只改了一处（见 test_saturation.py 里
# 校验 runbook 文案与本常量一致的回归测试）。
DIRTY_KEY_VERDICT = "未匹配到该词键（可能提取不干净，请人工核对）"

# 并列词串探测（main() 专用，不改动 is_clean_key 的判据/五案例）：段末裁决
# 手抄词表时若整串抄了「はい／いいえ」这类并列词，is_clean_key 逐字检查会
# 放行它——并列分隔符本身可能就出现在语料标点里（全角 ／ 就在游戏原文中，
# 半角 / 不在），于是"分隔符是不是语料内字符"这个纯粹的巧合决定了这个键被判
# clean 还是 dirty；判 clean 时 total==0 会被读成「无出现、可以随便定」，
# 判 dirty 时读成「未匹配到该词键」——两种读法都不对，因为 はい 单独查是
# 396 次、いいえ 是 18 次：这正是当初那个 Critical 的头号例子，绝不能再从
# 这道门进来。main() 另开一道探测，不依赖 is_clean_key：total==0 时按常见
# 并列分隔符（全角／半角斜杠、顿号、竖线）拆开，只要有一个子串 total>0，
# 就说明这键极可能是被误抄成一整块的并列词，直接把各子串的真实证据摆出来，
# 不再报「无出现」或「未匹配」。
COMPOUND_SPLIT_RE = re.compile(r"[/／、|｜]")
COMPOUND_VERDICT_PREFIX = "疑似并列词串，请拆开分别查"


def split_compound_candidates(term: str) -> list:
    """把 term 按常见并列分隔符拆开，返回非空子串列表；不含分隔符（或拆完
    只剩一段）时返回空列表，表示"不是并列词串"。"""
    parts = [p.strip() for p in COMPOUND_SPLIT_RE.split(term)]
    parts = [p for p in parts if p]
    return parts if len(parts) > 1 else []


def corpus_chars_from_ledger(ledger_rows) -> set:
    """从 ledger 的 jp 字段构造语料字符集：全书日文原文里实际出现过的字符。
    is_clean_key 用它判断词键里是否混入语料里根本不存在的字符（简体中文字、
    裸 ASCII id 数字等）——那种字符不可能是本作的日文词。"""
    chars = set()
    for r in ledger_rows:
        chars.update(r.get("jp", ""))
    return chars


def is_clean_key(key: str, corpus_chars: set, total: int) -> bool:
    """这个词键看起来像「本作里真实存在的日文词」吗？

    存在的意义：饱和度 0/0 有两种完全相反的含义——①这个词在全书原文里确实一次
    也没出现（证据为零，可放心另定）②**词键根本没提干净**，拿一串残渣去 count
    当然是 0。二者外观相同，而卷宗此前把两者一律写成「无出现」，于是「はい／
    いいえ」「首译定名：意識」这类脏键被读成「原文没这词」，真词 はい 396 次、
    意識 55 次（其中 10 个脏键的真词 ratio 甚至是 1.000、闸门本该当场放行）。

    判据用的是**语料本身**而不是拍脑袋的字符表：ledger 的 jp 字段就是全书日文
    原文，凡是键里出现语料中根本不存在的字符（简体中文字、空白、裸 ASCII id
    数字），这个键就不可能是本作的日文词。不干净的键一律降级进「（未归词）」——
    宁可明确待人工过目，也不要伪装成正常词族输出一个 0/0（task-1 修复确立的
    原则，此处一致适用）。

    `total > 0` 短路（P3 devwave1 复评 Important 2 收窄版——只对**部分**判据成立，
    不能整体跳过）：`total > 0` 意味着这个键逐字命中了 ledger 里的原文，对
    whitespace／WORDCHAR（至少一个假名或汉字）／语料外字符／长键零出现这四条
    判据而言，歧义确实不存在了——它们要分辨的正是「0/0 是无出现还是没提干净」，
    键既然有大于 0 的命中，这个问题已经有答案，不该再被外观判据错杀
    （`いつか きみが みる お話。` 带空格是绘本标题原文如此；`ＴｒｕｅＣｏｌｕｒ`
    全角拉丁也是原文书写形态，两者 total>0）。

    但 **ASCII_RE 这一条不在短路范围内，是硬门，`total` 多大都不豁免**：它防的
    是另一类脏键——纯 ASCII/数字/半角标点的提取残渣（裸 id 号、误吞的英文菜单
    残片）。这类键完全可能 `total > 0` 而依然不是词：ledger 里混有半角数字组成
    的时间/年龄表达（`17歳`「12時」「14分15秒」）甚至个别源码泄漏行，子串
    `"12"` 在 ledger 里就能测出 `total=1`（命中「12時」）——若也豁免它，`12` 这种
    一个字都不是词的裸 id 键会被判 clean、当成正常词族渲染进卷宗。「逐字命中
    语料 ⇒ 歧义不存在」这条论证只对「含语料外字符」那一条成立（因为该判据本身
    就是用「有没有出现在语料」来判定，与 total 的定义同源）；ASCII 门判的是
    「这个键像不像日文词」，与它是否出现在语料里是两件事，因此不能用同一个
    `total > 0` 去豁免。"""
    if not key:
        return False
    if ASCII_RE.search(key):
        return False
    if total > 0:
        return True
    if any(ch.isspace() for ch in key):
        return False
    if not WORDCHAR_RE.search(key):
        return False
    if any(ch not in corpus_chars for ch in key):
        return False
    if len(key) > 8:
        # 长键 + 零出现：即便逐字都是语料里的字，也更可能是被当成词键的整句
        # 描述（如「千秋口中的彩野さん」），交人工。
        return False
    return True


def saturation(term: str, ledger_rows, done_ids) -> dict:
    total = covered = 0
    uncov = Counter()
    for r in ledger_rows:
        n = r.get("jp", "").count(term)
        if not n:
            continue
        total += n
        # 优先用 id，备选 key（ledger_extra.jsonl 格式）
        rid = r.get("id") if "id" in r else r.get("key")
        if rid is None:
            continue
        if rid in done_ids:
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
    ledger_path = data / "ledger.jsonl"
    ledger = read_jsonl(ledger_path) if ledger_path.exists() else []
    extra = data / "ledger_extra.jsonl"
    if extra.exists():
        ledger += read_jsonl(extra)
    # 「已入线译文」为空是本工具唯一的失败开方向：漏传 --data-dir 时 DATA 落到
    # 仓库根 data/（那里没有车道 forward.jsonl），输出一张全列 0.000/「滚存」的
    # 完全合理的表——闸门失效却毫无痕迹（终审 I2；runbook 里那条命令还是折行
    # 两行、极易漏抄第二行）。故：表头前自述统计口径，forward 缺失时醒目告警。
    fwd_path, pat_path = data / "forward.jsonl", data / "patches.jsonl"
    missing_forward = not fwd_path.exists()
    fwd = read_jsonl(fwd_path) if not missing_forward else []
    pat = read_jsonl(pat_path) if pat_path.exists() else []
    done = set(resolve_map(fwd, pat))
    rows = [saturation(t, ledger, done) for t in terms]

    # 脏键判据（见 is_clean_key）：同一个「误读」此前只在 cluster_notes.py 里被
    # 挡住——saturation.py 自己的 main() 没有这道门，手抄词表带一点残渣、或从
    # 别处取词，就又能把「词键没提干净」读成「原文里没这词」。语料字符集与
    # cluster_notes 同源（都来自本次 ledger 的 jp 字段）。
    corpus_chars = corpus_chars_from_ledger(ledger)
    for r in rows:
        r["clean"] = is_clean_key(r["term"], corpus_chars, r["total"])
        # 并列词串探测（见 COMPOUND_SPLIT_RE 处注释）：只在 total==0 时才有
        # 意义——整词本身已有命中就不存在「被并列串掩盖了证据」的问题。
        r["compound"] = None
        if r["total"] == 0:
            cands = split_compound_candidates(r["term"])
            if cands:
                sub = [(c, saturation(c, ledger, done)) for c in cands]
                if any(s["total"] > 0 for _, s in sub):
                    r["compound"] = sub

    def _rank(r):
        # 有真实 ratio 的行最先看；「疑似并列词串」次之（有证据但需要拆开）；
        # 「无出现」（干净但零出现）再次之；脏键（未匹配到该词键）殿后。
        if r["compound"] is not None:
            cat = 1
        elif not r["clean"]:
            cat = 3
        elif r["ratio"] is None:
            cat = 2
        else:
            cat = 0
        return (cat, r["ratio"] if r["ratio"] is not None else 0)

    rows.sort(key=_rank)
    print(f"done={len(done)} 条已入线译文（data-dir={data}）")
    if missing_forward:
        print(f"!! 告警：{fwd_path} 不存在——本次按「零条已译」计算，全部词族必然"
              f"判为「滚存」，闸门等于失效。是否漏传 --data-dir？"
              f"（车道数据在 pilot/lanes/<lane>/data）")
    if not ledger:
        print(f"!! 告警：{ledger_path} 没读到或为空（0 条记录）——corpus_chars 语料"
              f"字符集随之为空集，is_clean_key 的「含语料外字符」判据对任何键都"
              f"成立，于是全部词键将被判脏（{DIRTY_KEY_VERDICT}），饱和度判定"
              f"不可用。这不是「这些词都没出现」，是数据源没读到。请确认 "
              f"--data-dir 指对了车道 data 目录、且该车道已跑过 build_ledger。")
    print("| 词 | 出现 | 已覆盖 | 饱和度 | 判定 | 未覆盖分布 |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if r["compound"] is not None:
            parts_str = "、".join(
                f"{c}={s['covered']}/{s['total']}"
                + (f"={s['ratio']:.3f}" if s["ratio"] is not None else "")
                for c, s in r["compound"])
            verdict, ratio_s = f"{COMPOUND_VERDICT_PREFIX}（{parts_str}）", "-"
        elif not r["clean"]:
            verdict, ratio_s = DIRTY_KEY_VERDICT, "-"
        elif r["ratio"] is None:
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
