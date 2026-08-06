"""彩野题库 ↔ 现行译文的失同步检查（回改把译文改了、题库没跟）。

**要防的事**：题库的参考答案大量**逐字引用译文**。而译文会被后续的抽读裁定/召回令
改掉（`patches.jsonl` 覆盖 `forward.jsonl`），题库却不会跟着动——于是标准答案里留着
一条**已经作废的译文串**，受试照现行译文作答反而被判「错」。

不是假想：SEG-7 的 `56be2f9` 把崩解开篇 5683/5684 的「きく 三换字」从 `闻/问/听` 改成
`汀/厅/听`，而 `seg7-e2.yaml` q11 的参考答案当时已写着 `闻/问/听`。**没有任何机械闸
能抓到这一类**——题库不参与 `check_batch`，`add_patch` 也不知道题库存在。

## 判据（第二版；第一版是错的，留档为戒）

第一版从参考答案里抽 `「」` 引文、查它还在不在现行译文里。**那个判据抓不到自己的
立案案例**——q11 把那三个字写在 `（）` 里而非 `「」`，正则够不着；而且它对「出题人
自己的转述」大量伪报（222 条引文报出 51 条候选，23%）。**一个抓不到自己创立理由的闸
就是恒绿闸。**

第二版反过来做，判据精确得多：

> 找出**同时出现在题库和「被覆盖的旧译文」里、却不在现行译文里**的片段。

这正是缺陷的定义本身：题库引着一句**曾经存在、现在已经不存在**的译文。
不需要猜哪段是引文、哪段是转述——转述若与旧译文有 ≥N 字的逐字重合，那它本来
也就是引文。

「被覆盖的旧译文」＝ 该 id 在 `forward.jsonl` 里的值，以及除末条外的历次 patch 值。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import read_jsonl

DECO_RE = re.compile(r"\*\*")
# ruby `<汉字,拼音>` 是渲染层标记、不是文本内容（style.md 用户裁决）。不剥它，
# 「给某行补注音」这种**只改渲染不改文本**的 patch 会被整行报成失同步——实测
# 12 条候选里有 5 条是这么来的（11130/11132/11268/11289）。
RUBY_RE = re.compile(r"<([^,<>]+),[^,<>]+>")
SPEAKER_RE = re.compile(r"^【[^】]*】")


def _norm(s: str) -> str:
    """比对前归一：去粗体星号、控制码、空白。

    `_n`/`_r` 是引擎断行符，题库引用时通常不带、译文里却有——不归一会让所有跨行
    引文永远匹配不上（第一版就吃过这个亏的反面：那时是伪报，这里会变成漏报）。
    """
    s = RUBY_RE.sub(lambda m: m.group(1), DECO_RE.sub("", s or ""))
    s = s.replace("_n", "").replace("_r", "")
    return re.sub(r"\s+", "", s)


def superseded(data_dir) -> dict:
    """→ {id: [被覆盖的旧 zh, …]}（不含现行值）。

    现行值＝最后一条 patch（若有），否则 forward 末条。其余历史值都是「曾经存在、
    现在已不存在」的文本。
    """
    data = Path(data_dir)
    fwd, pat = {}, {}
    p = data / "forward.jsonl"
    if p.exists():
        for r in read_jsonl(p):
            fwd[r["id"]] = r["zh"]
    q = data / "patches.jsonl"
    if q.exists():
        for r in read_jsonl(q):
            pat.setdefault(r["id"], []).append(r["zh"])
    out = {}
    for i, vals in pat.items():
        old = ([fwd[i]] if i in fwd else []) + vals[:-1]
        if old:
            out[i] = old
    return out


def _common_runs(a: str, b: str, min_len: int) -> list:
    """a 与 b 的所有长度 ≥ min_len 的公共子串（取极大者，去重）。"""
    hits, n = [], len(a)
    i = 0
    while i <= n - min_len:
        j = i + min_len
        if a[i:j] not in b:
            i += 1
            continue
        while j < n and a[i:j + 1] in b:
            j += 1
        run = a[i:j]
        if not any(run in h for h in hits):
            hits.append(run)
        i = j - min_len + 1
    return hits


def check(qa_paths, data_dir, min_len=8, *, any_line=False) -> list:
    """→ [{qa, id, fragment}]：题库里引着已作废译文的片段。"""
    import yaml
    old_map = superseded(data_dir)
    data = Path(data_dir)
    cur = {}
    p = data / "forward.jsonl"
    if p.exists():
        for r in read_jsonl(p):
            cur[r["id"]] = r["zh"]
    q = data / "patches.jsonl"
    if q.exists():
        for r in read_jsonl(q):
            cur[r["id"]] = r["zh"]
    # 全库现行译文（归一后连成一条）——判「这个片段是不是真的从语料里消失了」。
    # 只看该 id 的现行值不够：`ユウイチ同学` 只在**千秋侧**被改成「学长」，别处仍在，
    # 题库引它完全正确。**要报的是「全库都没有了」的串**，否则短片段全是伪报
    # （实测 min-len=6 时 30 条候选里 19 条是这种）。
    corpus = "\n".join(_norm(SPEAKER_RE.sub("", v)) for v in cur.values())
    out = []
    for path in qa_paths:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        blob = _norm("\n".join(
            (x.get("reference", "") or "") + (x.get("question", "") or "")
            for x in doc.get("questions", [])))
        for i, olds in old_map.items():
            now = _norm(SPEAKER_RE.sub("", cur.get(i, "")))
            for o in olds:
                for run in _common_runs(_norm(SPEAKER_RE.sub("", o)), blob, min_len):
                    # 片段若在现行译文里也存在，说明它是这一行**没被改动**的部分，
                    # 题库引它完全正确——只有「旧有、今无」的片段才是失同步。
                    if run not in now and (any_line or run not in corpus):
                        out.append({"qa": Path(path).name, "id": i, "fragment": run})
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="查彩野题库是否还引着被回改覆盖掉的旧译文")
    ap.add_argument("--qa", nargs="+", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--min-len", type=int, default=6,
                    help="公共子串长度下限（默认 6）——再短会撞上通用词")
    ap.add_argument("--any-line", action="store_true",
                    help="放宽：只要该 id 的现行值里没有就报（不再要求全库都没有）。"
                         "会多出大量伪报，仅在排查时用")
    ap.add_argument("--strict", action="store_true", help="有命中即退出码 1")
    a = ap.parse_args(argv)
    data = Path(a.data_dir)
    if not (data / "forward.jsonl").exists():
        print(f"!! 告警：{data}/forward.jsonl 不存在——没有译文可比，本次必然零命中。"
              f"**零命中在这种情况下不代表没问题**，多半是 --data-dir 指错了。",
              file=sys.stderr)
    hits = check(a.qa, data, a.min_len, any_line=a.any_line)
    old = superseded(data)
    print(f"被回改覆盖过的 id：{len(old)} 个（data-dir={data}，min-len={a.min_len}）")
    if not hits:
        print(f"✅ {len(a.qa)} 份题库都没有引用已作废的译文")
    for h in hits:
        print(f"  ⚠ {h['qa']} 引着 id {h['id']} 的旧译文片段：「{h['fragment']}」")
    if hits:
        print("→ 这些片段在旧译文里有、在现行译文里没有。题库须跟着回改更新，"
              "否则受试照现行译文作答会被判错。")
    return 1 if (hits and a.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
