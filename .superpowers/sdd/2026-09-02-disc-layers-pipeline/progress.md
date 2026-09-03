# SDD ledger — plan: docs/superpowers/plans/2026-09-02-disc-layers-pipeline.md

Spec: docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md（已读）
分支: feat/finale-stage　merge-base: 2e49539　起始 HEAD: 7324804

## 预检扫描（dispatch Task 1 之前）

### 共享文件 / 接口的任务对

| 任务对 | 共享物 | 生产 → 消费 | 结论 |
|---|---|---|---|
| T1→T2 | `tools/layers.py` | `OverlayError`/`apply_overlay` → `load_overlay` 设 `_name` 供其读 | 一致，追加式 |
| T2→T3 | `tools/layers.py` | `load_manifest` → `provenance` 读 `manifest["lane"]["dir"]`、`base[ledger]` | 一致 |
| T1/T2/T3→T4 | `tools/layers.py` | 三者之和 → `build_final_sources` + CLI | 一致 |
| T2→T4 | `layers/manifest.toml`、`vms_ids.toml` | T2「Files: Create」列了这两个文件，但其步骤只用 tmp_path 夹具；真文件在 T4 Step 3 写 | **冲突 1**，见裁决 |
| T3→T8 | `charset_of(sources, ledger_jp, always)` | T8 stage_font 传 `lua/final` 文本列表 | 一致 |
| T4→T7 | strip-ipl / boot-handoff 层 | T4 建静态层；T7 删 testboot 里的 `strip_ipl()`/`BOOT_HANDOFF` | 顺序正确，期间两条路径并存但互不干扰 |
| T4→T8 | `build_final_sources` 三元组 | T8 stage_lua 消费 | 一致 |
| T5→T8 | `inject_tree(base, ledger_rows, zh, extra)` | T8 stage_lua 消费 | 一致 |
| T6→T8 | `build_font.build(charset, out_dir, sizes, ruby_size)` | T8 stage_font 消费 | 一致 |
| T7→T8 | `testboot.generate(mode, out_dir, **opts)` | T8 stage_lua 在 test 剖面调用 | 一致 |
| T4∧T6 | `pyproject.toml` | T4 加 `local_assets` 标记；T6 加 `fonttools` 依赖 | 不同小节，无文本冲突 |
| T1/T2/T3/T6 | `tests/test_layers.py` | 四次追加 | 一致，纯追加 |
| T4→全后续 | `lua_scripts/` 纯净基座 | T4 还原 → 后续只读 | 一致 |

### 各任务自洽性

| 任务 | 自洽核查 | 结论 |
|---|---|---|
| T1 | 测试 import 的 5 个名字全部在实现里定义 | ✓ |
| T2 | 测试 import 6 个名字全部定义；`_mk_layers` 写空 `vms_ids.toml`，`_read_toml` 对空文件返回 `{}` | ✓ |
| T3 | 测试 import 3 个名字全部定义；`provenance` 对不存在的车道路径由 `_sha256` 返回 `"absent"` | ✓ |
| T4 | Step 9 的闸依赖 Step 7 的 `--compare-compiled`；Step 8 的测试依赖 Step 7 的 `build_final_sources`——步骤顺序正确 | ✓ |
| T5 | `inject_tree` 的 stats 少 `font_slot1` 键，测试夹具 `_stats()` 多带一个——多余键无害（`inject_text` 不读它） | ✓ |
| T6 | 测试 monkeypatch `TTF_PGF`/`widen_latin`；`sizes=(17,)` 不触发 widen 分支 | ✓ |
| T7 | 保留的扫描函数与删除的编译逻辑无交叉引用 | ✓ |
| T8 | 测试 import 的两个模块级函数在 Step 3 给了完整实现 | ✓ |
| T9 | 纯验证，无代码接口 | ✓ |
| T10 | 纯文档 | ✓ |

### 外部耦合实测

- `FONT_PATCH` 只在 `tools/migrate_base.py` 内部使用（3 处），无外部 import → T4 删除安全。
- `make_test_boot` 只在自身模板字符串里自指 → T7 改名无外部破坏。
- **`tools/build_disc.py:94` 硬编码 `FINALE_LUA = docs/finale/snr_finale.lua`** → T4 的 `git mv` 会让旧管线的 lua 阶段当场失败。**冲突 2**，见裁决。

### 裁决

Ruling: T2 不创建真实的 `layers/manifest.toml` 与 `layers/vms_ids.toml`，只交付代码与用 tmp_path 夹具的测试；真文件归 T4 Step 3 — 理由：T2 若写出真文件，其 `order` 必须与彼时尚空的 `layers/overlays/` 一致，写完 T4 又整体覆盖，中间态毫无价值且会让 `load_manifest()` 默认路径行为在两个任务间摇摆 — 若判错的代价：T2 的实现者少建两个文件，T4 照常创建，无返工。

Ruling: T4 顺带把 `tools/build_disc.py:94` 的 `FINALE_LUA` 指向 `layers/scripts/snr_finale.lua`（一行改动，不进 T8 的重写范围）— 理由：spec §9 接受 T4 与 T8 之间「构建链半新半旧」，但接受的是「不出盘」，不是「旧管线当场崩」；一行改动即可让旧路径在 T8 接手前保持可跑，代价远低于一个已知损坏的中间态 — 若判错的代价：T8 重写时这一行被整体替换，白改一行。

Ruling: T4 Step 10 的全量 pytest 不包含 T6 才加的 `test_build_font_reads_charset_file_not_lane`，这是预期而非遗漏 — 理由：任务按序执行，后置任务的测试不该在前置任务处出现 — 若判错的代价：无，纯记录。

---

## 执行记录

Task 1: dispatched (haiku, agent ab780aa6bd17795a5), BASE 7324804
Task 1: implementer DONE — commit 8acd288, 15/15 tests passing
Task 1: task review (sonnet) — spec ❌ 1 Important（plan-mandated）, 4 Minor
Task 1: Ruling: `count=0` 静默 no-op 的发现成立，必须加 `count < 1` 守卫 — 理由：设计稿 §6.2 明写 `count`（≥1，缺省 1），且「锚点不存在」与「期望零命中」在数值上不可区分，静默通过正是 count 要抓的漂移；缺陷源自计划里的代码，已同步修正计划 — 若判错的代价：多一行守卫与一个测试，无功能损失。
Task 1: Ruling: 计划 Task 1 Step 4 写「16 passed」而其代码块只有 15 个测试，是我写计划时的笔误；裁定 15 为正确基数，加上守卫测试后恰为 16，计划文本已改为言明这一点 — 若判错的代价：无，纯文本勘误。
Task 1: minor (deferred): apply_overlay 用 `overlay.get("ops", [])` 而非 `overlay["ops"]`，缺键时静默 no-op；Task 2 的 load_overlay 会在加载边界强制非空 ops，故不入循环。
Task 1: minor (deferred): select_indices 未被测试直接调用，其 count/occurrence 逻辑只经 apply_op 的 replace 路径间接覆盖。
Task 1: minor (deferred): apply_overlay 的错误包装（层名 + 操作序号前缀）无专门测试。
Task 1: minor (deferred): task-1-report.md 自评里两处计数笔误（说 5 个公开函数实列 4 个，说 2 个私有助手实列 3 个）——已在 fix 轮一并要求订正。
Task 1: fix round 1/5 (1 addressed, 0 open; commits 8acd288..0660e54)
Task 1: complete (commits 7324804..0660e54, review clean)
Task 2: dispatched (sonnet, agent a4aa4bd1990bd8b60), BASE 0660e54
Task 2: implementer DONE_WITH_CONCERNS — commit e75590f, 28/28 tests（16 旧 + 12 新），全库 1703 passed
Task 2: task review (sonnet) — spec ❌ 2 Important（均 plan-mandated）, 3 Minor
Task 2: Ruling: 发现 1（test 剖面豁免只写在 docstring 里、代码从未实现）成立，判为**实现它**而非删掉承诺 — 理由：设计稿 §6.3 明文规定该行为，是绑定权威；且现状里 manifest["scripts"] 的 test 条目被整段跳过 = 一次静默略过校验，直接违反本任务「一切正确性问题硬失败、绝不静默」的全局约束。给 [[ranges]] 加可选 profile 字段、test 段免于保留集比对、test 脚本改为照查（自身区段 + 跨 owner 唯一）而不是跳过 — 若判错的代价：约 10 行当前无人行经的代码，但让 §6.3 由空头承诺变为可依赖。
Task 2: Ruling: 发现 2 的「冗余检查」部分**不改**——校验器里的双保险不是缺陷，删掉才是脆弱的那一步；但其「测试因错误的原因而通过、需求 4（跨层重号）无真实测试」的部分成立，补一个 seen 真正能抓到的用例（同一 owner 被登记两次）并加注释说明内层检查是 belt-and-braces — 若判错的代价：多一个测试与两行注释。
Task 2: minor (deferred): tools/layers.py:117 与 :194 的 `import tomllib` / `import re as _re` 是文件中部 import，与本文件顶部 import 惯例不一致（plan-mandated）。
Task 2: minor (deferred): tests/test_layers.py 新增了三个未使用的 import（tomllib、Path、REPO），且 REPO 走了第二条 from tools.layers import 语句而非并入既有那条（plan-mandated）——已在 fix 轮附带清理。
Task 2: minor (deferred): _ranges_of 对畸形 pair 抛裸 ValueError/TypeError 而非 OverlayError，与「正确性问题一律 OverlayError」有窄口径出入。
Task 2: fix round 1/5 (2 addressed, 1 new Important——修复自身引入：tools/layers.py:271-275 的注释与其标注的代码矛盾，声称 test 层「真会命中」而 `profile != "test"` 短路使其永不可达；commits e75590f..0fb92d8)
Task 2: minor (deferred): vms_ids.toml 的 [[ranges]] 不校验 profile 取值（load_overlay 会校验），拼错时按 release 全查——方向安全，只是报错不清晰。
Task 2: fix round 2/5 (1 addressed, 0 open；顺带取了可选项 profile 校验 + 测试; commits 0fb92d8..8c45f38)
Task 2: complete (commits 0660e54..8c45f38, review clean) — tests/test_layers.py 33/33，全库 1708 passed
Task 3: dispatched (sonnet, agent a301e8e2db6264bfc), BASE 8c45f38
Task 3: implementer DONE — commit e95da15，40/40（33 旧 + 7 新），全库 1720 passed；自行发现并修掉 brief 缺陷（provenance 用 p.relative_to(REPO) 在 tmp_path root 下崩，改 root.parent）
Task 3: task review (sonnet) — spec ❌ 2 Important（均 plan-mandated）, 6 Minor
Task 3: Ruling: 发现 1（provenance 从不哈希 lua_scripts/ 基座树）成立，必须补 — 理由：设计稿 §6.6 的 inputs 示例明列 `"lua_scripts": "<树 sha256>"`，且这正是 provenance 的核心用途：换基座前后两次构建若指纹相同，取证就是废的 — 若判错的代价：多一个树哈希与一个测试。
Task 3: Ruling: 发现 2（工具哈希无视 SNDL_TTF_PGF / SNDL_LUAC 环境覆盖）成立，必须补 — 理由：设计稿 §12 第 4 条把「/tmp/pgftool/ttf_pgf 重启即失、哈希无记录」列为本次重构要解决的问题；同仓 build_font.py 早已实现该覆盖惯例。开发者一旦按既有惯例挪动工具，provenance 会把用过的工具记成 absent——记录者说谎比不记录更坏 — 若判错的代价：两行 os.environ.get 与一个测试。
Task 3: Ruling: 把「加强 provenance 测试（断言 inputs/tools/git 内容而非只断言顶层键）」并入本轮修复 — 理由：评审指出正是这条浅测试让发现 1 从套件里漏过去；只补代码不补测试，下次照漏 — 若判错的代价：无。
Task 3: minor (deferred): charset_of 收全部字面串字符而非仅 ord>0x7F（设计 §6.4 字面如此写），属无害过收，与宁滥勿缺一致。
Task 3: minor (deferred): _LUA_STR_RE 不识别 `--` 注释，注释里的引号串会被当字面串计入——永远过收不会漏收；实测 snr_finale.lua 无此形态。
Task 3: minor (deferred): write_provenance 无中文 docstring、无测试（同文件其余公开函数都有）。
Task 3: minor (deferred): _git 的 dirty 列表对重命名（R old -> new）会渲染成一整串，纯展示文本无消费者。
Task 3: minor (deferred): tools/layers.py 第三次在文件中部 import（hashlib/json/subprocess/datetime），与 Task 1/2 同一模式，已累计三次。
Ruling: SDD 工作区的 *.md（progress.md / task-N-brief / task-N-report）按 CLAUDE.md「开发规约」以 `git add -f` 入库，且**计划完成后不删除工作区** — 理由：CLAUDE.md 明文规定这些是不可再生的执行状态与证据须入库携带，而 subagent-driven-development 技能的收尾步骤要求 `rm -rf` 工作区；用户指令优先于技能。review-*.diff 仍按规约忽略（可由 git 历史一键再生） — 若判错的代价：仓库多出若干 KB 的执行台账，与既往 15 个 SDD 计划的做法一致。
Task 3: fix round 1/5 (2 addressed + 测试加强 addressed, 1 new Important——修复自身引入：SNDL_LUAC/SNDL_TTF_PGF 设为空串时 os.environ.get 返回 ""，Path("").expanduser() 成 "."，_sha256 越过 exists() 守卫在 read_bytes() 抛 IsADirectoryError，provenance 整个崩掉而非回退；commits 75fc980..979ab4a)
Task 3: 跨任务转达：同一空串脆弱性**先前就存在**于 tools/build_font.py:39 与 tools/inject_lua.py:49 的同款惯例里（本次是忠实照抄了一个潜伏缺陷）。Task 5（inject_lua）与 Task 6（build_font）派工时须一并带上。
Task 3: fix round 2/5 (1 addressed, 0 open；顺带把 _sha256 守卫从 exists() 收紧为 is_file()，全调用点已审计无行为变化; commits 787e563..af552fe)
Task 3: complete (commits 8c45f38..0f69caf, review clean) — tests/test_layers.py 45/45，全库 1725 passed
Task 4: 硬闸基线已由控制器在派工前捕获（build/stage/script 的 230 个字节码 = 迁移前手工改动编出来的样子），两份：/tmp/layers_baseline/script 与工作区内 gate-baseline-script/（后者防 /tmp 被清）。校验锚：snr_mainmenu.lua sha256 9269b5cb…、snr_common.lua 77335b90…、snr_finale.lua 3ee694cd…；snr_mainmenu 字节码内含 title_14_a 常量 2 处（encore 改动在场的证据）。
Ruling: 基线由控制器捕获而非留给实施者的 Step 1 — 理由：Task 4 一旦把 lua_scripts/snr_mainmenu.lua 还原成纯净基座，任何一次 inject/build 都会用不含 encore 的源覆盖 build/stage/script，基线随即永久丢失且无法再生（那是手工改动的编译产物）；先捕获成本近零，丢了则整个硬闸失去参照 — 若判错的代价：多占 6MB 磁盘。
Task 4: dispatched (sonnet, agent a285f171cfcdcd9fb), BASE 0f69caf
Task 4: implementer DONE — commit f9b4b40，硬闸 230/230，55/55 层测试，全库 1730 passed；自行发现并修掉 brief 两处缺陷（op4 锚点实为 2 处命中不是 1 处；闸按 brief 写法永不可能过，因基线是「已注入译文」的构建而 build_final_sources 不注入——补 _injected_sources 复用 inject_lua）
Task 4: 控制器独立复核（不依赖实施者报告）：硬闸 230/230；migrate_base --check 基座纯净 229；luac_norm 归一化后相同 229 / 不同 0；build_ledger --check OK；lua_scripts 仅两文件改动。
Task 4: task review (opus) — spec ✅ 合规、task quality **Approved**，但 4 Important + 8 Minor
Task 4: Ruling: 发现 1（闸可以「不闸而报成功」）成立，必须硬化 — 理由：这是全计划唯一的验收判据，缺 luac 时 print 后 return 0 正是全局约束禁止的静默略过（且系 brief 原文）；单向比对则让「[[scripts]] 写错 profile 导致 snr_finale 掉出 release」表现为 229/229 通过、盘里整章消失 — 若判错的代价：两处 sys.exit 与一个集合断言。
Task 4: Ruling: 发现 2（fonts.toml 的 why 谎称槽 1 已从 inject_lua 合并过来）成立，必须改 — 理由：inject_lua.py:209-211 至今仍在改写槽 1，本次只搬走了 migrate_base 的槽 0 重放；why 是这条边唯一的持久记录，写错会让下一个维护者朝错误方向排查 — 若判错的代价：一句话的措辞。
Task 4: Ruling: 发现 3（op4 的 occurrence 选择在仓库内无锚）成立，补断言 — 理由：/tmp 基线一清、gate-baseline-script 又在 gitignore 目录内，唯一能区分「装进了哪个菜单形态」的证据就消失了；而装错形态是逐字节比对永远抓不到的缺陷 — 若判错的代价：一条断言。
Task 4: Ruling: 发现 4（本 commit 到 Task 8 之间 build_disc 会产出静默降级的盘）——不只记录，要加**响亮的守卫** — 理由：spec §9 只说「期间不出盘」，而实况是跑了也不报错，只是盘里字体退回日文、encore 消失；本仓库同时有其他会话在工作，几个任务的窗口期里踩中的代价是一张看不出问题的坏盘 — 若判错的代价：Task 8 重写 build_disc 时删掉这 5 行守卫。
Task 4: minor (deferred): test 剖面的源从不编译（test_base_fidelity 只覆盖 release），strip-ipl/boot-handoff 只做子串断言。
Task 4: minor (deferred): 基座纯净性只在本机资产齐备时才强制（test_migrate_base_check_passes 会 skip），换机器则无人守住这条本任务确立的不变式；入库一份逐文件哈希清单可做成常开守卫。
Task 4: minor (deferred): 字体成员名在 manifest.toml 与 fonts.toml 各写一份、无交叉校验；改一处漏一处 = 打进 A 字体却加载 B，游戏内静默空白。
Task 4: minor (deferred): _injected_sources 每文件新建 stats 并丢弃；inject_lua 本就只 print 不硬失败，故未丢硬闸，但部分未译会表现为难懂的「与参照不一致」而非缺译计数。
Task 4: minor (deferred): 「luac 编译 + 校 PSP ABI 头」现已在三处重复（tools/layers.py、tests/test_base_fidelity.py、tools/inject_lua.py）。
Task 4: 跨任务转达（Task 5 必读）：inject_lua.py:209-211 的槽 1 改写与 layers/overlays/fonts.toml 的第二条 op 现在是**同一处改动的两个实现**。Task 5 删掉 inject_lua 那段的同时，fonts.toml 才真正独占该行；两者若同时作用于同一份源，第二条 op 会零命中并硬失败。
Task 4: 跨任务转达（Task 8 必读）：本轮给 build_disc.stage_lua 加了「管线迁移中，layers/ 尚未接线」的响亮守卫；Task 8 重写该文件时删除它。
Task 4: fix round 1/5 (4 addressed, 0 open；4 Minor 新增，均不入循环; commits f9b4b40..a054ac5)
Task 4: 控制器独立复核硬化后的闸三态：正常 230/230 exit 0；参照少一文件 exit 1 且指名 snr_finale.lua；参照多一文件 exit 1 且报「漏收了整份文件」。双向都真会失败。
Task 4: 守卫爆炸半径已查明并**判定为正确形状**：guard 只挡含 "lua" 的 stage（含缺省 all），不挡 gim/font/stage/pack/disc/iso/boot。这恰是想要的——被挡住的是「用未接线的源重新生成」，而 build/stage 与 build/inject 里现存的是迁移前的正确产物，仍可直接出盘。
Task 4: minor (deferred): fonts.toml:15 称「发布链路仍是老路径、inject_lua 独立跑一遍」，但同一 commit 的 guard 已让 build_disc 到不了那行——描述的代码路径在 guard 解除前是死的。
Task 4: minor (deferred): tools/layers.py:546 与报告里「见该函数第 441-442 行」的行号引用差一行（实为 442-443）。
Task 4: minor (deferred): tests/test_base_fidelity.py:19 仍硬编码 luac 兜底路径，而同文件 :24 已从 manifest 取 header_hex——自定的去重原则只用在了相邻两个常量中的一个。
Task 4: minor (deferred): tools/build_disc.py:378-379 的恢复指引仍推荐 `--stage lua,gim,font,stage,pack`，该命令现在会撞上迁移守卫（失败仍响亮，不静默）。
Task 4: complete (commits 0f69caf..a054ac5, review clean) — 硬闸 230/230，基座 229/229，56/56 层测试，全库 1731 passed
Task 5: dispatched (sonnet, agent aaec47f7c4c932ca8), BASE a054ac5
Task 5: implementer DONE — commit f450584，11/11 注入测试（本模块史上第一批），全库 1747 passed，闸仍 230/230；自行发现并补掉 brief 缺陷（Step 3 让删 LANE 却没说 load_translations 此后如何找车道目录，照做必 NameError 并打断闸——改从 layers/manifest.toml 的 [lane].dir 取，顺带收口了三处硬编码之一）
Task 5: 控制器独立复核：闸 230/230 exit 0；两个 import 序（inject_lua→layers、layers→inject_lua）均可导入，无循环。
Task 5: task review (sonnet) — spec ✅、task quality **Approved**，0 Critical / 0 Important / 8 Minor。无需 fix 轮。
Task 5: complete (commits a054ac5..f450584, review clean)
Task 5: minor (deferred): inject_lua 模块级 import layers、layers 函数内 import inject_lua——当前两序均可，但两端都没有注释说明这层安排的脆弱性；日后有人把 layers 里那句提到模块级即双双不可导入（失败响亮，非静默）。
Task 5: minor (deferred): load_translations 无负路径测试；manifest 有 [lane] 但缺 dir 键时抛裸 KeyError 而非专门信息，而该函数现在在硬闸调用链上。
Task 5: minor (deferred): tests/test_inject_lua.py 的 _stats() 仍带 font_slot1=0 残留键，与同文件另一条断言「font_slot1 not in stats」隐含的形状不一致。
Task 5: minor (deferred): SRC 与 main() 里的 ledger 路径仍硬编码，而同一份 manifest 已有 [base].dir/[base].ledger——车道路径收口了，这两处没有，半步。
Task 5: minor (deferred): tools/layers.py::_injected_sources 仍复制了 inject_tree 的遍历与聚合循环而非直接调用它。
Task 5: **需处理的 Minor（已排入 Task 6 派工）**：layers/overlays/fonts.toml 的 why 在 Task 4 修复轮里刚被改成描述「槽 1 此刻仍由 inject_lua 执行」，而 Task 5 恰好删掉了那段代码——该 why 现在又是假的。这是本计划第三次出现「散文与代码不符」，必须改。
Task 5: 跨任务转达（Task 7 必读）：tools/make_test_boot.py 有 4 处（287/449/462/502-504）硬编码 build/inject_src，而 inject_lua 缺省已不再产出该目录；无任何测试覆盖，失败响亮不静默。
Task 6: dispatched (sonnet, agent a9fb3d558b6cbf194), BASE f450584
Task 6: implementer DONE — commits 834a438 + 5b6cb75，47/47 层测试，全库 1749 passed；17px 与 9px 两种字体用现役字集重编均与现役逐字节相同；闸 230/230；自行发现并修掉 brief 第 6 处缺陷（build() 从不校验 charset_path，缺文件/空文件时 ttf_pgf 退出码 0 却静默产出 5.3MB 全字库——正是撑爆引擎字体缓冲的那个失败态）；另按令修掉 os.environ.get 两参陷阱与 fonts.toml 的 why。
Task 6: 控制器独立复核：闸 230/230 exit 0；corpus_chars 已删、ALWAYS 尚在且可导入（495 项）；build/font 三个现役文件哈希未变。
Task 6: task review (sonnet) — spec ✅ 但 1 Important + 2 Minor
Task 6: Ruling: 发现（charset 守卫只挡「缺文件 / 恰好 0 字节」，挡不住纯空白与截断）成立，必须扩到内容层 — 理由：评审用真实 ttf_pgf 复现了两个近失：纯空白文件 st_size=2 绕过守卫、ttf_pgf 报 Load list : 0 后照样产 5.3MB 全字库；截断文件更产出一个 8KB 的「看着很正常」的字体，静默缺掉表外全部字形——这正是 09-02 那七个空白字的成因。守卫的错误信息自称挡「空」，实现却只数字节，比它承诺的窄 — 若判错的代价：多解析一次字集文件与一条 stdout 断言。
Task 6: minor (deferred): build() 的 docstring 说「6 个字」而同文件模块 docstring 说 7（实为 6 + s7f 递卡旁白 1）——已在 fix 轮附带订正。
Task 6: minor (deferred): ALWAYS 目前是本模块视角下的死代码——build_font 自己不再引用，tools/layers.py 也尚未 import 它，要到接线任务才有消费者。
Task 6: 待 Task 8 留意（评审提出的作用域边界）：本任务的逐字节比对固定了字集文件的**排序与格式**，故它证明不了「write_charset 产出的另一种等价但格式不同的字集会不会导致 PGF 字节布局不同」。接线时值得实测一次。
Task 6: fix round 1/5 (1 addressed 三部分全中, 0 open; commits 61863ed..8c39932 + 3ae73b0)
Task 6: 实施者两处「不照字面执行但更对」的偏离，评审复核后均判正确：①floor 用 len(set(ALWAYS))=472 而非 len(ALWAYS)=495——ALWAYS 有 23 个重复码位，495 会误拒一份合法的 ALWAYS-only 字集，472 才是评审自己的理由真正要求的数；②「6 改 7」未照字面改，因为两个数说的是不同范围（6 = 本次重构针对的结构性根因，7 = 事故总数含一处无关的陈旧性缺字），改为两数并存且互相交叉引用。
Task 6: 评审顺带查证了 ttf_pgf 的 C 源（libpgf.c:246-256、ttfont_znd.c:184-187）：Load list 那行确实走 stderr；nucs==0 时 memset 全 65536 码位 = 5.3MB 全字库。实施者注释里的事实声明与源码逐条相符，且措辞如实标注为「实测/读源码确认」。
Task 6: complete (commits f450584..3ae73b0, review clean) — 51/51 层测试，全库 1753 passed，两种字体逐字节不变，闸 230/230
Task 6: 待 Task 8 注意（评审提出）：Part 2 的 floor 建立在「ALWAYS 无条件并入 charset_of 的每一份字集」这条前提上，而该前提目前**只在测试里成立**——生产链路尚无处把 build_font.ALWAYS 传给 charset_of，那正是 Task 8 stage_font 要接的线。接线时务必真的传 ALWAYS。
Task 7: dispatched (sonnet, agent a86f01279762746cc), BASE 3ae73b0
Task 7: implementer DONE — commits 0319e66 + f8241f1，5/5 testboot 测试，全库 1758 passed，两闸均过；自行发现并修掉 brief 第 7 处缺陷（_count_select_calls 对着纯净 lua_scripts 数，而 overlay 施加在注入后的源上——改用 _injected_source 在内存里取）；另发现一个**先前就存在**的设计缺陷：23 张卡的多处递卡各需不同答案，单值短路只填第一步、其后每步卡死。
Task 7: 控制器独立复核：release 闸 230/230 exit 0；test 闸通过；make_test_boot.py 已 git mv（similarity 56%）；lua_scripts 未动；inject_src 仅剩一处解释性注释；实跑 card=103 生成的层能过 load_overlay，profile=test，多步警告响亮。
Task 7: task review (sonnet) — spec ✅ 但 4 Important + 2 Minor，quality **Needs fixes**
Task 7: Ruling: 发现 2（generate() 不清理 out_dir，跨模式调用会留下上一轮的层）**是本轮最重要的一条，必须修** — 理由：评审实测复现——先 card=103 再 mainmenu，后者返回 {"overlays": []} 却把 card-short-circuit.toml 留在盘上；而 Task 8 的消费方按 glob 扫目录、不信任返回值，于是一份陈旧的递卡短路会被静默施加到无关的测试构建上。这正是被删掉的 emitted.json 机制当年防的那类串味，且该工具 2026-09-01 已经因此把 mainmenu 模式跑成了 cutin 探针 — 若判错的代价：一次 rmtree 与一条目录复用测试。
Task 7: Ruling: 发现 1（多步卡的告警只走 print 与 why 散文）成立，改为结构化 — 理由：评审找到了我要求它去找的第三条路——brief 强制的 5 个测试都不断言 generate() 返回字典的键集，故加一个 result["warnings"] 不与任何强制测试冲突，却让 Task 8、未来的测试、人类都能可编程地发现「这份产物是降级的」，而不必去解析散文或捕获 stdout — 若判错的代价：返回字典多一个键。
Task 7: Ruling: 发现 3（count 修复本身无回归测试）成立 — 理由：本任务的头号贡献若被日后重构悄悄改回读纯净源，今天的套件全绿——因为两个源在全部 103 张卡上恰好相同；唯一兜底要等到某张卡真的分歧才生效 — 若判错的代价：两条断言。
Task 7: Ruling: 发现 4（profile 钉子测试是枚举而非穷举，plan-mandated）成立，改为遍历模块自己的模式表 — 理由：三个手挑的模式里只有 card 真会产层，另两轮空转；日后新增产层模式若没人记得改这个元组，钉子就漏了 — 若判错的代价：测试多绕一层循环。
Task 7: minor (deferred): data/dag.json 在一次 generate("card") 里被重复解析三次（card_answer、_count_select_calls 链、_dag_answers）；文件小，无正确性影响。
Task 7: minor (deferred): 8 个模式里有 5 个（font/ruby/cutin/choices/map）无 pytest 覆盖，只有报告里的一次性冒烟记录——源自 brief 强制的测试文件内容。
Task 7: fix round 1/5 (4 addressed, 0 open, 1 新 Minor; commits f8241f1..73f609f)
Task 7: 控制器独立复现目录复用：第一次 card=103 后盘上有脚本+层，第二次 mainmenu 后只剩脚本，与该次返回值逐项相同；warnings 键在，card=103 一条告警。两闸均过。
Task 7: minor (deferred，但已排入 Task 8 派工)：generate() 的 rmtree 只按子目录名 scripts/overlays 判归属，不校验 out_dir 是否真属本工具的产物树。仓库里恰有同名同构的 layers/scripts 与 layers/overlays（内含手写的 snr_finale.lua 与四个层文件，均已入库）。今日无调用方会踩，但 Task 8 正是要接第一个真实调用方，两棵树刻意平行同名，传错一次就静默删掉手写层。
Task 7: complete (commits 3ae73b0..73f609f, review clean) — 7/7 testboot 测试，全库 1760 passed，两闸均过
Task 8: dispatched (sonnet, agent ad710fa36436bb0bc), BASE 73f609f
Task 8: implementer DONE_WITH_CONCERNS — commit 03fabf3（7 文件 +1028/-303），全库 1763 passed，三闸全过，成员逐件比对**含两个字体成员在内 0 处内容差异**（顺带用旧快照重打包对 DATA.BIN 字节与 sha256，亦相同）——carry-forward 4「字集格式会不会改变字体字节」由此实测闭合；六项转达全部落实；另自行发现并修掉 3 处缺陷（brief 自带的测试夹具在其自带的 release_assertions 下必然失败；assemble_stage 对缺失 members 目录静默 no-op；自己引入的 provenance 拷贝自相矛盾）。
Task 8: 控制器独立复核：两闸均过；迁移守卫已除；ALWAYS 已接线；testboot 传 layers/ 时守卫生效且五个手写层文件完好；release members 树无 snr_test；provenance 记录双工具哈希、两个已施加层、808 替换 11 新增、inputs 含 lua_scripts。
Task 8: Ruling: ISO 产出与否的指令冲突（brief Step 6 要求跑到 iso，我的派工说别产 ISO）——判定实施者照 brief 做是对的，不计为发现 — 理由：我那句话针对的是 Task 9 的模拟器验证，不是这一步的构建；产物落在已 gitignore 的 build/dist 下，可逆无害 — 若判错的代价：删掉一个本地文件。
Task 8: task review (opus) — spec ✅ 合规，但 **5 Important + 10 Minor**，quality Needs fixes。五条全部指向同一个要害：发布闸并不成立它自称成立的那条性质。
Task 8: Ruling: 五条 Important 全部必修 — 理由：①build/dist/DATA.BIN 在任何断言之前就发布（--stage pack 单跑即零断言出货，全量跑时 iso 处失败也已留下一个未验证的新档与一份变成谎言的 sidecar）；②断言查的是 stage 树、ISO 拼的是 DATA.BIN，两者无任何绑定，漏掉 pack 就会「断言一棵新树、拼一份旧档」；③脚本逐字节核对拿 stage/script 与它自己的拷贝源 members/script 相比，二者按构造必然相等——被删掉的 check_release_clean 当年是**独立重编译**来比的，那份独立性没了，于是 `--stage iso` 单跑会对着任意陈旧的字节码报「逐字节核对均正常」；④gim 缓存键只含 png 与模板，不含编码器本身，日后修好 gimcodec 会被静默旁路且无人比对 gim 成员字节；⑤缓存命中路径不算量化损耗却照样计入编码张数，于是第二次起每次都打印「编码 587 张；有量化损耗 0 张」这种自相矛盾的行——这正是全局约束唯一保留的告警通道被悄悄掐掉 — 若判错的代价：一轮修复，全部是加固不是改语义。
Task 8: minor (deferred): release_assertions 硬编码 "script/snr_test.lua" 而非用同模块 347 行之上的 TESTBOOT_MEMBER 常量（已排入 fix 轮）。
Task 8: minor (deferred): tests/test_build_disc.py 有两条断言只匹配文件名子串，删掉它们针对的分支照样通过（已排入 fix 轮）。
Task 8: minor (deferred): assemble_stage 读写 manifest.jsonl 未显式 encoding，与模块内其余 I/O 不一致（已排入 fix 轮）。
Task 8: minor (deferred): _write_provenance 的兜底路径不带 injected= 也不带 testboot 接线，故 --stage members 之后写出的 test 剖面 provenance 会漏掉生成的层与 snr_test 成员，且 members_stat 兜底成看着像事实的 {"replaced":0,"added":0} 而非「未知」。
Task 8: minor (deferred): stage_members 对整个 [gim].replace 面目录缺失仍只 log 不 die——release 构建会因此得到一张图未汉化的盘，而 release_assertions 看不见 gim 成员。是本函数里最后一条静默降级路径（属沿用既有行为）。
Task 8: minor (deferred): stage_font 在 --profile test 下也会写 build/release/charset.txt 并可能触发一次完整的 release stage_lua；内容确系 release 派生，但模块 docstring 的「两棵完全独立的树」并非字面为真，且日志会在 test 剖面横幅下打印属于另一剖面的注入行。
Task 8: minor (deferred): 新逻辑里 _encode_gim_cached 的键组成与命中路径、_compile_lua 的 ABI 头校验、stage_font 的新鲜度判定、剖面隔离本身，均无测试覆盖；七个测试只覆盖两个模块级纯函数。
Task 8: minor (deferred): tests/test_testboot.py 现在会写进仓库真实的 build/ 树（新守卫的必然后果），若测试被中途杀掉会残留 build/_test_testboot/。
Task 8: 评审对「0 差异比对」的作用域界定（重要，记录备查）：它比的是成员名集合与同名成员字节，故覆盖了 808 个替换件含全部 gim 面；**测不到**的有四类——(a) 构建目录当时不存在的 [gim].replace 条目（新旧都不产出，比对对「这条是否被正确搬迁」完全盲）；(b) 缓存命中路径（比对时缓存是冷的，copyfile 那条分支从未被测）；(c) 任何不是成员字节的东西（故结构上不可能发现发布闸变弱或告警通道变哑）；(d) test 剖面（无迁移前对照物）。
Task 8: fix round 1/5 (5 addressed + 3 cheap 全中, 0 open, 2 新 Minor; commits 03fabf3..5e1adde)
Task 8: 控制器独立复核：两闸仍过；DIST 只剩 stage_iso 一个写点且在断言之后；断言路径确实把 lua/final 现编到 tempdir 再比。
Task 8: 评审对两条 caveat 的界定（记录备查）：①Finding 2 的指纹锁的是「当前 stage 树 == 上次成功 pack 前那一刻的树」，之所以能推出「DATA.BIN 出自这棵树」是因为 ctx.root/DATA.BIN 全模块只有 stage_pack 一个写者；单独把 DATA.BIN 换掉而不动 stage/ 仍能过——超出 Finding 2 所问范围。②Finding 3 的独立性只到 lua/final 为止；若 lua/final 本身相对上游（lua_scripts + ledger + 层）陈旧，members 与现编产物同源同旧、照样相等——本轮无任何东西防更上游的陈旧。
Task 8: complete (commits 73f609f..5e1adde, review clean) — 全库 1766 passed，test_build_disc 10/10（含 2 个真跑而非 skip 的 local_assets），三闸全过
Task 8: **候选：合并前应修（点给最终评审）**：tests/test_build_disc.py:163-204 与 :207-252 两个新 local_assets 回归测试只 monkeypatch 了 BASE，没 patch DIST 与 ORIG_ISO（同轮的 Finding-1 测试是 patch 了的）。本机两个真实资产都在，故这两个测试是真跑不是 skip。当前代码下守卫会先抛 SystemExit，安全；但一旦守卫日后回归，重跑这两个「本该抓住回归」的测试反而会覆盖真实的 build/dist/DATA.BIN，并把一个 9 字节的玩具封包拼进真实 orig.iso 的副本当作 game_zh.iso——测试在最需要它的时刻毁掉发布产物。两行 monkeypatch 即可。
Task 8: minor (deferred): stage_iso 里 DIST/DATA.BIN 的拷贝发生在 ISO 拼接与结构自检**之前**；若拼接或自检失败，dist 下会短暂出现「新 DATA.BIN + 旧 ISO + 旧 sidecar」的不一致（可自愈、可检测，且严格优于修复前的「零断言就发布」）。
Task 9: 用户指出「Task 9 卡住」，实况是**从未派工**（无 agent、无报告、无 drives 目录）；按用户指示改由控制器在本 session 直接执行。
Task 9: Ruling: brief Step 2 让 menu/library/no_card144/finale_full 四个驾驶脚本跑在 **release** 盘上，但它们全都依赖全解锁存档（195 卡 + startMenuState=2 + 卡 144），旧架构靠 make_test_boot 往共用的 build/game 里打补丁才做到；新架构 release 盘干净无探针、开机是初始三项菜单，这四个脚本在 release 盘上根本进不了要验的界面。裁定：四个脚本跑在 `--profile test --mode mainmenu` 产的 test 盘上，release 盘由 release_iso.py 走原版开机链验证 — 理由：这正是剖面分离后的正确分工，brief 是按旧共树写的 — 若判错的代价：无，验的界面完全相同，只是引导对象换到了本就该承载探针的剖面。
Task 9: 驾驶脚本收纳时统一了底座（_common.py：--disc/--out 参数、等运行态、VRAM 截图、ERROR 汇总），六个脚本按键与时序逐字保留；缺省 --disc 为各自该用的盘（test 盘 / 发布 ISO）。
Task 9: menu.py / library.py 在 test 盘跑通，各 ERROR 1 条 = ILLEGAL_THID sceKernelWaitThreadEnd(0)，与 08-31/09-01 记录的原盘同源 HLE 噪声一致。
Task 9: finale_full.py 在 test 盘跑通：光标 5 步定位 encore（frac 0.17→0.35 与校准一致），p010 进 fin-10，p020–p180 谢幕五场画面依次出现（含 p170 千秋递卡、p180 黎明），p190 起已是 Story 模式（放学后的约定）——即谢幕章在 ~180 句处结束并回主菜单，其后 CIRCLE 溢出进 Story，与 2026-09-02 那次全章运行形态相同；ERROR 1 条同源噪声。
Task 9: no_card144.py：patch build/test/lua/final/snr_test.lua 加 myCard[144].hold=-1 后 `--stage members,stage,pack,disc`，00 帧回到原版 11 项版面（无 encore），CIRCLE 后 library 子列四项正常——版面回归成立。按 4 次 down 后光标停在 library 而非 option，属 1.0s 间隔下一次按键未吃到的驾驭时序问题，不影响所验断言。
Task 9: glyph.py 在 `--profile test --mode scene --scene fin-10` 盘上：p05「啥」、p11「颁 … 奖」字形正常，IPL 已剥（14 秒进场景），ERROR 0 条。
Task 9: 剖面隔离实证：三次 test 剖面构建（mainmenu / 手改 no144 / scene fin-10）期间，build/dist/game_zh.iso sha256 前缀 f5c5f1c5ad013d66 始终不变（与 Task 8 记录一致），build/release/DATA.BIN mtime 停在本轮 release 重建的 09:37。
Task 9: `--profile release --stage iso`：发布断言通过（指纹/成员集合/独立重编译逐字节/无测试成员），产出 ISO sha256 与本轮之前逐字节相同（f5c5f1c5ad01…）。release_iso.py：原版 IPL 链走完，35 秒处已是初始三项标题（Prologue/load/option，flag 未预开），三次 CIRCLE 进序章、中文题词烤图正常；ERROR 1 条同源噪声。
Task 9: Ruling: 本任务由控制器直接执行、不派任务评审 — 理由：用户明示「直接在本 session 检查现状然后做完」；产物是六个驾驶脚本 + 一段文档，无产品代码路径变化，交由最终整分支评审覆盖 — 若判错的代价：驾驶脚本若有瑕疵会在最终评审被抓，且它们不进盘。
Task 9: 附带发现（非缺陷）：release_iso.py 的 35 秒等待已越过 IPL，00 帧截到的是标题而非 IPL 屏；不影响所验断言（初始形态菜单），docstring 已如实描述帧含义。
Task 9: complete (commits d5a4508..9863be5, 控制器直接执行，无任务评审——见上条裁决)
Task 10: dispatched (sonnet, agent a85086525134663fb), BASE 9863be5
Task 10: implementer DONE — commit 5ae9460（9 文件 +395/-10）：新 docs/ops/disc-pipeline.md；CLAUDE.md 三处 + 一处相邻的陈旧槽位描述订正；四份旧 ops 文档加取代横幅（zh-disc-pipeline 另加缺口已修注记）；两份 finale 文档路径改指 layers/scripts。Step 5 全绿：1766 passed；layers check release/test 均过；migrate_base --check 纯净；build_ledger --check OK；grep 无过时引用。
Task 10: **候选：合并前应修（点给最终评审）**：实施者写文档时发现 `tools/layers.py::check_ids()` 只扫 manifest.scripts 里的编外脚本，**不扫叠加层 with/text 字段里出现的 vms/msg id**——设计 §6.3 明写两者都扫，Task 2 评审也曾以 ⚠ 标出。对本计划的驱动用例（novel 入口提示 = 一个带新 vms 的叠加层）这是直接漏洞：新层的 id 不会被登记检查。文档已如实写明该局限而非掩盖。
Task 10: task review (sonnet) — spec ✅、quality **Approved**，0 Critical / 0 Important / 2 Minor；评审对新文档与 CLAUDE.md 里每条命令、旗标、阶段名、闸描述逐一对照真实工具与源码，全部相符。
Task 10: minor (deferred): zh-disc-pipeline-2026-08-31.md 新加注记写「39 条漏译已修」并指向 release 文档，而后者标题写「41 条」（两个数是不同时点的口径），未注明差异来源。
Task 10: minor (deferred): tools/migrate_base.py 模块 docstring 仍写「snr_common 字体行要在新基座上重打」，与 CLAUDE.md 新表述（字体行归 fonts.toml 层）矛盾——本任务被禁止碰 tools/*.py，留给最终 fix 波。
Task 10: complete (commits 9863be5..5ae9460, review clean)
Task 9: 说明：本任务由控制器直接执行，未写 task-9-report.md；证据在本台账 Task 9 各行与 docs/ops/finale-stage-impl-2026-09-02.md 的「2026-09-03 复验」节。
全部 10 个任务完成。进入最终整分支评审。
