#!/usr/bin/env -S uv run python
"""探索地图底栏：五处 comSelectMap 逐页截图，验 `select/sel_map_0_a` 的中文提示。

前置：`build_disc.py --profile test --mode map`（testboot 把全库 5 处 comSelectMap 串起来，
每页按 CIRCLE 进下一处）。缺省引导 test 盘。
期望：00–05 帧底栏左上「请选择要前往的地点。」红晕白字、其下英文 `- MAP SELECT -` 原样、
右侧「当前位置」+ 地点条；01 帧是 00 帧按一次 DOWN 后的光标态（底栏不随光标变）；ERROR 0 条。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "map", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        await snap(cli, OUT / "00_map1.png")
        await cli.buttons_press("down", duration=3)
        await asyncio.sleep(1.2)
        await snap(cli, OUT / "01_map1_down.png")
        for i in range(2, 6):
            # comSelectMap 要先看到一帧「未按」再认按下（l1_18 释放判据），换页又有
            # 淡出 30 帧 + wait 30 + switchScreen 60：按 6 帧、等 4.5 秒，3 帧/3 秒时
            # 第 3 页之后的按键会丢（2026-09-06 实测 03–05 帧相同）。
            await cli.buttons_press("circle", duration=6)
            await asyncio.sleep(4.5)
            await snap(cli, OUT / f"{i:02d}_map{i}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")


asyncio.run(run())
