# P3 生产运行手册（opus 侦察全量）

> spec：`docs/superpowers/specs/2026-08-02-p3-fullrun-policy-design.md`。
> 本手册是生产会话（跑批）与段末裁决会话的唯一操作依据；改动本手册随 dev commit 走 main。

## 一、双会话并行纪律（最重要的三条）

1. **代码与数据分家**：生产批次执行的**按批四件套**来自生产 worktree
   `/Users/fotile96/Zndnovel-prod`（钉死在 tag；**当前哪个 tag 以 §2 末尾的「当前生产 tag」
   行为准**，本行不重复记版本号以免两处漂移）；车道数据的
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

**当前生产 tag：`prod-run-v6`**（升级时更新本行并在 git log 留痕）。
（v2 → v3 的 canary 结论与非覆盖面工具逐个判定见 §4.1 的「判定记录」。）

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
- **锚点核对不能按「整行等同」做。** 判据是「**锚点 zh 是否原样嵌入该行译文**」——
  `skeleton/anchors.yaml` 的 jp 有时只是行 jp 的**连续子串**，此时整行还带着锚点之外的成分。
  已三次命中、可判定为常态而非孤例：SEG-5 的 **15445**、SEG-6 的 **16594**（整行带 `【直哉】`
  前缀）与 **3904**（整行是 `先生は、「…」と、彼女に聞く。`）。按整行替换会把行内其余成分
  一并抹掉，且 `check_batch` 的锚点闸判的也是嵌入而非等同——两边口径必须一致。

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

### 4.0 滚 `prod-run-v3` 前必须由人做的一个取舍：detect_collapse F9 豁免的召回净损

`prod-run-v2` 之后 main 上的 `detect_collapse` 改动（F9「作品内引用的日文原文」豁免 +
预算 gate，落码 `567a323`）**同时有收益和损失**，而 **canary 结构上只看得见收益那一半**：
canary 重放的是**已入线的好译文**，那里没有「照抄型偷懒」的样本，所以它对这个改动只会
显示「纯降噪、一致」。**这个判断必须由人显式做出并在 git log／台账里留痕，不能用
canary 的「一致」代替。**

收益侧（已实测）：对**已入线的 b1–62 累计**真实译文（测得时 6146 行；截至 SEG-1 完结为
6278 行）整体重扫，C1 命中 **27 → 8**（消 19，新增 0）。**注意这是 b1–62 的累计口径，
不是某一段的段内收益**——曾有人把它读成「P2 段（b1–35）的 A/B 实测」，引用时务必带区间。原先
成片误报的「钱仙拼字」等作品内引用不再刷屏。

损失侧（全 ledger 16101 行含假名原文构造伪装集，旧码 `fd81aca` vs `567a323` 之后的
HEAD，`JP_QUOTE_BUDGET=-1` 归因隔离证明净损 100% 来自 F9 豁免）：

| 伪装形态 | 旧码 C1 召回 | 新码 | 净损 |
|---|---|---|---|
| 整行照抄 | 98.5% | 98.5% | 0 |
| 照抄 + 句尾加句号 | 98.5% | 82.4% | −16.1pp |
| 照抄 + 标点换中文 | 98.5% | 78.2% | −20.3pp |
| 照抄 + 前置一句中文 | 98.5% | 67.1% | −31.4pp |
| **照抄 + 前后各加一句中文** | 98.5% | **54.2%** | **−44.3pp** |
| 照抄 + 每 7 字换一个中文字 | 98.5% | 65.3% | −33.1pp |

（P3 devwave1 终审表。终审修正波用另一组填充短语独立复算，得 98.5/82.4/77.8/64.3/
50.1/66.5%，逐行同量级、结论相同——**具体百分点随包裹短语长短浮动，量级不变**。
复算脚本形态见 devwave1 final-fix-report。）

**要点**：净损最大的那一档「照抄后前后各加一句中文」恰恰是 LLM 最自然的偷懒形态，
命中率掉到约一半。也就是说，这次改动买到的是「少 19 条误报」，卖掉的是「对包裹型
照抄的一半探测力」。滚 tag 时人要明确回答：本项目当前更怕误报刷屏还是更怕漏检整行
照抄？（P2 实测 44 条崩溃命中里真崩溃 0 条，是支持前者的证据；但 C1 是**唯一**能抓
「结构合法、长度比正常的整行照抄」的规则，是支持后者的理由。）

#### 裁决（2026-08-02，用户）：接受现状，只留痕不加闸 ✅ 已签字

**这个取舍已经由人显式做过判断，不是没人管。** 下面是裁决原文与依据，滚 `prod-run-v3`
时生效；将来若风险画像变化，回到本节重新做这个判断，不要默认沿用。

**裁决内容**：保留 F9 的逐行豁免，**不**增设批级聚合闸。

**明确接受的代价**（不是没看见，是看见了并接受）：「照抄 + 前后各加中文短语」这类伪装的
C1 召回停在约 **54%**（上表最坏行），「照抄 + 标点换中文」约 **78%**。

**支持该裁决的证据**：
1. **C1 真阳性至今为 0**：已完成 62 批（P2 的 35 + SEG-1 的 27）**C1 真阳性 0 条**——SEG-1
   单段 53 条 collapse 中的 C1/C2 与 7 条 warn 全为误报，是「更怕误报」侧的又一数据点。
   （**订正，2026-08-02**：原文写作「真阳性 **0 条**」，未分规则。C3 判据重做后浮出 **6 条**
   C3 真信号——SEG-1 的 9441/9460/9483 与 b27 的 2174/2204/2225，此前被同批误报淹没，详见
   `.superpowers/sdd/2026-08-02-p3-devwave1/c3-redesign-report.md`。**本裁决不受影响，维持**：
   本节的取舍针对的是 **C1 对「整行照抄类伪装」的召回**，而那 6 条属 **C3**（译文把不同原文
   压成同一句）。两条规则的目标失效模式不同——C1 管「没翻」，C3 管「翻得重复/压平」——
   C3 出现真阳性**不构成**重新评估 C1 取舍的理由。签字记录被据实订正过这件事本身即为留痕。）
2. **降噪收益真实**：对**已入线的 b1–62 累计**真实译文（测得时 6146 行；截至 SEG-1
   完结为 6278 行）重扫，C1 命中 **27 → 8**（消 19，新增 0）。**是累计口径，不是段内收益。**

**曾评估但未采纳的替代方案**（留档备查，将来若风险画像变化可回头取用）：在逐行豁免
**之前**算一道**批级残留假名比闸**。实测 62 个已完成批次的批级比值中位 **0.00000**、最大
**0.00913**（batch 19，钱仙拼字段，合法引用最密的一批），而整批原样照抄约 **0.479**——两者
差 **52 倍**；取阈值 **0.05** 可对 62 批零误报（5.5 倍余量）且对整批照抄有近 10 倍冗余。
该指标在豁免之前计算，故天然不受逐行豁免影响。**未采纳的理由是用户判断当前风险画像下
不值得再加机制**——不是该方案无效，也不是没想到。

不要靠悄悄重新调 `JP_QUOTE_BUDGET`/`JP_QUOTE_MIN_NOVEL` 来回避这个取舍——两个常量的
标定过程有据（见 `tools/detect_collapse.py` 常量注释），改数字会同时改动收益侧。缺口
本身已由 `tests/test_detect_collapse.py::test_f9_known_recall_gap_copy_wrapped_in_chinese_phrases`
钉在 CI 上（该用例**断言的是当前的漏报事实**，不是期望行为；它变红＝有人动了取舍，
须回来更新本表）。

**段边界数据再生成**：`gen_timeline`（F7 行序：单元内 id 改按 `(file, line)` 排，
不再按消息号）落码于 `42472c3`，但 `data/timeline.jsonl` 未随之再生——数据再生成
属生产条件变更（在产批次的前缀正文顺序会变），与工具滚 tag 同流程：段边界执行
`uv run python tools/gen_timeline.py`、核对差异仅为 14 个 unit 内 21 处已知行序逆序
的修正（id 集合与其余字段逐行不变，已用临时 `ZND_DATA` 干跑核实）、随 canary 结论
一并提交。`data/ledger.jsonl` 的 `line` 字段是纯增字段，已于 `b285048` 落 main——
经钉死生产树对 batch 100 的 A/B 实验，`context.md`/`source.jsonl`/`manifest.json`
逐字节相同，对在产批次无影响（详见 P3 devwave1 task-3 报告）。

**执行时机纪律**：数据再生成**只在段边界做，且必须确认生产会话不在跑批**。
`data/ledger.jsonl` 被生产车道以符号链接实时读取，而 `build_ledger` 写盘走
`pipelib.write_jsonl`（truncate + 逐行写，不是 tmp+rename 原子替换）——重写这个 3MB
文件期间若有并发读，会读到截断内容。故障模式是响亮崩溃（JSON 解析失败）而非静默污染，
但没有理由去踩：段边界的定义本来就是「生产停在两段之间」。`write_jsonl` 本身**不改**
（多工具共用，改动面与风险不对等）。

**F7 覆盖面残留（读到这里必须知道边界在哪）**：本次 F7 修复**只覆盖前缀正文的顺序**，
即 `timeline.jsonl` 单元内的 id 次序（`build_context._render_prefix` 按 `unit["ids"]`
渲染）。**批次自身 `source.jsonl` 的行序不在覆盖面内、本轮永远不会被修好**：
`build_context` 组装 source 走的是 `for i in b["ids"]`，直接取 `data/batches.jsonl`
里那一批的 ids 数组，而 `batches.jsonl` **已冻结、不得再生成**（manifest 哈希锁定它），
`timeline` 再生多少次都不会回流到它。P2 记录的原始症状——「id 17181 排到 source.jsonl
第 58 位」（复核为 batch 7 第 59/90 位）——正属于**这不被修的一半**。也就是说：
段边界再生 timeline 后，译者看到的**前缀**顺序修正了，**本批待译行的排列**仍是消息号序。
要连这一半一起修，得解冻并重生 `batches.jsonl`，那是下一轮生产的事，不在 P3 范围内。

### 4.1 canary 的覆盖边界（必读——闸门不是万能的）

canary 只重算两件事：`check_batch.check` 与 `detect_collapse.scan`（加 `--regen-ctx`
时另含 `build_context`）。也就是说，**只有这三个工具的升级能被 canary 判定**。

即便是这三个，canary 也只能判「对**已入线的好译文**的判定有没有变」——**探测器召回率
的变化它结构上看不到**（重放集里没有坏样本）。detect_collapse 的 F9 豁免就是活例子，
见 §4.0。凡是改动**探测规则的宽严**（而非纯重构）的升级，canary 判「一致」都不构成放行
依据，必须另做召回侧 A/B 并人工留痕。

⚠ **`gen_timeline` 会写生产数据，且那是个符号链接——别手滑**：它无条件重写
`$ZND_DATA/timeline.jsonl`，而生产姿势 `ZND_DATA=pilot/lanes/opus/data` 下**该路径是指向
主仓 git 跟踪文件 `data/timeline.jsonl` 的符号链接**（`open(path,"w")` 跟随符号链接），
于是一条命令就改掉了主仓数据。重生 timeline 属**生产条件变更**（在产批次的前缀正文顺序会变），
按本节纪律**只许在段边界、且确认生产会话不在跑批时执行**。写盘走 `pipelib.write_jsonl`
（truncate + 逐行写，**非**原子替换），重写期间若有并发读会读到**截断的 JSON**——与
`ledger.jsonl` 同一类风险（见 §4「执行时机纪律」），故障模式同样是响亮崩溃而非静默污染。
该工具已加 argparse（实测）：**未知参数 → rc=2 且不写任何文件**；**`--help` → rc=0**，
打印帮助后**不执行**展开。两者在 `uv run python …`、`uv run -- python …` 与
`.venv/bin/python …` 三种调用下**行为相同**。此前它**从不读 `sys.argv`**，
`gen_timeline.py --help` 这类手误会被静默忽略并**照常重写主仓数据**。姊妹工具
`check_timeline` 只读、无写盘风险，CLI 行为已一并对齐。

不在覆盖面内、必须人工判定的：`gen_plan`、`append_forward`、`lane_setup`、`resolve`、
`build_ledger`、`ayano_test`（对**车道数据**风险为零：只读车道，不写车道任何文件。
但另两条常被以讹传讹的说法不成立——①**不是恒 exit 0**：未知段 label、缺
`DEEPSEEK_API_KEY`、题库 segment 与 `--segment` 不符都 rc=1 退出；`--qa` 指向的题库
文件不存在时 rc=2（「本段题库尚未产出，跳过」，与 rc=1 的真失败/配置错误刻意区分，
也不与 rc=0 的「跑完且全部通过」混淆）；②**它会写仓库跟踪
文件**：每次 API 调用向仓库跟踪的 `data/api_ledger.jsonl` 追加一行计费台账，且**没有
CLI 开关能改路径**（`ledger_path` 只是给测试注入的函数参数）——跑完记得连它一起
提交或确认无关改动），以及 §1 划入钉死面的 `prompts/`。这些东西改了，canary 照样输出
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

#### 判定记录：`prod-run-v2` → `prod-run-v3`（2026-08-02，SEG-1 完结 / SEG-2 开工前）

**漂移面**：`git diff prod-run-v2 main -- tools/ prompts/` = 9 文件 +1303/−37 行；
**`prompts/` 零改动**（钉死面守住）。按批四件套中**只有 `detect_collapse` 变了**——
与 canary 的覆盖面（`check_batch` + `detect_collapse`）恰好吻合，故本次**跑** canary。

**canary 结论（跑了，不是免跑）**：`--batches 36-62`（SEG-1 全段 27 批）、双树同一车道数据、
`--lane-dir` 均指主仓 `pilot/lanes/opus`；**不加 `--regen-ctx`**（本次不触及 `build_context`）。

- `check` 半边（hard/warn）：27 批**逐批深比较完全恒等**——与 `check_batch` 零改动相符。
- `collapse` 半边：27 批总命中 **53 → 51**，仅 2 批有差异，**全部为消失方向，新增 0 条**：

| 批次 | rule | 消失的命中 | 原文 | 判定 |
|---|---|---|---|---|
| 45 | C1 | id 9719 残留假名比 0.026 > 0.02 | 【アヤノ】「ゆ、ユウイチこそ、今日は…」 | 误报：残留假名是**结巴重复的片假名人名** `ユ、ユウイチ`（保留名词），非未译原文 |
| 56 | C1 | id 10041 残留假名比 0.045 > 0.02 | 【アヤノ】「ゆ、ユウイチ……だ、大丈夫？」 | 同上，同一形态 |

**人工判定**：两条消失的均为 F9 目标形态的**真误报**（保留人名的结巴重复被算进残留假名比），
消失方向正确、零信息损失；**新增命中 0 条**（集合级比对，非仅比计数）。放行。
召回侧的代价不由 canary 判定——见 §4.0 的用户签字裁决。

**canary 覆盖不到、须人工判定的 7 个工具**（逐个点名，不笼统带过）：

| 工具 | 是否有行为变更 | 对**在产批次**的影响判定 | 依据 |
|---|---|---|---|
| `build_ledger` | 有（F7：新增 `line` 字段） | **无影响**——纯增字段，`build()` 全局排序仍按 id | 台账已留痕的 A/B 实验：生产树 `build_context` 在只差 ledger 的两个镜像仓上跑 batch 100，`context.md`/`source.jsonl`/`manifest.json` **逐字节相同**（devwave1 task-3 报告） |
| `gen_timeline` | 有（F7：单元内 id 改按 `(file, line)` 排） | **有影响且已随本次一并落地**——前缀正文顺序会变，故本段边界同步再生 `data/timeline.jsonl` | 本次再生核对：533 行不变、14 unit 差异且差异字段恒为 `ids`、id 集合逐行不变、seq 清单与台账预期逐项一致；逆序数 21/16248 → **0/16248**，`check_timeline` OK |
| `gen_plan` | 有（段子区间 `segment_entry`/`segment_subrange`、段头/段尾文案） | **不影响在产批次**——只在**生成计划时**运行，产出的是 md 计划文件；在产计划不重新生成 | 改动全在 `_segment_head`/`segment_entry`/`segment_subrange`/`main`，四件套均不 import 它 |
| `saturation` | 有（脏键判据 `is_clean_key`、并列词串探测） | **不参与批次生产**——段末裁决会话的证据表工具；饱和度算法本身未动 | 改动全为新增 helper + `main` 输出；四件套均不 import 它 |
| `cluster_notes` | 新增工具 | **不参与批次生产**——裁决会话聚卷宗用 | `prod-run-v2` 时不存在，四件套不 import |
| `api_client` | 新增工具 | **不参与批次生产**——彩野测试走 deepseek 的 HTTP 客户端 | 同上 |
| `ayano_test` | 新增工具 | **不参与批次生产**，对车道数据风险为零（只读车道、不写车道任何文件） | 同上；注意它会向仓库跟踪的 `data/api_ledger.jsonl` 追加计费台账（见 §4.1 正文） |

**四件套对上述 7 者的依赖为空**（实测 `grep import`：`build_context`/`check_batch`/
`detect_collapse`/`append_forward` 均不 import 其中任何一个），故「不参与批次生产」不是
推断而是可核验的事实。

**全量测试**：327 passed（与基线一致）。**执行时机**：SEG-1 已完结、SEG-2 未开工，生产会话
不在跑批，符合本节「数据再生成只在段边界做」的纪律。
详细证据见 `.superpowers/sdd/2026-08-02-p3-devwave1/segment-boundary-v3-report.md`。

#### 判定记录：`prod-run-v3` → `prod-run-v4`（2026-08-03，SEG-2 完结 / SEG-3 开工前）

**触发**：SEG-2 段末裁决会话报「本段 30 条 C3 **全部**因原文侧同样重复而误报，且 C3 两条
子规则（批内复读／行内子串重复）**都不看原文侧**」。核查后确认——**该修复早已在 main 上**
（C3 v2「F4 重做」，两个半边均以原文重复程度为基线），生产树钉在 v3 故未享用。**本次是
部署任务而非开发任务**：生产现场独立重新发现了已修的缺陷，其 30/30 恰好是该修复前提的
又一次实证。

**漂移面**：`git diff prod-run-v3 main -- tools/ prompts/` = 9 文件 +1363/−62 行；
**`prompts/` 零改动**（钉死面守住）。按批四件套中**只有 `detect_collapse` 变了**（+89/−9）。
四件套只 import `pipelib`/`resolve`，**两者均不在漂移面内**——故其余 8 个变更文件与批次
生产无关是**可核验的事实而非推断**。

**canary 结论（跑了）**：`--batches 63-90`（SEG-2 全段 28 批）、双树同一车道数据、
`--lane-dir` 均指主仓 `pilot/lanes/opus`；**不加 `--regen-ctx`**（本次不触及 `build_context`）。
**集合级比对（非仅比计数）**：

- `check` 半边（hard/warn）：28 批 **消失 0、新增 0**，逐条恒等——与 `check_batch` 零改动相符。
- `collapse` 半边：**消失 30、新增 0，消失项 100% 是 C3**，落在 8 个批次（74/76/77/82/84/85/87/88）。
  与段末裁决会话独立核查出的「30 条 C3 全部误报」**数量精确一致**。

| 批次 | hard | warn | collapse |
|---|---|---|---|
| 74 / 76 / 77 / 82 / 87 | 0→0 | 0→0 | 3→0 / 5→0 / 3→0 / 3→0 / 4→0 |
| 84 / 85 | 0→0 | 2→2 | 1→0 / 4→0 |
| 88 | **1→1** | **4→4** | 7→0 |

**人工判定**：抽验消失项的原文与译文（11768/11766/11764/3469/3557），全部形如
`【ユウイチ】「……」`——**jp 与 zh 逐字相同的沉默拍**：原文自己重复 N 次、译文同样重复 N 次。
旧 C3 只看译文侧，把「忠实复现沉默」报成复读循环，是教科书级误报。消失方向正确、零信息
损失；**新增 0 条**。batch 88 的 1 条 hard 与 4 条 warn **原样保留**，阻断闸未被削弱。放行。

**canary 覆盖不到、须人工判定的工具**（本次相对 v3 的新增/变更，逐个点名）：

| 工具 | 变更 | 对**在产批次**的影响判定 | 依据 |
|---|---|---|---|
| `api_client` | 大改（chat_completions → Responses API 流式；function tools；`status` 键；运行时 web_search 闸） | **不参与批次生产** | 四件套不 import（实测 grep）；仅彩野测试/审计走它 |
| `ayano_test` | 改（分诊标记降级为中性遥测；卡组前缀按章过滤；题库段绑定校验） | **不参与批次生产**，只读车道 | 同上 |
| `agent_tools` / `agent_loop` | 新增（只读领域工具 + 有界工具循环） | **不参与批次生产**；`agent_tools` 全只读，有禁写回归绊线 | 同上 |
| `audit_notes_promises` | 新增（手记承诺-履行审计） | **不参与批次生产**；只读车道，产出写 `work/out/` | 同上 |
| `verify_card_chapter` | 新增（card_chapter 交叉校验） | **不参与批次生产** | 同上 |
| `gen_timeline` / `check_timeline` | 改（argparse；未知参数 rc=2 且不写文件） | **不参与批次生产**；该修复消除的正是「生产会话敲 `--help` 会静默重写主仓 `data/timeline.jsonl`」的风险 | 同上 |

**全量测试**：436 passed。**执行时机**：SEG-2 已完结、SEG-3 未开工，生产会话不在跑批，
符合本节纪律。

**用户签字**：2026-08-03，「感觉更新一下生产树工装还是有不少好处的，做吧」。

#### 判定记录：`prod-run-v5` → `prod-run-v6`（2026-08-05，SEG-4 已完成 / SEG-5 开工前）

**触发**：SEG-4 段末发现 `check_batch` 的 W3 把 ruby 注音计进了行宽，与引擎实际渲染不符
（注音在正上方以小字号渲染，**不占行宽**），已在 main 修掉（`43e3dd9`）。这是四件套里
唯一的改动（`+18/−2`）；`build_context`/`detect_collapse`/`append_forward` **一字未动**。

**⚠ canary 报「一致」，但它不构成本次放行的依据——这次是覆盖边界，不是安全结论。**

成对回验 b118–138（21 批）`canary diff: 一致`，两侧 warn 均为 `W4:3 / W3:6`、hard 均 0。
查因：**canary 的 draft 取 `forward.jsonl`（入线原稿），patches 按设计不参与**（判定要对齐
入线时刻）。而全库 36 行含 ruby 的译文里，**30 行只存在于 `patches.jsonl`**——ruby 是
SEG-4 段末才补的注音。于是 canary 对本次改动**最多只看得见六分之一的面**，「一致」说明的是
「这个闸看不见这次改动」，不是「这次改动没有影响」。

> 这条应读作 §4.1 覆盖边界的新增一项：**凡改动只在 patches 层的文本上才显形，canary 结构上
> 就判不到**。canary 判的是入线原稿，而 patches 是入线之后的覆盖层。

**真正的判据（直接量）**：用新旧两版 `_max_line_width` 跑**当前有效文本**（forward 叠加
patches，12702 行）：

| | 旧规则 | 新规则 |
|---|---|---|
| W3 命中 | 60 | **51** |

差集**恰好 9 行**（11126/11130/11141/11148/11151/11153/11157/11274/11286），**9/9 全部含
ruby**，**新增命中 0 行**。即：严格单向放宽，且放宽面与「ruby 不占屏宽」的设计意图逐行吻合，
无溢出。W3 是顾问级 warn，放宽不削弱任何阻断闸（hard 面零改动）。

**⚠ 本次又改动了 `prompts/`（钉死面）**：`translator_cc.md` **4 增 0 删**，新增「W3 真触发
时的默认动作：保留 warning、不改译文」与 ruby 不计宽的说明。canary 覆盖不到 `prompts/`，
人工核对：既有各节标题与文字不变，纯追加。该口径由 SEG-4 实战反推——前三组因无明文口径
出现三种做法（收紧／拒绝／再收紧），b130 组起写进派发单后 b130–138 五批 W3 全部为正当保留。

**off-canary 面逐个判定**（canary 只覆盖 `check_batch.check` / `detect_collapse.scan`，
`--regen-ctx` 时另含 `build_context`）：

| 变更 | 性质 | 判定 |
|---|---|---|
| `tools/check_charlevel.py`（新增 220 行）+ `config/charlists/` 7 份字表 | 绘本用字分层核查，**离线分析工具**，不在按批流水线上 | 放行——不参与任何入库判定 |
| `tools/check_voices_anchors.py`（新增 129 行）+ `lane_setup` 接线 | voices 示范译例 ↔ anchors 定稿自洽闸，跑在 `--verify` | 放行——纯新增检查，此前该面**无任何校验** |
| `tools/lane_setup.py`（+241） | `freeze_hashes` 扩到 style/voices；新增落后播报与车道级 `freeze_exclude` | 放行——不在按批面；三项均为「把此前看不见的东西变成看得见」 |
| `tools/gen_plan.py`（+37） | 会话组补回 collapse 处置指引、两段式 ctx 的重生成步与 `--jp-fallback` 说明 | 放行——纯指引增强，生成的四件套 Run 行形态不变 |
| `tools/cluster_notes.py`（+79） | 容器体提案解析（680→708 提案） | 放行——裁决轨工具，不在生产流水线 |
| `config/ayano_qa/*.yaml` | 题库（seg3/seg4 新增、seg1 补出题纪律） | 放行——段末测试用，不参与入库判定 |

**用户签字**：2026-08-05，「如无问题可以做段末车道重冻结，然后起草点火handoff」。

#### 判定记录：`prod-run-v4` → `prod-run-v5`（2026-08-03，SEG-3 中途 / b91–98 已入线）

**触发**：SEG-3 因额度暂停，决定改用**长对话会话模式**跑剩余 b99–117（投喂量省约 7 倍）。
该模式已实测的代价是复现句族退化（10 批 3 组，逐批模式做对了），而兜底闸 **W4** 只在 main
上、不在生产树——**长对话 + 无 W4 是最差组合**，故两者必须同时上。

**漂移面**：`git diff prod-run-v4 main -- tools/ prompts/` = 5 文件 +621/−34。按批四件套中
**只有 `check_batch` 变了**（+74/−4，即 W4 一处）；`build_context`/`detect_collapse`/
`append_forward` **一字未动**。

**⚠ 本次破例改动了 `prompts/`（钉死面）**——`prod-run-v3→v4` 的记录里「`prompts/` 零改动」
曾是被核对过的一项。改动为新增「长对话会话模式」契约节，**不修改既有任何一节**。canary
覆盖不到 `prompts/`（不在四件套判定面内），由人工核对：`git diff --numstat prod-run-v4..HEAD
-- prompts/` = **33 增 0 删**，既有 10 个节标题顺序与文字不变。

**⚠ 本次同时暴露并修掉了 canary 自身的一个覆盖缺口（`6e67cac`）**：`canary.py` 直调
`check(source, draft, speakers, glossary)` **不传第五参 `siblings`**，而 W4 的设计是「不传
就完全不判」。于是**升级判定闸对本次升级的核心变更结构性失明**——首次跑 diff 报「一致」，
不是因为无差异，而是因为压根没跑 W4。这与 `check_batch` CLI 缺 `--lane-dir` 时静默不判是
同一个洞的另一个入口（后者由 `3c0ab9c` 加显式播报修掉）。**补齐后才是下面的真实结论。**

**canary 结论（补齐 siblings 后重跑）**：`--batches 63-90`（SEG-2 全段 28 批）、双树同一车道
数据、不加 `--regen-ctx`（本次不触及 `build_context`）。**集合级比对**：

- `check` 半边：**新增 21 条、消失 0 条，新增项 100% 是 `W4`，其中 hard 新增 0**。12 批出现
  warn 增加（63/66/67/72/73/74/76/79/82/83/84/88），batch 88 的 **1 条 hard 原样保留**。
- `collapse` 半边：**28 批全部 0→0**，与 `detect_collapse` 零改动相符。

**人工判定**：抽验 3 条新增 W4（batch 63 id 11341、batch 66 id 11404/11443），均对应已裁决
的存量 19 组（`○_n結局` 的「结果/到头来」、`そんな事――` 的两读等），**无新面孔**。W4 是
顾问级 warn，不阻断流水线；存量 19 组用户已裁决「不统一、不建白名单」（见长对话 spec §6.1）。
阻断闸未被削弱、崩溃探测未受影响。**放行。**

**canary 覆盖不到、须人工判定的工具**：

| 工具 | 变更 | 对**在产批次**的影响 | 依据 |
|---|---|---|---|
| `gen_plan` | 大改（`--session-size`/`--session-lines` 双重上限、`_group_sessions`、`_session_task`） | **不影响在产批次**——只在生成计划时运行；且实施者把 `HEAD` 旧模块加载后在 5 组真实配置上比对 `render()` 输出，**5/5 逐字相同** | 四件套均不 import 它；既有 62 条回归测试一字未改 |
| `add_patch` | 车道护栏（无 `--data-dir` 且车道存在时拒绝） | **不参与批次生产**；且只收紧、不放宽 | 四件套不 import |
| `audit_notes_promises` | 大改（四分类标注、定点重跑、异常兜底可达） | **不参与批次生产**，只读车道 | 四件套不 import |
| `canary` | 补传 `siblings` | **不参与批次生产**，是判定闸自身 | 见上 |

**全量测试**：485 passed。**执行时机**：SEG-3 生产会话已暂停、不在跑批。

**已知遗留**：SEG-3 将成为**混合段**——b91–98 逐批产出、b99–117 会话产出。日后做段内对照
分析时这是混淆变量，须在段台账写明。

## 四·五、长对话会话模式（可选，spec 见 2026-08-03-long-conversation-batching-design.md）

生成会话组计划：在既有 `gen_plan` 命令上加 `--session-size N`（N ≤ 10）。`--session-size 1`（默认）输出与改造前逐字相同。

**三条硬约束**：

1. **一组不得跨 glossary 版本**——组内各批 `manifest.json` 的 `glossary_v` 必须全部相同。段边界天然满足该约束，跨段分组必须拆。
2. **单组 ≤10 批**（工具层已拦，`--session-size 11` 直接 rc≠0）。10 批/585 行是已实测范围，更长未测。
3. **`check_batch` 必须带 `--lane-dir`**——否则打印「⚠ W4 未启用」，复现句族一致性没被检查。见到该行不要当成通过。

**已知代价（spec §3.3/§5.1，非推测）**：本模式把「与表一致」换成「与自己一致」。跨批一致性变好，规则遵守滑向自洽。十批实测出 3 组长对话独有的复现句退化（逐批模式做对了）。**W4 是为此建的兜底闸，不可省。**

**投喂量实测**：b63–67 五批 594KB → 131KB（省 78%）；速度约 18 行/分钟，快于逐批模式。

## 五、段末流程与小裁决会话

段末流程按生产计划内嵌清单执行。**下面五项与 `tools/gen_plan.py::_segment_tail`
渲染进计划的那份清单逐项对齐**——生产会话实际照做的是计划里那份（handoff 明写
「按计划最后一个任务的『段末流程』执行」），本节是它的操作依据；**改一边必须同步
改另一边**，两边编号相同而含义不同会让段末会话在「第 N 步」上产生歧义。

> 📌 **历史注记（已失效，仅备查）**：seg1-s2 曾有一条编号例外——其在产计划
> `translate-seg1-s2.md` 生成于彩野测试进入 `_segment_tail` 之前（在产计划不重新生成），
> 内嵌清单是旧五项、第 3 项是打 tag、无彩野测试，故编号从第 3 项起与本节差一位。
> **seg1-s2 已于 2026-08-02 完结，该例外随之失效**；SEG-2 起计划由新版 `gen_plan`
> 生成，与本节五步自动一致，**不再有编号歧义**。

1. 机检复核。
2. 用户按 `config/segments.yaml` review_focus 抽读。
3. （tag 前，可选但强烈建议）跑彩野测试作额外验收：
   `uv run python tools/ayano_test.py --segment <label> --qa config/ayano_qa/<label>.yaml --lane-dir pilot/lanes/opus`
   （零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，
   `config/ayano_qa/<label>.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）
   并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过
   即记进段末台账，不必人工先 `ls` 探路径。报告落 work/out/ayano-<label>.md，
   判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。）
   **不得拿别段的题库顶替**：题库顶层带 `segment:` 绑定，与 `--segment` 不符工具直接
   报错退出。理由是上一段的答案往往整张躺在本段前缀卡里（实测 seg1 的 6 张答案卡
   41/44/45/46/58/134 全在 seg2 前缀内），受试模型一行译文不看即可全对——那是恒绿假信号。
   > 📌 **默认档位政策（用户长期口径，2026-08-02）**：`tools/api_client.py` 的
   > `reasoning.effort` 默认档由 `medium` 改为 **`max`**（除非调用方显式指定其他
   > 档），`max_output_tokens` 默认由 4096 改为 262,144（实测上界在 393,216 与
   > 524,288 之间，取比可行值保守一档，见该文件常量注释的实测表）。**影响**：
   > effort=max 使彩野测试 15 题全跑从约 2 分 19 秒变为约 7–8 分钟、输出 token
   > 约 1.6 倍，属预期——换来的是更扎实的 CoT（能看出受试模型是真读译文还是猜的）。
   > `api_client`/`ayano_test` 不在四件套内、不参与批次生产（见 §4.1 判定表），
   > 这条改动不影响在产批次。
4. `git tag prod-opus-<label>-done`。
5. 开裁决会话（先用 `tools/cluster_notes.py` 把本段提案聚成卷宗，见下）。

裁决会话清单：
1. 汇总本段 notes 提案 + 机器横扫结果，按词族聚类：
   `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-<label>.md`。
   卷宗里判**「未匹配到该词键（可能提取不干净，请人工核对）」**的词族＝饱和度算出 0/0，
   **不等于「原文里没这词」**——要么词键真没出现（如活用形/复合短语），要么标题没提干净；
   两者外观相同，一律人工核对原标题后再定，不要当成「无证据可随便定名」。提取不干净的键
   工具已自动降级进「（未归词）」段，那一段本来就是逐条人工过目的。
2. `uv run python tools/saturation.py --terms-file <词表> --data-dir
   pilot/lanes/opus/data --gate 0.8`：可裁决当场裁，滚存归档到下段。
   **`--data-dir` 是这条命令里最容易漏抄的一节**（本行折行，第二行开头就是它）：
   漏传会去读仓库根 `data/`，那里没有车道 forward.jsonl，于是按「零条已译」算出
   一张全列 `0.000 / 滚存` 的完全合理的假表。工具会在表头**之前**打印
   `done=<N> 条已入线译文（data-dir=…）`，N=0 或路径不是车道 data 就是漏传了。
   本工具现在也跑第 1 步同一份脏键判据（`is_clean_key`，两者共用
   `tools/saturation.py` 里的同一份实现）：手抄词表时若带进残渣（裸 id、
   简体字、描述性前缀没剥干净），该词那一行判**「未匹配到该词键（可能提取不干净，请人工核对）」**
   而不是「无出现」——同第 1 步，这不等于「原文里没这词」，核对词表抄写是否干净后重跑。
   **词表里不要整串抄并列词**（如「はい／いいえ」「はい/いいえ」，全角/半角斜杠、
   顿号、竖线皆算）：`total==0` 时工具会自动按这些分隔符拆开子串各查一次，只要
   有子串命中就判**「疑似并列词串，请拆开分别查」**并列出各子串的实际饱和度
   （形如 `词A=覆盖/出现=比值、词B=覆盖/出现=比值`，**具体数字为示意格式、非
   当前基准**——真实数字每次跑都会随生产进度变化，读到的人不要拿它对表），
   不会再误报「无出现」——但仍建议手抄词表时就按词分行，省得多一轮核对。
3. 术语登记纪律（v7 起强制）：active.json 每新增一条，先算对已入线译文的
   W2 命中率再定稿；值＝可字面校验的核心串。
   **v10 增补——「键」本身的覆盖度要查两个相反方向**（体例落码 `glossary.v10.yaml`
   的 `conventions/active-json-key-coverage`）：
   ① **键太窄→静默漏检**：排版变体（`バッドエンド` vs `バッド・エンド`）与活用形
      （`にじり寄る` vs 原文的 `にじり寄った`）不被键覆盖时，W2 对该形**完全不报警**，
      饱和度也会算出 `0/0`。**`0/0` 不等于「原文没这词」**，一律回原文核对后再定。
   ② **键太宽→跨词边界误报**：`メモ` 撞 `メモリされる`、`出前` 撞「カード提**出前**の」。
      这类不改校验器，登记时知道即可。
   另：**饱和度 1.000（剩余占位为零）的词不进 active.json**，改记 `ratified` 节
   （W2 只在待译批次上跑，登记只增词表长度）——见 `conventions/active-json-scope` 条件②。
4. 裁决产出 glossary.v<N> + 召回令；回改走车道 patches.jsonl；用
   `uv run python tools/resolve.py --data-dir pilot/lanes/opus/data` 验证生效
   （✅ **2026-08-05 起有 `--data-dir` 了**，与 `saturation.py` 同形；`ZND_DATA` 仍兼容）。
   此前它**只认环境变量**，主仓裸跑会读不到车道 forward、算出一张「完全合理」的空表
   （`final=0 missing=16749`）并把空的 `final.jsonl` 写进仓库根——SEG-6 裁决会话实测踩到。
   现在这一形态会**显式告警**（「forward.jsonl 不存在……多半是漏传 --data-dir / ZND_DATA」），
   且 `final.jsonl` 跟着 `--data-dir` 落在车道里，不再污染仓库根。输出末尾另打印
   `(data-dir=…)`，跑完扫一眼就知道读的是哪棵树。
5. **段边界版本切换**：漂移预检（确认漂移恰为本次召回令文件）→ 双车道
   `lane_setup --force` → `--verify` 无漂移 → 冻结内容抽验 → commit manifest+台账。
   ⚠ **两条实操陷阱（seg1-s2 与 seg2-s3 各踩出一条）**：
   ① **漂移预检必须用 `diff -rq 仓库侧 车道拷贝`，不能用 `--verify` 代替**——`--verify`
      比对的是「车道拷贝 vs manifest」，**看不见仓库侧的改动**，此时它照报「无漂移」。
      ✅ **2026-08-04 起已成闸**：`--verify` 每次都会在绿字后追加「⚠ 车道冻结拷贝落后于
      仓库侧 N 处」清单（`lane_setup.stale_vs_repo`），落后**不判错、不改退出码**——段中途
      仓库继续演进本就该不同，判错会训练人忽略它。手工 `diff -rq` 因此降为复核手段，不再是
      唯一防线。首次跑即抓到两条车道各 6 处落后（`style.md` 16 行 ruby 口径、
      `skeleton/anchors.yaml` 5 行锚点注音、4 份 voices 示范译例），此前两轮 `--verify` 全绿。
   ② **`--force` 单独给不够**：`lane_setup` 建/重建车道要求同时给
      `--lane/--model/--effort/--append-model-id`，取值照抄各车道现有 `lane.json`
      （opus: opus/max/claude-opus-5；fable: fable/high/claude-fable-5），否则直接报错退出。
   ⚠ **冻结面缺口（seg2-s3 新发现，未修，属开发轨待办）**：`lane_setup.freeze_hashes()`
   只哈希 5 项（`batches`/`cards_zh`/`anchors`/`active`/`glossary_max`），而
   `COPIED_DIRS=("skeleton","glossary")` 会把 **`speakers.json`、`style.md`、`voices/*.md`
   一并拷进车道冻结**——**这三类被冻结却不在 manifest 里，`--verify` 结构上检测不到它们的漂移**。
   v9 起这不再是纸面问题：`speakers.json` 是 **R2b 硬规则的数据源**、`style.md` 是译者唯一
   看得到的口径面，改了它们而忘记 `--force`，`--verify` 会照报「无漂移」且无任何信号。
   **在修好之前，凡召回令触及这三类文件，段边界的抽验步骤必须显式读车道拷贝确认内容**
   （而不是只看 `--verify` 的绿字）。
6. 顺手筛「裁决后逐批批注」（tr_note 候选，P4 fable 输入）归档到裁决记录。
7. **每条回改必须落在「译者看得见的面」上**（v9 新体例 `recall-must-be-visible`，
   落码 `glossary/glossary.v9.yaml` 的 conventions 节）。
   起因：`forward.jsonl` 是 append-only、**patches 只是覆盖层不回写前缀**，于是被否决的旧译法
   仍会在下游批次的**前缀正文**里现身，可能被当成先例照抄。seg2-s3 两处验收（10639、10454）
   **均未兑现**该风险，因为 `context.md` 第四节整篇内嵌 `active.json` + `style.md` + 7 份 `voices/`，
   **冻结骨架压过了前缀里的历史文本**——但这层保护依赖「旧译法恰好被 glossary 覆盖」，
   一旦某条回改的理由是纯语感/纯本地化（产生不了任何可登记词条），保护就不存在。
   译者看得见的面**只有三个**：`active.json`、`style.md`、`voices/*.md`
   （`glossary/style_refine.md` 是 2026-08-04 新增的**汉语母语感细则**，**刻意不在这三面里**——
   用户裁定 opus 本轮不接入，最早用于 fable 车道与润色轨；接入方式与代价见该文件 §7。
   **opus 的排除已写进 `pilot/lanes/opus/lane.json` 的 `freeze_exclude`，`--force` 重冻结自动继承**，
   段边界不必也不要额外记得什么；`--verify` 会单独播报「ℹ 有意排除」一节。）
   （`build_context._render` 的注入面；`glossary.vN.yaml` 与 anchors 之外的 skeleton **不**进 context.md）。
   三面都无处安放的回改，**须在 `pilot/lanes/<lane>/data/notes/<chapter>.md` 追加显式记录**
   （id、旧译、新译、一句话理由，并注明「旧文本作废、勿沿用」）。
   先例：SEG-1 的 `裏技`→作弊；seg2-s3 的 11565／12244／12166／12128／12129（已回填 `notes/s3s.md`）。
   注：这类维护者记录用 `##` 段落 + 表格写，**不要**用 `### 序号. 词 → 译` 形式——
   后者是 `cluster_notes.py` 的提案标题格式，会把维护者记录算成新提案
   （已实测：回填后卷宗仍是 558 提案 / 137 词族，与回填前逐字相同）。
   ✅ **表头怎么写不受限**（2026-08-05 澄清）：SEG-6 交接件里曾嘱「表头不要同时含『原文』
   与『译』两列，否则会被新版 `cluster_notes` 当成新提案」——**那条不必遵守，已撤销**。
   工具的分流判据是**容器标题**不是表头：标题含「维护者记录／自查／核对／沿用／备查」
   即判 `record`、进卷宗附录而非裁决面（已用真实的『【维护者记录】段末裁决回改』表实测确认）。
   多写一条要靠记忆维持、又不带来任何收益的纪律，本身就是负担。

## 六、额度软政策

生产 ≤50%/周；dev + 交互按需；留 ~15% 缓冲。进度按段不按批：每周 1–2 段即达标。
政策数字可随时人工调整，不建硬机制。
