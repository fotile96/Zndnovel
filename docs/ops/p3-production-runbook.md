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

### 4.0 滚 `prod-run-v3` 前必须由人做的一个取舍：detect_collapse F9 豁免的召回净损

`prod-run-v2` 之后 main 上的 `detect_collapse` 改动（F9「作品内引用的日文原文」豁免 +
预算 gate，落码 `567a323`）**同时有收益和损失**，而 **canary 结构上只看得见收益那一半**：
canary 重放的是**已入线的好译文**，那里没有「照抄型偷懒」的样本，所以它对这个改动只会
显示「纯降噪、一致」。**这个判断必须由人显式做出并在 git log／台账里留痕，不能用
canary 的「一致」代替。**

收益侧（已实测）：已入线 6146 行真实译文，C1 命中 **27 → 8**（消 19，新增 0）——原先
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

不在覆盖面内、必须人工判定的：`gen_plan`、`append_forward`、`lane_setup`、`resolve`、
`build_ledger`、`ayano_test`（对**车道数据**风险为零：只读车道，不写车道任何文件。
但另两条常被以讹传讹的说法不成立——①**不是恒 exit 0**：未知段 label、缺
`DEEPSEEK_API_KEY`、题库 segment 与 `--segment` 不符都 rc=1 退出；②**它会写仓库跟踪
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

## 五、段末流程与小裁决会话

段末流程按生产计划内嵌清单执行。**下面五项与 `tools/gen_plan.py::_segment_tail`
渲染进计划的那份清单逐项对齐**——生产会话实际照做的是计划里那份（handoff 明写
「按计划最后一个任务的『段末流程』执行」），本节是它的操作依据；**改一边必须同步
改另一边**，两边编号相同而含义不同会让段末会话在「第 N 步」上产生歧义。

> ⚠ **seg1-s2 的例外**：在产计划 `translate-seg1-s2.md` 生成于彩野测试进入
> `_segment_tail` 之前（在产计划不重新生成），其内嵌清单是旧五项、第 3 项是打 tag、
> 无彩野测试。**本段以本节五步为准**，下一段起两边自动一致。

1. 机检复核。
2. 用户按 `config/segments.yaml` review_focus 抽读。
3. （tag 前，可选但强烈建议）跑彩野测试作额外验收：
   `uv run python tools/ayano_test.py --segment <label> --qa config/ayano_qa/<label>.yaml --lane-dir pilot/lanes/opus`
   （零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，
   `config/ayano_qa/<label>.yaml` 不存在就跳过并记台账；报告落 work/out/ayano-<label>.md，
   判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。）
   **不得拿别段的题库顶替**：题库顶层带 `segment:` 绑定，与 `--segment` 不符工具直接
   报错退出。理由是上一段的答案往往整张躺在本段前缀卡里（实测 seg1 的 6 张答案卡
   41/44/45/46/58/134 全在 seg2 前缀内），受试模型一行译文不看即可全对——那是恒绿假信号。
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
