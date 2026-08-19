"""P4 润色 pass：SEG 级冻结。

把一个 SEG（config/segments.yaml 里的一条段表条目）的全部输入——原文（按段表
批号从 ledger 取）、opus 车道当前译文（resolve 固化的一个时点快照）、锁定 id
清单（anchors + 已有 patch）、术语/风格/口调（glossary/ 拷贝 + skeleton/
anchors.yaml 拷贝）、该段涉及章节的 notes——一次性拷进
`pilot/polish/<label>/frozen/`，并在同级 `manifest.json` 里记下逐文件哈希与
opus 侧固化时点（forward/patches 的行数与整体哈希）。

冻结之后该 SEG 的所有执行通道共读这一份快照，不再各自去读易变的 opus 车道
数据——`verify()` 用来事后证明 frozen/ 没有漂移。

repo 参数化：`polishlib.seg_dir()` 硬编码用 `pipelib.REPO`（真实仓库根），
不接受 repo 覆盖；本模块的 `setup()/verify()` 必须能被 tmp_path 造的替身仓库
完全接管（测试要求，也是安全要求——不能在单测里意外写进真实仓库的
pilot/polish/），故这里另起 `_dir_for(label, repo)`，只在 repo 落空时才退化
到 polishlib.seg_dir() 的默认路径逻辑。
"""
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_context import glossary_version
from tools.pipelib import REPO, dumps, read_jsonl, sha256_file, write_jsonl
from tools.polishlib import base_label, is_ignored_extra
from tools.resolve import resolve_map


def _dir_for(label, repo) -> Path:
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _seg_entry(repo, label) -> dict:
    segs = yaml.safe_load((Path(repo) / "config" / "segments.yaml").read_text(encoding="utf-8"))
    for s in segs:
        if s["label"] == label:
            return s
    # P5 段别名：p5segN-… 剥前缀映射回 P4 段表行（区间/章节/lane 完全复用），
    # 见 polishlib.base_label 的说明——P5 段不入段表是分区完备闸的要求。
    base = base_label(label)
    if base is not None:
        for s in segs:
            if s["label"] == base:
                return s
    raise KeyError(f"config/segments.yaml 里没有 label={label!r} 的段")


_ROUND_MARKER_RE = re.compile(r"^<!-- amplify-round:\d+ -->$\n?", re.MULTILINE)


def _seed_rulings(label, repo) -> str:
    """新 SEG 的 `frozen/rulings.md` 初值：**承接此前各段的裁决纪要**。

    2026-08-12 修复。此前这里每次写一个空壳，从不看前段——而 runbook §九 明写
    `polish_amplify --digest` 的产物「自动前馈进**下一 SEG** 的 render()」。
    那句话一直是假的：SEG-3 的 11135 字节纪要（299 条裁决的意图）一个字都没到
    SEG-4，是 SEG-4 的执行通道报「rulings.md 一节是空的」才暴露出来。

    这正是本项目反复吃亏的那条断链的工装侧成因——CLAUDE.md 记的「A 章纪要提请、
    B 章批次落笔」传不过去，P4 层同样传不过去。

    ⚠ **必须剥掉 `<!-- amplify-round:N -->` 标记**：那是放大扫描的轮数闸计数，
    连同纪要抄进新段会让新段一出生就被判定「本段的 amplify 配额已用掉」，
    `polish_amplify --scan-prompt` 直接拒绝装配。承接的是**内容**，不是**配额**。

    ⚠ **只承接紧邻的前一段（有内容的那一段），不是此前每一段**。

    初版遍历了此前全部段，而每段的 rulings.md 里**已经含着它自己承接来的部分**
    ——链条本来就是传递的，再逐段叠加就是重复计入。实测增长：
    seg4 12K → seg5 54K → **seg6 93K**，seg1/seg3/seg4 的正文在 seg6 里出现了两次。
    照此下去 seg7 会到二十万字节量级，而 rulings.md 是**嵌进生产 prompt 的**，
    等于让模型把同样的内容读两遍、还挤占上下文。

    往回找「最近一个有内容的前段」而不是「上一个序号」，是因为 seg0/seg2
    没跑过 digest、rulings 是空壳；跳过它们才能接上真正的链。
    """
    segs = yaml.safe_load((Path(repo) / "config" / "segments.yaml").read_text(encoding="utf-8"))
    me = next((s for s in segs if s["label"] == label), None)
    out = [f"# {label} 润色裁决与前序纪要", "（追加式）", ""]
    if me is not None:
        prior_labels = [x["label"] for x in
                        sorted((x for x in segs if x["seg"] < me["seg"]),
                               key=lambda x: x["seg"], reverse=True)]
    else:
        # P5 段别名：前段链 = 更早的 P5 段（倒序）→ 整条 P4 链（倒序）。
        # p5seg0 的「最近有内容前段」即 P4 链尾（seg7-e2 的 frozen/rulings.md
        # 是全链最新累计版，含 SEG-7 段末追加的收口裁定）；p5segN 则先接
        # p5seg(N-1)。链条传递性同 P4：找到第一个有内容者即停。
        base = base_label(label)
        base_me = next((s for s in segs if s["label"] == base), None) if base else None
        if base_me is None:
            return "\n".join(out[:2]) + "\n"
        from tools.polishlib import P5_PREFIX
        p5_prior = [P5_PREFIX + x["label"] for x in
                    sorted((x for x in segs if x["seg"] < base_me["seg"]),
                           key=lambda x: x["seg"], reverse=True)]
        p4_all = [x["label"] for x in sorted(segs, key=lambda x: x["seg"], reverse=True)]
        prior_labels = p5_prior + p4_all
    for s in [{"label": pl} for pl in prior_labels]:
        p = _dir_for(s["label"], Path(repo)) / "frozen" / "rulings.md"
        if not p.exists():
            continue
        body = _ROUND_MARKER_RE.sub("", p.read_text(encoding="utf-8"))
        # 去掉前段自己的标题与「（追加式）」，只留正文
        body = "\n".join(ln for ln in body.splitlines()
                         if not ln.startswith("# ") and ln.strip() != "（追加式）").strip()
        if not body:
            continue
        # 找到最近一个有内容的前段就停——它已经承接了更早的各段
        out.append(f"## 承接自 {s['label']}（前段裁决纪要，对本段同样有效）")
        out.append("")
        out.append(body)
        out.append("")
        break
    return "\n".join(out) + "\n"


def _seg_ids(repo, lane, lo, hi):
    """按段表 [lo, hi] 批号区间、限定 lane，从 data/batches.jsonl 收集 id 全集
    （保持批次出现顺序，同批内保持 ids 原序）与 id→batch 映射。"""
    ids, id2batch = [], {}
    for r in read_jsonl(Path(repo) / "data" / "batches.jsonl"):
        if r["lane"] == lane and lo <= r["batch"] <= hi:
            for i in r["ids"]:
                ids.append(i)
                id2batch[i] = r["batch"]
    return ids, id2batch


def _anchor_ids(repo) -> set:
    """skeleton/anchors.yaml 里全部 item 的 id 集合（跨 chapter block）。"""
    doc = yaml.safe_load((Path(repo) / "skeleton" / "anchors.yaml").read_text(encoding="utf-8")) or []
    ids = set()
    for block in doc:
        for item in block.get("items", []):
            ids.add(item["id"])
    return ids


def _anchor_twin_ids(anchor_ids: set, jp_by_id: dict) -> set:
    """jp **字面全同**于某条锚点、但自己不是锚点的 id。

    锚点的约束是「这一句一律逐字沿用定译」，可原文在别处又出现了一次时，
    那一处的 id 不在 `anchors.yaml` 里，于是形式上成了可随便改的普通行——
    **改了必然打破锚点的逐字一致，而闸不会响**。

    SEG-3 实测暴露了这个洞：`739`（b93）与软锁锚点 `13440` 的 jp 全同却不在
    `soft_ids` 里。那一轮是执行通道自己按锚点维持住并登记了 note——**那是运气
    不是闸**。全库共 11 条这样的孪生行（seg5 七条、seg7 两条、seg3/seg4 各一条）。

    归入软锁而非硬锁：它们本身没有被单独人裁过，约束来自锚点这条一般性定译，
    与锚点行本身同档——可以出稿，但改动必须带 `adjudicate=true`、永不自动清关。
    """
    anchor_jp = {jp_by_id[i] for i in anchor_ids if i in jp_by_id}
    return {i for i, jp in jp_by_id.items() if jp in anchor_jp and i not in anchor_ids}


def _locked_payload(locked_ids, anchor_ids, patched_ids, twin_ids=frozenset()) -> dict:
    """硬锁/软锁分类（2026-08-07 用户裁定：锚点行从硬锁改软锁）。

    - **硬锁**（`hard_ids`）＝该 id 在冻结时点已有人裁 patch（`patched_ids`）
      ——不得出稿，出稿即判死（`polish_ingest`）。
    - **软锁**（`soft_ids`）＝`skeleton/anchors.yaml` 锚点行，且**不**在
      `patched_ids` 里——可以出稿；`zh` 有改动必须带 `adjudicate=true`
      （否则判死），且改动行永不自动清关、必进裁决队列不被 K 挤出
      （`polish_triage`）。
    - **两者都命中时按裁定固定归为硬锁**：`patched_ids` 是这个 id 在冻结
      时点已经有的一条**具体、更新**的人裁决定，比 anchors.yaml 的一般性
      定译指引更"重"——一个 id 若已经被单独裁过，理应比一条通用锚点指引
      更不可触碰，取更保守（更严格）的那一档。`hard_ids`/`soft_ids` 因此
      互斥、并集恒等于 `locked_ids`（=`anchor_ids | twin_ids | patched_ids`）。
    - **孪生行**（`twin_ids`，2026-08-12 补）＝ jp 与某条锚点字面全同、自己却
      不是锚点的 id，与锚点同档归软锁，`why` 标 `anchor_twin`。补这一档之前，
      这些行形式上是可随便改的普通行，改了必然打破锚点逐字一致而闸不响。

    `why` 字段保留（旧消费者只用它做展示标注，不做行为判断），取值与
    `hard_ids`/`soft_ids` 的分类口径同步（tie-break 从旧版的固定标 "anchor"
    改为固定标 "patched"——旧版两档行为完全一样，标哪个纯属展示用词；现在
    行为分叉了，`why` 的字面值必须如实反映真正生效的那一档，不能自相矛盾）。
    """
    hard_ids = set(locked_ids) & patched_ids
    soft_ids = set(locked_ids) & (anchor_ids | twin_ids) - patched_ids
    why = {}
    for i in sorted(locked_ids):
        if i in patched_ids:
            why[str(i)] = "patched"
        elif i in anchor_ids:
            why[str(i)] = "anchor"
        else:
            why[str(i)] = "anchor_twin"
    return {
        "ids": sorted(locked_ids),
        "why": why,
        "hard_ids": sorted(hard_ids),
        "soft_ids": sorted(soft_ids),
    }


def _copy_glossary(repo, fz: Path) -> None:
    """glossary/ 术语层拷贝：active.json + speakers.json + voices/ + style.md
    + polish.md，外加 skeleton/anchors.yaml（伏笔锚点定译——正文润色对照的
    一部分，放进同一个 glossary/ 子目录，与执行通道读取路径一致）。

    **speakers.json 是评审 Task 6 时发现并回填的缺口**：`check_batch.check()`
    的 R2b（【】说话人结构对齐 + 名字映射）需要这份表，`tools/polish_check.py`
    的机械闸读它——而"冻结之后所有执行通道共读同一份快照，不再各自去读
    易变的活仓库数据"是本模块顶部 docstring 明写的设计原则（`polish_context.
    render()` 也专门有变异测试钉死这一点：从活仓库读 glossary 必须让测试
    变红）。原实现漏拷这一个文件，等于让 R2b 的判定结果绕过冻结面直接依赖
    活仓库当前状态——SEG 冻结后若活仓库的 speakers.json 被改动，该 SEG 的
    机械闸结论会静默漂移，且 `verify()` 完全看不见（它只哈希 frozen 里已
    登记的文件，不知道"本该拷贝但没拷贝"这件事）。"""
    repo = Path(repo)
    g = fz / "glossary"
    g.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "glossary" / "active.json", g / "active.json")
    shutil.copy2(repo / "glossary" / "speakers.json", g / "speakers.json")
    shutil.copy2(repo / "glossary" / "style.md", g / "style.md")
    shutil.copy2(repo / "glossary" / "polish.md", g / "polish.md")
    shutil.copytree(repo / "glossary" / "voices", g / "voices")
    shutil.copy2(repo / "skeleton" / "anchors.yaml", g / "anchors.yaml")


def _copy_notes(notes_src: Path, notes_dst: Path, chapters) -> list:
    """按段表条目的 chapters 列表逐章拷贝 notes（opus 车道 notes/ 是按章命名
    的 25 个文件，没有批号维度——按批号取是 brief 骨架里的错误，已被用户当场
    改正）。某章没有对应 notes 文件时跳过，绝不静默：跳过清单既打进 stderr，
    也随 setup() 返回的目录一起落进 manifest.json 的 notes_missing 字段。"""
    notes_dst.mkdir(parents=True, exist_ok=True)
    missing = []
    for ch in chapters:
        src = Path(notes_src) / f"{ch}.md"
        if src.exists():
            shutil.copy2(src, notes_dst / f"{ch}.md")
        else:
            missing.append(ch)
    if missing:
        print(f"!! 告警：{notes_src} 下缺少以下章节的 notes 文件，已跳过：{missing}",
              file=sys.stderr)
    return missing


# 「这个 SEG 已经在产」的判据：出现任何一个下游产物就算。三者都是
# 冻结之后才可能出现的东西（候选=已派发过通道并 ingest；裁决=人已经在裁；
# 分流=已经跑过 triage），且都**以冻结面为基准**——重建 frozen/ 会让它们的
# 基准静默换掉（见 setup() 的拒绝闸 docstring）。
IN_PRODUCTION_GLOBS = ("candidates.*.jsonl", "decisions.jsonl", "triage.json")


def in_production(d: Path) -> list:
    """`d` 下已存在的"在产产物"相对文件名（排序）。空列表＝尚未点火。"""
    found = []
    for pat in IN_PRODUCTION_GLOBS:
        found.extend(p.name for p in d.glob(pat) if p.is_file())
    return sorted(found)


class SegInProductionError(RuntimeError):
    """已在产的 SEG 被要求重新冻结，且没给 `--force`。"""


def setup(label, opus_data, repo=None, force=False) -> Path:
    """建/重建 `pilot/polish/<label>/frozen/` + `manifest.json`。

    ## 已在产的 SEG 拒绝重跑（最终评审 I5）

    `setup()` 是**破坏性**的：`shutil.rmtree(frozen)` 之后按**当前**车道状态
    整体重建，`manifest.json` 一并重写。对一个已经点火的 SEG 重跑，后果是
    一连串**静默**的基准置换，而不是一个错误：

    - `frozen/opus.jsonl` 会把本轮刚落的 `reason=polish` patch 吃进去，于是
      "润色起点"变成了"润色结果"——此后所有 `edit` 幅度、`zh==opus` 零改动
      判定、autoclear 阈值全部对着一个错的基线算；
    - `manifest["files"]` 跟着重写，`verify()` 事后**恒绿**——它比对的是刚
      写下的那份哈希，看不出基准被换过；
    - `frozen/rulings.md` 被清成空壳，连同 `<!-- amplify-round:N -->` 轮数闸
      标记一起没了，"每 SEG 限一轮放大扫描"随之失效；
    - `manifest["opus_at"]` 冻结基线前移，`polish_commit` 的"冻结后人裁 patch
      拒写闸"（评审 I4）也跟着失去参照。

    这些都不会报错，只会让后续判定安静地跑在错误的基准上。此前唯一的防线是
    runbook 里一句"不要重跑"——纪律，不是机制。现在：目录里出现
    `candidates.*.jsonl` / `decisions.jsonl` / `triage.json` 任何一个，就
    `SegInProductionError` 拒绝执行（**在任何文件被删除或写入之前**），除非
    显式 `force=True`（CLI `--force`）。拒绝信息逐条说清会毁掉什么。
    """
    repo = Path(repo) if repo is not None else REPO
    opus_data = Path(opus_data)

    d_guard = _dir_for(label, repo)
    existing = in_production(d_guard) if d_guard.is_dir() else []
    if existing and not force:
        raise SegInProductionError(
            f"{label} 已经点火（{d_guard} 下存在：{', '.join(existing)}），"
            "拒绝重新冻结。重跑 setup() 会 rmtree 掉 frozen/ 并按**当前**车道"
            "状态重建，后果全部是静默的：①opus.jsonl 会把本轮已清关的 "
            "reason=polish patch 吃成新的「润色起点」，此后 edit 幅度/零改动"
            "判定/autoclear 阈值全部基于错误基线；②manifest 一并重写，"
            "verify() 事后恒绿、看不出基准被换过；③frozen/rulings.md 连同 "
            "amplify 轮数闸标记被清零，「每 SEG 限一轮」失效；④manifest."
            "opus_at 冻结基线前移，polish_commit 的「冻结后人裁 patch 拒写闸」"
            "失去参照。确实要重来请显式加 --force（并先自己备份/核对上述四项）。")

    seg = _seg_entry(repo, label)
    lo, hi = seg["batches"]
    ids, id2batch = _seg_ids(repo, seg["lane"], lo, hi)

    led = {r["id"]: r for r in read_jsonl(opus_data / "ledger.jsonl")}
    missing_led = [i for i in ids if i not in led]
    if missing_led:
        raise KeyError(f"{opus_data}/ledger.jsonl 缺失该段 id：{missing_led}")

    fwd = list(read_jsonl(opus_data / "forward.jsonl"))
    pat_path = opus_data / "patches.jsonl"
    pat = list(read_jsonl(pat_path)) if pat_path.exists() else []
    cur = resolve_map(fwd, pat)
    missing_zh = [i for i in ids if i not in cur]
    if missing_zh:
        raise KeyError(f"opus 车道 forward/patches 尚未覆盖该段 id：{missing_zh}"
                        "——该 SEG 在 opus 车道还没译完，不该在此刻冻结")

    d = _dir_for(label, repo)
    fz = d / "frozen"
    if fz.exists():
        shutil.rmtree(fz)
    fz.mkdir(parents=True)

    write_jsonl(fz / "source.jsonl",
                [{"id": i, "jp": led[i]["jp"], "batch": id2batch[i]} for i in ids])
    write_jsonl(fz / "opus.jsonl", [{"id": i, "zh": cur[i]} for i in ids])

    anchor_ids = _anchor_ids(repo)
    twin_ids = _anchor_twin_ids(anchor_ids, {i: r["jp"] for i, r in led.items()})
    patched_ids = {r["id"] for r in pat}
    locked_ids = set(ids) & (anchor_ids | twin_ids | patched_ids)
    (fz / "locked.json").write_text(
        dumps(_locked_payload(locked_ids, anchor_ids, patched_ids, twin_ids)),
        encoding="utf-8")

    _copy_glossary(repo, fz)
    notes_missing = _copy_notes(opus_data / "notes", fz / "notes", seg["chapters"])

    (fz / "rulings.md").write_text(_seed_rulings(label, repo), encoding="utf-8")

    files = {}
    for p in sorted(fz.rglob("*")):
        if p.is_file():
            files[p.relative_to(d).as_posix()] = sha256_file(p)

    forward_p = opus_data / "forward.jsonl"
    manifest = {
        "label": label,
        "batches": [lo, hi],
        "glossary_v": glossary_version(repo),
        "files": files,
        "opus_at": {
            "forward_lines": len(fwd),
            "patches_lines": len(pat),
            "forward_sha": sha256_file(forward_p) if forward_p.exists() else None,
            "patches_sha": sha256_file(pat_path) if pat_path.exists() else None,
        },
        "notes_missing": notes_missing,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    (d / "manifest.json").write_text(dumps(manifest), encoding="utf-8")
    return d


def verify(label, repo=None) -> list:
    """frozen/ 逐文件哈希 ↔ manifest.json **双向**比对。空列表=绿。不得抛异常——
    manifest 缺失、frozen 里某文件被删，都要落成可读的漂移描述。

    双向：①manifest 登记的每个文件是否存在、哈希对不对（正向）；②frozen/ 实际
    目录树里是否有 manifest 从未登记过的文件（反向）。只查正向会漏掉"setup() 之
    后有人往 frozen/notes/、frozen/glossary/voices/ 这类整目录消费的地方多丢了
    一个文件"——只要不覆盖已登记的文件名，正向扫描永远看不见它，而下游会把它
    当成这个 SEG 冻结集的一部分一并读走。"""
    d = _dir_for(label, repo)
    mp = d / "manifest.json"
    if not mp.exists():
        return [f"{mp} 不存在——尚未 setup() 或已被清理"]
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    known = manifest.get("files", {})
    drift = []
    for rel, want in known.items():
        p = d / rel
        if not p.exists():
            drift.append(f"{rel}: 缺失")
            continue
        got = sha256_file(p)
        if got != want:
            drift.append(f"{rel}: 哈希不符")
    fz = d / "frozen"
    if fz.is_dir():
        for p in sorted(fz.rglob("*")):
            if p.is_file():
                if is_ignored_extra(p):
                    continue
                rel = p.relative_to(d).as_posix()
                if rel not in known:
                    drift.append(f"{rel}: 未登记（凭空多出）")
    return drift


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="SEG 冻结：建 frozen/ 快照 + manifest.json")
    ap.add_argument("--seg", help="段表 label，如 seg1-s2")
    ap.add_argument("--opus-data", help="opus 车道 data 目录（pilot/lanes/opus/data）")
    ap.add_argument("--verify", metavar="LABEL", help="只校验，不重新冻结")
    ap.add_argument("--force", action="store_true",
                     help="已点火的 SEG（存在 candidates/decisions/triage）默认拒绝重新"
                          "冻结；本开关强制执行——会静默置换全部下游判据基准，看清"
                          "拒绝信息里列的四条后果再用")
    args = ap.parse_args(argv)

    if args.verify:
        drift = verify(args.verify)
        if drift:
            print(f"冻结校验：漂移 {len(drift)} 处", file=sys.stderr)
            for x in drift:
                print(f"  - {x}", file=sys.stderr)
            return 1
        print("冻结校验：无漂移")
        return 0

    if args.seg and args.opus_data:
        try:
            d = setup(args.seg, args.opus_data, force=args.force)
        except SegInProductionError as e:
            print(f"拒绝冻结：{e}", file=sys.stderr)
            return 3
        print(f"冻结完成：{d}")
        return 0

    ap.error("需要 --seg 与 --opus-data 一起用，或单独 --verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
