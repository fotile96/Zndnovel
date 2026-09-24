### Task 6: 驾驶工具——PPSSPP 1.20.x 会话、音画分析、`movie_probe.py`

**Files:**
- Create: `tools/emu/legacy.py`（移植 `build/movie_debug/ppsspp1204.py`）
- Create: `tools/emu/movielab.py`（移植 `movie_sync_analyze.py` 与 `audio_local_align.py` 的核心为函数）
- Create: `tools/emu/drives/movie_probe.py`（移植 `movie_sync_probe.py`，分析改调 movielab）
- Test: `tests/test_movielab.py`
- Modify: `tools/emu/drives/README.md`

**Interfaces:**
- Produces:
  - `legacy.session(disc: Path, *, app: Path = ~/ppsspp-1204/…/PPSSPPSDL, port=45699, core: int | None = None, start_break=False)` → 异步上下文，产出 `(proc, EmuClient, log_path)`；进入时改 ini（`RemoteDebuggerOnStartup=True`、`RemoteISOPort`、`GraphicsBackend=0 (OPENGL)`、`SoftwareRenderer=True`、可选 `CPUCore`、`AutoRun=False`），退出时原样写回。
  - `movielab.local_align(dump: np.ndarray, ref: np.ndarray, sr: int, approx_s: float, step_s=5.0) -> list[tuple[float, float, float]]`（ref 时刻、偏移秒、相关系数）
  - `movielab.match_frames(frames: list[np.ndarray], ref_gray: np.ndarray) -> list[tuple[int, float, int]]`（帧号、mse、平台宽）
  - `movielab.verdict(align_rows, av_diffs) -> dict`：`{"audio_ok": 相关≥0.99 的段 ≥90%, "drift_ok": 偏移跨度 < 0.05 s, "av_ok": |中位音画差| < 0.2 s, "pass": 三者皆真}`

- [ ] **Step 1: 写失败测试** `tests/test_movielab.py`

```python
"""tools/emu/movielab.py：影片音画探针的纯分析部分（合成信号）。"""
import pytest

np = pytest.importorskip("numpy")
from tools.emu import movielab as ml  # noqa: E402


def test_local_align_recovers_constant_offset():
    sr = 8000
    rng = np.random.default_rng(1)
    ref = rng.standard_normal(sr * 30).astype(np.float32) * 1000
    dump = np.concatenate([np.zeros(int(1.25 * sr), np.float32), ref])
    rows = ml.local_align(dump, ref, sr, approx_s=1.2, step_s=5.0)
    assert all(abs(o - 1.25) < 1e-3 and c > 0.99 for _, o, c in rows)


def test_local_align_stops_where_dump_ends():
    sr = 8000
    rng = np.random.default_rng(2)
    ref = rng.standard_normal(sr * 60).astype(np.float32) * 1000
    dump = np.concatenate([np.zeros(sr, np.float32), ref[: sr * 20]])     # 只录到 20 s
    rows = ml.local_align(dump, ref, sr, approx_s=1.0, step_s=5.0)
    assert rows and all(c > 0.99 for _, _, c in rows) and rows[-1][0] < 20


def test_verdict_flags_drift_and_distortion():
    good = [(t, 2.0, 0.999) for t in range(0, 200, 5)]
    drift = [(t, 2.0 + t * 0.0023, 0.999) for t in range(0, 200, 5)]
    bad = [(t, 2.0, 0.5) for t in range(0, 200, 5)]
    assert ml.verdict(good, [-0.06] * 40)["pass"]
    assert not ml.verdict(drift, [-0.06] * 40)["drift_ok"]
    assert not ml.verdict(bad, [-0.06] * 40)["audio_ok"]
    assert not ml.verdict(good, [-0.5] * 40)["av_ok"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --with numpy pytest tests/test_movielab.py -v`
Expected: FAIL（`No module named 'tools.emu.movielab'`）。

- [ ] **Step 3: 实现 `tools/emu/movielab.py`**

```python
"""影片音画探针的分析部分（需要 numpy：uv run --with numpy …）。

录音与参照音轨逐 step_s 秒取 1 s 片段就近互相关 → (ref 时刻, 偏移, 相关)；截帧与参照影片 48×27 灰度逐帧
MSE 匹配 → 片中时刻；两者相减得音画差。判定阈值取 2026-09-24 实测：健康时分段相关 ≥0.999、偏移跨度 <2 ms、
音画差中位 −0.05…−0.10 s；1.20.4 的 48k 破音是相关 0.3–0.76 + 每分钟漂 0.14 s。
"""
from __future__ import annotations

import numpy as np

FPS = 30000 / 1001


def _best(seg: np.ndarray, region: np.ndarray) -> tuple[int, float]:
    n, m = len(seg), len(region) - len(seg)
    if m <= 0:
        return 0, 0.0
    fs = 1 << int(np.ceil(np.log2(len(region) + n)))
    c = np.fft.irfft(np.fft.rfft(region, fs) * np.conj(np.fft.rfft(seg, fs)), fs)[:m]
    k = int(np.argmax(c))
    x = region[k:k + n]
    cc = float(np.dot(x - x.mean(), seg - seg.mean()) / (np.std(x) * np.std(seg) * n + 1e-9))
    return k, cc


def local_align(dump: np.ndarray, ref: np.ndarray, sr: int, approx_s: float,
                step_s: float = 5.0) -> list[tuple[float, float, float]]:
    rows, off = [], int(approx_s * sr)
    t = 1.0
    while (t + 1) * sr <= len(ref) and int(t * sr) + off + int(1.5 * sr) <= len(dump):   # 录音覆盖不到就停
        a = int(t * sr)
        seg = ref[a:a + sr]
        if np.std(seg) >= 50:
            lo = max(0, a + off - sr // 2)
            k, cc = _best(seg, dump[lo:a + off + int(1.5 * sr)])
            loc = lo + k - a
            rows.append((t, loc / sr, cc))
            off = loc
        t += step_s
    return rows


def match_frames(frames: list[np.ndarray], ref_gray: np.ndarray) -> list[tuple[int, float, int]]:
    out = []
    for g in frames:
        mse = ((ref_gray - g) ** 2).mean(axis=(1, 2))
        k = int(mse.argmin())
        out.append((k, float(mse[k]), int((mse <= mse[k] * 1.15 + 2).sum())))
    return out


def verdict(align_rows: list[tuple[float, float, float]], av_diffs: list[float]) -> dict:
    core = align_rows[:-1] if len(align_rows) > 2 else align_rows      # 末段常落在片尾/循环交界
    corr_ok = sum(1 for _, _, c in core if c >= 0.99) >= 0.9 * max(1, len(core))
    offs = [o for _, o, c in core if c >= 0.9]
    drift_ok = bool(offs) and (max(offs) - min(offs)) < 0.05
    av_ok = bool(av_diffs) and abs(float(np.median(av_diffs))) < 0.2
    return {"audio_ok": corr_ok, "drift_ok": drift_ok, "av_ok": av_ok,
            "pass": corr_ok and drift_ok and av_ok}
```

- [ ] **Step 4: 实现 `tools/emu/legacy.py` 与 `tools/emu/drives/movie_probe.py`**

`tools/emu/legacy.py`：

```python
"""PPSSPP 1.20.x（iOS 商店版同版本）的驾驶会话：该版 SDL 构建没有 --debugger= 参数，远程调试器只能由 ini 的
RemoteDebuggerOnStartup + RemoteISOPort 打开；软渲染同样经 ini。进入时改 ini、退出时原样写回。
二进制缺省 ~/ppsspp-1204/build/PPSSPPSDL.app（本机 v1.20.4 构建），SNDL_PPSSPP_1204 覆盖。"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import time
from pathlib import Path

from tools.emu.client import EmuClient

APP = Path(os.environ.get("SNDL_PPSSPP_1204",
                          Path.home() / "ppsspp-1204/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL"))
INI = Path.home() / ".config/ppsspp/PSP/SYSTEM/ppsspp.ini"
LOG_DIR = Path(__file__).resolve().parents[2] / "build" / "emu" / "logs"


def _set(text: str, key: str, val: str) -> str:
    new, n = re.subn(rf"^{key} = .*$", f"{key} = {val}", text, flags=re.M)
    if n != 1:
        raise RuntimeError(f"ppsspp.ini 里找不到唯一的 {key}")
    return new


@contextlib.asynccontextmanager
async def session(disc: Path, *, app: Path = APP, port: int = 45699, core: int | None = None,
                  start_break: bool = False, extra: dict[str, str] | None = None):
    orig = INI.read_text(encoding="utf-8")
    t = orig
    for k, v in {"RemoteDebuggerOnStartup": "True", "RemoteISOPort": str(port),
                 "GraphicsBackend": "0 (OPENGL)", "SoftwareRenderer": "True", **(extra or {})}.items():
        t = _set(t, k, v)
    if core is not None:
        t = _set(t, "CPUCore", str(core))
    if start_break:
        t = _set(t, "AutoRun", "False")
    INI.write_text(t, encoding="utf-8")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logp = LOG_DIR / f"{time.strftime('%H%M%S')}-app1204.log"
    proc = None
    try:
        with open(logp, "w") as lf:
            proc = subprocess.Popen([str(app), str(Path(disc).resolve())], stdout=lf, stderr=subprocess.STDOUT)
        cli = EmuClient(port=port)
        await cli.connect(retry_seconds=20, alive=lambda: proc.poll() is None)
        try:
            yield proc, cli, logp
        finally:
            await cli.aclose()
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(3)
        INI.write_text(orig, encoding="utf-8")
```

`tools/emu/drives/movie_probe.py`（移植自已实测的 `build/movie_debug/movie_sync_probe.py` / `movie_sync_analyze.py`；参照媒体取盘上那份影片，所以 iOS 盘对照的是 44.1k 版本身）：

```python
#!/usr/bin/env -S uv run --with numpy python
"""影片音画探针：开 DumpAudio → 引导「开机循环播影片」的测试盘 → 每 dt 秒断 CPU 截 fb0/fb1 并记下录音文件长度
（=模拟时间）→ 与盘上那份影片的画面/音轨比对 → movielab.verdict 判 PASS/FAIL（退出码 0/1）。

前置：build_disc.py --profile test --mode movie [--movie ed --skippable] [--ios]
    uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 1 --movie op --seconds 225 --disc build/test/game_ios
    uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp new --movie ed --seconds 70 --check-dectop --disc build/test/game_ios
--ppsspp 1204 走 tools/emu/legacy.py（ini 开调试器）；new 走现有 launcher（SNDL_PPSSPP_APP 指定新版二进制）。
--check-dectop：ini 设 AutoRun=False 开机即停，在 VA 0xB4F4（sceMpegCreate 调用点）读 $a6，≠0x10000000 说明
iOS 层的条件包装走原样 NULL 分支（新版/实机应如此）。ini 改动一律 try/finally 还原。
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
BASE = 0x08804000


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


def _ref(mp4: Path, work: Path) -> tuple[np.ndarray, np.ndarray, int]:
    raw, wav = work / "ref.raw", work / "ref.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", "scale=48:27:flags=area,format=gray",
                    "-f", "rawvideo", str(raw)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vn", "-ac", "2", "-ar", "44100",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    gray = np.fromfile(raw, dtype=np.uint8).reshape(-1, 27, 48).astype(np.float32)
    audio, sr = _wav_mono(wav)
    return gray, audio, sr


def _wav_mono(p: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(p)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    return a.reshape(-1, ch).mean(axis=1), sr


async def _capture(cli, out: Path, seconds: float, dt: float, before: set[Path], dectop: bool) -> list[dict]:
    await wait_game(cli, 0.2)
    if dectop:
        await cli.bp_add(BASE + 0xB4F4)
        mark = cli.seq_mark()
        await cli.resume()
        await cli.wait_broadcast("cpu.stepping", after_seq=mark, timeout=60)
        a6 = (await cli.request("cpu.getReg", name="a6"))["uintValue"]
        print(f"sceMpegCreate 调用点 $a6 = {a6:#x}" +
              ("（1.20.x HLE 伪值：条件包装会传假 ringbuffer）" if a6 == 0x10000000 else "（走原样 NULL 分支）"), flush=True)
        await cli.bp_remove(BASE + 0xB4F4)
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
    return caps


def _analyze(out: Path, caps: list[dict], gray: np.ndarray, ref: np.ndarray, sr: int) -> dict:
    dump, dsr = _wav_mono(out / "dump.wav")
    if dsr != sr:
        sys.exit(f"录音采样率 {dsr} ≠ 参照 {sr}")
    env = lambda a: np.log(np.sqrt((a[: len(a) // 882 * 882].reshape(-1, 882) ** 2).mean(axis=1)) + 1)  # noqa: E731
    de, re_ = env(dump), env(ref)
    L = min(len(re_), 1000)                                   # 参照前 20 s 的包络
    q = (re_[:L] - re_[:L].mean()) / (re_[:L].std() + 1e-9)
    scores = [float(((de[o:o + L] - de[o:o + L].mean()) / (de[o:o + L].std() + 1e-9) * q).mean())
              for o in range(0, max(1, min(len(de) - L, 3000)))]
    approx = int(np.argmax(scores)) * 882 / sr
    rows = movielab.local_align(dump, ref, sr, approx_s=approx)
    off = rows[0][1] if rows else approx
    frames = []
    for c in caps:
        best = None
        for fb in ("fb0", "fb1"):
            g = np.asarray(Image.open(out / f"c{c['i']:03d}_{fb}.png").convert("L").resize((48, 27), Image.BOX),
                           dtype=np.float32)
            if g.max() >= 1 and (best is None or g.std() > best.std()):
                best = g
        frames.append(best)
    matched = movielab.match_frames([f for f in frames if f is not None], gray)
    dur = len(ref) / sr
    av, k = [], 0
    for c, f in zip(caps, frames):
        if f is None:
            continue
        idx, mse, plateau = matched[k]
        k += 1
        t_audio = (c["dump_bytes"] - 44) / (sr * 4) - off
        if plateau <= 6 and mse < 60 and 0 < t_audio < dur:
            av.append(idx / movielab.FPS - t_audio)
    v = movielab.verdict(rows, av)
    v.update({"audio_offset_s": off, "chunks": len(rows), "frames_judged": len(av),
              "av_median_s": float(np.median(av)) if av else None,
              "corr_min": min((c for _, _, c in rows), default=None)})
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
            ctx = session(lambda: Emulator.app(a.disc, graphics="software"))
        async with ctx as tup:
            cli = tup[1]
            caps = await _capture(cli, out, a.seconds, a.dt, before, a.check_dectop)
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
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑测试**

Run: `uv run --with numpy pytest tests/test_movielab.py -v`
Expected: 3 PASS。

- [ ] **Step 6: drives/README 表格加一行**

`| movie_probe.py | 影片音画：DumpAudio + fb0/fb1 截帧 → 分段互相关/漂移/音画差 → PASS/FAIL；--ppsspp 1204 走 ini 调试器会话（tools/emu/legacy.py） | --profile test --mode movie [--movie ed --skippable] [--ios]，--disc build/test/game_ios | 分段相关 ≥0.99 占 ≥90%、偏移跨度 <0.05 s、音画差中位 <0.2 s |`

- [ ] **Step 7: 提交**

```bash
git add tools/emu/legacy.py tools/emu/movielab.py tools/emu/drives/movie_probe.py tools/emu/drives/README.md tests/test_movielab.py
git commit -m "feat: 影片音画驾驶 movie_probe（DumpAudio+截帧→分段互相关/漂移/音画差判定）与 PPSSPP 1.20.x ini 调试器会话

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

