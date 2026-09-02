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
