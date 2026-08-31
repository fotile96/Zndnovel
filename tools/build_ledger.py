"""把 lua_scripts 解析为 data/ledger.jsonl（原文账本）与 data/ledger_extra.jsonl。"""
import re

try:
    from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS, NARRATIVE_FUNC_EXCEPTIONS
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS, NARRATIVE_FUNC_EXCEPTIONS

# 函数声明：兼容两代反编译基座的两种形状——
#   旧（pyluadec）  `NAME = function(...)`（顶部集中 local 声明 + 全局式赋值）
#   新（refactor）  `local NAME = function(...)`（890 处）与 `NAME = function(...)`（317 处）
# 入栈的缩进必须取**声明行缩进**（group 1）而非名字列号：新基座的 `end` 与声明行同缩进，
# 若沿用名字列号，`local ` 前缀会把名字推后 6 列，函数永远配不上 end。
# 依据：pyluadec-refactor/docs/runbooks/zndnovel-naming-migration.md §1。
FUNC_RE = re.compile(r'^(\s*)(?:local\s+)?([A-Za-z_][\w.]*)\s*=\s*function')
END_RE = re.compile(r'^(\s*)end\b')
VMS_RE = re.compile(r'vms\((\d+), "([A-Z0-9]+)", (.+)\)$')
TR_LINE_RE = re.compile(r'\s*--\s*tr_line:\d+\s*$')
# 无语义的残余局部名，_owner_func 找真实归属时要跳过：
# 旧基座 v\d+/p\d+，新基座 l<depth>_<reg>（例 l1_2）与 u\d+。两代并存。
BARE_VN_RE = re.compile(r'^(?:v\d+|p\d+|l\d+_\d+|u\d+)$')


def _owner_func(stack: list[tuple[str, int]]) -> str:
    """从栈顶（最内层）向外找第一个不匹配 ^v\\d+$ 的名字；全是裸 vN 则取最外层；栈空则 ""。"""
    if not stack:
        return ""
    for name, _indent in reversed(stack):
        if not BARE_VN_RE.match(name):
            return name
    return stack[0][0]


def parse_vms_lines(stem: str, text: str) -> list[dict]:
    rows = []
    stack: list[tuple[str, int]] = []  # (函数名, 该行前导空白长度)，嵌套栈
    for lineno, line in enumerate(text.splitlines(), 1):
        m = FUNC_RE.match(line)
        if m:
            stack.append((m.group(2), len(m.group(1))))   # (函数名, 声明行缩进)
            continue
        m_end = END_RE.match(line)
        if m_end and stack and len(m_end.group(1)) == stack[-1][1]:
            stack.pop()
            continue
        s = TR_LINE_RE.sub("", line.strip())
        m = VMS_RE.search(s)
        if not m:
            continue
        arg = m.group(3).strip()
        literal = arg.startswith('"') and arg.endswith('"') and '" ..' not in arg and '.. "' not in arg
        jp = arg[1:-1] if literal else arg
        rows.append({
            "id": int(m.group(1)), "jp": jp, "voice": m.group(2),
            "file": stem, "func": _owner_func(stack), "literal": literal,
            # line：该 vms 在 lua 源文件里的行号（1-based）。F7——单元内的 id 排序
            # 若按消息号，后补的行会错位；(file, line) 才是脚本真实执行顺序。
            # 错位规模有两个都对但口径不同的数，引用时务必带上口径：
            #   47/16529（0.28%，P2 记录的数）＝ 按 lua 文件分组、按 line 排，数
            #     「id 递减」的相邻对；分母 16529 = 16749 行 − 220 个文件，是每文件
            #     相邻对总数。衡量「账本里有多少处后补行」。
            #   21/16248（0.13%，见 gen_timeline 的注释）＝ 按 timeline 单元分组，
            #     数「line 递减」的相邻对。衡量「产物里真正错位的相邻对」——运维
            #     核对段边界 timeline 再生差异时用的是这个数。
            # 仅新增字段，build() 的全局排序仍按 id 不变。
            "line": lineno,
        })
    return rows


CHAPTER_RE = re.compile(r'^snr_([se]\d)_10_(s|f[abc]?)$')


def chapter_of(stem: str) -> str:
    m = CHAPTER_RE.match(stem)
    if m:
        return m.group(1) + m.group(2)
    if stem.startswith("snr_crd_"):
        return "crd"
    return "sys"


def classify(row: dict) -> dict:
    row["chapter"] = chapter_of(row["file"])
    key = f'{row["file"]}:{row["func"]}'
    if key in NARRATIVE_FUNC_EXCEPTIONS:
        row["kind"] = "narrative"
    elif row["file"] in SYS_FILES or row["chapter"] == "sys" or key in AMBIENT_FUNC_EXCEPTIONS:
        row["kind"] = "ambient"
    else:
        row["kind"] = "narrative"
    return row


PLOT_TITLE_RE = re.compile(r'^plotTitle\[(\d+)\] = "(.*)"')
SCENE_TITLE_RE = re.compile(r'scene_[\w]+\((?:doScriptScene|p0), "([^"]*)"')
SAVEDATA_RE = re.compile(r'savedataTitle\("([^"]*)", "([^"]*)"\)')
CARD_MSG_RE = re.compile(r'oCard\.show\(.+, "([^"]+)"\)$')


def parse_extra(stem: str, text: str) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = TR_LINE_RE.sub("", raw.strip())
        if m := PLOT_TITLE_RE.match(line):
            rows.append({"key": f"plotTitle:{m.group(1)}", "jp": m.group(2),
                         "kind": "plot_title", "file": stem})
        elif m := SAVEDATA_RE.search(line):
            for i in (1, 2):
                rows.append({"key": f"{stem}:{lineno}:{i}", "jp": m.group(i),
                             "kind": "savedata", "file": stem})
        elif m := CARD_MSG_RE.search(line):
            rows.append({"key": f"{stem}:{lineno}", "jp": m.group(1),
                         "kind": "card_msg", "file": stem})
        elif m := SCENE_TITLE_RE.search(line):
            rows.append({"key": f"{stem}:{lineno}", "jp": m.group(1),
                         "kind": "scene_title", "file": stem})
    return rows


def build(script_dir):
    ledger, extra = [], []
    for path in sorted(script_dir.glob("*.lua")):
        text = path.read_text(encoding="utf-8")
        stem = path.stem
        ledger += [classify(r) for r in parse_vms_lines(stem, text)]
        extra += parse_extra(stem, text)
    ledger.sort(key=lambda r: r["id"])
    extra.sort(key=lambda r: (r["kind"], r["key"]))
    ids = [r["id"] for r in ledger]
    assert len(ids) == len(set(ids)), "vms ID 出现重复"
    return ledger, extra


def main(argv=None):
    import argparse
    from tools.pipelib import REPO, DATA, write_jsonl, read_jsonl
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(DATA))
    ap.add_argument("--script-dir", default=None,
                    help="反编译语料目录（默认仓库 lua_scripts/）——换基座对账时指向新产物")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    from pathlib import Path
    out = Path(args.out_dir)
    ledger, extra = build(Path(args.script_dir) if args.script_dir else REPO / "lua_scripts")
    if args.report:
        from collections import Counter
        by_file = Counter((r["file"], r["kind"]) for r in ledger)
        for (f, k), n in sorted(by_file.items()):
            print(f"{f:24s} {k:9s} {n}")
        top = Counter(f'{r["file"]}:{r["func"]}' for r in ledger
                      if r["kind"] == "ambient").most_common(20)
        print("\n-- ambient 函数 TOP20 --")
        for name, n in top:
            print(f"{n:5d}  {name}")
        return 0
    if args.check:
        same = (read_jsonl(out / "ledger.jsonl") == ledger
                and read_jsonl(out / "ledger_extra.jsonl") == extra)
        print("check:", "OK" if same else "MISMATCH")
        return 0 if same else 1
    write_jsonl(out / "ledger.jsonl", ledger)
    write_jsonl(out / "ledger_extra.jsonl", extra)
    n_amb = sum(1 for r in ledger if r["kind"] == "ambient")
    print(f"ledger={len(ledger)} (ambient={n_amb})  extra={len(extra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
