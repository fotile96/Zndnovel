"""章翻译执行计划生成器：data/batches.jsonl 里选中的批次 → 可被
superpowers:executing-plans 直接执行的 docs/superpowers/plans/translate-<label>.md。

render() 是纯字符串模板函数（不碰文件系统）；select() 负责从全量批次里挑出
本次要生成计划的子集（按 lane + chapter 或 lane + 连续批号段）；main() 负责
读 batches.jsonl、解析 CLI、把 render() 的结果写盘。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, DATA, read_jsonl
from tools.build_context import glossary_version

# render() 的 glossary_v 参数默认值/测试兜底。真实运行由 main() 通过
# build_context.glossary_version() 动态扫描 glossary/ 目录求得，不再消费这个
# 常量——曾经两处各自维护一个真相源，计划文本会把这里的硬编码盖进 append-only
# 的 forward 行（Minor 修复）。
GLOSSARY_V = 6

# spec §2：压缩机制在段内 32 批（seq<100）从不触发，batch 33（seq 101 起）是
# 压缩生效后的第一批——窗口对撞探针（C1 item 4 / spec §6.4）只对这一批有意义。
# 写成常量而非"最后一批"，因为探针要回答的是"压缩触发瞬间是否丢信息"，与
# 计划恰好在哪批结束无关；未来若某次 render() 选中的批号段不含 33，探针任务
# 就不生成（见 render() 里的判断）。
WINDOW_PROBE_BATCH = 33


def _tools_prefix(tools_root=""):
    """按批四件套（build_context/check_batch/detect_collapse/append_forward）Run
    行里的工具目录前缀。终审 C1 的规则：

    - cwd 恒为主仓；
    - 只有这四件套用生产 worktree 的绝对路径（它们才是「段内必须不变」的东西，
      也是 canary 回归闸真正覆盖的判定面）；
    - `lane_setup`/`gen_plan`/`saturation`/`resolve` 与全部 git 操作固定用主仓
      `tools/`——lane_setup 的 `LANES_ROOT`/`REPO` 由 `__file__` 推出，在生产
      worktree 里指向 gitignore 的空车道目录，`--verify` 必然 exit 1；git 操作
      在生产树 cwd 下会因主仓路径「outside repository」而失败，且生产树是
      detached HEAD，commit 落不到 main。

    tools_root 为空（默认）时返回裸 "tools"——非段模式输出与改造前逐字相同。
    """
    return f"{tools_root.rstrip('/')}/tools" if tools_root else "tools"


def _paths(lane_cfg, tools_root=""):
    """把计划文本里的全部路径按车道根改写。lane_cfg 为 None 时返回仓库相对路径
    （回归闸 test_no_lane_cfg_keeps_repo_relative_paths 锁死这一点：非车道模式下
    全部产出路径必须保持仓库相对形态，不出现 --repo/ZND_WORK 等车道专属前缀）。
    "tools" 键是四件套的工具目录前缀，见 _tools_prefix。"""
    tools = _tools_prefix(tools_root)
    if lane_cfg is None:
        return {"ctx": "work/ctx", "out": "work/out", "forward": "data/forward.jsonl",
                "notes": "data/notes", "repo_arg": "", "env": "", "lane_dir_arg": "",
                "tools": tools}
    d = lane_cfg["lane_dir"]
    return {"ctx": f"{d}/work/ctx", "out": f"{d}/work/out",
            "forward": f"{d}/data/forward.jsonl", "notes": f"{d}/data/notes",
            "repo_arg": f" --repo {d}",
            "env": f"ZND_WORK={d}/work ZND_DATA={d}/data ",
            "lane_dir_arg": f" --lane-dir {d}",
            "tools": tools}


def _lane_block(lane_cfg, segment=None):
    if lane_cfg is None:
        return ""
    # 车道根的父目录（车道们的公共目录）动态取自 lane_dir，不写死——
    # 车道根从 work/lanes/ 迁到 pilot/lanes/ 之后（终审 C2）这里若仍硬编码
    # 旧路径会把隔离纪律指向一个不存在的目录。
    lanes_root_display = str(Path(lane_cfg["lane_dir"]).parent)
    # M6：段模式换段语汇——段末流程明文要求裁决，再说「裁决推迟到试点结束」
    # 会与本计划自己的段末清单直接打架。
    proposal = ("本段进行中提案只追加进" if segment else "试点期间提案只追加进")
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
- **隔离纪律**：禁止读取、列出 `{lanes_root_display}/` 下除 `{lane_cfg["lane"]}` 外的任何目录，禁止读取仓库根 `data/forward.jsonl`；查既有译法一律用 `{lane_cfg["lane_dir"]}/data/forward.jsonl`。违反即本批作废重跑。
- **术语提案不裁决**：{proposal} `{lane_cfg["lane_dir"]}/data/notes/<chapter>.md`，不新增 `glossary.vN.yaml`、不改 `glossary/active.json`。
- **中断恢复**：从 `{lane_cfg["lane_dir"]}/data/forward.jsonl` 已有的 id 对照 `data/batches.jsonl` **重新推导**第一个未完成的批次，不要信任任何进度文件或记忆——forward 是 append-only 的，它与实际完成状态不可能失同步。"""


def _segment_head(segment, tools_root="", segment_sub=None):
    tr = tools_root or "<生产worktree>"
    # 子区间标注（终审 I6）：段模式给了 --batches 且是段表区间的真子集时，本计划
    # 只覆盖段的一部分（断点续跑），抬头必须写明——否则「跑完本计划＝本段跑完」
    # 这个默认理解会连着段末流程一起被误触发。
    sub = (f"\n\n> ⚠ **本计划仅覆盖 {segment} 的子区间 {segment_sub[0]}–{segment_sub[1]}**"
           f"（`--batches` 限定，断点续跑用）。本段其余批次不在本计划内；"
           f"段末流程只在**整段**批次全部入线后才执行。" if segment_sub else "")
    return f"""

## 段开场自检（P3 生产会话必做，缺一不可）

本计划属于检查段 **{segment}**（`config/segments.yaml`）。开工前逐项确认并把结果写进台账：{sub}

1. **cwd 与工具树划分**（本节全部命令、以及本计划的全部 git 操作，一律在**主仓**执行，cwd 恒为主仓，**不要 `cd` 到生产 worktree**）：
   - 按批四件套 `build_context` / `check_batch` / `detect_collapse` / `append_forward` 走**生产 worktree 的绝对路径**——各批 Task 的 Run 行已内嵌 `{tr}/tools/…`，逐字照抄，不要改回相对形态；
   - `lane_setup` / `gen_plan` / `saturation` / `resolve` 与全部 git 操作走**主仓 `tools/`**（它们不参与段内冻结语义；lane_setup 在生产树里会因 `__file__` 推出的车道根为空而必然报「冻结文件缺失」，git 也会因主仓路径 outside repository 而失败）。
2. **工具树版本**：`git -C {tr} describe --tags` 应等于 runbook「当前生产 tag」行记录的值。
3. **车道冻结**（本命令在主仓执行）：`uv run python tools/lane_setup.py --lane opus --verify` 输出「冻结校验：无漂移」。
4. **额度余量**：确认本周订阅额度尚有本段预算（生产目标 ≤50%/周）。流程细节见 `docs/ops/p3-production-runbook.md`。"""


def _segment_tail(segment):
    # 本清单的编号与内容必须与 docs/ops/p3-production-runbook.md §5 的五项**逐项
    # 对齐**（终审 I3）：生产会话实际照做的是这份渲染出来的清单（handoff 明写
    # 「按计划最后一个任务的『段末流程』执行」），而 runbook 是操作依据；两边同为
    # 1–5 编号却第 3 项含义不同时，段末会话会在「第 3 步」上产生歧义。改一边就改
    # 另一边。
    return f"""

## 段末流程（本段全部批次入线后执行，缺一不可）

以下命令与 git 操作全部在**主仓**执行（cwd 恒为主仓，工具用主仓 `tools/`）。本清单与 `docs/ops/p3-production-runbook.md` §5 逐项对齐。

1. 机检复核：本计划各批 check/collapse 记录过一遍，hard 全零。
2. 请用户按 `config/segments.yaml` 本段 `review_focus` 抽读关键场。
3. （tag 前，可选但强烈建议）跑**彩野测试**作额外验收：`uv run python tools/ayano_test.py --segment {segment} --qa config/ayano_qa/{segment}.yaml --lane-dir pilot/lanes/opus`（零订阅额度，走 deepseek API，需 `DEEPSEEK_API_KEY`；题库由开发轨按段提供，`config/ayano_qa/{segment}.yaml` 不存在时**工具自身**会打印跳过提示（点名期望路径）并以 **rc=2** 退出——不抛异常、也不会被误读成「跑完且全部通过」（rc=0）；见此跳过即记进段末台账，不必人工先 `ls` 探路径。**不得拿别段的题库顶替**——题库自带 `segment` 绑定，段名不符工具会直接报错退出（rc=1）；上一段的题目其答案往往整张躺在本段前缀卡里，跑出来必是恒绿假信号）。报告落 `work/out/ayano-{segment}.md`，判「错」的题逐条人工核对是译文丢信息还是题目/判分问题，结论记进段末台账。
4. 打段完成 tag：`git tag prod-opus-{segment}-done`。
5. 提醒用户开**段末小裁决会话**：先跑 `uv run python tools/cluster_notes.py --lane-dir pilot/lanes/opus --out work/out/dossier-{segment}.md` 把本段提案按词族聚成卷宗，再对可裁词族跑 `uv run python tools/saturation.py --terms-file <本段提案词表> --data-dir pilot/lanes/opus/data --gate 0.8`（**`--data-dir` 必须带**——漏传会读仓库根 `data/`，那里没有车道 forward.jsonl，结果是一张全列「滚存」的合理假表；工具会在表头前打印 `done=N 条已入线译文`，N 为 0 即说明漏传），可裁决词族当场裁，滚存词族聚类归档（runbook §5「裁决会话清单」）。裁决产出新 glossary 版本时，按 runbook「段边界版本切换」执行车道再冻结 + 召回/patches。"""


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


def _header(label, lane, every, count, glossary_v, lane_cfg, chapters_all=(),
            segment=None, tools_root=""):
    """chapters_all：本计划全部批次涉及的真实章别（去重、升序）。--chapter 模式
    下 label 恰好就是唯一真实章别，"label 章"是准确表述；--batches 连续段模式
    下 label 只是计划名（如 "pilot-opus"），不是任何批次的真实章别——继续说
    "label 章"具有误导性（终审分诊的顺手 minor，与 Hotfix D 修的 _final_task/
    _checkpoint_task 是同一类 label-as-chapter 问题，当时未覆盖到这里）。"""
    p = _paths(lane_cfg, tools_root)
    single_chapter = len(chapters_all) == 1 and chapters_all[0] == label
    if single_chapter or not chapters_all:
        # chapters_all 为空是测试兜底（旧调用点未传参）——保持原表述，不因为
        # 新增可选参数就改变既有调用方的输出。
        title = f"{label} 章（{lane} 车道）翻译执行计划"
        goal = (f"把 `data/batches.jsonl` 里 {label} 章（lane={lane}）的全部 "
                f"{count} 个批次逐批译出、校验、入库到 `{p['forward']}`，章末"
                f"完成骨架一致性自检与人工评审 gate。")
    else:
        ch_str = "、".join(chapters_all)
        title = f"{label}（{lane} 车道）翻译执行计划"
        goal = (f"把 `data/batches.jsonl` 里 {label} 段（lane={lane}）的全部 "
                f"{count} 个批次逐批译出、校验、入库到 `{p['forward']}`，段末"
                f"完成骨架一致性自检与人工评审 gate。**这是一个 timeline 连续段"
                f"（非单一章节），横跨 {len(chapters_all)} 个真实章别：{ch_str}。**")
    if lane_cfg is None:
        pipeline_desc = ("「build_context 生成上下文包 → 按 `prompts/translator_cc.md` "
                         "派译者子代理 → check_batch 机械校验 → append_forward "
                         "入库并提交」四步流水线")
        git_step = "Step 4"
    else:
        pipeline_desc = ("「build_context 生成上下文包 → 按 `prompts/translator_cc.md` "
                         "派译者子代理 → check_batch 机械校验 → detect_collapse "
                         "语义崩溃探测（顾问级） → append_forward 入库并提交」五步流水线")
        git_step = "Step 5"
    # M6：段模式统一换段语汇（非段模式一字不变）。
    gate_where = "段末" if segment else "章末"
    baseline_when = "本段" if segment else "试点期"
    if segment:
        tr = tools_root or "<生产worktree>"
        run_rule = (f"**cwd 恒为主仓**；按批四件套（`build_context`/`check_batch`/"
                    f"`detect_collapse`/`append_forward`）用各 Task Run 行内嵌的"
                    f"生产 worktree 绝对路径 `{tr}/tools/…`，其余工具"
                    f"（`lane_setup`/`gen_plan`/`saturation`/`resolve`）与全部 git "
                    f"操作用主仓 `uv run python tools/<x>.py`（详见「段开场自检」）")
    else:
        run_rule = "运行 `uv run python tools/<x>.py`"
    return f"""# {title}

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** {goal}

**Architecture:** 每个批次一个任务，走 {pipeline_desc}（P1b 已建成，签名见下）；每 {every} 批插一个 CHECKPOINT 任务做术语提案裁决与抽查；{gate_where}插一个人工评审 gate，不自动放行。

**Tech Stack:** uv 项目 Python 工具链（`tools/build_context.py` / `tools/check_batch.py` / `tools/append_forward.py`），零新增依赖；译者/评审子代理分别按 `prompts/translator_cc.md` / `prompts/reviewer_cc.md` 派发。

## Global Constraints

- {run_rule}；commit 规范 `type: 中文摘要`（type ∈ feat/fix/docs/data/analysis/chore/refactor），本计划的批次提交固定用 `data: <chapter> 批次N 译文入线`（`<chapter>` 为该批次自己的真实章别，不是本计划名/label——连续段模式下同一计划可能横跨多章），main 分支直提交。
- `skeleton/`、`glossary/` 只读引用，本计划不修改它们；发现术语缺口按 `prompts/translator_cc.md`「术语提案」节追加到 `{p["notes"]}/<chapter>.md`，不要直接改 `glossary/active.json`（版本化流程见 `CLAUDE.md`「术语层」节）。
- `build_context.py` 的 `--profile` 固定 `cc`（本计划专属 CC 后端，即本工具名里的「CC」）；`--baseline` {baseline_when}固定 `none`。
- `append_forward.py` 的 `--backend/--model/--ctx/--glossary-v` 均为必填：`--backend cc`、`--glossary-v {glossary_v}`（当前最高 glossary 版本）固定；`--ctx` 取本批 `manifest.json` 里的 `ctx_sha`；`--model` 填实际执行本批翻译子代理所用的模型 ID。
- 派子代理（Step 2）与执行 git 操作（{git_step}）都由执行本计划的 agent 亲自完成——`prompts/translator_cc.md`/`reviewer_cc.md` 都明确子代理不得碰 git。
{_lane_block(lane_cfg, segment)}
---"""


def _batch_task(tnum, batch, baseline, glossary_v, p, thresholds_arg="", segment=None):
    n, ch, ids = batch["batch"], batch["chapter"], batch["ids"]
    # M6：段模式没有 P2 试点专属的硬停任务（render 不生成），再指向它就是悬空引用。
    roundup = "检查点/段末流程" if segment else "检查点/硬停任务"
    collapse_step = (
        f"""
- [ ] **Step 4: 语义崩溃探测（顾问级，不阻断——命中需人眼过一遍再入线）**

Run: `{p["env"]}uv run python {p["tools"]}/detect_collapse.py --batch {n}{p["lane_dir_arg"]}{thresholds_arg}`
Expected: `batch_{n}: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接进 Step 5；K>0 时打开 `{p["out"]}/batch_{n}.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回 Step 2 重新出译文、重跑 Step 3–4。把命中数（按规则 C1/C2/C3 分类）记进本批记录，供后面的{roundup}汇总参考。
"""
        if p["lane_dir_arg"] else "")
    step5_num = "5" if p["lane_dir_arg"] else "4"
    return f"""### Task {tnum}: {ch} 批次 {n} 译文入库（{len(ids)} 条，约 {batch["jp_chars"]} 日文字）

**Files:**
- Produces: `{p["ctx"]}/batch_{n}/{{context.md,source.jsonl,manifest.json}}`（Step 1）、`{p["out"]}/batch_{n}.draft.jsonl`（Step 2 产出、Step 3 校验）、`{p["forward"]}` 追加本批 {len(ids)} 行（Step {step5_num}）

**Interfaces:**
- Consumes: `data/batches.jsonl` 第 {n} 批（`lane={batch["lane"]} chapter={ch}`，{len(ids)} 条 id）
- Produces: `{p["forward"]}` 里这些 id 的正向译文行（下一批的前缀正文靠它）

- [ ] **Step 1: 生成上下文包**

Run: `uv run python {p["tools"]}/build_context.py --batch {n} --profile cc --baseline {baseline}{p["repo_arg"]}`
Expected: 生成 `{p["ctx"]}/batch_{n}/context.md`、`source.jsonl`、`manifest.json`；记下 `manifest.json` 里的 `ctx_sha`（Step {step5_num} 要用）。

- [ ] **Step 2: 派译者子代理**

按 `prompts/translator_cc.md` 派一个子代理处理本批（明确告诉它批次编号是 {n}，并按本计划头部「车道配置」注入车道根），产出 `{p["out"]}/batch_{n}.draft.jsonl`。

- [ ] **Step 3: 校验**

Run: `{p["env"]}uv run python {p["tools"]}/check_batch.py --batch {n}{p["lane_dir_arg"]}`
Expected: `batch_{n}: PASS  warn=K`（`hard=0` 即可，`K` 可以大于 0）。若输出 `FAIL`，按 `{p["out"]}/batch_{n}.check.json` 逐条修回 Step 2 产出的 `draft.jsonl`，重跑本步直到 PASS。
{collapse_step}
- [ ] **Step {step5_num}: 入库并提交**

Run（`<model>` 换成本车道 `append_model_id`；`<ctx_sha>` 取自 Step 1 产出的 `manifest.json`）：

`{p["env"]}uv run python {p["tools"]}/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v {glossary_v}`

```bash
git add {p["forward"]}
git commit -m "data: {ch} 批次{n} 译文入线"
```"""


SESSION_MAX = 10          # spec §5.6：单条对话批数上限
SESSION_LINES_MAX = 600   # 同节：行数上限（实测包络 b63–72 = 10 批 / 585 行）


def _group_sessions(sel, size, lines_cap):
    """按**双重上限**切会话组：批数 ≤ size 且行数 ≤ lines_cap。

    为什么不能只按批数：本语料批量差 200 倍（`data/batches.jsonl` 最小 2 行、
    最大 407 行）。只按批数封顶时「10 批」在不同段落可能是 20 行也可能是
    3000 行，而 spec §5.6 的实测包络（585 行）是**按行**给出的——单位错了，
    上限就形同虚设。SEG-3 剩余批次即为实例：b111=364 行、b115=374 行，单批
    就逼近整个实测组的规模。

    单批自身超 lines_cap 时独占一组（批不可再分）。
    """
    if size <= 1:
        return [[b] for b in sel]
    groups, cur, n = [], [], 0
    for b in sel:
        L = len(b["ids"])
        if cur and (len(cur) >= size or n + L > lines_cap):
            groups.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += L
    if cur:
        groups.append(cur)
    return groups


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
    # 车道根：非车道模式（lane_dir_arg 为空）退回仓库相对形态 "."，不要拼出
    # "/glossary/style.md" 这种看着像绝对路径的东西。
    lane_root = p["lane_dir_arg"].strip().replace("--lane-dir ", "") or "."
    # 后续批的增量材料**逐批点名**（不写 batch_N 通配）：派发方要照抄这行注入
    # 子代理，通配符会让它自己去猜批号，而这正是本模式最不该留的自由度。
    rest_srcs = "、".join(f"`{p['ctx']}/batch_{b['batch']}/source.jsonl`"
                          for b in rest) or "（无）"
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

- [ ] **Step 1: 生成全部批次的上下文包**（首批正常模式；其余批 `--jp-fallback`）

> **为什么后续批要加 `--jp-fallback`**：后批 `context.md` 的前缀正文取自 `{p["forward"]}`，
> 而整组开跑时后面几批的前置译文**还没入线**，正常模式必然报「前缀行 N 未译」。
> 这一步给后续批出包**只为让该批 `source.jsonl` 就位**——`source.jsonl` 只由
> `data/batches.jsonl` + ledger 决定，与 fallback 与否无关、逐字相同。
> 这些 fallback 档案的 `context.md` 与 `ctx_sha` 一律**不作数**，会在各自的
> Step 3.N 开头以正常模式重生成并覆盖，**审计链里不留 fallback 残迹**。

Run（逐批执行，ctx 照常入档）：
"""
    for b in batches:
        fb = "" if b["batch"] == first["batch"] else " --jp-fallback"
        head += (f"\n`uv run python {p['tools']}/build_context.py --batch {b['batch']}"
                 f" --profile cc --baseline {baseline}{p['repo_arg']}{fb}`")
    head += f"""

Expected: 各批生成 `context.md`/`source.jsonl`/`manifest.json`。**只有首批 {first["batch"]} 的 `ctx_sha` 现在有效**（它的前缀是真译文，也正是译者要读的那份）；其余批的 `ctx_sha` 以 Step 3.N 重生成后的值为准，不要用这一步的输出去 append。

**开工前硬检查**：确认 {ns} 各批 `manifest.json` 的 `glossary_v` **全部相同**。不同即说明本组跨越了 glossary 版本变更，**必须拆组重生成**（spec §4.3：对话里规则书只投一次，跨版本即过期）。

- [ ] **Step 2: 派一个译者子代理，按 `prompts/translator_cc.md` 的「长对话会话模式」一节连做 {len(batches)} 批**

注入：车道根、批次序列 {ns}、以及「首批 {first['batch']} 读全量 `{p['ctx']}/batch_{first['batch']}/context.md`，其余批只读 {rest_srcs} + `{lane_root}/glossary/style.md` + `{lane_root}/glossary/active.json`」。

**明令译者：除首批外，其余批的 `context.md` 一律不得读取。** 会话模式本就不读它，而 Step 1 给这些批出的是 `--jp-fallback` 档案——第二节前缀里带 `〔未译|…〕` 占位，读了只会把占位当既有译文去对齐。

每批译完即走 Step 3 的三件校验并入库，再进入下一批。
"""
    for b in batches:
        n = b["batch"]
        # 崩溃探测的处置指引必须与 _batch_task 等价：detect_collapse.main() 无条件
        # return 0，K>0 时若无人眼过目，这道顾问级闸在操作者视野里等于不存在。
        # 会话组曾把它写成裸命令行（无 Run/Expected、无处置指引），复评指出后补齐。
        collapse = (f"""

Run: `{p['env']}uv run python {p['tools']}/detect_collapse.py --batch {n}{p['lane_dir_arg']}{thresholds_arg}`
Expected: `batch_{n}: 崩溃探测 K 条 (C1=.. C2=.. C3=..)`。本工具**恒返回 0**，不会自己拦流水线——K=0 直接入库；K>0 时打开 `{p['out']}/batch_{n}.collapse.json` 逐条人眼过目：确认是误报还是真崩溃（整行漏译、复读、长度离群）。真崩溃需回本组的翻译环节重出该批译文、重跑本步与上一步。把命中数（按 C1/C2/C3 分类）记进本批记录，供{"段末流程" if segment else "检查点"}汇总参考。"""
                    if p["lane_dir_arg"] else "")
        # 首批的重生成是恒等重跑（Step 1 出它时本就是正常模式）。仍照跑：每批
        # 同形，操作者不必临场判断哪批该跑，也就不会跑漏真正需要重生成的那些批。
        identity = ("本批即本组首批，这里是**恒等重跑**（Step 1 出它时就是正常模式），"
                    "照跑即可——每批同形，免得临场判断哪批该跑。"
                    if n == first["batch"] else "")
        head += f"""
- [ ] **Step 3.{n}: 批次 {n} 校验与入库**（**严格按批号顺序**做，前一批入线是后一批 ctx 重生成的前提）

Run: `uv run python {p["tools"]}/build_context.py --batch {n} --profile cc --baseline {baseline}{p["repo_arg"]}`
Expected: **正常模式重生成本批 ctx（不带 `--jp-fallback`）**——此刻批次 {n} 之前的各批译文都已入线，前缀能完整渲染。这一步覆盖 Step 1 留下的 fallback 档案，并给出本批**真** `ctx_sha`（下面 `append_forward --ctx` 用的就是它，审计链因此不留 fallback 残迹）。{identity}若这里报「前缀行 N 未译」，说明上一批漏了 `append_forward`，**回去补上再回来**，**不许加 `--jp-fallback` 绕过**。

Run: `{p["env"]}uv run python {p["tools"]}/check_batch.py --batch {n}{p["lane_dir_arg"]}`
Expected: `batch_{n}: PASS  warn=K`（`hard=0` 即可）。若输出 `FAIL`，按 `{p["out"]}/batch_{n}.check.json` 逐条修回本批 `draft.jsonl`，重跑本步直到 PASS。**若打印「⚠ W4 未启用」说明复现句族一致性没被检查**——补 `--lane-dir` 重跑，不要把它当成通过。{collapse}

Run: `{p["env"]}uv run python {p["tools"]}/append_forward.py --batch {n} --backend cc --model <model> --ctx <ctx_sha> --glossary-v {glossary_v}`

```bash
git add {p["forward"]}
git commit -m "data: {b["chapter"]} 批次{n} 译文入线"
```
"""
    return head.rstrip()


def _checkpoint_task(tnum, first, last, chapters, p, lane_mode=False, segment=None):
    """chapters：本 chunk 涉及的真实章别（去重、升序），不是计划的 label——
    连续段模式下一个 chunk 可能横跨多章，label 拼出的笔记文件路径在这种场景下
    永远不存在（fix round 1 发现的文案错位）。

    lane_mode=True 时最前面插一步冻结校验（终审 C1 item 2）：每个检查点都是
    "继续派发下一段之前"的天然关口，若两条车道的冻结快照已经漂移（比如仓库
    glossary 被误改后又有人重跑了 setup），必须在这里拦下，而不是等到章末
    才发现。"""
    verify_step = ""
    if lane_mode:
        # M6：段模式换段语汇。lane_setup 恒用主仓 tools/（终审 C1）。
        stop = "**立即停止本段**，报告人工裁决" if segment else "**立即停止试点**，报告人工裁决"
        where = "（在主仓执行）" if segment else ""
        verify_step = f"""
- [ ] **Step 0: 冻结校验**{where}

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。若报出漂移，{stop}，不要继续派发下一批——漂移意味着两条车道的术语/骨架基准已经不再可比。
"""
    if segment:
        adjudicate = ("本段进行中**只清点归档、不裁决**：把提案原样留在文件里，不新增 "
                      "`glossary.vN.yaml`、不改 `glossary/active.json`，裁决集中到"
                      "本计划末尾「段末流程」指向的段末小裁决会话。")
    else:
        adjudicate = ("试点期间**只清点归档、不裁决**：把提案原样留在文件里，不新增 "
                      "`glossary.vN.yaml`、不改 `glossary/active.json`，裁决推迟到试点结束。")
    ch_str = "、".join(chapters)
    files = "、".join(f"`{c}.md`" for c in chapters)
    return f"""### Task {tnum}: CHECKPOINT——批次 {first}–{last} 术语提案裁决 + 抽查
{verify_step}
到这里已完成 {ch_str} 章批次 {first}–{last} 的翻译入库。继续下一批之前做以下几件事：

- [ ] **Step 1: 术语提案裁决**

查看 `{p["notes"]}/` 下本段涉及的 {files}（文件不存在说明该章本轮没有提案，跳过即可）：里面是译者/评审子代理发现的、`glossary/active.json` 未覆盖或疑似有问题的定译词建议。{adjudicate}

- [ ] **Step 2: 抽查**

从批次 {first}–{last} 已入库的译文里随机抽 2–3 条，对照对应 `{p["ctx"]}/batch_*/source.jsonl` 的原文与 `{p["forward"]}` 的译文：核对术语一致性、【说话人】前缀、锚点行是否逐字沿用。怀疑有问题时可按 `prompts/reviewer_cc.md` 派一个评审子代理复核（复核意见只作参考，不直接改 `{p["forward"]}`——它是 append-only 正向线）。"""


def _sibling_display(lane_cfg):
    """对方车道根用占位符，不在生成时解析成具体路径——和本文件里 `<model>`/
    `<ctx_sha>` 是同一种约定（执行者按上下文自己填），不是漏做。刻意如此：
    若在生成期把 "pilot/lanes/fable" 这类具体路径字面写进 opus 计划文件里，
    这份计划本身就"知道"另一条车道的存在与路径，读起来像是两条车道并不是
    真正互相独立生成的——与"两份计划各自只谈自己车道"的隔离精神相悖，也是
    终审自查清单里 `grep -c 'pilot/lanes/fable' translate-pilot-opus.md` 必须
    为 0 这条硬性要求的来由。"""
    return (f"<对方车道根——{Path(lane_cfg['lane_dir']).parent}/ 下除 "
            f"{lane_cfg['lane']} 外的另一条车道目录，执行时按当次试点实际"
            f"车道配置填入>")


def _hardstop_after_batch1(tnum, lane_cfg, p):
    """spec §3.3「隔离验收（batch 1 完成后立即执行，不通过则停止试点）」+
    §3.3「每批派发前校验冻结未漂移」的开跑前一次性版本。"""
    d = lane_cfg["lane_dir"]
    sib = _sibling_display(lane_cfg)
    return f"""### Task {tnum}: 硬停——batch 1 隔离验收（不通过则停止试点）

批次 1 已入库。**在继续 batch 2 之前必须做完以下检查，任一项不通过就停止试点、报告人工，不要往下派发**：

- [ ] **① 隔离验收——两条车道确实互不可见**

Run: `diff {d}/data/forward.jsonl {sib}/data/forward.jsonl`
Expected：**有差异**（`diff` 非零退出码，即两个文件不完全相同）。若输出为空，说明两条车道读到了同一份译文，双车道对照已经退化——立即停止试点。

再 Run（仅为核验隔离而提前生成一次，产物会被下面「batch 2 译文入库」任务的 Step 1 正常覆盖，无副作用）：

`{p["env"]}uv run python tools/build_context.py --batch 2 --profile cc --baseline none{p["repo_arg"]}`

然后核对：从 `{p["forward"]}` 里挑本车道 batch 1 译出的任意一行 zh 片段，`grep` 能在 `{p["ctx"]}/batch_2/context.md` 第二节「前缀正文」里找到。
Expected：能找到；找不到说明本车道下一批的前缀没有正确读到本车道自己的译文。

- [ ] **② 冻结校验**

Run: `uv run python tools/lane_setup.py --verify`
Expected: `冻结校验：无漂移`。

- [ ] **③ 人工抽读**

从本车道 batch 1 的译文里抽 3–5 条对照原文通读，粗筛是否符合中文可读性/术语口调/全知纪律基本水准（正式三栏 rubric 见 spec §6.5，这里只做粗筛，不必按盲评格式）。

- [ ] **④ 门禁**

**①②③任一项不通过，立即停止试点、报告人工裁决，不要继续派发 batch 2。** 全部通过才能继续下一个任务。"""


def _hardstop_after_batch2(tnum, lane_cfg, p, label, first_all, last_all):
    """spec §5.2「batch 1、batch 2 完成后各硬停一次」的第二次；同时承载
    I-extra（崩溃阈值标定值固化去处）：把标定结果写进 pilot-manifest.json，
    并在标定值偏离默认时指示重出计划以固化进后续批次命令行。"""
    return f"""### Task {tnum}: 硬停——batch 1–2 崩溃阈值标定 + 人工抽读（不通过则停止试点）

批次 1–2 已入库，两批都已跑过各自 Task 里的语义崩溃探测步骤。**在继续 batch 3 之前完成以下三项**：

- [ ] **① 用真实译文标定 detect_collapse 三个阈值**

对照 `{p["out"]}/batch_1.collapse.json` 与 `{p["out"]}/batch_2.collapse.json` 的命中，结合两批真实译文，人工判断 `--kana-max`/`--ratio-lo`/`--ratio-hi` 三个阈值（默认值见 `tools/detect_collapse.py` 常量注释）是否需要针对本次试点重新标定。把最终使用值写入 `pilot/lanes/pilot-manifest.json`（保留其余键，只加/改 `collapse_thresholds` 这一段）：

```bash
uv run python -c "
import json
p = 'pilot/lanes/pilot-manifest.json'
d = json.load(open(p, encoding='utf-8'))
d['collapse_thresholds'] = {{'kana_max': <值>, 'ratio_lo': <值>, 'ratio_hi': <值>}}
json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
"
```

若标定值与 `tools/detect_collapse.py` 默认值相同：无需其他动作，后续批次继续用当前命令行。
若不同：**必须重新生成本计划**——对本车道重跑（带上标定值；`--lane` 用本计划批次原本所属的 lane，通常是 `main`）：

`uv run python tools/gen_plan.py --lane main --batches {first_all}-{last_all} --label {label} --lane-dir {lane_cfg["lane_dir"]} --model {lane_cfg["model"]} --effort {lane_cfg["effort"]} --append-model-id {lane_cfg["append_model_id"]} --kana-max <值> --ratio-lo <值> --ratio-hi <值>`

用新计划覆盖当前文件（同一 `--label` 会写回同一路径 `docs/superpowers/plans/translate-{label}.md`），从 batch 3 对应的任务继续执行——新计划里 batch 3 起的 Step 4 检测命令会带上标定值。**batch 1、2 已入库的译文不受影响**（`{p["forward"]}` 是 append-only 正向线，重出计划不会动它）。

- [ ] **② 人工抽读**

同 batch 1 硬停的抽读粒度，这次对 batch 2 抽 3–5 条。

- [ ] **③ 崩溃探测命中逐条过目**

`{p["out"]}/batch_1.collapse.json` 与 `{p["out"]}/batch_2.collapse.json` 里的每一条命中（不论 C1/C2/C3）都要人眼确认是误报还是真崩溃；真崩溃需回对应批次的 Step 2 重新出译文、重跑 Step 3–4。

- [ ] **④ 门禁**

**①②③任一项发现真实问题且未处理，立即停止试点、报告人工裁决。** 全部通过才能继续下一个任务。"""


def _window_probe_task(tnum, batch_n, lane_cfg, p):
    """spec §6.4 窗口对撞探针：同一模型对同一批分别用窗口前缀（cc）与全前缀
    （api-A）各出一版译文，人工比对是否丢信息。终审 I6：build_context 的
    ctx_dir 不含 profile，两次调用会原地互相覆盖同批 context.md/manifest.json、
    写进 forward 的 ctx_sha 也会记错——不改产码，靠这里强制用临时车道副本
    规避（`cp -r` 出来，跑完删除，不落地到正式车道）。"""
    d = lane_cfg["lane_dir"]
    tmp = f"/tmp/lane-probe-{lane_cfg['lane']}-{batch_n}"
    return f"""### Task {tnum}: 探针——batch {batch_n} 窗口对撞（cc vs api-A 前缀对比，回答"压缩是否丢信息"）

batch {batch_n} 是压缩窗口生效后的第一批（spec §2），此刻已随正常流程入库。用**同一模型、同一 effort**在**临时车道副本**上分别以窗口前缀（`--profile cc`）与全前缀（`--profile api-A`）各出一版上下文，人工并排比对两版译文，回答"压缩触发瞬间是否丢信息"。

**必须用临时副本、不得覆盖正式车道产物**（`build_context.py` 的 `ctx_dir` 不含 profile，若 `--repo` 直接指到正式车道 `{d}`，`--profile api-A` 会原地覆盖 `{d}/work/ctx/batch_{batch_n}/context.md`，写进 `{p['forward']}` 的 `ctx_sha` 会记错——I6）：

- [ ] **Step 1: 建临时副本**

Run: `cp -r {d} {tmp}`

- [ ] **Step 2: 两版上下文**

```bash
uv run python tools/build_context.py --batch {batch_n} --profile cc --baseline none --repo {tmp}
cp {tmp}/work/ctx/batch_{batch_n}/context.md {tmp}-cc.md
uv run python tools/build_context.py --batch {batch_n} --profile api-A --baseline none --repo {tmp}
cp {tmp}/work/ctx/batch_{batch_n}/context.md {tmp}-api-a.md
```

- [ ] **Step 3: 两版译文**

按 `prompts/translator_cc.md` 分别用两份 context.md（`{tmp}-cc.md` 与 `{tmp}-api-a.md`）派子代理各出一版译文（同一模型、同一 effort，只换上下文）。**不要把任一版写回 `{p['forward']}`**——这是探针，不是正式批次产出，不参与入库。

- [ ] **Step 4: 并排人工比对 + 清理**

对照两版译文：窗口版（cc）出现全前缀版（api-A）没有的指代错误/前情误解，即为窗口丢信息的直接证据；若两版无实质差异，即为"压缩未丢信息"的证据。结论写进试点报告（含 §1 声明的"不能回答"边界：这仍只是段内唯一一次压缩跃迁的单点观测，不能外推到深层前缀）。完成后删除临时副本：`rm -rf {tmp}*`。"""


def _final_task(tnum, chapters, lane, first, last, count, p, lane_mode=False,
                segment=None):
    """chapters：本计划全部批次涉及的真实章别（去重、升序），与 `_checkpoint_task`
    的 chapters 参数同规格——不能再用 label（`--batches` 连续段模式下 label
    只是计划名，不是任何批次的真实章别；用它拼「skeleton/cards.zh/ 的 <label>
    章梗概卡」会指向一个不存在的东西，见 hotfix-d-brief.md 缺陷 1）。
    单章（含 --chapter 模式，chapters 恰好一个元素）时文案退化回原来的「本章」
    表述，保持自然；跨章别连续段时改用「本段」，并显式提醒某些章可能只覆盖
    了一部分，不要按整章完结的标准核对梗概。"""
    ch_str = "、".join(chapters)
    header = (f"{ch_str} 章 {lane} 车道全部 {count} 个批次（{first}–{last}）"
              f"已入库 `{p['forward']}`。收尾前做两件事：")
    if len(chapters) == 1:
        step1 = (
            f"对照本章对应的章节梗概卡（`skeleton/cards.zh/`，见 `CLAUDE.md`"
            f"「卡片分类」节「章节梗概卡」条目）与本章刚入库的 `{p['forward']}` "
            f"正文译文：核对人物称呼（双层人名——现实层汉字/故事层片假名，见 "
            f"`CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否和 "
            f"`skeleton/anchors.yaml` 一致，尤其检查有没有在本章尚不该点破的地方"
            f"提前泄露后续真相（全知纪律，`glossary/style.md`）。")
    else:
        step1 = (
            f"对照本段涉及的各章章节梗概卡（`skeleton/cards.zh/` 中 {ch_str} "
            f"各章对应卡，见 `CLAUDE.md`「卡片分类」节「章节梗概卡」条目）与本车道"
            f"刚入库的 `{p['forward']}`：核对人物称呼（双层人名——现实层汉字/"
            f"故事层片假名，见 `CLAUDE.md`「剧情核心」节）、关键道具/母题译名是否"
            f"与 `skeleton/anchors.yaml` 一致，尤其检查有没有在本段尚不该点破的"
            f"地方提前泄露后续真相（全知纪律，`glossary/style.md`）。**注意本段是"
            f" timeline 连续段而非完整章，某些章可能只覆盖了一部分，不要按"
            f"「整章完结」的标准要求梗概吻合。**")
    return f"""### Task {tnum}: {"段末" if segment else "章末"}——梗概回译自检 + 人工评审 gate

{header}

- [ ] **Step 1: 梗概回译自检**

{step1}

- [ ] **Step 2: 人工评审 gate**

把本计划产生的 {count} 个 `data: <chapter> 批次N 译文入线` commit（批号 {first}–{last}，`<chapter>` 各批不同，见各批 Task 的 Step {"5" if lane_mode else "4"}）交给人工复核。**不要自动放行**——人工确认无误后本计划才算完成，之后才能继续对后续批次跑 `tools/gen_plan.py` 生成新计划。"""


_THRESHOLD_FLAGS = (("kana_max", "--kana-max"), ("ratio_lo", "--ratio-lo"),
                    ("ratio_hi", "--ratio-hi"))


def _thresholds_arg(collapse_thresholds):
    """把 {"kana_max": 0.05, ...} 转成要拼进 detect_collapse 命令行的字符串。
    None 或空字典 → ""（沿用 tools/detect_collapse.py 自己的默认值，不在
    命令行里重复写一遍）；只给部分键时只拼那几个 flag，其余仍走工具默认——
    I-extra：崩溃阈值标定值固化去处，见 spec §6.3 缺口与 batch 2 硬停任务。"""
    if not collapse_thresholds:
        return ""
    return "".join(f" {flag} {collapse_thresholds[key]}"
                   for key, flag in _THRESHOLD_FLAGS if key in collapse_thresholds)


def render(sel, label, lane, every=5, baseline="none", glossary_v=GLOSSARY_V,
           lane_cfg=None, collapse_thresholds=None, segment=None,
           tools_root="", segment_sub=None, session_size=1,
           session_lines=SESSION_LINES_MAX) -> str:
    p = _paths(lane_cfg, tools_root)
    thresholds_arg = _thresholds_arg(collapse_thresholds)
    chapters_all = sorted({b["chapter"] for b in sel})
    parts = [_header(label, lane, every, len(sel), glossary_v, lane_cfg, chapters_all,
                     segment, tools_root)]
    if segment:
        parts.append(_segment_head(segment, tools_root, segment_sub))
    if not sel:
        parts.append(f"（`data/batches.jsonl` 中没有选中的批次，无事可做。）")
        if segment:
            parts.append(_segment_tail(segment))
        return "\n\n".join(parts)
    tnum = 1
    chunk = []
    batch_task_count = 0
    groups = _group_sessions(sel, session_size, session_lines)
    for grp in groups:
        if len(grp) == 1:
            parts.append(_batch_task(tnum, grp[0], baseline, glossary_v, p,
                                     thresholds_arg, segment=segment))
        else:
            parts.append(_session_task(tnum, grp, baseline, glossary_v, p,
                                       thresholds_arg, segment=segment))
        tnum += 1
        batch_task_count += len(grp)
        # 硬停：车道模式下生效，非车道模式（lane_cfg is None）零改动——
        # 终审 C1 item 3，位置紧跟第 1、第 2 个批次任务（不是全局 batch id
        # 恰好为 1/2，而是本计划里的第 1、第 2 个批次任务，语义上等价——但
        # 这个等价只在「计划恒从全局 batch 1 开始」的试点模式（segment is
        # None）下成立：两个模板里硬编码了字面量 --batch 2、batch_1/2.
        # collapse.json 等，P3 段模式（segment 非 None）的计划通常从段起始
        # 批（比如 SEG-1 的 36）开始，这些字面量会指向不相关批次，检查必然
        # 失败。段模式因此不生成这两个硬停任务——段计划有自己的门（段开场
        # 自检/段末流程，_segment_head/_segment_tail），P2 试点模式行为不变。
        #
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
            chapters = sorted({c["chapter"] for c in chunk})
            parts.append(_checkpoint_task(tnum, chunk[0]["batch"], chunk[-1]["batch"],
                                          chapters, p, lane_mode=lane_cfg is not None,
                                          segment=segment))
            tnum += 1
            chunk = []
    # 窗口对撞探针：车道模式下、且本次选中的批次里真的含 batch 33 时才生成
    # （终审 C1 item 4，位置在最后一个批次任务之后、终任务之前）。
    if lane_cfg is not None and any(b["batch"] == WINDOW_PROBE_BATCH for b in sel):
        parts.append(_window_probe_task(tnum, WINDOW_PROBE_BATCH, lane_cfg, p))
        tnum += 1
    parts.append(_final_task(tnum, chapters_all, lane, sel[0]["batch"], sel[-1]["batch"],
                             len(sel), p, lane_mode=lane_cfg is not None,
                             segment=segment))
    if segment:
        parts.append(_segment_tail(segment))
    return "\n\n".join(parts)


def _parse_range(s):
    m = __import__("re").fullmatch(r"(\d+)-(\d+)", s.strip())
    if not m:
        raise SystemExit(f"--batches 需形如 1-35，收到 {s!r}")
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo > hi:
        raise SystemExit(f"--batches 区间下界大于上界：{s!r}")
    return lo, hi


def segment_entry(label, repo=None):
    """config/segments.yaml 里 label 段的完整条目（含 batches/lane 等字段）。
    终审 devwave1 task 4：`--lane` 与 `--segment` 曾无交叉校验，错配只会静默
    产出空计划（select() 按 lane 过滤，段号对但车道错时选中的批次恰好是空集）；
    这里把段表条目整个交出来，供 main() 既读批号又读 lane 做交叉校验。"""
    import yaml
    p = Path(repo or REPO) / "config" / "segments.yaml"
    segs = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    for s in segs:
        if s["label"] == label:
            return s
    raise SystemExit(
        f"{p} 中没有 label={label!r} 的检查段；已有："
        f"{', '.join(s['label'] for s in segs)}")


def segment_subrange(label, seg_lo, seg_hi, batches_arg):
    """段模式下 `--batches` 的取值判定（终审 I6）。

    段模式的批号本应由段表读出，但 `--batches` 仍能覆盖它且**无任何交叉校验**：
    `--segment seg2-s3 --batches 36-62` 实测 rc=0，产出一份标题写着 seg2-s3、
    内容却是 SEG-1 批次的生产计划。合法用途只有一个——段内断点续跑（只重生成
    本段剩余批次的计划），故允许**真子区间**，越出段表区间一律报错。

    返回 (rng, sub)：sub 为 None 表示整段，否则为被限定的子区间（供计划抬头标注）。
    """
    if not batches_arg:
        return (seg_lo, seg_hi), None
    lo, hi = _parse_range(batches_arg)
    if lo < seg_lo or hi > seg_hi:
        raise SystemExit(
            f"--batches {lo}-{hi} 越出段表 {label} 的区间 {seg_lo}-{seg_hi}——"
            f"段模式的批号由段表读出，`--batches` 只允许给出段内**子区间**"
            f"（断点续跑用）。要跑别的批次请换 --segment，或用 --batches + --label "
            f"的非段模式。")
    if (lo, hi) == (seg_lo, seg_hi):
        return (lo, hi), None
    return (lo, hi), (lo, hi)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=False,
                    help="非段模式必填；段模式可省略——省略时取 config/segments.yaml "
                         "段表登记的 lane，显式给出且与段表不符时报错")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--chapter")
    g.add_argument("--batches", help="连续段批号闭区间，形如 1-35；"
                                     "与 --segment 同给时覆盖段表批号")
    ap.add_argument("--label", help="--batches 模式下的计划名（必填）")
    ap.add_argument("--checkpoint-every", type=int, default=5)
    ap.add_argument("--lane-dir")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--append-model-id")
    ap.add_argument("--kana-max", type=float,
                    help="I-extra：batch 1-2 硬停标定后固化进后续批次 detect_collapse 命令行")
    ap.add_argument("--ratio-lo", type=float)
    ap.add_argument("--ratio-hi", type=float)
    ap.add_argument("--segment", help="检查段 label（config/segments.yaml）：批号由段表"
                                      "读出，并生成段自检/段末流程块")
    ap.add_argument("--tools-root", default="",
                    help="按批四件套（build_context/check_batch/detect_collapse/"
                         "append_forward）的工具树根（生产 worktree 绝对路径）；"
                         "留空＝主仓相对 tools/（非段模式行为不变）")
    ap.add_argument("--session-size", type=int, default=1,
                    help="一条对话连做几批（spec §5.6 上限 10）；1=逐批模式，"
                         "输出与改造前逐字相同")
    ap.add_argument("--session-lines", type=int, default=SESSION_LINES_MAX,
                    help=f"一条对话的行数上限（默认 {SESSION_LINES_MAX}，实测包络 585）；"
                         f"与 --session-size 是**双重上限**，任一超限即切组")
    args = ap.parse_args(argv)

    if args.session_size < 1:
        raise SystemExit("--session-size 必须 ≥1")
    if args.session_size > SESSION_MAX:
        raise SystemExit(
            f"--session-size {args.session_size} 超过上限 {SESSION_MAX}"
            f"（spec §5.6：10 批/585 行是已验过的范围，更长未测）")
    if args.session_lines < 1:
        raise SystemExit("--session-lines 必须 ≥1")

    lane_params = [args.lane_dir, args.model, args.effort, args.append_model_id]
    if any(lane_params) and not all(lane_params):
        raise SystemExit("--lane-dir/--model/--effort/--append-model-id 要么全给要么全不给")
    lane_cfg = None if not all(lane_params) else {
        "lane": Path(args.lane_dir).name, "lane_dir": args.lane_dir,
        "model": args.model, "effort": args.effort,
        "append_model_id": args.append_model_id}

    seg_sub = None
    if args.segment:
        if args.chapter:
            raise SystemExit("--segment 与 --chapter 互斥")
        seg_entry = segment_entry(args.segment)
        seg_lane = seg_entry.get("lane")
        if args.lane is None:
            if seg_lane is None:
                raise SystemExit(
                    f"--lane 必填（段表 {args.segment} 未登记 lane，无法从段表推导）")
            lane = seg_lane
        else:
            if seg_lane is not None and args.lane != seg_lane:
                raise SystemExit(
                    f"--lane {args.lane} 与段表 {args.segment} 的 lane={seg_lane} 不符")
            lane = args.lane
        if not args.tools_root:
            raise SystemExit(
                "--segment 模式必须给 --tools-root（生产 worktree 绝对路径，见 "
                "docs/ops/p3-production-runbook.md §3）——漏传会产出未钉死的计划")
        lo, hi = (int(x) for x in seg_entry["batches"])
        rng, seg_sub = segment_subrange(args.segment, lo, hi, args.batches)
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=lane, batch_range=rng)
        label = args.label or args.segment
    elif args.batches:
        if args.lane is None:
            raise SystemExit("--lane 必填")
        lane = args.lane
        if not args.label:
            raise SystemExit("--batches 模式必须同时给 --label")
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=lane,
                     batch_range=_parse_range(args.batches))
        label = args.label
    elif args.chapter:
        if args.lane is None:
            raise SystemExit("--lane 必填")
        lane = args.lane
        sel = select(read_jsonl(DATA / "batches.jsonl"), lane=lane,
                     chapter=args.chapter)
        label = args.chapter
    else:
        raise SystemExit("需给 --chapter / --batches / --segment 之一")

    collapse_thresholds = {k: v for k, v in (("kana_max", args.kana_max),
                                             ("ratio_lo", args.ratio_lo),
                                             ("ratio_hi", args.ratio_hi))
                          if v is not None} or None
    md = render(sel, label=label, lane=lane, every=args.checkpoint_every,
                glossary_v=glossary_version(REPO), lane_cfg=lane_cfg,
                collapse_thresholds=collapse_thresholds, segment=args.segment,
                tools_root=args.tools_root, segment_sub=seg_sub,
                session_size=args.session_size, session_lines=args.session_lines)
    out_path = REPO / "docs" / "superpowers" / "plans" / f"translate-{label}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"{out_path}: {md.count('### Task')} 个任务")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
