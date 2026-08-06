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
