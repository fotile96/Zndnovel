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
3. 轮数闸：`scan_prompt()` 每次成功装配都会在 `frozen/rulings.md` 里留一个
   不会被自然文本撞到的标记；下次调用先数标记数，达到
   `CFG["amplify_rounds"]`（默认 1）就拒绝再装配——**每段最多放大一轮**。

放大产物的回炉路径不在本模块之内：模型按输出契约产出 `raw/amplify/b<N>
.out`，`polish_ingest --channel amplify` 原样入仓、`polish_triage`（Task 7
已保证 `channel=="amplify"` 恒不 autoclear）分流、人工追加小裁决、
`polish_commit` 清关——本模块只负责"喂出正确格式的下一轮 prompt"这一步。

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

## 设计点 2：轮数闸的标记形态与检测

标记是一行只会由本模块写入、且不会被"看起来像它"的普通中文正文撞到的
字符串：`<!-- amplify-round:N -->`（HTML 注释语法，`rulings.md` 是纯
markdown，人工/模型都不会往里面写字面意义上的 HTML 注释；`N` 是这是第几
轮）。检测用一个锚定单行的正则统计 `frozen/rulings.md` 全文里出现过多少
条这种标记，与 `CFG["amplify_rounds"]` 比较——**次数达到上限就拒绝**
（`>=`，不是 `>`：`amplify_rounds=1` 时，已经出现过 1 条标记就该拒绝第
2 次装配，不是要等出现第 2 条才拦）。

标记只在 `scan_prompt()` **成功装配之后**追加（gate 检查通过 → 组装内容
→ append 标记 → 返回文本）：如果提前在检查之前就写标记，一次因为其他
原因（比如 frozen 缺文件）中途抛异常的调用也会消耗掉本该属于"真正装配
成功一次"的轮次配额，是不诚实的记账。

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

### 关于 `plan.json`/`prompt_hash` 的一个已知、不新增的粗糙点

`polish_ingest.ingest()` 用 `plan.json` 反查某批所属会话的 `prompt_hash`
（`_find_prompt_hash`，按批号在记录列表里找**第一个**匹配，不区分
channel）。`polish_context.render()`+CLI 早于本模块运行、已经为该 SEG
全部批次写过至少一条 session 记录（真实流水线里不同 channel 执行的是
同一份 prompt 文字，只是换了个模型/车道去读——`render()` 本身不按
channel 参数化，session 记录天然是"channel 无关"的）。**本模块因此不
再往 `plan.json` 写任何新记录**：既有记录已经能让 `_find_prompt_hash`
对 SEG 的每个批号都返回一个非空哈希，`ingest(label, "amplify", batch)`
可以正常跑通（覆盖检查、jp_tail 核验等与 channel 无关的逻辑一切照旧）。

代价：`candidates.amplify.jsonl` 里记的 `prompt_hash` 指向的是**某次
普通会话**渲染出的哈希，不是"这次放大扫描 prompt 本身"的哈希——这是
一个真实存在、但不影响 ingest 是否成功、只影响审计精确度的粗糙点
（`_find_prompt_hash` 本身不支持按 channel 区分记录，修它超出本任务
范围，也违反"直接复用、不改动 polish_ingest.py"的既定分工）。已在报告
里作为 concern 记录。若该 SEG 从未跑过任何 `polish_context.render()`+
`--out` 流程（plan.json 完全为空），`ingest("amplify", batch)` 会按既有
逻辑正确地判"整批失败：查不到 prompt_hash"——这与其余 channel 遇到同一
情形的行为完全一致，不是本模块引入的新缺口。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_context import _render_anchors, _render_voices
from tools.pipelib import REPO, read_jsonl
from tools.polish_context import OUTPUT_CONTRACT_HEADER
from tools.polishlib import CFG

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
    fz = d / "frozen"
    source_rows = read_jsonl(fz / "source.jsonl")
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    id2opus = {r["id"]: r["zh"] for r in read_jsonl(fz / "opus.jsonl")}
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    locked_ids = set(locked.get("ids", []))
    # 批号按 source_rows 里的出现顺序去重——与 polish_context.plan() 同一
    # 惯例，保证批次在文档里的呈现顺序与玩家实际经历顺序一致。
    batches = []
    for r in source_rows:
        if r["batch"] not in batches:
            batches.append(r["batch"])
    return source_rows, id2jp, id2opus, locked_ids, batches


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
    _, id2jp, id2opus, _locked_ids, _batches = _load_frozen(d)
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
            final_zh = _decision_final_zh(dec, cand_zh, opus_zh)
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


def _bucket3_reason(row: dict) -> str:
    if row.get("autoclear") and not row.get("sampled"):
        return ("已判定安全、自动清关（未抽中复核样本）——生产车道当前译文"
                "已是该候选内容，不是 opus 原文；本轮放大扫描仍把它摆出来，"
                "供你确认这次自动判定是否可信")
    return ("有真实改动，但本轮未挤进人工裁决队列（K 配额已满）——生产车道"
            "当前译文**仍是 opus 原文**，这条候选从未被任何人看过")


def _build_panorama(d: Path, id2jp, id2opus, locked_ids, all_cands) -> str:
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

    out = ["## 二、全 SEG 四桶结果全景（`polish_triage.triage()` 的分流快照）\n"]

    out.append(f"### 桶 0（锁定 id，禁止改动，共 {len(locked_ids)} 个）\n")
    out.append("、".join(str(i) for i in sorted(locked_ids)) or "（本 SEG 无锁定 id）")

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
                out.append(f"  - 裁决结果：verdict={last.get('verdict')}，"
                            f"原因={last.get('reason_code')}")
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
## 零、本轮说明——这是一次「放大扫描」

前一轮，本项目对本 SEG 抽出的 K 条候选做了人工裁决（见下方"一、裁决意图
纪要"）。那批裁决体现的判断尺度（哪类改动该动、哪类不该动、术语/语气怎么
把握）理应适用于**整个 SEG**，不只是被抽到的那 K 条。你的任务：带着这份
纪要给出的判断尺度，重新审视本 SEG **全部**行的润色结果——尤其是下方
"二、全 SEG 四桶结果全景"里**桶 3（落选候选）**：这些行曾经产生过真实
改动，却因为人工裁决配额有限而从未被人看过，目前默认原样保留 opus（或
已被机械判定为"安全"而自动清关，但同样没有人确认过）。

**这不是只扫桶 3。** 输出契约要求你对本 SEG 每一批、批内每一个非锁定 id
都产出一行——桶 0/1/2 里那些已经确认没问题的行，也请原样抄一遍现行 zh
（与常规批次同一份契约，"不改的行 zh 逐字抄现行译文"同样适用；桶 2 已经
过一次人工裁决的行，`zh` 请照抄裁决结果里的最终译文，不要回退去抄更早
的候选或 opus）。真正需要你运用纪要里学到的判断尺度去重新斟酌的，是桶 3
落选候选与桶 1 里那些可能被之前通道武断判成"零改动"的行。
"""


def scan_prompt(label, repo=None) -> str:
    """装配整 SEG 放大扫描 prompt：纪要 + 四桶全景（含桶 3 落选句全文）+
    锁定 id 清单 + 术语/风格/口调/锚点 + 输出契约（channel 固定 amplify）。

    轮数闸：`frozen/rulings.md` 里已有的 `<!-- amplify-round:N -->` 标记数
    达到 `CFG["amplify_rounds"]` 就拒绝——抛 `AmplifyRoundLimitError`，不做
    任何写入（见模块 docstring 设计点 2：标记只在装配成功后才追加）。
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

    _, id2jp, id2opus, locked_ids, batches = _load_frozen(d)
    all_cands = _all_candidates(d)

    digest_text = _build_digest_text(label, repo=repo)
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    why = locked.get("why", {})

    active = json.loads((fz / "glossary" / "active.json").read_text(encoding="utf-8"))
    style = (fz / "glossary" / "style.md").read_text(encoding="utf-8")
    polish_md = (fz / "glossary" / "polish.md").read_text(encoding="utf-8")
    voices = _render_voices(fz / "glossary" / "voices")
    anchors = _render_anchors(fz / "glossary" / "anchors.yaml")

    out = [f"# {label} 放大扫描（第 {round_count + 1} 轮，共 {len(batches)} 批）",
           AMPLIFY_PREAMBLE]

    out.append("## 一、裁决意图纪要\n")
    out.append(digest_text)

    out.append(_build_panorama(d, id2jp, id2opus, locked_ids, all_cands))

    out.append("\n## 三、锁定 id 清单（禁止在输出中出现这些 id）\n")
    if locked_ids:
        for i in sorted(locked_ids):
            out.append(f"- 【锁】{i}（{why.get(str(i), '?')}）："
                       f"JP: {id2jp.get(i, '')} / ZH(opus): {id2opus.get(i, '')}")
    else:
        out.append("（本 SEG 无锁定 id）")

    out.append("\n## 四、术语 / 风格 / 口调 / 锚点（frozen 冻结面，强制遵守）")
    out.append("### active.json（术语表）")
    out.append(json.dumps(active, ensure_ascii=False))
    out.append("\n### style.md（对/错标准）")
    out.append(style)
    out.append("\n### polish.md（汉语母语感六条细则）")
    out.append(polish_md)
    if voices:
        out.append(voices)
    out.append(anchors)

    out.append("\n## 五、输出契约")
    out.append(OUTPUT_CONTRACT_HEADER)
    for b in batches:
        out.append(f"- `raw/amplify/b{b}.out`")

    text = "\n".join(out)

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    marker = f"\n## 放大扫描 · 第 {round_count + 1} 轮已装配（{ts}）\n<!-- amplify-round:{round_count + 1} -->\n"
    with open(rulings_path, "a", encoding="utf-8") as f:
        f.write(marker)

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
