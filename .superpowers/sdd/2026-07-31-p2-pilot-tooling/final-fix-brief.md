# 终审修复波：2 Critical + 6 Important + 2 顺手 minor

最终全分支评审判定「不建议直接开跑」。工具本身称职，问题集中在**唯一会被真正执行的产物**（两份执行计划）与几处安全网覆盖。本轮一次性修完，之后只做一次范围内再评审。

**总原则**：能由生成器产出的就改生成器再重出计划，不要手改那两份 md（手改会让它们不再可重现，P3 还要用同一套生成器）。

---

## C1（Critical）四道验收闸门在计划里零出现

实证：`grep -c` 于 `docs/superpowers/plans/translate-pilot-opus.md` —— `detect_collapse`=0、`隔离验收`=0、`硬停`=0、`lane_setup`=0、`--verify`=0、`窗口对撞`=0。

spec 要求而计划未承载的四道闸门：
- §3.3 隔离验收（batch 1 完成后立即执行，不通过则**停止试点**）
- §5.2 batch 1、2 后各硬停一次（人机双查 + 崩溃阈值标定）
- §6.3 每批 `check_batch` 之后再跑一道语义崩溃探测
- §3.3 每批派发前校验冻结未漂移

### 修法（改 `tools/gen_plan.py`，车道模式下生效；非车道模式输出保持不变）

1. **逐批崩溃探测**：`_batch_task` 在 Step 3（check_batch）与 Step 4（append_forward）之间插一个步骤，跑
   `{p["env"]}uv run python tools/detect_collapse.py --batch {n} --lane-dir {lane_dir}`
   并说明它是顾问级（恒返回 0）：hard 无、但 C1/C2/C3 有命中时要人眼过一遍再入线，命中数记进本批记录。
2. **每检查点先校验冻结**：`_checkpoint_task` 的最前面加一步 `uv run python tools/lane_setup.py --verify`，Expected「冻结校验：无漂移」；漂移则**停止试点**并报人。
3. **batch 1 / batch 2 后的硬停任务**：车道模式下，在第 1 个和第 2 个批次任务之后各插入一个 `### Task N: 硬停——…` 任务，内容分别为：
   - batch 1 后：①隔离验收——两条车道的 `forward.jsonl` 内容必须不同；两条车道 batch 2 的 `context.md` 第二节前缀正文必须各自含**本车道** batch 1 的译文（给出可跑的命令）②`lane_setup --verify` 无漂移 ③人工抽读本批译文 ④**不通过则停止试点**。
   - batch 2 后：①用已有的两批真实译文标定 `detect_collapse` 的三个阈值（`--kana-max/--ratio-lo/--ratio-hi`），把标定结果**写进 `pilot/lanes/pilot-manifest.json`** 并据此固化到后续批次的命令行（见下 §I-extra）②人工抽读 ③崩溃探测在两批上的命中逐条过目。
4. **窗口对撞探针任务**：在最后一个批次任务（batch 35）之后、终任务之前，插一个探针任务：在 batch 33 **已入线之后**执行，用 `--repo` 指向一份临时车道副本（避免覆盖正式产物，见 I6），对同一批分别以 `--profile cc` 与 `--profile api-A` 生成上下文并并排人工比对，结论写进试点报告。

上述新增任务参与任务编号，故两份计划的任务数会从 43 变为 **47**（43 + 2 硬停 + 1 探针 + 1 …按你实际插入数为准，报告里写清最终数）。

---

## C2（Critical）车道译文存放：移出 `work/`

实证：`git check-ignore -v work/lanes/opus/data/forward.jsonl` → `.gitignore:15:work/`；两份计划共 70 处 `git add work/lanes/...` 均会失败。8564 行译文（约 6.6M token 成本）无任何备份，且 spec §8 把「逐批 commit 历史」列为产出物。

**用户裁定**：车道根从 `work/lanes/` 移到 **`pilot/lanes/`**，只把车道内的中间产物 gitignore 掉，译文线正常入库。

### 修法

1. `tools/lane_setup.py` 的 `LANES_ROOT` 由 `WORK / "lanes"` 改为 `REPO / "pilot" / "lanes"`。
2. `.gitignore` 增加（注意顺序与否定规则）：
   ```
   pilot/lanes/*/work/
   pilot/lanes/*/skeleton/
   pilot/lanes/*/glossary/
   pilot/lanes/*/data/*
   !pilot/lanes/*/data/forward.jsonl
   !pilot/lanes/*/data/patches.jsonl
   ```
   即：**入库** `lane.json`、`data/forward.jsonl`、`data/patches.jsonl`、`pilot/lanes/pilot-manifest.json`；**不入库** 车道内的 `work/` 中间产物、`skeleton/`+`glossary/` 冻结拷贝（体量大且可由 manifest 哈希追溯）、`data/` 下指向仓库的符号链接。
3. 把现有两条真实车道从 `work/lanes/` **物理移动**到 `pilot/lanes/`（`mv`，不要重建——重建会刷新冻结快照，破坏已记录的 manifest 基准）。移动后跑 `uv run python tools/lane_setup.py --verify` 确认仍「无漂移」。
4. 重出两份计划（`--lane-dir pilot/lanes/{opus,fable}`），确认 Step 4 的 `git add` 指向 `pilot/lanes/...` 且不再被 ignore（`git check-ignore` 应无输出）。
5. 更新 `tools/lane_setup.py` 模块 docstring 与 `prompts/translator_cc.md`「路径基准」节里出现的 `work/lanes` 字样。

---

## I1 `stratified_sample` 位置退化，盲评看不到后半段

`tools/compare_lanes.py` 每层取 `buckets[kind][:per_kind]`（id 升序前 N）。实测：默认 `per_kind=20` 出 100 行只覆盖 35 批中的 6 批、最大批号 29；`batch 33–35`（压缩窗口生效后）在任何取值下都进不了盲评材料——而「压缩触发瞬间是否丢信息」正是试点要回答的问题之一。

修法：每层内**等距取样**而非取前 N（如 `bucket[::max(1, len(bucket)//per_kind)][:per_kind]`），或分层键改为 `(unit_kind, batch)`。补一条测试断言样本**同时覆盖首批与末批**的 id。

## I2 gen_plan 的车道断言又是假防护（评审已突变实证）

删掉 `_batch_task` 里 append_forward 那行的 `{p["env"]}` 后，`tests/test_gen_plan.py` **20/20 仍全绿**——因为 `test_lane_cfg_rewrites_every_path_to_lane_root` 只断言 `ZND_WORK=… ZND_DATA=…` 在**全文**出现过，而 Step 3 已经提供了这一次。该突变若为真，两条车道的 `append_forward` 都会写进仓库根 `data/forward.jsonl`，A/B 合并成一锅、试点作废。

修法：改为**按 Step 粒度断言整条命令行**，例如 `assert f'{env}uv run python tools/append_forward.py --batch 1 ' in md`（Step 3 的 check_batch 同理）。**必做突变验证**：删掉 append_forward 那处 `{p["env"]}`，确认新断言转红。

## I3 `translator_cc.md` 未随 Hotfix D 同步

- 自查命令仍是 `uv run python tools/check_batch.py --batch N`，缺 `--lane-dir`——译者读仓库根词表、控制器复检读车道冻结快照，冻结破口换了个执行主体。改为带 `--lane-dir <车道根>`，并在「路径基准」节补一句：校验命令除环境变量前缀外还须带 `--lane-dir`。
- 第 41、43 行仍称 context 第四节为「四、术语与风格」，T2 已改名「四、术语、风格与角色口调」——同步。
- **顺手修**（终审分诊为"开跑前顺手修"）：「两种写法都不会出错（哪怕结果字节完全相同）」的「哪怕」是让步连词、逻辑反了，应为因果（如「——因为读到的本就是同一份文件」）。

## I4 冻结校验只自比不互比；compare_lanes 从仓库根读锚点

- `tools/lane_setup.py` 的 `verify()` 只拿每条车道与它自己 `record()` 时的哈希比。两条车道若在仓库 glossary 变更前后分别 `setup`，各记各的哈希，`--verify` 永远绿而两条车道的术语基准已经不同——正是 spec §0「术语泄漏 → 谁更好退化成谁先跑」要防的事。修法：`verify()` 增加一条**跨车道一致性检查**——所有车道的 `cards_zh`/`anchors`/`active`/`glossary_max` 四项必须彼此相等，不等则报漂移。补测试（两条车道冻结快照不同时必须报）。
- `tools/compare_lanes.py` 的 anchors/ledger/timeline 全取 `REPO`，锚点遵从率因此按**仓库当前** anchors 判，而非译者当时看到的冻结版。修法：anchors 改从 `--lane-a` 的冻结快照读，并与 lane-b 的比对（不等则拒绝出对照材料并报错——两条车道锚点基准不同则遵从率不可比）。

## I5 `lane_setup` 重跑会静默重冻结并覆盖基准

`setup()` 对 `skeleton/`/`glossary/` 先 `rmtree` 再从**当前仓库**拷贝；`main()` 建完无条件 `record()` 重写 manifest。试点中途任何一次重跑建车道命令都会把两条车道重新冻结到仓库当时状态并擦掉原始基准，事后无法证明有没有漂移过。

修法：`setup()` 在该车道 `data/forward.jsonl` **已存在**时拒绝执行并提示（除非显式 `--force`）；`record()` 在 manifest 已存在时改为**校验并保持**而非覆盖（要覆盖需显式 `--force`）。补测试。

## I6 窗口对撞探针破坏性

`tools/build_context.py` 的 `ctx_dir = work_root/"ctx"/f"batch_{batch}"` 不含 profile，`--profile api-A` 会原地覆盖同批的 `context.md`/`manifest.json`，写进 forward 的 `ctx_sha` 会记错。

修法：**不改产码**，在 C1 新增的探针任务里写明：探针须在 batch 33 已入线之后、且 `--repo` 指向一份**临时车道副本**（`cp -r` 出来的），跑完删除副本；正式车道的 ctx 产物不得被覆盖。

## I-extra 崩溃阈值标定值的固化去处（spec §6.3 缺口）

`detect_collapse` 有三个覆盖参数但没规定标定后写去哪、后续批次如何保证用同一组值（每批手打三个数极易漂）。修法：batch 2 硬停任务里规定把标定值写进 `pilot/lanes/pilot-manifest.json` 的一个 `collapse_thresholds` 段；`_batch_task` 生成的探测命令**从该处取值**（或在硬停任务里明确指示"若标定值与默认不同，重出两份计划使其固化进命令行"——二选一，你判断哪种更简单可靠，在报告里说明理由）。

## 顺手 minor（终审分诊为"开跑前顺手修"，边际成本为零）

- `tools/gen_plan.py` 的 `_header` 渲染出的 H1 与 Goal 仍是「pilot-opus 章（lane=main）」——同类 label-as-chapter 表述，且是执行代理读到的第一行。改为不误导的措辞（如「pilot-opus（main 车道）翻译执行计划」+ Goal 里说明这是 timeline 连续段、跨 N 个章别）。

---

## 验证要求

- 全量 `uv run pytest -q` 全绿。
- **两处突变验证**（不提交突变，命令与红色输出记进报告）：
  1. I2：删掉 append_forward 那处 `{p["env"]}`，新断言须转红。
  2. I4：把 `verify()` 的跨车道一致性检查去掉，新测试须转红。
- 重出的两份计划自查：任务数（写清最终值）、四道闸门各自出现次数 > 0、`git check-ignore pilot/lanes/opus/data/forward.jsonl` 无输出、`grep -c 'pilot/lanes/fable' translate-pilot-opus.md` = 0。
- `uv run python tools/lane_setup.py --verify` 在移动后的车道上「无漂移」。
- 最终 `git status` 干净（除协调者拥有的 `progress.md`）。

## 提交

按逻辑分 commit（工具改动 / gitignore 与车道迁移 / 计划重出 / prompt 同步），消息用 `type: 中文摘要`，结尾带 Co-Authored-By 与 Claude-Session 两行。
