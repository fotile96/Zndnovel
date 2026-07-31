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
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "f", "state": "a_10",
         "title": "一", "ids": [1, 2]}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [1, 2], "seqs": [1], "jp_chars": 6,
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
        {"batch": 1, "lane": "main", "ids": [1], "seqs": [1], "jp_chars": 2, "chapter": "a", "cut_reason": "x"},
        {"batch": 2, "lane": "main", "ids": [2], "seqs": [3], "jp_chars": 2, "chapter": "a", "cut_reason": "x"},
        {"batch": 3, "lane": "main", "ids": [3], "seqs": [5], "jp_chars": 2, "chapter": "a", "cut_reason": "x"},
        {"batch": 4, "lane": "main", "ids": [4], "seqs": [7], "jp_chars": 3, "chapter": "a", "cut_reason": "tail"},
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
        {"batch": 1, "lane": "extra", "ids": ["snr_x:1", "snr_x:2"], "seqs": [], "jp_chars": 4,
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
        {"batch": 1, "lane": "main", "ids": [], "seqs": [], "jp_chars": 0,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    assert build(batch=1, profile="cc", baseline="none", repo=d) == 0
    text = (d / "work/ctx/batch_1/source.jsonl").read_text(encoding="utf-8")
    assert text == "" and text.splitlines() == []

def test_unknown_id_raises_with_context(tmp_path):
    """ledger 与 ledger_extra 都查不到的 id 必须报错（带批号与该 id），不许静默丢行。"""
    d = _env(tmp_path)
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 7, "lane": "main", "ids": [999], "seqs": [], "jp_chars": 3,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        build(batch=7, profile="cc", baseline="none", repo=d)
    msg = str(exc_info.value)
    assert "7" in msg and "999" in msg

# ---------------------------------------------------------------------------
# Park 项 A：api-B/cc 前缀窗口（自「上一个章梗概卡」起，不再用 chapter 相等）
# 下面 4 个 _xxx_row 是纯样板构造器，供 4 条窗口判别性用例共用，避免每条用例
# 重复 _env() 那套四文件模板；chapter 字段仍写入（其他工具仍用它），但
# build_context 的窗口逻辑本身不再读它。
# ---------------------------------------------------------------------------

def _mk_env(tmp_path, ledger_rows, timeline_rows, batches_rows, forward_rows=(), extra_rows=()):
    d = tmp_path
    (d / "data").mkdir(); (d / "glossary").mkdir(); (d / "skeleton").mkdir()
    (d / "skeleton" / "cards.zh.yaml").write_text(
        "- {card: 1, variant: a, title_zh: 测试卡, body_zh: 骨架正文, tr_note: ''}\n",
        encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (d / "data" / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in ledger_rows), encoding="utf-8")
    (d / "data" / "timeline.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in timeline_rows), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in batches_rows), encoding="utf-8")
    (d / "data" / "forward.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in forward_rows), encoding="utf-8")
    if extra_rows:
        (d / "data" / "ledger_extra.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in extra_rows), encoding="utf-8")
    return d

def _ledger_row(id_, jp, chapter="x"):
    return {"id": id_, "jp": jp, "chapter": chapter, "kind": "narrative", "file": "f", "func": "g"}

def _unit_row(seq, ids, title, src="f"):
    return {"seq": seq, "type": "unit", "unit_kind": "scene", "src": src,
            "state": f"st{seq}", "title": title, "ids": ids}

def _batch_row(batch, ids, seqs, chapter="x", lane="main", cut_reason="x"):
    return {"batch": batch, "lane": lane, "ids": ids, "seqs": seqs,
            "jp_chars": 1, "chapter": chapter, "cut_reason": cut_reason}

def _fwd_row(id_, zh, v=4):
    return {"id": id_, "zh": zh, "batch": 0, "backend": "cc", "model": "m",
            "ctx": "c", "glossary_v": v, "ts": "t"}

def test_window_prefix_keeps_only_content_after_last_chapter_card(tmp_path):
    """Park 项 A 判别性用例 1+5（brief 测试列表第 1、5 条）：cc/api-B 的前缀窗口
    ＝自「本批第一个时间轴位置之前、最近一个章梗概卡单元（script 单元 src ∈
    CHAPTER_CARD_SRCS）」起；边界单元自身的正文（现实层框架剧情，不是骨架卡组
    承载的卡面梗概）仍在窗口内——真实数据核实 batch 81/173 的窗口行数分别为
    1073/1255，比"排除边界自身"的算法多 1，与"该 unit 恰好 1 个 id"吻合。

    本用例是旧 test_apiB_and_cc_skip_other_chapter_prefix（断言已废弃的
    chapter 相等语义）的改写：继续守住"api-B/cc 前缀比 api-A 短"这条性质，但
    边界改用窗口。id1/3/5/6 与目标批次 6 同 chapter="x"，crd 边界卡 id2/4 才是
    chapter="crd"——刻意让"旧 chapter 语义"与"新窗口语义"在这份夹具上给出不同
    答案（旧语义下 id1/3/5 因同 chapter 而入选、id2/4 因 chapter=crd 被排除，
    恰与新语义相反），使本用例对二者都有判别力：去掉窗口过滤（或整个改回旧
    chapter 比较），本测试必红。"""
    ledger_rows = [
        _ledger_row(1, "内容零"), _ledger_row(2, "边界一正文", "crd"),
        _ledger_row(3, "内容一"), _ledger_row(4, "边界二正文", "crd"),
        _ledger_row(5, "内容二"), _ledger_row(6, "本批内容"),
    ]
    timeline_rows = [
        _unit_row(1, [1], "标题零"),
        _unit_row(2, [2], "边界一", src="snr_crd_133"),
        _unit_row(3, [3], "标题一"),
        _unit_row(4, [4], "边界二", src="snr_crd_134"),
        _unit_row(5, [5], "标题二"),
        _unit_row(6, [6], "本批标题"),
    ]
    batches_rows = [
        _batch_row(1, [1], [1]), _batch_row(2, [2], [2], "crd"),
        _batch_row(3, [3], [3]), _batch_row(4, [4], [4], "crd"),
        _batch_row(5, [5], [5]),
        _batch_row(6, [6], [6], cut_reason="tail"),
    ]
    forward_rows = [_fwd_row(1, "译零"), _fwd_row(2, "译边界一"),
                     _fwd_row(3, "译一"), _fwd_row(4, "译边界二"),
                     _fwd_row(5, "译二")]
    d = _mk_env(tmp_path, ledger_rows, timeline_rows, batches_rows, forward_rows)
    assert build(batch=6, profile="cc", baseline="none", repo=d) == 0
    cc_prefix = _prefix_of((d / "work/ctx/batch_6/context.md").read_text(encoding="utf-8"))
    assert build(batch=6, profile="api-A", baseline="none", repo=d) == 0
    a_prefix = _prefix_of((d / "work/ctx/batch_6/context.md").read_text(encoding="utf-8"))
    # 窗口内（最后一个边界卡「边界二」及其后）：cc 应保留
    assert "译边界二" in cc_prefix and "译二" in cc_prefix
    # 窗口外（边界二之前，含边界一自身）：cc 下不得出现
    assert "译零" not in cc_prefix
    assert "译边界一" not in cc_prefix
    assert "译一" not in cc_prefix
    # api-A 不做窗口过滤，全部 5 段已译前序都在
    for s in ("译零", "译边界一", "译一", "译边界二", "译二"):
        assert s in a_prefix
    assert len(cc_prefix) < len(a_prefix)

def test_window_start_is_zero_when_no_chapter_card_precedes_batch(tmp_path):
    """Park 项 A 判别性用例 2（brief 测试列表第 2 条）：本批之前的 timeline 里
    一个章梗概卡单元都没有时，窗口起点为 0，即窗口＝全部前序——cc 与 api-A
    结果相同。id1（chapter=x）与批次 2（chapter=y）故意不同 chapter：旧的
    chapter 相等语义会把 id1 判为"非当前章"而排除，新窗口语义（无边界→0）则
    保留它——这份夹具因此同时验证了"起点为 0"且对旧语义有判别力：去掉这条
    分支（例如把"无边界"误当"无时间轴位置"处理成空窗口），本测试必红。"""
    ledger_rows = [_ledger_row(1, "内容甲", "x"), _ledger_row(2, "内容乙", "y")]
    timeline_rows = [_unit_row(1, [1], "标题甲"), _unit_row(2, [2], "标题乙")]
    batches_rows = [_batch_row(1, [1], [1], "x"),
                     _batch_row(2, [2], [2], "y", cut_reason="tail")]
    forward_rows = [_fwd_row(1, "译甲")]
    d = _mk_env(tmp_path, ledger_rows, timeline_rows, batches_rows, forward_rows)
    assert build(batch=2, profile="cc", baseline="none", repo=d) == 0
    cc_prefix = _prefix_of((d / "work/ctx/batch_2/context.md").read_text(encoding="utf-8"))
    assert "译甲" in cc_prefix

def test_empty_seqs_batch_cc_prefix_is_skeleton_only(tmp_path):
    """Park 项 A 判别性用例 3（brief 测试列表第 3 条）：本批 seqs 为空（extra
    车道形态，无时间轴位置）时，cc 下前缀不取任何正文（只留骨架），且不报错、
    不因窗口外的未译前序行触发退出码 2。id1（chapter=snr_x，与本批 chapter
    相同）故意不入 forward.jsonl 且未被 jp_fallback：若把"无时间轴位置"误判为
    "无边界→起点 0"（等同全部前序），id1 会被收进窗口、因未译触发退出码 2；
    旧 chapter 语义下 id1 与本批同 chapter 也不会被排除，同样会触发退出码 2——
    对新旧语义都有判别力。"""
    ledger_rows = [_ledger_row(1, "内容甲", "snr_x")]
    extra_rows = [{"key": "snr_x:1", "jp": "额外标题", "kind": "scene_title", "file": "snr_x"}]
    timeline_rows = [_unit_row(1, [1], "标题甲")]
    batches_rows = [
        _batch_row(1, [1], [1], "snr_x"),
        {"batch": 2, "lane": "extra", "ids": ["snr_x:1"], "seqs": [], "jp_chars": 4,
         "chapter": "snr_x", "cut_reason": "extra"},
    ]
    d = _mk_env(tmp_path, ledger_rows, timeline_rows, batches_rows, forward_rows=(),
                extra_rows=extra_rows)
    assert build(batch=2, profile="cc", baseline="none", repo=d) == 0
    prefix = _prefix_of((d / "work/ctx/batch_2/context.md").read_text(encoding="utf-8"))
    assert prefix.strip() == ""
    assert "内容甲" not in prefix and "未译" not in prefix

def test_untranslated_id_outside_window_does_not_trigger_exit_2(tmp_path):
    """Park 项 A 判别性用例 4（brief 测试列表第 4 条，"最容易写错"的一条）：
    窗口外的未译 id 不得触发退出码 2——_render_prefix 必须先按窗口收窄
    prior_ids，再检查是否已译；顺序反了（先对全部 prior_ids 做已译检查、事后
    才按窗口筛 resolved）会让 cc 档在 id1（窗口外、未译、且与本批同 chapter=x）
    上误报 2。id2/3 在窗口内且已译，证明窗口内容依然正常渲染；末尾对照
    api-A（不做窗口过滤）在同一份数据上确实因 id1 未译而报 2，证明 cc 下不报
    2 是窗口把它挡在外面，不是夹具本身凑巧没有未译行。"""
    ledger_rows = [_ledger_row(1, "内容零"), _ledger_row(2, "边界正文", "crd"),
                    _ledger_row(3, "内容一"), _ledger_row(4, "本批内容")]
    timeline_rows = [
        _unit_row(1, [1], "标题零"),
        _unit_row(2, [2], "边界", src="snr_crd_133"),
        _unit_row(3, [3], "标题一"),
        _unit_row(4, [4], "本批标题"),
    ]
    batches_rows = [
        _batch_row(1, [1], [1]), _batch_row(2, [2], [2], "crd"),
        _batch_row(3, [3], [3]), _batch_row(4, [4], [4], cut_reason="tail"),
    ]
    forward_rows = [_fwd_row(2, "译边界"), _fwd_row(3, "译一")]
    d = _mk_env(tmp_path, ledger_rows, timeline_rows, batches_rows, forward_rows)
    assert build(batch=4, profile="cc", baseline="none", repo=d) == 0
    prefix = _prefix_of((d / "work/ctx/batch_4/context.md").read_text(encoding="utf-8"))
    assert "译边界" in prefix and "译一" in prefix
    assert "内容零" not in prefix and "未译" not in prefix
    assert build(batch=4, profile="api-A", baseline="none", repo=d) == 2


def test_cli_repo_flag_routes_reads_and_writes_to_that_dir(tmp_path, monkeypatch):
    """--repo 必须把数据读取与产物落点一起切到该目录：既有 build(repo=…) 已实现，
    此前只是没有 CLI 入口。去掉 main() 里的 --repo 透传本测试必红。"""
    from tools.build_context import main
    env = _env(tmp_path)
    (env / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "车道标记译文", "batch": 0, "backend": "cc",
                    "model": "m", "ctx": "c", "glossary_v": 4, "ts": "t"},
                   ensure_ascii=False), encoding="utf-8")
    (env / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    rc = main(["--batch", "1", "--profile", "cc", "--baseline", "none",
               "--repo", str(env)])
    assert rc == 0
    ctx = env / "work" / "ctx" / "batch_1" / "context.md"
    assert ctx.exists(), "产物必须落在 --repo 指定的目录下"
    assert (env / "work" / "ctx" / "batch_1" / "source.jsonl").exists()
    assert (env / "work" / "ctx" / "batch_1" / "manifest.json").exists()


def test_cli_without_repo_keeps_default_behaviour(tmp_path, monkeypatch):
    """不给 --repo 时行为不变（仍读仓库 data/、写 pipelib.WORK）——用 ZND_WORK
    把落点引到 tmp_path，断言真实仓库 work/ 不被本测试写入。"""
    from tools.build_context import main
    import tools.pipelib as pipelib
    monkeypatch.setattr(pipelib, "WORK", tmp_path / "w")
    import tools.build_context as bc
    monkeypatch.setattr(bc, "_WORK", tmp_path / "w")
    rc = main(["--batch", "1", "--profile", "cc", "--baseline", "none",
               "--jp-fallback"])
    assert rc == 0
    assert (tmp_path / "w" / "ctx" / "batch_1" / "context.md").exists()


# ---------------------------------------------------------------------------
# Task 2: 第三节压缩锚点 + 第四节内嵌角色口调表
# ---------------------------------------------------------------------------

def _env_with_voices(tmp_path):
    """在既有 _env 夹具上补出 anchors.yaml（含 recall）与 voices/ 两份口调表。"""
    d = _env(tmp_path)
    (d / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    (d / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n"
        "  items:\n"
        "    - {id: 1, jp: 第一句, zh: 定译第一句, recall: 这是给骨架维护者的复现说明}\n",
        encoding="utf-8")
    (d / "glossary" / "voices").mkdir()
    (d / "glossary" / "voices" / "naoya.md").write_text(
        "# 直哉口调表\n自称：僕→我", encoding="utf-8")
    (d / "glossary" / "voices" / "sakura.md").write_text(
        "# サクラ口调表\n句尾：ですね体", encoding="utf-8")
    return d


def test_anchor_section_is_compact_and_drops_recall(tmp_path):
    """第三节只给 id/jp/zh：recall 是骨架维护者的元信息，对译者不改变行动，
    却占该节 35% 体量。保留整文件内嵌本测试必红。"""
    from tools.build_context import build
    d = _env_with_voices(tmp_path)
    assert build(1, "cc", "none", repo=d, jp_fallback=True) == 0
    ctx = (d / "work" / "ctx" / "batch_1" / "context.md").read_text(encoding="utf-8")
    assert "定译第一句" in ctx, "锚点 zh 必须仍在"
    assert "[1] 第一句" in ctx, "锚点 jp 必须仍在，且为紧凑行形态"
    assert "这是给骨架维护者的复现说明" not in ctx, "recall 注释不应进入译者上下文"


def test_voice_sheets_are_embedded_in_section_four(tmp_path):
    """译者必须拿到评审据以打分的那 7 份口调表。"""
    from tools.build_context import build
    d = _env_with_voices(tmp_path)
    assert build(1, "cc", "none", repo=d, jp_fallback=True) == 0
    ctx = (d / "work" / "ctx" / "batch_1" / "context.md").read_text(encoding="utf-8")
    assert "## 四、术语、风格与角色口调" in ctx
    assert "口调表：naoya" in ctx and "自称：僕→我" in ctx
    assert "口调表：sakura" in ctx and "句尾：ですね体" in ctx
    # 口调表须排在第四节内、第五节之前
    assert ctx.index("自称：僕→我") < ctx.index("## 五、本批任务")


def test_manifest_records_voices_hash_and_it_tracks_changes(tmp_path):
    from tools.build_context import build
    import json as _json
    d = _env_with_voices(tmp_path)
    build(1, "cc", "none", repo=d, jp_fallback=True)
    h1 = _json.loads((d / "work" / "ctx" / "batch_1" / "manifest.json").read_text(
        encoding="utf-8"))["voices"]
    (d / "glossary" / "voices" / "naoya.md").write_text("# 直哉口调表\n改了", encoding="utf-8")
    build(1, "cc", "none", repo=d, jp_fallback=True)
    h2 = _json.loads((d / "work" / "ctx" / "batch_1" / "manifest.json").read_text(
        encoding="utf-8"))["voices"]
    assert len(h1) == 64 and h1 != h2, "口调表改动必须反映到 manifest 哈希"


def test_missing_voices_dir_degrades_gracefully(tmp_path):
    """既有夹具（无 voices/ 目录）必须照常构建——不得因缺目录而崩。"""
    from tools.build_context import build
    d = _env(tmp_path)
    (d / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    assert build(1, "cc", "none", repo=d, jp_fallback=True) == 0
