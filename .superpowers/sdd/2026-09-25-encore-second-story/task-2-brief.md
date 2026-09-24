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

