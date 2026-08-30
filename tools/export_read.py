"""通读导出：把全书最终译文按**正典路线序**摊成一份纯文本，供 1M 上下文模型一次读完。

与 `tools/read_server.py` 的关系：那一份是给**人**读的 Web UI，每行摊开原文、首译、
修订史、人裁批注——信息密度是为"逐行判断"设计的。本工具服务另一个场景：把定稿
一次性喂给长上下文模型做整体审读，于是只留**最终译文本身**，一条一行。序、单元
装配、卡名退化标题三件事直接复用 `read_server.Reader`（构造实测 0.2 秒），不复制
第二份路线逻辑——路线序只该有一个真相源。

## 与翻译/润色派发格式的分别

派发用的 JSON 每条带原文、候选、批注、glossary 版本，是为"改哪一条"服务的；那套
格式喂给通读模型，会让 40 万字正文膨胀到三四倍，且模型每读一行都要先跳过一堆
不该影响判断的元数据。这里反过来：**只有译文、标题、路线标记、卡面梗概**。

## 三处刻意不做的事

**选项不编号。** `sel_s2s_160_sel_b` 在 `s2s_80_sel` 那组里取值 3、在自己那组里取值 2
（`lua_scripts/snr_s2_10_s.lua:2745` 与 `:2794`），同一节点的选项集还随持卡状态变
（`:2792` 一项 / `:2794` 两项）——按钮字母与"第 N 项"之间**没有全局稳定的映射**。
硬编上号码等于凭空造一份路线事实，故只列出该节点的选项文本，具体这一遍选了第几项
由 marker 自己说（它来自 `route_plan.yaml`，是真的）。

**不用 `build/select_option_map.json`。** 它按"目标场景名即按钮字面"启发式推得，
与人工核验过的 `data/` 对不上（`sel_s1s_170_sel_a` 它说「放課後のコックリさん」，
人工核验的是「学校にもどる」），且 `build/` 已 gitignore。只认仓库内两份
`data/select_*_zh.jsonl`：一个按钮都没核验过的节点（34 个里有 11 个）**不给选项
行**；只核验了一部分的（12 个）照给，但行尾写明还缺几项——一份 1/3 的选项表与
完整的长得一模一样，不标出来就是在断言"这个节点只有这一个选择"。真实项数数
`png/select/` 的按钮图得来。

**缺译不静默跳过。** 写成 `〔缺译：id N〕` 并计数——跳过会让"完整"这个前提变成
假的，而少几十行没有任何征兆。（现车道实测 16693/16693 全译，这条是防回归的。）

## 标题的中文来源

`timeline` 的 `title` 是日文正名，本工具按用户裁定只出中文，三层查表：
1. `data/ledger_extra.jsonl` 的 454 条 `kind=scene_title` × 车道 `forward_extra.jsonl`
   ——场景名的中文定稿（393 个不同日文名，实测**零**一名多译）；
2. `data/extra_translated.jsonl`——UI/杂项词的定译；
3. `snr_crd_N` 单元一律走 `卡 N『中文卡名』`（`skeleton/cards.zh.yaml`）。
三层都不中的只剩 14 个单元（2 个演出池、教程卡 0、11 个整章 `_f`），由
`FALLBACK_TITLES` 与章段名兜底，**没有一个会退回日文**。
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import WORK, read_jsonl
from tools.read_server import DEFAULT_LANE, Reader

DEFAULT_OUT = WORK / "out" / "read.md"
#: 导言与正文的分界。测试靠它把导言摘掉（导言里有解释性的日文记号说明）。
HEADER_END = "<!-- 导言结束 -->"

#: 演出池单元（2 个）的中文名。键是 `snr_common:<函数名>`——`Reader._titles`
#: 对这类 title **原样透传**（它既不是 `snr_crd_N` 也不是 `snr_XX_10_f*`），所以
#: 这里查得到。其余兜底不走这张表：卡按卡号、整章 `_f` 按 unit_kind（见
#: `_unit_title`），因为那两类的 title 在 Reader 里已经被改写过，拿原值当键会静默落空。
FALLBACK_TITLES = {
    "snr_common:comSectionStoryEndAyanoTime": "讲述耗时与 Time over",
    "snr_common:comSectionMapmoveAyanoIn": "探索途中彩野到场",
}

HEADER = f"""\
# 《第二小说 ——她的夏天，15 分钟的记忆》中文通读本

本文件是全书**最终译文**的完整摊开，供一次性通读。读之前先记住六件事：

1. **顺序是玩家的经历序**，不是脚本登记序：先讲的场景在前，重讲、回溯、分支
   互斥的续写都按实际发生的先后排。`>` 开头的行是**讲述指针标记**——它说明
   接下来是回到某个选择点重讲、这一遍改选了第几项。看到它就意味着后面的内容
   与上文是**并行的另一种可能**，不是后续发展。
2. **双层叙事**。现实层：23 岁的直哉陪护重度前向性健忘（新记忆只存 15 分钟）的
   同级生彩野，听她在旧教室里断续讲一个夏天的故事。故事层：她讲的那个故事。
   人名两套写法**必须区分**——片假名系（Ayano、Yuichi、Sakura、Yukari）是故事层
   人物，汉字系（彩野、由加里、千秋、直哉）是现实层的人。
3. **一行 = 一条游戏文本**（对白或旁白）。`【名字】「…」` 是说话人前缀；无前缀即
   旁白；`○` 开头是场面说明式旁白；`■` 是系统通知。
4. **控制码原样保留**：`_n` `_r` 是引擎换行符，不是错字。`<汉字,pīn yīn>` 是注音
   （小字号渲染在该词正上方）。`『』` 是卡名与场面名的专用壳，`≪≫` `≦≧` 是
   强调与特殊语气括号。
5. `〔本场选项〕` 列出该选择节点的选项文本。**不编号**——游戏里按钮字母与
   "第几项"没有稳定对应，且选项集随持卡状态增减；这一遍选了哪个看紧随其后的
   场景标题和讲述指针标记。行尾若写着"另 N 项按钮文本未核验"，说明该节点实际
   还有 N 个选项，其文字尚未定稿，**不要**据此认为选项只有列出的这几个。
6. `〔卡面梗概〕` 是玩家把该场景压缩成一张卡片后，卡面上写着的梗概正文——游戏
   机制里"讲给 15 分钟记忆的人听"的压缩件，排在该卡首次作成的位置。

{HEADER_END}"""


def chapter_key(src) -> str:
    """单元的 `src` → 章段键。章段是**导出的大标题单位**，不是 ledger 的
    `chapter` 字段：后者把全部 196 张卡都记成 `crd`，而做卡段在路线上被打散成
    七十多截，按它分组会得到一个横跨全书的假章节。"""
    if not src:
        return "appendix"
    if re.fullmatch(r"snr_crd_\d+", src):
        return "crd"
    m = re.fullmatch(r"snr_([se]\d)_10_(s|f[a-z]?)", src)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    if src.startswith("snr_common"):
        return "pool"
    return "appendix"


def chapter_title(key: str) -> str:
    """章段键 → 中文大标题。"""
    if key == "crd":
        return "片段·做卡"
    if key == "pool":
        return "演出池"
    if key == "appendix":
        return "附录"
    m = re.fullmatch(r"([se])(\d)/(s|f)([a-z]?)", key)
    if not m:
        return key
    kind, num, layer, sub = m.groups()
    if kind == "e":
        head = f"EX{num}"
    else:
        head = "序章" if num == "0" else f"第 {num} 章"
    tail = "故事层" if layer == "s" else "现实层"
    # fa/fb/fc 是同一章按分支拆开的现实层脚本（3A 完 / 3B 完 / 强制段等）。
    # 给它们编中文序号等于替原作命名，故保留 lua 的后缀字母。
    return f"{head}·{tail}（f{sub}）" if sub else f"{head}·{tail}"


class Exporter:
    """把 `Reader` 装配好的路线渲染成通读文本。构造即完成全部读盘与建表；
    `render()` 纯拼字符串，可重复调用且结果恒等。"""

    def __init__(self, repo=None, lane=DEFAULT_LANE):
        self.reader = Reader(repo=repo, lane=lane)
        self.repo, self.zh = self.reader.repo, self.reader.current
        self.lane_label = self.reader.lane_label
        self.titles = self._title_map()
        self.cards = self._cards()
        self.options = self._options()
        self.button_counts = self._button_counts()
        self.stats = {}
        self._render()

    # ---- 查表 ----

    def _title_map(self) -> dict:
        """日文场景名 → 中文定稿。两个来源实测互不冲突（393 个 scene_title 无
        一名多译），故后来者不覆盖先到者。"""
        out = {}
        extra = self.repo / "data" / "ledger_extra.jsonl"
        fwd = self.reader.lane / "data" / "forward_extra.jsonl"
        if extra.exists() and fwd.exists():
            zh = {r["key"]: r.get("zh") for r in read_jsonl(fwd)}
            for r in read_jsonl(extra):
                if r.get("kind") == "scene_title" and zh.get(r["key"]):
                    out.setdefault(r["jp"], zh[r["key"]])
        tr = self.repo / "data" / "extra_translated.jsonl"
        if tr.exists():
            for r in read_jsonl(tr):
                if r.get("jp") and r.get("zh"):
                    out.setdefault(r["jp"], r["zh"])
        return out

    def _cards(self) -> dict:
        """卡号 → {title_zh, body_zh}。读不到骨架就返回空表——卡面是增补层，
        缺了它导出仍然成立（统计里会显示 card_faces=0）。"""
        p = self.repo / "skeleton" / "cards.zh.yaml"
        if not p.exists():
            return {}
        try:
            import yaml
            rows = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        except Exception:
            return {}
        return {r["card"]: r for r in rows
                if isinstance(r, dict) and r.get("card") is not None}

    def _options(self) -> dict:
        """`_sel` 状态 → 该节点选项的中文文本（按按钮字母序）。

        只认仓库内两份人工核验过的 `data/select_*_zh.jsonl`（见模块 docstring）。
        两份对同一按钮给出不同译文时以 `select_buttons_zh.jsonl` 为准——它是
        逐按钮核过的那一份（`bake_select.compute_coverage` 同序）。
        """
        by_button = {}
        opts = self.repo / "data" / "select_options_zh.jsonl"
        if opts.exists():
            for r in read_jsonl(opts):
                for b in r.get("buttons", []):
                    by_button[b] = r["zh"]
        btns = self.repo / "data" / "select_buttons_zh.jsonl"
        if btns.exists():
            for r in read_jsonl(btns):
                by_button[r["button"]] = r["zh"]
        out = {}
        for b, zh in by_button.items():
            m = re.fullmatch(r"sel_(.+_sel)_([a-z])", b)
            if m:
                out.setdefault(m.group(1), []).append((m.group(2), zh))
        return {st: [zh for _, zh in sorted(pairs)] for st, pairs in out.items()}

    def _button_counts(self) -> dict:
        """`_sel` 状态 → 该节点**实际存在**几个选项按钮（数 `png/select/` 的图）。

        存在的理由：34 个选择场景里有 12 个只核验过一部分按钮译文（如
        `s2s_190_sel` 3 项里只有 1 项）。照直印出来，一份 1/3 的选项表与完整的
        长得一模一样——读的人只会得出"这个节点就一个选择"。有了真实项数才能
        在行尾写明还缺几项。

        `png/` 是只读原始资产、恒在；真取不到时返回空表，选项行退化成不带
        缺项说明的形态（宁可少一句话，不因为一个装饰性字段让导出起不来）。
        """
        d = self.repo / "png" / "select"
        if not d.is_dir():
            return {}
        out = {}
        for f in d.iterdir():
            m = re.fullmatch(r"sel_(.+_sel)_([a-z])_(?:on|off)\.png", f.name)
            if m:
                out.setdefault(m.group(1), set()).add(m.group(2))
        return {st: len(v) for st, v in out.items()}

    # ---- 标题 ----

    def _unit_title(self, u: dict) -> str:
        """单元 → 中文小标题。查表顺序见模块 docstring；一路不中时用章段名
        兜底（`_f` 整章单元即走这里，渲染成「全章」）。"""
        src, title = u.get("src") or "", u.get("title") or ""
        m = re.fullmatch(r"snr_crd_(\d+)", src)
        if m:
            n = int(m.group(1))
            name = (self.cards.get(n) or {}).get("title_zh")
            if name:
                return f"卡 {n}『{name}』"
            # 卡 0 是教程脚本，骨架里没有它——它演示的正是"做卡"这件事本身
            return "卡 0（教程：做卡演示）" if n == 0 else f"卡 {n}"
        if title in self.titles:
            return self.titles[title]
        if title in FALLBACK_TITLES:
            return FALLBACK_TITLES[title]
        # 整章 `_f` 单元的 title 退化成了 lua 文件名，章段标题已经写明是哪一章
        return "全章" if u.get("unit_kind") == "fscene" else title

    # ---- 渲染 ----

    def _render(self) -> None:
        out, seen_runs, cur_run = [HEADER], set(), None
        n_lines = n_untranslated = n_faces = n_runs = 0
        n_sel_missing = n_sel_partial = 0
        used_cards = set()

        for u in self.reader.units:
            if u["type"] == "marker":
                out.append(f"\n> {u['text']}")
                continue
            key = "appendix" if u.get("unit_kind") == "appendix" else chapter_key(u.get("src"))
            if key != cur_run:
                cur_run, n_runs = key, n_runs + 1
                name = chapter_title(key)
                # 同一章被做卡段打断后回来，标题带（续）：重复出现的相同大标题
                # 会让线性阅读的模型以为自己绕回了开头。
                out.append(f"\n\n## {name}（续）" if key in seen_runs else f"\n\n## {name}")
                seen_runs.add(key)

            if u.get("unit_kind") == "appendix":
                # 这一段里混着反编译产物：`vms` 的第三参数不是字符串字面量而是
                # 拼接表达式（`i0 .. "_rsceneId：" .. …`）。它们照样是 ledger 的
                # 行、照样要出现，但不说明来历的话，读的人会当成待修的译文。
                nonlit = sum(1 for i in u.get("ids", ())
                             if not self.reader.ledger[i].get("literal"))
                note = f"；其中 {nonlit} 行是反编译拼接表达式，非游戏文本" if nonlit else ""
                out.append(f"\n### 路线未覆盖的 {u['n_lines']} 行（环境／系统串{note}）")
            else:
                out.append(f"\n### {self._unit_title(u)}")

            for cid in u.get("ids", []):
                if cid in self.zh:
                    out.append(self.zh[cid])
                else:
                    out.append(f"〔缺译：id {cid}〕")
                    n_untranslated += 1
                n_lines += 1

            # 选项只挂在**选择场景**上。做卡单元的 state 同样以 `_sel` 结尾
            # （34 个 scene 对 34 个 card），但那里玩家是在做这张选择卡，按钮
            # 没有出现过——列在那儿等于谎报选择发生的位置。
            state = str(u.get("state") or "")
            if state.endswith("_sel") and u.get("unit_kind") == "scene":
                picks = self.options.get(state)
                if picks:
                    short = (self.button_counts.get(state) or 0) - len(picks)
                    tail = f"（另 {short} 项按钮文本未核验）" if short > 0 else ""
                    out.append("〔本场选项〕" + "／".join(picks) + tail)
                    if short > 0:
                        n_sel_partial += 1
                else:
                    n_sel_missing += 1

            m = re.fullmatch(r"snr_crd_(\d+)", u.get("src") or "")
            if m:
                used_cards.add(int(m.group(1)))
                if self._card_face(int(m.group(1)), out):
                    n_faces += 1

        offroute = sorted(set(self.cards) - used_cards)
        for n in offroute:
            c = self.cards[n]
            out.append(f"\n### 卡 {n}『{c.get('title_zh') or ''}』（编外卡，不在路线上）")
            self._card_face(n, out, heading=False)

        self.text = "\n".join(out).rstrip() + "\n"
        self.stats = {
            "units": sum(1 for u in self.reader.units if u["type"] == "unit"),
            "chapter_runs": n_runs, "lines": n_lines,
            "untranslated": n_untranslated, "card_faces": n_faces,
            "offroute_cards": len(offroute),
            "sel_units_without_options": n_sel_missing,
            "sel_units_partial_options": n_sel_partial,
            "chars": len(self.text),
        }

    def _card_face(self, n: int, out: list, heading=True) -> bool:
        """卡面梗概正文追加到 `out`。原卡正文为空的两张（卡 94、卡 144，卡面
        只有标题）不写空块——但仍算作"这张卡到过场"，故返回值只反映是否真有
        正文（实测 196 张里 194 张有正文，路线内 193 张 + 编外卡 200）。"""
        body = (self.cards.get(n) or {}).get("body_zh") or ""
        if not body.strip():
            return False
        if heading:
            out.append("〔卡面梗概〕")
        out.extend(body.splitlines())
        return True

    def render(self) -> str:
        return self.text


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="通读导出：把全书最终译文按正典路线序摊成一份纯文本"
                    "（每条译文一行，无原文/提案/批注），供长上下文模型一次读完")
    ap.add_argument("--repo", default=None, help="仓库根（省略用本仓库；测试传 tmp_path）")
    ap.add_argument("--lane", default=DEFAULT_LANE,
                    help=f"车道目录（相对仓库根），默认 {DEFAULT_LANE}")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help=f"输出文件，`-` 走 stdout，默认 {DEFAULT_OUT}")
    args = ap.parse_args(argv)

    exp = Exporter(repo=args.repo, lane=args.lane)
    if args.out == "-":
        sys.stdout.write(exp.text)
    else:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(exp.text, encoding="utf-8")

    s = exp.stats
    where = "stdout" if args.out == "-" else args.out
    print(f"通读导出 → {where}：车道 {exp.lane_label}，"
          f"{s['units']} 个单元 / {s['chapter_runs']} 个章段 / {s['lines']} 行 / "
          f"{s['chars']} 字符；卡面梗概 {s['card_faces']} 张"
          f"（编外 {s['offroute_cards']} 张）", file=sys.stderr)
    if s["untranslated"]:
        print(f"!! 告警：{s['untranslated']} 行未译，已写成〔缺译：id N〕占位",
              file=sys.stderr)
    if s["sel_units_without_options"] or s["sel_units_partial_options"]:
        print(f"   选择节点：{s['sel_units_without_options']} 个无人工核验的按钮译文"
              f"（未输出〔本场选项〕行）、{s['sel_units_partial_options']} 个只核验了"
              f"一部分（行尾已注明还缺几项）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
