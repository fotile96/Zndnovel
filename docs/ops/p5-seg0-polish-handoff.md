# P5 SEG-0（p5seg0-s0-s1）点火 handoff

> 2026-08-19。P5 二轮润色首段。设计与决策见 `docs/ops/p5-polish-design.md`（四决策点已拍板）、
> 规范见 `glossary/polish.md` P5 版（守门三问 + §11–§18）。本段兼任**影子批载体**（session 1）。

## 一、现状清点

- 工装契约 v2 五件全落地并全绿（alts/noop/chosen_alt/--human-twins/prompt 新元素），全量 1267+ passed。
- `p5seg0-s0-s1` 已冻结（P5 段别名机制：剥 `p5` 前缀复用 P4 段表行；目录/产物用全名）。
  冻结校验无漂移；rulings 承接 seg7-e2 全链累计版（含 SEG-7 收口裁定）；polish.md 为 P5 版。
- 9 会话 prompt 已渲染：`work/ctx/p5s0-s{1..9}.md`（每份 ~900KB，与 P4 seg7 的 660–756KB 同构
  +25%，P4 双通道已验证此量级可消费）；`plan.json` 载 9 会话 prompt_hash。

## 二、段规模与锁（P5 终稿轮口径）

| 项 | 值 |
|---|---|
| 行数 | 4282（b1–35，s0f/crd/s1s/sys/s1f/s2s 头） |
| 硬锁 | **0**（P5 口径：最后一轮，一切行皆可提案） |
| 软锁 | **516** = p4_human 483（P4 人裁 patch 行，改动须 adjudicate）+ anchor 33 |
| 机械 recall 行 | 不锁（v19 罗马音化等；一致性由 W2/残留扫描把守） |
| K 配额 | 700（沿用；本段 P4 时待裁 ~500，P5 预期更低，段末复盘再调） |

⚠ 软锁语义提醒（裁决侧）：p4_human 行的改动提案=「推翻一条 P4 既有裁定」，复核时对照
P4 的 decisions/queue 记录再判；「P5 觉得更顺」不足以推翻「P4 用户亲手定的」。

## 三、通道矩阵与派发参数

### 正式通道（产物 `raw/<channel>/b{session}.out`，session 1–9 全跑）

| 通道 | 派发形态 | 参数 |
|---|---|---|
| fable-wf | Workflow 子代理（沿 P4 脚本形态） | `model=fable, effort=high`（用户拍板沿用） |
| ds-flash | `paseo run --provider deepseek --model deepseek-v4-flash --mode bypassPermissions` | 沿 P4 四条纠偏 |

### 影子通道（**仅 session 1**，产物 `shadow/<channel>/b1.out`，不 ingest 不入裁决面）

| 通道 | 路径（2026-08-19 探明） | 注意 |
|---|---|---|
| opus46 | `paseo run --provider claude --model claude-opus-4-6[1m]` | **必须 [1m]**（prompt ~40 万 token，200k 版装不下）；thinking 档派发前 `paseo inspect claude` 确认 thinkingOptionId 取最高档（用户要求 max） |
| glm-5.2 | `paseo run --provider opencode --model opencode-go/glm-5.2 --mode build` + `OPENCODE_CONFIG` 注入 | **bash: deny**（SEG-7 kimi 教训的既有配置复用）；glm-5.2 只有 opencode 一条路径 |
| glm-5.3 | `paseo run --provider packy --model "glm-5.3[1m]" --mode bypassPermissions` | z.ai 直连（比 opencode 干净，无 shell 配置负担）；packy 的 mode 枚举与 claude 同形态 |

探明记录：Workflow `model:'opus'` 实解析为 `claude-opus-5[1m]`（**非 4.6**）——故 opus46 通道走
paseo claude provider，不走 Workflow。z.ai（packy）只有 glm-5.3[1m]，无 5.2。

### 影子批评估（session 1 三通道交卷后）

判据（design §四）：独有真贡献 ≥3 条有意义；与正式双通道并集的重合结构（撞车率参照：
fable×ds ≈10%，kimi 63% 即抄袭红旗）；hard/R2b 违规数；score 单调可用；**alts 质量**
（备选是否真是不同解而非复述）。达标者从 p5seg1 起进正式矩阵。评估工具：`polish_bench`
（扩通道待做，人工比对兜底）；产物对照面=正式双通道同会话的 raw。

## 四、通道纪律（全体，含影子）

1. **只读 frozen/**，不写仓库任何其他文件，临时文件进 /tmp；能关 shell 一律关。
2. 候选与现行文本 diff 为空按**弃权**计（ingest 自动标 noop），score 不入权重。
3. R2b 硬闸常开；批注援引规则编号必须真实存在。
4. **契约 v2**：主候选 + 至多 2 条 alts，只在拿不准时给；软锁行（含 alts 提案）必须 adjudicate。
5. 派发词点名本段两件事：①v19 豁免清单不得回改（假名双关/读音链/盘面/小菊——prompt 已嵌）；
   ②s0f/s1s 的呼名密度是 §5(e) 演出机关主场（P4 全部驳回记录在案），P5 不得重启换代词争论。

## 五、段末必做

1. 逐会话 `polish_ingest` → `polish_check --seg … --channel …`（gates）→ `polish_triage`；
2. 机裁 + 用户复核（沿 P4 形态；queue.md 现在会渲染编号备选，`adopt_alt:N` 采纳）；
3. `polish_commit` 清关；
4. **新增**：`polish_check --seg p5seg0-s0-s1 --human-twins --lane-dir pilot/lanes/opus`
   （人改孪生传播扫描——15758/15832 型分叉的专用闸）；
5. `--w4-full` 与 `--bare-full` 照跑；`check_qa_quotes --strict`；
6. 影子批评估报告（§三判据逐条）→ 通道矩阵更新进 p5seg1 handoff；
7. **特例池批量裁定**（pattern report §五 ~40 条）安排在本段裁决会话顺带过；
8. 段末台账：channel_feedback.md + rulings 追加 + tag `p5-polish-seg0-done`；
9. K/待裁率实测记 threshold-ledger（P5 首段基线）。

## 六、本段语料性格（派发词与裁决参照）

s0f 序章（教学性对话与系统文本密集，复现句族多：_sel 三分支、TIMEOVER 双分支）→
crd 教程卡 → s1s 第 1 章前段 → s1f 现实层 → s2s 开头。P4 在本段的裁决画像：呼名/代词
攻防是最大裁决群（keep 侧全胜）；chunk-01/02 reader 报告的搭配体检与语域校准高发区。
P5 重点：三问自检的「事理坐实」在教学对话里最有空间；段级密度（教程段「就是这么回事」
解释腔、sys 地图语音的「呢/哦」贴片）是本段两大段级目标。

---

## 七、点火实况（2026-08-19）

**五通道正式矩阵**（见 `p5-polish-design.md` §四定案）。SEG-0 落地状态：

| 车道 | SEG-0 进度 | 机械闸 |
|---|---|---|
| `fable-wf` | **全段 4282 行**（35 批）已入仓 | hard 0 / warn 32（W2 18、W3 14） |
| `opus46-wf` | 会话 1（569 行）已入仓，余 8 会话待发 | hard 0 / warn 4 |
| `glm-5.2` | 会话 1 已入仓，余 8 待发 | hard 0 / warn 3 |
| `glm-5.3` | 会话 1 已入仓，余 8 待发 | hard 0 / warn 3 |
| `ds-flash` | 9 会话派发中 | — |

三条通道的会话 1 由影子批**晋升**而来（同一 prompt、同一冻结面，省 3 个会话重跑）。

⚠ **fable-wf 全段产出的由来**：它是叫停指令下达后仍在后台跑完的 Workflow（434 万 token）。
用户裁定留用。其溯源完整（prompt_hash 对应现冻结面），已正常入仓。

⚠ **冻结面漂移**：`6118` 在冻结后由孪生修复更新过（`a579eb2`）。**不重冻**——重冻会作废
fable 已入仓候选的 prompt 溯源。改由 `polish_check --lane-drift` + queue.md 警示兜住：
该 id 上四条通道都有改动提案，裁决须按车道最新文本重判，采纳前确认不是回退。

**派发词较影子批新增一条**：「原文自带的 『』 必须原样保留，不得以『此处不是引用』为由删除」
——封堵 opus46-wf 在 `6542` 犯的保真错误（『』不在硬闸 MARKS 内，机械闸抓不到）。

**留到 p5seg1 生效的两条**（改了要重渲 prompt，会作废本段已入仓候选的溯源）：
①契约配平条款「零改动/极低改动率交卷须在批末逐条说明检视过哪些面」；②`『』` 计数入机械闸。
