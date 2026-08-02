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
