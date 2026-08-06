"""P4 润色 pass：通道准入小考——「没考过试就不许免检」。

## 这个工具解决什么问题

润色流水线（`polish_triage.py`）里有一条"自动清关"通道：小改动 + 机械闸
全绿的候选可以不经人工裁决直接入库（`channel_state.json` 的
`{channel: {"autoclear": true}}`）。这条免检权对哪个执行通道开放，不能
凭感觉——本模块把若干条**人工裁决定稿句**（金标，模型不知情）混进一批
校准批喂给该通道，看它会不会把这些"已经拍板"的句子改坏。改坏比例超线
（`CFG["calib_fail"]`），该通道本 SEG 的自动清关权就初始关闭（候选照样
能产，但一律走人裁排队）。

## 金标池：从哪来、取哪个版本

`pilot/lanes/opus/data/patches.jsonl` 里 `reason ∈ {review, recall}` 的
行——那些 id 是被人裁过的、值得信任的定稿。**但绝不能直接拿这条 patch 行
本身的 `zh`**：同一 id 可能被多轮裁决层层修订（甚至后续被非 review/recall
理由的 patch——如本流水线自己的 `reason=polish`——再次覆盖），只有
`tools.resolve.resolve_map(forward_rows, patch_rows)` 算出的**现行值**（=
按文件出现顺序 forward 之后再叠 patches，最后一条生效）才是真正的"人工
定稿在此刻的样子"。取错等于拿一个已被推翻的旧版本去考模型——模型把它
改回现行版本反而会被误判成"改坏了金标"。

## 三档分档：unchanged / minor / substantive

对每条金标，量 `edit_distance(strip_ctl(model_zh), strip_ctl(ref_zh))`
（`ref_zh` = 该金标的现行文本，即 batch 里给模型的起点，也是这里的"标准
答案"），按 `config/polish.yaml` 的两个阈值切三档（该文件里
`minor_edit` 一行的注释就是这个三档表的定义）：

  - `edit ≤ minor_edit`                        → **unchanged**（基本没动）
  - `minor_edit < edit ≤ autoclear_limit(ref)`  → **minor**（有改动，但仍在
    "正常候选也会被判定可自动清关"的幅度内——这个量级的改动即使发生在
    普通候选身上也不会被拦下，所以不计入"实质改写"）
  - `edit > autoclear_limit(ref)`               → **substantive**（改动幅度
    已经超出自动清关本该允许的范围——这才是真正要防的：模型把一句人工
    拍板的定稿，改成了一个普通流程都不会放过的大改写）

`pass = substantive / (unchanged+minor+substantive) < CFG["calib_fail"]`。

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
from tools.polishlib import CFG, autoclear_limit, edit_distance, strip_ctl
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
    for id_str, info in truth.items():
        if not info.get("is_gold"):
            continue
        cid = int(id_str)
        ref_row = batch_rows.get(cid)
        if ref_row is None:
            continue
        ref_zh = ref_row["opus_zh"]
        out_row = last_by_id.get(cid)
        # 模型漏输出这个 id（截断/跳过）视为最坏情形——不能因为拿不到
        # 输出就悄悄跳过不计分，那等于让"没交卷"免于被判"实质改写"。
        model_zh = out_row.get("zh") if out_row else None

        edit = _content_edit(model_zh, ref_zh)
        limit = autoclear_limit(ref_zh)
        if edit <= CFG["minor_edit"]:
            gold_unchanged += 1
        elif edit <= limit:
            gold_minor += 1
        else:
            gold_substantive += 1

    total = gold_unchanged + gold_minor + gold_substantive
    # total==0（校准批里没有金标，理论上不该发生）保守判 False——没有证据
    # 就不给通过，呼应 channel_state 缺省关闭同一哲学。
    passed = (gold_substantive / total) < CFG["calib_fail"] if total else False

    result = {
        "gold_unchanged": gold_unchanged,
        "gold_minor": gold_minor,
        "gold_substantive": gold_substantive,
        "pass": passed,
        "known_bias": KNOWN_BIAS,
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
