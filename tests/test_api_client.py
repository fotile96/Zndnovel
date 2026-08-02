"""API 薄客户端：注入 transport 离线测试，零网络（P3 spec §5 里程碑 1）。"""
import json
import urllib.error

import pytest

from tools.api_client import chat, load_env


def _fake_transport(url, headers, payload):
    assert url.startswith("https://api.deepseek.com")
    assert headers["Authorization"] == "Bearer sk-test"
    assert payload["model"] == "deepseek-chat"
    return {"choices": [{"message": {"content": "回答内容"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}}


def test_chat_returns_content_and_writes_ledger(tmp_path):
    lp = tmp_path / "api_ledger.jsonl"
    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             transport=_fake_transport, ledger_path=lp, purpose="unit-test")
    assert r["content"] == "回答内容"
    assert r["prompt_tokens"] == 100 and r["completion_tokens"] == 20
    row = json.loads(lp.read_text(encoding="utf-8").splitlines()[0])
    assert row["purpose"] == "unit-test" and row["provider"] == "deepseek"
    assert row["prompt_tokens"] == 100


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
        return {"choices": [{"message": {"content": "回答内容"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    r = chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             transport=flaky_transport, ledger_path=tmp_path / "l.jsonl",
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
             transport=bad_request_transport, ledger_path=tmp_path / "l.jsonl",
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
             transport=always_fails, ledger_path=tmp_path / "l.jsonl",
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
             transport=always_fails, ledger_path=tmp_path / "l.jsonl",
             retries=0, sleeper=lambda s: pytest.fail("不该 sleep"))
    assert len(calls) == 1


def test_default_transport_receives_configured_timeout(tmp_path, monkeypatch):
    captured = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}], "usage": {}}
            ).encode("utf-8")

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return FakeResp()

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl", timeout=12)
    assert captured["timeout"] == 12


def test_default_timeout_and_max_tokens_when_unset(tmp_path, monkeypatch):
    from tools.api_client import DEFAULT_TIMEOUT

    captured = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}], "usage": {}}
            ).encode("utf-8")

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResp()

    monkeypatch.setattr("tools.api_client.urllib.request.urlopen", fake_urlopen)
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         ledger_path=tmp_path / "l.jsonl")
    assert captured["timeout"] == DEFAULT_TIMEOUT
    assert captured["payload"]["max_tokens"] == 4096
