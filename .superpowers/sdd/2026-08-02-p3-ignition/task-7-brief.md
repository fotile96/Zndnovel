### Task 7: 生成首段（SEG-1）生产计划

**Files:**
- Create: `docs/superpowers/plans/translate-seg1-s2.md`（gen_plan 产物）

**Interfaces:**
- Consumes: Task 4 的 `--segment`、Task 5 之后的车道 v7（gen_plan 经 `build_context.glossary_version()` 动态取 v=7）、`config/segments.yaml` 的 SEG-1（b36–62）。
- Produces: 可被 P3 生产会话直接执行的首段计划。collapse 阈值不传（P2 标定值＝默认值 kana_max 0.02 / ratio 0.40–1.50，见 pilot-manifest `collapse_thresholds`）。

- [ ] **Step 1: 生成**

```bash
uv run python tools/gen_plan.py --lane main --batches 36-62 --label seg1-s2 \
  --segment seg1-s2 --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus \
  --model opus --effort max --append-model-id claude-opus-5
```
Expected: 写出 `docs/superpowers/plans/translate-seg1-s2.md`。注意 `--lane main`——batches.jsonl 里 b36–62 的 lane 字段是 `main`（`opus` 是车道名不是 lane 字段值，P2 的计划同此用法；若 select 结果为空即是这里传错）。

- [ ] **Step 2: 人工核验生成物**

逐项确认：①头部车道配置表 model=opus/effort=max/append_model_id=claude-opus-5、lane_dir 为本机绝对路径；②「段开场自检」在批次任务前、「段末流程」在尾部、tag 名 `prod-opus-seg1-s2-done`；③glossary_v=7；④批次区间恰 36–62 共 27 批；⑤隔离纪律块存在（禁读其他车道）。

- [ ] **Step 3: commit + 点火交接**

```bash
git add docs/superpowers/plans/translate-seg1-s2.md
git commit -m "docs: SEG-1（s2 完结段，b36-62）生产计划"
```

向用户报告：点火就绪。生产会话开工方式＝新会话 + 按 `docs/ops/p3-production-runbook.md` 开场自检 + 执行 `translate-seg1-s2.md`。

---

## Self-Review 记录

- **Spec 覆盖**：spec §6「本周」行五项——段切分表(T1)、worktree(T6)、首段 gen_plan(T7)、饱和度计算器(T2)、canary(T3)；另含点火依赖项 v7 再冻结(T5) 与段模式(T4)。API 管道/彩野测试、降噪修理、F7、预聚类 helper 属「1–3 周」行，**不在本 plan**，下一份 plan 承接。
- **占位符**：无 TBD/TODO；所有代码块完整可粘贴；Task 4 (b) 步依赖 render() 实际组装结构，已注明以现文件为准（修改性任务的合理形态）。
- **类型一致性**：`saturation()`/`batch_verdicts()`/`diff_verdicts()`/`_draft_from_forward()` 签名在测试与实现两处一致；测试计数 208→211→214→217→219 递增链已核。
- **风险点已内嵌**：T3 Step 5 的 id 类型陷阱、T5 Step 1 的 assert 停机、T7 Step 1 的 `--lane main` 易错点，均写在步骤内。
