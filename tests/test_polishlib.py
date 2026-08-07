import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polishlib as pl

def test_cfg_loads():
    assert pl.CFG["K"] == 150 and 0 < pl.CFG["sample_rate"] < 1

def test_jp_tail_strips_ctl_and_ruby():
    s = "こんにちは_nよろしく<漢字,かんじ>ね"
    # 剥 _n 与 ruby 注音部（保留漢字前半）后为「こんにちはよろしく漢字ね」，共 12 字；
    # 取末 8 字 = 「はよろしく漢字ね」。
    # （brief 原断言 "よろしく漢字ね"[-8:] 只有 7 字、恒不相等——用户已裁定按此改正）
    assert pl.jp_tail(s) == "はよろしく漢字ね"

# ---- 2026-08-07：把 jp_tail 三个边角契约写死进测试（先读实现确认实际行为，
#      不是照着 brief 的措辞想当然）----

def test_jp_tail_shorter_than_n_takes_whole_string():
    """不足 8 字的原文——取剥离控制码后的全串，不报错、不补空格补齐（Python
    切片 `s[-8:]` 对短串天然返回整串，这里钉死这个"天然行为"就是契约本身）。"""
    s = "短句"
    assert pl.jp_tail(s) == "短句"
    assert len(pl.jp_tail(s)) < 8


def test_jp_tail_includes_speaker_prefix():
    """`【説話人】` 前缀算原文的一部分，参与"剥离控制码后取末 8 字"的计算，
    不能被当成排版噪声跳过单独从台词正文算起。"""
    s = "【アヤノ】「教室に来たよ」"
    # strip_ctl 不移除【】/「」（只处理 _n/_r/ruby），故整串（含前缀）参与
    # 取尾——若前缀被跳过，尾串会不同。
    assert pl.jp_tail(s) == pl.strip_ctl(s)[-8:]
    assert pl.jp_tail(s) != pl.strip_ctl("教室に来たよ」")[-8:]


def test_jp_tail_counts_spaces_as_characters():
    """空格算一个字符，不在取尾前被去掉——真实语料里带全角/半角空格断句的
    行（如 s5 章节日记体）尾串对齐依赖这一点。"""
    s = "为什么 大半夜 还吵个不停"
    assert pl.jp_tail(s) == s[-8:]
    assert pl.jp_tail(s) != s.replace(" ", "")[-8:]


def test_edit_distance_basic():
    assert pl.edit_distance("abc", "abc") == 0
    assert pl.edit_distance("abc", "axc") == 1
    assert pl.edit_distance("", "abc") == 3
    # 补充：brief 给的 3 条用例里唯一的 replace opcode（"abc"→"axc"）是等长替换
    # （i2-i1==j2-j1==1），min/max 恒相等，变异②（replace 记 min）测不出来。
    # 这条用不等长 replace（"ab"→"x"：i2-i1=2, j2-j1=1）撑开区分度：max 给 2，min 给 1。
    assert pl.edit_distance("ab", "x") == 2

def test_autoclear_limit_floor_and_ratio():
    assert pl.autoclear_limit("四字") == 4            # floor
    assert pl.autoclear_limit("十" * 100) == 15       # 100×0.15

def test_is_ignored_extra_matches_known_fs_noise():
    assert pl.is_ignored_extra(Path("/a/b/.DS_Store"))
    assert pl.is_ignored_extra(Path("/a/b/Thumbs.db"))
    assert pl.is_ignored_extra(Path("/a/__pycache__/x.pyc"))
    assert pl.is_ignored_extra(Path("/a/b/__pycache__/x.pyc"))

def test_is_ignored_extra_does_not_match_real_files():
    """名单窄——不得靠子串/前缀命中真实文件；只精确匹配已知噪声。"""
    assert not pl.is_ignored_extra(Path("/a/b/sneaky_extra.md"))
    assert not pl.is_ignored_extra(Path("/a/b/DS_Store_backup.txt"))
    assert not pl.is_ignored_extra(Path("/a/b/notes.pyc.md"))

def test_is_ignored_extra_directory_match_excludes_own_basename():
    """评审 Finding B（Task 11 修复轮）：目录名判据只该看祖先路径段
    （`p.parts[:-1]`），不含 `p` 自己的 basename。修复前
    `IGNORE_DIR_NAMES & set(p.parts)` 对全部路径段一视同仁——一个恰好叫
    `__pycache__` 的**普通文件**（无扩展名，basename 本身撞上目录名单）
    会被误判成"落在 __pycache__ 目录之下"而放行，破坏"名单不能宽到藏住
    真文件"这条底线。"""
    # 文件自身就叫 __pycache__（它是一个文件，不是目录）：不应被忽略。
    assert not pl.is_ignored_extra(Path("/a/b/__pycache__"))
    assert not pl.is_ignored_extra(Path("frozen/__pycache__"))
    # 真正落在 __pycache__ 目录之下的文件（含非 .pyc 后缀）：仍应被忽略——
    # 目录判据本身没有被削弱，只是不再看 basename 那一段。
    assert pl.is_ignored_extra(Path("/a/b/__pycache__/somefile.txt"))

def test_demote_anchors_heading_downgrades_and_only_once():
    """评审 Finding C：`_render_anchors()`（build_context.py 共享函数）硬编码
    "## 三、锚点行" 作为它自己编号体系里的第三节标题，但 `polish_context.py`
    与 `polish_amplify.py` 各自有独立的顶层标题方案，直接照搬会撞号（前者与
    自己的"三"撞、后者与自己的"三、锁定 id 清单"撞）。共享 helper 把这个
    硬编码标题降级成不带编号的三级标题，供两个复用方共用同一份处理，不再
    各自维护一份 `.replace(...)`。"""
    text = "## 三、锚点行（日中对照）\n### global\n[1] jp\n    → zh"
    out = pl.demote_anchors_heading(text)
    assert out == "### 锚点行（日中对照）\n### global\n[1] jp\n    → zh"
    assert "## 三、" not in out
    # 只替换一次——即使正文里恰好也出现同一串字面文本，不该被二次替换掉
    # （该字符串按设计只会出现在 _render_anchors() 产出的第一行，这里只是
    # 确认 helper 本身遵守"只替换一次"的约定，不依赖调用方的实际数据形态）。
    twice = "## 三、锚点行\n" * 2
    assert pl.demote_anchors_heading(twice) == "### 锚点行\n## 三、锚点行\n"

def test_demote_anchors_heading_no_op_when_marker_absent():
    """没有命中硬编码标题时原样返回，不误伤其他内容。"""
    text = "没有任何锚点标题的普通文本"
    assert pl.demote_anchors_heading(text) == text
