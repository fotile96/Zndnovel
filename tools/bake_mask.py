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
from dataclasses import dataclass, field
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


def _pm(p):
    a = p[3] / 255
    return (p[0] * a, p[1] * a, p[2] * a, float(p[3]))


def _unpm(q):
    a = max(0.0, min(255.0, q[3]))
    if a < 0.5:
        return (0, 0, 0, 0)
    return tuple(min(255, max(0, round(q[i] * 255 / a))) for i in range(3)) + (round(a),)


def photo_fill(im: Image.Image, region: list[list[bool]],
               roi: tuple[int, int, int, int], protect, bg) -> Image.Image:
    """非平底重建：在 `region` 内解拉普斯拉方程，边界取足迹外的**原图**像素。

    用于照片底（sys_12_b）与渐变底（sys_12_a 的底 alpha 实测 232–242 在缓变，
    平底填充会留下台阶）。预乘空间**四个通道一起解**（含 alpha——12a 要重建的
    正是 alpha）。

    为什么不用线性插值：sys_12_b 的照片在对角亮带的边缘穿过足迹，逐行插值把
    边缘抹平（实测照片像素误差 max 147）；拉普斯拉从四面八方取边界，实测足迹外
    差分恰为 0、足迹内无字形残迹（放大看图定案）。

    `protect` 里的像素（保留层）**不得当边界**：roi 网格常撞进保留层的行
    （12a/12b 的 roi 底行就是英文），白芯作边界会把白色引进重建区。它们以
    `bg` 的名义值固定成「墙」——既不参与也不污染。

    **图外格子是「未知」，不是边界。** 早先把它们当 (0,0,0,0) 的固定边界，
    而 12b 的擦除区大范围贴着 y=0——整条解被拽向全透明（实测 α 11–142，
    原图 237–247）。改为未知后解自然延伸，顶/左缘不再塌。
    """
    out = im.copy()
    op = out.load()
    px = im.load()
    l, t, r, b = roi
    W, H = r - l + 2, b - t + 2
    bgpm = _pm(bg)
    wall = [[(l <= l - 1 + i < r and t <= t - 1 + j < b
              and protect[t - 1 + j][l - 1 + i]
              and not region[t - 1 + j][l - 1 + i])
             for i in range(W)] for j in range(H)]
    f = [[[0.0] * W for _ in range(H)] for _ in range(4)]
    known = [[True] * W for _ in range(H)]
    for j in range(H):
        for i in range(W):
            x, y = l - 1 + i, t - 1 + j
            if not (0 <= x < im.width and 0 <= y < im.height):
                known[j][i] = False            # 图外：未知，参与迭代不落盘
                continue
            if wall[j][i]:
                for c in range(4):
                    f[c][j][i] = bgpm[c]                  # 名义底色成墙
            elif not (l <= x < r and t <= y < b and region[y][x]):
                p = _pm(px[x, y])
                for c in range(4):
                    f[c][j][i] = p[c]
            else:
                known[j][i] = False
    for c in range(4):
        tot = n = 0
        for j in range(H):
            for i in range(W):
                if known[j][i]:
                    tot += f[c][j][i]; n += 1
        v = tot / max(n, 1)
        for j in range(H):
            for i in range(W):
                if not known[j][i]:
                    f[c][j][i] = v
    for _ in range(600):
        for c in range(4):
            for j in range(H):
                for i in range(W):
                    if known[j][i]:
                        continue
                    # 网格边缘的未知格用 Neumann（只平均存在的邻居）：
                    # 图外方向没有数据，梯度为零地延伸进去。
                    nb = []
                    if j > 0:
                        nb.append(f[c][j-1][i])
                    if j < H - 1:
                        nb.append(f[c][j+1][i])
                    if i > 0:
                        nb.append(f[c][j][i-1])
                    if i < W - 1:
                        nb.append(f[c][j][i+1])
                    f[c][j][i] = sum(nb) / len(nb)
    for y in range(t, b):
        for x in range(l, r):
            if region[y][x]:
                i, j = x - l + 1, y - t + 1
                op[x, y] = _unpm((f[0][j][i], f[1][j][i], f[2][j][i], f[3][j][i]))
    return out


def plan_geo(im: Image.Image, boxes, geo: dict) -> MaskPlan:
    """几何足迹遮盖方案。`geo` 逐张给：

        keep:   [{"box": (l,t,r,b), "r": 半径, "kind": "white"|"bright:N"}, …]
        r_old:  旧墨（假名）晕的足迹半径（像素）
        bg:     底色（照片底也给名义色，供量偏差/闭合用）
        photo:  true＝足迹内拉普斯拉重建（sys_12_b）
        glow_floor: 判「还有旧墨晕」的可见性地板（预乘 L1）
        probe_d / tail_tol: 量环参数（转给 measure_glow）

    数字全部出自 2026-08-29 的实测（docs/ops/bake-sysgim-inventory.md「E 类版面
    测绘」节），逐张落在 data 的 geo 字段里，这里不做任何猜测。
    """
    px = im.load()
    W, H = im.size
    bgpm = _pm(geo["bg"])
    dev = lambda p: sum(abs(_pm(p)[i] - bgpm[i]) for i in range(4))
    floor = geo["glow_floor"]
    r_old = geo["r_old"]

    def is_white(x, y):
        p = px[x, y]
        return p[3] >= CORE_ALPHA and min(p[:3]) >= CORE_LUMA

    # ── 旧墨字芯：白芯连通块按盒归属分（和 `plan` 同一判据）──────────────
    core = [[is_white(x, y) for x in range(W)] for y in range(H)]
    drop_core = set()
    for pts in _components(core, W, H):
        inside = sum(1 for x, y in pts
                     if any(l <= x < r and t <= y < b for (l, t, r, b) in boxes))
        if inside * 2 > len(pts):
            drop_core.update(pts)
    if not drop_core:
        raise ValueError("量不到要换掉的那层墨")
    d_old = _edt(sorted(drop_core), W, H)

    # ── 未归属连通块自查 ───────────────────────────────────────────────
    # 白芯块既不属于要换的层、也不在任何保留组盒里、又贴着旧墨（≤ r_old+6）：
    # 多半是要换那层的漏字（sys_12_a 的尾「ー」芯是粉的、独立成块、盒没圈住，
    # 结果只擦掉半截，产物上漂着一截短横）。有它就当场炸，别让产物背着它。
    drop_bbox = (min(p[0] for p in drop_core), min(p[1] for p in drop_core),
                 max(p[0] for p in drop_core), max(p[1] for p in drop_core))
    near = r_old + 6
    for pts in _components(core, W, H):
        inside = sum(1 for x, y in pts
                     if any(l <= x < r and t <= y < b for (l, t, r, b) in boxes))
        if inside * 2 > len(pts):
            continue
        in_keep = sum(1 for x, y in pts
                      if any(l <= x < r and t <= y < b
                             for g in geo["keep"] for (l, t, r, b) in [g["box"]]))
        if in_keep * 2 > len(pts):
            continue
        cx, cy = pts[len(pts) // 2]
        dx = max(drop_bbox[0] - cx, 0, cx - drop_bbox[2])
        dy = max(drop_bbox[1] - cy, 0, cy - drop_bbox[3])
        # 只有「能活到足迹之外」的块才值得报：整块都在足迹内的碎芯反正会被
        # 遮盖区一起擦掉（sys_12_a 的 (18,7) 2px 碎芯属于此类，无害）。
        if math.hypot(dx, dy) > near:
            continue
        if all(d_old[y][x] < r_old for x, y in pts):
            continue
        raise ValueError(
                f"白芯连通块 {pts[0]}…{pts[-1]}（{len(pts)}px）不属于要换的层、"
                f"也不在任何保留组的盒里，却距旧墨 ≤{near}px——要么是漏圈的旧墨，"
                f"要么是漏声明的保留元素，先查清楚"
            )

    # ── 保留层：逐组字芯 + 逐组足迹半径 ────────────────────────────────
    protect = [[False] * W for _ in range(H)]
    keep_core = set()
    keep_edts = []
    for g in geo["keep"]:
        l, t, r, b = g["box"]
        kind = g.get("kind", "white")
        if kind == "white":
            pts = [(x, y) for y in range(max(0, t), min(H, b))
                   for x in range(max(0, l), min(W, r)) if is_white(x, y)]
        else:  # "bright:N"
            th = float(kind.split(":", 1)[1])
            pts = [(x, y) for y in range(max(0, t), min(H, b))
                   for x in range(max(0, l), min(W, r)) if dev(px[x, y]) > th]
        if not pts:
            raise ValueError(f"保留组 {g['box']} 量不到字芯")
        keep_core.update(pts)
        dg = _edt(pts, W, H)
        keep_edts.append((dg, g["r"]))
        for y in range(H):
            row = protect[y]
            drow = dg[y]
            for x in range(W):
                if drow[x] < g["r"]:
                    row[x] = True
    # 「一切保留层晕场之外」：旧墨自查只在这里跑。排除半径取该组的**实测死距**
    # （geo 里 `death`，缺省 r+2）——保留层的晕会拖到足迹半径外好几像素
    # （sys_2 绿晕 alpha=11 的尾巴在 d_sm≈12），重叠区里混色让逐像素判据必然
    # 误报（这是前三轮同一堵墙），所以不在它的晕场里判旧墨。死距之外保留层
    # 晕真为零，那里超地板的像素才必然是旧墨——这道自查的职责是抓 r_old 量错
    # 的数据事故，不是裁决重叠区（那由 protected_glow 与看图负责）。
    deaths = [g.get("death", g["r"] + 2) for g in geo["keep"]]
    dg_min = [[min(dg[y][x] for dg, _r in keep_edts) for x in range(W)]
              for y in range(H)]
    beyond_keep_glow = [[all(dg[y][x] >= death
                             for (dg, _r), death in zip(keep_edts, deaths))
                         for x in range(W)] for y in range(H)]

    # ── 擦除区：旧墨足迹 − 保留层足迹 ＋ 字芯豁免 ──────────────────────
    xs = [p[0] for p in drop_core]
    ys = [p[1] for p in drop_core]
    roi = (max(0, min(xs) - int(r_old) - 2), max(0, min(ys) - int(r_old) - 2),
           min(W, max(xs) + 1 + int(r_old) + 2), min(H, max(ys) + 1 + int(r_old) + 2))
    ink_core = [[(x, y) in drop_core for x in range(W)] for y in range(H)]
    allowed = [[False] * W for _ in range(H)]
    protected_glow = []
    for y in range(roi[1], roi[3]):
        for x in range(roi[0], roi[2]):
            do = d_old[y][x]
            if do >= r_old:
                # 闭合自查：只扫 r_old..r_old+2 这条**晕尾带**——旧墨的晕到 r_old
                # 应已衰减到地板以下。不扫整个 roi：更远处是保留层自己的地盘
                # （框的填充与抗锯齿、渐变底），与旧墨无关，扫了必然误报。
                if r_old <= do < r_old + 2 and beyond_keep_glow[y][x] \
                        and not geo.get("photo") and dev(px[x, y]) > floor:
                    raise ValueError(
                        f"({x},{y}) 在足迹外 {do:.1f}px 处仍有旧墨色 "
                        f"dev={dev(px[x, y]):.0f} > 地板 {floor}——r_old={r_old} 不够"
                    )
                continue
            if protect[y][x]:
                if ink_core[y][x]:
                    allowed[y][x] = True      # 字芯豁免：同位替换
                elif (x, y) not in keep_core and dev(px[x, y]) > floor:
                    # 保留层自己的字芯不算「旧墨晕」——它只是恰好落在旧墨
                    # 足迹半径内（两层只隔 4px 时必然发生）。
                    protected_glow.append((x, y, round(dev(px[x, y]))))
                continue
            allowed[y][x] = True

    # ── 写带：新字墨迹的合法领土（替换语义）────────────────────────────
    # 旧墨 bbox ±2px。汉字比假名高约 1px 且笔画位置不同，新字顶行必然撞进
    # 大标题晕的保护区——只豁免「旧字芯像素」时，没恰好落在旧芯上的顶行
    # 全被拦（sys_2_a 四个汉字顶上被削平，2026-08-30 用户反馈）。带内排除
    # 硬保护（缩略图框等，`hard: true` 的组）与保留层字芯：那两处一个像素不让。
    keep_core_mask = [[(x, y) in keep_core for x in range(W)] for y in range(H)]
    protect_hard = [[False] * W for _ in range(H)]
    for (dg, rg), g in zip(keep_edts, geo["keep"]):
        if not g.get("hard"):
            continue
        for y in range(H):
            drow = dg[y]
            row = protect_hard[y]
            for x in range(W):
                if drow[x] < rg:
                    row[x] = True
    xs = [p[0] for p in drop_core]
    ys = [p[1] for p in drop_core]
    band = [[False] * W for _ in range(H)]
    slack = 2
    for y in range(max(0, min(ys) - slack), min(H, max(ys) + 1 + slack)):
        for x in range(max(0, min(xs) - slack), min(W, max(xs) + 1 + slack)):
            if not protect_hard[y][x] and not keep_core_mask[y][x]:
                band[y][x] = True

    rects = _rects_of(allowed, roi)
    fill = (photo_fill(im, allowed, roi, protect, geo["bg"])
            if geo.get("photo") else None)

    # ── 幽灵晕清理（透明底重叠区）────────────────────────────────────
    # 旧墨黑晕与保留层彩晕叠在同一批像素上。黑加进混合只改变**幅值**、不改变
    # **色相**（pm_rgb 方向仍指着晕色），于是：
    #   - 无彩暗像素（黑晕本体）→ 归透明；
    #   - 亮灰像素按 d_old 近者归属（旧墨 AA 清掉 / 保留层 AA 不动）；
    #   - 彩色且 pm 方向与晕色一致（cos≥0.95）→ 重写为**纯晕色**、α＝沿晕色
    #     的投影幅值——黑被剥掉，晕恢复饱和。字母边缘的白晕过渡（粉/浅绿，
    #     cos≈0.8）与离保留层字芯 ≤2px 的像素天然排除，一个字都不动。
    # 强度模型在这里两个方向都会错（厚晕处环中位数低估→残留暗痕；绿主导处
    # 整层 alpha 被当黑减→透明洞，2026-08-30 用户反馈实测），色相不会。
    post_writes: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    glow = geo.get("glow_rgb")
    if geo.get("ghost_subtract") and glow:
        ch = [v / 255.0 for v in glow]
        ch_norm = math.sqrt(sum(v * v for v in ch))
        ch = [v / ch_norm for v in ch]
        gmax = max(glow)
        for y in range(roi[1], roi[3]):
            for x in range(roi[0], roi[2]):
                if not (protect[y][x] and d_old[y][x] < r_old
                        and not ink_core[y][x] and (x, y) not in keep_core):
                    continue
                p = px[x, y]
                if p[3] == 0:
                    continue
                lo, hi = min(p[:3]), max(p[:3])
                if hi - lo > 24:
                    # 彩色：方向与晕色一致才剥黑，否则不动
                    if dg_min[y][x] < 2:
                        continue              # 贴着保留层字芯：它的 AA 区，别碰
                    q = _pm(p)
                    mag = q[0] * ch[0] + q[1] * ch[1] + q[2] * ch[2]
                    qn = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2)
                    if qn < 1e-6 or mag < 0.15 * p[3]:
                        continue
                    if mag / qn < 0.95:
                        continue              # 方向偏离晕色（白晕过渡等）：不动
                    a = round(min(mag * 255.0 / gmax, float(p[3])))
                    post_writes[(x, y)] = (glow[0], glow[1], glow[2], a)
                    continue
                if hi <= 120:
                    post_writes[(x, y)] = (0, 0, 0, 0)   # 暗灰＝黑晕本体
                elif d_old[y][x] < dg_min[y][x]:
                    post_writes[(x, y)] = (0, 0, 0, 0)   # 亮灰贴旧墨＝旧墨 AA
                # 其余亮灰＝保留层 AA，不动
        # 被清掉的像素不再是「原样保留」——两份账必须互斥，报告才不撒谎
        protected_glow = [g for g in protected_glow if g[:2] not in post_writes]

    return MaskPlan(rects=rects, roi=roi, bg=tuple(geo["bg"]), protect=protect,
                    ink_core=ink_core, residual=[], residual_max_alpha=0,
                    fill=fill, protected_glow=protected_glow, geo_exemption=True,
                    writable=allowed, post_writes=post_writes, write_band=band)


def check_apply_exact(src: Image.Image, dst: Image.Image, mp: MaskPlan) -> list:
    """成品自检：**矩形之外**逐字节＝原图。

    嵌字的写入被 `can_write`（＝擦除区）夹住，擦除只发生在矩形里——所以成品里
    任何矩形外的差异都是越界写入。矩形**之内**是擦除与新字的地盘，不比
    （新字必然不等于底色；擦除态对底色/重建像素的逐字节比对放进单元测试做）。
    """
    sp, dp = src.load(), dst.load()
    inrect = [[False] * src.width for _ in range(src.height)]
    for (l, t, r, b) in mp.rects:
        for y in range(t, b):
            row = inrect[y]
            for x in range(l, r):
                row[x] = True
    bad = []
    for y in range(src.height):
        for x in range(src.width):
            if inrect[y][x]:
                continue
            if mp.write_band is not None and mp.write_band[y][x]:
                continue        # 写带：新字墨迹许落（替换语义），不比字节
            if (x, y) in mp.post_writes:
                if dp[x, y] != mp.post_writes[(x, y)]:
                    bad.append((x, y))
            elif sp[x, y] != dp[x, y]:
                bad.append((x, y))
    return bad


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
    #: `plan_geo` 专用：非 None 时 `apply` 在矩形内贴这张图的像素而不是纯底色
    #: （照片底：足迹内是拉普斯拉重建值，足迹外与原图逐字节相同）。
    fill: Image.Image | None = None
    #: `plan_geo` 专用：被保留层足迹罩住、**没擦**的旧墨晕（强度 > 可见性地板）。
    #: 不是缺陷清单——它们在保留层的地盘里原样活着（与原图同值），报出来供裁量。
    protected_glow: list[tuple[int, int, int]] = field(default_factory=list)  # (x, y, dev)
    #: `plan_geo` 专用：字芯豁免开着——`can_write` 允许写回落在保留层足迹内的
    #: 本层字芯位（新字同位替换旧字）。
    geo_exemption: bool = False
    #: `plan_geo` 专用：**写带**——旧墨 bbox ±2px 内、排除硬保护与保留层字芯的
    #: 像素。新字的墨迹许在这里落笔（替换语义：新字住旧字住的地方，汉字本就比
    #: 假名高且笔画位置不同）；带内的保留层晕被新墨盖掉属替换的固有代价。
    #: `can_write` 与两处校验都认它。
    write_band: list[list[bool]] | None = None
    #: `plan_geo` 专用：逐像素的可写域（＝擦除允许区本身）。给了它 `can_write`
    #: 就直接查它——旧墨足迹比 roi 小，若仍按「roi∧¬protect」判，晕圈外沿的
    #: roi 边缘就成了法外之地（实测 sys_12_a 越界 93 像素）。
    writable: list[list[bool]] | None = None
    #: `plan_geo` 专用：**幽灵晕减法**的写入表 (x,y)→RGBA。保留层足迹内擦不掉的
    #: 旧墨黑晕（与保留层彩晕叠在同一批像素上）按合成代数从像素里减掉——
    #: 见 `plan_geo` 的 ghost_subtract。`apply` 在矩形之后落这些点。
    post_writes: dict[tuple[int, int], tuple[int, int, int, int]] = field(
        default_factory=dict)

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

        `writable`（几何足迹方案）给定时直接查它——它就是擦除允许区，连
        「roi 之内、足迹之外」的边角也一并排除。`write_band`（写带）在其上
        追加：旧墨带内的保留层**软晕**许被新字墨迹盖掉（替换语义），硬保护
        （缩略图框等）与保留层字芯除外——那两处在建带时就已排除。
        """
        if self.write_band is not None and self.write_band[y][x]:
            return True
        if self.writable is not None:
            return self.writable[y][x]
        l, t, r, b = self.roi
        if not (l <= x < r and t <= y < b):
            return False
        if not self.protect[y][x]:
            return True
        return self.geo_exemption and self.ink_core[y][x]


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
    """按方案把矩形擦成底色。`mp.fill` 给定时（照片底）贴重建图的像素。"""
    for r in mp.rects:
        if mp.fill is None:
            dst.paste(mp.bg, r)
        else:
            dst.paste(mp.fill.crop(r), r[:2])
    dp = dst.load()
    for (x, y), c in mp.post_writes.items():
        dp[x, y] = c


def check_keep_intact(src: Image.Image, dst: Image.Image, mp: MaskPlan,
                      skip_ink: bool = False) -> int:
    """保留层的地盘必须逐字节不变。返回被改动的像素数（应为 0）。

    `skip_ink=True`（几何足迹方案）时，`ink_core` 里的旧墨字芯不算数：它们是
    **被新字同位替换的旧字**，即使落在了保留层的足迹里也必须擦掉——不擦才会
    留下鬼影。默认 False，标题轨的语义一个字节都不变。

    `post_writes`（幽灵晕减法）的写入是**有意的**改动：黑晕从叠合像素里减掉，
    保留层的彩晕按实测环恢复。它们同样豁免，改动是否成立由减法自身的代数与
    看图把关。
    """
    sp, dp = src.load(), dst.load()
    W, H = src.size
    bad = 0
    for y in range(H):
        for x in range(W):
            if not mp.protect[y][x]:
                continue
            if (skip_ink and mp.ink_core[y][x]) or (x, y) in mp.post_writes:
                continue
            # 写带内的保留层软晕许被新字墨迹盖掉（替换语义，E11′/E18）：
            # 有意改动，豁免。硬保护（框）在建带时已排除，不在此列。
            if mp.write_band is not None and mp.write_band[y][x]:
                continue
            if sp[x, y] != dp[x, y]:
                bad += 1
    return bad


def check_old_ink_gone(src: Image.Image, dst: Image.Image, mp: MaskPlan) -> list:
    """擦后，作用域内不该再有旧墨——除了 `residual` 那几粒。

    这是**闭合检查**：遮盖区的外边界必须落在全透明处，否则就是又切出一条边。
    """
    dp = dst.load()
    l, t, r, b = mp.roi
    resid = set(mp.residual)
    return [(x, y, dp[x, y]) for y in range(t, b) for x in range(l, r)
            if dp[x, y][3] > 0 and not mp.protect[y][x] and (x, y) not in resid]


