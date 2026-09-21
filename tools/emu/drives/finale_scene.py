#!/usr/bin/env -S uv run python
"""谢幕章直入场景逐句截图：连按 CIRCLE，每 FIN_EVERY 次按键截一帧，共 FIN_PRESSES 次。

前置：`build_disc.py --profile test --mode scene --scene fin-30`（或 fin-35/40/50）。缺省引导 test 盘。
环境变量：FIN_PRESSES（缺省 320）、FIN_EVERY（缺省 1）、FIN_SLEEP（每次按键后等待秒数，缺省 2.2）。
期望：帧序里能看到 fin-30 七张卡与空白卡、fin-35 右侧 mini 位的七张卡、fin-40 溶解到鲸客人 CG、
fin-50 尾巴对话；ERROR 0 条（ILLEGAL_THID HLE 噪声除外）。
"""
import asyncio
import os

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "finale_scene", __doc__)
PRESSES = int(os.environ.get("FIN_PRESSES", "320"))
EVERY = int(os.environ.get("FIN_EVERY", "1"))
SLEEP = float(os.environ.get("FIN_SLEEP", "2.2"))


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        await snap(cli, OUT / "p000.png")
        for i in range(1, PRESSES + 1):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(SLEEP)
            if i % EVERY == 0:
                await snap(cli, OUT / f"p{i:03d}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")


asyncio.run(run())
