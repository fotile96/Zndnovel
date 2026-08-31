#!/usr/bin/env python3
"""主菜单谢幕项 title_14_a 底图拼接——encore 字形移植。

按 docs/finale/mainmenu-entry-plan.md §5 的两步路线之第一步：
从 title_13_a（Section 7）与 title_02_a（Prologue）的同字号小写字库中
等大剪贴 e/n/c/o/r 字形，拼出上（暗态）下（亮态）双态的大词 `encore`，
下半再原样移植 title_13 的小注条『- セクション7 -』作**捐赠注**占位。
第二步在同一次运行里完成：把捐赠注态源图连同单行 jsonl 喂给
bake_para_glow（与 bake_sysgim_title 同款 Spec），遮掉捐赠注、烤上
『- 谢幕 -』——注盒＝title_13 实测盒 [47,56,115,65] 随贴图平移 −31px。

字形盒与词行窗口来自逐列/逐行强像素（alpha>200）投影实测（GLYPHS /
WINDOWS / BASELINE 表）；r 取 Prologue 的 ro 连段左半、切割列钉死在
[18,24)（x17/24-25 分别是 P 升部与 o 的横向光晕渗入列，一并舍弃），
窗口再收顶以避开 P 顶部光晕。lower 态一律裁
**词行窗口**而非整半区——半区里还躺着小注行，整裁会混入注的像素。
输出：docs/finale/assets/title_14_a_src.png ＋ build/finale_menu/ 3x 目检图。
不触碰 png/sysgim/ 原件。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from PIL import Image

SRC13 = REPO / "png" / "sysgim" / "title_13_a.png"   # Section 7
SRC02 = REPO / "png" / "sysgim" / "title_02_a.png"   # Prologue（r 的捐赠源——
# library 实测 x-height 仅 9px 与 Section7 的 13px 不同档，plan §5 的"等大"在 r 上失实；
# Prologue 与 Section7 同字号（x-height 13、上半基线同为 20），r 取其 ro 连段左半）
OUT_SRC = REPO / "docs" / "finale" / "assets" / "title_14_a.png"   # 管线按 file 名寻图，即源图名
NOTE_JSONL = REPO / "docs" / "finale" / "assets" / "title_14_note.jsonl"
OUT_DBG = REPO / "build" / "finale_menu"

W, H, SPLIT = 100, 68, 34          # 新图规格（plan §5：偶数高，分界 y=34）
KERN = 2                            # 原词相邻字形段间距实测 ≈2px

# 字形盒 (src, x0, x1)。title_13 上/下半词芯 x 段实测一致。
GLYPHS = {
    "e": ("13", 16, 27),
    "n": ("13", 70, 81),
    "c": ("13", 29, 39),
    "o": ("13", 55, 67),
    "r": ("02", 18, 24),
}
WORD = "encore"

# 词行裁剪窗口 (src,state) -> (y0,y1)：含光晕、不含小注行。
WINDOWS = {
    ("13", "up"): (0, 24),  ("02", "up"): (7, 24),
    ("13", "lo"): (32, 56), ("02", "lo"): (42, 56),
}
# 词芯强像素基线（bottom，实测）：贴图时平移对齐，抵消源图排版差。
BASELINE = {("13", "up"): 20, ("02", "up"): 20,
            ("13", "lo"): 55, ("02", "lo"): 56}
TARGET_BASE = {"up": 20, "lo": 20 + SPLIT}   # 新图两态基线（沿 title_13 上半位）

NOTE_BOX = (47, 56, 115, 66)   # title_13 下半小注条『- セクション7 -』


def main():
    imgs = {"13": Image.open(SRC13).convert("RGBA"),
            "02": Image.open(SRC02).convert("RGBA")}
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    word_w = sum(GLYPHS[ch][2] - GLYPHS[ch][1] for ch in WORD) + KERN * (len(WORD) - 1)
    x_start = (W - word_w) // 2
    print(f"word width={word_w}, x_start={x_start}")

    for state in ("up", "lo"):
        x = x_start
        for ch in WORD:
            src, x0, x1 = GLYPHS[ch]
            y0, y1 = WINDOWS[(src, state)]
            tile = imgs[src].crop((x0, y0, x1, y1))
            y_paste = TARGET_BASE[state] - BASELINE[(src, state)] + y0
            canvas.alpha_composite(tile, (x, y_paste))
            x += tile.size[0] + KERN

    # 捐赠注：title_13 下半注条整条移植，横向随词居中、纵向保持半区内原位
    note = imgs["13"].crop(NOTE_BOX)
    note_x = (W - note.size[0]) // 2
    note_y = NOTE_BOX[1]                     # 56：两图分界同为 34，半区内原位即同 y
    canvas.alpha_composite(note, (note_x, note_y))
    print(f"note pasted at ({note_x},{note_y}) size={note.size}")

    OUT_SRC.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT_SRC)
    OUT_DBG.mkdir(parents=True, exist_ok=True)
    canvas.resize((W * 3, H * 3), Image.NEAREST).save(OUT_DBG / "title_14_a_src_3x.png")
    ref = imgs["13"]
    combo = Image.new("RGBA", ((ref.size[0] + W + 12) * 3, max(ref.size[1], H) * 3), (24, 24, 24, 255))
    combo.alpha_composite(ref.resize((ref.size[0] * 3, ref.size[1] * 3), Image.NEAREST), (0, 0))
    combo.alpha_composite(canvas.resize((W * 3, H * 3), Image.NEAREST), ((ref.size[0] + 12) * 3, 0))
    combo.save(OUT_DBG / "compare_3x.png")
    print(f"src -> {OUT_SRC}")

    # ── 第二步：捐赠注 → 『- 谢幕 -』（bake_para_glow 管线，Spec 同 bake_sysgim_title）
    import json
    from tools.bake_para_glow import Spec, run
    note_row = {"file": "title_14_a", "row": 0, "box": [16, 56, 84, 65],
                "jp": "- セクション7 -", "zh": "- 谢幕 -",
                "note": "谢幕菜单项。盒＝title_13 注盒 [47,56,115,65] 平移 dx=-31（捐赠注贴于 x16）。"}
    NOTE_JSONL.write_text(json.dumps(note_row, ensure_ascii=False) + "\n", encoding="utf-8")
    spec = Spec(face="sysgim", src=OUT_SRC.parent, data=NOTE_JSONL, out=OUT_DBG,
                mask_mode="glow_footprint", core_anchor=True)
    bad = run(spec, write=True, label="谢幕菜单项小注")
    final = Image.open(OUT_DBG / "title_14_a.png").convert("RGBA")
    combo2 = Image.new("RGBA", ((ref.size[0] + W + 12) * 3, max(ref.size[1], H) * 3), (24, 24, 24, 255))
    combo2.alpha_composite(ref.resize((ref.size[0] * 3, ref.size[1] * 3), Image.NEAREST), (0, 0))
    combo2.alpha_composite(final.resize((W * 3, H * 3), Image.NEAREST), ((ref.size[0] + 12) * 3, 0))
    combo2.save(OUT_DBG / "final_compare_3x.png")
    print(f"final -> {OUT_DBG}/title_14_a.png  (bad={bad})")


if __name__ == "__main__":
    main()
