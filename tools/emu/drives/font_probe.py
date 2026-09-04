#!/usr/bin/env -S uv run python
"""字体/ruby/禁则探针逐页截图：test 盘 `--mode font` 的每一页（含 `_n` 分页）按 CIRCLE 推进。

前置：`build_disc.py --profile test --mode font`。缺省引导 test 盘。
期望（2026-09-04 EBOOT 补丁）：K1 帧「，」悬挂在第 26 格、「（」提前换行；K2 帧「……」」
三格悬挂可见；K3 帧「：」「——」悬挂、「≦」提前换行；R1 帧「kuāng」首字母不被左缘裁、
「故事」居中于「Ｓｔｏｒｙ」、「jì yì」中间有词距；ERROR 0 条（HLE 常态噪声除外）。
"""
import asyncio

from _common import TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "font_probe", __doc__)
PAGES = 40          # msg 页数 + `_n` 分页数的上限，多出的按键落在 quit 后无害


async def run():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 12)
        await snap(cli, OUT / "p00.png")          # fontPrint 逐槽样本屏（wait(hold) 中）
        for i in range(1, PAGES + 1):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.6)
            await snap(cli, OUT / f"p{i:02d}.png")
        report_errors(cli)
    print(f"截图 -> {OUT}")


asyncio.run(run())
