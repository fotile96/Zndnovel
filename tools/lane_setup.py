"""P2 试点车道搭建与冻结校验。

车道＝一份独立的译文线 + 一份冻结的骨架/术语快照：只读数据用符号链接（同源、
省空间），skeleton/ 与 glossary/ 用拷贝（拷贝即冻结，杜绝试点中途仓库侧升版
泄漏进任一车道）。spec：docs/superpowers/specs/2026-07-31-p2-pilot-design.md §3。
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO, WORK, dumps, sha256_file

LANES_ROOT = WORK / "lanes"

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


def setup(lane, model, effort, append_model_id, repo=None, lanes_root=None) -> Path:
    repo = Path(repo or REPO)
    lanes_root = Path(lanes_root or LANES_ROOT)
    lane_dir = lanes_root / lane
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


def record(lanes_root=None, repo=None) -> dict:
    """扫描 lanes_root 下全部车道，写 pilot-manifest.json 并返回其内容。"""
    lanes_root = Path(lanes_root or LANES_ROOT)
    lanes = {p.name: freeze_hashes(p, repo)
             for p in sorted(lanes_root.iterdir())
             if p.is_dir() and (p / "lane.json").exists()}
    _manifest_path(lanes_root).write_text(dumps({"lanes": lanes}), encoding="utf-8")
    return lanes


def verify(lanes_root=None, repo=None) -> list:
    """比对已记录的冻结哈希与当前实际值，返回漂移描述（空列表＝无漂移）。"""
    lanes_root = Path(lanes_root or LANES_ROOT)
    mp = _manifest_path(lanes_root)
    if not mp.exists():
        return ["pilot-manifest.json 不存在——尚未记录冻结哈希"]
    recorded = json.loads(mp.read_text(encoding="utf-8"))["lanes"]
    drift = []
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
        for k, v in want.items():
            # got 此刻要么完整覆盖 want 的键集（freeze_hashes 正常返回），要么已在
            # 上面 except 分支被拦下——不存在"部分键缺失"的中间态，故直接 got[k]。
            if got[k] != v:
                drift.append(f"{lane}: {k} 漂移（记录 {v[:12]}… 实际 {got[k][:12]}…）")
    return drift


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--append-model-id")
    ap.add_argument("--verify", action="store_true")
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
    lane_dir = setup(a.lane, a.model, a.effort, a.append_model_id, REPO, LANES_ROOT)
    record(LANES_ROOT, REPO)
    print(f"{lane_dir}: 车道就绪，冻结哈希已记入 {_manifest_path(LANES_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
