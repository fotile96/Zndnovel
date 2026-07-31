# 终审修复波：执行报告

Brief: `.superpowers/sdd/2026-07-31-p2-pilot-tooling/final-fix-brief.md`
Base commit: `b124450`（Hotfix D 之后，最终全分支评审之前）

全部 10 条发现（C1/C2/I1–I6/I-extra/顺手 minor）已按 brief 逐条修完，TDD 优先，
两处必做突变验证均已执行并转红，全量 `uv run pytest -q` 206/206 全绿。

---

## 逐条修法与落地位置

### C1（Critical）四道验收闸门在计划里零出现

改 `tools/gen_plan.py`，全部改动仅在 `lane_cfg is not None`（车道模式）时生效；
`test_non_lane_mode_gate_markers_are_completely_absent` 锁死非车道模式零改动。

- **逐批崩溃探测**：`_batch_task`（`tools/gen_plan.py:134`）在 check_batch（Step 3）
  与 append_forward 之间插入新的 Step 4（`--lane-dir` 参数存在时才插，非车道
  模式不动），命令 `uv run python tools/detect_collapse.py --batch N --lane-dir
  <车道根>`，正文说明"顾问级、恒返回 0、命中需人眼过一遍"。append_forward 相应
  从 Step 4 顺延为 Step 5——同时修了两处会因此错位的静态文案（见下方"连带发现"）。
- **每检查点先校验冻结**：`_checkpoint_task`（`tools/gen_plan.py:180`）
  `lane_mode=True` 时最前面插 Step 0 `uv run python tools/lane_setup.py --verify`，
  漂移则"立即停止试点"。
- **batch 1/2 硬停**：`_hardstop_after_batch1`（`tools/gen_plan.py:225`）与
  `_hardstop_after_batch2`（`tools/gen_plan.py:260`），`render()` 里按"本计划第
  1/第 2 个批次任务处理完之后"插入（`tools/gen_plan.py:415,418`，用
  `batch_task_count` 计数，不是硬编码全局 batch id——因为试点计划恒从 batch 1
  开始，两种判定等价，但前者对未来的部分区间重新生成更健壮）。
  - hardstop-1：①`diff <本车道>/data/forward.jsonl <对方车道根占位符>/data/forward.jsonl`
    + 提前跑一次 batch 2 的 build_context 核验前缀含本车道 batch 1 译文（产物会被
    正式 Step 1 覆盖，无副作用）②`lane_setup --verify`③人工抽读④门禁：任一项不过
    停止试点。
  - hardstop-2：①用 batch1/2 真实译文标定 `detect_collapse` 三阈值、写进
    `pilot/lanes/pilot-manifest.json` 的 `collapse_thresholds` 段、偏离默认时给出
    重出计划的完整命令行（见 I-extra）②人工抽读③崩溃探测命中逐条过目④门禁。
- **窗口对撞探针**：`_window_probe_task`（`tools/gen_plan.py:302`），`render()` 里
  仅当选中批次含 `WINDOW_PROBE_BATCH=33`（`tools/gen_plan.py:26`，spec §2 压缩
  边界常量，非"最后一批"）才生成，位置在最后一个周期检查点之后、终任务之前
  （`tools/gen_plan.py:431`）。内容：`cp -r` 临时车道副本 → 分别
  `--profile cc`/`--profile api-A` 出两版 context → 派子代理各出一版译文（不写回
  正式 forward）→ 人工并排比对 + 清理临时副本。**不改 `build_context.py`**（I6，
  见下）。

**连带发现（修复过程中自行发现、一并修复，未在 brief 中单独列出）**：
- `_header`（`tools/gen_plan.py:81`）的 Global Constraints 段与 `_final_task`
  （`tools/gen_plan.py:338`）都硬编码"执行 git 操作（Step 4）"——车道模式下入库
  提交现在是 Step 5，两处都已改为按 `lane_cfg`/`lane_mode` 动态取值，并各补一条
  回归测试（`test_header_git_step_reference_matches_actual_step_number`、
  `test_final_task_commit_step_reference_matches_actual_step_number`）。

**任务数**：`data/batches.jsonl` batch 1–35（every=5）从 43 变为 **46**
= 35 批次任务 + 7 个周期 CHECKPOINT（every=5 触发 7 次）+ 2 个硬停
（batch 1 后、batch 2 后）+ 1 个窗口对撞探针（batch 33 在段内）+ 1 个终任务。
brief 预留的 47 未用到——本实现里"1 个 …"的浮动项没有额外插入。

### C2（Critical）车道译文存放：移出 `work/`

- `tools/lane_setup.py:24`：`LANES_ROOT = REPO / "pilot" / "lanes"`（原
  `WORK / "lanes"`），模块 docstring 同步说明迁移原因。
- `.gitignore` 新增 6 行（`pilot/lanes/*/work/`、`skeleton/`、`glossary/`、
  `data/*` 忽略 + 两条否定规则放行 `forward.jsonl`/`patches.jsonl`）。
- 物理迁移：`mv work/lanes pilot/lanes`（未重建）；两个 `lane.json` 的
  `lane_dir` 字段（纯展示，不参与校验逻辑）同步更新为新绝对路径。
- 两份计划重出（见下方"重出计划自查"）。
- `tools/lane_setup.py` docstring 与 `prompts/translator_cc.md`「路径基准」节
  全部 `work/lanes` 字样已改 `pilot/lanes`（`prompts/translator_cc.md:11,95`）。

验证：
```
$ git check-ignore pilot/lanes/opus/data/forward.jsonl; echo "exit=$?"
exit=1   # 未被忽略
$ uv run python tools/lane_setup.py --verify
冻结校验：无漂移
```

### I1 `stratified_sample` 位置退化

`tools/compare_lanes.py:51`。没有采用 brief 举例的
`bucket[::max(1, len(bucket)//per_kind)][:per_kind]`——实测该式在非整除的真实
分布下不保证端点入选（例如 n=1000, per_kind=20 时最后落点是第 951 个而非
第 1000 个，仍会漏掉试点段末批）。改用严格保证端点的线性等距取样：
`idxs = {round(i*(n-1)/(per_kind-1)) for i in range(per_kind)}`，`i=0` 恒取
`bucket[0]`、`i=per_kind-1` 恒取 `bucket[-1]`。

新增 `test_stratified_sample_covers_head_and_tail_of_large_bucket`
（`tests/test_compare_lanes.py`）：1000 元素桶、per_kind=20，断言 1 与 1000
同时入选。原有 `test_stratified_sample_covers_every_unit_kind` 的期望值同步
更新为反映端点覆盖（scene 层从旧算法的 `{1,2}` 改为新算法的 `{1,3}`）。

### I2 gen_plan 车道断言假防护（已突变实证）

`tests/test_gen_plan.py` 新增 `test_lane_cfg_env_prefix_is_present_on_every_step_that_needs_it`：
按 Step 粒度断言整条命令行（`f'{env}uv run python tools/check_batch.py --batch 1'`、
`f'{env}uv run python tools/append_forward.py --batch 1 '`），不再只查全文出现
次数。

### I3 `translator_cc.md` 未随 Hotfix D 同步

- 自查命令（`prompts/translator_cc.md:85`）补 `--lane-dir <车道根>`，「路径
  基准」节（`prompts/translator_cc.md:11`）同步补一句解释原因。
- `prompts/translator_cc.md:41` 第四节旧名"四、术语与风格"改为
  "四、术语、风格与角色口调"，与 `prompts/translator_cc.md:34`（T2 已改名处）
  和 `build_context.py` 实际渲染节名一致。
- 顺手修：`prompts/translator_cc.md:16` "两种写法都不会出错（哪怕结果字节
  完全相同）"改为"——因为读到的本就是同一份文件"（让步→因果）。

### I4 冻结校验只自比不互比；compare_lanes 从仓库根读锚点

- `tools/lane_setup.py:123,126`：`verify()` 新增跨车道一致性检查
  `CROSS_LANE_KEYS = ("cards_zh", "anchors", "active", "glossary_max")`，
  取全部"健康"（未损坏）车道以字典序第一条为基准两两互比，不等则报
  "跨车道不一致：…"。新增
  `test_verify_detects_cross_lane_glossary_mismatch`（两条车道分别在仓库
  glossary 变更前后 setup，各自自比全绿但互比应报漂移）与
  `test_verify_cross_lane_check_does_not_false_positive_on_matching_lanes`
  （正常流程不误报）。
- `tools/compare_lanes.py:117-124`：`main()` 的锚点表改从 `--lane-a` 的冻结
  快照 `la/skeleton/anchors.yaml` 读，并与 `--lane-b` 的比对，不等则
  `raise SystemExit`（拒绝出任何对照材料）。新增
  `test_main_reads_anchors_from_lane_a_frozen_snapshot_not_repo`（仓库当前
  值故意设第三个值，验证确实读的是车道快照）与
  `test_main_refuses_when_lane_anchors_diverge`。

### I5 `lane_setup` 重跑会静默重冻结并覆盖基准

- `tools/lane_setup.py:42`：`setup()` 新增 `force` 参数，`data/forward.jsonl`
  已存在时 `raise SystemExit`（除非 `force=True`）。
- `tools/lane_setup.py:88`：`record()` 改为读现有 manifest、逐车道合并——
  已记录过的车道若当前实际哈希与记录不同且未 `force`，`raise SystemExit`；
  新车道或哈希未变则正常写入。**连带修复**：manifest 除 `"lanes"` 外的其余
  顶层键（供 I-extra 的 `collapse_thresholds` 使用）现在会被保留，不再被
  `record()` 整体覆盖清空。
- `main()`（`tools/lane_setup.py` 里的 CLI）新增 `--force` 透传给两者。
- 6 条新测试覆盖：拒绝重跑/`--force`放行/合并新车道不需要force/内容不变时
  重跑是 no-op/manifest 其余顶层键保留/CLI `--force` 端到端。

### I6 窗口对撞探针破坏性

**未改产码**（`tools/build_context.py` 零改动）。修法落在 C1 item 4 新增的
`_window_probe_task`（`tools/gen_plan.py:302`）文本里：显式要求 `cp -r` 出
临时车道副本、`--repo` 指向临时副本而非正式车道、两版译文均不写回正式
`forward.jsonl`、跑完 `rm -rf` 清理。测试
`test_window_probe_task_present_when_batch_33_selected` 断言生成文本里含
`cp -r` 与 `rm -rf`。

### I-extra 崩溃阈值标定值固化去处

选择"写进 `pilot-manifest.json` + 偏离默认时重出计划固化进命令行"（brief
给出的第二个选项），理由见文末"设计取舍说明"。落地：
- `tools/gen_plan.py:380` `_THRESHOLD_FLAGS` + `_thresholds_arg()`：把
  `{"kana_max": .., "ratio_lo": .., "ratio_hi": ..}` 转成要拼进
  detect_collapse 命令行的 flag 串，缺省为空（沿用工具自身默认值）。
- `render()`/`main()` 新增 `collapse_thresholds` 参数与
  `--kana-max`/`--ratio-lo`/`--ratio-hi` CLI flag（`tools/gen_plan.py:462`起）。
- hardstop-2 任务正文给出把标定值写进 `pilot/lanes/pilot-manifest.json`
  `collapse_thresholds` 段的一次性 Python 命令，以及偏离默认时重出计划的
  完整命令行（含批号区间、label、四个车道参数、三个阈值 flag）。
- I5 的 `record()` 改动（保留 manifest 其余顶层键）是这个方案能落地的前提——
  否则下次 `lane_setup.py`（非 `--verify`）重跑会把人工写入的
  `collapse_thresholds` 段整体抹掉。

### 顺手 minor：`_header` 的 label-as-chapter 表述

`tools/gen_plan.py:81`：`_header` 新增 `chapters_all` 参数，单章模式（含
`--chapter` 原生用法）保持原表述不变；跨章别连续段（`--batches` 模式）改为
"{label}（{lane} 车道）翻译执行计划"+ Goal 里显式列出真实章别数与列表、
声明"这是一个 timeline 连续段（非单一章节）"。两条新测试锁死两种模式各自
的表述。

---

## TDD / 突变验证

### I2 突变验证

```
$ python3 - <<'EOF'
# 删掉 append_forward 那行的 {p["env"]}
...
EOF
$ uv run pytest tests/test_gen_plan.py -q
.......F................................                                 [100%]
FAILED tests/test_gen_plan.py::test_lane_cfg_env_prefix_is_present_on_every_step_that_needs_it
1 failed, 39 passed in 0.09s
```
只有新增的 Step 粒度用例转红，其余（含旧的"全文出现过一次"断言）仍绿——
证明旧断言确实是假防护，新断言有判别力。已恢复原文件，恢复后
`uv run pytest tests/test_gen_plan.py -q` 40/40 全绿。

### I4 突变验证

```
$ python3 - <<'EOF'
# 删掉 verify() 里的跨车道一致性检查块
...
EOF
$ uv run pytest tests/test_lane_setup.py -q
...................F...                                                  [100%]
FAILED tests/test_lane_setup.py::test_verify_detects_cross_lane_glossary_mismatch
1 failed, 22 passed in 0.11s
```
只有新增的跨车道用例转红，`test_verify_cross_lane_check_does_not_false_positive_on_matching_lanes`
等其余用例仍绿（无 flaky）。已恢复原文件，恢复后
`uv run pytest tests/test_lane_setup.py -q` 23/23 全绿。

### 全量测试

```
$ uv run pytest -q
........................................................................ [ 34%]
........................................................................ [ 69%]
..............................................................           [100%]
206 passed in 2.61s
```
（修复前基线 173 passed；本轮净增 33 条测试）

---

## 重出计划自查（实际输出）

命令：
```bash
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-opus \
  --lane-dir pilot/lanes/opus --model opus --effort max --append-model-id claude-opus-5
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-fable \
  --lane-dir pilot/lanes/fable --model fable --effort high --append-model-id claude-fable-5
```
输出：`46 个任务`（两份计划一致）。

四道闸门出现次数（`translate-pilot-opus.md`，`translate-pilot-fable.md` 同）：

| marker | 次数 |
|---|---|
| `detect_collapse` | 39 |
| `隔离验收` | 2 |
| `硬停` | 38 |
| `lane_setup` | 8 |
| `--verify` | 8 |
| `窗口对撞` | 1 |

```
$ git check-ignore pilot/lanes/opus/data/forward.jsonl; echo "exit=$?"
exit=1        # 无输出，未被忽略
$ grep -c 'pilot/lanes/fable' docs/superpowers/plans/translate-pilot-opus.md
0
$ grep -c 'pilot/lanes/opus' docs/superpowers/plans/translate-pilot-fable.md
0
$ grep -ci 'fable' docs/superpowers/plans/translate-pilot-opus.md
0
$ grep -c 'work/lanes' docs/superpowers/plans/translate-pilot-opus.md docs/superpowers/plans/translate-pilot-fable.md
0 / 0
```

**设计取舍说明——对方车道路径用占位符**：C1 item 3① 要求硬停 1 给出"可跑
的命令"对照两条车道的 `forward.jsonl`；但终审自查清单同时要求
`grep -c 'pilot/lanes/fable' translate-pilot-opus.md` 必须为 0。两者字面
冲突：若在生成期自动解析出对方车道的具体路径写进 opus 计划文件，opus 计划
就会包含 "fable" 字样。判断这不是需要打断去问用户的"设计分歧"，而是有
现成解法：改用占位符 `<对方车道根——pilot/lanes/ 下除 opus 外的另一条车道
目录，执行时按当次试点实际车道配置填入>`，与本文件里既有的
`<model>`/`<ctx_sha>` 是同一种"执行者按上下文填空"的约定，diff 命令本身
仍然是完整可跑的（只差一次替换）。据此简化：移除了最初实现里在 `main()`
里自动扫盘发现 sibling 车道目录的代码（曾经能在两条车道都已 `setup` 过时
把具体路径烤进计划），改为恒定占位符——更简单，也更彻底地保证两份计划各自
独立、互不知晓对方存在。

## `lane_setup --verify` 迁移后输出

```
$ uv run python tools/lane_setup.py --verify
冻结校验：无漂移
```

## Files changed（按 commit）

1. `70cdef6 fix: 试点执行计划补齐四道验收闸门与安全网假防护修复`
   - `tools/gen_plan.py`、`tools/compare_lanes.py`、`tools/lane_setup.py`
   - `tests/test_gen_plan.py`、`tests/test_compare_lanes.py`、`tests/test_lane_setup.py`
2. `daae5e6 fix: 车道根迁出 work/，改 pilot/lanes/ 以让译文线可入库`
   - `.gitignore`
   - `pilot/lanes/opus/lane.json`、`pilot/lanes/fable/lane.json`（新增，随 mv）
   - `pilot/lanes/pilot-manifest.json`（新增，随 mv）
3. `e29cdc8 data: 重出两份试点执行计划（四道闸门 + pilot/lanes 路径）`
   - `docs/superpowers/plans/translate-pilot-opus.md`
   - `docs/superpowers/plans/translate-pilot-fable.md`
4. `03a7af9 docs: 译者模板同步车道根迁移、check_batch 车道参数与第四节改名`
   - `prompts/translator_cc.md`

未提交、保留原状：`.superpowers/sdd/2026-07-31-p2-pilot-tooling/progress.md`
（协调者拥有，本轮开场即处于已修改状态，非本次改动）。

`work/lanes/` 已随 `mv` 清空（原本就在 `.gitignore` 内，git 从未追踪其内容，
无需额外清理动作）。

---

## Self-review

**Completeness**：10 条逐条对照 brief 复核，均有对应代码/文档改动 + 测试
（C2 是纯配置+数据迁移，无新测试，但有 `--verify` 与 `check-ignore` 两项
可复核的验证输出）。C1 的"按你实际插入数为准"已如实报告为 46（非 brief
预留的 47）。

**Quality**：新增任务文本对无上下文执行者可直接照做——每个 Run 命令都是
完整可复制的字符串（含 `p["env"]`/`--lane-dir` 等前缀），门禁任务的"不通过
则停止试点"均加粗且独立成 bullet。抽查了生成的 `translate-pilot-opus.md`
若干任务段（batch 1/2 附近的两个硬停、CHECKPOINT、窗口探针、终任务），
未发现断章或悬空引用。

**Discipline**：
- 未重建车道（`mv` 后 `--verify` 报无漂移，若曾 `rmtree`+`copytree` 重建则
  哈希必变）。
- 两份计划均由 `tools/gen_plan.py` 命令生成，未手改任何 `.md`。
- 未触碰 `lua_scripts/`、`png/`、`skeleton/`、`glossary/`、`analysis/`
  （`git status` 全程未出现这些路径）。
- 非车道模式输出：`test_non_lane_mode_gate_markers_are_completely_absent`
  用严格等式（`== 10`，非原来的 `>= 9`）钉死任务数不变，且逐一断言六个
  新增 marker 字符串均不出现。

**Testing**：
- I2 突变（删 append_forward 行的 `{p["env"]}`）：仅新断言转红——已复核。
- I4 突变（删 verify() 跨车道检查块）：仅新断言转红——已复核。
- 全量 `uv run pytest -q`：修复前 173 → 修复后 206，206/206 全绿。

## Concerns

1. **C1 item 3① 与"跨车道 grep 必须为 0"的自查项存在字面张力**（已在上文
   "设计取舍说明"中给出判断与实现，未打断询问用户）：改成占位符后，硬停 1
   的 diff 命令不能直接复制执行——执行者需要先把 `<对方车道根……>` 换成
   实际路径（`pilot/lanes/fable` 或 `pilot/lanes/opus`）。这与本文件里
   `<model>`/`<ctx_sha>` 的既有占位符约定一致，但如果终审设计者原本预期
   "开箱即用、零替换"的命令，这里是一个可讨论点。
2. **窗口对撞探针（`_window_probe_task`）派子代理翻两版译文，成本记入
   spec §7 "额外约 1 批全前缀成本"**，但探针任务本身不会被
   `check_batch`/`append_forward` 校验或入库——如果试点报告忘记专门核对
   这个任务是否被跳过，探针有可能被无意漏做而不留痕迹。建议试点报告
   §4"人工对照评分记录"里显式勾一项"窗口对撞探针已执行/结论"。
3. **I-extra 选择了"文档级"方案**（manifest 存值 + 偏离时重出计划），
   `detect_collapse.py` 本身不读 manifest；如果标定确实偏离默认，执行者
   必须记得重新生成计划并从新文件继续——这一步完全靠硬停任务文本里的
   提醒，没有机器强制。브 brief 允许这个取舍（"二选一，你判断哪种更简单
   可靠"），但值得在试点报告里如实记录是否发生过遗忘。
4. 本轮未触碰 `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`——该
   spec 文档里仍有多处 `work/lanes/` 字样（§3.1/§3.3/§5.1/§8），是 C2 迁移
   前的原始设计文本。brief 的 C2 修法清单明确只列了 5 项（`lane_setup.py`、
   `.gitignore`、`mv`、重出计划、`lane_setup.py`+`translator_cc.md` 的
   docstring/路径基准节），未列 spec 文档本身，判断为有意保留（spec 是
   历史设计记录，不因后续实现调整而回改）——但如实记在这里，供复核者
   确认这个判断。
