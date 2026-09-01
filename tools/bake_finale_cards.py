#!/usr/bin/env python3
"""谢幕卡组（crd_201..207_a）烤字——bake_card 的薄复用。

与主管线的差别只有一处：新卡**没有原图**，无从做逐卡自指重建，故底图统一取
空白模板 crd_0_d.png（分割线/边框/渐变底俱全，本来就是"无字卡面"），字色取
标准卡实测值（全库 195 张字芯稳定落在 (56–60,0,0–1) 暗红，见
bake_card.measure_ink_color 的注释——这里量 crd_1 一张即代表全库）。
排版三件套（plan_title / plan_body / plan_right）与折行规格原样 import，
不复制常量，规格漂移时本工具自动跟随。

文案源：docs/finale/cards-bake.yaml（体例同 skeleton/cards.zh.yaml）。
右栏（セクション栏）统一『谢幕』。输出 build/finale_cards/。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import yaml
from PIL import Image, ImageDraw

from tools.bake_card import (plan_title, plan_body, plan_right, _font,
                             measure_ink_color)
from tools.measure_card import card_path, CARD_W, CARD_H

CARDS_YAML = REPO / "docs" / "finale" / "cards-bake.yaml"
OUT_DIR = REPO / "build" / "finale_cards"
SECTION_LABEL = "谢幕"
BLANK_TEMPLATE = card_path(0, "d")


def load_cards():
    rows = yaml.safe_load(CARDS_YAML.read_text(encoding="utf-8"))
    return {int(r["card"]): r for r in rows}


def bake_one(card, row, blank, ink):
    tplan = plan_title(card, row["title_zh"])
    bplan = plan_body(card, row["body_zh"])
    rplan = plan_right(card, SECTION_LABEL)
    im = blank.copy()
    d = ImageDraw.Draw(im)
    text = tplan["lines"][0] if tplan["lines"] else ""
    for (x, y, anchor) in tplan["positions"]:
        d.text((x, y), text, font=_font(tplan["font_size"]), fill=ink, anchor=anchor)
    for (x, y, anchor, line) in bplan["positions"]:
        d.text((x, y), line, font=_font(bplan["font_size"]), fill=ink, anchor=anchor)
    for (x, y, anchor, line) in rplan["positions"]:
        d.text((x, y), line, font=_font(rplan["font_size"]), fill=ink, anchor=anchor)
    problems = []
    if tplan["info"]["truncated"]:
        problems.append(f"title truncated: {tplan['info']}")
    if bplan["info"]["truncated"]:
        problems.append(f"body truncated: {bplan['info']['overflow_segments']}")
    if bplan["height_overflow"]:
        problems.append(f"body height overflow: {bplan['total_lines']} lines")
    if rplan["info"]["truncated"]:
        problems.append(f"right truncated: {rplan['info']}")
    return im, problems


def build_preview(pairs, scale=2, cols=4):
    cw, ch = CARD_W * scale, CARD_H * scale
    label_h, gap = 16, 10
    rows = (len(pairs) + cols - 1) // cols
    canvas = Image.new("RGBA", (cols * (cw + gap) + gap,
                                rows * (label_h + ch + gap) + gap), (30, 30, 30, 255))
    d = ImageDraw.Draw(canvas)
    for i, (card, im) in enumerate(pairs):
        col, row = i % cols, i // cols
        x = gap + col * (cw + gap)
        y = gap + row * (label_h + ch + gap)
        d.text((x, y), f"crd_{card}_a", fill=(255, 255, 0, 255))
        canvas.paste(im.resize((cw, ch), Image.NEAREST), (x, y + label_h))
    return canvas


def main():
    cards = load_cards()
    blank = Image.open(BLANK_TEMPLATE).convert("RGBA")
    assert blank.size == (CARD_W, CARD_H), blank.size
    ink, n_ink = measure_ink_color(1)
    print(f"ink from crd_1 ({n_ink} samples): {ink}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs, all_problems = [], []
    for card in sorted(cards):
        im, problems = bake_one(card, cards[card], blank, ink)
        out = OUT_DIR / f"crd_{card}_a.png"
        im.save(out)
        pairs.append((card, im))
        status = "OK" if not problems else "; ".join(problems)
        print(f"crd_{card}_a.png  {status}")
        all_problems.extend((card, p) for p in problems)
    preview = build_preview(pairs)
    preview.save(OUT_DIR / "_preview.png")   # _ 前缀＝QA 对照图，按约定非入包件
    print(f"preview: {OUT_DIR / '_preview.png'}")
    if all_problems:
        print(f"PROBLEMS: {all_problems}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
