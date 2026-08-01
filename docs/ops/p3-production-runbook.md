# P3 生产运行手册（opus 侦察全量）

> spec：`docs/superpowers/specs/2026-08-02-p3-fullrun-policy-design.md`。
> 本手册是生产会话（跑批）与段末裁决会话的唯一操作依据；改动本手册随 dev commit 走 main。

## 一、双会话并行纪律（最重要的三条）

1. **代码与数据分家**：生产批次执行的**按批四件套**来自生产 worktree
   `/Users/fotile96/Zndnovel-prod`（钉死在 tag，如 `prod-run-v2`）；车道数据的
   单一真相源在主仓 `/Users/fotile96/Zndnovel/pilot/lanes/opus/`（绝对路径经
   `--repo`/`--lane-dir`/`ZND_DATA` 传入，worktree 里自带的 pilot/ 副本**永不使用**）。
   **钉死面 = `tools/` + `prompts/`**：`prompts/translator_cc.md` / `reviewer_cc.md`
   同样是生产条件的一部分（计划正文有 27 处派发指令引用它），且 canary 完全测不到
   对它的改动——段中一律不得改，要改走和工具升级同一个段边界流程（见「四」）。
2. **git 提交只加显式路径**：生产会话只 `git add` 车道数据文件（forward.jsonl、
   notes/*.md、progress 台账）；dev 会话只 add 自己改的工具/文档。任何会话禁用
   `git add -A`/`git add .`——两类会话共享主仓工作树。
3. **工具升级只在段边界**，闸门＝canary（见「四」）。段中永不滚动 tag。

### 1.1 树与 cwd 的划分（照抄，不要自己发挥）

**生产会话的 cwd 恒为主仓 `/Users/fotile96/Zndnovel`，任何时候都不要 `cd` 到生产
worktree。** 命令按用途分两类：

| 用途 | 工具路径形态 | 理由 |
|---|---|---|
| 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` | `/Users/fotile96/Zndnovel-prod/tools/<tool>.py`（绝对路径，生成的计划 Run 行已内嵌，逐字照抄） | 它们才是「段内必须不变」的判定/产出面，也正是 canary 覆盖的面 |
| `lane_setup` / `gen_plan` / `saturation` / `resolve`，以及**全部 git 操作** | 主仓 `tools/<tool>.py`（相对路径，cwd 即主仓） | 不参与段内冻结语义；且在生产树里会硬失败（见下） |

在生产树 cwd 下会硬失败的两件事（已实测）：
- `tools/lane_setup.py --verify` 的 `LANES_ROOT`/`REPO` 由 `__file__` 推出，生产树的
  `pilot/lanes/*/skeleton|glossary` 是 gitignore 的冻结拷贝、根本不存在 →
  「冻结文件缺失或车道损坏」exit 1。
- `git add /Users/fotile96/Zndnovel/pilot/…/forward.jsonl` → `fatal: … is outside
  repository at '/Users/fotile96/Zndnovel-prod'`；且生产树是 detached HEAD，commit
  落不到 main。

四件套在「主仓 cwd + 生产树绝对路径 + 数据参数指向主仓车道」姿势下已实测可用
（build_context `--repo`、check_batch/detect_collapse `--lane-dir`、append_forward
`ZND_WORK`/`ZND_DATA`；且被调脚本自己 `sys.path.insert(__file__/../..)`，加载的是
**生产树自己的** `tools/pipelib.py`，钉死语义真实成立）。

## 二、生产会话开场自检（每段开工必做，**全部在主仓执行**）

1. `git -C /Users/fotile96/Zndnovel-prod describe --tags` == 本手册「当前生产 tag」。
2. `uv run python tools/lane_setup.py --lane opus --verify` →「冻结校验：无漂移」
   （本命令用主仓 `tools/`，见 §1.1）。
3. 确认本周订阅额度余量足够本段预算（生产目标 ≤50%/周，每周 1–2 段；不够就停，
   宁可跨周不要挤占 dev/裁决份额）。

**当前生产 tag：`prod-run-v2`**（升级时更新本行并在 git log 留痕）。

## 三、跑批要点（沿用 P2 机制）

- 计划文件由主仓的
  `uv run python tools/gen_plan.py --lane <lane> --segment <label> --lane-dir
  /Users/fotile96/Zndnovel/pilot/lanes/opus --model opus --effort max
  --append-model-id claude-opus-5 --tools-root /Users/fotile96/Zndnovel-prod`
  生成（批号由 `config/segments.yaml` 的段表读出，含段自检/段末流程块，四件套
  Run 行自带生产树前缀）；派发走 Workflow `agent(prompt, {model, effort})`，
  参数以计划内车道配置表为准。
- 生产命令统一形态（按批四件套）：`ZND_WORK=<lane>/work ZND_DATA=<lane>/data
  uv run python /Users/fotile96/Zndnovel-prod/tools/<tool>.py …`（lane 用主仓
  绝对路径；cwd 仍是主仓）。其余工具与 git 见 §1.1。
- 中断恢复：从 forward.jsonl 已有 id 对照 batches.jsonl 重新推导断点，不信任记忆。

## 四、段边界工具升级流程（canary 闸门）

1. dev 在 main 改好工具、pytest 全绿。
2. 成对回验（同一车道数据、同一时刻，先后紧挨着跑）：
   - 旧树：`cd /Users/fotile96/Zndnovel-prod && uv run python tools/canary.py
     --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --batches <最近完成段> --out /tmp/canary-old.json`
   - 新树：`cd /Users/fotile96/Zndnovel && uv run python tools/canary.py
     --lane-dir pilot/lanes/opus --batches <同区间> --out /tmp/canary-new.json`
   - `uv run python tools/canary.py --diff /tmp/canary-old.json /tmp/canary-new.json`
   - 升级触及 build_context 时两边各加 `--regen-ctx`。**注意 `--regen-ctx` 会覆写
     生产车道的 `work/ctx`**：跨过 glossary 版本切换后重生的 ctx 与当初入线时的
     已经不同（术语表变了），覆写掉就再也拿不回入线时刻的 ctx。非必要不用；确需
     用时先另存一份或改在车道副本上跑。
3. diff 一致（或差异逐条经人工判定为预期改进）→ `git tag prod-run-v<N+1>` →
   `git -C /Users/fotile96/Zndnovel-prod checkout prod-run-v<N+1>` → 更新本手册「当前生产 tag」行。

**段边界数据再生成**：`gen_timeline`（F7 行序：单元内 id 改按 `(file, line)` 排，
不再按消息号）落码于 `42472c3`，但 `data/timeline.jsonl` 未随之再生——数据再生成
属生产条件变更（在产批次的前缀正文顺序会变），与工具滚 tag 同流程：段边界执行
`uv run python tools/gen_timeline.py`、核对差异仅为 14 个 unit 内 21 处已知行序逆序
的修正（id 集合与其余字段逐行不变，已用临时 `ZND_DATA` 干跑核实）、随 canary 结论
一并提交。`data/ledger.jsonl` 的 `line` 字段是纯增字段，已于 `b285048` 落 main——
经钉死生产树对 batch 100 的 A/B 实验，`context.md`/`source.jsonl`/`manifest.json`
逐字节相同，对在产批次无影响（详见 P3 devwave1 task-3 报告）。

### 4.1 canary 的覆盖边界（必读——闸门不是万能的）

canary 只重算两件事：`check_batch.check` 与 `detect_collapse.scan`（加 `--regen-ctx`
时另含 `build_context`）。也就是说，**只有这三个工具的升级能被 canary 判定**。

不在覆盖面内、必须人工判定的：`gen_plan`、`append_forward`、`lane_setup`、`resolve`、
`build_ledger`，以及 §1 划入钉死面的 `prompts/`。这些东西改了，canary 照样输出
「一致」——它根本没跑它们。

- 判定方法：读 `git diff <旧tag> main -- tools/ prompts/`，逐文件问「这个改动会不会
  改变任何一批的产出或判定」；答案为否即可免跑 canary，但**必须在 git log / 台账里
  写明判定依据**。
- 先例：`prod-run-v1`(fc0e284) → `prod-run-v2`，`git diff prod-run-v1 prod-run-v2 --
  tools/ prompts/` 只触及 `gen_plan.py`（计划生成器：段模式不再误生成 P2 试点硬停
  任务、`--tools-root`、`--segment` 读段表、段语汇）与 `saturation.py`（段末裁决的
  证据表，仅**新增**两行说明性输出，饱和度算法一字未动）。两者都不在
  `check_batch.check` / `detect_collapse.scan` / `build_context` 三者之内，对已入线
  批次的判定与产出**恒等**；`prompts/` 零改动。故免跑 canary，留痕于此。

## 五、段末流程与小裁决会话

段末流程按生产计划内嵌清单执行（机检复核 → 用户按 `config/segments.yaml`
review_focus 抽读 → `git tag prod-opus-<label>-done` → 开裁决会话）。

裁决会话清单：
1. 汇总本段 notes 提案 + 机器横扫结果，按词族聚类。
2. `uv run python tools/saturation.py --terms-file <词表> --data-dir
   pilot/lanes/opus/data --gate 0.8`：可裁决当场裁，滚存归档到下段。
   **`--data-dir` 是这条命令里最容易漏抄的一节**（本行折行，第二行开头就是它）：
   漏传会去读仓库根 `data/`，那里没有车道 forward.jsonl，于是按「零条已译」算出
   一张全列 `0.000 / 滚存` 的完全合理的假表。工具会在表头**之前**打印
   `done=<N> 条已入线译文（data-dir=…）`，N=0 或路径不是车道 data 就是漏传了。
3. 术语登记纪律（v7 起强制）：active.json 每新增一条，先算对已入线译文的
   W2 命中率再定稿；值＝可字面校验的核心串。
4. 裁决产出 glossary.v<N> + 召回令；回改走车道 patches.jsonl；用
   `ZND_DATA=pilot/lanes/opus/data uv run python tools/resolve.py` 验证生效
   （`resolve.py` **只认 `ZND_DATA` 环境变量、没有 `--data-dir`**；主仓裸跑会读不到
   车道 forward，并把一份空的 `final.jsonl` 写进仓库根 `data/`）。
5. **段边界版本切换**：漂移预检（确认漂移恰为本次召回令文件）→ 双车道
   `lane_setup --force` → `--verify` 无漂移 → 冻结内容抽验 → commit manifest+台账。
6. 顺手筛「裁决后逐批批注」（tr_note 候选，P4 fable 输入）归档到裁决记录。

## 六、额度软政策

生产 ≤50%/周；dev + 交互按需；留 ~15% 缓冲。进度按段不按批：每周 1–2 段即达标。
政策数字可随时人工调整，不建硬机制。
