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

## 硬锁 / 软锁（2026-08-07 用户裁定：锚点行从硬锁改软锁）

`frozen/locked.json` 现在区分 `hard_ids`（该 id 冻结时点已有人裁 patch）与
`soft_ids`（`skeleton/anchors.yaml` 锚点行，且未被覆盖为硬锁——见
`polish_setup._locked_payload` 的 tie-break 规则）。两者待遇不同：

- **硬锁**：不得出稿，出稿即判死（`locked_hits`），与旧版行为完全一致。
- **软锁**：**可以出稿**——它不再被排除在"批内非锁定 id 必须覆盖完整"的
  期望之外（`expected_id_set` 只再扣掉硬锁），模型必须像对待普通行一样为
  它产出一行：
  - `zh` 归一后（`_norm`，仅 `.strip()`）与该 id 的 opus 逐字相同 → 视为
    "没改"，正常放行，走后续候选/misalignment 检测，最终在 `polish_triage`
    里落桶 1，无特殊待遇；
  - `zh` 与 opus 不同（真的动了这一行）但 `adjudicate` 不是 `true` →
    判死（`soft_lock_violations`）——这是"锚点句被静默改动"，必须显式
    请裁才放行；
  - `zh` 与 opus 不同且 `adjudicate=true` → 正常放行，`polish_triage`
    那一层会把它强制摘进裁决队列（不进自动清关、不被 K 挤出）。

旧格式 `locked.json`（没有 `hard_ids`/`soft_ids` 键，SEG 冻结面改版之前
落盘的产物）向后兼容：退化为"把 `ids`（旧版全集）整体当硬锁、`soft_ids`
为空集"——即完全复现旧版行为（不出稿即安全），不会因为读到旧格式冻结面
就意外放行本来不该出现的锚点行。

## 判死 vs 整批失败

**判死**（该行不入仓，同批其余合法行照常入仓）：
- id 不在这一批里（批号对不上，或者干脆不是这个 SEG 的任何 id）；
- 硬锁 id 出稿（额外计入 `discipline.<channel>.json`——纪律画像，衡量该
  通道有多少次试图对硬锁行出稿）；
- 软锁 id 改动但未显式 `adjudicate=true`（额外计入 `discipline.<channel>.
  json` 的 `soft_lock_violations`）；
- 批内该 id 出现不止一行（重复 id——模型输出错位的典型征兆，见下）；
- `jp_tail` 与 frozen 重算的期望值不符；
- `zh` 为空串或缺 `zh` 字段——空译文没有任何下游用途，让它进仓只会把问题
  推给后面（评审 Critical 修复轮实测：这类行原先被静默透传）；
- `zh` 字段类型非法（合法 JSON 但不是字符串，如 `12345`/`true`/数组/对象）
  ——评审 Important 修复轮实测：原先会在归一化时 `AttributeError` 崩溃，
  穿透整个 `ingest()`（CLI `--all` 因此整体中断，而不是"该行判死、继续
  扫下一批"），现改为显式判死；
- **`zh` 逐字等于本批内另一个 id 的 opus 译文、那两个 id 的 `jp` 不相同、
  且该行的 `zh` 不等于它自身 id 的 opus**（第三条是评审用真实语料复核
  伪报率后追加的收窄）——错位嫌疑，额外计入 `discipline.<channel>.json`
  的 `misaligned_hits`（评审两轮修复新增，见下方"错位侦测"专节）。

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
- **第三条收窄（评审用真实语料复核后追加）：`zh` 若与该行自身 id 的
  opus 逐字相同，一律不判错位**——即使这段文字在批内别的 id 上也恰好
  出现、且那个 id 的 jp 不同，也不判死。理由：评审读了真实
  `ledger.jsonl`/`forward.jsonl`/`patches.jsonl` 统计，全库"zh 逐字相同、
  jp 不同"的巧合有 527 对，缩到"同批内"（错位侦测实际比对的范围）仍有
  21 对、38 个 id、覆盖约 5% 的批——抽样全是正当的短促应答/近义收敛
  （`「ん」`/`「うん」`→「嗯」，`「え？」`/`「ええ？」`→「诶？」，
  `どうしたの？`/`どうかした？`→「怎么了？」）。这**不是概率性伪报**，
  而是**确定性**的：只要某通道对这类短行"不改"（契约里最常见、最正确
  的动作），这些批里对应的两行就会被双双误杀。第三条收窄精确对冲这个
  面："zh == 自身 opus" 就是"这行没改"，对本 id 天然正确，与它在别处
  是否巧合出现无关；而这个条件在轮转错位攻击里恒不成立（错位时 zh 挂的
  是别人的 opus，绝不等于自身 opus），所以不削弱错位防线本身。

**残留边界（写清楚，别让后来人以为这里已经全覆盖或已经零伪报）**：

1. **漏检面**（这道闸只抓一种确切指纹，"zh 逐字等于本批另一行的
   opus"）：如果模型把错挂的 `zh` 又顺手润色改写了几个字（不再与任何
   opus 逐字相同），本闸**抓不到**，会放行入仓。这一层残留风险由下游
   两道闸兜底，而不是本模块的职责：
   - **Task 6 `polish_check.py` 的 R2b 说话人核验**——错位的 zh 大概率
     带着别的说话人前缀（【名字】），与该行原文的说话人对不上，R2b 会
     报 hard；
   - **Task 7 `polish_triage.py` 的分流**——错位 zh 与该行真正
     `opus[id]` 的编辑距离必然很大（内容完全不相关），不满足自动清关的
     "小改"条件，会被强制落进人工裁决队列，不会被自动清关放过。
2. **加了第三条收窄之后仍然残留的伪报面**：`zh` **被改动过**（不等于
   自身 opus）、**改动后恰好逐字等于批内另一 id 的 opus**、且两行 jp
   不同——这种情形仍会被判死。也就是说第三条收窄只覆盖"完全不改"这个
   最常见的正当动作，不覆盖"改出来的新文本恰好撞上了另一句的现行译文"
   这种更巧合、更罕见的情形；后者理论上仍可能是正当的润色巧合（而非
   错位），本模块选择不为这个更窄的剩余面再加收窄条件——再收窄一层，
   判据的确切性会开始打折扣，与"逐字指纹、宁窄勿宽"的设计初衷冲突。
   这个残留伪报如果发生，同样会被上面第 1 点的两道下游闸接住（人工
   裁决队列兜底），不会造成数据丢失，只是需要人工复核一次。

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
from tools.polish_amplify import mark_round_if_complete
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
    `None` 归一化为空串，方便和"缺字段"统一处理。

    **类型防御（评审 Important 修复轮追加）**：只接受 `str`，其余类型
    （int/bool/list/dict/…）一律归一化为空串，绝不 `.strip()` 一个非字符串
    对象——`ingest()` 的调用点在此之前已经用 `isinstance` 显式判死了非法
    类型的 `zh`，把它挡在真正走到这个函数之前；这里的类型防御是第二层
    保险（比如 `batch_opus_norm` 理论上也吃 frozen 数据，不该崩，但没有
    再单独判死的必要），不是主防线。"""
    if not isinstance(s, str):
        return ""
    return s.strip()


def _load_json(path, default):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def _find_prompt_hash(plan_path, batch, channel=None):
    """按批号反查其所属会话的 prompt_hash。`plan.json` 是按 session 号去重
    的累积 list，一个 session 含多个批（`polish_context.plan/render` 产出）。
    找不到时返回 None——调用方必须把 None 当"根本没有这条记录"处理，不能
    与"查到了但恰好是空串"混同，也不能悄悄塞一个 "" 了事。

    **`channel` 参数（评审 Task 9 Finding B 追加）**：`polish_context.
    render()` 产出的普通会话记录天然是"channel 无关"的——同一份 prompt
    文字本来就是让多个 channel（fable/deepseek/…）各自去读同一份，从不在
    自己的记录里写 `channel` 字段。但 `polish_amplify.scan_prompt()` 装配
    的是一份**内容不同**的 prompt（纪要+四桶全景，不是普通逐批正文），
    却覆盖**同一批号区间**——如果不区分，按批号找到的"第一条匹配"会是
    更早写入的普通会话记录，导致 amplify 候选的 `prompt_hash` 记成别的
    channel 的文档（评审实测：确实如此，见 `polish_amplify.py` 原 concern
    与本次修复）。

    修法：只有 `scan_prompt()` 这类"专属某 channel"的记录才会带
    `"channel"` 字段（见 `polish_amplify.scan_prompt()`）；普通会话记录
    永远不带这个字段。查找时：
    1. 若调用方传了 `channel`，先只在"批号吻合且 `record['channel'] ==
       channel`"的记录里找——存在就直接返回，不受列表顺序、不受其他
       channel 记录干扰；
    2. 找不到（该 channel 从未写过专属记录——绝大多数普通 channel 都是
       这种情况）→ **退化到旧的、channel 无关的"批号匹配即返回第一条"**
       —— 对存量 `plan.json`（记录里压根没有 `channel` 键）完全透明，
       行为与本参数加入之前逐位一致（`test_find_prompt_hash_backward_
       compatible_without_channel_field` 钉死这一点）。
    """
    records = _load_json(plan_path, [])
    if channel is not None:
        for r in records:
            if batch in r.get("batches", []) and r.get("channel") == channel:
                return r.get("prompt_hash")
    for r in records:
        if batch in r.get("batches", []):
            return r.get("prompt_hash")
    return None


def _maybe_mark_amplify_round(label, channel, repo) -> None:
    """`ingest()` 对每一次 `ok=True` 的调用都会喊一句——`channel != "amplify"`
    时是零成本 no-op（普通生产通道的 ingest 不该被这一条拖慢，也不该受
    amplify 专属逻辑影响）。真正的判定（"这一轮是否已经真正覆盖全部批号、
    该不该在此刻消耗一次轮次配额"）全部委托给
    `tools.polish_amplify.mark_round_if_complete()`——本模块不重复实现
    一份"什么算完成一轮"的逻辑，那是 `polish_amplify` 的业务知识（轮数闸
    标记格式、`CFG['amplify_rounds']`、SEG 全部批号从哪读），`polish_
    ingest` 只负责"amplify 通道成功入仓了一次，问一句要不要记账"。见
    2026-08-07 修复：旧版标记写在 `polish_amplify.scan_prompt()` 装配
    时，导致"渲染了 prompt 但从未真正执行"的一轮被误记成"已经跑完"
    （SEG-1 `seg1-s2` 实测踩到）。"""
    if channel == "amplify":
        mark_round_if_complete(label, repo=repo)


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
        _maybe_mark_amplify_round(label, channel, repo)
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
    # 旧格式兼容：没有 hard_ids/soft_ids 键时，把 ids（旧版全集）整体当硬锁
    # ——完全复现旧版"锚点行也不得出稿"的行为，不因读到旧冻结面就意外放行。
    if "hard_ids" in locked or "soft_ids" in locked:
        hard_ids = set(locked.get("hard_ids", []))
        soft_ids = set(locked.get("soft_ids", []))
    else:
        hard_ids = set(locked.get("ids", []))
        soft_ids = set()
    expected_id_set = batch_id_set - hard_ids

    prompt_hash = _find_prompt_hash(d / "plan.json", batch, channel=channel)
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
    soft_violations = 0
    candidates = []
    for row in parsed:
        rid = row.get("id")
        if rid not in batch_id_set:
            dead.append({"id": rid, "reason": "id 不在批内"})
            continue
        if rid in hard_ids:
            dead.append({"id": rid, "reason": "硬锁 id 出稿"})
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

        zh_raw = row.get("zh")
        if zh_raw is None:
            dead.append({"id": rid, "reason": "zh 为空串或缺失"})
            continue
        if not isinstance(zh_raw, str):
            dead.append({"id": rid,
                         "reason": f"zh 字段类型非法：期望字符串，实收 {type(zh_raw).__name__}"})
            continue
        zh_norm = _norm(zh_raw)
        if not zh_norm:
            dead.append({"id": rid, "reason": "zh 为空串或缺失"})
            continue

        # 软锁（锚点行）改动必须显式 adjudicate=true，否则判死——见模块
        # docstring"硬锁/软锁"专节。判据同 `polish_triage._ws_equal`：只做
        # 空白归一（`_norm` 即 `.strip()`），不剥控制码/ruby——一次纯控制码
        # 改动同样算"动了这一行"，不能被悄悄放过不请裁。
        if rid in soft_ids and zh_norm != batch_opus_norm.get(rid, "") \
                and not row.get("adjudicate", False):
            dead.append({"id": rid,
                         "reason": "软锁 id（锚点行）有改动但未显式 adjudicate=true，判死"})
            soft_violations += 1
            continue

        # 收窄（评审真实语料伪报统计后追加）：这一行的 zh 若与它自身 id 的
        # opus 逐字相同，一律不判错位——"zh == 自身 opus" 就是"这行没改"，
        # 不管这段文字是否在批内别处也出现过，它对本 id 天然正确。轮转攻击
        # 里这个条件恒不成立（错位时 zh 挂的是别人的 opus，不等于自身
        # opus），所以不削弱错位防线；但能一次性消掉"短促应答/近义收敛"
        # 这整类确定性伪报（见模块 docstring"残留边界"一节的数据）。
        own_opus_norm = batch_opus_norm.get(rid, "")
        misaligned_with = None
        if zh_norm != own_opus_norm:
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
        reason = f"批内非硬锁 id 覆盖不完整（截断特征，含软锁 id——它们也要出现一行）：缺失 {sorted(missing)}"
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

    if locked_hits or misaligned_hits or soft_violations:
        disc_path = d / f"discipline.{channel}.json"
        disc = _load_json(disc_path, {"locked_hits": 0, "misaligned_hits": 0,
                                       "soft_lock_violations": 0})
        disc["locked_hits"] = disc.get("locked_hits", 0) + locked_hits
        disc["misaligned_hits"] = disc.get("misaligned_hits", 0) + misaligned_hits
        disc["soft_lock_violations"] = disc.get("soft_lock_violations", 0) + soft_violations
        disc_path.write_text(dumps(disc), encoding="utf-8")

    ingested["batches"] = sorted(set(ingested.get("batches", [])) | {batch})
    ingested_path.write_text(dumps(ingested), encoding="utf-8")

    extra_bits = []
    if locked_hits:
        extra_bits.append(f"硬锁违规 {locked_hits} 次")
    if soft_violations:
        extra_bits.append(f"软锁未请裁 {soft_violations} 次")
    if misaligned_hits:
        extra_bits.append(f"疑似错位 {misaligned_hits} 次")
    extra = f"，含{'、'.join(extra_bits)}" if extra_bits else ""
    print(f"ingest: {label}/{channel} 批 {batch} 入仓 {len(out_rows)} 行，"
          f"判死 {len(dead)} 行{extra}")
    _maybe_mark_amplify_round(label, channel, repo)
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
