"""tools/mips_asm.py：给 EBOOT 补丁用的最小 Allegrex/MIPS 汇编器（纯 stdlib）。

正确性的主证据是"把纯净 EBOOT 里一整段代码按 IDA 反汇编重新汇编，必须逐字相同"
（test_roundtrip_pristine_msg_layout_block，需本机 assets/EBOOT.dec.elf）；无资产时靠
下面一组固定字（均取自 docs/ops/eboot-hacking-runbook.md §5.3 的已验证编码与纯净 ELF）。
"""
from pathlib import Path

import pytest

from tools import mips_asm as asm

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "assets" / "EBOOT.dec.elf"


def one(line: str, pc: int = 0) -> int:
    return int.from_bytes(asm.assemble([line], pc), "little")


# ---- 固定字：编码 = 纯净 ELF 里的原字 ------------------------------------------

@pytest.mark.parametrize("line, word", [
    ("lw a0, 0x2cc(s3)", 0x8E6402CC),          # 0xA450
    ("sw zero, 0x2cc(s3)", 0xAE6002CC),        # 0xA5E0
    ("lbu a0, 0x2c6(s3)", 0x926402C6),         # 0xA62C
    ("lbu a2, 0x1ec6(a2)", 0x90C61EC6),        # 0xA678
    ("lui a2, 0x10", 0x3C060010),              # 0xA670
    ("ori a1, zero, 0x18", 0x34050018),        # 0xA5BC  (编译器的 li 是 ori)
    ("li a1, 0x18", 0x34050018),
    ("addiu a2, a2, 10", 0x24C6000A),          # 0xA598
    ("addiu s6, s6, 5", 0x26D60005),           # runbook §5.3
    ("sltiu a0, a0, 0x19", 0x2C840019),        # 0xA5F0
    ("sltiu t4, v0, 3", 0x2C4C0003),           # runbook
    ("xori t5, s0, 1", 0x3A0D0001),            # runbook
    ("addu a1, a1, a3", 0x00A72821),           # 0xA524
    ("addu s1, s1, t5", 0x022D8821),           # runbook
    ("subu a0, a0, a2", 0x00862023),           # 0xA518
    ("subu s2, s2, t4", 0x024C9023),           # runbook
    ("sll a3, a1, 4", 0x00053900),             # 0xA51C
    ("sll a2, s2, 2", 0x00123080),             # runbook
    ("sra a2, a0, 1", 0x00043043),             # 0xA520
    ("srl a2, a2, 31", 0x000637C2),            # 0xA528
    ("or a5, s4, zero", 0x02804825),           # 0xA568
    ("move a5, s4", 0x02804825),               # move = or
    ("move a0, zero", 0x00002025),             # runbook
    ("movn a0, s4, s0", 0x0290200B),           # runbook
    ("movz t4, zero, s0", 0x0010600A),         # runbook
    ("jal 0x5698", 0x0C0015A6),                # 0xA564
    ("nop", 0x00000000),
])
def test_fixed_words(line, word):
    assert one(line) == word & 0xFFFFFFFF


def test_branches_are_pc_relative_to_delay_slot():
    assert one("b 0xa3b4", pc=0xA5B0) == 0x1000FF80                 # 0xA5B0 原字
    assert one("bnel a0, a1, 0xa5f0", pc=0xA5C0) == 0x5485000B      # 0xA5C0
    assert one("beqzl v0, 0xa5f0", pc=0xA5D4) == 0x50400006         # 0xA5D4
    assert one("bnezl a0, 0xa624", pc=0xA5F4) == 0x5480000B         # 0xA5F4
    assert one("bne a0, a1, 0xa5b8", pc=0xA45C) == 0x14850056       # 0xA45C
    assert one("beqz a0, 0xa310", pc=0xA2D4) == 0x1080000E          # 0xA2D4


def test_labels_resolve_forward_and_backward():
    words = asm.assemble([
        "top:",
        "ori a0, zero, 1",
        "bnezl a0, done",
        "nop",
        "b top",
        "nop",
        "done:",
        "nop",
    ], 0x1000)
    w = [int.from_bytes(words[i:i + 4], "little") for i in range(0, len(words), 4)]
    assert w[1] == 0x54800003 and w[3] == 0x1000FFFC and len(w) == 6


def test_word_directive_and_comments_and_blank_lines():
    words = asm.assemble([".word 0x8fc74ad0   ; lw a3,%lo(text)(fp) 带重定位，逐字照抄", "", "nop  # 注释"], 0)
    assert words == bytes.fromhex("d04ac78f00000000")


def test_unknown_mnemonic_and_bad_register_are_errors():
    with pytest.raises(asm.AsmError):
        asm.assemble(["mul a0, a1, a2"], 0)         # Allegrex 无整数 mul
    with pytest.raises(asm.AsmError):
        asm.assemble(["addu a0, a1, x9"], 0)


def test_unresolved_label_is_error():
    with pytest.raises(asm.AsmError):
        asm.assemble(["b nowhere"], 0)


def test_branch_offset_out_of_range_is_error():
    with pytest.raises(asm.AsmError):
        asm.assemble(["b 0x100000"], 0)


# ---- 主证据：整段往返 ---------------------------------------------------------

@pytest.mark.local_assets
@pytest.mark.skipif(not SRC.exists(), reason="缺 assets/EBOOT.dec.elf（解密 EBOOT，本机资产）")
def test_roundtrip_pristine_msg_layout_block():
    """0xA50C–0xA67C（93 字，msg_layout_step 的 ruby 块 + 正文块）按 IDA 反汇编重新汇编，
    必须与纯净 ELF 逐字相同。这段覆盖了补丁会用到的全部指令形状。"""
    from tools.msgcol_px import PRISTINE_LISTING, REGION_VA
    data = SRC.read_bytes()
    lo = REGION_VA + 0xC0
    assert asm.assemble(PRISTINE_LISTING, REGION_VA) == data[lo:lo + 93 * 4]
