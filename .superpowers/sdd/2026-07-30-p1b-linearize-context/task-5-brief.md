### Task 5: 全书路线编写与 timeline 入库（内容任务，主会话执行）

**Files:**
- Create: `config/route_plan.yaml`（全书正典路线，人工资产）
- Modify: `config/unit_funcs.yaml`（孤儿函数附挂表，验证循环中增补）
- Modify: `tools/gen_timeline.py`（追加 `main()`：解析 route_plan 逐移动执行 + 从 snr_common 解析 sceneId2aCard 写 `data/scene2card.json`）
- Create(运行产物): `data/scene2card.json`、`data/timeline.jsonl`

**route_plan DSL（main() 按序执行的移动指令）：**

```yaml
- story:          {enter: s1s_10, until: s1s_20}          # 首讲撞墙（cost100 设计节奏）
- pool:           {func: "snr_common:comSectionStoryEndAyanoTime"}   # Time over 演出首次播出
- script:         {file: snr_crd_0}                        # 教程做卡剧情
- fragment_sweep: {only: [2]}                              # 制成卡2 → OP
- story:          {enter: s1s_30, choices: {}, until: s1s_140}       # 首过默认路线段
- story:          {enter: s1s_150, choices: {}, until: s1s_200_sel}  # 探索场景
- pool:           {func: "snr_common:comSectionMapmoveAyanoIn"}      # 首个探索场景后放置
- story:          {enter: s1s_210, choices: {}, until: s1s_260_sel}
- fragment_sweep: {}
- replay:         {at: s1s_35_sel, pick: 2, until: s1s_70}
# ……后续各章依「设计通关序≈最早解锁贪心」同构推进至 EX2；备忘：
#   GAMEOVER 短支线用 replay 进出；s3fc 强制段用 story: {enter: s3fc-10}；
#   Section7 用 story: {enter: s7f-10}；s5 日记章入口在 crd_177 sweep 之后。
```

**Step 概要（内容工作循环，不逐 checkbox 展开代码）：**

- [ ] **Step 1**：在 gen_timeline.py 补 `main()`：读 route_plan/unit_funcs/dag/ledger；解析 `snr_common.lua` 的 `sceneId2aCard.<scene> = N` 行生成 scene2card.json（跳过 `keyword` 重复键）；逐移动执行；写 timeline.jsonl（含 seq 编号）。双跑 diff 断言确定性。
- [ ] **Step 2**：主会话（具备全剧情知识）按 `analysis/dag_all.txt` + CLAUDE.md 章节流逐章编写 route_plan.yaml；每写一章跑一次 `gen_timeline && check_timeline`，按报错（缺失 id / 孤儿函数 / 门控缺卡）迭代：孤儿函数（如 `snr_s1_10_s:v0` 教程通知、`scene_s1s_dispatch_v*` 探索小节）通过 unit_funcs.yaml 附挂到属主单元。
- [ ] **Step 3**：全书绿灯后产出摘要（章序、unit 数、marker 数、每章 id 数）呈用户抽查 **CHECKPOINT（需用户）**。
- [ ] **Step 4**：提交：

```bash
uv run python tools/gen_timeline.py && uv run python tools/check_timeline.py
git add config/ data/scene2card.json data/timeline.jsonl tools/gen_timeline.py
git commit -m "data: 全书正典路线与 timeline 入库（check_timeline 全绿）"
```

---

