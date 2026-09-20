#!/usr/bin/env -S uv run python
"""文库入口一次性中文说明（layers/overlays/novel-notice-entry.toml）。

前置：`build_disc.py --profile test --mode mainmenu`（全卡 → 5 本小说齐全，不走空列表早退）。
期望：02 帧进 novel 后先出【■汉化说明】第一条；03 帧第二条；04 帧进入小说浏览画面；
退回主菜单（autoSystemSave 写下 novelNoticeSeen）再进一次：07 帧直接是浏览画面，不再提示；ERROR 0 条。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "novel_notice", __doc__)


async def to_novel(cli, prefix: str):
    for _ in range(4):                       # story → fragment → section7 → library（12 项形态）
        await cli.buttons_press("down", duration=3)
        await asyncio.sleep(1.2)
    await cli.buttons_press("circle", duration=3)   # 展开 library，光标落 novel
    await asyncio.sleep(2.5)
    await snap(cli, OUT / f"{prefix}0_library_expanded.png")
    await cli.buttons_press("circle", duration=3)   # 进 snr_novel
    await asyncio.sleep(4.0)
    await snap(cli, OUT / f"{prefix}1_after_enter.png")


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 15)
        await snap(cli, OUT / "00_menu.png")
        await to_novel(cli, "0")
        await cli.buttons_press("circle", duration=3)   # 翻到第二条
        await asyncio.sleep(2.0)
        await snap(cli, OUT / "02_notice_2.png")
        await cli.buttons_press("circle", duration=3)   # 关掉消息 → 加载 → 浏览画面
        await asyncio.sleep(6.0)
        await snap(cli, OUT / "03_viewer.png")
        # 退回主菜单（snr_novel 退出前 autoSystemSave(0)），再进一次
        for _ in range(3):
            await cli.buttons_press("cross", duration=3)
            await asyncio.sleep(2.5)
        await asyncio.sleep(6.0)
        await snap(cli, OUT / "04_back_to_menu.png")
        await to_novel(cli, "1")
        await asyncio.sleep(4.0)
        await snap(cli, OUT / "12_second_visit.png")
        report_errors(cli)


asyncio.run(run())
