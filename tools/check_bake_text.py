#!/usr/bin/env python3
"""烤字译文数据（`data/*_text.jsonl`）的 schema 闸。

**为什么现在才补。** 这两份文件是 A/B 两族烤字的译文来源，共 99 行，此前**零校验**：
`tests/` 里搜不到对它们的任何一处引用。打错的后果实测过两种——图名写错要跑到读图
那一步才 `FileNotFoundError`，漏掉 `zh` 字段是 `KeyError: 'zh'`。**都是崩溃，不是闸**：
不告诉你哪一行、哪个字段、该怎么改。C/D/E 三类要往里再灌二十多张（现有量的一倍），
正是最容易引入不一致的时点。

**两份文件的 schema 不同，这不是疏忽。** `box` 在 glow 里必填、在 outline 里可选，
差异是**工具行为的一部分**：

- glow 的每一行都是独立的盒，几何全由 `box` 说了算。
- outline 默认按整张图的墨迹自动分段成「行」；`box` 是**例外声明**——
  某一行带 `box` ＝ 覆盖该行的自动分段结果（`sys_22_ba/bb` 只改 x0–66，右边是
  10 个音量格）；某张图**所有**行都带 `box` ＝ 整张切到「纯按盒替换」模式
  （`sys_22_e` 七个名字里只改一个，其余逐像素保持原样）。

本闸把这条只写在代码注释里的规则变成可执行的检查。

**`zh` 为空 ＝ 待译，不是错误。** 原始语料先落盘、译文后补，是刻意的两步走：
先把「原文是什么、在哪个盒里」这件可测的事定死，再谈翻译。空 `zh` 会被单独报成
`待译`，并由 `bake_sysgim_*` 拒绝渲染（而不是渲成一片空白）。

    uv run python tools/check_bake_text.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SYSGIM = REPO / "png" / "sysgim"
OUTLINE = REPO / "data" / "sysgim_outline_text.jsonl"
GLOW = REPO / "data" / "sysgim_glow_text.jsonl"
EVENT_OP = REPO / "data" / "event_op_text.jsonl"

#: 受本闸管辖的数据文件：(数据文件, 原图目录, box 是否必填)。
#:
#: **加新面时往这里加一行，别新起一个闸。** `cutin/` 那 40 张、`graphic/` 的
#: memoryThumbnail 都会进来——每个面一个专用闸，等于每个面都有机会漏掉一条检查。
SOURCES = [
    (OUTLINE, SYSGIM, False),
    (GLOW, SYSGIM, True),
    (EVENT_OP, REPO / "png" / "event", True),
]

REQUIRED = ("file", "row", "jp", "zh")
KNOWN = REQUIRED + ("box", "note", "deferred")


@dataclass(frozen=True)
class Problem:
    path: str
    line: int
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}\t{self.path}:{self.line}\t{self.detail}"


def _rows(path: Path):
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if line:
            yield n, json.loads(line)


def check(path: Path, box_required: bool, img_dir: Path = SYSGIM) -> tuple[list[Problem], list[Problem]]:
    """返回 (错误, 待译)。待译单独一列——它不是缺陷，是工作还没做完。"""
    errs: list[Problem] = []
    todo: list[Problem] = []
    seen: set[tuple[str, int]] = set()
    by_file: dict[str, list[tuple[int, dict]]] = {}
    try:
        rel = str(path.relative_to(REPO))
    except ValueError:
        rel = str(path)      # 测试用的临时文件不在仓库内

    for n, r in _rows(path):
        for k in REQUIRED:
            if k not in r:
                errs.append(Problem(rel, n, "缺字段", f"缺 {k!r}"))
        unknown = set(r) - set(KNOWN)
        if unknown:
            # 打错字段名（zh_ / note2 / bbox…）会被工具默默忽略，是最难发现的一类
            errs.append(Problem(rel, n, "未知字段", f"{sorted(unknown)}；已知：{list(KNOWN)}"))
        if not all(k in r for k in REQUIRED):
            continue

        key = (r["file"], r["row"])
        if key in seen:
            errs.append(Problem(rel, n, "重复行号", f"{r['file']} 的 row={r['row']} 出现多次"))
        seen.add(key)
        by_file.setdefault(r["file"], []).append((n, r))

        img_p = img_dir / f"{r['file']}.png"
        if not img_p.exists():
            errs.append(Problem(rel, n, "图不存在", str(img_p.relative_to(REPO)) if REPO in img_p.parents else str(img_p)))
            continue

        if not str(r["jp"]).strip():
            errs.append(Problem(rel, n, "jp 为空", f"{r['file']} row={r['row']}"))
        if not str(r["zh"]).strip():
            if not r.get("deferred"):
                todo.append(Problem(rel, n, "待译", f"{r['file']} row={r['row']}「{r['jp']}」"))

        if "box" in r:
            box = r["box"]
            if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, int) for v in box)):
                errs.append(Problem(rel, n, "box 格式", f"要 4 个整数，收到 {box!r}"))
                continue
            x0, y0, x1, y1 = box
            W, H = Image.open(img_p).size
            if not (0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H):
                errs.append(Problem(rel, n, "box 越界",
                                    f"{box} 不在 {r['file']} 的 {W}x{H} 内，或宽高为 0"))
        elif box_required:
            errs.append(Problem(rel, n, "缺 box", f"{rel} 的每一行都必须带 box"))

    if not box_required:
        # outline 的「例外声明」规则：一张图要么全带 box（纯按盒替换），
        # 要么只有个别行带（覆盖那一行的自动分段）。二者都合法，但
        # **半数行带 box** 多半是漏写——那种图的自动分段结果已不可信。
        for f, rows in by_file.items():
            have = [n for n, r in rows if "box" in r]
            if have and len(have) != len(rows) and len(have) > 1:
                errs.append(Problem(rel, have[0], "box 半带",
                                    f"{f}：{len(have)}/{len(rows)} 行带 box。"
                                    f"要么全带（纯按盒替换），要么只标个别例外行"))
    return errs, todo


def run() -> tuple[list[Problem], list[Problem]]:
    errs: list[Problem] = []
    todo: list[Problem] = []
    for data, img_dir, box_req in SOURCES:
        if not data.exists():
            continue
        e, t = check(data, box_required=box_req, img_dir=img_dir)
        errs += e
        todo += t
    return errs, todo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-todo", action="store_true",
                    help="待译不算失败（原始语料刚落盘、译文未补时用）")
    a = ap.parse_args(argv)
    errs, todo = run()
    for p in errs:
        print(p)
    for p in todo:
        print(p)
    print(f"\n错误 {len(errs)} 条 / 待译 {len(todo)} 条", file=sys.stderr)
    if errs:
        return 1
    return 0 if (a.allow_todo or not todo) else 1


if __name__ == "__main__":
    raise SystemExit(main())
