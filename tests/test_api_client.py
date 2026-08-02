"""API 薄客户端：注入 transport 离线测试，零网络（P3 spec §5 里程碑 1）。"""
import json

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
