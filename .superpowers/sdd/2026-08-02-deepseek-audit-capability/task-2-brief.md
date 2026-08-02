### Task 2: `api_client` 支持 function tools（含守卫收紧与线格式探针）

**Files:**
- Modify: `tools/api_client.py`
- Test: `tests/test_api_client.py`（追加；**既有断言不得放宽**）

**Interfaces:**
- Consumes: 既有 `chat(messages, *, provider, model, temperature, max_tokens, purpose, stream_transport, ledger_path, api_key, timeout, retries, sleeper, effort, on_delta) -> dict`；`_consume(events, on_delta)`（返回 `prog` dict，终止事件时取 `data["response"]["usage"]`）；`_split_messages(messages) -> (instructions, turns)`。
- Produces: `chat()` 新增两个关键字参数 `tools=None`、`allowed_tool_names=None`；返回 dict 新增两个键 `function_calls: list[dict]`、`output_items: list[dict]`。Task 3 消费。

- [ ] **Step 1: 线格式探针（真实请求，必须先做）**

**DeepSeek Responses API 的 function calling 线格式文档没写**，不要照 OpenAI 惯例假设。先测：

```bash
cat > /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/probe_tools.py <<'PY'
"""探 Responses API function calling 的实际线格式：事件序列 + 终止事件里的 output 形状。"""
import json, sys, urllib.request
sys.path.insert(0, "/Users/fotile96/Zndnovel")
import os
from tools.api_client import load_env, PROVIDERS, iter_sse_events
key = os.environ.get("DEEPSEEK_API_KEY") or load_env().get("DEEPSEEK_API_KEY")
payload = {
    "model": "deepseek-v4-flash", "stream": True, "max_output_tokens": 2048,
    "instructions": "你可以调用工具。需要时就调用，不要猜。",
    "input": [{"role": "user", "content": "第 11 号台词的日文原文是什么？用工具查。"}],
    "tools": [{"type": "function", "name": "get_lines",
               "description": "取若干 id 的日文原文与中文译文",
               "parameters": {"type": "object",
                              "properties": {"ids": {"type": "array",
                                                     "items": {"type": "integer"}}},
                              "required": ["ids"]}}],
}
req = urllib.request.Request(PROVIDERS["deepseek"]["url"],
                             data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": f"Bearer {key}"}, method="POST")
seen = []
with urllib.request.urlopen(req, timeout=300) as resp:
    for etype, data in iter_sse_events(resp):
        seen.append(etype)
        if etype.startswith("response.function_call") or etype in (
                "response.output_item.added", "response.output_item.done",
                "response.completed", "response.incomplete", "response.failed"):
            print("==", etype)
            print(json.dumps(data, ensure_ascii=False)[:900])
print("\n事件序列：", seen)
PY
uv run python /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/probe_tools.py
```

**把实际输出完整抄进报告**，特别是：①`function_call` 项出现在哪个事件、字段名是什么（`call_id`? `id`? `name`? `arguments` 是字符串还是对象）；②终止事件的 `response.output` 数组形状；③继续对话时该往 `input` 里放什么（若模型未在响应里提示，按 OpenAI Responses 惯例试 `{"type":"function_call_output","call_id":…,"output":…}` 并在 Task 3 的探针里验证）。

**若探针显示 DeepSeek 不支持或形状迥异**：如实报告并**停下**，不要照假设写解析代码——这会让 Task 3 建在沙上。

- [ ] **Step 2: 写失败测试**

在 `tests/test_api_client.py` 追加（沿用该文件既有的 `_sse_lines()`/`_FakeResp` 夹具风格；`_sse_lines_with_tool_call()` 按 Step 1 探到的真实事件序列构造）：

```python
def test_tools_are_sent_when_whitelisted(tmp_path, monkeypatch):
    captured = {}

    def fake_transport(url, headers, payload):
        captured["payload"] = payload
        captured["raw"] = json.dumps(payload, ensure_ascii=False)
        yield from _events()

    tools = [{"type": "function", "name": "get_lines", "description": "d",
              "parameters": {"type": "object", "properties": {}}}]
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         stream_transport=fake_transport, ledger_path=tmp_path / "l.jsonl",
         tools=tools, allowed_tool_names={"get_lines"})
    assert captured["payload"]["tools"] == tools
    assert "web_search" not in captured["raw"]


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
```

（`_events()` 是该文件里已有的「把 `_sse_lines()` 转成 (etype, data) 迭代器」的辅助；若名字不同，用该文件实际的那个。）

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_api_client.py -v -k "tool"`
Expected: 新增四条 FAIL（`chat() got an unexpected keyword argument 'tools'`）；**既有的 `test_payload_never_sends_tools_or_web_search` 必须仍然 PASS**。

- [ ] **Step 4: 实现**

`tools/api_client.py` 四处改动：

(a) 新增校验函数（放在 `chat()` 之前）：

```python
def _validate_tools(tools, allowed_tool_names):
    """守卫（spec §2.2）：由「禁一切 tools」收紧为「只允许白名单内的 function」。

    ⚠ 不要放宽这里。Responses API 内置服务端 web_search——彩野测试里一旦启用即
    灾难：受试模型可上网查《セカンドノベル》剧情，不看译文也能答对，测试静默失效。
    历史上原始 JSON 串级的 `web_search` 子串断言捕获过 `builtin_tools` 这类改名
    绕过，那条断言在 test_payload_never_sends_tools_or_web_search 里，保留不动。
    """
    if not tools:
        return
    if not allowed_tool_names:
        raise SystemExit("传 tools 必须同时给 allowed_tool_names 白名单（缺省即拒绝）")
    for t in tools:
        if t.get("type") != "function":
            raise SystemExit(f"只允许 type=function 的工具，收到 {t.get('type')!r}")
        if t.get("name") not in allowed_tool_names:
            raise SystemExit(f"工具 {t.get('name')!r} 不在白名单内")
```

(b) `chat()` 签名新增 `tools=None, allowed_tool_names=None`；在构造 payload 前调用 `_validate_tools(tools, allowed_tool_names)`；`tools` 非空时写进 payload（`payload["tools"] = tools`）。**`tools` 为空时 payload 里不得出现该键**（既有断言靠这一点）。

(c) `_consume()` 在终止事件分支里追加捕获 output items：

```python
prog["output_items"] = resp.get("output") or []
```
并在 `prog` 初始化处加 `"output_items": []`。**其余分支一律不动**（多 part 追加逻辑、异常挂 partial 等经过三轮评审，不要顺手改）。

(d) `chat()` 的返回 dict 追加两个键：`"output_items": prog.get("output_items", [])`、`"function_calls": [it for it in prog.get("output_items", []) if it.get("type") == "function_call"]`。

**字段名以 Step 1 探针实测为准**——若 DeepSeek 的 function_call 项字段名与假设不同，按实测改，并在注释里写明实测出处。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_api_client.py -v` → 全 passed（含既有那条禁 tools 断言）。

- [ ] **Step 6: 变异自检**

临时把 `_validate_tools` 里的白名单检查注释掉，确认 `test_tool_name_outside_whitelist_is_rejected` 变红；再把 `type != "function"` 检查注释掉，确认对应用例变红。恢复后全绿。**把变异结果写进报告**——这道守卫是防作弊闸，不能是摆设。

- [ ] **Step 7: 全量测试 + commit**

Run: `uv run pytest -q` → 365 passed。

```bash
git add tools/api_client.py tests/test_api_client.py
git commit -m "feat: api_client 支持白名单内的 function tools（守卫收紧非删除）"
```

---

