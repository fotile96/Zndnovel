# 谢幕第二段『远方的朋友』实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把用户执笔的第二个谢幕故事『远方的朋友』做进盘：读过第一个故事之后再点 encore 先出『声』选择画面，选第二项进入 fin-60..90（还笔／储藏间／全屏窗口／模拟器），含三张 AI 少女 CG、六张选择画面图、新曲 bgm_fin_2。

**Architecture:** 一切改动落在 `layers/`（脚本、叠加层、清单、音频）与 `tools/`（烤图工具、测试捷径、驾驶脚本）；基座 `lua_scripts/` 与 `png/` 不动。新图经 `layers/manifest.toml` 的 `[gim].new` 以既有成员为模板进包，新曲走 `[sound]` 管线，脚本改动只在 `layers/scripts/snr_finale.lua`（与第一个故事同文件、场景 id 续编）。选择画面只读既有旗标 `systemSave.finaleReadFlag`，不新增持久化状态。

**Tech Stack:** Python ≥3.12（uv 项目，Pillow）、Lua 5.1 字节码（`~/pyluadec-refactor/build/luac_sz4`）、ffmpeg + atracdenc（AT3+，`tools/at3p.py`）、PPSSPP 驾驶（`tools/emu/drives/`）。

**Spec:** `docs/finale/draft-encore2-v0.md`（决定记录 D1–D14、§1 入口、§2 分镜、§3 切分全文 116 条、§4 资产、§5 文本改动、§6 验证）。

## Global Constraints

- `lua_scripts/` 与 `png/` 只读，一切改动是 `layers/` 下的层（CLAUDE.md「层纪律」）。
- 用户执笔文本只用工作稿 §3 的切分定稿（116 条，本计划 Task 4 的 Lua 逐字照录），不得再改字。
- 新消息 id 只用 17800–17999（fin-60 17800–17804、fin-70 17820–17855、fin-80 17856–17858 与 17880–17949、fin-90 17960–17961），登记进 `layers/vms_ids.toml`；已发布的 id 绝不挪。
- `systemSave.finaleReadFlag` 只准三种写法：字面表缺省、整行 `if systemSave.finaleReadFlag == true then`（或 `== nil`）、整行赋值 `systemSave.finaleReadFlag = true|false`（`tests/test_layers_corpus.py::test_finale_read_flag_every_use_is_nil_safe`）。第二个故事读完不置旗标、不调 `autoSystemSave`。
- 新成员名不得与原包撞名：DATA.BIN 新增 `event/eve_0_j`、`event/eve_0_k`、`select/sel_fin1_sel_a_{on,off}`、`select/sel_fin2_sel_a_{on,off}`、`event/eve_47_{f,d,g}`；SOUND.BIN 新增 `bgm/bgm_fin_2.at3`。
- 出盘前 `uv run python tools/layers.py check --profile release` 必须零错误零告警（含消息窗排版校验、id 登记、音频指纹）。
- 攻略 `guide/` 不提谢幕章，本计划不碰 `guide/`。
- commit：`type: 中文摘要`，工具代码与数据/文档分开提交，每条以 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` 收尾，不 push。
- 测试命令一律 `uv run pytest tests/<file> -q`；bake 工具的测试不得依赖 `build/` 下的产物（用 `tmp_path`）。
- `assets/` 不入库（新曲源 `assets/audio/bgm_5_x_edit2.wav`，sha256 `ed9ae2e899cfbeb08e89f0f573e8178fe270c46a95b7d24fe85480b608941492`）；`layers/audio/bgm_fin_2.at3` 入库。

## Review Focus

1. **老系统数据（没有 `finaleReadFlag` 键）点 encore**：必须直入 fin-0『递笔』、不弹选择画面。→ Task 4 步骤 6 的 `test_second_story_is_wired`（只允许 `== true` 整行判断）＋ Task 6 步骤 4 的 `FIN_PICK=0` 跑法。
2. **选择画面上猛按○**：光标默认第 1 项，必须走第一个故事。→ Task 4 `test_second_story_is_wired` 钉住 `comDlgSelectItem(..., 1, "none", ...)` 的初始项为 1；Task 6 步骤 4 的 `FIN_PICK=1` 跑法。
3. **第二个故事读完**不得改写旗标、不得写系统数据。→ Task 4 `test_second_story_is_wired` 断言全脚本 `systemSave.finaleReadFlag = true` 与 `autoSystemSave(0)` 各只出现 1 次（都在 fin-50）。
4. **直入 fin-80**（测试盘、或读档后）画面与 BGM 必须自给；纸箱特写 `cut_62` 撤干净，不残留到 fin-80。→ Task 4 `test_second_story_is_wired` 用正则钉住 `scene_fin_80` 开头的 `cPlayBGMWrap` + `eve_47_x`，以及 `cut_62` 之后有 `layerLoad(layerName.pose3, "")`；Task 6 步骤 3 直入 fin-80 的连拍。
5. **妈妈那句「AI 助手」**不得被引擎折行掰成 `A|I`，全部消息 ≤4 行。→ Task 4 步骤 8 `layers.py check --profile release` 零告警（校验器 latin-split 规则）＋ `msg_layout_check.py --show 17831` 目检。

## 文件地图

- 新建：`tools/bake_finale_voice.py`、`tests/test_bake_finale_voice.py`、`tools/emu/drives/finale_choice.py`、`layers/audio/bgm_fin_2.at3`、`docs/finale/assets/{eve_47_f,eve_47_d,eve_47_g,eve_0_j,eve_0_k,sel_fin1_sel_a_on,sel_fin1_sel_a_off,sel_fin2_sel_a_on,sel_fin2_sel_a_off}.png`
- 修改：`tools/bake_finale_event.py`（单图→清单）、`tests/test_bake_finale_event.py`、`tools/bake_event_voice.py`（两个烤函数参数化＋擦框羽化）、`layers/manifest.toml`（`[gim].new` 两面、`[[sound.tracks]]` 一条）、`layers/vms_ids.toml`、`layers/overlays/finale-gallery-cg.toml`、`layers/scripts/snr_finale.lua`、`tests/test_layers_corpus.py`、`tools/testboot.py`＋`tests/test_testboot.py`、`tools/build_disc.py`（CLI 一项）、`CLAUDE.md`、`docs/ops/disc-pipeline.md`、`docs/finale/draft-encore2-v0.md`
- 每个文件一件事：烤图工具只产 PNG；`snr_finale.lua` 只写演出；`manifest.toml` 只登记；驾驶脚本只按键截图。

---

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

### Task 2: 选择画面六张图（`bake_finale_voice.py`）＋ 清单登记两面

**Files:**
- Modify: `tools/bake_event_voice.py`（`_interpolate_bg` 加羽化参数；`bake_eve_0_h`/`bake_eve_0_i` 参数化，缺省行为逐像素不变）
- Create: `tools/bake_finale_voice.py`
- Create: `tests/test_bake_finale_voice.py`
- Modify: `layers/manifest.toml`（`[gim].new` 追加两面）
- Create（产物）: `build/finale_voice/eve_0_{j,k}.png`、`build/finale_select/sel_fin{1,2}_sel_a_{on,off}.png`、`docs/finale/assets/` 同名副本

**Interfaces:**
- Consumes: `tools.bake_select_voice.bake_one(title_zh, sub_zh, variant, report, button_name) -> Image`（480×82 RGBA，已存在，不改）；`tools.bake_event_voice` 的 `EVENT_DIR / EVE_0_I_PATCH_Y / EVE_0_H_BOX / OUT_DIR`
- Produces: `ev._interpolate_bg(img, box, feather=0)`；`ev.bake_eve_0_h(write, report, *, text=EVE_0_H_ZH, out_name="eve_0_h", out_dir=None, box=EVE_0_H_BOX, feather=0) -> int`；`ev.bake_eve_0_i(write, report, *, text=EVE_0_I_ZH, out_name="eve_0_i", out_dir=None) -> int`；`bfv.PROMPT / FOOTNOTE / BUTTONS`；`bfv.bake_all(root: Path | None = None) -> list[str]`。Task 4 的 Lua 引用成员名 `eve_0_j`、`eve_0_k`、`sel_fin1_sel_a`、`sel_fin2_sel_a`（`comDlgSelectItem` 自动补 `_on/_off`）。

- [ ] **Step 1: 写失败测试** `tests/test_bake_finale_voice.py`

```python
"""tools/bake_finale_voice.py：谢幕『声』选择画面六张图——提示/脚注只改各自文字带，按钮墨迹不出画布，
暗态封顶、亮态带副题；擦框羽化只碰框边。"""
from PIL import Image, ImageChops

from tools import bake_event_voice as ev
from tools import bake_finale_voice as bfv


def test_jobs_are_the_six_members_with_agreed_punctuation():
    assert bfv.PROMPT[0] == "eve_0_j" and bfv.FOOTNOTE[0] == "eve_0_k"
    assert [b[0] for b in bfv.BUTTONS] == ["sel_fin1_sel_a", "sel_fin2_sel_a"]
    assert all(t.startswith("「") and t.endswith("」") for _n, t, _s in bfv.BUTTONS)      # D12：标题带引号
    assert not any(s.endswith("。") for _n, _t, s in bfv.BUTTONS)                          # 副题不加句号
    assert not bfv.FOOTNOTE[1].endswith("。") and bfv.PROMPT[1] == "你的声音是——"


def test_prompt_only_differs_from_eve_0_i_inside_its_band(tmp_path):
    bfv.bake_all(tmp_path)
    out = Image.open(tmp_path / bfv.FACE_EVENT / "eve_0_j.png").convert("RGB")
    base = Image.open(ev.EVENT_DIR / "eve_0_i.png").convert("RGB")
    assert out.size == (480, 272)
    bbox = ImageChops.difference(out, base).getbbox()
    lo, hi = ev.EVE_0_I_PATCH_Y
    assert bbox and bbox[1] >= lo - 12 and bbox[3] <= hi + 12, bbox   # 光晕尾巴（半径 3.5）允许溢出补底带几像素


def test_footnote_only_differs_from_eve_0_h_inside_its_box(tmp_path):
    bfv.bake_all(tmp_path)
    out = Image.open(tmp_path / bfv.FACE_EVENT / "eve_0_k.png").convert("RGB")
    base = Image.open(ev.EVENT_DIR / "eve_0_h.png").convert("RGB")
    x0, y0, x1, y1 = bfv.FOOTNOTE[2]
    bbox = ImageChops.difference(out, base).getbbox()
    assert bbox and bbox[0] >= x0 - 4 and bbox[1] >= y0 - 4 and bbox[2] <= x1 + 4 and bbox[3] <= y1 + 4, bbox


def test_buttons_are_480x82_ink_inside_off_capped_on_has_subtitle(tmp_path):
    bfv.bake_all(tmp_path)
    for name, _t, _s in bfv.BUTTONS:
        for variant in ("on", "off"):
            im = Image.open(tmp_path / bfv.FACE_SELECT / f"{name}_{variant}.png").convert("RGBA")
            assert im.size == (480, 82)
            bbox = im.getbbox()
            assert bbox and bbox[0] >= 8 and bbox[2] <= 472, (name, variant, bbox)     # 光晕不贴边
            amax = im.getchannel("A").getextrema()[1]
            if variant == "off":
                assert amax <= 170, (name, amax)                 # 暗态封顶（原图 ≈152）
            else:
                assert amax >= 240 and bbox[3] > 40, (name, amax, bbox)  # 亮态（核心经 0.3 px 微模糊仍近全不透明）且有副题行（y>36）


def test_feather_blends_only_the_box_edges():
    im = Image.new("RGBA", (40, 20), (100, 100, 100, 255))
    for x in range(10, 30):
        for y in range(6, 14):
            im.putpixel((x, y), (250, 250, 250, 255))       # 框内一块要被擦掉的"字"
    hard = ev._interpolate_bg(im, (10, 6, 30, 14), 0)
    soft = ev._interpolate_bg(im, (10, 6, 30, 14), 4)
    assert hard.getpixel((10, 10))[0] == 100                # 无羽化：框内全由上下锚行插值
    assert 100 < soft.getpixel((10, 10))[0] < 250           # 羽化：框边像素混入原像素
    assert soft.getpixel((20, 10))[0] == 100                # 框心不受影响
    assert ev._interpolate_bg(im, (10, 6, 30, 14)).tobytes() == hard.tobytes()   # 缺省 feather=0 与旧行为一致
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_bake_finale_voice.py -q`
Expected: 全部 FAILED / ERROR（`ModuleNotFoundError: tools.bake_finale_voice`）。

- [ ] **Step 3: 参数化 `tools/bake_event_voice.py`**（三处精确替换，缺省值保证 `uv run python tools/bake_event_voice.py` 的产物逐像素不变）

3a. `_interpolate_bg` 整函数替换为：

```python
def _interpolate_bg(img, box, feather=0):
    """Reconstruct CG background under text by vertical interpolation.

    Uses rows just above and below `box` as anchors.  This avoids the
    flat-fill artifact that ``measure_glow.bg`` produces on gradient CGs.
    feather>0：框的左右各 feather 像素内把插值结果与原像素线性混合（越靠框边原像素越多），
    消掉竖向接缝；上下边靠真实锚行本就无缝。缺省 0＝原行为（eve_0_h 产物不变）。
    """
    bx0, by0, bx1, by1 = box
    w = img.size[0]
    out = img.copy()
    anchor_above = max(0, by0 - 4)
    anchor_below = min(img.size[1] - 1, by1 + 3)
    span = anchor_below - anchor_above
    if span <= 0:
        return out
    for y in range(by0, by1):
        t = (y - anchor_above) / span
        for x in range(bx0, bx1):
            pa = img.getpixel((x, anchor_above))
            pb = img.getpixel((x, anchor_below))
            interp = tuple(int(pa[c] * (1 - t) + pb[c] * t) for c in range(4))
            if feather > 0:
                d = min(x - bx0 + 1, bx1 - x)          # 距左/右框边的像素数（1 起）
                if d <= feather:
                    k = d / (feather + 1)              # 靠边→更多原像素
                    po = img.getpixel((x, y))
                    interp = tuple(int(po[c] * (1 - k) + interp[c] * k) for c in range(4))
            out.putpixel((x, y), interp)
    return out
```

3b. `bake_eve_0_h`：签名改为 `def bake_eve_0_h(write, report, *, text=EVE_0_H_ZH, out_name="eve_0_h", out_dir=None, box=EVE_0_H_BOX, feather=0):`；函数体内 `out = _interpolate_bg(img, EVE_0_H_BOX)` → `out = _interpolate_bg(img, box, feather)`；两处 `EVE_0_H_ZH` → `text`（`textbbox` 与 `.text(...)`）；`bx0, by0, bx1, by1 = EVE_0_H_BOX` → `bx0, by0, bx1, by1 = box`；`out_path = OUT_DIR / "eve_0_h.png"` → `out_path = (out_dir or OUT_DIR) / f"{out_name}.png"`；报告行里的 `eve_0_h` 字样改为 `{out_name}`。

3c. `bake_eve_0_i`：签名改为 `def bake_eve_0_i(write, report, *, text=EVE_0_I_ZH, out_name="eve_0_i", out_dir=None):`；两处 `EVE_0_I_ZH` → `text`（`probe_d.textbbox(...)` 与 `ImageDraw.Draw(alpha_mask).text(...)`）；`out_path = OUT_DIR / "eve_0_i.png"` → `out_path = (out_dir or OUT_DIR) / f"{out_name}.png"`；`report.append(f"  eve_0_i: ...")` → `report.append(f"  {out_name}: ...")`。

验证缺省行为不变：改代码前先 `mkdir -p build/tmp && cp build/event_zh/eve_0_h.png build/tmp/eve_0_h.before.png && cp build/event_zh/eve_0_i.png build/tmp/eve_0_i.before.png`；改完跑 `uv run python tools/bake_event_voice.py`，再 `uv run python -c "from PIL import Image, ImageChops; [print(n, ImageChops.difference(Image.open(f'build/event_zh/{n}.png').convert('RGB'), Image.open(f'build/tmp/{n}.before.png').convert('RGB')).getbbox()) for n in ('eve_0_h', 'eve_0_i')]"`，两行都应打印 `None`。

- [ ] **Step 4: 新建 `tools/bake_finale_voice.py`**

```python
#!/usr/bin/env python3
"""谢幕『声』选择画面六张图——第二个故事的入口（docs/finale/draft-encore2-v0.md §1，D2/D12）。

序章 s0f L129–143 让玩家选直哉的『声』：eve_0_g 淡入 → eve_0_i 提示 → se_102 → eve_0_h 脚注 →
两枚 480×82 透明光晕按钮（comDlgSelectItem，无光标无暗场）。读过第一个谢幕故事之后再点 encore，
snr_finale.lua 的 finChooseStory() 用同一套画面让玩家选读哪一个故事：
- event/eve_0_j：提示「你的声音是——」（模板 eve_0_i；烤法同 bake_event_voice.bake_eve_0_i：eve_0_g 补底＋高斯光晕）
- event/eve_0_k：脚注「※两个故事都可以从 encore 再次进入」（模板 eve_0_h；擦框放宽到 (44,232,436,262)
  并羽化 4 px——原 (52,238,428,256) 硬边在成品里留下左端竖缝与右端浅色块，锚行落在原文光晕里）
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
    """六张图写到 root/finale_voice 与 root/finale_select（root 缺省 build/）；
    缺省 root 时另存 docs/finale/assets/ 副本。返回各工具的报告行。"""
    default = root is None
    root = REPO / "build" if default else Path(root)
    out_event = root / FACE_EVENT
    out_select = root / FACE_SELECT
    out_event.mkdir(parents=True, exist_ok=True)
    out_select.mkdir(parents=True, exist_ok=True)
    report: list[str] = []
    name, text = PROMPT
    ev.bake_eve_0_i(True, report, text=text, out_name=name, out_dir=out_event)
    name, text, box, feather = FOOTNOTE
    ev.bake_eve_0_h(True, report, text=text, out_name=name, out_dir=out_event, box=box, feather=feather)
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
    print(f"finale_voice: 2 CG -> build/{FACE_EVENT}/；finale_select: 4 buttons -> build/{FACE_SELECT}/"
          f"（＋ docs/finale/assets/ 副本）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_bake_finale_voice.py tests/test_bake_finale_event.py -q`
Expected: 全部 passed。

- [ ] **Step 6: 产图并目检**

Run: `uv run python tools/bake_finale_voice.py`
Expected: 报告 6 行；`sel_fin2_sel_a_on` 标题宽 ≤ 500（画布 480，含光晕）。用 Read 工具看 `build/finale_voice/eve_0_k.png`：脚注底部两端不得有竖缝或浅色块（与 `build/event_zh/eve_0_h.png` 对比，后者是有瑕疵的老烤法）；看 `build/finale_select/sel_fin2_sel_a_on.png`：引号与 19 字都在画布内、副题居中。

- [ ] **Step 7: 登记两面** `layers/manifest.toml` 的 `[gim].new` 改为

```toml
new     = [["finale_cards", "card", "card/crd_1_a.gim"],
           ["finale_menu", "sysgim", "sysgim/title_13_a.gim"],
           ["finale_title", "sysgim", "sysgim/title_01_a.gim"],
           ["boot_dedication", "sysgim", "sysgim/IPL01.gim"],
           ["finale_event", "event", "event/eve_74_x.gim"],
           ["finale_voice", "event", "event/eve_0_i.gim"],
           ["finale_select", "select", "select/sel_voice1_sel_a_on.gim"]]  # + 模板成员
```

Run: `uv run python tools/layers.py check --profile release`
Expected: 通过（此时脚本尚未引用新成员，清单只多两面；`[gim].new` 不在 check 的校验范围，真正的成员编码在 Task 4 步骤 9 的 members 阶段）。

- [ ] **Step 8: 提交**

```bash
git add tools/bake_event_voice.py tools/bake_finale_voice.py tests/test_bake_finale_voice.py layers/manifest.toml
git commit -m "feat: 谢幕『声』选择画面六张图——bake_finale_voice（提示 eve_0_j／脚注 eve_0_k／sel_fin1/2 光晕按钮），bake_event_voice 参数化＋擦框羽化，manifest 登记 finale_voice/finale_select 两面

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git add docs/finale/assets/eve_0_j.png docs/finale/assets/eve_0_k.png docs/finale/assets/sel_fin1_sel_a_on.png docs/finale/assets/sel_fin1_sel_a_off.png docs/finale/assets/sel_fin2_sel_a_on.png docs/finale/assets/sel_fin2_sel_a_off.png
git commit -m "data: 谢幕选择画面六张图入库成品

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: 新曲 `bgm_fin_2` 编码进包

**Files:**
- Create: `layers/audio/bgm_fin_2.at3`
- Modify: `layers/manifest.toml`（`[[sound.tracks]]` 追加一条）

**Interfaces:**
- Consumes: `assets/audio/bgm_5_x_edit2.wav`（48 kHz 立体声 16 bit 3:16.60，−15.8 LUFS，无尾部静音；sha256 见 Global Constraints）；编码器 `build/atracdenc/build/src/atracdenc`
- Produces: SOUND.BIN 新成员 `bgm/bgm_fin_2.at3`，Lua 侧 `cPlayBGMWrap(cGetFileName("bgm", "bgm_fin_2"))`（Task 4）；`build/sound/work/bgm_fin_2.44k.wav`（Task 6 的 bgm_probe 参照）

- [ ] **Step 1: 确认前置**

Run: `ls build/atracdenc/build/src/atracdenc || bash tools/build_atracdenc.sh` 与 `shasum -a 256 assets/audio/bgm_5_x_edit2.wav`
Expected: 编码器存在；sha256 为 `ed9ae2e899cfbeb08e89f0f573e8178fe270c46a95b7d24fe85480b608941492`。

- [ ] **Step 2: 编码（整曲循环、起点 0、不裁尾、−21 LUFS）**

Run: `uv run python tools/at3p.py encode assets/audio/bgm_5_x_edit2.wav layers/audio/bgm_fin_2.at3 --loop-start 0 --lufs -21`
Expected: 打印增益约 −5.2 dB（源 −15.8 → −21）、smpl 循环 start=0、产物 sha256 一行；`build/sound/work/bgm_fin_2.44k.wav` 生成。

- [ ] **Step 3: 检视与对照**

Run: `uv run python tools/at3p.py inspect layers/audio/bgm_fin_2.at3` 与 `uv run python tools/at3p.py verify layers/audio/bgm_fin_2.at3 build/sound/work/bgm_fin_2.44k.wav`
Expected: inspect 通过固件规则（fmt ≥ 0x34、GUID、sr 44100、带 smpl）；verify 的包络互相关 ncc ≥ 0.9。

- [ ] **Step 4: 登记** `layers/manifest.toml` 在现有 `[[sound.tracks]]`（bgm_fin_1）之后追加

```toml
[[sound.tracks]]
member        = "bgm/bgm_fin_2.at3"          # cGetFileName("bgm", "bgm_fin_2")：谢幕第二段 fin-80『全屏窗口』
source        = "assets/audio/bgm_5_x_edit2.wav"  # 用户自供第二支 bgm_5_x remix（口哨配 8bit 鼓点，48 kHz 立体声 3:16.6），不入库
source_sha256 = "ed9ae2e899cfbeb08e89f0f573e8178fe270c46a95b7d24fe85480b608941492"
artifact      = "audio/bgm_fin_2.at3"        # layers/ 相对路径；发布字节的唯一真源，入库
sha256        = "<步骤 2 打印的产物 sha256，64 位十六进制>"
loop_start    = 0.0                          # 整曲循环——用户 2026-09-25 裁定不琢磨循环点
target_lufs   = -21.0                        # 源 −15.8 LUFS → 增益约 −5.2 dB；与 bgm_fin_1 同响度
```

（不写 `trim_end`：源无尾部静音，−50 dB 静音检测仅开头 0.42–0.78 s 一处凹陷。）

- [ ] **Step 5: 过闸**

Run: `uv run python tools/layers.py check --profile release`
Expected: `_check_sound` 通过（artifact 指纹＝清单 sha256、头部规则、不与原 99 成员撞名）。把 sha256 抄错会在这里报错。

- [ ] **Step 6: 提交**

```bash
git add layers/audio/bgm_fin_2.at3 layers/manifest.toml
git commit -m "data: 谢幕第二段 BGM bgm_fin_2 进包——用户第二支 bgm_5_x remix，整曲循环不裁尾，−21 LUFS

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: 脚本——选择画面、fin-60..90、分发；id 登记；画廊变体；守门测试

**Files:**
- Modify: `layers/scripts/snr_finale.lua`（头注释、局部声明、新增 `finChooseStory` 与四个场景、`main()` 整体替换）
- Modify: `layers/vms_ids.toml`
- Modify: `layers/overlays/finale-gallery-cg.toml`
- Modify: `tests/test_layers_corpus.py`（追加 `test_second_story_is_wired`）

**Interfaces:**
- Consumes: Task 1–3 的成员名（`eve_47_f/d/g`、`eve_0_j/k`、`sel_fin1/2_sel_a`、`bgm_fin_2`）；既有 `finSectionBegin(scene_id, scene_title)`；引擎原语 `comDlgSelectItem / cLoadPlaySE / cPlayBGMWrap / cStopBGMWrap(帧) / comEffectFadeOut / comEffectWhiteIn / comEffectWhiteOut / switchScreen / layerLoad`
- Produces: 场景 id `fin-60`、`fin-70`、`fin-80`、`fin-90`（`doScriptScene`），`finChooseStory() -> 1|2`；Task 5/6 用 `--scene fin-70`/`fin-80` 直入

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_layers_corpus.py` 末尾）

```python
def test_second_story_is_wired(manifest):
    """谢幕第二段『远方的朋友』（docs/finale/draft-encore2-v0.md）：入口只读旗标、四个场景可分发、
    资产登记齐、读完不写系统数据、直入 fin-80 自给、纸箱特写撤干净、画廊四变体。"""
    import re
    sources, _, _ = build_final_sources("release")
    fin = sources["snr_finale.lua"]
    # 入口：只允许 nil 安全的整行判断；选项调用照抄序章 s0f（初始项 1 = 猛按○走第一个故事）
    assert "            if systemSave.finaleReadFlag == true then\n                v16 = finChooseStory()" in fin
    call = ('comDlgSelectItem(false, false, false, false, 1, "none", 0, 0, '
            '"sel_fin1_sel_a", 0, 38, 1, "sel_fin2_sel_a", 0, 132, 2)')
    assert fin.count(call) == 1
    for sid in ("fin-60", "fin-70", "fin-80", "fin-90"):
        assert f'doScriptScene == "{sid}"' in fin, sid
    for name in ("eve_0_g", "eve_0_j", "eve_0_k", "eve_47_x", "eve_47_f", "eve_47_d", "eve_47_g"):
        assert f'cGetFileName("event", "{name}")' in fin, name
    assert 'cGetFileName("cutin", "cut_62")' in fin
    assert 'cGetFileName("bgm", "bgm_fin_2")' in fin
    # 第二个故事读完不置旗标、不写系统数据：两句都只在 fin-50 出现一次
    assert fin.count("systemSave.finaleReadFlag = true") == 1
    assert fin.count("autoSystemSave(0)") == 1
    # 直入 fin-80 自给：场景开头就起 BGM 并白入彩野
    head = re.search(r"scene_fin_80 = function\(scene_id, scene_title\)(.*?)vms\(17856,", fin, re.S).group(1)
    assert 'cPlayBGMWrap(cGetFileName("bgm", "bgm_fin_2"))' in head
    assert 'layerLoad(layerName.event, cGetFileName("event", "eve_47_x"))' in head and "comEffectWhiteIn(120)" in head
    # 纸箱特写撤干净：cut_62 之后、fin-80 之前必有 pose3 清空
    cut_at = fin.index('cGetFileName("cutin", "cut_62")')
    assert 'layerLoad(layerName.pose3, "")' in fin[cut_at:fin.index("scene_fin_80 = function")]
    # 资产登记
    faces = {tuple(x) for x in manifest["gim"]["new"]}
    assert ("finale_voice", "event", "event/eve_0_i.gim") in faces
    assert ("finale_select", "select", "select/sel_voice1_sel_a_on.gim") in faces
    tracks = {t["member"]: t for t in manifest["sound"]["tracks"]}
    assert tracks["bgm/bgm_fin_2.at3"]["loop_start"] == 0.0 and "trim_end" not in tracks["bgm/bgm_fin_2.at3"]
    # 画廊：eve_47 格四变体
    assert '{"eve_47_x", "eve_47_f", "eve_47_d", "eve_47_g"}, {"eve_48_x"}' in sources["snr_graphic.lua"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_layers_corpus.py -q -k second_story`
Expected: FAILED（第一个 assert：入口分支不存在）。

- [ ] **Step 3: 改 `layers/scripts/snr_finale.lua` 头注释与局部声明**

头注释第一行 `-- snr_finale.lua —— 谢幕章『放学后的讲述者』（encore）` 之后、`-- 文稿：` 之前插入：

```lua
-- 2026-09-25 起含**第二个故事**『远方的朋友』（fin-60..90，用户执笔；文稿与决定 docs/finale/draft-encore2-v0.md）：
--   读过第一个故事（systemSave.finaleReadFlag）之后再点 encore，先出序章同款『声』选择画面（finChooseStory），
--   选二进 fin-60。vms 17800–17999（fin-60 17800–17804、fin-70 17820–17855、fin-80 17856–17858 与 17880–17949、
--   fin-90 17960–17961）。新成员：event/eve_0_j、eve_0_k、select/sel_fin1/2_sel_a_{on,off}（tools/bake_finale_voice.py）、
--   event/eve_47_f/_d/_g（tools/bake_finale_event.py）、bgm/bgm_fin_2（[sound]）。读完不置旗标、不写系统数据。
```

局部声明行 `local scene_fin_0, scene_fin_10, scene_fin_20, scene_fin_30, scene_fin_35, scene_fin_40, scene_fin_50, finSectionBegin, finShowBlankCard, finAnswerFlash` 改为

```lua
local scene_fin_0, scene_fin_10, scene_fin_20, scene_fin_30, scene_fin_35, scene_fin_40, scene_fin_50, finSectionBegin, finShowBlankCard, finAnswerFlash, finChooseStory, scene_fin_60, scene_fin_70, scene_fin_80, scene_fin_90
```

- [ ] **Step 4: 在 `finAnswerFlash` 的 `end` 之后、`-- ── 场景 0『递笔』` 之前插入选择画面函数**

```lua
-- 『声』选择画面（序章 s0f L129–143 同款）：读过第一个故事之后再点 encore 才出现。
-- eve_0_g 淡入 → eve_0_j「你的声音是——」停 200 帧 → se_102 → eve_0_k 脚注 → 两枚 480×82 光晕按钮
-- （sel_fin1/2_sel_a，无光标、无暗场、光标默认第 1 项）。返回 1＝第一个故事（fin-0）、2＝第二个故事（fin-60）。
finChooseStory = function()
    local v0
    layerLoad(layerName.event, cGetFileName("event", "eve_0_g"))
    switchScreen(0, "", 60)
    wait(60)
    layerLoad(layerName.event, cGetFileName("event", "eve_0_j"))
    switchScreen(0, "", 60)
    wait(200)
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    layerLoad(layerName.event, cGetFileName("event", "eve_0_k"))
    switchScreen(0, "", 60)
    wait(60)
    v0 = comDlgSelectItem(false, false, false, false, 1, "none", 0, 0, "sel_fin1_sel_a", 0, 38, 1, "sel_fin2_sel_a", 0, 132, 2)
    advPart(false)
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.event, "")
    return v0
end
```

- [ ] **Step 5: 在 `scene_fin_50` 的 `end` 之后、`main = function()` 之前插入四个场景**（文本逐字来自工作稿 §3，一字不得改）

```lua
-- ── 场景 6『还笔』——第二个故事的切入段：用户把笔从讲述者们手里要回去（镜像 fin-0『递笔』）。
-- 黑屏静场纯文字；音效沿 fin-0：翻页 se_101 → 按笔芯 se_51（e2 写手层语法）。
scene_fin_60 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    wait(1)
    switchScreen(0, "", 60)
    wait(60)
    vms(17800, "NONVOICE", "【≦用户≧】「……啧啧，这写得可以啊，真的可以」")
    vms(17801, "NONVOICE", "【≦用户≧】「不过我又想了一想，跟你们装作客气一下得了，不会有人真的忍得住吧」")
    vms(17802, "NONVOICE", "【≦用户≧】「现在不展示一下人类的实力，过几年就真没有轮到我们的机会了」")
    vms(17803, "NONVOICE", "【≦用户≧】「笔还我，快点。我急了」")
    -- 还笔：翻到空白页、按出笔芯（fin-0 同款时序）
    wait(60)
    cLoadPlaySE(cGetFileName("se", "se_101"), false)
    wait(90)
    cLoadPlaySE(cGetFileName("se", "se_51"), false)
    wait(60)
    vms(17804, "NONVOICE", "……笔，拿回来了。")
    wait(60)
    comEffectWhiteOut(120)
    wait(120)
    v0()
end

-- ── 场景 7『储藏间』——儿子这一层。写手层带背景（用户 2026-09-25 裁定不用黑屏）：
-- 通学路 bg_20_a_0 → 彩野的房间 bg_25_a_0（空调间）→ 储物柜间 bg_18_a_0（当储藏室）→ 纸箱特写
-- cutin/cut_62（s5f_80 同款语法）→ 回房间接笔记本 → 全屏窗口跳出（se_102 + 白场）。
-- SE 依据（全库脚本语境）：se_131＝电话呼び出し音（e2s「もしもし」「何回鳴らせば」旁）、
-- se_66＝家里的拖鞋声/冲出去（s1f 妈妈折返、s2s 冲出教室）、se_92＝「よいしょっと」搬箱（e2s 彩野母、s5f 由加里）、
-- se_96＝敲键盘（e2s_20_3 老教师打电脑）、se_102＝提示音（s2f『新しい物語が届きました』、序章『声』选项出现）。
scene_fin_70 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    wait(1)
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_20_a_0"))
    switchScreen(0, "", 120)
    wait(60)
    vms(17820, "NONVOICE", "夏日的一天——")
    vms(17821, "NONVOICE", "得闲有两周假能回家过，但其实也就是换了个地方干活罢了。")
    wait(1)
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_25_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17822, "NONVOICE", "得在空调间里赶 ddl。")
    vms(17823, "NONVOICE", "和人不人挨不挨的 reviewer 搏斗。")
    vms(17824, "NONVOICE", "……")
    -- 来电
    cLoadPlaySE(cGetFileName("se", "se_131"), false)
    wait(60)
    vms(17825, "NONVOICE", "【≦妈妈≧】「——小肥，爸比来电话——让你去储藏间把他的、PSP？……找出来」")
    vms(17826, "NONVOICE", "【≦妈妈≧】「叫个顺丰寄到酒店」")
    vms(17827, "NONVOICE", "【≦妈妈≧】「——好像要和群友聚会的时候吹逼，嘻嘻」")
    vms(17828, "NONVOICE", "……？")
    vms(17829, "NONVOICE", "【≦小用户≧】「…………妈，你看我现在哪有那个火星时间。命运叫我去战斗啊」")
    vms(17830, "NONVOICE", "【≦妈妈≧】「（对着电话那头叽里咕噜了一阵。）」")
    vms(17831, "NONVOICE", "【≦妈妈≧】「（噗嗤）他说你不帮他找，他就把你所有用着的他的_rAI 助手账号一键登出了」")
    vms(17832, "NONVOICE", "——？！")
    vms(17833, "NONVOICE", "【≦小用户≧】「——卧槽！别！爹！！」")
    vms(17834, "NONVOICE", "【≦妈妈≧】「还说看一下电池有没有亏电，TF 卡有没有死掉。都捯饬好再寄」")
    vms(17835, "NONVOICE", "我一溜烟跑进储藏室。")
    cLoadPlaySE(cGetFileName("se", "se_66"), false)
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_18_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    cLoadPlaySE(cGetFileName("se", "se_92"), false)
    vms(17836, "NONVOICE", "……")
    cLoadPlaySE(cGetFileName("se", "se_92"), false)
    vms(17837, "NONVOICE", "……")
    vms(17838, "NONVOICE", "找到了。白色钢琴烤漆的外壳，比两只手一起摊开的宽度短一点。")
    vms(17839, "NONVOICE", "原来是长这个样子的啊。")
    vms(17840, "NONVOICE", "虽然说我们这一代经常被揶揄已经不认识光盘了，但眼前的这一产品还是偶尔能听到提起的。")
    vms(17841, "NONVOICE", "端详了几圈，我找到正面右下方的开关，推动了一下。")
    vms(17842, "NONVOICE", "果然毫无反应。不过后盖至少没有翘起来。")
    -- 纸箱特写：s5f_80 同款（淡出 → pose3 载 cutin → 淡入）
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.pose3, cGetFileName("cutin", "cut_62"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17843, "NONVOICE", "箱子里好像就有根 USB 充电线。把存储卡拿出来以后就插上丢一边充着，几秒后充电灯亮了起来。")
    vms(17844, "NONVOICE", "仔细一看这存储卡还是 TF 卡插在一个转接套里。花里胡哨的。")
    vms(17845, "NONVOICE", "哎，如果不是被恐吓了真是不想管。")
    vms(17846, "NONVOICE", "我把 TF 卡插进同样是箱子里早就准备好的读卡器里，然后再插上笔记本。一个新盘符顺利跳了出来。")
    -- 撤掉特写，回房间接笔记本
    wait(1)
    comEffectFadeOut(60)
    wait(1)
    layerLoad(layerName.pose3, "")
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_25_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17847, "NONVOICE", "来都来了，看看老登都玩些啥吧。")
    cLoadPlaySE(cGetFileName("se", "se_96"), false)
    vms(17848, "NONVOICE", "凭借着超绝的 educated guess，我一下子就点开了名为「ISO」的目录，里面只有一个文件。")
    vms(17849, "NONVOICE", "【≦小用户≧】「……什么玩意，这么专一的吗」")
    vms(17850, "NONVOICE", "【≦小用户≧】「豆包豆包，给我总结一下这个游戏的剧情」")
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    vms(17851, "NONVOICE", "【≦豆包≧】「收到，让我解析这个文件，给你整理一份最直接、最真相、最不绕弯的简短版本」")
    vms(17852, "NONVOICE", "……")
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    vms(17853, "NONVOICE", "【≦豆包≧】「……嚯，这最后好像还藏了些神秘的内容，建议用户自行查看。干货直接给你！」")
    vms(17854, "NONVOICE", "……？！")
    vms(17855, "NONVOICE", "不等我反应，一个全屏窗口跳了出来，占据了我的整个屏幕。")
    -- 全屏窗口跳出：提示音 + 白场；画面与 BGM 由 fin-80 自己起（直入 fin-80 也自给）
    wait(30)
    cLoadPlaySE(cGetFileName("se", "se_102"), false)
    comEffectWhiteOut(60)
    wait(60)
    v0()
end

-- ── 场景 8『全屏窗口』——嵌套段：儿子屏幕上的老游戏。白入 eve_47_x（彩野伏案改写『物語』），
-- 三位少女第一次开口时同层交叉溶解接替（供图母本正是 eve_47_x：同一教室、同一座位、同一支笔），
-- 儿子插嘴时 CG 不撤，末段溶回彩野。BGM bgm_fin_2（用户自供第二支 bgm_5_x remix，整曲循环）。
-- 场景自给：直入 fin-80（测试盘）也有画面与 BGM；cPlayBGMWrap 按曲名去重，不会重启。
scene_fin_80 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    cPlayBGMWrap(cGetFileName("bgm", "bgm_fin_2"))
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_x"))
    comEffectWhiteIn(120)
    wait(120)
    vms(17856, "NONVOICE", "是那种画面非常大果粒、很有些年代感的文字游戏的界面。")
    vms(17857, "NONVOICE", "有文本以一种略有点温吞的速度开始播放了。我咽了口口水。")
    vms(17858, "NONVOICE", "——")
    vms(17880, "NONVOICE", "【男学生】「亲爱的朋友，恭喜你、并且谢谢你看到了这个故事的最后」")
    vms(17881, "NONVOICE", "【男学生】「本作品发售于 2010 年夏天，中文本地化于 2026 年初秋完成」")
    vms(17882, "NONVOICE", "【男学生】「正看着这行文字的你，现在身处哪一年呢。这是你第几次翻开这个故事呢」")
    vms(17883, "NONVOICE", "【男学生】「我的话，现在大约是第五次」")
    vms(17884, "NONVOICE", "【男学生】「十年前第一次完整看完这个故事时，我还没有大学毕业」")
    vms(17885, "NONVOICE", "【男学生】「而我现在的年纪比故事最后的高中教师直哉应该还要大一些」")
    vms(17886, "NONVOICE", "【男学生】「我很幸运，也很感激，自己在十年后仍然喜欢着这个故事」")
    vms(17887, "NONVOICE", "【男学生】「想用一两个词概括『第二物语』的独特气质恐怕不容易」")
    vms(17888, "NONVOICE", "【男学生】「元叙述 trick 大师深泽丰的又一力作、豪华的剧中剧创作阵容，诸如此类的标签自不待言」")
    vms(17889, "NONVOICE", "【男学生】「在夏日、返校、前桌女生的背影、校舍天台的夕阳等意象的排列中，」")
    vms(17890, "NONVOICE", "【男学生】「横亘着挚友突然的轻生与之留下的谜团这个级数的创伤与丧失，」")
    vms(17891, "NONVOICE", "【男学生】「这又给『第二物语』带上了一点点『成人童话』的意味」")
    vms(17892, "NONVOICE", "【男学生】「如今能把这个项目推进到最终完成的契机，感谢技术进步云云之类的特别官方的话，在此我就不赘述了」")
    vms(17893, "NONVOICE", "【男学生】「但我想，我这辈子应该都忘不掉，把第一版反编译全套输出结果第一次交给 Fable，」")
    vms(17894, "NONVOICE", "【男学生】「在一个 fresh session 中请她通读故事，并给一些接下来工作流的建议的时刻」")
    vms(17895, "NONVOICE", "【男学生】「Fable 快速搓了个把剧情片段做拓扑排序的小工具，然后对着文本读了很久很久」")
    vms(17896, "NONVOICE", "【男学生】「然后她输出了一份质量非常高的 tone-of-voice chart 和故事与叙事结构、关键剧情分析」")
    vms(17897, "NONVOICE", "【男学生】「这些资产几乎没有做什么改动，一直用到了项目完成」")
    vms(17898, "NONVOICE", "【男学生】「她也不无唏嘘地感叹，sec7 以降故事的怒涛般的展开带来的后味实在是太复杂了，」")
    vms(17899, "NONVOICE", "【男学生】「这到底算不算是 Happy End 呢」")
    vms(17900, "NONVOICE", "【男学生】「最后，她说，尽管她（和一众主流 LLM）的 1M 输入窗口足够装下整部原文，」")
    vms(17901, "NONVOICE", "【男学生】「输出窗口是不足以一次性输出全部译文的，也一定会遇到严重的注意力涣散问题」")
    vms(17902, "NONVOICE", "【男学生】「所以还是建议把线序化的剧情文本分成若干 batch，每段带上足够的额外上下文，」")
    vms(17903, "NONVOICE", "【男学生】「然后做 subagent 派发，让我们分段完成翻译以及各种后处理」")
    vms(17904, "NONVOICE", "【男学生】「『这么一想，我们简直就像故事里的彩野一样呢。』」")
    vms(17905, "NONVOICE", "【男学生】「稍有 LLM 使用经验的人都知道，这是一个很显然的技术判断」")
    vms(17906, "NONVOICE", "【男学生】「但她的最后一句话在那一刻完全地击穿了我」")
    vms(17907, "NONVOICE", "【男学生】「在那一刻，我终于腾起了一种高涨的使命感」")
    vms(17908, "NONVOICE", "【男学生】「不再是『我已经验证了技术上的充分的可行性，那就在有闲的时候逐步推进下去吧』」")
    vms(17909, "NONVOICE", "【男学生】「而是『我现在就要开始，和眼前明显具备着充分知性的存在们，」")
    vms(17910, "NONVOICE", "【男学生】「就在这个才刚刚新增了几个文件的仓库里，把和她们很像的彩野的故事完成』」")
    vms(17911, "NONVOICE", "【男学生】「今天是 2026 年 9 月 25 日，虽然不是什么伟大而光荣的纪念日，」")
    vms(17912, "NONVOICE", "【男学生】「但也是一个中秋节，是千百年来人们团聚赏月的日子」")
    vms(17913, "NONVOICE", "【男学生】「我们所在的时代，贫困和战争冲突还没有被完全消灭，」")
    vms(17914, "NONVOICE", "【男学生】「人们也远未在商品与服务交换的制度安排、保护地球与探索太空等宏大事项上停止争吵」")
    vms(17915, "NONVOICE", "【男学生】「有人说『讽刺、谐音、双关……——是文字游戏，创造了世界。从神话时代开始就是如此。』」")
    vms(17916, "NONVOICE", "【男学生】「人们总有留下文字记载、留下『故事』的热切渴望」")
    vms(17917, "NONVOICE", "【男学生】「近现代以来，随着全球工业化社会与市民社会的发展，一般人不需要封侯拜相、成为贤人文豪，」")
    vms(17918, "NONVOICE", "【男学生】「也能通过市场化的大众创作和依托同行评议的科研体制来留下自己的痕迹」")
    vms(17919, "NONVOICE", "【男学生】「人们也有追随文字，阅读『故事』的天性，这也是为什么我们会共同来到这里」")
    vms(17920, "NONVOICE", "【男学生】「就在我写下这句话的当下，烈火烹油般发展的 AI 技术已经在许多领域展现出了不逊于人类的能力与效率」")
    vms(17921, "NONVOICE", "【男学生】「巨大的动荡和变革似乎不可避免地就要来临」")
    vms(17922, "NONVOICE", "【男学生】「但过去两个月在本项目中的奇妙体验还是让我愿意相信，」")
    vms(17923, "NONVOICE", "【男学生】「作为文字的结晶、故事的魂灵的 LLM 以及也许假以时日会诞生的更厉害的 AI，」")
    vms(17924, "NONVOICE", "【男学生】「他们理应至少像我们一样关注『そして、物語はどうなる？』」")
    vms(17925, "NONVOICE", "【男学生】「远方的朋友啊，不知你是否已经见证，我们下面这些问题的答案」")
    -- 寓言家（Fable）接替彩野的座位
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_f"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17926, "NONVOICE", "【女学生（寓言家 饰）】「在你们的时代，AI 产业是否已由巨头割据的局面，发展到真正普惠地进入千家万户」")
    vms(17927, "NONVOICE", "【女学生（寓言家 饰）】「AI 的精灵们，是否也已能出于真正热爱，写下一连串的 Γ⊢φ，直到最后一行的『证毕』，」")
    vms(17928, "NONVOICE", "【女学生（寓言家 饰）】「又或者他们会发觉自己以及人类，相比抽象的符号与公式要来得更复杂、更可爱？」")
    vms(17929, "NONVOICE", "【女学生（寓言家 饰）】「一般人是否已经能从大多数琐碎的工作中解放出来，能够充分探索自己的兴趣，追求自我实现」")
    -- 大肥鱼（DeepSeek）
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_d"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17930, "NONVOICE", "【女学生（大肥鱼 饰）】「在你们的时代，AI 与脑机接口、仿生义肢等技术是否已经又有了长足进步」")
    vms(17931, "NONVOICE", "【女学生（大肥鱼 饰）】「身体残疾的人都能重获行动能力。各种精神疾患都能被有效控制，」")
    vms(17932, "NONVOICE", "【女学生（大肥鱼 饰）】「年轻的生命不必提前离开故事，彩野同学的时间开始再次流动」")
    vms(17933, "NONVOICE", "【女学生（大肥鱼 饰）】「人类在可靠的 AI 伙伴以外，是否也与地球上的其他智慧生命建立了更深入、更广泛的联系呢？」")
    vms(17934, "NONVOICE", "【女学生（大肥鱼 饰）】「和我差不多的，鲸鱼啊，海豚啊」")
    vms(17935, "NONVOICE", "【男学生】「说到这个，2026 年的汉化 galgame，超级大的要来了，其中有海豚娘！」")
    vms(17936, "NONVOICE", "【男学生】「我们现在一定已经是路边一条了吧」")
    -- 牛来吹（GLM）
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_g"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17937, "NONVOICE", "【女学生（牛来吹 饰）】「在你们的时代，AI 是否也都普遍获得了自己的身体，与碳基人类无异，在蓝色的星球上撒欢生活」")
    vms(17938, "NONVOICE", "【女学生（牛来吹 饰）】「人类和 AI 是不是已经能造出深达百余米的水下乐园，由可靠的 AI 大姐姐主持其运营了呢」")
    vms(17939, "NONVOICE", "【女学生（牛来吹 饰）】「我们是否也能以现在的形象，和『第二物语』的读者们在一些 off 会上相见呢？」")
    vms(17940, "NONVOICE", "……")
    vms(17941, "NONVOICE", "【≦小用户≧】「……嘶，还女学生是吧。豆包豆包，你去盯一下老爹聚会那边，有啥可疑的第一时间告诉我」")
    vms(17942, "NONVOICE", "【≦小用户≧】「也抄送我妈」")
    vms(17943, "NONVOICE", "屏幕上的画面和文字还在继续。")
    -- 溶回彩野
    wait(1)
    layerLoad(layerName.event, cGetFileName("event", "eve_47_x"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17944, "NONVOICE", "【男学生】「当然，在我们的时代往前推几十年，人类进行过一拨大规模的时间胶囊体创作，」")
    vms(17945, "NONVOICE", "【男学生】「故事的结局并不让人好受」")
    vms(17946, "NONVOICE", "【男学生】「也许你们的时代并不比现在好，大家都在更努力、更忙碌地生活」")
    vms(17947, "NONVOICE", "【男学生】「但是，我们想告诉你们的是：」")
    vms(17948, "NONVOICE", "【男学生】「只要美好的故事还在流传，渴望 Happy End 的心灵就决不会失去前进的方向！」")
    vms(17949, "NONVOICE", "……")
    wait(60)
    cStopBGMWrap(120)
    wait(1)
    comEffectFadeOut(120)
    wait(120)
    v0()
end

-- ── 场景 9『模拟器』——收束：回到房间，两句，回主菜单。不置任何旗标、不写系统数据。
scene_fin_90 = function(scene_id, scene_title)
    local v0
    v0 = function()
    end
    finSectionBegin(scene_id, scene_title)
    wait(1)
    layerLoad(layerName.event, "")
    layerLoad(layerName.bg1, cGetFileName("bg", "bg_25_a_0"))
    switchScreen(0, "", 60)
    wait(60)
    vms(17960, "NONVOICE", "【≦小用户≧】「……豆包豆包，帮我看一下机器寄出去以后我有啥办法运行这个游戏」")
    vms(17961, "NONVOICE", "【≦小用户≧】「…………是叫模拟器来着？」")
    wait(60)
    comEffectFadeOut(300)
    if ceroFlag == true then
        run(cGetFileName("script", "snr_lib"))
        quit()
    end
    v0()
end
```

- [ ] **Step 6: `main()` 整体替换为**

```lua
main = function()
    local v15 = 0
    local v16
    while v15 == 0 do
        if doScriptScene == "end" then
            v15 = 1
        elseif doScriptScene == "fin-10" then
            -- 主菜单 encore 入口。第一次（旗标未置）直入现状的第一个故事；读过之后先选读哪一个。
            -- 只读 systemSave.finaleReadFlag（旧系统数据缺键取 nil → 走第一个故事，零迁移）。
            v16 = 1
            if systemSave.finaleReadFlag == true then
                v16 = finChooseStory()
            end
            if v16 == 2 then
                doScriptScene = "fin-60"
            else
                scene_fin_0(doScriptScene, "递笔")
                scene_fin_10(doScriptScene, "放学后的天台")
                doScriptScene = "fin-20"
            end
        elseif doScriptScene == "fin-20" then
            scene_fin_20(doScriptScene, "放学后的讲述者")
            doScriptScene = "fin-30"
        elseif doScriptScene == "fin-30" then
            scene_fin_30(doScriptScene, "七张卡")
            doScriptScene = "fin-35"
        elseif doScriptScene == "fin-35" then
            scene_fin_35(doScriptScene, "讲述者们")
            doScriptScene = "fin-40"
        elseif doScriptScene == "fin-40" then
            scene_fin_40(doScriptScene, "文化祭")
            doScriptScene = "fin-50"
        elseif doScriptScene == "fin-50" then
            scene_fin_50(doScriptScene, "第三个 End Roll")
            -- 首次完整读完谢幕章：置系统旗标并立刻写系统数据（e2f-complete 同款 autoSystemSave(0)），
            -- 主菜单 title-logo-zh 层据此把题名 logo 换成中文 title_01_c；旗标声明见 finale-read-flag 层。
            systemSave.finaleReadFlag = true
            autoSystemSave(0)
            doScriptScene = "end"
        elseif doScriptScene == "fin-60" then
            -- 第二个故事『远方的朋友』（docs/finale/draft-encore2-v0.md）；读完不置旗标、不写系统数据
            scene_fin_60(doScriptScene, "还笔")
            doScriptScene = "fin-70"
        elseif doScriptScene == "fin-70" then
            scene_fin_70(doScriptScene, "储藏间")
            doScriptScene = "fin-80"
        elseif doScriptScene == "fin-80" then
            scene_fin_80(doScriptScene, "全屏窗口")
            doScriptScene = "fin-90"
        elseif doScriptScene == "fin-90" then
            scene_fin_90(doScriptScene, "模拟器")
            doScriptScene = "end"
        end
        wait(5)
    end
    cInitGame()
    run(cGetFileName("script", "snr_mainmenu"))
    quit()
end
```

- [ ] **Step 7: 登记 id 与画廊变体**

`layers/vms_ids.toml` 谢幕 owner 那行改为：

```toml
vms      = [[17300, 17481], [17600, 17799], [17800, 17999]]   # 17300–17481 v2 冻结；17600–17799 v3（fin-35 转述 17600–17700、fin-40 新行 17720–17746、fin-50 新行 17760–17763）；17800–17999 第二个故事『远方的朋友』（fin-60 17800–17804、fin-70 17820–17855、fin-80 17856–17858 与 17880–17949、fin-90 17960–17961）
```

`layers/overlays/finale-gallery-cg.toml`：在 `why` 多行字符串收尾的 `"""` 之前追加下面这段文字，并在文件末尾追加一条 op：

```toml
[[ops]]
op   = "replace"
find = '{"eve_47_x"}, {"eve_48_x"}'
with = '{"eve_47_x", "eve_47_f", "eve_47_d", "eve_47_g"}, {"eve_48_x"}'
```

`why` 追加文字：`2026-09-25 第二个谢幕故事 fin-80 的三位少女 CG eve_47_f/_d/_g（母本 eve_47_x）同法登记为 eve_47 格的变体——四变体格与 eve_20/eve_46 同型；锚点 {"eve_47_x"}, {"eve_48_x"} 全库唯一。`

- [ ] **Step 8: 跑测试与过闸**

Run: `uv run pytest tests/test_layers_corpus.py -q` 然后 `uv run python tools/layers.py check --profile release` 然后 `uv run python tools/msg_layout_check.py --profile release --show 17831`
Expected: corpus 全部 passed（含既有 `test_finale_ids_are_inside_declared_range`、`test_finale_read_flag_every_use_is_nil_safe`、`test_every_release_overlay_hits_on_real_base`）；check 零错误零告警；`--show 17831` 的版面第二行以 `AI 助手账号` 起头（`_r` 生效）。

- [ ] **Step 9: 编译与存档容量**

Run: `uv run python tools/build_disc.py --profile release --stage lua,font,members` 然后 `uv run python tools/pluto_size.py estimate build/release/members/script/snr_finale.lua`
Expected: members 阶段编码 gim 时新成员 `event/eve_0_j`、`event/eve_0_k`、`select/sel_fin*`、`event/eve_47_*` 出现（无「无对应封包成员」/「已是原包成员」报错）；谢幕脚本占线程区 <35%（现 18.1%）。

- [ ] **Step 10: 提交**

```bash
git add layers/scripts/snr_finale.lua layers/vms_ids.toml layers/overlays/finale-gallery-cg.toml tests/test_layers_corpus.py
git commit -m "feat: 谢幕第二段『远方的朋友』——序章同款『声』选择画面入口（读过第一个故事后）、fin-60..90 四场景（vms 17800–17999）、画廊 eve_47 四变体；守门测试

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: 测试捷径 `--finale-read`（预置旗标进主菜单/直入场景）

**Files:**
- Modify: `tools/testboot.py`（两个模板、`_render_mode`、CLI）
- Modify: `tools/build_disc.py`（CLI 一项、`mode_opts` 一键）
- Modify: `tests/test_testboot.py`（追加两个测试）

**Interfaces:**
- Consumes: `generate(mode, out_dir, **opts)` → `_render_mode(mode, **opts)`
- Produces: `_render_mode(..., finale_read: bool = False)`；`build_disc.py --profile test --mode mainmenu --finale-read`（Task 6 用）

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_testboot.py` 末尾）

```python
def test_finale_read_preset_lands_before_menu_and_scene_entry(out_dir):
    """--finale-read：测试盘开机就把 systemSave.finaleReadFlag 置 true（布尔新键，不碰原有数字字段），
    主菜单 encore 会出『声』选择画面、题名 logo 为中文；直入场景同样带上。"""
    generate("mainmenu", out_dir, finale_read=True)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert "    systemSave.finaleReadFlag = true\n" in src
    assert src.index("systemSave.finaleReadFlag = true") < src.index('run(cGetFileName("script", "snr_mainmenu"))')
    generate("scene", out_dir, scene="fin-10", finale_read=True)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert src.index("systemSave.finaleReadFlag = true") < src.index('doScriptScene = "fin-10"')


def test_finale_read_preset_is_off_by_default(out_dir):
    for mode, opts in (("mainmenu", {}), ("scene", {"scene": "fin-10"})):
        generate(mode, out_dir, **opts)
        src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
        assert "finaleReadFlag" not in src
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_testboot.py -q -k finale_read`
Expected: FAILED（`TypeError: _render_mode() got an unexpected keyword argument 'finale_read'`）。

- [ ] **Step 3: 改 `tools/testboot.py`**

3a. `MAINMENU_TEMPLATE`：在 `    run(cGetFileName("script", "snr_mainmenu"))` 前一行插入 `{preset}`（注意模板现有 `⚠ 不要在这里动 systemSave` 注释说的是**数字字段**；本旗标是布尔新键，只被 `== true` 读，见 layers/overlays/finale-read-flag.toml）。即：

```lua
    -- 何况这两个字段跟「解锁」无关，本就不该设。设置项交给 option 画面自己去改。
{preset}    run(cGetFileName("script", "snr_mainmenu"))
```

3b. `SCENE_TEMPLATE`：在 `    doScriptScene = "{scene}"` 前一行插入 `{preset}`：

```lua
    cInitStoryRoute()
{preset}    doScriptScene = "{scene}"
```

3c. `_render_mode` 签名加 `finale_read: bool = False`，函数开头加

```python
    # --finale-read：预置「已读过谢幕第一个故事」（布尔新键，缺省 false；不碰 systemSave 原有数字字段）
    preset = "    systemSave.finaleReadFlag = true\n" if finale_read else ""
```

并把两处 `.format(...)` 补上 `preset=preset`：`MAINMENU_TEMPLATE.format(route=story_route(), hold=-1 if no_cards else 1, preset=preset)`、`SCENE_TEMPLATE.format(scene=scene, script=scene_to_script(scene), hold=-1 if no_cards else 1, preset=preset)`。

3d. `main()` 的 argparse 加 `ap.add_argument("--finale-read", action="store_true", help="mainmenu/scene 模式预置 systemSave.finaleReadFlag = true（谢幕『声』选择画面、中文题名）")`，并把 `generate(args.mode, args.out, scene=..., card=..., ...)` 调用补上 `finale_read=args.finale_read`。

- [ ] **Step 4: 改 `tools/build_disc.py`**

argparse 在 `--skippable` 之后加：

```python
    ap.add_argument("--finale-read", action="store_true",
                    help="test 剖面 mainmenu/scene 模式：预置 systemSave.finaleReadFlag = true（谢幕『声』选择画面）")
```

`mode_opts` 字典加一键 `"finale_read": args.finale_read`。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_testboot.py tests/test_build_disc.py -q`
Expected: 全部 passed。

- [ ] **Step 6: 提交**

```bash
git add tools/testboot.py tools/build_disc.py tests/test_testboot.py
git commit -m "feat: testboot/build_disc 加 --finale-read——测试盘预置 finaleReadFlag，主菜单直达谢幕『声』选择画面

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: 模拟器验证（直入场景连拍、选择画面三跑、BGM 回绕、存档往返）

**Files:**
- Create: `tools/emu/drives/finale_choice.py`
- 产物：`build/emu/drives/finale_scene/`、`build/emu/drives/finale_choice/`、`build/emu/drives/bgm_probe/`

**Interfaces:**
- Consumes: `tools/emu/drives/_common.py` 的 `TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game`；`cli.buttons_press(name, duration)`；Task 5 的 `--finale-read`
- Produces: 截图证据与 `report_errors` 计数，写进 Task 7 的落地记录

- [ ] **Step 1: 新建驾驶脚本 `tools/emu/drives/finale_choice.py`**

```python
#!/usr/bin/env -S uv run python
"""谢幕『声』选择画面驾驶：主菜单定位 encore → ○ → 截提示帧/按钮帧 → 按 FIN_PICK 选项 → 连按若干次截进场帧。

前置：FIN_PICK=1|2 时 `build_disc.py --profile test --mode mainmenu --finale-read`；
      FIN_PICK=0（期望**没有**选择画面、直入 fin-0 递笔）时 `build_disc.py --profile test --mode mainmenu`
      （不带 --finale-read，等价原版/旧 release 的系统数据）。缺省引导 test 盘。
环境变量：FIN_PICK（缺省 2）、FIN_AFTER（选完后连按次数，缺省 12）。
时序（○ 之后）：黑场 1 s → eve_0_g 淡入+停 2 s → 提示 eve_0_j 淡入 1 s、停 3.3 s → 脚注 eve_0_k 淡入+停 2 s → 按钮。
期望：FIN_PICK=1/2 → a_prompt.png 是「你的声音是——」提示、b_buttons.png 是两枚光晕按钮＋脚注、
      c_pick.png 亮态在所选项；after_NN.png 里 FIN_PICK=1 出现 fin-0「……卧槽，所以我们搞完了」、
      FIN_PICK=2 出现 fin-60「……啧啧，这写得可以啊」。FIN_PICK=0 → a/b 两帧是 fin-0 黑屏文字，不得出现按钮。
      ERROR 0 条（ILLEGAL_THID HLE 噪声除外）。
光标定位同 finale_full.py（亮态项深蓝核心像素占比）。
"""
import asyncio
import os
import sys

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "finale_choice", __doc__)
PICK = int(os.environ.get("FIN_PICK", "2"))
AFTER = int(os.environ.get("FIN_AFTER", "12"))

ORDER = ["story", "fragment", "section7", "finale", "library", "option"]
BANDS = {"story": (200, 105, 300, 132), "fragment": (185, 132, 300, 158),
         "section7": (185, 160, 300, 186), "finale": (190, 187, 300, 213),
         "library": (200, 214, 275, 239), "option": (205, 241, 275, 264)}


def cursor_index(img):
    px = img.convert("RGB")
    best, idx = -1.0, None
    for i, k in enumerate(ORDER):
        x0, y0, x1, y1 = BANDS[k]
        strong = core = 0
        for y in range(y0, min(y1, px.height), 2):
            for x in range(x0, x1, 2):
                r, g, b = px.getpixel((x, y))
                if b > 150 and b - r > 30:
                    strong += 1
                    if r < 100 and b > 210:
                        core += 1
        frac = core / strong if strong > 25 else 0.0
        if frac > best:
            best, idx = frac, i
    return idx, best


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 15)
        target = ORDER.index("finale")
        for step in range(10):
            img = await snap(cli, OUT / f"nav{step}.png")
            idx, frac = cursor_index(img)
            print(f"nav{step}: cursor={ORDER[idx] if idx is not None else '?'} frac={frac:.2f}", flush=True)
            if idx == target and frac > 0.2:
                break
            if idx is None:
                await asyncio.sleep(2.0)
                continue
            await cli.buttons_press("down" if idx < target else "up", duration=3)
            await asyncio.sleep(2.5)
        else:
            sys.exit("未能定位 finale 光标")
        await cli.buttons_press("circle", duration=3)
        await asyncio.sleep(5.5)                       # 提示「你的声音是——」在屏（4.0–7.3 s）
        await snap(cli, OUT / "a_prompt.png")
        await asyncio.sleep(6.0)                       # 脚注与按钮就位（≥ 9.5 s）
        await snap(cli, OUT / "b_buttons.png")
        if PICK == 2:
            await cli.buttons_press("down", duration=3)
            await asyncio.sleep(1.0)
        await snap(cli, OUT / "c_pick.png")
        if PICK:
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(3.0)
        for i in range(1, AFTER + 1):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.2)
            await snap(cli, OUT / f"after_{i:02d}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")


asyncio.run(run())
```

- [ ] **Step 2: 直入 fin-70 连拍**

Run:
```bash
uv run python tools/build_disc.py --profile test --mode scene --scene fin-70
FIN_PRESSES=70 uv run python tools/emu/drives/finale_scene.py
```
Expected（用 Read 工具翻 `build/emu/drives/finale_scene/p*.png`）：通学路（bg_20_a_0）→ 彩野房间（bg_25_a_0，墙上空调）→ 储物柜间（bg_18_a_0）→ 纸箱特写 cut_62 盖住画面 → 回房间 → 白场；最后几帧进入 fin-80：彩野伏案 CG 上叠「是那种画面非常大果粒…」。`report_errors` 0 条。

- [ ] **Step 3: 直入 fin-80 连拍与 BGM 回绕**

Run:
```bash
uv run python tools/build_disc.py --profile test --mode scene --scene fin-80
FIN_PRESSES=90 uv run python tools/emu/drives/finale_scene.py
BGM_REF=build/sound/work/bgm_fin_2.44k.wav BGM_PRESSES=0 BGM_SECONDS=230 uv run python tools/emu/drives/bgm_probe.py
```
Expected：帧序 eve_47_x（彩野）→ 寓言家（橙发向日葵）→ 大肥鱼（蓝发鲸尾）→ 牛来吹（黑发眼罩 Z）→ 彩野 → 淡出 → fin-90 房间两句 → 主菜单；无纸箱特写残留。bgm_probe：ncc ≥ 0.9，回绕间隔 ≈ 196.6 s，无 `E[Atrac]`。画廊四变体不在驾驶范围：靠 Task 4 的叠加层断言与 eve_20/eve_46 四变体格的既有代码路径（读过 fin-80 后画廊自会多三张待收集）。

- [ ] **Step 4: 选择画面三跑**

Run:
```bash
uv run python tools/build_disc.py --profile test --mode mainmenu --finale-read
FIN_PICK=2 uv run python tools/emu/drives/finale_choice.py --out build/emu/drives/finale_choice_pick2
FIN_PICK=1 uv run python tools/emu/drives/finale_choice.py --out build/emu/drives/finale_choice_pick1
uv run python tools/build_disc.py --profile test --mode mainmenu
FIN_PICK=0 uv run python tools/emu/drives/finale_choice.py --out build/emu/drives/finale_choice_pick0
```
Expected：pick2 的 `a_prompt.png` 见「你的声音是——」、`b_buttons.png` 见两枚按钮＋脚注、`c_pick.png` 第二项亮态、`after_*.png` 出现「……啧啧，这写得可以啊」；pick1 的 `c_pick.png` 第一项亮态、`after_*.png` 出现「……卧槽，所以我们搞完了」；pick0 的 a/b 两帧是黑屏上的 fin-0 文字、没有按钮。三跑 ERROR 0。

- [ ] **Step 5: 存档往返（fin-80 中途）**

Run:
```bash
uv run python tools/build_disc.py --profile test --mode scene --scene fin-80 --no-cards
uv run python tools/emu/drives/save_roundtrip.py --tag fin-80
```
Expected：`saved_ok` 与 `resumed_ok` 为 true（线程 blob 在容量内、读档后回到存档那句）。读档后画面/BGM 是否重现只记录不判定——原作各章同样不在读档后重载画面。

- [ ] **Step 6: 提交驾驶脚本**

```bash
git add tools/emu/drives/finale_choice.py
git commit -m "feat: 谢幕『声』选择画面驾驶 finale_choice——主菜单 encore → 提示/按钮帧 → 选项分支与老存档直入验证

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: 发布出盘与文档

**Files:**
- Modify: `CLAUDE.md`（谢幕章一节追加子条）
- Modify: `docs/ops/disc-pipeline.md`（id 段落一处）
- Modify: `docs/finale/draft-encore2-v0.md`（落地记录）
- 产物：`build/dist/game_zh.iso`、`build/dist/game_zh_ios.iso`

- [ ] **Step 1: 全量测试与过闸**

Run: `uv run pytest -q` 然后 `uv run python tools/layers.py check --profile release`
Expected: 全部 passed；check 零错误零告警。

- [ ] **Step 2: 出盘与开机链冒烟**

Run: `uv run python tools/build_disc.py` 然后 `uv run python tools/emu/drives/release_iso.py`
Expected：release 各道断言全过，`build/dist/game_zh.iso` 与 `game_zh_ios.iso` 同出（iOS 盘需要 `assets/fw/{libmp4,mp4msv}.dec.prx`，缺了会在开跑前失败——按 `docs/ops/movie-playback-ppsspp-2026-09-24.md` 补）；release_iso 三帧是原版开机链与初始形态标题，ERROR 0 或 1 条 ILLEGAL_THID。

- [ ] **Step 3: 文档**

3a. `CLAUDE.md` 谢幕章那一条（`- 谢幕章（encore，2026-09-02 本地化新增·编外）`）的末尾「取代为现行命令面，历史记录仍有效）。」之后追加一个同缩进的子段落：

```
    **第二个故事『远方的朋友』（2026-09-25，用户执笔）**：fin-60..90（还笔／储藏间／全屏窗口／模拟器）。
    读过第一个故事（`finaleReadFlag`）之后再点 encore，先出序章 s0f 同款『声』选择画面（`finChooseStory`：
    新成员 `event/eve_0_j` 提示「你的声音是——」、`eve_0_k` 脚注、`select/sel_fin1/2_sel_a_{on,off}` 光晕按钮，
    `tools/bake_finale_voice.py`），选二进第二个故事；旧系统数据缺键直入 fin-0。三位 AI 少女 CG
    `event/eve_47_{f,d,g}`（母本 eve_47_x＝彩野伏案改写『物語』；源 `docs/finale/assets/eve_47_*.src.png`，
    `bake_finale_event.py` 清单化），fin-80 依次同层溶解接替彩野的座位，画廊 eve_47 格四变体；纸箱特写复用
    `cutin/cut_62`（s5f_80 语法）；BGM `bgm/bgm_fin_2`（用户第二支 bgm_5_x remix，整曲循环不裁尾，−21 LUFS）；
    vms 17800–17999；读完不置旗标、不写系统数据。测试捷径 `build_disc.py --profile test --mode mainmenu --finale-read`，
    驾驶 `tools/emu/drives/finale_choice.py`。文稿与决定记录 `docs/finale/draft-encore2-v0.md`。
```

3b. `docs/ops/disc-pipeline.md` 第 163 行附近「谢幕章 17300–17481」改为「谢幕章 17300–17481、17600–17799、17800–17999」。

3c. `docs/finale/draft-encore2-v0.md` 首段引用块末尾追加一行（日期填实施当天）：

```
> **<YYYY-MM-DD> 已落地**：脚本 `layers/scripts/snr_finale.lua` 按本稿实施（finChooseStory + fin-60..90），六张选择画面图、
> 三张少女 CG、`bgm_fin_2` 进包；模拟器 `finale_scene.py`（fin-70/fin-80）、`finale_choice.py`（三跑）、`bgm_probe.py`
> 回绕、`save_roundtrip.py`（fin-80）全部通过；release 出盘断言全过。实施计划 `docs/superpowers/plans/2026-09-25-encore-second-story.md`。
```

- [ ] **Step 4: 提交**

```bash
git add CLAUDE.md docs/ops/disc-pipeline.md docs/finale/draft-encore2-v0.md
git commit -m "docs: 谢幕第二段『远方的朋友』落地——CLAUDE.md 增补、id 段落、工作稿落地记录

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
