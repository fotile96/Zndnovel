"""真语料测试：全部 release 层在真实基座上精确命中。

夹具证明不了「锚点还在」——只能对真语料跑。这是新增文本以后的日常守门员。
"""
import pytest

from tools.layers import (LAYERS, build_final_sources, check_ids, collect_ids,
                          load_manifest, load_overlay, overlays_for, REPO)
from tools.pipelib import read_jsonl


@pytest.fixture(scope="module")
def manifest():
    return load_manifest()


@pytest.fixture(scope="module")
def ledger_rows(manifest):
    return read_jsonl(REPO / manifest["base"]["ledger"])


@pytest.fixture(scope="module")
def ledger_ids(ledger_rows):
    return {r["id"] for r in ledger_rows}


def test_every_release_overlay_hits_on_real_base(manifest):
    sources, applied, _ = build_final_sources("release")
    assert [o["_name"] for o in applied] == ["fonts", "encore-menu"]
    assert sources["snr_common.lua"].count('pgf/LXGWWenKai-Regular.pgf') == 1
    assert "layerKeyCur" in sources["snr_mainmenu.lua"]


def test_every_test_overlay_hits_on_real_base(manifest):
    sources, applied, _ = build_final_sources("test")
    assert [o["_name"] for o in applied] == [
        "fonts", "encore-menu", "strip-ipl", "boot-handoff"]
    assert 'run(cGetFileName("script", "snr_test"))' in sources["snr_common.lua"]
    assert "layerMoveAlpha(0, 100, 120)" not in sources["snr_common.lua"]


def test_fast_boot_switch_off_keeps_ipl():
    sources, applied, _ = build_final_sources("test", switches={"fast-boot": False})
    assert "strip-ipl" not in [o["_name"] for o in applied]
    assert "layerMoveAlpha(0, 100, 120)" in sources["snr_common.lua"]


def test_id_registry_agrees_with_real_ledger(manifest, ledger_ids):
    check_ids(manifest, LAYERS, ledger_ids)


def test_finale_ids_are_inside_declared_range():
    text = (LAYERS / "scripts" / "snr_finale.lua").read_text(encoding="utf-8")
    ids = collect_ids(text)
    assert ids, "snr_finale.lua 里一条 vms 都没扫到——正则或文件出了问题"
    assert min(ids) >= 17300 and max(ids) <= 17481


def test_overlay_targets_all_exist_in_base(manifest):
    base = REPO / manifest["base"]["dir"]
    for name in manifest["overlays"]["order"]:
        ov = load_overlay(LAYERS / "overlays" / f"{name}.toml")
        assert (base / ov["target"]).exists(), f"{name} 的 target 不在基座里"


def test_injected_sources_translates_and_skips_old_font_patch(manifest, ledger_rows):
    """`_injected_sources` 是本任务在 brief 之外新增的（tools/layers.py）：CLI 的
    `check --compare-compiled` 拿它给 `build_final_sources` 供真译文，因为比对
    目标是真实发布链路编出的字节码（译文早已注入），`build_final_sources` 缺省
    「读基座原文」的快速路径在那种场景下文不对题——几乎每个含对白的文件都会
    被判「不一致」，而这不是层写错了。

    这里钉两件事：①真的翻译了（重头故事章节 snr_s1_10_s 与基座原文不再相同）；
    ②刻意不重放 tools/inject_lua.py 里那段槽 1 字体补丁（FONT_SLOT1_FROM/TO）
    ——那一步已转交 layers/overlays/fonts.toml；两处都做的话，fonts 层的
    `find` 锚点在注入后就找不到了（叠加引擎按 count 断言硬失败，不会静默叠两次）。
    """
    from tools.layers import _injected_sources

    injected = _injected_sources(manifest, ledger_rows)
    base = REPO / manifest["base"]["dir"]
    assert set(injected) == {p.name for p in base.glob("*.lua")}

    pristine = (base / "snr_s1_10_s.lua").read_text(encoding="utf-8")
    assert injected["snr_s1_10_s.lua"] != pristine

    assert 'fontLoad(1, "pgf/tsukuminpro_e_09.pgf")' in injected["snr_common.lua"]
