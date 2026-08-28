"""`tools/check_sysgim_text.py` —— sysgim 译文数据的 schema 闸。

这两份文件在此之前**零校验**：`tests/` 里搜不到对它们的任何引用。实测过两种打错
方式——图名写错要跑到读图那一步才 `FileNotFoundError`，漏 `zh` 字段是
`KeyError: 'zh'`。**都是崩溃，不是闸**：不告诉你哪一行、哪个字段、该怎么改。
"""

import json

import pytest

from tools.check_sysgim_text import GLOW, OUTLINE, check, run


def _write(tmp_path, rows, name="t.jsonl"):
    p = tmp_path / name
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return p


GOOD = {"file": "sys_5_a", "row": 0, "box": [0, 0, 268, 25], "jp": "あ", "zh": "啊", "note": ""}


def test_real_data_has_no_errors():
    """**本文件的主张**：仓库现有的 sysgim 数据是合规的。这条一旦红，
    说明有人往里写了工具吃不下的东西——而且是在烤字之前就该发现。"""
    errs, _todo = run()
    assert errs == [], "\n".join(str(e) for e in errs)


def test_untranslated_rows_are_todo_not_error(tmp_path):
    """`zh` 为空是「原始语料已落盘、译文待补」的中间态，不是缺陷。

    若把它算成错误，闸会一直红到翻译做完为止，那期间它守不住任何真问题。

    ⚠ 这条起初写成「对真数据断言 len(todo) >= 1」——当时 C 类 21 行正待译。
    翻译一做完它就红了：**它钉的是一个临时状态，不是机制**。改用合成数据测机制，
    真数据的待译数交给 `test_real_data_has_no_errors` 那条去管（它只管错误数）。
    """
    todo_row = dict(GOOD); todo_row["zh"] = ""
    errs, todo = check(_write(tmp_path, [todo_row]), box_required=True)
    assert errs == []
    assert len(todo) == 1 and todo[0].kind == "待译"


def test_deferred_rows_are_neither_error_nor_todo(tmp_path):
    """`deferred`（工具做不了，如 sys_1_i 的箭头晕）与「待译」是两回事：
    前者译文可能已经写好了、只是渲不出来，不该混进待译计数里催人去翻。"""
    row = dict(GOOD); row["zh"] = ""; row["deferred"] = True
    errs, todo = check(_write(tmp_path, [row]), box_required=True)
    assert errs == [] and todo == []


def test_missing_required_field_is_caught(tmp_path):
    bad = dict(GOOD); bad.pop("zh")
    errs, _ = check(_write(tmp_path, [bad]), box_required=True)
    assert any(e.kind == "缺字段" and "zh" in e.detail for e in errs)


def test_typo_field_name_is_caught(tmp_path):
    """打错字段名是最难发现的一类——工具会**默默忽略**它，译文看起来"写了"
    却永远不会被用上。"""
    bad = dict(GOOD); bad["zh_"] = bad.pop("zh")
    errs, _ = check(_write(tmp_path, [bad]), box_required=True)
    assert any(e.kind == "未知字段" for e in errs)


def test_nonexistent_sheet_is_caught_before_baking(tmp_path):
    bad = dict(GOOD); bad["file"] = "sys_does_not_exist"
    errs, _ = check(_write(tmp_path, [bad]), box_required=True)
    assert any(e.kind == "图不存在" for e in errs)


def test_duplicate_row_number_is_caught(tmp_path):
    errs, _ = check(_write(tmp_path, [GOOD, dict(GOOD)]), box_required=True)
    assert any(e.kind == "重复行号" for e in errs)


def test_box_outside_the_image_is_caught(tmp_path):
    bad = dict(GOOD); bad["box"] = [0, 0, 9999, 25]
    errs, _ = check(_write(tmp_path, [bad]), box_required=True)
    assert any(e.kind == "box 越界" for e in errs)


def test_zero_area_box_is_caught(tmp_path):
    bad = dict(GOOD); bad["box"] = [10, 10, 10, 25]
    errs, _ = check(_write(tmp_path, [bad]), box_required=True)
    assert any(e.kind == "box 越界" for e in errs)


def test_glow_requires_box_outline_does_not(tmp_path):
    """两份文件的 schema 差异**是工具行为的一部分**，不是疏忽——glow 每行都是
    独立的盒；outline 默认按墨迹自动分段，`box` 是例外声明。"""
    no_box = {k: v for k, v in GOOD.items() if k != "box"}
    errs_glow, _ = check(_write(tmp_path, [no_box], "g.jsonl"), box_required=True)
    errs_out, _ = check(_write(tmp_path, [no_box], "o.jsonl"), box_required=False)
    assert any(e.kind == "缺 box" for e in errs_glow)
    assert errs_out == []


def test_outline_half_boxed_sheet_is_caught(tmp_path):
    """一张图上「一半行带 box」多半是漏写：那张图的自动分段结果已经不可信，
    而工具只会照着半套几何渲下去。"""
    rows = [{"file": "sys_20_c", "row": i, "jp": "あ", "zh": "啊", "note": ""} for i in range(4)]
    rows[0]["box"] = [0, 0, 50, 16]
    rows[1]["box"] = [0, 16, 50, 32]
    errs, _ = check(_write(tmp_path, rows), box_required=False)
    assert any(e.kind == "box 半带" for e in errs)


def test_single_box_override_is_allowed(tmp_path):
    """只标一行是合法的——`sys_22_ba/bb` 就是这么用的（只改 x0–66，右边是音量格）。"""
    rows = [{"file": "sys_20_c", "row": i, "jp": "あ", "zh": "啊", "note": ""} for i in range(4)]
    rows[0]["box"] = [0, 0, 50, 16]
    errs, _ = check(_write(tmp_path, rows), box_required=False)
    assert errs == []
