#!/usr/bin/env python3
"""Extract the scene-dispatch DAG from snr_*_10_*.lua main() dispatchers.

Usage:
    python3 tools/extract_dag.py [lua files...] > analysis/dag_all.txt

With no arguments, processes all section scripts (snr_s*_10_*.lua / snr_e*_10_*.lua).
Output per scene node: played scene function + title, next-scene transitions,
choice branches (select image => return value), route/card conditions,
cross-file RUN jumps, ayanoTime costs, GAMEOVER/COMPLETE flags, and cards
granted on scene end (GET_CARD).
"""
import re, sys, os, glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(REPO, "lua_scripts")

def extract_main(text):
    # main function is the last 'main = function()' block
    idx = text.rfind("\nmain = function()")
    return text[idx:] if idx >= 0 else ""

def analyze(path):
    name = os.path.basename(path)
    text = open(path, encoding="utf-8").read()
    main = extract_main(text)
    lines = main.splitlines()
    out = []
    def emit(s):
        out.append(s)
    for ln in lines:
        s = ln.strip()
        m = re.match(r'(?:else)?if doScriptScene == "([^"]+)"', s)
        if m:
            emit(f"[{m.group(1)}]")
            continue
        m = re.search(r'scene_([A-Za-z0-9_]+)\(doScriptScene, "([^"]*)"', s)
        if m:
            emit(f"    play scene_{m.group(1)} 「{m.group(2)}」")
            continue
        m = re.search(r'doScriptScene = "([^"]+)"', s)
        if m:
            emit(f"    -> {m.group(1)}")
            continue
        m = re.search(r'run\(cGetFileName\("scriptc?", ?"([^"]+)"\)\)', s)
        if m:
            emit(f"    RUN {m.group(1)}")
            continue
        m = re.search(r'comSectionStoryCheckRoute\("([^"]+)"\)', s)
        if m:
            emit(f"    ?routeHas({m.group(1)})")
            continue
        m = re.search(r'gameSave\.myCard\[(\d+)\]\.hold == (-?1)', s)
        if m:
            emit(f"    ?card{m.group(1)}.hold=={m.group(2)}")
            continue
        m = re.search(r'gameSave\.myCard\[sceneId2aCard\.([A-Za-z0-9_]+)\]\.hold == -1', s)
        if m:
            emit(f"    ?noCardOf({m.group(1)})")
            continue
        m = re.search(r'comDlgSelectItem\((.*)\)', s)
        if m:
            sels = re.findall(r'"(sel_[A-Za-z0-9_]+)", \d+, \d+, (\d+)', m.group(1))
            if sels:
                emit(f"    CHOICE {' '.join(f'{a}=>{b}' for a,b in sels)}")
            continue
        m = re.search(r'(?:else)?if (v\d+) == (\d+) then', s)
        if m:
            emit(f"    on {m.group(1)}=={m.group(2)}:")
            continue
        m = re.search(r'comSelectMap\([^,]+, "([A-Z]+)", (\d+), [^,]*, (.*)\)', s)
        if m:
            spots = re.findall(r'"([a-zA-Z]+)", \d+, \d+, (\d+)', m.group(3))
            emit(f"    MAP({m.group(1)}) {' '.join(f'{a}=>{b}' for a,b in spots)}")
            continue
        m = re.search(r'comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, gameSave\.sceneName, (\d+)\)', s)
        if m:
            emit(f"    END(cost={m.group(1)})")
            continue
        m = re.search(r'scene_([A-Za-z0-9_]+)\(\)', s)
        if m:
            emit(f"    call scene_{m.group(1)}()")
            continue
        m = re.search(r'comSectionGameOver|comSectionComplete', s)
        if m:
            emit(f"    {m.group(0)}")
            continue
    return name, out

def scene_costs(path):
    """Extract per-scene metadata from scene function bodies."""
    text = open(path, encoding="utf-8").read()
    res = {}
    parts = re.split(r'\n(scene_[A-Za-z0-9_]+) = function', text)
    for i in range(1, len(parts), 2):
        fname = parts[i]
        body = parts[i+1]
        costs = re.findall(r'comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, gameSave\.sceneName, (\d+)\)', body)
        gover = 'comSectionGameOver' in body
        comp = 'comSectionComplete' in body
        cards_in = re.findall(r"comSectionCardFlagIn\((\d+)", body)
        gets = re.findall(r"gameSave\.myCard\[(\d+)\]\.hold = 1", body)
        tag = ""
        if costs: tag += f" cost={','.join(costs)}"
        if gover: tag += " GAMEOVER"
        if comp: tag += " COMPLETE"
        if cards_in: tag += f" showsCard={','.join(sorted(set(cards_in)))}"
        if gets: tag += f" GET_CARD={','.join(gets)}"
        if tag:
            res[fname] = tag
    return res

if __name__ == "__main__":
    files = sys.argv[1:] or sorted(glob.glob(f"{SCRIPT_DIR}/snr_s*_10_*.lua") + glob.glob(f"{SCRIPT_DIR}/snr_e*_10_*.lua"))
    for f in files:
        name, out = analyze(f)
        costs = scene_costs(f)
        print(f"\n================ {name} ================")
        for line in out:
            m = re.match(r'    play (scene_[A-Za-z0-9_]+)', line)
            if m and m.group(1) in costs:
                line += "  //" + costs[m.group(1)]
            print(line)
