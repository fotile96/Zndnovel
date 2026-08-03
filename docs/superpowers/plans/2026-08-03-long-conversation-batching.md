# 长对话多批生产模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `gen_plan` 能生成「一条对话连做 N 批」的会话组计划，把每批 44.7K 字符的固定材料重投降为只投一次 + 每批约 5KB 增量。

**Architecture:** 不改 `build_context`（ctx 照常逐批生成入档，只是不再整份投喂）、不改 `check_batch`/`detect_collapse`/`append_forward`（校验仍逐批做）。只改两处：①`gen_plan` 增加 `--session-size N` 把批次任务分组成会话任务；②`prompts/translator_cc.md` 增加长对话契约节。译者在会话第 2..N 批只读 `work/ctx/batch_N/source.jsonl` + 车道 `glossary/style.md` + `glossary/active.json`——**这三个文件已在磁盘上，无需任何工具产出新东西**。

**Tech Stack:** Python ≥3.12（纯 stdlib + pyyaml）、pytest、uv。

## Global Constraints

- `data/batches.jsonl` **已冻结，绝不可重新生成**（CLAUDE.md）。
- `prompts/` 属**钉死面**：改动后滚生产 tag 须过 canary 闸（runbook §4），且 `prod-run-v3→v4` 的判定记录里「`prompts/` 零改动」是被显式核对过的一项——本计划会打破它，须在判定记录中显式说明。
- **单条对话不超过 10 批**（spec §5.6）。
- **一条长对话不得跨越 glossary 版本变更**（spec §4.3）；该约束天然与段边界对齐。
- **默认 `--session-size 1` 必须与改造前逐字相同**——现有 62 条 `tests/test_gen_plan.py` 测试是回归闸，一条都不许改。
- 校验仍逐批：`check_batch` hard 修到 0 才 `append_forward`（spec §4.2）。
- W4（复现句族一致性）已于 commit `468c3ec`+`3c0ab9c` 上线，是本模式的配套机械闸（spec §6），**本计划不重复实现**。
- 车道路径一律经 `_paths(lane_cfg, tools_root)` 改写，**不得写死仓库根**。
- 不发任何 API 请求；单测一律用合成数据，**不得钉住活的生产数据**。

---

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `tools/gen_plan.py` | 计划渲染 | 新增 `_session_task()`；`render()`/`main()` 增 `session_size` 参数 |
| `tests/test_gen_plan.py` | 回归闸 | 追加会话分组用例；**既有 62 条一条不改** |
| `prompts/translator_cc.md` | 译者契约 | 追加「长对话会话模式」一节 |
| `docs/ops/p3-production-runbook.md` | 运行手册 | §4 增 prompts 改动的 canary 说明；新增会话模式使用条款 |

---

### Task 1: `gen_plan` 会话分组渲染

**Files:**
- Modify: `tools/gen_plan.py`（`render()` 约 487 行、`main()` 约 597 行；新增 `_session_task()`）
- Test: `tests/test_gen_plan.py`（追加）

**Interfaces:**
- Consumes: 既有 `_paths(lane_cfg, tools_root) -> dict`（键 `ctx/out/forward/notes/repo_arg/env/lane_dir_arg/tools`）、`_batch_task(tnum, batch, baseline, glossary_v, p, thresholds_arg="", segment=None) -> str`、`select(batches, *, lane, chapter=None, batch_range=None) -> list`
- Produces: `_session_task(tnum, batches, baseline, glossary_v, p, thresholds_arg="", segment=None) -> str`；`render(..., session_size=1)`；`main` 的 `--session-size`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_gen_plan.py`：

```python
def test_session_size_1_is_byte_identical_to_before():
    """默认值必须与改造前逐字相同——现有 62 条测试是回归闸，这条是显式断言。"""
    from tools.gen_plan import render
    sel = [{"batch": 1, "chapter": "s1s", "ids": [1, 2], "jp_chars": 50, "lane": "main"},
           {"batch": 2, "chapter": "s1s", "ids": [3], "jp_chars": 20, "lane": "main"}]
    assert render(sel, label="x", lane="main") == render(sel, label="x", lane="main",
                                                         session_size=1)


def test_session_size_groups_batches_into_one_task():
    from tools.gen_plan import render
    sel = [{"batch": n, "chapter": "s1s", "ids": [n], "jp_chars": 10, "lane": "main"}
           for n in range(1, 5)]
    md = render(sel, label="x", lane="main", session_size=2)
    assert md.count("### Task") < 4          # 4 批被并成更少的任务
    assert "会话组" in md


def test_session_task_first_batch_reads_full_ctx_rest_read_delta():
    from tools.gen_plan import _session_task, _paths
    p = _paths({"lane": "opus", "lane_dir": "pilot/lanes/opus", "model": "opus",
                "effort": "max", "append_model_id": "claude-opus-5"})
    bs = [{"batch": 7, "chapter": "s1s", "ids": [1], "jp_chars": 10, "lane": "main"},
          {"batch": 8, "chapter": "s1s", "ids": [2], "jp_chars": 10, "lane": "main"}]
    t = _session_task(1, bs, "none", 9, p)
    assert "batch_7/context.md" in t                    # 首批读全量
    assert "batch_8/source.jsonl" in t                  # 后续批只读增量
    assert "batch_8/context.md" not in t                # 后续批不读全量
    assert "glossary/style.md" in t                     # 每批重投退化最快的部分
    assert "glossary/active.json" in t


def test_session_task_keeps_per_batch_verification():
    """校验仍逐批：每批各有 check_batch / detect_collapse / append_forward。"""
    from tools.gen_plan import _session_task, _paths
    p = _paths({"lane": "opus", "lane_dir": "pilot/lanes/opus", "model": "opus",
                "effort": "max", "append_model_id": "claude-opus-5"})
    bs = [{"batch": 7, "chapter": "s1s", "ids": [1], "jp_chars": 10, "lane": "main"},
          {"batch": 8, "chapter": "s1s", "ids": [2], "jp_chars": 10, "lane": "main"}]
    t = _session_task(1, bs, "none", 9, p)
    assert t.count("check_batch.py --batch 7") >= 1
    assert t.count("check_batch.py --batch 8") >= 1
    assert t.count("append_forward.py --batch 7") >= 1
    assert t.count("append_forward.py --batch 8") >= 1


def test_session_size_over_10_is_refused():
    """spec §5.6：单条对话不超过 10 批。上限必须在工具层拦，不能靠人自觉。"""
    import pytest
    from tools.gen_plan import main
    with pytest.raises(SystemExit) as e:
        main(["--lane", "main", "--batches", "1-2", "--label", "x", "--session-size", "11"])
    assert "10" in str(e.value)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_gen_plan.py -k session -v`
Expected: FAIL（`render() got an unexpected keyword argument 'session_size'`）

- [ ] **Step 3: 实现 `_session_task`**

在 `tools/gen_plan.py` 的 `_batch_task` 之后加：

```python
SESSION_MAX = 10   # spec §5.6：单条对话批次上限


def _session_task(tnum, batches, baseline, glossary_v, p, thresholds_arg="",
                  segment=None):
    """会话组任务：一条对话连做多批。

    首批读全量 `context.md`；后续批**只**读该批 `source.jsonl` + 车道
    `glossary/style.md` + `glossary/active.json`。

    分档依据（spec §4.1，b63–72 十批实测）：骨架 8442 + 锚点 9439 + voices
    21887 三项共 39.8K 字符占固定开销 81%，且**各批逐字相同**，只投一次；
    退化最快的是 style.md 那类「低频触发 + 无机械兜底」的长散文规则，故每批
    重投（仅约 5KB）。

    校验仍逐批——本函数只改「模型看到什么」，不改校验语义。
    """
    first, rest = batches[0], batches[1:]
    ns = ", ".join(str(b["batch"]) for b in batches)
    lines = sum(len(b["ids"]) for b in batches)
    chars = sum(b["jp_chars"] for b in batches)
    chs = sorted({b["chapter"] for b in batches})
    head = f"""### Task {tnum}: 会话组 批次 {ns}（{len(batches)} 批 / {lines} 条 / 约 {chars} 日文字）

**Files:**
- Produces: 各批 `{p["ctx"]}/batch_N/{{context.md,source.jsonl,manifest.json}}`、`{p["out"]}/batch_N.draft.jsonl`、`{p["forward"]}` 追加共 {lines} 行

**Interfaces:**
- Consumes: `data/batches.jsonl` 的批次 {ns}（章别 {"/".join(chs)}）
- Produces: `{p["forward"]}` 里这些 id 的正向译文行

> **本任务是一条长对话连做 {len(batches)} 批**，不是 {len(batches)} 个独立子代理。
> 省的是每批重投 44.7K 字符固定材料；代价是规则遵守会从「查表」滑向「自洽」
> （spec §3.3），故后续批仍每批重投 `style.md`+`active.json`，并由 W4 机械闸
> 兜住复现句族一致性。

- [ ] **Step 1: 生成全部批次的上下文包**

Run（逐批执行，ctx 照常入档）：
"""
    for b in batches:
        head += (f"\n`uv run python {p['tools']}/build_context.py --batch {b['batch']}"
                 f" --profile cc --baseline {baseline}{p['repo_arg']}`")
    head += f"""

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`；记下每批 `manifest.json` 的 `ctx_sha`（入库要用）。

**开工前硬检查**：确认 {ns} 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 {len(batches)} 批**

注入：车道根、批次序列 {ns}、以及「首批 {first['batch']} 读全量 `context.md`，其余批只读 `{p['ctx']}/batch_N/source.jsonl` + `{p['lane_dir_arg'].strip().replace('--lane-dir ', '')}/glossary/style.md` + `.../glossary/active.json`」。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。
"""
    for b in batches:
        n = b["batch"]
        collapse = (f"\n`{p['env']}uv run python {p['tools']}/detect_collapse.py "
                    f"--batch {n}{p['lane_dir_arg']}{thresholds_arg}`"
                    if p["lane_dir_arg"] else "")
        head += f"""
- [ ] **Step 3.{n}: 批次 {n} 校验与入库**

Run: `{p["env"]}uv run python {p["tools"]}/check_batch.py --batch {n}{p["lane_dir_arg"]}`
Expected: `batch_{n}: PASS  warn=K`（`hard=0` 即可）。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。{collapse}

Run: `{p["env"]}uv run python {p["tools"]}/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v {glossary_v}`

```bash
git add {p["forward"]}
git commit -m "data: {b["chapter"]} 批次{n} 译文入线"
```
"""
    return head.rstrip()
```

- [ ] **Step 4: 接进 `render()` 与 `main()`**

`render()` 签名加 `session_size=1`（放在 `segment_sub=None` 之后），并把批次循环改为：

```python
    tnum = 1
    chunk = []
    batch_task_count = 0
    groups = ([[b] for b in sel] if session_size <= 1
              else [sel[i:i + session_size] for i in range(0, len(sel), session_size)])
    for grp in groups:
        if len(grp) == 1:
            parts.append(_batch_task(tnum, grp[0], baseline, glossary_v, p,
                                     thresholds_arg, segment=segment))
        else:
            parts.append(_session_task(tnum, grp, baseline, glossary_v, p,
                                       thresholds_arg, segment=segment))
        tnum += 1
        batch_task_count += len(grp)
        # 硬停任务只在 P2 试点（segment is None）且逐批模式下生成——它们的模板里
        # 硬编码了 batch_1/2 字面量，会话组模式下不适用。
        if session_size <= 1 and segment is None and lane_cfg is not None \
                and batch_task_count == 1:
            parts.append(_hardstop_after_batch1(tnum, lane_cfg, p))
            tnum += 1
        elif session_size <= 1 and segment is None and lane_cfg is not None \
                and batch_task_count == 2:
            parts.append(_hardstop_after_batch2(tnum, lane_cfg, p, label,
                                                sel[0]["batch"], sel[-1]["batch"]))
            tnum += 1
        chunk.extend(grp)
        if len(chunk) >= every:
            ...   # 既有检查点逻辑原样保留，只把 == 改成 >=
```

`main()` 里加：

```python
    ap.add_argument("--session-size", type=int, default=1,
                    help="一条对话连做几批（spec §5.6 上限 10）；1=逐批模式，"
                         "输出与改造前逐字相同")
```

并在 `args = ap.parse_args(argv)` 之后立即校验：

```python
    if args.session_size < 1:
        raise SystemExit("--session-size 必须 ≥1")
    if args.session_size > SESSION_MAX:
        raise SystemExit(
            f"--session-size {args.session_size} 超过上限 {SESSION_MAX}"
            f"（spec §5.6：10 批/585 行是已验过的范围，更长未测）")
```

最后把 `session_size=args.session_size` 传进 `render(...)` 调用。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_gen_plan.py -v`
Expected: 全部通过（既有 62 条 + 新增 5 条 = 67）

- [ ] **Step 6: 变异自检（本项目已栽过八次恒绿闸）**

把 `session_size > SESSION_MAX` 的上限判断改成 `if False:`，跑 `uv run pytest tests/test_gen_plan.py -k over_10 -v` → 必须精确变红；改回。把 `groups` 的分组三元表达式改成恒 `[[b] for b in sel]`，跑 `-k session` → 必须变红；改回。**两次变异结果写进报告**。

- [ ] **Step 7: 全量测试 + 提交**

Run: `uv run pytest -q` → 463 + 5 = 468 passed

```bash
git add tools/gen_plan.py tests/test_gen_plan.py
git commit -m "feat: gen_plan 支持会话组（--session-size，默认 1 行为不变）"
```

---

### Task 2: 译者指令的长对话契约

**Files:**
- Modify: `prompts/translator_cc.md`（在「开工前：读三件材料」一节之后插入新节）

**Interfaces:**
- Consumes: Task 1 生成的会话组任务文本（它会引用本节节名「长对话会话模式」）
- Produces: 无代码接口；本任务交付的是**契约文本**

> ⚠ `prompts/` 是钉死面。本任务改动它，Task 4 的 canary 判定记录必须显式说明——`prod-run-v3→v4` 的记录里「`prompts/` 零改动」曾是被核对过的一项。

- [ ] **Step 1: 追加契约节**

在 `prompts/translator_cc.md` 的「## 开工前：读三件材料」一节结束后插入：

```markdown
## 长对话会话模式（派发方明确说「会话组」时才适用）

平时是「一批一个全新会话、每批读一份完整 `context.md`」。派发方若告诉你这是**会话组**（形如「批次 63,64,65,66,67」），则：

- **只在开头读一次首批的 `work/ctx/batch_<首批>/context.md` 全文**（五节俱全）
- 其余各批**只读**三样：该批 `work/ctx/batch_N/source.jsonl`、车道 `glossary/style.md`、车道 `glossary/active.json`
- **不要**再读其余各批的 `context.md`

依据（b63–72 十批实测）：`context.md` 的第一节（冻结骨架 8442 字符）、第三节（锚点行 9439 字符）、第四节里的 7 份口调表（21887 字符）**各批逐字完全相同**，读一次即可；第二节前缀正文你自己刚译过、就在本对话里。

### 这个模式有一个已实测的失效模式，请当真

十批实测显示：**规则记忆本身不退化，退化的是「这句需要外部核对」的风险识别**。具体表现是——

> 复现句在「看起来不值得查的句子」里密度最高，而那恰恰是最不会去查的地方。

实测 16 组复现句里 3 组译法不一致，全部是短句（`【アヤノ】「そう……」` 这类）。长句零违例。

**这个模式把「与表一致」换成了「与自己一致」**：跨批一致性会变好（前面定的措辞可零成本复用），但一旦你的前文与规则表冲突，你大概率会输给自己的前文。

**因此每批开工前重读 `style.md`**（约 100 行，退化最快的润色四条边界、补『』三条口径都在里面），口调表与骨架卡组则确实只需读一次。

### 两条硬纪律

1. **每批译完立刻校验并入库**（`check_batch` → `detect_collapse` → `append_forward`），再进入下一批——不要攒到最后。
2. `check_batch` 若打印 **「⚠ W4 未启用」**，说明复现句族一致性**没有被检查**，不要把它当成通过；补 `--lane-dir` 重跑。W4 正是为兜住上述失效模式而建的机械闸。

### 一条来自实测的提醒：不要心算 W3

W3 的实际判据是 `_max_line_width(zh) > max(10, _max_line_width(jp) * 1.15)`——**有 10 的地板**，且**宽度按整行算、含 `【说话人】「」` 外壳**（CJK 按宽 2）。实测曾有译者为一个**根本不存在的 W3 风险**主动收紧措辞，牺牲了两条复现句的一致性。

**先写自然译文，再跑工具**。W3 只对长的裸旁白行有实际约束力。
```

- [ ] **Step 2: 核对没有破坏既有引用**

Run: `grep -n "开工前：读三件材料\|长对话会话模式\|## " prompts/translator_cc.md | head -20`
Expected: 新节出现在「开工前：读三件材料」之后、且不打断既有节序。

Run: `uv run pytest -q`
Expected: 468 passed（本任务不改代码，测试数不变——若变红说明有测试钉住了 prompts 内容，需查明）

- [ ] **Step 3: 提交**

```bash
git add prompts/translator_cc.md
git commit -m "docs: 译者指令增加长对话会话模式契约"
```

---

### Task 3: runbook 增补会话模式条款

**Files:**
- Modify: `docs/ops/p3-production-runbook.md`（§4 段边界工具升级流程之后；§5 段末流程之前）

**Interfaces:**
- Consumes: Task 1 的 `--session-size`、Task 2 的契约节名
- Produces: 生产会话据以执行的操作条款

- [ ] **Step 1: 插入条款**

在 runbook 的 `## 五、段末流程与小裁决会话` 之前插入：

```markdown
## 四·五、长对话会话模式（可选，spec 见 2026-08-03-long-conversation-batching-design.md）

生成会话组计划：在既有 `gen_plan` 命令上加 `--session-size N`（N ≤ 10）。`--session-size 1`（默认）输出与改造前逐字相同。

**三条硬约束**：

1. **一组不得跨 glossary 版本**——组内各批 `manifest.json` 的 `glossary_v` 必须全部相同。段边界天然满足该约束，跨段分组必须拆。
2. **单组 ≤10 批**（工具层已拦，`--session-size 11` 直接 rc≠0）。10 批/585 行是已实测范围，更长未测。
3. **`check_batch` 必须带 `--lane-dir`**——否则打印「⚠ W4 未启用」，复现句族一致性没被检查。见到该行不要当成通过。

**已知代价（spec §3.3/§5.1，非推测）**：本模式把「与表一致」换成「与自己一致」。跨批一致性变好，规则遵守滑向自洽。十批实测出 3 组长对话独有的复现句退化（逐批模式做对了）。**W4 是为此建的兜底闸，不可省。**

**投喂量实测**：b63–67 五批 594KB → 131KB（省 78%）；速度约 18 行/分钟，快于逐批模式。
```

- [ ] **Step 2: 核对**

Run: `grep -n "^## " docs/ops/p3-production-runbook.md`
Expected: 新节位于「四、段边界工具升级流程」与「五、段末流程」之间。

- [ ] **Step 3: 提交**

```bash
git add docs/ops/p3-production-runbook.md
git commit -m "docs: runbook 增补长对话会话模式条款"
```

---

### Task 4: 生产树升级（canary 闸 + prompts 钉死面破例说明）

**Files:**
- Modify: `docs/ops/p3-production-runbook.md`（§4 追加判定记录）

**Interfaces:**
- Consumes: Task 1–3 的全部改动
- Produces: `prod-run-v5` tag；生产树切至该 tag

> 本任务**必须最后做**，且 canary 差异需人工裁定后才能滚 tag（runbook §4 步骤 3）。

- [ ] **Step 1: 成对回验**

先记录漂移面：

Run: `git diff --stat prod-run-v4..HEAD -- tools/ prompts/`
Expected: 至少含 `tools/gen_plan.py` 与 `prompts/translator_cc.md`。

Run（旧树）：
`cd /Users/fotile96/Zndnovel-prod && uv run python tools/canary.py --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --batches 63-90 --out /tmp/canary-old.json`

Run（新树）：
`cd /Users/fotile96/Zndnovel && uv run python tools/canary.py --lane-dir pilot/lanes/opus --batches 63-90 --out /tmp/canary-new.json`

Run: `uv run python tools/canary.py --diff /tmp/canary-old.json /tmp/canary-new.json`

**不加 `--regen-ctx`**（本次不触及 `build_context`）。

- [ ] **Step 2: 判定差异**

**预期**：`check` 半边会**因 W4 而变化**（W4 是 `prod-run-v4` 之后新增的），`collapse` 半边应恒等（`detect_collapse` 未改）。

做**集合级**比对（非仅比计数）——参照 runbook §4 既有判定记录的做法：逐批取 `{(id, rule, msg)}` 集合求差。**新增的 W4 命中是预期改进，须逐条确认其确为复现句族不一致**（用 `tools/agent_tools.py` 的 `get_lines` 取兄弟行原文译文复算至少 3 条）。

**若 hard 有任何变化 → 停止，报告人工裁决。** hard 变化不在本次改动的预期影响面内。

- [ ] **Step 3: 写判定记录**

在 runbook §4 追加 `prod-run-v4 → prod-run-v5` 判定记录，格式照抄既有两条记录，**并显式写明**：

> **本次破例改动了 `prompts/`**（钉死面）——`prod-run-v3→v4` 的记录里「`prompts/` 零改动」曾是被核对过的一项。改动内容为新增「长对话会话模式」契约节，**不修改既有任何一节**，故对逐批模式的派发行为无影响。canary 覆盖不到 `prompts/`（它不参与四件套判定面），该项由人工核对：`git diff prod-run-v4..HEAD -- prompts/` 应只见新增行、无删除行。

- [ ] **Step 4: 滚 tag 并切换**

```bash
git tag prod-run-v5
git -C /Users/fotile96/Zndnovel-prod checkout prod-run-v5
git -C /Users/fotile96/Zndnovel-prod describe --tags
```
Expected: `prod-run-v5`

更新 runbook 的「**当前生产 tag**」行。

- [ ] **Step 5: 提交**

```bash
git add docs/ops/p3-production-runbook.md
git commit -m "ops: 生产树升级 prod-run-v4→v5（会话组 + 长对话契约）"
```

---

## Self-Review 记录

**Spec 覆盖**：§1 固定开销构成→Task 1 的 `_session_task` docstring 与分档实现；§4.1 分档处理→Task 1 Step 3 + Task 2 契约节；§4.2 逐批校验不变→Task 1 Step 3 的 `Step 3.N` 逐批三件套 + 测试 `test_session_task_keeps_per_batch_verification`；§4.3 不得跨 glossary 版本→Task 1 Step 3 的开工前硬检查 + Task 3 runbook 条款 1；§4.4 复现性凭证不变→Task 1 Step 1 仍逐批 `build_context`；§4.5 爆炸半径→逐批 `append_forward` 保证（Task 1 Step 3）；§5.1/§3.3 失效模式→Task 2 契约节「已实测的失效模式」；§5.4 W3 心智模型→Task 2「不要心算 W3」；§5.6 上限 10→Task 1 `SESSION_MAX` + `test_session_size_over_10_is_refused`；§6 W4→已上线，Task 2/3 引用其播报行为。**§5.5（手记里写进虚构规则）未覆盖**——spec 自身已标为审计能力缺口、明确不在实现范围。

**占位符**：无 TBD/TODO。Task 4 Step 2 的「判定差异」是人工裁决步骤，已给出具体判据（集合级比对、hard 变化即停、至少复算 3 条）而非泛泛「检查一下」。

**类型一致性**：`_session_task(tnum, batches, baseline, glossary_v, p, thresholds_arg="", segment=None) -> str` 在 Task 1 Step 3 定义、Step 4 调用，参数序与 `_batch_task` 对齐（后者是 `batch` 单数、前者 `batches` 复数）；`p` 恒为 `_paths()` 返回值；`SESSION_MAX` 在 Step 3 定义、Step 4 使用。测试计数链 463→468。

**风险点已内嵌**：Task 1 Step 6 的双变异自检；Task 2 Step 2 的「测试变红即说明有测试钉住 prompts」；Task 4 Step 2 的「hard 变化即停」与 prompts 钉死面破例的人工核对条款。
