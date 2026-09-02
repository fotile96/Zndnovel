## Task 10: 文档收口

**Files:**
- Create: `docs/ops/disc-pipeline.md`
- Modify: `CLAUDE.md`, `docs/ops/zh-disc-pipeline-2026-08-31.md`,
  `docs/ops/release-2026-09-01-volunteer-build.md`,
  `docs/ops/finale-stage-impl-2026-09-02.md`,
  `docs/ops/decompiler-base-migration-2026-08-31.md`,
  `docs/finale/handoff-stage-impl.md`, `docs/finale/mainmenu-entry-plan.md`

- [ ] **Step 1: 写 `docs/ops/disc-pipeline.md`**

不带日期，作为唯一现行说明。目录：一条命令；基座/层/剖面三概念；四类改动各自的落点与命令
（对照 spec §6.8 的表）；阶段表；加一个新层的完整走查（以 novel 入口提示为例：建
`layers/overlays/novel-notice.toml`、在 `manifest.toml` 的 order 排位、在 `vms_ids.toml`
登记区段、`layers.py check`、`build_disc.py`）；各道闸与它们各自防的是什么；
故障排查（锚点不中、id 撞号、字体过期、成员集合不符）。

- [ ] **Step 2: 改 CLAUDE.md**

三处：

1. 「仓库文件构成」的 `lua_scripts/` 条目后补一句：**`lua_scripts/` 是只读纯净基座，
   与原始字节码逐字节等价（`luac_norm` 229/229，由 `tests/test_base_fidelity.py` 钉住）；
   一切本地化改动是 `layers/` 下的层，绝不直接改基座。** 并在树里加 `layers/` 条目。
2. 「常用操作」的出盘那条改为新命令面，加 `layers.py check`。
3. 「开发规约」加一条「层纪律」：新增本地化文本 → 建叠加层 + 登记 id；
   改谢幕章 → 改 `layers/scripts/snr_finale.lua`；测试捷径 → `--profile test`，
   永远不要手改 `lua_scripts/`。

同时删掉「谢幕章」条目里「canonical 源刻意不入 lua_scripts」那段关于
`docs/finale/snr_finale.lua` 的路径描述，改指 `layers/scripts/`。

- [ ] **Step 3: 给四份旧 ops 文档加取代声明**

每份在标题下加一行：

```markdown
> ⚠ **已被 `docs/ops/disc-pipeline.md` 取代**（2026-09-02 管线规范化）。本文保留为历史
> 记录：其中的实测数据与故障机理仍然有效，但**命令与目录结构已过时**，不要照抄。
```

`zh-disc-pipeline-2026-08-31.md` 的「当前状态与已知缺口」一节额外标注：39 条漏译与
槽 1 未换两条早已修掉，缺字问题由新管线的字体新鲜度检查覆盖。

- [ ] **Step 4: 改两份 finale 文档的路径引用**

`docs/finale/handoff-stage-impl.md` 与 `mainmenu-entry-plan.md` 里所有
`docs/finale/snr_finale.lua` 改成 `layers/scripts/snr_finale.lua`；
mainmenu-entry-plan 补一句「实现已成 `layers/overlays/encore-menu.toml`」。

- [ ] **Step 5: 最终验收**

```bash
uv run pytest -q -m "not emu"
uv run python tools/layers.py check --profile release
uv run python tools/layers.py check --profile test
uv run python tools/migrate_base.py --check
uv run python tools/build_ledger.py --check
grep -rn "make_test_boot\|build/inject\b" docs/ops/disc-pipeline.md CLAUDE.md || echo "无过时引用 ✓"
```

Expected: 全绿；最后一条打印那句话。

- [ ] **Step 6: 提交**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: 管线文档收口——disc-pipeline.md 成为唯一现行说明

新写不带日期的 docs/ops/disc-pipeline.md：基座/层/剖面三概念、四类改动各自的落点与
命令、加一个新层的完整走查（以 novel 入口提示为例）、各道闸防的是什么、故障排查。
CLAUDE.md 三处改写，核心一句「lua_scripts 是只读纯净基座，一切本地化改动是层」。
四份带日期的 ops 文档加取代声明并保留为历史；finale 两份文档更新 snr_finale 路径。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## 完成后

分支 `feat/finale-stage` 上此时应有：Task 1–10 共 10 个 commit，加上此前的谢幕章 7 个
与设计稿 2 个。合并前跑一次完整验收（Task 10 Step 5）。实机验收清单不变，仍在
`docs/ops/finale-stage-impl-2026-09-02.md` 末节：CFW 引导、bgm_20_b/20_c 听曲、
版面实机目测、旧档兼容抽验。

**新管线下的日常**：

| 要做的事 | 怎么做 |
|---|---|
| 改一行译文 | `read_commit --apply` 后 `build_disc.py` |
| 改谢幕章台词 | 改 `layers/scripts/snr_finale.lua` 后 `build_disc.py` |
| 加一段新文本 | 建叠加层 + `manifest.toml` 排序 + `vms_ids.toml` 登记，`layers.py check` 后 `build_disc.py` |
| 跳到某场景测试 | `build_disc.py --profile test --mode scene --scene <ID>` |
