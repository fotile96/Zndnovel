"""`tools/bake_select_map_info.py` —— 探索地图底栏 `select/sel_map_0_a` 的两处提示。

这张 480×42 的底栏贴在 `comSelectMap` 画面的 y=230 处（`snr_common.lua`
`layerPosition(l1_10.info, 0, 230)`），五个探索场景共用。图上四块内容：

- 左上「移動場所を選択してください。」：白芯 12px 高 + 红色距离晕，晕向下铺到第 29 行；
- 其下「- MAP SELECT -」：白字 + 黑软阴影，**原样保留**（同 CARD SELECT 与三张模式框）；
- 右侧「現在位置」：浅色芯 11px 高 + 暗红晕，约 6px 归零；
- 右端深色框：运行时被 `sel_map_1_a` 的 120×26 地点条整块盖住，不烤。

要害与模式画面框那三张相同——只换日文那一层，英文一个像素不动——但红晕比它们
强 3–5 倍且压在英文阴影上（第 25 行 α 峰值 41／英文下方 61），裁盒会把旧晕的尾巴
留在更短的中文右边，故走几何足迹两步遮盖（`geo_footprint`）。

下面每条断言要么是原图上量出来的（2026-09-06），要么是在产物上量的。
"""

import json
from dataclasses import replace

from PIL import Image

from tests.conftest import diff_bbox, needs_face_font
from tools import bake_mask
from tools.bake_para_glow import _core_heights, bake_file, measure_para, run
from tools.bake_select_map_info import DATA, SPEC, SRC
from tools.bake_sysgim_glow import MAX_TAIL_DEV, _pm, measure_glow

NAME = "sel_map_0_a"
ROWS = sorted((json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines()
               if l.strip()), key=lambda r: r["row"])

PROMPT_JP, PROMPT_ZH = "移動場所を選択してください。", "请选择要前往的地点。"
LABEL_JP, LABEL_ZH = "現在位置", "当前位置"

# 原图实测的三块字芯 bbox（含端点）。白芯判据与 bake_mask 一致：
# α≥217 且 min(RGB)≥150 且 max−min≤60。
PROMPT_CORE = (7, 9, 201, 20)
LABEL_CORE = (288, 25, 340, 35)
ENGLISH_CORE = (52, 28, 141, 34)
#: 底栏框线（顶线 y=12、斜线、底线 y=40）的唯一颜色；图上别处不用它。
FRAME_LINE = (98, 81, 71, 255)
#: 英文黑软阴影的主体色。
ENGLISH_SHADOW = (0, 0, 0, 128)


def _img():
    return Image.open(SRC / f"{NAME}.png").convert("RGBA")


def _geo():
    return ROWS[0]["geo"]


def _plan(im):
    geo = _geo()
    return bake_mask.plan_geo(im, [tuple(r["box"]) for r in ROWS], geo,
                              bgs=[tuple(r.get("bg", geo["bg"])) for r in ROWS])


def _is_white(p):
    return p[3] >= 217 and min(p[:3]) >= 150 and max(p[:3]) - min(p[:3]) <= 60


def _white_bbox(im, box):
    """盒内白芯像素的 bbox（含端点）；没有则 None。"""
    px = im.load()
    pts = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])
           if _is_white(px[x, y])]
    if not pts:
        return None
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def _inside(pt, rect):
    x, y = pt
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


# ── 数据与路由 ──────────────────────────────────────────────────────────

def test_corpus_is_the_two_prompts_on_the_map_bar():
    assert [r["file"] for r in ROWS] == [NAME, NAME]
    assert [r["row"] for r in ROWS] == [0, 1]
    assert [r["jp"] for r in ROWS] == [PROMPT_JP, LABEL_JP]
    assert [r["zh"] for r in ROWS] == [PROMPT_ZH, LABEL_ZH]


def test_spec_routes_the_product_into_the_select_face():
    """产物必须落在 `build/select_zh/`：`layers/manifest.toml` 的 `[gim].replace`
    把这个目录整个映射到封包的 `select/`，与 `sel_map_1_a` 同一条回注路径。"""
    assert SRC.name == "select" and SRC.parent.name == "png"
    assert SPEC.out.name.split("__")[0] == "select_zh"
    assert SPEC.mask_mode == "geo_footprint"
    # 与同模板的三张模式框（music/graphic/memory）同字同号：字号锚在**行高**，
    # 不锚字芯。锚字芯是为 title_* 那种 7px 小注设的；这里日文白芯 12px、
    # 模式框的日文白芯也是 12px，它们按行高渲成 13px 并经用户看过——锚字芯会
    # 落到 11px，四条同模板的提示栏里就只有这一条小一圈。
    assert SPEC.face == "sysgim"
    assert SPEC.core_anchor is False
    # 整张统一 13px（Y7：一张图一个字号）。自动选号按 `_core_mask` 的高度卡在原行高
    # 13 之下，落到 12px——但那把尺子比产物里 α≥217 的白芯高约 2 行：12px 渲出的
    # 白芯只有 11 行（日文 12 行），「当前位置」11px 只有 10 行、宽 41（日文 11 行、
    # 宽 53）。13px 时白芯 12 行 / 12 行、宽 115 / 49——与日文同高、与模式框同档
    # （2026-09-06 四档对照后定）。
    assert SPEC.force_size == 13


# ── 遮盖方案（原图上量）───────────────────────────────────────────────────

def test_replaced_layer_is_exactly_the_two_japanese_texts():
    """要换掉的墨 = 日文提示 + 「現在位置」，一个像素都不落在英文上。"""
    mp = _plan(_img())
    ink = [(x, y) for y in range(42) for x in range(480) if mp.ink_core[y][x]]
    in_prompt = [p for p in ink if _inside(p, PROMPT_CORE)]
    in_label = [p for p in ink if _inside(p, LABEL_CORE)]
    assert len(in_prompt) >= 400 and len(in_label) >= 120, (len(in_prompt), len(in_label))
    assert len(in_prompt) + len(in_label) == len(ink), "旧墨落在两块日文字芯之外"
    assert not any(_inside(p, ENGLISH_CORE) for p in ink)


def test_english_subtitle_and_its_shadow_are_protected():
    """英文的白芯与它的黑软阴影都在保留层的地盘里——遮盖与嵌字都进不去。"""
    im = _img()
    mp = _plan(im)
    px = im.load()
    unprotected = [(x, y) for y in range(24, 38) for x in range(44, 152)
                   if (_is_white(px[x, y]) or px[x, y] == ENGLISH_SHADOW)
                   and not mp.protect[y][x]]
    assert unprotected == []


def test_every_box_passes_the_glow_convergence_check_and_has_a_glow():
    """底色取对了没有，用「环的远端收不收敛回底」验；两处都必须量到真发光。"""
    im = _img()
    mp = _plan(im)
    geo = _geo()
    for r in ROWS:
        g = measure_glow(im, tuple(r["box"]), ignore=mp.protect_at,
                         core_of=mp.is_ink_core, bg=tuple(r.get("bg", geo["bg"])),
                         probe_d=geo.get("probe_d", bake_mask.GLOW_PROBE_D),
                         tail_tol=geo.get("tail_tol", MAX_TAIL_DEV))
        bgpm = _pm(g.bg)
        assert sum(abs(g.ring[0][i] - bgpm[i]) for i in range(4)) > 100, r["row"]


def test_boxes_hold_one_line_each_with_the_measured_core_heights():
    """盒里必须**正好一行**：提示盒底 25 是上界（英文阴影从第 25 行起）。
    字芯高是选字号的锚：日文 12px、「現在位置」11px。"""
    im = _img()
    mp = _plan(im)
    geo = _geo()
    expect = {0: 12, 1: 11}
    for r in ROWS:
        box = tuple(r["box"])
        g = measure_glow(im, box, ignore=mp.protect_at, core_of=mp.is_ink_core,
                         bg=tuple(r.get("bg", geo["bg"])),
                         probe_d=geo.get("probe_d", bake_mask.GLOW_PROBE_D))
        para = measure_para(im, box, g, r["jp"].split("\n"))
        assert len(para.tops) == 1, (r["row"], para.tops)
        assert _core_heights(im, box, para) == [expect[r["row"]]], r["row"]


# ── 产物（真渲染）────────────────────────────────────────────────────────

@needs_face_font("sysgim")
def test_bake_touches_nothing_but_the_two_japanese_texts():
    """**本文件的主张。** 英文、框线、占位框、两块文字之间的空当逐像素不变。"""
    orig = _img()
    report = []
    baked = bake_file(NAME, ROWS, report, SPEC)
    assert not [l for l in report if l.startswith(("OVERFLOW", "PIXEL-VIOLATION"))], report
    op, bp = orig.load(), baked.load()
    # 框线：三条线的每一个像素
    assert all(bp[x, y] == FRAME_LINE for y in range(42) for x in range(480)
               if op[x, y] == FRAME_LINE)
    # 英文白芯与阴影
    assert all(bp[x, y] == op[x, y] for y in range(24, 38) for x in range(44, 152)
               if _is_white(op[x, y]) or op[x, y] == ENGLISH_SHADOW)
    # 占位框及其右侧、两块文字之间的空当
    for region in ((353, 0, 480, 42), (212, 0, 276, 42)):
        assert diff_bbox(orig.crop(region), baked.crop(region)) is None, region


def _visible_leftover(baked):
    """新字右边、旧晕原本铺到的地方，还剩多少**看得见**的像素。

    看得见＝预乘 L1 离底超过 geo 的可见性地板（`glow_floor`）——与 `plan_geo`
    闭合自查用的是同一把尺子。足迹半径外允许留 α1–2 的边角（dev 2–4），那是
    实测归零前的最后一圈，1:1 不可见；裁盒留下的尾巴是 α 几十的一整条。
    """
    core = _white_bbox(baked, tuple(ROWS[0]["box"]))
    assert core is not None
    x0 = max(core[2] + 12, 152)      # 152 = 英文保留组盒右缘，其内是保留层的地盘
    bp = baked.load()
    bgpm = _pm(tuple(_geo()["bg"]))
    dev = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    return [(x, y, bp[x, y]) for y in list(range(0, 9)) + list(range(21, 31))
            for x in range(x0, 215) if dev(bp[x, y]) > _geo()["glow_floor"]]


@needs_face_font("sysgim")
def test_old_red_glow_tail_does_not_outlive_the_shorter_chinese_line():
    """中文比日文短：旧晕在新字右边的尾巴必须一起消失，而不是像裁盒那样留下。"""
    leftover = _visible_leftover(bake_file(NAME, ROWS, [], SPEC))
    assert leftover == [], leftover[:10]


@needs_face_font("sysgim")
def test_clipping_to_the_box_would_have_left_the_tail_behind():
    """对照：模式框那种裁盒做法在这张图上**不够**——它把第 25 行起的旧晕整条留给
    英文行，而那里离底最远处 α41（英文正下方 61），是模式框残留（α≤11）的 3–5 倍。
    这条钉住「为什么这张走几何足迹」的前提；前提若变（比如原图换了），它先红。"""
    clipped = replace(SPEC, mask_mode=None, clip_to_box=True)
    rows = [{k: v for k, v in r.items() if k != "geo"} for r in ROWS]
    leftover = _visible_leftover(bake_file(NAME, rows, [], clipped))
    assert len(leftover) >= 50, len(leftover)
    assert max(p[2][3] for p in leftover) >= 30


@needs_face_font("sysgim")
def test_rendered_cores_match_the_japanese_heights():
    """拿同一把尺子（产物里 α≥217 的白芯）比：提示白芯 12 行＝日文 12 行、宽 ≥115；
    「当前位置」11–12 行对日文 11 行、宽 ≥47 对日文 53。这是 13px 的实测结果，
    12px/11px 会各矮一行、窄一截（见 spec 测试的注释）。"""
    baked = bake_file(NAME, ROWS, [], SPEC)
    p = _white_bbox(baked, tuple(ROWS[0]["box"]))
    assert 12 <= p[3] - p[1] + 1 <= 13 and p[2] - p[0] + 1 >= 115, p
    l = _white_bbox(baked, tuple(ROWS[1]["box"]))
    assert 11 <= l[3] - l[1] + 1 <= 12 and l[2] - l[0] + 1 >= 47, l


@needs_face_font("sysgim")
def test_label_is_recentred_where_the_japanese_was():
    """「当前位置」与「現在位置」同为四字，复现原块重心，仍落在斜线与占位框之间。"""
    orig, baked = _img(), bake_file(NAME, ROWS, [], SPEC)
    box = tuple(ROWS[1]["box"])
    o, b = _white_bbox(orig, box), _white_bbox(baked, box)
    assert abs((b[0] + b[2]) / 2 - (o[0] + o[2]) / 2) <= 1.5, (o, b)
    assert 24 <= b[1] and b[3] <= 36, b


@needs_face_font("sysgim")
def test_prompt_stays_left_aligned():
    """提示是贴着底栏左缘的一行标签，不是居中块（同模式框的裁定）。"""
    orig, baked = _img(), bake_file(NAME, ROWS, [], SPEC)
    box = tuple(ROWS[0]["box"])
    assert abs(_white_bbox(baked, box)[0] - _white_bbox(orig, box)[0]) <= 1


@needs_face_font("sysgim")
def test_run_writes_the_product_under_its_own_name(tmp_path):
    assert run(replace(SPEC, out=tmp_path), label="测试") == 0
    assert (tmp_path / f"{NAME}.png").exists()
