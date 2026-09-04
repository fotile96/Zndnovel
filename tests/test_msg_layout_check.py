"""tools/msg_layout_check.py：按引擎规则（含 layers/eboot 补丁）模拟消息窗排版。

规则出处 docs/ops/eboot-kinsoku-research-2026-09-04.md；禁则表直接取自 layers/eboot/kinsoku.toml。
"""
import pytest

from tools import msg_layout_check as mlc

HEAD, TAIL = mlc.kinsoku_tables()
P = mlc.ruby_pitch()
A25 = "一二三四五六七八九十一二三四五六七八九十一二三四五"      # 25 格


def sim(text):
    return mlc.simulate(text, head=HEAD, tail=TAIL, pitch=P)


def codes(layout, level=None):
    return [f.code for f in layout.findings if level is None or f.level == level]


# ---- 表来源 ----------------------------------------------------------------

def test_tables_come_from_the_eboot_layer():
    assert "，" in HEAD and "≫" in HEAD and "≧" in HEAD and "」" in HEAD
    assert "（" in TAIL and "≪" in TAIL and "≦" in TAIL and "「" in TAIL
    assert "ぁ" not in HEAD           # 原表里中文永不出现的项已删


# ---- 基本网格 --------------------------------------------------------------

def test_name_prefix_does_not_take_cells():
    lay = sim("【彩野】" + A25)
    assert lay.rows == [A25] and not lay.findings


def test_wrap_at_25_cells_and_underscore_r_newline():
    lay = sim(A25 + "六_r七")
    assert lay.rows == [A25, "六", "七"] and not lay.findings


def test_underscore_n_pauses_without_newline_or_page_clear():
    lay = sim("甲_n乙_n丙")
    assert lay.rows == ["甲乙丙"] and lay.pages == 3


def test_fifth_line_is_a_hard_error():
    lay = sim("甲_r乙_r丙_r丁_r戊")
    assert "page-overflow" in codes(lay, "error") and lay.overflow


def test_four_lines_exactly_is_fine():
    lay = sim("甲_r乙_r丙_r丁")
    assert not lay.findings and len(lay.rows) == 4


def test_stray_underscore_is_a_warning():
    lay = sim("甲_x乙")
    assert codes(lay) == ["stray-underscore"] and lay.rows == ["甲x乙"]


def test_buffer_limit_500_bytes():
    assert "too-long" in codes(sim("字" * 167), "error")      # 501 B
    assert "too-long" not in codes(sim("字" * 166))            # 498 B


def test_unterminated_name_bracket_is_error():
    assert codes(sim("【彩野 台词")) == ["name-unterminated"]


# ---- 禁则 -------------------------------------------------------------------

def test_head_kinsoku_hangs_comma_past_margin():
    lay = sim(A25 + "，后")
    assert lay.rows[0] == A25 + "，" and lay.rows[1] == "后"


def test_head_kinsoku_multiple_hang_and_deep_hang_warning():
    lay = sim(A25 + "……」下")
    assert lay.rows[0] == A25 + "……」" and lay.rows[1] == "下"
    assert "hang-deep" in codes(lay, "warn")            # 第 3 悬挂格


def test_tail_kinsoku_wraps_before_opening_bracket_at_col_24():
    lay = sim(A25[:24] + "（括号")
    assert lay.rows[0] == A25[:24] and lay.rows[1] == "（括号"


def test_custom_brackets_follow_tables():
    assert sim(A25 + "≫").rows[0] == A25 + "≫"
    assert sim(A25[:24] + "≦").rows[1] == "≦"


# ---- ruby -------------------------------------------------------------------

def test_ruby_units_and_centering():
    lay = sim("<记忆,jì yì>")
    rb = lay.rubies[0]
    assert rb["units"] == 5 and rb["x"] == 17 * 0 + int((34 - 5 * P) / 2) + 4
    assert lay.rows == ["记忆"] and not lay.findings


def test_fullwidth_ruby_counts_two_units():
    lay = sim("<Ｓｔｏｒｙ,故事>")
    assert lay.rubies[0]["units"] == 4


def test_ruby_negative_x_is_error():
    lay = sim("<哐,kuāng>")           # x = 4 + (17 - 25)//2 = 0 → 不为负（P=5）
    assert "ruby-negative-x" not in codes(lay)
    lay = sim("<哐,kuāngkuāng>")      # 10 单位 = 50 px → x = 4 + (17-50)/2 = -12
    assert "ruby-negative-x" in codes(lay, "error")


def test_ruby_group_past_margin_is_error():
    lay = sim(A25[:24] + "<记忆,jì yì>")
    assert "ruby-past-margin" in codes(lay, "error")


def test_adjacent_wide_ruby_overlap_warns():
    lay = sim("<哐,kuāng><咚,dōng>")
    assert "ruby-overlap" in codes(lay, "warn")


def test_ruby_unterminated_is_error():
    assert codes(sim("<记忆,jì yì")) == ["ruby-unterminated"]


def test_ruby_buffer_limits():
    assert "ruby-base-too-long" in codes(sim("<" + "字" * 34 + ",a>"), "error")   # 102 B
    assert "ruby-too-long" in codes(sim("<字," + "a" * 100 + ">"), "error")


def test_ruby_content_warnings():
    assert "ruby-halfwidth-nonpinyin" in codes(sim("<字,ji4>"), "warn")
    assert "ruby-base-space" in codes(sim("<Ｔｒｕｅ Ｃｏｌｏｒ,tc>"), "warn")
    assert "ruby-no-comma" in codes(sim("<记忆>"), "warn")


def test_ruby_on_fifth_line_is_page_overflow():
    lay = sim("甲_r乙_r丙_r丁_r<记忆,jì yì>")
    assert "page-overflow" in codes(lay, "error")


# ---- 提取 -------------------------------------------------------------------

def test_extract_vms_msg_and_card_show_literals():
    src = {
        "a.lua": 'vms(12, "NAO00010", "【直哉】「你好」")\n'
                 'msg(18003, "已写下『甲』的梗概。")\n'
                 'oCard.show(cGetFileName("card", "crd_" .. id .. "_a"), "已写下『乙』的梗概。") -- tr_line:3\n'
                 'vms(13, "NONVOICE", l1_3 .. "_r动态")\n'
                 'oCard.show(img, title .. "动态")\n',
    }
    msgs, dynamic = mlc.extract_messages(src)
    assert [(m.ref, m.text) for m in msgs] == [
        ("12", "【直哉】「你好」"), ("18003", "已写下『甲』的梗概。"), ("a:3", "已写下『乙』的梗概。")]
    assert dynamic == 2


def test_lua_unquote_handles_inject_escapes():
    assert mlc.lua_unquote(r'a\"b\\c\65') == 'a"b\\cA'


def test_check_sources_summary_counts(tmp_path):
    src = {"x.lua": 'vms(1, "NONVOICE", "' + "甲_r乙_r丙_r丁_r戊" + '")\nvms(2, "NONVOICE", "好")\n'}
    findings, stats = mlc.check_sources(src)
    assert stats["messages"] == 2 and stats["errors"] == 1 and stats["warnings"] == 0
    assert findings[0].code == "page-overflow" and findings[0].msg.ref == "1"
