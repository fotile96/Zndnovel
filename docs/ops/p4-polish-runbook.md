# P4 润色 pass 生产运行手册（双通道）

> spec：`docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`。
> 计划：`docs/superpowers/plans/2026-08-07-p4-polish-pass.md`（Task 1–10 落地九个工具，693 passed；
> Task 11 首次在 SEG-1 真实数据上跑通全链路并写下本手册）。
> 格式与详略程度对齐 `docs/ops/p3-production-runbook.md`（同一批人在用）；P4 与 P3 是两条独立流水线
> ——P3 管首译（opus 车道正文从 0 到 1），P4 管在**已入线**译文上做一遍模型润色 pass，产出
> `reason="polish"` 的 patch。两者共享同一个生产车道 `pilot/lanes/opus/data/`，但工具、冻结面、
> 数据目录（`pilot/polish/<seg>/` vs `pilot/lanes/opus/work/`）互不相同。
> 十个工具：`tools/polish_{setup,context,ingest,check,triage,commit,amplify,calibrate,audit}.py` +
> 公共层 `tools/polishlib.py`（`polish_audit.py` 是最终评审 I7 补的推翻率闸）。**CLI 参数以各工具 `--help` 为准，本手册给出的都是已实跑验证过的形态**
> （2026-08-07，SEG-1 `seg1-s2`，见 `.superpowers/sdd/2026-08-07-p4-polish-pass/task-11-report.md`）。

## 一、命名与目录约定

- **SEG label**：取 `config/segments.yaml` 的 `label` 字段（如 `seg1-s2`），与 P3 完全共用同一张段表。
- **数据根**：`pilot/polish/<label>/`：
  ```
  pilot/polish/<label>/
    frozen/                  SEG 冻结快照（source/opus/locked/glossary/notes/rulings）——git 忽略
    manifest.json            逐文件哈希 + glossary_v + opus 固化时点——入库
    plan.json                会话/放大扫描的 prompt_hash 累积记录——入库
    calib/                   校准批 + truth + （score 用的 raw，人工另存）——入库
    raw/<channel>/b<N>.out   执行通道原始输出——入库（真实生产台账，不可再生成）
    candidates.<channel>.jsonl  每通道各自的保税仓候选——入库
    gates.<channel>.json     机械闸结果（`{checked_ids, findings}`）——入库
    w4_full.json             清关后全段 W4 复检结果（`polish_check --w4-full`）——入库
    discipline.<channel>.json  通道纪律画像（锁定违规/错位命中计数，按需产生）——入库
    ingested.<channel>.json  批级入仓幂等标记——入库
    channel_state.json       准入小考结果（`{channel: {"autoclear": bool}}`）——入库
    triage.json / queue.md   四桶分流结果 + 人读裁决队列——入库
    decisions.jsonl          人工裁决记录（append-only）——入库
    committed.json           清关幂等标记——入库
  ```
  只有 `frozen/` 被 `.gitignore` 忽略（`pilot/polish/*/frozen/`）——它是可由 `polish_setup.setup()`
  从冻结时点的车道数据 + 仓库 glossary 重新生成的整体拷贝，体量随 SEG 增长、可由 `manifest.json`
  的逐文件哈希追溯，与 opus 车道 `pilot/lanes/opus/skeleton|glossary/` 同一惯例（那两个目录同样
  被忽略，理由同样是"冻结拷贝，非唯一真相源"）。其余文件全部不可再生成（含哈希/时间戳的元数据，
  或真实生产台账），一律入库，**逐路径显式 `git add`，绝不 `git add -A`**。
- **channel 名**：本 SEG 约定两条——`fable-wf`（fable Workflow 子代理通道）、`ds-flash`（paseo 派发
  的 deepseek v4 flash 通道）。放大扫描固定用保留字 `amplify`（`channel_state.json` 里它恒不生效
  自动清关，与配置无关）。
- **raw 文件路径**：`pilot/polish/<label>/raw/<channel>/b<N>.out`（**绝对路径**，两条通道执行时
  必须写死，不能让子代理自己"猜"——`polish_context.py` 渲染的输出契约里 `<channel>` 只是占位符，
  实际派发指令必须替换成真实通道名，见 `docs/ops/p4-seg1-polish-handoff.md`）。

## 二、SEG 冻结（`polish_setup.py`）

```bash
uv run python tools/polish_setup.py --seg <label> --opus-data pilot/lanes/opus/data
uv run python tools/polish_setup.py --verify <label>
```

- 第一条建 `frozen/` + `manifest.json`；`--opus-data` 必须指向车道 `data/` 目录（不是车道根）。
- 第二条只读校验，任何时候想确认"这份冻结面有没有漂移"都跑这条，`rc=0` 且打印
  「冻结校验：无漂移」才算过。反向扫描（frozen 里凭空多出的文件）**自带忽略名单**
  （`.DS_Store`/`Thumbs.db`/`__pycache__`/`*.pyc`，Task 11 补的——见 §十二 阈值/机制变更台账
  第一条），人用 Finder 翻一眼 `frozen/` 不会污染 verify 结果。
- **重跑 `setup()` 会整体重建 `frozen/`**（`shutil.rmtree` 后重写），manifest 也会跟着换掉。
  这条现在**是机制不是纪律**（最终评审 I5）：目录里一旦出现 `candidates.*.jsonl` /
  `decisions.jsonl` / `triage.json` 任何一个，`--seg` 直接拒绝执行（**rc=3，在任何文件被删写
  之前**），拒绝信息逐条列出重跑会静默毁掉什么：①`opus.jsonl` 把已清关的 polish patch 吃成
  新的"润色起点"，此后 edit 幅度/零改动判定/autoclear 阈值全部基于错误基线；②manifest 一并
  重写使 `verify()` 事后**恒绿**；③`rulings.md` 连同 amplify 轮数闸标记清零；④`opus_at` 冻结
  基线前移，§十 那道"冻结后人裁 patch 拒写闸"失去参照。确实要重来才加 `--force`。
  **点火之前**重冻结（例如仓库的 `glossary/polish.md` 又改了）是安全的，但必须连带重渲染各
  session 的 prompt 并更新 `plan.json`（见 `glossary/polish.md` §7.3）。
- setup 会硬性要求该 SEG 涉及的全部 id 在 opus 车道 `forward`+`patches` 里已有译文（`resolve_map`
  覆盖），没覆盖直接抛 `KeyError`——这是故意的：**P4 不对着还没译完的 SEG 冻结**。
- 锁定集合 = `anchors.yaml` 命中的 id ∪ 已有 patch 的 id。**2026-08-07 用户裁定：锚点行从
  硬锁改软锁**——`locked.json` 现在拆成 `hard_ids`（该 id 冻结时点已有人裁 patch，两者都
  命中时固定归为这一档）与 `soft_ids`（纯 anchors.yaml 锚点、未被覆盖为硬锁）。硬锁行只喂
  给模型做上下文，任何通道对硬锁 id 出稿在 ingest 阶段一律判死；软锁行**可以出稿**——不改
  就正常走桶 1，改了必须带 `adjudicate=true`（没带的判死），且这类改动在 `polish_triage`
  里永不自动清关、无条件强制进裁决队列（不被 K 挤出）。`ids`/`why` 字段保留向后兼容（旧
  消费者只用来展示），新代码应读 `hard_ids`/`soft_ids`。

## 三、通道准入小考（`polish_calibrate.py`）——两通道各跑一次，没考过不许免检

```bash
uv run python tools/polish_calibrate.py --seg <label> --make
```

产出 `calib/<label>.batch.jsonl`（20 句：10 句金标定稿 + 10 句普通句，不带锁标）与
`calib/<label>.truth.json`（判卷答案，绝不进任何 prompt）。

**然后渲染校准批 prompt**（最终评审 I9 补的模式——此前没有渲染器，操作者只能自己拼，
拼得与生产 prompt 不等价这场小考就测不到生产行为，**而它的产物直接决定免检权**）：

```bash
uv run python tools/polish_context.py --seg <label> --calib --out work/ctx/p4<短名>-calib.md
```

它与生产 prompt **同构**（共用同一份任务说明 / `active.json` / `style.md` / `polish.md`
六条细则 / 口调表 / 锚点行 / 章节纪要，均取自同一冻结面），差异只有两处：正文换成校准批的行，
输出契约换成单文件。`truth.json` 绝不进这份 prompt（有专测钉死）。

**两条执行通道各自**读这份 prompt（派发方式与生产 session 完全相同），把模型输出存成一份
JSONL（路径 `pilot/polish/<label>/calib/raw.<channel>.jsonl`——**不要**放进
`raw/<channel>/bN.out`，那个路径专属生产批的 ingest/幂等扫描）：

```bash
uv run python tools/polish_calibrate.py --seg <label> --score --channel fable-wf \
    --raw pilot/polish/<label>/calib/raw.fable-wf.jsonl
uv run python tools/polish_calibrate.py --seg <label> --score --channel ds-flash \
    --raw pilot/polish/<label>/calib/raw.ds-flash.jsonl
```

- `--score` 会把结果写进 `channel_state.json` 的 `{channel: {"autoclear": bool}}`——**只更新
  自己这个通道的键**，两条通道分别跑不会互相覆盖。
- **2026-08-07 缺陷修复**：判卷不再看"实质改写占比"（旧判据 `edit ≤ minor_edit` 被计成
  "未改动"，SEG-1 首次真实小考两条通道都报 `gold_unchanged=10`，独立核算发现实际分别改了
  3/10、2/10——报告在说谎）。三档改为字面一致的 `gold_unchanged`（`edit==0`）/`gold_minor`
  （`0<edit≤minor_edit`）/`gold_substantive`（`edit>minor_edit`），但**这三档只做展示，不
  再直接决定 pass**。真正决定 pass 的是「改了但有没有显式请裁」：`changed_adjudicated`
  （改了且 `adjudicate=true`，不算失败信号）与 `changed_silent`（改了但没请裁，静默推翻
  人工裁决——本次修复要防的最危险失败模式）。`pass=False` 判据是
  `changed_silent/total ≥ calib_silent_override_fail`（默认 0.10，10 句金标 1 句静默覆盖
  就会判 fail——"动了就是信号，幅度不重要"，1 个字的静默推翻和大段改写同样危险）。旧的
  `calib_fail`（0.30）不再被读取，留在 `config/polish.yaml` 仅作历史阈值可追溯，**不要
  以为改它还能影响 pass 判定**。`pass=False` 不阻止该通道产候选、跑生产批——只是本 SEG
  内它的候选一律强制走人工裁决队列（`_channel_autoclear_power` 返回 False），不能
  自动清关。**`channel_state.json` 缺失或某通道压根不在里面时，`polish_triage.py` 对它的
  默认判定同样是"自动清关权关闭"**——即两条通道哪怕都没跑过小考，生产也能正常进行，只是
  一律进人裁队列，不会因为"忘了跑小考"而误开免检权。
- 结果自带 `details` 字段（逐条金标的 edit/三档/`adjudicate`/是否静默覆盖），操作者不需要
  再像 2026-08-07 那次一样自己写脚本核算才能核实报告是否准确。
- 已知偏差（工具自己会打印）：金标是"曾出问题/值得记录"的非随机子集，**pass 率不是质量排行榜**，
  只做门槛判断。

## 四、会话点火（回指 handoff）

```bash
uv run python tools/polish_context.py --seg <label> --plan
```

打印该 SEG 的会话分组（长对话双帽，沿用 P3 阈值：≤10 批/≤600 行）。每组渲染一份 prompt：

```bash
uv run python tools/polish_context.py --seg <label> --session <N> \
    --out work/ctx/p4<label短名>-s<N>.md
```

`--out` 同时把 `{session, batches, prompt_hash}` 追加/更新进 `plan.json`（重渲染同一 session
会替换旧记录，不重复累积）。**具体哪个会话派给哪条通道、子代理怎么点火、raw 落盘的绝对路径**
——按 `docs/ops/p4-seg1-polish-handoff.md` 逐条执行，本手册只管流程骨架。

真实 prompt 通读要点（SEG-1 session 1 实测，709KB/4883 行）：任务说明 + 锁定 id 清单 + 术语/
风格/口调/锚点（含 style.md 全文——本 SEG glossary v14 版本约 56KB，anchors.yaml 全篇 120 条不
按批裁剪）+ 该 SEG 涉及全部章节的 notes（**按章整份嵌入，不按会话/批号裁剪**——crd.md 这类跨
全书章节的 notes 文件体量可观，SEG-1 约 300KB）+ 逐批正文 + 输出契约。这是"译者全知"设计原则
（`style.md` 全知纪律第一条）的自然结果，不是缺陷；执行通道若对超长 prompt 有截断风险，派发前
应实测一次真实上下文窗口。

## 五、逐批 ingest（`polish_ingest.py`）——唯一入仓口

```bash
uv run python tools/polish_ingest.py --seg <label> --channel <channel> --batch <N>
# 或扫整个通道目录：
uv run python tools/polish_ingest.py --seg <label> --channel <channel> --all
```

- 批级幂等：已入仓的批号重跑是 no-op（`ingested.<channel>.json` 记批号，不记逐行）。
- **整批失败**（raw 不是合法 JSONL / 非锁定 id 覆盖不完整 / plan.json 查不到该批 prompt_hash /
  raw 文件不存在）：不写任何候选、不打幂等标记，可安全重跑。
- **逐行判死**（同批其余行照常入仓）：id 不在批内、锁定 id 出稿、批内重复 id、`jp_tail` 对不上、
  `zh` 为空/非字符串、疑似错位（`zh` 逐字等于本批另一 id 的 opus 且两者 jp 不同且该行 zh 不等于
  自身 opus）。锁定违规与错位命中额外计入 `discipline.<channel>.json`——两通道各自的纪律画像，
  段末裁决时值得扫一眼。
- 每批 ingest 后终端会打印 `入仓 N 行，判死 M 行`，含违规提示——**不要静默批量跑完再看**，
  发现某批判死数异常高（截断/错位）应立刻定位原因，不要继续往后跑。

## 六、机械闸（`polish_check.py`）

```bash
uv run python tools/polish_check.py --seg <label> --channel <channel>
```

对该通道当前保税仓里**全部**候选跑一次 `check_batch.check()`（R2a/R2b/R2c 硬规则、W1/W2/W3
软规则）**加一条 P4 专属硬规则 `P4-CTL`**（`_n`/`_r`/ruby **计数**必须与 `frozen/opus.jsonl`
里该 id 的现行译文相等——只卡计数不卡位置，`_n` 与 `_r` 分开数），产出：

```json
{"checked_ids": [ …本次真正检查过的 id 全集，含全绿的… ],
 "findings": {"<id>": {"hard": [...], "warn": [...]}}}
```

**`hard` 非空的候选后续一切分流不得自动清关；`warn` 里带 `W3`（行宽超限）的同样不得自动清关**
（其余 warn 不阻断）。

⚠ **每次新一批候选入仓后必须重跑本命令——这是强制步骤，不是建议**（最终评审 C1）。理由：
`triage` 判"这个 id 有没有机械闸证据"看的是 `checked_ids`，gate 跑过之后又入仓的新候选**不在
里面**，会被判成"没有证据"而拒绝自动清关（安全方向，但会白白把它推去人裁）；而在加
`checked_ids` 之前，那些 id 是被判成"干净"直通免检的——评审实测复现过一条带 R2b 硬伤的候选
就这样进了 `polish_commit` 的写入计划。**顺序永远是：ingest 完这一批 → 重跑 gate → 再 triage。**

**W4（复现句族一致性）在这一层不跑**——保税仓阶段还没清关，谈不上"全段"，W4 见 §十一。

## 七、四桶分流（`polish_triage.py`）

```bash
uv run python tools/polish_triage.py --seg <label>
```

跨**全部**已入仓通道一次性分流，产出 `triage.json`（机器可读）与 `queue.md`（人读裁决队列）。
四桶：0=硬锁（不出稿）/ 1=零改动（`zh==opus`，空白归一，含软锁行未改动、以及**未请裁**
的普通候选未改动的情形）/ 2=进人工裁决队列（K 配额内的普通改动 **+ 软锁行任何改动 +
`adjudicate=true` 的候选（无论有无改动），三者均无条件强制进队列、不占用 K、不与其他候选
竞争排位**）/ 3=有改动但配额外（保留 opus，放大扫描可捞回；软锁行与请裁行都不会落到这一
桶）。自动清关（从 2/3 前截流，**软锁行与请裁行永不适用**）需要该 id 组内**全部**通道候选
同时满足下列**五条**：

1. `edit ≤ autoclear_limit(opus)`；
2. 该行所在通道 gates 里这个 id 的 **hard 为空**；
3. **这个 id 在本轮 gate 的覆盖面 `checked_ids` 之内**——「gates 里没有这个 id 的记录」不等于
   「查过且干净」，也可能是「压根没查过」。二者不可区分正是最终评审抓到的 Critical：不重跑
   `polish_check` 就 triage，新入仓的候选会带着**从未被机械闸检查过**的身份直通免检。
   故 §六 的「ingest 之后必须重跑 gate」是**强制**步骤，不是建议；
4. 该通道候选的 **W3 行宽 warn 为空**——行宽溢出是真实的游戏内故障，不该走免检。
   （W1/W2/W4 仍只作顾问，不阻断。W3 在真实语料 1996 行上的命中率实测 0.25%，是窄闸，
   纳入前置不会淹掉免检通道。）
5. 该通道自动清关权开启（`channel_state.json`；文件不存在或该通道不在其中 → 一律视为关闭）。

**软锁行/请裁行的 K 配额顺序**：软锁改动行与 `adjudicate=true` 的请裁行（无论有无改动）
先无条件占位进桶 2（`triage.json` 的 `meta.forced_soft_count`/`forced_adjudicate_count`，
两者去重后合计见 `meta.forced_total_count`——同一 id 可能同时命中两条支路，K 预算按 id
只扣一次），剩余名额（`K − forced_total_count`）再按既有顺序分配给抽检占用/正常排位。
若强制进队列的合计数超过 K（`meta.forced_total_over_budget=true`，`forced_soft_over_
budget` 单独统计"仅软锁"这一支路是否超过 K，语义不变），stderr 会显著播报——这是真信号
（近期大量改动了锚点行，或通道大量主动请裁），不是本工具的截断。

**2026-08-07 修复（SEG-0 D3）：`adjudicate=true` 的候选无论有无改动都强制进队列。**
旧实现按"有无改动"分桶——`zh==opus` 的候选无条件落桶 1，即使该行带
`adjudicate=true`（通道主动喊"我不改，但请你裁"）。实测两例被静默丢弃（17002/7963，见
`pilot/polish/seg0-s0-s1/channel_feedback.md` D3 节），全靠人工事后发现才手工并入裁决。
同一判定链条上还有一个隐藏镜像面：`adjudicate=true` 且**有**小幅改动、机械闸全绿的候选，
旧代码同样会被正常的 autoclear 判定吃掉（除非恰好命中抽检）。修复后，检查顺序把
"`adjudicate=true`"这一条提到"零改动"判据之前、且完全跳过 autoclear 判定，与软锁强制
进队列同一套机制。`queue.md` 对应新增"请裁·未改动"这一档"进入队列原因"（该 id 名下全部
`adjudicate=true` 的候选行都与 opus 逐字相同时）——避免裁决者把这类没有 diff 可看的行
误当空记录；每条通道候选行末尾若与 opus 逐字相同，也会打上
`[本通道未改动，与 opus 逐字相同]` 标记。人工把这类行裁成 `adopt` 是安全的（`polish_
commit` 会照常写出一条 zh 与 opus 相同的合法 patch，并在 stderr 打一条信息级提示建议
改用 `keep_opus`）——`keep_opus` 才是这类"看过了、维持原译"确认的正常归宿。

⚠ 另有一条独立于分流、在**清关时**才生效的拒绝：某 id 若在本 SEG 冻结之后新落过
`reason ∈ {review, recall}` 的人裁 patch，**自动清关路径一律拒绝写入**（人裁路径可放行，
但会显著播报）。见 §十。

**必看 `meta` 字段**：
```json
{"K":150,"sample_rate_configured":0.10,"sample_rate_effective":0.083,
 "autoclear_eligible_total":..,"sampled_count":..,"sampled_dropped":..,
 "forced_soft_count":..,"forced_soft_over_budget":false,
 "forced_adjudicate_count":..,"forced_total_count":..,"forced_total_over_budget":false}
```
`sample_rate_effective < sample_rate_configured`（或 `sampled_dropped > 0`）说明抽检被 K 硬
预算压缩了——工具会在 stderr 显式告警"少抽了多少条"，**这条一定要看一眼再往下走**：它是
自动清关这条免检通道唯一的兜底,覆盖率被压缩必须被看见,不能悄悄发生。

`queue.md` 只列桶 2 的 id，每个 id 并排列出全部通道候选（jp/opus/各通道 zh/score/批注）+
一行"进入队列原因"（软锁改动 / 请裁·未改动（D3 新增，见上）/ 显式请裁 / 进入本轮裁决队列
——后者**故意不区分正常排位与抽检**，避免裁决者因为知道"这条是抽检来的"而放松审查强度）。

## 八、段末裁决——`queue.md` 逐条定夺，append `decisions.jsonl`

裁决会话按 `queue.md` 逐条给出 verdict，原因码取 spec 枚举（可扩展）：
`量词 / 语序 / 补主语 / 过度归化 / 术语 / 口调 / 漂移 / 其他`。

**具体命令形态**（`decisions.jsonl` 没有专属 CLI——`polish_commit.py` 的模块文档明确写
"decisions.jsonl 是人工在裁决会话里手写的固件"；append 用仓库既有 `pipelib` 工具函数，
一次一条或攒批一次性追加均可）：

```bash
uv run python3 - <<'EOF'
import sys
sys.path.insert(0, ".")
from tools.pipelib import append_jsonl
from datetime import datetime, timezone

append_jsonl("pilot/polish/<label>/decisions.jsonl", [
    {"id": 9448, "verdict": "adopt", "chosen_channel": "fable-wf",
     "edited_zh": None, "reason_code": "语序",
     "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    # verdict ∈ {adopt, edit, keep_opus}；edit 时必须给 edited_zh（人工改写稿）；
    # keep_opus 时 edited_zh 留 None（=不采纳任何候选、维持 opus 原译）。
    # chosen_channel 必须是 candidates.<channel>.jsonl 里真实存在候选的那个通道。
])
EOF
```

- `verdict="adopt"`：清关时取 `chosen_channel` 那份候选的 `zh` 原样入库。
- `verdict="edit"`：清关时取本记录的 `edited_zh`（人工改写稿）入库，`chosen_channel` 仍须给出
  （用于倒查 `prompt_hash`/`candidate_ts` 溯源链，即使最终文字被人工改写过）。
- `verdict="keep_opus"`：不产生新 patch（相当于"看过了，维持现状"），`polish_commit.py` 对
  `keep_opus` 不落任何清关计划项——只作裁决记录留痕。
- 多通道同一 id 在队列里并排列出时，`queue.md` 已经把各通道的 `zh`/`score`/批注列全，裁决时
  直接对照决定 `chosen_channel`。
- **每条回改都要贴 `ts`**（ISO8601，任何唯一递增即可）——`(id, ts)` 是 `polish_commit.py` 的
  幂等键，同一 id 先后两次不同裁决（比如先 adopt 后来发现有问题改判 edit）靠不同 `ts` 区分，
  都能落地成两条 patch（后写者胜）。

## 八之二、抽检推翻率闸（`polish_audit.py`）——段末强制，不是可选

```bash
uv run python tools/polish_audit.py --seg <label>
```

裁决完 `queue.md` 之后**立刻跑这一条**（放大扫描之前）。它读 `triage.json` 里
`autoclear=True and sampled=True` 的行 × `decisions.jsonl` 的人裁 verdict，算每条通道的抽检
推翻率；**达到或超过 `overturn_freeze`（0.20）即改写 `channel_state.json` 关闭该通道本 SEG
的自动清关权**，并列出需要回滚复审的存量自动清关 patch id。

- 推翻的判据：该 id 的最后一条人裁不是"adopt 本通道的候选" → 算推翻（`keep_opus`/`edit`/
  `adopt` 了别家的，都算）。`verdict="auto"` 是 `polish_commit` 自己铸造的记录，**不算人裁**
  （算了的话抽检就自我背书，推翻率恒 0）。
- 尚未裁决的抽检样本不进分母，但会 stderr 播报待裁数——分母太小导致率虚低不能悄悄发生。
- `--dry-run` 只报不改。**默认就会改**：关权是安全方向的动作，不该需要额外开关才肯生效。
- 冻结之后**不能靠重跑准入小考解冻**：`polish_calibrate.py --score` 看到
  `autoclear_frozen_by` 就强制判 False 并播报，解冻必须是人处理完存量回滚之后的显式动作。
- 存量回滚不在本工具里做（生产 `patches.jsonl` 只经 `polish_commit --apply`/`add_patch.py`
  写入）——按 §十二 逐条用 `add_patch.py` 落 `reason=review` 覆盖 patch。

这条闸此前**只有文档没有代码**（runbook 自陈"由裁决会话人工执行"）。它是自动清关这条免检
通道**唯一**的事后反馈回路，而 `triage` 本身还会主动压缩抽检覆盖率（K 帽，SEG-1 规模下 10%
实际会掉到 6% 上下）——覆盖率在打折，出口再靠人记就等于没有闭环（最终评审 I7）。

## 九、放大扫描（`polish_amplify.py`）——每 SEG 限一轮

裁决完成后：

```bash
uv run python tools/polish_amplify.py --seg <label> --digest
```

把 `decisions.jsonl` 里 `verdict ∈ {adopt, edit, keep_opus}` 的记录（`auto` 决策不计入）按
原因码归纳成意图纪要，追加进 `frozen/rulings.md`（自动前馈进下一 SEG 的 render() 与本 SEG
后续渲染）。可重复调用，不受轮数闸限制。

```bash
uv run python tools/polish_amplify.py --seg <label> --scan-prompt \
    --out work/ctx/p4<label短名>-amplify.md
```

装配整 SEG 放大扫描 prompt（纪要 + 四桶全景，**含桶 3 落选句全文** + 桶 2 已裁决行的最终 zh，
要求模型"照抄"）。channel 固定 `amplify`。**每 SEG 最多一轮**——`frozen/rulings.md` 里
`<!-- amplify-round:N -->` 标记数达到 `CFG["amplify_rounds"]`（=1）会拒绝再装配（抛
`AmplifyRoundLimitError`，不写任何东西）。派发同一份 handoff 流程（读 prompt → 按批产出
`raw/amplify/b<N>.out` → `polish_ingest --channel amplify --all` → `polish_triage`（`amplify`
候选恒不自动清关，只能进人裁）→ 补充小裁决 append `decisions.jsonl`）。

## 十、清关（`polish_commit.py`）——先 dry-run 人工核对，再 `--apply`

```bash
# 第一步：dry-run（默认），只打印将写入的 patch 与倒查链，不碰任何文件
uv run python tools/polish_commit.py --seg <label> --data-dir pilot/lanes/opus/data

# 人工核对 stderr 输出的每一条：
#   id → verdict → 渠道 → glossary_v → ts
#   倒查链：id → 候选(channel, ts) → prompt_hash
#   zh：即将写入的最终译文
#   ⚠ id 已有 N 条 patch（若该 id 在润色期间被其他会话/工具动过，这里会显式告警）
# 核对无误后：
uv run python tools/polish_commit.py --seg <label> --data-dir pilot/lanes/opus/data --apply
```

⚠ **`--data-dir` 绝不可省**——车道模式下缺省即拒绝执行（复用 `add_patch.resolve_data_dir` 的
护栏，见 2026-08-02 事故：省略会静默落到主仓 `data/`，那里没有车道 forward，"零报错"但四条
回改一条都不生效）。`ZND_DATA` 环境变量同样兼容，但**手打命令一律显式给 `--data-dir`**，不要
依赖当时是否设了环境变量。

- 输入：`decisions.jsonl` 里 `verdict∈{adopt,edit}` 的记录 + `triage.json` 里
  `autoclear and not sampled` 的候选（`verdict=auto` 决策由本工具自己铸造并追加进
  `decisions.jsonl`，带 `reason_code="autoclear"`）。`keep_opus` 与 `auto` 之外的其余记录不
  产生 patch。
- 写入的 patch 行：`{"id", "zh", "reason":"polish", "glossary_v": <清关时点现行版本，不是
  manifest 里冻结时点那个>, "ts", "prov": {"channel","candidate_ts","seg"}}`——`prov` 支持
  三跳倒查：patch → candidates 行（按 channel+candidate_ts）→ plan.json 记录（按
  prompt_hash）→ 渲染时的 prompt 文件本身。
- 幂等键 `(id, decision_ts)`，不是单纯 `id`：同一 id 先被自动清关、后被人工改判，两条决策的
  `ts` 不同，都能落地（后写者胜）。重复 `--apply` 是 no-op。
- 多通道同一 id 都满足自动清关：取 `edit`（相对 opus 编辑距离）最小的通道，同分按通道名
  字典序打散——选"改动最保守"的那份。
- **冻结基线之后新落的人裁 patch，自动清关一律拒写**（最终评审 I4，spec §3 承诺的
  `manifest.opus_at` 安全承重点第一次真正被消费）：`commit()` 逐条比对该 id 在
  `opus_at.patches_lines` 之后是否新增过 `reason∈{review,recall}` 的 patch——
  - 有 → **`verdict=auto` 的直接拒绝写入**（dry-run 预览里同样不出现），stderr 打出冲突详情；
    要落它必须走人裁（在 `decisions.jsonl` 里显式给一条 adopt/edit），由人确认是否真要覆盖
    那条裁定稿。这正是 CLAUDE.md 记的「SEG-5 id 1600 误覆盖已裁定稿」同一失败模式，区别只在于
    这次执行者是无人值守的自动清关。
  - 人裁路径放行但**显著播报**——那条路上有人正看着这个 id。
  - manifest 缺 `opus_at`、或 `patches.jsonl` 比基线还短（append-only 被破坏／`--data-dir`
    指错车道）→ **保守放大**：把全部 review/recall patch 都当成冻结后的，自动清关一律拒写并
    告警。"算不出来"绝不等于"放行"。

## 十一、清关后必跑

```bash
# 1) 全段 W4 复检（复现句族一致性——ingest/gate 阶段刻意不跑这个）
uv run python tools/polish_check.py --seg <label> --w4-full --lane-dir pilot/lanes/opus

# 2) 题库引文同步检查（润色 patch 落库必然可能覆盖题库里逐字引用的旧译文）
uv run python tools/check_qa_quotes.py --qa config/ayano_qa/*.yaml \
    --data-dir pilot/lanes/opus/data
```

- 第 1 步扫的是**全段**（不只是本次清关的 id），因为润色改动可能让某句与它的"兄弟句"（同一
  日文反复出现的复现句族）产生新的不一致——W4 的判定面是全库兄弟索引，不是单条候选；比对的
  文本是**车道现行译文**（`resolve_map(forward, patches)`，即已叠加本轮 polish patch 的那一版）。
  结果落 `pilot/polish/<label>/w4_full.json`，命中项同时打到 stderr。
  **rc 语义**：`0`=跑完了（不管有没有命中，W4 是顾问级、不自动阻断）；`2`=**没能跑**
  （车道 data 缺 ledger 或全无译文，兄弟索引建不起来）——"没能跑"绝不冒充"跑了没问题"。
  ⚠ 本手册初版这一步写的是 `check_batch.py --batch N --lane-dir …`，**在 P4 语境下根本跑不
  起来**（它读 P3 的按批四件套 `work/ctx/batch_N/source.jsonl`，`work/` 是 gitignore 的临时
  目录、P3 跑完早已不存在；即便重建，它读的草稿是 P3 **首译稿**而不是清关后的现行译文）——
  结果是 spec §8 点名的"润色只改同 jp 兄弟句之一"这条真实风险**全程无闸**（最终评审 C3）。
  **2026-08-07 修复（SEG-0 D4）：每条 finding 现在报出该 jp 句族的全部其他成员，不再只报
  一个。** 旧代码复用 `check_batch._w4_msg()`（P3 钉死面，按 zh **文本**去重、只挑 3 个代表）
  生成 finding 的 `msg`，在"全段收敛检查"这个语境下会漏报：若两个不同 id 恰好带着完全相同
  的（错的）译法，去重只留一个代表，另一个的存在感被抹掉——SEG-0 实测：7894 的句族有
  9186/11407 两个其他成员，二者旧译文字面相同，第一轮只同步了 9186，重跑才暴露 11407。
  `w4_full()` 现在改用本模块自己的 `_w4_full_msg()`（不去重、不截断），finding 结构新增
  `siblings` 字段（`[{"id","zh","seg"}, ...]`，全族成员的结构化列表，`seg` 是该 id 经
  `forward.jsonl` 的 `batch` 号落进 `config/segments.yaml` 区间解出的"所属段"，查不到时为
  `null`——顾问级标注，缺了不影响告警本身触发）；`msg` 字段格式同步改为逐个列出全部成员。
  `w4_full.json` 除本工具与其自身测试外无其它消费者（已 grep 全仓确认），格式改变对生产
  流程零风险。**「循环『同步→重跑』直到本轮引入项归零」这条纪律依然保留**——报全一族之后
  单轮就能看全 7894/9186/11407 这类家族，循环次数应显著下降，但"同步伙伴行"这个编辑动作
  本身仍可能让族里另一个此前未被提及的成员产生新的不一致，报全一族解决不了这一层因果，仍
  需要重跑确认收敛。
- 第 2 步命中即说明某题库参考答案逐字引用的译文被本轮回改覆盖掉了，需人工核对是"译文改对了
  但题库答案没跟上"（更新题库引文）还是"回改本身有问题"（回到 §八 补一条裁决）。P3 runbook
  记录过首次跑即在 7 份题库里查出 5 处真失同步——这类闸此前完全不存在，**不要跳过**。
  **2026-08-07 加的抑制清单**：`config/qa_quote_suppressions.yaml`（与题库本身分开存放，
  评审时一眼看全"我们一共豁免了什么"）——SEG-1 5 处命中里有 1 处是伪报（id 10038，
  `seg1-s2.yaml`，片段「，ユウイチ像是」：题库自身叙述句与旧译的偶然子串重合，非引用），
  此前闸没有抑制机制，此后每次 SEG 强制复跑都会再报一次同一条已知伪报。抑制粒度精确到
  `(qa, id, fragment)` 三元组——只豁免这一条确切命中，`id` 换个片段（同一行未来再出现新的
  真实漂移）不会被连坐放过；`reason` **必填**，`load_suppressions()` 缺一条就拒绝加载
  整份清单（不是跳过那一条静默继续）。默认路径就是 `config/qa_quote_suppressions.yaml`，
  不用在命令行加任何 flag；`check_qa_quotes.py` 的输出会显式区分"本次命中 N 处，其中 M 处
  豁免，K 处需要处理"，被豁免的命中仍打印（标 `[豁免]`），只是不计入 `--strict` 的退出码
  ——**豁免绝不能悄悄消失在输出里**，藏起来等于把闸变恒绿。新增一条豁免前，先确认这确实是
  伪报（不是"看着报得烦就抑掉"），并把 `reason`/`date`/`source` 写清楚，供日后复核这条豁免
  是否还成立。
- 两步都过（或已人工核对差异）后，`git status --short pilot/lanes/opus/data/` 应只剩
  `patches.jsonl`（本轮新增的 polish patch）与（若更新了题库）`config/ayano_qa/<label>.yaml`
  的改动；`pilot/polish/<label>/` 下的产物按 §一 的入库清单逐路径 `git add`。

## 十二、阈值调整记台账

`config/polish.yaml` 的全部阈值（`K`/`sample_rate`/`overturn_freeze`/`calib_fail`（已废弃，
不再被读取，仅留存历史值）/`calib_silent_override_fail`（2026-08-07 新增，取代
`calib_fail` 用于准入小考 pass 判定）/`autoclear_abs`/`autoclear_ratio`/`minor_edit`/
`amplify_rounds`/`session_size`/`session_lines`）集中在一处；首个 SEG（seg1-s2）实测后
若需要调整，**只认抽检推翻率与裁决实感**——spec §9
明写"任何阈值调整不得以自动入库率为优化目标"。调整记录格式参照 P3 runbook §四的"判定记录"
体例：改了什么、为什么、影响哪些在产 SEG、全量测试结果。

**通道自动清关权推翻率闸**（`overturn_freeze`=0.20）：段末裁决核对抽检样本（`triage.json`
里 `sampled=True` 的行）时，若某通道被抽检推翻（人工判定该行不该被自动清关放过）的比例
超过此线，该通道**本 SEG**自动清关权立即冻结（改 `channel_state.json` 该通道的
`autoclear` 为 `false`），存量该通道的自动清关 patch **全部回滚复审**（保税仓单据链
`prov` 字段可精确定位每一条来源）。**这条闸现在有专属 CLI：`tools/polish_audit.py`，见 §八之二，段末强制跑。** 它负责算率、
关权、列出需回滚的 patch id；回滚本身仍由人执行（生产 `patches.jsonl` 只经
`polish_commit --apply`/`add_patch.py` 写入，不发明第三条写入路径）——按 `prov` 逐条找到
patch id，用 `add_patch.py --has-patch` 核实后落一条新的 `reason=review` 覆盖 patch 撤销
之前的自动清关内容。

### 阈值变更记录

| 日期 | 项 | 旧→新 | 理由 | 影响的在产 SEG |
|---|---|---|---|---|
| 2026-08-07 | `K` | 150 → 500 | SEG-1 两条通道准入小考均未通过、全量人裁；K=150 是按「有免检通道分流大头」设计的，全人裁形态下会把段末队列静默压缩成抽样，而首个 SEG 最需要看全。用户裁定本段宁可多花人力。 | seg1-s2（实际用掉 233，未触顶） |
| 2026-08-07 | `K` | 500 → 700 | SEG-0（b1–35）4282 行，是 SEG-1 的 2.15 倍；按 SEG-1 实测待裁率 11.7% 外推约 500 个 id，再加 33 条软锁强制项（软锁改动无条件进队列、不被 K 挤出）。700 留余量。 | seg0-s0-s1（未点火） |
| 2026-08-07 | `calib_silent_override_fail` | 新增 0.10 | 准入小考判据换轴：旧 `calib_fail`（0.30，看「实质改写占比」）实测会把 1 字推翻人裁裁定判成「未改动」而放行。新判据看「改了却没显式请裁」。旧键保留不再读取。 | 全部（seg1-s2 据此重判为 pass=false） |

⚠ 改 `K` 之前先想清楚：它是**总额**、多通道共享、且含抽检占用。软锁强制项与
`adjudicate=true` 请裁强制项（2026-08-07 D3 修复新增，见 §七）也计入（`meta.
forced_total_count`，两者去重合计）。调大不是没有代价——队列是人在读的。

## 纪律速记（前 10 个任务评审实证过、必须显式遵守）

1. **`polish_commit` 车道模式下缺省 `--data-dir` 拒绝执行且不创建任何文件**（2026-08-02
   事故的防线，见 §十）。
2. **判「某 id 是否已被裁过」用 `add_patch.py --has-patch`，绝不用 grep**——146 条 patch 里
   17 条是带空格体 JSON（`{"id": 10662,`），`grep '"id":<N>,'` 对它们恒返回 0：
   ```bash
   uv run python tools/add_patch.py --id <N> --has-patch --data-dir pilot/lanes/opus/data
   ```
3. **`triage.json` 的 `meta.sample_rate_effective < sample_rate_configured` 要看一眼少抽了
   多少**（见 §七）。
4. **每 SEG 只有一轮 amplify**（`amplify_rounds`=1，工具层已拦，见 §九）；放大扫描的输出
   **只落 `raw/amplify/b<N>.out` 这一个保留通道**，不要按执行通道各建一个目录——那种路径
   不被任何 ingest 认领，而改用原通道名回炉会撞上批级幂等，两条路都是"零报错、零入仓"。
4b. **ingest 完一批就重跑 `polish_check`，再跑 `polish_triage`**（§六）——gate 跑过之后
   入仓的新候选不在 `checked_ids` 里，triage 会拒绝给它免检权。
4c. **段末裁决完立刻跑 `polish_audit.py`**（§八之二），再进放大扫描/清关。
5. **绝不 `git add -A`**——生产会话/裁决会话只 add 车道数据与 `pilot/polish/<label>/` 下按
   §一 清单入库的文件；dev 会话只 add 自己改的工具/文档。工作树里若有其他会话未提交的
   `.claude/settings.json`/`data/api_ledger.jsonl` 改动，绝对不要碰。
6. **`pilot/lanes/*/data/` 在 P4 流程里同样只经 `polish_commit --apply`/`add_patch.py` 写入**
   ——不要手改，不要用编辑器直接改 `patches.jsonl`。
