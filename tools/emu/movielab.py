"""影片音画探针的分析部分（需要 numpy：uv run --with numpy …）。

录音与参照音轨逐 step_s 秒取 1 s 片段就近互相关 → (ref 时刻, 偏移, 相关)；截帧与参照影片 48×27 灰度逐帧
MSE 匹配 → 片中时刻；两者相减得音画差。判定阈值取 2026-09-24 实测：健康时分段相关 ≥0.999、偏移跨度 <2 ms、
音画差中位 −0.05…−0.10 s；1.20.4 的 48k 破音是相关 0.3–0.76 + 每分钟漂 0.14 s。
依据：docs/ops/movie-playback-ppsspp-2026-09-24.md。
"""
from __future__ import annotations

import numpy as np

FPS = 30000 / 1001


def _best(seg: np.ndarray, region: np.ndarray) -> tuple[int, float]:
    """seg 在 region 里互相关最大的位置与该处的归一化相关系数。"""
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
    """从参照 1 s 起每 step_s 秒取 1 s 片段，在录音里 approx 附近 −0.5…+1.5 s 找它，逐段跟踪偏移。
    返回 [(参照时刻 s, 录音相对参照的偏移 s, 相关)]；静音片段跳过；录音覆盖不到的时刻就停。"""
    rows, off = [], int(approx_s * sr)
    t = 1.0
    while (t + 1) * sr <= len(ref) and int(t * sr) + off + int(1.5 * sr) <= len(dump):
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
    """每帧 48×27 灰度在参照里找 MSE 最小的帧 → (帧号, mse, 平台宽)。平台宽 = 与最优差不多好的帧数，
    宽了说明画面是纯色/静止段，时刻不可判。"""
    out = []
    for g in frames:
        mse = ((ref_gray - g) ** 2).mean(axis=(1, 2))
        k = int(mse.argmin())
        out.append((k, float(mse[k]), int((mse <= mse[k] * 1.15 + 2).sum())))
    return out


def verdict(align_rows: list[tuple[float, float, float]], av_diffs: list[float]) -> dict:
    """audio_ok：相关 ≥0.99 的段 ≥90%；drift_ok：偏移跨度 <0.05 s；av_ok：|中位音画差| <0.2 s。"""
    core = align_rows[:-1] if len(align_rows) > 2 else align_rows      # 末段常落在片尾/循环交界
    corr_ok = sum(1 for _, _, c in core if c >= 0.99) >= 0.9 * max(1, len(core))
    offs = [o for _, o, c in core if c >= 0.9]
    drift_ok = bool(offs) and (max(offs) - min(offs)) < 0.05
    av_ok = bool(av_diffs) and abs(float(np.median(av_diffs))) < 0.2
    return {"audio_ok": corr_ok, "drift_ok": drift_ok, "av_ok": av_ok,
            "pass": corr_ok and drift_ok and av_ok}
