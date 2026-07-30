"""把章节剧本 dispatcher 与 crd 结构解析为 data/dag.json。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, DATA

STATE_RE = re.compile(r'(?:else)?if doScriptScene == "([^"]+)"')
PLAY_RE = re.compile(r'(scene_[\w]+)\((?:doScriptScene|p0), "([^"]*)"')
GOTO_RE = re.compile(r'doScriptScene = "([^"]+)"')
RUN_RE = re.compile(r'run\(cGetFileName\("scriptc?", ?"([^"]+)"\)\)')
ROUTE_RE = re.compile(r'comSectionStoryCheckRoute\("([^"]+)"\)')
GATE_RE = re.compile(r'gameSave\.myCard\[(\d+)\]\.hold == (-?1)')
CHOICE_RE = re.compile(r'(?:else)?if (v\d+) == (\d+) then')
SUBCALL_RE = re.compile(r'(scene_[\w]+)\(\)')
COST_RE = re.compile(r'comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, gameSave\.sceneName, (\d+)\)')
GET_RE = re.compile(r'gameSave\.myCard\[(\d+)\]\.hold = 1')
SHOW_RE = re.compile(r'comSectionCardFlagIn\((\d+)')


def parse_states(stem: str, text: str) -> dict:
    idx = text.rfind("\nmain = function()")
    main = text[idx:] if idx >= 0 else ""
    states, cur, pend_choice = {}, None, None
    for line in main.splitlines():
        s = line.strip()
        if m := STATE_RE.match(s):
            cur = m.group(1)
            states[cur] = {"file": stem, "scene": None, "title": None, "seq": []}
            pend_choice = None
            continue
        if cur is None:
            continue
        ev = states[cur]["seq"]
        if m := PLAY_RE.search(s):
            if states[cur]["scene"] is None:
                states[cur]["scene"], states[cur]["title"] = m.group(1), m.group(2)
            ev.append({"play": m.group(1), "title": m.group(2)})
        elif m := GOTO_RE.search(s):
            if pend_choice is not None:
                ev.append({"choice": pend_choice, "goto": m.group(1)})
            else:
                ev.append({"goto": m.group(1)})
        elif m := RUN_RE.search(s):
            ev.append({"run": m.group(1)})
        elif m := ROUTE_RE.search(s):
            ev.append({"route_has": m.group(1)})
        elif m := GATE_RE.search(s):
            ev.append({"card_gate": int(m.group(1)), "held": m.group(2) == "1"})
        elif m := CHOICE_RE.match(s):
            pend_choice = int(m.group(2))
        elif m := SUBCALL_RE.search(s):
            if not s.startswith("scene_") or "(doScriptScene" not in s:
                ev.append({"subcall": m.group(1)})
        elif m := COST_RE.search(s):
            ev.append({"end_cost": int(m.group(1))})
        elif "comSectionGameOver" in s:
            ev.append({"flag": "GAMEOVER"})
        elif "comSectionComplete" in s:
            ev.append({"flag": "COMPLETE"})
    return states


def parse_scene_meta(stem: str, text: str) -> dict:
    res = {}
    parts = re.split(r'\n(scene_[\w]+) = function', '\n' + text)
    for i in range(1, len(parts), 2):
        body = parts[i + 1]
        res[parts[i]] = {
            "cost": [int(x) for x in COST_RE.findall(body)],
            "gets": [int(x) for x in GET_RE.findall(body)],
            "shows": sorted({int(x) for x in SHOW_RE.findall(body)}),
            "gameover": "comSectionGameOver" in body,
            "complete": "comSectionComplete" in body,
        }
    return res


def parse_crds(script_dir) -> dict:
    crds = {}
    for p in sorted(script_dir.glob("snr_crd_*.lua")):
        n = int(re.search(r"snr_crd_(\d+)", p.stem).group(1))
        t = p.read_text(encoding="utf-8")
        crds[str(n)] = {
            "stub": t.count("vms(") <= 2 and t.count("\n") < 15,
            "req": sorted({int(x) for x in re.findall(r'myCard\[(\d+)\]\.hold == -1', t)}),
            "answers": sorted({int(x) for x in re.findall(r'if v\d+ == (\d+) then', t)} - {0, 1}),
            "runs": sorted(set(RUN_RE.findall(t)) - {"snr_fragment_main", "snr_mainmenu"}),
        }
    return crds


def main():
    script_dir = REPO / "lua_scripts"
    states, meta = {}, {}
    for p in sorted(script_dir.glob("snr_s*_10_*.lua")) + sorted(script_dir.glob("snr_e*_10_*.lua")):
        t = p.read_text(encoding="utf-8")
        states.update(parse_states(p.stem, t))
        meta.update(parse_scene_meta(p.stem, t))
    dag = {"states": states, "scene_meta": meta, "crds": parse_crds(script_dir)}
    (DATA / "dag.json").write_text(
        json.dumps(dag, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"states={len(states)} scene_meta={len(meta)} crds={len(dag['crds'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
