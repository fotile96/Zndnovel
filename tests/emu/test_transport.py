"""传输层活体验证：起 headless + 替身 PRX，握手、状态、放行跑完、日志捕获。

对应未来 L0 冒烟的地基：能起、能连、能放行、能收全程输出。
"""
import asyncio

import pytest

from tests.emu.conftest import requires_stack
from tools.emu.launcher import TESTDATA, Emulator, session

pytestmark = [pytest.mark.emu, requires_stack]


def test_handshake_status_and_full_run():
    async def run():
        async with session(lambda: Emulator.headless(TESTDATA / "cpu_alu.prx")) as (emu, cli):
            # version 握手：确认附着对象是我们拉起的那个进程
            assert cli.server_info["name"] == "PPSSPP"
            assert cli.server_info["pid"] == emu.proc.pid
            # --debugger 下 headless 开局断住（stepping），pc 停在 ELF 入口
            st = await cli.cpu_status()
            assert st["stepping"] is True
            assert st["pc"] != 0
            await cli.game_status()  # 能应答即可（headless 下 game 字段形状不作强断言）
            await cli.resume()
            rc = await asyncio.to_thread(emu.wait_exit, 60)
            assert rc == 0
        assert "test_ins:" in emu.log_text()  # 替身测试的模拟输出确实进了日志
    asyncio.run(run())
