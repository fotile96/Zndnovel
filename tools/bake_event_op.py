#!/usr/bin/env python3
"""`png/event/op_*` 序章题词的中文烤字——`bake_para_glow` 的一份配置。

段落几何、居中、字号、`_b` 虚化的全部逻辑都在共用核心里；本模块只说明**这一面
是什么**，以及那些只对它成立的实测常量。

**为什么这一面不能用「一盒一行」。** 发光半径 `MAX_DIST=18` 与 op 的行距 18–19px
相当——邻行的晕必然进盒，逐行盒的远场永远不是纯背景。实测 15 个逐行盒有 4 个被底色
收敛检查拒绝（离底 6.5–65.9，容差 6），且放宽或收紧盒形都救不回来：

    op_3_a y[107,126)   原盒 6.5 → 全宽 6.5 → 上下各扩4 45.0 → 各扩8 8.6

**`_b` 不是独立内容。** 6 张里只有 3 张 `_a` 有译文；`_b` 是 `_a` 的虚化版，实测
高斯 r=1.5 即可重建（alpha 平均残差 0.4–0.5／满量程 255，墨迹 IoU 0.89–0.91）。

    uv run python tools/bake_event_op.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.bake_para_glow import (  # noqa: E402  （转出给测试与其他工具复用）
    LINE_MERGE_GAP, LINE_RATIO, Para, Spec, bake_file, choose_size, load_text,
    measure_para, run, segment_lines,
)

REPO = Path(_REPO)
SRC = REPO / "png" / "event"
DATA = REPO / "data" / "event_op_text.jsonl"

#: `_b` 的高斯模糊半径。**实测**：逐半径扫 1/1.5/2/2.5/3/4/5，r=1.5 时残差最小。
BLUR_RADIUS = 1.5

SPEC = Spec(face="event", src=SRC, data=DATA,
            out=_out_dir("event_zh"), blur_variant=BLUR_RADIUS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="序章题词") else 0


if __name__ == "__main__":
    raise SystemExit(main())
