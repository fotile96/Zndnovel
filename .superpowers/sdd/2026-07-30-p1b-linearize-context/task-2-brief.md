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

