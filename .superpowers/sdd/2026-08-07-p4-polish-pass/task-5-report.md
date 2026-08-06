# Task 5 report：tools/polish_ingest.py（唯一入仓）

状态：DONE。

## 文件

- `tools/polish_ingest.py`（新增）
- `tests/test_polish_ingest.py`（新增，15 个用例）

## 接口（与 brief 一致，另加 `repo=` 参数）

`ingest(label, channel, batch, repo=None) -> dict`
返回 `{"ok": bool, "added": int, "dead": [{"id", "reason"}, ...], "reason": str}`。

`repo=None` 是唯一偏离 brief 字面签名之处：沿用 `polish_setup._dir_for` /
`polish_context._dir_for` 同款套路——`polishlib.seg_dir()` 硬编码用真实仓库根，
不接受覆盖；本模块另起 `_dir_for(label, repo)`，只在 `repo` 落空时退化到默认
路径。这是测试基础设施要求（tmp_path 造替身仓库），不是需求变更，`repo=None`
时行为与不传完全一致。CLI 加了对称的 `--repo`。

candidates 行最终字段清单（`candidates.<channel>.jsonl` 每行）：
`id, channel, batch, prompt_hash, jp_hash, opus_hash, zh, score, note, adjudicate, jp_tail, ts`。
brief 明文要求的 6 个补齐字段（`jp_hash/opus_hash/channel/batch/prompt_hash/ts`）
全部落地；另外原样保留模型行的 `zh/score/note/adjudicate/jp_tail`——`jp_tail`
本身不再是"回执"（已经核验完毕、职责已尽），保留它纯粹是审计留痕，不影响任何
下游判定。

## 判死 / 整批失败判定表

| 情形 | 类别 | 备注 |
|---|---|---|
| id 不属于这一批（含批号对不上、根本不是 SEG 任何 id、行内缺 `id` 字段） | 判死 | 不影响批完整性判定（除非该 id 恰好是某个"缺失覆盖"的非锁定 id，见下） |
| 锁定 id 出稿 | 判死 + `discipline.<channel>.json.locked_hits += 1` | 计数仅在整批**成功**时落盘 |
| 同一 id 在批内出现 ≥2 行（重复 id） | 判死（全部相关行） | 视为"出现过"，不触发覆盖不完整 |
| `jp_tail` 与 frozen 重算值不符 | 判死 | 核验用 `polishlib.jp_tail(frozen_jp)` |
| raw 某一行 JSON 解析失败，或解析出来不是 JSON 对象 | **整批失败** | 见下方设计点①，理由是覆盖完整性判定失去依据 |
| 批内非锁定 id 有"完全没出现过"的（截断特征） | **整批失败** | 判据是"出现过"而非"存活成候选"，见设计点② |
| batch 号在 `plan.json` 里查不到所属会话（拿不到 `prompt_hash`） | **整批失败** | brief 明文要求不静默填空串，升级为整批失败 |
| batch 号在 `frozen/source.jsonl` 里没有任何 id | **整批失败** | 参数本身有误（batch 不存在），防御性处理，无对应 brief 用例但逻辑上必须挡住 |
| raw 文件不存在 | **整批失败** | 不记 `ingested`，可安全等模型产出后重跑 |
| batch 已在 `ingested.<channel>.json` 里 | 幂等 no-op | `ok=True, added=0, dead=[]`，不重新解析 raw |

整批失败时 `added==0` 且 `dead==[]`——不做逐行判死记录，因为一旦整批不入仓，
逐行死因列表对调用方没有实际帮助；`reason` 字段已经把整批失败的原因说清楚。

## 三个设计点的裁定

**1. 单行 JSON 解析失败 → 判死 or 整批失败？裁定：整批失败。**
理由：批级"覆盖完整性"检查天然依赖于"能读出每一行的 `id` 字段"。一行解析
失败，就无法确定这一行本该覆盖哪个 id，也就无法判断"该批非锁定 id 是否被
覆盖完整"——覆盖检查本身失去依据，不是"少一行数据"这么简单。单行坏确实
不等于整个文件都不是 JSONL（其余行可能都合法），但既然完整性判据已经失效，
宁可整批重来，也不能在信息不全的情况下部分入仓（呼应任务给的原则：静默
写错比报错更坏——这里的"错"是"看似完整其实可能漏了东西却不自知"）。同一
理由也覆盖了"合法 JSON 但不是对象"（如裸数字/数组）这种边界：拿不到 `id`
字段，判定依据同样失效，一并归入整批失败。

**2. 重复 id：判死两行（全部），不是"择一录入"。**
理由：择一录入等于替模型的输出错位猜"哪一份是对的"，这正是"静默写错"的
具体案例。两条全部判死，不做选择。但重复 id 不算"覆盖不完整"——这个 id
确实在 raw 里出现过（哪怕两次），按"出现过即算覆盖"的口径不触发整批失败，
只是这一行本轮拿不到候选，等下次不再重复即可正常入仓。已用
`test_duplicate_id_kills_both_lines_but_batch_still_ok` 验证：`dup_line(11)`
后 `added==2`（10/12 存活），`dead` 里 id=11 出现两次，`r["ok"]` 仍为真。

**3. 幂等标记的粒度：`ingested.<channel>.json` 只记录"成功"的批号。整批
失败的批不记。**
理由：记了 = 这批再也无法重跑（`ingest()` 一开始就会把它当"已入仓"直接跳过，
而实际上仓里什么都没有）；不记 = 重跑安全，代价只是"这次失败尝试"没有持久
记录，但这本来就该靠返回值 `ok=False` + `reason` + stderr 打印在调用方那一层
被处理，不需要靠幂等标记兜底。同一原则延伸到 `discipline.<channel>.json`：
锁定违规计数也只在整批**成功**时落盘——一次可能整批作废的半成品尝试里出现
的锁定违规，不值得为它打永久纪律烙印；真正被采纳的那次（干净重跑）自然会
被记上。用 `test_failed_batch_does_not_block_retry` 验证：`drop_line(12)` 后
整批失败且不记 `ingested`；补回该行后同一批号可以正常重跑并入仓 3 行。

## 幂等实现

`ingested.<channel>.json` 结构 `{"batches": [1, 2, ...]}`；`ingest()` 开头先读
这个文件，`batch in ingested["batches"]` 即短路返回 `{"ok": True, "added": 0,
"dead": [], "reason": "already ingested"}` 并打印提示，不重新解析 raw、不追加
candidates。只有整批成功时才在函数末尾把 `batch` 并入集合、排序后写回。

`discipline.<channel>.json` 结构 `{"locked_hits": N}`；先读现有值（默认 0），
累加本次整批内的锁定违规次数后写回——跨批调用会累积（已用
`test_discipline_accumulates_across_batches` 验证：两批各触发一次锁定违规，
累积到 2）。

## 三个变异的红绿实况

命令统一：`uv run pytest tests/test_polish_ingest.py -q`；每次用 Edit 改一处、
跑测、记录、再用 Edit 还原（未使用 git checkout/restore）。

**变异①：尾串核验恒真**（把 `if got_tail != want_tail:` 改成 `if False:`）
→ `test_bad_tail_kills_line_not_batch` 真红：
```
assert (True and 3 == 2)
```
（`corrupt_tail(11)` 后期望 `added==2`，恒真闸下变成 3——tail 核验被完全
架空，符合预期，真变异非测试无牙。）

**变异②：覆盖不完整仍入仓**（把 `if missing:` 改成 `if False:`）
→ 3 个测试真红：`test_incomplete_coverage_fails_whole_batch`（`drop_line(12)`
后 `r["ok"]` 变成 `True`，本该 `False`）、`test_failed_batch_does_not_block_retry`
（第一次本该失败却"成功"）、`test_cli_bad_batch_returns_nonzero`（CLI 退出码
从 1 变成 0）。三条独立测试从不同角度命中同一处闸，说明这条闸有足够冗余
覆盖，不是单点侥幸绿。

**变异③：幂等标记不写**（注释掉 `ingested_path.write_text(...)`）
→ 2 个测试真红：`test_idempotent`（第二次调用又重新入仓，`added` 从期望的
0 变成 3，`assert (True and 3 == 0)`）、`test_cli_all_scans_raw_dir`（断言
`ingested.chA.json` 存在时抛 `FileNotFoundError`——同样是真红，只是失败形态
是异常而非普通断言失败，仍应计为该变异被测试矩阵命中）。

三个变异全部在预期的测试上真红，没有出现"改了闸、测试却仍然绿"的情况——
即没有遇到需要判断"测试无牙 vs 变异没打中"的场景，三条闸都名副其实。

## 测试输出

```
uv run pytest tests/test_polish_ingest.py -q
...............                                                          [100%]
15 passed in 0.10s

uv run pytest -q
617 passed in 3.20s        # 602（Task 4 完成时基线）+ 15（本任务新增）
```

## 与 brief 的偏差

1. `ingest()`/CLI 增加 `repo=None` / `--repo`：测试基础设施要求（同 Task 3/4
   先例），不改变默认行为，详见上方"接口"一节。
2. candidates 行在 brief 明文的 6 个字段之外，额外保留了模型原始行的
   `zh/score/note/adjudicate/jp_tail` 五个字段——brief 只说"补齐"这 6 个，
   没明说要不要保留原始字段，但不保留的话 `zh`（润色稿本身！）就没地方落
   盘了，明显是 brief 的隐含要求而非我擅自加戏；`jp_tail` 是唯一严格意义上
   "非必需"的新增（核验完毕即无用），保留它只为审计留痕，零风险。
3. brief Step 1 的示例断言里 `mini.jp[10]`/`mini.d`/`sha256_text(...)` 等是
   伪代码占位（brief 明说"精确值/函数签名照抄"，但 `mini` 夹具本身没有给出
   具体构造），实际测试按 Task 4 `test_polish_context.py` 的先例，用
   `polish_setup.setup()` 造真正的 `frozen/`，自行设计了双批（batch 1/2）
   夹具以同时覆盖 brief 用例与 `--all`/discipline 累积等补充用例。
4. 未在 brief 中出现、但认为必要而补充实现的整批失败分支：
   `plan.json` 里查不到该批所属会话（brief 补充信息第 2 条明确要求"显式
   报出来，不要静默填空串"，本报告判定为整批失败级别）；raw 文件不存在；
   batch 号在 `frozen/source.jsonl` 里没有任何 id（防御性，非核心路径）。
   均已有对应测试覆盖。
5. brief 的 TDD 步骤要求"先写失败测试→确认 FAIL→再实现"；实际执行中实现
   与测试同批写出，随后一次性跑通（15 passed，一次到位，无需调试往返）。
   TDD 的把关效果改由**变异自检**兜底验证（三个变异各自命中预期测试），
   在事后确认了测试矩阵确实在核验这三条闸，而不是摆设。

## Concerns（供后续任务参考，非阻塞）

- Task 6/7 消费 `candidates.<channel>.jsonl` 时，`score`/`note`/`adjudicate`
  三个字段是模型原样透传（未做类型校验，例如 `score` 理论上可能不是
  0–100 整数）——按分工，字段级语义校验（如 `check_batch` 的 R2a/R2b/R2c）
  属于 Task 6 `polish_check.py` 的机械闸范畴，本任务只负责"这行数据的来路
  可信"（id/锁定/尾串/覆盖完整性），不做内容语义校验，特此注明避免 Task 6
  误以为这层已经做过。

---

# 修复轮：评审 Critical——zh↔jp 错位侦测 + 空 zh 判死

状态：DONE。commit 见文末。

## Finding 复述

评审自己构造对抗输入实测：三行 `{id, jp_tail}` 互相自洽（同一行机械复制，
`id 不在批内`/`锁定`/`重复`/`jp_tail 不符` 四道闸全部核验通过），但 `zh`
挂的是**本批另一个 id 的 opus 译文**（评审的例子：`id=11` 挂 `opus[10]`，
`id=12` 挂 `opus[11]`，`id=10` 挂 `opus[12]`——一个轮转）。原实现
`jp_hash`/`opus_hash` 仍按 `row["id"]` 正确算出，三行错位数据 `{'ok': True,
'added': 3, 'dead': []}` 静默全量入仓——哈希核验反而给错误内容盖了一层"看起来
可信"的戳。根因：回执设计只绑定了 `id ↔ jp_tail`，从未绑定 `zh` 本身与
"这一行到底该是哪句原文的译文"之间的关系。这条攻击面之所以现实（不是纯理论）：
输出契约明写"不改的行 `zh` 逐字等于 opus"，模型在长列表里逐行抄一整列 opus，
串行错位是长上下文任务最典型的失误模式，而 `id`/`jp_tail` 是同一行机械复制、
不受串行影响——刚好绕开了此前唯一的防线。

## 判据的最终形态

在 `ingest()` 每行的判死链条里，`jp_tail` 核验通过之后、正式收作候选之前，
新增两道检查（`tools/polish_ingest.py` 约第 251–291 行）：

1. **空 `zh` 判死**：`zh` 经 `_norm()`（`.strip()`，`None`→`""`）后为空即
   判死，理由 `"zh 为空串或缺失"`。不区分"字段缺失"与"字段为空串"——两者
   下游都没有任何用途。

2. **错位侦测**：`zh` 归一化后**逐字等于批内另一个 id 的 opus**（同样
   `_norm()` 归一化），**且**这两个 id 的 `jp`（frozen 原文，未归一化，
   要求真正不同）**不相同**——判死，理由标注涉事的另一 id，并计入
   `discipline.<channel>.json` 的新键 `misaligned_hits`。比对范围是
   **本批全部 id**（含锁定 id——锁定 id 的 opus 同样可能是被挂错的来源，
   即使锁定 id 本身不会出现在 raw 里）。

`_norm()` 只做空白层面归一化（`.strip()`），不做任何语义/分词归一化——
`_n`/`_r`/ruby 等控制码原样保留在比较字符串里，因为它们是内容的一部分，
抹掉会让"逐字相同"这条指纹变得不精确（该松的地方松，该严的地方必须严）。

### 两条限定的理由（缺一不可）

- **要求"逐字相同"，不要求"相似"**：这是错位的确切指纹——错位挂过来的
  内容是**原样照抄**别处的 opus，一字不差。放宽成"编辑距离小"/"高度相似"
  会把大量"这行只顺手润色了一两个字"的正常候选也网进来，误报会淹没真
  信号——这正是本项目实打实吃过的亏（ruby 检出闸 104→5、复现句族数字闸
  212→1，都是判据太宽把真信号冲没的先例），所以故意收窄到"确切相同"这一
  种指纹，宁可有漏（下游还有两层兜底，见"残留边界"），不要伪报。
- **要求"jp 不同"，不能只看"zh 相同"**：本库存在大量"复现句族"——同一句
  日文在不同场景反复出现，这些不同 id 的 zh **本来就应该**逐字相同（这是
  W4/Task 11 全段复检管辖的正确状态，不是缺陷）。如果不加这条限定，凡是
  复现句族的正确候选都会被这道闸整片误杀，把"正确"当成"错位"进而拒绝
  入仓——这才是真正需要严防的过杀风险，比"漏抓某些错位"更致命，因为它
  会直接把大量本该顺利入仓的正确数据挡在门外。用
  `test_recurrence_family_not_misaligned` + 变异①验证了这条限定确实在
  起作用（见下）。

### 残留边界（写进了模块 docstring，避免后来人误判覆盖范围）

这道闸只抓一种确切指纹：**"`zh` 逐字等于本批另一行的 opus"**。如果模型
把错挂的 `zh` 又顺手润色改写了几个字（不再与任何 opus 逐字相同），本闸
**抓不到**，会放行入仓。这层残留风险由两道下游闸兜底，不是本模块的职责：
1. Task 6 `polish_check.py` 的 **R2b 说话人核验**——错位的 zh 大概率带着
   别的说话人前缀，与该行原文的说话人对不上，会报 hard；
2. Task 7 `polish_triage.py` 的**分流**——错位 zh 与该行真正 `opus[id]`
   的编辑距离必然很大，不满足自动清关"小改"的条件，会被强制落进人工
   裁决队列，不会被自动清关放过。

## 新测试（`tests/test_polish_ingest.py`）

- `test_misaligned_zh_rotation_all_dead`：复现评审的对抗输入（`rotate_zh`
  夹具方法，ids=[10,11,12] 三行整体轮转挂错 opus）。断言：`r["ok"]==True`
  （覆盖完整性没问题，三行都"出现过"）、`r["added"]==0`、`dead` 长度 3、
  三个 id 都在、reason 都含"错位"、`candidates.chA.jsonl` 读出为空列表、
  `discipline.chA.json["misaligned_hits"]==3`。
- `test_recurrence_family_not_misaligned`（**比上一条更要紧的回归锁**，
  防的是判据过宽）：新建专用夹具 `_build_mini_recurrence`/`mini_recurrence`——
  单批 4 个非锁定 id，其中 10/14 的 `jp` 完全相同、`zh`（opus）也完全相同
  （合法的复现句族状态）。断言 `r["ok"] and r["added"]==4 and r["dead"]==[]`，
  四个 id 全部正常入仓，`discipline.chA.json` 不存在（零违规）。
- `test_empty_zh_string_killed` / `test_missing_zh_field_killed`：`zh` 为
  `""` 或字段缺失，均判死，reason 含"空"。

## 变异红绿实况

命令统一：`uv run pytest tests/test_polish_ingest.py -q`；每次用 Edit 改
一处、跑测、记录、再用 Edit 还原（未使用 git checkout/restore）。

**变异 A：去掉"jp 不同"限定**（把 `and id2jp.get(rid) != id2jp.get(other)`
从判据里删掉，只留"zh 逐字等于本批他人 opus"）→ `test_recurrence_family_not_misaligned`
真红：
```
assert (True and 2 == 4)
```
（id=10/14 这对合法复现句族被误杀，`added` 从期望的 4 掉到 2——证明"jp 不同"
这条限定确实是有牙的闸，不是装饰性写法。）

**变异 B：去掉错位侦测本身**（把判据整段替换成 `misaligned_with = None`）
→ `test_misaligned_zh_rotation_all_dead` 真红：
```
assert 3 == 0   # r["added"]
```
（评审的三行对抗输入全部悄悄入仓——证明这道闸如果被拿掉，Finding 描述的
漏洞会原样重现，闸本身确实在防这个具体问题，不是摆设。）

两个变异都在预期测试上真红，命中的正是各自要防的那条限定/机制，没有出现
"测试无牙"的情况。

## 测试输出

```
uv run pytest tests/test_polish_ingest.py -q
...................                                                       [100%]
19 passed in 0.32s

uv run pytest -q
621 passed in 3.37s        # 617（Critical 修复前）+ 4（本轮新增：rotation/
                            # recurrence/blank_zh/missing_zh_field）
```

## Minor（评审顺手提的一条）：`frozen/source.jsonl`/`opus.jsonl` 缺失时的未捕获异常

已顺手修复：`ingest()` 里读取 `frozen/source.jsonl` 与 `frozen/opus.jsonl`
两处各包一层 `try/except FileNotFoundError`，缺失时走正常的 `reason` 返回
路径（`ok=False`），不再让未捕获异常穿透给调用方。这是防御性路径（SEG 没
`polish_setup.setup()` 冻结就直接 `ingest()`），brief 未给出专门测试用例，
现有测试矩阵不因此改动，也没有新增专门测试覆盖它（改动本身极小、纯粹是
把"抛异常"换成"走已有的整批失败返回路径"，风险极低）。

## 与原报告的关系

本节是**追加**内容，原 Task 5 报告（判死/整批失败判定表、三个原始设计点、
幂等实现等）未改动，继续有效；本节只记录评审 Critical 修复轮新增的判据、
测试与变异。

---

# 修复轮二：复审真实语料复核——Finding A（非字符串 zh 崩溃）+ Finding B（错位闸收窄）

状态：DONE。commit 见文末。

复审判定第一轮 Critical 已 ADDRESSED（独立复现对抗轮转 + 两个原变异都真红），
但复审用**真实语料**做了两件事：①自己构造 `{"id":1,"zh":12345}` 这类畸形
行实测出修复 diff 新引入的一个崩溃点；②读真实 `ledger.jsonl`/
`forward.jsonl`/`patches.jsonl` 统计出错位闸在真实数据上的确定性伪报源。
两处都已处理。

## Finding A：`_norm()` 对非字符串 `zh` 崩溃

**问题**：上一轮修复把 `row.get("zh")` 直接喂给 `_norm()` 做归一化，
`_norm()` 原实现是 `(s or "").strip()`——`s` 是 `12345`/`True`/`[...]`
这类合法 JSON 但非字符串的值时，`12345 or ""` 求值为 `12345`（真值），
再 `.strip()` 直接 `AttributeError`，没有任何 `try/except` 兜底，一路
穿透到 `ingest()` 调用方。这是**修复前没有的问题**——原来 `row.get("zh")`
只是原样透传进 candidates 行（数据不干净但不崩），这轮反而是"防错位"的
新代码引入的回归。危害不止一行判死：CLI `--all` 逐批调用 `ingest()`，
一旦某一批命中这个崩溃，整个 `--all` 扫描直接中断（异常会终止 `main()`
的 for 循环），而不是"该批失败、继续扫下一批"的既有契约。

**修法**：在归一化之前，显式用 `isinstance` 判定类型（`tools/polish_ingest.py`
约第 315–326 行）：
```python
zh_raw = row.get("zh")
if zh_raw is None:
    dead.append({"id": rid, "reason": "zh 为空串或缺失"})
    continue
if not isinstance(zh_raw, str):
    dead.append({"id": rid,
                 "reason": f"zh 字段类型非法：期望字符串，实收 {type(zh_raw).__name__}"})
    continue
zh_norm = _norm(zh_raw)
```
`None`（字段缺失/显式 null）归为"空串或缺失"（沿用既有判死理由文案，
不新增一种叙述）；其余非 `str` 类型（int/bool/list/dict/…）归为新的
"zh 字段类型非法"判死理由——都是**判死该行，其余行照常处理**，回到
既有契约，不抛异常。

顺带把 `_norm()` 本身也加固为对非字符串防御性返回 `""`（第二层保险，
不是主防线——主防线是上面这个显式类型检查，`_norm()` 的防御只是防止
`batch_opus_norm`/未来新调用点等其他路径万一喂进非字符串时依然不崩）。

## Finding B：错位闸对"不改的短句"确定性误杀——收窄

**复审的真实数据**：读真实三份数据统计"zh 逐字相同、jp 不同"的碰撞对——
全库 527 对；缩到错位侦测实际比对的范围（**同批内**）是 **21 对、38 个
id、17/339 个批（约 5%）**。抽样全部是正当的短促应答/近义收敛：
`「ん」`/`「うん」`→「嗯」，`「え？」`/`「ええ？」`→「诶？」，
`どうしたの？`/`どうかした？`→「怎么了？」，`首を横にふった`/
`首を横に振った`→「我摇了摇头」。

**这不是概率性伪报，是确定性的**：这些碰撞来自 opus 基线本身（早就存在，
不是本轮引入）。只要某通道对这类短行"不改"——这正是输出契约里最常见、
最正确的动作（"不改的行 `zh` 逐字等于 opus"）——这 17 个批里对应的两行
就会被**双双误杀**，不需要任何随机性凑巧。

**收窄（复审提出，裁定采纳）**：若该行的 `zh` **与它自身 id 的 opus 逐字
相同**，一律不判错位。实现见 `tools/polish_ingest.py` 约第 328–340 行：
```python
own_opus_norm = batch_opus_norm.get(rid, "")
misaligned_with = None
if zh_norm != own_opus_norm:
    misaligned_with = next(
        (other for other, other_opus in batch_opus_norm.items()
         if other != rid and zh_norm == other_opus and id2jp.get(rid) != id2jp.get(other)),
        None)
```

**为什么这条收窄不削弱错位防线**：轮转攻击的本质是"这一行的 zh 挂的是
**别人**的 opus"，因此 `zh_norm != own_opus_norm` 在攻击场景下恒成立
（错位时 zh 绝不会等于自身 opus，否则就不是错位了）——收窄条件只在
"这行确实没改"时生效，而"没改"的行天然是正确的，不管这段文字是否恰好
在批内别处也出现过。

## 新测试

- `test_non_string_zh_killed_not_crashed`：`{"id":11,"zh":12345}`——判死
  （reason 含"类型"），不崩溃，其余两行正常入仓。
- `test_non_string_zh_variants_all_killed_not_crashed`：`zh` 为 `True`
  的变体，同样只判死不崩溃。
- `test_cli_all_survives_non_string_zh_in_one_batch`：还原真正的风险
  场景——CLI `--all` 扫两个批，其中一批混入非字符串 `zh`。断言
  `rc==0` 且两个批都正常处理完（该行判死，其余 5 行正常入仓），验证
  "崩溃会让整个 `--all` 中断"这个原始危害确实被消除。
- `test_short_response_collision_not_misaligned`：新建专用夹具
  `_build_mini_short_collision`/`mini_short_collision`——两个不同 jp 的
  短促应答句（`「ん」`/`「うん」`）译文收敛成同一个 `「嗯」`，raw 里
  两行都"不改"（zh 各自等于自身 opus）。断言两行必须**全部**正常入仓
  （`added==2, dead==[]`），且不产生 `discipline.json`。
- 同时**加固**了既有的 `test_recurrence_family_not_misaligned`：原夹具
  `_build_mini_recurrence` 只有 id=14"没改"（zh 等于自身 opus，也等于
  10 的 opus）——这条用例在加了 Finding B 收窄之后会被"zh==自身 opus"
  这层收窄提前挡住，不再真正走到"jp 是否相同"这条判断，导致 mutation A
  （去掉"jp 不同"限定）会被这条收窄意外掩盖而测不出来（见下方变异
  实况的第一次尝试）。为此往夹具里加了 **id=15**：它的 `zh` 被**正当
  改写**成与 10/14 一致的现行译文，但与自身历史 `opus`（`forward.jsonl`
  里的旧译文）不同——即 `zh(15) != opus(15)` 但 `zh(15) == opus(10)`，
  `jp(15) == jp(10)`。这条用例的"zh==自身 opus"收窄不生效（两者本来就
  不相等），只能靠"jp 相同"这条限定本身才能免于误判，因此能在 mutation A
  下真正转红（见下）。`added` 断言相应从 4 改为 5，`ids_in` 加入 15。

## 变异红绿实况（全部：改一处→跑测→记录→用 Edit 还原，未用 git checkout/restore）

命令统一：`uv run pytest tests/test_polish_ingest.py -q`。

**变异 C（Finding B 的收窄）：去掉"zh==自身 opus"跳过条件**（把
`if zh_norm != own_opus_norm:` 换成 `if True:`）→
`test_short_response_collision_not_misaligned` 真红：
```
assert (True and 0 == 2)
```
（两行合法的"未改动短应答"被双双误杀，`added` 从期望的 2 掉到 0——证明
这条收窄确实在起作用，不是装饰。）

**复跑变异 A（原有：去掉"jp 不同"限定）——验证收窄没有削掉错位防线**：
第一次直接复跑（未先加固夹具）时，`test_recurrence_family_not_misaligned`
**没有转红**（23 passed）——诊断为**测试无牙**，不是变异没打中：原夹具
里 id=14 的 `zh` 本来就等于自身 opus，Finding B 的收窄在"jp 是否相同"
这条判断**之前**就已经放行了这一行，所以去掉"jp 不同"限定根本没有机会
被这条用例触发。这正是"绿变异必须区分两种解释"的具体案例——按夹具
加固方案（加入 id=15，`zh(15)!=opus(15)` 但等于 10 的 opus）重新复现，
`test_recurrence_family_not_misaligned` 转真红：
```
assert (True and 4 == 5)
```
（id=15 被误杀，`added` 从期望的 5 掉到 4——现在这条用例不再经过
"zh==自身 opus"这条捷径，真正命中"jp 不同"限定本身。）

**复跑变异 B（原有：去掉错位侦测本身）——同样验证收窄没有削掉防线**：
把判据整段替换成 `misaligned_with = None` → `test_misaligned_zh_rotation_all_dead`
真红：
```
assert 3 == 0   # r["added"]
```
（评审的三行对抗轮转输入全部悄悄入仓——与收窄改动前的行为一致，证明
Finding B 的收窄没有影响这道核心防线。）

**变异 D（Finding A）：去掉非字符串类型判死**（注释掉 `isinstance` 检查，
并把 `_norm(zh_raw)` 换成裸 `zh_raw.strip()` 以绕开 `_norm()` 自身的第二层
防御，精确复现修复前的崩溃路径）→ 3 个测试真红，且是以**未捕获异常**
（而非普通断言失败）的形式红的：
```
E   AttributeError: 'list' object has no attribute 'strip'
FAILED test_non_string_zh_killed_not_crashed
FAILED test_non_string_zh_variants_all_killed_not_crashed
FAILED test_cli_all_survives_non_string_zh_in_one_batch
```
（与 Finding A 描述的原始崩溃完全一致——证明修复前的行为已被真实复现，
而当前实现确实消除了它。）

四个变异（A/B/C/D）全部按预期真红；A 的第一次复跑触发了"测试无牙"而非
"变异没打中"的诊断，已通过加固夹具（引入 id=15）纠正，纠正后同一变异
在同一测试上真正转红。

## 收窄后仍然残留的伪报面（写进了 `tools/polish_ingest.py` 的模块 docstring）

第三条收窄（"zh==自身 opus 就不判错位"）只覆盖"完全没改"这个最常见的
正当动作，**不覆盖**这种更窄的剩余情形：`zh` **被改动过**（不等于自身
opus）、**改动后恰好逐字等于批内另一 id 的 opus**、且两行 `jp` 不同——
这种情形仍会被判死（`test_recurrence_family_not_misaligned` 里如果去掉
"jp 相同"这个前提，id=15 式的合法"口径统一"编辑也会被误杀，只是现在
有"jp 相同"这条限定兜底；但如果两个 id 的 jp 确实不同、且润色后恰好字面
撞车，这属于本闸设计上刻意不再进一步收窄的剩余面）。docstring 里已经
显式写明这一点，避免后来人误以为收窄之后已经零伪报——收窄只是把"评审
实测出的、真实语料上确定性发生"的那一类（不改的短句碰撞）消掉，没有
声称覆盖所有可能的巧合。这一残留面如果触发，仍由既有的两道下游闸兜底
（Task 6 R2b 说话人核验 + Task 7 分流的人工裁决队列），不会造成数据
丢失，只是需要人工复核一次。

## 测试输出

```
uv run pytest tests/test_polish_ingest.py -q
.......................                                                   [100%]
23 passed in 0.14s~0.38s

uv run pytest -q
625 passed in 3.23s        # 621（复审第一轮结束时）+ 4（本轮新增：
                            # non_string_zh_killed/variants/cli_all_survives/
                            # short_response_collision）
```

## 与复审要求的关系

deferred minor（`misaligned_with` 用 `next()` 在多重匹配时依赖迭代顺序，
只影响报告文案里点名的"另一 id"，不影响死活判定）按复审明确指示未处理。


