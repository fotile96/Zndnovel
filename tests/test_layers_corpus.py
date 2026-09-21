"""真语料测试：全部 release 层在真实基座上精确命中。

夹具证明不了「锚点还在」——只能对真语料跑。这是新增文本以后的日常守门员。
"""
import re
from pathlib import Path

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
    assert [o["_name"] for o in applied] == [
        "fonts", "cardname-halfwidth", "encore-menu", "finale-read-flag", "title-logo-zh",
        "finale-gallery-cg", "novel-notice-s1f", "novel-notice-entry", "boot-dedication"]
    assert sources["snr_common.lua"].count('pgf/LXGWWenKai-Regular.pgf') == 1
    # cardname-halfwidth：cfontPrint 不再经 cHan2Zen（卡名拉丁半角），定义本身保留
    assert "cHan2Zen(l1_5)" not in sources["snr_common.lua"]
    assert "fontPrint(l1_0, l1_1, l1_2, l1_3, l1_4, l1_5)" in sources["snr_common.lua"]
    assert "cHan2Zen = function" in sources["snr_common.lua"]
    assert "layerKeyCur" in sources["snr_mainmenu.lua"]


def test_every_test_overlay_hits_on_real_base():
    sources, applied, _ = build_final_sources("test")
    assert [o["_name"] for o in applied] == [
        "fonts", "cardname-halfwidth", "encore-menu", "finale-read-flag", "title-logo-zh",
        "finale-gallery-cg", "novel-notice-s1f", "novel-notice-entry", "boot-dedication", "strip-ipl", "boot-handoff"]
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
    segments = [range(lo, hi + 1) for lo, hi in entry["vms"]]   # 可登记多段（v3 起两段）

    text = (LAYERS / "scripts" / "snr_finale.lua").read_text(encoding="utf-8")
    ids = collect_ids(text)
    assert ids, "snr_finale.lua 里一条 vms 都没扫到——正则或文件出了问题"
    stray = sorted(i for i in ids if not any(i in seg for seg in segments))
    assert not stray, f"越出登记段的 id: {stray[:10]}"
    # 每一段都真的在用：登记了却一条不占，说明段是多余的或写错了
    for seg in segments:
        assert any(i in seg for i in ids), f"登记段 {seg} 里没有任何 vms"


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


def test_injected_sources_translates_and_leaves_font_lines_untouched(manifest, ledger_rows):
    """`_injected_sources` 是本任务在 brief 之外新增的（tools/layers.py）：CLI 的
    `check --compare-compiled` 拿它给 `build_final_sources` 供真译文，因为比对
    目标是真实发布链路编出的字节码（译文早已注入），`build_final_sources` 缺省
    「读基座原文」的快速路径在那种场景下文不对题——几乎每个含对白的文件都会
    被判「不一致」，而这不是层写错了。

    这里钉两件事：①真的翻译了（重头故事章节 snr_s1_10_s 与基座原文不再相同）；
    ②`inject_tree()` 不触碰 `fontLoad` 的槽 0、槽 1 任何一行——两个字体槽的改写权
    完整属于 `layers/overlays/fonts.toml`（曾经存在于 tools/inject_lua.py 的槽 1
    补丁 `FONT_SLOT1_FROM/TO` 已随「inject_lua 收缩为纯注入」整段删除，不是「刻意
    绕开」，是那段代码已经不存在了）。若 inject_tree() 改过其中任何一行，fonts 层
    的 `find` 锚点在注入后就会找不到、按 count 断言当场硬失败，不会静默叠两次。
    """
    from tools.layers import _injected_sources

    injected = _injected_sources(manifest, ledger_rows)
    base = REPO / manifest["base"]["dir"]
    assert set(injected) == {p.name for p in base.glob("*.lua")}

    pristine = (base / "snr_s1_10_s.lua").read_text(encoding="utf-8")
    assert injected["snr_s1_10_s.lua"] != pristine

    assert 'fontLoad(0, "pgf/tsukuminpro_e_17.pgf")' in injected["snr_common.lua"]
    assert 'fontLoad(1, "pgf/tsukuminpro_e_09.pgf")' in injected["snr_common.lua"]


def test_title_logo_swap_is_wired_end_to_end(manifest):
    """谢幕读完 → 系统旗标 → 主菜单换中文题名，三段各在最终源里出现且只出现一次。

    finale-read-flag 层在 snr_common 的 systemSave 字面表里声明缺省 false；
    title-logo-zh 层把 snr_mainmenu 的 logo 绘制改成条件分支，else 里保留原
    layerCopy（旧存档/未读谢幕时版面逐字不变）；snr_finale.lua 在 fin-50 之后、
    `doScriptScene = "end"` 之前置位并 autoSystemSave(0)——顺序反了旗标会漏写盘。
    """
    import re
    sources, _, _ = build_final_sources("release")
    common, menu = sources["snr_common.lua"], sources["snr_mainmenu.lua"]
    fin = (LAYERS / "scripts" / "snr_finale.lua").read_text(encoding="utf-8")

    assert common.count("finaleReadFlag = false") == 1
    assert re.search(r"^systemSave = \{.*finaleReadFlag = false\}$", common, re.M), \
        "缺省值没落在 systemSave 那张字面表里"

    zh_load = 'layerLoad(l0_0.layerNumber.logo, cGetFileName("sysgim", "title_01_c"))'
    ja_copy = "layerCopy(l0_0.layerNumber.logo, layerName.title_01_a)"
    cond = "if systemSave.finaleReadFlag == true then"
    assert menu.count(zh_load) == 1 and menu.count(ja_copy) == 1 and menu.count(cond) == 1
    assert menu.index(cond) < menu.index(zh_load) < menu.index(ja_copy) < menu.index(
        "layerPosition(l0_0.layerNumber.logo, 38, 10)")

    i50 = fin.index("scene_fin_50(doScriptScene")
    seg = fin[i50:fin.index('doScriptScene = "end"', i50)]
    seg = "\n".join(l for l in seg.splitlines() if not l.lstrip().startswith("--"))  # 去注释再查语句
    assert "systemSave.finaleReadFlag = true" in seg and "autoSystemSave(0)" in seg
    assert seg.index("systemSave.finaleReadFlag = true") < seg.index("autoSystemSave(0)")

    assert ["finale_title", "sysgim", "sysgim/title_01_a.gim"] in \
        [list(x) for x in manifest["gim"]["new"]]


_FLAG_LINE_OK = [
    re.compile(r"^systemSave = \{.*finaleReadFlag = false\}$"),                 # 字面表缺省
    re.compile(r"^\s*if systemSave\.finaleReadFlag == (?:true|nil) then$"),     # 严格读
    re.compile(r"^\s*systemSave\.finaleReadFlag = (?:true|false)$"),            # 赋值
]


def _flag_lines():
    out = []
    for profile in ("release", "test"):
        sources, _, _ = build_final_sources(profile)
        for name, text in sources.items():
            out += [(f"{profile}:{name}", l) for l in text.splitlines()
                    if "finaleReadFlag" in l and not l.lstrip().startswith("--")]
    fin = (LAYERS / "scripts" / "snr_finale.lua").read_text(encoding="utf-8")
    out += [("scripts/snr_finale.lua", l) for l in fin.splitlines()
            if "finaleReadFlag" in l and not l.lstrip().startswith("--")]
    return out


def test_finale_read_flag_every_use_is_nil_safe():
    """老系统数据（原版游戏 / 旧 release 写的）里没有 finaleReadFlag 这个键：runAutoLoad()
    是整表替换，snr_common 字面表里的缺省 false 在那之后不复存在，读出来是 nil。
    所以全部用法只准是三种 nil 安全形态：字面表缺省、`== nil`/`== true` 严格判断、赋
    true/false——不准做算术、拼接、取下标、或直接传给要布尔的 C 原语（nil 进 C 侧会
    「boolean expected」）。并且主菜单读之前必须有一次 `== nil` 补默认（自愈）。"""
    lines = _flag_lines()
    assert lines, "最终源里一处 finaleReadFlag 都没有——层没装上？"
    bad = [(w, l) for w, l in lines if not any(r.match(l) for r in _FLAG_LINE_OK)]
    assert not bad, f"finaleReadFlag 出现了非 nil 安全的用法：{bad}"
    menu = [l for w, l in lines if w.endswith("snr_mainmenu.lua")]
    assert any("== nil" in l for l in menu), "主菜单缺少 `== nil` 补默认——老存档兼容自愈没了"


def _lua_interpreter():
    import os
    luac = Path(os.environ.get("SNDL_LUAC") or load_manifest()["compiler"]["luac"]).expanduser()
    lua = Path(os.environ.get("SNDL_LUA") or luac.with_name("lua_sz4"))
    if not lua.exists():
        pytest.skip(f"缺 Lua 5.1 解释器 {lua}（与 luac_sz4 同目录的 lua_sz4，或设 SNDL_LUA）")
    return lua


@pytest.mark.parametrize("state, expect_call, expect_flag", [
    ("{messageSpeed = 3, storyLineSkip = 0}", "copy:1:212", "false"),   # 原版/旧 release：无此键
    ("{finaleReadFlag = false}", "copy:1:212", "false"),
    ("{finaleReadFlag = true}", "load:1:sysgim/title_01_c.gim", "true"),
])
def test_title_logo_snippet_runs_on_old_system_data(state, expect_call, expect_flag):
    """把 title-logo-zh 层实际注入的那段 Lua 原文，在与游戏同源的 Lua 5.1 解释器里跑三种
    systemSave：无键（老存档）→ 不报错、走 layerCopy 原 logo、键被补成 false；false 同；
    true → layerLoad 中文 logo。这是行为级证据，不只看字面形态。"""
    import subprocess
    lua = _lua_interpreter()
    overlay = load_overlay(LAYERS / "overlays" / "title-logo-zh.toml")
    snippet = overlay["ops"][0]["with"]
    harness = f"""
local calls = {{}}
l0_0 = {{layerNumber = {{logo = 1}}}}
layerName = {{title_01_a = 212}}
function layerLoad(layer, file) calls[#calls + 1] = "load:" .. layer .. ":" .. file end
function layerCopy(dst, src) calls[#calls + 1] = "copy:" .. dst .. ":" .. src end
function cGetFileName(kind, name) return kind .. "/" .. name .. ".gim" end
systemSave = {state}
{snippet}
print(table.concat(calls, ",") .. "|" .. tostring(systemSave.finaleReadFlag))
"""
    proc = subprocess.run([str(lua), "-"], input=harness, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == f"{expect_call}|{expect_flag}"


@pytest.mark.parametrize("layer", ["novel-notice-s1f", "novel-notice-entry"])
def test_novel_notice_ids_are_inside_declared_range(layer):
    """文库说明两层（2026-09-21）：层里新引入的 vms id 全部落在 vms_ids.toml 为它登记的段内。
    范围从登记表读、不写死（同 finale 那条的理由）。check_ids 本身已会硬失败，这条是文档化证据。"""
    import tomllib
    with open(LAYERS / "vms_ids.toml", "rb") as f:
        reg = tomllib.load(f)
    entry = next(r for r in reg["ranges"] if r["owner"] == f"overlays/{layer}.toml")
    lo, hi = entry["vms"][0]
    ov = load_overlay(LAYERS / "overlays" / f"{layer}.toml")
    ids = set()
    for op in ov["ops"]:
        ids |= set(collect_ids(op.get("text", "") + op.get("with", "")))
    assert ids, f"{layer} 里一条 vms 都没扫到"
    assert min(ids) >= lo and max(ids) <= hi


def test_novel_notice_lands_where_intended():
    """s1f 块插在 scene_s1f_complete 的淡出之前、原通知 17011 之后；入口块插在
    「一本也没有」早退之后、advPart(false) 之前，且有 nil 安全的一次性守卫。"""
    srcs, _, _ = build_final_sources("release")
    s1f = srcs["snr_s1_10_f.lua"]
    i_last_notice, i_new, i_fade = s1f.index("vms(17011,"), s1f.index("vms(17500,"), s1f.rindex("comEffectFadeOut(60)")
    assert i_last_notice < i_new < i_fade
    assert s1f.index("vms(17507,") < i_fade
    novel = srcs["snr_novel.lua"]
    i_empty, i_guard, i_adv = novel.index("run(cGetFileName(\"script\", \"snr_mainmenu\"))"), \
        novel.index("if systemSave.novelNoticeSeen ~= true then"), novel.index("advPart(false)")
    assert i_empty < i_guard < i_adv
    assert "systemSave.novelNoticeSeen = true" in novel


def test_boot_dedication_card_lands_between_copyright_and_autosave():
    """开机第五卡：层 4 整块（载入→淡入→停留→淡出）恰在层 2 淡出之后、层 3 淡入之前，
    节奏与前四卡逐帧相同；cInitGame 之前层 4 没有别的用途。"""
    src = build_final_sources("release")[0]["snr_common.lua"]
    body = src[src.index("main = function()"):]
    block = ('    layerLoad(4, cGetFileName("sysgim", "IPL03"))\n'
             '    layerAlpha(4, 0)\n'
             '    layerMoveAlpha(4, 100, 120)\n'
             '    wait(120)\n'
             '    keyWait(180)\n'
             '    layerMoveAlpha(4, 0, 120)\n'
             '    wait(120)\n')
    assert body.count(block) == 1
    i2, i4, i3 = (body.index("layerMoveAlpha(2, 0, 120)\n    wait(120)\n"),
                  body.index(block), body.index("layerMoveAlpha(3, 100, 120)"))
    assert i2 < i4 < i3
    assert body[i2:i4] == "layerMoveAlpha(2, 0, 120)\n    wait(120)\n"   # 紧接层 2 淡出
    assert body[i4 + len(block):].startswith("    layerMoveAlpha(3, 100, 120)")  # 紧接层 3 淡入
    pre = body[:body.index("cInitGame()")]
    assert pre.count("layerLoad(4,") == 1 and "layerCopy(4" not in pre
    # 前四卡的节奏没被动到
    for n in range(4):
        assert f"layerMoveAlpha({n}, 100, 120)" in body and f"layerMoveAlpha({n}, 0, 120)" in body


def test_fast_boot_strips_the_dedication_card_with_the_rest_of_the_ipl():
    """test 剖面快启动：strip-ipl 的 delete_span 连第五卡整块一起剥掉（否则没烤该面的 test 盘
    开机会去载不存在的 IPL03）；`--no-fast-boot` 时整块保留。"""
    sources, applied, _ = build_final_sources("test")
    names = [o["_name"] for o in applied]
    assert names.index("boot-dedication") < names.index("strip-ipl")
    assert "IPL03" not in sources["snr_common.lua"]
    sources, _, _ = build_final_sources("test", switches={"fast-boot": False})
    assert sources["snr_common.lua"].count('cGetFileName("sysgim", "IPL03")') == 1


def test_boot_dedication_member_is_registered_with_ipl01_as_template(manifest):
    assert ["boot_dedication", "sysgim", "sysgim/IPL01.gim"] in \
        [list(x) for x in manifest["gim"]["new"]]
    why = load_overlay(LAYERS / "overlays" / "boot-dedication.toml")["why"]
    assert "∀" in why and "不画" in why          # 「只写文字不画 ∀」的裁定留在层里，别被后人"补上"
