"""`tools/ui_font.py` —— 烤字字体的统一取用口。

在此之前，字体在六个工具里有两套写法：sysgim 两个认 `ZND_UI_FONT`，plot/scene/
card/select 四个写死路径。于是「换个字体看看」这件本该一行的事，在四个面上做不到。

而**按面分别选字**才是真需求：select 按钮是 17–18px、card 正文 9px、scene 条 9–11px、
sysgim 是 12–17px 还要叠描边与发光——同一套字在这几档上的表现不是一回事。
"""

import os
from pathlib import Path

import pytest

from tools.ui_font import BUNDLED, FACES, resolve


@pytest.fixture(autouse=True)
def _neutral_config(monkeypatch):
    """默认把持久配置**清空**，让每条测试只检它自己声明的那一层。

    否则 `config/bake_fonts.yaml` 一改（比如把 card 定成思源 Medium），
    这里一堆测环境变量优先级的用例就会莫名其妙地红——它们要检的是**机制**，
    不是仓库当前选了哪套字。要检真配置的用例自己把缓存置回 None。
    """
    import tools.ui_font as uf
    monkeypatch.setattr(uf, "_CONFIG_CACHE", {})


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
    assert FACES == ("PLOT", "SCENE", "CARD", "SELECT", "SYSGIM", "EVENT", "CUTIN")


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


# ---------------------------------------------------------------------------
# 配置文件：哪一面（必要时哪一张）最后用了哪套字
# ---------------------------------------------------------------------------

CFG_YAML = """
default:
  font: third_party/LXGWWenKai-Regular.ttf
faces:
  card:
    font: third_party/SourceHanSansSC-VF.ttf
    weight: Medium
  sysgim:
    font: third_party/LXGWWenKai-Regular.ttf
    sheets:
      sys_20_c: {font: third_party/SourceHanSansSC-VF.ttf, weight: Bold}
"""


@pytest.fixture
def cfg(monkeypatch):
    import yaml

    import tools.ui_font as uf
    for v in list(os.environ):
        if v.startswith("ZND_UI_FONT"):
            monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(uf, "_CONFIG_CACHE", yaml.safe_load(CFG_YAML))
    return uf


def test_config_gives_per_face_font_and_weight(cfg):
    assert cfg.resolve("card").name == "SourceHanSansSC-VF.ttf"
    assert cfg.weight("card") == "Medium"
    assert cfg.resolve("plot") == BUNDLED          # 未列出的面走 default
    assert cfg.weight("plot") is None


@needs_shs
def test_config_per_sheet_beats_per_face(cfg):
    """**sysgim 存在的理由**：61 张分五个重建族，某一张需要例外时要能表达。"""
    assert cfg.describe("sysgim") == "LXGWWenKai-Regular.ttf"
    assert cfg.describe("sysgim", "sys_5_a") == "LXGWWenKai-Regular.ttf"
    assert cfg.describe("sysgim", "sys_20_c") == "SourceHanSansSC-VF.ttf[Bold]"


def test_env_still_wins_over_config(cfg, monkeypatch, tmp_path):
    """环境变量是**试验用的临时开关**，配置文件是持久决定——试验必须能压过决定。"""
    f = tmp_path / "Tmp.ttf"
    f.write_bytes(b"")
    monkeypatch.setenv("ZND_UI_FONT_CARD", str(f))
    assert cfg.resolve("card") == f


def test_config_pointing_at_a_missing_font_raises(cfg, monkeypatch):
    import yaml

    bad = yaml.safe_load(CFG_YAML)
    bad["faces"]["card"]["font"] = "third_party/DoesNotExist.ttf"
    monkeypatch.setattr(cfg, "_CONFIG_CACHE", bad)
    with pytest.raises(FileNotFoundError, match="bake_fonts.yaml"):
        cfg.resolve("card")


def _config_defect(face):
    """真配置在这一面上有没有毛病；没有则返回 None。

    **两种「取不到字体」要分开**：

    - 仓库内字体（相对路径）取不到 = 配置错，必须红。裁决 G1 把字体入库正是为了
      换机器即开即用，它缺了就是坏了。
    - 机器本地的系统字体（绝对路径）取不到 = 这台机器没装，不是配置错。cutin 定的
      华文仿宋是 macOS 随系统分发的，云端 Ubuntu 上根本不存在——若与「路径打错」
      同等对待，整套测试在云端会一片红，真正的配置错反倒淹没在里面。

    面名打错、索引越界这类 `ValueError` 两种情形下都是错，一律不吞。
    """
    import tools.ui_font as uf
    try:
        return None if resolve(face).exists() else f"{face}: 解析出的路径不存在"
    except FileNotFoundError:
        raw, _idx = uf._split_index(str(uf._config_entry(face, None).get("font", "")))
        if Path(raw).is_absolute():
            return None          # 系统字体，这台机器没装
        return f"{face}: 仓库内字体缺失 {raw}"


@pytest.mark.parametrize("font,defective", [
    ("third_party/DoesNotExist.ttf", True),      # 仓库内缺失＝配置错
    ("/nowhere/SystemOnly.ttf", False),          # 机器本地没装＝允许
])
def test_repo_fonts_must_exist_but_system_fonts_may_be_absent(cfg, monkeypatch,
                                                              font, defective):
    import yaml

    bad = yaml.safe_load(CFG_YAML)
    bad["faces"]["card"]["font"] = font
    monkeypatch.setattr(cfg, "_CONFIG_CACHE", bad)
    assert (_config_defect("card") is not None) is defective


def test_real_config_resolves_every_face():
    """真配置必须能解析——打错路径或面名在这里就该红，而不是等到烤到一半。"""
    import tools.ui_font as uf
    uf._CONFIG_CACHE = None          # 强制读盘上的真文件
    assert [d for d in (_config_defect(f) for f in FACES) if d] == []


# ---------------------------------------------------------------------------
# TTC 子字体索引：`路径#N`
# ---------------------------------------------------------------------------
#
# 字体评估要选仿宋/宋体时撞上的：macOS 的 `Songti.ttc` 一个文件里装着 8 款
# （Songti SC Black/Bold/Light/Regular、Songti TC 三款、STSong），
# 而本模块此前只接受"字体文件路径"，8 选 1 根本表达不出来。

SONGTI = Path("/System/Library/Fonts/Supplemental/Songti.ttc")
needs_songti = pytest.mark.skipif(
    not SONGTI.exists(), reason="需要 macOS 自带的 Songti.ttc（8 款子字体）")


def _fake_ttc(tmp_path, n_faces, name="Fake.ttc"):
    """一份只有 TTC 头的假集合：`ttcf` + 版本 + numFonts。

    索引的**解析与校验**不该需要真字体——这样这几条在没装 Songti 的机器
    （云端 Ubuntu）上照样跑，只有"真渲染出来的确实是那一款"需要真字体。
    """
    p = tmp_path / name
    p.write_bytes(b"ttcf" + (1).to_bytes(2, "big") + (0).to_bytes(2, "big")
                  + n_faces.to_bytes(4, "big"))
    return p


def test_a_single_face_font_has_index_zero(monkeypatch):
    from tools.ui_font import index

    monkeypatch.delenv("ZND_UI_FONT", raising=False)
    monkeypatch.delenv("ZND_UI_FONT_CARD", raising=False)
    assert index("card") == 0


def test_index_is_parsed_off_the_path_and_not_left_in_it(monkeypatch, tmp_path):
    """`#N` 是**取字体的一部分**，不是路径的一部分——`resolve()` 仍须返回可 open 的路径。"""
    from tools.ui_font import index

    ttc = _fake_ttc(tmp_path, 8)
    monkeypatch.setenv("ZND_UI_FONT_CUTIN", f"{ttc}#3")
    assert resolve("cutin") == ttc
    assert resolve("cutin").exists()
    assert index("cutin") == 3


def test_a_collection_without_an_index_is_rejected(monkeypatch, tmp_path):
    """**与变量字体默认实例同型的陷阱，必须挡住。**

    `Songti.ttc` 不带索引 = 第 0 款 = **Songti SC Black**（实测），即整个集合里
    最重的一款。它不报错、不缺字，只是"比预期黑一圈"——于是你以为在评估宋体正文，
    看到的其实是黑体级字重的宋，结论会整个反过来。

    与 `SourceHanSansSC-VF` 默认实例是 ExtraLight 是同一种失效形态，处理也该一样：
    当场炸掉，并把可选项列出来。
    """
    from tools.ui_font import index

    ttc = _fake_ttc(tmp_path, 8)
    monkeypatch.setenv("ZND_UI_FONT_CUTIN", str(ttc))
    with pytest.raises(ValueError, match="8"):
        index("cutin")
    with pytest.raises(ValueError, match="8"):
        resolve("cutin")        # 早于任何渲染——FONT_PATH 类消费者也被挡住


def test_index_out_of_range_says_how_many_there_are(monkeypatch, tmp_path):
    """Pillow 自己只会抛 `OSError: invalid argument`，看不出是索引越界。"""
    from tools.ui_font import index

    ttc = _fake_ttc(tmp_path, 8)
    monkeypatch.setenv("ZND_UI_FONT_CUTIN", f"{ttc}#8")   # 合法索引是 0..7
    with pytest.raises(ValueError, match="8"):
        index("cutin")


def test_index_on_a_single_face_font_is_rejected(monkeypatch):
    """`.ttf#1` 说明写的人以为它是集合——静默取 0 会让这个误解一直留着。"""
    from tools.ui_font import index

    monkeypatch.setenv("ZND_UI_FONT_CARD", f"{BUNDLED}#1")
    with pytest.raises(ValueError, match="LXGWWenKai"):
        index("card")


def test_index_zero_on_a_single_face_font_is_fine(monkeypatch):
    from tools.ui_font import index

    monkeypatch.setenv("ZND_UI_FONT_CARD", f"{BUNDLED}#0")
    assert resolve("card") == BUNDLED
    assert index("card") == 0


def test_missing_file_error_shows_the_path_without_the_index(monkeypatch):
    monkeypatch.setenv("ZND_UI_FONT_PLOT", "/nope/Missing.ttc#3")
    with pytest.raises(FileNotFoundError, match="Missing.ttc") as e:
        resolve("plot")
    assert "#3" not in str(e.value), "报错该指向要找的文件本身"


def test_config_carries_the_index_too(cfg, monkeypatch, tmp_path):
    """环境变量与配置文件**同一套解析**——否则试验选定的字进不了持久决定。"""
    import yaml

    from tools.ui_font import index

    ttc = _fake_ttc(tmp_path, 8)
    conf = yaml.safe_load(CFG_YAML)
    conf["faces"]["cutin"] = {"font": f"{ttc}#6"}
    monkeypatch.setattr(cfg, "_CONFIG_CACHE", conf)
    assert cfg.resolve("cutin") == ttc
    assert index("cutin") == 6


@needs_songti
def test_truetype_loads_the_requested_subfont(monkeypatch):
    """**本组测试的主张**：索引真的走到了 FreeType，而不只是被解析掉。

    判据用 `getname()`（字体自报家门），不是墨迹量——后者只能说"不一样"，
    说不出"是不是要的那一款"。
    """
    from tools.ui_font import truetype

    monkeypatch.setenv("ZND_UI_FONT_CUTIN", f"{SONGTI}#3")
    assert truetype("cutin", 18).getname() == ("Songti SC", "Light")
    monkeypatch.setenv("ZND_UI_FONT_CUTIN", f"{SONGTI}#4")
    assert truetype("cutin", 18).getname() == ("STSong", "Regular")


@needs_songti
def test_describe_names_which_subfont(monkeypatch):
    """报告里只写 `Songti.ttc` 等于没写——8 款里的哪一款才是这次要记的决定。"""
    from tools.ui_font import describe

    monkeypatch.setenv("ZND_UI_FONT_CUTIN", f"{SONGTI}#3")
    assert describe("cutin") == "Songti.ttc#3[Songti SC Light]"
