"""tools/bake_select_map.py — png/select/sel_map_1_a.png（探索地图 10 地点 x
on/off 标签表，comSelectMap 的地点表）烤字回填。

覆盖硬约束闸（见 tools/bake_select_map.py 模块 docstring 与
.superpowers/sdd/2026-08-07-p4-polish-pass/bake-select-report.md 的既有惯例）：
  1. 格号↔地点映射是本图的承重点——20 个格子里错一格，两个地点就互换了。
     每次运行都从 lua 源码**重新解析**（不是缓存/一次性人工核对）钉死这个映射，
     且是**两条独立证据**：地点编号表（值恰为 1..10）与真正决定像素的
     layerClip 偏移表（列偏移 {0,120}、行偏移 {0,52,104,156,208}）。
     2026-08-31 换反编译基座后，这三张表从十条 `v0.<key> = <N>` 语句变成了
     `comSelectMap` 里三行 `{art = 1, ...}` 表构造器——闸的**语义**不变，
     只换了解析形状；绝不允许退化成"信任模块里硬编码的顺序"。
  2. 覆盖率（10/10 地点）必须每次独立重算，中文源缺失时必须报错停下。
  3. 字号级联的"零溢出"判据必须是真实渲染墨迹，不能只是字符数估算。
  4. TEXT_BOX 之外的像素必须逐字节保真。
  5. 静默截断/静默回落/静默映射错位三类失败模式必须都有对应的会变红的测试。
"""
import json
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

import tools.bake_select_map as bsm
from tools.bake_select_map import (
    GRID_CELL_H, GRID_CELL_W, GRID_COLS, GRID_LOCATIONS_LEFT,
    GRID_LOCATIONS_RIGHT, GRID_ROWS, MAP_FILL_BY_VARIANT, MAP_FONT_CASCADE,
    MAP_MAX_TEXT_W, MAP_TEXT_BOX, SHEET_H, SHEET_W, SOURCE_IMAGE, all_cells,
    absolute_box, bake_cell, build_map_render_plan, cell_origin,
    compute_coverage, find_all_outside_box_diffs, load_fonts,
    location_for, lua_grid_from_source, lua_order_from_source,
    measure_fill_colors, measure_stroke_colors, run, variant_for,
)
from tools.bake_select import measure_ink_extent, TEXT_FILL_COLOR

FONT_PATH = "third_party/LXGWWenKai-Regular.ttf"


from tools.ui_font import truetype as _ui_truetype


def _font(size):
    # **必须走 ui_font.truetype，不能裸调 ImageFont.truetype。** FONT_PATH 现在可能
    # 指向变量字体，裸调拿到的是它的默认实例（思源黑体是 ExtraLight＝权重轴最小值），
    # 于是测试量的字重和工具烤的根本不是同一档——而且不报错、不缺字，只是更细一点。
    return _ui_truetype("select", size)


def _real_image():
    return Image.open(SOURCE_IMAGE).convert("RGBA")


# ---------------------------------------------------------------------------
# 1. 资产几何：240x260、2x10 网格、120x26 格子、3px 边框、共享透明图标缺口
# ---------------------------------------------------------------------------

def test_source_image_size_is_240x260():
    im = _real_image()
    assert im.size == (SHEET_W, SHEET_H) == (240, 260)


def test_grid_covers_sheet_exactly():
    assert GRID_COLS * GRID_CELL_W == SHEET_W
    assert GRID_ROWS * GRID_CELL_H == SHEET_H


def test_all_cells_enumerates_20_real_cells():
    cells = all_cells()
    assert len(cells) == 20
    assert len(set((c, r) for c, r, _k, _v in cells)) == 20


def test_border_frame_is_3px_all_sides_real_asset():
    """对真实素材逐格核验：3px 边框环在四边整宽/整高存在（不是发丝线），
    与 tools/bake_select.py 250x26 按钮同一套约定，但这里独立对
    120x26 格子重新测量，不假设复用。"""
    im = _real_image()
    px = im.load()
    for col, row, _key, variant in all_cells():
        x0, y0 = cell_origin(col, row)
        border_colors = set()
        for y in range(y0, y0 + GRID_CELL_H):
            for x in (x0, x0 + 1, x0 + 2, x0 + GRID_CELL_W - 1,
                      x0 + GRID_CELL_W - 2, x0 + GRID_CELL_W - 3):
                border_colors.add(px[x, y])
        # 边框环颜色不应等于该态的内部填充色（真实边框环，不是被填充色吞掉）
        assert MAP_FILL_BY_VARIANT[variant] not in border_colors


def test_shared_icon_notch_is_transparent_and_outside_text_box():
    """x∈[5,10], 相对格顶 y偏移∈[5,6] 的图标缺口在全部 20 个真实格子里都
    透明，且落在 MAP_TEXT_BOX 之外——不需要特判代码，像素保全闸自动保护它。
    （y 偏移实测为 5/6，不是 3px 边框内的 2/3——已用逐格实测复核，不是
    照抄按钮模块的猜测）。"""
    im = _real_image()
    px = im.load()
    for col, row, _key, _variant in all_cells():
        x0, y0 = cell_origin(col, row)
        for dy in (5, 6):
            for dx in range(5, 11):
                assert px[x0 + dx, y0 + dy][3] == 0, (col, row, dx, dy)
        assert 5 < MAP_TEXT_BOX[0] and 10 < MAP_TEXT_BOX[0], (
            "图标缺口理应完全落在 TEXT_BOX 左边界之外")


def test_interior_fill_matches_measured_constants_real_asset():
    measure_fill_colors(_real_image())   # 不抛异常即通过


def test_interior_fill_mismatch_is_detected(monkeypatch):
    """变异形态：如果测得的背景色和常量对不上（例如未来素材换了色板），
    measure_fill_colors 必须报错，不能悄悄放行。"""
    fake = dict(MAP_FILL_BY_VARIANT)
    fake["on"] = (1, 2, 3, 255)
    monkeypatch.setattr(bsm, "MAP_FILL_BY_VARIANT", fake)
    with pytest.raises(RuntimeError, match="not uniformly"):
        measure_fill_colors(_real_image())


# ---------------------------------------------------------------------------
# 2. 格号↔地点映射：本图承重点，双重证据（lua 源头交叉核验 + 视觉读图）
# ---------------------------------------------------------------------------

def test_lua_order_from_source_matches_module_constant():
    """核心闸之一：重新解析 lua_scripts/snr_common.lua 里 comSelectMap 的
    地点编号表，必须与 GRID_LOCATIONS_LEFT+RIGHT 完全一致——这是本图
    "格号↔地点映射"的机械回归检查，不依赖任何一次性人工读图结论。"""
    lua_order = lua_order_from_source()
    assert lua_order == GRID_LOCATIONS_LEFT + GRID_LOCATIONS_RIGHT
    assert lua_order == ["art", "music", "health", "staffRoom", "court",
                          "ground", "class", "roof", "corridor", "library"]


def test_lua_order_ignores_the_sibling_offset_tables():
    """回归（2026-08-31 换基座后的真实污染源）：comSelectMap 里紧挨着编号表
    还有两张**同样 10 个地点键**的表——layerClip 的列偏移 {0,120} 与行偏移
    {0,52,104,156,208}。一个"扫全文件所有 `key = N`"的解析器会把三张表混在
    一起，得出的顺序随行序而变。解析函数必须只认"取值恰为 1..10"的那一张，
    并且只在 comSelectMap 函数体内找。"""
    tables = bsm._com_select_map_tables(bsm.LUA_COMMON)
    assert len(tables) == 3, "本基座里 comSelectMap 恰有 3 张 10 键表"
    assert sorted(tables[0].values()) == list(range(1, 11))
    order = lua_order_from_source()
    assert len(order) == 10
    assert set(order) == set(GRID_LOCATIONS_LEFT) | set(GRID_LOCATIONS_RIGHT)


def test_lua_grid_from_source_matches_module_constant():
    """核心闸之二（比编号表更硬）：真正决定"哪个地点显示这张 240x260 图的
    哪个 120x26 矩形"的是 comSelectMap 喂给 layerClip 的两张偏移表。
    col = x偏移 / GRID_CELL_W、loc_idx = y偏移 / (2*GRID_CELL_H)，必须与
    GRID_LOCATIONS_LEFT/RIGHT 逐项一致。"""
    left, right = lua_grid_from_source()
    assert left == GRID_LOCATIONS_LEFT == ["art", "music", "health",
                                           "staffRoom", "court"]
    assert right == GRID_LOCATIONS_RIGHT == ["ground", "class", "roof",
                                             "corridor", "library"]


def test_lua_parsers_raise_when_the_table_is_gone(tmp_path, monkeypatch):
    """变异形态：换了基座/改了源码导致表找不到时，必须硬报错停下，不能返回
    半张表或退回硬编码顺序。"""
    fake = tmp_path / "snr_common_stub.lua"
    fake.write_text("cHan2Zen = function(l1_0)\nend\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="comSelectMap"):
        lua_order_from_source(str(fake))
    with pytest.raises(RuntimeError, match="comSelectMap"):
        lua_grid_from_source(str(fake))

    fake2 = tmp_path / "snr_common_stub2.lua"
    keys = GRID_LOCATIONS_LEFT + GRID_LOCATIONS_RIGHT
    only_offsets = ", ".join(f"{k} = {0 if i < 5 else 120}"
                             for i, k in enumerate(keys))
    fake2.write_text(
        "comSelectMap = function(l1_0)\n"
        f"local l1_7 = {{{only_offsets}}}\n"
        "end\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="location-id"):
        lua_order_from_source(str(fake2))


def test_lua_parsers_are_scoped_to_comSelectMap_and_refuse_ambiguity(tmp_path):
    """两个"拆闸"变异形态各配一条：
    (a) 解析范围放宽到全文件——文件别处一张同样 10 键、值 1..10 的诱饵表就会
        污染顺序（这里诱饵是错位的，正确实现必须忽略它）；
    (b) 命中多张同类表时"随便取第一张"——必须硬报错，不能猜。"""
    keys = GRID_LOCATIONS_LEFT + GRID_LOCATIONS_RIGHT
    decoy_keys = list(reversed(keys))
    real = ", ".join(f"{k} = {i + 1}" for i, k in enumerate(keys))
    decoy = ", ".join(f"{k} = {i + 1}" for i, k in enumerate(decoy_keys))

    scoped = tmp_path / "scoped.lua"
    scoped.write_text(
        f"someOtherFunc = function()\nlocal l1_0 = {{{decoy}}}\nend\n"
        f"comSelectMap = function(l1_0)\nlocal l1_5 = {{{real}}}\nend\n"
        f"yetAnother = function()\nlocal l1_0 = {{{decoy}}}\nend\n",
        encoding="utf-8")
    assert lua_order_from_source(str(scoped)) == keys

    ambiguous = tmp_path / "ambiguous.lua"
    ambiguous.write_text(
        f"comSelectMap = function(l1_0)\nlocal l1_5 = {{{real}}}\n"
        f"local l1_6 = {{{decoy}}}\nend\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="refusing to guess"):
        lua_order_from_source(str(ambiguous))


def test_run_refuses_to_bake_when_grid_mapping_diverges_from_lua(monkeypatch):
    """变异回归：把 GRID_LOCATIONS_LEFT/RIGHT 错位一格（模拟本轮任务点名的
    "格号↔地点映射错位一格"故障），run() 必须整体拒绝渲染。"""
    swapped_left = ["music", "art", "health", "staffRoom", "court"]  # 错位一格
    monkeypatch.setattr(bsm, "GRID_LOCATIONS_LEFT", swapped_left)
    with pytest.raises(RuntimeError, match="承重点|does not match"):
        run(write=False)


def test_run_id_order_check_fires_even_if_the_grid_check_is_neutered(monkeypatch):
    """对称的另一半：伪造 layerClip 偏移表检查永远通过，编号表检查仍须拦住
    错位的映射。两条闸各自独立会红，才谈得上"双重证据"。"""
    swapped_left = ["music", "art", "health", "staffRoom", "court"]
    monkeypatch.setattr(bsm, "GRID_LOCATIONS_LEFT", swapped_left)
    monkeypatch.setattr(bsm, "lua_grid_from_source",
                        lambda *a, **kw: (swapped_left, GRID_LOCATIONS_RIGHT))
    with pytest.raises(RuntimeError, match="location-id"):
        run(write=False)


def test_run_grid_offset_check_fires_even_if_the_id_check_is_neutered(monkeypatch):
    """两条证据必须**各自独立**会红：把编号表检查伪造成永远通过（模拟"编号表
    被改得和错位后的模块常量一致"或"第一道闸被绕过"），第二道闸——真正决定像素
    的 layerClip 偏移表——仍须拦住错位的映射。"""
    swapped_left = ["music", "art", "health", "staffRoom", "court"]
    monkeypatch.setattr(bsm, "GRID_LOCATIONS_LEFT", swapped_left)
    monkeypatch.setattr(bsm, "lua_order_from_source",
                        lambda *a, **kw: swapped_left + GRID_LOCATIONS_RIGHT)
    with pytest.raises(RuntimeError, match="layerClip"):
        run(write=False)


def test_location_for_and_variant_for_agree_with_grid_lists():
    for row in range(GRID_ROWS):
        expected_variant = "on" if row % 2 == 0 else "off"
        assert variant_for(row) == expected_variant
        assert location_for(0, row) == GRID_LOCATIONS_LEFT[row // 2]
        assert location_for(1, row) == GRID_LOCATIONS_RIGHT[row // 2]


# ---------------------------------------------------------------------------
# 3. 覆盖率：10/10 地点，缺失必须硬停
# ---------------------------------------------------------------------------

def test_compute_coverage_is_10_of_10_today():
    covered, missing = compute_coverage()
    assert missing == []
    assert len(covered) == 10
    assert set(covered) == set(GRID_LOCATIONS_LEFT) | set(GRID_LOCATIONS_RIGHT)


def test_compute_coverage_known_translations():
    covered, _missing = compute_coverage()
    assert covered["art"]["zh"] == "美术室"
    assert covered["music"]["zh"] == "音乐室"
    assert covered["health"]["zh"] == "保健室"
    assert covered["staffRoom"]["zh"] == "教职员室"
    assert covered["court"]["zh"] == "中庭"
    assert covered["ground"]["zh"] == "操场"
    assert covered["class"]["zh"] == "教室"
    assert covered["roof"]["zh"] == "天台"
    assert covered["corridor"]["zh"] == "走廊"
    assert covered["library"]["zh"] == "图书室"


def test_compute_coverage_raises_on_unknown_key(tmp_path, monkeypatch):
    bad_path = tmp_path / "select_map_zh_bad.jsonl"
    with open(bad_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"key": "not_a_real_location", "jp": "x", "zh": "x"}) + "\n")
    monkeypatch.setattr(bsm, "DATA_MAP_ZH", str(bad_path))
    with pytest.raises(ValueError, match="unknown location key"):
        compute_coverage()


def test_run_refuses_to_bake_when_coverage_incomplete(tmp_path, monkeypatch):
    def fake_compute_coverage():
        covered, _missing = compute_coverage()
        del covered["library"]
        return covered, ["library"]

    monkeypatch.setattr(bsm, "compute_coverage", fake_compute_coverage)
    monkeypatch.setattr(bsm, "OUT_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="missing zh"):
        run(write=True)
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# 4. 字号级联：真实渲染墨迹判据，已知回落集合 = {corridor}
# ---------------------------------------------------------------------------

def test_build_map_render_plan_real_texts_zero_hard_failures_known_fallback():
    covered, missing = compute_coverage()
    assert missing == []
    texts = {k: covered[k]["zh"] for k in covered}
    fonts_by_size = load_fonts(MAP_FONT_CASCADE)
    plans, fallbacks, hard_failures = build_map_render_plan(texts, fonts_by_size)
    assert hard_failures == []
    assert len(plans) == 10
    fb_keys = sorted(k for k, _s, _t in fallbacks)
    # 2026-08-28 起为空：走廊原本在 18px 顶部越界 1px，那是 anchor="mm" 按字体
    # 设计度量居中造成的位移，不是字太大。改按真实墨迹居中后 10/10 都进 18px。
    assert fb_keys == []
    for k, size, tried in fallbacks:
        assert size == MAP_FONT_CASCADE[-1] == 17
        assert tried == [MAP_FONT_CASCADE[0]]
    assert {plans[k]["font_size"] for k in plans} == {MAP_FONT_CASCADE[0]}


def test_all_locations_fit_at_18px_after_ink_centering():
    """这条测试**换了主张**，原因值得记下来。

    原先它断言「走廊在 18px 下顶部越界 1px（y0=2 < box y0=3）」——那是真实测量，
    但测的是 `anchor="mm"` 下的结果：mm 按字体**设计度量**居中，墨迹被整体推离
    盒心，于是"越界"的其实是定位，不是字。2026-08-28 改为按**真实墨迹**居中后，
    10 个地点在 18px 全部装得下，回落集从 ['corridor'] 变成空。

    它守的性质没变：**判据是真实渲染墨迹，不是字符数估算**。
    """
    font18 = _font(18)
    for zh in ("走廊", "教职员室", "音乐室", "保健室", "图书室"):
        x0, x1, y0, y1 = measure_ink_extent(zh, font18, MAP_TEXT_BOX)
        assert MAP_TEXT_BOX[0] <= x0 and x1 <= MAP_TEXT_BOX[2], zh
        assert MAP_TEXT_BOX[1] <= y0 and y1 <= MAP_TEXT_BOX[3], zh


def test_corridor_fits_at_17px_real_measurement():
    font17 = _font(17)
    ext = measure_ink_extent("走廊", font17, MAP_TEXT_BOX)
    x0, x1, y0, y1 = ext
    assert MAP_TEXT_BOX[0] <= x0 and x1 <= MAP_TEXT_BOX[2]
    assert MAP_TEXT_BOX[1] <= y0 and y1 <= MAP_TEXT_BOX[3]


def test_build_map_render_plan_hard_failure_when_smallest_tier_overflows():
    """build_map_render_plan()（本模块的便捷封装）把 cascade 定死为
    MAP_FONT_CASCADE=[18,17]，这里改用它底下复用的通用 build_render_plan
    并显式传 cascade=[smallest]（与 tools/bake_select.py 自己的同名测试
    同一手法），验证"级联耗尽即硬失败"这条契约独立于按钮模块也成立。"""
    from tools.bake_select import build_render_plan
    smallest = MAP_FONT_CASCADE[-1]
    fonts_by_size = {smallest: _font(smallest)}
    long_text = "这是故意写得很长很长用来测试硬失败情形的文本"
    texts = {"fake_location": long_text}
    plans, fallbacks, hard_failures = build_render_plan(
        texts, fonts_by_size, cascade=[smallest], box=MAP_TEXT_BOX,
        max_width=MAP_MAX_TEXT_W)
    assert plans == {}
    assert fallbacks == []
    assert len(hard_failures) == 1
    key, text, size, _info = hard_failures[0]
    assert key == "fake_location"
    assert text == long_text
    assert size == smallest


def test_run_raises_before_writing_any_file_on_hard_failure(tmp_path, monkeypatch):
    covered, missing = compute_coverage()
    assert missing == []

    def fake_compute_coverage():
        c = dict(covered)
        c["art"] = dict(c["art"])
        c["art"]["zh"] = "这是故意写得很长很长用来测试硬失败情形的文本" * 2
        return c, []

    monkeypatch.setattr(bsm, "compute_coverage", fake_compute_coverage)
    monkeypatch.setattr(bsm, "OUT_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="cascade .* exhausted"):
        run(write=True)
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# 5. 像素保全闸：MAP_TEXT_BOX 之外逐字节不变
# ---------------------------------------------------------------------------

def test_find_all_outside_box_diffs_detects_change_outside_box():
    orig = _real_image()
    corrupted = orig.copy()
    # 在某格边框区（非 TEXT_BOX 内）改一个像素
    corrupted.putpixel((0, 0), (255, 0, 0, 255))
    diffs = find_all_outside_box_diffs(orig, corrupted)
    assert any(x == 0 and y == 0 for _c, _r, x, y in diffs)


def test_find_all_outside_box_diffs_ignores_change_inside_box():
    orig = _real_image()
    corrupted = orig.copy()
    # (col=0,row=0) 格内 TEXT_BOX 内的一点：cell 原点(0,0) + box 内部点(50,12)
    corrupted.putpixel((50, 12), (255, 0, 0, 255))
    diffs = find_all_outside_box_diffs(orig, corrupted)
    assert diffs == []


def test_find_all_outside_box_diffs_disabled_would_hide_real_corruption():
    """变异回归形态：模拟保全闸被关闭（硬编码返回 []）的坏实现，证明如果
    真的这样改，边框区的真实像素破坏会从"能看到"变成"看不到"。"""
    orig = _real_image()
    corrupted = orig.copy()
    corrupted.putpixel((0, 0), (255, 0, 0, 255))

    real_diffs = find_all_outside_box_diffs(orig, corrupted)

    def broken(*a, **kw):
        return []

    fake_diffs = broken(orig, corrupted)
    assert real_diffs != []
    assert fake_diffs == []


def test_run_end_to_end_zero_pixel_violations(tmp_path, monkeypatch):
    monkeypatch.setattr(bsm, "OUT_DIR", str(tmp_path))
    report, new_sheet, orig, diffs = run(write=True)
    assert diffs == []
    assert report["pixel_preservation_violation_count"] == 0
    assert os.path.exists(os.path.join(str(tmp_path), "sel_map_1_a.png"))
    assert os.path.exists(os.path.join(str(tmp_path), "_map1_zoom.png"))
    assert os.path.exists(os.path.join(str(tmp_path), "map_manifest.json"))
    assert new_sheet.size == orig.size == (SHEET_W, SHEET_H)
    with open(os.path.join(str(tmp_path), "map_manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["num_locations"] == 10
    assert manifest["lua_order_check"]["match"] is True
    assert manifest["lua_grid_check"]["match"] is True
    assert manifest["lua_grid_check"]["lua_grid"] == [
        GRID_LOCATIONS_LEFT, GRID_LOCATIONS_RIGHT]
    assert manifest["overflow"] == []


# ---------------------------------------------------------------------------
# 6. 描边/填充色：从这个具体素材实测，非沿用按钮模块的常量
# ---------------------------------------------------------------------------

def test_measure_stroke_colors_qualitative_on_red_off_blue():
    strokes = measure_stroke_colors(_real_image())
    on_r, on_g, on_b, on_a = strokes["on"]
    off_r, off_g, off_b, off_a = strokes["off"]
    assert on_r > on_b, "on 态描边应偏红"
    assert off_b > off_r, "off 态描边应偏蓝"


def test_measure_stroke_colors_on_is_fully_opaque_off_is_not():
    """本素材的特有事实（与 tools/bake_select.py 的按钮素材不同）：on 态
    描边完全不透明，off 态描边从未达到 alpha=255——如实记录，不假装它是
    255。"""
    strokes = measure_stroke_colors(_real_image())
    assert strokes["on"][3] == 255
    assert strokes["off"][3] < 255


def test_measure_stroke_colors_raises_if_no_ink_found(monkeypatch):
    blank = Image.new("RGBA", (SHEET_W, SHEET_H), MAP_FILL_BY_VARIANT["on"])
    with pytest.raises(RuntimeError, match="no ink pixels"):
        measure_stroke_colors(blank)


# ---------------------------------------------------------------------------
# 7. 渲染 / bake_cell：direct overwrite，不产生 ghosting
# ---------------------------------------------------------------------------

def test_bake_cell_erases_opaque_ink_without_ghosting():
    orig = _real_image()
    sheet = orig.copy()
    font = _font(18)
    strokes = measure_stroke_colors(orig)
    bake_cell(sheet, 0, 0, "美术室", font, strokes)
    # TEXT_BOX 内不应再残留原始日文墨迹的红色描边色（原 on 态描边）
    on_stroke = strokes["on"]
    bx0, by0, bx1, by1 = absolute_box(0, 0)
    px = sheet.load()
    # 抽样：原图里 (col=0,row=0) 格 TEXT_BOX 内曾有大量 on_stroke 像素，
    # 新图里这些像素位置的颜色理应改变（不能是原封不动的旧描边）。
    opx = orig.load()
    changed_any = False
    for y in range(by0, by1):
        for x in range(bx0, bx1):
            if opx[x, y] == on_stroke and px[x, y] != on_stroke:
                changed_any = True
                break
        if changed_any:
            break
    assert changed_any


def test_bake_cell_outside_box_untouched():
    orig = _real_image()
    sheet = orig.copy()
    font = _font(18)
    strokes = measure_stroke_colors(orig)
    bake_cell(sheet, 0, 0, "美术室", font, strokes)
    diffs = find_all_outside_box_diffs(orig, sheet)
    assert diffs == []


def test_render_text_centers_on_map_text_box():
    from tools.bake_select_map import render_text_layer_map
    font = _font(18)
    layer = render_text_layer_map(
        "中庭", font, TEXT_FILL_COLOR, (0, 0, 255, 255),
        (GRID_CELL_W, GRID_CELL_H), MAP_TEXT_BOX)
    bbox = layer.split()[-1].getbbox()
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    box_center_x = (MAP_TEXT_BOX[0] + MAP_TEXT_BOX[2]) / 2
    ink_center_x = (x0 + x1) / 2
    assert abs(ink_center_x - box_center_x) < 2.0


# ---------------------------------------------------------------------------
# 8. CLI smoke
# ---------------------------------------------------------------------------

def test_cli_check_mode_does_not_write_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bsm, "OUT_DIR", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["bake_select_map.py", "--check"])
    bsm.main()
    assert list(tmp_path.iterdir()) == []
    out = capsys.readouterr().out
    assert "locations: 10" in out
    assert "corridor" in out
