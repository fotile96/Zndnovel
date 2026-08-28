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
