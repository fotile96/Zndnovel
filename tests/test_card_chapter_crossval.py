"""config/card_chapter.yaml 全量交叉校验（P3 devwave1 数据闸补漏）。

背景：tools/ayano_test.py 的反剧透闸依赖 card_chapter.yaml 的 196 条手工推导
映射，此前 tests/test_ayano_test.py::test_real_card_chapter_data_gate 只硬编码
断言了 8 个卡号（Critical 原始证据）。终审的变异测试证明：把清单外的卡改早
（如卡 140 的 `s6f` 改成 `s1s`）全套测试仍全绿——泄题口重新打开而机检不响。

本文件补一条**读真实配置、覆盖全部 196 条**的交叉校验，用独立事实源验证
（不重写 assemble_context 的过滤逻辑，那是同义反复）：
  - 157 张场景/选择卡 ← data/scene2card.json（独立产物）
  - 13 张章节梗概卡（133–145）← lua_scripts/ 里 `myCard[N].hold = 1` 的
    赋值语句定位
  - 25 张关键词卡 ← 同上赋值定位法，其中 3 张（97/115/126）走 crd 主卡侧生
    路径 + scene2card 独立换算
  - 编外卡 200 ← lua_scripts/snr_e2_10_f.lua 内唯一一处 crd_200 引用

推导逻辑本身在 tools/verify_card_chapter.py（可独立重跑：
`uv run python tools/verify_card_chapter.py`），本文件只做断言。
"""
import yaml

from tools.pipelib import REPO
from tools.verify_card_chapter import (
    build_expected_mapping, crossval, expected_card_200,
    expected_chapter_summary_cards, expected_keyword_cards,
    expected_scene_cards, load_scene2card,
)


def _load_real_card_chapter():
    return yaml.safe_load(
        (REPO / "config" / "card_chapter.yaml").read_text(encoding="utf-8")) or {}


def test_scene2card_is_clean_no_keyword_noise():
    """CLAUDE.md 记载 sceneId2aCard 表里有 `keyword` 键重复覆盖的反编译噪声。
    确认 data/scene2card.json（流水线独立产物）已经把这噪声滤掉——不是本次
    新造，先核实其形态再当独立源用。"""
    scene2card = load_scene2card()
    assert "keyword" not in scene2card
    assert len(scene2card) == 157
    assert all(isinstance(v, int) for v in scene2card.values())
    # 每个键都形如 <章号>[a-z]?_<数字>(_sel)?，不是裸章节名
    assert all("_" in k for k in scene2card)


def test_scene_cards_cover_157_and_match_card_chapter():
    """A 类：157 张场景/选择卡，独立源 = scene2card.json，章节 = sceneId 首段
    （sof→s0f 特例，两者同为段 0、无行为差异）。"""
    card_chapter = _load_real_card_chapter()
    expected = expected_scene_cards()
    assert len(expected) == 157
    for card, ch in expected.items():
        assert card_chapter.get(card) == ch, (
            f"卡{card}：card_chapter.yaml={card_chapter.get(card)!r}，"
            f"scene2card.json 推出 {ch!r}")


def test_chapter_summary_cards_cover_13_and_match_card_chapter():
    """B 类：133–145 这 13 张章节梗概卡，独立源 = lua_scripts 里
    `myCard[N].hold = 1` 赋值语句所在的 `_f` 章节脚本文件名。"""
    card_chapter = _load_real_card_chapter()
    expected = expected_chapter_summary_cards()
    assert set(expected) == set(range(133, 146))
    for card, ch in expected.items():
        assert card_chapter.get(card) == ch, (
            f"卡{card}：card_chapter.yaml={card_chapter.get(card)!r}，"
            f"lua_scripts 赋值定位推出 {ch!r}")


def test_keyword_cards_cover_25_and_match_card_chapter():
    """C 类：25 张关键词卡。22 张走 `_s` 脚本直接闭包定位；97/115/126 这 3 张
    查无直接闭包，改走 crd 主卡侧生路径（crd_56→主卡56、crd_51→主卡51、
    crd_10→主卡10），主卡章节用 scene2card.json 独立换算，不信任
    card_chapter.yaml 自己的说法。"""
    card_chapter = _load_real_card_chapter()
    expected = expected_keyword_cards()
    want = ({95, 96, 97} | {105, 106, 107} | {109} | set(range(114, 118))
            | set(range(119, 133)))
    assert set(expected) == want, (
        f"缺失：{want - set(expected)}；多余：{set(expected) - want}")
    for card, ch in expected.items():
        assert card_chapter.get(card) == ch, (
            f"卡{card}：card_chapter.yaml={card_chapter.get(card)!r}，"
            f"独立源推出 {ch!r}")


def test_card_200_single_independent_reference_matches():
    """D 类：编外卡 200 全仓库唯一一处独立源（snr_e2_10_f.lua 内 crd_200 引用），
    只能单源确认，无法多源交叉——如实这样记录，不臆造第二个源。"""
    expected = expected_card_200()
    assert expected == {200: "e2f"}
    card_chapter = _load_real_card_chapter()
    assert card_chapter.get(200) == "e2f"


def test_full_196_coverage_by_independent_sources():
    """四类独立源加总必须精确覆盖 config/card_chapter.yaml 的全部 196 条，
    不多不少；若未来卡表变动导致缺口，这里会显式报出缺口卡号，不静默通过。"""
    card_chapter = _load_real_card_chapter()
    expected, sources = build_expected_mapping()
    assert len(card_chapter) == 196
    uncovered = set(card_chapter) - set(expected)
    assert uncovered == set(), f"以下卡号无法用独立源验证：{sorted(uncovered)}"
    extra = set(expected) - set(card_chapter)
    assert extra == set(), f"独立源多算出 card_chapter.yaml 里没有的卡号：{sorted(extra)}"
    counts = {}
    for tag in sources.values():
        counts[tag] = counts.get(tag, 0) + 1
    assert counts == {
        "A_scene": 157, "B_chapter_summary": 13, "C_keyword": 25, "D_card200": 1,
    }


def test_real_card_chapter_yaml_has_zero_mismatches_against_independent_sources():
    """反向校验（硬要求 2）：当前入库的 196 条映射，凡是能独立验证的部分，全部
    与独立源一致。若不一致，这是真发现——不改数据去迁就测试。"""
    card_chapter = _load_real_card_chapter()
    mismatches = crossval(card_chapter)
    assert mismatches == [], "发现 card_chapter.yaml 与独立源不一致：\n" + "\n".join(mismatches)


def test_crossval_catches_card_140_mutation():
    """硬要求 1：终审那个变异（把卡 140 的 `s6f` 改成 `s1s`，即把 seg5 的章节
    梗概卡挪进 seg1-s2 都算"此前"，B0 级泄题回归）必须被本交叉校验捕获——
    这是自我核验，不是空口声称测试有守护力。"""
    card_chapter = _load_real_card_chapter()
    assert card_chapter[140] == "s6f"          # 前提：仓库现行值未被污染
    mutated = dict(card_chapter)
    mutated[140] = "s1s"
    mismatches = crossval(mutated)
    assert any("卡140" in m for m in mismatches), (
        "变异（140: s6f→s1s）未被交叉校验捕获——反剧透闸的数据源无守护，回归到"
        "终审指出的漏洞")


def test_crossval_catches_arbitrary_scene_card_mutation():
    """同一变异手法在 A 类（场景/选择卡，占 196 条的大头）上也要能抓到——只验
    B 类（章节梗概卡）不够，因为 A 类是数量最大的一类。"""
    card_chapter = _load_real_card_chapter()
    assert card_chapter[41] == "s2s"           # Critical 原始证据卡之一
    mutated = dict(card_chapter)
    mutated[41] = "s1s"
    mismatches = crossval(mutated)
    assert any("卡41" in m for m in mismatches)


def test_crossval_catches_wholesale_clear():
    """整表清空（原 Critical 的另一种回归形态：D 类回归）同样要被抓住——清空后
    196 条全部从"有值"变成"None"，对已解出期望章节的每一条都应报不一致。"""
    mismatches = crossval({})
    assert len(mismatches) == 196
