import json
from pathlib import Path
import pytest
from tools.build_context import build, glossary_version

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

def _multi_unit_env(tmp_path):
    """Important 2 判别性用例的夹具：4 个 narrative id，timeline 里 3 个已译 unit
    （甲/乙/丙）与其间的 2 个 marker，第 4 个 unit（丁）与其后 marker 属于"当前批"
    自身/未来内容，不应泄漏进任何前缀。4 个各含 1 id 的 main 批次，批次 4 为待
    构建批（其余 3 批皆是它的 prior）。profile 用 api-A，规避章别过滤，专注测
    marker/title 的结构渲染本身。"""
    d = tmp_path
    (d / "data").mkdir(); (d / "glossary").mkdir(); (d / "skeleton").mkdir()
    (d / "skeleton" / "cards.zh.yaml").write_text(
        "- {card: 1, variant: a, title_zh: 测试卡, body_zh: 骨架正文, tr_note: ''}\n",
        encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    ledger_rows = [
        {"id": 1, "jp": "甲句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g1"},
        {"id": 2, "jp": "乙句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g2"},
        {"id": 3, "jp": "丙句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g3"},
        {"id": 4, "jp": "本批句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g4"},
    ]
    (d / "data" / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in ledger_rows), encoding="utf-8")
    timeline_rows = [
        {"seq": 0, "type": "marker", "text": "标记零", "recap": "回溯零"},   # 无 unit 在前，应被抑制
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "f", "state": "st1",
         "title": "标题甲", "ids": [1]},
        {"seq": 2, "type": "marker", "text": "标记一", "recap": "回溯一"},
        {"seq": 3, "type": "unit", "unit_kind": "scene", "src": "f", "state": "st2",
         "title": "标题乙", "ids": [2]},
        {"seq": 4, "type": "marker", "text": "标记二", "recap": "回溯二"},
        {"seq": 5, "type": "unit", "unit_kind": "scene", "src": "f", "state": "st3",
         "title": "标题丙", "ids": [3]},
        {"seq": 6, "type": "marker", "text": "标记三", "recap": "回溯三"},   # 不属于 prior 范围
        {"seq": 7, "type": "unit", "unit_kind": "scene", "src": "f", "state": "st4",
         "title": "标题丁（当前批，不应出现）", "ids": [4]},
    ]
    (d / "data" / "timeline.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in timeline_rows), encoding="utf-8")
    batches_rows = [
        {"batch": 1, "lane": "main", "ids": [1], "jp_chars": 2, "chapter": "a", "cut_reason": "x"},
        {"batch": 2, "lane": "main", "ids": [2], "jp_chars": 2, "chapter": "a", "cut_reason": "x"},
        {"batch": 3, "lane": "main", "ids": [3], "jp_chars": 2, "chapter": "a", "cut_reason": "x"},
        {"batch": 4, "lane": "main", "ids": [4], "jp_chars": 3, "chapter": "a", "cut_reason": "tail"},
    ]
    (d / "data" / "batches.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in batches_rows), encoding="utf-8")
    forward_rows = [
        {"id": 1, "zh": "译文甲", "batch": 0, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 4, "ts": "t"},
        {"id": 2, "zh": "译文乙", "batch": 0, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 4, "ts": "t"},
        {"id": 3, "zh": "译文丙", "batch": 0, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 4, "ts": "t"},
    ]
    (d / "data" / "forward.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in forward_rows), encoding="utf-8")
    return d

def _prefix_of(ctx_text):
    return ctx_text.split("## 二、前缀正文", 1)[1].split("## 三、锚点行", 1)[0]

def test_prefix_renders_timeline_markers_and_titles_in_order(tmp_path):
    """Important 2 判别性用例：timeline 的 marker text/recap 与各 unit 的 title
    必须在前缀里按 timeline 顺序出现；不属于本次前缀的内容（当前批自身、其后的
    marker、以及最前面「没有任何 unit 在其之前」的 marker）不得泄漏——最后一条
    是实测批次 70（cc profile）驱动的设计取舍：不加"至少已渲染过一个 unit"这道
    门槛，被章别过滤掉的更早章节会在前缀最前面堆出一堵几十行、前后都没有正文的
    marker 墙（详见 _render_prefix 注释）。去掉 _render_prefix 的结构渲染代码，
    本测试必红。"""
    d = _multi_unit_env(tmp_path)
    assert build(batch=4, profile="api-A", baseline="none", repo=d) == 0
    ctx = (d / "work/ctx/batch_4/context.md").read_text(encoding="utf-8")
    prefix = _prefix_of(ctx)
    ordered = ("标题甲", "标记一", "回溯一", "标题乙", "标记二", "回溯二", "标题丙")
    for s in ordered:
        assert s in prefix, f"缺失 {s!r}"
    positions = [prefix.index(s) for s in ordered]
    assert positions == sorted(positions), "前缀内容顺序应与 timeline 一致"
    assert "译文甲" in prefix and "译文乙" in prefix and "译文丙" in prefix
    # 当前批（4）自身内容、其后的 marker（标记三/回溯三）、以及最前面无 unit
    # 在前的 marker（标记零/回溯零）都不应泄漏进前缀
    assert "标题丁" not in prefix
    assert "标记三" not in prefix and "回溯三" not in prefix
    assert "标记零" not in prefix and "回溯零" not in prefix

def test_glossary_version_picks_max(tmp_path):
    g = tmp_path / "glossary"; g.mkdir()
    (g / "glossary.v1.yaml").write_text("{}", encoding="utf-8")
    (g / "glossary.v6.yaml").write_text("{}", encoding="utf-8")
    (g / "glossary.v3.yaml").write_text("{}", encoding="utf-8")
    assert glossary_version(tmp_path) == 6

def test_glossary_version_zero_when_absent(tmp_path):
    (tmp_path / "glossary").mkdir()
    assert glossary_version(tmp_path) == 0

def test_skeleton_heading_matches_other_sections_level(tmp_path):
    """Minor：五节标题层级应统一为 ##（一节此前是裸 #，与二~五节的 ## 不自洽）。
    回退 _render_skeleton 的「## 一、」为「# 一、」，本测试必红。"""
    d = _env(tmp_path)
    assert build(batch=1, profile="cc", baseline="none", repo=d) == 0
    ctx = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    assert "\n## 一、冻结骨架" in ctx
    assert "\n# 一、冻结骨架" not in ctx

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
    # Important 2 钉死的不变量：marker/标题都在前缀里、与 baseline 无关，上面这条
    # 比较在 batch=1（无 prior）时前缀天然是空的，不足以证明——换一个 prior 里真有
    # marker/多 unit 的批次（4），baseline none/revise 的前缀（SECTION5 之前）必须
    # 逐字节相同。
    d2 = tmp_path / "multi"
    d2.mkdir()
    _multi_unit_env(d2)
    build(batch=4, profile="api-A", baseline="none", repo=d2)
    a2 = (d2 / "work/ctx/batch_4/context.md").read_text(encoding="utf-8")
    build(batch=4, profile="api-A", baseline="revise", repo=d2)
    b2 = (d2 / "work/ctx/batch_4/context.md").read_text(encoding="utf-8")
    assert a2.split(cut)[0] == b2.split(cut)[0]
    assert "标记一" in _prefix_of(a2)          # 确认比较的不是两段空前缀

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
