"""build_disc 的封闭测试：成员树、缓存、发布断言。用迷你 databin 夹具。

2026-09-03 review 加固后追加了三组 stage_iso/stage_pack 级别的回归（对应
Finding 1/2/3），其中涉及独立重编译 lua/final 的两组需要真 luac，标 local_assets、
缺则 skip；其余仍是不碰真实资产的封闭测试。
"""
import json
import os
import shutil
from pathlib import Path

import pytest

from tools.build_disc import assemble_stage, release_assertions
from tools.layers import load_manifest

LUAC = Path(os.environ.get("SNDL_LUAC") or "~/pyluadec-refactor/build/luac_sz4").expanduser()


@pytest.fixture
def mini(tmp_path):
    """三成员的迷你封包树：a.gim / m.lua / z.pgf，manifest 按名有序。"""
    base = tmp_path / "databin"
    (base / "script").mkdir(parents=True)
    (base / "card").mkdir()
    (base / "card" / "a.gim").write_bytes(b"A")
    (base / "script" / "m.lua").write_bytes(b"M")
    rows = [{"name": "card/a.gim", "lzss": False, "sha1": ""},
            {"name": "script/m.lua", "lzss": False, "sha1": ""}]
    (base / "manifest.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return base


def _members(tmp_path, files: dict[str, bytes]):
    root = tmp_path / "members"
    for name, blob in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return root


def test_new_member_is_inserted_at_sorted_position(tmp_path, mini):
    members = _members(tmp_path, {"script/aaa.lua": b"NEW"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    names = [json.loads(l)["name"] for l in
             (stage / "manifest.jsonl").read_text().splitlines() if l]
    assert names == sorted(names)
    assert names.index("script/aaa.lua") < names.index("script/m.lua")


def test_existing_member_is_replaced_not_appended(tmp_path, mini):
    members = _members(tmp_path, {"script/m.lua": b"ZH"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    rows = [json.loads(l) for l in
            (stage / "manifest.jsonl").read_text().splitlines() if l]
    assert len(rows) == 2
    assert (stage / "script" / "m.lua").read_bytes() == b"ZH"


def test_stage_tree_is_rebuilt_not_accumulated(tmp_path, mini):
    stage_dir = tmp_path / "stage"
    assemble_stage(mini, _members(tmp_path, {"script/x.lua": b"1"}), stage_dir)
    assert (stage_dir / "script" / "x.lua").exists()
    (tmp_path / "members" / "script" / "x.lua").unlink()
    assemble_stage(mini, tmp_path / "members", stage_dir)
    assert not (stage_dir / "script" / "x.lua").exists(), "上一轮的成员没被清掉"


def test_assemble_stage_refuses_missing_members_dir(tmp_path, mini):
    """brief 缺陷（transcribe 后critically 复核发现，非测试断言层面的那个，见
    test_release_assertion_accepts_declared_new_member 的注释）：给定的
    assemble_stage 实现对 `members` 只用 `Path(members).rglob("*")`，而
    `Path.rglob()` 在**不存在**的目录上不报错、只静默返回空迭代器——传错路径
    （典型笔误：写成上一次构建的旧目录名）会悄悄产出一棵『看着正常、实则一个
    新成员都没覆盖』的封包树，且没有任何报错或告警。这正是全局约束「一切正确性
    问题都是硬失败」要堵的那类问题，补两行存在性检查即可。"""
    with pytest.raises(SystemExit):
        assemble_stage(mini, tmp_path / "no_such_members_dir", tmp_path / "stage")


def test_release_assertion_rejects_unexpected_member(tmp_path, mini):
    # ⚠ 同一处夹具不完整问题（2026-09-03 review「apply the same fixture
    # asymmetry fix ... to its two siblings」）：只放 snr_test.lua 时 compiled
    # 里没有 m.lua，逐字节核对循环会额外报一条"script/m.lua 不在本次编译产物
    # 里"——之前用 any() 弱断言测不出来（子串匹配对哪条消息命中不敏感），换成
    # 精确匹配整个列表就会现形。补上与 base 内容一致的 "script/m.lua": b"M"，
    # 让 bad 恰好是这条测试真正要验证的那两条消息，不多不少。
    members = _members(tmp_path, {"script/snr_test.lua": b"PROBE", "script/m.lua": b"M"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    bad = release_assertions(stage, mini, expected_new=set(), compiled=members / "script")
    # 断言消息文本本身，不是子串——子串匹配对"这条检查被删掉但另一条检查恰好
    # 也提到 snr_test"这类情形不敏感（这里两条检查确实都会命中 snr_test.lua，
    # 但 any() 写法本该锁的是"至少一条检查真的抓住了它"，不是"字符串里出现过
    # snr_test"这么松）。
    assert bad == [
        "封包树有未声明的成员 script/snr_test.lua（testboot 残留？）",
        "封包树里有测试引导成员 script/snr_test.lua",
    ]


def test_release_assertion_accepts_declared_new_member(tmp_path, mini):
    # ⚠ 修正 brief 缺陷（transcribe 后critically 复核发现，已用未改动的
    # release_assertions/assemble_stage 代入验证复现）：原版只放
    # {"script/snr_finale.lua": b"FIN"}。但 release_assertions 的最后一段对
    # `stage/script/` 下**每一个** .lua 都要求能在 `compiled` 里找到同名件
    # （这正是它要证明的事——"every packed script must be byte-identical to
    # what this build compiled"，对全体成立，不只对新增的那个）。真实构建里
    # stage_members 会把 lua/final 全部文件都编译进 members/script，包括未改动
    # 的 m.lua；这里的夹具若只放新增件，stage/script 下的 m.lua（继承自 base）
    # 就会被判「不在本次编译产物里」，bad 非空，`assert bad == []` 必败——
    # 与 assemble_stage/release_assertions 的实现无关，是夹具没有反映真实构建
    # 会重新编译全部脚本这件事。补上 "script/m.lua": b"M"（内容与 base 里的
    # 一致，代表"这次也编译了它，字节没变"）即可。
    members = _members(tmp_path, {"script/snr_finale.lua": b"FIN", "script/m.lua": b"M"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    bad = release_assertions(stage, mini, expected_new={"script/snr_finale.lua"},
                             compiled=members / "script")
    assert bad == []


def test_release_assertion_catches_script_byte_mismatch(tmp_path, mini):
    # 这条的夹具本就完整：mini 只声明一个脚本成员（script/m.lua），members 里
    # 已经放了它，compiled 不缺任何东西——不需要「两个 siblings」里的完整性
    # 补丁（那个问题专属于夹具里同时出现"新增脚本 + 未提及的既有脚本"的情形，
    # 这条没有新增脚本）。这里只把断言从子串收紧成精确消息，同一份 review 要求。
    members = _members(tmp_path, {"script/m.lua": b"ZH"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    (stage / "script" / "m.lua").write_bytes(b"TAMPERED")
    bad = release_assertions(stage, mini, expected_new=set(), compiled=members / "script")
    assert bad == ["script/m.lua 与本次编译产物不一致"]


def test_stage_pack_does_not_publish_to_dist(tmp_path, mini, monkeypatch):
    """Finding 1 回归：stage_pack 不再往 build/dist/ 发布，只有 stage_iso 的发布
    断言通过之后才发布。此前 pack 在 release 剖面末尾顺手同步一份到
    build/dist/DATA.BIN——于是 `--profile release --stage pack` 单独跑一次，
    不经过任何断言，就能把发布产物换掉；一次完整流程若在 iso 断言处失败，
    dist/DATA.BIN 也早已在这一步被换成未经验证的新包。这里验证：pack 跑完，
    一个本该是"发布产物"的全局位置（这里用 monkeypatch 换成假的 DIST 目录，
    不碰真实 build/dist/）必须原封不动。
    """
    import tools.build_disc as bd

    fake_dist = tmp_path / "fake_dist"
    fake_dist.mkdir()
    (fake_dist / "DATA.BIN").write_bytes(b"OLD-RELEASE-DATA-UNTOUCHED")
    monkeypatch.setattr(bd, "DIST", fake_dist)

    root = tmp_path / "root"
    shutil.copytree(mini, root / "stage")

    ctx = bd.BuildContext(profile="release", root=root, manifest={},
                          switches={}, mode_opts={}, force=False)
    bd.stage_pack(ctx)

    assert (root / "DATA.BIN").exists(), "pack 本身仍要正常产出 profile 内部的 DATA.BIN"
    assert (fake_dist / "DATA.BIN").read_bytes() == b"OLD-RELEASE-DATA-UNTOUCHED", \
        "pack 阶段不该碰 build/dist/DATA.BIN——那是 iso 断言通过之后才做的事"


@pytest.mark.local_assets
@pytest.mark.skipif(not LUAC.exists(), reason=f"缺 {LUAC}")
def test_stage_iso_catches_data_bin_packed_from_a_different_stage_tree(
        tmp_path, mini, monkeypatch, capsys):
    """Finding 2 回归：stage/ 在 pack 之后被重新装配过（典型场景：改了译文、
    重跑了 lua→font→members→stage，但漏跑 pack——`stage_iso` 自己给的恢复指引
    五个阶段名都会打这个字，是个容易犯的手滑），DATA.BIN 已经不对应当前这棵
    stage 树。旧逻辑里 `stage_iso` 断言的是 `ctx.root/"stage"`、splice 的是
    `ctx.root/"DATA.BIN"`，两者之间没有任何东西把它们锁在一起，断言会照常
    通过；新的指纹核对必须抓住这一点。
    """
    import tools.build_disc as bd

    monkeypatch.setattr(bd, "BASE", mini)
    # 这条测试预期在 stage_iso 的指纹核对处就 SystemExit；DIST/ORIG_ISO 指向真
    # 实的 build/dist/ 与 assets/orig.iso 只在"该守卫哪天失灵、代码真的往下
    # 跑到发布阶段"时才会被摸到——但那正是本机会真被写坏发布产物/真实 ISO 的
    # 时候，必须重定向到 tmp_path，不能指望前面的断言不失手。
    monkeypatch.setattr(bd, "DIST", tmp_path / "dist")
    monkeypatch.setattr(bd, "ORIG_ISO", tmp_path / "nonexistent.iso")
    ctx = bd.BuildContext(profile="release", root=tmp_path / "root",
                          manifest=load_manifest(), switches={}, mode_opts={},
                          force=False)
    root = ctx.root

    final_dir = root / "lua" / "final"
    final_dir.mkdir(parents=True)
    (final_dir / "m.lua").write_text('print("v1")\n', encoding="utf-8")

    members = root / "members"
    (members / "script").mkdir(parents=True)
    bd._compile_lua(final_dir / "m.lua", members / "script" / "m.lua", ctx)

    stage_dir = root / "stage"
    bd.assemble_stage(mini, members, stage_dir)
    (root / "new_members.json").write_text("[]", encoding="utf-8")
    bd.stage_pack(ctx)   # 记录的指纹对应 v1

    # 模拟"lua/final 改了、重新装配了 stage，但漏跑 pack"：stage 树内容已经是
    # v2，而 DATA.BIN 与它绑定的指纹记录仍停在 v1。
    (final_dir / "m.lua").write_text('print("v2")\n', encoding="utf-8")
    bd._compile_lua(final_dir / "m.lua", members / "script" / "m.lua", ctx)
    bd.assemble_stage(mini, members, stage_dir)

    with pytest.raises(SystemExit):
        bd.stage_iso(ctx)
    out = capsys.readouterr().out
    assert "DATA.BIN 与当前 stage 树指纹不一致" in out, out


@pytest.mark.local_assets
@pytest.mark.skipif(not LUAC.exists(), reason=f"缺 {LUAC}")
def test_stage_iso_catches_members_compiled_from_stale_lua_final(
        tmp_path, mini, monkeypatch, capsys):
    """Finding 3 回归（review 认为最尖锐的一条）：members/script（进而
    stage/script）是编译旧版 lua/final 得到的，lua/final 后来又改了，但没有人
    重新跑 members 阶段。旧逻辑拿 `members/script` 当 release_assertions 的
    compiled 参照——但 stage/script 本就是从 members/script 逐字节拷过去的
    （assemble_stage 干的事），拿它跟自己比，永远相同，测不出任何漂移。这里
    先直接验证旧逻辑确实测不出来，再验证新的 stage_iso（改用独立重编译
    lua/final 的结果当参照）真的抓住了。
    """
    import tools.build_disc as bd

    monkeypatch.setattr(bd, "BASE", mini)
    # 同 Finding 2 的测试：只 monkeypatch BASE 不够，DIST/ORIG_ISO 仍指向真实
    # build/dist/ 与 assets/orig.iso；一旦前面的守卫哪天失灵，测试会真的往
    # 发布阶段跑并写坏它们，必须重定向。
    monkeypatch.setattr(bd, "DIST", tmp_path / "dist")
    monkeypatch.setattr(bd, "ORIG_ISO", tmp_path / "nonexistent.iso")
    ctx = bd.BuildContext(profile="release", root=tmp_path / "root",
                          manifest=load_manifest(), switches={}, mode_opts={},
                          force=False)
    root = ctx.root

    final_dir = root / "lua" / "final"
    final_dir.mkdir(parents=True)
    (final_dir / "m.lua").write_text('print("v1")\n', encoding="utf-8")

    members = root / "members"
    (members / "script").mkdir(parents=True)
    bd._compile_lua(final_dir / "m.lua", members / "script" / "m.lua", ctx)

    stage_dir = root / "stage"
    bd.assemble_stage(mini, members, stage_dir)
    (root / "new_members.json").write_text("[]", encoding="utf-8")
    bd.stage_pack(ctx)   # 指纹与这一版 stage 对应，Finding 2 那道闸这里会过

    # lua/final 改了，但没有人重新跑 members——members/script、stage/script 仍是
    # v1 的编译产物。
    (final_dir / "m.lua").write_text('print("v2 - 已经改了")\n', encoding="utf-8")

    old_bad = bd.release_assertions(stage_dir, mini, set(), members / "script")
    assert old_bad == [], (
        f"旧逻辑（拿 members/script 当参照）应当测不出这处漂移——两者是同一次"
        f"assemble_stage 拷贝的两份副本，逐字节相同是同义反复；实际: {old_bad}")

    with pytest.raises(SystemExit):
        bd.stage_iso(ctx)
    out = capsys.readouterr().out
    assert "script/m.lua 与本次编译产物不一致" in out, out


def test_require_bake_face_dies_on_release_when_face_dir_missing(tmp_path, capsys):
    """Must-fix 3：release 剖面下某个烤字面（build/<face>/）完全没跑过 bake 工具时，
    stage_members 过去只打一行「不存在，跳过整面」日志就继续——release_assertions
    看不见这个缺失（它比对 new_members.json，而那份记录正是在这次跳过之后才写的），
    于是缺了某整面烤字的 release 盘能一路通过全部发布闸。`_require_bake_face` 是从
    stage_members 里抽出来的决策点：不依赖真实资产（databin/luac/PNG）就能单测。
    """
    import tools.build_disc as bd

    ctx = bd.BuildContext(profile="release", root=tmp_path / "root", manifest={},
                          switches={}, mode_opts={}, force=False)
    missing = tmp_path / "build" / "card_zh"
    assert not missing.exists()

    with pytest.raises(SystemExit) as e:
        bd._require_bake_face(ctx, missing, "card_zh")
    msg = str(e.value)
    assert "card_zh" in msg
    assert "release" in msg


def test_require_bake_face_logs_and_skips_on_test_profile(tmp_path, capsys):
    """对照：同样缺失的烤字面，test 剖面允许部分烤字面缺失，只告警跳过整面，
    不硬失败——这是 test 剖面局部走查（`--stage members,stage,pack,iso`）的合法状态。
    """
    import tools.build_disc as bd

    ctx = bd.BuildContext(profile="test", root=tmp_path / "root", manifest={},
                          switches={}, mode_opts={}, force=False)
    missing = tmp_path / "build" / "card_zh"

    assert bd._require_bake_face(ctx, missing, "card_zh") is True
    out = capsys.readouterr().out
    assert "card_zh" in out
    assert "test" in out


def test_require_bake_face_returns_false_when_dir_exists(tmp_path):
    """正面对照：目录存在时两个剖面都不该触发跳过或失败。"""
    import tools.build_disc as bd

    present = tmp_path / "build" / "card_zh"
    present.mkdir(parents=True)
    for profile in ("release", "test"):
        ctx = bd.BuildContext(profile=profile, root=tmp_path / "root", manifest={},
                              switches={}, mode_opts={}, force=False)
        assert bd._require_bake_face(ctx, present, "card_zh") is False


# ---------------------------------------------------------------------------
# eboot 阶段：无 [eboot] 节空转；有则在登记的纯净源上施加 layers/eboot 并落 EBOOT.BIN
# ---------------------------------------------------------------------------

def _mini_elf(payload: bytes, vaddr: int = 0x1000) -> bytes:
    import struct
    phoff, phentsize, off = 52, 32, 0x60
    hdr = (b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
           + struct.pack("<HHIIIIIHHHHHH", 0xFFA0, 8, 1, 0, phoff, 0, 0, 52, phentsize, 1, 40, 0, 0))
    ph = struct.pack("<8I", 1, off, vaddr, vaddr, len(payload), len(payload), 7, 0x10)
    return (hdr + ph).ljust(off, b"\0") + payload


def _ctx(tmp_path, manifest):
    from tools.build_disc import BuildContext
    return BuildContext(profile="release", root=tmp_path / "out", manifest=manifest,
                        switches={}, mode_opts={})


def test_stage_eboot_skips_without_manifest_section(tmp_path):
    from tools.build_disc import stage_eboot
    assert stage_eboot(_ctx(tmp_path, {"eboot": None})) == {"skipped": True}
    assert not (tmp_path / "out" / "EBOOT.BIN").exists()


def test_stage_eboot_applies_registered_layers(tmp_path, monkeypatch):
    import hashlib

    from tools import eboot_patch
    from tools.build_disc import stage_eboot

    src = tmp_path / "EBOOT.dec.elf"
    src.write_bytes(_mini_elf(b"ABCDEFGH"))
    layers_root = tmp_path / "eboot_layers"
    layers_root.mkdir()
    (layers_root / "x.toml").write_text(
        'why = "测试"\nprofile = "release"\n[[patches]]\nva = "0x1002"\nfrom = "43 44"\nto = "63 64"\n',
        encoding="utf-8")
    monkeypatch.setattr(eboot_patch, "EBOOT_LAYERS", layers_root)
    cfg = {"source": str(src), "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
           "iso_path": "/PSP_GAME/SYSDIR/EBOOT.BIN", "order": ["x"]}
    res = stage_eboot(_ctx(tmp_path, {"eboot": cfg}))
    out = (tmp_path / "out" / "EBOOT.BIN").read_bytes()
    assert out[0x60:0x68] == b"ABcdEFGH" and res["patches"] == 1


def test_stage_eboot_rejects_unregistered_source(tmp_path, monkeypatch):
    from tools import eboot_patch
    from tools.build_disc import stage_eboot

    src = tmp_path / "EBOOT.dec.elf"
    src.write_bytes(_mini_elf(b"ABCDEFGH"))
    layers_root = tmp_path / "eboot_layers"
    layers_root.mkdir()
    (layers_root / "x.toml").write_text(
        'why = "测试"\nprofile = "release"\n[[patches]]\nva = "0x1002"\nfrom = "43 44"\nto = "63 64"\n',
        encoding="utf-8")
    monkeypatch.setattr(eboot_patch, "EBOOT_LAYERS", layers_root)
    cfg = {"source": str(src), "sha256": "0" * 64,
           "iso_path": "/PSP_GAME/SYSDIR/EBOOT.BIN", "order": ["x"]}
    with pytest.raises(SystemExit):
        stage_eboot(_ctx(tmp_path, {"eboot": cfg}))
