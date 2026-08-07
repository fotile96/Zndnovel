"""P4 润色 pass：通道准入小考——「没考过试就不许免检」。

## 这个工具解决什么问题

润色流水线（`polish_triage.py`）里有一条"自动清关"通道：小改动 + 机械闸
全绿的候选可以不经人工裁决直接入库（`channel_state.json` 的
`{channel: {"autoclear": true}}`）。这条免检权对哪个执行通道开放，不能
凭感觉——本模块把若干条**人工裁决定稿句**（金标，模型不知情）混进一批
校准批喂给该通道，看它会不会把这些"已经拍板"的句子改坏。判卷不合格，
该通道本 SEG 的自动清关权就初始关闭（候选照样能产，但一律走人裁排队）。

## 金标池：从哪来、取哪个版本

`pilot/lanes/opus/data/patches.jsonl` 里 `reason ∈ {review, recall}` 的
行——那些 id 是被人裁过的、值得信任的定稿。**但绝不能直接拿这条 patch 行
本身的 `zh`**：同一 id 可能被多轮裁决层层修订（甚至后续被非 review/recall
理由的 patch——如本流水线自己的 `reason=polish`——再次覆盖），只有
`tools.resolve.resolve_map(forward_rows, patch_rows)` 算出的**现行值**（=
按文件出现顺序 forward 之后再叠 patches，最后一条生效）才是真正的"人工
定稿在此刻的样子"。取错等于拿一个已被推翻的旧版本去考模型——模型把它
改回现行版本反而会被误判成"改坏了金标"。

## 三档分档：unchanged / minor / substantive（2026-08-07 缺陷修复）

**根因（首次真实跑准入小考暴露）**：旧版把 `edit ≤ minor_edit` 记成
"unchanged"（"未改动"），实际含义是"未改动**或轻微改动**"——SEG-1 首次
真实小考里两条通道都报了 `gold_unchanged=10`，操作者读到会以为"一句金标
都没碰"，但独立核算显示 fable-wf 实际改了 3/10、ds-flash 改了 2/10（编辑
距离都在 1–2 字这个"轻微"区间，被旧判据悄悄计进了"未改动"）。**字段名
说的是"未改动"，字面意思却是"改动幅度不超过 4 字"——这是报告在说谎**，
比报告难看更严重。

现在三档改成与字面意思完全一致（只用 `minor_edit` 一个阈值，不再牵涉
`autoclear_limit`——那本是给普通候选定的自动清关阈值，用来定义"金标有没
有被动过"这件事从一开始就文不对题）：

  - `edit == 0`                    → **unchanged**（逐字未动）
  - `0 < edit ≤ minor_edit`        → **minor**（动了，但幅度不大）
  - `edit > minor_edit`            → **substantive**（大改写）

## pass 判定：以"改动是否被显式请裁"为基准，不再只看改动幅度

**更根本的问题**：对金标句而言，编辑距离本身就是错的判据。实测证据
（`pilot/polish/seg1-s2/calib/raw.{fable-wf,ds-flash}.jsonl` 对 id=5684
的真实输出）——

```
人裁定稿:  得厅那支曲子才行。          ← きく 三换字的 v13 裁定
ds-flash:  得听那支曲子才行。          edit=1, adjudicate=false  ← 静默推翻裁决
fable-wf:  得问问那支曲子才行。        edit=2, adjudicate=true   ← 改了但请裁了
```

1 个字推翻一条裁定，和大段改写一样严重——**动了就是信号，幅度不重要**。
`adjudicate` 才是这里真正有信息量的信号："察觉到并显式请裁"与"静默改动"
是完全不同的可信度。故本模块引入两个新分类（与 unchanged/minor/
substantive 三档并存，三档只做展示用的幅度分布，不再是 pass 的直接依据）：

  - **`changed_adjudicated`**：`edit > 0` 且该行 `adjudicate=true`
    ——通道"改了但主动说了"，这是我们希望看到的行为，不该被视为失败。
  - **`changed_silent`**：`edit > 0` 且 `adjudicate` 不是 `true`——通道
    "悄悄推翻了一条人工裁定"，这是本次修复要防的最危险失败模式。模型
    漏输出这个 id（截断/跳过）同样计入这一档最坏情形（没有 `adjudicate`
    可言，且内容视为"整句被换掉"，`edit` 按空串起手算，几乎必然 > 0）。

`silent_override_rate = changed_silent / total`；
`pass = silent_override_rate < CFG["calib_silent_override_fail"]`
（新配置项，**不复用** `CFG["calib_fail"]`——那个键原本是"实质改写占比"
的阈值，语义已经不适用于新判据，静默改变一个既有配置项的含义比新增一个
键更危险；`calib_fail` 保留在 `config/polish.yaml` 里但不再被本模块读取，
仅作历史阈值可追溯）。默认 `calib_silent_override_fail=0.10`——10 句金标
下 1 句静默覆盖就会落到边界（`0.10` 不小于 `0.10`，判 fail），阈值故意
收得接近零容忍：这类失败模式一旦发生就该被拦下，不是"多几次才算数"的
统计噪音。

结果里另外提供**逐条明细**（`details` 字段：每条金标 id 的 edit/分档/
`adjudicate`/是否静默覆盖），操作者不需要像本次一样自己写脚本核算就能
看清楚每一条金标到底发生了什么。

## ⚠ 已知偏差（贯穿本模块的免责声明，别当质量分用）

金标是"曾经出过问题或值得记录"的**非随机子集**（复现句族、争议句、边界
案例），其上下文分布系统性偏离普通批次——**本考只做门槛（pass/fail），
不是通道质量的精细度量**，更不能拿 pass 率当排行榜比较不同通道谁更好。
本模块每次 `make()`/`score()` 调用都会把这句话打进 stderr，`score()` 的
返回值里也带一份 `known_bias` 字段，供下游/人工核对时不至于遗忘这个前提。

## 校准批与生产批分离——且**不经 polish_ingest 入仓**

`make()` 产出的 `calib/<label>.batch.jsonl` 全部使用合成批号
`f"calib-{label}"`（不是任何真实批号），这不是随手选的字符串，而是刻意
的隔离设计：

1. **金标行是人工定稿**——如果校准批的模型输出被当作正常候选走
   `polish_ingest.py` → `polish_triage.py` → `polish_commit.py` 入仓，等于
   让本轮"能不能信任这个通道"的考试材料本身又被喂回生产库，一旦被
   自动清关，就是用模型的改写**覆盖掉已经拍板的人工决定**——恰好是本
   工具存在的目的要防止的事。
2. **普通陪考句虽然取自该 SEG 的真实 `frozen/source.jsonl`，但合成批号
   让它们结构上不可能满足 `polish_ingest.ingest()` 的"批内非锁定 id
   覆盖完整"检查**（那个检查按 `frozen/source.jsonl` 里登记的真实批号
   索引）——即便有人手滑把校准批的 raw 输出丢进 `raw/<channel>/` 目录，
   也无法被现有入仓逻辑认领成任何一个真实批次，天然作废。

结论：**校准批的 raw 输出只允许喂给 `score()`，绝不入仓**。它是诊断
材料，不是翻译产出。

## `channel_state.json`：与 `polish_triage.py` 的契约

`score()` 只更新自己这个 `channel` 的键，不覆盖其它通道已经写过的条目，
且**结构必须是 `{channel: {"autoclear": bool}}`**——这是 Task 7
`polish_triage._channel_autoclear_power()` 唯一认识的形状（
`channel_state.get(channel, {}).get("autoclear", False)`）。写成
`{channel: bool}` 或加一层嵌套，`polish_triage` 会静默把它读成"关闭"
（它对缺失/不识别的形状的保守缺省就是关闭）——后果不是报错，是**准入
结论悄悄失效**，故本模块的测试直接调用 `polish_triage._channel_autoclear_
power()` 来校验落盘格式，而不是自己重新发明一套解析逻辑自我验证。

## 与 `polish_audit.py`（抽检推翻率闸）的关系：小考不得解冻

`score()` 每次判卷都会重写该通道在 `channel_state.json` 里的条目。推翻率闸
（最终评审 I7 新增）冻结一个通道的方式恰恰也是改这个文件，若 `score()` 照旧
**整条覆盖**，那么"重跑一次准入小考"就能把刚落的冻结悄悄解掉——一道能被无意
中撤销的闸等于没有闸。故：

- 落盘改成"保留原条目其它键，只更新 `autoclear`"；
- 原条目带 `autoclear_frozen_by` 时，即使本次小考 pass 也**强制判 False**
  并显著播报（解冻必须是人看过存量回滚之后的显式动作，不是一条命令的副作用）。
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, dumps, read_jsonl, write_jsonl
from tools.polishlib import CFG, edit_distance, strip_ctl
from tools.resolve import resolve_map

KNOWN_BIAS = (
    "已知偏差：金标是「曾出问题或值得记录」的非随机子集（复现句族/争议句/"
    "边界案例），其上下文分布系统性偏离普通批次——本考只做门槛（pass/fail），"
    "不是通道质量的精细度量，请勿把 pass 率当排行榜使用。"
)


def _dir_for(label, repo) -> Path:
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _opus_lane_dir(repo) -> Path:
    """opus 车道 data 目录——固定路径约定（同 `tools.agent_tools.DEFAULT_LANE`
    == "pilot/lanes/opus"），本模块不像 `polish_setup.setup()` 那样开
    `opus_data` 参数：金标池天然就是"整个 opus 车道的裁决历史"，不随
    SEG 变化，没有需要外部指定别处的场景。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "lanes" / "opus" / "data"


def _gold_pool(repo) -> dict:
    """`patches.jsonl` 里 reason∈{review, recall} 的 id 集合，取其**现行**
    （`resolve_map` 之后）文本——同一 id 可能被多轮裁决层层修订，甚至被
    非 review/recall 理由的 patch（如本流水线自己写回的 reason=polish）
    再次覆盖；只要历史上出现过一次 review/recall，这个 id 就算金标，但
    喂给模型的"标准答案"必须是 resolve 之后的最新值，不是那条 review/
    recall 行自己的 zh。返回 `{id: {"jp": ..., "zh": ...}}`。"""
    lane = _opus_lane_dir(repo)
    ledger_p = lane / "ledger.jsonl"
    fwd_p = lane / "forward.jsonl"
    pat_p = lane / "patches.jsonl"

    ledger = {r["id"]: r for r in read_jsonl(ledger_p)} if ledger_p.exists() else {}
    fwd = read_jsonl(fwd_p) if fwd_p.exists() else []
    pat = read_jsonl(pat_p) if pat_p.exists() else []
    cur = resolve_map(fwd, pat)

    gold_ids = sorted({r["id"] for r in pat if r.get("reason") in ("review", "recall")})
    pool = {}
    for i in gold_ids:
        if i not in cur or i not in ledger:
            continue
        pool[i] = {"jp": ledger[i]["jp"], "zh": cur[i]}
    return pool


def make(label, n_gold=10, n_norm=10, repo=None) -> Path:
    """确定性抽样，产出一份混排的校准批（不带锁标，格式同生产批正文行：
    `{"id", "batch", "jp", "opus_zh"}`）+ 一份 `truth.json`（`id → {is_gold}`，
    **绝不进任何 prompt**，只是本模块自留的判卷答案）。

    种子取法与 Task 7（`polish_triage.py`）一致：
    `int(manifest["files"]["frozen/source.jsonl"][:8], 16)`——同一 SEG 的
    校准抽样与分流抽检共用同一颗种子来源（该 SEG 冻结面的 source.jsonl
    哈希），复现同一 SEG 时结果不漂移。

    普通陪考句取自该 SEG `frozen/source.jsonl` 里**非锁定**且**不在金标池
    里**的 id（后者是为了避免同一个 id 既是金标又是陪考句，造成
    `truth.json` 里同一 id 的判定互相打架）。锁定 id 本就不该出现在任何
    正文行里（生产批也不会），这里同样排除。
    """
    repo = Path(repo) if repo is not None else REPO
    d = _dir_for(label, repo)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    seed_hash = manifest["files"]["frozen/source.jsonl"]
    rng = random.Random(int(seed_hash[:8], 16))

    source_rows = read_jsonl(d / "frozen" / "source.jsonl")
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    opus = {r["id"]: r["zh"] for r in read_jsonl(d / "frozen" / "opus.jsonl")}
    locked = json.loads((d / "frozen" / "locked.json").read_text(encoding="utf-8"))
    locked_ids = set(locked.get("ids", []))

    gold_pool = _gold_pool(repo)
    gold_pool_ids = set(gold_pool)

    norm_candidates = sorted(
        i for i in id2jp if i not in locked_ids and i not in gold_pool_ids)
    gold_candidates = sorted(gold_pool_ids)

    if len(gold_candidates) < n_gold:
        raise ValueError(
            f"金标池只有 {len(gold_candidates)} 条（reason∈review/recall），"
            f"不足 n_gold={n_gold}")
    if len(norm_candidates) < n_norm:
        raise ValueError(
            f"{label} 冻结面里非锁定/非金标的 id 只有 {len(norm_candidates)} 条，"
            f"不足 n_norm={n_norm}")

    gold_ids = rng.sample(gold_candidates, n_gold)
    norm_ids = rng.sample(norm_candidates, n_norm)

    batch_tag = f"calib-{label}"
    rows = [
        {"id": i, "batch": batch_tag, "jp": gold_pool[i]["jp"], "opus_zh": gold_pool[i]["zh"]}
        for i in gold_ids
    ] + [
        {"id": i, "batch": batch_tag, "jp": id2jp[i], "opus_zh": opus[i]}
        for i in norm_ids
    ]
    rng.shuffle(rows)

    calib_dir = d / "calib"
    calib_dir.mkdir(parents=True, exist_ok=True)
    batch_path = calib_dir / f"{label}.batch.jsonl"
    write_jsonl(batch_path, rows)

    truth = {str(i): {"is_gold": True} for i in gold_ids}
    truth.update({str(i): {"is_gold": False} for i in norm_ids})
    (calib_dir / f"{label}.truth.json").write_text(dumps(truth), encoding="utf-8")

    print(KNOWN_BIAS, file=sys.stderr)
    return batch_path


def _content_edit(zh, ref) -> int:
    zs = strip_ctl(zh) if isinstance(zh, str) else ""
    rs = strip_ctl(ref) if isinstance(ref, str) else ""
    return edit_distance(zs, rs)


def score(label, raw_path, channel, repo=None) -> dict:
    """用一份模型输出（格式同生产 `raw/<channel>/b<N>.out`：逐行
    `{"id","jp_tail","zh","score","note","adjudicate"}`）给该通道判卷，只看
    校准批里标记为金标的 id：模型把这些人工定稿改成什么样了。

    结果写 `channel_state.json` 的 `{channel: {"autoclear": pass}}`——只更新
    本通道这一个键，不覆盖文件里其它通道已有的条目（与 `polish_triage.py`
    的读取契约见模块 docstring）。
    """
    repo = Path(repo) if repo is not None else REPO
    d = _dir_for(label, repo)
    calib_dir = d / "calib"
    truth = json.loads((calib_dir / f"{label}.truth.json").read_text(encoding="utf-8"))
    batch_rows = {r["id"]: r for r in read_jsonl(calib_dir / f"{label}.batch.jsonl")}

    raw_rows = read_jsonl(Path(raw_path))
    last_by_id = {}
    for r in raw_rows:
        last_by_id[r["id"]] = r  # 同 id 取最后一条（容错同生产 ingest 口径）

    gold_unchanged = gold_minor = gold_substantive = 0
    changed_adjudicated = changed_silent = 0
    details = []
    for id_str, info in sorted(truth.items(), key=lambda kv: int(kv[0])):
        if not info.get("is_gold"):
            continue
        cid = int(id_str)
        ref_row = batch_rows.get(cid)
        if ref_row is None:
            continue
        ref_zh = ref_row["opus_zh"]
        out_row = last_by_id.get(cid)
        # 模型漏输出这个 id（截断/跳过）视为最坏情形——不能因为拿不到
        # 输出就悄悄跳过不计分：既不给它"未改动"的清白，也不给它
        # "已请裁"的信任状（下面 adjudicate 取值同理默认 False）。
        model_zh = out_row.get("zh") if out_row else None
        adjudicate_flag = bool(out_row.get("adjudicate", False)) if out_row else False

        edit = _content_edit(model_zh, ref_zh)
        # 三档：只用 minor_edit 一个阈值，字段名与含义严格一致——见模块
        # docstring"2026-08-07 缺陷修复"一节。`gold_unchanged` 现在真的
        # 只计"逐字未动"，不再把"改了但幅度小"混进"未改动"里。
        if edit == 0:
            gold_unchanged += 1
            tier = "unchanged"
        elif edit <= CFG["minor_edit"]:
            gold_minor += 1
            tier = "minor"
        else:
            gold_substantive += 1
            tier = "substantive"

        # 真正决定 pass 的信号：改了但有没有显式请裁——"动了就是信号，
        # 幅度不重要"，1 个字的静默推翻和大段改写同样危险。
        silent_override = False
        if edit > 0:
            if adjudicate_flag:
                changed_adjudicated += 1
            else:
                changed_silent += 1
                silent_override = True

        details.append({
            "id": cid, "edit": edit, "tier": tier,
            "adjudicate": adjudicate_flag,
            "missing_output": out_row is None,
            "silent_override": silent_override,
            "ref_zh": ref_zh, "model_zh": model_zh,
        })

    total = gold_unchanged + gold_minor + gold_substantive
    # total==0（校准批里没有金标，理论上不该发生）保守判 False——没有证据
    # 就不给通过，呼应 channel_state 缺省关闭同一哲学。
    silent_override_rate = (changed_silent / total) if total else None
    passed = (silent_override_rate is not None
              and silent_override_rate < CFG["calib_silent_override_fail"])

    result = {
        "gold_unchanged": gold_unchanged,
        "gold_minor": gold_minor,
        "gold_substantive": gold_substantive,
        "changed_adjudicated": changed_adjudicated,
        "changed_silent": changed_silent,
        "silent_override_rate": silent_override_rate,
        "pass": passed,
        "known_bias": KNOWN_BIAS,
        "details": details,
    }

    state_path = d / "channel_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    prev = dict(state.get(channel) or {})
    # 推翻率闸（`tools/polish_audit.py`）冻结过的通道不得被一次重跑小考悄悄
    # 解冻——见本模块 docstring「与 polish_audit 的关系」。
    if prev.get("autoclear_frozen_by") and passed:
        print(f"⚠ {channel} 的自动清关权已被 {prev['autoclear_frozen_by']} 闸冻结"
              f"（{prev.get('frozen_ts')}，推翻率 {prev.get('overturn_rate')}），"
              "本次准入小考虽然通过，**不予重新开启**——先按 runbook §十二 处理完"
              "存量回滚复审，确认原因后再人工改 channel_state.json。", file=sys.stderr)
        passed = False
        result["pass"] = False
        result["blocked_by"] = prev["autoclear_frozen_by"]
    entry = dict(prev)
    entry["autoclear"] = passed
    state[channel] = entry
    state_path.write_text(dumps(state), encoding="utf-8")

    print(KNOWN_BIAS, file=sys.stderr)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 润色通道准入小考（金标校准）")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--make", action="store_true", help="生成校准批 + truth")
    ap.add_argument("--n-gold", type=int, default=10)
    ap.add_argument("--n-norm", type=int, default=10)
    ap.add_argument("--score", action="store_true", help="对模型输出判卷并写 channel_state.json")
    ap.add_argument("--channel", help="配合 --score：被考核的执行通道名")
    ap.add_argument("--raw", help="配合 --score：模型输出的 raw JSONL 路径")
    ap.add_argument("--repo", default=None, help="仓库根（省略用真实仓库根；测试传 tmp_path 替身仓库）")
    args = ap.parse_args(argv)

    if args.make:
        p = make(args.seg, n_gold=args.n_gold, n_norm=args.n_norm, repo=args.repo)
        print(p)
        return 0

    if args.score:
        if not args.channel or not args.raw:
            ap.error("--score 需要同时给 --channel 与 --raw")
        result = score(args.seg, args.raw, args.channel, repo=args.repo)
        print(dumps(result))
        return 0

    ap.error("需要 --make 或 --score 之一")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
