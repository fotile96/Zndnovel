# P1a 数据地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成翻译流水线的数据层地基：原文账本（ledger）、译文合并（resolve）、批次校验（check_batch）、正向线入库（append_forward），全部带测试并在真实语料上验证。

**Architecture:** 全部工具是无状态 CLI 脚本（`tools/*.py`，共享 `tools/pipelib.py`），围绕 append-only JSONL 文件工作（spec §2）。check_batch → pass 标记 → append_forward 构成入库握手。本计划不含线性化/上下文组装（P1b 另立计划）。

**Tech Stack:** Python 3.14（uv 管理），仅标准库；测试用 pytest（dev 依赖）。

## Global Constraints

- 运行方式：`uv run python tools/<script>.py`；测试 `uv run pytest`（Python 3.14，见 `.python-version`）。
- `data/ledger.jsonl`、`data/forward.jsonl`、`data/patches.jsonl` 为 append-only：任何工具不得重写/重排既有行（生成类文件 `data/final.jsonl`、`data/ledger_extra.jsonl` 可整体重建）。
- JSONL 序列化统一走 `pipelib.dumps`（`ensure_ascii=False`、紧凑分隔符、不排序键）；同输入必须字节级同输出（双跑 diff 为空）。
- `lua_scripts/`、`png/` 只读（CLAUDE.md 规约）。
- commit 规范：`type: 中文摘要`，type ∈ feat/fix/docs/data/analysis/chore/refactor；在 main 直接提交（轻量分支制，本计划无高危操作）。
- 期望总量断言：全仓库 vms 静态调用（带数字 ID）恰 **16750** 条，ID 全局唯一（`snr_common.lua` 的 `oCard.show` 内 `vms(v1,…)` 动态调用不入账本）。
- schema 以 spec §2.1 为准；本计划新增 `literal` 字段（bool，第三参数是否纯字符串字面量）为 schema 超集。

## 接口总表（P1b 将消费）

- `pipelib.REPO/DATA/WORK`（Path）；`dumps(obj)->str`；`read_jsonl(p)->list[dict]`；`append_jsonl(p,rows)`；`write_jsonl(p,rows)`；`sha256_file(p)->str`；`display_width(s)->int`
- ledger 行：`{"id":int,"jp":str,"voice":str,"file":str,"func":str,"chapter":str,"kind":"narrative"|"ambient","literal":bool}`
- ledger_extra 行：`{"key":str,"jp":str,"kind":"plot_title"|"scene_title"|"savedata"|"card_msg","file":str}`
- forward 行：`{"id":int,"zh":str,"batch":int,"backend":str,"model":str,"ctx":str,"glossary_v":int,"ts":str}`
- patches 行：`{"id":int,"zh":str,"reason":str,"glossary_v":int,"ts":str}`
- 入库握手：`work/out/batch_<N>.draft.jsonl`（行 `{"id":int,"zh":str}`）+ `work/ctx/batch_<N>/source.jsonl`（行=ledger 行子集）→ `check_batch` 通过后写 `work/out/batch_<N>.pass.json`（`{"sha256":…}`）→ `append_forward` 校验后入线。

---

### Task 1: 测试脚手架与 pipelib

**Files:**
- Modify: `pyproject.toml`（加 dev 依赖与 pytest 配置）
- Create: `tools/pipelib.py`
- Test: `tests/test_pipelib.py`

**Interfaces:**
- Produces: `pipelib.REPO`、`DATA`、`WORK`、`dumps`、`read_jsonl`、`append_jsonl`、`write_jsonl`、`sha256_file`、`display_width`（签名见接口总表；后续所有任务 import 使用）

- [ ] **Step 1: 安装 pytest 并配置**

```bash
uv add --dev pytest
```

在 `pyproject.toml` 末尾追加：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write the failing test**

创建 `tests/test_pipelib.py`：

```python
import json
from pathlib import Path
from tools.pipelib import dumps, read_jsonl, append_jsonl, write_jsonl, display_width, sha256_file, REPO

def test_dumps_keeps_unicode_and_is_compact():
    assert dumps({"jp": "彩野さん", "n": 1}) == '{"jp":"彩野さん","n":1}'

def test_jsonl_roundtrip_and_append(tmp_path):
    p = tmp_path / "a.jsonl"
    write_jsonl(p, [{"id": 1}, {"id": 2}])
    append_jsonl(p, [{"id": 3}])
    assert [r["id"] for r in read_jsonl(p)] == [1, 2, 3]

def test_display_width_east_asian():
    assert display_width("あa") == 3
    assert display_width("【彩野】「うん」") == 16

def test_sha256_file(tmp_path):
    p = tmp_path / "x.bin"; p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

def test_repo_points_at_project_root():
    assert (REPO / "lua_scripts").is_dir()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pipelib.py -v`
Expected: FAIL（ModuleNotFoundError: tools.pipelib）

- [ ] **Step 4: Write minimal implementation**

创建 `tools/pipelib.py`：

```python
"""翻译流水线共享底座：路径、JSONL 读写、显示宽度。全部标准库。"""
from pathlib import Path
import hashlib
import json
import unicodedata

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
WORK = REPO / "work"


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(dumps(r) + "\n")


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(dumps(r) + "\n")


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "FWA" else 1 for c in s)
```

另创建空文件 `tools/__init__.py` 与 `tests/__init__.py`（使 `tools.pipelib` 可 import）。

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_pipelib.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock tools/pipelib.py tools/__init__.py tests/
git commit -m "feat: pipelib 共享底座与 pytest 脚手架"
```

---

### Task 2: build_ledger 解析核心（vms 行）

**Files:**
- Create: `tools/build_ledger.py`
- Test: `tests/test_build_ledger.py`

**Interfaces:**
- Consumes: `pipelib.dumps` 等（Task 1）
- Produces: `build_ledger.parse_vms_lines(stem: str, text: str) -> list[dict]`（返回 ledger 行，含 id/jp/voice/file/func/literal，**不含** chapter/kind——Task 3 补）；`FUNC_RE`、`VMS_RE` 常量

- [ ] **Step 1: Write the failing test**

创建 `tests/test_build_ledger.py`：

```python
from tools.build_ledger import parse_vms_lines

FIXTURE = '''\
scene_x1_10 = function(scene_id, scene_title)
    local v0
    vms(100, "NONVOICE", "○_n通学路。") -- tr_line:3
    vms(101, "AYA00180", "【アヤノ】「教室に来たよ」")
    v0 = function()
        vms(102, "NORECORD", "≪入手済みカード≫")
    end
    vms(103, "NONVOICE", "これにより、『" .. v7 .. "』を読む。")
end
'''

def test_parse_extracts_ids_voice_and_text():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert [r["id"] for r in rows] == [100, 101, 102, 103]
    assert rows[0]["jp"] == "○_n通学路。"          # tr_line 注释被剥除，引号去壳
    assert rows[1]["voice"] == "AYA00180"
    assert rows[1]["file"] == "snr_x_10_s"

def test_func_tracking_follows_nearest_function_opener():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert rows[0]["func"] == "scene_x1_10"
    assert rows[2]["func"] == "v0"               # 嵌套闭包归最近的 opener

def test_literal_flag_false_for_concatenation():
    rows = parse_vms_lines("snr_x_10_s", FIXTURE)
    assert rows[0]["literal"] is True
    assert rows[3]["literal"] is False
    assert '.. v7 ..' in rows[3]["jp"]           # 非字面量保留原始表达式
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_ledger.py -v`
Expected: FAIL（ModuleNotFoundError: tools.build_ledger）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/build_ledger.py`：

```python
"""把 lua_scripts 解析为 data/ledger.jsonl（原文账本）与 data/ledger_extra.jsonl。"""
import re

FUNC_RE = re.compile(r'^\s*([A-Za-z_][\w.]*)\s*=\s*function')
VMS_RE = re.compile(r'vms\((\d+), "([A-Z0-9]+)", (.+)\)$')
TR_LINE_RE = re.compile(r'\s*--\s*tr_line:\d+\s*$')


def parse_vms_lines(stem: str, text: str) -> list[dict]:
    rows = []
    func = ""
    for line in text.splitlines():
        m = FUNC_RE.match(line)
        if m:
            func = m.group(1)
            continue
        s = TR_LINE_RE.sub("", line.strip())
        m = VMS_RE.search(s)
        if not m:
            continue
        arg = m.group(3).strip()
        literal = arg.startswith('"') and arg.endswith('"') and '" ..' not in arg and '.. "' not in arg
        jp = arg[1:-1] if literal else arg
        rows.append({
            "id": int(m.group(1)), "jp": jp, "voice": m.group(2),
            "file": stem, "func": func, "literal": literal,
        })
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_ledger.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/build_ledger.py tests/test_build_ledger.py
git commit -m "feat: ledger 解析核心（vms 行提取与函数归属）"
```

---

### Task 3: 章别推导与 ambient 分类

**Files:**
- Create: `tools/ambient_rules.py`
- Modify: `tools/build_ledger.py`（追加 `classify`）
- Test: `tests/test_build_ledger.py`（追加用例）

**Interfaces:**
- Produces: `ambient_rules.SYS_FILES: frozenset[str]`、`ambient_rules.AMBIENT_FUNC_EXCEPTIONS: dict[str, str]`（"file:func"→理由，人工审定后填）；`build_ledger.chapter_of(stem: str) -> str`；`build_ledger.classify(row: dict) -> dict`（补 chapter/kind 后返回同一 dict）

- [ ] **Step 1: Write the failing test**

在 `tests/test_build_ledger.py` 追加：

```python
from tools.build_ledger import chapter_of, classify

def test_chapter_of_section_files():
    assert chapter_of("snr_s1_10_s") == "s1s"
    assert chapter_of("snr_s3_10_fa") == "s3fa"
    assert chapter_of("snr_s0_10_f") == "s0f"
    assert chapter_of("snr_e2_10_f") == "e2f"
    assert chapter_of("snr_crd_42") == "crd"
    assert chapter_of("snr_common") == "sys"

def test_classify_kind_by_file():
    sysrow = classify({"file": "snr_common", "func": "vms"})
    assert (sysrow["chapter"], sysrow["kind"]) == ("sys", "ambient")
    story = classify({"file": "snr_s1_10_s", "func": "scene_s1s_20"})
    assert (story["chapter"], story["kind"]) == ("s1s", "narrative")
    card = classify({"file": "snr_crd_2", "func": "card_2_s1s_20_intro"})
    assert (card["chapter"], card["kind"]) == ("crd", "narrative")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_ledger.py -v`
Expected: 新增 2 条 FAIL（ImportError: chapter_of）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/ambient_rules.py`：

```python
"""ambient 分类规则表。人工审定的例外写进 AMBIENT_FUNC_EXCEPTIONS（Task 9 检查点）。"""
SYS_FILES = frozenset({
    "config", "snr_lib", "snr_common", "snr_mainmenu", "snr_story_main",
    "snr_fragment_main", "snr_memory", "snr_novel", "snr_music", "snr_graphic",
})
# "file:func" -> 判定理由；narrative 文件中被人工认定为 ambient 的函数写在这里
AMBIENT_FUNC_EXCEPTIONS: dict[str, str] = {}
```

在 `tools/build_ledger.py` 追加：

```python
from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS

CHAPTER_RE = re.compile(r'^snr_([se]\d)_10_(s|f[abc]?)$')


def chapter_of(stem: str) -> str:
    m = CHAPTER_RE.match(stem)
    if m:
        return m.group(1) + m.group(2)
    if stem.startswith("snr_crd_"):
        return "crd"
    return "sys"


def classify(row: dict) -> dict:
    row["chapter"] = chapter_of(row["file"])
    key = f'{row["file"]}:{row["func"]}'
    if row["file"] in SYS_FILES or row["chapter"] == "sys" or key in AMBIENT_FUNC_EXCEPTIONS:
        row["kind"] = "ambient"
    else:
        row["kind"] = "narrative"
    return row
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_ledger.py -v`
Expected: 全部 passed

- [ ] **Step 5: Commit**

```bash
git add tools/ambient_rules.py tools/build_ledger.py tests/test_build_ledger.py
git commit -m "feat: 章别推导与 ambient 规则表分类"
```

---

### Task 4: ledger_extra 提取（plotTitle/场景标题/savedataTitle/oCard.show）

**Files:**
- Modify: `tools/build_ledger.py`（追加 `parse_extra`）
- Test: `tests/test_build_ledger.py`（追加用例）

**Interfaces:**
- Produces: `build_ledger.parse_extra(stem: str, text: str) -> list[dict]`（返回 ledger_extra 行，key 规则：plotTitle→`plotTitle:<N>`；其余→`<stem>:<行号>`，savedataTitle 两参→`:<行号>:1/:2`）

- [ ] **Step 1: Write the failing test**

在 `tests/test_build_ledger.py` 追加：

```python
from tools.build_ledger import parse_extra

EXTRA_FIXTURE = '''\
plotTitle[1] = "ある子が学校にくる物語"
scene_s1s_20(doScriptScene, "夏の朝、高校までの通学路") -- tr_line:2
savedataTitle("オープニング", "フラグメント")
oCard.show(cGetFileName("card", "crd_1_a"), "書きとめました：『ある子』")
'''

def test_parse_extra_four_kinds():
    rows = parse_extra("snr_test", EXTRA_FIXTURE)
    kinds = {r["kind"] for r in rows}
    assert kinds == {"plot_title", "scene_title", "savedata", "card_msg"}
    byk = {r["kind"]: r for r in rows if r["kind"] != "savedata"}
    assert byk["plot_title"]["key"] == "plotTitle:1"
    assert byk["scene_title"]["jp"] == "夏の朝、高校までの通学路"
    savedata = [r for r in rows if r["kind"] == "savedata"]
    assert [r["jp"] for r in savedata] == ["オープニング", "フラグメント"]
    assert savedata[0]["key"].endswith(":1") and savedata[1]["key"].endswith(":2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_ledger.py::test_parse_extra_four_kinds -v`
Expected: FAIL（ImportError: parse_extra）

- [ ] **Step 3: Write minimal implementation**

在 `tools/build_ledger.py` 追加：

```python
PLOT_TITLE_RE = re.compile(r'^plotTitle\[(\d+)\] = "(.*)"')
SCENE_TITLE_RE = re.compile(r'scene_[\w]+\((?:doScriptScene|p0), "([^"]*)"')
SAVEDATA_RE = re.compile(r'savedataTitle\("([^"]*)", "([^"]*)"\)')
CARD_MSG_RE = re.compile(r'oCard\.show\([^,]+, "([^"]+)"\)')


def parse_extra(stem: str, text: str) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = TR_LINE_RE.sub("", raw.strip())
        if m := PLOT_TITLE_RE.match(line):
            rows.append({"key": f"plotTitle:{m.group(1)}", "jp": m.group(2),
                         "kind": "plot_title", "file": stem})
        elif m := SAVEDATA_RE.search(line):
            for i in (1, 2):
                rows.append({"key": f"{stem}:{lineno}:{i}", "jp": m.group(i),
                             "kind": "savedata", "file": stem})
        elif m := CARD_MSG_RE.search(line):
            rows.append({"key": f"{stem}:{lineno}", "jp": m.group(1),
                         "kind": "card_msg", "file": stem})
        elif m := SCENE_TITLE_RE.search(line):
            rows.append({"key": f"{stem}:{lineno}", "jp": m.group(1),
                         "kind": "scene_title", "file": stem})
    return rows
```

（注意 elif 顺序：savedata/card_msg 先于 scene_title，避免同一行被误吸。）

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_ledger.py -v`
Expected: 全部 passed

- [ ] **Step 5: Commit**

```bash
git add tools/build_ledger.py tests/test_build_ledger.py
git commit -m "feat: ledger_extra 四类结构文本提取"
```

---

### Task 5: build_ledger CLI 与真实语料整合

**Files:**
- Modify: `tools/build_ledger.py`（追加 `main`）
- Test: `tests/test_build_ledger.py`（追加真实语料整合用例）
- Create: `data/ledger.jsonl`、`data/ledger_extra.jsonl`（运行产物，入库）

**Interfaces:**
- Produces: CLI `uv run python tools/build_ledger.py`（写 data/ 两文件并打印统计；`--check` 模式与既有文件比对，不一致则退出码 1——供回归验证）

- [ ] **Step 1: Write the failing test**

在 `tests/test_build_ledger.py` 追加：

```python
import subprocess, sys
from tools.pipelib import REPO, read_jsonl

def test_real_repo_ledger_counts_and_uniqueness(tmp_path):
    out = subprocess.run(
        [sys.executable, "tools/build_ledger.py", "--out-dir", str(tmp_path)],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    rows = read_jsonl(tmp_path / "ledger.jsonl")
    assert len(rows) == 16750
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == 16750
    assert rows == sorted(rows, key=lambda r: r["id"])
    kinds = {r["kind"] for r in rows}
    assert kinds == {"narrative", "ambient"}
    extra = read_jsonl(tmp_path / "ledger_extra.jsonl")
    assert sum(1 for r in extra if r["kind"] == "plot_title") == 195

def test_double_run_is_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        subprocess.run([sys.executable, "tools/build_ledger.py", "--out-dir", str(d)],
                       cwd=REPO, check=True, capture_output=True)
    assert (a / "ledger.jsonl").read_bytes() == (b / "ledger.jsonl").read_bytes()
    assert (a / "ledger_extra.jsonl").read_bytes() == (b / "ledger_extra.jsonl").read_bytes()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_ledger.py::test_real_repo_ledger_counts_and_uniqueness -v`
Expected: FAIL（脚本无 main/--out-dir，returncode≠0）

- [ ] **Step 3: Write minimal implementation**

在 `tools/build_ledger.py` 追加：

```python
def build(script_dir):
    ledger, extra = [], []
    for path in sorted(script_dir.glob("*.lua")):
        text = path.read_text(encoding="utf-8")
        stem = path.stem
        ledger += [classify(r) for r in parse_vms_lines(stem, text)]
        extra += parse_extra(stem, text)
    ledger.sort(key=lambda r: r["id"])
    extra.sort(key=lambda r: (r["kind"], r["key"]))
    ids = [r["id"] for r in ledger]
    assert len(ids) == len(set(ids)), "vms ID 出现重复"
    return ledger, extra


def main(argv=None):
    import argparse
    from tools.pipelib import REPO, DATA, write_jsonl, read_jsonl
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(DATA))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    from pathlib import Path
    out = Path(args.out_dir)
    ledger, extra = build(REPO / "lua_scripts")
    if args.check:
        same = (read_jsonl(out / "ledger.jsonl") == ledger
                and read_jsonl(out / "ledger_extra.jsonl") == extra)
        print("check:", "OK" if same else "MISMATCH")
        return 0 if same else 1
    write_jsonl(out / "ledger.jsonl", ledger)
    write_jsonl(out / "ledger_extra.jsonl", extra)
    n_amb = sum(1 for r in ledger if r["kind"] == "ambient")
    print(f"ledger={len(ledger)} (ambient={n_amb})  extra={len(extra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

同时在文件顶部把 `from tools.ambient_rules import …` 改为兼容直跑：

```python
try:
    from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.ambient_rules import SYS_FILES, AMBIENT_FUNC_EXCEPTIONS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_ledger.py -v`
Expected: 全部 passed（如 16750 断言失败：先 `grep -oh 'vms([0-9]*' lua_scripts/*.lua | sort -u | wc -l` 复核真实数，查明差异原因后修正解析而非改断言）

- [ ] **Step 5: 生成正式账本并提交**

```bash
uv run python tools/build_ledger.py
uv run python tools/build_ledger.py --check
git add tools/build_ledger.py tests/test_build_ledger.py data/ledger.jsonl data/ledger_extra.jsonl
git commit -m "data: 生成 ledger 原文账本与 extra 结构文本"
```

---

### Task 6: resolve() 与 final.jsonl 物化

**Files:**
- Create: `tools/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: forward/patches 行 schema（接口总表）
- Produces: `resolve.resolve_map(forward_rows, patch_rows) -> dict[int, str]`；CLI `uv run python tools/resolve.py [--require-complete]` 读 data/forward.jsonl+patches.jsonl 写 data/final.jsonl（行 `{"id":int,"zh":str}`，按 id 升序），缺译行打印数量到 stderr；`--require-complete` 时有缺译则退出码 1

- [ ] **Step 1: Write the failing test**

创建 `tests/test_resolve.py`：

```python
from tools.resolve import resolve_map

FWD = [{"id": 1, "zh": "初译A"}, {"id": 2, "zh": "初译B"}, {"id": 1, "zh": "二遍A"}]
PATCH = [{"id": 2, "zh": "补丁B1"}, {"id": 2, "zh": "补丁B2"}]

def test_forward_last_wins():
    assert resolve_map(FWD, [])[1] == "二遍A"

def test_patch_overrides_forward_and_last_patch_wins():
    m = resolve_map(FWD, PATCH)
    assert m[2] == "补丁B2"
    assert m[1] == "二遍A"

def test_untranslated_absent():
    assert 99 not in resolve_map(FWD, PATCH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/resolve.py`：

```python
"""生效译文合并：resolve = 最新补丁 ∥ 正向线最后条。下游只准读本工具输出。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import DATA, read_jsonl, write_jsonl


def resolve_map(forward_rows, patch_rows) -> dict:
    m = {}
    for r in forward_rows:
        m[r["id"]] = r["zh"]
    for r in patch_rows:
        m[r["id"]] = r["zh"]
    return m


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-complete", action="store_true")
    args = ap.parse_args(argv)
    fwd = read_jsonl(DATA / "forward.jsonl") if (DATA / "forward.jsonl").exists() else []
    pat = read_jsonl(DATA / "patches.jsonl") if (DATA / "patches.jsonl").exists() else []
    m = resolve_map(fwd, pat)
    ledger_ids = [r["id"] for r in read_jsonl(DATA / "ledger.jsonl")]
    missing = [i for i in ledger_ids if i not in m]
    write_jsonl(DATA / "final.jsonl", [{"id": i, "zh": m[i]} for i in sorted(m)])
    print(f"final={len(m)}  missing={len(missing)}", file=sys.stderr)
    return 1 if (args.require_complete and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/resolve.py tests/test_resolve.py
git commit -m "feat: resolve 生效译文合并与 final 物化"
```

---

### Task 7: check_batch 校验器

**Files:**
- Create: `tools/check_batch.py`
- Test: `tests/test_check_batch.py`

**Interfaces:**
- Consumes: `work/ctx/batch_<N>/source.jsonl`（ledger 行子集）、`work/out/batch_<N>.draft.jsonl`（`{"id","zh"}`）、可选 `glossary/speakers.json`（`{"日文名":"中文名"}`）与 `glossary/active.json`（`{"日文词":"中文定译"}`）
- Produces: `check_batch.check(source_rows, draft_rows, speakers, glossary) -> dict`（`{"hard":[…],"warn":[…]}`，元素为 `{"id":…,"rule":…,"msg":…}`）；CLI `uv run python tools/check_batch.py --batch N`：hard 为空 → 写 `work/out/batch_<N>.pass.json`（`{"sha256":draft 文件哈希}`）+ 报告 `work/out/batch_<N>.check.json`，退出 0；否则只写报告，退出 1

硬规则：R1 id 集合精确相等；R2a ruby `<x,y>` 良构（去除合法 ruby 后不得残留 `<`/`>`）；R2b 说话人：有 speakers 表时 `【源名】`→`【表[源名]】` 精确匹配，无表时退化为"源有【】⇔译有【】"；R2c 源中出现的 `≪ ≫ ≦ ≧ ○ ■` 每种在译文中至少出现一次。
软规则：W1 `_n`+`_r` 总数差 >2；W2 命中 glossary 词条的源行、译文缺对应定译；W3 显示宽度：按 `_n|_r` 切分后的最宽显示行 > 源最宽显示行×1.15（下限 10）。

- [ ] **Step 1: Write the failing test**

创建 `tests/test_check_batch.py`：

```python
from tools.check_batch import check

SRC = [
    {"id": 1, "jp": "【彩野】「うん、<前向性健忘,ぜんこうせいけんぼう>だよ」"},
    {"id": 2, "jp": "○_nそこには≪きみ≫がいた。_r間違いなく。"},
]
OK = [
    {"id": 1, "zh": "【彩野】「嗯，是<前向性健忘,顺行性遗忘>哦」"},
    {"id": 2, "zh": "○_n那里有≪你≫。_r毫无疑问。"},
]

def test_clean_draft_passes():
    r = check(SRC, OK, speakers={"彩野": "彩野"}, glossary={})
    assert r["hard"] == [] and r["warn"] == []

def test_id_set_mismatch_is_hard():
    r = check(SRC, OK[:1], speakers=None, glossary=None)
    assert any(v["rule"] == "R1" for v in r["hard"])

def test_broken_ruby_is_hard():
    bad = [dict(OK[0], zh="【彩野】「嗯，<前向性健忘顺行」"), OK[1]]
    r = check(SRC, bad, speakers=None, glossary=None)
    assert any(v["rule"] == "R2a" for v in r["hard"])

def test_speaker_map_mismatch_is_hard():
    bad = [dict(OK[0], zh="【绫乃】「嗯」<a,b>"), OK[1]]
    r = check(SRC, bad, speakers={"彩野": "彩野"}, glossary=None)
    assert any(v["rule"] == "R2b" for v in r["hard"])

def test_lost_marks_is_hard():
    bad = [OK[0], dict(OK[1], zh="○_n那里有你。_r毫无疑问。")]
    r = check(SRC, bad, speakers=None, glossary=None)
    assert any(v["rule"] == "R2c" for v in r["hard"])

def test_linebreak_diff_and_width_are_warn():
    bad = [OK[0], dict(OK[1], zh="○那里有≪你≫。毫无疑问。" + "长" * 40)]
    r = check(SRC, bad, speakers=None, glossary=None)
    rules = {v["rule"] for v in r["warn"]}
    assert "W1" in rules and "W3" in rules and r["hard"] == []

def test_glossary_miss_is_warn():
    r = check(SRC, OK, speakers=None, glossary={"前向性健忘": "顺行性健忘症"})
    assert any(v["rule"] == "W2" for v in r["warn"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_check_batch.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/check_batch.py`：

```python
"""批次校验：硬规则挡入库，软规则进报告。spec §7。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import WORK, read_jsonl, sha256_file, display_width, dumps

RUBY_RE = re.compile(r'<[^<>,]+,[^<>,]+>')
SPEAKER_RE = re.compile(r'^【([^】]+)】')
MARKS = "≪≫≦≧○■"
BREAK_RE = re.compile(r'_n|_r')


def _ruby_ok(s: str) -> bool:
    rest = RUBY_RE.sub("", s)
    return "<" not in rest and ">" not in rest


def _max_line_width(s: str) -> int:
    return max(display_width(seg) for seg in BREAK_RE.split(s)) if s else 0


def check(source_rows, draft_rows, speakers=None, glossary=None) -> dict:
    hard, warn = [], []
    src = {r["id"]: r for r in source_rows}
    drf = {r["id"]: r for r in draft_rows}
    if set(src) != set(drf) or len(draft_rows) != len(drf):
        hard.append({"id": 0, "rule": "R1",
                     "msg": f"id 集合不一致 src={len(src)} draft={len(drf)}"})
        return {"hard": hard, "warn": warn}
    for i, s in src.items():
        jp, zh = s["jp"], drf[i]["zh"]
        if not _ruby_ok(zh):
            hard.append({"id": i, "rule": "R2a", "msg": "ruby 不良构"})
        sm, dm = SPEAKER_RE.match(jp), SPEAKER_RE.match(zh)
        if speakers:
            if sm:
                want = speakers.get(sm.group(1))
                if want is not None and (not dm or dm.group(1) != want):
                    hard.append({"id": i, "rule": "R2b",
                                 "msg": f"说话人应为【{want}】"})
        elif bool(sm) != bool(dm):
            hard.append({"id": i, "rule": "R2b", "msg": "【】说话人结构不对齐"})
        for ch in MARKS:
            if ch in jp and ch not in zh:
                hard.append({"id": i, "rule": "R2c", "msg": f"丢失符号 {ch}"})
        if abs(len(BREAK_RE.findall(jp)) - len(BREAK_RE.findall(zh))) > 2:
            warn.append({"id": i, "rule": "W1", "msg": "_n/_r 数量差>2"})
        if glossary:
            for term, tr in glossary.items():
                if term in jp and tr not in zh:
                    warn.append({"id": i, "rule": "W2",
                                 "msg": f"「{term}」未按定译「{tr}」"})
        if _max_line_width(zh) > max(10, _max_line_width(jp) * 1.15):
            warn.append({"id": i, "rule": "W3", "msg": "显示行宽超限"})
    return {"hard": hard, "warn": warn}


def main(argv=None):
    import argparse, json
    from tools.pipelib import REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    args = ap.parse_args(argv)
    n = args.batch
    source = read_jsonl(WORK / "ctx" / f"batch_{n}" / "source.jsonl")
    draft_path = WORK / "out" / f"batch_{n}.draft.jsonl"
    draft = read_jsonl(draft_path)
    speakers = glossary = None
    sp, gl = REPO / "glossary" / "speakers.json", REPO / "glossary" / "active.json"
    if sp.exists():
        speakers = json.loads(sp.read_text(encoding="utf-8"))
    if gl.exists():
        glossary = json.loads(gl.read_text(encoding="utf-8"))
    result = check(source, draft, speakers, glossary)
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / f"batch_{n}.check.json").write_text(
        dumps(result), encoding="utf-8")
    if not result["hard"]:
        (WORK / "out" / f"batch_{n}.pass.json").write_text(
            dumps({"sha256": sha256_file(draft_path)}), encoding="utf-8")
        print(f"batch_{n}: PASS  warn={len(result['warn'])}")
        return 0
    print(f"batch_{n}: FAIL  hard={len(result['hard'])}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_check_batch.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add tools/check_batch.py tests/test_check_batch.py
git commit -m "feat: check_batch 硬软规则校验与 pass 标记"
```

---

### Task 8: append_forward 入库

**Files:**
- Create: `tools/append_forward.py`
- Test: `tests/test_append_forward.py`

**Interfaces:**
- Consumes: pass 标记握手（Task 7）、forward 行 schema
- Produces: CLI `uv run python tools/append_forward.py --batch N --backend cc --model <名> --ctx <sha> --glossary-v <int> [--ts <iso>] [--data-dir 覆盖]`；函数 `append_forward.run(batch, backend, model, ctx, glossary_v, ts=None, work=None, data=None) -> int`（0=成功；拒绝时 2=无 pass 标记、3=哈希不符、4=批次已入线）

- [ ] **Step 1: Write the failing test**

创建 `tests/test_append_forward.py`：

```python
import json
from pathlib import Path
from tools.append_forward import run
from tools.pipelib import write_jsonl, read_jsonl, sha256_file, dumps

def _setup(tmp_path, with_pass=True, good_hash=True):
    work, data = tmp_path / "work", tmp_path / "data"
    (work / "out").mkdir(parents=True)
    draft = work / "out" / "batch_7.draft.jsonl"
    write_jsonl(draft, [{"id": 100, "zh": "译A"}, {"id": 101, "zh": "译B"}])
    if with_pass:
        h = sha256_file(draft) if good_hash else "0" * 64
        (work / "out" / "batch_7.pass.json").write_text(dumps({"sha256": h}))
    return work, data

def test_appends_with_metadata(tmp_path):
    work, data = _setup(tmp_path)
    assert run(7, "cc", "claude-x", "sha:abc", 1, ts="2026-07-30T00:00:00Z",
               work=work, data=data) == 0
    rows = read_jsonl(data / "forward.jsonl")
    assert [r["id"] for r in rows] == [100, 101]
    assert rows[0]["backend"] == "cc" and rows[0]["glossary_v"] == 1

def test_refuses_without_pass_marker(tmp_path):
    work, data = _setup(tmp_path, with_pass=False)
    assert run(7, "cc", "m", "c", 1, work=work, data=data) == 2

def test_refuses_on_hash_mismatch(tmp_path):
    work, data = _setup(tmp_path, good_hash=False)
    assert run(7, "cc", "m", "c", 1, work=work, data=data) == 3

def test_refuses_duplicate_batch_and_keeps_file_intact(tmp_path):
    work, data = _setup(tmp_path)
    run(7, "cc", "m", "c", 1, ts="t", work=work, data=data)
    before = (data / "forward.jsonl").read_bytes()
    assert run(7, "cc", "m", "c", 1, ts="t", work=work, data=data) == 4
    assert (data / "forward.jsonl").read_bytes() == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_append_forward.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

创建 `tools/append_forward.py`：

```python
"""校验通过的批次草稿 → 追加 forward.jsonl（append-only 正向线）。"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import WORK, DATA, read_jsonl, append_jsonl, sha256_file


def run(batch, backend, model, ctx, glossary_v, ts=None, work=None, data=None) -> int:
    work, data = Path(work or WORK), Path(data or DATA)
    draft_path = work / "out" / f"batch_{batch}.draft.jsonl"
    pass_path = work / "out" / f"batch_{batch}.pass.json"
    if not pass_path.exists():
        print(f"batch_{batch}: 无 pass 标记，先跑 check_batch", file=sys.stderr)
        return 2
    marker = json.loads(pass_path.read_text(encoding="utf-8"))
    if marker["sha256"] != sha256_file(draft_path):
        print(f"batch_{batch}: draft 在校验后被改动（哈希不符）", file=sys.stderr)
        return 3
    fwd_path = data / "forward.jsonl"
    if fwd_path.exists() and any(
            r["batch"] == batch for r in read_jsonl(fwd_path)):
        print(f"batch_{batch}: 已在正向线，拒绝重复入库", file=sys.stderr)
        return 4
    ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [{"id": r["id"], "zh": r["zh"], "batch": batch, "backend": backend,
             "model": model, "ctx": ctx, "glossary_v": glossary_v, "ts": ts}
            for r in read_jsonl(draft_path)]
    append_jsonl(fwd_path, rows)
    print(f"batch_{batch}: +{len(rows)} 行入线")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--ctx", required=True)
    ap.add_argument("--glossary-v", type=int, required=True)
    ap.add_argument("--ts")
    args = ap.parse_args(argv)
    return run(args.batch, args.backend, args.model, args.ctx,
               args.glossary_v, ts=args.ts)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_append_forward.py -v`
Expected: 4 passed

- [ ] **Step 5: Run 全量回归**

Run: `uv run pytest -q`
Expected: 全部 passed

- [ ] **Step 6: Commit**

```bash
git add tools/append_forward.py tests/test_append_forward.py
git commit -m "feat: append_forward 入库握手（pass标记/哈希/防重）"
```

---

### Task 9: ambient 审定报告（用户检查点）

**Files:**
- Modify: `tools/build_ledger.py`（追加 `--report`）
- Modify: `tools/ambient_rules.py`（按用户裁决填例外，若有）

**Interfaces:**
- Produces: `uv run python tools/build_ledger.py --report` 在 stdout 打印 每文件×kind 行数 与 sys 文件内 vms 数最多的前 20 个函数（供人工判断是否有"该上时间轴却被划为 ambient"或反之的函数）

- [ ] **Step 1: 实现 --report**

在 `tools/build_ledger.py` 的 `main` 中追加分支（位置：`ledger, extra = build(…)` 之后、`if args.check:` 之前）：

```python
    ap.add_argument("--report", action="store_true")
    # … parse 后：
    if args.report:
        from collections import Counter
        by_file = Counter((r["file"], r["kind"]) for r in ledger)
        for (f, k), n in sorted(by_file.items()):
            print(f"{f:24s} {k:9s} {n}")
        top = Counter(f'{r["file"]}:{r["func"]}' for r in ledger
                      if r["kind"] == "ambient").most_common(20)
        print("\n-- ambient 函数 TOP20 --")
        for name, n in top:
            print(f"{n:5d}  {name}")
        return 0
```

- [ ] **Step 2: 跑报告并请用户审定**

Run: `uv run python tools/build_ledger.py --report`
将输出呈交用户，问题只有一个：「sys 文件之外是否有函数应划为 ambient？sys 文件内是否有文本其实该上时间轴（如 comSectionStoryEndAyanoTime 的 Time over 演出词）？」按裁决填写例外。若需要"sys 文件内某函数划回 narrative"，在 `tools/ambient_rules.py` 增加：

```python
NARRATIVE_FUNC_EXCEPTIONS: dict[str, str] = {}  # "file:func" -> 理由
```

并把 `classify` 的判定改为（narrative 例外优先级最高）：

```python
def classify(row: dict) -> dict:
    row["chapter"] = chapter_of(row["file"])
    key = f'{row["file"]}:{row["func"]}'
    if key in NARRATIVE_FUNC_EXCEPTIONS:
        row["kind"] = "narrative"
    elif row["file"] in SYS_FILES or row["chapter"] == "sys" or key in AMBIENT_FUNC_EXCEPTIONS:
        row["kind"] = "ambient"
    else:
        row["kind"] = "narrative"
    return row
```

同时在 `tests/test_build_ledger.py` 追加单测：

```python
def test_narrative_exception_wins(monkeypatch):
    import tools.build_ledger as bl
    monkeypatch.setattr("tools.build_ledger.NARRATIVE_FUNC_EXCEPTIONS",
                        {"snr_common:comSectionStoryEndAyanoTime": "时间轴事件"},
                        raising=False)
    row = bl.classify({"file": "snr_common", "func": "comSectionStoryEndAyanoTime"})
    assert row["kind"] == "narrative"
```

（注意：`classify` 需从模块属性读例外表以便 monkeypatch 生效，即引用 `NARRATIVE_FUNC_EXCEPTIONS` 时通过模块级名字而非局部快照。）

- [ ] **Step 3: 重建账本并回归**

```bash
uv run python tools/build_ledger.py
uv run pytest -q
```
Expected: 全部 passed（16750 总数不变，仅 kind 分布变化）

- [ ] **Step 4: Commit**

```bash
git add tools/ambient_rules.py tools/build_ledger.py data/ledger.jsonl
git commit -m "data: ambient 例外清单人工审定入账"
```

---

## 完成定义

- `uv run pytest -q` 全绿；`uv run python tools/build_ledger.py --check` 输出 OK。
- data/ 下 ledger 两件已入库；forward/patches 尚为空（P2 试点才产生）。
- 补丁写入工具（add_patch）与按 glossary_v 的召回查询、以及线性化器/gen_batches/build_context/gen_plan/prompts 模板，均属 **P1b 计划**——在本计划合入后基于真实 schema 编写（patches 的 schema 与 resolve 语义已在本计划锁定并测试）。
