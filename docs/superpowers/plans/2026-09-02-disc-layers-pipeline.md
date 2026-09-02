# 中文盘构建管线规范化（基座 + 层 + 剖面）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `lua_scripts/` 还原成与原始游戏字节码等价的只读基座，令一切本地化改动成为在 `layers/` 里声明的「层」，并让 release / test 两个剖面各自构建出独立、可追溯、结构上不可能串味的盘。

**Architecture:** 构建分三段——译文注入（按账本 `(file, line)` 就地替换，行号不变）→ 叠加层（对基座文件做锚定文本操作，因而必须在注入之后）→ 编外脚本与资源。所有层在 `layers/manifest.toml` 声明，新工具 `tools/layers.py` 负责加载、校验、施加与取证，`tools/build_disc.py` 退化为纯编排器。

**Tech Stack:** Python ≥3.12（uv 管理）、tomllib（标准库）、Pillow、fontTools、pytest；外部二进制 `~/pyluadec-refactor/build/luac_sz4`（PSP ABI luac）与 `/tmp/pgftool/ttf_pgf`（PGF 生成）。

**Spec:** `docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`

## Global Constraints

- **原始资产只读**：`lua_scripts/`、`png/` 不就地修改（本计划 Task 4 是唯一例外，且方向是「还原成纯净基座」）。一切产物落 `build/`（已 gitignore）。
- **`vms()` 消息编号绝不改动**；文本内 `_n` `_r` `<漢字,かな>` `≪≫` `≦≧` `【】` `○` `■` 控制码原样保留。
- **基座定义**：`lua_scripts/` == `~/pyluadec-refactor/corpus/final/` + `tools/migrate_base.add_tr_line_markers()`，逐字节。判据是 `tools/luac_norm.py` 行号归零后与 `build/databin/script/` 逐字节相同，目标 **229/229**。
- **叠加层锚点只准是代码文本**，不准是可译文本，不准是行号。
- **一切正确性问题硬失败**（`SystemExit`，消息含可执行的下一步）；只有 gim 量化损耗保留为警告。
- **编译器**：`luac_sz4 -s`，产物头必须是 `1b4c75615100010404040800`。路径经 `SNDL_LUAC` 覆盖。
- **封包成员表严格按名升序**，新成员一律 `bisect` 插入，写盘前断言有序（引擎按名二分查找，失序即字体/资源加载失败）。
- **commit 规范**：`type: 中文摘要`，type ∈ feat / fix / docs / data / analysis / chore / refactor。工具代码与翻译数据分开提交。
- **测试哲学**：缺环境就 skip，绝不 fail，绝不默默换料。新标记 `local_assets` 用于依赖 `luac_sz4` / `build/databin` 的测试。
- **分支**：全部工作在 `feat/finale-stage` 上完成。

---

## 文件结构

**新建**

| 路径 | 职责 |
|---|---|
| `tools/layers.py` | 层系统全部逻辑：清单加载与校验、叠加操作引擎、id 检查、字集抽取、provenance、CLI |
| `layers/manifest.toml` | 唯一清单：基座/车道/编译器路径、叠加层顺序、编外脚本、gim 面表、字体成员 |
| `layers/vms_ids.toml` | 编外 vms / 卡消息 id 区段登记 |
| `layers/overlays/fonts.toml` | snr_common 两行 fontLoad（release） |
| `layers/overlays/encore-menu.toml` | snr_mainmenu 谢幕直达项（release） |
| `layers/overlays/strip-ipl.toml` | 剥 IPL 开场演出（test，switch=fast-boot） |
| `layers/overlays/boot-handoff.toml` | 引导交接改指 snr_test（test） |
| `layers/scripts/snr_finale.lua` | 谢幕章演出脚本（自 `docs/finale/` git mv） |
| `tests/test_layers.py` | 叠加引擎、清单、id、字集、provenance 的封闭单元测试 |
| `tests/test_layers_corpus.py` | 真语料测试：全部 release 层在真实注入文本上精确命中 |
| `tests/test_inject_lua.py` | 注入核心的封闭测试（今日缺失） |
| `tests/test_build_disc.py` | 成员树、缓存、发布断言的封闭测试（迷你 databin 夹具） |
| `tests/test_testboot.py` | testboot 生成器产物的封闭测试 |
| `tests/test_base_fidelity.py` | `local_assets`：基座保真 229/229、release 脚本全编译 |
| `docs/ops/disc-pipeline.md` | 唯一现行管线说明（不带日期） |

**修改**

| 路径 | 改动 |
|---|---|
| `tools/inject_lua.py` | 抽出 `inject_tree()`；删字体改写、车道写死、编译步骤 |
| `tools/build_disc.py` | `--profile`；阶段改名；成员树重建；gim 缓存；发布断言；provenance |
| `tools/make_test_boot.py` → `tools/testboot.py` | 改为层生成器 |
| `tools/build_font.py` | `build(charset_path, out_dir)`；删车道依赖 |
| `tools/migrate_base.py` | 删 `FONT_PATCH` 重放；加 `--check` |
| `tools/luac_norm.py` | 加 `compare_dirs()` |
| `lua_scripts/snr_common.lua`、`lua_scripts/snr_mainmenu.lua` | 还原成纯净基座 |
| `pyproject.toml` | 加 `fonttools` 依赖、`local_assets` 标记 |
| `CLAUDE.md` | 改写管线相关段落 |

---

## Task 1: 叠加操作引擎

**Files:**
- Create: `tools/layers.py`
- Test: `tests/test_layers.py`

**Interfaces:**
- Produces:
  - `class OverlayError(SystemExit)`
  - `apply_op(text: str, op: dict) -> str` — 施加单个操作，失败抛 `OverlayError`
  - `apply_overlay(text: str, overlay: dict) -> str` — 按 `overlay["ops"]` 顺序施加
  - `find_all(text: str, needle: str) -> list[int]` — 自左向右非重叠查找，返回起点列表
  - `select_indices(hits: list[int], count: int, occurrence) -> list[int]`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_layers.py`：

```python
"""叠加操作引擎的封闭单元测试。

这些测试不碰真实语料，只验引擎语义：五种操作、count/occurrence 的每种失败
路径、多行逐字匹配与缩进保真。真语料上的命中由 tests/test_layers_corpus.py 守。
"""
import pytest

from tools.layers import OverlayError, apply_op, apply_overlay, find_all, select_indices


def test_find_all_is_non_overlapping():
    assert find_all("aaaa", "aa") == [0, 2]


def test_replace_single_hit():
    out = apply_op("x = key3[i]\n", {"op": "replace", "find": "key3", "with": "keyCur"})
    assert out == "x = keyCur[i]\n"


def test_replace_count_mismatch_is_hard_failure():
    with pytest.raises(OverlayError) as e:
        apply_op("a a a\n", {"op": "replace", "count": 2, "find": "a", "with": "b"})
    assert "命中 3" in str(e.value)


def test_replace_zero_hit_is_hard_failure():
    with pytest.raises(OverlayError) as e:
        apply_op("hello\n", {"op": "replace", "find": "nope", "with": "x"})
    assert "命中 0" in str(e.value)


def test_replace_all_occurrences_by_default():
    out = apply_op("a a a\n", {"op": "replace", "count": 3, "find": "a", "with": "b"})
    assert out == "b b b\n"


def test_occurrence_negative_selects_from_end():
    out = apply_op("a a a\n",
                   {"op": "replace", "count": 3, "occurrence": -1, "find": "a", "with": "Z"})
    assert out == "a a Z\n"


def test_occurrence_out_of_range_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("a a\n", {"op": "replace", "count": 2, "occurrence": 3, "find": "a", "with": "b"})


def test_insert_before_keeps_indentation_verbatim():
    text = "        else\n            l0_1 = 1\n"
    out = apply_op(text, {"op": "insert_before",
                          "anchor": "        else\n",
                          "text": "        elseif cond then\n            body()\n"})
    assert out == ("        elseif cond then\n            body()\n"
                   "        else\n            l0_1 = 1\n")


def test_insert_after_places_text_after_anchor():
    out = apply_op("line1\nline2\n",
                   {"op": "insert_after", "anchor": "line1\n", "text": "mid\n"})
    assert out == "line1\nmid\nline2\n"


def test_delete_span_removes_start_through_end_inclusive():
    text = "keep\nSTART\nmiddle\nEND\ntail\n"
    out = apply_op(text, {"op": "delete_span", "start": "START\n", "end": "END\n"})
    assert out == "keep\ntail\n"


def test_replace_span_substitutes_region():
    text = "keep\nSTART\nmiddle\nEND\ntail\n"
    out = apply_op(text, {"op": "replace_span",
                          "start": "START\n", "end": "END\n", "with": "NEW\n"})
    assert out == "keep\nNEW\ntail\n"


def test_span_end_before_start_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("END\nSTART\n", {"op": "delete_span", "start": "START\n", "end": "END\n"})


def test_span_anchor_must_hit_exactly_once():
    with pytest.raises(OverlayError):
        apply_op("START\nx\nSTART\nEND\n",
                 {"op": "delete_span", "start": "START\n", "end": "END\n"})


def test_unknown_op_is_hard_failure():
    with pytest.raises(OverlayError):
        apply_op("x\n", {"op": "frobnicate", "find": "x", "with": "y"})


def test_ops_apply_in_order_and_see_previous_results():
    overlay = {"ops": [{"op": "replace", "find": "A", "with": "B"},
                       {"op": "replace", "find": "B", "with": "C"}]}
    assert apply_overlay("A\n", overlay) == "C\n"
```

- [ ] **Step 2: 跑测试确认全红**

Run: `uv run pytest tests/test_layers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.layers'`

- [ ] **Step 3: 写最小实现**

创建 `tools/layers.py`：

```python
#!/usr/bin/env -S uv run python
"""层系统：基座 + 层 + 剖面的加载、校验、施加与取证。

设计见 docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md。

核心约束：叠加层在**译文注入之后**施加（账本按 (file, line) 锚定，注入必须先跑
且行号不变），故锚点只准是代码文本，不准是可译文本，不准是行号。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class OverlayError(SystemExit):
    """叠加层施加失败。继承 SystemExit：正确性问题一律硬失败，不给静默机会。"""


def find_all(text: str, needle: str) -> list[int]:
    """自左向右非重叠查找，返回全部起点。"""
    if not needle:
        raise OverlayError("锚点为空串——叠加层写错了")
    hits, i = [], 0
    while (j := text.find(needle, i)) >= 0:
        hits.append(j)
        i = j + len(needle)
    return hits


def select_indices(hits: list[int], count: int, occurrence) -> list[int]:
    """按 count 断言总命中数，按 occurrence 选出要作用的那几处。"""
    # count=0 必须挡住：否则「锚点根本不存在」与「期望零命中」在数值上一样，
    # 施加就成了静默 no-op——而 count 存在的全部理由正是抓这种漂移。
    if count < 1:
        raise OverlayError(f"count 必须 ≥1，收到 {count}——零命中的层等于没写")
    if len(hits) != count:
        raise OverlayError(
            f"锚点期望命中 {count} 处，实际命中 {len(hits)} 处——"
            f"基座变了或叠加层写错了。用 `uv run python tools/layers.py diff <层名>` 核对")
    if occurrence == "all":
        return hits
    if not isinstance(occurrence, int) or occurrence == 0:
        raise OverlayError(f"occurrence 必须是 \"all\" 或非零整数，收到 {occurrence!r}")
    idx = occurrence - 1 if occurrence > 0 else count + occurrence
    if not 0 <= idx < count:
        raise OverlayError(f"occurrence={occurrence} 越界（命中 {count} 处）")
    return [hits[idx]]


def _need(op: dict, *keys: str) -> tuple:
    missing = [k for k in keys if k not in op]
    if missing:
        raise OverlayError(f"操作 {op.get('op')!r} 缺字段 {missing}")
    return tuple(op[k] for k in keys)


def _apply_point_op(text: str, op: dict, anchor: str, render) -> str:
    """replace / insert_before / insert_after 共用：定位 → 选点 → 自后向前改写。"""
    picks = select_indices(find_all(text, anchor), op.get("count", 1),
                           op.get("occurrence", "all"))
    for start in reversed(picks):        # 自后向前，前面的下标不受影响
        end = start + len(anchor)
        text = text[:start] + render(text[start:end]) + text[end:]
    return text


def _apply_span_op(text: str, op: dict, replacement: str) -> str:
    start_s, end_s = _need(op, "start", "end")
    if "count" in op or "occurrence" in op:
        raise OverlayError("span 类操作不接受 count / occurrence——两个锚各须恰好命中一次")
    starts, ends = find_all(text, start_s), find_all(text, end_s)
    if len(starts) != 1:
        raise OverlayError(f"start 锚点须恰好命中 1 次，实际 {len(starts)} 次")
    if len(ends) != 1:
        raise OverlayError(f"end 锚点须恰好命中 1 次，实际 {len(ends)} 次")
    if ends[0] < starts[0]:
        raise OverlayError("end 锚点在 start 之前——区间无效")
    return text[:starts[0]] + replacement + text[ends[0] + len(end_s):]


def apply_op(text: str, op: dict) -> str:
    """施加单个操作。五种：replace / insert_before / insert_after / delete_span / replace_span。"""
    kind = op.get("op")
    if kind == "replace":
        find, with_ = _need(op, "find", "with")
        return _apply_point_op(text, op, find, lambda _: with_)
    if kind == "insert_before":
        anchor, ins = _need(op, "anchor", "text")
        return _apply_point_op(text, op, anchor, lambda hit: ins + hit)
    if kind == "insert_after":
        anchor, ins = _need(op, "anchor", "text")
        return _apply_point_op(text, op, anchor, lambda hit: hit + ins)
    if kind == "delete_span":
        return _apply_span_op(text, op, "")
    if kind == "replace_span":
        (with_,) = _need(op, "with")
        return _apply_span_op(text, op, with_)
    raise OverlayError(f"未知操作 {kind!r}（可选 replace / insert_before / insert_after / "
                       f"delete_span / replace_span）")


def apply_overlay(text: str, overlay: dict) -> str:
    """按声明顺序依次施加全部操作；每个操作看到的都是前序操作之后的文本。"""
    for i, op in enumerate(overlay.get("ops", []), 1):
        try:
            text = apply_op(text, op)
        except OverlayError as exc:
            name = overlay.get("_name", "?")
            raise OverlayError(f"叠加层 {name} 第 {i} 个操作失败：{exc}") from None
    return text
```

- [ ] **Step 4: 跑测试确认全绿**

Run: `uv run pytest tests/test_layers.py -q`
Expected: PASS（16 passed——15 个上面列出的，加 `count < 1` 的守卫测试）

- [ ] **Step 5: 提交**

```bash
git add tools/layers.py tests/test_layers.py
git commit -m "feat: 叠加操作引擎——五种锚定文本操作 + count/occurrence 硬断言

层系统的第一块：apply_op 支持 replace / insert_before / insert_after /
delete_span / replace_span，count 断言全文命中总数、occurrence 选作用点（支持负数
自末尾计）。任一不符即 OverlayError（继承 SystemExit）——基座变了就当场炸，
不给静默偏移的机会。逐字匹配、零空白归一化，多行锚点因此按行对齐。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

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

## Task 3: 字集抽取与 provenance

**Files:**
- Modify: `tools/layers.py`
- Modify: `tests/test_layers.py`

**Interfaces:**
- Consumes: Task 2 的 `load_manifest`
- Produces:
  - `charset_of(sources: list[str], ledger_jp: list[str], always: list[int]) -> list[int]` — 排序去重的码位表
  - `write_charset(codes: list[int], path: Path) -> None` — 每行四位小写十六进制
  - `provenance(profile, manifest, root, applied, scripts_added, members, outputs) -> dict`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_layers.py`：

```python
from tools.layers import charset_of, provenance, write_charset


def test_charset_takes_non_ascii_from_string_literals_only():
    src = 'vms(1, "NONVOICE", "谢幕")\n-- 注释里的字不算：飨\nlocal x = 1\n'
    codes = charset_of([src], ledger_jp=[], always=[])
    assert ord("谢") in codes and ord("幕") in codes
    assert ord("飨") not in codes


def test_charset_handles_escaped_quotes_inside_literal():
    codes = charset_of([r'vms(1, "NONVOICE", "他说\"好\"的字：甲")' + "\n"],
                       ledger_jp=[], always=[])
    assert ord("甲") in codes


def test_charset_includes_ledger_jp_and_always():
    codes = charset_of([], ledger_jp=["彩野"], always=[ord("★")])
    assert ord("彩") in codes and ord("★") in codes


def test_charset_filters_to_bmp_printable():
    codes = charset_of(['vms(1, "X", "a\U0001F600b")' + "\n"], ledger_jp=[], always=[])
    assert 0x1F600 not in codes           # PGF charmap 只到 BMP
    assert all(0x20 <= c <= 0xFFFF for c in codes)


def test_charset_is_sorted_and_unique():
    codes = charset_of(['vms(1, "X", "乙甲甲")' + "\n"], ledger_jp=[], always=[])
    assert codes == sorted(set(codes))


def test_write_charset_format_matches_ttf_pgf_expectation(tmp_path):
    p = tmp_path / "ucs.txt"
    write_charset([0x20, 0x4E00], p)
    assert p.read_text() == "0020\n4e00\n"


def test_provenance_has_required_top_level_keys(tmp_path):
    root = _mk_layers(tmp_path)
    man = load_manifest(root)
    prov = provenance("release", man, root, applied=[], scripts_added=[],
                      members={"replaced": 1, "added": 2}, outputs={})
    assert set(prov) >= {"profile", "built_at", "git", "inputs", "tools",
                         "layers_applied", "scripts_added", "members", "outputs"}
    assert prov["members"] == {"replaced": 1, "added": 2}
```

- [ ] **Step 2: 跑测试确认全红**

Run: `uv run pytest tests/test_layers.py -q -k "charset or provenance"`
Expected: FAIL — `ImportError: cannot import name 'charset_of'`

- [ ] **Step 3: 写实现**

追加到 `tools/layers.py`：

```python
import hashlib
import json
import subprocess
from datetime import datetime, timezone

#: lua 双引号字面串。`[^"\\\n]|\\.` 让转义引号留在串内，换行则终止——注释里的字不算。
_LUA_STR_RE = _re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def charset_of(sources: list[str], ledger_jp: list[str], always: list[int]) -> list[int]:
    """字集 = 最终源的字面串 ∪ 账本 jp ∪ 常驻表，过滤到 BMP 可见区。

    保留账本 jp 是「宁滥勿缺」：未译面仍要渲染日文，且这样今日字集恒为新字集的
    子集，字体只会变大不会漏字。
    """
    chars: set[int] = set(always)
    for src in sources:
        for lit in _LUA_STR_RE.findall(src):
            chars.update(ord(c) for c in lit)
    for jp in ledger_jp:
        chars.update(ord(c) for c in jp)
    return sorted(c for c in chars if 0x20 <= c <= 0xFFFF)


def write_charset(codes: list[int], path: Path) -> None:
    """写 ttf_pgf 要的码位表：一行一个四位小写十六进制。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{c:04x}\n" for c in codes), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:                     # noqa: BLE001 — 取证失败不该阻断构建
        return ""


def provenance(profile: str, manifest: dict, root: Path, applied: list[dict],
               scripts_added: list[str], members: dict, outputs: dict) -> dict:
    """构建取证：输入与工具的哈希、git 状态、本次施加的层。"""
    lane = REPO / manifest["lane"]["dir"]
    inputs = {}
    for rel in ("forward.jsonl", "patches.jsonl", "forward_extra.jsonl"):
        inputs[str((lane / rel).relative_to(REPO))] = _sha256(lane / rel)
    for key in ("ledger", "ledger_extra"):
        p = REPO / manifest["base"][key]
        inputs[manifest["base"][key]] = _sha256(p)
    for p in sorted(root.rglob("*")):
        if p.is_file():
            inputs[str(p.relative_to(REPO))] = _sha256(p)
    luac = Path(manifest["compiler"]["luac"]).expanduser()
    return {
        "profile": profile,
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "git": {"head": _git("rev-parse", "HEAD"),
                "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": [l[3:] for l in _git("status", "--short").splitlines()]},
        "inputs": inputs,
        "tools": {"luac_sz4": _sha256(luac),
                  "ttf_pgf": _sha256(Path("/tmp/pgftool/ttf_pgf"))},
        "layers_applied": [{"overlay": o["_name"], "target": o["target"],
                            "ops": len(o["ops"])} for o in applied],
        "scripts_added": scripts_added,
        "members": members,
        "outputs": outputs,
    }


def write_provenance(prov: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: 跑测试确认全绿**

Run: `uv run pytest tests/test_layers.py -q`
Expected: PASS（约 35 passed）

- [ ] **Step 5: 提交**

```bash
git add tools/layers.py tests/test_layers.py
git commit -m "feat: 字集抽取与构建取证

charset_of 从最终源的 lua 字面串（含转义、排除注释）∪ 账本 jp ∪ 常驻表算码位，
过滤到 BMP——保留账本 jp 是宁滥勿缺，今日字集恒为新字集子集，字体只会变大不漏字。
provenance 记 git 状态、车道与账本与 layers/ 逐文件 sha256、luac_sz4 与 ttf_pgf 哈希、
本次施加的层。2026-09-02 的缺字事故正是因为没人知道字体是拿哪份译文烤的。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

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

## Task 5: inject_lua 瘦身与补测试

**Files:**
- Modify: `tools/inject_lua.py`
- Create: `tests/test_inject_lua.py`

**Interfaces:**
- Consumes: 无
- Produces: `inject_tree(base_dir: Path, ledger_rows: list[dict], zh: dict[int, str], extra: dict[str, str]) -> tuple[dict[str, str], dict]` — 返回 `(文件名→注入后源, 统计)`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_inject_lua.py`：

```python
"""注入核心的封闭测试。今日为零——而这是整条译文管线的心脏。"""
import pytest

from tools.inject_lua import inject_text, lua_quote, merge_adjacent_ruby


def _rows(*specs):
    return {line: {"id": i, "literal": lit} for line, i, lit in specs}


def test_line_count_never_changes():
    src = 'a()\nvms(1, "NONVOICE", "あ")\nb()\n'
    out = inject_text("f", src, _rows((2, 1, True)), {1: "啊"}, {}, _stats())
    assert len(out.splitlines()) == len(src.splitlines())
    assert out.splitlines()[1].strip() == 'vms(1, "NONVOICE", "啊")'


def _stats():
    return dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0,
                font_slot1=0, ruby_merged=0)


def test_id_mismatch_between_source_and_ledger_is_hard_failure():
    src = 'vms(7, "NONVOICE", "あ")\n'
    with pytest.raises(SystemExit) as e:
        inject_text("f", src, _rows((1, 1, True)), {1: "啊"}, {}, _stats())
    assert "不同步" in str(e.value)


def test_missing_translation_leaves_source_untouched():
    src = 'vms(1, "NONVOICE", "あ")\n'
    st = _stats()
    out = inject_text("f", src, _rows((1, 1, True)), {}, {}, st)
    assert out == src and st["vms_missing"] == 1


def test_non_literal_row_substitutes_whole_expression():
    src = 'vms(1, "NONVOICE", "■デバッグ：" .. msg)\n'
    out = inject_text("f", src, _rows((1, 1, False)), {1: '"■调试：" .. msg'}, {}, _stats())
    assert out.strip() == 'vms(1, "NONVOICE", "■调试：" .. msg)'


def test_tr_line_comment_is_preserved():
    src = 'plotTitle[1] = "あ" -- tr_line:1\n'
    out = inject_text("f", src, {}, {}, {"plotTitle:1": "啊"}, _stats())
    assert out.strip() == 'plotTitle[1] = "啊" -- tr_line:1'


def test_lua_quote_escapes_backslash_and_quote():
    assert lua_quote(r'a"b\c') == r'"a\"b\\c"'


def test_merge_adjacent_ruby_joins_touching_groups():
    out, n = merge_adjacent_ruby("<胡,hú><萝,luó><卜,bo>")
    assert out == "<胡萝卜,húluóbo>" and n == 2


def test_merge_adjacent_ruby_leaves_separated_groups_alone():
    out, n = merge_adjacent_ruby("<哐,kuāng>当<哐,kuāng>当")
    assert n == 0 and out == "<哐,kuāng>当<哐,kuāng>当"
```

- [ ] **Step 2: 跑测试确认表现**

Run: `uv run pytest tests/test_inject_lua.py -q`
Expected: 大部分 PASS（这些函数已存在），若有 FAIL 说明现有实现与预期不符，先查明再改测试或改实现。

- [ ] **Step 3: 抽出 inject_tree，删掉字体改写与编译**

在 `tools/inject_lua.py` 里：删除 `FONT_SLOT1_FROM` / `FONT_SLOT1_TO` 两个常量、`main()` 里的
`if stem == "snr_common" and FONT_SLOT1_FROM in text:` 三行（改由 `layers/overlays/fonts.toml` 承担）、
`compile_bytecode()` 函数、`LANE` / `OUT_SRC` / `OUT_BC` / `LUAC` / `PSP_LUAC_HEADER` 常量。新增：

```python
def inject_tree(base_dir: Path, ledger_rows: list[dict], zh: dict[int, str],
                extra: dict[str, str]) -> tuple[dict[str, str], dict]:
    """注入整棵基座，返回 (文件名→注入后源, 统计)。行数与行号严格不变。

    ⚠ 不做字体改写、不编译、不写盘——那些分别是 layers/overlays/fonts.toml 与
    build_disc 的职责。本函数是纯函数，好测。
    """
    by_file: dict[str, dict[int, dict]] = {}
    for row in ledger_rows:
        by_file.setdefault(row["file"], {})[row["line"]] = row
    stats = dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0,
                 ruby_merged=0)
    out: dict[str, str] = {}
    for f in sorted(Path(base_dir).glob("*.lua")):
        out[f.name] = inject_text(f.stem, f.read_text(encoding="utf-8"),
                                  by_file.get(f.stem, {}), zh, extra, stats)
    return out, stats
```

`main()` 改为调用 `inject_tree` 并把结果写到 `--out` 指定目录（缺省
`build/release/lua/injected`），保留 `--only` 调试参数，去掉 `--no-compile`。

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/test_inject_lua.py -q
uv run python tools/inject_lua.py --out /tmp/inj_check
```

Expected: 测试全绿；注入报告 `vms 替换 16749（缺译 0，账本外 0）；extra 替换 875`。

- [ ] **Step 5: 提交**

```bash
git add tools/inject_lua.py tests/test_inject_lua.py
git commit -m "refactor: inject_lua 收缩为纯注入——字体改写与编译各归其位

抽出 inject_tree()（纯函数：基座 + 账本 + 译文 → 文件名到源的字典），删掉槽 1 字体
改写（迁 layers/overlays/fonts.toml）、luac 编译（迁 build_disc）、车道路径写死
（迁 manifest.toml）。补上今日缺失的注入核心测试：行数不变、id 不符硬失败、
literal=false 整表达式替换、tr_line 注释保真、ruby 合并两种情形。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Task 6: build_font 改造与 fonttools 依赖

**Files:**
- Modify: `tools/build_font.py`, `pyproject.toml`
- Modify: `tests/test_layers.py`

**Interfaces:**
- Consumes: Task 3 的 `write_charset`
- Produces: `build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]`

- [ ] **Step 1: 加依赖并确认可导入**

```bash
uv add fonttools
uv run python -c "import fontTools; print('fontTools', fontTools.version)"
```

Expected: 打印版本号。2026-09-02 实测 venv 里没有它，`widen_latin()` 当场 ImportError——
此前靠什么环境跑通没有记录。

- [ ] **Step 2: 写失败测试**

追加到 `tests/test_layers.py`：

```python
def test_build_font_reads_charset_file_not_lane(tmp_path, monkeypatch):
    """build() 的字集必须来自参数指定的文件——车道依赖已经拆掉了。"""
    import tools.build_font as bf
    ucs = tmp_path / "ucs.txt"
    ucs.write_text("0020\n4e00\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(bf, "TTF_PGF", tmp_path / "fake_ttf_pgf")
    (tmp_path / "fake_ttf_pgf").write_text("#!/bin/sh\ntouch \"$2\"\n", encoding="utf-8")
    (tmp_path / "fake_ttf_pgf").chmod(0o755)
    monkeypatch.setattr(bf, "widen_latin", lambda ttf, out: (calls.append(out), ttf)[1])
    out = bf.build(ucs, tmp_path / "out", sizes=(17,))
    assert out and out[0].name == "lxgw17.pgf"
    assert not hasattr(bf, "corpus_chars"), "corpus_chars 应当已删除（字集改由 layers 算）"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_layers.py -q -k build_font`
Expected: FAIL — `AttributeError: module 'tools.build_font' has no attribute 'build'`

- [ ] **Step 4: 实现**

在 `tools/build_font.py` 里删除 `corpus_chars()` 与 `LANE` 常量及对 `resolve_map` / `read_jsonl`
的 import（`ALWAYS` 保留，供 `tools/layers.py` 引用）。把 `main()` 的循环体抽成：

```python
def build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]:
    """按给定字集文件产 PGF。字集由 tools/layers.py 从 release 最终源算出。

    ⚠ 不再自己算字集：2026-09-02 的缺字事故就是因为它只看车道与账本，
    编外的谢幕章源不在视野里，6 个字进了盘却没有字形。
    """
    if not TTF_PGF.exists():
        sys.exit(f"缺 ttf_pgf: {TTF_PGF}（见 docs/ops/pgf-font-research-2026-08-31.md 重建；"
                 f"或设 SNDL_TTF_PGF）")
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for size in sizes:
        ttf = TTF_BY_SIZE.get(size, TTF_DEFAULT)
        if not ttf.exists():
            sys.exit(f"缺字体源: {ttf}")
        if size in WIDEN_SIZES:
            ttf = widen_latin(ttf, out_dir / f"_widened{size:02d}.ttf")
        render = ruby_size if (size in WIDEN_SIZES and ruby_size) else size
        out = out_dir / f"lxgw{size:02d}.pgf"
        proc = subprocess.run([str(TTF_PGF), str(ttf), str(out), str(charset_path),
                               str(render)], capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            sys.exit(f"ttf_pgf 失败({size}px): {proc.stdout[-500:]} {proc.stderr[-500:]}")
        print(f"[font] {size}px(渲染 {render}px) <- {ttf.name} -> {out} "
              f"({out.stat().st_size:,} B)")
        made.append(out)
    return made
```

`main()` 改为：解析 `--charset`（缺省 `build/release/charset.txt`）、`--out`、`--sizes`、
`--ruby-size`，调 `build()`。

- [ ] **Step 5: 跑测试与真实构建**

```bash
uv run pytest tests/test_layers.py -q -k build_font
uv run python tools/build_font.py --charset build/font/ucs.txt --out /tmp/font_check --sizes 17
cmp /tmp/font_check/lxgw17.pgf build/font/lxgw17.pgf && echo "与现役字体逐字节相同 ✓"
```

Expected: 测试 PASS；`cmp` 无输出并打印那句话——证明改造没有改变产物。

- [ ] **Step 6: 提交**

```bash
git add tools/build_font.py tests/test_layers.py pyproject.toml uv.lock
git commit -m "refactor: build_font 改为按给定字集构建 + fonttools 入依赖

删掉 corpus_chars()——它只看车道与账本，编外的谢幕章源不在视野里，这正是 2026-09-02
六个字进了盘却没字形的根因。字集改由 tools/layers.py 从 release 最终源算，build()
只管拿字集产 PGF。同时把 fonttools 补进 pyproject：venv 里一直没有它，widen_latin()
当场 ImportError，此前靠什么环境跑通没有记录。
改造后用现役字集重编，产物与现役 lxgw17.pgf 逐字节相同。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

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
