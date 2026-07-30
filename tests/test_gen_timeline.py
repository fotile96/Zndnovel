from tools.gen_timeline import Expander

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
