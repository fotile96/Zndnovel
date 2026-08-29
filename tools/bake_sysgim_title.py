#!/usr/bin/env python3
"""`sysgim/title_02_a`…`title_13_a` —— 主菜单 12 个菜单项的青色假名小注。

`bake_para_glow` 的**第 4 份 Spec**（继 event/op、cutin 字幕卡、模式画面框之后）。

**版式**：每张含两个状态上下叠放——上为暗态（纯英文），下为亮态（英文 + 青色假名
小注）。**只换假名层，英文一律不动**（用户裁定），故 `clip_to_box=True`。

**盒是量出来的**，判据是「小注与英文蓝晕的颜色分离」：小注是青绿系
`(36,119,160)`–`(146,188,208)`，**G−R 达 42–83**；亮态英文的蓝晕是 `(33,32,253)` 一族，
**G−R ≈ 0**。故取 `G − R > 25 且 B ≥ G`。先试过「B>R+40」——那把英文的晕整片圈了
进来（title_02_a 命中 1286 个像素、覆盖全图），是判据太松而不是素材不好。
逐张盒见 `docs/ops/bake-sysgim-inventory.md` 的「E 类版面测绘」节。

12 张的底一律 `(255,255,255,0)`（透明），发光模型全部通过收敛检查。

    uv run python tools/bake_sysgim_title.py
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
SRC = REPO / "png" / "sysgim"
DATA = REPO / "data" / "sysgim_title_text.jsonl"

#: 居中：小注是英文大词的注脚，复现原文墨迹的**重心**即可保持它相对英文的位置
#: （07–12 那几张小注在英文左侧，重心复现同样成立）。
SPEC = Spec(face="sysgim", src=SRC, data=DATA, out=_out_dir("sysgim_title_zh"),
            clip_to_box=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="主菜单项假名小注") else 0


if __name__ == "__main__":
    raise SystemExit(main())
