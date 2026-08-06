# SDD ledger — plan: docs/superpowers/plans/2026-08-07-p4-polish-pass.md

分支：main（CLAUDE.md 规定工具代码/文档日常改动直接提交 main；三类强制开分支的情形均不适用）。
起点：fbdaeda（计划提交）。
用户已休息，遇需裁决事项记录后绕开，继续推进不阻塞任务。

## 预检（dispatch Task 1 前）
- 计划内已知小瑕疵（不阻塞，dispatch 时告知实施者）：Task 1 Step 5 的 commit 列表写了
  `pilot/lanes/lanes-manifest.json`，实际文件名是 `pilot/lanes/pilot-manifest.json`；
  计划本身已注明「实际待 add 文件以 git status 为准」。
- 未发现任务间矛盾，未发现计划强制而评审规则视为缺陷的条目。

## 进度
Task 1: complete (commits fbdaeda..45d192d, review clean)
  - 评审独立复核了承重点：lane.json freeze_exclude 实测 `["glossary/polish.md"]`，且
    `setup()` 的 `freeze_exclude is None → lane_exclusions()` 路径确认会读到新值（非表面通过）。
  - 567 passed；`.claude/settings.json` / `data/api_ledger.jsonl` 未被卷入提交。
  - Minor（不入循环）：fable 车道 `stale_vs_repo` 新增告警＝设计内播报（不进退出码），
    待 fable 车道下次 `--force` 重冻结自解。
Task 2: complete (commits 45d192d..6133908, review clean) — 571 passed
  - 计划瑕疵已裁定修正：`test_jp_tail_strips_ctl_and_ruby` 期望值原写 `"よろしく漢字ね"[-8:]`（7 字，恒不等），
    改为 `"はよろしく漢字ね"`（strip 后 12 字取末 8）。
  - **变异②立功**：`edit_distance` 的 replace 记 min 首跑为绿；实施者诊断为「测试无牙」——brief 唯一
    replace 用例 `"abc"→"axc"` 等长，min/max 恒等——追加 `edit_distance("ab","x")==2` 后转红。
    评审独立重跑复核该链条成立。这正是「绿变异必须区分两种解释」的兑现。
  - Minor（不入循环）：`RUBY_RE` 对畸形 ruby（多逗号/无逗号）静默不处理＝安全空操作；
    全库 38 处 ruby 均单逗号规范格式，语料中不会触发。
Task 3: 实施完成 5257cf7（583 passed）；计划瑕疵已裁定修正——notes 是**按章**存的
  （`s2s.md`/`crd.md`…），brief 的 `_copy_notes(..., lo, hi)` 按批号取行不通，改为按段表
  `chapters` 拷贝、缺章告警不静默。评审报 1 Important 进修复轮：
Task 3: fix round 1/5 — `verify()` 单向盲区：frozen 里凭空多出的文件永不报警
  （评审实测：塞入 manifest 未登记的 `frozen/glossary/voices/sneaky_extra.md`，verify 返回 []）。
  同时是测试矩阵盲区（12 用例 + 3 变异都没覆盖）。已派回原实施者加 rglob 反向扫描+新测试+新变异。
Task 3: fix round 1/5 (1 addressed, 0 open; commits 5257cf7..5cafc68) — 585 passed
  复审独立复现：两处子目录（glossary/voices、notes）塞未登记文件均报漂移；关掉反向扫描后
  两条新测试真红。三类漂移后缀可区分：`: 缺失` / `: 哈希不符` / `: 未登记（凭空多出）`。
Task 3: complete (commits 6133908..5cafc68, review clean)
Task 3: minor (deferred): `verify()` 反向扫描会把 `.DS_Store` 报成漂移（macOS 上人用 Finder
  翻 frozen/ 必然生成）。**这是「恒绿闸」的镜像形态——伪报淹没真信号，本项目同样吃过亏**
  （ruby 104→5、数字 212→1）。已挂给 Task 11：SEG-1 实跑前给 verify 加忽略名单
  （`.DS_Store`/`__pycache__` 等），那正是人第一次用 Finder 翻 frozen/ 的时点。
Task 4: 实施完成 4e27df7（599 passed）；计划瑕疵已裁定修正——①brief 的
  `assert "b<批号>.out" not in p or True` 是恒真断言（评审规则视为无断言测试），换成真断言；
  ②`plan` 签名以测试 kwargs 为准。评审报 2 Important 进修复轮：
Task 4: fix round 1/5 — ①`frozen/rulings.md` 从未被 render() 读取，spec §6 明写四件套
  jp/opus/notes/**rulings**。SEG-1 rulings 是空壳故看不出，但 SEG-2 起 amplify 的意图纪要
  前馈写进 rulings.md，**会被永久静默丢弃且无任何信号**——闸不存在所以永不响。
  ②正文行 `【jp】/【opus zh】` 与游戏原生 `【名字】` 说话人前缀嵌套（评审用真实 id=27 实测：
  `【【アヤノ】「…」】`），而同份任务说明第 4 条又命令模型「`【】` 原样保留」——几乎每行都成立。
Task 4: minor (deferred): ①复用 `build_context._render_anchors` 带进硬编码「## 三、锚点行」
  标题，与 render 自身的「## 三」撞号，文档里「三」出现两次后跳到「四」；
  ②`OUTPUT_CONTRACT_HEADER` 硬编码「最后 8 个字符」未插值 `CFG["jp_tail_n"]`（改配置会与
  Task 5 校验不一致，但表现为整批判死＝响的，不是恒绿）；③「单批自身超双帽」分支无回归测试
  （真实 SEG-1 最大批 b58=326 行 < 600，当前不触发）。
Task 4: fix round 1/5 (2 addressed, 0 open; commits 4e27df7..d45eee6) — 602 passed
  复审独立实测：rulings 标记串确实进 prompt、占位骨架不产生空节；正文行改 ASCII 标签
  `JP: … / ZH(opus): …`，真实 id=27 渲染无任何嵌套，与全库标记集（`_n`/`_r`/ruby/`≪≫`/
  `≦≧`/`○`/`■`/`【】`/`『』`/`「」`）字符层零交集。两个变异各自真红。
Task 4: complete (commits 5cafc68..d45eee6, review clean)
Task 4: minor (deferred): 章节编号瑕疵——复用的 `_render_anchors` 内嵌「三、锚点行」与
  render 自身「三」撞号；notes/rulings 为空时编号跳号。纯装订层面，不影响模型理解。
  与 `.DS_Store` 忽略名单一并挂 Task 11 收尾。
Task 5: 实施完成 0ce109b（617 passed）。评审做对抗性构造，报 1 **Critical** 进修复轮：
Task 5: fix round 1/5 — **回执只绑 `id ↔ jp_tail`，不绑 `zh ↔ jp`**。评审实测：三行
  `{id:11, jp_tail:正确, zh:opus[10]}` 轮转错位——id 与尾串内部自洽故全过核验，`zh` 却挂着
  别的原文的译文，`ok=True, added=3, dead=[]` 静默全量入仓，`jp_hash`/`opus_hash` 按 id
  正确算出**反而掩盖错位**。在本项目格外可信：契约要求「不改的行 zh 逐字抄 opus」，
  让模型逐行照抄一整列，抄串行正是最典型的长上下文失误，而 id/jp_tail 仍正确。
  裁定判据（窄，防伪报淹没真信号）：**zh 逐字等于本批另一 id 的 opus 且两行 jp 不同** → 判死。
  「jp 不同」这条限定是承重的——本库大量复现句族的 zh 本就该逐字相同（W4 管辖，是正确行为），
  少了它会整片误杀。要求补「去掉该限定则复现句族测试转红」的变异证明它有牙。
  另附：空 `zh` 判死。残留边界（改写后再挂错行）由 Task 6 R2b + Task 7 分流兜底，须写进 docstring。
Task 5: fix round 1/5 (1 addressed, 2 open; commits 0ce109b..a63631d) — 621 passed
  错位 Critical 已 ADDRESSED（复审独立复现 + 两变异真红，含「去掉 jp 不同限定则复现句族转红」）。
  但复审用**真实语料**做了伪报估算，开出两条新的：
  A（Important，修复 diff 新引入）：`_norm()` 对非字符串 `zh`（`"zh":12345`）抛 AttributeError
    穿透出 ingest，**CLI `--all` 整个中断**而非「该批失败继续扫」。修复前不会崩。
  B（判据收窄）：真实数据——同批内「zh 逐字同、jp 不同」有 **21 对 / 38 id / 17 批（约 5%）**，
    抽样全是正当收敛（`ん`/`うん`→嗯，`え？`/`ええ？`→诶？，`どうしたの？`/`どうかした？`→怎么了？）。
    **且不是概率事件**：碰撞来自 opus 基线本身，只要通道对这些短行「不改」（契约里最正确的动作）
    就确定性双双误杀。裁定收窄：**zh 若逐字等于自身 id 的 opus 则一律不判错位**——
    轮转攻击下该条件恒不成立故不削防线，却一次消掉整类伪报。
Task 5: fix round 2/5 (2 addressed, 0 open; commits a63631d..038856f) — 625 passed
  复审独立复现：非字符串 zh 四型均「该行判死、批照常」，CLI `--all` 不再中断；短句碰撞不误杀；
  轮转攻击仍全灭（收窄未削防线）。
  **本轮最有价值的一笔**：加收窄后原变异 A（去掉「jp 不同」限定）变绿，实施者诊断为「测试无牙」
  ——旧夹具的复现句族恰好 `zh == 自身 opus`，被新捷径提前拦下，那条分支根本走不到——补了 id 15
  夹具后转红。复审**独立重建了该场景验证诊断属实**，并另建 W4 收敛场景证明该限定仍承重：
  同 jp 族内 A 的 opus 陈旧、B 正确，模型把 A 改成与 B 一致 → `zh_A == opus[B]` 且 jp 相同，
  去掉该限定就会把**最正当的 W4 收敛改写**误杀。
Task 5: complete (commits d45eee6..038856f, review clean)
Task 5: minor (deferred): `misaligned_with` 用 `next()` 取首个匹配，多重匹配时报文里点名的
  「另一 id」依赖迭代顺序——只影响错误信息文字，不影响死活判定。
Task 6: 实施完成 357c68a（635 passed）。评审报 1 Important 进修复轮：
Task 6: fix round 1/5 — **speakers.json 从未进冻结面**。评审确认这不是实施偏差，
  **是 spec §3 的冻结清单本身漏了它**，而 §8 又把「R2b 说话人」列为机械闸的一部分。
  实施者的回落（读仓库根 glossary/speakers.json）没关上口子：R2b 映射是**影响判定结果**的
  输入，SEG 冻结后若有人改仓库的 speakers.json，该 SEG 的闸结论**静默漂移**，而
  `polish_setup.verify()` 完全看不见（只哈希 frozen 内文件）。今天能跑对只因仓库根恰好有那份。
  评审实测：无 speakers 表时 `【彩野】`→`【别人】` 的换名被**静默放过**（结构检查双方都有括号故通过）。
  >> **控制者裁定（用户休息中，记此供醒后复核）**：补齐冻结面而非回落。这不是推翻用户决定——
  >> spec §3 明写「润色输入只认冻结面」（Task 4 有专门变异测试钉这条），遗漏属起草疏忽，
  >> 补上是兑现既定原则。同时要求改 spec §3 与计划 Task 3 的 frozen 清单，堵住这条 finding 的根。
Task 6: fix round 1/5 (1 addressed, 0 open; commits 357c68a..46fe40b) — 637 passed
  复审独立实测：frozen/glossary/speakers.json 存在且入 manifest，篡改后 verify 报「哈希不符」；
  造「frozen 无该文件、仓库根有一份内容不同的」对抗场景，gate 只能是「无 speakers 表」那一种，
  确证无回落；变异（改回回落）真红。spec §3 与计划 Task 3 均已回填并注明理由。
  **专项核查「修复是否顺带削弱既有测试」**：受牵连的 4 个测试文件改动严格限于补夹具
  （`speakers.json` 源文件），无一条断言被改松/删除/改成恒真；一处测试改名+断言反转是
  行为变更后的合理更新，且另补了更严格的对抗性回归锁。
Task 6: complete (commits 038856f..46fe40b, review clean)
Task 6: minor (deferred): `gates.<channel>.json` 落盘 str key / 内存 int key（与
  `check_charlevel.py` 既有约定一致）。不入循环，已在 Task 7 指令里点明须处理。
Task 7: 实施完成（commit 5422266）；650 passed（637 基线 + 13 新增）。
  三个自行裁定的设计点（K 配额多通道同 id 共享一个名额、抽检占用 K 的顺序拆解、
  edit==0 与 zh==opus 用两套不同归一化）与四个变异（brief 给的 3 个 + 指令额外
  要求的"channel_state 缺失默认开启"1 个）全部真红，详见 task-7-report.md。
  **本任务自行发现并补上一个 brief 给定测试的薄弱点**：`test_deterministic_
  sampling`（brief Step 1 原文）在变异③（抽样用系统随机）下只有约 18% 概率
  转红（5 次重跑全部误判为绿），补了一条结构性钉死（monkeypatch 全局
  `random.random` 令其一炸就抛）把同一件事变成 100% 确定的检验。
  与 brief 一处已核实的字面偏差：随机种子 key 实测是 `manifest["files"]
  ["frozen/source.jsonl"]`（带 `frozen/` 前缀），不是 brief 写的
  `"source.jsonl"`——按字面实现会在真实 SEG 上直接 KeyError，已用临时仓库
  实测确认后改正。
  `gates.<channel>.json` 的 str/int key 转换（Task 6 遗留 minor）已处置：
  helper `load_gates()` 放在本模块（brief 补充信息允许二选一），未回去
  改动已过评审、clean 状态的 `tools/polish_check.py`。
  待复核：无。
