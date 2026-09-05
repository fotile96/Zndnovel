#!/usr/bin/env -S uv run python
"""用户内存预算探针：定时快照 heap16 块表与 newlib 堆（UserSbrk）指针，算出模块+C 堆与
heap16 之间的空隙（= 扩 bss 的余地）。

    uv run python tools/build_disc.py --profile test --mode movie     # OP 影片循环播放（峰值场合）
    uv run python tools/emu/drives/mem_probe.py --count 10 --interval 6

依据 docs/ops/eboot-savedata-research-2026-09-05.md §8a「内存预算」：模块之后紧跟 4 MB 固定的
UserSbrk（sceKernelAllocPartitionMemory LowAligned），heap16 走 sceKernelAllocMemoryBlock High
自顶向下；空隙 = 最低 heap16 块地址 − C 堆末。表/指针都是 bss 对象（IDA 地址减 0x6DA40 加基址）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO, TEST_GAME, Emulator, session, wait_game  # noqa: E402

LOAD_BASE, BSS_SHIFT = 0x08804000, 0x6DA40
HEAP16_TABLE_IDA, HEAP16_N = 0x257D60, 2000        # unk_257D60：2000 × {u8 used; u32 uid; u32 addr}
SBRK_BRK_IDA, SBRK_BASE_IDA, SBRK_END_IDA = 0x1DB4B8, 0x1DB4BC, 0x1DB4C0
USER_TOP = 0x0A000000


def bss(ida: int) -> int:
    return ida - BSS_SHIFT + LOAD_BASE


async def snapshot(cli) -> dict:
    await cli.break_cpu()
    tbl = await cli.read_bytes(bss(HEAP16_TABLE_IDA), 12 * HEAP16_N)
    base, brk, end = [await cli.read_u32(bss(x)) for x in (SBRK_BASE_IDA, SBRK_BRK_IDA, SBRK_END_IDA)]
    await cli.resume()
    addrs = sorted(struct.unpack_from("<I", tbl, i * 12 + 8)[0] for i in range(HEAP16_N)
                   if tbl[i * 12] and struct.unpack_from("<I", tbl, i * 12 + 8)[0])
    return {"sbrk_base": base, "sbrk_brk": brk, "sbrk_end": end, "heap16_blocks": len(addrs),
            "heap16_low": addrs[0] if addrs else None, "heap16_high": addrs[-1] if addrs else None,
            "gap": (addrs[0] - end) if addrs and end else None}


def fmt(s: dict) -> str:
    kb = lambda n: f"{n / 1024:.0f} KB"   # noqa: E731
    used = kb(s["sbrk_brk"] - s["sbrk_base"]) if s["sbrk_base"] else "?"
    return (f"C堆 {used}/{kb(s['sbrk_end'] - s['sbrk_base']) if s['sbrk_base'] else '?'}"
            f"（末 {s['sbrk_end']:#x}）  heap16 {s['heap16_blocks']} 块 自 {s['heap16_low']:#x}"
            f"（顶下 {kb(USER_TOP - s['heap16_low'])}）  空隙 {kb(s['gap']) if s['gap'] is not None else '?'}")


async def run(a: argparse.Namespace) -> int:
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    async with session(lambda: Emulator.app(a.disc, graphics="software")) as (emu, cli):
        await wait_game(cli, a.settle)
        for i in range(a.count):
            s = await snapshot(cli)
            rows.append(s)
            print(f"[{i * a.interval + a.settle:5.0f}s] {fmt(s)}", flush=True)
            await asyncio.sleep(a.interval)
    gaps = [r["gap"] for r in rows if r["gap"] is not None]
    print(f"最小空隙 {min(gaps) / 1024:.0f} KB（{len(rows)} 次快照）")
    (a.out / f"result{('_' + a.tag) if a.tag else ''}.json").write_text(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=Path, default=TEST_GAME)
    ap.add_argument("--out", type=Path, default=REPO / "build" / "emu" / "drives" / "mem_probe")
    ap.add_argument("--settle", type=float, default=8.0)
    ap.add_argument("--interval", type=float, default=6.0)
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--tag", default="")
    sys.exit(asyncio.run(run(ap.parse_args())))
