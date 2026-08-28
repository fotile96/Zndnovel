#!/usr/bin/env python3
"""`png/sysgim/` 描边字族的中文烤字。

**族的边界是实测出来的**（见 `tools/measure_sysgim.py`）：这一族的可见像素
100% 落在「白填充↔褐描边」或「灰填充↔褐描边」的插值带上，21 张全中，
6 张对照全在 0.23 以下。所以「哪些图归这一族」不靠文件名清单，靠 `--verify-family`。

**每行的填充色逐行实测**，不按文件假定：`sys_20_c` 一家四张（c/cb/cc/cd）文字
完全相同，差别只在哪几行是禁用态的灰。假定「整张要么白要么灰」会把禁用态抹平。

**部分替换**：`sys_22_ba/bb` 只能动 x0–66（x67 起是 10 个 14px 音量格，位置由
`snr_common.lua:3326` 的 `layerClip(67,0,67+14n,16)` 钉死）；`sys_22_e` 七个人名
里只有「その他」要改，其余中日同形——重绘反而会让字形变样，故只动那一块。
这类范围写在数据的 `box` 字段里，并对**盒外每一个像素**做逐像素比对。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.measure_sysgim import FILL_OFF, FILL_ON, STROKE, measure  # noqa: E402
from tools.ui_font import resolve as _resolve_font  # noqa: E402
from tools.bake_out import out_dir as _out_dir
from tools.ui_font import truetype as _ui_truetype

warnings.filterwarnings("ignore", message="Palette images with Transparency")

REPO = Path(__file__).resolve().parent.parent
SYSGIM = REPO / "png" / "sysgim"
OUTDIR = _out_dir("sysgim")
#: 字体按面可换：`ZND_UI_FONT_SYSGIM` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷 Regular
#: （统一走 tools/ui_font.py；原先只认 ZND_UI_FONT，行为不变，只是多了按面指定）。
#: 换成 Bold 字形时把 `FILL_GAIN` 一并调回 1.0——增益是为补 Regular 的细笔调而加的
#: 补偿，粗体上再叠增益只会把字腔糊死。
#:   ZND_UI_FONT_SYSGIM=/path/to/Bold.ttf ZND_UI_FILL_GAIN=1.0 uv run python tools/bake_...
FONT_PATH = _resolve_font("sysgim")
DATA = REPO / "data" / "sysgim_outline_text.jsonl"

FONT_CASCADE = (17, 16, 15, 14, 13, 12)

#: 描边不透明度。原图 `(73,59,59,217)` 是这一族最常见的描边取值。
STROKE_ALPHA = 217

FILL_BOLD = 0
STROKE_WIDTH = 1

#: 填充蒙版增益——**不做几何膨胀，只把蒙版拉到饱和**。
#:
#: 原图是日文粗黑体，白芯实心；霞鹜文楷 Regular 是细笔调，14–17px 下笔干宽不到
#: 一个像素，抗锯齿让填充蒙版根本到不了 255，整行读起来是灰的（实测纯白核
#: 12.7% → 0.6%）。
#:
#: 先试的是几何加粗（填充 stroke_width=1 + 描边 2）。逐张看图直接废掉：假名形体
#: 开放扛得住，汉字扛不住——「跳过询问」的字腔被填死，不可读。**几何膨胀对汉字
#: 是不可用的**。
#:
#: 增益法只抬蒙版值、不动轮廓，故笔画变实而字腔不闭。逐档对照
#: （1.0/1.6/2.2/3.0 × 15/16/17px）取 2.2：白芯饱满且字腔仍清晰可辨。
FILL_GAIN = float(os.environ.get("ZND_UI_FILL_GAIN", 2.2))

#: 文字相同、仅禁用态分布不同的几张，共用同一份译文。
TEXT_ALIAS = {"sys_20_cb": "sys_20_c", "sys_20_cc": "sys_20_c", "sys_20_cd": "sys_20_c"}

#: 零引用孤儿：lua 全库只有 `backLayerName` 声明，从未 `layerCopy`。不烤。
ORPHANS = {"sys_22_c"}


@dataclass
class RowPlan:
    idx: int
    jp: str
    zh: str
    box: tuple[int, int, int, int]  # 擦除/绘制范围 (l, t, r, b) 右下开区间
    fill: tuple[int, int, int]
    alpha: float
    anchor_x: int
    align: str
    ink_top: int
    ink_bottom: int


def load_text() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in DATA.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out.setdefault(r["file"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["row"])
    return out


def _row_style(im: Image.Image, box) -> tuple[tuple[int, int, int], float]:
    """这一行的（填充色, 整体不透明度）——逐行实测，不按文件假定。

    禁用态在这一族里有**两种**机制，都得认：

    - `sys_20_cb/cc/cd`：颜色不变，**整行 alpha 减半**（255→128、212→106）。
    - `sys_22_e` 下半：alpha 仍是 255，**填充色换成灰** `(166,154,145)`。

    只认其中一种，另一种就会被抹平成启用态——第一版只测颜色，结果 cb/cd 的
    六个灰行全被渲成了白行。
    """
    px = im.load()
    l, t, r, b = box
    vis = [px[x, y] for y in range(t, b) for x in range(l, r) if px[x, y][3] > 8]
    if not vis:
        return FILL_ON, 1.0
    peak = max(p[3] for p in vis)
    core = [p for p in vis if p[3] >= peak * 0.9]
    n_off = sum(
        1
        for p in core
        if sum((p[i] - FILL_OFF[i]) ** 2 for i in range(3))
        < sum((p[i] - FILL_ON[i]) ** 2 for i in range(3))
    )
    fill = FILL_OFF if n_off > len(core) / 2 else FILL_ON
    return fill, peak / 255.0


def _box_anchor(im: Image.Image, box) -> tuple[str, int]:
    """盒内原墨迹的对齐方式与锚点。"""
    px = im.load()
    l, t, r, b = box
    xs = [x for x in range(l, r) for y in range(t, b) if px[x, y][3] >= 8]
    if not xs:
        return "center", (l + r) // 2
    lm, rm = min(xs) - l, r - 1 - max(xs)
    if lm + 3 < rm:
        return "left", min(xs)
    if rm + 3 < lm:
        return "right", max(xs)
    return "center", (min(xs) + max(xs)) // 2


def _median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def plan_file(name: str, rows: list[dict]) -> tuple[Image.Image, list[RowPlan]]:
    im = Image.open(SYSGIM / f"{name}.png").convert("RGBA")
    W, H = im.size

    # 每条都自带 box 时，几何全由 box 说了算，"行" 这套概念不适用。
    # `sys_22_e` 就是：两条都是局部替换，而整张图自然分段是 3 行——按行去核
    # 只会得出一个假的不一致。
    if all("box" in m for m in rows):
        plans = []
        for meta in rows:
            box = tuple(meta["box"])
            fill, alpha = _row_style(im, box)
            align, anchor = _box_anchor(im, box)
            px = im.load()
            ys = [
                y
                for y in range(box[1], box[3])
                for x in range(box[0], box[2])
                if px[x, y][3] >= 8
            ]
            plans.append(
                RowPlan(
                    idx=meta["row"], jp=meta["jp"], zh=meta["zh"], box=box,
                    fill=fill, alpha=alpha, anchor_x=anchor, align=align,
                    ink_top=min(ys) if ys else box[1],
                    ink_bottom=max(ys) if ys else box[3] - 1,
                )
            )
        return im, plans

    spec = measure(SYSGIM / f"{name}.png", n_rows=len(rows))
    if len(spec.rows) != len(rows):
        raise ValueError(
            f"{name}: 译文 {len(rows)} 行，实测 {len(spec.rows)} 行——对不上，拒绝渲染"
        )

    # 对齐锚点取各行的中位数：`sys_20_c` 有一行是满宽的，用均值会被它拖偏。
    align = spec.align
    if align in ("mixed", "single"):
        # 单行/杂乱时按原行在图内的左右余量判定：`sys_22_ba` 的「ミュート」贴着
        # 左边缘（右侧 x67 起是音量格），一律居中会把它推到格子上去。
        r0 = spec.rows[0]
        lm, rm = r0.left, W - 1 - r0.right
        align = "left" if lm + 3 < rm else ("right" if rm + 3 < lm else "center")
    anchor = {
        "left": _median([r.left for r in spec.rows]),
        "right": _median([r.right for r in spec.rows]),
        "center": _median([(r.left + r.right) // 2 for r in spec.rows]),
    }[align]

    # 每行分到的**纵向带**取到与邻行的中线，而不是这一行墨迹的高度。
    # 用墨迹高会把可用高度卡死在 17–18px，逼出一堆本不必要的字号回落——
    # 中文比日文假名占得高，正好卡在这 1px 上。
    bands = []
    for i, r in enumerate(spec.rows):
        top = 0 if i == 0 else (spec.rows[i - 1].bottom + r.top + 1) // 2
        bot = H if i == len(spec.rows) - 1 else (r.bottom + spec.rows[i + 1].top + 1) // 2
        bands.append((top, bot))

    plans = []
    for r, meta, (bt, bb) in zip(spec.rows, rows, bands):
        if "box" in meta:
            box = tuple(meta["box"])
        else:
            box = (0, bt, W, bb)
        fill, alpha = _row_style(im, box)
        row_align, row_anchor = align, anchor
        if "box" in meta:
            # 带 box 的行必须**在盒内**重新测对齐：`sys_22_ba` 那一行的墨迹里
            # 混着 x67 起的十个音量格，按整行算会把「ミュート」的左对齐算成居中。
            row_align, row_anchor = _box_anchor(im, box)
        plans.append(
            RowPlan(
                idx=meta["row"],
                jp=meta["jp"],
                zh=meta["zh"],
                box=box,
                fill=fill,
                alpha=alpha,
                anchor_x=row_anchor,
                align=row_align,
                ink_top=r.top,
                ink_bottom=r.bottom,
            )
        )
    return im, plans


def _masks(text: str, size: int):
    font = _ui_truetype("sysgim", size)
    pad = 12
    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    l, t, rr, bb = d.textbbox((0, 0), text, font=font, stroke_width=STROKE_WIDTH)
    W, H = rr - l + 2 * pad, bb - t + 2 * pad
    fill_m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(fill_m).text(
        (pad - l, pad - t), text, font=font, fill=255,
        stroke_width=FILL_BOLD, stroke_fill=255,
    )
    str_m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(str_m).text(
        (pad - l, pad - t), text, font=font, fill=255,
        stroke_width=STROKE_WIDTH, stroke_fill=255,
    )
    return fill_m, str_m


def render_row(text: str, size: int, fill: tuple[int, int, int], alpha: float = 1.0) -> Image.Image:
    """填充覆在描边之上，按原图的两色插值结构合成。"""
    fill_m, str_m = _masks(text, size)
    W, H = fill_m.size
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fp, sp, op = fill_m.load(), str_m.load(), out.load()
    for y in range(H):
        for x in range(W):
            af = min(1.0, fp[x, y] / 255.0 * FILL_GAIN)
            a_s = sp[x, y] / 255.0 * (STROKE_ALPHA / 255.0)
            a = af + a_s * (1 - af)
            if a <= 0:
                continue
            w = af / a  # 填充在合成结果里占的比重
            rgb = tuple(
                round(fill[i] * w + STROKE[i] * (1 - w)) for i in range(3)
            )
            op[x, y] = (*rgb, round(a * 255 * alpha))
    return out.crop(out.getbbox() or (0, 0, W, H))


def bake_file(name: str, rows: list[dict], report: list[str]):
    im, plans = plan_file(name, rows)
    W, H = im.size
    out = im.copy()
    touched: list[tuple[int, int, int, int]] = []

    # 字号锚在**原行墨迹高**上，不是行距。行距留的余量比原文实际用掉的大得多，
    # 按行距选会渲出比日文原文明显更大的字——版面对了，观感却不是同一套 UI。
    target_h = _median([p.ink_bottom - p.ink_top + 1 for p in plans])
    base = next(
        (
            s
            for s in FONT_CASCADE
            if max(render_row(p.zh, s, p.fill, p.alpha).height for p in plans) <= target_h
        ),
        FONT_CASCADE[-1],
    )

    # 字号**整张统一**：同一张图里各行是并排看的，一行 14px 一行 15px 会显得坏掉。
    size, blocked_by = FONT_CASCADE[-1], None
    for cand in [s for s in FONT_CASCADE if s <= base]:
        over = [
            p
            for p in plans
            if (lambda g: g.width > p.box[2] - p.box[0] or g.height > p.box[3] - p.box[1])(
                render_row(p.zh, cand, p.fill, p.alpha)
            )
        ]
        if not over:
            size = cand
            break
        # 记住是谁挡住了这一档——回落理由要指名道姓，不能只说「回落了」
        blocked_by = (cand, over[0])
    if size != base and blocked_by:
        c, p = blocked_by
        report.append(
            f"cascade {name} 整张 {base}→{size}px（{c}px 卡在行{p.idx}「{p.zh}」）"
        )

    for p in plans:
        l, t, r, b = p.box
        avail_w, avail_h = r - l, b - t
        g = render_row(p.zh, size, p.fill, p.alpha)
        if g.width > avail_w or g.height > avail_h:
            report.append(
                f"OVERFLOW {name} 行{p.idx} 「{p.zh}」 {g.width}x{g.height} > {avail_w}x{avail_h}"
            )

        # 横向按原行对齐方式落位，纵向对齐原行墨迹的中心
        if p.align == "left":
            x = p.anchor_x
        elif p.align == "right":
            x = p.anchor_x - g.width + 1
        else:
            x = p.anchor_x - g.width // 2
        x = max(l, min(x, r - g.width))
        cy = (p.ink_top + p.ink_bottom) // 2
        y = cy - g.height // 2
        y = max(t, min(y, b - g.height))

        out.paste((0, 0, 0, 0), (l, t, r, b))
        out.alpha_composite(g, (x, y))
        touched.append((l, t, r, b))

    # 盒外逐像素保真
    src, dst = im.load(), out.load()
    violations = 0
    for y in range(H):
        for x in range(W):
            if any(l <= x < r and t <= y < b for (l, t, r, b) in touched):
                continue
            if src[x, y] != dst[x, y]:
                violations += 1
    if violations:
        report.append(f"PIXEL-VIOLATION {name}: 盒外 {violations} 个像素被改动")
    return out, violations


def verify_family(names) -> list[str]:
    bad = []
    for n in names:
        s = measure(SYSGIM / f"{n}.png")
        if not s.is_outline_family:
            bad.append(f"{n} 不属描边字族（share={s.family_share}）——判据与清单不符")
    return bad


def run(write: bool = True) -> int:
    text = load_text()
    targets = sorted(set(text) | set(TEXT_ALIAS))
    report: list[str] = []
    report += verify_family(targets)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    total_viol = 0
    for name in targets:
        rows = text[TEXT_ALIAS.get(name, name)]
        img, viol = bake_file(name, rows, report)
        total_viol += viol
        if write:
            img.save(OUTDIR / f"{name}.png")

    n_rows = sum(len(text[TEXT_ALIAS.get(n, n)]) for n in targets)
    print(f"描边字族：{len(targets)} 张 / {n_rows} 行")
    print(f"零引用孤儿跳过：{sorted(ORPHANS)}")
    print(f"盒外像素改动：{total_viol}")
    for line in report:
        print("  " + line)
    if not report:
        print("  （无回落、无溢出、无越界）")
    return 1 if any(x.startswith(("OVERFLOW", "PIXEL-VIOLATION")) or "不属" in x for x in report) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只算不写")
    a = ap.parse_args(argv)
    return run(write=not a.check)


if __name__ == "__main__":
    raise SystemExit(main())
