"""题库 ↔ 现行译文失同步检查。"""
import json
from tools.check_qa_quotes import check, superseded, _norm


def _lane(tmp_path, forward, patches):
    d = tmp_path / "data"
    d.mkdir()
    (d / "forward.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in forward), encoding="utf-8")
    (d / "patches.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in patches), encoding="utf-8")
    return d


def _qa(tmp_path, reference, name="seg.yaml"):
    p = tmp_path / name
    p.write_text("segment: seg\nquestions:\n  - id: q1\n    question: \"问\"\n"
                 f"    reference: \"{reference}\"\n", encoding="utf-8")
    return p


def test_catches_bank_quoting_superseded_text(tmp_path):
    """立案案例：回改把译文改了，题库还引着旧串。"""
    d = _lane(tmp_path, [{"id": 1, "zh": "得闻那支曲子才行。"}],
              [{"id": 1, "zh": "得汀那支曲子才行。"}])
    qa = _qa(tmp_path, "参考答案里写着（得**闻**那支曲子）。")
    hits = check([qa], d, min_len=6)
    assert len(hits) == 1 and hits[0]["id"] == 1, hits
    assert "得闻那支曲子" in hits[0]["fragment"]


def test_quote_not_in_parentheses_is_still_caught(tmp_path):
    """判据不能依赖「引文写在「」里」——第一版正是这么漏掉立案案例的。"""
    d = _lane(tmp_path, [{"id": 1, "zh": "旧的那句独特措辞在这里"}],
              [{"id": 1, "zh": "新的那句独特措辞在这里"}])
    for ref in ["「旧的那句独特措辞」", "（旧的那句独特措辞）", "旧的那句独特措辞"]:
        assert check([_qa(tmp_path, ref, f"{hash(ref)}.yaml")], d, min_len=6), ref


def test_unchanged_part_of_a_patched_line_is_not_reported(tmp_path):
    """同一行没被改动的部分，题库引它完全正确。"""
    d = _lane(tmp_path, [{"id": 1, "zh": "前半不变的独特措辞，后半旧文字"}],
              [{"id": 1, "zh": "前半不变的独特措辞，后半新文字"}])
    assert check([_qa(tmp_path, "「前半不变的独特措辞」")], d, min_len=6) == []


def test_fragment_still_present_elsewhere_is_not_reported(tmp_path):
    """`ユウイチ同学` 只在千秋侧被改，别处仍在——题库引它正确。

    只看该 id 的现行值会把这类全部报成失同步（实测 30 条候选里 19 条如此）。
    """
    d = _lane(tmp_path, [{"id": 1, "zh": "甲说ユウイチ同学好"}, {"id": 2, "zh": "乙说ユウイチ同学好"}],
              [{"id": 1, "zh": "甲说ユウイチ学长好"}])
    assert check([_qa(tmp_path, "「说ユウイチ同学好」")], d, min_len=6) == []


def test_ruby_only_patch_is_not_reported(tmp_path):
    """只加注音、不改文本的 patch 不算失同步——ruby 是渲染层标记。"""
    d = _lane(tmp_path, [{"id": 1, "zh": "妖怪纳哈梅就要找上门"}],
              [{"id": 1, "zh": "<妖,yāo>怪纳哈梅就要找上门"}])
    assert check([_qa(tmp_path, "「妖怪纳哈梅就要找上门」")], d, min_len=6) == []


def test_line_break_codes_do_not_cause_false_positives(tmp_path):
    d = _lane(tmp_path, [{"id": 1, "zh": "上半句_n_r下半句独特措辞"}],
              [{"id": 1, "zh": "上半句_n_r下半句改了措辞"}])
    assert check([_qa(tmp_path, "「上半句下半句独特措辞」")], d, min_len=6)


def test_superseded_excludes_the_current_value(tmp_path):
    d = _lane(tmp_path, [{"id": 1, "zh": "甲"}], [{"id": 1, "zh": "乙"}, {"id": 1, "zh": "丙"}])
    assert superseded(d) == {1: ["甲", "乙"]}, "现行值（末条 patch）不得进旧值集"


def test_norm_strips_bold_and_ruby_and_breaks():
    assert _norm("**甲**<乙,yi>丙_n丁 戊") == "甲乙丙丁戊"
