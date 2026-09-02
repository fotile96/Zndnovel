## Task 7: testboot 生成器化

**Files:**
- Rename: `tools/make_test_boot.py` → `tools/testboot.py`
- Create: `tests/test_testboot.py`

**Interfaces:**
- Consumes: Task 1–2 的层文件格式
- Produces: `generate(mode: str, out_dir: Path, **opts) -> dict` — 写出 `overlays/*.toml` 与 `scripts/snr_test.lua`，返回 `{"scripts": [...], "overlays": [...]}`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_testboot.py`：

```python
"""testboot 生成器：产层文件，不再直接写字节码。"""
import tomllib

import pytest

from tools.testboot import generate


def test_mainmenu_mode_emits_test_script(tmp_path):
    r = generate("mainmenu", tmp_path)
    assert r["scripts"] == ["scripts/snr_test.lua"]
    src = (tmp_path / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert "gameSave.startMenuState = 2" in src
    assert 'run(cGetFileName("script", "snr_mainmenu"))' in src


def test_scene_mode_targets_the_right_chapter_script(tmp_path):
    generate("scene", tmp_path, scene="fin-30")
    src = (tmp_path / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'doScriptScene = "fin-30"' in src
    assert 'run(cGetFileName("script", "snr_finale"))' in src


def test_card_mode_emits_short_circuit_overlay(tmp_path):
    r = generate("card", tmp_path, card=103)
    assert "overlays/card-short-circuit.toml" in r["overlays"]
    ov = tomllib.loads(
        (tmp_path / "overlays" / "card-short-circuit.toml").read_text(encoding="utf-8"))
    assert ov["target"] == "snr_crd_103.lua"
    assert ov["profile"] == "test"
    assert ov["ops"][0]["find"] == "oCard.selectCardObj()"


def test_generated_overlays_are_never_release(tmp_path):
    for mode, opts in (("mainmenu", {}), ("card", {"card": 103}), ("scene", {"scene": "s1s_20"})):
        r = generate(mode, tmp_path, **opts)
        for rel in r["overlays"]:
            ov = tomllib.loads((tmp_path / rel).read_text(encoding="utf-8"))
            assert ov["profile"] == "test", f"{mode} 产出了 release 层——测试补丁绝不能出货"


def test_unknown_mode_is_hard_failure(tmp_path):
    with pytest.raises(SystemExit):
        generate("frobnicate", tmp_path)
```

- [ ] **Step 2: 跑测试确认全红**

Run: `uv run pytest tests/test_testboot.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.testboot'`

- [ ] **Step 3: 改造**

```bash
git mv tools/make_test_boot.py tools/testboot.py
```

保留全部模板常量（`FONT_PAGES`、`RUBY_VARIANTS`、`*_TEMPLATE`）与扫描函数
（`scan_cutins`、`scan_calls`、`story_route`、`card_answer`、`card_scene`、
`scene_to_script`、`short_circuit_card`）。删除 `LUAC`、`emit()`、`strip_ipl()`、
`BOOT_HANDOFF`、`emitted.json` 还原逻辑、`INJECT` 常量——剥 IPL 与引导交接现在是
`layers/overlays/` 里的静态层，成员还原由「成员树每次重建」取代。新增：

```python
def generate(mode: str, out_dir: Path, **opts) -> dict:
    """产测试层：scripts/snr_test.lua + 需要时的参数化叠加层。

    产物落 build/test/generated/，由 build_disc 在静态 test 层之后按文件名序施加。
    """
    src = _render_mode(mode, **opts)          # 原 main() 里那串 if/elif，抽成函数
    (out_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (out_dir / "scripts" / "snr_test.lua").write_text(src, encoding="utf-8")
    result = {"scripts": ["scripts/snr_test.lua"], "overlays": []}
    if mode == "card":
        card = opts["card"]
        answer = card_answer(card)
        ov = (f'target  = "snr_crd_{card}.lua"\n'
              f'profile = "test"\n'
              f'why     = "递卡短路：把玩家递卡换成 dag.json 记的正确答案卡 {answer}"\n'
              f'\n[[ops]]\nop    = "replace"\ncount = {_count_select_calls(card)}\n'
              f'find  = "oCard.selectCardObj()"\nwith  = "{answer}"\n')
        (out_dir / "overlays").mkdir(parents=True, exist_ok=True)
        (out_dir / "overlays" / "card-short-circuit.toml").write_text(ov, encoding="utf-8")
        result["overlays"].append("overlays/card-short-circuit.toml")
    return result
```

`_count_select_calls(card)` 读 `lua_scripts/snr_crd_<card>.lua` 数 `oCard.selectCardObj()` 出现次数。
`_render_mode` 里未知 mode 抛 `SystemExit`。

- [ ] **Step 4: 跑测试**

Run: `uv run pytest tests/test_testboot.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add tools/testboot.py tests/test_testboot.py
git commit -m "refactor: make_test_boot 改为层生成器 testboot.py

不再直接写 build/inject/script 的字节码，改为产 build/test/generated/ 下的层文件。
剥 IPL 与引导交接成了 layers/overlays/ 里的静态 test 层，递卡短路成参数化叠加层；
emitted.json 那套「记账-还原」随之作废——成员树每次重建，本就不会串味。
新增测试钉死一条：生成器产出的层 profile 恒为 test，测试补丁不可能出货。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

