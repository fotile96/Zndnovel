"""extra 轨机械派生：从已冻结的 skeleton/cards.{jp,zh}.yaml 派生 extra 轨（plotTitle /
scene_title / card_msg / savedata）里能确定的中文，产出可复核报告。**本工具只读、只派生，
绝不写 pilot/lanes/opus/data/ 下任何文件**——派生结果只落 build/（gitignore）。落盘生产
数据（forward_extra.jsonl）是 tools/land_extra.py 的职责，两者刻意分开。

为什么派生而不是模型翻译：skeleton/ 是 git tag skeleton-v1 冻结的定译基准，cards.zh 同时
是前缀 compact 的『あらすじ』语料。派生保证同一张卡在两处（骨架 + extra 轨）文本逐字一致；
模型重译会产生"两种说法"的回归，参见 CLAUDE.md「翻译骨架已冻结」段。

四条派生规则（kind → 依据）：
- plot_title：按 key 里的卡号取 cards.zh 的 title_zh。⚠ 前提是该卡 cards.jp 的 title_jp
  与 ledger 的 jp **逐字相同**——只按卡号取值而不做这层校验，是「卡号对得上」掩盖「文本对不上」
  的恒绿形态（本工具的第一处安全闸）。
- scene_title：按 jp **全文逐字** 去 cards.jp 里找相同的 title_jp，命中就取该卡 title_zh。
  用「包含」代替「逐字相同」会张冠李戴（第二处安全闸）。169/454 条能这样解出；剩余 285 条
  不是冻结卡名（是纯场景标题，无对应卡），留 none——那部分译文来自人工裁定的
  data/extra_translated.jsonl，由 land_extra.py 消费，本工具不碰。
- card_msg：172 条实测聚成 12 种模板（『…』与（…）占位归一后去重可见）。模板译文已定稿
  （见 CARD_MSG_TEMPLATES）。『…』槽位先按精确卡名匹配；不中则退化到两条兜底规则——
  ①`セクション<X>` → `章节 <X>`（X 的全角拉丁/数字转半角，依据冻结骨架 38 处全角拉丁
  卡名无一例外转半角的先例）；②绘由文分かち書き空格形『いつか きみが みる お話』→
  取冻结卡 145 title_zh 并去尾句号（该卡 title_jp 是无空格无句读混写的『いつかきみが
  みるお話。』，字面不同不能走精确匹配，故设专门别名表 TITLE_ALIASES）。（…）槽位同样
  先按精确卡名匹配，不中则查 14 条选项文本定译表 OPTION_TABLE。⚠ 卡名本身可能含括号
  （如卡 180「サクラの日記：７月（書きかけ）」）——（…）槽位必须只在『…』闭合**之后**
  的剩余文本里找，绝不能对整个 jp 字符串做全局搜索，否则会把卡名内嵌的括号误当成槽位
  （第三处安全闸，paren_content_after_quote() 专门处理）。两个槽位都解出才拼模板，
  confidence=template；任一槽位解不出，无论原因，一律 confidence=none 且单列异常，
  绝不允许「解出一半就拼一个带空槽的译文」悄悄放行。
- savedata：全部 none。**空串是合法内容，不是缺失**——本工具对每一条 ledger 行都输出一条
  派生结果，绝不因 jp=="" 就跳过（第四处安全闸）。

用法：
    uv run python tools/derive_extra.py
    # 或系统 python3（纯 stdlib + pyyaml，与 tools/ 既有约定一致）
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, read_jsonl, write_jsonl  # noqa: E402

LEDGER_EXTRA = REPO / "pilot/lanes/opus/data/ledger_extra.jsonl"
CARDS_JP = REPO / "skeleton/cards.jp.yaml"
CARDS_ZH = REPO / "skeleton/cards.zh.yaml"
OUT_JSONL = REPO / "build/extra_derived.jsonl"
OUT_REPORT = REPO / "build/extra_derive_report.md"

# 『…』＝卡名/条目名槽位；（…）＝附加说明槽位（分支名等）。
_BRACKET_QUOTE = re.compile(r"『[^』]*』")
_BRACKET_PAREN = re.compile(r"（[^）]*）")
_FIRST_QUOTE = re.compile(r"『([^』]*)』")
_FIRST_PAREN = re.compile(r"（([^）]*)）")

# 全角拉丁字母 / 数字 → 半角。依据：冻结骨架 38 处含全角拉丁的卡名无一例外转半角
# （ＳｅｃｔｉｏｎＥｘ１→章节 EX1、９月１３日→9月13日）。刻意只覆盖「拉丁/数字」，
# 不动全角标点（如「：」）——`セクション` 规则只需要转换 X 本身。
_ZEN2HAN_ALNUM = str.maketrans(
    "".join(chr(c) for c in range(0xFF10, 0xFF1A)) +   # ０-９
    "".join(chr(c) for c in range(0xFF21, 0xFF3B)) +   # Ａ-Ｚ
    "".join(chr(c) for c in range(0xFF41, 0xFF5B)),    # ａ-ｚ
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)

_SECTION_PREFIX = "セクション"

# card_msg『…』槽位的别名表：jp 字面与冻结卡 title_jp 不逐字相同、但确定指向同一张卡
# 的特例。目前唯一一条——绘本标题的分かち書き（写作时加空格）形『いつか きみが みる
# お話』要对上冻结卡 145 的 title_jp『いつかきみがみるお話。』（无空格、带句号），
# 精确匹配天然对不上，故单独收录；取用时按该卡 title_zh 去掉尾句号。
TITLE_ALIASES = {
    "いつか きみが みる お話": 145,
}

# card_msg（…）槽位的 14 条选项文本定译表（用户裁定）。
# ⚠ 「腕を掴む→抓紧她的手」是用户就**这处 card_msg 选项文字**的明示裁定，
#   用户原话："此裁定仅限这处选项文字翻译，正文类似表现的处理不作变更"——
#   即 vms() 正文里出现的「腕」族表现，其译法不受这条影响，不要拿这条去改正文。
OPTION_TABLE = {
    "羨ましがる": "表示羡慕",
    "受け入れる": "接受",
    "興味を惹かれた": "被勾起了兴趣",
    "机を調べる": "检查课桌",
    "ノートを調べる": "翻看笔记本",
    "腕を掴む": "抓紧她的手",
    "家に帰る": "回家",
    "行く": "去",
    "両思いになるオマジナイ": "两情相悦的咒语",
    "適当に濁す": "含糊带过",
    "約束をしていない、している": "没有约定、有约定",
    "絶対に効く": "绝对灵验",
    "教えて": "告诉我",
    "聞かない": "不听",
}

# card_msg 12 种模板骨架 → 定稿中译（{0}=『…』槽位译文，{1}=（…）槽位译文，若模板本身
# 无（…）槽位则模板里不含 {1}，assemble 时也不会传第二个参数）。骨架字符串必须与
# template_of() 的输出逐字相同（含全角标点、省略号 …）——12 种已用真实 172 条
# card_msg 实测穷举过，键集合与其一一对应。
CARD_MSG_TEMPLATES = {
    "『…』のあらすじを作成しました。": "已写下『{0}』的梗概。",
    "『…』の選択肢（…）を作成しました。": "已写下『{0}』的选项（{1}）。",
    "『…』のあらすじを用意しました。": "已备好『{0}』的梗概。",
    "『…』のカードを作成しました。": "已写好『{0}』的卡片。",
    "『…』のあらすじが作成されました。": "『{0}』的梗概已写下。",
    "『…』のあらすじを作成します。": "这就写下『{0}』的梗概。",
    "『…』のあらすじを作成しますか？": "要写下『{0}』的梗概吗？",
    "『…』の選択肢について解説を加えました。": "已就『{0}』的选项补充说明。",
    "『…』の分岐（…）を作成しました。": "已写下『{0}』的分歧（{1}）。",
    "『…』のあらすじを作成しました": "已写下『{0}』的梗概",
    "『…』のあらすじは、あなたが作成しています。": "『{0}』的梗概，是你写下的。",
    "書きとめました：『…』": "已记下：『{0}』",
}


# ---------------------------------------------------------------------------
# 纯函数层：只吃/吐 Python 数据结构，不碰文件系统——单测与变异都打在这一层。
# ---------------------------------------------------------------------------

def load_yaml_rows(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def build_card_indexes(cards_jp_rows, cards_zh_rows):
    """返回 (jp_by_card, zh_by_card, title_to_cards)。

    title_to_cards 供 scene_title/card_msg 做「jp 全文逐字相同」匹配用；空标题
    （卡 0 无带字卡面，title_jp==''）刻意不入索引，避免空串误命中空串比较。
    """
    jp_by_card = {r["card"]: r["title_jp"] for r in cards_jp_rows}
    zh_by_card = {r["card"]: r["title_zh"] for r in cards_zh_rows}
    title_to_cards = defaultdict(list)
    for c, t in jp_by_card.items():
        if t:
            title_to_cards[t].append(c)
    return jp_by_card, zh_by_card, dict(title_to_cards)


def template_of(jp: str) -> str:
    """把 『…』 与 （…） 内容替换成占位符，得到模板骨架（用于给 172 条 card_msg 去重成 12 种）。"""
    s = _BRACKET_QUOTE.sub("『…』", jp)
    s = _BRACKET_PAREN.sub("（…）", s)
    return s


def bracket_name(jp: str):
    """取 jp 中第一个 『…』 的内容（card_msg 槽位候选卡名）；无则 None。"""
    m = _FIRST_QUOTE.search(jp)
    return m.group(1) if m else None


def paren_content_after_quote(jp: str):
    """取 jp 里『…』**闭合之后**剩余文本中的第一个（…）内容；无则 None。

    ⚠ 安全闸③：必须先跳过整段『…』再找（…），不能对整个 jp 做全局搜索——卡名本身可能
    含括号（如卡 180「サクラの日記：７月（書きかけ）」），全局搜索会把卡名内嵌的括号
    误当成模板的（…）槽位，参见模块 docstring。没有『…』时退化为对整串 jp 搜索（没有
    可跳过的边界，行为等价于全局搜索，语义上无害——没有卡名可供混淆）。
    """
    m = _FIRST_QUOTE.search(jp)
    rest = jp[m.end():] if m else jp
    m2 = _FIRST_PAREN.search(rest)
    return m2.group(1) if m2 else None


def zen2han_alnum(s: str) -> str:
    """全角拉丁字母/数字转半角，其余字符原样保留。"""
    return s.translate(_ZEN2HAN_ALNUM)


def resolve_section_label(name: str):
    """『セクション<X>』→『章节 <X>』兜底规则（X 的全角拉丁/数字转半角）。

    仅在 name 以「セクション」开头时生效；不是这个前缀一律返回 None。调用方须先尝试
    精确卡名匹配，此规则只在那条路失败后才会被走到——带「：」的『セクションN：人名』
    这类多数本身就是冻结卡名，精确匹配已经命中，不会落到这里；这里兜底的是没有对应
    卡的纯章节代号（如『セクション１』『セクションＥＸ２』本身，无冒号后缀）。
    """
    if not name.startswith(_SECTION_PREFIX):
        return None
    suffix = name[len(_SECTION_PREFIX):]
    if not suffix:
        return None
    return f"章节 {zen2han_alnum(suffix)}"


def resolve_quote_content(name, title_to_cards, zh_by_card):
    """解析 card_msg 『…』槽位：精确卡名匹配 → TITLE_ALIASES 别名 → セクション 兜底规则。

    返回 (zh_or_None, source_or_None)。三条路都不中时返回 (None, None)，调用方据此
    判定该行不可派生（card_msg 的第二处「槽位对不上」异常来源，另一处见 paren）。
    """
    cards, zh, ambiguous = resolve_exact_title(name, title_to_cards, zh_by_card)
    if zh is not None:
        card_ids = "|".join(str(c) for c in sorted(cards))
        note = "（同名多卡，zh 一致）" if ambiguous else ""
        return zh, f"cards.zh:card={card_ids}{note}"

    alias_card = TITLE_ALIASES.get(name)
    if alias_card is not None:
        alias_zh = zh_by_card.get(alias_card)
        if alias_zh is not None:
            return alias_zh.rstrip("。"), f"cards.zh:card={alias_card}（空格形）"

    section_zh = resolve_section_label(name)
    if section_zh is not None:
        return section_zh, "rule:セクション→章节"

    return None, None


def resolve_paren_content(text, title_to_cards, zh_by_card):
    """解析 card_msg （…）槽位：精确卡名匹配 → 14 条 OPTION_TABLE 定译表。

    返回 (zh_or_None, source_or_None)。两条路都不中时返回 (None, None)。
    """
    cards, zh, ambiguous = resolve_exact_title(text, title_to_cards, zh_by_card)
    if zh is not None:
        card_ids = "|".join(str(c) for c in sorted(cards))
        note = "（同名多卡，zh 一致）" if ambiguous else ""
        return zh, f"cards.zh:card={card_ids}{note}"

    option_zh = OPTION_TABLE.get(text)
    if option_zh is not None:
        return option_zh, "ruling:选项文本"

    return None, None


def resolve_exact_title(jp_text, title_to_cards, zh_by_card):
    """按『jp_text 与某卡 title_jp 逐字相同』解析。

    ⚠ 必须是精确相等（dict 键查找 ==），绝不能用 `in` 做包含匹配——scene_title 的
    第二处安全闸就是防这个（判据过宽＝张冠李戴，本项目文化里"过宽的判据比不判更坏"）。

    返回 (matched_cards, zh_or_None, ambiguous_bool)：
      - matched_cards：命中的卡号列表（可能因两张卡标题逐字相同而 >1，如卡 20/74「探索：
        放課後の学校」、卡 85/119「屋上」——库里实测仅此两组，且两组各自的 title_zh 相同，
        故仍可给出确定 zh；若某天出现"标题相同但译法不同"，ambiguous=True，调用方须转 none）。
      - zh_or_None：能确定的唯一译文；取不到时 None。
    """
    cards = title_to_cards.get(jp_text)
    if not cards:
        return [], None, False
    zh_values = {zh_by_card[c] for c in cards if c in zh_by_card}
    if len(zh_values) != 1:
        return cards, None, True
    return cards, next(iter(zh_values)), len(cards) > 1


# ---------------------------------------------------------------------------
# 逐 kind 派生：每个函数返回 (result_row, anomaly_or_None)。
# result_row 恒定包含 key/jp/kind/zh/source/confidence 六个字段。
# ---------------------------------------------------------------------------

def derive_plot_title(row, jp_by_card, zh_by_card):
    key, jp = row["key"], row["jp"]
    try:
        n = int(key.split(":", 1)[1])
    except (IndexError, ValueError):
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"plot_title: key 格式异常，取不出卡号: {key!r}")

    jp_title = jp_by_card.get(n)
    if jp_title is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"plot_title: 卡号 {n} 不在 cards.jp.yaml 里（key={key}）")

    # 安全闸①：卡号对得上不代表文本对得上——校验 jp 逐字相同，不同就不派生。
    if jp_title != jp:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"plot_title: 卡号 {n} 的 jp 与 cards.jp.yaml 不逐字相同——"
                f"ledger={jp!r} vs cards.jp={jp_title!r}")

    zh_title = zh_by_card.get(n)
    if zh_title is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"plot_title: 卡号 {n} 的 jp 校验通过，但 cards.zh.yaml 里没有这张卡")

    return ({"key": key, "jp": jp, "kind": row["kind"], "zh": zh_title,
              "source": f"cards.zh:card={n}", "confidence": "exact"},
             None)


def derive_scene_title(row, title_to_cards, zh_by_card):
    key, jp = row["key"], row["jp"]
    cards, zh, ambiguous = resolve_exact_title(jp, title_to_cards, zh_by_card)
    if not cards:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                None)  # 找不到逐字相同的卡名，属预期内的「留给模型翻译」，非异常
    if zh is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"scene_title: jp {jp!r} 命中卡号 {cards}，但各卡 title_zh 不一致，"
                f"取不到唯一译文")
    card_ids = "|".join(str(c) for c in sorted(cards))
    note = "（同名多卡，zh 一致）" if ambiguous else ""
    anomaly = (f"scene_title: jp {jp!r} 同时是卡号 {sorted(cards)} 的标题（同名但 zh 一致，"
               f"派生结果不受影响，仅记录以备核查）") if ambiguous else None
    return ({"key": key, "jp": jp, "kind": row["kind"], "zh": zh,
              "source": f"cards.zh:card={card_ids}{note}", "confidence": "exact"},
             anomaly)


def derive_card_msg(row, title_to_cards, zh_by_card):
    """card_msg 派生：模板骨架 + 『…』槽位 + （如需要）（…）槽位，三者全部解出才拼出
    zh、confidence=template；任一环节解不出，一律 confidence=none 并单列具体原因，
    绝不允许"拼一句带空槽的译文"悄悄放行（本函数是 card_msg 的第三处安全闸）。
    """
    key, jp = row["key"], row["jp"]
    tmpl = template_of(jp)

    name = bracket_name(jp)
    if name is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"card_msg: 无『…』槽位，模板骨架={tmpl!r}")

    tmpl_zh = CARD_MSG_TEMPLATES.get(tmpl)
    if tmpl_zh is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"card_msg: 未知模板骨架 {tmpl!r}（不在 12 种定稿模板表内，"
                f"jp={jp!r}）——需人工核实/扩表，不能假装能拼")

    quote_zh, quote_src = resolve_quote_content(name, title_to_cards, zh_by_card)
    if quote_zh is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"card_msg: 『…』槽位内容 {name!r} 既不是冻结卡名，也不匹配 TITLE_ALIASES"
                f"/セクション 兜底规则（模板骨架={tmpl!r}）——需人工核实")

    needs_paren = "（…）" in tmpl
    if not needs_paren:
        return ({"key": key, "jp": jp, "kind": row["kind"],
                  "zh": tmpl_zh.format(quote_zh),
                  "source": f"template:{tmpl} + {quote_src}",
                  "confidence": "template"},
                 None)

    paren_text = paren_content_after_quote(jp)
    if paren_text is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"card_msg: 模板 {tmpl!r} 需要（…）槽位，但『…』闭合之后的剩余文本里"
                f"找不到（…）（jp={jp!r}）")

    paren_zh, paren_src = resolve_paren_content(paren_text, title_to_cards, zh_by_card)
    if paren_zh is None:
        return ({"key": key, "jp": jp, "kind": row["kind"], "zh": "", "source": "",
                  "confidence": "none"},
                f"card_msg: （…）槽位内容 {paren_text!r} 既不是冻结卡名也不在 14 条 "
                f"OPTION_TABLE 定译表内（模板骨架={tmpl!r}）——需人工核实")

    return ({"key": key, "jp": jp, "kind": row["kind"],
              "zh": tmpl_zh.format(quote_zh, paren_zh),
              "source": f"template:{tmpl} + {quote_src} + {paren_src}",
              "confidence": "template"},
             None)


def derive_savedata(row):
    # 安全闸②：空串是合法内容，不是缺失——本函数对空串与非空串一视同仁地输出一条结果，
    # 绝不 return None / 跳过。
    return ({"key": row["key"], "jp": row["jp"], "kind": row["kind"], "zh": "",
              "source": "", "confidence": "none"},
             None)


_DISPATCH = {
    "plot_title": lambda row, idx: derive_plot_title(row, idx["jp_by_card"], idx["zh_by_card"]),
    "scene_title": lambda row, idx: derive_scene_title(row, idx["title_to_cards"], idx["zh_by_card"]),
    "card_msg": lambda row, idx: derive_card_msg(row, idx["title_to_cards"], idx["zh_by_card"]),
    "savedata": lambda row, idx: derive_savedata(row),
}


def derive_row(row, idx):
    fn = _DISPATCH.get(row["kind"])
    if fn is None:
        return ({"key": row["key"], "jp": row["jp"], "kind": row["kind"], "zh": "",
                  "source": "", "confidence": "none"},
                f"未知 kind={row['kind']!r}（key={row['key']}）——本工具未覆盖，标 none")
    return fn(row, idx)


def derive_all(ledger_rows, jp_by_card, zh_by_card, title_to_cards):
    """对全部 ledger 行逐条派生，绝不静默丢行——len(results) 必须等于 len(ledger_rows)。"""
    idx = {"jp_by_card": jp_by_card, "zh_by_card": zh_by_card, "title_to_cards": title_to_cards}
    results, anomalies = [], []
    for row in ledger_rows:
        result, anomaly = derive_row(row, idx)
        results.append(result)
        if anomaly:
            anomalies.append(anomaly)
    assert len(results) == len(ledger_rows), (
        f"派生结果条数 {len(results)} != ledger 行数 {len(ledger_rows)}——严禁静默丢行")
    return results, anomalies


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def build_report(ledger_rows, results, anomalies):
    by_kind_conf = defaultdict(Counter)
    by_key = {r["key"]: r for r in results}
    for r in results:
        by_kind_conf[r["kind"]][r["confidence"]] += 1

    lines = []
    lines.append("# extra 轨机械派生复核报告\n")
    lines.append(f"ledger 总行数：{len(ledger_rows)}；派生结果：{len(results)}；异常：{len(anomalies)} 条。\n")

    lines.append("## 总览\n")
    lines.append("| kind | exact | template | none | 小计 |")
    lines.append("|---|---:|---:|---:|---:|")
    kinds = sorted(by_kind_conf)
    tot_exact = tot_tmpl = tot_none = 0
    for k in kinds:
        c = by_kind_conf[k]
        e, t, n = c.get("exact", 0), c.get("template", 0), c.get("none", 0)
        tot_exact += e; tot_tmpl += t; tot_none += n
        lines.append(f"| {k} | {e} | {t} | {n} | {e+t+n} |")
    lines.append(f"| **合计** | **{tot_exact}** | **{tot_tmpl}** | **{tot_none}** | **{tot_exact+tot_tmpl+tot_none}** |")
    lines.append("")

    # 逐条派生结果，按 kind 分节；每节内 exact/template 与 none 分开列。
    by_kind = defaultdict(list)
    for r in results:
        by_kind[r["kind"]].append(r)

    for k in kinds:
        rows = by_kind[k]
        lines.append(f"## kind = {k}（共 {len(rows)} 条）\n")
        done = [r for r in rows if r["confidence"] != "none"]
        none_rows = [r for r in rows if r["confidence"] == "none"]
        if done:
            lines.append(f"### 已派生（{len(done)} 条）\n")
            lines.append("| key | jp | zh | confidence | source |")
            lines.append("|---|---|---|---|---|")
            for r in done:
                lines.append(f"| {r['key']} | {_esc(r['jp'])} | {_esc(r['zh'])} | {r['confidence']} | {_esc(r['source'])} |")
            lines.append("")
        lines.append(f"### 未派生 / none（{len(none_rows)} 条，留给模型翻译或人工定模板）\n")
        if none_rows:
            lines.append("| key | jp | source |")
            lines.append("|---|---|---|")
            for r in none_rows:
                lines.append(f"| {r['key']} | {_esc(r['jp'])} | {_esc(r['source'])} |")
        else:
            lines.append("（无）")
        lines.append("")

    # 12 种模板定稿表（CARD_MSG_TEMPLATES）
    cm_rows = [r for r in ledger_rows if r["kind"] == "card_msg"]
    tmpl_counter = Counter(template_of(r["jp"]) for r in cm_rows)
    tmpl_example = {}
    for r in cm_rows:
        t = template_of(r["jp"])
        tmpl_example.setdefault(t, r["jp"])
    lines.append(f"## card_msg 12 种模板定稿表（{len(tmpl_counter)} 种，共 {len(cm_rows)} 条）\n")
    lines.append("模板译文已定稿（CARD_MSG_TEMPLATES）；配合『…』/（…）槽位解析即可机械拼出"
                 "全部 172 条 card_msg（未收录进 CARD_MSG_TEMPLATES 的骨架会在下方异常一览"
                 "里单列，不会被静默忽略）。\n")
    lines.append("| 模板（占位归一后） | 定稿中译 | 出现次数 | 举例（原文） |")
    lines.append("|---|---|---:|---|")
    for t, c in tmpl_counter.most_common():
        lines.append(f"| {_esc(t)} | {_esc(CARD_MSG_TEMPLATES.get(t, ''))} | {c} | {_esc(tmpl_example[t])} |")
    lines.append("")

    lines.append(f"## 异常一览（{len(anomalies)} 条）\n")
    if anomalies:
        for a in anomalies:
            lines.append(f"- {a}")
    else:
        lines.append("（无）")
    lines.append("")

    return "\n".join(lines) + "\n"


def _esc(s):
    return (s or "").replace("|", "\\|").replace("\n", "⏎")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", default=str(LEDGER_EXTRA))
    ap.add_argument("--cards-jp", default=str(CARDS_JP))
    ap.add_argument("--cards-zh", default=str(CARDS_ZH))
    ap.add_argument("--out-jsonl", default=str(OUT_JSONL))
    ap.add_argument("--out-report", default=str(OUT_REPORT))
    args = ap.parse_args(argv)

    ledger_rows = read_jsonl(args.ledger)
    cards_jp_rows = load_yaml_rows(args.cards_jp)
    cards_zh_rows = load_yaml_rows(args.cards_zh)
    jp_by_card, zh_by_card, title_to_cards = build_card_indexes(cards_jp_rows, cards_zh_rows)

    results, anomalies = derive_all(ledger_rows, jp_by_card, zh_by_card, title_to_cards)

    out_jsonl = Path(args.out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_jsonl, results)

    report = build_report(ledger_rows, results, anomalies)
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(report, encoding="utf-8")

    by_kind_conf = defaultdict(Counter)
    for r in results:
        by_kind_conf[r["kind"]][r["confidence"]] += 1
    print(f"派生 {len(results)} 条（ledger 共 {len(ledger_rows)} 条），异常 {len(anomalies)} 条。", file=sys.stderr)
    for k in sorted(by_kind_conf):
        c = by_kind_conf[k]
        print(f"  {k}: exact={c.get('exact',0)} template={c.get('template',0)} none={c.get('none',0)}",
              file=sys.stderr)
    print(f"写出 {out_jsonl} / {out_report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
