"""`tools/ui_font.py` —— 烤字字体的统一取用口。

在此之前，字体在六个工具里有两套写法：sysgim 两个认 `ZND_UI_FONT`，plot/scene/
card/select 四个写死路径。于是「换个字体看看」这件本该一行的事，在四个面上做不到。

而**按面分别选字**才是真需求：select 按钮是 17–18px、card 正文 9px、scene 条 9–11px、
sysgim 是 12–17px 还要叠描边与发光——同一套字在这几档上的表现不是一回事。
"""

import pytest

from tools.ui_font import BUNDLED, FACES, resolve


def test_default_is_the_bundled_regular(monkeypatch):
    monkeypatch.delenv("ZND_UI_FONT", raising=False)
    for f in FACES:
        monkeypatch.delenv(f"ZND_UI_FONT_{f}", raising=False)
    assert resolve("card") == BUNDLED
    assert BUNDLED.exists(), "随仓库分发的字体必须在（G1：换机器即开即用）"


def test_global_env_overrides_default(monkeypatch, tmp_path):
    fake = tmp_path / "Other.ttf"
    fake.write_bytes(b"")
    monkeypatch.setenv("ZND_UI_FONT", str(fake))
    monkeypatch.delenv("ZND_UI_FONT_CARD", raising=False)
    assert resolve("card") == fake


def test_per_face_env_beats_global(monkeypatch, tmp_path):
    """本模块存在的理由：同一次运行里，各面可以用不同的字。"""
    glob_f, card_f = tmp_path / "Global.ttf", tmp_path / "Card.ttf"
    glob_f.write_bytes(b"")
    card_f.write_bytes(b"")
    monkeypatch.setenv("ZND_UI_FONT", str(glob_f))
    monkeypatch.setenv("ZND_UI_FONT_CARD", str(card_f))
    assert resolve("card") == card_f
    assert resolve("select") == glob_f  # 未单独指定的面仍走全局


def test_face_name_is_case_insensitive(monkeypatch, tmp_path):
    f = tmp_path / "F.ttf"
    f.write_bytes(b"")
    monkeypatch.setenv("ZND_UI_FONT_SCENE", str(f))
    assert resolve("scene") == resolve("SCENE") == f


def test_missing_file_raises_instead_of_falling_back(monkeypatch):
    """打错路径必须炸，**不能**悄悄回落到默认字体。

    悄悄回落＝你以为在评估新字体，看到的却还是霞鹜文楷——而两次输出的差别
    恰好是零，最像"这字体没救了"的那种零。
    """
    monkeypatch.setenv("ZND_UI_FONT_PLOT", "/nope/Missing.ttf")
    with pytest.raises(FileNotFoundError, match="ZND_UI_FONT_PLOT"):
        resolve("plot")


def test_unknown_face_is_rejected(monkeypatch):
    """面名打错同样不能静默——否则 `ZND_UI_FONT_CARDS`（多个 s）会永远没反应。"""
    with pytest.raises(ValueError, match="cards"):
        resolve("cards")


def test_every_bake_tool_face_is_registered():
    assert FACES == ("PLOT", "SCENE", "CARD", "SELECT", "SYSGIM")


# ---------------------------------------------------------------------------
# 变量字体的重量：默认实例是陷阱
# ---------------------------------------------------------------------------

SHS = BUNDLED.parent / "SourceHanSansSC-VF.ttf"
needs_shs = pytest.mark.skipif(not SHS.exists(), reason="需要 SourceHanSansSC-VF.ttf")


def _ink(font, text="章节5：Sakura的日记"):
    """墨迹里的纯白核占比——重量的可测代理量（同 sysgim 裁决 Y6 的判据）。"""
    from PIL import Image, ImageDraw

    img = Image.new("L", (260, 30), 0)
    ImageDraw.Draw(img).text((2, 2), text, font=font, fill=255)
    px = list(img.tobytes())
    ink = sum(1 for v in px if v > 0)
    return sum(1 for v in px if v >= 250) / max(ink, 1)


@needs_shs
def test_variable_font_defaults_to_regular_not_the_fonts_own_default(monkeypatch):
    """**本组测试的主张。** `SourceHanSansSC-VF` 的默认实例是 ExtraLight(250)——
    它是权重轴的**最小值**，不是设计者推荐的正文字重。

    裸调 `ImageFont.truetype()` 会拿到它，于是两千多张图会在发丝级字重下烤出来，
    而这恰恰与「霞鹜文楷太细」这个换字动机完全相反。更坏的是它**看起来是正常的**：
    没有报错、没有缺字，只是整体更灰一点——正是最容易被当成"这字体不行"的失效形态。
    """
    from PIL import ImageFont

    from tools.ui_font import truetype

    monkeypatch.setenv("ZND_UI_FONT_CARD", str(SHS))
    monkeypatch.delenv("ZND_UI_FONT_WEIGHT", raising=False)
    monkeypatch.delenv("ZND_UI_FONT_WEIGHT_CARD", raising=False)

    naive = ImageFont.truetype(str(SHS), 18)          # 裸调＝ExtraLight
    ours = truetype("card", 18)                        # 本模块＝Regular
    assert _ink(ours) > _ink(naive) * 2, "默认实例的陷阱没被挡住"


@needs_shs
def test_weight_env_selects_named_instance(monkeypatch):
    from tools.ui_font import truetype

    monkeypatch.setenv("ZND_UI_FONT_SCENE", str(SHS))
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT_SCENE", "Bold")
    bold = truetype("scene", 18)
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT_SCENE", "Regular")
    regular = truetype("scene", 18)
    assert _ink(bold) > _ink(regular)


@needs_shs
def test_per_face_weight_beats_global(monkeypatch):
    from tools.ui_font import truetype

    monkeypatch.setenv("ZND_UI_FONT", str(SHS))
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT", "Regular")
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT_SELECT", "Heavy")
    assert _ink(truetype("select", 18)) > _ink(truetype("card", 18))


@needs_shs
def test_unknown_weight_lists_what_is_available(monkeypatch):
    from tools.ui_font import truetype

    monkeypatch.setenv("ZND_UI_FONT_PLOT", str(SHS))
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT_PLOT", "SemiBold")
    with pytest.raises(ValueError, match="Heavy"):   # 报错里要带可用取值
        truetype("plot", 18)


def test_weight_on_a_static_font_is_an_error_not_a_no_op(monkeypatch):
    """在静态字体上设重量必须炸。

    静默忽略的话，你以为在看 Bold、其实还是 Regular——而这正是准备拿来
    比较字重的场合，结论会整个反过来。
    """
    from tools.ui_font import truetype

    monkeypatch.delenv("ZND_UI_FONT_CARD", raising=False)
    monkeypatch.delenv("ZND_UI_FONT", raising=False)
    monkeypatch.setenv("ZND_UI_FONT_WEIGHT_CARD", "Bold")
    with pytest.raises(ValueError, match="不是变量字体"):
        truetype("card", 18)


def test_truetype_without_weight_on_static_font_works(monkeypatch):
    from tools.ui_font import truetype

    for v in ("ZND_UI_FONT", "ZND_UI_FONT_CARD", "ZND_UI_FONT_WEIGHT",
              "ZND_UI_FONT_WEIGHT_CARD"):
        monkeypatch.delenv(v, raising=False)
    assert truetype("card", 18).getlength("章节") > 0
