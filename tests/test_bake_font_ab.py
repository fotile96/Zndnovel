"""`tools/bake_font_ab.py` —— 换字体的逐面对照图。

这份对照图是**用户挑字体时唯一看的东西**，所以它自己不能有失真：并排的两格若因
工具的合成方式不同而长得不一样，比较的结论就是错的，而且看图的人无从察觉。
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.bake_font_ab import FACES, _label_font, _trio_col, _trio_rows  # noqa: E402

#: 三联图的底色（`_trio_rows`/`_trio_col` 里的深灰）。
BACKDROP = (26, 26, 26, 255)


def _transparent_cell():
    """一格**透明底**产物：白字 + 全透明背景。

    `cutin/` 与 `event/` 两面的产物就是这样——发光字幕条压在游戏画面上，
    底是透明的。前四面（card/select/plot/scene/sysgim）则是不透明整图。
    """
    im = Image.new("RGBA", (6, 4), (255, 255, 255, 0))
    im.putpixel((3, 2), (255, 255, 255, 255))
    return im


@pytest.mark.parametrize("make", [_trio_rows, _trio_col])
def test_transparent_products_are_composited_not_punched_through(make):
    """透明底产物必须**合成到底色上**，不能连同 alpha 一起贴进去。

    `paste()` 会把源图的 alpha 一并写入，于是透明背景在对照图上变成**透明的洞**——
    在浅色背景的看图器里，白色发光字幕条恰好变得完全看不见。而这一面
    （`cutin/` 章节字幕卡）正是白字透明底，也正是当前要挑字体的那一面。
    """
    row = make([("A 版", _transparent_cell())], "样例", 2, _label_font())[0]
    assert row.getpixel((row.width - 1, row.height - 1))[3] == 255, "右下角被开了洞"
    assert row.getchannel("A").getextrema() == (255, 255), "对照图里出现了半透明像素"


def test_cutin_is_a_comparable_face():
    """`cutin/` 要能进对照图——否则这一面换字体只能靠逐张开产物目录肉眼比。"""
    assert "cutin" in FACES
    sub, cells_fn, _scale, orig, _layout = FACES["cutin"]
    assert sub == "cutin_zh"
    assert (REPO / orig).is_dir()
    for _name, spec in cells_fn([]):
        assert spec(REPO / orig).exists(), "取样指向了不存在的原图"
