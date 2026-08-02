"""提案预聚类：把车道 notes/*.md 的散条提案按词族聚合成裁决卷宗（P3 spec §2/§4）。
段末小裁决会话的输入整理器——聚合跨批/跨章的同词提案，并对每个词族附
saturation 饱和度判定（≥gate 可裁决，否则滚存）。只读，不改任何 notes 文件。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import read_jsonl
from tools.resolve import resolve_map
# is_clean_key（连同 ASCII_RE/WORDCHAR_RE/corpus_chars_from_ledger/脏键措辞）已
# 搬去 tools/saturation.py（P3 devwave1）：判据本身回答的是「这个词键值不值得
# 拿去 count」，语义上属于饱和度这一层，不是卷宗渲染层的事；saturation.py 的
# main() 现在也用同一份判据挡同一个误读，两个消费方共用一份才不会再分家。
from tools.saturation import (saturation, is_clean_key,
                               corpus_chars_from_ledger, DIRTY_KEY_VERDICT)

# 批次标题实况是 `## batch 33（scene_s2s_40「また、いつもの生活」＋ …）`——原先
# 的 `\s*$` 锚死行尾，opus 车道 16 个带括注的标题全部失配，其后的提案要么丢批号
# 要么**挂到上一个能匹配的批号上**（后者外观正常却是错的，裁决会话无从察觉）。
BATCH_RE = re.compile(r"^## batch (\d+)")
PROP_RE = re.compile(r"^### (\d+)\.\s*(.+)$")
# 标题里包裹词项的装饰：markdown 粗体、反引号、日式/强调引号、括号注（含
# (7302) 这类 id 注）。≪≫/≦≧ 是本作正文的强调括号，出现在词项两侧时同样是装饰。
STRIP_RE = re.compile(r"\*\*|[`『』「」≪≫≦≧]|[（(][^）)]*[）)]")
# 描述性冒号前缀：「首译定名：意識」「建议入 active.json：デジャブ」「登记：分岐」
# ——冒号左边是提案者的分类标签、不是词。限长 20 字免得把正文里的冒号也当前缀。
DESC_PREFIX_RE = re.compile(r"^[^：:]{0,20}[：:]\s*")
# 并列分隔符：半角 / 与**全角 ／**（`はい／いいえ` 这类实况原先整串留在键里）。
SPLIT_RE = re.compile(r"[/／]")
UNKEYED = "（未归词）"


def extract_terms(title: str) -> list:
    t = re.sub(r"^\d+\.\s*", "", title)
    if t.count("→") != 1:
        # 0 个 → 无词项；>1 个 → 顿号分隔的多词小族，不做多词解析（brief
        # 明确不扩展），直接归未归词待人工过目，避免第一段箭头前文本被
        # 误当成唯一词键、伪装成正常词族并跑出虚假的「无出现」饱和度。
        return []
    left = DESC_PREFIX_RE.sub("", STRIP_RE.sub("", t.split("→", 1)[0]).strip())
    return [w.strip() for w in SPLIT_RE.split(left.replace("★", "")) if w.strip()]


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
    md_files = sorted((data / "notes").glob("*.md"))
    for p in md_files:
        props += parse_notes(p.read_text(encoding="utf-8"), p.stem)
    ledger_path = data / "ledger.jsonl"
    ledger = read_jsonl(ledger_path) if ledger_path.exists() else []
    extra = data / "ledger_extra.jsonl"
    if extra.exists():
        ledger += read_jsonl(extra)
    fwd_path = data / "forward.jsonl"
    fwd = read_jsonl(fwd_path) if fwd_path.exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    done = set(resolve_map(fwd, pat))
    c = cluster(props)

    # 脏键降级（见 is_clean_key）：先算饱和度，再判键干净与否，脏键整簇并进未归词。
    corpus_chars = corpus_chars_from_ledger(ledger)
    sats, demoted = {}, []
    for key in [k for k in c if k != UNKEYED]:
        s = saturation(key, ledger, done)
        if is_clean_key(key, corpus_chars, s["total"]):
            sats[key] = s
            continue
        demoted.append(key)
        bucket = c.setdefault(UNKEYED, [])
        seen = {id(x) for x in bucket}
        bucket += [p for p in c.pop(key) if id(p) not in seen]

    lines = [f"# 术语提案裁决卷宗（{lane.name} 车道，共 {len(props)} 条提案 / {len(c)} 个词族）",
             "",
             f"> 扫描 {len(md_files)} 个 notes/*.md；{len(sats)} 个成词词族、"
             f"{len(c.get(UNKEYED, []))} 条未归词（含 {len(demoted)} 个提取不干净被降级的键）。",
             ""]
    def _order(item):
        # 多提案词族在前（跨批冲突优先裁），未归词殿后
        key, ps = item
        return (key == UNKEYED, -len(ps), key)
    for key, ps in sorted(c.items(), key=_order):
        if key == UNKEYED:
            head = f"## {UNKEYED}（{len(ps)} 条，逐条人工过目）"
        else:
            s = sats[key]
            # 「无出现」曾被读成「原文里没这词、可以随便定」——但 0/0 也可能是
            # 词键没提干净。脏键已在上面降级，能走到这里的键逐字都在语料字符集
            # 内，仍算不出出现次数的多是词形（活用形、复合短语）问题，措辞照实说。
            verdict = (DIRTY_KEY_VERDICT
                       if s["ratio"] is None
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

    # 自述统计口径（同 saturation.py 的教训：一张「完全合理的空表」比报错危险）。
    print(f"done={len(done)} 条已入线译文（data-dir={data}）")
    print(f"已扫描 {len(md_files)} 个 md，期望标题格式 `### 序号. 词 → 译`"
          f"；成词词族 {len(sats)}、未归词 {len(c.get(UNKEYED, []))} 条"
          f"（其中 {len(demoted)} 个键因提取不干净被降级）")
    if not ledger:
        print(f"!! 告警：{ledger_path} 没读到或为空（0 条记录）——corpus_chars 语料字符集"
              f"随之为空集，is_clean_key 的「含语料外字符」判据对**任何**键都成立，"
              f"于是全部词键将被降级进「（未归词）」、饱和度判定不可用。这不是"
              f"「本段提案都没法归词」，是数据源没读到。请确认 --lane-dir 指对了车道、"
              f"且该车道已跑过 build_ledger。")
    if not fwd_path.exists():
        print(f"!! 告警：{fwd_path} 不存在——按「零条已译」计算，全部词族必然判「滚存」，"
              f"闸门等于失效。是否 --lane-dir 指错车道？")
    nobatch = sum(1 for p in props if p["batch"] is None)
    if nobatch:
        print(f"!! 告警：{nobatch} 条提案没解析到批号（渲染为 bNone）——"
              f"检查 notes 里的批次标题是否为 `## batch <数字>` 开头")
    if not props:
        print(f"!! 告警：{data / 'notes'} 下解析出 0 条提案，卷宗是空的。"
              f"确认目录存在、且提案标题写成 `### 序号. 词 → 译`（bullet 体不识别）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
