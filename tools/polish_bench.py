"""通道评测：把若干条候选输出与某 SEG 的**最终定稿**对表，算精确率/召回。

## 为什么要有这个工具

2026-08-12/13 连续评测了 6 个新模型（antigravity 的 gemini、packy 的 grok-4.6、
opencode-go 的 grok-4.5 / kimi-k3 / kimi-k2.6、deepseek 的 v4-pro）。每加一个都要
临时写一段脚本算「改了多少、命中多少、精确率召回率」，**每次都重写一遍，口径还容易漂**。
固化成工具后，评估一条新通道的边际成本从「写脚本 + 自己核口径」降到一条命令。

## 判据（三个定义，都写死在这里，不要在别处另立一套）

- **需改行**（`need`）：批内那些**车道现行译文 ≠ 冻结面 opus** 的 id。
  即「这一段最终认定确实该改」的行——它包含人裁采纳的通道稿、人工改写、以及
  用户复核时的改判，是本段全部判断的沉淀。
- **精确率** = |改动 ∩ 需改| / |改动|。
- **召回** = |改动 ∩ 需改| / |需改|。

## ⚠ 两条必须与数字一起读的告诫（否则这张表会被误用）

1. **「精确率」不是「正确率」。** 它衡量的是**与该 SEG 裁决结果的一致度**。一条没被
   采纳的改动未必是错的，只是裁决者判断不必改。低精确率更准确的读法是
   **「它比裁决者激进」**，而不是「它改错了」。
2. **参与过该 SEG 裁决的通道有循环优势。** 最终定稿主要就是从它们的候选里裁出来的，
   它们的精确率天然接近 100%。本工具会自动识别这类通道（seg 目录下存在
   `candidates.<name>.jsonl`）并在输出里标 `※`，**它们不该与外部测试通道同台比较**。
3. **⚠「逐字同定稿」比例异常高时，先怀疑抄袭，再考虑质量。** 独立产出的中文散文
   **不可能**大量与裁决结果逐字撞车——`exact` 那一列若在外部通道上接近 `hit`，
   最可能的解释是它读到了仓库里的 `patches.jsonl` 或别的通道的
   `candidates.*.jsonl`，而不是它译得准。
   2026-08-14 实证（`docs/ops/agy-cli-channel.md` §十）：一条外部通道报出
   `改动 29 / 命中 28 / 精确 97% / 召回 85% / 逐字同定稿 23`，看着是历来最好；
   逐字比对后发现 **23 处与最终定稿相同、22 处与另一通道的候选相同，
   三处都对不上的只有 1 条，而那一条是字形损坏**。
   **那个异常数字当时就在表里，却被读成了「质量好」而不是「太好了以至于可疑」。**

## 用法

```bash
uv run python tools/polish_bench.py --seg seg4-s3tail-s5 \\
    --batch <mirror>/pilot/polish/seg4-s3tail-s5/calib/seg4-s3tail-s5.batch.jsonl \\
    --channel "grok-4.5=<mirror>/.../out-grok45/raw.grok45.jsonl" \\
    --channel "kimi-k2.6=<mirror>/.../out-kimik26/raw.kimik26.jsonl" \\
    --meta "grok-4.5=9%|5分" --meta "kimi-k2.6=4%|3分" \\
    --lane-dir pilot/lanes/opus/data
```

`--batch` 给的是评测批（`{id, jp, opus_zh}`，`polish_calibrate --make` 或手工构造均可）；
不给则默认取该 SEG 的全部 id。`--meta` 是自由文本列（配额/耗时之类），只做展示。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.check_batch import MARKS, SPEAKER_RE, _max_line_width, _ruby_ok, w3_ratio
from tools.pipelib import REPO, read_jsonl
from tools.polishlib import jp_tail


def _seg_dir(label, repo):
    return Path(repo) / "pilot" / "polish" / label


def gates(jp, zh, want_tail, got_tail):
    """返回该行命中的机械闸列表（与 ingest/check 同口径，只是不写文件）。"""
    out = []
    if got_tail is not None and got_tail != want_tail:
        out.append("jp_tail")
    if not _ruby_ok(zh):
        out.append("R2a")
    if bool(SPEAKER_RE.match(jp)) != bool(SPEAKER_RE.match(zh)):
        out.append("R2b")
    for c in MARKS:
        if c in jp and c not in zh:
            out.append(f"R2c:{c}")
    for m in ("_n", "_r"):
        if jp.count(m) != zh.count(m):
            out.append(f"P4-CTL:{m}")
    if _max_line_width(zh) > max(10, _max_line_width(jp) * w3_ratio(jp)):
        out.append("W3")
    return out


def bench(label, channels, batch_path=None, lane_dir=None, repo=REPO, meta=None):
    """channels: {name: path}；返回 {"need": [...], "rows": [...]}。"""
    repo = Path(repo)
    d = _seg_dir(label, repo)
    opus = {r["id"]: r["zh"] for r in read_jsonl(d / "frozen" / "opus.jsonl")}
    src = {r["id"]: r["jp"] for r in read_jsonl(d / "frozen" / "source.jsonl")}

    if batch_path:
        rows = read_jsonl(Path(batch_path))
        ids = [r["id"] for r in rows]
        for r in rows:                       # 评测批自带 jp/opus_zh 时以它为准
            src.setdefault(r["id"], r.get("jp", ""))
            opus.setdefault(r["id"], r.get("opus_zh", ""))
    else:
        ids = list(src)

    lane = Path(lane_dir or (repo / "pilot" / "lanes" / "opus" / "data"))
    cur = {}
    for fn in ("forward.jsonl", "patches.jsonl"):
        p = lane / fn
        if p.exists():
            for r in read_jsonl(p):
                cur[r["id"]] = r.get("zh")

    need = {i for i in ids if i in cur and (cur[i] or "").strip() != (opus.get(i) or "").strip()}

    out = []
    for name, path in channels.items():
        rows = {r["id"]: r for r in read_jsonl(Path(path))}
        changed, hit, exact, gate_hits, missing = set(), set(), 0, 0, 0
        for i in ids:
            r = rows.get(i)
            if r is None:
                missing += 1
                continue
            zh = r.get("zh") or ""
            if zh.strip() != (opus.get(i) or "").strip():
                changed.add(i)
                if i in need:
                    hit.add(i)
                    if zh.strip() == (cur.get(i) or "").strip():
                        exact += 1
            if gates(src.get(i, ""), zh, jp_tail(src.get(i, "")), r.get("jp_tail")):
                gate_hits += 1
        out.append({
            "channel": name,
            "in_segment": (d / f"candidates.{name}.jsonl").exists(),
            "lines": len(rows), "missing": missing,
            "changed": len(changed), "hit": len(hit), "exact": exact,
            "precision": (len(hit) / len(changed)) if changed else None,
            "recall": (len(hit) / len(need)) if need else None,
            "gate_hits": gate_hits,
            "meta": (meta or {}).get(name, ""),
        })
    return {"label": label, "batch_size": len(ids), "need": sorted(need), "rows": out}


def render(res) -> str:
    L = [f"# 通道评测：{res['label']}（批 {res['batch_size']} 行）", ""]
    L.append(f"**最终定稿实际改动 {len(res['need'])} 行**——精确率/召回都以它为分母。")
    L.append("")
    L.append("| 通道 | 行数 | 缺行 | 改动 | 命中 | 精确 | 召回 | 逐字同定稿 | 闸命中 | 备注 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in res["rows"]:
        pc = "—" if r["precision"] is None else f"{r['precision']*100:.0f}%"
        rc = "—" if r["recall"] is None else f"{r['recall']*100:.0f}%"
        nm = r["channel"] + ("※" if r["in_segment"] else "")
        L.append(f"| {nm} | {r['lines']} | {r['missing']} | {r['changed']} | {r['hit']} | "
                 f"{pc} | {rc} | {r['exact']} | {r['gate_hits']} | {r['meta']} |")
    L += ["", "⚠ **三条读法上的告诫**：",
          "1. 「精确率」是**与本段裁决的一致度**，不是正确率——未被采纳的改动未必错，",
          "   低精确率更准确的读法是「它比裁决者激进」。",
          "2. 标 `※` 的通道**参与过本段裁决**，最终定稿主要就是从它们的候选里裁出来的，",
          "   精确率天然接近 100%，**不该与外部测试通道同台比较**。",
          "3. **「逐字同定稿」若在外部通道上接近「命中」，先怀疑抄袭而不是质量**——",
          "   独立产出的中文散文不可能大量逐字撞车。2026-08-14 有过一次实证，",
          "   见 `docs/ops/agy-cli-channel.md` §十。"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="通道评测：候选 vs 该 SEG 最终定稿")
    ap.add_argument("--seg", required=True)
    ap.add_argument("--channel", action="append", required=True,
                    metavar="名字=路径", help="可重复；路径指向该通道的 raw JSONL")
    ap.add_argument("--batch", help="评测批 JSONL（{id,jp,opus_zh}）；不给则用整段 id")
    ap.add_argument("--meta", action="append", default=[], metavar="名字=自由文本",
                    help="备注列（配额/耗时等），只做展示")
    ap.add_argument("--lane-dir", help="车道 data/ 目录（默认 pilot/lanes/opus/data）")
    ap.add_argument("--json", help="同时写一份机器可读结果")
    a = ap.parse_args(argv)

    def kv(items):
        out = {}
        for s in items:
            if "=" not in s:
                raise SystemExit(f"格式应为 名字=值，得到 {s!r}")
            k, v = s.split("=", 1)
            out[k] = v
        return out

    res = bench(a.seg, kv(a.channel), batch_path=a.batch,
                lane_dir=a.lane_dir, meta=kv(a.meta))
    print(render(res))
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
