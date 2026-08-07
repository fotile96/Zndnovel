"""题库 ↔ 现行译文失同步检查。"""
import json

import pytest

from tools.check_qa_quotes import (check, load_suppressions, main,
                                    split_suppressed, superseded, _norm)


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


# ---- 带理由的抑制清单（2026-08-07 seg2-prep）----
#
# 背景：SEG-1 实跑报了 5 处，4 处真实漂移，第 5 处（id 10038，seg1-s2.yaml，
# 片段「，ユウイチ像是」）是题库自身叙述文与旧译的偶然子串重合——闸本身没有
# 抑制机制，此后每次 SEG 强制复跑都会再报一次这条已知伪报。要求：抑制必须
# 带理由、粒度精确到 (qa, id, fragment)、被抑制的命中仍要统计/播报只是不
# 计入退出码。

def _suppressions_file(tmp_path, items, name="suppressions.yaml"):
    import yaml
    p = tmp_path / name
    p.write_text(yaml.safe_dump(items, allow_unicode=True), encoding="utf-8")
    return p


def test_load_suppressions_missing_file_is_empty(tmp_path):
    assert load_suppressions(tmp_path / "nope.yaml") == []


def test_load_suppressions_requires_reason(tmp_path):
    """一条没有理由的抑制等于把闸悄悄关掉一块——缺 reason 必须整份拒绝加载，
    不能静默跳过那一条继续加载别的（那样会让"忘写理由"这个失误变得无害，
    削弱"必填"这条纪律本身）。"""
    p = _suppressions_file(tmp_path, [
        {"qa": "seg1-s2.yaml", "id": 10038, "fragment": "，ユウイチ像是"},
    ])
    with pytest.raises(ValueError, match="reason"):
        load_suppressions(p)


def test_load_suppressions_rejects_blank_reason(tmp_path):
    """空白字符串理由（纯空格/空串）等价于没写，同样拒绝——不能靠填一个
    空字符串糊弄过"必填"检查。"""
    p = _suppressions_file(tmp_path, [
        {"qa": "seg1-s2.yaml", "id": 10038, "fragment": "，ユウイチ像是",
         "reason": "   "},
    ])
    with pytest.raises(ValueError, match="reason"):
        load_suppressions(p)


def test_load_suppressions_with_reason_loads_fine(tmp_path):
    p = _suppressions_file(tmp_path, [
        {"qa": "seg1-s2.yaml", "id": 10038, "fragment": "，ユウイチ像是",
         "reason": "题库自身叙述文与旧译的偶然子串重合，非引用",
         "date": "2026-08-07"},
    ])
    items = load_suppressions(p)
    assert len(items) == 1 and items[0]["id"] == 10038


HIT_A = {"qa": "seg1-s2.yaml", "id": 10038, "fragment": "，ユウイチ像是"}
HIT_B = {"qa": "seg1-s2.yaml", "id": 9999, "fragment": "完全不同的另一处真实漂移"}
SUP_A = {"qa": "seg1-s2.yaml", "id": 10038, "fragment": "，ユウイチ像是",
         "reason": "偶然子串重合，非引用", "date": "2026-08-07"}


def test_split_suppressed_exact_triple_match(tmp_path):
    kept, suppressed = split_suppressed([HIT_A, HIT_B], [SUP_A])
    assert kept == [HIT_B]
    assert suppressed == [HIT_A]


def test_split_suppressed_does_not_match_different_fragment_same_id():
    """粒度收窄的核心断言：同一题库同一 id，但片段字符串不同（比如同一个 id
    未来又出现了一条新的、不同内容的漂移）——**不能**被这条旧抑制记录悄悄
    放过。这是"会不会在最该响的时候不响"的直接测试：粒度做粗了，新的真实
    漂移会被旧的豁免记录连坐豁免掉。"""
    new_drift_same_id = {"qa": "seg1-s2.yaml", "id": 10038, "fragment": "全新的另一段被改动的旧译文"}
    kept, suppressed = split_suppressed([new_drift_same_id], [SUP_A])
    assert kept == [new_drift_same_id]
    assert suppressed == []


def test_split_suppressed_does_not_match_different_qa_same_id_and_fragment():
    """同一 id、同一片段，但出现在另一份题库里——不该被本条豁免覆盖（豁免
    是针对"这份题库的这一处引用"作出的判断，换一份题库就是另一回事）。"""
    same_text_other_qa = {"qa": "seg2-s3.yaml", "id": 10038, "fragment": "，ユウイチ像是"}
    kept, suppressed = split_suppressed([same_text_other_qa], [SUP_A])
    assert kept == [same_text_other_qa]
    assert suppressed == []


def test_split_suppressed_preserves_suppressed_hits_not_silently_dropped():
    """被抑制的命中仍然完整保留在 suppressed 里（不是被丢弃）——上层要能
    统计/播报"N 处命中，其中 M 处豁免"，藏起来等于恒绿。"""
    kept, suppressed = split_suppressed([HIT_A], [SUP_A])
    assert suppressed == [HIT_A]
    assert suppressed[0]["fragment"] == "，ユウイチ像是"


# ---- CLI 集成：真实命中 + 抑制清单 + --strict 退出码 ----

def test_cli_suppressed_only_hit_passes_strict(tmp_path, capsys):
    d = _lane(tmp_path, [{"id": 10038, "zh": "得闻那支曲子才行。"}],
              [{"id": 10038, "zh": "得汀那支曲子才行。"}])
    qa = _qa(tmp_path, "参考答案里写着（得**闻**那支曲子）。")
    sup = _suppressions_file(tmp_path, [
        {"qa": qa.name, "id": 10038, "fragment": "得闻那支曲子",
         "reason": "测试固件：模拟已核实的伪报", "date": "2026-08-07"},
    ])
    rc = main(["--qa", str(qa), "--data-dir", str(d), "--min-len", "6",
               "--suppressions", str(sup), "--strict"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 处按抑制清单" in out
    assert "0 处需要处理" in out
    assert "[豁免]" in out
    assert "✅" in out


def test_cli_unsuppressed_hit_still_fails_strict_even_with_suppressions_file(tmp_path, capsys):
    """抑制清单存在、但这次命中不在清单里——必须照常报错退出，清单不能
    变成"这份题库以后随便报都没事"的通行证。"""
    d = _lane(tmp_path, [{"id": 1, "zh": "得闻那支曲子才行。"}],
              [{"id": 1, "zh": "得汀那支曲子才行。"}])
    qa = _qa(tmp_path, "参考答案里写着（得**闻**那支曲子）。")
    # 抑制清单里只豁免了一个完全不相关的 (qa, id, fragment) 三元组
    sup = _suppressions_file(tmp_path, [
        {"qa": "别的题库.yaml", "id": 99999, "fragment": "不相关的片段",
         "reason": "占位，不应匹配到本次命中", "date": "2026-08-07"},
    ])
    rc = main(["--qa", str(qa), "--data-dir", str(d), "--min-len", "6",
               "--suppressions", str(sup), "--strict"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "0 处按抑制清单" in out
    assert "1 处需要处理" in out
    assert "⚠" in out


def test_cli_mixed_suppressed_and_kept_hits(tmp_path, capsys):
    """一份题库里同时有一条豁免命中和一条真实命中——两者都要出现在输出里，
    但退出码只由未豁免的那条决定。"""
    d = _lane(tmp_path,
              [{"id": 10038, "zh": "得闻那支曲子才行。"}, {"id": 42, "zh": "完全不同的独特句子在此"}],
              [{"id": 10038, "zh": "得汀那支曲子才行。"}, {"id": 42, "zh": "完全改写过的另一句话在此"}])
    qa = _qa(tmp_path, "参考答案里写着（得**闻**那支曲子），另外还提到（完全不同的独特句子）。")
    sup = _suppressions_file(tmp_path, [
        {"qa": qa.name, "id": 10038, "fragment": "得闻那支曲子",
         "reason": "测试固件：已核实伪报", "date": "2026-08-07"},
    ])
    rc = main(["--qa", str(qa), "--data-dir", str(d), "--min-len", "6",
               "--suppressions", str(sup), "--strict"])
    out = capsys.readouterr().out
    assert rc == 1  # 仍有 1 条未豁免的真实命中
    assert "2 处，其中 1 处按抑制清单" in out
    assert "1 处需要处理" in out
    assert "[豁免]" in out and "得闻那支曲子" in out
    assert "⚠" in out and "完全不同的独特句子" in out


def test_cli_missing_reason_in_suppressions_file_aborts(tmp_path, capsys):
    """CLI 层同样受理由必填约束——不会因为在命令行里传了 --suppressions
    就绕过 load_suppressions() 的强制校验。"""
    d = _lane(tmp_path, [{"id": 1, "zh": "甲"}], [{"id": 1, "zh": "乙"}])
    qa = _qa(tmp_path, "「甲」")
    sup = _suppressions_file(tmp_path, [
        {"qa": qa.name, "id": 1, "fragment": "甲"},  # 缺 reason
    ])
    with pytest.raises(ValueError, match="reason"):
        main(["--qa", str(qa), "--data-dir", str(d), "--min-len", "1",
              "--suppressions", str(sup), "--strict"])


def test_cli_default_suppressions_path_used_when_flag_omitted(tmp_path, capsys, monkeypatch):
    """不传 --suppressions 时，默认读 `config/qa_quote_suppressions.yaml`
    （相对当前工作目录）——真实生产命令（见 runbook）没有带这个 flag，
    默认路径必须自己生效，不能要求每次手打。"""
    d = _lane(tmp_path, [{"id": 10038, "zh": "得闻那支曲子才行。"}],
              [{"id": 10038, "zh": "得汀那支曲子才行。"}])
    qa = _qa(tmp_path, "参考答案里写着（得**闻**那支曲子）。")

    workdir = tmp_path / "cwd"
    (workdir / "config").mkdir(parents=True)
    (workdir / "config" / "qa_quote_suppressions.yaml").write_text(
        f"- qa: {qa.name}\n  id: 10038\n  fragment: 得闻那支曲子\n"
        "  reason: 测试固件\n  date: '2026-08-07'\n", encoding="utf-8")
    monkeypatch.chdir(workdir)

    rc = main(["--qa", str(qa), "--data-dir", str(d), "--min-len", "6", "--strict"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[豁免]" in out
