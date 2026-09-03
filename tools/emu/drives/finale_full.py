#!/usr/bin/env -S uv run python
"""谢幕全章：主菜单定位 encore → 连按 CIRCLE 350 次跑完 fin-10..50 → 回主菜单。

光标定位靠颜色：亮态项深蓝核心像素（r<100 ∧ b>210）占墨迹比 ≈0.35，暗态 ≈0.1
（2026-09-02 对 nav 截图实测校准）。逐步导航、每步复核，可上可下。
前置同 menu.py。期望：每 10 句一帧 p010..p350，末尾 end0..2 回到主菜单；ERROR 0 条。
"""
import asyncio
import sys

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "finale_full", __doc__)

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
            print(f"nav{step}: cursor={ORDER[idx] if idx is not None else '?'} frac={frac:.2f}",
                  flush=True)
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
        await asyncio.sleep(5.0)
        for i in range(1, 351):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.2)
            if i % 10 == 0:
                await snap(cli, OUT / f"p{i:03d}.png")
        for j in range(3):
            await asyncio.sleep(5.0)
            await snap(cli, OUT / f"end{j}.png")
        report_errors(cli)


asyncio.run(run())
