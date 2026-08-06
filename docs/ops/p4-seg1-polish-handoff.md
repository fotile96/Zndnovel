# P4 SEG-1 润色双通道点火 handoff

> 段：**seg1-s2**（第 2 章：ナゾトキ多层选择迷宫段，批次 b36–62，27 批，冻结面已实跑生成）。
> 操作细节的权威是 `docs/ops/p4-polish-runbook.md`（本段流程与命令形态回指该手册；本文件只管
> "怎么点火、两条通道各自怎么执行、并行安全条款"）。
> 冻结实跑记录：`.superpowers/sdd/2026-08-07-p4-polish-pass/task-11-report.md`。

## 你的角色与边界（控制会话）

你是 P4 润色 pass 的**控制会话**：负责冻结校验、渲染 prompt、派发两条执行通道、跑 ingest/
check/triage、主持段末裁决、跑 amplify、清关。**执行通道本身不是你**——`fable-wf` 是 Workflow
派出的子代理，`ds-flash` 是 paseo 派出的独立 agent，两者都只读 prompt、只写 raw 文件，不碰
git、不碰 `patches.jsonl`、不跑本手册任何一个 `polish_*.py` 工具。

**开工前确认（全部在主仓 `/Users/fotile96/Zndnovel` 执行）：**

```bash
uv run python tools/polish_setup.py --verify seg1-s2       # 应输出「冻结校验：无漂移」
git status --short pilot/lanes/opus/data/                  # 应为空——本流程不改生产数据，只经 patches.jsonl 追加
```

冻结面已实跑生成（`pilot/polish/seg1-s2/frozen/` + `manifest.json`），**点火之后不要重跑
`--seg`**（会整体重建 frozen、换掉 manifest 与全部下游判据基准）；只需要 `--verify`。
这条现在**是机制不是纪律**：目录里一旦出现 `candidates.*.jsonl`/`decisions.jsonl`/`triage.json`
任何一个，`polish_setup.py --seg` 会直接拒绝执行（rc=3，`--force` 才强制），拒绝信息里逐条
列出重跑会静默毁掉什么。点火**之前**（比如仓库的 `glossary/polish.md` 又改了）重冻结是安全的，
但要连带重渲染四个 session 的 prompt 并更新 `plan.json`。

## 会话分组

```
session 1: batches 36-45（10 批，568 行）
session 2: batches 46-55（10 批，488 行）
session 3: batches 56-57（2 批，371 行）
session 4: batches 58-62（5 批，569 行）
```

**`prompt_hash` 的唯一真相源是 `pilot/polish/seg1-s2/plan.json`，本文件不再抄一份。**
初版在这里抄了一张哈希表，`ffcd6b4` 写下、`0d0a4d8` 改了 prompt 文本并更新了 `plan.json`，
这张表没跟——四个哈希**全部过期**，而它的用途恰恰是"确认哈希未漂移"（P4 最终评审 I1 实测）。
两处记同一个易变值，迟早只有一处是对的；现在只留一处，另一处给核对命令：

```bash
# 看当前记录（会话 → 批号 → prompt_hash）
cat pilot/polish/seg1-s2/plan.json

# 核对某个 session 的 prompt 文件与 plan.json 记录是否一致（两串应逐字相同）
shasum -a 256 work/ctx/p4s1-s<N>.md
uv run python -c "import json;print([r['prompt_hash'] for r in json.load(open('pilot/polish/seg1-s2/plan.json')) if r['session']==<N>][0])"
```

prompt 文件本身在 `work/` 下（gitignore，不入库），不存在就重新渲染（幂等，`--out` 会覆盖同一份
内容并替换 `plan.json` 里同 session 的记录——重渲染之后上面两串自然又一致）：

```bash
uv run python tools/polish_context.py --seg seg1-s2 --session <N> --out work/ctx/p4s1-s<N>.md
```

**用户已定：本段双通道齐跑**（spec §1 核心决策 2：任一 SEG 保留多通道齐跑的余地）——**每个
session 派发两次**，`fable-wf` 与 `ds-flash` 各读同一份 prompt 文件，各自独立产出候选，互不
知晓对方存在。四个 session、两条通道，共 8 次执行。

## 通道一：`fable-wf`（Workflow 子代理，每会话一个）

**派发只能走 Workflow 的 `agent(prompt, {"model": "fable", "effort": "high"})`**——`Agent` 工具
设不了 reasoning effort，用它会静默回落到会话默认档（P3/P2 反复踩过的坑，见
`docs/ops/p3-production-handoff.md`）。参数取值照抄 opus/fable 车道既有约定
（`pilot/lanes/fable/lane.json`：`model=fable, effort=high, append_model_id=claude-fable-5`）。

对每个 session `N`（1..4），子代理任务提示词（逐字给）：

```
读取文件 /Users/fotile96/Zndnovel/work/ctx/p4s1-s<N>.md（若不存在，先运行
`uv run python tools/polish_context.py --seg seg1-s2 --session <N> --out work/ctx/p4s1-s<N>.md`
生成）。按该文件里「## 任务说明（润色契约）」与「## 输出契约」两节的要求，对该会话
涉及的每一个批次产出一个 JSONL 文件，写到下面的绝对路径（不是相对路径，不要自己判断落哪）：

  /Users/fotile96/Zndnovel/pilot/polish/seg1-s2/raw/fable-wf/b<批号>.out

（把 <批号> 换成该会话实际列出的每个批号，如 b36.out、b37.out……；<channel> 占位符在这里
恒等于 fable-wf，文件名里不要出现字面的 "<channel>"。）

你不碰 git，不跑任何 tools/polish_*.py，不产出 raw 目录之外的任何文件。完成后回报你写了
哪些文件、每个文件多少行。
```

落完由**控制会话**跑 ingest（见下"落地后"）。

## 通道二：`ds-flash`（paseo 派发，独立 workspace）

**点火前必须先确认 provider 实名——不要猜。**

```
调用 paseo 的 list_providers，核对用户已配置的 deepseek v4 flash endpoint 的确切 provider
字符串（形如 `deepseek/xxx`，具体名字以 list_providers 实际返回为准）。找不到就停下问用户，
不要用猜测的字符串去 create_agent——那样要么直接失败，要么（更危险）静默落到另一个模型上，
使本通道的候选、准入小考结果、计费全部张冠李戴。
```

确认 provider 后，为本段建一个独立 workspace（与 fable-wf 隔离，避免两条通道共享文件系统状态）：

```
paseo create_workspace（isolation: local 即可——本通道只读 prompt 文件、只写自己的 raw 目录，
不需要 git 隔离）。
```

对每个 session `N`，`create_agent`（`provider` = 上面核实到的确切字符串，`title` 建议
`p4-seg1-s2-session<N>-ds-flash`），初始提示词与 fable-wf 那份**内容相同**，只把落盘目录换成：

```
  /Users/fotile96/Zndnovel/pilot/polish/seg1-s2/raw/ds-flash/b<批号>.out
```

- **计费**：deepseek v4 flash 走 API 调用，每次计费记录追加进仓库跟踪的
  `data/api_ledger.jsonl`（与 `ayano_test.py`/`api_client.py` 同一条既有约定，见
  `docs/ops/p3-production-runbook.md` §4.1）——**这是仓库里其他会话可能同时在写的文件**，
  控制会话跑完本段后不要用 `git add -A` 把它一并提交，按 CLAUDE.md 与本手册纪律速记第 5 条
  单独核对再决定是否入这一条改动（若不确定是不是自己这次跑的产生的改动，先 `git diff` 看内容）。
- **心跳**：最近一次 `raw/ds-flash/` 目录 mtime 更新的时间戳——判断是否假死。用 Monitor（或
  轮询 `ls -la --time-style=full-iso pilot/polish/seg1-s2/raw/ds-flash/ | tail -1` 的方式）
  盯一段时间没有新文件落盘，才判断为卡住，不要看到"进程还活着"就当作在正常工作。

## 并行安全条款（两条通道同时跑必须遵守）

1. **fable-wf 只写 `raw/fable-wf/` 与（经 ingest 后）`candidates.fable-wf.jsonl`**；
   **ds-flash 只写 `raw/ds-flash/` 与（经 ingest 后）`candidates.ds-flash.jsonl`**——两条通道
   各自独立的文件，物理上不可能互相覆盖。
2. **谁也不碰 `patches.jsonl`**——那是控制会话在段末裁决通过后，用 `polish_commit.py --apply`
   唯一写入的文件，两条执行通道全程不知道这个文件存在。
3. 两条通道可以真正同时（并发）执行——它们读的是同一份只读 prompt 文件，写的是各自独立的
   目录，没有共享可变状态，不存在竞态。
4. 落地节奏不要求同步：`fable-wf` 某个 session 先落完就先跑该 session 的 ingest，不必等
   `ds-flash` 那边跟上；`polish_triage.py` 本来就是"跨全部已入仓通道一次性分流"，晚到的通道
   下次重跑 triage 自然会被并入。

## 准入小考（两通道各跑一次，点火前必做）

**没考过试就不许免检**——按 `docs/ops/p4-polish-runbook.md` §三，`polish_calibrate.py --make`
产出的 20 句校准批，两条通道**各自**跑一遍并 `--score`：

```bash
# ① 造校准批（20 句：10 金标 + 10 陪考，truth.json 是判卷答案，绝不进任何 prompt）
uv run python tools/polish_calibrate.py --seg seg1-s2 --make

# ② 渲染校准批 prompt——**与生产 prompt 同构**（同一份任务说明/术语表/style.md/
#    六条细则/口调表/锚点，只换正文与输出契约、不带锁标）。
#    ⚠ 不要自己拼一份：拼得与生产不等价，这场小考就测不到生产行为，
#      而它的产物直接决定这条通道有没有免检权（P4 最终评审 I9）。
uv run python tools/polish_context.py --seg seg1-s2 --calib --out work/ctx/p4s1-calib.md

# ③ 两条通道**各读这一份 prompt**（派发方式与生产 session 完全相同，只是把
#    "读 work/ctx/p4s1-s<N>.md、写 raw/<channel>/b<N>.out" 换成
#    "读 work/ctx/p4s1-calib.md、写 calib/raw.<channel>.jsonl" 这一个文件）：
#      /Users/fotile96/Zndnovel/pilot/polish/seg1-s2/calib/raw.fable-wf.jsonl
#      /Users/fotile96/Zndnovel/pilot/polish/seg1-s2/calib/raw.ds-flash.jsonl
#    ⚠ 绝不要落进 raw/<channel>/bN.out——那个路径专属生产批的 ingest/幂等扫描。

# ④ 判卷
uv run python tools/polish_calibrate.py --seg seg1-s2 --score --channel fable-wf \
    --raw pilot/polish/seg1-s2/calib/raw.fable-wf.jsonl
uv run python tools/polish_calibrate.py --seg seg1-s2 --score --channel ds-flash \
    --raw pilot/polish/seg1-s2/calib/raw.ds-flash.jsonl
```

结果写进 `channel_state.json`，决定每条通道**本 SEG 的自动清关权初值**——`pass=False`
（或没跑过小考）都不阻止该通道产候选、走生产批，只是它的候选一律强制进人工裁决队列
（K 配额），不能自动清关。**这条闸不能跳过**：先出候选、后补小考，不能把已经产出的候选
"倒查"成已经开权限的样子——自动清关权只对小考**之后**产生的 triage 结果生效。

## 落地后（控制会话逐 session/批执行）

按 `docs/ops/p4-polish-runbook.md` §五～§七：

```bash
uv run python tools/polish_ingest.py --seg seg1-s2 --channel fable-wf --all
uv run python tools/polish_ingest.py --seg seg1-s2 --channel ds-flash --all
uv run python tools/polish_check.py --seg seg1-s2 --channel fable-wf
uv run python tools/polish_check.py --seg seg1-s2 --channel ds-flash
uv run python tools/polish_triage.py --seg seg1-s2
```

`triage.json` 的 `meta` 字段一定要看一眼（K=150 是本 SEG 总额、两通道共享；`sample_rate`
配置 10%，若被 K 压缩会显式告警，见 runbook §七）。

## 段末流程（回指 runbook，不在这里复述）

`queue.md` 逐条裁决 → append `decisions.jsonl`（原因码枚举：量词/语序/补主语/过度归化/术语/
口调/漂移/其他）→ **`polish_audit.py --seg seg1-s2`（抽检推翻率闸，段末强制跑，见 runbook
§八之后那一节）** → `polish_amplify.py --digest` → `--scan-prompt`（**每 SEG 限一轮**）→
放大扫描的输出**只走 `amplify` 这一个保留通道**（见下方"放大扫描的落盘路径"）→ 补充小裁决 →
`polish_commit.py`（**先 dry-run 人工核对倒查链，再 `--apply`，且必须
`--data-dir pilot/lanes/opus/data`**）→ 清关后必跑全段 W4 复检
（`polish_check.py --seg seg1-s2 --w4-full --lane-dir pilot/lanes/opus`）+
`check_qa_quotes.py --qa config/ayano_qa/*.yaml --data-dir pilot/lanes/opus/data`。

### 放大扫描的落盘路径（**不是两条通道各产一份**）

初版这里写的是"两条通道按同样的派发方式各自产出 `raw/<channel>/amplify` 批次"——**与工具契约
直接冲突，照做会静默零产出**（P4 最终评审 I3）：`polish_amplify.py` 固定 `channel="amplify"`，
`polish_ingest` 认领的路径是 `raw/amplify/b<N>.out`。按初版做的话，`raw/fable-wf/amplify`
这种路径不被任何 ingest 认领；改用 `--channel fable-wf` 回炉又会撞上批级幂等
（那些批号早已在 `ingested.fable-wf.json` 里）→ **no-op、零报错、零入仓，整轮放大扫描白跑**。

正确形态（与 runbook §九 一致）：

```
scan prompt：work/ctx/p4s1-amplify.md（一份，两条通道可以读同一份）
落盘路径：  /Users/fotile96/Zndnovel/pilot/polish/seg1-s2/raw/amplify/b<批号>.out
入仓：      uv run python tools/polish_ingest.py --seg seg1-s2 --channel amplify --all
```

两条通道若都要参与放大扫描，让它们写**同一个** `raw/amplify/` 目录下**不同批号**的文件
（批号由 scan prompt 的输出契约给定），不要各建一个通道目录。`amplify` 通道恒不自动清关
（与 `channel_state.json` 写了什么无关），产物只能进人裁。

**清关前的最后一道人工检查**：`polish_commit.py`（无 `--apply`）的 dry-run 输出会逐条打印
"倒查链：id → 候选(channel, ts) → prompt_hash"——核对这条链确实指向你认可的那次裁决，
且 `⚠ id 已有 N 条 patch` 的告警（若出现）已被人工看过、排除"润色期间被其他会话动过"的疑虑，
才能加 `--apply`。

## 收尾确认

段全部走完后：

```bash
git status --short pilot/lanes/opus/data/    # 应只剩本轮新增的 patches.jsonl 改动（若已 apply）
git status --short pilot/polish/seg1-s2/     # 按 runbook §一 入库清单逐路径 add，不要 git add -A
uv run pytest -q                              # 确认全量测试仍绿
```
