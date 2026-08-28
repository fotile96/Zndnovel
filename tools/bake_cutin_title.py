#!/usr/bin/env python3
"""`png/cutin/{cut_e_*,cut_s_*}` 章节起止字幕卡的中文烤字——`bake_para_glow` 的一份配置。

24 张：`cut_s_*` 14 张是章节开始卡（白字暖晕，带视点人物名），`cut_e_*` 10 张是
章节结束卡（**橙晕**，配色与前者不同——模型逐图实测底与环，不受影响）。

**这一批几乎不需要新译。** 24 张里 23 张在 lua 里有同一个字符串，作为
`scene_*(doScriptScene, "セクション１：アヤノ")` 的场景标题参数（带 `tr_line` 标记，
由引擎字体实时渲染）——也就是说**同一个逻辑串有两个载体**，lua 那份早就译了，
图这份没有。两处必须一致，否则玩家会在同一屏看到同一章节标签的两种写法。

来源分布：冻结骨架 10 张、`data/extra_translated.jsonl` 3 张、按同族格式推得 1 张
（`cut_s_ex21`）、依既有定译推得 10 张（`cut_e_*` 的 `X：おわり → X：完`）。

**盒＝整张图。** 这些是紧凑文字条（89×34 ~ 319×54），墨迹几乎填满画布，
四周留 1–8px 透明边——足够发光模型从盒边框取到底色。

**`cut_s_ex2` 是唯一的两行卡**（大字标题 21px + 小字注 13px）。它逼出了共用核心里
两处设定：`LINE_MERGE_GAP` 必须 ≤3（两行只隔 3px 空行，取 4 会并成一行），
以及**逐行字号**（行高差 8px 远超噪声，取中位数会把小字注渲成大字）。

    uv run python tools/bake_cutin_title.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.bake_para_glow import Spec, run  # noqa: E402

REPO = Path(_REPO)
SRC = REPO / "png" / "cutin"
DATA = REPO / "data" / "cutin_title_text.jsonl"

#: 无 `_b` 虚化版——这一族只有一张图，不像 `event/op_*` 有失焦转场。
SPEC = Spec(face="cutin", src=SRC, data=DATA, out=_out_dir("cutin_zh"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="章节起止字幕卡") else 0


if __name__ == "__main__":
    raise SystemExit(main())
