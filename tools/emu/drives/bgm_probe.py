#!/usr/bin/env -S uv run python
"""新曲探针：开 PPSSPP 音频落盘 → 直入场景 → 连按几下进入起播点 → 静置 → 与源 PCM 做包络互相关。

前置：`build_disc.py --profile test --mode scene --scene fin-30`（含 sound 阶段），
      `build/sound/work/<name>.44k.wav`（at3p encode 留下的 44.1k 参照）。缺省引导 test 盘。
环境变量：BGM_REF（参照 WAV，缺省 build/sound/work/bgm_fin_1.44k.wav）、BGM_PRESSES（起播前按键次数，
缺省 0：fin-30 一进场就起播）、BGM_SECONDS（静置秒数，缺省 230：整曲 196 s + 回绕验证）。
判定：ncc ≥ 0.9、回绕间隔 ≈ 曲长（整曲循环）；ERROR 日志无 E[Atrac]。
ppsspp.ini 的 DumpAudio 用 try/finally 还原；录音在 ~/.config/ppsspp/PSP/AUDIO/，副本存到 --out。
"""
import asyncio
import os
import re
import shutil
import sys
import time
import wave
from pathlib import Path

from _common import REPO, TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

sys.path.insert(0, str(REPO))
from tools import at3p  # noqa: E402

DISC, OUT = parse(TEST_GAME, "bgm_probe", __doc__)
REF = Path(os.environ.get("BGM_REF", REPO / "build" / "sound" / "work" / "bgm_fin_1.44k.wav"))
PRESSES = int(os.environ.get("BGM_PRESSES", "0"))
SECONDS = float(os.environ.get("BGM_SECONDS", "230"))
INI = Path.home() / ".config" / "ppsspp" / "PSP" / "SYSTEM" / "ppsspp.ini"
AUDIO_DIR = Path.home() / ".config" / "ppsspp" / "PSP" / "AUDIO"


def set_dump_audio(on: bool) -> str:
    text = INI.read_text(encoding="utf-8")
    new, n = re.subn(r"^DumpAudio = \w+$", f"DumpAudio = {'True' if on else 'False'}", text, flags=re.M)
    if n != 1:
        sys.exit("ppsspp.ini 里找不到唯一的 DumpAudio 行")
    INI.write_text(new, encoding="utf-8")
    return text


def analyze(dump: Path, ref: Path) -> dict:
    ed, es = at3p._envelope(dump), at3p._envelope(ref)
    head = es[:240]                                   # 参照的前 12 s
    if len(ed) <= 260:
        return {"error": "录音太短"}
    cands = [(o * 0.05, at3p.ncc(ed[o:o + 240], head)) for o in range(0, len(ed) - 240)]
    t1, c1 = max(cands, key=lambda t: t[1])
    with wave.open(str(ref), "rb") as w:
        track = w.getnframes() / w.getframerate()
    later = [c for c in cands if c[0] > t1 + track - 3]
    wrap = max(later, key=lambda t: t[1]) if later else None
    o = round(t1 / 0.05)
    L = min(len(es), len(ed) - o)
    return {"first_align_s": t1, "first_ncc": c1, "track_s": track,
            "wrap_s": wrap and wrap[0], "wrap_ncc": wrap and wrap[1],
            "wrap_delta_s": wrap and (wrap[0] - t1),
            "full_pass_ncc": at3p.ncc(ed[o:o + L], es[:L]), "dump_s": len(ed) * 0.05}


async def run() -> dict:
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 12)
        t0 = time.time()
        for i in range(PRESSES):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(2.2)
        await snap(cli, OUT / "k_start.png")
        (OUT / "t_start.txt").write_text(f"{time.time() - t0:.2f}")
        await asyncio.sleep(SECONDS)
        await snap(cli, OUT / "k_end.png")
        errors = [d.get("message") for d in cli.drain_broadcasts("log") if d.get("level") == 2]
        atrac = [e for e in errors if e and "trac" in e]
        report_errors(cli)
        return {"atrac_errors": atrac}


if not REF.exists():
    sys.exit(f"缺参照 {REF}（先 at3p.py encode）")
before = {p: p.stat().st_mtime for p in AUDIO_DIR.glob("*.wav")} if AUDIO_DIR.exists() else {}
saved = set_dump_audio(True)
try:
    res = asyncio.run(run())
finally:
    INI.write_text(saved, encoding="utf-8")
dumps = sorted((p for p in AUDIO_DIR.glob("*.wav") if p not in before), key=lambda p: p.stat().st_mtime)
if not dumps:
    sys.exit("没有新的录音落盘（DumpAudio 未生效？）")
dump = OUT / "dump.wav"
shutil.copyfile(dumps[-1], dump)
for p in dumps:
    p.unlink()
res.update(analyze(dump, REF))
print("判定:", res)
ok = res.get("full_pass_ncc", 0) >= 0.9 and not res["atrac_errors"] and res.get("wrap_s") is not None \
    and abs(res["wrap_delta_s"] - res["track_s"]) < 1.0
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
