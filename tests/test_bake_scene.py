"""tools/bake_scene.py — png/scene/ 场景名条集（145x15 单行格）烤字回填。

覆盖硬约束闸（见 build/scene_layout_spec.md 与
.superpowers/sdd/2026-08-07-p4-polish-pass/bake-scene-report.md）：
  1. 格号 -> 卡号映射：lua_scripts/snr_common.lua:955-984 的 sceneState
     构造循环是唯一权威来源（3 列/页，每 102 张卡换页，与 plot/ 的 6 列/
     60 张卡结构相同但参数不同，不能假设复用 plot 的具体数字）。
  2. TEXT_BOX 之外的像素保真：任何一个被动过的像素都必须被抓到（scene/
     背景是纯色半透明条带 + 四角缺口，不是照片，所以固定矩形闸的前提本身
     也需要证据——这里钉死"195 张真实卡的墨迹从未越过 TEXT_BOX"这条事实，
     不能只假设它成立）。
  3. 超长标题绝不能被静默截断：collect_overflow 必须把截断显式报出来。
  4. 墨迹检测：195 格真实素材必须全部落在 TEXT_BOX 内，越界/检测失败都要
     被 collect_ink_outliers 抓到并报出来，不能吞掉。
  5. 擦除必须是硬覆盖（直接写像素），不能用半透明 alpha_composite 盖在原
     日文墨迹上——那样只会把不透明的白字/黑边染灰，留下可辨认的残影。
"""
import sys

import pytest
from PIL import Image, ImageDraw, ImageFont

from tools.bake_scene import (
    BAND_ALPHA, BAND_COLOR, CARDS_PER_SHEET, CELL_H, CELL_W,
    CELLZOOM_CARDS, FONT_PATH, FONT_SIZE_CASCADE, GRID_COLS, GRID_ROWS,
    MAX_LINES, MAX_TEXT_W, NUM_CARDS, NUM_SHEETS, SCENE_DIR, SHEET_H,
    SHEET_W, TEXT_BOX, bake_cell, bake_sheet, build_cellzoom_image,
    build_render_plan, cell_box, cell_position, collect_ink_outliers,
    collect_overflow, collect_vertical_clip_risks, find_outside_box_diffs,
    ink_bbox_of_cell, load_fonts, measure_vertical_extent,
    render_text_layer, resolve_fonts_by_card, run, sheet_path,
)
from tools.bake_plot import load_titles_zh


def _font(size):
    return ImageFont.truetype(FONT_PATH, size)


def _real_titles():
    titles = load_titles_zh()
    return {c: titles[c] for c in range(1, NUM_CARDS + 1)}


# ---------------------------------------------------------------------------
# 1. 格号 -> 卡号映射（真值表来自 lua 源码算法，见 spec 第 2 节）
# ---------------------------------------------------------------------------

GROUND_TRUTH = {
    1: (1, 0, 0),      # sheet1 首格
    2: (1, 0, 1),
    3: (1, 0, 2),      # sheet1 第一行末格（3 列，换行前）
    4: (1, 1, 0),      # 换行到第二行首格
    102: (1, 33, 2),   # sheet1 末格（换页前，34 行 x 3 列 = 102）
    103: (2, 0, 0),    # sheet2 首格（换页后 col/row 清零）
    195: (2, 30, 2),   # 195-102=93 张卡；(93-1)//3=30 行，(93-1)%3=2 列
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


def test_cell_position_off_by_one_col_is_caught_by_ground_truth():
    """『格号映射错位一格』变异的回归形态：手写一个列错位的实现，确认它
    与真值表不符——证明真值表本身有牙，不是摆设。"""
    def buggy_cell_position(card):
        sheet, row, col = cell_position(card)
        return sheet, row, (col + 1) % GRID_COLS
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
    assert sheet == 2
    assert box == (2 * CELL_W, 30 * CELL_H, 3 * CELL_W, 31 * CELL_H)


def test_grid_constants_cover_all_cards():
    assert GRID_COLS == 3
    assert GRID_ROWS == 34
    assert CARDS_PER_SHEET == 102
    assert NUM_SHEETS == 2
    assert NUM_CARDS == 195
    # 204 格装 195 张卡，尾部 9 格空置（sheet2 的空白区）
    assert NUM_SHEETS * CARDS_PER_SHEET - NUM_CARDS == 9
    assert SHEET_W == GRID_COLS * CELL_W
    assert SHEET_H == GRID_ROWS * CELL_H


def test_real_sheet2_tail_cells_are_blank_beyond_card_195():
    """204 格容量 - 195 张卡 = 9 个空格，应为全透明（与 plot/ 的 45 空格
    先例一致），实测核对而非假设。"""
    sheet = Image.open(sheet_path(2)).convert("RGBA")
    for card in range(196, 205):
        idx0 = (card - 1) % CARDS_PER_SHEET
        row, col = idx0 // GRID_COLS, idx0 % GRID_COLS
        box = (col * CELL_W, row * CELL_H, (col + 1) * CELL_W, (row + 1) * CELL_H)
        cell = sheet.crop(box)
        assert cell.getextrema()[-1] == (0, 0), f"card {card} not fully transparent"


# ---------------------------------------------------------------------------
# 2. 超长标题不静默截断
# ---------------------------------------------------------------------------

def test_collect_overflow_matches_known_11px_overflow_set():
    """collect_overflow is a generic single-font check, unchanged in
    behaviour from before the v3 cascade. At the cascade's largest tier
    (11px) build_render_plan (section 7 below) independently finds exactly
    4 real titles that overflow -- cross-check that same fact through
    collect_overflow directly (not via the cascade machinery), so the two
    code paths agree from two different angles."""
    titles = _real_titles()
    font = _font(FONT_SIZE_CASCADE[0])
    overflow = collect_overflow(titles, font)
    assert sorted(c for c, *_ in overflow) == [2, 90, 180, 182]


def test_collect_overflow_empty_at_smallest_cascade_tier():
    """At the cascade's smallest configured tier (9px), all 195 real
    titles still fit -- i.e. today's data never actually needs the cascade
    to reach this tier (10px already absorbs the 4 overflow cases seen at
    11px). Re-verified every run, not assumed."""
    titles = _real_titles()
    font = _font(FONT_SIZE_CASCADE[-1])
    overflow = collect_overflow(titles, font)
    assert overflow == []


def test_collect_overflow_surfaces_truncated_titles():
    """合成一个远超 135px 预算、且找不到任何合法断点组合能在 1 行内放下
    的超长字符串，确认 collect_overflow 会把截断显式报出来，不静默吞字。"""
    font = _font(FONT_SIZE_CASCADE[0])
    long_text = "这是一段故意写得非常长非常长非常长非常长非常长的标题文本用来测试截断"
    titles = {1: "短标题", 2: long_text}
    overflow = collect_overflow(titles, font)
    cards = [c for c, *_ in overflow]
    assert cards == [2]
    card, text, lines, dropped = overflow[0]
    assert text == long_text
    assert dropped != ""  # 真的丢了字符，且这件事被报出来了
    assert "".join(lines) != long_text  # 确认这就是"信息有损"的那一条


def test_collect_overflow_disabled_would_hide_the_truncation():
    """变异回归形态：模拟"截断不进报告"的坏实现（恒返回 []），证明如果
    真的这样改，上面那条真实截断就会从"能看到"变成"看不到"——即这条闸
    确实是承重的，不是摆设。"""
    font = _font(FONT_SIZE_CASCADE[0])
    long_text = "这是一段故意写得非常长非常长非常长非常长非常长的标题文本用来测试截断"
    titles = {2: long_text}

    def broken_collect_overflow(titles, font, **kw):
        return []

    real = collect_overflow(titles, font)
    fake = broken_collect_overflow(titles, font)
    assert real != []
    assert fake == []


# ---------------------------------------------------------------------------
# 2b. 逐格字号级联（v3）：11px 优先，逐档回落，回落必须可见，最小档仍放不下
#     必须报错停下，不许静默截断。
# ---------------------------------------------------------------------------

def test_font_size_cascade_is_a_list_biggest_first():
    assert isinstance(FONT_SIZE_CASCADE, list)
    assert len(FONT_SIZE_CASCADE) >= 2
    assert FONT_SIZE_CASCADE == sorted(FONT_SIZE_CASCADE, reverse=True)
    assert FONT_SIZE_CASCADE[0] == 11
    assert FONT_SIZE_CASCADE[-1] <= 10  # today: [11, 10, 9]


def test_build_render_plan_real_titles_fallback_set():
    """195 条真实标题跑一次完整级联：必须 0 条硬失败（未命中任何档），
    且回落集合必须精确是卡 2/90/180/182（用户交办前提里的已知 11px 溢出
    四条），全部降到 10px 就放得下——不使用 9px 档，但机制仍会尝试它。"""
    titles = _real_titles()
    fonts_by_size = load_fonts()
    plans, fallbacks, hard_failures = build_render_plan(titles, fonts_by_size)
    assert hard_failures == []
    assert len(plans) == NUM_CARDS
    fb_cards = sorted(c for c, _size, _tried in fallbacks)
    assert fb_cards == [2, 90, 180, 182]
    for card, size, tried in fallbacks:
        assert size == 10
        assert tried == [11]  # only needed to step down ONE tier, not two
    non_fallback_cards = set(plans) - set(fb_cards)
    assert {plans[c]["font_size"] for c in non_fallback_cards} == {FONT_SIZE_CASCADE[0]}


def test_build_render_plan_walks_arbitrary_length_cascade():
    """级联阶梯必须是通用的多档循环，不能只硬编码"试一次、不行就退一档"
    这种两档特例。构造一个只有在级联第三档（也是最小档）才放得下的合成
    标题，确认 build_render_plan 会依次穿过前面所有更大的档才落地，且把
    "穿过了哪些档"如实记在 fallbacks 里。"""
    cascade = [40, 30, 20, 10]
    fonts_by_size = {s: _font(s) for s in cascade}
    # 13 个汉字：实测宽度在 40/30/20px 下分别为 520/390/260px，全部远超
    # 139px 预算；仅 10px（130px）放得下——见本测试上方的实测脚本结论。
    text = "这段文字必须最小号才放得下"  # 13 个汉字
    titles = {1: text}
    plans, fallbacks, hard_failures = build_render_plan(
        titles, fonts_by_size, cascade=cascade)
    assert hard_failures == [], (
        "synthetic text unexpectedly failed every tier -- adjust the "
        "fixture text/cascade so it fits at the smallest tier only")
    assert plans[1]["font_size"] == cascade[-1]
    card, size, tried = fallbacks[0]
    assert card == 1
    assert size == cascade[-1]
    assert tried == cascade[:-1]  # walked past every larger tier before landing
    assert len(tried) >= 2, "this fixture must exercise MORE than one fallback step"


def test_build_render_plan_hard_failure_when_even_smallest_tier_overflows():
    """若一个标题连级联最小档都放不下，build_render_plan 必须把它计入
    hard_failures（而不是悄悄选最小档、任由其被截断）——这是"零截断"
    约束在级联规划层面的体现。"""
    smallest = FONT_SIZE_CASCADE[-1]
    fonts_by_size = {smallest: _font(smallest)}
    long_text = "这是一段故意写得非常长非常长非常长非常长非常长的标题文本用来测试截断"
    titles = {1: long_text}
    plans, fallbacks, hard_failures = build_render_plan(
        titles, fonts_by_size, cascade=[smallest])
    assert plans == {}
    assert fallbacks == []
    assert len(hard_failures) == 1
    card, text, size, info = hard_failures[0]
    assert card == 1
    assert text == long_text
    assert size == smallest
    assert info["truncated"] is True


def test_fallbacks_disabled_would_hide_the_downgrade():
    """变异回归形态：模拟"fallbacks 列表被静默清空"的坏实现，证明如果
    真的这样改，卡 2/90/180/182 的真实回落就会从"能看到"变成"看不到"
    ——这正是 CLAUDE.md 点名的"静默回落是恒绿的一种"失败模式。"""
    titles = _real_titles()
    fonts_by_size = load_fonts()
    _plans, real_fallbacks, _hard = build_render_plan(titles, fonts_by_size)

    def broken_build_render_plan(*a, **kw):
        plans, _fallbacks, hard = build_render_plan(*a, **kw)
        return plans, [], hard  # 静默清空回落列表

    _plans2, fake_fallbacks, _hard2 = broken_build_render_plan(titles, fonts_by_size)
    assert real_fallbacks != []
    assert sorted(c for c, _s, _t in real_fallbacks) == [2, 90, 180, 182]
    assert fake_fallbacks == []


def test_run_raises_on_hard_failure_instead_of_silently_truncating(monkeypatch, tmp_path):
    """run() 遇到级联穷尽仍放不下的标题时必须报错停下，不能改成"就用最小
    档硬塞、任由截断"。用一个被注入的超长标题触发 hard_failures，确认
    run() 抛出异常，且异常发生在任何文件写入之前（tmp_path 应保持空）。"""
    import tools.bake_scene as bs
    real_titles = load_titles_zh()
    long_text = ("这是一段故意写得非常长非常长非常长非常长非常长的标题文本"
                 "用来测试截断") * 3

    def fake_load_titles_zh():
        d = dict(real_titles)
        d[1] = long_text
        return d

    monkeypatch.setattr(bs, "load_titles_zh", fake_load_titles_zh)
    monkeypatch.setattr(bs, "OUT_DIR", str(tmp_path))
    with pytest.raises(RuntimeError):
        bs.run(write=True)
    assert not (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "scene_1_a.png").exists()


# ---------------------------------------------------------------------------
# 2c. 竖直方向切边风险（11px 字形高 vs 15px 格高）
# ---------------------------------------------------------------------------

def test_measure_vertical_extent_real_cascade_no_clipping():
    """195 条真实标题按其实际解析出的级联字号渲染，墨迹竖直范围必须全部
    落在 [0, CELL_H) 内——这是本轮"11px 是否会切顶切底"的实测验证，不是
    从字体理论高度推算的猜测。"""
    titles = _real_titles()
    fonts_by_size = load_fonts()
    plans, _fb, hard_failures = build_render_plan(titles, fonts_by_size)
    assert hard_failures == []
    fonts_by_card = resolve_fonts_by_card(plans, fonts_by_size)
    risks = collect_vertical_clip_risks(titles, fonts_by_card)
    assert risks == []


def test_measure_vertical_extent_detects_synthetic_oversize_font():
    """回归证明：padded-canvas 测量法确实能测出切边——用一个明显过大的字号
    在同一个 box 上渲染，墨迹必须超出 [0, CELL_H) 边界，否则"11px 无切边"
    这个结论就是没牙的机制在空转。"""
    huge_font = _font(60)
    extent = measure_vertical_extent("字", huge_font)
    assert extent is not None
    y0, y1 = extent
    assert y0 < TEXT_BOX[1] or y1 >= TEXT_BOX[3]


def test_collect_vertical_clip_risks_flags_synthetic_oversize():
    fonts_by_card = {1: _font(60)}
    titles = {1: "字"}
    risks = collect_vertical_clip_risks(titles, fonts_by_card)
    assert len(risks) == 1
    assert risks[0][0] == 1


# ---------------------------------------------------------------------------
# 3. 墨迹检测 + TEXT_BOX 越界哨兵
# ---------------------------------------------------------------------------

def test_ink_bbox_of_cell_detects_synthetic_ink():
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    d = ImageDraw.Draw(cell)
    d.rectangle([20, 4, 22, 10], fill=(255, 255, 255, 255))
    bbox = ink_bbox_of_cell(cell)
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert x0 == 20 and x1 == 22
    assert y0 == 4 and y1 == 10


def test_ink_bbox_of_cell_ignores_flat_background():
    """背景恒为 RGB(0,0,0)（只有 alpha 变化），亮度阈值检测不应在纯背景格
    上误报——这是本模块敢用"只看亮度"而不必像 bake_plot 那样加暗描边邻域
    联合判据的前提，这里直接验证该前提。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    assert ink_bbox_of_cell(cell) is None


def test_collect_ink_outliers_empty_for_real_data():
    """195 格真实素材的墨迹必须全部落在 TEXT_BOX 内——这是"固定矩形闸
    对 scene/ 成立"这一设计前提的实测证据，每次跑都重新验证，不是写死
    在文档里就不管了。"""
    outliers = collect_ink_outliers()
    assert outliers == []


def test_collect_ink_outliers_flags_ink_outside_text_box():
    """变异回归形态：真实素材里没有越界墨迹，用合成数据证明检测逻辑本身
    确实会抓越界——不依赖"今天恰好没有"这件事来证明闸有牙。"""
    from tools.bake_scene import ink_bbox_of_cell as _ink
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    d = ImageDraw.Draw(cell)
    d.rectangle([0, 0, 3, 3], fill=(255, 255, 255, 255))  # x=0，恒 < TEXT_BOX[0]
    bbox = _ink(cell)
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert x0 < TEXT_BOX[0]  # 确认这个合成用例真的越界（不写死具体像素数，
    # 跟随 TEXT_BOX[0] 的实际取值，边距改动不会让这条测试悄悄失效）


# ---------------------------------------------------------------------------
# 4. 擦除必须是硬覆盖，不能半透明合成留残影
# ---------------------------------------------------------------------------

def test_bake_cell_erases_opaque_ink_without_ghosting():
    """构造一个 TEXT_BOX 内布满不透明白字的合成格子，烘焙后（若新标题很短）
    大部分 box 区域应回落到纯色带 (BAND_COLOR, BAND_ALPHA)，不能残留原白色
    像素的痕迹——这是"直接写像素，不 alpha_composite 盖在原墨迹上"这条
    设计决策要防的具体故障模式。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    d = ImageDraw.Draw(cell)
    d.rectangle([TEXT_BOX[0], TEXT_BOX[1], TEXT_BOX[2] - 1, TEXT_BOX[3] - 1],
                fill=(255, 255, 255, 255))  # 整个 box 涂满不透明白色

    font = _font(FONT_SIZE_CASCADE[0])
    new_cell = bake_cell(cell, "春", font)  # 极短标题，box 内应大部分是纯色带

    px = new_cell.load()
    # 角落（box 内但远离"春"字渲染中心）必须是纯色带，不能还留有原来的白色
    corner = px[TEXT_BOX[0] + 1, TEXT_BOX[1] + 1]
    assert corner == (BAND_COLOR[0], BAND_COLOR[1], BAND_COLOR[2], BAND_ALPHA), corner


def test_bake_cell_alpha_composite_over_original_would_ghost():
    """对照组：证明如果改用"半透明合成盖在原不透明墨迹上"（旧的错误做法）
    确实会留下可辨认的残影灰色，而不是纯色带——量化这条决策的必要性，不是
    凭直觉断言。"""
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    d = ImageDraw.Draw(cell)
    d.rectangle([TEXT_BOX[0], TEXT_BOX[1], TEXT_BOX[2] - 1, TEXT_BOX[3] - 1],
                fill=(255, 255, 255, 255))

    band = Image.new("RGBA", cell.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bd.rectangle([TEXT_BOX[0], TEXT_BOX[1], TEXT_BOX[2] - 1, TEXT_BOX[3] - 1],
                 fill=(BAND_COLOR[0], BAND_COLOR[1], BAND_COLOR[2], BAND_ALPHA))
    ghosted = Image.alpha_composite(cell, band)  # 半透明合成，不是直接写像素

    px = ghosted.load()
    corner = px[TEXT_BOX[0] + 1, TEXT_BOX[1] + 1]
    # 合成结果不是纯色带——原白色透了上来（这就是要避免的残影）
    assert corner != (BAND_COLOR[0], BAND_COLOR[1], BAND_COLOR[2], BAND_ALPHA)
    assert corner[0] > BAND_COLOR[0]  # 明显偏亮，残留白色痕迹


def test_bake_cell_centers_text_horizontally():
    """短标题应在 TEXT_BOX 内居中，不是左对齐——这是与 plot/ 排版取向不同
    的地方（plot/ 左对齐顶对齐，scene/ 实测水平垂直都居中，见 spec 第 4
    节），用可测的方式钉住不回归成"复用 plot 的左对齐逻辑"。"""
    font = _font(FONT_SIZE_CASCADE[0])
    layer = render_text_layer("春", font)
    bbox = layer.split()[-1].getbbox()
    assert bbox is not None
    cx = (bbox[0] + bbox[2]) / 2
    box_cx = (TEXT_BOX[0] + TEXT_BOX[2]) / 2
    assert abs(cx - box_cx) <= 2  # 允许 1-2px 的字形不对称舍入


# ---------------------------------------------------------------------------
# 5. 像素保真闸（TEXT_BOX 之外必须逐字节不变）
# ---------------------------------------------------------------------------

def test_find_outside_box_diffs_detects_change_outside_box():
    a = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    b = a.copy()
    b.putpixel((0, 0), (255, 0, 0, 255))  # x=0 在 TEXT_BOX(5,0,140,15) 之外
    diffs = find_outside_box_diffs(a, b, TEXT_BOX)
    assert (0, 0) in diffs


def test_find_outside_box_diffs_ignores_change_inside_box():
    a = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 153))
    b = a.copy()
    b.putpixel((70, 7), (255, 0, 0, 255))  # 在 TEXT_BOX 内
    diffs = find_outside_box_diffs(a, b, TEXT_BOX)
    assert diffs == []


def test_bake_sheet_real_data_zero_pixel_violations():
    """195 张真实卡全量跑一遍（每卡按其解析出的级联字号渲染），TEXT_BOX
    之外必须逐像素与原图一致——这是对 run() 报告里
    pixel_preservation_violations 字段的独立复现，不依赖对 run() 内部实现
    的信任。像素保全闸的矩形本身与字号无关（TEXT_BOX 是模块级常量，见
    module docstring "v3 update"），这里用混合字号（11px 为主、4 张 10px）
    的真实数据直接验证这条不变量没有因为级联改动而退化。"""
    titles = _real_titles()
    fonts_by_size = load_fonts()
    plans, _fallbacks, hard_failures = build_render_plan(titles, fonts_by_size)
    assert hard_failures == []
    fonts_by_card = resolve_fonts_by_card(plans, fonts_by_size)
    for sheet_num in (1, 2):
        _, diffs = bake_sheet(sheet_num, titles, fonts_by_card)
        bad = {c: d for c, d in diffs.items() if d}
        assert bad == {}, f"sheet {sheet_num} has violations: {bad}"


def test_real_chrome_identical_outside_text_box_across_different_cards():
    """两张内容完全不同的真实卡片（card1 与 card150，分属两张 sheet），
    TEXT_BOX 之外的像素必须逐字节相同——直接证据支撑"背景是跨格统一模板，
    不是逐格照片"这条设计前提（若不成立，固定矩形闸本身就不该用）。"""
    sheet1 = Image.open(sheet_path(1)).convert("RGBA")
    sheet2 = Image.open(sheet_path(2)).convert("RGBA")
    _, box1 = cell_box(1)
    _, box2 = cell_box(150)
    c1 = sheet1.crop(box1)
    c150 = sheet2.crop(box2)
    p1, p150 = c1.load(), c150.load()
    diffs = []
    for y in range(CELL_H):
        for x in list(range(0, TEXT_BOX[0])) + list(range(TEXT_BOX[2], CELL_W)):
            if p1[x, y] != p150[x, y]:
                diffs.append((x, y))
    assert diffs == []


# ---------------------------------------------------------------------------
# 6. 端到端：真实数据全量跑批
# ---------------------------------------------------------------------------

def test_real_run_report_is_clean(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.bake_scene.OUT_DIR", str(tmp_path))
    report = run(write=True, with_cellzoom=True)
    assert report["num_cards"] == NUM_CARDS
    assert report["overflow"] == []                # 硬失败（级联穷尽）：0
    assert report["pixel_preservation_violations"] == []
    assert report["ink_outliers"] == []
    assert report["vertical_clip_risks"] == []
    # 回落必须可见地记在返回报告里——不是"195 张全渲好了"就完事
    assert report["font_size_cascade"] == FONT_SIZE_CASCADE
    assert report["font_size_default"] == FONT_SIZE_CASCADE[0]
    assert sorted(fb["card"] for fb in report["fallbacks"]) == [2, 90, 180, 182]
    for fb in report["fallbacks"]:
        assert fb["font_size"] == 10
        assert fb["overflowed_at"] == [11]
        assert fb["reason"]  # 非空的人类可读理由
    assert len(report["cell_font_sizes"]) == NUM_CARDS
    assert (tmp_path / "scene_1_a.png").exists()
    assert (tmp_path / "scene_2_a.png").exists()
    assert (tmp_path / "_compare.png").exists()
    assert (tmp_path / "_cellzoom.png").exists()
    assert (tmp_path / "manifest.json").exists()

    # manifest.json 落盘内容必须与内存报告一致（结构化回落记录同样落盘）
    import json
    with open(tmp_path / "manifest.json", encoding="utf-8") as f:
        disk_report = json.load(f)
    assert disk_report["fallbacks"] == report["fallbacks"]
    assert disk_report["cell_font_sizes"] == report["cell_font_sizes"]
    assert disk_report["font_size_cascade"] == report["font_size_cascade"]


def test_output_sheets_are_correct_size_and_mode():
    titles = _real_titles()
    fonts_by_size = load_fonts()
    plans, _fallbacks, hard_failures = build_render_plan(titles, fonts_by_size)
    assert hard_failures == []
    fonts_by_card = resolve_fonts_by_card(plans, fonts_by_size)
    new_sheet, _ = bake_sheet(1, titles, fonts_by_card)
    assert new_sheet.size == (SHEET_W, SHEET_H)
    assert new_sheet.mode == "RGBA"


# ---------------------------------------------------------------------------
# 7. CLI / _cellzoom.png 选格：回落必须在三处（CLI/manifest/report）都可见，
#    且 _cellzoom.png 的选格必须把回落格与其真实同行邻格摆在一起。
# ---------------------------------------------------------------------------

def test_cli_reports_fallbacks(capsys, monkeypatch):
    """CLI 输出必须点名每张回落卡降到了几号字，不能只报一个数字。"""
    monkeypatch.setattr(sys, "argv", ["bake_scene.py", "--check"])
    from tools.bake_scene import main
    main()
    out = capsys.readouterr().out
    assert "fallbacks" in out
    for card in (2, 90, 180, 182):
        assert f"card {card}: -> 10px" in out


def test_cellzoom_cards_include_fallback_cards_and_real_row_neighbors():
    """本轮用户要看的核心问题：_cellzoom.png 必须把每张回落卡与它在真实
    网格里的同行邻格摆在一起。用 cell_position()（真值来源，非硬编码坐标）
    动态算出每张回落卡的同行邻居，钉住"CELLZOOM_CARDS 至少覆盖这些邻格"
    这条要求，不依赖"今天恰好选对了"这件事。"""
    titles = _real_titles()
    fonts_by_size = load_fonts()
    plans, fallbacks, hard_failures = build_render_plan(titles, fonts_by_size)
    assert hard_failures == []
    fallback_cards = {c for c, _size, _tried in fallbacks}
    assert fallback_cards == {2, 90, 180, 182}
    assert fallback_cards <= set(CELLZOOM_CARDS)
    for card in fallback_cards:
        sheet, row, _col = cell_position(card)
        neighbors = [c for c in range(1, NUM_CARDS + 1)
                     if cell_position(c)[:2] == (sheet, row)]
        assert set(neighbors) <= set(CELLZOOM_CARDS), (
            f"card {card}'s real row-mates {neighbors} not all in "
            f"CELLZOOM_CARDS {CELLZOOM_CARDS}")


def test_build_cellzoom_image_runs_with_real_cascade_result():
    titles = _real_titles()
    fonts_by_size = load_fonts()
    plans, _fb, hard_failures = build_render_plan(titles, fonts_by_size)
    assert hard_failures == []
    fonts_by_card = resolve_fonts_by_card(plans, fonts_by_size)
    img = build_cellzoom_image(titles, fonts_by_card, plans)
    assert img.mode == "RGBA"
    assert img.size[0] > 0 and img.size[1] > 0
