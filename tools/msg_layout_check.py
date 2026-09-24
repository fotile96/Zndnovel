#!/usr/bin/env python3
"""消息窗排版校验器：按引擎规则逐格模拟每条会进入 msg() 的文本，报错误/警告（纯 stdlib）。

引擎事实（docs/ops/eboot-kinsoku-research-2026-09-04.md，含 layers/eboot 补丁后的行为）：
  - 每个 UTF-8 字符恒占一格 17 px，25 格/行，4 行/消息；`_n` 只是等键（**不换行、
    不清页**），`_r` 换行；第 5 行起引擎停滞、消息永远结束不了（探针实测卡死）。
  - 正文缓冲与 backlog 每槽 500 B，`sprintf` 无界——文本（含控制码）必须 < 500 B。
  - 行末禁则：字符落第 25 格（col 24）且在行末表内 → 先换行；行头禁则：行满（col ≥ 25）
    时字符在行头表内 → 悬挂到第 26/27… 格，否则换行。两张表直接读 layers/eboot/kinsoku.toml，
    与打进 EBOOT 的完全一致。
  - `【名】` 只在文本开头被解析成名牌，正文从 `】` 之后起算列 0；没有 `】` 引擎会读穿缓冲。
  - `<base,ruby>`：半角逗号切段（多个逗号都只是切换、不入串）、半角 `>` 结束；base/ruby
    各进 100 B 栈缓冲（strcat 无界）；整组一帧画完，**不做换行/禁则/第 4 行检查**；
    ruby 起点 x = 17·col + (17·nb − P·units)/2 + 4，units：1–2 字节字符 1、3–4 字节 2，
    P = build_font.RUBY_PITCH_PX（半角字母/空格步进）；缺 `>` 引擎读穿缓冲。
  - `_` 后接 n/r 以外的字符：引擎吞掉 `_`、照画后一个字符。
  - `_n` 不清页：4 行上限是整条消息的上限，不是每个 `_n` 分段。

用法：
  uv run python tools/msg_layout_check.py [--profile release] [--lua-dir DIR] [--show 11141] [--json]
默认在内存里装配 release 最终源（译文注入 + 全部层 + 编外脚本），也可指向已构建的
build/<profile>/lua/final/。退出码：有错误 1，否则 0。
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CELL_PX = 17          # 汉字/全角步进 = 原网格一格
COLS = 25             # 原网格每行格数（行宽仍是 25 × 17 = 425 px）
LINE_PX = COLS * CELL_PX      # 425：行宽；起点 ≥ 此值即悬挂区（layers/eboot/msgcol-px）
LATIN_EST_PX = 9      # 单字节字符画之前的步进估算（只用于"放不放得下"判定，与 msgcol-px 层一致）
CJK_EST_PX = 17       # 多字节字符的估算
HANG_DEEP_PX = LINE_PX + 2 * CELL_PX   # 起点 ≥ 459（x ≥ 463）算"深悬挂"
TAIL_PX = LINE_PX - 2 * CELL_PX + 1    # 392：起点 ≥ 此值的开括号提前换行（原 col == 24）
ADVANCE_TABLE = REPO / "data" / "font_advances_17.json"   # tools/pgf_inspect.py export-advances
LINES = 4             # 每消息行数上限（第 5 行起引擎停滞）
BUF_BYTES = 500       # 正文缓冲 / backlog 槽（含 NUL）
RUBY_BUF = 100        # base / ruby 各自的栈缓冲（含 NUL）
HANG_WARN = 3         # 悬挂到第 3 格（x ≥ 463）起告警
KINSOKU_LAYER = REPO / "layers" / "eboot" / "kinsoku.toml"
HEAD_VA, TAIL_VA = 0x663E0, 0x66462


def kinsoku_tables(layer: Path = KINSOKU_LAYER) -> tuple[str, str]:
    """从 kinsoku 层读行头/行末表（与 EBOOT 里的字节同源）。返回 (行头表, 行末表)。"""
    raw = tomllib.loads(layer.read_text(encoding="utf-8"))
    head = tail = None
    for p in raw.get("patches", []):
        va = int(str(p.get("va", "0")), 0)
        if va == HEAD_VA:
            head = p["str"]
        elif va == TAIL_VA:
            tail = p["str"]
    if head is None or tail is None:
        raise SystemExit(f"{layer}: 找不到 va={HEAD_VA:#x}/{TAIL_VA:#x} 的 str 补丁，无法得到禁则表")
    return head, tail


def ruby_pitch() -> int:
    from tools import build_font
    return build_font.RUBY_PITCH_PX


_ADV: dict | None = None


def advance(ch: str) -> int:
    """正文一个字符的真实步进（px）：来自 17 px 字体的步进表；空格走引擎的跳过路径 = ruby_pitch。"""
    global _ADV
    if ch == " ":
        return ruby_pitch()
    if _ADV is None:
        _ADV = json.loads(ADVANCE_TABLE.read_text(encoding="utf-8"))
    return _ADV["adv"].get(ch, _ADV["default"])


def est(ch: str) -> int:
    return LATIN_EST_PX if len(ch.encode("utf-8")) == 1 else CJK_EST_PX


def _pinyin_chars() -> str:
    from tools import build_font
    return build_font.PINYIN_CHARS


@dataclass(frozen=True)
class Msg:
    file: str          # 源文件名（不含扩展名）
    ref: str           # vms/msg 的数字 id，或 oCard.show 的 "file:行号"
    text: str          # 解转义后的文本（引擎看到的字节）
    line: int          # 源文件行号


@dataclass
class Finding:
    level: str         # "error" | "warn"
    code: str
    msg: Msg
    detail: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.msg.file} {self.msg.ref} {self.code}: {self.detail}"


@dataclass
class Layout:
    rows: list[str] = field(default_factory=list)       # 每行的字符串（含悬挂区）
    line_px: list[int] = field(default_factory=list)    # 每行结束时的列（px）
    hang_from: dict[int, int] = field(default_factory=dict)   # 行 → 悬挂区从第几个字符起
    findings: list[Finding] = field(default_factory=list)
    rubies: list[dict] = field(default_factory=list)    # {line, col(px), base, ruby, x, width, width_base, units}
    pages: int = 1                                       # `_n` 分段数 + 1
    overflow: bool = False


# ---------------------------------------------------------------------------
# 提取：最终 lua 源里的 vms / msg / oCard.show 字面量
# ---------------------------------------------------------------------------

_LUA_STR = r'"((?:[^"\\]|\\.)*)"'
_VMS = re.compile(r'(?<![A-Za-z0-9_.])vms\(\s*(\d+)\s*,\s*"[A-Za-z0-9]+"\s*,\s*' + _LUA_STR + r'\s*\)')
_MSG = re.compile(r'(?<![A-Za-z0-9_.])msg\(\s*(\d+)\s*,\s*' + _LUA_STR + r'\s*\)')
_ANY_CALL = re.compile(r'(?<![A-Za-z0-9_.])(?:vms|msg)\(\s*\d+\s*,')
_CARD = re.compile(r'oCard\.show\(')
_ESC = re.compile(r'\\(\d{1,3}|.)', re.S)


def lua_unquote(body: str) -> str:
    """还原 lua 双引号字符串体里的转义（tools/inject_lua.lua_quote 只产 \\\\ 与 \\"，
    这里顺带认 \\n \\r \\t 与 \\ddd）。"""
    def sub(m: re.Match) -> str:
        e = m.group(1)
        if e.isdigit():
            return chr(int(e))
        return {"n": "\n", "r": "\r", "t": "\t", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}.get(e, e)
    return _ESC.sub(sub, body)


def _card_show_text(src: str, start: int) -> tuple[str | None, int]:
    """从 `oCard.show(` 的左括号后扫到配对右括号，返回 (第 2 个顶层字面量参数, 结束位置)。
    第 1 个参数是含嵌套调用与字符串的表达式，正则搞不定，这里手写一遍小扫描。"""
    depth, i, n = 1, start, len(src)
    args: list[str | None] = []
    cur_literal: str | None = None
    saw_nonliteral = False
    while i < n and depth > 0:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            lit = src[i + 1:j]
            if depth == 1 and not saw_nonliteral and cur_literal is None:
                cur_literal = lit
            else:
                saw_nonliteral = True
            i = j + 1
            continue
        if c == "(":
            depth += 1
            saw_nonliteral = True
        elif c == ")":
            depth -= 1
            if depth == 0:
                args.append(None if saw_nonliteral else cur_literal)
                return (args[1] if len(args) > 1 else None), i + 1
        elif c == "," and depth == 1:
            args.append(None if saw_nonliteral else cur_literal)
            cur_literal, saw_nonliteral = None, False
        elif not c.isspace():
            saw_nonliteral = True
        i += 1
    return None, i


def extract_messages(sources: dict[str, str]) -> tuple[list[Msg], int]:
    """返回 (字面量消息列表, 动态拼接而无法静态校验的调用数)。"""
    msgs: list[Msg] = []
    dynamic = 0
    for name in sorted(sources):
        stem = name[:-4] if name.endswith(".lua") else name
        src = sources[name]
        line_of = _LineIndex(src)
        literal_spans = 0
        for pat in (_VMS, _MSG):
            for m in pat.finditer(src):
                literal_spans += 1
                msgs.append(Msg(stem, m.group(1), lua_unquote(m.group(2)), line_of(m.start())))
        dynamic += sum(1 for _ in _ANY_CALL.finditer(src)) - literal_spans
        for m in _CARD.finditer(src):
            text, _end = _card_show_text(src, m.end())
            if text is None:
                dynamic += 1
            else:
                ln = line_of(m.start())
                msgs.append(Msg(stem, f"{stem}:{ln}", lua_unquote(text), ln))
    return msgs, dynamic


class _LineIndex:
    def __init__(self, src: str):
        self.starts = [0]
        for i, c in enumerate(src):
            if c == "\n":
                self.starts.append(i + 1)

    def __call__(self, pos: int) -> int:
        import bisect
        return bisect.bisect_right(self.starts, pos)


# ---------------------------------------------------------------------------
# 模拟
# ---------------------------------------------------------------------------

def _units(ruby: str) -> int:
    return sum(1 if len(c.encode("utf-8")) <= 2 else 2 for c in ruby)


_ALNUM = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


def simulate(text: str, msg: Msg | None = None, *, head: str, tail: str, pitch: int,
             pinyin: str | None = None) -> Layout:
    """按引擎规则（含 layers/eboot 各层）排一条消息。findings 里 error 表示引擎会出可见故障
    （卡死/读穿/裁切），warn 表示排版难看或与估算假设不符。

    像素模型（msgcol-px 层）：列 col 是行内像素 x；行末禁则 col ≥ 392、行头禁则 col + est ≥ 426
    （est：单字节 9、多字节 17）；画在 col + 4，然后 col += 真实步进（步进表）。ruby 组先画 base
    取真实宽 w，注音起点 col + (w − pitch·units)/2 + 4，col += w。"""
    m = msg or Msg("?", "?", text, 0)
    L = Layout()
    F = L.findings
    pinyin = pinyin if pinyin is not None else _pinyin_chars()
    allowed_half = set(pinyin) | set(" ")

    nbytes = len(text.encode("utf-8"))
    if nbytes >= BUF_BYTES:
        F.append(Finding("error", "too-long", m, f"{nbytes} B ≥ {BUF_BYTES} B 缓冲（含 NUL），sprintf 无界会写穿"))

    i, n = 0, len(text)
    if text.startswith("【"):
        j = text.find("】")
        if j < 0:
            F.append(Finding("error", "name-unterminated", m, "开头的【没有配对的】，引擎会一直读到缓冲之外"))
            return L
        i = j + 1

    rows: list[list[str]] = [[]]
    line_px: list[int] = [0]
    col = line = 0
    hang_reported: set[int] = set()
    last_ruby: dict | None = None
    prev_ch = ""
    narrow: list[str] = []

    def newline() -> None:
        nonlocal col, line, last_ruby
        col, line = 0, line + 1
        last_ruby = None
        while len(rows) <= line:
            rows.append([])
            line_px.append(0)

    def place(ch: str) -> None:
        nonlocal col
        if col >= LINE_PX and line not in L.hang_from:
            L.hang_from[line] = len(rows[line])
        if col >= HANG_DEEP_PX and line not in hang_reported:
            hang_reported.add(line)
            F.append(Finding("warn", "hang-deep", m,
                             f"第 {line + 1} 行悬挂到 x≈{col + 4}（行宽 {LINE_PX}）：贴近屏幕右缘"))
        rows[line].append(ch)

    def overflow() -> bool:
        nonlocal L
        if line >= LINES and not L.overflow:
            L.overflow = True
            F.append(Finding("error", "page-overflow", m,
                             f"排到第 {line + 1} 行（上限 {LINES}）：引擎不再绘制也不再推进，消息永远结束不了"))
        return L.overflow

    while i < n:
        ch = text[i]
        if ch == "_":
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt == "n":
                L.pages += 1
                i += 2
                continue
            if nxt == "r":
                newline()
                prev_ch = ""
                i += 2
                continue
            F.append(Finding("warn", "stray-underscore", m, f"`_{nxt}` 不是控制码：引擎吞掉 `_`、照画 `{nxt}`"))
            i += 1
            continue
        if ch == "<":
            end = text.find(">", i + 1)
            if end < 0:
                F.append(Finding("error", "ruby-unterminated", m, "`<` 没有配对的 `>`：引擎会读穿正文缓冲直到撞见 `>`"))
                return L
            body = text[i + 1:end]
            if "<" in body:
                F.append(Finding("warn", "ruby-nested", m, f"注音组内又出现 `<`：{body!r}"))
            if "," not in body:
                F.append(Finding("warn", "ruby-no-comma", m, f"注音组没有半角逗号，ruby 为空：{body!r}"))
            parts = body.split(",")
            base, ruby = parts[0], "".join(parts[1:])
            if "_n" in body or "_r" in body:
                F.append(Finding("warn", "ruby-control-code", m, f"注音组内的 _n/_r 不被识别，会按字面画出：{body!r}"))
            if len(base.encode("utf-8")) >= RUBY_BUF:
                F.append(Finding("error", "ruby-base-too-long", m, f"base {len(base.encode())} B ≥ {RUBY_BUF} B 栈缓冲，strcat 会砸栈"))
            if len(ruby.encode("utf-8")) >= RUBY_BUF:
                F.append(Finding("error", "ruby-too-long", m, f"ruby {len(ruby.encode())} B ≥ {RUBY_BUF} B 栈缓冲，strcat 会砸栈"))
            if not base:
                F.append(Finding("warn", "ruby-empty-base", m, "注音组 base 为空"))
            if " " in base:
                F.append(Finding("warn", "ruby-base-space", m, f"base 含半角空格：引擎跳过字形只推进 {pitch} px：{body!r}"))
            bad = sorted({c for c in ruby if ord(c) < 0x300 and c not in allowed_half})
            if bad:
                F.append(Finding("warn", "ruby-halfwidth-nonpinyin", m,
                                 f"ruby 含非拼音半角字符 {bad}：字体步进 4 px 与估算 {pitch} px 不符"))
            units = _units(ruby)
            w = sum(advance(c) for c in base)
            if overflow():
                return L
            if col + w > LINE_PX:
                F.append(Finding("error", "ruby-past-margin", m,
                                 f"注音组起于 x={col + 4}、base 宽 {w} px，越过行宽 {LINE_PX}：整组不折行，画进悬挂区/被裁"))
            x = col + int((w - pitch * units) / 2) + 4
            width = pitch * units
            if x < 0:
                F.append(Finding("error", "ruby-negative-x", m,
                                 f"注音起点 x={x} < 0：`{ruby}` 首字母会被屏幕左缘裁掉（base `{base}` 起于 col {col}）"))
            if last_ruby is not None and last_ruby["line"] == line and x < last_ruby["x"] + last_ruby["width"]:
                F.append(Finding("warn", "ruby-overlap", m,
                                 f"注音 `{last_ruby['ruby']}` 与 `{ruby}` 在同一行重叠 {last_ruby['x'] + last_ruby['width'] - x} px"))
            info = {"line": line, "col": col, "base": base, "ruby": ruby, "x": x, "width": width,
                    "width_base": w, "units": units}
            L.rubies.append(info)
            last_ruby = info
            for c in base:
                place(c)
            col += w
            line_px[line] = col
            prev_ch = base[-1] if base else ""
            i = end + 1
            continue
        # 普通字符：先按估算判"放不放得下"，画完按真实步进推进
        wrapped = False
        if col >= TAIL_PX and ch in tail:
            newline()
            wrapped = True
        if col + est(ch) > LINE_PX and ch not in head:
            newline()
            wrapped = True
        if wrapped and prev_ch in _ALNUM and ch in _ALNUM:
            F.append(Finding("warn", "latin-split", m,
                             f"拉丁串在 `{prev_ch}|{ch}` 处被自动折行掰开（引擎无词级折行，需手工 _r 或改写）"))
        if overflow():
            return L
        adv = advance(ch)
        # 字母（希腊/西里尔/带附加符号的拉丁，category L*）本就按比例宽排、与 ASCII 拉丁同理；
        # 只报本该占满一格的窄符号/标点（× “” · …）
        if len(ch.encode("utf-8")) > 1 and adv < CJK_EST_PX and ch not in narrow \
                and not unicodedata.category(ch).startswith("L"):
            narrow.append(ch)
        place(ch)
        col += adv
        line_px[line] = col
        prev_ch = ch
        i += 1

    if narrow:
        F.append(Finding("warn", "narrow-glyph", m,
                         f"多字节字符 {narrow} 在 17 px 字体里是窄字形（{[advance(c) for c in narrow]} px）：会挤在一起"))
    L.rows = ["".join(r) for r in rows]
    L.line_px = line_px
    return L


def render(layout: Layout) -> str:
    """人读版面：行宽 425 px 之后的悬挂区用 ¦ 标出；注音另列。"""
    out = []
    for k, r in enumerate(layout.rows):
        cut = layout.hang_from.get(k)
        body, hang = (r, "") if cut is None else (r[:cut], r[cut:])
        px = layout.line_px[k] if k < len(layout.line_px) else 0
        out.append(f"{k + 1}| {body}{'¦' + hang if hang else ''}   ({px} px)")
    for rb in layout.rubies:
        out.append(f"   ruby 第{rb['line'] + 1}行 x={rb['x']} <{rb['base']},{rb['ruby']}> base宽{rb['width_base']} 注音宽≈{rb['width']}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 批量
# ---------------------------------------------------------------------------

def check_messages(msgs: list[Msg], *, head: str, tail: str, pitch: int) -> list[Finding]:
    out: list[Finding] = []
    pinyin = _pinyin_chars()
    for m in msgs:
        out.extend(simulate(m.text, m, head=head, tail=tail, pitch=pitch, pinyin=pinyin).findings)
    return out


def check_sources(sources: dict[str, str]) -> tuple[list[Finding], dict]:
    head, tail = kinsoku_tables()
    msgs, dynamic = extract_messages(sources)
    findings = check_messages(msgs, head=head, tail=tail, pitch=ruby_pitch())
    stats = {"messages": len(msgs), "dynamic_skipped": dynamic,
             "errors": sum(f.level == "error" for f in findings),
             "warnings": sum(f.level == "warn" for f in findings)}
    return findings, stats


def format_report(findings: list[Finding], stats: dict, limit: int = 20) -> str:
    from collections import Counter, defaultdict
    lines = [f"[msg-layout] 消息 {stats['messages']} 条（动态拼接跳过 {stats['dynamic_skipped']}）："
             f"错误 {stats['errors']}，警告 {stats['warnings']}"]
    by_code: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_code[f.code].append(f)
    order = sorted(by_code, key=lambda c: (by_code[c][0].level != "error", c))
    for code in order:
        fs = by_code[code]
        lines.append(f"  {fs[0].level:5} {code}: {len(fs)} 条")
        for f in fs[:limit]:
            lines.append(f"    {f.msg.file} {f.msg.ref}: {f.detail}")
        if len(fs) > limit:
            lines.append(f"    … 另 {len(fs) - limit} 条（--limit 调整）")
    return "\n".join(lines)


def load_sources(profile: str, lua_dir: Path | None) -> dict[str, str]:
    if lua_dir is not None:
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(lua_dir.glob("*.lua"))}
    from tools import layers
    from tools.pipelib import read_jsonl
    manifest = layers.load_manifest()
    ledger_rows = read_jsonl(REPO / manifest["base"]["ledger"])
    injected = layers._injected_sources(manifest, ledger_rows)
    sources, _applied, _added = layers.build_final_sources(profile, injected=injected)
    return sources


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="release", choices=("release", "test"))
    ap.add_argument("--lua-dir", type=Path, help="用已构建的 build/<profile>/lua/final/ 代替内存装配")
    ap.add_argument("--show", help="打印某条消息的模拟版面（vms/msg 的 id，或 oCard.show 的 file:行号）")
    ap.add_argument("--limit", type=int, default=20, help="每类问题最多列出几条")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出全部问题")
    args = ap.parse_args(argv)

    sources = load_sources(args.profile, args.lua_dir)
    if args.show:
        msgs, _ = extract_messages(sources)
        head, tail = kinsoku_tables()
        hit = [m for m in msgs if m.ref == args.show]
        if not hit:
            print(f"找不到消息 {args.show}")
            return 2
        for m in hit:
            lay = simulate(m.text, m, head=head, tail=tail, pitch=ruby_pitch())
            print(f"{m.file} {m.ref}（{len(m.text.encode())} B，{lay.pages} 段）\n{m.text}\n{render(lay)}")
            for f in lay.findings:
                print("  ", f)
        return 0
    findings, stats = check_sources(sources)
    if args.json:
        print(json.dumps([{"level": f.level, "code": f.code, "file": f.msg.file, "ref": f.msg.ref,
                           "detail": f.detail} for f in findings], ensure_ascii=False, indent=1))
    else:
        print(format_report(findings, stats, args.limit))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
