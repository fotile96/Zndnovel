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
    assert len(rows) == 6
    assert all(abs(o - 1.25) < 1e-3 and c > 0.99 for _, o, c in rows)


def test_local_align_stops_where_dump_ends():
    sr = 8000
    rng = np.random.default_rng(2)
    ref = rng.standard_normal(sr * 60).astype(np.float32) * 1000
    dump = np.concatenate([np.zeros(sr, np.float32), ref[: sr * 20]])     # 只录到 20 s
    rows = ml.local_align(dump, ref, sr, approx_s=1.0, step_s=5.0)
    assert rows and all(c > 0.99 for _, _, c in rows) and rows[-1][0] < 20


def test_match_frames_finds_the_frame_and_flags_flat_matches():
    rng = np.random.default_rng(3)
    ref = rng.uniform(0, 255, (50, 27, 48)).astype(np.float32)
    ref[30:40] = 7.0                                  # 一段纯色：匹配平台很宽，应判为模糊
    got = ml.match_frames([ref[12] + 1.0, ref[35]], ref)
    assert got[0][0] == 12 and got[0][2] == 1
    assert got[1][2] >= 10


def test_verdict_flags_drift_and_distortion():
    good = [(t, 2.0, 0.999) for t in range(0, 200, 5)]
    drift = [(t, 2.0 + t * 0.0023, 0.999) for t in range(0, 200, 5)]
    bad = [(t, 2.0, 0.5) for t in range(0, 200, 5)]
    assert ml.verdict(good, [-0.06] * 40)["pass"]
    assert not ml.verdict(drift, [-0.06] * 40)["drift_ok"]
    assert not ml.verdict(bad, [-0.06] * 40)["audio_ok"]
    assert not ml.verdict(good, [-0.5] * 40)["av_ok"]
    assert not ml.verdict([], [])["pass"]                # 什么都没测到不能算通过
