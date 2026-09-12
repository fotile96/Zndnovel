#!/usr/bin/env -S uv run python
"""题名 logo 双态端到端：开机日文 logo → 跑完谢幕章 → 回主菜单换中文 logo → 重启仍是中文。

前置：`build_disc.py --profile test --mode mainmenu`（全解锁，含 encore 项）。
流程：会话 A 截标题（00）→ 光标定位 encore → 逐句 CIRCLE 跑完 fin-10..50（每句先截图
判态，回到标题即停；每 25 句留一帧）→ 主菜单截 end0..2；会话 B 重新起模拟器截标题（10）——验证 finaleReadFlag
确实随 autoSystemSave(0) 写进了 NPJH50279SYSTEM。
判据（数值）：logo 区（屏幕 38..443 × 10..99）与「bg_4_a_0 + 日文/中文 logo」合成图各算
MSE，取更近者为该帧的 logo 态；中文期望图从本次盘的成员 stage/sysgim/title_01_c.gim
解码（含量化损耗）。期望：00 帧 ja；end*/10 帧 zh；ERROR 0 条。
跑前备份模拟器的 NPJH50279SYSTEM，跑完恢复（`--keep-save` 则保留写了旗标的系统数据）。
**存档兼容也在这里验**：00 帧是用模拟器里**旧的**系统数据（本旗标出现之前写的，表里没有
`finaleReadFlag` 键，等价于原版/旧 release 的存档）开机——必须正常画出日文 logo、ERROR 0；
跑完谢幕后同一份系统数据被 autoSystemSave 覆写成带键的新版，10 帧验它被读回。
时长约 15 分钟。
"""
import asyncio
import shutil
import sys
from pathlib import Path

KEEP_SAVE = "--keep-save" in sys.argv
sys.argv = [a for a in sys.argv if a != "--keep-save"]

from _common import REPO, TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game  # noqa: E402

DISC, OUT = parse(TEST_GAME, "title_logo", __doc__)
sys.path.insert(0, str(REPO))
from PIL import Image  # noqa: E402

from tools.gimcodec import Gim  # noqa: E402

SYSTEM_SAVE = Path.home() / ".config" / "ppsspp" / "PSP" / "SAVEDATA" / "NPJH50279SYSTEM"
LOGO_BOX = (38, 10, 38 + 405, 10 + 89)
ORDER = ["story", "fragment", "section7", "finale", "library", "option"]
BANDS = {"story": (200, 105, 300, 132), "fragment": (185, 132, 300, 158),
         "section7": (185, 160, 300, 186), "finale": (190, 187, 300, 213),
         "library": (200, 214, 275, 239), "option": (205, 241, 275, 264)}


def expected_logos() -> dict[str, Image.Image]:
    bg = Image.open(REPO / "png" / "bg" / "bg_4_a_0.png").convert("RGBA")
    ja = Image.open(REPO / "png" / "sysgim" / "title_01_a.png").convert("RGBA")
    gim = next(p for p in (REPO / "build" / "test" / "stage" / "sysgim" / "title_01_c.gim",
                           REPO / "build" / "test" / "members" / "sysgim" / "title_01_c.gim")
               if p.exists())
    zh = Gim(gim.read_bytes()).to_pil().convert("RGBA")
    out = {}
    for tag, logo in (("ja", ja), ("zh", zh)):
        fr = bg.copy()
        fr.alpha_composite(logo, (LOGO_BOX[0], LOGO_BOX[1]))
        out[tag] = fr.crop(LOGO_BOX).convert("RGB")
    return out


def mse(a: Image.Image, b: Image.Image) -> float:
    pa, pb = a.getdata(), b.getdata()
    return sum((x - y) ** 2 for p, q in zip(pa, pb) for x, y in zip(p, q)) / (len(pa) * 3)


def classify(img: Image.Image, expect: dict[str, Image.Image], tag: str) -> str:
    region = img.convert("RGB").crop(LOGO_BOX)
    scores = {k: mse(region, v) for k, v in expect.items()}
    verdict = min(scores, key=scores.get)
    print(f"{tag}: MSE ja={scores['ja']:.1f} zh={scores['zh']:.1f} → {verdict}", flush=True)
    return verdict


def is_title(img: Image.Image, expect: dict[str, Image.Image], thresh: float = 100.0) -> bool:
    """logo 区与任一期望合成图 MSE < thresh 即标题画面（实测同态 ≈14，白闪中/章内画面 ≫100）。"""
    region = img.convert("RGB").crop(LOGO_BOX)
    return min(mse(region, v) for v in expect.values()) < thresh


def is_black(img: Image.Image) -> bool:
    """99.8% 以上像素 max(RGB) < 16 视为全黑（淡出帧）。"""
    px = img.convert("RGB").getdata()
    dark = sum(1 for r, g, b in px if max(r, g, b) < 16)
    return dark >= 0.998 * len(px)


async def snap_retry(cli, path, tries: int = 3):
    """截图容错。`snap()` 先 break_cpu 等 `cpu.stepping` 广播，模拟器忙时这个请求偶发
    丢失（2026-09-12 谢幕章第 125 句实测踩到一次，整轮 15 分钟白跑）。break_cpu 本身
    已处理「已经断住」那种不会再有新广播的情形，所以这里只需对「请求没被响应」重试：
    放行 CPU、缓一拍再试，连续失败才抛。"""
    for i in range(tries):
        try:
            return await snap(cli, path)
        except TimeoutError:
            print(f"截图超时（{i + 1}/{tries}），放行 CPU 后重试", flush=True)
            try:
                await cli.resume()
            except Exception:
                pass
            await asyncio.sleep(3.0)
    raise TimeoutError(f"连续 {tries} 次截图超时：{path}")


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


async def play_finale(cli, expect):
    target = ORDER.index("finale")
    for step in range(10):
        img = await snap_retry(cli, OUT / f"nav{step}.png")
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
    await asyncio.sleep(5.0)
    # 逐句推进，**每次按键前先截图判态**：回到标题（logo 区贴近任一期望图）就停，绝不把多余的
    # CIRCLE 按进主菜单（会进 Story 模式——finale_full.py 固定 350 次的写法就是这样跑偏的，
    # 谢幕章实际约 160 句）。全黑帧（章内淡出 / 结尾 5 秒淡出）不按键只等待——章内淡出后都是
    # 自动切场，不需要按键；结尾淡出后接 autoSystemSave 与主菜单白闪。连续多帧全黑（fin-0 的
    # 黑屏纯文字段不会全黑到 99.8%，但留个防呆）就照按一次。
    presses = black_run = 0
    while presses < 400:
        img = await snap_retry(cli, OUT / "_cur.png")
        if is_title(img, expect):
            break
        if is_black(img) and black_run < 5:
            black_run += 1
            await asyncio.sleep(4.0)
            continue
        black_run = 0
        await cli.buttons_press("circle", duration=3)
        presses += 1
        await asyncio.sleep(2.2)
        if presses % 25 == 0:
            (OUT / "_cur.png").rename(OUT / f"p{presses:03d}.png")
    else:
        sys.exit("按了 400 次仍未回到标题——谢幕章没跑完或标题判态失效")
    print(f"谢幕章跑完：CIRCLE {presses} 次后回到标题", flush=True)


async def run():
    expect = expected_logos()
    backup = OUT / "system_backup"
    if SYSTEM_SAVE.exists():
        shutil.copytree(SYSTEM_SAVE, backup)
    verdict = {}
    errors = 0
    try:
        async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
            await wait_game(cli, 15)
            verdict["before_ja"] = classify(await snap_retry(cli, OUT / "00_title_before.png"), expect, "00") == "ja"
            await play_finale(cli, expect)
            ends = []
            for j in range(3):
                await asyncio.sleep(4.0)
                ends.append(classify(await snap_retry(cli, OUT / f"end{j}.png"), expect, f"end{j}"))
            verdict["after_zh"] = ends[-1] == "zh"
            errors += report_errors(cli)
        async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
            await wait_game(cli, 15)
            verdict["reboot_zh"] = classify(await snap_retry(cli, OUT / "10_title_reboot.png"), expect, "10") == "zh"
            errors += report_errors(cli)
    finally:
        if backup.exists() and not KEEP_SAVE:
            shutil.rmtree(SYSTEM_SAVE, ignore_errors=True)
            shutil.copytree(backup, SYSTEM_SAVE)
            print("已恢复跑前的 NPJH50279SYSTEM（--keep-save 可保留）", flush=True)
    verdict["errors"] = errors
    print(f"判定: {verdict}", flush=True)
    if not (verdict.get("before_ja") and verdict.get("after_zh") and verdict.get("reboot_zh")):
        sys.exit(1)


asyncio.run(run())
