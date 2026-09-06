#!/usr/bin/env python3
"""`select/sel_map_0_a`——探索地图底栏的两处提示，`bake_para_glow` 的一份配置。

这张 480×42 的底栏贴在 `comSelectMap` 画面底部（`snr_common.lua`：
`layerPosition(l1_10.info, 0, 230)`），s1s_200_sel 等五个探索场景共用。图上有：

- 左上「移動場所を選択してください。」——白芯 12px + 红色距离晕，晕向下铺到第 29 行；
- 其下一行英文「- MAP SELECT -」——白字黑软阴影，**原样保留**（同 `sys_11_a` 的
  CARD SELECT 与三张模式画面框：只换日文那一层，英文一个像素不动）；
- 右侧「現在位置」——浅色芯 11px + 暗红晕，约 6px 归零；
- 右端深色框——运行时被 `sel_map_1_a` 的 120×26 地点条整块盖住
  （`layerPosition(l1_10.map, 356, 246)` ＝ 本图的 (356,16)），不烤。

**为什么走几何足迹遮盖而不是裁盒。** 模式画面框那三张也是「日文提示 + 英文小注」，
它们裁盒到日文行底、把 α≤11 的晕尾留给英文行就够了。这张的红晕强得多：第 25 行
（英文阴影起始行）旧晕 α 峰值 41、英文正下方 61，而中文只有 10 字、比 15 字的日文短，
裁盒会把旧晕的尾巴留在新字右边。`geo_footprint`（`tools/bake_mask.plan_geo`）按旧墨的
足迹半径擦、按英文字芯的半径保护，嵌字框与遮盖框各管各的。geo 参数逐项写在数据行里，
数字出自 2026-09-06 的实测（复核见 tests/test_bake_select_map_info.py）。

**字体走 `sysgim` 面**：与同模板的三张模式框（music/graphic/memory 的「○○を選択して
ください。」）同字同号。产物落 `build/select_zh/`，由 `layers/manifest.toml` 的
`[gim].replace` 表随 `sel_map_1_a` 一起回注到封包的 `select/`，不必改清单。

    uv run python tools/bake_select_map_info.py
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
SRC = REPO / "png" / "select"
DATA = REPO / "data" / "select_map_info_text.jsonl"

#: **整张统一 13px**（裁决 Y7：一张图一个字号），不走自动选号。自动选号按 `_core_mask`
#: 的高度卡在原行高之下，这张会落到提示 12px／「当前位置」11px——但那把尺子比产物里
#: α≥217 的白芯高约 2 行：12px 渲出的白芯只有 11 行（日文 12 行），11px 的「当前位置」
#: 只有 10 行、宽 41（日文 11 行、宽 53）。13px 时白芯 12 行／12 行、宽 115／49，与日文
#: 同高、与三张模式框（13/14px）同档。2026-09-06 原图/自动/13/14 四档对照后定。
SPEC = Spec(face="sysgim", src=SRC, data=DATA, out=_out_dir("select_zh"),
            align="left", mask_mode="geo_footprint", force_size=13)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="探索地图底栏") else 0


if __name__ == "__main__":
    raise SystemExit(main())
