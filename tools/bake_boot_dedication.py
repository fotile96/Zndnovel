#!/usr/bin/env python3
"""开机链第五卡 IPL03——汉化组署名与献词。纯排版，**代码即源图**，没有外部素材。

来龙去脉：用户 2026-09-21 裁定在正式盘开场、原开发商版权页（sys_1_a）之后、自动存档告知
（autosave）之前加一张卡，两段文字：署名「全称量词汉化组」与献词「谨以此本地化作品献给
盛夏、提前合上书页的年轻生命与被留在故事里的人们」。插入点与节奏在
layers/overlays/boot-dedication.toml（工作层 4，淡入/停留/淡出与前四卡逐帧相同）。

版式沿用厂牌卡 IPL01 的语言，让它读起来是"同一副牌里再加一张"而不是免责声明的续页：
- 黑底；那条蓝→白分隔线**逐像素抄自 IPL01 第 114 行**（x 60..419），不是重画的；
- 署名用 IPL01 大字 "Nippon Ichi Software, Inc." 的淡紫白高光色，左缘同为 x=28，
  墨迹底行同为 y=107（距线 7 px）；
- 献词三行、右对齐到分隔线右端，浅灰小字（首行是动词短语，三个受献者占下两行，
  2026-09-21 用户看过两行/三行 mock 后取三行、15 px）。

⚠ 署名**只写文字，不画 ∀ 记号**：组名是对 Anthropic 的"A"转 180° 的梗，寓意
"用 AI 多做好事少吵架"；画出来就破梗（用户 2026-09-21）。不要在这张卡上加任何标志。

尺寸 480×272 = IPL01 模板实尺寸（gimcodec 模板回填钉死尺寸，encode_from_pil 尺寸不符即拒）。
全图不透明。文字不是直接画上去的：先画成 L 蒙版、把抗锯齿覆盖率**量化到 16 级**、再以纯色
按蒙版贴上——两段文字各只产生 16 种颜色，加分隔线的 91 色与黑，整卡 ≤ 256 色，
build_disc.quantize_for_template 走**精确色板**路径，进包像素与本图逐字节相同（不走 MEDIANCUT：
2026-09-21 实测直接抗锯齿有 526 色，MEDIANCUT 虽只损 MSE 0.03，却把分隔线渐变从 91 阶并成 30 阶）。
16 级覆盖率在 15/22 px 字号上与 256 级目检无差（_quant_3x.png 可核）。

字体按 sysgim 面解析（`ZND_UI_FONT_SYSGIM` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷）。

输出：build/boot_dedication/IPL03.png（进包件：members 阶段按 [gim].new 以 IPL01 为模板编码，
成员名 sysgim/IPL03.gim，按名排序恰落在 IPL02 之后）＋ QA 图：_zoom3x.png（文字区 3 倍）、
_boot_strip.png（五卡按开机顺序并排，免责/自动存档卡取 build/sysgim 的中文面，没烤则取原图）、
_quant_3x.png（量化前后 3 倍并排）。不触碰 png/sysgim/ 原件。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.bake_out import out_dir  # noqa: E402
from tools.ui_font import truetype as ui_truetype  # noqa: E402

FACE = "boot_dedication"          # build/<FACE>/ → manifest [gim].new → sysgim/ 前缀
MEMBER = "IPL03"                  # 成员名（IPL01/IPL02 是厂牌卡，第三张接着编号）
FONT_FACE = "sysgim"              # 字体解析面
TEMPLATE_PNG = REPO / "png" / "sysgim" / "IPL01.png"   # 版式母本：同尺寸、同色板容量、分隔线来源
W, H = 480, 272
BG = (0, 0, 0, 255)

# IPL01 的分隔线：第 114 行，x 60..419（含），蓝 (87,98,254) → 白 (253,252,255) 渐变
RULE_Y, RULE_X0, RULE_X1 = 114, 60, 419

NAME = "全称量词汉化组"
NAME_PX = 22
NAME_FILL = (201, 205, 254, 255)  # IPL01 大字高光色
NAME_LEFT = 28                    # 墨迹左缘，同 IPL01 大字
NAME_BOTTOM = 107                 # 墨迹底行（含），同 IPL01 大字；距分隔线 7 px

DEDICATION = ("谨以此本地化作品献给",
              "盛夏、提前合上书页的年轻生命",
              "与被留在故事里的人们")
DED_PX = 15
DED_FILL = (215, 215, 215, 255)
DED_TOP = RULE_Y + 10             # 首行绘制原点（Pillow 文本原点，墨迹再往下 2–3 px）
DED_LEADING = 6                   # 行距 = 字号 + 6
DED_RIGHT = RULE_X1 + 1           # 墨迹排他右缘 = 分隔线排他右缘（右对齐到线端）

INK_MIN = 40                      # 测量用：max(r,g,b) > 40 计为墨迹（去掉抗锯齿的极淡边）
ALPHA_LEVELS = 16                 # 文字抗锯齿覆盖率的阶数（含 0 与满）；每段文字 = 这么多种颜色


def _posterise(mask: Image.Image, levels: int = ALPHA_LEVELS) -> Image.Image:
    """L 蒙版 0..255 → 均匀 levels 阶（0 与 255 保留）。"""
    step = 255 / (levels - 1)
    return mask.point([round(round(v / step) * step) for v in range(256)])


def _stamp(im: Image.Image, text: str, origin: tuple[int, int], font, fill) -> None:
    """按量化后的字形蒙版把纯色贴到不透明画布上（不经 RGBA 直画——Pillow 在透明底上
    画字会把颜色与覆盖率各衰减一次，边缘发暗）。"""
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).text(origin, text, font=font, fill=255)
    im.paste(fill, mask=_posterise(mask))


def render() -> Image.Image:
    """整张卡（RGBA，不透明）。"""
    tpl = Image.open(TEMPLATE_PNG).convert("RGBA")
    if tpl.size != (W, H):
        raise ValueError(f"模板 {TEMPLATE_PNG.name} 尺寸 {tpl.size} ≠ {(W, H)}")
    im = Image.new("RGBA", (W, H), BG)
    im.paste(tpl.crop((RULE_X0, RULE_Y, RULE_X1 + 1, RULE_Y + 1)), (RULE_X0, RULE_Y))

    fn = ui_truetype(FONT_FACE, NAME_PX)
    b = fn.getbbox(NAME)                                  # (l, t, r, b)，r/b 排他，相对原点
    _stamp(im, NAME, (NAME_LEFT - b[0], NAME_BOTTOM + 1 - b[3]), fn, NAME_FILL)

    fd = ui_truetype(FONT_FACE, DED_PX)
    y = DED_TOP
    for line in DEDICATION:
        b = fd.getbbox(line)
        _stamp(im, line, (DED_RIGHT - b[2], y), fd, DED_FILL)
        y += DED_PX + DED_LEADING
    return im


def ink_box(im: Image.Image, box=None) -> tuple[int, int, int, int] | None:
    """区域内墨迹的外接盒（l, t, r, b；r/b 排他），无墨迹返回 None。"""
    region = im.convert("RGB") if box is None else im.convert("RGB").crop(box)
    # 逐通道取最大值再阈值（convert("L") 是亮度加权，细的蓝字会被压暗漏检）
    r, g, bl = region.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v > INK_MIN else 0)
    bb = mx.getbbox()
    if bb is None or box is None:
        return bb
    return (bb[0] + box[0], bb[1] + box[1], bb[2] + box[0], bb[3] + box[1])


def ink_rows(im: Image.Image, box) -> list[tuple[int, int]]:
    """区域内逐行投影得到的墨迹行段 [(y0, y1 排他), ...]——数献词有几行。"""
    region = im.convert("RGB").crop(box)
    r, g, bl = region.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), bl).point(lambda v: 255 if v > INK_MIN else 0)
    w, h = mx.size
    px = mx.load()
    bands, start = [], None
    for y in range(h):
        has = any(px[x, y] for x in range(w))
        if has and start is None:
            start = y
        elif not has and start is not None:
            bands.append((start + box[1], y + box[1]))
            start = None
    if start is not None:
        bands.append((start + box[1], h + box[1]))
    return bands


def _card_for_strip(name: str) -> Image.Image:
    for cand in (REPO / "build" / "sysgim" / f"{name}.png", REPO / "png" / "sysgim" / f"{name}.png"):
        if cand.exists():
            return Image.open(cand).convert("RGBA")
    raise FileNotFoundError(name)


def main() -> int:
    from tools.build_disc import quantize_for_template   # 进包用同一套量化，QA 看的就是最终像素

    card = render()
    out = out_dir(FACE)
    out.mkdir(parents=True, exist_ok=True)
    card.save(out / f"{MEMBER}.png")

    zone = (20, 70, 460, 200)
    card.crop(zone).resize(((zone[2] - zone[0]) * 3, (zone[3] - zone[1]) * 3), Image.NEAREST) \
        .save(out / "_zoom3x.png")

    q = quantize_for_template(card, 256).convert("RGBA")
    ab = Image.new("RGBA", ((zone[2] - zone[0]) * 3, (zone[3] - zone[1]) * 6 + 12), (40, 40, 40, 255))
    ab.paste(card.crop(zone).resize(((zone[2] - zone[0]) * 3, (zone[3] - zone[1]) * 3), Image.NEAREST), (0, 0))
    ab.paste(q.crop(zone).resize(((zone[2] - zone[0]) * 3, (zone[3] - zone[1]) * 3), Image.NEAREST),
             (0, (zone[3] - zone[1]) * 3 + 12))
    ab.save(out / "_quant_3x.png")
    n = len(card.getdata())
    mse = sum((x - y) ** 2 for p, qq in zip(card.getdata(), q.getdata()) for x, y in zip(p[:3], qq[:3])) / (n * 3)

    strip_cards = [_card_for_strip("IPL01"), _card_for_strip("IPL02"), _card_for_strip("sys_1_a"),
                   card, _card_for_strip("autosave")]
    strip = Image.new("RGBA", (W * 5 + 8 * 4, H), (40, 40, 40, 255))
    for i, c in enumerate(strip_cards):
        strip.paste(c, (i * (W + 8), 0))
    strip.save(out / "_boot_strip.png")

    colours = len(card.getcolors(1 << 20))
    print(f"{MEMBER}: {card.size} 颜色 {colours} 量化后 MSE {mse:.2f}")
    print(f"署名墨迹 {ink_box(card, (0, 0, W, RULE_Y))}  献词行段 {ink_rows(card, (0, RULE_Y + 1, W, H))}")
    print(f"-> {out / (MEMBER + '.png')} ＋ _zoom3x / _quant_3x / _boot_strip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
