#!/usr/bin/env python3
"""sysgim **D 族**：`sys_5_d` / `sys_1_g` —— 保留面板、盒内替换。

**为什么 A/B/C 三族的工具都不适用。** A 是描边字、B/C 是发光字；这一族的字既没有
描边也没有发光，直接压在**渐变面板**上：

- `sys_5_d`（239×74）米黄圆角面板，B 通道横向从 215 变到 255，深褐字 3 行；
- `sys_1_g`（127×37）深红面板，红字 1 行 + 白字 2 行。

面板底不是纯色，`measure_glow` 那套「盒边众数取底」当场就被收敛检查拒掉。但两张的
**行与行之间都有干净行**（`sys_1_g` 三行只隔 2–3 行，`sys_5_d` 隔 5–7 行），
于是底可以由 `bake_fill.vfill` 逐列纵向插值补回来——与 `memoryThumbnail` 同一手法。

**字色逐行实测，不写死**：`sys_1_g` 同一张图里第 1 行红字、另两行白字。写死一个色
会让其中一行整行变色，而**产物看上去只是"配色略有不同"**（同裁决 C8）。

**字号锚在原行墨迹高**（承 Y7）。⚠ 交接文档记 `sys_1_g`「3 行塞进 37px＝每行 12px，
中文在这个字号下恐怕要缩短译文」——那 12px 是**行距**，实测**墨迹只有 8px 高**，
档位因此宽裕，三行译文都装得下，无需缩短。

    uv run python tools/bake_panel.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from PIL import Image, ImageDraw

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_fill import vfill  # noqa: E402
from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.ui_font import truetype as _ui_truetype  # noqa: E402

REPO = Path(_REPO)
SRC = REPO / "png" / "sysgim"
DATA = REPO / "data" / "sysgim_panel_text.jsonl"
OUTDIR = _out_dir("sysgim_panel_zh")

#: 与其余 sysgim 各族同面——这一面的字尚未定案，D 族该跟着它一起定，不各定各的。
FACE = "sysgim"
FONT_CASCADE = (14, 13, 12, 11, 10, 9, 8)

#: 允许比原行墨迹高出几像素。**必须给**：假名不填满字身、汉字填满，同字号下汉字的
#: 墨迹恒高约 1px。`sys_1_g` 第 2 行原文墨迹 8px，而中文最小档 8px 就已经是 9px 高
#: ——余量为 0 时整行无解，会被判成 OVERFLOW 而根本渲不出来。
#: （交接文档担心的「要缩短译文」其实是这一条，不是宽度：那行宽 82 < 可用 121。）
HEIGHT_SLACK = 1


def rows_by_file() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in DATA.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out.setdefault(r["file"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["row"])
    return out


def ink_colour(row: dict) -> tuple[int, ...]:
    """该行字芯的颜色——**逐行从原图实测**。

    取盒内「离面板底最远」的那一成像素的中位数。用中位数而非均值：抗锯齿边会把
    均值往底色拉，而我们要的是笔画中心的颜色（同 C8 的取法）。
    """
    im = Image.open(SRC / f"{row['file']}.png").convert("RGBA")
    px = im.load()
    l, t, r, b = row["box"]
    # 面板底取盒**上方**那条干净行的中位数
    base = tuple(round(statistics.median([px[x, t - 1][k] for x in range(l, r)]))
                 for k in range(4))
    dist = lambda p: sum(abs(p[k] - base[k]) for k in range(4))
    px_in = [px[x, y] for y in range(t, b) for x in range(l, r)]
    px_in.sort(key=dist, reverse=True)
    core = px_in[: max(1, len(px_in) // 10)]
    return tuple(round(statistics.median([c[k] for c in core])) for k in range(4))


def row_dirt(im: Image.Image, y: int, l: int, r: int) -> float:
    """该行里「偏离本行中位数 >60」的像素占比——用来判一行干不干净。

    **不能用整行离散度**：`sys_5_d` 的面板 B 通道横向从 215 变到 255，干净行的 σ
    就有 50，比某些字行还高。中位数跟得上缓变的渐变，跟不上突变的字。
    实测干净行 ≤4.4%、字行 ≥14.9%。
    """
    px = im.load()
    row = [px[x, y] for x in range(l, r)]
    med = [statistics.median([p[k] for p in row]) for k in range(len(row[0]))]
    far = sum(1 for p in row if sum(abs(p[k] - med[k]) for k in range(len(med))) > 60)
    return far / len(row)


def _ink_box(text: str, size: int):
    m = Image.new("L", (600, 60), 0)
    ImageDraw.Draw(m).text((10, 10), text, font=_ui_truetype(FACE, size), fill=255)
    return m.getbbox()


def choose_size(text: str, target_h: int, avail_w: int) -> tuple[int, tuple | None]:
    """锚在原行墨迹高（Y7）：取核高 ≤ target_h 且宽放得下的最大档。"""
    over = None
    for size in FONT_CASCADE:
        bb = _ink_box(text, size)
        if bb is None:
            continue
        h, w = bb[3] - bb[1], bb[2] - bb[0]
        if h <= target_h + HEIGHT_SLACK and w <= avail_w:
            return size, bb
        if h <= target_h + HEIGHT_SLACK:
            over = size
    return (over or FONT_CASCADE[-1]), None


def bake_file(name: str, rows: list[dict], report: list[str] | None = None) -> Image.Image:
    report = report if report is not None else []
    orig = Image.open(SRC / f"{name}.png").convert("RGBA")
    out = orig
    for r in rows:                      # 先把所有盒的底补回来，再落字
        out = vfill(out, tuple(r["box"]))
    op = orig.load()
    for r in rows:
        l, t, rr, b = r["box"]
        # 原行的墨迹几何：高度定字号，左缘/中心定落位
        base = tuple(round(statistics.median([op[x, t - 1][k] for x in range(l, rr)]))
                     for k in range(4))
        ink = [(x, y) for y in range(t, b) for x in range(l, rr)
               if sum(abs(op[x, y][k] - base[k]) for k in range(4)) > 90]
        if not ink:
            report.append(f"NO-INK {name} 行{r['row']}：盒内量不到原文墨迹")
            continue
        ys = [y for _x, y in ink]
        xs = [x for x, _y in ink]
        target_h = max(ys) - min(ys) + 1
        avail_w = rr - l
        size, bb = choose_size(r["zh"], target_h, avail_w)
        if bb is None:
            report.append(
                f"OVERFLOW {name} 行{r['row']}：「{r['zh']}」在 {size}px 下"
                f"放不进 {avail_w}×{target_h}")
            bb = _ink_box(r["zh"], size)
        if r.get("align") == "left":
            x0 = r.get("left", min(xs))
        else:                            # 居中：复现原行墨迹的中心
            x0 = round((min(xs) + max(xs) + 1) / 2 - (bb[2] - bb[0]) / 2)
        # 纵向对**原行墨迹的中心**，不是对盒——盒为了容下高一点的汉字多留了 1 行，
        # 对盒会把整行往下推半格，行距看着就不匀了。
        y0 = round((min(ys) + max(ys) + 1) / 2 - (bb[3] - bb[1]) / 2)
        # `bb` 是在草稿图上以 (10,10) 为原点量的，反推绘制原点时把那个 10 加回来
        layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((x0 - bb[0] + 10, y0 - bb[1] + 10), r["zh"],
                                   font=_ui_truetype(FACE, size), fill=ink_colour(r))
        # **夹进盒**：本族的名字就叫「保留面板」，字的抗锯齿边一律不许越出盒。
        out.alpha_composite(layer.crop(tuple(r["box"])), (l, t))
    return out


def run(write: bool = True) -> int:
    report: list[str] = []
    data = rows_by_file()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, rows in sorted(data.items()):
        img = bake_file(name, rows, report)
        if write:
            img.save(OUTDIR / f"{name}.png")
    print(f"sysgim 面板族：{len(data)} 张 / {sum(len(v) for v in data.values())} 行")
    for line in report:
        print(f"  {line}")
    return sum(1 for x in report if x.startswith(("OVERFLOW", "NO-INK")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(write=not a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
