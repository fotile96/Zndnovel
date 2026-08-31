"""像素通路活体验证，两条：

1. GE 帧转储（官方 frametest CI 素材）经 headless `--screenshot-save` 渲染出图，
   跑两遍逐像素一致——软渲染确定性 + 截图落盘 + imgdiff 全链路。这正是未来
   L2 视觉回归（golden diff）的机制原型。
2. WS `gpu.buffer.screenshot` 的请求/错误语义：开局断住（无帧缓冲）时要么给出
   可解码 PNG、要么返回结构化 error——验证命令通路。真实取像用例在
   test_game_boot.py（等游戏）。

注：pspautotests 的 gpu 替身（如 guardband）fast-forward 下瞬间跑完就退，
无法充当"持续绘制的活目标"，故像素验证走 ppdmp 而非 PRX（首轮实测教训）。
"""
import asyncio
import io
import subprocess

import pytest
from PIL import Image

from tests.emu.conftest import requires_stack
from tools.emu.client import EmuError
from tools.emu.imgdiff import mse
from tools.emu.launcher import HEADLESS_EXE, REPO, TESTDATA, Emulator, session

pytestmark = [pytest.mark.emu, requires_stack]

FRAME_DUMP = TESTDATA / "frame.ppdmp"


@pytest.mark.skipif(not FRAME_DUMP.exists(), reason="缺 frame.ppdmp（重跑 fetch_testdata.sh）")
def test_ppdmp_render_is_deterministic(tmp_path):
    outs = []
    for i in (1, 2):
        out = tmp_path / f"shot{i}.png"
        subprocess.run(
            [str(HEADLESS_EXE), str(FRAME_DUMP), "--graphics=software",
             f"--screenshot-save={out}", "--timeout=60"],
            check=True, capture_output=True, timeout=120)
        img = Image.open(out).convert("RGB")
        assert img.size[1] == 272
        assert any(lo != hi for lo, hi in img.getextrema()), "渲染结果是单色"
        outs.append(out)
    assert mse(outs[0], outs[1]) == 0.0, "软渲染两遍像素不一致"
    # 留一份供人眼确认
    keep = REPO / "build" / "emu" / "ppdmp_smoke.png"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_bytes(outs[0].read_bytes())


def test_ws_screenshot_semantics():
    async def run():
        async with session(lambda: Emulator.headless(TESTDATA / "cpu_alu.prx")) as (emu, cli):
            # 开局断住：stepping 满足，但尚无游戏帧缓冲。两种合法结果：
            # 结构化 error（常见）或可解码 PNG（若引擎给出了缓冲内容）。
            try:
                png, w, h = await cli.screenshot()
            except EmuError as e:
                assert str(e)  # 结构化错误而非断连/超时
            else:
                img = Image.open(io.BytesIO(png))
                assert (w, h) == img.size
            await cli.resume()
            rc = await asyncio.to_thread(emu.wait_exit, 60)
            assert rc == 0
    asyncio.run(run())
