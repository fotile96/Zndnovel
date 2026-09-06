"""研究脚本：逐卡重建普查——配方合成（场景内各状态取最优）与暴力单图两条路各算 RMSE。

    uv run --with numpy python tools/research/plot_plate/survey.py > build/research/plot_plate/survey.txt

产物：build/research/plot_plate/survey.json（逐卡：brute 最佳单图、配方最佳状态与 RMSE）。
"""
import sys, os, glob, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from plot_recon import (compose, thumb, fit, cell_of, mask_for, parse_ops, state_after, defs,
                        card2scene_table, OUT_DIR, JP)

# 暴力参照：全部 480×272 的 bg/event 单图
BRUTE = []
for p in sorted(glob.glob("png/bg/*.png")) + sorted(glob.glob("png/event/*.png")):
    im = Image.open(p).convert("RGB")
    if im.size == (480, 272):
        BRUTE.append((os.path.relpath(p, "png").replace(".png", ""), thumb(im)))

card2scene = card2scene_table()

out = {}
for card in range(1, 196):
    cell = cell_of(card); m = mask_for(card)
    rec = {"card": card, "jp": JP.get(card), "scene": (card2scene.get(card) or [None])[0]}
    # 暴力单图
    best = min(((fit(t, cell, m), name) for name, t in BRUTE), key=lambda r: r[0][0])
    rec["brute"] = {"image": best[1], "rmse": round(best[0][0], 1), "gain": round(best[0][1], 2)}
    sc = rec["scene"]
    if sc and sc in defs:
        ops = parse_ops(sc)
        # 候选状态：每个 vms 之前 / 每次 load 之后的状态，取最好的（记下位置）
        cands = []
        for i, o in enumerate(ops):
            if o[0] in ("load", "copy", "clear", "pos", "vms", "com"):
                cands.append(i + 1)
        seen = set(); results = []
        for upto in cands:
            st = state_after(ops, upto)
            key = tuple(sorted((k, v) for k, v in st.items()))
            if key in seen or not st: continue
            seen.add(key)
            r, g, o = fit(thumb(compose(st)), cell, m)
            n_vms_before = sum(1 for x in ops[:upto] if x[0] == "vms")
            results.append((r, g, o, upto, n_vms_before, {k: (v[0][0], v[0][1], v[1]) for k, v in st.items()}))
        if results:
            results.sort(key=lambda r: r[0])
            r, g, o, upto, nv, st = results[0]
            first_vms = next((i for i, x in enumerate(ops) if x[0] == "vms"), None)
            r0 = None
            if first_vms is not None:
                st0 = state_after(ops, first_vms)
                if st0:
                    r0 = fit(thumb(compose(st0)), cell, m)
            rec["recipe"] = {"rmse": round(r, 1), "gain": round(g, 2), "offset": round(o, 1),
                             "vms_before": nv, "state": st,
                             "rmse_at_first_vms": (round(r0[0], 1) if r0 else None),
                             "state_at_first_vms": ({k: (v[0][0], v[0][1], v[1]) for k, v in state_after(ops, first_vms).items()} if first_vms is not None else None)}
    out[card] = rec

os.makedirs(OUT_DIR, exist_ok=True)
json.dump(out, open(os.path.join(OUT_DIR, "survey.json"), "w"), ensure_ascii=False, indent=1)

def bucket(v):
    return "<8" if v < 8 else "<12" if v < 12 else "<16" if v < 16 else "<24" if v < 24 else ">=24"
rc = collections.Counter(bucket(r["recipe"]["rmse"]) for r in out.values() if "recipe" in r)
bc = collections.Counter(bucket(r["brute"]["rmse"]) for r in out.values())
print("recipe RMSE buckets (best state in scene):", dict(rc), "n=", sum(rc.values()))
print("recipe RMSE at first vms buckets:", dict(collections.Counter(bucket(r["recipe"]["rmse_at_first_vms"]) for r in out.values() if r.get("recipe", {}).get("rmse_at_first_vms") is not None)))
print("brute single-image RMSE buckets (all 195):", dict(bc))
print("\ncard  scene         recipe(best) @vms#  first-vms   brute(best image)")
for card, r in out.items():
    rp = r.get("recipe")
    print(f"{card:3d}  {str(r['scene']):13s} "
          f"{(str(rp['rmse'])+' g'+str(rp['gain'])) if rp else '   -   ':>12s} "
          f"{(rp['vms_before'] if rp else ''):>4}  "
          f"{(str(rp['rmse_at_first_vms']) if rp and rp['rmse_at_first_vms'] is not None else '-'):>6s}   "
          f"{r['brute']['rmse']:5.1f} {r['brute']['image']}")
