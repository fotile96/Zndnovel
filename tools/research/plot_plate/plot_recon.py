"""研究模块：195 张卡缩略图能否由素材重建（配方解析 / 合成 / 缩放 / 色调拟合）。

对每张卡：从场景函数开头的图层操作拼出「配方」（bg/event + pose@位置），合成 480×272
→ BILINEAR 缩到 82×48 → 在无字行上最小二乘拟合 gain/offset → RMSE。另做一遍暴力匹配
（全部 bg/event 单图）作参照。产物落 build/research/plot_plate/（见 README）。
"""
import sys, re, glob, json, os, collections
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
os.chdir(REPO)
sys.path.insert(0, '.')
from PIL import Image
import numpy as np
from tools import bake_plot as bp

LAYER_Z = {"event": 0, "bg1": 0, "bg2": 1, "bg3": 2, "bg4": 3, "bg5": 4,
           "pose1": 5, "pose2": 6, "pose3": 7, "pose4": 8, "pose5": 9, "swap": 10, "pose6": 11}
RESIDENT = {"effectBlack": ("solid", (0, 0, 0)), "effectWhite": ("solid", (255, 255, 255)),
            "effectYellow": ("solid", (255, 255, 0)), "bg_1_a_0": ("bg", "bg_1_a_0"),
            "po1_aya_f_1_a": ("pose", "po1_aya_f_1_a")}

defs = {}
for f in sorted(glob.glob("lua_scripts/snr_*_10_*.lua")):
    for i, l in enumerate(open(f, encoding="utf-8").read().splitlines()):
        m = re.match(r"^local scene_([A-Za-z0-9_\-]+) = function", l)
        if m: defs[m.group(1)] = (f, i)

_txt = open("skeleton/cards.jp.yaml", encoding="utf-8").read()
JP = {int(n): t.strip().strip("'\"") for n, t in re.findall(r"- card: (\d+)\n  variant: a\n  title_jp: (.+)", _txt)}

def parse_ops(scene_id):
    """整个场景函数体的图层操作（含 vms 标记），逐条。"""
    f, start = defs[scene_id]
    src = open(f, encoding="utf-8").read().splitlines()
    ops = []
    for l in src[start + 1:]:
        if re.match(r"^local scene_[A-Za-z0-9_\-]+ = function", l) or l.startswith("main = function"):
            break
        s = l.strip()
        if s.startswith("vms("): ops.append(("vms",)); continue
        m = re.match(r'layerLoad\(layerName\.(\w+), cGetFileName\("(\w+)", "(\w+)"\)', s)
        if m: ops.append(("load", m.group(1), m.group(2), m.group(3))); continue
        m = re.match(r'layerLoad\(layerName\.(\w+), ""\)', s)
        if m: ops.append(("clear", m.group(1))); continue
        m = re.match(r'layerPosition\(layerName\.(\w+), (-?\d+), (-?\d+)', s)
        if m: ops.append(("pos", m.group(1), int(m.group(2)), int(m.group(3)))); continue
        m = re.match(r'layerCopy\(layerName\.(\w+), layerName\.(\w+)\)', s)
        if m: ops.append(("copy", m.group(1), m.group(2))); continue
        m = re.match(r'comPoseLoad\("(\w+)"', s)
        if m: ops.append(("load", "pose1", "pose", m.group(1))); continue
        m = re.match(r'comPoseLoadSec3\("(\w+)"', s)
        if m: ops.append(("load", "pose1", "pose", m.group(1))); ops.append(("pos", "pose1", 0, 20)); continue
        m = re.match(r'comPoseDoubleLoad\(layerName\.(\w+), "(\w+)"', s)
        if m:
            ops.append(("load", m.group(1), "pose", m.group(2)))
            ops.append(("pos", "pose1", 80, 0)); ops.append(("pos", "pose2", -100, 0)); continue
        if s.startswith("comPoseDelete("): ops.append(("clear", "pose1")); ops.append(("clear", "pose2")); continue
        if s.startswith("comPoseInitPosition(2"): ops.append(("pos", "pose1", 80, 0)); ops.append(("pos", "pose2", -100, 0)); continue
        m = re.match(r'(com\w+)\(', s)
        if m: ops.append(("com", m.group(1))); continue
    return ops

def state_after(ops, upto):
    """执行 ops[:upto]，返回各图层 (kind, name, pos)。"""
    layers = {}
    pos = collections.defaultdict(lambda: (0, 0))
    for o in ops[:upto]:
        if o[0] == "load": layers[o[1]] = (o[2], o[3])
        elif o[0] == "clear": layers.pop(o[1], None)
        elif o[0] == "pos": pos[o[1]] = (o[2], o[3])
        elif o[0] == "copy":
            src = RESIDENT.get(o[2])
            if src: layers[o[1]] = src
            elif o[2] in layers: layers[o[1]] = layers[o[2]]
    return {k: (v, pos[k]) for k, v in layers.items() if k in LAYER_Z}

_cache = {}
def img(kind, name):
    if isinstance(name, list): name = tuple(name)
    key = (kind, name)
    if key not in _cache:
        if kind == "solid":
            _cache[key] = Image.new("RGBA", (480, 272), name + (255,))
        else:
            p = f"png/{kind}/{name}.png"
            _cache[key] = Image.open(p).convert("RGBA") if os.path.exists(p) else None
    return _cache[key]

def compose(state):
    scr = Image.new("RGBA", (480, 272), (0, 0, 0, 255))
    for lname in sorted(state, key=lambda k: LAYER_Z[k]):
        (kind, name), (x, y) = state[lname]
        im = img(kind, name)
        if im is None: continue
        layer = Image.new("RGBA", (480, 272), (0, 0, 0, 0))
        layer.paste(im, (x, y))          # 不带掩膜（带掩膜会把 alpha 平方）
        scr.alpha_composite(layer)
    return scr.convert("RGB")

def thumb(im):
    return np.asarray(im.resize((82, 48), Image.BILINEAR)).astype(float)

def fit(a, b, m):
    x = a[m].ravel(); y = b[m].ravel()
    A = np.vstack([x, np.ones_like(x)]).T
    g, o = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(np.sqrt(((g * x + o - y) ** 2).mean())), float(g), float(o)

def cell_of(card):
    s, box = bp.cell_box(card)
    return np.asarray(Image.open(f"png/plot/plot_{s}_a.png").convert("RGB").crop(box)).astype(float)

def mask_for(card):
    lines = 1 if len(JP.get(card, "")) <= 7 else 2
    m = np.zeros((48, 82), bool); m[(26 if lines == 2 else 14):, :] = True
    return m




def card2scene_table():
    """卡号 → 场景 id 列表（snr_common 的 sceneId2aCard 反查；`keyword` 噪声键保留为 'keyword'）。"""
    txt = open("lua_scripts/snr_common.lua", encoding="utf-8").read()
    table = {}
    for m in re.finditer(r"sceneId2aCard\.(\w+) = (\d+)$", txt, re.M):
        table.setdefault(int(m.group(2)), []).append(m.group(1))
    for k, v in table.items():
        v.sort(key=lambda s: s == "keyword")   # 真场景在前
    return table


OUT_DIR = os.path.join(REPO, "build", "research", "plot_plate")
