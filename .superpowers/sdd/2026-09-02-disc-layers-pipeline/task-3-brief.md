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

