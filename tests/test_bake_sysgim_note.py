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

# 按文件聚合（sys_1_i 有三行；geo 放在 row 0）
ROWS = {}
for _l in DATA.read_text(encoding="utf-8").splitlines():
    if _l.strip():
        _r = json.loads(_l)
        ROWS.setdefault(_r["file"], []).append(_r)
SIX = sorted(ROWS)


@lru_cache(maxsize=None)
def _img(name):
    return Image.open(SRC / f"{name}.png").convert("RGBA")


@lru_cache(maxsize=None)
def _plan(name):
    rs = ROWS[name]
    return bake_mask.plan_geo(_img(name),
                              [tuple(r["box"]) for r in rs], rs[0]["geo"])


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


def test_synth_hue_aligned_mixed_pixels_purified():
    """色相对齐剥离（2026-08-30 最终语义）：

    黑加进混合只改幅值不改色相，故 pm 方向与晕色一致的像素应被重写为
    **纯晕色**、α＝沿晕色的投影幅值（＝aG·(1−aB)，合成是黑在上时按此
    尊重事实；黑在下则恰好精确）。无彩暗像素归透明；亮灰按 d_old 归属。
    """
    im, red, black, geo = _synth()
    geo["glow_rgb"] = [1, 254, 1]
    mp = bake_mask.plan_geo(im, [[18, 10, 46, 18]], geo)
    out = im.copy()
    bake_mask.apply(out, mp)
    op, ip = out.load(), im.load()
    assert mp.post_writes, "合成图上应有清理写入"
    n_clear = n_purify = 0
    for (x, y), c in mp.post_writes.items():
        p = ip[x, y]
        if max(p[:3]) - min(p[:3]) <= 24:
            assert c == (0, 0, 0, 0), f"({x},{y}) 无彩像素应清成透明，实测 {c}"
            n_clear += 1
        else:
            # 混合像素：色相必须提纯到晕色，α 介于 aG·(1−aB) 与 aG 之间
            assert c[:3] == (1, 254, 1), f"({x},{y}) 应提纯为晕色，实测 {c}"
            aG = p[1] * p[3] / 255.0 / (254 / 255.0)
            aB = _pm(black.load()[x, y])[3] / 255.0
            assert aG * (1 - aB) - 2 <= c[3] <= aG + 2, \
                f"({x},{y}) 剥黑后 α={c[3]}，应落在 [{aG * (1 - aB):.0f},{aG:.0f}]"
            n_purify += 1
    assert n_clear and n_purify, f"两类都应发生: 清透明 {n_clear} / 剥黑 {n_purify}"
    # 字母边缘的白晕过渡（色相偏离）不许动：合成里没有，但纯晕像素不许变
    for (x, y), c in mp.post_writes.items():
        assert op[x, y][3] <= ip[x, y][3] + 2, f"({x},{y}) α 不许变大"


def test_synth_black_halo_with_no_red_vanishes():
    """黑晕独存（无彩暗）的清理像素减完后应归透明。"""
    im, red, black, geo = _synth()
    geo["glow_rgb"] = [1, 254, 1]
    mp = bake_mask.plan_geo(im, [[18, 10, 46, 18]], geo)
    out = im.copy()
    bake_mask.apply(out, mp)
    op, ip = out.load(), im.load()
    zone = [(x, y) for (x, y) in mp.post_writes
            if max(ip[x, y][:3]) <= 120 and ip[x, y][3] >= 40
            and max(ip[x, y][:3]) - min(ip[x, y][:3]) <= 24]
    assert zone, "应存在无彩暗（黑晕本体）的清理像素"
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
    assert SIX == ["sys_12_a", "sys_12_b", "sys_12_c", "sys_1_i", "sys_2_a", "sys_3_a"]
    assert len(ROWS["sys_1_i"]) == 3 and all(r["zh"].strip() for r in ROWS["sys_1_i"])
    assert ROWS["sys_1_i"][0]["geo"]["keep"][0]["hard"] is True
    for rs in ROWS.values():
        for r in rs:
            assert r["zh"].strip(), f"{r['file']} row{r['row']} 未译"
    assert ROWS["sys_12_b"][0]["zh"] == "时间耗尽"
    assert "时间结束" in ROWS["sys_12_b"][0]["note"], "备选译文应记在 note 里"


def test_plan_geo_tiles_allowed_region_with_rects():
    """rects 必须精确铺满允许区（不多盖不少盖）——can_write 的语义靠它。"""
    for name in SIX:
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
    for name in SIX:
        mp = _plan(name)
        hurt = bake_mask.check_keep_intact(_img(name), _product(name), mp,
                                           skip_ink=True)
        assert hurt == 0, f"{name}: 保留层被改动 {hurt} 像素"


def test_products_change_only_inside_mask_region():
    for name in SIX:
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
    """成品与计划一致：**写带之外**的清理像素必须等于计划值。

    写带内的清理像素可能随后被新字的晕按 farther-wins 合法覆盖（新晕压旧晕，
    与原图行为一致），故不在断言之列。
    """
    for name in ("sys_2_a", "sys_3_a"):
        mp = _plan(name)
        dp = _product(name).load()
        checked = 0
        for (x, y), c in mp.post_writes.items():
            if mp.write_band is not None and mp.write_band[y][x]:
                continue
            assert dp[x, y] == c, f"{name}: ({x},{y}) 清理未落盘"
            checked += 1
        assert checked, f"{name}: 写带外竟无清理像素？"


@needs_face_font("sysgim")
def test_products_rendered_chinese_present():
    """成品里必须有新墨（不能只擦不写）。"""
    for name in SIX:
        src, dst = _img(name).load(), _product(name).load()
        W, H = _img(name).size
        diff = sum(1 for y in range(H) for x in range(W)
                   if src[x, y] != dst[x, y])
        assert diff > 200, f"{name}: 成品与原图差异仅 {diff} 像素，像是没渲染"


@needs_face_font("sysgim")
def test_products_alignment_matches_reference():
    """对齐回归（2026-08-30 用户反馈）：

    - 12 系：新墨中心与英文行（含两侧 `-`）bbox 中心差 ≤1px——原假名块自身
      偏右 3.5–5.5px，照搬其重心会把偏差带进成品；
    - 2a/3a：新墨右缘与大标题芯右缘差 ≤1px；
    - sys_1_i：左对齐——行1 新墨左缘与原棕芯左缘差 ≤1px。
    """
    for name in SIX:
        r0 = ROWS[name][0]
        im, dst = _img(name), _product(name)
        sp, dp = im.load(), dst.load()
        if name == "sys_1_i":
            oldl = min(x for y in range(8, 34) for x in range(30, im.width)
                       if sp[x, y][3] >= 150 and sp[x, y][0] >= 100
                       and sp[x, y][1] - sp[x, y][2] >= 30)
            newl = min(x for y in range(8, 34) for x in range(30, im.width)
                       if dp[x, y][3] >= 150 and dp[x, y][0] >= 100
                       and dp[x, y][1] - dp[x, y][2] >= 30)
            assert abs(newl - oldl) <= 1, f"{name}: 左缘 {oldl}→{newl}"
            continue
        kb = r0["geo"]["keep"][0]["box"]
        kpts = [(x, y) for y in range(kb[1], kb[3]) for x in range(kb[0], kb[2])
                if sp[x, y][3] >= 217 and min(sp[x, y][:3]) >= 150]
        kx0, kx1 = min(p[0] for p in kpts), max(p[0] for p in kpts)
        ylo, yhi = (0, 22) if name.startswith("sys_12") else (25, 37)
        npts = [(x, y) for y in range(ylo, yhi) for x in range(im.width)
                if dp[x, y][3] >= 217 and min(dp[x, y][:3]) >= 150]
        nx0, nx1 = min(p[0] for p in npts), max(p[0] for p in npts)
        if name.startswith("sys_12"):
            delta = (nx0 + nx1 + 1) / 2 - (kx0 + kx1 + 1) / 2
            assert abs(delta) <= 1.0, f"{name}: 居中偏 {delta:+.1f}px"
        else:
            assert abs(nx1 - kx1) <= 1, f"{name}: 右缘差 {nx1 - kx1:+d}px"


@needs_face_font("sysgim")
def test_panel_annotations_have_visible_dashes():
    """面板两张的小注两侧必须有**看得见**的短线（α≥150 的实心像素）。

    ASCII '-' 在 8–9px 字号只有 3×1px 且大半发灰（3a 实测 α12–31，观感＝
    没有），已改全角 '－'（6×1 实心）。
    """
    for name in ("sys_2_a", "sys_3_a"):
        dp = _product(name).load()
        npts = [(x, y) for y in range(25, 37) for x in range(_img(name).width)
                if dp[x, y][3] >= 217 and min(dp[x, y][:3]) >= 150]
        nx0, nx1 = min(p[0] for p in npts), max(p[0] for p in npts)
        for tag, a, b in (("左", nx0, nx0 + 8), ("右", nx1 - 8, nx1)):
            solid = [1 for y in range(25, 37) for x in range(a, b + 1)
                     if dp[x, y][3] >= 150]
            assert solid, f"{name}: {tag}短线不可见"


@needs_face_font("sysgim")
def test_sys_2_a_glyph_tops_not_clipped():
    """写带回归（2026-08-30 用户反馈）：新字顶行不许被保护区拦成「削平」。

    汉字比假名高约 1px 且笔画位置不同，顶行若只豁免「旧字芯像素」，没恰好
    落在旧芯上的墨迹全被拦（当时 128 个像素、含 (249,249,249,249) 的实心白）。
    重放合并、断言**实心墨**（贴片 mask>200）不再有被拦的。
    """
    import dataclasses

    from tools.bake_para_glow import (_core_heights, choose_size, measure_para,
                                      render_glow, _core_mask)
    from tools.bake_sysgim_glow import MAX_TAIL_DEV, _pm, measure_glow

    name = "sys_2_a"
    meta = ROWS[name][0]
    im = _img(name)
    mp = _plan(name)
    box = tuple(meta["box"])
    geo = meta["geo"]
    g = measure_glow(im, box, ignore=mp.protect_at, core_of=mp.is_ink_core,
                     bg=mp.bg, probe_d=geo.get("probe_d", bake_mask.GLOW_PROBE_D),
                     tail_tol=geo.get("tail_tol", MAX_TAIL_DEV))
    if geo.get("r_old") is not None:
        bgpm = _pm(g.bg)
        g.ring = [bgpm if k >= geo["r_old"] else ring
                  for k, ring in enumerate(g.ring, 1)]
    zh = meta["zh"]
    para = measure_para(im, box, g, meta["jp"].split("\n"))
    para = dataclasses.replace(para, heights=_core_heights(im, box, para))
    size = choose_size([zh], para, box, name, "sysgim")[0][0]
    cbb = _core_mask(zh, size, name, "sysgim").getbbox()
    left = round(((para.ink_x0 + para.ink_x1) / 2) - (cbb[0] + cbb[2]) / 2)
    gy = para.tops[0] + (para.heights[0] - (cbb[3] - cbb[1])) // 2
    ox, oy = left - cbb[0], gy - cbb[1]
    tile = render_glow(zh, size, g, name, "sysgim")
    mask = _core_mask(zh, size, name, "sysgim").load()
    mpaste = mask
    blocked_solid = []
    for ty in range(tile.height):
        for tx in range(tile.width):
            if mpaste[tx, ty] <= 200:
                continue
            xx, yy = ox + tx, oy + ty
            if 0 <= xx < im.width and 0 <= yy < im.height \
                    and not mp.can_write(xx, yy):
                blocked_solid.append((xx, yy))
    assert not blocked_solid, \
        f"实心墨仍被拦 {len(blocked_solid)} 个: {blocked_solid[:8]}"
