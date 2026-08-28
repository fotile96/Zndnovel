"""`tools/bake_mode_frame.py` —— 三张模式画面框的选择提示。

`music_01_a`（曲目）／`graphic_01_a`（CG）／`memory_01_a`（回想场景）是**同一套模板**：
左上角一行白字红晕的日文提示，其下一行英文大词（`- MUSIC SELECT -` 等）。

**要害是「只改假名层」**：英文按用户裁定原样保留，而它离日文只有 7px、
发光半径却有 18px——两行的晕必然互相进盒。所以盒只框日文那一行，
英文一个像素都不许动。这两条都在下面逐像素验。
"""

import json

from PIL import Image

from tests.conftest import diff_bbox, needs_face_font
from tools.bake_mode_frame import DATA, SPEC, SRC
from tools.bake_para_glow import bake_file, measure_para
from tools.bake_sysgim_glow import measure_glow

ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def _img(name):
    return Image.open(SRC / f"{name}.png").convert("RGBA")


def test_corpus_is_the_three_mode_frames_all_translated():
    assert sorted(r["file"] for r in ROWS) == [
        "graphic/graphic_01_a", "graphic/memory_01_a", "music/music_01_a"]
    assert all(r["zh"].strip() for r in ROWS)


def test_every_box_passes_the_glow_convergence_check():
    """底色取对了没有，用「环的远端收不收敛回底」验——不是靠肉眼看它是不是透明。"""
    for r in ROWS:
        measure_glow(_img(r["file"]), tuple(r["box"]))


def test_boxes_hold_the_japanese_line_only():
    """盒里必须**正好一行**。

    英文小注在 y[27,33]，日文在 y[7,19]，中间只隔 7px；`MAX_DIST` 是 18，
    两行的晕在盒里叠着。盒若框到两行，`measure_para` 会分出 2 段，
    而第二段是英文——那就等于把英文也交给中文字体去重渲了。
    """
    for r in ROWS:
        im, box = _img(r["file"]), tuple(r["box"])
        para = measure_para(im, box, measure_glow(im, box), r["jp"].split("\n"))
        assert len(para.tops) == 1, (r["file"], para.tops)
        assert 10 <= para.heights[0] <= 15, (r["file"], para.heights)


@needs_face_font("sysgim")
def test_english_subtitle_is_left_byte_identical():
    """**本文件的主张。** 英文大词按用户裁定原样保留——不是"重渲得像"，是**没动过**。

    重渲一遍即便字体相同也会有抗锯齿差异，而这里的英文是原作的点阵形态，
    换任何字体都会走样。故逐像素比对盒外区域。
    """
    for r in ROWS:
        name, box = r["file"], tuple(r["box"])
        orig = _img(name)
        baked = bake_file(name, [r], [], SPEC)
        # 盒外整体不许变（英文小注、右下 Cancel、中间面板都在盒外）
        masked = baked.copy()
        masked.paste(orig.crop(box), box)      # 把盒内换回原图，只剩盒外的差异
        assert diff_bbox(orig, masked) is None, (
            f"{name} 盒外像素被改动：{diff_bbox(orig, masked)}")


@needs_face_font("sysgim")
def test_run_writes_into_the_source_subdirectory(tmp_path):
    """三张分处 `png/music/` 与 `png/graphic/`，`file` 因此带子目录。

    产物必须照搬那层子目录：一是回注时不必再猜哪张回哪个目录，
    二是 `run()` 原先只 mkdir 顶层，带子目录的名字会直接 `FileNotFoundError`。
    """
    from dataclasses import replace

    from tools.bake_para_glow import run

    run(replace(SPEC, out=tmp_path), label="测试")
    assert (tmp_path / "music" / "music_01_a.png").exists()
    assert (tmp_path / "graphic" / "memory_01_a.png").exists()


@needs_face_font("sysgim")
def test_label_is_left_aligned_not_centred():
    """**这一面是齐左标签，不是居中块**——与 op/cutin 的「复现重心」相反。

    裁决 Y15 定「复现重心不复现左缘」，理由是原文**填满整宽**、中文只有它 65–70%
    长，照搬左缘会整块塌左。这三张的前提不同：日文是贴着屏幕左上角的一行标签
    （字芯左缘 x=5/6/7），居中会把中文推到 x≈50，在那条粉色标题条上留出一个
    左边的大豁口。前提不同，结论就该不同。
    """
    for r in ROWS:
        name, box = r["file"], tuple(r["box"])
        orig, baked = _img(name), bake_file(name, [r], [], SPEC)
        def ink_left(im):
            a = im.getchannel("A").load()
            return min(x for x in range(box[0], box[2])
                       for y in range(box[1], box[3]) if a[x, y] > 200)
        assert abs(ink_left(baked) - ink_left(orig)) <= 1, name
