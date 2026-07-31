"""批次上下文组装：context.md / source.jsonl / manifest.json。"""
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO as _REPO, WORK as _WORK, dumps, read_jsonl, sha256_file
from tools.resolve import resolve_map

SECTION5 = "## 五、本批任务"

# 章节梗概卡的 script 单元 src 集合（crd_133..145，见 CLAUDE.md「章节梗概卡
# 133–144 + 145」）：游戏机制里「这一章已被压成一张あらすじ卡」的边界，专供
# api-B/cc 前缀窗口识别使用。与 Task 7 删掉的 SYN_CARDS（chapter→卡号 映射）
# 是两回事，不要复活后者——这里锚定的是 script 单元的 src，不是 chapter 字段。
CHAPTER_CARD_SRCS = {f"snr_crd_{n}" for n in range(133, 146)}


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
    # 已经把这层压缩信息带进上下文；profile 差异只体现在 _render_prefix 对窗口外细文的丢弃
    # （见 _window_start_seq：窗口边界＝上一个章梗概卡单元，窗口外的内容正是这里已经
    # 承载的卡面梗概，省略细文不丢信息）。
    out = ["## 一、冻结骨架（中文卡组）"]
    for c in cards:
        out.append(f"【卡{c['card']}】{c['title_zh']}：{c.get('body_zh','').replace(chr(10),'')}")
    return "\n".join(out)


def _render_anchors(anchors_path) -> str:
    """第三节：锚点行紧凑日中对照。只给 id/jp/zh——recall 记录的是复现位置、
    裁决史与定译源指针，服务于骨架维护者；对译者不改变行动（命中锚点的行无论
    如何都要逐字沿用给定 zh），却占该节 35% 体量。省下的空间用于内嵌口调表。"""
    p = Path(anchors_path)
    if not p.exists():
        return "\n## 三、锚点行（暂缺）"
    groups = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    out = ["\n## 三、锚点行（日中对照；本批 source 命中的 id 必须逐字沿用 zh）"]
    for g in groups:
        out.append(f"### {g['chapter']}")
        for it in g["items"]:
            out.append(f"[{it['id']}] {it['jp']}")
            out.append(f"    → {it['zh']}")
    return "\n".join(out)


def _render_voices(voices_dir) -> str:
    """第四节尾部：角色口调表全文。reviewer_cc.md 按这些表判「口调表偏离」，
    译者此前拿不到它们——同一份标准必须两边都有（spec §4.4）。"""
    d = Path(voices_dir)
    if not d.is_dir():
        return ""
    return "".join(f"\n### 口调表：{p.stem}\n{p.read_text(encoding='utf-8')}\n"
                   for p in sorted(d.glob("*.md")))


def _unit_heading(unit) -> str:
    """timeline unit 的小标题正文：优先用 title，为空退化为 state，再退化为 src
    （三者在 gen_timeline.Expander.emit_unit 产出的 unit 里必有其一非空）。"""
    return unit.get("title") or unit.get("state") or unit.get("src") or ""


def _id_to_seq(timeline) -> dict:
    """timeline 里每个 unit id 到其所属 unit seq 的映射（marker 行没有 ids，
    不参与）。cc/api-B 前缀窗口靠它判断某 id 是否落在窗口内。"""
    m = {}
    for row in timeline:
        if row["type"] == "unit":
            for i in row["ids"]:
                m[i] = row["seq"]
    return m


def _window_start_seq(env, batch_no):
    """cc/api-B 前缀窗口的起点 seq。

    窗口边界＝「本批第一个时间轴位置（min(本批 seqs)）之前，最近的一个章梗概卡
    单元」（章梗概卡＝script 单元 src ∈ CHAPTER_CARD_SRCS，对应游戏机制里「这
    一章已被压成一张あらすじ卡」，见 CLAUDE.md「剧情 DAG 组装规则」第 4 条）。
    起点取该边界单元自身的 seq——窗口按 >= 起点收窄，即含边界自身：它是该章
    收尾的现实层框架剧情文本，不是骨架卡组已经承载的卡面梗概正文，仍需留在
    窗口内。已用真实数据核实：batch 81 窗口内 1073 行、batch 173 窗口内 1255
    行——都比"排除边界自身"的算法多 1，与"每个边界 unit 恰好 1 个 id"吻合。

    一个边界都找不到时起点为 0（＝全书开头，序章批次的情形）——窗口退化为
    「全部前序」，与 api-A 语义一致。

    本批 seqs 为空（extra/ambient 车道，没有时间轴位置）时返回 None，调用方
    应把窗口当作空处理——这是刻意选择，不是 chapter 比较失配的副产物：extra
    车道装的是卡面/UI 文本，正文由骨架卡组本身承载，术语一致性靠尾部术语表
    保证（见 _render_skeleton 顶部注释）。
    """
    seqs = env["batches"][batch_no]["seqs"]
    if not seqs:
        return None
    min_seq = min(seqs)
    boundary_seqs = [u["seq"] for u in env["timeline"]
                      if u["type"] == "unit" and u.get("src") in CHAPTER_CARD_SRCS
                      and u["seq"] < min_seq]
    return max(boundary_seqs) if boundary_seqs else 0


def _render_prefix(env, batch_no, profile, jp_fallback):
    led, zh = env["ledger"], env["zh"]
    prior_ids = [i for b, r in sorted(env["batches"].items())
                 if r["lane"] == "main" and b < batch_no for i in r["ids"]]
    if profile in ("api-B", "cc"):
        # 窗口过滤必须在下面的「未译则报错」循环之前完成：窗口外的 id 根本不该
        # 进前缀，因此也不该因未译触发退出码 2（它们由骨架卡组承载）。先在这里
        # 把 prior_ids 收窄成窗口内的子集，翻译检查循环就只会看到窗口内的 id——
        # 顺序反过来（对全部 prior_ids 先做翻译检查、事后再筛 resolved）会让
        # 窗口外的未译行错误地触发退出码 2。
        window_start = _window_start_seq(env, batch_no)
        if window_start is None:
            prior_ids = []          # 无时间轴位置（extra/ambient）：前缀只留骨架
        else:
            id2seq = _id_to_seq(env["timeline"])
            prior_ids = [i for i in prior_ids if id2seq.get(i, -1) >= window_start]
    resolved = {}
    for i in prior_ids:
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
    # 只渲染其 id 真落进 resolved 的 unit（被窗口筛掉的 unit 不留空标题）；
    # resolved 里的 id 一旦被消耗完就立即停止扫描——否则 batch 1（resolved 为
    # 空）会把全书 76 条 marker 都当结构信号倒进空前缀，窗口收窄后的批次也会
    # 带出不属于本次前缀的后续内容的 marker。
    # marker 只在「已经渲染过至少一个 unit」之后才输出，即只渲染真正夹在两个
    # unit 之间的 marker（贴合措辞本身——「夹在相邻 unit 之间」）：cc/api-B 下
    # 实测（批次 70）显示，若不加这条门槛，被窗口排除在外的更早内容会在前缀
    # 最前面堆出一堵前后都没有正文的 marker 墙（那些内容的细文本本来就被窗口
    # 筛掉了，marker 脱离了它原本要消歧的正文，沦为噪音）；史上没有 unit 先
    # 出现过，说明这些 marker 全部来自窗口之外的更早内容——它们的消歧价值
    # 已经由骨架卡组的章梗概覆盖，不必在这里重复。
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
    anchors = _render_anchors(anchors_p)
    voices = _render_voices(repo / "glossary" / "voices")
    tail = ["\n## 四、术语、风格与角色口调",
            json.dumps(env["active"], ensure_ascii=False),
            env["style"], voices,
            f"\n{SECTION5}（baseline={baseline}）"]
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
                "voices": hashlib.sha256(voices.encode("utf-8")).hexdigest(),
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
    ap.add_argument("--repo", default=None,
                    help="车道根目录（内含 data/skeleton/glossary，产物落其 work/ 下）；"
                         "省略时读仓库根、产物落 pipelib.WORK")
    a = ap.parse_args(argv)
    return build(a.batch, a.profile, a.baseline, repo=a.repo, jp_fallback=a.jp_fallback)


if __name__ == "__main__":
    raise SystemExit(main())
