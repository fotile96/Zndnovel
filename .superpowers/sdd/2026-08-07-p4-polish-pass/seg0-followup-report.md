# SEG-0 followup：两个 P4 润色工装缺口修复报告

修的是 SEG-0（`pilot/polish/seg0-s0-s1/`，4282 行、506 条裁决）实跑暴露的两个
工装缺口，原始记录见 `pilot/polish/seg0-s0-s1/channel_feedback.md` D3/D4 节。

状态：两个缺口均已修复、测试全绿、变异全部按预期红/绿、用真实 SEG-0 数据分别
复现验证过（复现在 tmp 副本里做，未写真实目录）。

---

## 缺口一（D3）：`adjudicate=true` 但未改动的候选被静默丢弃

### 改法与理由

`tools/polish_triage.py` 原分桶顺序是：硬锁 → 零改动（`zh==opus`）→ 软锁+改动
→ 其余进 pool 排队/自动清关。`adjudicate=true` 这个字段完全不参与前两步判定，
于是：

1. 零改动 + `adjudicate=true` 的候选被"零改动"分支拦下，直接落桶 1，永远
   不会出现在 `queue.md` 里（D3 报告点名的 17002/7963）。
2. **同一判定链条上的隐藏镜像面**（原始 D3 记录未点名，本次一并堵上）：
   `adjudicate=true` 且**有**改动、但幅度小、机械闸全绿的候选，同样不受
   `adjudicate` 字段保护——它会正常流入 pool 走 `_eligible`/autoclear 判定，
   满足条件就被判 `autoclear=True`，除非恰好命中抽检，否则同样静默消失在
   桶 3。两种情形是同一句话"契约鼓励拿不准就请裁，但当前实现惩罚这个行为"
   的两种触发路径，只用一个判据（`adjudicate=true`）统一堵，不分别打补丁。

**修法**：把"`adjudicate=true`"这一条检查提到"零改动"判据**之前**，命中就
无条件 `bucket=2`、完全跳过 pool/autoclear 计算——与既有的"软锁+改动强制进
队列"机制完全对称（不占 K、不参与排序竞争）。检查顺序：硬锁 → 软锁+改动
（沿用原有，因为它已经隐含 `adjudicate=true`，检查顺序在前保留其"软锁改动"
专属标签）→ `adjudicate=true`（新增，覆盖零改动+软锁外的一切请裁）→ 零改动
→ 其余进 pool。

### 设计点裁定

**1. `queue.md` 呈现（零改动+请裁的行不能看着像空记录）**——归入"进入队列
原因"新增第三档：**请裁·未改动**（该 id 名下全部 `adjudicate=true` 的候选行
都与 opus 逐字相同时使用），与既有"软锁改动"/"显式请裁"并列，不再用笼统的
"进入本轮裁决队列"糊弄过去。另外，**每一条通道候选行**（不限于这一档）末尾，
若该行 `zh` 与 opus 逐字相同，追加 `` `[本通道未改动，与 opus 逐字相同]` ``
标记——这条标记独立于"进入队列原因"存在，任何情况下"桶 2 里这一行长得和
opus 一样"都值得一眼看出，不需要裁决者自己去对比原文。

**2. 与既有桶语义的协调**——归桶 2 带标记，**不新开一档**。理由：桶的语义
是"人要不要看"，请裁行显然要看，没必要为"为什么进来"另开一个桶（那是
"进入队列原因"文字该管的事）；新开一档会要求 `polish_commit`/`polish_audit`
等下游多认识一个 bucket 取值，风险大于收益。`triage.json` 既有字段含义
**完全不变**：`forced_soft_count`/`forced_soft_over_budget` 精确保留原语义
（只统计"软锁且改动"这一支路，不含本次新增的请裁支路）；新增
`forced_adjudicate_count`（请裁支路的 id 数）与 `forced_total_count`/
`forced_total_over_budget`（两支路去重并集，真正用于 K 预算扣减）——同一 id
可能同时命中两条支路（比如一个通道走软锁+改动、另一个通道对同一 id 零改动
但主动请裁），K 名额按 id 只扣一次，不会重复扣两次。下游消费者
（`polish_commit.py`/`polish_audit.py`）只读 `rows` 里的
`bucket`/`autoclear`/`sampled` 字段，已 grep 全仓确认不读这几个新 `meta.
forced_*` 字段，新增字段零风险。

**3. `polish_commit` 侧的处理**——裁决者对这类行的**正常归宿是
`keep_opus`**（不产生任何 patch）。但若裁决者仍选 `adopt`（比如想显式留一条
"人工确认过"的痕迹），`commit()` 必须安全落地：写出一条 `zh` 与 opus 逐字
相同的合法 patch，`prov` 倒查链完整，`resolve_map()` 消费是幂等的。这条路径
**不是错误**，不阻断，但加了一条信息级 stderr 提示（"这条 patch 是空 diff，
通常应改用 keep_opus"），呼应"静默写错比报错更坏"——虽然这不是"错"，也不该
悄无声息地在 `patches.jsonl` 里堆一条文字未变的记录而不给操作者任何提示。

### 改动文件

- `tools/polish_triage.py`：分桶顺序调整、新增 `forced_adjudicate_ids` 集合、
  `meta` 新增三个字段、`queue.md` 呈现逻辑（新增"请裁·未改动"档 + 未改动行
  内联标记）、CLI 输出补充打印。
- `tools/polish_commit.py`：新增 `_ws_equal()` 辅助、加载 `frozen/opus.jsonl`
  的 `id2opus`、在写入循环里对 adopt/edit 且译文与 opus 逐字相同的情形打一条
  信息级提示。
- `docs/ops/p4-polish-runbook.md` §七：更新四桶分流描述、`meta` 字段示例、
  `queue.md` 呈现说明、§十二 K 预算说明，写明本次修复。

### 新测试（`tests/test_polish_triage.py`）

新增夹具 `_build_mini_adjudicate_forced`（单批 4 个 id：50 零改动对照组、
51 零改动+请裁=D3 原始场景、52 小改+请裁=隐藏镜像面、53 小改无请裁对照组）+
5 条测试：

- `test_adjudicate_zero_edit_forced_into_queue_not_bucket1`：51 必须落桶 2，
  50 仍正常落桶 1。
- `test_adjudicate_small_edit_never_autoclears`：52（满足全部四项普通
  autoclear 条件）必须 `autoclear=False` 落桶 2；53（条件相同但无请裁）
  必须正常被 autoclear——证明新规则没有连带破坏正常自动清关。
- `test_adjudicate_forced_not_squeezed_out_by_zero_K`：K=0 时 51/52 仍强制
  进队列，`meta.forced_total_over_budget=True`。
- `test_adjudicate_queue_md_marks_unchanged_row_not_empty_looking`：queue.md
  里 51 显示"请裁·未改动"+"不是空记录"+未改动内联标记；52（有改动）显示
  "显式请裁"、不带"未改动"字样——证明呈现规则是有差别打的，不是无脑贴。
- `test_meta_forced_adjudicate_fields_present`：`meta` 新字段值正确
  （`forced_adjudicate_count=2`、`forced_soft_count=0`、
  `forced_total_count=2`、`forced_total_over_budget=False`）。

`tests/test_polish_commit.py` 新增 2 条：

- `test_adopt_zero_edit_candidate_writes_safe_noop_patch`：id 10（零改动）
  被人工裁成 `adopt`——patch 正确写出、`resolve_map` 幂等、stderr 含"空
  diff"与"keep_opus"提示、重复 `--apply` 仍是 no-op。
- `test_adopt_changed_candidate_does_not_print_noop_note`：对照组，id 11
  是真实大改的 adopt，不应触发"空 diff"提示。

全部原有 31（triage）+ 18（commit）条测试保持通过，新增 5 + 2 = 7 条全绿。

### 变异（红绿实况）

**Mutation A**（`tools/polish_triage.py`：把 `if row["_adjudicate"]:` 改成
`if False and row["_adjudicate"]:`，完全禁用修复）：

```
uv run pytest -q tests/test_polish_triage.py -k "adjudicate_zero_edit_forced or adjudicate_small_edit_never_autoclears or forced_not_squeezed or queue_md_marks_unchanged or meta_forced_adjudicate"
```
结果：**5 failed**（新增的 5 条全红）。用 Edit 还原。

**Mutation B**（窄化修复，只覆盖零改动这一半：`if row["_adjudicate"] and
_ws_equal(zh, opus_zh):`——模拟"只修了 D3 报告字面点名的那个场景，没堵住
隐藏镜像面"这种不完整修法）：

```
uv run pytest -q tests/test_polish_triage.py -k "..."
```
结果：**4 failed, 1 passed**——`test_adjudicate_zero_edit_forced_into_queue_
not_bucket1` **通过**（给出假绿），`test_adjudicate_small_edit_never_
autoclears` 等 4 条**正确转红**。这正是"绿变异必须分清两种解释"的示范：
如果测试集只有第一条，窄化修法会被误判为"修复完整"；`test_adjudicate_
small_edit_never_autoclears` 才是真正钉住"无论有没有改动"这几个字的测试。
用 Edit 还原。

**Mutation C**（`tools/polish_commit.py`：给信息级提示条件加 `False and`，
禁用"空 diff"提示）：

```
uv run pytest -q tests/test_polish_commit.py -k "noop or adopt_changed"
```
结果：**1 failed**（`test_adopt_zero_edit_candidate_writes_safe_noop_patch`
转红，`test_adopt_changed_candidate_does_not_print_noop_note` 仍绿——符合
预期，对照组不该受影响）。用 Edit 还原。

三处变异应用/还原均用 Edit 工具，还原后 `grep -n MUTATION tools/*.py
tests/*.py` 确认无残留，`git diff --stat` 未见异常残留。

### 用真实 SEG-0 数据复现验证

在 scratchpad 建 tmp 副本（`pilot/polish/seg0-s0-s1/{frozen,manifest.json,
candidates.{fable-wf,ds-flash}.jsonl,gates.{fable-wf,ds-flash}.json}` 原样
拷贝，**未写任何真实目录**），跑 `polish_triage.triage("seg0-s0-s1",
repo=<tmp>)`：

| id | channel | 修复前（真实 `triage.json`） | 修复后（tmp 重跑） |
|---|---|---|---|
| 17002 | fable-wf | bucket=1（丢弃） | **bucket=2** |
| 17002 | ds-flash | bucket=1（丢弃） | bucket=1（该通道确实未请裁，符合预期） |
| 7963 | ds-flash | bucket=1（丢弃） | **bucket=2** |
| 7963 | fable-wf | bucket=1 | bucket=1（未请裁，符合预期） |
| 269 | fable-wf | bucket=1（原靠 ds-flash 侥幸带进队列） | **bucket=2**（自身即被强制，不再依赖侥幸） |

`queue.md` 重跑后对这三个 id 的呈现分别是"请裁·未改动"（17002/7963/269 的
fable-wf 或 ds-flash 那一侧）——与真实候选文件里的 `note` 字段（"我不改，但
请你裁：同词終了在 17002 作「完结」……"等）完全对应，`meta.forced_adjudicate_
count=21`（真实 SEG-0 全量数据里有 21 个 id 命中这条新规则）。特别验证了
269 这个"混合"案例：ds-flash 侧是真实改动（`adjudicate=False`），fable-wf
侧零改动但 `adjudicate=True`——reason 逻辑正确识别出"未改动"指的是 fable-wf
那条请裁，不因 ds-flash 的无关改动而误判成"显式请裁但有改动"。

`git status --short pilot/polish/seg0-s0-s1/` 复现前后均为空，未污染生产
目录。

---

## 缺口二（D4）：`polish_check --w4-full` 每条 finding 只报一个伙伴

### 根因

`w4_full()` 计算的 `others`（该 jp 句族里、与本行现行译文不同的其它成员）
本身就是**全量**的——问题不在"漏扫"，在生成人读 `msg` 时复用了
`check_batch._w4_msg()`（P3 钉死面，为"批内交互复核"场景设计）：那个函数
**按 zh 文本去重**、只挑前 3 种文本变体各展示一个代表 id。这在 P3 语境下是
合理克制，但在 P4"全段收敛检查"语境下是缺陷：**当两个不同 id 恰好带着完全
相同的（错的）译法时，去重会把其中一个 id 的存在感抹掉**——SEG-0 实测正是
如此：7894 的句族有 9186/11407 两个其他成员，二者旧译文字面相同，第一轮
`msg` 只报出 9186，人工只同步了它，11407 要等下一轮重跑 W4 才暴露。

**不能改 `check_batch._w4_msg`/`check_batch.check()` 本身**——已 grep 确认
`tools/check_batch.py` 是本轮任务明确禁止改动的 P3 钉死面（`main()`/其它
调用方还在用它原本"批内截断"的行为，那个场景下截断是合理的）。

### 改法

在 `tools/polish_check.py`（P4 专属文件）新增：

- `_w4_full_msg(others, id2label)`：**不去重、不截断**，逐个列出全部成员，
  每条带 `id={id}@{段}` 前缀。
- `_load_segment_ranges(repo)` + `_id_to_label_map(repo, lane_dir)`：把
  `lane_dir/data/forward.jsonl` 的 `batch` 字段（首译批号，polish patch 不
  改这个历史事实）落进 `config/segments.yaml` 的 `batches` 区间，解出每个
  sibling id "首译时属于哪个 SEG"。查不到时标"未知段"（`seg: null`），不
  阻断——这是顾问级标注。
- `w4_full()` 改用上述两者：finding 结构新增 `siblings` 字段
  （`[{"id","zh","seg"}, ...]`，全族成员的结构化列表），`msg` 同步改为逐个
  列出全部成员，不再截断到 3 种 + "共 N 种异译"摘要。

### 设计点裁定

**1. `w4_full.json` 既有消费者会不会受影响**——已 grep 全仓
（`grep -rln "w4_full\|_w4_msg"`），除本模块自身与 `tests/test_polish_check.py`
外**无任何其它消费者**（`polish_commit.py`/`polish_audit.py`/
`polish_triage.py` 均不读这个文件）。`msg` 字段格式改变、新增 `siblings`
字段对现有生产流程零风险。

**2. "循环直到收敛"这条纪律还需不需要**——**仍需要**，已写进 runbook：
报全一族之后，单轮就能看全 7894/9186/11407 这类家族，循环次数应显著下降；
但"同步伙伴行"这个编辑动作本身仍可能让族里另一个此前未被提及的成员产生
新的不一致（比如把 A 改成跟 B 一致后，族里从未被提及的 C 现在又与新文本
不一致了）——这是"编辑行为本身产生新差异"这一层因果，报全一族解决不了它，
仍需重跑确认引入项归零。

**3. runbook §十一 更新**——已写明"每条 finding 现在报全族成员"、
`siblings` 字段结构、"所属段"解析方式与容错、"循环直到收敛"纪律保留及理由。

### 改动文件

- `tools/polish_check.py`：新增 3 个函数、`w4_full()` 内部改用新函数、finding
  结构新增 `siblings` 字段、docstring 补充 D4 修复专节。
- `docs/ops/p4-polish-runbook.md` §十一：写明修复内容、`siblings` 字段、
  "循环直到收敛"纪律保留的理由。

### 新测试（`tests/test_polish_check.py`）

- `test_w4_full_msg_lists_every_member_no_truncation`：5 个互不相同译法的
  纯函数级测试，逐个成员必须出现在 `msg` 里（对照 `check_batch._w4_msg` 会
  截断到 3+摘要）。
- `test_w4_full_reports_all_members_not_just_one`：id 900/901 的旧译文
  **字面相同**（D4 精确复现条件），finding 的 `siblings` 与 `msg` 都必须
  把两个都点出来，`w4_full.json` 落盘与返回值一致。
- `test_w4_full_siblings_report_segment_label`：跨两个段（segX 的 batch=1、
  segY 的 batch=2）验证 `siblings[].seg` 正确解出。
- `test_w4_full_siblings_seg_unknown_when_batch_out_of_range`：batch 号落在
  已知段区间之外时标"未知段"，不报错、不漏成员。

全部原有 22 条 `test_polish_check.py` 测试保持通过，新增 4 条全绿。

### 变异（红绿实况）

**Mutation D**（`w4_full()` 内 `out.append(...)` 前插入按 zh 文本去重逻辑，
还原成旧行为）：

```
uv run pytest -q tests/test_polish_check.py -k "w4_full"
```
结果：**1 failed**（`test_w4_full_reports_all_members_not_just_one` 转红，
断言 `sibling_ids == {900, 901}` 实得 `{900}`，精确复现 D4 症状），其余 8 条
仍绿。用 Edit 还原。

**Mutation E**（`id2label = _id_to_label_map(...)` 改成 `id2label = {}`，
破坏"所属段"解析）：

```
uv run pytest -q tests/test_polish_check.py -k "w4_full"
```
结果：**1 failed**（`test_w4_full_siblings_report_segment_label` 转红，
`seg` 期望 `"segY"` 实得 `None`），其余 8 条仍绿。用 Edit 还原。

两处变异均用 Edit 工具应用/还原，`grep -n MUTATION tools/*.py` 确认无残留。

### 用真实 SEG-0 数据复现验证

在 scratchpad 建 tmp 副本（只含 `config/segments.yaml` 与
`pilot/polish/seg0-s0-s1/frozen/source.jsonl` 的拷贝），`lane_dir` 直接指向
真实 `pilot/lanes/opus`（**只读**，`w4_full()` 不写 lane_dir，只写
`repo/pilot/polish/<label>/w4_full.json`，落在 tmp 里，未碰真实目录），跑
`polish_check.w4_full("seg0-s0-s1", "pilot/lanes/opus", repo=<tmp>)`：

- 28 条 finding（与真实已提交的 `w4_full.json` 条数一致——这 28 条是 D4 报告
  里"既有问题"的那批，SEG-0 段末已把本轮引入的 14 条同步收敛，本次复现不
  应、也确实没有引入新的不一致）。
- 其中 **4 条**的 `siblings` 里有两个成员共享**完全相同**的 zh 文本
  （7892→9184/11405、7954→9222/11443、8629→11650/11708、7228→10511/12639）
  ——这正是"旧代码按文本去重会吞掉一个"的精确适用场景。用旧的
  `check_batch._w4_msg()` 对这 4 组的真实 `others` 直接跑一遍验证：

  ```
  7892 OLD: 复现句族内不一致（同一 jp 另有译法）：id=9184 作「试着凝神细看。」
  7954 OLD: 复现句族内不一致（同一 jp 另有译法）：id=9222 作「○_n结果。」
  8629 OLD: 复现句族内不一致（同一 jp 另有译法）：id=11650 作「【アヤノ】「这样啊……」」
  7228 OLD: 复现句族内不一致（同一 jp 另有译法）：id=10511 作「【千秋】「好的」」
  ```

  旧代码分别漏报 11405（seg2-s3）、11443（seg2-s3）、11708（seg2-s3）、12639
  （seg3-s4）——全部是跨段伙伴，与 D4 记录里"伙伴所在段"跨越 seg2-s3/
  seg3-s4 的实况一致。新代码（`_w4_full_msg`）对同一批 `others` 输出：

  ```
  id=9184@seg0-s0-s1 作「试着凝神细看。」；id=11405@seg2-s3 作「试着凝神细看。」
  id=9222@seg0-s0-s1 作「○_n结果。」；id=11443@seg2-s3 作「○_n结果。」
  id=11650@seg2-s3 作「【アヤノ】「这样啊……」」；id=11708@seg2-s3 作「【アヤノ】「这样啊……」」
  id=10511@seg2-s3 作「【千秋】「好的」」；id=12639@seg3-s4 作「【千秋】「好的」」
  ```

  两个成员都报出，段标注也正确（seg0-s0-s1/seg2-s3/seg3-s4 均命中真实
  `config/segments.yaml` 的 batch 区间）。这是用真实生产数据对 D4 缺陷的
  直接、可复现的实锤，不是构造出来的假设场景。

`git status --short pilot/lanes/opus/ pilot/polish/seg0-s0-s1/` 复现前后均
为空，未污染任何生产目录。

---

## 测试结果

```
uv run pytest -q
810 passed in ~4s
```

基线 799 → 810，净增 11 条测试（triage 5 + commit 2 + check 4），全部与本次
两个修复一一对应。全部变异（A/B/C/D/E）均按预期红/绿，Mutation B 额外验证
了"绿变异必须分清两种解释"——窄化修法会让 D3 字面测试假绿，只有覆盖"隐藏
镜像面"的测试才能抓住不完整的修复。

## 未完全解决的条目 / 决定不修的

无。两个缺口按任务要求的范围全部修复，所有设计点均已裁定并写进本报告与
`docs/ops/p4-polish-runbook.md`。以下两点是裁定过程中主动扩大过的范围，
记录在此供复核：

- D3 的"隐藏镜像面"（`adjudicate=true` + 有改动 + 满足 autoclear 四项条件
  会被自动清关吃掉）不在原始 D3 报告的 3 个实测例子里，是本次分析代码路径
  时发现的同一判定链条上的关联缺陷，一并修复并补了专门的测试
  （`test_adjudicate_small_edit_never_autoclears`）与变异（Mutation B）。
- "所属段"解析（`_id_to_label_map`）是任务原文点名要报的字段，但实现依赖
  `forward.jsonl` 的 `batch` 字段 + `config/segments.yaml` 的区间——这条
  链路此前没有任何代码实现过（runbook D4 表格的"伙伴所在段"列此前是人工
  交叉核对填出的）。已用真实 SEG-0/2-s3/3-s4 三个段的数据验证解析结果正确。

## 相关文件

- `tools/polish_triage.py`（缺口一核心改动）
- `tools/polish_commit.py`（缺口一 adopt 安全落地）
- `tools/polish_check.py`（缺口二核心改动）
- `docs/ops/p4-polish-runbook.md`（§七、§十一、§十二 同步更新）
- `tests/test_polish_triage.py`（新增 5 条）
- `tests/test_polish_commit.py`（新增 2 条）
- `tests/test_polish_check.py`（新增 4 条）
