#!/usr/bin/env python3
"""EBOOT 补丁层：按 layers/eboot/*.toml 给解密后的引擎 ELF 打字节补丁（纯 stdlib）。

为什么是"层"而不是直接改文件：引擎二进制（EBOOT.BIN）与 lua_scripts/ 一样是只读
基座——本机只有一份从 PPSSPP dump 出来的解密副本（版权物，放 assets/ 不入库），
所有改动都以"原字节锚点 + 新字节"的形式记在 layers/eboot/<名>.toml 里，构建时
重新施加。这样：①改了什么、为什么改，与代码一起受版本控制；②每个补丁都带
原字节锚点，源文件换了、补丁重叠了、或已经打过一次，都会当场报错而不是静默
写坏；③施加是幂等的——对已打好的产物再跑一遍，逐补丁报"已施加"，不会二次破坏。

层文件格式（layers/eboot/<name>.toml）：

    why     = \"\"\"这层为什么存在（必填，见 layers/overlays 同款约定）\"\"\"
    profile = "release"          # release：两剖面都打；test：只在 test 剖面打
    [[patches]]
    va   = "0x663E0"             # ELF 内虚拟地址（PRX 型 ELF 基址 0；装载后 +0x08804000）
    from = "e3 80 81 …"          # 原字节（锚点）。其长度就是补丁区间长度
    to   = "…"                   # 新字节（十六进制），长度必须与 from 相同；或
    str  = '…'                   # UTF-8 字符串 + NUL，零填充到 from 的长度（与 to 二选一）
    note = "一句话说明"

VA → 文件偏移由 ELF 程序头（PT_LOAD）换算，不硬编码 0xC0。源文件指纹由
layers/manifest.toml 的 [eboot].sha256 钉住，不符拒绝施加。

用法：
    python3 tools/eboot_patch.py check  <eboot.elf>            # 逐补丁报 pristine/applied/mismatch
    python3 tools/eboot_patch.py apply  <in.elf> <out.elf>     # 施加 manifest [eboot].order 全部层
    python3 tools/eboot_patch.py show                          # 列出各层补丁
"""
from __future__ import annotations

import hashlib
import struct
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EBOOT_LAYERS = REPO / "layers" / "eboot"

_LAYER_KEYS = {"why", "profile", "patches"}
_PATCH_KEYS = {"va", "from", "to", "str", "note"}
PROFILES = ("release", "test")


class PatchError(SystemExit):
    """补丁层出错一律硬失败——静默跳过一个补丁等于交付一份行为未知的引擎。"""


@dataclass(frozen=True)
class Patch:
    layer: str
    va: int
    before: bytes
    after: bytes
    note: str

    @property
    def size(self) -> int:
        return len(self.before)


def parse_hex(text: str) -> bytes:
    try:
        return bytes.fromhex("".join(text.split()))
    except ValueError as e:
        raise PatchError(f"十六进制串不合法: {text[:40]!r}…: {e}") from e


def _parse_va(v) -> int:
    if isinstance(v, int):
        return v
    try:
        return int(str(v), 0)
    except ValueError as e:
        raise PatchError(f"va 不合法: {v!r}") from e


def load_layer(path: Path) -> dict:
    """读一层：校验键、把每条补丁规整成 Patch。"""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise PatchError(f"{path}: TOML 语法错误: {e}") from e
    unknown = set(raw) - _LAYER_KEYS
    if unknown:
        raise PatchError(f"{path}: 未知键 {sorted(unknown)}")
    if not raw.get("why", "").strip():
        raise PatchError(f"{path}: 缺 why——每一层都必须说明自己为什么存在")
    profile = raw.get("profile", "release")
    if profile not in PROFILES:
        raise PatchError(f"{path}: profile 只能是 {PROFILES}，得到 {profile!r}")
    patches = []
    for i, p in enumerate(raw.get("patches", [])):
        unknown = set(p) - _PATCH_KEYS
        if unknown:
            raise PatchError(f"{path}: patches[{i}] 有未知键 {sorted(unknown)}")
        for k in ("va", "from"):
            if k not in p:
                raise PatchError(f"{path}: patches[{i}] 缺 {k}")
        if ("to" in p) == ("str" in p):
            raise PatchError(f"{path}: patches[{i}] 必须恰好给 to 或 str 之一")
        before = parse_hex(p["from"])
        if not before:
            raise PatchError(f"{path}: patches[{i}] from 为空")
        if "to" in p:
            after = parse_hex(p["to"])
            if len(after) != len(before):
                raise PatchError(f"{path}: patches[{i}] to 长 {len(after)} B ≠ from 长 {len(before)} B"
                                 f"——补丁不能改变区间长度")
        else:
            body = p["str"].encode("utf-8") + b"\0"
            if len(body) > len(before):
                raise PatchError(f"{path}: patches[{i}] str 连 NUL 共 {len(body)} B，"
                                 f"超过区间 {len(before)} B")
            after = body + b"\0" * (len(before) - len(body))
        patches.append(Patch(layer=path.stem, va=_parse_va(p["va"]), before=before,
                             after=after, note=str(p.get("note", ""))))
    if not patches:
        raise PatchError(f"{path}: 没有任何补丁")
    return {"_name": path.stem, "why": raw["why"], "profile": profile, "patches": patches}


def load_layers(order: list[str], root: Path | None = None, profile: str = "release"
                ) -> list[Patch]:
    """按 order 读层、按剖面筛选，并拒绝任何区间重叠（施加顺序在重叠时会决定结果，
    那是隐式语义，宁可不允许）。root 缺省在调用时才取 EBOOT_LAYERS，测试可 monkeypatch。"""
    root = root or EBOOT_LAYERS
    if profile not in PROFILES:
        raise PatchError(f"未知剖面 {profile!r}")
    on_disk = sorted(p.stem for p in root.glob("*.toml"))
    if sorted(order) != on_disk:
        raise PatchError(f"manifest [eboot].order 与 {root}/ 下的文件不一致：\n"
                         f"  order   = {sorted(order)}\n  on disk = {on_disk}")
    out: list[Patch] = []
    for name in order:
        layer = load_layer(root / f"{name}.toml")
        if layer["profile"] == "test" and profile != "test":
            continue
        out.extend(layer["patches"])
    spans = sorted((p.va, p.va + p.size, p.layer) for p in out)
    for (a0, a1, la), (b0, _b1, lb) in zip(spans, spans[1:]):
        if b0 < a1:
            raise PatchError(f"补丁区间重叠: {la} [{a0:#x},{a1:#x}) 与 {lb} 起于 {b0:#x}")
    return out


class Image:
    """PRX 型 ELF 的 VA→文件偏移换算（只认 PT_LOAD 段）。"""

    def __init__(self, data: bytes):
        if data[:4] != b"\x7fELF":
            raise PatchError("不是 ELF（PPSSPP dump 的应是解密后的 \\x7fELF，"
                             "以 ~PSP 开头的是加密容器）")
        (self.e_type, e_machine, _v, _entry, phoff, _shoff, _flags, _ehsize,
         phentsize, phnum) = struct.unpack_from("<HHIIIIIHHH", data, 16)
        if e_machine != 8:
            raise PatchError(f"e_machine={e_machine}，不是 MIPS")
        self.segments: list[tuple[int, int, int]] = []     # (vaddr, offset, filesz)
        for i in range(phnum):
            p_type, p_offset, p_vaddr, _pa, p_filesz = struct.unpack_from(
                "<IIIII", data, phoff + i * phentsize)
            if p_type == 1 and p_filesz:
                self.segments.append((p_vaddr, p_offset, p_filesz))
        if not self.segments:
            raise PatchError("ELF 没有带文件内容的 PT_LOAD 段")

    def offset(self, va: int, size: int) -> int:
        for vaddr, off, filesz in self.segments:
            if vaddr <= va and va + size <= vaddr + filesz:
                return va - vaddr + off
        raise PatchError(f"VA {va:#x}+{size} 不落在任何 PT_LOAD 段的文件内容里")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hexdump(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def check(data: bytes, patches: list[Patch]) -> list[dict]:
    """逐补丁判定当前状态：pristine（原字节在位）/ applied（新字节在位）/ mismatch。"""
    img = Image(data)
    out = []
    for p in patches:
        off = img.offset(p.va, p.size)
        cur = data[off:off + p.size]
        state = "pristine" if cur == p.before else "applied" if cur == p.after else "mismatch"
        out.append({"layer": p.layer, "va": p.va, "offset": off, "size": p.size,
                    "state": state, "note": p.note, "current": cur})
    return out


def apply(data: bytes, patches: list[Patch]) -> tuple[bytes, list[dict]]:
    """施加全部补丁。任何一条 mismatch 都整体失败、不写任何字节。"""
    report = check(data, patches)
    bad = [r for r in report if r["state"] == "mismatch"]
    if bad:
        lines = []
        for r in bad:
            p = next(p for p in patches if p.va == r["va"] and p.layer == r["layer"])
            lines.append(f"  {r['layer']} @ {r['va']:#x} (文件偏移 {r['offset']:#x}): 期望原字节\n"
                         f"    {_hexdump(p.before[:24])}{'…' if p.size > 24 else ''}\n"
                         f"  实际\n    {_hexdump(r['current'][:24])}{'…' if p.size > 24 else ''}")
        raise PatchError("补丁锚点不匹配（源不是纯净 EBOOT，或与别的改动冲突）：\n" + "\n".join(lines))
    buf = bytearray(data)
    for p, r in zip(patches, report):
        if r["state"] == "pristine":
            buf[r["offset"]:r["offset"] + p.size] = p.after
    return bytes(buf), report


def load_manifest_eboot(manifest: dict) -> dict | None:
    """从 layers.load_manifest() 的结果取 [eboot]；没有该节返回 None。"""
    return manifest.get("eboot")


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="逐补丁报 pristine/applied/mismatch")
    c.add_argument("elf", type=Path)
    c.add_argument("--profile", default="release", choices=PROFILES)
    a = sub.add_parser("apply", help="施加全部层")
    a.add_argument("src", type=Path)
    a.add_argument("dst", type=Path)
    a.add_argument("--profile", default="release", choices=PROFILES)
    a.add_argument("--no-hash", action="store_true", help="不核对 manifest 的源指纹")
    sub.add_parser("show", help="列出各层补丁")
    args = ap.parse_args(argv)

    from tools.layers import load_manifest
    man = load_manifest()
    cfg = load_manifest_eboot(man)
    if cfg is None:
        raise PatchError("layers/manifest.toml 没有 [eboot] 节")
    patches = load_layers(cfg["order"], profile=getattr(args, "profile", "release"))

    if args.cmd == "show":
        for p in patches:
            print(f"{p.layer:12} {p.va:#08x} {p.size:4} B  {p.note}")
        return 0
    data = args.elf.read_bytes() if args.cmd == "check" else args.src.read_bytes()
    if args.cmd == "apply" and not args.no_hash and sha256(data) != cfg["sha256"]:
        raise PatchError(f"{args.src} 的 sha256 与 manifest [eboot].sha256 不符——"
                         f"不是登记的纯净源，拒绝施加")
    if args.cmd == "check":
        for r in check(data, patches):
            print(f"{r['state']:9} {r['layer']:12} {r['va']:#08x} {r['size']:4} B  {r['note']}")
        return 0
    out, report = apply(data, patches)
    args.dst.parent.mkdir(parents=True, exist_ok=True)
    args.dst.write_bytes(out)
    n_new = sum(r["state"] == "pristine" for r in report)
    n_old = sum(r["state"] == "applied" for r in report)
    print(f"[eboot] {args.dst}: 施加 {n_new} 条，已在位 {n_old} 条，sha256 {sha256(out)[:16]}…")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
