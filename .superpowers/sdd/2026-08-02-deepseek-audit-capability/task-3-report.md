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
