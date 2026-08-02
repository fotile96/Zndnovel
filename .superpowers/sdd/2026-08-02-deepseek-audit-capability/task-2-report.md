# Task 2 报告：`api_client` 支持 function tools（含守卫收紧与线格式探针）

状态：**DONE**。测试 365 passed（基线 361 + 新增 4）。

---

## Step 1：线格式探针（真实请求，2026-08-02）

对 `https://api.deepseek.com/v1/responses`、`model=deepseek-v4-flash`、`stream=true`
发两次真实请求。**结论：DeepSeek 的 function calling 线格式与 OpenAI Responses 惯例
完全一致，无需任何字段名调整。**

### ① 完整事件序列（探针 1 实测，去掉重复的 delta 计数）

```
response.created
response.in_progress
response.output_item.added          ← item.type = "reasoning"
response.content_part.added         ← part.type = "reasoning_text"
response.reasoning_text.delta × 21
response.reasoning_text.done
response.content_part.done
response.output_item.done           ← reasoning item 收尾
response.output_item.added          ← item.type = "function_call"（已带 call_id/name，arguments="")
response.function_call_arguments.delta × 9
response.function_call_arguments.done
response.output_item.done           ← function_call item 收尾（带完整 arguments）
response.completed
```

**关键观察：function_call item 不发 `content_part.added` / `content_part.done`**
（reasoning 与 message item 都发）。参数增量走**专用事件** `response.function_call_arguments.delta`，
其载荷是 `{"type":…, "delta": "<片段>", "item_id": …, "output_index": …}`——注意是
`item_id` 而非 `call_id`，且**没有** `call_id`/`name`，所以单靠 delta 事件无法知道调
的是哪个函数，必须从 `output_item.added` 或终止事件的 `output` 里取。

### ② `function_call` 项的实际 JSON 形状

`response.output_item.added`（开始，arguments 为空串）：

```json
{"type": "response.output_item.added",
 "item": {"type": "function_call", "id": "ff61a12a-18a2-4793-8510-7c285157ef61",
          "status": "in_progress", "arguments": "",
          "call_id": "call_00_zpQBBijfbGNniXO4rgfM2256", "name": "get_lines"},
 "output_index": 1, "sequence_number": 28}
```

`response.function_call_arguments.done`：

```json
{"type": "response.function_call_arguments.done", "arguments": "{\"ids\": [11]}",
 "item_id": "ff61a12a-18a2-4793-8510-7c285157ef61", "output_index": 1, "sequence_number": 38}
```

`response.output_item.done`（完成态 item，与终止事件 `output` 里的那一项**逐字相同**）：

```json
{"type": "function_call", "id": "ff61a12a-18a2-4793-8510-7c285157ef61",
 "status": "completed", "arguments": "{\"ids\": [11]}",
 "call_id": "call_00_zpQBBijfbGNniXO4rgfM2256", "name": "get_lines"}
```

字段名裁决（brief 里三个待定问题的答案）：

| 问题 | 实测答案 |
|---|---|
| `call_id` 还是 `id`？ | **两者都有，且是两个不同的东西**：`id` 是 output item 自身的 UUID（`ff61a12a-…`，delta 事件里叫 `item_id`）；`call_id` 是工具调用句柄（`call_00_…`），续轮 `function_call_output` 要回引的是**它**。解析工具调用请用 `call_id`。 |
| `arguments` 是字符串还是对象？ | **JSON 字符串**（`"{\"ids\": [11]}"`），不是 dict。消费侧必须 `json.loads`。 |
| 函数名字段 | `name`（顶层，与 `type`/`id`/`call_id` 平级；**不**嵌在 `function` 子对象里——这点与 chat/completions 的 `tool_calls[].function.name` 不同）。 |

### ③ 终止事件的 `response.output` 数组形状（探针 2 完整打印）

```json
[{"type": "reasoning", "id": "231ad576-…", "status": "completed",
  "content": [{"type": "reasoning_text", "text": "The user asks for line 11's …"}],
  "summary": []},
 {"type": "function_call", "id": "1a8a8009-…", "status": "completed",
  "arguments": "{\"ids\": [11]}", "call_id": "call_00_krk9AavRozPaHmucWwY47211",
  "name": "get_lines"}]
```

即：**扁平数组，每个 output item 一项，function_call 与 reasoning / message 平级**。
本轮没有 `message` item（模型直接调工具，未出正文）——所以工具循环不能假设一定有正文。

`usage`（形状与无工具时一致，既有 `_usage_of` 不需要改）：

```json
{"input_tokens": 393, "input_tokens_details": {"cached_tokens": 384},
 "output_tokens": 71, "output_tokens_details": {"reasoning_tokens": 25}, "total_tokens": 464}
```

终止事件 `response` 顶层键（含 `tools`/`tool_choice`/`max_tool_calls`/`parallel_tool_calls`
——说明服务端确实按工具模式处理了这次请求，不是静默忽略）：
`background, completed_at, content_filters, created_at, error, frequency_penalty, id,
incomplete_details, instructions, max_output_tokens, max_tool_calls, metadata, model,
moderation, object, output, parallel_tool_calls, presence_penalty, previous_response_id,
prompt_cache_key, prompt_cache_retention, reasoning, safety_identifier, service_tier,
status, store, temperature, text, tool_choice, tools, top_logprobs, top_p, truncation,
usage, user`

### ④ 续轮形状（brief 说可留给 Task 3，这里顺手实测掉了）

按 OpenAI Responses 惯例构造并**实测通过**：把上一轮 `response.output` 的各项
**原样**追加进 `input`，再追加一项

```json
{"type": "function_call_output", "call_id": "call_00_…", "output": "<结果 JSON 字符串>"}
```

远端接受（HTTP 200），返回正常的 `reasoning` + `message` 两项 output，正文正确引用了
工具喂进去的内容（回答「第 11 号台词的日文原文是：**「夏の匂いがした。」**」——该内容
纯属探针捏造，正说明模型是从 tool 结果读的而非自己编的）。轮 2 事件序列不含任何
`function_call_*` 事件。**Task 3 可以按这个形状写，无需再探。**

> 注：`output` 字段实测接受 JSON 字符串。未测试传 dict 是否也被接受。

**探针脚本**：`<scratchpad>/probe_tools.py`、`probe_tools2.py`（临时文件，不入库；key 从
仓库根 `.env` 读，未落任何文件）。

---

## Step 4：实现（tools/api_client.py 四处，均如 brief 所写，无字段名调整）

- (a) 新增 `_validate_tools(tools, allowed_tool_names)`，docstring 原样保留 brief 里
  那段「为什么不能放宽」的说明（含 `builtin_tools` 改名绕过的历史）。
- (b) `chat()` 签名新增 `tools=None, allowed_tool_names=None`；构造 payload 前调用
  `_validate_tools`；`if tools: payload["tools"] = tools`。**`tools` 为空时该键不出现**。
  原「⚠ 绝不发送 tools」的注释改写为「只发白名单内的 function 工具，永不发服务端内置
  工具」，并显式点名它守着的那条既有测试。
- (c) `_consume()` 的 `prog` 初始化加 `"output_items": []`；终止事件分支加
  `prog["output_items"] = resp.get("output") or []`。**其余分支一个字没动**（多 part
  追加、异常挂 partial、重试分类均原样）。
- (d) `chat()` 返回 dict 加 `output_items` 与 `function_calls`（按 `type=="function_call"`
  过滤），并在注释里写明字段名的实测出处指向本报告。

`tools/ayano_test.py` **未改动**，两处 `chat()` 调用都不传 `tools`——受试者仍只能靠给定
文本作答。

---

## Step 6：变异自检（守卫是真闸，不是摆设）

逐条注释掉 `_validate_tools` 里的检查，跑 `pytest tests/test_api_client.py -k tool`：

| 变异 | 结果 | 变红的用例 |
|---|---|---|
| A 删掉「name 不在白名单则拒」 | 1 failed, 4 passed | `test_tool_name_outside_whitelist_is_rejected` |
| B 删掉「type != function 则拒」 | 1 failed, 4 passed | `test_non_function_tool_type_is_rejected` |
| C 删掉「缺白名单即拒」 | 1 failed, 4 passed | `test_tools_require_explicit_whitelist` |
| 恢复 | 33 passed | — |

三条变异各自**只**杀掉对应那一条用例（无过度耦合、也无漏网），源文件已 `diff` 确认逐字
恢复。

一个观察：变异 C 下用例是以 `TypeError`（`"get_lines" not in None`）变红而非
`SystemExit`。红是红了，但那是崩溃不是拒绝——说明「缺白名单」这条分支同时也是防
`None` 的护栏，删了会得到一个丑陋的崩溃而非干净的拒绝。保留原实现。

既有的 `test_payload_never_sends_tools_or_web_search`（含**原始 JSON 串不得含
`web_search` 子串**那条断言）**全程未改一字、全程 PASS**；新增的
`test_tools_are_sent_when_whitelisted` 也复刻了同一条串级断言，使得「白名单路径」上
同样挡住改名绕过。

---

## Step 7：全量测试 + commit

`uv run pytest -q` → **365 passed**（基线 361 + 4）。
`git add` 只加了 `tools/api_client.py` `tests/test_api_client.py` 与本 SDD 目录下的
`*.md`；生产会话的 `pilot/lanes/`、`prompts/`、`2026-08-02-p3-seg2-s3/` 一律未触碰。

## 给 Task 3 的交接要点

1. 解析工具调用用 `fc["call_id"]`（不是 `fc["id"]`），`json.loads(fc["arguments"])`。
2. 续轮 `input` = 原 input + 上一轮 `output_items` **原样** + 每个调用一条
   `{"type":"function_call_output","call_id":…,"output": <JSON 字符串>}`。已实测通过。
3. 一轮可能**没有** message item（只有 reasoning + function_call），循环终止条件应看
   「本轮 `function_calls` 是否为空」而不是「有没有正文」。
4. 一轮可能有**多个** function_call（`parallel_tool_calls` 在响应里存在）；本次探针只出
   现单个，多个的情形未实测——工具循环按数组处理即可，形状上无额外未知。
