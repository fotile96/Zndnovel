#!/usr/bin/env -S uv run python
"""发布 ISO 原版开机链：完整开场五卡（厂牌两屏 → 免责/版权 → 汉化组献词 IPL03 → 自动存档告知）→ 初始形态标题菜单。

引导 build/dist/game_zh.iso 本体（不是目录盘），无任何测试引导，**全程不按键**。
实测时间轴（2026-09-21，五卡，PPSSPP 软渲染）：自动存档卡到约 30 s，Now Loading 31–32 s，白闪 33 s，
标题从 35 s 起菜单三项常驻（每约 10 s 有一帧白闪把菜单项盖住）。00 帧取 45 s（留 10 s 余量），
01/02 各再隔 5 s——三帧里至少两帧应是 Prologue / load / option 三项（startMenuState=0，flag 未被预开）；
ERROR 日志与原盘同源（0 或 1 条 ILLEGAL_THID=sceKernelWaitThreadEnd HLE 噪声）。
⚠ 不要在这里按 CIRCLE：菜单已就位时它会选中 Prologue 直接开始序章。2026-09-21 之前的版本按三次
CIRCLE 是老四卡时序下用来跳过开场的，加第五卡、静置改 45 s 后变成误触（01/02 帧成了序章旁白）。
开场五卡的顺序与新卡本身由 boot_dedication.py 逐帧验。
"""
import asyncio

from _common import RELEASE_ISO, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(RELEASE_ISO, "release_iso", __doc__)


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 45)
        await snap(cli, OUT / "00_title.png")
        await asyncio.sleep(5.0)
        await snap(cli, OUT / "01_title.png")
        await asyncio.sleep(5.0)
        await snap(cli, OUT / "02_title.png")
        report_errors(cli)


asyncio.run(run())
