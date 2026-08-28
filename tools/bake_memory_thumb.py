#!/usr/bin/env python3
"""`graphic/memoryThumbnail_{1,2}_a` —— 回想模式缩略图上的 14 个章节名。

**这一面与前面所有面的差别：字直接压在照片上。** 前面几面的底要么透明、要么是纯色
面板，擦掉即可；这里擦掉字之后必须把**照片**补回来，而照片没有可解析的模型。

解法是测出来的，不是设计的：**每一格都是仓库里某张图的 1/4 缩放**（360×204 = 3×3 格、
360×136 = 3×2 格，格 120×68 = 480×272 的四分之一）。逐格与全库 2100 张比对，匹配是
决定性的——最佳 2.2、次名 41 以上。于是干净底可以从来源重新缩放出来。

**两条重建路径，按实测保真度分流**（判据取字带**正上方** y[44,53] 的平均通道差，
那里没有字，可直接与来源比）：

- **≤7 → 用来源重建。** 11 格落在 2.2–5.01，肉眼不可辨（<2%）。
- **>7 或无来源 → 上下干净行插值。** 3 格落在 9.04–14.6；空档是 [5.01, 9.04]，
  阈值 7 取在空档中点，不是拍的。这三格的来源**场景是对的**（同一张 CG），
  差在缩放锐度，各种滤镜与锐化都试过无改善。对它们，**连续性比保真度重要**：
  贴一块误差 9–14 的矩形会留下可见的方块边界，而插值是从本格自身的行连续过来的，
  没有接缝。字带上下都有干净行（上 y≤53、下 y[65,67]），故是**插值**不是外推。

第 14 格「いつかきみがみるお話」的绘本插画在 png/ 全库找不到来源（最佳 52.4），
一并走插值——用户 2026-08-29 裁定「就地修补那一格」。

**字样实测**（四格完全一致，故钉死而不给容差）：白芯 y[55,63] 高 9px，
黑边外扩 1px（y[54,64]），右对齐于格内 x=115。

    uv run python tools/bake_memory_thumb.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.ui_font import truetype as _ui_truetype  # noqa: E402

REPO = Path(_REPO)
#: `file` 带子目录（与模式画面框同一约定），故 src 取 png/ 而非 png/graphic/。
SRC = REPO / "png"
DATA = REPO / "data" / "memory_thumb_text.jsonl"
OUTDIR = _out_dir("memory_thumb_zh")

CELL_W, CELL_H = 120, 68
#: 白芯右缘（格内 x）。右对齐。
RIGHT = 115
OUTLINE = 1
#: 原图实测：白芯 y[55,63]（高 9），黑边外扩 1px ⇒ 字带 y[54,64]。白芯中心 y=59。
ORIG_CORE_TOP, ORIG_CORE_H = 55, 9
CORE_CENTER = ORIG_CORE_TOP + ORIG_CORE_H / 2.0
#: 允许的最大白芯高。**不锁死在原图的 9px**：原图是假名，假名不填满字身；
#: 汉字填满，按芯高对齐会让中文看着比原文小一圈（与 cutin 那轮 `size_bias` 同因）。
#: 可用 `ZND_THUMB_CORE_H` 临时试别的档。
#: 取 11 而非原图的 9：原图是**假名**，假名不填满字身；汉字填满，按芯高对齐会让
#: 中文看着比原文小一圈。实测四档并排（`build/_thumb_ab.png`），芯高 11（思源 10px）
#: 的分量最接近原图；芯高 9 时统一字号只剩 7px，明显偏小。
#: 字带随之由 y[54,64] 长到 y[53,65]，多占照片两行——那两行同样由干净底重建。
CORE_H = int(os.environ.get("ZND_THUMB_CORE_H", 11))


def band_for(core_h: int) -> tuple[int, int]:
    """给定白芯高，字带＝白芯上下各加 1px 黑边，且**保持白芯中心不动**。"""
    top = int(round(CORE_CENTER - core_h / 2.0))
    return top - OUTLINE, top + core_h + OUTLINE


BAND = band_for(CORE_H)
CORE_TOP = BAND[0] + OUTLINE
#: 字号从大到小试，取**全部 14 格都放得下**的最大档。
#:
#: **一个字号管全部**，不逐格选：原图 14 格的白芯高实测一律 9px，而逐格选会让
#: 「序章」比「总有一天你会看到的故事」大一档——同一张九宫格里并排，一眼就看出来
#: （同裁决 Y7 对「一行 15px 一行 16px」的警告）。
FONT_CASCADE = (13, 12, 11, 10, 9, 8, 7, 6)

#: 用哪一面的字。**不是 sysgim。**
#:
#: 这些字幕的白芯只有 9px——全工程最小的一档。实测霞鹜文楷在 9–11px 下纯白核占比
#: **0.0%**、最亮只到 246，即渲出来是灰字；而原图是**真白芯**。思源黑体 Medium 在
#: 同样的墨迹高下纯白核 6.8%、到得了 255，且更窄。这与裁决 F1/F4 是同一条：
#: 卡面 9px 正文当初就是因此选的思源黑体 Medium。故这一面跟 `card` 的字体决定走，
#: 不跟尚未定案的 `sysgim`。
FACE = os.environ.get("ZND_THUMB_FACE", "card")

#: 保真度阈值。实测两簇是 **2.2–5.01** 与 **9.04–14.6**，空档 [5.01, 9.04]，
#: 取中点 7.0。（先取过 5.0，正好把 5.01 那格切到错的一侧——阈值卡在簇的边缘上，
#: 而不是空档里，等于让一个测量噪声决定走哪条重建路径。）
FIDELITY_MAX = 7.0

#: (图, 列, 行) → (来源图相对 png/ 的路径, 缩放滤镜) 或 None（全库无来源）。
#:
#: **缺的那格显式写 None，不是漏掉。** 漏掉与「查遍 2100 张确实没有」在代码里
#:长得一样，含义却相反。
SOURCES = {
    ("graphic/memoryThumbnail_1_a", 0, 0): ("event/eve_3_x", "BICUBIC"),
    ("graphic/memoryThumbnail_1_a", 1, 0): ("event/eve_4_x", "BICUBIC"),
    ("graphic/memoryThumbnail_1_a", 2, 0): ("event/eve_20_c", "BICUBIC"),
    ("graphic/memoryThumbnail_1_a", 0, 1): ("event/eve_21_x", "BICUBIC"),
    ("graphic/memoryThumbnail_1_a", 1, 1): ("event/eve_26_x", "BICUBIC"),
    ("graphic/memoryThumbnail_1_a", 2, 1): None,          # 绘本插画，全库无来源
    ("graphic/memoryThumbnail_1_a", 0, 2): ("event/eve_25_b", "BICUBIC"),
    ("graphic/memoryThumbnail_1_a", 1, 2): ("event/eve_60_x", "BILINEAR"),
    ("graphic/memoryThumbnail_1_a", 2, 2): ("event/eve_34_x", "BICUBIC"),
    ("graphic/memoryThumbnail_2_a", 0, 0): ("event/eve_44_x", "BICUBIC"),
    ("graphic/memoryThumbnail_2_a", 1, 0): ("event/eve_48_x", "BICUBIC"),
    ("graphic/memoryThumbnail_2_a", 2, 0): ("event/eve_50_x", "BILINEAR"),
    ("graphic/memoryThumbnail_2_a", 0, 1): ("bg/bg_26_a_0", "BILINEAR"),
    ("graphic/memoryThumbnail_2_a", 1, 1): ("bg/bg_7_a_0", "BICUBIC"),
}

_FILTERS = {"BICUBIC": Image.BICUBIC, "BILINEAR": Image.BILINEAR}


def cell_of(row: dict) -> tuple[int, int]:
    """从 `box` 反推该行落在第几列第几行。"""
    return row["box"][0] // CELL_W, row["box"][1] // CELL_H


def _thumb(name: str) -> Image.Image:
    # 绕一次 RGBA：P+透明 直接转 RGB 会告警。实测两条路逐字节相同
    # （这两张的透明索引在图中出现 0 次）。
    return Image.open(SRC / f"{name}.png").convert("RGBA").convert("RGB")


def _rescaled(src: tuple[str, str]) -> Image.Image:
    path, flt = src
    return (Image.open(REPO / "png" / f"{path}.png").convert("RGBA").convert("RGB")
            .resize((CELL_W, CELL_H), _FILTERS[flt]))


def source_fidelity(name: str, cell: tuple[int, int], src) -> float:
    """来源在字带**正上方** y[44,53] 的平均通道差。那里没有字，可直接比。"""
    c, r = cell
    tp = _thumb(name).load()
    gp = _rescaled(src).load()
    n = 10 * CELL_W * 3
    return sum(abs(a - b)
               for y in range(44, 54) for x in range(CELL_W)
               for a, b in zip(tp[c * CELL_W + x, r * CELL_H + y], gp[x, y])) / n


def clean_band(name: str, cell: tuple[int, int]) -> Image.Image:
    """该格字带的干净底（120×11）。来源够好就用来源，否则上下插值。"""
    c, r = cell
    src = SOURCES[(name, c, r)]
    if src is not None and source_fidelity(name, cell, src) <= FIDELITY_MAX:
        return _rescaled(src).crop((0, BAND[0], CELL_W, BAND[1]))

    thumb = _thumb(name)
    cellim = thumb.crop((c * CELL_W, r * CELL_H, (c + 1) * CELL_W, (r + 1) * CELL_H))
    sp = cellim.load()
    band = Image.new("RGB", (CELL_W, BAND[1] - BAND[0]))
    bp = band.load()
    # 字带上下都有干净行（上 y=53、下 y=65），故是**插值**不是外推——
    # 两端已知的 11px 缺口远比单端外推好条件。
    for x in range(CELL_W):
        top, bot = sp[x, BAND[0] - 1], sp[x, BAND[1]]
        for i, y in enumerate(range(BAND[0], BAND[1])):
            t = (i + 1) / (BAND[1] - BAND[0] + 1)
            bp[x, y - BAND[0]] = tuple(round(top[k] * (1 - t) + bot[k] * t)
                                       for k in range(3))
    return band


def _ink_box(text: str, size: int, face: str = FACE):
    m = Image.new("L", (CELL_W * 4, CELL_H * 2), 0)
    ImageDraw.Draw(m).text((10, 10), text, font=_ui_truetype(face, size), fill=255)
    return m.getbbox()


def unified_size(face: str = FACE) -> int:
    """全部 14 格共用的字号：芯高 ≤ CORE_H 且宽 ≤ 可用宽的最大档。"""
    texts = [json.loads(l)["zh"]
             for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    avail = RIGHT + 1 - OUTLINE
    for size in FONT_CASCADE:
        boxes = [_ink_box(t, size, face) for t in texts]
        if all(b is not None and b[3] - b[1] <= CORE_H and b[2] - b[0] <= avail
               for b in boxes):
            return size
    return FONT_CASCADE[-1]


def _fit(text: str, avail_w: int, face: str = FACE):
    """返回 (统一字号, 字体, 墨迹框)。字号不逐格选，见 FONT_CASCADE 处的说明。"""
    size = unified_size(face)
    bb = _ink_box(text, size, face)
    if bb is not None and bb[3] - bb[1] <= CORE_H and bb[2] - bb[0] <= avail_w:
        return size, _ui_truetype(face, size), bb
    return size, _ui_truetype(face, size), None


def bake_file(name: str, rows: list[dict], report: list[str]) -> Image.Image:
    out = Image.open(SRC / f"{name}.png").convert("RGBA")
    for meta in rows:
        c, r = cell_of(meta)
        ox, oy = c * CELL_W, r * CELL_H
        out.paste(clean_band(name, (c, r)).convert("RGBA"), (ox, oy + BAND[0]))

        text = meta["zh"]
        avail = RIGHT + 1 - OUTLINE          # 格内 x[1,115]
        size, font, bb = _fit(text, avail)
        if bb is None:
            report.append(f"OVERFLOW {name} 格({c},{r})：「{text}」放不下")
            continue
        if bb[2] - bb[0] > avail:
            report.append(
                f"OVERFLOW {name} 格({c},{r})：「{text}」{size}px 宽 "
                f"{bb[2] - bb[0]} > 可用 {avail}")
        # 右对齐白芯右缘到 RIGHT，白芯顶对到 CORE_TOP。
        # `bb` 是在草稿图上以 (10,10) 为原点量的，故墨迹相对原点的偏移是
        # (bb[0]-10, bb[1]-10)；反推绘制原点时那个 10 要**加**回来，且到此为止——
        # 早先又在 d.text 里减了一次，整块字高了 8px、右缘差 10px，而**产物看上去
        # 只是"位置略高"**，不像出错。
        px = ox + RIGHT - (bb[2] - 1) + 10
        py = oy + CORE_TOP - bb[1] + 10
        d = ImageDraw.Draw(out)
        # 1px 纯黑描边：八邻域各描一遍，再压白芯。比 stroke_width 可控——
        # Pillow 的描边会随字号变粗，而实测原图**恒为 1px**。
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    d.text((px + dx, py + dy), text, font=font,
                           fill=(0, 0, 0, 255))
        d.text((px, py), text, font=font, fill=(255, 255, 255, 255))
    return out


def run(write: bool = True) -> int:
    rows_by_file: dict[str, list[dict]] = {}
    for line in DATA.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows_by_file.setdefault(r["file"], []).append(r)
    report: list[str] = []
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, rows in sorted(rows_by_file.items()):
        img = bake_file(name, rows, report)
        if write:
            dst = OUTDIR / f"{name}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst)
    print(f"回想缩略图章节名：{len(rows_by_file)} 张 / "
          f"{sum(len(v) for v in rows_by_file.values())} 格")
    for line in report:
        print(f"  {line}")
    return sum(1 for line in report if line.startswith("OVERFLOW"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(write=not a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
