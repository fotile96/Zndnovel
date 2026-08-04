"""P2 试点车道搭建与冻结校验。

车道＝一份独立的译文线 + 一份冻结的骨架/术语快照：只读数据用符号链接（同源、
省空间），skeleton/ 与 glossary/ 用拷贝（拷贝即冻结，杜绝试点中途仓库侧升版
泄漏进任一车道）。spec：docs/superpowers/specs/2026-07-31-p2-pilot-design.md §3。

车道根在 `pilot/lanes/`（不在 `work/`）：`work/` 整体 gitignore，而车道内的
`data/forward.jsonl`/`data/patches.jsonl`（8000+ 行译文、约 6.6M token 成本）
是 spec §8 明确要求逐批 commit 入库的产出物，放在 `work/` 下会让入库操作全部
静默失败（终审 C2）。车道内部仍有需要 gitignore 的中间产物（`work/`、
`skeleton/`、`glossary/` 冻结拷贝、指向仓库的符号链接）——见仓库根
`.gitignore` 里 `pilot/lanes/*/...` 那几条。
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.check_voices_anchors import check as _check_voices_anchors
from tools.pipelib import REPO, dumps, sha256_file

LANES_ROOT = REPO / "pilot" / "lanes"

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


def _sha256_dir(path) -> str:
    """glossary/voices/ 这类目录的确定性哈希：按文件名排序后逐份把「文件名 +
    内容」都喂进同一个 sha256。只哈希内容不够——把某份口调表整个删掉，或把
    一份内容不变的文件改名（如 naoya.md → naoya2.md），纯内容拼接哈希会认不
    出区别（删掉一份 8000 字的文件、换成另一份恰好等长同内容的文件这种巧合
    虽罕见，但"文件集合变了、拼接内容的哈希没变"这类情况必须能被捕捉，工程
    上最简单可靠的办法就是把文件名一并纳入摘要）。每条记录前加长度前缀
    （8 字节大端），避免"文件名/内容边界"因拼接产生的歧义（如 "ab"+"c" 与
    "a"+"bc" 不应撞成同一个哈希）。"""
    path = Path(path)
    if not path.is_dir():
        raise FileNotFoundError(f"{path} 不是目录（或不存在）")
    h = hashlib.sha256()
    for p in sorted(path.glob("*.md")):
        name = p.name.encode("utf-8")
        data = p.read_bytes()
        h.update(len(name).to_bytes(8, "big"))
        h.update(name)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def lane_exclusions(lane_dir) -> list:
    """该车道 lane.json 里记的 freeze_exclude（车道相对路径，如
    `glossary/style_refine.md`）。文件缺失或键不存在时返回空列表。"""
    p = Path(lane_dir) / "lane.json"
    if not p.exists():
        return []
    try:
        return list(json.loads(p.read_text(encoding="utf-8")).get("freeze_exclude", []))
    except (json.JSONDecodeError, AttributeError):
        return []


def set_exclusions(lane, paths, lanes_root=None) -> list:
    """只改 lane.json 的 freeze_exclude 并清掉车道内已存在的被排除文件，
    **不重新冻结**（冻结快照与 manifest 哈希一概不动）。

    单独给一个入口，是为了让「某条车道不要这份文件」这个决定能在**重冻结之前**
    就落到盘上：`setup(force=True)` 未显式传 freeze_exclude 时会**继承** lane.json
    里已有的值，于是段边界重冻结不依赖操作者记得加参数。靠记忆的纪律会衰减。
    """
    lane_dir = Path(lanes_root or LANES_ROOT) / lane
    p = lane_dir / "lane.json"
    if not p.exists():
        raise SystemExit(f"{p} 不存在——该车道尚未 setup")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["freeze_exclude"] = sorted(set(paths))
    p.write_text(dumps(cfg), encoding="utf-8")
    removed = []
    for rel in cfg["freeze_exclude"]:
        f = lane_dir / rel
        if f.is_file():
            f.unlink()
            removed.append(rel)
    return removed


def setup(lane, model, effort, append_model_id, repo=None, lanes_root=None,
          force=False, freeze_exclude=None) -> Path:
    repo = Path(repo or REPO)
    lanes_root = Path(lanes_root or LANES_ROOT)
    lane_dir = lanes_root / lane
    # None ＝ 未指定 ⇒ 继承车道现有设置（重冻结的默认路径，见 set_exclusions 的
    # docstring）；显式传空列表 ＝ 清除排除项。二者必须可区分。
    if freeze_exclude is None:
        freeze_exclude = lane_exclusions(lane_dir)
    freeze_exclude = sorted(set(freeze_exclude))
    forward = lane_dir / "data" / "forward.jsonl"
    if forward.exists() and not force:
        raise SystemExit(
            f"{lane_dir} 已有译文线 {forward}——重跑 setup() 会用当前仓库状态"
            f"覆盖 skeleton/glossary 冻结快照，抹掉试点期间可能已发生的漂移"
            f"证据。若确认要重新冻结，显式传 --force/force=True。")
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
    for rel in freeze_exclude:
        f = lane_dir / rel
        if f.is_file():
            f.unlink()
        else:
            # 排除项打错字会静默生效（少排一个文件谁也看不出），故必须出声。
            print(f"⚠ freeze_exclude 项 {rel} 在 {lane} 的冻结拷贝里不存在——"
                  f"路径写错了？（排除仍记入 lane.json）", file=sys.stderr)
    (lane_dir / "work").mkdir(exist_ok=True)
    cfg = {"lane": lane, "lane_dir": str(lane_dir), "model": model,
           "effort": effort, "append_model_id": append_model_id}
    if freeze_exclude:
        cfg["freeze_exclude"] = freeze_exclude
    (lane_dir / "lane.json").write_text(dumps(cfg), encoding="utf-8")
    return lane_dir


def freeze_hashes(lane_dir, repo=None) -> dict:
    """冻结集的哈希：batches 取仓库侧（两条车道共享同一份批次规划），
    其余六项取车道内的拷贝（各车道各自冻结，理应彼此相同）。

    style/voices 是 build_context.py 整篇渲染进 context.md 第四节、译者直接
    照做的规则书（style.md 全文 + voices/ 全部角色口调表），且其哈希本就写进
    每批 manifest.json（build_context.py 的 "voices" 键）——冻结校验若不覆盖
    它们，规则书可以随意漂移而 --verify 永远报「无漂移」，等于闸门对着译者
    实际读的东西是瞎的。voices/ 是目录，用 _sha256_dir（而非 sha256_file）。"""
    repo, lane_dir = Path(repo or REPO), Path(lane_dir)
    return {
        "batches": sha256_file(repo / "data" / "batches.jsonl"),
        "cards_zh": sha256_file(lane_dir / "skeleton" / "cards.zh.yaml"),
        "anchors": sha256_file(lane_dir / "skeleton" / "anchors.yaml"),
        "active": sha256_file(lane_dir / "glossary" / "active.json"),
        "glossary_max": sha256_file(_glossary_max_path(lane_dir)),
        "style": sha256_file(lane_dir / "glossary" / "style.md"),
        "voices": _sha256_dir(lane_dir / "glossary" / "voices"),
    }


def _manifest_path(lanes_root) -> Path:
    return Path(lanes_root) / "pilot-manifest.json"


def record(lanes_root=None, repo=None, force=False) -> dict:
    """扫描 lanes_root 下全部车道，把冻结哈希合并进 pilot-manifest.json 并返回
    合并后的 lanes 字典。

    合并而非覆盖：manifest 里已记录过的车道，若当前实际哈希与记录值不同，
    默认拒绝执行（重跑 record() 不该静默重冻结、抹掉原始基准——事后就再也
    无法证明试点期间是否发生过漂移，这正是 verify() 存在的意义）。要接受
    新值需显式 force=True。新车道（manifest 里还没有的）可以直接加入，不
    需要 force——这是"先后 setup 两条车道"的正常流程。manifest 里除
    "lanes" 之外的其余顶层键（如人工写入的 collapse_thresholds）原样保留。
    """
    lanes_root = Path(lanes_root or LANES_ROOT)
    mp = _manifest_path(lanes_root)
    doc = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    existing = doc.get("lanes", {})
    fresh = {}
    for p in sorted(lanes_root.iterdir()):
        if not (p.is_dir() and (p / "lane.json").exists()):
            continue
        try:
            fresh[p.name] = freeze_hashes(p, repo)
        except FileNotFoundError as e:
            # 纯克隆场景（云端拿到的内容）：pilot/lanes/ 下只有各车道入库的
            # lane.json，data/ 符号链接与 skeleton/glossary 冻结拷贝要靠
            # setup() 在本地重建。两条车道互为鸡生蛋——先建一条时另一条尚未
            # 重建，freeze_hashes 会在这里触底。record() 是"记录本次搭建结果"
            # 的入口，不是漂移安全网，但同样不该让一条车道的缺失拖垮整条命令：
            # 跳过该车道、continue 处理其余车道。注意 merged 起点是
            # dict(existing)（见下），跳过只是不更新——manifest 里该车道原有
            # 记录原样保留，不会被这次跳过抹掉。
            print(f"跳过 {p.name}：车道尚未搭建或冻结文件缺失（{e}）",
                  file=sys.stderr)
            continue
    merged = dict(existing)
    for lane, h in fresh.items():
        if lane in existing and existing[lane] != h and not force:
            changed = sorted(k for k in h if existing[lane].get(k) != h.get(k))
            raise SystemExit(
                f"车道 {lane} 已记录过冻结哈希，且当前实际值与记录不同"
                f"（{changed}）——重跑 record() 会覆盖原始基准，事后无法证明"
                f"是否漂移过。若确认要重新冻结，显式传 --force/force=True。")
        merged[lane] = h
    doc["lanes"] = merged
    mp.write_text(dumps(doc), encoding="utf-8")
    return merged


# 跨车道一致性检查覆盖的键：cards_zh/anchors/active/glossary_max/style/voices
# 是"应当彼此相同"的冻结基准（batches 不列入——batches.jsonl 本就是仓库共享
# 的单一文件，不存在"两条车道各自一份"的概念，見 freeze_hashes 的 docstring）。
# style/voices 与前四项同理：都是各车道各自拷贝冻结、理应彼此相同的规则书
# （style.md 风格与润色尺度、voices/ 角色口调表），漏掉就是给术语/风格泄漏
# 开后门。
CROSS_LANE_KEYS = ("cards_zh", "anchors", "active", "glossary_max",
                   "style", "voices")


def verify(lanes_root=None, repo=None) -> list:
    """比对已记录的冻结哈希与当前实际值，返回漂移描述（空列表＝无漂移）。

    三层检查：①每条车道自比——当前实际哈希 vs 该车道 record() 时记下的值；
    ②跨车道互比——若两条车道分别在仓库术语变更前后 setup，各自的自比都会
    通过（各记各的），但两条车道的术语基准已经不同，正是 spec §0「术语泄漏」
    要防的事，必须由①之外的检查单独抓住；③仓库侧内容自洽——glossary/voices/
    的示范译例与 skeleton/anchors.yaml 的定稿是否互相打架（tools/
    check_voices_anchors.py），这层与哈希漂移无关（两份文件各自都可能"没有
    漂移"却仍然彼此矛盾），只跑一次、查仓库侧而非各车道的冻结拷贝——两份都是
    仓库同一时刻的内容，车道只是原样拷贝，自洽与否是仓库侧的属性。这一层与
    manifest 是否存在无关，故放在下面的 mp.exists() 判断之前，任何时候
    --verify 都会跑到。
    """
    lanes_root = Path(lanes_root or LANES_ROOT)
    repo_path = Path(repo or REPO)
    drift = []
    voices_dir = repo_path / "glossary" / "voices"
    anchors_path = repo_path / "skeleton" / "anchors.yaml"
    if voices_dir.is_dir() and anchors_path.exists():
        mismatches, _n = _check_voices_anchors(voices_dir, anchors_path)
        drift.extend(mismatches)
    mp = _manifest_path(lanes_root)
    if not mp.exists():
        drift.append("pilot-manifest.json 不存在——尚未记录冻结哈希")
        return drift
    recorded = json.loads(mp.read_text(encoding="utf-8"))["lanes"]
    healthy = {}  # lane -> got，只收完整读出哈希的车道，供下面跨车道比对用
    for lane, want in recorded.items():
        try:
            got = freeze_hashes(lanes_root / lane, repo)
        except FileNotFoundError as e:
            # 车道整个被删、或车道内某个冻结文件被误删/改名——freeze_hashes 触底时
            # 抛的就是 FileNotFoundError（sha256_file 读不到文件，或
            # _glossary_max_path 找不到 glossary.v*.yaml）。verify 是漂移安全网，
            # 一条车道损坏不该让整次校验栈回溯，记一条可诊断描述、继续查其余车道。
            drift.append(f"{lane}: 冻结文件缺失或车道损坏（{e}）")
            continue
        healthy[lane] = got
        # want 曾经必定与 got 同键集（freeze_hashes 正常返回时二者键集相等）；
        # 但 freeze_hashes 后续加过新键（如本次的 style/voices）后，存量 manifest
        # 里记录的 want 会是当前 got 键集的真子集——这不是"没有漂移"，而是
        # "这些新键从来没被这条车道校验过"，必须显式报出并给可操作的修复方式，
        # 不能因为 want.items() 遍历不到就悄悄放过（那样新增的冻结项对所有
        # 存量车道形同虚设，等于把同一个"闸门永远报绿"的洞换了个地方）。
        missing_keys = sorted(set(got) - set(want))
        if missing_keys:
            drift.append(
                f"{lane}: manifest 缺少冻结键 {missing_keys}——这些项从未被"
                f"校验过（不代表未漂移，只是从来没查）。请对该车道重新冻结："
                f"跑 `python tools/lane_setup.py --lane {lane} --model <model> "
                f"--effort <effort> --append-model-id <id> --force`（或直接调用 "
                f"record(force=True)）补齐后再校验。")
        for k, v in want.items():
            if got[k] != v:
                drift.append(f"{lane}: {k} 漂移（记录 {v[:12]}… 实际 {got[k][:12]}…）")
    lanes_sorted = sorted(healthy)
    if len(lanes_sorted) >= 2:
        base_lane = lanes_sorted[0]
        base = healthy[base_lane]
        for lane in lanes_sorted[1:]:
            got = healthy[lane]
            for k in CROSS_LANE_KEYS:
                if got[k] != base[k]:
                    drift.append(
                        f"跨车道不一致：{lane}.{k} 与 {base_lane}.{k} 不同"
                        f"（{base_lane}={base[k][:12]}… {lane}={got[k][:12]}…）")
    return drift


def stale_vs_repo(lanes_root=None, repo=None) -> list:
    """车道冻结拷贝与仓库当前内容的差异清单（每条一个相对路径）。

    **这不是漂移**：段中途仓库继续演进而车道保持冻结，本就该不同，故不进
    `verify()` 的返回值、不影响退出码。但它必须被**播报**——译者读到的是车道
    拷贝，仓库侧改了 `style.md`／`voices/` 而没重冻结时，新口径对生产端等于
    不存在；而 `--verify` 比的是「车道 vs manifest」，**结构上看不见这一面**，
    此时它照报「无漂移」。runbook §5 陷阱①要求人工补跑 `diff -rq` 来堵这个洞，
    靠的是记忆——记忆会衰减，闸不会。2026-08-04 实测：仓库侧 `style.md` 已比
    车道多 16 行 ruby 口径，两轮 `--verify` 全绿。
    """
    lanes_root = Path(lanes_root or LANES_ROOT)
    repo_path = Path(repo or REPO)
    out = []
    for lane_dir in sorted(p for p in lanes_root.glob("*") if p.is_dir()):
        excl = set(lane_exclusions(lane_dir))
        for d in COPIED_DIRS:
            lane_sub, repo_sub = lane_dir / d, repo_path / d
            if not lane_sub.is_dir():
                continue
            for f in sorted(p for p in lane_sub.rglob("*") if p.is_file()):
                rel = f.relative_to(lane_dir)
                mirror = repo_path / rel
                if not mirror.exists():
                    out.append(f"{lane_dir.name}: {rel} 仓库侧已不存在（车道仍冻结着）")
                elif sha256_file(f) != sha256_file(mirror):
                    out.append(f"{lane_dir.name}: {rel} 仓库侧较新，车道拷贝落后")
            for f in sorted(p for p in repo_sub.rglob("*") if p.is_file()):
                rel = f.relative_to(repo_path)
                if str(rel) in excl:
                    continue  # 有意排除，不算落后；由 frozen_exclusions() 单独播报
                if not (lane_dir / rel).exists():
                    out.append(f"{lane_dir.name}: {rel} 仓库侧新增，未进车道")
    return out


def frozen_exclusions(lanes_root=None) -> list:
    """各车道 lane.json 里有意排除的文件清单，供 --verify 单独播报。

    排除是**静默丢文件**的机制：排错了、或某条车道的排除早该解除了，从产物上
    完全看不出来。所以它不能只是从 `stale_vs_repo` 里被 skip 掉了事——**跳过等于
    藏起来**，而藏起来的机制正是本项目反复吃亏的形态。有意排除照样每次出声，
    只是标明它是有意的，并指出决定记在哪儿（lane.json）。
    """
    lanes_root = Path(lanes_root or LANES_ROOT)
    out = []
    for lane_dir in sorted(p for p in lanes_root.glob("*") if p.is_dir()):
        for rel in lane_exclusions(lane_dir):
            out.append(f"{lane_dir.name}: {rel} 按 lane.json:freeze_exclude 有意排除，"
                       f"该车道看不到它")
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--append-model-id")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="车道已有译文进度（data/forward.jsonl 存在）时仍强制"
                         "重新冻结 skeleton/glossary 快照并覆盖已记录的基准哈希")
    ap.add_argument("--freeze-exclude",
                    help="逗号分隔的车道相对路径，建/重建时不拷进该车道（如 "
                         "glossary/style_refine.md）。**不传＝继承车道现有设置**，"
                         "传空串＝清除。")
    ap.add_argument("--set-exclude",
                    help="只改 lane.json 的 freeze_exclude（并删掉车道内已存在的该文件），"
                         "不重新冻结。需配 --lane。")
    a = ap.parse_args(argv)
    if a.set_exclude is not None:
        if not a.lane:
            raise SystemExit("--set-exclude 需同时给 --lane")
        paths = [s for s in a.set_exclude.split(",") if s]
        removed = set_exclusions(a.lane, paths, LANES_ROOT)
        print(f"{a.lane}: freeze_exclude = {paths or '（已清空）'}"
              + (f"；已从车道删除 {removed}" if removed else ""))
        return 0
    if a.verify:
        drift = verify(LANES_ROOT, REPO)
        stale = stale_vs_repo(LANES_ROOT, REPO)
        excl = frozen_exclusions(LANES_ROOT)
        rc = 0
        if drift:
            for d in drift:
                print(d)
            rc = 1
        else:
            print("冻结校验：无漂移")
        # 播报而不判错：见 stale_vs_repo 的 docstring。绿字后面跟这一段，正是为了
        # 让「无漂移」不再被读成「车道内容与仓库一致」。
        if stale:
            print(f"⚠ 车道冻结拷贝落后于仓库侧 {len(stale)} 处"
                  f"（**不是漂移**，段中途正常；但译者读的是车道拷贝，"
                  f"这些改动对生产端尚未生效，段边界须 --force 重冻结）：")
            for s in stale:
                print(f"  {s}")
        if excl:
            print(f"ℹ 有意排除 {len(excl)} 项（不是缺陷，但每次出声——"
                  f"排除是静默丢文件的机制，藏起来才危险）：")
            for e in excl:
                print(f"  {e}")
        return rc
    if not all([a.lane, a.model, a.effort, a.append_model_id]):
        raise SystemExit("建车道需同时给 --lane/--model/--effort/--append-model-id")
    lane_dir = setup(a.lane, a.model, a.effort, a.append_model_id, REPO, LANES_ROOT,
                     force=a.force,
                     freeze_exclude=(None if a.freeze_exclude is None
                                     else [s for s in a.freeze_exclude.split(",") if s]))
    record(LANES_ROOT, REPO, force=a.force)
    print(f"{lane_dir}: 车道就绪，冻结哈希已记入 {_manifest_path(LANES_ROOT)}")
    kept = lane_exclusions(lane_dir)
    if kept:
        print(f"  freeze_exclude（{'继承' if a.freeze_exclude is None else '本次指定'}）：{kept}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
