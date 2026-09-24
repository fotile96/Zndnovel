### Task 4: EBOOT iOS 层（`eboot_patch` 支持 `ios` 层 + 生成器 + 层文件）

**Files:**
- Modify: `tools/eboot_patch.py`（`_LAYER_KEYS` 不变；新增 `LAYER_PROFILES = ("release", "test", "ios")`；`load_layer` 校验改用它；`load_layers(order, root=None, profile="release", *, ios=False)`：层 profile 为 `ios` 时只在 `ios=True` 施加）
- Modify: `tools/layers.py`（`_check_eboot` 额外 `load_layers(..., ios=True)` 核对锚点；`_MANIFEST_KEYS` 加 `"ios"`）
- Create: `tools/ios_eboot.py`、`layers/eboot/ios-movie.toml`（生成）
- Modify: `layers/manifest.toml`（`[eboot].order` 末尾加 `"ios-movie"`）
- Test: `tests/test_ios_eboot.py`、`tests/test_eboot_patch.py`

**Interfaces:**
- Consumes: `tools/mips_asm.assemble`；`tools/eboot_patch.load_layers/apply/sha256`。
- Produces: `tools/ios_eboot.render_layer(pristine: bytes) -> str`；常量 `CAVE = 0x624C8`、`WRAP_AVC = 0x625D8`、`WRAP_CREATE = 0x6262C`、`CALLS = {0xB470: CAVE, 0xB4F4: WRAP_CREATE, 0xEA94: WRAP_AVC}`、`RELOC_NONE = (0x84188, 0x84198)`、`IMPORT_NAME_VA = 0x657D0`；`eboot_patch.load_layers(..., ios=True)`。

- [ ] **Step 1: 记下开工前现行 EBOOT 指纹**（Review Focus 1 的基准）

```bash
uv run python -c "
from tools import eboot_patch as ep, layers
m = layers.load_manifest()['eboot']
out, _ = ep.apply(open(m['source'],'rb').read(), ep.load_layers(m['order'], profile='release'))
print(ep.sha256(out))"
```
Expected: 一行 sha256，抄进 Step 2 测试的 `RELEASE_EBOOT_SHA`。

- [ ] **Step 2: 写失败测试** `tests/test_ios_eboot.py`

```python
"""layers/eboot/ios-movie.toml 由 tools/ios_eboot.py 生成（E1–E4，见 movie-playback 文档「追记：iOS」）。"""
import struct
from pathlib import Path

import pytest

from tools import eboot_patch as ep
from tools import ios_eboot as ie
from tools import layers

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "assets" / "EBOOT.dec.elf"
needs_src = pytest.mark.skipif(not SRC.exists(), reason="assets/EBOOT.dec.elf 不在")
RELEASE_EBOOT_SHA = "<Step 1 打印的值>"


def _relocs(elf: bytes):
    shoff, = struct.unpack_from("<I", elf, 32)
    shentsize, shnum = struct.unpack_from("<HH", elf, 46)
    for i in range(shnum):
        _, t, _, _, off, size = struct.unpack_from("<6I", elf, shoff + i * shentsize)
        if t == 0x700000A0:
            for j in range(size // 8):
                r_off, r_info = struct.unpack_from("<II", elf, off + 8 * j)
                yield off + 8 * j, r_off, r_info & 0xFF


@needs_src
def test_regenerated_layer_matches_committed():
    assert ie.render_layer(SRC.read_bytes()) == (REPO / "layers/eboot/ios-movie.toml").read_text(encoding="utf-8")


@needs_src
def test_release_profile_excludes_ios_layer_and_is_unchanged():
    m = layers.load_manifest()["eboot"]
    rel = ep.load_layers(m["order"], profile="release")
    assert not any(p.layer == "ios-movie" for p in rel)
    out, _ = ep.apply(SRC.read_bytes(), rel)
    assert ep.sha256(out) == RELEASE_EBOOT_SHA


@needs_src
def test_ios_build_neutralizes_every_reloc_in_used_cave_and_keeps_call_relocs():
    m = layers.load_manifest()["eboot"]
    out, _ = ep.apply(SRC.read_bytes(), ep.load_layers(m["order"], profile="release", ios=True))
    used_end = ie.WRAP_CREATE + 4 * len(ie.CREATE_LISTING)
    for fo, r_off, typ in _relocs(out):
        if ie.CAVE <= r_off < used_end:
            assert typ == 0, f"洞内 {r_off:#x} 的重定位（表项 {fo:#x}）没有改成 NONE"
        if r_off in ie.CALLS:
            assert typ == 4, f"调用点 {r_off:#x} 必须保留 R_MIPS_26"
    for site, target in ie.CALLS.items():
        w = struct.unpack_from("<I", out, site + 0xC0)[0]
        assert w == 0x0C000000 | (target >> 2)
    assert out[ie.IMPORT_NAME_VA + 0xC0: ie.IMPORT_NAME_VA + 0xC0 + 7] == b"zndMp4\0"
```

`tests/test_eboot_patch.py` 追加：

```python
def test_ios_layers_only_with_ios_flag(tmp_path):
    (tmp_path / "a.toml").write_text('why = "x"\nprofile = "ios"\n[[patches]]\nva = "0x10"\nfrom = "00"\nto = "01"\n',
                                     encoding="utf-8")
    assert ep.load_layers(["a"], root=tmp_path, profile="release") == []
    assert len(ep.load_layers(["a"], root=tmp_path, profile="release", ios=True)) == 1
```

（`ep` 为该测试文件既有的 `from tools import eboot_patch as ep` 别名；若既有别名不同，照用既有别名。）

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_ios_eboot.py tests/test_eboot_patch.py -v`
Expected: FAIL（`No module named 'tools.ios_eboot'`；`load_layers() got an unexpected keyword argument 'ios'`）。

- [ ] **Step 4: 改 `tools/eboot_patch.py`**

```python
LAYER_PROFILES = ("release", "test", "ios")   # 层的适用范围；构建剖面仍是 PROFILES
```

`load_layer` 中把 `if profile not in PROFILES:` 改为 `if profile not in LAYER_PROFILES:`（报错文案同步列出三值）。`load_layers` 签名与过滤：

```python
def load_layers(order: list[str], root: Path | None = None, profile: str = "release",
                *, ios: bool = False) -> list[Patch]:
    ...
        if layer["profile"] == "test" and profile != "test":
            continue
        if layer["profile"] == "ios" and not ios:
            continue
```

模块 docstring 的层格式说明里 `profile` 一行改为：`profile = "release"   # release：两剖面都打；test：只在 test 剖面打；ios：只在 build_disc --ios 的 iOS 变体打`。

- [ ] **Step 5: 改 `tools/layers.py`**

`_MANIFEST_KEYS` 加 `"ios"`。`_check_eboot` 在现有核对之后追加：

```python
    ios_patches = eboot_patch.load_layers(cfg["order"], profile=profile, ios=True)
    bad = [r for r in eboot_patch.check(data, ios_patches) if r["state"] != "pristine"]
    if bad:
        raise OverlayError("iOS 变体 eboot 补丁锚点在纯净源上不匹配: " +
                           ", ".join(f"{r['layer']}@{r['where']}" for r in bad))
    print(f"[layers] eboot（iOS 变体）: {len(ios_patches)} 条补丁锚点全部命中 ✓")
```

（`check()` 返回项的键名以该文件现有实现为准；若不是 `layer`/`where`，照现有 `_check_eboot` 的拼法改。）

- [ ] **Step 6: 写生成器 `tools/ios_eboot.py`**（代码逐条移植自已实测的 `build/movie_debug/cave_loader.py`、`cave_avcwrap.py`、`cave_createwrap.py`）

```python
#!/usr/bin/env python3
"""生成 layers/eboot/ios-movie.toml：iOS 变体（PPSSPP 1.20.x）播放 OP/ED 的四处 EBOOT 改动。

  E1 导入库名 sceMp4→zndMp4（VA 0x657D0），配合 tools/ios_fwmod.py 改过名的 libmp4。
  E2 洞（sceGumLookAt 0x624C8，零引用死代码）里写加载例程：bal 取 PC、addiu 算导入桩地址 jalr，
     依次 sceKernelLoadModule/StartModule disc0:/PSP_GAME/USRDIR/module/{mp4msv,libmp4}.prx；
     sub_B444 里 0xB470 的 jal sceUtilityLoadModule(0x308) 改指向这里；洞内被新代码覆盖的 HI16/LO16
     两个重定位条目（表项文件偏移 0x84188、0x84198）改 R_MIPS_NONE。
  E3 sceMpegCreate 条件包装（0x6262C）：$a6（DecTopAddr）== 0x10000000（1.20.x HLE 伪值）才把 ringbuffer
     设为 mpeg 工作区 +0x7000；0xB4F4 的 jal 改指向它。
  E4 sceMpegAvcDecode 保 pts 包装（0x625D8）：存/恢复 AU 前 8 字节；0xEA94 的 jal 改指向它。
依据与实测：docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。

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
FILE_BASE = 0xC0
CAVE, WRAP_AVC, WRAP_CREATE = 0x624C8, 0x625D8, 0x6262C
STUB_LOAD, STUB_START, STUB_AVCDEC, STUB_CREATE = 0x65170, 0x65160, 0x65520, 0x65578
CALLS = {0xB470: CAVE, 0xB4F4: WRAP_CREATE, 0xEA94: WRAP_AVC}
CALL_OLD = {0xB470: 0x65230, 0xB4F4: STUB_CREATE, 0xEA94: STUB_AVCDEC}
RELOC_NONE = (0x84188, 0x84198)            # r_offset 0x62570（HI16）/0x62574（LO16）
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
    l0 = CAVE + 6 * 4
    n_words = 7 + 2 * 17 + 6
    s1 = CAVE + 4 * n_words
    s2 = s1 + len(PATHS[0])
    fail = CAVE + 4 * (n_words - 5)
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
    l2 = WRAP_AVC + 10 * 4
    return ["addiu sp, sp, -16", "sw ra, 12(sp)", "sw s0, 8(sp)", "lw t4, 0(a1)", "lw t5, 4(a1)",
            "sw t4, 0(sp)", "sw t5, 4(sp)", "move s0, a1", ("bal", l2), "nop",
            f"addiu t9, ra, {STUB_AVCDEC - l2}", ("raw", 0x0320F809), "nop", "lw t4, 0(sp)", "lw t5, 4(sp)",
            "sw t4, 0(s0)", "sw t5, 4(s0)", "lw s0, 8(sp)", "lw ra, 12(sp)", ("raw", 0x03E00008),
            "addiu sp, sp, 16"]


CREATE_LISTING: list = []


def create_listing() -> list:
    l3 = WRAP_CREATE + 0x1C
    return ["lui t4, 0x1000", f"bne a6, t4, {WRAP_CREATE + 0x10:#x}", "nop", "addiu a3, a1, 0x7000",
            "move t5, ra", ("bal", l3), "nop", f"addiu t9, ra, {STUB_CREATE - l3}", ("raw", 0x03200008),
            "move ra, t5"]


CREATE_LISTING = create_listing()


def cave_bytes() -> bytes:
    loader, strings = loader_listing()
    blob = b"".join(struct.pack("<I", w) for w in _enc(loader, CAVE)) + strings
    assert CAVE + len(blob) <= WRAP_AVC
    blob = blob.ljust(WRAP_AVC - CAVE, b"\0")
    blob += b"".join(struct.pack("<I", w) for w in _enc(avc_listing(), WRAP_AVC))
    assert CAVE + len(blob) == WRAP_CREATE
    blob += b"".join(struct.pack("<I", w) for w in _enc(CREATE_LISTING, WRAP_CREATE))
    return blob


def _hex(b: bytes) -> str:
    return "\n" + "\n".join("    " + b[i:i + 16].hex(" ") for i in range(0, len(b), 16)) + "\n"


WHY = """iOS 变体（仅推荐 iOS 商店版 PPSSPP 1.20.x）播放 OP/ED：配合 tools/ios_fwmod.py 改过库名的固件
libmp4/mp4msv（EBOOT 自行从盘上加载）与 tools/ios_movie.py 的 44.1k 影片。E1 导入改名、E2 洞内加载例程
（sceGumLookAt 死代码，洞内两个 HI16/LO16 条目改 NONE）、E3 sceMpegCreate 条件假 ringbuffer（仅 1.20.x
HLE 的 DecTopAddr 伪值 0x10000000 生效）、E4 sceMpegAvcDecode 保 pts。只在 build_disc.py --ios 施加。
生成器 tools/ios_eboot.py；依据 docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。"""


def render_layer(pristine: bytes) -> str:
    def at(va, n):
        return pristine[va + FILE_BASE: va + FILE_BASE + n]
    new_cave = cave_bytes()
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
        patch("off", fo, entry, entry[:4] + b"\0" + entry[5:], "洞内被覆盖字的重定位条目 → R_MIPS_NONE")
    return "".join(parts)


def main() -> int:
    LAYER.write_text(render_layer(SRC.read_bytes()), encoding="utf-8")
    print(f"写出 {LAYER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: 生成层并登记**

```bash
uv run python tools/ios_eboot.py
```
`layers/manifest.toml` 的 `[eboot]` 改为：`order    = ["kinsoku", "ruby-p5", "msgcol-px", "savebuf", "ios-movie"]     # …（ios-movie 层 profile="ios"，只在 --ios 施加）`

- [ ] **Step 8: 跑测试与闸**

Run: `uv run pytest tests/test_ios_eboot.py tests/test_eboot_patch.py tests/test_msgcol_px.py -v && uv run python tools/layers.py check --profile release`
Expected: 全 PASS；闸打印「eboot（iOS 变体）: N 条补丁锚点全部命中 ✓」。

- [ ] **Step 9: 与实验盘 EBOOT 对账**（实验盘 EBOOT 是 test 剖面层 + E1–E4；这里只比洞与四处改动的字节）

```bash
uv run python -c "
from tools import eboot_patch as ep, layers
m = layers.load_manifest()['eboot']
out, _ = ep.apply(open(m['source'],'rb').read(), ep.load_layers(m['order'], profile='test', ios=True))
exp = open('build/movie_debug/iosdisc/PSP_GAME/SYSDIR/EBOOT.BIN','rb').read()
for lo, hi in ((0x624C8+0xC0, 0x62654+0xC0), (0x657D0+0xC0, 0x657D7+0xC0), (0x84188, 0x841a0)):
    assert out[lo:hi] == exp[lo:hi], hex(lo)
for s in (0xB470, 0xB4E8, 0xB4F4, 0xEA94):
    assert out[s+0xC0:s+0xC4] == exp[s+0xC0:s+0xC4], hex(s)
print('与实验盘逐字节一致')"
```
Expected: `与实验盘逐字节一致`。

- [ ] **Step 10: 提交**（工具与层分开）

```bash
git add tools/eboot_patch.py tools/layers.py tools/ios_eboot.py tests/test_ios_eboot.py tests/test_eboot_patch.py
git commit -m "feat: EBOOT 层支持 profile=ios（仅 --ios 施加）+ ios_eboot 生成器（E1–E4）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git add layers/eboot/ios-movie.toml layers/manifest.toml
git commit -m "data: layers/eboot/ios-movie——iOS 变体 EBOOT 层入库并登记 [eboot].order

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

