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
