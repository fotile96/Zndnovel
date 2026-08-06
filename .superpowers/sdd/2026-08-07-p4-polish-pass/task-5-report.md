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
