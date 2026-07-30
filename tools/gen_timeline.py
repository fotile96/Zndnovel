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
