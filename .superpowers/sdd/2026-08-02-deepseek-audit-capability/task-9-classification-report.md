# Task 9：手记「承诺-履行」审计报告的「未履行」四类归因 执行报告

状态：**完成**。改动文件：`tools/audit_notes_promises.py` +
`tests/test_audit_notes_promises.py` + `docs/superpowers/specs/
2026-08-02-deepseek-audit-capability-design.md`（新增 §4.5）+ 本报告。

## 判据（一行）

对每条「未履行」，把其 `evidence_ids` 与车道 `<lane_dir>/data/patches.jsonl` 交叉
核对：命中 `reason=recall` 标「⚠ 曾因术语裁定被召回（glossary_v=X）——若手记写于
裁定之前，此条属『手记过时』而非译文违约」；命中 `reason=review` 标「✅ 已有
review 回改（glossary_v=X）——本条可能已被处理」；`reason=polish` 或无命中不标注。
**只呈现证据，不改判 verdict，不自动归类**——报告顶部另给「真违约/比对过严/手记
过时/措辞过宽」四类判据的一句话人工分类模板，分类判断留给抽核的人。

## 实现要点

- `load_patches(lane_dir)`：读 `<lane_dir>/data/patches.jsonl`，按 id 建索引
  `{id: [patch, ...]}`。`lane_dir=None`（调用方未要求）或文件不存在都返回
  `None`——两者都不等于「查过、无命中」的空字典 `{}`，调用方据此区分「未启用」
  与「启用但无命中」。路径完全由 `lane_dir` 参数解释，不写死仓库根，与
  `check_batch.load_siblings(root)` 同惯例。
- `_patch_annotations(evidence_ids, patches)`：纯函数，只生成标注行，不touch
  verdict。
- `render_report(results, extraction_failures=None, lane_dir=None)`：新增
  `lane_dir` 形参，默认 `None` 保持向后兼容（既有 65 个调用点未传该参数，行为
  不变，不产生任何标注/播报）。传了 `lane_dir` 但 `patches.jsonl` 不存在时，在
  报告顶部**显式播报**「回改车道证据核对未执行」——同 `check_batch.py` 里 W4
  未启用时「闸没跑」与「闸跑了没报」必须可区分的纪律（commit `3c0ab9c`）。标注
  只加在 `verdict == "未履行"` 的条目下面，「已履行」条目即便依据行命中
  patches 也不标注。
- `main()` 与 `_main_rerun()` 的两处 `render_report(...)` 调用都补上
  `lane_dir=lane`——`lane` 变量在两处调用点均已在作用域内（来自 `--lane-dir`，
  默认 `pilot/lanes/opus`），无需额外解析。
- 报告顶部的人工分类模板（`CLASSIFICATION_TEMPLATE`）**恒定显示**，不依赖
  `lane_dir` 是否传入——四类判据是通用的抽核指南，不是 patches 命中才需要。

## Spec 落档

`docs/superpowers/specs/2026-08-02-deepseek-audit-capability-design.md` 新增
§4.5：四类判据表格 + 首次全量跑 6/4/1/2 实测分布、「只让机器做机器能做的」设计
判断、`patches.jsonl` 的 `reason` 语义、显式播报纪律的引用（commit `3c0ab9c`）。
另记一条已知缺口（交叉引用，未修改该文件本身，其 §5.5 已如实记录该事件）：
`docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md` §5.5
提到的「手记里写进了虚构的承诺」——现有审计只核对承诺是否被执行，不核对承诺
本身是否成立，这一类审计不到，记为能力缺口，不在本次实现范围。

## 测试

`uv run pytest -q` → **475 passed**（HEAD 基线 463 → +12）。新增合成数据测试
（不钉活的生产 `pilot/lanes/opus/data/patches.jsonl`，用 `tmp_path` 自造）：

- 顶部人工分类模板恒定出现（四类关键词都在）
- `reason=recall` 命中 → 标注含「曾因术语裁定被召回」+ `glossary_v=8` + 「手记
  过时」提示
- `reason=review` 命中 → 标注含「已有 review 回改」+ `glossary_v=9` + 「可能已
  被处理」提示
- 依据行不在 patches 里 → 不标注
- `reason=polish` → 不标注（不在两类范围内，强行归类是伪造证据）
- `lane_dir` 给了但文件缺失 → 显式播报「未执行」
- `lane_dir=None`（默认）→ 不播报「未执行」（向后兼容旧调用方式）
- 命中标注不改变 verdict / 计数
- 标注只加在「未履行」条目，「已履行」即便命中也不标
- `load_patches` 本身：文件缺失返回 `None`、`lane_dir=None` 返回 `None`、
  按 id 建索引（同 id 多条全保留）

## 变异自检（这条闸真的会响）

把触发条件 `if r["verdict"] == "未履行" and patches:` 改成
`if False and r["verdict"] == "未履行" and patches:`（标注逻辑恒不触发），
运行 `tests/test_audit_notes_promises.py`：

**精确 2 红**：`test_report_annotates_recall_hit`、
`test_report_annotates_review_hit`；其余 75 绿（含另外 10 条本任务新增测试与
全部既有测试）。已改回，改回后 `uv run pytest -q` 475 passed。

## 顾虑

1. **生产车道 `pilot/lanes/opus/data/patches.jsonl` 当前恰好只有 recall/review
   两种 reason（13 条 recall + 4 条 review，无 polish）**——spec §4.5 提到的
   "reason ∈ {review, recall, polish}" 里 polish 分支目前只有合成测试覆盖，
   未在真实数据上验证过；若未来 polish 记录出现，行为已按测试锁定（不标注）。
2. 会话期间工作树里持续有**其他并发会话的未提交改动**
   （`.superpowers/sdd/2026-08-03-p3-seg3-s4/progress.md`、
   `data/api_ledger.jsonl`、`docs/superpowers/specs/
   2026-08-03-extra-lane-collapse-design.md`、
   `pilot/lanes/opus/data/notes/s4s.md`），且执行期间主分支又多出一个
   与本任务无关的 commit（`6248c57`）。本次只 `git add` 了自己改的三个文件 +
   本报告，未触碰、未 `git add -A`。
3. 标注文案里两处 emoji（⚠/✅）与既有报告风格（`⚠ 依据行含非法项已丢弃`等）
   一致，未引入新的视觉语汇。
