"""`tools/bake_cutin_title.py` —— 章节起止字幕卡（`cutin/cut_e_*` `cut_s_*`）。

这一批的要害不是渲染，是**一致性**：24 张里 23 张在 lua 里有同一个字符串，作为
`scene_*(doScriptScene, "セクション１：アヤノ")` 的场景标题参数由引擎实时渲染。
同一个逻辑串两个载体，译文必须逐字相同，否则玩家会在同一屏看到两种写法。
"""

import json

import yaml
from PIL import Image

from tests.conftest import needs_face_font
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


@needs_face_font("cutin")
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


@needs_face_font("cutin")
def test_single_line_cards_get_one_size():
    """单行卡与行高一致的段仍是全段同档——Y7 警告过「一行 15px 一行 16px 会显得坏掉」。"""
    for name in ("cut_e_s1", "cut_s_s1", "cut_s_s82"):
        r = next(x for x in ROWS if x["file"] == name)
        im = _img(name)
        box = tuple(r["box"])
        para = measure_para(im, box, measure_glow(im, box), r["jp"].split("\n"))
        sizes, _ = choose_size(r["zh"].split("\n"), para, box, name, SPEC.face)
        assert len(set(sizes)) == 1, (name, sizes)


@needs_face_font("cutin")
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


# ---------------------------------------------------------------------------
# 字号加成：人工把算出来的档位再抬一格
# ---------------------------------------------------------------------------


@needs_face_font("cutin")
def test_size_bias_raises_every_line_by_one_step(monkeypatch):
    """`ZND_UI_SIZE_BIAS_CUTIN=1` 就该让每一行都比算出来的大一档。

    加成必须走在 `choose_size` 里、而不是烤完再放大：字号是**逐行**选的
    （`cut_s_ex2` 是 21px 标题 + 13px 小字注），整段统一缩放会把那个差抹掉。
    """
    # 基线显式设 0，**不能用 delenv**：配置文件里已经有 size_bias 了，
    # 删掉环境变量只会退回到配置那一档，于是"基线"与"加成后"是同一个值，
    # 这条断言就永远绿。环境变量压过配置，这里正是要用它。
    monkeypatch.setenv("ZND_UI_SIZE_BIAS_CUTIN", "0")
    base = {}
    for r in ROWS:
        im, box = _img(r["file"]), tuple(r["box"])
        para = measure_para(im, box, measure_glow(im, box), r["jp"].split("\n"))
        base[r["file"]] = (choose_size(r["zh"].split("\n"), para, box,
                                       r["file"], SPEC.face)[0], para, box)

    monkeypatch.setenv("ZND_UI_SIZE_BIAS_CUTIN", "1")
    for name, (sizes, para, box) in base.items():
        r = next(x for x in ROWS if x["file"] == name)
        got, _ = choose_size(r["zh"].split("\n"), para, box, name, SPEC.face)
        assert got == [s + 1 for s in sizes], (name, sizes, got)


@needs_face_font("cutin")
def test_size_bias_never_pushes_text_out_of_its_box(monkeypatch):
    """抬档若会撞出盒外，必须退回并报告——**溢出是缺陷，不是风格**。

    这是加成与倾斜的分界：倾斜在取值域内不改变可用宽的判定，抬档直接改。
    """
    # 撞盒的是**最窄的那张**（`cut_s_s82`「五年后」，89px 宽、可用 71px），
    # 不是字最多的那张——中文比日文短得多，宽盒里加成 +6 照样绰绰有余
    # （`cut_s_ex2` 可用 301px，26px 下才 205px）。挑错卡这条就永远绿。
    monkeypatch.setenv("ZND_UI_SIZE_BIAS_CUTIN", "6")
    r = next(x for x in ROWS if x["file"] == "cut_s_s82")
    im, box = _img(r["file"]), tuple(r["box"])
    para = measure_para(im, box, measure_glow(im, box), r["jp"].split("\n"))
    sizes, over = choose_size(r["zh"].split("\n"), para, box, r["file"], SPEC.face)
    assert over, "撞盒了却没报告"
    avail = box[2] - box[0] - 2 * (para.left - box[0])
    from tools.bake_sysgim_glow import _core_mask
    for line, size in zip(r["zh"].split("\n"), sizes):
        bb = _core_mask(line, size, r["file"], SPEC.face).getbbox()
        assert bb[2] - bb[0] <= avail, (line, size, bb[2] - bb[0], avail)
