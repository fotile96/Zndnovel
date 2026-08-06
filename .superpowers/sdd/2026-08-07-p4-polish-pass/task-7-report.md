# Task 7 report：tools/polish_triage.py（四桶分流 + 自动清关判定 + 抽检）

状态：DONE。

## 文件

- `tools/polish_triage.py`（新增）——`triage(label, repo=None) -> dict`，写
  `pilot/polish/<label>/triage.json` + `queue.md`；CLI `--seg <label>
  [--repo ...]`。
- `tests/test_polish_triage.py`（新增，13 个用例，含 brief 给的 4 个 + 9
  个自行补充的，覆盖三处自行裁定的设计点与四个变异）。

## 接口（与 brief 一致，另加 `repo=` 参数，同 Task 3/4/5/6 先例）

`triage(label, repo=None) -> dict`，返回 `{"rows": [...], "queue_ids":
[...]}`；`rows` 是"每候选一条"的列表（不是字典——brief 说"返回 dict"，
但"每候选一条"的描述与测试里需要按 id/channel 检索单行的 `by_id()` 助手
函数（brief 没给出实现，本任务自己写）合起来看，最自然的形状是"dict 里
包一个 list"，见下方"与 brief 的偏差"第 1 条）。

## 桶判定顺序（完整决策表）

| 步骤 | 判据 | 结果 | 备注 |
|---|---|---|---|
| 1 | `id ∈ locked_ids`（`frozen/locked.json`） | bucket=0 | 兜底再判死；正常流程下 `polish_ingest.ingest()` 已经在入仓时挡掉锁定 id 出稿，候选文件里不该出现——本步骤防御的是"万一出现了" |
| 2 | 归一后 `zh == opus`（`.strip()`，**不剥控制码/ruby**） | bucket=1 | 见下方"设计点 3" |
| 3 | 其余候选按 id 分组，组内任一行 `adjudicate=True` 优先，同优先级按组内 `max(edit)` 降序，同 edit 按组内 `min(score)` 升序，最后 id 升序兜底去重 | 排前 `K − 抽检占用数` 名的 id → 2；其余 → 3 | 见下方"设计点 1" |
| （截流，发生在步骤 3 排序之前，与之并行独立计算） | `channel != "amplify"` 且 `edit ≤ autoclear_limit(opus)` 且该行所在通道 gates 里这个 id 的 `hard` 为空且该通道 `channel_state.json` 里 `autoclear=True` ——**组内全部候选行都满足才整体摘出** | `autoclear=True`；按 `sample_rate` 抽中的 `sampled=True` 强制塞回队列（bucket=2，不参与步骤 3 的排序竞争，直接占位）；未抽中的 `sampled=False`，`bucket=3`（记录在案，不进 `queue.md`） | 见下方"设计点 2" |

`edit` 字段（每行必填）＝`edit_distance(strip_ctl(zh), strip_ctl(opus))`
——与判定 bucket 0/1/2/3 是否命中无关，是排序与阈值比较用的"幅度"度量。

## 三个自行裁定的设计点

### 1. K 的分配：多通道同一 id 只占一个名额

`K`（150）是整个 SEG 的总额，多通道共享。裁决是**并排比较**（`queue.md`
把同一 id 的全部通道候选摆在一起给人一次看完），所以"是否占用一个 K
名额"按 **id** 算，不按 `(id, channel)` 行算——实现上把待裁决候选先按
`id` 分组（`pool: dict[id -> [row, ...]]`），排序 key、K 截断、bucket
2/3 的分配全部作用在"id"这一层，同一 id 名下全部候选行**永远拿到同一个
bucket**（不会出现"同一 id 两个通道的候选，一个算配额内一个算配额外"
这种自相矛盾的状态——那样"并排裁决"就没有意义）。

多通道聚合成一个排序 key 的具体取法：
- **`adjudicate` 优先级**：组内**任意**一行显式请裁 → 整个 id 视为显式
  请裁（模型主动喊"这句我吃不准"，不该被同 id 下另一个没喊的通道稀释）。
- **`edit`**：取组内**最大值**——只要有一个通道对这个 id 提出了大改动，
  这个 id 就该被优先审；取最小值会让"一个通道乱改、另一个没怎么动"的
  危险案例被没怎么动的那个通道系统性地拖低优先级，不安全。
- **`score`**（只在 `edit` 打平后做最后并列打散，**从不跨 id/跨通道当
  阈值用**）：取组内**最小值**——低分代表"这个通道自己都不确定"，用
  更谨慎的那个值，不让某通道虚报高分把整个 id 的排队优先级拉低。

已用 `test_adjudicate_priority_beats_edit_magnitude_under_quota`（独立
小夹具 `segP`：id 20 小改+显式请裁 vs id 21 大改写+未请裁，K=1）验证
"显式请裁"确实压过纯粹的改动幅度排序；用
`test_partial_channel_eligibility_blocks_whole_id_autoclear`（独立小夹具
`segM`：id 30 同时被 chX 小改、chY 大改覆盖，两通道自动清关权都开、
gates 都绿）验证"id 级 all-or-nothing"——只有一行单独达标不足以让整个
id 被自动清关摘走，两行最终仍落在同一个 bucket 里等待并排裁决。

### 2. 抽检占用 K：顺序依赖的正确展开

brief point 出这里有循环依赖的表象："抽检数取决于自动清关数，而自动
清关是从桶 2/3 前截流的"。解开循环的关键：**autoclear 资格判定的四个
条件（`edit≤limit`／gates hard 空／channel 清关权开／`channel!=amplify`）
全部只看"这一行自己的属性"，与"它将来会被排进桶 2 还是桶 3"无关**，
所以可以在排序之前就算完，真实执行顺序是：

1. 先出桶 0（locked）、桶 1（零改动）——不依赖 K/排序/autoclear。
2. 对剩余候选按 id 分组成 `pool`，**逐行**独立算 `_eligible`（不看排名）。
3. 一个 id **组内全部行都 `_eligible`** 才整体摘出、归入 `autoclear_ids`
   （逐 id all-or-nothing，见上一节）；否则留在 `pool` 正常参与排序。
4. 对 `autoclear_ids`（此时已确定、不再变化）用种子化 `random.Random`
   按 id 升序逐个抽样：抽中 → `sampled=True`，**强制**收入队列
   （`bucket=2`，不参与下一步排序，直接占位，这是"占 K"的字面含义）；
   未抽中 → `sampled=False`，`bucket=3`（不进队列）。
5. 这一步之后 `len(sampled_ids)` 已经是确定数字，`pool` 里剩下的（未被
   摘出的）id 才真正按 key 排序、取前 `K − len(sampled_ids)` 名 → 桶 2，
   其余 → 桶 3。

即"先算与排名无关的资格 → 再做 id 级摘除+抽样 → 最后才用「K 减去抽样
占用」切排序队列"——每一步只依赖"更早、且与自身无关"的信息，循环不
成立。brief 原文"bucket∈{2,3}"这半句不是要求先分出 2/3 再倒查
autoclear，而是在说"只有非 0/1 的候选才谈得上 autoclear 这件事"（0/1
桶本来就不出稿/零改动，无需这个动作），这一点在只对 `pool`（已排除
0/1）算 `_eligible` 时已经隐含满足。

### 3. `edit == 0` 与 `zh == opus` 的关系：两套归一化不能共用

- **桶 1 判据**（`_ws_equal`）只做 `.strip()`，`_n`/`_r`/ruby 原样保留
  参与比较。如果归一到 `strip_ctl()` 层级（剥控制码/ruby）再比较相等，
  "只挪了 `_n` 位置"或"改了 ruby 拼音拼写"这类**真实存在**的改动会被
  悄悄归零——这条候选从此既不产生 patch、也不出现在任何人工可见的
  地方，是不可接受的静默丢失（brief 明确警告的风险）。
- **`edit`（排序/阈值比较用的幅度）** 在 `strip_ctl()` 之后的文本上算，
  与 `polishlib.autoclear_limit()` 本身的阈值基准（同样是"剥控制码后
  的长度 × 比例"）保持同一单位。如果 `edit` 却在带控制码的原文上算，
  一次纯粹的换行方式调整会被算出很大的编辑距离，与"幅度阈值按可读
  正文字数定义"的设计初衷冲突，会把大量"内容没怎么变、只是断行方式
  变了"的候选错误地推去人工排队，稀释 K 配额。

两套分开后互不干扰：一次纯控制码变动会被 `_ws_equal` 正确识别为"有
改动"（不会被静默吞掉，能进入 `pool` 参与后续判定），但 `edit` 很可能
算出接近 0——只要 gates 绿、通道清关权开，这类候选恰好会被 autoclear
判定为"小改"而自动清关：改动没有被隐藏（触发了完整的判定流程），也
没有占用宝贵的人工审阅名额。

## queue.md 的最终形态与抽检标注的权衡

每个桶 2 的 id 一节，按 id 升序：日文原文、opus 现行译文、该 id 名下
全部通道候选（`zh` + `score` + 批注）并排列出，以及一行"进入队列原因"。

**抽检标注**：`triage.json` 的 `sampled` 字段如实记录（机器可读，供
将来 Task 10 之后统计推翻率），但 `queue.md`（人读的裁决界面）**故意
不出现"抽检"字样**。"进入队列原因"只分两档：
- **「显式请裁」**：该 id 至少一个通道候选 `adjudicate=True`。
- **「进入本轮裁决队列」**：其余全部情况——"改动幅度靠前正常排位挤进
  K 配额"与"已自动清关、抽中审计样本被塞回来"统一用这一句话，故意不
  再细分，让两者在文档里长得一模一样。

理由（brief 明确要求自己权衡）：知道某条是"已经自动清关、只是抽出来
复核一下"会实质性降低裁决者的审查强度（"既然已经过了，应该没问题"），
这恰好摧毁抽检本来要验证的东西——抽检需要裁决者用跟审别的候选**同等**
的严格程度去看，结果才有统计意义（推翻率）。已用
`test_queue_md_content_and_sample_blinding` 验证：`queue.md` 全文不出现
"抽检"/`sample`（大小写不敏感）字样，同时确认真正入队的候选（K=1 场景
下的 id 11）连带 jp/opus/候选正文都正常渲染。

## `channel_state.json` 缺失时的保守缺省

文件整体缺失、或某 channel 不在里面——一律视为该通道自动清关权关闭
（`_channel_autoclear_power()`）。已用两条测试钉死：
`test_autoclear_off_by_default_when_channel_state_missing`（文件完全
不存在）与 `test_autoclear_off_when_channel_absent_from_state_file`
（文件存在但只登记了别的通道）。

## `gates.<channel>.json` 的 str key ↔ int key（Task 6 遗留 concern 的处置）

Task 6 报告 concern 明确点出"磁盘 str key / 内存 int key"的落差，建议
"本模块或 Task 6 里加一个 `load_gates()` helper"。裁定：**放在本模块**
（`tools/polish_triage.py::load_gates()`），不回去改 `tools/polish_check.
py`——那个文件已过评审、处于 clean 状态，本模块是它目前唯一的消费方，
为一个纯读取侧的 int/str key 转换再触碰一个已完成任务的文件，风险/收益
不对等（与 Task 6 报告"speakers 的取法"一节"为什么不直接去修 polish_
setup.py"的判断逻辑一致）。

`load_gates(path)` 额外多做一件 brief 没直接要求、但设计上必须的事：
区分"文件不存在"（返回 `None`，代表"这个通道从未跑过 Task 6 的机械闸，
没有证据"）与"文件存在但是空字典"（代表"跑过、全绿"）——两者对
autoclear 资格判定的含义不同：前者必须**保守地拒绝**自动清关（没有
证据不给通过，与 `channel_state.json` 缺失的保守缺省同一哲学），后者
才真正放行。已用 `test_missing_gates_file_blocks_autoclear`（新开一个
从未跑过 `polish_check.gate()` 的通道 chC）验证。

## 变异红绿实况

命令统一：`uv run pytest tests/test_polish_triage.py -q`；每次用 Edit
改一处、跑测、记录、再用 Edit 精确还原（未使用 `git checkout`/`stash`/
`restore`）。全部四个变异都在预期的测试上真红，且都不多不少（除变异④
外没有波及其他测试）。

**变异①（brief 给定）：autoclear 无视 gates hard**（`_eligible` 去掉
`gates_hard_empty` 条件）→ `test_autoclear_requires_gate_green_and_right`
真红（`assert not True`），其余 12 条不受影响：
```
1 failed, 12 passed in 0.34s
```

**变异②（brief 给定）：配额排序丢显式请裁优先**（`_sort_key` 去掉
`adjudicate_flag` 分量）→ `test_adjudicate_priority_beats_edit_magnitude_
under_quota` 真红（`assert 3 == 2`，id 20 被挤到桶 3），其余 12 条不受
影响：
```
1 failed, 12 passed in 0.11s
```

**变异③（brief 给定）：抽样用系统随机而非种子化 Random**（`rng.random()`
→ 全局 `random.random()`）→ `test_sampling_never_touches_global_random`
真红（monkeypatch 炸出 `AssertionError`，堆栈精确定位到 `polish_triage.
py` 里那一行）：
```
1 failed, 12 passed in 0.30s
```
**附带验证**：brief 给的 `test_deterministic_sampling`（两次调用逐字段
相等）在这个变异下**没有可靠地转红**——该测试用的夹具只有 1 个自动
清关候选（id 14），两次独立的未播种 `[0,1)` 抽样落在 `sample_rate=0.10`
阈值两侧、从而让两次结果不一致的概率只有约 `2×0.10×0.90=18%`。同一
变异下重跑这条测试 5 次，5 次都通过（见下方命令输出），证实它作为
唯一把关手段并不可靠（这正是本项目"绿变异要区分测试无牙还是变异没
打中"的纪律要求本身）——`test_sampling_never_touches_global_random`
（monkeypatch 全局 `random.random` 让其一炸就抛）把同一件事变成 100%
确定性的检验，是本任务在 brief 给定测试之外补的关键一条：
```
$ for i in 1 2 3 4 5; do uv run pytest tests/test_polish_triage.py::test_deterministic_sampling -q; done
1 passed in 0.04s   （×5，变异③下全部通过——不可靠）
```

**变异④（本任务按指令额外要求的一个）：`channel_state.json` 缺失时
默认开启自动清关**（`_channel_autoclear_power` 的缺省值 `False`→`True`）
→ 两条专门测试真红，外加一条连带转红（`test_adjudicate_priority_beats_
edit_magnitude_under_quota` 所在的 `segP` 夹具没调用 `enable_autoclear`，
翻转缺省后 id 20 意外变成"autoclear 资格达标"，改变了桶 2/3 分配，属于
预期内的连带效应，不是测试设计缺陷）：
```
3 failed, 10 passed in 0.10s
FAILED test_autoclear_off_by_default_when_channel_state_missing
FAILED test_autoclear_off_when_channel_absent_from_state_file
FAILED test_adjudicate_priority_beats_edit_magnitude_under_quota（连带）
```

四个变异全部按预期真红，均已用 Edit 精确还原（未使用 git 相关的破坏性
命令）；每次还原后单独跑 `tests/test_polish_triage.py` 确认恢复到
13 passed，最终跑一次全量确认 650 passed（见下方"测试输出"）。

## 与 brief 的一切偏差

1. **`triage(label) -> dict` 的具体形状**：brief 只给了返回类型
   `dict`，没给字段名；结合"每候选一条"的描述与测试里必须能按 id/
   channel 检索单行（`by_id()` 助手，brief 没给实现，本任务自己写）
   这两点，选择 `{"rows": [...], "queue_ids": [...]}`——`rows` 是列表
   （每候选一条，与 brief 描述字面一致），`queue_ids` 是额外补充字段
   （桶 2 的 id 排序去重列表，方便 `queue.md` 渲染与未来 Task 8/10
   直接复用，不强制但无害）。
2. **随机种子的 key**：brief 写 `manifest["files"]["source.jsonl"]`；
   实测（临时仓库跑一遍 `polish_setup.setup()`，见下方"实测证据"）
   `manifest.json` 的 `files` 字典 key 是**相对 SEG 目录**的路径
   `"frozen/source.jsonl"`，不带前缀的 `"source.jsonl"` 在真实
   manifest 里不存在，按 brief 字面实现会在真实 SEG 上直接
   `KeyError`。已按实测结果改用 `"frozen/source.jsonl"`。
3. **CLI 加 `--repo`**：与 Task 3/4/5/6 同一先例，测试基础设施要求，
   不改变省略该参数时的默认行为。
4. **`load_gates()` helper 放在本模块**（brief 补充信息允许"本模块或
   Task 6 里"二选一）：不改动已过评审、处于 clean 状态的 `tools/
   polish_check.py`，理由见上方专节。
5. 变异④是"额外要求"而非 brief 原文的一部分，已按指令要求补上并验证。

## 实测证据（manifest.json 的 files key 形态）

用临时仓库跑一遍 `polish_setup.setup()`（未落任何东西进真实仓库，只在
系统临时目录）：
```python
manifest["files"].keys() 的前 5 个：
['frozen/glossary/active.json', 'frozen/glossary/anchors.yaml',
 'frozen/glossary/polish.md', 'frozen/glossary/speakers.json',
 'frozen/glossary/style.md']
筛 "source.jsonl" 结尾的 key：['frozen/source.jsonl']
```
（源自 `tools/polish_setup.py` 第 165-168 行：`files[p.relative_to(d)
.as_posix()] = sha256_file(p)`，其中 `d` 是 `pilot/polish/<label>/`
本身，`p` 遍历 `d / "frozen"` 子树——故 key 必然带 `frozen/` 前缀。）

## 测试输出

```
uv run pytest tests/test_polish_triage.py -q
.............                                                            [100%]
13 passed in 0.33s

uv run pytest -q
650 passed in 3.31s      # 637（本任务开始前基线）+ 13（本任务新增）
```

## Concerns（供后续任务参考，非阻塞）

- **Task 8（`polish_commit.py`）的消费假设已核实一致**：计划文本第 442
  行写"②triage 里 `autoclear and not sampled` 的候选"直接自动清关——
  本模块的字段语义（`autoclear=True` 且 `sampled=False` 才是"真正自动
  提交、不需要人看"；`sampled=True` 即使 `autoclear=True` 也仍然
  `bucket=2` 进队列）与这条消费假设完全对齐，Task 8 不需要额外读
  `bucket` 字段来判断是否自动清关，只需要 `autoclear and not sampled`
  这一个组合条件。
- `bucket` 字段对"已自动清关但未被抽中"的行取值为 3（"记录在案，不进
  队列"）——这是本任务的选择而非 brief 明文规定（brief 的四桶语义表
  里桶 3 的措辞是"保留 opus"，与 autoclear 实际会写入润色稿这件事字面
  上不完全贴合）。选择 3 而不是发明一个新桶号的理由：`bucket` 字段
  在本模块的定位始终是"是否需要人工排队"这一件事，`autoclear` 才是
  真正决定下游动作的字段；Task 8 消费时明确只看 `autoclear`+`sampled`
  组合（见上一条），不依赖 `bucket` 的具体数值语义，所以这里的选择
  只影响审计可读性，不影响任何下游判定的正确性。若后续任务发现需要
  更精细的区分，建议在 `bucket` 之外新增一个独立的 disposition 字段，
  而不是重新定义 `bucket` 的取值范围（那会牵连 `queue_ids`/`queue.md`
  的现有实现）。
