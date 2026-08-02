# Task 3 报告：有界工具循环 `tools/agent_loop.py`

状态：**complete**。测试 371 passed（基线 365 + loop 5 + 串级闸运行时用例 1）。

## 交付

- 新增 `tools/agent_loop.py`：`run_with_tools(messages, *, tool_names=None, max_rounds=6, lane_dir=None, **chat_kw)`
  → `{content, rounds, tool_calls, stopped_reason, reasoning_text, prompt_tokens, completion_tokens}`，
  `stopped_reason ∈ {"finished","max_rounds"}`。代码逐字采用 brief Step 3（仅 docstring
  的「回灌形状取舍」一段按 T2 探针实况改写：结构化续轮已被证明**可行**，本任务仍走纯文本，
  理由是接口改动量而非可行性未知）。
- 新增 `tests/test_agent_loop.py`：brief Step 1 的 5 条，逐字采用。

安全性的落点仍是 T1 那条：工具面全只读，写报告由任务层做、不经过模型；到顶不静默由
`test_max_rounds_stops_loudly` 守着（`rounds==3` 且 `stopped_reason=="max_rounds"`）。

## Step 5 真实冒烟 —— loop 的首次真实验证

命令（brief 原样）：

```
uv run python tools/agent_loop.py --prompt "第 8478 号台词是不是伏笔锚点？如果是，它的中文定译是什么？用工具查，不要猜。" --tools get_anchor,get_lines
```

**模型真的调了工具**（不是猜）。stderr 摘要行：

```
[rounds=2 stopped=finished tools=['get_anchor']]
```

- rounds = **2**（第 1 轮只发 function_call、正文为空；第 2 轮吃回灌后出正文）
- 调用的工具：**`get_anchor` 一次**（`{"id": 8478}`）。给了 `get_lines` 但模型没用——
  `get_anchor` 的返回已含 jp/zh/recall，够答题，属合理取舍。
- 台账两行（purpose=agent-loop-cli）：478+79 / 770+343 tokens，第二轮 cached_tokens=384
  ——**前缀缓存在续轮命中了**，说明纯文本回灌是「原对话 + 追加轮次」的形状，没有破坏前缀。

回答原文（stdout 全文）：

> 根据工具返回，第 8478 号台词**是伏笔锚点**。
>
> 它的中文定译是：
>
> > **【サクラ】「约定，原来是不肯为我遵守呀。彩野同学」**
>
> 补充说明（工具中记录的锚点信息）：
>
> - 日文原文：**【サクラ】「約束、まもってくれないんだ。彩野さん」**
> - 所属章节：**s1s**
> - 伏笔类型：**★汉字呼名装置**（v7 补锚，与 s6s 15775 成对）
> - 核心规则：全库 696 条 SAK 语音行中，仅 2 处用汉字「彩野さん」（本行即其一），其余 100 处均为片假名「アヤノさん」——作者以书写切换标记「面具滑落」。**必须保持汉字形「彩野同学」，绝不可归一为「アヤノ同学」。**
>
> ⚠️ 特别提醒：本场（scene_s1s_300）中サクラ共 5 句，仅开口这句（8478）用汉字，其后 8501/8506/8508 三句全部回到片假名，且 8508 已锚定并注明「称呼不变」——8478 与 8508 的写法差异是**有意的**，不是笔误，后续翻译时切勿「修复」为本行。

预期命中：回答含「彩野同学」✅。

**关于纯文本回灌是否够用**：本次**未观察到**模型分不清「工具结果」与「用户输入」的迹象
——它把回灌内容明确称作「工具返回」「工具中记录的锚点信息」，并把 recall 字段里的
约束原样转述。单例不构成结论，但目前没有换结构化回灌的证据（与 T2 评审的设计决定一致）。
最后一段「⚠ 特别提醒」超出工具返回的字面内容（8501/8506/8508 三句的写法、8508 已锚定），
是模型从 recall 文本推演/复述的——审计场景下这类**外推**需要在 T4/T5 的提示词里约束成
「只报工具查得到的」，否则会混入未经核实的断言。这条留给 T4 注意，不改本任务。

## 顺手三条的处置

- **①（T1 评审）无写操作断言黑名单**：`tests/test_agent_tools.py::test_module_has_no_write_operations`
  的黑名单由 5 项扩到 15 项，含 `append_jsonl(`、`write_bytes(`、`os.remove(`、`os.rename(`、
  `os.replace(`、`shutil.`、`subprocess`、`.touch(`、`rmdir(`、`os.makedirs(`。
  `agent_tools.py` 扩展后**仍通过**（它本来就干净，未改一字）。测试条数不变。
- **②（T2 评审）串级 `web_search` 升级为运行时闸**：`tools/api_client.py::chat()` 在 payload
  构造完成、发请求之前加一行 `if "web_search" in json.dumps(payload, ensure_ascii=False): raise SystemExit(...)`。
  新增 `test_web_search_in_payload_is_refused_at_runtime`：字段级检查放行（type=function、
  name 在白名单内）但描述里含 `web_search` 的用例被拒，且断言**根本没走到 transport**。
  `api_client.py` 除这一处外未动。
- **③（T2 评审留给实现者的两条实况）**：已在实现中意识到，无需改代码——
  loop 累加的是 `chat()` 返回的 `prompt_tokens`/`completion_tokens`（正常路径来自 usage，准确）；
  partial 路径 `function_calls` 恒空，对 loop 的表现是「那一轮被当作无工具调用 → 提前
  `finished`」，此时 `content` 也是半截，属于既有的 partial 语义，不是本 loop 新引入的失效模式。
  这一点值得记下来：**partial 会让 loop 以 `finished` 收尾而非 `max_rounds`**，
  即「到顶不静默」这条不覆盖「流中断」这条路径——若将来审计里出现无来由的短回答，先查台账
  有没有 partial 行。

## 顾虑

1. `partial` → 静默 `finished`（见上）。当前不改：修它要动 `_consume`／`chat()` 的返回契约，
   而 api_client 已过三轮评审。建议在 T5 消费侧检查台账 partial 行，或将来给 `chat()`
   加一个 `was_partial` 标志再由 loop 转成 `stopped_reason="stream_aborted"`。
2. 模型的**外推**（上文）——工具面只读保证的是「不会改坏东西」，不保证「不会说没查过的话」，
   提示词侧要补。
3. 多个并行 function_call 的真实形状仍未实测（T2 遗留）。loop 的实现按数组遍历、逐个执行
   逐个回灌，形状上支持；但本次冒烟同样只出单个 call，未验证。

---

# 修正一节（评审 I-1 / I-2 / m-1..m-3，2026-08-02）

**上面的原文一字未删**，包括其中两条错误的自陈顾虑。保留原文是有意的：本节记录的
「自陈被独立复算推翻」这一过程本身就是结论——**不要相信自陈，要能复算**。

## I-1 订正：漏洞真实存在，但我指错了真凶

**我原先写的**：「partial 路径会让 loop 以 `finished` 静默收尾」，并据此建议 T5 去查
台账的 partial 行。

**错在哪**：`partial` 路径**是大声失败的**。我自己复现的离线探针（注入 transport，
零真实请求）：流在终止事件前中断 → `_consume` 抛 `StreamAborted` → `chat()` 的重试循环
（`produced>0` 强制不重试 / 重试耗尽）一律 `raise` → 异常**穿透** `run_with_tools`
（本模块的 `except` 只包住单个工具执行，不包 `chat()`）。探针输出：

```
partial 大声失败 = StreamAborted 流在终止事件到达前结束（未收到 response.completed/incomplete/failed）
```

我把「`function_calls` 恒空」这条 T2 遗留实况**外推**成了一条运行时路径，而没有去追
异常是否可达 loop。这正是我在原文里指摘模型的那种毛病（拿着一条实况推演出没验证的结论），
我自己在同一份报告里犯了。

**真凶是 `response.incomplete`**——它在 `TERMINAL_EVENTS` 里，`_consume` 正常返回、
`chat()` 正常返回。我复现的探针（与评审输出逐字一致）：

```
P1 chat() 正常返回 = True
P1 content = '结论是：本次审计发现 3 处未履行，分别是'     ← 半截结论
P1 有没有任何键说明这是被截断的 = []
P1 loop stopped_reason = finished
P1 台账行 = {…"prompt_tokens":100,"completion_tokens":20,"cached_tokens":0,
             "reasoning_tokens":5,"effort":"max"}          ← 无 partial 无 estimated
```

台账行与一次正常调用**完全同形**，所以我原先建议的兜底（「T5 查台账 partial 行」）
**对这条路径查不出任何东西**——错误的诊断连带给出了无效的对策。

**已修**：
1. `api_client.chat()` 返回 dict 追加 `"status": prog["status"]`（纯追加，既有模式；
   现有测试全按键取值、无键集全等断言）。
2. `agent_loop`：`status == "response.incomplete"` → `stopped_reason = "incomplete"`。
   用 `.get()`，brief 那 5 条不带该键的桩**未改一字**仍通过。
3. 新增 4 条测试（loop 2 + api_client 2，含反向用例防恒真）。
4. `stopped_reason` 枚举 2 值 → 3 值，消费契约「**只有 `finished` 才算完整**」已写进
   模块与函数 docstring。

## I-2 订正：「模型外推」的定性与证据相反

**我原先写的**：回答末段关于 8501/8506/8508 的内容「超出工具返回的字面内容」，是模型
「从 recall 文本推演」，据此建议 T4 提示词加「只报工具查得到的」。

**错在哪**：我没有把工具的实际返回打出来核对，凭印象判定。实跑
`uv run python tools/agent_tools.py get_anchor --args '{"id":8478}'`，`recall` 字段里
**逐字写着**：

> 「…本场（scene_s1s_300）尤其危险：サクラ 本场共 5 句，仅开口这句用汉字，其后
> 8501/8506/8508 三句全部回到片假名，且 8508 已锚定并注明「称呼不变」…」

**模型一个字都没外推，是逐点忠实转述。** 这次冒烟的正确定性是：**「模型忠实转述工具
返回」的正面证据**，是 loop 做对了的地方。

**为什么这条必须改**：按我原来的定性去写 T4 提示词，会**压掉模型这次做对的事**——
把 recall 里的约束整合进答案，恰恰是审计要的能力。**订正后给 T4 的设计输入是：
不要加「只报工具查得到的」这类抑制性约束**（它会误伤对 recall 的正常转述）。

**真正该防的两条**（本次冒烟都没暴露，故均无证据、只是待防）：
- 模型**压根不调工具**、凭先验作答（brief Step 5 预见过；这次没发生，单例不足以说明常态）。
- **工具失败被静默吞掉**、模型照样自信作答——这条是我代码里的**真实结构问题**：原实现把
  `json.loads(raw)` 与 `call_tool(...)` 包在同一个 `try` 里，于是 `lane_dir` 传错、
  `anchors.yaml` 缺失这类**系统性故障**，会与「模型给了非法 JSON」一样降级成一条
  `{"error": …}` 回灌，loop 继续跑、最后报 `finished`。
  **已修**：两个 `try` 拆开，`result_summary` 分别标 `kind: bad_arguments` / `tool_error`；
  返回值加 `tool_errors: int`（只计工具执行失败），T5 不必 grep 字符串。新增 2 条测试。

## m-1：`-1` 哨兵毒化 token 合计（已修）

`pin += last.get("prompt_tokens", 0) or 0` 的 `or 0` 只挡 None/0，挡不住 `-1`。我复现：
第 1 轮 500 + 第 2 轮 -1 → loop 返回 `prompt_tokens = 499`，**总数被减**且无任何标记。
`api_client.ledger_token()` 的 docstring 大篇幅警告过这条失效模式，loop 原样重犯了。
**已修**：累加改走 `ledger_token(last, key)`，取不到就跳过该轮并置返回值 `tokens_estimated: True`。
新增 2 条测试（含「全部已知时不得误标 estimated」的反向用例）。

## m-2：运行时 `web_search` 闸的假阳性（不改行为，已写进 docstring）

确认存在：它 `json.dumps` **整个 payload** 后查子串，`input`/`instructions` 里的正文
也在扫描范围内。实测「作者提到 web_search 关键词」→ 直接 `SystemExit`。
**宁严勿松的取舍保留**（正是串级扫描挡住了 `builtin_tools` 那类改键名绕过），但这条
已知代价现已写进 `chat()` 里那段注释，并注明「将来若真要在正文里谈这个词，改的应该是
『只扫非正文字段』而不是删掉这道闸」——别让后来者踩了当 bug 修。

## m-3：黑名单缺口（已补两项 + 已降低承诺）

补入 `os.system(` / `os.popen(`（封 `subprocess` 的理由同样适用，全仓现无此用法，零成本）。
黑名单现 17 项。另按评审要求在断言 docstring 里写明：**这是回归绊线，不是安全边界**
——`from os import makedirs` 这类裸名导入、`getattr` 拼接都能绕过；只读的保证来自人工
通读（T1 评审做过）与设计意图，不来自这条子串断言。绊线真的会红：往 `agent_tools.py`
末尾追加一行 `os.system(...)` 注释即令该用例失败（已实测，随后还原）。

## 变异自检（全部离线，零真实请求）

| 变异 | 预期变红 | 实测 |
|---|---|---|
| 去掉 loop 的 incomplete 分支 | incomplete 用例 | 1 failed ✅ |
| token 累加退回 `or 0` | -1 哨兵用例 | 1 failed ✅ |
| 去掉 api_client 的 `status` 键 | 2 条 status 用例 | 2 failed ✅ |
| 两个 `try` 合并回原样 | tool_error / bad_arguments 两条 | 2 failed ✅ |
| 往 agent_tools 塞 `os.system(` | 只读断言 | 1 failed ✅ |

全量：**379 passed**（371 + loop 6 + api_client 2）。

## 修正后仍存的顾虑

1. 多个并行 function_call 的真实形状仍未实测（T2 遗留）。loop 按数组遍历逐个执行逐个回灌，
   形状上支持；冒烟只出单个 call，未验证。
2. `tool_errors > 0` 目前只是**报给调用方**，loop 本身不改变行为（不中止、不换
   `stopped_reason`）。是否该让系统性故障直接终止循环，取决于 T5 的审计语义，留给 T5 定。
3. 本轮修正后**未再发真实请求**（评审明确不需要）。故 `stopped_reason="incomplete"`
   与 `tool_errors` 两条新路径只有离线证据，未在真机上见过。
