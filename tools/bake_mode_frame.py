#!/usr/bin/env python3
"""`music_01_a` / `graphic_01_a` / `memory_01_a` 三张模式画面框——`bake_para_glow` 的一份配置。

三张是**同一套模板**：左上角一行白字红晕的日文提示（y[7,19]，高 12–13px），
其下一行英文大词（`- MUSIC SELECT -` / `- CG SELECT -` / `- SCENE SELECT -`）。

**盒只框日文那一行。** 英文按用户裁定原样保留，而它离日文只有 7px、发光半径
`MAX_DIST` 却是 18——两行的晕在盒里必然叠着。框两行就等于把英文也交给中文字体
重渲一遍，而那是原作的点阵形态，换任何字体都会走样。盒 `(0,0,200,24)` 三张
实测都过发光收敛检查，底色一律 `(255,255,255,0)`。

**`file` 带子目录**：三张分处 `png/music/` 与 `png/graphic/`，`src` 取两者的公共
父目录 `png/`，产物照搬那层子目录（`build/mode_zh/music/…`），回注时不必再猜。

**字体走 `sysgim` 面**，不另立新面：同一族 UI（白字芯 + 距离场发光）、同一档字号
（12–17px），而 sysgim 的字尚未定——这三张该跟着它一起定，不该各定各的。

    uv run python tools/bake_mode_frame.py
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
SRC = REPO / "png"
DATA = REPO / "data" / "mode_frame_text.jsonl"

SPEC = Spec(face="sysgim", src=SRC, data=DATA, out=_out_dir("mode_zh"),
            align="left", clip_to_box=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="模式画面框") else 0


if __name__ == "__main__":
    raise SystemExit(main())
