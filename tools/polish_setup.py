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
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_context import glossary_version
from tools.pipelib import REPO, dumps, read_jsonl, sha256_file, write_jsonl
from tools.resolve import resolve_map


def _dir_for(label, repo) -> Path:
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _seg_entry(repo, label) -> dict:
    segs = yaml.safe_load((Path(repo) / "config" / "segments.yaml").read_text(encoding="utf-8"))
    for s in segs:
        if s["label"] == label:
            return s
    raise KeyError(f"config/segments.yaml 里没有 label={label!r} 的段")


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


def _locked_payload(locked_ids, anchor_ids, patched_ids) -> dict:
    """来源标注：两者都命中时按用户裁定固定选 anchor（稳定可复现，不看运行
    时 set 遍历顺序）。"""
    why = {}
    for i in sorted(locked_ids):
        why[str(i)] = "anchor" if i in anchor_ids else "patched"
    return {"ids": sorted(locked_ids), "why": why}


def _copy_glossary(repo, fz: Path) -> None:
    """glossary/ 术语层拷贝：active.json + voices/ + style.md + polish.md，
    外加 skeleton/anchors.yaml（伏笔锚点定译——正文润色对照的一部分，放进
    同一个 glossary/ 子目录，与执行通道读取路径一致）。"""
    repo = Path(repo)
    g = fz / "glossary"
    g.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "glossary" / "active.json", g / "active.json")
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


def setup(label, opus_data, repo=None) -> Path:
    repo = Path(repo) if repo is not None else REPO
    opus_data = Path(opus_data)

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
    patched_ids = {r["id"] for r in pat}
    locked_ids = set(ids) & (anchor_ids | patched_ids)
    (fz / "locked.json").write_text(
        dumps(_locked_payload(locked_ids, anchor_ids, patched_ids)), encoding="utf-8")

    _copy_glossary(repo, fz)
    notes_missing = _copy_notes(opus_data / "notes", fz / "notes", seg["chapters"])

    (fz / "rulings.md").write_text(f"# {label} 润色裁决与前序纪要\n（追加式）\n",
                                    encoding="utf-8")

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
        d = setup(args.seg, args.opus_data)
        print(f"冻结完成：{d}")
        return 0

    ap.error("需要 --seg 与 --opus-data 一起用，或单独 --verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
