"""`tools/bake_plot_plate.py` —— `png/plot/` 缩略图的「干净底板」烤字（方案 B）。

原缩略图 = 0.5 × 游戏画面（bg / event CG / bg+立绘）→ BILINEAR 缩到 82×48 → 全表 256 色板
（`docs/ops/plot-plate-research-2026-09-07.md`）。本工具按 `data/plot_plates.jsonl` 里逐卡冻结的配方
重建每格的底板，**对照原格无字行算 RMSE 过闸**，再把中文标题烤上去；配方写 `band` 的格走
`tools/bake_plot.py` 的色带路径兜底。下面每条断言要么是数据契约，要么在真素材上量。
"""

from pathlib import Path

import pytest
from PIL import Image, ImageChops

from tools import bake_plot as bp
from tools import bake_plot_plate as bpp

ROWS = bpp.load_plates()
KINDS = ("single", "compose", "flat", "band")


def _orig_cell(card):
    s, box = bp.cell_box(card)
    return Image.open(bp.PLOT_DIR + f"/plot_{s}_a.png").convert("RGB").crop(box)


def _maxdiff(a, b):
    return max(hi for _lo, hi in ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getextrema())


# ── 数据契约 ────────────────────────────────────────────────────────────

def test_plates_cover_every_card_exactly_once_with_a_known_kind():
    assert sorted(ROWS) == list(range(1, bp.NUM_CARDS + 1))
    assert all(r["kind"] in KINDS for r in ROWS.values())
    assert all(r.get("tone", 0.5) == 0.5 for r in ROWS.values() if r["kind"] in ("single", "compose"))


def test_every_layer_in_the_plates_points_at_an_existing_asset():
    for card, r in ROWS.items():
        for layer in r.get("layers", []):
            assert layer["kind"] in ("bg", "event", "pose", "solid", "effect", "cutin", "sysgim"), (card, layer)
            if layer["kind"] != "solid":
                assert (Path("png") / layer["kind"] / f"{layer['name']}.png").exists(), (card, layer)


def test_single_and_compose_rows_carry_a_verified_rmse_under_the_gate():
    """配方表里记的 `verify_rmse` 是生成时量的；进闸时工具会重量（见下），这里钉住数据本身。"""
    for card, r in ROWS.items():
        if r["kind"] in ("single", "compose"):
            assert 0 <= r["verify_rmse"] <= bpp.GATE_RMSE, (card, r["verify_rmse"])


# ── 底板重建与闸 ────────────────────────────────────────────────────────

def test_single_plate_is_half_of_the_bilinear_thumbnail():
    """`single` 配方＝源图 BILINEAR 缩到 82×48 再 ×0.5，逐像素可复算。"""
    card = next(c for c, r in ROWS.items() if r["kind"] == "single")
    r = ROWS[card]
    src = Image.open(f"png/{r['layers'][0]['kind']}/{r['layers'][0]['name']}.png").convert("RGBA")
    base = Image.new("RGBA", (480, 272), (0, 0, 0, 255))     # 引擎清屏色是黑，素材带 alpha 时压在黑上
    base.alpha_composite(src)
    expect = base.convert("RGB").resize((82, 48), Image.BILINEAR).point([int(round(v * 0.5)) for v in range(256)] * 3)
    assert _maxdiff(bpp.build_plate(r), expect) <= 1


def test_verify_rejects_a_wrong_recipe_and_accepts_the_real_one():
    """闸是对照**原格**量的，不信配方表的自述：把卡 7 的配方换成别的教室 bg 必须被拒。"""
    r = ROWS[7]
    assert r["kind"] == "compose"
    assert bpp.verify_plate(bpp.build_plate(r), _orig_cell(7), 7) <= bpp.GATE_RMSE
    wrong = dict(r, layers=[{"layer": "bg1", "kind": "bg", "name": "bg_5_a_0", "x": 0, "y": 0}])
    assert bpp.verify_plate(bpp.build_plate(wrong), _orig_cell(7), 7) > bpp.GATE_RMSE


def test_real_plates_all_pass_the_gate_when_remeasured():
    """195 张全部重量一遍：single/compose 不超过 GATE。这是本文件的主张。"""
    bad = []
    for card, r in ROWS.items():
        if r["kind"] not in ("single", "compose"):
            continue
        rm = bpp.verify_plate(bpp.build_plate(r), _orig_cell(card), card)
        if rm > bpp.GATE_RMSE:
            bad.append((card, round(rm, 1)))
    assert bad == [], bad


def test_flat_plate_is_black_on_top_and_matches_the_measured_bottom_glow():
    """纯黑底板：上 24 行全黑；下 24 行取所有 flat 格的中位数（原图实测 y45–47 有淡光）。"""
    plate = bpp.flat_plate()
    assert max(hi for _lo, hi in plate.crop((0, 0, 82, 24)).getextrema()) == 0
    flat_cards = [c for c, r in ROWS.items() if r["kind"] == "flat" and not r.get("black")]
    assert len(flat_cards) >= 30
    far = [c for c in flat_cards if bpp.rmse_rows(plate, _orig_cell(c), 26) > 3.0]
    assert len(far) <= len(flat_cards) // 10, far
    # 开场黑屏的格另走纯黑变体，底板整格为 0
    for c, r in ROWS.items():
        if r["kind"] == "flat" and r.get("black"):
            assert max(hi for _lo, hi in bpp.build_plate(r).getextrema()) == 0, c


# ── 成品 ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def product(tmp_path_factory):
    out = tmp_path_factory.mktemp("plot_plate")
    report = bpp.run(write=True, out_dir=str(out))
    return out, report


def test_run_writes_four_sheets_and_a_manifest(product):
    out, report = product
    for s in range(1, 5):
        assert (out / f"plot_{s}_a.png").exists()
    assert (out / "manifest.json").exists()
    assert report["num_cards"] == bp.NUM_CARDS
    assert sorted(int(k) for k in report["per_card"]) == list(range(1, bp.NUM_CARDS + 1))


def test_blank_tail_cells_are_byte_identical(product):
    out, _ = product
    orig = Image.open(bp.PLOT_DIR + "/plot_4_a.png").convert("RGBA")
    baked = Image.open(out / "plot_4_a.png").convert("RGBA")
    for box in ((246, 96, 492, 144), (0, 144, 492, 480)):     # 卡 195 之后的 45 个空格
        assert orig.crop(box).tobytes() == baked.crop(box).tobytes(), box


def test_band_fallback_equals_the_band_tool_output():
    """`band` 兜底格逐像素等于 `bake_plot` 自己烤出来的那格——两条路径不许各烤各的。
    配方表里现在没有 band 格，这里把卡 7 强制成 band 来钉住这条路径（含 P5 的行数规则）。"""
    font = bp._ui_truetype("plot", bp.FONT_SIZE)
    titles = bp.load_titles_zh()
    jp = bpp.load_titles_jp()
    c = 7
    orig = bpp.orig_cell(c)
    cell, info = bpp.bake_card(c, {"card": c, "kind": "band"}, orig, titles[c], font, jp[c])
    lines, _ = bp.wrap_title(titles[c], font)
    expect, decision = bp.bake_cell(orig.convert("RGBA"), lines, font, jp_title=jp[c])
    assert cell.convert("RGBA").tobytes() == expect.convert("RGBA").tobytes()
    assert info["kind"] == "band" and info["line_rule"] == decision.line_rule == "override"


def test_titles_are_rendered_exactly_like_the_band_tool(product):
    """中文标题的字形/字号/落点与色带工具相同：文字层 alpha=0 处成品＝底板，alpha=255 处成品＝文字色。"""
    out, _ = product
    font = bp._ui_truetype("plot", bp.FONT_SIZE)
    titles = bp.load_titles_zh()
    card = next(c for c, r in ROWS.items() if r["kind"] == "single")
    s, box = bp.cell_box(card)
    got = list(Image.open(out / f"plot_{s}_a.png").convert("RGB").crop(box).getdata())
    plate = list(bpp.build_plate(ROWS[card]).getdata())
    lines, _ = bp.wrap_title(titles[card], font)
    text = bp.render_text_layer((82, 48), lines, font)
    alpha = list(text.getchannel("A").getdata())
    rgb = list(text.convert("RGB").getdata())
    assert any(a == 255 for a in alpha)
    for g, p, a, t in zip(got, plate, alpha, rgb):
        if a == 0:
            assert max(abs(g[i] - p[i]) for i in range(3)) <= 1
        elif a == 255:
            assert max(abs(g[i] - t[i]) for i in range(3)) <= 1


def test_manifest_reports_review_band_and_gate_per_card(product):
    _, report = product
    per = report["per_card"]
    assert {r["kind"] for r in per.values()} <= set(KINDS)
    for r in per.values():
        if r["kind"] in ("single", "compose"):
            assert r["rmse"] <= bpp.GATE_RMSE
            if r["rmse"] > bpp.REVIEW_RMSE:
                assert r["review"] and r["review_reason"] == "rmse"
    assert "review_cards" in report and "band_cards" in report and report["gate_failures"] == []


# ── 裁切框（2026-09-07 猎手：卡 56/82 的走廊格是整帧 1.035× 居中放大）────────

def test_crop_box_is_applied_before_the_thumbnail_resize():
    """`crop: [x0, y0, x1, y1]`（可含小数）＝先裁再缩：等价于 PIL resize 的 box= 参数。"""
    row = {"kind": "single", "layers": [{"layer": "bg1", "kind": "bg", "name": "bg_4_b_0", "x": 0, "y": 0}], "tone": 0.5}
    plain = bpp.build_plate(row)
    cropped = bpp.build_plate(dict(row, crop=[7.0, 3.5, 472.0, 266.5]))
    assert _maxdiff(plain, cropped) > 4          # 裁切确实改变了底板
    src = bpp.compose_layers(row["layers"])
    expect = src.resize((82, 48), Image.BILINEAR, box=(7.0, 3.5, 472.0, 266.5)).point([int(round(v * 0.5)) for v in range(256)] * 3)
    assert _maxdiff(cropped, expect) <= 1


def test_card_56_and_82_use_the_same_zoomed_hallway_plate():
    """两张「走廊」格是同一块底板：同 bg、同裁切框，重量后都在 REVIEW 线之下。"""
    for c in (56, 82):
        r = ROWS[c]
        assert r["kind"] in ("single", "compose") and r.get("crop"), c
        assert bpp.verify_plate(bpp.build_plate(r), _orig_cell(c), c) <= bpp.REVIEW_RMSE, c


def test_localised_foreign_object_flags_review_even_when_global_rmse_is_low():
    """测量审计的建议：整格 RMSE 低不代表没问题——底板某 3 行带里若与原格差 >20（局部异物/错位），
    也要进复核名单。用卡 7 的底板在无字行贴一块亮斑来触发。"""
    r = ROWS[7]
    plate = bpp.build_plate(r)
    assert bpp.local_band_rmse(plate, _orig_cell(7), 7) < 20
    spoiled = plate.copy()
    spoiled.paste((255, 255, 255), (30, 40, 60, 43))
    assert bpp.local_band_rmse(spoiled, _orig_cell(7), 7) > 20
    font = bp._ui_truetype("plot", bp.FONT_SIZE)
    titles = bp.load_titles_zh(); jp = bpp.load_titles_jp()
    _cell, info = bpp.bake_card(7, r, _orig_cell(7), titles[7], font, jp[7])
    assert info["review"] is False and info.get("review_reason") is None


# ── 宽掩膜（2026-09-07 测量审计建议）────────────────────────────────────
#
# 窄掩膜只看无字行，而**我们替换掉的正是标题那片区域**——那里对不对，窄掩膜一个字都没测。
# 宽掩膜＝原格里所有「不是标题墨迹」的像素（墨迹＝近白且 2px 内有近黑，再膨胀 2px），
# 包含字间空隙、行间空隙与顶部空行，于是标题区的底也被量到。

def test_ink_mask_covers_the_title_and_leaves_the_picture():
    """墨迹掩膜必须罩住标题、且不吞掉画面：两行标题格的墨迹应集中在 y<26 且占比不过半。"""
    m = bpp.ink_mask(_orig_cell(7))
    n = sum(sum(1 for v in row if v) for row in m)
    assert 0 < n < 82 * 48 * 0.5
    below = sum(1 for y in range(26, 48) for x in range(82) if m[y][x])
    assert below <= n * 0.05, below


def test_wide_rmse_sees_errors_hidden_under_the_title():
    """在标题区凿一块坏底板：窄掩膜纹丝不动，宽掩膜必须炸。"""
    r = ROWS[7]
    plate = bpp.build_plate(r)
    spoiled = plate.copy()
    spoiled.paste((255, 0, 255), (0, 0, 82, 24))       # 整个标题区改成品红
    orig = _orig_cell(7)
    assert bpp.verify_plate(spoiled, orig, 7) == bpp.verify_plate(plate, orig, 7)
    assert bpp.wide_rmse(spoiled, orig, 7) > 3 * bpp.wide_rmse(plate, orig, 7)


def test_manifest_carries_wide_rmse_and_flags_the_divergent_cells():
    """每格都记宽掩膜 RMSE；宽掩膜超线、或宽比窄大 3 以上，都算复核（审计建议的两条）。"""
    report = bpp.run(write=False)
    per = report["per_card"]
    for c, i in per.items():
        if i["kind"] not in ("single", "compose"):
            continue
        assert i["wide_rmse"] is not None
        expect = (i["rmse"] > bpp.REVIEW_RMSE or i["wide_rmse"] > bpp.REVIEW_RMSE
                  or i["wide_rmse"] - i["rmse"] > bpp.WIDE_GAP or i["local_band_rmse"] > bpp.LOCAL_BAND_RMSE)
        assert i["review"] == expect, (c, i)


# ── 人工接受（2026-09-07 用户裁定）────────────────────────────────────
#
# 复核清单是机械判据的产物，人看过并接受之后，它不该每次再报同一批格——否则清单久了没人看，
# 真正**新**冒出来的偏差就淹在里面。故把「已接受」写进数据行，manifest 分两栏：
# review_cards（机械命中，仍然照报）与 review_unaccepted（需要人看的，应为空）。

def test_accepted_cells_are_recorded_in_the_data_not_only_in_prose():
    accepted = {c for c, r in ROWS.items() if r.get("accepted")}
    flagged = {c for c, r in ROWS.items()
               if r["kind"] in ("single", "compose")
               and (r["verify_rmse"] > bpp.REVIEW_RMSE or (r.get("wide_rmse") or 0) > bpp.REVIEW_RMSE)}
    assert accepted, "配方表里没有任何 accepted 行"
    assert accepted <= set(ROWS)
    for c in accepted:
        assert ROWS[c].get("accepted_note"), c        # 接受要写清楚是谁在什么前提下接受的
    assert flagged <= accepted, sorted(flagged - accepted)


def test_manifest_separates_mechanical_flags_from_unaccepted_ones():
    report = bpp.run(write=False)
    per = report["per_card"]
    flagged = {int(c) for c, i in per.items() if i.get("review")}
    assert report["review_cards"] == sorted(flagged)
    assert report["review_unaccepted"] == sorted(
        c for c in flagged if not ROWS[c].get("accepted"))
    assert report["review_unaccepted"] == [], report["review_unaccepted"]
    for c in flagged:
        assert per[str(c)]["accepted"] is bool(ROWS[c].get("accepted"))
