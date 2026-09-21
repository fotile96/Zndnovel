"""tools/bake_boot_dedication.py：开机第五卡——模板尺寸不透明、分隔线逐像素同 IPL01、
署名落在 IPL01 大字的位置、献词三行右对齐到线端、墨迹外全黑、≤256 色进包逐字节无损、
文案即用户定稿且不含 ∀ 记号。"""
from PIL import Image
import pytest

from tools import bake_boot_dedication as bbd
from tools.build_disc import quantize_for_template


@pytest.fixture(scope="module")
def card():
    return bbd.render()


def test_is_template_sized_and_fully_opaque(card):
    tpl = Image.open(bbd.TEMPLATE_PNG)
    assert card.size == tpl.size == (bbd.W, bbd.H)
    assert {a for _n, a in card.getchannel("A").getcolors(256)} == {255}


def test_rule_is_pixel_exact_copy_of_ipl01(card):
    tpl = Image.open(bbd.TEMPLATE_PNG).convert("RGBA")
    for x in range(bbd.RULE_X0, bbd.RULE_X1 + 1):
        assert card.getpixel((x, bbd.RULE_Y)) == tpl.getpixel((x, bbd.RULE_Y)), x
    assert card.getpixel((bbd.RULE_X0 - 1, bbd.RULE_Y)) == (0, 0, 0, 255)
    assert card.getpixel((bbd.RULE_X1 + 1, bbd.RULE_Y)) == (0, 0, 0, 255)
    # 线不是重画的：IPL01 那一行本身就是蓝→白渐变（左端偏蓝、右端近白）
    l, r = card.getpixel((bbd.RULE_X0 + 2, bbd.RULE_Y)), card.getpixel((bbd.RULE_X1 - 2, bbd.RULE_Y))
    assert l[2] > l[0] + 100 and min(r[:3]) > 240


def test_name_sits_where_the_ipl01_wordmark_sits(card):
    box = bbd.ink_box(card, (0, 0, bbd.W, bbd.RULE_Y))
    assert box is not None
    l, t, r, b = box
    assert abs(l - bbd.NAME_LEFT) <= 1, box
    assert abs((b - 1) - bbd.NAME_BOTTOM) <= 1, box          # 墨迹底行 = 107（IPL01 大字同）
    assert b <= bbd.RULE_Y - 5                                 # 与线之间留空
    assert r < bbd.W // 2 + 40                                 # 大字在左半（七个字 22 px）
    assert t > 60                                              # 不顶到上边


def test_dedication_is_three_lines_right_aligned_to_the_rule_end(card):
    below = (0, bbd.RULE_Y + 1, bbd.W, bbd.H)
    bands = bbd.ink_rows(card, below)
    assert len(bands) == len(bbd.DEDICATION) == 3, bands
    for y0, y1 in bands:
        l, t, r, b = bbd.ink_box(card, (0, y0, bbd.W, y1))
        assert abs(r - bbd.DED_RIGHT) <= 1, (bands, (l, t, r, b))   # 每行都齐右
        assert l >= 180                                             # 在右半
        assert 12 <= (y1 - y0) <= bbd.DED_PX + 2                    # 一行字高，不是粘连的两行
    assert bands[0][0] >= bbd.RULE_Y + 6                           # 线下留空
    assert bands[-1][1] <= 200                                     # 整块仍在屏幕上中带，不掉到下半


def test_everything_outside_ink_boxes_is_black(card):
    name = bbd.ink_box(card, (0, 0, bbd.W, bbd.RULE_Y))
    ded = bbd.ink_box(card, (0, bbd.RULE_Y + 1, bbd.W, bbd.H))
    grow = 3   # 墨迹盒按 INK_MIN 阈值量的，抗锯齿的淡边（量化后最低一阶）可能再往外 1–2 px
    keep = [(bx[0] - grow, bx[1] - grow, bx[2] + grow, bx[3] + grow) for bx in (name, ded)]
    keep.append((bbd.RULE_X0 - 1, bbd.RULE_Y, bbd.RULE_X1 + 2, bbd.RULE_Y + 1))
    px = card.load()
    for y in range(0, bbd.H, 2):
        for x in range(0, bbd.W, 2):
            if any(bx[0] <= x < bx[2] and bx[1] <= y < bx[3] for bx in keep):
                continue
            assert px[x, y] == (0, 0, 0, 255), (x, y, px[x, y])


def test_fits_the_256_colour_template_losslessly(card):
    """整卡 ≤256 色 → quantize_for_template 走精确色板：进包像素与烤字图逐字节相同，
    分隔线的 91 阶渐变原样保留（MEDIANCUT 路径会把它并成 30 阶）。"""
    colours = card.getcolors(256)
    assert colours is not None, "颜色数超过 256——文字覆盖率量化没生效"
    assert len(colours) <= 91 + 2 * bbd.ALPHA_LEVELS + 1
    q = quantize_for_template(card, 256).convert("RGBA")
    assert q.size == card.size and q.tobytes() == card.tobytes()
    tpl = Image.open(bbd.TEMPLATE_PNG).convert("RGB")
    row = {tpl.getpixel((x, bbd.RULE_Y)) for x in range(bbd.RULE_X0, bbd.RULE_X1 + 1)}
    assert {q.getpixel((x, bbd.RULE_Y))[:3] for x in range(bbd.RULE_X0, bbd.RULE_X1 + 1)} == row


def test_text_coverage_is_posterised_but_still_antialiased(card):
    """每段文字恰好 ≤ ALPHA_LEVELS 种颜色（含满色），且不是二值——边缘仍有中间阶。"""
    ded = bbd.ink_box(card, (0, bbd.RULE_Y + 1, bbd.W, bbd.H))
    region = card.crop((ded[0] - 3, ded[1] - 3, ded[2] + 3, ded[3] + 3)).convert("RGB")
    greys = {c for _n, c in region.getcolors(1 << 16) if c != (0, 0, 0)}
    assert 4 <= len(greys) <= bbd.ALPHA_LEVELS - 1, sorted(greys)
    assert bbd.DED_FILL[:3] in greys


def test_wording_is_the_ratified_text_and_has_no_forall_mark():
    assert bbd.NAME == "全称量词汉化组"
    assert "".join(bbd.DEDICATION) == "谨以此本地化作品献给盛夏、提前合上书页的年轻生命与被留在故事里的人们"
    # 组名只写文字：∀ 是对 Anthropic 的 A 倒转 180° 的梗，画出来即破（用户 2026-09-21）
    assert "∀" not in bbd.NAME and not any("∀" in line for line in bbd.DEDICATION)
    assert bbd.MEMBER == "IPL03" and bbd.FACE == "boot_dedication"
