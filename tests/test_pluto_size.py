"""tools/pluto_size.py：Pluto 存档尺寸估算与转储解析。

规则出处 docs/ops/eboot-savedata-research-2026-09-05.md（EBOOT 0x39A08 persist 与
0x390C8 persistproto 的反编译）。estimate 的用例需要 layers/manifest.toml 里的 luac_sz4，
缺则跳过；parse 的用例用手工拼的 Pluto 流，不依赖任何外部件。
"""
import os
import struct
import subprocess
import tomllib
from pathlib import Path

import pytest

from tools import pluto_size as ps

REPO = Path(__file__).resolve().parents[1]


def _luac() -> Path | None:
    manifest = tomllib.loads((REPO / "layers" / "manifest.toml").read_text(encoding="utf-8"))
    luac = Path(os.environ.get("SNDL_LUAC") or manifest["compiler"]["luac"]).expanduser()
    return luac if luac.exists() else None


def _compile(tmp_path: Path, src: str, name: str = "t.lua") -> bytes:
    luac = _luac()
    if luac is None:
        pytest.skip("缺 luac_sz4")
    s = tmp_path / name
    s.write_text(src, encoding="utf-8")
    out = tmp_path / (name + "c")
    subprocess.run([str(luac), "-s", "-o", str(out), str(s)], check=True, capture_output=True)
    return out.read_bytes()


# ---- 常数钉合 --------------------------------------------------------------

def test_capacities_match_engine_layout():
    # 存档结构 0x32DAA8（IDA）：+0x480 gameSave blob，size 在 +0x7C80；+0x7C84 线程 blob，size 在 +0x57C84
    assert ps.OFF_GAMESAVE_SIZE - ps.OFF_GAMESAVE == ps.GAMESAVE_CAP == 0x7800
    assert ps.OFF_THREAD_SIZE - ps.OFF_THREAD == ps.THREAD_CAP == 0x50000
    assert ps.STRUCT_SIZE == 0x63268
    assert ps.DEFAULT_EXTRA >= 5453          # 2026-09-05 三场景实测差值上限（s2s_10），余量只能加不能减


# ---- 字节码解析与估算 ------------------------------------------------------

def test_minimal_chunk_estimate_is_exact(tmp_path):
    """`return`：无常量、无子 Proto（luac 会给出两条 RETURN）。
    闭包 12+1 + Proto(12 + 4 sizek + 4 sizep + 4 sizecode + 4·n + 4 upvalues + 4 locvars
    + "=?" 18 + 4 lineinfo + 8 linedefined + 4 misc) + fenv 8 = 87 + 4·n。"""
    data = _compile(tmp_path, "return\n")
    p = ps.parse_bytecode(data)
    assert p.consts == [] and p.protos == []
    assert p.lineinfo == [] and p.locvars == [] and p.upvalues == [] and p.source is None
    est = ps.Estimate()
    est.persist_main_closure(p)
    assert est.total == 87 + 4 * len(p.code)


def test_string_constants_dedupe_and_cost(tmp_path):
    """常量首次出现 = 12 头 + 4 长度 + 串；再次出现 = 8 B 引用；指令 4 B/条。"""
    a = ps.parse_bytecode(_compile(tmp_path, 'x = "aaaa"\n', "a.lua"))
    b = ps.parse_bytecode(_compile(tmp_path, 'x = "aaaa"\ny = "bbbbbbbbbb"\n', "b.lua"))
    ea, eb = ps.Estimate(), ps.Estimate()
    ea.persist_main_closure(a)
    eb.persist_main_closure(b)
    d_code = 4 * (len(b.code) - len(a.code))
    # b 多两个常量：'y'（12+4+1）与 10 字节串（12+4+10）
    assert eb.total - ea.total == d_code + 17 + 26
    # 同一 Proto 内 luac 已把相同常量合并；跨 Proto 的相同字符串（Lua 全部内部化）
    # 在 Pluto 里第二次只付 8 B 引用：子函数里的 "aaaa" 对比 "bbbb"（新串 12+4+4=20）差 12 B
    c = ps.parse_bytecode(_compile(tmp_path, 'x = "aaaa"\nf = function() return "aaaa" end\n', "c.lua"))
    d = ps.parse_bytecode(_compile(tmp_path, 'x = "aaaa"\nf = function() return "bbbb" end\n', "d.lua"))
    assert len(c.protos) == 1 and c.protos[0].consts == [(ps.LUA_TSTRING, b"aaaa")]
    ec, ed = ps.Estimate(), ps.Estimate()
    ec.persist_main_closure(c)
    ed.persist_main_closure(d)
    assert ed.total - ec.total == 20 - 8 and ec.refs == 8 * 2      # "aaaa" 与 "=?" 各一次引用


def test_nested_protos_share_source_string(tmp_path):
    src = "local function f() return 1 end\nlocal function g() return 2 end\nreturn f, g\n"
    p = ps.parse_bytecode(_compile(tmp_path, src))
    assert len(p.protos) == 2
    est = ps.Estimate()
    est.persist_main_closure(p)
    assert est.protos == 3
    # "=?" 只付一次 18 B，另两次各 8 B 引用
    assert ("s", b"=?") in est.seen


def test_estimate_file_rejects_non_bytecode(tmp_path):
    f = tmp_path / "x.lua"
    f.write_text("print(1)\n")
    with pytest.raises(ValueError):
        ps.estimate_file(f)


# ---- Pluto 流解析 ----------------------------------------------------------

def _obj(counter: int, t: int, payload: bytes) -> bytes:
    return struct.pack("<iii", 1, counter, t) + payload


def test_parse_table_stream():
    """{ k = 1.5 }：表头 special=0、metatable nil、键串、值 double、终止 nil。"""
    stream = (_obj(1, ps.LUA_TTABLE, struct.pack("<i", 0))
              + struct.pack("<ii", 0, 0)
              + _obj(2, ps.LUA_TSTRING, struct.pack("<i", 1) + b"k")
              + _obj(3, ps.LUA_TNUMBER, struct.pack("<d", 1.5))
              + struct.pack("<ii", 0, 0))
    st = ps.PlutoStream(stream, 0, len(stream)).run()
    assert st.consumed == len(stream) == 69
    assert st.objects == 3 and st.refs == 0 and st.top_types == [ps.LUA_TTABLE]


def test_parse_reference_and_permanent():
    """第二次出现的对象是 (0, ref)；perms 命中写 101 + 键的 persist。"""
    key = _obj(2, ps.LUA_TSTRING, struct.pack("<i", 3) + b"msg")
    stream = (_obj(1, ps.LUA_TTABLE, struct.pack("<i", 0))
              + struct.pack("<ii", 0, 0)
              + _obj(3, ps.LUA_TNUMBER, struct.pack("<d", 1.0))
              + struct.pack("<iii", 1, 4, ps.PLUTO_TPERMANENT) + key
              + _obj(5, ps.LUA_TNUMBER, struct.pack("<d", 2.0))
              + struct.pack("<ii", 0, 4)
              + struct.pack("<ii", 0, 0))
    st = ps.PlutoStream(stream, 0, len(stream)).run()
    assert st.consumed == len(stream)
    assert st.perms == ["msg"] and st.refs == 1


def test_parse_dump_layout(tmp_path, capsys):
    """按存档结构偏移放两条最小流，parse-dump 必须读到一致的 size。"""
    d = bytearray(ps.STRUCT_SIZE)
    d[:8] = "标题".encode()
    gs = (_obj(1, ps.LUA_TTABLE, struct.pack("<i", 0)) + struct.pack("<ii", 0, 0)
          + struct.pack("<ii", 0, 0))
    d[ps.OFF_GAMESAVE:ps.OFF_GAMESAVE + len(gs)] = gs
    struct.pack_into("<I", d, ps.OFF_GAMESAVE_SIZE, len(gs))
    th = _obj(1, ps.LUA_TSTRING, struct.pack("<i", 2) + b"hi")
    d[ps.OFF_THREAD:ps.OFF_THREAD + len(th)] = th
    struct.pack_into("<I", d, ps.OFF_THREAD_SIZE, len(th))
    f = tmp_path / "s.bin"
    f.write_bytes(d)
    ps.cmd_parse_dump(type("A", (), {"dump": str(f)})())
    out = capsys.readouterr().out
    assert f"gameSave blob: {len(gs)} B" in out and f"mainThread blob: {len(th)} B" in out
    assert "✓" in out and "✗" not in out
