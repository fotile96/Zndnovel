# SDD ledger — plan: docs/superpowers/plans/2026-08-02-p3-devwave1.md

执行分支：`main`（沿用点火轮的用户批准；本 plan 同属 CLAUDE.md 允许直提 main 的工具代码/文档类日常改动）。
起点：`fd81aca`（docs: P3 开发轨第一波实施计划），基线 234 passed。

**并行状态**：生产会话正在同一主仓工作树跑 SEG-1（b36–62）。全程铁律——只 `git add` 显式路径、
不碰 `pilot/lanes/` 数据与 `prompts/`、改主仓直调工具（gen_plan/saturation/resolve/lane_setup）
须向后兼容且有回归验证、数据再生成先证明对在产批次无影响。

预扫描备注：Task 3 含「生产安全预检」决策树（证明不了就改落分支 `fix/f7-ledger-line`）；
Task 8 Step 3 是用户抽核硬 gate、Step 4 需 DEEPSEEK_API_KEY（用户稍后提供，无 key 时记「跳过」不阻塞）。

W1-T1: 评审 Important——含多个 `→` 的标题（顿号分隔多词小族）使 extract_terms 只切首段当词键，产出 24 个「伪装成正常词族」的乱码词键（如「建议入 active.json：カード」），各自跑 saturation 得「0/0 无出现」的**假零证据信号**；而真词 カード 在 ledger 出现 453 次。裁决会话若信该信号即误判。裁定修法：`→` 计数 >1 直接归 UNKEYED（不做多词解析，不违反 brief 的「不扩展」约束）
W1-T1: 评审实测未归词簇 108/224（48%）构成：约 36 条真无词项（自查记录/★存疑/杂项兜底），约 72 条有词项但标题未用 `→`（裸词+id、无箭头 `/` 并列、引号对举、词簇枚举）。实例后果：メモ/待ち合わせ/ハンバーガー 三词各有正常词族，同时各有一条同主题提案躺在未归词里未合并
W1-T1: parked（评审可选建议，本轮不做）：未归词段渲染时用子串匹配给「参见 §<词族>」提示，进一步压低人工全扫的心智负担
W1-T1: 并行观察：生产会话在本任务执行期间向 pilot/lanes/opus/data/notes/s2s.md 追加了 49 行提案（纯追加），本工具只读未触碰——并行纪律成立，提案总数由 ~216 涨到 224
W1-T1: fix round 1/5 (1 addressed, 0 open — F1 多箭头乱码词键：extract_terms 判据 `"→" not in t` → `t.count("→") != 1`；commit e4b7468) — 复评全量验证：21 条多箭头标题 100% 归 UNKEYED；对全部 95 单箭头 + 108 零箭头标题跑新旧 extract_terms 比对 mismatch=0（全量非抽样）；241 passed；词族 120→101、未归词 108→129
W1-T1: complete (commits fd81aca..e4b7468, review clean) — tools/cluster_notes.py + 7 测试
W1-T1: deferred（独立问题，非 F1 残留，复评已定性）：8 条「描述性冒号前缀 + 单箭头」标题仍产 look-alike 乱码键（如「存疑请人工复核：7705はうっ！」「建议入 active.json：デジャブ」），成因是 STRIP_RE 未剥冒号类前缀，修正前即存在；若后续要修需一并处理全角字符与反引号
W1-T1: 并行观察：生产会话已入线 b36（88 行）并建了自己的段台账 .superpowers/sdd/2026-08-02-p3-seg1-s2/；两轮 commit 均只碰自身路径，无交叉
W1-T2: 评审 Critical——实现者为修「brief 字面 F9 代码打破 2 条既有测试」加的 `zh != jp` gate 过弱：整行照抄+一个字符扰动即全额豁免。全 ledger 16101 行实测 C1 召回 98.5%→36.3%（末尾加「。」）/52.7%（日文标点换中文标点），是降噪改动引入的**探测能力净损失**，丢的正是 C1 唯一目标。裁定修法：加豁免预算 gate（豁免假名字符数/len(zh) ≤ BUDGET 且 novel_share ≥ 0.05），阈值实测 0.32/0.40/0.50 三档后按「零新增误报 + 对已观测最大合法引用占比 0.316 有 ≥25% 余量」选定；写模块常量不加 CLI（避免 canary 口径分家，同 M1）
W1-T2: 评审 Important——①测试只锁 zh==jp 精确相等，63.7% 的漏报洞在 CI 上不可见，须补「zh = jp + 。仍报 C1」的测试；②验收只算 FP 减少未算 TP 损失，是本次问题的直接成因
W1-T2: 评审独立复算 canary 45→28（C1 21→4、C2 2→2、C3 22→22），消失 17 新增 0，分布 batch19×10/31×4/26×2/30×1，与报告逐项一致
W1-T2: deferred（本轮不处理）：`m.group() in jp` 是任意位置子串判定、不校验位置，实测无影响
W1-T2: fix round 1/5 (Critical+2 Important+3 Minor 全 addressed，0 open；commit 567a323) — 预算 gate JP_QUOTE_BUDGET=0.40 + JP_QUOTE_MIN_NOVEL=0.05，模块常量无 CLI；246 passed
W1-T2: 复评独立重算标定表与实现者逐格相同（0.32/0.40/0.50 成本均 4，漏报 8.6/13.1/18.0%）；已观测最大合法豁免占比复算为 0.3158（id 8300），0.40 余量 26.6% 达标。评审此前引用的 12.5% 复评同样未复现，判定实现者披露诚实、不影响结论
W1-T2: 复评实测 F1 效果（全 ledger 16101 行）：`jp+"。"` 伪装 C1 召回 36.7%→86.9%，标点互换 46.2%→93.5%；真实译文侧零变化，12 条合法引用行无一被打回，扩到已入线 4525 行 old→new 判定变化 0 条
W1-T2: complete (commits e4b7468..567a323, review clean)
W1-T2: deferred（复评范围外观察，留终审分诊）：①真正吃紧的是 JP_QUOTE_MIN_NOVEL=0.05 而非 budget——它出力更大（单开即把漏报 63.3%→21.2%）但余量仅 5.2%（最小合法 novel=0.0526，恰是 id 8300），下次先破的是这道门；②test_f9_approx_copy_with_punct_swap_still_caught 在修前代码上同样通过（被 JP_QUOTE_MAX_LEN 拦下），不具回归守护力，宜换成汉字切短段的句子；③novel 用未剔角色名的原始 zh 计算，方向上略放松 gate，当前数据无影响
W1-T3: 预检判定「落 main」——生产树 build_context 在只差 ledger 的两个镜像 repo 上跑，context.md/source.jsonl/manifest.json 逐字节相同。实现者换掉了 brief 的预检设计（--repo 下 ZND_DATA 不参与、且产物会落进生产车道），改用 scratchpad 双镜像仓，经评审读码核实理由属实
W1-T3: 评审独立复现预检并给出更强证据——3 个批次（70/80/41）+ 阴性对照（改一条 jp 即检出差异，证明装置有灵敏度）+ **时间旅行**：用旧账本重造生产会话 07:45 已发出的 batch 41 上下文，与其实际产物逐字节相同。另全量回验 16749 条 line 与 lua 实际行号 0 处不符
W1-T3: 评审 Important 1——**F7 只修好一半**：段边界再生 timeline 只修前缀正文顺序；批次自身 source.jsonl 行序取自已冻结的 batches.jsonl，本轮永不修复，而 P2 记录的原始症状（17181 排到 source.jsonl 第 58 位）恰在这一半。runbook 未言明，须补残留说明
W1-T3: 评审 Important 2——47 vs 21 的归因错误。两数各自正确、只是口径不同：21/16248=timeline 单元内相邻对 line 递减；47/16529=ledger 按 lua 文件分组按 line 排数 id 递减（分母 16529=16749−220 文件）。timeline.jsonl 全历史仅 1 commit、lua 零改动、47 今天可逐位复现——**P2 报告不需要第二次订正**。运维取 21
W1-T3: 评审 Minor：build_ledger 注释「47」与 gen_timeline 注释「21」打架且均无口径；报告「23 条既有测试」实为 21；write_jsonl 非原子替换而生产实时读 ledger（不改共用工具，改为 runbook 写明数据再生成只在段边界且须确认生产不在跑）
W1-T3: fix round 1/5 (2 Important + 3 Minor 全 addressed，0 open；commit 9e3fd63，纯注释/文档改动) — 复评独立复算 21/16248 与 47/16529 均逐位吻合，另复算第三行 30/16529 亦吻合；确认 timeline.jsonl 全历史 1 commit、lua_scripts 自初始导入零改动；tools/ 下每一改动行都是 # 注释、无逻辑变更；251 passed
W1-T3: complete (commits f27897f..9e3fd63, review clean) — runbook 新增「F7 覆盖面残留」与「执行时机纪律」两节，复评判定「两周后接手的人可仅凭该段回答哪半修了/为何/修另一半的代价」
W1-T3: deferred（复评未能复现，非承重）：口径表第四行「25/16520（batches.jsonl 每批内相邻对）」方法未写明，复评按最佳猜测得 136/16575，差异源于 ids 数组里 829 个非整数 extra id（如 plotTitle:N）的处理方式。运维只用 21/16248，该行不承重；若将来要引用需先钉死定义
W1-T3: 方法论留痕（值得后续复用）：评审验证「改动共享数据而生产在跑」时用了**时间旅行**——拿改动前的账本重造生产会话已发出的 batch 41 上下文，与其实际产物逐字节比对。比模拟环境 A/B 强一个量级，证明的是「在产那份本身没受影响」。凡此类任务均应采用
W1-T4: complete (commits 9e3fd63..5cce3a5, review clean) — 段模式强制 --tools-root + segments.yaml 加 lane 字段并交叉校验；255 passed
W1-T4: 复评独立复做逐字节回归用了 8 组输入（chapter 模式/车道模式含 batch33 窗口探针/纯批号/空 sel×2/collapse_thresholds×3），全部 sha256 一致；实跑 handoff 换段命令模板 seg2-s3 得 34 任务、b63-90、114 条生产树前缀、0 条裸相对残留，产物已删、在产计划 hash 未变；三条错误路径均报错退出不静默
W1-T4: 复评核实实现者改的两条既有测试是最小改动（各只多一个 --tools-root 入参，断言逐字未动）；segments.yaml 的 lane 字段 9 段与 batches.jsonl 实算全一致，变异测试确认错配值与整段缺键都能被拦下
W1-T4: minor (deferred): 非段模式漏传 --lane 的错误呈现变了（argparse exit 2 + usage → 自定义 SystemExit exit 1 + 中文提示），语义仍必填但非「一字不变」，未被任何测试断言文本/退出码
W1-T4: minor (deferred): segment_range() 已成死代码（main() 改调 segment_entry()，tools/ 与 tests/ 再无调用点）
W1-T5: complete (commits 5cce3a5..a22a9a5, review clean) — 三条补锁测试 + canary 头注订正；258 passed
W1-T5: 复评对三条测试逐条做变异测试（临时副本改坏实现）：①saturation 去掉 key 分支→红 ②canary --diff 返回值改恒 0→红 ③gen_plan 空 sel 分支删段尾块→红。三条均有真实守护力，无假绿
W1-T6: complete (commits 39f4d89..db8d44f, review clean) — tools/api_client.py + 3 测试；261 passed
W1-T6: 复评安全核查全过：diff 无凭据字符串（仅 sk-test/sk-abc 假值）、未创建 .env、未改 .gitignore、缺 key 在构造 payload/headers 前即 SystemExit 且只暴露环境变量名、台账字段不含 key、无日志/异常泄漏路径。零网络独立验证：把 socket.socket/create_connection/urlopen 全换成一调用即抛的假函数后跑测试仍 3 passed
W1-T6: minor (deferred，留给消费侧)：响应缺 usage 时 token 计数兜底为 -1（brief 指定的哨兵值），下游若直接 sum() 台账两列会被污染，需显式过滤/特判
W1-T6: minor (deferred)：PROVIDERS 表的「提供商无关」建立在 OpenAI 兼容响应结构假设上，接入结构不同的提供商仍需改 chat() 解析逻辑，非纯配置项
W1-T7: 评审 Critical（**归属 brief 设计缺陷，非实现者违规**——实现对 brief 逐字节忠实）：assemble_context 把全部 196 张卡无条件拼进前缀，而卡组含**本段题目的字面答案**——卡 41 是 ナゾトキ 迷宫答案原文照抄、卡 44/45/46 是周末去处伏笔（卡 45 标题逐字＝plan 示例题的标准答案「游泳池的约定」）、卡 58 是 s2s_390 夜晚判定、卡 134 是第 2 章整段梗概。受试模型一行译文不看即可满分 → 工具在唯一用途上产出**系统性假绿**。叠加全知纪律违规（卡 141/142 泄 s7f 真相）。定 Critical 的理由：runbook §5 已把它写成段末验收环节，恒绿的关卡比没有关卡更危险
W1-T7: 裁定修法——前缀只取**严格早于当前段**的卡（非「当前段及之前」，否则卡 134 仍泄题）；卡→章映射优先取 analysis/crd_summary.txt 的触发章节字段，不足时补 snr_common.lua 的 sceneId2aCard（注意 CLAUDE.md 记载的 keyword 键重复噪声），固化成 config/card_chapter.yaml 入库；**无法归章的卡默认排除**（少一张只是前缀略薄，多一张则整个测试失效）；补反剧透闸与前缀非空闸两条测试（后者防过滤写过头把工具从恒绿变恒错）
W1-T7: 评审核实 runbook §5 改写（箭头链→1-5 编号清单）语义完全等价、原四步一字未削弱、与 §1.1/§4 无矛盾；dry-run 归因正确——cards.zh.yaml 的 58019 是**字节**数（中文 UTF-8 三字节 + YAML 结构 + 未用的 tr_note），实拼入 9185 字符，评审用装饰开销算术反推误差为零、确认 196 张一张不落。**brief 预期的 6-15 万字符本身算错了**（把字节当字符）
W1-T7: deferred（本轮不做）：①正文按 batches ids 的消息号序拼接而非阅读序，收益要等段边界再生 timeline 才兑现，现在改只增数据耦合；②config/ayano_qa/ 目录尚不存在（Task 8 产出），runbook §5 第 3 步已标「可选」对冲
W1-T7: fix round 1/5 (Critical F1 + Minor M1 addressed；commit 37c2762) — 前缀只取严格早于当前段的卡，新增 config/card_chapter.yaml（196 卡全覆盖：157 场景卡 + 13 章节梗概卡 + 25 关键词卡 + 1 编外卡）；266 passed；seg1-s2 前缀 196→46 张
W1-T7: 复评穷举验证 9/9 段零违例（独立重算表逐卡判定 max(章出现段) < 当前段）；确认「保守取最晚段」方向恒为多排除（max 集是 min 集子集，max独有在 9 段全为空）；157 张场景卡与独立产物 scene2card.json 逐条比对 157/157 全中；13 张梗概卡逐个 grep myCard[N].hold 命中；keyword 噪声正确避开（195 行 sceneId2aCard 中 38 行是 keyword 噪声，真实键恰 157）
W1-T7: fix round 2 触发——复评变异测试发现**静态数据无测试守护**：变异 C（真实 card_chapter.yaml 把 41:s2s 篡改成 41:s1s，答案卡放回 seg1 前缀）与变异 D（整个清空为 {}）**全绿放过**。两条新测试用合成 fixture、不读真实配置，守住了过滤代码没守住那 196 条手工推导数据——「恒绿的关卡比没有关卡更危险」在下一层重演。裁定：补读真实配置的数据闸（全覆盖 + seg1 不含 41/44/45/46/58/134/141/142 + 每段前缀非空），且要求实现者自做变异自检
W1-T7: fix round 2 另修两条——①未归段章节 fallback 到段 0＝**静默纳入**，与文件头宣称的「无法归章默认排除」方向相反，改安全方向但须保留 s0f/s1s/s1f（seg1 前缀全部来源）；②plan L791-930 仍内嵌未修版实现，照它重跑 task-7 会原样重引入 Critical，加勘误注记指向 37c2762
W1-T7: fix round 2/5 (F2 数据闸 + F3 fallback 安全方向 + F4 plan 勘误，全 addressed，0 open；commit f65dd45) — 267 passed；复评独立复做变异 C（41:s2s→s1s）与 D（清空）均变红，补做 E（删一条卡）亦变红；seg1-s2 前缀仍 46 张、9 段卡数全部未变；白名单 PRE_P3_CHAPTERS={s0f,s1s,s1f} 显式区分「确知早于全部段」与「未知」，未知一律排除
W1-T7: complete (commits e1640e0..f65dd45, review clean, 2 fix rounds)
W1-T7: deferred（复评变异 F2 发现，留终审分诊）：反剧透断言只硬编码 8 个卡号（Critical 的原始证据），**清单外的卡被误改成更早章节仍会漏网**——实测把卡 140（s6f→s1s，不在清单内）改错，全套测试全绿。可能的加固：用独立事实源做全量交叉校验（157 张场景卡对 data/scene2card.json，13 张梗概卡对 lua 里的 myCard[N].hold 授予点），这是非同义反复的独立验证，不是把 assemble_context 逻辑在测试里重写一遍
W1-T7: deferred（复评范围外观察）：数据闸断言 2 用 `body not in ctx` 整段子串匹配，不如直接断言卡号不在 prior_cards 集合里稳健
W1-T8: 用户抽核 gate **通过**（2026-08-02，选「放行，入库」，q14「姐姐去世」措辞维持原样）；首跑时机裁决：**等 SEG-1 译完后整套跑 15 题**，不跑 10 题子集试水
W1-T8: complete (commit 见下, review pending) — config/ayano_qa/seg1-s2.yaml 15 题；结构自检 OK（12≤n≤15、四字段齐全、id 唯一）、剧透自检无命中；Step 4 连通冒烟跳过（无 key），data/api_ledger.jsonl 未产生；267 passed 未变
W1-T8: 出题者留下的实况（生产会话可能想知道）：s2s_170（アヤノ 答「喜欢ユウイチ」）尚未译，而同一选择的另一支 s2s_180（「太近了」）已译——该分支对是夜晚成立三条件之一，q6 因此处于半译状态。非缺陷，只是段未跑完
W1-T8: 评审 Approved（无 Critical）+ 2 Important。逐题可答性表 15/15 通过：信息点全部落 b36-62 内、**无一题越界 b63+**、无一题需日文原文或他章正文；剧透语义复核通过；q14「姐姐去世」经查确在段内原文（analysis/text_digest/snr_s2_10_f.txt 的 scene_s2f_60 由加里转述小学教师的话，逐条对齐 vms 9072/9091→b59），**不是从 CLAUDE.md 全局真相带出来的**，无需改写
W1-T8: 评审 Important I1——READER_SYS 要求「两三句以内」作答，而 15 题 reference 长 107-196 字（q10/q14 含 3-4 个事实块），系统性错配会使几乎每题判「部分对」、信号压平，首跑分不清「译文丢信息」与「答不满字数」
W1-T8: 评审 Important I2——q13 问「哪两个问题」，原文 s2f_40 千秋实际连问四处（CHI00480/00520/00530/00540），受试者可能挑另一对，判分无从裁定
W1-T8: 评审 Minor：M1 info_point 的已译/未译标注已过时（出题时 b46，现 b56，q6/q11/q12 均已有译文，实际只剩 q13/q14/q15 未译）；M2 q11 题面「被什么东西引上天台」无文本依据、可能诱导编造；M3 三处引导式设问（q2/q6/q8）先说了半个答案；M4 三条件之一 s2s_350 无独立题目；M5 报告把 q9 归 s2f 实为 crd
W1-T8: 用户提供 DEEPSEEK_API_KEY（已在 .env，git check-ignore 确认被忽略）；指定测试用 deepseek-v4-flash
W1-T9（追加任务）：API 配置硬伤——timeout 硬编码 300s 不可配、PROVIDERS 写死 deepseek-chat 且 ayano_test 无 --model（**用户指定的模型进不去**）、无重试（15 题×2 调用，一次瞬时失败即整跑作废）、max_tokens 2048 固定
W1-T9: complete (commits ffed0a0..f0f8746, review clean) — api_client 超时/重试/max_tokens 可配 + ayano_test 模型透传 + 题库修 I2/M1 + READER_SYS/JUDGE_SYS 修 I1 + deepseek 真实冒烟；274 passed
W1-T9: 评审独立验证重试分类：401 不重试零 sleep、429/URLError 重试后成功 sleeps=[2]、连续 503 耗尽 4 次调用 sleeps=[2,4,8] 后抛原异常、retries=0 立即抛；全量测试 2.13s 证实单测不真 sleep。transport 三参契约经 functools.partial 闭包保住，既有 3 条测试一行未改。15 条 reference 程序化比对：仅 q13 首句加「千秋追问到两处：」衔接语，其余 14 条字符级完全相同
W1-T9: 实测发现（改变 API 风格取舍的关键数据）：现有 /chat/completions **已有上下文缓存**，同前缀第二次调用 20992/21065 命中（99.65%）；且 deepseek-v4-flash 在该端点上本就产出 reasoning_tokens（49/54），只是台账未记。reader 单次 21150 prompt tokens，15 题全跑约 32 万输入 token、其中约 30 万是重复前缀
W1-T9: 用户裁决——**切换到 Responses API（流式）**。理由：①CoT 可看 ②**流式 CoT 持续下行可避免长思考被 timeout 误杀**（这条比调大超时数字对症）。维持 chat() 对外接口不变，只换内部实现
W1-T10（下一任务）：评审给出的四条重写约束——①总请求超时改为**逐 chunk 静默超时**，只在真正断流时重试（现在把 socket.timeout 当网络错重试，对长思考是反效果：原样再等一个相同窗口）②**不要超载现有 transport 参数**（一次调用→一次完整 dict 的同步语义与流式天然不匹配），新开独立流式注入点，保住刚加固的 3 条历史测试与 ayano_test ③流式重试会丢弃已收 CoT 并重复计费，重试前须把已产生 token 计入 ledger，否则花费被系统性低估 ④429 应读 Retry-After 而非纯指数退避
W1-T10 风险提醒：Responses API 内置服务端 web_search——**彩野测试里一旦启用即灾难**（模型可上网查本作剧情，不看译文也能答对，测试静默失效，与本轮已踩两次的「恒绿关卡」同类）。必须显式不发 tools 字段并写测试防回潮
W1-T10: Responses API 流式改造完成（commits 55c9bda/9534179/41762f7），287 passed。实测：端点 /v1/responses 与 /responses 均 200 且事件序列一致（取前者）；deepseek-v4-pro 返 400「available starting early August 2026」，Responses 现仅支持 v4-flash；**缓存仍有效**（同前缀二次 cached 23424/23551=99.46%，与 chat/completions 的 99.65% 同量级）；**CoT 真能拿到**，q1 的 CoT 逐句引用译文原句、直接证明是从译文读出来的
W1-T10: 评审独立实证「真流式」——127.0.0.1 裸 socket 按节奏吐 SSE，总耗时 2.47s > timeout 1.0s（2.5 倍）仍正常完成、delta 到达时刻均匀铺开 → **socket 超时确为逐次 read 计时、确实逐事件消费**，抗超时动机落地。禁 web_search 防线经变异测试有效：直白加 tools 红、**改名 builtin_tools 绕过仍被原始 JSON 串的 web_search 子串断言捕获**、stream 改 False 亦被捕获
W1-T10: 评审 Important I-1——入账门槛 `if produced or partial["usage"]`（须已吐出 delta）与重试逻辑要救的场景（首个 delta 之前的 prefill 超时）**互斥**，导致唯一会触发重试的路径永远不写台账；探针实证「尝试 2 次、台账 1 行」。彩野测试输入侧是成本主导（23.5k in vs ~400 out），这笔重试花费账上不可见
W1-T10: 评审 Important I-2——`.done` 事件覆盖而非追加累加器，多 part 响应**静默截断**正文与 CoT（探针得 '222' 而非 '111222'）。2.35 万 token 输入 + high effort 正是最易产生多段推理的场景；「是否永远单 part」仅一次最小请求观察支撑、样本不足，故判 Important
W1-T10: 评审对判分盲区的诊断（比实现者自陈更准）：q4 真问题是**该题可被字符串检索答对**——答案在上下文里是可逐字复制的跨度，定位到旁证再抄前一句即可得分，不需理解推理链。暴露的是「答案层评分对检索型可答题天然失效」。且**不应把 CoT 直接喂判分员**（「需确认/大概」是常规对冲话术，真读懂也常出现，会推高误报并让分数挂钩不稳定的私有产物）。采纳其替代方案：加不改判分语义的机械分诊标记
W1-T10: deferred（结构性修复，非本轮）：给检索型可答题在题库里补追击问（如「为什么原作有问题会导致赝品被识破？」），让逐字复制无法得分。这才是根治
W1-T10: fix round 1/5（I-1 + I-2 + 顺手三条 + 新增机械分诊标记，全 addressed，0 open；commits a7db79b/955f666）—— 294 passed。复评独立重做两探针：I-1 台账行数 1→**2**（失败行 partial:true/attempt:1/estimated:true，零事件失败仍不入账有反向测试）；I-2 content '222'→**'111222'**、reasoning 'BBB'→**'AAABBB'**；多 part 夹具已按报告 §B 实测事件序列逐行重写
W1-T10: 实现者**主动修正控制器给的两个参数**，复评复核均成立：①逐字重合门槛 20→12（20 对 q4 实测 0 命中＝抓不到唯一已知真阳性；q1=7 字、q4=12 字）②裸问号从犹豫标记表去掉（复评实测重新加回即在 q1 干净 CoT 上产生误报——本作是视觉小说，对白问号密集）
W1-T10: 复评独立评估门槛 12 的误报风险（查真实语料而非空想）：cards.zh.yaml 的 196 个卡名里 **17 个（9%）本身 ≥12 字**（如「サクラ的日记：9月13日」「总有一天你会看到的故事。」），指认类题目的正确答案若恰是卡名/日期，会因合法引用专名被误标。建议：**先留 12**（抬高会重新丢 q4），跑更多段后统计误报构成；若专名/日期占主导，应**排除精确专名匹配**而非抬高全局门槛
W1-T10: 复评认可「不伪造 fixture」的取舍——为复现已知数字而造的 fixture 是不可证伪的假证据、语料变化时会静默腐坏；只钉边界语义（差一字不打标、够了就打标）是正确做法
W1-T10: complete (commits f0f8746..955f666, review clean, 1 fix round)
W1-T10: minor (deferred)：test_part_without_done_is_not_lost_when_next_part_starts 未真正锁住它声称守护的逻辑——复评实测把 content_part.added 的 flush 分支整个删掉，该测试仍通过（夹具里缺一个冲突的 .done 来暴露 bug）。建议补一例带 .done 的场景
W1-T10: minor (deferred，既有风险非本轮引入)：_verdict_head 按首个 `|` 切分，该格式契约完全依赖判分提示词、无测试约束
W1-FINAL: 终审修正波（一轮定稿，commits 55d9846..f588925，311 passed）——报告见 final-fix-report.md
W1-FINAL: C1 修复实跑 opus 车道：判「无出现」词族 46→5（13 脏键降级进未归词、28 键恢复真实证据）；bNone 95→0；卷宗 366 提案/110 词族（成词 109）。终审四例逐数复算一致（はい 396/0.422、意識 55/0.509、ワンパタ 7/1.000、視聴覚室 5/1.000）。仍判「未匹配」的 5 个键（クスクスと笑う/セクションその１/物語を創る/腕を組む/記憶が途絶える）经 ledger 独立复算确系真零出现——全是提案写成词典形、正文是活用形，措辞已改为「未匹配到该词键（可能提取不干净，请人工核对）」
W1-FINAL: 脏键判据用**语料字符集**而非拍脑袋字符表——键里出现 ledger jp 中根本不存在的字符即不可能是本作日文词。副作用：ledger 为空/残缺时会全量降级（安全方向，但表现为「卷宗突然全是未归词」，靠 done= 自述行辨认）
W1-FINAL: I2 的测试按指示写成**断言当前漏报事实**（「照抄+前后各加中文短语仍应报 C1」实测为红，未为其改实现/放宽阈值）；A/B 表进 runbook §4.0 作为滚 prod-run-v3 的人工判定材料。独立复算（另一组填充短语）得 98.5/82.4/77.8/64.3/50.1/66.5%，与终审表同量级。**取舍本身仍悬着**：在人做出判断前，detect_collapse 对「包裹型照抄」只有约一半探测力
W1-FINAL: I3 收尾留痕——在产计划 translate-seg1-s2.md 不重新生成，其内嵌段末清单仍是旧五项（第 3 项是打 tag、无彩野测试）；runbook §5 与 handoff 各加一条本段例外提示，下一段起两边自动一致
W1-FINAL: 明确未做（记账）：T7 L60 card_chapter.yaml 全量交叉校验（SEG-2 起前置）、台账其余 deferred minors、config/ayano_qa 只有 seg1 一份题库（seg2 起段末第 3 项会走「无题库→跳过」分支，出题工作量需排期）

## 终审修正波复评（opus）：11/11 ADDRESSED，判定可交付
复评独立复算：C1 词族「无出现」46→5（当前实况 48→5），5 个残留键经 ledger 逐个复算确系真零出现（皆为提案写成词典形、正文用活用形）；**35 个键恢复出真实证据**（多于终审估的 28），抽查 11 个数字全对；13 个降级键中 12 条确该降级且全部 total=0，本轮零证据损失。I3 非段模式 **15 组输入 sha256 全同、0 mismatch**；在产计划 blob hash 前后未变（编号例外写进 runbook+handoff 而非在产计划）。I4 跨段题库 rc=1 且在触达 API 前拦下，15 题内容 canonical sha 一致。I6 越界 rc=1、真子区间放行带横幅、显式全区间与省略 --batches 逐字节相同。I2 detect_collapse **全波空 diff**、常量未动，缺口测试断言的是漏报事实；复评自建 A/B 得最坏情形 41.4%（比终审表的 54.2% 更糟，图景一致）
**parked（残留 Minor，裁定不阻断交付，留下一波）**：
- P1 `is_clean_key` 会降级**有真实证据**的合法词键（`いつか きみが みる お話。` 3 次因含空白、`ＴｒｕｅＣｏｌｏｒ` 1 次因无假名汉字）→ 整簇进未归词且饱和度读数丢失。裁定：方向安全（不伪造 0/0）、量级 2/110，但**一行可修**（`total > 0` 即判 clean），建议段末裁决会话前顺手做
- P2 ledger 为空/缺失时全体降级且无点名告警（复评重建快照时真撞上：0 成词词族 / 372 未归词、rc=0 无告警）。裁定：安全方向，补一条告警即可
- P3 `ayano_test --qa <不存在>` 抛 FileNotFoundError traceback，而新写进计划/runbook 的第 3 项明说「不存在就跳过并记台账」——文档与行为不符。裁定：修前即如此、非本波引入，但现在这条路径被文档指引了，宜补 try/except
**parked（范围外，同类病可从另一扇门进来）**：`tools/saturation.py::main()` 仍把 ratio None 打成「无出现」且无脏键判据，而 runbook §5 裁决清单第 2 步正是让人手抄词表跑它。C1 的语义修复只落在 cluster_notes 一侧。裁定：风险已因卷宗词键变干净而大幅降低（手抄来源就是卷宗），但同一误读的入口仍在
Final review: clean（1 Critical + 6 Important + 4 Minor 全 ADDRESSED，3+1 条 Minor 已 parked 并留裁定）

## parked 三条清理（commit a6242b6）+ 复评
P1 is_clean_key 加 `total>0` 短路、P2 ledger 空/缺失点名告警（含顺手修的未处理 FileNotFoundError）、P3 --qa 不存在改 rc=2（三态：0 通过 / 1 真配置错 / 2 跳过）；316 passed
复评变异测试确认 P1 两条测试有真实拦截力（删短路→1 failed；写宽成 total>=0→3 failed，反向用例在防写宽）。**P1 在真实车道上是零覆盖空测试**——当前全车道没有任何键同时满足「pre-fix 判脏」且「total>0」，故 before/after diff 0 字节是必然结果而非验证通过；靠单测验证这两个具体例子，复评判定对该两例充分（单测用的 corpus/total 就是从真实 ledger 核实的值）
复评 Important 1：`gen_plan._segment_tail` 文案未同步 runbook §5——而该函数正上方注释明写「必须逐项对齐（终审 I3），改一边就改另一边」。该文本会渲染进未来每一段新生成的生产计划，是同类静默漂移换身位重现，且**规则明写在代码里仍然漏了**
复评 Important 2：P1 短路绕过了**全部**降级判据，但那些判据保护两类不同东西——「含语料外字符」被 total>0 绕过是严格正确的（有语料外字符则 count 必为 0），而 whitespace/WORDCHAR/**ASCII** 三条保护的是纯 ASCII/数字残渣，这类键**可以**有 total>0（实测子串 "12" 在 ledger total=1，命中 12時）。当前未触发只因现有三个无假名汉字键 882/2470/【】 的 total 恰为 0，是数据巧合非代码保证。裁定：短路收窄为只豁免 whitespace/WORDCHAR/语料外字符/长键四条，**ASCII 保持硬门**
parked 清理 fix round 1（commit 3720ebb）：2 Important 全 ADDRESSED，318 passed。复评独立复算五案例判定表全对（いつか…／ＴｒｕｅＣｏｌｏｒ clean；12／882／2470／【】／含空白+total0 dirty）；变异测试双向有效（ASCII 门挪回短路后 2 failed；短路整体删除 2 failed）；非段模式自建双加载对 5 组输入 sha256 全同；在产计划 blob hash 在 a6242b6／3720ebb／工作树三处均为 edb1f4d1，未被重新生成；真实车道卷宗数字（成词 111／未归词 276／降级 13）无变化
**方法论留痕（本波最值得记的一条）**：`_segment_tail` 的跨文件一致性规则**白纸黑字写在该函数正上方的注释里**（「改一边就改另一边」），仍然漏了。结论——**靠注释约束跨文件一致性不可靠，必须落成测试断言**。本轮已给该测试补上 rc=2 语义断言并变异验证
**方法论留痕之二**：控制器给的修法「total>0 即判 clean」论证有缺陷——该论证只对「含语料外字符」一条判据成立（有语料外字符则 count 必为 0，二者互斥），对 ASCII/WORDCHAR 那类判据不成立。复评用真实数据反证（子串 "12" 在 ledger total=1）。教训：**给「豁免所有检查」型修法时，必须逐条检查每个被豁免的检查各自在防什么**
Devwave1 收尾：全部任务 + 终审修正波 + parked 清理均 review clean，318 passed

## saturation 脏键门收尾（commits 223f728 / b34827f / ada1d5d）
把 is_clean_key 及依赖从 cluster_notes 迁到 saturation（避免循环导入，因 cluster_notes 本就 import saturation），两个消费方共用同一判据；saturation.main() 补脏键判定与 ledger 空/缺失告警。327 passed
**发现并堵住一个巧合漏洞**：`はい／いいえ`（全角斜杠）因全角 ／ 本身出现在游戏原文里而被判 clean、total=0 报「无出现」；而 `はい/いいえ`（半角）因半角 / 不在语料里被正确判脏——**判定取决于抄词表的人用了哪个斜杠**。而漏网的那种恰是终审假零证据表的第一行（真词 はい 396 次）。修法：total==0 且含并列分隔符时拆开各查，任一子串有出现即报「疑似并列词串，请拆开分别查」并列出各子串数字，两种抄法输出现已逐字一致
分隔符集合刻意不含 `・`——复评实测 ledger 里 22 次 `・` 全是 `です・ます`、`オ・ト・ナ` 这类原文书写惯例，加入会把固定搭配拆开产生噪音
**方法论留痕之三（测试与生产数据耦合）**：新测试一度钉死 `はい=167/396`。分母 396（全书出现总数）是冻结的，但**分子 167 来自生产会话每天追加的 forward.jsonl**，而 はい 的未覆盖分布横跨几乎所有未译章节——生产再推进一段就必变。危险不在于会红，而在于**红在与被测逻辑无关的原因上，会训练人忽略红灯**。改用合成 fixture（现算 ratio、与生产解耦）+ 一条只断言结构性质的真实车道测试。复评做了关键验证：**模拟生产推进 50 行后，旧硬编码断言已失效而新测试仍全绿**
Devwave1 全部收尾：327 passed，全部 review clean

## 彩野测试首次全跑（SEG-1，2026-08-02）
命令：`ayano_test.py --segment seg1-s2 --qa config/ayano_qa/seg1-s2.yaml --lane-dir pilot/lanes/opus --model deepseek-v4-flash`
上下文 48294 字符、**缺译 0 行**、15 题；耗时 2 分 19 秒；30 次调用、输入 486,299 tokens（**缓存命中 90.7%**）、输出 10,476（其中推理 8,817）
**段级结论：13 对 / 2 部分对 / 0 错——未检出信息丢失。** 两条部分对：q9 遗漏「记卡片」等具体承诺细节（真部分对）；q10 受试者补了「其实是为了去和サクラ见面」——该内容剧情上为真但不在 reference 里，判分员据此扣分，属**判分员对「正确但超出标准答案」的推断做了惩罚**，非译文缺陷
**⚠ 机械分诊标记不成立，建议停用**（本轮最重要的发现）：15 题打了 **10 个标记**，全部落在「对」上（对 10/13＝77%），而两条「部分对」**零标记**——与判分员自己的疑虑**反相关**，无区分力。构成：仅犹豫词 5（大概×4、需确认、应该是）、仅重合 3（13/15/17 字）、两者都有 2（12/19 字）
**致命的一条**：q4 —— 分诊标记当初就是为它设计的（冒烟时它「照抄得分但 CoT 写需确认」）——**本轮零标记**。同一题、同一上下文（且更完整），标记消失。根因是它**键控在模型 run-to-run 可变的私有推理文本上**，这正是当初评审警告「不该让分数挂钩不稳定私有产物」的那条，我把它用在了判分上却没用在标记自身
裁定建议：**降级为「打印 CoT 摘要供人读」，去掉自动 ⚠ 判定**（CoT 摘要本身有价值——q1 逐句引用译文原句证明是真读出来的）。不建议在 n=15 上重新标定：AND 化只剩 2 个标记但仍会漏掉 q4，说明问题在假设本身而非阈值
**题库侧观察**：0 错说明题目区分度偏低。SEG-2 题库宜提高推断依赖度（少问「文中说了什么」，多问「据此可推出什么」），并按终审建议给检索型可答题补追击问
