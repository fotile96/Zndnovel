"""route_plan DSL → data/timeline.jsonl 展开器。"""
import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, DATA, read_jsonl, write_jsonl


class Expander:
    def __init__(self, dag, ledger_rows, unit_funcs, scene2card=None):
        self.dag = dag
        self.unit_funcs = unit_funcs or {}
        self.scene2card = scene2card or {}
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
        跳过其后紧随的一个 goto；伴随的 run 事件不驱动行走、无需门控
        （enter 跳转由 goto 承载；引擎先赋 doScriptScene 再 run；nxt 已指向目标脚本 enter 状态）。
        choice 事件：pick 命中的 {choice,goto} 提供 nxt，其余忽略。"""
        choices = choices or {}
        state = enter
        while state and state != "end":
            st = self.dag["states"].get(state)
            if st is None:
                raise KeyError(f"未知状态 {state}")
            funcs, title = [], st["title"]
            nxt, skip = None, False
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
                    pass  # 跨文件切换由伴随 goto 承载（引擎先赋 doScriptScene 再 run；nxt 已指向目标脚本 enter 状态）
            if funcs:
                self.emit_unit("scene", st["file"], state, title, funcs)
                self.emitted_states.add(state)
                self.route.append(state)
                for f in funcs:
                    self._apply_meta(f)
            if until and state == until:
                return
            state = nxt

    def _makeable(self, state):
        """检查该状态对应的卡片是否可以做：
        - 卡片必须在 scene2card 中有映射
        - 卡片未持有
        - 卡片的前置卡都已持有
        - 若非 _sel 场景，其路线前缀上所有非 _sel 场景都已持卡"""
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
        """按 route 前缀序找可做的卡片，逐张 emit card unit 并持有，
        然后发出 runs 中的 _f 章脚本作 fscene unit。"""
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
        """emit 回溯标记，然后沿状态图重讲，已 emit 过的状态折叠（不发 unit，只推进状态与 route）。"""
        self.emit_marker(f"【讲述指针回溯至 {at}，本次选 {pick}】",
                         recap=f"重讲：上一轮在 {at} 走了默认分支。")
        before = set(self.emitted_states)
        saved_emit = self.emit_unit
        def dedup_emit(kind, src, state, title, funcs):
            if state in before:
                return
            saved_emit(kind, src, state, title, funcs)
        self.emit_unit = dedup_emit
        try:
            self.story(at, {at: pick}, until)
        finally:
            self.emit_unit = saved_emit

    def script(self, file_stem):
        """整文件 narrative ids 为一个 unit，用于无状态脚本（如 snr_crd_0）。"""
        funcs = sorted({fn for (f, fn) in self.by_filefunc if f == file_stem})
        self.emit_unit("script", file_stem, None,
                       file_stem, funcs)

    def pool(self, file_func):
        """该函数全部 narrative ids 为一个 unit，用于 comSectionMapmoveAyanoIn 等函数级别复用。"""
        f, fn = file_func.split(":")
        self.emit_unit("pool", f, None, file_func, [fn])
