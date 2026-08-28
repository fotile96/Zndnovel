#!/usr/bin/env python3
"""烤字产物目录——可打标签，好让多套字体的产物并存对比。

默认 `build/<面>`；设了 `ZND_BUILD_TAG` 则是 `build/<面>__<标签>`。

**为什么需要它。** 换字体评估天然要「两套并排看」，而每个工具的产物目录原先是写死的，
第二次烤会把第一次的盖掉。靠人工挪目录也行，但中途一中断就说不清盘上那一套是谁烤的
——而两套字的产物**肉眼极难分辨**（都是中文、都在同样的位置），一旦搞混，比较的结论
就是错的且没人会发现。

    ZND_UI_FONT=…/SourceHanSansSC-VF.ttf ZND_BUILD_TAG=shs \\
        uv run python tools/bake_card.py       # → build/card_zh__shs/

标签只做目录名后缀，不做别的：产物内容、manifest 结构、各闸的判据都不受影响。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: 标签用于目录名，故只允许文件名安全的字符——打错了当场炸，而不是造出个怪目录。
_TAG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def tag() -> str:
    """当前的产物标签；未设返回空串。"""
    t = os.environ.get("ZND_BUILD_TAG", "").strip()
    if t and not _TAG_RE.match(t):
        raise ValueError(f"ZND_BUILD_TAG 只允许字母数字与 . _ -，收到 {t!r}")
    return t


def out_dir(name: str) -> Path:
    """`build/<name>`，带标签时为 `build/<name>__<tag>`。"""
    t = tag()
    return REPO / "build" / (f"{name}__{t}" if t else name)
