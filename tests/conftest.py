"""跨测试模块共用的夹具。

目前只有一件事：**某些面的字体只存在于这台机器上**。裁决 F6 把 `cutin` 定成了
macOS 随系统分发的华文仿宋——它不是 OFL，不能入库，于是凡是真去渲染 cutin 的
测试在别的机器（云端 Ubuntu）上都取不到字。

这种情况要 **skip 而不是 fail**：字体没装不是代码坏了。但也**不能默默换字**跑过去
——那样测的就不是将要进游戏的那张图了。
"""

from __future__ import annotations

import pytest


def face_font_missing(face: str) -> bool:
    """这台机器上取不到该面配置的字体吗？"""
    from tools.ui_font import resolve
    try:
        resolve(face)
        return False
    except FileNotFoundError:
        return True


def needs_face_font(face: str):
    """给要真渲染某一面的测试用的 skip 标记。"""
    return pytest.mark.skipif(
        face_font_missing(face),
        reason=f"这台机器没有 {face} 面配置的字体（见 config/bake_fonts.yaml）")


def diff_bbox(a, b):
    """两张图差异的包围盒；无差异返回 None。

    **不要用 `ImageChops.difference(a, b).getbbox()`。** 在 RGBA 上 `getbbox()`
    只按 alpha 通道判非零——RGB 差到 255 而 alpha 相同时它照样返回 None。于是
    「盒外一个像素不动」这类断言会**永远绿**，而这正是它要守的东西。
    （2026-08-29 实测：`difference` 的 extrema 是 ((0,255),(0,255),(0,255),(0,0))，
    `getbbox()` 仍是 None，逐像素直接比却有 16788 个不同。）
    """
    from PIL import ImageChops

    d = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
    boxes = [bb for band in d.split() if (bb := band.getbbox()) is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))
