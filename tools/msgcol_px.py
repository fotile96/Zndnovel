#!/usr/bin/env python3
"""生成 layers/eboot/msgcol-px.toml：正文列计数从"17 px 一格"改成"像素"，拉丁字母按字形
真实步进（比例宽）推进。机制、字数预算与取舍见 docs/ops/eboot-kinsoku-research-2026-09-04.md §9。

用法（改动 NEW_LISTING 后重生成，tests/test_msgcol_px.py 会拿纯净源重推对账）：
    uv run python tools/msgcol_px.py            # 写 layers/eboot/msgcol-px.toml
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools import mips_asm as asm  # noqa: E402

LAYER = REPO / "layers" / "eboot" / "msgcol-px.toml"
FILE_BASE = 0xC0                    # 段内字节：文件偏移 = VA + 0xC0

REGION_VA = 0xA50C                  # 重排区间 [0xA50C, 0xA680)，93 字；0xA508 归 ruby-p5 层
REGION_WORDS = 93
LATIN_EST_PX = 9                    # 单字节字符画之前的步进估算（只用于"这一行还放不放得下"）
CJK_EST_PX = 17
LINE_PX = 25 * 17                   # 425：25 格 × 17 px 的行宽（悬挂区从这里起）

# 0xA50C–0xA67C 的纯净代码（IDA 反汇编逐条转写；带重定位的字用 .word 照抄）。
# tests/test_mips_asm.py 用它做汇编器的往返证据。
PRISTINE_LISTING = [
    "lw a1, 0x2cc(s3)",          # a50c  col
    "addu a0, s1, a0",           # a510  17*nb（a0 = 16*nb 来自延迟槽）
    "addu a2, s2, a2",           # a514  5*units
    "subu a0, a0, a2",           # a518
    "sll a3, a1, 4",             # a51c
    "sra a2, a0, 1",             # a520
    "addu a1, a1, a3",           # a524  17*col
    "srl a2, a2, 31",            # a528
    "lw a3, 0x2d0(s3)",          # a52c  line
    "addu a0, a0, a2",           # a530
    "sra a0, a0, 1",             # a534  (17nb-5u)/2
    "sll a2, a3, 3",             # a538
    "addu a0, a1, a0",           # a53c
    "addu a1, a3, a2",           # a540  9L
    "addiu a3, a0, 4",           # a544  x_ruby
    "addu a0, a2, a1",           # a548  17L
    "addu a0, a0, a1",           # a54c  26L
    "or a1, a3, zero",           # a550
    ".word 0x8fc74ad0",          # a554  lw a3,%lo(msg_text_layer)(fp)   [LO16]
    "addiu a2, a0, 1",           # a558  y_ruby
    ".word 0x8ee84ad4",          # a55c  lw a4,%lo(msg_outline_layer)(s7) [LO16]
    "ori a0, zero, 1",           # a560  font 1
    ".word 0x0c0015a6",          # a564  jal font_draw_string             [R_MIPS_26]
    "or a5, s4, zero",           # a568  ruby buf
    "lw a0, 0x2cc(s3)",          # a56c
    "lw a1, 0x2d0(s3)",          # a570
    "sll a2, a0, 4",             # a574
    "sll a3, a1, 3",             # a578
    "addu a0, a0, a2",           # a57c  17col
    "addu a2, a1, a3",           # a580  9L
    "addiu a1, a0, 4",           # a584  x_base
    "addu a0, a3, a2",           # a588  17L
    "addu a2, a0, a2",           # a58c  26L
    ".word 0x8fc74ad0",          # a590  [LO16]
    ".word 0x8ee84ad4",          # a594  [LO16]
    "addiu a2, a2, 10",          # a598  y_base
    "or a0, zero, zero",         # a59c  font 0
    ".word 0x0c0015a6",          # a5a0  jal font_draw_string             [R_MIPS_26]
    "or a5, s5, zero",           # a5a4  base buf
    "lw a0, 0x2cc(s3)",          # a5a8
    "addu a0, a0, s1",           # a5ac  col += nb
    "b 0xa3b4",                  # a5b0
    "sw a0, 0x2cc(s3)",          # a5b4
    "lw a0, 0x2cc(s3)",          # a5b8  loc_A5B8（单字节入口）
    "ori a1, zero, 0x18",        # a5bc  loc_A5BC（多字节入口）
    "bnel a0, a1, 0xa5f0",       # a5c0  col != 24 → 跳过行末禁则
    "lw a0, 0x2cc(s3)",          # a5c4
    "lw a0, 0xe0(sp)",           # a5c8  行末表
    ".word 0x0c004600",          # a5cc  jal strstr_                      [R_MIPS_26]
    "or a1, sp, zero",           # a5d0
    "beqzl v0, 0xa5f0",          # a5d4
    "lw a0, 0x2cc(s3)",          # a5d8
    "lw a0, 0x2d0(s3)",          # a5dc  换行
    "sw zero, 0x2cc(s3)",        # a5e0
    "addiu a0, a0, 1",           # a5e4
    "sw a0, 0x2d0(s3)",          # a5e8
    "lw a0, 0x2cc(s3)",          # a5ec
    "sltiu a0, a0, 0x19",        # a5f0  loc_A5F0：col < 25？
    "bnezl a0, 0xa624",          # a5f4
    "lw a0, 0x2d0(s3)",          # a5f8
    "lw a0, 0xdc(sp)",           # a5fc  行头表
    ".word 0x0c004600",          # a600  jal strstr_                      [R_MIPS_26]
    "or a1, sp, zero",           # a604
    "bnezl v0, 0xa624",          # a608
    "lw a0, 0x2d0(s3)",          # a60c
    "lw a0, 0x2d0(s3)",          # a610  换行
    "sw zero, 0x2cc(s3)",        # a614
    "addiu a0, a0, 1",           # a618
    "sw a0, 0x2d0(s3)",          # a61c
    "lw a0, 0x2d0(s3)",          # a620
    "sltiu a1, a0, 4",           # a624  loc_A624：line < 4？
    "beqzl a1, 0xa6ec",          # a628
    "lbu a0, 0x2c6(s3)",         # a62c
    "lw a1, 0x2cc(s3)",          # a630  col
    "sll a2, a0, 3",             # a634
    "sll a3, a1, 4",             # a638
    "addu a0, a0, a2",           # a63c  9L
    "addu a1, a1, a3",           # a640  17col
    "addu a2, a2, a0",           # a644  17L
    "addu a2, a2, a0",           # a648  26L
    ".word 0x8fc74ad0",          # a64c  [LO16]
    "addiu a1, a1, 4",           # a650  x
    ".word 0x8ee84ad4",          # a654  [LO16]
    "addiu a2, a2, 10",          # a658  y
    "or a0, zero, zero",         # a65c  font 0
    ".word 0x0c0015a6",          # a660  jal font_draw_string             [R_MIPS_26]
    "or a5, sp, zero",           # a664  单字符缓冲
    "lw a0, 0x2cc(s3)",          # a668
    "lw a1, 0xd4(sp)",           # a66c  var_10
    ".word 0x3c060010",          # a670  lui a2,%hi(byte_1DD346)          [HI16]
    "addiu a0, a0, 1",           # a674  col++
    ".word 0x90c61ec6",          # a678  lbu a2,%lo(byte_1DD346)(a2)      [LO16]
    "sw a0, 0x2cc(s3)",          # a67c
]
assert len([l for l in PRISTINE_LISTING if not l.endswith(":")]) == REGION_WORDS


# ---------------------------------------------------------------------------
# 新代码：同一区间重排（带重定位的字原样搬到新位置，条目 r_offset 随之改；顺序不变，
# HI16/LO16 按表内先后配对，见研究记录 §7.5 / §9.3）
# ---------------------------------------------------------------------------
NEW_LISTING = [
    # ---- ruby 块：先画 base 取真实宽 w，再按 w 居中画注音；0xA508 的 sll a2,s2,2（=4u）归 ruby-p5 层
    "addu s1, s2, a2",           # a50c  s1 = 5u（nb 计数作废，s1 复用）
    "lw a1, 0x2cc(s3)",          # a510  col（像素）
    "lw a3, 0x2d0(s3)",          # a514  line
    "sll a2, a3, 3",             # a518  8L
    "addu a0, a3, a2",           # a51c  9L
    "addu a2, a0, a2",           # a520  17L
    "addu a2, a0, a2",           # a524  26L
    "addiu a1, a1, 4",           # a528  x_base = col + 4
    ".word 0x8fc74ad0",          # a52c  lw a3,%lo(msg_text_layer)(fp)    [LO16 ← a554]
    ".word 0x8ee84ad4",          # a530  lw a4,%lo(msg_outline_layer)(s7) [LO16 ← a55c]
    "addiu a2, a2, 10",          # a534  y_base = 26L + 10
    "or a0, zero, zero",         # a538  font 0
    ".word 0x0c0015a6",          # a53c  jal font_draw_string             [R_MIPS_26 ← a564]
    "or a5, s5, zero",           # a540  base 缓冲
    "or s0, v0, zero",           # a544  w = base 像素宽（font_draw_string 现返回 pen）
    "subu a0, s0, s1",           # a548  w − 5u
    "sra a2, a0, 1",             # a54c
    "srl a2, a2, 31",            # a550
    "addu a0, a0, a2",           # a554
    "sra a0, a0, 1",             # a558  (w − 5u)/2，向零截断
    "lw a1, 0x2cc(s3)",          # a55c  col
    "lw a3, 0x2d0(s3)",          # a560  line
    "addu a0, a1, a0",           # a564  col + (w − 5u)/2
    "sll a2, a3, 3",             # a568  8L
    "addu a1, a3, a2",           # a56c  9L
    "addiu a3, a0, 4",           # a570  x_ruby
    "addu a0, a2, a1",           # a574  17L
    "addu a0, a0, a1",           # a578  26L
    "or a1, a3, zero",           # a57c
    ".word 0x8fc74ad0",          # a580  [LO16 ← a590]
    "addiu a2, a0, 1",           # a584  y_ruby = 26L + 1
    ".word 0x8ee84ad4",          # a588  [LO16 ← a594]
    "ori a0, zero, 1",           # a58c  font 1
    ".word 0x0c0015a6",          # a590  jal font_draw_string             [R_MIPS_26 ← a5a0]
    "or a5, s4, zero",           # a594  ruby 缓冲
    "lw a0, 0x2cc(s3)",          # a598
    "addu a0, a0, s0",           # a59c  col += w
    "b 0xa3b4",                  # a5a0  下一字符
    "sw a0, 0x2cc(s3)",          # a5a4
    # ---- 正文入口：两条路径各自设"画之前的步进估算"s1，只用于行头判定
    "entry_1byte:",              # a5a8 ← 0xA45C bne（单字节且非 '<'）
    "ori s1, zero, 9",           # a5a8  LATIN_EST_PX
    "b join",                    # a5ac
    "lw a0, 0x2cc(s3)",          # a5b0  （延迟槽）a0 = col
    "entry_multi:",              # a5b4 ← 0xA44C bnel（len ≠ 1；其延迟槽已装 a0 = col）
    "ori s1, zero, 17",          # a5b4  CJK_EST_PX
    "join:",
    "sltiu a1, a0, 392",         # a5b8  col < 425 − 2·17 → 不查行末禁则
    "bnezl a1, head",            # a5bc
    "lw a0, 0x2cc(s3)",          # a5c0
    "lw a0, 0xe0(sp)",           # a5c4  行末表
    ".word 0x0c004600",          # a5c8  jal strstr_                      [R_MIPS_26 ← a5cc]
    "or a1, sp, zero",           # a5cc
    "beqzl v0, head",            # a5d0
    "lw a0, 0x2cc(s3)",          # a5d4
    "lw a0, 0x2d0(s3)",          # a5d8  换行
    "sw zero, 0x2cc(s3)",        # a5dc
    "addiu a0, a0, 1",           # a5e0
    "sw a0, 0x2d0(s3)",          # a5e4
    "lw a0, 0x2cc(s3)",          # a5e8  = 0
    "head:",
    "addu a1, a0, s1",           # a5ec  col + est
    "sltiu a1, a1, 426",         # a5f0  < 426 即放得下 → 不查行头禁则
    "bnezl a1, draw",            # a5f4
    "lw a0, 0x2d0(s3)",          # a5f8
    "lw a0, 0xdc(sp)",           # a5fc  行头表
    ".word 0x0c004600",          # a600  jal strstr_                      [R_MIPS_26，位置不变]
    "or a1, sp, zero",           # a604
    "bnezl v0, draw",            # a608
    "lw a0, 0x2d0(s3)",          # a60c
    "lw a0, 0x2d0(s3)",          # a610  换行（原块末尾重读 line 的那条删掉：a0 已是新 line）
    "sw zero, 0x2cc(s3)",        # a614
    "addiu a0, a0, 1",           # a618
    "sw a0, 0x2d0(s3)",          # a61c
    "draw:",
    "sltiu a1, a0, 4",           # a620  line < 4？
    "beqzl a1, 0xa6ec",          # a624  第 5 行起停滞（延迟槽装 page_wait 给 loc_A6EC）
    "lbu a0, 0x2c6(s3)",         # a628
    "lw a1, 0x2cc(s3)",          # a62c  col
    "sll a2, a0, 3",             # a630  8L
    "addu a0, a0, a2",           # a634  9L
    "addu a2, a2, a0",           # a638  17L
    "addu a2, a2, a0",           # a63c  26L
    ".word 0x8fc74ad0",          # a640  [LO16 ← a64c]
    "addiu a1, a1, 4",           # a644  x = col + 4
    ".word 0x8ee84ad4",          # a648  [LO16 ← a654]
    "addiu a2, a2, 10",          # a64c  y = 26L + 10
    "or a0, zero, zero",         # a650  font 0
    ".word 0x0c0015a6",          # a654  jal font_draw_string             [R_MIPS_26 ← a660]
    "or a5, sp, zero",           # a658  单字符缓冲
    "lw a0, 0x2cc(s3)",          # a65c
    "lw a1, 0xd4(sp)",           # a660
    ".word 0x3c060010",          # a664  lui a2,%hi(byte_1DD346)          [HI16 ← a670]
    "addu a0, a0, v0",           # a668  col += 真实步进（比例宽）
    ".word 0x90c61ec6",          # a66c  lbu a2,%lo(byte_1DD346)(a2)      [LO16 ← a678]
    "sw a0, 0x2cc(s3)",          # a670
    "nop",                       # a674
    "nop",                       # a678
    "nop",                       # a67c  0xA680 起原样（or a0,a2,a1 …）
]

# 重定位条目搬家：文件偏移 → (旧 r_offset, 新 r_offset)。类型不变，表内顺序不变。
RELOC_MOVES = {
    0x73600: (0xA554, 0xA52C), 0x73610: (0xA55C, 0xA530), 0x73618: (0xA564, 0xA53C),
    0x73620: (0xA590, 0xA580), 0x73628: (0xA594, 0xA588), 0x73630: (0xA5A0, 0xA590),
    0x73638: (0xA5CC, 0xA5C8),
    0x73648: (0xA64C, 0xA640), 0x73650: (0xA654, 0xA648), 0x73658: (0xA660, 0xA654),
    0x73660: (0xA670, 0xA664), 0x73668: (0xA678, 0xA66C),
}

# 区间外的单字补丁：VA → (新指令, 说明)
SINGLE = {
    0x5ACC: "or v0, s6, zero",          # font_draw_string 末尾 li v0,1 → 返回 pen（s6 = 累计步进）
    0xA44C: "bnel a0, a1, 0xa5b4",      # 多字节字符 → 新的 entry_multi（延迟槽 lw a0,col 不变）
    0xA45C: "bne a0, a1, 0xa5a8",       # 单字节非 '<' → 新的 entry_1byte
    0xA738: "or a5, zero, zero",        # 等待光标 x：17·col+8 → col+8（sll a5,a3,4 → a5 = 0）
}
SINGLE_NOTE = {
    0x5ACC: "font_draw_string 返回 pen 像素宽：li v0,1 → move v0,s6（错误路径仍返回 0）",
    0xA44C: "多字节入口重定向 0xA5BC → 0xA5B4（bnel 立即数 0x5B → 0x59）",
    0xA45C: "单字节入口重定向 0xA5B8 → 0xA5A8（bne 立即数 0x56 → 0x52）",
    0xA738: "等待光标 x = col + 8（原 17·col + 8）：sll a5,a3,4 → move a5,zero",
}

WHY = """正文列计数从"17 px 一格"改成"像素"，拉丁字母按字形真实步进（比例宽）推进；
名牌、卡名、正文三处从此同一步进。机制与字数预算见
docs/ops/eboot-kinsoku-research-2026-09-04.md §9；生成器 tools/msgcol_px.py（改 NEW_LISTING
后重跑，tests/test_msgcol_px.py 拿纯净源重推对账）。

- msg_col 存行内像素 x（0..425 = 25 格 × 17）。汉字步进 17 = 一格，不含 ASCII 的文本
  版面逐像素不变；"Ayano" 从 5 格 85 px 变成约 48 px。
- 行末禁则 col ≥ 392（原 col == 24）；行头禁则 col + est ≥ 426（原 col ≥ 25），est 由入口
  决定：单字节 9、多字节 17（画之前拿不到真实步进，只能估；误差落进悬挂区）。
- 画在 x = col + 4，然后 col += font_draw_string 返回的 pen（真实步进）。
- ruby 组先画 base 取宽 w，再按 col + (w − 5u)/2 + 4 画注音，col += w；base 从此可含 ASCII。
- 等待光标 x = col + 8。backlog 复用同一函数，自动一致。
- 0xA50C–0xA67C 93 字整段重排（0xA508 的 sll 归 ruby-p5 层）；带重定位的 13 个字里 12 个
  搬了位置，对应条目只改 r_offset、不改顺序（HI16/LO16 按表内先后配对）。
校验器 tools/msg_layout_check.py 的像素模型与 LATIN_EST_PX/CJK_EST_PX/LINE_PX 三个常数
由 tests/test_msgcol_px.py 钉住与本层一致。"""


def _hex_block(b: bytes, per_line: int = 16) -> str:
    lines = [b[i:i + per_line].hex(" ") for i in range(0, len(b), per_line)]
    return '"""\n    ' + "\n    ".join(lines) + '"""'


def render_layer(pristine: bytes) -> str:
    """从纯净 ELF 取锚点、汇编新代码，返回 layers/eboot/msgcol-px.toml 全文。"""
    lo = REGION_VA + FILE_BASE
    region_from = pristine[lo:lo + REGION_WORDS * 4]
    if region_from != asm.assemble(PRISTINE_LISTING, REGION_VA):
        raise SystemExit("纯净源与 PRISTINE_LISTING 不符：源文件不是登记的 EBOOT，或转写有错")
    region_to = asm.assemble(NEW_LISTING, REGION_VA)
    assert len(region_to) == len(region_from)
    out = [f'why = """{WHY}"""', 'profile = "release"', ""]
    out += ["[[patches]]", f'va   = "{REGION_VA:#06X}"',
            'note = "msg_layout_step 0xA50C–0xA67C 整段重排：ruby 先画 base 取宽、正文列计数改像素、col += 真实步进"',
            f"from = {_hex_block(region_from)}", f"to   = {_hex_block(region_to)}", ""]
    for va, line in SINGLE.items():
        src = pristine[va + FILE_BASE:va + FILE_BASE + 4]
        dst = asm.assemble([line], va)
        out += ["[[patches]]", f'va   = "{va:#06X}"', f'note = "{SINGLE_NOTE[va]}"',
                f'from = "{src.hex(" ")}"', f'to   = "{dst.hex(" ")}"', ""]
    for off, (old_va, new_va) in RELOC_MOVES.items():
        r_off, r_info = struct.unpack_from("<II", pristine, off)
        if r_off != old_va:
            raise SystemExit(f"重定位条目 {off:#x} 的 r_offset 是 {r_off:#x}，不是登记的 {old_va:#x}")
        out += ["[[patches]]", f'off  = "{off:#06X}"',
                f'note = "重定位条目 r_offset {old_va:#X} → {new_va:#X}（type {r_info & 0xFF} 不变）"',
                f'from = "{struct.pack("<I", old_va).hex(" ")}"', f'to   = "{struct.pack("<I", new_va).hex(" ")}"', ""]
    return "\n".join(out)


def main(argv=None) -> int:
    src = REPO / "assets" / "EBOOT.dec.elf"
    if not src.exists():
        print(f"缺 {src}（解密 EBOOT，本机资产）", file=sys.stderr)
        return 2
    text = render_layer(src.read_bytes())
    LAYER.write_text(text, encoding="utf-8")
    print(f"写出 {LAYER.relative_to(REPO)}（{len(text)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
