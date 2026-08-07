# P4 润色 pass：准入小考首考暴露问题的修复报告

日期：2026-08-07。范围：三组用户裁定的变更 + 一组小项修复，均在首次真实跑 SEG-1
（seg1-s2）准入小考之后暴露。全量测试：**780 passed**（基线 758，净增 22 条新测试；
另有若干原有测试因语义变更被同步改写，详见各节）。

---

## 变更一：锚点行从硬锁改软锁

### 改法与理由

`skeleton/anchors.yaml` 锚点行与"该 id 冻结时点已有 patch"两类行为不再一视同仁：

| 类别 | 判据 | 出稿 | 改动 | 自动清关 | K 配额 |
|---|---|---|---|---|---|
| 硬锁 | 冻结时点已有 patch | 判死 | — | — | — |
| 软锁 | 纯 anchors.yaml 锚点（未被覆盖为硬锁） | 可出稿 | 改动须 `adjudicate=true`，否则判死 | 永不 | 强制进队列，不被 K 挤出 |

**tie-break（两者都命中）固定归为硬锁**：一个 id 若已经有具体的人工 patch，这条
具体裁决比锚点表这条一般性指引更"重"，取更保守的一档。`hard_ids`/`soft_ids` 因此
互斥，并集恒等于旧版 `ids`。

**实现落点**：

- `tools/polish_setup.py::_locked_payload()`——`locked.json` 新增 `hard_ids`/
  `soft_ids` 两个字段（`ids`/`why` 保留，向后兼容；`why` 的 tie-break 字面值从旧版
  固定标 `"anchor"` 改为固定标 `"patched"`，与新的 `hard_ids` 分类一致，不再自相
  矛盾）。
- `tools/polish_ingest.py::ingest()`——硬锁出稿判死不变；软锁行新增一条判死：
  `zh` 改动但 `adjudicate` 不是 `true` → 判死（计入新字段 `discipline.<channel>.
  json.soft_lock_violations`）。批完整性检查 `expected_id_set` 从"减去全部锁定 id"
  改成"只减去硬锁 id"——软锁 id 现在必须像普通行一样出现一行（不改就照抄 opus）。
  旧格式 `locked.json`（无 `hard_ids`/`soft_ids` 键）向后兼容：整体当硬锁，`soft_ids`
  空集——不会因为读到旧格式就意外放行本来不该出稿的锚点行。
- `tools/polish_triage.py::triage()`——桶 0 判据从"锁定集合"收窄为"硬锁集合"；
  新增"软锁行且真的改了 → 无条件强制摘进桶 2，跳过 `_eligible` 计算与 K 排序竞争"
  这条分支。K 配额分配顺序：软锁强制占位（`forced_soft_count`）→ 剩余预算
  `K_remaining = max(0, K - forced_soft_count)` → 抽检/正常排位仍按原公式（只是把
  `K` 换成 `K_remaining`）。若软锁改动数本身超过 K，`meta.forced_soft_over_budget=
  true` 并 stderr 显著播报（不静默吸收）。`queue.md` 对这类 id 单独标注"进入队列
  原因：软锁改动（锚点行，强制进入队列，不受 K 名额影响）"。
- `tools/polish_context.py::render()`/`render_calib()`——任务说明拆成"硬锁绝对不能
  动"与"软锁可以斟酌但改动须 adjudicate=true 并写 note"两条；"锁定 id 清单"拆成
  "硬锁 id 清单"（禁止出稿）与"软锁 id 清单"（可以出稿）两节；逐批正文里软锁 id
  不再被排除，前面带 `【软锁】` 标记；输出契约措辞同步更新。
- `tools/polish_amplify.py`——`_load_frozen()` 与 `_build_panorama()` 同步拆分
  hard_ids/soft_ids（放大扫描的桶 0 全景与锁定 id 清单不该继续把两者混说"禁止
  改动"，那对软锁不成立）——这个模块不在用户列的三组变更范围内，但沿用旧的单一
  锁定语义会让放大扫描 prompt 对模型说谎（"软锁 id 禁止改动"这句现在是假的），
  故做了同一批次的最小同步修复。

### 新测试

- `tests/test_polish_setup.py`：`test_setup_freezes_and_locks`（更新，断言
  `hard_ids`/`soft_ids`）+ 新增 `test_locked_payload_overlap_resolves_to_hard`。
- `tests/test_polish_ingest.py`：新增 `_build_mini_soft_lock` 夹具 + 6 条测试
  （未改动放行/改动+adjudicate 放行/改动无 adjudicate 判死/批完整性要求软锁 id
  出现/旧格式兼容）。既有 `_build_mini`/`test_locked_id_killed_and_disciplined`
  等测试通过给锁定 id 补一条内容相同的 patch（使其归为硬锁）保持不变，不测试软锁
  行为混进已有大量断言的主夹具。
- `tests/test_polish_triage.py`：新增 `_build_mini_soft_lock` 夹具 + 5 条测试
  （软锁改动永不自动清关/K=0 时不被挤出/未改动正常走桶 1/不饿死普通自动清关候选/
  queue.md 标注原因）。原 `mini` 夹具的 id 13（原为纯 anchor）补一条 patch 归为
  硬锁，保留原有"triage 自己的锁定兜底"测试语义不变。
- `tests/test_polish_context.py`：`_build_mini_seg()` 新增 `patched_ids` 参数；
  `mini_seg_render`（硬锁）与新增 `mini_seg_soft_render`（软锁）两个夹具区分；
  新增 `test_render_soft_locked_ids_appear_in_body_with_marker`；更新
  `test_render_marks_locked_and_embeds_opus`/`test_render_locked_ids_excluded_
  from_body`/`test_render_chapter_titles_stable_regardless_of_optional_sections`/
  `test_calib_prompt_has_no_lock_marks` 的标记与文案断言。
- `tests/test_polish_amplify.py`：`_build_mini` 给 id 10 补一条 patch（归为硬锁，
  保留桶 0 相关既有测试）；新增 `test_scan_prompt_splits_hard_and_soft_lock_
  sections`；`test_scan_prompt_includes_bucket3_full_text` 的 "锁定 id" 断言改为
  "硬锁 id"。

### 变异红绿实况

1. **软锁行改动却没带 adjudicate 时不判死**（`polish_ingest.py` 判死分支临时改成
   `if False and ...`）→ `test_soft_lock_changed_without_adjudicate_killed`
   转红（`added==3` 而不是期望的 `2`）。还原后绿。命令：
   `uv run pytest -q tests/test_polish_ingest.py -k soft_lock`。
2. **软锁行被自动清关**（`polish_triage.py` 强制进队列分支临时改成
   `if False and cid in soft_ids:`）→ 3 条测试转红
   （`test_soft_lock_edit_forced_into_queue_never_autoclears`、
   `test_soft_lock_edit_not_squeezed_out_by_zero_K`、
   `test_soft_lock_queue_md_labels_forced_reason`）。还原后绿。命令：
   `uv run pytest -q tests/test_polish_triage.py -k soft_lock`。
3. **tie-break 翻回旧版"anchor 优先"**（`polish_setup.py` 的
   `hard_ids = patched_ids - anchor_ids` / `soft_ids = anchor_ids`）→
   `test_locked_payload_overlap_resolves_to_hard` 转红（`hard_ids==[]` 而不是
   `[13]`）。还原后绿。

绿变异区分说明：以上三处红测试都是在**移除新增的具体判定分支/改写具体表达式**
后立刻转红，且转红的正是"专门为这条规则写的测试"（不是碰巧被别的判据兜住）——
判定为"变异真正打中"，不是"测试无牙"。

---

## 变更二：`polish_calibrate.score()` 判卷缺陷修复

### 根因

`gold_unchanged` 统计口径是 `edit <= minor_edit`（=4），字面上叫"未改动"，实际是
"未改动或轻微改动"。SEG-1 首次真实小考两条通道都报 `gold_unchanged=10`，独立核算
显示 fable-wf 实际改了 3/10（1 条 `adjudicate=true` + 2 条静默）、ds-flash 改了
2/10（全部静默）——报告在说谎。

**更根本的问题**：金标句的正确判据不是编辑距离，是"有没有被静默推翻"——实测 id
5684：ds-flash 把人裁定稿"得**厅**那支曲子才行。"悄悄改成"得**听**那支曲子才行。"
（`edit=1, adjudicate=false`），fable-wf 改成"得**问问**那支曲子才行。"但带了
`adjudicate=true`（`edit=2`）。1 个字的静默推翻和大段改写同样危险——动了就是信号，
幅度不重要。

### 修法

1. **三档改为字面一致**：`gold_unchanged`=`edit==0`、`gold_minor`=`0<edit≤
   minor_edit`、`gold_substantive`=`edit>minor_edit`（不再牵涉 `autoclear_limit`
   ——那本是给普通候选定的自动清关阈值，从一开始就文不对题）。这三档现在只做
   幅度展示，不再直接决定 pass。
2. **pass 判定改用"有没有静默推翻"**：新增 `changed_adjudicated`（`edit>0` 且
   `adjudicate=true`，正常信号）与 `changed_silent`（`edit>0` 且未请裁，或模型
   干脆漏交这个 id——两种都是最坏情形）。`silent_override_rate = changed_silent
   / total`；`pass = silent_override_rate < CFG["calib_silent_override_fail"]`
   （新配置项，默认 **0.10**——10 句金标 1 句静默覆盖就落到边界判 fail）。
   **未复用** `CFG["calib_fail"]`（旧键语义是"实质改写占比"，与新判据不同，静默
   改变一个既有配置项的含义比新增一个键更危险）；`calib_fail` 留在
   `config/polish.yaml` 但 `score()` 不再读取它，仅作历史阈值可追溯，注释里写明
   已废弃。
3. **`calib_silent_override_fail=0.10` 的理由**：这是本次修复要防的最危险失败
   模式（静默覆盖人工裁决），"动了就是信号，幅度不重要"意味着理论上应该零容忍；
   留 10% 而不是 0% 是给"金标行恰好撞上某种极端边界巧合"留一点点冗余，不是纵容
   静默覆盖——真实两条通道的静默覆盖率都是 20%，本就应该在这个阈值下双双 fail
   （见下方"SEG-1 复核结果"）。
4. **结果新增 `details` 逐条明细**（每条金标的 `id`/`edit`/`tier`/`adjudicate`/
   `missing_output`/`silent_override`/`ref_zh`/`model_zh`），操作者不需要再像
   这次一样自己写脚本核算才能核实报告是否准确。

### 新测试

`tests/test_polish_calibrate.py` 新增/改写共 8 条：
`test_gold_unchanged_only_counts_exact_match_not_edit_le_4`（核心回归锁，edit=1
必须落 minor 不是 unchanged）、`test_tier_boundary_uses_only_minor_edit_
threshold`（三档边界只看 minor_edit，替换掉原来牵涉 autoclear_limit 的旧测试）、
`test_changed_with_adjudicate_does_not_count_as_silent_override`、
`test_silent_override_fails_even_a_single_line`（1/10 静默覆盖必须 fail，核心
场景）、`test_mixed_channel_matches_real_incident_id5684_shape`（按实测比例
形态构造：2 条静默+1 条请裁+7 条未动）、`test_details_field_reports_per_gold_
row`、`test_missing_gold_output_marked_missing_and_silent_in_details`。原有
`test_score_all_unchanged_passes`/`test_score_4_of_10_substantive_fails`/
`test_score_missing_gold_output_counts_as_substantive` 等未改动即通过（三档
字段名不变，行为在这些用例下与旧实现巧合一致，因为这些用例本来就没有"轻微改动
被误记成未改动"或"改了却不该算失败"这类边界）。

### 变异红绿实况

1. **`gold_unchanged` 退回统计 `edit≤4`**（把 `if edit == 0` 改回
   `if edit <= CFG["minor_edit"]`）→ 4 条测试转红（`test_mixed_channel_...`、
   `test_details_field_...`、`test_gold_unchanged_only_counts_exact_match_...`、
   `test_tier_boundary_uses_only_minor_edit_threshold`）。还原后绿。
2. **"改动未请裁"不影响 pass**（把 `pass` 判定改回旧的
   `(gold_substantive/total) < CFG["calib_fail"]`，完全无视 `changed_silent`）→
   `test_silent_override_fails_even_a_single_line`、
   `test_mixed_channel_matches_real_incident_id5684_shape` 两条转红（都算出
   `pass=True`，与断言的 `False` 相反）。还原后绿。

绿变异区分：两处都是命中"这次修复要防的具体缺陷"，转红测试正是为这个缺陷专门
写的，不是被无关判据碰巧兜住——判定为"变异真正打中"。

### SEG-1 复核结果（真实数据，非测试）

用修好的 `score()` 重跑 SEG-1 已有的两份真实校准输出（`calib/raw.{fable-wf,
ds-flash}.jsonl`，未删除、未改动，按用户要求保留作实测证据）：

| 通道 | gold_unchanged | gold_minor | gold_substantive | changed_adjudicated | changed_silent | silent_override_rate | pass |
|---|---:|---:|---:|---:|---:|---:|---|
| fable-wf | 7 | 3 | 0 | 1 | 2 | 0.20 | **false** |
| ds-flash | 8 | 2 | 0 | 0 | 2 | 0.20 | **false** |

`pilot/polish/seg1-s2/channel_state.json` 已重新生成为
`{"ds-flash":{"autoclear":false},"fable-wf":{"autoclear":false}}`（此前两条都是
`true`——本次修复直接纠正了 SEG-1 的免检权判定，两条通道段末都必须走人工裁决
队列，不能自动清关）。

---

## 变更三：小项修复（fable-wf 通读 prompt 报告）

1. **`adjudicate: true` 时 `zh` 该放什么**：`polish_context.TASK_INSTRUCTIONS`
   新增明确规则——放"你认为更好的那一版建议稿"，不是机械照抄 opus 敷衍了事；
   opus 原文本来就在 prompt 里给裁决者对照，通道给出的是判断依据。
2. **遇到确定的错译/错字没有条款**：新增一条——怀疑是错译/错字时一律
   `adjudicate=true`，`note` 里写"疑似错译/错字"及具体理由，不擅自改判定。
3. **`jp_tail` 三个边角契约**：先读了 `tools/polishlib.jp_tail`/`strip_ctl` 与
   `polish_ingest.ingest()` 的核验代码确认实际行为——三条边角**实现本来就是
   对的**（Python 切片对短串天然返回全串；`strip_ctl` 不移除【】前缀；`strip_ctl`
   不移除空格），只是契约文字从未写清楚。把三条写死进 `OUTPUT_CONTRACT_HEADER`
   （不足 8 字取全串／【说话人】前缀算原文一部分／空格算一个字符），并在
   `tests/test_polishlib.py` 补 3 条测试锁定这个行为（不是新代码，是把"已经正确
   的实现"钉成"写清楚的契约"）。

无需变异（这三条是文档/措辞修正 + 只读验证，没有新增可被删除的判定分支；
`jp_tail` 三条边角测试直接验证的是既有 `polishlib` 代码的天然行为）。

---

## SEG-1 重冻结/重渲染处理

SEG-1（seg1-s2）冻结面因 `locked.json` 结构改动（新增 `hard_ids`/`soft_ids`）与
prompt 文本改动（硬锁/软锁措辞、任务说明新增条款、输出契约新增 jp_tail 三条边角）
需要重新冻结与重渲染：

1. `polish_setup.setup()` 判断"是否已点火"只看 `candidates.*.jsonl`/
   `decisions.jsonl`/`triage.json` 是否存在——SEG-1 这三者都不存在（只有 calib
   产物），故**不需要 `--force`**，正常重跑：
   `uv run python tools/polish_setup.py --seg seg1-s2 --opus-data pilot/lanes/opus/data`。
   `polish_setup --verify seg1-s2` 确认"冻结校验：无漂移"。
2. 重渲染四个生产 session + 校准 prompt，`plan.json` 随 `--out` 自动更新：
   ```
   uv run python tools/polish_context.py --seg seg1-s2 --session {1,2,3,4} --out work/ctx/p4s1-s{N}.md
   uv run python tools/polish_context.py --seg seg1-s2 --calib --out work/ctx/p4s1-calib.md
   ```
   四个 session 的 `prompt_hash` 全部更新（`manifest.json` 里除 `frozen/locked.json`
   的哈希与 `ts` 外，其余文件哈希/`opus_at`/`glossary_v` 逐位不变——证明这次重冻结
   只是 schema 变化，不是数据漂移）。
3. **重跑准入小考判卷**（用已有真实模型输出、不重新派发）：见上方"SEG-1 复核
   结果"。这一步把 `channel_state.json` 从错误的 `{true, true}` 纠正为正确的
   `{false, false}`——是本次修复对生产数据的实际影响，不只是代码/测试层面的改动。

未涉及：`candidates.*.jsonl`/`decisions.jsonl`/`triage.json` 均不存在（SEG-1 尚
未点火），无需处理"冻结后新落人裁 patch"之类的连带问题；`w4_full.json` 是清关后
才有意义的全段复检产物，与本次冻结面 schema 改动无关，未touch。

---

## 测试结果

```
uv run pytest -q
780 passed in ~4s
```

基线 758 passed → 780 passed（净增 22）。分模块（含改写）：
`test_polish_setup.py` +2、`test_polish_ingest.py` +6、`test_polish_triage.py`
+5（净计，另替换/更新既有断言若干处不改变用例数）、`test_polish_context.py`
+2（新增1，另有若干既有测试改写断言不增删用例数）、`test_polish_calibrate.py`
净 +6（新增 8 条，删除 1 条不再适用的旧测试）、`test_polish_amplify.py` +1、
`test_polishlib.py` +3。

---

## 未完全解决 / 决定不修的条目

1. **`polish_amplify.py` 的软锁/硬锁拆分**只做到"展示层面不再说谎"（桶 0 全景、
   锁定 id 清单文案与字段拆分），**没有**给放大扫描本身新增"软锁强制回炉"之类的
   行为——放大扫描的候选恒不自动清关（`channel=="amplify"` 硬规则），这本来就
   比软锁的"永不自动清关"更严格，语义上不冲突，故未做更多改动。如果后续放大
   扫描要对软锁行有专门的展示（比如把桶 2 里"因软锁强制排队"的 id 单独摘出来
   展示，而不是和普通桶 2 候选混在一起），需要另开工作项。
2. **未在 `_build_panorama()` 的"软锁 id"小节里逐条渲染 opus/候选内容**——目前
   只列 id 号（类似原来桶 0 硬锁列表的呈现方式）。若软锁行已经进了桶 2（真的被
   改动、强制排队），它会在桶 2 小节里正常展示 opus/候选/裁决全文；这个"软锁 id
   小节"只服务于"这个 SEG 里哪些 id 是软锁"这个静态背景信息，认为够用，未过度
   设计。
3. 用户明确排除在本轮之外的三项（兄弟句盲区/score 双轴语义/校准批覆盖面）与
   `tools/check_batch.py`/`tools/build_context.py` 均未触碰。
4. `docs/superpowers/plans/2026-08-07-p4-polish-pass.md`（原始计划文档，记录的
   是 Task 1-11 的历史执行记录）未回改——它是执行历史的快照，spec/runbook 才是
   "现行状态"文档，本次改动按惯例只更新后者。
