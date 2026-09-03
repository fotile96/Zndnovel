#!/usr/bin/env -S uv run python
"""全解锁主菜单：12 项版面 + encore 亮暗态 + CIRCLE 进谢幕章。

前置：`build_disc.py --profile test --mode mainmenu`（全 195 卡 + startMenuState=2），
或任何持卡 144 的存档。缺省引导 test 盘。
期望：00 帧 12 项菜单（含 encore 暗态）；01–03 帧光标依次到 fragment/section7/finale，
03 帧 encore 亮态；04 帧已进 fin-10；05–08 帧对白推进；ERROR 0 条。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "menu", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        await snap(cli, OUT / "00_menu_story.png")
        for i, tag in ((1, "fragment"), (2, "section7"), (3, "finale")):
            await cli.buttons_press("down", duration=3)
            await asyncio.sleep(1.2)
            await snap(cli, OUT / f"{i:02d}_menu_{tag}.png")
        await cli.buttons_press("circle", duration=3)
        await asyncio.sleep(6)
        await snap(cli, OUT / "04_entered.png")
        for i in range(5, 9):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.0)
            await snap(cli, OUT / f"{i:02d}_text.png")
        report_errors(cli)


asyncio.run(run())
