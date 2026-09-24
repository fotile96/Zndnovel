"""layers/eboot/ios-movie.toml 由 tools/ios_eboot.py 生成（E1–E4，见 movie-playback 文档「追记：iOS」）。"""
import struct
from pathlib import Path

import pytest

from tools import eboot_patch as ep
from tools import ios_eboot as ie
from tools import layers

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "assets" / "EBOOT.dec.elf"
needs_src = pytest.mark.skipif(not SRC.exists(), reason="assets/EBOOT.dec.elf 不在")
RELEASE_EBOOT_SHA = "6c82faecf77d1db0baf706eecc34c5c506e251ed7ff84251c65893a6da75590c"   # 2026-09-24 开工前


def _relocs(elf: bytes):
    shoff, = struct.unpack_from("<I", elf, 32)
    shentsize, shnum = struct.unpack_from("<HH", elf, 46)
    for i in range(shnum):
        _, t, _, _, off, size = struct.unpack_from("<6I", elf, shoff + i * shentsize)
        if t == 0x700000A0:
            for j in range(size // 8):
                r_off, r_info = struct.unpack_from("<II", elf, off + 8 * j)
                yield off + 8 * j, r_off, r_info & 0xFF


@needs_src
def test_regenerated_layer_matches_committed():
    assert ie.render_layer(SRC.read_bytes()) == (REPO / "layers/eboot/ios-movie.toml").read_text(encoding="utf-8")


@needs_src
def test_release_profile_excludes_ios_layer_and_is_unchanged():
    m = layers.load_manifest()["eboot"]
    rel = ep.load_layers(m["order"], profile="release")
    assert not any(p.layer == "ios-movie" for p in rel)
    out, _ = ep.apply(SRC.read_bytes(), rel)
    assert ep.sha256(out) == RELEASE_EBOOT_SHA


@needs_src
def test_ios_build_neutralizes_every_reloc_in_used_cave_and_keeps_call_relocs():
    m = layers.load_manifest()["eboot"]
    out, _ = ep.apply(SRC.read_bytes(), ep.load_layers(m["order"], profile="release", ios=True))
    used_end = ie.WRAP_CREATE + 4 * len(ie.CREATE_LISTING)
    for fo, r_off, typ in _relocs(out):
        if ie.CAVE <= r_off < used_end:
            assert typ == 0, f"洞内 {r_off:#x} 的重定位（表项 {fo:#x}）没有改成 NONE"
        if r_off in ie.CALLS:
            assert typ == 4, f"调用点 {r_off:#x} 必须保留 R_MIPS_26"
    for site, target in ie.CALLS.items():
        w = struct.unpack_from("<I", out, site + 0xC0)[0]
        assert w == 0x0C000000 | (target >> 2)
    assert out[ie.IMPORT_NAME_VA + 0xC0: ie.IMPORT_NAME_VA + 0xC0 + 7] == b"zndMp4\0"
