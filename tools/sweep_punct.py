"""标点清扫：删掉句末 `……` 后面那个多余的句号（polish.md §7(a)）。

## 为什么单独做成工具而不是靠润色通道顺手改

`……。` 是全库唯一一处**真正机械**的汉语标点问题：汉语的省略号自己收尾，后面不
再加句号（GB/T 15834），日语可以写 `……。`。实测全库 745 行命中，其中 **742 行**
同一行的 jp 也正好含 `……。`——99.6% 是原样照搬，不是任何人判断的结果。

指望润色通道逐段改它是浪费：它会占裁决队列的名额、占通道的注意力，而这件事没有
任何判断成分。故单独扫一次。

## ⚠ 三类看着像、其实不能一起扫的（起草本工具时全部踩过）

1. **`——。` / `――。` 不扫**（全库 105 行）。它们绝大多数是**长音符 `ー` 的译法**，
   后面那个句号是正常的句末句号：

       #6182  jp 【教師】「へえー。ズバッといい所に行ってるねえ」
              zh 【教师】「哦——。一下子就进了个好地方嘛」

   删了反而错。本工具的正则只认 `……`，不认破折号。

2. **行中的 `……。` 不扫**（全库 206 行）。一拍沉默之后同一行还有话时，那个句号在
   分隔「沉默」与「开口」两拍：`【直哉】「……。对不起」` 删成 `「……对不起」`，
   两拍就并成了一个迟疑的起头。**这是判断题，留给 polish.md §7(a) 逐行判。**
   故本工具只认 `……。` 后面紧跟**字符串结尾**或 `_n`/`_r` 的位置。

3. **锚点定译（`skeleton/anchors.yaml`）与已有 patch 的行不扫**。前者是「逐字沿用」
   的定译，改它要走新 glossary 版本 + 召回令；后者是人裁/润色已经拍过板的行，
   在上面再叠一层等于绕过裁决。两类都**列出来但不动**——`--list-skipped` 可看全，
   跳过的东西不许悄悄消失。

## 写入路径

复用 `tools/add_patch.add(reason="review")`，**不发明第三条写生产数据的路径**
（既有两条：`polish_commit --apply` 与 `add_patch`）。`--apply` 才真写，缺省 dry-run。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.add_patch import add
from tools.build_context import glossary_version
from tools.pipelib import REPO, read_jsonl

# `……。` 且其后紧跟字符串结尾或换行控制码——只有这个位置是机械安全的。
TAIL_RE = re.compile(r"……。(?=$|_n|_r)")


def sweep_targets(data_dir, repo=REPO, seg_labels=None):
    """返回 (targets, skipped)。

    targets: [{"id", "old", "new", "batch"}]  可机械改的行
    skipped: {"anchor": [...], "patched": [...]}  命中但按规则不动的行
    """
    data_dir, repo = Path(data_dir), Path(repo)
    cur, batch = {}, {}
    for r in read_jsonl(data_dir / "forward.jsonl"):
        cur[r["id"]] = r.get("zh")
        batch[r["id"]] = r.get("batch")
    patched = set()
    pf = data_dir / "patches.jsonl"
    if pf.exists():
        for r in read_jsonl(pf):
            cur[r["id"]] = r.get("zh")
            patched.add(r["id"])

    anchors = set()
    af = repo / "skeleton" / "anchors.yaml"
    if af.exists():
        import yaml
        for ch in yaml.safe_load(af.read_text(encoding="utf-8")) or []:
            for it in ch.get("items", []):
                anchors.add(it["id"])

    keep_batches = None
    if seg_labels:
        import yaml
        segs = yaml.safe_load((repo / "config" / "segments.yaml").read_text(encoding="utf-8"))
        keep_batches = [tuple(s["batches"]) for s in segs if s["label"] in seg_labels]
        missing = set(seg_labels) - {s["label"] for s in segs}
        if missing:
            raise SystemExit(f"segments.yaml 里没有这些 label：{sorted(missing)}")

    targets, skipped = [], {"anchor": [], "patched": []}
    for i, zh in sorted(cur.items()):
        if not zh or not TAIL_RE.search(zh):
            continue
        if keep_batches is not None:
            b = batch.get(i)
            if b is None or not any(a <= b <= z for a, z in keep_batches):
                continue
        if i in anchors:
            skipped["anchor"].append(i); continue
        if i in patched:
            skipped["patched"].append(i); continue
        targets.append({"id": i, "old": zh, "new": TAIL_RE.sub("……", zh),
                        "batch": batch.get(i)})
    return targets, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description="删掉句末 `……` 后多余的句号（polish.md §7(a)）")
    ap.add_argument("--data-dir", required=True, help="车道 data/ 目录（不可省，见 add_patch 的护栏）")
    ap.add_argument("--seg", action="append", default=None,
                    help="只扫这些段的 label（可重复）；不给＝全库")
    ap.add_argument("--apply", action="store_true", help="真写入；缺省只报不改")
    ap.add_argument("--list-skipped", action="store_true", help="逐条列出跳过的锚点/已 patch 行")
    ap.add_argument("--out", help="把逐条改动写成 JSONL 供人工过目")
    a = ap.parse_args(argv)

    targets, skipped = sweep_targets(a.data_dir, seg_labels=a.seg)
    gv = glossary_version(REPO)

    print(f"sweep_punct: 命中可改 {len(targets)} 行；"
          f"跳过锚点定译 {len(skipped['anchor'])} 行、已有 patch {len(skipped['patched'])} 行")
    if skipped["anchor"]:
        print(f"  ⚠ 锚点（改它要走新 glossary 版本＋召回令）：{skipped['anchor']}")
    if skipped["patched"] and a.list_skipped:
        print(f"  ⚠ 已有 patch（人裁/润色拍过板）：{skipped['patched']}")
    elif skipped["patched"]:
        print(f"  ⚠ 已有 patch {len(skipped['patched'])} 行——加 --list-skipped 看 id")

    if a.out:
        Path(a.out).write_text(
            "\n".join(json.dumps(t, ensure_ascii=False) for t in targets) + "\n",
            encoding="utf-8")
        print(f"  逐条改动已写入 {a.out}")

    if not a.apply:
        for t in targets[:5]:
            print(f"  [dry-run] {t['id']}: {t['old']}  →  {t['new']}")
        print(f"[dry-run] 未写入任何文件——加 --apply 才真写（glossary_v={gv}）")
        return 0

    for t in targets:
        add(t["id"], t["new"], "review", gv, data=a.data_dir, announce=False)
    print(f"[apply] 已写入 {len(targets)} 条 patch → {a.data_dir}/patches.jsonl（glossary_v={gv}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
