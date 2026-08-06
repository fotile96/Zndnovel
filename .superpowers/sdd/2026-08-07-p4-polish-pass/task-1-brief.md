### Task 1: 命名统一 polish

**Files:**
- Rename: `glossary/style_refine.md` → `glossary/polish.md`
- Modify: 文内 §7.1 自述路径；`docs/ops/p3-production-runbook.md` 中出现的 `style_refine.md` 字样
- 车道配置: `pilot/lanes/opus/lane.json` 的 `freeze_exclude`（经 CLI 改，不手编）

**Interfaces:**
- Produces: 此后一切引用固定为 `glossary/polish.md`；opus 车道排除集含新路径。

- [ ] **Step 1: 查清全部引用**

Run: `grep -rn "style_refine" --include="*.py" --include="*.md" --include="*.json" /Users/fotile96/Zndnovel --exclude-dir=.git`
记录清单（预期：glossary/style_refine.md 自身、runbook、opus lane.json、可能的 spec/handoff 文档）。

- [ ] **Step 2: git mv + 引用替换**

```bash
git mv glossary/style_refine.md glossary/polish.md
```
逐个 Edit 替换 Step 1 清单里的路径字样（spec/历史 handoff 里的**叙述性**提法保留原文+括注新名，不改史料）。

- [ ] **Step 3: 更新 opus 车道排除集并校验**

```bash
uv run python tools/lane_setup.py --set-exclude opus --freeze-exclude glossary/polish.md
uv run python tools/lane_setup.py --verify
```
Expected: `冻结校验：无漂移`；`ℹ 有意排除` 列表含 `glossary/polish.md` 不含旧名。
（`--set-exclude` 的实际参数名以 `lane_setup.py main()` 现行 CLI 为准，执行前先 `--help` 核对。）

- [ ] **Step 4: 全量测试**

Run: `uv run pytest -q`
Expected: 567 passed（若有测试引用旧路径，随本 task 修正）。

- [ ] **Step 5: Commit**

```bash
git add glossary/polish.md docs/ops/p3-production-runbook.md pilot/lanes/lanes-manifest.json pilot/lanes/opus/lane.json
git commit -m "chore: style_refine.md 统一更名 polish.md（含 opus 车道排除集迁移）"
```
（实际待 add 文件以 `git status` 为准，仍逐一显式列出。）

---

