#!/usr/bin/env -S uv run python
"""谢幕『声』选择画面驾驶：主菜单定位 encore → ○ → 截提示帧/按钮帧 → 按 FIN_PICK 选项 → 连按若干次截进场帧。

前置：FIN_PICK=1|2 时 `build_disc.py --profile test --mode mainmenu --finale-read`；
      FIN_PICK=0（期望**没有**选择画面、直入 fin-0 递笔）时 `build_disc.py --profile test --mode mainmenu`
      （不带 --finale-read）。缺省引导 test 盘。
环境变量：FIN_PICK（缺省 2）、FIN_AFTER（选完后连按次数，缺省 12）。
时序（○ 之后）：菜单退场与载脚本约 3 s → eve_0_g 淡入+停 2 s → 提示 eve_0_j 淡入 1 s、停 3.3 s → 脚注 eve_0_k
      淡入+停 2 s → 按钮（实测约 12 s；switchScreen 阻塞到转场结束）。
期望：FIN_PICK=1/2 → a_prompt.png 是「你的声音是——」提示、b_buttons.png 是两枚光晕按钮＋脚注、
      c_pick.png 亮态在所选项；after_NN.png 里 FIN_PICK=1 出现 fin-0「……卧槽，所以我们搞完了」、
      FIN_PICK=2 出现 fin-60「……啧啧，这写得可以啊」。FIN_PICK=0 → a/b 两帧是 fin-0 黑屏文字，不得出现按钮。
      ERROR 0 条（ILLEGAL_THID HLE 噪声除外）。
系统数据：模拟器里的 NPJH50279SYSTEM 可能早被别的驾驶写进了 finaleReadFlag = true（存档加密，看不出来），
      FIN_PICK=0 那一跑因此先把它挪开——开机 runAutoLoad 读不到系统数据，systemSave 保持
      snr_common 字面表缺省（finaleReadFlag = false），不弹任何对话框。三种跑法都先备份到 OUT 之外的
      build/emu/finale_choice_system_backup/、跑完原样放回；上次没放回的备份还在就拒绝开跑（别覆盖它）。
光标定位同 finale_full.py（亮态项深蓝核心像素占比）。
"""
import asyncio
import os
import shutil
import sys
from pathlib import Path

from _common import REPO, TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

DISC, OUT = parse(TEST_GAME, "finale_choice", __doc__)
PICK = int(os.environ.get("FIN_PICK", "2"))
AFTER = int(os.environ.get("FIN_AFTER", "12"))
SYSTEM_SAVE = Path.home() / ".config" / "ppsspp" / "PSP" / "SAVEDATA" / "NPJH50279SYSTEM"
BACKUP = REPO / "build" / "emu" / "finale_choice_system_backup"

ORDER = ["story", "fragment", "section7", "finale", "library", "option"]
BANDS = {"story": (200, 105, 300, 132), "fragment": (185, 132, 300, 158),
         "section7": (185, 160, 300, 186), "finale": (190, 187, 300, 213),
         "library": (200, 214, 275, 239), "option": (205, 241, 275, 264)}


def cursor_index(img):
    px = img.convert("RGB")
    best, idx = -1.0, None
    for i, k in enumerate(ORDER):
        x0, y0, x1, y1 = BANDS[k]
        strong = core = 0
        for y in range(y0, min(y1, px.height), 2):
            for x in range(x0, x1, 2):
                r, g, b = px.getpixel((x, y))
                if b > 150 and b - r > 30:
                    strong += 1
                    if r < 100 and b > 210:
                        core += 1
        frac = core / strong if strong > 25 else 0.0
        if frac > best:
            best, idx = frac, i
    return idx, best


async def drive():
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 15)
        target = ORDER.index("finale")
        for step in range(10):
            img = await snap(cli, OUT / f"nav{step}.png")
            idx, frac = cursor_index(img)
            print(f"nav{step}: cursor={ORDER[idx] if idx is not None else '?'} frac={frac:.2f}", flush=True)
            if idx == target and frac > 0.2:
                break
            if idx is None:
                await asyncio.sleep(2.0)
                continue
            await cli.buttons_press("down" if idx < target else "up", duration=3)
            await asyncio.sleep(2.5)
        else:
            sys.exit("未能定位 finale 光标")
        await cli.buttons_press("circle", duration=3)
        await asyncio.sleep(5.5)                       # 提示「你的声音是——」在屏（4.0–7.3 s）
        await snap(cli, OUT / "a_prompt.png")
        await asyncio.sleep(7.5)                       # 脚注与按钮就位（实测按钮约 12 s 才出：switchScreen 阻塞，
                                                       # 6.0 s 时只有脚注、下键可能落空）
        await snap(cli, OUT / "b_buttons.png")
        if PICK == 2:
            await cli.buttons_press("down", duration=3)
        await asyncio.sleep(1.0)                       # 两种选法都隔 1 s 再截（紧贴上一帧截会读到旧帧缓冲）
        await snap(cli, OUT / "c_pick.png")
        if PICK:
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(3.0)
        for i in range(1, AFTER + 1):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.2)
            await snap(cli, OUT / f"after_{i:02d}.png")
        report_errors(cli)


async def run():
    if BACKUP.exists():
        sys.exit(f"{BACKUP} 还在——上次运行没把系统数据放回去；先核对后手工恢复到 {SYSTEM_SAVE} 再删掉它")
    had = SYSTEM_SAVE.exists()
    if had:
        shutil.copytree(SYSTEM_SAVE, BACKUP)
    try:
        if PICK == 0 and had:
            shutil.rmtree(SYSTEM_SAVE)                 # 无系统数据开机：finaleReadFlag 取字面表缺省 false
        await drive()
    finally:
        shutil.rmtree(SYSTEM_SAVE, ignore_errors=True)
        if had:
            shutil.copytree(BACKUP, SYSTEM_SAVE)
            shutil.rmtree(BACKUP)
    print(f"截图 -> {OUT}")


asyncio.run(run())
