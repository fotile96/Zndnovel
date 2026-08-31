"""游戏本体 L0 冒烟（SNDL_GAME_DIR=解包目录 时启用）。

首轮实测教训（docs/ops 补记）：
  - app 传参引导极快（~0.6s），game.start 广播常在 WS 客户端连上之前就发出，
    等广播必竞态——改为轮询 game.status 直到 game 非空；
  - 运行态下 gpu.buffer.screenshot 会拒绝（Neither CPU or GPU is stepping），
    须 break_cpu() 后取图再 resume；
  - 游戏在 HLE 下有常态 ERROR 噪声（如 sceKernelWaitThreadEnd ILLEGAL_THID），
    ERROR 日志只记录供人审，不做硬断言——待样本积累后再收紧白名单。
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


async def wait_game_running(cli, timeout: float = 90.0) -> dict:
    """轮询 game.status 直到 game 非空（免疫 game.start 广播的连接时序竞态）。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        status = await cli.game_status()
        if status.get("game"):
            return status
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(f"游戏未进入运行态: {status}")
        await asyncio.sleep(1.0)


def test_boot_extracted_dir_to_first_frame():
    async def run():
        async with session(lambda: Emulator.app(GAME_DIR)) as (emu, cli):
            status = await wait_game_running(cli)
            print(f"game: {status['game']}")
            # gpu.buffer.* 回读本机不可用（见 client.screenshot 注记）——走 VRAM 直读。
            # 逐段等引导演出画出内容（IPL 品牌屏约在 10s 上下）。
            img = None
            for wait_s in (8, 4, 4, 8, 8):
                await asyncio.sleep(wait_s)
                await cli.break_cpu()
                img = await cli.vram_screenshot()
                await cli.resume()
                if any(lo != hi for lo, hi in img.getextrema()):
                    break
            assert img is not None
            assert any(lo != hi for lo, hi in img.getextrema()), "帧缓冲始终单色"
            assert img.size == (480, 272)
            out = REPO / "build" / "emu" / "game_first_frame.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out)
            print(f"first frame -> {out}  extrema={img.getextrema()}")
            errors = [d["message"] for d in cli.drain_broadcasts("log") if d.get("level") == 2]
            print(f"ERROR 日志 {len(errors)} 条（仅记录）: {errors[:5]}")
    asyncio.run(run())
