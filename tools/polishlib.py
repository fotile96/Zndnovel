"""P4 润色 pass 公共层：配置、路径、回执尾串、编辑距离。"""
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

RUBY_RE = re.compile(r"<([^,<>]+),[^,<>]+>")
CTL_RE = re.compile(r"_[nr]")

def _load_cfg():
    import yaml
    return yaml.safe_load((REPO / "config" / "polish.yaml").read_text(encoding="utf-8"))

CFG = _load_cfg()

def seg_dir(label) -> Path:
    return REPO / "pilot" / "polish" / label

def strip_ctl(s: str) -> str:
    return CTL_RE.sub("", RUBY_RE.sub(lambda m: m.group(1), s or ""))

def jp_tail(s: str, n: int = None) -> str:
    return strip_ctl(s)[-(n or CFG["jp_tail_n"]):]

def edit_distance(a: str, b: str) -> int:
    # difflib opcodes：replace 记 max(删,插)，insert/delete 记其长——字符级近似 Levenshtein，
    # 用途只是「幅度分档」，不需要严格最优解。
    d = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "replace":
            d += max(i2 - i1, j2 - j1)
        elif tag in ("delete", "insert"):
            d += (i2 - i1) + (j2 - j1)
    return d

def autoclear_limit(opus_zh: str) -> int:
    return max(CFG["autoclear_abs"], int(len(strip_ctl(opus_zh)) * CFG["autoclear_ratio"]))
