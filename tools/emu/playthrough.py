#!/usr/bin/env -S uv run python
"""按固定操作脚本推进游戏并逐帧存图——中日 A/B 与视觉回归的取样器。

同一份操作脚本对两张盘（原版 / 中文化）各跑一次，产出可逐帧对照的两组截图。
时序靠「按键帧数 + 固定等待」而非画面识别，故两次运行的分歧只来自盘内容本身
（软渲染 + 无随机源，实测可复现）。

用法:
  uv run python tools/emu/playthrough.py --disc build/release/game --out build/emu/release
  uv run python tools/emu/playthrough.py --disc build/test/game --out build/emu/test
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from tools.emu.launcher import Emulator, session  # noqa: E402

# (按键, 按住帧数, 按后等待秒) —— None 表示纯等待不按键
SCRIPT = [
    (None, 0, 22.0),        # IPL 标志 + 引擎初始化 + 免责声明
    ("cross", 4, 2.5),      # 跳过免责
    ("cross", 4, 2.5),      # 跳过自动存档告知
    ("cross", 4, 3.0),      # 到标题
    ("circle", 4, 7.0),     # 进 Prologue
] + [("circle", 3, 2.6) for _ in range(24)]   # 连续推进序章对白


async def run(disc: Path, out: Path, tag: str) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    async with session(lambda: Emulator.app(disc, graphics="software",
                                            extra=("-l",))) as (emu, cli):
        for _ in range(60):
            if (await cli.game_status()).get("game"):
                break
            await asyncio.sleep(1)
        else:
            sys.exit("游戏未进入运行态")
        for i, (btn, frames, wait) in enumerate(SCRIPT):
            if btn:
                await cli.buttons_press(btn, duration=frames)
            await asyncio.sleep(wait)
            await cli.break_cpu()
            img = await cli.vram_screenshot()
            await cli.resume()
            img.save(out / f"{i:03d}.png")
        errs = [d["message"] for d in cli.drain_broadcasts("log") if d.get("level") == 2]
        print(f"[{tag}] {len(SCRIPT)} 帧 -> {out}；ERROR 日志 {len(errs)} 条")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disc", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="play")
    args = ap.parse_args()
    asyncio.run(run(Path(args.disc).resolve(), Path(args.out), args.tag))


if __name__ == "__main__":
    main()
