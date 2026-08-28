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
