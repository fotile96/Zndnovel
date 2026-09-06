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
    FONT_PATH, HARD_ALPHA, INK_MAX_PLAUSIBLE_BOTTOM, MAX_TEXT_W, NUM_CARDS,
    NUM_SHEETS, PLOT_DIR, ZH_BOTTOM_MARGIN, _tokenize, bake_cell, bake_sheet,
    build_ink_fallback_coverage_note, cell_box, cell_position,
    collect_ink_fallbacks, collect_overflow, decide_band,
    find_outside_box_diffs, ink_bbox_of_cell, load_titles_zh, main,
    measure_rendered_text_bottom, render_band_layer, render_text_layer, run,
    wrap_title,
)


from tools.ui_font import truetype as _ui_truetype


def _font(size=10):
    # **必须走 ui_font.truetype，不能裸调 ImageFont.truetype。** FONT_PATH 现在可能
    # 指向变量字体，裸调拿到的是它的默认实例（思源黑体是 ExtraLight＝权重轴最小值），
    # 于是测试量的字重和工具烤的根本不是同一档——而且不报错、不缺字，只是更细一点。
    return _ui_truetype("plot", size)


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
    assert two_line == 65  # v19 罗马音化：5 张含名卡标题变窄降为单行（原 70）


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
    """无法测出墨迹时（如全灰格子），回退高度取『中文实际渲染需要的高度』
    （不再是任何固定值），且因为不知道原文墨迹具体在哪，整个区域都必须按
    『必须不透明』处理——不能只做局部不透明然后赌真正的墨迹恰好落在软区。
    变异目标：如果回退高度被改回一个固定常量（不随中文行数变化），这条
    测试必须变红——它用一个短标题独立算出期望值，不依赖任何写死的数字。"""
    font = _font()
    cell = Image.new("RGBA", (CELL_W, CELL_H), (128, 128, 128, 255))
    lines, _ = wrap_title("短", font)
    expected_content_bottom = measure_rendered_text_bottom(lines, font) + ZH_BOTTOM_MARGIN
    decision = decide_band(cell, lines, font)
    assert decision.fallback is True
    assert decision.fallback_reason == "no_ink_detected"
    assert decision.ink_bottom_used is None
    assert decision.content_bottom == expected_content_bottom
    assert decision.hard_range == (0, expected_content_bottom)
    # 具体到这个单字合成格子：中文只需 1 行，回退高度必须远小于旧的固定
    # 28px（旧方案按『2 行 JP + 安全边』写死，不管中文实际只要 1 行）。
    assert decision.content_bottom < 20


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


def test_real_card162_fallback_band_sized_to_zh_caption_not_fixed_height():
    """用户裁定的直接回归钉子（2026-08-08）：卡 162（游戏标题 logo 格，
    唯一的墨迹检测回退格）的中文标题『第二物语』只需 1 行，回退色带高度
    必须按这 1 行的实际渲染高度算，不能再是旧方案『2 行 JP + 安全边』的
    固定 28（+ 4px 羽化 = 32 行可见色带，实测像故障——y0-31 共 32 行，
    文字下方空出一大片纯黑）。

    变异目标 1（『回退格色带高度改回固定值』）：如果 decide_band 的回退
    分支被改回写死 28，这里的 content_bottom/band_bottom 断言必须变红
    ——期望值是独立用 measure_rendered_text_bottom 现测出来的，不依赖
    生产代码内部同一份计算，不会跟着同一个 bug 一起偏。"""
    font = _font()
    titles = load_titles_zh()
    assert titles[162] == "第二物语"
    lines, truncated = wrap_title(titles[162], font)
    assert not truncated and len(lines) == 1  # 确认只需一行

    cell = _real_cell(162)
    decision = decide_band(cell, lines, font)
    assert decision.fallback is True
    assert decision.fallback_reason == "no_ink_detected"

    expected_content_bottom = measure_rendered_text_bottom(lines, font) + ZH_BOTTOM_MARGIN
    assert decision.content_bottom == expected_content_bottom
    assert decision.hard_range == (0, expected_content_bottom)
    expected_band_bottom = min(expected_content_bottom + BAND_BOTTOM_FEATHER_PX, CELL_H)
    assert decision.band_bottom == expected_band_bottom

    # 用户裁定的具体诉求：改前是 32 行（0..31）的整片黑色带，明显盖过 1 行
    # 字实际需要的高度、留出了『第二行』的空当；改后必须显著变矮。
    # 用户的诉求是"色带别再盖出第二行的空当"，判据是**显著矮于 32**，不是某个
    # 具体数字——具体数字跟着字体走（霞鹜文楷 17，思源 Medium 21）。
    assert decision.band_bottom < 24
    assert decision.band_bottom < 32


def test_ink_fallback_coverage_note_names_the_reduced_guarantee():
    """变异目标（『回退格只覆盖文字高度』这条告警不播报 -> 必须真红）：
    run() 的 report 必须包含一条非空的 ink_fallback_coverage_note，且
    这条note必须明确点出『按文字高度覆盖、原文墨迹可能残留可见』这件
    事——不能只是『有格子回退了』这种不痛不痒的状态说明，藏起真正的
    风险等于恒绿。"""
    report = run(write=False)
    note = report["ink_fallback_coverage_note"]
    assert note is not None
    assert "162" in note
    assert "caption" in note.lower()
    assert "visible" in note.lower()
    assert "unknown" in note.lower()


def test_build_ink_fallback_coverage_note_absent_when_no_fallback():
    """反向确认：note 不是恒非空的摆设——没有任何回退时必须是 None，不能
    无论有没有回退都吐出同一句话（那样就失去了「有回退时才要警觉」的
    信号价值）。这是对 build_ink_fallback_coverage_note 本身的单元测试，
    不依赖 png/plot/ 今天恰好有 card 162 这一个回退格。"""
    assert build_ink_fallback_coverage_note([]) is None


def test_build_ink_fallback_coverage_note_names_cards_and_risk():
    """build_ink_fallback_coverage_note 的单元测试（与 run() 的真实素材
    解耦）：喂合成的 fallback 列表，确认卡号、以及『按文字高度覆盖、原文
    可能残留可见』这条具体风险措辞都在返回的字符串里，不是一句『有格子
    回退了』的空话。"""
    note = build_ink_fallback_coverage_note([(2, "no_ink_detected"), (7, "implausible_ink_bottom_40")])
    assert note is not None
    assert "2" in note and "7" in note
    assert "caption" in note.lower()
    assert "visible" in note.lower()
    assert "unknown" in note.lower()


def test_cli_check_mode_prints_ink_fallback_coverage_warning(capsys):
    """变异目标（同上，CLI 侧）：`--check` 模式下 main() 的标准输出必须
    包含这条告警的完整措辞，不能只在 manifest.json 里写、CLI 却只打印一句
    『N 个格子回退了』就完事——用户明确要求 CLI/manifest/report 三处都要
    看得到。"""
    import sys
    argv_backup = sys.argv
    try:
        sys.argv = ["bake_plot.py", "--check"]
        main()
    finally:
        sys.argv = argv_backup
    out = capsys.readouterr().out
    assert "card 162" in out
    assert "caption-only" in out
    assert "PARTIALLY VISIBLE" in out


# ---------------------------------------------------------------------------
# 4b. 回退逻辑绝不能波及正常（非回退）格子的高度计算（变异目标）
# ---------------------------------------------------------------------------

# 2026-08-08 改动前（用户裁定修正卡 162 之前）用生产代码对这些真实非回退
# 卡片跑出的 decide_band 结果，逐字段记录为金标准。这批数字与本轮改动
# （只动 decide_band 的 fallback 分支）无关，理应在改动后逐字节不变——
# 如果哪个数字变了，说明修 fallback 分支时不小心波及了正常格子的公式。
#
# 2026-08-08 第二次改动（wrap_title 换用 tools/zh_wrap.py 的词边界感知 DP
# 折行，见 zh-wrap-report.md）：这批数字里只有 card 170 变了，其余 12 张
# 逐字节不变——content_bottom/band_bottom/hard_range 由 (a) 原文日文墨迹
# 高度（ink 侧，折行算法变了也不影响，hard_range 全部不变可证）和 (b) 我
# 们自己渲染的中文标题实际像素高度（zh 侧）的较大者决定；只要新算法给出
# 的行数（1 行还是 2 行）不变，zh 侧高度通常也不变——除非某一行换了一批
# 不同的字符，而这些字符的墨迹纵向范围恰好不同。card 170『选择：将
# アヤノ――』就是这一种：旧贪心断成"选择：将アヤノ"/"――"（第二行只有两个
# 破折号，墨迹很浅）；新算法为了避免把假名人名"アヤノ"和其后的破折号拆开、
# 且两行更均衡，断成"选择：将"/"アヤノ――"（第二行多了"アヤノ"三个
# 假名字符，墨迹明显更深）——这是断行质量提升的预期副作用，不是回退分支
# 的 bug，content_bottom/band_bottom 相应从 (22,26) 变为 (26,30)，
# hard_range（ink 侧，未变）仍是 (2,20)。
_NONFALLBACK_GOLDEN = {
    #  card: (content_bottom, band_bottom, hard_range)
    #
    # 2026-08-28：默认字体改为思源黑体 Medium（用户看过四路对照后裁定），这些数
    # 随之上移——Medium 的字身比霞鹜文楷高，同字号下 content_bottom 大 2–3px。
    # 值本身是**跟着字体走的**；这条测试守的是"非回退分支的算法没被 fallback
    # 分支的改动带歪"，不是守这些具体数字。
    1:   (29, 33, (2, 24)),
    2:   (29, 33, (2, 24)),
    3:   (17, 21, (2, 12)),
    6:   (24, 28, (2, 24)),
    9:   (17, 21, (2, 12)),
    25:  (29, 33, (2, 12)),
    59:  (17, 21, (2, 12)),
    60:  (17, 21, (2, 12)),
    101: (24, 28, (2, 24)),
    115: (17, 21, (3, 12)),
    170: (29, 33, (2, 20)),
    180: (29, 33, (2, 24)),
    195: (24, 28, (3, 24)),
}


def test_decide_band_nonfallback_cells_unaffected_by_fallback_refactor():
    """变异目标（『回退逻辑波及了正常格的高度』-> 必须真红）：这批卡全部
    是非回退格（ink_bbox_of_cell 能测出墨迹），它们的 content_bottom /
    band_bottom / hard_range 是本次改动之前用同一套生产代码跑出来的金标准
    （见 _NONFALLBACK_GOLDEN 注释）。本次改动只重写了 decide_band 的
    fallback 分支，非回退分支的代码字面上没有变化——但『没有变化』需要
    被这条测试实际证明，而不是靠读代码"应该没事"。如果修 fallback 分支时
    手滑改到了共享的 max()/content_bottom 计算，或者不小心让 fallback 的
    判断条件覆盖到了正常格子，这里会立刻现出不匹配。"""
    font = _font()
    titles = load_titles_zh()
    for card, (exp_content, exp_band, exp_hard) in _NONFALLBACK_GOLDEN.items():
        lines, _ = wrap_title(titles[card], font)
        cell = _real_cell(card)
        decision = decide_band(cell, lines, font)
        assert decision.fallback is False, f"card {card} unexpectedly fell back"
        assert decision.content_bottom == exp_content, f"card {card} content_bottom"
        assert decision.band_bottom == exp_band, f"card {card} band_bottom"
        assert decision.hard_range == exp_hard, f"card {card} hard_range"


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
    # 旧实现里任何非回退格都恒等于 28（旧的固定 TEXT_BOX 高度）；新实现里
    # 短标题格子的高度必须明显小于这个数，证明它是逐格实测出来的，不是
    # 巧合落在旧常量附近。
    assert short_decision.band_bottom < 28


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


# ---------------------------------------------------------------------------
# 8. 行数规则（2026-09-07，测试反馈卡 7「没有约」色带没盖住第二行的「い」）
#
# 根因：第二行只有一个「い」，每行合格像素 1–2 个，低于 INK_MIN_ROW_PIXELS=3，
# 整行被判无墨。全库 195 张里标题 ≤7 字的全是一行、≥8 字的全是两行（原图的断行
# 规则就是第 7 字后断），一个例外都没有——行数由**标题字数**决定是数据事实，
# 像素检测降级为交叉核对。详见 docs/ops/plot-plate-research-2026-09-07.md §1。
# ---------------------------------------------------------------------------

from tools.bake_plot import jp_line_count, load_titles_jp  # noqa: E402

_LINE2_MISSED = (7, 42, 86, 161)   # 第二行整行漏检
_LINE2_PARTIAL = (170,)            # 第二行只检到 y=19


def test_jp_line_count_rule_matches_pixel_detection_on_all_other_cells():
    """规则的证据：除已知 5 张外，字数规则与像素检测的行数逐张一致。"""
    jp = load_titles_jp()
    assert sorted(jp) == list(range(1, NUM_CARDS + 1))
    mismatch = []
    for card in range(1, NUM_CARDS + 1):
        if card in _LINE2_MISSED + _LINE2_PARTIAL or card == 162:
            continue
        ink = ink_bbox_of_cell(_real_cell(card))
        detected = 2 if ink and ink[1] >= 15 else 1
        if detected != jp_line_count(jp[card]):
            mismatch.append((card, jp[card], ink))
    assert mismatch == []
    assert jp_line_count("プラネタリウム") == 1          # 7 字
    assert jp_line_count("約束をしていない") == 2         # 8 字


def test_decide_band_title_rule_covers_the_missed_second_line():
    """5 张已知缺陷格：按字数规则第二行存在，色带硬区必须盖到 y≥24。"""
    font = _font()
    titles = load_titles_zh()
    jp = load_titles_jp()
    for card in _LINE2_MISSED + _LINE2_PARTIAL:
        lines, _ = wrap_title(titles[card], font)
        d = decide_band(_real_cell(card), lines, font, jp_title=jp[card])
        assert d.fallback is False
        assert d.hard_range[1] >= 24, (card, d)
        assert d.content_bottom >= 24, (card, d)
        assert d.line_rule == "override", (card, d)


def test_decide_band_title_rule_leaves_agreeing_cells_unchanged():
    """规则与检测一致时决策一个字都不变（卡 6：两行检出、9 字）。"""
    font = _font()
    titles = load_titles_zh()
    jp = load_titles_jp()
    lines, _ = wrap_title(titles[6], font)
    before = decide_band(_real_cell(6), lines, font)
    after = decide_band(_real_cell(6), lines, font, jp_title=jp[6])
    assert (after.content_bottom, after.band_bottom, after.hard_range) == \
        (before.content_bottom, before.band_bottom, before.hard_range)
    assert after.line_rule == "agree"


def test_bake_sheet_applies_the_title_rule_to_card_7():
    """成品层面：卡 7 那格第 21–23 行（「い」所在）必须落在色带硬区里。

    硬区末两行按既有设计是 255→200 的短坡（HARD_TRANSITION_PX），所以不是纯黑，
    但白色墨迹最多只能剩 22%；修前这三行根本不在色带里，「い」原样露出（255）。
    """
    font = _font()
    titles = load_titles_zh()
    sheet, _diffs, decisions = bake_sheet(1, titles, font)
    d = decisions[7]
    assert d.line_rule == "override" and d.hard_range[1] >= 24
    band = render_band_layer((CELL_W, CELL_H), d)
    assert all(band.getpixel((40, y))[3] >= 200 for y in (21, 22, 23))
    s, box = cell_box(7)
    cell = sheet.convert("RGB").crop(box)
    px = cell.load()
    assert max(max(px[x, y]) for y in (21, 22, 23) for x in range(4, 30)) <= 64
