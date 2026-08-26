"""通读 Web UI：按**正典路线序**从头到尾看全书原文与当前落盘译文（只读）。

与 `tools/adjudicate_server.py` 的关系：那一份是**逐条裁决**用的，视野被段的
候选队列框住（只看得见"有人提过改动"的那几百行）；本工具正相反——它不裁决、
不写任何文件，只把**全书 16749 行**按玩家实际经历的顺序摊开给人读。

## 行序取 `data/timeline.jsonl`，不是 id 序也不是批序

「从新游戏开局玩到通关、沿途每条文本恰好出现一次」这条线是 `config/route_plan.yaml`
（人工资产）经 `tools/gen_timeline.py` 展开出来的，产物即 `data/timeline.jsonl`：
533 条记录，`type=unit` 的 457 条各带一串 `ids`（该演出单元内的 vms 顺序），
`type=marker` 的 76 条是「讲述指针回溯至 X、本次改选第 N 项」这类路线标记
——它们本身没有文本，但**是路线叙事的一部分**，照样按 seq 穿插显示。

id 序（1..17220）是脚本里的登记序，与玩家看到的顺序毫无关系；批序（batches.jsonl）
是翻译作业的切分，也不是路线序。要读出"故事读起来对不对"，只有 timeline 这一条序
说得通。

## 未被路线覆盖的 56 行

`timeline` 覆盖 16693 行，恰是 ledger 里 `kind=narrative` 的全部；余下 56 行是
`kind=ambient`（环境/系统串，不在任何演出单元内）。它们**不丢**——挂在路线末尾的
附录单元里，否则"从头到尾显示所有行"就是假的。

## 每行能看到什么

| 层 | 来源 |
|---|---|
| 原文 | `data/ledger.jsonl`（jp、语音 id、所属 lua 文件/函数） |
| 现行译文 | `<lane>/data/` 的 `forward.jsonl` + `patches.jsonl` 经 `resolve.resolve_map` |
| 首译 | `forward.jsonl` 的 zh（P3 产物，带 backend/model/glossary_v/ts） |
| 修订史 | 该 id 的全部 patch，逐条给 reason/glossary_v/ts/prov（哪个通道、哪个段） |
| 人裁批注 | `pilot/polish/*/decisions.jsonl` 里该 id 的 note/reason_code |

## 写：只写一处草稿，永不碰生产

本模块**唯一的写盘出口**是 `append_edit()`，且只写
`pilot/read-edits/<lane>.draft.jsonl`（append-only，同 id 取最后一条）。
生产车道的 `patches.jsonl` 由**另一个显式步骤** `tools/read_commit.py` 清关
——沿用本项目「保税仓 + 唯一清关口」的既有纪律（见 `polish_commit` 模块
docstring 的 2026-08-02 事故）：读的人一边读一边改，改动先落草稿，
要不要进生产是另一个决定、由另一条命令做，且默认 dry-run。

编辑框**原样保存**（不 trim 内部空白、不清洗、不拒收），但会**同时给出机械
体检**（`check_edit()`）并显示在界面上——不阻断。这与裁决 UI 的口径不同，
理由是那边的编辑框可能写着给主控会话的批注，这边写的就是最终译文本身；
而实测里人手改出来的缺陷（多敲的「编」字前缀、尾随换行、新增原文没有的
`『』`）都属于"当场就能看见、事后要靠闸才抓得到"那一类。
"""
import argparse
import difflib
import json
import re
import socket
import socketserver
import sys
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, read_jsonl
from tools.resolve import resolve_map

UI_DIR = Path(__file__).resolve().parent / "read_ui"
#: 人工修改草稿的目录（相对仓库根）。与 `pilot/polish/<seg>/decisions.draft.jsonl`
#: 同一性质：未清关的人工产物，入库跟踪，由显式命令清进生产。
EDITS_DIR = "pilot/read-edits"
DRAFT_SUFFIX = ".draft.jsonl"
STATIC = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js"}
DEFAULT_LANE = "pilot/lanes/opus"
#: 附录单元的 seq——排在全部路线单元之后，容纳 timeline 未覆盖的 ambient 行。
APPENDIX_SEQ = 10 ** 6


#: v19 修订一（C1）的片假名→罗马音改名表，长者优先。后半段那些残片
#: （ユウイ／イチ／ノ／チ…）来自断名、拖长音、结巴行——`アヤ……ノ`→`Aya……no`
#: 这类，diff 会把名字切成两段，只有连音节一起收进来才认得出。
C1_NAMES = [
    ("ユウイチ", "Yuichi"), ("サクラコ", "Sakurako"), ("アヤノ", "Ayano"),
    ("サクラ", "Sakura"), ("ユカリ", "Yukari"), ("ユキノ", "Yukino"),
    ("ナオヤ", "Naoya"), ("チアキ", "Chiaki"), ("さくら", "sakura"),
    ("ユウイ", "Yui"), ("ヤノ", "yano"), ("キノ", "kino"), ("アヤ", "Aya"),
    ("ユウ", "Yu"), ("イチ", "ichi"), ("ノ", "no"), ("チ", "chi"),
    ("ヤ", "ya"), ("ユ", "Yu"), ("ア", "A"),
]


def _c1_sub(s: str) -> str:
    for k, v in C1_NAMES:
        s = s.replace(k, v)
    return s


def is_c1_rename(prev: str, zh: str) -> bool:
    """这一步修订**是否只是**把故事层片假名人名换成了罗马音（v19 C1）。

    为什么要它：C1 是一次机械的全库改名，`patches.jsonl` 里 8737 步修订中有
    **4825 步（55%）**只干了这一件事。通读时逐行摊开修订史，这些步会把真正
    值得看的改动（取义、搭配、口径）淹掉。

    判据刻意**保守**——按 diff 的每一段变化逐段核：某一步里只要有**一处**变化
    不能由改名表解释，整步就照常显示。误判方向因此只会是"多显示一步机械改名"
    （无害），不会是"藏起一处真改动"（那才是这道判断唯一会造成的伤害）。

    实测这条方向是对的：全库有 6 步「片假名消失了、但不止改名」——如
    `1430` 的 `アヤノ→彩野`（故事层滑到现实层）、`7865` 的 `ユウイチ→他`
    （改成代词）、`715` 的 `是片假名→写法跟我不一样`（元话语位改写）——
    这 6 步全部**未**被判为纯改名，照常显示。
    """
    if prev == zh or not prev or not zh:
        return False
    ops = [o for o in difflib.SequenceMatcher(None, prev, zh).get_opcodes()
           if o[0] != "equal"]
    return bool(ops) and all(_c1_sub(prev[i1:i2]) == zh[j1:j2]
                             for _, i1, i2, j1, j2 in ops)


def _lane_dir(repo: Path, lane: str) -> Path:
    p = Path(lane)
    return p if p.is_absolute() else repo / p


def _lane_slug(lane: str) -> str:
    return Path(lane).name or Path(lane).parent.name


def edits_path(repo, lane: str) -> Path:
    return Path(repo) / EDITS_DIR / (_lane_slug(lane) + DRAFT_SUFFIX)


def append_edit(path, rec: dict) -> None:
    """**本模块唯一的写盘函数**。文件名不以 `.draft.jsonl` 结尾就拒写。

    断言放在真正 `open()` 的这一层，而不是算路径的 `edits_path()` 里——
    算路径的函数只要还拼着后缀，校验它自己的产物就永远为真，那是一句恒真的
    断言，比没有断言更糟（它看着像有保护）。放在这里，以后任何新增的调用点、
    任何把路径参数化的改动，都必须过这一关。同 `adjudicate_server.append_draft`。
    """
    p = Path(path)
    if not p.name.endswith(DRAFT_SUFFIX):
        raise AssertionError(f"拒绝写非草稿文件：{p}（本服务只准写 *{DRAFT_SUFFIX}）")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_edits(path) -> dict:
    """→ `{id: 最后一条编辑记录}`。append-only：同 id 后写覆盖先写。"""
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for r in read_jsonl(p):
        if r.get("id"):
            out[r["id"]] = r
    return out


_RUBY_RE = re.compile(r"<([^,>]+),([^>]+)>")
_SPK_RE = re.compile(r"^【([^】]*)】")
_MARKS = "「」『』≪≫≦≧"


def check_edit(jp: str, old_zh: str, new_zh: str) -> list:
    """人工改动的**机械体检**（顾问级，不阻断）→ 一串人话警告。

    每一条都对应一次真实翻过的车：
    - 首尾空白：`8872` 的编辑带了个尾随换行，一路落到车道才被发现；
    - 说话人前缀：`14987` 的编辑多敲进一个「编」字（`编【Yuichi】…`），
      是段末闸而不是当场发现的；
    - **新增原文没有的 `『』`**：`『』` 在本作是卡名／场面名的专用壳，正文里
      新增会被读成卡名（SEG-1 的 `2810`）。注意 `「」` 不在此列——SEG-4 已
      裁定 `参ったなあ` 处可以有意新增 `「」`；
    - `_n`/`_r` 计数：控制码是引擎的换行，多一个少一个都改版式；
    - ruby 良构与不该丢：日文注音去掉、中文拼音新增都是既定口径，所以**不与
      原文比数量**，只查括号是否成对良构、以及旧译有 ruby 而新译没有；
    - 「小千秋」：v19 已废止的形。
    """
    w = []
    if new_zh != new_zh.strip():
        w.append("首尾有空白／换行——会原样落进 lua 字符串")
    for k in ("_n", "_r"):
        if jp.count(k) != new_zh.count(k):
            w.append(f"控制码 {k} 数量与原文不符（原文 {jp.count(k)}，你写了 {new_zh.count(k)}）")
    # 说话人前缀查三件事，缺一漏一种真实事故：
    #   **有没有**——对着原文（jp 有【】译文就得有，反之亦然）。只比旧译会漏掉
    #     「原文本来没有说话人、译文却凭空多出一个」；
    #   **在不在行首**——`14987` 的编辑写成 `编【Yuichi】…`，多敲进一个字，
    #     两边都"有"【】、名字也没变，只有位置能看出来；
    #   **是谁**——对着旧译（名字是译过的，跟 jp 比不了内容）。
    a, b = _SPK_RE.match(old_zh or ""), _SPK_RE.match(new_zh)
    jp_has, new_has = "【" in jp, "【" in new_zh
    if jp_has != new_has:
        w.append("说话人前缀的有无与原文不符"
                 f"（原文{'有' if jp_has else '没有'}【】，你{'写了' if new_has else '没写'}）")
    elif jp_has and not b:
        w.append("说话人前缀不在行首——前面是不是多敲了字符？")
    elif b and (a.group(1) if a else None) != b.group(1):
        w.append(f"说话人前缀变了：{a.group(0) if a else '（无）'} → {b.group(0)}")
    for ch in _MARKS:
        if jp.count(ch) != new_zh.count(ch):
            extra = "——`『』` 是卡名／场面名的专用壳，正文新增会被读成卡名" if ch in "『』" else ""
            w.append(f"记号 {ch} 数量与原文不符（原文 {jp.count(ch)}，你写了 {new_zh.count(ch)}）{extra}")
    if new_zh.count("<") != new_zh.count(">") or len(_RUBY_RE.findall(new_zh)) * 2 != (
            new_zh.count("<") + new_zh.count(">")):
        w.append("ruby 括号不成对或不良构（应形如 `<汉字,pīn yīn>`）")
    if _RUBY_RE.findall(old_zh or "") and not _RUBY_RE.findall(new_zh):
        w.append("旧译里的 ruby 注音在新译里没有了")
    if "小千秋" in new_zh:
        w.append("含「小千秋」——v19 已废止，现行是对白「千秋酱」／旁白「千秋」")
    return w


class Reader:
    """把「路线序 + 原文 + 现行译文 + 修订史 + 人裁批注」装配成可分单元取用的模型。

    构造时一次性读完所有数据并建索引（全书 16749 行、8000+ patch、3000+ 决策，
    合计几十 MB，一次读完远比每个请求重读划算）；此后每个 `/api/unit` 只在自己
    那一串 id 上做查表。
    """

    def __init__(self, repo=None, lane=DEFAULT_LANE):
        self.repo = Path(repo) if repo is not None else REPO
        self.lane = _lane_dir(self.repo, lane)
        self.lane_label = lane

        data = self.lane / "data"
        self.ledger = {r["id"]: r for r in read_jsonl(self.repo / "data" / "ledger.jsonl")}
        fwd_rows = read_jsonl(data / "forward.jsonl")
        pat_rows = read_jsonl(data / "patches.jsonl")
        self.forward = {r["id"]: r for r in fwd_rows}
        self.current = resolve_map(fwd_rows, pat_rows)

        # id → 该 id 的全部 patch（按文件顺序，即时间顺序）
        self.patches = defaultdict(list)
        for r in pat_rows:
            self.patches[r["id"]].append(r)

        # id → 各段的人裁记录（append-only，同段同 id 可能多条；全部保留，
        # 因为"改判过"本身就是读者想看到的信息）
        self.decisions = defaultdict(list)
        for p in sorted((self.repo / "pilot" / "polish").glob("*/decisions.jsonl")):
            seg = p.parent.name
            for r in read_jsonl(p):
                if r.get("id"):
                    self.decisions[r["id"]].append({**r, "seg": seg})

        self.edits_path = edits_path(self.repo, lane)
        self.edits = load_edits(self.edits_path)

        self.units, self.by_seq = self._build_units()

    # ---- 路线装配 ----

    def _card_titles(self) -> dict:
        """卡号 → 中文卡名（`skeleton/cards.zh.yaml`）。

        为什么要它：`timeline` 里 `unit_kind=script` 的单元（59 个，多是 crd 卡面
        stub）与 `fscene`（11 个现实层整章）**没有场景标题**，`title` 字段退化成了
        lua 文件名（`snr_crd_1`／`snr_s2_10_f`）。目录里排着一串文件名读不出是
        什么——而卡面本来就有人话名字，取来用即可。读不到骨架文件就退回文件名，
        不因为一个装饰性字段让工具起不来。
        """
        p = self.repo / "skeleton" / "cards.zh.yaml"
        if not p.exists():
            return {}
        try:
            import yaml
            rows = yaml.safe_load(p.read_text(encoding="utf-8")) or []
        except Exception:
            return {}
        return {r["card"]: r.get("title_zh") for r in rows
                if isinstance(r, dict) and r.get("card") is not None}

    def _titles(self, r: dict, cards: dict) -> tuple:
        """→ (显示标题, 中文副题)。

        `timeline` 给的 `title` 是**日文**的场景名／卡名（与游戏内一致，是正名，
        所以留作主标题）。两处补充：
        - `unit_kind=card`／`script` 的单元 src 形如 `snr_crd_N`，骨架里有该卡的
          中文定稿名——挂成副题，本地化审读时一眼对得上；
        - `script`／`fscene` 的单元**没有场景名**，`title` 退化成 lua 文件名
          （59 + 11 个，目录里排一串文件名读不出是什么）——给它们配一个人话标题。
        """
        title, src = r.get("title"), r.get("src") or ""
        m = re.fullmatch(r"snr_crd_(\d+)", src)
        card_zh = cards.get(int(m.group(1))) if m else None
        if title and title != src:
            return title, (card_zh if card_zh and card_zh != title else None)
        if m:
            n = int(m.group(1))
            return (f"卡 {n}『{card_zh}』" if card_zh else f"卡 {n}"), None
        m2 = re.fullmatch(r"snr_(s\d|e\d)_10_(f[a-z]?)", src)
        if m2:
            return f"{m2.group(1)} 现实层（{m2.group(2)}）", None
        return (title or src), None

    def _build_units(self):
        rows = read_jsonl(self.repo / "data" / "timeline.jsonl")
        cards = self._card_titles()
        units, seen = [], set()
        for r in rows:
            if r.get("type") == "marker":
                units.append({"seq": r["seq"], "type": "marker",
                              "text": r.get("text", ""), "recap": r.get("recap", ""),
                              "n_lines": 0})
                continue
            ids = [i for i in r.get("ids", []) if i in self.ledger]
            seen.update(ids)
            units.append({
                "seq": r["seq"], "type": "unit", "unit_kind": r.get("unit_kind"),
                "src": r.get("src"), "state": r.get("state"),
                "title": self._titles(r, cards)[0],
                "title_zh": self._titles(r, cards)[1],
                "chapter": (self.ledger[ids[0]].get("chapter") if ids else None),
                "n_lines": len(ids), "ids": ids,
            })
        # 路线没覆盖到的行（ambient 轨）挂成附录，否则"从头到尾"是假的
        rest = [i for i in sorted(self.ledger) if i not in seen]
        if rest:
            units.append({
                "seq": APPENDIX_SEQ, "type": "unit", "unit_kind": "appendix",
                "src": "（不在正典路线上）", "state": "appendix",
                "title": f"附录：路线未覆盖的 {len(rest)} 行（ambient 轨）",
                "chapter": "sys", "n_lines": len(rest), "ids": rest,
            })
        return units, {u["seq"]: u for u in units}

    # ---- 载荷 ----

    def outline_payload(self) -> dict:
        """左边栏用的目录：不带 ids，避免把 16693 个整数塞进第一屏。"""
        return {
            "lane": self.lane_label,
            "total_lines": sum(u["n_lines"] for u in self.units),
            "ledger_lines": len(self.ledger),
            "units": [{k: v for k, v in u.items() if k != "ids"} for u in self.units],
        }

    def _line_payload(self, cid: int) -> dict:
        led = self.ledger[cid]
        fwd = self.forward.get(cid, {})
        pats = self.patches.get(cid, [])
        zh = self.current.get(cid, "")
        first = fwd.get("zh", "")
        history = []
        prev = first
        for p in pats:
            cur_zh = p.get("zh", "")
            history.append({
                "zh": cur_zh, "prev": prev, "reason": p.get("reason"),
                "glossary_v": p.get("glossary_v"), "ts": p.get("ts"),
                "prov": p.get("prov") or None,
                # 前端默认折叠这一步（v19 C1 机械改名），但**仍然计数**——
                # 藏起来不算数就成了假的修订史
                "c1_rename": is_c1_rename(prev, cur_zh),
            })
            prev = cur_zh
        return {
            "id": cid, "jp": led.get("jp", ""), "zh": zh,
            "voice": led.get("voice"), "file": led.get("file"), "func": led.get("func"),
            "chapter": led.get("chapter"), "kind": led.get("kind"),
            "first_zh": first,
            "first_meta": ({"model": fwd.get("model"), "backend": fwd.get("backend"),
                            "glossary_v": fwd.get("glossary_v"), "ts": fwd.get("ts"),
                            "batch": fwd.get("batch")} if fwd else None),
            "history": history,
            "c1_hidden": sum(1 for h in history if h["c1_rename"]),
            "revised": bool(pats),
            "pending": self._pending_payload(cid, led.get("jp", ""), zh),
            "decisions": [
                {"seg": d["seg"], "verdict": d.get("verdict"),
                 "chosen_channel": d.get("chosen_channel"),
                 "reason_code": d.get("reason_code") or "",
                 "note": (d.get("note") or "").strip(), "ts": d.get("ts")}
                for d in self.decisions.get(cid, [])
            ],
        }

    def _pending_payload(self, cid, jp, zh):
        """该行是否有**未清关**的人工修改。`stale=True` 表示草稿记下的"改动前
        文本"与车道现值已经对不上——多半是这行在你改完之后又被别处动过，
        清关前要重看一眼。"""
        e = self.edits.get(cid)
        if not e:
            return None
        return {
            "zh": e.get("zh", ""), "note": (e.get("note") or "").strip(),
            "ts": e.get("ts"), "base_zh": e.get("base_zh", ""),
            "stale": e.get("base_zh", "") != zh,
            "warnings": check_edit(jp, zh, e.get("zh", "")),
        }

    def record_edit(self, payload: dict) -> dict:
        """收一条人工修改，落草稿。**原样保存**——不 trim、不清洗、不拒收，
        只把机械体检的结果一并回给前端显示（见模块 docstring）。"""
        cid = payload.get("id")
        if not isinstance(cid, int) or cid not in self.ledger:
            raise ValueError(f"id 不在 ledger 里：{cid!r}")
        zh = payload.get("zh")
        if not isinstance(zh, str):
            raise ValueError("zh 必须是字符串")
        rec = {
            "id": cid, "zh": zh, "note": payload.get("note") or "",
            "base_zh": self.current.get(cid, ""),
            "jp": self.ledger[cid].get("jp", ""),
            "lane": self.lane_label,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        append_edit(self.edits_path, rec)
        self.edits[cid] = rec
        return {"record": rec,
                "warnings": check_edit(rec["jp"], rec["base_zh"], zh),
                "pending_total": len(self.edits)}

    def pending_payload(self) -> dict:
        """全部未清关的修改，按路线序——给"只看改过的"那个视图用。"""
        seq_of = {}
        for u in self.units:
            for i in u.get("ids", ()):
                seq_of[i] = u["seq"]
        rows = []
        for cid in sorted(self.edits, key=lambda i: (seq_of.get(i, 10 ** 9), i)):
            e = self.edits[cid]
            rows.append({"id": cid, "seq": seq_of.get(cid), "zh": e.get("zh", ""),
                         "base_zh": e.get("base_zh", ""), "note": (e.get("note") or "").strip(),
                         "ts": e.get("ts"),
                         "stale": e.get("base_zh", "") != self.current.get(cid, "")})
        return {"path": str(self.edits_path), "total": len(rows), "rows": rows}

    def unit_payload(self, seq: int) -> dict:
        u = self.by_seq[seq]
        out = {k: v for k, v in u.items() if k != "ids"}
        out["lines"] = [self._line_payload(i) for i in u.get("ids", [])]
        order = [x["seq"] for x in self.units]
        i = order.index(seq)
        out["prev_seq"] = order[i - 1] if i > 0 else None
        out["next_seq"] = order[i + 1] if i + 1 < len(order) else None
        return out

    def search(self, q: str, limit=200) -> dict:
        """原文与译文的朴素子串搜索。

        16749 行的全表扫描在本机是毫秒级，不值得为它建倒排索引——真要建，还得
        考虑中日文分词，那是另一件事。命中超过 `limit` 就截断并**明说截断了**
        （`truncated` 字段），不假装搜全了。
        """
        q = (q or "").strip()
        if not q:
            return {"q": q, "hits": [], "truncated": False}
        seq_of = {}
        for u in self.units:
            for i in u.get("ids", []):
                seq_of[i] = u["seq"]
        hits = []
        for u in self.units:
            for cid in u.get("ids", []):
                jp = self.ledger[cid].get("jp", "")
                zh = self.current.get(cid, "")
                where = ("原文" if q in jp else "") + ("译文" if q in zh else "")
                if not where:
                    continue
                if len(hits) >= limit:
                    return {"q": q, "hits": hits, "truncated": True}
                hits.append({"id": cid, "seq": u["seq"], "title": u.get("title"),
                             "jp": jp, "zh": zh, "where": where})
        return {"q": q, "hits": hits, "truncated": False}

    def locate(self, cid: int):
        """id → 它所在单元的 seq（跳转用）。不在任何单元里返回 None。"""
        for u in self.units:
            if cid in u.get("ids", ()):
                return u["seq"]
        return None


class Server(ThreadingHTTPServer):
    """同 `adjudicate_server.Server`：绕开 `server_bind()` 里的 `socket.getfqdn()`
    反向 DNS（macOS 上实测卡 35 秒），`server_name` 本服务用不到。"""
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


def make_handler(model: Reader):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ZndRead/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _err(self, code, msg):
            self._json({"error": msg}, code)

        def do_GET(self):
            u = urlparse(self.path)
            path, q = u.path, parse_qs(u.query)
            if path in STATIC:
                f = UI_DIR / STATIC[path]
                if not f.exists():
                    return self._err(500, f"缺静态文件：{f}")
                ctype = ("text/html; charset=utf-8" if f.suffix == ".html" else
                         "text/css; charset=utf-8" if f.suffix == ".css" else
                         "application/javascript; charset=utf-8")
                return self._send(200, f.read_bytes(), ctype)
            if path == "/api/outline":
                return self._json(model.outline_payload())
            if path == "/api/unit":
                raw = (q.get("seq") or [""])[0]
                try:
                    seq = int(raw)
                except ValueError:
                    return self._err(400, f"seq 不是整数：{raw!r}")
                try:
                    return self._json(model.unit_payload(seq))
                except KeyError:
                    return self._err(404, f"没有 seq={seq} 这个单元")
            if path == "/api/search":
                return self._json(model.search((q.get("q") or [""])[0]))
            if path == "/api/pending":
                return self._json(model.pending_payload())
            if path == "/api/locate":
                raw = (q.get("id") or [""])[0]
                try:
                    cid = int(raw)
                except ValueError:
                    return self._err(400, f"id 不是整数：{raw!r}")
                seq = model.locate(cid)
                if seq is None:
                    return self._err(404, f"id {cid} 不在任何单元里")
                return self._json({"id": cid, "seq": seq})
            return self._err(404, f"没有这个端点：{path}")

        def do_HEAD(self):
            self.do_GET()

        def do_POST(self):
            # 唯一的写路径：落草稿。生产车道由 tools/read_commit.py 另行清关。
            if urlparse(self.path).path != "/api/edit":
                return self._err(404, f"没有这个端点：{self.path}")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception as e:
                return self._err(400, f"请求体不是合法 JSON：{e}")
            try:
                return self._json({"ok": True, **model.record_edit(payload)})
            except ValueError as e:
                return self._err(400, str(e))

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="通读 Web UI：按正典路线序看全书原文与当前落盘译文（**只读**，不写任何文件）")
    ap.add_argument("--repo", default=None, help="仓库根（省略用本仓库；测试传 tmp_path）")
    ap.add_argument("--lane", default=DEFAULT_LANE,
                    help=f"车道目录（相对仓库根），默认 {DEFAULT_LANE}")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    ap.add_argument("--port", type=int, default=8789,
                    help="监听端口，默认 8789（裁决 UI 用 8788，刻意错开以便同时开着）")
    args = ap.parse_args(argv)

    model = Reader(repo=args.repo, lane=args.lane)
    httpd = Server((args.host, args.port), make_handler(model))
    n_units = sum(1 for u in model.units if u["type"] == "unit")
    shown = "、".join(f"{host}:{args.port}" for host in
                      dict.fromkeys(["127.0.0.1", socket.gethostbyname(socket.gethostname())]))
    print(f"通读 UI：车道 {model.lane_label}，{n_units} 个演出单元 / "
          f"{sum(u['n_lines'] for u in model.units)} 行（ledger 共 {len(model.ledger)} 行）")
    print(f"打开：http://{shown.split('、')[0]}/    （Ctrl-C 退出）")
    print(f"人工修改只写草稿：{model.edits_path}"
          f"（现有 {len(model.edits)} 条）；进生产用 tools/read_commit.py")
    if len(shown.split("、")) > 1:
        print(f"局域网：http://{shown.split('、')[1]}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
