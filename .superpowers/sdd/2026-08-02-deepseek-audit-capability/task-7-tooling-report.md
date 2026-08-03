# Task 7 工装修复报告：add_patch 车道护栏 + 审计 --max-rounds/定点重跑

- 起点 HEAD `50faf6d`（436 passed）→ 终点 `dc82f8b`，**454 passed**（+18）
- commit：`fc023fc`（一）／`dc82f8b`（二）
- 改动文件：`tools/add_patch.py`、`tests/test_patch_recall.py`、
  `tools/audit_notes_promises.py`、`tests/test_audit_notes_promises.py`
- 全程零真实 API 调用（测试一律注入假 runner；真实数据核对也用假 verify）

---

## 一、`add_patch.py`：车道模式下缺省数据目录 → 拒绝执行

### 修法

CLI 层新增两个函数，闸设在 `main()` 里、`add()` 被调用之前：

- `lane_data_dirs(repo=None)`：列出 `pilot/lanes/*/data/`。判据取**目录存在**而
  非 `patches.jsonl` 存在——还没落过补丁的车道（如现在的 fable）恰恰最危险：第
  一条补丁写错地方，连「文件本来就在那儿」这种事后线索都没有。
- `resolve_data_dir(explicit, repo=None, env=None)`：`--data-dir` 优先；否则
  `ZND_DATA` 视同显式选定（生产命令形态 `ZND_DATA=<lane>/data uv run python …`
  正是如此，此时 `pipelib.DATA` 已指向车道）；两者皆无且检测到车道 → 抛
  `SystemExit`，**在任何文件被创建之前**。

拒绝信息直接给可照抄的路径（实测输出）：

```
拒绝执行：本仓库处于车道模式，但没有显式指定数据目录。
缺省会写进主仓 …/data/patches.jsonl——生产补丁写在那里不会生效，
而且不会有任何报错（2026-08-02 已经这样丢过 4 条回改）。
请显式选择其一：
    --data-dir …/pilot/lanes/fable/data
    --data-dir …/pilot/lanes/opus/data
  或用环境变量：ZND_DATA=<车道>/data uv run python tools/add_patch.py ...
  确实要写主仓请显式写出：--data-dir …/data
```

成功路径新增一行 stdout 回执（`已追加 1 条 patch（id=N）→ <路径>`）——事故当天
「命令没报错」之所以能骗过人，一半原因是它成功时也什么都不说。

### 「非车道用法是否被弄坏」的核实结论

**没有弄坏。** 三条证据：

1. **调用面清点**：全仓 grep `add_patch`，除计划文档外只有一个导入方——
   `tests/test_patch_recall.py:2 from tools.add_patch import add`，且它显式传
   `data=`。没有任何工具/脚本以库形式调用 `add()`，也没有任何脚本以缺省
   `--data-dir` 调 CLI。
2. **闸只在 CLI**：`add()` 签名与语义（含 `data=None` 时落 `DATA`）一字未动，
   程序化调用方完全不受影响（`test_add_patch_library_add_unaffected_by_guard`）。
3. **非车道仓库行为不变**：仓库里没有 `pilot/lanes/*/data/` 时缺省照旧落 `DATA`
   （`test_add_patch_non_lane_repo_keeps_default_behaviour`）。而在**本**仓库
   （车道模式）里，主仓 `data/patches.jsonl` 事故前根本不存在、事故后已被清掉——
   即主仓补丁路径从来没有过真实用法，拒绝它不阻断任何既有工作流；真要写也留了
   `--data-dir <repo>/data` 这个显式出口。

### 新增测试（6 条，`tests/test_patch_recall.py`）

`refuses_in_lane_mode_without_data_dir`（拒绝 + **一个文件都没新增**，逐文件比对
`rglob` 前后快照）／`writes_when_data_dir_explicit_in_lane_mode`（正常写入车道且
不碰主仓）／`accepts_znd_data_as_explicit_choice`／
`non_lane_repo_keeps_default_behaviour`／`lane_dirs_listed_in_refusal`（多车道全
列出）／`library_add_unaffected_by_guard`。

---

## 二、`audit_notes_promises.py`：`--max-rounds` + 定点重跑

### (a) `--max-rounds N`

`_rounds_kw(max_rounds)` → `{}` if None else `{"max_rounds": n}`，透传进
`extract_promises` 与 `verify_promise`，最终落到 `run_with_tools` 的 kwargs。
**省略时不传该 kwarg**，默认仍由 `run_with_tools` 自己的 6 决定（传 `None` 会把
默认覆写成 `None`，`while rounds < None` 直接 TypeError——这一点有专门测试钉住）。
抽取阶段一并可调，因为首轮里抽取阶段同样撞过轮次预算。

**四条机械闸一字未动**：提高预算只是给模型更多轮次，闸的语义（`stopped_reason
!= finished` / `tool_errors` / 开了工具没调 / 预拼取回全无译文）不变。

### (b) 定点重跑 `--rerun-from`

```
uv run python tools/audit_notes_promises.py \
  --rerun-from work/out/audit-s3s.jsonl \
  --out work/out/audit-s3s-rerun.md \
  --max-rounds 16 \
  --lane-dir pilot/lanes/opus \
  [--rerun-gates max_rounds|all]
```

- `load_sidecar(path)` → `(results, extraction_failures)`；坏行（进程被杀留下的
  半截末行）跳过并 stderr 留痕，不因一行坏 JSON 拒绝启动。
- `is_gated(row, gates="max_rounds")`：`verdict == "无法判断"` 且 reason 含
  `机械闸`；默认再要求含 `max_rounds`（预算一族），`gates="all"` 放宽到四闸全部。
  **模型自判的「无法判断」永不入选**——那是证据不足，重跑只是再花一次钱。
- `rerun_gated(...) -> (merged, reran)`：`merged` 与输入**等长同序**，未选中的
  条目原样搬运（连对象身份都不变），选中的替换后补回 `proposal`/`promise`，并加
  `rerun_of` / `rerun_prev_reason` 让两轮可对比。单条抛异常照旧降级成一条可见的
  「无法判断」（复用 `_forced_cannot_tell`），不因重跑丢记录。`main` 里另有
  `assert len(merged) == len(results)` 兜底。
- **不覆盖原 sidecar**：`--out` 推出的新 sidecar 若 `resolve()` 等于
  `--rerun-from`，在 `write_text("")` 之前拒绝执行并给出建议文件名。不靠人记得
  先手工备份。旧的 `extraction_failure` 条目也会搬进新 sidecar，故新 sidecar 可
  直接当下一轮重跑的输入。

### 真实数据核对（只读，未改动 `work/out/`）

`load_sidecar` + `is_gated` 扫全部生产 sidecar：

| 文件 | results | 抽取失败 | 命中闸(max_rounds) | 命中闸(all) | 无法判断 |
|---|---|---|---|---|---|
| audit-s1s | 120 | 0 | 0 | 0 | 6 |
| audit-s2f | 34 | 0 | 0 | 1 | 2 |
| audit-s2s | 397 | 1 | 9 | 11 | 29 |
| audit-s3s | 413 | 3 | 27 | 28 | 50 |
| audit-sys | 8 | 0 | 0 | 0 | 0 |
| audit-notes-promises（≡ part1 副本） | 535 | 1 | 13 | 13 | 27 |

三大章 9+27+13 = 49，与「48 条 max_rounds」的口径吻合。s3s 全量重跑 2h48m，定点
重跑只需重验 27 条。

假 verify 的端到端干跑（`--rerun-from work/out/audit-s3s.jsonl --max-rounds 16`，
产物写 scratchpad）：413 条结果一条不少，命中闸 27 条全部收到 `max_rounds=16`，
源文件 sha256 前后一致。

### 新增测试（12 条）

透传：`verify_passes_max_rounds_to_run_with_tools`（假 runner 断言收到的 kwargs）／
`max_rounds_reaches_tool_fallback_path_too`／`omitted_keeps_run_with_tools_default`
（断言 kwargs 里**没有** `max_rounds`）／`extract_promises_passes_max_rounds`。
筛选：`is_gated_selects_only_budget_exhaustion_by_default`（对预算闸/工具闸/
证据不足/已履行四类各断言，含 `gates="all"` 的放宽面）／`load_sidecar_splits_…`
（含坏行）。合并：`rerun_merges_without_losing_any_row`（数量、顺序、未选中对象
身份、`rerun_of` 留痕）／`rerun_passes_max_rounds_to_verify`／
`rerun_survives_verify_raising`。端到端：`main_rerun_from_sidecar_end_to_end`
（只重验 1 条、源字节不变、3 条硬承诺与 1 条抽取失败全在新报告与新 sidecar 里）／
`main_rerun_refuses_to_overwrite_source_sidecar`／`main_rerun_gates_all_widens_selection`。

### 顺带的必要改动

原有 4 个 `fake_extract` / 3 个 `fake_verify` 测试替身补上了 `max_rounds=None`
形参——真函数签名变了，替身必须跟着变，否则它们只是在测一个已不存在的接口
（不补会因 TypeError 被异常隔离吞成「抽取失败」，测试红）。

---

## 顾虑

1. **`is_gated` 按 reason 字符串字面匹配**（`机械闸`、`max_rounds`）。它与
   `verify_promise` 里生成那串文案的那行是一对，改其一必须改其二；代码里已写下
   这条注释，但没有机械约束。更硬的做法是往结果里存结构化的 `gate` 字段，但那会
   改变 sidecar schema、让**已有的**生产 sidecar 无法被重跑——本次刻意不做。
2. **重跑不重新解析手记**：`proposal`/`promise` 全部来自旧 sidecar。若期间手记被
   编辑过，重跑核的仍是旧文本。这是「定点」的应有之义（要跟进新手记就该全量重
   跑），但用的时候心里要有数。
3. **重跑不改抽取阶段的失败**：抽取阶段撞 `max_rounds` 的提案（sidecar 里是
   `extraction_failure`，reason 形如 `stopped_reason=max_rounds`）只被原样搬运，
   不会被重新抽取——重新抽取会产出**新的承诺条目**，那就不是「等长同序合并」而
   是一次局部全量跑了。这些提案要捡回来，目前只能对该章全量重跑（带大
   `--max-rounds`）。s3s 有 3 条这样的提案。
4. **`--max-rounds` 调大直接放大单条成本上限**（真实计费）。建议先在小 `--limit`
   或单章上试 16，看 flip 率再决定是否推广。
