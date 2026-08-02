# SDD ledger — plan: docs/superpowers/plans/2026-08-02-deepseek-audit-capability.md

执行分支：`main`（沿用本项目既有批准；CLAUDE.md 轻量分支制允许工具代码/文档类日常改动直提 main）。
起点：`96ca011`（docs: DeepSeek 审计能力实施计划），基线 354 passed。
上游 spec：`docs/superpowers/specs/2026-08-02-deepseek-audit-capability-design.md`。

**并行状态**：生产会话正在同一主仓工作树跑 SEG-2（seg2-s3，b63–90，已入线到 b70），
其台账 `.superpowers/sdd/2026-08-02-p3-seg2-s3/progress.md` 处于未提交修改态——那是它的，不碰。
全程铁律：只 `git add` 显式路径；不碰 `pilot/lanes/`、`prompts/`、`2026-08-02-p3-seg2-s3/`、
`docs/superpowers/plans/translate-seg*.md`。

预扫描备注：
- T2 Step 1 与 T3 Step 5、T6 Step 3 会发**真实 API 请求**（DeepSeek，不吃订阅额度，总量几分钱）。
- T2 Step 1 是「探测未知线格式」型步骤，形状不符须停下报告，不得照假设写解析代码。
- T6 Step 4 是**用户抽核硬 gate**，未确认前不得声称审计可用。

DS-T1: complete (commits 96ca011..4884958, review clean) — tools/agent_tools.py + 7 测试；361 passed
DS-T1: 评审独立通读确认只读约束**真成立**（全文只 read_text/read_jsonl/yaml.safe_load/parse_notes/resolve_map，无网络无 subprocess，main 只 print）；冒烟三条全对，9441/9483 jp「人の事」vs 9460「人のこと」而三行 zh 完全相同，工具如实透传原文差异未做归一化；另补测缺行返回 null 不静默丢、search_lines 全库「彩野」3187 命中 truncated=true 标记正确
DS-T1: minor (deferred，**已折进 T3 顺手做**)：无写操作断言的黑名单漏了几类同样危险的写法，其中 `append_jsonl(` 是本仓库 pipelib 现成的追加写函数——最可能的误写路径恰恰不在名单内，与 card_chapter「清单外的卡被改早不会变红」同型。建议扩展为 append_jsonl/write_bytes/os.remove/os.rename/os.replace/shutil./subprocess/.touch(/rmdir(/os.makedirs(
DS-T2: complete — api_client 支持白名单内 function tools；365 passed（基线 361+4）
DS-T2: Step 1 探针（2 次真实请求）确认 DeepSeek function calling 线格式**与 OpenAI Responses 惯例完全一致**，零字段名调整：function_call item 带 `id`(item 自身)/`call_id`(call_00_…，续轮回引的是它)/`name`(顶层)/`arguments`(**JSON 字符串**)；参数走专用 `response.function_call_arguments.delta/.done`（载荷只有 item_id，无 name），**不发 content_part 事件**；终止事件 `response.output` 是扁平 item 数组。顺手实测续轮 `{"type":"function_call_output","call_id":…,"output":…}` + 原样回填 output items **被接受**，T3 无需再探（详见 task-2-report.md §④）
DS-T2: 守卫收紧非删除——变异自检 3/3 各自只杀对应用例（白名单成员 / type!=function / 缺白名单即拒），既有 `test_payload_never_sends_tools_or_web_search` 的原始 JSON 串级 `web_search` 断言未改一字且全程 PASS，新用例复刻同一条串级断言使白名单路径同样挡改名绕过；`tools/ayano_test.py` 未改动，仍零 tool
DS-T1: minor (deferred)：tool_schemas() docstring 称「同时也是 MCP tool 形状」不精确——MCP 官方 tool 是 {name, description, inputSchema}，无 type:"function" 且键名是 inputSchema 非 parameters。内层 JSON Schema 可直接复用，外层需改键名去 type。spec §3.3 承诺的「将来包一层即可」成立，但不是「零改动即是」，措辞宜订正
DS-T2: complete (commits 22944ae..5ecefcb, review clean) — api_client 支持白名单内 function tools；365 passed
DS-T2: **探针实测结论——DeepSeek function calling 与 OpenAI Responses 惯例完全一致、零字段名调整**：function_call item 同时有 id（delta 事件里叫 item_id）与 call_id（call_00_…，续轮引用后者）、顶层 name、arguments 为 JSON 字符串；参数走 response.function_call_arguments.delta/.done；**function_call 不发 content_part 事件**；终止事件 response.output 是扁平 item 数组。实现者顺手实测了续轮：{"type":"function_call_output","call_id":…,"output":"<JSON 串>"} + 原样回填上轮 output items **被远端接受**
DS-T2: 评审对探针可信度的独立判断＝高置信。硬证据：①sequence_number 28+1+9=38 自洽 ②id 是 UUID 而 call_id 是 call_00_+22 位，两套风格符合「两个不同的东西」③终止事件含 content_filters/moderation/prompt_cache_retention 等**非 OpenAI 标准的 DeepSeek 特有键**——照 OpenAI 文档编不出来 ④续轮正文引用的正是探针脚本捏造的 tool 结果。另确认代码只依赖 response["output"] 与 type=="function_call" 两处，call_id/name/arguments **一个都不读**（原样透传给 T3），无隐蔽 fallback
DS-T2: 评审自加变异 D/E/E2/E3。**E 发现守卫边界**：调用方若把 "web_search" 塞进自己的白名单，客户端 function 声明会被放行。评审正确定性为**不构成作弊通道**——客户端 function 声明不会让服务端联网；真正危险的服务端内置工具走 type 一路、被 E2 证明焊死（`只允许 type=function`）；历史上的 builtin_tools 改名绕过需改源码另加 payload 键，而既有测试解析整个 raw payload 照样抓得住
DS-T2: **设计决定——T3 维持 plan 的纯文本回灌，不改结构化**。探针虽已确认结构化续轮可用，但它需要 chat() 能接受预构建 input items（回填上轮 output items），是比 plan 预期更大的接口改动；而纯文本方案**尚未被证明不够用**。「不确定性消除了」不等于「该换方案」——等真实审计里暴露问题（如模型分不清工具结果与用户输入）再换，那时有证据而不只是有选项
DS-T2: minor (deferred，**折进 T3 顺手做**)：串级 web_search 断言只是**测试级**不变量，运行时不存在。建议 chat() 加一行 `if "web_search" in json.dumps(payload): raise SystemExit(...)`，把它升级为运行时闸，成本一行无副作用
DS-T2: minor (deferred，**T3 实现者须知**)：partial 路径拿不到 output_items（_consume 不处理 response.output_item.done，流在终止事件前中断时该键恒空）；且 function_call_arguments.delta 不计入 text_deltas/reasoning_deltas，**估算记账会系统性低估纯工具调用轮的 output token**。有界循环若遇重试要意识到这两点
DS-T2: minor (deferred)：①探针报告是整理稿非原始 stdout（评审给高置信但无法逐字硬保证，因代码只依赖两处、爆炸半径极小）②三条拒绝型用例未传 sleeper，变异时会真 sleep 14 秒 ③_validate_tools 不校验 tools 是 list[dict]，传字符串会 AttributeError 而非干净 SystemExit ④**多个并行 function_call 的形状未实测**（响应有 parallel_tool_calls 字段但本轮只出单个），留给 T3
DS-T3: complete — tools/agent_loop.py + tests/test_agent_loop.py（brief 代码逐字采用）；371 passed（基线 365 + loop 5 + 串级闸运行时用例 1）
DS-T3: **Step 5 真实冒烟＝loop 首次真实验证，模型真的调了工具**（不是猜）：`rounds=2 stopped=finished tools=['get_anchor']`；给了 get_anchor,get_lines 两个，模型只用 get_anchor（返回已含 jp/zh/recall，够答题），回答含预期的定译「彩野同学」并复述了 v7 汉字呼名装置的锚定规则。台账两行 478+79 / 770+343，**第二轮 cached_tokens=384 → 前缀缓存命中**，证明纯文本回灌保持了「原对话+追加轮次」的前缀形状
DS-T3: 纯文本回灌**未见**模型分不清工具结果与用户输入（它明确称之为「工具返回」）——目前没有换结构化回灌的证据，与 T2 设计决定一致。但回答末段外推出工具没返回的内容（8501/8506/8508 的写法、8508 已锚定），审计提示词需约束「只报工具查得到的」，留给 T4
DS-T3: 顺手 ① 无写操作黑名单 5→15 项（含 append_jsonl/write_bytes/os.remove/os.rename/os.replace/shutil./subprocess/.touch(/rmdir(/os.makedirs(），agent_tools.py 未改一字仍通过；② 串级 web_search 升级为 chat() 内的**运行时闸**（payload 构造后、发请求前），补 test_web_search_in_payload_is_refused_at_runtime 并断言拒发时根本没走到 transport；api_client.py 除这一行外未动
DS-T3: 新顾虑（deferred）：**partial 路径会让 loop 以 `finished` 静默收尾而非 max_rounds**——流在终止事件前中断时 function_calls 恒空，loop 视同「无工具调用」提前返回半截 content。「到顶不静默」这条不覆盖「流中断」。当前不改（要动 api_client 返回契约，已过三轮评审）；建议 T5 消费侧查台账 partial 行，或将来给 chat() 加 was_partial 标志、由 loop 转成 stopped_reason="stream_aborted"
DS-T3-fix: 评审 I-1/I-2 均成立，**上面 DS-T3 那两条自陈顾虑一条指错机制、一条结论与证据相反**——原文不删，追加订正（task-3-report.md「修正一节」），保留过程本身作为「不要相信自陈，要能复算」的实例。379 passed（371+8）
DS-T3-fix: **I-1 真凶是 `response.incomplete` 不是 partial**。自行复现离线探针（零真实请求）确认：partial 路径抛 StreamAborted 并**穿透** run_with_tools（loop 的 except 只包工具执行不包 chat），是大声失败；而 incomplete 在 TERMINAL_EVENTS 里，chat() 正常返回、usage 齐全、**台账行与正常调用完全同形**（无 partial 无 estimated），故原建议「T5 查台账 partial 行」对这条路径查不出任何东西。已修：chat() 追加 `status` 键（纯追加，既有模式）→ loop `stopped_reason="incomplete"`（用 .get()，brief 5 条桩未改一字仍通过）。**枚举 2 值→3 值，消费契约＝只有 finished 才算完整**，已写进 docstring
DS-T3-fix: **I-2 订正——「模型外推」的定性与证据相反**。实跑 get_anchor(8478) 打出 recall 字段，8501/8506/8508 那段**逐字写在返回里**，模型是忠实转述、一个字都没外推。这次冒烟是「模型正确整合 recall 约束」的**正面证据**。**给 T4 的订正输入：不要加「只报工具查得到的」这类抑制性约束**，它会误伤对 recall 的正常转述。真正该防的是「压根不调工具」与「工具失败被静默吞掉」两条（本次均未暴露）
DS-T3-fix: I-2 附带的**真实结构问题已修**：原实现把 json.loads 与 call_tool 包在同一个 try 里，lane_dir 传错/anchors.yaml 缺失这类**系统性故障**会与「模型给了非法 JSON」一样降级成 error 文本回灌、loop 照报 finished。现两个 try 拆开，result_summary 分标 kind: bad_arguments / tool_error，返回值加 `tool_errors: int`（只计工具执行失败）
DS-T3-fix: m-1 已修（token 累加改走 ledger_token，-1 哨兵不再把总数**减**掉——实证 500+(-1)=499 无标记；取不到即置 tokens_estimated=True）；m-2 不改行为、把「整串扫描会误伤正文里的 web_search 字面串」这条已知代价写进 chat() 注释（宁严勿松的取舍保留）；m-3 黑名单补 os.system(/os.popen( 共 17 项，并在 docstring 写明**这是回归绊线不是安全边界**（裸名导入/getattr 拼接均可绕过，只读保证来自人工通读而非子串断言）
DS-T3-fix: 变异自检 5/5 各自只杀对应用例（去 incomplete 分支 / 累加退回 or 0 / 去 status 键 / 合并 try / 往 agent_tools 塞 os.system(），全部离线零真实请求
DS-T3-fix: 遗留顾虑：①并行多 function_call 形状仍未实测 ②tool_errors>0 目前只报不改行为（是否该中止循环取决于 T5 审计语义）③incomplete 与 tool_errors 两条新路径只有离线证据，未在真机上见过
