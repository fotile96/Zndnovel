# Task 2 Report: 词族饱和度计算器

## 执行摘要

成功实现了词族饱和度计算器模块，用于计算某个日文词在全书 ledger 里的出现次数中，已被翻译过的批次覆盖的比例。该工具作为段末小裁决的证据闸门，仅当饱和度达到阈值（默认 0.8）时允许术语裁决，否则聚类滚存。

## 实现步骤

### Step 1: 写失败测试
创建 `tests/test_saturation.py`，包含三个测试用例：
1. `test_saturation_counts_occurrences_not_rows()`：验证按词出现次数计数（一行多次按多次计）
2. `test_saturation_zero_occurrence_term()`：验证零出现词的处理（ratio 返回 None）
3. `test_main_reads_data_dir_and_gates()`：验证 CLI 入口、数据目录覆盖、阈值门控

### Step 2: 确认失败
```bash
uv run pytest tests/test_saturation.py -v
```
结果：`ModuleNotFoundError: No module named 'tools.saturation'`（预期）

### Step 3: 写实现
创建 `tools/saturation.py`，主要接口：
- **`saturation(term, ledger_rows, done_ids) -> dict`**：
  - `total`：词在全 ledger 中的出现总次数（sum of count）
  - `covered`：已译行中词的出现次数
  - `ratio`：覆盖比（covered/total，总数为 0 时为 None）
  - `uncovered_by_chapter`：未覆盖分布（按 chapter 汇总）

- **`main(argv) -> int`**：CLI 入口
  - 支持 `--term <词>` 多指定、`--terms-file <路径>` 批量读取
  - `--data-dir <路径>` 覆盖 DATA 默认值
  - `--gate <阈值>` 设置裁决门槛（默认 0.8）
  - 输出 markdown 表格，按饱和度排序（ratio None 优先，然后按值升序）

**关键实现细节**：
- 处理了 ledger_extra.jsonl 的异构格式：主 ledger 用 `id` 整数，extra 用 `key` 字符串
- 依赖 `resolve_map(forward_rows, patch_rows)` 获取已译 id 集合
- 同时读取 ledger.jsonl + ledger_extra.jsonl（若存在）

### Step 4: 确认单元测试通过
```bash
uv run pytest tests/test_saturation.py -v
```
结果：
```
test_saturation_counts_occurrences_not_rows PASSED
test_saturation_zero_occurrence_term PASSED
test_main_reads_data_dir_and_gates PASSED
===== 3 passed =====
```

### Step 5: 真实数据冒烟测试
```bash
uv run python tools/saturation.py --term 十円玉 --term 消しゴム --term 浜千鳥 --data-dir pilot/lanes/opus/data
```

**实际输出**：
```
| 词 | 出现 | 已覆盖 | 饱和度 | 判定 | 未覆盖分布 |
|---|---|---|---|---|---|
| 浜千鳥 | 3 | 0 | 0.000 | 滚存 | e2f:1 s5s:1 s8f:1 |
| 消しゴム | 57 | 15 | 0.263 | 滚存 | ?:4 crd:17 e2f:1 s2f:1 s2s:2 s3s:7 s4s:6 s5f:1 s6s:1 s7f:2 |
| 十円玉 | 12 | 12 | 1.000 | 可裁决 | - |
```

**冒烟结果验证**：✓
- 十円玉：12/12 出现，饱和度 1.000，判定「可裁决」（符合预期）
- 其他词正确按阈值（0.8）分类为「滚存」
- 未覆盖分布清晰展示各章节缺口

### Step 6: 全量测试
```bash
uv run pytest -q
```

结果：**214 passed**（符合预期基线 211 + 3 新测试）

### Commit
```bash
git add tools/saturation.py tests/test_saturation.py
git commit -m "feat: 词族饱和度计算器（段末裁决证据闸门）"
```

Commit hash: `5480681`

## 设计要点

1. **词族 vs 行**：按词出现次数计（一行多次按多次计），而非按行计。这与游戏内『あらすじ』多次提及术语的场景一致。

2. **异构数据处理**：代码兼容 ledger.jsonl（`id` 整数）和 ledger_extra.jsonl（`key` 字符串）的混用。

3. **已译集合确定**：`done_ids = set(resolve_map(forward_rows, patch_rows).keys())`，包含所有已翻译行（无论 id 类型）。

4. **闸门与决策**：
   - `ratio >= gate` → 可裁决（证据充足）
   - `ratio < gate` → 滚存（证据不足，等待后续批次补充）
   - `ratio is None` → 无出现（特殊情况，单列展示）

5. **输出排序**：ratio None 优先（无出现），然后按覆盖比升序排列，便于快速定位低饱和度词。

## 后续使用

段末裁决会话（runbook）可调用：
```bash
uv run python tools/saturation.py --terms-file <聚类词表> --data-dir <数据目录> --gate 0.8
```

仅对 `判定=可裁决` 的词族展开形态变体与近似词查重、集群细化等深层决策。

## 自查结论

✓ 代码逻辑正确，单元测试覆盖充分  
✓ 冒烟测试数据完整，十円玉 符合预期 1.000 饱和度  
✓ 全量测试达成 214 passed 目标  
✓ 实现代码与 brief 逐字一致，仅在数据格式适配上加了兼容性处理  
✓ Commit 规范正确，仅涉及两个指定文件  

**状态**：DONE
