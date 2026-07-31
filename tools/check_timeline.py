"""timeline 三组断言：覆盖 / crd 合法 / 门控表。独立于展开器重放验证。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, REPO, read_jsonl


def _grant(held, unit, dag, scene2card, file_funcs, id_func):
    """对单个 timeline unit 施加它带来的发卡，原地更新 held。
    check() 的签名里没有 unit_funcs，无法照抄展开器（gen_timeline.Expander）的
    内部口径；改用一条只依赖入参、且不严于展开器（不会误报）的推导——对每个
    unit 取以下四路发卡的并集，B 段（按 timeline 顺序累积）与 C 段（重扫
    timeline[:pos]）共用这一份实现，避免两边口径漂移：
    1. 由 ids 反查：unit["ids"] 每个 id 对应的 func（id_func）的 scene_meta.gets——
       这一路自动覆盖 unit_funcs 附挂进来的孤儿函数（它们的 id 已经在这个 unit
       里，如 scene_s7f_dispatch_v52 挂在 s7f-50 状态的 unit 上）；
    2. scene unit：dag["states"][state]["seq"] 里 play 与 subcall 两类事件的
       scene_meta.gets；
    3. card unit：scene2card[state] 那张卡本身，外加 crds[cid]["gets"]（crd 自身
       附带发出的别的卡，见 build_dag 的 parse_crds）；
    4. fscene / script unit：该文件（unit["src"]）在 ledger_rows 里出现过的全部
       函数的 scene_meta.gets（_f 章现实层/无状态脚本被整文件经历，章梗概卡
       133-145 由其 *_complete 场景授予）。
    file_funcs：file→{func,…} 反查表；id_func：id→func 反查表；两者均由调用方从
    ledger_rows 建一次。"""
    kind = unit.get("unit_kind")
    state = unit.get("state")
    for i in unit.get("ids", []):
        fn = id_func.get(i)
        if fn:
            held.update(dag["scene_meta"].get(fn, {}).get("gets", []))
    if kind == "scene":
        for ev in dag["states"].get(state or "", {}).get("seq", []):
            if "play" in ev:
                held.update(dag["scene_meta"].get(ev["play"], {}).get("gets", []))
            elif "subcall" in ev:
                held.update(dag["scene_meta"].get(ev["subcall"], {}).get("gets", []))
    elif kind == "card":
        cid = scene2card.get(state)
        held.add(cid)
        held.update(dag["crds"].get(str(cid), {}).get("gets", []))
    elif kind in ("fscene", "script"):
        for fn in file_funcs.get(unit.get("src"), ()):
            held.update(dag["scene_meta"].get(fn, {}).get("gets", []))


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

    file_funcs = {}
    for r in ledger_rows:
        if r.get("kind") == "narrative":
            file_funcs.setdefault(r["file"], set()).add(r["func"])
    id_func = {r["id"]: r["func"] for r in ledger_rows}

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
        _grant(held, u, dag, scene2card, file_funcs, id_func)
    for g in gates:
        pos = first_pos.get(g["unit_state"])
        if pos is None:
            # 门控状态从未作为 unit 出现（如状态本身无 play/subcall，dag 里不产生
            # unit）：静默跳过会让这条门控恒过，形同虚设（Task 5 评审 Finding 2）；
            # 显式报错，让作者把门控改锚到真的会出现的状态。
            errs.append(f"门控: {g['unit_state']} 从未作为 unit 出现（门控落空）")
            continue
        held2 = set()
        for u in timeline[:pos]:
            if u.get("type") == "unit":
                _grant(held2, u, dag, scene2card, file_funcs, id_func)
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
