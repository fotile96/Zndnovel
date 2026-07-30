# SDD ledger — plan: docs/superpowers/plans/2026-07-30-p1b-linearize-context.md
# 工作台：main 直提交（仓库规约，用户已批准；无并行会话写树）
# BASE(T1 前)=fe3e028
Task 1: review — spec ✅ / quality Needs fixes（Important×1: pend_choice 陈旧→choice:0 假事件，s2s_190_sel；plan 代码承袭 bug，修复=恢复 plan 语义，不需人裁）
Task 1: minor (deferred): SUBCALL_RE 惰性守卫需注释或移除；parse_crds/main 无 pytest 回归；states 合并 dict.update 无碰撞告警；dag.json 无末行换行
Task 1: fix round 1/5 — pend_choice 两遍扫描修复（SEL_ASSIGN_RE 收集选择变量、消费后清零）+ SUBCALL_RE 注释 + 末行换行；再评审：全部 ADDRESSED、无新增 C/I（对全语料 72 处 comDlgSelectItem 站点独立核验 0 分歧）；修复 commit 消息由韩语 amend 为中文（a7d415e→4fdff8f）
Task 1: minor (deferred): in_while 单计数器不区分 if/for/function 的 end，存在潜在嵌套误判（当前全语料惰性，新增脚本时需警惕）；test_choice_cleared_after_consumption 未真正隔离清零（去掉清零行仍过）；test_real_data_s2s_190_sel_targets 用 dict 键控、未强制"各仅一次"；choice_vars=set() 死初始化
Task 1: complete (commits fe3e028..4fdff8f, review clean)
# BASE(T2 前)=4fdff8f；T2 实现者已派发（haiku）
Task 2: implementer DONE_WITH_CONCERNS (81f42ef)——实现完好，但 Step5 冒烟暴露 P1a build_ledger 平面函数追踪缺陷：场景体 vms 被归给内层闭包名 v0（snr_s1_10_s 1234/1433 行；全库章节文件受累），(file,func) 联结断裂
Hotfix A 开启：build_ledger 嵌套栈追踪（brief=hotfix-a-brief.md；BASE=81f42ef；控制器已核实：AMBIENT_FUNC_EXCEPTIONS 空、2 个 narrative 例外函数无内闭包、顶层无带 vms 的裸 vN → 预期 kind 零变化、仅 func 迁移）；T2 评审推迟到 Hotfix A 落地后（评审范围仍取 4fdff8f..81f42ef）
Hotfix A: implementer DONE_WITH_CONCERNS (2dda37e)——12018 行 func 迁移；控制器独立核验：前后均 16749 行、源码 finditer 16749 唯一 id 与 ledger 一致、裸 vN 残留恰 24 行（snr_crd_102 顶层兄弟闭包 v0/v1/v2，Task 5 可用 unit_funcs.yaml 附挂解决）、kind {ambient:56, narrative:16693}、冒烟 s1s_10→9/s1s_20→75 通过
# 发现并修正文档计数错误：vms 实为 16749 非 16750（CLAUDE.md/analysis README，commit 6f04620）
# T2 评审（4fdff8f..81f42ef）与 Hotfix A 评审（81f42ef..2dda37e）已并行派发（sonnet×2；后者用裁剪评审包=代码全量+数据抽样+控制器核验数字）
Hotfix A: review — spec ✅ / quality Approved（评审者独立复核：全语料弹栈平衡零异常、无匿名函数/end)/tab；重放旧平面算法确认被改断言原编码缺陷；红线抽查+分布核对全吻合）
Hotfix A: minor (deferred): crd_102 例外钉法可收紧为精确 (file,func,id) 三元组集合（现为 (file,func) 允许列表 + 总数==24）
Hotfix A: complete (commits 81f42ef..2dda37e, review clean)
Task 2: review — spec ✅ / quality Approved，但 Important[plan-mandated]×1：ran 死变量 + skip 被 goto 消费后 run 不受门控，与计划 docstring「含伴随 run」相悖（对真实数据惰性：32 个带 run 状态的 nxt 均由伴随 goto 正确解出）。控制器裁决：计划内部 deadcode/契约表述缺陷（后续任务零消费 ran；跨文件由伴随 goto 承载是引擎 doScriptScene 语义的忠实映射），修复=删死变量+docstring 对齐+补 card_gate→goto→run→goto 版式用例，不需人裁 → 进 fix round 1
Task 2: minor (deferred): choices.setdefault 就地污染调用方 dict（T5 复用 choices 跨多次 story 会累积默认值）；默认选项取"首个遇到"依赖 seq 升序而非显式 min（现全 32 状态升序成立）；REPO/DATA/write_jsonl 等 F401 未用导入；事件分发无 catch-all（end_cost 静默忽略，未知键不报错）；emitted_states 只写不读；报告自称覆盖 funcs=[] 边界实未断言；card_gate/route_has/run/subcall/unit_funcs 零测试覆盖（brief 批准的裁剪，T5 补硬化）
Task 2: fix round 1/5 — 删 ran、run 分支显式 no-op+注释、docstring 契约对齐、补 card_gate→goto→run→goto 双分支用例（0a03599）；再评审：全部 ADDRESSED、无新增 C/I
Task 2: complete (任务提交 81f42ef+0a03599，间夹 Hotfix A/2dda37e 与 docs/6f04620；review clean)
# BASE(T3 前)=0a03599；T3 实现者已派发（haiku）
# T3 派发时控制器裁决修正 brief 代码一处：dedup_emit 删除 route.append（story 本身会 append，原代码双写折叠状态）；已核实真实 crds 结构与 fixture 同形（196 条、四字段、str 键）
Task 3: implementer DONE (2dbdd2a)，7/7 绿，裁决修正已落实；评审已派发（sonnet，0a03599..2dbdd2a）
# 用户指令（2026-07-30）：T3 评审返回后暂停——记录裁决即止，不派 T4、不启修复轮，等用户发话
Task 3: review — spec ✅（全项，含裁决修正精确落实、real crds 抽查吻合、无越界改动）/ quality Approved；Important[plan-mandated]×1：三条新测试为 brief Step 1 原文，四个关键语义零测试覆盖——_makeable 阻断分支、fragment_sweep(only=…) 过滤、fscene 紧随位置（现断言仅 membership）、replay route 单写回归；评审者已用临时脚本实证四者行为均正确（无在体缺陷），是否补测试待用户裁决
Task 3: minor (deferred): pool() 的 split(":") 无格式守卫（裸 ValueError）；script/pool/card 对零匹配 stem/func 静默 emit 空 ids unit（typo 难察觉）；replay marker 测试只查形状存在不查 text 内容
# T3 未记 complete——Important 为 plan-mandated（brief 自身测试内容所致），按流程属人裁；已暂停等用户
# 用户裁决（2026-07-30）：补一轮测试（fix round 1，仅四项测试缺口，不动产码不动 Minor），完成本修复轮（含范围内再评审）后继续暂停——仍不派 T4
Task 3: fix round 1/5 — 补四回归用例（f5f0f8c，纯测试 +106 行）；再评审：1/2/4 ADDRESSED（断言真防护、突变复现自洽、产码零变更），**3 NOT ADDRESSED**——fscene 位置用例的 runs 卡在扫描序末位，批尾实现同样通过（评审者批尾突变实测 11/11 绿）→ 进 round 2（fixture 把 runs 卡移出末位）
Task 3: fix round 2/5 — runs 移到首卡 21、23 置空，精确全序断言+字段核验（c34a606，纯测试 +19/-11）；再评审：ADDRESSED（评审者隔离副本批尾突变复现恰一红十绿）、用例 1/2/4 零改动未削弱、产码零变更、突变证据自洽
Task 3: minor (deferred，评审注记): DAG2 的旧 fscene 用例仍是 membership 断言（判别职责已由新用例承担，不阻塞）；round 2 报告的突变仅散文描述未附字面 patch
Task 3: complete (commits 2dbdd2a+f5f0f8c+c34a606, review clean)
# 已按用户指令暂停：T4 简报已备好（task-4-brief.md）未派发，等用户发话
