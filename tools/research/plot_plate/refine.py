"""研究脚本：对带立绘的难例做「变体 + 位置」坐标下降搜索（先跑 survey.py）。

    uv run --with numpy python tools/research/plot_plate/refine.py
"""
import sys, json, glob, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from plot_recon import compose, thumb, fit, cell_of, mask_for

from plot_recon import OUT_DIR
d = json.load(open(os.path.join(OUT_DIR, "survey.json")))

def variants_of(name):
    base = re.sub(r"[a-z]$", "", name)
    return sorted(os.path.basename(p)[:-4] for p in glob.glob(f"png/pose/{base}*.png"))

def score(state, cell, m):
    return fit(thumb(compose(state)), cell, m)

def refine(card, state, cell, m, step=2, span=8):
    state = {k: ((v[0], tuple(v[1]) if isinstance(v[1], list) else v[1]), tuple(v[2])) for k, v in state.items()}
    best_r = score(state, cell, m)[0]
    pose_layers = [k for k, v in state.items() if v[0][0] == "pose"]
    for _round in range(2):
        for lay in pose_layers:
            (kind, name), (x0, y0) = state[lay]
            cand = None
            for nm in variants_of(name):
                for dx in range(-span, span + 1, step):
                    for dy in range(-span, span + 1, step):
                        st = dict(state); st[lay] = ((kind, nm), (x0 + dx, y0 + dy))
                        r = score(st, cell, m)[0]
                        if r < best_r - 0.05:
                            best_r = r; cand = st
            if cand: state = cand
        # 试删掉某个立绘层
        for lay in list(pose_layers):
            st = dict(state); st.pop(lay)
            if st:
                r = score(st, cell, m)[0]
                if r < best_r - 0.05:
                    best_r = r; state = st; pose_layers.remove(lay)
    return best_r, state

out = {}
targets = [(int(c), r) for c, r in d.items()
           if r.get("recipe") and r["recipe"]["rmse"] >= 6 and any(v[0] == "pose" for v in r["recipe"]["state"].values())]
print("targets:", len(targets), flush=True)
for card, r in targets:
    cell = cell_of(card); m = mask_for(card)
    r0 = r["recipe"]["rmse"]
    r1, st = refine(card, r["recipe"]["state"], cell, m)
    out[card] = {"before": r0, "after": round(r1, 1), "state": {k: (v[0][0], v[0][1], list(v[1])) for k, v in st.items()}}
    print(f"card {card:3d} {r['scene']:12s}: {r0:5.1f} -> {r1:5.1f}  " + ", ".join(f"{k}={v[0][1]}@{v[1]}" for k, v in st.items()), flush=True)
json.dump(out, open(os.path.join(OUT_DIR, "refine.json"), "w"), ensure_ascii=False, indent=1)
