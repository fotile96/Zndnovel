from tools.check_timeline import check
from tests.test_gen_timeline import DAG2, LEDGER2, S2C
from tools.gen_timeline import Expander

def _full_timeline():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.story("b_10", {}, until=None)
    ex.fragment_sweep()
    ex.replay(at="b_20_sel", pick=2, until=None)
    ex.pool("snr_common:poolFn")
    return ex.timeline

def test_clean_timeline_passes():
    errs = check(_full_timeline(), LEDGER2, DAG2, S2C, gates=[])
    assert errs == []

def test_missing_and_duplicate_ids_detected():
    tl = _full_timeline()
    tl[0]["ids"] = []                       # 弄丢 id 10
    errs = check(tl, LEDGER2, DAG2, S2C, gates=[])
    assert any("缺失" in e and "10" in e for e in errs)
    tl2 = _full_timeline(); tl2[1]["ids"].append(10)
    assert any("重复" in e for e in check(tl2, LEDGER2, DAG2, S2C, gates=[]))

def test_gate_violation_detected():
    errs = check(_full_timeline(), LEDGER2, DAG2, S2C,
                 gates=[{"unit_state": "b_10", "requires_cards": [99]}])
    assert any("门控" in e and "99" in e for e in errs)

def test_crd_req_violation_detected():
    tl = _full_timeline()
    card_units = [u for u in tl if u.get("unit_kind") == "card"]
    tl.remove(card_units[0])                # 抽掉 crd_11，crd_12 的 req=[11] 失去前提
    errs = check(tl, LEDGER2, DAG2, S2C, gates=[])
    assert any("req" in e for e in errs)


# Hotfix B3: check() 的 held 推导须与展开器口径对齐——req 可由 crd 自身 gets /
# fscene（_f 章）/ scene 的 subcall 的 scene_meta.gets 满足，不止 scene 的 play 事件。
DAG_GRANT = {"states": {
    "z_10": {"file": "snr_z_10_s", "scene": "scene_z_10", "title": "甲",
             "seq": [{"play": "scene_z_10", "title": "甲"},
                     {"subcall": "scene_z_dispatch"},
                     {"goto": "z_20"}]},
    "z_20": {"file": "snr_z_10_s", "scene": "scene_z_20", "title": "乙",
             "seq": [{"play": "scene_z_20", "title": "乙"}, {"goto": "end"}]},
}, "scene_meta": {
    "scene_z_10": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
    "scene_z_dispatch": {"gets": [201], "cost": [], "shows": [], "gameover": False, "complete": False},
    "scene_z_20": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
    "scene_zf_complete": {"gets": [203], "cost": [], "shows": [], "gameover": False, "complete": True},
}, "crds": {
    "60": {"stub": False, "req": [], "answers": [], "runs": ["snr_z_10_f"], "gets": [202]},
    "70": {"stub": False, "req": [201, 202, 203], "answers": [], "runs": []},
}}
LEDGER_GRANT = [
    {"id": 400, "file": "snr_z_10_s", "func": "scene_z_10", "kind": "narrative"},
    {"id": 401, "file": "snr_z_10_s", "func": "scene_z_dispatch", "kind": "narrative"},
    {"id": 402, "file": "snr_z_10_s", "func": "scene_z_20", "kind": "narrative"},
    {"id": 410, "file": "snr_crd_60", "func": "card_60_main", "kind": "narrative"},
    {"id": 411, "file": "snr_crd_70", "func": "card_70_main", "kind": "narrative"},
    {"id": 420, "file": "snr_z_10_f", "func": "scene_zf_complete", "kind": "narrative"},
]
S2C_GRANT = {"z_10": 60, "z_20": 70}


def _grant_timeline():
    """手写 timeline（不经 Expander，保持 check() 模块 docstring 所说的"独立于展开器
    重放验证"）：卡 70 的 req=[201,202,203] 分别来自 subcall（201）/ crd60 自身
    gets（202）/ crd60.runs 触发的 _f 章 fscene gets（203）。"""
    return [
        {"type": "unit", "unit_kind": "scene", "src": "snr_z_10_s", "state": "z_10",
         "title": "甲", "ids": [400, 401]},
        {"type": "unit", "unit_kind": "card", "src": "snr_crd_60", "state": "z_10",
         "title": "甲", "ids": [410]},
        {"type": "unit", "unit_kind": "fscene", "src": "snr_z_10_f", "state": None,
         "title": "snr_z_10_f", "ids": [420]},
        {"type": "unit", "unit_kind": "scene", "src": "snr_z_10_s", "state": "z_20",
         "title": "乙", "ids": [402]},
        {"type": "unit", "unit_kind": "card", "src": "snr_crd_70", "state": "z_20",
         "title": "乙", "ids": [411]},
    ]


def test_check_accepts_req_satisfied_by_crd_and_fscene_and_subcall_grants():
    errs = check(_grant_timeline(), LEDGER_GRANT, DAG_GRANT, S2C_GRANT, gates=[])
    assert errs == []


# Hotfix C3: check() 的 held 推导须补第 1 路"由 ids 反查"——check() 拿不到
# unit_funcs，无法像展开器那样知道哪个孤儿函数附挂到了哪个状态；但该孤儿函数的
# id 已经在 unit["ids"] 里（gen_timeline 的 Hotfix C1 保证），反查 id→func→
# scene_meta.gets 即可拿到它的发卡，且不需要 unit_funcs 这个参数。
DAG_C3 = {"states": {
    "w_10": {"file": "snr_w_10_s", "scene": "scene_w_10", "title": "甲",
             "seq": [{"play": "scene_w_10", "title": "甲"}, {"goto": "w_20"}]},
    "w_20": {"file": "snr_w_10_s", "scene": "scene_w_20", "title": "乙",
             "seq": [{"play": "scene_w_20", "title": "乙"}, {"goto": "end"}]},
}, "scene_meta": {
    "scene_w_10": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
    # scene_w_dispatch_v9 不出现在 w_10 的 seq 里（模拟 unit_funcs 附挂进来的孤儿
    # 函数）；check() 的 item2（扫 dag["states"][state]["seq"]）看不到它，唯一能
    # 发现它 gets=[141] 的路径是 item1（由 unit["ids"] 反查 id_func）。
    "scene_w_dispatch_v9": {"gets": [141], "cost": [], "shows": [], "gameover": False, "complete": False},
    "scene_w_20": {"gets": [], "cost": [], "shows": [], "gameover": False, "complete": False},
}, "crds": {
    "80": {"stub": False, "req": [141], "answers": [], "runs": []},
}}
LEDGER_C3 = [
    {"id": 700, "file": "snr_w_10_s", "func": "scene_w_10", "kind": "narrative"},
    {"id": 701, "file": "snr_w_10_s", "func": "scene_w_dispatch_v9", "kind": "narrative"},
    {"id": 702, "file": "snr_w_10_s", "func": "scene_w_20", "kind": "narrative"},
    {"id": 710, "file": "snr_crd_80", "func": "card_80_main", "kind": "narrative"},
]
S2C_C3 = {"w_20": 80}


def _c3_timeline():
    """手写 timeline（不经 Expander，保持 check() 模块 docstring 所说的"独立于
    展开器重放验证"）：w_10 的 unit["ids"] 里含 701——它属于 scene_w_dispatch_v9，
    一个不在 dag["states"]["w_10"]["seq"] 里出现的孤儿函数（模拟 gen_timeline
    经 unit_funcs 附挂后的真实产物）。卡 80 的 req=[141] 只能靠这一路满足。"""
    return [
        {"type": "unit", "unit_kind": "scene", "src": "snr_w_10_s", "state": "w_10",
         "title": "甲", "ids": [700, 701]},
        {"type": "unit", "unit_kind": "scene", "src": "snr_w_10_s", "state": "w_20",
         "title": "乙", "ids": [702]},
        {"type": "unit", "unit_kind": "card", "src": "snr_crd_80", "state": "w_20",
         "title": "乙", "ids": [710]},
    ]


def test_check_accepts_req_satisfied_by_unit_funcs_attached_orphan_via_id_lookup():
    """去掉 _grant 里"由 ids 反查"那一路（C3 第 1 路），此测试必红：item2 扫
    w_10 的 seq 只看到 scene_w_10（gets=[]），看不到 scene_w_dispatch_v9，held
    永远缺 141，card unit w_20 的 req 检查报错。"""
    errs = check(_c3_timeline(), LEDGER_C3, DAG_C3, S2C_C3, gates=[])
    assert errs == []
