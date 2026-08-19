# P5 二轮润色·任务书与派发设计（定稿）

> 2026-08-19。前置：`glossary/polish.md` P5 改版（5d8a7b6）、修订窗口收官（80e0ccf，v19/skeleton-v2）、
> `docs/ops/p5-polish-pattern-report.md`（含用户两批裁定）。
> 本文是 P5 点火前的设计定稿：任务形态、输出契约 v2（多候选）、通道矩阵（含三条测试通道）、
> 裁决分流、工装改动清单。用户过目后按 §九 决策点拍板，工装改动走实施计划。

## 一、定位与目标

P5 是**最后一轮**全文 pass：结束后即成品品质，不再安排让 LLM 完整过一遍文本的处理轮。
目标对准 pattern report §一的「用户成品线」——通道每行三问（说清了没有/最具体吗/是不是演出），
段级密度检查是本轮相对 P4 的核心增量。守门三条压过一切（polish.md「P5 守门与三问」）。

## 二、任务形态与 prompt 组装

**沿用 P4 的冻结-派发-入仓-裁决-清关骨架**（polish_setup/polish_context/polish_ingest/
polish_triage/polish_commit），改动最小化：

- **SEG 与会话**：沿用 `config/segments.yaml` 八段结构与 `config/polish.yaml` 会话组贪心合并
  （P3/P4 已验证的大批合并省 token 机制）。
- **冻结面**（polish_setup 拷贝，只读纪律不变）：source.jsonl（jp）+ opus.jsonl（**现行文本
  = forward+patches 叠加**，含 P4 与 v19 全部成果）+ locked.json（硬/软锁）+ glossary/
  （active/speakers/voices/style.md/**polish.md P5 版**/anchors）+ notes/ + rulings.md
  （跨段承接，P4 末段累计 + P5 各段追加）。
- **prompt 新增元素**：
  1. 输出契约 v2（多候选，见 §三）；
  2. 三问自检与段级两遍读要求（见 §六）；
  3. 本段分形保护清单 + v19 豁免清单（防「补改」罗马音化豁免行）；
  4. P4 成品线判例精选（12713/13869/973/4253 等 ~8 对，直接嵌 prompt 尾部）。

## 三、输出契约 v2：多候选（用户新要求）

**每句希望润色时，允许对当前译文提出 1–3 个候选**（不再固定 1 条）：

- 行 schema 在 P4 基础上增加 `alts` 字段（可缺省）：
  `{id, channel, zh, score, note, adjudicate, jp_tail, alts: [{zh, note}, ...]}`
  - `zh` 仍是**主候选**（通道自信最高的一版）——不认识 `alts` 的既有工装照旧工作，兼容性零破坏。
  - `alts` 至多 2 条备选，各带一句理由（与主候选的差异点，不是重复论证）。
- **何时给多候选**（写进契约）：两可取义、语气档位难定、§0 疑似错译的不同修法、
  段级密度调整的不同幅度——即「拿不准需要人裁定」的场景；此时倾向 `adjudicate=true`
  或低 score。**把握足的改动仍单候选**——多候选不是免责装置，滥发（如全线 3 候选）
  视同 score 混量纲问题按通道纪律记录。
- 机械闸：主候选走 P4 全套硬闸；`alts` 逐条过 R2b 结构闸（入仓时），语义闸在**采纳时**
  由 polish_commit 侧把关（采纳 alt 同样过 W3/W4/jp_tail 校验后落 patch）。
- 裁决面：queue.md 渲染 alts；decisions 增加 `chosen_alt`（采纳第 N 条备选时记索引）。

## 四、通道矩阵

> **2026-08-19 定案（用户拍板）**：影子批评估后，测试通道全部转正，P5 正式矩阵为**五条**：
> `fable-wf`（Workflow, fable-5 high）、`ds-flash`（paseo deepseek-v4-flash）、
> `opus46-wf`（Workflow, claude-opus-4-6[1m], effort=max——codename 定此，与 fable-wf 同构）、
> `glm-5.2`（paseo z.ai, glm-5.2[1m]）、`glm-5.3`（paseo z.ai, glm-5.3[1m]）。
> **opus 4.6 走 Workflow 不走 paseo**——影子实测同模型 paseo 形态 0 改动（形式完美实质为空），
> Workflow 形态 30 改动，见 `p5-channel-shadow-eval.md` §二。
> **Workflow 的 `model` 参数可直接钉完整模型 ID**（如 `claude-opus-4-6[1m]`），不限于别名；
> 早前「别名 opus 解析为 opus-5」的记录只说明别名的指向，不是能力上限。
>
> **队列规模实测（p5seg0 会话 1，569 行，四通道）**：各通道改动 14–30，**并集 67（11.8%）**——
> 重合极低、互补性强。全段外推 ≈504（四通道）+100~150（ds-flash）≈ **600–650 待裁 id**，
> K=700 够用但接近满载（86–93%）；若后续段并集升高需上调，否则队列会被静默截断成抽样（T1 教训）。
>
> 下面小节是评估前的原始设计，保留作历史。

### 原始设计（2026-08-19 影子批之前）

### 正式通道（P4 验证，直接进 P5）

| 通道 | 形态 | 沿用参数 |
|---|---|---|
| fable-wf | Workflow 子代理并发 | model=fable, effort=high（提升到 max 见 §九决策点） |
| ds-flash | paseo deepseek-v4-flash, bypassPermissions | 派发词四条纠偏沿用 |

### 测试通道（用户新增，先跑测试批，有价值再进正式 runbook）

| 通道 | 形态 | 落地探明点 |
|---|---|---|
| opus46-wf | Workflow, opus 4.6, **effort=max** | Workflow `model` 枚举别名 `opus` 在当前 CLI 解析到哪一代须先探明；若无法钉住 4.6，备选路径：paseo claude provider 显式指定模型。测试批派发前用最小 agent 自报 model ID 验证 |
| glm-5.2 | paseo | provider/model 名以 `paseo provider ls` / `paseo provider models` 复核为准（SEG-3 纪律），派发模式与权限配置逐项照 schema 配（SEG-7 教训：症状驱动配权限一轮漏一个） |
| glm-5.3 | paseo | 同上 |

**通道纪律**（全体，含测试通道，源自 P4 实测教训）：
1. 只读 frozen/，不写仓库任何其他文件，临时文件进 /tmp；能关 shell 的一律关
   （kimi 教训：`bash` 放开→写脚本→读隔壁通道产物→剥坏 11 行。opencode 侧 `bash: deny`
   先例在案；glm 侧按其权限模型等价配置）。
2. 候选与现行文本 diff 为空者按**弃权**计，score 不入任何权重（kimi「同文高分」教训的机制化）。
3. R2b 硬闸常开；「批注若援引规则编号必须确实是那条规则」。

### 测试批规程（准入判据，rulings SEG-6 §8 已立的规矩）

- **规模**：每条测试通道至少 **1 个完整会话（300 行量级）**——60 行评测批的召回率不可外推
  （kimi 第一教训）。
- **形态：影子批**——正式双通道照常跑该会话并正常入裁决面；测试通道平行跑同一冻结面，
  产物入 `pilot/polish/<seg>/shadow/<channel>/`，**不入裁决面**，事后与正式产出对照评估。
- **判据**（polish_bench 扩展 + 人工抽读）：独有真贡献条数（≥3 有意义）、与双通道并集的
  重合结构、hard/R2b 违规数、score 分布是否单调可用、多候选的质量（alts 是否真是不同解
  而非复述）。达标者进正式 runbook，其段起生效。

## 五、裁决与分流

- **沿用 P4 机裁+人工队列框架**（成熟且用户复核改判率 24–35% 证明自动入库有真实风险）。
- score（把握程度）用作**队列排序与分层参考**；§0 类（批注含疑似/请裁/取义）无论分数必读
  （pattern report P12 流程条款）。
- autoclear 维持关闭为缺省（P4 全程未开）；若开，仅限「零改动行的确认清关」档——见 §九决策点。
- 多候选行的裁决动作扩展：adopt（主候选）/ adopt_alt:N / edit / keep。
- 段末用户复核环节保留（P4 形态）；复核改判后**必跑人改孪生传播扫描**（新工装，§七）。

## 六、段级质量执行面（M1/P8 落地）

任务书要求每批**两遍读**：
1. 第一遍行级：polish.md 三问自检 + §14–§18 清单；
2. 第二遍段级：§13 密度检查（语气词同尾连用/垫词三连/比况连排/感知框架/ながら），
   段级改动同样落行级候选，note 标「段级：密度」；批末可附 ≤5 行的段级观察
   （渲染进 channel_feedback 汇总，不占行级 schema）。
- 密度报表工具（§七 3）随卷发给通道作输入、给裁决作验收面——只报表不设闸。

## 七、工装改动清单（实施计划的任务分解基础）

**必做（点火前）**：
1. `polish_ingest`：`alts` 字段接受 + R2b 逐条闸 + 「候选=现行」弃权标记；
2. `polish_triage`/queue 渲染：alts 展示 + 弃权行不占 K 配额；
3. `polish_commit`：`chosen_alt` 采纳路径（过全套语义闸后落 patch）；
4. **人改孪生传播扫描**（pattern report 工装缺口 1）：对 edited_zh/复核改动行，
   全库检索 jp 全等与句级孪生（含 bare 剥壳面）未同步者，段末必跑；
5. `polish_context.render`：prompt 新元素组装（契约 v2 文本、三问、判例精选、豁免清单）。

**应做（首段前后皆可）**：
6. 语气词密度报表（按批统计句尾呢/哦/啦/呐与明明/说到底/总觉得频次）；
7. `polish_bench` 扩测试通道 + alts 质量维度；
8. 测试通道客户端：glm via paseo（复用 ds-flash 派发形态）、opus46-wf（复用 fable-wf
   workflow script 换 model/effort）。

**编入段计划的一次性子任务**：
9. seg6 keep_opus 重扫（P5 覆盖 s8s/s8f/e1 段时执行）；
10. W3 压缩痕迹定向复审（手记登记行捞出重估，宁留 warning）；
11. 特例池 ~40 条批量裁定（P5 开工首周，pattern report §五清单）。

## 八、与 P4 的差异一览（执行者速查）

| 维度 | P4 | P5 |
|---|---|---|
| 目标 | 首轮母语感 | 成品线（坐实/显态/演出保护）+ 段级密度 |
| 规范 | polish.md §0–§10 | P5 版全篇（守门三问前置，§11–§18） |
| 候选 | 每行 1 条 | 1–3 条（alts），拿不准场景显式化 |
| 通道 | fable-wf + ds-flash（kimi 两段后除名） | 双正式 + 三测试（影子批准入） |
| 底文本 | P3 初译 | P3+P4+v19 现行（罗马音化后） |
| 段级质量 | 无 | 两遍读 + 密度报表 |
| 人改传播 | 盲区（15758/15832 分叉实证） | 段末孪生扫描必跑 |

## 九、决策点（用户已拍板，2026-08-19）

1. **P5 段结构**：✅ 沿用八段（p5seg0…p5seg7，同批区间）。
2. **fable-wf effort**：✅ 直接沿用 high（不做 max 对比）。
3. **autoclear**：✅ 全关（全量机裁+人工队列沿用）。
4. **测试批落点**：✅ p5seg0 session 1 作三条测试通道的影子会话，一次并测。
5. **多候选上限**：✅ 1–3（用户原案）。

## 十、点火路径

1. 用户拍板 §九 → 2. 工装必做 1–5（走实施计划，量约 2–3 个工作单元）→
3. p5seg0 冻结 + prompt 渲染 → 4. 测试通道探明点落地（opus46 model 钉定、glm provider 复核）→
5. 影子批 + 正式双通道点火 → 6. 段末：裁决/复核/孪生扫描/测试通道评估 → 7. 按评估更新
runbook 通道矩阵，进入常规段循环。
