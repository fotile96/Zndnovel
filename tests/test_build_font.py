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


# ---------------------------------------------------------------------------
# PGF 头部竖向量度由 build_font 自己写，不再信任 ttf_pgf 二进制（2026-09-19）
# 起因：/tmp/pgftool/ttf_pgf 于 2026-09-12 被重编，丢了 2026-08-31 的头部补丁，
# 两份 PGF 的 ascender 都回到上游写死的 0x3F5（15.83 px）；引擎按
# `y + (ascender>>6) − top + 1` 摆字形，9px 槽的 ruby 因此整体下沉 6 px、压进正文。
# ---------------------------------------------------------------------------
import struct


@pytest.mark.skipif(not MONO.exists() or not REGULAR.exists(), reason="缺 third_party TTF")
def test_pgf_vertical_metrics_follow_freetype_size_metrics():
    """与 FreeType 的 size metrics 同算法：ascender 向上取整、descender 向下取整到整像素，
    26.6 定点。17px → 16/−5、9px → 9/−3，正是 2026-09-02 验证过的落点
    （docs/ops/eboot-kinsoku-research-2026-09-04.md §6.3）。"""
    assert bf.pgf_vertical_metrics(REGULAR, 17) == (16 << 6, -5 << 6)
    assert bf.pgf_vertical_metrics(MONO, 9) == (9 << 6, -3 << 6)


@pytest.mark.skipif(not MONO.exists(), reason="缺 third_party/LXGWWenKaiMono-Regular.ttf")
def test_patch_pgf_header_rewrites_size_resolution_and_ascender(tmp_path):
    """头部 6 个字段被改写成"px<<6 尺寸、72 dpi、FreeType 竖向量度"，其余字节原样。"""
    buf = bytearray(0x200)
    buf[4:8] = b"PGF0"
    # 模拟上游 ttf_pgf 写死的值：size = px*72/128、128 dpi、ascender 0x3F5、descender 0xFFFFFF75
    struct.pack_into("<iiii", buf, 0x24, int(9 * 72 / 128 * 64), int(9 * 72 / 128 * 64), 128 << 6, 128 << 6)
    struct.pack_into("<ii", buf, 0xD4, 0x3F5, -139)
    buf[0x100:0x110] = b"\xAA" * 16              # 头部其他字段的哨兵
    p = tmp_path / "x.pgf"
    p.write_bytes(buf)

    got = bf.patch_pgf_header(p, 9, MONO)

    data = p.read_bytes()
    assert struct.unpack_from("<iiii", data, 0x24) == (9 << 6, 9 << 6, 72 << 6, 72 << 6)
    assert struct.unpack_from("<ii", data, 0xD4) == (9 << 6, -3 << 6)
    assert got == {"ascender": 9, "descender": -3}
    assert data[0x100:0x110] == b"\xAA" * 16       # 没碰别的
    assert len(data) == 0x200


def test_patch_pgf_header_rejects_non_pgf(tmp_path):
    p = tmp_path / "bad.pgf"
    p.write_bytes(b"\0" * 0x200)
    with pytest.raises(ValueError):
        bf.patch_pgf_header(p, 9, MONO)
