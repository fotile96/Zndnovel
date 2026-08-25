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

**只读**：本模块不写仓库任何文件。没有 POST 端点。
"""
import argparse
import difflib
import json
import re
import socket
import socketserver
import sys
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, read_jsonl
from tools.resolve import resolve_map

UI_DIR = Path(__file__).resolve().parent / "read_ui"
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
            "decisions": [
                {"seg": d["seg"], "verdict": d.get("verdict"),
                 "chosen_channel": d.get("chosen_channel"),
                 "reason_code": d.get("reason_code") or "",
                 "note": (d.get("note") or "").strip(), "ts": d.get("ts")}
                for d in self.decisions.get(cid, [])
            ],
        }

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
    print(f"打开：http://{shown.split('、')[0]}/    （只读，不写任何文件；Ctrl-C 退出）")
    if len(shown.split("、")) > 1:
        print(f"局域网：http://{shown.split('、')[1]}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
