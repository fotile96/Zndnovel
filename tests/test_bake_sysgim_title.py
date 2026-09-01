"""`tools/bake_sysgim_title.py` + `tools/bake_mask.py` —— 主菜单 12 个菜单项的小注。

**这一面要害是遮盖与嵌字分两步、两个框。** 青色假名小注紧挨着必须原样保留的英文
大词（02–06/13 就写在英文正下方 3–4px）。一个框两用只有两种结局：收紧到嵌字合适
就盖不住小注的晕（产物上一圈矩形亮边），放大到盖得住就压到英文的字芯。

下面每条断言都是**在原图上量出来的**，不是设计选择。
"""

import json
import math
from functools import lru_cache

from PIL import Image

from tests.conftest import diff_bbox, needs_face_font
from tools import bake_mask
from tools.bake_para_glow import bake_file
from tools.bake_sysgim_glow import measure_glow
from tools.bake_sysgim_title import DATA, SPEC, SRC

ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
BOXES = {r["file"]: [tuple(r["box"])] for r in ROWS}
#: 小注与英文**空间分离**的六张——它们是「已知答案」样本：那里根本没有英文可伤。
SEPARATE = ["title_07_a", "title_08_a", "title_09_a", "title_10_a",
            "title_11_a", "title_12_a"]
#: 小注压在英文正下方的六张。
ADJACENT = ["title_02_a", "title_03_a", "title_04_a", "title_05_a",
            "title_06_a", "title_13_a"]


@lru_cache(maxsize=None)
def _img(name):
    return Image.open(SRC / f"{name}.png").convert("RGBA")


TWIN = {r["file"]: r["twin"] for r in ROWS if "twin" in r}


@lru_cache(maxsize=None)
def _plan(name):
    """**不带**孪生重建的方案——遮盖本身的行为由它作证。"""
    return bake_mask.plan(_img(name), tuple(BOXES[name]))


@lru_cache(maxsize=None)
def _plan_twin(name):
    """production 用的方案：带孪生重建（六张紧贴英文的才有孪生态）。"""
    return bake_mask.plan(_img(name), tuple(BOXES[name]), twin=TWIN.get(name))


def _cyan(im):
    """小注那一层的颜色签名：青绿系 `G−R` 达 42–83，而英文蓝晕 `G−R≈0`。"""
    px = im.load()
    return sum(1 for y in range(im.height) for x in range(im.width)
               if px[x, y][3] > 0 and px[x, y][1] - px[x, y][0] > 25
               and px[x, y][2] >= px[x, y][1])


def _split(name):
    """把两层的字芯分开：与 `bake_mask` 同一套判据，供测量用。"""
    im = _img(name)
    px = im.load()
    W, H = im.size
    core = [[px[x, y][3] >= bake_mask.CORE_ALPHA
             and min(px[x, y][:3]) >= bake_mask.CORE_LUMA
             for x in range(W)] for y in range(H)]
    boxes = BOXES[name]
    inside = lambda x, y: any(l <= x < r and t <= y < b for l, t, r, b in boxes)
    keep, drop = [], []
    for pts in bake_mask._components(core, W, H):
        n = sum(1 for p in pts if inside(*p))
        (drop if n * 2 > len(pts) else keep).extend(pts)
    return im, px, W, H, keep, drop


def test_corpus_is_the_twelve_menu_items_all_erase_only():
    """12 张全部**只擦不写**（用户 2026-09-01 裁定，理由见 bake_sysgim_title 文档串）。

    先前这条断言的是「12 条译文全部非空」。裁定把它整个推翻了：小注只有 7–10px 高，
    中文四字注在这个像素预算下换任何字体都糊，故抹掉日文、只留英文大词。
    留空必须是**显式**的 `erase`，不能靠空 `zh` 推断——那和「还没译」同形，
    而两者的处置相反（待译要整张跳过，只擦要照常出活）。
    """
    assert sorted(r["file"] for r in ROWS) == sorted(SEPARATE + ADJACENT)
    assert all(r.get("erase") for r in ROWS), [
        r["file"] for r in ROWS if not r.get("erase")]
    assert all(not r["zh"].strip() for r in ROWS), [
        r["file"] for r in ROWS if r["zh"].strip()]


def test_the_retired_translations_are_kept_in_the_notes():
    """撤下的 12 条中文小注要留在数据里，不能只活在 git 历史里。

    它们是过了术语闸的定译（「故事目录」「片段目录」「记录存档」…）。翻案时
    直接取回，不必重译、不必再走一遍闸。
    """
    for r in ROWS:
        assert "撤下备查" in r["note"], r["file"]
        assert r["note"].count("「- ") >= 1, (r["file"], r["note"][:80])


def test_english_glow_dies_exactly_at_distance_five():
    """**整套遮盖压在这一条实测上。**

    英文的外发光是到字芯距离的确定函数。取离小注墨 ≥12px 的**纯英文**像素分箱，
    12 张合并后逐距的 alpha 上界是 153/143/53/42/16/8/8/3/0，外沿精确落在
    d=√20≈4.472；d=5.000 那一箱 1418 个样本**全是 0**。

    **双向验**：d≥5 处必须一个非零都没有（否则「擦这里不伤英文」不成立），
    而 d≤4.5 处必须确实还有非零（否则这条判据是废的，随便取个大半径也能"通过"）。
    """
    far_max, near_max = 0, 0
    for name in ROWS and [r["file"] for r in ROWS]:
        im, px, W, H, keep, drop = _split(name)
        d_keep = bake_mask._edt(keep, W, H)
        d_drop = bake_mask._edt(drop, W, H)
        for y in range(H):
            for x in range(W):
                if d_drop[y][x] < 12 or d_keep[y][x] == 0:
                    continue
                a = px[x, y][3]
                if d_keep[y][x] >= 5.0:
                    far_max = max(far_max, a)
                elif d_keep[y][x] <= 4.5:
                    near_max = max(near_max, a)
    assert far_max == 0, f"d≥5 处竟有 alpha {far_max} 的英文晕——外沿判据不成立"
    assert near_max > 0, "d≤4.5 处一个非零都没有——这条判据没在量任何东西"


def test_protect_table_is_monotone_and_ends_at_zero():
    """查表用的上界必须单调、且在外沿归零；外发光按构造就是单调衰减的。"""
    vals = [a for _, a in bake_mask.GLOW_ALPHA_MAX]
    assert vals == sorted(vals, reverse=True), vals
    assert vals[-1] == 0
    assert bake_mask.protect_alpha(99.0) == 0


def test_the_old_binary_criterion_blamed_the_material_for_its_own_bug():
    """**把教训钉死在测试里。**

    上一轮那条二值判据（小注足迹取 `G−R>8`，其余非透明像素一律算英文）报出
    「不可盖 73–89%」，并据此断言「英文的蓝晕是大范围的，小注整个落在它的辉光场里」。
    实测：被它划成「盒内英文足迹」的像素里，**65.6%–100% 离真英文字芯 >4px**
    ——那是小注自己的白字芯与白抗锯齿边（`G−R≈0`）被划了进去。
    空间分离的那六张更是 **100%**：那里根本没有英文可言。

    是判据的毛病，不是素材的毛病（bake-handoff-2026-08-29 §5.3 同一个坑的第三次）。
    """
    for name in [r["file"] for r in ROWS]:
        im, px, W, H, keep, _drop = _split(name)
        d_keep = bake_mask._edt(keep, W, H)
        l, t, r, b = BOXES[name][0]
        old_eng = [(x, y) for y in range(t, b) for x in range(l, r)
                   if px[x, y][3] > 0 and not (px[x, y][1] - px[x, y][0] > 8)]
        mislabelled = [p for p in old_eng if d_keep[p[1]][p[0]] > 4.5]
        assert old_eng, name
        share = len(mislabelled) / len(old_eng)
        assert share >= 0.65, (name, share)   # 实测 65.6%–100%，最低是 title_06_a
        if name in SEPARATE:
            assert share == 1.0, (name, share)


def test_mask_never_touches_the_protected_layer():
    """**遮盖的主张**：保留层的地盘逐字节不变。"""
    for name in [r["file"] for r in ROWS]:
        im = _img(name)
        mp = _plan(name)
        out = im.copy()
        bake_mask.apply(out, mp)
        assert bake_mask.check_keep_intact(im, out, mp) == 0, name


def test_mask_boundary_never_severs_the_ink_it_is_removing():
    """**这才是矩形亮边的解药**：切口不许落在旧墨的晕里。

    旧框只圈到青色强部，框外还活着的晕被齐边留下，那条边界自己就成了一个矩形。
    现在遮盖区比旧墨的外接盒还大 `ROI_PAD`，切口外侧应当没有旧墨。

    实测：擦区外侧一圈（且不属于保留层）的像素，**最大 alpha 只有 11**，
    且每一个都是保留层那头的蓝色最外圈（`(33,32,253)` / `(136,121,235)`），
    一个青的都没有——即切口只轻蹭到保留层 τ 以下的外沿，从不切断旧墨。
    """
    for name in [r["file"] for r in ROWS]:
        im = _img(name)
        px = im.load()
        mp = _plan(name)
        W, H = im.size
        erased = {(x, y) for (l, t, r, b) in mp.rects
                  for y in range(t, b) for x in range(l, r)}
        outside = {(x + dx, y + dy) for (x, y) in erased
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        edge = [(x, y) for (x, y) in outside
                if 0 <= x < W and 0 <= y < H and (x, y) not in erased
                and not mp.protect[y][x] and px[x, y][3] > 0]
        assert all(px[x, y][3] <= bake_mask.PROTECT_TAU for x, y in edge), (
            name, sorted(((px[x, y][3], x, y) for x, y in edge), reverse=True)[:3])
        cyan = [(x, y, px[x, y]) for x, y in edge if px[x, y][1] - px[x, y][0] > 8]
        assert not cyan, (name, cyan[:5])


def test_old_ink_is_gone_except_the_counted_residual():
    """擦后作用域内不该再有旧墨——除了逐粒计数过的那几个残留。

    残留是**两层真的重叠**的地方（小注顶行落在英文字芯下方 3–4px，英文晕在那里
    还有 42–153 的强度），不是判据放水。空间分离的六张残留必须是 0。
    """
    for name in [r["file"] for r in ROWS]:
        im = _img(name)
        mp = _plan(name)
        out = im.copy()
        bake_mask.apply(out, mp)
        assert bake_mask.check_old_ink_gone(im, out, mp) == [], name
        if name in SEPARATE:
            assert mp.residual == [], (name, mp.residual)
        else:
            assert len(mp.residual) <= 12, (name, len(mp.residual))


def test_ring_is_contaminated_without_the_layer_split():
    """**已知答案上的双向自检。**

    不做分层就量小注的环，量到的是英文的晕：`title_04_a` 在 d=5..10 处得到
    36/48/57/35/20/34——**非单调，且远到 d=10 还不收敛**。分层后是
    136/43/17/6/2/0，单调且在自己的外沿归零。

    ⚠ `MAX_TAIL_DEV` 那道收敛检查两种情形都放行：它只看 d=18 的尾端，污染在中段。
    """
    name = "title_04_a"
    box = BOXES[name][0]
    im = _img(name)
    dirty = measure_glow(im, box)
    a = [r[3] for r in dirty.ring[4:10]]
    assert not all(a[i] >= a[i + 1] for i in range(len(a) - 1)), a
    assert dirty.ring[9][3] > 8, dirty.ring[9]

    mp = _plan(name)
    clean = measure_glow(im, box, ignore=mp.protect_at, core_of=mp.is_ink_core,
                         bg=mp.bg, probe_d=bake_mask.GLOW_PROBE_D)
    c = [r[3] for r in clean.ring[:8]]
    assert all(c[i] >= c[i + 1] for i in range(len(c) - 1)), c
    assert c[0] > 100 and c[5] == 0, c


def test_box_border_mode_is_not_a_usable_background_here():
    """**底不能靠盒边众数量**——这一族的盒边整个泡在晕里。

    `title_06_a` 的盒边 140 个像素散成一堆各不相同的淡白，众数只占 10 个，
    量出来的底是 `(255,255,255,20)`；擦盒时就擦成了一块淡灰的矩形（旧产物上
    肉眼可见的那块）。`title_13_a` 同病。作用域边界够远，那里才有干净的底。
    """
    for name in ("title_06_a", "title_13_a"):
        wrong = measure_glow(_img(name), BOXES[name][0]).bg
        assert wrong[3] != 0, (name, wrong)
        assert _plan(name).bg == (255, 255, 255, 0), (name, _plan(name).bg)


def test_pure_cyan_strokes_count_as_ink_not_as_glow():
    """字芯判据必须按 alpha 判，不能按「离底的距离」。

    全不透明的纯青 `(36,119,160,255)` 离底 570、白芯 1020，只有 56%——按默认判据
    它不是墨。小注两端那对 `-` 太细，整笔都到不了白，于是被当成「晕」；它离最近的
    白芯 5–9px，环因此在远处凭空多出强度。
    """
    im = _img("title_04_a")
    px = im.load()
    mp = _plan("title_04_a")
    cyan = [(x, y) for y in range(im.height) for x in range(im.width)
            if px[x, y][3] == 255 and px[x, y][1] - px[x, y][0] > 60
            and min(px[x, y][:3]) < bake_mask.CORE_LUMA]
    assert cyan, "样本图里没有纯青实心像素——这条测试失去了对象"
    assert all(mp.is_ink_core(x, y) for x, y in cyan)


@needs_face_font("sysgim")
def test_baked_output_leaves_the_english_byte_identical():
    """**产物层面的主张**：英文大词按用户裁定原样保留——不是"渲得像"，是没动过。

    ⚠ 唯一的例外是 `post_writes`：孪生态重建按地面真值改写的那批**晕**像素
    （`check_keep_intact` 对它豁免）。那不是"没动过"的破例，正相反——那些像素原本
    就不是纯英文，是英文的晕**叠着旧墨**，重建才让它们回到"只有英文"。英文的
    笔画本体一粒都没被选中，由 `test_reconstruction_never_touches_the_english_strokes`
    单独作证。
    """
    for r in ROWS:
        name = r["file"]
        orig = _img(name)
        baked = bake_file(name, [r], [], SPEC)
        assert bake_mask.check_keep_intact(orig, baked, _plan_twin(name)) == 0, name


@needs_face_font("sysgim")
def test_baked_output_changes_nothing_outside_the_mask_roi():
    """作用域之外一个像素也不许动——含另一态（暗态）的英文。"""
    for r in ROWS:
        name = r["file"]
        orig, baked = _img(name), bake_file(name, [r], [], SPEC)
        mp = _plan(name)
        masked = baked.copy()
        masked.paste(orig.crop(mp.roi), mp.roi)
        assert diff_bbox(orig, masked) is None, (name, diff_bbox(orig, masked))


@needs_face_font("sysgim")
def test_erase_only_output_keeps_no_cyan_at_all():
    """**产物层面的主张**：假名走了，也没有中文顶上——**12 张一个青像素都不剩**。

    判据就是工具文档串里那条实测的分层判据（小注青 `G−R` 达 42–83，英文蓝晕
    `G−R≈0`），故「还有青」等价于「还有假名，或者写了新字」。双向验：原图必须
    确实有一大片青（250–354），否则这条测试没在量任何东西。

    ⚠ 这条曾经宽到 `after <= 12`：紧贴英文的六张有 3–11 粒旧墨压在英文的发光足迹
    里，按 `d_keep < 5` 那条距离判据一律不许动。嵌中文时它们被新墨的晕淹掉看不见，
    改成只擦不写后就孤零零露在英文底下（用户 2026-09-01：「极力辨认仍可见」）。
    孪生态重建把它们清了，**所以这里收紧到零**——宽限额度一旦没有了理由就该收回。
    """
    for r in ROWS:
        name = r["file"]
        before, after = _cyan(_img(name)), _cyan(bake_file(name, [r], [], SPEC))
        assert before > 200, (name, before)      # 实测 250–354
        assert after == 0, (name, after)


# ── 孪生态重建 ────────────────────────────────────────────────


def test_twin_band_carries_no_kana():
    """**孪生重建的前提**：暗态那条带是纯英文，一个假名像素都没有。

    前提不成立的话，「地面真值」本身就带着要清的东西，重建只是把污染搬个家。
    """
    assert set(TWIN) == set(ADJACENT), sorted(TWIN)
    for name, tw in TWIN.items():
        im = _img(name)
        b0, b1 = tw["band"]
        assert _cyan(im.crop((0, b0, im.width, b1))) == 0, name
        # 亮态那条带反过来必须有青，否则是把两条带认反了
        lo = b0 + tw["dy"]
        assert _cyan(im.crop((0, lo, im.width, lo + b1 - b0))) > 0, name


def test_twin_offset_puts_the_two_states_on_top_of_each_other():
    """记下来的 Δy 必须真的把两态对齐，**差一行就崩**——这个值不是随手填的。

    尺子用「远场 alpha 一致度」而不是「非透明蒙版重叠率」。重叠率量的是笔画有没有
    盖住笔画，而笔画是**粗的**：错开一行照样盖得住九成以上（实测 Δy 1.000 vs
    +1 0.996，title_05_a 上只差 0.004，根本分不开）。一致度量的是**灰度层面对不对得上**，
    对错位极敏感：

        Δy 正确  p95 = 1–3（均值 0.22–0.52）
        Δy ±1    p95 = 82–87（均值 24–30）

    差着一个数量级。这也顺带说明「两态只换了配色、几何逐像素相同」这个前提是真的。
    """
    for name, tw in TWIN.items():
        im = _img(name)
        px = im.load()
        W, H = im.size
        mp = _plan(name)
        drop = [(x, y) for y in range(H) for x in range(W) if mp.ink_core[y][x]]
        dd = bake_mask._edt(drop, W, H)
        b0, b1 = tw["band"]

        def agree(dy):
            """远场（离旧墨够远，没有污染）两态 alpha 差的 p95。"""
            v = []
            for y in range(b0, b1):
                yl = y + dy
                if not 0 <= yl < H:
                    continue
                for x in range(W):
                    if px[x, y][3] == 0 and px[x, yl][3] == 0:
                        continue
                    if dd[yl][x] < bake_mask.TWIN_NEAR_D:
                        continue
                    v.append(abs(px[x, yl][3] - px[x, y][3]))
            v.sort()
            return v[int(len(v) * 0.95)]

        assert agree(tw["dy"]) <= 3, (name, agree(tw["dy"]))
        for off in (-1, 1):
            assert agree(tw["dy"] + off) > 40, (name, off, agree(tw["dy"] + off))


def test_contamination_only_raises_alpha_and_dies_within_three_pixels():
    """`TWIN_EXCESS_TOL` 的两条实测依据，双向验。

    ①**远处两态逐字节相同**：离旧墨字芯 ≥4px 处「亮态 α − 孪生 α」的 p95 只有 1。
      这同时排除了「两态本来就一强一弱」——真有系统性差异的话远处不会归零，
      那样按超出量做减法就会把英文的晕一起削掉。
    ②**近处确实有污染**：d≤3 处成规模地超出容差，故这把尺子在量东西。
    """
    far, near = [], []
    for name, tw in TWIN.items():
        im = _img(name)
        px = im.load()
        W, H = im.size
        mp = _plan(name)
        drop = [(x, y) for y in range(H) for x in range(W) if mp.ink_core[y][x]]
        dd = bake_mask._edt(drop, W, H)
        b0, b1 = tw["band"]
        for y in range(b0, b1):
            yl = y + tw["dy"]
            if not 0 <= yl < H:
                continue
            for x in range(W):
                if px[x, y][3] == 0 and px[x, yl][3] == 0:
                    continue
                (far if dd[yl][x] >= 4 else near).append(px[x, yl][3] - px[x, y][3])
    far.sort()
    assert far[int(len(far) * 0.95)] <= 1, far[-5:]
    assert sum(1 for v in near if v > bake_mask.TWIN_EXCESS_TOL) > 200, len(near)


@needs_face_font("sysgim")
def test_reconstruction_never_brightens_past_the_ground_truth():
    """重建后成品不许比「只有英文」的地面真值亮出噪声地板以上。

    这是重建**做到了**的正向主张。修前实测最多亮出 60+（孤零零的旧墨粒与它的晕），
    修后 ≤11——而 11 正是两态量化噪声本身的极值（见上一条的 far 分布）。
    """
    for r in ROWS:
        name = r["file"]
        if name not in TWIN:
            continue
        dy, (b0, b1) = TWIN[name]["dy"], TWIN[name]["band"]
        src, baked = _img(name), bake_file(name, [r], [], SPEC)
        sp, bp = src.load(), baked.load()
        worst = max(bp[x, y + dy][3] - sp[x, y][3]
                    for y in range(b0, b1) for x in range(src.width)
                    if 0 <= y + dy < src.height)
        assert worst <= 11, (name, worst)


def test_reconstruction_never_touches_the_english_strokes():
    """重建只碰**晕**，绝不碰英文的笔画本体（「英文一律不动」是用户的裁定）。

    ⚠ **这条曾经真的挂过，靠的不是运气而是补了一道闸。** 起初以为合成代数自动保证
    ——英文字芯 alpha 拉满、旧墨压不上去、超出量恒为 0。但两态在笔画**边沿**会各自
    舍入到差 4 左右（远场超出量 p95 虽是 1，极值却有 11），于是 title_03_a (20,52)
    与 title_13_a (44,51) 两粒纯白满 alpha 的笔画被当成污染改掉了。
    容差挡不住这条尾巴，`TWIN_NEAR_D` 那道几何闸才挡得住。
    """
    for name in ADJACENT:
        px = _img(name).load()
        for (x, y) in _plan_twin(name).post_writes:
            p = px[x, y]
            assert not (p[3] >= bake_mask.CORE_ALPHA
                        and min(p[:3]) >= bake_mask.CORE_LUMA), (name, x, y, p)


def test_merge_farther_accepts_a_predicate_for_non_rectangular_bounds():
    """保留区不是矩形（是绕着字形的一条阶梯边界），故 `bounds` 要能收谓词。"""
    from tools.bake_sysgim_glow import _merge_farther

    bg = (255, 255, 255, 0)
    dst = Image.new("RGBA", (4, 1), bg)
    tile = Image.new("RGBA", (4, 1), (0, 0, 0, 255))
    _merge_farther(dst, tile, 0, 0, bg, bounds=lambda x, y: x % 2 == 0)
    assert [dst.load()[x, 0][3] for x in range(4)] == [255, 0, 255, 0]
