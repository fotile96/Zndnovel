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

# --- local-constant folding -------------------------------------------------
# The decompiler base materialises literals as single-use locals, e.g.
#     local l2_0 = 25
#     comSectionStoryEnd(gameSave.sceneId, gameSave.sceneName, l2_0)
#     local l1_1 = sceneId2aCard.s1s_35_sel
#     if gameSave.myCard[l1_1].hold == -1 then
# so every numeric/table-key operand has to be resolved through a tiny
# straight-line environment instead of being read off the call site.
LOCAL_NAME = r'(?:l\d+_\d+|u\d+|v\d+|p\d+|i\d+|g\d+)'
CONST_ASSIGN = re.compile(
    r'^(?:local\s+)?(' + LOCAL_NAME + r')\s*=\s*'
    r'(-?\d+|sceneId2aCard\.[A-Za-z0-9_]+)\s*(?:--.*)?$')
ANY_ASSIGN = re.compile(r'^(?:local\s+)?(' + LOCAL_NAME + r')\s*=[^=]')
FOR_BIND = re.compile(r'^for\s+(' + LOCAL_NAME + r')\b')

def track_const(env, s):
    """Update `env` from one source line (last write wins; non-const kills)."""
    m = CONST_ASSIGN.match(s)
    if m:
        env[m.group(1)] = m.group(2)
        return
    for pat in (ANY_ASSIGN, FOR_BIND):
        m = pat.match(s)
        if m:
            env.pop(m.group(1), None)
            return

def fold(env, tok, dynamic="dyn"):
    """Resolve an operand to its literal; `dynamic` if it is runtime-computed."""
    tok = tok.strip()
    if re.fullmatch(r'-?\d+', tok):
        return tok
    if tok in env:
        return env[tok]
    if re.fullmatch(LOCAL_NAME, tok):
        return dynamic
    return tok

def analyze(path):
    name = os.path.basename(path)
    text = open(path, encoding="utf-8").read()
    main = extract_main(text)
    lines = main.splitlines()
    out = []
    env = {}
    def emit(s):
        out.append(s)
    for ln in lines:
        s = ln.strip()
        track_const(env, s)
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
        m = re.search(r'gameSave\.myCard\[([A-Za-z0-9_.]+)\]\.hold == (-?1)', s)
        if m:
            raw = m.group(1)
            idx, want = fold(env, raw, dynamic=raw), m.group(2)
            if re.fullmatch(r'\d+', idx):
                emit(f"    ?card{idx}.hold=={want}")
                continue
            if idx.startswith("sceneId2aCard.") and want == "-1":
                emit(f"    ?noCardOf({idx.split('.', 1)[1]})")
                continue
            if idx.startswith("sceneId2aCard."):
                emit(f"    ?cardOf({idx.split('.', 1)[1]}).hold=={want}")
                continue
            # unresolved operand: surface it rather than silently dropping the edge
            emit(f"    ?card[{idx}].hold=={want}")
            continue
        m = re.search(r'comDlgSelectItem\((.*)\)', s)
        if m:
            sels = re.findall(r'"(sel_[A-Za-z0-9_]+)", \d+, \d+, (\d+)', m.group(1))
            if sels:
                emit(f"    CHOICE {' '.join(f'{a}=>{b}' for a,b in sels)}")
            continue
        m = re.search(r'(?:else)?if (' + LOCAL_NAME + r') == (\d+) then', s)
        if m:
            emit(f"    on {m.group(1)}=={m.group(2)}:")
            continue
        # 1st arg is cGetFileName("bg", "..."), which itself contains a comma —
        # a `[^,]+` first field never matched, so this rule was dead in every
        # base. Lazy-scan up to the speaker tag instead.
        m = re.search(r'comSelectMap\(.*?, "([A-Z]+)", (\d+), [^,]*, (.*)\)', s)
        if m:
            spots = re.findall(r'"([a-zA-Z]+)", \d+, \d+, (\d+)', m.group(3))
            emit(f"    MAP({m.group(1)}) {' '.join(f'{a}=>{b}' for a,b in spots)}")
            continue
        m = re.search(r'comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, gameSave\.sceneName, ([^)]+)\)', s)
        if m:
            emit(f"    END(cost={fold(env, m.group(1))})")
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
    # `^` + MULTILINE, not `\n...`: in the current base the first scene function
    # sits on line 1 (there is no leading declaration block any more), so a
    # newline-anchored split silently swallowed it.
    parts = re.split(r'^(?:local )?(scene_[A-Za-z0-9_]+) = function', text, flags=re.M)
    for i in range(1, len(parts), 2):
        fname = parts[i]
        body = parts[i+1]
        costs = []
        env = {}
        for ln in body.splitlines():
            s = ln.strip()
            track_const(env, s)
            m = re.search(r'comSectionStoryEnd(?:Force)?\('
                          r'gameSave\.sceneId, gameSave\.sceneName, ([^)]+)\)', s)
            if m:
                costs.append(fold(env, m.group(1)))
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
