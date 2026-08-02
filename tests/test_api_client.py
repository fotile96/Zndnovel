"""API 薄客户端：注入 stream_transport 离线测试，零网络（P3 spec §5 里程碑 1）。

架构变更说明（task-10：chat/completions → Responses API 流式）：本文件里的假
transport 由「返回一个完整 dict」改成「yield `(event_type, data)` 事件序列」，
注入参数名由 `transport` 改为 `stream_transport`——旧的一次性同步语义与流式天然
不匹配，不该被超载（见 tools/api_client.py 里 `_http_stream_transport` 注释）。
断言本身只做了必要的字段名迁移（`max_tokens`→`max_output_tokens`、
`prompt_tokens`←`usage.input_tokens`），未削弱。
"""
import json
import urllib.error

import pytest

from tools.api_client import chat, iter_sse_events, load_env


def _events(text="回答内容", reasoning="先看看文本里怎么说",
            input_tokens=100, output_tokens=20, cached=0, reasoning_tokens=7,
            status="response.completed"):
    """造一段最小但形状真实的 Responses 事件序列（字段路径照实测抄）。"""
    yield "response.created", {"type": "response.created", "response": {}}
    yield "response.in_progress", {"type": "response.in_progress", "response": {}}
    yield "response.output_item.added", {"item": {"type": "reasoning"}}
    yield "response.reasoning_text.delta", {"delta": reasoning}
    yield "response.reasoning_text.done", {"text": reasoning}
    yield "response.output_item.added", {"item": {"type": "message"}}
    for ch in text:
        yield "response.output_text.delta", {"delta": ch}
    yield "response.output_text.done", {"text": text}
    yield status, {"response": {"usage": {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": cached},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
        "total_tokens": input_tokens + output_tokens}}}


def _fake_transport(url, headers, payload):
    assert url.startswith("https://api.deepseek.com")
    assert headers["Authorization"] == "Bearer sk-test"
    assert payload["model"] == "deepseek-v4-flash"   # Responses 只支持这个模型
    return _events()


def test_chat_returns_content_and_writes_ledger(tmp_path):
    lp = tmp_path / "api_ledger.jsonl"
    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=_fake_transport, ledger_path=lp, purpose="unit-test")
    assert r["content"] == "回答内容"
    assert r["prompt_tokens"] == 100 and r["completion_tokens"] == 20
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["purpose"] == "unit-test" and row["provider"] == "deepseek"
    assert row["prompt_tokens"] == 100


def test_chat_exposes_reasoning_and_cache_fields(tmp_path):
    """新增契约：reasoning_text / cached_tokens / reasoning_tokens 三键，且台账
    也记 cached/reasoning（此前对成本结构半盲——缓存命中与否差一个量级）。"""
    lp = tmp_path / "l.jsonl"
    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=_fake_transport, ledger_path=lp, purpose="u")
    assert r["reasoning_text"] == "先看看文本里怎么说"
    assert r["cached_tokens"] == 0 and r["reasoning_tokens"] == 7
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["cached_tokens"] == 0 and row["reasoning_tokens"] == 7


def test_missing_key_exits_with_guidance(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("tools.api_client.load_env", lambda path=None: {})
    with pytest.raises(SystemExit, match="DEEPSEEK_API_KEY"):
        chat([{"role": "user", "content": "hi"}], ledger_path=tmp_path / "l.jsonl")


def test_load_env_parses_quotes_and_comments(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# 注释\nDEEPSEEK_API_KEY="sk-abc"\nOTHER=1\n', encoding="utf-8")
    env = load_env(p)
    assert env["DEEPSEEK_API_KEY"] == "sk-abc" and env["OTHER"] == "1"


def test_retry_on_5xx_then_succeeds(tmp_path):
    calls = []
    sleeps = []

    def flaky_transport(url, headers, payload):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)
        return _events(input_tokens=1, output_tokens=1)

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=flaky_transport, ledger_path=tmp_path / "l.jsonl",
             sleeper=sleeps.append)
    assert r["content"] == "回答内容"
    assert len(calls) == 3                    # 失败两次后第三次成功
    assert sleeps == [2, 4]                   # 指数退避 2s / 4s，且未真正 sleep


def test_no_retry_on_4xx(tmp_path):
    calls = []
    sleeps = []

    def bad_request_transport(url, headers, payload):
        calls.append(1)
        raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=bad_request_transport, ledger_path=tmp_path / "l.jsonl",
             sleeper=sleeps.append)
    assert len(calls) == 1                    # 4xx 不重试，只打一次
    assert sleeps == []


def test_retries_exhausted_raises(tmp_path):
    calls = []
    sleeps = []

    def always_fails(url, headers, payload):
        calls.append(1)
        raise urllib.error.URLError("connection refused")

    with pytest.raises(urllib.error.URLError):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=always_fails, ledger_path=tmp_path / "l.jsonl",
             retries=2, sleeper=sleeps.append)
    assert len(calls) == 3                    # 1 次首发 + 2 次重试
    assert sleeps == [2, 4]


def test_retries_zero_disables_retry(tmp_path):
    calls = []

    def always_fails(url, headers, payload):
        calls.append(1)
        raise urllib.error.URLError("connection refused")

    with pytest.raises(urllib.error.URLError):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=always_fails, ledger_path=tmp_path / "l.jsonl",
             retries=0, sleeper=lambda s: pytest.fail("不该 sleep"))
    assert len(calls) == 1


def _sse_lines(text="ok", reasoning="想一下", input_tokens=5, output_tokens=3):
    """真实 SSE 线格式（event: / data: / 空行分隔），用于验默认 transport 通路。"""
    def ev(t, d):
        return [f"event: {t}\n", f"data: {json.dumps(d, ensure_ascii=False)}\n", "\n"]
    out = []
    out += ev("response.created", {"type": "response.created", "response": {}})
    out += ev("response.reasoning_text.delta", {"delta": reasoning})
    out += ev("response.output_text.delta", {"delta": text})
    out += ev("response.output_text.done", {"text": text})
    out += ev("response.completed", {"response": {"usage": {
        "input_tokens": input_tokens, "input_tokens_details": {"cached_tokens": 2},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": 1}}}})
    return [ln.encode("utf-8") for ln in out]


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def test_default_transport_receives_configured_timeout(tmp_path, monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return _FakeResp(_sse_lines())

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl", timeout=12)
    assert captured["timeout"] == 12


def test_default_idle_timeout_and_max_output_tokens_when_unset(tmp_path, monkeypatch):
    """默认值闸：timeout 未指定时走 DEFAULT_IDLE_TIMEOUT（逐 chunk 静默超时，
    urlopen 的 socket 超时对流式响应本就是每次 read 各自计时）；max_tokens 默认
    4096 且映射到 Responses 的 `max_output_tokens`（不是 chat/completions 的
    `max_tokens`）。"""
    from tools.api_client import DEFAULT_IDLE_TIMEOUT

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(_sse_lines())

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             ledger_path=tmp_path / "l.jsonl")
    assert captured["timeout"] == DEFAULT_IDLE_TIMEOUT
    assert captured["payload"]["max_output_tokens"] == 4096
    assert r["content"] == "ok" and r["cached_tokens"] == 2


# ---------------------------------------------------------------- 新增行为

def test_payload_is_responses_shaped_and_streaming(tmp_path, monkeypatch):
    """请求体形状：Responses 字段名（input/instructions/max_output_tokens/
    reasoning.effort）且 stream=True——非流式就拿不到 CoT 与抗超时两条好处。"""
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(_sse_lines())

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    chat([{"role": "system", "content": "你是判分员"},
          {"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl", effort="low")
    p = captured["payload"]
    assert p["stream"] is True
    assert p["instructions"] == "你是判分员"
    assert p["input"] == [{"role": "user", "content": "hi"}]
    assert p["reasoning"] == {"effort": "low"}
    assert "messages" not in p and "max_tokens" not in p


def test_payload_never_sends_tools_or_web_search(tmp_path, monkeypatch):
    """⚠ 恒绿关卡防线：Responses API 内置服务端 web_search，一旦启用，彩野测试的
    受试模型就能直接上网查《セカンドノベル》剧情、不看译文也答对，测试静默失效。
    请求体里不得出现 tools，也不得出现任何 web_search 相关字段。"""
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["raw"] = req.data.decode("utf-8")
        captured["payload"] = json.loads(captured["raw"])
        return _FakeResp(_sse_lines())

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl")
    assert "tools" not in captured["payload"]
    assert "tool_choice" not in captured["payload"]
    assert "web_search" not in captured["raw"]


def test_iter_sse_events_parses_multiline_comments_and_done():
    """SSE 解析：event/data 配对、跨行 data 拼接、`:` 注释行忽略、[DONE] 跳过、
    结尾无空行也要吐出最后一个事件、data 非法 JSON 不炸。"""
    lines = [
        ": keep-alive\n",
        "event: response.output_text.delta\n",
        'data: {"delta": "你好"}\n',
        "\n",
        "event: multi\n",
        'data: {"a":\n',
        'data: 1}\n',
        "\n",
        "event: broken\n",
        "data: not-json\n",
        "\n",
        "data: [DONE]\n",
        "\n",
        "event: response.completed\n",
        'data: {"response": {}}\n',          # 故意不以空行收尾
    ]
    got = list(iter_sse_events(lines))
    assert got[0] == ("response.output_text.delta", {"delta": "你好"})
    assert got[1] == ("multi", {"a": 1})
    assert got[2] == ("broken", {})
    assert got[-1] == ("response.completed", {"response": {}})
    assert len(got) == 4                      # [DONE] 与注释行都没变成事件


def test_no_terminal_event_is_an_error(tmp_path):
    """断流：只吐了几个 delta 就没了（没有 completed/incomplete/failed）不能被当
    成正常完成——那会把半截回答当完整答案交给判分员。"""
    def truncated(url, headers, payload):
        yield "response.output_text.delta", {"delta": "半"}

    with pytest.raises(Exception, match="终止事件"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=truncated, ledger_path=tmp_path / "l.jsonl",
             retries=0)


def test_partial_tokens_are_ledgered_even_when_request_fails(tmp_path):
    """① 流式重试/失败要把已产生的部分 token 计入台账，否则实际花费被系统性低估。
    台账行带 partial 标记与 estimated（终止事件没到达时输出侧按 delta 计数估算，
    输入侧无从得知记 -1）。"""
    lp = tmp_path / "l.jsonl"

    def dies_midstream(url, headers, payload):
        yield "response.reasoning_text.delta", {"delta": "想"}
        yield "response.output_text.delta", {"delta": "半"}
        raise ConnectionError("对端断开")

    with pytest.raises(ConnectionError):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=dies_midstream, ledger_path=lp, retries=3,
             sleeper=lambda s: pytest.fail("不该 sleep"))
    rows = [json.loads(x) for x in lp.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["partial"] is True and rows[0]["estimated"] is True
    assert rows[0]["completion_tokens"] == 2      # 两个 delta
    assert rows[0]["reasoning_tokens"] == 1
    assert rows[0]["prompt_tokens"] == -1


def test_started_stream_is_not_retried(tmp_path):
    """② 已经开始吐字的流不因中途一次读超时就整体重试——重试会丢弃已收到的 CoT
    并整段重来、重复消耗计费 token（彩野测试单次输入约 2.1 万）。只有「一个 delta
    都还没产出」的失败才重试（那正是远端长思考被误杀的场景）。"""
    calls = []

    def dies_after_delta(url, headers, payload):
        calls.append(1)
        yield "response.output_text.delta", {"delta": "半"}
        raise TimeoutError("read timed out")

    with pytest.raises(TimeoutError):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=dies_after_delta, ledger_path=tmp_path / "l.jsonl",
             retries=3, sleeper=lambda s: pytest.fail("不该 sleep"))
    assert len(calls) == 1                    # 明明可重试的错误类型，但没重试


def test_timeout_before_any_delta_is_retried(tmp_path):
    """②的另一半：首个 delta 之前超时（＝远端还在 prefill/长思考）**要**重试。"""
    calls = []
    sleeps = []

    def slow_start(url, headers, payload):
        calls.append(1)
        if len(calls) == 1:
            yield "response.created", {"response": {}}
            raise TimeoutError("read timed out")
        yield from _events()

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=slow_start, ledger_path=tmp_path / "l.jsonl",
             sleeper=sleeps.append)
    assert r["content"] == "回答内容"
    assert len(calls) == 2 and sleeps == [2]


def test_429_honours_retry_after_header(tmp_path):
    """④ 429 优先读 Retry-After 响应头，没有才回退指数退避。"""
    calls = []
    sleeps = []

    def limited(url, headers, payload):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                url, 429, "Too Many Requests", {"Retry-After": "37"}, None)
        return _events()

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=limited, ledger_path=tmp_path / "l.jsonl",
             sleeper=sleeps.append)
    assert r["content"] == "回答内容"
    assert sleeps == [37.0]                   # 听远端的，不是退避的 2s


def test_429_without_retry_after_falls_back_to_backoff(tmp_path):
    calls = []
    sleeps = []

    def limited(url, headers, payload):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        return _events()

    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         stream_transport=limited, ledger_path=tmp_path / "l.jsonl",
         sleeper=sleeps.append)
    assert sleeps == [2, 4]


def test_on_delta_callback_sees_reasoning_and_text(tmp_path):
    """CoT 可看：delta 回调按到达顺序收到 reasoning 与 text 两类增量。"""
    seen = []
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         stream_transport=_fake_transport, ledger_path=tmp_path / "l.jsonl",
         on_delta=lambda kind, t: seen.append((kind, t)))
    assert seen[0] == ("reasoning", "先看看文本里怎么说")
    assert [t for k, t in seen if k == "text"] == list("回答内容")
