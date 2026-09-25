"""[[movies]]：用户压制的影片（如中文字幕版 OP）替换盘内 movie/ 成员——两张盘都用；iOS 盘另要求 44.1k 音轨。"""
import hashlib
import struct

import pytest

from tools import ios_movie as im


def _box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _trak(handler: bytes, timescale: int) -> bytes:
    mdhd = _box(b"mdhd", b"\0" * 4 + b"\0" * 8 + struct.pack(">II", timescale, 1000) + b"\0" * 4)
    hdlr = _box(b"hdlr", b"\0" * 8 + handler + b"\0" * 13)
    return _box(b"trak", _box(b"mdia", mdhd + hdlr))


def _mp4(path, audio_rate: int):
    data = (_box(b"ftyp", b"MSNV\0\0\x02\0") + _box(b"moov", _trak(b"vide", 30000) + _trak(b"soun", audio_rate))
            + _box(b"mdat", b"x" * 16))
    path.write_bytes(data)
    return path


def _entry(path, sha=None, member="op.mp4"):
    return {"member": member, "source": str(path), "why": "测试",
            "sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest()}


# ---------------------------------------------------------------- ios_movie

def test_audio_rate_reads_the_sound_track_timescale(tmp_path):
    assert im.audio_rate(_mp4(tmp_path / "a.mp4", 44100)) == 44100
    assert im.audio_rate(_mp4(tmp_path / "b.mp4", 48000)) == 48000


def test_build_only_touches_requested_members(tmp_path, monkeypatch):
    touched = []
    monkeypatch.setattr(im, "require_ffmpeg", lambda: None)
    monkeypatch.setattr(im, "_extract", lambda iso, inner, dst: (touched.append(inner), dst.write_bytes(b"src")))
    monkeypatch.setattr(im, "resample", lambda s, d: d.write_bytes(b"ed"))
    monkeypatch.setattr(im, "probe", lambda p: {"audio_rate": 44100, "audio_codec": "aac", "channels": 2,
                                                "video": "h264 480x272"})
    monkeypatch.setattr(im, "video_md5", lambda p: "same")
    pins = {"op.mp4": "0" * 64, "ed.mp4": hashlib.sha256(b"ed").hexdigest()}
    got = im.build(tmp_path, pins, tmp_path / "no.iso", members=["ed.mp4"])
    assert list(got) == ["ed.mp4"] and touched == ["/PSP_GAME/USRDIR/movie/ed.mp4"]
    assert im.cached(tmp_path, pins, members=["ed.mp4"]) and not im.cached(tmp_path, pins)


# ---------------------------------------------------------------- build_disc

def _ctx(tmp_path, movies):
    import tools.build_disc as bd
    return bd.BuildContext(profile="release", root=tmp_path / "root", switches={}, mode_opts={},
                           manifest={"movies": movies, "ios": {"iso_name": "game_zh_ios.iso", "movies": {}}})


def test_layer_movies_checks_pins(tmp_path):
    import tools.build_disc as bd
    op = _mp4(tmp_path / "op.mp4", 44100)
    assert bd._layer_movies(_ctx(tmp_path, [_entry(op)])) == {"op.mp4": op}
    with pytest.raises(SystemExit, match="sha256"):
        bd._layer_movies(_ctx(tmp_path, [_entry(op, sha="0" * 64)]))
    with pytest.raises(SystemExit, match="gone.mp4"):
        bd._layer_movies(_ctx(tmp_path, [_entry(op) | {"source": str(tmp_path / "gone.mp4")}]))


def test_ios_disc_takes_layer_movie_and_refuses_48k(tmp_path):
    import tools.build_disc as bd
    built = {"op.mp4": tmp_path / "op_resampled.mp4", "ed.mp4": tmp_path / "ed_resampled.mp4"}
    op44 = _mp4(tmp_path / "op44.mp4", 44100)
    got = bd._ios_movie_set(_ctx(tmp_path, [_entry(op44)]), built)
    assert got == {"op.mp4": op44, "ed.mp4": built["ed.mp4"]}
    op48 = _mp4(tmp_path / "op48.mp4", 48000)
    with pytest.raises(SystemExit, match="44100"):
        bd._ios_movie_set(_ctx(tmp_path, [_entry(op48)]), built)


# ---------------------------------------------------------------- layers 闸

def test_gate_checks_movie_pins_and_rate(tmp_path, capsys):
    from tools import layers
    op = _mp4(tmp_path / "op.mp4", 44100)
    layers._check_movies({"movies": [_entry(op)]})
    assert "movies: 1" in capsys.readouterr().out
    with pytest.raises(layers.OverlayError, match="sha256"):
        layers._check_movies({"movies": [_entry(op, sha="0" * 64)]})
    with pytest.raises(layers.OverlayError, match="44100"):
        layers._check_movies({"movies": [_entry(_mp4(tmp_path / "op48.mp4", 48000))]})
    layers._check_movies({"movies": [_entry(op) | {"source": str(tmp_path / "gone.mp4")}]})   # 缺素材只告警
    assert "⚠" in capsys.readouterr().out


def test_manifest_movie_entries_are_validated():
    from tools import layers
    with pytest.raises(layers.OverlayError, match="缺"):
        layers._validate_movies([{"member": "op.mp4", "source": "x"}])
    with pytest.raises(layers.OverlayError, match="op.mp4"):
        layers._validate_movies([{"member": "intro.mp4", "source": "x", "sha256": "0" * 64, "why": "w"}])
    with pytest.raises(layers.OverlayError, match="两次"):
        e = {"member": "op.mp4", "source": "x", "sha256": "0" * 64, "why": "w"}
        layers._validate_movies([e, dict(e)])
