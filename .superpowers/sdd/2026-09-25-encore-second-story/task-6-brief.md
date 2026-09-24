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

