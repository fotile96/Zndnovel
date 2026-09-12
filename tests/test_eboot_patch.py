"""tools/eboot_patch.py：EBOOT 补丁层的封闭测试（合成 ELF）+ 真实源上的锚点测试（local_assets）。"""
import struct
from pathlib import Path

import pytest

from tools import eboot_patch as ep

REPO = Path(__file__).resolve().parent.parent


def _elf(payload: bytes, vaddr: int = 0x1000) -> bytes:
    """最小 PRX 型 ELF：一个 PT_LOAD，文件偏移 0x60，虚拟地址 vaddr。"""
    phoff, phentsize, off = 52, 32, 0x60
    hdr = (b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
           + struct.pack("<HHIIIIIHHHHHH", 0xFFA0, 8, 1, 0, phoff, 0, 0, 52, phentsize, 1, 40, 0, 0))
    ph = struct.pack("<8I", 1, off, vaddr, vaddr, len(payload), len(payload), 7, 0x10)
    return (hdr + ph).ljust(off, b"\0") + payload


def _layers(tmp_path, **bodies) -> Path:
    root = tmp_path / "eboot"
    root.mkdir(exist_ok=True)
    for name, body in bodies.items():
        (root / f"{name}.toml").write_text(body, encoding="utf-8")
    return root


HEAD = 'why = "测试"\nprofile = "release"\n'


def test_str_patch_is_nul_terminated_and_zero_padded(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\nfrom = "41 42 43 44 45 46 47 48"\nstr = \'xy\'\n')
    [p] = ep.load_layers(["a"], root)
    assert p.after == b"xy\0\0\0\0\0\0" and p.size == 8


def test_str_longer_than_region_is_hard_failure(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\nfrom = "41 42"\nstr = \'xy\'\n')
    with pytest.raises(SystemExit):
        ep.load_layers(["a"], root)


def test_to_length_mismatch_is_hard_failure(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\nfrom = "41 42"\nto = "43"\n')
    with pytest.raises(SystemExit):
        ep.load_layers(["a"], root)


def test_missing_why_is_hard_failure(tmp_path):
    root = _layers(tmp_path, a='profile = "release"\n[[patches]]\nva = "0x1000"\nfrom = "41"\nto = "42"\n')
    with pytest.raises(SystemExit):
        ep.load_layers(["a"], root)


def test_apply_then_check_reports_applied_and_is_idempotent(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1002"\nfrom = "43 44"\nto = "63 64"\n')
    patches = ep.load_layers(["a"], root)
    src = _elf(b"ABCDEFGH")
    assert [r["state"] for r in ep.check(src, patches)] == ["pristine"]
    out, _ = ep.apply(src, patches)
    assert out[0x60:0x68] == b"ABcdEFGH"
    assert [r["state"] for r in ep.check(out, patches)] == ["applied"]
    again, report = ep.apply(out, patches)
    assert again == out and report[0]["state"] == "applied"


def test_anchor_mismatch_refuses_whole_batch(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\nfrom = "41 42"\nto = "61 62"\n'
                                       '[[patches]]\nva = "0x1004"\nfrom = "ff ff"\nto = "00 00"\n')
    patches = ep.load_layers(["a"], root)
    with pytest.raises(SystemExit) as e:
        ep.apply(_elf(b"ABCDEFGH"), patches)
    assert "0x1004" in str(e.value)


def test_overlapping_patches_are_rejected(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\nfrom = "41 42 43"\nto = "00 00 00"\n',
                             b=HEAD + '[[patches]]\nva = "0x1002"\nfrom = "43 44"\nto = "00 00"\n')
    with pytest.raises(SystemExit) as e:
        ep.load_layers(["a", "b"], root)
    assert "重叠" in str(e.value)


def test_order_must_match_files_on_disk(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\nfrom = "41"\nto = "42"\n')
    with pytest.raises(SystemExit):
        ep.load_layers([], root)


def test_va_outside_load_segment_is_hard_failure(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x2000"\nfrom = "41"\nto = "42"\n')
    with pytest.raises(SystemExit):
        ep.check(_elf(b"ABCDEFGH"), ep.load_layers(["a"], root))


def test_test_profile_layer_is_skipped_in_release(tmp_path):
    root = _layers(tmp_path, a=HEAD.replace("release", "test") + '[[patches]]\nva = "0x1000"\nfrom = "41"\nto = "42"\n')
    assert ep.load_layers(["a"], root, profile="release") == []
    assert len(ep.load_layers(["a"], root, profile="test")) == 1


def test_encrypted_container_is_rejected():
    with pytest.raises(SystemExit):
        ep.Image(b"~PSP" + b"\0" * 400)


# ---------------------------------------------------------------------------
# 真实源（local_assets）：layers/eboot 的全部锚点必须在登记的纯净源上命中
# ---------------------------------------------------------------------------

SRC = REPO / "assets" / "EBOOT.dec.elf"


@pytest.mark.local_assets
@pytest.mark.skipif(not SRC.exists(), reason="缺 assets/EBOOT.dec.elf（解密 EBOOT，本机资产）")
def test_real_layers_apply_on_registered_source():
    from tools.layers import load_manifest
    cfg = load_manifest()["eboot"]
    data = SRC.read_bytes()
    assert ep.sha256(data) == cfg["sha256"], "纯净源指纹与 manifest 登记值不符"
    patches = ep.load_layers(cfg["order"])
    assert {r["state"] for r in ep.check(data, patches)} == {"pristine"}
    out, _ = ep.apply(data, patches)
    assert {r["state"] for r in ep.check(out, patches)} == {"applied"}
    img = ep.Image(out)
    head = out[img.offset(0x663E0, 130):img.offset(0x663E0, 130) + 130]
    assert head.rstrip(b"\0").decode() == "〉》」』】’”ー？！・、。，：；）…—―．～·≫≧ェッゃ＝-"
    tail = out[img.offset(0x66462, 34):img.offset(0x66462, 34) + 34]
    assert tail.rstrip(b"\0").decode() == "〈《「『【‘“（≪≦"
    assert out[img.offset(0xA508, 4):img.offset(0xA508, 4) + 4] == bytes.fromhex("80301200")
    assert out[img.offset(0x5810, 12):img.offset(0x5810, 12) + 12] == bytes.fromhex("0500d626910000102520 0000".replace(" ", ""))
    assert out[img.offset(0x5808, 4):img.offset(0x5808, 4) + 4] == bytes.fromhex("04008514")   # bne 保持原样
    assert len(out) == len(data)


def test_file_offset_patch_targets_bytes_outside_load_segments(tmp_path):
    """off= 补丁打在段外字节（如重定位表）：不经 VA 换算，直接按文件偏移定位。"""
    # 0x58 落在程序头之后、PT_LOAD 内容（0x60）之前的补零区——段外字节
    root = _layers(tmp_path, a=HEAD + '[[patches]]\noff = "0x58"\nfrom = "00 00 00 00"\nto = "01 02 03 04"\n')
    patches = ep.load_layers(["a"], root)
    src = _elf(b"ABCDEFGH")
    assert src[0x58:0x5C] == b"\0\0\0\0"
    out, report = ep.apply(src, patches)
    assert out[0x58:0x5C] == b"\x01\x02\x03\x04" and report[0]["where"] == "off 0x58"


def test_patch_must_give_exactly_one_of_va_or_off(tmp_path):
    root = _layers(tmp_path, a=HEAD + '[[patches]]\nva = "0x1000"\noff = "0x10"\nfrom = "41"\nto = "42"\n')
    with pytest.raises(SystemExit):
        ep.load_layers(["a"], root)


def test_ruby_layer_space_advance_matches_font_pitch():
    """ruby-p5 层 C 段把空格笔位推进写死为 addiu s6,s6,P；P 必须等于 build_font.RUBY_PITCH_PX，
    否则字体与引擎对"一个半角空格多宽"意见不一，居中估算与实际错位。"""
    from tools import build_font
    layer = ep.load_layer(REPO / "layers" / "eboot" / "ruby-p5.toml")
    c = next(p for p in layer["patches"] if p.note.startswith("C"))
    word = int.from_bytes(c.after[:4], "little")
    assert word >> 26 == 9 and (word >> 16) & 0x1F == 22 and (word >> 21) & 0x1F == 22   # addiu s6,s6,imm
    assert word & 0xFFFF == build_font.RUBY_PITCH_PX
