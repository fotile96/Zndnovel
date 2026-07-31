# SDD ledger — plan: docs/superpowers/plans/2026-07-31-p2-pilot-tooling.md
# 工作台：main 直提交（仓库 CLAUDE.md 规约「main 分支直提交」，用户已批准；本会话无并行写树）
# BASE(T1 前)=ea4e317
# spec: docs/superpowers/specs/2026-07-31-p2-pilot-design.md
# 规约提醒：本工作台下的 *.md 需 `git add -f` 入库携带（CLAUDE.md「SDD 工作台」节）
# pre-flight 扫描：计划自身一处措辞矛盾已修——Global Constraints 原写「纯标准库」，
#   与 Tech Stack「依赖仅 pillow/pyyaml/pytest」及 T5/T6/T7 实际用 yaml.safe_load 冲突，
#   照字面读会诱使实现者手写 YAML 解析；已改为「不得新增第三方依赖，可用既有 pyyaml」
Task 1: complete (commits b2d05d6..3fcc6b6, review clean) —— spec ✅ / Approved，零 C/I；16/16 测试
Task 1: minor (deferred): 两条均承袭 brief 原文、无功能影响——①test_cli_without_repo docstring 说用 ZND_WORK 实为 monkeypatch 属性 ②monkeypatch pipelib.WORK 那行对本路径惰性（build_context 用 import 期绑定的 _WORK 别名，真正生效的是 patch bc._WORK）
# BASE(T2 前)=3fcc6b6
Task 2: complete (commits 3fcc6b6..06ce37d, review clean) —— spec ✅ / Approved，零 C/I；20/20 测试；实测 batch 1=52,583、batch 32=177,789 字符（spec 预期 51,900/177,100，偏差 +1.3%/+0.4%）
Task 2: ⚠️ 项已由控制器核实结清——评审指出压缩丢弃的不止 recall，还有 anchors.yaml 头部裁决日志。逐项核查其实质内容在新 context 中仍全部可见且各有仍内嵌的来源：腕→手/手臂 在 style.md「润色尺度」第1条、回家的歌谣/Happy End 在 active.json、直哉哥在新内嵌的 voices/chiaki.md、逐字沿用规则在新第三节标题 → 零信息损失，非缺口
Task 2: minor (deferred): 章别分组 `### {chapter}` 仅被单章夹具覆盖、无 "### " 断言（真实 19 章仅在 Step5 手工跑过）；section-ordering 用例只断言 voices 在第五节之前、未断言在第四节标题之后；压缩连带丢弃 anchors 头部注释（已核实无信息损失，见上）
# BASE(T3 前)=06ce37d
Task 3: review — spec ✅（brief 给全码处逐字一致；三个散文函数落实到位，实现者另修两处 brief 未点名的路径残留，评审独立复扫确认车道模式零残留）/ quality Approved
Task 3: Important[plan-mandated]×2，待人裁：
  #1 --batches 模式下 label 占 chapter 槽位 → 检查点让人看 notes/<label>.md（实际提案写在 <chapter>.md，永远看不到）+ 终任务 git log 过滤 <label>（实际 commit 是 data: <章> 批次N，过滤恒空）。控制器已实测复现（6 批段横跨 s0f/crd/s1s/sys 四章）；与计划自身 _header 文案直接矛盾
  #2 test_no_lane_cfg_output_is_byte_identical_to_repo_mode 名不副实（只查 3 个子串）；且 12 条 brief 用例无一能抓住 _checkpoint_task/_final_task 的路径残留——实现者自查修掉的那两处若漏修，全绿照过
Task 3: minor (deferred): _header 的 commit 消息说明在 --batches 模式下不准确（描述性文本）；_parse_range 用 __import__("re") 不地道（brief 原文）；select() 同时给 chapter+batch_range 的 AND 语义未测（CLI 不可达但 T8 可能直调）；两条改写用例的原解释性 docstring 丢失
Task 3: 用户裁定（2026-07-31）：#1 取「算出真实章别集合」、#2 取「补车道模式模板断言 + 改名」（不做 golden 逐字节）
Task 3: fix round 1/5 — chunk 真实章别去重排序传入检查点、终任务改批号区间口径、_header 描述改字面 <chapter>、补车道模式段内路径残留断言并改名（e2ac88b）；再评审：7 项全部 ADDRESSED，评审者自建隔离突变复现断言判别力、并证 _lane_block 故意的仓库路径在 header 段内不会误伤；16/16 gen_plan 测试、全量 136/136
Task 3: minor (deferred): 多章别检查点文案「该章」单数指代在列出多文件时不贴切（本轮新引入，纯文案）；_final_task 的介绍句与 Step1 仍把 label 当单一章别描述（评审判为本轮 scope 外，实现者已诚实标注）；_paths() docstring 称覆盖「全部产出路径」但改名后的用例只抽查 3 个子串；「章末」标题在跨章段计划里措辞不贴切
Task 3: complete (commits 06ce37d..e2ac88b, review clean)
# BASE(T4 前)=e2ac88b
Task 4: review — spec ✅（三处改动逐字落地；评审独立核实第三/四节描述与 build_context 实际渲染逐字相符、7 份口调表名单与 reviewer_cc.md 名单一一对应）/ quality Approved
Task 4: Important[plan-mandated] ×1 —— 路径基准的两张封闭清单漏了 data/ledger.jsonl 与 data/batches.jsonl（模板后文自己引用，子代理只能猜）。**控制器裁决直接修，未占用用户**：与 T3 那两条不同，本条无设计选择——补全枚举正是该节自述目标，且不与计划任何文本冲突；评审已给出确切修法。风险本就低（该批文件在车道内是指向仓库同一份的符号链接，两种猜法读到同样字节）→ 进 fix round 1
Task 4: minor (deferred): 实现者报告的一致性结论系抽样非穷举（正因此漏掉上条）；`glossary.vN.yaml` 裸文件名省略目录成分（沿袭既有文风，非本次引入）
Task 4: fix round 1/5 — 路径基准补第三类「只读符号链接数据文件」并与车道私有的 forward/notes 对照点明（ba1028f）；再评审：三子项全部 ADDRESSED、穷举核对属实（非抽样）、无新增破坏
Task 4: minor (deferred): 新增句「两种写法都不会出错（哪怕结果字节完全相同）」的「哪怕」是让步连词、逻辑反了，应为因果（建议改「——因为读到的本就是同一份文件」或直接删该括注）；控制器发现，再评审未察（其判「语法正确」）。操作性指令本身无歧义，不阻断
Task 4: complete (commits e2ac88b..ba1028f, review clean)
# BASE(T5 前)=ba1028f
Task 5: implementer DONE_WITH_CONCERNS (3d5f789) —— 上报简报计数笔误（散文 8 条 vs 代码块 7 条），未为凑数自造测试（判断正确）；控制器核实系计划笔误、五接口覆盖完整，已修计划文本（bd6b1a9，只动那一行）
Task 5: 首次评审因 ECONNRESET 中断未出裁决 → 重派（要求独立重做）。控制器同时清掉早先 prompt 预览遗留的 work/lanes/opus（内含 Task 2 之前的旧版 context 产物，留到 T8 会造成陈旧对照）
Task 5: review — spec 主体 ✅ / quality **Needs fixes**：Important×1（非 plan-mandated，直接进修复轮）——verify() 在「车道被删」「冻结文件缺失」两种情形抛未捕获 FileNotFoundError 栈回溯而非可诊断漂移行，main --verify 亦透传异常；三种边界仅「manifest 不存在」优雅退化。评审已在 /tmp 隔离副本实证复现。安全网自身炸掉 ≈ 漂移检不出，且这两种破坏正是人手滑最易造成的
Task 5: minor (deferred): record() 无直测（仅经 verify/main 间接覆盖）；main() 缺参 SystemExit 分支无测；verify() 的 got.get(k,'缺失') 为不可达死代码（本轮顺带清）
Task 5: fix round 1/5 — verify 捕获 FileNotFoundError 转可诊断漂移行并 continue、清死代码、补 5 条测试（9bc037d）；再评审：三子项+五条补测试全部 ADDRESSED、异常捕获范围判定得当（只捕 FileNotFoundError 不吞真 bug），但**遗留一条开放项**
Task 5: 再评审抓到假防护——`continue` 突变成 `return drift`（第一条坏车道后全不检查）时 12 条测试仍全绿，因五条新用例无一构造双车道 manifest；实现者自己那轮突变只证明了 try/except 有用、未证明 continue 有用 → 进 fix round 2（只补一条双车道判别用例，不改产码；要求突变对象为 continue 本身）
Task 5: fix round 2/5 — 补双车道判别用例（fable 删除＝异常路径在前、opus 内容漂移在后，字典序保证坏车道先被遍历），产码零改动（1c91c02）；再评审：ADDRESSED，突变 continue→return 时恰仅新用例转红、其余 12 条仍绿，顺序确定无 flaky
Task 5: complete (commits ba1028f..1c91c02, review clean) —— 13/13 lane_setup 测试、全量 149
# BASE(T6 前)=1c91c02
Task 6: implementer DONE_WITH_CONCERNS (8a73b45) —— 9/9 新测试、全量 158；Step5 真实语料（120 条锚点）0 告警。上报两点：①**擅自改了简报的 LOOP_RE**，重复单元下限 {6,}→{2,}，理由是简报自带 C3 用例（13 字符串/3 字符单元）在 {6,} 下数学上不可能匹配（此观察属实）②对 cards.zh 额外抽查 25 条 C1 命中，溯源为卡面硬折行劈开片假名人名（ア\nヤノ），判为图片版式产物、与 vms 管线无关，未改码
Task 6: 控制器实测量化 LOOP_RE 三种取值（退化样本 4 条 / 合法样本 7 条 / 定稿语料 510 条）：{2,}=4正确但**5/7 合法误报**（哈哈哈哈哈哈、呵呵呵呵呵呵、……………………、很好很好很好、卡面全角空格填充）；{6,}=0 误报但**只抓 1/4 退化**；**{4,}=4/4 退化 + 0/7 合法 + 0/510 语料** → 实现者发现的问题真、修的方向过头。数据已交评审独立复核裁定
Task 6: review — spec ✅ / quality **Needs fixes**：Important×1（LOOP_RE {2,} 大面积误报）。评审独立复现了报告全部可核对数字（Step5 0 告警、6 名白名单、长度降序替换、除零保护、158 全绿），并提出第三选项 {3,}（可通过简报原用例、无需改测试）
Task 6: 控制器补测中文三字情绪重复后否掉 {3,}——「对不起对不起对不起」「为什么为什么为什么」「别走啊别走啊别走啊」等 6/6 全误报（本作道歉/恳求场面极多，属合法台词）。**裁定取 {4,}**：退化 4/4、常见表达 0/7、三字情绪 0/6、定稿语料 0/510，是唯一三类语料皆零误报者 → 进 fix round 1（含改简报那条不具生产代表性的 C3 用例 + 补反向用例 + 双侧突变验证）
Task 6: fix round 1/5 — LOOP_RE 取 {4,} 并旁注四语料定值依据、改简报那条 3 字单元的 C3 正向用例为「我不知道」×3、补反向用例钉住合法重复不告警、retained_names 加作用域注释（7dc2a94）；再评审：八项全部 ADDRESSED，独立复现反向用例真有判别力（三串在 {2,} 下确告警、{4,} 下确不告警）、正向用例在 {6,} 下确失配（"两侧夹住"成立）、三阈值常量原封未动、其余 8 条用例逐条对照未被改写；Step5 重跑仍 0 告警；10/10 detect_collapse、全量 159
Task 6: minor (deferred): 反向用例只钉了「对不起对不起对不起」一例，prose 里另举的「为什么为什么为什么」「别走啊别走啊别走啊」未入测试；正向用例的日文侧示例是 5 字单元、与注释所述「4 字」措辞不符（纯文案，断言只作用于 zh 字段）
Task 6: complete (commits 1c91c02..7dc2a94, review clean)
# BASE(T7 前)=7dc2a94
Task 7: implementer DONE (909185b) —— 7/7 新测试、全量 166；上报简报内部不一致（接口表散文 anchor_ids -> set[int] vs Step3 代码返回 {id: zh}），按代码实现。控制器核实两处调用方都需映射、实现者选择正确，已修计划文本（f6a0a05）
Task 7: review — spec ✅ / quality Approved，零 C/I。评审实测验证三条设计意图：①奇偶交替真能去位置锚定——真实试点段 4282 id 奇/偶=2142/2140，各单元类型内部亦近 50/50（vms ID 按脚本顺序连续分配所致）②divergence 用锚点全集 120 作 exclude 与用段内 32 等价（common 已与两车道 forward 求交，段外 88 条永不出现）③anchor_compliance 的 total 口径正确（本车道 forward 覆盖到的锚点数，非全集）
Task 7: minor (deferred): import json 未使用（承袭 brief 原码）；无用例覆盖「锚点 id 缺席某车道 forward」的部分覆盖情形；violations 仅给 id、人工需自行交叉引用期望/实际文本（brief 强制形状）；stratified_sample 的 "unknown" 兜底分支未测；anchor_compliance/divergence 无函数级 docstring
Task 7: complete (commits 7dc2a94..f6a0a05, review clean)
# BASE(T8 前)=f6a0a05
Task 8: review — 机械正确性全项 ✅（评审逐批对照 batches.jsonl 核验 35×2 任务的章别/条数/字数、7 个检查点的章别集合、终任务批号区间、两计划归一化后零差异、他车道路径 0 处、提交范围干净），但判 **Needs fixes**：两条 Important 均为**前序任务代码的既有缺陷**、非 T8 diff 引入，而 T8 报告称「Concerns: 无」属漏报
Task 8: Important #1 —— gen_plan 的 _final_task 仍把 label 当章别用：真实产物里写「对照本章对应的章节梗概卡」，而 pilot-opus 不是章、skeleton/cards.zh 里没有这张卡；批次 1–35 横跨 s0f/crd/s1s/sys/s1f/s2s 且多章未完整。T3 fix round 1 只修了 _checkpoint_task 与 git-log 口径，_final_task 的卡片/锚点/查漏文案未同步（此前作为 minor 递延，现因落进真实执行计划而升级）
Task 8: Important #2 —— check_batch.py main() 硬编码 REPO/glossary/{speakers,active}.json（控制器已实证），不随 ZND_DATA/车道走；两个兄弟工具 build_context --repo 与 detect_collapse --lane-dir 都已车道化。影响澄清：两车道读同一份，故**不产生 A/B 偏袒**，破的是**冻结**属性——跨多会话跑 70 批期间仓库根 glossary 若被动过，早晚批次校验基准不一致且与 manifest 哈希对不上；R2b 说话人口径同理
Task 8: 控制器裁决——两条都在开跑前修，开 Hotfix D（一次覆盖两条 + 重生成两份计划）。理由：无设计分歧（终任务应像检查点那样列真实章别；check_batch 应像两个兄弟工具那样接受车道根），且都直接影响试点可信度
Hotfix D: 修两条 T8 评审揪出的前序缺陷 —— #1 _final_task 收真实章别集合并加「本段是 timeline 连续段而非完整章」提醒（2a449dc）#2 check_batch 加 --lane-dir 与 detect_collapse 同名同义、gen_plan 车道模式 Step3 带上它；重生成两份计划（cab0497）；SDD 证据入库（b124450）。173 测试全绿
Hotfix D: 再评审全部 ADDRESSED，零新增破坏。评审独立核实：终任务列全六个真实章别且任务段内零 label；--lane-dir 省略时逐字保持旧行为；车道词表用例的判别词「＠车道试验术语＠」确不在仓库 glossary 内（真判别非摆设）；突变自洽性经独立推导确认（第三条用例不涉 --lane-dir 故合理保持绿）；35/35 批次 Step3 带本车道参数、他车道 0 处；第三个 commit 仅含两份 SDD md 未夹带车道目录或评审包
Hotfix D: minor (deferred): _header() 的 H1 标题与 Goal 行仍写「pilot-opus 章」——同类 label-as-chapter 问题但位于 _header、本轮两条 finding 均未涵盖（评审列为 out-of-scope）
Task 8: complete (commits f6a0a05..b124450, review clean after Hotfix D)
# ==== 8 个计划任务 + Hotfix D 全部完成，进最终全分支评审 ====

# ==== 最终全分支评审（opus 档）：不建议直接开跑，2 Critical + 6 Important ====
FINAL: C1 两份执行计划里 spec 的四道验收闸门零出现（detect_collapse/隔离验收/硬停/lane_setup --verify/窗口对撞 grep 均为 0）——计划把它们划给「后续执行阶段」，但执行阶段拿到的只有这两份计划，trap #1（伪双车道）与 #5（拿 check_batch 当质量指标）的防线全部落空。控制器已实证
FINAL: C2 70 处 `git add work/lanes/...` 均因 work/ 在 .gitignore 内而必失败（git check-ignore 实证 .gitignore:15），且 8564 行译文（约 6.6M token 成本）无任何备份，spec §8「逐批 commit 历史」产出物与 T8「车道不入库」直接矛盾 → **用户裁定：车道移出 work/，改 pilot/lanes/，只 gitignore 其 work/ 子目录**
FINAL: I1 stratified_sample 位置退化（每层取 id 升序前 N），默认 per_kind=20 只覆盖 35 批中的 6 批、最大批号 29，batch 33-35（压缩窗口生效后）任何取值都进不了盲评材料
FINAL: I2 **又一处假防护，评审已突变实证**：删掉 append_forward 那行的 {p["env"]} 后 gen_plan 20/20 仍全绿——断言只查「全文出现过一次 ZND_WORK=…」而 Step3 已提供该次。此突变若为真，两车道 append_forward 都写进仓库根 data/forward.jsonl，A/B 合并成一锅
FINAL: I3 translator_cc.md 未随 Hotfix D 同步（自查命令仍无 --lane-dir，译者读仓库根词表、控制器读车道快照，冻结破口换了执行主体）；且第 41/43 行仍称第四节旧名
FINAL: I4 verify() 只做车道自比从不互比（两条车道若在仓库 glossary 变更前后分别 setup，各记各的哈希，--verify 永远绿而基准已不同）；compare_lanes 的 anchors/ledger/timeline 全取 REPO 而非冻结快照
FINAL: I5 lane_setup 重跑会静默重冻结并覆盖 pilot-manifest 基准，事后无法证明是否漂移过
FINAL: I6 窗口对撞探针破坏性：ctx_dir 不含 profile，--profile api-A 会原地覆盖同批的 context.md/manifest.json，写进 forward 的 ctx_sha 会记错
FINAL: 递延 minor 分诊 —— 10 组中 2 组「开跑前顺手修」（T4「哪怕」让步连词、Hotfix D 的 _header「pilot-opus 章」，均因同批要改同一文件而边际成本为零）、1 组「已无意义」（T2 章别分组无断言，评审在真实 context 上实测 19 个分组、120 条锚点全在）、其余可带着走；T7 的 violations 一条转为试点报告须知（两车道锚点覆盖数不同则 rate 分母不同，须同时记 total 不可只记 rate）
FINAL: spec 覆盖缺口 6 项：四道闸门无载体（C1）、pilot-manifest 缺车道配置与逐批机器指标、卡面回译自检工装缺失（compare_lanes docstring 过度宣称）、三段 workflow 边界(12/24)与 checkpoint-every=5 不重合、崩溃阈值标定值无固化去处、窗口对撞无对应任务
FINAL-FIX: 一次修复波覆盖全部 10 条（70cdef6 闸门+假防护 / daae5e6 车道迁 pilot/lanes / e29cdc8 重出计划 / 03a7af9 译者模板同步 / 82efd69 报告入库）；控制器另提交 spec 路径同步与 C2 裁决理由
FINAL-FIX: 范围内再评审（唯一一次）——**10 条全部 ADDRESSED，零新增 C/I**。评审实证：四道闸门在真实计划里各就位（硬停在 Task 2/4、冻结校验为每个 CHECKPOINT 的 Step 0、逐批探测确在 check_batch 与 append_forward 之间、窗口探针 Task 45 强制 cp 到 /tmp 副本并 rm -rf 收尾）；gitignore 否定规则成立（排除的是 data/* 文件级而非 data/ 目录级）；I2/I4 两处突变自洽；I5 拒绝逻辑不误伤（键于 forward.jsonl 是否已存在，非车道是否存在）；minor 的 _header 已改且 --chapter 模式逐字未变
FINAL-FIX: 评审自查出并自修两处本波引入的静态文案 bug（插入 Step 4 后 append_forward 变 Step 5，_header 与 _final_task 的 "Step 4" 引用同步，各带回归测试）
PARKED-1: data/notes/*.md 被 pilot/lanes/*/data/* 吞掉而 spec §8 列其为产出物 —— **控制器当场修**（.gitignore 加 !.../notes/ 与 !.../notes/*.md 两行；三种权威判定复验：git add --dry-run 成功、check-ignore 退出码 1、status 可见；其余四类规则回归未松动）。注：check-ignore -v 匹配否定规则时仍返回 0，判定须用非 -v 形式
PARKED-2: 硬停 2 若标定值偏离默认需重出计划，会重置 markdown 复选框状态（含已完成的批 1/2）——现仅由散文提示「从 batch 3 继续」缓解。裁决：可带着走，执行者按提示操作即可；P3 若沿用此机制可考虑把进度从计划文本外置
PARKED-3: 硬停 1 的 diff 命令在姊妹车道尚未产出 forward.jsonl 时会硬报错而非「无差异」——两条硬停按设计应邻近执行，风险低。裁决：可带着走，执行时若撞上按「对方车道尚未跑到此处」理解即可
# ==== P2 试点工装：8 任务 + Hotfix D + 终审修复波，全部完成并再评审 clean ====
# 收尾决定：**不删除本 SDD 工作台**——CLAUDE.md 规定 .superpowers/sdd/ 下 *.md 为不可再生的执行状态与证据须入库携带，项目规约优先于技能默认（与 P1b 同）
