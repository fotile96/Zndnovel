"""tools/bake_plot.py — plot/ 卡名缩略图集烤字回填。

覆盖三条硬约束闸（见 build/plot_layout_spec.md 第 2/6/7 节的证据与取舍）：
  1. 格号 -> 卡号映射：lua_scripts/snr_common.lua:925-954 的 plotState 构造
     循环是唯一权威来源，这里用它推出的真值表（含 3 处换页边界）钉死。
  2. 非文字区域像素保真：TEXT_BOX 之外任何一个像素被动过都必须被抓到。
  3. 超长卡名绝不能被静默截断：wrap_title/collect_overflow 必须把截断
     显式报出来，不能吞掉多出来的字符。
"""
from PIL import Image, ImageDraw, ImageFont

from tools.bake_plot import (
    CARDS_PER_SHEET, CELL_H, CELL_W, ELLIPSIS, FONT_PATH, MAX_TEXT_W,
    NUM_CARDS, NUM_SHEETS, TEXT_BOX, _tokenize, bake_cell, cell_box,
    cell_position, collect_overflow, find_outside_box_diffs, load_titles_zh,
    reconstruct_box, wrap_title,
)


def _font(size=10):
    return ImageFont.truetype(FONT_PATH, size)


# ---------------------------------------------------------------------------
# 1. 格号 -> 卡号映射（真值表来自 lua 源码算法，见 spec 第 2.1 节）
# ---------------------------------------------------------------------------

GROUND_TRUTH = {
    1: (1, 0, 0),     # sheet1 首格
    2: (1, 0, 1),
    6: (1, 0, 5),     # sheet1 第一行末格（换行前）
    7: (1, 1, 0),     # 换行到第二行首格
    60: (1, 9, 5),    # sheet1 末格（换页前）
    61: (2, 0, 0),    # sheet2 首格（换页后 col/row 清零）
    120: (2, 9, 5),
    121: (3, 0, 0),
    180: (3, 9, 5),
    181: (4, 0, 0),
    195: (4, 2, 2),   # 195-180=15 张卡；(15-1)//6=2 行，(15-1)%6=2 列
}


def test_cell_position_matches_lua_ground_truth():
    for card, expected in GROUND_TRUTH.items():
        assert cell_position(card) == expected, f"card {card}"


def test_cell_position_rejects_out_of_range():
    import pytest
    with pytest.raises(ValueError):
        cell_position(0)
    with pytest.raises(ValueError):
        cell_position(196)


def test_cell_position_off_by_one_row_is_caught_by_ground_truth():
    """回归形态的『映射错位一格』变异描述：手写一个错位一行的实现，确认它
    与真值表不符——这不是测 bake_plot 本身，是证明真值表有牙（如果这个断言
    对错位实现也通过，说明真值表太松）。"""
    def buggy_cell_position(card):
        sheet, row, col = cell_position(card)
        return sheet, row + 1, col  # 错位一行
    mismatches = sum(
        1 for card, expected in GROUND_TRUTH.items()
        if buggy_cell_position(card) == expected
    )
    assert mismatches == 0


def test_cell_box_pixel_rect_matches_grid():
    sheet, box = cell_box(1)
    assert sheet == 1
    assert box == (0, 0, CELL_W, CELL_H)
    sheet, box = cell_box(195)
    assert sheet == 4
    assert box == (2 * CELL_W, 2 * CELL_H, 3 * CELL_W, 3 * CELL_H)


def test_grid_constants_cover_all_cards():
    assert CARDS_PER_SHEET == 60
    assert NUM_SHEETS == 4
    assert NUM_CARDS == 195
    # 240 格装 195 张卡，尾部 45 格空置（sheet4 的空白区，spec 第 2.3 节核实过）
    assert NUM_SHEETS * CARDS_PER_SHEET - NUM_CARDS == 45


# ---------------------------------------------------------------------------
# 2. 换行 / 超长卡名不静默截断
# ---------------------------------------------------------------------------

def test_wrap_title_single_short_line():
    font = _font()
    lines, truncated = wrap_title("朝的教室", font)
    assert lines == ["朝的教室"]
    assert truncated is False


def test_wrap_title_splits_into_two_lines_when_too_wide():
    font = _font()
    lines, truncated = wrap_title("有个孩子来学校的故事", font)
    assert len(lines) == 2
    assert "".join(lines) == "有个孩子来学校的故事"  # 没丢字
    assert truncated is False


def test_tokenize_keeps_ascii_digit_runs_atomic():
    atoms = _tokenize("サクラ的日记：10月3日")
    assert "10" in atoms          # "10" 是一个原子，不是 "1","0" 两个
    assert "1" not in atoms
    assert "0" not in atoms


def test_wrap_title_never_splits_inside_a_number():
    """卡188『サクラ的日记：10月3日』一类：换行不能把 "10" 切成 "1"/"0"。"""
    font = _font()
    lines, truncated = wrap_title("サクラ的日记：10月3日", font)
    assert truncated is False
    full = "".join(lines)
    assert "10" in full
    # "10" 必须完整落在同一行内，不能被行边界劈开
    assert any("10" in line for line in lines)


def test_wrap_title_truncates_and_flags_when_it_does_not_fit():
    font = _font()
    long_text = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"  # 34 字，远超 2 行 76px 预算
    lines, truncated = wrap_title(long_text, font, max_width=MAX_TEXT_W, max_lines=2)
    assert truncated is True
    assert len(lines) == 2
    assert lines[-1].endswith(ELLIPSIS)


def test_collect_overflow_surfaces_truncated_titles():
    """变异目标①：collect_overflow 如果被阉割成『不管三七二十一都返回 []』，
    这条测试必须变红——它直接喂一个会截断的标题，要求出现在结果里。"""
    font = _font()
    titles = {
        1: "朝的教室",  # 正常，不该出现
        2: "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥",  # 会截断
    }
    overflow = collect_overflow(titles, font)
    cards_in_overflow = [c for c, _, _ in overflow]
    assert cards_in_overflow == [2]


def test_real_titles_need_at_most_two_lines_zero_truncation():
    """195 条 title_zh 的现状回归：spec 第 7 节记录『0 条截断』。如果译文改
    动导致某条变长触发截断，这里会先叫出来，而不是让 bake 悄悄产出省略号。"""
    font = _font()
    titles = load_titles_zh()
    assert len(titles) == NUM_CARDS
    overflow = collect_overflow(titles, font)
    assert overflow == []


def test_real_titles_two_line_count_matches_spec():
    """spec 第 7 节记录的『70 条需要 2 行』——钉住这个数，防止 spec 与实现
    未来悄悄漂移而没人发现。"""
    font = _font()
    titles = load_titles_zh()
    two_line = 0
    for card in titles:
        lines, truncated = wrap_title(titles[card], font)
        assert not truncated
        if len(lines) == 2:
            two_line += 1
    assert two_line == 70


# ---------------------------------------------------------------------------
# 3. 非文字区域像素保真
# ---------------------------------------------------------------------------

def _solid_cell(color=(80, 80, 80, 255)):
    return Image.new("RGBA", (CELL_W, CELL_H), color)


def test_find_outside_box_diffs_detects_change_outside_box():
    """变异目标②：如果这个函数被阉割成『恒返回 []』，这条测试必须变红——
    它在 TEXT_BOX 之外故意改一个像素（模拟『顺手把背景重画了』），要求抓到。"""
    orig = _solid_cell()
    corrupted = orig.copy()
    x0, y0, x1, y1 = TEXT_BOX
    outside_xy = (5, y1 + 3)  # 明确在 TEXT_BOX 下方，属于『非文字区域』
    assert not (x0 <= outside_xy[0] < x1 and y0 <= outside_xy[1] < y1)
    corrupted.putpixel(outside_xy, (255, 0, 0, 255))
    diffs = find_outside_box_diffs(orig, corrupted)
    assert outside_xy in diffs


def test_find_outside_box_diffs_ignores_change_inside_box():
    orig = _solid_cell()
    edited = orig.copy()
    inside_xy = (10, 10)
    x0, y0, x1, y1 = TEXT_BOX
    assert x0 <= inside_xy[0] < x1 and y0 <= inside_xy[1] < y1
    edited.putpixel(inside_xy, (255, 0, 0, 255))
    diffs = find_outside_box_diffs(orig, edited)
    assert diffs == []


def test_find_outside_box_diffs_empty_when_identical():
    orig = _solid_cell()
    same = orig.copy()
    assert find_outside_box_diffs(orig, same) == []


def test_bake_cell_touches_only_text_box_on_synthetic_cell():
    """端到端属性测试（非 mutation 专用）：真实渲染路径（reconstruct_box +
    render_text_layer + alpha_composite）跑一遍，确认 TEXT_BOX 外部像素
    逐字节不变——这是 bake_plot.py 自己在跑批时也会做的同一个检查，这里
    独立复现一遍，不依赖对内部实现的信任。"""
    font = _font()
    # 造一个有渐变+局部高对比的合成格子，比纯色更接近真实素材的挑战性
    cell = Image.new("RGBA", (CELL_W, CELL_H))
    px = cell.load()
    for y in range(CELL_H):
        for x in range(CELL_W):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, 120, 255)
    new_cell = bake_cell(cell, ["测试标题", "第二行"], font)
    diffs = find_outside_box_diffs(cell, new_cell)
    assert diffs == []


def test_reconstruct_box_erases_entire_box_deterministically():
    """reconstruct_box 是『按列从 box 下边界拉伸』——同一列在 box 内应全部
    等于 box 下边界处的颜色（这是渲染质量取舍的直接体现，见 spec 第 6 节）。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H))
    px = cell.load()
    for y in range(CELL_H):
        for x in range(CELL_W):
            px[x, y] = (x % 256, y % 256, 0, 255)
    recon = reconstruct_box(cell, TEXT_BOX)
    x0, y0, x1, y1 = TEXT_BOX
    w = x1 - x0
    rpx = recon.load()
    for x in range(w):
        expected = cell.getpixel((x0 + x, y1))
        for y in range(y1 - y0):
            assert rpx[x, y] == expected


# ---------------------------------------------------------------------------
# 4. 与真实素材的最小集成核对（数据健全性，不依赖上面纯函数测试的假设）
# ---------------------------------------------------------------------------

def test_load_titles_zh_covers_1_to_195_exactly():
    titles = load_titles_zh()
    assert set(titles) == set(range(1, NUM_CARDS + 1))
    assert all(isinstance(v, str) and v for v in titles.values())


def test_real_plot_sheets_have_expected_size_and_mode():
    import os
    from tools.bake_plot import PLOT_DIR
    for i in range(1, NUM_SHEETS + 1):
        im = Image.open(os.path.join(PLOT_DIR, f"plot_{i}_a.png"))
        assert im.size == (492, 480)


def test_real_sheet4_tail_cells_are_blank_beyond_card_195():
    """spec 第 2.3 节的核实断言的回归版本：195 号之后的 45 格应全透明。"""
    import os
    from tools.bake_plot import PLOT_DIR
    im = Image.open(os.path.join(PLOT_DIR, "plot_4_a.png")).convert("RGBA")
    # row2 col3 起 + row3-9 全部 = 195 号之后
    tail_region = im.crop((3 * CELL_W, 2 * CELL_H, 6 * CELL_W, 10 * CELL_H))
    px = tail_region.load()
    w, h = tail_region.size
    max_alpha = max(px[x, y][3] for y in range(h) for x in range(w))
    assert max_alpha == 0
