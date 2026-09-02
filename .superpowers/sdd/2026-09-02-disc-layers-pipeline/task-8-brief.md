## Task 8: build_disc 剖面化【硬闸】

**Files:**
- Modify: `tools/build_disc.py`
- Create: `tests/test_build_disc.py`

**Interfaces:**
- Consumes: Task 1–7 全部
- Produces: `stage_lua/stage_font/stage_members/stage_stage/stage_pack/stage_disc/stage_iso/stage_boot`，全部接 `ctx: BuildContext`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_build_disc.py`（用三成员迷你 databin 夹具，不碰真实资产）：

```python
"""build_disc 的封闭测试：成员树、缓存、发布断言。用迷你 databin 夹具。"""
import json

import pytest

from tools.build_disc import assemble_stage, release_assertions


@pytest.fixture
def mini(tmp_path):
    """三成员的迷你封包树：a.gim / m.lua / z.pgf，manifest 按名有序。"""
    base = tmp_path / "databin"
    (base / "script").mkdir(parents=True)
    (base / "card").mkdir()
    (base / "card" / "a.gim").write_bytes(b"A")
    (base / "script" / "m.lua").write_bytes(b"M")
    rows = [{"name": "card/a.gim", "lzss": False, "sha1": ""},
            {"name": "script/m.lua", "lzss": False, "sha1": ""}]
    (base / "manifest.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return base


def _members(tmp_path, files: dict[str, bytes]):
    root = tmp_path / "members"
    for name, blob in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return root


def test_new_member_is_inserted_at_sorted_position(tmp_path, mini):
    members = _members(tmp_path, {"script/aaa.lua": b"NEW"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    names = [json.loads(l)["name"] for l in
             (stage / "manifest.jsonl").read_text().splitlines() if l]
    assert names == sorted(names)
    assert names.index("script/aaa.lua") < names.index("script/m.lua")


def test_existing_member_is_replaced_not_appended(tmp_path, mini):
    members = _members(tmp_path, {"script/m.lua": b"ZH"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    rows = [json.loads(l) for l in
            (stage / "manifest.jsonl").read_text().splitlines() if l]
    assert len(rows) == 2
    assert (stage / "script" / "m.lua").read_bytes() == b"ZH"


def test_stage_tree_is_rebuilt_not_accumulated(tmp_path, mini):
    stage_dir = tmp_path / "stage"
    assemble_stage(mini, _members(tmp_path, {"script/x.lua": b"1"}), stage_dir)
    assert (stage_dir / "script" / "x.lua").exists()
    (tmp_path / "members" / "script" / "x.lua").unlink()
    assemble_stage(mini, tmp_path / "members", stage_dir)
    assert not (stage_dir / "script" / "x.lua").exists(), "上一轮的成员没被清掉"


def test_release_assertion_rejects_unexpected_member(tmp_path, mini):
    members = _members(tmp_path, {"script/snr_test.lua": b"PROBE"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    bad = release_assertions(stage, mini, expected_new=set(), compiled=members / "script")
    assert any("snr_test" in b for b in bad)


def test_release_assertion_accepts_declared_new_member(tmp_path, mini):
    members = _members(tmp_path, {"script/snr_finale.lua": b"FIN"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    bad = release_assertions(stage, mini, expected_new={"script/snr_finale.lua"},
                             compiled=members / "script")
    assert bad == []


def test_release_assertion_catches_script_byte_mismatch(tmp_path, mini):
    members = _members(tmp_path, {"script/m.lua": b"ZH"})
    stage = assemble_stage(mini, members, tmp_path / "stage")
    (stage / "script" / "m.lua").write_bytes(b"TAMPERED")
    bad = release_assertions(stage, mini, expected_new=set(), compiled=members / "script")
    assert any("m.lua" in b for b in bad)
```

- [ ] **Step 2: 跑测试确认全红**

Run: `uv run pytest tests/test_build_disc.py -q`
Expected: FAIL — `ImportError: cannot import name 'assemble_stage'`

- [ ] **Step 3: 重写 build_disc.py**

要点（保留全部既有实测常量与注释，只改结构）：

```python
@dataclass
class BuildContext:
    profile: str            # release | test
    root: Path              # build/<profile>
    manifest: dict
    switches: dict
    mode_opts: dict         # test 剖面的 --mode/--scene/--card 等
    force: bool
```

- `stage_lua(ctx)`：读账本与车道 → `inject_lua.inject_tree` → 写 `root/lua/injected/`；
  test 剖面先调 `testboot.generate(...)` 产 `root/generated/`；
  `layers.build_final_sources(profile, switches, injected=…)`，并把 `root/generated/overlays/*.toml`
  按文件名序追加施加；`layers.check_ids`；写 `root/lua/final/`。
- `stage_font(ctx)`：**永远从 release 剖面的 `lua/final` 算字集**（test 复用 release 字体）。
  release 剖面若 `lua/final` 不存在则先跑 `stage_lua`。`layers.charset_of` → `write_charset`
  → 与 `build/font/ucs.txt` 比对，不等或 pgf 缺失就 `build_font.build(charset, build/font)`；
  缺 ttf_pgf 时硬失败并打印重建指令。
- `stage_members(ctx)`：`shutil.rmtree(root/"members")` 后重建；编译 `lua/final/*.lua`
  （校 PSP ABI 头）；gim 走 `build/cache/gim/<sha256(png ‖ tpl)[:16]>.gim`；字体拷入。
  烤图无对应成员、`new` 面撞既有成员 → 硬失败。
- 两个模块级纯函数（测试直接 import，不经 `BuildContext`）：

```python
def assemble_stage(base: Path, members: Path, stage_dir: Path) -> Path:
    """封包树 = 基座镜像快照 + members 覆入。新成员按名插到排序位。

    ⚠ 新成员**必须**插到按名排序的位置，绝不能追加表尾。原包文件表严格按成员名
    升序，引擎按名二分查找；表一乱新成员就查不到。2026-08-31 三次实测定论：
    追加表尾 → sceFontOpenUserMemory(addr=0) ×169；插到 e_17 处 → 同样失败；
    排序位 → 零错误。
    """
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    subprocess.run(["cp", "-Rc", str(base), str(stage_dir)], check=True)  # APFS clone，秒级
    manifest = [json.loads(l) for l in
                (stage_dir / "manifest.jsonl").read_text().splitlines() if l]
    names = {m["name"] for m in manifest}
    for f in sorted(Path(members).rglob("*")):
        if not f.is_file():
            continue
        member = str(f.relative_to(members))
        dst = stage_dir / member
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        if member not in names:
            idx = bisect.bisect_left([m["name"] for m in manifest], member)
            manifest.insert(idx, {"name": member, "lzss": False, "sha1": ""})
            names.add(member)
    order = [m["name"] for m in manifest]
    if order != sorted(order):
        die("文件表失序——引擎二分查找会失败，检查新成员插入逻辑")
    (stage_dir / "manifest.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manifest))
    return stage_dir


def release_assertions(stage: Path, base: Path, expected_new: set[str],
                       compiled: Path) -> list[str]:
    """出盘前的结构断言。返回问题列表，空 = 放行。

    与旧 check_release_clean 的区别：那个只查「inject_src 里有的脚本是否一致」，
    查不出**多出来的**成员；这个正查成员集合，测试引导的新成员一个也藏不住。
    """
    bad: list[str] = []
    base_names = {json.loads(l)["name"] for l in
                  (base / "manifest.jsonl").read_text().splitlines() if l}
    stage_names = {json.loads(l)["name"] for l in
                   (stage / "manifest.jsonl").read_text().splitlines() if l}
    allowed = base_names | expected_new
    for extra in sorted(stage_names - allowed):
        bad.append(f"封包树有未声明的成员 {extra}（testboot 残留？）")
    for missing in sorted(allowed - stage_names):
        bad.append(f"封包树缺声明的成员 {missing}")
    if "script/snr_test.lua" in stage_names:
        bad.append("封包树里有测试引导成员 script/snr_test.lua")
    for p in sorted((stage / "script").glob("*.lua")):
        ref = Path(compiled) / p.name
        if not ref.exists():
            bad.append(f"script/{p.name} 不在本次编译产物里")
        elif ref.read_bytes() != p.read_bytes():
            bad.append(f"script/{p.name} 与本次编译产物不一致")
    return bad
```
- `stage_iso(ctx)`：仅 release；先跑 `release_assertions`，不过就 `die`。
- 全部阶段跑完写 `provenance.json`；release 另拷 `build/dist/game_zh.iso.provenance.json`。
- CLI：`--profile`、`--stage`（`lua,font,members,stage,pack,disc,iso,boot`）、`--force`、
  `--no-fast-boot`、`--mode/--scene/--card/--hold/--no-cards`。缺省 `all`：release 到 `iso`、
  test 到 `disc`，均不含 `boot`。

- [ ] **Step 4: 跑封闭测试**

Run: `uv run pytest tests/test_build_disc.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 跑硬闸——与迁移前的 stage 树逐成员比对**

```bash
cp -Rc build/stage /tmp/stage_before                 # 迁移前的封包树（Task 4 之后未再动过）
uv run python tools/build_disc.py --profile release --stage lua,font,members,stage
uv run python - <<'PY'
from pathlib import Path
import json
before, after = Path("/tmp/stage_before"), Path("build/release/stage")
nb = {json.loads(l)["name"] for l in (before/"manifest.jsonl").read_text().splitlines() if l}
na = {json.loads(l)["name"] for l in (after/"manifest.jsonl").read_text().splitlines() if l}
print("成员集合相同:", nb == na, "| 仅旧有:", sorted(nb-na)[:5], "| 仅新有:", sorted(na-nb)[:5])
diff = [n for n in sorted(nb & na) if (before/n).read_bytes() != (after/n).read_bytes()]
print(f"内容不同 {len(diff)} 个: {diff[:10]}")
PY
```

Expected: 成员集合相同；内容不同 **0 个**（Task 0 的字体热修已让两份字体也一致）。
若只有两个 pgf 不同，说明字集口径有出入，查明再定夺。

- [ ] **Step 6: 出盘并跑全套测试**

```bash
uv run python tools/build_disc.py --profile release
uv run pytest -q -m "not emu"
shasum -a 256 build/dist/game_zh.iso
cat build/release/provenance.json | head -30
```

Expected: 出盘成功、发布断言通过；测试全绿；provenance 里 `tools.luac_sz4` 与
`tools.ttf_pgf` 都不是 `absent`。

- [ ] **Step 7: 提交**

```bash
git add tools/build_disc.py tests/test_build_disc.py
git commit -m "feat: build_disc 剖面化——release/test 各自独立输出树 + 依赖建模

--profile 分离两棵树，test 产物不可能落进 build/dist（此前共用 build/inject，
2026-09-02 一次测试盘构建就把 build/dist/DATA.BIN 换成了带探针的封包）。
字体阶段改为「从 release 最终源算字集、与现役 ucs.txt 比对、不等即重建」——
过期字体从此是硬失败而不是无声出货。成员树每次重建，gim 走内容哈希缓存；
发布断言升级为成员集合 + 脚本逐字节双查；每次构建落 provenance.json。

硬闸：新链路的 release stage 树与迁移前逐成员比对，内容差异 0。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

