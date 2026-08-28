#!/usr/bin/env python3
"""`config/ui_terms.yaml` 的**自校准闸**——把冻结的 evidence 重新对着现行译文量一遍。

**它防的是什么。** `check_ui_terms.py` 的判据全部来自 `ui_terms.yaml` 里人手写下的
`zh` 与 `evidence`。那是**字符串**：正文改了它不会自己动，闸也不会因此变红——闸只会
继续拿一条作废的规则去检东西。2026-08-19 的 glossary v19 C1 把故事层片假名人名整体
改成罗马音，这张表却仍写着「ユウイチ → ユウイチ」，于是接下来 9 天里：

- select/ 那 8 条真该罗马音化的按钮，一条都没报；
- extra 车道那 11 条**已经改对**的，反被报成 mismatch。

闸恒绿是一种失效，闸**反着绿**是更坏的一种。区别在于后者会主动把人往回带。

**判据。** 语料 = 现行译文（`forward.jsonl` 叠 `patches.jsonl`，patch 后写者胜）配上
`ledger.jsonl` 的 jp，加上卡面骨架 `cards.{jp,zh}.yaml` 的 title/body。对每条术语算
「jp 含该词的行里，zh 含定译的占多少」——和当初造表时同一套算法，所以两边的数字可以
直接比。低于 `DRIFT_THRESHOLD` 即报漂移。

**用法。**

    uv run python tools/measure_ui_terms.py            # 报告，漂移则非零退出
    uv run python tools/measure_ui_terms.py --write    # 把 evidence 数字刷成实测值

`--write` **只改 evidence 里的数字，从不碰 zh**——定译改成什么是人的裁决，不是本工具
的。也正因如此，只要还有条目在漂移，`--write` 就拒绝执行：那种情况下先要人来定新的
`zh`，而不是把一个错误的定译配上一份漂亮的新数字。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "ui_terms.yaml"

#: 收录门槛，与 `ui_terms.yaml` 头部自述的一致。低于此即认为定译已与正文脱节。
DRIFT_THRESHOLD = 85.0

#: evidence 的规范形状。**刻意要求统一格式**——格式不齐就没法机器复核，
#: 而"没法复核的证据"正是这张表烂掉的方式。附加说明写在全角分号之后。
_EVIDENCE_RE = re.compile(r"^(\d+) 行中 (\d+) 行（([\d.]+)%）")


@dataclass(frozen=True)
class Measurement:
    jp: str
    zh: str
    evidence: str
    hits: int
    total: int

    @property
    def pct(self) -> float:
        return 100.0 * self.hits / self.total if self.total else 0.0

    def drifted(self, threshold: float = DRIFT_THRESHOLD) -> bool:
        """占比跌破门槛，或该词在正文里已经一次都不出现。

        `total == 0` 单独算一种漂移：它意味着这条术语管的东西没了，属于僵尸条目。
        若当成"无数据故跳过"，表会越积越多这种看着权威的死条文。
        """
        return self.total == 0 or self.pct < threshold

    def evidence_text(self) -> str:
        """按实测值渲染出的规范 evidence 前缀（不含全角分号之后的附注）。"""
        # 沿用原表惯例：满分写整数「100%」，其余一律保一位小数（含 99.0% 这种）。
        pct = "100" if self.pct == 100.0 else f"{self.pct:.1f}"
        return f"{self.total} 行中 {self.hits} 行（{pct}%）"

    def evidence_matches(self) -> bool:
        """evidence 里写的数字是否就是现在量出来的数字。"""
        m = _EVIDENCE_RE.match(self.evidence)
        if not m:
            return False
        return (int(m.group(1)), int(m.group(2))) == (self.total, self.hits)


def _resolved_zh(repo: Path) -> dict[int, str]:
    """现行译文：forward 打底，patches 覆盖（同 id 后写者胜，与 resolve.resolve_map 一致）。"""
    lane = repo / "pilot" / "lanes" / "opus" / "data"
    out: dict[int, str] = {}
    for name in ("forward.jsonl", "patches.jsonl"):
        p = lane / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r["zh"]
    return out


def _cards(repo: Path) -> list[tuple[str, str]]:
    jp_p, zh_p = repo / "skeleton" / "cards.jp.yaml", repo / "skeleton" / "cards.zh.yaml"
    if not (jp_p.exists() and zh_p.exists()):
        return []

    def by_key(path: Path) -> dict:
        rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return {(r.get("card"), r.get("variant")): r for r in rows}

    jp, zh = by_key(jp_p), by_key(zh_p)
    out = []
    for k, j in jp.items():
        z = zh.get(k)
        if not z:
            continue
        # section_label 刻意不进语料：zh 侧没有对应字段（右栏中文另存
        # data/card_section_labels.jsonl），算进来只会让分母虚高。
        for fj, fz in (("title_jp", "title_zh"), ("body_jp", "body_zh")):
            if j.get(fj):
                out.append((str(j[fj]), str(z.get(fz) or "")))
    return out


def corpus_pairs(repo: Path = REPO) -> list[tuple[str, str]]:
    """对齐的 (jp, zh) 语料。**没有 zh 的 ledger 行不进来**——它们不是"译错了"，
    是压根没进译文线（ambient 等 56 条），算进分母等于无差别稀释每一条术语。
    """
    zh_by_id = _resolved_zh(repo)
    pairs: list[tuple[str, str]] = []
    led = repo / "data" / "ledger.jsonl"
    if led.exists():
        for line in led.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] in zh_by_id:
                pairs.append((r["jp"], zh_by_id[r["id"]]))
    return pairs + _cards(repo)


def measure_term(
    jp: str,
    zh: str,
    pairs: list[tuple[str, str]],
    exempt_jp: tuple[str, ...] = (),
    evidence: str = "",
) -> Measurement:
    sel = [(a, b) for a, b in pairs if jp in a and not any(x in a for x in exempt_jp)]
    hits = sum(1 for _a, b in sel if zh in b)
    return Measurement(jp=jp, zh=zh, evidence=evidence, hits=hits, total=len(sel))


def measure_all(repo: Path = REPO, config: Path = CONFIG) -> list[Measurement]:
    pairs = corpus_pairs(repo)
    raw = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    return [
        measure_term(
            e["jp"],
            e["zh"],
            pairs,
            tuple(e.get("exempt_jp", ())),
            e.get("evidence", ""),
        )
        for e in raw.get("terms", [])
    ]


def rewrite_evidence(text: str, ms: list[Measurement]) -> str:
    """把 evidence 的数字前缀刷成实测值，保留全角分号之后的人写附注与全部注释。

    逐行改而不是 yaml round-trip：这张表的价值有一半在注释里（每条为什么收、
    为什么不收），round-trip 会把它们全部抹掉。

    只替换 `_EVIDENCE_RE` 匹配到的数字前缀，全角分号之后的人写附注原样带走。
    **不合规范格式的 evidence 一律不动并抛错**——把整行覆盖掉会连人写的理由一起
    吞掉（`砂時計` 的「唯一取值；正文教程原文即…」正是这种），而那种丢失是静默的。
    """
    by_jp = {m.jp: m for m in ms}
    out, cur, unparsable = [], None, []
    for line in text.splitlines(keepends=True):
        m_jp = re.match(r"^  - jp: (.+?)\s*$", line)
        if m_jp:
            cur = m_jp.group(1)
        m_ev = re.match(r"^(\s+evidence: )(.*)$", line, re.S)
        if m_ev and cur in by_jp:
            body = m_ev.group(2).rstrip("\n")
            hit = _EVIDENCE_RE.match(body)
            if not hit:
                unparsable.append((cur, body))
            else:
                line = f"{m_ev.group(1)}{by_jp[cur].evidence_text()}{body[hit.end():]}\n"
        out.append(line)
    if unparsable:
        raise ValueError(
            "以下 evidence 不合「N 行中 M 行（P%）」的规范格式，拒绝改写"
            "（覆盖会吞掉后面人写的理由，请先手工规范化）：\n"
            + "\n".join(f"  {jp}: {body!r}" for jp, body in unparsable)
        )
    return "".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="把 evidence 数字刷成实测值")
    ap.add_argument("--threshold", type=float, default=DRIFT_THRESHOLD)
    a = ap.parse_args(argv)

    ms = measure_all()
    drift = [m for m in ms if m.drifted(a.threshold)]
    stale = [m for m in ms if not m.evidence_matches()]

    for m in ms:
        mark = "  <<< 漂移" if m.drifted(a.threshold) else ("  <- 数字过期" if not m.evidence_matches() else "")
        print(f"{m.jp:<12} -> {m.zh:<10} {m.evidence_text():>22}   记：{m.evidence}{mark}")

    print(
        f"\n共 {len(ms)} 条：漂移 {len(drift)} 条 / evidence 数字过期 {len(stale)} 条",
        file=sys.stderr,
    )

    if a.write:
        if drift:
            print(
                "拒绝 --write：还有条目在漂移。定译（zh）该改成什么是人的裁决，"
                "先把 zh 定下来，再来刷数字——否则只是给一个错误的定译配一份漂亮的新证据。",
                file=sys.stderr,
            )
            return 1
        CONFIG.write_text(
            rewrite_evidence(CONFIG.read_text(encoding="utf-8"), ms), encoding="utf-8"
        )
        print(f"已刷新 {len(stale)} 条 evidence 数字。", file=sys.stderr)
        return 0

    return 1 if (drift or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
