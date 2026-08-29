"""`tools/bake_sysgim_note.py` + `plan_geo` —— E 类收尾五张。

**这一面要害是遮盖判据换了原理。** `title_*` 的 protect 查合并实测的 alpha 上界
表；这五张底不透明/是照片、晕色不同、保留层的晕长 9–10px，那张表照搬不过去。
`plan_geo` 改用**几何足迹**（逐保留层一个保守半径），叠加**幽灵晕减法**——
保留层足迹内擦不掉的旧墨黑晕按合成代数从像素里减掉（合成图已知答案自检：
还原红单层误差为 0）。

下面每条断言要么是合成已知答案，要么是在原图上量出来的。
"""

import json
import math
from functools import lru_cache

import pytest
from PIL import Image

from tests.conftest import needs_face_font
from tools import bake_mask
from tools.bake_sysgim_glow import _pm
from tools.bake_sysgim_note import DATA, SPEC, SRC

ROWS = {json.loads(l)["file"]: json.loads(l)
        for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()}
FIVE = sorted(ROWS)


@lru_cache(maxsize=None)
def _img(name):
    return Image.open(SRC / f"{name}.png").convert("RGBA")


@lru_cache(maxsize=None)
def _plan(name):
    r = ROWS[name]
    return bake_mask.plan_geo(_img(name), [tuple(r["box"])], r["geo"])


@lru_cache(maxsize=None)
def _product(name):
    return Image.open(SPEC.out / f"{name}.png").convert("RGBA")


# ── 合成已知答案 ──────────────────────────────────────────────────────────

def _synth():
    """60×40 透明底：上行「绿晕白字」（保留），下行「黑晕白字」（要换，晕与
    上层的晕**重叠**——真实五张两层只隔 4px，减法只在这种图上发生）。

    返回 (im, red_layer, black_layer, geo)。红/黑两层单独存着，作减法的真值。
    """
    W, H = 60, 40
    red = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rp, bp = red.load(), black.load()
    # 保留层字芯：横杠 (10..25, 6)
    for x in range(10, 26):
        rp[x, 6] = (255, 255, 255, 255)
    # 要换层字芯：横杠 (18..45, 13)
    for x in range(18, 46):
        bp[x, 13] = (255, 255, 255, 255)

    def glow(img, core, colour, radius, peak):
        p = img.load()
        for y in range(H):
            for x in range(W):
                d = min(math.hypot(x - cx, y - cy) for cx, cy in core)
                if d <= 0.5:
                    continue
                if d <= radius:
                    a = round(peak * (1 - d / radius))
                    p[x, y] = (colour[0], colour[1], colour[2],
                               max(p[x, y][3], a))

    core_red = [(x, 6) for x in range(10, 26)]
    core_blk = [(x, 13) for x in range(18, 46)]
    glow(red, core_red, (1, 254, 1), 9, 160)          # 绿晕（保留层）
    glow(black, core_blk, (0, 0, 0), 4, 140)          # 黑晕（要换层）
    im = Image.alpha_composite(red, black)            # 黑在上——与实测一致
    geo = {
        "keep": [{"box": [0, 0, W, 10], "r": 10, "kind": "white", "death": 12}],
        "r_old": 5, "bg": [255, 255, 255, 0], "photo": False,
        "glow_floor": 12, "ghost_subtract": True,
    }
    return im, red, black, geo


def test_synth_subtract_recovers_red_layer_exactly():
    """已知答案：减法后保留层足迹内的像素应等于红单层。

    在**预乘空间**比较（容差 2.5）：RGB 绝对容差会被低 alpha 处的 unpm 放大
    （α=18 时 ×13），失真；pm 空间里量化往返 ≤1，逻辑错误（非预乘直接除）
    的偏差 ≥8，分得开。
    """
    im, red, black, geo = _synth()
    mp = bake_mask.plan_geo(im, [[18, 10, 46, 18]], geo)
    out = im.copy()
    bake_mask.apply(out, mp)
    rp, op = red.load(), out.load()
    bad = []
    for (x, y), c in mp.post_writes.items():
        want, got = _pm(rp[x, y]), _pm(op[x, y])
        if any(abs(want[i] - got[i]) > 2.5 for i in range(4)):
            bad.append((x, y, rp[x, y], op[x, y]))
    assert mp.post_writes, "合成图上应发生减法"
    assert not bad, f"减法偏离红单层: {bad[:5]}"


def test_synth_black_halo_with_no_red_vanishes():
    """红晕已衰减到 ≈0 的减法像素（黑晕独存）减完后应归透明。"""
    im, red, black, geo = _synth()
    mp = bake_mask.plan_geo(im, [[18, 10, 46, 18]], geo)
    out = im.copy()
    bake_mask.apply(out, mp)
    op, rp = out.load(), red.load()
    zone = [(x, y) for (x, y) in mp.post_writes if rp[x, y][3] <= 8]
    assert zone, "应存在红晕≈0 的减法像素"
    for x, y in zone:
        assert op[x, y][3] <= 14, f"({x},{y}) 黑晕应归零，实测 {op[x, y]}"


def test_synth_protect_and_rects_partition_correctly():
    im, red, black, geo = _synth()
    mp = bake_mask.plan_geo(im, [[18, 10, 46, 18]], geo)
    # 保留层字芯本身一个都不许可写
    for x in range(10, 26):
        assert not mp.can_write(x, 6), "保留层字芯不可写"
    # 换层字芯全部可擦（哪怕在保留层足迹内——豁免规则）
    for x in range(18, 46):
        assert mp.can_write(x, 13), f"换层字芯 ({x},13) 应可擦"


def test_synth_too_small_r_old_raises():
    """r_old 明显小于黑晕半径时，晕尾带自查必须当场炸。"""
    im, _red, _black, geo = _synth()
    geo = dict(geo)
    geo["r_old"] = 1
    with pytest.raises(ValueError, match="r_old"):
        bake_mask.plan_geo(im, [[18, 10, 46, 18]], geo)


# ── 真图上的结构断言 ──────────────────────────────────────────────────────

def test_corpus_is_the_five_leftovers_all_translated():
    assert FIVE == ["sys_12_a", "sys_12_b", "sys_12_c", "sys_2_a", "sys_3_a"]
    for r in ROWS.values():
        assert r["zh"].strip(), f"{r['file']} 未译"
    assert ROWS["sys_12_b"]["zh"] == "时间耗尽"
    assert "时间结束" in ROWS["sys_12_b"]["note"], "备选译文应记在 note 里"


def test_plan_geo_tiles_allowed_region_with_rects():
    """rects 必须精确铺满允许区（不多盖不少盖）——can_write 的语义靠它。"""
    for name in FIVE:
        mp = _plan(name)
        im = _img(name)
        covered = [[False] * im.width for _ in range(im.height)]
        for l, t, r, b in mp.rects:
            for y in range(t, b):
                for x in range(l, r):
                    assert not covered[y][x], f"{name}: 矩形重叠"
                    covered[y][x] = True
        for y in range(im.height):
            for x in range(im.width):
                assert covered[y][x] == mp.writable[y][x], \
                    f"{name}: ({x},{y}) 矩形与允许区不一致"


def test_products_keep_layer_byte_identical():
    for name in FIVE:
        mp = _plan(name)
        hurt = bake_mask.check_keep_intact(_img(name), _product(name), mp,
                                           skip_ink=True)
        assert hurt == 0, f"{name}: 保留层被改动 {hurt} 像素"


def test_products_change_only_inside_mask_region():
    for name in FIVE:
        mp = _plan(name)
        bad = bake_mask.check_apply_exact(_img(name), _product(name), mp)
        assert not bad, f"{name}: 矩形外越界写入 {bad[:5]}"


def test_real_panels_subtract_hits_the_ghost_zone():
    """两张透明底面板必须发生减法，且 12 系（平底/照片）不发生。"""
    for name in ("sys_2_a", "sys_3_a"):
        assert len(_plan(name).post_writes) > 50, f"{name}: 幽灵晕减法没生效"
    for name in ("sys_12_a", "sys_12_b", "sys_12_c"):
        assert not _plan(name).post_writes


def test_products_subtracted_pixels_match_plan():
    """成品与计划一致：减法表里的像素必须等于表里的值（防 apply 漏写）。"""
    for name in ("sys_2_a", "sys_3_a"):
        dp = _product(name).load()
        for (x, y), c in _plan(name).post_writes.items():
            assert dp[x, y] == c, f"{name}: ({x},{y}) 减法未落盘"


@needs_face_font("sysgim")
def test_products_rendered_chinese_present():
    """成品里必须有新墨（不能只擦不写）。"""
    for name in FIVE:
        src, dst = _img(name).load(), _product(name).load()
        W, H = _img(name).size
        diff = sum(1 for y in range(H) for x in range(W)
                   if src[x, y] != dst[x, y])
        assert diff > 200, f"{name}: 成品与原图差异仅 {diff} 像素，像是没渲染"
