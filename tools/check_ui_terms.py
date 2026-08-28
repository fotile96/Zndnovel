#!/usr/bin/env python3
"""UI／标签译文与「已入线正文」的用词一致性闸。

**它防的是什么。** `png/` 各面（card 右栏、select 按钮、sysgim 菜单……）上的字
是新造的，正文那 16749 条不是。两边若各译各的，玩家会在同一屏里看到两套词——
`select/` 那轮已经真的踩到过（L4：谜面写「赝品」而按钮写「赝作师」）。

**判据从哪来。** 不凭语感，凭**已入线正文里的压倒性用法**：`config/ui_terms.yaml`
每条术语都带 evidence（命中行数与分布）。所以这道闸检的不是「译得好不好」，
是「和已经落地的那 16749 条一致不一致」。

**两条腿，缺一条就会变成恒绿的闸：**

- `check`  —— 登记过的术语：标签 jp 含 T 则其 zh 必须含 T 的定译。
- `discover` —— 标签 jp 里出现、正文里也够常见（≥MIN_HITS 行）、却**没登记**的词。
  没有这条腿，闸只会检它已经知道的东西：新面新词一律零命中，永远绿。

例外（`exempt_jp`）：`物語` 一般译「故事」，但 `セカンドノベル`→「第二物语」、
`失われた夢の物語`→「已失去的梦之物语」是专有书名，另有定译——命中例外词则跳过该条。
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
LEDGER = REPO / "pilot" / "lanes" / "opus" / "data" / "ledger.jsonl"
CARDS_JP = REPO / "skeleton" / "cards.jp.yaml"
CARDS_ZH = REPO / "skeleton" / "cards.zh.yaml"

#: 一个词要在正文里多常见，才值得要求 UI 与之对齐。低于此则不进 discover 报告。
MIN_HITS = 20

#: 一个词要在**被检标签集**里重复出现多少次，才算「术语」而不是路过的散文词。
#:
#: 这条门槛是被伪报逼出来的：只卡 MIN_HITS 时，243 条自由文本场景名（『夕方の校庭』
#: 『コーヒー』『深呼吸』…）会刷出四十多条「未登记」，把真信号淹掉——而闸一旦开始
#: 狼来了就等于没有。术语的特征是**跨条目复现**（あらすじ／カード／セクション 天然如此），
#: 一次性出现的词是散文，不是术语。
MIN_LABEL_USES = 2

#: discover 只看这两类连续串：片假名词与汉字词。平假名串多是助词/词尾，噪声太大。
_KATAKANA = re.compile(r"[ァ-ヶー]{2,}")
_KANJI = re.compile(r"[一-鿿]{2,}")


@dataclass(frozen=True)
class Term:
    jp: str
    zh: str
    evidence: str
    exempt_jp: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    kind: str  # "mismatch" | "unregistered"
    path: str
    jp: str
    zh: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}\t{self.path}\t{self.jp!r} -> {self.zh!r}\t{self.detail}"


def load_terms(path: Path = CONFIG) -> list[Term]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for e in raw.get("terms", []):
        out.append(
            Term(
                jp=e["jp"],
                zh=e["zh"],
                evidence=e.get("evidence", ""),
                exempt_jp=tuple(e.get("exempt_jp", ())),
            )
        )
    if not out:
        raise ValueError(f"{path} 里一条术语都没有——闸会恒绿，拒绝以此配置运行")
    return out


def load_not_terms(path: Path = CONFIG) -> set[str]:
    """刻意不登记的词：discovery 跳过，但理由留在配置里可查。"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = set()
    for e in raw.get("not_terms", []):
        if not e.get("why"):
            raise ValueError(f"not_terms 条目 {e.get('jp')!r} 缺 why——除名必须写明理由")
        out.add(e["jp"])
    return out


def load_suppressions(path: Path) -> set[tuple[str, str]]:
    """(jp, term) 级的 mismatch 抑制，理由必填。

    抑制的是**个案**而非术语：`担任の教師→班主任` 是对的，不该逼它写「教师」，
    但这不能牵连 `教師` 这条术语本身。
    """
    if not path.exists():
        return set()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = set()
    for e in raw.get("suppress", []):
        if not e.get("why"):
            raise ValueError(f"抑制条目 {e.get('jp')!r}/{e.get('term')!r} 缺 why")
        out.add((e["jp"], e["term"]))
    return out


def load_pairs(path: Path) -> list[dict]:
    """读一个 {jp, zh} 的 jsonl 标签文件。

    **`zh` 为空的行跳过**：那是「原始语料已落盘、译文待补」的中间态（见
    `tools/check_sysgim_text.py`），不是译错。拿空串去比对术语只会得到一串
    必然的 mismatch，把真信号淹掉——闸一旦开始狼来了就等于没有。
    待译的计数由 `check_sysgim_text.py` 单独负责。
    """
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if "jp" not in r or "zh" not in r:
            raise ValueError(f"{path}:{n} 缺 jp/zh 字段")
        if not str(r["zh"]).strip():
            continue
        rows.append(r)
    return rows


def corpus_jp_lines(repo: Path = REPO) -> list[str]:
    """jp 语料 = 正文 ledger + 卡面骨架的 title_jp/body_jp。

    **刻意不含卡面的 `section_label`**：zh 侧没有对应字段（右栏中文另存
    `data/card_section_labels.jsonl`），把它算进来会让 `config/ui_terms.yaml`
    里的 evidence 分母虚高、占比虚低。语料的定义在这里和 evidence 一致。
    """
    lines: list[str] = []
    lg = repo / "pilot" / "lanes" / "opus" / "data" / "ledger.jsonl"
    if lg.exists():
        for line in lg.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append(json.loads(line)["jp"])
    cj = repo / "skeleton" / "cards.jp.yaml"
    if cj.exists():
        for c in yaml.safe_load(cj.read_text(encoding="utf-8")) or []:
            for f in ("title_jp", "body_jp"):
                if c.get(f):
                    lines.append(str(c[f]))
    return lines


def check_mismatches(
    rows: list[dict],
    terms: list[Term],
    path: str,
    suppress: set[tuple[str, str]] = frozenset(),  # type: ignore[assignment]
) -> list[Violation]:
    out = []
    for r in rows:
        jp, zh = r["jp"], r["zh"]
        for t in terms:
            if t.jp not in jp:
                continue
            if any(x in jp for x in t.exempt_jp):
                continue
            if (jp, t.jp) in suppress:
                continue
            if t.zh not in zh:
                out.append(
                    Violation(
                        "mismatch",
                        path,
                        jp,
                        zh,
                        f"jp 含「{t.jp}」，正文定译为「{t.zh}」（{t.evidence}），但 zh 里没有",
                    )
                )
    return out


def check_unregistered(
    rows: list[dict],
    terms: list[Term],
    corpus_lines: list[str],
    path: str,
    min_hits: int = MIN_HITS,
    min_label_uses: int = MIN_LABEL_USES,
    not_terms: set[str] = frozenset(),  # type: ignore[assignment]
) -> list[Violation]:
    """标签里**反复**出现、正文里也常见、却没登记的词。

    两道门槛缺一不可：`min_label_uses` 挡散文噪声，`min_hits` 挡正文里本就罕见、
    无「既有用法」可对齐的词。
    """
    known = {t.jp for t in terms} | set(not_terms)
    uses: dict[str, list[dict]] = {}
    for r in rows:
        for c in set(_KATAKANA.findall(r["jp"])) | set(_KANJI.findall(r["jp"])):
            # 已登记术语的子串／超串都算已覆盖
            if any(c in k or k in c for k in known):
                continue
            uses.setdefault(c, []).append(r)

    out = []
    for c in sorted(uses):
        rs = uses[c]
        if len(rs) < min_label_uses:
            continue
        hits = sum(1 for ln in corpus_lines if c in ln)
        if hits < min_hits:
            continue
        out.append(
            Violation(
                "unregistered",
                path,
                rs[0]["jp"],
                rs[0]["zh"],
                f"「{c}」在被检标签中出现 {len(rs)} 次、正文 {hits} 行，却未登记在 {CONFIG.name}",
            )
        )
    return out


def run(
    paths: list[Path],
    repo: Path = REPO,
    min_hits: int = MIN_HITS,
    min_label_uses: int = MIN_LABEL_USES,
) -> list[Violation]:
    cfg = repo / "config" / "ui_terms.yaml"
    terms = load_terms(cfg)
    not_terms = load_not_terms(cfg)
    suppress = load_suppressions(repo / "config" / "ui_term_suppressions.yaml")
    corpus = corpus_jp_lines(repo)
    out: list[Violation] = []
    for p in paths:
        rows = load_pairs(p)
        try:
            rel = str(p.relative_to(repo))
        except ValueError:
            rel = str(p)
        out += check_mismatches(rows, terms, rel, suppress)
        out += check_unregistered(
            rows, terms, corpus, rel, min_hits, min_label_uses, not_terms
        )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path, help="{jp,zh} 的 jsonl 标签文件")
    ap.add_argument("--min-hits", type=int, default=MIN_HITS)
    ap.add_argument("--min-label-uses", type=int, default=MIN_LABEL_USES)
    a = ap.parse_args(argv)
    v = run(
        [p.resolve() for p in a.files],
        min_hits=a.min_hits,
        min_label_uses=a.min_label_uses,
    )
    for x in v:
        print(x)
    n_mis = sum(1 for x in v if x.kind == "mismatch")
    n_unr = len(v) - n_mis
    print(f"\n用词不一致 {n_mis} 条 / 未登记术语 {n_unr} 条", file=sys.stderr)
    return 1 if v else 0


if __name__ == "__main__":
    raise SystemExit(main())
