"""testboot 生成器：产层文件，不再直接写字节码。"""
import tomllib

import pytest

from tools.testboot import generate


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


def test_generated_overlays_are_never_release(tmp_path):
    for mode, opts in (("mainmenu", {}), ("card", {"card": 103}), ("scene", {"scene": "s1s_20"})):
        r = generate(mode, tmp_path, **opts)
        for rel in r["overlays"]:
            ov = tomllib.loads((tmp_path / rel).read_text(encoding="utf-8"))
            assert ov["profile"] == "test", f"{mode} 产出了 release 层——测试补丁绝不能出货"


def test_unknown_mode_is_hard_failure(tmp_path):
    with pytest.raises(SystemExit):
        generate("frobnicate", tmp_path)
