# SEG-2 准备三件小改动——报告

> 上游：SEG-1（seg1-s2）P4 润色 pass 首个 SEG 跑完后，用户裁定的三条独立收尾项。
> 基线：`uv run pytest -q` 780 passed（改动前实测），本轮改完 **798 passed**（新增
> 18 条测试：Change 3 净 +4、Change 2 +13、Change 1 +1）。
> 全程未跑 `polish_setup`/`polish_commit --apply`，未碰
> `pilot/lanes/opus/data/`（`git status --short pilot/lanes/opus/data/` 收尾核对为空），
> 未碰 `.claude/settings.json`/`data/api_ledger.jsonl`/`glossary/polish.md`（这三个文件
> 在会话开始时已是其他会话的未提交改动，本轮逐路径显式 add 时不包含它们）。

## 改动一：补上段表漏掉的开头段（SEG-0 → seg1-s0-s1）

### 实算数据

`data/batches.jsonl` 的 b1–35：**35 批、116282 jp_chars**（与用户给出的数字完全吻合），
lane 全部 `main`，chapter 分布（按批数）：`s1s 14 / crd 12 / s1f 3 / s0f 2 / sys 2 / s2s 2`
（同样与用户给出的实测一致）。id 范围 6060–9337（跨多个不连续区间，序章+第1章+相关卡片+
第2章开头两批）。

### 设计裁定

**label**：`seg1-s0-s1`。不用 `seg0-…`——`test_segments_labels_unique_and_ordered` 要求
`seg` 字段严格是 `1..N`（不含 0），叫"seg0"容易让人误以为对应 `seg: 0`。

**seg 编号 / 排序位置（关键裁定，非拍脑袋）**：新段插到列表**最前面**，编号 `seg: 1`；
原有 9 段的 `seg` 字段整体 **+1**（1–9 → 2–10），**`label` 字符串保持不变**（`seg1-s2`
现在 `seg` 字段是 2，`label` 前缀数字与 `seg` 字段从此不再逐位对应——这是历史命名遗留，
已在 `config/segments.yaml` 顶部注释里写清楚，不是打错）。

理由：`tools/ayano_test.py::_chapter_max_seg()`/`is_before_cur_seg()` 拿 `seg` 字段的
**数值大小**做反剧透卡组前缀的排序依据（`chapter_max_seg[ch] < cur_seg` 判定"这一章严格
早于当前段"）。若图省事把新段**追加到末尾**（`seg: 10`），会把 `chapter_max_seg["s0f"/"s1s"/
"s1f"]` 顶到 10——这三章原本靠 `PRE_P3_CHAPTERS` 白名单被硬编码成"确知早于全部段"（无条件
放行），新段一旦被表收录，`ch in chapter_max_seg` 分支会先于白名单命中，若这个值是 10，
则对 seg2–9 的**每一段**，`10 < cur_seg` 恒假——这三章的卡组前缀会从"无条件早于"静默退化成
"从不早于"，每一段的彩野测试 harness 前缀都会悄悄变薄。这正是"静默写错比报错更坏"的具体
案例，且是我在动手前推理出来、而非事后从测试报告里发现的——推理过程：
1. 读 `tools/ayano_test.py` 全文，发现 `PRE_P3_CHAPTERS = {"s0f","s1s","s1f"}` 与其注释
   "对应 b1–32/35，故 segments.yaml 里查不到它们"——这句注释本身就是"新增条目会改变这个
   不变量"的信号。
2. 手推 `is_before_cur_seg()` 的分支顺序：`ch in chapter_max_seg` 先于白名单判定，新增条目
   一旦让这三章"可查到"，白名单分支就变成死代码，真正生效的是数值比较。
3. 由此倒推：新段的 `seg` 数值必须小于全部既有段，唯一做法是插到最前面并整体重排后续编号。

**验证**（非合成 fixture，用仓库真实数据）：`tests/test_ayano_test.py::
test_real_card_chapter_data_gate` 直接读 `REPO` 下的真实 `config/segments.yaml` +
`config/card_chapter.yaml` + `skeleton/cards.zh.yaml` + `pilot/lanes/opus` 车道数据，对
**全部**段跑 `assemble_context()`。这条测试在我改完 `segments.yaml`（尚未改 `test_ayano_test.py`
本身）后**真红**过一次：

```
AssertionError: seg1-s0-s1（seg=1）前缀被滤空
assert 0 > 0
```

——这是**预期内的红**，不是新缺陷：新段是游玩顺序上真正最早的段，它之前没有任何"此前
剧情"，前缀卡数=0 才是正确答案；旧版"每段非空"断言的前提（每段都有非空前缀）只在"最早的
段恰好靠 `PRE_P3_CHAPTERS` 白名单借到别处的卡"这个巧合下成立，新增真正最早的段之后这个
巧合不再适用于它。修法：把断言改成"除游玩顺序最早的段（`seg` 字段最小）外，其余段前缀非
空；最早的段前缀必须为空"，两个方向都断言到（不是简单删掉断言）。改完后我又做了一次
Edit/还原的显式变异（把"最早段应为空"那条断言替换成 `if False: ...`，等价于恢复旧版对
全部段一视同仁的错误假设）验证它会真红回同一条 `AssertionError`，然后原样还原。

修完后 `tests/test_ayano_test.py`（21 项，含这条真实数据闸）与全量测试全绿——即用仓库
**真实**车道数据、真实卡组、真实题库确认了这次重排没有让任何既有段的反剧透前缀塌缩，也
没有让新段意外泄露不该有的卡。

**chapters**：`[s0f, crd, s1s, sys, s1f, s2s]`（实算集合，含 crd，遵循既有条目"卡片批次
与剧本批次交错、抽读范围须包含它们"的口径）。**jp_chars**：`116282`（实算）。

**review_focus**：序章现实层框架 + 教程 crd_0/crd_2；第1章故事层三条分支点
（`s1s_35_sel`/`s1s_150`/`s1s_260_sel→RUN s5`）+ 正常完结与 2 处 GAMEOVER；第1章现实层
框架剧情；教程/常规卡片谜题；`sys` 系统提示串（非正文）；末两批已进入第2章开头，标注与
`seg1-s2` 的衔接边界。

### 测试

- `tests/test_segments.py::test_segments_partition_b1_to_339`（重命名自
  `test_segments_partition_b36_to_339`，断言范围由 `range(36,340)` 改为 `range(1,340)`）——
  这条测试**确实在检验新条目**：它遍历全部 `segs` 累加 `batches` 区间，新条目的 `[1,35]`
  天然参与累加，不是"恰好绕过"。
- `tests/test_segments.py::test_segments_jp_chars_match_batches`/
  `test_segments_chapters_match_actual_chapters`/`test_each_segment_covers_exactly_one_lane`/
  `test_segments_lane_field_matches_batches`/`test_segments_labels_unique_and_ordered`——
  均对 `for s in segs` 泛型遍历，新条目自动纳入，无需改动即生效。
- 新增 `test_seg1_s0_s1_covers_b1_to_35_prologue_and_chapter1`：显式钉死新条目的
  label/seg/batches/lane/jp_chars/chapters，防止"删掉这一段、同时把 partition 测试下界也
  错改回 36"这种双重误改被其余通用测试放过（docstring 里写明这条测试只钉"身份没被张冠
  李戴"这一半，分区完整性仍由 partition 测试兜底）。
- `tests/test_ayano_test.py::test_real_card_chapter_data_gate` 的"每段非空"改为
  "除最早段外每段非空 + 最早段必须为空"（见上）。

### 变异（Edit 应用 → 验证真红 → Edit 还原）

1. `batches: [1,35] → [1,34]`（制造覆盖缺口）：`test_segments_partition_b1_to_339`（b35 未
   覆盖）、`test_segments_jp_chars_match_batches`（116282≠113389）、
   `test_seg1_s0_s1_covers_b1_to_35_prologue_and_chapter1`（batches 不等）**三条真红**。已还原。
2. `chapters` 去掉 `sys`：`test_segments_chapters_match_actual_chapters`（缺 sys）、
   `test_seg1_s0_s1_covers_b1_to_35_prologue_and_chapter1`（集合不等）**两条真红**。已还原。
3. `tests/test_ayano_test.py` 里把"最早段前缀应为空"的断言短路成 `if False`（等价于恢复旧版
   "全部段非空"的错误假设）：`test_real_card_chapter_data_gate` **真红**（
   `seg1-s0-s1（seg=1）前缀被滤空`，与我改 `segments.yaml` 那一刻自然产生的红一致）。已还原。

三轮变异后 `grep -rn "MUTATION" tools/ tests/ config/` 为空，`git diff --stat` 与还原前一致。

---

## 改动二：`tools/check_qa_quotes.py` 带理由的抑制清单

### 设计裁定

**存放位置**：新文件 `config/qa_quote_suppressions.yaml`，与题库（`config/ayano_qa/*.yaml`）
物理分开——评审要能一眼看全"我们一共豁免了什么"，不该和题库正文混在一起。

**粒度**：`(qa文件名, id, fragment)` 三元组精确匹配，**不支持** "这个 id 以后都别报" 或
"这份题库别报了" 这种粗粒度。这是本次设计的核心安全属性，也是变异测试重点验证的一条——
放宽到 `(qa, id)` 会让同一 id 未来任何新的真实漂移都被旧的豁免记录连坐放过（见下方变异②）。

**reason 必填**：`load_suppressions()` 对任何一条缺 `reason`（缺字段/空串/纯空白）**拒绝
加载整份清单**（不是跳过那一条静默继续）——防止"忘写理由"被悄悄放过。

**播报纪律**：`main()` 统计口径改为"本次命中 N 处，其中 M 处按抑制清单豁免，K 处需要处理"，
被豁免的命中仍逐条打印（标 `[豁免]`），只是不计入 `--strict` 退出码——`return 1 if (kept and
a.strict) else 0`，不是 `hits`。默认 `--suppressions` 路径就是
`config/qa_quote_suppressions.yaml`，不用在命令行加 flag，故 runbook 给的真实命令原样可用。

### 已录入的豁免

`config/qa_quote_suppressions.yaml` 里的唯一一条：`qa: seg1-s2.yaml, id: 10038,
fragment: "，ユウイチ像是"`，`reason` 说明题库 q12 自身叙述天台门那句与 10038 旧译只是 6 字
偶然重合、非引用，`date: 2026-08-07`，`source` 指向本次排查与
`docs/ops/p4-seg1-adjudication-handoff.md`。

### 真实命令复核

```
$ uv run python tools/check_qa_quotes.py --qa config/ayano_qa/*.yaml --data-dir pilot/lanes/opus/data
被回改覆盖过的 id：374 个（data-dir=pilot/lanes/opus/data，min-len=6）
本次命中 1 处，其中 1 处按抑制清单（config/qa_quote_suppressions.yaml）豁免，0 处需要处理
✅ 7 份题库除 1 处已豁免命中外，未发现失同步引用
  ○ [豁免] seg1-s2.yaml 引着 id 10038 的旧译文片段：「，ユウイチ像是」
```

干净结论：4 处真实漂移（此前已回填题库）+ 1 处豁免，0 处待处理，与任务要求完全一致。

### 文档

`docs/ops/p4-polish-runbook.md` §十一"清关后必跑"里题库引文检查段落新增一段说明：抑制
清单位置、粒度承诺（不连坐）、`reason` 必填纪律、播报口径、"新增豁免前先确认确实是伪报"
的提醒。

### 测试（`tests/test_check_qa_quotes.py`，新增 13 条）

- `load_suppressions`：缺文件→空清单；缺 `reason`/纯空白 `reason`→拒绝加载并报错；正常
  加载。
- `split_suppressed`：精确三元组匹配；**同 id 不同 fragment 不被连坐豁免**（核心安全测试，
  docstring 明写"这是会不会在最该响的时候不响的直接测试"）；同 fragment 不同 qa 不被连坐；
  被抑制的命中不被丢弃（完整保留在 `suppressed` 里，供上层统计）。
- CLI 集成：豁免命中 `--strict` 通过；未豁免命中即使清单存在也照常 `--strict` 失败；
  混合场景（一条豁免+一条未豁免）两者都出现在输出里、退出码只由未豁免那条决定；
  `--suppressions` 缺 reason 时 CLI 层同样拒绝；不传 `--suppressions` 时默认路径生效
  （`monkeypatch.chdir` 模拟真实命令不带 flag 的场景）。

### 变异（Edit 应用 → 验证真红 → Edit 还原）

1. 去掉 `load_suppressions()` 的 `reason` 必填校验：`test_load_suppressions_requires_reason`/
   `test_load_suppressions_rejects_blank_reason`/
   `test_cli_missing_reason_in_suppressions_file_aborts` **三条真红**（`DID NOT RAISE
   ValueError`）。已还原。
2. `split_suppressed()` 的匹配键从 `(qa,id,fragment)` 放宽到 `(qa,id)`：
   `test_split_suppressed_does_not_match_different_fragment_same_id` **真红**——这条正是
   "粒度太宽会静默放过新漂移"的直接证据：同一 id 的一段全新的、内容完全不同的旧译文片段
   被旧豁免记录连坐放过。已还原。
3. 退出码判据从 `kept and a.strict` 改回旧版 `hits and a.strict`（即抑制清单形同虚设）：
   `test_cli_suppressed_only_hit_passes_strict`/
   `test_cli_default_suppressions_path_used_when_flag_omitted` **两条真红**（rc 应为 0 却
   得到 1）。已还原。
4. 播报层"藏起来"：`main()` 改成只统计/打印 `kept`，完全不提被豁免的命中：
   `test_cli_suppressed_only_hit_passes_strict`/
   `test_cli_unsuppressed_hit_still_fails_strict_even_with_suppressions_file`/
   `test_cli_mixed_suppressed_and_kept_hits`/
   `test_cli_default_suppressions_path_used_when_flag_omitted` **四条真红**（找不到统计行/
   `[豁免]` 字样）。已还原——这条对应任务里明确点名的"藏起来等于恒绿"红线。

四轮变异全部真红、全部还原，`git diff --stat` 核对无残留。

---

## 改动三：`polish_amplify` 轮数标记语义修正

### 缺陷复核（改动前）

`pilot/polish/seg1-s2/frozen/rulings.md` 里确有一条 `<!-- amplify-round:1 -->`，而
`raw/amplify/` 目录、`candidates.amplify.jsonl` 均不存在——`scan_prompt()` 被调用过一次
（仅用于查看内容），随后 SEG-1 判断桶 3 已因 K 拓宽提前清零、放大扫描收益已兑现，主动放弃
真正执行。旧代码把"装配成功"当"跑完一轮"计费，这条标记记的是一件没发生过的事。

### 设计裁定

**谁来写标记**：`tools/polish_amplify.py` 新增 `mark_round_if_complete(label, repo=None)`，
只有当 `ingested.amplify.json` 记录的批号**完全覆盖**该 SEG 的全部批号（`_load_frozen()`
算出的 `batches`，与 `scan_prompt()` 输出契约里逐批列出的 `raw/amplify/bN.out` 同一份集合）
时才追加标记；`tools/polish_ingest.py::ingest()` 在每次 `channel=="amplify"` 且 `ok=True`
的调用（含"已入仓，跳过"的幂等 no-op 分支）之后调用这个钩子（`_maybe_mark_amplify_round`）。
业务知识（标记格式、`CFG['amplify_rounds']`、SEG 全部批号从哪读）全部留在 `polish_amplify`
一侧，`polish_ingest` 只负责"amplify 通道成功入仓了一次，问一句要不要记账"——避免两个模块
各自维护一份"什么算完成一轮"的判断。

**轮数闸的新判据**：`scan_prompt()` 仍然读 `frozen/rulings.md` 里的标记数与
`CFG["amplify_rounds"]` 比较，**但自己不再写标记**——装配本身（哪怕反复装配、重渲染）不再
消耗配额，只有真正入仓覆盖全 SEG 才消耗。用四条测试钉死这个语义没有被顺手拆掉：
`test_scan_prompt_can_be_recalled_freely_before_round_is_ingested`（连续装配 3 次不留标记）、
`test_ingest_marks_round_only_after_full_seg_coverage`（只入一批不该标记，两批都入才标记）、
`test_ingest_marking_is_idempotent_across_repeat_calls`（覆盖齐全后重复调用不重复标记）、
`test_round_gate_blocks_scan_prompt_only_after_real_ingest`（真正入仓完覆盖后第三次装配才
被拦）——外加对应的两条 CLI 级测试。

**既有 seg1-s2 那条误记的标记**：判定**清理**，不保留。理由：
1. 它记录的是没发生过的事，且在**新语义下**语义已经变了（旧标记文案"已装配"，新标记文案
   "已真正入仓完成"）——留着一条措辞、含义都对不上新代码的旧标记，本身就会误导后来人。
2. 它不是纯粹的文档问题：这条误记的标记**此刻就会挡住合法操作**——只要它还在，任何后续
   对 `seg1-s2` 调用 `scan_prompt()` 都会被 `AmplifyRoundLimitError` 拒绝，而按新语义，
   SEG-1 的放大扫描轮次从未被真正消耗，理应仍可用。不清理等于让一个已经查明是误记的状态
   继续实际阻断未来工作，这比"文档留一句不准确的历史记录"更坏。
3. `frozen/rulings.md` 属于 `pilot/polish/*/frozen/`，被 `.gitignore` 整体忽略（`git
   check-ignore -v` 确认），编辑它不产生任何 git 差异，不影响可复现性。

清理做法：不做静默删除，改写成一段"撤销说明"（保留原标记文本作为引用、写明为什么撤销、
何时/为什么这条配额其实仍然可用），并把真正的标记正则从这段说明文字里避开（验证：
`_round_count()` 对改写后的文件返回 `0`）。

**`frozen/rulings.md` 的 verify() 哈希是否受影响**：动手前用
`uv run python tools/polish_setup.py --verify seg1-s2` 核实——**改动前**就已经报
`frozen/rulings.md: 哈希不符`（rc=1），因为 `digest()`/`scan_prompt()` 早就在 SEG-1 生产
过程中往这个文件追加过内容，而 `manifest.json` 里的哈希是 `setup()` 建立冻结面那一刻的
空壳快照——这是这套"哈希在 setup 时点冻结、内容却设计成持续追加"机制本身的既有属性，与
本次改动无关，属于超出本轮三项任务范围的既有观察，**未修**（详见下方"未处理事项"）。改完
之后重新 `--verify` 仍然是同样的"漂移 1 处（同一文件）"，没有变得更差。

### 测试（`tests/test_polish_amplify.py`，净增 4 条：移除旧 2 条+旧 1 条 CLI 测试，新增
7 条）

- 移除并替换语义反转的旧测试：`test_scan_prompt_round_gate_blocks_second_call`（旧假设"装配
  两次就该拦第二次"，与新语义矛盾）、`test_scan_prompt_writes_marker_only_after_success`
  （旧假设"scan_prompt 自己写标记"）、`test_cli_scan_prompt_second_call_rejected`（同上，
  CLI 层）。
- 新增：`test_scan_prompt_can_be_recalled_freely_before_round_is_ingested`、
  `test_ingest_marks_round_only_after_full_seg_coverage`、
  `test_ingest_marking_is_idempotent_across_repeat_calls`、
  `test_mark_round_hook_is_noop_for_non_amplify_channel`、
  `test_round_gate_blocks_scan_prompt_only_after_real_ingest`、
  `test_cli_scan_prompt_repeated_calls_succeed_before_ingest`、
  `test_cli_scan_prompt_rejected_after_round_really_ingested`。

### 变异（Edit 应用 → 验证真红 → Edit 还原）

1. **重新引入旧缺陷**：在 `scan_prompt()` 末尾重新加回"装配成功即写标记"的代码——
   `test_scan_prompt_can_be_recalled_freely_before_round_is_ingested`/
   `test_ingest_marks_round_only_after_full_seg_coverage`/
   `test_round_gate_blocks_scan_prompt_only_after_real_ingest`/
   `test_cli_scan_prompt_repeated_calls_succeed_before_ingest` **四条真红**。已还原。
2. `mark_round_if_complete()` 去掉"批号覆盖齐全"检查（只要有过一批入仓就标记）：
   `test_ingest_marks_round_only_after_full_seg_coverage` **真红**（只入 batch1 就出现了
   标记）。已还原。
3. 去掉幂等短路（`round_count >= limit` 分支）：
   `test_ingest_marking_is_idempotent_across_repeat_calls` **真红**（4 次 ingest 调用后
   累积出 3 条标记而不是 1 条）。已还原。
4. **绿变异，已分类**：`_maybe_mark_amplify_round()` 去掉 `if channel == "amplify":` 判定，
   任何通道入仓成功都去问一句——**50 项测试全绿，包括专门为此设计的
   `test_mark_round_hook_is_noop_for_non_amplify_channel`**。判定为**"变异没打中"**，不是
   "测试无牙"：`mark_round_if_complete()` 内部硬编码只读 `ingested.amplify.json`（不接受
   `channel` 参数），与调用方传的是哪个 `channel` 无关——即使调用点的判定被拆掉，函数内部
   仍然只会在 amplify 自己的入仓状态真正覆盖全 SEG 时才动作，一次 `chA` 批次入仓不会让
   `ingested.amplify.json` 的内容发生变化。这个 `if channel == "amplify":` 判定因此是防御
   性冗余（避免非 amplify 通道白跑一次读文件+比较），不是承载安全语义的分支——真正的安全
   边界在 `mark_round_if_complete()` 内部对 `ingested.amplify.json` 的硬编码读取，已被
   变异 2/3 验证过。已还原（虽然该改动本身不产生可观测差异，仍按纪律撤回，不留探针代码）。

四轮变异（含一次已分类的绿变异）后 `grep -rn "MUTATION" tools/` 为空。

---

## 全量验证

```
$ uv run pytest -q
798 passed in 4.14s
```

（改动前基线 780 passed；净增 18：改动一 +1、改动二 +13、改动三 净 +4。）

```
$ git status --short pilot/lanes/opus/data/
（空，未改动车道数据）
```

```
$ grep -rn "MUTATION" tools/ tests/ config/
（空，无变异残留）
```

## 未完全解决 / 决定不修的事项

1. **`pilot/polish/seg1-s2/frozen/rulings.md` 的 `polish_setup.verify()` 哈希不符**——
   这是"`manifest.json` 在 `setup()` 时点为 `rulings.md` 记一份空壳哈希、而该文件的设计
   本身就是靠 `digest()`/`scan_prompt()` 持续追加内容"这套机制的固有属性，**在本轮三项
   任务开始之前就已存在**（改动前用 `--verify seg1-s2` 核实过，rc=1，同一文件同一原因）。
   本轮清理 SEG-1 的误记标记时会再次触碰这个文件，但没有让 verify 的结论变得更差（改前
   改后都是"漂移 1 处：`frozen/rulings.md` 哈希不符"）。这属于 P4 工具链更早期任务遗留的
   一个既有设计缺口（`rulings.md` 一旦被 `digest()` 写过，`verify()` 就会对它恒报漂移，
   使这条闸对该文件失去信号价值），**不在本轮三项任务的授权范围内**，未修，留给后续
   session 视情况处理（可能的方向：`verify()` 对 `rulings.md` 改成"前缀匹配"而非全文件
   哈希，或干脆把它移出 manifest 的强校验文件集、只做存在性检查）。
2. 其余三项改动本身均已按要求完成、测试与变异全部通过，无遗留。

## 涉及文件

- `config/segments.yaml`（新增 seg1-s0-s1，原 9 段 `seg` 字段 +1，label 不变）
- `config/qa_quote_suppressions.yaml`（新建）
- `tools/check_qa_quotes.py`（`load_suppressions`/`split_suppressed`/`main` 改动）
- `tools/polish_amplify.py`（`mark_round_if_complete` 新增，`scan_prompt` 不再写标记）
- `tools/polish_ingest.py`（`_maybe_mark_amplify_round` 钩子接入 `ingest()`）
- `tests/test_segments.py`、`tests/test_ayano_test.py`、`tests/test_check_qa_quotes.py`、
  `tests/test_polish_amplify.py`
- `docs/ops/p4-polish-runbook.md`（§十一 补抑制清单说明）
- `pilot/polish/seg1-s2/frozen/rulings.md`（本地清理，gitignored，不入库）
