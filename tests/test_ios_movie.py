"""tools/ios_movie.py：op/ed 音轨重采样 44.1k（视频原样）+ 指纹钉住。"""
import shutil
from pathlib import Path

import pytest

from tools import ios_movie as im

ORIG = Path(__file__).resolve().parents[1] / "assets" / "orig.iso"
needs_media = pytest.mark.skipif(not ORIG.exists() or not shutil.which("ffmpeg"),
                                 reason="需要 assets/orig.iso 与 ffmpeg")


def test_recipe_keeps_video_and_resamples_audio():
    a = im.FFMPEG_ARGS
    assert a[a.index("-c:v") + 1] == "copy" and a[a.index("-ar") + 1] == "44100"
    assert "+bitexact" in a


def test_pin_mismatch_names_ffmpeg_version(tmp_path, monkeypatch):
    monkeypatch.setattr(im, "_extract", lambda iso, inner, dst: dst.write_bytes(b"src"))
    monkeypatch.setattr(im, "resample", lambda s, d: d.write_bytes(b"out"))
    monkeypatch.setattr(im, "probe", lambda p: {"audio_rate": 44100, "audio_codec": "aac", "channels": 2,
                                                "video": "h264 480x272"})
    monkeypatch.setattr(im, "video_md5", lambda p: "same")
    monkeypatch.setattr(im, "ffmpeg_version", lambda: "ffmpeg version 99.9")
    with pytest.raises(SystemExit, match="99.9"):
        im.build(tmp_path, {"op.mp4": "0" * 64, "ed.mp4": "0" * 64}, ORIG)


@needs_media
def test_real_op_resample_structure(tmp_path):
    src = tmp_path / "op.mp4"
    im._extract(ORIG, "/PSP_GAME/USRDIR/movie/op.mp4", src)
    dst = tmp_path / "op44.mp4"
    im.resample(src, dst)
    p = im.probe(dst)
    assert (p["audio_rate"], p["audio_codec"], p["channels"]) == (44100, "aac", 2)
    assert im.video_md5(dst) == im.video_md5(src)
