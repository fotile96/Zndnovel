"""游戏本体冒烟骨架（等 ISO：设 SNDL_GAME_DIR=解包目录后自动启用）。

到位后这里就是 M0 剩余项的机器化入口：引导解包目录 → game.start →
稳定后截图存档 → 日志无 ERROR。后续 L1（msg-oracle vms ID 流）在此基础上加。
"""
import asyncio

import pytest

from tests.emu.conftest import GAME_DIR, requires_game
from tools.emu.launcher import APP_EXE, REPO, Emulator, session

pytestmark = [
    pytest.mark.emu,
    requires_game,
    pytest.mark.skipif(not APP_EXE.exists(), reason="缺 PPSSPP app 构建"),
]


def test_boot_extracted_dir_to_first_frame():
    async def run():
        async with session(lambda: Emulator.app(GAME_DIR)) as (emu, cli):
            await cli.wait_broadcast("game.start", timeout=90)
            status = await cli.game_status()
            assert status["game"], f"game.start 后 game.status 仍为空: {status}"
            await asyncio.sleep(5)  # IPL 标志/引导演出推进几秒再取帧
            png, w, h = await cli.screenshot()
            assert h == 272
            out = REPO / "build" / "emu" / "game_first_frame.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(png)
            errors = [d for d in cli.drain_broadcasts("log") if d.get("level") == 2]
            assert not errors, f"引导期出现 ERROR 日志: {errors[:3]}"
    asyncio.run(run())
