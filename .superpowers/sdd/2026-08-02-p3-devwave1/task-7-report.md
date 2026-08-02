# Task 7 报告：彩野测试 harness `tools/ayano_test.py`

## 概述

按 brief（`.superpowers/sdd/2026-08-02-p3-devwave1/task-7-brief.md`）逐字实现。全过程
未发任何真实网络请求；三条注入 transport 的测试与一次 `--dry-run` 真实数据冒烟均已
跑通。生产会话（SEG-1 b36–62 跑批中）的 `pilot/lanes/` `prompts/`
`.superpowers/sdd/2026-08-02-p3-seg1-s2/` 未被触碰，commit 只 add 了三个指定路径。

## 步骤与实际输出

### Step 1：写失败测试

按 brief 逐字写入 `tests/test_ayano_test.py`（未做任何改动）。

### Step 2：跑测试确认失败

```
$ uv run pytest tests/test_ayano_test.py -v
ERROR collecting tests/test_ayano_test.py
ModuleNotFoundError: No module named 'tools.ayano_test'
```
符合预期（模块不存在）。

### Step 3：写实现

按 brief 逐字写入 `tools/ayano_test.py`（未做任何改动）。

### Step 4：跑测试确认通过

```
$ uv run pytest tests/test_ayano_test.py -v
tests/test_ayano_test.py::test_assemble_context_cards_plus_zh_no_jp PASSED
tests/test_ayano_test.py::test_main_writes_report_with_verdicts PASSED
tests/test_ayano_test.py::test_dry_run_zero_api_calls PASSED
3 passed in 0.02s
```

三条测试验证的内容：
- `test_assemble_context_cards_plus_zh_no_jp`：`assemble_context` 组装出的上下文同时
  含卡组梗概正文（"卡一梗概正文"）与段内已译 zh（"游泳池的约定"），且不含任何日文
  原文；fixture 里 batch 36 有 ids [100,101]，只有 100 有译文，`missing==1`。
- `test_main_writes_report_with_verdicts`：注入 fake transport，第一次调用返回读者
  作答、第二次返回判分（`对|回答与标准一致`）；验证 `main()` 恰好调用 2 次 API（一次
  作答 + 一次判分），报告 markdown 里含题号、答案、判分标记与缺译提示行。
- `test_dry_run_zero_api_calls`：`--dry-run` 传入一个必炸的 transport（断言不该被调），
  跑通且 stdout 含 "题数 1"，验证 dry-run 路径零 API 调用。

### Step 5：runbook §5 追加一步

原文件 §5 段末流程是一句用箭头连接的话（"机检复核 → 用户按 review_focus 抽读 →
`git tag prod-opus-<label>-done` → 开裁决会话"），brief 给的插入块是 3 空格悬挂缩进
格式（与本文件其余编号清单的续行缩进风格一致，如「裁决会话清单」item 2）。为了在
"打 tag 之前"插入这一步且保持格式一致，把这句箭头链改写成编号清单，在原 tag 步骤
前插入新的第 3 项，其余语义不变（原来的 4 个动作现拆成 5 个编号项，第 4 项就是原来
的 `git tag`，第 5 项是原来的"开裁决会话"）：

```
段末流程按生产计划内嵌清单执行：

1. 机检复核。
2. 用户按 `config/segments.yaml` review_focus 抽读。
3. （tag 前，可选但强烈建议）跑彩野测试作额外验收：
   `uv run python tools/ayano_test.py --segment <label> --qa config/ayano_qa/<label>.yaml --lane-dir pilot/lanes/opus`
   （零订阅额度，走 deepseek API；题库由开发轨按段提供；报告落 work/out/ayano-<label>.md，
   判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。）
4. `git tag prod-opus-<label>-done`。
5. 开裁决会话。
```

`裁决会话清单：` 及其下 1–6 项原样保留，未改动。

### Step 6：真实数据 dry-run 冒烟

brief 原命令 `--qa /dev/null` 会让 `yaml.safe_load` 读到 `None`，`main()` 里
`len(qa)` 会对 `None` 抛 `TypeError`（brief 也预判到这点，明确要求不改实现迁就它）。
改为造一个单题临时 yaml：

```
$ cat > /private/tmp/.../scratchpad/smoke-qa.yaml <<'EOF'
- id: smoke-q1
  question: "占位冒烟题：本段讲了什么？"
  reference: "占位"
  info_point: "smoke"
EOF

$ uv run python tools/ayano_test.py --segment seg1-s2 \
    --qa /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/smoke-qa.yaml \
    --lane-dir pilot/lanes/opus --dry-run

segment=seg1-s2 上下文 20670 字符 缺译 1531 行 题数 1
```

零 API 调用（未传 transport/api_key，dry-run 分支在读到 qa 后立即 return，不触达
`chat()`）。

**与 brief「Expected：约 6–15 万级」的偏差及根因核实**：实测 20670 字符，低于预期
区间。已定位两个叠加原因，均不是实现 bug：
1. `skeleton/cards.zh.yaml` 文件本身 58019 字节，但其中相当篇幅是 YAML 结构（键名、
   引号）与未被 `assemble_context` 使用的 `tr_note` 字段；组装进前缀的只有
   `title_zh`+`body_zh`，实测该前缀仅 9185 字符——brief 把"卡组 ~5.8 万"直接等同于
   文件字节数，但 5.8 万是整份 yaml 文件大小，不是 prompt 里实际拼入的文本量。
2. `seg1-s2`（b36–62，共 27 批、批内 id 1996 条）目前只入线到约 b42
   （与用户告知的生产进度一致）：实测 `pilot/lanes/opus/data` 里该段区间已译 465
   行、缺译 1531 行——缺译占比约 77%，段远未译完，故已译正文贡献的字符量也远低于
   全段译完后的量级。
   两者相加即 20670（9185 前缀 + ~11000 已译正文 + 少量标题分隔符），量级正确、
   数字合理，是当前生产进度下的真实读数，不是 bug。brief 的"6–15 万"隐含"段已译完"
   的假设，段完成后重跑该命令预期会落在该区间。

### Step 7：全量测试 + commit

```
$ uv run pytest -q
264 passed in 1.55s
```

（brief 写的基线是 257 passed；实际仓库当前基线是 261 passed，本任务净增 3 条，
264 与调用方给出的预期基线一致。）

```
$ git status --porcelain   # commit 前核对暂存范围
 M .superpowers/sdd/2026-08-02-p3-seg1-s2/progress.md   # 生产会话自己的台账，未 add
M  docs/ops/p3-production-runbook.md
A  tests/test_ayano_test.py
A  tools/ayano_test.py

$ git add tools/ayano_test.py tests/test_ayano_test.py docs/ops/p3-production-runbook.md
$ git commit -m "feat: 彩野测试 harness（卡组梗概前缀+段译文/读者-判分双调用/dry-run）"
[main 6753bef] feat: 彩野测试 harness（卡组梗概前缀+段译文/读者-判分双调用/dry-run）
 3 files changed, 174 insertions(+), 2 deletions(-)
```

## 偏差与处理小结

| 项 | brief 原文 | 实际处理 |
|---|---|---|
| Step 6 `--qa /dev/null` | 会让 `None` 崩实现 | 未改实现；改用临时单题 yaml，命令已记录在上文 |
| Step 6 字符数量级 | "约 6–15 万" | 实测 20670，根因见上（yaml 文件字节数≠拼入前缀字符数；段仅译 23%） |
| Step 7 全量基线 | brief 写 257 passed | 实测 261→264（仓库已比 brief 撰写时多跑了一些用例），与用户给出的最新基线一致 |
| Step 5 插入形式 | 给的是一段 3 空格缩进 markdown | 判断需嵌入编号清单第 3 项，据此把原箭头句改写为 1–5 编号清单（语义不变，仅格式化） |

## 自查结论

- 三条注入 transport 测试全部通过，dry-run 路径零 API 调用（有断言型 fake transport
  兜底验证）。
- 全程未发任何真实网络请求：Step 6 冒烟未传 `--transport`/api_key，且命中的是
  `--dry-run` 分支（在 `chat()` 调用之前就 return）；Step 2/4 的 pytest 全部走注入
  transport。
- 未修改 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/` 任何
  文件；commit 只 add 了 brief 指定的三个路径，未使用 `git add -A`/`git add .`。
- 未新增任何依赖（仅用已有 pyyaml + stdlib）。

---

## 修正轮：Critical 反剧透闸修复（评审后）

### 问题复述

评审判定初版 100% 忠实落地 brief，但 brief 本身设计有 Critical 缺陷：
`assemble_context()` 把 `skeleton/cards.zh.yaml` 全部 196 张卡无条件拼进「此前剧情
的卡片梗概」，对 seg1-s2（第 2 章）而言，这泄漏了：
- 本段自己的答案卡（卡 41 ナゾトキ答案、卡 44/45/46 周末伏笔、卡 58 s2s_390 判定、
  卡 134 章节 2 梗概全文）；
- 更晚段才该揭示的真相卡（卡 141「原来是直哉」＝s7f 全盘揭示、卡 142 s8f）。

后果：受试模型不看译文也能满分，「答错≈译文丢信息」这条核心命题不成立。

### 卡→章映射的实际推导（未采用 crd_summary.txt，理由见下）

先读了 `analysis/crd_summary.txt`（`tools/extract_crd.py` 产物），确认它**没有**
「触发章节」这一字段——只有 `req`（前置卡）/`answersCmp`（正确答案卡号，`>=2` 的
才是真答案）/`gets`（副产物授予）/`runs`（章节终卡启动的 `_f` 脚本）/`MSG`。于是
改用三条独立可核实的数据源，逐一在 `lua_scripts/` 里核实（过程记在
`config/card_chapter.yaml` 头注释里，供复算）：

1. **场景/选择卡（157 张）**：`lua_scripts/snr_common.lua` 的
   `sceneId2aCard.<sceneId> = <card>` 真实赋值（195 条里过滤掉 38 条字面键就叫
   `keyword` 的重复覆盖噪声——CLAUDE.md 已记载这是反编译噪声）。对每个真实
   sceneId，用 `scene_<sceneId>\s*=\s*function` 精确定义模式去 23 个章节脚本里
   定位——8 个 sceneId（如 `e2s_10`、`s3s_340`）在多个脚本里以字符串形式被提及
   （多是跨章 RUN 跳转目标），但用严格"定义处"模式后全部唯一消歧，157/157 全部
   解出、无遗留歧义。
2. **章节梗概卡 133–145**：crd_133..145 全是 9 行 STUB（`analysis/crd_summary.txt`
   证实，不揭示信息）；真正的授予点是各 `_f` 章节脚本收尾的
   `gameSave.myCard[N].hold = 1`，逐个 grep 定位（133→s1f … 141→s7f、142→s8f …
   145→s3fc），与 CLAUDE.md「完成各章 `_f` 框架剧本时授予」完全吻合。
3. **关键词卡（25 张）**：多数用同样手法在对应 `_s` 脚本里直接 grep 到
   `myCard[N].hold=1`；97/115/126 三张查无直接闭包，改为定位授予它们的
   `crd_N` 脚本本身对应的主卡章节（`crd_56`→卡56、`crd_51`→卡51、`crd_10`→
   卡10，副产物`gets`必与主卡同一次现实层做卡事件，同章节）。

三类相加 157+13+25=195，恰好覆盖全部真实卡号、无重叠、无缺口；另加编外卡 200
（`cards.zh.yaml` 里 tr_note 明写"与卡144对应"，同记 e2f）。196/196 全覆盖，
**没有用到"默认排除"兜底**——虽然 brief 授权了这条安全网，但实测下来数据本身
是完备的，不需要动用。

### 段序换算：不写死，运行时从 segments.yaml 动态推导

章节短码→段号没有写进 `card_chapter.yaml`（避免和 `config/segments.yaml` 产生
第二份可能漂移的真相源），改为 `tools/ayano_test.py` 新增的 `_chapter_max_seg()`
在运行时扫 `segments.yaml` 全部段的 `chapters` 字段动态算：**同一章节可能跨多段**
（`s3s` 横跨 seg2 与 seg4、`s4s` 横跨 seg3 与 seg6——分支剧情来回跳章的实况，
CLAUDE.md「跨章跳转」一节有载；`crd` 因遍布全书被显式排除在归章依据外，但因
195 张卡全部已归到具体故事章节，从未出现 `chapter="crd"` 的情况，未触发这条
排除规则），保守取该章节出现过的**最晚**段号；`s0f`/`s1s`/`s1f` 不出现在任何
main-lane 段的 `chapters` 里（P3 范围外、开工前已译完），记为段 0，恒早于全部段。
判定：卡的章节最晚段号 < 当前段号，才算"严格早于"。

这条规则会让 `s3s`/`s4s` 里实际发生在更早段的部分也被排除在稍晚一点的段之外
（前缀略薄，如 seg3 测试时本该能看到的 seg2 那部分 s3s 内容也会被排掉），但绝不会
把还没轮到的内容错纳成"此前"——按任务方指示，这个方向的偏差是明确可接受的
safety margin，未做批次级（`batches.jsonl` 行序）精细拆分（那需要额外的场景→
批号反查，超出本次 Critical 修复的必要范围）。

### 验证

- `assemble_context("seg1-s2", ...)` 过滤前 196 张卡、过滤后 46 张（全部是
  `s0f`(1)+`s1s`(44)+`s1f`(1)，即 P3 范围外、开工前已译完的部分）；具体核对卡
  41/44/45/46/58（均归 s2s，同段）、134（s2f，同段）、141（s7f）、142（s8f）
  全部被正确排除在 seg1-s2 的前缀之外。
- 新增两条测试：
  - `test_assemble_context_excludes_current_and_later_cards`：同段答案卡与更晚段
    真相卡都断言"不在 ctx 里"，早期卡断言"在 ctx 里"。
  - `test_assemble_context_prefix_not_emptied_by_filter`：断言过滤后前缀段落仍有
    实际卡片内容，防止过滤过头导致前缀清空。
  - `uv run pytest tests/test_ayano_test.py -v` → 5 passed（原 3 条不变）。
  - `uv run pytest -q` → 266 passed（上一轮 264 + 本轮新增 2）。
- 真实数据重跑 dry-run 冒烟（同一临时单题 yaml，命令与上文一致）：

  ```
  segment=seg1-s2 上下文 15959 字符 缺译 1428 行 题数 1
  ```

  上下文字符数从修复前的 20670 降到 15959（卡组前缀从 196 张过滤到 46 张，
  预期内的下降）；缺译行数从 1531 变为 1428——这是本次修复期间生产会话继续
  推进（present 465→568）导致的，与本次代码改动无关，非 bug。

### Minor：runbook §4.1 补 ayano_test

在「不在 canary 覆盖面内、必须人工判定」的工具清单里加了 `ayano_test`
（判定依据：advisory 工具，恒 exit 0，不写车道数据，只读不改，实际风险为零）。

### 纪律核对

- `git add` 只加了 `tools/ayano_test.py`、`tests/test_ayano_test.py`、新增的
  `config/card_chapter.yaml`、`docs/ops/p3-production-runbook.md` 四个路径，未用
  `git add -A`/`git add .`；提交 `37c2762`（`fix: 彩野测试反剧透闸——卡组前缀只取
  严格早于当前段的卡`）。
- 未碰 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`；
  `lua_scripts/`、`analysis/`、`skeleton/` 全程只读（grep/cat 核实映射，未写入）。
- 零真实 API 请求：修正轮全部验证靠 pytest 注入 transport 与 `--dry-run`，未传
  `--transport`/api_key，未触达 `chat()`。
- 未新增依赖。

---

## 修正轮二：复评变异测试的必修项（F1 数据闸缺失 + M1 fallback 方向）

复评确认第一轮 Critical 修复（反剧透闸）已 ADDRESSED，并做了完整穷举验证
（9 个段跑 `assemble_context` 零违例；`card_chapter.yaml` 157 张场景卡与
`scene2card.json` 逐条比对全中；13 张章节梗概卡逐个 grep 命中）。但复评做的
四组变异测试里，后两组全绿放过，暴露了下一层问题。

### 必修：数据闸（对应变异 C/D）

**问题**：`test_assemble_context_excludes_current_and_later_cards` 与
`test_assemble_context_prefix_not_emptied_by_filter` 两条新测试都用合成
fixture（自造 `segments.yaml` + `card_chapter.yaml`），从不读仓库里那份真实的
196 条手工推导数据。于是：
- 变异 C（把仓库真实 `config/card_chapter.yaml` 里 `41: s2s` 改成
  `41: s1s`，即把 seg1-s2 自己的谜题答案卡错记成"更早段"、从而放回它自己的
  前缀）——全绿，未被发现。
- 变异 D（把 `card_chapter.yaml` 整个清空为 `{}`）——全绿，未被发现。

**修法**：新增 `test_real_card_chapter_data_gate`（`tests/test_ayano_test.py`），
不用 fixture，直接读仓库现行的 `config/card_chapter.yaml` + `config/segments.yaml`
+ `skeleton/cards.zh.yaml` + `pilot/lanes/opus` 车道数据（只读）。断言三件事：
1. **全覆盖**：`card_chapter.yaml` 的卡号集合与 `cards.zh.yaml` 的卡号集合完全
   相等（196 条，无缺无多）——直接命中变异 D（清空后 `set()` 对不上 196 个卡号，
   AssertionError 明确指出缺了哪些）。
2. **反剧透**：断言 `seg1-s2` 的前缀里**不含**卡 41/44/45/46/58/134/141/142 的
   `body_zh`，每张卡在测试里注释写明排除理由（这几个卡号就是 Critical 的原始
   证据，注释相当于活文档）——直接命中变异 C（卡 41 的 body 会出现在 ctx 里）。
3. **每段非空**：对 `segments.yaml` 全部 9 段各跑一遍 `assemble_context`，断言
   过滤后前缀的「【卡」计数 > 0，防止过滤/白名单写过头把某段前缀清空。

**自检记录（要求"写完必须自己验证会红"）**：
- 备份真实 `config/card_chapter.yaml` 到 scratchpad，`sed` 把 `41: s2s` 改成
  `41: s1s`（等价于变异 C），跑
  `uv run pytest tests/test_ayano_test.py::test_real_card_chapter_data_gate -v`
  → **FAILED**（`AssertionError: 卡41 泄进了 seg1-s2 前缀（回归到 Critical）`）；
  从备份恢复，重跑 → **1 passed**。
- 把 `config/card_chapter.yaml` 整个替换为 `{}`（等价于变异 D），跑同一条测试
  → **FAILED**（`AssertionError: assert set() == {1, 2, 3, 4, 5, 6, ...}`，
  全覆盖断言先炸）；从备份恢复，重跑全量 → **267 passed**。
- 恢复后 `git diff config/card_chapter.yaml` 只剩本轮 fallback 修复那处
  header 注释改动，确认自检过程未在文件里留任何中间态残留。

### 顺手修二：`chapter_max_seg.get(ch, 0)` 的 fallback 方向反了

**问题**：任何不在 `segments.yaml` chapters 里出现的章节短码，原实现会用
`.get(ch, 0)` 悄悄当作段 0（"最早"）纳入前缀。今天恰好只有 `s0f`/`s1s`/`s1f`
走这条路径（它们确实最早，结果碰巧对），但语义是"查不到=未知"，不该等同于
"确知最早"——方向反了，一旦 `card_chapter.yaml` 将来收录一个 `segments.yaml`
尚未覆盖的**晚期**章节短码，会被这条 fallback 静默放行。

**修法**：`tools/ayano_test.py` 新增显式常量
`PRE_P3_CHAPTERS = {"s0f", "s1s", "s1f"}`（P3 开工前即已译完、对应
`pilot/lanes/opus/data/batches.jsonl` 的 b1–32，确知早于全部 P3 段），
`is_before_cur_seg()` 改为：章节在 `chapter_max_seg` 里就按最晚段号比较；不在
里面则只有落在 `PRE_P3_CHAPTERS` 白名单才算通过，否则一律"未知→默认排除"。
`config/card_chapter.yaml` 头注释同步更新，说明这三个章节为何在白名单里、以及
将来新增此类特例须同步维护白名单而非依赖 fallback。

**验证**：改完后重跑 `assemble_context("seg1-s2", ...)`，前缀卡数仍是 46
（与修复前一致，确认这条修正只改变了"如何得出结论"的路径，未改变
`seg1-s2` 本身应有的结果）。

### 顺手修三：plan 文档勘误

`docs/superpowers/plans/2026-08-02-p3-devwave1.md` 的 Task 7 一节仍内嵌着初版
（未修版）`ayano_test.py` 与原始 3 条测试。按要求**只加勘误注记、不改写内嵌
代码**：在 Task 7 的 Interfaces 段落之后、Step 1 之前插入一段引用块，说明该节
内嵌代码含 Critical 泄题缺陷、已在 commit `37c2762` 及本轮修复中解决，若要
逐字重跑 task-7 请以仓库现行 `tools/ayano_test.py` /
`tests/test_ayano_test.py` / `config/card_chapter.yaml` 为准，并指向
`task-7-report.md`。

### 验证汇总

- `uv run pytest tests/test_ayano_test.py -v` → 6 passed（5 条不变 + 新增
  `test_real_card_chapter_data_gate`）。
- `uv run pytest -q` → **267 passed**（上一轮 266 + 本轮新增 1）。
- 真实数据重跑 dry-run 冒烟（同一临时单题 yaml）：

  ```
  segment=seg1-s2 上下文 16702 字符 缺译 1396 行 题数 1
  ```

  卡数确认仍是 46（独立脚本核对：`ctx[head:tail].count("【卡") == 46`）；
  字符数量级与缺译行数的小幅变动（16702 vs 上一轮 15959；1396 vs 1428）来自
  并发生产会话持续推进，与本轮代码改动无关。

### 纪律核对

- `git add` 只加了 `config/card_chapter.yaml`、
  `docs/superpowers/plans/2026-08-02-p3-devwave1.md`、
  `tests/test_ayano_test.py`、`tools/ayano_test.py` 四个路径，未用
  `git add -A`/`git add .`；提交 `f65dd45`（`fix: 彩野测试补数据闸与 fallback
  安全方向 + plan 勘误`）。commit 前确认 `.superpowers/sdd/
  2026-08-02-p3-seg1-s2/progress.md` 处于 modified 状态（并发生产会话所写），
  未加入暂存区。
- 未碰 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`；
  `skeleton/`、`analysis/`、`lua_scripts/` 全程只读。
- 零真实 API 请求：新测试与自检全部走注入 fixture 或纯离线的
  `assemble_context()` 调用，未传 `--transport`/api_key，未触达 `chat()`。
- 未新增依赖。
