"""imgdiff 纯单元测试（不起模拟器）。"""
import pytest
from PIL import Image

from tools.emu.imgdiff import assert_match, diff_image, mse


def test_identical_is_zero():
    img = Image.new("RGB", (8, 4), (120, 30, 200))
    assert mse(img, img.copy()) == 0.0


def test_known_difference_exact():
    a = Image.new("RGB", (2, 1), (0, 0, 0))
    b = a.copy()
    b.putpixel((0, 0), (3, 0, 0))
    b.putpixel((1, 0), (0, 4, 0))
    # (3² + 4²) / (2×1×3) = 25/6
    assert mse(a, b) == pytest.approx(25 / 6)


def test_assert_match_writes_diff(tmp_path):
    a = Image.new("RGB", (4, 4), (0, 0, 0))
    b = Image.new("RGB", (4, 4), (255, 255, 255))
    out = tmp_path / "d.png"
    with pytest.raises(AssertionError, match="MSE"):
        assert_match(a, b, max_mse=1.0, diff_out=out)
    assert out.exists()
    assert diff_image(a, b).size == (8, 8)


def test_size_mismatch_rejected():
    with pytest.raises(AssertionError, match="尺寸"):
        mse(Image.new("RGB", (2, 2)), Image.new("RGB", (3, 2)))
