## Task 9: 模拟器复验

**Files:**
- Create: `tools/emu/drives/` （收纳驾驶脚本）
- Modify: `docs/ops/finale-stage-impl-2026-09-02.md`（追加复验结果）

**Interfaces:**
- Consumes: Task 8 的两个剖面

- [ ] **Step 1: 收纳既有驾驶脚本**

```bash
mkdir -p tools/emu/drives
cp /tmp/finale_smoke/drive_menu.py    tools/emu/drives/menu.py
cp /tmp/finale_smoke/drive_lib3.py    tools/emu/drives/library.py
cp /tmp/finale_smoke/drive_no144.py   tools/emu/drives/no_card144.py
cp /tmp/finale_smoke/drive_full.py    tools/emu/drives/finale_full.py
cp /tmp/finale_smoke/drive_iso.py     tools/emu/drives/release_iso.py
cp /tmp/finale_smoke/drive_glyph.py   tools/emu/drives/glyph.py
```

在 `tools/emu/drives/` 下写一份 `README.md`：每个脚本验什么、怎么跑、期望看到什么。

- [ ] **Step 2: release 剖面复验**

```bash
uv run python tools/build_disc.py --profile release --stage lua,font,members,stage,pack,disc
uv run python tools/emu/drives/menu.py        # 12 项版面 + encore 亮暗态
uv run python tools/emu/drives/library.py     # library 子列四项齐全
uv run python tools/emu/drives/no_card144.py  # 无 144 档回归 11 项
uv run python tools/emu/drives/finale_full.py # 谢幕全章跑通回主菜单
```

逐个看截图确认，ERROR 日志应为 0 条。

- [ ] **Step 3: test 剖面复验**

```bash
uv run python tools/build_disc.py --profile test --mode scene --scene fin-30
uv run python tools/emu/drives/glyph.py       # 改指 build/test/game
uv run python tools/build_disc.py --profile test --mode mainmenu
```

确认：直入 fin-30；IPL 已剥；`build/dist/` 与 `build/release/` 未被触碰
（`shasum -a 256 build/dist/game_zh.iso` 与 Task 8 记的值相同）。

- [ ] **Step 4: 发布 ISO 原版开机链**

```bash
uv run python tools/build_disc.py --profile release --stage iso
uv run python tools/emu/drives/release_iso.py
```

确认走完整 IPL、标题菜单是初始形态、ERROR 日志与原盘同源。

- [ ] **Step 5: 提交**

```bash
git add tools/emu/drives docs/ops/finale-stage-impl-2026-09-02.md
git commit -m "test: 模拟器复验矩阵通过 + 驾驶脚本收纳入库

新链路的 release 盘在模拟器上复验：12 项菜单与 encore 亮暗态、library 子列、
无 144 档回归、谢幕全章、发布 ISO 原版开机链，ERROR 日志均 0 条。test 剖面直入
fin-30 且 build/dist 未被触碰——剖面隔离生效。六个驾驶脚本自 /tmp 收进
tools/emu/drives/，附 README 说明各验什么。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

