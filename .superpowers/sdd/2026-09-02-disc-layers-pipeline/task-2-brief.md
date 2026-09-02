## Task 2: 清单与 id 登记的加载与校验

**Files:**
- Modify: `tools/layers.py`
- Create: `layers/manifest.toml`, `layers/vms_ids.toml`
- Modify: `tests/test_layers.py`

**Interfaces:**
- Consumes: Task 1 的 `OverlayError`、`apply_overlay`
- Produces:
  - `load_manifest(root: Path = REPO / "layers") -> dict` — 校验后的清单，键 `base` / `lane` / `compiler` / `overlays` / `scripts` / `gim` / `fonts`
  - `load_overlay(path: Path) -> dict` — 单个叠加层，含 `_name`
  - `overlays_for(manifest, root, profile, switches) -> list[dict]` — 按 `order` 过滤剖面与开关
  - `collect_ids(text: str) -> set[int]` — 扫 `vms(N,` / `msg(N,`
  - `check_ids(manifest, root, ledger_ids: set[int]) -> None`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_layers.py`：

```python
import tomllib
from pathlib import Path

from tools.layers import (REPO, check_ids, collect_ids, load_manifest, load_overlay,
                          overlays_for)

MINIMAL_MANIFEST = """
[base]
dir = "lua_scripts"
ledger = "data/ledger.jsonl"
ledger_extra = "data/ledger_extra.jsonl"
[lane]
dir = "pilot/lanes/opus/data"
[compiler]
luac = "~/pyluadec-refactor/build/luac_sz4"
header_hex = "1b4c75615100010404040800"
[overlays]
order = ["alpha"]
[gim]
replace = [["card_zh", "card"]]
new = [["finale_cards", "card", "card/crd_1_a.gim"]]
[[fonts]]
size = 17
member = "pgf/A.pgf"
"""

ALPHA_OVERLAY = """
target = "snr_common.lua"
profile = "release"
why = "测试用"
[[ops]]
op = "replace"
find = "a"
with = "b"
"""


def _mk_layers(tmp_path, manifest=MINIMAL_MANIFEST, overlays=None):
    root = tmp_path / "layers"
    (root / "overlays").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "manifest.toml").write_text(manifest, encoding="utf-8")
    for name, body in (overlays or {"alpha": ALPHA_OVERLAY}).items():
        (root / "overlays" / f"{name}.toml").write_text(body, encoding="utf-8")
    (root / "vms_ids.toml").write_text("", encoding="utf-8")
    return root


def test_load_manifest_reads_all_sections(tmp_path):
    m = load_manifest(_mk_layers(tmp_path))
    assert m["base"]["dir"] == "lua_scripts"
    assert m["gim"]["replace"] == [["card_zh", "card"]]
    assert m["fonts"][0]["member"] == "pgf/A.pgf"


def test_unknown_top_level_key_is_hard_failure(tmp_path):
    root = _mk_layers(tmp_path, manifest=MINIMAL_MANIFEST + '\n[bogus]\nx = 1\n')
    with pytest.raises(SystemExit) as e:
        load_manifest(root)
    assert "bogus" in str(e.value)


def test_overlay_missing_why_is_hard_failure(tmp_path):
    bad = ALPHA_OVERLAY.replace('why = "测试用"', "")
    root = _mk_layers(tmp_path, overlays={"alpha": bad})
    with pytest.raises(SystemExit):
        load_overlay(root / "overlays" / "alpha.toml")


def test_overlay_bad_profile_is_hard_failure(tmp_path):
    bad = ALPHA_OVERLAY.replace('profile = "release"', 'profile = "staging"')
    root = _mk_layers(tmp_path, overlays={"alpha": bad})
    with pytest.raises(SystemExit):
        load_overlay(root / "overlays" / "alpha.toml")


def test_order_must_list_every_overlay_file(tmp_path):
    root = _mk_layers(tmp_path, overlays={"alpha": ALPHA_OVERLAY, "beta": ALPHA_OVERLAY})
    with pytest.raises(SystemExit) as e:
        load_manifest(root)
    assert "beta" in str(e.value)


def test_overlays_for_release_excludes_test_layers(tmp_path):
    test_layer = ALPHA_OVERLAY.replace('profile = "release"', 'profile = "test"')
    root = _mk_layers(tmp_path,
                      manifest=MINIMAL_MANIFEST.replace('order = ["alpha"]',
                                                        'order = ["alpha", "beta"]'),
                      overlays={"alpha": ALPHA_OVERLAY, "beta": test_layer})
    m = load_manifest(root)
    assert [o["_name"] for o in overlays_for(m, root, "release", {})] == ["alpha"]
    assert [o["_name"] for o in overlays_for(m, root, "test", {})] == ["alpha", "beta"]


def test_switch_off_drops_the_layer(tmp_path):
    sw = ALPHA_OVERLAY.replace('why = "测试用"', 'why = "测试用"\nswitch = "fast-boot"')
    root = _mk_layers(tmp_path, overlays={"alpha": sw})
    m = load_manifest(root)
    assert overlays_for(m, root, "release", {}) != []
    assert overlays_for(m, root, "release", {"fast-boot": False}) == []


def test_collect_ids_finds_vms_and_msg():
    assert collect_ids('vms(17300, "NONVOICE", "x")\nmsg(9001, "y")\n') == {17300, 9001}


def test_collect_ids_ignores_non_call_digits():
    assert collect_ids('local x = 17300\nxmsg(5, "y")\n') == set()


def test_check_ids_rejects_collision_with_ledger(tmp_path):
    root = _mk_layers(tmp_path)
    (root / "scripts" / "s.lua").write_text('vms(100, "NONVOICE", "x")\n', encoding="utf-8")
    man = load_manifest(root)
    man["scripts"] = [{"file": "scripts/s.lua", "member": "script/s.lua",
                       "profile": "release"}]
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "scripts/s.lua"\nvms = [[100, 200]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids={100})
    assert "100" in str(e.value)


def test_check_ids_rejects_id_outside_declared_range(tmp_path):
    root = _mk_layers(tmp_path)
    (root / "scripts" / "s.lua").write_text('vms(999, "NONVOICE", "x")\n', encoding="utf-8")
    man = load_manifest(root)
    man["scripts"] = [{"file": "scripts/s.lua", "member": "script/s.lua",
                       "profile": "release"}]
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "scripts/s.lua"\nvms = [[100, 200]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "999" in str(e.value)


def test_check_ids_rejects_overlapping_owner_ranges(tmp_path):
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    (root / "vms_ids.toml").write_text(
        '[[ranges]]\nowner = "a"\nvms = [[100, 200]]\n'
        '[[ranges]]\nowner = "b"\nvms = [[150, 250]]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        check_ids(man, root, ledger_ids=set())
    assert "重叠" in str(e.value)
```

- [ ] **Step 2: 跑测试确认全红**

Run: `uv run pytest tests/test_layers.py -q -k "manifest or overlay or ids or switch or order"`
Expected: FAIL — `ImportError: cannot import name 'load_manifest'`

- [ ] **Step 3: 写实现**

追加到 `tools/layers.py`（放在 `apply_overlay` 之后）：

```python
import tomllib

LAYERS = REPO / "layers"
PROFILES = ("release", "test")
CARD_MSG_RESERVED = range(18001, 18196)   # oCard.show 动态 id = 18000 + 卡号（卡 1..195）

_MANIFEST_KEYS = {"base", "lane", "compiler", "overlays", "scripts", "gim", "fonts"}
_OVERLAY_KEYS = {"target", "profile", "why", "switch", "ops"}


def _read_toml(path: Path) -> dict:
    if not path.exists():
        raise OverlayError(f"缺 {path}")
    with open(path, "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise OverlayError(f"{path} 不是合法 TOML：{exc}") from None


def load_overlay(path: Path) -> dict:
    """读一个叠加层文件并校验。`_name` = 文件名去 .toml。"""
    d = _read_toml(path)
    unknown = set(d) - _OVERLAY_KEYS
    if unknown:
        raise OverlayError(f"{path.name} 有未知键 {sorted(unknown)}")
    for key in ("target", "profile", "why"):
        if not d.get(key):
            raise OverlayError(f"{path.name} 缺 {key}（why 必须写清依据，不许留空）")
    if d["profile"] not in PROFILES:
        raise OverlayError(f"{path.name} 的 profile={d['profile']!r} 非法（只能 {PROFILES}）")
    if not d.get("ops"):
        raise OverlayError(f"{path.name} 没有任何 [[ops]]")
    d["_name"] = path.stem
    return d


def load_manifest(root: Path = LAYERS) -> dict:
    """读清单并校验：未知键报错；order 必须与 overlays/ 下的文件一一对应。"""
    man = _read_toml(root / "manifest.toml")
    unknown = set(man) - _MANIFEST_KEYS
    if unknown:
        raise OverlayError(f"manifest.toml 有未知键 {sorted(unknown)}")
    for key in ("base", "lane", "compiler", "overlays"):
        if key not in man:
            raise OverlayError(f"manifest.toml 缺 [{key}]")
    order = man["overlays"].get("order", [])
    on_disk = sorted(p.stem for p in (root / "overlays").glob("*.toml"))
    if sorted(order) != on_disk:
        raise OverlayError(
            f"manifest.toml 的 overlays.order 与 layers/overlays/ 下的文件不一致：\n"
            f"  order  = {sorted(order)}\n  on disk = {on_disk}\n"
            f"新加的层必须在 order 里排位置——施加顺序是语义的一部分")
    man.setdefault("scripts", [])
    man.setdefault("gim", {"replace": [], "new": []})
    man.setdefault("fonts", [])
    return man


def overlays_for(manifest: dict, root: Path, profile: str, switches: dict) -> list[dict]:
    """按 order 取该剖面要施加的层。release 层在两个剖面都施加；test 层只在 test。

    switches: {开关名: bool}。带 switch 的层缺省施加，显式给 False 才关掉。
    """
    if profile not in PROFILES:
        raise OverlayError(f"未知剖面 {profile!r}")
    out = []
    for name in manifest["overlays"]["order"]:
        ov = load_overlay(root / "overlays" / f"{name}.toml")
        if ov["profile"] == "test" and profile != "test":
            continue
        if "switch" in ov and switches.get(ov["switch"], True) is False:
            continue
        out.append(ov)
    return out


import re as _re

#: 只认真正的调用：`vms(N,` / `msg(N,`。左侧的 (?<![A-Za-z0-9_]) 挡住 xmsg(/debagMsg( 之类。
_ID_CALL_RE = _re.compile(r"(?<![A-Za-z0-9_])(?:vms|msg)\((\d+),")


def collect_ids(text: str) -> set[int]:
    """扫一段 lua（或叠加层的 with/text 字段）里出现的全部消息 id。"""
    return {int(m.group(1)) for m in _ID_CALL_RE.finditer(text)}


def _ranges_of(entry: dict, key: str) -> list[range]:
    out = []
    for pair in entry.get(key, []):
        lo, hi = pair
        if lo > hi:
            raise OverlayError(f"区段 [{lo}, {hi}] 顺序颠倒（owner={entry.get('owner')}）")
        out.append(range(lo, hi + 1))
    return out


def check_ids(manifest: dict, root: Path, ledger_ids: set[int]) -> None:
    """id 登记检查：落在本层区段内、owner 区段两两不交、不与保留集相交、全局唯一。

    保留集 = 账本 id ∪ [18001, 18195]（卡消息由引擎按 18000 + 卡号动态生成）。
    test 层免于与保留集比对（探针沿用 9000 段，测试盘永不出货），但层间仍须不交。
    """
    reg = _read_toml(root / "vms_ids.toml")
    owned: dict[str, list[range]] = {}
    for entry in reg.get("ranges", []):
        owner = entry.get("owner")
        if not owner:
            raise OverlayError("vms_ids.toml 有 [[ranges]] 缺 owner")
        owned[owner] = _ranges_of(entry, "vms") + _ranges_of(entry, "card_msg")

    seen: dict[int, str] = {}
    for owner, rs in owned.items():
        for r in rs:
            for other, ors in owned.items():
                if other <= owner:
                    continue
                for o in ors:
                    if max(r.start, o.start) < min(r.stop, o.stop):
                        raise OverlayError(
                            f"id 区段重叠：{owner} 与 {other} 在 "
                            f"[{max(r.start, o.start)}, {min(r.stop, o.stop) - 1}] 相交")
            hit = sorted(set(r) & (ledger_ids | set(CARD_MSG_RESERVED)))
            if hit:
                raise OverlayError(
                    f"{owner} 声明的区段撞上保留 id {hit[:5]}"
                    f"（账本 1..17220 与卡消息 18001..18195 已占）")

    for spec in manifest["scripts"]:
        if spec.get("profile", "release") != "release":
            continue
        # spec["file"] 形如 "scripts/snr_finale.lua"，相对 layers/ 根。
        # 用传进来的 root 而不是模块级 LAYERS——夹具测试要能指向 tmp_path。
        text = (root / spec["file"]).read_text(encoding="utf-8")
        _check_ids_of(spec["file"], text, owned, seen, ledger_ids)


def _check_ids_of(owner: str, text: str, owned, seen, ledger_ids) -> None:
    ranges = owned.get(owner)
    if ranges is None:
        raise OverlayError(f"{owner} 没有在 layers/vms_ids.toml 登记 id 区段")
    for i in sorted(collect_ids(text)):
        if not any(i in r for r in ranges):
            raise OverlayError(
                f"{owner} 用了 id {i}，不在其声明的区段内——"
                f"在 layers/vms_ids.toml 里扩段，或改用段内的 id")
        if i in ledger_ids:
            raise OverlayError(f"{owner} 的 id {i} 与账本冲突")
        if i in seen:
            raise OverlayError(f"id {i} 被 {seen[i]} 与 {owner} 同时使用")
        seen[i] = owner
```

- [ ] **Step 4: 跑测试确认全绿**

Run: `uv run pytest tests/test_layers.py -q`
Expected: PASS（约 28 passed）

- [ ] **Step 5: 提交**

```bash
git add tools/layers.py tests/test_layers.py
git commit -m "feat: 清单与 id 登记的加载与校验

manifest.toml 未知键报错、order 必须与 overlays/ 下文件一一对应（施加顺序是语义的
一部分）；叠加层 why 字段强制非空。check_ids 四道：落在本层声明区段内、owner 区段
两两不交、不与保留集（账本 ∪ 卡消息 18001..18195）相交、release 层间全局唯一。
test 层免于与保留集比对——探针沿用 9000 段且测试盘永不出货。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

