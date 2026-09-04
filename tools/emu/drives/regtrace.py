#!/usr/bin/env -S uv run python
"""断点 + 寄存器/内存转储 + 单步：研究/验证 EBOOT 补丁时看"引擎此刻到底在算什么"。

    uv run python tools/emu/drives/regtrace.py --bp 0xA4DC --cond "s0 == 1" --steps 12 \\
        --regs pc,a0,v0,s0,s1,s2,s4,t4,t5 --read s5:16 --read s4:24

--bp 给 ELF 内 VA（IDA 里的地址），脚本自动加装载基址 0x08804000（--abs 则按运行时地址）。
流程：引导盘 → 等 settle 秒 → 设断点（可带 PPSSPP 条件表达式）→ 每 --interval 秒按一次
CIRCLE 直到断住（最多 --presses 次）→ 打印寄存器与 --read 指定的内存 → 单步 --steps 条
（jal 用 stepOver 跨过调用），每步打印寄存器与下一条反汇编 → 撤断点放行。
单步走的是 WS 广播（cpu.stepInto/stepOver 没有票据回包，request() 会超时），见 _step()。
memory.read 对无效地址会抛 EmuError，这里捕获后打印"read failed"——那本身就是线索
（2026-09-04 就是靠它发现 s4 被重定位砸成 1）。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO, TEST_GAME, Emulator, session  # noqa: E402

LOAD_BASE = 0x08804000


async def _reg(cli, name: str) -> int:
    return (await cli.request("cpu.getReg", name=name))["uintValue"]


async def _regs(cli, names: list[str]) -> dict[str, int]:
    return {n: await _reg(cli, n) for n in names}


def _fmt(r: dict[str, int]) -> str:
    return " ".join(f"{k}={v:#x}" for k, v in r.items())


async def _step(cli, kind: str) -> None:
    mark = cli.seq_mark()
    await cli.fire(kind)
    await cli.wait_broadcast("cpu.stepping", after_seq=mark, timeout=8)


async def _dump_reads(cli, reads: list[str], regs: dict[str, int]) -> None:
    for spec in reads:
        reg, _, n = spec.partition(":")
        addr = regs.get(reg) if reg in regs else int(reg, 0)
        size = int(n or "16")
        try:
            print(f"    mem[{reg}={addr:#x}] = {await cli.read_bytes(addr, size)}")
        except Exception as e:                       # noqa: BLE001
            print(f"    mem[{reg}={addr:#x}] read failed: {e}")


async def run(a: argparse.Namespace) -> None:
    bp = a.bp if a.abs else a.bp + LOAD_BASE
    names = a.regs.split(",")
    async with session(lambda: Emulator.app(a.disc, graphics="software")) as (emu, cli):
        for _ in range(60):
            if (await cli.game_status()).get("game"):
                break
            await asyncio.sleep(1)
        await asyncio.sleep(a.settle)
        await cli.bp_add(bp, condition=a.cond)
        hit = False
        for _ in range(a.presses):
            if (await cli.cpu_status()).get("stepping"):
                hit = True
                break
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(a.interval)
        if not hit and not (await cli.cpu_status()).get("stepping"):
            print(f"断点 {bp:#x} 在 {a.presses} 次按键内未命中")
            await cli.bp_remove(bp)
            return
        regs = await _regs(cli, names)
        print(f"hit @ {bp:#x}: {_fmt(regs)}")
        for r in a.read:
            await _dump_reads(cli, [r], regs)
        for i in range(a.steps):
            pc = await _reg(cli, "pc")
            line = (await cli.disasm(pc, 1))[0]
            kind = "cpu.stepOver" if str(line.get("name", "")).startswith("jal") else "cpu.stepInto"
            await _step(cli, kind)
            regs = await _regs(cli, names)
            print(f"{i:2} after {line.get('name', '')} {str(line.get('params', '')):26} -> {_fmt(regs)}")
        if a.steps:
            for r in a.read:
                await _dump_reads(cli, [r], regs)
        await cli.bp_remove(bp)
        await cli.resume()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=Path, default=TEST_GAME)
    ap.add_argument("--bp", type=lambda s: int(s, 0), required=True, help="ELF VA（缺省自动 +0x08804000）")
    ap.add_argument("--abs", action="store_true", help="--bp 已是运行时地址")
    ap.add_argument("--cond", default=None, help='PPSSPP 断点条件，如 "s0 == 1"')
    ap.add_argument("--presses", type=int, default=14, help="最多按几次 CIRCLE 去够断点")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--settle", type=float, default=12.0)
    ap.add_argument("--regs", default="pc,a0,a1,a2,a3,v0,s0,s1,s2,s4,s5,t4,t5,ra")
    ap.add_argument("--read", action="append", default=[], help="reg:bytes 或 0xADDR:bytes，可多次")
    ap.add_argument("--steps", type=int, default=0)
    a = ap.parse_args()
    if not a.disc.exists():
        sys.exit(f"盘不存在：{a.disc}（先 build_disc.py --profile test --mode font）")
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
