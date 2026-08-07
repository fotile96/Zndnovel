"""P4 润色 pass：四桶分流决策中枢——整条润色流水线里"谁自动入库、谁排队
给人裁、谁保留 opus"的唯一判定点。消费 Task 5/6 的产出（`candidates.
<channel>.jsonl` / `gates.<channel>.json`）与 Task 3 的冻结面（`frozen/
opus.jsonl` / `frozen/locked.json`），产出 `triage.json`（机器可读的分流
结果，Task 8 `polish_commit.py` 的唯一输入）与 `queue.md`（人读的裁决
队列）。

## 核心原则（spec §9 明写，本模块存在的理由）

**模型自报的 `score` 只在同档内排序，绝不作为绝对阈值**——跨模型（fable/
deepseek/未来第三个）的自报分不可比。分桶靠的是客观信号：是否命中冻结面、
有没有真的改动、改动幅度多大、机械闸是否全绿；`score` 只用来在"改动幅度
打平"时做同档内的精细排序。任何把 `score` 变成阈值（比如"score<60 才
autoclear"）的实现都是错的——本模块通篇不出现这种比较。

## 桶判定顺序（2026-08-07 用户裁定更新：锚点行从硬锁改软锁；同日追加：
## `adjudicate=true` 候选无论有无改动一律强制进队列，见 D3 修复专节）

对每一条 `(id, channel)` 候选行，判定顺序如下（**顺序本身是判定的一部分**
——软锁与显式请裁两条强制规则都必须排在"零改动 → 桶 1"之前，否则零改动
的请裁行会先被 `zh==opus` 分支拦截，见下方 D3 修复专节的教训）：
1. **硬锁 → 0**：id 在 `frozen/locked.json` 的 `hard_ids` 里。理论上
   `polish_ingest.ingest()` 已经在入仓时判死硬锁 id 出稿，候选文件里
   不应该出现硬锁 id——这里是**兜底**（防御 `locked.json` 在 ingest 之后
   被新裁决 patch 更新、或任何绕过 ingest 直接写入 candidates 文件的
   异常路径）。
2. **软锁 id 且有真实改动 → 强制摘进桶 2**（见"软锁强制进队列"专节）：
   `polish_ingest` 已经保证这类候选必然带 `adjudicate=true`（没带的在
   入仓阶段就判死了），但本层不重新校验这个前提——只要"是软锁 id 且真的
   改了"就无条件强制排队，永不自动清关、不参与 K 配额竞争（**不被 K
   挤出**，即使这意味着桶 2 总量超出 K）。
3. **`adjudicate=true`（显式请裁）→ 强制摘进桶 2，无论有没有改动**（见
   "显式请裁强制进队列"专节，D3 修复）：与上一条同等待遇——永不自动清关、
   不占 K 配额竞争。检查顺序排在"零改动"判据之前，保证一条"我不改，但请
   你裁"的候选不会被"zh==opus"分支拦下丢进桶 1。
4. **`zh == opus`（归一后逐字相等）→ 1**：见下方"零改动判据"专节，
   这里刻意只做**空白归一**，不剥控制码/ruby。软锁 id 若没改动、且没有
   显式请裁，同样走这一档，**无特殊待遇**（spec 原话）。
5. 其余（有真实改动、且没有显式请裁的普通候选）进入排队池，按 id 分组
   （见"K 配额与多通道同 id"专节）用（`adjudicate` 显式请裁优先 → `edit`
   大→小 → 同 edit 按 `score` 低→高 → id 升序兜底去重）排序，前
   `K − 抽检占用 − 软锁/请裁强制占用` 个 id → 2；其余 → 3。
   （注：走到这一步的候选 `adjudicate` 恒为 `False`——真的话早在第 3 步
   被摘走了；排序 key 仍保留 `adjudicate` 位是为了兼容"同一 id 下这一
   通道没请裁、另一通道请裁了"的分组聚合场景，见"K 配额"专节原文。）

## 显式请裁强制进队列（D3 修复：`adjudicate=true` 但零改动的候选此前被
## 静默丢弃）

**实测缺陷**（SEG-0 `pilot/polish/seg0-s0-s1/channel_feedback.md` D3
节）：润色契约明确鼓励"拿不准就照抄 + 请裁"（`glossary/polish.md` §0、
纠偏 3），但旧实现按"有无改动"分桶——`zh == opus` 的候选无条件落桶 1，
`adjudicate=true` 这个字段在"零改动"分支面前完全不起作用。三例实测：
269（侥幸靠另一通道改了同一行才蹭进桶 2）、17002（跨段术语一致性疑问，
被丢弃，靠人工发现才捞回）、7963（触及有段外伙伴的锚点句互文，被丢弃）。
**越是老实照抄并请裁的通道，它的请裁越容易消失**——这惩罚了契约明确
鼓励的行为。

**同一缺陷的隐藏镜像面**（本次修复顺带堵上，未见于原始 D3 记录但同一
判定链条上）：`adjudicate=true` 且**有**改动、但改动幅度小、机械闸全绿
的候选，旧代码里同样不受 `adjudicate` 字段保护——它会正常流入 `pool` 走
`_eligible`/autoclear 判定，若满足条件会被判 `autoclear=True`，只有命中
抽检才会被塞回队列，否则同样悄悄消失在桶 3（`autoclear and not sampled`
直接被 `polish_commit` 清关，不进 `queue.md`）。这与零改动那面是同一个
"请裁被自动化流程吃掉"的失败模式，只是触发条件不同——本次修复用同一个
判据（"该行 `adjudicate=true`"）覆盖两面，不分别打补丁。

**修法**：`adjudicate=true` 的候选行，检查顺序提到"零改动"判据**之前**、
且完全跳过 `pool`/`_eligible`/autoclear 计算——与软锁强制进队列同一套
机制（bucket=2、`autoclear` 恒 `False`、不参与 K 排序竞争、不被 K 挤出），
落盘计入新字段 `meta.forced_adjudicate_count`（与 `forced_soft_count`
语义对称但独立计数，二者可能对同一 id 重叠——见下方"K 预算的合并去重"）。

**是新开一桶还是归桶 2 带标记**——裁定：**归桶 2 带标记，不新开一档**。
理由：桶的语义是"人要不要看"，请裁行显然要看，桶 2 已经是"人工裁决队列"
这一档，没有必要为"为什么进来"这件事另开一个桶——`bucket` 字段本就不是
用来回答"为什么"的，`queue.md` 的"进入队列原因"行才是。新开一档反而要求
`polish_commit`/`polish_audit` 等下游多认识一个 bucket 取值，风险大于
收益。

**`queue.md` 呈现（零改动请裁行不能看着像空记录）**：
- id 级"进入队列原因"三档取代原来的二档：**软锁改动**（不变）/
  **请裁·未改动**（该 id 名下所有 `adjudicate=true` 的候选行都与 opus
  逐字相同——新增，专门针对 D3 这类"没有 diff 可看，只有疑问"的行，用
  显式的"未改动"字样避免裁决者一眼扫过以为是空行）/ **显式请裁**（原有，
  即请裁且确有改动）。
- 每一条通道候选行末尾，若该行 `zh` 与 opus 逐字相同，追加
  `[本通道未改动，与 opus 逐字相同]` 标记——这条标记与"进入队列原因"
  独立存在（不局限于请裁场景），任何情况下"这一行摆在桶 2 里却和 opus
  长得一样"都值得让裁决者一眼看出，不用自己去对比原文。

**它与既有桶语义/`triage.json` 字段的协调**：不改变任何既有字段的既有
含义——`forced_soft_count`/`forced_soft_over_budget` 精确保留原语义
（只统计"软锁且改动"这一支路径，不含本次新增的请裁支路），新增
`forced_adjudicate_count`（本次新增支路的 id 数，可能与 `forced_soft`
有交集——见下方合并去重）与 `forced_total_count`/`forced_total_over_
budget`（去重后合计，真正用于 K 预算扣减与"是否超预算"判断，见下）。
下游消费者（`polish_commit.py`/`polish_audit.py`）只读 `rows` 里的
`bucket`/`autoclear`/`sampled` 字段，不读这几个 `meta.forced_*` 字段，
新增字段对它们零影响。

**K 预算的合并去重**：一个 id 理论上可能同时命中"软锁+改动"（走软锁
支路）与"另一通道 `adjudicate=true` 但零改动"（走请裁支路）——两条支路
各自维护的 `forced_soft_ids`/`forced_adjudicate_ids` 集合可能有交集，
K 预算扣减必须按**去重后的并集** `forced_total_count` 算一次，不能把
同一个 id 的名额从 K 里扣两次。

## `polish_commit` 侧的对应处理：D3 这类"零改动+请裁"行裁成 `adopt` 时
## 不产生"无意义 patch"风险的说明

裁决者对 D3 这类行的**正常归宿是 `keep_opus`**（人看过了、确认维持
opus 原译，不产生任何 patch——`polish_commit.commit()` 本就对
`keep_opus` 不落任何计划项，见其模块 docstring）。但裁决者仍然可能选
`adopt`（比如想要在 `decisions.jsonl`/`patches.jsonl` 里显式留一条
"经人工确认过"的痕迹）——这条路径必须**安全落地**，不能因为候选文本
逐字等于 opus 就出错或产生损坏数据。实测确认（见
`tests/test_polish_commit.py::test_adopt_zero_edit_adjudicated_candidate_
writes_safe_noop_patch`）：`commit()` 对这种候选正常走 `verdict="adopt"`
分支，写出一条 `zh` 与 opus 逐字相同、`reason="polish"` 的合法 patch——
不崩溃、`prov` 倒查链完整、`resolve_map()` 消费这条 patch 是幂等的
（新文本与旧文本相同）。**唯一的额外处理**：`commit()` 在这种情况下
会往 stderr 打一条信息级提示（不是告警，不阻断），提醒操作者"这条 patch
未改变译文，通常应改用 keep_opus"——这是"静默写错比报错更坏"原则的延伸
：虽然这不是"错误"，但也不该悄无声息地在 `patches.jsonl` 里堆出一条
看似有内容、实则文字未变的记录而不给操作者任何提示。

## 软锁强制进队列（spec §5：可出稿、永不自动清关、必进裁决队列不被 K 挤出）

`soft_ids`（`frozen/locked.json`）代表 anchors.yaml 锚点行——用户裁定它们
"翻译轨结束时的认知"允许在润色阶段再议，但**动了就必须有人看一眼**，且
"看一眼"这件事不能因为 K 配额被别的候选占满就被挤掉（spec 原话："若软锁
行本身就超过 K，那是真信号，要显著播报而不是静默截断"）。

**顺序（用户建议的展开，避免与"K 减抽检"的既有循环依赖再叠加一层）**：
"软锁改动行先占位，其余名额再按原排序分配"——具体地：

1. 逐行遍历候选时，`cid in soft_ids` 且 `not _ws_equal(zh, opus)` 的行
   直接归入 `forced_soft`（按 id 分组），**完全跳过** `_eligible` 计算与
   `pool` 插入——它不参与自动清关判定（永不清关，与 gates/channel_state
   无关），也不参与排序竞争。
2. `forced_soft_ids = sorted(forced_soft)`——这些 id 的**全部**候选行
   （可能有多个通道）无条件 `bucket=2`，直接写入 `rows`，不受任何后续
   步骤影响。
3. 后续"K 减抽检"的既有推导（`rank_floor`/`sample_cap`/`quota`）里，
   K 先减去 `len(forced_soft_ids)`（`K_remaining = max(0, K -
   len(forced_soft_ids))`），再按原逻辑分配抽检/排位——软锁强制占用
   排在抽检占用之前，与用户"先占位"的顺序一致。
4. **`len(forced_soft_ids) > K`（软锁改动行本身就超过人工预算）**：
   `K_remaining` 钳到 0（抽检/排位名额全部让出），并 stderr **显著播报**
   （不是普通告警级别的一行字，是带明确"预算已耗尽"字样的告警），且
   `triage.json` 的 `meta` 记 `forced_soft_over_budget=True`——这是真信号
   （anchors.yaml 这段时间被大量改动），不能被这道分配逻辑悄悄吸收掉。

`queue.md` 对这类强制进队列的 id 单独标注"进入队列原因"为
"软锁改动（锚点行，强制进入队列，不受 K 名额影响）"——比笼统的"进入本轮
裁决队列"更明确地告诉裁决者这条为什么会出现在这里，且**不违反**"抽检
不泄露"的既有设计（那条设计只针对"审计已经清关的候选"这一种隐藏动机，
软锁强制排队没有类似的心理暗示风险——反而应该让裁决者知道这是锚点句，
需要格外审慎）。

## 自动清关（从桶 2/3 前"截流"——见"K 配额"专节展开这句话到底什么顺序）

`bucket∈{2,3}` 且 `edit ≤ autoclear_limit(opus)` 且该行所在通道
`gates.<channel>.json` **本次检查覆盖了这个 id**（`checked_ids`，最终评审
C1）且它的 `hard` 为空、`warn` 里没有 W3 行宽（最终评审 C2）且该通道自动
清关权开启（`channel_state.json`，缺省关闭）→ 从竞争排队的候选池里摘出，
`autoclear=True`；其中按 `sample_rate` 抽一部分 `sampled=True` 塞回裁决队列（占用
K 配额，供人工事后审计，Task 8 只对 `autoclear and not sampled` 的候选
直接清关，`sampled=True` 的即使 `autoclear=True` 也还要走一遍人工裁决——
这是 Task 8 brief 原文的分工，本模块只需要保证两个字段都如实落盘）。

`channel=="amplify"` 恒不 autoclear，与 `channel_state.json` 里写了什么
无关——测试 `test_amplify_never_autoclears` 故意先开启 amplify 的清关权
再断言它仍然不生效，就是为了钉死"这条硬规则不依赖配置，配置开对了也没用"。

## 三个自行裁定的设计点（brief 明确点名要我拿主意的地方）

### 1. K 的分配：多通道同一 id 只占一个名额

`K`（`config/polish.yaml` 里的 `K: 150`）是**整个 SEG 的总额，多通道
共享**。裁决时是**并排比较**（`queue.md` 把同一 id 的全部通道候选列在
一起给人一次看完），所以"要不要占用一个 K 名额"天然是**按 id**、不是
按 `(id, channel)` 行。

实现：把"需要裁决"的候选行（桶 2/3 候选，不含 0/1）先按 `id` 分组
（`pool: dict[id -> list[row]]`），K 配额的排序、截断、abstain 全部在
"id 分组"这一层操作——一个 id 无论有 1 个还是 3 个通道的候选行，进
`pool` 之后只对应**一次**排序 key、**一次**"是否挤进前 K"的判断，决定
出的 bucket 会**同时施加给该 id 名下的全部候选行**（不会出现同一 id
在不同通道下拿到不同 bucket 的情况——那样"并排比较"就没有意义了：
人工裁决台面上摆着同一个 id 的两个候选，总不能一个算"配额内"另一个
算"配额外"）。

排序 key 里"多通道怎么聚合成一个"的选择（都记在 `_sort_key` 里）：
- **`adjudicate` 优先级**：组内**任意**一行显式请裁 → 整个 id 视为显式
  请裁。理由：显式请裁是模型主动喊"这句我吃不准，请人看"，任何一个
  通道喊了，这个 id 就该被人看到，不该因为另一个通道没喊就被稀释掉。
- **`edit`（改动幅度）聚合**：取组内**最大**编辑距离。理由：多通道里
  只要有一个通道对这个 id 提出了大改动，这个 id 本身就值得优先审——
  用最小值聚合会让"一个通道乱改、另一个通道没怎么动"的危险案例被
  没怎么动的那个通道拖累评分，systematically 压低优先级，不安全。
- **`score`（同 edit 打平的最后并列）聚合**：取组内**最小**分。理由与
  上面对称——`score` 低代表"这个通道自己都不太确定"，聚合取更谨慎的
  那个值，不让"某个通道虚报高分"把整个 id 的排队优先级拉低。
  ⚠ 再强调一次：这只是**同一 id 内、edit 打平之后**的最后一道并列
  打散手段，从未跨 id/跨通道地把 score 当阈值用。

### 2. 抽检占用 K：顺序依赖的正确展开

brief 原文点破了这里的循环依赖："抽检数取决于自动清关数，而自动清关是
从桶 2/3 前截流的"。真正的执行顺序（避免循环的唯一办法：让"是否
autoclear-eligible"完全独立于"排位排到第几"）：

1. 先算桶 0（locked）、桶 1（零改动）——这两桶的判据不依赖 K/排序/
   autoclear，可以无条件先算。
2. 剩下的候选行按 id 分组成 `pool`。**对每一行**（不依赖它将来会被
   排到桶 2 还是桶 3）算 `_eligible`：`edit ≤ autoclear_limit(opus)`
   且该行所在通道这个 id 的 gates hard 为空且该通道自动清关权开启且
   `channel != "amplify"`——这四个条件全部只看"这一行自己的属性"，
   与"它在全体候选里排第几"完全无关，所以可以在排序之前就算出来，
   打破了"autoclear 依赖 bucket、bucket 依赖排序、排序又要扣掉抽检
   占用"这个看似循环的链条：**只要 autoclear 的判据本身不依赖排名，
   循环就不存在**——brief 里"bucket∈{2,3}"这半句话不是要求"先分出
   2/3 再倒查 autoclear"，而是在说"只有非 0/1 的候选才谈得上 autoclear
   这件事"（0/1 桶的候选不需要"自动清关"这个动作：0 桶本来就不出稿，
   1 桶本来就零改动不产生 patch），这一点在算 `_eligible` 时已经隐含
   满足（只对 `pool` 里的行算）。
3. 一个 id **只有组内全部候选行都 `_eligible`**，才把整个 id 从 `pool`
   摘出、归入 `autoclear_ids`（"unanimous" 规则，展开见下一节）；否则
   留在 `pool` 里正常参与排序竞争（即使其中某一行单独看是"小改+绿"，
   只要同 id 还有别的通道候选没过关，人工照样要把这几行摆在一起看，
   autoclear 单独摘走其中一行没有意义——见"id 级 all-or-nothing"专节）。
4. 对 `autoclear_ids`（此时已确定，不再变化）用种子化的 `random.Random`
   逐 id 抽样，抽中的记 `sampled=True` 并**强制**收进裁决队列（bucket=2，
   不参与下面的排序竞争、直接占一个位置）；抽不中的 `sampled=False`，
   `bucket=3`（未进队列——即"记录在案，autoclear 已经把它清关掉了，
   不需要也不会出现在 `queue.md`"）。
5. 到这一步，"抽检占用了多少个 K 名额"（`len(sampled_ids)`）已经是
   确定数字，`pool` 里剩下的（未被摘出的）id 才真正进入"按 key 排序、
   取前 `K − len(sampled_ids)` 个 → 桶 2，其余 → 桶 3"这一步。

这个顺序——**先兜底桶 0/1，再逐行独立算 autoclear 资格，再按 id 做
all-or-nothing 摘除+抽样，最后才用"K 减去抽样数"去切排序队列**——是
本模块唯一不产生循环依赖的写法，因为每一步只依赖"更早、且与自身无关"
的信息。

### 2b. 抽检 K 帽与最小配额（评审 Important 修复，追加于原始实现之后）

**评审发现的漏洞**：`quota = max(0, K - len(sampled_ids))` 只保证了
"给排位池的配额不为负"，却**没有反过来约束 `len(sampled_ids)` 本身不
能超过 K**——原始实现里 `sampled_ids` 是"逐个自动清关 id 独立掷一次
`rng.random() < sample_rate`"的直接产物，理论上没有任何上限。评审构造
的对抗场景：50 个满足 autoclear 条件的候选 + 20 个真实大改候选，
`K=2`、`sample_rate=0.5` → 期望被抽中的样本数在 25 上下，桶 2 实际
总量（抽检 + 排位）远超 `K=2`，20 条真正需要人裁的大改候选反而被全部
挤到桶 3。这不是纯理论：真实规模下 `K=150`、`sample_rate=0.10`，只要
单 SEG 满足 autoclear 条件的候选数超过 1500（多通道齐跑、单 SEG 候选量
上千时会发生），抽检数本身就 > 150，"K 是总额、含抽检占用"这条 brief
与本模块 docstring 反复强调的不变量此前没有任何代码在维持它。

**修法：两步——先算"配置比率下本该抽中谁"（`desired_sampled_ids`，
可能比 K 还大），再单独用一个与排位池大小联动的帽子把它压到 `sample_
cap` 以内**：

```python
rank_floor  = min((K + 1) // 2, len(non_autoclear_ids))
sample_cap  = max(0, K - rank_floor)
sampled_ids = set(desired_sampled_ids[:sample_cap])   # 超出部分丢弃（deterministic：按 id 升序砍尾）
```

`quota = max(0, K - len(sampled_ids))` 这一行代码完全不用改——一旦
`len(sampled_ids)` 本身先被压到 `≤ sample_cap = K - rank_floor`，
`quota = K - len(sampled_ids) ≥ rank_floor` 自动成立，"桶 2 总量
`len(sampled_ids) + min(quota, len(ranked_ids)) ≤ K`" 这条不变量就
恒真——问题根本不在这一行，而在它上游"喂给它的 `sampled_ids` 从未
被封顶"。

**设计张力的裁定（控制者已明确指示，记录在此）：宁可降低抽检覆盖率，
也不能突破用户定的人工预算**——`K` 是用户明确给的裁决带宽（spec §5：
"人工请裁配额 K≈100–150 句/SEG"），静默超出这个预算比"抽检少抽几条"
更坏；反之，抽检覆盖率不足只是牺牲了一部分"事后验证 autoclear 判定
是否可信"的统计功效，不会让任何一条真正需要人看的大改候选被挤掉。

**是否给正常排位（桶 2 的"真实改动候选"部分）留最小配额——本任务的
选择与理由**：留，且量取 `min(ceil(K/2), 真实需要审的候选数)`：
- **为什么要留**：桶 2 存在的**首要目的**是"有真实改动、需要人拿主意
  的候选排上队"（spec §3 四桶表：桶 2 = "有改动 ...段末人工裁决"）；
  抽检审计的对象是"一条已经被自动清关判定为『安全』的候选"——它本身
  风险更低（否则也不会通过 autoclear 的四项前置条件），审计的价值是
  "校准 autoclear 判定本身可不可信"，是二阶目标。如果自动清关候选量
  一旦膨胀就能把真正有实质改动、还没有任何判定为它背书的候选**完全**
  挤出人工视野，那是本末倒置——真实编辑风险应该优先于"再确认一下已经
  过关的东西是不是真的没问题"。
- **为什么是"最多一半"而不是"全部给排位"**：抽检本身也不能形同虚设——
  如果排位池稍微大一点（哪怕只有几十条真实改动）就能把抽检挤到 0，
  autoclear 通道就会长期处于"无人验证"状态，一旦某个通道的自动清关
  判定系统性跑偏（比如某次准入小考通过了但实际表现变差），要等到人
  自己发现才会被注意到——抽检兜底的意义就没有了。"一半"是本任务在
  brief 没有给出具体数字时选择的一个居中值，不追求精确调优（brief §9
  "调整记台账、不以自动入库率为优化目标"同样适用于这里）。
- **为什么用 `ceil` 而不是 `floor`**：只有在 `K` 为奇数、且排位池与
  抽检都"想要"最后那一个名额时才有区别（`K=1` 是最极端的例子：
  `floor(1/2)=0` 会让抽检拿到唯一的名额、排位池颗粒无收；`ceil(1/2)=1`
  则反过来。按上一条"真实编辑风险优先于二阶审计"的裁定，这唯一的
  名额应该给排位池，所以取 `ceil`）。
- **为什么设了 `min(..., len(non_autoclear_ids))`**：排位池没有那么多
  真实候选时，不占着不用的配额——K=150 而只有 5 条真实改动候选时，
  不应该白白锁掉 70 个名额只给排位池摆着，那 70 个应该回流给抽检
  （`sample_cap = K - rank_floor` 会自动变大，因为 `rank_floor` 已经
  按实际需要收窄了），这样在正常规模下（K=150、真实改动候选往往有
  几十上百条）不会改变原有行为——`rank_floor`/`sample_cap` 的计算
  只在候选量足够极端时才会真正触发裁剪。

**抽检覆盖率被压缩必须"响"**（brief"限了什么就得说出来"这条一贯原则
的延伸，控制者本轮明确要求）：`sampled_dropped > 0` 时打印到 stderr
（配置抽检率 vs 实际达成比率 vs 少抽了多少条），并把 `sample_rate_
configured`/`sample_rate_effective`/`sampled_dropped`/`autoclear_
eligible_total`/`sampled_count`/`K` 六项落进 `triage.json` 顶层的
`meta` 字段——不依赖读 stderr 日志才能知道覆盖率被削减过，落盘的
`triage.json` 本身就带着这份证据，供 Task 10（准入小考/推翻率统计）
之后复核。`autoclear_ids` 为空（没有任何自动清关候选）时
`sample_rate_effective` 记 `None`（不是 0——"没有分母"和"抽检率恰好
是 0" 是两件不同的事，`None` 明确表达"这个比率在本次 triage 里无意义"，
不会被后续统计代码误当成"这个通道抽检率是 0%"）。

### 3. `edit == 0` 与 `zh == opus` 的关系：两套归一化，不能共用一套

brief 点名的风险："归一过头会把「只改了控制码位置」的真实改动误判成
零改动，那是静默丢失"。本模块对"相等"和"幅度"故意用**两套不同**的
归一化，缺一不可：

- **桶 1 的"零改动"判据**（`_ws_equal`）：只做 `.strip()`（掐首尾空白），
  `_n`/`_r`/ruby 全部**原样保留参与比较**。理由：这些控制码是内容的
  一部分（`_n`/`_r` 决定断行位置，ruby 的拼音/注音部分是要显示给玩家
  看的文字），如果润色只是把 `_n` 挪了个位置、或者改了 ruby 注音的
  拼音拼写，这**是一次真实的、需要被看见的改动**——不能因为"剥掉
  控制码之后两边长得一样"就悄悄归零，那样这次改动会从 triage.json
  里彻底消失（既不产生 patch，也不会被任何人看到），是不可接受的
  静默丢失。
- **`edit`（幅度分档，供排序与 autoclear 阈值比较用）**：`edit_distance`
  跑在 `polishlib.strip_ctl()` 剥过控制码/ruby 之后的文本上。理由：
  `autoclear_limit(opus_zh)` 本身就是"以剥控制码后的长度算比例阈值"
  （`tools/polishlib.py` 第 39-40 行），如果 `edit` 却在带控制码的原文
  上算，两者的"单位"对不上——一次纯粹的 `_n`→`_r` 换行方式调整会被
  计入很大的编辑距离，跟"幅度阈值是按可读正文字数定的"这个设计初衷
  冲突，会把大量"内容其实没怎么变、只是断行方式变了"的候选错误地
  推去人工排队，稀释 K 配额、掩盖真正的大改动。

两套分开之后互不干扰：一次纯控制码变动，`_ws_equal` 判定为"有改动"
（不会被静默吞掉、能进入 pool 参与排序/autoclear），但 `edit`（幅度）
很可能算出接近 0（因为剥控制码后两边文本一样）——只要 gates 绿、通道
清关权开，这类"改动真实存在但幅度可忽略"的候选恰好会被 autoclear
判定为"小改"而自动清关，这正是我们想要的行为：改动没有被隐藏（触发
了自动清关流程），但也没有占用宝贵的人工审阅名额（幅度确实可忽略）。

## id 级 all-or-nothing 的 autoclear 规则

上面第 3 点提到："一个 id 只有组内全部候选行都 eligible 才整体摘出"。
换句话说：**autoclear 是以 id 为单位的整体决定，不是逐通道各自决定**。
如果同一 id 下 channel A 的候选够格自动清关、channel B 的候选不够格
（比如改动更大、或 gates 没过），这个 id 整体留在 `pool` 里正常排队，
channel A 那一行**不会**被单独摘走——理由与 K 配额分组一致：既然这个
id 注定要摆上人工裁决台面（因为 channel B 需要人看），channel A 的
候选留在台面上供人一起参照比较，没有必要（也不应该）自己先斩后奏
清关掉。反过来，如果这个 id 名下**只有一个**通道提交过候选（P4 的
主要形态——多通道分段分担为主），"全部候选行" 退化成"这一行"，
all-or-nothing 规则自然退化成普通的单行判定，不额外增加负担。

## 抽样与排序的确定性

`random.Random(int(manifest["files"]["frozen/source.jsonl"][:8], 16))`
——⚠ **与 brief 原文一处已核实的偏差**：brief 写的 key 是
`"source.jsonl"`，但实测 `polish_setup.setup()` 落盘的 `manifest.json`
里 `files` 字典的 key 是**相对 SEG 目录**的路径（`p.relative_to(d)`，
`d` 是 `pilot/polish/<label>/`，`p` 遍历的是 `d/"frozen"` 子树），实际
key 是 `"frozen/source.jsonl"`，不带 `frozen/` 前缀的 `"source.jsonl"`
在真实 manifest 里**不存在**，按 brief 字面实现会在真实 SEG 上直接
`KeyError`。已用临时仓库跑过一遍 `polish_setup.setup()` 验证（见
task-7-report.md），按实测结果改用 `"frozen/source.jsonl"`。

随机数**只用在一处**：从 `autoclear_ids`（此时已经是一个与排序无关、
仅由"是否全部符合 autoclear 资格"决定的集合）按固定顺序（`sorted()`
出来的 id 升序）逐个抽取 `rng.random() < sample_rate`。这保证了两次
调用 `triage()`（同一份磁盘状态、没有任何东西被改动）产生**完全一致**
的抽样结果——`test_deterministic_sampling` 验证的就是这件事。**排序
本身不需要随机数**：`_sort_key` 用显式的 `(adjudicate, edit, score, id)`
四元组做 key，`id` 作为最终并列打散兜底，Python 的 `sorted()` 本身
就是确定性的稳定排序，不依赖字典/集合的迭代顺序（本模块里所有会影响
输出顺序的地方——`channels`、`pool` 的 id 遍历、最终 `rows` 落盘前—
—都显式 `sorted()` 过，不依赖 `dict`/`set` 的天然迭代顺序，虽然
CPython 3.7+ 字典本身有序，但集合 `set` 的迭代顺序不保证，本模块用到
集合的地方（`locked_ids`、`sampled_ids`、`top_ids`）全部只用来做
`in` 成员判断，从不直接迭代取顺序）。

## queue.md：给人裁决用，抽检项"标出来但不泄露"

`queue.md` 只收桶 2（K 配额内）的 id，按 id 升序排列；每个 id 一节，
并排列出该 id 全部通道的候选（jp 原文 + opus 现行译文 + 各通道
`zh`/`score`/批注），外加一行"为什么进队列"。

**抽检的标注权衡**（brief 明确要求自己拿主意）：`triage.json` 里的
`sampled` 字段如实记录（机器可读、供 Task 10 之后统计推翻率），但
`queue.md`（人读的裁决界面）**故意不出现"这是随机抽检"这几个字**。
原因：知道某一条是"已经自动清关、只是抽出来给你复核一下"会实质性
改变裁决者的心态——大概率会倾向于"既然已经通过了，那就没问题吧"
从而降低审查强度，这恰恰摧毁了抽检本来要验证的东西（"自动清关的
判定是否可信"，需要裁决者用跟审别的候选**同样**的严格程度去看它，
结果才有统计意义）。所以 `queue.md` 里能显式区分的"为什么进队列"
只有两档：
- **「显式请裁」**：该 id 至少一个通道候选 `adjudicate=True`。
- **「进入本轮裁决队列」**：其余全部情况——不管是"改动幅度靠前、
  正常排位挤进了 K 配额"还是"已自动清关、抽中审计样本被塞回来"，
  一律用这句话，**故意不再细分**，让两者在文档里长得一模一样。

## `channel_state.json` 缺失时的保守缺省

`channel_state.json` 是 Task 10（准入小考）的产出，本任务实施时**尚
不存在**、也不应该在本模块里创建。文件整体缺失，或者某个 channel
压根不在里面（比如刚接入的新通道，还没跑过准入小考）——两种情况
一律视为"该通道自动清关权关闭"。这是故意的保守缺省，呼应 CLAUDE.md/
brief 反复强调的原则："没考过准入小考就不许免检"——**任何把这个缺省
翻转成"缺失=默认开启"的改动都是危险的**（会让一个从未被校准过的
新通道，第一天接入就能自动往库里写东西），本模块专门为这个缺省
方向配了一个变异自检（见 `tests/test_polish_triage.py`）。
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl
from tools.polishlib import CFG, autoclear_limit, edit_distance, strip_ctl


def _dir_for(label, repo) -> Path:
    """同 Task 3/4/5/6 一致的理由：`polishlib.seg_dir()` 硬编码仓库根，
    这里另起一份只在 `repo` 落空时退化，使 `triage()`/CLI 都能被 tmp_path
    造的替身仓库完全接管（测试要求：不得写进真实仓库的 `pilot/polish/`）。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def load_gates(path) -> dict | None:
    """读 `gates.<channel>.json`，返回
    `{"checked_ids": set[int], "findings": {int: {"hard": […], "warn": […]}}}`
    （磁盘上 findings 的 key 是 JSON 字符串——int 键无法落 JSON，见
    `polish_check.gate()` 落盘前的显式转换——这里统一转回 int 键）。

    返回 `None`（不是空结构）表示"这个通道的 gates 文件根本不存在"——即
    `polish_check.gate()` 从未针对这个通道跑过；这与"跑过、全绿"是两种
    不同的状态，`triage()` 据此做出的默认动作也不同：**没有 gates 证据 →
    不允许该通道任何候选自动清关**（与 `channel_state.json` 缺失时的保守
    缺省同一逻辑：没有证据就不给通过）。

    **`checked_ids` 是最终评审 C1 的修复承重点**：文件存在不等于"文件里
    没提到的那个 id 被检查过"。陈旧 gates（跑过 gate 之后又入仓了新批次）
    下，新 id 在 findings 里查无此人，初版据此判"干净"→ 直通自动清关。
    现在改判"不在 checked_ids 里 → 没有证据 → 不 eligible"，把文件层已有
    的保守缺省贯彻到 id 层。

    **旧格式兼容（安全方向）**：读到没有 `checked_ids` 键的裸字典（本次
    改版之前落盘的文件），`checked_ids` 取**空集**而不是"findings 的键集"
    也不是"全部"——空集意味着该通道本轮一个 id 都不许自动清关，操作者会
    在 triage 的 stderr 告警里看到"请重跑 polish_check"。反过来把它当成
    "全部检查过"就等于把 C1 这个洞原样保留下来。
    """
    p = Path(path)
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    if "checked_ids" not in raw:
        print(f"!! polish_triage: {p} 是**旧格式** gates 文件（无 checked_ids），"
              "无法区分「查过且干净」与「从未查过」——本轮该通道一律不予自动清关。"
              "请重跑 `polish_check.py --seg … --channel …` 后再 triage。",
              file=sys.stderr)
        return {"checked_ids": set(),
                "findings": {int(k): v for k, v in raw.items()}}
    return {"checked_ids": {int(i) for i in raw.get("checked_ids", [])},
            "findings": {int(k): v for k, v in raw.get("findings", {}).items()}}


def _load_channel_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _channel_autoclear_power(channel, channel_state) -> bool:
    """`channel_state.json` 缺失、或该 channel 不在里面 → 自动清关权
    一律关闭（保守缺省，见模块 docstring 专节）。`channel == "amplify"`
    恒 False，与 `channel_state` 内容无关——这条硬规则由调用方
    （`_row_eligible`）里另一个独立条件表达，这个函数本身只负责读取
    配置这一件事，不在这里重复判 amplify（保持单一职责，"amplify 恒
    不清关"这条硬规则集中写在一处，靠调用方合取）。
    """
    return bool(channel_state.get(channel, {}).get("autoclear", False))


def _ws_equal(a, b) -> bool:
    """桶 1"零改动"判据的归一化——只做空白层面的 `.strip()`，`_n`/`_r`/
    ruby 全部原样保留参与比较。见模块 docstring"edit==0 与 zh==opus 的
    关系"专节：归一过头（比如顺手剥了控制码再比）会把"只改了控制码
    位置/ruby 拼音"这类真实改动误判成零改动，那是静默丢失。"""
    sa = a.strip() if isinstance(a, str) else ""
    sb = b.strip() if isinstance(b, str) else ""
    return sa == sb


def _content_edit(zh, opus_zh) -> int:
    """幅度分档用的编辑距离——在 `strip_ctl()` 剥过控制码/ruby 之后的
    文本上算，与 `polishlib.autoclear_limit()` 的阈值基准（同样剥过
    控制码再算长度）保持同一"单位"，见模块 docstring 专节。"""
    zs = strip_ctl(zh) if isinstance(zh, str) else ""
    os_ = strip_ctl(opus_zh) if isinstance(opus_zh, str) else ""
    return edit_distance(zs, os_)


def triage(label, repo=None) -> dict:
    """对该 SEG 全部通道当前保税仓里的候选做四桶分流 + 条件自动清关 +
    确定性抽检，写 `triage.json` + `queue.md`，返回
    `{"rows": [{id, channel, bucket, edit, autoclear, sampled}, ...],
      "queue_ids": [...]}`。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"

    source_rows = read_jsonl(fz / "source.jsonl")
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    opus_rows = read_jsonl(fz / "opus.jsonl")
    id2opus = {r["id"]: r["zh"] for r in opus_rows}
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    # 旧格式兼容：没有 hard_ids/soft_ids 键时，把 ids（旧版全集）整体当硬锁
    # ——与 `polish_ingest.ingest()` 的同款兼容口径一致，见其模块 docstring。
    if "hard_ids" in locked or "soft_ids" in locked:
        hard_ids = set(locked.get("hard_ids", []))
        soft_ids = set(locked.get("soft_ids", []))
    else:
        hard_ids = set(locked.get("ids", []))
        soft_ids = set()

    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    seed_hash = manifest["files"]["frozen/source.jsonl"]
    rng = random.Random(int(seed_hash[:8], 16))

    channel_state = _load_channel_state(d / "channel_state.json")

    channels = sorted(
        p.name[len("candidates."):-len(".jsonl")]
        for p in d.glob("candidates.*.jsonl")
    )

    rows = []       # 已定桶（0/1）或即将定桶（2/3）的全部候选行，最终输出源
    pool = {}       # id -> [row, ...]：尚待裁决/自动清关判定的候选
    forced_soft_ids = set()   # 软锁 id 且真的改了——强制桶 2，不进 pool
    forced_adjudicate_ids = set()   # adjudicate=true（无论改没改）——强制桶 2，不进 pool

    for channel in channels:
        candidates = read_jsonl(d / f"candidates.{channel}.jsonl")
        last_by_id = {}
        for c in candidates:
            last_by_id[c["id"]] = c  # 同 id 后行覆盖前行——取最后一条

        gates = load_gates(d / f"gates.{channel}.json")

        for cid in sorted(last_by_id):
            c = last_by_id[cid]
            if cid not in id2jp:
                print(f"!! polish_triage: {label}/{channel} 的候选 id={cid} "
                      "不在 frozen/source.jsonl 里，已跳过", file=sys.stderr)
                continue

            zh = c.get("zh")
            opus_zh = id2opus.get(cid, "")
            row = {
                "id": cid, "channel": channel,
                "bucket": None, "edit": _content_edit(zh, opus_zh),
                "autoclear": False, "sampled": False,
                "_zh": zh, "_note": c.get("note", ""),
                "_score": c.get("score"), "_adjudicate": bool(c.get("adjudicate", False)),
            }

            if cid in hard_ids:
                row["bucket"] = 0
                rows.append(row)
                continue
            if cid in soft_ids and not _ws_equal(zh, opus_zh):
                # 软锁（锚点）行且真的改了——无条件强制进队列，永不自动
                # 清关、不参与 K 配额排序竞争。见模块 docstring"软锁强制
                # 进队列"专节。`polish_ingest` 已保证这类候选带
                # `adjudicate=true`，本层不重新校验这个前提，只按"是软锁
                # 且真的改了"这一条件本身触发（belt-and-suspenders：即使
                # 某条候选绕开 ingest 直接写入 candidates 文件，本层依然
                # 会把它按最严格的方式对待）。**检查顺序排在"零改动"判据
                # 之前**——这条与紧随其后的"显式请裁"分支同理，见模块
                # docstring"桶判定顺序"专节的顺序说明。
                row["bucket"] = 2
                rows.append(row)
                forced_soft_ids.add(cid)
                continue
            if row["_adjudicate"]:
                # 显式请裁——无论有没有改动，一律强制进队列，永不自动
                # 清关、不参与 K 配额排序竞争。见模块 docstring"显式请裁
                # 强制进队列（D3 修复）"专节：契约鼓励"拿不准就照抄+请裁"，
                # 这条分支保证这类请求不会被下面的"零改动→桶1"分支拦下
                # 静默丢弃，也不会被后面 pool 的 autoclear 判定悄悄吃掉。
                row["bucket"] = 2
                rows.append(row)
                forced_adjudicate_ids.add(cid)
                continue
            if _ws_equal(zh, opus_zh):
                row["bucket"] = 1
                rows.append(row)
                continue

            # --- 机械闸证据（最终评审 C1/C2 修复后的三段判定）---
            # ① 文件在不在（gate 跑过没有）；② 这个 id 在不在本次检查的覆盖面
            #    里（陈旧 gates 的新候选＝没有证据）；③ 覆盖面内才谈 hard/warn。
            gate_checked = gates is not None and cid in gates["checked_ids"]
            gate_entry = (gates["findings"].get(cid) or {}) if gates is not None else {}
            gates_hard_empty = gate_checked and not gate_entry.get("hard")
            # W3（显示行宽超限）是唯一一条对应**真实游戏内故障**的 warn——中文
            # 比日文占宽，溢出玩家一眼看得见。其余 warn（W1 断行数差/W2 术语提示/
            # W4 复现句族，后者本层根本不跑）保持"不阻断"：它们要么是粗略提示、
            # 要么另有专门环节（W4 见 polish_check.w4_full）。带 W3 的候选照常
            # 进人裁队列，只是不能免检直通。
            no_w3 = not any(v.get("rule") == "W3" for v in gate_entry.get("warn", []))
            row["_eligible"] = (
                channel != "amplify"
                and row["edit"] <= autoclear_limit(opus_zh)
                and gates_hard_empty
                and no_w3
                and _channel_autoclear_power(channel, channel_state)
            )
            pool.setdefault(cid, []).append(row)

    # --- id 级 all-or-nothing：组内全部候选行都 eligible 才整体摘出 ---
    autoclear_ids = sorted(cid for cid, grp in pool.items()
                            if grp and all(r["_eligible"] for r in grp))
    non_autoclear_ids = sorted(set(pool) - set(autoclear_ids))

    # --- 确定性抽样：固定顺序（id 升序）逐个抽，seed 来自 manifest 哈希 ---
    # 这一步只决定"配置比率下本该抽中谁"，产出的 desired_sampled_ids 可能
    # 比 K 还大（评审 Important：autoclear 候选量足够大时必然发生）。真正
    # 的 K 帽在下面单独一段处理，见模块 docstring"抽检 K 帽与最小配额"专节。
    K = CFG["K"]
    forced_soft_ids = sorted(forced_soft_ids)
    forced_adjudicate_ids = sorted(forced_adjudicate_ids)
    n_forced_soft = len(forced_soft_ids)
    n_forced_adjudicate = len(forced_adjudicate_ids)
    # 去重后的并集——同一 id 可能同时命中"软锁+改动"（走软锁支路）与
    # "另一通道 adjudicate=true 但零改动"（走请裁支路），K 预算只能按 id
    # 扣一次。见模块 docstring"K 预算的合并去重"专节。
    forced_all_ids = sorted(set(forced_soft_ids) | set(forced_adjudicate_ids))
    n_forced_total = len(forced_all_ids)
    forced_soft_over_budget = n_forced_soft > K
    forced_total_over_budget = n_forced_total > K
    if forced_soft_over_budget:
        print(f"!!!! polish_triage: {label} 软锁（锚点行）改动数 {n_forced_soft} "
              f"超过人工预算 K={K}——这些行仍然全部强制进入裁决队列（不受 K 限制、"
              "也不可能被自动清关），但已经没有名额留给抽检/正常排位。这是真信号"
              "（近期大量改动了锚点行），不是本工具的截断，需要立即关注，不能被"
              "静默吸收。", file=sys.stderr)
    elif forced_total_over_budget:
        print(f"!!!! polish_triage: {label} 强制进队列的行合计 {n_forced_total} "
              f"（软锁改动 {n_forced_soft} + 显式请裁 {n_forced_adjudicate}，去重后）"
              f"超过人工预算 K={K}——软锁单独看不超预算，是两类强制项叠加后才超的。"
              "这些行仍然全部强制进入裁决队列（不受 K 限制、也不可能被自动清关），"
              "但已经没有名额留给抽检/正常排位。不是本工具的截断，需要立即关注。",
              file=sys.stderr)
    # 两类强制占用都排在抽检占用之前分配（用户裁定的顺序对软锁那条已经定案：
    # "软锁改动行先占位，其余名额再按原排序分配"；显式请裁与软锁同等待遇，
    # 延伸适用同一顺序）——K 先扣掉去重后的强制占用合计，下面抽检/排位的
    # 全部推导都改用这个"剩余预算"，恒 >= 0。
    K_remaining = max(0, K - n_forced_total)

    desired_sampled_ids = sorted(cid for cid in autoclear_ids
                                  if rng.random() < CFG["sample_rate"])

    # 给"正常排位"（真实改动候选）留一个最小配额：最多 K_remaining 的一半
    # （ceil，K 为奇数时最后一个名额偏向排位而不是抽检——理由见 docstring），
    # 但不会预留超过排位池实际需要的量（没有真实候选就不占空）。抽检能用
    # 的名额上限 = K_remaining 减去这个保底。
    rank_floor = min((K_remaining + 1) // 2, len(non_autoclear_ids))
    sample_cap = max(0, K_remaining - rank_floor)
    if len(desired_sampled_ids) > sample_cap:
        sampled_ids = set(desired_sampled_ids[:sample_cap])
        sampled_dropped = len(desired_sampled_ids) - sample_cap
    else:
        sampled_ids = set(desired_sampled_ids)
        sampled_dropped = 0

    sample_rate_configured = CFG["sample_rate"]
    sample_rate_effective = (len(sampled_ids) / len(autoclear_ids)
                              if autoclear_ids else None)
    if sampled_dropped:
        eff_str = f"{sample_rate_effective:.1%}" if sample_rate_effective is not None else "N/A"
        print(f"!! polish_triage: {label} 自动清关候选过多（{len(autoclear_ids)} 个满足条件），"
              f"抽检名额被人工预算 K={K} 压缩——配置抽检率 "
              f"{sample_rate_configured:.0%}，实际达成 {eff_str}，少抽 "
              f"{sampled_dropped} 条。抽检是自动清关这条免检通道的唯一兜底，"
              "覆盖率被压缩必须被看见，不能静默发生。", file=sys.stderr)

    for cid in autoclear_ids:
        for r in pool[cid]:
            r["autoclear"] = True
            r["sampled"] = cid in sampled_ids
        if cid not in sampled_ids:
            for r in pool[cid]:
                r["bucket"] = 3
            rows.extend(pool[cid])

    # 抽中的自动清关 id：强制塞回裁决队列（bucket=2），不参与下面的排序
    # 竞争——它们"占 K"，不是"跟别人抢 K"。
    for cid in sorted(sampled_ids):
        for r in pool[cid]:
            r["bucket"] = 2
        rows.extend(pool[cid])

    def _sort_key(cid):
        grp = pool[cid]
        adjudicate_flag = any(r["_adjudicate"] for r in grp)
        max_edit = max(r["edit"] for r in grp)
        scores = [r["_score"] for r in grp if isinstance(r["_score"], (int, float))]
        min_score = min(scores) if scores else -1  # 缺分默认最优先复核
        return (not adjudicate_flag, -max_edit, min_score, cid)

    ranked_ids = sorted(non_autoclear_ids, key=_sort_key)
    # K_remaining 减去(已经封顶过的)抽检占用——不变量：len(sampled_ids) +
    # len(top_ids) + n_forced_total <= K 恒成立（sampled_ids 已经被上面的
    # sample_cap 逻辑封顶过，而 sample_cap 本身就是基于 K_remaining 算的，
    # K_remaining 已经扣过去重后的软锁+请裁强制占用合计）。
    quota = max(0, K_remaining - len(sampled_ids))
    top_ids = set(ranked_ids[:quota])

    for cid in ranked_ids:
        bucket = 2 if cid in top_ids else 3
        for r in pool[cid]:
            r["bucket"] = bucket
        rows.extend(pool[cid])

    rows.sort(key=lambda r: (r["id"], r["channel"]))
    queue_ids = sorted({r["id"] for r in rows if r["bucket"] == 2})

    out_rows = [{"id": r["id"], "channel": r["channel"], "bucket": r["bucket"],
                 "edit": r["edit"], "autoclear": r["autoclear"], "sampled": r["sampled"]}
                for r in rows]
    meta = {
        "K": K,
        "sample_rate_configured": sample_rate_configured,
        "sample_rate_effective": sample_rate_effective,
        "autoclear_eligible_total": len(autoclear_ids),
        "sampled_count": len(sampled_ids),
        "sampled_dropped": sampled_dropped,
        "forced_soft_count": n_forced_soft,
        "forced_soft_over_budget": forced_soft_over_budget,
        "forced_adjudicate_count": n_forced_adjudicate,
        "forced_total_count": n_forced_total,
        "forced_total_over_budget": forced_total_over_budget,
    }
    result = {"rows": out_rows, "queue_ids": queue_ids, "meta": meta}

    d.mkdir(parents=True, exist_ok=True)
    (d / "triage.json").write_text(dumps(result), encoding="utf-8")
    _write_queue_md(d, queue_ids, rows, id2jp, id2opus, set(forced_soft_ids),
                     set(forced_adjudicate_ids))
    return result


def _write_queue_md(d: Path, queue_ids, rows, id2jp, id2opus, forced_soft_ids=frozenset(),
                     forced_adjudicate_ids=frozenset()) -> None:
    """人读的裁决队列。同 id 的多通道候选并排列出；"为什么进队列"分四档：
    软锁改动（锚点行，强制进队列，不受 K 名额影响）/ 请裁·未改动（D3 修复：
    该 id 名下全部 `adjudicate=true` 的候选行都与 opus 逐字相同——没有 diff
    可看，只有疑问，必须显式标出，不能让裁决者以为是空记录）/ 显式请裁
    （请裁且确有改动）/ 进入本轮裁决队列（刻意不再细分"正常排位"与"抽检"
    ——见模块 docstring"queue.md：抽检项标出来但不泄露"专节）。软锁与请裁
    两档单独标注是有意的：与"隐藏抽检来源以防止裁决者放松审查"的顾虑不同，
    让裁决者知道"这是锚点句"或"这行没改但通道有疑问"只会让审查更审慎，不
    构成同类风险。"""
    by_id_rows = {}
    for r in rows:
        if r["bucket"] == 2:
            by_id_rows.setdefault(r["id"], []).append(r)

    lines = ["# 裁决队列\n", f"共 {len(queue_ids)} 个待裁 id（K 配额内，"
             "软锁/显式请裁强制进队列的 id 不计入 K 但同样列在下面）。\n"]
    for cid in queue_ids:
        group = sorted(by_id_rows.get(cid, []), key=lambda r: r["channel"])
        lines.append(f"## id {cid}\n")
        lines.append(f"- 日文原文：{id2jp.get(cid, '')}")
        opus_zh = id2opus.get(cid, "")
        lines.append(f"- 现行译文（opus）：{opus_zh}")
        if cid in forced_soft_ids:
            reason = "软锁改动（锚点行，强制进入队列，不受 K 名额影响）"
        elif cid in forced_adjudicate_ids:
            adjudicated_rows = [r for r in group if r["_adjudicate"]]
            all_unchanged = bool(adjudicated_rows) and all(
                _ws_equal(r["_zh"], opus_zh) for r in adjudicated_rows)
            if all_unchanged:
                reason = ("请裁·未改动（通道没有改这一行，但主动标记了疑问——"
                           "不是空记录，请看下面各通道行的批注）")
            else:
                reason = "显式请裁"
        elif any(r["_adjudicate"] for r in group):
            reason = "显式请裁"
        else:
            reason = "进入本轮裁决队列"
        lines.append(f"- 进入队列原因：{reason}")
        for r in group:
            unchanged_tag = ("　`[本通道未改动，与 opus 逐字相同]`"
                              if _ws_equal(r["_zh"], opus_zh) else "")
            note = f"（批注：{r['_note']}）" if r["_note"] else ""
            lines.append(f"- **{r['channel']}**（score={r['_score']}）："
                          f"{r['_zh']}{note}{unchanged_tag}")
        lines.append("")
    (d / "queue.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 四桶分流 + 条件自动清关 + 确定性抽检")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    result = triage(args.seg, repo=args.repo)
    rows = result["rows"]
    counts = {b: sum(1 for r in rows if r["bucket"] == b) for b in (0, 1, 2, 3)}
    n_autoclear = sum(1 for r in rows if r["autoclear"])
    n_sampled = sum(1 for r in rows if r["sampled"])
    print(f"triage: {args.seg} 共 {len(rows)} 条候选（跨全部通道）——"
          f"桶0 {counts[0]} / 桶1 {counts[1]} / 桶2 {counts[2]} / 桶3 {counts[3]}，"
          f"自动清关 {n_autoclear}（其中抽检 {n_sampled}），"
          f"裁决队列 {len(result['queue_ids'])} 个 id")
    dropped = result["meta"]["sampled_dropped"]
    if dropped:
        print(f"!! 抽检覆盖率被 K 压缩：少抽 {dropped} 条（详见 stderr 告警与 "
              "triage.json 的 meta 字段）")
    n_forced = result["meta"]["forced_soft_count"]
    if n_forced:
        over = "（已超出 K 预算！）" if result["meta"]["forced_soft_over_budget"] else ""
        print(f"软锁（锚点行）改动强制进队列 {n_forced} 个 id{over}")
    n_forced_adj = result["meta"]["forced_adjudicate_count"]
    if n_forced_adj:
        print(f"显式请裁（adjudicate=true，含未改动的）强制进队列 {n_forced_adj} 个 id")
    if result["meta"]["forced_total_over_budget"]:
        print(f"!! 强制进队列合计 {result['meta']['forced_total_count']} 个 id 已超出 "
              f"K 预算（K={result['meta']['K']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
