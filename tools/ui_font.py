#!/usr/bin/env python3
"""烤字字体的统一取用口——**按面**可换。

在此之前字体有两套写法：sysgim 两个工具认 `ZND_UI_FONT`，plot/scene/card/select
四个把路径写死。于是「换个字体看看」在四个面上根本做不到。

**为什么要按面而不是一个全局变量。** 各面的字号档位差得很远：

| 面 | 字号 | 额外负担 |
|---|---|---|
| `select/` | 18/17px | 描边 |
| `sysgim/` | 12–17px | 描边、或字芯+距离场发光 |
| `scene/` | 11/10/9px | 无（15px 行高，垂直余量已用尽） |
| `card/` | 11/9/9px | 无（正文最紧的行只余 2px） |
| `plot/` | 定档 | 82×48 的格子 |

同一套字在 18px 和 9px 上不是一回事：霞鹜文楷 Regular 在 15px 以下笔干到不了一个
像素，整行发灰（sysgim 那边为此加了 `ZND_UI_FILL_GAIN=2.2` 的补偿）。所以合理的
终局多半是"大字号一套、小字号另一套"，而不是全库一套。

**用法。**

    # 全库换一套试
    ZND_UI_FONT=/path/to/Other.ttf uv run python tools/bake_card.py

    # 只给 card 换，其余仍用默认
    ZND_UI_FONT_CARD=/path/to/Other.ttf uv run python tools/bake_card.py

    # 各面分别指定
    ZND_UI_FONT=/path/to/Big.ttf ZND_UI_FONT_CARD=/path/to/Small.ttf ...

优先级：`ZND_UI_FONT_<面>` > `ZND_UI_FONT` > 随仓库分发的霞鹜文楷 Regular。

⚠ **换字体后测试会红**，这是对的：金标夹具里的墨迹尺寸、字号回落集、溢出判定全都是
对着默认字体实测出来的。换字评估应当看图与看 manifest，不是看测试绿不绿。

⚠ 换成 Bold 字形时 sysgim 两个工具的 `ZND_UI_FILL_GAIN` 要一并调回 1.0——增益是为
补 Regular 细笔调而加的，粗体上再叠只会把字腔糊死（裁决 Y6/Y14）。
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFont

REPO = Path(__file__).resolve().parent.parent

#: 随仓库分发（裁决 G1：25.6MB，入库以保证换机器即开即用；SIL OFL）。
BUNDLED = REPO / "third_party" / "LXGWWenKai-Regular.ttf"

#: 有字可换的五个面。**写成白名单**，好让打错的面名当场炸掉——
#: `ZND_UI_FONT_CARDS`（多个 s）若被默默忽略，人会以为"换了没效果"。
FACES = ("PLOT", "SCENE", "CARD", "SELECT", "SYSGIM")


def resolve(face: str) -> Path:
    """取某个面该用的字体路径。

    路径不存在时抛 `FileNotFoundError` 而**不回落到默认字体**：悄悄回落意味着
    你以为在评估新字体，看到的却仍是霞鹜文楷——而两次输出的差别恰好是零，
    最像"这字体没救了"的那种零。
    """
    key = face.upper()
    if key not in FACES:
        raise ValueError(f"未知的烤字面 {face!r}；可用：{', '.join(FACES)}")

    for var in (f"ZND_UI_FONT_{key}", "ZND_UI_FONT"):
        val = os.environ.get(var)
        if not val:
            continue
        p = Path(val)
        if not p.exists():
            raise FileNotFoundError(f"{var} 指向的字体不存在：{p}")
        return p

    return BUNDLED


#: 变量字体在没有显式指定重量时用哪一档。
#:
#: **不用字体自己的默认实例**——`SourceHanSansSC-VF` 的默认实例是 ExtraLight(250)，
#: 那是权重轴的**最小值**而非设计者推荐的正文字重。裸调 `ImageFont.truetype()` 拿到
#: 的就是它，于是两千多张图会在发丝级字重下烤出来，与「霞鹜文楷太细」这个换字动机
#: 恰好相反。而它**看起来是正常的**：不报错、不缺字，只是整体更灰一点——正是最容易
#: 被误读成「这字体不行」的失效形态。
DEFAULT_VF_INSTANCE = "Regular"


def _variation_names(font) -> list[str]:
    """字体的命名实例；静态字体返回空表。"""
    try:
        return [n.decode("utf-8", "replace") if isinstance(n, bytes) else str(n)
                for n in font.get_variation_names()]
    except OSError:
        return []   # Pillow 对非变量字体抛 OSError


def weight(face: str) -> str | None:
    """该面显式要求的重量；未指定返回 None。"""
    key = face.upper()
    return os.environ.get(f"ZND_UI_FONT_WEIGHT_{key}") or os.environ.get("ZND_UI_FONT_WEIGHT")


def truetype(face: str, size: int):
    """取该面的字体对象，并把变量字体钉到确定的重量档上。

    优先级同路径：`ZND_UI_FONT_WEIGHT_<面>` > `ZND_UI_FONT_WEIGHT` >
    `DEFAULT_VF_INSTANCE`（仅当字体是变量字体时才有意义）。

    在**静态**字体上指定重量会抛 `ValueError` 而不是静默忽略：静默忽略意味着你以为
    在看 Bold、其实还是 Regular，而这正是拿来比较字重的场合，结论会整个反过来。
    """
    path = resolve(face)
    font = ImageFont.truetype(str(path), size)
    names = _variation_names(font)
    want = weight(face)

    if not names:
        if want:
            raise ValueError(
                f"{path.name} 不是变量字体，无法指定重量 {want!r}——"
                f"请改用该字重对应的独立字体文件"
            )
        return font

    want = want or DEFAULT_VF_INSTANCE
    if want not in names:
        raise ValueError(
            f"{path.name} 没有名为 {want!r} 的重量实例；可用：{', '.join(names)}"
        )
    font.set_variation_by_name(want)
    return font


def size_cascade(face: str, default: list[int]) -> list[int]:
    """该面的字号级联档位，可按面覆盖：`ZND_UI_SIZE_CASCADE_<面>` > `ZND_UI_SIZE_CASCADE`。

    **为什么这也得可配。** 各工具里的级联（select `[18,17]`、scene `[11,10,9]`）是当初
    对着霞鹜文楷逐格实测定下来的，**它是字体的函数**：思源黑体同 px 下字身更高，
    `select/` 134 个按钮里有 118 个在 17px 上就撞了文字框的下沿（框高仅 20px）。
    级联写死的话，换字体这件事在 `select/` 上直接做不成——工具会（正确地）拒绝
    静默截断，然后什么也烤不出来。

    档位只增不改语义：仍是从大到小逐档试，第一个不越界的胜出。

        ZND_UI_SIZE_CASCADE_SELECT=18,17,16,15 uv run python tools/bake_select.py
    """
    key = face.upper()
    if key not in FACES:
        raise ValueError(f"未知的烤字面 {face!r}；可用：{', '.join(FACES)}")
    raw = os.environ.get(f"ZND_UI_SIZE_CASCADE_{key}") or os.environ.get("ZND_UI_SIZE_CASCADE")
    if not raw:
        return list(default)
    try:
        sizes = [int(x) for x in raw.replace(" ", "").split(",") if x]
    except ValueError:
        raise ValueError(f"字号级联要写成逗号分隔的整数，收到 {raw!r}") from None
    if not sizes:
        raise ValueError("字号级联不能为空")
    if sizes != sorted(sizes, reverse=True):
        raise ValueError(f"字号级联须从大到小，收到 {sizes}——顺序错了会先试小档，结果全是小字")
    return sizes


def describe(face: str) -> str:
    """给报告用的一行自述：字体文件名 + 重量档（若为变量字体）。"""
    path = resolve(face)
    names = _variation_names(ImageFont.truetype(str(path), 12))
    if not names:
        return path.name
    return f"{path.name}[{weight(face) or DEFAULT_VF_INSTANCE}]"
