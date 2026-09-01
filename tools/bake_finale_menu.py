#!/usr/bin/env python3
"""主菜单谢幕项 title_14_a 底图拼接——encore 字形移植（无小注版）。

从 title_13_a（Section 7）与 title_02_a（Prologue）的同字号小写字库中
等大剪贴 e/n/c/o/r 字形，拼出上（暗态）下（亮态）双态的大词 `encore`。
**不烤中文小注**——2026-09-01 用户裁定：主菜单 12 项定稿为"只留英文大词、
小注只擦不写"（裁定 E22：注芯像素预算下中文糊成一团，留白比糊干净），
encore 项与全族同体例。早期的『- 谢幕 -』/『- 安可 -』A/B 与捐赠注管线
随该裁定作废（git 历史可查）。

画布 117×68 ＝ title_13_a 模板实尺寸——gimcodec 模板回填**钉死尺寸**
（encode_from_pil 尺寸不符即拒），直接产模板同尺寸省去 pad；墨迹居中，
摆位 x=194 时墨心 ≈252 与主列墨迹中轴对齐（且与 section7 同 x 左缘对齐）。

字形盒与词行窗口来自逐列/逐行强像素（alpha>200）投影实测（GLYPHS /
WINDOWS / BASELINE 表）；r 取 Prologue 的 ro 连段左半、切割列钉死在
[18,24)（x17/24-25 分别是 P 升部与 o 的横向光晕渗入列，一并舍弃）；
盒收窄后 P 顶部渗入已实测为零（y0-5 干净），r 的头尾光晕（up y6-7、lo y57-58）
完整保留——早先窗口裁掉光晕尾曾造成 r 底缘生硬、被目检读作"色差"。lower 态一律裁
**词行窗口**而非整半区——半区里还躺着小注行，整裁会混入注的像素。
输出：docs/finale/assets/title_14_a.png（源=成品）＋ build/finale_menu/ 成品与 3x 目检图。
不触碰 png/sysgim/ 原件。
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from PIL import Image

SRC13 = REPO / "png" / "sysgim" / "title_13_a.png"   # Section 7
SRC02 = REPO / "png" / "sysgim" / "title_02_a.png"   # Prologue（r 的捐赠源——
# library 实测 x-height 仅 9px 与 Section7 的 13px 不同档，plan §5 的"等大"在 r 上失实；
# Prologue 与 Section7 同字号（x-height 13、上半基线同为 20），r 取其 ro 连段左半）
OUT_SRC = REPO / "docs" / "finale" / "assets" / "title_14_a.png"
OUT_DBG = REPO / "build" / "finale_menu"

W, H, SPLIT = 117, 68, 34          # ＝title_13_a 模板尺寸（偶数高，分界 y=34）
KERN = 2                            # 原词相邻字形段间距实测 ≈2px

# 字形盒 (src, x0, x1)。title_13 上/下半词芯 x 段实测一致。
GLYPHS = {
    "e": ("13", 16, 27),
    "n": ("13", 70, 81),
    "c": ("13", 29, 39),
    "o": ("13", 55, 67),
    "r": ("02", 18, 24),
}
WORD = "encore"

# 词行裁剪窗口 (src,state) -> (y0,y1)：含光晕、不含小注行。
WINDOWS = {
    ("13", "up"): (0, 24),  ("02", "up"): (5, 24),
    ("13", "lo"): (32, 56), ("02", "lo"): (42, 59),
}
# 词芯强像素基线（bottom，实测）：贴图时平移对齐，抵消源图排版差。
# 基线＝该源该态 x-height 字形的 strong 底行**逐一实测**（t13 用 e/n，t02 用 r；
# 平底与圆底字形在本字体同底，n 与 e 实测同为 53/20）。曾按 plan 的"词 y[35,55]"
# 取 t13 lo=55，比实测低 2px，导致 r 相对 t13 群下沉 2px——用户目检抓出的错位即此。
BASELINE = {("13", "up"): 20, ("02", "up"): 20,
            ("13", "lo"): 53, ("02", "lo"): 56}
# TARGET lo=53 使 t13 群 y_paste=32＝半区内原位（两图同 68 高、同 34 分界），
# r 按同底对齐；up 同理原位。
TARGET_BASE = {"up": 20, "lo": 53}


def main():
    imgs = {"13": Image.open(SRC13).convert("RGBA"),
            "02": Image.open(SRC02).convert("RGBA")}
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    word_w = sum(GLYPHS[ch][2] - GLYPHS[ch][1] for ch in WORD) + KERN * (len(WORD) - 1)
    x_start = (W - word_w) // 2
    print(f"word width={word_w}, x_start={x_start}")

    for state in ("up", "lo"):
        x = x_start
        for ch in WORD:
            src, x0, x1 = GLYPHS[ch]
            y0, y1 = WINDOWS[(src, state)]
            tile = imgs[src].crop((x0, y0, x1, y1))
            y_paste = TARGET_BASE[state] - BASELINE[(src, state)] + y0
            canvas.alpha_composite(tile, (x, y_paste))
            x += tile.size[0] + KERN

    OUT_SRC.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT_SRC)
    OUT_DBG.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT_SRC, OUT_DBG / "title_14_a.png")   # 成品＝源（无烤注步）
    canvas.resize((W * 3, H * 3), Image.NEAREST).save(OUT_DBG / "_src_3x.png")
    ref = imgs["13"]
    combo = Image.new("RGBA", ((ref.size[0] + W + 12) * 3, max(ref.size[1], H) * 3), (24, 24, 24, 255))
    combo.alpha_composite(ref.resize((ref.size[0] * 3, ref.size[1] * 3), Image.NEAREST), (0, 0))
    combo.alpha_composite(canvas.resize((W * 3, H * 3), Image.NEAREST), ((ref.size[0] + 12) * 3, 0))
    combo.save(OUT_DBG / "_final_compare_3x.png")
    print(f"final -> {OUT_SRC} ＋ {OUT_DBG}/title_14_a.png")


if __name__ == "__main__":
    main()
