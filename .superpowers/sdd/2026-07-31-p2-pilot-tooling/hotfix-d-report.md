# Hotfix D 报告：终任务章别文案 + check_batch 车道化，并重生成两份试点计划

## 摘要

Task 8 集成评审在真实产出的 `translate-pilot-opus.md` 上发现两条前序任务代码的既有缺陷（均非 Task 8 自身源码问题）：

1. `tools/gen_plan.py` 的 `_final_task()` 把 `--batches` 模式下的 `label`（计划名，如 `pilot-opus`）当章别用，导致终任务 Step 1 文案指向一个不存在的「pilot-opus 章节梗概卡」。
2. `tools/check_batch.py` 的 `main()` 恒读仓库根 `glossary/`，不随 `--lane-dir` 走，破坏了 70 批跨会话试点期间术语校验基准应有的「冻结」属性（两条车道读的是同一份文件，不产生 A/B 偏袒；被破坏的是同一份文件在试点期间可能被改动，导致早晚批次基准不一致，且与 `pilot-manifest.json` 记录的哈希对不上）。

两条缺陷均已修复、补测试、全绿；两份执行计划已用修复后的生成器重出，四项自查全部通过。

---

## 缺陷 1：`_final_task` 章别文案

### 落地位置

- `tools/gen_plan.py`：
  - `_paths()`：无改动（此缺陷不涉及路径表）。
  - `_final_task(tnum, chapters, lane, first, last, count, p)`：形参 `chapter` 改名为 `chapters`，改收「本计划全部批次涉及的真实章别集合」（去重排序的 list），不再收 `label`。内部按 `len(chapters) == 1` 分两支：
    - 单章（含 `--chapter` 模式）：措辞与改动前逐字一致（「对照本章对应的章节梗概卡……」）。
    - 跨章别（`--batches` 连续段模式常见情形）：改为「对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 `{ch_str}` 各章对应卡……）与本车道刚入库的 `{forward}`」，并追加加粗提示：「**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**」
  - `render()`：调用处从 `_final_task(tnum, label, ...)` 改为先算出 `chapters_all = sorted({b["chapter"] for b in sel})` 再传入 `_final_task(tnum, chapters_all, ...)`——与 `_checkpoint_task` 对每个 chunk 算 `chapters` 的写法同规格，只是作用域是整个 `sel` 而非单个 chunk。

### TDD Evidence

RED（新增两条断言 + 一条既有测试新增断言，均先失败）：

```
$ uv run pytest -q tests/test_gen_plan.py::test_final_task_lists_real_chapters_not_label \
    tests/test_gen_plan.py::test_final_task_flags_partial_chapter_coverage_in_cross_chapter_mode \
    tests/test_gen_plan.py::test_checkpoint_and_final_stay_natural_in_single_chapter_mode
...
FAILED tests/test_gen_plan.py::test_final_task_lists_real_chapters_not_label
FAILED tests/test_gen_plan.py::test_final_task_flags_partial_chapter_coverage_in_cross_chapter_mode
3 failed / 触发原因：旧 `_final_task` 用 label 拼文案，chapters 断言全部落空
```
（完整批量红测证据见下方联合 RED 记录，缺陷 1 与缺陷 2 的新增测试一起跑的红测在同一条命令里，见「联合 RED」节。）

GREEN：

```
$ uv run pytest -q
........................................................................ [ 41%]
........................................................................ [ 83%]
.............................                                            [100%]
173 passed in 2.55s
```

### 新增测试

`tests/test_gen_plan.py`：
- `test_final_task_lists_real_chapters_not_label`：跨章别 fixture（s0f/crd/s1s/sys）下，终任务文案列出全部 4 个真实章别，且不出现 label（`pilot-opus`）。
- `test_final_task_flags_partial_chapter_coverage_in_cross_chapter_mode`：同一 fixture 下断言出现「timeline 连续段」与「整章完结」两处关键措辞。
- 扩展 `test_checkpoint_and_final_stay_natural_in_single_chapter_mode`：新增断言 `--chapter` 单章模式下终任务 Step 1 仍是「对照本章对应的章节梗概卡」且不出现「timeline 连续段」——回归闸，锁死单章模式文案不因新逻辑变啰嗦。

---

## 缺陷 2：`check_batch.py` 车道化

### 落地位置

- `tools/check_batch.py` `main()`：
  - 新增 CLI 参数 `--lane-dir`（`default=None`），与 `tools/detect_collapse.py` 同名同义。
  - `groot = Path(args.lane_dir) if args.lane_dir else REPO`；`sp, gl` 从 `groot / "glossary" / ...` 派生（原先硬编码 `REPO / "glossary" / ...`）。省略 `--lane-dir` 时 `groot == REPO`，与改动前完全一致（逐字回归）。
- `tools/gen_plan.py`：
  - `_paths()` 新增键 `lane_dir_arg`：非车道模式为空串，车道模式为 `f" --lane-dir {d}"`。
  - `_batch_task()` 的 Step 3 命令行改为 `` `{p["env"]}uv run python tools/check_batch.py --batch {n}{p["lane_dir_arg"]}` ``——非车道模式下 `lane_dir_arg` 为空串，命令与之前逐字一致；车道模式下追加 `--lane-dir <lane_dir>`。

### TDD Evidence

联合 RED（缺陷 1 + 缺陷 2 的全部新增测试一次性收集，改代码前跑）：

```
$ uv run pytest -q tests/test_gen_plan.py tests/test_check_batch.py
...
FAILED tests/test_gen_plan.py::test_final_task_lists_real_chapters_not_label
FAILED tests/test_gen_plan.py::test_final_task_flags_partial_chapter_coverage_in_cross_chapter_mode
FAILED tests/test_gen_plan.py::test_lane_cfg_check_batch_step_includes_lane_dir
FAILED tests/test_check_batch.py::test_lane_dir_glossary_drives_w2 - SystemExit: 2（argparse: unrecognized arguments: --lane-dir）
FAILED tests/test_check_batch.py::test_lane_dir_does_not_fall_back_to_repo_root - SystemExit: 2（同上）
5 failed, 30 passed in 0.27s
```

实现后 GREEN（见上方联合 GREEN：`173 passed`）。

### 突变验证

按 brief 要求，把 `--lane-dir` 分支临时改回恒读 `REPO`：

```python
groot = REPO  # MUTATION: temporarily ignore --lane-dir to verify test discriminates
```

```
$ uv run pytest -q tests/test_check_batch.py -k "lane_dir"
FAILED tests/test_check_batch.py::test_lane_dir_glossary_drives_w2
    AssertionError: {'hard': [], 'warn': []}
    assert False
     +  where False = any(...)
FAILED tests/test_check_batch.py::test_lane_dir_does_not_fall_back_to_repo_root
    AssertionError: {'hard': [], 'warn': [{'id': 601, 'rule': 'W2', 'msg': '「コックリさん」未按定译「钱仙」'}]}
    assert not True
2 failed, 1 passed, 12 deselected in 0.05s
```

两个用真实判别力设计的测试（车道词表专属术语触发 W2；空车道目录不应静默退回仓库根）均转红，确认它们确实在检验 `--lane-dir` 分支本身，不是摆设。第三个测试（`test_no_lane_dir_reads_repo_root_glossary`，回归闸）在突变下仍绿——符合预期，因为该测试本就不传 `--lane-dir`，突变（恒读 REPO）与原实现在这条路径上行为一致。

还原后再次全绿：

```
$ uv run pytest -q
173 passed in 2.55s
```

### 新增测试

`tests/test_check_batch.py`：
- `test_lane_dir_glossary_drives_w2`：`--lane-dir` 指向含自定义 `active.json`（含一个仓库根词表里绝对没有的术语 `＠车道试验术语＠`）的临时目录，W2 按该目录判定并触发。
- `test_no_lane_dir_reads_repo_root_glossary`：不给 `--lane-dir` 时仍读仓库根真实词表（用仓库根已有的「コックリさん→钱仙」造判别力），回归闸。
- `test_lane_dir_does_not_fall_back_to_repo_root`：给了 `--lane-dir` 但该目录没有 `glossary/` 时，不静默退回仓库根（用仓库根词表里确有判别力的术语验证不触发 W2）。

`tests/test_gen_plan.py`：
- `test_lane_cfg_check_batch_step_includes_lane_dir`：车道模式下 Step 3 命令含 `--lane-dir work/lanes/opus`。
- `test_no_lane_cfg_check_batch_step_has_no_lane_dir`：非车道模式下 Step 3 命令不含 `--lane-dir`（回归闸）。

---

## 两份计划重生成

```bash
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-opus \
  --lane-dir work/lanes/opus --model opus --effort max --append-model-id claude-opus-5
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-fable \
  --lane-dir work/lanes/fable --model fable --effort high --append-model-id claude-fable-5
```

输出：
```
.../docs/superpowers/plans/translate-pilot-opus.md: 43 个任务
.../docs/superpowers/plans/translate-pilot-fable.md: 43 个任务
```

### 四项自查（实际输出）

1. **两份计划仍各 43 个任务**——`grep -c '### Task'`：opus=43，fable=43。✓

2. **终任务 Step 1 列出真实章别、不含 label 作为章别**——摘录 `translate-pilot-opus.md` Task 43：
   > crd、s0f、s1f、s1s、s2s、sys 章 main 车道全部 35 个批次（1–35）已入库 `work/lanes/opus/data/forward.jsonl`。收尾前做两件事：
   >
   > - [ ] **Step 1: 梗概回译自检**
   >
   > 对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 crd、s0f、s1f、s1s、s2s、sys 各章对应卡……）与本车道刚入库的 `work/lanes/opus/data/forward.jsonl`：……**注意本段是 timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按「整章完结」的标准要求梗概吻合。**

   Task 43 段落内 `grep -c pilot-opus` = 0。✓

3. **每个批次任务的 Step 3 命令都带 `--lane-dir <本车道>`**——`grep -c 'check_batch.py --batch .* --lane-dir work/lanes/opus'` = 35（35 个批次任务全覆盖）；fable 计划同理 = 35。✓

4. **车道隔离**——`grep -c 'work/lanes/fable' translate-pilot-opus.md` = 0；`grep -c 'work/lanes/opus' translate-pilot-fable.md` = 0。✓

---

## Files Changed

- `tools/gen_plan.py`：`_paths()` 新增 `lane_dir_arg`；`_batch_task()` Step 3 命令追加该键；`_final_task()` 签名与内容重写（`chapter`→`chapters`，单章/跨章别分支）；`render()` 调用处改传真实章别集合。
- `tools/check_batch.py`：`main()` 新增 `--lane-dir` 参数，`groot` 替代硬编码 `REPO` 作为 glossary 读取根。
- `tests/test_gen_plan.py`：新增 5 条测试（缺陷 1 两条 + 缺陷 2 两条 + 扩展一条既有测试）。
- `tests/test_check_batch.py`：新增 3 条测试（缺陷 2）+ 顶部新增 `import json` 与 `write_jsonl`/`main` 引用。
- `docs/superpowers/plans/translate-pilot-opus.md`：用修复后的生成器重出（43 任务）。
- `docs/superpowers/plans/translate-pilot-fable.md`：用修复后的生成器重出（43 任务）。

## 验证清单

- 全量 `uv run pytest -q`：173 passed（改动前 166 passed，净增 7 条新测试全绿）。
- 突变验证：命令与红色输出见上方「突变验证」节，验证后已还原，`git diff tools/check_batch.py` 只剩正式修复。
- `work/lanes/` 下两条真实车道（opus/fable）未被改动：`git ls-files work/lanes/` 为空（`work/` 整体 gitignore，非 git 管控范围）；额外用 `find work/lanes -maxdepth 3 -newer tools/check_batch.py` 核实重跑 `gen_plan.py` 前后车道目录内文件 mtime 均早于本次代码改动，无文件被触碰。
- 最终 `git status --short`：
  ```
   M .superpowers/sdd/2026-07-31-p2-pilot-tooling/progress.md
   M docs/superpowers/plans/translate-pilot-fable.md
   M docs/superpowers/plans/translate-pilot-opus.md
   M tests/test_check_batch.py
   M tests/test_gen_plan.py
   M tools/check_batch.py
   M tools/gen_plan.py
  ```
  与 brief 预期的文件集合完全一致（`progress.md` 为协调者拥有，未改动其内容，仅保留其在本会话开场即已存在的未提交状态）。

## Self-Review

- **Completeness**：两条缺陷各自修复 + 补测试均完成；两份计划重生成并通过 brief 列的四项自查（见上）。
- **Quality**：`_final_task` 在 `--chapter` 单章模式下文案与改动前逐字一致（`test_checkpoint_and_final_stay_natural_in_single_chapter_mode` 扩展断言覆盖）；`check_batch.py` 省略 `--lane-dir` 时行为回归闸（`test_no_lane_dir_reads_repo_root_glossary`）绿。
- **Discipline**：未触碰 `work/lanes/` 下任何真实车道文件；未改动除 brief 列出的两个工具文件外的其它 `tools/*.py`；未新增第三方依赖（`argparse`/`pathlib`/`json` 均为标准库或已在文件内导入）。
- **Testing**：先红后绿证据完整（联合 RED 5 failed → 联合 GREEN 173 passed）；突变验证做了且证据完整；全量套件无回归（166→173，无既有测试变红）。

## Concerns

- 无重大遗留问题。唯一值得注意的措辞取舍：`_final_task` 是否要用「本段」还是继续用「本车道」指代 forward 文件位置——采用了 brief 参考表述里的「本车道刚入库的 `<lane>/data/forward.jsonl`」写法（跨章别分支），单章分支保留原「本章刚入库的」写法，两者语义边界清晰（前者强调车道产物文件本身，后者强调该章节范围），未见歧义。
- 缺陷 2 的注释与本报告均按 brief 要求的口径表述："不产生 A/B 之间的偏袒，破坏的是冻结属性"，未夸大为车道间会互相污染。
