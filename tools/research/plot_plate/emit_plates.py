"""研究脚本：把普查/细化/猎手结果汇成 `data/plot_plates.jsonl` 初稿（逐卡取 RMSE 最优的配方）。

    uv run --with numpy python tools/research/plot_plate/emit_plates.py [--gate 12] [--hunts build/research/plot_plate/hunts.json]

来源优先级：本目录 hunts.json（子代理猎手/主线程探针确认的配方，入库）> refine.json > survey.json 的 recipe > survey.json 的 brute 单图。
每条候选都用 `tools/bake_plot_plate.build_plate + verify_plate` **按生产口径重量**（底板原样、tone 0.5、无拟合），
取最小者；超过 gate 的写 `kind: band`；flat 家族（拟合倍率 ≈0）写 `kind: flat`；卡 162（logo）写 band。
"""
import argparse
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
os.chdir(REPO)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools import bake_plot_plate as bpp  # noqa: E402
from plot_recon import OUT_DIR  # noqa: E402


def layers_from_state(state):
    out = []
    for layer, v in state.items():
        kind, name, pos = v[0], v[1], v[2]
        if kind == "solid":
            out.append({"layer": layer, "kind": "solid", "rgb": list(name), "x": 0, "y": 0})
        else:
            out.append({"layer": layer, "kind": kind, "name": name, "x": int(pos[0]), "y": int(pos[1])})
    # 稳定排序：同 z（event/bg1 同槽）保持 state 的插入顺序＝加载顺序，后加载者在上
    return sorted(out, key=lambda l: bpp.LAYER_Z.get(l["layer"], 99))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", type=float, default=bpp.GATE_RMSE)
    ap.add_argument("--hunts", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunts.json"))
    ap.add_argument("--out", default=bpp.PLATES_PATH)
    a = ap.parse_args(argv)
    survey = json.load(open(os.path.join(OUT_DIR, "survey.json")))
    refine = json.load(open(os.path.join(OUT_DIR, "refine.json")))
    hunts = json.load(open(a.hunts)) if os.path.exists(a.hunts) else {}
    rows = []
    for card in range(1, 196):
        s = survey[str(card)]
        cands = []
        if abs(s["brute"]["gain"]) < 0.15 and card != 162:
            cell = bpp.orig_cell(card).convert("RGB")
            black = max(hi for _lo, hi in cell.crop((0, 26, 82, 48)).getextrema()) == 0
            row = {"card": card, "kind": "flat", "note": f"平板家族（{s['jp']}）" + ("；无字行全黑＝开场黑屏格" if black else "")}
            if black:
                row["black"] = True
            rows.append(row)
            continue
        h = hunts.get(str(card))
        if card == 162 and not (h and h.get("layers")):
            rows.append({"card": card, "kind": "band", "note": "题名 logo 格：保持色带路径（裁决 P3）"})
            continue
        if h and h.get("layers"):
            cands.append(("hunt", {"layers": h["layers"], "title": h.get("title"), "crop": h.get("crop")}, h.get("note", "")))
        if str(card) in refine:
            cands.append(("refine", {"layers": layers_from_state(refine[str(card)]["state"])}, ""))
        if s.get("recipe"):
            cands.append(("recipe", {"layers": layers_from_state(s["recipe"]["state"])}, ""))
        kind, name = s["brute"]["image"].split("/")
        cands.append(("brute", {"layers": [{"layer": "event" if kind == "event" else "bg1", "kind": kind, "name": name, "x": 0, "y": 0}]}, ""))
        best = None
        for src, rec, note in cands:
            row = {"card": card, "kind": "compose" if len(rec["layers"]) > 1 else "single", "layers": rec["layers"], "tone": 0.5}
            if rec.get("title"):
                row["title"] = rec["title"]
            if rec.get("crop"):
                row["crop"] = rec["crop"]
            try:
                rm = bpp.verify_plate(bpp.build_plate(row), bpp.orig_cell(card), card)
            except Exception as e:  # 素材缺失等
                print(f"card {card} {src}: {e}", file=sys.stderr)
                continue
            if best is None or rm < best[0]:
                best = (rm, src, row, note)
        rm, src, row, note = best
        if rm > a.gate:
            rows.append({"card": card, "kind": "band", "note": f"最佳配方 {src} RMSE {rm:.1f} > {a.gate}（{s['jp']}），走色带兜底", "best_candidate": row["layers"], "best_rmse": round(rm, 2)})
        else:
            row["verify_rmse"] = round(rm, 2)
            row["note"] = f"{src}；{s['jp']}" + (f"；{note}" if note else "")
            rows.append(row)
    # accepted/accepted_note 是**人的裁定**，不是搜索结果：重生成时按卡号原样带过来，
    # 否则每次跑 emit 都会把「已接受」抹掉，复核清单又开始重报同一批格。
    if os.path.exists(a.out):
        prev = {json.loads(l)["card"]: json.loads(l) for l in open(a.out, encoding="utf-8") if l.strip()}
        for r in rows:
            old_row = prev.get(r["card"])
            if old_row and old_row.get("accepted"):
                r["accepted"] = True
                r["accepted_note"] = old_row.get("accepted_note", "")
    with open(a.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("written", a.out, kinds)
    print("band:", [(r["card"], r.get("best_rmse")) for r in rows if r["kind"] == "band"])


if __name__ == "__main__":
    main()
