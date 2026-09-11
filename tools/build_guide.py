#!/usr/bin/env python3
"""中文攻略（guide/）的生成与编译。

三个动作（缺省全跑）：

  gen    从定译数据源生成 guide/generated/*.typ 与 options.json 快照
  pdf    typst 编译 guide/main.typ → guide/dist/second-novel-guide-zh.pdf
  check  仅校验：generated/ 与数据源一致（无漂移）+ 能编译（编译期断言卡名/选项名）

定译数据源（只读，不在这里改）：
  skeleton/cards.zh.yaml + cards.jp.yaml   卡名定译（card → title_zh / title_jp / section_label）
  data/dag.json                            章节 DAG、卡片谜题结构（req/answers/gets/runs）
  data/scene2card.json                     场景 → 卡号
  data/extra_translated.jsonl              场景标题 jp → zh
  tools/bake_select.compute_coverage()     134 个选项按钮的 jp → zh（烤字用的同一解析器）

compute_coverage 依赖 build/ 下的派生产物（select_option_map.json 等，gitignore）；
缺失时退回已入库的快照 guide/generated/options.json 并告警——快照就是为此存在的。

正文（guide/chapters/*.typ）引用卡名/选项名一律走模板函数 #card("…") / #opt("…")，
模板从 generated/data.typ 取定译集合做 assert：名字写错或定译改了，typst 编译直接失败。
用法：
  uv run python tools/build_guide.py            # gen + pdf
  uv run python tools/build_guide.py check      # CI/测试用
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
GUIDE = REPO / "guide"
GEN = GUIDE / "generated"
DIST = GUIDE / "dist"
PDF_NAME = "second-novel-guide-zh.pdf"

sys.path.insert(0, str(REPO / "tools"))


# ----------------------------------------------------------------------------
# 数据源
# ----------------------------------------------------------------------------
def load_cards() -> dict[int, dict]:
    jp = {c["card"]: c for c in yaml.safe_load((REPO / "skeleton/cards.jp.yaml").read_text())}
    zh = {c["card"]: c for c in yaml.safe_load((REPO / "skeleton/cards.zh.yaml").read_text())}
    out = {}
    for n, c in zh.items():
        if n >= 196:
            continue  # 编外卡（谢幕章专用），刻意不入攻略
        j = jp.get(n, {})
        out[n] = {
            "card": n,
            "title_zh": c["title_zh"],
            "title_jp": j.get("title_jp", ""),
            "section": (j.get("section_label") or "").replace("\n", " "),
        }
    return out


def load_scene_titles(cards: dict[int, dict]) -> dict[str, str]:
    """场景标题 jp → zh。与场景同名的卡以卡名定译为准（cards.zh），其余取 extra 轨译文。"""
    m = {}
    for line in (REPO / "data/extra_translated.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("jp") and o.get("zh"):
            m.setdefault(o["jp"], o["zh"])
    for c in cards.values():
        if c["title_jp"]:
            m[c["title_jp"]] = c["title_zh"]
    return m


CARDSORT_RE = re.compile(r"^cardSort\[(\d+)\]\[1\] = (\d+)", re.M)
GRID_COLS, GRID_ROWS = 15, 13
CELL_W, CELL_H = 26, 15
CELL_SCALE = 4          # 单格 swatch 放大倍数（最近邻，保留像素风）
GRID_SCALE = 3          # 总览图放大倍数
CARD_MODE_SHEET = REPO / "png/sysgim/sys_11_c.png"   # 选卡界面光标所在格的亮色版（印刷可辨）


def cell_rect(pos: int) -> tuple[int, int, int, int]:
    """选卡界面第 pos 个槽位（1..195）的裁切矩形，移植自 snr_common.lua oCard.cardModeSet：
    15 列 × 13 行；x = (col-1)*30 + {13,17,21}（每 5 列一组、组间留缝），y = row*16 + 30，格 26×15。"""
    col = (pos - 1) % GRID_COLS + 1
    row = (pos - 1) // GRID_COLS + 1
    if col <= 5:
        x = (col - 1) * 30 + 13
    elif col <= 10:
        x = (col - 1) * 30 + 17
    else:
        x = (col - 1) * 30 + 21
    y = row * 16 + 30
    return x, y, x + CELL_W, y + CELL_H


def load_card_positions() -> dict[int, dict]:
    """card → {pos,row,col}。槽位顺序 = snr_common.lua 的 cardSort[pos][1] = card。"""
    src = (REPO / "lua_scripts/snr_common.lua").read_text(encoding="utf-8")
    out = {}
    for m in CARDSORT_RE.finditer(src):
        pos, card = int(m.group(1)), int(m.group(2))
        out[card] = {"pos": pos, "row": (pos - 1) // GRID_COLS + 1, "col": (pos - 1) % GRID_COLS + 1}
    assert len(out) == 195, f"cardSort 条目数异常: {len(out)}"
    return out


def render_cell_images(positions: dict[int, dict]) -> None:
    """每张卡在选卡界面里那一格的样子 → generated/cells/cNNN.png；全网格总览 → generated/card-grid.png。"""
    from PIL import Image, ImageDraw, ImageFont

    sheet = Image.open(CARD_MODE_SHEET).convert("RGBA")
    cells = GEN / "cells"
    cells.mkdir(parents=True, exist_ok=True)
    for card, p in positions.items():
        x0, y0, x1, y1 = cell_rect(p["pos"])
        im = sheet.crop((x0, y0, x1, y1)).resize((CELL_W * CELL_SCALE, CELL_H * CELL_SCALE), Image.NEAREST)
        # 白底合成：印刷时透明像素落在白纸上，这里预先合成保证与正文一致
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        bg.convert("RGB").save(cells / f"c{card:03d}.png", optimize=True)

    # 总览：裁掉四周空白，放大，叠行号/列号/卡号
    left, top = cell_rect(1)[0], cell_rect(1)[1]
    right, bottom = cell_rect(GRID_COLS)[2], cell_rect(GRID_COLS * GRID_ROWS)[3]
    pad = 12
    grid = sheet.crop((left - pad, top - pad, right + pad, bottom + pad))
    grid = grid.resize((grid.width * GRID_SCALE, grid.height * GRID_SCALE), Image.NEAREST)
    margin_l, margin_t = 34, 30
    canvas = Image.new("RGB", (grid.width + margin_l, grid.height + margin_t), (255, 255, 255))
    canvas.paste(grid, (margin_l, margin_t), grid)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default(size=13)
        font_small = ImageFont.load_default(size=11)
    except TypeError:  # Pillow < 10.1
        font = font_small = ImageFont.load_default()

    def to_canvas(px, py):
        return margin_l + (px - (left - pad)) * GRID_SCALE, margin_t + (py - (top - pad)) * GRID_SCALE

    pos2card = {p["pos"]: c for c, p in positions.items()}
    for pos in range(1, GRID_COLS * GRID_ROWS + 1):
        x0, y0, x1, y1 = cell_rect(pos)
        cx0, cy0 = to_canvas(x0, y0)
        cx1, cy1 = to_canvas(x1, y1)
        card = pos2card.get(pos)
        if card is None:
            continue
        label = str(card)
        tw = draw.textlength(label, font=font_small)
        # 白描边：前三行格子里有 WORD / S.1 之类的大字标签，裸数字会糊在一起
        draw.text(((cx0 + cx1 - tw) / 2, cy0 + (cy1 - cy0 - 11) / 2 - 1), label, fill=(25, 25, 25),
                  font=font_small, stroke_width=2, stroke_fill=(255, 255, 255))
        if pos <= GRID_COLS:  # 列号
            col = str(pos)
            tw = draw.textlength(col, font=font)
            draw.text(((cx0 + cx1 - tw) / 2, 8), col, fill=(110, 110, 110), font=font)
        if (pos - 1) % GRID_COLS == 0:  # 行号
            row = str((pos - 1) // GRID_COLS + 1)
            tw = draw.textlength(row, font=font)
            draw.text((margin_l - 8 - tw, (cy0 + cy1) / 2 - 7), row, fill=(110, 110, 110), font=font)
    canvas.save(GEN / "card-grid.png", optimize=True)


def load_options() -> dict[str, dict]:
    """button → {jp, zh}。优先走烤字解析器；build/ 缺失时用入库快照。"""
    snap = GEN / "options.json"
    try:
        import bake_select  # noqa: WPS433

        rows = bake_select.compute_coverage()[0]
        return {k: {"jp": v["jp"], "zh": v["zh"]} for k, v in sorted(rows.items())}
    except Exception as exc:  # 缺 build 产物、缺 PIL 等
        if snap.exists():
            print(f"[build_guide] compute_coverage 不可用（{exc.__class__.__name__}: {exc}），"
                  f"退回快照 {snap.relative_to(REPO)}", file=sys.stderr)
            return json.loads(snap.read_text())
        raise


# ----------------------------------------------------------------------------
# 生成
# ----------------------------------------------------------------------------
def typ_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_data_typ(cards, options, scene_titles, positions) -> str:
    lines = ["// 由 tools/build_guide.py gen 生成，勿手改。定译集合：模板 card()/opt() 据此断言。"]
    lines.append("// 选卡界面槽位：card-pos.at(str(卡号)) = (row, col)，15 列 × 13 行，源 snr_common.lua cardSort。")
    lines.append("#let card-pos = (")
    for n in sorted(positions):
        p = positions[n]
        lines.append(f'  "{n}": ({p["row"]}, {p["col"]}),')
    lines.append(")")
    lines.append("#let card-titles = (")
    seen_titles = set()
    for n in sorted(cards):
        t = cards[n]["title_zh"]
        if t in seen_titles:
            continue  # 同名卡（探索：放学后的学校 20/74、天台 85/119），正文用 cn() 区分
        seen_titles.add(t)
        lines.append(f"  {typ_str(t)}: {n},")
    lines.append(")")
    lines.append("#let option-texts = (")
    seen = set()
    for b, o in options.items():
        if o["zh"] in seen:
            continue
        seen.add(o["zh"])
        lines.append(f"  {typ_str(o['zh'])}: {typ_str(o['jp'])},")
    lines.append(")")
    lines.append("#let scene-titles = (")
    seen_zh = set()
    for jp, zh in scene_titles.items():
        if zh in seen_zh:
            continue
        seen_zh.add(zh)
        lines.append(f"  {typ_str(zh)}: {typ_str(jp)},")
    lines.append(")")
    return "\n".join(lines) + "\n"


def render_cards_table(cards, dag, scene2card, positions) -> str:
    """附录 A：196 张卡一览。"""
    card2scene = defaultdict(list)
    for sid, n in scene2card.items():
        card2scene[n].append(sid)
    # 关键词卡由哪个场景听完自动入手
    granted_by = defaultdict(list)
    for scene_fn, meta in dag["scene_meta"].items():
        for n in meta.get("gets", []):
            granted_by[n].append(scene_fn.replace("scene_", "", 1))
    for k, c in dag["crds"].items():
        for n in c.get("gets", []):
            granted_by[n].append(f"做卡{k}")

    def name(n):
        n = int(n)
        return cards[n]["title_zh"] if n in cards else f"卡{n}"

    def section_short(label: str) -> str:
        # 卡面右栏标签 → 紧凑分类词（表格列窄）
        label = label.replace(" ", "")
        if label == "キーワード":
            return "关键词"
        if label == "物語あらすじ":
            return "章节梗概"
        if label in ("物語？", ""):
            return "—"
        sec = label.replace("セクション", "").replace("あらすじ", "").replace("選択肢", "").replace("探索", "").replace("日記", "")
        kind = "梗概" if label.endswith("あらすじ") else "选择" if label.endswith("選択肢") else "探索" if label.endswith("探索") else "日记" if label.endswith("日記") else ""
        return f"{sec}·{kind}"

    lines = ["// 由 tools/build_guide.py gen 生成，勿手改。", "", "#let cards-rows = ("]
    for n in sorted(cards):
        c = dag["crds"].get(str(n), {})
        stub = c.get("stub", False)
        req = "、".join(name(x) for x in c.get("req", []))
        ans = "、".join(name(x) for x in c.get("answers", []))
        runs = c.get("runs", [])
        if stub:
            src = set(granted_by.get(n, []))
            how = "做卡附带" if any(s.startswith("做卡") for s in src) else "听完场景" if src else "自动"
        else:
            how = "做卡·章节终卡" if runs else "做卡"
        p = positions[n]
        lines.append("  (" + ", ".join(typ_str(x) for x in (
            str(n), f'{p["row"]}行{p["col"]}列', section_short(cards[n]["section"]), cards[n]["title_jp"], cards[n]["title_zh"],
            req or "—", ans or ("—" if stub else "无需递卡"), how)) + "),")
    lines.append(")")
    return "\n".join(lines) + "\n"


def render_options_table(options, dag, scene_titles) -> str:
    """附录 B：134 个选项按钮，按选择场景分组。"""
    by_scene = defaultdict(list)
    for b, o in options.items():
        # sel_<scene>_<letter>
        core = b[len("sel_"):]
        scene, letter = core.rsplit("_", 1)
        by_scene[scene].append((letter, o["jp"], o["zh"]))

    # 选择发生在场景函数内部、dispatcher 里没有独立状态的按钮组 → 场景内提示语的日文标题
    inner_titles = {
        "s3s_230h_sel": "探索：放課後の学校",
        "s3s_230l_sel": "探索：放課後の学校",
        "s4fb_30_sel": "選択：彩野さんを――",
        "s4fb_50_sel": "選択：彩野さん――",
        "s5s_80_sel": "選択：ウワサとは？",
        "s5s_190_sel": "選択：どこに行く？",
        "s5s_350_sel": "選択：耐えられそうにない発作",
        "s5s_710_sel": "選択：彼の姿",
        "s6s_110_sel": "図書室で読む",
    }

    def scene_title(sid):
        st = dag["states"].get(sid)
        jp = (st.get("title") if st else None) or inner_titles.get(sid)
        if not jp:
            return sid
        return f"{scene_titles.get(jp, jp)}（{sid}）"

    def natkey(s):
        import re
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)]

    lines = ["// 由 tools/build_guide.py gen 生成，勿手改。", "", "#let option-groups = ("]
    for sid in sorted(by_scene, key=natkey):
        rows = sorted(by_scene[sid])
        lines.append(f"  ({typ_str(scene_title(sid))}, (")
        for letter, jp, zh in rows:
            lines.append(f"    ({typ_str(letter)}, {typ_str(jp)}, {typ_str(zh)}),")
        lines.append("  )),")
    lines.append(")")
    return "\n".join(lines) + "\n"


def generate() -> dict[str, str]:
    cards = load_cards()
    dag = json.loads((REPO / "data/dag.json").read_text())
    scene2card = json.loads((REPO / "data/scene2card.json").read_text())
    scene_titles = load_scene_titles(cards)
    options = load_options()
    positions = load_card_positions()
    return {
        "options.json": json.dumps(options, ensure_ascii=False, indent=1) + "\n",
        "data.typ": render_data_typ(cards, options, scene_titles, positions),
        "cards-table.typ": render_cards_table(cards, dag, scene2card, positions),
        "options-table.typ": render_options_table(options, dag, scene_titles),
    }


def do_gen() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    for name, text in generate().items():
        (GEN / name).write_text(text, encoding="utf-8")
        print(f"[build_guide] wrote {(GEN / name).relative_to(REPO)}")
    render_cell_images(load_card_positions())
    print(f"[build_guide] wrote {(GEN / 'cells').relative_to(REPO)}/c*.png (195) 与 card-grid.png")


def do_check_gen() -> bool:
    ok = True
    for name, text in generate().items():
        p = GEN / name
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            print(f"[build_guide] DRIFT: {p.relative_to(REPO)} 与数据源不一致，请重跑 gen", file=sys.stderr)
            ok = False
    return ok


# ----------------------------------------------------------------------------
# 递卡顺序校验：正文 make-cards 行里的「依次递 A、B、C」必须与 crd 脚本的比较顺序一致
# ----------------------------------------------------------------------------
SELECT_BLOCK_RE = re.compile(r"selectCardObj\(\)(.*?)(?=selectCardObj\(\)|\Z)", re.S)
CMP_RE = re.compile(r"== (\d+) then")
MAKE_ROW_RE = re.compile(r'\("([^"]+)", \[(.*?)\](?:, (\d+))?\)')
CARD_REF_RE = re.compile(r'#card\("([^"]+)"')


def expected_hand_order() -> dict[int, list[int]]:
    """crd → 依次要递的卡号。每个 oCard.selectCardObj() 之后第一个 `== N then`（N>1）就是该步接受的卡；
    data/dag.json 的 answers 是集合，顺序不可信，攻略正文只能以这里为准。"""
    out = {}
    for f in sorted((REPO / "lua_scripts").glob("snr_crd_*.lua")):
        n = int(re.search(r"crd_(\d+)", f.name).group(1))
        ids = []
        for m in SELECT_BLOCK_RE.finditer(f.read_text(encoding="utf-8")):
            cmp = [int(x) for x in CMP_RE.findall(m.group(1)) if int(x) > 1]
            if cmp:
                ids.append(cmp[0])
        if ids:
            out[n] = ids
    return out


def check_hand_order(cards: dict[int, dict] | None = None) -> list[str]:
    """返回不一致说明列表（空 = 全部一致）。只查多卡谜题；正文里提到的前置卡会出现在序列前面，故比对尾段。"""
    cards = cards or load_cards()
    title2id = {}
    for n in sorted(cards):
        title2id.setdefault(cards[n]["title_zh"], n)
    expected = {n: s for n, s in expected_hand_order().items() if len(s) > 1}
    problems, seen = [], set()
    for f in sorted((GUIDE / "chapters").glob("*.typ")):
        for m in MAKE_ROW_RE.finditer(f.read_text(encoding="utf-8")):
            title, body, cid = m.group(1), m.group(2), m.group(3)
            n = int(cid) if cid else title2id.get(title)
            if n not in expected:
                continue
            seen.add(n)
            exp = [cards[i]["title_zh"] for i in expected[n]]
            # 只看「递 …。」这一句：前面可能提到前置卡，后面可能提到做成后解锁的场景
            seg = body[body.rfind("递") + 1:] if "递" in body else body
            seg = seg.split("。")[0]
            got = CARD_REF_RE.findall(seg)
            if got != exp:
                problems.append(f"{f.name} crd_{n}『{title}』递卡顺序应为 {exp}，正文写的是 {got}")
    for n in sorted(set(expected) - seen):
        problems.append(f"crd_{n}『{cards[n]['title_zh']}』是多卡谜题但正文没有 make-cards 行")
    return problems


# ----------------------------------------------------------------------------
# 编译
# ----------------------------------------------------------------------------
def do_pdf(out: Path | None = None) -> Path:
    if not shutil.which("typst"):
        sys.exit("[build_guide] 未找到 typst，请 brew install typst（或 cargo install --locked typst-cli）")
    out = out or (DIST / PDF_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["typst", "compile", "--root", str(GUIDE), str(GUIDE / "main.typ"), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        sys.exit("[build_guide] COMPILE-FAIL")
    print(f"[build_guide] COMPILE-OK → {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(out)], capture_output=True, text=True).stdout
        pages = [l for l in info.splitlines() if l.startswith("Pages")]
        if pages:
            print("[build_guide]", pages[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", default="all", choices=["all", "gen", "pdf", "check"])
    ap.add_argument("--out", type=Path, help="pdf 输出路径（缺省 guide/dist/%s）" % PDF_NAME)
    a = ap.parse_args()
    if a.action in ("all", "pdf", "check"):
        problems = check_hand_order()
        for p in problems:
            print("[build_guide] 递卡顺序:", p, file=sys.stderr)
        if problems:
            sys.exit("[build_guide] 递卡顺序与 crd 脚本不一致，拒绝出盘")
    if a.action in ("all", "gen"):
        do_gen()
    if a.action in ("all", "pdf"):
        do_pdf(a.out)
    if a.action == "check":
        ok = do_check_gen()
        tmp = REPO / "build" / "guide-check.pdf"
        do_pdf(tmp)
        if not ok:
            sys.exit(1)
        print("[build_guide] check OK")


if __name__ == "__main__":
    main()
