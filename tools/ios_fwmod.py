#!/usr/bin/env python3
"""iOS 变体用的固件模块补丁：libmp4.prx / mp4msv.prx（本作 UMD 自带 6.20 升级包解密出的 Sony 模块）。

为什么（docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」M1–M3）：
  M1 PPSSPP 1.20.x 的 HLE 表里有 sceMp4/mp4msv（空桩），EBOOT 的导入会被钉死在上面。两侧改库名
     （sceMp4→zndMp4、mp4msv→zndmsv，同长度原地改）后，1.20.x 把导入暂存、真模块加载时补绑。
  M2 1.20.x 的 sceAudiocodecDecode 拿输出字段 srcBytesRead(0x1C) 当 AAC 输入长度，首帧为 0 → 永远静音。
     把 0x487C 的 jal sceAudiocodecDecode 改指向跳板（游戏不用的导出 sceMp4GetAvcAuWithoutSampleBuf 入口
     0x6054，前 14 字无重定位）：srcBytesRead = byte[0x2C] ? 0x609 : 0x600（同上游 b561de3f），再 b 回导入桩。
  M3 ModuleMgrForUser::0xD2FBC957（取回调 gp，1.20.x 缺）导入计数清零、桩改 jr ra; li v0,-1 → libmp4 走
     自带兜底（取当前 gp）。

输入（解密原件，版权物，不入库）与输出的 sha256 都钉在本文件常量里；原件放 assets/fw/，取得方法见
movie-playback 文档「固件模块的取得」。

用法：uv run python tools/ios_fwmod.py build [--out build/ios/module]
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.mips_asm import assemble  # noqa: E402

LIBMP4_IN_SHA = "ffa4c7e46f0be68e653b7230e39049b78013b8172bb43f5482bae5d7f10c240e"
MP4MSV_IN_SHA = "f9639c746ba4690cfea0342bdd62ad3c68f2d911a5985c4303d200b08a880bf5"
LIBMP4_OUT_SHA = "55916c14e7eee56a13f33af0e82eed9145ee328cc249bfdccedec36999908298"
MP4MSV_OUT_SHA = "cf9e3df024f7a56544bcb5146cd12155387e857caa4e5ab4db0b7750500c5ccd"
LIB_EXPORT, MSV_EXPORT = "zndMp4", "zndmsv"

AAC_CALL, AAC_STUB, TRAMP = 0x487C, 0x7450, 0x6054
GP_NID, GP_STUB = 0xD2FBC957, 0x72A8


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ph(b: bytes) -> list[tuple]:
    phoff, = struct.unpack_from("<I", b, 0x1C)
    phnum, = struct.unpack_from("<H", b, 0x2C)
    return [struct.unpack_from("<8I", b, phoff + 32 * i) for i in range(phnum)]


def text_off(b: bytes) -> int:
    """段 0 的文件偏移：PRX 以 0 为基址，段 0 内 VA + 此值 = 文件偏移。"""
    return _ph(b)[0][1]


def _modinfo(b: bytes) -> tuple[int, int, int, int]:
    mi = _ph(b)[0][3] & 0x7FFFFFFF                # 段 0 的 p_paddr = sceModuleInfo 的文件偏移
    _gp, et, ee, st, se = struct.unpack_from("<5I", b, mi + 32)
    return et, ee, st, se


def _cstr(b: bytes, va: int) -> str:
    o = text_off(b) + va
    return b[o:b.index(b"\0", o)].decode()


def exports(b: bytes) -> dict[str, dict]:
    et, ee, _, _ = _modinfo(b)
    out, va, t = {}, et, text_off(b)
    while va < ee:
        nm, _v, _a, elen, vc, fc, tab = struct.unpack_from("<IHHBBHI", b, t + va)
        if nm:                                      # 首条是模块自身的无名 syslib 表
            out[_cstr(b, nm)] = {"entry": va, "name_va": nm, "funcs": fc, "vars": vc, "tab": tab}
        va += elen * 4
    return out


def imports(b: bytes) -> dict[str, dict]:
    _, _, st, se = _modinfo(b)
    out, va, t = {}, st, text_off(b)
    while va < se:
        nm, _v, _a, elen, _vc, sc, nidtab, stubtab = struct.unpack_from("<IHHBBHII", b, t + va)
        out[_cstr(b, nm)] = {"entry": va, "name_va": nm, "count": sc, "nidtab": nidtab, "stubtab": stubtab}
        va += elen * 4
    return out


def relocs_b(b: bytes) -> list[tuple[int, int]]:
    """PT 0x700000A1（type-B）重定位解码，移植自 PPSSPP ElfReader::LoadRelocations2。

    返回 [(site_va, type)]；type：2=R32、4=HI16、5=LO16、6=J26、7=JAL26。"""
    ph = _ph(b)
    rel_seg = next(i for i, p in enumerate(ph) if p[0] == 0x700000A1)
    seg_va = [p[2] for p in ph]
    buf = b[ph[rel_seg][1]:ph[rel_seg][1] + ph[rel_seg][4]]
    flag_bits, type_bits = buf[2], buf[3]
    seg_bits = 1
    while (1 << seg_bits) < rel_seg:
        seg_bits += 1
    i = 4
    flag_table = buf[i:i + buf[i]]
    i += buf[i]
    type_table = buf[i:i + buf[i]]
    i += buf[i]
    rel_base = off_seg = 0
    out = []
    while i < len(buf):
        cmd = struct.unpack_from("<H", buf, i)[0]
        i += 2
        flag = flag_table[((cmd << (16 - flag_bits)) & 0xFFFF) >> (16 - flag_bits)]
        seg = ((cmd << (16 - seg_bits - flag_bits)) & 0xFFFF) >> (16 - seg_bits)
        typ = type_table[((cmd << (16 - type_bits - seg_bits - flag_bits)) & 0xFFFF) >> (16 - type_bits)]
        if (flag & 1) == 0:                          # 换基址段
            off_seg = seg
            if (flag & 6) == 0:
                rel_base = cmd >> (seg_bits + flag_bits)
            elif (flag & 6) == 4:
                rel_base = struct.unpack_from("<I", buf, i)[0]
                i += 4
            continue
        shift = type_bits + seg_bits + flag_bits
        signed = cmd - 0x10000 if cmd & 0x8000 else cmd
        if (flag & 6) == 0:
            rel_base += signed >> shift
        elif (flag & 6) == 2:
            rel_base += ((signed >> shift) << 16) | buf[i] | (buf[i + 1] << 8)
            i += 2
        elif (flag & 6) == 4:
            rel_base = struct.unpack_from("<I", buf, i)[0]
            i += 4
        if (flag & 0x38) == 0x10:
            i += 2                                   # 行内 lo16，本工具只需站点
        out.append(((rel_base + seg_va[off_seg]) & 0xFFFFFFFF, typ))
    return out


def _rename(b: bytearray, name_va: int, old: str, new: str) -> None:
    assert len(old) == len(new)
    o = text_off(b) + name_va
    if bytes(b[o:o + len(old) + 1]) != old.encode() + b"\0":
        raise ValueError(f"库名锚点不符：{name_va:#x} 处不是 {old!r}")
    b[o:o + len(new)] = new.encode()


def patch_mp4msv(data: bytes) -> bytes:
    if sha256(data) != MP4MSV_IN_SHA:
        raise ValueError("mp4msv 输入 sha256 与登记不符")
    b = bytearray(data)
    _rename(b, exports(data)["mp4msv"]["name_va"], "mp4msv", MSV_EXPORT)
    return bytes(b)


def patch_libmp4(data: bytes) -> bytes:
    if sha256(data) != LIBMP4_IN_SHA:
        raise ValueError("libmp4 输入 sha256 与登记不符")
    b = bytearray(data)
    t = text_off(data)
    rel = dict(relocs_b(data))
    _rename(b, exports(data)["sceMp4"]["name_va"], "sceMp4", LIB_EXPORT)
    _rename(b, imports(data)["mp4msv"]["name_va"], "mp4msv", MSV_EXPORT)
    # M2：AAC 输入长度跳板
    if any(TRAMP <= s < TRAMP + 32 for s in rel):
        raise ValueError("跳板区含重定位")
    lines = ["li t6, 0x600", "lbu t7, 0x2C(a0)", f"beqz t7, {TRAMP + 0x14:#x}", "nop",
             "li t6, 0x609", f"b {AAC_STUB:#x}", "sw t6, 0x1C(a0)"]
    for k, line in enumerate(lines):
        pc = TRAMP + 4 * k
        b[t + pc:t + pc + 4] = assemble([line], pc)
    old = struct.unpack_from("<I", b, t + AAC_CALL)[0]
    if rel.get(AAC_CALL) != 7 or old != (0x0C000000 | (AAC_STUB >> 2)):
        raise ValueError(f"{AAC_CALL:#x} 不是带 JAL26 重定位的 jal sceAudiocodecDecode")
    struct.pack_into("<I", b, t + AAC_CALL, 0x0C000000 | (TRAMP >> 2))
    # M3：0xD2FBC957 导入去掉、桩改 jr ra; li v0,-1
    mm = imports(data)["ModuleMgrForUser"]
    if mm["count"] != 1 or struct.unpack_from("<I", data, t + mm["nidtab"])[0] != GP_NID \
            or mm["stubtab"] != GP_STUB:
        raise ValueError("ModuleMgrForUser 导入不是预期的单条 0xD2FBC957")
    struct.pack_into("<H", b, t + mm["entry"] + 10, 0)
    struct.pack_into("<II", b, t + GP_STUB, 0x03E00008, 0x2402FFFF)
    return bytes(b)


def build(out_dir: Path, fw_dir: Path = REPO / "assets" / "fw") -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, fn, want in (("libmp4.prx", patch_libmp4, LIBMP4_OUT_SHA),
                           ("mp4msv.prx", patch_mp4msv, MP4MSV_OUT_SHA)):
        src = fw_dir / name.replace(".prx", ".dec.prx")
        if not src.exists():
            raise SystemExit(f"缺 {src}（取得方法见 docs/ops/movie-playback-ppsspp-2026-09-24.md「固件模块的取得」）")
        out = fn(src.read_bytes())
        if sha256(out) != want:
            raise SystemExit(f"{name} 产物 sha256 {sha256(out)} 与登记 {want} 不符")
        (out_dir / name).write_bytes(out)
        res[name] = out_dir / name
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--out", type=Path, default=REPO / "build" / "ios" / "module")
    a = ap.parse_args(argv)
    for k, v in build(a.out).items():
        print(f"{k} → {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
