"""P4 润色 pass：裁决意图归纳 + 放大扫描装配（Task 9）。

段末人工裁决只处理 K≈150 条（`config/polish.yaml` 的 `K`），但裁决体现的
判断尺度理应适用于整个 SEG。本模块把这份小样本裁决"放大"成两件产物：

1. `digest(label) -> str`：把 `decisions.jsonl` 里的人工裁决按 `reason_code`
   归纳成一份意图纪要（原因码分布表 + 每码 ≤3 个代表例：jp/opus/候选/最终
   zh/裁决语），**追加**写入 `frozen/rulings.md`（spec §7.4：
   `polish_context.render()` 已经会读这个文件，见 Task 4 fix round 1——
   纪要写进去之后，本 SEG 后续会话、乃至未来章节的 render() 都会自动带上
   它，不需要本模块再操心"怎么传下去"）。
2. `scan_prompt(label) -> str`：纪要 + 整 SEG 四桶结果全景（**含桶 3 落选
   句全文**——这是放大扫描存在的唯一理由：这些候选曾经产生过真实改动，
   却因 K 配额或抽检未命中而从未被人看过，默认原样保留 opus）+ 与生产批
   一致的输出契约（channel 固定 `amplify`）。
3. 轮数闸：`frozen/rulings.md` 里一个不会被自然文本撞到的标记
   （`<!-- amplify-round:N -->`）达到 `CFG["amplify_rounds"]`（默认 1）就
   拒绝再装配——**每段最多放大一轮**。**2026-08-07 修正**：标记不在
   `scan_prompt()` 装配成功时写（那只是"渲染看看"，SEG-1 实测证明装配
   之后完全可能被临时放弃执行），改在 `polish_ingest.ingest()` 以
   `channel="amplify"` 把这一轮全部批号**真正入仓完毕**时，由
   `mark_round_if_complete()` 写入——见该函数与 `scan_prompt()` 文档字符串。

放大产物的回炉路径不在本模块之内：模型按输出契约产出 `raw/amplify/b<N>
.out`，`polish_ingest --channel amplify` 原样入仓、`polish_triage`（Task 7
已保证 `channel=="amplify"` 恒不 autoclear）分流、人工追加小裁决、
`polish_commit` 清关——本模块只负责"喂出正确格式的下一轮 prompt"这一步。

## 设计点 0：桶 2 全景必须渲染每一条裁决的最终 zh（评审 Finding A，已修复）

`AMPLIFY_PREAMBLE` 明确要求模型对桶 2（已裁决）的行"`zh` 请照抄裁决结果
里的最终译文，不要回退去抄更早的候选或 opus"。初版实现里，唯一渲染"最终
zh"的地方是 `_build_digest_text()` 里**每个原因码最多 3 条**的代表例——
`_build_panorama()` 的桶 2 小节只渲染了 `verdict`/`reason_code`，从不
渲染最终译文本身。评审实测：单个原因码聚集 5 条 `verdict="edit"` 裁决时，
第 4/5 条的 `edited_zh` 在整份 `scan_prompt()` 输出里完全不出现——工具
要求模型"照抄"一段它从未被展示过的文本，只能猜或重建，而失真的恰恰是
价值密度最高的那批（人工重写稿，既不同于 opus 也不同于任何通道候选）。
K≈150 的真实规模下，单原因码 >3 条是大概率事件，不是边界情形。

**修法（评审建议的方案，本次采纳）：让 `_build_panorama()` 的桶 2 渲染
对每一个已裁决的 id 都展示实际最终 zh**，不再依赖 digest 里限量的代表例
兜底这件事。新增共享 helper `_final_zh_for_decision(dec, all_cands,
id2opus)`（按 `dec["chosen_channel"]` 查该决策实际参照的候选行、代入
`_decision_final_zh()` 同一套 adopt/edit/keep_opus 规则），`_build_
digest_text()` 与 `_build_panorama()` 都改用这同一个 helper，避免两处
各自维护一份"怎么算最终 zh"的逻辑而互相漂移。桶 2 小节现在对**每个**
已裁决 id（不再受"每码 ≤3 条"限制——那个限制只该约束 digest 的"代表例"
篇幅，不该限制模型能否看到自己被要求照抄的文本）都追加一行"裁决后最终
zh"；若该 id 的最新决策缺少可算出的最终译文（比如 `verdict="edit"` 却
没填 `edited_zh`），显式标注"（决策缺少最终译文，需人工确认）"而不是
静默留白。变异自检①专门验证"去掉这一行渲染，测试必须真红"。

## 设计点 1：`verdict="auto"` 决策不计入人裁意图分布

`decisions.jsonl` 里 `verdict="auto"` 的记录是 `polish_commit.commit()` 对
autoclear-and-not-sampled 候选**自动铸造**的（`reason_code` 恒为字面量
`"autoclear"`，`edited_zh` 恒为 `None`，见 `tools/polish_commit.py` 第
305-310 行）——这条记录里没有任何人的判断，只是"机械闸+配额算法批准通过"
这件事本身的存档。把它计入"人裁意图"分布会有两个坏处：
- 用一个不代表任何审美/术语/语序取舍的类别（字面量 `"autoclear"`）冲淡
  真正有信息量的类别（量词/语序/补主语/术语/…）在分布表里的占比；
- "代表例"环节可能抽到一条根本没有人工裁决语的记录（`edited_zh=None`，
  没有人写过"为什么这么改"），破坏"代表例=可读的裁决案例"这个契约。

裁定：`digest()` 只统计 `verdict in {"adopt", "edit", "keep_opus"}` 的
记录（brief 给的 verdict 枚举里唯三种真正代表人工判断的取值），
`verdict == "auto"` 一律跳过，不进分布表、不进代表例。变异自检②专门
验证"混进一条 auto 决策后，分布表/代表例里都不应该出现字面量 autoclear
这一类，且总计数不受影响"。

## 设计点 2：轮数闸的标记形态与检测（2026-08-07 修正：标记改由 ingest 侧写）

标记是一行只会由本模块写入、且不会被"看起来像它"的普通中文正文撞到的
字符串：`<!-- amplify-round:N -->`（HTML 注释语法，`rulings.md` 是纯
markdown，人工/模型都不会往里面写字面意义上的 HTML 注释；`N` 是这是第几
轮）。检测用一个锚定单行的正则统计 `frozen/rulings.md` 全文里出现过多少
条这种标记，与 `CFG["amplify_rounds"]` 比较——**次数达到上限就拒绝**
（`>=`，不是 `>`：`amplify_rounds=1` 时，已经出现过 1 条标记就该拒绝第
2 次装配，不是要等出现第 2 条才拦）。

**缺陷（SEG-1 实测暴露）与修正**：初版把标记写在 `scan_prompt()` 装配
成功之后——这把"渲染看看这份 prompt 长什么样"与"真的跑完了一轮放大扫描"
两件事混为一谈。SEG-1 段末装配过一次 `scan_prompt()`（想看看内容），随后
判断桶 3 已经空了、收益已经提前兑现，主动放弃执行——没有派发任何子代理、
没有产出 `raw/amplify/`、没有 `polish_ingest --channel amplify` 入仓过
一行。但轮数闸只看"装配过几次"，`frozen/rulings.md` 里已经留下一条
`<!-- amplify-round:1 -->`，把根本没发生过的事记成了发生过——这正是
`CLAUDE.md` 反复强调的"静默写错比报错更坏"的具体案例：往后任何一次
`--seg seg1-s2 --scan-prompt` 都会被这条假标记拒绝，而拒绝的理由
（"已经跑过一轮"）是假的。

**修正**：标记不再由 `scan_prompt()` 写，改由 `mark_round_if_complete()`
在 `polish_ingest.ingest()` 侧、且仅当 `channel == "amplify"` 的入仓
**真正覆盖了这一轮要求的全部批号**时才写（见下方新函数）。`scan_prompt()`
本身仍然读同一条标记做轮数闸判断（"这一轮是否已经真正跑完，跑完了就
拒绝再装配"），但**不再是标记的写入方**——装配 prompt 只是"看看/准备
派发"，不再消耗轮次配额；配额只在模型输出真正入仓、覆盖到这一轮全部批号
那一刻才被消耗。这意味着 `scan_prompt()` 现在可以被反复调用（比如纪要
更新后想重渲染一份新的 prompt 再派发），直到真的有一轮被完整入仓为止。

`digest()` 本身**不**受这道闸约束、也不写这个标记——`digest()` 只是纪要
写入，可以被调用任意次（比如中途想先看看归纳结果长什么样，或者纪要要
反复微调后再触发真正的装配）；真正稀缺、要限流的资源是"发给模型的整
SEG 装配 prompt"这个动作本身（对应 `scan_prompt()`），不是"看一眼纪要"
这个动作。

## 设计点 3：raw 落盘粒度——按批（`raw/amplify/b<N>.out`），不是整段一个文件

`polish_ingest.ingest(label, channel, batch)` 的批级幂等（`ingested.
<channel>.json` 记的是"批号"）与覆盖完整性检查（"批内非锁定 id 是否在
这份 raw 里全部出现过"）**都是按批做的**，且 `raw` 路径本身就写死是
`raw/<channel>/b<batch>.out`——这不是本模块可以自由选择的接口，是
`polish_ingest.py` 已经存在、且本任务被要求"直接复用、不改动"的既定
契约。若把整段输出成一个文件，`ingest()` 会在 `d / "raw" / "amplify" /
f"b{batch}.out"` 这个路径上找不到文件，对每一个批都判"raw 不存在"、
整批失败——"放大扫描"产的东西会一行都进不了保税仓。故输出契约的"本会话
需要产出的文件"列表按 SEG 全部批号逐一列出 `raw/amplify/b<N>.out`，与
`polish_context.OUTPUT_CONTRACT_HEADER`（原样复用，保证字段契约不漂移）
配合，要求模型对**每个批**、**批内每个非锁定 id**都产出恰好一行——即
"重扫整个 SEG"字面意义上的重扫（含桶 0/1/2 已经不需要改动的行，也要求
原样抄一遍 zh，与常规批次同一份契约），不是只扫桶 3。

### `plan.json`/`prompt_hash` 的 channel 精确性（评审 Finding B，已修复）

`polish_ingest.ingest()` 用 `plan.json` 反查某批所属会话的 `prompt_hash`
（`_find_prompt_hash`）。初版实现里该函数按批号在记录列表里找**第一个**
匹配、不区分 channel——`polish_context.render()`+CLI 早于本模块运行、
已经为该 SEG 全部批次写过普通会话记录（真实流水线里不同普通 channel
执行的是同一份 prompt 文字，`render()` 本身不按 channel 参数化，这些
记录天然"channel 无关"，从不带 `channel` 字段）。评审实测发现：初版
`scan_prompt()` 不写任何新记录，导致 `ingest(label, "amplify", batch)`
反查到的 `prompt_hash` 其实是**更早的普通通道**那次渲染的哈希——不是
"查不到"（那还有信号），而是"查到了一个真实存在但错误的文档"，破坏了
Task 8 立下的 `prov` 三跳倒查链的精确性承诺。

**修法**：`tools.polish_ingest._find_prompt_hash(plan_path, batch,
channel=None)` 加了可选 `channel` 参数——传了 `channel` 时先只在"批号
吻合且记录自带的 `channel` 字段等于查询值"的记录里找，找到就直接返回；
找不到（绝大多数普通 channel 从未写过带 `channel` 标签的专属记录）才
退化到旧的"批号匹配即返回第一条、不看 channel"兜底。`ingest()` 内部
调用点相应改为 `_find_prompt_hash(d / "plan.json", batch, channel=channel)`。

配合本模块这一侧：`scan_prompt()` 装配成功后，往 `plan.json` **追加**
一条 `{"session": <新会话号>, "batches": <本 SEG 全部批号>, "prompt_hash":
sha256(scan_prompt 文本), "channel": "amplify"}` 记录（新会话号取现有
记录里最大 `session` + 1，不与任何既有记录冲突，也不覆盖/移除任何既有
记录）。这条记录**专属** `channel="amplify"` 的查询：
- `ingest(label, "amplify", batch)` 查询时传 `channel="amplify"`，第一
  轮匹配直接命中这条新记录，返回的正是这次放大扫描 prompt 自身的哈希——
  不再借用任何普通通道的文档。
- 普通 channel（`chA`/`fable`/`deepseek`/…）的查询完全不受影响：它们
  从未写过、也不会写带 `channel` 字段的记录，第一轮匹配（要求 channel
  吻合）永远找不到东西，直接落到旧的 channel-无关兜底，行为与本次改动
  之前逐位一致——`test_find_prompt_hash_backward_compatible_without_
  channel_field`（`tests/test_polish_ingest.py`）与
  `test_amplify_ingest_prompt_hash_matches_scan_prompt_not_normal_
  channel`（`tests/test_polish_amplify.py`）分别从"函数级直接调用"与
  "端到端 ingest 出来的 candidates 行"两个层面钉死这一点。

⚠ **本次改动的授权范围**：评审明确"这次授权你改 `polish_ingest.py`"，
仅限于 `_find_prompt_hash` 加 channel 参数、`ingest()` 内部调用点传
channel——`ingest()` 既有的判死/整批失败逻辑（R1 覆盖检查、重复 id、
错位侦测三条件、非法类型等）**一处未动**，`tests/test_polish_ingest.py`
全量重跑确认无回归（见下方"回归"一节）。
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_context import _render_anchors, _render_voices
from tools.pipelib import REPO, dumps, read_jsonl
from tools.polish_context import OUTPUT_CONTRACT_HEADER
from tools.polishlib import CFG, demote_anchors_heading

HUMAN_VERDICTS = ("adopt", "edit", "keep_opus")

AMPLIFY_MARKER_RE = re.compile(r"^<!-- amplify-round:(\d+) -->$", re.MULTILINE)


class AmplifyRoundLimitError(RuntimeError):
    """该 SEG 已用完 `CFG['amplify_rounds']` 规定的放大扫描轮次配额。"""


def _dir_for(label, repo) -> Path:
    """同 Task 3-8 一致的理由：`polishlib.seg_dir()` 硬编码仓库根，这里另起
    一份只在 repo 落空时退化，使本模块的一切函数与 CLI 都能被 tmp_path 造
    的替身仓库完全接管（测试要求：不得写进真实仓库的 `pilot/polish/`）。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _load_frozen(d: Path):
    """返回 `(source_rows, id2jp, id2opus, hard_ids, soft_ids, batches)`。

    2026-08-07 裁定（锚点行从硬锁改软锁）：`locked.json` 现在区分
    `hard_ids`（该 id 冻结时点已有人裁 patch，禁止出稿）与 `soft_ids`
    （anchors.yaml 锚点行，可以斟酌但改动须 adjudicate=true）——本模块
    只做展示用途（放大扫描 prompt 的锁定 id 清单、桶 0 全景），不做任何
    出稿判死（那是 `polish_ingest`/`polish_triage` 的职责），但展示文案
    不该继续把两者混在一起说"禁止改动"，那对软锁 id 不成立。旧格式
    `locked.json`（无 hard_ids/soft_ids 键）向后兼容：整体当硬锁，与
    `polish_ingest`/`polish_triage` 同一兼容口径。"""
    fz = d / "frozen"
    source_rows = read_jsonl(fz / "source.jsonl")
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    id2opus = {r["id"]: r["zh"] for r in read_jsonl(fz / "opus.jsonl")}
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    if "hard_ids" in locked or "soft_ids" in locked:
        hard_ids = set(locked.get("hard_ids", []))
        soft_ids = set(locked.get("soft_ids", []))
    else:
        hard_ids = set(locked.get("ids", []))
        soft_ids = set()
    # 批号按 source_rows 里的出现顺序去重——与 polish_context.plan() 同一
    # 惯例，保证批次在文档里的呈现顺序与玩家实际经历顺序一致。
    batches = []
    for r in source_rows:
        if r["batch"] not in batches:
            batches.append(r["batch"])
    return source_rows, id2jp, id2opus, hard_ids, soft_ids, batches


def _all_candidates(d: Path) -> dict:
    """`{channel: {id: 最后一条候选行}}`——跨全部已入仓通道。同 id 多条取
    最后一条（append-only 文件的通篇约定，见 polish_check.py 同名处理）。"""
    result = {}
    for p in sorted(d.glob("candidates.*.jsonl")):
        channel = p.name[len("candidates."):-len(".jsonl")]
        last = {}
        for r in read_jsonl(p):
            last[r["id"]] = r
        result[channel] = last
    return result


def _decision_final_zh(dec: dict, cand_zh, opus_zh):
    """按 verdict 取"最终生效"的 zh：adopt→候选原文，edit→人工改写稿，
    keep_opus→opus 原译（这条决策的字面意思就是"不采纳候选、维持原译"）。"""
    verdict = dec.get("verdict")
    if verdict == "edit":
        return dec.get("edited_zh")
    if verdict == "keep_opus":
        return opus_zh
    return cand_zh


def _final_zh_for_decision(dec: dict, all_cands: dict, id2opus: dict):
    """`_decision_final_zh()` 的查表版本——按这条决策自己的 `chosen_
    channel` 去 `all_cands` 里找该 id 对应的候选行，取其 `zh` 作为
    "候选原文"这一路输入，再代入同一套 adopt/edit/keep_opus 规则。

    `_build_digest_text()`（代表例）与 `_build_panorama()`（桶 2 全量）
    都调用这同一个 helper——两处都需要"这条决策的最终 zh 到底是什么"这
    件事，若各自实现一份查表逻辑，将来任何一处改了对齐规则都可能悄悄
    分裂成两套答案（评审 Finding A 的教训：两处只有一处渲染，被漏掉的
    那一处就成了"工具对模型撒了谎"）。
    """
    cid = dec.get("id")
    channel = dec.get("chosen_channel")
    cand_row = all_cands.get(channel, {}).get(cid) if channel else None
    cand_zh = cand_row.get("zh") if cand_row else None
    opus_zh = id2opus.get(cid, "")
    return _decision_final_zh(dec, cand_zh, opus_zh)


def _decision_ruling_text(dec: dict) -> str:
    """裁决语——decisions.jsonl 目前没有专门的自由文本字段（brief 给的六个
    字段里没有），故按 verdict/reason_code/chosen_channel 拼一句可读的
    裁决摘要；若某条记录额外带了 `note`（人工在 Task 11 runbook 里手工
    加的自由文本，向后兼容、不强制要求），优先原样使用那句话。"""
    note = dec.get("note")
    if note:
        return note
    verdict = dec.get("verdict")
    reason = dec.get("reason_code") or "未分类"
    channel = dec.get("chosen_channel") or "?"
    if verdict == "adopt":
        return f"采纳 {channel} 候选（原因：{reason}）"
    if verdict == "edit":
        return f"人工改写后采用（原因：{reason}）"
    if verdict == "keep_opus":
        return f"保留 opus 原译，不采纳候选（原因：{reason}）"
    return f"{verdict}（原因：{reason}）"


def _build_digest_text(label, repo=None) -> str:
    """纯函数：只读磁盘，不写任何文件。`digest()`/`scan_prompt()` 各自决定
    要不要落盘/落什么盘——避免把"计算纪要"与"追加进 rulings.md 这个副
    作用"耦合在一处（`scan_prompt()` 需要复用同一份纪要文本嵌入 prompt，
    但不该在装配失败/被闸拒绝时也把纪要重复 append 进 rulings.md）。
    """
    d = _dir_for(label, repo)
    _, id2jp, id2opus, _hard_ids, _soft_ids, _batches = _load_frozen(d)
    all_cands = _all_candidates(d)

    decisions_path = d / "decisions.jsonl"
    decisions = read_jsonl(decisions_path) if decisions_path.exists() else []
    human = [dec for dec in decisions if dec.get("verdict") in HUMAN_VERDICTS]

    by_code = {}
    for dec in human:
        code = dec.get("reason_code") or "未分类"
        by_code.setdefault(code, []).append(dec)

    total = len(human)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = [f"## 放大扫描意图纪要（{label}，{ts}，人工裁决 {total} 条，"
           f"{len(by_code)} 类原因码）\n"]

    out.append("### 原因码分布\n")
    out.append("| 原因码 | 计数 | 占比 |")
    out.append("|---|---:|---:|")
    for code in sorted(by_code, key=lambda c: (-len(by_code[c]), c)):
        n = len(by_code[code])
        pct = f"{n / total:.1%}" if total else "0.0%"
        out.append(f"| {code} | {n} | {pct} |")
    out.append("")

    out.append("### 代表例（每类原因码 ≤3 条）\n")
    for code in sorted(by_code, key=lambda c: (-len(by_code[c]), c)):
        out.append(f"#### {code}\n")
        examples = sorted(by_code[code], key=lambda dec: dec.get("id", 0))[:3]
        for dec in examples:
            cid = dec.get("id")
            channel = dec.get("chosen_channel")
            cand_row = all_cands.get(channel, {}).get(cid) if channel else None
            cand_zh = cand_row.get("zh") if cand_row else None
            opus_zh = id2opus.get(cid, "")
            final_zh = _final_zh_for_decision(dec, all_cands, id2opus)
            ruling = _decision_ruling_text(dec)
            out.append(f"- id {cid}（verdict={dec.get('verdict')}）")
            out.append(f"  - JP：{id2jp.get(cid, '')}")
            out.append(f"  - opus：{opus_zh}")
            out.append(f"  - 候选（{channel}）：{cand_zh if cand_zh is not None else '（无候选记录）'}")
            out.append(f"  - 最终 zh：{final_zh}")
            out.append(f"  - 裁决语：{ruling}")
        out.append("")

    return "\n".join(out)


def digest(label, repo=None) -> str:
    """计算意图纪要并**追加**写入 `frozen/rulings.md`（不覆盖），返回文本。
    可重复调用——每次都会在 rulings.md 里再追加一份当前状态下的纪要快照，
    不受任何轮数闸约束（见模块 docstring 设计点 2）。
    """
    text = _build_digest_text(label, repo=repo)
    d = _dir_for(label, repo)
    rulings_path = d / "frozen" / "rulings.md"
    with open(rulings_path, "a", encoding="utf-8") as f:
        f.write("\n" + text + "\n")
    return text


def _round_count(rulings_text: str) -> int:
    return len(AMPLIFY_MARKER_RE.findall(rulings_text))


def mark_round_if_complete(label, repo=None) -> bool:
    """`polish_ingest.ingest()` 的钩子：`channel == "amplify"` 且这次调用
    `ok=True` 时应当调用本函数。只有在 `ingested.amplify.json` 记录的批号
    **完全覆盖**这个 SEG 的全部批号（`_load_frozen()` 算出的 `batches`，
    与 `scan_prompt()` 装配输出契约时要求模型逐批产出 `raw/amplify/bN.out`
    的那同一份批号集合）时，才判定"这一轮放大扫描真正跑完了"，此刻才在
    `frozen/rulings.md` 追加 `<!-- amplify-round:N -->` 消耗一次轮次配额；
    覆盖不全（`polish_ingest --channel amplify --all` 通常是按批一批批
    调用，中途每一次都会经过这里）则什么也不做，返回 `False`。

    返回 `True` 仅当本次调用**真正新写入**了一条标记；否则返回 `False`
    （尚未覆盖齐全，或该 SEG 轮次配额已经用完——见下方 `round_count >=
    limit` 分支，这也保证了幂等：一轮只会被标记一次，即使
    `ingest(..., "amplify", ...)` 在同一批号上被调用第二次、或在覆盖
    齐全之后又被别的批号触发一次多余检查，都不会重复追加标记）。

    找不到 `frozen/rulings.md`（SEG 还没冻结）或 `ingested.amplify.json`
    （还没有任何 amplify 批入仓过）都视为"未完成"，安静返回 `False`——
    不抛异常：这个钩子在调用方（`polish_ingest.ingest()`）看来只是"顺手
    问一句这一轮完事了没"，不该因为它自己的前置条件不满足而打断真正的
    ingest 流程本身。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"
    rulings_path = fz / "rulings.md"
    if not rulings_path.exists():
        return False
    rulings_text = rulings_path.read_text(encoding="utf-8")

    round_count = _round_count(rulings_text)
    limit = CFG["amplify_rounds"]
    if round_count >= limit:
        return False

    ingested_path = d / "ingested.amplify.json"
    if not ingested_path.exists():
        return False
    ingested = json.loads(ingested_path.read_text(encoding="utf-8"))
    ingested_batches = set(ingested.get("batches", []))

    try:
        _, _, _, _, _, batches = _load_frozen(d)
    except FileNotFoundError:
        return False
    if not batches or not set(batches).issubset(ingested_batches):
        return False

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    marker = (f"\n## 放大扫描 · 第 {round_count + 1} 轮已真正入仓完成"
              f"（{ts}，覆盖全部 {len(batches)} 批）\n"
              f"<!-- amplify-round:{round_count + 1} -->\n")
    with open(rulings_path, "a", encoding="utf-8") as f:
        f.write(marker)
    return True


def _bucket3_reason(row: dict) -> str:
    if row.get("autoclear") and not row.get("sampled"):
        return ("已判定安全、自动清关（未抽中复核样本）——生产车道当前译文"
                "已是该候选内容，不是 opus 原文；本轮放大扫描仍把它摆出来，"
                "供你确认这次自动判定是否可信")
    return ("有真实改动，但本轮未挤进人工裁决队列（K 配额已满）——生产车道"
            "当前译文**仍是 opus 原文**，这条候选从未被任何人看过")


def _build_panorama(d: Path, id2jp, id2opus, hard_ids, soft_ids, all_cands) -> str:
    triage_path = d / "triage.json"
    if not triage_path.exists():
        raise FileNotFoundError(
            f"{triage_path} 不存在——该 SEG 尚未 polish_triage.triage() 分流，"
            "放大扫描无法装配（没有四桶结果可供全景展示）")
    triage = json.loads(triage_path.read_text(encoding="utf-8"))
    rows = triage.get("rows", [])

    decisions_path = d / "decisions.jsonl"
    decisions = read_jsonl(decisions_path) if decisions_path.exists() else []
    decisions_by_id = {}
    for dec in decisions:
        decisions_by_id.setdefault(dec.get("id"), []).append(dec)

    out = ["## 全 SEG 四桶结果全景（`polish_triage.triage()` 的分流快照）\n"]

    out.append(f"### 桶 0（硬锁 id，禁止改动，共 {len(hard_ids)} 个）\n")
    out.append("、".join(str(i) for i in sorted(hard_ids)) or "（本 SEG 无硬锁 id）")
    out.append(f"\n### 软锁 id（锚点行，可以斟酌但改动须 adjudicate=true，"
               f"共 {len(soft_ids)} 个——不属于桶 0/1/2/3 任何一桶，单独列出仅供参照）\n")
    out.append("、".join(str(i) for i in sorted(soft_ids)) or "（本 SEG 无软锁 id）")

    b1 = sorted((r for r in rows if r["bucket"] == 1), key=lambda r: (r["id"], r["channel"]))
    out.append(f"\n### 桶 1（零改动——已确认这些行的候选与 opus 逐字相同，共 {len(b1)} 条）\n")
    if b1:
        for r in b1:
            out.append(f"- id {r['id']}（{r['channel']}）：{id2opus.get(r['id'], '')}")
    else:
        out.append("（本 SEG 本轮无零改动候选）")

    b2 = sorted((r for r in rows if r["bucket"] == 2), key=lambda r: (r["id"], r["channel"]))
    out.append(f"\n### 桶 2（已进入本轮人工裁决队列，共 {len(b2)} 条候选行）\n")
    if b2:
        for r in b2:
            cid, channel = r["id"], r["channel"]
            cand_row = all_cands.get(channel, {}).get(cid)
            cand_zh = cand_row.get("zh") if cand_row else None
            out.append(f"- id {cid}（{channel}）")
            out.append(f"  - JP：{id2jp.get(cid, '')}")
            out.append(f"  - opus：{id2opus.get(cid, '')}")
            out.append(f"  - 候选：{cand_zh if cand_zh is not None else '（无候选记录）'}")
            decs = decisions_by_id.get(cid)
            if decs:
                last = decs[-1]
                final_zh = _final_zh_for_decision(last, all_cands, id2opus)
                out.append(f"  - 裁决结果：verdict={last.get('verdict')}，"
                            f"原因={last.get('reason_code')}")
                out.append(f"  - 裁决后最终 zh（请照抄这一行，不要回退去抄候选或 opus）："
                            f"{final_zh if final_zh is not None else '（决策缺少最终译文，需人工确认）'}")
            else:
                out.append("  - 裁决结果：（尚未裁决）")
    else:
        out.append("（本 SEG 本轮裁决队列为空）")

    b3 = sorted((r for r in rows if r["bucket"] == 3), key=lambda r: (r["id"], r["channel"]))
    out.append(f"\n### 桶 3（有改动但本轮落选，共 {len(b3)} 条——"
               "**本次放大扫描的重点复核对象，候选全文完整列出**）\n")
    if b3:
        for r in b3:
            cid, channel = r["id"], r["channel"]
            cand_row = all_cands.get(channel, {}).get(cid)
            cand_zh = cand_row.get("zh") if cand_row else None
            out.append(f"- id {cid}（{channel}）")
            out.append(f"  - JP：{id2jp.get(cid, '')}")
            out.append(f"  - opus（现行生产车道译文，除非下方另有说明）：{id2opus.get(cid, '')}")
            out.append(f"  - 落选候选全文：{cand_zh if cand_zh is not None else '（无候选记录）'}")
            out.append(f"  - 落选原因：{_bucket3_reason(r)}")
    else:
        out.append("（本 SEG 本轮无落选候选）")

    return "\n".join(out)


AMPLIFY_PREAMBLE = """\
## 本轮说明——这是一次「放大扫描」

前一轮，本项目对本 SEG 抽出的 K 条候选做了人工裁决（见下方"裁决意图
纪要"）。那批裁决体现的判断尺度（哪类改动该动、哪类不该动、术语/语气怎么
把握）理应适用于**整个 SEG**，不只是被抽到的那 K 条。你的任务：带着这份
纪要给出的判断尺度，重新审视本 SEG **全部**行的润色结果——尤其是下方
"全 SEG 四桶结果全景"里**桶 3（落选候选）**：这些行曾经产生过真实
改动，却因为人工裁决配额有限而从未被人看过，目前默认原样保留 opus（或
已被机械判定为"安全"而自动清关，但同样没有人确认过）。

**这不是只扫桶 3。** 输出契约要求你对本 SEG 每一批、批内每一个非硬锁 id
（含软锁 id——像普通行一样给出一行，改动仍须 adjudicate=true）都产出
一行——桶 0/1/2 里那些已经确认没问题的行，也请原样抄一遍现行 zh
（与常规批次同一份契约，"不改的行 zh 逐字抄现行译文"同样适用；桶 2 已经
过一次人工裁决的行，`zh` 请照抄裁决结果里的最终译文，不要回退去抄更早
的候选或 opus）。真正需要你运用纪要里学到的判断尺度去重新斟酌的，是桶 3
落选候选与桶 1 里那些可能被之前通道武断判成"零改动"的行。
"""


def _upsert_amplify_plan_record(plan_path: Path, batches: list, prompt_hash: str) -> None:
    """往 `plan.json` **追加**一条 `channel="amplify"` 的专属记录（评审
    Finding B 的修复）：新会话号取现有记录里最大 `session` + 1，不覆盖、
    不移除任何既有记录（普通 channel 的会话记录完全不受影响，它们从来
    不带 `channel` 字段，`polish_ingest._find_prompt_hash` 对它们的查找
    行为逐位不变）。"""
    records = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else []
    next_session = max((r.get("session", 0) for r in records), default=0) + 1
    records.append({"session": next_session, "batches": list(batches),
                     "prompt_hash": prompt_hash, "channel": "amplify"})
    plan_path.write_text(dumps(records), encoding="utf-8")


def scan_prompt(label, repo=None) -> str:
    """装配整 SEG 放大扫描 prompt：纪要 + 四桶全景（含桶 3 落选句全文）+
    锁定 id 清单 + 术语/风格/口调/锚点 + 输出契约（channel 固定 amplify）。

    轮数闸：`frozen/rulings.md` 里已有的 `<!-- amplify-round:N -->` 标记数
    达到 `CFG["amplify_rounds"]` 就拒绝——抛 `AmplifyRoundLimitError`，不做
    任何写入。**2026-08-07 修正**：本函数自己**不再**写这个标记（见模块
    docstring 设计点 2）——标记只在 `polish_ingest.ingest()` 以
    `channel="amplify"` 把这一轮全部批号真正入仓完毕时，由
    `mark_round_if_complete()` 写入。这意味着 `scan_prompt()` 现在可以
    被反复调用而不消耗轮次配额（例如纪要更新后想重新渲染一份 prompt），
    直到某一轮真正被完整执行、入仓为止；轮数闸依旧生效，只是判据从"装配
    过几次"改成了"真正跑完过几次"。

    成功装配后还会往 `plan.json` 追加一条 `channel="amplify"` 的专属会话
    记录（`prompt_hash` = 本次返回文本自身的 sha256），供
    `polish_ingest.ingest(label, "amplify", batch)` 精确反查——见模块
    docstring"`plan.json`/`prompt_hash` 的 channel 精确性"专节。**这一条
    每次调用都会追加**（不受轮数闸约束之外的限制），重复调用
    `scan_prompt()` 会在 `plan.json` 里留下多条 `channel="amplify"` 记录
    ——`_find_prompt_hash()` 按批号+channel 找到的是**第一条**匹配，故
    只有第一次 `scan_prompt()` 产出的文本哈希会被 `ingest()` 采信；若
    中途重渲染过 prompt，请确保派发给模型/子代理的是同一份最初渲染的
    文本，或在真正派发前只调用一次 `scan_prompt()`——这是既有行为，本次
    修复未改变，此处仅记录在案供操作者注意。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"
    rulings_path = fz / "rulings.md"
    rulings_text_before = rulings_path.read_text(encoding="utf-8") if rulings_path.exists() else ""

    round_count = _round_count(rulings_text_before)
    limit = CFG["amplify_rounds"]
    if round_count >= limit:
        raise AmplifyRoundLimitError(
            f"{label} 已用完放大扫描轮次配额（已装配 {round_count} 轮，"
            f"上限 CFG['amplify_rounds']={limit}）——拒绝再装配")

    _, id2jp, id2opus, hard_ids, soft_ids, batches = _load_frozen(d)
    all_cands = _all_candidates(d)

    digest_text = _build_digest_text(label, repo=repo)
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    why = locked.get("why", {})

    active = json.loads((fz / "glossary" / "active.json").read_text(encoding="utf-8"))
    style = (fz / "glossary" / "style.md").read_text(encoding="utf-8")
    polish_md = (fz / "glossary" / "polish.md").read_text(encoding="utf-8")
    voices = _render_voices(fz / "glossary" / "voices")
    # `_render_anchors()` 硬编码"## 三、锚点行"（build_context.py 自己的编号
    # 体系里正确的第三节）——本函数自己不编号顶层标题，用共享 helper 把它
    # 降级成不带编号的三级标题，与 polish_context.render() 同一处理、同一
    # 理由（评审 Finding A/C：两份 prompt 是同一批人读的，风格不该分叉），
    # 见 tools/polishlib.demote_anchors_heading 的 docstring。
    anchors = demote_anchors_heading(_render_anchors(fz / "glossary" / "anchors.yaml"))

    out = [f"# {label} 放大扫描（第 {round_count + 1} 轮，共 {len(batches)} 批）",
           AMPLIFY_PREAMBLE]

    out.append("## 裁决意图纪要\n")
    out.append(digest_text)

    out.append(_build_panorama(d, id2jp, id2opus, hard_ids, soft_ids, all_cands))

    out.append("\n## 硬锁 id 清单（禁止在输出中出现这些 id）\n")
    if hard_ids:
        for i in sorted(hard_ids):
            out.append(f"- 【硬锁】{i}（{why.get(str(i), '?')}）："
                       f"JP: {id2jp.get(i, '')} / ZH(opus): {id2opus.get(i, '')}")
    else:
        out.append("（本 SEG 无硬锁 id）")

    out.append("\n## 软锁 id 清单（锚点行，可以斟酌——不改就照抄现行 zh，"
                "改了必须 adjudicate=true 并在 note 里写清楚理由）\n")
    if soft_ids:
        for i in sorted(soft_ids):
            out.append(f"- 【软锁】{i}：JP: {id2jp.get(i, '')} / ZH(opus): {id2opus.get(i, '')}")
    else:
        out.append("（本 SEG 无软锁 id）")

    out.append("\n## 术语 / 风格 / 口调 / 锚点（frozen 冻结面，强制遵守）")
    out.append("### active.json（术语表）")
    out.append(json.dumps(active, ensure_ascii=False))
    out.append("\n### style.md（对/错标准）")
    out.append(style)
    out.append("\n### polish.md（汉语母语感六条细则）")
    out.append(polish_md)
    if voices:
        out.append(voices)
    out.append(anchors)

    out.append("\n## 输出契约")
    out.append(OUTPUT_CONTRACT_HEADER)
    for b in batches:
        out.append(f"- `raw/amplify/b{b}.out`")

    text = "\n".join(out)

    prompt_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    _upsert_amplify_plan_record(d / "plan.json", batches, prompt_hash)

    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 裁决意图归纳 + 放大扫描装配")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--digest", action="store_true", help="产出意图纪要（追加进 rulings.md）")
    ap.add_argument("--scan-prompt", action="store_true", help="装配放大扫描 prompt")
    ap.add_argument("--out", help="配合 --scan-prompt：写出 prompt 文件路径（省略则打印到 stdout）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    if args.digest:
        text = digest(args.seg, repo=args.repo)
        print(text)
        return 0

    if args.scan_prompt:
        try:
            text = scan_prompt(args.seg, repo=args.repo)
        except AmplifyRoundLimitError as e:
            print(f"!! {e}", file=sys.stderr)
            return 1
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            print(f"放大扫描 prompt 已写入 {out_path}")
        else:
            print(text)
        return 0

    ap.error("需要 --digest 或 --scan-prompt 之一")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
