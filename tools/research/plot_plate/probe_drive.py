#!/usr/bin/env -S uv run python
"""研究用：直入 s1s_38，按时间序列截图，看引擎合成的画面与缩略图的差异。"""
import asyncio, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "emu", "drives"))
from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "plot_probe", __doc__)

async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 1.5)
        for i, dt in enumerate((0, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0)):
            await asyncio.sleep(dt if i else 0)
            await snap(cli, OUT / f"t{i:02d}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")

asyncio.run(run())
