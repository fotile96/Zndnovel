"""guide/ 攻略：generated/ 与定译数据源无漂移；有 typst 时还能编译（定译断言在编译期）。"""
import json
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
    """凡要递卡的谜题，正文「递 …」必须与 snr_crd_N.lua 里 selectCardObj 后的比较顺序逐张一致。

    2026-09-12 用户反馈 crd_35 顺序写反；2026-09-13 又反馈 crd_30 漏掉开头的卡 1。"""
    assert build_guide.check_hand_order() == []


def test_card1_is_a_real_answer():
    """卡 1 是 crd_2/30/108 的合法答案，不是哨兵值。

    钉住 2026-09-13 的根因：提取器曾用「卡号 > 1」筛掉错卡计数器的 0/1，把卡 1 一并误伤。
    正确做法是绑定 oCard.selectCardObj() 的返回变量。这里同时钉 build_guide 的有序口径
    与 data/dag.json 的成员口径，两边都不许再回退。"""
    order = build_guide.expected_hand_order()
    assert order[2] == [1]
    assert order[108] == [1]
    assert order[30][0] == 1, "crd_30 第一步递的就是卡 1"

    dag = json.loads((REPO / "data/dag.json").read_text(encoding="utf-8"))
    for n in (2, 30, 108):
        assert 1 in dag["crds"][str(n)]["answers"], f"data/dag.json 的 crd_{n} 又把卡 1 滤掉了，重跑 tools/build_dag.py"


def test_route_feasible():
    """正文的故事/片段交替按引擎规则（时间轴截断、沙漏、做卡前缀）必须走得通。

    2026-09-19 玩家反馈 5 处「几轮压成一轮」「做卡顺序反」「场景已不在时间轴上」，
    typst 断言与递卡顺序校验都抓不到，故加模拟器 tools/guide_route_check.py。"""
    import guide_route_check

    assert guide_route_check.check() == []


def test_route_sim_engine_rules():
    """模拟器本身钉住几条引擎事实（改 lua 解析或规则时先过这里）。"""
    import guide_route_check as g

    sim = g.Sim()
    assert sim.story("s1s_20", [], set()) == "timeover"          # 首场固定 100
    sim.make(2)
    # 教程后从头讲：四个 25 的场景正好在『想起约定』沙漏满，讲不到『午休的教室』
    assert sim.story("s1s_20", ["想不起约定"], set()) == "timeover"
    assert sim.route[-1].scene == "s1s_60"
    # 未持卡的耗时 100 选择场景：选项弹出前就 Time over
    sim2 = g.Sim()
    sim2.held |= {2, 3, 4, 5, 9, 10, 11, 133, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47, 48, 50, 51, 52, 55, 58, 59, 60, 61, 134}
    sim2.story("s1s_20", ["没有约", "不去"], set())
    assert sim2.route[-1].scene == "s3s_20_sel" and sim2.time >= 100
    # 时间轴截断：回到分歧点重讲后，之前那条支线的场景不再能做卡
    sim3 = g.Sim()
    sim3.story("s1s_20", [], set()); sim3.make(2)
    sim3.story("s1s_20", ["想不起约定"], set()); sim3.make(3); sim3.make(4)
    sim3.story("s1s_35_sel", ["约好了"], set())
    with pytest.raises(g.RouteError):
        sim3.make(6)  # 『想不起约定』已被截掉


def test_no_real_name_spoiler():
    """用户 2026-09-22 裁定：攻略里不写 Sakura 的真名「佐仓雪乃／雪乃」，一律用 Sakura。

    游戏到章节 5 的现实层才说出这个名字，攻略第 1 章的人名说明与 EX2 导语曾提前写出。
    只查会渲染的文件；generated/data.typ 的场景标题字典里有「雪乃」这个键，但正文不引用它。"""
    banned = ("雪乃", "佐仓", "佐倉")
    files = list((build_guide.GUIDE / "chapters").glob("*.typ")) + list((build_guide.GUIDE / "appendix").glob("*.typ"))
    files += [build_guide.GUIDE / "main.typ", build_guide.GUIDE / "template.typ",
              build_guide.GEN / "cards-table.typ", build_guide.GEN / "options-table.typ"]
    for p in files:
        text = p.read_text(encoding="utf-8")
        for w in banned:
            assert w not in text, f"{p.name} 写出了真名 {w!r}"


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
