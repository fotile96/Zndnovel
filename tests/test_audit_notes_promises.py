"""手记「承诺-履行」审计：只审硬承诺，软倾向不审（spec §4.2）。

「无法判断」是一等公民（spec §4.4）：解析失败/轮次或输出被截断，必须能与
「确认无承诺」区分，不得静默坍缩成 clean。
"""
import json

from tools.audit_notes_promises import extract_promises, prewire_ids

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
