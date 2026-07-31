from tools.gen_plan import render

BATCHES = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
            "chapter": "s1s", "cut_reason": "budget"} for i in range(1, 8)]

def test_render_contains_tasks_and_checkpoints():
    md = render(BATCHES, chapter="s1s", lane="main", every=3)
    assert md.count("### Task") >= 7 + 2          # 7 批任务+至少 2 检查点
    assert "build_context.py --batch 1" in md
    assert "check_batch.py --batch 1" in md
    assert "append_forward.py --batch 1" in md
    assert "梗概回译自检" in md and "CHECKPOINT" in md

def test_only_selected_chapter_and_lane():
    extra = BATCHES + [{"batch": 99, "lane": "ambient", "ids": [99], "jp_chars": 1,
                        "chapter": "sys", "cut_reason": "tail"}]
    md = render(extra, chapter="s1s", lane="main", every=5)
    assert "--batch 99" not in md
