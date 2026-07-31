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
