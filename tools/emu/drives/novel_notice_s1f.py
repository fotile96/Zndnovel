#!/usr/bin/env -S uv run python
"""章节 1 读完（scene_s1f_complete）：原作九条【■通知】之后紧接八条【■汉化说明】
（layers/overlays/novel-notice-s1f.toml）。

前置：`build_disc.py --profile test --mode scene --scene s1f-complete`（全卡；直入该场景）。
期望：授卡 133 → 17002 → cutin → 17003–17011 → 17500–17507 → 淡出；每按一次 CIRCLE 截一帧，
最后十来帧应依次是原通知尾段与八条汉化说明；ERROR 只有基线的 ILLEGAL_THID 一条。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "novel_notice_s1f", __doc__)
PRESSES = 40


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 22)                 # 音乐 + cutin 淡入 + 240 帧等待 + 卡面弹出
        await snap(cli, OUT / "00_card_show.png")
        for i in range(1, PRESSES + 1):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.6)
            await snap(cli, OUT / f"{i:02d}.png")
        report_errors(cli)


asyncio.run(run())
