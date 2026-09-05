"""tools/eboot_relscan.py：重定位扫描（lui 回溯）与存档结构搬迁干跑。

合成用例不依赖任何资产；真源用例（`assets/EBOOT.dec.elf` 在本机时）钉住搬迁清单，并把
layers/eboot/savebuf.toml 与从纯净 ELF 重新推导的清单逐字对账——层文件漂移即红。
"""
import struct
from pathlib import Path

import pytest

from tools import eboot_relscan as rs
from tools import pluto_size as ps

REPO = Path(__file__).resolve().parents[1]
ELF = REPO / "assets" / "EBOOT.dec.elf"


def _lui(rt, imm):
    return (0x0F << 26) | (rt << 16) | (imm & 0xFFFF)


def _lw(rt, base, off):
    return (0x23 << 26) | (base << 21) | (rt << 16) | (off & 0xFFFF)


def _addu(rd, rs_, rt):
    return (rs_ << 21) | (rt << 16) | (rd << 11) | 0x21


def _fake_elf(words: list[int], lo16_sites: list[int]) -> rs.Elf:
    """不经 ELF 头：直接构造 Elf 对象，text 从 0 起、只有 LO16 重定位（addr_base=1）。"""
    e = object.__new__(rs.Elf)
    e.d = b"".join(struct.pack("<I", w) for w in words)
    e.text_off, e.text_size, e.bss_size, e.phoff = 0, len(e.d), 0x10000000, 0
    e.rels = [(4 * i, 6, 0, 1) for i in lo16_sites]
    return e


def test_lui_tracked_through_addu_index_and_clobber():
    # a0 = lui 0x2B; a0 += s1（数组索引）; lbu 0x5888(a0)  → 目标 (0x2B<<16)+0x5888
    # a1 = lui 0x25; a1 = lw 0(a1)（被改写）; lw 4(a1)     → 无法回溯
    words = [_lui(4, 0x2B), _addu(4, 4, 17), _lw(2, 4, 0x5888),
             _lui(5, 0x25), _lw(5, 5, 0), _lw(6, 5, 4)]
    e = _fake_elf(words, [2, 5])
    refs, nolui = e.scan()
    assert [r["X"] for r in refs] == [0x2B5888] and refs[0]["lui"] == 0
    assert nolui == [5 * 4]


def test_negative_lo16_is_sign_extended():
    words = [_lui(4, 0x26), _lw(2, 4, 0xDAA8)]          # (0x26<<16) − 0x2558 = 0x25DAA8
    e = _fake_elf(words, [1])
    refs, _ = e.scan()
    assert refs[0]["X"] == 0x25DAA8


@pytest.mark.skipif(not ELF.exists(), reason="缺解密 EBOOT（本机资产）")
def test_move_plan_matches_committed_layer(tmp_path, capsys):
    """从纯净 ELF 重新推导搬迁清单：37 个 lui + 3 个常量高半字 + p_memsz，与入库层逐字一致。"""
    elf = rs.Elf(ELF)
    refs, _ = elf.scan()
    sref = [r for r in refs if r["ab"] == 1 and rs.STRUCT_RAW <= r["X"] < rs.STRUCT_RAW + rs.STRUCT_SIZE]
    assert len(sref) == 40 and len({r["X"] for r in sref}) == 22
    assert not [r for r in sref if r["kind"] == "W32"]
    luis = sorted({r["lui"] for r in sref})
    assert len(luis) == 37 and 0x7204 in luis and 0x7518 in luis     # lui+addu 索引的两处
    base, delta = ps.savebuf_layout("test")
    out = tmp_path / "savebuf.toml"
    a = type("A", (), {"elf": str(ELF), "delta": hex(delta), "emit_toml": str(out), "profile": "test"})()
    rs.cmd_move_plan(a)
    capsys.readouterr()
    committed = (REPO / "layers" / "eboot" / "savebuf.toml").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == committed
    assert base == 0x2D2628 and delta == 0x40000


@pytest.mark.skipif(not ELF.exists(), reason="缺解密 EBOOT（本机资产）")
def test_patched_elf_has_no_reference_to_old_struct():
    from tools import eboot_patch as ep
    data = ELF.read_bytes()
    import tomllib
    order = tomllib.loads((REPO / "layers" / "manifest.toml").read_text(encoding="utf-8"))["eboot"]["order"]
    assert "savebuf" in order
    patched, _ = ep.apply(data, ep.load_layers(order, profile="test"))
    tmp = REPO / "build" / "eboot" / "_savebuf_test.elf"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(patched)
    try:
        elf = rs.Elf(tmp)
        refs, _ = elf.scan()
        base, delta = ps.savebuf_layout("test")
        old = [r for r in refs if r["ab"] == 1 and rs.STRUCT_RAW <= r["X"] < rs.STRUCT_RAW + rs.STRUCT_SIZE]
        new = [r for r in refs if r["ab"] == 1 and base <= r["X"] < base + rs.STRUCT_SIZE + delta]
        assert not old and len(new) == 40
        assert elf.bss_size == base + rs.STRUCT_SIZE + delta
    finally:
        tmp.unlink()
