import pytest

from tools.gen_timeline import Expander, parse_scene2card, run_plan

DAG = {"states": {
    "a_10": {"file": "snr_a_10_s", "scene": "scene_a_10", "title": "开场",
             "seq": [{"play": "scene_a_10", "title": "开场"}, {"goto": "a_20"}]},
    "a_20": {"file": "snr_a_10_s", "scene": "scene_a_20", "title": "选择",
             "seq": [{"play": "scene_a_20", "title": "选择"},
                     {"choice": 1, "goto": "a_30"}, {"choice": 2, "goto": "a_40"}]},
    "a_30": {"file": "snr_a_10_s", "scene": "scene_a_30", "title": "默认支",
             "seq": [{"play": "scene_a_30", "title": "默认支"}, {"goto": "end"}]},
    "a_40": {"file": "snr_a_10_s", "scene": "scene_a_40", "title": "另一支",
             "seq": [{"play": "scene_a_40", "title": "另一支"}, {"goto": "end"}]},
}, "scene_meta": {"scene_a_30": {"gets": [7], "cost": [25], "shows": [],
                                  "gameover": False, "complete": False}}, "crds": {}}
LEDGER = [
    {"id": 1, "file": "snr_a_10_s", "func": "scene_a_10", "kind": "narrative"},
    {"id": 2, "file": "snr_a_10_s", "func": "scene_a_20", "kind": "narrative"},
    {"id": 3, "file": "snr_a_10_s", "func": "scene_a_30", "kind": "narrative"},
    {"id": 4, "file": "snr_a_10_s", "func": "scene_a_40", "kind": "narrative"},
]

def _ex():
    return Expander(DAG, LEDGER, unit_funcs={})

def test_story_walks_default_choice_and_emits_units():
    ex = _ex()
    ex.story("a_10", choices={}, until=None)
    kinds = [(u["state"], u["ids"]) for u in ex.timeline if u["type"] == "unit"]
    assert kinds == [("a_10", [1]), ("a_20", [2]), ("a_30", [3])]

def test_story_honors_explicit_choice_and_gets_cards():
    ex = _ex()
    ex.story("a_10", choices={"a_20": 2}, until=None)
    assert [u["state"] for u in ex.timeline] == ["a_10", "a_20", "a_40"]
    ex2 = _ex(); ex2.story("a_10", choices={}, until=None)
    assert 7 in ex2.held           # scene_a_30 的 GET_CARD 生效

def test_until_stops_after_that_state():
    ex = _ex()
    ex.story("a_10", choices={}, until="a_20")
    assert [u["state"] for u in ex.timeline] == ["a_10", "a_20"]

def test_card_gate_goto_run_pattern_with_cross_file_jump():
    """card_gate→goto→run→goto 版式：run 事件不驱动行走，enter 跳转由 goto 承载。"""
    dag_with_gate = {"states": {
        "b_10": {"file": "snr_b_10_s", "scene": "scene_b_10", "title": "门控分支",
                 "seq": [{"play": "scene_b_10", "title": "门控分支"},
                         {"card_gate": 99, "held": True},
                         {"goto": "b_20_enter"},  # 持卡时走这条 goto → 跳转到 b_20_enter
                         {"run": "snr_b_20_s"},   # run 无需门控，由伴随 goto 承载
                         {"goto": "b_30"}]},      # 未持卡时走这条 goto → 跳转到 b_30
        "b_20_enter": {"file": "snr_b_20_s", "scene": "scene_b_20", "title": "跨脚本片段",
                       "seq": [{"play": "scene_b_20", "title": "跨脚本片段"}, {"goto": "end"}]},
        "b_30": {"file": "snr_b_10_s", "scene": "scene_b_30", "title": "默认下一状态",
                 "seq": [{"play": "scene_b_30", "title": "默认下一状态"}, {"goto": "end"}]},
    }, "scene_meta": {
        "scene_b_10": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
        "scene_b_20": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
        "scene_b_30": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
    }, "crds": {}}
    ledger = [
        {"id": 10, "file": "snr_b_10_s", "func": "scene_b_10", "kind": "narrative"},
        {"id": 20, "file": "snr_b_20_s", "func": "scene_b_20", "kind": "narrative"},
        {"id": 30, "file": "snr_b_10_s", "func": "scene_b_30", "kind": "narrative"},
    ]

    # 持卡 99 时：跳转到 b_20_enter
    ex_held = Expander(dag_with_gate, ledger, unit_funcs={})
    ex_held.held.add(99)
    ex_held.story("b_10", choices={}, until=None)
    states_held = [u["state"] for u in ex_held.timeline if u["type"] == "unit"]
    assert states_held == ["b_10", "b_20_enter"], f"持卡时应跳 b_20_enter，得{states_held}"

    # 未持卡 99 时：跳转到 b_30（run 事件被 skip=True 后的 goto 正常消费）
    ex_unheld = Expander(dag_with_gate, ledger, unit_funcs={})
    ex_unheld.story("b_10", choices={}, until=None)
    states_unheld = [u["state"] for u in ex_unheld.timeline if u["type"] == "unit"]
    assert states_unheld == ["b_10", "b_30"], f"未持卡时应跳 b_30，得{states_unheld}"


# Task 3 tests: fragment_sweep / replay / script / pool
DAG2 = {"states": {
    "b_10": {"file": "snr_b_10_s", "scene": "scene_b_10", "title": "一",
             "seq": [{"play": "scene_b_10", "title": "一"}, {"goto": "b_20_sel"}]},
    "b_20_sel": {"file": "snr_b_10_s", "scene": "scene_b_20_sel", "title": "选",
             "seq": [{"play": "scene_b_20_sel", "title": "选"},
                     {"choice": 1, "goto": "b_30"}, {"choice": 2, "goto": "b_40"}]},
    "b_30": {"file": "snr_b_10_s", "scene": "scene_b_30", "title": "甲",
             "seq": [{"play": "scene_b_30", "title": "甲"}, {"goto": "end"}]},
    "b_40": {"file": "snr_b_10_s", "scene": "scene_b_40", "title": "乙",
             "seq": [{"play": "scene_b_40", "title": "乙"}, {"goto": "end"}]},
}, "scene_meta": {}, "crds": {
    "11": {"stub": False, "req": [], "answers": [], "runs": []},
    "12": {"stub": False, "req": [11], "answers": [11], "runs": ["snr_b_10_f"]},
}}
LEDGER2 = [
    {"id": 10, "file": "snr_b_10_s", "func": "scene_b_10", "kind": "narrative"},
    {"id": 20, "file": "snr_b_10_s", "func": "scene_b_20_sel", "kind": "narrative"},
    {"id": 30, "file": "snr_b_10_s", "func": "scene_b_30", "kind": "narrative"},
    {"id": 40, "file": "snr_b_10_s", "func": "scene_b_40", "kind": "narrative"},
    {"id": 51, "file": "snr_crd_11", "func": "card_11_main", "kind": "narrative"},
    {"id": 52, "file": "snr_crd_12", "func": "card_12_main", "kind": "narrative"},
    {"id": 60, "file": "snr_b_10_f", "func": "scene_bf_10", "kind": "narrative"},
    {"id": 70, "file": "snr_common", "func": "poolFn", "kind": "narrative"},
]
S2C = {"b_10": 11, "b_20_sel": 12}   # sceneId→卡号映射作为 Expander 构造参数传入

def test_fragment_sweep_emits_cards_then_fchapter():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.story("b_10", {}, until=None)
    ex.fragment_sweep()
    kinds = [(u["unit_kind"], u.get("state"), u["ids"]) for u in ex.timeline if u["type"] == "unit"]
    assert ("card", "b_10", [51]) in kinds
    assert ("card", "b_20_sel", [52]) in kinds
    assert ("fscene", None, [60]) in kinds          # crd_12 的 runs 紧随
    assert {11, 12} <= ex.held

def test_replay_emits_marker_and_only_new_units():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.story("b_10", {}, until=None)                # 默认走 b_30
    ex.replay(at="b_20_sel", pick=2, until=None)
    types = [(e["type"], e.get("state")) for e in ex.timeline]
    assert ("marker", None) in types
    states = [u["state"] for u in ex.timeline if u["type"] == "unit"]
    assert states.count("b_20_sel") == 1 and "b_40" in states   # 折叠重讲

def test_script_and_pool_units():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.script("snr_crd_11")
    ex.pool("snr_common:poolFn")
    kinds = [(u["unit_kind"], u["ids"]) for u in ex.timeline]
    assert ("script", [51]) in kinds and ("pool", [70]) in kinds


# Task 3 fix round 1: Semantic regression tests for four critical branches
DAG3 = {"states": {
    "c_10": {"file": "snr_c_10_s", "scene": "scene_c_10", "title": "开始",
             "seq": [{"play": "scene_c_10", "title": "开始"}, {"goto": "c_20"}]},
    "c_20": {"file": "snr_c_10_s", "scene": "scene_c_20", "title": "中间",
             "seq": [{"play": "scene_c_20", "title": "中间"}, {"goto": "c_30_sel"}]},
    "c_30_sel": {"file": "snr_c_10_s", "scene": "scene_c_30_sel", "title": "选",
             "seq": [{"play": "scene_c_30_sel", "title": "选"},
                     {"choice": 1, "goto": "c_40"}, {"choice": 2, "goto": "c_50"}]},
    "c_40": {"file": "snr_c_10_s", "scene": "scene_c_40", "title": "甲",
             "seq": [{"play": "scene_c_40", "title": "甲"}, {"goto": "c_60"}]},
    "c_50": {"file": "snr_c_10_s", "scene": "scene_c_50", "title": "乙",
             "seq": [{"play": "scene_c_50", "title": "乙"}, {"goto": "c_60"}]},
    "c_60": {"file": "snr_c_10_s", "scene": "scene_c_60", "title": "结束",
             "seq": [{"play": "scene_c_60", "title": "结束"}, {"goto": "end"}]},
}, "scene_meta": {}, "crds": {
    "21": {"stub": False, "req": [], "answers": [], "runs": ["snr_c_10_f"]},
    "22": {"stub": False, "req": [], "answers": [], "runs": []},
    "23": {"stub": False, "req": [], "answers": [], "runs": []},
}}
LEDGER3 = [
    {"id": 100, "file": "snr_c_10_s", "func": "scene_c_10", "kind": "narrative"},
    {"id": 101, "file": "snr_c_10_s", "func": "scene_c_20", "kind": "narrative"},
    {"id": 102, "file": "snr_c_10_s", "func": "scene_c_30_sel", "kind": "narrative"},
    {"id": 103, "file": "snr_c_10_s", "func": "scene_c_40", "kind": "narrative"},
    {"id": 104, "file": "snr_c_10_s", "func": "scene_c_50", "kind": "narrative"},
    {"id": 105, "file": "snr_c_10_s", "func": "scene_c_60", "kind": "narrative"},
    {"id": 111, "file": "snr_crd_21", "func": "card_21_main", "kind": "narrative"},
    {"id": 112, "file": "snr_crd_22", "func": "card_22_main", "kind": "narrative"},
    {"id": 113, "file": "snr_crd_23", "func": "card_23_main", "kind": "narrative"},
    {"id": 120, "file": "snr_c_10_f", "func": "scene_cf_10", "kind": "narrative"},
]
S3C = {"c_10": 21, "c_20": 22, "c_40": 23}

def test_makeable_blocks_on_prefix_uncarded():
    """_makeable 阻断分支：c_10→21(req[]), c_20→22(req[]), c_40→23(req[])
    无交叉依赖，但 c_20 的卡 22 未持卡时，c_40 的卡 23 应被前缀阻断（同路由上
    c_20 是 c_40 之前的非 _sel 场景，其卡必须先持有）。
    fragment_sweep(only=[23]) 应因前缀阻断而不 emit；
    全量 sweep 应按顺序 emit 21，22，23。"""
    ex = Expander(DAG3, LEDGER3, {}, scene2card=S3C)
    ex.story("c_10", {}, until=None)  # route: [c_10, c_20, c_30_sel, c_40, c_60]

    # c_20 的卡 22 未持卡，c_40 的卡 23 被前缀阻断
    cards_before_count = len([u for u in ex.timeline if u.get("type") == "unit" and u.get("unit_kind") == "card"])
    ex.fragment_sweep(only=[23])
    cards_after_count = len([u for u in ex.timeline if u.get("type") == "unit" and u.get("unit_kind") == "card"])
    assert cards_before_count == cards_after_count, "Should emit no cards when prefix is uncarded"
    assert ex.held == set(), "held should remain empty"

    # 全量 sweep：21 → 22 → 23（按前缀顺序）
    ex2 = Expander(DAG3, LEDGER3, {}, scene2card=S3C)
    ex2.story("c_10", {}, until=None)
    ex2.fragment_sweep()
    card_units = [u for u in ex2.timeline if u.get("type") == "unit" and u.get("unit_kind") == "card"]
    card_states = [u.get("state") for u in card_units]
    assert card_states == ["c_10", "c_20", "c_40"], f"Card order should be c_10→c_20→c_40, got {card_states}"
    assert ex2.held == {21, 22, 23}, "All three cards should be held"

def test_only_filter_semantics():
    """only= 过滤语义：fragment_sweep(only=[21]) 只 emit 21，不 emit 22 和 23，held 恰增 {21}。"""
    ex = Expander(DAG3, LEDGER3, {}, scene2card=S3C)
    ex.story("c_10", {}, until=None)

    ex.fragment_sweep(only=[21])
    card_units = [u for u in ex.timeline if u.get("type") == "unit" and u.get("unit_kind") == "card"]
    assert len(card_units) == 1, f"Should emit exactly 1 card, got {len(card_units)}"
    assert card_units[0].get("state") == "c_10", f"Should emit c_10, got {card_units[0].get('state')}"
    assert card_units[0].get("ids") == [111], f"Should have IDs [111], got {card_units[0].get('ids')}"
    assert ex.held == {21}, f"held should be {{21}}, got {ex.held}"

def test_fscene_positioned_after_card():
    """fscene 紧随位置：card 21 的 runs["snr_c_10_f"] 应紧在 card 21 后（非批尾）。
    单位序列应精确为 [card c_10, fscene snr_c_10_f, card c_20, card c_40]
    （若为批尾实现则会是 [card c_10, card c_20, card c_40, fscene]——可判别）。"""
    ex = Expander(DAG3, LEDGER3, {}, scene2card=S3C)
    ex.story("c_10", {}, until=None)
    ex.fragment_sweep()

    # Only look at card and fscene units from fragment_sweep, not story's scene units
    units = [u for u in ex.timeline if u.get("type") == "unit" and u.get("unit_kind") in ["card", "fscene"]]
    # Verify exact order: [card(c_10/21), fscene(snr_c_10_f), card(c_20/22), card(c_40/23)]
    assert len(units) == 4, f"Should have 4 card/fscene units, got {len(units)}: {[(u.get('unit_kind'), u.get('state')) for u in units]}"

    # Precise sequence validation
    unit_kinds = [u.get("unit_kind") for u in units]
    assert unit_kinds == ["card", "fscene", "card", "card"], f"Kind order wrong: {unit_kinds}"

    # Verify unit 0 is card c_10
    assert units[0].get("unit_kind") == "card", "Unit 0 should be card"
    assert units[0].get("state") == "c_10", "Unit 0 should be card c_10"
    assert units[0].get("ids") == [111], "Card 21 (c_10) should have ID 111"

    # Verify unit 1 is fscene immediately after card c_10
    assert units[1].get("unit_kind") == "fscene", "Unit 1 should be fscene"
    assert units[1].get("src") == "snr_c_10_f", "fscene src should be snr_c_10_f"
    assert units[1].get("ids") == [120], "fscene should have ID 120"

    # Verify units 2-3 are cards c_20 and c_40
    card_states = [u.get("state") for u in units if u.get("unit_kind") == "card"]
    assert card_states == ["c_10", "c_20", "c_40"], f"Card state order wrong: {card_states}"

def test_replay_route_single_write():
    """replay route 单写回归：dedup_emit 不追加 route，由 story() 唯一写入。
    执行后 route 应精确为 ["b_10", "b_20_sel", "b_30", "b_20_sel", "b_40"]
    （b_20_sel 出现两次，各一次）。"""
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.story("b_10", {}, until=None)  # route: [b_10, b_20_sel, b_30]
    ex.replay(at="b_20_sel", pick=2, until=None)  # Re-enter at choice, pick option 2

    expected_route = ["b_10", "b_20_sel", "b_30", "b_20_sel", "b_40"]
    assert ex.route == expected_route, f"route should be {expected_route}, got {ex.route}"


# Task 5: parse_scene2card / run_plan
def test_parse_scene2card_skips_keyword_and_keeps_real_entries():
    """跳过 name == "keyword" 的反编译噪声行（键重复覆盖）；保留真实场景→卡号条目，
    容忍行内前导空白与无关邻近行。"""
    lua_text = '''\
sceneId2aCard = {}
sceneId2aCard.sof_10 = 1
sceneId2aCard.s1s_20 = 2
sceneId2aCard.keyword = 95
sceneId2aCard.keyword = 96
sceneId2aCard.keyword = 97
    sceneId2aCard.s1s_30 = 3
cHan2Zen = function(p0)
    local v0
end
'''
    result = parse_scene2card(lua_text)
    assert result == {"sof_10": 1, "s1s_20": 2, "s1s_30": 3}
    assert "keyword" not in result


def test_run_plan_dispatches_all_move_kinds_in_order():
    """run_plan 按声明顺序把每条移动分派到 Expander 对应方法：
    story/fragment_sweep/replay 的 DSL 键名与方法形参一致，直接 **展开；
    pool 的 "func"、script 的 "file" 换名为方法的位置参数（file_func/file_stem）。
    用 DAG2/LEDGER2/S2C 夹具跑一遍完整的 5 种移动，核对 timeline 形状与 held。"""
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    moves = [
        {"story": {"enter": "b_10", "until": None}},
        {"fragment_sweep": {}},
        {"pool": {"func": "snr_common:poolFn"}},
        {"script": {"file": "snr_crd_11"}},
        {"replay": {"at": "b_20_sel", "pick": 2, "until": None}},
    ]
    run_plan(ex, moves)

    shape = [(u["type"], u.get("unit_kind"), u.get("state"), u.get("ids")) for u in ex.timeline]
    assert shape == [
        ("unit", "scene", "b_10", [10]),
        ("unit", "scene", "b_20_sel", [20]),
        ("unit", "scene", "b_30", [30]),
        ("unit", "card", "b_10", [51]),
        ("unit", "card", "b_20_sel", [52]),
        ("unit", "fscene", None, [60]),
        ("unit", "pool", None, [70]),
        ("unit", "script", None, [51]),
        ("marker", None, None, None),
        ("unit", "scene", "b_40", [40]),
    ]
    assert ex.held == {11, 12}


def test_run_plan_rejects_unknown_move_key():
    """未知的顶层移动键必须明确报错（route_plan 是人工手写资产，typo 须当场暴露），
    异常信息须指明是第几条移动，便于定位。"""
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    moves = [
        {"story": {"enter": "b_10", "until": None}},
        {"teleport": {"to": "nowhere"}},
    ]
    with pytest.raises(ValueError, match=r"第 2 条"):
        run_plan(ex, moves)
