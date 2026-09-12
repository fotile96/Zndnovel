"""build_font.widen_latin：拼音字母与空格步进撑到 RUBY_PITCH_PX/RUBY_FONT_PX em（P=5 → 556/1000），
数字/标点保持半角；字母墨迹居中；声调轮廓加粗后横向不越界。依赖仓库自带的 Mono TTF。"""
import pytest
from fontTools.ttLib import TTFont

from tools import build_font as bf

MONO = bf.TTF_BY_SIZE[9]


@pytest.mark.skipif(not MONO.exists(), reason="缺 third_party/LXGWWenKaiMono-Regular.ttf")
def test_widen_latin_sets_integer_pixel_pitch(tmp_path):
    out = bf.widen_latin(MONO, tmp_path / "w.ttf")
    f = TTFont(str(out))
    upm, cmap, hmtx, glyf = f["head"].unitsPerEm, f.getBestCmap(), f["hmtx"], f["glyf"]
    target = round(upm * bf.RUBY_PITCH_PX / bf.RUBY_FONT_PX)
    assert target == 556
    for ch in "kuāngAZǚ ":
        assert hmtx[cmap[ord(ch)]][0] == target, ch
    for ch in "17?":
        assert hmtx[cmap[ord(ch)]][0] == upm // 2, ch      # 数字/标点保持 Mono 半角 500
    g = glyf[cmap[ord("k")]]
    assert hmtx[cmap[ord("k")]][1] == int((target - (g.xMax - g.xMin)) / 2)   # 墨迹居中
    g = glyf[cmap[ord("ā")]]
    assert g.xMax - g.xMin <= target                          # 声调加粗后不越出步进框


REGULAR = bf.TTF_BY_SIZE.get(17, bf.TTF_DEFAULT)


@pytest.mark.skipif(not REGULAR.exists(), reason="缺 third_party/LXGWWenKai-Regular.ttf")
def test_widen_body_narrow_stretches_curly_quotes_and_interpunct(tmp_path):
    out = bf.widen_body_narrow(REGULAR, tmp_path / "b.ttf")
    f = TTFont(str(out))
    upm, cmap, hmtx = f["head"].unitsPerEm, f.getBestCmap(), f["hmtx"]
    for ch in bf.WIDEN_BODY_CHARS:
        assert hmtx[cmap[ord(ch)]][0] == upm, f"{ch!r} should be widened to full cell"
    # 汉字与拉丁字母不受影响
    assert hmtx[cmap[ord("一")]][0] == upm           # 汉字本来就是 1000
    assert hmtx[cmap[ord("A")]][0] < upm             # 拉丁保持比例宽
