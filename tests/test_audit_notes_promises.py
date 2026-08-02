"""手记「承诺-履行」审计：只审硬承诺，软倾向不审（spec §4.2）。"""
import json

from tools.audit_notes_promises import extract_promises, prewire_ids

HARD = {"chapter": "s1s", "batch": 4, "num": 1,
        "title": "寝癖 → 睡翘的头发",
        "body": "- id 7327、7329、7332（本批 8 处）\n"
                "- 理由：两处措辞必须能对上。本批已按上述译法统一。\n"}
SOFT = {"chapter": "s1s", "batch": 4, "num": 2,
        "title": "菜单名的拉丁形态需要一条形态判据",
        "body": "- id 6632\n- 建议：立通则——片假名形态中文化。\n"}


def _runner(payload):
    def fake(messages, **kw):
        return {"content": json.dumps(payload, ensure_ascii=False), "rounds": 1,
                "tool_calls": [], "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    return fake


def test_prewire_ids_reads_ids_from_body():
    assert prewire_ids(HARD) == [7327, 7329, 7332]
    assert prewire_ids(SOFT) == [6632]


def test_extract_hard_promise():
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "本批已按上述译法统一"}]}))
    assert len(out) == 1 and out[0]["kind"] == "已统一"
    assert out[0]["ids"] == [7327, 7329, 7332]


def test_soft_suggestion_yields_no_promise():
    out = extract_promises(SOFT, runner=_runner({"promises": []}))
    assert out == []


def test_malformed_model_output_is_treated_as_no_promise():
    """模型吐了非 JSON —— 视为无承诺并留痕，不得让整轮审计崩掉。"""
    out = extract_promises(HARD, runner=_runner_raw("这不是 JSON"))
    assert out == []


def _runner_raw(text):
    def fake(messages, **kw):
        return {"content": text, "rounds": 1, "tool_calls": [],
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    return fake


def test_quote_verified_true_when_quote_is_substring_of_body():
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "本批已按上述译法统一"}]}))
    assert out[0]["quote_verified"] is True


def test_quote_verified_false_when_quote_not_found_but_promise_kept():
    """`quote` 编造/走样时不核实但**不丢弃**该承诺——机械闸只留痕、不做过滤，
    避免模型对原话做省略号截断这类合理改写被误伤为「无承诺」。"""
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "这句话提案正文里压根没有"}]}))
    assert len(out) == 1
    assert out[0]["quote_verified"] is False
