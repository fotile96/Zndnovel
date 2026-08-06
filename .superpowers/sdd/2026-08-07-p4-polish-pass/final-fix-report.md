# P4 润色 pass —— 最终全分支评审修复轮报告

日期：2026-08-07。基线 706 passed → **758 passed**（净增 52 条测试）。
commit：`825ab2c` / `74af7dd` / `f262455` / `1c4bd22` / `eb78158` / `b889e97` / `96897c9`。

裁定范围：必修 3 Critical + 9 Important（C1/C2/C3、I1/I2/I3/I4/I5/I7/I8/I9）。
**明确不修**：I6、M1–M5、台账里九条 `minor (deferred)`——本轮**一个都没碰**（见文末核对）。
`tools/check_batch.py` 与 `tools/build_context.py` 全程未动（`git diff` 对这两个文件为空）。

---

## C1 陈旧 `gates.<channel>.json` ＝ 恒绿闸

**修法**：`gates.<channel>.json` 落盘结构改为
`{"checked_ids": [本次真正检查过的 id 全集（含全绿）], "findings": {id: {hard, warn}}}`；
`polish_triage.load_gates()` 相应返回 `{"checked_ids": set, "findings": dict}`；
`_eligible` 的机械闸判定拆成三段：**①文件在不在 → ②这个 id 在不在 `checked_ids` 里 →
③覆盖面内才谈 hard/warn**。

**为什么不是直接改 triage 判空**（评审已实测那样会让 7 条既有测试转红）：那 7 条测试钉住的
恰恰是"findings 里没有 ⇒ 干净"这个不安全推断，问题在于**信息本身不存在**——`gates.json` 里
根本没有"我查了哪些"这份事实，triage 无论怎么判都在猜。补上覆盖面之后，`load_gates` 在文件
层已有的"没有证据就不放行"才被贯彻到 id 层。

**旧格式兼容取安全方向**：读到无 `checked_ids` 的裸字典 → `checked_ids` 取**空集**（不是
"findings 的键集"、更不是"全部"），该通道本轮一律不许自动清关，并 stderr 播报"请重跑
polish_check"。当成"全部查过"就等于把这个洞原样保留。

**runbook**：§六 那句"每次新一批候选入仓后**建议**重跑"升级为**强制步骤**，并写明顺序
"ingest 这一批 → 重跑 gate → 再 triage"，附上不重跑的具体后果。

**测试**（新 6 条 + 改 9 条既有）
- 新：`test_stale_gates_id_not_checked_blocks_autoclear`、
  `test_stale_gates_end_to_end_new_candidate_not_autocleared`（不手改文件，走真实
  ingest→gate→append 新候选→triage 的链条，并验证**补跑 gate 后资格恢复**——证明拦的是
  "没查过"而不是把 id 永久打死）、`test_legacy_gates_format_blocks_autoclear_and_warns`、
  `test_all_green_candidates_empty_findings_but_checked_ids_recorded`（把"findings 空"与
  "checked_ids 空"两件事同时钉住）、落盘结构与 stray id 两条。
- 改：`tests/test_polish_check.py` 9 处断言从 `gates[...]` 改为 `gates["findings"][...]`。
  **逐条确认改的是"取值路径"而不是把断言放松**——每条改动后的断言语义与改动前逐字对应
  （`assert 12 in gates` → `assert 12 in findings`），另有两条**加严**：
  `test_gates_json_matches_return_value` 现在额外断言 `checked_ids` 覆盖全部三个非锁定 id
  （含两个全绿的、不在 findings 里的），`test_stray_candidate_id_skipped_not_crashed`
  现在额外断言游离 id 不进 `checked_ids`。
- 夹具改动：`tests/test_polish_triage.py` 的 `make_gate_hard` 改写新格式，新增
  `make_gate_warn` / `drop_from_checked` 两个 helper。

**变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M1 | `gate_checked = gates is not None`（不看 checked_ids） | `pytest tests/test_polish_triage.py -k "stale or legacy"` | **红 3 条** |
| M2 | 旧格式返回一个 `__contains__` 恒 True 的 checked_ids（当成"全都查过"） | `pytest tests/test_polish_triage.py -k legacy` | **红 1 条** |

---

## C2 纯控制码删除直通自动清关

分两半修，都落在 `polish_check`/`polish_triage` 一侧，**不动 `tools/check_batch.py`**。

### C2a 新硬规则 `P4-CTL`（`polish_check.ctl_violations()`）

判据：候选 `zh` 与 `frozen/opus.jsonl` 里该 id 的现行译文相比，**`_n` 条数、`_r` 条数、
ruby 组数三者各自必须相等**。落在 `hard` 里（不是 warn——warn 在整条 P4 流水线上此前零消费者，
放 warn 等于没写）。

判据宽窄的两处刻意选择（**"计数相等但位置移动"放行**，理由写在代码 docstring 与测试里）：

1. **只卡计数，不卡位置。** 润色改了中文字数之后把断行点前后挪一两个字是正当甚至必要的排版
   动作；卡位置会让几乎每条真实润色都变红，一周内这条闸就会被当噪音无视——那是"恒绿闸的镜像
   形态"。位置挪动的真实风险是"某一行变得过长"，而那正是 W3 的管辖面，W3 现已纳入 autoclear
   前置（见 C2b），不存在无人看管的缺口。
2. **`_n` 与 `_r` 分开数，不合并成总数。** 两者是引擎里不同的断行语义，`_n`→`_r` 对换会让
   总数不变而行为改变，且明确违反 prompt 任务说明第 4 条。分开数不引入任何伪报（正当润色本来
   就不该换断行码种类）。

**为什么顺带把 ruby 组数也算进去**（超出 finding 字面的 `_n`/`_r`）：R2a 只检查"写出来的 ruby
良不良构"，**整组 ruby 被删掉它一声不吭**——与 `_n` 被删完全同型的静默丢失，同一条判据（计数
相等、位置自由）一并覆盖，零额外伪报面。

### C2b W3 行宽 warn 纳入 autoclear 前置

`_row_eligible` 追加 `no_w3`。其余 warn（W1/W2/W4）**保持不阻断**，取舍与实测依据：

- **W3 是唯一对应真实游戏内故障的 warn**（中文比日文占宽，溢出玩家一眼看得见）。
- **实测伪报面**：对 SEG-1 的 1996 行**现行 opus 译文**跑 W3 判据，命中 **5 行（0.3%）**。
  即真实语料上 W3 是窄闸、高信号，纳入前置不会把自动清关整条通道淹掉。
- W1 是 jp↔zh 断行数差的粗略提示（真正的控制码保全已由 P4-CTL 硬规则接管，W1 阈值 ≥2 本就
  抓不住单个删除）；W2 是术语提示；W4 在候选级根本不跑（归口 `w4_full`）。把它们一并阻断
  会让免检通道形同虚设，而它们各自都有更合适的归口。这条取舍有参数化测试落盘
  （`test_other_warns_do_not_block_autoclear[W1/W2/W4]`）。

**夹具修正的说明（不是放松断言）**：`_build_mini_overload` 原来的合成语料 zh 比 jp 还长，
**每一条**小改候选都会挂 W3 → 整个夹具产不出 autoclear 候选，两条 K 帽不变量测试测不到它们
本来要测的东西。改为 jp 长于 zh（与真实语料一致，见上面 0.3% 的实测）。这是夹具脱离现实，
不是判据过严。

**测试**（新 6 条）：`test_ctl_drop_n_is_hard`、`test_ctl_swap_n_for_r_is_hard`、
`test_ctl_position_move_is_allowed`（反向锁：只挪位置不报）、`test_ruby_drop_is_hard`、
`test_ctl_unchanged_candidates_stay_green`（反向锁：什么都没改不报）、
`test_ctl_violations_unit`；triage 侧 `test_w3_warn_blocks_autoclear` +
参数化 `test_other_warns_do_not_block_autoclear`。

**变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M3 | `for i in []`（P4-CTL 整条不跑） | `pytest tests/test_polish_check.py -k "ctl or ruby_drop"` | **红 3 条** |
| M4 | `_n`/`_r` 合并成一个总数计数器 | `pytest tests/test_polish_check.py -k ctl` | **红 2 条**（含专测对换的那条） |
| M5 | `no_w3 = True`（W3 不阻断） | `pytest tests/test_polish_triage.py -k warn` | **红 1 条**，另 4 条 W1/W2/W4 反向锁保持绿 |

---

## C3 清关后全段 W4 复检不可执行

**复现确认**：`uv run python tools/check_batch.py --batch 36 --lane-dir pilot/lanes/opus` →
`FileNotFoundError: work/ctx/batch_36/source.jsonl`。

**修法**：`polish_check.w4_full(label, lane_dir)` + CLI `--w4-full --lane-dir`。
判定面：**id 集 = `frozen/source.jsonl` 全段**（不只本轮清关的 id——被改的那条和没被改的兄弟
条都要能报出来）× **文本 = 车道现行译文**（`resolve_map(forward, patches)`）× **索引 =
`check_batch.load_siblings` 的全库兄弟索引**。结果落 `w4_full.json` + stderr 明细。

**rc 语义**：`0` = 跑完了（W4 是 P3 既定的顾问级规则，不自动阻断）；**`2` = 没能跑**
（索引建不起来 → 抛 `W4NotAvailable`，绝不返回空清单冒充绿）。"没能跑"与"跑了没问题"在退出码
上就可区分——这正是原 finding 的核心（命令跑不起来 = 闸不存在）。

**runbook §十一 第 1 步已换成这条真能跑的命令**，并写明 rc 语义与"为什么旧命令查的是错的文本"。

**真实数据实跑**：`polish_check.py --seg seg1-s2 --w4-full --lane-dir pilot/lanes/opus`
→ rc=0，**9 处**既有复现句族不一致（0.2s）。这 9 处是润色开始**之前**就存在的，已作为基线
入库（`96897c9`），清关后重跑时新增的才是本轮润色引入的。

**测试**（新 5 条）+ **变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M6 | 索引建不起来时 `return []` 而不是抛异常 | `pytest tests/test_polish_check.py -k w4` | **红 2 条**（含 CLI rc=2） |
| M7 | 只扫"本轮有 patch 的 id"而不是全段 | 同上 | **红 2 条** |

---

## I1 handoff 里四个 `prompt_hash` 全部过期

**修法**：handoff 不再抄哈希表——**`plan.json` 是唯一真相源**，handoff 给出核对命令
（`shasum -a 256 work/ctx/p4s1-s<N>.md` vs 从 `plan.json` 取同 session 的记录）。
根因是"同一个易变值记在两处"，所以修法不是把表更新一遍（下次改 prompt 还会脱钩），而是
**删掉其中一处**。会话分组表保留（批号/行数是段表的稳定事实，不随 prompt 文本变）。

## I2 提示词指向不存在的节名

`"一、任务说明"`/`"七、输出契约"` → `「## 任务说明（润色契约）」`/`「## 输出契约」`。
实测核对：两串在真实渲染稿 `work/ctx/p4s1-s1.md` 里 grep 计数各为 **1**。

## I3 amplify 派发指令与工具契约冲突

handoff 段末流程改写，新增"放大扫描的落盘路径"一节，写明：scan prompt 一份、落盘固定
`raw/amplify/b<N>.out`、入仓固定 `--channel amplify`；并写明照初版做的两条死路
（路径不被认领 / 换回原通道名撞批级幂等 → no-op 零报错零入仓）。runbook 纪律速记同步加一条。

---

## I4 `manifest.opus_at` 无消费者 → 自动清关可覆盖人裁定稿

**修法**：`polish_commit._post_freeze_rulings()` 以 `opus_at.patches_lines` 为基线（
`patches.jsonl` append-only，之后的行都是冻结后新增的），取其中 `reason ∈ {review, recall}`
的行；`commit()` 写每条 patch 之前比对：

- `verdict="auto"` 命中 → **拒绝写入**（dry-run 预览里同样不出现——预览与实写必须给同一个
  答案），stderr 打出冲突详情与"要落它必须走人裁"的出路；
- 人裁路径（adopt/edit）**放行但显著播报**——那条路上有人正看着这个 id，他有权知情覆盖；
- 基线建不起来（manifest 缺 `opus_at`／`patches.jsonl` 比基线还短）→ **保守放大**：全部
  review/recall patch 都当成冻结后的。"算不出来"绝不等于"放行"。

**测试**（新 7 条）：拒写、dry-run 同样拒写、人裁放行且播报、
**两条反向锁**（冻结**前**的 review patch 不拦、冻结后的 `reason=polish` patch 不拦——否则
同一 SEG 第二次 commit 寸步难行）、两条保守分支。

**变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M8 | 去掉 `verdict=="auto"` 的拒写分支 | `pytest tests/test_polish_commit.py -k "refuse or conservative or post_freeze"` | **红 4 条** |
| M9 | 基线算不出来时 `return {}`（放行） | `pytest tests/test_polish_commit.py -k conservative` | **红 1 条**（另一条走 elif 分支、由它自己的测试覆盖，M9 打不中它——不是测试无牙） |

## I5 `polish_setup --seg` 对已在产 SEG 无护栏

**修法**：`in_production(d)` 判据 = 目录下存在 `candidates.*.jsonl` / `decisions.jsonl` /
`triage.json` 任何一个；命中且无 `force` → `SegInProductionError`，**抛在任何文件被删除或
写入之前**（CLI rc=3，`--force` 强制）。拒绝信息逐条列出重跑会静默毁掉的四项基准。

**测试**（新 6 条）：三种在产产物各一（参数化）、`test_refusal_destroys_nothing`（拒绝前后
目录树逐字节比对）、`--force` 放行且 `verify()` 仍绿、**反向锁**（无在产产物时重跑照常放行
——SEG-1 这类"已冻结未点火"的段仍可重冻结）、CLI rc=3 → `--force` rc=0。

**变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M10 | 拒绝闸恒不触发 | `pytest tests/test_polish_setup.py -k "production or refusal or force or rc3"` | **红 5 条** |
| M11 | 闸设在 `rmtree` **之后**（照样抛异常，但 frozen/ 已毁） | 同上 | **红 1 条**（只有 `test_refusal_destroys_nothing` 红——正是它该抓的那一条） |

## I7 推翻率闸只有文档没有代码

**新工具 `tools/polish_audit.py`**：读 `triage.json` 里 `autoclear and sampled` 的行 ×
`decisions.jsonl` 的**人裁** verdict，算每通道推翻率；`rate >= CFG["overturn_freeze"]` →
改写 `channel_state.json` 关闭该通道自动清关权（`autoclear=False` +
`autoclear_frozen_by/overturn_rate/frozen_ts`），并列出需回滚复审的存量自动清关 patch id。

判据（写进 docstring 的真值表）：`adopt` 且 `chosen_channel==本通道` → 不算推翻；
`adopt` 别家 / `edit` / `keep_opus` → 算推翻；`verdict="auto"` **不算人裁**（算了的话抽检就
自我背书，推翻率恒 0——这条闸会变成恒绿）；尚无人裁 → 不进分母但**播报待裁数**。

两个自行裁定，都写在代码里：
- **边界取 `>=`**（`config/polish.yaml` 该行注释写的就是"≥ 此值 → 冻结"，spec §5 散文写
  ">20%"）——只在恰好 0.20 时有别，向安全侧靠。
- **默认就写盘**，`--dry-run` 才只报不改：关权是安全方向的动作，不该需要额外开关才肯生效。
- **存量回滚不在本工具里做**：生产 `patches.jsonl` 只经 `polish_commit --apply`/`add_patch.py`
  写入（2026-08-02 事故的防线），本工具只关权 + 精确列出待回滚 id。

**配套（本轮自己发现的新洞）**：`polish_calibrate.score()` 原来整条覆盖该通道条目——
**重跑一次准入小考就能把本闸刚落的冻结悄悄解开**。改为保留原条目其它键，且看到
`autoclear_frozen_by` 时即使小考满分也强制判 `pass=False` 并播报。

**runbook**：新增 **§八之二**（段末强制步骤，带具体命令与判据说明），§十二 那句"这条闸没有
专属 CLI"改写。

**测试**（新文件 `tests/test_polish_audit.py`，14 条）+ **变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M12 | 超线只播报、不真的改 `channel_state.json` | `pytest tests/test_polish_audit.py` | **红 3 条** |
| M13 | `verdict="auto"` 也算人裁 | 同上 | **红 1 条** |
| M14 | `score()` 无视 `autoclear_frozen_by`（小考可解冻） | `pytest tests/test_polish_audit.py tests/test_polish_calibrate.py` | **红 1 条**，既有 calibrate 测试全绿（改动向后兼容） |

## I8 `glossary/polish.md` §7 自称"谁也看不见"

**修法**：§7 改写为「现在谁看得见这份文件」——7.1 三个面的现状表（P4 润色 pass **看得见，
整篇**；opus 正文轨看不见（有意，附机制）；`reviewer_cc` 看不见（有意，附理由））、
7.2 opus 车道排除机制（原文保留）、7.3 **改本文要连带做什么**（点火前/点火后两条路径）。
文首那句"尚未接入任何生产指令"同步改正。

**§1–§6 逐字未动**：`git diff -U0` 的 hunk 全部落在第 3 行与 ≥105 行（§7），13–103 行零改动。

**一处自查修正**：改写初稿在 §7 引言里引用了旧措辞原文（"这份文件现在谁也看不见……等于没
写"），渲染后 grep 到它在 prompt 里出现 2 次——**同一个问题换了个引号又回来了**。改为只说
"此前描述的是 2026-08-04 的状态"，把原文指向 git 历史与本报告。重渲染后
`grep -c "谁也看不见" work/ctx/p4s1-s1.md` = **0**。

## I9 校准批没有渲染器

**修法**：`polish_context.render_calib()` + CLI `--calib`。与 `render()` **共用**
`_frozen_blocks()`（任务说明 / `active.json` / `style.md` / `polish.md` / 口调表 / 锚点 /
章节纪要 / 裁决纪要 —— 同构靠共用同一段代码保证，不靠两处各自维护相似的拼接），差异只有
两处：正文换成 `calib/<label>.batch.jsonl` 的行、输出契约换成单文件
`calib/raw.<channel>.jsonl`。**不带锁标**（校准批取样时已排除锁定 id；"锁定 id 清单"一节
保留并写明"本校准批不含锁定 id"，因为任务说明第 1 条引用它）。
刻意**不写 `plan.json`**：那份记录是给 `polish_ingest` 反查生产批 prompt_hash 用的，
而校准批的输出绝不入仓。

**测试**（新 5 条）+ **变异**
| # | 变异 | 命令 | 结果 |
|---|---|---|---|
| M15 | `truth.json` 内容拼进 prompt | `pytest tests/test_polish_context.py -k calib` | **红 1 条**（`test_calib_prompt_never_contains_truth`） |
| M16 | 丢掉任务说明/术语/口调，只剩正文 | 同上 | **红 3 条** |

一处测试自查：`test_calib_prompt_has_no_lock_marks` 初版断言 `"【锁】" not in prompt`
**首跑即红**——因为共用的任务说明里本来就有"带【锁】标记的 id"这句话（那是同构的一部分）。
诊断为**断言写错了对象**（要卡的是"清单里真的标出了某个 id"，即 `- 【锁】<id>（…）` 行），
改为按行首匹配，并**加一条对照断言**：同一夹具下生产 prompt 确实会产出这种行——否则新断言
会因为"这种行本来就不存在"而恒真。

---

## 变异汇总

16 个变异，**16 个全部真红**，无绿变异，故无需区分"测试无牙"与"变异没打中"。
一处需要说明的部分命中：**M9**（I4 的基线放行）只红了 1 条，另一条保守分支测试
（`test_shrunken_patches_file_is_conservative`）保持绿——那条走的是 `elif baseline > len(rows)`
另一个分支，M9 物理上打不中它；该分支有自己的专测，不是测试无牙。

全部变异一律用 Edit 应用与还原，**未使用任何 git 回滚类命令**。收尾
`grep -rn "MUTATION" tools/ tests/` → 无残留；`git diff --stat` 只含本轮真实改动。

## SEG-1 重冻结与重渲染

顺序：先落 I5 护栏 → 再改 `glossary/polish.md` → 再重冻结。SEG-1 **尚未点火**（无
`candidates.*.jsonl`/`decisions.jsonl`/`triage.json`），护栏判定放行，**未使用 `--force`**。

核对（重冻结前先把旧产物拷进 scratchpad 逐一比对）：
- `frozen/source.jsonl`、`frozen/opus.jsonl`、`frozen/locked.json` 与重冻结前**逐字节相同**
  （车道数据全程未动，`git status --short pilot/lanes/opus/data/` 始终为空）；
- `manifest.json` 的 19 个文件哈希里**只有 `frozen/glossary/polish.md` 变了**，顶层只有 `ts` 变；
- 校准批 20 行的 10 条陪考句 `opus_zh` 与新冻结面**零差异**（随机种子取自 `source.jsonl`
  哈希，未变 ⇒ 抽样不漂移），`calib/` 无需重造；
- 四个 session prompt 已重渲染，`plan.json` 四个 `prompt_hash` 用 `shasum -a 256` **独立重算
  逐个吻合**：`43401b0b…` / `c1f08389…` / `66251482…` / `d1a57de3…`；
- 校准批 prompt 也已渲染一份（`work/ctx/p4s1-calib.md`，4308 行，`grep is_gold` = 0）；
- `polish_setup.py --verify seg1-s2` → 无漂移；渲染稿顶层带编号标题 grep = 0。

---

## 明确不修的，本轮确认未碰

- **I6**（纪要前馈未实现 + `frozen/` gitignore 导致 clean checkout 丢失）：未碰。
- **M1–M5**：未碰。
- 台账九条 `minor (deferred)`：未碰。其中一条与本轮有交集但**刻意未顺手改**——
  `OUTPUT_CONTRACT_HEADER` 硬编码"最后 8 个字符"未插值 `CFG["jp_tail_n"]`：新写的
  `CALIB_OUTPUT_CONTRACT` 用了 `%d` 插值（新代码不该复制旧瑕疵），但**没有回头改生产那份**
  ——那是 deferred 名单上的条目，改它会让四个 session 的 `prompt_hash` 再动一次。
- `tools/check_batch.py`、`tools/build_context.py`：`git diff` 对这两个文件为空。
- `.claude/settings.json`、`data/api_ledger.jsonl`：全程未 add、未修改（工作树里它们的改动
  是其他会话的，收尾时仍在）。
- `pilot/lanes/opus/data/`：`git status --short` 为空，`polish_commit --apply` 一次也没跑过。

## 未完全解决 / 需要下一手知道的

1. **I7 的存量回滚仍是人工**（有意，见上）。工具只关权 + 列出待回滚 id；真正撤销要人逐条用
   `add_patch.py` 落 `reason=review`。这条依赖操作者执行，**没有机械兜底**。
2. **`polish_audit` 缺 triage.json 时抛 `FileNotFoundError`（带可读消息）而非友好退出**——
   与 `polish_amplify.scan_prompt()` 既有的同类行为一致（台账里已记为 deferred minor），
   本轮沿用未改。
3. **P4-CTL 只卡计数不卡内容**：ruby 组数相等但注音文字被改写、`_n` 位置挪到不合理处，
   本闸不管。前者属润色裁量（人裁面），后者的真实风险由 W3 承接。这是有意的判据收窄，
   记录在案。
4. **W4 全段复检仍是 rc=0 顾问级**（命中不阻断）。沿用 P3 对 W4 的既定定位（同一日文在不同
   语境下偶有正当的不同处理）。"没能跑"用 rc=2 与之区分，但"跑了有命中"不会让流程停下——
   靠 runbook §十一 要求人工核对。若日后认为该硬化，改的是 CLI 退出码一行。
5. **`glossary/polish.md` 改动只对尚未点火的 SEG 生效**（已点火的 SEG 沿用其冻结版本，
   `setup()` 会拒绝重冻结）。这是冻结面的设计意图，但意味着**若 SEG-1 点火后再改 polish.md，
   SEG-1 的执行通道读到的仍是旧版**——已写进 §7.3。
