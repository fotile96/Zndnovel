#!/usr/bin/env -S uv run python
"""plot 缩略图在游戏里的观感：无卡主菜单 → Story / Fragment 两条时间轴逐页截图（缩略图来自 plot_{1..4}_a）。

前置：`build_disc.py --profile test --mode mainmenu --no-cards`。缺省引导 test 盘。
⚠ 必须 `--no-cards`：全卡持有时 Story 一进就是「要跳过吗」对话框、Fragment 提示「没有可以制作
梗概的故事」，两条时间轴都看不到（2026-09-07 实测）。testboot 用 data/dag.json 预置了记忆路线。
期望：s00 主菜单；s01 Story 时间轴首页（若干格缩略图 + 场景名条）；s02–s07 按 RIGHT 逐格右移；
f01–f07 Fragment 同理；ERROR 0 条。看点：缩略图中文标题是否清晰、底板与相邻格观感是否一致、有无残留原文。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "plot_timeline", __doc__)


async def timeline(tag: str, downs: int):
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        if tag == "s":
            await snap(cli, OUT / "s00_menu.png")
        for _ in range(downs):
            await cli.buttons_press("down", duration=6)
            await asyncio.sleep(1.2)
        await cli.buttons_press("circle", duration=6)
        await asyncio.sleep(6)
        await snap(cli, OUT / f"{tag}01_timeline.png")
        for i in range(2, 8):
            await cli.buttons_press("right", duration=6)
            await asyncio.sleep(1.5)
            await snap(cli, OUT / f"{tag}{i:02d}_timeline_r{i-1}.png")
        report_errors(cli)


async def run():
    await timeline("s", 0)     # Story
    await timeline("f", 1)     # Fragment
    print(f"截图 -> {OUT}")


asyncio.run(run())
