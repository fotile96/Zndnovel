"""日志断点调用跟踪活体验证——未来 msg-oracle（vms ID 流）的同款机制。

流程：开局断在入口 → 反汇编取入口后第 4 条指令地址 → 挂 log-only 断点
（enabled=False 不停机 + logFormat 表达式）→ 放行 → 断言 cpu.breakpoint.hit
广播与 log 广播都到达、且程序不受影响跑完。
"""
import asyncio

import pytest

from tests.emu.conftest import requires_stack
from tools.emu.launcher import TESTDATA, Emulator, session

pytestmark = [pytest.mark.emu, requires_stack]


def test_log_only_breakpoint_traces_without_stopping():
    async def run():
        async with session(lambda: Emulator.headless(TESTDATA / "cpu_alu.prx")) as (emu, cli):
            pc = (await cli.cpu_status())["pc"]
            lines = await cli.disasm(pc, 8)
            target = lines[3]["address"]
            assert target > pc
            await cli.bp_add(target, enabled=False, log=True, log_format="ZNDPROBE pc={pc}")
            await cli.resume()

            hit = await cli.wait_broadcast("cpu.breakpoint.hit", timeout=20)
            assert hit["hit"]["address"] == target
            assert hit["hit"]["logged"] is True
            assert hit["hit"]["paused"] is False  # log-only：CPU 未被停下

            logline = await cli.wait_broadcast(
                "log", predicate=lambda d: "ZNDPROBE" in d.get("message", ""), timeout=20)
            assert "ZNDPROBE" in logline["message"]

            rc = await asyncio.to_thread(emu.wait_exit, 60)
            assert rc == 0  # 跟踪不影响程序完整跑完
    asyncio.run(run())
