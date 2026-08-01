import pytest
from tools.gen_plan import render, select, main
from tools.pipelib import write_jsonl

BATCHES = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
            "chapter": "s1s", "cut_reason": "budget"} for i in range(1, 8)]

def _sel(chapter="s1s", lane="main", rng=None):
    return select(BATCHES, lane=lane, chapter=chapter, batch_range=rng)

def _sections(md):
    """按 '### Task' 边界切分成任务段（不含 header），每段含标题行——用于精确
    断言某个具体任务段落里是否出现某模式，不被 header（比如 Architecture 段
    落里提到的「CHECKPOINT」一词）或其它任务段误伤。"""
    chunks = md.split("\n\n### Task ")[1:]
    return [f"### Task {c}" for c in chunks]

def _find(sections, marker):
    return next(s for s in sections if marker in s)

def test_render_contains_tasks_and_checkpoints():
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert md.count("### Task") >= 7 + 2
    assert "build_context.py --batch 1" in md
    assert "check_batch.py --batch 1" in md
    assert "append_forward.py --batch 1" in md
    assert "梗概回译自检" in md and "CHECKPOINT" in md

def test_only_selected_chapter_and_lane():
    extra = BATCHES + [{"batch": 99, "lane": "ambient", "ids": [99], "jp_chars": 1,
                        "chapter": "sys", "cut_reason": "tail"}]
    md = render(select(extra, lane="main", chapter="s1s"), label="s1s", lane="main", every=5)
    assert "--batch 99" not in md

def test_render_glossary_v_is_a_parameter_not_the_module_constant():
    md6 = render(_sel(), label="s1s", lane="main", every=3, glossary_v=6)
    md9 = render(_sel(), label="s1s", lane="main", every=3, glossary_v=9)
    assert "--glossary-v 6" in md6 and "--glossary-v 9" not in md6
    assert "--glossary-v 9" in md9 and "--glossary-v 6" not in md9

def test_main_uses_dynamically_derived_glossary_version(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v9.yaml").write_text("{}", encoding="utf-8")
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    assert main(["--lane", "main", "--chapter", "s1s"]) == 0
    out = (tmp_path / "docs" / "superpowers" / "plans" / "translate-s1s.md").read_text(
        encoding="utf-8")
    assert "--glossary-v 9" in out
    assert "--glossary-v 6" not in out

# ---- 新增：连续段模式 ----

def test_select_batch_range_is_inclusive_and_sorted():
    sel = select(BATCHES, lane="main", batch_range=(2, 5))
    assert [b["batch"] for b in sel] == [2, 3, 4, 5]

def test_select_range_ignores_chapter_boundaries():
    mixed = BATCHES + [{"batch": 8, "lane": "main", "ids": [8], "jp_chars": 9,
                        "chapter": "crd", "cut_reason": "chapter"}]
    sel = select(mixed, lane="main", batch_range=(7, 8))
    assert [b["chapter"] for b in sel] == ["s1s", "crd"], "连续段必须跨章别取批"

# ---- 新增：车道感知 ----

LANE_CFG = {"lane": "opus", "lane_dir": "work/lanes/opus", "model": "opus",
            "effort": "max", "append_model_id": "claude-opus-5"}

def test_lane_cfg_rewrites_every_path_to_lane_root():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "--repo work/lanes/opus" in md
    assert "ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data" in md
    assert "work/lanes/opus/work/out/batch_1.draft.jsonl" in md
    assert "work/lanes/opus/data/forward.jsonl" in md
    # 不得残留仓库相对的产物路径
    assert "`work/ctx/batch_1/" not in md
    assert "git add data/forward.jsonl" not in md


def test_lane_cfg_env_prefix_is_present_on_every_step_that_needs_it():
    """I2 回归：终审突变实证——删掉 append_forward 那行的 `{p["env"]}` 后，
    旧版全文断言（只查 "ZND_WORK=… ZND_DATA=…" 出现过一次）20/20 仍全绿，
    因为 Step 3（check_batch）已经提供了那一次命中。若该突变为真，两条车道
    的 append_forward 都会写进仓库根 data/forward.jsonl，A/B 合并成一锅、
    试点作废——必须按 Step 粒度分别断言整条命令行，不能只查全文出现次数。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    env = "ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data "
    assert f'{env}uv run python tools/check_batch.py --batch 1' in md
    assert f'{env}uv run python tools/append_forward.py --batch 1 ' in md

def test_lane_cfg_emits_config_block_with_model_and_effort():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "claude-opus-5" in md
    assert "effort" in md and "max" in md
    assert "Workflow" in md, "必须写明只能走 Workflow 派发（Agent 工具设不了 effort）"
    assert "work/lanes/" in md and "隔离" in md, "必须写明隔离纪律"

def test_no_lane_cfg_keeps_repo_relative_paths():
    """回归闸：不给 lane_cfg 时，全部产出路径必须保持仓库相对形态（work/ctx、
    data/forward.jsonl 等），不出现 --repo/ZND_WORK 等车道专属前缀。"""
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert "work/ctx/batch_1/" in md
    assert "git add data/forward.jsonl" in md
    assert "--repo" not in md and "ZND_WORK" not in md

def test_main_batches_mode_writes_labelled_plan(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v6.yaml").write_text("{}", encoding="utf-8")
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    rc = main(["--lane", "main", "--batches", "2-5", "--label", "pilot-opus",
               "--lane-dir", "work/lanes/opus", "--model", "opus",
               "--effort", "max", "--append-model-id", "claude-opus-5"])
    assert rc == 0
    out = (tmp_path / "docs" / "superpowers" / "plans" /
           "translate-pilot-opus.md").read_text(encoding="utf-8")
    assert "--batch 2" in out and "--batch 5" in out
    assert "--batch 1" not in out and "--batch 6" not in out
    assert "--repo work/lanes/opus" in out

def test_main_batches_mode_requires_label(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    with pytest.raises(SystemExit):
        main(["--lane", "main", "--batches", "2-5"])

def test_main_lane_params_are_all_or_nothing(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    with pytest.raises(SystemExit):
        main(["--lane", "main", "--batches", "2-5", "--label", "x",
              "--lane-dir", "work/lanes/opus"])   # 缺 model/effort/append-model-id

# ---- Fix round 1：跨章别连续段的文案错位 + 车道路径判别力缺口 ----

def test_lane_cfg_checkpoint_and_final_sections_have_no_repo_relative_paths():
    """真正有判别力的车道残留检查：单独切出 CHECKPOINT 段与终任务段分别断言，
    不像 test_lane_cfg_rewrites_every_path_to_lane_root 那样只查了 batch_1 任务
    段——如果 _checkpoint_task/_final_task 里有路径漏改回 p[...]，这里必须转红。
    _lane_block 里「禁止读取仓库根 `data/forward.jsonl`」那句是头部车道配置块的
    内容，不落在这两个任务段里，不会被误伤。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    sections = _sections(md)
    checkpoint = _find(sections, "CHECKPOINT")
    final = _find(sections, "梗概回译自检")
    for name, sec in (("CHECKPOINT", checkpoint), ("终任务", final)):
        for bad in ("`work/ctx", "`work/out", "`data/notes/", "`data/forward.jsonl"):
            assert bad not in sec, f"{name} 段落残留仓库相对路径 {bad!r}：\n{sec}"

def test_checkpoint_lists_every_real_chapter_in_the_chunk():
    """跨章别连续段：CHECKPOINT 文案必须列出 chunk 内全部真实章别对应的笔记
    文件，不能再用一个连续段模式下往往不存在的 label 拼笔记路径。"""
    mixed = [
        {"batch": 1, "lane": "main", "ids": [1], "jp_chars": 10, "chapter": "s0f", "cut_reason": "b"},
        {"batch": 2, "lane": "main", "ids": [2], "jp_chars": 10, "chapter": "crd", "cut_reason": "b"},
        {"batch": 3, "lane": "main", "ids": [3], "jp_chars": 10, "chapter": "s1s", "cut_reason": "b"},
        {"batch": 4, "lane": "main", "ids": [4], "jp_chars": 10, "chapter": "sys", "cut_reason": "b"},
    ]
    sel = select(mixed, lane="main", batch_range=(1, 4))
    md = render(sel, label="mix", lane="main", every=4)
    checkpoint = _find(_sections(md), "CHECKPOINT")
    assert "crd.md" in checkpoint and "s0f.md" in checkpoint
    assert "s1s.md" in checkpoint and "sys.md" in checkpoint
    assert "mix.md" not in checkpoint, "不能落回用 label 拼一个不存在的笔记文件"

def test_final_task_no_longer_filters_git_log_by_label():
    """--batches 模式下 label 不是任何批次的真实章别，git log 用它过滤永远匹配
    不到东西——章末任务改用批号区间描述待复核 commit，不再提「过滤」这个词。"""
    md = render(_sel(), label="distinctive-plan-label", lane="main", every=3)
    final = _find(_sections(md), "梗概回译自检")
    assert "过滤" not in final
    assert "批号 1–7" in final

def test_checkpoint_and_final_stay_natural_in_single_chapter_mode():
    """非车道模式 + --chapter 模式：chunk 内真实章别集合退化为单元素时，
    CHECKPOINT 文案要和改造前一样自然可读（不因为新支持多章别而变得啰嗦）。"""
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert "到这里已完成 s1s 章批次 1–3 的翻译入库" in md
    assert "s1s 章 main 车道全部 7 个批次（1–7）已入库" in md
    sections = _sections(md)
    checkpoint = _find(sections, "CHECKPOINT")
    assert "s1s.md" in checkpoint
    # Hotfix D 缺陷 1：单章模式下 Step 1 文案仍用「本章」表述，不引入连续段
    # 才需要的「本段」/「timeline 连续段」措辞。
    final = _find(sections, "梗概回译自检")
    assert "对照本章对应的章节梗概卡" in final
    assert "timeline 连续段" not in final


# ---- Hotfix D 缺陷 1：`_final_task` 不再把 label 当章别用 ----

MIXED_CHAPTERS = [
    {"batch": 1, "lane": "main", "ids": [1], "jp_chars": 10, "chapter": "s0f", "cut_reason": "b"},
    {"batch": 2, "lane": "main", "ids": [2], "jp_chars": 10, "chapter": "crd", "cut_reason": "b"},
    {"batch": 3, "lane": "main", "ids": [3], "jp_chars": 10, "chapter": "s1s", "cut_reason": "b"},
    {"batch": 4, "lane": "main", "ids": [4], "jp_chars": 10, "chapter": "sys", "cut_reason": "b"},
]


def test_final_task_lists_real_chapters_not_label():
    """跨章别连续段：终任务 Step 1 文案必须列出全部真实章别，不能把
    --batches 模式下的 label（计划名，不是任何批次的真实章别）当章别读。"""
    sel = select(MIXED_CHAPTERS, lane="main", batch_range=(1, 4))
    md = render(sel, label="pilot-opus", lane="main", every=10)
    final = _find(_sections(md), "梗概回译自检")
    for ch in ("s0f", "crd", "s1s", "sys"):
        assert ch in final, f"终任务文案漏了真实章别 {ch}：\n{final}"
    assert "pilot-opus" not in final, "终任务文案不能把 label 当章别读"


def test_final_task_flags_partial_chapter_coverage_in_cross_chapter_mode():
    """跨章别连续段必须明确提示「本段可能只覆盖某章的一部分」，避免执行者
    误把未完结的章当成整章已完结来核对梗概卡。"""
    sel = select(MIXED_CHAPTERS, lane="main", batch_range=(1, 4))
    md = render(sel, label="pilot-opus", lane="main", every=10)
    final = _find(_sections(md), "梗概回译自检")
    assert "timeline 连续段" in final
    assert "整章完结" in final


# ---- Hotfix D 缺陷 2：check_batch 的 --lane-dir 车道化 ----

def test_lane_cfg_check_batch_step_includes_lane_dir():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "check_batch.py --batch 1 --lane-dir work/lanes/opus" in md


def test_no_lane_cfg_check_batch_step_has_no_lane_dir():
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert "check_batch.py --batch 1" in md
    assert "check_batch.py --batch 1 --lane-dir" not in md


# ---- 终审 C1：四道验收闸门在计划里零出现 ----

BATCHES_35 = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
              "chapter": ("s0f" if i <= 2 else "crd" if i <= 14 else "s1s"
                          if i <= 28 else "sys" if i <= 30 else "s1f"
                          if i <= 33 else "s2s"),
              "cut_reason": "budget"} for i in range(1, 36)]

LANE_CFG_NO_SIBLING = LANE_CFG  # 别名保留：对方车道路径恒为占位符，不存在
                                # "含 sibling"的 lane_cfg 变体，两个名字等价


def test_non_lane_mode_gate_markers_are_completely_absent():
    """回归闸：C1 明确要求「车道模式下生效；非车道模式输出保持不变」——四道
    闸门相关的全部新增文案在非车道模式下一处都不能出现，且任务总数不变。"""
    md = render(_sel(), label="s1s", lane="main", every=3)
    for marker in ("detect_collapse", "隔离验收", "硬停", "lane_setup",
                   "--verify", "窗口对撞"):
        assert marker not in md, f"非车道模式不该出现 {marker!r}"
    assert md.count("### Task") == 10, "7 个批次任务 + 2 个周期 CHECKPOINT + 1 个终任务"


def test_lane_mode_batch_task_has_collapse_probe_step_between_check_and_append():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    sections = _sections(md)
    t1 = _find(sections, "批次 1 译文入库")
    assert "tools/detect_collapse.py --batch 1 --lane-dir work/lanes/opus" in t1
    assert "顾问级" in t1 and "不阻断" in t1
    i_check = t1.index("check_batch.py --batch 1")
    i_collapse = t1.index("detect_collapse.py --batch 1")
    i_append = t1.index("append_forward.py --batch 1")
    assert i_check < i_collapse < i_append, "崩溃探测须插在 check_batch 与 append_forward 之间"


def test_lane_mode_checkpoint_starts_with_freeze_verify_gate():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    checkpoint = _find(_sections(md), "CHECKPOINT")
    assert "tools/lane_setup.py --verify" in checkpoint
    assert "冻结校验：无漂移" in checkpoint
    assert "停止试点" in checkpoint


def test_non_lane_mode_checkpoint_has_no_verify_gate():
    md = render(_sel(), label="s1s", lane="main", every=3)
    checkpoint = _find(_sections(md), "CHECKPOINT")
    assert "lane_setup.py --verify" not in checkpoint


def test_hardstop_tasks_after_batch_1_and_2_in_lane_mode():
    md = render(_sel(), label="pilot-opus", lane="main", every=10, lane_cfg=LANE_CFG)
    sections = _sections(md)
    hardstops = [s for s in sections if "硬停" in s.split("\n", 1)[0]]
    assert len(hardstops) == 2
    hs1, hs2 = hardstops
    assert "隔离验收" in hs1
    assert "forward.jsonl" in hs1 and "diff" in hs1
    assert "lane_setup.py --verify" in hs1
    assert "停止试点" in hs1
    assert "kana-max" in hs2 or "kana_max" in hs2
    assert "pilot-manifest.json" in hs2
    assert "崩溃探测" in hs2 or "collapse" in hs2
    assert "停止试点" in hs2
    # 硬停任务必须紧跟在 batch 1 / batch 2 各自的批次任务之后
    idx_b1 = sections.index(_find(sections, "批次 1 译文入库"))
    idx_b2 = sections.index(_find(sections, "批次 2 译文入库"))
    idx_hs1 = sections.index(hs1)
    idx_hs2 = sections.index(hs2)
    assert idx_hs1 == idx_b1 + 1
    assert idx_hs2 == idx_b2 + 1


def test_non_lane_mode_has_no_hardstop_tasks():
    md = render(_sel(), label="s1s", lane="main", every=3)
    sections = _sections(md)
    assert not [s for s in sections if "硬停" in s.split("\n", 1)[0]]


def test_segment_mode_with_lane_cfg_has_no_hardstop_tasks():
    """P3 段计划（segment 非 None）不该出现 P2 试点专属的两个硬停任务——
    它们硬编码假设计划恒从全局 batch 1 开始，段计划通常从段起始批（比如
    SEG-1 的 36）开始，硬编码的 --batch 2 / batch_1.collapse.json 等字面量
    在段模式下指向不相关批次，必然失败。段计划自己的门是段开场自检/段末
    流程（_segment_head/_segment_tail），不需要也不该叠加试点硬停。"""
    md = render(_sel(), label="seg1-s2", lane="main", every=10,
                lane_cfg=LANE_CFG, segment="seg1-s2")
    sections = _sections(md)
    assert not [s for s in sections if "硬停" in s.split("\n", 1)[0]]


def test_pilot_mode_lane_cfg_without_segment_still_has_hardstop_tasks():
    """回归闸：不传 segment（P2 试点模式）时，车道模式硬停任务必须原样保留——
    防止修复 P3 段模式时把硬停功能整个删掉。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=10,
                lane_cfg=LANE_CFG, segment=None)
    sections = _sections(md)
    hardstops = [s for s in sections if "硬停" in s.split("\n", 1)[0]]
    assert len(hardstops) == 2


def test_window_probe_task_present_when_batch_33_selected():
    sel = select(BATCHES_35, lane="main", batch_range=(1, 35))
    md = render(sel, label="pilot-opus", lane="main", every=5, lane_cfg=LANE_CFG)
    sections = _sections(md)
    probe = [s for s in sections if "窗口对撞" in s.split("\n", 1)[0]]
    assert len(probe) == 1
    p = probe[0]
    assert "batch 33" in p or "33" in p
    assert "--profile api-A" in p and "--profile cc" in p
    assert "cp -r" in p, "必须用临时车道副本，不得覆盖正式产物（I6）"
    assert "rm -rf" in p, "用完须清理临时副本"
    # 必须在 batch 35 任务之后、终任务之前
    idx_b35 = sections.index(_find(sections, "批次 35 译文入库"))
    idx_probe = sections.index(p)
    idx_final = sections.index(_find(sections, "梗概回译自检"))
    assert idx_b35 < idx_probe < idx_final


def test_window_probe_task_absent_when_batch_33_not_in_range():
    sel = select(BATCHES_35, lane="main", batch_range=(1, 10))
    md = render(sel, label="pilot-opus", lane="main", every=5, lane_cfg=LANE_CFG)
    assert "窗口对撞" not in md


def test_window_probe_task_absent_in_non_lane_mode_even_with_batch_33():
    sel = select(BATCHES_35, lane="main", batch_range=(1, 35))
    md = render(sel, label="pilot-opus", lane="main", every=5)
    assert "窗口对撞" not in md


def test_full_pilot_task_count_in_lane_mode():
    """35 批 + 7 个周期 CHECKPOINT（every=5：5/10/.../35）+ 2 个硬停
    （batch1 后、batch2 后）+ 1 个窗口对撞探针（batch 33 在段内）+ 1 个终任务
    = 46。此数字供终审自查引用。"""
    sel = select(BATCHES_35, lane="main", batch_range=(1, 35))
    md = render(sel, label="pilot-opus", lane="main", every=5, lane_cfg=LANE_CFG)
    assert md.count("### Task") == 46


# ---- I-extra：崩溃阈值标定值固化进命令行 ----

def test_collapse_thresholds_are_appended_to_detect_collapse_command():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG,
                collapse_thresholds={"kana_max": 0.05, "ratio_lo": 0.3, "ratio_hi": 1.8})
    assert ("detect_collapse.py --batch 1 --lane-dir work/lanes/opus "
            "--kana-max 0.05 --ratio-lo 0.3 --ratio-hi 1.8") in md


def test_collapse_thresholds_default_to_none_means_no_extra_flags():
    """未标定时批次任务的 detect_collapse 命令行不带任何阈值 flag（沿用工具
    自身默认值）。断言范围限定在批次任务段——batch 2 硬停任务的正文本就会
    以散文提到这三个 flag 名字（指导人工怎么标定），那不是本用例要钉的东西。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    t1 = _find(_sections(md), "批次 1 译文入库")
    assert "--kana-max" not in t1 and "--ratio-lo" not in t1 and "--ratio-hi" not in t1


def test_collapse_thresholds_partial_override_only_emits_given_keys():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG,
                collapse_thresholds={"kana_max": 0.05})
    t1 = _find(_sections(md), "批次 1 译文入库")
    assert "--kana-max 0.05" in t1
    assert "--ratio-lo" not in t1 and "--ratio-hi" not in t1


def test_main_accepts_threshold_cli_flags_and_forwards_to_plan(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v6.yaml").write_text("{}", encoding="utf-8")
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    rc = main(["--lane", "main", "--batches", "1-7", "--label", "pilot-opus",
               "--lane-dir", "work/lanes/opus", "--model", "opus",
               "--effort", "max", "--append-model-id", "claude-opus-5",
               "--kana-max", "0.05", "--ratio-lo", "0.3", "--ratio-hi", "1.8"])
    assert rc == 0
    out = (tmp_path / "docs" / "superpowers" / "plans" /
           "translate-pilot-opus.md").read_text(encoding="utf-8")
    assert "--kana-max 0.05 --ratio-lo 0.3 --ratio-hi 1.8" in out


# ---- 对方车道路径用占位符，不在生成期解析成具体路径 ----
#
# 早期实现尝试过在 main() 里自动扫盘发现对方车道目录、把具体路径（如
# "pilot/lanes/fable"）直接烤进 opus 计划文件——但这会让 translate-pilot-opus.md
# 里出现 "pilot/lanes/fable" 字样，违反终审自查清单里
# `grep -c 'pilot/lanes/fable' translate-pilot-opus.md` 必须为 0 这条硬性要求
# （两份计划各自只该谈自己的车道，不该在生成期就"知道"对方车道路径）。改为
# 占位符（与本文件其它地方的 `<model>`/`<ctx_sha>` 是同一约定），见下。


# ---- 顺手 minor：_header 的 label-as-chapter 表述 ----

def test_final_task_commit_step_reference_matches_actual_step_number():
    """同一处 Step-4-变-Step-5 的连带问题，也出现在终任务 Step 2 里"见各批
    Task 的 Step 4"这句——车道模式下入库提交是 Step 5。"""
    md_no_lane = render(_sel(), label="s1s", lane="main", every=3)
    final_no_lane = _find(_sections(md_no_lane), "梗概回译自检")
    assert "Step 4）交给人工复核" in final_no_lane
    md_lane = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    final_lane = _find(_sections(md_lane), "梗概回译自检")
    assert "Step 5）交给人工复核" in final_lane
    assert "Step 4）交给人工复核" not in final_lane


def test_header_git_step_reference_matches_actual_step_number():
    """终审自查发现的连带问题：Global Constraints 里"执行 git 操作（Step N）"
    是静态文案，车道模式下新插入的崩溃探测步把入库提交从 Step 4 挤到
    Step 5，若不跟着变就会指错步骤号。"""
    md_no_lane = render(_sel(), label="s1s", lane="main", every=3)
    assert "执行 git 操作（Step 4）" in md_no_lane
    md_lane = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "执行 git 操作（Step 5）" in md_lane
    assert "执行 git 操作（Step 4）" not in md_lane


def test_header_single_chapter_mode_keeps_original_wording():
    """--chapter 模式下 label 本就是真实章别，"label 章"是准确表述，不改。"""
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert md.startswith("# s1s 章（main 车道）翻译执行计划")
    assert "把 `data/batches.jsonl` 里 s1s 章（lane=main）的全部 7 个批次" in md


def test_header_cross_chapter_label_mode_does_not_say_label_is_a_chapter():
    """--batches 连续段模式下 label（如 pilot-opus）不是任何批次的真实章别——
    H1/Goal 不能再写"pilot-opus 章"，须改为不误导的措辞并列出真实章别、
    说明这是 timeline 连续段（终审分诊的顺手 minor）。"""
    mixed = [
        {"batch": 1, "lane": "main", "ids": [1], "jp_chars": 10, "chapter": "s0f", "cut_reason": "b"},
        {"batch": 2, "lane": "main", "ids": [2], "jp_chars": 10, "chapter": "crd", "cut_reason": "b"},
    ]
    sel = select(mixed, lane="main", batch_range=(1, 2))
    md = render(sel, label="pilot-opus", lane="main", every=10)
    assert "pilot-opus 章" not in md
    assert md.startswith("# pilot-opus（main 车道）翻译执行计划")
    header_block = md.split("\n\n---")[0]
    assert "timeline 连续段" in header_block
    assert "s0f" in header_block and "crd" in header_block


def test_hardstop_1_diff_command_uses_placeholder_not_a_resolved_sibling_path():
    """硬停 1 的隔离验收要 diff 对方车道的 forward.jsonl，但对方车道路径必须是
    占位符，不能在生成期就解析出具体路径写死进计划——否则 opus 计划文件里会
    出现 "fable" 字样，违反两份计划互不知晓对方车道路径的隔离精神（也是终审
    自查清单里跨车道 grep 必须为 0 的来由）。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=10,
               lane_cfg=LANE_CFG_NO_SIBLING)
    hs1 = next(s for s in _sections(md) if "硬停" in s.split("\n", 1)[0]
              and "隔离验收" in s)
    assert "diff" in hs1
    assert "<对方车道根" in hs1
    assert "fable" not in hs1.lower()


# ---- P3 Task 4：段模式 --segment ----

def test_render_segment_blocks_present():
    sel = _sel()
    md = render(sel, label="seg1-s2", lane="main", segment="seg1-s2")
    assert "## 段开场自检" in md
    assert "lane_setup.py --lane opus --verify" in md
    assert "## 段末流程" in md
    assert "prod-opus-seg1-s2-done" in md
    assert "tools/saturation.py" in md
    # 自检在正文批次任务之前、段末流程在其后
    assert md.index("## 段开场自检") < md.index("## 段末流程")


def test_render_without_segment_unchanged():
    sel = _sel()
    md = render(sel, label="x", lane="main")
    assert "段开场自检" not in md and "段末流程" not in md


# ---- 终审 C1：生产树/主仓的命令形态划分（--tools-root） ----

PROD = "/Users/fotile96/Zndnovel-prod"


def test_tools_root_prefixes_only_the_four_per_batch_tools():
    """按批四件套（build_context/check_batch/detect_collapse/append_forward）是
    「段内必须不变」的东西，Run 行须带生产树绝对路径；lane_setup/gen_plan/
    saturation/resolve 不参与段内冻结语义，必须保持主仓 `tools/` 形态——否则
    lane_setup 在生产树里因 `__file__` 推出的 LANES_ROOT 指向 gitignore 的空
    车道目录而必然 exit 1（终审 C1 实测）。"""
    md = render(_sel(), label="seg1-s2", lane="main", every=3, lane_cfg=LANE_CFG,
                segment="seg1-s2", tools_root=PROD)
    for tool in ("build_context", "check_batch", "detect_collapse", "append_forward"):
        assert f"{PROD}/tools/{tool}.py" in md, tool
        assert f"python tools/{tool}.py" not in md, f"{tool} 仍有主仓相对形态残留"
    for tool in ("lane_setup", "saturation", "gen_plan"):
        assert f"{PROD}/tools/{tool}.py" not in md, f"{tool} 不该指向生产树"
    assert "tools/lane_setup.py --lane opus --verify" in md


def test_tools_root_default_is_bare_tools_path():
    """回归闸：不传 --tools-root 时四件套 Run 行必须与改造前逐字相同。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    for tool in ("build_context", "check_batch", "detect_collapse", "append_forward"):
        assert f"uv run python tools/{tool}.py" in md, tool
    assert "Zndnovel-prod" not in md


def test_segment_head_pins_cwd_to_main_repo_and_names_the_prod_tree():
    md = render(_sel(), label="seg1-s2", lane="main", every=3, lane_cfg=LANE_CFG,
                segment="seg1-s2", tools_root=PROD)
    head = md.split("## 段开场自检")[1].split("### Task")[0]
    assert "主仓" in head and "cwd" in head
    assert PROD in head
    assert "本命令在主仓执行" in head
    # 旧措辞（"本会话执行的 tools/ 必须来自生产 worktree" + "主仓 main 上的工具
    # 不得用于生产批次"）与批次 Run 行的相对形态自相矛盾，必须消失。
    assert "主仓 main 上的工具**不得**用于生产批次" not in head


# ---- 终审 M6：段模式不得再用 P2 试点措辞 ----

# 段模式不生成 P2 试点专属的两个硬停任务，正文任何地方都不该再引用「硬停」
SEG_ONLY_FORBIDDEN = ("试点", "章末——", "硬停")


def test_segment_mode_drops_pilot_vocabulary():
    md = render(_sel(), label="seg1-s2", lane="main", every=3, lane_cfg=LANE_CFG,
                segment="seg1-s2", tools_root=PROD)
    for bad in SEG_ONLY_FORBIDDEN:
        assert bad not in md, f"段模式残留试点措辞 {bad!r}"
    assert "段末——梗概回译自检" in md
    assert "段末插一个人工评审 gate" in md
    checkpoint = _find(_sections(md), "CHECKPOINT")
    assert "停止本段" in checkpoint
    assert "段末小裁决" in checkpoint


def test_pilot_mode_keeps_pilot_vocabulary():
    """回归闸：非段模式（P2 试点那种计划）措辞一字不变。"""
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "试点期间提案只追加进" in md
    assert "裁决推迟到试点结束" in md
    assert "章末——梗概回译自检" in md
    assert "章末插一个人工评审 gate" in md
    assert "检查点/硬停任务汇总参考" in md
    checkpoint = _find(_sections(md), "CHECKPOINT")
    assert "立即停止试点" in checkpoint


# ---- 终审 I3：--segment 与 config/segments.yaml 的程序耦合 ----

SEGMENTS_YAML = """\
- seg: 1
  label: seg1-s2
  batches: [2, 5]
  chapters: [s1s]
  jp_chars: 400
  review_focus: "x"
- seg: 2
  label: seg2-s3
  batches: [6, 7]
  chapters: [s1s]
  jp_chars: 200
  review_focus: "y"
"""


def _repo_fixture(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "glossary" / "glossary.v7.yaml").write_text("{}", encoding="utf-8")
    (tmp_path / "config" / "segments.yaml").write_text(SEGMENTS_YAML, encoding="utf-8")
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    return tmp_path


def _plan(tmp_path, label):
    return (tmp_path / "docs" / "superpowers" / "plans" /
            f"translate-{label}.md").read_text(encoding="utf-8")


def test_main_segment_derives_batches_from_segments_yaml(tmp_path, monkeypatch):
    _repo_fixture(tmp_path, monkeypatch)
    assert main(["--lane", "main", "--segment", "seg1-s2"]) == 0
    out = _plan(tmp_path, "seg1-s2")
    assert "--batch 2" in out and "--batch 5" in out
    assert "--batch 1" not in out and "--batch 6" not in out


def test_main_segment_unknown_label_exits(tmp_path, monkeypatch):
    _repo_fixture(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        main(["--lane", "main", "--segment", "seg9-nope"])


def test_main_segment_batches_override_wins(tmp_path, monkeypatch):
    _repo_fixture(tmp_path, monkeypatch)
    assert main(["--lane", "main", "--segment", "seg1-s2",
                 "--batches", "6-7", "--label", "seg1-s2"]) == 0
    out = _plan(tmp_path, "seg1-s2")
    assert "--batch 6" in out and "--batch 7" in out
    assert "--batch 2" not in out


def test_main_segment_forwards_tools_root(tmp_path, monkeypatch):
    _repo_fixture(tmp_path, monkeypatch)
    assert main(["--lane", "main", "--segment", "seg1-s2",
                 "--lane-dir", "/abs/lanes/opus", "--model", "opus",
                 "--effort", "max", "--append-model-id", "claude-opus-5",
                 "--tools-root", PROD]) == 0
    out = _plan(tmp_path, "seg1-s2")
    assert f"{PROD}/tools/build_context.py" in out
    assert f"{PROD}/tools/append_forward.py" in out
    assert "tools/lane_setup.py --lane opus --verify" in out


def test_main_requires_one_of_chapter_batches_segment(tmp_path, monkeypatch):
    _repo_fixture(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        main(["--lane", "main"])
