#!/usr/bin/env python3
"""最小 MIPS/Allegrex 汇编器（纯 stdlib），专供 EBOOT 补丁层生成用。

为什么要自己写：IDA MCP 的 patch_asm 不会汇编 MIPS，手工编码 90 个字必错。这里只实现
补丁实际用到的指令形状；正确性由 tests/test_mips_asm.py 里"把纯净 EBOOT 的一整段按 IDA
反汇编重新汇编、逐字比对"来钉住。

语法（每行一条，`;`/`#` 后为注释，`label:` 定义标签）：
  addu/subu/or/and/xor/nor/slt/sltu/movz/movn  rd, rs, rt
  sll/srl/sra  rd, rt, sa
  lw/sw/lb/lbu/lh/lhu/sb/sh  rt, imm(base)
  addiu/ori/andi/xori/slti/sltiu  rt, rs, imm      li rt, imm（= ori rt,zero,imm，PSP 编译器的习惯）
  lui rt, imm                                     move rd, rs（= or rd,rs,zero）
  beq/bne/beql/bnel rs, rt, target                beqz/bnez/beqzl/bnezl rs, target      b target
  jal/j abs_va（未加基址的 VA；带重定位的 jal 请照抄原字：.word 0x........）
  nop        .word imm32
寄存器名用 PSP 习惯：$8–$11 = a4–a7（也接受 t0–t3），$12–$15 = t4–t7，fp = s8。
分支偏移相对延迟槽（pc+4），单位 4 字节；目标可以是标签或绝对地址。
硬规矩（docs/ops/eboot-hacking-runbook.md §0）：Allegrex 没有整数 mul；新 jal 没有重定位
条目会跳飞——所以这里故意不提供 mul，jal 只用于"原地重现同一目标"的场合。
"""
from __future__ import annotations

import re

__all__ = ["AsmError", "assemble", "words"]


class AsmError(ValueError):
    pass


_REGS: dict[str, int] = {"zero": 0, "at": 1, "v0": 2, "v1": 3, "a0": 4, "a1": 5, "a2": 6, "a3": 7,
                         "a4": 8, "a5": 9, "a6": 10, "a7": 11, "t0": 8, "t1": 9, "t2": 10, "t3": 11,
                         "t4": 12, "t5": 13, "t6": 14, "t7": 15,
                         "s0": 16, "s1": 17, "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22, "s7": 23,
                         "t8": 24, "t9": 25, "k0": 26, "k1": 27, "gp": 28, "sp": 29, "fp": 30, "s8": 30,
                         "ra": 31}
_R3 = {"addu": 0x21, "subu": 0x23, "and": 0x24, "or": 0x25, "xor": 0x26, "nor": 0x27,
       "slt": 0x2A, "sltu": 0x2B, "movz": 0x0A, "movn": 0x0B}
_SHIFT = {"sll": 0x00, "srl": 0x02, "sra": 0x03}
_MEM = {"lb": 0x20, "lh": 0x21, "lw": 0x23, "lbu": 0x24, "lhu": 0x25, "sb": 0x28, "sh": 0x29, "sw": 0x2B}
_IMM = {"addiu": 0x09, "slti": 0x0A, "sltiu": 0x0B, "andi": 0x0C, "ori": 0x0D, "xori": 0x0E}
_BR2 = {"beq": 0x04, "bne": 0x05, "beql": 0x14, "bnel": 0x15}
_BRZ = {"beqz": 0x04, "bnez": 0x05, "beqzl": 0x14, "bnezl": 0x15}
_JUMP = {"j": 0x02, "jal": 0x03}
_MEM_RE = re.compile(r"^(-?\w+)\((\w+)\)$")


def _reg(tok: str) -> int:
    t = tok.strip().lstrip("$")
    if t in _REGS:
        return _REGS[t]
    if t.isdigit() and 0 <= int(t) < 32:
        return int(t)
    raise AsmError(f"未知寄存器 {tok!r}")


def _num(tok: str, labels: dict[str, int] | None = None) -> int:
    t = tok.strip()
    if labels is not None and t in labels:
        return labels[t]
    try:
        return int(t, 0)
    except ValueError:
        raise AsmError(f"无法解析数值/标签 {tok!r}") from None


def _imm16(v: int, what: str) -> int:
    if not -0x8000 <= v <= 0xFFFF:
        raise AsmError(f"{what} 立即数 {v:#x} 超出 16 位")
    return v & 0xFFFF


def _split(line: str) -> tuple[str, list[str]]:
    parts = line.split(None, 1)
    mnem = parts[0].lower()
    ops = [o.strip() for o in parts[1].split(",")] if len(parts) > 1 else []
    return mnem, ops


def _strip(line: str) -> str:
    return re.split(r"[;#]", line, maxsplit=1)[0].strip()


def _encode(mnem: str, ops: list[str], pc: int, labels: dict[str, int]) -> int:
    n = len(ops)
    if mnem == "nop":
        return 0
    if mnem == ".word":
        return _num(ops[0]) & 0xFFFFFFFF
    if mnem == "move" and n == 2:
        return (_reg(ops[1]) << 21) | (_reg(ops[0]) << 11) | _R3["or"]
    if mnem == "li" and n == 2:
        v = _num(ops[1])
        if not 0 <= v <= 0xFFFF:
            raise AsmError(f"li 只实现 ori 形式（0..0xFFFF），收到 {v:#x}")
        return (_IMM["ori"] << 26) | (_reg(ops[0]) << 16) | v
    if mnem in _R3 and n == 3:
        return (_reg(ops[1]) << 21) | (_reg(ops[2]) << 16) | (_reg(ops[0]) << 11) | _R3[mnem]
    if mnem in _SHIFT and n == 3:
        sa = _num(ops[2])
        if not 0 <= sa < 32:
            raise AsmError(f"移位量 {sa} 越界")
        return (_reg(ops[1]) << 16) | (_reg(ops[0]) << 11) | (sa << 6) | _SHIFT[mnem]
    if mnem in _MEM and n == 2:
        m = _MEM_RE.match(ops[1].replace(" ", ""))
        if not m:
            raise AsmError(f"访存操作数应为 imm(base)：{ops[1]!r}")
        return (_MEM[mnem] << 26) | (_reg(m.group(2)) << 21) | (_reg(ops[0]) << 16) | _imm16(_num(m.group(1)), mnem)
    if mnem in _IMM and n == 3:
        return (_IMM[mnem] << 26) | (_reg(ops[1]) << 21) | (_reg(ops[0]) << 16) | _imm16(_num(ops[2]), mnem)
    if mnem == "lui" and n == 2:
        return (0x0F << 26) | (_reg(ops[0]) << 16) | _imm16(_num(ops[1]), mnem)
    if mnem in _BR2 and n == 3:
        return (_BR2[mnem] << 26) | (_reg(ops[0]) << 21) | (_reg(ops[1]) << 16) | _boff(ops[2], pc, labels)
    if mnem in _BRZ and n == 2:
        return (_BRZ[mnem] << 26) | (_reg(ops[0]) << 21) | _boff(ops[1], pc, labels)
    if mnem == "b" and n == 1:
        return (0x04 << 26) | _boff(ops[0], pc, labels)
    if mnem in _JUMP and n == 1:
        target = _num(ops[0], labels)
        if target & 3 or target >> 28 != (pc + 4) >> 28:
            raise AsmError(f"{mnem} 目标 {target:#x} 不在同一 256 MB 区或未对齐")
        return (_JUMP[mnem] << 26) | ((target >> 2) & 0x03FFFFFF)
    raise AsmError(f"不支持的指令/操作数形状：{mnem} {', '.join(ops)}")


def _boff(target_tok: str, pc: int, labels: dict[str, int]) -> int:
    target = _num(target_tok, labels)
    delta = target - (pc + 4)
    if delta & 3:
        raise AsmError(f"分支目标 {target:#x} 未对齐")
    off = delta >> 2
    if not -0x8000 <= off <= 0x7FFF:
        raise AsmError(f"分支偏移 {off} 超出 16 位（pc={pc:#x} → {target:#x}）")
    return off & 0xFFFF


def words(lines: list[str], base_va: int) -> list[int]:
    """两遍：先收标签，再编码。返回 32 位字列表。"""
    labels: dict[str, int] = {}
    prog: list[tuple[str, list[str], int]] = []
    pc = base_va
    for raw in lines:
        line = _strip(raw)
        if not line:
            continue
        if line.endswith(":") and " " not in line:
            name = line[:-1]
            if name in labels:
                raise AsmError(f"标签重复 {name!r}")
            labels[name] = pc
            continue
        mnem, ops = _split(line)
        prog.append((mnem, ops, pc))
        pc += 4
    return [_encode(m, o, p, labels) for m, o, p in prog]


def assemble(lines: list[str], base_va: int) -> bytes:
    return b"".join(w.to_bytes(4, "little") for w in words(lines, base_va))
