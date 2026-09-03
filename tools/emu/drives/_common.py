"""驾驶脚本共用底座：参数、引导等待、截图、ERROR 日志汇总。

每个驾驶脚本只写「按什么键、等多久、截哪几帧」，盘目录与输出目录由这里统一解析：
  --disc  引导对象（目录盘或 ISO），缺省由各脚本给（release 盘 / test 盘 / 发布 ISO）
  --out   截图目录，缺省 build/emu/drives/<脚本名>/，每次先清空
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.emu.launcher import Emulator, session  # noqa: E402,F401

RELEASE_GAME = REPO / "build" / "release" / "game"
TEST_GAME = REPO / "build" / "test" / "game"
RELEASE_ISO = REPO / "build" / "dist" / "game_zh.iso"


def parse(default_disc: Path, name: str, doc: str) -> tuple[Path, Path]:
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--disc", type=Path, default=default_disc,
                    help=f"目录盘或 ISO（缺省 {default_disc.relative_to(REPO)}）")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "emu" / "drives" / name)
    a = ap.parse_args()
    if not a.disc.exists():
        sys.exit(f"盘不存在：{a.disc}（先跑 build_disc.py 对应剖面）")
    if a.out.exists():
        shutil.rmtree(a.out)
    a.out.mkdir(parents=True)
    return a.disc, a.out


async def wait_game(cli, settle: float) -> None:
    """等引擎进入运行态，再等 settle 秒让初始化/开场演出走完。"""
    for _ in range(60):
        st = await cli.game_status()
        if st.get("game"):
            print("game:", st["game"].get("id", st["game"]), flush=True)
            break
        await asyncio.sleep(1)
    else:
        sys.exit("游戏未进入运行态")
    await asyncio.sleep(settle)


async def snap(cli, path: Path):
    """断 CPU → 直读 VRAM → 放行。gpu.buffer.screenshot 在本机两种后端都不可用。"""
    await cli.break_cpu()
    img = await cli.vram_screenshot()
    await cli.resume()
    img.save(path)
    return img


def report_errors(cli) -> int:
    errors = [d.get("message") for d in cli.drain_broadcasts("log") if d.get("level") == 2]
    print(f"ERROR 日志 {len(errors)} 条", flush=True)
    for e in errors[:10]:
        print("  ", e, flush=True)
    return len(errors)
