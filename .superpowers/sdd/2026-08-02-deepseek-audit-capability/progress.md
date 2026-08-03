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
DS-T3: complete (commits 5ecefcb..ccf8b4d, 含 1 轮修正, review clean) — tools/agent_loop.py + 顺手两条；379 passed
DS-T3: 冒烟——模型**真的调了工具**（rounds=2，给两个工具只用了 get_anchor），台账第二轮 cached_tokens=384 证明纯文本回灌保住了前缀缓存
DS-T3: 评审推翻实现者的**两条自陈顾虑**（此处是本波最值得记的方法论）：
  I-1 「partial 会让 loop 静默收尾」**指错机制**——partial 走 StreamAborted、异常穿透 loop，**是大声失败的**；真凶是 `response.incomplete`（在 TERMINAL_EVENTS 里 → _consume 正常返回 → chat() 正常返回，而返回契约里没有任何一位能表达「被砍断了」）。且实现者提的兜底「T5 查台账 partial 行」**对真凶完全无效**——评审实测 incomplete 的台账行与正常调用**完全同形**（usage 齐全、无 partial 无 estimated）
  I-2 「模型外推了工具没返回的内容」**结论与证据相反**——评审把 get_anchor(8478) 的实际返回打出来，`recall` 字段**逐字包含**「其后 8501/8506/8508 三句全部回到片假名」，模型是忠实转述、一字未外推。**这次冒烟是「模型正确整合 recall 约束」的正面证据**。按原定性给 T4 加「只报工具字面返回的」会**压掉模型做对的综合能力**
DS-T3: **方法论留痕——自陈的顾虑本身也需要被复算**。这两条读起来非常合理、甚至显得作者警觉，若评审只「读报告+看 diff」会原样通过。挖出来靠的是追代码路径、把工具实际返回打印出来。「自陈的问题」天然带可信光环，恰恰最容易被跳过验证。控制器也一度原样转述了 I-2 给用户，一并被纠正
DS-T3: 修正落地——chat() 追加 `status` 键（纯追加，该 dict 已追加过 4 次）→ loop 映射 `stopped_reason="incomplete"`，枚举 2 值变 3 值、「只有 finished 才算完整」写进 docstring；拆开 json.loads 与 call_tool 的 try（分标 bad_arguments/tool_error）+ 返回值加 tool_errors 计数；m-1 token 累加改走 ledger_token（实证 500+(-1) 不再被减成 499、取不到置 tokens_estimated）；m-2 web_search 整串扫描的误伤代价写进注释（不改行为）；m-3 黑名单 15→17 项 + docstring 写明「回归绊线非安全边界」
DS-T3: 复评独立复现全部实证 + 3 组变异（去 incomplete 分支/合并 try/累加退回 or 0）各自精确变红无附带杀伤；brief 原 5 条 stub 逐字未改；报告订正遵守「保留原文 + 追加订正」纪律
DS-T3: **给 T4/T5 的订正输入**（替代原错误定性）：①提示词写**接地要求**而非抑制约束——每条判定标注依据的 tool call 与字段名，无法标注即显式标 unverified；②**机械闸优于提示词**——T5 收结论前断言 `tool_calls` 非空、`tool_errors == 0`、`stopped_reason == "finished"`，三条缺一即判本次审计不可采信。提示词只能劝，这三条是能验的
DS-T3: deferred（留档）：①并行多 function_call 形状仍未实测 ②incomplete 与 tool_errors 两条新路径只有离线证据、未在真机见过——**修的是「万一发生时不会静默」，不是「让它不发生」**，两者常被混为一谈 ③tool_errors>0 只报不改行为，是否中止由 T5 的审计语义定（控制器倾向：loop 是通用设施，该判断属任务层）
DS-T3: **复评自曝一次操作事故**（值得记的纪律教训）：它的第一版探针脚本遗留一处未注入 transport 的真实调用，误发了一次真实 API 请求（114 tokens），随后用 `git checkout -- data/api_ledger.jsonl` 复原。两点问题：①在生产会话并行追加的仓库里对**共享的已跟踪文件**用 `git checkout --` 有误删他人未提交行的风险（本次侥幸只丢了它自己那行）②按本项目既定的记账纪律，真实发生且已计费的调用**本就该留在台账里**，丢弃它等于让花费被系统性低估——正是 api_client 的入账门槛注释反复警告的那类失效
DS-T4: complete (commits 5e38fb0 + 0866a1d + 修正 1e55211, review 需修正→已修) — tools/audit_notes_promises.py + tests；385 → **392 passed**
DS-T4: 实现者按派发要求自行加了 `quote_verified`（模型给的「提案原话」去空白后是否真是正文子串），处置正确：**校验不过只打标不丢弃**——模型对原话做省略号截断是合理改写，机械闸过滤掉会变成误伤。与 DS-T3 订正确立的方向一致（机械闸负责留痕，判定权留给下游）
DS-T4: **复评验实控制器提出的线索——解析失败静默坍缩进「无承诺」（阻断级）**。探针实测：模型吐「抱歉，我无法访问该内容」与模型正常吐 `{"promises": []}`，`extract_promises` 返回值**完全相等**，全仓搜索确认无任何 side channel。后果：全量跑 366 条时若干条解析失败会与「确实没有硬承诺」无法区分、静默计入 clean，而报告顶部的「无法判断占比」本是可信度指标——那个指标会因此是假的。直中 spec §4.4（不得强迫二元判定）与 §5（恒绿关卡）
DS-T4: **恒绿的一个新变种：文档替不存在的闸站岗**。`_ask_json` docstring 里「非 JSON 视为空结果**并留痕**」这四个字是实现者在 brief 原文之外**自己加的**（brief 原句无此四字），而留痕机制根本不存在，报告「顾虑」节亦只字未提。缺机制未来还有人会去找；文档说有机制，就没人再去找了。**比缺实现更坏**
DS-T4: 复评另挖一条控制器未预见的：`ids or prewire_ids(proposal)` **跨子句污染**。构造真实形态（提案前半段带 id 5001/5002、后半段是与之无关的通则声明、模型正确返回 `ids: []`），实测那条通则承诺被强行接上 5001/5002 = **凭空制造错误的依据行归属**，而 T5 正要拿这些 id 去取原文译文核对，等于拿错行审对的承诺。掩盖原因很典型：**测试里所有用例的 ids 都恰好等于 prewire 结果**，该分支从未被走过
DS-T4: **真实数据复算（本项目最看重的那种验证）**：复评用 cluster_notes.parse_notes 跑 pilot/lanes/opus/data/notes/*.md 全部 455 条真实提案、对照 ledger.jsonl 合法 id 全集 → **0 条越界、0 条真实跨行合并**。但合成用例证实 `\s` 字符类能吞下一行数字（`id 100、101\n  202、303` → 抽出四个）。照修的理由不是「现在错了」而是**「语料还在长」**——生产会话此刻仍在往这些 notes 追加提案，排版一出现缩进延续行就会中
DS-T4: 另两处静默造假 id（当前语料未触发）：字符类含全角 `０-９` 但 `NUM_RE` 只认半角 = **捕获了却悄悄丢掉**；`isinstance(i, int)` 对 `bool` 亦为真，探针显示 `ids: ["abc", 7327.5, True, "007"]` 被清洗成 `[1, 7]`——`True` 变成**虚构 id 1**
DS-T4: 恒绿测试排查（打坏成恒返回 `[]`）：3 红 3 绿，其中 2 条绿属预期（期望输出本就是 `[]`）。套件整体不恒绿。唯一问题是那条 malformed 用例**断言范围小于文档承诺**——名字与 docstring 都承诺验证「留痕」，实际只断言 `out == []`
DS-T4: `PROMISE_SYS` 复评逐字节核对 331 vs 331 与 brief 一致、**未被加抑制性约束**——DS-T3 订正确立的方向守住了。修正轮为支撑三态判据**追加了一行接地要求**（「若该承诺不针对具体 id，ids 请显式给 []，不要省略该字段」）：是接地要求不是抑制约束，且是 ids_source 能成立的前提
DS-T4-fix: **`extract_promises` 改签名为 dict（T5 照此写）**：`{promises, parse_ok, stopped_reason, ok}`；每条 promise 含 `kind/ids/ids_source("model"|"prewire")/prewire_ids/ids_invalid/quote/quote_verified`。**三态判据：`ok and promises`→有承诺；`ok and not promises`→确认无承诺；`not ok`→没读懂（无论 promises 是什么都不得计入 clean）**。`ok = parse_ok and stopped_reason == "finished"`，把 DS-T3 那条「只有 finished 才算完整」的消费契约接上了
DS-T4-fix: id 归属改为**不做不可逆合并**——模型显式给 ids（含 `[]`）不再被回退覆盖，仅 key 缺失才用 prewire；两路分开保留并标 `ids_source`，`prewire_ids` 始终额外提供，**回退与否交 T5 决定**。非法项显式丢弃并记入 `ids_invalid` 留痕，不再静默转成看似合法的 id
DS-T4: **给 T5 的输入**：①`quote_verified`/`ids_invalid`/`ids_source` 目前都只是信息位、无任何下游消费，T5 必须**显式决定**怎么用（不用也要说明为何不用）②DS-T3 定下的三条机械闸（`tool_calls` 非空、`tool_errors == 0`、`stopped_reason == "finished"`）在 T5 收结论前断言 ③`not ok` 的提案必须流进报告顶部的「无法判断」占比，这是该指标不为假的前提 ④字段命名是修正轮在无 T5 实现时自定的，**落地前改代价还低，落地后不再改签名**
DS-T5: complete (commits ce32f95 + 修正 6f5800e, review 需修正→已修) — VERIFY_SYS/verify_promise/render_report/main；392 → 408 → **415 passed**
DS-T5: **三条机械闸落地**（DS-T3 订正确立的「提示词只能劝，机械闸才能验」）：①stopped_reason != finished ②tool_errors != 0 ③开了工具却一次没调 → 任一不满足强制降「无法判断」并在 reason 写明是哪条闸。**闸③的边界是关键**：预拼路径不给工具，那里 tool_calls 空是正常的，若也开火就是系统性误伤（本可判定的全变「无法判断」、占比指标反而失真）。复评用真实调用路径复算了「预拼不误开火 / 工具兜底确实开火」两侧
DS-T5: 三个信息位均**显式做了决定且代码里真实发生**（复评变异验证，非仅写在报告里）：`quote_verified` 仅在显式 False 时作 caveat 呈现、不作闸；`ids_source=="model"` 且 `ids==[]` 时**不回退** prewire_ids 而转走工具兜底（尊重 T4 的跨子句污染防护，改成回退则专测立即变红）；`ids_invalid` 透传进报告作质量标记、不改 verdict
DS-T5: **复评挖出控制器与实现者都未盯住的一条（应修）：`main()` 无任何异常隔离**。变异实测：让第 2 条提案的 verify_promise 抛 RuntimeError → 进程直接死、rc 未返回、报告文件不存在，**连第 1 条已算出的「已履行」也一起没了**。不是「分母缩小」而是全部结果连同已发生已计费的调用一起从存在中消失。T6 全量跑约 100 次真实请求，跑到第 80 条偶发一次网络异常＝前 79 条的钱与结论全废
DS-T5-fix: 已修——逐条 try/except（抽取与核对两处），失败变成**可见结果**（`_forced_cannot_tell`，reason 带异常类型+消息），绝不静默吞掉或计入已履行；修前 rc=None 无报告，修后 rc=0、报告含「已履行 1 + 无法判断 1」且异常文本可见
DS-T5-fix: **增量落盘**（sidecar `.jsonl`，与 --out 同名，每条结果算出即落盘、开跑时截断）。理由是本项目既有纪律在结论侧的延伸：`api_ledger.jsonl` 已记了每次调用的账，但**结论**一崩就没——账在、结论不在，等于钱花了拿不回东西。遗留：无自动 resume/merge，中途死需人工判断是否续跑
DS-T5: 复评第二条（可记录，已一并修）：**预拼路径的 `call_tool` 不在任何 try/except 里**，机械闸②（tool_errors）对这条路径**根本不生效**——闸建起来了但守的是另一扇门。且 `get_lines` 对不存在的 id **静默返回 jp=None/zh=None**，模型拿空材料照样可能答「已履行」
DS-T5-fix: 补**闸④「材料为空」**：取回的行全都没有译文时强制降「无法判断」。**边界写死**：只在**全空**时开火——部分有部分没有是正常情形（该批可能只译了一部分），在那种情况下开火会把大量本可判定的承诺误降成「无法判断」，**反而把可信度指标搞脏**（另一种形式的假指标）。两侧各钉一条测试（全空开火且模型根本没被调用 / 部分空不开火）
DS-T5: **首次真跑（s0f，5 条提案）**：抽出 2 条硬承诺、均「已履行」、0% 无法判断。复评独立复算 id 6351（zh=杏仁核、内嗅皮质）与 6130（zh 含「操场角落…眺望着场地」）确认结论成立；并读 s0f.md 原文确认被排除的 #2/#4/#5 **全是「建议…」纯倾向措辞、无「已按…处理」字样**，入选的 #1/#3 各嵌一句既成事实陈述。**spec §4.2「只审硬承诺」的裁决第一次在真实数据上被验证可执行**，无建议误判、无硬承诺漏检。但样本仅 5 条，0% 占比不可采信
DS-T5: 复评认可但不阻断的一条：报告顶部**两个独立诊断数**（抽取失败提案 N 条 vs verdict 阶段无法判断占比）而非合并成一个数。控制器判断：不合并是对的——「无法判断」是**审了但材料不足**，抽取失败是**根本没审到**，合并会让「没审到」伪装成一种审计结论。但存在「只扫一眼 0% 误以为全干净」的风险，留 T6 人工抽核时评估
DS-T5: 复评核对 G：`git diff 1e55211 ce32f95` 对 audit_notes_promises.py **无任何删除行**，T4 五个函数未被触碰——纯追加纪律守住
DS-T6: Step1-2 播种检验 4/4 全绿（commit c98095c，419 passed）。**假 runner 设计得比 plan 更强**：不是「模型说什么就返回什么」的木偶，而是**确定性机械裁判**——只读被预拼进 user 消息的【相关行】、按可复算规则作答。于是每条违约用例还能额外断言**违约译文逐字出现在提示里**（材料没送到就会红）；违约组与合规组**共用同一规则、只换数据**，排除「无论喂什么都判违约」的假绿。变异自检：verdict 钉成「已履行」→ 3 failed / 1 passed
DS-T6: **控制器在 brief 里新增了 plan 没有的「先量再跑」闸，触发了**。计时试跑 `--limit 20` 实测 6:08、50 次真实调用（比 plan 估的「每条一次」翻倍——核对走工具兜底时每轮一次调用），外推 473 条 ≈ 2h25m。执行者按闸停下未擅自开跑。**一次性长任务先量后跑，是这一步最值钱的纪律**
DS-T6: 试跑挖出**三条会毒化全量跑的缺陷**，共同点是——它们抬高的是报告顶部那个「无法判断占比」，而该指标本该衡量**语料证据是否充分**，被工具缺陷污染后就成了又一个假指标：
  ①`prewire_ids` 不认区间写法 `id 17050–17121`（字符类不含破折号，只截首个 id）→ 要核「19 个标签整族统一」的承诺只送进 1 行材料 → **工具自己制造的「无法判断」**
  ②`verify_promise` **根本不把提案正文传给模型**（只传 kind+quote+出处+相关行）→ 承诺内容住在正文表格里的一律核不了。模型判「无法判断」诚实且正确，不确定是我们造的
  ③`evidence_ids` 用 `isinstance(i, int)` 静默丢字符串型 id，与抽取阶段 `_clean_model_ids`（接受 `"007"`）**同模块两套口径**
DS-T6-fix: 已修（commit f40fc8b，419 → **436 passed**，播种检验未改动仍 4 passed）。①破折号全谱 + `_TOKEN_RE` 保序消费单 id/区间，三重防爆炸（总数 100 / 单区间跨度 10000 / 起止倒置）**全部截断留痕**，新增 `prewire_ids_detail` 而 `prewire_ids` 签名不变 ②user 消息加【提案正文】（两条路径都传），6000 字符上限 + 显式截断标记 + 报告标注该条不可尽信 ③改用 `_clean_model_ids`，非法项记 `evidence_ids_invalid`
DS-T6-fix: **执行者用语料实测修正了控制器的交办描述**（值得记）：50 处区间只有 **14 处在提案正文里**，另 36 处落在 `## batch NN（id …）` 标题行、被 `parse_notes` 跳过；分隔符实际只有 `-`(6) 与 en dash `–`(45)、**无波浪号**（控制器猜的）。478 条全跑最大展开 72 个 id，上限一次未触发
DS-T6-fix: 试跑 v1→v2 对比：耗时 6:08→6:32(+6.5%)｜硬承诺 17→14｜调用 50→44｜**无法判断 2→0（11%→0%）**｜evidence_ids 为空 3→0｜verify 首轮 prompt 中位 470→787(+67%)、均值 541→1213、max 951→5818
DS-T6-fix: **crd b10 #2 从「无法判断」翻成「已履行」，且执行者独立复算比模型更强**：把提案表格 20 行写成 dict，对 `get_lines(17050..17121)` 全部 72 行取行首标签逐一比对 → **ok 72 / 违约 0 / 未译 0 / 表外标签 0**（模型只列了 18 行依据）。缺陷 1+2 造的假不确定确认消除
DS-T6-fix: 执行者顾虑（控制器认可，全部留档）：①两次试跑 31 条承诺**零「未履行」**，播种证明工具能判违约但真语料零命中仍缺独立佐证 ②**「无法判断 0%」≠ 可信度 100%**——修完缺陷 2 后该指标只反映材料够不够、**对「模型判错」不再敏感**，需另一条独立信号 ③两次运行的**承诺集合不重合**（17 vs 14），「2→0」不是同一批承诺上的对照实验，可确定的只是 v1 那两条的直接成因已消除 ④两处上限当前语料一次未触发＝未压测，全量若出现 ⚠ 留痕行**应复核阈值而非直接调大**
DS-T6: 全量跑快照（2026-08-02 20:32，HEAD f40fc8b）：8 个 notes 文件、**485 条提案**（crd 181 / s2s 103 / s1s 85 / s3s 67 / s1f 19 / s0f 12 / s2f 12 / sys 6），ledger 151 行。外推 ≈ 2h36m。**语料仍在长**（生产会话 SEG-2 在追加）：spec 写 366 → T6 开跑时 467 → 473 → 478 → 485
DS-T6: **全量审计最终账（三批定点重跑后）**：1408 条硬承诺 / 485 条提案 → 已履行 1379→**1410**、无法判断 114→**82**、未履行 14→15。**可信度指标 7.6% → 5.4%**
DS-T6: 32 条「无法判断」被解出（part1 8 / s2s 7 / s3s 17），全部来自 `--max-rounds` 6→16。**这 2.2 个百分点本就不是语料问题，是工具预算不足造成的假不确定**——5.4% 才是真实反映「材料够不够判」的数字
DS-T6: **14→15 那条新增「未履行」是误报，已复算推翻**（s2s b56 #6）：模型按 id 数值区间圈「本批范围」，把不属于 batch 56 的 10108/10112/10118/10122/10129【熊三郎】行当成反例。实扫全批说话人分布 `アヤノ 71 + ユウイチ 70 = 141`，**手记原话成立**。故本轮重跑**未发现任何新的真违约**，全部价值是清掉 32 条假不确定
DS-T6: **四分类要补一个亚型：「依据行选取错误」**。它不是「字面比对过严」——比对本身可能很严谨，但依据行根本不在承诺覆盖范围内，结论即不成立。成因：**批次的 ids 不是连续区间**，而模型倾向按 id 数值区间理解「本批」
DS-T6: **一条被复算推翻的自我论断（留痕）**：控制器见 s2s 出现「无法判断→未履行」时，曾判断「说明提高预算不只是把不确定变成没问题、也会变成有问题，故模型是真的在判」。复算发现唯一的反方向翻转正是那条误报 → **该论据不成立**。就现有证据而言**无法排除「给够预算后模型倾向判已履行」的偏向**；排除它需要另做实验（往重跑集播种已知违约看能否捞出），本轮不作结论
DS-T6: 三批重跑翻转方向：part1 8/8 → 已履行；s2s 6 → 已履行 + 1 → 未履行（误报）；s3s **17/17 → 已履行**
