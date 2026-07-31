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
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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


def setup(lane, model, effort, append_model_id, repo=None, lanes_root=None,
          force=False) -> Path:
    repo = Path(repo or REPO)
    lanes_root = Path(lanes_root or LANES_ROOT)
    lane_dir = lanes_root / lane
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
    (lane_dir / "work").mkdir(exist_ok=True)
    (lane_dir / "lane.json").write_text(dumps({
        "lane": lane, "lane_dir": str(lane_dir), "model": model,
        "effort": effort, "append_model_id": append_model_id}), encoding="utf-8")
    return lane_dir


def freeze_hashes(lane_dir, repo=None) -> dict:
    """冻结集的哈希：batches 取仓库侧（两条车道共享同一份批次规划），
    其余四项取车道内的拷贝（各车道各自冻结，理应彼此相同）。"""
    repo, lane_dir = Path(repo or REPO), Path(lane_dir)
    return {
        "batches": sha256_file(repo / "data" / "batches.jsonl"),
        "cards_zh": sha256_file(lane_dir / "skeleton" / "cards.zh.yaml"),
        "anchors": sha256_file(lane_dir / "skeleton" / "anchors.yaml"),
        "active": sha256_file(lane_dir / "glossary" / "active.json"),
        "glossary_max": sha256_file(_glossary_max_path(lane_dir)),
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
    fresh = {p.name: freeze_hashes(p, repo)
             for p in sorted(lanes_root.iterdir())
             if p.is_dir() and (p / "lane.json").exists()}
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


# 跨车道一致性检查覆盖的键：cards_zh/anchors/active/glossary_max 是"应当彼此
# 相同"的冻结基准（batches 不列入——batches.jsonl 本就是仓库共享的单一文件，
# 不存在"两条车道各自一份"的概念，見 freeze_hashes 的 docstring）。
CROSS_LANE_KEYS = ("cards_zh", "anchors", "active", "glossary_max")


def verify(lanes_root=None, repo=None) -> list:
    """比对已记录的冻结哈希与当前实际值，返回漂移描述（空列表＝无漂移）。

    两层检查：①每条车道自比——当前实际哈希 vs 该车道 record() 时记下的值；
    ②跨车道互比——若两条车道分别在仓库术语变更前后 setup，各自的自比都会
    通过（各记各的），但两条车道的术语基准已经不同，正是 spec §0「术语泄漏」
    要防的事，必须由①之外的检查单独抓住。
    """
    lanes_root = Path(lanes_root or LANES_ROOT)
    mp = _manifest_path(lanes_root)
    if not mp.exists():
        return ["pilot-manifest.json 不存在——尚未记录冻结哈希"]
    recorded = json.loads(mp.read_text(encoding="utf-8"))["lanes"]
    drift = []
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
        for k, v in want.items():
            # got 此刻要么完整覆盖 want 的键集（freeze_hashes 正常返回），要么已在
            # 上面 except 分支被拦下——不存在"部分键缺失"的中间态，故直接 got[k]。
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
    a = ap.parse_args(argv)
    if a.verify:
        drift = verify(LANES_ROOT, REPO)
        if drift:
            for d in drift:
                print(d)
            return 1
        print("冻结校验：无漂移")
        return 0
    if not all([a.lane, a.model, a.effort, a.append_model_id]):
        raise SystemExit("建车道需同时给 --lane/--model/--effort/--append-model-id")
    lane_dir = setup(a.lane, a.model, a.effort, a.append_model_id, REPO, LANES_ROOT,
                     force=a.force)
    record(LANES_ROOT, REPO, force=a.force)
    print(f"{lane_dir}: 车道就绪，冻结哈希已记入 {_manifest_path(LANES_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
