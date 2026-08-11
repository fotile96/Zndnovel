"""tools/sweep_punct.py 的行为闸。

每个用例对应一个**起草时真踩过的坑**，不是为覆盖率凑的。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import sweep_punct


def _repo(tmp_path, lines, *, anchors=(), patches=()):
    """lines: [(id, batch, zh)]；anchors: [id]；patches: [(id, zh)]"""
    root = tmp_path / "repo"
    data = root / "data"
    data.mkdir(parents=True)
    (data / "forward.jsonl").write_text(
        "\n".join(json.dumps({"id": i, "batch": b, "zh": z}, ensure_ascii=False)
                  for i, b, z in lines) + "\n", encoding="utf-8")
    if patches:
        (data / "patches.jsonl").write_text(
            "\n".join(json.dumps({"id": i, "zh": z, "reason": "review"}, ensure_ascii=False)
                      for i, z in patches) + "\n", encoding="utf-8")
    (root / "skeleton").mkdir()
    (root / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n  items:\n" + "".join(
            f'    - id: {i}\n      jp: "x"\n      zh: "y"\n' for i in anchors)
        if anchors else "[]", encoding="utf-8")
    (root / "config").mkdir()
    (root / "config" / "segments.yaml").write_text(
        '- {seg: 0, label: segA, batches: [1, 5]}\n'
        '- {seg: 1, label: segB, batches: [6, 9]}\n', encoding="utf-8")
    return root, data


def test_strips_only_at_line_end_or_before_break(tmp_path):
    """行末与 `_n`/`_r` 前才改；行中的一拍**不动**——这是 §7(a) 的判断题一侧。"""
    root, data = _repo(tmp_path, [
        (1, 1, "他没有说话……。"),
        (2, 1, "他没有说话……。_n然后走了。"),
        (3, 1, "【直哉】「……。对不起」"),          # 行中，不动
        (4, 1, "【彩野】「……。这样啊。也是呢」"),   # 行中，不动
    ])
    t, _ = sweep_punct.sweep_targets(data, repo=root)
    assert {x["id"] for x in t} == {1, 2}
    assert {x["id"]: x["new"] for x in t} == {
        1: "他没有说话……", 2: "他没有说话……_n然后走了。"}


def test_never_touches_long_vowel_dashes(tmp_path):
    """`——。`/`――。` 多是长音符 ー 的译法，句号本该留——起草时误收过这一类。"""
    root, data = _repo(tmp_path, [
        (1, 1, "【教师】「哦——。一下子就进了个好地方嘛」"),
        (2, 1, "【彩野】「啊――。是学校啊」"),
        (3, 1, "算了……。"),
    ])
    t, _ = sweep_punct.sweep_targets(data, repo=root)
    assert {x["id"] for x in t} == {3}


def test_skips_anchors_and_patched_but_reports_them(tmp_path):
    """跳过不等于藏起来：两类都要出现在 skipped 里。"""
    root, data = _repo(tmp_path, [
        (1, 1, "甲……。"), (2, 1, "乙……。"), (3, 1, "丙……。"),
    ], anchors=[1], patches=[(2, "乙……。")])
    t, sk = sweep_punct.sweep_targets(data, repo=root)
    assert [x["id"] for x in t] == [3]
    assert sk == {"anchor": [1], "patched": [2]}


def test_seg_filter_uses_batch_ranges(tmp_path):
    root, data = _repo(tmp_path, [(1, 3, "甲……。"), (2, 7, "乙……。")])
    t, _ = sweep_punct.sweep_targets(data, repo=root, seg_labels=["segA"])
    assert [x["id"] for x in t] == [1]
    t, _ = sweep_punct.sweep_targets(data, repo=root, seg_labels=["segA", "segB"])
    assert [x["id"] for x in t] == [1, 2]


def test_unknown_seg_label_is_an_error_not_a_silent_empty_sweep(tmp_path):
    """label 打错时静默扫 0 行是本项目反复吃亏的形态，必须报错。"""
    root, data = _repo(tmp_path, [(1, 3, "甲……。")])
    with pytest.raises(SystemExit):
        sweep_punct.sweep_targets(data, repo=root, seg_labels=["segX"])


def test_control_codes_and_length_never_grow(tmp_path):
    """只删一个句号：`_n`/`_r` 计数不变、长度只减不增（行宽闸不可能被它弄坏）。"""
    root, data = _repo(tmp_path, [(1, 1, "甲……。_n乙……。_r丙……。")])
    t, _ = sweep_punct.sweep_targets(data, repo=root)
    old, new = t[0]["old"], t[0]["new"]
    assert new.count("_n") == old.count("_n") and new.count("_r") == old.count("_r")
    assert len(new) < len(old) and new == "甲……_n乙……_r丙……"
