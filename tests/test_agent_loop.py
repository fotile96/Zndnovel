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
