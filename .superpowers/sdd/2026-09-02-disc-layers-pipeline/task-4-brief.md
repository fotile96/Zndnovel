## Task 4: 基座纯净化与叠加承接【硬闸】

> ⚠ **本任务必须是单个 commit**。基座还原与叠加层承接若分成两步，中间态的盘会丢掉谢幕入口与中文字体。

**Files:**
- Modify: `lua_scripts/snr_common.lua`, `lua_scripts/snr_mainmenu.lua`
- Create: `layers/overlays/fonts.toml`, `layers/overlays/encore-menu.toml`
- Move: `docs/finale/snr_finale.lua` → `layers/scripts/snr_finale.lua`
- Modify: `layers/manifest.toml`, `layers/vms_ids.toml`, `tools/layers.py`, `tools/migrate_base.py`, `tools/luac_norm.py`
- Create: `tests/test_layers_corpus.py`, `tests/test_base_fidelity.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: Task 1–3 全部
- Produces:
  - `tools/luac_norm.compare_dirs(a: Path, b: Path) -> tuple[int, int, int, list[str]]` — `(same, diff, err, names)`
  - `tools/layers.py` CLI：`check [--profile P] [--compare-compiled DIR]`、`diff <层名>`、`ids`
  - `build_final_sources(profile, switches) -> dict[str, str]` — 文件名 → 最终源文本

- [ ] **Step 1: 记录基线——当前 stage 树是唯一的正确性参照**

```bash
mkdir -p /tmp/layers_baseline
cp -R build/stage/script /tmp/layers_baseline/script
ls /tmp/layers_baseline/script | wc -l      # 期望 230
shasum -a 256 /tmp/layers_baseline/script/snr_mainmenu.lua
```

这 230 个字节码是「今日手工改动编出来的样子」。本任务结束时新链路必须逐字节复现它们。

- [ ] **Step 2: 写四个层文件**

`layers/overlays/fonts.toml`：

```toml
target  = "snr_common.lua"
profile = "release"
why     = """槽 0 = 正文 17px 中文字体；槽 1 = ruby/小字 9px。
2026-08-31 游戏内实测：ruby 走槽 1，槽 1 原配日文字体的简体字与声调元音全是空白，
不换就没有中文拼音注音。原先槽 0 由 migrate_base 重放、槽 1 由 inject_lua 改写，
两处分居；现在合并到这一个层里。"""

[[ops]]
op   = "replace"
find = 'fontLoad(0, "pgf/tsukuminpro_e_17.pgf")'
with = 'fontLoad(0, "pgf/LXGWWenKai-Regular.pgf")'

[[ops]]
op   = "replace"
find = 'fontLoad(1, "pgf/tsukuminpro_e_09.pgf")'
with = 'fontLoad(1, "pgf/LXGWWenKai-Regular-09.pgf")'
```

`layers/overlays/encore-menu.toml`：七个操作，`why` 写明依据是
`docs/finale/mainmenu-entry-plan.md` 与 `docs/ops/finale-stage-impl-2026-09-02.md`。
各操作的锚点与 count（已对纯净基座实测）：

| # | op | 锚点 | count | 内容来源 |
|---|---|---|---:|---|
| 1 | `replace` | 首行 `layerKey3 = {…}, layerWidth =` 整段 | 1 | 加 `layerKey4`（12 项）与 `title_14_a` 的宽 117 / 高 68 |
| 2 | `insert_before` | `        else\n            l0_1 = {story = 1, fragment = 2, section7 = 3, library = 4, option = 5, save = 6, load = 7, novel = 8, scene = 9, cg = 10, music = 11}\n` | 1 | 42 行 `elseif gameSave.myCard[144].hold == 1 then` 绘制块 |
| 3 | `insert_after` | 同上第二行（l0_1 那行） | 1 | `            l0_0.layerKeyCur = l0_0.layerKey3\n` |
| 4 | `insert_before` | `                        elseif l1_0 == l0_1.library then\n` | 1 | 6 行 finale 分发块 |
| 5 | `replace` | `for l1_7 = 1, 11, 1 do` | 1 | → `for l1_7 = 1, #l0_0.layerKeyCur, 1 do` |
| 6 | `replace` | `l0_0.layerKey3[l1_1]` | 3 | → `l0_0.layerKeyCur[l1_1]` |
| 7 | `replace` | `l0_0.layerKey3[l1_0]` | 3 | → `l0_0.layerKeyCur[l1_0]` |

操作 2 与 4 的 `text` 逐字取自当前 `lua_scripts/snr_mainmenu.lua`：

```bash
sed -n '/elseif gameSave.myCard\[144\].hold == 1 then/,/l0_3(l0_0.layerNumber.menu + 1, l0_0.layerKey4\[1\])/p' \
    lua_scripts/snr_mainmenu.lua > /tmp/encore_block.txt     # 42 行
sed -n '/elseif l1_0 == l0_1.finale then/,/^ *quit()$/p' \
    lua_scripts/snr_mainmenu.lua | head -6 > /tmp/finale_dispatch.txt
```

把两段原样贴进 TOML 的 `'''` 多行字面串（保留全部前导空格，以换行收尾）。

`layers/overlays/strip-ipl.toml`：

```toml
target  = "snr_common.lua"
profile = "test"
switch  = "fast-boot"
why     = """剥 IPL 开场：4 屏 logo 各淡入 120 帧 + keyWait 180 + 淡出 120 帧，
合计约 28 秒，每轮测试都要白等。四个图层进块前后都是 alpha 0，整块删除不改变末态。
`--no-fast-boot` 关掉本层即保留开场演出。"""

[[ops]]
op    = "delete_span"
start = "    layerMoveAlpha(0, 100, 120)\n"
end   = "    layerMoveAlpha(3, 0, 120)\n    wait(120)\n"
```

`layers/overlays/boot-handoff.toml`：

```toml
target  = "snr_common.lua"
profile = "test"
why     = """引导交接改指测试脚本。全文 8 处 run(snr_mainmenu)，只有 main() 末尾
那一处是引导交接，其余 7 处是暂停菜单的返回——换错了从暂停菜单回主菜单也会掉进
测试脚本。故 count=8 钉住结构、occurrence=-1 只改最后一处。"""

[[ops]]
op         = "replace"
count      = 8
occurrence = -1
find       = 'run(cGetFileName("script", "snr_mainmenu"))'
with       = 'run(cGetFileName("script", "snr_test"))'
```

- [ ] **Step 3: 写清单与 id 登记**

`layers/manifest.toml` 照 spec §6.1 全文写出，`overlays.order = ["fonts", "encore-menu", "strip-ipl", "boot-handoff"]`。

`layers/vms_ids.toml`：

```toml
# 账本占 1..17220（data/ledger.jsonl 派生）；卡消息 id 由引擎按 18000 + 卡号动态生成，
# 卡 1..195 → 18001..18195。编外层只能用这两段之外的号。
[[ranges]]
owner    = "scripts/snr_finale.lua"
vms      = [[17300, 17481]]
card_msg = [[18201, 18207]]
```

- [ ] **Step 4: 移脚本、还原基座**

```bash
mkdir -p layers/scripts
git mv docs/finale/snr_finale.lua layers/scripts/snr_finale.lua
uv run python - <<'PY'
import sys; sys.path.insert(0, '.')
from pathlib import Path
from tools.migrate_base import add_tr_line_markers
base = Path.home() / "pyluadec-refactor" / "corpus" / "final"
for name in ("snr_common.lua", "snr_mainmenu.lua"):
    text, n = add_tr_line_markers(Path(name).stem, (base / name).read_text(encoding="utf-8"))
    (Path("lua_scripts") / name).write_text(text, encoding="utf-8")
    print(f"还原 {name}（tr_line {n} 条）")
PY
```

- [ ] **Step 5: 给 luac_norm 加可调用接口**

在 `tools/luac_norm.py` 里把 `main()` 的比对循环抽成函数，`main()` 改为调用它：

```python
def compare_dirs(a: Path, b: Path) -> tuple[int, int, int, list[str]]:
    """逐同名 .lua 归一化后比对，返回 (相同, 不同, 解析失败, 有问题的文件名)。"""
    same = diff = err = 0
    bad: list[str] = []
    for pa in sorted(Path(a).glob("*.lua")):
        pb = Path(b) / pa.name
        if not pb.exists():
            continue
        try:
            if normalize(pa.read_bytes()) == normalize(pb.read_bytes()):
                same += 1
            else:
                diff += 1
                bad.append(pa.name)
        except Exception as exc:  # noqa: BLE001
            err += 1
            bad.append(f"{pa.name}: {exc}")
    return same, diff, err, bad
```

- [ ] **Step 6: 给 migrate_base 去掉字体重放、加 --check**

删掉 `main()` 里 `if f.name == "snr_common.lua": … text.replace(*FONT_PATCH)` 三行，
把 `FONT_PATCH` 常量替换为一行注释说明「已迁到 layers/overlays/fonts.toml」。加：

```python
    ap.add_argument("--check", action="store_true",
                    help="只断言 lua_scripts == 语料 + tr_line 标记，不落盘")
```

```python
    if args.check:
        bad = []
        for f in src_files:
            text, _ = add_tr_line_markers(f.stem, f.read_text(encoding="utf-8"))
            if text != (DEST / f.name).read_text(encoding="utf-8"):
                bad.append(f.name)
        if bad:
            sys.exit(f"[migrate] 基座不纯净，{len(bad)} 个文件与「语料 + tr_line」不符：{bad[:5]}\n"
                     f"  本地化改动应当是 layers/ 下的层，不该直接改 lua_scripts/")
        print(f"[migrate] 基座纯净 ✓（{len(src_files)} 文件 == 语料 + tr_line 标记）")
        return
```

- [ ] **Step 7: 给 layers.py 加最终源装配与 CLI**

追加到 `tools/layers.py`：

```python
def build_final_sources(profile: str = "release", switches: dict | None = None,
                        root: Path = LAYERS, injected: dict[str, str] | None = None
                        ) -> tuple[dict[str, str], list[dict], list[str]]:
    """装配某剖面的最终 lua 源。

    injected: 文件名 → 注入译文后的源。缺省时**读基座原文**（只验层用，不产盘）。
    返回 (文件名→最终源, 施加的层, 新增成员名)。
    """
    manifest = load_manifest(root)
    base = REPO / manifest["base"]["dir"]
    sources = dict(injected) if injected else {
        p.name: p.read_text(encoding="utf-8") for p in sorted(base.glob("*.lua"))}
    applied = overlays_for(manifest, root, profile, switches or {})
    for ov in applied:
        target = ov["target"]
        if target not in sources:
            raise OverlayError(f"叠加层 {ov['_name']} 的 target={target} 不在基座里")
        sources[target] = apply_overlay(sources[target], ov)
    added = []
    for spec in manifest["scripts"]:
        if spec.get("profile", "release") == "test" and profile != "test":
            continue
        name = Path(spec["member"]).name
        sources[name] = (root / spec["file"]).read_text(encoding="utf-8")
        added.append(spec["member"])
    return sources, applied, added
```

CLI（文件末尾）：

```python
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="校验清单与全部层（不产盘）")
    c.add_argument("--profile", default="release", choices=PROFILES)
    c.add_argument("--compare-compiled", metavar="DIR",
                   help="把最终源编译后与该目录逐字节比对（迁移期的硬闸）")
    d = sub.add_parser("diff", help="打印某层施加前后的 unified diff")
    d.add_argument("name")
    sub.add_parser("ids", help="只跑 id 登记检查")
    args = ap.parse_args(argv)

    from tools.pipelib import read_jsonl
    manifest = load_manifest()
    ledger_ids = {r["id"] for r in read_jsonl(REPO / manifest["base"]["ledger"])}

    if args.cmd == "ids":
        check_ids(manifest, LAYERS, ledger_ids)
        print("[layers] id 登记检查通过 ✓")
        return 0
    if args.cmd == "diff":
        import difflib
        ov = load_overlay(LAYERS / "overlays" / f"{args.name}.toml")
        before = (REPO / manifest["base"]["dir"] / ov["target"]).read_text(encoding="utf-8")
        after = apply_overlay(before, ov)
        sys.stdout.writelines(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True),
            fromfile=f"base/{ov['target']}", tofile=f"{args.name}/{ov['target']}"))
        return 0

    check_ids(manifest, LAYERS, ledger_ids)
    sources, applied, added = build_final_sources(args.profile)
    print(f"[layers] {args.profile}: 施加 {len(applied)} 层"
          f"（{', '.join(o['_name'] for o in applied)}），新增成员 {len(added)}")
    if args.compare_compiled:
        return _compare_compiled(sources, Path(args.compare_compiled), manifest)
    print("[layers] 全部层命中 ✓")
    return 0


def _compare_compiled(sources: dict[str, str], ref_dir: Path, manifest: dict) -> int:
    """把最终源编译一遍与参照目录逐字节比对。迁移期证明「层精确复现了手工改动」。"""
    import tempfile
    luac = Path(manifest["compiler"]["luac"]).expanduser()
    if not luac.exists():
        print(f"[layers] 跳过比对：缺 {luac}")
        return 0
    bad = []
    with tempfile.TemporaryDirectory() as td:
        for name, text in sorted(sources.items()):
            src = Path(td) / name
            src.write_text(text, encoding="utf-8")
            out = Path(td) / (name + ".luac")
            proc = subprocess.run([str(luac), "-s", "-o", str(out), str(src)],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                bad.append(f"{name} 编译失败: {proc.stderr.strip()}")
                continue
            ref = ref_dir / name
            if not ref.exists():
                bad.append(f"参照目录缺 {name}")
            elif ref.read_bytes() != out.read_bytes():
                bad.append(f"{name} 与参照不一致")
    for b in bad:
        print(f"[layers] ✗ {b}")
    print(f"[layers] 逐字节比对：{len(sources) - len(bad)}/{len(sources)} 相同")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: 写真语料测试与基座保真测试**

`tests/test_layers_corpus.py`：

```python
"""真语料测试：全部 release 层在真实基座上精确命中。

夹具证明不了「锚点还在」——只能对真语料跑。这是新增文本以后的日常守门员。
"""
import pytest

from tools.layers import (LAYERS, build_final_sources, check_ids, collect_ids,
                          load_manifest, load_overlay, overlays_for, REPO)
from tools.pipelib import read_jsonl


@pytest.fixture(scope="module")
def manifest():
    return load_manifest()


@pytest.fixture(scope="module")
def ledger_ids(manifest):
    return {r["id"] for r in read_jsonl(REPO / manifest["base"]["ledger"])}


def test_every_release_overlay_hits_on_real_base(manifest):
    sources, applied, _ = build_final_sources("release")
    assert [o["_name"] for o in applied] == ["fonts", "encore-menu"]
    assert sources["snr_common.lua"].count('pgf/LXGWWenKai-Regular.pgf') == 1
    assert "layerKeyCur" in sources["snr_mainmenu.lua"]


def test_every_test_overlay_hits_on_real_base(manifest):
    sources, applied, _ = build_final_sources("test")
    assert [o["_name"] for o in applied] == [
        "fonts", "encore-menu", "strip-ipl", "boot-handoff"]
    assert 'run(cGetFileName("script", "snr_test"))' in sources["snr_common.lua"]
    assert "layerMoveAlpha(0, 100, 120)" not in sources["snr_common.lua"]


def test_fast_boot_switch_off_keeps_ipl():
    sources, applied, _ = build_final_sources("test", switches={"fast-boot": False})
    assert "strip-ipl" not in [o["_name"] for o in applied]
    assert "layerMoveAlpha(0, 100, 120)" in sources["snr_common.lua"]


def test_id_registry_agrees_with_real_ledger(manifest, ledger_ids):
    check_ids(manifest, LAYERS, ledger_ids)


def test_finale_ids_are_inside_declared_range():
    text = (LAYERS / "scripts" / "snr_finale.lua").read_text(encoding="utf-8")
    ids = collect_ids(text)
    assert ids, "snr_finale.lua 里一条 vms 都没扫到——正则或文件出了问题"
    assert min(ids) >= 17300 and max(ids) <= 17481


def test_overlay_targets_all_exist_in_base(manifest):
    base = REPO / manifest["base"]["dir"]
    for name in manifest["overlays"]["order"]:
        ov = load_overlay(LAYERS / "overlays" / f"{name}.toml")
        assert (base / ov["target"]).exists(), f"{name} 的 target 不在基座里"
```

`tests/test_base_fidelity.py`：

```python
"""local_assets：基座保真与全量编译。缺 luac_sz4 或原包解包镜像即整体 skip。"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tools.layers import LAYERS, REPO, build_final_sources, load_manifest
from tools.luac_norm import compare_dirs

LUAC = Path("~/pyluadec-refactor/build/luac_sz4").expanduser()
CORPUS = Path("~/pyluadec-refactor/corpus/final").expanduser()
DATABIN_SCRIPT = REPO / "build" / "databin" / "script"

pytestmark = [
    pytest.mark.local_assets,
    pytest.mark.skipif(not LUAC.exists(), reason=f"缺 {LUAC}"),
    pytest.mark.skipif(not DATABIN_SCRIPT.is_dir(),
                       reason="缺 build/databin（先 databin.py unpack）"),
]


def _compile_all(sources: dict[str, str], out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    bad = []
    for name, text in sorted(sources.items()):
        src = out / ("_" + name)
        src.write_text(text, encoding="utf-8")
        dst = out / name
        proc = subprocess.run([str(LUAC), "-s", "-o", str(dst), str(src)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            bad.append(f"{name}: {proc.stderr.strip()}")
        elif dst.read_bytes()[:12] != bytes.fromhex("1b4c75615100010404040800"):
            bad.append(f"{name}: 头非 PSP ABI")
        src.unlink()
    return bad


def test_base_is_byte_identical_to_original_bytecode():
    """基座重编译、行号归零后必须与原包字节码逐字节相同——229/229。"""
    with tempfile.TemporaryDirectory() as td:
        base = {p.name: p.read_text(encoding="utf-8")
                for p in sorted((REPO / "lua_scripts").glob("*.lua"))}
        bad = _compile_all(base, Path(td))
        assert not bad, f"基座有文件编译失败：{bad[:3]}"
        same, diff, err, names = compare_dirs(Path(td), DATABIN_SCRIPT)
        assert (diff, err) == (0, 0), f"基座不再与原字节码等价：{names[:5]}"
        assert same == 229, f"只比对了 {same} 个文件"


def test_migrate_base_check_passes():
    if not CORPUS.is_dir():
        pytest.skip(f"缺 {CORPUS}")
    r = subprocess.run([sys.executable, "tools/migrate_base.py", "--check"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_release_final_sources_all_compile():
    sources, _, added = build_final_sources("release")
    assert "snr_finale.lua" in sources
    with tempfile.TemporaryDirectory() as td:
        bad = _compile_all(sources, Path(td))
    assert not bad, f"最终源编译失败：{bad[:3]}"
```

`pyproject.toml` 的 `markers` 追加一行：

```toml
    "local_assets: 依赖本机资产（luac_sz4 / build/databin），缺则自动 skip",
```

- [ ] **Step 9: 跑硬闸——新链路必须逐字节复现今日产物**

```bash
uv run python tools/layers.py check --profile release
uv run python tools/layers.py check --profile release --compare-compiled /tmp/layers_baseline/script
```

Expected: `逐字节比对：230/230 相同`，退出码 0。

不相同就用 `uv run python tools/layers.py diff encore-menu` 与
`git show 653b0ad -- lua_scripts/snr_mainmenu.lua` 对照，修层文件直到全等。
**这是本任务唯一的验收判据，不许放宽。**

- [ ] **Step 10: 跑全套测试**

```bash
uv run pytest tests/test_layers.py tests/test_layers_corpus.py tests/test_base_fidelity.py -q
uv run python tools/build_ledger.py --check      # 期望 OK：账本不受基座还原影响
python3 tools/extract_dag.py | diff -q - analysis/dag_all.txt
python3 tools/extract_crd.py | diff -q - analysis/crd_summary.txt
uv run pytest -q -m "not emu"
```

Expected: 全绿；账本 `check: OK`；两个 diff 无输出。

- [ ] **Step 11: 提交（单个 commit）**

```bash
git add lua_scripts/snr_common.lua lua_scripts/snr_mainmenu.lua \
        layers/ tools/layers.py tools/luac_norm.py tools/migrate_base.py \
        tests/test_layers_corpus.py tests/test_base_fidelity.py pyproject.toml
git add -A docs/finale/ layers/scripts/snr_finale.lua
git commit -m "refactor: 基座纯净化——lua_scripts 回到与原字节码等价，改动全部成层

lua_scripts/ 现在 == corpus/final + tr_line 标记，逐字节；luac_norm 行号归零后与原包
字节码 229/229 相同，并由 tests/test_base_fidelity.py 钉住。此前散在三处的本地化改动
收进 layers/：槽 0 字体行（原 migrate_base 重放）与槽 1（原 inject_lua 改写）合并为
fonts.toml；主菜单谢幕直达项 7 个操作成 encore-menu.toml；测试期的剥 IPL 与引导交接
成 strip-ipl/boot-handoff.toml；snr_finale.lua 自 docs/finale 移入 layers/scripts/。

硬闸：新链路装配的最终源编译后与迁移前的 build/stage/script 逐字节 230/230 相同
——证明层精确复现了手工改动，不是近似。账本与 analysis/ 三件套零漂移。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

