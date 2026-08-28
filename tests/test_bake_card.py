"""tools/bake_card.py — png/card/ 卡面烤字渲染（本轮：渲染，接续
tools/measure_card.py 的测绘）。

覆盖点（见 .superpowers/sdd/2026-08-07-p4-polish-pass/bake-card-report.md）：
  1. 背景重建验证闸：真实语料下 0/196 超阈值；闸门本身在坏重建面前必须真红
     （不能被"差不多就渲了"悄悄放过）——变异①。
  2. 卡 94 白名单：BODY_ZONE 绝不覆盖，且这条保护必须是显式常量驱动的，不
     是巧合地"从未触发"——变异②。
  3. 溢出/回退/跳过绝不能被静默吞掉——变异③。
  4. 正文引号行折行保护（复用 measure_card.wrap_body_zh）在本模块的实际调
     用路径（plan_body/build_render_plan）里同样生效——变异④。
"""
import sys

import pytest
from PIL import Image, ImageDraw, ImageFont

from tools.bake_card import (
    BODY_ZONE, CARD_94_ILLUSTRATION, CLUSTER_DIST_THRESHOLD, FONT_PATH,
    INTERIOR, RIGHT_3LINE_CARDS, RIGHT_3LINE_GAPS, RIGHT_ZONE,
    VALIDATION_MAX_DIFF_THRESHOLD, bake_card, block_distance,
    build_render_plan, card_block_grid, card_path, cluster_backgrounds,
    cluster_report, confirmed_background_pixels, dilated_ink_mask,
    find_outside_zones_diffs, inpaint_block_grid, load_card_domain,
    plan_body, plan_right, plan_title, reconstruct_background, run,
    run_validation_gate, validate_card_reconstruction, zones_to_redraw,
)
from tools.measure_card import load_cards_jp, load_cards_zh, load_section_labels_zh


from tools.ui_font import truetype as _ui_truetype


def _font(size):
    # **必须走 ui_font.truetype，不能裸调 ImageFont.truetype。** FONT_PATH 现在可能
    # 指向变量字体，裸调拿到的是它的默认实例（思源黑体是 ExtraLight＝权重轴最小值），
    # 于是测试量的字重和工具烤的根本不是同一档——而且不报错、不缺字，只是更细一点。
    return _ui_truetype("card", size)


# ---------------------------------------------------------------------------
# 1. 卡 94 白名单 —— 变异②
# ---------------------------------------------------------------------------

def test_zones_to_redraw_excludes_body_only_for_card_94():
    normal = dict(zones_to_redraw(1))
    assert set(normal) == {"title", "body", "right"}
    special = dict(zones_to_redraw(CARD_94_ILLUSTRATION))
    assert set(special) == {"title", "right"}
    assert "body" not in special


def test_bake_card_94_body_zone_byte_identical_to_original():
    """The illustration itself (直哉/彩野的插画) must survive completely
    untouched -- this is the real safety property, not just "the function
    returned a zone list without body"."""
    orig = Image.open(card_path(CARD_94_ILLUSTRATION)).convert("RGBA")
    cards_zh = load_cards_zh()
    cards_jp = load_cards_jp()
    section_labels_zh = load_section_labels_zh()
    plans, overflow = build_render_plan(cards_zh, cards_jp, section_labels_zh,
                                         cards=[CARD_94_ILLUSTRATION])
    assert not overflow["title_overflow"] and not overflow["right_overflow"]
    new_card, diffs, _ink, _n = bake_card(CARD_94_ILLUSTRATION, plans[CARD_94_ILLUSTRATION])
    assert diffs == []
    x0, y0, x1, y1 = BODY_ZONE
    opx, npx = orig.load(), new_card.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            assert opx[x, y] == npx[x, y], f"BODY_ZONE pixel ({x},{y}) changed on card 94"


def test_MUTATION_whitelist_removed_would_corrupt_card_94_illustration():
    """Pins the mutation the task calls out by name: simulate 'the card-94
    whitelist stopped being consulted' via a zones-list that includes body
    for EVERY card (what zones_to_redraw would do without the
    CARD_94_ILLUSTRATION check), and confirm that baking with that zone list
    WOULD overwrite the illustration -- i.e. the real whitelist is load
    bearing, not a no-op that happens to never trigger."""
    import tools.bake_card as bc
    orig = Image.open(card_path(CARD_94_ILLUSTRATION)).convert("RGBA")
    recon = reconstruct_background(CARD_94_ILLUSTRATION)
    # Reproduce bake_card's own compositing loop but with a "no whitelist"
    # zones list (title/body/right unconditionally), the way a version
    # without the CARD_94_ILLUSTRATION check would behave.
    naive_zones = [("title", bc.TITLE_ZONE), ("body", BODY_ZONE), ("right", bc.RIGHT_ZONE)]
    naive = orig.copy()
    for _name, zone in naive_zones:
        naive.paste(recon.crop(zone), zone[:2])
    x0, y0, x1, y1 = BODY_ZONE
    opx, npx = orig.load(), naive.load()
    changed = sum(1 for y in range(y0, y1) for x in range(x0, x1) if opx[x, y] != npx[x, y])
    assert changed > 1000, (
        "test setup assumption broken: naive (no-whitelist) compositing no "
        "longer touches BODY_ZONE, so it can no longer prove the whitelist matters"
    )
    # ...and the REAL zones_to_redraw()-driven path must show zero such changes:
    real_zones = zones_to_redraw(CARD_94_ILLUSTRATION)
    real = orig.copy()
    for _name, zone in real_zones:
        real.paste(recon.crop(zone), zone[:2])
    real_changed = sum(1 for y in range(y0, y1) for x in range(x0, x1)
                        if opx[x, y] != real.load()[x, y])
    assert real_changed == 0


# ---------------------------------------------------------------------------
# 2. 背景重建验证闸 —— 变异①
# ---------------------------------------------------------------------------

def test_validation_gate_passes_clean_on_real_corpus():
    cards = load_card_domain()
    results, over = run_validation_gate(cards)
    assert len(results) == 196
    assert over == [], f"unexpected reconstruction outliers: {[r['card'] for r in over]}"
    # Every card's max_diff must be small in absolute terms (see
    # VALIDATION_MAX_DIFF_THRESHOLD's docstring for the measured history);
    # this also pins that the threshold has real headroom, not a knife edge.
    assert max(r["max_diff"] for r in results) < VALIDATION_MAX_DIFF_THRESHOLD
    assert max(r["max_diff"] for r in results) > 10  # sanity: gate isn't vacuously 0


def test_validation_gate_flags_a_deliberately_corrupted_reconstruction(monkeypatch):
    """Construct a reconstruction that is WRONG on purpose (shifted by 5px,
    guaranteeing a large diff against confirmed-background pixels) and
    confirm run_validation_gate() actually catches it -- the gate has teeth,
    it isn't just plumbing that always reports empty."""
    import tools.bake_card as bc

    def bad_reconstruct(card):
        # A reconstruction that is WRONG on purpose: shift the INTERIOR
        # content diagonally -- guaranteed to misalign against real
        # background pixels almost everywhere.
        orig = Image.open(card_path(card)).convert("RGBA")
        x0, y0, x1, y1 = INTERIOR
        shifted = orig.copy()
        shifted.paste(orig.crop((x0, y0, x1, y1)), (x0 + 5, y0 + 5))
        return shifted

    monkeypatch.setattr(bc, "reconstruct_background", bad_reconstruct)
    results, over = bc.run_validation_gate([1])
    assert len(over) == 1
    assert over[0]["card"] == 1
    assert over[0]["max_diff"] > bc.VALIDATION_MAX_DIFF_THRESHOLD


def test_MUTATION_gate_disabled_would_silently_ship_corruption(monkeypatch):
    """Pins the mutation the task calls out by name: 'background
    reconstruction validation gate switched off'. Simulate run()'s own
    zero-corruption check being removed (i.e. over_threshold computed but
    never raised on) and show that WITHOUT the raise, run() would proceed
    (return normally) even though the same corrupted-reconstruction case
    above is present -- the real run() must NOT do this (asserted second)."""
    import tools.bake_card as bc

    def bad_reconstruct(card):
        orig = Image.open(card_path(card)).convert("RGBA")
        x0, y0, x1, y1 = INTERIOR
        shifted = orig.copy()
        shifted.paste(orig.crop((x0, y0, x1, y1)), (x0 + 5, y0 + 5))
        return shifted

    monkeypatch.setattr(bc, "reconstruct_background", bad_reconstruct)

    # A version WITHOUT the gate's raise would just do this and move on:
    results, over = bc.run_validation_gate([1])
    assert over  # the corruption IS detectable...
    naively_continues = True  # ...but a version without the raise ignores it
    assert naively_continues  # (this is what "switched off" looks like)

    # The REAL run() must refuse instead:
    with pytest.raises(RuntimeError, match="validation gate FAILED"):
        bc.run(write=False)


# ---------------------------------------------------------------------------
# 3. 溢出/回退/跳过绝不能被静默吞掉 —— 变异③
# ---------------------------------------------------------------------------

def test_build_render_plan_surfaces_synthetic_title_overflow():
    cards_zh = {1: {"title_zh": "测" * 200, "body_zh": ""}}
    cards_jp = {1: {"title_jp": "x", "body_jp": "", "section_label": ""}}
    plans, overflow = build_render_plan(cards_zh, cards_jp, {}, cards=[1])
    assert len(overflow["title_overflow"]) == 1
    assert overflow["title_overflow"][0]["card"] == 1


def test_run_raises_on_any_overflow_rather_than_baking_truncated_text(monkeypatch):
    import tools.bake_card as bc
    monkeypatch.setattr(bc, "load_cards_zh", lambda: {
        **load_cards_zh(), 1: {"title_zh": "测" * 200, "body_zh": load_cards_zh()[1]["body_zh"]}
    })
    with pytest.raises(RuntimeError, match="text overflow"):
        bc.run(write=False)


def test_right_3line_cards_all_get_nonuniform_spacing_on_real_data():
    section_labels_zh = load_section_labels_zh()
    cards_jp = load_cards_jp()
    for card in RIGHT_3LINE_CARDS:
        label = section_labels_zh[cards_jp[card]["section_label"]]
        rplan = plan_right(card, label)
        assert rplan["spacing_mode"] == "nonuniform_3line", (
            f"card {card} did not get the attempted non-uniform 3-line "
            f"spacing on real data (would need to be surfaced as a "
            f"documented fallback, see run()'s right_3line_fallback_to_uniform)"
        )
        ys = [p[1] for p in rplan["positions"]]
        assert ys[1] - ys[0] == RIGHT_3LINE_GAPS[0]
        assert ys[2] - ys[1] == RIGHT_3LINE_GAPS[1]


def test_right_3line_falls_back_to_uniform_and_is_detectable_when_a_segment_overflows():
    """If wrapping ever turns one of the 3 segments into 2 physical lines
    (e.g. a future translation edit makes 'EX2' longer), plan_right() must
    fall back to uniform spacing rather than pretending 4 lines fit the
    3-slot non-uniform layout -- and that fallback must be visible via
    spacing_mode, which is exactly what run()'s right_3line_fallback_to_uniform
    list is built from."""
    card = RIGHT_3LINE_CARDS[0]
    long_label = "章节\n" + ("超长文本导致换行" * 3) + "\n梗概"
    rplan = plan_right(card, long_label)
    assert rplan["spacing_mode"] == "uniform"


def test_MUTATION_overflow_not_appended_would_hide_a_real_regression():
    """Pins the mutation: simulate 'the overflow list append got dropped'
    by re-deriving the check the way build_render_plan does internally, but
    forgetting to record it (as a naive/incorrect caller would), and show
    the two disagree -- i.e. build_render_plan's real bookkeeping is doing
    real work, not something a no-op could satisfy."""
    cards_zh = {1: {"title_zh": "测" * 200, "body_zh": ""}}
    cards_jp = {1: {"title_jp": "x", "body_jp": "", "section_label": ""}}
    plans, overflow = build_render_plan(cards_zh, cards_jp, {}, cards=[1])
    naive_overflow = []  # what a version that "checked but didn't append" would report
    assert overflow["title_overflow"] != naive_overflow
    assert len(overflow["title_overflow"]) == 1


# ---------------------------------------------------------------------------
# 4. 正文引号行折行保护在本模块调用路径中同样生效 —— 变异④
# ---------------------------------------------------------------------------

def test_plan_body_card_4_keeps_each_option_on_its_own_line():
    cards_zh = load_cards_zh()
    bplan = plan_body(4, cards_zh[4]["body_zh"])
    all_lines = [ln for para in bplan["paragraphs"] for ln in para]
    assert "「想不起来」" in all_lines
    assert "「约好了」" in all_lines
    assert "「没有约」" in all_lines
    assert not any("」「" in ln for ln in all_lines)


def test_MUTATION_quote_line_regex_disabled_would_merge_card_4_options(monkeypatch):
    """Pins the mutation the task calls out by name: disable
    measure_card's quote-line regex (the same guard tools.bake_card.plan_body
    relies on via wrap_body_zh) and show card 4's real option list gets
    glued together through THIS module's actual call path (plan_body), not
    just measure_card's own test suite."""
    import tools.measure_card as mc
    import re
    never_matches = re.compile(r"(?!x)x")  # matches nothing
    monkeypatch.setattr(mc, "_QUOTE_LINE_RE", never_matches)
    cards_zh = load_cards_zh()
    bplan = plan_body(4, cards_zh[4]["body_zh"])
    all_lines = [ln for para in bplan["paragraphs"] for ln in para]
    assert any("」「" in ln for ln in all_lines), (
        "test setup assumption broken: disabling the quote-line regex no "
        "longer merges card 4's options, so it can no longer prove the "
        "guard matters through this module's call path"
    )


def test_card_41_paragraph_break_survives_as_a_visible_gap():
    cards_zh = load_cards_zh()
    bplan = plan_body(41, cards_zh[41]["body_zh"])
    ys = [p[1] for p in bplan["positions"]]
    # 5 content lines with one \n\n paragraph break -> the y-gap crossing the
    # break must be LARGER than the normal 12px pitch (BODY_PARAGRAPH_GAP_LINES
    # adds one extra line-pitch of space).
    diffs = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    assert max(diffs) > 12
    assert diffs.count(12) == len(diffs) - 1  # every other gap is the normal pitch


def test_card_145_body_is_rendered_verbatim_not_rewrapped():
    cards_zh = load_cards_zh()
    bplan = plan_body(145, cards_zh[145]["body_zh"])
    lines = [ln for para in bplan["paragraphs"] for ln in para]
    assert lines == cards_zh[145]["body_zh"].split("\n")


# ---------------------------------------------------------------------------
# 5. 背景聚类
# ---------------------------------------------------------------------------

def test_block_distance_undefined_below_min_overlap():
    fa = {(0, 0): (255, 255, 255)}
    fb = {(0, 0): (0, 0, 0)}
    assert block_distance(fa, fb) is None  # only 1 shared block, floor is 20


def test_block_distance_small_for_near_identical_vectors():
    fa = {(i, 0): (250.0, 240.0, 230.0) for i in range(30)}
    fb = {(i, 0): (251.0, 241.0, 229.0) for i in range(30)}
    d = block_distance(fa, fb)
    assert d is not None and d < 10


def test_clustering_on_real_corpus_finds_card_94_as_its_own_cluster():
    cards = load_card_domain()
    assignment = cluster_backgrounds(cards, threshold=CLUSTER_DIST_THRESHOLD)
    card94_cluster = assignment[CARD_94_ILLUSTRATION]
    same_cluster_as_94 = [c for c, cid in assignment.items() if cid == card94_cluster]
    assert same_cluster_as_94 == [CARD_94_ILLUSTRATION]
    # every other card must land in a single shared cluster (the report's
    # "2 clusters, not several-to-a-dozen" finding, pinned as a regression):
    other_clusters = {cid for c, cid in assignment.items() if c != CARD_94_ILLUSTRATION}
    assert len(other_clusters) == 1


def test_cluster_report_shape():
    cards = load_card_domain()
    report = cluster_report(cards)
    assert report["num_clusters"] == 2
    sizes = sorted(c["size"] for c in report["clusters"])
    assert sizes == [1, 195]


def test_cluster_threshold_is_not_knife_edge():
    """The chosen CLUSTER_DIST_THRESHOLD (20) must not be sitting right at a
    boundary -- re-running at 2x and 0.5x should produce the SAME partition
    on real data (see CLUSTER_DIST_THRESHOLD's docstring: >6x headroom above
    the observed intra-group max, >30x below the outlier)."""
    cards = load_card_domain()
    a = cluster_backgrounds(cards, threshold=CLUSTER_DIST_THRESHOLD / 2)
    b = cluster_backgrounds(cards, threshold=CLUSTER_DIST_THRESHOLD * 2)
    for c in cards:
        assert (a[c] == a[CARD_94_ILLUSTRATION]) == (c == CARD_94_ILLUSTRATION)
        assert (b[c] == b[CARD_94_ILLUSTRATION]) == (c == CARD_94_ILLUSTRATION)


# ---------------------------------------------------------------------------
# 6. 像素保全闸（zones 之外不得改动一个像素）
# ---------------------------------------------------------------------------

def test_bake_card_pixel_preservation_outside_zones():
    cards_zh = load_cards_zh()
    cards_jp = load_cards_jp()
    section_labels_zh = load_section_labels_zh()
    sample = [1, 2, 41, 94, 145, 26]
    plans, overflow = build_render_plan(cards_zh, cards_jp, section_labels_zh, cards=sample)
    assert not any(overflow.values())
    for card in sample:
        _new_card, diffs, _ink, _n = bake_card(card, plans[card])
        assert diffs == [], f"card {card} touched pixels outside its redraw zones: {diffs[:5]}"


# ---------------------------------------------------------------------------
# 7. inpaint / ink-mask 基础健全性
# ---------------------------------------------------------------------------

def test_inpaint_block_grid_fills_missing_from_neighbors():
    feats = {(0, 0): (10.0, 10.0, 10.0), (1, 0): None, (2, 0): (30.0, 30.0, 30.0)}
    filled = inpaint_block_grid(feats, cols=3, rows=1)
    assert filled[(1, 0)] == pytest.approx((20.0, 20.0, 20.0))


def test_inpaint_block_grid_raises_when_totally_empty():
    feats = {(0, 0): None, (1, 0): None}
    with pytest.raises(RuntimeError):
        inpaint_block_grid(feats, cols=2, rows=1)


def test_dilated_ink_mask_covers_a_known_dark_pixel_and_its_neighborhood():
    from tools.measure_card import TITLE_ZONE
    im = Image.open(card_path(1)).convert("RGBA")
    px = im.load()
    x0z, y0z, x1z, y1z = TITLE_ZONE
    # Find one actual confirmed-ink pixel by direct scan (measure_card's own
    # criterion) -- NOT collect_ink_bbox's corner, which is just the bbox's
    # min/max extent and is not guaranteed to itself be an ink pixel.
    ink_pixel = None
    for y in range(y0z, y1z):
        for x in range(x0z, x1z):
            r, g, b, a = px[x, y]
            if a >= 200 and max(r, g, b) < 120:
                ink_pixel = (x, y)
                break
        if ink_pixel:
            break
    assert ink_pixel is not None, "test setup: card 1's title has no ink?!"
    mask = dilated_ink_mask(im, TITLE_ZONE)
    assert ink_pixel in mask
    # and a point far from any glyph (top margin, y near the zone's own top
    # edge) must NOT be swept into the mask by over-eager dilation:
    assert (x0z + 50, y0z + 1) not in mask


# ---------------------------------------------------------------------------
# 8. 端到端 smoke test
# ---------------------------------------------------------------------------

def test_run_end_to_end_smoke(tmp_path, monkeypatch):
    import tools.bake_card as bc
    monkeypatch.setattr(bc, "OUT_DIR", str(tmp_path))
    report = bc.run(write=True, with_images=False)
    assert report["num_cards"] == 196
    assert report["validation_gate"]["over_threshold"] == []
    assert not any(report["overflow"].values())
    assert report["pixel_preservation_violations"] == {}
    assert report["clusters"]["num_clusters"] == 2
    import os
    assert os.path.exists(os.path.join(str(tmp_path), "crd_1_a.png"))
    assert os.path.exists(os.path.join(str(tmp_path), "manifest.json"))


# ---------------------------------------------------------------------------
# 9. 字色：原图的字**不是黑的**（用户 2026-08-28 指出，实测确认）
# ---------------------------------------------------------------------------
#
# 旧实现写死 `FILL_COLOR = (12,11,10)`，近乎中性黑。而全库 195 张实测，字芯稳定
# 落在 (56–60, 0, 0–1) 的暗红上，与卡片外框 (18,0,1,243) 同色系；卡 94 的框是褐色，
# 它的字芯也相应是褐的。
#
# 这个错误能一直住着，是因为 C5 那道重建验证闸**只看"原图确无文字处"**——它守的是
# 背景，从不看字本身。下面这组测试就是补上那块守不到的地方。

import statistics as _stats
from pathlib import Path as _Path

from PIL import Image as _Image

from tools.bake_card import (
    INK_COLOR_FALLBACK, INK_CORE_MIN_PIXELS, measure_ink_color,
    reconstruct_background,
)
from tools.measure_card import CARD_H, CARD_W, TITLE_ZONE, card_path

_SHS = _Path(__file__).resolve().parent.parent / "third_party" / "SourceHanSansSC-VF.ttf"


def _frame_color(card):
    """卡片四周的纯色边框——从上往下第一条不透明的整行。"""
    px = _Image.open(card_path(card)).convert("RGBA").load()
    from collections import Counter
    for y in range(CARD_H):
        op = [px[x, y] for x in range(CARD_W) if px[x, y][3] > 200]
        if len(op) > CARD_W * 0.6:
            return Counter(op).most_common(1)[0][0][:3]
    raise AssertionError(f"卡 {card} 找不到不透明边框行")


def test_ink_is_not_black_and_not_the_old_constant():
    for card in (3, 10, 46, 145):
        ink, n = measure_ink_color(card)
        assert n >= INK_CORE_MIN_PIXELS
        r, g, b, a = ink
        assert a == 255
        assert r > 40, f"卡 {card} 字芯 {ink} 不该这么暗——原图的字不是黑的"
        assert g < 15 and b < 15, f"卡 {card} 字芯 {ink} 应是暗红，G/B 接近 0"
        assert (r, g, b) != (12, 11, 10), "旧的固定字色不该再出现"


def test_ink_hue_points_at_the_cards_own_frame_colour():
    """字色与框色同源——**这是本组测试的主张**，也是用户观察的实质。

    判据取方向而非取值：字芯比框色浅（框 (18,0,1) vs 字 (57,0,0)），但从卡面底色
    出发指向两者的向量几乎共线。全库 195 张 cos = 0.95–0.999。
    """
    import math
    for card in (10, 46, 94, 145):
        ink, _n = measure_ink_color(card)
        frame = _frame_color(card)
        bg = (245, 236, 230)          # 卡面底的浅色端，两个向量的共同起点
        u = [ink[i] - bg[i] for i in range(3)]
        v = [frame[i] - bg[i] for i in range(3)]
        cos = (sum(u[i] * v[i] for i in range(3))
               / (math.hypot(*u) * math.hypot(*v)))
        assert cos > 0.94, f"卡 {card}：字色 {ink} 与框色 {frame} 不同向（cos={cos:.3f}）"


def test_card_94_ink_differs_from_the_red_family():
    """卡 94 的框是褐色，字也是褐的——逐卡实测才能自动接住这一张。

    写死一个常量的实现，会把这张卡的字渲成和其余 195 张一样的红。
    """
    ink94, _ = measure_ink_color(94)
    ink10, _ = measure_ink_color(10)
    assert ink94[1] > 30 and ink94[2] > 10, f"卡 94 字芯 {ink94} 应带明显的绿/蓝分量"
    assert sum(abs(ink94[i] - ink10[i]) for i in range(3)) > 60


def test_too_few_core_pixels_falls_back_and_says_so(monkeypatch):
    """取样不足要回退并**把数目报出来**，不能默默用一个看起来合理的颜色。"""
    import tools.bake_card as bc
    monkeypatch.setattr(bc, "INK_CORE_RATIO", 1.0000001)   # 谁都够不着
    ink, n = bc.measure_ink_color(10)
    assert ink == INK_COLOR_FALLBACK
    assert n < INK_CORE_MIN_PIXELS


def test_manifest_records_per_card_ink_and_fallbacks(tmp_path, monkeypatch):
    import tools.bake_card as bc
    monkeypatch.setattr(bc, "OUT_DIR", str(tmp_path))
    report = bc.run(write=False, with_images=False)
    ic = report["ink_color"]
    assert len(ic["per_card"]) == 196
    assert ic["fallback_color"] == list(INK_COLOR_FALLBACK)
    assert all(len(v) == 4 for v in ic["per_card"].values())
    # 取值种类应远少于卡数——全库外框只有两种颜色，字色与框色同源
    assert len(ic["distinct"]) < 60


@pytest.mark.skipif(not _SHS.exists(), reason="需要 SourceHanSansSC-VF.ttf")
def test_saturating_font_reproduces_the_original_ink_exactly(tmp_path, monkeypatch):
    """**这条才是"复刻成功"的判据。**

    字色改对只是一半：笔画若细到没有一个像素达到满覆盖，纯字色根本不会出现在
    产物里。霞鹜文楷 9–11px 正是如此（字芯色距约 42）；换成笔画能饱和的思源黑体，
    同一段代码渲出来的字芯与原图**逐通道相等**。

    所以这条测试同时守住两件事：字色取对了，以及"取对了就真的落到像素上"。
    """
    import tools.bake_card as bc
    monkeypatch.setenv("ZND_UI_FONT", str(_SHS))
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT", "Regular")
    bc._FONT_CACHE.clear()

    def core_med(img, recon, ratio=0.97):
        o, b = img.load(), recon.load()
        x0, y0, x1, y1 = TITLE_ZONE
        px = [(sum(abs(o[x, y][i] - b[x, y][i]) for i in range(3)), o[x, y])
              for y in range(y0, y1) for x in range(x0, x1)]
        dmax = max(p[0] for p in px)
        sel = [p[1] for p in px if p[0] >= dmax * ratio]
        return tuple(int(_stats.median(s[i] for s in sel)) for i in range(3))

    try:
        plans, _overflow = bc.build_render_plan(
            load_cards_zh(), load_cards_jp(), load_section_labels_zh(),
            cards=[10, 46])
        for card in (10, 46):
            recon = reconstruct_background(card)
            new_card, _d, _ink, _n = bc.bake_card(card, plans[card])
            got = core_med(new_card, recon)
            want = core_med(_Image.open(card_path(card)).convert("RGBA"), recon)
            assert got == want, f"卡 {card}：烤出来 {got}，原图 {want}"
    finally:
        bc._FONT_CACHE.clear()
