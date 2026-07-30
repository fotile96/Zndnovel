import json
from pathlib import Path
from tools.append_forward import run
from tools.pipelib import write_jsonl, read_jsonl, sha256_file, dumps

def _setup(tmp_path, with_pass=True, good_hash=True):
    work, data = tmp_path / "work", tmp_path / "data"
    (work / "out").mkdir(parents=True)
    draft = work / "out" / "batch_7.draft.jsonl"
    write_jsonl(draft, [{"id": 100, "zh": "译A"}, {"id": 101, "zh": "译B"}])
    if with_pass:
        h = sha256_file(draft) if good_hash else "0" * 64
        (work / "out" / "batch_7.pass.json").write_text(dumps({"sha256": h}))
    return work, data

def test_appends_with_metadata(tmp_path):
    work, data = _setup(tmp_path)
    assert run(7, "cc", "claude-x", "sha:abc", 1, ts="2026-07-30T00:00:00Z",
               work=work, data=data) == 0
    rows = read_jsonl(data / "forward.jsonl")
    assert [r["id"] for r in rows] == [100, 101]
    assert rows[0]["backend"] == "cc" and rows[0]["glossary_v"] == 1

def test_refuses_without_pass_marker(tmp_path):
    work, data = _setup(tmp_path, with_pass=False)
    assert run(7, "cc", "m", "c", 1, work=work, data=data) == 2

def test_refuses_on_hash_mismatch(tmp_path):
    work, data = _setup(tmp_path, good_hash=False)
    assert run(7, "cc", "m", "c", 1, work=work, data=data) == 3

def test_refuses_duplicate_batch_and_keeps_file_intact(tmp_path):
    work, data = _setup(tmp_path)
    run(7, "cc", "m", "c", 1, ts="t", work=work, data=data)
    before = (data / "forward.jsonl").read_bytes()
    assert run(7, "cc", "m", "c", 1, ts="t", work=work, data=data) == 4
    assert (data / "forward.jsonl").read_bytes() == before
