"""`tools/check_bake_text.py` —— 烤字译文数据的 schema 闸（全部面共用一道）。

这两份文件在此之前**零校验**：`tests/` 里搜不到对它们的任何引用。实测过两种打错
方式——图名写错要跑到读图那一步才 `FileNotFoundError`，漏 `zh` 字段是
`KeyError: 'zh'`。**都是崩溃，不是闸**：不告诉你哪一行、哪个字段、该怎么改。
"""

import json

import pytest

from tools.check_bake_text import GLOW, OUTLINE, SOURCES, check, run


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


def test_every_registered_source_is_actually_checked():
    """**加新面时往 SOURCES 加一行，别新起一个闸。**

    每个面一个专用闸，等于每个面都有机会漏掉一条检查——sysgim 那两份数据此前
    零校验，正是因为没人为它们单独写过闸。
    """
    names = {d.name for d, _img, _b in SOURCES}
    assert "sysgim_outline_text.jsonl" in names
    assert "sysgim_glow_text.jsonl" in names
    assert "event_op_text.jsonl" in names
    for data, img_dir, _box in SOURCES:
        assert img_dir.is_dir(), img_dir


def test_event_op_corpus_is_four_paragraph_blocks():
    """`event/op_*` 的渲染单元是**段**不是行。

    发光半径 18 与行距 18–19 相当，逐行盒的远场永远不干净——实测 15 个逐行盒有 4 个
    被底色收敛检查拒绝，且放宽/收紧盒形都救不回来（离底 6.5→45.0 反而更差）。
    段落盒可行，但需 ≥14px 边距。这条钉住那个结构性事实。
    """
    import json

    from tools.check_bake_text import EVENT_OP

    rows = [json.loads(l) for l in EVENT_OP.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 4
    assert sum(r["jp"].count("\n") + 1 for r in rows) == 15
    assert {r["file"] for r in rows} == {"op_1_a", "op_2_a", "op_3_a"}
    # _b 不进数据：它是 _a 的虚化版（高斯 r=1.5，alpha 平均残差 0.4）
    assert not any(r["file"].endswith("_b") for r in rows)


def test_geo_footprint_params_are_a_known_row_field(tmp_path):
    """`geo`（`bake_para_glow` 的 geo_footprint 遮盖参数，`bake_mask.plan_geo` 同名同义）
    与 `align` 一样是逐行字段，不是打错的字段名。探索地图底栏是第一份既走几何足迹、
    又归本闸管辖的数据。"""
    row = dict(GOOD)
    row["geo"] = {"keep": [], "r_old": 9, "bg": [255, 255, 255, 0], "glow_floor": 12}
    errs, _ = check(_write(tmp_path, [row]), box_required=True)
    assert errs == []


def test_select_map_info_is_registered():
    """探索地图底栏的译文数据归本闸管：加新面时往 SOURCES 加一行，别新起一个闸。"""
    names = {d.name for d, _img, _b in SOURCES}
    assert "select_map_info_text.jsonl" in names
