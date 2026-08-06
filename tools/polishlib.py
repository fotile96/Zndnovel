"""P4 润色 pass 公共层：配置、路径、回执尾串、编辑距离。"""
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

RUBY_RE = re.compile(r"<([^,<>]+),[^,<>]+>")
CTL_RE = re.compile(r"_[nr]")

# `polish_setup.verify()` 反向扫描（frozen/ 实际目录树里有、manifest 未登记的
# 文件）的忽略名单。这些是文件系统/工具自己产生的噪声，与 SEG 冻结内容无关：
# macOS Finder 打开 frozen/ 目录必然落一个 .DS_Store（Task 3 评审挂起的 minor，
# 本轮由 Task 11 收尾）、Windows 资源管理器同理落 Thumbs.db、Python 字节码缓存
# __pycache__/*.pyc（frozen/ 里不该有 .py，但防御性收窄不嫌多）。
# ⚠ 名单必须窄——见 CLAUDE.md「伪报淹没真信号」的教训（ruby 闸 104→5、数字闸
# 212→1）：一道稳定冤枉正确行为的闸很快会被当噪音忽略，那是「恒绿闸」的镜像；
# 但反过来，名单本身也不能宽到能借机藏住真的漂移文件——只挑逐字面/后缀精确
# 匹配的已知系统噪声，不用通配符、不用前缀匹配。
IGNORE_BASENAMES = {".DS_Store", "Thumbs.db"}
IGNORE_SUFFIXES = (".pyc",)
IGNORE_DIR_NAMES = {"__pycache__"}


def is_ignored_extra(p: Path) -> bool:
    """`p` 是否属于 verify() 反向扫描该忽略的文件系统噪声。"""
    if p.name in IGNORE_BASENAMES:
        return True
    if p.suffix in IGNORE_SUFFIXES:
        return True
    if IGNORE_DIR_NAMES & set(p.parts):
        return True
    return False

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
