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

