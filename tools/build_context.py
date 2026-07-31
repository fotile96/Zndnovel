"""批次上下文组装：context.md / source.jsonl / manifest.json。"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO as _REPO, WORK as _WORK, dumps, read_jsonl, sha256_file
from tools.resolve import resolve_map

SECTION5 = "## 五、本批任务"


def _load(repo):
    data = repo / "data"
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    extra_p = data / "ledger_extra.jsonl"
    return {
        "ledger": {r["id"]: r for r in read_jsonl(data / "ledger.jsonl")},
        "timeline": read_jsonl(data / "timeline.jsonl"),
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
    out = ["## 一、冻结骨架（中文卡组）"]
    for c in cards:
        out.append(f"【卡{c['card']}】{c['title_zh']}：{c.get('body_zh','').replace(chr(10),'')}")
    return "\n".join(out)


def _unit_heading(unit) -> str:
    """timeline unit 的小标题正文：优先用 title，为空退化为 state，再退化为 src
    （三者在 gen_timeline.Expander.emit_unit 产出的 unit 里必有其一非空）。"""
    return unit.get("title") or unit.get("state") or unit.get("src") or ""


def _render_prefix(env, batch_no, profile, jp_fallback):
    led, zh = env["ledger"], env["zh"]
    prior_ids = [i for b, r in sorted(env["batches"].items())
                 if r["lane"] == "main" and b < batch_no for i in r["ids"]]
    cur_ch = env["batches"][batch_no]["chapter"]
    resolved = {}
    for i in prior_ids:
        ch = led[i]["chapter"]
        if profile in ("api-B", "cc") and ch != cur_ch:
            continue                       # 已完结章走章梗概（骨架卡已含），细文省略
        if i in zh:
            resolved[i] = zh[i]
        elif jp_fallback:
            resolved[i] = f"〔未译|{led[i]['jp']}〕"
        else:
            return None, i
    # 结构渲染：按 timeline 出现顺序把 marker（讲述指针回溯/推进——整条链路里
    # 唯一标记非线性的信号）与各 unit 的小标题夹进前缀正文，不再把 resolved 的
    # 译文拼成一长串连续文本首尾相接——否则同一个 _sel 节点互斥分支的续写会被
    # 模型读成先后发生的事件（CLAUDE.md：全部文本须「按出现顺序」拼接）。
    # 只渲染其 id 真落进 resolved 的 unit（被 profile 章别过滤掉的 unit 不留空
    # 标题）；resolved 里的 id 一旦被消耗完就立即停止扫描——否则 batch 1
    # （resolved 为空）会把全书 76 条 marker 都当结构信号倒进空前缀，chapter
    # 过滤后的批次也会带出不属于本次前缀的后续章节 marker。
    # marker 只在「已经渲染过至少一个 unit」之后才输出，即只渲染真正夹在两个
    # unit 之间的 marker（贴合措辞本身——「夹在相邻 unit 之间」）：cc/api-B 下
    # 实测（批次 70）显示，若不加这条门槛，被章别过滤掉的更早章节会在前缀最前面
    # 堆出一堵 34 条、58 行、前后都没有正文的 marker 墙（那些章节的细文本就是被
    # profile 过滤掉的，marker 脱离了它原本要消歧的正文，沦为噪音）；史上没有
    # unit 先出现过，说明这些 marker 全部来自与本批章别不同的更早章节——它们的
    # 消歧价值已经由骨架卡组的章梗概覆盖，不必在这里重复。
    out = ["\n## 二、前缀正文"]
    remaining = set(resolved)
    started = False
    for row in env["timeline"]:
        if not remaining:
            break
        if row["type"] == "marker":
            if started:
                out.append(f"> {row['text']}\n> {row['recap']}")
            continue
        hit = [i for i in row["ids"] if i in resolved]
        if not hit:
            continue
        out.append(f"### 【场景】{_unit_heading(row)}")
        out.extend(resolved[i] for i in hit)
        remaining.difference_update(hit)
        started = True
    return "\n".join(out), None


def glossary_version(repo) -> int:
    """glossary/ 下 glossary.v*.yaml 的最高版本号（append-only，最高版即现行）。
    gen_plan.py 复用同一份逻辑生成执行计划里的 --glossary-v，避免两处各自维护
    一个真相源（Minor：曾各自为政，计划文本会把 gen_plan 侧的硬编码盖进
    append-only 的 forward 行）。"""
    import re as _re
    versions = [int(_re.search(r"v(\d+)", p.stem).group(1))
                for p in (repo / "glossary").glob("glossary.v*.yaml")]
    return max(versions) if versions else 0


def build(batch, profile, baseline, repo=None, jp_fallback=False):
    # work_root：批次 ctx 产物的落盘根。真实仓库（repo 留默认）时用 pipelib.WORK
    # （可被 ZND_WORK 环境变量重定向，见 Critical 1——让子进程形式跑的 e2e 测试能
    # 把输出指到 tmp_path，不写真实 work/ 树）；单测传入替身 repo（如 tmp_path）时，
    # 保持原有「产物落在 repo/work 下」的隔离行为不变，不随 ZND_WORK 漂移。
    work_root = _WORK if repo is None else Path(repo) / "work"
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
    ctx_dir = work_root / "ctx" / f"batch_{batch}"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    (ctx_dir / "context.md").write_text(
        "\n".join([f"# 批次 {batch}（profile={profile}）",
                   _render_skeleton(env["cards"]), prefix, anchors, *tail]),
        encoding="utf-8")
    (ctx_dir / "source.jsonl").write_text(
        ("\n".join(dumps(r) for r in src_rows) + "\n") if src_rows else "",
        encoding="utf-8")
    gv = glossary_version(repo)
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
