### Task 6: API 薄客户端 `tools/api_client.py`（deepseek）

**Files:**
- Create: `tools/api_client.py`
- Test: `tests/test_api_client.py`

**Interfaces:**
- Consumes: 环境变量/`.env` 的 `DEEPSEEK_API_KEY`（`.env` 已 gitignore，`:9-10`）；deepseek OpenAI 兼容端点 `https://api.deepseek.com/chat/completions`。
- Produces: `load_env(path=None) -> dict`（解析仓库根 `.env`）；`chat(messages, *, provider="deepseek", model=None, temperature=0.2, max_tokens=2048, purpose="", transport=None, ledger_path=None, api_key=None) -> {content, prompt_tokens, completion_tokens, model, provider}`——`transport` 可注入（签名 `transport(url, headers, payload) -> resp_dict`，单测零网络）；每次调用向 `data/api_ledger.jsonl`（或 `ledger_path`）追加一行 `{ts, provider, model, purpose, prompt_tokens, completion_tokens}` 计费台账。Task 7 消费 `chat`。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_api_client.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_api_client.py -v` → FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

写入 `tools/api_client.py`：

```python
"""外部 API 薄客户端（P3 spec §5 里程碑 1）：deepseek 首连，OpenAI 兼容 chat/completions。
纯 stdlib（urllib）；key 取环境变量 DEEPSEEK_API_KEY 或仓库根 .env（已 gitignore，
绝不入库）；每次调用向 data/api_ledger.jsonl 追加一行计费台账（token 计数为准，
换算金额留给人看账时按当日价目做）。transport 可注入以便离线测试。
提供商无关的扩展点是 PROVIDERS 表——加第二家只需加一条记录。"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

PROVIDERS = {
    "deepseek": {"url": "https://api.deepseek.com/chat/completions",
                 "key_env": "DEEPSEEK_API_KEY",
                 "default_model": "deepseek-chat"},
}


def load_env(path=None) -> dict:
    p = Path(path) if path else REPO / ".env"
    env = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _http_transport(url, headers, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(messages, *, provider="deepseek", model=None, temperature=0.2,
         max_tokens=2048, purpose="", transport=None, ledger_path=None,
         api_key=None) -> dict:
    cfg = PROVIDERS[provider]
    model = model or cfg["default_model"]
    key = api_key or os.environ.get(cfg["key_env"]) or load_env().get(cfg["key_env"])
    if not key:
        raise SystemExit(
            f"缺 {cfg['key_env']}：设环境变量，或写进仓库根 .env（已 gitignore）")
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    resp = (transport or _http_transport)(cfg["url"], headers, payload)
    usage = resp.get("usage", {})
    out = {"content": resp["choices"][0]["message"]["content"],
           "prompt_tokens": usage.get("prompt_tokens", -1),
           "completion_tokens": usage.get("completion_tokens", -1),
           "model": model, "provider": provider}
    lp = Path(ledger_path) if ledger_path else REPO / "data" / "api_ledger.jsonl"
    with open(lp, "a", encoding="utf-8") as f:
        f.write(json.dumps(
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "provider": provider,
             "model": model, "purpose": purpose,
             "prompt_tokens": out["prompt_tokens"],
             "completion_tokens": out["completion_tokens"]},
            ensure_ascii=False) + "\n")
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--provider", default="deepseek")
    ap.add_argument("--model")
    ap.add_argument("--purpose", default="cli-smoke")
    a = ap.parse_args(argv)
    r = chat([{"role": "user", "content": a.prompt}], provider=a.provider,
             model=a.model, purpose=a.purpose)
    print(r["content"])
    print(f"[{r['provider']}/{r['model']} tokens {r['prompt_tokens']}+{r['completion_tokens']}]",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

注意：`chat` 缺 key 是 `SystemExit`（不是静默降级）；`test_missing_key_exits_with_guidance` 用 monkeypatch 挡住真实 `.env`——本机可能已有 key，测试不得依赖也不得读它。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_api_client.py -v` → 3 passed。

- [ ] **Step 5: 全量测试 + commit**

Run: `uv run pytest -q` → 254 passed。

```bash
git add tools/api_client.py tests/test_api_client.py
git commit -m "feat: API 薄客户端（deepseek/stdlib/可注入 transport/计费台账）"
```

---

