import json
from tools.add_patch import add
from tools.recall import find
from tools.pipelib import write_jsonl, read_jsonl

def test_add_patch_appends(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    add(5, "新译", "review", 4, ts="t", data=d / "data")
    add(5, "更新译", "review", 4, ts="t2", data=d / "data")
    rows = read_jsonl(d / "data" / "patches.jsonl")
    assert [r["zh"] for r in rows] == ["新译", "更新译"]

def test_recall_finds_stale_rows(tmp_path):
    d = tmp_path; (d / "data").mkdir()
    write_jsonl(d / "data" / "ledger.jsonl", [
        {"id": 1, "jp": "彼女の手帳を見た", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"},
        {"id": 2, "jp": "無関係の行", "chapter": "s1s", "kind": "narrative",
         "file": "f", "func": "g"}])
    write_jsonl(d / "data" / "forward.jsonl", [
        {"id": 1, "zh": "看了她的手帐", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"},
        {"id": 2, "zh": "无关", "batch": 1, "backend": "cc", "model": "m",
         "ctx": "c", "glossary_v": 1, "ts": "t"}])
    hits = find(term="手帳", glossary_v=2, data=d / "data")
    assert [h["id"] for h in hits] == [1]
