import json
from pathlib import Path
import pytest
from tools.build_context import build

def _env(tmp_path):
    d = tmp_path
    (d / "data").mkdir(); (d / "glossary").mkdir(); (d / "skeleton").mkdir()
    (d / "skeleton" / "cards.zh.yaml").write_text(
        "- {card: 1, variant: a, title_zh: 测试卡, body_zh: 骨架正文, tr_note: ''}\n",
        encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{"あ":"啊"}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    rows = [
        {"id": 1, "jp": "第一句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
        {"id": 2, "jp": "第二句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
    ]
    (d / "data" / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (d / "data" / "timeline.jsonl").write_text(json.dumps(
        {"type": "unit", "unit_kind": "scene", "src": "f", "state": "a_10",
         "title": "一", "ids": [1, 2]}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [1, 2], "jp_chars": 6,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "已译一", "batch": 0, "backend": "cc", "model": "m",
                    "ctx": "c", "glossary_v": 4, "ts": "t"}, ensure_ascii=False),
        encoding="utf-8")
    return d

def test_ctx_files_and_manifest(tmp_path):
    d = _env(tmp_path)
    build(batch=1, profile="cc", baseline="none", repo=d)
    ctx = d / "work" / "ctx" / "batch_1"
    assert (ctx / "context.md").exists() and (ctx / "manifest.json").exists()
    src = [json.loads(l) for l in (ctx / "source.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in src] == [1, 2] and "base" not in src[0]

def test_baseline_only_touches_tail(tmp_path):
    d = _env(tmp_path)
    build(batch=1, profile="cc", baseline="none", repo=d)
    a = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    build(batch=1, profile="cc", baseline="revise", repo=d)
    b = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    cut = "## 五、本批任务"
    assert a.split(cut)[0] == b.split(cut)[0]
    src = [json.loads(l) for l in (d / "work/ctx/batch_1/source.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert src[0]["base"] == "已译一"

def test_untranslated_prefix_requires_fallback(tmp_path):
    d = _env(tmp_path)
    # 批次 2：把行 2 当作后续批，行 1 未译时前缀应报错
    (d / "data" / "forward.jsonl").write_text("", encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text("\n".join([
        json.dumps({"batch": 1, "lane": "main", "ids": [1], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "budget"}, ensure_ascii=False),
        json.dumps({"batch": 2, "lane": "main", "ids": [2], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False)]),
        encoding="utf-8")
    assert build(batch=2, profile="api-A", baseline="none", repo=d) == 2
    assert build(batch=2, profile="api-A", baseline="none", repo=d, jp_fallback=True) == 0

def test_extra_lane_produces_readable_source(tmp_path):
    """extra 车道（ids 为 ledger_extra 的 str key）必须产出可逐行 json.loads 的
    source.jsonl，id/jp 取自 ledger_extra，且不带 base（resolve_map 只按 int id 建）。"""
    d = _env(tmp_path)
    (d / "data" / "ledger_extra.jsonl").write_text("\n".join([
        json.dumps({"key": "snr_x:1", "jp": "标题一", "kind": "scene_title", "file": "snr_x"},
                    ensure_ascii=False),
        json.dumps({"key": "snr_x:2", "jp": "标题二", "kind": "scene_title", "file": "snr_x"},
                    ensure_ascii=False),
    ]), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "extra", "ids": ["snr_x:1", "snr_x:2"], "jp_chars": 4,
         "chapter": "snr_x", "cut_reason": "extra"}, ensure_ascii=False), encoding="utf-8")
    assert build(batch=1, profile="cc", baseline="revise", repo=d) == 0
    lines = (d / "work/ctx/batch_1/source.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(l) for l in lines]      # 逐行必须能 json.loads，不许崩
    assert rows == [{"id": "snr_x:1", "jp": "标题一"}, {"id": "snr_x:2", "jp": "标题二"}]
    assert "base" not in rows[0] and "base" not in rows[1]

def test_zero_row_batch_yields_empty_source(tmp_path):
    """0 行批次的 source.jsonl 应为空串，.splitlines() 得 []，而不是 "\\n" → ['']。"""
    d = _env(tmp_path)
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [], "jp_chars": 0,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    assert build(batch=1, profile="cc", baseline="none", repo=d) == 0
    text = (d / "work/ctx/batch_1/source.jsonl").read_text(encoding="utf-8")
    assert text == "" and text.splitlines() == []

def test_unknown_id_raises_with_context(tmp_path):
    """ledger 与 ledger_extra 都查不到的 id 必须报错（带批号与该 id），不许静默丢行。"""
    d = _env(tmp_path)
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 7, "lane": "main", "ids": [999], "jp_chars": 3,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        build(batch=7, profile="cc", baseline="none", repo=d)
    msg = str(exc_info.value)
    assert "7" in msg and "999" in msg

def test_apiB_and_cc_skip_other_chapter_prefix(tmp_path):
    """api-B/cc 应跳过前缀里非当前章的行（已完结章走骨架里的章梗概卡），
    api-A 则保留全部已译前缀（含跨章）。"""
    d = _env(tmp_path)
    rows = [
        {"id": 1, "jp": "第一句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
        {"id": 2, "jp": "章b第一句", "chapter": "b", "kind": "narrative", "file": "f2", "func": "g2"},
    ]
    (d / "data" / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text("\n".join([
        json.dumps({"batch": 1, "lane": "main", "ids": [1], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "chapter"}, ensure_ascii=False),
        json.dumps({"batch": 2, "lane": "main", "ids": [2], "jp_chars": 5,
                    "chapter": "b", "cut_reason": "tail"}, ensure_ascii=False)]),
        encoding="utf-8")
    # _env 默认 forward.jsonl 已含 id=1 → "已译一"，批次 2 的前缀会引用批次 1（章 a）
    assert build(batch=2, profile="api-A", baseline="none", repo=d) == 0
    ctx_a = (d / "work/ctx/batch_2/context.md").read_text(encoding="utf-8")
    assert build(batch=2, profile="api-B", baseline="none", repo=d) == 0
    ctx_b = (d / "work/ctx/batch_2/context.md").read_text(encoding="utf-8")
    assert "已译一" in ctx_a
    assert "已译一" not in ctx_b
