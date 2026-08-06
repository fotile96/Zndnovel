# P4 润色 pass 生产运行手册（双通道）

> spec：`docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`。
> 计划：`docs/superpowers/plans/2026-08-07-p4-polish-pass.md`（Task 1–10 落地九个工具，693 passed；
> Task 11 首次在 SEG-1 真实数据上跑通全链路并写下本手册）。
> 格式与详略程度对齐 `docs/ops/p3-production-runbook.md`（同一批人在用）；P4 与 P3 是两条独立流水线
> ——P3 管首译（opus 车道正文从 0 到 1），P4 管在**已入线**译文上做一遍模型润色 pass，产出
> `reason="polish"` 的 patch。两者共享同一个生产车道 `pilot/lanes/opus/data/`，但工具、冻结面、
> 数据目录（`pilot/polish/<seg>/` vs `pilot/lanes/opus/work/`）互不相同。
> 九个工具：`tools/polish_{setup,context,ingest,check,triage,commit,amplify,calibrate}.py` +
> 公共层 `tools/polishlib.py`。**CLI 参数以各工具 `--help` 为准，本手册给出的都是已实跑验证过的形态**
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
    gates.<channel>.json     机械闸结果（`polish_check.gate()`）——入库
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
- **重跑 `setup()` 会整体重建 `frozen/`**（`shutil.rmtree` 后重写），manifest 也会跟着换掉——
  已经跑过 ingest/triage/commit 的 SEG **不要**重跑 `--seg`（只重跑 `--verify` 是安全的）。
- setup 会硬性要求该 SEG 涉及的全部 id 在 opus 车道 `forward`+`patches` 里已有译文（`resolve_map`
  覆盖），没覆盖直接抛 `KeyError`——这是故意的：**P4 不对着还没译完的 SEG 冻结**。
- 锁定集合 = `anchors.yaml` 命中的 id ∪ 已有 patch 的 id（`locked.json` 的 `why` 字段区分两者，
  两者都命中时固定标 `anchor`）；锁定的行只喂给模型做上下文，任何通道对锁定 id 出稿在 ingest
  阶段一律判死。

## 三、通道准入小考（`polish_calibrate.py`）——两通道各跑一次，没考过不许免检

```bash
uv run python tools/polish_calibrate.py --seg <label> --make
```

产出 `calib/<label>.batch.jsonl`（20 句：10 句金标定稿 + 10 句普通句，不带锁标）与
`calib/<label>.truth.json`（判卷答案，绝不进任何 prompt）。**两条执行通道各自**把这份
`batch.jsonl` 当作一批正常翻译任务喂进去（字段 `{"id","batch","jp","opus_zh"}`，输出契约
与生产批完全一致：`{"id","jp_tail","zh","score","note","adjudicate"}`），把模型输出存成一份
JSONL（建议路径 `pilot/polish/<label>/calib/raw.<channel>.jsonl`——**不要**放进
`raw/<channel>/bN.out`，那个路径专属生产批的 ingest/幂等扫描）：

```bash
uv run python tools/polish_calibrate.py --seg <label> --score --channel fable-wf \
    --raw pilot/polish/<label>/calib/raw.fable-wf.jsonl
uv run python tools/polish_calibrate.py --seg <label> --score --channel ds-flash \
    --raw pilot/polish/<label>/calib/raw.ds-flash.jsonl
```

- `--score` 会把结果写进 `channel_state.json` 的 `{channel: {"autoclear": bool}}`——**只更新
  自己这个通道的键**，两条通道分别跑不会互相覆盖。
- `pass=False`（金标实质改写占比 ≥ `calib_fail`=0.30）不阻止该通道产候选、跑生产批——只是
  本 SEG 内它的候选一律强制走人工裁决队列（`_channel_autoclear_power` 返回 False），不能
  自动清关。**`channel_state.json` 缺失或某通道压根不在里面时，`polish_triage.py` 对它的
  默认判定同样是"自动清关权关闭"**——即两条通道哪怕都没跑过小考，生产也能正常进行，只是
  一律进人裁队列，不会因为"忘了跑小考"而误开免检权。
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
软规则），产出 `gates.<channel>.json`（`{id: {"hard":[...], "warn":[...]}}`，只收有问题的 id）。
**W4（复现句族一致性）在这一层不跑**——保税仓阶段还没清关，谈不上"全段"，W4 挪到 §十一"清关后
必跑"。`hard` 非空的候选后续一切分流不得自动清关。每次新一批候选入仓后建议重跑本命令，保持
`gates.<channel>.json` 与 `candidates.<channel>.jsonl` 同步。

## 七、四桶分流（`polish_triage.py`）

```bash
uv run python tools/polish_triage.py --seg <label>
```

跨**全部**已入仓通道一次性分流，产出 `triage.json`（机器可读）与 `queue.md`（人读裁决队列）。
四桶：0=锁定（不出稿）/ 1=零改动（`zh==opus`，空白归一）/ 2=进人工裁决队列（K 配额内）/
3=有改动但配额外（保留 opus，放大扫描可捞回）。自动清关（从 2/3 前截流）需要该 id 组内**全部**
通道候选同时满足：`edit ≤ autoclear_limit(opus)` 且该行所在通道 gates 里这个 id 的 hard 为空
且该通道自动清关权开启（`channel_state.json`）。

**必看 `meta` 字段**：
```json
{"K":150,"sample_rate_configured":0.10,"sample_rate_effective":0.083,
 "autoclear_eligible_total":..,"sampled_count":..,"sampled_dropped":..}
```
`sample_rate_effective < sample_rate_configured`（或 `sampled_dropped > 0`）说明抽检被 K 硬
预算压缩了——工具会在 stderr 显式告警"少抽了多少条"，**这条一定要看一眼再往下走**：它是
自动清关这条免检通道唯一的兜底,覆盖率被压缩必须被看见,不能悄悄发生。

`queue.md` 只列桶 2 的 id，每个 id 并排列出全部通道候选（jp/opus/各通道 zh/score/批注）+
一行"进入队列原因"（显式请裁 / 进入本轮裁决队列——**故意不区分正常排位与抽检**，避免裁决者
因为知道"这条是抽检来的"而放松审查强度）。

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

## 十一、清关后必跑

```bash
# 1) 全段 W4 复检（复现句族跨候选一致性——ingest/gate 阶段刻意不跑这个）
for b in $(seq <lo批号> <hi批号>); do
    uv run python tools/check_batch.py --batch $b --lane-dir pilot/lanes/opus
done

# 2) 题库引文同步检查（润色 patch 落库必然可能覆盖题库里逐字引用的旧译文）
uv run python tools/check_qa_quotes.py --qa config/ayano_qa/*.yaml \
    --data-dir pilot/lanes/opus/data
```

- 第 1 步扫的是**全段**（不只是本次清关的 id），因为润色改动可能让某句与它的"兄弟句"（同一
  日文反复出现的复现句族）产生新的不一致——W4 的判定面是全库兄弟索引，不是单条候选。
- 第 2 步命中即说明某题库参考答案逐字引用的译文被本轮回改覆盖掉了，需人工核对是"译文改对了
  但题库答案没跟上"（更新题库引文）还是"回改本身有问题"（回到 §八 补一条裁决）。P3 runbook
  记录过首次跑即在 7 份题库里查出 5 处真失同步——这类闸此前完全不存在，**不要跳过**。
- 两步都过（或已人工核对差异）后，`git status --short pilot/lanes/opus/data/` 应只剩
  `patches.jsonl`（本轮新增的 polish patch）与（若更新了题库）`config/ayano_qa/<label>.yaml`
  的改动；`pilot/polish/<label>/` 下的产物按 §一 的入库清单逐路径 `git add`。

## 十二、阈值调整记台账

`config/polish.yaml` 的全部阈值（`K`/`sample_rate`/`overturn_freeze`/`calib_fail`/
`autoclear_abs`/`autoclear_ratio`/`minor_edit`/`amplify_rounds`/`session_size`/`session_lines`）
集中在一处；首个 SEG（seg1-s2）实测后若需要调整，**只认抽检推翻率与裁决实感**——spec §9
明写"任何阈值调整不得以自动入库率为优化目标"。调整记录格式参照 P3 runbook §四的"判定记录"
体例：改了什么、为什么、影响哪些在产 SEG、全量测试结果。

**通道自动清关权推翻率闸**（`overturn_freeze`=0.20）：段末裁决核对抽检样本（`triage.json`
里 `sampled=True` 的行）时，若某通道被抽检推翻（人工判定该行不该被自动清关放过）的比例
超过此线，该通道**本 SEG**自动清关权立即冻结（改 `channel_state.json` 该通道的
`autoclear` 为 `false`），存量该通道的自动清关 patch **全部回滚复审**（保税仓单据链
`prov` 字段可精确定位每一条来源）。这条闸没有专属 CLI，由裁决会话人工执行——按 `prov`
逐条找到需要回滚的 patch id，用 `add_patch.py --has-patch` 核实后再决定是否需要一条新的
`reason=review` 覆盖 patch 撤销之前的自动清关内容。

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
4. **每 SEG 只有一轮 amplify**（`amplify_rounds`=1，工具层已拦，见 §九）。
5. **绝不 `git add -A`**——生产会话/裁决会话只 add 车道数据与 `pilot/polish/<label>/` 下按
   §一 清单入库的文件；dev 会话只 add 自己改的工具/文档。工作树里若有其他会话未提交的
   `.claude/settings.json`/`data/api_ledger.jsonl` 改动，绝对不要碰。
6. **`pilot/lanes/*/data/` 在 P4 流程里同样只经 `polish_commit --apply`/`add_patch.py` 写入**
   ——不要手改，不要用编辑器直接改 `patches.jsonl`。
