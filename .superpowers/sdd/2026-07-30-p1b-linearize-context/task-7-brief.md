### Task 7: build_context（三 profile × 四 baseline）

**Files:**
- Create: `tools/build_context.py`
- Test: `tests/test_build_context.py`

**Interfaces:**
- Produces: CLI `uv run python tools/build_context.py --batch N --profile {api-A|api-B|cc} --baseline {none|ref|revise|judge} [--jp-fallback]` → `work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`
  - `source.jsonl` 行：`{"id":int,"jp":str}`＋baseline≠none 时 `"base":str`（resolve() 生效译文）
  - `manifest.json`：`{"batch","profile","baseline","glossary_v","skeleton":"cards.zh.yaml sha256","anchors":"sha256|absent","ctx_sha":"context.md sha256"}`
  - 前缀构成：api-A=骨架+全部已译 timeline 前缀（zh）；api-B 与 cc=骨架+已完结章的章梗概卡（cards.zh 卡133-145 对应章）+当前章已译 zh；**baseline 只进尾部**——`--baseline none` 与其他档的 context.md 至「## 五、本批任务」之前逐字节相同（测试断言此不变量）
  - 前缀取 zh：`resolve.resolve_map`；prefix 内未译行默认报错退出 2，`--jp-fallback` 时以 `〔未译|jp〕` 行代替
- Consumes: `skeleton/cards.zh.yaml`、`skeleton/anchors.yaml`（若存在）、`glossary/active.json`、`glossary/style.md`、data/ 各件

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path
from tools.build_context import build

def _env(tmp_path):
    d = tmp_path
    (d / "data").mkdir(); (d / "glossary").mkdir(); (d / "skeleton").mkdir()
    (d / "skeleton" / "cards.zh.yaml").write_text(
        "- {card: 1, variant: a, title_zh: 测试卡, body_zh: 骨架正文, tr_note: ''}\n",
        encoding="utf-8")
    (d / "glossary" / "active.json").write_text('{"あ":"啊"}', encoding="utf-8")
    (d / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    rows = [
        {"id": 1, "jp": "第一句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
        {"id": 2, "jp": "第二句", "chapter": "a", "kind": "narrative", "file": "f", "func": "g"},
    ]
    (d / "data" / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (d / "data" / "timeline.jsonl").write_text(json.dumps(
        {"type": "unit", "unit_kind": "scene", "src": "f", "state": "a_10",
         "title": "一", "ids": [1, 2]}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text(json.dumps(
        {"batch": 1, "lane": "main", "ids": [1, 2], "jp_chars": 6,
         "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False), encoding="utf-8")
    (d / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "已译一", "batch": 0, "backend": "cc", "model": "m",
                    "ctx": "c", "glossary_v": 4, "ts": "t"}, ensure_ascii=False),
        encoding="utf-8")
    return d

def test_ctx_files_and_manifest(tmp_path):
    d = _env(tmp_path)
    build(batch=1, profile="cc", baseline="none", repo=d)
    ctx = d / "work" / "ctx" / "batch_1"
    assert (ctx / "context.md").exists() and (ctx / "manifest.json").exists()
    src = [json.loads(l) for l in (ctx / "source.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in src] == [1, 2] and "base" not in src[0]

def test_baseline_only_touches_tail(tmp_path):
    d = _env(tmp_path)
    build(batch=1, profile="cc", baseline="none", repo=d)
    a = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    build(batch=1, profile="cc", baseline="revise", repo=d)
    b = (d / "work/ctx/batch_1/context.md").read_text(encoding="utf-8")
    cut = "## 五、本批任务"
    assert a.split(cut)[0] == b.split(cut)[0]
    src = [json.loads(l) for l in (d / "work/ctx/batch_1/source.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert src[0]["base"] == "已译一"

def test_untranslated_prefix_requires_fallback(tmp_path):
    d = _env(tmp_path)
    # 批次 2：把行 2 当作后续批，行 1 未译时前缀应报错
    (d / "data" / "forward.jsonl").write_text("", encoding="utf-8")
    (d / "data" / "batches.jsonl").write_text("\n".join([
        json.dumps({"batch": 1, "lane": "main", "ids": [1], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "budget"}, ensure_ascii=False),
        json.dumps({"batch": 2, "lane": "main", "ids": [2], "jp_chars": 3,
                    "chapter": "a", "cut_reason": "tail"}, ensure_ascii=False)]),
        encoding="utf-8")
    assert build(batch=2, profile="api-A", baseline="none", repo=d) == 2
    assert build(batch=2, profile="api-A", baseline="none", repo=d, jp_fallback=True) == 0
```

- [ ] **Step 2: Run test to verify it fails** → `uv run pytest tests/test_build_context.py -v`（ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

`tools/build_context.py`（骨干；渲染顺序即 context.md 章节顺序）：

```python
"""批次上下文组装：context.md / source.jsonl / manifest.json。"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pipelib import REPO as _REPO, dumps, read_jsonl, sha256_file
from tools.resolve import resolve_map

SECTION5 = "## 五、本批任务"
SYN_CARDS = {"s1": 133, "s2": 134, "s3a": 135, "s3b": 136, "s4a": 137, "s4b": 138,
             "s5": 139, "s6": 140, "s7": 141, "s8": 142, "e1": 143, "e2": 144}


def _load(repo):
    data = repo / "data"
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    return {
        "ledger": {r["id"]: r for r in read_jsonl(data / "ledger.jsonl")},
        "timeline": read_jsonl(data / "timeline.jsonl"),
        "batches": {r["batch"]: r for r in read_jsonl(data / "batches.jsonl")},
        "zh": resolve_map(fwd, pat),
        "cards": yaml.safe_load(open(repo / "skeleton" / "cards.zh.yaml", encoding="utf-8")),
        "active": json.loads((repo / "glossary" / "active.json").read_text(encoding="utf-8")),
        "style": (repo / "glossary" / "style.md").read_text(encoding="utf-8"),
    }


def _render_skeleton(cards):
    out = ["# 一、冻结骨架（中文卡组）"]
    for c in cards:
        out.append(f"【卡{c['card']}】{c['title_zh']}：{c.get('body_zh','').replace(chr(10),'')}")
    return "\n".join(out)


def _render_prefix(env, batch_no, profile, jp_fallback):
    led, zh = env["ledger"], env["zh"]
    prior_ids = [i for b, r in sorted(env["batches"].items())
                 if r["lane"] == "main" and b < batch_no for i in r["ids"]]
    cur_ch = env["batches"][batch_no]["chapter"]
    out, missing = ["\n## 二、前缀正文"], 0
    for i in prior_ids:
        ch = led[i]["chapter"]
        if profile in ("api-B", "cc") and ch != cur_ch:
            continue                       # 已完结章走章梗概（骨架卡已含），细文省略
        if i in zh:
            out.append(zh[i])
        elif jp_fallback:
            out.append(f"〔未译|{led[i]['jp']}〕"); missing += 1
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
        if isinstance(i, int):
            row = {"id": i, "jp": env["ledger"][i]["jp"]}
            if baseline != "none" and i in env["zh"]:
                row["base"] = env["zh"][i]
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
        "\n".join(dumps(r) for r in src_rows) + "\n", encoding="utf-8")
    import re as _re
    gv = max(int(_re.search(r"v(\d+)", p.stem).group(1))
             for p in (repo / "glossary").glob("glossary.v*.yaml"))
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
```

（测试环境 tmp_path 下无 glossary.v*.yaml 时 `max()` 会抛错——测试夹具需写入一个 `glossary.v1.yaml` 空壳，或 build() 中对空 glob 回退 `gv=0`；实现取后者更稳。）

- [ ] **Step 4: Run test to verify it passes** → `uv run pytest tests/test_build_context.py -v`
- [ ] **Step 5: Commit** → `git add tools/build_context.py tests/test_build_context.py && git commit -m "feat: build_context 三 profile×四 baseline 组装"`

---

