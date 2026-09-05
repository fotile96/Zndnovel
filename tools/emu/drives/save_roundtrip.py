#!/usr/bin/env -S uv run python
"""存档往返验证：直入场景 → 毒化旧结构区 → 暂停菜单「保存」走完 PSP 存档对话框 → 推进两句 →
「读取」走完读档对话框 → 核对恢复到存档时那句、旧结构区一字未动。

    uv run python tools/build_disc.py --profile test --mode scene --scene s1s_20 --no-cards [--bloat]
    uv run python tools/emu/drives/save_roundtrip.py --patched --tag s1s_20

判据（全部打印并写 result_<tag>.json）：
  saved_ok      存档序列化后 mainThread blob ≤ 容量（断点 0xCB50 读 size 字段）
  resumed_ok    读档后消息缓冲（msg_text_buf，IDA 0x1DD440）与存档瞬间一致
  poison_ok     --patched 时旧结构区（IDA 0x32DAA8，0x63268 B）在存/读档后仍全是 0xEE
对话框按键序列按 PPSSPP 的 savedata UI 实测（选槽 CIRCLE → 确认 CIRCLE → 完成 CIRCLE），
每步截图到 --out，失败时看图定位卡在哪一步。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO, TEST_GAME, Emulator, report_errors, session, snap, wait_game  # noqa: E402

sys.path.insert(0, str(REPO))
from tools import pluto_size as ps  # noqa: E402

LOAD_BASE = 0x08804000
BSS_SHIFT = 0x6DA40
BP_AFTER_PERSIST = 0xCB50
OLD_STRUCT_IDA = 0x32DAA8
STRUCT_SIZE = 0x63268
MSG_TEXT_BUF_IDA = 0x1DD440         # msg_text_buf，500 B
DIALOG_ACTIVE_IDA = 0x326294        # byte_326294：sceUtilitySavedata 对话框活动中
LOAD_OK_IDA = 0x326297              # byte_326297：上次 LOAD result==0（applyGamedata 后清零）
PARAM_RESULT_IDA = 0x325204         # SceUtilitySavedataParam.common.result
GAMESAVE_SIZE_OFF, THREAD_SIZE_OFF = 0x7C80, 0x57C84


def bss(ida_va: int) -> int:
    return ida_va - BSS_SHIFT + LOAD_BASE


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=Path, default=TEST_GAME)
    ap.add_argument("--out", type=Path, default=REPO / "build" / "emu" / "drives" / "save_roundtrip")
    ap.add_argument("--presses", type=int, default=8)
    ap.add_argument("--settle", type=float, default=16.0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--patched", action="store_true", help="盘里 EBOOT 带 savebuf 层：按新布局读并毒化旧区")
    ap.add_argument("--dialog-wait", type=float, default=3.0, help="PSP 对话框每步等待秒数")
    return ap.parse_args()


async def press(cli, btn: str, wait: float, duration: int = 3) -> None:
    await cli.buttons_press(btn, duration=duration)
    await asyncio.sleep(wait)


async def read_msg(cli) -> str:
    raw = await cli.read_bytes(bss(MSG_TEXT_BUF_IDA), 500)
    return raw.split(b"\0")[0].decode("utf-8", "replace")


async def read_u8(cli, ida: int) -> int:
    return (await cli.read_bytes(bss(ida), 1))[0]


async def wait_flag(cli, ida: int, value: int, seconds: float, press_every: float = 0.0,
                    button: str = "circle") -> bool:
    """轮询某个 bss 字节直到等于 value；press_every>0 时每隔这么久按一次 button（收掉"完成"提示）。"""
    t = 0.0
    while t < seconds:
        if await read_u8(cli, ida) == value:
            return True
        await asyncio.sleep(0.5)
        t += 0.5
        if press_every and abs(t % press_every) < 0.25:
            await cli.buttons_press(button, duration=4)
    return False


async def drive_savedata_dialog(cli, out: Path, tag: str, step: str, dw: float) -> bool:
    """LISTSAVE/LISTLOAD 对话框（PPSSPP Core/Dialog/PSPSaveDialog.cpp 的状态机）：
    列表 ○ 选槽 → 槽里已有数据时弹「覆盖？」且默认 No：← 到 Yes 再 ○（空槽直接开始写）→
    「Save completed」只认 ✕（Load completed ○✕ 皆可）→ 引擎 ShutdownStart → 活动标志回 0。
    结束后读 param.result（IDA 0x325204）：0 = 成功。"""
    if not await wait_flag(cli, DIALOG_ACTIVE_IDA, 1, 15):
        print(f"[{step}] 存档对话框没有启动")
        return False
    await asyncio.sleep(dw)
    await snap(cli, out / f"{step}a_list{tag}.png")
    await press(cli, "circle", 1.5)                      # 选槽（NEW DATA / GAME00）
    await snap(cli, out / f"{step}b_confirm{tag}.png")
    await press(cli, "left", 0.5)                        # 若是「覆盖？」：No → Yes
    await press(cli, "circle", 3.0)                      # 确认（无确认框时此键被忽略）
    ok = await wait_flag(cli, DIALOG_ACTIVE_IDA, 0, 40, press_every=3.0, button="cross")
    await snap(cli, out / f"{step}c_done{tag}.png")
    res = await cli.read_u32(bss(PARAM_RESULT_IDA))
    print(f"[{step}] 对话框{'结束' if ok else '超时未结束'}，param.result = {res:#x}")
    return ok and res == 0


async def wait_bp(cli, seconds: float) -> bool:
    for _ in range(int(seconds * 2)):
        await asyncio.sleep(0.5)
        if (await cli.cpu_status()).get("stepping"):
            return True
    return False


async def run(a: argparse.Namespace) -> int:
    a.out.mkdir(parents=True, exist_ok=True)
    tag = f"_{a.tag}" if a.tag else ""
    base_raw, delta = ps.savebuf_layout("test") if a.patched else (ps.STRUCT_RAW, 0)
    struct_ida = base_raw + 2 * BSS_SHIFT
    cap = ps.THREAD_CAP + delta
    result: dict = {"patched": a.patched, "delta": delta}
    bp = LOAD_BASE + BP_AFTER_PERSIST
    dw = a.dialog_wait
    async with session(lambda: Emulator.app(a.disc, graphics="software")) as (emu, cli):
        await wait_game(cli, a.settle)
        # 毒化旧结构区（只在扩容布局下：旧区已无人引用）
        if a.patched:
            await cli.break_cpu()
            await cli.write_bytes(bss(OLD_STRUCT_IDA), b"\xee" * STRUCT_SIZE)
            await cli.resume()
        for i in range(a.presses):
            await press(cli, "circle", 2.2)
        await snap(cli, a.out / f"10_before_save{tag}.png")
        msg_at_save = await read_msg(cli)
        print(f"存档瞬间消息: {msg_at_save[:40]!r}")
        # 暂停菜单 → 保存
        await cli.bp_add(bp)
        await press(cli, "square", 2.5)
        await press(cli, "down", 0.8)
        await press(cli, "down", 0.8)
        await snap(cli, a.out / f"11_menu_save{tag}.png")
        await press(cli, "circle", 0.5)
        if not await wait_bp(cli, 30):
            print("未命中序列化断点——暂停菜单/存档项没打开？看截图")
            return 2
        gs = await cli.read_u32(bss(struct_ida + GAMESAVE_SIZE_OFF))
        th = await cli.read_u32(bss(struct_ida + THREAD_SIZE_OFF + delta))
        result.update({"gamesave_blob": gs, "thread_blob": th, "thread_cap": cap, "saved_ok": th <= cap})
        print(f"序列化完成：gameSave {gs} B，mainThread {th} B / {cap} B → {'OK' if th <= cap else '超容量'}")
        await cli.bp_remove(bp)
        await cli.resume()
        # PSP LISTSAVE 对话框
        if not await drive_savedata_dialog(cli, a.out, tag, "12", dw):
            return 3
        # Lua 侧 autoSystemSave(1)：无系统数据时弹「是/否」确认（是 默认高亮）→ CIRCLE → AUTOSAVE 对话框
        await asyncio.sleep(2.5)
        await snap(cli, a.out / f"15_sysconfirm{tag}.png")
        await press(cli, "circle", 1.0)
        if await wait_flag(cli, DIALOG_ACTIVE_IDA, 1, 8):
            await wait_flag(cli, DIALOG_ACTIVE_IDA, 0, 30)
            print("[15] 系统数据 AUTOSAVE 完成")
        await asyncio.sleep(3.0)                         # pageScreen(0); wait(10); Config() 菜单重开
        await snap(cli, a.out / f"16_menu_reopened{tag}.png")
        await press(cli, "cross", 2.5)                   # 关菜单
        await snap(cli, a.out / f"17_menu_closed{tag}.png")
        # 推进两句，让"读档前"与"存档瞬间"的消息不同
        await press(cli, "circle", 2.2)
        await press(cli, "circle", 2.2)
        await snap(cli, a.out / f"20_advanced{tag}.png")
        msg_before_load = await read_msg(cli)
        print(f"读档前消息: {msg_before_load[:40]!r}")
        # 暂停菜单 → 读取（第 4 项）→ LISTLOAD 对话框 → AUTOLOAD → applyGamedata
        await press(cli, "square", 2.5)
        for _ in range(3):
            await press(cli, "down", 0.8)
        await snap(cli, a.out / f"21_menu_load{tag}.png")
        await press(cli, "circle", 0.5)
        if not await drive_savedata_dialog(cli, a.out, tag, "22", dw):
            return 4
        load_ok = await read_u8(cli, LOAD_OK_IDA)
        print(f"[22] succeedLoadGamedata 标志 = {load_ok}")
        if await wait_flag(cli, DIALOG_ACTIVE_IDA, 1, 8):          # runAutoLoad 的 AUTOLOAD
            await wait_flag(cli, DIALOG_ACTIVE_IDA, 0, 30)
        await asyncio.sleep(6.0)                                     # cInitGame/switchScreen/applyGamedata
        await snap(cli, a.out / f"26_resumed{tag}.png")
        msg_after_load = await read_msg(cli)
        print(f"读档后消息: {msg_after_load[:40]!r}")
        result.update({"msg_at_save": msg_at_save, "msg_before_load": msg_before_load,
                       "msg_after_load": msg_after_load, "load_flag": load_ok})
        result["resumed_ok"] = (msg_after_load == msg_at_save and msg_after_load != msg_before_load)
        if a.patched:
            await cli.break_cpu()
            poison = await cli.read_bytes(bss(OLD_STRUCT_IDA), STRUCT_SIZE)
            await cli.resume()
            bad = sum(1 for b in poison if b != 0xEE)
            result["poison_ok"] = bad == 0
            print(f"旧结构区毒化核对：{bad} B 被改动 → {'OK' if bad == 0 else '有代码仍在写旧区！'}")
        result["errors"] = report_errors(cli)
    print("判定:", {k: v for k, v in result.items() if k.endswith("_ok")})
    (a.out / f"result{tag}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(v for k, v in result.items() if k.endswith("_ok")) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
