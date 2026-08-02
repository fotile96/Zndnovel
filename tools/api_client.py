"""外部 API 薄客户端（P3 spec §5 里程碑 1）：deepseek **Responses API 流式调用**。

为什么是 Responses + 流式（不是 OpenAI 兼容的 chat/completions）：
1. **CoT 可看**——Responses 会以 `response.reasoning_text.delta` 事件把推理过程
   逐字流下来。对「彩野测试」（让外部模型扮演只靠梗概续听故事的读者答剧情理解
   题）尤其有价值：能看见受试者是**真从译文里读出来的**还是猜的，而这正是我们
   想判别的东西。
2. **抗超时鲁棒性**（主因）——远端长思考时，流式 CoT 持续下行让连接一直有数据
   到达，从根本上避免被各种 timeout 机制误杀。这比把超时数字调大对症得多。
   因此**必须真的走流式**：非流式地调 Responses API 拿不到第 2 条好处。

**模型限制**：deepseek 的 Responses API 目前**只支持 `deepseek-v4-flash`**
（实测 2026-08-02：`deepseek-v4-pro` 返回 400「Codex integration with
deepseek-v4-pro will be available starting early August 2026」）。将来若想给
判分换更强的模型，Responses 侧可能还没有——那时要么等 v4-pro 开放，要么单独为
判分保留一条 chat/completions 通路（git 历史里有旧实现）。

纯 stdlib（urllib + 手写 SSE 解析）；key 取环境变量 DEEPSEEK_API_KEY 或仓库根
.env（已 gitignore，绝不入库）；每次调用向 data/api_ledger.jsonl 追加一行计费
台账（含 cached_tokens / reasoning_tokens——缓存是否命中直接决定成本差一个量级）。
`stream_transport` 可注入以便离线测试。
提供商无关的扩展点是 PROVIDERS 表——加第二家只需加一条记录。
"""
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
    # 端点路径实测确认（2026-08-02）：文档只写了 base_url `https://api.deepseek.com`，
    # 没写路径。实测 `/v1/responses` 与 `/responses` **两条都返回 200 且 SSE 事件
    # 序列完全一致**；取 `/v1/responses`——与 OpenAI Responses 惯例一致，将来换
    # SDK / 换供应商时不用改。
    "deepseek": {"url": "https://api.deepseek.com/v1/responses",
                 "key_env": "DEEPSEEK_API_KEY",
                 # Responses API 现阶段只认这个模型（见模块 docstring）。
                 "default_model": "deepseek-v4-flash"},
}

# **逐 chunk 静默超时**（不是整次请求的总时长上限）。
# `urlopen(req, timeout=T)` 设的是底层 socket 超时：http.client 把 T 交给
# `socket.settimeout()`，而 socket 超时的语义是「**单次** recv 等待上限」——对
# 流式响应来说每次 read 各自重新计时。所以这个参数天然就是 idle timeout：只要
# 远端持续吐字节（哪怕吐的是 CoT）就永远不会触发，只有真断流／远端长时间一声不吭
# 才触发。这正是本次改造要的语义，不需要额外的看门狗线程。
# 取值理由：门槛量级是「**单次事件间隔**」而非「总时长」。稳定吐字时事件间隔是
# 毫秒级；实际最长的一次静默是「请求发出 → 首个 response.created」之间的远端
# prefill（彩野测试单次 prompt 约 2.1 万 token），量级几十秒。120s 给它留了数倍
# 余量，同时把「连接已死」的检出时间从旧的 600s 压到 2 分钟。
DEFAULT_IDLE_TIMEOUT = 120
DEFAULT_RETRIES = 3
# reasoning.effort 合法取值（实测 400 报文列举）：
# none / minimal / low / medium / high / xhigh / max。
# 默认取 medium：彩野测试要看 CoT 是"读出来的还是猜的"，需要有实质推理内容，
# 但又不该为此把 reasoning_tokens（计费的输出 token）烧到 high/max 的量级。
DEFAULT_EFFORT = "medium"

# 终止事件的 data 里带完整 response 与 usage。
TERMINAL_EVENTS = {"response.completed", "response.incomplete", "response.failed"}


class StreamAborted(RuntimeError):
    """流在终止事件到达之前断掉（或远端回了 response.failed）。

    带上本次已经收到的部分内容与 token 估算，供调用方/台账使用。"""

    def __init__(self, message, *, partial):
        super().__init__(message)
        self.partial = partial


def _is_retryable(exc: Exception) -> bool:
    """只重试网络类错误与 5xx/429；4xx（鉴权错/模型名错/请求格式错）立即失败——
    重试一个写错的请求毫无意义还浪费时间。注意这只判「错误类型可不可重试」，
    「这次流已经吐过字了要不要重试」是另一层判断，见 chat() 的重试循环。"""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code == 429
    if isinstance(exc, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, StreamAborted):
        return True
    return False


def _retry_after(exc: Exception):
    """429 优先读 `Retry-After` 响应头（秒数或 HTTP-date，只支持秒数形式——
    deepseek 用的是秒数）；读不到返回 None，由调用方回退指数退避。"""
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


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


def iter_sse_events(lines):
    """把 SSE 行流解析成 `(event_type, data_dict)` 迭代器。

    线格式：`event: <type>\\n` + `data: <json>\\n` + 空行分隔。规范允许 data 跨多
    行（拼接时用 `\\n`）、允许 `:` 开头的注释行、允许字段值前有一个可选空格。
    `data: [DONE]`（OpenAI 系惯例的收尾哨兵）直接跳过。data 不是合法 JSON 时给
    空 dict 而不是炸掉——半行/心跳不该让整次调用失败。
    没有 `event:` 行时回退用 data 里的 `type` 字段（Responses 的 data 自带 type）。
    """
    event_type = None
    data_buf = []

    def flush():
        nonlocal event_type, data_buf
        if data_buf:
            payload = "\n".join(data_buf)
            if payload.strip() != "[DONE]":
                try:
                    data = json.loads(payload)
                except (json.JSONDecodeError, ValueError):
                    data = {}
                if not isinstance(data, dict):
                    data = {}
                yield_me = (event_type or data.get("type", ""), data)
            else:
                yield_me = None
        else:
            yield_me = None
        event_type, data_buf = None, []
        return yield_me

    for raw in lines:
        line = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else raw
        line = line.rstrip("\n").rstrip("\r")
        if line == "":
            hit = flush()
            if hit is not None:
                yield hit
            continue
        if line.startswith(":"):          # 注释/心跳行
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_type = value
        elif field == "data":
            data_buf.append(value)
    hit = flush()                          # 末尾没有空行收尾时也要吐出来
    if hit is not None:
        yield hit


def _http_stream_transport(url, headers, payload, *, timeout=DEFAULT_IDLE_TIMEOUT):
    """默认流式 transport：POST + SSE，逐事件 yield `(event_type, data)`。

    注入点签名 `stream_transport(url, headers, payload) -> Iterable[(str, dict)]`
    ——与旧的 `transport(url, headers, payload) -> dict` **不是同一个参数**：那个
    是「一次调用→一次完整 dict」的同步语义，与流式天然不匹配，不该被超载。

    `timeout` 是逐 chunk 静默超时，理由见 DEFAULT_IDLE_TIMEOUT 注释。
    """
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    resp = urllib.request.urlopen(req, timeout=timeout)
    with resp:
        yield from iter_sse_events(resp)


def _split_messages(messages):
    """`[{role, content}]` → `(instructions, input)`。

    Responses API 的字段名与 chat/completions 不同：system 提示走顶层
    `instructions`，对话轮次走 `input`（可以是字符串，也可以是 role/content 数组
    ——实测数组形式多轮上下文正常生效）。多条 system 消息按出现顺序拼接。"""
    sys_parts, turns = [], []
    for m in messages:
        if m.get("role") == "system":
            sys_parts.append(m.get("content", ""))
        else:
            turns.append({"role": m.get("role", "user"), "content": m.get("content", "")})
    return "\n\n".join(p for p in sys_parts if p), turns


def _consume(events, on_delta=None):
    """消费事件流，返回本次尝试的进度快照 dict。

    正常收尾要求见到 TERMINAL_EVENTS 之一；否则抛 StreamAborted（带进度快照）。
    """
    prog = {"text": [], "reasoning": [], "text_deltas": 0, "reasoning_deltas": 0,
            "usage": None, "status": None, "event_types": []}
    try:
        for etype, data in events:
            prog["event_types"].append(etype)
            if etype == "response.output_text.delta":
                d = data.get("delta", "")
                prog["text"].append(d)
                prog["text_deltas"] += 1
                if on_delta:
                    on_delta("text", d)
            elif etype == "response.reasoning_text.delta":
                d = data.get("delta", "")
                prog["reasoning"].append(d)
                prog["reasoning_deltas"] += 1
                if on_delta:
                    on_delta("reasoning", d)
            elif etype == "response.output_text.done":
                # .done 带完整 text——以它为准，防 delta 漏拼。
                prog["text"] = [data.get("text", "".join(prog["text"]))]
            elif etype == "response.reasoning_text.done":
                prog["reasoning"] = [data.get("text", "".join(prog["reasoning"]))]
            elif etype in TERMINAL_EVENTS:
                resp = data.get("response") or {}
                prog["usage"] = resp.get("usage") or {}
                prog["status"] = etype
                break
    except Exception as exc:
        # 中途炸掉（读超时/连接重置/远端 5xx）：把已收到的进度挂到原异常上再抛，
        # 好让 chat() 既能按**原始异常类型**判可重试性，又能拿到部分 token 记账。
        exc.partial = prog
        raise
    if prog["status"] is None:
        raise StreamAborted("流在终止事件到达前结束（未收到 response.completed/"
                            "incomplete/failed）", partial=prog)
    if prog["status"] == "response.failed":
        raise StreamAborted(f"远端返回 response.failed：{json.dumps(prog['usage'], ensure_ascii=False)}",
                            partial=prog)
    return prog


def _usage_of(prog):
    """从进度快照抽 token 四元组。终止事件没到达时 usage 是 None——此时输出侧用
    **delta 事件计数**做估算（deepseek 基本一事件一 token），输入侧无从得知，记
    -1；台账行会带 partial 标记说明这是「已发生且已计费、但计数不全」的一次。"""
    u = prog.get("usage")
    if u:
        return {"prompt_tokens": u.get("input_tokens", -1),
                "completion_tokens": u.get("output_tokens", -1),
                "cached_tokens": (u.get("input_tokens_details") or {}).get("cached_tokens", -1),
                "reasoning_tokens": (u.get("output_tokens_details") or {}).get("reasoning_tokens", -1),
                "estimated": False}
    return {"prompt_tokens": -1,
            "completion_tokens": prog["text_deltas"] + prog["reasoning_deltas"],
            "cached_tokens": -1,
            "reasoning_tokens": prog["reasoning_deltas"],
            "estimated": True}


def _write_ledger(lp, *, provider, model, purpose, usage, partial=False, attempt=1):
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "provider": provider,
           "model": model, "purpose": purpose,
           "prompt_tokens": usage["prompt_tokens"],
           "completion_tokens": usage["completion_tokens"],
           "cached_tokens": usage["cached_tokens"],
           "reasoning_tokens": usage["reasoning_tokens"]}
    if partial:
        # 失败的尝试也要入账：流式重试意味着丢弃已收到的部分 CoT 并整段重来，
        # 那些 token 是真金白银花掉的；不记就会系统性低估实际花费。
        row["partial"] = True
        row["attempt"] = attempt
        if usage["estimated"]:
            row["estimated"] = True
    with open(lp, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def chat(messages, *, provider="deepseek", model=None, temperature=0.2,
         max_tokens=4096, purpose="", stream_transport=None, ledger_path=None,
         api_key=None, timeout=None, retries=None, sleeper=None,
         effort=DEFAULT_EFFORT, on_delta=None) -> dict:
    """对外契约与旧的 chat/completions 版**保持不变**：入参 `messages` 仍是
    `[{role, content}]`，返回 dict 的 `content`/`prompt_tokens`/`completion_tokens`
    /`model`/`provider` 语义与名字都不变（`prompt_tokens` ← `usage.input_tokens`，
    `completion_tokens` ← `usage.output_tokens`）。**新增** `reasoning_text`、
    `cached_tokens`、`reasoning_tokens` 三个键。

    `timeout` 现在是**逐 chunk 静默超时**（默认 DEFAULT_IDLE_TIMEOUT），不再是
    整次请求的总时长上限——参数名沿用是为了不动调用方，语义见常量注释。
    `on_delta(kind, text)` 可选回调，kind ∈ {"text", "reasoning"}，用于实时打印。
    """
    cfg = PROVIDERS[provider]
    model = model or cfg["default_model"]
    key = api_key or os.environ.get(cfg["key_env"]) or load_env().get(cfg["key_env"])
    if not key:
        raise SystemExit(
            f"缺 {cfg['key_env']}：设环境变量，或写进仓库根 .env（已 gitignore）")
    instructions, input_turns = _split_messages(messages)
    # ⚠ 绝不发送 `tools` 字段。Responses API 内置服务端 web_search——在彩野测试里
    # 一旦启用即灾难：受试模型可以直接上网查《セカンドノベル》的剧情，不看译文也
    # 能答对，测试静默失效（与本轮踩过的「恒绿关卡」是同一类病）。
    # tests/test_api_client.py 有一条断言守着 payload 里没有 tools/web_search。
    payload = {"model": model, "input": input_turns, "stream": True,
               "max_output_tokens": max_tokens, "temperature": temperature,
               "reasoning": {"effort": effort}}
    if instructions:
        payload["instructions"] = instructions
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    timeout = DEFAULT_IDLE_TIMEOUT if timeout is None else timeout
    retries = DEFAULT_RETRIES if retries is None else retries
    sleep_fn = sleeper or time.sleep
    transport_fn = stream_transport if stream_transport is not None else \
        functools.partial(_http_stream_transport, timeout=timeout)
    lp = Path(ledger_path) if ledger_path else REPO / "data" / "api_ledger.jsonl"

    delay = 2
    attempt = 0
    while True:
        attempt += 1
        try:
            prog = _consume(transport_fn(cfg["url"], headers, payload), on_delta=on_delta)
            break
        except Exception as exc:
            partial = getattr(exc, "partial", None)
            produced = 0
            if partial is not None:
                produced = partial["text_deltas"] + partial["reasoning_deltas"]
                # ① 已产生的部分 token 先记账，再决定重不重试。一个字节都没回来的
                #    失败（4xx/连不上）不入账——那次没有产出、也没有计费。
                if produced or partial["usage"]:
                    _write_ledger(lp, provider=provider, model=model, purpose=purpose,
                                  usage=_usage_of(partial), partial=True, attempt=attempt)
            retryable = _is_retryable(exc)
            # ② 已经开始吐字的流不整体重试：重试要丢弃已收到的部分 CoT 并整段
            #    重来，重复消耗计费 token（彩野测试单次输入约 2.1 万 token）。而
            #    「远端长思考被误杀」这个我们真正想救的场景发生在**首个 delta 之
            #    前**——一旦稳定吐字，静默超时（120s）远大于事件间隔，此时再超时
            #    就是连接真死了，重来一遍只会再烧一次钱。故只重试「尚未产出任何
            #    delta」的失败。
            if retryable and produced > 0:
                retryable = False
                reason = f"不重试：本次流已产出 {produced} 个 delta（重试会整段重来并重复计费）"
            elif not retryable:
                reason = "不重试：非可重试错误"
            else:
                reason = f"已达重试上限（{retries}）"
            if not retryable or attempt > retries:
                print(f"[api_client] 第 {attempt} 次尝试失败，{reason}：{exc}",
                      file=sys.stderr)
                raise
            # ④ 429 优先听远端的 Retry-After，读不到才回退指数退避。
            wait = _retry_after(exc)
            src = "Retry-After" if wait is not None else "指数退避"
            if wait is None:
                wait = delay
                delay *= 2
            print(f"[api_client] 第 {attempt} 次尝试失败，{wait}s 后重试（{src}）：{exc}",
                  file=sys.stderr)
            sleep_fn(wait)
    if attempt > 1:
        print(f"[api_client] 第 {attempt} 次尝试后成功", file=sys.stderr)
    if prog["status"] == "response.incomplete":
        print("[api_client] ⚠ response.incomplete：输出被截断（多半是 max_output_tokens "
              "打满），内容仍按已收到的部分返回", file=sys.stderr)
    usage = _usage_of(prog)
    out = {"content": "".join(prog["text"]),
           "reasoning_text": "".join(prog["reasoning"]),
           "prompt_tokens": usage["prompt_tokens"],
           "completion_tokens": usage["completion_tokens"],
           "cached_tokens": usage["cached_tokens"],
           "reasoning_tokens": usage["reasoning_tokens"],
           "model": model, "provider": provider}
    _write_ledger(lp, provider=provider, model=model, purpose=purpose, usage=usage)
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--provider", default="deepseek")
    ap.add_argument("--model")
    ap.add_argument("--purpose", default="cli-smoke")
    ap.add_argument("--timeout", type=int, default=None,
                     help=f"逐 chunk 静默超时（秒），默认 {DEFAULT_IDLE_TIMEOUT}")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--retries", type=int, default=None,
                     help=f"默认 {DEFAULT_RETRIES}")
    ap.add_argument("--effort", default=DEFAULT_EFFORT,
                     choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
                     help=f"reasoning.effort，默认 {DEFAULT_EFFORT}")
    ap.add_argument("--show-cot", action="store_true",
                     help="把 CoT 与正文 delta 实时打到 stderr")
    a = ap.parse_args(argv)

    def on_delta(kind, text):
        print(text, end="", file=sys.stderr, flush=True)

    r = chat([{"role": "user", "content": a.prompt}], provider=a.provider,
             model=a.model, purpose=a.purpose, timeout=a.timeout,
             max_tokens=a.max_tokens, retries=a.retries, effort=a.effort,
             on_delta=on_delta if a.show_cot else None)
    if a.show_cot:
        print("", file=sys.stderr)
    print(r["content"])
    print(f"[{r['provider']}/{r['model']} tokens {r['prompt_tokens']}"
          f"(cached {r['cached_tokens']})+{r['completion_tokens']}"
          f"(reasoning {r['reasoning_tokens']})]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
