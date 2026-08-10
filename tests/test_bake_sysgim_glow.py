"""发光字族的测试。

承重假设只有一条：**发光只依赖「到字芯的距离」**。除了正向断言，这里给它配了
两样东西——一个用原图字芯回放模型的比对（`verify_model`），和一组变异：
把判据拿掉，结果必须变。
"""

from __future__ import annotations

import pytest
from PIL import Image

from tools import bake_sysgim_glow as G
from tools import check_ui_terms as T


def test_glow_ring_decays_monotonically():
    """外发光按构造是单调衰减的——这是整个模型成立的前提。"""
    im = Image.open(G.SYSGIM / "sys_5_a.png").convert("RGBA")
    a = [r[3] for r in G.measure_glow(im, (0, 0, 268, 25)).ring[:6]]
    assert all(a[i] >= a[i + 1] for i in range(5)), a
    assert a[0] > 100 and a[5] < 20


def test_glow_colour_is_stable_in_the_plateau():
    """去掉 alpha 后的发光**色相**应当基本不变；若各向异性，这里就会散开。

    环存的是预乘值，随距离整体变淡是正常的；要看的是「变淡之后还是不是同一个颜色」，
    所以先按各自的 alpha 还原再比。
    """
    im = Image.open(G.SYSGIM / "sys_5_a.png").convert("RGBA")
    ring = G.measure_glow(im, (0, 0, 268, 25)).ring
    rgbs = [G._unpm(r)[:3] for r in ring[1:4]]
    for ch in range(3):
        vals = [c[ch] for c in rgbs]
        assert max(vals) - min(vals) < 30, rgbs


def test_no_glow_row_is_detected():
    """`sys_5_i` 第二行是纯白小字，没有晕——套环模型会糊出一圈假的。"""
    im = Image.open(G.SYSGIM / "sys_5_i.png").convert("RGBA")
    assert not any(a for *_, a in G.measure_glow(im, (0, 31, 280, 50)).ring)
    assert any(a for *_, a in G.measure_glow(im, (0, 0, 280, 31)).ring)


def test_monotonicity_is_what_separates_them():
    """变异自检：只看浓度不看形状，就会把无发光那行误判成有发光。

    那一行 d=1..5 的 alpha 是 120/76/111/128/133——浓度足够，但根本不衰减。
    """
    im = Image.open(G.SYSGIM / "sys_5_i.png").convert("RGBA")
    l, t, r, b = 0, 31, 280, 50
    px = im.load()
    peak = max(px[x, y][3] for y in range(t, b) for x in range(l, r) if px[x, y][3] > 0)
    core = [[px[l + x, t + y][3] >= peak * G.CORE_ALPHA_RATIO for x in range(r - l)] for y in range(b - t)]
    d = G._dist_field(core, r - l, b - t)
    head = []
    for dist in range(1, 6):
        vals = [px[l + x, t + y][3] for y in range(b - t) for x in range(r - l)
                if d[y][x] == dist and px[l + x, t + y][3] > 0]
        head.append(round(sum(vals) / len(vals)) if vals else 0)
    assert head[G.GLOW_PROBE_D - 1] >= G.GLOW_TAIL_MIN_A, "浓度判据在这行是过关的"
    assert not all(head[i] >= head[i + 1] for i in range(4)), "而形状判据不过关——差别就在这"


@pytest.mark.parametrize("name", ["sys_5_a", "sys_5_c", "sys_5_f", "sys_6_b", "sys_13_a"])
def test_model_reproduces_the_original(name):
    """拿原图自己的字芯回放模型，平均偏差要小。各向异性的光会在这里露馅。"""
    rows = G.load_text()[name]
    for (mx, mean), meta in zip(G.verify_model(name, [tuple(r["box"]) for r in rows]), rows):
        if mx < 0:
            continue
        assert mean < 25, f"{name} 行{meta['row']} 平均偏差 {mean}"


def test_deferred_files_are_not_rendered():
    """暂缓的图不能悄悄渲染出来。"""
    text = G.load_text()
    assert "sys_1_i" not in text


@pytest.mark.parametrize(
    "name,box,bg",
    [
        ("sys_5_a", (0, 0, 268, 25), (255, 255, 255, 0)),   # 透明底
        ("sys_2_b", (0, 0, 83, 19), (0, 0, 0, 179)),        # 半透明暗面板
        ("sys_11_a", (0, 0, 480, 23), (0, 0, 0, 179)),      # 半透明黑带
        ("autosave", (0, 90, 480, 115), (0, 0, 0, 255)),    # 不透明黑
        ("sys_1_f", (0, 54, 480, 78), (245, 236, 226, 255)),  # 不透明米黄
    ],
)
def test_background_is_measured_not_assumed(name, box, bg):
    """同一个模型要能处理透明底与不透明底——这正是「相对底色」推广的全部意义。"""
    assert G.measure_glow(Image.open(G.SYSGIM / f"{name}.png").convert("RGBA"), box).bg == bg


def test_background_comes_from_the_border_not_the_mode():
    """字密的盒里全盒众数会把**文字**当成底。

    `sys_2_b` 行 3（亮态「あらすじ作成済」）几乎填满 19px 的行，白像素多过背景；
    取全盒众数会得到 (255,255,255,255)，字芯与底整个反过来。
    """
    from collections import Counter

    im = Image.open(G.SYSGIM / "sys_2_b.png").convert("RGBA")
    px = im.load()
    box = (0, 57, 83, 76)
    whole = Counter(
        px[x, y] for y in range(box[1], box[3]) for x in range(box[0], box[2])
    ).most_common(1)[0][0]
    assert whole == (255, 255, 255, 255), "前提变了：这一行不再是字多过底"
    assert G.measure_glow(im, box).bg == (0, 0, 0, 179)


def test_no_flat_background_is_refused():
    """底是渐变而非单一色时，环的远端收不回去——模型的前提不成立，必须拒绝。

    这条验的是判据本身有没有牙：占比与倍数都量不出「底是不是唯一」
    （试过两版都被真实图例推翻），最后靠的就是这条收敛检查。
    """
    im = Image.new("RGBA", (60, 40))
    px = im.load()
    for y in range(40):
        for x in range(60):
            px[x, y] = (x * 4, 0, 0, 255)  # 横向渐变，没有平底
    for y in range(18, 22):
        for x in range(28, 32):
            px[x, y] = (255, 255, 255, 255)  # 一小块「字」
    with pytest.raises(ValueError, match="仍离底"):
        G.measure_glow(im, (0, 0, 60, 40))


def test_deferred_rows_still_carry_their_translation():
    """暂缓不等于没做——译文照记，理由照写。"""
    import json

    rows = [json.loads(l) for l in G.DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    dfr = [r for r in rows if r.get("deferred")]
    assert len(dfr) == 3  # sys_1_i 的三行
    assert all(r["zh"].strip() and "暂缓" in r["note"] for r in dfr)


def test_baked_files_touch_nothing_they_shouldnt():
    text = G.load_text()
    for name in sorted(text):
        _, bad = G.bake_file(name, text[name], [])
        assert bad == 0, name


def test_translations_pass_the_term_gate():
    v = T.run([G.DATA])
    assert v == [], "\n".join(str(x) for x in v)
