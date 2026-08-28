"""`tools/bake_event_op.py` —— 序章题词（`png/event/op_*`）的烤字。

这一面的**渲染单元是「段」不是「行」**，原因是量出来的：发光半径 MAX_DIST=18 与
行距 18–19px 相当，邻行的晕必然进盒，逐行盒的远场永远不是纯背景。实测 15 个逐行盒
有 4 个被底色收敛检查拒绝，且放宽/收紧盒形都救不回来。
"""

import json

import pytest
from PIL import Image, ImageFilter

from tools.bake_event_op import (
    BLUR_RADIUS, DATA, SRC, choose_size, load_text, measure_para, segment_lines,
)
from tools.bake_sysgim_glow import measure_glow

ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def _img(name):
    return Image.open(SRC / f"{name}.png").convert("RGBA")


def test_corpus_is_four_paragraph_blocks_over_three_sheets():
    assert len(ROWS) == 4
    assert {r["file"] for r in ROWS} == {"op_1_a", "op_2_a", "op_3_a"}


def test_every_block_box_passes_the_glow_convergence_check():
    """段落盒必须能被发光模型吃下——逐行盒不能，这正是本模块存在的理由。

    这条一旦红，说明有人把盒改小了：`op_2_a` 收到 [30,74,450,177] 时环在 d=18 处
    离底 9.5，会被（正确地）拒绝。段落盒需 ≥14px 边距。
    """
    for r in ROWS:
        measure_glow(_img(r["file"]), tuple(r["box"]))   # 不抛错即通过


def test_segmentation_agrees_with_the_transcription():
    """图上分出的行数必须与人转写的 jp 行数一致——两条独立来源互相校验。

    分行阈值取 0.5 而非字芯用的 0.85：`op_2_a` 第 2 行「『もし』である、と。」
    只有标点与少量假名，0.85 下会被切成 3 段（识别成 6 行而非 5 行）。
    """
    for r in ROWS:
        im = _img(r["file"])
        bands = segment_lines(im, tuple(r["box"]), measure_glow(im, tuple(r["box"])))
        assert len(bands) == r["jp"].count("\n") + 1, r["file"]


def test_measure_para_line_heights_are_all_positive():
    """回归：`heights` 曾写成 `[y1 - y0 for _, y1 in bands]`。

    那个 `y0` 不是推导式的变量，而是上面那个真 for 循环**泄漏下来的最后一行**的
    y0——于是除末行外全是负数（实测 [-43,-24,-6,13]），中位数 -24，`choose_size`
    找不到满足 h≤-24 的档，一路掉到级联最小的 11px。四个块里三个字号都错了，
    而**图上看起来只是「字偏小」**，不像有 bug。
    """
    for r in ROWS:
        im = _img(r["file"])
        para = measure_para(im, tuple(r["box"]), measure_glow(im, tuple(r["box"])),
                            r["jp"].count("\n") + 1)
        assert all(h > 0 for h in para.heights), (r["file"], para.heights)
        assert all(10 <= h <= 16 for h in para.heights), (r["file"], para.heights)


def test_measure_para_pitch_matches_the_measured_18_to_19():
    for r in ROWS:
        im = _img(r["file"])
        para = measure_para(im, tuple(r["box"]), measure_glow(im, tuple(r["box"])),
                            r["jp"].count("\n") + 1)
        if len(para.tops) > 1:
            assert 17 <= para.pitch <= 20, (r["file"], para.pitch)
        else:
            assert para.pitch == 0


def test_line_count_mismatch_raises_instead_of_rendering():
    """两条来源对不上就抛错，不将就。继续渲染只会把错误固化进产物。"""
    r = ROWS[2]
    im = _img(r["file"])
    with pytest.raises(ValueError, match="两条独立来源不一致"):
        measure_para(im, tuple(r["box"]), measure_glow(im, tuple(r["box"])), 99)


def test_blur_radius_reproduces_the_real_b_variants():
    """**`_b` 不是独立内容**，是 `_a` 的虚化版——这条把那个结论钉住。

    对真实素材逐半径扫，r=1.5 时 alpha 平均残差最小。若日后有人改了 BLUR_RADIUS，
    这条会红。
    """
    for n in ("op_1", "op_2", "op_3"):
        a = _img(f"{n}_a")
        b = _img(f"{n}_b")
        got = a.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        resid = sum(abs(p - q) for p, q in
                    zip(got.split()[-1].tobytes(), b.split()[-1].tobytes())) / (a.width * a.height)
        assert resid < 1.5, (n, resid)


def test_untranslated_sheets_are_not_rendered():
    """空 `zh` 的图整张不渲染——只渲一半会得到半中半日的图，看起来像"做完了"。"""
    text, untranslated = load_text()
    for name in untranslated:
        assert name not in text


def test_choose_size_anchors_to_original_ink_height_not_pitch():
    """承裁决 Y7：字号锚在原行墨迹高（13px），不锚行距（18–19px）。

    按行距选会渲出比原文明显更大的字。
    """
    r = ROWS[3]
    im = _img(r["file"])
    para = measure_para(im, tuple(r["box"]), measure_glow(im, tuple(r["box"])),
                        r["jp"].count("\n") + 1)
    import statistics

    from tools.bake_sysgim_glow import FONT_CASCADE, _core_mask

    lines = ["测试文本一二三四五六七八九十"] * 3
    size, _over = choose_size(lines, para, tuple(r["box"]), r["file"])
    target_h = int(statistics.median(para.heights))

    # 断言**不变量**而非某个具体档位：选中档的核高不超过原行墨迹高，
    # 且它是满足这一条的最大档。（起初这里拍了个 `size <= 14`，实测是 15 ——
    # 拍数字的测试只是把当时的观察写死，不是在守性质。）
    bb = _core_mask(lines[0], size, r["file"]).getbbox()
    assert bb[3] - bb[1] <= target_h, (size, bb[3] - bb[1], target_h)
    bigger = [c for c in FONT_CASCADE if c > size]
    for c in bigger:
        cb = _core_mask(lines[0], c, r["file"]).getbbox()
        assert cb[3] - cb[1] > target_h, f"{c}px 也放得下，不该选 {size}px"

    # 而且必须明显小于行距——按行距选会渲出比原文大一圈的字（裁决 Y7）
    assert size < para.pitch
