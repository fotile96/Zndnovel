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


# `tools.build_context._render_anchors()` 返回的文本硬编码了一个顶层标题
# "## 三、锚点行"——那是 build_context.py 自己的编号体系里正确的第三节
# （build_context.build() 的顺序：一、冻结骨架 → 二、前缀正文 → 三、锚点行 →
# 四、术语风格口调 → 五、本批任务），但任何**其他**文档复用这个函数
# （`polish_context.render()`、`polish_amplify.scan_prompt()` 都是——它们
# 各自有自己的一套顶层标题/编号）都会撞上这个硬编码的"三"，或者在自己已经
# 去掉编号之后，让这段文本显得像一个孤零零带着编号的顶层标题。
#
# **根因处置的选择（Task 11 评审 Finding A/C 共同结论）**：不修改
# `build_context._render_anchors()` 本身——它是 P3 生产在用的钉死面
# （`tools/build_context.py` 属"按批四件套"，生产树独立 pin 版本、
# 改动需要 canary 回验；这里的标题在它自己的编号体系里是**正确**的，
# 问题只出在"被复用到别的编号体系里"这一侧），而是提供这个共享 helper，
# 由**每一个复用方**在拼自己的文档之前，把这段文本的标题降级/去编号。
# 好处：改动面永远限定在 P4 自己的模块里，`build_context.py` 的 P3 覆盖面
# 与既有行为逐字不变，不需要为这一处装订问题走 canary 流程；未来任何第三个
# 复用方（不管是不是 P4 的）都只需要调这一个函数，不需要各自发明一份
# `.replace(...)`（Task 11 修复轮初版就是每个复用方各自内联一份，抽出来
# 才能保证以后只需要改一处）。
ANCHORS_HEADING_OLD = "## 三、锚点行"
ANCHORS_HEADING_DEMOTED = "### 锚点行"


def demote_anchors_heading(anchors_text: str) -> str:
    """把 `build_context._render_anchors()` 产出文本里硬编码的顶层标题
    "## 三、锚点行" 降级成不带编号的三级标题 "### 锚点行"——读起来是调用方
    某个二级章节下的子块，而不是一段孤立的、带着别处编号体系"三"的顶层标题。
    只替换一次（`count=1`）：该字符串在 `_render_anchors()` 的产出里只会
    出现一次，就是返回文本的第一行。"""
    return anchors_text.replace(ANCHORS_HEADING_OLD, ANCHORS_HEADING_DEMOTED, 1)


def is_ignored_extra(p: Path) -> bool:
    """`p` 是否属于 verify() 反向扫描该忽略的文件系统噪声。

    **目录名判据只看祖先路径段（`p.parts[:-1]`），不含 `p` 自己的 basename**
    （Task 11 评审 Finding B 追加，修复前 `IGNORE_DIR_NAMES & set(p.parts)`
    对全部路径段一视同仁——一个恰好叫 `__pycache__` 的**普通文件**（无扩展名，
    basename 本身撞上目录名单）会被错误当成目录内容而放行，破坏名单"不能宽到
    藏住真文件"这条底线。目录名单该管的是"这个文件是不是落在一个真 `__pycache__`
    目录**之下**"，不该管"这个文件自己是不是叫这个名字"——后者如果真的发生，
    是一个反常但合法的文件名，理应被正常判成漂移，而不是被目录名单顺手放过。"""
    if p.name in IGNORE_BASENAMES:
        return True
    if p.suffix in IGNORE_SUFFIXES:
        return True
    if IGNORE_DIR_NAMES & set(p.parts[:-1]):
        return True
    return False

def _load_cfg():
    import yaml
    return yaml.safe_load((REPO / "config" / "polish.yaml").read_text(encoding="utf-8"))

CFG = _load_cfg()

def seg_dir(label) -> Path:
    return REPO / "pilot" / "polish" / label

P5_PREFIX = "p5"


def base_label(label: str):
    """P5 段别名 → P3/P4 段表 label（`p5segN-…` → `segN-…`），非别名返回 None。

    P5 二轮润色与 P4 同区间复用 `config/segments.yaml`，但段表的分区完备闸
    （`test_segments_partition_b1_to_339`）与序数连续闸不允许同区间重复入表——
    P5 段因此**不入段表**，靠本函数把别名解析回段表行；`pilot/polish/<label>/`
    目录、tag、题库等产物面用全名（p5segN-…），与 P4 目录天然不冲突。
    """
    if label.startswith(P5_PREFIX + "seg"):
        return label[len(P5_PREFIX):]
    return None


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
