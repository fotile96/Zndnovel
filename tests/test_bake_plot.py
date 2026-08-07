"""tools/bake_plot.py — plot/ 卡名缩略图集烤字回填。

覆盖硬约束闸（见 build/plot_layout_spec.md + bake-plot-report.md 追记的
"背景处理方案 v2" 一节的证据与取舍）：
  1. 格号 -> 卡号映射：lua_scripts/snr_common.lua:925-954 的 plotState 构造
     循环是唯一权威来源，这里用它推出的真值表（含 3 处换页边界）钉死。
  2. 色带区域（逐格动态计算，非固定 TEXT_BOX）之外的像素保真：任何一个
     被动过的像素都必须被抓到。
  3. 超长卡名绝不能被静默截断：wrap_title/collect_overflow 必须把截断
     显式报出来，不能吞掉多出来的字符。
  4. 墨迹检测判据：195 格真实素材上必须能正确识别原文日文墨迹的纵向范围，
     且不能被明亮背景（泳池、天空等）误判。
  5. 色带高度 = max(墨迹实测高度, 中文实际需要的行数高度)，任一方向的
     "只取其一"都必须被抓到。
  6. 墨迹检测失败（或判定不合理）时必须保守回退，且这次回退必须被显式
     报出来（manifest/report/CLI），不能静默发生。
"""
from PIL import Image, ImageFont

from tools.bake_plot import (
    BAND_BOTTOM_FEATHER_PX, CARDS_PER_SHEET, CELL_H, CELL_W, ELLIPSIS,
    FALLBACK_BAND_BOTTOM, FONT_PATH, HARD_ALPHA, INK_MAX_PLAUSIBLE_BOTTOM,
    MAX_TEXT_W, NUM_CARDS, NUM_SHEETS, PLOT_DIR, _tokenize, bake_cell,
    bake_sheet, cell_box, cell_position, collect_ink_fallbacks,
    collect_overflow, decide_band, find_outside_box_diffs, ink_bbox_of_cell,
    load_titles_zh, measure_rendered_text_bottom, render_band_layer,
    render_text_layer, run, wrap_title,
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
    """变异目标：collect_overflow 如果被阉割成『不管三七二十一都返回 []』，
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
# 3. 墨迹检测（ink_bbox_of_cell）——195 格真值 + 抗亮背景误判
# ---------------------------------------------------------------------------

# 6 个已在 spec 第 4 节用「近白色不透明像素外接框」独立量出坐标的参照卡，
# 与 ink_bbox_of_cell 的联合判据（亮+邻域暗）在这些卡上必须给出同一结论
# （见 report 附录的 195 格实测扫描，这 6 张与 spec 手工测量完全吻合）。
INK_REFERENCE = {
    1: (3, 23),     # 2 行标题
    2: (3, 23),     # 2 行标题
    9: (3, 11),     # 1 行标题
    60: (3, 11),    # 1 行标题（sheet1 末格）
    195: (4, 23),   # 2 行标题
    180: (3, 23),   # 2 行标题（15 字最长标题之一）
}


def _real_cell(card):
    sheet, box = cell_box(card)
    import os
    im = Image.open(os.path.join(PLOT_DIR, f"plot_{sheet}_a.png")).convert("RGBA")
    return im.crop(box)


def test_ink_bbox_matches_spec_measured_reference_cards():
    for card, expected in INK_REFERENCE.items():
        assert ink_bbox_of_cell(_real_cell(card)) == expected, f"card {card}"


def test_ink_bbox_rejects_uniform_bright_background():
    """明亮背景（泳池水面、天空一类）本身没有临近的暗色描边像素，联合判据
    必须拒绝把它当墨迹——如果退化成『只看亮度』，这条测试会因为大片假阳性
    行而失败（bbox 不是 None）。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (220, 220, 225, 255))
    assert ink_bbox_of_cell(cell) is None


def test_ink_bbox_rejects_bright_and_dark_regions_that_are_not_adjacent():
    """亮块和暗块都存在，但彼此距离超过判据半径——不应被联合判据配对成
    『墨迹』（这是照片里『远处有把黑伞、别处有片白墙』这类巧合的防线）。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (128, 128, 128, 255))
    px = cell.load()
    for y in range(3, 8):
        for x in range(2, 20):
            px[x, y] = (230, 230, 230, 255)  # 亮块，顶部
    for y in range(40, 46):
        for x in range(2, 20):
            px[x, y] = (10, 10, 10, 255)     # 暗块，底部，相距远超半径
    assert ink_bbox_of_cell(cell) is None


def test_ink_bbox_detects_adjacent_bright_dark_pairing():
    """白底黑边描边字的最小合成复现：亮块中间嵌一条暗色描边，联合判据应该
    在该行区间内测出墨迹。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (128, 128, 128, 255))
    px = cell.load()
    for y in range(18, 23):
        for x in range(10, 30):
            px[x, y] = (240, 240, 240, 255)
        for x in range(19, 21):
            px[x, y] = (0, 0, 0, 255)
    bbox = ink_bbox_of_cell(cell)
    assert bbox is not None
    top, bottom = bbox
    assert 15 <= top <= 20
    assert 20 <= bottom <= 26


def test_real_195_cells_ink_detection_summary():
    """195 格真实素材全量扫描的回归钉子：card 162（游戏自身 logo 缩略图，
    用的是纯色描边风格而非白芯黑边描边字，不满足联合判据）是唯一的检测
    失败案例。如果这个数字变了（不管变多变少），说明判据或素材前提发生了
    漂移，需要人工重新核实，而不是让测试默默接受新数字。"""
    font = _font()
    titles = load_titles_zh()
    total = 0
    fallback_cards = []
    for card in range(1, NUM_CARDS + 1):
        total += 1
        bbox = ink_bbox_of_cell(_real_cell(card))
        if bbox is None or bbox[1] > INK_MAX_PLAUSIBLE_BOTTOM:
            fallback_cards.append(card)
    assert total == 195
    assert fallback_cards == [162]


# ---------------------------------------------------------------------------
# 4. decide_band：色带高度 = max(墨迹高度, 中文需要高度)（变异目标）
# ---------------------------------------------------------------------------

def _cell_with_ink_block(fill_y, fill_x=(10, 30), stroke_x=(19, 21),
                          bg=(128, 128, 128, 255)):
    """合成一张『亮块中嵌暗描边』的格子，ink_bbox_of_cell 应该在 fill_y
    附近测出墨迹（用于可控地摆放"原文墨迹"而不依赖任何真实卡片内容）。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), bg)
    px = cell.load()
    for y in range(*fill_y):
        for x in range(*fill_x):
            px[x, y] = (240, 240, 240, 255)
        for x in range(*stroke_x):
            px[x, y] = (0, 0, 0, 255)
    return cell


def test_decide_band_ink_dominates_when_zh_is_short():
    """变异目标：色带高度必须取『墨迹高度、中文需要高度』的较大者。这里构造
    一张原文墨迹很深（一路到 y=22 附近）但中文译名很短（1 行）的合成格子——
    如果 decide_band 只看中文需要的高度（忽略墨迹），band 会明显不够深，
    露出原文墨迹的下半截。"""
    font = _font()
    cell = _cell_with_ink_block(fill_y=(18, 23))
    ink = ink_bbox_of_cell(cell)
    assert ink is not None and ink[1] >= 20  # 确认合成墨迹真的很深

    short_lines, _ = wrap_title("短", font)
    zh_only_bottom = measure_rendered_text_bottom(short_lines, font)

    decision = decide_band(cell, short_lines, font)
    assert decision.content_bottom > zh_only_bottom  # 中文高度本身不够
    assert decision.content_bottom >= ink[1]          # 必须覆盖到墨迹底部
    assert decision.hard_range[1] >= ink[1]


def test_decide_band_zh_dominates_when_ink_is_short():
    """反方向：原文墨迹很浅（只在顶部一行），但中文译名要 2 行——如果
    decide_band 只看墨迹高度（忽略中文），第二行中文会被裁到色带外面。"""
    font = _font()
    cell = _cell_with_ink_block(fill_y=(3, 8))
    ink = ink_bbox_of_cell(cell)
    assert ink is not None and ink[1] <= 10  # 确认合成墨迹很浅

    long_lines, truncated = wrap_title(
        "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅", font, max_lines=2)
    assert len(long_lines) == 2
    zh_bottom = measure_rendered_text_bottom(long_lines, font)

    decision = decide_band(cell, long_lines, font)
    assert decision.content_bottom > ink[1] + 3   # 中文比墨迹深不少
    assert decision.content_bottom >= zh_bottom    # 必须完整容纳两行中文


def test_real_card6_ink_dominates_over_short_zh():
    """真实数据确认（正方向）：卡 6『約束を思い出せない』原文墨迹是 2 行
    （y3-23），中文译名『想不起约定』只有 1 行——色带必须仍然深到能盖住
    原文墨迹，不能因为中文短就缩水。"""
    font = _font()
    titles = load_titles_zh()
    cell = _real_cell(6)
    lines, truncated = wrap_title(titles[6], font)
    assert not truncated and len(lines) == 1
    decision = decide_band(cell, lines, font)
    zh_bottom = measure_rendered_text_bottom(lines, font)
    assert decision.ink_bottom_used > decision.zh_bottom_used
    assert decision.content_bottom == decision.ink_bottom_used
    assert decision.content_bottom > zh_bottom


def test_real_card25_zh_dominates_over_short_ink():
    """真实数据确认（反方向）：卡 25『選択：声の主』原文墨迹只有 1 行
    （y3-11），中文译名『选择：声音的主人』要 2 行——色带必须深到能容纳
    完整的两行中文，不能因为原文只有 1 行就缩水。"""
    font = _font()
    titles = load_titles_zh()
    cell = _real_cell(25)
    lines, truncated = wrap_title(titles[25], font)
    assert not truncated and len(lines) == 2
    decision = decide_band(cell, lines, font)
    assert decision.zh_bottom_used > decision.ink_bottom_used
    assert decision.content_bottom == decision.zh_bottom_used


def test_decide_band_implausible_ink_falls_back():
    """墨迹检测结果荒谬地深（超过 INK_MAX_PLAUSIBLE_BOTTOM）时，必须整体
    拒绝并回退，而不是信以为真地把色带拉到那么深。"""
    font = _font()
    cell = _cell_with_ink_block(fill_y=(2, 40))  # 明显超出任何真实标题范围
    lines, _ = wrap_title("短", font)
    decision = decide_band(cell, lines, font)
    assert decision.fallback is True
    assert decision.fallback_reason.startswith("implausible_ink_bottom_")
    assert decision.hard_range == (0, decision.content_bottom)


def test_decide_band_fallback_marks_whole_zone_hard():
    """无法测出墨迹时（如全灰格子），回退高度取 FALLBACK_BAND_BOTTOM，且
    因为不知道原文墨迹具体在哪，整个区域都必须按『必须不透明』处理——不能
    只做局部不透明然后赌真正的墨迹恰好落在软区。"""
    font = _font()
    cell = Image.new("RGBA", (CELL_W, CELL_H), (128, 128, 128, 255))
    lines, _ = wrap_title("短", font)
    decision = decide_band(cell, lines, font)
    assert decision.fallback is True
    assert decision.fallback_reason == "no_ink_detected"
    assert decision.content_bottom == FALLBACK_BAND_BOTTOM
    assert decision.hard_range == (0, FALLBACK_BAND_BOTTOM)


# ---------------------------------------------------------------------------
# 5. 墨迹回退必须显式播报，不能静默发生（变异目标）
# ---------------------------------------------------------------------------

def test_collect_ink_fallbacks_surfaces_fallback_decisions():
    """变异目标：collect_ink_fallbacks 如果被阉割成『不管三七二十一都返回
    []』，这条测试必须变红——喂一组混合 fallback/非-fallback 的合成决策，
    要求只有 fallback 的那些被报出来，且原因原样带出。"""
    font = _font()
    ok_cell = _cell_with_ink_block(fill_y=(3, 8))
    bad_cell = Image.new("RGBA", (CELL_W, CELL_H), (128, 128, 128, 255))
    lines, _ = wrap_title("短", font)
    decisions = {
        1: decide_band(ok_cell, lines, font),    # 应该检测成功，不进列表
        2: decide_band(bad_cell, lines, font),   # 应该回退，进列表
    }
    assert decisions[1].fallback is False
    assert decisions[2].fallback is True
    fallbacks = collect_ink_fallbacks(decisions)
    assert fallbacks == [(2, "no_ink_detected")]


def test_real_run_report_flags_card_162_as_ink_fallback():
    """端到端确认：真实跑批的 report 必须把卡 162 的回退显式报出来（这是
    195 格里唯一的检测失败案例，见 test_real_195_cells_ink_detection_summary
    ），且不是只存在于某个中间变量里、CLI/manifest 从不读它——run() 的
    report 字典本身就必须包含它。"""
    report = run(write=False)
    fallback_cards = [f["card"] for f in report["ink_fallback_cards"]]
    assert fallback_cards == [162]
    assert report["ink_detection_summary"] == {
        "total": 195, "detected": 194, "fallback": 1,
    }


# ---------------------------------------------------------------------------
# 6. 色带区域外像素保真（变异目标：闸被关掉）——闸本身是通用函数，box 现在
#    逐格动态计算，不再是模块级常量，这里用测试内部固定的 box 验证闸的行为。
# ---------------------------------------------------------------------------

_TEST_BOX = (0, 0, CELL_W, 28)  # 仅供本节测试使用的任意固定框，不代表任何
                                 # 生产常量（生产里这个框逐格算出）。


def _solid_cell(color=(80, 80, 80, 255)):
    return Image.new("RGBA", (CELL_W, CELL_H), color)


def test_find_outside_box_diffs_detects_change_outside_box():
    """变异目标：如果这个函数被阉割成『恒返回 []』，这条测试必须变红——
    它在 box 之外故意改一个像素（模拟『顺手把背景重画了』），要求抓到。"""
    orig = _solid_cell()
    corrupted = orig.copy()
    x0, y0, x1, y1 = _TEST_BOX
    outside_xy = (5, y1 + 3)  # 明确在 box 下方，属于『非文字区域』
    assert not (x0 <= outside_xy[0] < x1 and y0 <= outside_xy[1] < y1)
    corrupted.putpixel(outside_xy, (255, 0, 0, 255))
    diffs = find_outside_box_diffs(orig, corrupted, _TEST_BOX)
    assert outside_xy in diffs


def test_find_outside_box_diffs_ignores_change_inside_box():
    orig = _solid_cell()
    edited = orig.copy()
    inside_xy = (10, 10)
    x0, y0, x1, y1 = _TEST_BOX
    assert x0 <= inside_xy[0] < x1 and y0 <= inside_xy[1] < y1
    edited.putpixel(inside_xy, (255, 0, 0, 255))
    diffs = find_outside_box_diffs(orig, edited, _TEST_BOX)
    assert diffs == []


def test_find_outside_box_diffs_empty_when_identical():
    orig = _solid_cell()
    same = orig.copy()
    assert find_outside_box_diffs(orig, same, _TEST_BOX) == []


def test_bake_cell_only_modifies_within_its_own_dynamic_band_bottom():
    """端到端属性测试（非 mutation 专用）：真实渲染路径（decide_band +
    render_band_layer + render_text_layer + alpha_composite）跑一遍，确认
    band_bottom 外部像素逐字节不变——这是 bake_sheet 自己在跑批时也会做的
    同一个检查，这里独立复现一遍，不依赖对内部实现的信任。"""
    font = _font()
    # 造一个有渐变+局部高对比的合成格子，比纯色更接近真实素材的挑战性
    cell = Image.new("RGBA", (CELL_W, CELL_H))
    px = cell.load()
    for y in range(CELL_H):
        for x in range(CELL_W):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, 120, 255)
    new_cell, decision = bake_cell(cell, ["测试标题", "第二行"], font)
    box = (0, 0, CELL_W, decision.band_bottom)
    diffs = find_outside_box_diffs(cell, new_cell, box)
    assert diffs == []


def test_bake_cell_band_bottom_varies_with_real_content_not_fixed():
    """TEXT_BOX 固定框已被废除的行为验证：短标题格子和长标题格子必须得到
    不同的 band_bottom，不能像旧实现那样恒等于某个固定值（如旧版的 28）。"""
    font = _font()
    titles = load_titles_zh()
    short_cell = _real_cell(59)   # 「プール」->「游泳池」，短
    long_cell = _real_cell(6)     # 2 行原文墨迹，中文虽短但墨迹深
    short_lines, _ = wrap_title(titles[59], font)
    long_lines, _ = wrap_title(titles[6], font)
    _, short_decision = bake_cell(short_cell, short_lines, font)
    _, long_decision = bake_cell(long_cell, long_lines, font)
    assert short_decision.band_bottom < long_decision.band_bottom
    assert short_decision.band_bottom < FALLBACK_BAND_BOTTOM


def test_render_band_layer_hard_zone_is_fully_opaque_soft_zone_is_not():
    """render_band_layer 的核心承诺：decision.hard_range 内必须是
    HARD_ALPHA（255，完全不透明——这是消除原文墨迹残影的唯一手段，见
    report「背景处理方案 v2」一节的实测过程），hard_range 之外（但仍在
    content_bottom 内）必须明显低于 255（真正半透明，不是摆设）。"""
    font = _font()
    cell = _cell_with_ink_block(fill_y=(3, 8))
    lines, truncated = wrap_title(
        "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅", font, max_lines=2)
    assert len(lines) == 2
    decision = decide_band(cell, lines, font)
    band = render_band_layer(cell.size, decision)
    px = band.load()
    hard_top, hard_bottom = decision.hard_range
    assert hard_bottom > hard_top
    mid_hard_y = (hard_top + hard_bottom) // 2
    assert px[40, mid_hard_y][3] == HARD_ALPHA
    # 一个明确落在 content_bottom 内、但不在 hard_range 内的软区行
    soft_y = decision.content_bottom - 1
    assert not (hard_top <= soft_y < hard_bottom)
    assert 0 < px[40, soft_y][3] < HARD_ALPHA


def test_bake_sheet_reports_per_card_dynamic_band_via_decisions():
    """bake_sheet 必须把每格的 BandDecision 一并交回（而不是只有像素差异
    列表），供 run() 组装 ink_fallback / band_bottom 统计——这是报告『195
    格实测统计』的数据来源。"""
    font = _font()
    titles = load_titles_zh()
    _new_sheet, diffs, decisions = bake_sheet(1, titles, font)
    assert set(diffs) == set(decisions)
    assert all(d == [] for d in diffs.values())  # sheet1 逐格像素保真
    assert decisions[1].band_bottom > 0


# ---------------------------------------------------------------------------
# 7. 与真实素材的最小集成核对（数据健全性，不依赖上面纯函数测试的假设）
# ---------------------------------------------------------------------------

def test_load_titles_zh_covers_1_to_195_exactly():
    titles = load_titles_zh()
    assert set(titles) == set(range(1, NUM_CARDS + 1))
    assert all(isinstance(v, str) and v for v in titles.values())


def test_real_plot_sheets_have_expected_size_and_mode():
    import os
    for i in range(1, NUM_SHEETS + 1):
        im = Image.open(os.path.join(PLOT_DIR, f"plot_{i}_a.png"))
        assert im.size == (492, 480)


def test_real_sheet4_tail_cells_are_blank_beyond_card_195():
    """spec 第 2.3 节的核实断言的回归版本：195 号之后的 45 格应全透明。"""
    import os
    im = Image.open(os.path.join(PLOT_DIR, "plot_4_a.png")).convert("RGBA")
    # row2 col3 起 + row3-9 全部 = 195 号之后
    tail_region = im.crop((3 * CELL_W, 2 * CELL_H, 6 * CELL_W, 10 * CELL_H))
    px = tail_region.load()
    w, h = tail_region.size
    max_alpha = max(px[x, y][3] for y in range(h) for x in range(w))
    assert max_alpha == 0


def test_real_run_zero_pixel_preservation_violations():
    """全量 195 格跑批的像素保真闸回归：真实产物里不应有任何一格在
    band_bottom 之外被动过。"""
    report = run(write=False)
    assert report["pixel_preservation_violations"] == []


def test_real_run_band_bottom_stays_within_cell():
    report = run(write=False)
    assert 0 < report["band_bottom_min"]
    assert report["band_bottom_max"] <= CELL_H
    # 旧固定实现是恒定 28；新实现必须体现出跨格差异（废除固定框的行为证据）
    assert report["band_bottom_min"] < report["band_bottom_max"]
