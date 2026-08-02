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
