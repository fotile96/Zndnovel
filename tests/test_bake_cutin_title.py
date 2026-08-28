"""`tools/bake_cutin_title.py` —— 章节起止字幕卡（`cutin/cut_e_*` `cut_s_*`）。

这一批的要害不是渲染，是**一致性**：24 张里 23 张在 lua 里有同一个字符串，作为
`scene_*(doScriptScene, "セクション１：アヤノ")` 的场景标题参数由引擎实时渲染。
同一个逻辑串两个载体，译文必须逐字相同，否则玩家会在同一屏看到两种写法。
"""

import json

import yaml
from PIL import Image

from tools.bake_cutin_title import DATA, SPEC, SRC
from tools.bake_para_glow import Para, choose_size, measure_para, segment_lines
from tools.bake_sysgim_glow import measure_glow

ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def _img(name):
    return Image.open(SRC / f"{name}.png").convert("RGBA")


def test_corpus_is_24_cards_all_translated():
    assert len(ROWS) == 24
    assert all(r["zh"].strip() for r in ROWS)
    assert sum(1 for r in ROWS if r["file"].startswith("cut_e_")) == 10
    assert sum(1 for r in ROWS if r["file"].startswith("cut_s_")) == 14


def test_translations_are_verbatim_from_the_frozen_skeleton():
    """**本文件的主张。** 凡骨架里有的，必须逐字沿用——骨架是冻结基准
    （`git tag skeleton-v2`），且同一串还由 lua 场景标题走引擎渲染。
    两个载体给出不同译文，等于同一个章节标签在游戏里有两种写法。
    """
    def by_key(p):
        return {(r.get("card"), r.get("variant")): r for r in
                yaml.safe_load(p.read_text(encoding="utf-8"))}

    root = DATA.parent.parent
    cj = by_key(root / "skeleton" / "cards.jp.yaml")
    cz = by_key(root / "skeleton" / "cards.zh.yaml")
    frozen = {str(j["title_jp"]): cz[k].get("title_zh")
              for k, j in cj.items() if k in cz and j.get("title_jp")}

    checked = 0
    for r in ROWS:
        jp = r["jp"].split("\n")[0]
        if jp in frozen:
            assert r["zh"].split("\n")[0] == frozen[jp], (jp, r["zh"], frozen[jp])
            checked += 1
    assert checked >= 10, f"只核到 {checked} 条，骨架对应关系可能断了"


def test_every_box_passes_the_glow_convergence_check():
    for r in ROWS:
        measure_glow(_img(r["file"]), tuple(r["box"]))


def test_two_line_card_splits_and_gets_two_different_sizes():
    """`cut_s_ex2` 是唯一的两行卡，它逼出了共用核心的两处设定。

    ① 两行只隔 3px 空行（末行墨迹 y27、次行起 y31），`LINE_MERGE_GAP` 取 4 会把
       两行并成一行；取 3 才分得开。而 3 对 `event/op_*` 的四段同样给出正确行数
       ——一个常数满足两面，不给单张开特例。
    ② 两行墨迹高 21px 与 13px，差 8px 远超噪声。若按全段中位数选字号（17），
       小字注会被渲成大字。故逐行选字号。
    """
    r = next(x for x in ROWS if x["file"] == "cut_s_ex2")
    im = _img(r["file"])
    box = tuple(r["box"])
    g = measure_glow(im, box)
    assert len(segment_lines(im, box, g)) == 2

    jp = r["jp"].split("\n")
    para = measure_para(im, box, g, jp)
    assert max(para.heights) - min(para.heights) >= 6, para.heights
    sizes, _over = choose_size(r["zh"].split("\n"), para, box, r["file"], SPEC.face)
    assert len(set(sizes)) == 2, sizes
    assert sizes[0] > sizes[1], sizes


def test_single_line_cards_get_one_size():
    """单行卡与行高一致的段仍是全段同档——Y7 警告过「一行 15px 一行 16px 会显得坏掉」。"""
    for name in ("cut_e_s1", "cut_s_s1", "cut_s_s82"):
        r = next(x for x in ROWS if x["file"] == name)
        im = _img(name)
        box = tuple(r["box"])
        para = measure_para(im, box, measure_glow(im, box), r["jp"].split("\n"))
        sizes, _ = choose_size(r["zh"].split("\n"), para, box, name, SPEC.face)
        assert len(set(sizes)) == 1, (name, sizes)


def test_baked_blocks_are_centred_like_the_originals():
    """中文比日文短得多（`章节 1：完` 6 字 vs `セクション１：おわり` 10 字），
    块宽 99 vs 180——若沿用原文左缘会明显塌左。承 op 那轮的结论：复现**重心**。
    """
    from tools.bake_para_glow import bake_file

    for r in ROWS:
        name = r["file"]
        box = tuple(r["box"])
        orig = _img(name)
        baked = bake_file(name, [r], [], SPEC)

        def centre(im):
            a = im.split()[-1].load()
            xs = [x for y0, y1 in segment_lines(im, box, measure_glow(im, box))
                  for x in range(box[0], box[2]) for y in range(y0, y1) if a[x, y] > 140]
            return (min(xs) + max(xs) + 1) / 2

        assert abs(centre(baked) - centre(orig)) <= 6, name
