#!/usr/bin/env python3
"""`png/sysgim/` 发光字族的中文烤字。

**发光是距离的函数——这一点是实测出来的，不是假定的。** 逐盒统计「到字芯的
距离 d」与「该距离处的 RGBA」，`sys_5_a` 的结果是：d=1 时 (236,145,92,211)、
d=2 (229,104,42,163)、d=3 (227,92,25,122)……颜色在 d=2–5 稳定在
(226,84,14) 附近（标准差个位数），alpha 单调衰减到 0。`sys_6_b` 同形，
只是发光色换成蓝 (110,125,225)。这正是 Photoshop 外发光的形状。

于是重建就是：渲中文字芯 → 算距离场 → 套这条实测曲线。

**模型的独立验证**在 `--verify`：拿**原图自己的字芯**过一遍同一条曲线，
重建出来的图与原图逐像素比对。曲线是从这张图拟合的，所以这不证明曲线的取值，
但它证明了那个承重假设——「发光只依赖到字芯的距离」。若原图的发光其实是各向
异性的（投影、单边光），重建会明显对不上。

不做的：`sys_1_i` 的箭头发光与文字连成一片，没有干净切口，留待单独处理。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

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
DATA = REPO / "data" / "sysgim_glow_text.jsonl"

FONT_CASCADE = (20, 19, 18, 17, 16, 15, 14, 13, 12, 11)

#: 字芯＝盒内 alpha 达到峰值这一比例的像素。取 0.85 是为了把抗锯齿边缘留给发光那侧。
CORE_ALPHA_RATIO = 0.85
#: 曲线量到多远。**实测各盒的收敛半径**：多数 5–11，`sys_5_i/j` 第一行到 16
#: （那一行字大、盒又宽，远处量到的是相邻字与盒角）。取 18 留余量；取 12 时
#: `sys_13_a` 的环在远端仍离底 14，被收敛检查挡下——那道检查是有效的。
MAX_DIST = 18
#: 与描边族同因：霞鹜文楷 Regular 太细，字芯蒙版到不了饱和。
FILL_GAIN = float(os.environ.get("ZND_UI_FILL_GAIN", 2.2))

#: **底存在与否，用「环的远端收不收敛到它」来验，不用占比或倍数来猜。**
#:
#: 试过两版都不成立：①要求众数占比 ≥15%——`sys_5_b` 字排得密，透明底只占 10.3%，
#: 被误判；②要求众数至少是第二名的 3 倍——`sys_5_c` 是 506 : 447，同样被误判。
#: 占比与倍数量的都是「底有多大一片」，而这与「底是不是唯一」无关。
#:
#: 真正该验的是模型自身的前提：发光衰减到远处应当**回到底色**。若众数取错了，
#: 远端环就不会收敛到它。这个判据直接测承重假设，且对字疏字密一视同仁。
MAX_TAIL_DEV = 6
#:
#: 早先这里卡的是「必须是透明底」，于是 `sys_2_b/c`（暗面板）、`sys_11_a`（半透明
#: 黑带）与整个 C 类（不透明纯色底）全被挡在外面。**实测表明那道限制是多余的**：
#: 这些盒的底逐行取众数都只有一个取值（`(0,0,0,179)` / `(0,0,0,255)` /
#: `(245,236,226,255)`），只要把环从「相对透明」改成「相对底色」，同一个模型就成立。
MIN_BG_DOMINANCE = 3.0

#: 判「这一行有没有发光」看的是环的**形状**，不是浓度。外发光按构造就是单调衰减；
#: 无发光的行，d=3 往外量到的其实是**邻字的抗锯齿边**，会忽高忽低。
#:
#: 实测 `sys_5_i`：第一行（有发光）164→113→68→33→15 单调；
#: 第二行（纯白小字，字距密）120→76→111→128→133，根本不衰减。
#: 先试过「d=4 的 alpha 够不够大」，正是被这条非单调的曲线骗过去的。
GLOW_PROBE_D = 5
GLOW_TAIL_MIN_A = 8

#: 本工具的适用前提是「字浮在透明底上，擦掉即可」。不满足的图在数据里标
#: `deferred: true`，译文照记但不渲染：
#:   sys_1_i  箭头发光与文字连成一片，无干净切口
#:   sys_11_a 字压在一整条半透明黑带上，清擦会把带子也擦掉（同 plot/ 的处境）
DEFERRED_NOTE = "见 data/sysgim_glow_text.jsonl 的 deferred 字段"


@dataclass
class Glow:
    #: 字芯的**预乘** RGBA（实测均值）
    core: tuple[float, float, float, float]
    #: 盒内的底色 RGBA（众数，非预乘——贴图时直接用）
    bg: tuple[int, int, int, int]
    #: 距离 d（1..MAX_DIST）处的**预乘** RGBA；无发光时全部等于预乘后的 bg
    ring: list[tuple[float, float, float, float]]


def _pm(p):
    """预乘：(r,g,b,a) → (r·a/255, g·a/255, b·a/255, a)。

    整条链（测环 / 求均值 / 渲染 / 比对）都在预乘空间里做，因为**「盖在底上」
    这件事只有在预乘空间里才是线性的**。非预乘空间里 alpha 趋零处的 RGB 是噪声：
    (255,0,0,1) 与 (0,0,255,1) 看上去一样却相差 255。
    """
    a = p[3]
    return (p[0] * a / 255, p[1] * a / 255, p[2] * a / 255, float(a))


def _unpm(q):
    """预乘 → RGBA。"""
    a = max(0.0, min(255.0, q[3]))
    if a < 0.5:
        return (0, 0, 0, 0)
    return tuple(min(255, max(0, round(q[i] * 255 / a))) for i in range(3)) + (round(a),)


def _dist_field(core: list[list[bool]], W: int, H: int) -> list[list[int]]:
    INF = 10**6
    d = [[INF] * W for _ in range(H)]
    q: deque = deque()
    for y in range(H):
        for x in range(W):
            if core[y][x]:
                d[y][x] = 0
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and d[ny][nx] > d[y][x] + 1:
                d[ny][nx] = d[y][x] + 1
                q.append((nx, ny))
    return d


def measure_glow(im: Image.Image, box) -> Glow:
    """从原图的一个盒子里量出「距离 → RGBA」这条曲线。"""
    l, t, r, b = box
    W, H = r - l, b - t
    px = im.load()
    n_all = W * H
    # 底取**盒边框**的众数，不取全盒众数。
    #
    # 全盒众数会在字密的盒里翻车：`sys_2_b` 行 3（亮态「あらすじ作成済」）几乎填满
    # 19px 的行，白色像素多过背景，于是底被测成 (255,255,255,255)——字芯与底整个
    # 反了过来，那一行渲成了一大团无晕的白字。文字总有边距，边框上就是底。
    border = (
        [px[x, t] for x in range(l, r)]
        + [px[x, b - 1] for x in range(l, r)]
        + [px[l, y] for y in range(t, b)]
        + [px[r - 1, y] for y in range(t, b)]
    )
    bg = Counter(border).most_common(1)[0][0]

    # 「离底多远」取代「alpha 多高」作为字芯判据：底可能是不透明的，那时 alpha
    # 恒为 255，按 alpha 判会把整盒都算成字芯。
    #
    # 距离在**预乘空间**里算。直接比 RGBA 会在透明底上出错：底是
    # (255,255,255,0)，橙色发光随 alpha 衰减时 RGB 一直是橙的，于是「离白色更远」，
    # 距离反而随 d 递增——单调性判据会因此把真发光判成无发光。预乘后
    # alpha→0 的像素自然趋近底，单调性才成立。
    bg_pm = _pm(bg)
    dist = lambda p: sum(abs(_pm(p)[i] - bg_pm[i]) for i in range(4))
    ink = [(x, y) for y in range(t, b) for x in range(l, r) if dist(px[x, y]) > 8]
    if not ink:
        raise ValueError(f"盒 {box} 里没有与底不同的像素")
    peak = max(dist(px[x, y]) for x, y in ink)
    thr = peak * CORE_ALPHA_RATIO
    core = [[dist(px[l + x, t + y]) >= thr for x in range(W)] for y in range(H)]
    n_core = sum(sum(row) for row in core)
    if n_core == 0:
        raise ValueError(f"盒 {box} 量不到字芯")

    core_px = [_pm(px[l + x, t + y]) for y in range(H) for x in range(W) if core[y][x]]
    core_pm = tuple(sum(p[i] for p in core_px) / len(core_px) for i in range(4))

    d = _dist_field(core, W, H)
    ring = []
    for k in range(1, MAX_DIST + 1):
        vals = [
            _pm(px[l + x, t + y])
            for y in range(H)
            for x in range(W)
            if d[y][x] == k
        ]
        if not vals:
            ring.append(bg_pm)
            continue
        # **普通均值**，在预乘空间里。早先这里按「离底的距离」加权，等于把少数
        # 亮像素放大——重建出来的晕比原图强，verify 平均偏差从 6–20 涨到 8–98。
        # 预乘空间里合成是线性的，算术平均就是正确的估计量。
        ring.append(tuple(sum(p[i] for p in vals) / len(vals) for i in range(4)))
    # 有没有发光看环**离底的距离**是否单调衰减——底不透明时 alpha 恒 255，
    # 按 alpha 判会把每一圈都看成「浓」。
    # 远端必须收敛回底色——这是环模型的前提，也是「众数取对了没有」的验法。
    ringdist = lambda q: sum(abs(q[i] - bg_pm[i]) for i in range(4))
    tail = ringdist(ring[-1])
    if tail > MAX_TAIL_DEV:
        raise ValueError(
            f"盒 {box} 的环在 d={MAX_DIST} 处仍离底 {tail}（容差 {MAX_TAIL_DEV}）"
            f"——底色 {bg} 恐怕取错了，或发光半径超出了 MAX_DIST"
        )

    head = [ringdist(r) for r in ring[:GLOW_PROBE_D]]
    monotone = all(head[i] >= head[i + 1] for i in range(len(head) - 1))
    if not (monotone and head[-1] >= GLOW_TAIL_MIN_A):
        ring = [bg_pm] * MAX_DIST
    return Glow(core_pm, bg, ring)


def _core_mask(text: str, size: int, sheet: str | None = None) -> Image.Image:
    font = _ui_truetype("sysgim", size, sheet)
    pad = MAX_DIST + 4
    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    l, t, rr, bb = d.textbbox((0, 0), text, font=font)
    m = Image.new("L", (rr - l + 2 * pad, bb - t + 2 * pad), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), text, font=font, fill=255)
    return m


def render_glow(text: str, size: int, g: Glow, sheet: str | None = None) -> Image.Image:
    """中文字芯 + 实测发光曲线。返回的图**已经含底**，直接盖到盒里即可。

    每个像素 = `lerp(该距离处的环色, 字芯色, 字芯蒙版)`。环色是绝对值（底已含在
    里面），故这一式对透明底与不透明底同样成立——这正是能把两条路径合成一条的原因。
    """
    m = _core_mask(text, size, sheet)
    W, H = m.size
    mp = m.load()
    core = [[mp[x, y] > 128 for x in range(W)] for y in range(H)]
    d = _dist_field(core, W, H)
    out = Image.new("RGBA", (W, H), g.bg)
    op = out.load()
    bg_pm = _pm(g.bg)
    for y in range(H):
        for x in range(W):
            ac = min(1.0, mp[x, y] / 255.0 * FILL_GAIN)
            k = d[y][x]
            base = g.ring[k - 1] if 1 <= k <= MAX_DIST else bg_pm
            op[x, y] = _unpm(
                tuple(base[i] * (1 - ac) + g.core[i] * ac for i in range(4))
            )
    return out


def load_text() -> tuple[dict[str, list[dict]], list[str]]:
    """返回 (可渲染的行, 待译的张)。

    **`zh` 为空的张整张不渲染，并且是整张、不是整行。** 原始语料先落盘、译文后补是
    刻意的两步走；但一张图上若有一行没译，只渲染其余行会得到一张**半中半日**的图——
    它看起来像"做完了"，而那正是最坏的失效形态。两个理由必须分开报：`deferred` 是
    「工具做不了」（如 sys_1_i 的箭头晕），`untranslated` 是「人还没译」。
    """
    out: dict[str, list[dict]] = {}
    untranslated: set[str] = set()
    for line in DATA.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("deferred"):
            continue
        if not str(r.get("zh", "")).strip():
            untranslated.add(r["file"])
        out.setdefault(r["file"], []).append(r)
    for f in untranslated:
        out.pop(f, None)
    for v in out.values():
        v.sort(key=lambda r: r["row"])
    return out, sorted(untranslated)


def _core_bbox(im: Image.Image, box, g: "Glow"):
    """原字芯（离底最远的那部分）的墨迹盒——不含发光晕。"""
    l, t, r, b = box
    px = im.load()
    bgpm = _pm(g.bg)
    dist = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    peak = max(dist(px[x, y]) for y in range(t, b) for x in range(l, r))
    thr = peak * CORE_ALPHA_RATIO
    pts = [(x, y) for y in range(t, b) for x in range(l, r) if dist(px[x, y]) >= thr]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bake_file(name: str, rows: list[dict], report: list[str]):
    im = Image.open(SYSGIM / f"{name}.png").convert("RGBA")
    out = im.copy()
    boxes = [tuple(r["box"]) for r in rows]

    # 先把所有盒擦成各自的底，再把各行的块合并进去。
    # **两步必须分开**：块自带底，若边擦边贴，后一行的擦除会抹掉前一行溢出过来的晕。
    plans = []
    for meta, box in zip(rows, boxes):
        g = measure_glow(im, box)
        bb = _core_bbox(im, box, g)
        if bb is None:
            raise ValueError(f"{name} 行{meta['row']}: 量不到原字芯墨迹")
        x0, y0, x1, y1 = bb
        target_h = y1 - y0 + 1
        avail_w, avail_h = box[2] - box[0], box[3] - box[1]

        size = FONT_CASCADE[-1]
        for cand in FONT_CASCADE:
            cbb = _core_mask(meta["zh"], cand, name).getbbox()
            if cbb and (cbb[3] - cbb[1]) <= target_h:
                size = cand
                break
        # 判「放不放得下」只看**字芯**。发光晕本来就会溢出行盒——原图也溢出，
        # 正因如此 sys_2_b 的八行在自动分段里才粘成一段。
        for cand in [c for c in FONT_CASCADE if c <= size]:
            cbb = _core_mask(meta["zh"], cand, name).getbbox()
            if cbb and (cbb[2] - cbb[0]) <= avail_w and (cbb[3] - cbb[1]) <= avail_h:
                if cand != size:
                    report.append(f"cascade {name} 行{meta['row']} {size}→{cand}px（字芯宽度）")
                size = cand
                break
        else:
            report.append(
                f"OVERFLOW {name} 行{meta['row']}「{meta['zh']}」字芯放不下 {avail_w}x{avail_h}"
            )

        glyph = render_glow(meta["zh"], size, g, name)
        cbb = _core_mask(meta["zh"], size, name).getbbox()
        core_w, core_h = cbb[2] - cbb[0], cbb[3] - cbb[1]

        # 原字芯在盒内的横向对齐，照搬到中文上
        # 居中判据的容差按盒宽取。绝对 3px 在 480px 的盒上太苛刻——`sys_11_a`
        # 原文左右边距 151 : 146，只差 5px 却被判成右对齐，中文整个被推到右边。
        lm, rm = x0 - box[0], box[2] - 1 - x1
        tol = max(3, round((box[2] - box[0]) * 0.02))
        if lm + tol < rm:
            gx = x0
        elif rm + tol < lm:
            gx = x1 + 1 - core_w
        else:
            gx = (x0 + x1) // 2 - core_w // 2
        gy = (y0 + y1) // 2 - core_h // 2
        halo = (glyph.width - core_w) // 2
        vhalo = (glyph.height - core_h) // 2
        plans.append((g, glyph, gx - halo, gy - vhalo))

    for (g, _, _, _), box in zip(plans, boxes):
        out.paste(g.bg, box)

    for g, glyph, ox, oy in plans:
        _merge_farther(out, glyph, ox, oy, g.bg)

    spill = _outside_box_violations(im, out, boxes)
    keep = [tuple(b) for r in rows for b in r.get("preserve", [])]
    bad = 0
    if keep:
        sp, dp = im.load(), out.load()
        for l, t, r, b in keep:
            for y in range(t, b):
                for x in range(l, r):
                    if sp[x, y] != dp[x, y]:
                        bad += 1
    if bad:
        report.append(f"PIXEL-VIOLATION {name}: 保留区被改动 {bad} 个像素")
    elif spill:
        report.append(f"spill {name}: 发光溢出行盒 {spill} 个像素（预期行为）")
    return out, bad


def _merge_farther(dst: Image.Image, tile: Image.Image, ox: int, oy: int, bg) -> None:
    """把 tile 并进 dst：**离底更远者胜**。

    块自带底，直接 paste 会把邻行的晕、乃至盒外本该保留的东西（`sys_11_a` 下方那
    行英文）一起盖掉。按「离底的距离」取胜方后：块里等于底的那些像素不会覆盖任何
    已有内容，而两行的晕重叠处取更强的一侧——与原图叠加发光的观感一致。
    """
    W, H = dst.size
    tp, dp = tile.load(), dst.load()
    bgpm = _pm(bg)
    far = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    for y in range(tile.height):
        yy = oy + y
        if not (0 <= yy < H):
            continue
        for x in range(tile.width):
            xx = ox + x
            if not (0 <= xx < W):
                continue
            src = tp[x, y]
            if far(src) > far(dp[xx, yy]):
                dp[xx, yy] = src


def _outside_box_violations(src: Image.Image, dst: Image.Image, boxes) -> int:
    W, H = src.size
    sp, dp = src.load(), dst.load()
    n = 0
    for y in range(H):
        for x in range(W):
            if any(l <= x < r and t <= y < b for (l, t, r, b) in boxes):
                continue
            if sp[x, y] != dp[x, y]:
                n += 1
    return n


def verify_model(name: str, boxes) -> list[tuple[int, float]]:
    """把原图自己的字芯过一遍实测曲线，与原图比对。

    验的是承重假设——发光只依赖「到字芯的距离」。各向异性的光（投影、单边）
    会在这里露馅。曲线是从同一张图拟合的，故这不验证曲线取值本身。
    """
    im = Image.open(SYSGIM / f"{name}.png").convert("RGBA")
    px = im.load()
    out = []
    for box in boxes:
        g = measure_glow(im, box)
        if all(r == _pm(g.bg) for r in g.ring):
            # 无发光行：那一圈墨迹是抗锯齿，由字芯蒙版本身复现，不走环模型。
            # 拿环模型去比会得出一个无意义的大偏差。
            out.append((-1, -1.0))
            continue
        l, t, r, b = box
        W, H = r - l, b - t
        bgpm = _pm(g.bg)
        dist = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
        peak = max(dist(px[l + x, t + y]) for y in range(H) for x in range(W))
        thr = peak * CORE_ALPHA_RATIO
        core = [[dist(px[l + x, t + y]) >= thr for x in range(W)] for y in range(H)]
        d = _dist_field(core, W, H)
        diffs = []
        for y in range(H):
            for x in range(W):
                dd = d[y][x]
                if dd == 0:
                    continue
                pg = _pm(px[l + x, t + y])
                pe = g.ring[dd - 1] if dd <= MAX_DIST else bgpm
                diffs.append(max(abs(pg[i] - pe[i]) for i in range(4)))
        out.append((max(diffs) if diffs else 0, sum(diffs) / len(diffs) if diffs else 0))
    return out


def run(write: bool = True, verify: bool = False) -> int:
    text, untranslated = load_text()
    report: list[str] = []
    OUTDIR.mkdir(parents=True, exist_ok=True)
    total_viol = 0
    for name in sorted(text):
        rows = text[name]
        img, viol = bake_file(name, rows, report)
        total_viol += viol
        if write:
            img.save(OUTDIR / f"{name}.png")
        if verify:
            for (mx, mean), meta in zip(verify_model(name, [tuple(r["box"]) for r in rows]), rows):
                if mx < 0:
                    print(f"  verify {name} 行{meta['row']}: 无发光行，环模型不适用")
                else:
                    print(f"  verify {name} 行{meta['row']}: 最大偏差 {mx:5.1f}  平均 {mean:.1f}")

    print(f"发光字族：{len(text)} 张 / {sum(len(v) for v in text.values())} 行")
    if untranslated:
        print(f"待译（整张不渲染，避免半中半日）：{len(untranslated)} 张 {untranslated}")
    deferred = sorted(
        {json.loads(l)["file"] for l in DATA.read_text(encoding="utf-8").splitlines()
         if l.strip() and json.loads(l).get("deferred")}
    )
    print(f"暂缓：{deferred}（{DEFERRED_NOTE}）")
    print(f"盒外像素改动：{total_viol}")
    for line in report:
        print("  " + line)
    if not report:
        print("  （无回落、无溢出、无越界）")
    return 1 if any(x.startswith(("OVERFLOW", "PIXEL-VIOLATION")) for x in report) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true", help="用原图字芯回放模型并比对")
    a = ap.parse_args(argv)
    return run(write=not a.check, verify=a.verify)


if __name__ == "__main__":
    raise SystemExit(main())
