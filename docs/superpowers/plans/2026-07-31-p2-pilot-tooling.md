# P2 试点工装与开跑准备 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs/superpowers/specs/2026-07-31-p2-pilot-design.md` 所需的全部工装建起来，并实建两条隔离车道、生成两份逐批执行计划，跑通 batch 1 的隔离验收——此后即可开始 35×2 批次的实际翻译。

**Architecture:** 三项对既有工具的小改（`build_context` 暴露 `--repo`、`gen_plan` 选批与渲染分离并支持车道、`translator_cc.md` 内置路径基准）+ 三个新工具（车道搭建与冻结校验、语义崩溃探测、双车道分层对照材料生成）+ 一个集成任务。全部纯 stdlib/既有依赖，无新增第三方包。

**Tech Stack:** uv 项目 Python（≥3.12），依赖仅 pillow/pyyaml/pytest；测试 `uv run pytest`。

## Global Constraints

- 运行 `uv run python tools/<x>.py`；测试 `uv run pytest`；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），main 分支直提交。
- `lua_scripts/`、`png/`、`skeleton/`、`glossary/`、`analysis/` 只读——本计划的任何任务都不得修改它们（`skeleton/` 与 `glossary/` 已由 `git tag skeleton-v1` 冻结）。
- `data/batches.jsonl`、`data/timeline.jsonl` 等生成物本计划不重建：试点期间 `batches.jsonl` 必须与冻结哈希一致，重切会破坏双车道可比性。
- 试点期间**不裁决任何术语提案**、不新增 `glossary.vN.yaml`：提案照收进车道的 `data/notes/<chapter>.md`，裁决全部推迟到试点结束。
- 现行术语表版本为 **v6**（`glossary/glossary.v6.yaml`）；工具里凡需版本号一律调 `tools.build_context.glossary_version(repo)` 动态推导，禁止硬编码。
- 车道根固定为 `work/lanes/<lane>/`（`work/` 已在 `.gitignore` 内，两条车道的译文与产物不进主库历史）。
- 新工具**不得新增第三方依赖**：可用标准库、既有项目依赖 `pyyaml`（读 `anchors.yaml`/`cards.zh.yaml`/`glossary.vN.yaml` 一律用 `yaml.safe_load`，禁止手写 YAML 解析），以及既有 `tools/pipelib.py` 助手（`REPO/DATA/WORK`、`read_jsonl`/`write_jsonl`/`append_jsonl`、`dumps`、`sha256_file`、`display_width`）。

## 文件结构

| 文件 | 职责 |
|---|---|
| `tools/build_context.py`（改） | ①`main()` 暴露 `--repo`（Task 1）；②第三节锚点压成 id/jp/zh、第四节内嵌 7 份角色口调表（Task 2） |
| `tools/gen_plan.py`（改） | 选批（`select`）与渲染（`render`）分离；新增连续段模式与车道感知路径/配置块 |
| `prompts/translator_cc.md`（改） | 新增「路径基准」节（派发方注入车道根）与隔离纪律条目 |
| `tools/lane_setup.py`（新） | 建车道目录（只读资产符号链接、`skeleton/`+`glossary/` 拷贝冻结）、写 `lane.json` 与 `pilot-manifest.json`、`--verify` 校验漂移 |
| `tools/detect_collapse.py`（新） | 语义崩溃探测：残留假名比 / 中日长度比离群 / 复读循环 |
| `tools/compare_lanes.py`（新） | 双车道分层统计、盲评并排材料、卡面回译自检材料 |
| `tests/test_lane_setup.py`、`tests/test_detect_collapse.py`、`tests/test_compare_lanes.py`（新） | 对应单测 |
| `tests/test_build_context.py`、`tests/test_gen_plan.py`（改） | 追加/更新用例 |

---

### Task 1: `build_context` 暴露 `--repo`

**Files:**
- Modify: `tools/build_context.py`（`main()`，约 222–232 行）
- Test: `tests/test_build_context.py`（追加）

**Interfaces:**
- Consumes: 已有 `build(batch, profile, baseline, repo=None, jp_fallback=False)`——`repo` 同时决定 `data/`、`skeleton/`、`glossary/` 读取路径与 `work/` 落点。
- Produces: CLI `--repo <dir>`，供 Task 3 生成的计划文本与 Task 8 调用。

- [ ] **Step 1: Write the failing test**

追加到 `tests/test_build_context.py` 末尾（复用该文件已有的 `_env(tmp_path)` 夹具，它会造一个含 `data/`+`skeleton/`+`glossary/` 的替身仓库）：

```python
def test_cli_repo_flag_routes_reads_and_writes_to_that_dir(tmp_path, monkeypatch):
    """--repo 必须把数据读取与产物落点一起切到该目录：既有 build(repo=…) 已实现，
    此前只是没有 CLI 入口。去掉 main() 里的 --repo 透传本测试必红。"""
    from tools.build_context import main
    env = _env(tmp_path)
    (env / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "车道标记译文", "batch": 0, "backend": "cc",
                    "model": "m", "ctx": "c", "glossary_v": 4, "ts": "t"},
                   ensure_ascii=False), encoding="utf-8")
    (env / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    rc = main(["--batch", "1", "--profile", "cc", "--baseline", "none",
               "--repo", str(env)])
    assert rc == 0
    ctx = env / "work" / "ctx" / "batch_1" / "context.md"
    assert ctx.exists(), "产物必须落在 --repo 指定的目录下"
    assert (env / "work" / "ctx" / "batch_1" / "source.jsonl").exists()
    assert (env / "work" / "ctx" / "batch_1" / "manifest.json").exists()


def test_cli_without_repo_keeps_default_behaviour(tmp_path, monkeypatch):
    """不给 --repo 时行为不变（仍读仓库 data/、写 pipelib.WORK）——用 ZND_WORK
    把落点引到 tmp_path，断言真实仓库 work/ 不被本测试写入。"""
    from tools.build_context import main
    import tools.pipelib as pipelib
    monkeypatch.setattr(pipelib, "WORK", tmp_path / "w")
    import tools.build_context as bc
    monkeypatch.setattr(bc, "_WORK", tmp_path / "w")
    rc = main(["--batch", "1", "--profile", "cc", "--baseline", "none",
               "--jp-fallback"])
    assert rc == 0
    assert (tmp_path / "w" / "ctx" / "batch_1" / "context.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_context.py -k repo_flag -v`
Expected: FAIL —— `unrecognized arguments: --repo`（argparse 报错，SystemExit 2）。

- [ ] **Step 3: Write minimal implementation**

把 `tools/build_context.py` 的 `main()` 改成（只加一行参数、改一行调用）：

```python
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--profile", choices=["api-A", "api-B", "cc"], required=True)
    ap.add_argument("--baseline", choices=["none", "ref", "revise", "judge"], default="none")
    ap.add_argument("--jp-fallback", action="store_true")
    ap.add_argument("--repo", default=None,
                    help="车道根目录（内含 data/skeleton/glossary，产物落其 work/ 下）；"
                         "省略时读仓库根、产物落 pipelib.WORK")
    a = ap.parse_args(argv)
    return build(a.batch, a.profile, a.baseline, repo=a.repo, jp_fallback=a.jp_fallback)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_context.py -v`
Expected: 全部 PASS（含既有用例，无回归）。

- [ ] **Step 5: Commit**

```bash
git add tools/build_context.py tests/test_build_context.py
git commit -m "feat: build_context 暴露 --repo，支持车道隔离调用"
```

---

### Task 2: `build_context` 第三节压缩锚点 + 第四节内嵌角色口调表

**Files:**
- Modify: `tools/build_context.py`（新增 `_render_anchors`/`_render_voices`，改 `build()` 中第三、四节拼装与 manifest）
- Test: `tests/test_build_context.py`（追加）

**Interfaces:**
- Produces：
  - `_render_anchors(anchors_path) -> str`——第三节紧凑对照；每条渲染两行 `[id] jp` 与 `    → zh`，按 `chapter` 分组小标题；文件不存在时返回 `"\n## 三、锚点行（暂缺）"`。
  - `_render_voices(voices_dir) -> str`——把 `glossary/voices/*.md` 按文件名升序拼成 `### 口调表：<stem>` + 全文；目录不存在返回 `""`。
  - `manifest.json` 新增 `voices` 字段（口调表渲染结果的 sha256）。

**背景（spec §4.4）**：`prompts/reviewer_cc.md` 把「口调表偏离」列为四类必查发现之一并点名全部 7 份表，但 `translator_cc.md` 零提及、context 也从不嵌它们的正文——译者被按一份从未拿到的标准打分，而口调一致性是人工 rubric 三栏之一。实测：7 份表共 21,084 字符；`anchors.yaml` 整文件 23,285 字符中 `recall` 注释占 8,036（35%），压成 id/jp/zh 后约 8,530 字符。两项配套后净 +6,329 字符（batch 32 由 170,783 → 177,112），换来译者与评审终于按同一份标准工作。

- [ ] **Step 1: Write the failing test**

追加到 `tests/test_build_context.py` 末尾：

```python
def _env_with_voices(tmp_path):
    """在既有 _env 夹具上补出 anchors.yaml（含 recall）与 voices/ 两份口调表。"""
    d = _env(tmp_path)
    (d / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    (d / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n"
        "  items:\n"
        "    - {id: 1, jp: 第一句, zh: 定译第一句, recall: 这是给骨架维护者的复现说明}\n",
        encoding="utf-8")
    (d / "glossary" / "voices").mkdir()
    (d / "glossary" / "voices" / "naoya.md").write_text(
        "# 直哉口调表\n自称：僕→我", encoding="utf-8")
    (d / "glossary" / "voices" / "sakura.md").write_text(
        "# サクラ口调表\n句尾：ですね体", encoding="utf-8")
    return d


def test_anchor_section_is_compact_and_drops_recall(tmp_path):
    """第三节只给 id/jp/zh：recall 是骨架维护者的元信息，对译者不改变行动，
    却占该节 35% 体量。保留整文件内嵌本测试必红。"""
    from tools.build_context import build
    d = _env_with_voices(tmp_path)
    assert build(1, "cc", "none", repo=d, jp_fallback=True) == 0
    ctx = (d / "work" / "ctx" / "batch_1" / "context.md").read_text(encoding="utf-8")
    assert "定译第一句" in ctx, "锚点 zh 必须仍在"
    assert "[1] 第一句" in ctx, "锚点 jp 必须仍在，且为紧凑行形态"
    assert "这是给骨架维护者的复现说明" not in ctx, "recall 注释不应进入译者上下文"


def test_voice_sheets_are_embedded_in_section_four(tmp_path):
    """译者必须拿到评审据以打分的那 7 份口调表。"""
    from tools.build_context import build
    d = _env_with_voices(tmp_path)
    assert build(1, "cc", "none", repo=d, jp_fallback=True) == 0
    ctx = (d / "work" / "ctx" / "batch_1" / "context.md").read_text(encoding="utf-8")
    assert "## 四、术语、风格与角色口调" in ctx
    assert "口调表：naoya" in ctx and "自称：僕→我" in ctx
    assert "口调表：sakura" in ctx and "句尾：ですね体" in ctx
    # 口调表须排在第四节内、第五节之前
    assert ctx.index("自称：僕→我") < ctx.index("## 五、本批任务")


def test_manifest_records_voices_hash_and_it_tracks_changes(tmp_path):
    from tools.build_context import build
    import json as _json
    d = _env_with_voices(tmp_path)
    build(1, "cc", "none", repo=d, jp_fallback=True)
    h1 = _json.loads((d / "work" / "ctx" / "batch_1" / "manifest.json").read_text(
        encoding="utf-8"))["voices"]
    (d / "glossary" / "voices" / "naoya.md").write_text("# 直哉口调表\n改了", encoding="utf-8")
    build(1, "cc", "none", repo=d, jp_fallback=True)
    h2 = _json.loads((d / "work" / "ctx" / "batch_1" / "manifest.json").read_text(
        encoding="utf-8"))["voices"]
    assert len(h1) == 64 and h1 != h2, "口调表改动必须反映到 manifest 哈希"


def test_missing_voices_dir_degrades_gracefully(tmp_path):
    """既有夹具（无 voices/ 目录）必须照常构建——不得因缺目录而崩。"""
    from tools.build_context import build
    d = _env(tmp_path)
    (d / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    assert build(1, "cc", "none", repo=d, jp_fallback=True) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_build_context.py -k "compact or voice or manifest_records" -v`
Expected: FAIL —— 第三节仍是整文件内嵌（`recall` 断言不过）、第四节标题仍为「术语与风格」、manifest 无 `voices` 键（KeyError）。

- [ ] **Step 3: Write minimal implementation**

在 `tools/build_context.py` 顶部 import 区加 `import hashlib`，并新增两个渲染函数（放在 `_render_skeleton` 之后）：

```python
def _render_anchors(anchors_path) -> str:
    """第三节：锚点行紧凑日中对照。只给 id/jp/zh——recall 记录的是复现位置、
    裁决史与定译源指针，服务于骨架维护者；对译者不改变行动（命中锚点的行无论
    如何都要逐字沿用给定 zh），却占该节 35% 体量。省下的空间用于内嵌口调表。"""
    p = Path(anchors_path)
    if not p.exists():
        return "\n## 三、锚点行（暂缺）"
    groups = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    out = ["\n## 三、锚点行（日中对照；本批 source 命中的 id 必须逐字沿用 zh）"]
    for g in groups:
        out.append(f"### {g['chapter']}")
        for it in g["items"]:
            out.append(f"[{it['id']}] {it['jp']}")
            out.append(f"    → {it['zh']}")
    return "\n".join(out)


def _render_voices(voices_dir) -> str:
    """第四节尾部：角色口调表全文。reviewer_cc.md 按这些表判「口调表偏离」，
    译者此前拿不到它们——同一份标准必须两边都有（spec §4.4）。"""
    d = Path(voices_dir)
    if not d.is_dir():
        return ""
    return "".join(f"\n### 口调表：{p.stem}\n{p.read_text(encoding='utf-8')}\n"
                   for p in sorted(d.glob("*.md")))
```

改 `build()` 中第三、四节的拼装（替换原 `anchors = (...)` 与 `tail = [...]` 两处）：

```python
    anchors_p = repo / "skeleton" / "anchors.yaml"
    anchors = _render_anchors(anchors_p)
    voices = _render_voices(repo / "glossary" / "voices")
    tail = ["\n## 四、术语、风格与角色口调",
            json.dumps(env["active"], ensure_ascii=False),
            env["style"], voices,
            f"\n{SECTION5}（baseline={baseline}）"]
```

在 manifest 里增记一项（`"anchors"` 那行之后）：

```python
                "voices": hashlib.sha256(voices.encode("utf-8")).hexdigest(),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_build_context.py -v`
Expected: 全部 PASS（含既有用例——注意既有夹具没有 `voices/` 目录，`_render_voices` 必须优雅退化）。

- [ ] **Step 5: 真实数据体量核对**

Run:

```bash
uv run python -c "
import sys; sys.path.insert(0,'.')
from tools.build_context import build
for n in (1, 32):
    build(n, 'cc', 'none', jp_fallback=True)
    p = f'work/ctx/batch_{n}/context.md'
    print(n, len(open(p, encoding='utf-8').read()), '字符')
"
grep -c '口调表：' work/ctx/batch_1/context.md
```

Expected: batch 1 约 51,900 字符、batch 32 约 177,100 字符（各 ±2%，与 spec §4.4 记载一致）；`口调表：` 计数为 **7**。若 batch 32 显著超过 180,000 字符，停下来在报告里记录实测值——逼近子代理上限时需要回到 spec §4.4 的备选方案重新裁决。

- [ ] **Step 6: Commit**

```bash
git add tools/build_context.py tests/test_build_context.py
git commit -m "feat: context 内嵌角色口调表并压缩锚点节为 id/jp/zh"
```

---

### Task 3: `gen_plan` 选批与渲染分离 + 连续段模式 + 车道感知

**Files:**
- Modify: `tools/gen_plan.py`（`_header`/`_batch_task`/`_checkpoint_task`/`_final_task`/`render`/`main`）
- Test: `tests/test_gen_plan.py`（更新既有 3 例 + 追加新例）

**Interfaces:**
- Produces（供 Task 8 与试点执行使用）：
  - `select(batches, *, lane, chapter=None, batch_range=None) -> list[dict]`——按 lane 过滤，再按 chapter 或 `(lo, hi)` 闭区间批号过滤，返回按 `batch` 升序的列表。
  - `render(sel, label, lane, every=5, baseline="none", glossary_v=GLOSSARY_V, lane_cfg=None) -> str`——`sel` 由调用方选好；`lane_cfg` 为 `None` 时输出与改动前逐字一致，否则为 `{"lane": str, "lane_dir": str, "model": str, "effort": str, "append_model_id": str}` 并把全部路径切到车道下、在头部插入车道配置块。
  - CLI：`--lane <l>` + 互斥的 `--chapter <ch>` 或 `--batches <lo-hi>`（后者需 `--label <name>`）；车道四参数 `--lane-dir/--model/--effort/--append-model-id` 要么全给要么全不给。

- [ ] **Step 1: Write the failing test**

把 `tests/test_gen_plan.py` 整体替换为下面内容（前三例是既有用例按新签名的等价改写，后五例为新增）：

```python
import pytest
from tools.gen_plan import render, select, main
from tools.pipelib import write_jsonl

BATCHES = [{"batch": i, "lane": "main", "ids": [i], "jp_chars": 100,
            "chapter": "s1s", "cut_reason": "budget"} for i in range(1, 8)]

def _sel(chapter="s1s", lane="main", rng=None):
    return select(BATCHES, lane=lane, chapter=chapter, batch_range=rng)

def test_render_contains_tasks_and_checkpoints():
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert md.count("### Task") >= 7 + 2
    assert "build_context.py --batch 1" in md
    assert "check_batch.py --batch 1" in md
    assert "append_forward.py --batch 1" in md
    assert "梗概回译自检" in md and "CHECKPOINT" in md

def test_only_selected_chapter_and_lane():
    extra = BATCHES + [{"batch": 99, "lane": "ambient", "ids": [99], "jp_chars": 1,
                        "chapter": "sys", "cut_reason": "tail"}]
    md = render(select(extra, lane="main", chapter="s1s"), label="s1s", lane="main", every=5)
    assert "--batch 99" not in md

def test_render_glossary_v_is_a_parameter_not_the_module_constant():
    md6 = render(_sel(), label="s1s", lane="main", every=3, glossary_v=6)
    md9 = render(_sel(), label="s1s", lane="main", every=3, glossary_v=9)
    assert "--glossary-v 6" in md6 and "--glossary-v 9" not in md6
    assert "--glossary-v 9" in md9 and "--glossary-v 6" not in md9

def test_main_uses_dynamically_derived_glossary_version(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v9.yaml").write_text("{}", encoding="utf-8")
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    assert main(["--lane", "main", "--chapter", "s1s"]) == 0
    out = (tmp_path / "docs" / "superpowers" / "plans" / "translate-s1s.md").read_text(
        encoding="utf-8")
    assert "--glossary-v 9" in out
    assert "--glossary-v 6" not in out

# ---- 新增：连续段模式 ----

def test_select_batch_range_is_inclusive_and_sorted():
    sel = select(BATCHES, lane="main", batch_range=(2, 5))
    assert [b["batch"] for b in sel] == [2, 3, 4, 5]

def test_select_range_ignores_chapter_boundaries():
    mixed = BATCHES + [{"batch": 8, "lane": "main", "ids": [8], "jp_chars": 9,
                        "chapter": "crd", "cut_reason": "chapter"}]
    sel = select(mixed, lane="main", batch_range=(7, 8))
    assert [b["chapter"] for b in sel] == ["s1s", "crd"], "连续段必须跨章别取批"

# ---- 新增：车道感知 ----

LANE_CFG = {"lane": "opus", "lane_dir": "work/lanes/opus", "model": "opus",
            "effort": "max", "append_model_id": "claude-opus-5"}

def test_lane_cfg_rewrites_every_path_to_lane_root():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "--repo work/lanes/opus" in md
    assert "ZND_WORK=work/lanes/opus/work ZND_DATA=work/lanes/opus/data" in md
    assert "work/lanes/opus/work/out/batch_1.draft.jsonl" in md
    assert "work/lanes/opus/data/forward.jsonl" in md
    # 不得残留仓库相对的产物路径
    assert "`work/ctx/batch_1/" not in md
    assert "git add data/forward.jsonl" not in md

def test_lane_cfg_emits_config_block_with_model_and_effort():
    md = render(_sel(), label="pilot-opus", lane="main", every=3, lane_cfg=LANE_CFG)
    assert "claude-opus-5" in md
    assert "effort" in md and "max" in md
    assert "Workflow" in md, "必须写明只能走 Workflow 派发（Agent 工具设不了 effort）"
    assert "work/lanes/" in md and "隔离" in md, "必须写明隔离纪律"

def test_no_lane_cfg_output_is_byte_identical_to_repo_mode():
    """回归闸：不给 lane_cfg 时输出必须与车道感知改造前逐字一致。"""
    md = render(_sel(), label="s1s", lane="main", every=3)
    assert "work/ctx/batch_1/" in md
    assert "git add data/forward.jsonl" in md
    assert "--repo" not in md and "ZND_WORK" not in md

def test_main_batches_mode_writes_labelled_plan(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v6.yaml").write_text("{}", encoding="utf-8")
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    rc = main(["--lane", "main", "--batches", "2-5", "--label", "pilot-opus",
               "--lane-dir", "work/lanes/opus", "--model", "opus",
               "--effort", "max", "--append-model-id", "claude-opus-5"])
    assert rc == 0
    out = (tmp_path / "docs" / "superpowers" / "plans" /
           "translate-pilot-opus.md").read_text(encoding="utf-8")
    assert "--batch 2" in out and "--batch 5" in out
    assert "--batch 1" not in out and "--batch 6" not in out
    assert "--repo work/lanes/opus" in out

def test_main_batches_mode_requires_label(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    with pytest.raises(SystemExit):
        main(["--lane", "main", "--batches", "2-5"])

def test_main_lane_params_are_all_or_nothing(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(); (tmp_path / "glossary").mkdir()
    write_jsonl(tmp_path / "data" / "batches.jsonl", BATCHES)
    monkeypatch.setattr("tools.gen_plan.REPO", tmp_path)
    monkeypatch.setattr("tools.gen_plan.DATA", tmp_path / "data")
    with pytest.raises(SystemExit):
        main(["--lane", "main", "--batches", "2-5", "--label", "x",
              "--lane-dir", "work/lanes/opus"])   # 缺 model/effort/append-model-id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gen_plan.py -v`
Expected: FAIL —— `ImportError: cannot import name 'select'`。

- [ ] **Step 3: Write minimal implementation**

改 `tools/gen_plan.py`。**新增**路径助手与 `select()`：

```python
def _paths(lane_cfg):
    """把计划文本里的全部路径按车道根改写。lane_cfg 为 None 时返回仓库相对路径，
    输出与车道感知改造前逐字一致（回归闸 test_no_lane_cfg_output_is_byte_identical
    _to_repo_mode 锁死这一点）。"""
    if lane_cfg is None:
        return {"ctx": "work/ctx", "out": "work/out", "forward": "data/forward.jsonl",
                "notes": "data/notes", "repo_arg": "", "env": ""}
    d = lane_cfg["lane_dir"]
    return {"ctx": f"{d}/work/ctx", "out": f"{d}/work/out",
            "forward": f"{d}/data/forward.jsonl", "notes": f"{d}/data/notes",
            "repo_arg": f" --repo {d}",
            "env": f"ZND_WORK={d}/work ZND_DATA={d}/data "}


def _lane_block(lane_cfg):
    if lane_cfg is None:
        return ""
    return f"""

## 车道配置（本计划专属，派发时逐字遵守）

| 项 | 值 |
|---|---|
| lane | {lane_cfg["lane"]} |
| lane_dir | {lane_cfg["lane_dir"]} |
| model | {lane_cfg["model"]} |
| effort | {lane_cfg["effort"]} |
| append_model_id | {lane_cfg["append_model_id"]} |

- **派发只能走 Workflow 的 `agent(prompt, {{"model": "{lane_cfg["model"]}", "effort": "{lane_cfg["effort"]}"}})`**——`Agent` 工具无法指定 reasoning effort，用它重试会静默回落到会话默认档，使该批次失去可比性。任何一次重试都必须重新读取本表。
- **隔离纪律**：禁止读取、列出 `work/lanes/` 下除 `{lane_cfg["lane"]}` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `{lane_cfg["lane_dir"]}/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：试点期间提案只追加进 `{lane_cfg["lane_dir"]}/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `{lane_cfg["lane_dir"]}/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。"""


def select(batches, *, lane, chapter=None, batch_range=None):
    """按 lane 过滤，再按 chapter 或 batch_range（闭区间 (lo, hi)）过滤，
    返回按 batch 升序的列表。两个过滤条件可同时为 None（取该 lane 全部）。"""
    sel = [b for b in batches if b["lane"] == lane]
    if chapter is not None:
        sel = [b for b in sel if b["chapter"] == chapter]
    if batch_range is not None:
        lo, hi = batch_range
        sel = [b for b in sel if lo <= b["batch"] <= hi]
    return sorted(sel, key=lambda b: b["batch"])
```

**改** `_header` 签名为 `(label, lane, every, count, glossary_v, lane_cfg)`：把原文里的 `{chapter} 章` 改成 `{label}`，把 `data/forward.jsonl` 改成 `{p["forward"]}`、`data/notes/{chapter}.md` 改成 `{p["notes"]}/<chapter>.md`（函数体开头先 `p = _paths(lane_cfg)`），并在 `---"""` 之前拼接 `{_lane_block(lane_cfg)}`。

**改** `_batch_task` 签名为 `(tnum, batch, baseline, glossary_v, p)`，函数体内四处路径替换：

```python
def _batch_task(tnum, batch, baseline, glossary_v, p):
    n, ch, ids = batch["batch"], batch["chapter"], batch["ids"]
    return f"""### Task {tnum}: {ch} 批次 {n} 译文入库（{len(ids)} 条，约 {batch["jp_chars"]} 日文字）

**Files:**
- Produces: `{p["ctx"]}/batch_{n}/{{context.md,source.jsonl,manifest.json}}`（Step 1）、`{p["out"]}/batch_{n}.draft.jsonl`（Step 2 产出、Step 3 校验）、`{p["forward"]}` 追加本批 {len(ids)} 行（Step 4）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 {n} 批（`lane={batch["lane"]} chapter={ch}`，{len(ids)} 条 id）
- Produces: `{p["forward"]}` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python tools/build_context.py --batch {n} --profile cc --baseline {baseline}{p["repo_arg"]}`
Expected: 生成 `{p["ctx"]}/batch_{n}/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step 4 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 {n}，并按本计划头部「车道配置」注入车道根），产出 `{p["out"]}/batch_{n}.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `{p["env"]}uv run python tools/check_batch.py --batch {n}`
Expected: `batch_{n}: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `{p["out"]}/batch_{n}.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。

- [ ] **Step 4: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`{p["env"]}uv run python tools/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v {glossary_v}`

```bash
git add {p["forward"]}
git commit -m "data: {ch} 批次{n} 译文入线"
```"""
```

**改** `_checkpoint_task(tnum, first, last, chapter)` → 增加第五个参数 `p`，把正文里的 `data/notes/{chapter}.md` 换成 `{p["notes"]}/{chapter}.md`，并把「采纳的词条走新一版 glossary…」整句替换为：「试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。」

**改** `_final_task(tnum, chapter, lane, first, last, count)` → 签名加 `p`，正文里的 `data/forward.jsonl` 换成 `{p["forward"]}`。

**改** `render` 与 `main`：

```python
def render(sel, label, lane, every=5, baseline="none", glossary_v=GLOSSARY_V,
           lane_cfg=None) -> str:
    p = _paths(lane_cfg)
    parts = [_header(label, lane, every, len(sel), glossary_v, lane_cfg)]
    if not sel:
        parts.append(f"（`data/batches.jsonl` 中没有选中的批次，无事可做。）")
        return "\n\n".join(parts)
    tnum = 1
    chunk = []
    for b in sel:
        parts.append(_batch_task(tnum, b, baseline, glossary_v, p))
        tnum += 1
        chunk.append(b["batch"])
        if len(chunk) == every:
            parts.append(_checkpoint_task(tnum, chunk[0], chunk[-1], label, p))
            tnum += 1
            chunk = []
    parts.append(_final_task(tnum, label, lane, sel[0]["batch"], sel[-1]["batch"],
                             len(sel), p))
    return "\n\n".join(parts)


def _parse_range(s):
    m = __import__("re").fullmatch(r"(\d+)-(\d+)", s.strip())
    if not m:
        raise SystemExit(f"--batches 需形如 1-35，收到 {s!r}")
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo > hi:
        raise SystemExit(f"--batches 区间下界大于上界：{s!r}")
    return lo, hi


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--chapter")
    g.add_argument("--batches", help="连续段批号闭区间，形如 1-35")
    ap.add_argument("--label", help="--batches 模式下的计划名（必填）")
    ap.add_argument("--checkpoint-every", type=int, default=5)
    ap.add_argument("--lane-dir")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--append-model-id")
    args = ap.parse_args(argv)

    lane_params = [args.lane_dir, args.model, args.effort, args.append_model_id]
    if any(lane_params) and not all(lane_params):
        raise SystemExit("--lane-dir/--model/--effort/--append-model-id 要么全给要么全不给")
    lane_cfg = None if not all(lane_params) else {
        "lane": Path(args.lane_dir).name, "lane_dir": args.lane_dir,
        "model": args.model, "effort": args.effort,
        "append_model_id": args.append_model_id}

    if args.batches:
        if not args.label:
            raise SystemExit("--batches 模式必须同时给 --label")
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=args.lane,
                     batch_range=_parse_range(args.batches))
        label = args.label
    else:
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=args.lane,
                     chapter=args.chapter)
        label = args.chapter

    md = render(sel, label=label, lane=args.lane, every=args.checkpoint_every,
                glossary_v=glossary_version(REPO), lane_cfg=lane_cfg)
    out_path = REPO / "docs" / "superpowers" / "plans" / f"translate-{label}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"{out_path}: {md.count('### Task')} 个任务")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gen_plan.py -v`
Expected: 全部 PASS（12 例）。

- [ ] **Step 5: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿，无其他测试因签名变更而破。

- [ ] **Step 6: Commit**

```bash
git add tools/gen_plan.py tests/test_gen_plan.py
git commit -m "feat: gen_plan 选批渲染分离，新增连续段模式与车道感知"
```

---

### Task 4: `translator_cc.md` 路径基准节与隔离纪律

**Files:**
- Modify: `prompts/translator_cc.md`

**Interfaces:**
- Consumes: Task 3 生成的计划头部「车道配置」表（提供车道根一个值）。
- Produces: 子代理读到的路径规则——派发 prompt 此后只需给出车道根，不必再贴整张路径覆盖表。

- [ ] **Step 1: 插入「路径基准」节**

在 `prompts/translator_cc.md` 的「你是谁」节**之前**（紧接文件开头的两条引言之后）插入：

```markdown
## 路径基准（先读这节，它决定下文所有路径怎么解释）

本文件中所有**产出路径与译文线路径**——`work/ctx/batch_N/`、`work/out/batch_N.draft.jsonl`、`data/forward.jsonl`、`data/notes/<chapter>.md`、`glossary/`、`skeleton/`——都以派发方注入的**车道根**为基准：

- 派发时**给了车道根**（形如 `work/lanes/opus`）：上述路径一律加该前缀，例如 `work/lanes/opus/work/ctx/batch_N/`、`work/lanes/opus/data/forward.jsonl`。校验与入库命令要带环境变量前缀 `ZND_WORK=<车道根>/work ZND_DATA=<车道根>/data`，`build_context.py` 要带 `--repo <车道根>`。
- 派发时**没给车道根**：全部按仓库相对路径解释，即本文件字面所写。

以下路径**恒为仓库根**，任何情况下都不加车道前缀：`CLAUDE.md`、`prompts/`、`analysis/text_digest/`、`png/`、`tools/`。
```

- [ ] **Step 2: 更新「开工前：读三件材料」对第四节的描述**

Task 2 已把 context 第四节改名为「术语、风格与角色口调」并在尾部内嵌 `glossary/voices/` 全部 7 份口调表。把 `prompts/translator_cc.md` 中描述该节的那一行（现为「四、术语与风格：`glossary/active.json`（现行定译词表）+ `glossary/style.md` 全文——**style.md 已经整篇内嵌在这里，不用你再单独去开那个文件**。」）替换为：

```markdown
   - 四、术语、风格与角色口调：`glossary/active.json`（现行定译词表）+ `glossary/style.md` 全文 + `glossary/voices/` 全部 7 份角色口调表全文（直哉 / 彩野现实层 / アヤノ故事层 / ユウイチ / 由加里・ユカリ / サクラ / 千秋）——**三者都已整篇内嵌在这里，不用你再单独去开那些文件**。口调表给的是各角色的自称、称呼、口癖、句尾、语域与例句：`prompts/reviewer_cc.md` 的评审者正是按这些表判「口调表偏离」，你据同一份标准落笔。
```

同时把描述第三节的那一行里的「`skeleton/anchors.yaml` 全文」改为「`skeleton/anchors.yaml` 的 id/日/中紧凑对照（`recall` 等维护者注释已省略）」——其余措辞（"本批 source 里任何一个 id，只要出现在这一节的锚点列表里，zh 必须逐字沿用给定译文"）保持不变。

- [ ] **Step 3: 在「不要做的事」节追加隔离纪律**

在 `prompts/translator_cc.md` 的「## 不要做的事」节末尾追加两条：

```markdown
- **不要窥探其他车道**。P2 试点期间有两条并行车道在翻同一批文本用于人工对照：禁止读取、列出或以任何方式访问 `work/lanes/` 下除本车道以外的任何目录，也不要读仓库根的 `data/forward.jsonl`。看到别人的译法会污染对照结论，这比译错一句严重得多——违反即本批作废重跑。
- **不要裁决术语**。试点期间术语表冻结：提案照常追加到 `data/notes/<chapter>.md`（按上文「路径基准」加车道前缀），但不要新增 `glossary.vN.yaml`、不要改 `glossary/active.json`，裁决一律推迟到试点结束。
```

- [ ] **Step 4: 校验改动落地**

Run:

```bash
grep -c '路径基准' prompts/translator_cc.md
grep -c '不要窥探其他车道' prompts/translator_cc.md
```

Expected: 两条命令均输出 ≥1。再通读该文件「术语提案」节，确认它与新增的「不要裁决术语」条目不矛盾（前者说"留给术语委员会在下一次 glossary 版本升级时裁决"，与试点期冻结一致，无需改动）。

- [ ] **Step 5: Commit**

```bash
git add prompts/translator_cc.md
git commit -m "docs: 译者模板新增路径基准节与试点隔离纪律"
```

---

### Task 5: `tools/lane_setup.py` 车道搭建与冻结校验

**Files:**
- Create: `tools/lane_setup.py`
- Test: `tests/test_lane_setup.py`

**Interfaces:**
- Produces：
  - `setup(lane, model, effort, append_model_id, repo=REPO, lanes_root=None) -> Path`——建车道目录并返回其路径。只读数据文件用**符号链接**，`skeleton/` 与 `glossary/` 用**拷贝**（冻结）。写 `<lane_dir>/lane.json`。
  - `freeze_hashes(lane_dir, repo) -> dict`——返回 `{"batches": sha, "cards_zh": sha, "anchors": sha, "active": sha, "glossary_vN": sha}`。
  - `verify(lanes_root, repo) -> list[str]`——比对 `pilot-manifest.json` 与当前实际哈希，返回漂移描述列表（空列表＝无漂移）。
  - CLI：`--lane <name> --model <m> --effort <e> --append-model-id <id>` 建车道；`--verify` 校验全部车道，有漂移则退出码 1。

- [ ] **Step 1: Write the failing test**

创建 `tests/test_lane_setup.py`：

```python
import json
import pytest
from tools.lane_setup import setup, freeze_hashes, record, verify, main


def _repo(tmp_path):
    """替身仓库：只读数据 + skeleton/ + glossary/。"""
    d = tmp_path / "repo"
    (d / "data").mkdir(parents=True)
    (d / "skeleton").mkdir()
    (d / "glossary").mkdir()
    for name in ("ledger.jsonl", "ledger_extra.jsonl", "timeline.jsonl",
                 "batches.jsonl", "dag.json", "scene2card.json"):
        (d / "data" / name).write_text("{}\n", encoding="utf-8")
    (d / "skeleton" / "cards.zh.yaml").write_text("- {card: 1}\n", encoding="utf-8")
    (d / "skeleton" / "anchors.yaml").write_text("- {chapter: g, items: []}\n",
                                                 encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{"a":"啊"}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (d / "glossary" / "glossary.v6.yaml").write_text("version: 6", encoding="utf-8")
    return d


def test_setup_symlinks_data_and_copies_frozen_assets(tmp_path):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    assert (lane_dir / "data" / "ledger.jsonl").is_symlink(), "只读数据须为符号链接"
    assert (lane_dir / "data" / "timeline.jsonl").is_symlink()
    assert not (lane_dir / "skeleton" / "cards.zh.yaml").is_symlink(), \
        "skeleton 须为拷贝（冻结），不能是符号链接"
    assert not (lane_dir / "glossary" / "active.json").is_symlink(), \
        "glossary 须为拷贝（冻结），不能是符号链接"
    assert (lane_dir / "glossary" / "glossary.v6.yaml").exists()


def test_setup_writes_lane_config(tmp_path):
    repo = _repo(tmp_path)
    lane_dir = setup("fable", "fable", "high", "claude-fable-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    cfg = json.loads((lane_dir / "lane.json").read_text(encoding="utf-8"))
    assert cfg == {"lane": "fable", "lane_dir": str(lane_dir), "model": "fable",
                   "effort": "high", "append_model_id": "claude-fable-5"}


def test_setup_creates_no_forward_file(tmp_path):
    """车道的 forward.jsonl 由 append_forward 首次写入，setup 不得预建——
    预建空文件会让 build_context 把它当"已存在但无译文"，掩盖前缀空洞。"""
    repo = _repo(tmp_path)
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    assert not (lane_dir / "data" / "forward.jsonl").exists()


def test_freeze_hashes_covers_the_frozen_set(tmp_path):
    repo = _repo(tmp_path)
    lane_dir = setup("opus", "opus", "max", "claude-opus-5", repo=repo,
                     lanes_root=tmp_path / "lanes")
    h = freeze_hashes(lane_dir, repo)
    assert set(h) == {"batches", "cards_zh", "anchors", "active", "glossary_max"}
    assert all(isinstance(v, str) and len(v) == 64 for v in h.values())


def test_verify_detects_drift_in_copied_glossary(tmp_path):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)          # verify 比对的是 record() 落下的基准，必须先记
    assert verify(lanes, repo) == []
    (lanes / "opus" / "glossary" / "active.json").write_text('{"a":"改了"}',
                                                             encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift and any("active" in d for d in drift)


def test_verify_detects_drift_in_repo_batches(tmp_path):
    """batches.jsonl 被重切 → 两条车道的批号语义不再一致，必须拦下。"""
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    setup("opus", "opus", "max", "claude-opus-5", repo=repo, lanes_root=lanes)
    record(lanes, repo)
    (repo / "data" / "batches.jsonl").write_text('{"batch":1}\n', encoding="utf-8")
    drift = verify(lanes, repo)
    assert drift and any("batches" in d for d in drift)


def test_main_verify_exits_nonzero_on_drift(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    lanes = tmp_path / "lanes"
    monkeypatch.setattr("tools.lane_setup.REPO", repo)
    monkeypatch.setattr("tools.lane_setup.LANES_ROOT", lanes)
    assert main(["--lane", "opus", "--model", "opus", "--effort", "max",
                 "--append-model-id", "claude-opus-5"]) == 0
    assert main(["--verify"]) == 0
    (lanes / "opus" / "skeleton" / "cards.zh.yaml").write_text("- {card: 2}\n",
                                                              encoding="utf-8")
    assert main(["--verify"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lane_setup.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'tools.lane_setup'`。

- [ ] **Step 3: Write minimal implementation**

创建 `tools/lane_setup.py`：

```python
"""P2 试点车道搭建与冻结校验。

车道＝一份独立的译文线 + 一份冻结的骨架/术语快照：只读数据用符号链接（同源、
省空间），skeleton/ 与 glossary/ 用拷贝（拷贝即冻结，杜绝试点中途仓库侧升版
泄漏进任一车道）。spec：docs/superpowers/specs/2026-07-31-p2-pilot-design.md §3。
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, WORK, dumps, sha256_file

LANES_ROOT = WORK / "lanes"

# 只读数据：符号链接。forward.jsonl / patches.jsonl 不在此列——它们是车道私有的
# 译文线，由 append_forward 首次写入（预建空文件会掩盖前缀空洞）。
LINKED_DATA = ("ledger.jsonl", "ledger_extra.jsonl", "timeline.jsonl",
               "batches.jsonl", "dag.json", "scene2card.json")
# 冻结快照：整目录拷贝。
COPIED_DIRS = ("skeleton", "glossary")


def _glossary_max_path(root: Path) -> Path:
    """glossary/ 下版本号最大的 glossary.vN.yaml。"""
    import re
    cands = [(int(re.search(r"v(\d+)", p.stem).group(1)), p)
             for p in (root / "glossary").glob("glossary.v*.yaml")]
    if not cands:
        raise FileNotFoundError(f"{root}/glossary 下没有 glossary.v*.yaml")
    return max(cands)[1]


def setup(lane, model, effort, append_model_id, repo=None, lanes_root=None) -> Path:
    repo = Path(repo or REPO)
    lanes_root = Path(lanes_root or LANES_ROOT)
    lane_dir = lanes_root / lane
    (lane_dir / "data").mkdir(parents=True, exist_ok=True)
    for name in LINKED_DATA:
        src, dst = (repo / "data" / name).resolve(), lane_dir / "data" / name
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to(src)
    for d in COPIED_DIRS:
        dst = lane_dir / d
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(repo / d, dst)
    (lane_dir / "work").mkdir(exist_ok=True)
    (lane_dir / "lane.json").write_text(dumps({
        "lane": lane, "lane_dir": str(lane_dir), "model": model,
        "effort": effort, "append_model_id": append_model_id}), encoding="utf-8")
    return lane_dir


def freeze_hashes(lane_dir, repo=None) -> dict:
    """冻结集的哈希：batches 取仓库侧（两条车道共享同一份批次规划），
    其余四项取车道内的拷贝（各车道各自冻结，理应彼此相同）。"""
    repo, lane_dir = Path(repo or REPO), Path(lane_dir)
    return {
        "batches": sha256_file(repo / "data" / "batches.jsonl"),
        "cards_zh": sha256_file(lane_dir / "skeleton" / "cards.zh.yaml"),
        "anchors": sha256_file(lane_dir / "skeleton" / "anchors.yaml"),
        "active": sha256_file(lane_dir / "glossary" / "active.json"),
        "glossary_max": sha256_file(_glossary_max_path(lane_dir)),
    }


def _manifest_path(lanes_root) -> Path:
    return Path(lanes_root) / "pilot-manifest.json"


def record(lanes_root=None, repo=None) -> dict:
    """扫描 lanes_root 下全部车道，写 pilot-manifest.json 并返回其内容。"""
    lanes_root = Path(lanes_root or LANES_ROOT)
    lanes = {p.name: freeze_hashes(p, repo)
             for p in sorted(lanes_root.iterdir())
             if p.is_dir() and (p / "lane.json").exists()}
    _manifest_path(lanes_root).write_text(dumps({"lanes": lanes}), encoding="utf-8")
    return lanes


def verify(lanes_root=None, repo=None) -> list:
    """比对已记录的冻结哈希与当前实际值，返回漂移描述（空列表＝无漂移）。"""
    lanes_root = Path(lanes_root or LANES_ROOT)
    mp = _manifest_path(lanes_root)
    if not mp.exists():
        return ["pilot-manifest.json 不存在——尚未记录冻结哈希"]
    recorded = json.loads(mp.read_text(encoding="utf-8"))["lanes"]
    drift = []
    for lane, want in recorded.items():
        got = freeze_hashes(lanes_root / lane, repo)
        for k, v in want.items():
            if got.get(k) != v:
                drift.append(f"{lane}: {k} 漂移（记录 {v[:12]}… 实际 {got.get(k, '缺失')[:12]}…）")
    return drift


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--append-model-id")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    if a.verify:
        drift = verify(LANES_ROOT, REPO)
        if drift:
            for d in drift:
                print(d)
            return 1
        print("冻结校验：无漂移")
        return 0
    if not all([a.lane, a.model, a.effort, a.append_model_id]):
        raise SystemExit("建车道需同时给 --lane/--model/--effort/--append-model-id")
    lane_dir = setup(a.lane, a.model, a.effort, a.append_model_id, REPO, LANES_ROOT)
    record(LANES_ROOT, REPO)
    print(f"{lane_dir}: 车道就绪，冻结哈希已记入 {_manifest_path(LANES_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_lane_setup.py -v`
Expected: 7 passed。

- [ ] **Step 5: Commit**

```bash
git add tools/lane_setup.py tests/test_lane_setup.py
git commit -m "feat: 车道搭建与冻结校验工具"
```

---

### Task 6: `tools/detect_collapse.py` 语义崩溃探测

**Files:**
- Create: `tools/detect_collapse.py`
- Test: `tests/test_detect_collapse.py`

**Interfaces:**
- Consumes: 批次的 `source.jsonl`（`{"id","jp"}`）与 `draft.jsonl`（`{"id","zh"}`）；车道的 `glossary/glossary.vN.yaml`（推导保留片假名人名白名单）。
- Produces：
  - `retained_names(glossary_yaml_path) -> set[str]`——术语表 `characters` 中 `zh == jp` 且含假名的条目（即"原样保留的片假名人名"）。
  - `scan(source_rows, draft_rows, names=(), kana_max=KANA_MAX, ratio_lo=RATIO_LO, ratio_hi=RATIO_HI) -> list[dict]`——每项 `{"id", "rule": "C1"|"C2"|"C3", "msg"}`。
  - CLI：`--batch N [--lane-dir D] [--kana-max/--ratio-lo/--ratio-hi]` → 写 `<work>/out/batch_N.collapse.json`，打印计数，**恒返回 0**（顾问性质，不阻断流水线）。

**阈值默认值的来源（实测，不是拍脑袋）**：对 `skeleton/anchors.yaml` 120 条已定稿日中对照与 `cards.jp/zh` 194 对卡面正文测得——zh/jp 字符比锚点为 0.48–1.20（中位 0.85）、卡面 p5 0.62–p95 1.00；剔除保留片假名人名后的残留假名比**最大值为 0.0000**。故取 `RATIO_LO=0.40`、`RATIO_HI=1.50`（宽于全部已定稿样本，不误伤好译文）、`KANA_MAX=0.02`（定稿实测为 0，留 2% 余量）。这些是**试点初值**，batch 1–2 硬停时用真实译文重新标定并记入试点记录。

- [ ] **Step 1: Write the failing test**

创建 `tests/test_detect_collapse.py`：

```python
import json
import pytest
from tools.detect_collapse import scan, retained_names, main


def test_untranslated_line_is_flagged_by_kana_ratio():
    """整行原文照抄：长度比正常（1.0，落在 C2 阈值内），只能靠假名比抓住。"""
    src = [{"id": 1, "jp": "彼女は静かに笑った。"}]
    drf = [{"id": 1, "zh": "彼女は静かに笑った。"}]
    hits = scan(src, drf)
    assert any(h["rule"] == "C1" and h["id"] == 1 for h in hits)


def test_retained_katakana_names_do_not_trigger_kana_rule():
    src = [{"id": 2, "jp": "【アヤノ】「ユウイチ、おはよう」"}]
    drf = [{"id": 2, "zh": "【アヤノ】「ユウイチ，早上好」"}]
    hits = scan(src, drf, names={"アヤノ", "ユウイチ"})
    assert not any(h["rule"] == "C1" for h in hits)


def test_ratio_outliers_are_flagged():
    src = [{"id": 3, "jp": "あ" * 100}, {"id": 4, "jp": "あ" * 10}]
    drf = [{"id": 3, "zh": "短"},                    # 比 0.01，过短
           {"id": 4, "zh": "长" * 40}]               # 比 4.0，过长
    hits = scan(src, drf)
    assert {h["id"] for h in hits if h["rule"] == "C2"} == {3, 4}


def test_normal_ratio_is_not_flagged():
    """已定稿译文的实测比区间 0.48–1.20 必须全部放行。"""
    src = [{"id": 5, "jp": "あ" * 100}]
    for zh_len in (48, 85, 120):
        drf = [{"id": 5, "zh": "中" * zh_len}]
        assert not [h for h in scan(src, drf) if h["rule"] == "C2"], \
            f"比 {zh_len/100} 是已定稿样本内的正常值，不该告警"


def test_repeated_substring_loop_is_flagged():
    src = [{"id": 6, "jp": "彼は歩いた。"}]
    drf = [{"id": 6, "zh": "他走着走走着走走着走走着走"}]
    hits = scan(src, drf)
    assert any(h["rule"] == "C3" and h["id"] == 6 for h in hits)


def test_duplicated_lines_across_batch_are_flagged():
    src = [{"id": i, "jp": f"原文{i}あああああ"} for i in (7, 8, 9)]
    drf = [{"id": i, "zh": "完全相同的一整句译文内容"} for i in (7, 8, 9)]
    hits = scan(src, drf)
    assert len([h for h in hits if h["rule"] == "C3"]) >= 3


def test_clean_batch_yields_nothing():
    src = [{"id": 10, "jp": "遠くから『帰りの歌』が聞こえてきた。"}]
    drf = [{"id": 10, "zh": "远处传来了『回家的歌谣』。"}]
    assert scan(src, drf) == []


def test_retained_names_reads_glossary_characters(tmp_path):
    g = tmp_path / "glossary.v6.yaml"
    g.write_text(
        "characters:\n"
        "  - {jp: アヤノ, zh: アヤノ, layer: story}\n"
        "  - {jp: ユウイチ, zh: ユウイチ, layer: both}\n"
        "  - {jp: きくちゃん, zh: 小菊, layer: real}\n"
        "  - {jp: 直哉, zh: 直哉, layer: real}\n", encoding="utf-8")
    assert retained_names(g) == {"アヤノ", "ユウイチ"}


def test_main_writes_report_and_always_returns_zero(tmp_path, monkeypatch):
    import tools.detect_collapse as dc
    work = tmp_path / "work"
    (work / "ctx" / "batch_1").mkdir(parents=True)
    (work / "out").mkdir(parents=True)
    (work / "ctx" / "batch_1" / "source.jsonl").write_text(
        json.dumps({"id": 1, "jp": "彼女は静かに笑った。"}, ensure_ascii=False),
        encoding="utf-8")
    (work / "out" / "batch_1.draft.jsonl").write_text(
        json.dumps({"id": 1, "zh": "彼女は静かに笑った。"}, ensure_ascii=False),
        encoding="utf-8")
    (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "glossary.v6.yaml").write_text("characters: []",
                                                            encoding="utf-8")
    monkeypatch.setattr(dc, "WORK", work)
    monkeypatch.setattr(dc, "REPO", tmp_path)
    assert main(["--batch", "1"]) == 0
    rep = json.loads((work / "out" / "batch_1.collapse.json").read_text(
        encoding="utf-8"))
    assert any(h["rule"] == "C1" for h in rep)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_detect_collapse.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'tools.detect_collapse'`。

- [ ] **Step 3: Write minimal implementation**

创建 `tools/detect_collapse.py`：

```python
"""语义崩溃探测：check_batch 只管结构，拦不住"结构合法但语义垮掉"的批次，
而那种批次会成为后续所有批次的可信前缀。三条顾问级规则（不阻断流水线）：

  C1 残留假名——译文里出现（剔除术语表规定原样保留的片假名人名后的）假名，
     典型成因是整行原文照抄；这类行的长度比恰好正常，只有本规则抓得住。
  C2 中日长度比离群——译文相对原文过短/过长。
  C3 复读循环——行内子串连续重复，或同一句译文在批内重复出现。

阈值初值由已定稿语料实测得出（见 spec §6.3 与本文件常量注释），batch 1–2
硬停时用真实译文重新标定。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, WORK, dumps, read_jsonl

KANA_RE = re.compile(r"[぀-ゟ゠-ヿ]")
# 行内连续重复：长度≥6 的子串连续出现≥3 次
LOOP_RE = re.compile(r"(.{6,}?)\1{2,}")

# 实测依据（skeleton/anchors.yaml 120 对 + cards.jp/zh 194 对已定稿语料）：
# zh/jp 字符比锚点 0.48–1.20（中位 0.85）、卡面 p5 0.62–p95 1.00 → 阈值取更宽的
# [0.40, 1.50]，保证已定稿水准的译文零误报；残留假名比定稿实测最大 0.0000 →
# 取 0.02 留余量。试点 batch 1–2 硬停时重新标定。
RATIO_LO = 0.40
RATIO_HI = 1.50
KANA_MAX = 0.02
# 批内完全相同且长度≥8 的译文出现≥3 次即视为复读
DUP_MIN_LEN = 8
DUP_MIN_COUNT = 3


def retained_names(glossary_path) -> set:
    """术语表 characters 中「原样保留」（zh == jp）且含假名的条目——这些假名
    是合法的，计算残留假名比前必须先剔除。"""
    import yaml
    doc = yaml.safe_load(Path(glossary_path).read_text(encoding="utf-8")) or {}
    return {c["jp"] for c in (doc.get("characters") or [])
            if c.get("zh") == c.get("jp") and KANA_RE.search(c.get("jp", ""))}


def _kana_ratio(zh: str, names) -> float:
    s = zh
    for n in sorted(names, key=len, reverse=True):
        s = s.replace(n, "")
    return len(KANA_RE.findall(s)) / max(len(zh), 1)


def scan(source_rows, draft_rows, names=(), kana_max=KANA_MAX,
         ratio_lo=RATIO_LO, ratio_hi=RATIO_HI) -> list:
    src = {r["id"]: r["jp"] for r in source_rows}
    hits = []
    zh_counts = Counter(r["zh"] for r in draft_rows
                        if len(r["zh"]) >= DUP_MIN_LEN)
    for r in draft_rows:
        i, zh = r["id"], r["zh"]
        jp = src.get(i)
        if jp is None:
            continue
        kr = _kana_ratio(zh, names)
        if kr > kana_max:
            hits.append({"id": i, "rule": "C1",
                         "msg": f"残留假名比 {kr:.3f} > {kana_max}（疑似原文未译）"})
        ratio = len(zh) / max(len(jp), 1)
        if not (ratio_lo <= ratio <= ratio_hi):
            hits.append({"id": i, "rule": "C2",
                         "msg": f"中日长度比 {ratio:.2f} 越界 [{ratio_lo}, {ratio_hi}]"})
        if LOOP_RE.search(zh):
            hits.append({"id": i, "rule": "C3", "msg": "行内子串连续重复≥3 次"})
        elif zh_counts[zh] >= DUP_MIN_COUNT:
            hits.append({"id": i, "rule": "C3",
                         "msg": f"同一句译文在批内出现 {zh_counts[zh]} 次"})
    return hits


def _glossary_max(root: Path) -> Path:
    cands = [(int(re.search(r"v(\d+)", p.stem).group(1)), p)
             for p in (root / "glossary").glob("glossary.v*.yaml")]
    return max(cands)[1]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--lane-dir", default=None,
                    help="车道根；省略时用 pipelib.WORK 与仓库 glossary/")
    ap.add_argument("--kana-max", type=float, default=KANA_MAX)
    ap.add_argument("--ratio-lo", type=float, default=RATIO_LO)
    ap.add_argument("--ratio-hi", type=float, default=RATIO_HI)
    a = ap.parse_args(argv)
    work = Path(a.lane_dir) / "work" if a.lane_dir else Path(WORK)
    groot = Path(a.lane_dir) if a.lane_dir else Path(REPO)
    src = read_jsonl(work / "ctx" / f"batch_{a.batch}" / "source.jsonl")
    drf = read_jsonl(work / "out" / f"batch_{a.batch}.draft.jsonl")
    hits = scan(src, drf, names=retained_names(_glossary_max(groot)),
                kana_max=a.kana_max, ratio_lo=a.ratio_lo, ratio_hi=a.ratio_hi)
    out = work / "out" / f"batch_{a.batch}.collapse.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(hits), encoding="utf-8")
    by_rule = Counter(h["rule"] for h in hits)
    print(f"batch_{a.batch}: 崩溃探测 {len(hits)} 条 "
          f"(C1={by_rule['C1']} C2={by_rule['C2']} C3={by_rule['C3']}) → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_detect_collapse.py -v`
Expected: 9 passed。

- [ ] **Step 5: 真实语料零误报验证**

Run:

```bash
uv run python - <<'EOF'
import sys, yaml; sys.path.insert(0, ".")
from tools.detect_collapse import scan, retained_names
names = retained_names("glossary/glossary.v6.yaml")
anc = [it for g in yaml.safe_load(open("skeleton/anchors.yaml", encoding="utf-8"))
       for it in g["items"]]
src = [{"id": it["id"], "jp": it["jp"]} for it in anc]
drf = [{"id": it["id"], "zh": it["zh"]} for it in anc]
hits = scan(src, drf, names=names)
print(f"保留人名 {len(names)} 个；120 条已定稿锚点的告警数：{len(hits)}")
for h in hits[:10]:
    print("  ", h)
EOF
```

Expected: 告警数应为 **0**。若非 0，逐条判断是阈值过严（调常量并在本步记录新值与依据）还是规则实现有误（修实现）——**不要**为了归零而放宽到掩盖真实缺陷的程度。

- [ ] **Step 6: Commit**

```bash
git add tools/detect_collapse.py tests/test_detect_collapse.py
git commit -m "feat: 语义崩溃探测（残留假名/长度比离群/复读循环）"
```

---

### Task 7: `tools/compare_lanes.py` 分层统计与对照材料

**Files:**
- Create: `tools/compare_lanes.py`
- Test: `tests/test_compare_lanes.py`

**Interfaces:**
- Consumes: 两条车道的 `data/forward.jsonl`；仓库 `data/ledger.jsonl`、`data/timeline.jsonl`、`skeleton/anchors.yaml`、`skeleton/cards.zh.yaml`。
- Produces：
  - `anchor_ids(anchors_path) -> set[int]`
  - `anchor_compliance(forward_rows, anchors) -> dict`——`{"total", "verbatim", "rate", "violations": [id…]}`，`anchors` 为 `{id: zh}`。
  - `divergence(zh_a, zh_b, exclude_ids) -> dict`——`{"compared", "differing", "rate", "ids": [...]}`；`zh_a/zh_b` 为 `{id: zh}`。
  - `blind_pairs(ids, zh_a, zh_b, ledger, lane_a, lane_b) -> (list[dict], dict)`——返回并排材料与揭示用的 key；每项 `{"id","jp","甲","乙"}`，甲/乙 与车道的对应**按 id 奇偶交替**（消除位置锚定），key 为 `{"odd_id_甲": lane_a, "even_id_甲": lane_b}`。
  - `stratified_sample(ids, timeline, per_kind)`——按 timeline 单元类型分层取样，每类取前 `per_kind` 个 id（确定性，按 id 升序）。
  - CLI：`--lane-a <dir> --lane-b <dir> [--per-kind 20] [--out work/compare]` → 写 `summary.json`、`blind.md`、`blind-key.json`。

- [ ] **Step 1: Write the failing test**

创建 `tests/test_compare_lanes.py`：

```python
import json
from tools.compare_lanes import (anchor_compliance, divergence, blind_pairs,
                                 stratified_sample, main)


def test_anchor_compliance_counts_verbatim_reuse():
    anchors = {1: "定译一", 2: "定译二"}
    fwd = [{"id": 1, "zh": "定译一"}, {"id": 2, "zh": "我自己重译的"}]
    r = anchor_compliance(fwd, anchors)
    assert r["total"] == 2 and r["verbatim"] == 1
    assert r["rate"] == 0.5 and r["violations"] == [2]


def test_divergence_excludes_anchor_ids():
    """锚点行两模型必然同串，混进区分度统计会制造"两模型很接近"的假阳性。"""
    zh_a = {1: "同", 2: "甲说法", 3: "同样"}
    zh_b = {1: "同", 2: "乙说法", 3: "同样"}
    r = divergence(zh_a, zh_b, exclude_ids={1, 3})
    assert r["compared"] == 1 and r["differing"] == 1 and r["rate"] == 1.0


def test_divergence_only_counts_ids_present_in_both():
    zh_a = {1: "甲", 2: "甲二"}
    zh_b = {1: "乙"}
    r = divergence(zh_a, zh_b, exclude_ids=set())
    assert r["compared"] == 1


def test_blind_pairs_alternate_lane_positions_by_id_parity():
    """位置锚定消除：奇数 id 甲=A，偶数 id 甲=B。"""
    ledger = {1: "原文一", 2: "原文二"}
    zh_a, zh_b = {1: "A译一", 2: "A译二"}, {1: "B译一", 2: "B译二"}
    pairs, key = blind_pairs([1, 2], zh_a, zh_b, ledger, "opus", "fable")
    p1 = next(p for p in pairs if p["id"] == 1)
    p2 = next(p for p in pairs if p["id"] == 2)
    assert p1["甲"] == "A译一" and p1["乙"] == "B译一"
    assert p2["甲"] == "B译二" and p2["乙"] == "A译二"
    assert key == {"odd_id_甲": "opus", "even_id_甲": "fable"}


def test_blind_pairs_carry_source_text():
    ledger = {1: "原文一"}
    pairs, _ = blind_pairs([1], {1: "a"}, {1: "b"}, ledger, "x", "y")
    assert pairs[0]["jp"] == "原文一"


def test_stratified_sample_covers_every_unit_kind():
    timeline = [
        {"type": "unit", "unit_kind": "scene", "ids": [1, 2, 3]},
        {"type": "unit", "unit_kind": "card", "ids": [4, 5]},
        {"type": "marker", "text": "x"},
        {"type": "unit", "unit_kind": "script", "ids": [6]},
    ]
    s = stratified_sample([1, 2, 3, 4, 5, 6], timeline, per_kind=2)
    assert set(s) == {1, 2, 4, 5, 6}, "每类取前 2 个，script 只有 1 个也要取到"


def test_main_writes_summary_and_blind_material(tmp_path, monkeypatch):
    import tools.compare_lanes as cl
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir()
    (repo / "data" / "ledger.jsonl").write_text("\n".join(
        json.dumps({"id": i, "jp": f"原文{i}", "chapter": "s0f", "kind": "narrative",
                    "file": "f", "func": "g", "voice": "NONVOICE", "literal": True},
                   ensure_ascii=False) for i in (1, 2, 3)), encoding="utf-8")
    (repo / "data" / "timeline.jsonl").write_text(json.dumps(
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "f", "state": None,
         "title": "一", "ids": [1, 2, 3]}, ensure_ascii=False), encoding="utf-8")
    (repo / "skeleton" / "anchors.yaml").write_text(
        "- chapter: global\n  items:\n    - {id: 1, jp: 原文1, zh: 定译一, recall: x}\n",
        encoding="utf-8")
    for lane, zh in (("opus", "甲译"), ("fable", "乙译")):
        d = tmp_path / "lanes" / lane / "data"
        d.mkdir(parents=True)
        d.joinpath("forward.jsonl").write_text("\n".join(
            json.dumps({"id": i, "zh": ("定译一" if i == 1 else f"{zh}{i}"),
                        "batch": 1, "backend": "cc", "model": "m", "ctx": "c",
                        "glossary_v": 6, "ts": "t"}, ensure_ascii=False)
            for i in (1, 2, 3)), encoding="utf-8")
    monkeypatch.setattr(cl, "REPO", repo)
    out = tmp_path / "compare"
    assert main(["--lane-a", str(tmp_path / "lanes" / "opus"),
                 "--lane-b", str(tmp_path / "lanes" / "fable"),
                 "--out", str(out)]) == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["anchor"]["opus"]["verbatim"] == 1
    assert summary["divergence"]["compared"] == 2, "锚点 id 1 必须被排除"
    assert (out / "blind.md").exists()
    key = json.loads((out / "blind-key.json").read_text(encoding="utf-8"))
    assert key["odd_id_甲"] == "opus"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_compare_lanes.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'tools.compare_lanes'`。

- [ ] **Step 3: Write minimal implementation**

创建 `tools/compare_lanes.py`：

```python
"""双车道对照材料生成：分层统计 + 盲评并排 + 卡面回译自检素材。

分层的要点（spec §6.1）：锚点覆盖行规定逐字沿用骨架定稿，两模型应当输出同一
字符串——把它们混进"模型区分度"统计会制造"两模型很接近"的假阳性，故必须单列
并从区分度里剔除。盲评的要点：甲/乙 与车道的对应按 id 奇偶交替，消除"总是排在
左边的那个更好"的位置锚定。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl


def anchor_ids(anchors_path) -> dict:
    """锚点表 → {id: zh}。"""
    import yaml
    groups = yaml.safe_load(Path(anchors_path).read_text(encoding="utf-8")) or []
    return {it["id"]: it["zh"] for g in groups for it in g["items"]}


def anchor_compliance(forward_rows, anchors) -> dict:
    zh = {r["id"]: r["zh"] for r in forward_rows}
    present = [i for i in anchors if i in zh]
    bad = [i for i in present if zh[i] != anchors[i]]
    return {"total": len(present), "verbatim": len(present) - len(bad),
            "rate": (len(present) - len(bad)) / len(present) if present else 0.0,
            "violations": sorted(bad)}


def divergence(zh_a, zh_b, exclude_ids) -> dict:
    common = [i for i in zh_a if i in zh_b and i not in exclude_ids]
    diff = [i for i in common if zh_a[i] != zh_b[i]]
    return {"compared": len(common), "differing": len(diff),
            "rate": len(diff) / len(common) if common else 0.0,
            "ids": sorted(diff)}


def blind_pairs(ids, zh_a, zh_b, ledger, lane_a, lane_b):
    """并排材料 + 揭示 key。甲/乙 与车道的对应按 id 奇偶交替。"""
    pairs = []
    for i in sorted(ids):
        if i not in zh_a or i not in zh_b:
            continue
        first, second = (zh_a[i], zh_b[i]) if i % 2 == 1 else (zh_b[i], zh_a[i])
        pairs.append({"id": i, "jp": ledger.get(i, ""), "甲": first, "乙": second})
    return pairs, {"odd_id_甲": lane_a, "even_id_甲": lane_b}


def stratified_sample(ids, timeline, per_kind=20):
    """按 timeline 单元类型分层，每类按 id 升序取前 per_kind 个。
    段内单元构成极不均衡（场景/卡面/整脚本…），不分层会过采样机械性最强、
    模型差异最小的那一类。"""
    id_kind = {}
    for row in timeline:
        if row.get("type") != "unit":
            continue
        for i in row.get("ids", []):
            id_kind.setdefault(i, row["unit_kind"])
    buckets = {}
    for i in sorted(ids):
        buckets.setdefault(id_kind.get(i, "unknown"), []).append(i)
    out = []
    for kind in sorted(buckets):
        out.extend(buckets[kind][:per_kind])
    return sorted(out)


def _render_blind(pairs) -> str:
    lines = ["# 盲评并排材料",
             "",
             "> 甲/乙 与车道的对应关系已隐去（见 blind-key.json）。**打完分再看 key。**",
             "> 三栏评分：中文可读性 / 术语与口调一致性 / 全知纪律（剧透与提前消歧）。",
             ""]
    for p in pairs:
        lines += [f"## id {p['id']}", "", f"- 原文：{p['jp']}", f"- 甲：{p['甲']}",
                  f"- 乙：{p['乙']}", ""]
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane-a", required=True)
    ap.add_argument("--lane-b", required=True)
    ap.add_argument("--per-kind", type=int, default=20)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    repo = Path(REPO)
    la, lb = Path(a.lane_a), Path(a.lane_b)
    out = Path(a.out) if a.out else repo / "work" / "compare"
    out.mkdir(parents=True, exist_ok=True)

    fa = read_jsonl(la / "data" / "forward.jsonl")
    fb = read_jsonl(lb / "data" / "forward.jsonl")
    zh_a = {r["id"]: r["zh"] for r in fa}
    zh_b = {r["id"]: r["zh"] for r in fb}
    anchors = anchor_ids(repo / "skeleton" / "anchors.yaml")
    ledger = {r["id"]: r["jp"] for r in read_jsonl(repo / "data" / "ledger.jsonl")}
    timeline = read_jsonl(repo / "data" / "timeline.jsonl")

    summary = {
        "anchor": {la.name: anchor_compliance(fa, anchors),
                   lb.name: anchor_compliance(fb, anchors)},
        "divergence": divergence(zh_a, zh_b, exclude_ids=set(anchors)),
    }
    (out / "summary.json").write_text(dumps(summary), encoding="utf-8")

    sample = stratified_sample(
        [i for i in zh_a if i in zh_b and i not in anchors], timeline, a.per_kind)
    pairs, key = blind_pairs(sample, zh_a, zh_b, ledger, la.name, lb.name)
    (out / "blind.md").write_text(_render_blind(pairs), encoding="utf-8")
    (out / "blind-key.json").write_text(dumps(key), encoding="utf-8")
    print(f"{out}: 锚点遵从 {la.name}={summary['anchor'][la.name]['rate']:.3f} "
          f"{lb.name}={summary['anchor'][lb.name]['rate']:.3f}；"
          f"区分度样本 {summary['divergence']['compared']} 行、"
          f"分歧率 {summary['divergence']['rate']:.3f}；盲评 {len(pairs)} 组")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_compare_lanes.py -v`
Expected: 7 passed。

- [ ] **Step 5: Commit**

```bash
git add tools/compare_lanes.py tests/test_compare_lanes.py
git commit -m "feat: 双车道分层统计与盲评对照材料生成"
```

---

### Task 8: 集成——实建两条车道、生成执行计划、batch 1 隔离验收

**Files:**
- 无源码改动；产出 `work/lanes/{opus,fable}/`、`work/lanes/pilot-manifest.json`、`docs/superpowers/plans/translate-pilot-{opus,fable}.md`

**Interfaces:**
- Consumes: Task 1–7 的全部产物。
- Produces: 可直接执行的两份逐批计划 + 通过隔离验收的车道环境。

- [ ] **Step 1: 全量测试与工装自检**

Run: `uv run pytest -q`
Expected: 全绿（Task 1–7 新增用例全部计入）。

- [ ] **Step 2: 实建两条车道**

```bash
uv run python tools/lane_setup.py --lane opus  --model opus  --effort max  --append-model-id claude-opus-5
uv run python tools/lane_setup.py --lane fable --model fable --effort high --append-model-id claude-fable-5
uv run python tools/lane_setup.py --verify
```

Expected: 两条命令各打印「车道就绪」，`--verify` 打印「冻结校验：无漂移」（退出码 0）。

- [ ] **Step 3: 隔离结构验收**

```bash
test -L work/lanes/opus/data/ledger.jsonl  && echo "只读数据=符号链接 OK"
test ! -L work/lanes/opus/glossary/active.json && echo "glossary=拷贝 OK"
test ! -e work/lanes/opus/data/forward.jsonl && echo "forward 未预建 OK"
diff -r work/lanes/opus/glossary work/lanes/fable/glossary && echo "两车道 glossary 快照一致 OK"
diff -r work/lanes/opus/skeleton work/lanes/fable/skeleton && echo "两车道 skeleton 快照一致 OK"
```

Expected: 五行 OK 全部打印。

- [ ] **Step 4: 生成两份执行计划**

```bash
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-opus \
  --lane-dir work/lanes/opus --model opus --effort max --append-model-id claude-opus-5
uv run python tools/gen_plan.py --lane main --batches 1-35 --label pilot-fable \
  --lane-dir work/lanes/fable --model fable --effort high --append-model-id claude-fable-5
```

Expected: 各打印 `docs/superpowers/plans/translate-pilot-<lane>.md: N 个任务`，N = 35 批 + 7 个检查点 + 1 个终任务 = 43。

- [ ] **Step 5: 计划内容抽查**

```bash
grep -c 'work/lanes/opus' docs/superpowers/plans/translate-pilot-opus.md
grep -c 'work/lanes/fable' docs/superpowers/plans/translate-pilot-opus.md
grep -n 'effort' docs/superpowers/plans/translate-pilot-opus.md | head -3
grep -n '批次 35' docs/superpowers/plans/translate-pilot-opus.md | head -2
```

Expected: 第一条 >0；**第二条必须为 0**（opus 计划里不得出现 fable 路径）；第三条能看到 `max`；第四条能看到批次 35 的任务标题。

- [ ] **Step 6: batch 1 上下文冒烟（两车道产出应逐字节相同）**

```bash
# 先清掉 Task 2 Step 5 体量核对留下的仓库侧产物（work/ 是 gitignore 的临时区，可安全删）
rm -rf work/ctx/batch_1
uv run python tools/build_context.py --batch 1 --profile cc --baseline none --repo work/lanes/opus
uv run python tools/build_context.py --batch 1 --profile cc --baseline none --repo work/lanes/fable
cmp work/lanes/opus/work/ctx/batch_1/context.md work/lanes/fable/work/ctx/batch_1/context.md \
  && echo "batch 1 两车道上下文一致 OK（前缀为空、快照相同，理应逐字节相同）"
test ! -e work/ctx/batch_1/context.md && echo "仓库 work/ 未被污染 OK（--repo 确实改道）"
```

Expected: 两行 OK。若 `cmp` 报差异，说明两条车道的冻结快照不一致，回到 Step 2 重建。

- [ ] **Step 7: 语义崩溃探测联通性自检**

用一份**人造**草稿验证工具在车道路径下可运行（不产生任何入线数据）：

```bash
uv run python - <<'EOF'
import json, sys, pathlib; sys.path.insert(0, ".")
src = [json.loads(l) for l in open("work/lanes/opus/work/ctx/batch_1/source.jsonl",
                                   encoding="utf-8")]
out = pathlib.Path("work/lanes/opus/work/out"); out.mkdir(parents=True, exist_ok=True)
# 人造草稿：原文照抄——应触发 C1（残留假名）
with open(out / "batch_1.draft.jsonl", "w", encoding="utf-8") as f:
    for r in src:
        f.write(json.dumps({"id": r["id"], "zh": r["jp"]}, ensure_ascii=False) + "\n")
EOF
uv run python tools/detect_collapse.py --batch 1 --lane-dir work/lanes/opus
rm work/lanes/opus/work/out/batch_1.draft.jsonl
```

Expected: 打印的 C1 计数远大于 0（证明探测器在真实数据上确实会响）。随后删除人造草稿——**它绝不能留在车道里被误当成真译文**。

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/plans/translate-pilot-opus.md docs/superpowers/plans/translate-pilot-fable.md
git commit -m "data: 生成 P2 试点两条车道的逐批执行计划（batch 1-35）"
```

（`work/lanes/` 在 `.gitignore` 内，车道目录本身不入库——这是设计使然：两条车道的译文属试点中间产物，结论确定后才决定哪一份进主线。）

---

## 收尾：交付状态

本计划完成后应处于以下状态，可直接开始 35×2 批次的翻译：

- `uv run pytest -q` 全绿；`uv run python tools/lane_setup.py --verify` 无漂移。
- `work/lanes/{opus,fable}/` 两条车道就绪，冻结哈希已记入 `work/lanes/pilot-manifest.json`。
- `docs/superpowers/plans/translate-pilot-{opus,fable}.md` 两份逐批计划已生成并入库，各 43 个任务。
- 三个新工具（`lane_setup` / `detect_collapse` / `compare_lanes`）带测试入库。

**尚未做、由后续执行阶段负责的事**（本计划不含）：
- 实际翻译 35×2 批次（按生成的两份计划执行，每条车道拆 3 个 workflow：批次 1–12 / 13–24 / 25–35）。
- batch 1、2 后的硬停验收（隔离验收 + 崩溃探测阈值标定 + 人工抽读）。
- batch 33 的窗口对撞探针（同模型同批次跑 `--profile cc` 与 `--profile api-A` 并排比对）。
- 卡面回译自检与三栏人工 rubric 评分（材料由 `compare_lanes.py` 产出）。
