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
# 局部名跨基座不稳定（旧 pyluadec 是 v\d+，现基座是 l<depth>_<reg>），故这两条一律用
# 通用标识符匹配；「是不是选项变量」由 comDlgSelectItem 赋值集合判定，不靠命名形状。
CHOICE_RE = re.compile(r'(?:else)?if ([A-Za-z_]\w*) == (\d+) then')
SEL_ASSIGN_RE = re.compile(r'^(?:local\s+)?([A-Za-z_]\w*) = comDlgSelectItem\(')
SUBCALL_RE = re.compile(r'(scene_[\w]+)\(\)')
COST_RE = re.compile(r'comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, gameSave\.sceneName, (\d+)\)')
GET_RE = re.compile(r'gameSave\.myCard\[(\d+)\]\.hold = 1')
SHOW_RE = re.compile(r'comSectionCardFlagIn\((\d+)')
# 现基座的函数声明是 `local NAME = function(...)`（890 处）或 `NAME = function(...)`（317 处）
SCENE_DECL_SPLIT_RE = re.compile(r'\n(?:local +)?(scene_[\w]+) = function')
# crd 的「答案卡号」：绑定到 oCard.selectCardObj() 的返回值变量，再看它跟哪些卡号比。
# 旧基座靠 `if v\d+ == (\d+)` 的松正则 + 扣掉 {0,1}，跨基座既不可移植（局部名变了）
# 又会误收循环/选项下标（如 crd_102 的 `if l1_2 == 5`，那是 6 选 1 的选项序号不是卡号）。
# 这条严格规则在全 196 张卡上与旧产物逐卡一致（101 张有答案 / 168 个答案，0 处不符）。
CARD_SEL_RE = re.compile(r'^\s*(?:local\s+)?([A-Za-z_]\w*)\s*=\s*oCard\.selectCardObj\(\)')
CARD_CMP_RE = re.compile(r'if ([A-Za-z_]\w*) == (\d+) then')
WHILE_RE = re.compile(r'^while\b')

COST_ARG_RE = re.compile(
    r'(comSectionStoryEnd(?:Force)?\(gameSave\.sceneId, gameSave\.sceneName, )([A-Za-z_]\w*)(\))')
INT_LIT_RE = re.compile(r'^-?\d+$')
COST_LOOKBACK = 8


def inline_cost_consts(text: str) -> str:
    """把 comSectionStoryEnd(…, <局部常量>) 里的变量替换回它的整数字面量。

    现基座 175/175 个 comSectionStoryEnd 传的都是局部常量（`local l2_0 = 25` 紧挨其后
    的调用），字面量形状的 COST_RE 会全部失配 ⇒ ayanoTime 耗时全丢。
    回溯规则：向上找该变量的**首个**赋值——只有 RHS 是整数字面量才内联；若首个赋值是
    函数调用（s5 的 `l1_1 = scene_s5s_dispatch_v42(…, l1_1, 30, …)` 累加器）就原样留着，
    那种 cost 是运行期算出来的，本来就没有静态字面量可填（旧基座同样取不到）。
    """
    lines = text.splitlines(keepends=True)
    out = list(lines)
    for i, line in enumerate(lines):
        m = COST_ARG_RE.search(line)
        if not m:
            continue
        var = m.group(2)
        assign = re.compile(r'^\s*(?:local\s+)?' + re.escape(var) + r'\s*=\s*(.*?)\s*$')
        for j in range(i - 1, max(-1, i - 1 - COST_LOOKBACK), -1):
            a = assign.match(lines[j].rstrip("\n"))
            if not a:
                continue
            if INT_LIT_RE.match(a.group(1)):
                out[i] = line[:m.start(2)] + a.group(1) + line[m.end(2):]
            break   # 首个赋值说了算；非字面量则放弃解析
    return "".join(out)


def parse_states(stem: str, text: str) -> dict:
    text = inline_cost_consts(text)
    idx = text.rfind("\nmain = function()")
    main = text[idx:] if idx >= 0 else ""
    states, cur, pend_choice = {}, None, None
    choice_vars = set()  # Track which variables are assigned from comDlgSelectItem

    # First pass: collect choice variables for each state (exclude vars inside while loops)
    # while 块靠**缩进**配对（打印器统一 4 空格、`end` 与开块语句同缩进），不数 `end`：
    # 数 `end` 的老写法会被 if/else 的 end 提前清零，而新旧基座 else/elseif 的 end 数量
    # 本就不同（旧基座嵌套 else+if，新基座合成 elseif）。
    state_choice_vars = {}
    cur_state = None
    while_stack = []  # 当前所在 while 块的开块缩进（栈顶=最内层）
    for line in main.splitlines():
        s = line.strip()
        if m := STATE_RE.match(s):
            cur_state = m.group(1)
            state_choice_vars[cur_state] = set()
            while_stack = []
            continue
        if cur_state is None:
            continue
        indent = len(line) - len(line.lstrip())
        if s == "end":
            while while_stack and indent <= while_stack[-1]:
                while_stack.pop()
        elif WHILE_RE.match(s):
            while_stack.append(indent)
            continue
        # Only collect choice vars if NOT inside a while loop
        if not while_stack and (m := SEL_ASSIGN_RE.search(s)):
            state_choice_vars[cur_state].add(m.group(1))

    # Second pass: parse events
    for line in main.splitlines():
        s = line.strip()
        if m := STATE_RE.match(s):
            cur = m.group(1)
            states[cur] = {"file": stem, "scene": None, "title": None, "seq": []}
            pend_choice = None
            choice_vars = state_choice_vars.get(cur, set())
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
                pend_choice = None
            else:
                ev.append({"goto": m.group(1)})
        elif m := RUN_RE.search(s):
            ev.append({"run": m.group(1)})
        elif m := ROUTE_RE.search(s):
            ev.append({"route_has": m.group(1)})
        elif m := GATE_RE.search(s):
            ev.append({"card_gate": int(m.group(1)), "held": m.group(2) == "1"})
        elif m := CHOICE_RE.match(s):
            var = m.group(1)
            # Only arm pend_choice if this variable is a known choice variable
            if var in choice_vars:
                pend_choice = int(m.group(2))
        elif m := SUBCALL_RE.search(s):
            # Guard: avoid matching scene function calls with parameters (dispatcher calls)
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
    text = inline_cost_consts(text)
    res = {}
    parts = SCENE_DECL_SPLIT_RE.split('\n' + text)
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


def parse_crd_answers(text: str) -> list:
    """玩家递上来的卡（oCard.selectCardObj() 的返回值）被拿去跟哪些卡号比对。

    ⚠ 2026-09-13 修正：曾在结尾扣掉 {0, 1}。那是旧松正则（`if v\\d+ == (\\d+)`）时代的补丁——
    当时会误收错卡计数器的 `l1_2 == 0/1`。改成绑定 `oCard.selectCardObj()` 的返回变量后，
    计数器已经进不来（全库实测：hand_var 与 0 比零处、与 1 比恰好 3 处），那条减法就只剩误伤：
    **卡 1『ある子が学校にくる物語』是 crd_2/30/108 的合法答案卡**，被一并抹掉了。
    取消返回的 -1 不必再滤——CARD_CMP_RE 的 `(\\d+)` 不吃负号。"""
    hand_vars, answers = set(), set()
    for line in text.splitlines():
        if m := CARD_SEL_RE.match(line):
            hand_vars.add(m.group(1))
            continue
        if (m := CARD_CMP_RE.search(line)) and m.group(1) in hand_vars:
            answers.add(int(m.group(2)))
    return sorted(answers)


def parse_crds(script_dir) -> dict:
    crds = {}
    for p in sorted(script_dir.glob("snr_crd_*.lua")):
        n = int(re.search(r"snr_crd_(\d+)", p.stem).group(1))
        t = p.read_text(encoding="utf-8")
        crds[str(n)] = {
            "stub": t.count("vms(") <= 2 and t.count("\n") < 15,
            "req": sorted({int(x) for x in re.findall(r'myCard\[(\d+)\]\.hold == -1', t)}),
            "answers": parse_crd_answers(t),
            "runs": sorted(set(RUN_RE.findall(t)) - {"snr_fragment_main", "snr_mainmenu"}),
            # 该卡自身的授予写作 gameSave.myCard[fragmentDoCardId].hold = 1（变量下标，
            # 不会被这条字面量正则命中）；gets 只收「做这张卡时附带发出的别的卡」。
            "gets": sorted({int(x) for x in GET_RE.findall(t)}),
        }
    return crds


def build(script_dir):
    states, meta = {}, {}
    for p in sorted(script_dir.glob("snr_s*_10_*.lua")) + sorted(script_dir.glob("snr_e*_10_*.lua")):
        t = p.read_text(encoding="utf-8")
        states.update(parse_states(p.stem, t))
        meta.update(parse_scene_meta(p.stem, t))
    return {"states": states, "scene_meta": meta, "crds": parse_crds(script_dir)}


def render(dag) -> str:
    return json.dumps(dag, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(DATA))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    dag = build(REPO / "lua_scripts")
    text = render(dag)
    path = Path(args.out_dir) / "dag.json"
    if args.check:
        same = path.exists() and path.read_text(encoding="utf-8") == text
        print("check:", "OK" if same else "MISMATCH")
        return 0 if same else 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"states={len(dag['states'])} scene_meta={len(dag['scene_meta'])} crds={len(dag['crds'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
