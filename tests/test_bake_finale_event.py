"""tools/bake_finale_event.py：鲸客人 CG 变体——纵横比中心裁剪、降采样到模板尺寸、
预量化不超过 256 色且调色板为 RGBA 形态（进包时走 quantize_for_template 的无损路径）。"""
from PIL import Image

from tools import bake_finale_event as bfe


def _gradient(w: int, h: int) -> Image.Image:
    """横向色相渐变 + 纵向亮度渐变：颜色数远超 256，逼真地触发量化。"""
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x * 255 // max(w - 1, 1), y * 255 // max(h - 1, 1), (x + y) % 256)
    return im


def test_crop_to_aspect_keeps_near_ratio_and_crops_far_ratio():
    near = Image.new("RGB", (1665, 944))            # 源图实际尺寸：只差万分之五，原样返回
    assert bfe.crop_to_aspect(near).size == (1665, 944)
    wide = Image.new("RGB", (2000, 500))
    out = bfe.crop_to_aspect(wide)
    assert out.size[1] == 500 and abs(out.size[0] / 500 - 480 / 272) < 1e-2
    tall = Image.new("RGB", (480, 1000))
    out = bfe.crop_to_aspect(tall)
    assert out.size[0] == 480 and abs(480 / out.size[1] - 480 / 272) < 1e-2


def test_downsample_hits_template_size():
    out = bfe.downsample(_gradient(1665, 944))
    assert out.size == (480, 272) and out.mode == "RGB"


def test_quantize_best_returns_p_image_within_palette_and_rgba_palette():
    mid = bfe.downsample(_gradient(1665, 944))
    q, method, err = bfe.quantize_best(mid)
    assert method in bfe.METHODS and err >= 0
    final = bfe.to_rgba_palette(q)
    assert final.mode == "P" and final.size == (480, 272)
    colors = final.convert("RGBA").getcolors(256)
    assert colors is not None and len(colors) <= 256
    assert all(rgba[3] == 255 for _n, rgba in colors)


def test_quantize_best_is_lossless_when_already_few_colours():
    flat = Image.new("RGB", (480, 272), (200, 30, 30))
    flat.paste((30, 30, 200), (0, 0, 240, 272))
    q, _m, err = bfe.quantize_best(flat)
    assert err == 0
    assert set(c for _n, c in q.convert("RGB").getcolors(4)) == {(200, 30, 30), (30, 30, 200)}
