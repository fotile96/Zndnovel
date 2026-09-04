#!/usr/bin/env -S uv run python
"""存档探针：直入场景 → 呼出暂停菜单 → 选「存档」→ 在引擎序列化完成处断住，读出
Pluto blob 的真实大小并把整个 406120 B 存档结构转储到文件。

    uv run python tools/build_disc.py --profile test --mode scene --scene s1s_20 --no-cards
    uv run python tools/emu/drives/save_probe.py --presses 3

机制（docs/ops/eboot-savedata-research-2026-09-05.md）：`runListSave()` 只置标志并
yield；`script_step`(0x5CCC) 看到标志后调 `savedata_req_listsave_game`(0xCB1C) →
`gamedata_persist_or_apply(1)`(0x6E78) 用 Pluto 把 `gameSave` 表与 `mainThread` 协程
序列化进全局数组 0x32DAA8（0x63268 B），再 sceUtilitySavedataInitStart。断点设在
0xCB50（jal 返回后的第一条指令），此时两个 size 字段已写好：
  0x335728 = gameSave blob 大小（区间 0x32DF28..0x335728，容量 0x7800）
  0x38572C = mainThread blob 大小（区间 0x33572C..0x38572C，容量 0x50000）
写入回调 `pluto_writer_membuf`(0x5FF8) 逐字节拷贝且无边界检查——blob 超容量即
溢出后续字段乃至整个结构之外。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO, TEST_GAME, Emulator, report_errors, session, snap, wait_game  # noqa: E402

LOAD_BASE = 0x08804000
# ⚠ IDB 里 bss（段 1）对象的地址比链接时 VA 高 0x6DA40（IDA 的 PSP 重定位把段基址加了两次）；
# 代码段地址（函数/rodata）无此偏移。bss 对象运行时地址 = IDA 地址 − 0x6DA40 + 0x08804000。
BSS_SHIFT = 0x6DA40
BP_AFTER_PERSIST = 0xCB50          # savedata_req_listsave_game: jal gamedata_persist_or_apply 之后
SAVEDATA_PARAM = 0x3251E8          # SceUtilitySavedataParam（IDA 地址，bss）
SAVE_STRUCT = 0x32DAA8
SAVE_STRUCT_SIZE = 0x63268
GAMESAVE_BLOB = 0x32DF28
GAMESAVE_SIZE_FIELD = 0x335728
THREAD_BLOB = 0x33572C
THREAD_SIZE_FIELD = 0x38572C
THREAD_CAP = THREAD_SIZE_FIELD - THREAD_BLOB       # 0x50000
GAMESAVE_CAP = GAMESAVE_SIZE_FIELD - GAMESAVE_BLOB  # 0x7800


def bss(ida_va: int) -> int:
    """IDA 里的 bss 地址 → PPSSPP 运行时地址。"""
    return ida_va - BSS_SHIFT + LOAD_BASE


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=Path, default=TEST_GAME)
    ap.add_argument("--out", type=Path, default=REPO / "build" / "emu" / "drives" / "save_probe")
    ap.add_argument("--presses", type=int, default=3, help="呼出菜单前先按几次 CIRCLE 推进对白")
    ap.add_argument("--settle", type=float, default=14.0)
    ap.add_argument("--tag", default="", help="输出文件名后缀（区分场景）")
    ap.add_argument("--no-dump", action="store_true", help="不转储 406 KB 存档结构")
    return ap.parse_args()


async def read_chunked(cli, addr: int, size: int, chunk: int = 0x10000) -> bytes:
    out = bytearray()
    while len(out) < size:
        n = min(chunk, size - len(out))
        out += await cli.read_bytes(addr + len(out), n)
    return bytes(out)


async def run(a: argparse.Namespace) -> int:
    a.out.mkdir(parents=True, exist_ok=True)
    tag = f"_{a.tag}" if a.tag else ""
    bp = LOAD_BASE + BP_AFTER_PERSIST
    result: dict = {"disc": str(a.disc), "presses": a.presses}
    async with session(lambda: Emulator.app(a.disc, graphics="software")) as (emu, cli):
        await wait_game(cli, a.settle)
        # 地址换算自检：SceUtilitySavedataParam.size 必为 1536、gameName 必为 NPJH50279
        await cli.break_cpu()
        psize = await cli.read_u32(bss(SAVEDATA_PARAM))
        gname = await cli.read_string(bss(SAVEDATA_PARAM) + 0x3C)
        await cli.resume()
        if psize != 1536 or gname != "NPJH50279":
            print(f"bss 地址换算失败：param.size={psize} gameName={gname!r}（期望 1536 / NPJH50279）")
            return 3
        print(f"bss 换算自检通过：param@{bss(SAVEDATA_PARAM):#x} size={psize} gameName={gname}")
        await snap(cli, a.out / f"00_scene{tag}.png")
        for i in range(a.presses):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.5)
            await snap(cli, a.out / f"01_press{i:02d}{tag}.png")
        await cli.bp_add(bp)
        await cli.buttons_press("square", duration=3)
        await asyncio.sleep(2.5)
        await snap(cli, a.out / f"02_menu{tag}.png")
        for _ in range(2):                      # 光标 1(story)→2(fragment)→3(save)
            await cli.buttons_press("down", duration=3)
            await asyncio.sleep(0.8)
        await snap(cli, a.out / f"03_cursor_save{tag}.png")
        await cli.buttons_press("circle", duration=3)
        hit = False
        for _ in range(60):
            await asyncio.sleep(0.5)
            if (await cli.cpu_status()).get("stepping"):
                hit = True
                break
        if not hit:
            print("断点未命中（暂停菜单没打开或不是存档项？看截图）")
            await cli.bp_remove(bp)
            report_errors(cli)
            return 2
        pc = (await cli.request("cpu.getReg", name="pc"))["uintValue"]
        gs = await cli.read_u32(bss(GAMESAVE_SIZE_FIELD))
        th = await cli.read_u32(bss(THREAD_SIZE_FIELD))
        title = await cli.read_string(bss(SAVE_STRUCT))          # savedataTitle() 第 1 参
        chapter = await cli.read_string(bss(SAVE_STRUCT) + 0x80)  # savedataTitle() 第 2 参
        result.update({"pc": hex(pc), "gamesave_blob": gs, "gamesave_cap": GAMESAVE_CAP,
                       "thread_blob": th, "thread_cap": THREAD_CAP,
                       "thread_headroom": THREAD_CAP - th, "title": title, "chapter": chapter})
        print(f"hit pc={pc:#x}  gameSave blob = {gs} B / {GAMESAVE_CAP} B  "
              f"mainThread blob = {th} B / {THREAD_CAP} B  (headroom {THREAD_CAP - th} B)")
        print(f"title={title!r} chapter={chapter!r}")
        img = await cli.vram_screenshot()
        img.save(a.out / f"04_at_bp{tag}.png")
        if not a.no_dump:
            blob = await read_chunked(cli, bss(SAVE_STRUCT), SAVE_STRUCT_SIZE)
            (a.out / f"savestruct{tag}.bin").write_bytes(blob)
            print(f"dumped {len(blob)} B -> {a.out / f'savestruct{tag}.bin'}")
        await cli.bp_remove(bp)
        await cli.resume()
        await asyncio.sleep(4.0)
        await snap(cli, a.out / f"05_save_dialog{tag}.png")
        result["errors"] = report_errors(cli)
    (a.out / f"result{tag}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
