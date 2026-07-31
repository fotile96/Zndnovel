# Hotfix D: 终任务章别文案 + check_batch 车道化，并重生成两份试点计划

## 背景

Task 8（集成）的评审在**真实产出的执行计划**上发现两条 Important，均为前序任务代码的既有缺陷（非 Task 8 引入，Task 8 自身源码冻结故无权修）。两条都直接影响 P2 试点的可信度，须在 35×2 批次开跑前修掉。

修完后**必须重新生成两份执行计划**——它们是 Task 8 的入库交付物，内容随本次修复而变。

---

## 缺陷 1：`_final_task` 仍把计划名当章别用

`tools/gen_plan.py` 的 `_final_task()` 收到的 `chapter` 形参在 `--batches` 模式下实际是 `label`（如 `pilot-opus`）。Task 3 的修复轮只修了 `_checkpoint_task`（改为列出 chunk 内真实章别集合）与终任务的 git-log 过滤口径，**卡片/锚点/查漏那段文案没同步**。

真实产物（`docs/superpowers/plans/translate-pilot-opus.md` 终任务 Step 1）现在写着：

> 对照本章对应的章节梗概卡（`skeleton/cards.zh/`…）与本章刚入库的 `…/forward.jsonl`：核对人物称呼…

问题：`pilot-opus` 不是章别，`skeleton/cards.zh/` 里没有"pilot-opus 的章节梗概卡"；而批次 1–35 横跨 **s0f / crd / s1s / sys / s1f / s2s** 六个章别，且其中多章并未在本段内完整跑完（s1f 只有批次 29–31，s2s 只有 33 与 35）。执行者照做会找不到卡、也不知该核对哪些章的锚点。

### 修复要求

1. 让 `_final_task` 像 `_checkpoint_task` 那样接收**本计划涉及的真实章别集合**（去重、排序），由 `render()` 从 `sel` 的各批 `chapter` 字段算出后传入。
2. Step 1 的文案改为按真实章别表述，并**明确点出"本段可能只覆盖某些章的一部分"**，避免执行者误以为该章已完结。参考表述（措辞你可自行组织，要点须齐）：

   > 对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 s0f、crd、s1s、sys、s1f、s2s 各章对应卡）与本车道刚入库的 `<lane>/data/forward.jsonl`：核对人物称呼（双层人名…）、关键道具/母题译名是否与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的地方提前泄露后续真相。**注意本段是 timeline 连续段而非完整章，某些章（如 s1f、s2s）只覆盖了一部分，不要按"整章完结"的标准要求梗概吻合。**

3. `_final_task` 介绍句里其余把 `label` 当章别读的措辞（如"{chapter} 章 {lane} 车道全部 N 个批次"）一并改为不误导的表述——`--chapter` 模式下仍应自然（该模式下章别集合恰为单元素）。
4. 补测试：
   - 跨章别 fixture 下，终任务文案列出**全部**真实章别，且不出现 label 作为章别；
   - `--chapter` 单章模式下终任务文案仍自然（既有 `test_checkpoint_and_final_stay_natural_in_single_chapter_mode` 可扩展或另加）。

---

## 缺陷 2：`check_batch.py` 不随车道走

`tools/check_batch.py` 的 `main()` 里：

```python
from tools.pipelib import REPO
...
sp, gl = REPO / "glossary" / "speakers.json", REPO / "glossary" / "active.json"
```

读的是**固定的仓库根**，与 `ZND_DATA`/车道无关。而它的两个兄弟工具都已车道化：`build_context.py` 有 `--repo <lane>`（同时切 data/skeleton/glossary 与产物落点），`detect_collapse.py` 有 `--lane-dir <lane>`（切 work 与 glossary）。

**影响澄清**（写进注释与报告时请照此口径，不要夸大）：两条车道读的是同一份仓库文件，所以**不产生 A/B 之间的偏袒**；被破坏的是**冻结**属性——试点跨多会话跑 70 个批次，期间若仓库根 `glossary/active.json` 或 `speakers.json` 被改动（例如有人违反冻结令裁决了术语提案），早期批次与后期批次的校验基准就不一致，且与 `pilot-manifest.json` 记录的哈希对不上；R2b 说话人硬规则的判定基准同理会漂移。

### 修复要求

1. 给 `tools/check_batch.py` 的 CLI 增加 `--lane-dir <dir>`（与 `detect_collapse.py` 同名同义，保持一致），指定时从 `<lane-dir>/glossary/` 读 `speakers.json` 与 `active.json`；省略时行为与现在完全一致（读仓库根）。
2. `tools/gen_plan.py` 在车道模式下让 Step 3 的 `check_batch` 命令带上 `--lane-dir <lane_dir>`（非车道模式不带，输出与现在逐字一致）。
3. 补测试：
   - `check_batch` 的 `--lane-dir` 指向一个含自定义 `glossary/active.json` 的临时目录时，W2 术语告警按**该目录**的词表判定（用一个仓库根词表里没有、而车道词表里有的词造判别力）；
   - 不给 `--lane-dir` 时仍读仓库根（回归）；
   - `gen_plan` 车道模式下生成的 Step 3 命令含 `--lane-dir`，非车道模式不含。

---

## 重新生成两份计划（本 Hotfix 的交付物之一）

上述两项改完并全绿后，重新生成：

```bash
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-opus \
  --lane-dir work/lanes/opus --model opus --effort max --append-model-id claude-opus-5
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-fable \
  --lane-dir work/lanes/fable --model fable --effort high --append-model-id claude-fable-5
```

生成后自查（把结果写进报告）：

- 两份计划仍各 **43 个任务**。
- 终任务 Step 1 现在列出真实章别、且**不含** `pilot-opus`/`pilot-fable` 作为章别。
- 每个批次任务的 Step 3 命令都带 `--lane-dir <本车道>`。
- `grep -c 'work/lanes/fable' translate-pilot-opus.md` 仍为 **0**（反之亦然）。

## 验证要求

- 全量 `uv run pytest -q` 全绿。
- **突变验证**（不提交突变）：把 `check_batch` 的 `--lane-dir` 分支临时改回恒读 `REPO`，确认新加的车道词表判别用例转红；还原后把命令与红色输出记进报告。
- 确认仓库 `work/lanes/` 下两条真实车道未被改动（本 Hotfix 只改代码与计划，不重建车道）。
- 最终 `git status` 只应有：`tools/gen_plan.py`、`tools/check_batch.py`、对应测试文件、两份重生成的计划（以及协调者拥有的 `progress.md`，不要动）。

## 提交

建议分两个 commit（工具修复与计划再生成分开，便于回溯）：

```bash
git add tools/gen_plan.py tools/check_batch.py tests/test_gen_plan.py tests/test_check_batch.py
git commit -m "fix: 终任务按真实章别表述，check_batch 支持 --lane-dir 读车道术语快照"

git add docs/superpowers/plans/translate-pilot-opus.md docs/superpowers/plans/translate-pilot-fable.md
git commit -m "data: 按修复后的生成器重出两份 P2 试点执行计划"
```
