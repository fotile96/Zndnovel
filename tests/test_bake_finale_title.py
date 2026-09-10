"""tools/bake_finale_title.py：中文题名降采样——预乘 alpha 无暗边、等比贴高居中、
入库成品与模板同尺寸且可由源图再生。"""
from pathlib import Path

import pytest
from PIL import Image

from tools import bake_finale_title as bft

REPO = Path(__file__).resolve().parents[1]


def _mse(a: Image.Image, b: Image.Image) -> float:
    pa, pb = a.convert("RGBA").getdata(), b.convert("RGBA").getdata()
    n = len(pa) * 4
    return sum((x - y) ** 2 for p, q in zip(pa, pb) for x, y in zip(p, q)) / n


def test_premultiplied_resize_keeps_edge_colour_clean():
    """左半不透明白、右半全透明黑，缩 8 倍：凡 alpha>0 的像素 RGB 仍是白——
    直 alpha 缩放会把透明黑混进边缘（灰边），预乘路径不会。"""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for y in range(64):
        for x in range(32):
            im.putpixel((x, y), (255, 255, 255, 255))
    out = bft.premultiplied_resize(im, (8, 8))
    assert out.size == (8, 8)
    seen_partial = False
    for px in out.getdata():
        r, g, b, a = px
        if a > 0:
            assert min(r, g, b) >= 253, px
        if 0 < a < 255:
            seen_partial = True
        if a == 0:
            assert (r, g, b) == (0, 0, 0)
    assert seen_partial, "边界列应产生半透明像素（LANCZOS 抗锯齿），否则测试没测到边缘"
    # 对照：逐通道直 alpha 缩放确实会产生灰边——证明上面那条断言不是平凡成立。
    # （Pillow 的 Image.resize 对 RGBA 自己会走 8 位预乘"RGBa"，所以对照必须手工拆通道。）
    naive = Image.merge("RGBA", [ch.resize((8, 8), Image.LANCZOS) for ch in im.split()])
    assert any(a > 0 and min(r, g, b) < 200 for r, g, b, a in naive.getdata())


def test_fit_logo_crops_margin_fills_height_and_centres():
    """透明留白很大的源：内容盒等比放到贴满画布高，水平居中，留白不占尺寸。"""
    src = Image.new("RGBA", (600, 300), (0, 0, 0, 0))
    for y in range(100, 200):          # 内容 400x100，纵横比 4:1
        for x in range(100, 500):
            src.putpixel((x, y), (10, 20, 200, 255))
    out = bft.fit_logo(src, (405, 89))
    assert out.size == (405, 89)
    box = bft.content_box(out, 128)
    assert box[1] == 0 and box[3] == 89                    # 贴满高
    width = box[2] - box[0]
    assert abs(width - round(400 * 89 / 100)) <= 1          # 等比：356
    assert abs(box[0] - (405 - box[2])) <= 1                # 居中


def test_fit_logo_falls_back_to_width_when_source_is_wide():
    src = Image.new("RGBA", (1000, 100), (0, 0, 0, 0))
    for y in range(10, 90):
        for x in range(0, 1000):
            src.putpixel((x, y), (0, 0, 0, 255))
    out = bft.fit_logo(src, (405, 89))
    box = bft.content_box(out, 128)
    assert box[0] == 0 and box[2] == 405
    assert box[3] - box[1] < 89


def test_committed_product_is_template_sized_and_soft_edged():
    """入库成品 = 模板尺寸（gimcodec 回填钉死尺寸），且保留了半透明光晕（不是二值 alpha）。"""
    prod = Image.open(bft.OUT_SRC)
    tpl = Image.open(bft.TEMPLATE_PNG)
    assert prod.size == tpl.size == (bft.W, bft.H)
    alphas = {a for _n, a in prod.convert("RGBA").getchannel("A").getcolors(256)}
    assert len(alphas) > 32, "alpha 层次太少——降采样丢了光晕渐变"
    assert 0 in alphas, "画布四周应是全透明（居中留白）"


def test_committed_product_regenerates_from_committed_source():
    """『源=成品』：成品必须是本工具从入库源图算出来的，手改成品会被抓住（容差 ≤2/通道）。"""
    if not bft.SRC.exists():
        pytest.skip("缺源图")
    regen = bft.fit_logo(Image.open(bft.SRC))
    prod = Image.open(bft.OUT_SRC).convert("RGBA")
    assert regen.size == prod.size
    diff = max(abs(x - y) for p, q in zip(regen.getdata(), prod.getdata()) for x, y in zip(p, q))
    assert diff <= 2, f"再生成品与入库成品最大通道差 {diff}"


def test_manifest_routes_face_to_title_template():
    from tools.layers import load_manifest
    new = [list(x) for x in load_manifest()["gim"]["new"]]
    assert [bft.FACE, "sysgim", "sysgim/title_01_a.gim"] in new
