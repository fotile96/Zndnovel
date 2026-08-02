"""有界工具循环：模型要调工具就代它调，结果回灌，轮次有上限且到顶不静默。"""
import pytest

from tools.agent_loop import run_with_tools


def _chat_stub(script):
    """按脚本依次返回预设的 chat() 结果。"""
    calls = {"n": 0, "payloads": []}

    def fake_chat(messages, **kw):
        calls["payloads"].append((messages, kw))
        r = script[calls["n"]]
        calls["n"] += 1
        return r
    return fake_chat, calls


def test_single_round_without_tool_calls(monkeypatch):
    fake, calls = _chat_stub([{"content": "答案", "function_calls": [],
                              "reasoning_text": "想了想", "prompt_tokens": 10,
                              "completion_tokens": 2}])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    out = run_with_tools([{"role": "user", "content": "问"}])
    assert out["content"] == "答案" and out["rounds"] == 1
    assert out["tool_calls"] == [] and out["stopped_reason"] == "finished"


def test_tool_call_is_executed_and_fed_back(monkeypatch, tmp_path):
    fake, calls = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c1", "name": "get_anchor",
             "arguments": '{"id": 11}'}],
         "reasoning_text": "", "prompt_tokens": 10, "completion_tokens": 1},
        {"content": "它是锚点", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": 20, "completion_tokens": 3},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    monkeypatch.setattr("tools.agent_loop.call_tool",
                        lambda name, args, lane_dir=None: {"is_anchor": True, "id": args["id"]})
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["rounds"] == 2 and out["content"] == "它是锚点"
    assert out["tool_calls"][0]["name"] == "get_anchor"
    assert out["tool_calls"][0]["args"] == {"id": 11}
    assert out["stopped_reason"] == "finished"
    # 第二轮的 messages 必须带上工具结果
    second_messages = calls["payloads"][1][0]
    assert any("is_anchor" in str(m.get("content", "")) for m in second_messages)


def test_max_rounds_stops_loudly(monkeypatch):
    forever = {"content": "", "function_calls": [
        {"type": "function_call", "call_id": "c", "name": "get_anchor",
         "arguments": '{"id": 1}'}],
        "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr("tools.agent_loop.chat", lambda messages, **kw: dict(forever))
    monkeypatch.setattr("tools.agent_loop.call_tool",
                        lambda name, args, lane_dir=None: {"ok": True})
    out = run_with_tools([{"role": "user", "content": "问"}],
                         tool_names=["get_anchor"], max_rounds=3)
    assert out["rounds"] == 3 and out["stopped_reason"] == "max_rounds"


def test_bad_tool_arguments_do_not_crash_the_loop(monkeypatch):
    fake, _ = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c1", "name": "get_anchor",
             "arguments": "{不是合法 JSON"}],
         "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1},
        {"content": "算了", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": 2, "completion_tokens": 1},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["stopped_reason"] == "finished"
    assert "error" in out["tool_calls"][0]["result_summary"]


def test_incomplete_status_is_not_reported_as_finished(monkeypatch):
    """截断的一轮**必须**看得出来。`response.incomplete` 走的是正常返回路径
    （usage 齐全、台账行与正常调用同形），若不看 status，半截结论会被当完整结论用。"""
    fake, _ = _chat_stub([{"content": "结论是：本次审计发现 3 处未履行，分别是",
                           "function_calls": [], "reasoning_text": "",
                           "status": "response.incomplete",
                           "prompt_tokens": 100, "completion_tokens": 20}])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    out = run_with_tools([{"role": "user", "content": "问"}])
    assert out["stopped_reason"] == "incomplete"
    assert out["content"].endswith("分别是")      # 内容照常返回，只是标了不完整


def test_completed_status_still_finishes(monkeypatch):
    """反向：status 正常时不得误报 incomplete（防这条断言恒真）。"""
    fake, _ = _chat_stub([{"content": "答案", "function_calls": [], "reasoning_text": "",
                           "status": "response.completed",
                           "prompt_tokens": 1, "completion_tokens": 1}])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    assert run_with_tools([{"role": "user", "content": "问"}])["stopped_reason"] == "finished"


def test_tool_execution_failure_is_counted_not_just_stringified(monkeypatch):
    """系统性故障（lane_dir 传错、anchors.yaml 缺失）不得与「模型给了非法参数」
    混为一谈：前者计入 tool_errors，后者不计。"""
    def boom(name, args, lane_dir=None):
        raise FileNotFoundError("skeleton/anchors.yaml")

    fake, _ = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c1", "name": "get_anchor",
             "arguments": '{"id": 11}'}],
         "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1},
        {"content": "查不到也照样答", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": 2, "completion_tokens": 1},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    monkeypatch.setattr("tools.agent_loop.call_tool", boom)
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["tool_errors"] == 1
    assert "tool_error" in out["tool_calls"][0]["result_summary"]
    assert out["tool_calls"][0]["args"] == {"id": 11}     # 参数合法，照常记下来


def test_bad_arguments_are_not_counted_as_tool_errors(monkeypatch):
    fake, _ = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c1", "name": "get_anchor",
             "arguments": "{不是合法 JSON"}],
         "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1},
        {"content": "算了", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": 2, "completion_tokens": 1},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    monkeypatch.setattr("tools.agent_loop.call_tool",
                        lambda name, args, lane_dir=None: {"ok": True})
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["tool_errors"] == 0
    assert "bad_arguments" in out["tool_calls"][0]["result_summary"]


def test_unknown_token_sentinel_does_not_shrink_the_total(monkeypatch):
    """-1 是「不知道」不是 0：直接相加会把总数**减**掉（一个静默的低估）。
    正确做法是跳过该轮并标 tokens_estimated。"""
    fake, _ = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c", "name": "get_anchor",
             "arguments": '{"id": 1}'}],
         "reasoning_text": "", "prompt_tokens": 500, "completion_tokens": 10},
        {"content": "答", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": -1, "completion_tokens": -1},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    monkeypatch.setattr("tools.agent_loop.call_tool",
                        lambda name, args, lane_dir=None: {"ok": True})
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["prompt_tokens"] == 500 and out["completion_tokens"] == 10
    assert out["tokens_estimated"] is True


def test_tokens_not_flagged_estimated_when_all_known(monkeypatch):
    fake, _ = _chat_stub([{"content": "答案", "function_calls": [], "reasoning_text": "",
                           "prompt_tokens": 10, "completion_tokens": 2}])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    out = run_with_tools([{"role": "user", "content": "问"}])
    assert out["tokens_estimated"] is False and out["prompt_tokens"] == 10


def test_only_registry_names_reach_chat(monkeypatch):
    """白名单单一来源：loop 传给 chat 的 allowed_tool_names 必须来自注册表。"""
    from tools.agent_tools import TOOLS
    seen = {}

    def fake_chat(messages, **kw):
        seen.update(kw)
        return {"content": "ok", "function_calls": [], "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr("tools.agent_loop.chat", fake_chat)
    run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert seen["allowed_tool_names"] <= set(TOOLS)
    assert {t["name"] for t in seen["tools"]} == {"get_anchor"}
