#!/usr/bin/env python3
"""`s6s_110` 六条座席按钮的写法对照片 → `build/select_zh/_seat_ab.png`。

**要解决的是什么。** glossary v19 C1 把故事层片假名人名改成罗马音之后，这六条
座席文本从 `Aサクラ Bアヤノ Cユウイチ` 变成 `ASakura BAyano CYuichi`。原文里
`A` 是拉丁、`サクラ` 是片假名，**换字体系本身就是分界**；罗马音化之后两边都是
拉丁，`A` 和 `Sakura` 黏成了一个词。v19 对这一处的原话是：

    全角标号并置（15589「ＡAyano」）暂按机械结果，游戏内实测后再定间隔。

本脚本就是那个「实测」。四行一组，每组一个座席排列：

1. **原图**——`png/select/` 的真图，只读，未经任何处理
2. **现状 18px**——`ASakura BAyano CYuichi`，已入线（`data/select_buttons_zh.jsonl`）
3. **点分隔 16px**——`A.Sakura B.Ayano C.Yuichi`（用户 2026-08-28 点名要看的一版）
4. **全角标号 17px**——`ＡSakura ＢAyano ＣYuichi`，与正文 15589 逐字同形

**为什么各用各的字号。** 这三种写法的宽度不一样，逼出来的档位也不一样，实测：

| 写法 | 18px | 17px | 16px |
|---|---|---|---|
| `ASakura …`（现状） | ✓ | ✓ | ✓ |
| `ＡSakura …`（全角标号） | ✗ | ✓ | ✓ |
| `A.Sakura …`（点分隔） | ✗ | ✗ | ✓ |

框宽 `TEXT_BOX=(15,3,235,23)`。点分隔比现状多出三个半角点，18/17px 下都放不进去，
**16px 是它能落地的最大档**——而现行级联只有 `[18,17]`，故这一版若要真的采用，
需要给 `bake_select.py` 开第三档。这不是本脚本能替你决定的事，所以这里显式写死
字号、只渲染给你看，**不动 `FONT_SIZE_CASCADE`、不写任何入线产物**。

同理，四行的字号是**冻结的历史快照**，不从 `tools.bake_select` 的当前常量读——
那样的话日后级联一改，这张对照片的含义就跟着漂了（`bake_scene_size_ab.py` 因为
同一个理由也是这么做的）。

    uv run python tools/bake_select_seat_ab.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools.bake_select import (
    CELL_H, CELL_W, FONT_PATH, OUT_DIR, TEXT_BOX, _button_image_path,
    bake_button, measure_ink_extent,
)

#: 六条座席按钮与其现役译文（与 data/select_buttons_zh.jsonl 一致）。
SEATS = [
    ("sel_s6s_110_sel_a", "ASakura BAyano CYuichi"),
    ("sel_s6s_110_sel_b", "ASakura BYuichi CAyano"),
    ("sel_s6s_110_sel_c", "AYuichi BAyano CSakura"),
    ("sel_s6s_110_sel_d", "AYuichi BSakura CAyano"),
    ("sel_s6s_110_sel_e", "AAyano BSakura CYuichi"),
    ("sel_s6s_110_sel_f", "AAyano BYuichi CSakura"),
]

#: 冻结的字号快照，理由见模块 docstring。
CURRENT_SIZE = 18
DOT_SIZE = 16
FULLWIDTH_SIZE = 17

SCALE = 4
VARIANT = "on"          # 选中态；未选中态只是配色不同，对间隔判断无影响
LABEL_W = 200


def to_dot(text):
    """`ASakura BAyano CYuichi` → `A.Sakura B.Ayano C.Yuichi`。"""
    return " ".join(w[0] + "." + w[1:] for w in text.split(" "))


def to_fullwidth(text):
    """标号改全角：`ASakura …` → `ＡSakura …`（名字仍是半角拉丁）。"""
    return " ".join(chr(ord(w[0]) + 0xFEE0) + w[1:] for w in text.split(" "))


def _row(button, text, size, label, draw_font):
    """渲染一行：左侧文字标签 + 右侧放大后的按钮。"""
    cell = Image.open(_button_image_path(button, VARIANT)).convert("RGBA")
    if text is not None:
        font = ImageFont.truetype(FONT_PATH, size)
        cell = bake_button(cell, text, font, VARIANT)
        x0, x1, y0, y1 = measure_ink_extent(text, font, TEXT_BOX)
        over = "  越界!" if not (TEXT_BOX[0] <= x0 and x1 <= TEXT_BOX[2]) else ""
        label = f"{label} {size}px  x[{x0},{x1}]{over}"
    big = cell.resize((CELL_W * SCALE, CELL_H * SCALE), Image.NEAREST)
    row = Image.new("RGBA", (LABEL_W + big.width, big.height), (24, 24, 24, 255))
    row.paste(big, (LABEL_W, 0))
    ImageDraw.Draw(row).text((6, big.height // 2 - 7), label, font=draw_font,
                             fill=(230, 230, 230, 255))
    return row


def build():
    draw_font = ImageFont.truetype(FONT_PATH, 13)
    rows = []
    for button, current in SEATS:
        rows.append(_row(button, None, 0, f"{button[-5:]} 原图", draw_font))
        rows.append(_row(button, current, CURRENT_SIZE, "现状", draw_font))
        rows.append(_row(button, to_dot(current), DOT_SIZE, "点分隔", draw_font))
        rows.append(_row(button, to_fullwidth(current), FULLWIDTH_SIZE, "全角标号", draw_font))
        rows.append(None)   # 组间留白

    gap = 10
    height = sum(gap if r is None else r.height for r in rows)
    width = max(r.width for r in rows if r is not None)
    sheet = Image.new("RGBA", (width, height), (16, 16, 16, 255))
    y = 0
    for r in rows:
        if r is None:
            y += gap
            continue
        sheet.paste(r, (0, y))
        y += r.height
    return sheet


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "_seat_ab.png")
    sheet = build()
    sheet.save(out)
    print(f"座席写法对照片 -> {out}  ({sheet.width}x{sheet.height})")
    print(f"  现状     {CURRENT_SIZE}px  {SEATS[0][1]}")
    print(f"  点分隔   {DOT_SIZE}px  {to_dot(SEATS[0][1])}")
    print(f"  全角标号 {FULLWIDTH_SIZE}px  {to_fullwidth(SEATS[0][1])}")
    print("  注：点分隔的 16px 不在现行级联 [18,17] 内，采用则需开第三档。")


if __name__ == "__main__":
    main()
