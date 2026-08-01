### Task 6: 生产 worktree 钉死 + P3 运行手册

**Files:**
- Create: `docs/ops/p3-production-runbook.md`
- 操作: `git tag prod-run-v1` + `git worktree add ../Zndnovel-prod prod-run-v1`

**Interfaces:**
- Consumes: Task 2/3/4/5 全部已 commit（tag 必须含它们）。
- Produces: 生产会话的唯一操作手册；tag `prod-run-v1`；worktree `/Users/fotile96/Zndnovel-prod`（只读代码源）。Task 7 生成的计划与 Task 4 的自检块引用本手册。

- [ ] **Step 1: 写 runbook**

写入 `docs/ops/p3-production-runbook.md`：

```markdown
# P3 生产运行手册（opus 侦察全量）

> spec：`docs/superpowers/specs/2026-08-02-p3-fullrun-policy-design.md`。
> 本手册是生产会话（跑批）与段末裁决会话的唯一操作依据；改动本手册随 dev commit 走 main。

## 一、双会话并行纪律（最重要的三条）

1. **代码与数据分家**：生产会话执行的 `tools/` 一律来自生产 worktree
   `/Users/fotile96/Zndnovel-prod`（钉死在 tag，如 `prod-run-v1`）；车道数据的
   单一真相源在主仓 `/Users/fotile96/Zndnovel/pilot/lanes/opus/`（绝对路径经
   `--repo`/`--lane-dir`/`ZND_DATA` 传入，worktree 里自带的 pilot/ 副本**永不使用**）。
2. **git 提交只加显式路径**：生产会话只 `git add` 车道数据文件（forward.jsonl、
   notes/*.md、progress 台账）；dev 会话只 add 自己改的工具/文档。任何会话禁用
   `git add -A`/`git add .`——两类会话共享主仓工作树。
3. **工具升级只在段边界**，闸门＝canary（见「四」）。段中永不滚动 tag。

## 二、生产会话开场自检（每段开工必做）

1. `git -C /Users/fotile96/Zndnovel-prod describe --tags` == 本手册「当前生产 tag」。
2. `uv run python tools/lane_setup.py --lane opus --verify` →「冻结校验：无漂移」。
3. 确认本周订阅额度余量足够本段预算（生产目标 ≤50%/周，每周 1–2 段；不够就停，
   宁可跨周不要挤占 dev/裁决份额）。

**当前生产 tag：`prod-run-v1`**（升级时更新本行并在 git log 留痕）。

## 三、跑批要点（沿用 P2 机制）

- 计划文件由 `tools/gen_plan.py --segment <label>` 生成（含段自检/段末流程块）；
  派发走 Workflow `agent(prompt, {model, effort})`，参数以计划内车道配置表为准。
- 生产命令统一形态：`ZND_WORK=<lane>/work ZND_DATA=<lane>/data uv run python
  /Users/fotile96/Zndnovel-prod/tools/<tool>.py …`（lane 用主仓绝对路径）。
- 中断恢复：从 forward.jsonl 已有 id 对照 batches.jsonl 重新推导断点，不信任记忆。

## 四、段边界工具升级流程（canary 闸门）

1. dev 在 main 改好工具、pytest 全绿。
2. 成对回验（同一车道数据、同一时刻，先后紧挨着跑）：
   - 旧树：`cd /Users/fotile96/Zndnovel-prod && uv run python tools/canary.py
     --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --batches <最近完成段> --out /tmp/canary-old.json`
   - 新树：`cd /Users/fotile96/Zndnovel && uv run python tools/canary.py
     --lane-dir pilot/lanes/opus --batches <同区间> --out /tmp/canary-new.json`
   - `uv run python tools/canary.py --diff /tmp/canary-old.json /tmp/canary-new.json`
   - 升级触及 build_context 时两边各加 `--regen-ctx`。
3. diff 一致（或差异逐条经人工判定为预期改进）→ `git tag prod-run-v<N+1>` →
   `git -C /Users/fotile96/Zndnovel-prod checkout prod-run-v<N+1>` → 更新本手册「当前生产 tag」行。

## 五、段末流程与小裁决会话

段末流程按生产计划内嵌清单执行（机检复核 → 用户按 `config/segments.yaml`
review_focus 抽读 → `git tag prod-opus-<label>-done` → 开裁决会话）。

裁决会话清单：
1. 汇总本段 notes 提案 + 机器横扫结果，按词族聚类。
2. `uv run python tools/saturation.py --terms-file <词表> --data-dir
   pilot/lanes/opus/data --gate 0.8`：可裁决当场裁，滚存归档到下段。
3. 术语登记纪律（v7 起强制）：active.json 每新增一条，先算对已入线译文的
   W2 命中率再定稿；值＝可字面校验的核心串。
4. 裁决产出 glossary.v<N> + 召回令；回改走车道 patches.jsonl；`resolve` 验证生效。
5. **段边界版本切换**：漂移预检（确认漂移恰为本次召回令文件）→ 双车道
   `lane_setup --force` → `--verify` 无漂移 → 冻结内容抽验 → commit manifest+台账。
6. 顺手筛「裁决后逐批批注」（tr_note 候选，P4 fable 输入）归档到裁决记录。

## 六、额度软政策

生产 ≤50%/周；dev + 交互按需；留 ~15% 缓冲。进度按段不按批：每周 1–2 段即达标。
政策数字可随时人工调整，不建硬机制。
```

- [ ] **Step 2: commit runbook**

```bash
git add docs/ops/p3-production-runbook.md
git commit -m "docs: P3 生产运行手册（并行纪律/自检/canary 升级闸/裁决清单）"
```

- [ ] **Step 3: 打 tag 并建 worktree**

```bash
git tag prod-run-v1
git worktree add ../Zndnovel-prod prod-run-v1
```

- [ ] **Step 4: 验证 worktree**

```bash
git -C ../Zndnovel-prod describe --tags        # 期望 prod-run-v1
cd ../Zndnovel-prod && uv sync --locked && uv run pytest -q; cd -
```
Expected: describe 输出 `prod-run-v1`；worktree 内 pytest 全绿（worktree 有独立 `.venv`，`uv sync --locked` 首跑建立）。

---

