#!/usr/bin/env -S uv run python
"""开机五卡顺序：日本一 → Text. → 免责/版权 → 汉化组署名与献词（IPL03，新增第五卡）→ 自动存档告知。

前置：`build_disc.py --profile test --mode mainmenu --no-fast-boot`——不带 --no-fast-boot 的
test 盘被 strip-ipl 层剥掉整段开场（含本卡），什么也验不到。也可 `--disc build/dist/game_zh.iso`
验发布盘本体（期望图改从 build/release/stage 取）。
流程：引擎进入运行态起每约 0.5 s 直读一帧 VRAM，最长 SAMPLE_SECONDS 秒；每帧与五张期望卡
算 MSE（全部取本盘 stage 里的 gim 解码——sys_1_a/autosave 是中文面、IPL03 含量化损耗；缺则退到
png/sysgim 原图），最小者 < MSE_HIT 即判为该卡的满亮帧（淡入/淡出中的帧不会命中）。命中帧存盘
（文件名带卡名与 MSE），其余每 10 帧留一帧。自动存档卡命中过后再多采 4 s 即停。
判据：按首次命中顺序得到的卡序列 == 期望五序；IPL03 至少命中 2 帧（停留约 3 s）；
ERROR 0 或仅 ILLEGAL_THID=sceKernelWaitThreadEnd 这条 HLE 噪声。
"""
import asyncio
import sys
import time

from _common import REPO, TEST_GAME, Emulator, parse, report_errors, session, wait_game

DISC, OUT = parse(TEST_GAME, "boot_dedication", __doc__)
sys.path.insert(0, str(REPO))
from PIL import Image, ImageChops  # noqa: E402

from tools.gimcodec import Gim  # noqa: E402

ORDER = ["IPL01", "IPL02", "sys_1_a", "IPL03", "autosave"]
MSE_HIT = 60.0          # 满亮帧 ≈0；半亮帧与全黑帧对这些黑底卡也只有几百，阈值取远低于它
SAMPLE_SECONDS = 70
TAIL_SECONDS = 4.0


def profile_of() -> str:
    parts = DISC.resolve().parts
    return "test" if "test" in parts else "release"


def expected() -> dict[str, Image.Image]:
    prof = profile_of()
    out = {}
    for name in ORDER:
        for cand in (REPO / "build" / prof / "stage" / "sysgim" / f"{name}.gim",
                     REPO / "build" / prof / "members" / "sysgim" / f"{name}.gim"):
            if cand.exists():
                out[name] = Gim(cand.read_bytes()).to_pil().convert("RGB")
                break
        else:
            png = REPO / "png" / "sysgim" / f"{name}.png"
            if not png.exists():
                sys.exit(f"期望图缺失：{name}（stage/members 与 png/sysgim 都没有）")
            out[name] = Image.open(png).convert("RGB")
    return out


def mse(a: Image.Image, b: Image.Image) -> float:
    """RGB 均方误差，走直方图（C 级），每帧五张不到 10 ms。"""
    h = ImageChops.difference(a, b).histogram()
    n = a.size[0] * a.size[1] * 3
    return sum(i * i * h[c * 256 + i] for c in range(3) for i in range(256)) / n


async def grab(cli) -> Image.Image:
    await cli.break_cpu()
    img = await cli.vram_screenshot()
    await cli.resume()
    return img.convert("RGB")


async def run():
    exp = expected()
    seq, hits, i = [], {n: 0 for n in ORDER}, 0
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 0)
        t0 = time.monotonic()
        done_at = None
        while time.monotonic() - t0 < SAMPLE_SECONDS:
            frame = await grab(cli)
            scores = {n: mse(frame, exp[n]) for n in ORDER}
            best = min(scores, key=scores.get)
            t = time.monotonic() - t0
            if scores[best] < MSE_HIT:
                hits[best] += 1
                if not seq or seq[-1] != best:
                    seq.append(best)
                    print(f"{t:5.1f}s  帧 {i:03d}  {best}  MSE {scores[best]:.1f}", flush=True)
                frame.save(OUT / f"{i:03d}_{best}_{scores[best]:.0f}.png")
                if best == ORDER[-1] and done_at is None:
                    done_at = time.monotonic()
            elif i % 10 == 0:
                frame.save(OUT / f"{i:03d}_.png")
            i += 1
            if done_at is not None and time.monotonic() - done_at > TAIL_SECONDS:
                break
            await asyncio.sleep(0.3)
        n_err = report_errors(cli)
    verdict = {"order_ok": seq == ORDER, "ipl03_held": hits["IPL03"] >= 2,
               "seq": seq, "hits": hits, "frames": i, "errors": n_err}
    print("判定:", verdict, flush=True)
    return verdict["order_ok"] and verdict["ipl03_held"]


sys.exit(0 if asyncio.run(run()) else 1)
