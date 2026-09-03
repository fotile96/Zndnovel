#!/usr/bin/env -S uv run python
"""字形/场景直入：直入某场景逐句推进截图。缺省对 fin-10 验 17305「啥」/17311「奖颁」。

前置：`build_disc.py --profile test --mode scene --scene fin-10`。缺省引导 test 盘。
期望：p05 帧含「啥」、p11 帧含「颁 … 奖」无空白方块；IPL 已剥（14 秒内进场景）；ERROR 0 条。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "glyph", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        await snap(cli, OUT / "p00.png")
        for i in range(1, 16):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.2)
            await snap(cli, OUT / f"p{i:02d}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")


asyncio.run(run())
