### Task 1: 领域只读工具层 `tools/agent_tools.py`

**Files:**
- Create: `tools/agent_tools.py`
- Test: `tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `tools.pipelib`（`REPO`/`DATA`/`read_jsonl`）、`tools.resolve.resolve_map(forward_rows, patch_rows) -> dict{id: zh}`、`tools.cluster_notes.parse_notes(text, chapter) -> list[dict(chapter,batch,num,title,terms,starred,body)]`、`data/ledger.jsonl`（行含 `id:int, jp:str, chapter:str`）、`skeleton/anchors.yaml`（章列表，每章 `items` 含 `id/jp/zh/recall`）。
- Produces: `ToolSpec`（`namedtuple` 含 `fn`/`schema`/`description`）；`TOOLS: dict[str, ToolSpec]` 注册表；四个函数 `get_lines(ids, lane_dir=None)`、`search_lines(keyword, scope="all", limit=20, lane_dir=None)`、`get_note_proposal(chapter, batch, num, lane_dir=None)`、`get_anchor(id)`；`call_tool(name, args, lane_dir=None) -> dict`；`tool_schemas() -> list[dict]`（Responses API function 形状）。Task 2/3/4/5 消费。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_agent_tools.py`：

```python
"""领域只读工具层：纯函数 + 注册表 + CLI。全部只读——这是自建 agent loop 的安全性来源。"""
import json

import pytest

from tools.agent_tools import TOOLS, call_tool, tool_schemas


def _mk_lane(tmp_path):
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "forward.jsonl").write_text("\n".join([
        json.dumps({"id": 10, "zh": "【彩野】「那孩子的名字……」"}, ensure_ascii=False),
        json.dumps({"id": 11, "zh": "头发睡翘了"}, ensure_ascii=False),
    ]), encoding="utf-8")
    (lane / "data" / "notes" / "s1s.md").write_text(
        "# 提案\n\n## batch 4\n\n### 1. 寝癖 → 睡翘的头发\n- id 11\n- 理由：略。\n",
        encoding="utf-8")
    return lane


def _mk_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir()
    (repo / "data" / "ledger.jsonl").write_text("\n".join([
        json.dumps({"id": 10, "jp": "【彩野】「あの子の名前って……」", "chapter": "crd"},
                   ensure_ascii=False),
        json.dumps({"id": 11, "jp": "寝癖がなおらない", "chapter": "s1s"}, ensure_ascii=False),
        json.dumps({"id": 12, "jp": "寝癖はそのまま", "chapter": "s1s"}, ensure_ascii=False),
    ]), encoding="utf-8")
    (repo / "skeleton" / "anchors.yaml").write_text(
        "- chapter: s1s\n  items:\n    - id: 11\n      jp: 寝癖がなおらない\n"
        "      zh: 头发睡翘了\n      recall: 跨轨复现，须逐字一致\n", encoding="utf-8")
    return repo


def test_registry_shape_and_schemas():
    assert set(TOOLS) == {"get_lines", "search_lines", "get_note_proposal", "get_anchor"}
    for name, spec in TOOLS.items():
        assert callable(spec.fn) and spec.description.strip()
        assert spec.schema["type"] == "object" and "properties" in spec.schema
    schemas = tool_schemas()
    assert {s["name"] for s in schemas} == set(TOOLS)
    for s in schemas:
        assert s["type"] == "function" and s["parameters"]["type"] == "object"


def test_get_lines_returns_jp_and_zh(tmp_path, monkeypatch):
    repo, lane = _mk_repo(tmp_path), _mk_lane(tmp_path)
    monkeypatch.setattr("tools.agent_tools.REPO", repo)
    out = call_tool("get_lines", {"ids": [10, 11, 999]}, lane_dir=lane)
    got = {r["id"]: r for r in out["lines"]}
    assert got[10]["jp"] == "【彩野】「あの子の名前って……」"
    assert got[10]["zh"] == "【彩野】「那孩子的名字……」"
    assert got[11]["chapter"] == "s1s"
    assert got[999]["jp"] is None and got[999]["zh"] is None   # 缺行如实报 None，不静默丢


def test_search_lines_scope_and_limit(tmp_path, monkeypatch):
    repo, lane = _mk_repo(tmp_path), _mk_lane(tmp_path)
    monkeypatch.setattr("tools.agent_tools.REPO", repo)
    out = call_tool("search_lines", {"keyword": "寝癖", "scope": "s1s", "limit": 1},
                    lane_dir=lane)
    assert out["total_hits"] == 2 and len(out["lines"]) == 1 and out["truncated"] is True
    out2 = call_tool("search_lines", {"keyword": "寝癖", "scope": "crd"}, lane_dir=lane)
    assert out2["total_hits"] == 0


def test_get_note_proposal(tmp_path, monkeypatch):
    repo, lane = _mk_repo(tmp_path), _mk_lane(tmp_path)
    monkeypatch.setattr("tools.agent_tools.REPO", repo)
    out = call_tool("get_note_proposal", {"chapter": "s1s", "batch": 4, "num": 1},
                    lane_dir=lane)
    assert "寝癖" in out["title"] and "id 11" in out["body"]


def test_get_anchor_hit_and_miss(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    monkeypatch.setattr("tools.agent_tools.REPO", repo)
    hit = call_tool("get_anchor", {"id": 11})
    assert hit["is_anchor"] is True and hit["zh"] == "头发睡翘了"
    miss = call_tool("get_anchor", {"id": 10})
    assert miss["is_anchor"] is False


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        call_tool("rm_rf", {}, lane_dir=None)


def test_module_has_no_write_operations():
    """只读约束是自建 loop 的安全性来源：本模块不得出现任何写文件的调用。"""
    src = (__import__("pathlib").Path(__file__).resolve().parent.parent
           / "tools" / "agent_tools.py").read_text(encoding="utf-8")
    for bad in ("write_text(", "open(", "write_jsonl(", "mkdir(", "unlink("):
        assert bad not in src, f"agent_tools 出现写操作嫌疑：{bad}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_agent_tools.py -v`
Expected: FAIL（`ModuleNotFoundError: tools.agent_tools`）。

- [ ] **Step 3: 写实现**

写入 `tools/agent_tools.py`：

```python
"""领域只读工具层：给 DeepSeek agent loop 用的四个工具，同时提供 CLI 子命令。

**全部只读**——本模块不含任何写操作。这不是巧合而是设计约束（spec §1.2）：
自建 agent loop 的通常风险是跑飞/死循环/误改，把工具面限定为只读之后，
循环跑飞的最坏后果是报告不完整，而不是仓库被改坏。唯一的写操作（写报告）
由任务层执行、不经过模型。`tests/test_agent_tools.py` 有一条断言守着这一点。

一份实现三个消费面（spec §3.3）：①Python 直调（agent_loop 用）②CLI 子命令
（任何有 Bash 的 agent 可调；也让人能手动复算模型看到的东西——对一个反复强调
「不要恒绿关卡」的项目，这本身是纪律的一部分）③MCP server（**现在不做**，
schema 已是 MCP 形状，将来包一层即可）。
"""
import json
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yaml

from tools.pipelib import REPO, read_jsonl
from tools.resolve import resolve_map
from tools.cluster_notes import parse_notes

ToolSpec = namedtuple("ToolSpec", "fn schema description")

DEFAULT_LANE = "pilot/lanes/opus"
SEARCH_LIMIT = 20


def _lane(lane_dir):
    return Path(lane_dir) if lane_dir else REPO / DEFAULT_LANE


def _ledger():
    return {r["id"]: r for r in read_jsonl(REPO / "data" / "ledger.jsonl")}


def _zh(lane_dir):
    data = _lane(lane_dir) / "data"
    fwd = read_jsonl(data / "forward.jsonl") if (data / "forward.jsonl").exists() else []
    pat = read_jsonl(data / "patches.jsonl") if (data / "patches.jsonl").exists() else []
    return resolve_map(fwd, pat)


def get_lines(ids, lane_dir=None):
    """取若干 id 的原文与现行译文。缺行如实返回 None，不静默丢弃。"""
    led, zh = _ledger(), _zh(lane_dir)
    out = []
    for i in ids:
        r = led.get(i)
        out.append({"id": i, "jp": r["jp"] if r else None,
                    "chapter": r.get("chapter") if r else None, "zh": zh.get(i)})
    return {"lines": out}


def search_lines(keyword, scope="all", limit=SEARCH_LIMIT, lane_dir=None):
    """按关键词在原文中检索，限量返回。`scope` 为章别或 "all"。"""
    led, zh = _ledger(), _zh(lane_dir)
    hits = [r for r in led.values()
            if keyword in r.get("jp", "") and (scope == "all" or r.get("chapter") == scope)]
    hits.sort(key=lambda r: r["id"])
    shown = hits[:limit]
    return {"total_hits": len(hits), "truncated": len(hits) > len(shown),
            "lines": [{"id": r["id"], "jp": r["jp"], "chapter": r.get("chapter"),
                       "zh": zh.get(r["id"])} for r in shown]}


def get_note_proposal(chapter, batch, num, lane_dir=None):
    """取单条译者手记提案的标题与正文。"""
    p = _lane(lane_dir) / "data" / "notes" / f"{chapter}.md"
    if not p.exists():
        return {"found": False, "title": None, "body": None}
    for prop in parse_notes(p.read_text(encoding="utf-8"), chapter):
        if prop["batch"] == batch and prop["num"] == num:
            return {"found": True, "title": prop["title"], "body": prop["body"]}
    return {"found": False, "title": None, "body": None}


def get_anchor(id):
    """该 id 是否为伏笔锚点；是则给出定译 zh 与 recall 说明。"""
    doc = yaml.safe_load((REPO / "skeleton" / "anchors.yaml").read_text(encoding="utf-8"))
    for chap in doc or []:
        for item in chap.get("items") or []:
            if item.get("id") == id:
                return {"is_anchor": True, "chapter": chap.get("chapter"),
                        "jp": item.get("jp"), "zh": item.get("zh"),
                        "recall": item.get("recall")}
    return {"is_anchor": False, "chapter": None, "jp": None, "zh": None, "recall": None}


TOOLS = {
    "get_lines": ToolSpec(
        get_lines,
        {"type": "object",
         "properties": {"ids": {"type": "array", "items": {"type": "integer"},
                                "description": "要取的消息 id 列表"}},
         "required": ["ids"]},
        "取若干 id 的日文原文与现行中文译文（缺行返回 null）"),
    "search_lines": ToolSpec(
        search_lines,
        {"type": "object",
         "properties": {"keyword": {"type": "string", "description": "在日文原文中检索的关键词"},
                        "scope": {"type": "string", "description": "章别如 s1s，或 all"},
                        "limit": {"type": "integer", "description": f"返回上限，默认 {SEARCH_LIMIT}"}},
         "required": ["keyword"]},
        "按关键词检索日文原文，限量返回命中行的原文与译文"),
    "get_note_proposal": ToolSpec(
        get_note_proposal,
        {"type": "object",
         "properties": {"chapter": {"type": "string"}, "batch": {"type": "integer"},
                        "num": {"type": "integer"}},
         "required": ["chapter", "batch", "num"]},
        "取单条译者手记提案的标题与正文"),
    "get_anchor": ToolSpec(
        get_anchor,
        {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
        "查某 id 是否为伏笔锚点及其定译"),
}


def tool_schemas():
    """Responses API function 形状（同时也是 MCP tool 形状，便于将来包 MCP server）。"""
    return [{"type": "function", "name": n, "description": s.description,
             "parameters": s.schema} for n, s in TOOLS.items()]


def call_tool(name, args, lane_dir=None):
    """按名字分发。未注册的名字抛 KeyError（不静默返回空）。"""
    spec = TOOLS[name]
    kwargs = dict(args)
    if name != "get_anchor":
        kwargs["lane_dir"] = lane_dir
    return spec.fn(**kwargs)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="领域只读工具的 CLI 面（JSON 输出）")
    ap.add_argument("tool", choices=sorted(TOOLS) + ["schemas"])
    ap.add_argument("--args", default="{}", help="JSON 形式的参数，如 '{\"ids\":[10,11]}'")
    ap.add_argument("--lane-dir", default=None)
    a = ap.parse_args(argv)
    if a.tool == "schemas":
        print(json.dumps(tool_schemas(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(call_tool(a.tool, json.loads(a.args), lane_dir=a.lane_dir),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**注意**：`main()` 里用了 `print` 而非写文件——只读约束成立。测试里那条「无写操作」断言会扫描源码里的 `open(`/`write_text(` 等，实现里不要引入它们（`read_text` 不含 `open(` 子串，`parse_notes` 的读取在 `cluster_notes` 侧）。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_agent_tools.py -v` → 7 passed。

- [ ] **Step 5: 真实数据冒烟（CLI 面）**

```bash
uv run python tools/agent_tools.py get_lines --args '{"ids":[9441,9460,9483]}' --lane-dir pilot/lanes/opus
uv run python tools/agent_tools.py get_anchor --args '{"id":8478}'
uv run python tools/agent_tools.py schemas | head -20
```
Expected: 第一条应显示这三行 zh 完全相同而 jp 存在 `人の事`/`人のこと` 差异（这是 C3 重做查出的真信号，正好可作为工具正确性的现实校验）；第二条 `is_anchor: true`（8478 是 v7 补的サクラ汉字呼名锚点）。把实际输出摘要写进报告。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 361 passed。

```bash
git add tools/agent_tools.py tests/test_agent_tools.py
git commit -m "feat: 领域只读工具层（四工具 + 注册表 + CLI 面）"
```

---

