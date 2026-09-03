#!/usr/bin/env -S uv run python
"""library 子列展开/收合：12 项形态下 novel/scene/cg/music 四项齐全。

验证的是 snr_mainmenu 里 `for l1_7 = 1, 11` → `#layerKeyCur` 那处修正：
若仍硬编码 11，12 项形态下最后一项不会被淡出/淡入。
前置同 menu.py（全解锁 test 盘）。期望：00 光标在 library；01 四子项展开；02 收合。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "library", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 15)
        for _ in range(4):
            await cli.buttons_press("down", duration=3)
            await asyncio.sleep(3.0)
        await snap(cli, OUT / "00_cursor_library.png")
        await cli.buttons_press("circle", duration=3)
        await asyncio.sleep(3.0)
        await snap(cli, OUT / "01_expanded.png")
        await cli.buttons_press("cross", duration=3)
        await asyncio.sleep(3.0)
        await snap(cli, OUT / "02_collapsed.png")
        report_errors(cli)


asyncio.run(run())
