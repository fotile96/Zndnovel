#!/usr/bin/env python3
"""**段落式发光烤字**的共用核心（`event/op_*`、`cutin/cut_*` 等共用）。

**这一面为什么不能直接用 `bake_sysgim_glow`。** 发光模型是同一个（透明底 + 距离场
外发光），但**渲染单元不同**：sysgim 是「一盒一行」，op 是「一盒一段」。

原因是量出来的，不是设计选择：op 的行距 18–19px，而发光半径 `MAX_DIST=18` 与之
相当——**邻行的晕必然进盒，逐行盒的远场永远不是纯背景**。实测 15 个逐行盒有 4 个
被底色收敛检查拒绝（离底 6.5–65.9，容差 6），而且放宽或收紧盒形都救不回来：

    op_3_a y[107,126)   原盒 6.5 → 全宽 6.5 → 上下各扩4 45.0 → 各扩8 8.6

扩边距反而把邻行的晕吸得更多。改整段一盒即全部通过（需 ≥14px 边距）。

于是本模块复用 `bake_sysgim_glow` 的**模型**（`measure_glow` / `render_glow` /
`_merge_farther`），另起一套**段落几何**：一个 Glow 管整段，各行共用它，按实测的
行距逐行落位。

**`_b` 不是独立内容。** 6 张里只有 3 张 `_a` 有译文——`_b` 是 `_a` 的虚化版，
实测高斯 r=1.5 即可重建（alpha 平均残差 0.4–0.5／满量程 255，墨迹 IoU 0.89–0.91，
高频能量减半）。故 `_b` 由烤好的 `_a` 滤一次生成，不单独译、不单独存。

**行数可以不等。** 中文比日文紧，段落的中文行数往往少于日文。盒会先被擦成底色，
少写的行就是背景，不必凑数——但**多写一行会溢出盒**，故有 OVERFLOW 检查。

    uv run python tools/bake_event_op.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.bake_sysgim_glow import (  # noqa: E402
    FONT_CASCADE, Glow, _core_mask, _merge_farther, _pm, measure_glow, render_glow,
)

REPO = Path(_REPO)


@dataclass(frozen=True)
class Spec:
    """一个面的配置。**新面加一个 Spec，别复制一份工具**——`tut_*` 会是第三个消费者。"""
    face: str                    #: 烤字面（决定用哪套字，见 tools/ui_font.py）
    src: Path                    #: 只读原图目录
    data: Path                   #: 译文数据 jsonl
    out: Path                    #: 产物目录
    blur_variant: float | None = None   #: 非 None 时另存一张 `_b` 虚化版

#: 分行阈值：相对该盒峰值墨距的比例。
#:
#: 取 0.5 而非字芯用的 0.85——**短行会被 0.85 切碎**：`op_2_a` 第 2 行
#: 「『もし』である、と。」只有标点与少量假名，中间几行没有字芯像素，0.85 下被切成
#: 3 段（识别成 6 行而非 5 行）。0.5 配 4px 的并段间隙，四个块全部与转写的行数吻合。
LINE_RATIO = 0.5

#: 并段间隙：相邻墨迹段的间距 ≤ 此值就算同一行。
#:
#: **两面共同约束出来的值。** op 那边 1–4 都给出正确行数（0.5 阈值下短行本就不碎，
#: 这个值对 op 不承重）；但 `cutin/cut_s_ex2` 的大字与小字注只隔 3px 空行
#: （31−27=4），取 4 会把两行并成一行、小字注被按大字的高度渲。取 3 是两面都成立的
#: 最大值——留最多的并段容忍度，同时不误并。
LINE_MERGE_GAP = 3


@dataclass
class Para:
    """一段的实测几何。"""
    tops: list[int]      #: 各行墨迹顶端的 y（绝对坐标）
    heights: list[int]   #: 各行墨迹高
    pitch: float         #: 行距（顶到顶的中位数）；单行段为 0
    left: int            #: 原文的齐左基准（只由非缩进行给出）
    indent_px: int       #: 原文的段首缩进量（实测）
    ink_x0: int          #: 原文整段墨迹的左端
    ink_x1: int          #: 原文整段墨迹的右端（开区间）


def segment_lines(im: Image.Image, box, g: Glow) -> list[tuple[int, int]]:
    """把一段切成行。返回各行的 (y0, y1] 闭开区间。"""
    l, t, r, b = box
    px = im.load()
    bgpm = _pm(g.bg)
    dist = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    peak = max(dist(px[x, y]) for y in range(t, b) for x in range(l, r))
    thr = peak * LINE_RATIO
    ys = [y for y in range(t, b) if any(dist(px[x, y]) >= thr for x in range(l, r))]
    out: list[list[int]] = []
    for y in ys:
        if out and y - out[-1][1] <= LINE_MERGE_GAP:
            out[-1][1] = y
        else:
            out.append([y, y])
    return [(a, c + 1) for a, c in out]


def measure_para(im: Image.Image, box, g: Glow, jp_lines: list[str]) -> Para:
    """量一段的行位置、行距与齐左基准。

    **行数与转写互相校验**：分段结果必须与 `jp` 的行数一致，不一致就抛错而不是
    将就——两条独立来源（图上的墨迹、人转写的文本）对不上，说明其中一条错了，
    这时候继续渲染只会把错误固化进产物。
    """
    bands = segment_lines(im, box, g)
    if len(bands) != len(jp_lines):
        raise ValueError(
            f"盒 {box}：图上分出 {len(bands)} 行，而 jp 转写是 {len(jp_lines)} 行——"
            f"两条独立来源不一致，先查清楚是哪边错了"
        )
    l, _t, r, _b = box
    px = im.load()
    bgpm = _pm(g.bg)
    dist = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    peak = max(dist(px[x, y]) for y0, y1 in bands for y in range(y0, y1) for x in range(l, r))
    thr = peak * LINE_RATIO
    lefts = []
    for y0, y1 in bands:
        xs = [x for x in range(l, r) for y in range(y0, y1) if dist(px[x, y]) >= thr]
        lefts.append(min(xs) if xs else l)
    # **齐左基准只能由「非缩进行」给出。**
    #
    # 曾经写成 `min(所有行左缘)`：多行段里既有缩进行又有齐左行时它是对的，但
    # **单行段那一行本身就是缩进的**——min 取到的是已含缩进的位置，外面再加一次
    # 缩进，就成了双重缩进。`op_1_a` 的单行段实测右偏 17px，且与第二段的缩进行
    # 不齐；而那正是玩家看到的第一行。
    #
    # 整段全是缩进行时，从观测值里把一个缩进量减掉。缩进量优先用同段实测
    # （缩进行与齐左行的左缘之差），拿不到就用该段的字芯高当一个全角字宽。
    flush = [i for i, ln in enumerate(jp_lines) if not ln.startswith("　")]
    indented = [i for i, ln in enumerate(jp_lines) if ln.startswith("　")]
    if flush and indented:
        indent_px = int(statistics.median([lefts[i] for i in indented])
                        - statistics.median([lefts[i] for i in flush]))
    else:
        indent_px = int(statistics.median([b[1] - b[0] for b in bands]))
    left = (min(lefts[i] for i in flush) if flush
            else min(lefts) - max(indent_px, 1))
    rights = []
    for y0, y1 in bands:
        xs = [x for x in range(l, r) for y in range(y0, y1) if dist(px[x, y]) >= thr]
        rights.append(max(xs) + 1 if xs else l)

    tops = [y0 for y0, _ in bands]
    # ⚠ 这里曾写成 `[y1 - y0 for _, y1 in bands]`——那个 `y0` 不是本推导式的变量，
    # 而是上面那个真 for 循环泄漏下来的**最后一行**的 y0，于是除末行外全是负数
    # （实测 [-43,-24,-6,13]），中位数 -24，`choose_size` 找不到满足 h≤-24 的档，
    # 一路掉到级联最小的 11px。四个块里三个字号都错了，而**图上看起来只是"偏小"**。
    heights = [y1 - y0 for y0, y1 in bands]
    pitch = statistics.median(
        [tops[i + 1] - tops[i] for i in range(len(tops) - 1)]
    ) if len(tops) > 1 else 0.0
    return Para(tops=tops, heights=heights, pitch=pitch, left=left,
                indent_px=max(indent_px, 1), ink_x0=min(lefts), ink_x1=max(rights))


#: 行高差 ≤ 此值就当作「同一档，差异是噪声」，全段用一个字号。
UNIFORM_HEIGHT_TOL = 2


def _fit_one(text: str, target_h: int, avail_w: int, sheet: str, face: str):
    """选出核高 ≤ target_h 且核宽 ≤ avail_w 的最大档。"""
    over = None
    for cand in FONT_CASCADE:
        bb = _core_mask(text, cand, sheet, face).getbbox()
        if bb is None:
            continue
        h, w = bb[3] - bb[1], bb[2] - bb[0]
        if h <= target_h and w <= avail_w:
            return cand, None
        if h <= target_h:
            over = f"{sheet} {cand}px 宽 {w} > 可用 {avail_w}「{text[:16]}」"
    return FONT_CASCADE[-1], over


def choose_size(zh_lines: list[str], para: Para, box, sheet: str,
                face: str = "sysgim") -> tuple[list[int], list[str]]:
    """逐行选字号，返回与 `zh_lines` 等长的字号表。

    承裁决 Y7——**锚在原行墨迹高，不锚行距**（按行距选会渲出比原文大一圈的字）。
    但 Y7 同时警告「同一段里一行 15px 一行 16px 会显得坏掉」。两条并不矛盾：

    - **行高差在噪声范围内**（≤ `UNIFORM_HEIGHT_TOL`）→ 全段取中位数，一个字号。
      op 的四段都是这种（各行高清一色 13）。
    - **行高成簇、差异是真的** → 逐行按自己的原行高选。`cutin/cut_s_ex2` 是这种：
      大字 21px + 小字注 13px，若取中位数 17，小字注会被渲成大字号。

    宽度对每一行单独判：最宽的那行不能超出盒。
    """
    avail_w = box[2] - box[0] - 2 * (para.left - box[0])
    spread = max(para.heights) - min(para.heights)
    uniform = spread <= UNIFORM_HEIGHT_TOL
    over: list[str] = []
    sizes: list[int] = []
    for i, s in enumerate(zh_lines):
        if not s.strip():
            sizes.append(FONT_CASCADE[-1])
            continue
        target = (int(statistics.median(para.heights)) if uniform
                  else para.heights[min(i, len(para.heights) - 1)])
        size, warn = _fit_one(s, target, avail_w, sheet, face)
        sizes.append(size)
        if warn:
            over.append(warn)
    return sizes, over


def bake_file(name: str, rows: list[dict], report: list[str], spec: "Spec") -> Image.Image:
    im = Image.open(spec.src / f"{name}.png").convert("RGBA")
    out = im.copy()
    plans = []
    boxes = []
    for meta in rows:
        box = tuple(meta["box"])
        boxes.append(box)
        g = measure_glow(im, box)
        jp_lines = meta["jp"].split("\n")
        para = measure_para(im, box, g, jp_lines)
        zh_lines = [s for s in meta["zh"].split("\n")]
        if len(zh_lines) > len(jp_lines):
            report.append(
                f"OVERFLOW {name} 段{meta['row']}：中文 {len(zh_lines)} 行 > "
                f"原文 {len(jp_lines)} 行，段落盒放不下"
            )
        sizes, warn = choose_size(zh_lines, para, box, name, spec.face)
        report += warn

        # ── 横向：复现原文块的**重心**，不是它的左缘 ────────────────────
        #
        # 起初照搬原文的齐左基准 `para.left`，结果整段明显塌向画面左侧：实测块心
        # 偏离 49–73px，左距 47–71 而右距 155–193。原因不是算错，是**目标定错了**
        # ——原文填满整宽（左右边距 52/52、53/53、58/59），块心正落在画面中心
        # 239.5–243.5；中文只有它 65–70% 长，同一个左缘下重心必然塌到左边。
        #
        # 所以该复现的是块心。段内结构不变：各行仍齐左，段首仍缩进一个字宽。
        cells = []
        for s, size in zip(zh_lines, sizes):
            if not s.strip():
                cells.append(None)
                continue
            cbb = _core_mask(s, size, name, spec.face).getbbox()
            cells.append((s, cbb[2] - cbb[0], cbb[3] - cbb[1],
                          size if s.startswith("　") else 0, size))
        # 按**真实墨迹范围**居中，不是按「含缩进的概念块」。
        #
        # 差别只在整段全是缩进行时显形（`op_1_a` 的单行段）：缩进那一截是空白，
        # 把它算进块宽再居中，墨迹就被推右半个缩进——实测偏 10.5px。取墨迹的
        # 实际左右端（最小缩进 → 最右端）来居中，两种情形都对。
        ink_lo = min(c[3] for c in cells if c)
        ink_hi = max(c[3] + c[1] for c in cells if c)
        cx = (para.ink_x0 + para.ink_x1) / 2
        left = round(cx - (ink_lo + ink_hi) / 2)
        # 不许越出盒；越出说明这段本就放不下，交给 OVERFLOW 那条报
        left = max(box[0] - ink_lo, min(left, box[2] - ink_hi))

        for i, c in enumerate(cells):
            if c is None:
                continue
            s, core_w, core_h, indent, size = c
            glyph = render_glow(s, size, g, name, spec.face)
            # 纵向：按实测行距落位，行内以**该行自己**的原墨迹高居中
            top = para.tops[0] + round(para.pitch * i) if para.pitch else para.tops[0]
            own_h = para.heights[min(i, len(para.heights) - 1)]
            gy = top + (own_h - core_h) // 2
            gx = left + indent
            halo = (glyph.width - core_w) // 2
            vhalo = (glyph.height - core_h) // 2
            plans.append((g, glyph, gx - halo, gy - vhalo))

    for box, meta in zip(boxes, rows):
        out.paste(measure_glow(im, box).bg, box)
    for g, glyph, ox, oy in plans:
        _merge_farther(out, glyph, ox, oy, g.bg)
    return out


def load_text(spec: "Spec") -> tuple[dict[str, list[dict]], list[str]]:
    """同 `bake_sysgim_glow.load_text`：空 `zh` 的图整张不渲染，避免半中半日。"""
    out: dict[str, list[dict]] = {}
    untranslated: set[str] = set()
    for line in spec.data.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not str(r.get("zh", "")).strip():
            untranslated.add(r["file"])
        out.setdefault(r["file"], []).append(r)
    for f in untranslated:
        out.pop(f, None)
    for v in out.values():
        v.sort(key=lambda r: r["row"])
    return out, sorted(untranslated)


def run(spec: "Spec", write: bool = True, label: str = "段落烤字") -> int:
    text, untranslated = load_text(spec)
    report: list[str] = []
    spec.out.mkdir(parents=True, exist_ok=True)
    for name in sorted(text):
        img = bake_file(name, text[name], report, spec)
        if write:
            img.save(spec.out / f"{name}.png")
        if spec.blur_variant is not None:
            # `_b` 由 `_a` 虚化而来，不单独渲染
            blurred = img.filter(ImageFilter.GaussianBlur(spec.blur_variant))
            if write:
                blurred.save(spec.out / f"{name[:-2]}_b.png")

    extra = (f"（另各生成一张 `_b` 虚化版，高斯 r={spec.blur_variant}）"
             if spec.blur_variant is not None else "")
    print(f"{label}：{len(text)} 张 / {sum(len(v) for v in text.values())} 段{extra}")
    if untranslated:
        print(f"待译（整张不渲染）：{len(untranslated)} 张 {untranslated}")
    for line in report:
        print(f"  {line}")
    return sum(1 for line in report if line.startswith("OVERFLOW"))


