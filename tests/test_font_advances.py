"""17 px 正文字体的字形步进表 data/font_advances_17.json：校验器像素模型的数据源。

由 `uv run python tools/pgf_inspect.py export-advances build/font/lxgw17.pgf data/font_advances_17.json`
生成（引擎按 advanceH>>6 截断，表里存截断后的整数 px；只存 ≠ 默认 17 的码位）。
"""
import json
from pathlib import Path

import pytest

from tools import pgf_inspect as pi

REPO = Path(__file__).resolve().parent.parent
PGF = REPO / "build" / "font" / "lxgw17.pgf"
TABLE = REPO / "data" / "font_advances_17.json"


def test_advance_px_truncates_like_the_engine():
    assert pi.advance_px(4.25) == 4 and pi.advance_px(5.75) == 5 and pi.advance_px(17.0) == 17


def test_committed_table_has_the_expected_shape_and_latin_widths():
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    assert t["default"] == 17 and t["font"] == "lxgw17.pgf"
    adv = t["adv"]
    assert adv["A"] == 11 and adv["a"] == 9 and adv["i"] == 4 and adv["W"] == 14 and adv[" "] == 5
    assert "一" not in adv and "Ａ" not in adv          # 全角/汉字 = 默认 17，不入表
    assert adv["“"] == 5                                 # 弯引号在 LXGW 里是比例宽——校验器要告警


@pytest.mark.local_assets
@pytest.mark.skipif(not PGF.exists(), reason="缺 build/font/lxgw17.pgf（先跑 build_disc 的 font 阶段）")
def test_committed_table_matches_the_built_font():
    fresh = pi.export_advances(PGF.read_bytes(), "lxgw17.pgf")
    assert json.loads(TABLE.read_text(encoding="utf-8")) == fresh
