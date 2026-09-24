### Task 5: 测试捷径 `--finale-read`（预置旗标进主菜单/直入场景）

**Files:**
- Modify: `tools/testboot.py`（两个模板、`_render_mode`、CLI）
- Modify: `tools/build_disc.py`（CLI 一项、`mode_opts` 一键）
- Modify: `tests/test_testboot.py`（追加两个测试）

**Interfaces:**
- Consumes: `generate(mode, out_dir, **opts)` → `_render_mode(mode, **opts)`
- Produces: `_render_mode(..., finale_read: bool = False)`；`build_disc.py --profile test --mode mainmenu --finale-read`（Task 6 用）

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_testboot.py` 末尾）

```python
def test_finale_read_preset_lands_before_menu_and_scene_entry(out_dir):
    """--finale-read：测试盘开机就把 systemSave.finaleReadFlag 置 true（布尔新键，不碰原有数字字段），
    主菜单 encore 会出『声』选择画面、题名 logo 为中文；直入场景同样带上。"""
    generate("mainmenu", out_dir, finale_read=True)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert "    systemSave.finaleReadFlag = true\n" in src
    assert src.index("systemSave.finaleReadFlag = true") < src.index('run(cGetFileName("script", "snr_mainmenu"))')
    generate("scene", out_dir, scene="fin-10", finale_read=True)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert src.index("systemSave.finaleReadFlag = true") < src.index('doScriptScene = "fin-10"')


def test_finale_read_preset_is_off_by_default(out_dir):
    for mode, opts in (("mainmenu", {}), ("scene", {"scene": "fin-10"})):
        generate(mode, out_dir, **opts)
        src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
        assert "finaleReadFlag" not in src
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_testboot.py -q -k finale_read`
Expected: FAILED（`TypeError: _render_mode() got an unexpected keyword argument 'finale_read'`）。

- [ ] **Step 3: 改 `tools/testboot.py`**

3a. `MAINMENU_TEMPLATE`：在 `    run(cGetFileName("script", "snr_mainmenu"))` 前一行插入 `{preset}`（注意模板现有 `⚠ 不要在这里动 systemSave` 注释说的是**数字字段**；本旗标是布尔新键，只被 `== true` 读，见 layers/overlays/finale-read-flag.toml）。即：

```lua
    -- 何况这两个字段跟「解锁」无关，本就不该设。设置项交给 option 画面自己去改。
{preset}    run(cGetFileName("script", "snr_mainmenu"))
```

3b. `SCENE_TEMPLATE`：在 `    doScriptScene = "{scene}"` 前一行插入 `{preset}`：

```lua
    cInitStoryRoute()
{preset}    doScriptScene = "{scene}"
```

3c. `_render_mode` 签名加 `finale_read: bool = False`，函数开头加

```python
    # --finale-read：预置「已读过谢幕第一个故事」（布尔新键，缺省 false；不碰 systemSave 原有数字字段）
    preset = "    systemSave.finaleReadFlag = true\n" if finale_read else ""
```

并把两处 `.format(...)` 补上 `preset=preset`：`MAINMENU_TEMPLATE.format(route=story_route(), hold=-1 if no_cards else 1, preset=preset)`、`SCENE_TEMPLATE.format(scene=scene, script=scene_to_script(scene), hold=-1 if no_cards else 1, preset=preset)`。

3d. `main()` 的 argparse 加 `ap.add_argument("--finale-read", action="store_true", help="mainmenu/scene 模式预置 systemSave.finaleReadFlag = true（谢幕『声』选择画面、中文题名）")`，并把 `generate(args.mode, args.out, scene=..., card=..., ...)` 调用补上 `finale_read=args.finale_read`。

- [ ] **Step 4: 改 `tools/build_disc.py`**

argparse 在 `--skippable` 之后加：

```python
    ap.add_argument("--finale-read", action="store_true",
                    help="test 剖面 mainmenu/scene 模式：预置 systemSave.finaleReadFlag = true（谢幕『声』选择画面）")
```

`mode_opts` 字典加一键 `"finale_read": args.finale_read`。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_testboot.py tests/test_build_disc.py -q`
Expected: 全部 passed。

- [ ] **Step 6: 提交**

```bash
git add tools/testboot.py tools/build_disc.py tests/test_testboot.py
git commit -m "feat: testboot/build_disc 加 --finale-read——测试盘预置 finaleReadFlag，主菜单直达谢幕『声』选择画面

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

