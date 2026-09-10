#!/usr/bin/env python3
"""标题画面中文题名 title_01_c——用户改图降采样到 title_01_a 模板尺寸（405×89）。

来龙去脉：谢幕章首次完整读完后，主菜单的题名 logo 由日文 `sysgim/title_01_a` 换成
中文 `sysgim/title_01_c`（系统旗标 `systemSave.finaleReadFlag`，见 layers/overlays/
finale-read-flag.toml 与 title-logo-zh.toml）。用户 2026-09-11 提供高清源图
docs/finale/assets/title_01_c.src.png（2172×724 RGBA，四周各约 100 px 全透明留白）。
成品必须与 title_01_a **同尺寸**：gimcodec 模板回填钉死尺寸（encode_from_pil 尺寸不符
即拒），而且 snr_mainmenu 的 `layerPosition(logo, 38, 10)` 沿用不动，换图不换版面。

做法：
1. 裁掉 alpha < CROP_ALPHA_MIN 的外圈留白（alpha==1 的散点 402 个，肉眼不可见）；
2. **预乘 alpha 的 LANCZOS 降采样**（float 通道运算）：对直 alpha 图直接缩放会把全透明
   像素的 RGB 混进边缘产生暗边；预乘后缩放、再反预乘，光晕的半透明渐变按原值保留；
3. 高度贴满 89（原 logo 的 alpha>16 行段是 2..86，新图落在同一带），宽度按比例得
   323，水平居中于 405 画布——中文 4 字比日文 7 字短，居中后与原 logo 同中轴（屏幕 x=240）。

源图内容纵横比 3.6:1，title_01_a 是 4.7:1，等比缩放后宽度只占原 logo 的 80%；不做
非等比拉伸。要更满，改源图排版（拉宽字距/缩小上下间距）后重跑本工具即可。

输出：docs/finale/assets/title_01_c.png（源=成品，入库）＋ build/finale_title/title_01_c.png
（进包件：build_disc members 阶段按 [gim].new 以 title_01_a 为模板量化到 256 色编码，
2026-09-11 实测 perceptual MSE ≈10，低于告警阈 15，3 倍目检无可见色阶）＋ QA 图：
_zoom3x.png（原/新/量化后 3 倍并排）、_titlescreen_mock.png（标题画面合成对照，
上=日文原版、下=中文）。不触碰 png/sysgim/ 原件。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageMath

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.bake_out import out_dir  # noqa: E402

FACE = "finale_title"
NAME = "title_01_c"
SRC = REPO / "docs" / "finale" / "assets" / f"{NAME}.src.png"
OUT_SRC = REPO / "docs" / "finale" / "assets" / f"{NAME}.png"
TEMPLATE_PNG = REPO / "png" / "sysgim" / "title_01_a.png"     # 模板尺寸的来源
BG_PNG = REPO / "png" / "bg" / "bg_4_a_0.png"                  # 标题画面底图（mock 用）
MENU_PNG = REPO / "docs" / "finale" / "assets" / "title_14_a.png"
W, H = 405, 89                # = title_01_a 模板尺寸
CROP_ALPHA_MIN = 2            # 外圈裁剪：alpha < 2 视为留白
LOGO_POS = (38, 10)           # snr_mainmenu 里 logo 层的摆位，沿用不动

# 标题画面第 5 形态（卡 140∧144）的菜单项与摆位（layers/overlays/encore-menu.toml）；
# 每张菜单图是上暗下亮双态叠放，mock 取上半（暗态）。
MENU_ITEMS = [("title_03_a", (210, 104)), ("title_04_a", (190, 131)), ("title_13_a", (194, 158)),
              ("title_14_a", (184, 185)), ("title_05_a", (205, 212)), ("title_06_a", (215, 241)),
              ("title_07_a", (48, 145)), ("title_08_a", (330, 142))]


def content_box(im: Image.Image, alpha_min: int = CROP_ALPHA_MIN) -> tuple[int, int, int, int]:
    """alpha ≥ alpha_min 的像素外接盒（left, top, right, bottom）。全透明图报错。"""
    mask = im.convert("RGBA").getchannel("A").point(lambda v: 255 if v >= alpha_min else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("源图没有 alpha ≥ %d 的像素" % alpha_min)
    return box


def premultiplied_resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """RGBA 预乘 alpha → LANCZOS 缩放 → 反预乘。全 float 运算，末尾四舍五入。

    直 alpha 图逐通道 resize 会把透明像素的 RGB（常是黑）混进半透明边缘形成暗边；
    预乘后缩放，边缘颜色只来自可见像素。alpha==0 处 RGB 置 0。
    Pillow 的 Image.resize 对 RGBA 内部也预乘，但走 8 位 "RGBa"：低 alpha 像素的颜色
    在预乘空间只剩几级、反预乘后成块——光晕外沿正是这种像素，故这里全程 float。
    """
    im = im.convert("RGBA")
    r, g, b, a = [ch.convert("F") for ch in im.split()]
    ev = ImageMath.lambda_eval
    a01 = ev(lambda d: d["a"] / 255.0, a=a)
    pre = [ev(lambda d: d["x"] * d["y"], x=c, y=a01).resize(size, Image.LANCZOS) for c in (r, g, b)]
    a2 = a.resize(size, Image.LANCZOS)
    a201 = ev(lambda d: d["a"] / 255.0, a=a2)
    chans = [ev(lambda d: (d["x"] / (d["y"] + (d["y"] == 0))) * (d["y"] > 0) + 0.5,
                x=c, y=a201).convert("L") for c in pre]          # F→L 截断，+0.5 即四舍五入
    chans.append(ev(lambda d: d["a"] + 0.5, a=a2).convert("L"))
    return Image.merge("RGBA", chans)


def fit_logo(src: Image.Image, size: tuple[int, int] = (W, H)) -> Image.Image:
    """裁留白 → 等比缩放贴满画布高（或宽，取先碰到的那边）→ 居中于透明画布。"""
    w, h = size
    content = src.convert("RGBA").crop(content_box(src))
    scale = min(h / content.height, w / content.width)
    tw, th = max(1, round(content.width * scale)), max(1, round(content.height * scale))
    logo = premultiplied_resize(content, (tw, th))
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(logo, ((w - tw) // 2, (h - th) // 2))
    return canvas


def compose_title_mock(logo: Image.Image) -> Image.Image:
    """标题画面合成：底图 + logo@(38,10) + 第 5 形态菜单项暗态。QA 目检用，非引擎渲染。"""
    frame = Image.open(BG_PNG).convert("RGBA")
    frame.alpha_composite(logo, LOGO_POS)
    for name, pos in MENU_ITEMS:
        p = MENU_PNG if name == "title_14_a" else REPO / "png" / "sysgim" / f"{name}.png"
        im = Image.open(p).convert("RGBA")
        frame.alpha_composite(im.crop((0, 0, im.width, im.height // 2)), pos)
    return frame


def main() -> None:
    from tools.build_disc import perceptual_mse, quantize_for_template

    tpl = Image.open(TEMPLATE_PNG)
    assert tpl.size == (W, H), f"title_01_a 模板尺寸变了：{tpl.size}"
    src = Image.open(SRC).convert("RGBA")
    box = content_box(src)
    canvas = fit_logo(src)
    OUT_SRC.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT_SRC)
    dbg = out_dir(FACE)
    dbg.mkdir(parents=True, exist_ok=True)
    canvas.save(dbg / f"{NAME}.png")

    q = quantize_for_template(canvas, 256).convert("RGBA")
    mse = perceptual_mse(q, canvas)
    orig = tpl.convert("RGBA")
    zoom = Image.new("RGBA", (W * 3, (H * 3 + 10) * 3), (60, 60, 60, 255))
    for i, im in enumerate((orig, canvas, q)):
        zoom.paste(im.resize((W * 3, H * 3), Image.NEAREST), (0, i * (H * 3 + 10)))
    zoom.save(dbg / "_zoom3x.png")
    mock = Image.new("RGBA", (480, 272 * 2 + 10), (40, 40, 40, 255))
    mock.paste(compose_title_mock(orig), (0, 0))
    mock.paste(compose_title_mock(canvas), (0, 282))
    mock.resize((mock.width * 2, mock.height * 2), Image.LANCZOS).save(dbg / "_titlescreen_mock.png")
    cw, ch = box[2] - box[0], box[3] - box[1]
    print(f"源 {src.size[0]}x{src.size[1]}，内容盒 {box} = {cw}x{ch}，"
          f"缩放 {min(H / ch, W / cw):.4f} → logo {round(cw * min(H / ch, W / cw))}x{round(ch * min(H / ch, W / cw))}，"
          f"画布 {W}x{H}；量化 256 色 perceptual MSE={mse:.2f}")
    print(f"final -> {OUT_SRC} ＋ {dbg}/{NAME}.png（QA: _zoom3x.png, _titlescreen_mock.png）")


if __name__ == "__main__":
    main()
