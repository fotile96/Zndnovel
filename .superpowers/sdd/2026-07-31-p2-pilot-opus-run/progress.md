# P2 试点执行台账 · opus 车道（计划 docs/superpowers/plans/translate-pilot-opus.md，46 任务）

开跑：2026-07-31（云端会话，分支 claude/second-novel-p2-pilot-u7mf7n）

## 开场自检

- `bash .claude/cloud-setup.sh --mode session`：pytest 208 passed，build_ledger/build_dag --check OK，uv sync --locked OK。告警 3 项（两条车道未搭建 + 无 tag），均属纯克隆预期。
- 车道重建：opus（model=opus effort=max append=claude-opus-5）、fable（model=fable effort=high append=claude-fable-5）。
- `lane_setup.py --verify` → `冻结校验：无漂移`（exit 0）。

## 偏离记录（相对用户交办口径）

- **D1｜fable 车道提前搭建**：用户口径是「opus batch 1 跑完后再临时建 fable」。实际在开跑前就建好两条车道。理由：`verify()` 的跨车道一致性检查（CROSS_LANE_KEYS）**只在 ≥2 条健康车道时才运行**，只建一条时该检查静默跳过，而它正是 spec §0「术语泄漏」陷阱的唯一机器防线；且计划里每个 CHECKPOINT 的 Step 0 都期望 `冻结校验：无漂移`，单车道下会恒定报错、把真实漂移淹没在噪声里。仅建目录不改变任何译文语义，fable 的 batch 1 仍按计划在 opus batch 1 之后单独跑。
- **D2｜单车道试点**：本次只跑 opus 全 35 批；fable 仅跑 batch 1 用于 spec §3.3 隔离验收。故 spec §6 的双车道对照（区分度统计、盲评 rubric）本次**不产出**，试点报告须记为未完成项。

## 流水线缺陷清单（spec §8 产出物之一，随发现随记）

- **F1｜`lane.json` 存绝对路径，跨环境必然抖动**：`lane_setup.setup()` 把 `lane_dir` 写成绝对路径（本地 `/home/fotile96/claude/2ndnovel-translation/...`，云端 `/home/user/Zndnovel/...`），而该文件入库。每次换环境重建车道都产生一条无意义 diff，且两环境来回翻。实测**无任何生产代码读取该字段**（`record()` 只用 lane.json 的存在性判定车道，其余全是测试引用），即纯文档字段。修法：改存仓库相对路径（`pilot/lanes/<lane>`）。记为 P3 输入，本次不修（试点期不动工装）。

## 逐批记录

| batch | chapter | ids | check | collapse (C1/C2/C3) | commit |
|---|---|---|---|---|---|
