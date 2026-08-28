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
