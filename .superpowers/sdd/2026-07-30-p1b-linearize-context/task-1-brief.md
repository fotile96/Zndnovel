### Task 1: dag.json 生成器

**Files:**
- Create: `tools/build_dag.py`
- Test: `tests/test_build_dag.py`
- Create(运行产物): `data/dag.json`

**Interfaces:**
- Produces: `build_dag.parse_states(stem,text)->dict`、`build_dag.parse_scene_meta(stem,text)->dict`、CLI 写 `data/dag.json`：
  - `states[<sceneId>] = {"file":stem,"scene":"scene_x"|null,"title":str|null,"seq":[事件…]}`，事件为 `{"play":func,"title":str}` / `{"goto":sceneId}` / `{"choice":N,"goto":sceneId}` / `{"route_has":sceneId}` / `{"card_gate":int,"held":bool}` / `{"run":script}` / `{"subcall":func}` / `{"end_cost":int}` / `{"flag":"GAMEOVER"|"COMPLETE"}`（按 dispatcher 行序保留）
  - `scene_meta[func] = {"cost":[int,…],"gets":[int,…],"shows":[int,…],"gameover":bool,"complete":bool}`
  - `crds[str(cid)] = {"stub":bool,"req":[int,…],"answers":[int,…],"runs":[str,…]}`

- [ ] **Step 1: Write the failing test**

创建 `tests/test_build_dag.py`：

```python
from tools.build_dag import parse_states, parse_scene_meta

FIX = '''\
scene_x_20 = function(scene_id, scene_title)
    local v0
    v0 = function()
        gameSave.myCard[128].hold = 1
        comSectionStoryEnd(gameSave.sceneId, gameSave.sceneName, 25)
    end
end
main = function()
    while v48 == 0 do
        if doScriptScene == "end" then
            v48 = 1
        elseif doScriptScene == "x_20" then
            scene_x_20(doScriptScene, "夏の朝")
            doScriptScene = "x_30"
        elseif doScriptScene == "x_30_sel" then
            if gameSave.myCard[133].hold == 1 then
                doScriptScene = "y_10"
                run(cGetFileName("script", "snr_y_10_s"))
            end
            v49 = comDlgSelectItem(false, true, false, true, 1, "none", 0, 0, "sel_a", 115, 140, 1)
            if v49 == 1 then
                doScriptScene = "x_40"
            elseif v49 == 2 then
                doScriptScene = "x_50"
            end
            scene_x_dispatch_v20()
        end
    end
end
'''

def test_states_capture_flow_in_order():
    st = parse_states("snr_x_10_s", FIX)
    ev = st["x_20"]["seq"]
    assert st["x_20"]["scene"] == "scene_x_20"
    assert st["x_20"]["title"] == "夏の朝"
    assert {"goto": "x_30"} in ev

def test_states_capture_gate_choice_run_subcall():
    st = parse_states("snr_x_10_s", FIX)
    ev = st["x_30_sel"]["seq"]
    assert {"card_gate": 133, "held": True} in ev
    assert {"run": "snr_y_10_s"} in ev
    assert {"choice": 1, "goto": "x_40"} in ev and {"choice": 2, "goto": "x_50"} in ev
    assert {"subcall": "scene_x_dispatch_v20"} in ev

def test_scene_meta_costs_and_gets():
    m = parse_scene_meta("snr_x_10_s", FIX)
    assert m["scene_x_20"]["cost"] == [25]
    assert m["scene_x_20"]["gets"] == [128]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_dag.py -v`
Expected: FAIL（ModuleNotFoundError: tools.build_dag）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/build_dag.py`（解析规则移植自 `tools/extract_dag.py`，输出结构化 JSON）：

```python
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
    parts = re.split(r'\n(scene_[\w]+) = function', text)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_dag.py -v`
Expected: 3 passed

- [ ] **Step 5: 真实数据生成并抽查**

```bash
uv run python tools/build_dag.py
uv run python - <<'EOF'
import json
dag = json.load(open("data/dag.json", encoding="utf-8"))
assert "s1s_20" in dag["states"] and dag["states"]["s1s_20"]["title"].startswith("夏の朝")
assert dag["crds"]["2"]["req"] == [1] and dag["crds"]["30"]["runs"] == ["snr_s1_10_f"]
assert {"card_gate": 133, "held": True} in dag["states"]["s1s_40"]["seq"]
print("spot OK")
EOF
uv run python tools/build_dag.py && git diff --stat data/dag.json  # 双跑确定性：第二次运行后 diff 必须为空
```

- [ ] **Step 6: Commit**

```bash
git add tools/build_dag.py tests/test_build_dag.py data/dag.json
git commit -m "feat: dag.json 结构化剧情图生成器"
```

---

