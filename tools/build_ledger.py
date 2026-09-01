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
# ⚠ 旧基座的 `p0` 形式已随基座迁移消失（实测 lua_scripts 全库 0 处，452 处一律是
# `doScriptScene`）。留着一个永不命中的分支只会让人以为两种形状都还在。
SCENE_TITLE_RE = re.compile(r'scene_[\w]+\(doScriptScene, "([^"]*)"')
SAVEDATA_RE = re.compile(r'savedataTitle\("([^"]*)", "([^"]*)"\)')
CARD_MSG_RE = re.compile(r'oCard\.show\(.+, "([^"]+)"\)$')
# ── 以下四类是 2026-09-01 补的，此前**整整漏在账本外**（见 SIMPLE_EXTRA 的说明）──
#: `gameSave.sceneName = "放課後の教室"`——Story 时间轴上显示的场景名。
SCENE_NAME_RE = re.compile(r'gameSave\.sceneName = "([^"]*)"')
#: `gameSave.sectionName = "１：Ｓｔｏｒｙ"`——存档界面的章节标签。
SECTION_NAME_RE = re.compile(r'gameSave\.sectionName = "([^"]*)"')
#: `scene_s7f_dispatch_v52("その『お話』の題名は――", 104, l1_1, 10)`
#: ——递卡段的提示语，文本在**第一参**（与 scene_title 的「第二参」正好相反）。
DISPATCH_TEXT_RE = re.compile(r'scene_[A-Za-z0-9_]+_dispatch_v\d+\("([^"]*)"')
#: 单参 `msg("まだ一冊も取得していません。")`——`(?<![A-Za-z0-9_])` 挡住 `vms(`/`xmsg(`。
MSG_TEXT_RE = re.compile(r'(?<![A-Za-z0-9_])msg\("([^"]*)"\)')

#: extra 轨里「一行一个可译串、键就是 `文件:行号`」的构造，**按序匹配、先中先得**。
#:
#: ⚠ **这张表是 `parse_extra` 与 `inject_lua._inject_body` 共用的，别再拆成两条
#: elif 链。** 拆开正是 41 条玩家可见文本漏译的成因：两边各写一份，
#: `add_tr_line_markers` 又按「含全角串且非 vms」这个**更宽**的判据打标记，于是
#: 「标了 tr_line 却没有账本键」的行悄悄堆到 51 条，注入期既不报缺译也不报错
#: ——账本里根本没有这个键，无从缺起。`uncovered_tr_lines()` 现在把这个洞钉死。
SIMPLE_EXTRA = [
    ("card_msg", CARD_MSG_RE),
    ("scene_title", SCENE_TITLE_RE),
    ("scene_name", SCENE_NAME_RE),
    ("section_name", SECTION_NAME_RE),
    ("dispatch_text", DISPATCH_TEXT_RE),
    ("msg_text", MSG_TEXT_RE),
]


def parse_extra(stem: str, text: str) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = TR_LINE_RE.sub("", raw.strip())
        if m := PLOT_TITLE_RE.match(line):
            rows.append({"key": f"plotTitle:{m.group(1)}", "jp": m.group(2),
                         "kind": "plot_title", "file": stem})
            continue
        if m := SAVEDATA_RE.search(line):
            for i in (1, 2):
                rows.append({"key": f"{stem}:{lineno}:{i}", "jp": m.group(i),
                             "kind": "savedata", "file": stem})
            continue
        for kind, rx in SIMPLE_EXTRA:
            if m := rx.search(line):
                rows.append({"key": f"{stem}:{lineno}", "jp": m.group(1),
                             "kind": kind, "file": stem})
                break
    return rows


def uncovered_tr_lines(stem: str, text: str) -> list[tuple[int, str]]:
    """带 `-- tr_line:N` 标记、却没能产出账本键的行。**应当恒为空。**

    两套识别器的口径必须一致：`migrate_base.should_mark` 负责标记「这行有可译文本」，
    `parse_extra` 负责给它一个键。标了却没键 ＝ 这段文字**永远不会被翻译**，而且
    整条管线一声不吭——注入期只会报「账本里的键缺译」，账本里压根没有的键报不出来。
    """
    covered = set()
    for r in parse_extra(stem, text):
        parts = r["key"].split(":")
        if len(parts) > 1 and parts[1].isdigit():
            covered.add(int(parts[1]))
    out = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if "-- tr_line:" not in raw or lineno in covered:
            continue
        line = TR_LINE_RE.sub("", raw.strip())
        if PLOT_TITLE_RE.match(line):      # plotTitle 的键不带行号，另算
            continue
        out.append((lineno, line))
    return out


def build(script_dir):
    ledger, extra, holes = [], [], []
    for path in sorted(script_dir.glob("*.lua")):
        text = path.read_text(encoding="utf-8")
        stem = path.stem
        ledger += [classify(r) for r in parse_vms_lines(stem, text)]
        extra += parse_extra(stem, text)
        holes += [(stem, n, s) for n, s in uncovered_tr_lines(stem, text)]
    ledger.sort(key=lambda r: r["id"])
    extra.sort(key=lambda r: (r["kind"], r["key"]))
    ids = [r["id"] for r in ledger]
    assert len(ids) == len(set(ids)), "vms ID 出现重复"
    # 标了 tr_line 却没有账本键 ＝ 那段文字永远不会被翻译，且全程一声不吭。
    # 宁可在这里炸掉：账本是整条译文管线的入口，入口漏了后面全是白做。
    assert not holes, (
        f"{len(holes)} 行带 tr_line 标记却没进 extra 账本，"
        f"parse_extra 少一条识别规则：\n" +
        "\n".join(f"  {f}:{n}  {s[:70]}" for f, n, s in holes[:10]))
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
