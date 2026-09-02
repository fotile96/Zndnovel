#!/usr/bin/env -S uv run python
"""把 PSP luac（Lua 5.1, size_t=4, stripped）里的行号字段归零，用于跨基座逐字节比对。

为什么需要：`luac -s` 剥掉 debug 段，但**不剥** Proto 头部的 `linedefined` /
`lastlinedefined`——这两个 int 记的是函数在**源文件**里的行号。换反编译基座后打印
结构变了、行号自然不同，字节码却应当完全一样。把这两个字段归零后再比，就能判定
「除了行号，是不是同一份字节码」。

格式（lundump.c）：12 字节头 + 顶层 Proto。Proto =
  linedefined:int | lastlinedefined:int | nups:u8 | numparams:u8 | is_vararg:u8 |
  maxstacksize:u8 | code(int n + n×4B) | constants(int n + 逐个) |
  protos(int n + 递归) | debug(lineinfo/locvars/upvalues，stripped 后均为长度 0)
常量：1B 类型 + (nil 无体 / bool 1B / number 8B double / string 4B 长度+字节)。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

HEADER = bytes.fromhex("1b4c75615100010404040800")


class Reader:
    def __init__(self, data: bytes):
        self.d = bytearray(data)
        self.p = 0

    def u8(self) -> int:
        v = self.d[self.p]
        self.p += 1
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def skip(self, n: int) -> None:
        self.p += n


def norm_proto(r: Reader) -> None:
    # LoadFunction 的字段顺序（lundump.c）：source 先于 linedefined，最初漏掉这一项
    # 会让后续所有偏移全错。stripped 产物里 source 长度为 0。
    r.skip(r.i32())                               # source: size_t 长度 + 字节
    struct.pack_into("<ii", r.d, r.p, 0, 0)       # linedefined / lastlinedefined 归零
    r.skip(8)
    r.skip(4)                                     # nups/numparams/is_vararg/maxstacksize
    r.skip(r.i32() * 4)                           # code
    for _ in range(r.i32()):                      # constants
        t = r.u8()
        if t == 1:
            r.skip(1)
        elif t == 3:
            r.skip(8)
        elif t == 4:
            r.skip(r.i32())
        elif t != 0:
            raise ValueError(f"未知常量类型 {t} @ {r.p}")
    for _ in range(r.i32()):                      # 子 Proto（LoadConstants 尾部递归）
        norm_proto(r)
    r.skip(r.i32() * 4)                           # debug: lineinfo（stripped 后 n=0）
    for _ in range(r.i32()):                      # debug: locvars
        r.skip(r.i32())                           #   varname
        r.skip(8)                                 #   startpc/endpc
    for _ in range(r.i32()):                      # debug: upvalues
        r.skip(r.i32())


def normalize(data: bytes) -> bytes:
    if data[:12] != HEADER:
        raise ValueError("非 PSP ABI luac 头")
    r = Reader(data)
    r.skip(12)
    norm_proto(r)
    if r.p != len(data):
        raise ValueError(f"解析未覆盖全文件: {r.p} / {len(data)}")
    return bytes(r.d)


def compare_dirs(a: Path, b: Path) -> tuple[int, int, int, list[str]]:
    """逐同名 .lua 归一化后比对，返回 (相同, 不同, 解析失败, 有问题的文件名)。"""
    same = diff = err = 0
    bad: list[str] = []
    for pa in sorted(Path(a).glob("*.lua")):
        pb = Path(b) / pa.name
        if not pb.exists():
            continue
        try:
            if normalize(pa.read_bytes()) == normalize(pb.read_bytes()):
                same += 1
            else:
                diff += 1
                bad.append(pa.name)
        except Exception as exc:  # noqa: BLE001
            err += 1
            bad.append(f"{pa.name}: {exc}")
    return same, diff, err, bad


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("用法: luac_norm.py <目录A> <目录B>   # 逐同名文件归一化后比对")
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    same, diff, err, bad = compare_dirs(a, b)
    print(f"归一化后相同 {same}；不同 {diff}；解析失败 {err}")
    for x in bad[:10]:
        print("   ", x)


if __name__ == "__main__":
    main()
