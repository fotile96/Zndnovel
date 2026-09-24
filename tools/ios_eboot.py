#!/usr/bin/env python3
"""生成 layers/eboot/ios-movie.toml：iOS 变体（PPSSPP 1.20.x）播放 OP/ED 的四处 EBOOT 改动。

  E1 导入库名 sceMp4→zndMp4（VA 0x657D0），配合 tools/ios_fwmod.py 改过名的 libmp4。
  E2 洞（sceGumLookAt 0x624C8，零引用死代码）里写加载例程：bal 取 PC、addiu 算导入桩地址 jalr，
     依次 sceKernelLoadModule/StartModule disc0:/PSP_GAME/USRDIR/module/{mp4msv,libmp4}.prx；
     sub_B444 里 0xB470 的 jal sceUtilityLoadModule(0x308) 改指向这里；洞内被新代码覆盖的 HI16/LO16
     两个重定位条目（表项文件偏移 0x84188、0x84198）改 R_MIPS_NONE，与它们共用那个 LO16 的死代码 HI16
     （0x62B74，表项 0x84190）一并改 NONE——否则它成了悬空 HI16（见 RELOC_NONE 注释）。
  E3 sceMpegCreate 条件包装（0x6262C）：$a6（DecTopAddr）== 0x10000000（1.20.x HLE 伪值）才把 ringbuffer
     设为 mpeg 工作区 +0x7000；0xB4F4 的 jal 改指向它。
  E4 sceMpegAvcDecode 保 pts 包装（0x625D8）：存/恢复 AU 前 8 字节；0xEA94 的 jal 改指向它。
依据与实测：docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。代码逐条移植自实测通过的实验盘
（build/movie_debug/iosdisc），洞区与四处改动与之逐字节相同；重定位表比实验盘多 NONE 一条（0x84190，
悬空 HI16，2026-09-24 产品化驾驶时发现）。tests/test_ios_eboot.py 另核重定位。

用法：uv run python tools/ios_eboot.py      # 写 layers/eboot/ios-movie.toml
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.mips_asm import assemble  # noqa: E402

SRC = REPO / "assets" / "EBOOT.dec.elf"
LAYER = REPO / "layers" / "eboot" / "ios-movie.toml"
FILE_BASE = 0xC0                           # 段 0：VA 0 ↔ 文件偏移 0xC0
CAVE, WRAP_AVC, WRAP_CREATE = 0x624C8, 0x625D8, 0x6262C
STUB_LOAD, STUB_START, STUB_AVCDEC, STUB_CREATE = 0x65170, 0x65160, 0x65520, 0x65578
CALLS = {0xB470: CAVE, 0xB4F4: WRAP_CREATE, 0xEA94: WRAP_AVC}
CALL_OLD = {0xB470: 0x65230, 0xB4F4: STUB_CREATE, 0xEA94: STUB_AVCDEC}   # 0x65230 = sceUtilityLoadModule 桩
# 原表是 [HI16 0x62570, HI16 0x62B74, LO16 0x62574]：两个 HI16 共用一个 LO16。洞覆盖了 0x62570/0x62574，
# 这两条必须 NONE（否则装载器往新指令里加基址，实测砸过 lw 偏移）；0x62B74 在 sceGumLookAt 死代码里，
# 它的 LO16 一 NONE 就成了悬空 HI16——PPSSPP 记 ERROR 后拿后面别的 LO16 凑进位，实机装载器行为未知，
# 现行盘一个悬空 HI16 都没有，这里也不留：一并 NONE（死代码字不重定位，无害）。
RELOC_NONE = (0x84188, 0x84190, 0x84198)   # r_offset 0x62570（HI16）/0x62B74（HI16）/0x62574（LO16）
IMPORT_NAME_VA = 0x657D0
PATHS = (b"disc0:/PSP_GAME/USRDIR/module/mp4msv.prx\0", b"disc0:/PSP_GAME/USRDIR/module/libmp4.prx\0")


def _bal(pc: int, target: int) -> int:
    return (1 << 26) | (0x11 << 16) | (((target - (pc + 4)) >> 2) & 0xFFFF)   # bgezal zero


def _enc(lines: list, base: int) -> list[int]:
    """listing 元素：汇编文本，或 ("bal", 目标)/("bltz_v0", 目标)/("raw", 字)。"""
    out = []
    for i, x in enumerate(lines):
        pc = base + 4 * i
        if isinstance(x, tuple):
            kind, arg = x
            if kind == "bal":
                out.append(_bal(pc, arg))
            elif kind == "bltz_v0":
                out.append((1 << 26) | (2 << 21) | (((arg - (pc + 4)) >> 2) & 0xFFFF))
            else:
                out.append(arg)
        else:
            out.append(struct.unpack("<I", assemble([x], pc))[0])
    return out


def loader_listing() -> tuple[list, bytes]:
    """E2：两次 LoadModule+StartModule，任一返回负值即带着该错误码返回（游戏不查返回值）。"""
    l0 = CAVE + 6 * 4                      # bal 之后的 ra = 这里，s0 = 位置无关的基准
    n_words = 7 + 2 * 17 + 6
    s1 = CAVE + 4 * n_words
    s2 = s1 + len(PATHS[0])
    fail = CAVE + 4 * (n_words - 5)        # 「lw s1, 20(sp)」：跳过 move v0, zero，保留错误码
    src: list = ["addiu sp, sp, -32", "sw ra, 28(sp)", "sw s0, 24(sp)", "sw s1, 20(sp)",
                 ("bal", l0), "nop", "move s0, ra"]
    for s in (s1, s2):
        src += [f"addiu a0, s0, {s - l0}", "move a1, zero", "move a2, zero",
                f"addiu t9, s0, {STUB_LOAD - l0}", ("raw", 0x0320F809), "nop", ("bltz_v0", fail),
                "move a0, v0", "move a1, zero", "move a2, zero", "move a3, zero", "move a4, zero",
                f"addiu t9, s0, {STUB_START - l0}", ("raw", 0x0320F809), "nop", ("bltz_v0", fail), "nop"]
    src += ["move v0, zero", "lw s1, 20(sp)", "lw s0, 24(sp)", "lw ra, 28(sp)", ("raw", 0x03E00008),
            "addiu sp, sp, 32"]
    assert len(src) == n_words
    return src, PATHS[0] + PATHS[1]


def avc_listing() -> list:
    """E4：调用前把 AU 前 8 字节（pts）存栈上，调用后写回。"""
    l2 = WRAP_AVC + 10 * 4
    return ["addiu sp, sp, -16", "sw ra, 12(sp)", "sw s0, 8(sp)", "lw t4, 0(a1)", "lw t5, 4(a1)",
            "sw t4, 0(sp)", "sw t5, 4(sp)", "move s0, a1", ("bal", l2), "nop",
            f"addiu t9, ra, {STUB_AVCDEC - l2}", ("raw", 0x0320F809), "nop", "lw t4, 0(sp)", "lw t5, 4(sp)",
            "sw t4, 0(s0)", "sw t5, 4(s0)", "lw s0, 8(sp)", "lw ra, 12(sp)", ("raw", 0x03E00008),
            "addiu sp, sp, 16"]


def create_listing() -> list:
    """E3：$a6 == 0x10000000 时 a3 = a1 + 0x7000，然后尾调 sceMpegCreate 桩（ra 在延迟槽里还原）。"""
    l3 = WRAP_CREATE + 0x1C
    return ["lui t4, 0x1000", f"bne a6, t4, {WRAP_CREATE + 0x10:#x}", "nop", "addiu a3, a1, 0x7000",
            "move t5, ra", ("bal", l3), "nop", f"addiu t9, ra, {STUB_CREATE - l3}", ("raw", 0x03200008),
            "move ra, t5"]


CREATE_LISTING = create_listing()


def cave_bytes(pristine: bytes) -> bytes:
    """洞区新内容。路径串末尾到 WRAP_AVC 之间的对齐空隙保留原字节（与实测盘逐字节相同；永不被读）。"""
    loader, strings = loader_listing()
    blob = b"".join(struct.pack("<I", w) for w in _enc(loader, CAVE)) + strings
    assert CAVE + len(blob) <= WRAP_AVC
    blob += pristine[CAVE + FILE_BASE + len(blob):WRAP_AVC + FILE_BASE]
    blob += b"".join(struct.pack("<I", w) for w in _enc(avc_listing(), WRAP_AVC))
    assert CAVE + len(blob) == WRAP_CREATE
    blob += b"".join(struct.pack("<I", w) for w in _enc(CREATE_LISTING, WRAP_CREATE))
    return blob


def _hex(b: bytes) -> str:
    return "\n" + "\n".join("    " + b[i:i + 16].hex(" ") for i in range(0, len(b), 16)) + "\n"


WHY = """iOS 变体（仅推荐 iOS 商店版 PPSSPP 1.20.x）播放 OP/ED：配合 tools/ios_fwmod.py 改过库名的固件
libmp4/mp4msv（EBOOT 自行从盘上加载）与 tools/ios_movie.py 的 44.1k 影片。E1 导入改名、E2 洞内加载例程
（sceGumLookAt 死代码；洞内 HI16/LO16 及共用该 LO16 的死代码 HI16 共三条重定位改 NONE）、E3 sceMpegCreate
条件假 ringbuffer（仅 1.20.x HLE 的 DecTopAddr 伪值 0x10000000 生效）、E4 sceMpegAvcDecode 保 pts。
只在 build_disc.py --ios 施加。
生成器 tools/ios_eboot.py；依据 docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。"""


def render_layer(pristine: bytes) -> str:
    def at(va, n):
        return pristine[va + FILE_BASE: va + FILE_BASE + n]
    new_cave = cave_bytes(pristine)
    parts = [f'why = """{WHY}"""\nprofile = "ios"\n']

    def patch(key, where, frm, to, note):
        parts.append(f'\n[[patches]]\n{key} = "{where:#x}"\nnote = "{note}"\n'
                     f'from = """{_hex(frm)}"""\nto   = """{_hex(to)}"""\n')

    patch("va", IMPORT_NAME_VA, at(IMPORT_NAME_VA, 7), b"zndMp4\0", "E1 导入库名 sceMp4→zndMp4")
    patch("va", CAVE, at(CAVE, len(new_cave)), new_cave,
          "E2 加载例程 + 路径串 / E4 保 pts 包装 / E3 条件 ringbuffer 包装（覆盖 sceGumLookAt 死代码）")
    for site, target in CALLS.items():
        old = struct.unpack("<I", at(site, 4))[0]
        assert old == 0x0C000000 | (CALL_OLD[site] >> 2), f"{site:#x} 不是预期的 jal"
        patch("va", site, at(site, 4), struct.pack("<I", 0x0C000000 | (target >> 2)),
              f"jal {CALL_OLD[site]:#x} → {target:#x}（R_MIPS_26 条目保留，目标仍在段内）")
    for fo in RELOC_NONE:
        entry = pristine[fo:fo + 8]
        assert entry[4] in (5, 6), f"表项 {fo:#x} 不是 HI16/LO16"
        patch("off", fo, entry, entry[:4] + b"\0" + entry[5:], "洞内被覆盖字（及共用其 LO16 的死代码 HI16）的重定位条目 → R_MIPS_NONE")
    return "".join(parts)


def main() -> int:
    LAYER.write_text(render_layer(SRC.read_bytes()), encoding="utf-8")
    print(f"写出 {LAYER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
