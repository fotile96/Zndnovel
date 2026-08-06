### Task 11: SEG-1 点火准备（冻结实跑 + runbook + handoff）

**Files:**
- Create: `docs/ops/p4-polish-runbook.md`、`docs/ops/p4-seg1-polish-handoff.md`
- Produce (数据，不入 git 的部分按现行惯例处理): `pilot/polish/seg1-s2/`（frozen + plan.json + calib）

**Interfaces:**
- Consumes: Task 1–10 全部工具
- Produces: 两条通道可直接照单点火的一切。

- [ ] **Step 1: 实跑 SEG-1 冻结与计划**

```bash
uv run python tools/polish_setup.py --seg seg1-s2 --opus-data pilot/lanes/opus/data
uv run python tools/polish_setup.py --verify seg1-s2
uv run python tools/polish_context.py --seg seg1-s2 --plan
uv run python tools/polish_calibrate.py --seg seg1-s2 --make
```
Expected: frozen 全套生成、verify 绿、会话表打印（27 批按双帽预计 3–5 组）、校准批就绪。抽查 locked.json：SEG-1 的锚点 id（anchors.yaml chapter=global/s2 相关）与已裁 patch id 都在。

- [ ] **Step 2: 写 p4-polish-runbook.md**

内容（按本计划各工具的 CLI 逐条落成操作序列）：命名与目录约定 → SEG 冻结 → 准入小考（两通道各跑校准批并 `--score`）→ 会话点火（见 handoff）→ 逐批 ingest → gate → triage → 段末裁决（queue.md 逐条 verdict+原因码 append decisions.jsonl 的命令形态）→ amplify 一轮 → commit（先 dry-run 人工核对倒查链，再 --apply，`--data-dir pilot/lanes/opus/data`）→ 清关后必跑：`check_batch` 全段 W4 复检 + `check_qa_quotes.py --qa config/ayano_qa/*.yaml --data-dir pilot/lanes/opus/data` + 题库引文更新 → 阈值调整记台账。

- [ ] **Step 3: 写 p4-seg1-polish-handoff.md（双通道点火指令）**

- **fable-workflow 通道**（channel=`fable-wf`）：每会话一个 Workflow 子代理；prompt 由 `polish_context.py --seg seg1-s2 --session N --out work/ctx/p4s1-sN.md` 生成；子代理任务=读该文件、按输出契约写 `pilot/polish/seg1-s2/raw/fable-wf/b<N>.out`（绝对路径写死在指令里）；落完由控制会话跑 ingest。
- **paseo-deepseek 通道**（channel=`ds-flash`）：`create_agent`（provider 取用户 paseo 中已配置的 deepseek v4 flash endpoint 实名，点火前 `list_providers` 核对）在独立 workspace 跑，同一 raw 契约、同一绝对路径；计费入 `data/api_ledger.jsonl`；心跳=最近 raw 落盘时间戳，`Monitor`/heartbeat 检查目录 mtime。
- 并行安全条款：两通道只写各自 `raw/<channel>/` 与（经 ingest）各自 candidates 文件；谁也不碰 patches。
- 段末流程回指 runbook；K=150、抽检、放大一轮、清关 dry-run 纪律全部写明。

- [ ] **Step 4: 全量测试 + 提交**

```bash
uv run pytest -q
git add docs/ops/p4-polish-runbook.md docs/ops/p4-seg1-polish-handoff.md pilot/polish/seg1-s2/manifest.json pilot/polish/seg1-s2/plan.json
git commit -m "docs: P4 润色 runbook + SEG-1 双通道点火 handoff（冻结与计划实跑产物）"
```
（frozen/ 大文件是否入库：沿 opus 车道现行惯例——若车道冻结拷贝入库则同样入库，逐路径显式 add。）

---

## Self-review 记录

- spec 覆盖：§2→Task 1；§3→Task 3；§4→Task 5/8（回执落地修正见 Global Constraints）；§5→Task 7；§6→Task 4/5/11；§7→Task 9；§8→Task 6/10/11；§9→Task 2 与各 task 变异步骤；§10 开放事项由用户已定（SEG-1、双通道齐跑）。
- 类型一致：`seg_dir/edit_distance/autoclear_limit`（Task 2）被 5/7/10 按同名引用；`ingest→candidates 字段` 与 Task 7/8 消费字段一致；`channel_state.json` 由 Task 10 写、Task 7 读。
- 无占位符；每 task 有测试代码与判定预期。
