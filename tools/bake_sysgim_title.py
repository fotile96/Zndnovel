#!/usr/bin/env python3
"""`sysgim/title_02_a`…`title_13_a` —— 主菜单 12 个菜单项的青色假名小注。

`bake_para_glow` 的**第 4 份 Spec**（继 event/op、cutin 字幕卡、模式画面框之后）。

**版式**：每张含两个状态上下叠放——上为暗态（纯英文），下为亮态（英文 + 青色假名
小注）。**只动假名层，英文一律不动**（用户裁定），故 `clip_to_box=True`。

## 为什么这一族只擦不写

12 张全部走 `erase`（数据行 `zh` 为空 + `erase: true`）：**抹掉日文小注，不放中文**。
成品因此是「英文大词 + 空白」，相对原图只少了那行假名。

理由是像素预算，不是字体或字重问题。小注墨迹只有 **7–10px 高**，而中文注多为四字
（「故事目录」约 30 笔），在这个高度上换任何字体都糊成一团——2026-09-01 实测思源黑体
Medium/Bold × 抬档 0/1 四种组合与霞鹜文楷**无可辨差异**，缩短成两字也只是留白变多。
先前为补霞鹜细笔而给这一族挂的 2.2 填充增益，同样只是让那团糊变亮。

于是取舍从「哪种中文渲法最好」变成「有没有中文更好」。用户 2026-09-01 裁定：去掉。
英文大词（Prologue / Story / Fragment / library / option …）本就是原版版式的一半，
对中文玩家可读，留白也比一团糊干净。

⚠ **这是本族独有的裁定，不要外推。** 全局体例仍是「英文大词 + 中文小注」；
同族只是恰好撞上了 7px 这个下限。字号够大的面（cutin 15–21px、卡面 9px 正文）
不适用——那里中文渲得清楚，删掉就是丢信息。

⚠ 撤下的 12 条中文小注**逐张记在数据行的 `note` 里**（不是只在 git 历史里）：
翻案时要能直接拿回来，不必重译，也不必再走一遍术语闸。

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
#:
#: `mask_mode`：遮盖与嵌字分两步、两个框。数据里的 `box` 只当**嵌字框**（字多大、
#: 落在哪）；遮盖另按实测的发光足迹算矩形。先前一个框两用，收紧到嵌字合适就盖不住
#: 小注的晕（产物上一圈矩形亮边）、放大到盖得住就压到英文——**那个框不存在**。
SPEC = Spec(face="sysgim", src=SRC, data=DATA, out=_out_dir("sysgim_title_zh"),
            mask_mode="glow_footprint", core_anchor=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    a = ap.parse_args(argv)
    return 1 if run(SPEC, write=not a.check, label="主菜单项假名小注") else 0


if __name__ == "__main__":
    raise SystemExit(main())
