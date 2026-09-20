"""通读 UI 人工修改的**唯一清关口**：把 `pilot/read-edits/<lane>.draft.jsonl`
落成生产车道的 `patches.jsonl`（`reason=review`）。

与 `tools/polish_commit.py` 同一套纪律，逐条对应：

1. **车道模式拒绝闸原样复用**：CLI 一律先调 `add_patch.resolve_data_dir()`，
   车道模式下没给 `--data-dir` 也没设 `ZND_DATA` 就 `SystemExit(2)`，在任何文件
   被创建之前。见 `add_patch.py` 记的 2026-08-02 事故：四条回改零报错、退出码 0，
   却全落进了主仓 `data/`，一条都没生效。
2. **dry-run 是默认**，`--apply` 才真写。
3. **写前逐 id 播报既有 patch**（`add_patch.add(announce=True)` 内部完成）。
4. **幂等键 `(id, ts)`**：`committed.json` 记已处理的草稿行——已落地的，以及**与车道
   逐字相同、无需落地的**（编辑后又撤回的行）；重复 `--apply` 是 no-op。
   同 id 改判过多次（草稿 append-only）只落**最后一条**——中间态没有落地的意义，
   与 `polish_commit` 的「同 id 取最后一条」一致。
5. **`--prune` 归档**：已关账 id 的草稿行搬进 `<lane>.archive.jsonl`（批注只在草稿里，
   不能删），草稿只留待办；通读 UI 的"未清关"视图本身也不再显示已关账的行
   （`read_server.pending_edits`），两道保险。

## 两道本工具特有的闸

**① 漂移（`stale`）默认拒写。** 草稿行记着 `base_zh`＝写下这条修改时车道的样子。
清关时若车道现值已经不是那个样子，说明这一行在你改完之后又被别处动过（另一段的
润色清关、某次召回）——直接盖上去会静默抹掉那次改动。默认跳过并列出来，
`--allow-stale` 才放行。

**② 机械体检有警告的行默认拒写。** 编辑框是原样保存的（读的人可能正想写点别的），
所以体检不在写入草稿时阻断；但清关是进生产，这里该拦。`--allow-warn` 放行。
警告口径见 `read_server.check_edit()`——每一条都对应一次真实翻过的车。

两个开关都**不静默**：被拦下的行逐条打印，不会出现"清关完了但少了几条而没人知道"。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import add_patch
from tools.build_context import glossary_version
from tools.pipelib import REPO, read_jsonl
from tools.read_server import (DEFAULT_LANE, DRAFT_SUFFIX, check_edit, committed_path,
                               edits_path, load_committed, load_edits)
from tools.resolve import resolve_map


def _committed_path(p: Path) -> Path:
    return committed_path(p)


def _load_committed(p: Path) -> set:
    return load_committed(p.with_name(p.name.replace(".committed.json", DRAFT_SUFFIX)))


def archive_path(draft: Path) -> Path:
    return draft.with_name(draft.name.replace(DRAFT_SUFFIX, ".archive.jsonl"))


def prune(repo=None, lane=DEFAULT_LANE, dry_run=True) -> dict:
    """把**已关账的 id** 的全部草稿行搬进 `<lane>.archive.jsonl`，草稿只留还在待办的行。

    「已关账」＝该 id 的最后一条 `(id, ts)` 在 `committed.json` 里（已落地，或撤回后与
    车道相同而记为已处理）。它名下更早的中间态行一并归档——草稿是 append-only 的编辑
    过程记录，批注（`note`）只存在这里、不进 patches，所以是**搬走**而不是删掉。
    还开着的 id（最后一条未清关）整个不动，哪怕它更早的某一行已清关过。
    归档后 `committed.json` 只留仍在草稿里的行的记录，账与草稿始终一一对应。
    """
    repo = Path(repo) if repo is not None else REPO
    draft = edits_path(repo, lane)
    rows = list(read_jsonl(draft)) if draft.exists() else []
    done = load_committed(draft)
    last_ts = {}
    for r in rows:
        last_ts[r["id"]] = r.get("ts")
    closed = {i for i, ts in last_ts.items() if (i, ts) in done}
    keep = [r for r in rows if r["id"] not in closed]
    gone = [r for r in rows if r["id"] in closed]
    tag = "[dry-run]" if dry_run else "[apply]"
    for r in gone:
        print(f"{tag} 归档 id={r['id']} ts={r.get('ts')} {r.get('zh', '')[:40]}", file=sys.stderr)
    print(f"{tag} 草稿 {len(rows)} 行：归档 {len(gone)}（{len(closed)} 个已关账 id），留 {len(keep)}"
          f"（{len(last_ts) - len(closed)} 个待办 id）", file=sys.stderr)
    if not dry_run and gone:
        arc = archive_path(draft)
        with open(arc, "a", encoding="utf-8") as f:
            for r in gone:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        draft.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        kept_keys = {(r["id"], r.get("ts")) for r in keep}
        _save_committed(committed_path(draft), {k for k in done if k in kept_keys})
        print(f"{tag} 已写 {arc}", file=sys.stderr)
    return {"archived": len(gone), "kept": len(keep)}


def _save_committed(p: Path, done: set) -> None:
    rows = sorted(({"id": i, "ts": t} for i, t in done),
                  key=lambda r: (r["id"], r["ts"]))
    p.write_text(json.dumps({"committed": rows}, ensure_ascii=False, indent=1),
                 encoding="utf-8")


def commit(data_dir, repo=None, lane=DEFAULT_LANE, dry_run=True,
           allow_stale=False, allow_warn=False, skip=()) -> list:
    """`skip`：这一轮**不清关**的 id 集合。被跳过的行原样留在草稿里、不进
    `committed.json`，下一轮不带 `--skip` 照常落地——用于「这几条要先和人商量」
    而其余几十条不必陪着等的场合。跳过的行逐条打印，不静默。"""
    repo = Path(repo) if repo is not None else REPO
    skip = set(skip)
    data_dir = Path(data_dir)
    draft = edits_path(repo, lane)
    edits = load_edits(draft)
    if not edits:
        print(f"read_commit: {draft} 里没有待清关的修改")
        return []

    cur = resolve_map(read_jsonl(data_dir / "forward.jsonl"),
                      read_jsonl(data_dir / "patches.jsonl"))
    ledger = {r["id"]: r for r in read_jsonl(repo / "data" / "ledger.jsonl")}
    done_path = _committed_path(draft)
    done = _load_committed(done_path)
    gv = glossary_version(repo)
    tag = "[dry-run]" if dry_run else "[apply]"

    out = []
    for cid in sorted(edits):
        e = edits[cid]
        ts = e.get("ts")
        if (cid, ts) in done:
            continue
        if cid in skip:
            print(f"{tag} - id {cid} 按 --skip 跳过（仍留在草稿里，下一轮再清）", file=sys.stderr)
            continue
        zh, base = e.get("zh", ""), e.get("base_zh", "")
        now = cur.get(cid, "")
        if zh == now:
            # 与车道逐字相同＝没有东西要落地（多半是编辑后又撤回）。记进 committed.json
            # 视为已处理：否则它每轮都报一遍空 diff，而且日后车道被召回改成别的值时，
            # 这条「撤回」会突然变成一条要把新值改回旧值的漂移补丁——与写它的人的本意相反。
            print(f"{tag} = id {cid} 与车道现值逐字相同——无需落地，记为已处理", file=sys.stderr)
            if not dry_run:
                done.add((cid, ts))
                _save_committed(done_path, done)
            continue
        if base != now and not allow_stale:
            print(f"{tag} ✗ 拒绝写入（漂移）：id {cid} 在你改完之后又被别处动过\n"
                  f"{tag}   你改时是：{base[:60]}\n"
                  f"{tag}   车道现在：{now[:60]}\n"
                  f"{tag}   ——直接盖上去会静默抹掉那次改动。确认要盖请加 --allow-stale。",
                  file=sys.stderr)
            continue
        warns = check_edit(ledger.get(cid, {}).get("jp", ""), now, zh)
        if warns and not allow_warn:
            print(f"{tag} ✗ 拒绝写入（机械体检未过）：id {cid}", file=sys.stderr)
            for w in warns:
                print(f"{tag}   · {w}", file=sys.stderr)
            print(f"{tag}   ——确认无误请加 --allow-warn。", file=sys.stderr)
            continue

        print(f"{tag} id={cid} glossary_v={gv} ts={ts}", file=sys.stderr)
        print(f"{tag}   旧：{now}", file=sys.stderr)
        print(f"{tag}   新：{zh}", file=sys.stderr)
        if e.get("note"):
            print(f"{tag}   批注：{e['note']}", file=sys.stderr)
        row = {"id": cid, "zh": zh, "reason": "review", "glossary_v": gv, "ts": ts}
        if dry_run:
            prior = add_patch.existing_patches(cid, data_dir)
            if prior:
                print(f"{tag}   ⚠ 该 id 已有 {len(prior)} 条 patch，本次将追加第 {len(prior)+1} 条",
                      file=sys.stderr)
        else:
            add_patch.add(cid, zh, "review", gv, ts=ts, data=data_dir, announce=True)
            done.add((cid, ts))
            _save_committed(done_path, done)
        out.append(row)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="通读 UI 人工修改的唯一清关口：草稿 → 生产 patches.jsonl（dry-run 默认）",
        epilog="⚠ 车道模式下必须显式给 --data-dir 或设 ZND_DATA，否则拒绝执行"
               "——见 tools/add_patch.resolve_data_dir。")
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="生产车道 data 目录（如 pilot/lanes/opus/data）")
    ap.add_argument("--lane", default=DEFAULT_LANE, help=f"车道目录，默认 {DEFAULT_LANE}")
    ap.add_argument("--apply", action="store_true", help="真正写入；省略则只预览")
    ap.add_argument("--allow-stale", action="store_true",
                    help="放行「改完之后车道又被别处动过」的行（默认拒写）")
    ap.add_argument("--allow-warn", action="store_true",
                    help="放行机械体检有警告的行（默认拒写）")
    ap.add_argument("--repo", default=None, help="仓库根（测试传 tmp_path）")
    ap.add_argument("--skip", default="",
                    help="这一轮不清关的 id，逗号分隔（留在草稿里，下一轮再清）")
    ap.add_argument("--prune", action="store_true",
                    help="不清关，只把已关账 id 的草稿行搬进 <lane>.archive.jsonl（配 --apply 真写）")
    args = ap.parse_args(argv)

    if args.prune:
        res = prune(repo=args.repo, lane=args.lane, dry_run=not args.apply)
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"read_commit[{mode}] prune: 归档 {res['archived']} 行，草稿留 {res['kept']} 行")
        return 0

    skip = {int(x) for x in args.skip.split(",") if x.strip()}
    data_dir = add_patch.resolve_data_dir(args.data_dir, repo=args.repo)
    rows = commit(data_dir, repo=args.repo, lane=args.lane, dry_run=not args.apply,
                  allow_stale=args.allow_stale, allow_warn=args.allow_warn, skip=skip)
    mode = "APPLY" if args.apply else "DRY-RUN"
    tail = f"已写入 {data_dir}" if args.apply else "未写入任何文件——加 --apply 才真写"
    print(f"read_commit[{mode}]: 共 {len(rows)} 条 patch（{tail}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
