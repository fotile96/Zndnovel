# 翻译流水线核心设计（上下文组装 × 翻译执行 × 数据层）

日期：2026-07-30 ｜ 状态：已与用户逐节确认的设计定稿
范围：数据层 / 线性化 / 骨架 / 翻译执行（双后端）/ 迭代与 QA / 测试 / 路线图。
**不在范围**：图片重制工艺、lua 回写与 gim 转换细节（P4 另立 spec，本文只预留接口）。
前置阅读：仓库 `CLAUDE.md`（游戏系统/剧情/DAG 规则）、`analysis/`（DAG 快照、卡片表、全文本摘要）。

## 0. 已定决策记录

| 决策点 | 结论 |
|---|---|
| 译者知识策略 | **全知+纪律**：骨架卡组（含后期卡）全量入前缀，允许引用任意已译章节；指令层强制「译文不得预支读者未知信息、原文歧义处保持歧义」，QA 抽查剧透式措辞 |
| 线性化形状 | **单线+回溯标记**：正典体验序一条线（每场景首次到访一次），重讲/分支处插回溯标记+一句提要；互斥分支互见由全知纪律兜底；支配树血统方案降级为后备（QA 发现语气渗漏时启用） |
| 单元划分 | **多粒度**：原子=vms 行（寻址/回写）；校对单元=场景函数；LLM 批次=token 预算滑窗（一本道自然合并，分支/章界强制断）；锚点=分支点与章边界 |
| 骨架先行 | 采纳 C 档增强版（梗概卡组+口调表+伏笔锚点行），**由 Claude Code 子代理完成，不走外部 API** |
| 迭代模型 | D3 全套：append-only 正向线 + 补丁仓 + 尾部术语层 + 章界重铸阀门 + 试点实测 |
| 基线对照 | 缩小版：第 1 章单发全章翻译作对照组（CC 后端天然承担） |
| 执行后端 | **双后端**：Claude Code 代理执行（cc）与外部 API（gemini/deepseek）平级；分工在试点后定量决定；CC 独立完成全量在架构上可行 |

## 1. 目录与工件总览

```
data/                     数据层（全部入库）
  ledger.jsonl            原文账本（不可变）
  timeline.jsonl          正典体验序（线性化器产物，版本化）
  batches.jsonl           批次规划（开翻前冻结）
  forward.jsonl           正向译文线（append-only）
  patches.jsonl           补丁仓（append-only）
  final.jsonl             resolve() 物化结果（生成物，可重建）
  notes/<chapter>.md      译者手记（检查点时提交）
glossary/
  glossary.v<N>.yaml      术语表（版本号递增，只增版不改旧版）
  style.md                风格指令（全知纪律条款在此）
  voices/<char>.md        角色口调表
skeleton/                 P0 骨架（冻结后打 tag skeleton-v1）
  cards.jp.yaml           197 卡面梗概日文转写（自图片）
  cards.zh.yaml           中文卡组（卡面图片汉化文案源）
  anchors.yaml            伏笔锚点行（日中对照，按章分组）
prompts/
  translator_cc.md        CC 翻译子代理模板（版本化）
  reviewer_cc.md          CC 评审子代理模板
  api_system.md           API 后端 system 指令
tools/                    既有三件套 + 本设计新增脚本
work/                     瞬态工作区（gitignore；ctx 包、draft、模拟输出）
```

## 2. 数据层（D3）

### 2.1 Schema

`ledger.jsonl`（每行一条，生成后不可变；`build_ledger.py` 连跑两遍 diff 断言字节确定性）：

```json
{"id": 7313, "jp": "【女子生徒】「じゃあさ、…」", "voice": "NONVOICE",
 "file": "snr_s1_10_s", "func": "scene_s1s_20", "chapter": "s1s",
 "kind": "narrative"}
```

- `kind ∈ {narrative, ambient}`。ambient=不在时间轴上的文本：snr_common 的 UI/系统通知、oCard 随机反应、comSectionMapmove 随机到场台词、时间轴外可重复文本。分类规则=显式规则表（按 file/func 匹配）+ 人工审定的例外清单（P1 交付物之一），校验器断言二分覆盖全部 16750 行。
- 场景标题、`oCard.show` 提示语、`savedataTitle` 等**非 vms 文本**单列 `ledger_extra.jsonl`（键=`file:line`），同样进翻译流但不占时间轴序。

`forward.jsonl`（append-only，永不回改）：

```json
{"id": 7313, "zh": "【女生】「那我问你，…」", "batch": 42,
 "backend": "cc", "model": "...", "ctx": "sha256:…", "glossary_v": 3, "ts": "…"}
```

`patches.jsonl`（append-only；同 id 多补丁时文件序最后者生效）：

```json
{"id": 7313, "zh": "…", "reason": "review|recall|polish", "glossary_v": 5, "ts": "…"}
```

### 2.2 resolve()

`resolve(id) = patches 中该 id 的最后一条 ∥ forward 中该 id 的最后一条`；无译文时报 UNTRANSLATED。物化为 `final.jsonl`。**一切下游（进度统计、校对界面、lua 注入、烤字任务单）禁止直读 forward/patches，只准经 resolve。** resolve 是纯函数，配单元测试。

### 2.3 术语演化

- 术语表只在 prompt **尾部活动层**出现（头部变更=全前缀 cache 报废，禁止）。
- 词条变更 → 发**召回令**：筛出 `glossary_v < 新版` 且原文命中变更词条的行，走旁路小上下文批处理（受影响行±3 行语境）重译成补丁；主线纹丝不动。
- **章界重铸阀门**：某章之后补丁覆盖率 > 30% 时，在下一个章边界把 resolve 结果重铸为新前缀（一次性全量重付输入费，量级几美元），开新缓存线。

## 3. 线性化器

输入：`analysis/dag_all.txt` 的结构化等价物（P1 把提取器输出升级为 JSON）+ crd 表 + 门控条件。
输出：`timeline.jsonl`，有序事件流，两类事件：

```json
{"seq": 103, "type": "unit", "unit_kind": "scene|card|fscene",
 "src": "snr_s1_10_s:scene_s1s_30", "title": "放課後の約束", "ids": [7350, 7351, …]}
{"seq": 104, "type": "marker",
 "text": "【讲述指针回溯至 s1s_35_sel，本次改选『約束をしている』】",
 "recap": "上轮从此处选了『思い出せない』直到 s1s_60。"}
```

- marker 是**工具生成的中文引导文本**，只进 prompt，永不进游戏。
- 顺序策略（policy 模块，可配置+人工 override 表）：模拟「最早解锁贪心 × 设计节奏」玩家——Story 推进至强制中断/无新卡可得 → Fragment 按路线前缀序做全部可做卡（crd 单元紧跟其对应场景群）→ 回 Story；分支在解锁后的最早重讲点展开（marker 进出）；GAMEOVER 支线作为短支线在最早可达分支点后插入；章末卡 → 对应 `_f` 章紧随；跨章门控（卡 141/142/143、s3fc 强制段、Section7 菜单项）逐项遵守。
- **校验器**（`check_timeline.py`）断言：①每条 narrative id 恰好出现一次、ambient id 零次；②事件序满足全部解锁门控（重放 DAG 门控做合法性证明）；③与 analysis/ 快照的场景清单一致。

## 4. Phase 0 骨架（Claude Code 亲自执行，无外部 API）

1. **卡面转写**：多模态逐张读 `png/card/crd_*_a.png` → `skeleton/cards.jp.yaml`（id、标题、正文、章别）。此步同时是卡面图片汉化的文案采集。
2. **中文卡组**：按剧情序翻译全部卡面梗概 → `cards.zh.yaml`；与用户交互定稿。
3. **口调表**：主要角色各一份中文语体范例（含 彩野/アヤノ、由加里/ユカリ 片假名-汉字双写法的中文对策——这是 P0 必须裁决的第一批术语）。
4. **伏笔锚点行**（C 档）：从剧情知识+DAG 交叉引用挑出被后章回收的原句，日中对照入 `anchors.yaml`（每章数十行，token 近零）。
5. 全部定稿后 git tag `skeleton-v1` 冻结；此后修改=新版本+受控重跑评估。

## 5. 翻译执行器 = 公共接口 + 双后端

### 5.0 公共接口（数据层对后端无感知）

```
build_context.py --batch N --profile {api-A | api-B | cc}
  → work/ctx/batch_N/{context.md, source.jsonl, manifest.json}
<后端翻译> → work/out/batch_N.draft.jsonl
check_batch.py batch_N     （见 §7 校验项）→ pass 才允许
append_forward.py batch_N  （追加 forward.jsonl + commit：data: <章> 批次N 译文入线）
```

- 批次规划：`gen_batches.py` 输出三条车道——①主车道沿 timeline 贪心累积原文 token 至预算（初值 6-8k，可配置），遇 marker(分支)/章界强制断批；②ambient 池车道（上下文=骨架+术语表，全局语境翻译，可与主车道并行）；③ledger_extra 车道（场景标题/提示语等短文本，随其所属章的主车道批次搭车）。产物 batches.jsonl 开翻前人工过目一次后冻结。
- prompt 公共结构 = `[冻结骨架][timeline 前缀（按档位）][尾部活动层：术语表当前版+style.md+本批 source]`。
- 前缀语言形态默认**中文单语**（已译正文）+ 锚点行日中对照；日中全对照形态在试点做 A/B。

### 5.A API 后端（gemini / deepseek）

- 档位：A 档=全文 append-only（40-60 万 token 封顶，纯吃 prefix cache）；B 档=章级 epoch 压缩（前缀=骨架+已完结章中文梗概链+当前章已译全文；压缩只发生在章边界，章内绝不改写前缀）。A→B 可在任意章边界无损降级。
- **离线成本模拟器**先行（不调 API）：用 ledger 行长统计对 档位×批次大小×前缀形态×两家计费规则 全组合 dry-run，输出总费用/峰值前缀/命中率曲线，据此定档。
- TTL 保温调度：兄弟批次排同一 TTL 窗口连跑；长停后先发预热请求；gemini 对骨架段注册显式 cache。
- 启用与否、承担多大比例，待 CC 试点与模拟器数据出来后决定。

### 5.B Claude Code 后端（superpowers 风格：计划文档 + 子代理执行）

1. 上下文形态：子代理上限 ~200k → 只用 **cc 档压缩上下文**（骨架+章梗概链+当前章已译全文+锚点+术语 ≈ 30-80k）。字节级 cache 纪律对本后端不承重；append-only 仍保留（审计+续跑）。
2. `gen_plan.py --chapter <ch>` 从 batches.jsonl 机械生成 `docs/superpowers/plans/translate-<ch>.md`：逐批任务（build_context → 按 `prompts/translator_cc.md` 派翻译子代理 → check_batch → append+commit）；每 5 批一个检查点任务（术语提案裁决+抽查）；章末任务=梗概回译自检+人工评审 gate。
3. 执行：专门翻译 session 用 superpowers:executing-plans（或同 session 用 subagent-driven-development）。章内批次严格串行（后批依赖前批译文）；ambient 池等独立车道可并行。每批 commit，任意时刻可断可续。
4. 翻译子代理模板要点：译者人设、全知纪律、控制码规则、输出 schema（按 id 的 JSONL）、返回前自检清单；**允许并鼓励用工具**——rg 查 forward 里既有译法、查 text_digest 上下文、看场景 CG/立绘把握语气。
5. 译者手记：每批向 `data/notes/<ch>.md` 追加新术语提案/存疑点/语气决策，下一批必读；提案进 pending 队列，检查点时用户或主 session 裁决并入 glossary（版本++）。
6. 评审子代理（二段式，难点章强制：e2 单边电话、s7 递卡、s3fc 绘本童谣）：独立对照原文挑刺（术语漂移/剧透措辞/控制码）后才进 validator。
7. 配额运营：吞吐受订阅限速，计划按多日断续跑设计（每批落盘+commit 即断点）。

## 6. 迭代与 QA

- 校对单元=场景函数；打回→补丁仓；召回令→旁路批处理（§2.3）。
- 章界**梗概回译自检**：每章压缩前，令模型仅凭该章中文译文重写章梗概，与 cards.zh diff；人名/称谓/关键事件分歧 → 阻断压缩，先修复。
- 全知纪律抽查：每章按 5% 抽行，检查剧透式措辞/提前消歧。
- **基线对照**：第 1 章由 CC 单个子代理单发全章翻译，与流水线产出人工盲评，量化流水线复杂度的边际收益。
- 灾难性早期错译的核选项：回放截断（作废后缀重排）——仅人工显式触发。

## 7. 校验器（check_batch）与测试

check_batch 逐批断言：
1. 输出 id 集合 == source id 集合（不多不少不重复）；
2. 控制码：`<漢字,かな>` ruby 结构合法；`【说话人】`前缀与 glossary 映射表精确一致；`_n/_r` 允许移位但数量差 >2 时告警转人工；`≪≫≦≧○■` 保留；
3. 术语合规：命中 glossary 词条的原文，其译文缺失对应定译时**告警转人工**（词形/语序变化可人工放行，不硬阻断）；
4. 行宽启发：显示宽度阈值初值=原文宽×1.15，超限告警（试点后校准为硬规则）；
5. 失败处理：硬规则（1/2）fail → 该批携带失败原因重译，两次失败转人工；软规则（3/4）积累进批次报告供检查点审阅。

测试策略：build_ledger 双跑 diff；check_timeline 三断言；resolve() 单测；tools/ 提取器以 analysis/ 快照为 golden test；试点章端到端演练全链路（含打回→召回→重铸→注入 dry-run 接口）。

## 8. 路线图

- **P0** 骨架（CC，本/另 session）：cards.jp → cards.zh → 口调表 → anchors → tag skeleton-v1
- **P1** 基建：build_ledger / 线性化器+校验器 / gen_batches / build_context / check_batch / append_forward / resolve / prompts 模板（DAG 提取器升级为 JSON 输出）
- **P2** 试点：CC 翻第 1 章（顺带基线对照）→ 视结果决定是否开 API 试点（成本模拟器+实测 cache 系数）
- **P3** 全量翻译 + QA 循环（双后端按试点结论分工）
- **P4** 图片汉化（novel 993 页、select 278、card 197、sysgim 等）与 lua 回写/gim 转换——另立 spec

## 9. 已否决/后备方案存档

- 支配树血统（互斥分支 fork + 汇流梗概接驳）：后备。触发条件=QA 发现跨分支语气/定译渗漏成系统性问题。
- 看板动态排序：降级为顺序合法性校验器的实现思路。
- 锚点(选择支)先翻、按返工风险排序、发现序开工、叙内知识屏障车道：否决（理由见 ADHD 收敛记录，会话 2026-07-30）。
- 三轮讲述全量重译：仅保留「终讲润色」轻量变体，作为 P3 尾部可选 pass。

## 10. 留待试点数据裁决的开放项

1. 前缀语言形态：中文单语 vs 日中对照（试点 A/B）。
2. API 后端启用与否及分工比例。
3. 行宽阈值定值；`_n/_r` 移位规则是否收紧。
4. cc 档批次预算（6-8k 初值）与章梗概链长度的最优点。
