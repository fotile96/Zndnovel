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
import sys
import warnings
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

warnings.filterwarnings("ignore", message="Palette images with Transparency")

REPO = Path(__file__).resolve().parent.parent
SYSGIM = REPO / "png" / "sysgim"
OUTDIR = REPO / "build" / "sysgim"
FONT_PATH = REPO / "third_party" / "LXGWWenKai-Regular.ttf"
DATA = REPO / "data" / "sysgim_glow_text.jsonl"

FONT_CASCADE = (20, 19, 18, 17, 16, 15, 14, 13, 12, 11)

#: 字芯＝盒内 alpha 达到峰值这一比例的像素。取 0.85 是为了把抗锯齿边缘留给发光那侧。
CORE_ALPHA_RATIO = 0.85
#: 曲线量到多远。超出后 alpha 已经不足 1/255。
MAX_DIST = 12
#: 与描边族同因：霞鹜文楷 Regular 太细，字芯蒙版到不了饱和。
FILL_GAIN = 2.2

#: **本工具的前提**：字浮在透明底上，擦掉即可。盒内全透明像素的占比低于此值，
#: 说明字是压在底上的（暗面板、半透明色带…），环测量会把底色当成晕、重建出一圈
#: 黑边——`sys_2_b/c`（暗面板）与 `sys_11_a`（半透明黑带）都栽在这里。
#: 实测：可做的行透明占比 18–62%，压底的行是 0.0%。
MIN_TRANSPARENT_SHARE = 0.05

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
    core_rgb: tuple[int, int, int]
    core_alpha: int
    #: 距离 d（1..MAX_DIST）处的 (r,g,b,a)。d=0 是字芯本身。
    ring: list[tuple[int, int, int, int]]


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
    vis = [px[x, y] for y in range(t, b) for x in range(l, r) if px[x, y][3] > 0]
    if not vis:
        raise ValueError(f"盒 {box} 里没有可见像素")
    n_all = (r - l) * (b - t)
    if (n_all - len(vis)) / n_all < MIN_TRANSPARENT_SHARE:
        raise ValueError(
            f"盒 {box} 的底不是透明的（全透明像素仅 {(n_all-len(vis))/n_all:.1%}）"
            "——字压在底上，本工具的前提不成立"
        )
    peak = max(p[3] for p in vis)
    thr = peak * CORE_ALPHA_RATIO
    core = [[px[l + x, t + y][3] >= thr for x in range(W)] for y in range(H)]
    n_core = sum(sum(row) for row in core)
    if n_core == 0:
        raise ValueError(f"盒 {box} 量不到字芯")

    core_px = [px[l + x, t + y] for y in range(H) for x in range(W) if core[y][x]]
    core_rgb = tuple(round(sum(p[i] for p in core_px) / len(core_px)) for i in range(3))

    d = _dist_field(core, W, H)
    ring = []
    for dist in range(1, MAX_DIST + 1):
        vals = [
            px[l + x, t + y]
            for y in range(H)
            for x in range(W)
            if d[y][x] == dist and px[l + x, t + y][3] > 0
        ]
        if not vals:
            ring.append((0, 0, 0, 0))
            continue
        # 颜色按 alpha 加权：alpha 趋零处的 RGB 是噪声，不该拉平均值
        wsum = sum(p[3] for p in vals) or 1
        rgb = tuple(round(sum(p[i] * p[3] for p in vals) / wsum) for i in range(3))
        a = round(sum(p[3] for p in vals) / len(vals))
        ring.append((*rgb, a))
    head = [r[3] for r in ring[:GLOW_PROBE_D]]
    monotone = all(head[i] >= head[i + 1] for i in range(len(head) - 1))
    if not (monotone and head[-1] >= GLOW_TAIL_MIN_A):
        ring = [(0, 0, 0, 0)] * MAX_DIST
    return Glow(core_rgb, peak, ring)


def _core_mask(text: str, size: int) -> Image.Image:
    font = ImageFont.truetype(str(FONT_PATH), size)
    pad = MAX_DIST + 4
    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    l, t, rr, bb = d.textbbox((0, 0), text, font=font)
    m = Image.new("L", (rr - l + 2 * pad, bb - t + 2 * pad), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), text, font=font, fill=255)
    return m


def render_glow(text: str, size: int, g: Glow) -> Image.Image:
    """中文字芯 + 实测发光曲线。"""
    m = _core_mask(text, size)
    W, H = m.size
    mp = m.load()
    core = [[mp[x, y] > 128 for x in range(W)] for y in range(H)]
    d = _dist_field(core, W, H)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    op = out.load()
    for y in range(H):
        for x in range(W):
            ac = min(1.0, mp[x, y] / 255.0 * FILL_GAIN)
            dist = d[y][x]
            if dist == 0 or dist > MAX_DIST:
                gr, gg, gb, ga = (0, 0, 0, 0)
            else:
                gr, gg, gb, ga = g.ring[dist - 1]
            a_g = ga / 255.0
            a = ac + a_g * (1 - ac)
            if a <= 0:
                continue
            w = ac / a
            rgb = tuple(
                round(g.core_rgb[i] * w + (gr, gg, gb)[i] * (1 - w)) for i in range(3)
            )
            op[x, y] = (*rgb, round(a * g.core_alpha))
    return out.crop(out.getbbox() or (0, 0, W, H))


def load_text() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in DATA.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("deferred"):
                continue
            out.setdefault(r["file"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["row"])
    return out


def _ink_bbox(im: Image.Image, box, thr: int):
    l, t, r, b = box
    px = im.load()
    pts = [(x, y) for y in range(t, b) for x in range(l, r) if px[x, y][3] >= thr]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bake_file(name: str, rows: list[dict], report: list[str]):
    im = Image.open(SYSGIM / f"{name}.png").convert("RGBA")
    out = im.copy()
    boxes = [tuple(r["box"]) for r in rows]

    for meta, box in zip(rows, boxes):
        g = measure_glow(im, box)
        # 目标尺寸取原字芯（不含发光晕）的墨迹盒
        peak = g.core_alpha
        bb = _ink_bbox(im, box, int(peak * CORE_ALPHA_RATIO))
        if bb is None:
            raise ValueError(f"{name} 行{meta['row']}: 量不到原字芯墨迹")
        x0, y0, x1, y1 = bb
        target_h = y1 - y0 + 1
        avail_w, avail_h = box[2] - box[0], box[3] - box[1]

        size = FONT_CASCADE[-1]
        for cand in FONT_CASCADE:
            core = _core_mask(meta["zh"], cand)
            cbb = core.getbbox()
            if cbb is None:
                continue
            if (cbb[3] - cbb[1]) <= target_h:
                size = cand
                break
        # 判「放不放得下」只看**字芯**。发光晕本来就会溢出行盒——原图也溢出，
        # 正因如此 sys_2_b 的八行才在自动分段里粘成一段。拿含晕的整块去比，
        # 会把每一行都判成溢出。
        for cand in [c for c in FONT_CASCADE if c <= size]:
            cbb = _core_mask(meta["zh"], cand).getbbox()
            if cbb and (cbb[2] - cbb[0]) <= avail_w and (cbb[3] - cbb[1]) <= avail_h:
                if cand != size:
                    report.append(f"cascade {name} 行{meta['row']} {size}→{cand}px（字芯宽度）")
                size = cand
                break
        else:
            report.append(f"OVERFLOW {name} 行{meta['row']}「{meta['zh']}」字芯放不下 {avail_w}x{avail_h}")
        glyph = render_glow(meta["zh"], size, g)

        cbb = _core_mask(meta["zh"], size).getbbox()
        core_w, core_h = cbb[2] - cbb[0], cbb[3] - cbb[1]

        # 原字芯在盒内的横向对齐，照搬到中文上
        lm, rm = x0 - box[0], box[2] - 1 - x1
        if lm + 3 < rm:
            gx = x0
        elif rm + 3 < lm:
            gx = x1 + 1 - core_w
        else:
            gx = (x0 + x1) // 2 - core_w // 2
        gy = (y0 + y1) // 2 - core_h // 2
        # glyph 里字芯的偏移——定位要对齐字芯，不是对齐含晕的整块
        halo = (glyph.width - core_w) // 2
        vhalo = (glyph.height - core_h) // 2
        out.paste((0, 0, 0, 0), box)
        out.alpha_composite(glyph, (gx - halo, gy - vhalo))

    # 发光**本来就会**溢出行盒（原图也溢出，正因如此 sys_2_b 的八行才粘成一段），
    # 故盒外有改动不等于出错。真正不能碰的区域写在数据的 `preserve` 里，单独硬检。
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
        if not any(a for *_, a in g.ring):
            # 无发光行：那一圈墨迹是抗锯齿，由字芯蒙版本身复现，不走环模型。
            # 拿环模型去比会得出一个无意义的大偏差。
            out.append((-1, -1.0))
            continue
        l, t, r, b = box
        W, H = r - l, b - t
        thr = g.core_alpha * CORE_ALPHA_RATIO
        core = [[px[l + x, t + y][3] >= thr for x in range(W)] for y in range(H)]
        d = _dist_field(core, W, H)
        diffs = []
        for y in range(H):
            for x in range(W):
                dist = d[y][x]
                if dist == 0:
                    continue
                got = px[l + x, t + y]
                exp = g.ring[dist - 1] if dist <= MAX_DIST else (0, 0, 0, 0)
                # **比预乘值**：alpha 趋零处的 RGB 是噪声，直接比会把
                # (255,0,0,1) 与 (0,0,255,1) 算成差 255，而它们看上去一模一样。
                pg = [got[i] * got[3] // 255 for i in range(3)] + [got[3]]
                pe = [exp[i] * exp[3] // 255 for i in range(3)] + [exp[3]]
                diffs.append(max(abs(pg[i] - pe[i]) for i in range(4)))
        out.append((max(diffs) if diffs else 0, sum(diffs) / len(diffs) if diffs else 0))
    return out


def run(write: bool = True, verify: bool = False) -> int:
    text = load_text()
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
                    print(f"  verify {name} 行{meta['row']}: 最大偏差 {mx:3d}  平均 {mean:.1f}")

    print(f"发光字族：{len(text)} 张 / {sum(len(v) for v in text.values())} 行")
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
