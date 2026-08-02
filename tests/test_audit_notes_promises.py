"""手记「承诺-履行」审计：只审硬承诺，软倾向不审（spec §4.2）。

「无法判断」是一等公民（spec §4.4）：解析失败/轮次或输出被截断，必须能与
「确认无承诺」区分，不得静默坍缩成 clean。
"""
import json

from tools.audit_notes_promises import extract_promises, prewire_ids, render_report

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


def test_verify_does_not_fall_back_to_prewire_ids_when_model_says_none(monkeypatch):
    """决策（brief §4）：`ids_source == "model"` 且 `ids == []` 时不回退到
    `prewire_ids`——尊重模型「本承诺不针对具体行」的判断，走工具兜底而不是
    静默接回同一提案里其他子句的 id（T4 已刻意避免的跨子句污染，T5 不得在
    这里重新引入，见 `test_explicit_empty_model_ids_is_not_overridden_by_prewire`）。
    """
    from tools import audit_notes_promises as A
    seen = {}

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
    assert "5001" not in seen["user"]  # 没有偷偷把 prewire_ids 接进上下文


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

    def fake_extract(prop, runner=None):
        if prop["num"] == 1:
            return {"promises": [], "parse_ok": False, "stopped_reason": "finished", "ok": False}
        return {"promises": [{"kind": "已统一", "ids": [2], "ids_source": "model",
                              "prewire_ids": [2], "ids_invalid": [], "quote": "已统一",
                              "quote_verified": True}],
                "parse_ok": True, "stopped_reason": "finished", "ok": True}

    def fake_verify(pr, prop, lane_dir=None, runner=None):
        return {"verdict": "已履行", "evidence_ids": [2], "reason": "ok", "used_tools": False}

    monkeypatch.setattr(A, "extract_promises", fake_extract)
    monkeypatch.setattr(A, "verify_promise", fake_verify)

    out_path = tmp_path / "report.md"
    rc = A.main(["--lane-dir", str(lane), "--out", str(out_path)])
    assert rc == 0
    md = out_path.read_text(encoding="utf-8")
    assert "抽取失败提案 1 条" in md
    assert "提案甲" in md
    assert "已履行 1" in md
