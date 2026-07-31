import pytest
from tools.gen_plan import render, select, main
from tools.pipelib import write_jsonl

BATCHES = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
            "chapter": "s1s", "cut_reason": "budget"} for i in range(1, 8)]

def _sel(chapter="s1s", lane="main", rng=None):
    return select(BATCHES, lane=lane, chapter=chapter, batch_range=rng)

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

def test_no_lane_cfg_output_is_byte_identical_to_repo_mode():
    """回归闸：不给 lane_cfg 时输出必须与车道感知改造前逐字一致。"""
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
