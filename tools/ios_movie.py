#!/usr/bin/env python3
"""iOS 变体的 op/ed：音轨重采样 AAC-LC 44.1 kHz，视频流原样拷贝。

为什么（docs/ops/movie-playback-ppsspp-2026-09-24.md V1）：PPSSPP 1.20.x 的混音器对 48 kHz vaudio 做 SRC
时按 128 值一块弹出 139 值（截断且为奇数）→ 慢 0.229% 且每 1.45 ms 左右声道错位＝破音。游戏按音轨采样率开
vaudio（全局 IDA 0x39CE3C），音轨是 44.1k 时不走 SRC。产物指纹钉在 layers/manifest.toml [ios.movies]；
FFmpeg 升级导致字节变化时硬失败，先用 tools/emu/drives/movie_probe.py 在 1.20.4 上复测再更新指纹。

用法：uv run python tools/ios_movie.py build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

MOVIES = {"op.mp4": "/PSP_GAME/USRDIR/movie/op.mp4", "ed.mp4": "/PSP_GAME/USRDIR/movie/ed.mp4"}
FFMPEG_ARGS = ["-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-ar", "44100",
               "-ac", "2", "-b:a", "160k", "-brand", "MSNV", "-fflags", "+bitexact",
               "-flags:a", "+bitexact", "-f", "mp4"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ffmpeg_version() -> str:
    return subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True,
                          check=True).stdout.splitlines()[0]


def _extract(iso: Path, inner: str, dst: Path) -> None:
    from tools.umdiso import SECTOR, Iso
    with Iso(str(iso)) as f:
        rec = f.find(inner)
        f.f.seek(rec.lba * SECTOR)
        dst.write_bytes(f.f.read(rec.size))


def resample(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    *FFMPEG_ARGS, str(dst)], check=True)


def probe(mp4: Path) -> dict:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(mp4)],
                                  capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    return {"video": f"{v['codec_name']} {v['width']}x{v['height']}", "audio_codec": a["codec_name"],
            "audio_rate": int(a["sample_rate"]), "channels": int(a["channels"])}


def video_md5(mp4: Path) -> str:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-map", "0:v:0", "-c", "copy",
                          "-f", "md5", "-"], capture_output=True, text=True, check=True).stdout
    return out.strip()


def build(out_dir: Path, pins: dict[str, str], orig_iso: Path) -> dict[str, Path]:
    """从原盘抽 op/ed → 重采样 → 核验（44.1k AAC 立体声、视频流与原片逐包相同）→ 核对 pins 指纹。
    产物已存在且指纹相符则直接复用。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, inner in MOVIES.items():
        dst = out_dir / name
        if dst.exists() and _sha(dst) == pins[name]:
            res[name] = dst
            continue
        src = out_dir / f"{name}.orig"
        _extract(orig_iso, inner, src)
        resample(src, dst)
        p = probe(dst)
        if (p["audio_rate"], p["audio_codec"], p["channels"]) != (44100, "aac", 2):
            raise SystemExit(f"{name}: 音轨不是 44.1k AAC 立体声：{p}")
        if video_md5(dst) != video_md5(src):
            raise SystemExit(f"{name}: 视频流与原片不一致（应为原样拷贝）")
        got = _sha(dst)
        if got != pins[name]:
            raise SystemExit(f"{name}: 产物 sha256 {got} 与登记 {pins[name]} 不符（{ffmpeg_version()}）——"
                             "FFmpeg 变了就先在 PPSSPP 1.20.4 上跑 movie_probe 复测，再更新 manifest [ios.movies]")
        src.unlink()
        res[name] = dst
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--out", type=Path, default=REPO / "build" / "ios" / "movie")
    a = ap.parse_args(argv)
    from tools import layers
    pins = layers.load_manifest()["ios"]["movies"]
    for k, v in build(a.out, pins, REPO / "assets" / "orig.iso").items():
        print(f"{k} → {v}（{_sha(v)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
