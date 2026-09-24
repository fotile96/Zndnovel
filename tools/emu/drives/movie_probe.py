#!/usr/bin/env -S uv run --with numpy python
"""影片音画探针：开 DumpAudio → 引导「开机循环播影片」的测试盘 → 每 dt 秒断 CPU 截 fb0/fb1 并记下录音文件长度
（=模拟时间）→ 与盘上那份影片的画面/音轨比对 → movielab.verdict 判 PASS/FAIL（退出码 0/1）。

前置：build_disc.py --profile test --mode movie [--movie ed --skippable] [--ios]
    uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 1 --movie op --seconds 225 --disc build/test/game_ios
    uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp new --movie ed --seconds 70 --check-dectop --disc build/test/game_ios
--ppsspp 1204 走 tools/emu/legacy.py（ini 开调试器，~/ppsspp-1204，SNDL_PPSSPP_1204 覆盖）；new 用
~/ppsspp-new（开发版 ≥ v1.20.4-1841，LLE 真 libmp4；SNDL_PPSSPP_NEW 覆盖）——launcher 缺省的 ~/ppsspp 基线
（1ee9168）放不出影片，不能当 new 用。
--check-dectop：ini 设 AutoRun=False 开机即停，在 VA 0xB4F4（sceMpegCreate 调用点；$a6 在 0xB4DC 已赋好，
延迟槽只改 a0）读 $a6（PPSSPP 寄存器名 t2）：1.20.x HLE 应为伪值 0x10000000（iOS 层条件包装据此传假
ringbuffer），新版/实机应 ≠ 0x10000000（包装原样传 NULL）；不符即 FAIL。ini 改动一律 try/finally 还原。
参照媒体取盘上那份影片，所以 iOS 盘对照的是 44.1k 版本身。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO, TEST_GAME, Emulator, session, wait_game  # noqa: E402

from tools.emu import legacy, movielab  # noqa: E402

INI = Path.home() / ".config/ppsspp/PSP/SYSTEM/ppsspp.ini"
AUDIO_DIR = Path.home() / ".config/ppsspp/PSP/AUDIO"
NEW_APP = Path(os.environ.get("SNDL_PPSSPP_NEW",
                              Path.home() / "ppsspp-new/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL"))
BASE = 0x08804000
CREATE_CALL = 0xB4F4
HLE_DECTOP = 0x10000000


def _ini_set(pairs: dict[str, str]) -> str:
    orig = INI.read_text(encoding="utf-8")
    t = orig
    for k, v in pairs.items():
        t, n = re.subn(rf"^{k} = .*$", f"{k} = {v}", t, flags=re.M)
        if n != 1:
            sys.exit(f"ppsspp.ini 里找不到唯一的 {k}")
    INI.write_text(t, encoding="utf-8")
    return orig


def _movie_file(disc: Path, movie: str, work: Path) -> Path:
    if disc.is_dir():
        return disc / "PSP_GAME" / "USRDIR" / "movie" / f"{movie}.mp4"
    from tools.umdiso import SECTOR, Iso
    dst = work / f"{movie}.mp4"
    with Iso(str(disc)) as iso:
        rec = iso.find(f"/PSP_GAME/USRDIR/movie/{movie}.mp4")
        iso.f.seek(rec.lba * SECTOR)
        dst.write_bytes(iso.f.read(rec.size))
    return dst


def _wav_mono(p: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(p)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    return a.reshape(-1, ch).mean(axis=1), sr


def _ref(mp4: Path, work: Path) -> tuple[np.ndarray, np.ndarray, int]:
    raw, wav = work / "ref.raw", work / "ref.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", "scale=48:27:flags=area,format=gray",
                    "-f", "rawvideo", str(raw)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vn", "-ac", "2", "-ar", "44100",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    gray = np.fromfile(raw, dtype=np.uint8).reshape(-1, 27, 48).astype(np.float32)
    audio, sr = _wav_mono(wav)
    return gray, audio, sr


async def _capture(cli, out: Path, seconds: float, dt: float, before: set[Path], dectop: bool) -> tuple[list, int | None]:
    await wait_game(cli, 0.2)
    a6 = None
    if dectop:
        await cli.bp_add(BASE + CREATE_CALL)
        mark = cli.seq_mark()
        await cli.resume()
        await cli.wait_broadcast("cpu.stepping", after_seq=mark, timeout=60)
        a6 = (await cli.request("cpu.getReg", name="t2"))["uintValue"]
        print(f"sceMpegCreate 调用点 $a6 = {a6:#x}" +
              ("（1.20.x HLE 伪值：条件包装会传假 ringbuffer）" if a6 == HLE_DECTOP else "（走原样 NULL 分支）"),
              flush=True)
        await cli.bp_remove(BASE + CREATE_CALL)
        await cli.resume()
    caps, t0, i = [], time.monotonic(), 0
    while time.monotonic() - t0 < seconds:
        await cli.break_cpu()
        dumps = sorted((p for p in AUDIO_DIR.glob("*.wav") if p not in before), key=lambda p: p.stat().st_mtime)
        size = dumps[-1].stat().st_size if dumps else 0
        for name, addr in (("fb0", cli.VRAM_FB0), ("fb1", cli.VRAM_FB1)):
            (await cli.vram_screenshot(addr)).save(out / f"c{i:03d}_{name}.png")
        await cli.resume()
        caps.append({"i": i, "wall": time.monotonic() - t0, "dump_bytes": size})
        i += 1
        await asyncio.sleep(dt)
    return caps, a6


def _analyze(out: Path, caps: list[dict], gray: np.ndarray, ref: np.ndarray, sr: int) -> dict:
    dump, dsr = _wav_mono(out / "dump.wav")
    if dsr != sr:
        sys.exit(f"录音采样率 {dsr} ≠ 参照 {sr}")
    hop = 882                                                 # 20 ms @ 44.1k
    env = lambda a: np.log(np.sqrt((a[: len(a) // hop * hop].reshape(-1, hop) ** 2).mean(axis=1)) + 1)  # noqa: E731
    de, re_ = env(dump), env(ref)
    L = min(len(re_), 1000)                                   # 参照前 20 s 的包络
    if len(de) < L + 250:
        sys.exit(f"录音只有 {len(dump) / sr:.1f} s，不够做首次对齐（--seconds 调大）")
    q = (re_[:L] - re_[:L].mean()) / (re_[:L].std() + 1e-9)
    scores = [float(((de[o:o + L] - de[o:o + L].mean()) / (de[o:o + L].std() + 1e-9) * q).mean())
              for o in range(0, min(len(de) - L, 3000))]
    approx = int(np.argmax(scores)) * hop / sr
    rows = movielab.local_align(dump, ref, sr, approx_s=approx)
    off = rows[0][1] if rows else approx
    dur = len(ref) / sr
    av = []
    for c in caps:
        cands = []
        for fb in ("fb0", "fb1"):                              # 两块缓冲都比，取与参照最像的那块（实验同法）
            g = np.asarray(Image.open(out / f"c{c['i']:03d}_{fb}.png").convert("L").resize((48, 27), Image.BOX),
                           dtype=np.float32)
            if g.max() >= 1:
                cands.append(g)
        if not cands:
            continue
        idx, mse, plateau = min(movielab.match_frames(cands, gray), key=lambda r: r[1])
        t_audio = (c["dump_bytes"] - 44) / (sr * 4) - off
        if plateau <= 6 and mse < 60 and 0 < t_audio < dur:
            av.append(idx / movielab.FPS - t_audio)
    v = movielab.verdict(rows, av)
    v.update({"audio_offset_s": off, "chunks": len(rows), "frames_judged": len(av),
              "av_median_s": float(np.median(av)) if av else None,
              "av_range_s": [float(min(av)), float(max(av))] if av else None,
              "corr_min": min((c for _, _, c in rows), default=None),
              "offset_span_s": (max(o for _, o, _ in rows) - min(o for _, o, _ in rows)) if rows else None})
    return v


async def _run(a: argparse.Namespace) -> int:
    out = a.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    before = set(AUDIO_DIR.glob("*.wav")) if AUDIO_DIR.exists() else set()
    pairs = {"DumpAudio": "True"}
    if a.check_dectop:
        pairs["AutoRun"] = "False"
    orig = _ini_set(pairs)
    try:
        if a.ppsspp == "1204":
            ctx = legacy.session(a.disc, core=a.core)
        else:
            if not NEW_APP.exists():
                sys.exit(f"找不到新版 PPSSPP：{NEW_APP}（SNDL_PPSSPP_NEW 可覆盖）")
            ctx = session(lambda: Emulator(NEW_APP, ["--graphics=software", str(a.disc.resolve())], tag="app"))
        async with ctx as tup:
            caps, a6 = await _capture(tup[1], out, a.seconds, a.dt, before, a.check_dectop)
    finally:
        INI.write_text(orig, encoding="utf-8")
    dumps = sorted((p for p in AUDIO_DIR.glob("*.wav") if p not in before), key=lambda p: p.stat().st_mtime)
    if not dumps:
        sys.exit("没有新的录音落盘（DumpAudio 未生效？）")
    shutil.copy(dumps[-1], out / "dump.wav")
    for p in dumps:
        p.unlink()
    (out / "captures.json").write_text(json.dumps(caps, indent=1))
    with tempfile.TemporaryDirectory() as td:
        gray, ref, sr = _ref(_movie_file(a.disc, a.movie, Path(td)), Path(td))
    v = _analyze(out, caps, gray, ref, sr)
    if a.check_dectop:
        v["dectop"] = f"{a6:#x}"
        v["dectop_ok"] = (a6 == HLE_DECTOP) if a.ppsspp == "1204" else (a6 != HLE_DECTOP)
        v["pass"] = v["pass"] and v["dectop_ok"]
    (out / "verdict.json").write_text(json.dumps(v, indent=1, ensure_ascii=False))
    print(json.dumps(v, ensure_ascii=False, indent=1))
    print("PASS" if v["pass"] else "FAIL")
    return 0 if v["pass"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=Path, default=TEST_GAME)
    ap.add_argument("--ppsspp", choices=["new", "1204"], default="new")
    ap.add_argument("--core", type=int, default=None, help="仅 1204：CPUCore（1 JIT / 2 IR 解释器）")
    ap.add_argument("--movie", choices=["op", "ed"], default="op")
    ap.add_argument("--seconds", type=float, default=225)
    ap.add_argument("--dt", type=float, default=4.0)
    ap.add_argument("--check-dectop", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "emu" / "drives" / "movie_probe")
    a = ap.parse_args()
    if not a.disc.exists():
        sys.exit(f"盘不存在：{a.disc}（先跑 build_disc.py --profile test --mode movie [--ios]）")
    return asyncio.run(_run(a))


if __name__ == "__main__":
    sys.exit(main())
