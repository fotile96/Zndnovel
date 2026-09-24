#!/usr/bin/env python3
"""谢幕『声』选择画面六张图——第二个故事的入口（docs/finale/draft-encore2-v0.md §1，D2/D12）。

序章 s0f L129–143 让玩家选直哉的『声』：eve_0_g 淡入 → eve_0_i 提示 → se_102 → eve_0_h 脚注 →
两枚 480×82 透明光晕按钮（comDlgSelectItem，无光标无暗场）。读过第一个谢幕故事之后再点 encore，
snr_finale.lua 的 finChooseStory() 用同一套画面让玩家选读哪一个故事：
- event/eve_0_j：提示「你的声音是——」（模板 eve_0_i；烤法同 bake_event_voice.bake_eve_0_i：eve_0_g 补底＋高斯光晕）
- event/eve_0_k：脚注「※两个故事都可以从 encore 再次进入」（模板 eve_0_h；擦框放宽到 (44,232,436,262)
  并羽化 4 px——原 (52,238,428,256) 硬边在成品里留下左端竖缝与右端浅色块，锚行落在原文光晕里；
  框内底图用 eve_0_g 按框外拟合压暗重建（eve_0_h≈0.556·eve_0_g），竖向插值会把背景斜向光带抹成平块）
- select/sel_fin1_sel_a_{on,off}：「……那，考考我吧」／副题「第一个故事：『放学后的讲述者』」
- select/sel_fin2_sel_a_{on,off}：「正看着这行文字的你，现在身处哪一年呢」／副题「第二个故事：『远方的朋友』」
  标题带「」引号、副题与脚注不加句号（用户 2026-09-25）；bake_select_voice.bake_one 同参数（20px 标题、13px 副题）。
产物：build/finale_voice/、build/finale_select/（manifest [gim].new 两面，模板 eve_0_i.gim / sel_voice1_sel_a_on.gim）
＋ docs/finale/assets/ 入库副本（只在缺省 root 下写）。

    uv run python tools/bake_finale_voice.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

_REPO = str(Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from tools import bake_event_voice as ev  # noqa: E402
from tools import bake_select_voice as sv  # noqa: E402
from tools.bake_out import out_dir  # noqa: E402

REPO = Path(_REPO)
FACE_EVENT = "finale_voice"
FACE_SELECT = "finale_select"
ASSETS = REPO / "docs" / "finale" / "assets"

PROMPT = ("eve_0_j", "你的声音是——")
FOOTNOTE = ("eve_0_k", "※两个故事都可以从 encore 再次进入", (44, 232, 436, 262), 4)
BUTTONS = [
    ("sel_fin1_sel_a", "「……那，考考我吧」", "第一个故事：『放学后的讲述者』"),
    ("sel_fin2_sel_a", "「正看着这行文字的你，现在身处哪一年呢」", "第二个故事：『远方的朋友』"),
]


def bake_all(root: Path | None = None) -> list[str]:
    """六张图写到 root/finale_voice 与 root/finale_select（root 缺省 build/，经 bake_out.out_dir、认 ZND_BUILD_TAG）；
    缺省 root 时另存 docs/finale/assets/ 副本。返回各工具的报告行。"""
    default = root is None
    out_event = out_dir(FACE_EVENT) if default else Path(root) / FACE_EVENT
    out_select = out_dir(FACE_SELECT) if default else Path(root) / FACE_SELECT
    out_event.mkdir(parents=True, exist_ok=True)
    out_select.mkdir(parents=True, exist_ok=True)
    report: list[str] = []
    name, text = PROMPT
    ev.bake_eve_0_i(True, report, text=text, out_name=name, out_dir=out_event)
    name, text, box, feather = FOOTNOTE
    ev.bake_eve_0_h(True, report, text=text, out_name=name, out_dir=out_event, box=box, feather=feather,
                    patch_src=ev.EVENT_DIR / "eve_0_g.png")
    for name, title, sub in BUTTONS:
        for variant in ("on", "off"):
            canvas = sv.bake_one(title, sub, variant, report, name)
            canvas.save(out_select / f"{name}_{variant}.png")
    if default:
        ASSETS.mkdir(parents=True, exist_ok=True)
        for p in sorted(out_event.glob("*.png")) + sorted(out_select.glob("*.png")):
            shutil.copyfile(p, ASSETS / p.name)
    return report


def main() -> None:
    for line in bake_all():
        print(line)
    print(f"finale_voice: 2 CG -> {out_dir(FACE_EVENT)}/；finale_select: 4 buttons -> {out_dir(FACE_SELECT)}/"
          f"（＋ docs/finale/assets/ 副本）")


if __name__ == "__main__":
    main()
