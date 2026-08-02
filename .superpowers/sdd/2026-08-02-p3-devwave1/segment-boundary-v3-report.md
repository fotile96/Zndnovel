# 段边界工具升级报告：`prod-run-v2` → `prod-run-v3`

- **日期**：2026-08-02
- **时机**：SEG-1（seg1-s2，b36–62，27 批）已完结、段末裁决已出 glossary v8 并完成双车道重冻结；
  **SEG-2（seg2-s3，b63–90）尚未开工** —— 符合 runbook §4「工具升级只在段边界」与
  「数据再生成只在段边界做，且必须确认生产会话不在跑批」的双重时机纪律。
- **依据流程**：`docs/ops/p3-production-runbook.md` §4 / §4.0 / §4.1。
- **结论**：**放行并已滚 `prod-run-v3`**。canary 差异全部为误报消失方向，**新增命中 0 条**。

---

## 0. 开工时的 `git status`

```
On branch main
Your branch is ahead of 'origin/main' by 3 commits.
nothing to commit, working tree clean
```

**工作树干净** —— 未发现生产会话的在制品（`glossary/` 下的 v8 相关改动已由生产/裁决会话
自行提交完毕，commit `4b06979` / `e84ad0b` / `f0ed4c5`）。故本次全程无需规避他人在制品，
但仍严格遵守「只 `git add` 实际改动路径」纪律，未使用 `git add -A` / `git add .`。

**全程未触碰**：`pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`、
`docs/superpowers/plans/translate-seg1-s2.md`、`data/batches.jsonl`、
`lua_scripts/`、`png/`、`analysis/`、`skeleton/`。未发任何真实 API 请求。

---

## 1. 漂移面盘点

`git diff --stat prod-run-v2 main -- tools/ prompts/`：**9 文件，+1303 / −37 行**

| 文件 | 变动 | 是否在按批四件套内 | 是否在 canary 覆盖面内 |
|---|---|---|---|
| `tools/detect_collapse.py` | +66/−… | ✅ 是 | ✅ 是 |
| `tools/canary.py` | +7 | 否（闸门自身） | — |
| `tools/build_ledger.py` | +13 | 否 | ❌ 否 |
| `tools/gen_timeline.py` | +13 | 否 | ❌ 否 |
| `tools/gen_plan.py` | +103 | 否 | ❌ 否 |
| `tools/saturation.py` | +159 | 否 | ❌ 否 |
| `tools/cluster_notes.py` | +174（新增） | 否 | ❌ 否 |
| `tools/api_client.py` | +495（新增） | 否 | ❌ 否 |
| `tools/ayano_test.py` | +310（新增） | 否 | ❌ 否 |

**`prompts/` 零改动** —— §1 划入钉死面的 `translator_cc.md` / `reviewer_cc.md` 守住了。

**按批四件套（`build_context` / `check_batch` / `detect_collapse` / `append_forward`）中
只有 `detect_collapse` 变了**，而 canary 覆盖的正是 `check_batch` + `detect_collapse`
——覆盖面与本次变更恰好吻合，故本次**跑** canary（不是免跑）。

---

## 2. 第一件事：F9 取舍的用户签字留痕

runbook §4.0 此前只**陈述**了 A/B 召回表与「此判断必须由人显式做出并留痕」的要求，
但**判断本身一直空缺**。本次已将用户 2026-08-02 的裁决逐字签进 §4.0（A/B 表之后），
措辞明确标注「已签字 ✅」「这个取舍已经由人显式做过判断，不是没人管」。

签入内容摘要（原文见 runbook §4.0）：

- **裁决**：接受现状，只留痕不加闸 —— 保留 F9 逐行豁免，**不**增设批级聚合闸。
- **明确接受的代价**：「照抄 + 前后各加中文短语」C1 召回停在约 **54%**（终审 A/B 表最坏行）；
  「照抄 + 标点换中文」约 **78%**。
- **支持证据**：① 已完成 62 批（P2 的 35 + SEG-1 的 27）**真阳性 0 条**——SEG-1 单段
  53 条 collapse + 7 条 warn 全为误报；② 降噪收益真实：已入线真实译文 C1 命中 **27 → 8**
  （消 19，新增 0）。
- **曾评估但未采纳的替代方案**（留档备查）：逐行豁免**之前**的批级残留假名比闸。
  62 批批级比值中位 **0.00000**、最大 **0.00913**（batch 19 钱仙拼字段），整批照抄约 **0.479**
  ——差 **52 倍**；阈值 **0.05** 可对 62 批零误报（5.5 倍余量）、对整批照抄近 10 倍冗余；
  该指标在豁免之前算，天然不受逐行豁免影响。**未采纳理由：用户判断当前风险画像下
  不值得再加机制**（非该方案无效，亦非没想到）。

Commit：`18cc77c`。

---

## 3. 第二件事：canary 双树比对

### 3.1 执行姿势

**cwd 恒为主仓** `/Users/fotile96/Zndnovel`（未 `cd` 到生产树）。

```bash
# 旧树（prod-run-v2），工具用生产树绝对路径，数据指主仓车道
uv run python /Users/fotile96/Zndnovel-prod/tools/canary.py \
  --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --batches 36-62 \
  --out <scratchpad>/canary-old.json      # → canary: 27 批判定已写 …

# 新树（main）
uv run python /Users/fotile96/Zndnovel/tools/canary.py \
  --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --batches 36-62 \
  --out <scratchpad>/canary-new.json      # → canary: 27 批判定已写 …

uv run python tools/canary.py --diff <scratchpad>/canary-old.json <scratchpad>/canary-new.json
```

- **批次范围**：`36-62` = 最近完成的那一段（SEG-1 全段 27 批）。
- **未加 `--regen-ctx`**：本次升级不触及 `build_context`（其文件与 prod-run-v2 逐字节相同），
  故无需重生 ctx，也就避开了 §4 警告的「覆写生产车道 `work/ctx`、跨 glossary 版本后
  拿不回入线时刻 ctx」的风险。
- 输出全部落 scratchpad，**未在仓库留任何文件**。
- 旧树 `canary.py` 第 10 行 `sys.path.insert(0, Path(__file__).resolve().parent.parent)`
  已核实 —— 它加载的是**生产树自己的** `tools/pipelib` / `check_batch` / `detect_collapse`，
  钉死语义真实成立。

### 3.2 `--diff` 原始输出

```
batch 45: hard 0->0, warn 0->0, collapse 2->1
batch 56: hard 0->0, warn 0->0, collapse 13->12
canary diff: 2 批有差异
```

### 3.3 集合级比对（不只比计数）

`--diff` 只报计数，**计数相同也可能是「消一条又增一条」**，故另做逐条集合级比对
（脚本 `<scratchpad>/canary_detail.py`，按 `json.dumps(sort_keys=True)` 归一化后取多重集差）：

- 单批结构为 `{"check": {"hard": [...], "warn": [...]}, "collapse": [...]}`。
- **`check` 半边：27 批逐批深比较完全恒等**（`[b for b in old if old[b]['check']!=new[b]['check']]` → `[]`）
  —— 与 `check_batch` 零改动相符。
- **`collapse` 半边**：27 批总命中 **53 → 51**；深比较有差异的批次仅 `['45', '56']`。

### 3.4 差异逐条清单

| 批次 | rule | 方向 | 消失的命中 | 对应原文 / 译文 | 判定 |
|---|---|---|---|---|---|
| 45 | **C1** | 消失 | `id 9719：残留假名比 0.026 > 0.02（疑似原文未译）` | JP `【アヤノ】「ゆ、ユウイチこそ、今日はやけに急いでるんじゃないの？ いつもはもっとダラダラしてるのに」`<br>ZH `【アヤノ】「ユ、ユウイチ你才是，今天不是急得反常吗？ 平时明明都磨磨蹭蹭的」` | **真误报**：译文里的「残留假名」是**保留的片假名人名 `ユウイチ` 及其结巴重复 `ユ、`**，并非未译原文 |
| 56 | **C1** | 消失 | `id 10041：残留假名比 0.045 > 0.02（疑似原文未译）` | JP `【アヤノ】「ゆ、ユウイチ……だ、大丈夫？」`<br>ZH `【アヤノ】「ユ、ユウイチ……你、你没事吧？」` | **真误报**，与上条同一形态（结巴重复的保留人名） |

**统计汇总**：消失 **2** 条，新增 **0** 条。涉及 rule 仅 **C1** 一种；hard / warn / C2 及其余
rule 均**零变动**。

### 3.5 canary 人工判定

> **✅ 差异全部是误报消失方向（C1 减少），没有任何新增命中。**

两条消失的命中都是 F9 豁免的**目标形态**：`ユ、ユウイチ` 是按项目术语纪律**必须保留**的
片假名角色名（CLAUDE.md：片假名【アヤノ】【ユウイチ】= 故事层角色，与汉字现实层角色
两套写法必须区分），其结巴重复片段 `ユ、` 此前未被 `retained_names` 覆盖而被计入残留
假名比。消除它们是**零信息损失的纯降噪**。

**放行**。召回侧的代价不由 canary 判定（canary 重放的是已入线好译文，结构上看不到召回
变化，见 §4.1），该代价已由 §4.0 的用户签字裁决明确承担。

### 3.6 切换后冒烟（额外验证）

滚 tag 并 checkout 后，用**新生产树**重跑同一条 canary 命令：

```
cmp canary-prodv3.json canary-new.json  → 逐字节相同 ✅
```

证明生产树确实已经是新代码，且其判定与 main 一致。

---

## 4. canary 覆盖不到的工具：逐个点名结论

runbook §4.1 明列 canary 只重算 `check_batch.check` 与 `detect_collapse.scan`
（加 `--regen-ctx` 时另含 `build_context`）。其余一律人工判定，逐个如下：

| # | 工具 | 有无行为变更 | 对**在产批次**的影响 | 判定依据 |
|---|---|---|---|---|
| 1 | `build_ledger` | **有**（F7：`parse_vms_lines` 新增 `line` 字段，记 vms 在 lua 源文件的 1-based 行号） | **无影响** | **纯增字段**，`build()` 的全局排序仍按 id 不变（见其代码注释）。判定依据是台账已留痕的 **A/B 实验**：钉死生产树的 `build_context` 在只差 ledger 的两个镜像仓上跑 batch 100，`context.md` / `source.jsonl` / `manifest.json` **逐字节相同**（devwave1 task-3 报告，落码 `b285048`） |
| 2 | `gen_timeline` | **有**（F7：`_ids_for` 的 `sorted(set(ids))` 改为 `key=lambda i: (*self.pos.get(i, ("", 0)), i)`，即按 `(file, line)` 行序排） | **有影响，且已随本次一并落地** —— 前缀正文顺序会变，属生产条件变更 | 本段边界同步再生 `data/timeline.jsonl`，差异形态逐项核对通过（见 §5） |
| 3 | `gen_plan` | **有**（`segment_range` → `segment_entry` + 新 `segment_subrange` 段子区间；`_segment_head` 增 `segment_sub` 参数；段头/段尾文案同步） | **不影响在产批次** | 只在**生成计划时**运行，产出物是 md 计划文件；在产计划不重新生成。改动全部落在 `_segment_head` / `segment_entry` / `segment_subrange` / `main` 四处，无一进入批次执行路径 |
| 4 | `saturation` | **有**（新增 `split_compound_candidates` 并列词串探测、`corpus_chars_from_ledger`、`is_clean_key` 脏键判据；`main` 增说明性输出） | **不参与批次生产** | 段末裁决会话的证据表工具，**饱和度算法本身一字未动**；改动全为新增 helper 函数 + `main` 的输出分支 |
| 5 | `cluster_notes` | **新增工具**（prod-run-v2 时不存在） | **不参与批次生产** | 裁决会话聚卷宗用（`--out work/out/dossier-<label>.md`） |
| 6 | `api_client` | **新增工具** | **不参与批次生产** | 彩野测试走 deepseek Responses API 的 HTTP 客户端；本次**未发任何真实 API 请求** |
| 7 | `ayano_test` | **新增工具** | **不参与批次生产**；对**车道数据风险为零**（只读车道，不写车道任何文件） | 段末验收工具。⚠ 注意 §4.1 已记的边界：它会向仓库跟踪的 `data/api_ledger.jsonl` 追加计费台账且无 CLI 开关改路径 —— 本次未运行它，故 `api_ledger.jsonl` 无改动 |

**一条可核验的加固事实**：实测 `grep -n 'import' tools/{build_context,check_batch,detect_collapse,append_forward}.py`
过滤上述 7 个模块名 → **结果为空**。即按批四件套对这 7 者的 import 依赖为零，
「不参与批次生产」不是推断而是可核验的事实。

`canary.py` 自身也有 +7 行改动（纯 docstring：说明 `dumps` 的确定性来自固定字典插入顺序
而非 `sort_keys`），**无行为变更**，且它是闸门自身、不参与批次生产。

---

## 5. 第三件事：`data/timeline.jsonl` 再生（F7 后半截）

### 5.1 执行

```bash
uv run python tools/gen_timeline.py
# → scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693
```

（注：`gen_timeline.py` 与 `check_timeline.py` 均**无 argparse**，任何参数都会被忽略而直接执行。）

### 5.2 差异核对：与台账预期逐项比对

核对脚本 `<scratchpad>/tl_verify.py`，基线取 `git show HEAD:data/timeline.jsonl`：

```
行数 old=533 new=533  相等=True
有差异的 unit 数 = 14；违反预期形态的 = 0
```

**形态校验**（三条硬断言，任一不满足即计入「违反」）：
1. 字段集合不变 → 0 例违反；
2. **差异字段恒为 `["ids"]` 单项** → 0 例违反；
3. **`sorted(ids)` 逐行不变（id 集合不变）** → 0 例违反。

即：**差异严格且仅为 14 个 unit 的 `ids` 重排，id 集合与其余字段逐行不变** —— 与预期完全吻合。

### 5.3 seq 清单逐项核对

```
实际 seq 清单 = [10, 14, 23, 82, 167, 181, 234, 253, 266, 334, 343, 353, 363, 373]
台账 seq 清单 = [10, 14, 23, 82, 167, 181, 234, 253, 266, 334, 343, 353, 363, 373]
一致 = True
```

**14/14 逐项一致，无多余、无缺失。** 明细：

| seq | state / title | len(ids) | 位次变动数 |
|---|---|---|---|
| 10 | `s1s_20` 夏の朝、高校までの通学路 | 75 | 75 |
| 14 | `s1s_30` 放課後の約束 | 59 | 39 |
| 23 | `s1s_37` 約束を思い出せない | 103 | 84 |
| 82 | `s1s_330` 誰かが呼んでた | 66 | 24 |
| 167 | `s2s_293` オマジナイ、成功……？ | 16 | 8 |
| 181 | `snr_s2_10_f` | 429 | 15 |
| 234 | `s3s_340` 陸上部のウワサ | 21 | 2 |
| 253 | `s3s_380` 走り去るアヤノ | 64 | 59 |
| 266 | `snr_s3_10_fa` | 423 | 44 |
| 334 | `snr_s4_10_fa` | 600 | 524 |
| 343 | `snr_s4_10_fb` | 447 | 15 |
| 353 | `snr_s3_10_fb` | 263 | 262 |
| 363 | `s3fc-80` 手帳のメモ | 35 | 5 |
| 373 | `s5s_20` サクラさん | 78 | 25 |

典型例证与 `gen_timeline` 注释所记一致：**seq=14（`s1s_30`）里 id `17181` 由末位（旧位次 58）
移到第 20 位** —— 正是「后补的行消息号最大却应排在中间」的 F7 病征。同理 seq=10 的 `17185`
由末位移至位次 3、seq=334 的 `17192` 由末位移至位次 76。

### 5.4 后置校验

```bash
uv run python tools/check_timeline.py        # → OK   (rc=0)
```

**单元内行序逆序数**（按 timeline 单元分组、数 `line` 递减的相邻对，即 `build_ledger`
注释里 21/16248 的那个口径）：

```
单元内行序逆序数 = 0/16248
```

**修复前 21/16248 → 修复后 0/16248**，与台账记载一致。

### 5.5 覆盖面边界（未修的那一半，重申）

按 runbook §4「F7 覆盖面残留」：本次再生**只修前缀正文顺序**（`timeline.jsonl` 单元内 id 次序，
`build_context._render_prefix` 按 `unit["ids"]` 渲染）。**批次自身 `source.jsonl` 的行序不在
覆盖面内** —— `build_context` 组装 source 走 `for i in b["ids"]` 直取 `data/batches.jsonl`，
而后者**已冻结、不得再生成**（manifest 哈希锁定）。本次**未触碰** `data/batches.jsonl`。

Commit：`bb65909`。

---

## 6. 第四件事：滚 `prod-run-v3`

在上述三件事**全部完成并提交之后**执行（tag 因而包含它们）：

```bash
git tag prod-run-v3
git -C /Users/fotile96/Zndnovel-prod checkout prod-run-v3
```

### 6.1 验证输出

```
$ git -C /Users/fotile96/Zndnovel-prod checkout prod-run-v3
Previous HEAD position was 0aaee66 docs: canary 免跑判定留痕补全 saturation（prod-run-v2 已打并切至生产树）
HEAD is now at 6ad593f docs: 段边界升级判定记录 + 当前生产 tag 切到 prod-run-v3

$ git -C /Users/fotile96/Zndnovel-prod describe --tags
prod-run-v3                                   ✅ 与期望一致

$ git -C /Users/fotile96/Zndnovel-prod status --short
                                              ✅ 空 —— worktree 干净
```

**按批四件套与 main 的一致性**：

```
build_context   : identical to main
check_batch     : identical to main
detect_collapse : identical to main
append_forward  : identical to main
```

**切换后冒烟**：新生产树重跑 `canary --batches 36-62`，输出与 `canary-new.json` **逐字节相同**。

### 6.2 两处「当前生产 tag」记录已更新

1. `docs/ops/p3-production-runbook.md` §2 尾：
   `**当前生产 tag：`prod-run-v3`**`（并加一行指向 §4.1 的判定记录）。
2. `docs/ops/p3-production-handoff.md` 自检段（第 29 行附近）：
   `# 应为 prod-run-v3（与 runbook「当前生产 tag」行一致）`。

### 6.3 失效的 seg1-s2 编号例外：改为历史注记

SEG-1 已完结，该例外已失效。**选择改为历史注记而非直接删除**，理由：`translate-seg1-s2.md`
这份旧编号计划仍在仓库里，将来有人回读该段台账/计划时会遇到编号差一位的现象；
留一条明确标注「已失效」的注记比凭空消失更不易造成误解，且注记明写「SEG-2 起照计划
执行即可，无需再做编号换算」，不会被误当作现行规则。

两处同步处理（原文只点名 handoff，但 runbook §5 有同一条例外，一并处理以免两边不一致）：

- `docs/ops/p3-production-handoff.md` 第 65 行：`⚠ 本段（seg1-s2）的例外` → `📌 历史注记（已失效，仅备查）`。
- `docs/ops/p3-production-runbook.md` §5 开头：同样改为 `📌 历史注记（已失效，仅备查）`。

Commit：`6ad593f`。

---

## 7. 收工时的 `git status` 对照

```
On branch main
Your branch is ahead of 'origin/main' by 7 commits.
nothing to commit, working tree clean
```

（本报告文件提交后。）

**与开工时对照**：开工 clean（ahead by 3）→ 收工 clean（ahead by 7），净增 4 个 commit
（3 个生产条件 + 1 个证据）。`prod-run-v3` 指向 `6ad593f`，即三件生产条件变更的末位 commit
—— 证据 commit `f84f3f3` 落在 tag 之后，不属于生产条件，符合预期。

**逐 commit 的 `git add` 路径**（全部显式，无 `-A` / `.`）：

| commit | 类型 | add 的路径 |
|---|---|---|
| `18cc77c` | docs | `docs/ops/p3-production-runbook.md` |
| `bb65909` | data | `data/timeline.jsonl` |
| `6ad593f` | docs | `docs/ops/p3-production-runbook.md` `docs/ops/p3-production-handoff.md` |
| （本报告） | docs | `.superpowers/sdd/2026-08-02-p3-devwave1/segment-boundary-v3-report.md`（`git add -f`，SDD 目录自忽略） |

**确认未动生产会话在制品**：开工时工作树即为 clean，`glossary/` 下的 v8 相关改动已由裁决
会话自行提交（`4b06979` / `e84ad0b` / `f0ed4c5`），本次全程未 `git add` 任何 `glossary/`、
`pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`、
`docs/superpowers/plans/` 下的路径。

---

## 8. 测试基线

```
$ uv run pytest -q
327 passed in 2.10s
```

与基线 **327 passed** 一致，每次提交前均已确认全绿。
（含 `tests/test_detect_collapse.py::test_f9_known_recall_gap_copy_wrapped_in_chinese_phrases`
—— 该用例断言的是**当前的漏报事实**，它保持绿色即表示 §4.0 的取舍未被人偷偷改动。）

---

## 9. 遗留事项 / 交接提醒

1. **handoff 的段名尚未切到 SEG-2**：`docs/ops/p3-production-handoff.md` 第 4 行「当前段：
   **seg1-s2**」与第 11 行「本次执行检查段 **seg1-s2**」仍是旧段名。这属于 handoff §「换段时
   改什么」的第 1、2 步（生成 `translate-seg2-s3.md` 计划 + 换段名），**不在本次工具升级的
   范围内**，留给开 SEG-2 的会话执行。本次只改了自检段的 tag 期望值。
2. **生成 SEG-2 计划时务必带 `--tools-root /Users/fotile96/Zndnovel-prod`** —— 漏传会产出
   「自称已钉死、实则裸相对路径」的计划。生成后检查 Run 行确实带生产树前缀。
3. **SEG-2 的彩野题库** `config/ayano_qa/seg2-s3.yaml` 若尚未产出，段末 `ayano_test` 会以
   **rc=2** 打印跳过提示（与 rc=1 的真失败刻意区分），照实记进段末台账即可。
4. 本次未运行 `ayano_test`，故 `data/api_ledger.jsonl` 无改动。
