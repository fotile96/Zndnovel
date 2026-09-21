"""tools/at3p.py：RIFF 头算式对原版标准件逐字节重现、inspect 对 99 原曲全过／对坏头全拒、
响度增益的峰值退让。真实资产（build/sound/）缺席时相应用例 skip。"""
import struct
from pathlib import Path

import pytest

from tools import at3p

REPO = Path(__file__).resolve().parents[1]
BGM_20_B = REPO / "build" / "sound" / "bgm_20_b.at3"
SOUND_BIN = REPO / "build" / "sound" / "SOUND.BIN"
local_assets = pytest.mark.skipif(not BGM_20_B.exists(), reason="缺 build/sound/bgm_20_b.at3")


def _chunks(data: bytes) -> dict[str, bytes]:
    out, p = {}, 12
    while p + 8 <= len(data):
        cid = data[p:p + 4].decode("latin1")
        size = struct.unpack_from("<I", data, p + 4)[0]
        out[cid] = data[p + 8:p + 8 + size]
        p += 8 + size + (size & 1)
    return out


def test_build_riff_synthetic_roundtrip():
    raw = bytes(range(256)) * (744 * 3 // 256 + 1)
    raw = raw[: 744 * 3]
    blob = at3p.build_riff(raw, ch=2, delay=4464, loop_start=0)
    info, problems = at3p.inspect(blob)
    assert problems == []
    assert info["frame"] == 744 and info["total_samples"] == 3 * 2048
    assert info["delay"] == 4464 and info["loop_start_src"] == 0
    assert _chunks(blob)["data"] == raw


def test_build_riff_rejects_misaligned_and_out_of_range_loop():
    with pytest.raises(ValueError):
        at3p.build_riff(b"\0" * 745)
    with pytest.raises(ValueError):
        at3p.build_riff(b"\0" * (744 * 3), loop_start=3 * 2048)


def test_inspect_rejects_firmware_violations():
    raw = b"\0" * (744 * 4)
    good = at3p.build_riff(raw, delay=4464)
    # ① fmt 40 B（atracdenc 原生头）
    fmt = at3p.build_fmt(2)[:40]
    body = b"WAVE" + b"fmt " + struct.pack("<I", 40) + fmt + b"data" + struct.pack("<I", len(raw)) + raw
    _, p = at3p.inspect(b"RIFF" + struct.pack("<I", len(body)) + body)
    assert any("0x34" in x for x in p)
    # ② 无 smpl
    c = _chunks(good)
    body = b"WAVE"
    for cid in ("fmt ", "fact", "data"):
        body += cid.encode() + struct.pack("<I", len(c[cid])) + c[cid]
    _, p = at3p.inspect(b"RIFF" + struct.pack("<I", len(body)) + body)
    assert any("smpl" in x for x in p)
    # ③ 采样率 48000
    fmt = bytearray(c["fmt "])
    struct.pack_into("<I", fmt, 4, 48000)
    body = b"WAVE"
    for cid, payload in (("fmt ", bytes(fmt)), ("fact", c["fact"]), ("smpl", c["smpl"]), ("data", c["data"])):
        body += cid.encode() + struct.pack("<I", len(payload)) + payload
    _, p = at3p.inspect(b"RIFF" + struct.pack("<I", len(body)) + body)
    assert any("44100" in x for x in p)
    # 对照：好头零问题
    assert at3p.inspect(good)[1] == []


def test_gain_for_backs_off_at_peak_ceiling():
    assert at3p.gain_for(-30.0, -12.0, -21.0) == (9.0, False)
    gain, limited = at3p.gain_for(-18.0, -0.1, -21.0)      # 要减 3 dB，峰值无碍
    assert gain == pytest.approx(-3.0) and not limited
    gain, limited = at3p.gain_for(-30.0, -3.0, -21.0)      # 想加 9 dB，峰值只让加 2 dB
    assert gain == pytest.approx(2.0) and limited


@local_assets
def test_build_riff_reproduces_bgm_20_b_headers_byte_for_byte():
    """标准件 bgm_20_b：T=2344960（1145 帧）、d=2416、S=336786——按算式重建 fmt/fact/smpl
    与原文件逐字节相同。这是整套头部算式对真机文件成立的直接证据。"""
    data = BGM_20_B.read_bytes()
    c = _chunks(data)
    info, problems = at3p.inspect(data)
    assert problems == []
    rebuilt = at3p.build_riff(c["data"], ch=info["ch"], delay=info["delay"], loop_start=info["loop_start_src"])
    r = _chunks(rebuilt)
    assert r["fmt "] == c["fmt "]
    assert r["fact"] == c["fact"]
    assert r["smpl"] == c["smpl"]
    assert rebuilt == data


@pytest.mark.skipif(not SOUND_BIN.exists(), reason="缺 build/sound/SOUND.BIN")
def test_inspect_accepts_all_original_members():
    from tools.databin import read_toc
    with open(SOUND_BIN, "rb") as f:
        entries = read_toc(f)
        assert len(entries) == 99
        for name, off, length in entries:
            f.seek(off)
            info, problems = at3p.inspect(f.read(length))
            assert problems == [], (name, problems)
            assert info["frame"] == 744
