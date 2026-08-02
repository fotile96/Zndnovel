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


def test_ledger_records_effort(tmp_path):
    """台账缺口：上一轮 SEG-1 全跑（medium 档）的台账查不出档位，将来解释不了
    「为什么那次推理 token 少」。effort 现在与 cached_tokens/reasoning_tokens 同批
    写入；显式传档时台账如实记录该档，不是写死的 DEFAULT_EFFORT。"""
    lp = tmp_path / "l.jsonl"
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         stream_transport=_fake_transport, ledger_path=lp, purpose="u",
         effort="low")
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["effort"] == "low"


def test_dirty_summary_tolerates_rows_missing_effort_key():
    """`effort` 是本次新加的列，历史行（本字段加入之前写下的）没有它。
    汇总入口（ledger_token/summarize_ledger）按列名读取，旧行缺 `effort` 键不该
    让任何汇总炸掉——即便有人把 "effort" 传进 keys 也一样按缺键即未知处理
    （不是数值列，恒不可求和，但绝不能 KeyError）。"""
    from tools.api_client import ledger_token, summarize_ledger

    old = {"prompt_tokens": 10, "completion_tokens": 5}                 # 无 effort 键
    new = {"prompt_tokens": 20, "completion_tokens": 6,
           "cached_tokens": 0, "reasoning_tokens": 3, "effort": "max"}  # 有 effort 键

    assert ledger_token(old, "effort") is None   # 缺键：非数值/None，安全返回未知
    assert ledger_token(new, "effort") is None   # 字符串同样不是可求和的计数列

    s = summarize_ledger([old, new])  # 默认 LEDGER_TOKEN_KEYS 不含 effort，不受影响
    assert s["prompt_tokens"] == {"sum": 30, "n": 2, "unknown": 0}


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
    """真实 SSE 线格式（event: / data: / 空行分隔），用于验默认 transport 通路。

    事件序列照 2026-08-02 对 `https://api.deepseek.com/v1/responses` 的实测抄写：
    reasoning item 先完整走完一遍（output_item.added → content_part.added →
    delta* → done → content_part.done → output_item.done），然后才开第二个 item
    出正文。**保留这些 item/part 边界事件**——复评 I-2 指出，测试侧只造单 part 的
    裸 delta 正是「`.done` 覆盖而非追加」那个 bug 漏网的直接原因。"""
    def ev(t, d):
        return [f"event: {t}\n", f"data: {json.dumps(d, ensure_ascii=False)}\n", "\n"]
    out = []
    out += ev("response.created", {"type": "response.created", "response": {}})
    out += ev("response.in_progress", {"type": "response.in_progress", "response": {}})
    out += ev("response.output_item.added", {"item": {"type": "reasoning"}, "output_index": 0})
    out += ev("response.content_part.added", {"part": {"type": "reasoning_text", "text": ""},
                                              "output_index": 0})
    out += ev("response.reasoning_text.delta", {"delta": reasoning})
    out += ev("response.reasoning_text.done", {"text": reasoning})
    out += ev("response.content_part.done", {"part": {"type": "reasoning_text",
                                                      "text": reasoning}})
    out += ev("response.output_item.done", {"item": {"type": "reasoning"}, "output_index": 0})
    out += ev("response.output_item.added", {"item": {"type": "message"}, "output_index": 1})
    out += ev("response.content_part.added", {"part": {"type": "output_text", "text": ""},
                                              "output_index": 1})
    out += ev("response.output_text.delta", {"delta": text})
    out += ev("response.output_text.done", {"text": text})
    out += ev("response.content_part.done", {"part": {"type": "output_text", "text": text}})
    out += ev("response.output_item.done", {"item": {"type": "message"}, "output_index": 1})
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
    urlopen 的 socket 超时对流式响应本就是每次 read 各自计时）；max_tokens 未传时
    走 DEFAULT_MAX_OUTPUT_TOKENS（256K，实测 393,216 OK / 524,288 400，取比可行
    值保守一档），映射到 Responses 的 `max_output_tokens`（不是 chat/completions
    的 `max_tokens`）。"""
    from tools.api_client import DEFAULT_IDLE_TIMEOUT, DEFAULT_MAX_OUTPUT_TOKENS

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(_sse_lines())

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             ledger_path=tmp_path / "l.jsonl")
    assert captured["timeout"] == DEFAULT_IDLE_TIMEOUT
    assert captured["payload"]["max_output_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS
    assert DEFAULT_MAX_OUTPUT_TOKENS == 262144
    assert r["content"] == "ok" and r["cached_tokens"] == 2

    # 显式传值时以传入为准，不被默认值覆盖。
    captured.clear()
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l2.jsonl", max_tokens=999)
    assert captured["payload"]["max_output_tokens"] == 999


def test_default_effort_is_max(tmp_path, monkeypatch):
    """默认值闸（用户长期口径，2026-08-02）：effort 未指定时 payload 里
    `reasoning.effort == "max"`——除非调用方显式传别的档。"""
    from tools.api_client import DEFAULT_EFFORT

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(_sse_lines())

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl")
    assert DEFAULT_EFFORT == "max"
    assert captured["payload"]["reasoning"] == {"effort": "max"}


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


def test_timeout_before_any_delta_is_retried_and_is_ledgered(tmp_path):
    """②的另一半：首个 delta 之前超时（＝远端还在 prefill/长思考）**要**重试。

    复评 I-1：这条路径**同时**是①的重点——它是唯一会触发重试的路径，若入账门槛
    按「已吐出 delta」算，最该记账的失败反而永远零留痕。`response.created` 到了就
    证明远端已接受请求并开始 prefill，而彩野测试的成本主导项正是输入侧（约 2.35
    万 in vs 数百 out）。所以这里要连台账一起断言，不能只断言重试次数。"""
    calls = []
    sleeps = []
    lp = tmp_path / "l.jsonl"

    def slow_start(url, headers, payload):
        calls.append(1)
        if len(calls) == 1:
            yield "response.created", {"response": {}}
            raise TimeoutError("read timed out")
        yield from _events()

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=slow_start, ledger_path=lp, sleeper=sleeps.append)
    assert r["content"] == "回答内容"
    assert len(calls) == 2 and sleeps == [2]
    rows = [json.loads(x) for x in lp.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2                      # 失败那次 + 成功那次
    assert rows[0]["partial"] is True and rows[0]["attempt"] == 1
    assert rows[0]["estimated"] is True
    assert rows[0]["prompt_tokens"] == -1 and rows[0]["completion_tokens"] == 0
    assert "partial" not in rows[1] and rows[1]["prompt_tokens"] == 100


def test_zero_event_failure_is_not_ledgered(tmp_path):
    """入账门槛的另一侧：一个事件都没到（4xx / 连不上）不入账——那次确实没发生、
    也没计费。避免把 I-1 的修法修过头变成给每次连接失败都记一笔。"""
    lp = tmp_path / "l.jsonl"

    def nothing(url, headers, payload):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
        yield  # pragma: no cover - 让它是生成器

    with pytest.raises(urllib.error.HTTPError):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=nothing, ledger_path=lp, retries=0)
    assert not lp.exists() or lp.read_text(encoding="utf-8").strip() == ""


def test_estimated_flag_is_decoupled_from_partial(tmp_path):
    """复评顺手项①：终止事件到了但远端没下发 usage —— 这行不是 partial，却同样
    是估算值。不标 estimated 就会出现「prompt_tokens 是 -1 却看不出是估的」。"""
    lp = tmp_path / "l.jsonl"

    def no_usage(url, headers, payload):
        yield "response.output_text.delta", {"delta": "ok"}
        yield "response.output_text.done", {"text": "ok"}
        yield "response.completed", {"response": {}}      # usage 缺失

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=no_usage, ledger_path=lp)
    assert r["content"] == "ok" and r["prompt_tokens"] == -1
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["estimated"] is True
    assert "partial" not in row                # 不是部分失败，是完成但计数不全


def test_multiple_parts_are_concatenated_not_overwritten(tmp_path):
    """复评 I-2：一次响应可能有**多个** content part / output item（长推理常被拆
    成多段）。`.done` 必须追加而不是替换累加器——否则前面的段被静默丢弃，报告里
    拿到半截答案 + 半截 CoT，判分员照常打分，失败完全无声。"""
    def multi(url, headers, payload):
        yield "response.content_part.added", {"part": {"type": "reasoning_text"}}
        yield "response.reasoning_text.delta", {"delta": "AAA"}
        yield "response.reasoning_text.done", {"text": "AAA"}
        yield "response.content_part.added", {"part": {"type": "reasoning_text"}}
        yield "response.reasoning_text.delta", {"delta": "BBB"}
        yield "response.reasoning_text.done", {"text": "BBB"}
        yield "response.content_part.added", {"part": {"type": "output_text"}}
        yield "response.output_text.delta", {"delta": "111"}
        yield "response.output_text.done", {"text": "111"}
        yield "response.content_part.added", {"part": {"type": "output_text"}}
        yield "response.output_text.delta", {"delta": "222"}
        yield "response.output_text.done", {"text": "222"}
        yield "response.completed", {"response": {"usage": {"input_tokens": 1,
                                                            "output_tokens": 1}}}

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=multi, ledger_path=tmp_path / "l.jsonl")
    assert r["content"] == "111222"
    assert r["reasoning_text"] == "AAABBB"


def test_part_without_done_is_not_lost_when_next_part_starts(tmp_path):
    """同上的边角：某一段没等到 `.done` 就换段时，缓冲要先收进已完成列表，不能被
    下一段的 delta 冲掉。"""
    def sloppy(url, headers, payload):
        yield "response.content_part.added", {"part": {"type": "output_text"}}
        yield "response.output_text.delta", {"delta": "前"}
        yield "response.content_part.added", {"part": {"type": "output_text"}}
        yield "response.output_text.delta", {"delta": "后"}
        yield "response.completed", {"response": {"usage": {}}}

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=sloppy, ledger_path=tmp_path / "l.jsonl")
    assert r["content"] == "前后"


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


def test_ledger_token_and_summary_tolerate_dirty_rows():
    """终审 M7：`data/api_ledger.jsonl` 是 append-only 历史账本，混着两种行形态
    （Responses 改造前的 6 行没有 cached/reasoning 两列）与 -1 哨兵（远端没下发
    usage）。历史行不改，消费侧靠这两个函数安全汇总：缺键与负哨兵都当「未知」，
    不参与求和、单独计数；真实的 0 仍算已知值。"""
    from tools.api_client import ledger_token, summarize_ledger

    old = {"prompt_tokens": 87, "completion_tokens": 24}                  # 缺两列
    new = {"prompt_tokens": 100, "completion_tokens": 10,
           "cached_tokens": 0, "reasoning_tokens": 12}                    # 0 是真值
    est = {"prompt_tokens": -1, "completion_tokens": 5,
           "cached_tokens": -1, "reasoning_tokens": 5, "estimated": True}  # 哨兵

    assert ledger_token(old, "cached_tokens") is None      # 缺键不 KeyError
    assert ledger_token(est, "prompt_tokens") is None      # 哨兵不当 0、更不当 -1
    assert ledger_token(new, "cached_tokens") == 0         # 真 0 是已知值
    assert ledger_token({"prompt_tokens": True}, "prompt_tokens") is None  # bool 不是计数

    s = summarize_ledger([old, new, est])
    assert s["prompt_tokens"] == {"sum": 187, "n": 2, "unknown": 1}
    assert s["cached_tokens"] == {"sum": 0, "n": 1, "unknown": 2}
    assert s["reasoning_tokens"] == {"sum": 17, "n": 2, "unknown": 1}
    # 朴素 sum() 会把哨兵减掉：这正是本函数要挡住的静默低估
    assert sum(r.get("prompt_tokens", 0) for r in [old, new, est]) == 186


def test_summarize_real_repo_ledger_has_both_row_shapes():
    """数据闸：仓库现行台账确实混着两种形态（否则本测试就是同义反复）。
    只读，不改历史行。"""
    import json
    from tools.api_client import REPO, summarize_ledger

    p = REPO / "data" / "api_ledger.jsonl"
    if not p.exists():
        return
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert any("cached_tokens" not in r for r in rows), "缺键行没了，本用例可退休"
    s = summarize_ledger(rows)
    assert s["prompt_tokens"]["n"] + s["prompt_tokens"]["unknown"] == len(rows)
    assert s["cached_tokens"]["unknown"] >= 1


# ---------------------------------------------- function tools（守卫收紧非删除）

def _events_with_tool_call(call_id="call_00_zpQBBijfbGNniXO4rgfM2256",
                           item_id="ff61a12a-18a2-4793-8510-7c285157ef61",
                           name="get_lines", arguments='{"ids": [11]}'):
    """带 function_call 的事件序列——**字段名与顺序照 2026-08-02 真实探针抄写**
    （probe：POST /v1/responses + tools=[{type:function,...}]，见 task-2-report.md）。

    实测要点：function_call 项走 `response.output_item.added`（item 里已带
    `call_id`/`name`，`arguments` 初值为空串）→ `response.function_call_arguments
    .delta`* → `.done`（带完整 arguments **字符串**）→ `response.output_item.done`
    （item 带完整 arguments），终止事件的 `response.output` 里同样有这一项。
    注意 function_call **不发 content_part 事件**，且 `arguments` 是 JSON 字符串
    不是对象——解析侧不能想当然当 dict 用。"""
    fc_partial = {"type": "function_call", "id": item_id, "status": "in_progress",
                  "arguments": "", "call_id": call_id, "name": name}
    fc_done = {"type": "function_call", "id": item_id, "status": "completed",
               "arguments": arguments, "call_id": call_id, "name": name}
    reasoning = {"type": "reasoning", "id": "1cbd9161", "status": "completed",
                 "content": [{"type": "reasoning_text", "text": "查一下"}], "summary": []}
    yield "response.created", {"type": "response.created", "response": {}}
    yield "response.in_progress", {"type": "response.in_progress", "response": {}}
    yield "response.output_item.added", {"item": {"type": "reasoning"}, "output_index": 0}
    yield "response.content_part.added", {"part": {"type": "reasoning_text", "text": ""}}
    yield "response.reasoning_text.delta", {"delta": "查一下"}
    yield "response.reasoning_text.done", {"text": "查一下"}
    yield "response.content_part.done", {"part": {"type": "reasoning_text", "text": "查一下"}}
    yield "response.output_item.done", {"item": reasoning, "output_index": 0}
    yield "response.output_item.added", {"item": fc_partial, "output_index": 1}
    for ch in arguments:
        yield "response.function_call_arguments.delta", {"delta": ch, "item_id": item_id,
                                                         "output_index": 1}
    yield "response.function_call_arguments.done", {"arguments": arguments,
                                                    "item_id": item_id, "output_index": 1}
    yield "response.output_item.done", {"item": fc_done, "output_index": 1}
    yield "response.completed", {"response": {
        "output": [reasoning, fc_done],
        "usage": {"input_tokens": 393, "input_tokens_details": {"cached_tokens": 384},
                  "output_tokens": 71, "output_tokens_details": {"reasoning_tokens": 25}}}}


def test_tools_are_sent_when_whitelisted(tmp_path):
    """白名单内的 function 工具照发；返回值把 output_items / function_calls 透出。
    ⚠ 原始 JSON 串里仍不得出现 web_search（那条防线不因本功能松动）。"""
    captured = {}

    def fake_transport(url, headers, payload):
        captured["payload"] = payload
        captured["raw"] = json.dumps(payload, ensure_ascii=False)
        return _events_with_tool_call()

    tools = [{"type": "function", "name": "get_lines", "description": "d",
              "parameters": {"type": "object", "properties": {}}}]
    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=fake_transport, ledger_path=tmp_path / "l.jsonl",
             tools=tools, allowed_tool_names={"get_lines"})
    assert captured["payload"]["tools"] == tools
    assert "web_search" not in captured["raw"]
    # 实测字段名：call_id（不是 id——id 是 item 自身的标识）、name、arguments 为字符串
    assert [it["type"] for it in r["output_items"]] == ["reasoning", "function_call"]
    assert len(r["function_calls"]) == 1
    fc = r["function_calls"][0]
    assert fc["name"] == "get_lines"
    assert fc["call_id"].startswith("call_")
    assert json.loads(fc["arguments"]) == {"ids": [11]}


def test_non_function_tool_type_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="function"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=lambda *a: iter(()), ledger_path=tmp_path / "l.jsonl",
             tools=[{"type": "web_search"}], allowed_tool_names={"get_lines"})


def test_tool_name_outside_whitelist_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="白名单"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=lambda *a: iter(()), ledger_path=tmp_path / "l.jsonl",
             tools=[{"type": "function", "name": "rm_rf",
                     "parameters": {"type": "object", "properties": {}}}],
             allowed_tool_names={"get_lines"})


def test_tools_require_explicit_whitelist(tmp_path):
    """不给白名单就传 tools —— 拒绝。防止「忘了传白名单」变成事实上的无限制。"""
    with pytest.raises(SystemExit, match="白名单"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=lambda *a: iter(()), ledger_path=tmp_path / "l.jsonl",
             tools=[{"type": "function", "name": "get_lines",
                     "parameters": {"type": "object", "properties": {}}}])
