"""P5 逐条裁决 Web UI 的本地服务端——人工裁决阶段的"对读台"。

规格见 `docs/ops/p5-adjudicate-ui-spec.md`（唯一需求源）。一句话：左边栏是
待裁队列，右主体等分两栏对照**日文原文**与**最新落盘译文**（各带前文上下
文、逐行对齐），各通道提案摆在右栏当前行正下方，人做出选择后自动跳下一条。

## 只写一处：`decisions.draft.jsonl`（拍板第 1 条）

本服务对仓库**只读**，唯一的写口是 `pilot/polish/<seg>/decisions.draft.jsonl`。
`decisions.jsonl` / `patches.jsonl` / `candidates.*.jsonl` / `frozen/` 一律
不碰——草稿由主控会话事后检查再落盘。全模块只有 `append_draft()` 一个函数
会 open 写模式，它进门先硬校验文件名就是 `decisions.draft.jsonl`，别的路径
直接抛异常。这道断言看着多余，但它是"绝不写生产文件"这条约束在代码里唯一
的物理保证，改动本文件时不要把它优化掉、也不要绕过它另开写口。

**草稿 verdict 与生产 `decisions.jsonl` 同词汇**：`adopt`（采纳某通道；采纳它
的第 N 条备选时同为 `adopt`，另带 `chosen_alt=N`）、`keep_opus`（保留现译）、
`edit`（人工改写）。规格初稿曾另立 `adopt_alt`/`keep` 两个值，是写规格时的疏忽
——`polish_commit` 的采纳路径本就用 `adopt` + `chosen_alt` 表达备选，而"保留现译"
在既有 8 段台账里一律记 `keep_opus`。**源头对齐、不留映射层**：映射层意味着草稿
与落盘之间有一道人肉翻译，正是本项目反复吃亏的形态。

## 自选行：队列之外的行也能改（2026-08-19 用户追加需求）

队列只收「有通道提案的行」（本段 4282 行里的 381 行）。但人在读上下文时经常
会看见**一条谁都没提案、自己却想改**的行——P4 全程反复发生。故本服务把
"可处理的 id" 放宽到**整个段**（`frozen/source.jsonl` 的全部 id），队列只是
其中"机器认为需要人看"的子集：

- `item_payload()` 接受段内任意 id；不在队列里的记 `in_queue=false`。
- 这类行**没有提案可采纳**，动作集只有 `edit` / `keep_opus`；`record()` 会
  直接拒掉对非队列行的 `adopt`（服务端硬拒，不只靠前端不画按钮——草稿是要
  落进生产 patch 的，一条指向不存在提案的 adopt 记录会在 polish_commit 那边
  变成一句"找不到候选，跳过"的静默丢失）。
- 左栏只列**已经裁决过的**自选行（草稿里有记录才出现）。不这么收窄的话，
  4282 行会把 381 条队列彻底淹掉——队列的价值就在于它是个短名单。
- 计数分开报：`total`/`done` 永远只算队列，自选行单独计 `picked`。把两者
  混进一个分母会让"队列还剩多少"这个唯一有意义的进度失真。
- 裁完一条自选行，`next_undecided()` **回到队列**里、按阅读顺序在它后面的
  第一条未处理项（不是沿着 4282 行往下走）——自选行是插曲，主线仍是队列。

## 敲定文本：右栏显示的是"裁决之后这一行会变成什么"（2026-08-19 用户追加需求）

右栏原本一律显示车道最新译文（`resolve_map`）。但人一旦裁过某一行，那一行
**将要落盘的文字**就已经变了；再往下读时上下文里还显示旧文本，等于对着自己
已经推翻的版本在读——连续裁相邻行、判段级衔接（密度/前后呼应）时会直接误导。

故右栏每一行的显示文本改为 `settled(id)`：草稿里有该 id 的裁决就用敲定文本，
没有就回落车道最新。解析规则（`resolve_settled()`）：
`adopt` 无 `chosen_alt` → 该通道候选的 `zh`；带 `chosen_alt=N` → `alts[N-1].zh`
（1-based，与 queue.md 的「备选N」和 polish_commit 同一口径）；`edit` →
`edited_zh` **原样**（可能压根不是译文，见拍板第 4 条）；`keep_opus` → 车道最新
（文本不变，但仍标记为"已裁·保留"，让人知道这行看过了）。同 id 取最后一条。

三条不变量：
1. **`zh_current`（车道最新）永不被顶掉**——漂移警告和"原文/现译对照"还要用它；
   敲定文本是**另加**一层（`zh_display` / 行内 `zh` 显示的是它，`zh_lane` 留着）。
2. **不缓存**。敲定文本每次请求现算（`decisions()` 本来就是现读文件），否则改判
   后别的条目的上下文视图会留着旧值——那正是本需求要消灭的东西。
3. **解析不出来时回落车道文本并显式播报 `problem`**，绝不静默：草稿是可手工
   编辑的、候选文件也可能在两次启动之间变过，一条 `adopt` 完全可能指向一个
   已经不存在的通道/越界的备选号。悄悄显示成别的文本比报错危险得多。

## 队列直读 candidates.*.jsonl 自算（拍板第 3 条）

不读 `triage.json` / `queue.md`：那两者要先跑 triage，且桶 2 受 K 配额截断，
"没进 K 名额"的提案会看不见——而人工对读阶段要的是**全部有话要说的行**。
故本服务直接扫 `candidates.*.jsonl`，通道名从文件名解出，新通道补齐候选后
重启服务即自动纳入，不需要改代码。同 id 取**最后一条**（候选文件 append-only）。

进队判据（满足任一）：
1. `zh.strip() != frozen_opus[id].strip()`——提了改动；
2. `adjudicate == true`——显式请裁，哪怕逐字没改（这类行的价值全在 note 里，
   被"零改动"判据吞掉正是 P4 D3 缺陷的形态，见 polish_triage 模块 docstring）；
3. `alts` 非空——给了备选，即便主候选没改也要让人看见备选。

排序按**阅读顺序**（`data/batches.jsonl` 中 `lane=="main"` 的批按 batch 升序、
批内按 ids 原序），不是 id 数值序——id 是脚本内的登记序号，跳着走，按它排
会让上下文对读完全失效。

## 右栏显示的是车道最新，不是冻结面

候选是对着 `frozen/opus.jsonl` 产出的，但从冻结到现在车道可能又改过
（`patches.jsonl` 新补丁）。右栏必须显示 `tools.resolve.resolve_map()` 的结果
（= 玩家真正会看到的现行译文），否则会出现"采纳一条候选 = 悄悄回退掉冻结后
的修正"。两者不一致的行打**漂移**标记并同时显示两份文本，让人自己判。

漂移判据用「现算比对」而非只读 `lane_drift.json`：右栏本来就同时持有冻结面
与车道最新两张表，现算永不过期；`lane_drift.json` 的结论仍然**并入**（取并集）
——那份文件是段末体检的正式结论，宁可多显示一条已经消失的旧警告（届时两份
文本会显示成一样，人一眼看得出），也不能漏掉一条。

## 手工编辑框原样保存（拍板第 4 条）

编辑框内容**可能不是纯译文**：用户可能写得松散、附批注给主控会话、或写
"这条再行讨论"。故服务端对 `edited_zh` 不做任何 strip / 控制码校验 / 长度
检查——原样进 JSON。唯一的结构性要求是"它得是个字符串"，那不是内容校验。
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import socketserver
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl
from tools.resolve import resolve_map

UI_DIR = Path(__file__).resolve().parent / "adjudicate_ui"
DRAFT_NAME = "decisions.draft.jsonl"
#: 与生产 `decisions.jsonl` **完全同词汇**（2026-08-19 主控会话对齐）。
#: 规格初稿曾另立 `adopt_alt`/`keep` 两个值，是写规格时的疏忽——`polish_commit`
#: 认的是 `adopt` + `chosen_alt=N`（备选走 adopt 的同一条路径），保留现译在
#: 全部 8 段既有台账里一律记 `keep_opus`。词汇不一致会逼出一道事后映射，
#: 而映射层正是本项目反复吃亏的地方，故在源头对齐、不留映射。
VERDICTS = ("adopt", "keep_opus", "edit")
CAND_RE = re.compile(r"^candidates\.(.+)\.jsonl$")
DEFAULT_LANE = "pilot/lanes/opus"
DEFAULT_CONTEXT_BEFORE = 30
DEFAULT_CONTEXT_AFTER = 3
# 静态资源白名单：手写死这三项，不做任何路径拼接——本服务 listen 0.0.0.0，
# 一个「按 URL 拼文件名」的静态目录就是一条现成的目录穿越口子。
STATIC = {"/": "index.html", "/index.html": "index.html",
          "/app.css": "app.css", "/app.js": "app.js"}


def _ws_equal(a: str, b: str) -> bool:
    """零改动判据：只掐首尾空白，`_n`/`_r`/ruby 全部原样参与比较。

    与 `tools/polish_triage._ws_equal` 同一口径（那边的 docstring 有完整理由）：
    控制码是内容的一部分，一次纯 `_n` 位置调整**是**真实改动，不能因为剥掉
    控制码后长得一样就判成零改动、从队列里静默消失。
    """
    return (a or "").strip() == (b or "").strip()


def _draft_path(seg_dir: Path) -> Path:
    return Path(seg_dir) / DRAFT_NAME


def append_draft(path, rec: dict) -> None:
    """**本模块唯一的写盘函数**。文件名不是 `decisions.draft.jsonl` 就拒写。

    断言放在"真正 open 的那一层"而不是"算路径的那一层"：算路径的函数只要
    还拼着 DRAFT_NAME，校验它自己的产物永远为真（一句恒真的断言比没有断言
    更糟——它看着像有保护）。写在这里，任何以后新增的调用点、任何把路径参数
    化的改动，都必须过这一关。见模块 docstring「只写一处」。
    """
    p = Path(path)
    if p.name != DRAFT_NAME:
        raise AssertionError(f"拒绝写非草稿文件：{p}（本服务只准写 {DRAFT_NAME}）")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(dumps(rec) + "\n")


def load_channels(seg_dir: Path) -> dict:
    """扫 `candidates.<channel>.jsonl` → `{channel: {id: 最后一条候选行}}`。

    通道名从文件名解出（拍板第 3 条：新通道不改代码，重启即纳入）。同 id 取
    最后一条是候选文件的 append-only 语义，与 polish_triage/polish_commit 一致。
    """
    out = {}
    for p in sorted(Path(seg_dir).glob("candidates.*.jsonl")):
        m = CAND_RE.match(p.name)
        if not m:
            continue
        last = {}
        for r in read_jsonl(p):
            last[r["id"]] = r
        out[m.group(1)] = last
    return out


def reading_order(batch_rows) -> list:
    """`data/batches.jsonl` → 玩家阅读顺序的 id 列表。

    只取 `lane == "main"`：extra（图片烤字等）与 ambient 不是正文阅读流，混进
    来会把前文上下文搅乱。批按 batch 升序、批内按 ids 原序——这两条就是段表
    生成时定下的顺序，不要再排序 ids（那会把同批内的脚本顺序打乱）。
    """
    ids = []
    for r in sorted([r for r in batch_rows if r.get("lane") == "main"],
                    key=lambda r: r["batch"]):
        ids.extend(r["ids"])
    return ids


def candidate_reasons(cand: dict, frozen_zh: str) -> list:
    """一条候选的进队理由（可能多条），空列表＝这条候选没话要说。"""
    reasons = []
    if not _ws_equal(cand.get("zh", ""), frozen_zh):
        reasons.append("changed")
    if cand.get("adjudicate"):
        reasons.append("adjudicate")
    if cand.get("alts"):
        reasons.append("alts")
    return reasons


def order_key(cid, order_pos: dict, n: int):
    """阅读顺序排序键。不在阅读顺序表里的 id（理论上不该有）排到全表之后并按 id
    兜底升序，而不是被丢掉——静默丢条目是本项目反复吃亏的形态。队列排序与
    "下一条未处理项"必须用同一个键，否则两者会在这类边角 id 上错位。"""
    return order_pos.get(cid, n + (cid if isinstance(cid, int) else 0))


def build_queue(source_rows, frozen_opus: dict, channels: dict, order_pos: dict) -> list:
    """算出待裁队列（阅读顺序），每项带上"哪些通道有话说/为什么进来"。

    `order_pos` 是 `{id: 阅读序号}`，排序键见 `order_key()`。
    """
    batch_of = {r["id"]: r.get("batch") for r in source_rows}
    seg_ids = [r["id"] for r in source_rows]
    items = []
    for cid in seg_ids:
        frozen_zh = frozen_opus.get(cid, "")
        proposals, covered, reasons = [], 0, set()
        for ch in sorted(channels):
            cand = channels[ch].get(cid)
            if cand is None:
                continue
            covered += 1
            rs = candidate_reasons(cand, frozen_zh)
            if rs:
                proposals.append(ch)
                reasons.update(rs)
        if not proposals:
            continue
        items.append({
            "id": cid,
            "batch": batch_of.get(cid),
            "channels": proposals,          # 有话要说的通道
            "n_proposals": len(proposals),
            "n_covered": covered,           # 对该 id 出过候选的通道数（分母）
            "reasons": sorted(reasons),
        })
    n = len(order_pos)
    items.sort(key=lambda it: (order_key(it["id"], order_pos, n), it["id"]))
    return items


def read_draft(path) -> dict:
    """草稿 → `{id: 最后一条裁决}`。append-only，改判＝追加新行，读时后行覆盖前行。

    文件不存在＝还没裁过任何一条，返回空表（不是错误）。
    """
    p = Path(path)
    if not p.exists():
        return {}
    last = {}
    for r in read_jsonl(p):
        if isinstance(r, dict) and "id" in r:
            last[r["id"]] = r
    return last


class Adjudication:
    """一个 SEG 的全部只读数据 + 草稿读写。HTTP 层只是它的一层薄壳，便于单测。"""

    def __init__(self, seg, repo=None, lane=DEFAULT_LANE,
                 context_before=DEFAULT_CONTEXT_BEFORE,
                 context_after=DEFAULT_CONTEXT_AFTER):
        self.seg = seg
        self.repo = Path(repo) if repo is not None else REPO
        self.seg_dir = self.repo / "pilot" / "polish" / seg
        self.lane_dir = self.repo / lane
        self.context_before = int(context_before)
        self.context_after = int(context_after)
        self._lock = threading.Lock()
        self._load()

    # ---------- 装载 ----------
    def _load(self):
        d = self.seg_dir
        if not d.exists():
            raise SystemExit(f"段目录不存在：{d}")
        self.source = read_jsonl(d / "frozen" / "source.jsonl")
        # 段内全部 id → 批号。这张表定义了"本工具可以处理哪些行"：队列只是它的
        # 子集，自选行（用户从上下文里捞出来的）也必须落在这张表里——段外的 id
        # 就算写进草稿也无处可落（不属于本段的冻结面），故一律拒收。
        self.batch_of = {r["id"]: r.get("batch") for r in self.source}
        self.frozen_opus = {r["id"]: r["zh"] for r in read_jsonl(d / "frozen" / "opus.jsonl")}
        locked_p = d / "frozen" / "locked.json"
        locked = json.loads(locked_p.read_text(encoding="utf-8")) if locked_p.exists() else {}
        self.hard_ids = set(locked.get("hard_ids") or [])
        self.soft_ids = set(locked.get("soft_ids") or [])
        self.lock_why = {int(k): v for k, v in (locked.get("why") or {}).items()
                         if str(k).lstrip("-").isdigit()}
        self.channels = load_channels(d)

        batches_p = self.repo / "data" / "batches.jsonl"
        order = reading_order(read_jsonl(batches_p)) if batches_p.exists() else []
        self.order = order
        self.order_pos = {cid: i for i, cid in enumerate(order)}

        # jp 全局表：段外的前文上下文（跨段边界那几行）要靠 ledger 才拿得到；
        # 段内以 frozen/source.jsonl 为准（那是本段冻结时点的权威原文）。
        ledger_p = self.repo / "data" / "ledger.jsonl"
        self.jp = {r["id"]: r.get("jp", "") for r in read_jsonl(ledger_p)} if ledger_p.exists() else {}
        for r in self.source:
            self.jp[r["id"]] = r.get("jp", "")

        # 右栏 = 车道最新落盘译文（resolve = 补丁 ∥ 正向线），不是冻结面。
        fwd_p, pat_p = self.lane_dir / "data" / "forward.jsonl", self.lane_dir / "data" / "patches.jsonl"
        fwd = read_jsonl(fwd_p) if fwd_p.exists() else []
        pat = read_jsonl(pat_p) if pat_p.exists() else []
        self.current = resolve_map(fwd, pat)

        self.queue = build_queue(self.source, self.frozen_opus, self.channels, self.order_pos)
        self.queue_pos = {it["id"]: i for i, it in enumerate(self.queue)}
        self._queue_keys = [order_key(it["id"], self.order_pos, len(order)) for it in self.queue]
        self.drift = self._compute_drift()

    def _compute_drift(self) -> dict:
        """`{id: {"frozen": .., "current": .., "source": ..}}`——现算比对 ∪ lane_drift.json。

        见模块 docstring「右栏显示的是车道最新」：现算永不过期，正式体检结论
        并入以防漏报；`source` 字段如实记录这条警告的来路，方便人判断可信度。
        """
        found = {}
        for cid, frozen_zh in self.frozen_opus.items():
            cur = self.current.get(cid)
            if cur is not None and not _ws_equal(frozen_zh, cur):
                found[cid] = {"frozen": frozen_zh, "current": cur, "source": "compare"}
        p = self.seg_dir / "lane_drift.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            for f in data.get("findings") or []:
                cid = f.get("id")
                if cid in found:
                    found[cid]["source"] = "both"
                else:
                    found[cid] = {"frozen": f.get("frozen_zh", self.frozen_opus.get(cid, "")),
                                  "current": f.get("current_zh", self.current.get(cid, "")),
                                  "source": "lane_drift.json"}
        return found

    # ---------- 草稿 ----------
    @property
    def draft_path(self) -> Path:
        return _draft_path(self.seg_dir)

    def decisions(self) -> dict:
        """每次现读文件：草稿只有几百行，读盘代价可忽略；换来的是主控会话在
        服务运行期间手工改过草稿也能被看见，不会拿着一份过期的内存副本工作。"""
        return read_draft(self.draft_path)

    def record(self, payload: dict) -> dict:
        """把一条裁决追加进草稿。返回落盘后的完整记录。

        `edited_zh` 原样进 JSON——不 strip、不校验控制码（拍板第 4 条）。
        """
        verdict = payload.get("verdict")
        if verdict not in VERDICTS:
            raise ValueError(f"verdict 取值非法：{verdict!r}（应为 {VERDICTS} 之一）")
        cid = payload.get("id")
        if not isinstance(cid, int):
            raise ValueError(f"id 必须是整数：{cid!r}")
        if cid not in self.batch_of:
            raise ValueError(f"id {cid} 不在本段 frozen/source.jsonl 里，无处可落")
        if verdict == "adopt" and cid not in self.queue_pos:
            # 服务端硬拒，不只靠前端不画按钮：一条指向"不存在的提案"的 adopt 记录
            # 到了 polish_commit 那边只会变成一句"找不到候选，跳过"的静默丢失，
            # 而人这边以为自己已经裁过了——正是本项目最怕的失败形态。
            raise ValueError(f"id {cid} 不在队列里（没有任何通道提案），"
                             f"只能 edit / keep_opus")
        if verdict == "adopt" and not payload.get("chosen_channel"):
            raise ValueError(f"{verdict} 必须带 chosen_channel")
        chosen_alt = payload.get("chosen_alt")
        if chosen_alt is not None and not isinstance(chosen_alt, int):
            raise ValueError(f"chosen_alt 必须是整数（1-based 序号）：{chosen_alt!r}")
        edited = payload.get("edited_zh")
        if verdict == "edit" and not isinstance(edited, str):
            raise ValueError("edit 必须带 edited_zh 字符串")
        rec = {
            "id": cid,
            "verdict": verdict,
            "chosen_channel": payload.get("chosen_channel") if verdict == "adopt" else None,
            "chosen_alt": chosen_alt if verdict == "adopt" else None,
            "edited_zh": edited if verdict == "edit" else None,
            "reason_code": payload.get("reason_code") or "",
            "note": payload.get("note") or "",
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with self._lock:                          # 多标签页/多请求并发追加时不交错
            append_draft(self.draft_path, rec)    # 写前过一道文件名断言
        return rec

    # ---------- 敲定文本 ----------
    def lane_zh(self, cid) -> str:
        """车道最新译文（resolve 结果），段内缺失时回落冻结面。右栏的"未裁"基线。"""
        return self.current.get(cid, self.frozen_opus.get(cid, ""))

    def resolve_settled(self, cid, d: dict) -> dict:
        """一条草稿记录 → 这一行"裁决之后会变成什么"。见模块 docstring「敲定文本」。

        任何解析不出来的情况都**回落车道文本 + 写 problem**，不抛异常：这个函数
        跑在每一次上下文渲染上（一屏 30+ 行），一条手工写坏的草稿行不该让整页打不开。
        """
        v = d.get("verdict")
        out = {"zh": self.lane_zh(cid), "verdict": v,
               "channel": d.get("chosen_channel"), "alt": d.get("chosen_alt"),
               "reason_code": d.get("reason_code") or "", "note": d.get("note") or "",
               "ts": d.get("ts"), "problem": None}
        if v == "edit":
            zh = d.get("edited_zh")
            if isinstance(zh, str):
                out["zh"] = zh          # 原样：不 trim、不清洗、不截断（拍板第 4 条）
            else:
                out["problem"] = "edit 记录里没有 edited_zh 字符串"
        elif v == "adopt":
            ch = d.get("chosen_channel")
            cand = self.channels.get(ch, {}).get(cid)
            if cand is None:
                out["problem"] = f"通道 {ch!r} 里找不到 id {cid} 的候选（通道改名或候选文件变过？）"
            elif d.get("chosen_alt") is None:
                out["zh"] = cand.get("zh", "")
            else:
                alts, n = cand.get("alts") or [], d.get("chosen_alt")
                if isinstance(n, int) and 1 <= n <= len(alts):
                    out["zh"] = alts[n - 1].get("zh", "")
                else:
                    out["problem"] = f"chosen_alt={n!r} 越界：{ch} 对该 id 只有 {len(alts)} 条备选"
        elif v != "keep_opus":
            out["problem"] = f"未知 verdict：{v!r}"
        return out

    def settled_for(self, cid, dec: dict):
        """`{id: 敲定信息}` 里的一条；该 id 没裁过则 None。"""
        d = dec.get(cid)
        return self.resolve_settled(cid, d) if d else None

    # ---------- 视图 ----------
    def _list_row(self, cid, dec: dict, it=None) -> dict:
        """左栏一行。`it` 是队列项（自选行传 None，现造一个空壳）。"""
        d = dec.get(cid)
        base = it if it is not None else {
            "id": cid, "batch": self.batch_of.get(cid), "channels": [], "n_proposals": 0,
            "n_covered": sum(1 for ch in self.channels if cid in self.channels[ch]),
            "reasons": [],
        }
        return {**base,
                "in_queue": cid in self.queue_pos,
                "drift": cid in self.drift,
                "soft": cid in self.soft_ids,
                "hard": cid in self.hard_ids,
                "verdict": d.get("verdict") if d else None,
                "chosen_channel": d.get("chosen_channel") if d else None}

    def queue_payload(self) -> dict:
        """左栏列表 = 队列全体 + **已裁决过的**自选行，按阅读顺序混排。

        自选行混进同一条阅读顺序线（而不是另起一栏）是有意的：它本来就是从
        上下文里捞出来的，摆在它的邻居中间才对得上人当时在读的位置。只有
        `in_queue` 标记区分二者，计数则严格分开（见模块 docstring「自选行」）。
        """
        dec = self.decisions()
        items = [self._list_row(it["id"], dec, it) for it in self.queue]
        picked = [cid for cid in dec if cid not in self.queue_pos and cid in self.batch_of]
        items += [self._list_row(cid, dec) for cid in picked]
        n = len(self.order)
        items.sort(key=lambda r: (order_key(r["id"], self.order_pos, n), r["id"]))
        return {
            "seg": self.seg,
            "channels": sorted(self.channels),
            # total/done 只算队列：自选行是人自己捞的，混进同一个分母会让
            # "队列还剩多少"这个唯一有意义的进度失真。
            "total": len(self.queue),
            "done": sum(1 for r in items if r["in_queue"] and r["verdict"]),
            "picked": len(picked),
            "seg_rows": len(self.batch_of),
            "drifted": sum(1 for r in items if r["in_queue"] and r["drift"]),
            "context_before": self.context_before,
            "context_after": self.context_after,
            "draft_path": str(self.draft_path),
            "items": items,
        }

    def next_undecided(self, cid=None) -> int | None:
        """**队列里**当前位置之后的第一条未裁项（到底则从头绕一圈），全裁完返回 None。

        起点用「阅读顺序位置」而不是「队列下标」找，这样**自选行也能算**：一条
        不在队列里的行裁完后，落点是队列中按阅读顺序排在它后面的那一条，人是
        继续往前读，而不是被甩回队首（也不会沿着段内 4282 行往下走）。
        对队列内的 id，这个算法与"下标 +1"逐字等价。
        """
        dec = self.decisions()
        n = len(self.queue)
        if n == 0:
            return None
        if cid is None:
            start = 0
        else:
            key = order_key(cid, self.order_pos, len(self.order))
            start = bisect.bisect_right(self._queue_keys, key)
        for k in range(n):
            it = self.queue[(start + k) % n]
            if it["id"] not in dec:
                return it["id"]
        return None

    def context_rows(self, cid, dec: dict = None) -> list:
        """当前行 + 前后文，按阅读顺序。左右两栏共用这一份行表以保证逐行对齐。

        `zh` 是**敲定文本**（裁过就是裁后的、没裁就是车道最新），`zh_lane` 保留
        车道最新原值。上下文行同样适用——这正是本需求的价值所在：连续裁相邻行时，
        前几行显示的必须是刚刚敲定的样子，而不是被自己推翻掉的旧译文。
        """
        pos = self.order_pos.get(cid)
        if pos is None:                      # 不在阅读顺序表里：至少把自己显示出来
            window = [cid]
        else:
            lo = max(0, pos - self.context_before)
            hi = min(len(self.order), pos + self.context_after + 1)
            window = self.order[lo:hi]
        dec = self.decisions() if dec is None else dec
        rows = []
        for i in window:
            lane = self.lane_zh(i)
            st = self.settled_for(i, dec)
            rows.append({
                "id": i,
                "jp": self.jp.get(i, ""),
                "zh": st["zh"] if st else lane,     # 显示用：敲定文本优先
                "zh_lane": lane,                    # 车道最新，永不被顶掉
                "current": i == cid,
                "in_queue": i in self.queue_pos,
                "verdict": st["verdict"] if st else None,
                "settled": st,                      # 未裁为 None；含 channel/alt/reason/note/problem
            })
        return rows

    def item_payload(self, cid) -> dict:
        """段内任意 id 都能开（不只是队列里的 381 条）——自选行走的就是这条路。
        段外 id 抛 KeyError（HTTP 层转 404）：那是"输错了 id"，必须报错而不是
        开一个空白页让人对着改。"""
        if cid not in self.batch_of:
            raise KeyError(cid)
        dec = self.decisions()          # 本次请求只读一次草稿，下面各处共用（且必然是最新的）
        frozen_zh = self.frozen_opus.get(cid, "")
        cur = self.lane_zh(cid)
        settled = self.settled_for(cid, dec)
        # 提案 diff 的基线取**右栏实际显示的那段文字**：人看到什么就跟什么比。
        # 未裁时它等于车道最新（与本功能之前的行为逐字一致）。
        display = settled["zh"] if settled else cur
        proposals = []
        for ch in sorted(self.channels):
            cand = self.channels[ch].get(cid)
            if cand is None:
                continue
            zh = cand.get("zh", "")
            reasons = candidate_reasons(cand, frozen_zh)
            same_cur = _ws_equal(zh, display)
            note = cand.get("note") or ""
            alts = [{"zh": a.get("zh", ""), "note": a.get("note", "")}
                    for a in (cand.get("alts") or [])]
            proposals.append({
                "channel": ch,
                "score": cand.get("score"),
                "adjudicate": bool(cand.get("adjudicate")),
                "note": note,
                "zh": zh,
                "alts": alts,
                "reasons": reasons,
                "same_as_frozen": _ws_equal(zh, frozen_zh),
                "same_as_current": same_cur,
                # 折叠判据：与现行译文逐字相同**且**没有任何要说的话才折叠。
                # 只按 noop 折叠会把"照抄 + 请裁"这类行的批注一起藏掉——那正是
                # 契约鼓励的行为，藏它等于惩罚老实通道（P4 D3 缺陷同一形态）。
                "collapsible": same_cur and not cand.get("adjudicate") and not note and not alts,
            })
        d = dec.get(cid)
        in_queue = cid in self.queue_pos
        return {
            "id": cid,
            "in_queue": in_queue,
            "batch": self.batch_of.get(cid),
            "jp": self.jp.get(cid, ""),
            "zh_current": cur,          # 车道最新（漂移面板与"原文/现译对照"用，别删）
            "zh_display": display,      # 右栏实际显示的文字＝敲定文本 ?? 车道最新
            "settled": settled,         # 未裁为 None
            "zh_frozen": frozen_zh,
            "drift": self.drift.get(cid),
            "soft": cid in self.soft_ids,
            "hard": cid in self.hard_ids,
            "lock_why": self.lock_why.get(cid, ""),
            "context": self.context_rows(cid, dec),
            "proposals": proposals,
            "decision": d,
            "queue_index": self.queue_pos[cid] if in_queue else None,
            "queue_total": len(self.queue),
            "next_undecided": self.next_undecided(cid),
        }


# ---------------------------------------------------------------- HTTP 层
class Server(ThreadingHTTPServer):
    """`ThreadingHTTPServer` + 跳过 `socket.getfqdn()` 的 bind。

    实测（macOS）：`HTTPServer.server_bind()` 里那句 `socket.getfqdn()` 会去做
    反向 DNS，本机环境下**卡 35 秒**才返回——服务启动和单测都被它拖死。
    `server_name` 只用于 CGI 场景的环境变量，本服务根本不用，直接填监听地址。
    """
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


def make_handler(model: Adjudication):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ZndAdjudicate/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):    # 静音访问日志：逐条裁决会刷屏
            pass

        # -- 小工具 --
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

        # -- 路由 --
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
            if path == "/api/queue":
                return self._json(model.queue_payload())
            if path == "/api/item":
                raw = (q.get("id") or [""])[0]
                try:
                    cid = int(raw)
                except ValueError:
                    return self._err(400, f"id 不是整数：{raw!r}")
                try:
                    return self._json(model.item_payload(cid))
                except KeyError:
                    return self._err(404, f"id {cid} 不在本段（frozen/source.jsonl）里")
            return self._err(404, f"没有这个端点：{path}")

        def do_HEAD(self):
            self.do_GET()

        def do_POST(self):
            if urlparse(self.path).path != "/api/decide":
                return self._err(404, f"没有这个端点：{self.path}")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception as e:
                return self._err(400, f"请求体不是合法 JSON：{e}")
            try:
                rec = model.record(payload)
            except ValueError as e:
                return self._err(400, str(e))
            return self._json({"ok": True, "record": rec,
                               "next_undecided": model.next_undecided(rec["id"]),
                               "done": len(model.decisions())})

    return Handler


def main(argv=None):
    ap = argparse.ArgumentParser(description="P5 逐条裁决 Web UI（本地服务，只写 decisions.draft.jsonl）")
    ap.add_argument("--seg", required=True, help="段目录名（如 p5seg0-s0-s1）")
    ap.add_argument("--repo", default=None, help="仓库根（省略用本仓库；测试传 tmp_path）")
    ap.add_argument("--lane", default=DEFAULT_LANE, help="车道目录（相对仓库根），默认 pilot/lanes/opus")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0")
    ap.add_argument("--port", type=int, default=8788, help="端口，默认 8788")
    ap.add_argument("--context", type=int, default=DEFAULT_CONTEXT_BEFORE, help="前文行数，默认 30")
    ap.add_argument("--after", type=int, default=DEFAULT_CONTEXT_AFTER, help="后文行数，默认 3")
    args = ap.parse_args(argv)

    model = Adjudication(args.seg, repo=args.repo, lane=args.lane,
                         context_before=args.context, context_after=args.after)
    dec = model.decisions()
    # flush=True：stdout 被重定向到文件/管道时是块缓冲的，不 flush 就看不到
    # 访问 URL——而"启动后把 URL 打到 stdout"正是拍板第 2 条要的东西。
    picked = [i for i in dec if i not in model.queue_pos and i in model.batch_of]
    print(f"段 {args.seg}：全段 {len(model.batch_of)} 行，队列 {len(model.queue)} 条"
          f"（通道 {', '.join(sorted(model.channels)) or '无'}；漂移 "
          f"{sum(1 for it in model.queue if it['id'] in model.drift)} 条；"
          f"草稿已裁 {sum(1 for it in model.queue if it['id'] in dec)} 条"
          f"，另有自选行 {len(picked)} 条）", flush=True)
    print(f"草稿文件（唯一写口）：{model.draft_path}", flush=True)
    try:
        httpd = Server((args.host, args.port), make_handler(model))
    except OSError as e:
        print(f"!! 起不来：{e}——端口 {args.port} 多半被占，用 --port 换一个", file=sys.stderr)
        return 1
    # 不自动开浏览器（拍板第 2 条）：把 URL 打出来由人自己点。
    print(f"服务已启动：http://127.0.0.1:{args.port}/   （监听 {args.host}:{args.port}，Ctrl-C 停）",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
