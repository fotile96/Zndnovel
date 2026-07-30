### Task 4: check_timeline 校验器

**Files:**
- Create: `tools/check_timeline.py`
- Test: `tests/test_check_timeline.py`
- Create: `config/gates.yaml`

**Interfaces:**
- Produces: `check_timeline.check(timeline, ledger_rows, dag, scene2card, gates) -> list[str]`（错误串列表，空=通过）；CLI `uv run python tools/check_timeline.py` 读 data/ 与 config/ 运行三组断言：
  - A 覆盖：narrative id 恰好出现一次；ambient id 零次；无未知 id
  - B crd 合法：每个 card unit 出现时 req⊆此前 held、且路线前缀规则满足（复用 Expander._makeable 的判定逻辑，独立重放）
  - C 门控表：`config/gates.yaml` 每条 `{unit_state: X, requires_cards: […]}`——X 首次出现前这些卡必须已获得

`config/gates.yaml` 初始内容（依 CLAUDE.md 章节门控，Task 5 编路线时可增补）：

```yaml
- {unit_state: s2s_10,  requires_cards: [133]}   # 进入 s2 前需 Section1 梗概
- {unit_state: s3s_10,  requires_cards: [134]}
- {unit_state: s5s_20,  requires_cards: [177]}   # 日记章入口
- {unit_state: s7f-10,  requires_cards: [140]}   # 主菜单 Section7
- {unit_state: s8s_10,  requires_cards: [141]}
- {unit_state: e1s_10,  requires_cards: [142]}
- {unit_state: e2s_10,  requires_cards: [143]}
- {unit_state: s3fc-10, requires_cards: [136]}   # 强制段：持 136 未持 145
```

- [ ] **Step 1: Write the failing test**

创建 `tests/test_check_timeline.py`（复用 test_gen_timeline 的 DAG2/LEDGER2/S2C）：

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_check_timeline.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/check_timeline.py`：

```python
"""timeline 三组断言：覆盖 / crd 合法 / 门控表。独立于展开器重放验证。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, REPO, read_jsonl


def check(timeline, ledger_rows, dag, scene2card, gates):
    errs = []
    narrative = {r["id"] for r in ledger_rows if r["kind"] == "narrative"}
    ambient = {r["id"] for r in ledger_rows if r["kind"] == "ambient"}
    seen = Counter()
    for u in timeline:
        if u["type"] != "unit":
            continue
        seen.update(u["ids"])
    dup = [i for i, c in seen.items() if c > 1]
    missing = sorted(narrative - set(seen))
    stray = sorted((set(seen) - narrative) & ambient)
    unknown = sorted(set(seen) - narrative - ambient)
    if dup: errs.append(f"重复 id: {sorted(dup)[:10]}…共{len(dup)}")
    if missing: errs.append(f"缺失 narrative id: {missing[:10]}…共{len(missing)}")
    if stray: errs.append(f"ambient 混入: {stray[:10]}")
    if unknown: errs.append(f"未知 id: {unknown[:10]}")

    held, route = set(), []
    first_pos = {}
    for pos, u in enumerate(timeline):
        if u["type"] != "unit":
            continue
        st = u.get("state")
        if st and st not in first_pos:
            first_pos[st] = pos
        if u["unit_kind"] == "scene":
            route.append(st)
            for f in ("scene_meta",):
                pass
            for ev in dag["states"].get(st, {}).get("seq", []):
                if "play" in ev:
                    held.update(dag["scene_meta"].get(ev["play"], {}).get("gets", []))
        elif u["unit_kind"] == "card":
            cid = scene2card.get(st)
            crd = dag["crds"].get(str(cid), {})
            if not set(crd.get("req", [])) <= held:
                errs.append(f"card unit {st}: req {crd.get('req')} 未满足（held 缺 "
                            f"{sorted(set(crd.get('req', [])) - held)}）")
            if not (st or "").endswith("_sel"):
                for prev in route:
                    if prev == st:
                        break
                    if prev.endswith("_sel"):
                        continue
                    pc = scene2card.get(prev)
                    if pc is not None and pc not in held:
                        errs.append(f"card unit {st}: 前缀 {prev}（卡{pc}）未先做卡")
                        break
            held.add(cid)
    for g in gates:
        pos = first_pos.get(g["unit_state"])
        if pos is None:
            continue
        held2 = set()
        for u in timeline[:pos]:
            if u.get("type") == "unit":
                if u.get("unit_kind") == "card":
                    held2.add(scene2card.get(u.get("state")))
                for ev in dag["states"].get(u.get("state") or "", {}).get("seq", []):
                    if "play" in ev:
                        held2.update(dag["scene_meta"].get(ev["play"], {}).get("gets", []))
        lack = [c for c in g["requires_cards"] if c not in held2]
        if lack:
            errs.append(f"门控: {g['unit_state']} 出现前缺卡 {lack}")
    return errs


def main():
    import yaml
    timeline = read_jsonl(DATA / "timeline.jsonl")
    ledger = read_jsonl(DATA / "ledger.jsonl")
    dag = json.loads((DATA / "dag.json").read_text(encoding="utf-8"))
    s2c = json.loads((DATA / "scene2card.json").read_text(encoding="utf-8"))
    gates = yaml.safe_load(open(REPO / "config" / "gates.yaml", encoding="utf-8")) or []
    errs = check(timeline, ledger, dag, s2c, gates)
    print("\n".join(errs) if errs else "OK")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_check_timeline.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tools/check_timeline.py tests/test_check_timeline.py config/gates.yaml
git commit -m "feat: check_timeline 覆盖/crd/门控三组断言"
```

---

