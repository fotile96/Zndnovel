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

# ---- 容器标题 + 列表项提案（长对话／会话组模式的 notes 书写结构）----
# 逐批模式的 notes 是「一词一标题」（`### 1. 作業記憶 → 工作记忆`），extract_terms
# 从标题里抠词即可。长对话模式改成「一批一节、按主题分小节」：提案落在**容器标题**
# （`### 5. 术语提案（留给术语委员会）`）之下的有序列表里，标题本身一个词都没有——
# SEG-3 段末实测，s4s/s4fa/s4fb 三份 notes 里的 34 条真提案在卷宗中一条都不成词，
# 裁决会话只能人工逐节读 notes 兜底。
#
# 判据取书写约定的**结构**，不猜「像不像术语提案」：这些 notes 里反引号 = 原文、
# 粗体 = 译文或提案头。一个反引号片段算词项，当且仅当
#   (a) 它落在某个 `**…**` 粗体片段内——提案头写法 **`エンドロール`→片尾字幕**；或
#   (b) 其后紧跟 `→` 且箭头右侧紧接粗体——并列写法 `銀婚式`→**银婚纪念**｜`ココア`→**可可**。
# 正文里随手引用的原文（`雷は苦手`、`現実が物語のストーリーを追う…`）两条都不满足，
# 自然被排除；有序列表若一条都不满足（纯散文编号列表），整节照旧只当正文，
# **逐批模式的 notes 因此逐字不受影响**。
LIST_ITEM_RE = re.compile(r"^(\d+)\.\s+(.*)$")

# ---- 表格体提案（第三种书写结构）----
# 实测（2026-08-05，全 19 份 notes）：**543 行表格数据行 / 103 张表头**，最早出现在
# SEG-1 的 s2f/s2s。此前两条判据（标题体、容器内有序列表）**一行都匹配不到表格**
# ——`|…|` 行既不是 `### N.` 也不是 `N. `，于是整表静默丢失。裁决会话连续多段
# 只能人工逐节读 notes 兜底。
#
# 表格里「原文」和「译法」**分处不同单元格**，故容器体的两条判据（反引号落在粗体
# 内 / `原文`→**译文**）结构上不可能命中——这不是正则写得不够宽，是判据形状不对。
# 表格的正确判据是**表头列名**：找出「原文」列与「译法」列，词项取自前者。
#
# ⚠ 但「解析所有表格」同样是错的：这 543 行里有大量**记录性判断**（「已核对的复现
# 句」「沿用既有译法」「自查记录」「【维护者记录】」），它们不请求裁决。全量收进卷宗
# 会用备查内容淹没真提案——裁决会话明确提过这条。故按**容器标题**三分类，
# 且**一条都不丢**：提案进卷宗正文，备查与存疑进附录，三类计数一律播报。
TABLE_SEP_RE = re.compile(r"^\|[\s:\-|]+\|\s*$")
# 列名判据：中文 notes 的表头用词实测有「原文」「原文关键词」「词」；译法列有
# 「建议译法」「本批译法」「译文」「新译」「沿用的既有译法」。取最宽的子串判据。
COL_SRC_RE = re.compile(r"原文|^词$")
COL_DST_RE = re.compile(r"译")
# 容器标题分类。**顺序有意义**：记录性关键词先判——「【维护者记录】段末裁决回改」
# 同时含「裁决」与「记录」，它是记录不是提案。
CONTAINER_RECORD_RE = re.compile(
    r"维护者记录|记录性|自查|核对|沿用|备查|已知信息损失|一次性生词表")
CONTAINER_PROP_RE = re.compile(r"提案|请裁|待裁")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
TICK_RE = re.compile(r"`([^`]+)`")
# 反引号片段 → 粗体：并列写法里「原文→译文」的那个译文一律加粗，这是判据 (b)。
PAIR_RE = re.compile(r"`[^`]+`\s*→\s*\*\*")
# 说话人标签：`【千秋】「はい」` 这类提案的词是 はい，【千秋】是标签不是词。
SPEAKER_RE = re.compile(r"^【[^】]*】")


def extract_terms(title: str) -> list:
    t = re.sub(r"^\d+\.\s*", "", title)
    if t.count("→") != 1:
        # 0 个 → 无词项；>1 个 → 顿号分隔的多词小族，不做多词解析（brief
        # 明确不扩展），直接归未归词待人工过目，避免第一段箭头前文本被
        # 误当成唯一词键、伪装成正常词族并跑出虚假的「无出现」饱和度。
        return []
    left = DESC_PREFIX_RE.sub("", STRIP_RE.sub("", t.split("→", 1)[0]).strip())
    return [w.strip() for w in SPLIT_RE.split(left.replace("★", "")) if w.strip()]


def item_terms(text: str) -> list:
    """列表项里的词项：粗体内的反引号片段 ∪ 后接 `→**` 的反引号片段（判据见上）。"""
    bolds = [(m.start(1), m.end(1)) for m in BOLD_RE.finditer(text)]
    terms = []
    for m in TICK_RE.finditer(text):
        in_bold = any(a <= m.start(1) and m.end(1) <= b for a, b in bolds)
        if not (in_bold or PAIR_RE.match(text, m.start())):
            continue
        # 反引号内已是纯原文，不再套 DESC_PREFIX_RE：那条是给标题体准备的
        # （「首译定名：意識」），套在 `０：００` 这类含冒号的原文上反而把左半截吃掉。
        raw = STRIP_RE.sub("", SPEAKER_RE.sub("", m.group(1))).strip()
        for w in SPLIT_RE.split(raw.replace("★", "")):
            if w.strip() and w.strip() not in terms:
                terms.append(w.strip())
    return terms


def expand_container(prop: dict) -> list:
    """把「容器标题 + 有序列表」的一节展开成逐条列表项提案。

    只有当该节至少有**一条**列表项能按结构判据抠出词项时，才认定它是提案容器；
    此时整节的列表项**全部**转为提案（抠不出词的那几条照旧进未归词，不丢文本），
    容器标题自身不再单独成条——它是「术语提案（留给术语委员会）」「自查记录」
    这类分节名，不该成词族。标题自带词项（`### 6. 术语提案｜`カウンター` …`）时
    两者并存：标题里的词是真词，不能因为它名下有列表就被吞掉。
    """
    lines = prop["body"].splitlines()
    starts = [i for i, ln in enumerate(lines) if LIST_ITEM_RE.match(ln)]
    if not starts:
        return [prop]
    segs = []
    for k, i in enumerate(starts):
        j = starts[k + 1] if k + 1 < len(starts) else len(lines)
        m = LIST_ITEM_RE.match(lines[i])
        segs.append((m.group(1), m.group(2), "\n".join(lines[i + 1:j])))
    kids = [dict(prop, num=f"{prop['num']}.{n}", title=title, body=body,
                 terms=item_terms(title + "\n" + body), starred="★" in title)
            for n, title, body in segs]
    if not any(k["terms"] for k in kids):
        return [prop]
    # 容器前言（首条列表项之前的散文）不能随容器一起丢，挂到第一条上。
    intro = "\n".join(lines[:starts[0]]).strip()
    if intro:
        kids[0]["body"] = intro + "\n" + kids[0]["body"]
    return ([prop] + kids) if prop["terms"] else kids


def _cells(line: str) -> list:
    """markdown 表格行 → 单元格列表（去掉首尾的空串）。"""
    parts = line.split("|")
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [c.strip() for c in parts]


def classify_container(title: str) -> str:
    """容器标题 → proposal / record / unknown。

    unknown 不是「丢掉」的同义词——它进卷宗附录并单独计数。**默认值必须是
    unknown 而不是 proposal 或 record**：前者会把备查内容混进裁决面，后者会把
    真提案静默降级，两种猜法都会在下一种新写法出现时无声出错。
    """
    if CONTAINER_RECORD_RE.search(title):
        return "record"
    if CONTAINER_PROP_RE.search(title):
        return "proposal"
    return "unknown"


def table_terms(cell: str) -> list:
    """表格「原文」单元格里的词项。有反引号取反引号内容，否则取整格去装饰。"""
    ticks = [m.group(1) for m in TICK_RE.finditer(cell)]
    raw = ticks or [cell]
    terms = []
    for r in raw:
        r = DESC_PREFIX_RE.sub("", STRIP_RE.sub("", SPEAKER_RE.sub("", r))).strip()
        for w in SPLIT_RE.split(r.replace("★", "")):
            w = w.strip()
            # 纯 id/数字格（`| 152 | 15864 |`）不是词
            if w and not w.isdigit() and w not in terms:
                terms.append(w)
    return terms


def parse_tables(text: str, chapter: str):
    """扫全文的 markdown 表格，返回 (提案列表, 未识别表的诊断列表)。

    与 parse_notes 的标题扫描**互不干扰**：表格行永远不会被 PROP_RE/LIST_ITEM_RE
    匹配，故这里单独走一遍全文，不改动既有两条判据的任何行为。
    """
    lines = text.splitlines()
    props, unparsed = [], []
    batch, container = None, ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if m := BATCH_RE.match(line):
            batch = int(m.group(1))
        if line.startswith("#"):
            container = line.lstrip("# ").strip()
        # 表头 = 以 | 开头、下一行是分隔行
        if (line.startswith("|") and i + 1 < len(lines)
                and TABLE_SEP_RE.match(lines[i + 1])):
            header = _cells(line)
            body_start = i + 2
            j = body_start
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = [_cells(lines[k]) for k in range(body_start, j)]
            src = next((n for n, h in enumerate(header) if COL_SRC_RE.search(h)), None)
            dst = next((n for n, h in enumerate(header) if COL_DST_RE.search(h)), None)
            if src is None or dst is None:
                # 认不出来就说出来。**不能静默跳过**——正是「静默」让表格体在五个段里
                # 无人察觉，而不是「少写了一条正则」。
                unparsed.append({"chapter": chapter, "container": container,
                                 "header": header, "rows": len(rows)})
            else:
                kind = classify_container(container)
                # 批号优先取表里的「批次」列：表格体常写在 `## 术语提案` 这类不带批号的
                # 容器下（s6s/s6f/s7f 全文件如此），只靠 BATCH_RE 会整表渲染成 bNone。
                bcol = next((n for n, h in enumerate(header)
                             if "批" in h and "译" not in h), None)
                for n, cells in enumerate(rows, 1):
                    if src >= len(cells):
                        continue
                    rb = batch
                    if bcol is not None and bcol < len(cells):
                        digits = re.findall(r"\d+", cells[bcol])
                        if digits:
                            rb = int(digits[0])
                    props.append({
                        "chapter": chapter, "batch": rb, "num": f"T{n}",
                        "title": " ｜ ".join(cells[:dst + 1]),
                        "terms": table_terms(cells[src]),
                        "starred": "★" in " ".join(cells),
                        "kind": kind, "container": container,
                        "body": " ｜ ".join(cells[dst + 1:])})
            i = j
            continue
        i += 1
    return props, unparsed


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
    # 第二遍才展开容器：第一遍逐字保持原有的标题扫描语义，没有合格列表项时
    # expand_container 是恒等映射，逐批模式的解析结果因此不可能被改动。
    return [q for p in props for q in expand_container(p)]


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
    props, aside, unparsed = [], [], []
    md_files = sorted((data / "notes").glob("*.md"))
    for p in md_files:
        text = p.read_text(encoding="utf-8")
        props += parse_notes(text, p.stem)
        tprops, tun = parse_tables(text, p.stem)
        unparsed += tun
        for t in tprops:
            (props if t["kind"] == "proposal" else aside).append(t)
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
    if aside:
        # 备查不进裁决面，但**必须在同一份卷宗里看得见**：删掉它才是这次要修的病。
        byc = {}
        for p in aside:
            byc.setdefault((p["chapter"], p["kind"], p["container"]), []).append(p)
        lines += ["", "---", "",
                  f"## 附录：表格体里未判为提案的 {len(aside)} 行（备查，不请求裁决）", "",
                  "> 判据是**容器标题**：含「提案/请裁/待裁」→ 提案（已在上面）；含「维护者记录/"
                  "自查/核对/沿用/备查/一次性生词表」→ 记录性；两者都不含 → `unknown`，"
                  "**默认不猜**，一并列在这里由人过目。", ""]
        for (ch, kind, cont), ps in sorted(byc.items()):
            lines.append(f"### [{ch}] {cont}（{kind}，{len(ps)} 行）")
            for p in ps:
                lines.append(f"- b{p['batch']} {p['title']}")
            lines.append("")
    text = "\n".join(lines)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"卷宗已写 {a.out}（{len(props)} 提案 / {len(c)} 词族）")
    else:
        print(text)

    # 自述统计口径（同 saturation.py 的教训：一张「完全合理的空表」比报错危险）。
    print(f"done={len(done)} 条已入线译文（data-dir={data}）")
    ntab = sum(1 for p in props if str(p["num"]).startswith("T"))
    print(f"已扫描 {len(md_files)} 个 md，识别三种提案体：标题体 `### 序号. 词 → 译`、"
          f"容器体（有序列表，词写成 **`原文`→译文**）、"
          f"表格体（表头须同时有「原文」列与「译」列）"
          f"；成词词族 {len(sats)}、未归词 {len(c.get(UNKEYED, []))} 条"
          f"（其中 {len(demoted)} 个键因提取不干净被降级）")
    print(f"其中表格体：{ntab} 行判为提案（已进卷宗正文）、{len(aside)} 行判为备查/存疑"
          f"（进附录，不请求裁决）")
    if unparsed:
        # 「认不出来」必须与「认出来了、没内容」在输出上可区分。表格体在五个段里
        # 静默丢失，正是因为没有这一行——不是因为少写了一条正则。
        tot = sum(u["rows"] for u in unparsed)
        print(f"!! 告警：{len(unparsed)} 张表未能识别列结构，合计 {tot} 行**未进卷宗**"
              f"（表头缺「原文」列或「译」列）。若其中有真提案，请人工提取：")
        for u in unparsed:
            print(f"   {u['chapter']}: {u['rows']} 行｜表头 {u['header']}"
                  f"｜容器「{u['container'][:40]}」")
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
              f"确认目录存在、且提案写成 `### 序号. 词 → 译` 标题体，或容器标题之下的"
              f"有序列表项（词须写作 **`原文`→译文** 或 `原文`→**译文**）；无序 bullet 体不识别")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
