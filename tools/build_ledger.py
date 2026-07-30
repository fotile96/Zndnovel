"""把 lua_scripts 解析为 data/ledger.jsonl（原文账本）与 data/ledger_extra.jsonl。"""
import re

try:
    from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS

FUNC_RE = re.compile(r'^\s*([A-Za-z_][\w.]*)\s*=\s*function')
VMS_RE = re.compile(r'vms\((\d+), "([A-Z0-9]+)", (.+)\)$')
TR_LINE_RE = re.compile(r'\s*--\s*tr_line:\d+\s*$')


def parse_vms_lines(stem: str, text: str) -> list[dict]:
    rows = []
    func = ""
    for line in text.splitlines():
        m = FUNC_RE.match(line)
        if m:
            func = m.group(1)
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
            "file": stem, "func": func, "literal": literal,
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
    if row["file"] in SYS_FILES or row["chapter"] == "sys" or key in AMBIENT_FUNC_EXCEPTIONS:
        row["kind"] = "ambient"
    else:
        row["kind"] = "narrative"
    return row
