#!/usr/bin/env -S uv run python
"""音效探针：开 PPSSPP 音频落盘 → 直入场景 → 连按 SE_PRESSES 下 → 静置 → 在录音里找每个参照 SE 的
包络（互相关），报出现时刻、ncc 与录音里的声音事件表，并按 SE_REFS 的顺序判定先后。

前置：`build_disc.py --profile test --mode scene --scene fin-10`；参照 WAV 从解包的 .vag 解出：
      `ffmpeg -i build/databin/se/se_51.vag build/se_probe/se_51.wav`（databin.py unpack 之后）。缺省引导 test 盘。
环境变量：SE_REFS（逗号分隔的参照 WAV，缺省 build/se_probe/se_101.wav,build/se_probe/se_51.wav）、
SE_PRESSES（缺省 14：fin-0 第 14 句「……」按掉之后即翻页与按笔）、SE_SECONDS（按完后静置秒数，缺省 8）、
SE_SLEEP（每次按键间隔秒，缺省 2.2）。
判定：每个参照 ncc ≥ 0.8，且按 SE_REFS 顺序时刻递增、都落在录音最后 SE_SECONDS+3 秒内（即最后一次按键之后）。
ppsspp.ini 的 DumpAudio 用 try/finally 还原；录音在 ~/.config/ppsspp/PSP/AUDIO/，副本存到 --out。
"""
import asyncio
import os
import re
import shutil
import sys
from pathlib import Path

from _common import REPO, TEST_GAME, Emulator, parse, report_errors, session, snap, wait_game

sys.path.insert(0, str(REPO))
from tools import at3p  # noqa: E402

DISC, OUT = parse(TEST_GAME, "se_probe", __doc__)
REFS = [Path(p) if Path(p).is_absolute() else REPO / p
        for p in os.environ.get("SE_REFS", "build/se_probe/se_101.wav,build/se_probe/se_51.wav").split(",")]
PRESSES = int(os.environ.get("SE_PRESSES", "14"))
SECONDS = float(os.environ.get("SE_SECONDS", "8"))
SLEEP = float(os.environ.get("SE_SLEEP", "2.2"))
INI = Path.home() / ".config" / "ppsspp" / "PSP" / "SYSTEM" / "ppsspp.ini"
AUDIO_DIR = Path.home() / ".config" / "ppsspp" / "PSP" / "AUDIO"
FRAME = 0.05  # at3p._envelope 的 50 ms 窗


def set_dump_audio(on: bool) -> str:
    text = INI.read_text(encoding="utf-8")
    new, n = re.subn(r"^DumpAudio = \w+$", f"DumpAudio = {'True' if on else 'False'}", text, flags=re.M)
    if n != 1:
        sys.exit("ppsspp.ini 里找不到唯一的 DumpAudio 行")
    INI.write_text(new, encoding="utf-8")
    return text


def events(env: list[float], thr_ratio: float = 0.05) -> list[tuple[float, float]]:
    """录音里的声音事件：连续高于 max*thr_ratio 的帧段 → (起始秒, 时长秒)。"""
    thr = max(env) * thr_ratio if env else 0
    out, start = [], None
    for i, v in enumerate(env + [0.0]):
        if v > thr and start is None:
            start = i
        elif v <= thr and start is not None:
            out.append((start * FRAME, (i - start) * FRAME))
            start = None
    return out


def analyze(dump: Path, refs: list[Path]) -> dict:
    ed = at3p._envelope(dump)
    res = {"dump_s": len(ed) * FRAME, "events": events(ed), "refs": {}}
    for ref in refs:
        es = at3p._envelope(ref)
        if len(es) < 4 or len(ed) <= len(es):
            res["refs"][ref.stem] = {"error": "参照太短或录音太短"}
            continue
        cands = [(o * FRAME, at3p.ncc(ed[o:o + len(es)], es)) for o in range(0, len(ed) - len(es))]
        top = sorted(cands, key=lambda t: -t[1])[:3]
        res["refs"][ref.stem] = {"ref_s": len(es) * FRAME, "at_s": top[0][0], "ncc": top[0][1], "top3": top}
    return res


async def run() -> dict:
    async with session(lambda: Emulator.app(DISC, graphics="software")) as (emu, cli):
        await wait_game(cli, 14)
        await snap(cli, OUT / "k_start.png")
        for i in range(PRESSES):
            await cli.buttons_press("circle", duration=3)
            await asyncio.sleep(SLEEP)
        await snap(cli, OUT / "k_pressed.png")
        await asyncio.sleep(SECONDS)
        await snap(cli, OUT / "k_end.png")
        report_errors(cli)
        return {}


for r in REFS:
    if not r.exists():
        sys.exit(f"缺参照 {r}（先 ffmpeg 从 build/databin/se/*.vag 解出）")
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
res.update(analyze(dump, REFS))
print("录音时长 %.1f s；声音事件（起始 s, 时长 s）：" % res["dump_s"])
for t, d in res["events"]:
    print(f"   {t:7.2f}  {d:5.2f}")
tail_from = res["dump_s"] - (SECONDS + 3)
ok, last = True, -1.0
for r in REFS:
    info = res["refs"][r.stem]
    print(f"{r.stem}: {info}")
    good = "error" not in info and info["ncc"] >= 0.8 and info["at_s"] > last and info["at_s"] >= tail_from
    ok &= good
    last = info.get("at_s", last)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
