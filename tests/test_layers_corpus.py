"""真语料测试：全部 release 层在真实基座上精确命中。

夹具证明不了「锚点还在」——只能对真语料跑。这是新增文本以后的日常守门员。
"""
import pytest

from tools.layers import (LAYERS, build_final_sources, check_ids, collect_ids,
                          load_manifest, load_overlay, REPO)
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


def test_every_release_overlay_hits_on_real_base():
    sources, applied, _ = build_final_sources("release")
    assert [o["_name"] for o in applied] == ["fonts", "encore-menu"]
    assert sources["snr_common.lua"].count('pgf/LXGWWenKai-Regular.pgf') == 1
    assert "layerKeyCur" in sources["snr_mainmenu.lua"]


def test_every_test_overlay_hits_on_real_base():
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
    """范围本身从登记表读，不写死——这条测试要钉的是「脚本没有越出自己声明的段」，
    不是「17300/17481 这两个数字」；正当地在 vms_ids.toml 里扩段不该反过来把这条
    测试也改瞎。"""
    import tomllib
    with open(LAYERS / "vms_ids.toml", "rb") as f:
        reg = tomllib.load(f)
    entry = next(r for r in reg["ranges"] if r["owner"] == "scripts/snr_finale.lua")
    lo, hi = entry["vms"][0]

    text = (LAYERS / "scripts" / "snr_finale.lua").read_text(encoding="utf-8")
    ids = collect_ids(text)
    assert ids, "snr_finale.lua 里一条 vms 都没扫到——正则或文件出了问题"
    assert min(ids) >= lo and max(ids) <= hi


def test_finale_dispatch_lands_in_the_card_140_menu_form():
    """encore-menu.toml 的 op4 锚点「elseif l1_0 == l0_1.library then」在基座里命中
    2 次：菜单形态 2（无卡 140，其 library 分支前没有 section7，靠 #l0_0.layerKey2
    退场）与形态 2+140（其 library 分支紧跟在 section7 CIRCLE 分支之后，靠写死的
    `for l1_7 = 1, 11` 退场）——只有后者具备卡 144 存在的前提。op4 用
    count=2/occurrence=-1 命中后者；字节码闸能分辨对错，但闸比对的基线是临时目录
    （/tmp 与 SDD 工作区里那份 gitignore 副本），两者迟早都会不在。装错形态是
    这个层最容易被后人改坏、又最难从字面上看出来的一种错——两处锚点文本逐字相同，
    review 时肉眼不容易分辨改动落在哪一处。这里直接对装配结果做源码级断言，不
    依赖任何外部基线：finale 分发只能出现一次，且必须排在 section7 分发
    （s7f-10，只在形态 2+140 那条 CIRCLE 链路里出现）之后。
    """
    sources, _, _ = build_final_sources("release")
    text = sources["snr_mainmenu.lua"]

    anchor = "elseif l1_0 == l0_1.finale then"
    hits = text.count(anchor)
    assert hits == 1, (
        f"finale 分发应当只出现一次，实际 {hits} 次——"
        f"encore-menu.toml 的 op4 可能又变得不唯一了，检查 count/occurrence")

    finale_at = text.index(anchor)
    s7f_at = text.index('doScriptScene = "s7f-10"')
    assert finale_at > s7f_at, (
        "finale 分发出现在 section7 分发（doScriptScene = \"s7f-10\"）之前——"
        "说明 op4 把它插进了没有 section7 的菜单形态（形态 2，无卡 140），而不是"
        "卡 140∧144 那条唯一持有 layerKey4/finale 枚举的分支；去查 encore-menu.toml"
        "的 count/occurrence 是不是又选中了第一处而非最后一处")


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
