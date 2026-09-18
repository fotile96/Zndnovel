"""tools/bake_select.py — png/select/ 250x26 选项按钮（134 个按钮 = 268 张
_on/_off 真实文件）烤字回填。

覆盖硬约束闸（见 tools/bake_select.py 模块 docstring 与
.superpowers/sdd/2026-08-07-p4-polish-pass/bake-select-report.md）：
  1. 覆盖率必须每次独立重算，不信任任何缓存（build/_select_coverage.json
     是上一轮快照，本模块完全不读它）；134/134 缺一不可，且中文源缺失时
     必须报错停下，不能静默跳过该按钮。
  2. 字号级联的"零溢出"判据必须是真实渲染墨迹（含描边），不能只是字符数
     估算——TEXT_BOX 相对文本长度的余量比 scene/ 紧得多，纯字符数估算精度
     不够。
  3. TEXT_BOX 之外的像素必须逐字节保真（边框环、四角缺口、共享透明图标
     缺口都在这个区域内，off/on 两态分别验证）。
  4. 静默截断/静默回落/静默跳过三类失败模式必须都有对应的会变红的测试。
"""
import json
import sys

import pytest
from PIL import Image, ImageDraw, ImageFont

from tools.bake_select import (
    CELL_H, CELL_W, CELLZOOM_BUTTONS, FILL_BY_VARIANT, FONT_SIZE_CASCADE,
    MAX_TEXT_W, SELECT_DIR, STROKE_BY_VARIANT, TEXT_FILL_COLOR, TEXT_BOX,
    bake_button, build_cellzoom_image, build_compare_image,
    build_render_plan, build_size_ab_image, compute_coverage,
    find_outside_box_diffs, load_fonts, measure_ink_colors, measure_ink_extent,
    real_button_bases, render_text_layer, resolve_fonts_by_button, run,
)

FONT_PATH = "third_party/LXGWWenKai-Regular.ttf"


from tools.ui_font import truetype as _ui_truetype


def _font(size):
    # **必须走 ui_font.truetype，不能裸调 ImageFont.truetype。** FONT_PATH 现在可能
    # 指向变量字体，裸调拿到的是它的默认实例（思源黑体是 ExtraLight＝权重轴最小值），
    # 于是测试量的字重和工具烤的根本不是同一档——而且不报错、不缺字，只是更细一点。
    return _ui_truetype("select", size)


def _button_path(button, variant):
    import os
    return os.path.join(SELECT_DIR, f"{button}_{variant}.png")


# ---------------------------------------------------------------------------
# 1. 资产几何：134 个按钮、3px 边框、共享透明图标缺口 —— 直接对真实素材实测
# ---------------------------------------------------------------------------

def test_real_button_bases_count_is_134():
    bases = real_button_bases()
    assert len(bases) == 134


def test_real_button_bases_every_base_has_both_variants():
    bases = real_button_bases()
    import os
    for b in sorted(bases):
        assert os.path.exists(_button_path(b, "off")), b
        assert os.path.exists(_button_path(b, "on")), b


def test_border_frame_is_3px_all_sides_real_asset():
    """真实素材实测：边框环覆盖整条边（不只是 1px 发丝线），四边一致，
    与 tools.select_layout.BORDER_FRAME=3 的既有测绘结论互相印证。"""
    img = Image.open(_button_path("sel_s1s_35_sel_a", "off")).convert("RGBA")
    px = img.load()
    w, h = img.size
    fill = FILL_BY_VARIANT["off"]
    # row 2 (0-based) at a mid column must still be border, not fill;
    # row 3 at the same column must be fill.
    assert px[125, 2] != fill
    assert px[125, 3] == fill
    assert px[2, 12] != fill
    assert px[3, 12] == fill
    assert px[247, 12] != fill
    assert px[246, 12] == fill
    assert px[125, 23] != fill
    assert px[125, 22] == fill


def test_shared_icon_notch_is_transparent_and_outside_text_box():
    """左侧共享透明缺口 x∈[5,10],y∈[5,6] 完全落在 TEXT_BOX 之外
    （TEXT_BOX[0]=15），所以不需要任何特判代码就能被像素保全闸保护。"""
    assert TEXT_BOX[0] == 15
    for variant in ("off", "on"):
        img = Image.open(_button_path("sel_s1s_35_sel_a", variant)).convert("RGBA")
        px = img.load()
        for x in range(5, 11):
            for y in (5, 6):
                assert x < TEXT_BOX[0]
                assert px[x, y][3] == 0, (variant, x, y)


# ---------------------------------------------------------------------------
# 2. 覆盖率：每次独立重算，134/134，且能抓出各类缺失/冲突
# ---------------------------------------------------------------------------

def test_compute_coverage_is_134_of_134_today():
    covered, missing, evidence = compute_coverage()
    assert missing == []
    assert len(covered) == 134
    assert evidence["total_buttons"] == 134


def test_compute_coverage_layer_breakdown_matches_known_survey_numbers():
    """回归钉子：92 条按钮级 + 61 条选项级（69 按钮，且与 92 条完全重叠）+
    42 条走推导层——这是本轮任务交办文档记载的既有事实，用测试钉住，
    避免未来数据文件改动时这个"134/134"结论在无人察觉的情况下漂移。"""
    covered, missing, evidence = compute_coverage()
    # 93：sel_s1s_260_sel_a 补进 select_buttons_zh.jsonl —— 它此前没有
    # 人工校订行，烤图直接沿用了带片假名的「サクラ同学」，违反 v19 C1 罗马音化。
    # 94（2026-09-19）：sel_s4s_170_sel_a 补人工行 —— 派生层把下一分支场景
    # 标题「選択：メモの内容」当成了按钮文字（原图「興味を惹かれた」）。
    assert evidence["src1_distinct_buttons"] == 94
    assert evidence["src2_distinct_buttons"] == 69
    assert evidence["src1_src2_overlap"] == 69  # src2 ⊆ src1 today
    # 40：sel_s1s_260_sel_a、sel_s4s_170_sel_a 先后从派生层升格为 src1 人工校订行
    assert evidence["remaining_after_src1_src2"] == 40
    assert evidence["resolved_via_derived_layer"] == 40
    # 有了人工行后它不再进派生层，守门自然也不再报它
    assert evidence["derived_rejected_scene_title"] == []
    assert missing == []


def test_compute_coverage_raises_when_a_button_has_no_source_at_all(tmp_path, monkeypatch):
    """变异回归形态之一：如果三层来源都覆盖不到某个真实按钮，
    compute_coverage 必须把它报进 missing，不能悄悄漏掉。用一个精简的假
    button 全集（真实全集 + 1 个不存在于任何数据源的假按钮名）验证。"""
    import tools.bake_select as bs

    real_bases = real_button_bases()

    def fake_bases():
        return real_bases | {"sel_totally_fake_button_sel_z"}

    monkeypatch.setattr(bs, "real_button_bases", fake_bases)
    covered, missing, evidence = bs.compute_coverage()
    assert "sel_totally_fake_button_sel_z" in missing


def test_derived_layer_rejects_scene_title_shaped_jp(tmp_path, monkeypatch):
    """派生层守门：derive_select.py 顺着空过渡臂追到下一个场景的
    `scene_X(id, "選択：…")`，会把**场景标题**当成按钮文字交上来；墨迹宽度
    校验对"字数相近"的串拦不住（实案 sel_s4s_170_sel_a：原图「興味を惹かれた」
    7 字，派生「選択：メモの内容」8 字，偏差 0.126 判 match，再经 extra
    查表命中卡 159 标题，整条链无一环报警，烤进盘里的是下一分支的名字）。
    按钮文字不可能以「選択：」「探索：」开头，这种派生结果必须落 missing，
    不能被静默采用。"""
    import tools.bake_select as bs

    ink = json.load(open(bs.BUILD_INK_VERIFY, encoding="utf-8"))
    victim = "sel_s4s_290_sel_b"   # 今天走派生层、且 status==match 的真实按钮
    hit = [r for r in ink["results"] if r["button"] == victim]
    assert hit and hit[0]["status"] == "match"
    # 把它的派生原文改成一个真实存在 exact 译文的场景标题（卡 159）
    hit[0]["jp"] = "選択：メモの内容"
    bad_path = tmp_path / "ink_verify_scene_title.json"
    bad_path.write_text(json.dumps(ink, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bs, "BUILD_INK_VERIFY", str(bad_path))

    covered, missing, evidence = bs.compute_coverage()
    assert victim in missing
    assert victim not in covered
    assert victim in evidence["derived_rejected_scene_title"]


def test_run_refuses_to_bake_when_coverage_incomplete(tmp_path, monkeypatch):
    """核心闸：missing 非空时 run() 必须整体拒绝渲染（不是渲染 133 个、
    跳过 1 个）——这是"中文源缺失时静默跳过该按钮"这一类禁止模式的直接
    回归。"""
    import tools.bake_select as bs

    def fake_compute_coverage():
        covered, missing, evidence = compute_coverage()
        # 假装真的缺了一个
        fake_missing = missing + ["sel_totally_fake_missing"]
        return covered, fake_missing, evidence

    monkeypatch.setattr(bs, "compute_coverage", fake_compute_coverage)
    monkeypatch.setattr(bs, "OUT_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="WITHOUT a zh source"):
        bs.run(write=True)
    assert list(tmp_path.iterdir()) == []


def test_compute_coverage_raises_on_src1_src2_conflict(tmp_path, monkeypatch):
    """src1/src2 对同一按钮给出不同译文时必须报错，不能悄悄选一个——这类
    分歧意味着两份数据源之间已经不同步，需要人工核对，不该被自动吞掉。"""
    import tools.bake_select as bs

    real_src1 = bs._load_jsonl(bs.DATA_BUTTONS_ZH)
    conflicting = list(real_src1)
    # 找一个真实存在于 src2 的按钮，塞一条"同按钮不同译文"的伪造行
    src2_rows = bs._load_jsonl(bs.DATA_OPTIONS_ZH)
    target_button = src2_rows[0]["buttons"][0]
    conflicting.append({"button": target_button, "jp": "__fake_jp__",
                         "zh": "__fake_conflicting_zh__", "source": "test"})

    bad_path = tmp_path / "buttons_zh_conflict.jsonl"
    with open(bad_path, "w", encoding="utf-8") as f:
        for r in conflicting:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    monkeypatch.setattr(bs, "DATA_BUTTONS_ZH", str(bad_path))
    with pytest.raises(ValueError, match="disagree"):
        bs.compute_coverage()


# ---------------------------------------------------------------------------
# 3. 字号级联：真实渲染墨迹判据（不是字符数估算），134/134 零溢出于最小档
# ---------------------------------------------------------------------------

def test_build_render_plan_real_texts_zero_hard_failures_and_known_fallback_set():
    covered, missing, _ev = compute_coverage()
    assert missing == []
    texts = {b: covered[b]["zh"] for b in covered}
    fonts_by_size = load_fonts()
    plans, fallbacks, hard_failures = build_render_plan(texts, fonts_by_size)
    assert hard_failures == []
    assert len(plans) == 134
    fb_buttons = sorted(b for b, _s, _t in fallbacks)
    # 回落集三次变化，每次都是**输入变了而判据没变**：
    #   20 → 14  glossary v19 C1 罗马音化，s6s_110 六条从全角片假名变半角拉丁，变窄
    #   14 →  2  居中改为按**真实墨迹**（原先 anchor="mm" 按字体设计度量，把整段
    #            墨迹压低，134 条里一大批越的是"定位的界"而非"字的界"）
    #      →  2  默认字体改思源黑体 Medium；同一份级联下反而比霞鹜文楷更省
    # 8：见下方 real_fallbacks 处的说明（s6s_110 六项补点号后降一档字号）
    assert len(fb_buttons) == 8
    # 2026-09-01 起这六项**确实**降到 17px：补了半角点号后串长 24 字符，18px 下
    # 超出 220px 文本框。原断言写的是「不该降级」，那是补点号之前的事实。
    # 若日后判定必须保住 18px，得缩短文案（如去掉名字间空格）而不是放宽这里。
    assert all(b.startswith(("sel_s6s_110_", "sel_s2s_260_", "sel_s4s_420_"))
               for b in fb_buttons)
    for b, size, tried in fallbacks:
        assert size == FONT_SIZE_CASCADE[-1] == 17
        assert tried == [FONT_SIZE_CASCADE[0]]
    non_fb = set(plans) - set(fb_buttons)
    assert {plans[b]["font_size"] for b in non_fb} == {FONT_SIZE_CASCADE[0]}


def test_measure_ink_extent_uses_real_rendered_pixels_not_char_count():
    """x 轴越界的关键回归：18px 下这类字符串的 textlength 估算值本身就已经
    很接近上限，只有测真实描边墨迹才能精确判定是否越界。

    ⚠ 这条字符串是 **v19 之前** 的 s6s_110 座席文本（现役已改为半角罗马音
    `ASakura BAyano CYuichi`，18px 下不再越界）。**刻意保留为史料**：现役
    134 条按钮里 x 轴越界者为 0，仅剩的 14 条回落全是字高越界，语料里再也
    找不出第二个 x 轴样例。这条一旦删掉，「墨迹测量优于字符数估算」在**宽度
    方向**上就此失去回归——而当初逼出这套测量法的正是宽度。
    """
    text = "Aサクラ Bアヤノ Cユウイチ"
    font18 = _font(18)
    font17 = _font(17)
    extent18 = measure_ink_extent(text, font18, TEXT_BOX)
    extent17 = measure_ink_extent(text, font17, TEXT_BOX)
    x0, x1, y0, y1 = extent18
    assert x1 > TEXT_BOX[2], "18px 下这条真实文本理应实测越界（本轮判定的真实事实）"
    x0, x1, y0, y1 = extent17
    assert TEXT_BOX[0] <= x0 and x1 <= TEXT_BOX[2]
    assert TEXT_BOX[1] <= y0 and y1 <= TEXT_BOX[3]


def test_measure_ink_extent_detects_synthetic_oversize_both_axes():
    """回归证明：padded-canvas 测量法真的能测出两个方向的越界，不只是
    垂直方向（scene/ 的既有机制只测了垂直）。"""
    huge_font = _font(80)
    extent = measure_ink_extent("字字字字字字", huge_font, TEXT_BOX)
    assert extent is not None
    x0, x1, y0, y1 = extent
    assert x0 < TEXT_BOX[0] or x1 > TEXT_BOX[2]
    assert y0 < TEXT_BOX[1] or y1 > TEXT_BOX[3]


def test_build_render_plan_hard_failure_when_smallest_tier_still_overflows():
    smallest = FONT_SIZE_CASCADE[-1]
    fonts_by_size = {smallest: _font(smallest)}
    long_text = "这是一段故意写得非常长非常长非常长的按钮文本用来测试硬失败情形"
    texts = {"fake_button": long_text}
    plans, fallbacks, hard_failures = build_render_plan(
        texts, fonts_by_size, cascade=[smallest])
    assert plans == {}
    assert fallbacks == []
    assert len(hard_failures) == 1
    button, text, size, info = hard_failures[0]
    assert button == "fake_button"
    assert text == long_text
    assert size == smallest


def test_run_raises_before_writing_any_file_on_hard_failure(tmp_path, monkeypatch):
    import tools.bake_select as bs
    covered, missing, _ev = compute_coverage()
    assert missing == []

    def fake_compute_coverage():
        c = dict(covered)
        c["sel_s1s_35_sel_a"] = dict(c["sel_s1s_35_sel_a"])
        c["sel_s1s_35_sel_a"]["zh"] = "这是一段故意写得非常长非常长非常长的按钮文本用来测试硬失败情形" * 2
        return c, [], _ev

    monkeypatch.setattr(bs, "compute_coverage", fake_compute_coverage)
    monkeypatch.setattr(bs, "OUT_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="cascade .* exhausted"):
        bs.run(write=True)
    assert list(tmp_path.iterdir()) == []


def test_fallbacks_disabled_would_hide_the_downgrade():
    """变异回归形态：模拟 fallbacks 列表被静默清空的坏实现，证明如果真的
    这样改，2 条真实回落就会从"能看到"变成"看不到"。"""
    covered, missing, _ev = compute_coverage()
    assert missing == []
    texts = {b: covered[b]["zh"] for b in covered}
    fonts_by_size = load_fonts()
    _plans, real_fallbacks, _hard = build_render_plan(texts, fonts_by_size)

    def broken(*a, **kw):
        plans, _fb, hard = build_render_plan(*a, **kw)
        return plans, [], hard

    _plans2, fake_fallbacks, _hard2 = broken(texts, fonts_by_size)
    # 2026-09-01：s6s_110 六项按用户裁定在字母与名字间补了半角点号
    # （罗马音化后 ASakura 会连读成一个词，原文 Aサクラ 靠字符集切换天然分隔），
    # 串长了 6 个字符，于是这六项也从 18px 降到 17px —— 2 → 8 是预期的。
    assert len(real_fallbacks) == 8
    assert fake_fallbacks == []


# ---------------------------------------------------------------------------
# 4. 像素保全闸：TEXT_BOX 之外逐字节不变，off/on 两态分别验证
# ---------------------------------------------------------------------------

def test_find_outside_box_diffs_detects_change_outside_box():
    a = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 129))
    b = a.copy()
    b.putpixel((0, 0), (255, 0, 0, 255))
    diffs = find_outside_box_diffs(a, b, TEXT_BOX)
    assert (0, 0) in diffs


def test_find_outside_box_diffs_ignores_change_inside_box():
    a = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 129))
    b = a.copy()
    b.putpixel((125, 13), (255, 0, 0, 255))
    diffs = find_outside_box_diffs(a, b, TEXT_BOX)
    assert diffs == []


def test_bake_button_erases_opaque_ink_without_ghosting():
    for variant in ("off", "on"):
        cell = Image.new("RGBA", (CELL_W, CELL_H), FILL_BY_VARIANT[variant])
        d = ImageDraw.Draw(cell)
        d.rectangle([TEXT_BOX[0], TEXT_BOX[1], TEXT_BOX[2] - 1, TEXT_BOX[3] - 1],
                    fill=(255, 255, 255, 255))
        font = _font(FONT_SIZE_CASCADE[-1])
        new_cell = bake_button(cell, "去", font, variant)
        px = new_cell.load()
        corner = px[TEXT_BOX[0] + 1, TEXT_BOX[1] + 1]
        assert corner == FILL_BY_VARIANT[variant], (variant, corner)


def test_bake_button_real_data_zero_pixel_violations_sample():
    """全量 268 张在 run() 端到端测试里已经跑过一次（见下），这里另外
    对一小批手选按钮（含最长/最短/s6s_110/标点样例）做独立复算，防止
    只信任 run() 内部同一份逻辑。"""
    covered, missing, _ev = compute_coverage()
    assert missing == []
    texts = {b: covered[b]["zh"] for b in covered}
    fonts_by_size = load_fonts()
    plans, _fb, hard = build_render_plan(texts, fonts_by_size)
    assert hard == []
    fonts_by_button = resolve_fonts_by_button(plans, fonts_by_size)
    for button in CELLZOOM_BUTTONS:
        for variant in ("off", "on"):
            orig = Image.open(_button_path(button, variant)).convert("RGBA")
            new = bake_button(orig, texts[button], fonts_by_button[button], variant)
            diffs = find_outside_box_diffs(orig, new, TEXT_BOX)
            assert diffs == [], (button, variant, diffs[:5])


def test_render_text_layer_centers_text():
    font = _font(FONT_SIZE_CASCADE[-1])
    layer = render_text_layer("去", font, "off")
    bbox = layer.split()[-1].getbbox()
    assert bbox is not None
    cx = (bbox[0] + bbox[2]) / 2
    box_cx = (TEXT_BOX[0] + TEXT_BOX[2]) / 2
    assert abs(cx - box_cx) <= 2


# ---------------------------------------------------------------------------
# 5. 描边/填充色：从真实素材实测，不是硬编码猜的值
# ---------------------------------------------------------------------------

def test_stroke_colors_measured_are_qualitatively_blue_off_red_on():
    """不钉死具体 RGB（那是"猜的值"该有的钉法），钉住测绘文档描述的定性
    结论："off 偏蓝描边"、"on 偏红描边"。"""
    off_stroke = STROKE_BY_VARIANT["off"]
    on_stroke = STROKE_BY_VARIANT["on"]
    r, g, b, _a = off_stroke
    assert b > r, f"off stroke should lean blue: {off_stroke}"
    r, g, b, _a = on_stroke
    assert r > b, f"on stroke should lean red: {on_stroke}"


def test_measure_ink_colors_fill_is_pure_white_both_variants():
    for variant in ("off", "on"):
        fill, _stroke = measure_ink_colors(variant)
        assert fill == TEXT_FILL_COLOR


def test_measure_ink_colors_raises_if_sample_has_no_stroke_pixels():
    """回归形态：若采样按钮全是空白（无墨迹），测色函数必须报错，不能
    悄悄返回一个假的/猜的颜色。"""
    import tools.bake_select as bs
    with pytest.raises(RuntimeError):
        # 传一个真实存在但故意会产生"无 ink"结果的极端场景不好构造，
        # 这里改用空列表直接触发"没有任何采样像素"分支。
        bs.measure_ink_colors("off", sample_buttons=[])


# ---------------------------------------------------------------------------
# 6. 端到端：真实数据全量跑批
# ---------------------------------------------------------------------------

def test_real_run_report_is_clean(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.bake_select.OUT_DIR", str(tmp_path))
    report = run(write=True, with_extras=True)
    assert report["num_buttons"] == 134
    assert report["overflow"] == []
    assert report["pixel_preservation_violations"] == []
    assert report["font_size_cascade"] == FONT_SIZE_CASCADE
    # 2026-09-01：s6s_110 六项按用户裁定在字母与名字间补了半角点号
    # （罗马音化后 ASakura 会连读成一个词，原文 Aサクラ 靠字符集切换天然分隔），
    # 串长了 6 个字符，于是这六项也从 18px 降到 17px —— 2 → 8 是预期的。
    assert len(report["fallbacks"]) == 8
    assert len(report["button_font_sizes"]) == 134
    assert report["coverage_evidence"]["total_buttons"] == 134

    import os
    files = os.listdir(tmp_path)
    png_files = [f for f in files if f.endswith(".png") and not f.startswith("_")]
    assert len(png_files) == 268
    assert "_compare.png" in files
    assert "_cellzoom.png" in files
    assert "_size_ab.png" in files
    assert "manifest.json" in files

    with open(tmp_path / "manifest.json", encoding="utf-8") as f:
        disk_report = json.load(f)
    assert disk_report["fallbacks"] == report["fallbacks"]
    assert disk_report["button_font_sizes"] == report["button_font_sizes"]
    assert disk_report["pixel_preservation_violations"] == []


def test_output_images_are_correct_size_and_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.bake_select.OUT_DIR", str(tmp_path))
    run(write=True, with_extras=False)
    img = Image.open(tmp_path / "sel_s1s_35_sel_a_off.png")
    assert img.size == (CELL_W, CELL_H)
    assert img.mode in ("RGBA", "RGB", "P")
    img2 = img.convert("RGBA")
    assert img2.mode == "RGBA"


# ---------------------------------------------------------------------------
# 7. 复核 / cellzoom / size_ab 图像能正常构建
# ---------------------------------------------------------------------------

def test_build_compare_and_cellzoom_and_size_ab_images_run():
    covered, missing, _ev = compute_coverage()
    assert missing == []
    texts = {b: covered[b]["zh"] for b in covered}
    fonts_by_size = load_fonts()
    plans, _fb, hard = build_render_plan(texts, fonts_by_size)
    assert hard == []
    fonts_by_button = resolve_fonts_by_button(plans, fonts_by_size)

    compare_img = build_compare_image(texts, fonts_by_button)
    assert compare_img.mode == "RGBA"
    assert compare_img.size[0] > 0 and compare_img.size[1] > 0

    cellzoom_img = build_cellzoom_image(texts, fonts_by_button, plans)
    assert cellzoom_img.mode == "RGBA"

    small_size = FONT_SIZE_CASCADE[-1]
    ab_img = build_size_ab_image(texts, fonts_by_size[small_size], small_size,
                                  fonts_by_button, plans)
    assert ab_img.mode == "RGBA"


def test_cellzoom_buttons_include_s6s_110_full_set_and_punctuation_example():
    """本轮任务点名的三类难例都必须在 _cellzoom.png 的选样里：s6s_110
    全部 6 条、标点样例「多半吧……」、以及最长/最短常规译文。"""
    assert set(f"sel_s6s_110_sel_{c}" for c in "abcdef") <= set(CELLZOOM_BUTTONS)
    assert "sel_s2s_340_sel_b" in CELLZOOM_BUTTONS  # 多半吧……


def test_cli_reports_coverage_and_fallbacks(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["bake_select.py", "--check"])
    from tools.bake_select import main
    main()
    out = capsys.readouterr().out
    assert "coverage evidence" in out
    assert "fallbacks" in out
    # 样例取当下真实回落的那条。它换过几次（s6s_110 → sel_s4s_170 → 现在）——
    # 每次都是内容或定位变了，钉住某个具体按钮只会把测试钉在过去。
    assert "sel_s4s_420_sel_b: -> 17px" in out
