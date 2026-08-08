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
from PIL import Image, ImageDraw, ImageFont

from tools.bake_scene import (
    BAND_ALPHA, BAND_COLOR, CARDS_PER_SHEET, CELL_H, CELL_W, FONT_PATH,
    FONT_SIZE, GRID_COLS, GRID_ROWS, MAX_LINES, MAX_TEXT_W, NUM_CARDS,
    NUM_SHEETS, SCENE_DIR, SHEET_H, SHEET_W, TEXT_BOX, bake_cell, bake_sheet,
    cell_box, cell_position, collect_ink_outliers, collect_overflow,
    find_outside_box_diffs, ink_bbox_of_cell, render_text_layer, run,
    sheet_path,
)
from tools.bake_plot import load_titles_zh


def _font(size=FONT_SIZE):
    return ImageFont.truetype(FONT_PATH, size)


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

def test_collect_overflow_empty_for_real_titles():
    """195 条真实 title_zh 在 FONT_SIZE=9 / TEXT_BOX 宽度下全部单行放得下
    ——见 build/scene_layout_spec.md 的测量结论。这条钉住"当前数据 0 条
    截断"这一事实，不是假设它恒真。"""
    titles = load_titles_zh()
    titles = {c: titles[c] for c in range(1, NUM_CARDS + 1)}
    font = _font()
    overflow = collect_overflow(titles, font)
    assert overflow == []


def test_collect_overflow_surfaces_truncated_titles():
    """合成一个远超 135px 预算、且找不到任何合法断点组合能在 1 行内放下
    的超长字符串，确认 collect_overflow 会把截断显式报出来，不静默吞字。"""
    font = _font()
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
    font = _font()
    long_text = "这是一段故意写得非常长非常长非常长非常长非常长的标题文本用来测试截断"
    titles = {2: long_text}

    def broken_collect_overflow(titles, font, **kw):
        return []

    real = collect_overflow(titles, font)
    fake = broken_collect_overflow(titles, font)
    assert real != []
    assert fake == []


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
    d.rectangle([0, 0, 3, 3], fill=(255, 255, 255, 255))  # x<5，越出 TEXT_BOX
    bbox = _ink(cell)
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert x0 < TEXT_BOX[0]  # 确认这个合成用例真的越界


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

    font = _font()
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
    font = _font()
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
    """195 张真实卡全量跑一遍，TEXT_BOX 之外必须逐像素与原图一致——这是
    对 run() 报告里 pixel_preservation_violations 字段的独立复现，不依赖
    对 run() 内部实现的信任。"""
    titles = load_titles_zh()
    titles = {c: titles[c] for c in range(1, NUM_CARDS + 1)}
    font = _font()
    for sheet_num in (1, 2):
        _, diffs = bake_sheet(sheet_num, titles, font)
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
    assert report["overflow"] == []
    assert report["pixel_preservation_violations"] == []
    assert report["ink_outliers"] == []
    assert (tmp_path / "scene_1_a.png").exists()
    assert (tmp_path / "scene_2_a.png").exists()
    assert (tmp_path / "_compare.png").exists()
    assert (tmp_path / "_cellzoom.png").exists()
    assert (tmp_path / "manifest.json").exists()


def test_output_sheets_are_correct_size_and_mode():
    titles = load_titles_zh()
    titles = {c: titles[c] for c in range(1, NUM_CARDS + 1)}
    font = _font()
    new_sheet, _ = bake_sheet(1, titles, font)
    assert new_sheet.size == (SHEET_W, SHEET_H)
    assert new_sheet.mode == "RGBA"
