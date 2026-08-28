#!/usr/bin/env python3
"""被字盖住的背景怎么补回来——**逐列纵向插值**。

`memoryThumbnail` 的照片字带与 `sysgim` D 族的面板都要这一手：字压在没有解析模型的
背景上（照片 / 渐变面板），擦掉字之后必须把背景补回来。

**是插值不是外推。** 两者的字带上下都有干净行，两端已知的窄缺口远比单端外推好条件。
外推只能假定「继续保持」，插值则被两端同时钉住，渐变、缓变纹理都能跟上。

**不做横向插值。** 这两处的字都横贯整幅，左右没有可用的锚。
"""

from __future__ import annotations

from PIL import Image


def vfill(im: Image.Image, box, above: int = 1, below: int = 1) -> Image.Image:
    """把 `box` 内的像素换成由其上下干净行逐列线性插值出来的值。

    `above` / `below` 是取锚行时相对盒边的偏移（默认紧贴盒外那一行）。返回新图。

    ⚠ 锚行必须在图内且**本身不含字**——调用方负责保证。盒紧贴图边时抬不到锚，
    这里直接抛错而不是悄悄改用外推：外推与插值的误差量级不同，混在一起会让
    「补得好不好」这件事无从判断。
    """
    l, t, r, b = box
    if t - above < 0 or b - 1 + below >= im.height:
        raise ValueError(
            f"盒 {box} 取不到上下锚行（图高 {im.height}）——"
            f"这里只做插值，不退化成外推")
    out = im.copy()
    src, dst = im.load(), out.load()
    span = (b - t) + 1
    for x in range(l, r):
        top, bot = src[x, t - above], src[x, b - 1 + below]
        for i, y in enumerate(range(t, b)):
            f = (i + 1) / span
            dst[x, y] = tuple(round(top[k] * (1 - f) + bot[k] * f)
                              for k in range(len(top)))
    return out
