from tools.gen_plan import render, main
from tools.pipelib import write_jsonl

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

def test_render_glossary_v_is_a_parameter_not_the_module_constant():
    """render() 保持纯函数：glossary_v 由调用方传入，不同调用可得不同值——
    证明它不是从模块常量 GLOSSARY_V 读死的。"""
    md6 = render(BATCHES, chapter="s1s", lane="main", every=3, glossary_v=6)
    md9 = render(BATCHES, chapter="s1s", lane="main", every=3, glossary_v=9)
    assert "--glossary-v 6" in md6 and "--glossary-v 9" not in md6
    assert "--glossary-v 9" in md9 and "--glossary-v 6" not in md9

def test_main_uses_dynamically_derived_glossary_version(tmp_path, monkeypatch):
    """Minor：main() 必须用 build_context.glossary_version() 动态推导的版本号，
    不能是硬编码的 GLOSSARY_V 常量——否则计划文本里的 --glossary-v 会与
    glossary/ 目录实际最高版本不同步，操作者会把这个盖进 append-only 的
    forward 行。去掉 main() 里对 glossary_version() 的调用（改回裸
    GLOSSARY_V）本测试必红。"""
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
