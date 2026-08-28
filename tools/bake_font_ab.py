#!/usr/bin/env python3
"""两套字体的逐面对照图 → `build/font_ab/<面>.png` + `build/font_ab/summary.md`。

**比的是已烤好的产物，不是现场重渲。** 各面的产物目录由 `ZND_BUILD_TAG` 分开
（见 `tools/bake_out.py`），本工具把两边同一位置的图裁出来上下并排。这样比的是
**真正会进游戏的那张图**——包含了字号级联、溢出回落、描边取色、发光重建在内的
全链路差异，而不只是"这个字长什么样"。

三行一组：

    原图（png/ 只读真图）
    A 版（默认目录 build/<面>，霞鹜文楷）
    B 版（build/<面>__<tag>，另一套字）

字号级联的差异单独出在 `summary.md` 里：换字体后哪些格从 18px 掉到 17px、
哪些溢出、哪些反而不用回落了——这些是数字，不该靠看图猜。

用法（先把两版都烤出来）：

    uv run python tools/bake_card.py                             # A 版
    ZND_UI_FONT=…/SourceHanSansSC-VF.ttf ZND_BUILD_TAG=shs \\
        uv run python tools/bake_card.py                         # B 版
    uv run python tools/bake_font_ab.py --tag shs
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.ui_font import truetype as _ui_truetype

OUT = REPO / "build" / "font_ab"
LABEL_W = 92


def _label_font(size=13):
    """标注用字体——**固定用随仓库分发的那套**，不受 ZND_UI_FONT 影响。

    否则你正在评估的字体会同时被用来写「A 版 / B 版」这些标签，两边的标注长得
    不一样，读图时反而分神。
    """
    saved = {k: os.environ.pop(k, None)
             for k in list(os.environ) if k.startswith("ZND_UI_FONT")}
    try:
        return _ui_truetype("select", size)
    finally:
        os.environ.update({k: v for k, v in saved.items() if v is not None})


# ---------------------------------------------------------------------------
# 各面怎么取样：有的产物是单张图，有的是整张格表要裁格
# ---------------------------------------------------------------------------


def _cells_card(_tag):
    picks = [10, 40, 46, 91, 125, 145, 178, 94]
    return [(f"卡 {c}", lambda d, c=c: d / f"crd_{c}_a.png") for c in picks]


def _cells_select(_tag):
    picks = ["sel_s6s_110_sel_a", "sel_s3s_230h_sel_a", "sel_s4s_170_sel_a",
             "sel_s2s_193c_sel_b", "sel_s1s_35_sel_a", "sel_s4fb_50_sel_a"]
    return [(b[4:], lambda d, b=b: d / f"{b}_on.png") for b in picks]


def _cells_sysgim(_tag):
    picks = ["sys_20_c", "sys_5_a", "sys_22_a", "sys_13_a", "sys_6_a", "sys_11_a"]
    return [(b, lambda d, b=b: d / f"{b}.png") for b in picks]


def _sheet_cropper(mod, cards, stem):
    """plot/scene：产物是整张格表，`cell_box` 给的是 (第几张, 格内矩形)。"""
    def make(card):
        def get(d: Path):
            sheet, box = mod.cell_box(card)
            return (d / f"{stem}_{sheet}_a.png", box)
        return get
    return [(f"卡 {c}", make(c)) for c in cards]


def _cells_plot(_tag):
    import tools.bake_plot as m
    return _sheet_cropper(m, [56, 162, 115, 170, 9], "plot")


def _cells_scene(_tag):
    import tools.bake_scene as m
    return _sheet_cropper(m, [1, 2, 89, 90, 178, 180, 182], "scene")


def _cells_cutin(_tag):
    """章节起止字幕卡。取样覆盖这一族的四种极端，而不是随手挑四张：

    `cut_s_s1` 常规开始卡（白字暖晕）／`cut_e_s1` 结束卡（**橙晕**，配色另一路）／
    `cut_s_ex2` 全族唯一的两行卡（21px 标题 + 13px 小注，字号差最大）／
    `cut_s_s82` 最短的一条（89px，字少，单字形态看得最清）。
    """
    picks = ["cut_s_s1", "cut_e_s1", "cut_s_ex2", "cut_s_s82"]
    return [(b, lambda d, b=b: d / f"{b}.png") for b in picks]


#: 面 -> (产物子目录, 取样函数, 放大倍数, 原图目录, 三联方向)
#:
#: 方向：宽而扁的格（select/scene/plot 条）上下叠着看最直接；卡面 212×148 又高又方，
#: 竖着叠六张就有一万四千像素高，没法看，故横排三联。
FACES = {
    "card":   ("card_zh",   _cells_card,   2, "png/card",   "cols"),
    "select": ("select_zh", _cells_select, 3, "png/select", "rows"),
    "scene":  ("scene_zh",  _cells_scene,  8, None,         "rows"),
    "plot":   ("plot_zh",   _cells_plot,   6, None,         "rows"),
    "sysgim": ("sysgim",    _cells_sysgim, 3, "png/sysgim", "cols"),
    "cutin":  ("cutin_zh",  _cells_cutin,  2, "png/cutin",  "rows"),
}


def _load(spec, d: Path):
    """取一格：可能是整张图，也可能是 (整张图, 裁框)。"""
    got = spec(d)
    if isinstance(got, tuple):
        path, box = got
        if not path.exists():
            return None
        return Image.open(path).convert("RGBA").crop(box)
    return Image.open(got).convert("RGBA") if got.exists() else None


def _orig_for(face, spec):
    """原图：从只读的 png/ 里取同一格。"""
    src = FACES[face][3] or {"plot": "png/plot", "scene": "png/scene"}[face]
    return _load(spec, REPO / src)


def _trio_rows(trio, name, scale, font):
    """三联上下叠：每行左侧一条文字标签。"""
    out = []
    for lab, img in trio:
        big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        row = Image.new("RGBA", (LABEL_W + big.width, big.height), (26, 26, 26, 255))
        row.alpha_composite(big, (LABEL_W, 0))
        ImageDraw.Draw(row).text((5, max(2, big.height // 2 - 8)),
                                 f"{name}\n{lab}" if lab == "原图" else lab,
                                 font=font, fill=(225, 225, 225, 255))
        out.append(row)
    return out


def _trio_col(trio, name, scale, font):
    """三联横排：一行三格，格上方各写一个标题。"""
    pad, head = 6, 18
    bigs = [(lab, im.resize((im.width * scale, im.height * scale), Image.NEAREST))
            for lab, im in trio]
    w = sum(b.width + pad for _l, b in bigs) + LABEL_W
    h = max(b.height for _l, b in bigs) + head + pad
    row = Image.new("RGBA", (w, h), (26, 26, 26, 255))
    d = ImageDraw.Draw(row)
    d.text((5, h // 2 - 8), name, font=font, fill=(225, 225, 225, 255))
    x = LABEL_W
    for lab, b in bigs:
        d.text((x + 2, 2), lab, font=font, fill=(200, 200, 200, 255))
        row.alpha_composite(b, (x, head))
        x += b.width + pad
    return [row]


def build_face(face: str, tags: list[str]) -> Image.Image | None:
    sub, cells_fn, scale, _orig, layout = FACES[face]
    dirs = [("霞鹜文楷", REPO / "build" / sub)]
    for t in tags:
        d = REPO / "build" / f"{sub}__{t}"
        if d.exists():
            dirs.append((t, d))
        else:
            print(f"  {face}: 跳过标签 {t}（{d} 不存在）")
    if len(dirs) < 2:
        return None

    font = _label_font()
    make = _trio_col if layout == "cols" else _trio_rows
    rows = []
    for name, spec in cells_fn(tags):
        trio = [("原图", _orig_for(face, spec))]
        trio += [(lab, _load(spec, d)) for lab, d in dirs]
        if any(img is None for _l, img in trio):
            print(f"    {face}/{name}: 有版本缺图，跳过")
            continue
        rows += make(trio, name, scale, font)
        rows.append(None)

    if not any(r is not None for r in rows):
        print(f"  跳过 {face}：没取到可比的格")
        return None
    gap, width = 12, max(r.width for r in rows if r is not None)
    height = sum(gap if r is None else r.height for r in rows)
    sheet = Image.new("RGBA", (width, height), (16, 16, 16, 255))
    y = 0
    for r in rows:
        if r is None:
            y += gap
            continue
        sheet.paste(r, (0, y))
        y += r.height
    return sheet


# ---------------------------------------------------------------------------
# 数字差异：字号级联、溢出、回落——看图看不出来的那部分
# ---------------------------------------------------------------------------

def _manifest(d: Path):
    p = d / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _count(v):
    if v is None:
        return None
    return len(v) if isinstance(v, list) else sum(len(x) for x in v.values())


def _size_hist(d: Path) -> str:
    """实际用了哪些字号档、各多少格——比「回落了几条」更能说明代价。"""
    import collections
    for name, key in (("manifest.json", "button_font_sizes"),
                      ("manifest.json", "cell_font_sizes")):
        m = _manifest(d)
        if m and key in m:
            h = collections.Counter(m[key].values())
            return " ".join(f"{s}px×{n}" for s, n in sorted(h.items(), reverse=True))
    return "—"


def summarize(tags: list[str]) -> str:
    cols = ["霞鹜文楷"] + list(tags)
    lines = ["# 换字体的数字差异", "",
             "基准＝`build/<面>`（霞鹜文楷 Regular）；其余＝`build/<面>__<标签>`。", "",
             "| 面 | 指标 | " + " | ".join(cols) + " |",
             "|---|---|" + "---:|" * len(cols)]
    for face, (sub, *_rest) in FACES.items():
        dirs = [REPO / "build" / sub] + [REPO / "build" / f"{sub}__{t}" for t in tags]
        ms = [_manifest(d) for d in dirs]
        if not all(ms):
            continue
        for key, label in (("fallbacks", "字号回落"), ("overflow", "溢出"),
                           ("pixel_preservation_violations", "盒外像素改动")):
            vals = [_count(m.get(key)) for m in ms]
            if any(v is None for v in vals):
                continue
            mark = "" if len(set(vals)) == 1 else "  ⚠"
            lines.append(f"| `{face}` | {label} | " + " | ".join(str(v) for v in vals) + f"{mark} |")
        hist = [_size_hist(d) for d in dirs]
        if any(h != "—" for h in hist):
            lines.append(f"| `{face}` | 字号分布 | " + " | ".join(hist) + " |")
    lines += ["", "⚠ 标记＝各版不同。字号回落变多意味着这套字在同档下更宽或更高，",
              "游戏内可读性会随之下降；溢出或盒外像素改动**任何一版不为 0 都是缺陷**，",
              "不是风格问题。", "",
              "「字号分布」比「回落了几条」更实在：回落只说明降过档，分布直接说明",
              "**最终有多少格落在哪一档**——两套字的回落数一样、分布可以完全不同。"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", nargs="+", default=["shs"],
                    help="要并排比的 ZND_BUILD_TAG，可给多个（顺序即出图顺序）")
    ap.add_argument("--faces", nargs="*", default=list(FACES))
    a = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    for face in a.faces:
        sheet = build_face(face, a.tag)
        if sheet is None:
            continue
        p = OUT / f"{face}.png"
        sheet.save(p)
        print(f"  {face:<8} -> {p}  ({sheet.width}x{sheet.height})")
    (OUT / "summary.md").write_text(summarize(a.tag), encoding="utf-8")
    print(f"  数字差异 -> {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
