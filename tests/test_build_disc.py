"""build_disc 的封闭测试：成员树、缓存、发布断言。用迷你 databin 夹具。"""
import json

import pytest

from tools.build_disc import assemble_stage, release_assertions


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
    members = _members(tmp_path, {"script/snr_test.lua": b"PROBE"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    bad = release_assertions(stage, mini, expected_new=set(), compiled=members / "script")
    assert any("snr_test" in b for b in bad)


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
    members = _members(tmp_path, {"script/m.lua": b"ZH"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    (stage / "script" / "m.lua").write_bytes(b"TAMPERED")
    bad = release_assertions(stage, mini, expected_new=set(), compiled=members / "script")
    assert any("m.lua" in b for b in bad)
