"""tools/ios_fwmod.py：固件 libmp4/mp4msv 改库名 + 1.20.x 兼容补丁（有 assets/fw/ 才跑真件）。"""
import struct
from pathlib import Path

import pytest

from tools import ios_fwmod as fm

FW = Path(__file__).resolve().parents[1] / "assets" / "fw"
needs_fw = pytest.mark.skipif(not (FW / "libmp4.dec.prx").exists(), reason="assets/fw 不在（版权物）")


def test_input_sha_mismatch_is_hard_error():
    with pytest.raises(ValueError, match="sha256"):
        fm.patch_libmp4(b"\0" * 64)


@needs_fw
def test_relocs_b_decodes_libmp4():
    rs = fm.relocs_b((FW / "libmp4.dec.prx").read_bytes())
    assert len(rs) == 903
    sites = dict(rs)
    assert sites[0x487C] == 7                   # jal sceAudiocodecDecode（JAL26）
    assert not any(0x6054 <= s < 0x6054 + 4 * 14 for s, _ in rs)   # 跳板区无重定位


@needs_fw
def test_patched_tables_and_trampoline():
    out = fm.patch_libmp4((FW / "libmp4.dec.prx").read_bytes())
    ex, im = fm.exports(out), fm.imports(out)
    assert fm.LIB_EXPORT in ex and "sceMp4" not in ex
    assert fm.MSV_EXPORT in im and "mp4msv" not in im
    assert im["ModuleMgrForUser"]["count"] == 0
    w = lambda va: struct.unpack_from("<I", out, fm.text_off(out) + va)[0]  # noqa: E731
    assert w(0x487C) == 0x0C000000 | (0x6054 >> 2)          # jal → 跳板
    assert w(0x72A8) == 0x03E00008 and w(0x72AC) == 0x2402FFFF  # jr ra; li v0,-1
    assert fm.sha256(out) == fm.LIBMP4_OUT_SHA


@needs_fw
def test_mp4msv_export_renamed():
    out = fm.patch_mp4msv((FW / "mp4msv.dec.prx").read_bytes())
    assert fm.MSV_EXPORT in fm.exports(out)
    assert fm.sha256(out) == fm.MP4MSV_OUT_SHA


def test_build_without_source_points_to_the_doc(tmp_path):
    with pytest.raises(SystemExit, match="固件模块的取得"):
        fm.build(tmp_path / "out", fw_dir=tmp_path / "empty")


@needs_fw
def test_build_writes_both_patched_modules(tmp_path):
    got = fm.build(tmp_path / "out", fw_dir=FW)
    assert sorted(got) == ["libmp4.prx", "mp4msv.prx"]
    assert fm.sha256(got["libmp4.prx"].read_bytes()) == fm.LIBMP4_OUT_SHA
    assert fm.sha256(got["mp4msv.prx"].read_bytes()) == fm.MP4MSV_OUT_SHA
