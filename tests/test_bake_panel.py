"""`tools/bake_panel.py` —— sysgim D 族「保留面板、盒内替换」。

两张：`sys_5_d`（239×74 米黄面板、深褐字 3 行）与 `sys_1_g`（127×37 深红面板、
红字 1 行 + 白字 2 行）。

**这一族既不是描边字也不是发光字**，所以 A/B/C 三族的两个工具都不适用：字直接压在
**渐变面板**上。面板底不是纯色（`sys_5_d` 的 B 通道横向从 215 变到 255），
故 `measure_glow` 那套「盒边众数取底」不成立；但三行之间都有干净行，
可以逐列纵向插值把底补回来。
"""

import json

from PIL import Image

from tests.conftest import diff_bbox, needs_face_font
from tools.bake_panel import DATA, SRC, bake_file, ink_colour, row_dirt, rows_by_file

ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_corpus_is_the_two_panels_all_translated():
    assert len(ROWS) == 6
    assert sorted({r["file"] for r in ROWS}) == ["sys_1_g", "sys_5_d"]
    assert all(r["zh"].strip() for r in ROWS)


def test_boxes_have_clean_anchor_rows():
    """每个盒的上下**紧邻行必须无字**——插值的锚就是它们。

    这不是形式要求：`sys_1_g` 三行之间只隔 2–3 行，锚行选错一行就把字当成底
    插进去，产物会出现一条鬼影。判据用逐行离散度，干净行实测 σ≤13，字行 ≥57。
    """
    for r in ROWS:
        im = Image.open(SRC / f"{r['file']}.png").convert("RGBA")
        l, t, rr, b = r["box"]
        for y in (t - 1, b):
            assert row_dirt(im, y, l, rr) < 0.06, (
                f"{r['file']} 锚行 y={y} 含字比例 {row_dirt(im, y, l, rr):.1%}")


def test_ink_colour_is_measured_per_line_not_assumed():
    """字色**逐行实测**：`sys_1_g` 第 1 行是红字、另两行是白字，同一张图里两种色。

    写死一个颜色会让其中一行整行变色，而**产物看上去只是"配色略有不同"**。
    同裁决 C8（卡面字色逐卡实测）。
    """
    cols = {(r["file"], r["row"]): ink_colour(r) for r in ROWS}
    red = cols[("sys_1_g", 0)]
    white1, white2 = cols[("sys_1_g", 1)], cols[("sys_1_g", 2)]
    assert red[0] - max(red[1], red[2]) > 40, f"第 1 行没测出红字：{red}"
    for w in (white1, white2):
        assert max(w[:3]) - min(w[:3]) < 40, f"应是白字却测出偏色：{w}"
    brown = cols[("sys_5_d", 0)]
    assert brown[0] > brown[1] > brown[2], f"sys_5_d 应是深褐字：{brown}"


@needs_face_font("sysgim")
def test_nothing_outside_the_text_boxes_is_touched():
    """面板、边框、圆角一律不动——本族的名字就叫「保留面板」。"""
    for name, rows in rows_by_file().items():
        orig = Image.open(SRC / f"{name}.png").convert("RGBA")
        baked = bake_file(name, rows)
        masked = baked.copy()
        for r in rows:
            masked.paste(orig.crop(tuple(r["box"])), tuple(r["box"]))
        assert diff_bbox(orig, masked) is None, (
            f"{name} 盒外被改动：{diff_bbox(orig, masked)}")


@needs_face_font("sysgim")
def test_japanese_ink_is_gone_from_every_box():
    """盒内不该再有日文墨迹。

    判据**自校准**：拿该盒上方那条干净行的离散度当基准。重建后的行若仍带着
    原来的字，离散度会明显高于它。
    """
    for name, rows in rows_by_file().items():
        orig = Image.open(SRC / f"{name}.png").convert("RGBA")
        for r in rows:
            l, t, rr, b = r["box"]
            # 先只补底、不落字，验的是「底补回来了没有」这一步本身
            from tools.bake_fill import vfill
            filled = vfill(orig, tuple(r["box"]))
            ref = row_dirt(orig, t - 1, l, rr)
            for y in range(t, b):
                assert row_dirt(filled, y, l, rr) <= max(ref * 2 + 0.01, 0.06), (
                    f"{name} 行{r['row']} 补底后 y={y} 仍含 "
                    f"{row_dirt(filled, y, l, rr):.1%}（锚行 {ref:.1%}）")


@needs_face_font("sysgim")
def test_every_line_fits_its_box():
    """**这一族最紧**，装不下必须报出来而不是溢出面板。"""
    report = []
    for name, rows in rows_by_file().items():
        bake_file(name, rows, report)
    assert [x for x in report if x.startswith("OVERFLOW")] == []
