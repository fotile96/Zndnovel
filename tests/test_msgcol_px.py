"""layers/eboot/msgcol-px.toml 由 tools/msgcol_px.py 生成：正文列计数改像素、拉丁比例宽。

无资产也能测的：新代码块字数、带重定位的字是否原样搬到登记的新位置、估算常数与校验器一致。
有 assets/EBOOT.dec.elf 时：重生成必须与入库文件逐字相同；施加后分支重定向与重定位表如预期。
"""
import struct
from pathlib import Path

import pytest

from tools import eboot_patch as ep
from tools import mips_asm as asm
from tools import msgcol_px as mp

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "assets" / "EBOOT.dec.elf"


def _words(listing, base):
    return {base + 4 * i: w for i, w in enumerate(asm.words(listing, base))}


def test_new_block_fills_the_region_exactly():
    assert len(asm.words(mp.NEW_LISTING, mp.REGION_VA)) == mp.REGION_WORDS


def test_relocated_words_are_copied_verbatim_to_their_new_slots():
    """每条搬家的重定位条目：新地址上的字必须与纯净源里旧地址上的字相同（jal / %lo / %hi 照抄）。"""
    old = _words(mp.PRISTINE_LISTING, mp.REGION_VA)
    new = _words(mp.NEW_LISTING, mp.REGION_VA)
    assert len(mp.RELOC_MOVES) == 12
    for off, (old_va, new_va) in mp.RELOC_MOVES.items():
        assert new[new_va] == old[old_va], f"reloc@{off:#x}: {old_va:#x}→{new_va:#x}"
    # 没搬的那条（a600 jal strstr_）也得还在原地
    assert new[0xA600] == old[0xA600] == 0x0C004600


def test_no_new_jal_or_hi_lo_word_without_a_reloc_entry():
    """新块里凡是 jal / lui / %lo 形态的字，只能出现在 RELOC_MOVES 的新地址或未搬的 a600。"""
    new = _words(mp.NEW_LISTING, mp.REGION_VA)
    allowed = {nv for _, nv in mp.RELOC_MOVES.values()} | {0xA600}
    for va, w in new.items():
        op = w >> 26
        if op == 3 or op == 0x0F or w in (0x8FC74AD0, 0x8EE84AD4, 0x90C61EC6):
            assert va in allowed, f"{va:#x}: {w:08x} 带重定位却没有条目"


def test_single_word_patches_encode_as_designed():
    assert mp.SINGLE[0x5ACC] == "or v0, s6, zero"            # font_draw_string 返回 pen
    assert mp.SINGLE[0xA738] == "or a5, zero, zero"          # 等待光标 x = col + 8
    w = asm.words([mp.SINGLE[0xA44C]], 0xA44C)[0]
    assert w == 0x54850059                                   # bnel a0,a1 → 0xA5B4（多字节入口）
    w = asm.words([mp.SINGLE[0xA45C]], 0xA45C)[0]
    assert w == 0x14850052                                   # bne a0,a1 → 0xA5A8（单字节入口）


def test_entry_estimates_match_validator_constants():
    from tools import msg_layout_check as mlc
    new = _words(mp.NEW_LISTING, mp.REGION_VA)
    assert new[0xA5A8] == 0x34110000 | mlc.LATIN_EST_PX      # ori s1,zero,LATIN_EST
    assert new[0xA5B4] == 0x34110000 | mlc.CJK_EST_PX        # ori s1,zero,17
    assert new[0xA5B8] == 0x2C850000 | mlc.TAIL_PX               # sltiu a1,a0,392
    assert new[0xA5F0] == 0x2CA50000 | (mlc.LINE_PX + 1)        # sltiu a1,a1,426


@pytest.mark.local_assets
@pytest.mark.skipif(not SRC.exists(), reason="缺 assets/EBOOT.dec.elf（解密 EBOOT，本机资产）")
def test_committed_layer_equals_regeneration_and_applies():
    data = SRC.read_bytes()
    assert mp.render_layer(data) == mp.LAYER.read_text(encoding="utf-8")
    layer = ep.load_layer(mp.LAYER)
    assert {r["state"] for r in ep.check(data, layer["patches"])} == {"pristine"}
    out, _ = ep.apply(data, layer["patches"])
    img = ep.Image(out)

    def word(va):
        return int.from_bytes(out[img.offset(va, 4):img.offset(va, 4) + 4], "little")

    assert word(0x5ACC) == 0x02C01025 and word(0xA44C) == 0x54850059 and word(0xA45C) == 0x14850052
    assert word(0xA738) == 0x00004825
    assert word(0xA5A8) == 0x34110009 and word(0xA668) == 0x00822021     # ori s1,9 / addu a0,a0,v0
    # 重定位表：旧 r_offset 消失、新 r_offset 出现，类型不变
    for off, (old_va, new_va) in mp.RELOC_MOVES.items():
        r_off, r_info = struct.unpack_from("<II", out, off)
        o_off, o_info = struct.unpack_from("<II", data, off)
        assert (o_off, r_off) == (old_va, new_va) and r_info == o_info
