"""guide/ 攻略：generated/ 与定译数据源无漂移；有 typst 时还能编译（定译断言在编译期）。"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_guide  # noqa: E402


def test_generated_matches_sources():
    """gen 的产物已入库；数据源（cards.zh / dag.json / 选项定译）变了必须重跑 gen 再提交。"""
    for name, text in build_guide.generate().items():
        p = build_guide.GEN / name
        assert p.exists(), f"{p} 缺失，先跑 tools/build_guide.py gen"
        assert p.read_text(encoding="utf-8") == text, f"{p} 与数据源不一致，重跑 tools/build_guide.py gen"


def test_hand_order_matches_crd_scripts():
    """多卡谜题的「依次递 A、B、C」必须与 snr_crd_N.lua 里 selectCardObj 后的比较顺序一致（2026-09-12 用户反馈 crd_35 写反）。"""
    assert build_guide.check_hand_order() == []


def test_no_encore_mention():
    """用户裁定：攻略不提谢幕章。"""
    banned = ("encore", "谢幕", "snr_finale", "title_14")
    for p in list((build_guide.GUIDE / "chapters").glob("*.typ")) + [build_guide.GUIDE / "main.typ"]:
        text = p.read_text(encoding="utf-8")
        for w in banned:
            assert w not in text, f"{p.name} 提到了 {w!r}"
    for name in ("data.typ", "cards-table.typ", "options-table.typ"):
        text = (build_guide.GEN / name).read_text(encoding="utf-8")
        assert "SectionEx2\"" not in text and "\"200\"" not in text, f"{name} 混入了编外卡 200"


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst 未安装")
def test_compiles(tmp_path):
    out = tmp_path / "guide.pdf"
    r = subprocess.run(
        ["typst", "compile", "--root", str(build_guide.GUIDE), str(build_guide.GUIDE / "main.typ"), str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    assert out.stat().st_size > 100_000
