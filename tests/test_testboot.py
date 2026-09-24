"""testboot 生成器：产层文件，不再直接写字节码。"""
import shutil

import tomllib

import pytest

from tools.testboot import _MODES, generate, REPO


@pytest.fixture
def out_dir(tmp_path):
    """generate() 现在会拒绝不在 build/ 之下的 out_dir（见 tools/testboot.py 的
    守卫：判归属只看目录名，layers/scripts、layers/overlays 与本工具产物目录
    同构同名，传错一次会静默删掉手写入库的层文件）。真实调用方永远传
    build/<profile>/generated/ 这类路径，这里用仓库 build/ 下的一个按测试名
    区分的临时子目录来匹配这条契约，测完清掉。"""
    d = REPO / "build" / "_test_testboot" / tmp_path.name
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_mainmenu_mode_emits_test_script(out_dir):
    r = generate("mainmenu", out_dir)
    assert r["scripts"] == ["scripts/snr_test.lua"]
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert "gameSave.startMenuState = 2" in src
    assert 'run(cGetFileName("script", "snr_mainmenu"))' in src


def test_scene_mode_targets_the_right_chapter_script(out_dir):
    generate("scene", out_dir, scene="fin-30")
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'doScriptScene = "fin-30"' in src
    assert 'run(cGetFileName("script", "snr_finale"))' in src


def test_card_mode_emits_short_circuit_overlay(out_dir):
    r = generate("card", out_dir, card=103)
    assert "overlays/card-short-circuit.toml" in r["overlays"]
    ov = tomllib.loads(
        (out_dir / "overlays" / "card-short-circuit.toml").read_text(encoding="utf-8"))
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


def test_single_answer_card_has_no_warning(out_dir):
    r = generate("card", out_dir, card=10)  # crd_10：1 处递卡、1 个答案
    assert r["warnings"] == []


def test_generated_overlays_are_never_release(out_dir):
    # 驱动源是模块自己的模式表 _MODES，不是手写的三元组：新增一种会产 overlay 的
    # 模式时，这条测试自动跟着覆盖到，不必有人记得回来把它加进硬编码列表。
    for mode in _MODES:
        opts = {"card": 103} if mode == "card" else {}
        r = generate(mode, out_dir, **opts)
        for rel in r["overlays"]:
            ov = tomllib.loads((out_dir / rel).read_text(encoding="utf-8"))
            assert ov["profile"] == "test", f"{mode} 产出了 release 层——测试补丁绝不能出货"


def test_generate_clears_stale_layers_from_previous_call(out_dir):
    """产物目录不是只增不减的：第二次调用必须先清掉第一次的残留，磁盘实况才会
    跟返回值一致。Task 8 的消费方按 glob 扫 overlays/*.toml 施加，一份调用方
    以为已经不存在的旧层会被悄悄套用到跟它毫不相干的下一次构建上。
    """
    generate("card", out_dir, card=103)
    assert (out_dir / "overlays" / "card-short-circuit.toml").exists()

    r2 = generate("mainmenu", out_dir)
    assert r2["overlays"] == []

    on_disk = sorted(p.relative_to(out_dir).as_posix()
                     for p in out_dir.rglob("*") if p.is_file())
    assert on_disk == sorted(r2["scripts"] + r2["overlays"])


def test_unknown_mode_is_hard_failure(out_dir):
    with pytest.raises(SystemExit):
        generate("frobnicate", out_dir)


def test_generate_refuses_output_dir_outside_build(tmp_path):
    """守卫本体（2026-09-03 carried-forward item 3）：out_dir 不在仓库 build/
    之下就必须硬拒绝，不能走到"先清空再写"那一步——layers/scripts、
    layers/overlays 与本工具的产物目录同构同名，传错一次会静默删掉手写入库的
    层文件。这里故意用一个不在 build/ 之下的 tmp_path（pytest 给的临时目录，
    与仓库 build/ 无关）来证明守卫真的拦得住，而不是"恰好从没传错过"。
    """
    with pytest.raises(SystemExit):
        generate("mainmenu", tmp_path)


def test_story_route_presets_card_scenes_in_story_order():
    """主菜单测试模式预置的记忆路线必须是**有卡的真场景 ID**（不带 scene_ 前缀）。

    data/dag.json 的 scene_meta 键是函数名 `scene_<id>`；直接按 `s1s_` 前缀筛会得到空路线，
    Story/Fragment 时间轴就是空的（2026-09-07 实测：Fragment 报「没有可以制作梗概的故事」）。
    路线里若混进无卡场景（如 s1s_10），snr_story_main 会在 sceneId2aCard 上取到 nil 而报错。
    """
    import re
    from tools.testboot import REPO, story_route
    ids = [s.strip('"') for s in story_route(16).split(", ")]
    assert len(ids) == 16
    assert all(not i.startswith("scene_") for i in ids)
    txt = (REPO / "lua_scripts" / "snr_common.lua").read_text(encoding="utf-8")
    carded = set(re.findall(r"sceneId2aCard\.(\w+) = \d+", txt))
    assert all(i in carded for i in ids), [i for i in ids if i not in carded]
    assert ids[0] == "s1s_20"


def test_movie_mode_can_play_ed_skippably(out_dir):
    generate("movie", out_dir, movie="ed", skippable=True)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'playMovie("movie/ed.mp4", true)' in src


def test_movie_mode_defaults_to_op_like_the_real_call(out_dir):
    generate("movie", out_dir)                    # snr_crd_2 的真调用：playMovie("movie/op.mp4", false)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'playMovie("movie/op.mp4", false)' in src


def test_movie_mode_rejects_unknown_movie(out_dir):
    with pytest.raises(SystemExit, match="op/ed"):
        generate("movie", out_dir, movie="xx")
