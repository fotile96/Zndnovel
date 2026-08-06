"""P4 润色 pass：唯一入仓口——模型输出（raw/<channel>/b<N>.out）是数据，
写保税仓（`candidates.<channel>.jsonl`）的是代码。

**回执二重核验，分工写在这里免得下游忘记**：
1. **模型侧回显尾串 ↔ frozen jp**（本模块负责）——模型算不出 sha256，只能
   回显 `id + jp_tail`（原文剥离控制码/ruby 后的末 N 字符，`polishlib.jp_tail`）；
   本模块从 `frozen/source.jsonl` 重算期望尾串，逐行核对。
2. **frozen ↔ manifest 哈希**（`polish_setup.verify()` 负责，不是本模块的
   事）——那一层核验的是「frozen/ 有没有相对于 SEG 冻结时点漂移」，与本模块
   核验「这一行模型输出对不对得上 frozen 里的某一行」是两个正交问题。

本模块只 **append** `candidates.<channel>.jsonl`（append-only，绝不重写整
文件），且只有在一整批的完整性通过之后才落盘——宁可整批判死，也不能让一行
来路不明的数据无声进仓。

## 判死 vs 整批失败

**判死**（该行不入仓，同批其余合法行照常入仓）：
- id 不在这一批里（批号对不上，或者干脆不是这个 SEG 的任何 id）；
- 锁定 id 出稿（额外计入 `discipline.<channel>.json`——纪律画像，衡量该
  通道有多少次试图对锁定行出稿）；
- 批内该 id 出现不止一行（重复 id——模型输出错位的典型征兆，见下）；
- `jp_tail` 与 frozen 重算的期望值不符；
- `zh` 为空串或缺 `zh` 字段——空译文没有任何下游用途，让它进仓只会把问题
  推给后面（评审 Critical 修复轮实测：这类行原先被静默透传）；
- **`zh` 逐字等于本批内另一个 id 的 opus 译文，且那两个 id 的 `jp` 不相同**
  ——错位嫌疑，额外计入 `discipline.<channel>.json` 的 `misaligned_hits`
  （评审 Critical 修复轮新增，见下方"错位侦测"专节）。

**整批失败**（不入仓任何行，且不写 `ingested.<channel>.json`——见下方幂等
小节的理由）：
- raw 不是合法 JSONL：**只要有一行解析失败（或解析出来不是 JSON 对象），
  就判整批失败，不是只杀那一行**。理由：批级"覆盖完整性"检查依赖于能读出
  每一行的 `id` 字段——一行解析失败，我们就无法确定这一行本来该覆盖哪个
  id，也就无法判断"该批非锁定 id 是否被覆盖完整"，覆盖检查本身失去依据。
  单行坏 ≠ 整个文件不是 JSONL（多数行仍可读），但覆盖完整性判定一旦失去
  依据，宁可整批重来，也不能在信息不全的情况下部分入仓。
- 批内非锁定 id 覆盖不完整（截断特征）：判定用"这个 id 有没有在 raw 里
  **出现过**"（哪怕出现的那一行随后因为 jp_tail 不符/锁定出稿被判死），
  不是"有没有存活成候选"——因为"出现但被判死"是模型输出了错误内容（有
  信号），而"完全没出现"是模型很可能中途截断了输出（另一种信号，且更
  危险：无法知道截断点之后还漏了多少）。这两种信号不该混为一谈，所以
  完整性检查故意只看"出现过"。
- `plan.json` 里查不到这一批所属的会话（因而拿不到 `prompt_hash`）：这本身
  就是异常（还没渲染过 prompt 就来了 raw），brief 明确要求不能静默填空串，
  所以升级为整批失败，而不是塞一个 `""` 混进 candidates 行。

## 三个自行裁定的设计点

1. **单行 JSON 解析失败 → 整批失败**（above，已展开理由）。

2. **重复 id → 判死两行（或多行），不是"择一录入"**：同一 id 在一批 raw 里
   出现 ≥2 次，是模型输出错位的典型征兆（比如断句/编号漂移，导致一个 id
   的内容被重复写了两遍，或者相邻两行的 id 被错误地写成同一个）。择一录入
   等于替模型猜"哪一份是对的"——这正是"静默写错比报错更坏"的具体案例，
   所以两条全部判死，不做选择。但这不算"覆盖不完整"：这个 id 确实在 raw
   里出现过（多次），只是没有一份存活成候选——按上面"出现过即算覆盖"的
   口径，不触发整批失败，只是这个 id 那一行本轮拿不到候选，需要重新出稿
   （下一次会话/重跑该批时，只要不再重复即可正常入仓）。

3. **幂等标记的粒度：`ingested.<channel>.json` 只记录\"成功\"的批号**。
   整批失败的批不记——如果记了，这批就再也无法重跑（`ingest()` 一开始就
   会把它当"已入仓"直接跳过，而实际上仓里什么都没有）。不记的代价是"整批
   失败"这个事件本身没有持久记录，但这本来就该在返回值/stderr 里被外部
   看到并处理（brief 要求"整批失败"要打印+记入返回值），不需要靠幂等标记
   兜底。同理，`discipline.<channel>.json`（锁定违规计数）也只在整批**成功**
   时落盘——一次整批失败的尝试里出现的锁定违规，等这批用干净的 raw 重跑
   一遍后，真正被采纳的那一次自然会被记上；不需要为一次可能整批作废的
   半成品尝试打永久的纪律烙印。

## 错位侦测（评审 Critical 修复轮追加）

**背景**：上线后评审自己构造对抗输入实测出一个漏洞——回执原先只绑定
`id ↔ jp_tail`，从不绑定 `zh ↔ jp`。三行互相"自洽错位"（`id=11` 挂着
`opus[10]` 的译文、`id=12` 挂着 `opus[11]`……）时，`id`/`jp_tail` 都是从
同一行机械复制来的，逐项核验全过，`jp_hash`/`opus_hash` 还是按 `row["id"]`
正确算出——反而把错位彻底掩盖了。这个失败模式恰好绕开了原设计的唯一防线：
输出契约要求"不改的行 `zh` 逐字抄 opus"，让模型在长列表里逐行照抄 opus
一列，抄串行是长上下文最典型的失误，而 id/jp_tail 是同一行机械复制、往往
仍然正确。

**判据（两条限定缺一不可，故意收窄，不做宽判据）**：
若某行的 `zh` **逐字**（`.strip()` 归一化空白后完全相等，不做任何语义/
分词层面的归一化）等于**本批内另一个 id** 的 opus 译文，**且**这两个 id
的 `jp`（frozen 原文）**不相同**——判该行死，计入
`discipline.<channel>.json` 的 `misaligned_hits`。

- **为什么要求"逐字"**：这是错位的确切指纹——被错误挂到这一行的 zh 本该
  是别处的 opus 译文，一字不差地照抄过来。放宽成"相似"/"编辑距离小"会把
  大量"这行几乎没改动、只是顺手润色了一两个字"的正常候选也网进来，误报
  会淹没真信号——这正是本项目吃过的具体亏（ruby 检出 104→5、复现句族数字
  212→1，都是判据太宽把真信号冲掉的先例）。
- **为什么要求"jp 不相同"**：本库存在大量同一句日文反复出现的"复现句族"
  （anchors.yaml/skeleton 明确承认的现象），这些句子的 zh 本来就**应该**
  逐字相同——那是 W4（跨候选一致性检查，Task 11 全段复检的管辖范围）的
  正确行为，不是错位。少了这条限定，复现句族会被整片误杀，把大量本该
  入仓的正确候选错杀。

**残留边界（写清楚，别让后来人以为这里已经全覆盖）**：这道闸只抓一种
确切指纹——"`zh` 逐字等于本批另一行的 opus"。如果模型把错挂的 `zh` 又
顺手润色改写了几个字（不再与任何 opus 逐字相同），本闸**抓不到**，会
放行入仓。这一层残留风险由下游两道闸兜底，而不是本模块的职责：
1. **Task 6 `polish_check.py` 的 R2b 说话人核验**——错位的 zh 大概率带着
   别的说话人前缀（【名字】），与该行原文的说话人对不上，R2b 会报 hard；
2. **Task 7 `polish_triage.py` 的分流**——错位 zh 与该行真正 `opus[id]`
   的编辑距离必然很大（内容完全不相关），不满足自动清关的"小改"条件，
   会被强制落进人工裁决队列，不会被自动清关放过。
本模块的错位侦测只是"确切指纹"这一层最便宜、最不会伪报的一道闸，不是
唯一防线；这三层合起来才是这类问题的完整覆盖。
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, append_jsonl, dumps, read_jsonl
from tools.polishlib import jp_tail as _jp_tail


def _dir_for(label, repo) -> Path:
    """同 `polish_setup._dir_for` / `polish_context._dir_for` 的理由：
    `polishlib.seg_dir()` 硬编码用仓库根，不接受覆盖；这里另起一份，只在
    repo 落空时才退化到默认路径，使 `ingest()`/CLI 都能被 tmp_path 造的
    替身仓库完全接管（测试要求：不得写进真实仓库的 pilot/polish/）。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _sha256_text(s: str) -> str:
    """frozen 内容的文本哈希——不是 `pipelib.sha256_file`（那个是对文件字节
    算，这里是对某个 id 的一段字符串内容算）。模型算不出这个，所以模型只
    回显 `jp_tail`；这里由代码从 frozen 侧补齐。"""
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _norm(s) -> str:
    """错位侦测/空 zh 判定用的归一化——**只做空白层面**，不做任何语义/分词
    归一化：只 `.strip()` 掉首尾空白，`_n`/`_r`/ruby 等控制码原样保留（它们
    是内容的一部分，不是排版噪声，抹掉会让"逐字相同"这条确切指纹变得不准）。
    `None` 归一化为空串，方便和"缺字段"统一处理。"""
    return (s or "").strip()


def _load_json(path, default):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def _find_prompt_hash(plan_path, batch):
    """按批号反查其所属会话的 prompt_hash。`plan.json` 是按 session 号去重
    的累积 list，一个 session 含多个批（`polish_context.plan/render` 产出）。
    找不到时返回 None——调用方必须把 None 当"根本没有这条记录"处理，不能
    与"查到了但恰好是空串"混同，也不能悄悄塞一个 "" 了事。"""
    for r in _load_json(plan_path, []):
        if batch in r.get("batches", []):
            return r.get("prompt_hash")
    return None


def ingest(label, channel, batch, repo=None) -> dict:
    """核验单个 (label, channel, batch) 的模型输出并入仓。

    返回 `{"ok": bool, "added": int, "dead": [{"id":…, "reason":…}, …], "reason": str}`。
    `ok=False` 时 `added==0` 且 `dead==[]`（整批失败不做任何逐行判死记录——
    那一层判定这时已经失去意义：既然整批都不入仓，逐行的死因列表对调用方
    没有实际帮助，`reason` 字段已经把整批失败的原因说清楚了）。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"

    ingested_path = d / f"ingested.{channel}.json"
    ingested = _load_json(ingested_path, {"batches": []})
    if batch in ingested.get("batches", []):
        print(f"ingest: {label}/{channel} 批 {batch} 已入仓，跳过（幂等 no-op）")
        return {"ok": True, "added": 0, "dead": [], "reason": "already ingested"}

    try:
        source_rows = read_jsonl(fz / "source.jsonl")
    except FileNotFoundError:
        reason = f"{fz / 'source.jsonl'} 不存在——该 SEG 尚未 polish_setup.setup() 冻结"
        print(f"ingest 整批失败：{reason}")
        return {"ok": False, "added": 0, "dead": [], "reason": reason}
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    batch_ids = [r["id"] for r in source_rows if r["batch"] == batch]
    if not batch_ids:
        reason = f"{label} 的 frozen/source.jsonl 里没有 batch={batch} 的任何 id"
        print(f"ingest 整批失败：{reason}")
        return {"ok": False, "added": 0, "dead": [], "reason": reason}
    batch_id_set = set(batch_ids)

    try:
        opus_rows = read_jsonl(fz / "opus.jsonl")
    except FileNotFoundError:
        reason = f"{fz / 'opus.jsonl'} 不存在——该 SEG 尚未 polish_setup.setup() 冻结"
        print(f"ingest 整批失败：{reason}")
        return {"ok": False, "added": 0, "dead": [], "reason": reason}
    id2opus = {r["id"]: r["zh"] for r in opus_rows}

    locked = _load_json(fz / "locked.json", {"ids": [], "why": {}})
    locked_ids = set(locked.get("ids", []))
    expected_id_set = batch_id_set - locked_ids

    prompt_hash = _find_prompt_hash(d / "plan.json", batch)
    if prompt_hash is None:
        reason = (f"{label}/plan.json 里查不到批 {batch} 所属的会话（因而拿不到 "
                   "prompt_hash）——这本身是异常：还没渲染过 prompt 就来了 raw，"
                   "不静默填空串，判整批失败")
        print(f"ingest 整批失败：{reason}")
        return {"ok": False, "added": 0, "dead": [], "reason": reason}

    raw_path = d / "raw" / channel / f"b{batch}.out"
    if not raw_path.exists():
        reason = f"raw 文件不存在：{raw_path}"
        print(f"ingest 整批失败：{reason}")
        return {"ok": False, "added": 0, "dead": [], "reason": reason}

    parsed = []
    for lineno, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            reason = (f"raw 不是合法 JSONL：{raw_path} 第 {lineno} 行 JSON 解析失败"
                       f"（{e}）——单行损坏会让「批内覆盖是否完整」失去判定依据，"
                       "整批判死，不入仓任何行")
            print(f"ingest 整批失败：{reason}")
            return {"ok": False, "added": 0, "dead": [], "reason": reason}
        if not isinstance(obj, dict):
            reason = (f"raw 不是合法 JSONL：{raw_path} 第 {lineno} 行是合法 JSON 但"
                       f"不是对象（{type(obj).__name__}）——同上，整批判死")
            print(f"ingest 整批失败：{reason}")
            return {"ok": False, "added": 0, "dead": [], "reason": reason}
        parsed.append(obj)

    # 重复 id：只在"属于本批"的 id 范围内统计——不与"id 不在批内"这条判死
    # 理由混淆（那条对不属于本批的 id 已经有更精确的判死理由）。
    id_counts = Counter(r.get("id") for r in parsed if r.get("id") in batch_id_set)
    dup_ids = {i for i, c in id_counts.items() if c > 1}

    # 错位侦测的比对范围：本批全部 id（含锁定 id，锁定 id 的 opus 内容
    # 同样可以是"被挂错"的来源）的 opus 译文，做空白归一化（不做语义归一）。
    batch_opus_norm = {i: _norm(id2opus.get(i, "")) for i in batch_id_set}

    dead = []
    locked_hits = 0
    misaligned_hits = 0
    candidates = []
    for row in parsed:
        rid = row.get("id")
        if rid not in batch_id_set:
            dead.append({"id": rid, "reason": "id 不在批内"})
            continue
        if rid in locked_ids:
            dead.append({"id": rid, "reason": "锁定 id 出稿"})
            locked_hits += 1
            continue
        if rid in dup_ids:
            dead.append({"id": rid,
                         "reason": "重复 id：批内该 id 出现不止一行，不猜测取舍，全部判死"})
            continue
        want_tail = _jp_tail(id2jp.get(rid, ""))
        got_tail = row.get("jp_tail")
        if got_tail != want_tail:
            dead.append({"id": rid,
                         "reason": f"jp_tail 与 frozen 不符（期望 {want_tail!r}，实收 {got_tail!r}）"})
            continue

        zh_norm = _norm(row.get("zh"))
        if not zh_norm:
            dead.append({"id": rid, "reason": "zh 为空串或缺失"})
            continue

        misaligned_with = next(
            (other for other, other_opus in batch_opus_norm.items()
             if other != rid and zh_norm == other_opus and id2jp.get(rid) != id2jp.get(other)),
            None)
        if misaligned_with is not None:
            dead.append({"id": rid,
                         "reason": f"疑似错位：zh 与本批 id={misaligned_with} 的 opus 逐字"
                                   "相同，但两者原文（jp）不同"})
            misaligned_hits += 1
            continue

        candidates.append(row)

    # 覆盖完整性：判据是"这个 id 有没有在 raw 里出现过"（哪怕那一行随后被
    # 判死），不是"有没有存活成候选"——理由见模块 docstring。
    appeared_ids = {r.get("id") for r in parsed}
    missing = expected_id_set - appeared_ids
    if missing:
        reason = f"批内非锁定 id 覆盖不完整（截断特征）：缺失 {sorted(missing)}"
        print(f"ingest 整批失败：{reason}")
        return {"ok": False, "added": 0, "dead": [], "reason": reason}

    ts = datetime.now(timezone.utc).isoformat()
    out_rows = [{
        "id": row["id"],
        "channel": channel,
        "batch": batch,
        "prompt_hash": prompt_hash,
        "jp_hash": _sha256_text(id2jp.get(row["id"], "")),
        "opus_hash": _sha256_text(id2opus.get(row["id"], "")),
        "zh": row.get("zh"),
        "score": row.get("score"),
        "note": row.get("note", ""),
        "adjudicate": row.get("adjudicate", False),
        "jp_tail": row.get("jp_tail"),
        "ts": ts,
    } for row in candidates]

    append_jsonl(d / f"candidates.{channel}.jsonl", out_rows)

    if locked_hits or misaligned_hits:
        disc_path = d / f"discipline.{channel}.json"
        disc = _load_json(disc_path, {"locked_hits": 0, "misaligned_hits": 0})
        disc["locked_hits"] = disc.get("locked_hits", 0) + locked_hits
        disc["misaligned_hits"] = disc.get("misaligned_hits", 0) + misaligned_hits
        disc_path.write_text(dumps(disc), encoding="utf-8")

    ingested["batches"] = sorted(set(ingested.get("batches", [])) | {batch})
    ingested_path.write_text(dumps(ingested), encoding="utf-8")

    extra_bits = []
    if locked_hits:
        extra_bits.append(f"锁定违规 {locked_hits} 次")
    if misaligned_hits:
        extra_bits.append(f"疑似错位 {misaligned_hits} 次")
    extra = f"，含{'、'.join(extra_bits)}" if extra_bits else ""
    print(f"ingest: {label}/{channel} 批 {batch} 入仓 {len(out_rows)} 行，"
          f"判死 {len(dead)} 行{extra}")
    return {"ok": True, "added": len(out_rows), "dead": dead, "reason": ""}


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 润色候选唯一入仓口")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--channel", required=True, help="执行通道（如 fable/deepseek）")
    ap.add_argument("--batch", type=int, help="批号；与 --all 二选一")
    ap.add_argument("--all", action="store_true", help="扫 raw/<channel>/ 目录下全部批")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    if args.all:
        d = _dir_for(args.seg, args.repo)
        raw_dir = d / "raw" / args.channel
        batches = sorted(
            int(p.stem[1:]) for p in raw_dir.glob("b*.out")
        ) if raw_dir.is_dir() else []
        if not batches:
            print(f"--all：{raw_dir} 下没有找到任何 bN.out")
            return 0
        ok_all = True
        for b in batches:
            r = ingest(args.seg, args.channel, b, repo=args.repo)
            print(dumps({"batch": b, **r}))
            ok_all = ok_all and r["ok"]
        return 0 if ok_all else 1

    if args.batch is not None:
        r = ingest(args.seg, args.channel, args.batch, repo=args.repo)
        print(dumps(r))
        return 0 if r["ok"] else 1

    ap.error("需要 --batch <N>，或改用 --all 扫整个 raw/<channel>/ 目录")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
