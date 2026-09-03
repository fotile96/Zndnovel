# Task 10 实施报告：文档收口

## 做了什么

新写 `docs/ops/disc-pipeline.md`（不带日期，唯一现行说明），改写 `CLAUDE.md` 三处，
给四份带日期的 ops 文档加取代声明（`zh-disc-pipeline-2026-08-31.md` 额外标注两条已修
的缺口），改两份 finale 文档的路径引用。所有命令、路径、阶段名、flag 在写入文档前都对
照 `tools/layers.py --help`、`tools/build_disc.py --help`（其模块 docstring）、
`tools/build_font.py --help`、`tools/migrate_base.py --help`、`tools/build_ledger.py --help`
逐一核实，并对 `layers.py check`（release/test 两剖面）、`layers.py diff fonts`、
`layers.py ids` 实际跑过确认输出。

## 各文件改动

### 新建 `docs/ops/disc-pipeline.md`

结构：一条命令 → 三个概念（基座/层/剖面）→ 四类改动的落点与命令（对照 spec §6.8 并逐条
核实）→ 阶段表（照抄 `build_disc.py` 模块 docstring 的阶段语义，与实际 `--stage` 选项
一致）→ 加一个新层的完整走查（示例：文库入口中文说明，取自 `MEMORY.md` 的待做项，
**明确标注尚未实施**）→ 各道闸防什么 → 故障排查（锚点不中/id 撞号/字体过期/成员集合
不符）→ 验证（链接 `tools/emu/drives/README.md`，不重复其内容）。

走查示例的关键设计决定：

- 锚点用 `snr_novel.lua` 里真实存在、全文件唯一出现一次的 `endLoading()`（已用
  `tools.layers.find_all` 实测确认命中 1 次，不是编出来的锚点）。
- **发现并如实记录一个现状缺口**：`tools/layers.py::check_ids()` 目前只扫描
  `manifest.toml` 的 `[[scripts]]`（编外整篇脚本，如 `snr_finale.lua`）用了哪些 id，
  **不扫描叠加层 `ops[].text`/`with` 字段里新引入的 vms/msg id**——`vms_ids.toml` 的
  登记对这条路径而言目前只是文档与人工纪律，不是自动闸（读 `tools/layers.py` 源码
  逐行确认：`check_ids()` 里只有 `for spec in manifest["scripts"]` 一处调用
  `_check_ids_of`，`overlays_for()`/`apply_overlay()` 的返回值从未被扫过 id）。这与 spec
  §6.8 表格「新增本地化文本 → …vms_ids.toml 登记区段」的字面表述看似矛盾，但代码
  事实如此；文档没有回避，而是给出了补救路径（仿照
  `test_finale_ids_are_inside_declared_range` 的写法给新层加一条真语料测试）。这是本
  任务里对"每条命令都要核对代码事实"要求最吃紧的一处。

### `CLAUDE.md`（4 处实质改动，多于brief列出的3处字面项，原因见下）

1. 「仓库文件构成」树里加 `layers/` 条目；`lua_scripts/` 段落后补brief要求的加粗句。
2. **顺带修正**了同一段紧邻的字体描述：原文说"字体槽 1 由 `tools/inject_lua.py` 在注入期
   改写"、"字体 0 已换成…（迁移时自动重放，FONT_PATCH）"——这两句已经不真实。核实
   `lua_scripts/snr_common.lua:4006-4007` 现仍是原版 `tsukuminpro_e_{17,09}.pgf`（基座
   纯净，`migrate_base.py` 里已找不到 `FONT_PATCH` 字样），两个字体槽的中文化现在唯一
   来自 `layers/overlays/fonts.toml`（其 `why` 字段明确写了这次交接）。这两句紧挨着我
   要写的「基座纯净/一切改动是层」新句，若不改会自相矛盾，故一并修正。不在 brief 字面
   三项之列，视为同一处改动的必要延伸，未涉及 brief 未提及的其它段落。
3. 「常用操作」出盘那条：加 `layers.py check --profile release` 前置步骤，命令改为
   `build_disc.py`（缺省 `--profile release --stage all`），指向新 ops 文档。
4. 「开发规约」加「层纪律」一条。
5. 「谢幕章」条目：删掉 `docs/finale/snr_finale.lua`/`build_disc.stage_lua`/
   `NEW_GIM_SOURCES` 三处已改名或已迁移的引用，改指 `layers/scripts/snr_finale.lua`、
   `layers.build_final_sources`、`layers/manifest.toml` 的 `[gim].new`（`NEW_GIM_SOURCES`
   这个 Python 常量已被删除，spec §6.7 列明；核实 `build_disc.py` 源码确认现在的机制是
   manifest 的 `[gim]` 两张表）。

### 四份带日期 ops 文档

各加统一取代声明（标题下一行）。`zh-disc-pipeline-2026-08-31.md` 额外在「当前状态与
已知缺口」节尾追加一段，标注槽 1/39 条漏译已修、缺字问题由新管线字体新鲜度检查覆盖。
四份文档正文的历史实测数据、故障机理原样未动。

### 两份 finale 文档

`handoff-stage-impl.md`：表格里 `docs/finale/snr_finale.lua` → `layers/scripts/snr_finale.lua`
（这份文档不在"四份带日期文档"之列，不受"保留历史原文"约束，直接改路径而非加注）。

`mainmenu-entry-plan.md`：在已有的"勘误（2026-09-02 实施后）"引用块后追加一段，指出
§2.1/2.2 的 8 处手工改动实现已成 `layers/overlays/encore-menu.toml`，`snr_finale.lua`
canonical 源同期迁移，指向 `docs/ops/disc-pipeline.md`。该文档里另外两处
`script/snr_finale.lua`（cGetFileName 拼接出的运行期成员名）不是 `docs/finale/` 路径，
本就正确，未改动。

## Step 5 验收输出

```
$ uv run pytest -q -m "not emu"
........................................................................ [  4%]
（省略中间进度行）
...................s.....................                                [100%]
1766 passed, 3 skipped, 6 deselected in 303.14s (0:05:03)

$ uv run python tools/layers.py check --profile release
[layers] release: 施加 2 层（fonts, encore-menu），新增成员 1
[layers] 全部层命中 ✓

$ uv run python tools/layers.py check --profile test
[layers] test: 施加 4 层（fonts, encore-menu, strip-ipl, boot-handoff），新增成员 1
[layers] 全部层命中 ✓

$ uv run python tools/migrate_base.py --check
[migrate] 新基座 229 文件 / 现有 229 文件
[migrate] 基座纯净 ✓（229 文件 == 语料 + tr_line 标记）

$ uv run python tools/build_ledger.py --check
check: OK

$ grep -rn "make_test_boot\|build/inject\b" docs/ops/disc-pipeline.md CLAUDE.md || echo "无过时引用 ✓"
无过时引用 ✓
```

全绿。（3 skipped 是既有的 `local_assets` 标记测试，本机没跑 `--compare-compiled` 依赖
的 `~/pyluadec-refactor` 全套；6 deselected 是 `-m "not emu"` 排除的模拟器测试，符合预期，
`pytest.ini` 里两个标记的说明与此一致。）

## 自检

- 逐条核对新文档与 CLAUDE.md 里的每条命令：`layers.py check/diff/ids`、
  `build_disc.py --profile/--stage/--mode/--scene/--card/--force/--no-fast-boot`、
  `build_font.py --charset/--out/--sizes/--ruby-size`、`migrate_base.py --check`、
  `build_ledger.py --check`、`read_commit.py --data-dir/--apply` —— 全部对着各自
  `--help` 核实存在且拼写正确。
- 阶段表七行（lua/font/members/stage/pack/disc/iso）+ boot，逐行对照 `build_disc.py`
  模块 docstring 与对应函数体（`stage_lua`/`stage_font`/`stage_members`/`stage_stage`/
  `stage_pack`/`stage_disc`/`stage_iso`）核实语义一致，未照抄 spec 文档了事。
  发布三道断言的具体内容（stage 树指纹、独立重编译核对、成员集合+测试引导成员）
  逐字对照 `stage_iso()`/`release_assertions()` 源码。
- 走查示例的锚点用 `tools.layers.find_all` 实际跑过，确认在真实 `lua_scripts/snr_novel.lua`
  上命中 1 次（不是凭印象编的）。
- Step5 的 grep 检查本身第一轮**没通过**——`disc-pipeline.md` 里一句历史性描述
  "此前两个剖面共用一棵 `build/inject`/`build/stage`" 里的 `` `build/inject` `` 字面命中
  了 grep 模式 `build/inject\b`（反引号不是词字符，`\b` 在其前成立），导致该命令会打印
  这一行而不是"无过时引用 ✓"。已重写为不含该字面路径的表述并重新验证通过。这是唯一
  一处在自检里被抓到、修正过的问题。
- grep 扫了 `make_test_boot`/`build/inject`/`inject_src`/`docs/finale/snr_finale.lua`/
  `NEW_GIM_SOURCES`/`check_release_clean` 六个词，在 `disc-pipeline.md`、`CLAUDE.md`、
  两份 finale 文档里全部干净；四份带日期文档里仅剩的历史引用（`finale-stage-impl-
  2026-09-02.md` 待办第 5 条里的 `docs/finale/snr_finale.lua`）按要求保留不动（那是
  Step 3 的"保留历史"范围，brief 明确要求不重复处理这份文件的复验内容）。

## 关切 / 遗留

- `layers.py check` 目前不扫描叠加层内新引入的 vms/msg id（见上文"发现的缺口"）；
  这是代码现状，不是本任务范围内该修的东西（brief 明确"仅文档"），已在 disc-pipeline.md
  的走查示例与故障排查两处如实说明并给出手工补救路径，供后续任务参考。
- `.superpowers/sdd/2026-09-02-disc-layers-pipeline/progress.md` 在会话开始后被
  （非本任务操作）自动追加了一行 "Task 9: complete…"，成为 git 未跟踪的修改。
  按 brief Step 6 明确给出的 `git add docs/ CLAUDE.md` 命令，本次提交未包含它，
  留给后续处理。
