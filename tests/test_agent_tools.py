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
