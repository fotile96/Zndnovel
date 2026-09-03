#!/usr/bin/env -S uv run python
"""无卡 144 档回归：主菜单应仍是原版 11 项形态，第 4 项是 library 而非 encore。

前置：一张**不持卡 144** 的全菜单盘——`build_disc.py --profile test --mode mainmenu`
生成的 snr_test.lua 把 195 卡全置 1；在 `build/test/lua/final/snr_test.lua`（members
阶段的编译输入；generated/ 只是 lua 阶段的中间产物）的全卡循环后补一行
`gameSave.myCard[144].hold = -1`，再跑 `--profile test --stage members,stage,pack,disc`
（跳过 lua 阶段，否则会被重新生成覆盖）。
期望：00 帧 11 项；下 4 次后光标在 option（第 5 项）；CIRCLE 进 option 画面而不是谢幕。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "no_card144", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        await snap(cli, OUT / "00_menu11.png")
        for _ in range(3):
            await cli.buttons_press("down", duration=3)
            await asyncio.sleep(1.0)
        await snap(cli, OUT / "01_cursor_after_3down.png")
        await cli.buttons_press("down", duration=3)
        await asyncio.sleep(1.0)
        await snap(cli, OUT / "02_cursor_after_4down.png")
        await cli.buttons_press("circle", duration=3)
        await asyncio.sleep(2.0)
        await snap(cli, OUT / "03_after_circle.png")
        report_errors(cli)


asyncio.run(run())
