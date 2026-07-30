import json
from pathlib import Path
from tools.pipelib import dumps, read_jsonl, append_jsonl, write_jsonl, display_width, sha256_file, REPO

def test_dumps_keeps_unicode_and_is_compact():
    assert dumps({"jp": "彩野さん", "n": 1}) == '{"jp":"彩野さん","n":1}'

def test_jsonl_roundtrip_and_append(tmp_path):
    p = tmp_path / "a.jsonl"
    write_jsonl(p, [{"id": 1}, {"id": 2}])
    append_jsonl(p, [{"id": 3}])
    assert [r["id"] for r in read_jsonl(p)] == [1, 2, 3]

def test_display_width_east_asian():
    assert display_width("あa") == 3
    assert display_width("【彩野】「うん」") == 16

def test_sha256_file(tmp_path):
    p = tmp_path / "x.bin"; p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

def test_repo_points_at_project_root():
    assert (REPO / "lua_scripts").is_dir()
