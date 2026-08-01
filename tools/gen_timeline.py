"""route_plan DSL → data/timeline.jsonl 展开器。"""
import fnmatch
import json
import re
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
        # pos：id → (file, line)，即该 vms 在 lua 源文件里的位置。单元内的 id 顺序
        # 必须按脚本行序，不能按消息号（F7）——后补的行消息号最大却排在中间，按 id
        # 排会把它甩到单元末尾：本口径下——按 timeline 单元分组、数「line 递减」的
        # 相邻对——全库 21/16248 处逆序（0.13%），例证 id 17181 在 snr_s1_10_s 第 234
        # 行。另有一个 47/16529（0.28%）的数指同一件事的另一口径（按 lua 文件分组、
        # 按 line 排数「id 递减」对），两者都对，见 build_ledger 的 line 字段注释。
        # line 由 build_ledger 记录；缺字段的旧数据/夹具退化为按 id 排。
        self.pos = {}
        for r in ledger_rows:
            if r.get("kind") == "narrative":
                self.by_filefunc.setdefault((r["file"], r["func"]), []).append(r["id"])
                self.pos[r["id"]] = (r["file"], r.get("line", 0))
        self.timeline, self.held, self.route = [], set(), []
        self.emitted_states = set()
        self._emitted_ids = set()

    def _matched_funcs(self, file, funcs):
        """该 unit 实际命中的全部真实函数名：nominal funcs 本身，加上
        config/unit_funcs.yaml 里附挂到其中任一 nominal func 的孤儿函数
        （dispatcher 内带参调用、PLAY_RE/SUBCALL_RE 抓不到的那批，如
        scene_s7f_dispatch_v52）。按 fnmatch 模式匹配 by_filefunc 的真实函数名——
        _ids_for（收 id）与 emit_unit（发 scene_meta 卡）共用这一份口径，避免
        fnmatch 逻辑抄两份。"""
        extra = self.unit_funcs.get(file, {})
        pats = list(funcs) + [p for p, tgt in extra.items() if tgt in funcs or tgt == "*"]
        return {fn for (f, fn) in self.by_filefunc
                if f == file and any(fnmatch.fnmatch(fn, p) for p in pats)}

    def _ids_for(self, file, funcs):
        """该 unit 的 id 列表，按 (file, line) 行序排（见 __init__ 的 pos 注释）；
        id 本身只作同位置的稳定 tie-break，也是 line 缺失时的退化序。"""
        ids = []
        for fn in self._matched_funcs(file, funcs):
            ids += self.by_filefunc.get((file, fn), [])
        return sorted(set(ids), key=lambda i: (*self.pos.get(i, ("", 0)), i))

    def emit_unit(self, kind, src_file, state, title, funcs):
        """emit 一个 unit：
        - 发卡：对该 unit 实际匹配到的全部 (file, func)（即 _matched_funcs，含
          unit_funcs 附挂的孤儿函数）逐个 _apply_meta，统一覆盖 story()/
          fragment_sweep() 原先两处各自遗漏 unit_funcs 附挂函数的特例；
        - 去重：ids 里已在此前任意 unit 出现过的全局滤掉再登记（同一条 vms 只能
          属于一个 unit）；unit 本身照常 emit，即便 ids 被滤空——它承载
          state/title/unit_kind，是叙事节拍，不能丢。"""
        matched = self._matched_funcs(src_file, funcs)
        ids = [i for i in self._ids_for(src_file, funcs) if i not in self._emitted_ids]
        self._emitted_ids.update(ids)
        self.timeline.append({
            "type": "unit", "unit_kind": kind, "src": src_file,
            "state": state, "title": title,
            "ids": ids,
        })
        for fn in matched:
            self._apply_meta(fn)

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
        然后发出 runs 中的 _f 章脚本作 fscene unit。
        crd 自身附带发出的别的卡（crds[cid]["gets"]，见 build_dag B1）在循环内、
        紧随该卡 emit 之后立即生效（好让同一次 sweep 里 route 序靠后的卡立刻能
        用上刚发的卡）——这不是 scene_meta，emit_unit 覆盖不到，须单独处理。
        runs 里 _f 章脚本（fscene unit）的 scene_meta.gets 改由 emit_unit 内部
        对其实际匹配到的全部函数统一施加（章梗概卡 133-145 由其 *_complete
        场景授予），此处不再重复申请。"""
        for state in list(self.route):
            cid = self.scene2card.get(state)
            if cid is None or (only and cid not in only):
                continue
            if not self._makeable(state):
                continue
            stem = f"snr_crd_{cid}"
            crd = self.dag["crds"].get(str(cid), {})
            funcs = sorted({fn for (f, fn) in self.by_filefunc if f == stem})
            self.emit_unit("card", stem, state,
                           self.dag["states"].get(state, {}).get("title"), funcs)
            self.held.add(cid)
            self.held.update(crd.get("gets", []))
            for runf in crd.get("runs", []):
                fs = sorted({fn for (f, fn) in self.by_filefunc if f == runf})
                self.emit_unit("fscene", runf, None, runf, fs)

    def replay(self, at, pick, until=None):
        """emit 讲述指针标记，然后沿状态图续讲，已 emit 过的状态折叠（不发 unit，只推进状态与
        route）。config/route_plan.yaml 把 replay 当通用的「在状态 X 续讲」原语用（编写规约
        第 1 条：每章首讲用 story，其后一律 replay）——at 未必讲过，marker 文案须按 at 此刻
        是否已经讲过、以及 at 在 dag 里是否真有 choice 事件分三种，字面陈述与实际讲述历史
        相符（Task 5 评审 Finding 1 + 修复轮 2）：
        - at 已讲过 且 at 的 seq 里有 choice 事件（真选择节点的真·重讲）：保留"回溯"语义，
          且可以声称"选第 N 项"——这是玩家在游戏里真实能做的选择；
        - at 已讲过 但 at 的 seq 里没有 choice 事件（只有线性 goto，或 card_gate/
          route_has 这类由引擎而非玩家解的条件分支）：同样是"回溯"，但不能编造"选了第 N
          项"——游戏脚本里根本没有对应的分支，pick 对这类状态没有玩家可见的选项语义；
        - at 未讲过（首次讲到）：发首访 marker，不用"回溯"/"上一轮"这类词——这一刻并不存在
          "上一轮"，pick 同样没有意义。
        at 若不在 dag["states"] 里，这里不抛异常（用 .get(at, {})），留给随后的 story()
        抛出更清楚的 KeyError。"""
        seq = self.dag["states"].get(at, {}).get("seq", [])
        has_choice = any("choice" in ev for ev in seq)
        if at in self.emitted_states and has_choice:
            self.emit_marker(f"【讲述指针回溯至 {at}，本次选第 {pick} 项】",
                             recap=f"重讲：指针回到 {at}，本次改选第 {pick} 项。")
        elif at in self.emitted_states:
            self.emit_marker(f"【讲述指针回溯至 {at}】",
                             recap=f"重讲：指针回到 {at}，从这里再讲一遍。")
        else:
            self.emit_marker(f"【讲述指针移至 {at}】",
                             recap=f"讲述从 {at} 继续。")
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


SCENE2CARD_RE = re.compile(r'^sceneId2aCard\.(\w+) = (-?\d+)')


def parse_scene2card(lua_text: str) -> dict:
    """从 snr_common.lua 文本中解析 sceneId2aCard.<scene> = N 行为场景→卡号映射。
    跳过 name == "keyword" 的行（反编译噪声，同一键被重复赋值覆盖，全文共 38 处，
    无场景语义）；真实条目（每个场景/选择场景各一张卡）应为 157 条。"""
    result = {}
    for line in lua_text.splitlines():
        m = SCENE2CARD_RE.match(line.strip())
        if not m:
            continue
        name = m.group(1)
        if name == "keyword":
            continue
        result[name] = int(m.group(2))
    return result


MOVE_KEYS = ("story", "pool", "script", "fragment_sweep", "replay")


def run_plan(ex, moves):
    """按 route_plan.yaml 顶层 list 的顺序执行移动。每项须为恰好一个键的 dict，
    键 ∈ MOVE_KEYS，值是该 Expander 方法的参数 dict。
    story/fragment_sweep/replay 的 DSL 参数名与方法形参一一对应，直接以 **kwargs 展开；
    pool/script 的 DSL 参数名（func/file）对应方法的单个位置参数（file_func/file_stem），
    在此显式换名。未知的移动键立即抛异常，异常信息指明是第几条移动（1-based，与
    route_plan.yaml 里从上到下数的条目序号一致，便于定位 typo）。"""
    for i, move in enumerate(moves, start=1):
        if not isinstance(move, dict) or len(move) != 1:
            raise ValueError(f"route_plan 第 {i} 条移动应为恰好一个键的 dict，得到 {move!r}")
        (kind, params), = move.items()
        params = params or {}
        if kind == "story":
            ex.story(**params)
        elif kind == "fragment_sweep":
            ex.fragment_sweep(**params)
        elif kind == "replay":
            ex.replay(**params)
        elif kind == "script":
            ex.script(params["file"])
        elif kind == "pool":
            ex.pool(params["func"])
        else:
            raise ValueError(f"route_plan 第 {i} 条移动使用未知键 {kind!r}，"
                              f"合法键：{MOVE_KEYS}")


def main():
    import yaml
    route_plan = yaml.safe_load((REPO / "config" / "route_plan.yaml").read_text(encoding="utf-8")) or []
    unit_funcs = yaml.safe_load((REPO / "config" / "unit_funcs.yaml").read_text(encoding="utf-8")) or {}
    dag = json.loads((DATA / "dag.json").read_text(encoding="utf-8"))
    ledger_rows = read_jsonl(DATA / "ledger.jsonl")

    lua_text = (REPO / "lua_scripts" / "snr_common.lua").read_text(encoding="utf-8")
    scene2card = parse_scene2card(lua_text)
    s2c_path = DATA / "scene2card.json"
    s2c_path.parent.mkdir(parents=True, exist_ok=True)
    s2c_path.write_text(
        json.dumps(scene2card, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")

    ex = Expander(dag, ledger_rows, unit_funcs, scene2card=scene2card)
    run_plan(ex, route_plan)

    timeline = [{"seq": i, **row} for i, row in enumerate(ex.timeline, start=1)]
    write_jsonl(DATA / "timeline.jsonl", timeline)

    n_unit = sum(1 for r in timeline if r["type"] == "unit")
    n_marker = sum(1 for r in timeline if r["type"] == "marker")
    covered = {i for r in timeline if r["type"] == "unit" for i in r["ids"]}
    print(f"scene2card={len(scene2card)} moves={len(route_plan)} "
          f"unit={n_unit} marker={n_marker} covered_ids={len(covered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
