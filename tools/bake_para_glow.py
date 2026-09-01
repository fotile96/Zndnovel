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
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageFilter

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools import bake_mask  # noqa: E402
from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.ui_font import size_bias as _ui_size_bias  # noqa: E402
from tools.bake_sysgim_glow import (  # noqa: E402
    FONT_CASCADE, Glow, MAX_TAIL_DEV, _core_mask, _merge_farther, _pm,
    measure_glow, render_glow,
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
    #: 横向对齐。`center`＝复现原文块的**重心**（裁决 Y15，op/cutin 用）；
    #: `left`＝复现原文的**左缘**。前提不同结论就不同：Y15 的理由是原文填满整宽、
    #: 中文只有 65–70% 长，照搬左缘会整块塌左；而模式画面框那三张是**贴着屏幕
    #: 左上角的一行标签**，居中反而会在标题条左侧留出一个豁口。
    align: str = "center"
    #: 把渲染夹在盒内，盒外一个像素不动。默认关——op 的相邻段本就靠溢出的晕
    #: 互相衔接，夹了会在段间切出硬边。模式画面框要开：它下方 7px 处就是**必须
    #: 原样保留**的英文大词，而发光半径 18px 一定会盖过去。
    clip_to_box: bool = False
    #: 字号锚在**字芯**高，而不是 `segment_lines` 判的行高。
    #:
    #: 行高是用 `LINE_RATIO=0.5` 的距离阈值量的，**把发光的晕算了进去**——
    #: `title_*` 的小注实测行高比真字芯高 1–2px，锚在虚高上渲出来就偏大
    #: （原字芯 7px 的几张渲成了 10px，用户看图指出）。晕越强的面偏得越多，
    #: 故做成选项而不是一律改：event/op 与 cutin 的产物已按行高定案并经用户看过。
    core_anchor: bool = False
    #: **遮盖与嵌字分两步**（`tools/bake_mask.py`）。None＝老行为：把译文盒整个
    #: 擦成底、再把新字夹在同一个盒里。
    #:
    #: `"glow_footprint"`＝按实测的发光足迹另算一套**遮盖矩形**：擦掉旧墨连同它
    #: 的晕（外边界落在全透明处，故不会切出矩形亮边），同时逐像素避开必须保留的
    #: 那层字的发光足迹。**两步的框不是同一个**——译文盒仍只管字该多大、落在哪。
    #: 设了它就不要再设 `clip_to_box`：那是矩形夹，而这里的保留区不是矩形。
    #:
    #: `"geo_footprint"`＝E 类剩余 5 张（sys_2_a/3_a、sys_12_a/b/c）的变体：底
    #: 不透明/是照片、晕色不同、保留层的晕长得多，title 的 alpha 上界表不适用。
    #: 保护判据改成**几何足迹**（逐保留层一个实测半径，见 tools/bake_mask.py
    #: `plan_geo`），geo 参数逐张放在数据行的 `geo` 字段里。
    mask_mode: str | None = None
    #: 强制所有行使用同一字号（跳过自动选号）。用于跨段/跨文件统一字号。
    force_size: int | None = None

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


def segment_lines(im: Image.Image, box, g: Glow,
                  line_ratio: float = LINE_RATIO) -> list[tuple[int, int]]:
    """把一段切成行。返回各行的 (y0, y1] 闭开区间。"""
    l, t, r, b = box
    px = im.load()
    bgpm = _pm(g.bg)
    dist = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    peak = max(dist(px[x, y]) for y in range(t, b) for x in range(l, r))
    thr = peak * line_ratio
    ys = [y for y in range(t, b) if any(dist(px[x, y]) >= thr for x in range(l, r))]
    out: list[list[int]] = []
    for y in ys:
        if out and y - out[-1][1] <= LINE_MERGE_GAP:
            out[-1][1] = y
        else:
            out.append([y, y])
    return [(a, c + 1) for a, c in out]


def measure_para(im: Image.Image, box, g: Glow, jp_lines: list[str],
                 line_ratio: float = LINE_RATIO) -> Para:
    """量一段的行位置、行距与齐左基准。

    **行数与转写互相校验**：分段结果必须与 `jp` 的行数一致，不一致就抛错而不是
    将就——两条独立来源（图上的墨迹、人转写的文本）对不上，说明其中一条错了，
    这时候继续渲染只会把错误固化进产物。

    `line_ratio`：墨迹阈值的比例覆盖。默认 0.5×盒内峰值；**渐变墨**（sys_1_i
    行1：棕字 374 里有白热点 1020）会被 0.5×1020=510 的阈值整片落选，量出的
    左缘偏右 2px——按 geo 给 0.35 让墨体入选。
    """
    bands = segment_lines(im, box, g, line_ratio)
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
    thr = peak * line_ratio
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
                face: str = "sysgim",
                force_size: int | None = None) -> tuple[list[int], list[str]]:
    """逐行选字号，返回与 `zh_lines` 等长的字号表。

    承裁决 Y7——**锚在原行墨迹高，不锚行距**（按行距选会渲出比原文大一圈的字）。
    但 Y7 同时警告「同一段里一行 15px 一行 16px 会显得坏掉」。两条并不矛盾：

    - **行高差在噪声范围内**（≤ `UNIFORM_HEIGHT_TOL`）→ 全段取中位数，一个字号。
      op 的四段都是这种（各行高清一色 13）。
    - **行高成簇、差异是真的** → 逐行按自己的原行高选。`cutin/cut_s_ex2` 是这种：
      大字 21px + 小字注 13px，若取中位数 17，小字注会被渲成大字号。

    宽度对每一行单独判：最宽的那行不能超出盒。

    `force_size`：跳过自动选号，所有内容行强制使用该字号。用于跨段/跨文件统一。
    """
    if force_size is not None:
        return ([force_size if ln.strip() else FONT_CASCADE[-1]
                 for ln in zh_lines], [])
    avail_w = box[2] - box[0] - 2 * (para.left - box[0])
    spread = max(para.heights) - min(para.heights)
    uniform = spread <= UNIFORM_HEIGHT_TOL
    bias = _ui_size_bias(face, sheet)
    over: list[str] = []
    sizes: list[int] = []
    for i, s in enumerate(zh_lines):
        if not s.strip():
            sizes.append(FONT_CASCADE[-1])
            continue
        target = (int(statistics.median(para.heights)) if uniform
                  else para.heights[min(i, len(para.heights) - 1)])
        size, warn = _fit_one(s, target, avail_w, sheet, face)
        if bias:
            size, bwarn = _apply_bias(s, size, bias, avail_w, sheet, face)
            warn = warn or bwarn
        sizes.append(size)
        if warn:
            over.append(warn)
    if uniform:
        content = [s for s, ln in zip(sizes, zh_lines) if ln.strip()]
        if content:
            m = min(content)
            sizes = [m if ln.strip() else s for s, ln in zip(sizes, zh_lines)]
    return sizes, over


def _apply_bias(text: str, size: int, bias: int, avail_w: int,
                sheet: str, face: str) -> tuple[int, str | None]:
    """把算出来的档位抬（或压）`bias` 档，**但不许撞出盒外**。

    加成是风格选择，溢出不是——所以撞盒时逐档退回到放得下的最大档并报告，
    而不是渲一张超出盒子的图。逐行加，不是整段缩放：字号本就是**逐行**选的
    （`cut_s_ex2` 是 21px 标题 + 13px 小字注），统一缩放会把那个差抹掉。
    """
    # 加成把**整个可用区间**一起平移，而不是被级联的天花板吞掉。
    # 级联上限 20px 是「没有哪一行原文比它更高」得来的；显式加成正是要主动越过
    # 那条线——不平移的话，本就顶到 20px 的卡（`cut_s_s8`）会原地不动，
    # 于是 24 张里 23 张变大、1 张没变，而且不报错。
    lo = FONT_CASCADE[-1] + min(bias, 0)
    hi = FONT_CASCADE[0] + max(bias, 0)
    want = min(max(size + bias, lo), hi)
    for cand in range(want, size - 1, -1) if want > size else [want]:
        bb = _core_mask(text, cand, sheet, face).getbbox()
        if bb is not None and bb[2] - bb[0] <= avail_w:
            warn = (None if cand == want else
                    f"{sheet} 字号加成 {bias:+d} 到 {want}px 会超出可用宽 {avail_w}，"
                    f"退回 {cand}px「{text[:16]}」")
            return cand, warn
    return size, (f"{sheet} 字号加成 {bias:+d} 无一档放得下，维持 {size}px"
                  f"「{text[:16]}」")


#: 字芯判据：高不透明 + 高亮度。与 `measure_glow` 的 `CORE_ALPHA_RATIO` 同精神，
#: 但这里要的是**纵向范围**而非颜色，故直接取阈值，不必再拟合。
CORE_ALPHA, CORE_LUMA = 200, 170


def _core_heights(im: Image.Image, box, para: Para) -> list[int]:
    """逐行的**字芯**高（不含晕）。量不到字芯的行退回原行高。"""
    px = im.load()
    out = []
    for i, top in enumerate(para.tops):
        h = para.heights[min(i, len(para.heights) - 1)]
        ys = [y for y in range(top, top + h) for x in range(box[0], box[2])
              if px[x, y][3] > CORE_ALPHA and min(px[x, y][:3]) > CORE_LUMA]
        out.append(max(ys) - min(ys) + 1 if ys else h)
    return out


def _white_core_bbox(im: Image.Image, box) -> tuple[int, int, int, int] | None:
    """盒内白芯（α≥217 且 min(RGB)≥150）的 bbox；没有则 None。

    作 `ref_center`/`ref_right` 对齐的**参照物**：12 系是下方英文行（含两侧
    `-`，bbox 中心即两短线跨距的中点），面板两张是上方英文大词（右缘对齐）。
    """
    l, t, r, b = box
    px = im.load()
    pts = [(x, y) for y in range(max(0, t), min(im.height, b))
           for x in range(max(0, l), min(im.width, r))
           if px[x, y][3] >= 217 and min(px[x, y][:3]) >= 150]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bake_file(name: str, rows: list[dict], report: list[str], spec: "Spec") -> Image.Image:
    im = Image.open(spec.src / f"{name}.png").convert("RGBA")
    out = im.copy()
    plans = []
    boxes = []
    mp = None
    if spec.mask_mode == "glow_footprint":
        mp = bake_mask.plan(im, [tuple(r["box"]) for r in rows],
                            twin=rows[0].get("twin"))
        if mp.residual:
            report.append(
                f"residual {name}: 旧墨有 {len(mp.residual)} 个像素压在保留层的发光里，"
                f"擦不掉（最亮 alpha {mp.residual_max_alpha}）"
            )
        if mp.post_writes:
            # 重建了多少、强度掉到多少，要说出来——静默的修补读起来就像「本来就干净」
            hi = max(v[3] for v in mp.post_writes.values())
            report.append(
                f"twin {name}: 按孪生态重建 {len(mp.post_writes)} 粒残留"
                f"（重建后最亮 alpha {hi}）"
            )
    elif spec.mask_mode == "geo_footprint":
        geo = rows[0].get("geo")
        if not geo:
            raise ValueError(f"{name}: mask_mode=geo_footprint 但数据行没有 geo 字段")
        mp = bake_mask.plan_geo(im, [tuple(r["box"]) for r in rows], geo,
                                fill_softs=[r.get("fill_soft") for r in rows],
                                bgs=[tuple(r.get("bg", geo["bg"])) for r in rows])
        if mp.protected_glow:
            report.append(
                f"protected-glow {name}: {len(mp.protected_glow)} 个旧墨晕像素落在"
                f"保留层足迹内原样保留（最亮 dev "
                f"{max(d for _, _, d in mp.protected_glow)}）"
            )
    elif spec.mask_mode is not None:
        raise ValueError(f"未知的 mask_mode：{spec.mask_mode!r}")
    for meta in rows:
        box = tuple(meta["box"])
        boxes.append(box)
        # `erase`＝**只擦不写**：这一盒的原文抹掉，不落任何中文。
        #
        # 与「待译」（空 zh）是两回事，故用独立字段而不是靠空 zh 推断：待译要整张
        # 跳过（免得半中半日），只擦要照常出活。用在**中文注不如没有**的地方——
        # 主菜单 12 项的小注只有 7px 高，中文四字注在这个像素预算下必然糊成一团
        # （2026-09-01 用户裁定：抹掉日文小注、留英文大词）。
        if meta.get("erase"):
            continue
        # 保留层的地盘不参与量环——盒里混着它的晕，不排除就会把它当成本层的晕。
        # 字芯也由 mask 给：默认判据会漏掉纯青的细笔，漏掉的笔画会变成假的远场晕。
        geo = (rows[0].get("geo", {})
               if spec.mask_mode == "geo_footprint" else {})
        g = (measure_glow(im, box) if mp is None else
             measure_glow(im, box, ignore=mp.protect_at, core_of=mp.is_ink_core,
                          bg=tuple(meta.get("bg", mp.bg)),
                          probe_d=geo.get("probe_d", bake_mask.GLOW_PROBE_D),
                          tail_tol=geo.get("tail_tol", MAX_TAIL_DEV),
                          core_ratio_hi=meta.get(
                              "core_ratio_hi", geo.get("core_ratio_hi"))))
        if geo.get("taper"):
            # 晕的物理死距已实测（r_old）：ring 在此之外是底/照片的残渣，不是晕。
            # 12b 的量环盒只有 11 行高、tail_tol 又为照片放宽，远端环灌满了照片
            # 纹理；照写进新字远场就是一圈浑浊。**只该用于晕场会被重建/清掉的
            # 版面**；长行整行保留晕场的版面（sys_1_i）不能开——沿行方向的
            # 远端环是真实晕，taper 掉会让新字的晕铺不满原晕的范围。
            bgpm = _pm(g.bg)
            g.ring = [bgpm if k >= geo["r_old"] else ring
                      for k, ring in enumerate(g.ring, 1)]
        jp_lines = meta["jp"].split("\n")
        para = measure_para(im, box, g, jp_lines, line_ratio=meta.get(
            "line_ratio", geo.get("line_ratio", LINE_RATIO)))
        zh_lines = [s for s in meta["zh"].split("\n")]
        if len(zh_lines) > len(jp_lines):
            report.append(
                f"OVERFLOW {name} 段{meta['row']}：中文 {len(zh_lines)} 行 > "
                f"原文 {len(jp_lines)} 行，段落盒放不下"
            )
        if spec.core_anchor:
            para = replace(para, heights=_core_heights(im, box, para))
        sizes, warn = choose_size(zh_lines, para, box, name, spec.face,
                                  force_size=spec.force_size)
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
                          size if s.startswith("　") else 0, size,
                          cbb[0], cbb[1]))
        # 按**真实墨迹范围**居中，不是按「含缩进的概念块」。
        #
        # 差别只在整段全是缩进行时显形（`op_1_a` 的单行段）：缩进那一截是空白，
        # 把它算进块宽再居中，墨迹就被推右半个缩进——实测偏 10.5px。取墨迹的
        # 实际左右端（最小缩进 → 最右端）来居中，两种情形都对。
        ink_lo = min(c[3] for c in cells if c)
        ink_hi = max(c[3] + c[1] for c in cells if c)
        # 行级对齐（数据字段 `align`，盖过 Spec）：`ref_center`＝与参照物 bbox
        # 中心对齐；`ref_right`＝新墨右缘对齐参照物右缘。参照物＝geo 第一个
        # 保留组的白芯 bbox（12 系＝英文行含两侧 `-`；面板＝英文大词）。
        # 用户 2026-08-30：原假名块自身与英文差 3.5–5.5px，照搬它的重心会把
        # 偏差原样带进成品。
        align = meta.get("align", spec.align)
        ref_bbox = None
        if align.startswith("ref_"):
            ref_bbox = _white_core_bbox(im, rows[0]["geo"]["keep"][0]["box"])
            if ref_bbox is None:
                raise ValueError(f"{name}: align={align} 但参照组量不到白芯")
        if align == "left":
            left = para.left - ink_lo
        elif align == "ref_center" and ref_bbox:
            left = round((ref_bbox[0] + ref_bbox[2] + 1) / 2
                         - (ink_lo + ink_hi) / 2)
        elif align == "ref_right" and ref_bbox:
            left = round(ref_bbox[2] + 1 - ink_hi)
        else:
            cx = (para.ink_x0 + para.ink_x1) / 2
            left = round(cx - (ink_lo + ink_hi) / 2)
        # 不许越出盒；越出说明这段本就放不下，交给 OVERFLOW 那条报
        left = max(box[0] - ink_lo, min(left, box[2] - ink_hi))

        for i, c in enumerate(cells):
            if c is None:
                continue
            s, core_w, core_h, indent, size, ink_dx, ink_dy = c
            glyph = render_glow(s, size, g, name, spec.face)
            # 纵向：按实测行距落位，行内以**该行自己**的原墨迹高居中
            top = para.tops[0] + round(para.pitch * i) if para.pitch else para.tops[0]
            if meta.get("vcenter") and para.pitch and len(zh_lines) < len(jp_lines):
                # 中文行数少于日文时整块垂直居中（sys_1_i 行2+3 合并为一行）：
                # 不居中则单行贴在第一行原位，下方留出一整行空白。
                top += round(para.pitch * (len(jp_lines) - len(zh_lines)) / 2)
            own_h = para.heights[min(i, len(para.heights) - 1)]
            gy = top + (own_h - core_h) // 2
            gx = left + indent
            # 贴片里的墨迹**不一定居中**：`_core_mask` 按 `textbbox` 加等边距，
            # 而 textbbox 含字体的边距——「。」这类全角标点右侧几乎是空的，墨迹
            # 因此偏左。早先按 `(贴片宽 − 墨迹宽)/2` 反推贴点，等于假定它居中，
            # 实测在以「。」结尾的行上差 5px。改用 `getbbox()` 给的真实偏移。
            # （cutin/event 现有译文都不带尾部标点，实测偏差恰为 0，故产物不变。）
            clip = (mp.can_write if mp is not None
                    else (box if spec.clip_to_box else None))
            plans.append((g, glyph, gx - ink_dx, gy - ink_dy, clip))

    if mp is not None:
        bake_mask.apply(out, mp)
    else:
        for box, meta in zip(boxes, rows):
            out.paste(measure_glow(im, box).bg, box)
    for g, glyph, ox, oy, clip in plans:
        _merge_farther(out, glyph, ox, oy, g.bg, bounds=clip)
    if mp is not None:
        hurt = bake_mask.check_keep_intact(im, out, mp,
                                           skip_ink=spec.mask_mode == "geo_footprint")
        if hurt:
            report.append(f"PIXEL-VIOLATION {name}: 保留层被改动 {hurt} 个像素")
    return out


def load_text(spec: "Spec") -> tuple[dict[str, list[dict]], list[str]]:
    """同 `bake_sysgim_glow.load_text`：空 `zh` 的图整张不渲染，避免半中半日。

    带 `erase` 的行不算待译——它的空 `zh` 是**裁定**不是缺口（见 `bake_file`）。
    """
    out: dict[str, list[dict]] = {}
    untranslated: set[str] = set()
    for line in spec.data.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not str(r.get("zh", "")).strip() and not r.get("erase"):
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
            dst = spec.out / f"{name}.png"
            # `file` 可以带子目录（模式画面框那三张分处 png/music 与 png/graphic，
            # `src` 取的是两者的公共父目录）。产物照搬那层子目录，回注时不必再猜
            # 哪张回哪个目录——但那样顶层 mkdir 就不够了。
            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst)
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


