"""`png/sysgim/` 描边字族的测绘与烤字测试。

这一族的所有关键判断都是**实测**得来的（族归属、每行填充色与不透明度、对齐、
可动范围）。测试要证的就是这些实测真的在起作用——所以除了正向断言，每条
承重判据都配一个变异：把判据拿掉，结果必须变。判据拿掉了结果还一样，
那条判据就是摆设。
"""

from __future__ import annotations

import json

import pytest
from PIL import Image

from tools import bake_sysgim_outline as B
from tools import check_ui_terms as T
from tools import measure_sysgim as M

# ── 族边界 ────────────────────────────────────────────────────

IN_FAMILY = [
    "sys_12_f", "sys_12_g", "sys_13_c", "sys_13_d", "sys_20_c", "sys_20_cb",
    "sys_20_cc", "sys_20_cd", "sys_20_d", "sys_21_a", "sys_21_d", "sys_21_e",
    "sys_21_f", "sys_22_a", "sys_22_ba", "sys_22_bb", "sys_22_c", "sys_22_d",
    "sys_22_e", "sys_24_b", "sys_24_c",
]
#: 对照组来自另外几类（发光字、全屏正文、英文+假名），族判据必须把它们排除。
OUT_OF_FAMILY = ["sys_5_a", "sys_6_b", "sys_2_b", "title_03_a", "autosave", "sys_11_a"]


@pytest.mark.parametrize("name", IN_FAMILY)
def test_in_family(name):
    s = M.measure(M.SYSGIM / f"{name}.png")
    assert s.is_outline_family, f"{name} share={s.family_share}"


@pytest.mark.parametrize("name", OUT_OF_FAMILY)
def test_out_of_family(name):
    """判据若把别族也收进来，就等于没有判据。"""
    s = M.measure(M.SYSGIM / f"{name}.png")
    assert not s.is_outline_family, f"{name} 被误判入族 share={s.family_share}"


def test_family_threshold_actually_separates():
    """族内最低分与族外最高分之间要有肉眼可见的间隔，阈值不是踩线定的。"""
    lo = min(M.measure(M.SYSGIM / f"{n}.png").family_share for n in IN_FAMILY)
    hi = max(M.measure(M.SYSGIM / f"{n}.png").family_share for n in OUT_OF_FAMILY)
    assert lo - hi > 0.5, f"族内最低 {lo} vs 族外最高 {hi}，间隔太窄"


# ── 版面测绘 ──────────────────────────────────────────────────


def test_rows_split_when_touching():
    """`sys_24_b` 七行贴死无空行，只能按行距强切；lua 的 layerClip 也是 18px。"""
    s = M.measure(M.SYSGIM / "sys_24_b.png", n_rows=7)
    assert len(s.rows) == 7
    assert {s.rows[i + 1].top - s.rows[i].top for i in range(6)} == {18}


def test_rows_found_when_separated():
    s = M.measure(M.SYSGIM / "sys_20_c.png")
    assert len(s.rows) == 8
    assert s.pitch == 24


# ── 逐行样式实测 ──────────────────────────────────────────────


def test_disabled_rows_are_dimmed_not_recolored():
    """`sys_20_cb` 的禁用态是整行 alpha 减半，不是换色。"""
    im = Image.open(M.SYSGIM / "sys_20_cb.png").convert("RGBA")
    dim = B._row_style(im, (0, 0, 133, 18))       # 行0：原图里是灰的
    lit = B._row_style(im, (0, 48, 133, 66))      # 行2：原图里是亮的
    assert dim[0] == M.FILL_ON and lit[0] == M.FILL_ON, "两行都是白填充，色没变"
    assert dim[1] == pytest.approx(0.5, abs=0.02)
    assert lit[1] == pytest.approx(1.0, abs=0.02)


def test_disabled_by_recolor_is_also_detected():
    """`sys_22_e` 下半用的是另一种机制：alpha 不变，填充色换成灰。"""
    im = Image.open(M.SYSGIM / "sys_22_e.png").convert("RGBA")
    fill, alpha = B._row_style(im, (212, 65, 260, 82))
    assert fill == M.FILL_OFF
    assert alpha == pytest.approx(1.0, abs=0.02)


def test_boxed_row_anchor_ignores_ink_outside_the_box():
    """`sys_22_ba` 那一行的墨迹含十个音量格，锚点必须只看盒内。"""
    im = Image.open(M.SYSGIM / "sys_22_ba.png").convert("RGBA")
    align, anchor = B._box_anchor(im, (0, 0, 67, 16))
    assert align == "left" and anchor == 0
    # 整行不设盒时会被格子拖到居中——这正是当初的 bug
    whole, _ = B._box_anchor(im, (0, 0, 207, 16))
    assert whole == "center"


# ── 烤字产物 ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def baked():
    text = B.load_text()
    out = {}
    for name in sorted(set(text) | set(B.TEXT_ALIAS)):
        rows = text[B.TEXT_ALIAS.get(name, name)]
        img, viol = B.bake_file(name, rows, [])
        out[name] = (img, viol)
    return out


def test_no_pixels_touched_outside_boxes(baked):
    assert all(v == 0 for _, v in baked.values())


def test_partial_replace_preserves_the_volume_boxes(baked):
    """音量格由 lua 的 layerClip 按 14px 步进取用，动一个像素都会错位。"""
    src = Image.open(M.SYSGIM / "sys_22_ba.png").convert("RGBA")
    dst = baked["sys_22_ba"][0]
    sp, dp = src.load(), dst.load()
    for y in range(16):
        for x in range(67, 207):
            assert sp[x, y] == dp[x, y], f"({x},{y}) 音量格被改动"


def test_sys_22_e_boxes_never_cross_the_state_boundary():
    """`sys_22_e` 的盒**绝不可跨过 y=41**。

    上半 y0–40 是启用态、下半 y41–81 是禁用态，`snr_common.lua:3167` 的
    `layerClip(0, 41, 260, 82)` 取的正是下半作底。盒跨界就会擦掉相邻那一行的顶部
    ——2026-09-01 用户在产物里看出「由加里/千秋 的盒遮住了第三行」，就是这个。
    这条钉的是**数据**而非像素：跨界与否在盒里一眼可判，比事后比像素稳。
    """
    import json
    from tools.bake_sysgim_outline import DATA
    rows = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    boxes = [r["box"] for r in rows if r["file"] == "sys_22_e"]
    assert len(boxes) == 14, f"sys_22_e 应为 7 名 × 2 态 = 14 行，现有 {len(boxes)}"
    bad = [b for b in boxes if b[1] < 41 < b[3]]
    assert bad == [], f"这些盒跨过了启用/禁用分界 y=41：{bad}"


def test_sys_22_e_redraws_all_seven_names(baked):
    """七个名字**全部**重绘。

    先前只重烤片假名两处（其余「中日同形」跳过），结果晕的粗细对不齐——原图墨迹与
    我们渲的描边不同源，混排看得出来（用户 2026-09-01 指出）。故改为整张重绘；
    这条钉住它，免得日后有人为了省事又退回部分重绘。
    """
    src = Image.open(M.SYSGIM / "sys_22_e.png").convert("RGBA")
    dst = baked["sys_22_e"][0]
    sp, dp = src.load(), dst.load()
    for name, (x0, x1) in (("直哉", (0, 36)), ("彩野", (58, 100)), ("Yuichi", (120, 186)),
                           ("由加里", (0, 52)), ("千秋", (73, 112)),
                           ("Sakura", (135, 186)), ("其他", (210, 260))):
        changed = sum(1 for y in range(82) for x in range(x0, min(x1, 260))
                      if sp[x, y] != dp[x, y])
        assert changed > 0, f"{name} 区域未被重绘（{x0}..{x1}）"


def test_disabled_rows_stay_disabled_in_output(baked):
    """变异自检：把 alpha 实测拿掉，这条必须挂。"""
    dst = baked["sys_20_cb"][0]
    px = dst.load()

    def peak(top):
        return max(
            (px[x, y][3] for y in range(top, top + 18) for x in range(133) if px[x, y][3] > 8),
            default=0,
        )

    assert peak(0) < 160, "行0 在原图是禁用态，产物里却是全不透明"
    assert peak(48) > 240, "行2 在原图是启用态，产物里却被压暗"


def test_orphan_is_not_baked():
    """`sys_22_c` 在 lua 全库只有 backLayerName 声明，从未 layerCopy。"""
    assert "sys_22_c" in B.ORPHANS
    assert "sys_22_c" not in B.load_text()


def test_every_row_has_a_translation():
    text = B.load_text()
    for name, rows in text.items():
        assert [r["row"] for r in rows] == list(range(len(rows))), f"{name} 行号不连续"
        assert all(r["zh"].strip() for r in rows), f"{name} 有空译文"


def test_row_count_mismatch_refuses_to_render():
    """译文行数与实测行数对不上时宁可报错，也不要错位渲染。"""
    rows = B.load_text()["sys_20_c"][:5]
    with pytest.raises(ValueError, match="对不上"):
        B.plan_file("sys_20_c", rows)


def test_translations_pass_the_term_gate():
    """这一批新译必须与已入线正文用词一致——闸和烤字绑在一起，不许各走各的。"""
    v = T.run([B.DATA])
    assert v == [], "\n".join(str(x) for x in v)


def test_data_is_valid_jsonl():
    for line in B.DATA.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            assert {"file", "row", "jp", "zh"} <= set(r)
