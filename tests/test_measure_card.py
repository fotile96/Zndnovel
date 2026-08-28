"""tools/measure_card.py — png/card/ 卡面版面测绘（本轮只测绘，不烤字）。

覆盖点（见 build/card_layout_spec.md 与
.superpowers/sdd/2026-08-07-p4-polish-pass/card-layout-report.md）：
  1. 卡号域一致性：skeleton/cards.zh.yaml 的 196 条与 png/card/*_a.png 磁盘
     文件必须逐一对应，不能有孤儿。
  2. crd_0_d.png 必须是真正的空白模板（三个文字区一律测不出墨迹）。
  3. 边框颜色异常卡：全库唯一一张非红/粉边框卡（94）必须被抓出来，不能被
     "大多数卡都是红边框"这种多数假设悄悄吞掉。
  4. 正文折行的「「…」独占一行不与相邻行合并」规则——这是任务要求"自己复核"
     的既定裁决，必须能独立重新验证出 27/27（不含卡 145）+ 卡 145 自身 1
     处 = 28/28。**变异①**：去掉这条规则的保护，验证会不再覆盖用户点名的
     真实案例（卡 4 的选项列表），必须真红。
  5. 溢出统计绝不能被静默吞掉——空 overflow 列表必须是"检查过，确实是空"
     而不是"没检查"。**变异②**：模拟一个总是返回"未截断"的 wrap，若调用方
     不老实核对 zh_wrap 返回的 info["truncated"]，测试必须真红。
"""
import sys

import pytest
from PIL import Image, ImageFont

from tools.measure_card import (
    BODY_ZONE, CARD_145_POEM, CARD_H, CARD_W, DIVIDER_H_Y, DIVIDER_V_X,
    FONT_PATH, INTERIOR, RIGHT_ZONE, TITLE_ZONE, card_path,
    collect_ink_bbox, find_border_color_outliers, find_structural_breaks,
    is_blank_template, line_bands, load_card_domain, load_cards_jp,
    load_cards_zh, load_section_labels_zh, quote_line_rule_coverage,
    trial_wrap_bodies, trial_wrap_right_labels, trial_wrap_titles,
    wrap_body_zh, wrap_right_zh, wrap_title_zh,
)


from tools.ui_font import truetype as _ui_truetype


def _font(size):
    # **必须走 ui_font.truetype，不能裸调 ImageFont.truetype。** FONT_PATH 现在可能
    # 指向变量字体，裸调拿到的是它的默认实例（思源黑体是 ExtraLight＝权重轴最小值），
    # 于是测试量的字重和工具烤的根本不是同一档——而且不报错、不缺字，只是更细一点。
    return _ui_truetype("card", size)


# ---------------------------------------------------------------------------
# 1. 卡号域一致性
# ---------------------------------------------------------------------------

def test_card_domain_matches_disk_files_1to1():
    cards = load_card_domain()
    assert len(cards) == 196
    assert cards[0] == 1
    assert cards[-1] == 200
    # 196-199 缺号（编外卡只有 200）
    assert 196 not in cards and 197 not in cards and 198 not in cards and 199 not in cards


def test_card_domain_raises_on_disk_yaml_mismatch(tmp_path, monkeypatch):
    import yaml
    bogus = tmp_path / "cards.zh.bogus.yaml"
    bogus.write_text(yaml.dump([{"card": 1, "variant": "a", "title_zh": "x"},
                                 {"card": 99999, "variant": "a", "title_zh": "y"}]),
                      encoding="utf-8")
    with pytest.raises(ValueError):
        load_card_domain(path=str(bogus))


# ---------------------------------------------------------------------------
# 2. crd_0_d.png 空白模板验证
# ---------------------------------------------------------------------------

def test_blank_template_is_genuinely_empty():
    assert is_blank_template() is True


def test_blank_template_check_would_fail_on_a_real_card():
    # card 1 has real ink in all three zones -- sanity check that
    # is_blank_template() isn't vacuously true for any input.
    assert is_blank_template(path=card_path(1)) is False


# ---------------------------------------------------------------------------
# 3. 边框颜色异常卡
# ---------------------------------------------------------------------------

def test_border_color_outlier_is_exactly_card_94():
    cards = load_card_domain()
    outliers = find_border_color_outliers(cards)
    outlier_cards = sorted(c for c, _rgba in outliers)
    assert outlier_cards == [94]


# ---------------------------------------------------------------------------
# 4. 正文折行「「…」独占一行」规则 —— 变异①
# ---------------------------------------------------------------------------

def test_quote_line_rule_covers_27_of_27_real_structural_breaks():
    cards_zh = load_cards_zh()
    breaks = find_structural_breaks(cards_zh)  # excludes card 145 by default
    covered, not_covered = quote_line_rule_coverage(breaks)
    assert not_covered == []
    assert covered == 27
    assert len(breaks) == 27


def test_card145_contributes_the_28th_structural_break_as_its_own_exception():
    cards_zh = load_cards_zh()
    poem = cards_zh[CARD_145_POEM]["body_zh"]
    lines = poem.split("\n")
    from tools.pipelib import display_width
    poem_breaks = sum(
        1 for i in range(len(lines) - 1)
        if display_width(lines[i]) + display_width(lines[i + 1]) <= 24
    )
    assert poem_breaks == 1
    # and it's NOT covered by the quote-line rule (neither side is a
    # standalone "「...」" line) -- this is why card 145 needs its own
    # whole-card no-rewrap exception rather than being folded into the
    # quote-line rule.
    import re
    quote_re = re.compile(r"^「[^「」]*」$")
    assert not quote_re.match(lines[0])
    assert not quote_re.match(lines[1])


def test_wrap_body_zh_never_merges_a_standalone_quote_line_with_its_neighbor():
    """The exact real-data case: card 4's option list. If the merge-guard is
    removed, '「想不起来」'+'「约好了」' (combined display width 22 <= 24)
    would get glued into one re-wrapped run and the option-per-line
    structure would be destroyed."""
    font = _font(9)
    text = "「想不起来」\n「约好了」\n「没有约」\n有以上分支展开。"
    paragraphs, info = wrap_body_zh(4, text, font, max_width=200, max_lines=7)
    assert len(paragraphs) == 1
    lines = paragraphs[0]
    # each quote line must survive as ITS OWN rendered line, never fused
    # with a neighboring quote line even though there's plenty of width.
    assert "「想不起来」" in lines
    assert "「约好了」" in lines
    assert "「没有约」" in lines
    assert not any("」「" in line for line in lines)  # no two quotes glued


def test_wrap_body_zh_MUTATION_without_quote_guard_would_merge_options():
    """Pins the mutation the task asks for: simulate "quote-line rule
    removed" by feeding the concatenated (no internal \\n) text directly
    through the plain wrapper the way a version WITHOUT the guard would.
    This must produce a DIFFERENT (merged) result than the guarded
    function above -- i.e. the guard is load-bearing, not a no-op."""
    from tools.zh_wrap import wrap as plain_wrap
    font = _font(9)
    measurer = lambda s: __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(
        Image.new("RGBA", (1, 1))).textlength(s, font=font)
    naive_concat = "".join(["「想不起来」", "「约好了」", "「没有约」", "有以上分支展开。"])
    naive_lines, _info = plain_wrap(naive_concat, 200, max_lines=7, measurer=measurer)
    guarded_paragraphs, _info2 = wrap_body_zh(
        4, "「想不起来」\n「约好了」\n「没有约」\n有以上分支展开。",
        font, max_width=200, max_lines=7)
    guarded_lines = guarded_paragraphs[0]
    # The naive (no-guard) wrap is free to glue quote-lines together on one
    # line since width easily allows it; the guarded wrap must not.
    assert naive_lines != guarded_lines
    assert any("」「" in line for line in naive_lines), (
        "test setup assumption broken: naive wrap no longer merges quotes, "
        "so it can no longer prove the guard matters"
    )
    assert not any("」「" in line for line in guarded_lines)


def test_wrap_right_zh_never_merges_structural_segments():
    font = _font(9)
    segs, info = wrap_right_zh(2, "章节 1\n梗概", font, max_width=200)
    assert len(segs) == 2
    assert segs[0] == ["章节 1"]
    assert segs[1] == ["梗概"]


# ---------------------------------------------------------------------------
# 5. 溢出统计不能被静默吞掉 —— 变异②
# ---------------------------------------------------------------------------

def test_trial_wrap_titles_overflow_field_present_even_when_empty():
    cards_zh = load_cards_zh()
    report = trial_wrap_titles(cards_zh, font_size=11, max_width=176)
    assert "overflow" in report
    assert isinstance(report["overflow"], list)


def test_trial_wrap_titles_surfaces_a_synthetic_overflow():
    """A title text engineered to be far too long for the box MUST show up
    in the overflow list -- this is the never-silent gate itself."""
    cards_zh = {1: {"title_zh": "测" * 200, "body_zh": ""}}
    report = trial_wrap_titles(cards_zh, font_size=11, max_width=176)
    assert len(report["overflow"]) == 1
    assert report["overflow"][0]["card"] == 1


def test_wrap_title_zh_MUTATION_ignoring_truncated_flag_would_hide_overflow():
    """Pins: a caller that does NOT check info["truncated"] (e.g. only
    checks whether `lines` is non-empty, which is always true) would never
    detect overflow. Assert the real info dict actually flags it, i.e. the
    signal a correct caller depends on is genuinely present -- if
    wrap_title_zh's info stopped reporting truncated=True on this input,
    this test goes red."""
    font = _font(11)
    lines, info = wrap_title_zh("测" * 200, font, max_width=176, max_lines=1)
    assert info["truncated"] is True
    assert info["dropped"] != ""


def test_trial_wrap_bodies_reports_line_count_overflow_not_just_segment_overflow():
    """A body whose EACH INDIVIDUAL segment wraps fine within the zone's own
    max_lines cap (so no segment-level `truncated` fires) can still need
    MORE total lines, SUMMED ACROSS SEGMENTS, than the zone physically has
    room for -- because wrap_body_zh grants each quote-line/prose segment
    its own independent max_lines allowance (a modeling necessity: a quote
    segment and a prose segment don't share one zh_wrap() call), which does
    NOT by itself guard the zone-wide total. This is exactly the "needs an
    8th line but nothing individually truncated" failure mode
    line_count_overflow exists to catch -- four standalone quote lines (4
    segments, 1 line each, nowhere near truncating) plus a prose tail that
    alone fits in under 7 lines (so it doesn't truncate either) must still
    be caught when 4 + prose_lines > 7."""
    long_prose = "".join(f"第{i}行内容测试" for i in range(10))  # ~60 chars
    body = "「A」\n「B」\n「C」\n「D」\n" + long_prose
    cards_zh = {1: {"title_zh": "x", "body_zh": body}}
    report = trial_wrap_bodies(cards_zh, font_size=9, max_width=110, max_lines=7,
                                cards=[1])
    assert report["overflow"] == [], (
        "test setup assumption broken: a segment truncated on its own, so "
        "this no longer isolates the zone-wide-sum failure mode"
    )
    assert report["line_count_overflow"] != []
    assert report["line_count_overflow"][0]["card"] == 1


def test_trial_wrap_right_labels_flags_missing_zh_label_never_silently_skips():
    cards_jp = {1: {"title_jp": "x", "body_jp": "", "section_label": "全新未登记标签"}}
    labels_zh = {}  # deliberately missing the mapping
    report = trial_wrap_right_labels(cards_jp, labels_zh, font_size=8,
                                      max_width=53, cards=[1])
    assert report["missing_label"] == [{"card": 1, "jp_label": "全新未登记标签"}]


# ---------------------------------------------------------------------------
# 6. 几何常量与真实素材的墨迹交叉核对（防止 TEXT ZONE 常量漂移不被发现）
# ---------------------------------------------------------------------------

def test_all_196_real_cards_have_single_line_title_ink():
    cards = load_card_domain()
    mismatches = []
    for c in cards:
        im = Image.open(card_path(c)).convert("RGBA")
        bands = line_bands(im, TITLE_ZONE)
        if len(bands) != 1:
            mismatches.append((c, len(bands)))
    assert mismatches == []


def test_ink_never_exceeds_zone_bounds_for_sampled_real_cards():
    for c in [1, 2, 3, 90, 145, 180, 182, 200]:
        im = Image.open(card_path(c)).convert("RGBA")
        for zone in (TITLE_ZONE, BODY_ZONE, RIGHT_ZONE):
            bbox = collect_ink_bbox(im, zone)
            if bbox is None:
                continue
            x0, y0, x1, y1 = bbox
            zx0, zy0, zx1, zy1 = zone
            assert zx0 <= x0 and x1 < zx1, (c, zone, bbox)
            assert zy0 <= y0 and y1 < zy1, (c, zone, bbox)


def test_geometry_constants_are_internally_consistent():
    assert INTERIOR == (10, 10, 202, 138)
    assert TITLE_ZONE[3] == DIVIDER_H_Y
    assert BODY_ZONE[1] == DIVIDER_H_Y + 1
    assert RIGHT_ZONE[1] == DIVIDER_H_Y + 1
    assert BODY_ZONE[2] < RIGHT_ZONE[0]  # body ends strictly before divider col
    assert DIVIDER_V_X > BODY_ZONE[2] and DIVIDER_V_X < RIGHT_ZONE[0]
    assert (CARD_W, CARD_H) == (212, 148)
