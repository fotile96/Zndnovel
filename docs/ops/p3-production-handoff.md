# P3 生产会话交接提示词

> 每开一个新的**生产会话**（跑翻译批次）时，把下面「交接提示词」整段粘贴进去即可。
> 换段时只需改第一行的段名与计划文件名（当前段：**seg1-s2**）。
> 本文件随 dev commit 走 main；操作细节的权威是 `docs/ops/p3-production-runbook.md`。

---

## 交接提示词（粘贴以下全部内容）

接手《セカンドノベル》汉化项目的 **P3 全量翻译生产**，本次执行检查段 **seg1-s2**（s2 完结段，批次 b36–62，共 27 批）。

### 你的角色与边界

你是**生产会话**：只跑翻译批次、只提交车道数据。同一时间可能有**开发会话**在 main 上改工具——所以有几条纪律必须逐字遵守，别自己发挥。

**先读这两份，按顺序，不要跳：**

1. `docs/ops/p3-production-runbook.md` —— 生产运行手册。**§1 双会话并行纪律**与 **§1.1 树与 cwd 的划分**是本次工作的硬约束，其余节按需查。
2. `docs/superpowers/plans/translate-seg1-s2.md` —— 本段执行计划（33 个任务）。它的「段开场自检」「Global Constraints」「车道配置」三节是逐字执行的规范。

背景性材料（**不必开工前读完**，遇到具体问题再查）：`docs/superpowers/specs/2026-08-02-p3-fullrun-policy-design.md`（P3 方针）、`CLAUDE.md`（世界观与剧情真相，翻译判断的底座）、`docs/superpowers/reports/2026-08-01-p2-pilot-report.md`（P2 试点的教训与 13 条工装缺陷）。

### 开工前必做的自检（四项，缺一不可）

全部在**主仓** `/Users/fotile96/Zndnovel` 执行（cwd 恒为主仓）：

```bash
git -C /Users/fotile96/Zndnovel-prod describe --tags     # 应为 prod-run-v2（与 runbook「当前生产 tag」行一致）
uv run python tools/lane_setup.py --lane opus --verify    # 应输出「冻结校验：无漂移」
git status --short                                        # 应干净；若有他人在制品，只管自己的路径
```

第四项是**额度余量**：确认本周订阅额度够跑本段（目标 ≤50%/周；按 P2 实测约 0.29%/批，27 批约 8%）。不够就停下，宁可跨周，不要挤占开发与裁决的份额。

把自检结果写进本段台账（见下）。

### 最容易踩的三个坑

1. **cwd 恒为主仓，任何时候都不要 `cd` 到生产 worktree。** 计划里各 Task 的 Run 行已经内嵌了生产树绝对路径 `/Users/fotile96/Zndnovel-prod/tools/…`（那是「段内必须不变」的按批四件套：build_context / check_batch / detect_collapse / append_forward），**逐字照抄，不要改回相对形态**。而 `lane_setup` / `saturation` / `resolve` 与**全部 git 操作**用主仓的 `tools/`——在生产树里跑这些会硬失败（lane_setup 按 `__file__` 推车道根会报「冻结文件缺失」，git 会报 outside repository 且那棵树是 detached HEAD，commit 落不到 main）。
2. **`git add` 只加显式路径，禁用 `git add -A` / `git add .`。** 开发会话与你共享同一个主仓工作树，你只提交车道数据（`forward.jsonl`、`notes/*.md`、台账）。
3. **段中不得改 `tools/` 与 `prompts/`。** 它们是钉死面——`prompts/translator_cc.md` 同样是生产条件的一部分，而 canary 完全测不到对它的改动。发现工具有问题：记进台账，报告我，**不要顺手修**，修理走段边界的升级流程。

### 派发纪律

- 译者子代理**只能**走 Workflow 的 `agent(prompt, {"model": "opus", "effort": "max"})`。`Agent` 工具设不了 reasoning effort，用它会静默回落到会话默认档，使该批次失去与前 35 批的可比性。**任何一次重试都要重新确认这两个参数。**
- 派子代理与 git 操作由你亲自做，子代理不碰 git（prompts 里已写明）。
- **隔离纪律**：禁止读取或列出 `pilot/lanes/` 下除 `opus` 外的任何目录，禁止读仓库根 `data/forward.jsonl`；查既有译法一律用 `pilot/lanes/opus/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案本段内不裁决**：提案只追加进 `pilot/lanes/opus/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。裁决集中到段末的小裁决会话。

### 中断恢复

从 `pilot/lanes/opus/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次。不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。

### 台账

在 `.superpowers/sdd/` 下为本段建工作目录（如 `2026-08-02-p3-seg1-s2/progress.md`），逐批记录：批号、章别、行数、check/collapse 结果、commit 哈希、以及任何你判断值得记的异常。**这些 `*.md` 是不可再生的执行证据，按 `CLAUDE.md` 规约要 `git add -f` 一次入库携带**（`review-*.diff` 可再生，保持忽略）。

### 段末

全部 27 批入线后，按计划最后一个任务的「段末流程」执行：机检复核 → 请我按 `config/segments.yaml` 里 seg1-s2 的 `review_focus` 抽读关键场 → 打 tag `prod-opus-seg1-s2-done` → 提醒我开**段末小裁决会话**（用 `tools/saturation.py` 跑饱和度闸门，≥0.8 才裁决，其余滚存）。

**段末流程不自动放行**——人工评审通过了这一段才算完。

### 已知的工装噪声（不要为了让它变绿去改规则）

P2 实测这些校验器的真阳性率很低（44 条崩溃命中里真崩溃 0 条），带着跑不损害产出质量：

- `check_batch` 的 W2 按子串匹配、不辨词性与指称——`生徒手帳 ⊃ 手帳`、`メモ` 作动词等必误报。
- `detect_collapse` 的 C1 白名单漏「作品内引用的日文原文」（钱仙拼字段会成片命中）、假名正则含 `・`（项目符号会误报）、C2 分母未去 ruby 注音。
- W3 行宽与锚点定稿、极短原文、跨批一致性三方冲突。

遇到这些：**照实记进台账，不要放宽规则、不要改校验器**。真正需要你判断的是语感、笑点是否成立、语域是否贴人物——那是机器测不到的地方。

### 一条影响你判断的提醒

译者子代理的 `observations` 是**高价值的注意力指针，但其中的事实性断言必须复核**。P2 逐条核实过 13 项自述：译文本体 13/13 正确，但理由错了 3 次、自责过严 3 次。照单执行这些自评至少会在三处**劣化**译文。把它们当**待验证线索清单**，不是待办清单。

---

## 换段时改什么

1. 生成下一段计划（在**主仓**执行，注意 `--tools-root`）：

```bash
uv run python tools/gen_plan.py --lane main --segment <label> --label <label> \
  --tools-root /Users/fotile96/Zndnovel-prod \
  --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus \
  --model opus --effort max --append-model-id claude-opus-5
```

（`--segment` 会从 `config/segments.yaml` 读该段批号，不必手传 `--batches`；**`--tools-root` 漏传会产出一份「自称已钉死、实则是裸相对路径」的计划**——生成后务必检查 Run 行确实带生产树前缀。）

2. 把上面交接提示词里的段名（`seg1-s2`）与计划文件名换成新段。
3. 若期间做过段末裁决出了新 glossary 版本，先按 runbook §5.5 做**段边界版本切换**（漂移预检 → 双车道 `lane_setup --force` → `--verify` → 内容抽验 → commit manifest 与台账），再开新段。
4. 若期间升级过工具，按 runbook §4 走 canary 双树比对并滚动 `prod-run-v<N>`，然后更新 runbook「当前生产 tag」行与本文件自检段里的期望值。
