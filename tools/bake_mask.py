#!/usr/bin/env python3
"""**遮盖**：把一张图里「要换掉的那层字连同它的晕」算成若干矩形，且不伤旁边
必须原样保留的字。这是两步法的第一步（第二步是嵌字，见 `bake_para_glow`）。

**为什么必须两步、且两个框不是同一个。** `sysgim/title_*` 那 12 张里，青色假名
小注紧挨着必须保留的英文大词。先前只有一个框两用：收紧到嵌字合适就盖不住小注
的晕（→ 产物上一圈矩形亮边），放大到盖得住就压到英文（→ 擦掉过英文的字芯）。
嵌字框量的是**字该多大、落在哪**；遮盖框量的是**旧墨到哪为止**——两件事。

## 承重的那条实测

发光是距离的确定函数（这一族与 `bake_sysgim_glow` 同一个 Photoshop 外发光）。
把 12 张里**离假名墨 ≥12px 的纯英文像素**按到英文字芯的**精确欧氏距离**分箱，
逐距的 alpha 上界是：

    d      2.828 3.000 3.162 3.606 4.000 4.123 4.243 4.472 5.000
    n        870  1550   988   963  1217   811   360   633   1418
    amax     153   143    53    42    16     8     8     3     0

**英文晕的外沿精确落在 d=√20≈4.472**：d=5.000 那一箱 1418 个样本的 alpha
全是 0。所以「擦掉这里会不会伤到英文」不必猜——查表即可。

⚠ **上一轮交接文档里「英文的蓝晕是大范围的，小注整个落在它的辉光场里」是错的。**
那条结论出自一版二值判据（小注足迹取 `G−R>8`，其余非透明像素一律算英文），
而**小注自己的字芯是白的**（`G−R≈0`）、抗锯齿边也是白的，于是被整片划进「英文
足迹」，膨胀 1px 后几乎盖住整个小注，报出「不可盖 73–89%」。实证：那 12 张里
被该判据划为「盒内英文足迹」的 165–330 个像素中，有 **65.6%–100%** 离真英文字芯
**>4px**（07–12 六张是 **100%**——那几张的小注与英文根本不相邻）。**是判据的
毛病，不是素材的毛病**；这已是同一个坑的第三次（见 bake-handoff-2026-08-29 §5.3）。
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

#: 字芯判据：高不透明 + 高亮度。与 `bake_para_glow.CORE_ALPHA/CORE_LUMA` 同值同义。
CORE_ALPHA, CORE_LUMA = 217, 150

#: 实测的「到字芯的精确欧氏距离 → 该处发光 alpha 的上界」。见模块头的表。
#: 末项 (5.0, 0) 是外沿：更远处恒为 0，故 `protect_alpha` 越界即返回 0。
GLOW_ALPHA_MAX = ((2.829, 153), (3.001, 143), (3.163, 53), (3.607, 42),
                  (4.001, 16), (4.124, 8), (4.244, 8), (4.473, 3), (5.001, 0))

#: **允许被擦掉的保留层发光强度上限（alpha）。**
#:
#: τ=0 等于「一个像素都不碰英文」，但那样 02–06/13 六张的小注顶行（正落在英文
#: 字芯下方 4.0px）擦不掉，残留 22–41px；τ=16 把残留压到 4–11px，代价是抹掉
#: 至多 alpha 16 ＝满量程的 6.3%，且只在英文晕的最外一圈。
#:
#: 取 16 而不是 42：实测的 alpha 上界阶梯是 153/143/53/42/16/8/8/3/0，
#: 42→16 是低段里最大的一级落差（2.6 倍），阈值落在这一级的下沿而不是贴着
#: 53/42 那两档的边缘（承 bake-handoff-2026-08-28 §5.6：阈值要落在空档里）。
PROTECT_TAU = 16

#: 判「有没有发光」时探到多远（`measure_glow(probe_d=...)`）。
#: `bake_sysgim_glow` 的默认 5 是按那几族的字号定的；被换掉的这层小注实测晕半径
#: 只有 4（环 146/36/13/3/1/0），在 d=5 处要求还剩强度等于要求晕超出自己的外沿，
#: 真发光会被判成没发光、环被压平成底色——渲出来的中文一点晕都没有。
GLOW_PROBE_D = 3

#: 遮盖区在旧墨外接盒之外再放多少像素。取 6 ＝实测的假名晕半径上界 5 再加 1，
#: 保证遮盖区的**外边界落在全透明的地方**——那正是先前「矩形亮边」的成因：
#: 旧框只圈到青色强部，框外还活着的晕被齐边留下，边界自己成了一个矩形。
ROI_PAD = 6


def _pm_dist_bg(p, bg) -> int:
    """预乘空间里离底的距离。与 `bake_sysgim_glow` 同一把尺子。"""
    a, ba = p[3] / 255, bg[3] / 255
    return sum(abs(p[i] * a - bg[i] * ba) for i in range(3)) + abs(p[3] - bg[3])


def protect_alpha(d: float) -> int:
    """到保留层字芯的距离 `d` 处，保留层发光 alpha 的实测上界。"""
    for lim, a in GLOW_ALPHA_MAX:
        if d < lim:
            return a
    return 0


def _components(mask, W, H):
    """8 连通分量。"""
    seen = [[False] * W for _ in range(H)]
    out = []
    for y in range(H):
        for x in range(W):
            if mask[y][x] and not seen[y][x]:
                stack = [(x, y)]
                seen[y][x] = True
                pts = []
                while stack:
                    a, b = stack.pop()
                    pts.append((a, b))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            u, v = a + dx, b + dy
                            if 0 <= u < W and 0 <= v < H and mask[v][u] and not seen[v][u]:
                                seen[v][u] = True
                                stack.append((u, v))
                out.append(pts)
    return out


def _edt(pts, W, H):
    """精确欧氏距离场。

    **不用 4 邻域 BFS**（`bake_sysgim_glow._dist_field` 那种曼哈顿距离）：
    发光是各向同性的，曼哈顿距离在对角方向高估 41%，而这里整个判据都压在
    「d 落在 4.472 还是 5.000」这一档上，41% 的畸变足以把结论翻过来。
    图只有百来像素见方，暴力算即可。
    """
    d = [[999.0] * W for _ in range(H)]
    if not pts:
        return d
    for y in range(H):
        for x in range(W):
            best = 1e18
            for a, b in pts:
                v = (a - x) * (a - x) + (b - y) * (b - y)
                if v < best:
                    best = v
                    if v == 0:
                        break
            d[y][x] = math.sqrt(best)
    return d


@dataclass
class MaskPlan:
    """一张图的遮盖方案。"""
    rects: list[tuple[int, int, int, int]]   #: 要擦成底的矩形（左, 上, 右, 下）
    roi: tuple[int, int, int, int]           #: 旧墨的作用域
    bg: tuple[int, int, int, int]            #: 底色
    protect: list[list[bool]]                #: 逐像素：True＝保留层的地盘，不许写
    ink_core: list[list[bool]]               #: 逐像素：True＝旧墨的**实心笔画**
    residual: list[tuple[int, int]]          #: 擦不掉的旧墨像素
    residual_max_alpha: int

    def protect_at(self, x: int, y: int) -> bool:
        """True＝保留层的发光足迹，一律不看、不写。"""
        return self.protect[y][x]

    def is_ink_core(self, x: int, y: int) -> bool:
        """量本层的发光环时，从哪里起算距离。

        底透明时「实心」的正确判据是 **alpha**，不是离底的距离：纯青的细笔
        `(36,119,160,255)` 不透明度拉满，只是颜色暗，按离底距离量只有白芯的 56%。
        """
        return self.ink_core[y][x]

    def can_write(self, x: int, y: int) -> bool:
        """嵌字时哪里可以落笔：**恰好等于擦掉的那片**。

        新字的晕于是只可能出现在旧墨原本的作用域内，且一个像素也碰不到保留层。
        作用域的外边界在全透明处（`ROI_PAD` 保证），所以那条边界不会显形。
        """
        l, t, r, b = self.roi
        return l <= x < r and t <= y < b and not self.protect[y][x]


def _erase_allowed(im: Image.Image, boxes, tau: int):
    """算出「哪些像素可以擦」。返回 (allowed, protect, roi, bg, kana_ink, d_keep)。

    分层是按**盒归属**判的，不是按颜色：落在译文盒里的字芯连通块属于「要换掉的
    那层」，其余属于「必须保留的那层」。颜色只用来把青色细笔补进旧墨
    （纯青像素如 `(36,119,160,255)` 的 min(RGB)=36 达不到字芯亮度门槛）。
    """
    px = im.load()
    W, H = im.size
    core = [[px[x, y][3] >= CORE_ALPHA and min(px[x, y][:3]) >= CORE_LUMA
             for x in range(W)] for y in range(H)]

    def in_boxes(x, y):
        return any(l <= x < r and t <= y < b for (l, t, r, b) in boxes)

    keep_core, drop_core = [], []
    for pts in _components(core, W, H):
        inside = sum(1 for p in pts if in_boxes(*p))
        (drop_core if inside * 2 > len(pts) else keep_core).extend(pts)

    # 旧墨 = 盒内字芯 ∪ 青色像素（已验证的分离判据：G−R>25 且 B≥G）
    old_ink = set(drop_core)
    for y in range(H):
        for x in range(W):
            p = px[x, y]
            if p[3] > 0 and p[1] - p[0] > 25 and p[2] >= p[1]:
                old_ink.add((x, y))
    if not old_ink:
        raise ValueError("量不到要换掉的那层墨")

    xs = [p[0] for p in old_ink]
    ys = [p[1] for p in old_ink]
    roi = (max(0, min(xs) - ROI_PAD), max(0, min(ys) - ROI_PAD),
           min(W, max(xs) + 1 + ROI_PAD), min(H, max(ys) + 1 + ROI_PAD))

    d_keep = _edt(keep_core, W, H)
    protect = [[protect_alpha(d_keep[y][x]) > tau for x in range(W)] for y in range(H)]
    allowed = [[roi[0] <= x < roi[2] and roi[1] <= y < roi[3] and not protect[y][x]
                for x in range(W)] for y in range(H)]

    border = ([px[x, roi[1]] for x in range(roi[0], roi[2])]
              + [px[x, roi[3] - 1] for x in range(roi[0], roi[2])])
    bg = max(set(border), key=border.count)
    return allowed, protect, roi, bg, old_ink, d_keep


def _rects_of(allowed, roi):
    """把允许区**精确**拆成矩形：逐列取极大连通段，再把段完全相同的相邻列并起来。

    是精确拆分（不多盖也不少盖），所以矩形数就是边界阶梯的台阶数——英文在小注
    上方且下缘平整时只有个位数。
    """
    l, t, r, b = roi
    runs = {}
    for x in range(l, r):
        cur = []
        y = t
        while y < b:
            if allowed[y][x]:
                y0 = y
                while y < b and allowed[y][x]:
                    y += 1
                cur.append((y0, y))
            else:
                y += 1
        runs[x] = tuple(cur)
    rects = []
    x = l
    while x < r:
        if not runs[x]:
            x += 1
            continue
        x2 = x + 1
        while x2 < r and runs[x2] == runs[x]:
            x2 += 1
        for (y0, y1) in runs[x]:
            rects.append((x, y0, x2, y1))
        x = x2
    return rects


def plan(im: Image.Image, boxes, tau: int = PROTECT_TAU) -> MaskPlan:
    """算一张图的遮盖方案。"""
    px = im.load()
    W, H = im.size
    allowed, protect, roi, bg, old_ink, d_keep = _erase_allowed(im, boxes, tau)
    rects = _rects_of(allowed, roi)

    # 残留：擦不掉、又确实带旧墨颜色的像素。**用擦后的图判**，不是用原图猜。
    d_old = _edt(sorted(old_ink), W, H)
    residual = [(x, y) for y in range(H) for x in range(W)
                if not allowed[y][x] and px[x, y][3] > 0
                and d_old[y][x] <= 5 and px[x, y][1] - px[x, y][0] > 8]
    ink_core = [[(x, y) in old_ink and px[x, y][3] >= CORE_ALPHA
                 for x in range(W)] for y in range(H)]
    return MaskPlan(rects=rects, roi=roi, bg=bg, protect=protect,
                    ink_core=ink_core, residual=residual,
                    residual_max_alpha=max((px[x, y][3] for x, y in residual), default=0))


def apply(dst: Image.Image, mp: MaskPlan) -> None:
    """按方案把矩形擦成底色。"""
    for r in mp.rects:
        dst.paste(mp.bg, r)


def check_keep_intact(src: Image.Image, dst: Image.Image, mp: MaskPlan) -> int:
    """保留层的地盘必须逐字节不变。返回被改动的像素数（应为 0）。"""
    sp, dp = src.load(), dst.load()
    W, H = src.size
    return sum(1 for y in range(H) for x in range(W)
               if mp.protect[y][x] and sp[x, y] != dp[x, y])


def check_old_ink_gone(src: Image.Image, dst: Image.Image, mp: MaskPlan) -> list:
    """擦后，作用域内不该再有旧墨——除了 `residual` 那几粒。

    这是**闭合检查**：遮盖区的外边界必须落在全透明处，否则就是又切出一条边。
    """
    dp = dst.load()
    l, t, r, b = mp.roi
    resid = set(mp.residual)
    return [(x, y, dp[x, y]) for y in range(t, b) for x in range(l, r)
            if dp[x, y][3] > 0 and not mp.protect[y][x] and (x, y) not in resid]
