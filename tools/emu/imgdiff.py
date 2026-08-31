"""截图比对：与 PPSSPPHeadless 同款 MSE 公式 + 可视化 diff 图。

MSE = Σ (actual - reference)² / (width × height × 3)，逐像素 RGB 三通道、忽略 alpha
（headless/README.md「Screenshot Comparison Details」）。阈值语义与 --max-mse 一致：
0 = 逐像素完全一致。
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageChops


def load(src: bytes | str | Path | Image.Image) -> Image.Image:
    if isinstance(src, Image.Image):
        img = src
    elif isinstance(src, bytes):
        img = Image.open(io.BytesIO(src))
    else:
        img = Image.open(src)
    return img.convert("RGB")


def mse(actual, reference) -> float:
    a, b = load(actual), load(reference)
    assert a.size == b.size, f"尺寸不一致: {a.size} vs {b.size}"
    diff = ImageChops.difference(a, b)
    # histogram() 按 R/G/B 依次给出各 256 桶计数，Σ count·v² 即平方差总和——O(768) 且精确。
    hist = diff.histogram()
    total = sum(count * (v % 256) ** 2 for v, count in enumerate(hist))
    return total / (a.size[0] * a.size[1] * 3)


def diff_image(actual, reference, amplify: int = 8) -> Image.Image:
    """左=实际，右=参照，下=放大 amplify 倍的差异图（黑=一致）。"""
    a, b = load(actual), load(reference)
    assert a.size == b.size, f"尺寸不一致: {a.size} vs {b.size}"
    w, h = a.size
    diff = ImageChops.difference(a, b).point(lambda v: min(v * amplify, 255))
    canvas = Image.new("RGB", (w * 2, h * 2), (32, 32, 32))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (w, 0))
    canvas.paste(diff, (w // 2, h))
    return canvas


def assert_match(actual, reference, *, max_mse: float = 0.0,
                 diff_out: str | Path | None = None) -> float:
    """断言两图 MSE ≤ 阈值；超阈时（若给了 diff_out）落可视化 diff 再抛错。返回实测 MSE。"""
    value = mse(actual, reference)
    if value > max_mse:
        hint = ""
        if diff_out is not None:
            Path(diff_out).parent.mkdir(parents=True, exist_ok=True)
            diff_image(actual, reference).save(diff_out)
            hint = f"，diff 已存 {diff_out}"
        raise AssertionError(f"截图不匹配: MSE={value:.4f} > {max_mse}{hint}")
    return value
