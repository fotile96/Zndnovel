"""build_disc 的 sound 阶段：新曲按名有序插入、原成员逐字节不动、撞名拒绝；
layers._check_sound 对清单/产物的闸。用迷你 pack 容器夹具，不碰真实资产。"""
import hashlib
import io
import json

import pytest

from tools import at3p, layers
from tools.build_disc import build_sound_container
from tools.databin import read_toc, write_container


def _at3(seed: int, frames: int = 3) -> bytes:
    raw = bytes((seed + i) % 256 for i in range(744 * frames))
    return at3p.build_riff(raw, ch=2, delay=4464, loop_start=0)


@pytest.fixture
def orig(tmp_path):
    entries = [("bgm/a.at3", _at3(1)), ("bgm/c.at3", _at3(2)), ("se/z.at3", _at3(3))]
    p = tmp_path / "SOUND.BIN"
    with open(p, "wb") as f:
        write_container(entries, f)
    return p, entries


def test_new_track_inserted_at_sorted_position_and_originals_untouched(orig):
    p, entries = orig
    new = _at3(9)
    blob, ordered = build_sound_container(p, [("bgm/b.at3", new)])
    assert ordered == ["bgm/a.at3", "bgm/b.at3", "bgm/c.at3", "se/z.at3"]
    toc = read_toc(io.BytesIO(blob))
    got = {}
    for name, off, length in toc:
        got[name] = blob[off:off + length]
    assert [n for n, _, _ in toc] == ordered
    assert got["bgm/b.at3"] == new
    for name, data in entries:
        assert got[name] == data, name


def test_container_is_idempotent_without_tracks(orig):
    p, _ = orig
    blob, _ = build_sound_container(p, [])
    assert blob == p.read_bytes()


def test_clashing_member_name_is_rejected(orig):
    p, _ = orig
    with pytest.raises(SystemExit):
        build_sound_container(p, [("bgm/a.at3", _at3(5))])


def _manifest(tmp_path, blob: bytes, member="bgm/bgm_new.at3", loop_start=0.0, sha=None):
    art = tmp_path / "audio" / "x.at3"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_bytes(blob)
    return {"sound": {"iso_path": "/PSP_GAME/USRDIR/SOUND.BIN", "tracks": [{
        "member": member, "source": "assets/audio/x.wav", "source_sha256": "0" * 64,
        "artifact": "audio/x.at3", "sha256": sha or hashlib.sha256(blob).hexdigest(),
        "loop_start": loop_start}]}}


def test_check_sound_passes_on_consistent_track(tmp_path):
    layers._check_sound(_manifest(tmp_path, _at3(4)), root=tmp_path)


def test_check_sound_rejects_bad_fingerprint_clash_and_loop_mismatch(tmp_path):
    blob = _at3(4)
    with pytest.raises(layers.OverlayError, match="sha256"):
        layers._check_sound(_manifest(tmp_path, blob, sha="f" * 64), root=tmp_path)
    original = json.loads((layers.REPO / "data" / "sound_members.json").read_text(encoding="utf-8"))[0]
    with pytest.raises(layers.OverlayError, match="原 SOUND.BIN 成员"):
        layers._check_sound(_manifest(tmp_path, blob, member=original), root=tmp_path)
    with pytest.raises(layers.OverlayError, match="循环起点"):
        layers._check_sound(_manifest(tmp_path, blob, loop_start=1.0), root=tmp_path)
    with pytest.raises(layers.OverlayError, match="bgm/ 或 se/"):
        layers._check_sound(_manifest(tmp_path, blob, member="voice/x.at3"), root=tmp_path)


def test_check_sound_rejects_header_violation(tmp_path):
    bad = _at3(4)[:-8]          # 截掉尾巴：data 不再是帧长整数倍
    with pytest.raises(layers.OverlayError, match="固件规则"):
        layers._check_sound(_manifest(tmp_path, bad), root=tmp_path)
