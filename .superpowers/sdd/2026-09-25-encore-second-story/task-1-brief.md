### Task 1: 三张少女 CG（`bake_finale_event.py` 清单化）

**Files:**
- Modify: `tools/bake_finale_event.py`（整文件替换，见步骤 3）
- Modify: `tests/test_bake_finale_event.py`（追加两个测试）
- Create（产物）: `build/finale_event/eve_47_{f,d,g}.png`（进包件）、`docs/finale/assets/eve_47_{f,d,g}.png`（入库成品）

**Interfaces:**
- Consumes: `docs/finale/assets/eve_47_{f,d,g}.src.png`（已入库，1665×944 级 RGB）、模板 `png/event/eve_74_x.png`（尺寸对照）
- Produces: `bfe.JOBS: tuple[tuple[str, Path], ...]`（四条：`eve_74_z`、`eve_47_f`、`eve_47_d`、`eve_47_g`）；`bfe.bake(name: str, src: Path, tpl: Image.Image, *, out_root: Path | None = None, asset_dir: Path | None = None) -> tuple[Image.Image, str, float]`；既有 `crop_to_aspect / downsample / quantize_best / to_rgba_palette / METHODS` 签名不变。Task 4 的脚本引用成员名 `eve_47_f/_d/_g`；`[gim].new` 既有条目 `["finale_event", "event", "event/eve_74_x.gim"]` 自动拾取 `build/finale_event/` 下所有不以 `_` 开头的 PNG。

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_bake_finale_event.py` 末尾）

```python
def test_jobs_cover_whale_and_three_girls_with_existing_sources():
    """清单化后四张图一条不少、源图都在库里（1665×944 级，供图与 eve_74_z 同规格）。"""
    names = [n for n, _s in bfe.JOBS]
    assert names == ["eve_74_z", "eve_47_f", "eve_47_d", "eve_47_g"]
    for _n, src in bfe.JOBS:
        assert src.exists(), src
        w, h = Image.open(src).size
        assert abs(w / h - 480 / 272) < 1e-2, (src, w, h)


def test_bake_writes_final_and_qa_under_out_root(tmp_path):
    src = tmp_path / "x.src.png"
    _gradient(1665, 944).save(src)
    tpl = Image.open(bfe.TEMPLATE_PNG)
    final, method, err = bfe.bake("x", src, tpl, out_root=tmp_path, asset_dir=None)
    assert final.mode == "P" and final.size == (480, 272) and method in bfe.METHODS and err >= 0
    assert (tmp_path / bfe.FACE / "x.png").exists()
    assert (tmp_path / bfe.FACE / "_ab_x_2x.png").exists()       # 以 _ 开头，build_disc 不会当成员
    assert [d.name for d in tmp_path.iterdir() if d.is_dir()] == [bfe.FACE]   # asset_dir=None 时只写 out_root/finale_event
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_bake_finale_event.py -q`
Expected: 2 FAILED（`AttributeError: module 'tools.bake_finale_event' has no attribute 'JOBS'` / `bake`），原有 4 个 PASS。

- [ ] **Step 3: 整文件替换 `tools/bake_finale_event.py`**

```python
#!/usr/bin/env python3
"""谢幕章 CG 变体清单——用户供图降采样到 event 模板尺寸（480×272）并预量化 256 色。

四张（JOBS）：
- eve_74_z：fin-40 文化祭的鲸客人（DeepSeek 拟人；2026-09-21 用户供图，原 eve_74_x 的变体创作），
  客人到场时同层交叉溶解到本图，e2f_340 仍用原图。
- eve_47_f / eve_47_d / eve_47_g：第二个谢幕故事 fin-80『全屏窗口』的三位「女学生」——寓言家（Fable）、
  大肥鱼（DeepSeek）、牛来吹（GLM）（2026-09-25 用户供图，docs/finale/draft-encore2-v0.md D4/D5）。
  构图母本是 eve_47_x（crd_61/s6s/s7f：彩野伏案用橡皮反复改写『物語』的画面），三人依次接替
  彩野的座位；画廊登记为 eve_47 格的三个变体（layers/overlays/finale-gallery-cg.toml）。

做法（每张相同）：
1. 中心裁到 480:272 的精确纵横比（源图只差万分之五，裁 1 px 量级），LANCZOS 降采样；
2. **在烤图阶段就量化到 256 色**（event 模板 eve_74_x 是 index8/256 色）：分别试
   MEDIANCUT / MAXCOVERAGE / FASTOCTREE，按感知 MSE 取最优。这样 build_disc 的
   quantize_for_template 见到 ≤256 色的图走无损精确调色板路径，量化器由本工具选定而不是
   交给缺省，产物像素在这里就定稿、可目检；
3. 产物：docs/finale/assets/<name>.png（入库成品）＋ build/finale_event/<name>.png
   （进包件；layers/manifest.toml [gim].new 以 event/eve_74_x.gim 为模板编成新成员 event/<name>.gim）
   ＋ QA 图 _ab_<name>_2x.png（原 eve_74_x / 降采样 / 量化后 三联，2 倍；以 _ 开头，build_disc 不收）。
不触碰 png/event/ 原件。

    uv run python tools/bake_finale_event.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.bake_out import out_dir  # noqa: E402

FACE = "finale_event"
ASSETS = REPO / "docs" / "finale" / "assets"
JOBS: tuple[tuple[str, Path], ...] = (
    ("eve_74_z", ASSETS / "eve_74_z.src.png"),
    ("eve_47_f", ASSETS / "eve_47_f.src.png"),
    ("eve_47_d", ASSETS / "eve_47_d.src.png"),
    ("eve_47_g", ASSETS / "eve_47_g.src.png"),
)
TEMPLATE_PNG = REPO / "png" / "event" / "eve_74_x.png"      # 模板尺寸与对照图
W, H = 480, 272
COLORS = 256                                                # event 模板 index8 色板容量
METHODS = ("MEDIANCUT", "MAXCOVERAGE", "FASTOCTREE")


def crop_to_aspect(im: Image.Image, size: tuple[int, int] = (W, H)) -> Image.Image:
    """中心裁剪到目标纵横比（只裁不缩），偏差在 1 px 内时原样返回。"""
    w, h = im.size
    tw, th = size
    target = tw / th
    if w / h > target:            # 太宽：裁宽
        nw = round(h * target)
        if abs(nw - w) <= 1:
            return im
        left = (w - nw) // 2
        return im.crop((left, 0, left + nw, h))
    nh = round(w / target)        # 太高：裁高
    if abs(nh - h) <= 1:
        return im
    top = (h - nh) // 2
    return im.crop((0, top, w, top + nh))


def downsample(im: Image.Image, size: tuple[int, int] = (W, H)) -> Image.Image:
    """裁到纵横比 → LANCZOS 缩到模板尺寸（RGB，不透明 CG 无 alpha 顾虑）。"""
    return crop_to_aspect(im.convert("RGB"), size).resize(size, Image.LANCZOS)


def _mse_rgb(a: Image.Image, b: Image.Image) -> float:
    from tools.emu.imgdiff import mse
    return mse(a.convert("RGB"), b.convert("RGB"))


def quantize_best(im: Image.Image, colors: int = COLORS) -> tuple[Image.Image, str, float]:
    """按感知 MSE 从几种量化器里挑最优；返回 (P 图, 方法名, MSE)。

    不抖动：赛璐璐风 CG 的平涂面在抖动下会起噪点，且抖动会抬高 MSE 却未必更好看；
    渐变处的色阶由 QA 图目检。
    """
    im = im.convert("RGB")
    best = None
    for name in METHODS:
        q = im.quantize(colors=colors, method=getattr(Image.Quantize, name), dither=Image.Dither.NONE)
        err = _mse_rgb(q, im)
        if best is None or err < best[2]:
            best = (q, name, err)
    return best


def to_rgba_palette(q: Image.Image) -> Image.Image:
    """P 图的调色板补成 RGBA（alpha 255），与 quantize_for_template 的精确路径同型。"""
    pal = q.getpalette()[: 3 * COLORS]
    n = len(pal) // 3
    rgba = []
    for i in range(n):
        rgba.extend((pal[3 * i], pal[3 * i + 1], pal[3 * i + 2], 255))
    out = q.copy()                      # 像素索引原样复制，只换调色板
    out.info.pop("transparency", None)
    out.putpalette(rgba, rawmode="RGBA")
    return out


def compose_ab(orig: Image.Image, mid: Image.Image, final: Image.Image, scale: int = 2) -> Image.Image:
    """三联对照：原 eve_74_x / 降采样 / 量化后，各放大 scale 倍竖排。"""
    gap = 8
    canvas = Image.new("RGB", (W * scale, (H * scale + gap) * 3 - gap), (60, 60, 60))
    for i, im in enumerate((orig, mid, final)):
        canvas.paste(im.convert("RGB").resize((W * scale, H * scale), Image.NEAREST), (0, i * (H * scale + gap)))
    return canvas


def bake(name: str, src: Path, tpl: Image.Image, *, out_root: Path | None = None,
         asset_dir: Path | None = None) -> tuple[Image.Image, str, float]:
    """一张：源图 → 裁/缩 → 量化 → 写 out_root/finale_event/<name>.png 与 QA 三联；
    asset_dir 非空时另存入库成品 asset_dir/<name>.png。out_root 缺省 build/（经 bake_out.out_dir）。"""
    srcim = Image.open(src)
    mid = downsample(srcim)
    q, method, err = quantize_best(mid)
    final = to_rgba_palette(q)
    assert len(final.convert("RGBA").getcolors(COLORS) or []) <= COLORS
    dbg = out_dir(FACE) if out_root is None else Path(out_root) / FACE
    dbg.mkdir(parents=True, exist_ok=True)
    final.save(dbg / f"{name}.png")
    compose_ab(tpl, mid, final).save(dbg / f"_ab_{name}_2x.png")
    if asset_dir is not None:
        asset_dir.mkdir(parents=True, exist_ok=True)
        final.save(asset_dir / f"{name}.png")
    print(f"{name}: 源 {srcim.size[0]}x{srcim.size[1]} → 裁 {crop_to_aspect(srcim).size} → {W}x{H}；"
          f"量化 {COLORS} 色：{method} MSE={err:.2f}")
    return final, method, err


def main() -> None:
    tpl = Image.open(TEMPLATE_PNG)
    assert tpl.size == (W, H), f"eve_74_x 模板尺寸变了：{tpl.size}"
    for name, src in JOBS:
        bake(name, src, tpl, asset_dir=ASSETS)
    print(f"{len(JOBS)} 张 -> {out_dir(FACE)}（QA: _ab_<name>_2x.png）＋ {ASSETS}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_bake_finale_event.py -q`
Expected: 6 passed。

- [ ] **Step 5: 产图并目检**

Run: `uv run python tools/bake_finale_event.py`
Expected: 四行 `<name>: 源 … 量化 256 色：<方法> MSE=<数>`；`eve_74_z` 那行的方法与 MSE 与上一版一致（MEDIANCUT，≈15.4）——证明清单化没改变鲸客人的像素（可再 `git diff --stat docs/finale/assets/eve_74_z.png` 确认无改动）。用 Read 工具看 `build/finale_event/_ab_eve_47_f_2x.png`、`_ab_eve_47_d_2x.png`、`_ab_eve_47_g_2x.png` 的第三联：发色/尾鳍/睡眠眼罩等细节不糊、平涂面无噪点。MSE 若 >30 记进提交说明但不阻塞（eve_74_z 先例 15.4）。

- [ ] **Step 6: 提交**

```bash
git add tools/bake_finale_event.py tests/test_bake_finale_event.py
git commit -m "feat: bake_finale_event 清单化——鲸客人＋三位少女 CG（eve_47_f/d/g，母本 eve_47_x）同一流程产出

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git add docs/finale/assets/eve_47_f.png docs/finale/assets/eve_47_d.png docs/finale/assets/eve_47_g.png
git commit -m "data: 谢幕第二段三位少女 CG 入库成品（480×272 预量化 256 色）

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

