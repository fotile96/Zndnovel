# SDD ledger — plan: docs/superpowers/plans/2026-08-02-p3-ignition.md

执行分支：`main`（用户 2026-08-02 明示批准；CLAUDE.md 轻量分支制允许工具代码/文档类日常改动直提 main，且 Task 6 的 `prod-run-v1` tag 需落在 main 历史上才对生产 worktree 有意义）。
起点：`226e87f`（docs: P3 点火实施计划）。

预扫描备注：Task 5/6/7 是运维性任务（车道再冻结、tag+worktree+runbook、生成计划），
天然无单元测试；其验收靠步骤内的断言/抽验命令，评审时不应按「缺测试」判缺陷。

Task 1: complete (commits 226e87f..49d85a3, review clean) — config/segments.yaml 8 段 + tests/test_segments.py 3 测试；评审独立重算 8/8 段 jp_chars 与 b36-339 完美划分；211 passed
Task 2: complete (commits 49d85a3..5480681, review clean) — tools/saturation.py + 3 测试；214 passed；冒烟 十円玉 12/12 饱和 1.000 可裁决、消しゴム 57/15 0.263 滚存、浜千鳥 3/0 0.000 滚存
Task 2: 发现（重要事实，后续任务须知）：data/ledger_extra.jsonl 的行用 "key"（如 "snr_crd_100:35"）而非 "id" 字段，829 行皆然；brief 示例代码假设 "id" 会 KeyError，实现者按实际字段修正，评审判定必要且正确
Task 2: minor (deferred): id/key 兼容分支无单测覆盖，只在人工冒烟跑到——误改回 r["id"] 时 pytest 仍全绿
Task 2: minor (deferred): 报告文字称「ratio None 优先排序」与实际（None 排最后）不符，纯文档笔误，代码即 brief 原样
Task 3: complete (commits 5480681..e4e8378, review clean) — tools/canary.py + 3 测试；217 passed；冒烟 35 批 hard=0 warn=30(W2 15/W3 15) collapse=45(C1 21/C2 2/C3 22)，自比对「一致」exit 0
Task 3: 发现（待终审修正波处理）：canary 重算 collapse=45 与 P2 逐批台账求和一致（4+3+1+17+6+6+4+4=45），而 docs/superpowers/reports/2026-08-01-p2-pilot-report.md §6 写的「44 条命中」是汇总誊录错误。canary 正确，报告该订正为 45（warn 30 亦吻合）
Task 3: minor (deferred): canary.py 头注称 pipelib.dumps 是「排序确定性输出」，实际 dumps 未传 sort_keys，确定性来自固定插入顺序（brief 原文表述不精确，功能无碍）
Task 3: minor (deferred): --diff 的 exit 0/1 只有函数级测试，无 CLI 子进程级覆盖（评审已手工验证两种情况均正确）
Task 4: complete (commits e4e8378..58cc5df, review clean) — gen_plan --segment + 2 测试；219 passed；评审用临时 worktree 取改动前版本对 5 组用例逐字节比对 render() 默认路径输出：IDENTICAL
Task 4: 自主判断（评审认可）：两个 return 点（空 sel 提前返回 / 正常返回）都追加段末块，保证段模式头尾成对；测试 helper 用文件既有 _sel() 替代 brief 虚构的 _small_sel()，字段等价
Task 4: minor (deferred): 空 sel + segment 组合路径无测试覆盖（评审已手工验证可正常渲染）
Task 5: complete (commits 58cc5df..a4fb603, review clean) — 车道再冻结至 v7；漂移预检恰为召回令三项（active/anchors/glossary_max），batches/cards_zh 未动；opus+fable 双 verify 无漂移；219 passed
Task 5: 评审独立核实：两车道冻结拷贝均 v7（寝癖=睡翘、anchors 122 条含 8478/15775），manifest 五项哈希与仓库侧逐一相符，progress.md 为纯尾部追加（前 670 行字节级一致）
Task 6: complete (commits a4fb603..fc0e284, review clean) — docs/ops/p3-production-runbook.md；tag prod-run-v1 指向 fc0e284（含手册本身，顺序纪律成立）；worktree /Users/fotile96/Zndnovel-prod 钉死该 tag，内建独立 venv，219 passed
Task 6: 评审独立核实：手册第二/四/五节引用的 lane_setup/canary/saturation/gen_plan 参数与各工具真实 argparse 签名逐一相符，无照抄即错的命令；worktree 与主仓 tools/ 当前一致
Task 7: 评审 Critical——gen_plan 的两个硬停任务（_hardstop_after_batch1/2）硬编码字面量 --batch 2 / batch_1.collapse.json / batch_2.collapse.json，前提是「计划恒从 batch 1 开始」（代码注释自述），P3 段从 b36 起即失效；通用缺陷，SEG-2 起每段都会复现。裁定修法：段模式不生成这两个硬停（①隔离验收需双车道同跑，P3 单车道无对象；②阈值标定已完成并记在 manifest collapse_thresholds），非段模式行为一字不变
Task 7: minor (deferred)：config/segments.yaml 的 chapters 字段遗漏 crd（SEG-1 的 27 批里 8 批是 crd）；计划正文自 batches.jsonl 动态推导、不受影响，属 Task 1 遗留的描述性字段粗粒度问题
Task 7: 评审可复现性核实：临时 worktree 内用同命令重生成，与入库版本 sha256 一致（b51c0966d938…），确认产物未被手工编辑
Task 7: fix round 1/5 (1 addressed, 0 open — F1 硬停硬编码：段模式加 segment is None 卫兵；commits e8ef830..9725864) — 复评独立取修正前 render() 对两组非段模式输入比对：逐字节相同；新增 2 测试含回归闸 test_pilot_mode_lane_cfg_without_segment_still_has_hardstop_tasks；221 passed
Task 7: complete (commits fc0e284..9725864, review clean) — translate-seg1-s2.md 重生成：33 任务（27 批+5 CHECKPOINT+1 终任务）无硬停、编号连续、五项核验全过、与同命令重生成逐字节一致

## 终审（opus，全分支 226e87f..9725864 共 9 commit）
判断：不能直接点火，需一轮修正。C1(Critical)：worktree 机制在 runbook 与 translate-seg1-s2.md 之间自相矛盾——计划里 Run 行全是主仓相对路径（照跑＝机制失效），而按 runbook 字面 cd 到生产树则 lane_setup --verify 与 git add 均硬失败（lane_setup 用 __file__ 推 REPO，无 --repo 开关；生产树是 detached HEAD 且冻结拷贝 gitignore 不存在）。
Important：I1 生产 tag 仍含已修的 gen_plan 缺陷且 canary 覆盖不到（只覆盖 check/collapse）；I2 saturation 漏传 --data-dir 时静默「全部滚存」＝闸门失效方向最难发现；I3 segments.yaml 与 --segment 无程序耦合，批号靠手传可静默错配；I4 SEG-8 跨 lane（b339 是 ambient），select() 单 lane 过滤会静默漏批；I5 prompts/ 不在钉死面内，段中改 prompt 即改变生产条件且 canary 测不到；I6 P2 报告 44→45 确认（逐批台账求和＝canary 重算＝45）。
Minor：M1 canary 不读 manifest 阈值；M2 --regen-ctx 覆写生产车道 ctx 证据；M3 diff 摘要计数相同时像「无差异」；M4 extra 轨 chapter 落 ?；M5 chapters 全段漏 crd（不止 SEG-1）；M6 段模式仍输出试点措辞（与段末裁决冲突）；M7 runbook 的 resolve 命令缺 ZND_DATA。

### 终审修正波（1 轮，commits 9725864..0aaee66 共 6 个）
复评结论：C1/I1/I2/I3/I5/I6/M5/M6/M7/I4 **全部 ADDRESSED**，无越界改动，234 passed。
复评独立实证：①计划 Task 1 Step 1 逐字照跑 EXIT 0 且 `python -v` 证实加载的是生产树 pipelib（钉死语义成立）；②自建 22 例矩阵比对新旧 render() 非段模式输出 sha256 相同（b664eb20…）；③段表耦合、拆段 lane 唯一性经变异测试确认可捕获；④prod-run-v2=0aaee66=HEAD，生产树已切、runbook 一致；⑤计划重生成 sha256 一致（785e8df6…），未被手工编辑。
**parked（残留 minor，不阻断点火）**：段模式漏传 `--tools-root` 会产出「自称已钉死、实则裸相对路径」的计划——裁定：不阻断，理由是 SEG-1 已入库计划前缀正确、失效形态是肉眼可见的占位符而非静默、runbook §3 已写全命令；下轮让 `--segment` 时 `--tools-root` 必填/默认。
**parked（范围外）**：`--lane` 与 `--segment` 无交叉校验（segments.yaml 无 lane 字段），换 lane 的 SEG-8/9 会静默产出空计划；I5 的 prompts/ 钉死是策略性（runbook 规则）而非机制性。
Final review: clean（十条全 ADDRESSED，一条不阻断 minor 已 parked）
