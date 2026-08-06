"""tools/polish_ingest.py：唯一入仓口的单测。

mini 夹具复用 `tools/polish_setup.setup()` 造真正的 `frozen/` 快照（比手搓
目录更可靠，见 task-4/5 brief 的补充说明），只是按测试需要控制 raw/plan.json
内容。全部测试都显式传 `repo=` 隔离到 tmp_path，绝不触碰真实仓库的
`pilot/polish/`。

夹具设计：2 批。
- batch 1：ids 10/11/12（非锁定）+ 13（锁定，anchor）。
- batch 2：ids 20/21/22（非锁定）+ 23（锁定，anchor）。
两批各自的 raw/chA/b{N}.out 基线都是"3 行非锁定 id，逐字照抄 opus，不锁定
id 不出现"——即模型规规矩矩符合契约的形态。plan.json 记两个会话，批 1→会话
1，批 2→会话 2，prompt_hash 各异。
"""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_ingest as pi
from tools import polish_setup as ps
from tools.pipelib import dumps, read_jsonl, write_jsonl
from tools.polishlib import jp_tail


def _sha256_text(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


BATCHES = {
    1: {"plain": [10, 11, 12], "locked": 13, "session_hash": "hash-session-1"},
    2: {"plain": [20, 21, 22], "locked": 23, "session_hash": "hash-session-2"},
}


def _build_mini(tmp_path, label="segX", channel="chA"):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": label, "lane": "main", "batches": [1, 2],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")

    all_ids = {}
    batch_rows = []
    for b, spec in BATCHES.items():
        ids = list(spec["plain"]) + [spec["locked"]]
        batch_rows.append({"batch": b, "lane": "main", "ids": ids, "seqs": [b],
                            "jp_chars": len(ids), "chapter": "s2s", "cut_reason": "budget"})
        for i in ids:
            all_ids[i] = b
    write_jsonl(repo / "data" / "batches.jsonl", batch_rows)

    jp = {i: f"第{i}句测试原文本体テキスト" for i in all_ids}
    zh = {i: f"第{i}句译文" for i in all_ids}

    anchor_items = [{"id": spec["locked"], "jp": jp[spec["locked"]], "zh": zh[spec["locked"]],
                     "recall": "测试锚点"} for spec in BATCHES.values()]
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([
        {"chapter": "global", "items": anchor_items},
    ], allow_unicode=True), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": jp[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in all_ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": zh[i], "batch": all_ids[i], "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"}
        for i in all_ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(label, opus_data, repo=repo)

    (d / "plan.json").write_text(dumps([
        {"session": b, "batches": [b], "prompt_hash": spec["session_hash"]}
        for b, spec in BATCHES.items()
    ]), encoding="utf-8")

    raw_dir = d / "raw" / channel
    raw_dir.mkdir(parents=True)
    for b, spec in BATCHES.items():
        lines = [dumps({"id": i, "jp_tail": jp_tail(jp[i]), "zh": zh[i],
                         "score": 90, "note": "", "adjudicate": False})
                 for i in spec["plain"]]
        (raw_dir / f"b{b}.out").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _rows(batch):
        p = raw_dir / f"b{batch}.out"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _save(batch, rows):
        p = raw_dir / f"b{batch}.out"
        p.write_text("\n".join(dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")

    def corrupt_tail(id, batch=1):
        rows = _rows(batch)
        for r in rows:
            if r["id"] == id:
                r["jp_tail"] = "坏尾串XX"
        _save(batch, rows)

    def add_locked_line(id, batch=1):
        rows = _rows(batch)
        rows.append({"id": id, "jp_tail": jp_tail(jp[id]), "zh": zh[id],
                     "score": 50, "note": "", "adjudicate": False})
        _save(batch, rows)

    def add_foreign_line(id, batch=1):
        rows = _rows(batch)
        rows.append({"id": id, "jp_tail": "不存在的尾串", "zh": "不知道哪来的",
                     "score": 10, "note": "", "adjudicate": False})
        _save(batch, rows)

    def drop_line(id, batch=1):
        rows = [r for r in _rows(batch) if r["id"] != id]
        _save(batch, rows)

    def dup_line(id, batch=1):
        rows = _rows(batch)
        target = next(r for r in rows if r["id"] == id)
        rows.append(dict(target))
        _save(batch, rows)

    def corrupt_json(batch=1):
        p = raw_dir / f"b{batch}.out"
        lines = p.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0][:-3] + "###NOTJSON"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return SimpleNamespace(
        root=repo, d=d, label=label, channel=channel, jp=jp, zh=zh, raw_dir=raw_dir,
        corrupt_tail=corrupt_tail, add_locked_line=add_locked_line,
        add_foreign_line=add_foreign_line, drop_line=drop_line, dup_line=dup_line,
        corrupt_json=corrupt_json,
    )


@pytest.fixture
def mini(tmp_path):
    return _build_mini(tmp_path)


# --- brief Step 1 核心断言 ---

def test_ingest_ok_and_receipt(mini):
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert len(rows) == 3
    row10 = next(x for x in rows if x["id"] == 10)
    assert row10["jp_hash"] == _sha256_text(mini.jp[10])
    assert row10["opus_hash"] == _sha256_text(mini.zh[10])
    assert row10["channel"] == mini.channel
    assert row10["batch"] == 1
    assert row10["prompt_hash"] == "hash-session-1"
    assert "ts" in row10 and row10["ts"]
    assert not (mini.d / f"discipline.{mini.channel}.json").exists()


def test_bad_tail_kills_line_not_batch(mini):
    mini.corrupt_tail(id=11)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 2
    assert r["dead"][0]["id"] == 11
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert ids_in == {10, 12}


def test_locked_id_killed_and_disciplined(mini):
    mini.add_locked_line(id=13)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    assert 13 in [d["id"] for d in r["dead"]]
    disc = json.loads((mini.d / f"discipline.{mini.channel}.json").read_text(encoding="utf-8"))
    assert disc["locked_hits"] == 1
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert 13 not in ids_in


def test_incomplete_coverage_fails_whole_batch(mini):
    mini.drop_line(id=12)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r["ok"]
    assert r["added"] == 0 and r["dead"] == []
    assert not (mini.d / f"candidates.{mini.channel}.jsonl").exists()
    assert not (mini.d / f"ingested.{mini.channel}.json").exists()


def test_idempotent(mini):
    r1 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    r2 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r1["added"] == 3
    assert r2["ok"] and r2["added"] == 0
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert len(rows) == 3


# --- 补充：三个自行裁定的设计点 ---

def test_foreign_id_killed_not_batch(mini):
    """id 根本不属于这个 SEG 的任何 id——判死，不影响批完整性。"""
    mini.add_foreign_line(id=999999)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"] and r["added"] == 3
    assert any(d["id"] == 999999 and "不在批内" in d["reason"] for d in r["dead"])


def test_duplicate_id_kills_both_lines_but_batch_still_ok(mini):
    """重复 id：两行全部判死（不猜测取哪一条），但该 id 仍算"出现过"，
    不触发整批失败——duplicate 是错位信号，不是截断信号。"""
    mini.dup_line(id=11)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r["ok"]
    assert r["added"] == 2  # 10, 12 存活；11 的两行全死
    dead_ids = [d["id"] for d in r["dead"]]
    assert dead_ids.count(11) == 2
    assert all("重复" in d["reason"] for d in r["dead"] if d["id"] == 11)
    ids_in = {row["id"] for row in read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")}
    assert ids_in == {10, 12}


def test_malformed_json_line_fails_whole_batch(mini):
    """单行不是合法 JSON——整批失败，不是只杀那一行（覆盖完整性判据失效）。"""
    mini.corrupt_json(batch=1)
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r["ok"]
    assert r["added"] == 0 and r["dead"] == []
    assert not (mini.d / f"candidates.{mini.channel}.jsonl").exists()
    assert not (mini.d / f"ingested.{mini.channel}.json").exists()


def test_missing_plan_entry_fails_whole_batch_explicitly(mini):
    """batch 在 plan.json 里查不到所属会话——显式整批失败，不是静默填空串。"""
    (mini.d / "plan.json").write_text(dumps([
        {"session": 2, "batches": [2], "prompt_hash": "hash-session-2"},
    ]), encoding="utf-8")
    r = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r["ok"]
    assert "plan.json" in r["reason"]
    assert not (mini.d / f"candidates.{mini.channel}.jsonl").exists()


def test_raw_file_missing_fails_whole_batch(mini):
    r = pi.ingest(mini.label, "chZ", 1, repo=mini.root)
    assert not r["ok"]
    assert "raw 文件不存在" in r["reason"]
    assert not (mini.d / "candidates.chZ.jsonl").exists()


def test_failed_batch_does_not_block_retry(mini):
    """整批失败不记 ingested——修好 raw 后重跑同一批应能正常入仓（这正是
    「幂等标记只记成功批」这条设计的价值：失败可安全重试）。"""
    mini.drop_line(id=12)
    r1 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert not r1["ok"]

    # 修复：重新写回一份完整的合法批（模拟重跑模型/人工修正后的 raw）
    p = mini.raw_dir / "b1.out"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows.append({"id": 12, "jp_tail": jp_tail(mini.jp[12]), "zh": mini.zh[12],
                 "score": 90, "note": "", "adjudicate": False})
    p.write_text("\n".join(dumps(r) for r in rows) + "\n", encoding="utf-8")

    r2 = pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    assert r2["ok"] and r2["added"] == 3


def test_discipline_accumulates_across_batches(mini):
    """discipline.<channel>.json 的 locked_hits 是跨批累积计数，不是每次
    覆盖重写。"""
    mini.add_locked_line(id=13, batch=1)
    pi.ingest(mini.label, mini.channel, 1, repo=mini.root)
    mini.add_locked_line(id=23, batch=2)
    pi.ingest(mini.label, mini.channel, 2, repo=mini.root)
    disc = json.loads((mini.d / f"discipline.{mini.channel}.json").read_text(encoding="utf-8"))
    assert disc["locked_hits"] == 2


# --- CLI ---

def test_cli_single_batch(mini, capsys):
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--batch", "1",
                  "--repo", str(mini.root)])
    assert rc == 0
    rows = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    assert len(rows) == 3


def test_cli_bad_batch_returns_nonzero(mini):
    mini.drop_line(id=12)
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--batch", "1",
                  "--repo", str(mini.root)])
    assert rc == 1


def test_cli_all_scans_raw_dir(mini):
    rc = pi.main(["--seg", mini.label, "--channel", mini.channel, "--all",
                  "--repo", str(mini.root)])
    assert rc == 0
    rows1 = read_jsonl(mini.d / f"candidates.{mini.channel}.jsonl")
    ids = {r["id"] for r in rows1}
    assert ids == {10, 11, 12, 20, 21, 22}
    ingested = json.loads((mini.d / f"ingested.{mini.channel}.json").read_text(encoding="utf-8"))
    assert set(ingested["batches"]) == {1, 2}
