#!/usr/bin/env python3
"""`png/plot/` 缩略图的「干净底板」烤字（方案 B）——按逐卡冻结的配方重建每格的底板，再烤中文标题。

原缩略图 = 0.5 × 游戏画面（bg / event CG / bg+立绘）→ BILINEAR 缩到 82×48 → 全表 256 色板
（`docs/ops/plot-plate-research-2026-09-07.md`：色调倍率 98 格实测 0.493±0.02，滤镜不可分辨，
量化地板 RMSE≈4）。`tools/bake_plot.py` 用色带盖住原文再写中文，画面上半格被遮；本工具改为
**重建没有原文的底板**，中文标题直接压在画面上，观感与原版一致。

配方在 `data/plot_plates.jsonl`，逐卡一行：
    {"card": 7, "kind": "compose", "layers": [{"layer": "bg1", "kind": "bg", "name": "bg_1_a_0", "x": 0, "y": 0},
      {"layer": "pose1", "kind": "pose", "name": "po1_aya_s_1_a", "x": -2, "y": -6}], "tone": 0.5, "verify_rmse": 5.5, "note": "…"}
    kind: single（单张 bg/event 直缩）| compose（多层合成）| flat（纯黑底板，取 flat 格中位数）| band（走 bake_plot 色带兜底）
    可选：layers[].scale=[w,h]（先缩放素材）、layers[].fill="edge"（素材边缘延伸铺满画布）、
    crop=[x0,y0,x1,y1]（整帧先裁再缩，可含小数）、title="none"（不压中文，logo 板）、black=true（flat 纯黑变体）

**闸**：single/compose 的底板在烤字前对照**原格无字行**算 RMSE（底板原样，不做拟合），超过
`GATE_RMSE` 直接拒绝出活——配方表自述的 `verify_rmse` 不算数，素材或配方漂移必须当场现形
（与 `card/` 面的重建闸 C5 同型）。`REVIEW_RMSE` 以上的格在 manifest 里列为 review，供看图。

纯 Pillow 实现（本仓库工具链不带 numpy）。

    uv run python tools/bake_plot_plate.py            # 写 build/plot_zh/plot_{1..4}_a.png + manifest.json + _compare.png
    uv run python tools/bake_plot_plate.py --check    # 只算、只报告
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from functools import lru_cache

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools import bake_plot as bp  # noqa: E402
from tools.bake_out import out_dir as _out_dir  # noqa: E402
from tools.ui_font import truetype as _ui_truetype  # noqa: E402

PLATES_PATH = os.path.join(REPO, "data", "plot_plates.jsonl")
OUT_DIR = str(_out_dir("plot_zh"))
SCREEN = (480, 272)
THUMB = (bp.CELL_W, bp.CELL_H)

#: 闸：底板与原格无字行的 RMSE 上限。量化地板 ≈4；≤6 同一张画；≤10 同画面、立绘细节有差；
#: 10–12 仍是同一场景。超过 12 的配方不出活（回退 band 要写进数据，不能静默）。
GATE_RMSE = 12.0
#: 复核线：以上的格在 manifest 里列出，供人看拼图。
REVIEW_RMSE = 8.0
#: 无字行起点：日文标题一行 y≥14，两行 y≥26（spec §4：line1 y3–11，line2 y15–23）。
TEXT_FREE_ROW = {1: 14, 2: 26}
#: 纯黑底板：上 24 行全黑（行间空白实测为 0），下 24 行取 flat 格的中位数。
FLAT_TOP_ROWS = 24

#: 图层 z 序（snr_common.lua 的 layerName 编号；event 与 bg1 同为 0＝同一槽）。只给生成配方的
#: 脚本做稳定排序用；compose_layers 本身按数据里的列表顺序绘制。
LAYER_Z = {"event": 0, "bg1": 0, "bg2": 1, "bg3": 2, "bg4": 3, "bg5": 4,
           "pose1": 5, "pose2": 6, "pose3": 7, "pose4": 8, "pose5": 9, "swap": 10, "pose6": 11}


def load_plates(path: str = PLATES_PATH) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r["card"] in rows:
                raise ValueError(f"{path}:{n}: card {r['card']} 重复")
            rows[r["card"]] = r
    return rows


def load_titles_jp():
    return bp.load_titles_jp()


@lru_cache(maxsize=None)
def _asset(kind: str, name: str) -> Image.Image:
    return Image.open(os.path.join(REPO, "png", kind, f"{name}.png")).convert("RGBA")


def compose_layers(layers: list[dict]) -> Image.Image:
    """按 z 序把各层贴到 480×272 黑底上（立绘画布 480×300/320，贴在 (x,y)，越界裁掉）。

    可选字段：`scale: [w, h]` 先把素材缩放到该尺寸（卡 162 的 logo 板）；`fill: "edge"`
    在贴图之前用素材的边缘行/列把整块画布填满——用于原缩略图里 bg 比脚本位置低几像素、
    露出的顶部是天空而不是黑的那种格（卡 77/78 的 bg_11_b_0 低 11 px）。
    """
    scr = Image.new("RGBA", SCREEN, (0, 0, 0, 255))
    # 列表顺序即绘制顺序（先写的在底）。引擎里 event 与 bg1 是同一图层槽（编号都是 0），
    # 谁后加载谁可见——这层语义只在「加载顺序」里，所以数据把顺序定死，这里不再按 z 重排。
    for l in layers:
        if l["kind"] == "solid":
            im = Image.new("RGBA", SCREEN, tuple(l["rgb"]) + (255,))
        else:
            im = _asset(l["kind"], l["name"])
        if l.get("scale"):
            im = im.resize((int(l["scale"][0]), int(l["scale"][1])), Image.BILINEAR)
        x, y = int(l.get("x", 0)), int(l.get("y", 0))
        layer = Image.new("RGBA", SCREEN, (0, 0, 0, 0))
        if l.get("fill") == "edge":
            # 画布先铺满素材的边缘延伸（上下用首/末行，左右用首/末列），再贴素材本体
            w, h = im.size
            if y > 0:
                layer.paste(im.crop((0, 0, w, 1)).resize((w, y)), (x, 0))
            if y + h < SCREEN[1]:
                layer.paste(im.crop((0, h - 1, w, h)).resize((w, SCREEN[1] - y - h)), (x, y + h))
            if x > 0:
                layer.paste(im.crop((0, 0, 1, h)).resize((x, h)), (0, y))
            if x + w < SCREEN[0]:
                layer.paste(im.crop((w - 1, 0, w, h)).resize((SCREEN[0] - x - w, h)), (x + w, y))
        layer.paste(im, (x, y))          # 不带掩膜：整块拷入（含 alpha），alpha 混合交给 alpha_composite
        scr.alpha_composite(layer)
    return scr.convert("RGB")


def _tone(im: Image.Image, tone: float) -> Image.Image:
    lut = [int(round(v * tone)) for v in range(256)]
    return im.convert("RGB").point(lut * 3)


@lru_cache(maxsize=None)
def _orig_sheet(sheet: int) -> Image.Image:
    return Image.open(os.path.join(bp.PLOT_DIR, f"plot_{sheet}_a.png")).convert("RGBA")


def orig_cell(card: int) -> Image.Image:
    s, box = bp.cell_box(card)
    return _orig_sheet(s).crop(box)


@lru_cache(maxsize=None)
def flat_plate() -> Image.Image:
    """纯黑底板：flat 格的逐像素中位数（下 24 行），上 24 行全黑。"""
    rows = load_plates()
    cards = [c for c, r in rows.items() if r["kind"] == "flat" and not r.get("black")]
    if not cards:
        raise ValueError("配方表里没有 flat 格，无法取中位数板")
    datas = [list(orig_cell(c).convert("RGB").getdata()) for c in cards]
    w, h = THUMB
    out = Image.new("RGB", THUMB, (0, 0, 0))
    px = out.load()
    n = len(datas)
    for y in range(FLAT_TOP_ROWS, h):
        for x in range(w):
            i = y * w + x
            vals = []
            for ch in range(3):
                col = sorted(d[i][ch] for d in datas)
                med = col[n // 2] if n % 2 else (col[n // 2 - 1] + col[n // 2]) / 2
                vals.append(int(round(med)))
            px[x, y] = tuple(vals)
    return out


def build_plate(row: dict) -> Image.Image:
    """配方 → 82×48 RGB 底板（已按 tone 变暗；band 格没有底板）。"""
    kind = row["kind"]
    if kind == "flat":
        if row.get("black"):
            return Image.new("RGB", THUMB, (0, 0, 0))   # 开场即黑屏的格：整格纯黑，无底部淡光
        return flat_plate()
    if kind in ("single", "compose"):
        tone = float(row.get("tone", 0.5))
        scr = compose_layers(row["layers"])
        # `crop: [x0, y0, x1, y1]`（可含小数）：先裁再缩。卡 56/82 的走廊格是整帧 1.035× 居中放大
        # （裁 (7,3.5)-(472,266.5)），没有任何脚本状态能产生，是当年截图的裁切。
        box = tuple(float(v) for v in row["crop"]) if row.get("crop") else None
        return _tone(scr.resize(THUMB, Image.BILINEAR, box=box), tone)
    raise ValueError(f"kind={kind!r} 没有底板")


def text_free_row(card: int, titles_jp=None) -> int:
    titles_jp = titles_jp or load_titles_jp()
    return TEXT_FREE_ROW[bp.jp_line_count(titles_jp[card])]


def rmse_rows(a: Image.Image, b: Image.Image, y0: int) -> float:
    """两图从第 y0 行起到底的 RMSE（RGB 三通道一起算）。"""
    w, h = a.size
    pa = list(a.convert("RGB").crop((0, y0, w, h)).getdata())
    pb = list(b.convert("RGB").crop((0, y0, w, h)).getdata())
    se = 0
    for p, q in zip(pa, pb):
        se += (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
    return math.sqrt(se / (len(pa) * 3))


def verify_plate(plate: Image.Image, orig: Image.Image, card: int, titles_jp=None) -> float:
    """底板原样（不拟合）对照原格无字行的 RMSE。"""
    return rmse_rows(plate, orig, text_free_row(card, titles_jp))


#: 宽掩膜与窄掩膜的差距线：宽比窄大过它就进复核——差距大＝**标题区底下**与画面其余部分不一致，
#: 而标题区正是我们要替换的地方（测量审计 2026-09-07）。
WIDE_GAP = 3.0
#: 局部异物线：无字行里任一 3 行窗口的 RMSE 超过它就进复核（测量审计 2026-09-07 的建议——
#: 整格 RMSE 低不代表没有局部错位/多出来的东西，均值会把它摊平）。
LOCAL_BAND_RMSE = 20.0


def ink_mask(orig: Image.Image, dilate: int = 2) -> list[list[bool]]:
    """原格里「标题墨迹」的逐像素掩膜：近白（min≥200）且 2px 内有近黑（max≤40），再膨胀 `dilate`。

    与 `bake_plot.ink_bbox_of_cell` 同一条判据（亮 + 邻近暗才算墨），只是这里要的是**逐像素**
    而不是纵向范围：宽掩膜要把字间与行间的空隙留出来量。
    """
    px = orig.convert("RGB").load()
    w, h = orig.size
    dark = [[max(px[x, y]) <= 40 for x in range(w)] for y in range(h)]
    core = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if min(px[x, y]) < 200:
                continue
            if any(dark[yy][xx] for yy in range(max(0, y - 2), min(h, y + 3))
                   for xx in range(max(0, x - 2), min(w, x + 3))):
                core[y][x] = True
    out = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if any(core[yy][xx] for yy in range(max(0, y - dilate), min(h, y + dilate + 1))
                   for xx in range(max(0, x - dilate), min(w, x + dilate + 1))):
                out[y][x] = True
    return out


def wide_rmse(plate: Image.Image, orig: Image.Image, card: int, mask=None) -> float:
    """底板对照原格**所有非墨迹像素**的 RMSE（含标题区的字间/行间空隙与顶行）。"""
    m = ink_mask(orig) if mask is None else mask
    pa = plate.convert("RGB").load()
    pb = orig.convert("RGB").load()
    w, h = plate.size
    se = n = 0
    for y in range(h):
        for x in range(w):
            if m[y][x]:
                continue
            p, q = pa[x, y], pb[x, y]
            se += (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
            n += 3
    return math.sqrt(se / n) if n else 0.0


def local_band_rmse(plate: Image.Image, orig: Image.Image, card: int, titles_jp=None, rows: int = 3) -> float:
    """无字行里 `rows` 行滑窗的最大 RMSE。"""
    y0 = text_free_row(card, titles_jp)
    w, h = plate.size
    pa = list(plate.convert("RGB").getdata()); pb = list(orig.convert("RGB").getdata())
    worst = 0.0
    for top in range(y0, h - rows + 1):
        se = 0
        for y in range(top, top + rows):
            for x in range(w):
                p, q = pa[y * w + x], pb[y * w + x]
                se += (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
        worst = max(worst, math.sqrt(se / (rows * w * 3)))
    return worst


def bake_card(card: int, row: dict, orig: Image.Image, title_zh: str, font, jp_title: str):
    """一格：底板 + 中文标题（或 band 兜底）。返回 (RGBA cell, info dict)。"""
    lines, truncated = bp.wrap_title(title_zh, font)
    info = {"kind": row["kind"], "lines": lines, "truncated": truncated}
    if row["kind"] == "band":
        cell, decision = bp.bake_cell(orig.convert("RGBA"), lines, font, jp_title=jp_title)
        info.update({"band_bottom": decision.band_bottom, "line_rule": decision.line_rule,
                     "rmse": None, "review": False})
        return cell, info
    plate = build_plate(row)
    flat = row["kind"] == "flat"
    rmse = 0.0 if flat else round(verify_plate(plate, orig, card), 2)
    wide = None if flat else round(wide_rmse(plate, orig, card), 2)
    band = 0.0 if flat else round(local_band_rmse(plate, orig, card), 2)
    reason = ("rmse" if rmse > REVIEW_RMSE else
              "wide" if (wide or 0) > REVIEW_RMSE else
              "wide_gap" if (wide or 0) - rmse > WIDE_GAP else
              "local_band" if band > LOCAL_BAND_RMSE else None)
    info.update({"rmse": rmse, "wide_rmse": wide, "local_band_rmse": band,
                 "review": reason is not None, "review_reason": reason,
                 "gate_ok": rmse <= GATE_RMSE})
    cell = plate.convert("RGBA")
    if row.get("title") == "none":
        # logo 板（卡 162）：原格本就没有烤字标题，logo 即标题，不再压中文
        info["title"] = "none"
        return cell, info
    cell.alpha_composite(bp.render_text_layer(cell.size, lines, font))
    return cell, info


def run(write: bool = True, out_dir: str = OUT_DIR) -> dict:
    rows = load_plates()
    missing = sorted(set(range(1, bp.NUM_CARDS + 1)) - set(rows))
    extra = sorted(set(rows) - set(range(1, bp.NUM_CARDS + 1)))
    if missing or extra:
        raise ValueError(f"配方表卡号不对：缺 {missing}，多 {extra}")
    font = _ui_truetype("plot", bp.FONT_SIZE)
    titles = bp.load_titles_zh()
    jp = load_titles_jp()
    sheets = {s: _orig_sheet(s).copy() for s in range(1, bp.NUM_SHEETS + 1)}
    per_card = {}
    failures = []
    for card in range(1, bp.NUM_CARDS + 1):
        s, box = bp.cell_box(card)
        cell, info = bake_card(card, rows[card], orig_cell(card), titles[card], font, jp[card])
        if info.get("gate_ok") is False:
            failures.append((card, info["rmse"]))
        sheets[s].paste(cell, box[:2])
        per_card[str(card)] = info
    report = {
        "num_cards": bp.NUM_CARDS,
        "gate_rmse": GATE_RMSE,
        "review_rmse": REVIEW_RMSE,
        "per_card": per_card,
        "kinds": {k: sum(1 for i in per_card.values() if i["kind"] == k) for k in ("single", "compose", "flat", "band")},
        "review_cards": sorted(int(c) for c, i in per_card.items() if i.get("review")),
        "band_cards": sorted(int(c) for c, i in per_card.items() if i["kind"] == "band"),
        "gate_failures": [{"card": c, "rmse": r} for c, r in failures],
        "truncated": sorted(int(c) for c, i in per_card.items() if i["truncated"]),
    }
    if failures:
        raise RuntimeError(f"底板过闸失败（RMSE > {GATE_RMSE}）：{failures}——改配方或在数据里明确写 band，不能静默")
    if write:
        os.makedirs(out_dir, exist_ok=True)
        for s, im in sheets.items():
            im.save(os.path.join(out_dir, f"plot_{s}_a.png"))
        compare = bp.build_compare_image([(_orig_sheet(s), sheets[s]) for s in range(1, bp.NUM_SHEETS + 1)])
        compare.save(os.path.join(out_dir, "_compare.png"))
        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="只算、只报告，不写盘")
    ap.add_argument("--out", default=OUT_DIR)
    a = ap.parse_args(argv)
    report = run(write=not a.check, out_dir=a.out)
    print(f"plot 底板：{report['kinds']}；review {len(report['review_cards'])} 格 {report['review_cards']}；"
          f"band 兜底 {len(report['band_cards'])} 格 {report['band_cards']}；截断 {report['truncated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
