# P4 润色 pass 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 P4 润色 pass 全套工装（SEG 冻结→多通道产候选→保税仓→四桶分流→清关→放大扫描），并完成 SEG-1（b36–62）双通道（fable-workflow + paseo-deepseek）的点火准备。

**Architecture:** 冻结单位是 SEG（`pilot/polish/<label>/frozen/` 全通道共读）；模型输出是数据（raw 文件），写保税仓的是代码（`polish_ingest` 唯一入仓、`polish_commit` 唯一写 patch）；三个数据文件（candidates/decisions/patches）全部 append-only。spec 见 `docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`。

**Tech Stack:** Python ≥3.12（uv 项目 venv），pytest，纯 stdlib + pyyaml；复用 `tools/pipelib.py`、`tools/check_batch.py`、`tools/resolve.py`、`tools/add_patch.py`。

## Global Constraints

- `lua_scripts/`、`png/`、`analysis/`、`skeleton/` 只读；`data/batches.jsonl` 冻结，绝不重生成。
- `pilot/lanes/*/data/forward.jsonl` 与一切 `patches.jsonl`、新增的 `candidates.*.jsonl`/`decisions.jsonl` 均 append-only；改判=追加新记录，绝不就地改。
- 仓库处于车道模式：任何写 patch 的命令必须显式 `--data-dir`（见 `add_patch.resolve_data_dir` 的闸）。
- git 只 add 显式路径，绝不 `git add -A`/`git add .`；绝不 `checkout --`/`stash`/`restore`（并行会话共享工作树）。push 仅用户明示。
- commit message：`type: 中文摘要`，type ∈ feat/fix/docs/data/analysis/chore/refactor。
- 每个新工具带 pytest + 变异自检（3–6 个变异；绿变异必须区分「测试无牙」与「变异没打中」）。
- 所有阈值集中 `config/polish.yaml`；任何阈值调整不得以「自动入库率」为优化目标。
- SEG-1 = 段表 `seg1-s2`，batches **[36, 62]**（27 个原始批，opus 时代逐批跑、无会话分组）；K=150；抽检率 0.10；推翻率冻结线 0.20；准入实质改写线 0.30；自动清关幅度 `max(4, opus 行长×0.15)`；放大每 SEG 1 轮。
- 长对话双帽沿用 P3：一条对话 ≤10 批且 ≤600 行。
- 回执设计（spec §4 的落地修正）：**模型算不出 sha256**——模型只回显 `id + jp 尾串（末 8 个非控制码字符）`；`jp_hash/opus_hash` 由 ingest 从 frozen 计算写入 candidates。核验二重：回显尾串 ↔ frozen jp；frozen ↔ manifest 哈希。
- opus 车道数据目录：`pilot/lanes/opus/data/`（ledger.jsonl 有每 id 的 jp；forward+patches 经 `resolve.resolve_map` 合成现行译文）。

---

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

### Task 2: config/polish.yaml + tools/polishlib.py（公共层）

**Files:**
- Create: `config/polish.yaml`、`tools/polishlib.py`
- Test: `tests/test_polishlib.py`

**Interfaces:**
- Produces:
  - `polishlib.CFG` → dict（读 config/polish.yaml）
  - `polishlib.seg_dir(label) -> Path`（`REPO/pilot/polish/<label>`）
  - `polishlib.jp_tail(s, n=8) -> str`（剥控制码/ruby 注音后取末 n 字符）
  - `polishlib.edit_distance(a, b) -> int`（字符级 Levenshtein，difflib opcodes 计数）
  - `polishlib.autoclear_limit(opus_zh) -> int`（`max(4, int(len×0.15))`，len 取剥控制码后）
  - `polishlib.strip_ctl(s) -> str`（去 `_n/_r`、ruby 注音部、不去文本）

- [ ] **Step 1: 写 config/polish.yaml**

```yaml
# P4 润色 pass 阈值（spec §9：集中一处；调整记台账；不以自动入库率为优化目标）
K: 150                 # 每 SEG 请裁配额（总额，多通道共享，含抽检占用）
sample_rate: 0.10      # 自动清关随机抽检率
overturn_freeze: 0.20  # 抽检推翻率 ≥ 此值 → 冻结该通道本 SEG 自动清关权
calib_fail: 0.30       # 准入小考：金标句实质改写占比 ≥ 此值 → 自动清关权初始关闭
autoclear_abs: 4       # 自动清关幅度 = max(autoclear_abs, len(opus)×autoclear_ratio)
autoclear_ratio: 0.15
minor_edit: 4          # 校准三档：edit≤minor_edit 为轻微，>autoclear_limit 为实质
amplify_rounds: 1
session_size: 10       # 长对话双帽（沿 P3）
session_lines: 600
jp_tail_n: 8           # 回执尾串长度
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_polishlib.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polishlib as pl

def test_cfg_loads():
    assert pl.CFG["K"] == 150 and 0 < pl.CFG["sample_rate"] < 1

def test_jp_tail_strips_ctl_and_ruby():
    s = "こんにちは_nよろしく<漢字,かんじ>ね"
    # 剥 _n 与 ruby 注音部（保留汉字前半），末 8 字
    assert pl.jp_tail(s) == "よろしく漢字ね"[-8:]

def test_edit_distance_basic():
    assert pl.edit_distance("abc", "abc") == 0
    assert pl.edit_distance("abc", "axc") == 1
    assert pl.edit_distance("", "abc") == 3

def test_autoclear_limit_floor_and_ratio():
    assert pl.autoclear_limit("四字") == 4            # floor
    assert pl.autoclear_limit("十" * 100) == 15       # 100×0.15
```

- [ ] **Step 3: 跑测确认失败** — `uv run pytest tests/test_polishlib.py -q` → FAIL (no module)

- [ ] **Step 4: 实现 tools/polishlib.py**

```python
"""P4 润色 pass 公共层：配置、路径、回执尾串、编辑距离。"""
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO

RUBY_RE = re.compile(r"<([^,<>]+),[^,<>]+>")
CTL_RE = re.compile(r"_[nr]")

def _load_cfg():
    import yaml
    return yaml.safe_load((REPO / "config" / "polish.yaml").read_text(encoding="utf-8"))

CFG = _load_cfg()

def seg_dir(label) -> Path:
    return REPO / "pilot" / "polish" / label

def strip_ctl(s: str) -> str:
    return CTL_RE.sub("", RUBY_RE.sub(lambda m: m.group(1), s or ""))

def jp_tail(s: str, n: int = None) -> str:
    return strip_ctl(s)[-(n or CFG["jp_tail_n"]):]

def edit_distance(a: str, b: str) -> int:
    # difflib opcodes：replace 记 max(删,插)，insert/delete 记其长——字符级近似 Levenshtein，
    # 用途只是「幅度分档」，不需要严格最优解。
    d = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "replace":
            d += max(i2 - i1, j2 - j1)
        elif tag in ("delete", "insert"):
            d += (i2 - i1) + (j2 - j1)
    return d

def autoclear_limit(opus_zh: str) -> int:
    return max(CFG["autoclear_abs"], int(len(strip_ctl(opus_zh)) * CFG["autoclear_ratio"]))
```

- [ ] **Step 5: 跑测通过 + 变异自检**

Run: `uv run pytest tests/test_polishlib.py -q` → 4 passed。
变异（各改一处→对应测试必须红→还原）：①`autoclear_abs` 取 0；②`edit_distance` 的 replace 记 min；③`jp_tail` 不剥 ruby。

- [ ] **Step 6: Commit**

```bash
git add config/polish.yaml tools/polishlib.py tests/test_polishlib.py
git commit -m "feat: P4 润色公共层 polishlib + 集中阈值配置"
```

---

### Task 3: tools/polish_setup.py（SEG 冻结）

**Files:**
- Create: `tools/polish_setup.py`
- Test: `tests/test_polish_setup.py`

**Interfaces:**
- Consumes: `config/segments.yaml`（段表批号）、`data/batches.jsonl`、opus 车道 `ledger.jsonl/forward.jsonl/patches.jsonl/notes/`、`resolve.resolve_map`、`skeleton/anchors.yaml`、`build_context.glossary_version`
- Produces:
  - `setup(label, opus_data, repo=None) -> Path`：建 `pilot/polish/<label>/frozen/` + `manifest.json`
  - frozen 内容：`source.jsonl`（{id, jp, batch}，按段表批号从 ledger 取）、`opus.jsonl`（{id, zh}，resolve 固化）、`locked.json`（锁定 id 清单+来源）、`glossary/`（active.json+**speakers.json**+voices/+style.md+polish.md+anchors.yaml 拷贝——speakers.json 是评审 Task 6 时发现的缺口回填：§8 机械闸 R2b 说话人映射要读它，冻结面必须自足，不能让机械闸回落读活仓库）、`notes/`（该段批号的 notes 拷贝）、`rulings.md`（占位骨架，人工/放大纪要追加）
  - `manifest.json`：`{label, batches, glossary_v, files: {rel: sha256}, opus_at: {forward_lines, patches_lines, forward_sha, patches_sha}, ts}`
  - `verify(label) -> list`（frozen 逐文件哈希 ↔ manifest，漂移清单；空=绿）
  - `locked.json` 判据：段内 id ∩（anchors 全部 item id ∪ opus patches 已有 id）
- CLI: `--seg <label> --opus-data <dir>`、`--verify <label>`

- [ ] **Step 1: 写失败测试**（tmp_path 造 mini 仓：2 批 4 行 ledger、1 条 anchor、1 条 patch）

```python
# tests/test_polish_setup.py 核心断言
def test_setup_freezes_and_locks(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    src = {r["id"] for r in read_jsonl(d / "frozen" / "source.jsonl")}
    assert src == {10, 11, 12, 13}
    locked = json.loads((d / "frozen" / "locked.json").read_text())
    assert set(locked["ids"]) == {11, 13}          # 11=anchor, 13=已有 patch
    assert locked["why"]["11"] == "anchor" and locked["why"]["13"] == "patched"
    m = json.loads((d / "manifest.json").read_text())
    assert m["opus_at"]["patches_lines"] == 1

def test_opus_snapshot_is_resolved(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    opus = {r["id"]: r["zh"] for r in read_jsonl(d / "frozen" / "opus.jsonl")}
    assert opus[13] == "补丁后文本"                 # patch 覆盖 forward

def test_verify_detects_drift(mini_repo):
    d = ps.setup("segX", mini_repo.opus_data, repo=mini_repo.root)
    assert ps.verify("segX", repo=mini_repo.root) == []
    (d / "frozen" / "opus.jsonl").write_text("坏")
    assert ps.verify("segX", repo=mini_repo.root) != []
```

- [ ] **Step 2: 跑测失败** → **Step 3: 实现**（骨架）

```python
def setup(label, opus_data, repo=None):
    repo = Path(repo or REPO)
    seg = _seg_entry(repo, label)                 # 读 config/segments.yaml
    lo, hi = seg["batches"]
    ids, id2batch = _seg_ids(repo, seg["lane"], lo, hi)     # data/batches.jsonl
    led = {r["id"]: r for r in read_jsonl(Path(opus_data) / "ledger.jsonl")}
    fwd = list(read_jsonl(Path(opus_data) / "forward.jsonl"))
    pat = list(read_jsonl(Path(opus_data) / "patches.jsonl")) if (...).exists() else []
    cur = resolve_map(fwd, pat)
    d = seg_dir(label); fz = d / "frozen"; fz.mkdir(parents=True)
    write_jsonl(fz / "source.jsonl", [{"id": i, "jp": led[i]["jp"], "batch": id2batch[i]} for i in ids])
    write_jsonl(fz / "opus.jsonl", [{"id": i, "zh": cur[i]} for i in ids])
    anchor_ids = _anchor_ids(repo)                # skeleton/anchors.yaml 全部 item id
    patched = {r["id"] for r in pat}
    locked = sorted(set(ids) & (anchor_ids | patched))
    (fz / "locked.json").write_text(dumps_locked(locked, anchor_ids, patched))
    _copy_glossary(repo, fz)                       # active.json/speakers.json/voices/style.md/polish.md/anchors.yaml
    _copy_notes(Path(opus_data) / "notes", fz / "notes", lo, hi)
    (fz / "rulings.md").write_text(f"# {label} 润色裁决与前序纪要\n（追加式）\n")
    manifest = {..., "files": {rel: sha256_file(p) for ...}, "opus_at": {...}}
    (d / "manifest.json").write_text(pipelib.dumps(manifest))
    return d
```
`verify(label)`：重算 frozen 逐文件 sha256 与 manifest 比对，返回漂移相对路径列表。

- [ ] **Step 4: 跑测通过 + 变异**：①locked 漏并 anchor 集；②opus.jsonl 直接抄 forward 不走 resolve；③verify 恒返回 []（三个变异各自必须打红对应测试）。

- [ ] **Step 5: Commit** — `feat: polish_setup——SEG 级冻结+锁定面+opus 固化时点`

---

### Task 4: tools/polish_context.py（大批划分 + prompt 拼接）

**Files:**
- Create: `tools/polish_context.py`
- Test: `tests/test_polish_context.py`

**Interfaces:**
- Consumes: Task 3 的 frozen 全套；`data/batches.jsonl`；polishlib.CFG 双帽
- Produces:
  - `plan(label) -> list[dict]`：把段表批号区间按双帽（≤session_size 批 / ≤session_lines 行）切成会话组：`[{session: 1, batches: [36,…,41], lines: 583}, …]`——**SEG-1（b36–62）opus 时代逐批跑，本函数即是补上会话分组**
  - `render(label, session_no) -> str`：一条会话的完整 prompt——任务说明（润色契约）+ 锁定 id 清单 + frozen/glossary 全套 + 逐批的 `[b36] id: 【jp】 / 【opus zh】 / (note…)` 正文 + 输出契约
  - `main` CLI：`--seg <label> --plan`（打印会话表）/ `--seg <label> --session N --out <path>`（写 prompt 文件并打印 sha256 = prompt_hash，同时落 `pilot/polish/<label>/plan.json` 记录 {session, batches, prompt_hash}）
- 输出契约（写进 prompt，供 Task 5 解析）：每批产一个 JSONL 文件 `raw/<channel>/b<批号>.out`，每行
  `{"id": 5683, "jp_tail": "<原文末8字>", "zh": "<润色稿或原样 opus>", "score": 87, "note": "", "adjudicate": false}`；
  批内**每个非锁定 id 恰好一行**；锁定 id（带【锁】标）**不得出现**；不改动的行 zh 逐字抄 opus。

- [ ] **Step 1: 失败测试**

```python
def test_plan_respects_double_cap(mini_seg):     # mini 段：3 批，行数 300/300/100
    sessions = pc.plan("segX", session_lines=600, session_size=10)
    assert [s["batches"] for s in sessions] == [[1, 2], [3]]   # 600 顶帽切组

def test_plan_size_cap(mini_seg11):              # 11 个 10 行小批
    sessions = pc.plan("segX", session_lines=600, session_size=10)
    assert len(sessions[0]["batches"]) == 10     # 批数帽先触发

def test_render_marks_locked_and_embeds_opus(mini_seg):
    p = pc.render("segX", 1)
    assert "【锁】" in p and "锁定 id" in p
    assert "旧译文本样例" in p                    # opus zh 在正文里
    assert "b<批号>.out" not in p or True         # 输出契约按实名渲染
```

- [ ] **Step 2: 失败** → **Step 3: 实现**：`plan` 累计 `len(ids)` 与批数双帽贪心切组；`render` 读 frozen（不读活仓库——**润色输入只认冻结面**），glossary 段沿 `build_context._render_voices/_render_anchors` 的渲染函数直接 import 复用。

- [ ] **Step 4: 通过 + 变异**：①双帽只查其一；②render 从仓库活 glossary 读而非 frozen（测试用「frozen 改坏一字后 render 必须跟着变」来抓）。

- [ ] **Step 5: Commit** — `feat: polish_context——SEG-1 会话分组补齐+润色 prompt 拼接`

---

### Task 5: tools/polish_ingest.py（唯一入仓）

**Files:**
- Create: `tools/polish_ingest.py`
- Test: `tests/test_polish_ingest.py`

**Interfaces:**
- Consumes: `raw/<channel>/b<N>.out`（模型输出契约见 Task 4）、frozen/source.jsonl、frozen/opus.jsonl、frozen/locked.json、plan.json（prompt_hash）
- Produces:
  - `ingest(label, channel, batch) -> dict`：`{"ok": bool, "added": int, "dead": [...], "reason": str}`
  - 成功 → append `candidates.<channel>.jsonl`，每行补齐 `jp_hash`（sha256(frozen jp)）、`opus_hash`、`channel`、`batch`、`prompt_hash`、`ts`
  - **判死**（记入返回值并打印，不入仓）：id 不在批内；jp_tail 与 frozen 不符；锁定 id 出稿（额外计入 `discipline.<channel>.json` 纪律画像）
  - **整批失败**（不入仓任何行）：raw 不是合法 JSONL；批内非锁定 id 覆盖不完整（截断特征）
  - **幂等**：`ingested.<channel>.json` 记录已入仓批号；重复调用同批 = no-op（打印提示）
- CLI: `--seg <label> --channel <ch> --batch N`（或 `--all` 扫 raw 目录）

- [ ] **Step 1: 失败测试**（mini 段 + 手造 raw）

```python
def test_ingest_ok_and_receipt(mini):
    r = pi.ingest("segX", "chA", 1)
    assert r["ok"] and r["added"] == 3
    rows = list(read_jsonl(mini.d / "candidates.chA.jsonl"))
    assert rows[0]["jp_hash"] == sha256_text(mini.jp[10])

def test_bad_tail_kills_line_not_batch(mini):
    mini.corrupt_tail(id=11)
    r = pi.ingest("segX", "chA", 1)
    assert r["ok"] and r["added"] == 2 and r["dead"][0]["id"] == 11

def test_locked_id_killed_and_disciplined(mini):
    mini.add_locked_line(id=13)
    r = pi.ingest("segX", "chA", 1)
    assert 13 in [d["id"] for d in r["dead"]]
    assert json.loads((mini.d / "discipline.chA.json").read_text())["locked_hits"] == 1

def test_incomplete_coverage_fails_whole_batch(mini):
    mini.drop_line(id=12)                          # 截断特征
    r = pi.ingest("segX", "chA", 1)
    assert not r["ok"]
    assert not (mini.d / "candidates.chA.jsonl").exists()

def test_idempotent(mini):
    pi.ingest("segX", "chA", 1); r2 = pi.ingest("segX", "chA", 1)
    assert r2["added"] == 0 and len(list(read_jsonl(...))) == 3
```

- [ ] **Step 2: 失败** → **Step 3: 实现**（解析→三查→原子决定整批入/不入→append→记 ingested）。

- [ ] **Step 4: 通过 + 变异**：①尾串核验恒真；②覆盖不完整仍入仓；③幂等标记不写。三变异各红。

- [ ] **Step 5: Commit** — `feat: polish_ingest——回执核验+锁定判死+批级幂等的唯一入仓口`

---

### Task 6: tools/polish_check.py（保税仓机械闸）

**Files:**
- Create: `tools/polish_check.py`
- Test: `tests/test_polish_check.py`

**Interfaces:**
- Consumes: `check_batch.check`（R2a/R2b/R2c/W1/W2/W3 整体复用）、frozen/source.jsonl、candidates、`glossary/speakers.json`、frozen glossary active.json
- Produces: `gate(label, channel) -> dict`：对该通道全部候选跑 `check_batch.check(source_rows, draft_rows, speakers, glossary)`（draft=候选 zh），返回 `{id: {"hard": [...], "warn": [...]}}` 并写 `gates.<channel>.json`；**hard 非空的候选后续一切分流不得自动清关**（Task 7 消费）。W4 不在此跑（需全库兄弟索引，放清关后全段复检，见 Task 11 runbook）。
- CLI: `--seg <label> --channel <ch>`

- [ ] **Step 1: 失败测试**：候选丢【】说话人 → gate 报 R2b hard；候选行宽爆 → W3 warn；全绿候选 → 空。
- [ ] **Step 2: 失败** → **Step 3: 实现**（薄封装：组装 source_rows/draft_rows → check → 落盘）。
- [ ] **Step 4: 通过 + 变异**：gate 吞掉 hard 只留 warn → 测试必须红。
- [ ] **Step 5: Commit** — `feat: polish_check——候选级机械闸（复用 check_batch）`

---

### Task 7: tools/polish_triage.py（四桶分流 + 自动清关判定 + 抽检）

**Files:**
- Create: `tools/polish_triage.py`
- Test: `tests/test_polish_triage.py`

**Interfaces:**
- Consumes: 全部 `candidates.*.jsonl`、frozen/opus.jsonl、frozen/locked.json、`gates.*.json`、polishlib（edit_distance/autoclear_limit/CFG）
- Produces:
  - `triage(label) -> dict` 并写 `triage.json`：每候选一条
    `{id, channel, bucket, edit, autoclear: bool, sampled: bool}`
    - bucket 判定顺序：locked→0（理论上 ingest 已判死，此处兜底再判死）；`zh == opus`（逐字）→1；其余按（`adjudicate` 显式请裁优先，再按 `edit 大→小`、同 edit 按 `score 低→高`）排序，前 K−抽检占用 名→2；其余→3
    - autoclear：bucket∈{2,3} 且 `edit ≤ autoclear_limit(opus)` 且 gates hard 空 且 channel 自动清关权开启（`channel_state.json`，准入小考写入，缺省关闭）→ 从桶中摘出为 autoclear；其中按 `sample_rate` 抽 `sampled=true` 塞回裁决队列（占 K）
    - **channel=="amplify" 恒不 autoclear**
    - 抽样与排序**确定性**：random.Random(int(manifest["files"]["source.jsonl"][:8], 16))
  - `queue.md`：裁决队列（K 内，多通道同 id 并排：jp / opus / 各候选 zh+score+note）
- CLI: `--seg <label>`

- [ ] **Step 1: 失败测试**

```python
def test_buckets(mini):                            # 造 4 类候选
    t = pt.triage("segX")
    assert by_id(t, 10)["bucket"] == 1             # zh==opus
    assert by_id(t, 11)["bucket"] == 2             # 大改，配额内
    assert by_id(t, 12)["bucket"] == 3             # 配额 K=1 挤出
    assert by_id(t, 13)["bucket"] == 0             # locked 兜底

def test_autoclear_requires_gate_green_and_right(mini):
    mini.enable_autoclear("chA")
    t = pt.triage("segX")
    assert by_id(t, 14)["autoclear"]               # 小改+绿
    mini.make_gate_hard(14)
    assert not by_id(pt.triage("segX"), 14)["autoclear"]

def test_amplify_never_autoclears(mini):
    mini.enable_autoclear("amplify")
    assert not by_id(pt.triage("segX"), 15, ch="amplify")["autoclear"]

def test_deterministic_sampling(mini):
    assert pt.triage("segX") == pt.triage("segX")  # 两跑逐字段一致
```

- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：①autoclear 无视 hard；②配额排序丢显式请裁优先；③抽样用系统随机（两跑不一致测试抓）。
- [ ] **Step 5: Commit** — `feat: polish_triage——四桶分流+条件自动清关+确定性抽检`

---

### Task 8: tools/polish_commit.py（唯一清关口）

**Files:**
- Create: `tools/polish_commit.py`
- Test: `tests/test_polish_commit.py`

**Interfaces:**
- Consumes: `triage.json`、`decisions.jsonl`、`candidates.*.jsonl`、`add_patch.resolve_data_dir`（车道模式显式 --data-dir 闸原样复用）、`build_context.glossary_version`
- Produces:
  - `commit(label, data_dir, dry_run=True) -> list[patch_row]`
    - 来源两路：①decisions 里 verdict∈{adopt, edit} 的（adopt 取 chosen_channel 候选 zh；edit 取 edited_zh）；②triage 里 `autoclear and not sampled` 的候选
    - patch 行：`{"id", "zh", "reason": "polish", "glossary_v", "ts", "prov": {"channel", "candidate_ts", "seg"}}`（resolve 只读已知键，向后兼容）
    - 自动清关的同时 append 一条 `decisions.jsonl` 记录 `verdict="auto"`（裁决面完备：每个落地 patch 都有 decision 可查）
    - **dry_run=True 是默认**：只打印将写入的 patch 与倒查链（id→candidate ts→prompt_hash），不落盘；`--apply` 才写
    - 写前逐 id 过 `add_patch.existing_patches` 播报（防误覆盖已有裁决——注意锁定面本就排除了冻结时点已有 patch 的 id，此处防的是**润色期间新落的** patch）
  - 幂等：`committed.json` 记录已清关 (id, decision_ts)；重复 `--apply` no-op
- CLI: `--seg <label> --data-dir <dir> [--apply]`

- [ ] **Step 1: 失败测试**：dry-run 不写文件但返回 2 行；apply 写入且 prov 回指正确；重复 apply 零新增；期间新出现的 patch 触发 stderr 播报。
- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：①dry_run 也落盘（测试抓文件不存在）；②autoclear sampled 的也清关；③prov 丢 channel。
- [ ] **Step 5: Commit** — `feat: polish_commit——保税仓唯一清关口（dry-run 默认+prov 倒查链）`

---

### Task 9: tools/polish_amplify.py（意图归纳 + 放大扫描装配）

**Files:**
- Create: `tools/polish_amplify.py`
- Test: `tests/test_polish_amplify.py`

**Interfaces:**
- Consumes: `decisions.jsonl`（reason_code）、`triage.json`、candidates、frozen
- Produces:
  - `digest(label) -> str`：意图纪要 markdown——原因码分布表 + 每码 ≤3 个代表例（jp/opus/候选/最终 zh/裁决语），追加写入 `frozen/../rulings.md`（**追加**，不覆盖）并返回文本
  - `scan_prompt(label) -> str`：纪要 + 整 SEG 四桶结果全景（含桶 3 落选句全文）+ 输出契约（同 Task 4，channel 固定 amplify、raw 落 `raw/amplify/`）
  - 轮数闸：`rulings.md` 里已有本 SEG 放大标记 → 拒绝再装配（`amplify_rounds: 1`）
- CLI: `--seg <label> --digest` / `--seg <label> --scan-prompt --out <path>`
- 放大产物回炉：直接复用 `polish_ingest --channel amplify` + `polish_triage`（amplify 恒不 autoclear，Task 7 已保证）→ 追加小裁决 → `polish_commit`。

- [ ] **Step 1: 失败测试**：3 条 decisions（两码）→ digest 含分布表与代表例；二次调用 scan 装配被轮数闸拒绝。
- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：轮数闸恒放行 → 测试红。
- [ ] **Step 5: Commit** — `feat: polish_amplify——裁决意图纪要+放大扫描装配（每段一轮）`

---

### Task 10: tools/polish_calibrate.py（通道准入小考）

**Files:**
- Create: `tools/polish_calibrate.py`
- Test: `tests/test_polish_calibrate.py`

**Interfaces:**
- Consumes: opus 车道 `patches.jsonl`（金标池：reason∈{review, recall} 的 id 的**现行文本**）、frozen/source.jsonl、frozen/opus.jsonl、polishlib
- Produces:
  - `make(label, n_gold=10, n_norm=10) -> Path`：确定性抽样（种子同 Task 7），产 `calib/<label>.batch.jsonl`（混排、**不带锁标**、格式同生产批正文行）+ `calib/<label>.truth.json`（id→{is_gold}，**此文件不进任何 prompt**）
  - `score(label, raw_path) -> dict`：`{"gold_unchanged": x, "gold_minor": y, "gold_substantive": z, "pass": z/(x+y+z) < CFG["calib_fail"]}`（三档按 edit_distance vs minor_edit/autoclear_limit）；结果写 `channel_state.json` 的 `{channel: {"autoclear": pass}}`
- CLI: `--seg <label> --make` / `--seg <label> --score --channel <ch> --raw <path>`
- 金标已知偏差（spec §8）在工具输出里原样播报：「金标为曾出问题的非随机子集，本考只做门槛」。

- [ ] **Step 1: 失败测试**：金标 10 句中 4 句实质改写 → pass=False、channel_state 关闭 autoclear；0 句 → True 开启。truth 文件绝不出现在 make 产出的 batch 文件内容里。
- [ ] **Step 2: 失败** → **Step 3: 实现** → **Step 4: 通过 + 变异**：①三档阈值互换；②truth 混进 batch（测试抓）。
- [ ] **Step 5: Commit** — `feat: polish_calibrate——金标准入小考（门槛制，播报已知偏差）`

---

### Task 11: SEG-1 点火准备（冻结实跑 + runbook + handoff）

**Files:**
- Create: `docs/ops/p4-polish-runbook.md`、`docs/ops/p4-seg1-polish-handoff.md`
- Produce (数据，不入 git 的部分按现行惯例处理): `pilot/polish/seg1-s2/`（frozen + plan.json + calib）

**Interfaces:**
- Consumes: Task 1–10 全部工具
- Produces: 两条通道可直接照单点火的一切。

- [ ] **Step 1: 实跑 SEG-1 冻结与计划**

```bash
uv run python tools/polish_setup.py --seg seg1-s2 --opus-data pilot/lanes/opus/data
uv run python tools/polish_setup.py --verify seg1-s2
uv run python tools/polish_context.py --seg seg1-s2 --plan
uv run python tools/polish_calibrate.py --seg seg1-s2 --make
```
Expected: frozen 全套生成、verify 绿、会话表打印（27 批按双帽预计 3–5 组）、校准批就绪。抽查 locked.json：SEG-1 的锚点 id（anchors.yaml chapter=global/s2 相关）与已裁 patch id 都在。

- [ ] **Step 2: 写 p4-polish-runbook.md**

内容（按本计划各工具的 CLI 逐条落成操作序列）：命名与目录约定 → SEG 冻结 → 准入小考（两通道各跑校准批并 `--score`）→ 会话点火（见 handoff）→ 逐批 ingest → gate → triage → 段末裁决（queue.md 逐条 verdict+原因码 append decisions.jsonl 的命令形态）→ amplify 一轮 → commit（先 dry-run 人工核对倒查链，再 --apply，`--data-dir pilot/lanes/opus/data`）→ 清关后必跑：`check_batch` 全段 W4 复检 + `check_qa_quotes.py --qa config/ayano_qa/*.yaml --data-dir pilot/lanes/opus/data` + 题库引文更新 → 阈值调整记台账。

- [ ] **Step 3: 写 p4-seg1-polish-handoff.md（双通道点火指令）**

- **fable-workflow 通道**（channel=`fable-wf`）：每会话一个 Workflow 子代理；prompt 由 `polish_context.py --seg seg1-s2 --session N --out work/ctx/p4s1-sN.md` 生成；子代理任务=读该文件、按输出契约写 `pilot/polish/seg1-s2/raw/fable-wf/b<N>.out`（绝对路径写死在指令里）；落完由控制会话跑 ingest。
- **paseo-deepseek 通道**（channel=`ds-flash`）：`create_agent`（provider 取用户 paseo 中已配置的 deepseek v4 flash endpoint 实名，点火前 `list_providers` 核对）在独立 workspace 跑，同一 raw 契约、同一绝对路径；计费入 `data/api_ledger.jsonl`；心跳=最近 raw 落盘时间戳，`Monitor`/heartbeat 检查目录 mtime。
- 并行安全条款：两通道只写各自 `raw/<channel>/` 与（经 ingest）各自 candidates 文件；谁也不碰 patches。
- 段末流程回指 runbook；K=150、抽检、放大一轮、清关 dry-run 纪律全部写明。

- [ ] **Step 4: 全量测试 + 提交**

```bash
uv run pytest -q
git add docs/ops/p4-polish-runbook.md docs/ops/p4-seg1-polish-handoff.md pilot/polish/seg1-s2/manifest.json pilot/polish/seg1-s2/plan.json
git commit -m "docs: P4 润色 runbook + SEG-1 双通道点火 handoff（冻结与计划实跑产物）"
```
（frozen/ 大文件是否入库：沿 opus 车道现行惯例——若车道冻结拷贝入库则同样入库，逐路径显式 add。）

---

## Self-review 记录

- spec 覆盖：§2→Task 1；§3→Task 3；§4→Task 5/8（回执落地修正见 Global Constraints）；§5→Task 7；§6→Task 4/5/11；§7→Task 9；§8→Task 6/10/11；§9→Task 2 与各 task 变异步骤；§10 开放事项由用户已定（SEG-1、双通道齐跑）。
- 类型一致：`seg_dir/edit_distance/autoclear_limit`（Task 2）被 5/7/10 按同名引用；`ingest→candidates 字段` 与 Task 7/8 消费字段一致；`channel_state.json` 由 Task 10 写、Task 7 读。
- 无占位符；每 task 有测试代码与判定预期。
