# Task 10 报告：tools/polish_calibrate.py（通道准入小考）

## 产出

- `tools/polish_calibrate.py`（新增）：`make()` / `score()` / CLI（`--make` / `--score`）。
- `tests/test_polish_calibrate.py`（新增）：11 个测试，含 4 个变异自检点（对应 brief 要求的 2 个 + 用户追加的 2 个）。
- 基线 682 passed → 693 passed（682 + 本模块新增 11 个），无回归。

## 1. 金标池取法与 resolve 的处理

`_gold_pool(repo)` 读 `repo/pilot/lanes/opus/data/{ledger,forward,patches}.jsonl`：

1. `gold_ids = {r["id"] for r in patches if r["reason"] in ("review","recall")}`——只用 reason 筛"这个 id 曾被人裁过"这件事本身，不直接使用该行的 `zh`。
2. 现行文本一律用 `tools.resolve.resolve_map(forward_rows, patch_rows)` 重新算，取 `cur[i]`——`resolve_map` 内部先铺 forward、再按文件出现顺序把 patches 逐条覆盖上去，天然拿到"最后一条 patch"，且**不限定这最后一条的 reason**。

单测夹具专门设计了 id=5 的三轮修订：`recall`（最早）→ `review`（中间，命名为 `GOLD_STALE_ZH_5`）→ `polish`（最终，非 review/recall 理由，来自本流水线自己的 `polish_commit.py` 写回场景）。`test_gold_current_text_is_resolved_not_stale_review_row` 断言取到的是 `polish` 版本，不是 `review` 版本。变异③（见下）证实：若实现改成"直接拿最后一条 reason∈{review,recall} 的 patch 行"，会错误地把 `review` 版本（已被推翻的中间版本）当成金标现行文本，测试立即抓到。

## 2. 三档分档的判据

对每个金标 id：`edit = edit_distance(strip_ctl(model_zh), strip_ctl(ref_zh))`，`limit = autoclear_limit(ref_zh)`：

- `edit ≤ minor_edit(4)` → **unchanged**
- `minor_edit < edit ≤ limit` → **minor**（幅度仍在"哪怕发生在普通候选身上也会被判定可自动清关"的范围内）
- `edit > limit` → **substantive**（超出了自动清关本该允许的幅度——这才是真正要防的"模型把定稿改成大改写"）

这个三分法直接对应 `config/polish.yaml` 里 `minor_edit` 一行的注释（"edit≤minor_edit 为轻微，>autoclear_limit 为实质"），中间区间补全为 minor。由于 `autoclear_abs=4=minor_edit`，`autoclear_limit()` 恒 ≥ `minor_edit`，三区间良序，不会出现负宽度。

`gold_pass = gold_substantive/(unchanged+minor+substantive) < CFG["calib_fail"](0.30)`。`total==0`（理论上不该发生，校准批里没有金标）保守判 `False`——呼应 `channel_state` 缺省关闭同一哲学，没有证据不给通过。

模型漏输出某个金标 id（`out_row is None`）按最坏情形算：`model_zh=None` → `strip_ctl(None)=""` → edit 约等于 `len(ref_zh)`，几乎必然落入 substantive——不会因为"没交卷"而免于计入实质改写（`test_score_missing_gold_output_counts_as_substantive` 钉死）。

## 3. 校准批是否入仓：裁定 = 不入仓

`make()` 产出的 `calib/<label>.batch.jsonl` 全部行统一打上合成批号 `f"calib-{label}"`（不是任何真实批号）。裁定：**校准批的模型输出只允许喂给 `score()`，绝不通过 `polish_ingest.py` 走正常入仓/清关流程**。理由两条：

1. 金标行是人工已裁定的定稿——若被当普通候选清关，等于用模型改写覆盖已拍板的决定，正是本工具要防止的事，逻辑自相矛盾。
2. 普通陪考句虽取自该 SEG 真实 `frozen/source.jsonl`，但合成批号让它们结构上不可能通过 `polish_ingest.ingest()` 的"批内非锁定 id 覆盖完整"检查（该检查按 `frozen/source.jsonl` 里登记的真实批号索引）——即便有人手滑把 `raw/<channel>/` 里的校准输出丢进正常流程，也无法被认领成任何真实批次，天然作废，不需要额外加白名单/拦截逻辑。

陪考句抽样时额外排除了"同时也在金标池里"的 id（`norm_candidates` 排除 `gold_pool_ids`），避免同一个 id 在 `truth.json` 里被判定成两种矛盾结果。

## 4. `channel_state.json` 与 Task 7 的契约核对

读 `tools/polish_triage.py` 里 `_channel_autoclear_power()`：

```python
return bool(channel_state.get(channel, {}).get("autoclear", False))
```

确认结构必须是 `{channel: {"autoclear": bool}}`，且**只更新自己这个 channel 的键**（读现有文件→改一个键→整体写回，不覆盖其它通道），`test_score_preserves_other_channels_in_state` 验证这一点。

`test_channel_state_contract_matches_polish_triage_reader` 不是自己重写一套解析逻辑自证，而是**直接 import 并调用 `polish_triage._channel_autoclear_power`** 去读本模块产出的 `channel_state.json`，同时验证一个"从未跑过 calibrate 的通道"仍保守缺省为 `False`——这是跨模块契约的真实断言，不是自我复述。

## 5. 已知偏差的播报措辞

固定字符串 `KNOWN_BIAS`：

> 已知偏差：金标是「曾出问题或值得记录」的非随机子集（复现句族/争议句/边界案例），其上下文分布系统性偏离普通批次——本考只做门槛（pass/fail），不是通道质量的精细度量，请勿把 pass 率当排行榜使用。

- `make()`/`score()`/CLI 每次调用都打进 stderr；
- `score()` 的返回 dict 额外带 `known_bias` 字段（下游/人工核对时不会遗忘）；
- 模块顶部 docstring 单列一节专门讲这件事。

## 6. 四个变异的红绿实况

全部按「改代码→跑对应测试确认真红→用 Edit 精确还原→跑全量确认恢复绿」的流程执行，无一处需要放宽测试来"迁就"变异（说明测试本身有牙，不是变异没打中）。

### ①三档阈值互换
```python
if edit <= limit:          # 互换：本该是 CFG["minor_edit"]
    gold_unchanged += 1
elif edit <= CFG["minor_edit"]:   # 互换：本该是 limit
    gold_minor += 1
```
命令：`uv run pytest -q tests/test_polish_calibrate.py::test_three_tier_classification_distinguishes_minor_from_unchanged`
结果：**红**——`assert result["gold_unchanged"] == 9` 处 `AssertionError: assert 10 == 9`（id=10 的 edit=6 本该落 minor，互换后被 `6≤7` 误判成 unchanged）。

### ②truth 混进 batch
在 `make()` 的金标行字典里加了一个 `"is_gold": True` 字段。
命令：`uv run pytest -q tests/test_polish_calibrate.py::test_make_produces_mixed_batch_and_truth`
结果：**红**——`assert "is_gold" not in r` 处 `AssertionError`（顺带验证了：即便这次没有触发字段名断言，下面的原始字节扫描 `"is_gold" not in raw_text.lower()` 也会独立抓到，双重保险）。

### ③（追加）金标取「patch 行里的 zh」而非 resolve 后现行值
`_gold_pool()` 改成维护 `last_gold_row`（只遍历 `reason∈{review,recall}` 的行，取其中最后一条的 `zh`），不再调用 `cur[i]`。
命令：`uv run pytest -q tests/test_polish_calibrate.py::test_gold_current_text_is_resolved_not_stale_review_row`
结果：**红**——`AssertionError`，实测拿到的是 `GOLD_STALE_ZH_5`（三轮修订里中间那条 `review` 版本），印证了 brief 警告的失败模式确实会发生。

### ④（追加）channel_state.json 结构错误
`score()` 里把 `state[channel] = {"autoclear": passed}` 改成 `state[channel] = passed`（少一层嵌套）。
命令：`uv run pytest -q tests/test_polish_calibrate.py -k "channel_state_contract or score_all_unchanged or preserves_other_channels"`
结果：**红，且红得比预期更响**——不是普通的断言失败，而是真实调用 `polish_triage._channel_autoclear_power()` 时直接 `AttributeError: 'bool' object has no attribute 'get'` 崩溃（3 个测试全部失败）。这是最强信号：结构一旦不对，Task 7 的消费代码会当场炸，而不是静默吞掉——但也说明如果没有 `test_channel_state_contract_matches_polish_triage_reader` 这个直接调用真实读取函数的测试，光靠 `polish_calibrate` 自己的单测是看不出这个崩溃的（`test_score_all_unchanged_passes` 之所以也红，是因为它内部同样断言了 `state == {"chTest": {"autoclear": True}}` 这个精确结构，属于额外命中，不是巧合）。

全部 4 处变异用 Edit 精确还原为原始代码，`git diff tools/polish_calibrate.py` 相对提交版本无残留改动（已跑 `uv run pytest -q` 全量确认 693 passed 恢复）。

## 7. 与 brief 的偏差

- brief 接口签名 `make(label, n_gold=10, n_norm=10)` / `score(label, raw_path)` 未显式带 `channel` 参数；父任务补充信息第 3 条已明确 `score(label, raw_path, channel, repo=None)`，本实现按补充信息走。
- brief 未定义 `.batch.jsonl` 逐行字段名；本实现选用 `{"id","batch","jp","opus_zh"}`（`opus_zh` 而非 `zh`，避免和 `score()` 判卷时读取模型输出行的 `zh` 字段混淆）。
- `_opus_lane_dir()` 硬编码 `repo/pilot/lanes/opus/data`（不像 `polish_setup.setup()` 那样开 `opus_data` 参数）——因为金标池语义上就是"整个 opus 车道的裁决历史"，不随 SEG 变化，没有需要指向别处的场景；已在模块 docstring 里写明这个设计取舍。
- 未额外实现"渲染成可直接投喂模型的 prompt 文本"这一步（`polish_context.render()` 那样的完整 prompt 拼接）——brief 的 `make()` 只要求产出 `.batch.jsonl`/`.truth.json`，如何把 `.batch.jsonl` 渲染成具体某个执行通道的 prompt 格式留给调用方（不同通道/车道可能有各自的投喂方式），本模块只负责"产出待投喂内容 + 判卷"两端。

## 测试输出（全量）

```
$ uv run pytest -q
693 passed in 3.47s
```

`git status --short` 显示本任务只新增了 `tools/polish_calibrate.py` 与 `tests/test_polish_calibrate.py`；`.claude/settings.json`、`data/api_ledger.jsonl` 是其他会话的未提交改动，任务全程未触碰。
