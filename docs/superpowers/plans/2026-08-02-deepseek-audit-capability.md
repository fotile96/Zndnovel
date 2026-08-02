# DeepSeek 审计能力 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 DeepSeek 承担「读若干资产 → 交叉核对 → 产出结构化清单」的审计任务，第一个落地任务是 366 条译者手记的「承诺-履行」审计。

**Architecture:** 三层——`agent_tools.py` 领域**只读**工具层（纯函数 + MCP 形状 schema + 注册表，同时提供 CLI 子命令）；`api_client.py` 扩展 function calling 并把守卫从「禁一切 tools」收紧为「只允许调用方白名单内的 function、`web_search` 字面量仍全禁」；`agent_loop.py` 有界工具循环；`audit_notes_promises.py` 固定流程任务。工具面全只读，唯一写操作（写报告）由任务层执行、不经过模型。

**Tech Stack:** Python ≥3.12（uv venv）、pytest、pyyaml、stdlib urllib。零新增依赖。

## Global Constraints

- spec：`docs/superpowers/specs/2026-08-02-deepseek-audit-capability-design.md`。
- **工具面全只读**（spec §1.2）：`agent_tools` 不含任何写操作。这是不可动摇的约束——它是自建 loop 的安全性来源。
- **守卫收紧而非删除**（spec §2.2）：`tools` 只允许 `type=="function"` 且名字在调用方白名单内；原始 JSON 串**不得含 `web_search` 字面量**（历史上该断言捕获过 `builtin_tools` 改名绕过，必须保留）；`tools/ayano_test.py` **继续一个 tool 都不发**。
- **「无法判断」是一等公民**（spec §4.4）：不得强迫二元判定；报告顶部须显示其占比。
- **判定锚定可复算的字面事实**（spec §5.3）：依据行 id + 原文/译文内容。CoT 可留痕，**不得作为判定依据**。
- **⚠ 生产会话正在同一工作树并行跑 SEG-2**：只 `git add` 显式路径，禁止 `git add -A`/`git add .`；绝不碰 `pilot/lanes/`（车道数据）、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`、`docs/superpowers/plans/translate-seg*.md`。
- `lua_scripts/`、`png/`、`analysis/`、`skeleton/`、`data/batches.jsonl` 只读。
- `tools/` 惯例：文件头 docstring、`sys.path.insert(0, …parent.parent)`、从 `tools.pipelib` 取 `REPO/DATA/read_jsonl/dumps`、`main(argv=None)` + `raise SystemExit(main())`；纯 stdlib+pyyaml。
- API key 绝不入库；单测一律零真实网络（注入 `stream_transport`）。
- commit 规范 `type: 中文摘要`；每次提交前 `uv run pytest -q` 全绿。当前基线 **354 passed**（HEAD `573e22c`）。

---

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

### Task 2: `api_client` 支持 function tools（含守卫收紧与线格式探针）

**Files:**
- Modify: `tools/api_client.py`
- Test: `tests/test_api_client.py`（追加；**既有断言不得放宽**）

**Interfaces:**
- Consumes: 既有 `chat(messages, *, provider, model, temperature, max_tokens, purpose, stream_transport, ledger_path, api_key, timeout, retries, sleeper, effort, on_delta) -> dict`；`_consume(events, on_delta)`（返回 `prog` dict，终止事件时取 `data["response"]["usage"]`）；`_split_messages(messages) -> (instructions, turns)`。
- Produces: `chat()` 新增两个关键字参数 `tools=None`、`allowed_tool_names=None`；返回 dict 新增两个键 `function_calls: list[dict]`、`output_items: list[dict]`。Task 3 消费。

- [ ] **Step 1: 线格式探针（真实请求，必须先做）**

**DeepSeek Responses API 的 function calling 线格式文档没写**，不要照 OpenAI 惯例假设。先测：

```bash
cat > /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/probe_tools.py <<'PY'
"""探 Responses API function calling 的实际线格式：事件序列 + 终止事件里的 output 形状。"""
import json, sys, urllib.request
sys.path.insert(0, "/Users/fotile96/Zndnovel")
import os
from tools.api_client import load_env, PROVIDERS, iter_sse_events
key = os.environ.get("DEEPSEEK_API_KEY") or load_env().get("DEEPSEEK_API_KEY")
payload = {
    "model": "deepseek-v4-flash", "stream": True, "max_output_tokens": 2048,
    "instructions": "你可以调用工具。需要时就调用，不要猜。",
    "input": [{"role": "user", "content": "第 11 号台词的日文原文是什么？用工具查。"}],
    "tools": [{"type": "function", "name": "get_lines",
               "description": "取若干 id 的日文原文与中文译文",
               "parameters": {"type": "object",
                              "properties": {"ids": {"type": "array",
                                                     "items": {"type": "integer"}}},
                              "required": ["ids"]}}],
}
req = urllib.request.Request(PROVIDERS["deepseek"]["url"],
                             data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "Authorization": f"Bearer {key}"}, method="POST")
seen = []
with urllib.request.urlopen(req, timeout=300) as resp:
    for etype, data in iter_sse_events(resp):
        seen.append(etype)
        if etype.startswith("response.function_call") or etype in (
                "response.output_item.added", "response.output_item.done",
                "response.completed", "response.incomplete", "response.failed"):
            print("==", etype)
            print(json.dumps(data, ensure_ascii=False)[:900])
print("\n事件序列：", seen)
PY
uv run python /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/probe_tools.py
```

**把实际输出完整抄进报告**，特别是：①`function_call` 项出现在哪个事件、字段名是什么（`call_id`? `id`? `name`? `arguments` 是字符串还是对象）；②终止事件的 `response.output` 数组形状；③继续对话时该往 `input` 里放什么（若模型未在响应里提示，按 OpenAI Responses 惯例试 `{"type":"function_call_output","call_id":…,"output":…}` 并在 Task 3 的探针里验证）。

**若探针显示 DeepSeek 不支持或形状迥异**：如实报告并**停下**，不要照假设写解析代码——这会让 Task 3 建在沙上。

- [ ] **Step 2: 写失败测试**

在 `tests/test_api_client.py` 追加（沿用该文件既有的 `_sse_lines()`/`_FakeResp` 夹具风格；`_sse_lines_with_tool_call()` 按 Step 1 探到的真实事件序列构造）：

```python
def test_tools_are_sent_when_whitelisted(tmp_path, monkeypatch):
    captured = {}

    def fake_transport(url, headers, payload):
        captured["payload"] = payload
        captured["raw"] = json.dumps(payload, ensure_ascii=False)
        yield from _events()

    tools = [{"type": "function", "name": "get_lines", "description": "d",
              "parameters": {"type": "object", "properties": {}}}]
    chat([{"role": "user", "content": "hi"}], api_key="sk-test",
         stream_transport=fake_transport, ledger_path=tmp_path / "l.jsonl",
         tools=tools, allowed_tool_names={"get_lines"})
    assert captured["payload"]["tools"] == tools
    assert "web_search" not in captured["raw"]


def test_non_function_tool_type_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="function"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=lambda *a: iter(()), ledger_path=tmp_path / "l.jsonl",
             tools=[{"type": "web_search"}], allowed_tool_names={"get_lines"})


def test_tool_name_outside_whitelist_is_rejected(tmp_path):
    with pytest.raises(SystemExit, match="白名单"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=lambda *a: iter(()), ledger_path=tmp_path / "l.jsonl",
             tools=[{"type": "function", "name": "rm_rf",
                     "parameters": {"type": "object", "properties": {}}}],
             allowed_tool_names={"get_lines"})


def test_tools_require_explicit_whitelist(tmp_path):
    """不给白名单就传 tools —— 拒绝。防止「忘了传白名单」变成事实上的无限制。"""
    with pytest.raises(SystemExit, match="白名单"):
        chat([{"role": "user", "content": "hi"}], api_key="sk-test",
             stream_transport=lambda *a: iter(()), ledger_path=tmp_path / "l.jsonl",
             tools=[{"type": "function", "name": "get_lines",
                     "parameters": {"type": "object", "properties": {}}}])
```

（`_events()` 是该文件里已有的「把 `_sse_lines()` 转成 (etype, data) 迭代器」的辅助；若名字不同，用该文件实际的那个。）

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_api_client.py -v -k "tool"`
Expected: 新增四条 FAIL（`chat() got an unexpected keyword argument 'tools'`）；**既有的 `test_payload_never_sends_tools_or_web_search` 必须仍然 PASS**。

- [ ] **Step 4: 实现**

`tools/api_client.py` 四处改动：

(a) 新增校验函数（放在 `chat()` 之前）：

```python
def _validate_tools(tools, allowed_tool_names):
    """守卫（spec §2.2）：由「禁一切 tools」收紧为「只允许白名单内的 function」。

    ⚠ 不要放宽这里。Responses API 内置服务端 web_search——彩野测试里一旦启用即
    灾难：受试模型可上网查《セカンドノベル》剧情，不看译文也能答对，测试静默失效。
    历史上原始 JSON 串级的 `web_search` 子串断言捕获过 `builtin_tools` 这类改名
    绕过，那条断言在 test_payload_never_sends_tools_or_web_search 里，保留不动。
    """
    if not tools:
        return
    if not allowed_tool_names:
        raise SystemExit("传 tools 必须同时给 allowed_tool_names 白名单（缺省即拒绝）")
    for t in tools:
        if t.get("type") != "function":
            raise SystemExit(f"只允许 type=function 的工具，收到 {t.get('type')!r}")
        if t.get("name") not in allowed_tool_names:
            raise SystemExit(f"工具 {t.get('name')!r} 不在白名单内")
```

(b) `chat()` 签名新增 `tools=None, allowed_tool_names=None`；在构造 payload 前调用 `_validate_tools(tools, allowed_tool_names)`；`tools` 非空时写进 payload（`payload["tools"] = tools`）。**`tools` 为空时 payload 里不得出现该键**（既有断言靠这一点）。

(c) `_consume()` 在终止事件分支里追加捕获 output items：

```python
prog["output_items"] = resp.get("output") or []
```
并在 `prog` 初始化处加 `"output_items": []`。**其余分支一律不动**（多 part 追加逻辑、异常挂 partial 等经过三轮评审，不要顺手改）。

(d) `chat()` 的返回 dict 追加两个键：`"output_items": prog.get("output_items", [])`、`"function_calls": [it for it in prog.get("output_items", []) if it.get("type") == "function_call"]`。

**字段名以 Step 1 探针实测为准**——若 DeepSeek 的 function_call 项字段名与假设不同，按实测改，并在注释里写明实测出处。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_api_client.py -v` → 全 passed（含既有那条禁 tools 断言）。

- [ ] **Step 6: 变异自检**

临时把 `_validate_tools` 里的白名单检查注释掉，确认 `test_tool_name_outside_whitelist_is_rejected` 变红；再把 `type != "function"` 检查注释掉，确认对应用例变红。恢复后全绿。**把变异结果写进报告**——这道守卫是防作弊闸，不能是摆设。

- [ ] **Step 7: 全量测试 + commit**

Run: `uv run pytest -q` → 365 passed。

```bash
git add tools/api_client.py tests/test_api_client.py
git commit -m "feat: api_client 支持白名单内的 function tools（守卫收紧非删除）"
```

---

### Task 3: 有界工具循环 `tools/agent_loop.py`

**Files:**
- Create: `tools/agent_loop.py`
- Test: `tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `tools.api_client.chat(..., tools=, allowed_tool_names=) -> dict`（含 `content`/`function_calls`/`output_items`/`reasoning_text`/token 计数）；`tools.agent_tools.TOOLS`、`tool_schemas()`、`call_tool(name, args, lane_dir)`。
- Produces: `run_with_tools(messages, *, tool_names=None, max_rounds=6, lane_dir=None, **chat_kw) -> dict`，返回 `{content, rounds, tool_calls: list[{name,args,result_summary}], stopped_reason, reasoning_text, prompt_tokens, completion_tokens}`。`stopped_reason ∈ {"finished","max_rounds"}`。Task 5 消费。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_agent_loop.py`：

```python
"""有界工具循环：模型要调工具就代它调，结果回灌，轮次有上限且到顶不静默。"""
import pytest

from tools.agent_loop import run_with_tools


def _chat_stub(script):
    """按脚本依次返回预设的 chat() 结果。"""
    calls = {"n": 0, "payloads": []}

    def fake_chat(messages, **kw):
        calls["payloads"].append((messages, kw))
        r = script[calls["n"]]
        calls["n"] += 1
        return r
    return fake_chat, calls


def test_single_round_without_tool_calls(monkeypatch):
    fake, calls = _chat_stub([{"content": "答案", "function_calls": [],
                              "reasoning_text": "想了想", "prompt_tokens": 10,
                              "completion_tokens": 2}])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    out = run_with_tools([{"role": "user", "content": "问"}])
    assert out["content"] == "答案" and out["rounds"] == 1
    assert out["tool_calls"] == [] and out["stopped_reason"] == "finished"


def test_tool_call_is_executed_and_fed_back(monkeypatch, tmp_path):
    fake, calls = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c1", "name": "get_anchor",
             "arguments": '{"id": 11}'}],
         "reasoning_text": "", "prompt_tokens": 10, "completion_tokens": 1},
        {"content": "它是锚点", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": 20, "completion_tokens": 3},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    monkeypatch.setattr("tools.agent_loop.call_tool",
                        lambda name, args, lane_dir=None: {"is_anchor": True, "id": args["id"]})
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["rounds"] == 2 and out["content"] == "它是锚点"
    assert out["tool_calls"][0]["name"] == "get_anchor"
    assert out["tool_calls"][0]["args"] == {"id": 11}
    assert out["stopped_reason"] == "finished"
    # 第二轮的 messages 必须带上工具结果
    second_messages = calls["payloads"][1][0]
    assert any("is_anchor" in str(m.get("content", "")) for m in second_messages)


def test_max_rounds_stops_loudly(monkeypatch):
    forever = {"content": "", "function_calls": [
        {"type": "function_call", "call_id": "c", "name": "get_anchor",
         "arguments": '{"id": 1}'}],
        "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr("tools.agent_loop.chat", lambda messages, **kw: dict(forever))
    monkeypatch.setattr("tools.agent_loop.call_tool",
                        lambda name, args, lane_dir=None: {"ok": True})
    out = run_with_tools([{"role": "user", "content": "问"}],
                         tool_names=["get_anchor"], max_rounds=3)
    assert out["rounds"] == 3 and out["stopped_reason"] == "max_rounds"


def test_bad_tool_arguments_do_not_crash_the_loop(monkeypatch):
    fake, _ = _chat_stub([
        {"content": "", "function_calls": [
            {"type": "function_call", "call_id": "c1", "name": "get_anchor",
             "arguments": "{不是合法 JSON"}],
         "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1},
        {"content": "算了", "function_calls": [], "reasoning_text": "",
         "prompt_tokens": 2, "completion_tokens": 1},
    ])
    monkeypatch.setattr("tools.agent_loop.chat", fake)
    out = run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert out["stopped_reason"] == "finished"
    assert "error" in out["tool_calls"][0]["result_summary"]


def test_only_registry_names_reach_chat(monkeypatch):
    """白名单单一来源：loop 传给 chat 的 allowed_tool_names 必须来自注册表。"""
    from tools.agent_tools import TOOLS
    seen = {}

    def fake_chat(messages, **kw):
        seen.update(kw)
        return {"content": "ok", "function_calls": [], "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr("tools.agent_loop.chat", fake_chat)
    run_with_tools([{"role": "user", "content": "问"}], tool_names=["get_anchor"])
    assert seen["allowed_tool_names"] <= set(TOOLS)
    assert {t["name"] for t in seen["tools"]} == {"get_anchor"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_agent_loop.py -v` → FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

写入 `tools/agent_loop.py`：

```python
"""有界工具循环：模型要调工具就代它调，把结果回灌进下一轮，轮次有硬上限。

**为什么敢自建**：工具面（tools/agent_tools.py）全只读，唯一的写操作（写报告）
由任务层执行、不经过模型。所以循环跑飞的最坏后果是报告不完整，而不是仓库被
改坏（spec §1.2）。

**到顶不静默**：`max_rounds` 用尽时返回 `stopped_reason="max_rounds"`，调用方
必须能看出「这次是被截断的」——静默截断会让下游把半截结论当完整结论。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.api_client import chat
from tools.agent_tools import TOOLS, call_tool, tool_schemas

DEFAULT_MAX_ROUNDS = 6
RESULT_SUMMARY_CHARS = 2000


def _summarize(obj):
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= RESULT_SUMMARY_CHARS else s[:RESULT_SUMMARY_CHARS] + "…（已截断）"


def run_with_tools(messages, *, tool_names=None, max_rounds=DEFAULT_MAX_ROUNDS,
                   lane_dir=None, **chat_kw) -> dict:
    """带工具的多轮对话。`tool_names` 省略即不给工具（退化为单轮 chat）。"""
    names = list(tool_names or [])
    unknown = [n for n in names if n not in TOOLS]
    if unknown:
        raise SystemExit(f"未注册的工具名：{unknown}")
    schemas = [s for s in tool_schemas() if s["name"] in names]
    convo = list(messages)
    tool_calls, rounds = [], 0
    last = {"content": "", "reasoning_text": "", "prompt_tokens": 0, "completion_tokens": 0}
    pin = pout = 0
    while rounds < max_rounds:
        rounds += 1
        kw = dict(chat_kw)
        if schemas:
            kw["tools"] = schemas
            kw["allowed_tool_names"] = set(TOOLS)
        last = chat(convo, **kw)
        pin += last.get("prompt_tokens", 0) or 0
        pout += last.get("completion_tokens", 0) or 0
        fcs = last.get("function_calls") or []
        if not fcs:
            return {"content": last.get("content", ""), "rounds": rounds,
                    "tool_calls": tool_calls, "stopped_reason": "finished",
                    "reasoning_text": last.get("reasoning_text", ""),
                    "prompt_tokens": pin, "completion_tokens": pout}
        # 代模型执行工具，把结果作为一条 user 轮次回灌（不依赖 function_call_output
        # 的特定线格式——用纯文本回灌在任何兼容层上都成立，代价是少一点结构化）。
        convo = convo + [{"role": "assistant", "content": last.get("content", "") or "（调用工具）"}]
        for fc in fcs:
            name = fc.get("name")
            raw = fc.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
                result = call_tool(name, args, lane_dir=lane_dir)
                summary = _summarize(result)
            except Exception as exc:
                args = {"_raw": raw}
                summary = _summarize({"error": f"{type(exc).__name__}: {exc}"})
            tool_calls.append({"name": name, "args": args, "result_summary": summary})
            convo = convo + [{"role": "user",
                              "content": f"工具 {name} 的返回：\n{summary}"}]
    return {"content": last.get("content", ""), "rounds": rounds,
            "tool_calls": tool_calls, "stopped_reason": "max_rounds",
            "reasoning_text": last.get("reasoning_text", ""),
            "prompt_tokens": pin, "completion_tokens": pout}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="带工具的一次性提问（调试用）")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--tools", default="", help="逗号分隔的工具名，空则不给工具")
    ap.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    ap.add_argument("--lane-dir", default=None)
    a = ap.parse_args(argv)
    names = [t for t in a.tools.split(",") if t]
    out = run_with_tools([{"role": "user", "content": a.prompt}], tool_names=names,
                         max_rounds=a.max_rounds, lane_dir=a.lane_dir,
                         purpose="agent-loop-cli")
    print(out["content"])
    print(f"\n[rounds={out['rounds']} stopped={out['stopped_reason']} "
          f"tools={[c['name'] for c in out['tool_calls']]}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**设计说明（写进 docstring 或注释）**：工具结果用**纯文本 user 轮次**回灌，而不是 `function_call_output` 结构化项。理由：Task 2 的探针若显示 DeepSeek 的结构化回灌形状与 OpenAI 惯例不同，纯文本方案不受影响；代价是模型少一点结构提示。**若 Task 2 探针确认结构化形状可用且稳定，可在报告里建议改用结构化回灌，但本任务不改。**

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_agent_loop.py -v` → 5 passed。

- [ ] **Step 5: 真实调用冒烟**

```bash
uv run python tools/agent_loop.py --prompt "第 8478 号台词是不是伏笔锚点？如果是，它的中文定译是什么？用工具查，不要猜。" --tools get_anchor,get_lines
```
Expected: 模型调用 `get_anchor`，回答含「彩野同学」（8478 是 v7 补的サクラ汉字呼名锚点）。**把实际的 rounds / 调用了哪些工具 / 回答原文抄进报告**——这是 loop 的第一次真实验证。若模型不调工具而直接猜，也如实记录（那说明提示词需要更强的「必须用工具」约束）。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 370 passed。

```bash
git add tools/agent_loop.py tests/test_agent_loop.py
git commit -m "feat: 有界工具循环（只读工具面 + 到顶不静默）"
```

---

### Task 4: 手记审计步骤 1 —— 硬承诺抽取

**Files:**
- Create: `tools/audit_notes_promises.py`
- Test: `tests/test_audit_notes_promises.py`

**Interfaces:**
- Consumes: `tools.cluster_notes.parse_notes`；`tools.agent_loop.run_with_tools`。
- Produces: `PROMISE_SYS`（步骤 1 的系统提示词常量）、`extract_promises(proposal, *, runner=None) -> list[dict]`（每项 `{kind, ids, quote}`）、`ID_RE`（从提案正文抽 id 的正则）、`prewire_ids(proposal) -> list[int]`。Task 5 消费。

- [ ] **Step 1: 写失败测试**

写入 `tests/test_audit_notes_promises.py`：

```python
"""手记「承诺-履行」审计：只审硬承诺，软倾向不审（spec §4.2）。"""
import json

from tools.audit_notes_promises import extract_promises, prewire_ids

HARD = {"chapter": "s1s", "batch": 4, "num": 1,
        "title": "寝癖 → 睡翘的头发",
        "body": "- id 7327、7329、7332（本批 8 处）\n"
                "- 理由：两处措辞必须能对上。本批已按上述译法统一。\n"}
SOFT = {"chapter": "s1s", "batch": 4, "num": 2,
        "title": "菜单名的拉丁形态需要一条形态判据",
        "body": "- id 6632\n- 建议：立通则——片假名形态中文化。\n"}


def _runner(payload):
    def fake(messages, **kw):
        return {"content": json.dumps(payload, ensure_ascii=False), "rounds": 1,
                "tool_calls": [], "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    return fake


def test_prewire_ids_reads_ids_from_body():
    assert prewire_ids(HARD) == [7327, 7329, 7332]
    assert prewire_ids(SOFT) == [6632]


def test_extract_hard_promise():
    out = extract_promises(HARD, runner=_runner(
        {"promises": [{"kind": "已统一", "ids": [7327, 7329, 7332],
                       "quote": "本批已按上述译法统一"}]}))
    assert len(out) == 1 and out[0]["kind"] == "已统一"
    assert out[0]["ids"] == [7327, 7329, 7332]


def test_soft_suggestion_yields_no_promise():
    out = extract_promises(SOFT, runner=_runner({"promises": []}))
    assert out == []


def test_malformed_model_output_is_treated_as_no_promise():
    """模型吐了非 JSON —— 视为无承诺并留痕，不得让整轮审计崩掉。"""
    out = extract_promises(HARD, runner=_runner_raw("这不是 JSON"))
    assert out == []


def _runner_raw(text):
    def fake(messages, **kw):
        return {"content": text, "rounds": 1, "tool_calls": [],
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    return fake
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_audit_notes_promises.py -v` → FAIL（模块不存在）。

- [ ] **Step 3: 写实现（步骤 1 部分）**

写入 `tools/audit_notes_promises.py`：

```python
"""手记「承诺-履行」审计（spec §4）。

审的是**决策的执行**而非文本质量：手记里记着大量显式翻译决定（「照原样保留」
「须逐字一致」「不消歧」「已按 X 统一」），从来没有人回头查过它们是否真被
执行——甚至可能在后续批次被无意识违反。机器校验器结构上做不到这件事。

**只审硬承诺，不审软倾向**（spec §4.2）：「建议」「宜」「可考虑」本来就没许诺
执行，审它会制造大量伪违约，把真违约淹掉——与本项目反复吃过亏的「噪声掩盖
信号」是同一种失败。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.agent_loop import run_with_tools

ID_RE = re.compile(r"\bid\s*([0-9０-９、,，\s]+)")
NUM_RE = re.compile(r"[0-9]+")

PROMISE_SYS = """你在审计一份翻译项目的译者手记。你的任务**只有一个**：从提案正文里
找出**已经作出的硬承诺**，不要找建议。

算硬承诺的（举例）：「本批已按 X 统一」「照原样保留待判」「须逐字一致」「此处保留
歧义」「不消歧」「已按上述译法统一」——它们描述的是**已经决定并执行的事**。

**不算**硬承诺的：「建议」「宜」「可考虑」「请一并裁决」「拟」——这些只是倾向，没有
许诺执行。把它们当承诺会制造伪违约。

只输出 JSON，不要任何其他文字：
{"promises": [{"kind": "一句话概括承诺类型", "ids": [涉及的消息 id], "quote": "提案里的原话"}]}
找不到硬承诺就输出 {"promises": []}。"""


def prewire_ids(proposal):
    """从提案正文里抽出显式写明的 id（提案格式如 `- id 7327、7329、7332`）。"""
    ids = []
    for m in ID_RE.finditer(proposal.get("body", "")):
        ids += [int(x) for x in NUM_RE.findall(m.group(1))]
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _ask_json(runner, messages, **kw):
    """跑一轮并把结果解析成 dict；非 JSON 视为空结果并留痕，不让整轮审计崩掉。"""
    fn = runner or run_with_tools
    res = fn(messages, **kw)
    text = (res.get("content") or "").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text), res
    except Exception:
        return {}, res


def extract_promises(proposal, *, runner=None):
    """步骤 1（无工具）：从单条提案抽硬承诺。"""
    body = (f"【提案标题】{proposal['title']}\n【提案正文】\n{proposal['body']}\n"
            f"【正文里显式写明的 id】{prewire_ids(proposal)}")
    data, _ = _ask_json(runner, [{"role": "system", "content": PROMISE_SYS},
                                 {"role": "user", "content": body}],
                        purpose=f"audit-promise-extract:{proposal['chapter']}"
                                f":b{proposal['batch']}:#{proposal['num']}")
    out = []
    for p in (data.get("promises") or []):
        ids = [int(i) for i in (p.get("ids") or []) if str(i).isdigit() or isinstance(i, int)]
        out.append({"kind": p.get("kind", ""), "ids": ids or prewire_ids(proposal),
                    "quote": p.get("quote", "")})
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_audit_notes_promises.py -v` → 4 passed。

- [ ] **Step 5: 全量测试 + commit**

Run: `uv run pytest -q` → 374 passed。

```bash
git add tools/audit_notes_promises.py tests/test_audit_notes_promises.py
git commit -m "feat: 手记审计步骤 1——硬承诺抽取（软倾向不审）"
```

---

### Task 5: 手记审计步骤 2/3 —— 履行核对与报告

**Files:**
- Modify: `tools/audit_notes_promises.py`
- Test: `tests/test_audit_notes_promises.py`（追加）

**Interfaces:**
- Consumes: Task 4 的 `extract_promises`/`prewire_ids`；`tools.agent_tools.call_tool`（预拼上下文用 `get_lines`）；`tools.agent_loop.run_with_tools`（工具兜底）。
- Produces: `VERIFY_SYS`；`verify_promise(promise, proposal, *, lane_dir=None, runner=None) -> dict`（`{verdict, evidence_ids, reason, used_tools}`，`verdict ∈ {"已履行","未履行","无法判断"}`）；`render_report(results) -> str`；`main(argv=None)`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_audit_notes_promises.py` 追加：

```python
def test_verify_uses_prewired_context_when_ids_present(monkeypatch):
    """id 齐全时走预拼上下文，不开工具（便宜、可预测）。"""
    from tools import audit_notes_promises as A
    seen = {}

    def fake_runner(messages, **kw):
        seen["tool_names"] = kw.get("tool_names")
        seen["user"] = messages[-1]["content"]
        return {"content": json.dumps({"verdict": "已履行", "evidence_ids": [7327],
                                       "reason": "译文含睡翘"}, ensure_ascii=False),
                "rounds": 1, "tool_calls": [], "stopped_reason": "finished",
                "reasoning_text": "", "prompt_tokens": 1, "completion_tokens": 1}
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {
        "lines": [{"id": 7327, "jp": "寝癖", "zh": "头发睡翘了", "chapter": "s1s"}]})
    out = A.verify_promise({"kind": "已统一", "ids": [7327], "quote": "已统一"},
                           HARD, runner=fake_runner)
    assert out["verdict"] == "已履行" and out["used_tools"] is False
    assert not seen["tool_names"]          # 未给工具
    assert "头发睡翘了" in seen["user"]     # 上下文已预拼


def test_verify_opens_tools_when_ids_missing(monkeypatch):
    """id 缺失时才给工具兜底。"""
    from tools import audit_notes_promises as A
    seen = {}

    def fake_runner(messages, **kw):
        seen["tool_names"] = kw.get("tool_names")
        return {"content": json.dumps({"verdict": "无法判断", "evidence_ids": [],
                                       "reason": "找不到对应行"}, ensure_ascii=False),
                "rounds": 2, "tool_calls": [{"name": "search_lines"}],
                "stopped_reason": "finished", "reasoning_text": "",
                "prompt_tokens": 1, "completion_tokens": 1}
    out = A.verify_promise({"kind": "保留歧义", "ids": [], "quote": "保留歧义"},
                           {"chapter": "s1s", "batch": 4, "num": 9, "title": "t",
                            "body": "本段 8 处"}, runner=fake_runner)
    assert out["used_tools"] is True
    assert set(seen["tool_names"]) == {"get_lines", "search_lines", "get_anchor"}


def test_unparseable_verdict_becomes_cannot_tell(monkeypatch):
    """模型没给合法 JSON —— 记「无法判断」，绝不硬判成「已履行」（spec §4.4）。"""
    from tools import audit_notes_promises as A
    monkeypatch.setattr(A, "call_tool", lambda name, args, lane_dir=None: {"lines": []})
    out = A.verify_promise({"kind": "x", "ids": [1], "quote": "q"}, HARD,
                           runner=_runner_raw("我觉得应该没问题"))
    assert out["verdict"] == "无法判断"


def test_report_puts_unfulfilled_first_and_shows_cannot_tell_ratio():
    from tools.audit_notes_promises import render_report
    md = render_report([
        {"proposal": HARD, "promise": {"kind": "a", "quote": "q1"},
         "verdict": "已履行", "evidence_ids": [1], "reason": "r1", "used_tools": False},
        {"proposal": HARD, "promise": {"kind": "b", "quote": "q2"},
         "verdict": "未履行", "evidence_ids": [2], "reason": "r2", "used_tools": False},
        {"proposal": HARD, "promise": {"kind": "c", "quote": "q3"},
         "verdict": "无法判断", "evidence_ids": [], "reason": "r3", "used_tools": True},
    ])
    assert md.index("未履行") < md.index("已履行")
    assert "无法判断占比" in md and "33" in md
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_audit_notes_promises.py -v -k "verify or report"` → FAIL。

- [ ] **Step 3: 实现步骤 2/3**

在 `tools/audit_notes_promises.py` 追加：

```python
from tools.agent_tools import call_tool

VERIFY_SYS = """你在核对一条**已经作出的翻译承诺**是否真的被执行。

给你的材料是：承诺原话、以及相关行的日文原文与现行中文译文。

判定只能是三者之一：
- **已履行**：译文确实按承诺处理了
- **未履行**：译文与承诺矛盾
- **无法判断**：材料不足以判定

**「无法判断」是正当答案，不要为了给个结论而硬判。** 把不确定硬判成「已履行」
比不判更有害。

判定必须锚定**可复算的字面事实**——引用具体的行 id 与原文/译文内容。不要用
你的推理过程本身当依据。

只输出 JSON：{"verdict": "已履行|未履行|无法判断", "evidence_ids": [行 id], "reason": "一句话"}"""

TOOL_NAMES = ["get_lines", "search_lines", "get_anchor"]
VALID_VERDICTS = {"已履行", "未履行", "无法判断"}


def verify_promise(promise, proposal, *, lane_dir=None, runner=None):
    """步骤 2：预拼为主、工具兜底。"""
    ids = promise.get("ids") or []
    used_tools = not ids
    if ids:
        lines = call_tool("get_lines", {"ids": ids}, lane_dir=lane_dir)["lines"]
        ctx = "\n".join(
            f"id {r['id']}（{r['chapter']}）\n  原文：{r['jp']}\n  译文：{r['zh']}"
            for r in lines)
        kw = {}
    else:
        ctx = "（提案未写明 id，请用工具自行查找相关行）"
        kw = {"tool_names": TOOL_NAMES, "lane_dir": lane_dir}
    user = (f"【承诺】{promise.get('kind')}：{promise.get('quote')}\n"
            f"【出处】{proposal['chapter']} b{proposal['batch']} #{proposal['num']}"
            f" —— {proposal['title']}\n【相关行】\n{ctx}")
    data, res = _ask_json(runner, [{"role": "system", "content": VERIFY_SYS},
                                   {"role": "user", "content": user}],
                          purpose=f"audit-promise-verify:{proposal['chapter']}"
                                  f":b{proposal['batch']}:#{proposal['num']}",
                          **kw)
    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        verdict = "无法判断"
    return {"verdict": verdict,
            "evidence_ids": [i for i in (data.get("evidence_ids") or []) if isinstance(i, int)],
            "reason": data.get("reason", "（模型未给出可解析的判定）"),
            "used_tools": used_tools or bool(res.get("tool_calls")),
            "reasoning_text": res.get("reasoning_text", "")}


ORDER = {"未履行": 0, "无法判断": 1, "已履行": 2}


def render_report(results):
    """步骤 3（无模型）：未履行优先，无法判断单列，顶部显示可信度指标。"""
    n = len(results)
    cnt = {v: sum(1 for r in results if r["verdict"] == v) for v in VALID_VERDICTS}
    pct = (cnt["无法判断"] * 100 // n) if n else 0
    lines = [f"# 手记「承诺-履行」审计报告（{n} 条硬承诺）", "",
             f"- 未履行 **{cnt['未履行']}** ｜ 已履行 {cnt['已履行']} ｜ 无法判断 {cnt['无法判断']}",
             f"- **无法判断占比 {pct}%** —— 该比例本身是可信度指标，偏高说明材料或判据不足", ""]
    for r in sorted(results, key=lambda r: ORDER[r["verdict"]]):
        p, pr = r["proposal"], r["promise"]
        lines += [f"## [{r['verdict']}] {p['chapter']} b{p['batch']} #{p['num']} · {pr.get('kind')}",
                  f"- 承诺原话：{pr.get('quote')}",
                  f"- 依据行：{r['evidence_ids'] or '（无）'}",
                  f"- 理由：{r['reason']}",
                  f"- 用了工具：{'是' if r['used_tools'] else '否'}", ""]
    return "\n".join(lines)


def main(argv=None):
    import argparse
    from tools.cluster_notes import parse_notes
    ap = argparse.ArgumentParser(description="手记「承诺-履行」审计")
    ap.add_argument("--lane-dir", default="pilot/lanes/opus")
    ap.add_argument("--chapter", default=None, help="只审某一章，省略则全部")
    ap.add_argument("--limit", type=int, default=0, help="只审前 N 条提案（0=不限）")
    ap.add_argument("--out", default="work/out/audit-notes-promises.md")
    a = ap.parse_args(argv)
    lane = Path(a.lane_dir)
    props = []
    for p in sorted((lane / "data" / "notes").glob("*.md")):
        if a.chapter and p.stem != a.chapter:
            continue
        props += parse_notes(p.read_text(encoding="utf-8"), p.stem)
    if a.limit:
        props = props[:a.limit]
    results = []
    for prop in props:
        for pr in extract_promises(prop):
            r = verify_promise(pr, prop, lane_dir=lane)
            r.update({"proposal": prop, "promise": pr})
            results.append(r)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(results), encoding="utf-8")
    print(f"审计报告已写 {out}（{len(props)} 条提案 → {len(results)} 条硬承诺）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_audit_notes_promises.py -v` → 8 passed。

- [ ] **Step 5: 小样真实跑**

```bash
uv run python tools/audit_notes_promises.py --chapter s0f --limit 5 --out /private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/audit-smoke.md
```
把报告全文抄进执行报告。**观察三件事并如实记录**：①抽出的硬承诺是否确实是硬承诺（有没有把「建议」当承诺）；②判定的依据行是否真的支持结论；③「无法判断」的比例。

- [ ] **Step 6: 全量测试 + commit**

Run: `uv run pytest -q` → 378 passed。

```bash
git add tools/audit_notes_promises.py tests/test_audit_notes_promises.py
git commit -m "feat: 手记审计步骤 2/3——履行核对与报告（无法判断是一等公民）"
```

---

### Task 6: 播种检验（硬门）+ 全量跑

**Files:**
- Create: `tests/test_audit_seeded.py`
- Create: `.superpowers/sdd/<本计划工作台>/audit-notes-promises-firstrun.md`（首跑报告，`git add -f`）

**Interfaces:**
- Consumes: Task 4/5 的 `extract_promises`/`verify_promise`。
- Produces: 播种检验用例；首次全量跑的报告。

- [ ] **Step 1: 写播种检验**

写入 `tests/test_audit_seeded.py`。**这是 spec §5.1 的硬门：播种未被检出即视为不可用，不得以「其余结论看起来合理」放行。**

三类承诺形态各造一条「已知被违反」的合成数据（**用合成 ledger/译文，不依赖生产会话正在写的车道数据**），断言 `verify_promise` 报「未履行」：

```python
"""播种检验（spec §5.1 硬门）：人为构造已知被违反的承诺，审计必须报出未履行。

不通过即视为审计器不可用——本项目反复吃过「恒绿关卡比没有关卡更危险」的亏。
本测试用注入 runner，不发真实网络；它验的是**判定路径与阈值语义**，模型判断
质量另由 Task 6 的人工抽核负责。
"""
```

三条用例的构造要点（实现者按此写）：
1. **「已统一」被违反**：承诺说「本批已统一为 X」，而预拼进上下文的译文里有一行不是 X。注入 runner 模拟模型正确识别 → 断言 `verdict == "未履行"`。
2. **「须逐字一致」被违反**：两行 jp 相同、zh 不同。
3. **「照原样保留」被违反**：jp 有细微书写差异（`人の事`/`人のこと`），zh 被压成同一句——**这是真实存在的案例（b37 id 9441/9460/9483）**，可直接用真实数据构造。

再加一条**反向**用例：承诺确实被履行时不得报「未履行」。

**注意**：这些用例用注入 runner，所以它们验的是「判定路径是否把模型的判断如实传递并归类」，不是「模型判断得准不准」。后者由 Step 3 的人工抽核负责。**这个区分要写进测试 docstring**，否则下一个人会以为播种检验保证了模型质量。

- [ ] **Step 2: 跑播种检验**

Run: `uv run pytest tests/test_audit_seeded.py -v` → 4 passed。
若有任何一条红，**停止本任务并报告**——不要调整断言去迁就实现。

- [ ] **Step 3: 全量真实跑**

```bash
uv run python tools/audit_notes_promises.py --lane-dir pilot/lanes/opus \
  --out work/out/audit-notes-promises.md
```

预期规模：366 条提案 → 约 100 条硬承诺。**记录**：提案数、硬承诺数、三类判定的分布与「无法判断」占比、总 token 与耗时。

把报告复制一份到工作台并 `git add -f` 入库（`work/` 是 gitignore 的 scratch）。

- [ ] **Step 4: 请用户抽核（硬 gate）**

按 spec §5.2：呈给用户至少 2 条「未履行」与 2 条「无法判断」的完整判定（含承诺原话、依据行的原文与译文、理由），请其确认判据站得住。

**用户未确认前不得声称审计可用。** 用户要求修改则改后重跑。

- [ ] **Step 5: commit**

```bash
git add tests/test_audit_seeded.py
git add -f .superpowers/sdd/<本计划工作台>/audit-notes-promises-firstrun.md
git commit -m "test: 手记审计播种检验（硬门）+ 首次全量跑证据入库"
```

---

## Self-Review 记录

- **Spec 覆盖**：§2 能力层→T2；§3 工具层（含 CLI 面、MCP 不做）→T1；§4 任务层三步→T4/T5；§4.2 只审硬承诺→T4 的 `PROMISE_SYS` 与测试；§4.4「无法判断」一等公民→T5 的 `VALID_VERDICTS` 兜底与报告占比；§5.1 播种检验硬门→T6；§5.2 人工抽核→T6 Step 4；§5.3 判定锚定字面事实→T5 的 `VERIFY_SYS` 与 `evidence_ids`；§1.2 只读约束→T1 的 `test_module_has_no_write_operations`。§0 非目标（MCP/novel 图/runner 抽象）在本计划中均未出现任务，符合。
- **占位符**：无 TBD/TODO。T2 Step 1 与 T6 Step 1 是「先探测/按要点构造」型步骤，已给出完整探针脚本与逐条构造要点（含可直接使用的真实案例 id），属该类任务的合理形态。
- **类型一致性**：`ToolSpec`/`TOOLS`/`call_tool`/`tool_schemas` 在 T1 定义、T2/T3 消费；`run_with_tools` 返回键在 T3 定义、T4/T5 消费（`content`/`tool_calls`/`stopped_reason`/`reasoning_text`）；`verify_promise` 返回键在 T5 定义、T6 消费。测试计数链 354→361→365→370→374→378→382 已核。
- **风险点已内嵌**：T2 Step 1 的「探针形状不符即停」、T2 Step 6 的守卫变异自检、T3 Step 5 的「模型不调工具也要如实记录」、T6 Step 2 的「播种红了就停」、T6 Step 4 的用户硬 gate。
