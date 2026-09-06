#!/usr/bin/env -S uv run python
"""研究用：直入某场景，逐句 CIRCLE 推进并截图（找缩略图对应的剧情时刻）。"""
import asyncio, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "emu", "drives"))
from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "plot_walk", __doc__)
N = 45

async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 6)
        await snap(cli, OUT / "m00.png")
        for i in range(1, N + 1):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(1.3)
            await snap(cli, OUT / f"m{i:02d}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")

asyncio.run(run())
