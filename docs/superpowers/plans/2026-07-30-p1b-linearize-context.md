# P1b 线性化与上下文组装 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成从 DAG 到可翻译批次的完整链路：dag.json（结构化剧情图）→ route_plan（正典路线 DSL）→ timeline.jsonl（体验序）→ batches.jsonl（三车道批次）→ build_context（三 profile×四 baseline 上下文包）→ prompts/gen_plan/add_patch。

**Architecture:** 「聪明的数据 + 笨的代码」：正典游玩顺序写成人工可审的 `config/route_plan.yaml`（DSL），代码只做机械展开（expander）与机械验证（check_timeline 的覆盖/门控断言）。所有工具沿用 P1a 的 pipelib/append-only 纪律。

**Tech Stack:** Python 3.14（uv），pyyaml（已装）；测试 pytest。零新增依赖。

## Global Constraints

- 运行 `uv run python tools/<x>.py`、测试 `uv run pytest`；commit 规范 `type: 中文摘要`，main 直提交。
- `data/ledger.jsonl` 为原文权威（16750 行，schema 见 P1a 接口表；含 `literal` 标志与 kind narrative/ambient）。narrative 例外已审定：`snr_common:comSectionMapmoveAyanoIn`、`snr_common:comSectionStoryEndAyanoTime` 为 narrative（需上时间轴的"文本池"）。
- 生成类文件（dag.json/timeline.jsonl/batches.jsonl）可整体重建，重建必须字节级确定（双跑 diff）；重建后须重跑下游校验。
- `skeleton/`（tag skeleton-v1 目标物）与 `glossary/`（当前 v4）只读引用；本计划不修改它们。
- 术语表/风格只出现在 context 的**尾部活动层**（spec §2.3）。
- baseline 只注入尾部：冻结前缀与 `--baseline none` 逐字节相同（spec §5.0）。

## 接口总表（消费 P1a / 产出给 P2）

消费（P1a 已落地，签名勿改）：
- `pipelib`: `REPO/DATA/WORK: Path`；`dumps(obj)->str`；`read_jsonl(p)->list[dict]`；`append_jsonl/write_jsonl(p,rows)`；`sha256_file(p)->str`；`display_width(s)->int`
- ledger 行：`{"id","jp","voice","file","func","chapter","kind","literal"}`
- `resolve.resolve_map(forward_rows, patch_rows) -> dict[int,str]`
- 入库握手：`work/ctx/batch_<N>/source.jsonl` + `work/out/batch_<N>.draft.jsonl` → `check_batch --batch N` → pass 标记 → `append_forward`

产出（P2 试点消费）：
- `data/dag.json`：`{"states": {…}, "scene_meta": {…}, "crds": {…}}`（Task 1）
- `config/route_plan.yaml` + `config/unit_funcs.yaml` + `config/gates.yaml`（Task 5，人工路线资产）
- `data/timeline.jsonl`：事件行 `{"seq":int,"type":"unit"|"marker",…}`（unit: `{"unit_kind":"scene|card|fscene|script|pool","src":"file:func","state":str|null,"title":str,"ids":[int,…]}`；marker: `{"text":str,"recap":str}`）
- `data/batches.jsonl`：`{"batch":int,"lane":"main|ambient|extra","ids":[…],"seqs":[…],"jp_chars":int,"chapter":str,"cut_reason":str}`
- `build_context.py --batch N --profile {api-A|api-B|cc} --baseline {none|ref|revise|judge}` → `work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`
- `prompts/{translator_cc,reviewer_cc,api_system}.md`；`gen_plan.py --lane main --chapter <ch>`；`add_patch.py`；`recall.py`

---

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

### Task 2: 时间轴展开器——story 步进核心

**Files:**
- Create: `tools/gen_timeline.py`
- Test: `tests/test_gen_timeline.py`
- Create: `config/unit_funcs.yaml`（先放空表）

**Interfaces:**
- Produces: `gen_timeline.Expander(dag, ledger_rows, unit_funcs)`：
  - `ex.story(enter: str, choices: dict[str,int], until: str|None) -> None`（沿 states 走默认/指定路径，逐场景 emit unit；直到 until 状态**播完**、或 GAMEOVER/COMPLETE/RUN/end）
  - `ex.emit_unit(kind, src, state, title, funcs: list[str])`（ids = ledger 中 file:func 匹配行，按 id 升序；funcs 含主 scene 函数+subcalls+unit_funcs 附挂）
  - `ex.timeline: list[dict]`；`ex.held: set[int]`（GET_CARD 生效）；`ex.route: list[str]`
  - 规则：`card_gate` 按 `held` 真值走对应分支；`route_has` 按 `ex.route`；`choice` 用 `choices.get(state, 最小可用编号)`；`run` 记为跨文件跳转（状态机切到目标脚本的 enter 状态并继续）

- [ ] **Step 1: Write the failing test**

创建 `tests/test_gen_timeline.py`（构造 4 状态迷你 dag + 迷你 ledger）：

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gen_timeline.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/gen_timeline.py`（本任务只需 Expander 核心与 story/emit）：

```python
"""route_plan DSL → data/timeline.jsonl 展开器。"""
import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, DATA, read_jsonl, write_jsonl


class Expander:
    def __init__(self, dag, ledger_rows, unit_funcs):
        self.dag = dag
        self.unit_funcs = unit_funcs or {}
        self.by_filefunc = {}
        for r in ledger_rows:
            if r.get("kind") == "narrative":
                self.by_filefunc.setdefault((r["file"], r["func"]), []).append(r["id"])
        self.timeline, self.held, self.route = [], set(), []
        self.emitted_states = set()

    def _ids_for(self, file, funcs):
        ids = []
        extra = self.unit_funcs.get(file, {})
        pats = list(funcs) + [p for p, tgt in extra.items() if tgt in funcs or tgt == "*"]
        for (f, fn), v in self.by_filefunc.items():
            if f == file and any(fnmatch.fnmatch(fn, p) for p in pats):
                ids += v
        return sorted(set(ids))

    def emit_unit(self, kind, src_file, state, title, funcs):
        self.timeline.append({
            "type": "unit", "unit_kind": kind, "src": src_file,
            "state": state, "title": title,
            "ids": self._ids_for(src_file, funcs),
        })

    def emit_marker(self, text, recap=""):
        self.timeline.append({"type": "marker", "text": text, "recap": recap})

    def _apply_meta(self, func):
        m = self.dag["scene_meta"].get(func, {})
        self.held.update(m.get("gets", []))

    def story(self, enter, choices=None, until=None):
        """沿状态图行进。skip 语义契约：card_gate/route_has 判假时，
        跳过其后**紧随的一个** goto（含伴随 run）；判真则正常吸收。
        choice 事件：pick 命中的 {choice,goto} 提供 nxt，其余忽略。"""
        choices = choices or {}
        state = enter
        while state and state != "end":
            st = self.dag["states"].get(state)
            if st is None:
                raise KeyError(f"未知状态 {state}")
            funcs, title = [], st["title"]
            nxt, ran, skip = None, None, False
            for ev in st["seq"]:
                if "play" in ev:
                    funcs.append(ev["play"]); title = title or ev["title"]
                elif "subcall" in ev:
                    funcs.append(ev["subcall"])
                elif "card_gate" in ev:
                    skip = ((ev["card_gate"] in self.held) != ev["held"])
                elif "route_has" in ev:
                    skip = (ev["route_has"] not in self.route)
                elif "choice" in ev:
                    pick = choices.setdefault(state, ev["choice"])  # 首个选项即默认
                    if ev["choice"] == pick and nxt is None:
                        nxt = ev["goto"]
                elif "goto" in ev:
                    if skip:
                        skip = False
                        continue
                    if nxt is None:
                        nxt = ev["goto"]
                elif "run" in ev:
                    if not skip:
                        ran = ev["run"]
            if funcs:
                self.emit_unit("scene", st["file"], state, title, funcs)
                self.emitted_states.add(state)
                self.route.append(state)
                for f in funcs:
                    self._apply_meta(f)
            if until and state == until:
                return
            state = nxt        # ran 时 nxt 已指向目标脚本的 enter 状态，跨文件直接续走
```

（skip 契约以真实 dispatcher 的行序为准——`card_gate→goto→run` 与 `route_has→goto真→goto假` 两种版式已覆盖；若 Task 5 全书验证暴露新版式，先在本测试文件加最小用例再改实现。）

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gen_timeline.py -v`
Expected: 3 passed

- [ ] **Step 5: 真实 s1 冒烟**

```bash
uv run python - <<'EOF'
import json, sys; sys.path.insert(0, ".")
from tools.pipelib import read_jsonl
from tools.gen_timeline import Expander
dag = json.load(open("data/dag.json", encoding="utf-8"))
ex = Expander(dag, read_jsonl("data/ledger.jsonl"), {})
ex.story("s1s_10", choices={}, until="s1s_20")
units = [u for u in ex.timeline if u["type"] == "unit"]
assert [u["state"] for u in units] == ["s1s_10", "s1s_20"], units
assert all(u["ids"] for u in units), "s1s_10/20 都应有 vms 行"
print("smoke OK:", [(u["state"], len(u["ids"])) for u in units])
EOF
```

- [ ] **Step 6: Commit**

```bash
git add tools/gen_timeline.py tests/test_gen_timeline.py config/unit_funcs.yaml
git commit -m "feat: 时间轴展开器 story 步进核心"
```

---

### Task 3: 展开器——fragment_sweep / replay / script / pool 与回溯标记

**Files:**
- Modify: `tools/gen_timeline.py`
- Test: `tests/test_gen_timeline.py`（追加）

**Interfaces:**
- Produces（Expander 新方法，供 route_plan 移动指令调用）：
  - `ex.fragment_sweep(only: list[int]|None)`：按 `ex.route` 前缀序找「未持卡、前缀非 `_sel` 场景全部已持卡、req⊆held」的场景卡，逐张 emit `card` unit（file=snr_crd_<cid>，funcs=`["*"]` 全文件）并 `held.add(cid)`；crd 的 `runs` 里的 `_f` 章脚本紧随以 `script` unit 整文件 emit（unit_kind="fscene"）
  - `ex.replay(at: str, pick: int, until: str|None)`：emit marker『【讲述指针回溯至 {at}，本次选 {pick}】』+ recap，然后 `story(at, {at: pick}, until)`（已 emit 过的状态**不再**发 unit，只推进状态与 route——重讲折叠）
  - `ex.script(file_stem: str)`：整文件 narrative ids 为一个 unit（unit_kind="script"，用于 snr_crd_0 等无状态脚本）
  - `ex.pool(file_func: "file:func")`：该函数全部 narrative ids 为一个 unit（unit_kind="pool"，用于 comSectionMapmoveAyanoIn / comSectionStoryEndAyanoTime）

- [ ] **Step 1: Write the failing test**

在 `tests/test_gen_timeline.py` 追加（扩充迷你 dag：加 crd 与 `_sel` 状态）：

```python
DAG2 = {"states": {
    "b_10": {"file": "snr_b_10_s", "scene": "scene_b_10", "title": "一",
             "seq": [{"play": "scene_b_10", "title": "一"}, {"goto": "b_20_sel"}]},
    "b_20_sel": {"file": "snr_b_10_s", "scene": "scene_b_20_sel", "title": "选",
             "seq": [{"play": "scene_b_20_sel", "title": "选"},
                     {"choice": 1, "goto": "b_30"}, {"choice": 2, "goto": "b_40"}]},
    "b_30": {"file": "snr_b_10_s", "scene": "scene_b_30", "title": "甲",
             "seq": [{"play": "scene_b_30", "title": "甲"}, {"goto": "end"}]},
    "b_40": {"file": "snr_b_10_s", "scene": "scene_b_40", "title": "乙",
             "seq": [{"play": "scene_b_40", "title": "乙"}, {"goto": "end"}]},
}, "scene_meta": {}, "crds": {
    "11": {"stub": False, "req": [], "answers": [], "runs": []},
    "12": {"stub": False, "req": [11], "answers": [11], "runs": ["snr_b_10_f"]},
}}
LEDGER2 = [
    {"id": 10, "file": "snr_b_10_s", "func": "scene_b_10", "kind": "narrative"},
    {"id": 20, "file": "snr_b_10_s", "func": "scene_b_20_sel", "kind": "narrative"},
    {"id": 30, "file": "snr_b_10_s", "func": "scene_b_30", "kind": "narrative"},
    {"id": 40, "file": "snr_b_10_s", "func": "scene_b_40", "kind": "narrative"},
    {"id": 51, "file": "snr_crd_11", "func": "card_11_main", "kind": "narrative"},
    {"id": 52, "file": "snr_crd_12", "func": "card_12_main", "kind": "narrative"},
    {"id": 60, "file": "snr_b_10_f", "func": "scene_bf_10", "kind": "narrative"},
    {"id": 70, "file": "snr_common", "func": "poolFn", "kind": "narrative"},
]
S2C = {"b_10": 11, "b_20_sel": 12}   # sceneId→卡号映射作为 Expander 构造参数传入

def test_fragment_sweep_emits_cards_then_fchapter():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.story("b_10", {}, until=None)
    ex.fragment_sweep()
    kinds = [(u["unit_kind"], u.get("state"), u["ids"]) for u in ex.timeline if u["type"] == "unit"]
    assert ("card", "b_10", [51]) in kinds
    assert ("card", "b_20_sel", [52]) in kinds
    assert ("fscene", None, [60]) in kinds          # crd_12 的 runs 紧随
    assert {11, 12} <= ex.held

def test_replay_emits_marker_and_only_new_units():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.story("b_10", {}, until=None)                # 默认走 b_30
    ex.replay(at="b_20_sel", pick=2, until=None)
    types = [(e["type"], e.get("state")) for e in ex.timeline]
    assert ("marker", None) in types
    states = [u["state"] for u in ex.timeline if u["type"] == "unit"]
    assert states.count("b_20_sel") == 1 and "b_40" in states   # 折叠重讲

def test_script_and_pool_units():
    ex = Expander(DAG2, LEDGER2, {}, scene2card=S2C)
    ex.script("snr_crd_11")
    ex.pool("snr_common:poolFn")
    kinds = [(u["unit_kind"], u["ids"]) for u in ex.timeline]
    assert ("script", [51]) in kinds and ("pool", [70]) in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gen_timeline.py -v`
Expected: 新增 3 条 FAIL（TypeError: scene2card / AttributeError）

- [ ] **Step 3: Write minimal implementation**

在 `tools/gen_timeline.py` 的 Expander 中追加（构造参数 `scene2card: dict[str,int]`，真实数据由 Task 5 从 `snr_common.lua` 的 `sceneId2aCard` 表解析注入）：

```python
    # __init__ 追加参数与保存：
    #   def __init__(self, dag, ledger_rows, unit_funcs, scene2card=None):
    #       …
    #       self.scene2card = scene2card or {}

    def script(self, file_stem):
        funcs = sorted({fn for (f, fn) in self.by_filefunc if f == file_stem})
        self.emit_unit("script", file_stem, None,
                       file_stem, funcs)

    def pool(self, file_func):
        f, fn = file_func.split(":")
        self.emit_unit("pool", f, None, file_func, [fn])

    def _makeable(self, state):
        cid = self.scene2card.get(state)
        if cid is None or cid in self.held:
            return False
        crd = self.dag["crds"].get(str(cid), {})
        if not set(crd.get("req", [])) <= self.held:
            return False
        if state.endswith("_sel"):
            return True
        for prev in self.route:
            if prev == state:
                break
            if prev.endswith("_sel"):
                continue
            pc = self.scene2card.get(prev)
            if pc is not None and pc not in self.held:
                return False
        return True

    def fragment_sweep(self, only=None):
        for state in list(self.route):
            cid = self.scene2card.get(state)
            if cid is None or (only and cid not in only):
                continue
            if not self._makeable(state):
                continue
            stem = f"snr_crd_{cid}"
            funcs = sorted({fn for (f, fn) in self.by_filefunc if f == stem})
            self.emit_unit("card", stem, state,
                           self.dag["states"].get(state, {}).get("title"), funcs)
            self.held.add(cid)
            for runf in self.dag["crds"].get(str(cid), {}).get("runs", []):
                fs = sorted({fn for (f, fn) in self.by_filefunc if f == runf})
                self.emit_unit("fscene", runf, None, runf, fs)

    def replay(self, at, pick, until=None):
        self.emit_marker(f"【讲述指针回溯至 {at}，本次选 {pick}】",
                         recap=f"重讲：上一轮在 {at} 走了默认分支。")
        before = set(self.emitted_states)
        saved_emit = self.emit_unit
        def dedup_emit(kind, src, state, title, funcs):
            if state in before:
                self.route.append(state)
                return
            saved_emit(kind, src, state, title, funcs)
        self.emit_unit = dedup_emit
        try:
            self.story(at, {at: pick}, until)
        finally:
            self.emit_unit = saved_emit
```

（`fragment_sweep` 的 `runs` 只对 `_f` 章脚本出现——crd 表中 runs 已剔除 fragment_main/mainmenu。）

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gen_timeline.py -v`
Expected: 全部 passed

- [ ] **Step 5: Commit**

```bash
git add tools/gen_timeline.py tests/test_gen_timeline.py
git commit -m "feat: 展开器 sweep/replay/script/pool 与回溯标记"
```

---

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

### Task 5: 全书路线编写与 timeline 入库（内容任务，主会话执行）

**Files:**
- Create: `config/route_plan.yaml`（全书正典路线，人工资产）
- Modify: `config/unit_funcs.yaml`（孤儿函数附挂表，验证循环中增补）
- Modify: `tools/gen_timeline.py`（追加 `main()`：解析 route_plan 逐移动执行 + 从 snr_common 解析 sceneId2aCard 写 `data/scene2card.json`）
- Create(运行产物): `data/scene2card.json`、`data/timeline.jsonl`

**route_plan DSL（main() 按序执行的移动指令）：**

```yaml
- story:          {enter: s1s_10, until: s1s_20}          # 首讲撞墙（cost100 设计节奏）
- pool:           {func: "snr_common:comSectionStoryEndAyanoTime"}   # Time over 演出首次播出
- script:         {file: snr_crd_0}                        # 教程做卡剧情
- fragment_sweep: {only: [2]}                              # 制成卡2 → OP
- story:          {enter: s1s_30, choices: {}, until: s1s_140}       # 首过默认路线段
- story:          {enter: s1s_150, choices: {}, until: s1s_200_sel}  # 探索场景
- pool:           {func: "snr_common:comSectionMapmoveAyanoIn"}      # 首个探索场景后放置
- story:          {enter: s1s_210, choices: {}, until: s1s_260_sel}
- fragment_sweep: {}
- replay:         {at: s1s_35_sel, pick: 2, until: s1s_70}
# ……后续各章依「设计通关序≈最早解锁贪心」同构推进至 EX2；备忘：
#   GAMEOVER 短支线用 replay 进出；s3fc 强制段用 story: {enter: s3fc-10}；
#   Section7 用 story: {enter: s7f-10}；s5 日记章入口在 crd_177 sweep 之后。
```

**Step 概要（内容工作循环，不逐 checkbox 展开代码）：**

- [ ] **Step 1**：在 gen_timeline.py 补 `main()`：读 route_plan/unit_funcs/dag/ledger；解析 `snr_common.lua` 的 `sceneId2aCard.<scene> = N` 行生成 scene2card.json（跳过 `keyword` 重复键）；逐移动执行；写 timeline.jsonl（含 seq 编号）。双跑 diff 断言确定性。
- [ ] **Step 2**：主会话（具备全剧情知识）按 `analysis/dag_all.txt` + CLAUDE.md 章节流逐章编写 route_plan.yaml；每写一章跑一次 `gen_timeline && check_timeline`，按报错（缺失 id / 孤儿函数 / 门控缺卡）迭代：孤儿函数（如 `snr_s1_10_s:v0` 教程通知、`scene_s1s_dispatch_v*` 探索小节）通过 unit_funcs.yaml 附挂到属主单元。
- [ ] **Step 3**：全书绿灯后产出摘要（章序、unit 数、marker 数、每章 id 数）呈用户抽查 **CHECKPOINT（需用户）**。
- [ ] **Step 4**：提交：

```bash
uv run python tools/gen_timeline.py && uv run python tools/check_timeline.py
git add config/ data/scene2card.json data/timeline.jsonl tools/gen_timeline.py
git commit -m "data: 全书正典路线与 timeline 入库（check_timeline 全绿）"
```

---

### Task 6: gen_batches 三车道

**Files:**
- Create: `tools/gen_batches.py`
- Test: `tests/test_gen_batches.py`

**Interfaces:**
- Produces: `gen_batches.plan(timeline, ledger_rows, extra_rows, budget_chars=9000) -> list[dict]`（batches 行 schema 见接口总表；lane 顺序：main 全部→每章 extra→ambient）；CLI 写 `data/batches.jsonl` 并打印统计。切批规则：预算超限（cut_reason=budget）、遇 marker（cut_reason=branch）、unit 换章（cut_reason=chapter）。ambient 车道按 `(file,func)` 分组贪心装批；extra 车道读 `data/ledger_extra.jsonl` 按 file 章别成批。**注意：main/ambient 车道 ids 为 int（vms id），extra 车道 ids 为 str（ledger_extra 的 key）——下游按 lane 区分处理。**

- [ ] **Step 1: Write the failing test**

```python
from tools.gen_batches import plan

TL = [
    {"type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_10",
     "title": "一", "ids": [1, 2]},
    {"type": "marker", "text": "【回溯】", "recap": ""},
    {"type": "unit", "unit_kind": "scene", "src": "snr_a_10_s", "state": "a_30",
     "title": "三", "ids": [3]},
    {"type": "unit", "unit_kind": "scene", "src": "snr_b_10_s", "state": "b_10",
     "title": "换章", "ids": [4]},
]
LED = [
    {"id": 1, "jp": "あ" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    {"id": 2, "jp": "い" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f1"},
    {"id": 3, "jp": "う" * 30, "chapter": "a", "kind": "narrative", "file": "snr_a_10_s", "func": "f2"},
    {"id": 4, "jp": "え" * 30, "chapter": "b", "kind": "narrative", "file": "snr_b_10_s", "func": "f3"},
    {"id": 9, "jp": "お" * 10, "chapter": "sys", "kind": "ambient", "file": "snr_common", "func": "u1"},
]
EXTRA = [{"key": "snr_a_10_s:5", "jp": "题", "kind": "scene_title", "file": "snr_a_10_s"}]

def test_marker_and_chapter_cut():
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    main = [r for r in rows if r["lane"] == "main"]
    assert [r["ids"] for r in main] == [[1, 2], [3], [4]]
    assert main[0]["cut_reason"] == "branch" and main[1]["cut_reason"] == "chapter"

def test_budget_cut_and_lanes():
    rows = plan(TL, LED, EXTRA, budget_chars=40)
    main = [r for r in rows if r["lane"] == "main"]
    assert [r["ids"] for r in main][:2] == [[1], [2]]      # 30字/行，40 预算下逐行成批
    assert any(r["lane"] == "ambient" and r["ids"] == [9] for r in rows)
    assert any(r["lane"] == "extra" for r in rows)

def test_batch_numbering_is_global_and_stable():
    rows = plan(TL, LED, EXTRA, budget_chars=10**6)
    assert [r["batch"] for r in rows] == list(range(1, len(rows) + 1))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gen_batches.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

```python
"""timeline+ledger → data/batches.jsonl（main/extra/ambient 三车道）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl, write_jsonl


def plan(timeline, ledger_rows, extra_rows, budget_chars=9000):
    led = {r["id"]: r for r in ledger_rows}
    rows, cur_ids, cur_chars, cur_ch = [], [], 0, None

    def flush(reason):
        nonlocal cur_ids, cur_chars
        if cur_ids:
            rows.append({"lane": "main", "ids": cur_ids, "jp_chars": cur_chars,
                         "chapter": cur_ch, "cut_reason": reason})
            cur_ids, cur_chars = [], 0

    for ev in timeline:
        if ev["type"] == "marker":
            flush("branch")
            continue
        ch = led[ev["ids"][0]]["chapter"] if ev["ids"] else cur_ch
        if cur_ch is not None and ch != cur_ch:
            flush("chapter")
        cur_ch = ch
        for i in ev["ids"]:
            n = len(led[i]["jp"])
            if cur_ids and cur_chars + n > budget_chars:
                flush("budget")
            cur_ids.append(i)
            cur_chars += n
    flush("tail")

    by_file = {}
    for r in extra_rows:
        by_file.setdefault(r["file"], []).append(r["key"])
    for f in sorted(by_file):
        rows.append({"lane": "extra", "ids": by_file[f], "jp_chars": 0,
                     "chapter": f, "cut_reason": "extra"})

    amb, chars = [], 0
    for r in ledger_rows:
        if r["kind"] != "ambient":
            continue
        n = len(r["jp"])
        if amb and chars + n > budget_chars:
            rows.append({"lane": "ambient", "ids": amb, "jp_chars": chars,
                         "chapter": "sys", "cut_reason": "budget"})
            amb, chars = [], 0
        amb.append(r["id"]); chars += n
    if amb:
        rows.append({"lane": "ambient", "ids": amb, "jp_chars": chars,
                     "chapter": "sys", "cut_reason": "tail"})

    for n, r in enumerate(rows, 1):
        r["batch"] = n
    return rows


def main():
    tl = read_jsonl(DATA / "timeline.jsonl")
    led = read_jsonl(DATA / "ledger.jsonl")
    extra = read_jsonl(DATA / "ledger_extra.jsonl")
    rows = plan(tl, led, extra)
    write_jsonl(DATA / "batches.jsonl", rows)
    lanes = {}
    for r in rows:
        lanes[r["lane"]] = lanes.get(r["lane"], 0) + 1
    print("batches:", len(rows), lanes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes** → `uv run pytest tests/test_gen_batches.py -v`
- [ ] **Step 5: 真实数据生成、人工过目批次表后提交（spec：开翻前冻结）**

```bash
uv run python tools/gen_batches.py && uv run python - <<'EOF'
from tools.pipelib import DATA, read_jsonl
rows = read_jsonl(DATA / "batches.jsonl")
ids = [i for r in rows for i in r["ids"] if isinstance(i, int)]
assert len(ids) == len(set(ids)), "批次间 id 重复"
print("main 批均字数:", sum(r["jp_chars"] for r in rows if r["lane"]=="main") //
      max(1, sum(1 for r in rows if r["lane"]=="main")))
EOF
git add tools/gen_batches.py tests/test_gen_batches.py data/batches.jsonl
git commit -m "data: 批次规划三车道生成并冻结"
```

---

### Task 7: build_context（三 profile × 四 baseline）

**Files:**
- Create: `tools/build_context.py`
- Test: `tests/test_build_context.py`

**Interfaces:**
- Produces: CLI `uv run python tools/build_context.py --batch N --profile {api-A|api-B|cc} --baseline {none|ref|revise|judge} [--jp-fallback]` → `work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`
  - `source.jsonl` 行：`{"id":int,"jp":str}`＋baseline≠none 时 `"base":str`（resolve() 生效译文）
  - `manifest.json`：`{"batch","profile","baseline","glossary_v","skeleton":"cards.zh.yaml sha256","anchors":"sha256|absent","ctx_sha":"context.md sha256"}`
  - 前缀构成：api-A=骨架+全部已译 timeline 前缀（zh）；api-B 与 cc=骨架+已完结章的章梗概卡（cards.zh 卡133-145 对应章）+当前章已译 zh；**baseline 只进尾部**——`--baseline none` 与其他档的 context.md 至「## 五、本批任务」之前逐字节相同（测试断言此不变量）
  - 前缀取 zh：`resolve.resolve_map`；prefix 内未译行默认报错退出 2，`--jp-fallback` 时以 `〔未译|jp〕` 行代替
- Consumes: `skeleton/cards.zh.yaml`、`skeleton/anchors.yaml`（若存在）、`glossary/active.json`、`glossary/style.md`、data/ 各件

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path
from tools.build_context import build

def _env(tmp_path):
    d = tmp_path
    (d / "data").mkdir(); (d / "glossary").mkdir(); (d / "skeleton").mkdir()
    (d / "skeleton" / "cards.zh.yaml").write_text(
        "- {card: 1, variant: a, title_zh: 测试卡, body_zh: 骨架正文, tr_note: ''}\n",
        encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{"あ":"啊"}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    rows = [
        {"id": 1, "jp": "第一句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
        {"id": 2, "jp": "第二句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
    ]
    (d / "data" / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (d / "data" / "timeline.jsonl").write_text(json.dumps(
        {"type": "unit", "unit_kind": "scene", "src": "f", "state": "a_10",
         "title": "一", "ids": [1, 2]}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [1, 2], "jp_chars": 6,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "已译一", "batch": 0, "backend": "cc", "model": "m",
                    "ctx": "c", "glossary_v": 4, "ts": "t"}, ensure_ascii=False),
        encoding="utf-8")
    return d

def test_ctx_files_and_manifest(tmp_path):
    d = _env(tmp_path)
    build(batch=1, profile="cc", baseline="none", repo=d)
    ctx = d / "work" / "ctx" / "batch_1"
    assert (ctx / "context.md").exists() and (ctx / "manifest.json").exists()
    src = [json.loads(l) for l in (ctx / "source.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in src] == [1, 2] and "base" not in src[0]

def test_baseline_only_touches_tail(tmp_path):
    d = _env(tmp_path)
    build(batch=1, profile="cc", baseline="none", repo=d)
    a = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    build(batch=1, profile="cc", baseline="revise", repo=d)
    b = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    cut = "## 五、本批任务"
    assert a.split(cut)[0] == b.split(cut)[0]
    src = [json.loads(l) for l in (d / "work/ctx/batch_1/source.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert src[0]["base"] == "已译一"

def test_untranslated_prefix_requires_fallback(tmp_path):
    d = _env(tmp_path)
    # 批次 2：把行 2 当作后续批，行 1 未译时前缀应报错
    (d / "data" / "forward.jsonl").write_text("", encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text("\n".join([
        json.dumps({"batch": 1, "lane": "main", "ids": [1], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "budget"}, ensure_ascii=False),
        json.dumps({"batch": 2, "lane": "main", "ids": [2], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False)]),
        encoding="utf-8")
    assert build(batch=2, profile="api-A", baseline="none", repo=d) == 2
    assert build(batch=2, profile="api-A", baseline="none", repo=d, jp_fallback=True) == 0
```

- [ ] **Step 2: Run test to verify it fails** → `uv run pytest tests/test_build_context.py -v`（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

`tools/build_context.py`（骨干；渲染顺序即 context.md 章节顺序）：

```python
"""批次上下文组装：context.md / source.jsonl / manifest.json。"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO as _REPO, dumps, read_jsonl, sha256_file
from tools.resolve import resolve_map

SECTION5 = "## 五、本批任务"
SYN_CARDS = {"s1": 133, "s2": 134, "s3a": 135, "s3b": 136, "s4a": 137, "s4b": 138,
             "s5": 139, "s6": 140, "s7": 141, "s8": 142, "e1": 143, "e2": 144}


def _load(repo):
    data = repo / "data"
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    return {
        "ledger": {r["id"]: r for r in read_jsonl(data / "ledger.jsonl")},
        "timeline": read_jsonl(data / "timeline.jsonl"),
        "batches": {r["batch"]: r for r in read_jsonl(data / "batches.jsonl")},
        "zh": resolve_map(fwd, pat),
        "cards": yaml.safe_load(open(repo / "skeleton" / "cards.zh.yaml", encoding="utf-8")),
        "active": json.loads((repo / "glossary" / "active.json").read_text(encoding="utf-8")),
        "style": (repo / "glossary" / "style.md").read_text(encoding="utf-8"),
    }


def _render_skeleton(cards):
    out = ["# 一、冻结骨架（中文卡组）"]
    for c in cards:
        out.append(f"【卡{c['card']}】{c['title_zh']}：{c.get('body_zh','').replace(chr(10),'')}")
    return "\n".join(out)


def _render_prefix(env, batch_no, profile, jp_fallback):
    led, zh = env["ledger"], env["zh"]
    prior_ids = [i for b, r in sorted(env["batches"].items())
                 if r["lane"] == "main" and b < batch_no for i in r["ids"]]
    cur_ch = env["batches"][batch_no]["chapter"]
    out, missing = ["\n## 二、前缀正文"], 0
    for i in prior_ids:
        ch = led[i]["chapter"]
        if profile in ("api-B", "cc") and ch != cur_ch:
            continue                       # 已完结章走章梗概（骨架卡已含），细文省略
        if i in zh:
            out.append(zh[i])
        elif jp_fallback:
            out.append(f"〔未译|{led[i]['jp']}〕"); missing += 1
        else:
            return None, i
    return "\n".join(out), None


def build(batch, profile, baseline, repo=None, jp_fallback=False):
    repo = Path(repo or _REPO)
    env = _load(repo)
    b = env["batches"][batch]
    prefix, blocked = _render_prefix(env, batch, profile, jp_fallback)
    if prefix is None:
        print(f"前缀行 {blocked} 未译（--jp-fallback 可放行）", file=sys.stderr)
        return 2
    anchors_p = repo / "skeleton" / "anchors.yaml"
    anchors = ("\n## 三、锚点行（日中对照）\n" +
               anchors_p.read_text(encoding="utf-8")) if anchors_p.exists() else \
              "\n## 三、锚点行（暂缺）"
    tail = ["\n## 四、术语与风格", json.dumps(env["active"], ensure_ascii=False),
            env["style"], f"\n{SECTION5}（baseline={baseline}）"]
    src_rows = []
    for i in b["ids"]:
        if isinstance(i, int):
            row = {"id": i, "jp": env["ledger"][i]["jp"]}
            if baseline != "none" and i in env["zh"]:
                row["base"] = env["zh"][i]
            src_rows.append(row)
            tail.append(f"[{i}] {row['jp']}" +
                        (f"\n    base: {row.get('base','')}" if baseline != "none" else ""))
    ctx_dir = repo / "work" / "ctx" / f"batch_{batch}"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    (ctx_dir / "context.md").write_text(
        "\n".join([f"# 批次 {batch}（profile={profile}）",
                   _render_skeleton(env["cards"]), prefix, anchors, *tail]),
        encoding="utf-8")
    (ctx_dir / "source.jsonl").write_text(
        "\n".join(dumps(r) for r in src_rows) + "\n", encoding="utf-8")
    import re as _re
    gv = max(int(_re.search(r"v(\d+)", p.stem).group(1))
             for p in (repo / "glossary").glob("glossary.v*.yaml"))
    manifest = {"batch": batch, "profile": profile, "baseline": baseline,
                "glossary_v": gv,
                "skeleton": sha256_file(repo / "skeleton" / "cards.zh.yaml"),
                "anchors": sha256_file(anchors_p) if anchors_p.exists() else "absent",
                "ctx_sha": sha256_file(ctx_dir / "context.md")}
    (ctx_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--profile", choices=["api-A", "api-B", "cc"], required=True)
    ap.add_argument("--baseline", choices=["none", "ref", "revise", "judge"], default="none")
    ap.add_argument("--jp-fallback", action="store_true")
    a = ap.parse_args(argv)
    return build(a.batch, a.profile, a.baseline, jp_fallback=a.jp_fallback)


if __name__ == "__main__":
    raise SystemExit(main())
```

（测试环境 tmp_path 下无 glossary.v*.yaml 时 `max()` 会抛错——测试夹具需写入一个 `glossary.v1.yaml` 空壳，或 build() 中对空 glob 回退 `gv=0`；实现取后者更稳。）

- [ ] **Step 4: Run test to verify it passes** → `uv run pytest tests/test_build_context.py -v`
- [ ] **Step 5: Commit** → `git add tools/build_context.py tests/test_build_context.py && git commit -m "feat: build_context 三 profile×四 baseline 组装"`

---

### Task 8: prompts 三件（真实全文入库）

**Files:**
- Create: `prompts/translator_cc.md`、`prompts/reviewer_cc.md`、`prompts/api_system.md`

**Step 概要：**

- [ ] **Step 1**：`translator_cc.md` 全文（要点必须含：译者人设=本作骨架译者；先读 work/ctx/batch_N 三件；全知纪律引用 style.md；控制码硬规则（`_n/_r` 总量差≤2、ruby、【】按 speakers.json、≪≫≦≧○■ 保留）；输出 `work/out/batch_N.draft.jsonl` 行 `{"id","zh"}` 且 id 集合=source；**允许用工具**：rg forward.jsonl 查既有译法、查 analysis/text_digest 语境、看该场景 CG/立绘图；返回前自跑 `check_batch --batch N` 到 PASS；禁止 git commit；术语提案写入 `data/notes/<chapter>.md` 尾部）。
- [ ] **Step 2**：`reviewer_cc.md` 全文（对照 source jp 逐行挑刺：术语漂移/剧透措辞/控制码/口调表偏离；输出 verdict 列表 `{"id","verdict":"keep|fix","zh":…,"reason":…}` 到 `work/out/batch_N.review.jsonl`；不改 draft 本体）。
- [ ] **Step 3**：`api_system.md` 全文（api 后端 system 指令：revise 档按 keep/fix 输出、none 档全量输出；JSON lines 格式契约；控制码规则同上）。
- [ ] **Step 4**：`git add prompts/ && git commit -m "feat: 翻译/评审/API 三份 prompt 模板"`

（三份模板的完整文案由执行者按上述要点撰写并在 PR 描述里贴出给用户过目——模板是 P2 试点的调参对象，首版不追求完美。）

---

### Task 9: gen_plan（CC 后端批次计划生成器）

**Files:**
- Create: `tools/gen_plan.py`
- Test: `tests/test_gen_plan.py`

**Interfaces:**
- Produces: CLI `uv run python tools/gen_plan.py --lane main --chapter s1s [--checkpoint-every 5]` → `docs/superpowers/plans/translate-<chapter>.md`；函数 `gen_plan.render(batches, chapter, lane, every) -> str`。每批一个任务（build_context cc/revise? 试点期 baseline=none → 参数化 `--baseline`）：①build_context ②按 prompts/translator_cc.md 派翻译子代理 ③check_batch ④append_forward+commit `data: <ch> 批次N 译文入线`；每 every 批插检查点任务（术语提案裁决+抽查）；章末任务=梗概回译自检+人工评审 gate。

- [ ] **Step 1: Write the failing test**

```python
from tools.gen_plan import render

BATCHES = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
            "chapter": "s1s", "cut_reason": "budget"} for i in range(1, 8)]

def test_render_contains_tasks_and_checkpoints():
    md = render(BATCHES, chapter="s1s", lane="main", every=3)
    assert md.count("### Task") >= 7 + 2          # 7 批任务+至少 2 检查点
    assert "build_context.py --batch 1" in md
    assert "check_batch.py --batch 1" in md
    assert "append_forward.py --batch 1" in md
    assert "梗概回译自检" in md and "CHECKPOINT" in md

def test_only_selected_chapter_and_lane():
    extra = BATCHES + [{"batch": 99, "lane": "ambient", "ids": [99], "jp_chars": 1,
                        "chapter": "sys", "cut_reason": "tail"}]
    md = render(extra, chapter="s1s", lane="main", every=5)
    assert "--batch 99" not in md
```

- [ ] **Step 2: Run** → FAIL（ModuleNotFoundError）
- [ ] **Step 3: 实现**（纯字符串模板函数 + main() 读 batches.jsonl 过滤写文件；模板含 executing-plans 头注、每任务 4 步 checkbox、检查点任务文案）
- [ ] **Step 4: Run** → 2 passed
- [ ] **Step 5: Commit** → `git commit -m "feat: gen_plan CC 批次计划生成器"`

---

### Task 10: add_patch 与 recall 召回查询

**Files:**
- Create: `tools/add_patch.py`、`tools/recall.py`
- Test: `tests/test_patch_recall.py`

**Interfaces:**
- `add_patch.py --id N --zh 文本 --reason review|recall|polish --glossary-v K [--data-dir]`：追加 patches.jsonl（append-only；schema 见 P1a 接口表；ts 可注入）
- `recall.py --glossary-v K --term 手帳 [--data-dir]`：列出 forward 中 `glossary_v < K` 且 ledger.jp 含 term 的行（id、旧译、章别），退出码 0；`--emit-batch` 时把命中行写 `work/recall/<term>.jsonl`（旁路小上下文批的输入）

- [ ] **Step 1: Write the failing test**

```python
import json
from tools.add_patch import add
from tools.recall import find
from tools.pipelib import write_jsonl, read_jsonl

def test_add_patch_appends(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    add(5, "新译", "review", 4, ts="t", data=d / "data")
    add(5, "更新译", "review", 4, ts="t2", data=d / "data")
    rows = read_jsonl(d / "data" / "patches.jsonl")
    assert [r["zh"] for r in rows] == ["新译", "更新译"]

def test_recall_finds_stale_rows(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"},
        {"id": 2, "jp": "無関係の行", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "看了她的手帐", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"},
        {"id": 2, "zh": "无关", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    hits = find(term="手帳", glossary_v=2, data=d / "data")
    assert [h["id"] for h in hits] == [1]
```

- [ ] **Step 2: Run** → FAIL；**Step 3: 实现**（两个 ~40 行脚本，签名如上）；**Step 4: Run** → passed
- [ ] **Step 5: Commit** → `git commit -m "feat: add_patch 与 recall 召回查询"`

---

### Task 11: 端到端 dry-run（无 API、无翻译）

**Files:**
- Create: `tests/test_e2e_dryrun.py`

- [ ] **Step 1: 写端到端测试**（真实 data/ 上运行，进默认测试套件；依赖 Task 5/6 产物已入库）：

```python
import json, subprocess, sys
from tools.pipelib import REPO, WORK, read_jsonl

def test_batch1_context_and_fake_roundtrip(tmp_path):
    r = subprocess.run([sys.executable, "tools/build_context.py",
                        "--batch", "1", "--profile", "cc", "--jp-fallback"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    src = read_jsonl(WORK / "ctx" / "batch_1" / "source.jsonl")
    draft = [{"id": row["id"], "zh": "【占位】" + row["jp"]} for row in src]
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "batch_1.draft.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in draft) + "\n",
        encoding="utf-8")
    r2 = subprocess.run([sys.executable, "tools/check_batch.py", "--batch", "1"],
                        cwd=REPO, capture_output=True, text=True)
    # 占位译文可能触发软警但硬规则应可通过（【】/符号照抄自 jp）
    assert r2.returncode == 0, r2.stdout + r2.stderr
```

- [ ] **Step 2: Run** → `uv run pytest tests/test_e2e_dryrun.py -v` 通过；随后 `uv run pytest -q` 全套回归全绿
- [ ] **Step 3: work/ 产物不入库（已在 .gitignore）；Commit** → `git commit -m "test: 端到端 dry-run（context→假草稿→check_batch）"`

---

## 完成定义

- `uv run pytest -q` 全绿（含 e2e）；`check_timeline` OK；batches.jsonl 冻结入库。
- `build_context --batch 1 --profile cc` 产出可读 context.md（人工抽查一次）。
- P2 试点（CC 翻第 1 章 + 基线对照）所需全部工件就绪；成本模拟器与 API 客户端属 P2，不在本计划。

## 风险与对策

- **展开器状态机边角**（skip 语义、嵌套选择迷宫 s2s_190_sel）：以 check_timeline 全书覆盖断言兜底；个别复杂状态允许在 route_plan 用显式 `script`/多段 `story` 绕行，宁可路线文件啰嗦不写聪明代码。
- **孤儿函数清单膨胀**：unit_funcs.yaml 每条附一句归属理由；Task 5 检查点让用户抽查。
- **timeline 返工**：dag.json/timeline/batches 全部可重建且字节确定，重建后必须重跑 check_timeline + gen_batches 并重新人工过目批次表（append-only 的 forward 不受影响，但批次边界变更仅允许发生在未开翻区段——已开翻批次的边界冻结，见 spec §5.0）。
