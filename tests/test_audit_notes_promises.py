"""手记「承诺-履行」审计：只审硬承诺，软倾向不审（spec §4.2）。

「无法判断」是一等公民（spec §4.4）：解析失败/轮次或输出被截断，必须能与
「确认无承诺」区分，不得静默坍缩成 clean。
"""
import json

from tools.audit_notes_promises import (extract_promises, prewire_ids,
                                        prewire_ids_detail, render_report)

HARD = {"chapter": "s1s", "batch": 4, "num": 1,
        "title": "寝癖 → 睡翘的头发",
        "body": "- id 7327、7329、7332（本批 8 处）\n"
                "- 理由：两处措辞必须能对上。本批已按上述译法统一。\n"}
SOFT = {"chapter": "s1s", "batch": 4, "num": 2,
        "title": "菜单名的拉丁形态需要一条形态判据",
        "body": "- id 6632\n- 建议：立通则——片假名形态中文化。\n"}
# 两子句提案：一条带 id，另一条是与该 id 无关的通则声明。
MIXED = {"chapter": "s1s", "batch": 5, "num": 3,
         "title": "两条独立承诺",
         "body": "- id 5001、5002\n- 本批已按上述译法统一。\n"
                 "- 另：全篇「先生」一律不消歧，遇歧义保留原词——此为通则，不针对具体行。\n"}


def _runner(payload, stopped_reason="finished"):
    def fake(messages, **kw):
        return {"content": json.dumps(payload, ensure_ascii=False), "rounds": 1,
                "tool_calls": [], "stopped_reason": stopped_reason, "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    return fake


def _runner_raw(text, stopped_reason="finished"):
    def fake(messages, **kw):
        return {"content": text, "rounds": 1, "tool_calls": [],
                "stopped_reason": stopped_reason, "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    return fake


def test_prewire_ids_reads_ids_from_body():
    assert prewire_ids(HARD) == [7327, 7329, 7332]
    assert prewire_ids(SOFT) == [6632]


def test_extract_hard_promise():
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "本批已按上述译法统一"}]}))
    assert out["ok"] is True and out["parse_ok"] is True
    assert out["stopped_reason"] == "finished"
    promises = out["promises"]
    assert len(promises) == 1 and promises[0]["kind"] == "已统一"
    assert promises[0]["ids"] == [7327, 7329, 7332]
    assert promises[0]["ids_source"] == "model"


def test_soft_suggestion_yields_no_promise():
    out = extract_promises(SOFT, runner=_runner({"promises": []}))
    assert out["ok"] is True
    assert out["promises"] == []


def test_malformed_model_output_is_distinguishable_from_confirmed_no_promise():
    """模型吐了非 JSON —— 必须能与「模型确认无承诺」区分，不能都坍缩成 `promises == []`。

    过去的实现里两者都是 `[] == []`，报告顶部的「无法判断占比」因此是假的
    （见 task-4 复评）：这里同时断言「无承诺」分支的 `ok` 为真、「解析失败」
    分支的 `ok` 为假，证明二者在返回值层面确实可区分，而不仅仅是断言前者
    等于空列表。
    """
    clean = extract_promises(SOFT, runner=_runner({"promises": []}))
    broken = extract_promises(HARD, runner=_runner_raw("这不是 JSON"))

    assert clean["ok"] is True and clean["promises"] == []
    assert broken["parse_ok"] is False
    assert broken["ok"] is False
    assert broken["promises"] == []
    # 二者的 `promises` 字面相等，但 `ok` 不同——下游必须按 `ok` 分流，不能只看 promises。
    assert clean["promises"] == broken["promises"]
    assert clean["ok"] != broken["ok"]


def test_stopped_reason_max_rounds_is_not_treated_as_clean():
    out = extract_promises(HARD, runner=_runner({"promises": []}, stopped_reason="max_rounds"))
    assert out["stopped_reason"] == "max_rounds"
    assert out["ok"] is False


def test_stopped_reason_incomplete_is_not_treated_as_clean():
    out = extract_promises(HARD, runner=_runner({"promises": []}, stopped_reason="incomplete"))
    assert out["stopped_reason"] == "incomplete"
    assert out["ok"] is False


def test_quote_verified_true_when_quote_is_substring_of_body():
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "本批已按上述译法统一"}]}))
    assert out["promises"][0]["quote_verified"] is True


def test_quote_verified_false_when_quote_not_found_but_promise_kept():
    """`quote` 编造/走样时不核实但**不丢弃**该承诺——机械闸只留痕、不做过滤，
    避免模型对原话做省略号截断这类合理改写被误伤为「无承诺」。"""
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "这句话提案正文里压根没有"}]}))
    promises = out["promises"]
    assert len(promises) == 1
    assert promises[0]["quote_verified"] is False


def test_explicit_empty_model_ids_is_not_overridden_by_prewire():
    """模型对『通则声明』正确返回 `ids: []`（本承诺不针对具体 id）时，不得被
    提案级 prewire_ids 强行接上——那是跨子句污染，会让 T5 拿错误的依据行去核对。
    """
    out = extract_promises(MIXED, runner=_runner(
        {"promises": [
            {"kind": "已统一", "ids": [5001, 5002], "quote": "本批已按上述译法统一。"},
            {"kind": "通则不消歧", "ids": [],
             "quote": "全篇「先生」一律不消歧，遇歧义保留原词"},
        ]}))
    promises = out["promises"]
    assert len(promises) == 2
    tied, general = promises
    assert tied["ids"] == [5001, 5002]
    assert tied["ids_source"] == "model"

    # 关键断言：显式空 ids 必须保持为空，不能被 prewire_ids(MIXED)（[5001, 5002]）覆盖。
    assert general["ids"] == []
    assert general["ids_source"] == "model"
    # 提案级 prewire ids 仍然分开保留，供 T5 自行决定是否回退。
    assert general["prewire_ids"] == [5001, 5002]


def test_model_omitting_ids_field_falls_back_to_prewire():
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "quote": "本批已按上述译法统一"}]}))
    p = out["promises"][0]
    assert p["ids_source"] == "prewire"
    assert p["ids"] == prewire_ids(HARD)


def test_invalid_id_items_are_dropped_not_silently_coerced():
    """`bool` 是 `int` 的子类、`isinstance` 会把 `True` 误判为合法 id；浮点数/
    非数字字符串同理不应被静默接受。非法项应被丢弃并记入 `ids_invalid`，而不是
    像过去那样把 `True` 变成虚构的 id `1`。
    """
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": ["abc", 7327.5, True, "007"],
                       "quote": "本批已按上述译法统一"}]}))
    p = out["promises"][0]
    assert p["ids"] == [7]  # 只有 "007" 是合法的纯数字字符串
    assert True in p["ids_invalid"]
    assert "abc" in p["ids_invalid"]
    assert 7327.5 in p["ids_invalid"]
    assert 1 not in p["ids"]  # True 不得被静默转换成 id 1


def test_prewire_ids_does_not_cross_newline():
    """排版延续行（缩进换行）不应被吞进同一个 id 列表——生产会话仍在往
    notes/*.md 追加内容，缩进延续行随时可能出现。
    """
    proposal = {"body": "- id 100、101\n  202、303\n"}
    assert prewire_ids(proposal) == [100, 101]


def test_prewire_ids_normalizes_fullwidth_digits():
    proposal = {"body": "- id 7327、７３２９\n"}
    assert prewire_ids(proposal) == [7327, 7329]


# --- 缺陷 1：区间写法（`id 17050–17121`）必须展开 -------------------------


def test_prewire_ids_expands_ranges_with_each_dash_variant():
    """语料实测只有 `-` 与 en dash `–`，但手记是人手写的：全角减号/波浪号
    随时可能冒出，漏一种就等于把整族承诺静默截成首个 id。逐种钉死。
    """
    for dash in "-–—―‐‑‒−~〜～ー－ｰ":
        proposal = {"body": f"- id 100{dash}104（本批 5 处）\n"}
        assert prewire_ids(proposal) == [100, 101, 102, 103, 104], f"分隔符 {dash!r} 未被识别"


def test_prewire_ids_expands_range_from_real_corpus_line():
    """crd b10 #2 的实况写法：区间后面还跟着中文与反引号。"""
    proposal = {"body": "- id 17050–17121 等；这些【】不是角色，是教程小标题。\n"}
    ids = prewire_ids(proposal)
    assert len(ids) == 72
    assert ids[0] == 17050 and ids[-1] == 17121
    assert 17118 in ids and 17121 in ids


def test_prewire_ids_mixes_ranges_and_enumerations_in_order():
    proposal = {"body": "- id 17193、17195–17197\n"}
    assert prewire_ids(proposal) == [17193, 17195, 17196, 17197]


def test_prewire_ids_does_not_join_adjacent_numbers_into_a_range():
    """顿号/全角逗号分隔的相邻数字是**枚举**，不是区间——误连会凭空造出
    从未写明的 id，把核对材料掺进无关行。
    """
    assert prewire_ids({"body": "- id 100、105\n"}) == [100, 105]
    assert prewire_ids({"body": "- id 100，105\n"}) == [100, 105]
    assert prewire_ids({"body": "- id 100 105\n"}) == [100, 105]
    # 跨行更不该连：延续行本来就不属于同一个 id 列表。
    assert prewire_ids({"body": "- id 100\n  105\n"}) == [100]


def test_prewire_ids_truncates_at_limit_with_visible_trace():
    """防区间爆炸：超上限必须**显式截断并留痕**，绝不静默丢弃。"""
    d = prewire_ids_detail({"body": "- id 1–500\n"}, limit=100)
    assert len(d["ids"]) == 100
    assert d["ids"][0] == 1 and d["ids"][-1] == 100
    assert d["truncated"] is True
    assert d["dropped"] == 400
    assert d["notes"] and "上限" in d["notes"][0] and "400" in d["notes"][0]


def test_prewire_ids_no_trace_when_within_limit():
    d = prewire_ids_detail({"body": "- id 7327、7329\n"})
    assert d["ids"] == [7327, 7329]
    assert d["notes"] == [] and d["truncated"] is False and d["dropped"] == 0


def test_prewire_ids_reversed_range_keeps_both_ends_with_trace():
    """起止倒置（笔误）照 `range(a, b+1)` 展开会得到空集，等于把两个写明的
    id 一起吞掉。保留两端并留痕。"""
    d = prewire_ids_detail({"body": "- id 200–100\n"})
    assert d["ids"] == [200, 100]
    assert any("倒置" in n for n in d["notes"])


def test_prewire_ids_absurd_span_is_refused_not_materialized():
    """`id 1–99999999` 这类笔误若照直展开会把进程拖死；拒绝展开并留痕。"""
    d = prewire_ids_detail({"body": "- id 1–99999999\n"})
    assert d["ids"] == [1, 99999999]
    assert any("跨度" in n for n in d["notes"])


def test_extract_promises_carries_prewire_note(monkeypatch):
    """留痕要一路传到 promise 上，`render_report` 才印得出来。"""
    prop = dict(HARD, body="- id 1–500\n- 本批已按上述译法统一。\n")
    out = extract_promises(prop, runner=_runner(
        {"promises": [{"kind": "已统一", "quote": "本批已按上述译法统一"}]}))
    p = out["promises"][0]
    assert p["ids_source"] == "prewire"
    assert len(p["ids"]) == 100
    assert "上限" in p["prewire_note"]


def test_report_shows_prewire_note():
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1",
                                       "prewire_note": "正文 id 展开后超过上限 100"},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False}])
    assert "id 抽取留痕" in md and "超过上限" in md


# ---------------------------------------------------------------------------
# Task 5：verify_promise / render_report / main
# ---------------------------------------------------------------------------


def test_verify_uses_prewired_context_when_ids_present(monkeypatch):
    """id 齐全时走预拼上下文，不开工具（便宜、可预测）。"""
    from tools import audit_notes_promises as A
    seen = {}

    def fake_runner(messages, **kw):
        seen["tool_names"] = kw.get("tool_names")
        seen["user"] = messages[-1]["content"]
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "译文含睡翘"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "已履行" and out["used_tools"] is False
    assert not seen["tool_names"]          # 未给工具
    assert "头发睡翘了" in seen["user"]     # 上下文已预拼


def test_verify_opens_tools_when_ids_missing(monkeypatch):
    """id 缺失时才给工具兜底。"""
    from tools import audit_notes_promises as A
    seen = {}

    def fake_runner(messages, **kw):
        seen["tool_names"] = kw.get("tool_names")
        return {"content": json.dumps({"verdict": "无法判断", "evidence_ids": [],
                                       "reason": "找不到对应行"}, ensure_ascii=False),
                "rounds": 2, "tool_calls": [{"name": "search_lines"}],
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "保留歧义", "ids": [], "quote": "保留歧义"},
                           {"chapter": "s1s", "batch": 4, "num": 9, "title": "t",
                            "body": "本段 8 处"}, runner=fake_runner)
    assert out["used_tools"] is True
    assert set(seen["tool_names"]) == {"get_lines", "search_lines", "get_anchor"}


def test_unparseable_verdict_becomes_cannot_tell(monkeypatch):
    """模型没给合法 JSON —— 记「无法判断」，绝不硬判成「已履行」（spec §4.4）。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {"lines": []})
    out = A.verify_promise({"kind": "x", "ids": [1], "quote": "q"}, HARD,
                           runner=_runner_raw("我觉得应该没问题"))
    assert out["verdict"] == "无法判断"


def test_report_puts_unfulfilled_first_and_shows_cannot_tell_ratio():
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False},
        {"proposal": HARD, "promise": {"kind": "b", "quote": "q2"},
         "verdict": "未履行", "evidence_ids": [2], "reason": "r2", "used_tools": False},
        {"proposal": HARD, "promise": {"kind": "c", "quote": "q3"},
         "verdict": "无法判断", "evidence_ids": [], "reason": "r3", "used_tools": True},
    ])
    assert md.index("未履行") < md.index("已履行")
    assert "无法判断占比" in md and "33" in md


# --- 三条机械闸（brief §2，本任务核心要求） -------------------------------


def test_gate_stopped_reason_not_finished_forces_cannot_tell(monkeypatch):
    """机械闸①：stopped_reason 非 finished——纵使模型给出「已履行」也要强制降级。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "看起来没问题"}, ensure_ascii=False),
                "rounds": 6, "tool_calls": [], "stopped_reason": "max_rounds",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "无法判断"
    assert "机械闸" in out["reason"] and "max_rounds" in out["reason"]


def test_gate_tool_errors_forces_cannot_tell(monkeypatch):
    """机械闸②：tool_errors 非 0——模型看到的是报错文本，纵使它照样自信作答。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "看起来没问题"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [{"name": "get_lines"}], "tool_errors": 1,
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "无法判断"
    assert "tool_errors" in out["reason"]


def test_gate_missing_tool_errors_key_defaults_to_zero(monkeypatch):
    """假 runner 没给 `tool_errors` 键时按 0 处理（`.get(..., 0)`），不因缺键
    崩溃、也不误判为闸②生效——plan 给的假 runner 就没有这个键。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "ok"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "已履行"


def test_gate_tools_opened_but_never_called_forces_cannot_tell():
    """机械闸③：ids 缺失→开了工具，但模型一次都没调用——判断是凭空作答。"""
    from tools import audit_notes_promises as A

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [],
                                       "reason": "我觉得应该统一了"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "保留歧义", "ids": [], "quote": "保留歧义"},
                           {"chapter": "s1s", "batch": 4, "num": 9, "title": "t",
                            "body": "本段 8 处"}, runner=fake_runner)
    assert out["verdict"] == "无法判断"
    assert "一次都没调用" in out["reason"]


def test_gate3_does_not_fire_when_ids_prewired_even_if_no_tool_calls(monkeypatch):
    """边界：预拼路径（ids 齐全）本来就不给工具，`tool_calls` 为空是正常状态，
    不得被闸③误伤（brief §2 明确点名的边界）。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "译文含睡翘"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "已履行"


def test_prewire_call_tool_exception_forces_cannot_tell_without_calling_model(monkeypatch):
    """T5 复评 §2：预拼路径的 `call_tool` 不经过 `run_with_tools` 内部的
    try/except，机械闸②对它不生效。这里补的早退闸：取材阶段抛异常时强制
    「无法判断」，口径与机械闸②一致（reason 里点明是取材阶段失败），且
    **不应该再去调用模型**——材料都没有，调用只是白花钱。
    """
    from tools import audit_notes_promises as A

    def boom(name, args, lane_dir=None):
        raise RuntimeError("ledger 文件缺失")
    monkeypatch.setattr(A, "call_tool", boom)

    called = {"n": 0}

    def fake_runner(messages, **kw):
        called["n"] += 1
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [],
                                       "reason": "不管怎样都算履行了"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "无法判断"
    assert "RuntimeError" in out["reason"] and "取材阶段失败" in out["reason"]
    assert called["n"] == 0  # 模型未被调用——省下一次注定判不出东西的真实调用


def test_gate4_all_lines_without_translation_forces_cannot_tell(monkeypatch):
    """「材料为空」闸：预拼取回的行全部没有译文（zh 为空/None）——id 不在
    ledger/zh 表里时 `get_lines` 会静默返回 `zh=None`，没有任何闸拦截的话
    模型可能拿着空材料照样给出「已履行」（T5 复评 §2）。全空时应强制降级，
    且不应该再调用模型。
    """
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 9999, "jp": None, "zh": None, "chapter": None}]})

    called = {"n": 0}

    def fake_runner(messages, **kw):
        called["n"] += 1
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [],
                                       "reason": "看起来没问题"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [9999], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "无法判断"
    assert "材料不足以判定" in out["reason"] or "为空" in out["reason"]
    assert called["n"] == 0


def test_gate4_partial_translation_does_not_fire(monkeypatch):
    """边界：部分行有译文、部分没有是正常情形（该批可能只译了一部分），
    不应误开火——否则会把大量本可判定的承诺误降成「无法判断」，把可信度
    指标搞脏。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"},
                  {"id": 9999, "jp": "未译行", "zh": None, "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "译文含睡翘"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327, 9999], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "已履行"  # 未被误伤，模型的结论正常生效


def test_verify_does_not_fall_back_to_prewire_ids_when_model_says_none(monkeypatch):
    """决策（brief §4）：`ids_source == "model"` 且 `ids == []` 时不回退到
    `prewire_ids`——尊重模型「本承诺不针对具体行」的判断，走工具兜底而不是
    静默接回同一提案里其他子句的 id（T4 已刻意避免的跨子句污染，T5 不得在
    这里重新引入，见 `test_explicit_empty_model_ids_is_not_overridden_by_prewire`）。

    **断言口径随缺陷 2 的修复调整过**：原先断言的是「`"5001"` 这个字符串不出现
    在整条 user 消息里」。加入提案正文后该字面必然出现——正文里就写着
    `- id 5001、5002`，而让模型读到正文正是缺陷 2 要修的东西。真正要守住的
    invariant 不是「字面不出现」，而是**工具没被绕过**：不得拿 `prewire_ids`
    去 `call_tool` 预取行、把结果当成既定依据塞进【相关行】。下面按这个口径
    断言（`call_tool` 零调用 + 【相关行】仍是兜底占位符），比原来更贴题。
    """
    from tools import audit_notes_promises as A
    seen = {}
    fetched = {"n": 0}
    monkeypatch.setattr(A, "call_tool",
                        lambda *a, **k: fetched.__setitem__("n", fetched["n"] + 1))

    def fake_runner(messages, **kw):
        seen["tool_names"] = kw.get("tool_names")
        seen["user"] = messages[-1]["content"]
        return {"content": json.dumps({"verdict": "无法判断", "evidence_ids": [],
                                       "reason": "无具体行"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    promise = {"kind": "通则不消歧", "ids": [], "ids_source": "model",
               "prewire_ids": [5001, 5002], "quote": "全篇不消歧"}
    A.verify_promise(promise, MIXED, runner=fake_runner)
    assert seen["tool_names"]          # 走了工具兜底，不是预拼
    assert fetched["n"] == 0           # 没有偷偷拿 prewire_ids 去预取行
    ctx = seen["user"].split("【相关行】", 1)[1]
    assert "请用工具自行查找相关行" in ctx
    assert "5001" not in ctx           # 依据行区里没有被接回来的 prewire id


# --- 缺陷 2：提案正文必须拼进核对提示 --------------------------------------


def test_verify_passes_proposal_body_to_model(monkeypatch):
    """承诺内容常常不在 quote 那句里，而在正文后面的表格/清单里。正文不传
    等于让模型闭着眼判——它判「无法判断」是诚实的，但那份不确定是工具造的。
    """
    from tools import audit_notes_promises as A
    seen = {}
    prop = dict(HARD, body="- id 7327\n- 本批落笔如下：\n"
                           "  | 原文 | 译法 |\n  | 寝癖 | 睡翘的头发 |\n")

    def fake_runner(messages, **kw):
        seen["user"] = messages[-1]["content"]
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "对得上表格"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "本批落笔如下"},
                           prop, runner=fake_runner)
    assert out["verdict"] == "已履行"
    assert "【提案正文】" in seen["user"]
    assert "| 寝癖 | 睡翘的头发 |" in seen["user"]
    assert out["body_truncated"] is False


def test_verify_passes_proposal_body_on_tool_fallback_path(monkeypatch):
    """工具兜底路径（ids 为空）同样要给正文——那条路径的材料本来就更少。"""
    from tools import audit_notes_promises as A
    seen = {}

    def fake_runner(messages, **kw):
        seen["user"] = messages[-1]["content"]
        return {"content": json.dumps({"verdict": "无法判断", "evidence_ids": [],
                                       "reason": "x"}, ensure_ascii=False),
                "rounds": 2, "tool_calls": [{"name": "search_lines"}],
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    A.verify_promise({"kind": "通则", "ids": [], "quote": "全篇不消歧"},
                     MIXED, runner=fake_runner)
    assert "全篇「先生」一律不消歧" in seen["user"]


def test_verify_truncates_overlong_body_with_explicit_marker(monkeypatch):
    """超长正文要截断，但**必须带截断标记**——静默截断会让模型拿着半截表格
    照常给出「已履行」，而报告里没有任何痕迹。"""
    from tools import audit_notes_promises as A
    seen = {}
    long_body = "- id 7327\n" + ("正文很长" * 5000)
    prop = dict(HARD, body=long_body)

    def fake_runner(messages, **kw):
        seen["user"] = messages[-1]["content"]
        return {"content": json.dumps({"verdict": "无法判断", "evidence_ids": [],
                                       "reason": "判据在截断段"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "q"},
                           prop, runner=fake_runner)
    assert out["body_truncated"] is True
    assert "已截断" in seen["user"]
    assert len(seen["user"]) < len(long_body)


def test_report_flags_truncated_body():
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1",
         "used_tools": False, "body_truncated": True}])
    assert "提案正文过长" in md and "已截断" in md


# --- 缺陷 3：evidence_ids 与抽取阶段口径一致 -------------------------------


def test_verify_accepts_string_evidence_ids(monkeypatch):
    """过去用 `isinstance(i, int)` 过滤，模型给 `"7327"` 会被**静默丢弃**，
    报告印出「依据行：（无）」而 reason 里明明点了行号。复用
    `_clean_model_ids`，与抽取阶段同一口径。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行",
                                       "evidence_ids": ["7327", 7329, "007"],
                                       "reason": "id 7327 译文含睡翘"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "q"},
                           HARD, runner=fake_runner)
    assert out["evidence_ids"] == [7327, 7329, 7]
    assert out["evidence_ids_invalid"] == []


def test_verify_traces_invalid_evidence_ids_instead_of_dropping_silently(monkeypatch):
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})

    def fake_runner(messages, **kw):
        return {"content": json.dumps({"verdict": "已履行",
                                       "evidence_ids": [7327, "abc", True, 1.5],
                                       "reason": "r"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "q"},
                           HARD, runner=fake_runner)
    assert out["evidence_ids"] == [7327]          # True 不得变成虚构的 id 1
    assert "abc" in out["evidence_ids_invalid"]
    assert True in out["evidence_ids_invalid"] and 1.5 in out["evidence_ids_invalid"]


def test_report_flags_invalid_evidence_ids():
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
         "verdict": "已履行", "evidence_ids": [1], "evidence_ids_invalid": ["abc"],
         "reason": "r1", "used_tools": False}])
    assert "依据行含非法项" in md


# --- 报告分母问题（brief §3，阻断级） -------------------------------------


def test_extraction_failures_are_visible_and_not_counted_as_clean():
    fail_prop = {"chapter": "s2s", "batch": 1, "num": 5, "title": "坏提案"}
    md = render_report(
        [{"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
          "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False}],
        extraction_failures=[{"proposal": fail_prop,
                               "reason": "parse_ok=False stopped_reason=finished"}])
    assert "抽取失败提案 1 条" in md
    assert "s2s" in md and "坏提案" in md
    # 抽取失败不得计入「已履行」——已履行仍只有 1（来自那条真实结果）
    assert "已履行 1" in md


def test_render_report_defaults_extraction_failures_to_empty():
    """无 extraction_failures 参数时按 0 条处理，向后兼容旧调用方式（plan
    给的 Step 1 测试就是这样调用的）。"""
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False}])
    assert "抽取失败提案 0 条" in md


def test_report_warns_when_quote_not_verified():
    """决策（brief §4）：`quote_verified` 不用于过滤/改判，只在明确为 False
    时于报告里加一句留痕提示——读者能看见但不影响判定。"""
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1", "quote_verified": False},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False}])
    assert "未在提案正文中逐字核验" in md


def test_report_does_not_warn_when_quote_verified_field_missing():
    """缺 `quote_verified` 字段（旧数据/最小测试桩）不应被当成核验失败误报警告。"""
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False}])
    assert "未在提案正文中逐字核验" not in md


def test_report_flags_invalid_ids_from_promise():
    """决策（brief §4）：`ids_invalid` 非空即说明模型输出有杂质，在报告里
    逐条列出供人复核，同样不用于改判。"""
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1", "ids_invalid": ["abc"]},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False}])
    assert "abc" in md and "非法项" in md


def test_main_records_extraction_failures_separately(monkeypatch, tmp_path):
    """main() 的循环要捕获抽取阶段的失败，而不是 `for pr in extract_promises(prop)`
    一笔带过（brief §3）。"""
    from tools import audit_notes_promises as A
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(
        "## batch 1\n### 1. 提案甲\n- id 1\n- 本批已按 X 统一。\n"
        "### 2. 提案乙\n- id 2\n- 本批已按 Y 统一。\n",
        encoding="utf-8")

    def fake_extract(prop, runner=None, max_rounds=None):
        if prop["num"] == 1:
            return {"promises": [], "parse_ok": False, "stopped_reason": "finished", "ok": False}
        return {"promises": [{"kind": "已统一", "ids": [2], "ids_source": "model",
                              "prewire_ids": [2], "ids_invalid": [], "quote": "已统一",
                              "quote_verified": True}],
                "parse_ok": True, "stopped_reason": "finished", "ok": True}

    def fake_verify(pr, prop, lane_dir=None, runner=None, max_rounds=None):
        return {"verdict": "已履行", "evidence_ids": [2], "reason": "ok", "used_tools": False}

    monkeypatch.setattr(A, "extract_promises", fake_extract)
    monkeypatch.setattr(A, "verify_promise", fake_verify)

    out_path = tmp_path / "report.md"
    rc = A.main(["--lane-dir", str(lane), "--out", str(out_path)])
    assert rc == 0
    md = out_path.read_text(encoding="utf-8")
    assert "抽取失败提案 1 条" in md
    assert "提案甲" in md


# --- main() 异常隔离 + 增量落盘（T5 复评发现，本次修复核心） -------------


def _lane_with_two_proposals(tmp_path):
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(
        "## batch 1\n### 1. 提案甲\n- id 1\n- 本批已按 X 统一。\n"
        "### 2. 提案乙\n- id 2\n- 本批已按 Y 统一。\n",
        encoding="utf-8")
    return lane


def test_main_survives_verify_promise_raising_and_still_writes_report(monkeypatch, tmp_path):
    """复评复现的场景：第 2 条提案的 `verify_promise` 抛异常。过去 `main()`
    会整体崩溃——`render_report` 从未被调用，报告文件根本不存在，连第 1
    条已经算出的「已履行」结果都一起没了。修复后：第 2 条的异常变成一条
    可见的「无法判断」结果，第 1 条的结果原样保留，报告正常写出，
    `rc == 0`。
    """
    from tools import audit_notes_promises as A
    lane = _lane_with_two_proposals(tmp_path)

    def fake_extract(prop, runner=None, max_rounds=None):
        return {"promises": [{"kind": "已统一", "ids": [prop["num"]],
                              "ids_source": "model", "prewire_ids": [prop["num"]],
                              "ids_invalid": [], "quote": "已统一",
                              "quote_verified": True}],
                "parse_ok": True, "stopped_reason": "finished", "ok": True}

    def fake_verify(pr, prop, lane_dir=None, runner=None, max_rounds=None):
        if prop["num"] == 1:
            return {"verdict": "已履行", "evidence_ids": [1], "reason": "ok",
                    "used_tools": False}
        raise RuntimeError("网络异常")

    monkeypatch.setattr(A, "extract_promises", fake_extract)
    monkeypatch.setattr(A, "verify_promise", fake_verify)

    out_path = tmp_path / "report.md"
    rc = A.main(["--lane-dir", str(lane), "--out", str(out_path)])

    assert rc == 0
    assert out_path.exists()
    md = out_path.read_text(encoding="utf-8")
    # 第 1 条已算出的「已履行」结果没有跟着第 2 条的异常一起消失。
    assert "已履行 1" in md
    # 第 2 条的异常变成一条可见的「无法判断」，异常类型+消息出现在报告里，
    # 不是被吞掉、也不是被误计入「已履行」。
    assert "无法判断 1" in md
    assert "RuntimeError" in md and "网络异常" in md


def test_main_survives_extract_promises_raising(monkeypatch, tmp_path):
    """抽取阶段本身抛异常（不是 `ok=False`，是直接抛）同样不得杀死整个循环，
    应归入抽取失败列表，异常类型+消息可见。"""
    from tools import audit_notes_promises as A
    lane = _lane_with_two_proposals(tmp_path)

    def fake_extract(prop, runner=None, max_rounds=None):
        if prop["num"] == 1:
            raise ValueError("解析崩了")
        return {"promises": [], "parse_ok": True, "stopped_reason": "finished", "ok": True}

    monkeypatch.setattr(A, "extract_promises", fake_extract)

    out_path = tmp_path / "report.md"
    rc = A.main(["--lane-dir", str(lane), "--out", str(out_path)])

    assert rc == 0
    md = out_path.read_text(encoding="utf-8")
    assert "抽取失败提案 1 条" in md
    assert "ValueError" in md and "解析崩了" in md


def test_main_writes_incremental_jsonl_sidecar_surviving_later_crash(monkeypatch, tmp_path):
    """增量落盘：即使第 2 条在核对阶段抛异常，第 1 条已经算出的结果也必须
    已经落在 sidecar 里——这是「进程中途死亡也不丢已花费调用的结论」这条
    纪律的验证点（哪怕 `main()` 本身已经不会再因此崩溃，sidecar 仍然是
    抵御「try/except 也接不住的意外」的第二道防线）。
    """
    from tools import audit_notes_promises as A
    lane = _lane_with_two_proposals(tmp_path)

    def fake_extract(prop, runner=None, max_rounds=None):
        return {"promises": [{"kind": "已统一", "ids": [prop["num"]],
                              "ids_source": "model", "prewire_ids": [prop["num"]],
                              "ids_invalid": [], "quote": "已统一",
                              "quote_verified": True}],
                "parse_ok": True, "stopped_reason": "finished", "ok": True}

    def fake_verify(pr, prop, lane_dir=None, runner=None, max_rounds=None):
        if prop["num"] == 1:
            return {"verdict": "已履行", "evidence_ids": [1], "reason": "ok",
                    "used_tools": False}
        raise RuntimeError("网络异常")

    monkeypatch.setattr(A, "extract_promises", fake_extract)
    monkeypatch.setattr(A, "verify_promise", fake_verify)

    out_path = tmp_path / "report.md"
    rc = A.main(["--lane-dir", str(lane), "--out", str(out_path)])
    assert rc == 0

    sidecar = out_path.with_suffix(".jsonl")
    assert sidecar.exists()
    lines = [json.loads(l) for l in sidecar.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert all(l["type"] == "result" for l in lines)
    verdicts = {l["data"]["verdict"] for l in lines}
    assert verdicts == {"已履行", "无法判断"}


def test_main_sidecar_truncated_at_start_of_run(tmp_path):
    """sidecar 在每次运行开始时清空，避免上一次运行的行混进这一次——
    否则增量落盘反而会制造「结论比实际多」的假象。"""
    from tools import audit_notes_promises as A
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    # 空提案：没有任何提案，验证 main() 至少会把 sidecar 清空成空文件。
    out_path = tmp_path / "report.md"
    sidecar = out_path.with_suffix(".jsonl")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text('{"type": "result", "data": {"verdict": "已履行"}}\n',
                       encoding="utf-8")

    rc = A.main(["--lane-dir", str(lane), "--out", str(out_path)])
    assert rc == 0
    assert sidecar.read_text(encoding="utf-8") == ""


# --- --max-rounds 透传 + 定点重跑（首轮全量审计暴露：110 条「无法判断」里 48 条
# 的 reason 是 stopped_reason=max_rounds，那是预算耗尽而非证据不足）-----------


def _spy_runner(seen, payload, **res_kw):
    def fake(messages, **kw):
        seen.append(kw)
        base = {"content": json.dumps(payload, ensure_ascii=False), "rounds": 1,
                "tool_calls": [], "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
        base.update(res_kw)
        return base
    return fake


def test_verify_passes_max_rounds_to_run_with_tools(monkeypatch):
    """判别性用例：`--max-rounds` 必须真的落到 `run_with_tools` 的 kwargs 上。
    只加 CLI 参数而没接到底（很容易发生）时本测试必红。"""
    from tools import audit_notes_promises as A
    seen = []
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})
    A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"}, HARD,
                     runner=_spy_runner(seen, {"verdict": "已履行",
                                               "evidence_ids": [7327], "reason": "r"}),
                     max_rounds=16)
    assert seen[0]["max_rounds"] == 16


def test_verify_max_rounds_reaches_tool_fallback_path_too(monkeypatch):
    """工具兜底那条路（`ids` 为空）才是 max_rounds 真正开火的地方，
    别只接了预拼路径。"""
    from tools import audit_notes_promises as A
    seen = []
    A.verify_promise({"kind": "通则", "ids": [], "quote": "q"},
                     {"chapter": "s1s", "batch": 4, "num": 9, "title": "t", "body": "b"},
                     runner=_spy_runner(seen, {"verdict": "已履行", "evidence_ids": [],
                                               "reason": "r"},
                                        tool_calls=[{"name": "get_lines"}]),
                     max_rounds=16)
    assert seen[0]["max_rounds"] == 16
    assert set(seen[0]["tool_names"]) == {"get_lines", "search_lines", "get_anchor"}


def test_max_rounds_omitted_keeps_run_with_tools_default(monkeypatch):
    """默认行为不变：不给 `--max-rounds` 时**不传**该 kwarg，
    由 `run_with_tools` 自己的默认（6）说了算——传 None 会把默认覆写成 None
    并让 `while rounds < None` 直接抛 TypeError。"""
    from tools import audit_notes_promises as A
    seen = []
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 1, "jp": "j", "zh": "z", "chapter": "s1s"}]})
    A.verify_promise({"kind": "k", "ids": [1], "quote": "q"}, HARD,
                     runner=_spy_runner(seen, {"verdict": "已履行",
                                               "evidence_ids": [1], "reason": "r"}))
    assert "max_rounds" not in seen[0]
    seen.clear()
    A.extract_promises(HARD, runner=_spy_runner(seen, {"promises": []}))
    assert "max_rounds" not in seen[0]


def test_extract_promises_passes_max_rounds():
    """抽取阶段同样会撞轮次预算（首轮里就有），一并可调。"""
    from tools import audit_notes_promises as A
    seen = []
    A.extract_promises(HARD, runner=_spy_runner(seen, {"promises": []}), max_rounds=12)
    assert seen[0]["max_rounds"] == 12


# --- 定点重跑：筛选 ---------------------------------------------------------

def _row(verdict, reason, num=1):
    return {"verdict": verdict, "reason": reason, "evidence_ids": [],
            "used_tools": True,
            "proposal": {"chapter": "s3s", "batch": 1, "num": num, "title": "t",
                         "body": "- id 1\n- 本批已按 X 统一。"},
            "promise": {"kind": "已统一", "ids": [], "quote": "已统一"}}


def test_is_gated_selects_only_budget_exhaustion_by_default():
    """判别性用例：默认只选轮次预算耗尽的那一族。模型自判的「无法判断」是
    证据不足，重跑只是再花一次钱；工具报错等其它机械闸是另一类问题，
    默认不混进来（要的话 gates="all"）。"""
    from tools.audit_notes_promises import is_gated
    budget = _row("无法判断", "机械闸：stopped_reason=max_rounds，结论不完整")
    tool_err = _row("无法判断", "机械闸：tool_errors=2，模型基于报错信息作答")
    evidence = _row("无法判断", "材料里没有可比对的译文")
    done = _row("已履行", "译文含睡翘")
    assert is_gated(budget) is True
    assert is_gated(tool_err) is False
    assert is_gated(evidence) is False
    assert is_gated(done) is False
    assert is_gated(tool_err, gates="all") is True
    assert is_gated(evidence, gates="all") is False
    assert is_gated(done, gates="all") is False


def test_load_sidecar_splits_results_and_extraction_failures(tmp_path):
    from tools.audit_notes_promises import load_sidecar
    p = tmp_path / "s.jsonl"
    p.write_text(
        json.dumps({"type": "result", "data": _row("已履行", "ok")}, ensure_ascii=False)
        + "\n"
        + json.dumps({"type": "extraction_failure",
                      "data": {"proposal": {"chapter": "s3s", "batch": 1, "num": 2,
                                            "title": "甲"}, "reason": "parse_ok=False"}},
                     ensure_ascii=False) + "\n"
        + '{"type": "result", "data": {"verdict"\n',   # 半截行（进程被杀）
        encoding="utf-8")
    results, fails = load_sidecar(p)
    assert len(results) == 1 and len(fails) == 1


def test_rerun_merges_without_losing_any_row():
    """合并不丢条目：重跑后条目数、顺序与原来完全一致，未选中的原样搬运。"""
    from tools.audit_notes_promises import rerun_gated
    rows = [_row("已履行", "ok", 1),
            _row("无法判断", "机械闸：stopped_reason=max_rounds，结论不完整", 2),
            _row("未履行", "与承诺矛盾", 3),
            _row("无法判断", "材料不足", 4)]

    def fake_verify(pr, prop, lane_dir=None, max_rounds=None):
        return {"verdict": "已履行", "evidence_ids": [9], "reason": "重跑后判出",
                "used_tools": True}

    merged, reran = rerun_gated(rows, verify=fake_verify)
    assert reran == 1
    assert len(merged) == len(rows)
    assert [m["proposal"]["num"] for m in merged] == [1, 2, 3, 4]
    assert [m["verdict"] for m in merged] == ["已履行", "已履行", "未履行", "无法判断"]
    # 被重跑那条保留了上一轮的判定与理由，两轮可对比。
    assert merged[1]["rerun_of"] == "无法判断"
    assert "max_rounds" in merged[1]["rerun_prev_reason"]
    # 未选中的条目原样搬运，连对象都没被改写。
    assert merged[0] is rows[0] and merged[3] is rows[3]


def test_rerun_passes_max_rounds_to_verify():
    from tools.audit_notes_promises import rerun_gated
    seen = {}

    def fake_verify(pr, prop, lane_dir=None, max_rounds=None):
        seen["max_rounds"], seen["lane_dir"] = max_rounds, lane_dir
        return {"verdict": "已履行", "evidence_ids": [], "reason": "r", "used_tools": True}

    rerun_gated([_row("无法判断", "机械闸：stopped_reason=max_rounds，结论不完整")],
                lane_dir="LANE", max_rounds=16, verify=fake_verify)
    assert seen == {"max_rounds": 16, "lane_dir": "LANE"}


def test_rerun_survives_verify_raising():
    """重跑里单条抛异常，仍变成一条可见的「无法判断」，条目不消失。"""
    from tools.audit_notes_promises import rerun_gated

    def boom(pr, prop, lane_dir=None, max_rounds=None):
        raise RuntimeError("网络异常")

    merged, reran = rerun_gated(
        [_row("无法判断", "机械闸：stopped_reason=max_rounds，结论不完整")],
        verify=boom)
    assert len(merged) == 1 and reran == 1
    assert merged[0]["verdict"] == "无法判断"
    assert "RuntimeError" in merged[0]["reason"] and "网络异常" in merged[0]["reason"]


# --- 定点重跑：main() 端到端 -------------------------------------------------

def _write_sidecar(path, rows, fails=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"type": "result", "data": r}, ensure_ascii=False) + "\n")
        for x in fails:
            f.write(json.dumps({"type": "extraction_failure", "data": x},
                               ensure_ascii=False) + "\n")


def test_main_rerun_from_sidecar_end_to_end(monkeypatch, tmp_path):
    """定点重跑不解析手记（不需要 notes/ 存在）、只重验被闸拦下的条目，
    合并成一份完整报告；原 sidecar 一个字节都没动。"""
    from tools import audit_notes_promises as A
    src = tmp_path / "audit-s3s.jsonl"
    fails = [{"proposal": {"chapter": "s3s", "batch": 1, "num": 9, "title": "提案戊"},
              "reason": "parse_ok=False stopped_reason=finished"}]
    _write_sidecar(src, [
        _row("已履行", "ok", 1),
        _row("无法判断", "机械闸：stopped_reason=max_rounds，结论不完整", 2),
        _row("无法判断", "材料不足以判定", 3)], fails)
    before = src.read_bytes()

    calls = []

    def fake_verify(pr, prop, lane_dir=None, max_rounds=None):
        calls.append((prop["num"], max_rounds))
        return {"verdict": "未履行", "evidence_ids": [1], "reason": "重跑判出矛盾",
                "used_tools": True}

    monkeypatch.setattr(A, "verify_promise", fake_verify)
    out = tmp_path / "rerun.md"
    rc = A.main(["--rerun-from", str(src), "--out", str(out),
                 "--max-rounds", "16", "--lane-dir", str(tmp_path / "lane")])
    assert rc == 0
    # 只重验了被闸拦下的那一条，且 max_rounds 透传到底。
    assert calls == [(2, 16)]
    # 原 sidecar 未被覆盖/截断。
    assert src.read_bytes() == before
    md = out.read_text(encoding="utf-8")
    # 3 条硬承诺一条不少，抽取失败条目也跟着搬进新报告。
    assert "（3 条硬承诺）" in md
    assert "已履行 1" in md and "未履行 **1**" in md and "无法判断 1" in md
    assert "抽取失败提案 1 条" in md and "提案戊" in md
    # 新 sidecar 完整（3 结果 + 1 抽取失败），可作为下一轮重跑的输入。
    new_rows = [json.loads(l) for l in
                out.with_suffix(".jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(1 for r in new_rows if r["type"] == "result") == 3
    assert sum(1 for r in new_rows if r["type"] == "extraction_failure") == 1


def test_main_rerun_refuses_to_overwrite_source_sidecar(tmp_path):
    """判别性用例：`--out` 推出的新 sidecar 若正是源文件，必须在**截断之前**
    拒绝。main() 开跑就 write_text("") ——撞上就等于原始证据永久丢失。"""
    import pytest
    from tools import audit_notes_promises as A
    out = tmp_path / "audit.md"
    src = out.with_suffix(".jsonl")
    _write_sidecar(src, [_row("已履行", "ok", 1)])
    before = src.read_bytes()
    with pytest.raises(SystemExit) as e:
        A.main(["--rerun-from", str(src), "--out", str(out)])
    assert "拒绝执行" in str(e.value.code)
    assert src.read_bytes() == before


def test_main_rerun_gates_all_widens_selection(monkeypatch, tmp_path):
    """`--rerun-gates all` 把四条机械闸拦下的全选上；模型自判的「无法判断」
    仍然不入选。"""
    from tools import audit_notes_promises as A
    src = tmp_path / "src.jsonl"
    _write_sidecar(src, [
        _row("无法判断", "机械闸：stopped_reason=max_rounds，结论不完整", 1),
        _row("无法判断", "机械闸：tool_errors=2，模型基于报错信息作答", 2),
        _row("无法判断", "材料不足以判定", 3)])
    calls = []

    def fake_verify(pr, prop, lane_dir=None, max_rounds=None):
        calls.append(prop["num"])
        return {"verdict": "已履行", "evidence_ids": [], "reason": "r", "used_tools": True}

    monkeypatch.setattr(A, "verify_promise", fake_verify)
    rc = A.main(["--rerun-from", str(src), "--out", str(tmp_path / "o.md"),
                 "--rerun-gates", "all"])
    assert rc == 0 and calls == [1, 2]
