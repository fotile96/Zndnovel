"""输入注入活体验证：开局断住时预置 cross 按下 → 放行 → 替身程序
（ctrl/sampling，逐行打印 sceCtrl 按键位掩码 %08x）的输出里出现 CROSS 位
0x00004000——证明注入穿透到了游戏侧输入 API，且"断住时预置"可消除时序竞态。
"""
import asyncio

import pytest

from tests.emu.conftest import requires_stack
from tools.emu.launcher import TESTDATA, Emulator, session

pytestmark = [pytest.mark.emu, requires_stack]


def test_button_state_reaches_scectrl():
    async def run():
        async with session(lambda: Emulator.headless(TESTDATA / "sampling.prx")) as (emu, cli):
            # 开局断住时预置按下（消除时序竞态）；广播由逐帧轮询产生，
            # 所以要先放行再等回声——断住时不推帧、不发 input.* 广播。
            await cli.buttons_send({"cross": True})
            mark = cli.seq_mark()
            await cli.resume()
            echo = await cli.wait_broadcast("input.buttons", after_seq=mark, timeout=15)
            assert echo["buttons"]["cross"] is True
            rc = await asyncio.to_thread(emu.wait_exit, 90)
            assert rc == 0
        assert "00004000" in emu.log_text()  # CTRL_CROSS 位掩码出现在采样输出中
    asyncio.run(run())
