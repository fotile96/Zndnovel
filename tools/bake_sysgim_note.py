#!/usr/bin/env python3
"""`sysgim` 的 E 类收尾五张：`sys_2_a`/`sys_3_a`（面板标题小注）与
`sys_12_a/b/c`（结算横幅大词）。

`bake_para_glow` 的**第 5 份 Spec**。版式与 `title_*` 同构——上层假名要换成中文、
下层英文原样保留——但底与晕都不同族：

- `sys_2_a`/`sys_3_a`：透明底，白字 + **黑**软晕；上方大标题的绿/红晕长 9–10px，
  正下方 1px 就是缩略图框（第三元素）。
- `sys_12_a`：底是**缓变梯度**（就地 alpha 232–242），走拉普斯拉重建。
- `sys_12_b`：底是**沙漏照片**，晕尾与照片纹理同量级，阈值判据全部失效，
  遮盖走足迹内拉普斯拉重建。
- `sys_12_c`：底纯平 `(0,0,0,204)`（实测 2600/2600 单值），平底填充。

遮盖判据是**几何足迹**而非强度阈值：逐保留层量一个保守半径（晕衰减到可见性
地板以下的距离），protect＝距离该层字芯 < 半径。为什么不再用强度判据——
2026-08-29 试过一版「逐图现量曲线当上界」，三轮修补把 `title_*` 的验证数字
打穿（残留 47→300+），整体回滚；几何半径量错只往安全侧偏（多保护→多残留，
可见、可量化），详见 `tools/bake_mask.py` 模块头与 `bake-handoff-2026-08-29b`。

译文五条全部已裁（`タイムオーバー`→**时间耗尽**为用户 2026-08-29 裁定，
备选记在数据 note 里）。

    uv run python tools/bake_sysgim_note.py
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
DATA = REPO / "data" / "sysgim_note_text.jsonl"

SPEC = Spec(face="sysgim", src=SRC, data=DATA, out=_out_dir("sysgim_note_zh"),
            mask_mode="geo_footprint", core_anchor=True, align="center")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="E 类收尾五张") else 0


if __name__ == "__main__":
    raise SystemExit(main())
