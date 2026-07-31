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
    checkpoint = _find(_sections(md), "CHECKPOINT")
    assert "s1s.md" in checkpoint
