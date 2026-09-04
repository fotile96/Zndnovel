#!/usr/bin/env python3
"""Pluto 存档尺寸：静态估算（读 Lua 5.1 字节码）与实测转储解析（读模拟器转出的存档结构）。

背景（docs/ops/eboot-savedata-research-2026-09-05.md）：游戏用 Pluto 把正在运行的
`mainThread` 协程整个序列化进存档——协程栈上挂着章节脚本的主 chunk 闭包，Pluto 会把
它的整棵 Proto 树（全部指令 + 常量 = 整份脚本）写进去。引擎给线程 blob 的定长区只有
0x50000 = 327680 B，写入回调无边界检查，超过即溢出砸坏后续字段乃至全局。

    uv run python tools/pluto_size.py estimate build/release/members/script/*.lua
    uv run python tools/pluto_size.py estimate --members build/databin/script      # 原版基座
    uv run python tools/pluto_size.py parse-dump build/emu/drives/save_probe/savestruct_s1s_20.bin

estimate：按引擎里 Pluto 的写出规则（见 _persist_* 系列，逐字段对照 EBOOT 0x39A08/0x390C8
的反编译）算出「主 chunk 闭包的 Proto 树」被持久化后的字节数。这是线程 blob 的大头；
栈上其余东西（snr_common 里 vms 等闭包的 Proto、CallInfo、局部值）另算成 --extra 常数，
默认值来自 2026-09-05 的实测差值。

parse-dump：解析 save_probe.py 转出的 406120 B 结构，按 Pluto 流格式逐对象走一遍，
核对 size 字段并给出分类占比（Proto 指令 / 常量字符串 / 其他）。
"""
from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

THREAD_CAP = 0x50000        # 0x33572C..0x38572C（IDA 地址；运行时减 0x6DA40 加 0x08804000）
# 实测（2026-09-05）：线程 blob 与"主 chunk 闭包 Proto 树"估算之差——s1s_20 1674 B、s2s_10 5453 B、
# s7f-10 1831 B（栈上的值、CallInfo、vms 等 snr_common 闭包的 Proto）。缺省 extra 取 16 KiB（≈5% 容量）。
DEFAULT_EXTRA = 16384
GAMESAVE_CAP = 0x7800       # 0x32DF28..0x335728
STRUCT_SIZE = 0x63268
OFF_GAMESAVE = 0x480
OFF_GAMESAVE_SIZE = 0x7C80
OFF_THREAD = 0x7C84
OFF_THREAD_SIZE = 0x57C84

LUA_TNIL, LUA_TBOOLEAN, LUA_TLIGHTUSERDATA, LUA_TNUMBER, LUA_TSTRING = 0, 1, 2, 3, 4
LUA_TTABLE, LUA_TFUNCTION, LUA_TUSERDATA, LUA_TTHREAD, LUA_TPROTO, LUA_TUPVAL = 5, 6, 7, 8, 9, 10
PLUTO_TPERMANENT = 101

# ---------------------------------------------------------------- Lua 5.1 bytecode


@dataclass
class Proto:
    source: bytes | None
    linedefined: int
    lastlinedefined: int
    nups: int
    numparams: int
    is_vararg: int
    maxstacksize: int
    code: list[int]
    consts: list[tuple[int, object]]      # (type, value)
    protos: list["Proto"]
    lineinfo: list[int]
    locvars: list[tuple[bytes, int, int]]
    upvalues: list[bytes]

    def walk(self):
        yield self
        for p in self.protos:
            yield from p.walk()


class _Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.d, self.pos = data, pos

    def u8(self) -> int:
        v = self.d[self.pos]
        self.pos += 1
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.d, self.pos)[0]
        self.pos += 4
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.d, self.pos)[0]
        self.pos += 4
        return v

    def f64(self) -> float:
        v = struct.unpack_from("<d", self.d, self.pos)[0]
        self.pos += 8
        return v

    def raw(self, n: int) -> bytes:
        v = self.d[self.pos:self.pos + n]
        if len(v) != n:
            raise ValueError(f"truncated at {self.pos:#x}")
        self.pos += n
        return v

    def lstring(self) -> bytes | None:
        n = self.u32()
        if n == 0:
            return None
        return self.raw(n)[:-1]          # 字节码里的长度含结尾 NUL


def parse_bytecode(data: bytes) -> Proto:
    if data[:4] != b"\x1bLua" or data[4] != 0x51:
        raise ValueError("not Lua 5.1 bytecode")
    ver, fmt, endian, szint, szt, szins, sznum, integral = data[4:12]
    if (endian, szint, szt, szins, sznum, integral) != (1, 4, 4, 4, 8, 0):
        raise ValueError(f"unexpected header {data[4:12].hex()}（本工具只认 PSP 版：LE/int4/size_t4/double）")
    r = _Reader(data, 12)

    def func() -> Proto:
        src = r.lstring()
        ld, lld = r.i32(), r.i32()
        nups, np_, va, mss = r.u8(), r.u8(), r.u8(), r.u8()
        n = r.u32()
        code = list(struct.unpack_from(f"<{n}I", r.d, r.pos))
        r.pos += 4 * n
        consts: list[tuple[int, object]] = []
        for _ in range(r.u32()):
            t = r.u8()
            if t == LUA_TNIL:
                consts.append((t, None))
            elif t == LUA_TBOOLEAN:
                consts.append((t, bool(r.u8())))
            elif t == LUA_TNUMBER:
                consts.append((t, r.f64()))
            elif t == LUA_TSTRING:
                consts.append((t, r.lstring() or b""))
            else:
                raise ValueError(f"bad constant type {t} at {r.pos:#x}")
        protos = [func() for _ in range(r.u32())]
        lineinfo = [r.i32() for _ in range(r.u32())]
        locvars = [(r.lstring() or b"", r.i32(), r.i32()) for _ in range(r.u32())]
        upvalues = [r.lstring() or b"" for _ in range(r.u32())]
        return Proto(src, ld, lld, nups, np_, va, mss, code, consts, protos, lineinfo, locvars, upvalues)

    p = func()
    if r.pos != len(data):
        raise ValueError(f"trailing bytes: {len(data) - r.pos}")
    return p


# ---------------------------------------------------------------- Pluto 写出规则（引擎版）


@dataclass
class Estimate:
    total: int = 0
    code: int = 0            # 指令字节（4×sizecode）
    strings: int = 0         # 首次出现的字符串常量 payload（4+len）
    numbers: int = 0
    refs: int = 0            # 重复对象的 (0,ref) 8 B
    protos: int = 0
    consts: int = 0
    seen: set = field(default_factory=set)

    def _persist_hdr(self, key) -> bool:
        """persist() 头部：已见→写 8 B 引用并返回 False；未见→写 12 B (1,counter,type) 并登记。"""
        if key in self.seen:
            self.total += 8
            self.refs += 8
            return False
        self.seen.add(key)
        self.total += 12
        return True

    def persist_const(self, t: int, v) -> None:
        self.consts += 1
        if t == LUA_TNIL:
            self.total += 8
        elif t == LUA_TBOOLEAN:
            if self._persist_hdr(("b", v)):
                self.total += 4
        elif t == LUA_TNUMBER:
            if self._persist_hdr(("n", v)):
                self.total += 8
                self.numbers += 8
        elif t == LUA_TSTRING:
            if self._persist_hdr(("s", v)):
                self.total += 4 + len(v)
                self.strings += 4 + len(v)
        else:
            raise ValueError(t)

    def persist_proto(self, p: Proto, source_key=("s", b"=?")) -> None:
        if not self._persist_hdr(("p", id(p))):
            return
        self.protos += 1
        self.total += 4
        for t, v in p.consts:
            self.persist_const(t, v)
        self.total += 4
        for sp in p.protos:
            self.persist_proto(sp, source_key)
        self.total += 4 + 4 * len(p.code)
        self.code += 4 * len(p.code)
        self.total += 4
        for name in p.upvalues:
            self.persist_const(LUA_TSTRING, name)
        self.total += 4
        for name, _, _ in p.locvars:
            self.persist_const(LUA_TSTRING, name)
            self.total += 8
        # source：strip 后 luaU_undump 给顶层 "=?"，子 Proto 继承同一 TString
        src = p.source if p.source is not None else source_key[1]
        self.persist_const(LUA_TSTRING, src)
        self.total += 4 + 4 * len(p.lineinfo)
        self.total += 8            # linedefined, lastlinedefined
        self.total += 4            # nups, numparams, is_vararg, maxstacksize

    def persist_main_closure(self, p: Proto) -> None:
        """栈上主 chunk 闭包：persist 头 12 + nups 1 + Proto 树 + fenv(nil) 8。"""
        self._persist_hdr(("f", id(p)))
        self.total += 1
        self.persist_proto(p)
        self.total += 8


def estimate_file(path: Path) -> tuple[int, Estimate, Proto]:
    data = path.read_bytes()
    p = parse_bytecode(data)
    est = Estimate()
    est.persist_main_closure(p)
    return len(data), est, p


# ---------------------------------------------------------------- 实测转储解析


@dataclass
class DumpStats:
    consumed: int = 0
    objects: int = 0
    refs: int = 0
    by_type: dict = field(default_factory=dict)
    proto_code: int = 0
    proto_consts_strings: int = 0
    strings: int = 0
    perms: list = field(default_factory=list)
    stack_items: int = 0
    frames: int = 0
    protos: int = 0
    top_types: list = field(default_factory=list)
    stack_sizes: list = field(default_factory=list)   # 线程栈上每一项 (type, bytes)，自栈顶向下


class PlutoStream:
    """按引擎 Pluto（EBOOT 0x39A08 及各 persist_*）的写出顺序逐对象读回，只做计数不重建对象。"""

    def __init__(self, data: bytes, start: int, limit: int):
        self.r = _Reader(data, start)
        self.start, self.limit = start, start + limit
        self.st = DumpStats()
        self.reftypes: dict[int, int] = {}
        self.depth = 0

    def _add(self, t: int, n: int) -> None:
        self.st.by_type[t] = self.st.by_type.get(t, 0) + n

    def persist(self) -> tuple[str, int]:
        """返回 (kind, type)：kind ∈ {'nil','ref','obj'}。"""
        r = self.r
        p0 = r.pos
        first = r.i32()
        if first == 0:
            ref = r.i32()
            if ref == 0:
                return ("nil", LUA_TNIL)
            self.st.refs += 1
            return ("ref", self.reftypes.get(ref, -1))
        counter = r.i32()
        t = r.i32()
        self.st.objects += 1
        if t == PLUTO_TPERMANENT:
            k0 = r.pos
            kind, kt = self.persist()
            key = self.r.d[k0:self.r.pos]
            self.st.perms.append(key[16:].decode("utf-8", "replace") if kind == "obj" else "<ref>")
            self.reftypes[counter] = t
            self._add(t, r.pos - p0)
            return ("obj", t)
        self.reftypes[counter] = t
        if self.depth == 0:
            self.st.top_types.append(t)
        self.depth += 1
        try:
            self._payload(t)
        finally:
            self.depth -= 1
        self._add(t, r.pos - p0)
        return ("obj", t)

    def _payload(self, t: int) -> None:
        r = self.r
        if t == LUA_TBOOLEAN:
            r.i32()
        elif t == LUA_TLIGHTUSERDATA:
            r.u32()
        elif t == LUA_TNUMBER:
            r.f64()
        elif t == LUA_TSTRING:
            n = r.i32()
            r.raw(n)
            self.st.strings += 4 + n
        elif t == LUA_TTABLE:
            special = r.i32()
            if special:
                self.persist()          # __persist 返回的闭包
                return
            self.persist()              # metatable / nil
            while True:
                kind, _ = self.persist()    # key
                if kind == "nil":
                    break
                self.persist()          # value
        elif t == LUA_TFUNCTION:
            nups = r.u8()
            self.persist()              # proto
            for _ in range(nups):
                self.persist()          # upval
            self.persist()              # fenv / nil
        elif t == LUA_TUSERDATA:
            special = r.i32()
            if not special:
                raise ValueError("userdata without __persist")
            self.persist()
        elif t == LUA_TTHREAD:
            n = r.i32()
            self.st.stack_items = n
            for _ in range(n):
                p0 = r.pos
                kind, kt = self.persist()
                self.st.stack_sizes.append((kind if kind != "obj" else TYPE_NAMES.get(kt, kt), r.pos - p0))
            nframes = r.i32()
            self.st.frames = nframes
            r.raw(20 * nframes)
            r.u8()                      # status
            r.raw(12)                   # base, top, errfunc
            while True:
                kind, _ = self.persist()    # open upval / nil
                if kind == "nil":
                    break
                r.i32()                 # stackpos
        elif t == LUA_TPROTO:
            self.st.protos += 1
            nk = r.i32()
            for _ in range(nk):
                p0 = r.pos
                kind, kt = self.persist()
                if kind == "obj" and kt == LUA_TSTRING:
                    self.st.proto_consts_strings += r.pos - p0
            np_ = r.i32()
            for _ in range(np_):
                self.persist()
            ncode = r.i32()
            r.raw(4 * ncode)
            self.st.proto_code += 4 * ncode
            nupn = r.i32()
            for _ in range(nupn):
                self.persist()
            nloc = r.i32()
            for _ in range(nloc):
                self.persist()
                r.raw(8)
            self.persist()              # source
            nline = r.i32()
            r.raw(4 * nline)
            r.raw(8)                    # linedefined, lastlinedefined
            r.raw(4)                    # nups numparams is_vararg maxstacksize
        elif t == LUA_TUPVAL:
            self.persist()
        else:
            raise ValueError(f"unknown pluto type {t} at {r.pos:#x}")

    def run(self) -> DumpStats:
        self.persist()
        self.st.consumed = self.r.pos - self.start
        return self.st


TYPE_NAMES = {0: "nil", 1: "boolean", 2: "lightuserdata", 3: "number", 4: "string", 5: "table",
              6: "function", 7: "userdata", 8: "thread", 9: "proto", 10: "upval", 101: "PERMANENT"}


def cmd_estimate(a: argparse.Namespace) -> int:
    files: list[Path] = []
    if a.members:
        files += sorted(Path(a.members).glob("*.lua"))
    files += [Path(f) for f in a.files]
    if not files:
        sys.exit("没有输入文件")
    rows = []
    for f in files:
        try:
            size, est, p = estimate_file(f)
        except ValueError as e:
            print(f"{f.name}: 跳过（{e}）", file=sys.stderr)
            continue
        total = est.total + a.extra
        rows.append((total, f.name, size, est))
    rows.sort(reverse=True)
    print(f"{'脚本':28s} {'字节码':>8s} {'Proto树':>8s} {'+extra':>8s} {'占线程区':>7s}  备注")
    worst = 0
    for total, name, size, est in rows:
        pct = 100.0 * total / THREAD_CAP
        worst = max(worst, total)
        flag = "  ⚠ 超容量" if total > THREAD_CAP else ("  ！>80%" if pct > 80 else "")
        print(f"{name:28s} {size:8d} {est.total:8d} {total:8d} {pct:6.1f}%{flag}")
    print(f"线程 blob 容量 {THREAD_CAP} B；extra = {a.extra} B；最大 {worst} B（余量 {THREAD_CAP - worst} B）")
    return 1 if worst > THREAD_CAP else 0


def cmd_parse_dump(a: argparse.Namespace) -> int:
    d = Path(a.dump).read_bytes()
    if len(d) != STRUCT_SIZE:
        print(f"⚠ 转储长度 {len(d)} ≠ {STRUCT_SIZE}", file=sys.stderr)
    title = d[:0x80].split(b"\0")[0].decode("utf-8", "replace")
    chapter = d[0x80:0x100].split(b"\0")[0].decode("utf-8", "replace")
    print(f"title={title!r} chapter={chapter!r}")
    gs_size = struct.unpack_from("<I", d, OFF_GAMESAVE_SIZE)[0]
    th_size = struct.unpack_from("<I", d, OFF_THREAD_SIZE)[0]
    print(f"gameSave blob: {gs_size} B / {GAMESAVE_CAP} B ({100.0 * gs_size / GAMESAVE_CAP:.1f}%)")
    print(f"mainThread blob: {th_size} B / {THREAD_CAP} B ({100.0 * th_size / THREAD_CAP:.1f}%)")
    for label, off, size in (("gameSave", OFF_GAMESAVE, gs_size), ("mainThread", OFF_THREAD, th_size)):
        ps = PlutoStream(d, off, size)
        try:
            st = ps.run()
        except Exception as e:      # noqa: BLE001
            print(f"[{label}] 解析失败 @ {ps.r.pos - off:#x}: {e}")
            continue
        ok = "✓" if st.consumed == size else f"✗ (size 字段 {size})"
        print(f"\n[{label}] 流长 {st.consumed} B {ok}；对象 {st.objects}，引用 {st.refs}，"
              f"Proto {st.protos}，栈项 {st.stack_items}，CallInfo {st.frames}")
        if st.perms:
            print(f"  perms 引用: {sorted(set(st.perms))}")
        print(f"  Proto 指令字节 {st.proto_code}；Proto 字符串常量（含头）{st.proto_consts_strings}；"
              f"字符串 payload 合计 {st.strings}")
        top = [TYPE_NAMES.get(t, t) for t in st.top_types]
        print(f"  顶层对象类型: {top[:12]}{' …' if len(top) > 12 else ''}")
        if st.stack_sizes:
            items = ", ".join(f"{t}:{n}" for t, n in st.stack_sizes)
            print(f"  线程栈项（栈顶→栈底）字节: {items}")
        print("  按类型（含子对象）字节: " + ", ".join(
            f"{TYPE_NAMES.get(t, t)}={n}" for t, n in sorted(st.by_type.items(), key=lambda kv: -kv[1])[:8]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("estimate", help="按字节码估算主 chunk 闭包持久化字节数")
    e.add_argument("files", nargs="*")
    e.add_argument("--members", help="目录：其中全部 *.lua 字节码")
    e.add_argument("--extra", type=int, default=DEFAULT_EXTRA,
                   help=f"栈上其余对象的经验常数（B，缺省 {DEFAULT_EXTRA}），实测差值见研究记录")
    e.set_defaults(fn=cmd_estimate)
    p = sub.add_parser("parse-dump", help="解析 save_probe.py 转出的存档结构")
    p.add_argument("dump")
    p.set_defaults(fn=cmd_parse_dump)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
