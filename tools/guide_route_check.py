#!/usr/bin/env python3
"""攻略路线可行性校验：按引擎规则重放 guide/chapters 里写的「故事模式 / 片段模式」交替。

抓的是 2026-09-19 玩家反馈的那一类错误——正文把几轮「讲 → 做卡 → 重讲」压成一轮，
或做卡顺序违反路线前缀要求，或要做的场景已经不在时间轴上。这些错 typst 断言与
check_hand_order 都抓不到，只能按引擎状态机模拟。

引擎规则（snr_common / snr_story_main / snr_fragment_main 逐条核对）：
- 故事模式在时间轴上选一点重讲：ayanoTime 回滚到**该点开讲前**的值，该点及其后的路线全部
  截断（cClearNumStoryRoute），然后从该场景重讲。
- 每个场景结束 comSectionStoryEnd(id, _, cost)：先把 (id, 当前 ayanoTime) 追加进 storyRoute，
  再在**未持该场景卡**时加 cost；≥100 立即 Time over 并终止脚本——选择场景的选项在场景
  结束之后才弹出，所以未持卡而耗时 100 的选择场景在第一次讲时根本选不了。
- 片段模式做非 _sel 场景卡：场景必须在当前路线上，且路线上它之前的全部非 _sel 场景都已
  持卡（mesNotStoryLine）；_sel 卡只要在路线上。做成后从其后各点的 ayanoTime 扣掉该
  场景耗时（comAyanoTimeRefresh）。
- 做卡脚本：req 全部持有才开始；答案卡按脚本顺序递（build_guide.expected_hand_order）；
  终卡 run 对应 _f 剧本，读完授予章节梗概卡。
- 持卡 136 且未持 145 时，下一次进片段模式强制播 s3fc，得卡 145。

正文侧的机读约定（guide/template.typ）：
  #story-box(from: "s1s_35_sel", pick: ("没有约",))[ …正文… ]
      from  = 时间轴上要重讲的场景 id（首轮开局写 "s1s_20"）
      pick  = 沿途每个选择依次选的选项定译；谜题未持选择卡时用 "谜题答对"/"谜题答错"
      noskip = 持卡也不跳过的场景 id（如 s5s_680 要看到「他的身影」选择）
  #route(from: …, pick: …)   同上但不渲染（用于章节 5 那种表格化叙述）
  #route(event: "s7f")       主菜单直入的现实层剧本，只授卡
  #frag-box[ #make-cards(("卡名", [递 …]), …) ]   每行按序做一张卡

用法：
  uv run python tools/guide_route_check.py            # 校验，列出问题
  uv run python tools/guide_route_check.py --trace    # 逐步打印路线/沙漏/持卡
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUIDE = REPO / "guide"
LUA = REPO / "lua_scripts"
sys.path.insert(0, str(REPO / "tools"))
import build_guide  # noqa: E402

# ----------------------------------------------------------------------------
# Lua 调度器 → 语句树
# ----------------------------------------------------------------------------
STATE_RE = re.compile(r'^(?:else)?if doScriptScene == "([^"]+)" then$')
FUNC_DECL_RE = re.compile(r'^(?:local +)?(scene_\w+) = function\(')


@dataclass
class If:
    branches: list  # [(cond_text, [nodes])]
    orelse: list = field(default_factory=list)


@dataclass
class While:
    cond: str
    body: list


def parse_block(lines: list[str]) -> list:
    """把 main() 体内的行解析成 If/While/语句 的嵌套树（printer 保证 if/else/end 各占一行）。"""
    root: list = []
    stack: list = [root]  # 栈顶 = 当前正在填充的语句列表
    owners: list = []     # 与 stack 平行：当前列表属于哪个 If/While（root 为 None）
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("--"):
            continue
        s = re.sub(r"\s*--.*$", "", s)
        if s.startswith("if ") and s.endswith(" then"):
            node = If([(s[3:-5], [])])
            stack[-1].append(node)
            stack.append(node.branches[0][1])
            owners.append(node)
        elif s.startswith("elseif ") and s.endswith(" then"):
            node = owners[-1]
            assert isinstance(node, If), s
            node.branches.append((s[7:-5], []))
            stack[-1] = node.branches[-1][1]
        elif s == "else":
            node = owners[-1]
            assert isinstance(node, If), s
            stack[-1] = node.orelse
        elif s.startswith("while ") and s.endswith(" do"):
            node = While(s[6:-3], [])
            stack[-1].append(node)
            stack.append(node.body)
            owners.append(node)
        elif s == "end":
            stack.pop()
            owners.pop()
        else:
            stack[-1].append(s)
    assert len(stack) == 1, "块未闭合"
    return root


def load_states() -> dict[str, list]:
    """全部章节剧本的调度器状态 → 语句树（状态名全局唯一，跨章 run() 直接续跑）。"""
    states: dict[str, list] = {}
    for f in sorted(LUA.glob("snr_*_10_*.lua")):
        text = f.read_text(encoding="utf-8")
        idx = text.rfind("\nmain = function()")
        if idx < 0:
            continue
        body = text[idx + 1:].splitlines()[1:]
        # 去掉最后的 `end`（main 的），其余交给块解析
        while body and body[-1].strip() != "end":
            body.pop()
        body.pop()
        tree = parse_block(body)
        # 找 `while l1_0 == 0 do` 里的 if 链
        chain = None
        for node in tree:
            if isinstance(node, While):
                for inner in node.body:
                    if isinstance(inner, If) and STATE_RE.match("if " + inner.branches[0][0] + " then"):
                        chain = inner
        if chain is None:
            continue
        for cond, nodes in chain.branches:
            m = STATE_RE.match("if " + cond + " then")
            if not m:
                print(f"[route] {f.name}: 调度器 if 链里混入非状态分支 `{cond}`，已跳过", file=sys.stderr)
                continue
            states[m.group(1)] = nodes
    return states


# ----------------------------------------------------------------------------
# 场景函数元数据：自带耗时 / 授卡 / GameOver / 完成 / 可跳过
# ----------------------------------------------------------------------------
@dataclass
class SceneFn:
    cost: int | None = None
    gets: list[int] = field(default_factory=list)
    gameover: bool = False
    complete: bool = False
    skippable: bool = False


def load_scene_fns() -> dict[str, SceneFn]:
    out: dict[str, SceneFn] = {}
    for f in sorted(LUA.glob("snr_*_10_*.lua")):
        lines = f.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            m = FUNC_DECL_RE.match(lines[i])
            if not m:
                i += 1
                continue
            j = i + 1
            while j < len(lines) and lines[j] != "end":
                j += 1
            body = lines[i + 1:j]
            sf = SceneFn()
            for k, ln in enumerate(body):
                s = ln.strip()
                mm = re.match(r"comSectionStoryEnd\(gameSave\.sceneId, gameSave\.sceneName, (\w+)\)", s)
                if mm:
                    arg = mm.group(1)
                    if arg.isdigit():
                        sf.cost = int(arg)
                    else:
                        for back in range(k - 1, max(-1, k - 8), -1):
                            a = re.match(r"(?:local )?" + re.escape(arg) + r" = (-?\d+)$", body[back].strip())
                            if a:
                                sf.cost = int(a.group(1))
                                break
                mm = re.match(r"gameSave\.myCard\[(\d+)\]\.hold = 1$", s)
                if mm:
                    sf.gets.append(int(mm.group(1)))
                if s.startswith("comSectionGameOver()"):
                    sf.gameover = True
                if s.startswith("comSectionComplete()"):
                    sf.complete = True
                if "comDlgStorylineSkip(" in s:
                    sf.skippable = True
            out[m.group(1)] = sf
            i = j + 1
    return out


# ----------------------------------------------------------------------------
# 模拟器
# ----------------------------------------------------------------------------
class RouteError(Exception):
    pass


class Terminal(Exception):
    def __init__(self, kind: str):
        self.kind = kind


@dataclass
class RouteEntry:
    scene: str
    time: int  # 开讲前的 ayanoTime


class Sim:
    def __init__(self, trace: bool = False):
        self.states = load_states()
        self.scene_fns = load_scene_fns()
        dag = json.loads((REPO / "data/dag.json").read_text(encoding="utf-8"))
        self.crds = dag["crds"]
        self.scene2card: dict[str, int] = json.loads((REPO / "data/scene2card.json").read_text(encoding="utf-8"))
        self.card2scene: dict[int, str] = {}
        for sid, n in self.scene2card.items():
            self.card2scene.setdefault(n, sid)
        # _f 剧本读完授予的卡（按文件前缀聚合 scene_meta.gets）
        self.f_gets: dict[str, list[int]] = {}
        for fn, meta in dag["scene_meta"].items():
            m = re.match(r"scene_((?:s\d|e\d|so)f[abc]?)[_-]", fn)
            if m and meta.get("gets"):
                self.f_gets.setdefault(m.group(1), []).extend(meta["gets"])
        self.hand_order = build_guide.expected_hand_order()
        options = json.loads((GUIDE / "generated/options.json").read_text(encoding="utf-8"))
        self.opt_zh: dict[str, str] = {b: o["zh"] for b, o in options.items()}
        cards = build_guide.load_cards()
        self.card_title: dict[int, str] = {n: c["title_zh"] for n, c in cards.items()}
        self.trace = trace
        # 存档状态
        self.route: list[RouteEntry] = []
        self.time = 0
        self.held: set[int] = {1}  # 序章读完得卡 1
        self.visited: list[str] = []

    # -- 小工具 -------------------------------------------------------------
    def name(self, n: int) -> str:
        return f"『{self.card_title.get(n, '卡' + str(n))}』"

    def sname(self, sid: str) -> str:
        n = self.scene2card.get(sid)
        return f"{sid}{self.name(n) if n else ''}"

    def held_scene(self, sid: str) -> bool:
        n = self.scene2card.get(sid)
        if n is None:
            raise RouteError(f"场景 {sid} 没有对应卡（sceneId2aCard 缺项）")
        return n in self.held

    def log(self, *a):
        if self.trace:
            print("   ", *a)

    def _end(self, sid: str, cost: int, force: bool = False, append: bool = True):
        if append:
            self.route.append(RouteEntry(sid, self.time))
        if force or not self.held_scene(sid):
            self.time += cost
        self.log(f"结束 {self.sname(sid)} 耗时{cost if force or not self.held_scene(sid) else 0} → 沙漏 {self.time}")
        if self.time >= 100:
            raise Terminal("timeover")

    # -- 表达式 / 条件求值 -----------------------------------------------------
    def eval_expr(self, e: str, env: dict, ctx: dict):
        e = e.strip()
        if re.fullmatch(r"-?\d+", e):
            return int(e)
        if e == "true":
            return True
        if e == "false":
            return False
        if e in ("{}", '""'):
            return None
        if e.startswith('"'):
            return e.strip('"')
        m = re.fullmatch(r"sceneId2aCard\.(\w+)", e)
        if m:
            return self.scene2card[m.group(1)]
        m = re.fullmatch(r"sceneId2aCard\[(\w+)\]", e)
        if m:
            return self.scene2card[self.eval_expr(m.group(1), env, ctx)]
        m = re.fullmatch(r"gameSave\.myCard\[(.+)\]\.hold", e)
        if m:
            n = self.eval_expr(m.group(1), env, ctx)
            return 1 if n in self.held else -1
        m = re.fullmatch(r'comSectionStoryCheckRoute\("([^"]+)"\)', e)
        if m:
            return any(r.scene == m.group(1) for r in self.route)
        m = re.fullmatch(r"comDlgSelectItem\((.*)\)", e)
        if m:
            return self.choose(m.group(1), ctx)
        m = re.fullmatch(r'(scene_\w+)\(doScriptScene, "[^"]*"\)', e)
        if m:
            return self.play(m.group(1), ctx)
        m = re.fullmatch(r"scene_s5s_dispatch_v4[23]\(.*\)", e)
        if m:
            return 0  # 日记递卡：假定一次递对，无罚时
        m = re.fullmatch(r"scene_s5s_dispatch_v4[45]\(\)", e)
        if m:
            return True
        m = re.fullmatch(r"comSelectMap\(.*\)", e)
        if m:
            return 0
        if re.fullmatch(r"[A-Za-z_]\w*", e):
            if e in env:
                return env[e]
            raise RouteError(f"未定义变量 {e}")
        raise RouteError(f"不会求值的表达式: {e}")

    def eval_cond(self, c: str, env: dict, ctx: dict) -> bool:
        c = c.strip()
        m = re.fullmatch(r"not \((.+)\)", c)
        if m:
            return not self.eval_cond(m.group(1), env, ctx)
        # `A == B`：B 一般是字面量，A 可能含括号（函数调用）
        m = re.fullmatch(r"(.+) == ([^=]+)", c)
        if m:
            return self.eval_expr(m.group(1), env, ctx) == self.eval_expr(m.group(2), env, ctx)
        m = re.fullmatch(r"(.+) <= (.+)", c)
        if m:
            return self.eval_expr(m.group(1), env, ctx) <= self.eval_expr(m.group(2), env, ctx)
        m = re.fullmatch(r"(.+) < (.+)", c)
        if m:
            return self.eval_expr(m.group(1), env, ctx) < self.eval_expr(m.group(2), env, ctx)
        raise RouteError(f"不会求值的条件: {c}")

    # -- 场景 / 选择 ------------------------------------------------------------
    def play(self, fn: str, ctx: dict) -> bool:
        sid = ctx["state"]
        sf = self.scene_fns.get(fn)
        if sf is None:
            raise RouteError(f"找不到场景函数 {fn}")
        self.visited.append(sid)
        if sf.gameover:
            self.log(f"GAME OVER 场景 {fn}")
            raise Terminal("gameover")
        if sf.complete:
            self.log(f"章节完成 {fn}")
            raise Terminal("complete")
        skip = sf.skippable and self.held_scene(sid) and sid not in ctx["noskip"]
        for g in sf.gets:
            if g not in self.held:
                self.held.add(g)
                self.log(f"入手 {self.name(g)}")
        if sf.cost is not None:
            self._end(sid, sf.cost)
        return skip

    def choose(self, args: str, ctx: dict) -> int:
        buttons = re.findall(r'"(sel_[^"]+)", -?\d+, -?\d+, (\d+)', args)
        avail = {self.opt_zh.get(b, b): int(v) for b, v in buttons}
        picks = ctx["picks"]
        if not picks:
            raise RouteError(f"{self.sname(ctx['state'])} 弹出选择但 pick 已用完，可选：{list(avail)}")
        p = picks.pop(0)
        if p not in avail:
            raise RouteError(f"{self.sname(ctx['state'])} 此时没有选项「{p}」，可选：{list(avail)}")
        self.log(f"选择「{p}」")
        return avail[p]

    # -- 语句执行 -----------------------------------------------------------------
    def run_nodes(self, nodes: list, env: dict, ctx: dict):
        for node in nodes:
            if isinstance(node, If):
                for cond, body in node.branches:
                    if self.eval_cond(cond, env, ctx):
                        self.run_nodes(body, env, ctx)
                        break
                else:
                    self.run_nodes(node.orelse, env, ctx)
            elif isinstance(node, While):
                self.run_while(node, env, ctx)
            else:
                self.run_stmt(node, env, ctx)

    def run_while(self, node: While, env: dict, ctx: dict):
        """探索地图 / 谜题这类交互循环：假定玩家按攻略做完，只处理其对后续状态的影响。"""
        state = ctx["state"]
        if state == "s2s_190_sel" and not ctx.get("quiz_done"):
            # 未持选择卡直接答题：结果由 pick 决定（"谜题答对"/"谜题答错"）
            picks = ctx["picks"]
            if not picks or picks[0] not in ("谜题答对", "谜题答错"):
                raise RouteError("s2s_190_sel 直接答题，pick 需要给出「谜题答对」或「谜题答错」")
            p = picks.pop(0)
            env["l1_3"] = 0 if p == "谜题答对" else 1
            ctx["quiz_done"] = True
            self.log(f"谜题：{p}")
        # 其余 while（探索地图、谜题第二题、ウワサ循环）按「做完」处理，跳过循环体

    def run_stmt(self, s: str, env: dict, ctx: dict):
        m = re.fullmatch(r'doScriptScene = "([^"]+)"', s)
        if m:
            env["doScriptScene"] = m.group(1)
            return
        m = re.fullmatch(r"gameSave\.myCard\[(\d+)\]\.hold = 1", s)
        if m:
            n = int(m.group(1))
            if n not in self.held:
                self.held.add(n)
                self.log(f"入手 {self.name(n)}")
            return
        if s == "gameSave.ayanoTime = 0":
            self.time = 0
            return
        if s == "cInitStoryRoute()":
            self.route.clear()
            return
        m = re.fullmatch(r"comSectionStoryEnd(Force)?\(gameSave\.sceneId, gameSave\.sceneName, (\w+)\)", s)
        if m:
            self._end(ctx["state"], int(self.eval_expr(m.group(2), env, ctx)), force=bool(m.group(1)))
            return
        m = re.fullmatch(r"comSectionStoryChkAyanoTime\(gameSave\.sceneId, (\w+)\)", s)
        if m:
            self._end(ctx["state"], int(self.eval_expr(m.group(1), env, ctx)), append=False)
            return
        m = re.fullmatch(r"(?:local )?([A-Za-z_]\w*) = (.+)", s)
        if m:
            env[m.group(1)] = self.eval_expr(m.group(2), env, ctx)
            return
        m = re.fullmatch(r'(scene_\w+)\(doScriptScene, "[^"]*"\)', s)
        if m:
            self.play(m.group(1), ctx)
            return
        if re.fullmatch(r"scene_\w+\(\)", s):
            return  # 探索小节 / 收尾小节，无耗时无授卡（有授卡的写在调度器里）
        if re.fullmatch(r"(?:local )?[A-Za-z_]\w*\.\w+ = .+", s):
            return  # 探索地图的到访计数表
        if s.startswith(("run(", "quit()", "wait(", "oCom.", "comSectionFragmentItemInit", "break")):
            return
        if s.startswith(("gameSave.sectionName", "layer", "switchScreen", "cPlay", "cStop", "fontClear")):
            return
        raise RouteError(f"不会执行的语句: {s}")

    # -- 故事模式一轮 ---------------------------------------------------------------
    def story(self, start: str, picks: list[str], noskip: set[str]) -> str:
        if self.route:
            idxs = [i for i, r in enumerate(self.route) if r.scene == start]
            if not idxs:
                raise RouteError(f"时间轴上没有 {self.sname(start)}，无法从它重讲；当前路线：{[r.scene for r in self.route]}")
            i = idxs[-1]
            self.time = self.route[i].time
            del self.route[i:]
            self.log(f"从 {self.sname(start)} 重讲，沙漏回到 {self.time}")
        elif start != "s1s_20":
            raise RouteError("首轮只能从 s1s_20 开局")
        self.visited = []
        picks = list(picks)
        ctx = {"picks": picks, "noskip": noskip}
        state = start
        try:
            while state != "end":
                if state not in self.states:
                    raise RouteError(f"没有状态 {state}")
                ctx["state"] = state
                env = {"doScriptScene": state}
                self.run_nodes(self.states[state], env, ctx)
                state = env["doScriptScene"]
            terminal = "menu"
        except Terminal as t:
            terminal = t.kind
        if picks:
            raise RouteError(f"pick 有多余项未用到: {picks}（终止于 {terminal}）")
        self.log(f"本轮终止：{terminal}；路线 {[r.scene for r in self.route]}")
        return terminal

    def probe_deadend(self, last: str) -> bool:
        """沙漏在 last 用完之后：做完它的卡再从它接着讲，是否只会问一次跳过就直接 GAME OVER、时间轴不添新场景。

        玩家 2026-09-20 反馈：这种位置攻略直接换分支是对的，但「这里后面还有没有剧情」不明确，须显式标注。
        探针在快照上跑：假定 last 的卡已持有，从 last 重讲、不给任何选项；只有「gameover 且路线只多回
        last 自己」才算死胡同——弹出选择（RouteError）、再次 Time over（说明后面还有未持卡的新场景）、
        章节完成都不算。"""
        snap = (list(self.route), self.time, set(self.held), list(self.visited), self.trace)
        self.trace = False
        try:
            self.held.add(self.scene2card[last])
            n_before = len([r for r in self.route][: [i for i, r in enumerate(self.route) if r.scene == last][-1]])
            try:
                terminal = self.story(last, [], set())
            except RouteError:
                return False
            return terminal == "gameover" and len(self.route) == n_before + 1
        finally:
            self.route, self.time, self.held, self.visited, self.trace = list(snap[0]), snap[1], set(snap[2]), list(snap[3]), snap[4]

    # -- 片段模式做一张卡 ---------------------------------------------------------------
    def enter_fragment(self):
        if 136 in self.held and 145 not in self.held:
            self.held.add(145)
            self.log("强制事件 s3fc → 入手 卡145")

    def make(self, card: int):
        sid = self.card2scene.get(card)
        if sid is None:
            raise RouteError(f"{self.name(card)} 不是场景卡，不能在片段模式做")
        if card in self.held:
            raise RouteError(f"{self.name(card)} 已持有，不必再做")
        idxs = [i for i, r in enumerate(self.route) if r.scene == sid]
        if not idxs:
            raise RouteError(f"要做 {self.name(card)}，但 {sid} 不在当前时间轴上；当前路线：{[r.scene for r in self.route]}")
        i = idxs[-1]
        if not sid.endswith("_sel"):
            for r in self.route[:i]:
                if not r.scene.endswith("_sel") and not self.held_scene(r.scene):
                    raise RouteError(f"要做 {self.name(card)}，但它之前的 {self.sname(r.scene)} 还没做卡（あらすじは物語の先頭から順番に作成する必要があります）")
        crd = self.crds[str(card)]
        for r in crd["req"]:
            if r not in self.held:
                raise RouteError(f"做 {self.name(card)} 需要先持有 {self.name(r)}")
        for a in self.hand_order.get(card, []):
            if a not in self.held:
                raise RouteError(f"做 {self.name(card)} 要递 {self.name(a)}，但没有这张卡")
        self.held.add(card)
        for g in crd["gets"]:
            self.held.add(g)
        for run in crd["runs"]:
            m = re.match(r"snr_(s\d|e\d)_10_(f[abc]?)", run)
            key = m.group(1) + m.group(2)
            for g in self.f_gets.get(key, []):
                self.held.add(g)
            self.log(f"读现实层 {key} → 入手 {[self.name(g) for g in self.f_gets.get(key, [])]}")
        # comAyanoTimeRefresh：从做卡场景之后各点扣掉它的耗时
        if i + 1 < len(self.route):
            delta = self.route[i + 1].time - self.route[i].time
            for r in self.route[i + 1:]:
                r.time = max(0, r.time - delta)
        self.log(f"做成 {self.name(card)}")

    def event(self, name: str):
        if name == "s7f":
            for g in self.f_gets["s7f"]:
                self.held.add(g)
            self.log(f"主菜单 Section 7 → 入手 {[self.name(g) for g in self.f_gets['s7f']]}")
        else:
            raise RouteError(f"未知事件 {name}")


# ----------------------------------------------------------------------------
# 从 guide/chapters/*.typ 抽路线步骤
# ----------------------------------------------------------------------------
@dataclass
class Step:
    kind: str          # story / frag / event
    file: str
    line: int
    args: dict = field(default_factory=dict)
    body: str = ""
    cards: list = field(default_factory=list)   # frag：(卡号, 行号)


def parse_args(text: str) -> dict:
    out: dict = {}
    for key in ("from", "event"):
        m = re.search(key + r':\s*"([^"]+)"', text)
        if m:
            out[key] = m.group(1)
    for key in ("pick", "noskip"):
        m = re.search(key + r":\s*\((.*?)\)", text, re.S)
        if m:
            out[key] = re.findall(r'"([^"]*)"', m.group(1))
    return out


def match_bracket(text: str, start: int, pair: str = "[]") -> int:
    """text[start] == pair[0]，返回配对 pair[1] 的下标（pick 元组、make-cards 都有嵌套）。"""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == pair[0]:
            depth += 1
        elif text[i] == pair[1]:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"{pair} 不配对")


def chapter_files() -> list[Path]:
    main = (GUIDE / "main.typ").read_text(encoding="utf-8")
    return [GUIDE / m for m in re.findall(r'#include "(chapters/[^"]+)"', main)]


def load_steps(cards_by_title: dict[str, int]) -> list[Step]:
    steps: list[Step] = []
    box_re = re.compile(r"#(story-box|frag-box|route)\b")
    for f in chapter_files():
        text = f.read_text(encoding="utf-8")
        pos = 0
        while True:
            m = box_re.search(text, pos)
            if not m:
                break
            kind = m.group(1)
            line = text.count("\n", 0, m.start()) + 1
            i = m.end()
            argtxt = ""
            if i < len(text) and text[i] == "(":
                j = match_bracket(text, i, "()")
                argtxt = text[i:j + 1]
                i = j + 1
            body = ""
            if i < len(text) and text[i] == "[":
                end = match_bracket(text, i)
                body = text[i + 1:end]
                pos = end + 1
            else:
                pos = i
            args = parse_args(argtxt)
            if kind == "route":
                steps.append(Step("event" if "event" in args else "story", f.name, line, args, body))
            elif kind == "story-box":
                steps.append(Step("story", f.name, line, args, body))
            else:
                st = Step("frag", f.name, line, args, body)
                for row in build_guide.MAKE_ROW_RE.finditer(body):
                    title, cid = row.group(1), row.group(3)
                    n = int(cid) if cid else cards_by_title.get(title)
                    if n is None:
                        raise RouteError(f"{f.name}:{line} 未知卡名 {title}")
                    st.cards.append((n, line + body.count("\n", 0, row.start())))
                steps.append(st)
    return steps


MARKERS = {"timeover": "#timeover", "gameover": "#gameover", "complete": "#complete"}


def check(trace: bool = False) -> list[str]:
    sim = Sim(trace=trace)
    cards = build_guide.load_cards()
    by_title: dict[str, int] = {}
    for n in sorted(cards):
        by_title.setdefault(cards[n]["title_zh"], n)
    scene_cards = set(sim.card2scene)
    problems: list[str] = []
    for st in load_steps(by_title):
        where = f"{st.file}:{st.line}"
        if trace:
            print(f"== {where} {st.kind} {st.args}")
        try:
            if st.kind == "event":
                sim.event(st.args["event"])
            elif st.kind == "story":
                if "from" not in st.args:
                    problems.append(f"{where} story-box 缺 from:（未标明从哪个场景重讲，无法校验）")
                    continue
                terminal = sim.story(st.args["from"], st.args.get("pick", []), set(st.args.get("noskip", [])))
                # 正文里提到的场景卡必须按序出现在本轮讲过的场景里
                mentioned = []
                for t, cid in re.findall(r'#card\("([^"]+)"(?:, id: (\d+))?', st.body):
                    n = int(cid) if cid else by_title.get(t)
                    if n in scene_cards:
                        mentioned.append(n)
                visited_cards = [sim.scene2card[s] for s in sim.visited if s in sim.scene2card]
                k = 0  # 子序列匹配；同一张卡紧接着再提一次可以落在同一位置
                for n in mentioned:
                    while k < len(visited_cards) and visited_cards[k] != n:
                        k += 1
                    if k == len(visited_cards):
                        problems.append(f"{where} 正文提到 {sim.name(n)}，但本轮按 pick 讲不到它或顺序不对（讲到的：{[sim.name(c) for c in visited_cards]}；终止于 {terminal}）")
                        break
                for kind, marker in MARKERS.items():
                    if marker in st.body and terminal != kind:
                        problems.append(f"{where} 正文标了 {marker}，模拟结果是 {terminal}")
                if terminal == "timeover" and "#timeover" not in st.body and "沙漏" not in st.body:
                    problems.append(f"{where} 本轮在 {sim.sname(sim.route[-1].scene)} 沙漏满（Time over），正文没写")
                if terminal == "timeover":
                    last = sim.route[-1].scene
                    dead = sim.probe_deadend(last)
                    marked = "#deadend" in st.body
                    if dead and not marked:
                        problems.append(f"{where} 沙漏在 {sim.sname(last)} 用完，其后紧接 GAME OVER（做完卡回来接着讲没有新剧情），正文须标 #deadend")
                    if marked and not dead:
                        problems.append(f"{where} 标了 #deadend，但从 {sim.sname(last)} 接着讲并不是直接 GAME OVER")
            else:
                sim.enter_fragment()
                for n, ln in st.cards:
                    try:
                        sim.make(n)
                    except RouteError as e:
                        problems.append(f"{st.file}:{ln} {e}")
        except RouteError as e:
            problems.append(f"{where} {e}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trace", action="store_true")
    a = ap.parse_args()
    problems = check(trace=a.trace)
    for p in problems:
        print("[route]", p)
    if problems:
        sys.exit(f"[route] {len(problems)} 处路线问题")
    print("[route] OK")


if __name__ == "__main__":
    main()
