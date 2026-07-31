"""批次上下文组装：context.md / source.jsonl / manifest.json。"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO as _REPO, dumps, read_jsonl, sha256_file
from tools.resolve import resolve_map

SECTION5 = "## 五、本批任务"


def _load(repo):
    data = repo / "data"
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    extra_p = data / "ledger_extra.jsonl"
    return {
        "ledger": {r["id"]: r for r in read_jsonl(data / "ledger.jsonl")},
        "extra": {r["key"]: r for r in read_jsonl(extra_p)} if extra_p.exists() else {},
        "batches": {r["batch"]: r for r in read_jsonl(data / "batches.jsonl")},
        "zh": resolve_map(fwd, pat),
        "cards": yaml.safe_load(open(repo / "skeleton" / "cards.zh.yaml", encoding="utf-8")),
        "active": json.loads((repo / "glossary" / "active.json").read_text(encoding="utf-8")),
        "style": (repo / "glossary" / "style.md").read_text(encoding="utf-8"),
    }


def _render_skeleton(cards):
    # 接口所述 api-B/cc「已完结章的章梗概卡」（cards.zh 卡 133-145 对应章）不需要额外的
    # 挑选/映射逻辑：骨架卡组对任何 profile、任何批次都完整渲染全部卡（含 133-145），
    # 已经把这层压缩信息带进上下文；profile 差异只体现在 _render_prefix 对别章细文的丢弃。
    out = ["# 一、冻结骨架（中文卡组）"]
    for c in cards:
        out.append(f"【卡{c['card']}】{c['title_zh']}：{c.get('body_zh','').replace(chr(10),'')}")
    return "\n".join(out)


def _render_prefix(env, batch_no, profile, jp_fallback):
    led, zh = env["ledger"], env["zh"]
    prior_ids = [i for b, r in sorted(env["batches"].items())
                 if r["lane"] == "main" and b < batch_no for i in r["ids"]]
    cur_ch = env["batches"][batch_no]["chapter"]
    out = ["\n## 二、前缀正文"]
    for i in prior_ids:
        ch = led[i]["chapter"]
        if profile in ("api-B", "cc") and ch != cur_ch:
            continue                       # 已完结章走章梗概（骨架卡已含），细文省略
        if i in zh:
            out.append(zh[i])
        elif jp_fallback:
            out.append(f"〔未译|{led[i]['jp']}〕")
        else:
            return None, i
    return "\n".join(out), None


def build(batch, profile, baseline, repo=None, jp_fallback=False):
    repo = Path(repo or _REPO)
    env = _load(repo)
    b = env["batches"][batch]
    prefix, blocked = _render_prefix(env, batch, profile, jp_fallback)
    if prefix is None:
        print(f"前缀行 {blocked} 未译（--jp-fallback 可放行）", file=sys.stderr)
        return 2
    anchors_p = repo / "skeleton" / "anchors.yaml"
    anchors = ("\n## 三、锚点行（日中对照）\n" +
               anchors_p.read_text(encoding="utf-8")) if anchors_p.exists() else \
              "\n## 三、锚点行（暂缺）"
    tail = ["\n## 四、术语与风格", json.dumps(env["active"], ensure_ascii=False),
            env["style"], f"\n{SECTION5}（baseline={baseline}）"]
    src_rows = []
    for i in b["ids"]:
        # main/ambient 车道 ids 为 int（查 ledger，可带 base）；extra 车道 ids 为 str
        # （查 ledger_extra，base 无意义——resolve_map 只按 int id 建）。两张表都查不到
        # 时必须报错（带批号/id/类型），不许静默丢行（曾经的缺陷：extra 批次整批丢空）。
        if isinstance(i, int) and i in env["ledger"]:
            row = {"id": i, "jp": env["ledger"][i]["jp"]}
            if baseline != "none" and i in env["zh"]:
                row["base"] = env["zh"][i]
        elif isinstance(i, str) and i in env["extra"]:
            row = {"id": i, "jp": env["extra"][i]["jp"]}
        else:
            raise ValueError(f"批次 {batch} 的 id {i!r}（类型 {type(i).__name__}）"
                              f"在 ledger 与 ledger_extra 中均未找到")
        src_rows.append(row)
        tail.append(f"[{i}] {row['jp']}" +
                    (f"\n    base: {row.get('base','')}" if baseline != "none" else ""))
    ctx_dir = repo / "work" / "ctx" / f"batch_{batch}"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    (ctx_dir / "context.md").write_text(
        "\n".join([f"# 批次 {batch}（profile={profile}）",
                   _render_skeleton(env["cards"]), prefix, anchors, *tail]),
        encoding="utf-8")
    (ctx_dir / "source.jsonl").write_text(
        ("\n".join(dumps(r) for r in src_rows) + "\n") if src_rows else "",
        encoding="utf-8")
    import re as _re
    versions = [int(_re.search(r"v(\d+)", p.stem).group(1))
                for p in (repo / "glossary").glob("glossary.v*.yaml")]
    gv = max(versions) if versions else 0
    manifest = {"batch": batch, "profile": profile, "baseline": baseline,
                "glossary_v": gv,
                "skeleton": sha256_file(repo / "skeleton" / "cards.zh.yaml"),
                "anchors": sha256_file(anchors_p) if anchors_p.exists() else "absent",
                "ctx_sha": sha256_file(ctx_dir / "context.md")}
    (ctx_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--profile", choices=["api-A", "api-B", "cc"], required=True)
    ap.add_argument("--baseline", choices=["none", "ref", "revise", "judge"], default="none")
    ap.add_argument("--jp-fallback", action="store_true")
    a = ap.parse_args(argv)
    return build(a.batch, a.profile, a.baseline, jp_fallback=a.jp_fallback)


if __name__ == "__main__":
    raise SystemExit(main())
