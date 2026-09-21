#!/usr/bin/env python3
"""ATRAC3+ 曲目工具：把 PCM 编成本作 SOUND.BIN 同款 .at3、检视头部、与源对照。

引擎事实与算式全部来自 docs/superpowers/specs/2026-09-17-encore-bgm-injection-design.md
（IDA 逆向 + PPSSPP 探针）：
- 引擎只吃 AT3+（`sceAtracGetAtracID(0x1000)`），`sceAtracSetLoopNum` 在文件无 `smpl` 块时
  直接失败、线程退出——**每首曲子必须带 smpl**，不循环也要带。
- RIFF 头逐字节照原版模板（99/99 一致，`bgm_20_b` 为标准件）：
    fmt  (52 B) 0xFFFE 扩展格式：ch, 44100, avg=ceil(frame*44100/2048), blockAlign=frame, bps=0,
                cbSize=0x22, validBits=2048, chanMask=3(立体声)/4(单声道), GUID,
                version=1(LE), codecParams=BE(0x2000 | ch<<10 | (frame-8)/8) + 8 B 零
    fact (12 B) (T-d-368, d, d+184)      T=总采样数=帧数×2048，d=编码器延迟
    smpl (60 B) 标准 sampler 头(numLoops=1, samplerData=0x18) + 1 条 loop(start=S+d+184, end=T-185)
    data        帧流，744 B/帧 = 128 kbps
  固件（PPSSPP `AtracTrack.cpp::ParseWaveAT3`，照真机反写）：fmt ≥ 0x34 B、GUID 命中、
  codecParams 的声道位与 ch 一致、sr 必须 44100；12 B fact 走扩展分支，起播点=d，循环起点=S+d。
- 编码器 atracdenc（`tools/build_atracdenc.sh`，帧长改 744）只用 `--container raw` 的裸帧流，
  输入限 44.1 kHz/16 bit WAV——重采样、响度归一交给 ffmpeg。延迟 d 实测 4464（冲激法）。

用法::

    at3p.py encode  <src.wav> <out.at3> [--loop-start 秒] [--trim-end 秒] [--lufs -21] [--ch 2]
                    [--delay 4464] [--encoder 路径] [--work 目录]
    at3p.py inspect <x.at3>                 # 打印 fmt/fact/smpl，反推 (T, d, S)，校验固件规则
    at3p.py verify  <x.at3> <ref_44k.wav>   # ffmpeg 解码 → 与 encode 留下的 44.1k 中间件做包络互相关

encode 的中间件（响度归一 + 重采样后的 44.1k s16 WAV、裸帧流）留在 --work（缺省 build/sound/work/）；
verify 就拿那份 WAV 当参照。产物 sha256 打印出来，抄进 layers/manifest.toml 的 [[sound.tracks]]。
纯 stdlib；ffmpeg 与 atracdenc 走子进程。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import wave
from array import array
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUID = bytes.fromhex("bfaa23e958cb7144a119fffa01e4ce62")
SR = 44100
SAMPLES_PER_FRAME = 2048
FRAME_BYTES = 744                 # 128 kbps；原版 99 首全部如此
DEFAULT_DELAY = 4464              # atracdenc AT3+ 编码延迟（采样），744/2048 两种帧长相同
FACT_TAIL = 368
FACT_HEAD = 184
LOOP_END_MARGIN = 185
DEFAULT_LUFS = -21.0              # 原版 bgm_19_x −20.8 / bgm_20_b −22.4
PEAK_CEILING_DB = -1.0            # 峰值余量
DEFAULT_ENCODER = REPO / "build" / "atracdenc" / "build" / "src" / "atracdenc"
DEFAULT_WORK = REPO / "build" / "sound" / "work"


# ---------------------------------------------------------------- RIFF 头

def build_fmt(ch: int, frame: int = FRAME_BYTES) -> bytes:
    if ch not in (1, 2):
        raise ValueError(f"声道数只能是 1/2，得到 {ch}")
    avg = math.ceil(frame * SR / SAMPLES_PER_FRAME)
    codec_params = 0x2000 | (ch << 10) | ((frame - 8) // 8)
    fmt = struct.pack("<HHIIHH", 0xFFFE, ch, SR, avg, frame, 0)
    fmt += struct.pack("<HHI", 0x22, SAMPLES_PER_FRAME, 3 if ch == 2 else 4)
    fmt += GUID + struct.pack("<H", 1) + struct.pack(">H", codec_params) + b"\0" * 8
    assert len(fmt) == 0x34
    return fmt


def build_riff(raw: bytes, *, ch: int = 2, frame: int = FRAME_BYTES,
               delay: int = DEFAULT_DELAY, loop_start: int = 0) -> bytes:
    """裸帧流 → 完整 .at3。loop_start 以源 PCM 采样计（整曲循环为 0）。"""
    if len(raw) % frame:
        raise ValueError(f"帧流长度 {len(raw)} 不是帧长 {frame} 的整数倍")
    nframes = len(raw) // frame
    total = nframes * SAMPLES_PER_FRAME
    if loop_start < 0 or loop_start + delay + FACT_HEAD >= total - LOOP_END_MARGIN:
        raise ValueError(f"循环起点 {loop_start} 越界（曲长 {total} 采样）")
    fact = struct.pack("<III", total - delay - FACT_TAIL, delay, delay + FACT_HEAD)
    smpl = struct.pack("<9I", 0, 0, 22676, 60, 0, 0, 0, 1, 24)
    smpl += struct.pack("<6I", 0, 0, loop_start + delay + FACT_HEAD, total - LOOP_END_MARGIN, 0, 0)
    body = b"WAVE"
    for cid, payload in ((b"fmt ", build_fmt(ch, frame)), (b"fact", fact), (b"smpl", smpl), (b"data", raw)):
        body += cid + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def parse_riff(data: bytes) -> dict:
    """拆 RIFF 块；不判断对错，只把字段读出来（inspect 再按规则评）。"""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("不是 RIFF/WAVE")
    chunks: dict[str, bytes] = {}
    p = 12
    while p + 8 <= len(data):
        cid = data[p:p + 4].decode("latin1")
        size = struct.unpack_from("<I", data, p + 4)[0]
        chunks[cid] = data[p + 8:p + 8 + size]
        p += 8 + size + (size & 1)
    info: dict = {"chunks": {k: len(v) for k, v in chunks.items()}}
    fmt = chunks.get("fmt ")
    if fmt is not None and len(fmt) >= 16:
        tag, ch, sr, avg, align, bps = struct.unpack_from("<HHIIHH", fmt, 0)
        info.update(tag=tag, ch=ch, sr=sr, avg=avg, block_align=align, bps=bps, fmt_len=len(fmt))
        if len(fmt) >= 0x34:
            cb, valid, mask = struct.unpack_from("<HHI", fmt, 16)
            info.update(cb_size=cb, valid_bits=valid, chan_mask=mask, guid=fmt[24:40],
                        version=struct.unpack_from("<H", fmt, 40)[0],
                        codec_params=struct.unpack_from(">H", fmt, 42)[0])
    if "fact" in chunks and len(chunks["fact"]) >= 12:
        info["fact"] = struct.unpack_from("<III", chunks["fact"], 0)
    if "smpl" in chunks and len(chunks["smpl"]) >= 60:
        head = struct.unpack_from("<9I", chunks["smpl"], 0)
        loop = struct.unpack_from("<6I", chunks["smpl"], 36)
        info["smpl"] = {"num_loops": head[7], "sampler_data": head[8],
                        "loop_start": loop[2], "loop_end": loop[3]}
    info["data_len"] = len(chunks.get("data", b""))
    return info


def inspect(data: bytes) -> tuple[dict, list[str]]:
    """按固件规则与原版算式评头部；返回 (info + 反推的 T/d/S, 问题清单)。空清单即合格。"""
    problems: list[str] = []
    try:
        info = parse_riff(data)
    except ValueError as e:
        return {}, [str(e)]
    if "tag" not in info:
        return info, ["缺 fmt 块或 fmt 太短"]
    if info["fmt_len"] < 0x34:
        problems.append(f"fmt 块 {info['fmt_len']} B < 0x34：固件拒绝（atracdenc 原生头就是 40 B）")
        return info, problems
    if info["tag"] != 0xFFFE:
        problems.append(f"fmt tag 0x{info['tag']:04X} ≠ 0xFFFE")
    if info["guid"] != GUID:
        problems.append("GUID 不是 AT3+")
    if info["sr"] != SR:
        problems.append(f"采样率 {info['sr']} ≠ 44100：固件拒绝")
    ch, cp = info["ch"], info["codec_params"]
    if ch not in (1, 2):
        problems.append(f"声道数 {ch}")
    if (cp >> 10) & 7 != ch:
        problems.append(f"codecParams 0x{cp:04X} 的声道位 {(cp >> 10) & 7} 与 ch={ch} 不符")
    frame = ((cp & 0x3FF) + 1) * 8
    info["frame"] = frame
    if info["block_align"] != frame:
        problems.append(f"blockAlign {info['block_align']} ≠ 由 codecParams 推出的帧长 {frame}")
    if info["avg"] != math.ceil(frame * SR / SAMPLES_PER_FRAME):
        problems.append(f"avgBytesPerSec {info['avg']} ≠ ceil(帧长×44100/2048)")
    if info["data_len"] % frame:
        problems.append(f"data {info['data_len']} B 不是帧长 {frame} 的整数倍")
    total = (info["data_len"] // frame) * SAMPLES_PER_FRAME
    info["total_samples"] = total
    info["duration_s"] = total / SR
    if "fact" not in info:
        problems.append("缺 12 B fact 块")
    else:
        a, d, c = info["fact"]
        info["delay"] = d
        if a != total - d - FACT_TAIL:
            problems.append(f"fact[0]={a} ≠ T−d−368={total - d - FACT_TAIL}")
        if c != d + FACT_HEAD:
            problems.append(f"fact[2]={c} ≠ d+184={d + FACT_HEAD}")
    if "smpl" not in info:
        problems.append("缺 smpl 循环块：sceAtracSetLoopNum 会失败、线程退出（不循环的曲子也要带）")
    else:
        s = info["smpl"]
        d = info.get("delay", 0)
        if s["num_loops"] != 1 or s["sampler_data"] != 24:
            problems.append("smpl 不是单循环标准头")
        if s["loop_end"] != total - LOOP_END_MARGIN:
            problems.append(f"smpl.end={s['loop_end']} ≠ T−185={total - LOOP_END_MARGIN}")
        if s["loop_start"] < d + FACT_HEAD or s["loop_start"] >= s["loop_end"]:
            problems.append(f"smpl.start={s['loop_start']} 越界（须 ≥ d+184={d + FACT_HEAD} 且 < end）")
        info["loop_start_src"] = s["loop_start"] - d - FACT_HEAD
    return info, problems


# ---------------------------------------------------------------- 外部工具

def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


def ffmpeg_loudness(src: Path, trim_end: float | None = None) -> tuple[float, float]:
    """(综合响度 LUFS, 真峰值 dBFS)——ffmpeg ebur128 扫描。"""
    cmd = ["ffmpeg", "-nostats", "-hide_banner", "-i", str(src)]
    if trim_end is not None:
        cmd += ["-t", f"{trim_end:.6f}"]
    cmd += ["-af", "ebur128=peak=true", "-f", "null", "-"]
    out = subprocess.run(cmd, check=True, text=True, capture_output=True).stderr
    # 逐帧进度行里也有 "I: -70.0 LUFS"（门限前的初值）——只认结尾 Summary 段
    summary = out[out.rfind("Summary:"):] if "Summary:" in out else ""
    m_i = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", summary)
    m_p = re.search(r"Peak:\s+(-?[\d.]+)\s+dBFS", summary)
    if not (m_i and m_p):
        raise RuntimeError("ffmpeg ebur128 输出没有 I/Peak 汇总：\n" + out[-800:])
    return float(m_i.group(1)), float(m_p.group(1))


def gain_for(lufs: float, peak: float, target: float, ceiling: float = PEAK_CEILING_DB) -> tuple[float, bool]:
    """响度归一增益（dB）；若会顶穿峰值余量则退让，返回 (增益, 是否被峰值限制)。"""
    gain = target - lufs
    if peak + gain > ceiling:
        return ceiling - peak, True
    return gain, False


def ffmpeg_prepare(src: Path, dst: Path, *, gain_db: float, ch: int, trim_end: float | None) -> None:
    """裁尾 → 增益 → swr 高质量重采样 44.1 kHz（三角抖动）→ s16 WAV。"""
    cmd = ["ffmpeg", "-y", "-nostats", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    if trim_end is not None:
        cmd += ["-t", f"{trim_end:.6f}"]
    # swr 内建重采样器、64 抽头（缺省 32）、三角抖动——不依赖 libsoxr（homebrew ffmpeg 未编入）
    cmd += ["-af", f"volume={gain_db:.4f}dB,"
                   f"aresample={SR}:resampler=swr:filter_size=64:phase_shift=10:dither_method=triangular",
            "-ac", str(ch), "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)]
    _run(cmd)


def atracdenc_encode(wav: Path, raw: Path, encoder: Path) -> None:
    if not encoder.exists():
        raise FileNotFoundError(f"缺编码器 {encoder}：先跑 tools/build_atracdenc.sh")
    _run([str(encoder), "-e", "atrac3plus", "-i", str(wav), "-o", str(raw), "--container", "raw"])


def ffmpeg_decode(at3: Path, dst: Path) -> None:
    _run(["ffmpeg", "-y", "-nostats", "-hide_banner", "-loglevel", "error", "-i", str(at3),
          "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)])


# ---------------------------------------------------------------- 对照

def _envelope(path: Path, win: int = 2205, stride: int = 7) -> list[float]:
    """50 ms 窗 RMS 包络（抽样步进 stride）——与探针 analyze_dump 同一手法。"""
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if sw != 2:
            raise ValueError("只支持 16 bit")
        pcm = array("h")
        pcm.frombytes(w.readframes(n))
    if sys.byteorder != "little":
        pcm.byteswap()
    out = []
    for i in range(0, n - win, win):
        s = 0.0
        cnt = 0
        for j in range(i, i + win, stride):
            for c in range(ch):
                v = pcm[j * ch + c]
                s += v * v
            cnt += ch
        out.append(math.sqrt(s / cnt))
    return out


def ncc(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


def verify(at3: Path, ref_wav: Path, work: Path) -> dict:
    """解码 .at3 → 包络互相关（对齐编码延迟 d）＋ 响度对照。"""
    info, problems = inspect(at3.read_bytes())
    if problems:
        raise ValueError("头部不合规则: " + "; ".join(problems))
    work.mkdir(parents=True, exist_ok=True)
    dec = work / (at3.stem + ".decoded.wav")
    ffmpeg_decode(at3, dec)
    ea, eb = _envelope(dec), _envelope(ref_wav)
    # ffmpeg 解码不吃 fact 里的起播偏移：解码流前面多出约 d 个采样，包络按窗数对齐
    shift = round(info["delay"] / 2205)
    best = max((ncc(ea[s:], eb), s) for s in range(max(0, shift - 2), shift + 3))
    lufs_dec, peak_dec = ffmpeg_loudness(dec)
    lufs_ref, peak_ref = ffmpeg_loudness(ref_wav)
    return {"ncc": best[0], "shift_windows": best[1], "lufs_decoded": lufs_dec, "lufs_ref": lufs_ref,
            "peak_decoded": peak_dec, "peak_ref": peak_ref, "duration_s": info["duration_s"]}


# ---------------------------------------------------------------- 编码主流程

def encode(src: Path, out: Path, *, loop_start_s: float = 0.0, trim_end_s: float | None = None,
           target_lufs: float = DEFAULT_LUFS, ch: int = 2, delay: int = DEFAULT_DELAY,
           encoder: Path = DEFAULT_ENCODER, work: Path = DEFAULT_WORK) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    stem = out.stem
    lufs, peak = ffmpeg_loudness(src, trim_end_s)
    gain, limited = gain_for(lufs, peak, target_lufs)
    prepared = work / f"{stem}.44k.wav"
    ffmpeg_prepare(src, prepared, gain_db=gain, ch=ch, trim_end=trim_end_s)
    raw = work / f"{stem}.raw"
    atracdenc_encode(prepared, raw, encoder)
    blob = build_riff(raw.read_bytes(), ch=ch, delay=delay, loop_start=round(loop_start_s * SR))
    info, problems = inspect(blob)
    if problems:
        raise RuntimeError("自产头部不过规则（工具 bug）: " + "; ".join(problems))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    return {"out": str(out), "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob),
            "frames": info["data_len"] // info["frame"], "duration_s": info["duration_s"],
            "source_lufs": lufs, "source_peak_dbfs": peak, "gain_db": gain, "peak_limited": limited,
            "loop_start_s": loop_start_s, "trim_end_s": trim_end_s, "delay": delay,
            "prepared_wav": str(prepared)}


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("encode")
    e.add_argument("src", type=Path)
    e.add_argument("out", type=Path)
    e.add_argument("--loop-start", type=float, default=0.0, help="循环起点（秒，源 PCM 时基）；整曲循环 0")
    e.add_argument("--trim-end", type=float, help="只取到这一秒为止（裁掉尾巴）")
    e.add_argument("--lufs", type=float, default=DEFAULT_LUFS)
    e.add_argument("--ch", type=int, default=2, choices=(1, 2))
    e.add_argument("--delay", type=int, default=DEFAULT_DELAY)
    e.add_argument("--encoder", type=Path, default=Path(os.environ.get("SNDL_ATRACDENC", DEFAULT_ENCODER)))
    e.add_argument("--work", type=Path, default=DEFAULT_WORK)
    i = sub.add_parser("inspect")
    i.add_argument("at3", type=Path, nargs="+")
    v = sub.add_parser("verify")
    v.add_argument("at3", type=Path)
    v.add_argument("ref", type=Path, help="encode 留下的 44.1k 中间 WAV")
    v.add_argument("--work", type=Path, default=DEFAULT_WORK)
    a = ap.parse_args(argv)

    if a.cmd == "encode":
        r = encode(a.src, a.out, loop_start_s=a.loop_start, trim_end_s=a.trim_end, target_lufs=a.lufs,
                   ch=a.ch, delay=a.delay, encoder=a.encoder, work=a.work)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "inspect":
        bad = 0
        for p in a.at3:
            info, problems = inspect(p.read_bytes())
            tag = "✓" if not problems else "✗"
            if info.get("total_samples") is not None:
                print(f"{tag} {p.name}: ch={info.get('ch')} frame={info.get('frame')} "
                      f"T={info['total_samples']} ({info['duration_s']:.2f}s) d={info.get('delay')} "
                      f"S={info.get('loop_start_src')} ({(info.get('loop_start_src') or 0) / SR:.2f}s)")
            else:
                print(f"{tag} {p.name}")
            for q in problems:
                print("    -", q)
            bad += bool(problems)
        return 1 if bad else 0
    if a.cmd == "verify":
        r = verify(a.at3, a.ref, a.work)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ncc"] >= 0.95 and abs(r["lufs_decoded"] - r["lufs_ref"]) <= 0.5 else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
