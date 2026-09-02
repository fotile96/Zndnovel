"""testboot 生成器：产层文件，不再直接写字节码。"""
import tomllib

import pytest

from tools.testboot import _MODES, generate


def test_mainmenu_mode_emits_test_script(tmp_path):
    r = generate("mainmenu", tmp_path)
    assert r["scripts"] == ["scripts/snr_test.lua"]
    src = (tmp_path / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert "gameSave.startMenuState = 2" in src
    assert 'run(cGetFileName("script", "snr_mainmenu"))' in src


def test_scene_mode_targets_the_right_chapter_script(tmp_path):
    generate("scene", tmp_path, scene="fin-30")
    src = (tmp_path / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'doScriptScene = "fin-30"' in src
    assert 'run(cGetFileName("script", "snr_finale"))' in src


def test_card_mode_emits_short_circuit_overlay(tmp_path):
    r = generate("card", tmp_path, card=103)
    assert "overlays/card-short-circuit.toml" in r["overlays"]
    ov = tomllib.loads(
        (tmp_path / "overlays" / "card-short-circuit.toml").read_text(encoding="utf-8"))
    assert ov["target"] == "snr_crd_103.lua"
    assert ov["profile"] == "test"
    assert ov["ops"][0]["find"] == "oCard.selectCardObj()"
    # count/with 是这次改造的核心产出（count 照译文注入后的源数，见
    # _injected_source 的 docstring；with 取 dag.json 答案集合里最小的一个，见
    # card_answer）。此前只断言 find，count/with 完全不受保护——一次把 count 算
    # 错、把 with 算错、甚至两个字段互换，都会全绿通过。这两条钉死具体数值，
    # 任何偏离这两个数的改动都会在这里现形（已用故障注入验证：把 with 改成
    # answer+1 会让第二条断言在这里报 '134' != '133' 而不是静默通过）。
    # ⚠ 诚实说明：crd_103 的 count 在 lua_scripts/ 原文与译文注入后的源里恰好
    # 都是 10（全库 103 个含该调用的文件穷举验证过，无一例外）——这两条断言
    # 不能单独证明"count 是照哪份源算的"，那件事由 count 缺陷本身的机制修复
    # 保证（tools/testboot.py 的 _injected_source 与 short_circuit_card），
    # 这里钉的是"数值本身不会被静默改坏"。
    assert ov["ops"][0]["count"] == 10
    assert ov["ops"][0]["with"] == "133"
    # crd_103 是多步骤大谜题（10 处递卡、10 个不同答案）：结构化的 warnings 必须
    # 带上这条已知限制，供程序化调用方（Task 8 的 build_disc）判断"这份产物打了
    # 折扣"，不必解析 print() 或截获 stdout。
    assert r["warnings"] and "多步骤" in r["warnings"][0]


def test_single_answer_card_has_no_warning(tmp_path):
    r = generate("card", tmp_path, card=10)  # crd_10：1 处递卡、1 个答案
    assert r["warnings"] == []


def test_generated_overlays_are_never_release(tmp_path):
    # 驱动源是模块自己的模式表 _MODES，不是手写的三元组：新增一种会产 overlay 的
    # 模式时，这条测试自动跟着覆盖到，不必有人记得回来把它加进硬编码列表。
    for mode in _MODES:
        opts = {"card": 103} if mode == "card" else {}
        r = generate(mode, tmp_path, **opts)
        for rel in r["overlays"]:
            ov = tomllib.loads((tmp_path / rel).read_text(encoding="utf-8"))
            assert ov["profile"] == "test", f"{mode} 产出了 release 层——测试补丁绝不能出货"


def test_generate_clears_stale_layers_from_previous_call(tmp_path):
    """产物目录不是只增不减的：第二次调用必须先清掉第一次的残留，磁盘实况才会
    跟返回值一致。Task 8 的消费方按 glob 扫 overlays/*.toml 施加，一份调用方
    以为已经不存在的旧层会被悄悄套用到跟它毫不相干的下一次构建上。
    """
    generate("card", tmp_path, card=103)
    assert (tmp_path / "overlays" / "card-short-circuit.toml").exists()

    r2 = generate("mainmenu", tmp_path)
    assert r2["overlays"] == []

    on_disk = sorted(p.relative_to(tmp_path).as_posix()
                     for p in tmp_path.rglob("*") if p.is_file())
    assert on_disk == sorted(r2["scripts"] + r2["overlays"])


def test_unknown_mode_is_hard_failure(tmp_path):
    with pytest.raises(SystemExit):
        generate("frobnicate", tmp_path)
