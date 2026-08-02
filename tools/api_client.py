"""外部 API 薄客户端（P3 spec §5 里程碑 1）：deepseek 首连，OpenAI 兼容 chat/completions。
纯 stdlib（urllib）；key 取环境变量 DEEPSEEK_API_KEY 或仓库根 .env（已 gitignore，
绝不入库）；每次调用向 data/api_ledger.jsonl 追加一行计费台账（token 计数为准，
换算金额留给人看账时按当日价目做）。transport 可注入以便离线测试。
提供商无关的扩展点是 PROVIDERS 表——加第二家只需加一条记录。"""
import functools
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

PROVIDERS = {
    "deepseek": {"url": "https://api.deepseek.com/chat/completions",
                 "key_env": "DEEPSEEK_API_KEY",
                 "default_model": "deepseek-chat"},
}

# 长上下文请求（整段前缀+正文喂给外部模型）可能久等不返回，超时从宽；
# 彩野测试一跑是若干题 × 2 次调用，任何一次瞬时失败就整跑作废，故加重试。
DEFAULT_TIMEOUT = 600
DEFAULT_RETRIES = 3


def _is_retryable(exc: Exception) -> bool:
    """只重试网络类错误与 5xx/429；4xx（鉴权错/模型名错/请求格式错）立即失败——
    重试一个写错的请求毫无意义还浪费时间（指数退避最长可攒到 2+4+8=14s）。"""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code == 429
    if isinstance(exc, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)):
        return True
    return False


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


def _http_transport(url, headers, payload, *, timeout=DEFAULT_TIMEOUT):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(messages, *, provider="deepseek", model=None, temperature=0.2,
         max_tokens=4096, purpose="", transport=None, ledger_path=None,
         api_key=None, timeout=None, retries=None, sleeper=None) -> dict:
    cfg = PROVIDERS[provider]
    model = model or cfg["default_model"]
    key = api_key or os.environ.get(cfg["key_env"]) or load_env().get(cfg["key_env"])
    if not key:
        raise SystemExit(
            f"缺 {cfg['key_env']}：设环境变量，或写进仓库根 .env（已 gitignore）")
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    retries = DEFAULT_RETRIES if retries is None else retries
    sleep_fn = sleeper or time.sleep
    # transport 仍只收三参（url, headers, payload）——保持既有注入契约不变；
    # 走默认 transport 时用 functools.partial 把 timeout 通过闭包塞给
    # _http_transport，不改注入签名。
    transport_fn = transport if transport is not None else \
        functools.partial(_http_transport, timeout=timeout)

    delay = 2
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = transport_fn(cfg["url"], headers, payload)
            break
        except Exception as exc:
            retryable = _is_retryable(exc)
            if not retryable or attempt > retries:
                reason = "不重试：非可重试错误" if not retryable else f"已达重试上限（{retries}）"
                print(f"[api_client] 第 {attempt} 次尝试失败，{reason}：{exc}",
                      file=sys.stderr)
                raise
            print(f"[api_client] 第 {attempt} 次尝试失败，{delay}s 后重试：{exc}",
                  file=sys.stderr)
            sleep_fn(delay)
            delay *= 2
    if attempt > 1:
        print(f"[api_client] 第 {attempt} 次尝试后成功", file=sys.stderr)
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
    ap.add_argument("--timeout", type=int, default=None,
                     help=f"秒，默认 {DEFAULT_TIMEOUT}（长上下文请求从宽）")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--retries", type=int, default=None,
                     help=f"默认 {DEFAULT_RETRIES}")
    a = ap.parse_args(argv)
    r = chat([{"role": "user", "content": a.prompt}], provider=a.provider,
             model=a.model, purpose=a.purpose, timeout=a.timeout,
             max_tokens=a.max_tokens, retries=a.retries)
    print(r["content"])
    print(f"[{r['provider']}/{r['model']} tokens {r['prompt_tokens']}+{r['completion_tokens']}]",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
