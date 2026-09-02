"""叠加操作引擎的封闭单元测试。

这些测试不碰真实语料，只验引擎语义：五种操作、count/occurrence 的每种失败
路径、多行逐字匹配与缩进保真。真语料上的命中由 tests/test_layers_corpus.py 守。
"""
import hashlib
import json

import pytest

from tools.layers import (OverlayError, apply_op, apply_overlay, charset_of, check_ids,
                          collect_ids, find_all, load_manifest, load_overlay, overlays_for,
                          provenance, select_indices, write_charset, write_provenance)


def test_find_all_is_non_overlapping():
    assert find_all("aaaa", "aa") == [0, 2]


def test_replace_single_hit():
    out = apply_op("x = key3[i]\n", {"op": "replace", "find": "key3", "with": "keyCur"})
    assert out == "x = keyCur[i]\n"


def test_replace_count_mismatch_is_hard_failure():
    with pytest.raises(OverlayError) as e:
        apply_op("a a a\n", {"op": "replace", "count": 2, "find": "a", "with": "b"})
    assert "命中 3" in str(e.value)


def test_replace_zero_hit_is_hard_failure():
    with pytest.raises(OverlayError) as e:
        apply_op("hello\n", {"op": "replace", "find": "nope", "with": "x"})
    assert "命中 0" in str(e.value)


def test_count_zero_is_hard_failure_not_silent_noop():
    with pytest.raises(OverlayError) as e:
        apply_op("hello\n", {"op": "replace", "count": 0, "find": "nope", "with": "x"})
    assert "≥1" in str(e.value)


def test_replace_all_occurrences_by_default():
    out = apply_op("a a a\n", {"op": "replace", "count": 3, "find": "a", "with": "b"})
    assert out == "b b b\n"


def test_occurrence_negative_selects_from_end():
    out = apply_op("a a a\n",
                   {"op": "replace", "count": 3, "occurrence": -1, "find": "a", "with": "Z"})
    assert out == "a a Z\n"


def test_occurrence_out_of_range_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("a a\n", {"op": "replace", "count": 2, "occurrence": 3, "find": "a", "with": "b"})


def test_insert_before_keeps_indentation_verbatim():
    text = "        else\n            l0_1 = 1\n"
    out = apply_op(text, {"op": "insert_before",
                          "anchor": "        else\n",
                          "text": "        elseif cond then\n            body()\n"})
    assert out == ("        elseif cond then\n            body()\n"
                   "        else\n            l0_1 = 1\n")


def test_insert_after_places_text_after_anchor():
    out = apply_op("line1\nline2\n",
                   {"op": "insert_after", "anchor": "line1\n", "text": "mid\n"})
    assert out == "line1\nmid\nline2\n"


def test_delete_span_removes_start_through_end_inclusive():
    text = "keep\nSTART\nmiddle\nEND\ntail\n"
    out = apply_op(text, {"op": "delete_span", "start": "START\n", "end": "END\n"})
    assert out == "keep\ntail\n"


def test_replace_span_substitutes_region():
    text = "keep\nSTART\nmiddle\nEND\ntail\n"
    out = apply_op(text, {"op": "replace_span",
                          "start": "START\n", "end": "END\n", "with": "NEW\n"})
    assert out == "keep\nNEW\ntail\n"


def test_span_end_before_start_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("END\nSTART\n", {"op": "delete_span", "start": "START\n", "end": "END\n"})


def test_span_anchor_must_hit_exactly_once():
    with pytest.raises(OverlayError):
        apply_op("START\nx\nSTART\nEND\n",
                 {"op": "delete_span", "start": "START\n", "end": "END\n"})


def test_unknown_op_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("x\n", {"op": "frobnicate", "find": "x", "with": "y"})


def test_ops_apply_in_order_and_see_previous_results():
    overlay = {"ops": [{"op": "replace", "find": "A", "with": "B"},
                       {"op": "replace", "find": "B", "with": "C"}]}
    assert apply_overlay("A\n", overlay) == "C\n"


MINIMAL_MANIFEST = """
[base]
dir = "lua_scripts"
ledger = "data/ledger.jsonl"
ledger_extra = "data/ledger_extra.jsonl"
[lane]
dir = "pilot/lanes/opus/data"
[compiler]
luac = "~/pyluadec-refactor/build/luac_sz4"
header_hex = "1b4c75615100010404040800"
[overlays]
order = ["alpha"]
[gim]
replace = [["card_zh", "card"]]
new = [["finale_cards", "card", "card/crd_1_a.gim"]]
[[fonts]]
size = 17
member = "pgf/A.pgf"
"""

ALPHA_OVERLAY = """
target = "snr_common.lua"
profile = "release"
why = "测试用"
[[ops]]
op = "replace"
find = "a"
with = "b"
"""


def _mk_layers(tmp_path, manifest=MINIMAL_MANIFEST, overlays=None):
    root = tmp_path / "layers"
    (root / "overlays").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "manifest.toml").write_text(manifest, encoding="utf-8")
    for name, body in (overlays or {"alpha": ALPHA_OVERLAY}).items():
        (root / "overlays" / f"{name}.toml").write_text(body, encoding="utf-8")
    (root / "vms_ids.toml").write_text("", encoding="utf-8")
    return root


def test_load_manifest_reads_all_sections(tmp_path):
    m = load_manifest(_mk_layers(tmp_path))
    assert m["base"]["dir"] == "lua_scripts"
    assert m["gim"]["replace"] == [["card_zh", "card"]]
    assert m["fonts"][0]["member"] == "pgf/A.pgf"


def test_unknown_top_level_key_is_hard_failure(tmp_path):
    root = _mk_layers(tmp_path, manifest=MINIMAL_MANIFEST + '\n[bogus]\nx = 1\n')
    with pytest.raises(SystemExit) as e:
        load_manifest(root)
    assert "bogus" in str(e.value)


def test_overlay_missing_why_is_hard_failure(tmp_path):
    bad = ALPHA_OVERLAY.replace('why = "测试用"', "")
    root = _mk_layers(tmp_path, overlays={"alpha": bad})
    with pytest.raises(SystemExit):
        load_overlay(root / "overlays" / "alpha.toml")


def test_overlay_bad_profile_is_hard_failure(tmp_path):
    bad = ALPHA_OVERLAY.replace('profile = "release"', 'profile = "staging"')
    root = _mk_layers(tmp_path, overlays={"alpha": bad})
    with pytest.raises(SystemExit):
        load_overlay(root / "overlays" / "alpha.toml")


def test_order_must_list_every_overlay_file(tmp_path):
    root = _mk_layers(tmp_path, overlays={"alpha": ALPHA_OVERLAY, "beta": ALPHA_OVERLAY})
    with pytest.raises(SystemExit) as e:
        load_manifest(root)
    assert "beta" in str(e.value)


def test_overlays_for_release_excludes_test_layers(tmp_path):
    test_layer = ALPHA_OVERLAY.replace('profile = "release"', 'profile = "test"')
    root = _mk_layers(tmp_path,
                      manifest=MINIMAL_MANIFEST.replace('order = ["alpha"]',
                                                        'order = ["alpha", "beta"]'),
                      overlays={"alpha": ALPHA_OVERLAY, "beta": test_layer})
    m = load_manifest(root)
    assert [o["_name"] for o in overlays_for(m, root, "release", {})] == ["alpha"]
    assert [o["_name"] for o in overlays_for(m, root, "test", {})] == ["alpha", "beta"]


def test_switch_off_drops_the_layer(tmp_path):
    sw = ALPHA_OVERLAY.replace('why = "测试用"', 'why = "测试用"\nswitch = "fast-boot"')
    root = _mk_layers(tmp_path, overlays={"alpha": sw})
    m = load_manifest(root)
    assert overlays_for(m, root, "release", {}) != []
    assert overlays_for(m, root, "release", {"fast-boot": False}) == []


def test_collect_ids_finds_vms_and_msg():
    assert collect_ids('vms(17300, "NONVOICE", "x")\nmsg(9001, "y")\n') == {17300, 9001}


def test_collect_ids_ignores_non_call_digits():
    assert collect_ids('local x = 17300\nxmsg(5, "y")\n') == set()


def test_check_ids_rejects_collision_with_ledger(tmp_path):
    root = _mk_layers(tmp_path)
    (root / "scripts" / "s.lua").write_text('vms(100, "NONVOICE", "x")\n', encoding="utf-8")
    man = load_manifest(root)
    man["scripts"] = [{"file": "scripts/s.lua", "member": "script/s.lua",
                       "profile": "release"}]
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "scripts/s.lua"\nvms = [[100, 200]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids={100})
    assert "100" in str(e.value)


def test_check_ids_rejects_id_outside_declared_range(tmp_path):
    root = _mk_layers(tmp_path)
    (root / "scripts" / "s.lua").write_text('vms(999, "NONVOICE", "x")\n', encoding="utf-8")
    man = load_manifest(root)
    man["scripts"] = [{"file": "scripts/s.lua", "member": "script/s.lua",
                       "profile": "release"}]
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "scripts/s.lua"\nvms = [[100, 200]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "999" in str(e.value)


def test_check_ids_rejects_overlapping_owner_ranges(tmp_path):
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "a"\nvms = [[100, 200]]\n'
        '[[ranges]]\nowner = "b"\nvms = [[150, 250]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "重叠" in str(e.value)


def test_check_ids_test_profile_range_exempt_from_ledger(tmp_path):
    # 探针沿用 9000 段——即便与账本相交，test 层也不因此报错。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "probe"\nprofile = "test"\nvms = [[9000, 9050]]\n',
        encoding="utf-8")
    check_ids(man, root, ledger_ids={9010})


def test_check_ids_release_profile_range_not_exempt_from_ledger(tmp_path):
    # 同一区段换成 release：不再免检，照样因撞账本报错——对照上一个测试。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "probe"\nprofile = "release"\nvms = [[9000, 9050]]\n',
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids={9010})
    assert "9010" in str(e.value)


def test_check_ids_test_profile_owners_still_mutually_exclusive(tmp_path):
    # 免于与保留集比对不等于免检——test 层之间仍须两两不交。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "a"\nprofile = "test"\nvms = [[9000, 9050]]\n'
        '[[ranges]]\nowner = "b"\nprofile = "test"\nvms = [[9020, 9080]]\n',
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "重叠" in str(e.value)


def test_check_ids_rejects_same_owner_listed_twice_in_scripts(tmp_path):
    # seen 字典真正防的场景：同一个 owner 被 manifest["scripts"] 重复登记
    # （同一文件两条 spec）——跨不同 owner 撞号早被区段两两不交挡住，到不了这里。
    root = _mk_layers(tmp_path)
    (root / "scripts" / "s.lua").write_text('vms(100, "NONVOICE", "x")\n', encoding="utf-8")
    man = load_manifest(root)
    spec = {"file": "scripts/s.lua", "member": "script/s.lua", "profile": "release"}
    man["scripts"] = [spec, dict(spec)]
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "scripts/s.lua"\nvms = [[100, 200]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "同时使用" in str(e.value)


def test_check_ids_rejects_bad_range_profile(tmp_path):
    # vms_ids.toml 的 [[ranges]] 也要挡非法 profile，跟 load_overlay 对 profile 的
    # 校验同规格——错字应该报「非法」，不该被悄悄当成某一种已知剖面处理。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "probe"\nprofile = "staging"\nvms = [[9000, 9050]]\n',
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "staging" in str(e.value)


def test_charset_takes_non_ascii_from_string_literals_only():
    src = 'vms(1, "NONVOICE", "谢幕")\n-- 注释里的字不算：飨\nlocal x = 1\n'
    codes = charset_of([src], ledger_jp=[], always=[])
    assert ord("谢") in codes and ord("幕") in codes
    assert ord("飨") not in codes


def test_charset_handles_escaped_quotes_inside_literal():
    codes = charset_of([r'vms(1, "NONVOICE", "他说\"好\"的字：甲")' + "\n"],
                       ledger_jp=[], always=[])
    assert ord("甲") in codes


def test_charset_includes_ledger_jp_and_always():
    codes = charset_of([], ledger_jp=["彩野"], always=[ord("★")])
    assert ord("彩") in codes and ord("★") in codes


def test_charset_filters_to_bmp_printable():
    codes = charset_of(['vms(1, "X", "a\U0001F600b")' + "\n"], ledger_jp=[], always=[])
    assert 0x1F600 not in codes           # PGF charmap 只到 BMP
    assert all(0x20 <= c <= 0xFFFF for c in codes)


def test_charset_is_sorted_and_unique():
    codes = charset_of(['vms(1, "X", "乙甲甲")' + "\n"], ledger_jp=[], always=[])
    assert codes == sorted(set(codes))


def test_write_charset_format_matches_ttf_pgf_expectation(tmp_path):
    p = tmp_path / "ucs.txt"
    write_charset([0x20, 0x4E00], p)
    assert p.read_text() == "0020\n4e00\n"


def test_provenance_has_required_top_level_keys(tmp_path):
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    prov = provenance("release", man, root, applied=[], scripts_added=[],
                      members={"replaced": 1, "added": 2}, outputs={})
    assert set(prov) >= {"profile", "built_at", "git", "inputs", "tools",
                         "layers_applied", "scripts_added", "members", "outputs"}
    assert prov["members"] == {"replaced": 1, "added": 2}


def test_provenance_inputs_include_lua_scripts_tree_and_lane_and_ledger_keys(tmp_path):
    # Finding 1 的回归钉子：inputs 曾经只哈希账本与车道三文件，唯独漏了基座本身——
    # 换基座（如 migrate_base.py 重跑）不会反映在指纹里。这里只断言键存在，不比对
    # 具体哈希值，因为 lua_scripts/ 的真实内容会随仓库演进变化。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    prov = provenance("release", man, root, applied=[], scripts_added=[],
                      members={}, outputs={})
    assert "lua_scripts" in prov["inputs"]
    assert "pilot/lanes/opus/data/forward.jsonl" in prov["inputs"]
    assert "data/ledger.jsonl" in prov["inputs"]
    assert "data/ledger_extra.jsonl" in prov["inputs"]


def test_provenance_tools_honours_env_overrides(tmp_path, monkeypatch):
    # Finding 2 的回归钉子：/tmp 下的 ttf_pgf 重启即失，luac_sz4 是仓库外二进制，
    # 两者都要能用 SNDL_TTF_PGF / SNDL_LUAC 重新指向——否则「文件不存在」被记成
    # "absent"，而实际构建明明用了别处的那一份，取证就成了误导而非证据。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    fake_luac = tmp_path / "fake_luac"
    fake_luac.write_bytes(b"fake luac binary")
    fake_ttf = tmp_path / "fake_ttf_pgf"
    fake_ttf.write_bytes(b"fake ttf_pgf binary")
    monkeypatch.setenv("SNDL_LUAC", str(fake_luac))
    monkeypatch.setenv("SNDL_TTF_PGF", str(fake_ttf))
    prov = provenance("release", man, root, applied=[], scripts_added=[],
                      members={}, outputs={})
    assert prov["tools"]["luac_sz4"] == hashlib.sha256(fake_luac.read_bytes()).hexdigest()
    assert prov["tools"]["ttf_pgf"] == hashlib.sha256(fake_ttf.read_bytes()).hexdigest()


def test_provenance_layers_applied_reflects_real_overlay_dict(tmp_path):
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    overlay = load_overlay(root / "overlays" / "alpha.toml")
    prov = provenance("release", man, root, applied=[overlay], scripts_added=[],
                      members={}, outputs={})
    assert prov["layers_applied"] == [{"overlay": "alpha", "target": "snr_common.lua", "ops": 1}]


def test_write_provenance_round_trips_through_json(tmp_path):
    p = tmp_path / "provenance.json"
    write_provenance({"profile": "release", "members": {"replaced": 1}}, p)
    assert json.loads(p.read_text(encoding="utf-8")) == {"profile": "release",
                                                          "members": {"replaced": 1}}


def test_provenance_treats_empty_env_override_as_unset(tmp_path, monkeypatch):
    # Finding（Important，本轮修复）：`export SNDL_LUAC=` / `SNDL_TTF_PGF=`（shell 手滑
    # 设成空串）不等于「没设」——os.environ.get(key, default) 只看键在不在 os.environ
    # 里，键存在但值是空串时仍会拿到 ""，`Path("").expanduser()` 归一化成
    # `PosixPath('.')`，那是个存在的目录：不空串的兜底逻辑被跳过，_sha256 直接在
    # read_bytes() 上崩成 IsADirectoryError——provenance 是取证，不该被这种输入崩掉。
    #
    # 用「空串结果 == 完全不设时的结果」而不是硬编码期望哈希值来断言：这样测试不
    # 依赖本机是否真的装了 luac_sz4 / ttf_pgf，两台机器（有工具 / 没工具）都能跑，
    # 且如果修复只让它不崩但退化成误报的 "absent"（工具其实在默认路径上），
    # 这里也会因为跟 baseline 不一致而抓到。
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    monkeypatch.delenv("SNDL_LUAC", raising=False)
    monkeypatch.delenv("SNDL_TTF_PGF", raising=False)
    baseline = provenance("release", man, root, applied=[], scripts_added=[],
                          members={}, outputs={})

    monkeypatch.setenv("SNDL_LUAC", "")
    monkeypatch.setenv("SNDL_TTF_PGF", "")
    with_empty = provenance("release", man, root, applied=[], scripts_added=[],
                            members={}, outputs={})

    assert with_empty["tools"] == baseline["tools"]


def test_build_font_reads_charset_file_not_lane(tmp_path, monkeypatch):
    """build() 的字集必须来自参数指定的文件——车道依赖已经拆掉了。"""
    import tools.build_font as bf
    ucs = tmp_path / "ucs.txt"
    ucs.write_text("0020\n4e00\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(bf, "TTF_PGF", tmp_path / "fake_ttf_pgf")
    (tmp_path / "fake_ttf_pgf").write_text("#!/bin/sh\ntouch \"$2\"\n", encoding="utf-8")
    (tmp_path / "fake_ttf_pgf").chmod(0o755)
    monkeypatch.setattr(bf, "widen_latin", lambda ttf, out: (calls.append(out), ttf)[1])
    out = bf.build(ucs, tmp_path / "out", sizes=(17,))
    assert out and out[0].name == "lxgw17.pgf"
    assert not hasattr(bf, "corpus_chars"), "corpus_chars 应当已删除（字集改由 layers 算）"


def test_build_font_rejects_missing_or_empty_charset(tmp_path, monkeypatch):
    """字集文件缺失/为空必须硬失败——2026-09-03 实测 ttf_pgf 遇到这种输入不报错，
    而是静默退化成渲染整个字库（43478 字形、5.3MB），exit code 仍是 0、pgf 仍会
    落盘，比漏几个字严重得多（正是模块开头那次引擎崩溃的原样复现），不能放行。
    """
    import tools.build_font as bf
    monkeypatch.setattr(bf, "TTF_PGF", tmp_path / "fake_ttf_pgf")
    (tmp_path / "fake_ttf_pgf").write_text("#!/bin/sh\ntouch \"$2\"\n", encoding="utf-8")
    (tmp_path / "fake_ttf_pgf").chmod(0o755)

    missing = tmp_path / "missing.txt"
    with pytest.raises(SystemExit):
        bf.build(missing, tmp_path / "out1", sizes=(17,))

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        bf.build(empty, tmp_path / "out2", sizes=(17,))
