"""`tools/bake_memory_thumb.py` —— 回想模式缩略图上的 14 个章节名。

**这一面与前面所有面都不同：字直接压在照片上，没有底板可擦。** 前面几面的底要么
是透明、要么是纯色面板，擦掉即可；这里擦掉字之后必须**把照片补回来**。

解法是测出来的：缩略图的每一格都是仓库里某张图的 1/4 缩放（决定性匹配——最佳 2.2、
次名 41+）。13 格能这样重建干净底；第 14 格「いつかきみがみるお話」在全库 2100 张里
没有来源，用上下干净行插值就地修补（用户 2026-08-29 裁定）。
"""

import json

from PIL import Image

from tests.conftest import diff_bbox, needs_face_font
from tools.bake_memory_thumb import (
    BAND, CELL_H, CELL_W, CORE_H, DATA, FIDELITY_MAX, OUTLINE, RIGHT, SOURCES,
    SRC, bake_file, band_for, cell_of, clean_band, source_fidelity,
)

ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_corpus_is_the_fourteen_chapter_names():
    assert len(ROWS) == 14
    assert all(r["zh"].strip() for r in ROWS)
    assert sum(1 for r in ROWS if r["file"].endswith("_1_a")) == 9
    assert sum(1 for r in ROWS if r["file"].endswith("_2_a")) == 5


def test_chapter_names_match_the_cutin_wording():
    """`章节 N` 的写法必须与 `cutin/cut_s_*` 一字不差。

    同一个章节标签在游戏里有两个载体（起始字幕卡、回想缩略图），玩家会在相隔
    几秒的两屏上看到它。写法不一致的代价比看上去大——那正是 cutin 那批
    「同一逻辑串两个载体」的教训。
    """
    cutin = {json.loads(l)["file"]: json.loads(l)["zh"]
             for l in (DATA.parent / "cutin_title_text.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()}
    assert cutin["cut_s_s1"].startswith("章节 1：")
    assert cutin["cut_s_ex1"].startswith("章节 EX1：")
    zh = {r["jp"]: r["zh"] for r in ROWS}
    assert zh["セクション１"] == "章节 1"
    assert zh["セクションＥＸ１"] == "章节 EX1"


def test_every_cell_is_either_sourced_or_deliberately_inpainted():
    """来源表必须**覆盖每一格**，缺的那格要显式写成 None 而不是漏掉。

    漏掉与「确实没有来源」在代码里长得一样，但含义相反：前者是没查，
    后者是查遍了 2100 张。显式的 None 把这个区别记在案。
    """
    for r in ROWS:
        key = (r["file"], *cell_of(r))
        assert key in SOURCES, f"{key} 不在来源表里"
    assert sum(1 for v in SOURCES.values() if v is None) == 1


def test_sourced_cells_are_faithful_enough_to_paste():
    """有来源的格，其保真度必须真的够好——阈值不是拍的，是双峰之间的空档。

    实测各格在字带**正上方**（无字，可直接比）的平均通道差：
    好的一簇 2.2–5.01，差的一簇 9.04–14.6，空档 [5.01, 9.04]。阈值取中点 7。

    **阈值必须落在空档里**，不能贴着簇的边缘：先取过 5.0，正好把 5.01 那格切到
    错的一侧——那等于让一个测量噪声决定这一格走哪条重建路径。
    """
    ds = [(r["file"], cell_of(r), source_fidelity(r["file"], cell_of(r), src))
          for r in ROWS
          if (src := SOURCES[(r["file"], *cell_of(r))]) is not None]
    good = [d for *_x, d in ds if d <= FIDELITY_MAX]
    bad = [d for *_x, d in ds if d > FIDELITY_MAX]
    assert len(good) == 10 and len(bad) == 3, (len(good), len(bad))
    assert max(good) < FIDELITY_MAX < min(bad), (max(good), min(bad))


def test_data_boxes_match_the_derived_band():
    """数据里的 `box` 必须等于按 `CORE_H` 推出的字带。

    字带是**算出来的**（白芯高 + 上下 1px 描边，白芯中心固定），而 `box` 是各道闸
    与「盒外不许动」那条测试的依据。两者一旦漂开，测试就会守着一个不存在的区域。
    """
    lo, hi = band_for(CORE_H)
    for r in ROWS:
        c, rw = cell_of(r)
        assert r["box"] == [c * CELL_W, rw * CELL_H + lo,
                            (c + 1) * CELL_W, rw * CELL_H + hi], r["file"]


def test_reconstructed_band_joins_the_photo_without_a_seam():
    """重建的字带必须与它上面那一行**接得上**。

    这是能真正抓住「来源选错 / 缩放错 / 对位差一格」的判据——那些错误都会在
    接缝处跳变。判据**自校准**：拿本格自身相邻两行的天然差异当基准，
    重建行与其上一行的差异不该显著超过它。绝对阈值在这里没有意义，
    因为各格的照片纹理差得远。
    """
    for r in ROWS:
        name, cell = r["file"], cell_of(r)
        c, rw = cell
        px = Image.open(SRC / f"{name}.png").convert("RGBA").convert("RGB").load()
        lo, _hi = band_for(CORE_H)

        def rowdiff(ya, yb, src_a=None):
            return sum(abs(a - b) for x in range(CELL_W) for a, b in
                       zip(src_a[x] if src_a else px[c * CELL_W + x, rw * CELL_H + ya],
                           px[c * CELL_W + x, rw * CELL_H + yb])) / (CELL_W * 3)

        natural = max(rowdiff(lo - 3, lo - 2), rowdiff(lo - 2, lo - 1))
        band = clean_band(name, cell).load()
        seam = sum(abs(a - b) for x in range(CELL_W) for a, b in
                   zip(band[x, 0], px[c * CELL_W + x, rw * CELL_H + lo - 1])) / (CELL_W * 3)
        assert seam <= max(natural * 3, 12), (
            f"{name} {cell} 接缝 {seam:.1f} 远超本格天然行差 {natural:.1f}")


@needs_face_font("card")
def test_caption_lands_where_the_original_did():
    """落点：墨迹右缘对齐 x=116（白芯 115 + 1px 描边），且整体落在字带内。

    **判据取「含描边的墨迹」而不是「白芯」**：描边是纯黑压在照片上，差异总是很大；
    白芯的最右一列常常是抗锯齿的浅灰，够不到亮度门槛，于是右缘量出来会在 111–115
    之间跳——那是抗锯齿，不是落点错。

    这条曾经放过一个真错误：`bb` 是在草稿图上以 (10,10) 为原点量的，反推绘制原点时
    那个 10 被减了两次，整块字高了 8px、右缘差 10px。而**产物看上去只是"位置略高"**。
    """
    for r in ROWS:
        name, cell = r["file"], cell_of(r)
        c, rw = cell
        baked = bake_file(name, [r], []).convert("RGB").load()
        blank = clean_band(name, cell).load()
        ink = [(x, y) for y in range(BAND[0], BAND[1]) for x in range(CELL_W)
               if sum(abs(p - q) for p, q in
                      zip(baked[c * CELL_W + x, rw * CELL_H + y],
                          blank[x, y - BAND[0]])) > 90]
        assert ink, name
        assert abs(max(x for x, _ in ink) - (RIGHT + OUTLINE)) <= 1, (name, r["zh"])
        assert BAND[0] <= min(y for _, y in ink), (name, r["zh"])
        assert max(y for _, y in ink) < BAND[1], (name, r["zh"])



@needs_face_font("card")
def test_nothing_outside_the_caption_band_is_touched():
    """格里除字带外一个像素不动——照片是原始资产，重建只该发生在字带里。"""
    for name in sorted({r["file"] for r in ROWS}):
        rows = [r for r in ROWS if r["file"] == name]
        orig = Image.open(SRC / f"{name}.png").convert("RGBA")
        baked = bake_file(name, rows, [])
        masked = baked.copy()
        for r in rows:
            masked.paste(orig.crop(tuple(r["box"])), tuple(r["box"]))
        assert diff_bbox(orig, masked) is None, (
            f"{name} 字带外被改动：{diff_bbox(orig, masked)}")


@needs_face_font("card")
def test_the_face_actually_renders_a_white_core_at_this_size():
    """字必须是**真白**，不是灰的——这是选思源黑体 Medium 而非霞鹜文楷的理由。

    **不能在合成图上验**：`memoryThumbnail_1_a` 的 (0,0) 格照片通体发白，白字压上去
    几乎没有差异，差分只抠得到黑描边（原图也正因此才加描边）。故直接量字体本身。

    实测（统一字号档）：霞鹜文楷纯白核占比 **0.0%**、最亮只到 246；
    思源黑体 Medium 到得了 255。原图是真白芯。
    """
    from PIL import ImageDraw

    from tools.bake_memory_thumb import FACE, unified_size
    from tools.ui_font import truetype

    size = unified_size()
    m = Image.new("L", (300, 40), 0)
    ImageDraw.Draw(m).text((5, 5), "章节 EX1", font=truetype(FACE, size), fill=255)
    ink = [v for v in m.tobytes() if v > 0]
    assert max(ink) == 255, f"{FACE} 在 {size}px 下最亮只有 {max(ink)}，渲的是灰字"
    assert sum(1 for v in ink if v >= 250) / len(ink) > 0.05
