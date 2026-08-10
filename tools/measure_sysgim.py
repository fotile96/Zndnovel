#!/usr/bin/env python3
"""`png/sysgim/` 描边字家族的版面测绘。

这一族的辨识特征是**调色板只有两个源色**：填充纯白 `(255,255,255,255)`、
描边褐 `(73,59,59,~217)`，中间的几十档全是两者之间的抗锯齿插值；禁用态把
填充换成 `(166,154,145,255)`。故「是不是这一族」不靠文件名清单判定，靠实测
——清单会过期，判据不会。

输出的是**给渲染器用的规格**：行距、每行墨迹盒、对齐方式、填充/描边取色。
"""

from __future__ import annotations

import argparse
import json
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

warnings.filterwarnings("ignore", message="Palette images with Transparency")

REPO = Path(__file__).resolve().parent.parent
SYSGIM = REPO / "png" / "sysgim"

FILL_ON = (255, 255, 255)
FILL_OFF = (166, 154, 145)  # 禁用态
STROKE = (73, 59, 59)

#: 判定「属于描边字族」的阈值：可见像素里落在 白↔褐 或 灰↔褐 连线附近的比例。
FAMILY_MIN_SHARE = 0.90
#: 判到线段的最大色距（RGB 欧氏），抗锯齿插值都在这个带内。
_LINE_TOL = 12.0


def _near_segment(c, a, b) -> float:
    """点 c 到线段 ab 的距离。"""
    ax, ay, az = a
    bx, by, bz = b
    vx, vy, vz = bx - ax, by - ay, bz - az
    wx, wy, wz = c[0] - ax, c[1] - ay, c[2] - az
    den = vx * vx + vy * vy + vz * vz
    t = 0.0 if den == 0 else max(0.0, min(1.0, (wx * vx + wy * vy + wz * vz) / den))
    dx, dy, dz = wx - t * vx, wy - t * vy, wz - t * vz
    return (dx * dx + dy * dy + dz * dz) ** 0.5


@dataclass
class Row:
    top: int
    bottom: int
    left: int
    right: int

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    @property
    def width(self) -> int:
        return self.right - self.left + 1


@dataclass
class Spec:
    name: str
    size: tuple[int, int]
    is_outline_family: bool
    family_share: float
    rows: list[Row]
    pitch: int | None
    align: str  # left | center | right | mixed
    has_disabled_fill: bool


def _ink_rows(px, W: int, H: int, alpha_min: int = 8) -> list[tuple[int, int]]:
    on = [any(px[x, y][3] >= alpha_min for x in range(W)) for y in range(H)]
    segs, s = [], None
    for y, v in enumerate(on):
        if v and s is None:
            s = y
        elif not v and s is not None:
            segs.append((s, y - 1))
            s = None
    if s is not None:
        segs.append((s, H - 1))
    return segs


def _split_by_pitch(segs, pitch: int, top0: int, n: int) -> list[tuple[int, int]]:
    """行与行贴死时（无空行），按固定行距强切。"""
    return [(top0 + i * pitch, top0 + (i + 1) * pitch - 1) for i in range(n)]


def measure(path: Path, n_rows: int | None = None, pitch: int | None = None) -> Spec:
    im = Image.open(path).convert("RGBA")
    W, H = im.size
    px = im.load()

    vis = [px[x, y] for y in range(H) for x in range(W) if px[x, y][3] > 0]
    near = sum(
        1
        for p in vis
        if min(
            _near_segment(p[:3], FILL_ON, STROKE),
            _near_segment(p[:3], FILL_OFF, STROKE),
        )
        <= _LINE_TOL
    )
    share = near / len(vis) if vis else 0.0
    has_off = any(p[:3] == FILL_OFF for p in vis)

    segs = _ink_rows(px, W, H)
    if n_rows is not None and len(segs) < n_rows:
        # 行贴死了（自然分段数偏少）：按行距强切。行距优先用调用方给的，
        # 否则用总墨迹高整除。
        t0 = segs[0][0] if segs else 0
        t1 = segs[-1][1] if segs else H - 1
        p = pitch or round((t1 - t0 + 1) / n_rows)
        segs = _split_by_pitch(segs, p, t0, n_rows)
    # 自然分段数**多于**预期时**不强切**：那说明调用方给的行数是错的，
    # 强切会照着错误行数把图切开、把每行渲到别人的位置上，而调用方的
    # 「行数对不对得上」检查将永远为真——一道恒绿的闸。让它对不上。

    rows = []
    for a, b in segs:
        xs = [x for x in range(W) for y in range(a, b + 1) if px[x, y][3] >= 8]
        if not xs:
            continue
        ys = [y for y in range(a, b + 1) if any(px[x, y][3] >= 8 for x in range(W))]
        rows.append(Row(min(ys), max(ys), min(xs), max(xs)))

    pitches = {rows[i + 1].top - rows[i].top for i in range(len(rows) - 1)}
    pit = pitches.pop() if len(pitches) == 1 else None

    align = _align_of(rows, W)
    return Spec(path.stem, (W, H), share >= FAMILY_MIN_SHARE, round(share, 4), rows, pit, align, has_off)


def _align_of(rows: list[Row], W: int, tol: int = 3) -> str:
    if len(rows) < 2:
        return "single"
    lefts = [r.left for r in rows]
    rights = [W - 1 - r.right for r in rows]
    centers = [(r.left + r.right) / 2 for r in rows]
    if max(lefts) - min(lefts) <= tol:
        return "left"
    if max(rights) - min(rights) <= tol:
        return "right"
    if max(centers) - min(centers) <= tol:
        return "center"
    return "mixed"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", nargs="+", help="sysgim 文件名（不带 .png）")
    ap.add_argument("--rows", type=int, default=None, help="预期行数（行贴死时必给）")
    ap.add_argument("--pitch", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = []
    for n in a.names:
        s = measure(SYSGIM / f"{n}.png", a.rows, a.pitch)
        out.append(s)
        if not a.json:
            fam = "描边族" if s.is_outline_family else f"非描边族({s.family_share})"
            print(
                f"{s.name:12s} {s.size[0]:3d}x{s.size[1]:<3d} {fam:12s} "
                f"行{len(s.rows)} 距{s.pitch} {s.align}"
                + (" +禁用态" if s.has_disabled_fill else "")
            )
            for i, r in enumerate(s.rows):
                print(f"    {i+1}: y{r.top}-{r.bottom}(h{r.height}) x{r.left}-{r.right}(w{r.width})")
    if a.json:
        print(json.dumps([asdict(s) for s in out], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
