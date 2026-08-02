# Task 10 报告：api_client 换 deepseek Responses API 流式调用 + ayano_test 用上 CoT

**状态：完成，已 commit（3 个逻辑提交）。**

全量测试 `uv run pytest -q` → **287 passed**（基线 274 + 本任务净增 13：
`tests/test_api_client.py` 9→20，`tests/test_ayano_test.py` 7→9）。零真实网络。

未碰 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`；
`analysis/`、`lua_scripts/`、`skeleton/` 只读。key 全程只从 `.env` 读取，未出现在
任何代码、测试、报告或 commit message 里（**已就绪**）。

---

## A. 实测确认：端点路径

| 路径 | 结果 |
|---|---|
| `https://api.deepseek.com/v1/responses` | **HTTP 200**，`content-type: text/event-stream; charset=utf-8` |
| `https://api.deepseek.com/responses` | **HTTP 200**，事件序列与上面**完全一致** |

文档只写了 base_url `https://api.deepseek.com`，路径未明示。**实测两条都通**。
代码取 `/v1/responses`——与 OpenAI Responses 惯例一致，将来换 SDK/换供应商不用改；
这条结论同时写进了 `tools/api_client.py` 的 `PROVIDERS` 注释。

顺带实测到的两件事（也写进了代码注释）：

- **模型**：`deepseek-v4-pro` → HTTP 400「Codex integration with deepseek-v4-pro
  will be available starting early August 2026. Please use deepseek-v4-flash
  instead for now.」→ 证实 Responses 现阶段**只支持 `deepseek-v4-flash`**。
  已写进模块 docstring，并把 `PROVIDERS["deepseek"]["default_model"]` 从
  `deepseek-chat` 改成 `deepseek-v4-flash`（旧默认模型在 Responses 上不可用）。
- **`reasoning.effort` 合法取值**（由 400 报文枚举出来）：
  `none / minimal / low / medium / high / xhigh / max`。

## B. 实测确认：事件类型序列

一次最小请求（`instructions` + 单轮 `input` + `stream:true`）实收的完整序列，
按到达顺序、`uniq -c` 后：

```
 1 response.created
 1 response.in_progress
 1 response.output_item.added        ← item.type = "reasoning"
 1 response.content_part.added       ← part.type = "reasoning_text"
 9 response.reasoning_text.delta     ← CoT 逐字下行
 1 response.reasoning_text.done      ← 带完整 text
 1 response.content_part.done
 1 response.output_item.done
 1 response.output_item.added        ← item.type = "message"
 1 response.content_part.added       ← part.type = "output_text"
 1 response.output_text.delta        ← 正文逐字下行
 1 response.output_text.done         ← 带完整 text
 1 response.content_part.done
 1 response.output_item.done
 1 response.completed                ← data.response.usage 在这里
```

要点：**推理 item 在正文 item 之前完整走完一遍**（added→delta*→done→part.done→
item.done），然后才开第二个 item 出正文。终止事件 `response.completed` 的
`data.response.usage` 形状实测为：

```
{"input_tokens":14,"input_tokens_details":{"cached_tokens":0},
 "output_tokens":11,"output_tokens_details":{"reasoning_tokens":9},"total_tokens":25}
```

`response.created` 回显的 `response` 里 `"tools":[]`——**是远端回显的空列表，不是
我们发的**；请求体里从未出现 `tools` 键（见 §F）。

多轮 `input`（role/content 数组形式）实测正常生效：三轮对话里记数字再问回来，
答案正确，说明 `_split_messages()` 的 system→`instructions` / 其余→`input` 映射
可用。

## C. 缓存验证：**仍然有效**

同一条约 2.35 万 token 的长前缀（seg1-s2 的完整卡组梗概 + 正文，35257 字符）
连发两次，同一模型同一 purpose 前缀：

| 次序 | 耗时 | input_tokens | cached_tokens | 命中率 |
|---|---|---|---|---|
| #1 | 12.8s | 23551 | 15232 | 64.68% |
| #2 | 14.8s | 23551 | **23424** | **99.46%** |

**结论：Responses API 上前缀缓存照常命中，与 chat/completions 实测的 99.65%
（20992/21065）同一量级。**这条改造没有牺牲成本结构。

有意思的旁证：**第 1 次就已经有 64.68% 命中**——那条前缀在 T9 是通过
chat/completions 发的。看上去缓存跨 API surface 复用、且留存时间足够长；不过这
只是一次观察，不当结论用。

端到端小样里 q1/q4 两次 reader 调用的 `cached_tokens` 都是 23424（前缀完全相同，
只有末尾问题不同），judge 调用 256/355。**新台账字段第一次让这件事可见**——此前
我们对成本结构是半盲的。

## D. 端到端小样：q1 / q4（与 T9 对比）

命令（题库子集与输出都落 scratchpad，未入仓库）：

```
uv run python tools/ayano_test.py --segment seg1-s2 --qa <scratch>/smoke-qa.yaml \
  --lane-dir pilot/lanes/opus --out <scratch>/ayano-smoke-report.md \
  --model deepseek-v4-flash
```

**整跑 15.0s，退出码 0，零重试、零告警行。**

### 对比表

| 项 | T9（chat/completions） | T10（Responses 流式） |
|---|---|---|
| q1 判分 | 对 | **对** |
| q4 判分 | 对 | **对** |
| q1 reader tokens | 21152 + 285 | 23566 + 473（其中 reasoning 417；cached 23424） |
| q4 reader tokens | 21143 + 397 | 23557 + 287（其中 reasoning 234；cached 23424） |
| q1/q4 judge tokens | 338+60 / 361+58 | 355+70 / 350+111 |
| 整跑耗时 | 未计时（约 9s，按台账时间戳 11:23:11→11:23:20 推） | 15.0s |
| 缺译提示 | 缺译 707 行 | 缺译 569 行（并行会话又译了一批，前缀变长 → input 从 21k 涨到 23.5k） |
| CoT | **拿不到** | **拿到，且进了报告** |

耗时变长、output_tokens 变多，都来自同一个原因：现在**推理 token 是显式产出的**
（reasoning 417/234），之前 chat/completions 用的是非推理路径。这不是回归——CoT
可看正是这次改造要买的东西，而它同时就是抗超时的那条数据流。

### q1

- **题面**：ユウイチ约アヤノ这个周六出去玩，アヤノ为什么没能当场答应？两人最后
  把出去玩的日子改到了什么时候？
- **受试回答**：因为アヤノ之前已经和隔壁班的サクラ同学约好，周末要是有空就两个
  人去买东西；虽然还没得到回复，但毕竟是自己先约了人家，所以不能当场答应
  ユウイチ。两人最后把出去玩的日子改到了下周。
- **判分**：`对|受试回答完整说明了先约サクラ、未得到回复但自己先约所以不能答应，
  以及改到下周日。`
- **CoT 摘要（报告里实际写入的那 300 字）**：
  > 我们根据给定文本回答。问题：ユウイチ约アヤノ这个周六出去玩，アヤノ为什么没能
  > 当场答应？两人最后把出去玩的日子改到了什么时候？ 从最新正文开头：アヤノ说
  > “啊——，这周六啊——”，ユウイチ问“嗯？有什么安排吗？”，アヤノ道歉后说“要说有
  > 安排……倒也不算是啦。就是之前跟一个女孩子说过，周末要是有空的话……”提到
  > サクラ同学，约好休息日要是有空就两个人去买东西。虽然还没得到回复，但毕竟是
  > 自己先约的人家。ユウイチ说“有约在先那也没办法。那就改到下周吧”。之后一段
  > 重复类似内容，然后アヤノ列举各种地方，最后决定改到下周。注意前面アヤノ说
  > “之前跟一个女孩子说过，周末要是有空的话……”这是原因：已经和サクラ同学有……
  > （共 663 字，已截断）

  **这正是本次改造的核心增值**：CoT 里逐句引用了译文原句（「啊——，这周六啊——」
  「有约在先那也没办法」），可以直接确认它**是从译文里读出来的，不是靠剧情常识
  猜的**。T9 那次只能看到结论「对」，无从判别。

### q4

- **题面**：サクラ在教咒语之前先出了两道推理题。这两道题的正确答案分别是什么？
- **受试回答**：① 女孩看到的光景其实只是普通的房间外面；因为她一直生活在阁楼
  房间里，所以那是有冲击力的景象，原因是她的父母（不让她出去）。
  ② 赝品的做工完全没有问题，被识破的原因在于原作本身。
- **判分**：`对|两道题均答出核心事实：第一题是房间外面且女孩住在阁楼，第二题是
  原作有问题。`
- **CoT 摘要**：
  > 我们只需要根据给定文本回答。问题：サクラ在教咒语之前先出了两道推理题。这两道
  > 题的正确答案分别是什么？ 文本中两道题：第一题小女孩阁楼，答案是“女孩看到的是
  > 再平常不过的普通的家里，原因是她的父母。女孩一直生活在阁楼房间里，所以看到
  > 房间外面是冲击性光景”。更简洁：女孩一直住在阁楼房间里，看到的其实是普通的
  > 家/房间外面；原因是她的父母（一直把她关在阁楼）。第二题赝品男人：答案是
  > “赝品的做工完全没有问题，原因在于原作”（因为原作本身就是赝品/假货？需确认）。
  > 文本中アヤノ答对：“赝品的做工完全没有问题，原因在于原作。”サクラ说答对了。
  > 所以正确答案分别是： 1. 女孩看到的只是普通的房间外面，因为她一直住……
  > （共 386 字，已截断）

  这条 CoT 里有一处**值得注意的诊断信号**：受试者对第二题写了「因为原作本身就是
  赝品/假货？**需确认**」——它把译文里那句「原因在于原作」照抄下来了，但**不理解
  这句到底什么意思**，只能靠「サクラ说答对了」这个旁证反推。答案判「对」，可它其实
  没读懂推理链。这类「照抄得分但没读懂」的情况，**只有看 CoT 才能发现**，判分本身
  是看不出来的——这正是这次改造给彩野测试装上的新眼睛，建议段末验收时把 q4 的
  译文推理链单独看一眼。

---

## E. 静默超时设计

`DEFAULT_TIMEOUT = 600` → **`DEFAULT_IDLE_TIMEOUT = 120`**。

**机制确认**：`urlopen(req, timeout=T)` 设的是底层 **socket** 超时——`http.client`
把 T 交给 `socket.settimeout()`，而 socket 超时的语义是「**单次 recv 的等待上限**」，
不是「整个响应的总时长上限」。对流式响应来说，每次 `read`/迭代各自重新计时。所以
这个参数**天然就是 idle timeout**，不需要额外看门狗线程；只要远端持续吐字节（哪怕
吐的是 CoT）就永不触发，只有真断流/远端长时间一声不吭才触发。这段已写进
`DEFAULT_IDLE_TIMEOUT` 与 `_http_stream_transport` 的注释。

**取值理由**：门槛量级从「总时长」降到「**单次事件间隔**」。稳定吐字时事件间隔是
毫秒级；实际最长的一次静默是「请求发出 → 首个 `response.created`」之间的远端
prefill（彩野测试单次 prompt 约 2.35 万 token，实测整次 12–15s），量级几十秒。
120s 给它留了数倍余量，同时把「连接已死」的检出时间从 600s 压到 2 分钟。

**参数名**：`chat()` 的形参仍叫 `timeout`（不动对外契约、不动 `ayano_test` 的
`--timeout` 透传），docstring/CLI help 明写它现在是「逐 chunk 静默超时」；**常量名**
按要求改成了表达语义的 `DEFAULT_IDLE_TIMEOUT`。

## F. 重试设计

| 要求 | 实现 |
|---|---|
| ① 失败也要把已产生的部分 token 计入 ledger | `_consume()` 中途出错时把进度快照挂到**原异常**上（`exc.partial = prog`，保住原异常类型好判可重试性），`chat()` 在决定重不重试**之前**先写一行台账。终止事件没到达时 usage 拿不到 → 输出侧按 **delta 事件计数**估算（deepseek 基本一事件一 token），输入侧无从得知记 `-1`，行里带 `"partial": true`（＋ `"estimated": true`）与 `"attempt": n`。一个字节都没回来的失败（4xx/连不上）**不入账**——那次没产出也没计费。 |
| ② 已开始吐字的流不整体重试 | **只重试「本次尝试尚未产出任何 delta」的失败。** 理由：重试要丢弃已收到的部分 CoT 并整段重来，重复消耗计费 token（彩野测试单次输入 2.35 万）；而我们真正想救的「远端长思考被 timeout 误杀」这个场景**恰恰发生在首个 delta 之前**。一旦稳定吐字，120s 静默超时已远大于事件间隔，此时再超时就是连接真死了，重来只会再烧一次钱。stderr 打「不重试：本次流已产出 N 个 delta（重试会整段重来并重复计费）」。 |
| ③ 4xx 立即失败 | `_is_retryable()` 保持原逻辑：`HTTPError` 仅 `>=500` 或 `429` 可重试。 |
| ④ 429 优先 Retry-After | `_retry_after(exc)` 读 `exc.headers["Retry-After"]`（秒数形式），读到就照它 sleep 且**不推进退避倍数**；读不到才回退 2/4/8s 指数退避。stderr 里标出用的是哪一路。 |

另外两条流式特有的正确性处理：

- **`response.incomplete`** 当成功处理（内容按已收到部分返回）＋ stderr 告警
  「输出被截断，多半是 max_output_tokens 打满」。缓存探针用 `max_tokens=1024` 时
  真实触发过，行为符合预期。**`response.failed`** 抛错。
- **没有任何终止事件就断流** → `StreamAborted`。不能当正常完成——那会把半截回答当
  完整答案交给判分员。有专测 `test_no_terminal_event_is_an_error`。

## G. 「绝不发送 tools」

请求体的构造处（`chat()` 里 `payload = {...}`）有醒目注释说明理由：Responses API
内置服务端 `web_search`，一旦启用，彩野测试的受试模型就能直接上网查
《セカンドノベル》剧情、不看译文也能答对，**测试静默失效**——与本轮踩过两次的
「恒绿关卡」是同一类病。

防回潮的测试：`test_payload_never_sends_tools_or_web_search` 断言序列化后的请求体
里 **没有 `tools` 键、没有 `tool_choice` 键、原始 JSON 串里不含 `web_search`
子串**（子串断言是为了连「换个字段名把它塞进来」也一起挡住）。

## H. 台账新字段

成功行在原有 `{ts, provider, model, purpose, prompt_tokens, completion_tokens}`
基础上**追加** `cached_tokens`、`reasoning_tokens`（`prompt_tokens` ←
`usage.input_tokens`、`completion_tokens` ← `usage.output_tokens`，语义与名字不变，
老行仍可读）。失败行额外带 `partial`/`attempt`/`estimated`。

本次实测新增 8 行已入库 `data/api_ledger.jsonl`（responses-smoke 1 + cache-probe 2
+ q1/q4 各 reader/judge 4）。

---

## I. 既有测试的改动（逐条）

### `tests/test_api_client.py`（原 9 条 → 现 20 条）

架构变化本身是强制的：注入点由 `transport(url, headers, payload) -> dict`（一次
调用→一次完整 dict 的同步语义）改成
`stream_transport(url, headers, payload) -> Iterable[(event_type, data)]`。旧签名
与流式天然不匹配，按评审要求**不超载**、另开独立注入点，所以所有注入型测试的假
transport 必须改形状。**没有一条断言被削弱。**

| 原测试 | 改了什么 | 为什么必须改 |
|---|---|---|
| `_fake_transport`（辅助） | 返回 dict → 返回 `_events()` 事件生成器；`payload["model"]` 断言 `deepseek-chat` → `deepseek-v4-flash` | 注入点语义变了；且 Responses 只支持 v4-flash，`default_model` 随之改 |
| `test_chat_returns_content_and_writes_ledger` | 仅 kwarg 名 `transport=` → `stream_transport=` | 同上；4 条断言一字未动 |
| `test_missing_key_exits_with_guidance` | **未改** | — |
| `test_load_env_parses_quotes_and_comments` | **未改** | — |
| `test_retry_on_5xx_then_succeeds` | 假 transport 成功分支返回 `_events(...)`；kwarg 名 | 同上；`len(calls)==3` / `sleeps==[2,4]` 断言未动 |
| `test_no_retry_on_4xx` | 仅 kwarg 名 | 同上；断言未动 |
| `test_retries_exhausted_raises` | 仅 kwarg 名 | 同上；断言未动 |
| `test_retries_zero_disables_retry` | 仅 kwarg 名 | 同上；断言未动 |
| `test_default_transport_receives_configured_timeout` | `FakeResp.read()` → `FakeResp.__iter__()` 吐真实 SSE 行 | 默认 transport 现在按行迭代响应而不是一次 `read()`；`captured["timeout"]==12` 断言未动 |
| `test_default_timeout_and_max_tokens_when_unset` | 改名 `..._default_idle_timeout_and_max_output_tokens_...`；`DEFAULT_TIMEOUT`→`DEFAULT_IDLE_TIMEOUT`；`payload["max_tokens"]`→`payload["max_output_tokens"]`；**加**了 `content`/`cached_tokens` 断言 | Responses 的字段名就是 `max_output_tokens`；常量按要求改名。**只加不减** |

新增 11 条：`test_chat_exposes_reasoning_and_cache_fields`、
`test_payload_is_responses_shaped_and_streaming`（含 `stream is True`）、
`test_payload_never_sends_tools_or_web_search`、
`test_iter_sse_events_parses_multiline_comments_and_done`（跨行 data / `:` 注释 /
`[DONE]` / 非法 JSON / 结尾无空行五种边界）、`test_no_terminal_event_is_an_error`、
`test_partial_tokens_are_ledgered_even_when_request_fails`、
`test_started_stream_is_not_retried`、`test_timeout_before_any_delta_is_retried`、
`test_429_honours_retry_after_header`、
`test_429_without_retry_after_falls_back_to_backoff`、
`test_on_delta_callback_sees_reasoning_and_text`。

### `tests/test_ayano_test.py`（原 7 条 → 现 9 条）

| 原测试 | 改了什么 |
|---|---|
| `test_main_writes_report_with_verdicts` | 假 transport 返回 `_fake_events(...)`；kwarg `transport=`→`stream_transport=`。**5 条断言一字未动** |
| `test_dry_run_zero_api_calls` | 仅 kwarg 名 |
| 其余 5 条（`assemble_context` 系列 + `test_model_and_timeout_passthrough`） | **完全未改** |

新增 2 条：`test_report_includes_cot_excerpt`（CoT 进报告、超长截断、judge 的 CoT
不进报告、摘要压成单行）、`test_effort_passthrough`。

`tools/ayano_test.py` 的 `main()` 形参也由 `transport=` 改名 `stream_transport=`
——只是注入点改名，两处 `chat()` 的**调用方式未变**（仍是
`chat(messages, purpose=..., **kw)`），符合契约不变的要求。

---

## J. commit

- `55c9bda` feat: api_client 换 deepseek Responses API 流式调用（CoT 可看 + 抗超时）
- `9534179` feat: ayano_test 报告写入受试者 CoT 摘要 + --effort 透传
- （第三个 commit）chore: Responses 流式改造实测台账入库 + task-10 报告
  ——本报告自身就在这个 commit 里，哈希以 `git log` 为准（自引用无法写死）

---

## K. 顾虑 / 待用户关注

1. **`deepseek-v4-flash` 是 Responses 上唯一可用模型**（实测 400 报文写明 v4-pro
   要 2026 年 8 月初）。判分员目前也只能用它。若将来想给判分换更强的模型而
   Responses 侧还没开放，需要为判分单独保留一条 chat/completions 通路——旧实现在
   git 历史里（本次按要求直接替换，未保留双路径）。
2. **q4 的 CoT 暴露了一个真实的译文问题**（见 §D）：受试者照抄「原因在于原作」得了
   分，但 CoT 里明说「需确认」，即它并没读懂这条推理链。判分是「对」，CoT 说的是
   「其实没懂」。建议段末验收时人工看一眼这处的推理链译文。这类信号 T9 完全看不见
   ——是这次改造第一次拿到的东西。
3. **部分 token 记账里输入侧记 `-1`**：终止事件没到达时 `usage` 根本不下发，输入
   token 数无从得知（但远端多半已经计费）。台账行的 `partial:true` 标记就是提示
   「这一次发生过、也花过钱、但计数不全」，看账时不要把它当作 0。
4. **缓存跨 API surface 复用只是一次观察**（§C 里第 1 次就 64.68% 命中，那条前缀
   是 T9 用 chat/completions 发的），不作为结论，别据此做成本规划。
5. `--dry-run` 之外新增的 `--effort` 默认走 `api_client.DEFAULT_EFFORT = "medium"`。
   若发现 CoT 太短看不出所以然，可以 `--effort high`；但 reasoning token 是计费的
   输出 token，成本会涨。
