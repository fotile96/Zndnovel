#!/usr/bin/env -S uv run python
"""发布 ISO 原版开机链：完整 IPL 四屏 → 免责/自动存档告知 → 初始形态标题菜单。

引导 build/dist/game_zh.iso 本体（不是目录盘），无任何测试引导。
期望：00 帧在 IPL/告知屏；02 帧标题菜单为初始三项（Prologue / load / option）
——即 startMenuState=0，flag 未被预开；ERROR 日志与原盘同源（0 或 1 条 HLE 噪声）。
"""
import asyncio

from _common import RELEASE_ISO, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(RELEASE_ISO, "release_iso", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 35)
        await snap(cli, OUT / "00_ipl.png")
        for _ in range(3):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(4.0)
        await snap(cli, OUT / "01.png")
        await asyncio.sleep(10)
        await snap(cli, OUT / "02_menu.png")
        report_errors(cli)


asyncio.run(run())
