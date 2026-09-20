"""`tools/read_commit.py`（通读 UI 人工修改的唯一清关口）的测试。

盯的是三件**静默出错**的事——本项目在这三处都真翻过车：
1. 车道模式没给 `--data-dir` 就写进主仓 `data/`，零报错、退出码 0，改动一条不生效
   （`add_patch.py` 记的 2026-08-02 事故）；
2. 草稿写下之后车道又被别处动过，直接盖上去会**静默抹掉**那次改动；
3. 人手改出来的机械缺陷（多敲的字、尾随换行、新增 `『』`）混进生产。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import read_commit
from tools.pipelib import append_jsonl, read_jsonl, write_jsonl
from tools.read_server import Reader

LANE = "pilot/lanes/opus"


def _repo(tmp_path, edits):
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "glossary").mkdir(parents=True)
    (repo / "glossary" / "glossary.v7.yaml").write_text("version: 7", encoding="utf-8")
    lane = repo / LANE / "data"
    lane.mkdir(parents=True)
    write_jsonl(repo / "data" / "ledger.jsonl", [
        {"id": 10, "jp": "【彩野】「あ」", "voice": "N", "file": "f", "func": "g",
         "chapter": "s1s", "kind": "narrative", "line": 1},
        {"id": 11, "jp": "夜。", "voice": "N", "file": "f", "func": "g",
         "chapter": "s1s", "kind": "narrative", "line": 2},
    ])
    write_jsonl(repo / "data" / "timeline.jsonl", [
        {"seq": 1, "type": "unit", "unit_kind": "scene", "src": "f",
         "state": "s", "title": "t", "ids": [10, 11]}])
    write_jsonl(lane / "forward.jsonl", [
        {"id": i, "zh": z, "batch": 1, "backend": "cc", "model": "m", "ctx": "x",
         "glossary_v": 1, "ts": "t0"} for i, z in ((10, "【彩野】「啊」"), (11, "夜。"))])
    write_jsonl(lane / "patches.jsonl", [])
    (repo / "pilot" / "read-edits").mkdir(parents=True)
    write_jsonl(repo / "pilot" / "read-edits" / "opus.draft.jsonl", edits)
    return repo, lane


CLEAN = {"id": 11, "zh": "夜晚。", "note": "", "base_zh": "夜。", "jp": "夜。",
         "lane": LANE, "ts": "2026-08-26T00:00:00+00:00"}


def _zh(lane, cid):
    from tools.resolve import resolve_map
    return resolve_map(read_jsonl(lane / "forward.jsonl"),
                       read_jsonl(lane / "patches.jsonl")).get(cid)


# ---- 1. dry-run 是默认 ----

def test_dry_run_writes_nothing(tmp_path):
    repo, lane = _repo(tmp_path, [CLEAN])
    before = (lane / "patches.jsonl").read_bytes()
    rows = read_commit.commit(lane, repo=repo, lane=LANE)
    assert [r["id"] for r in rows] == [11]
    assert (lane / "patches.jsonl").read_bytes() == before


def test_apply_writes_review_patch(tmp_path):
    repo, lane = _repo(tmp_path, [CLEAN])
    read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False)
    pats = read_jsonl(lane / "patches.jsonl")
    assert len(pats) == 1
    assert pats[0]["reason"] == "review" and pats[0]["zh"] == "夜晚。"
    assert pats[0]["ts"] == CLEAN["ts"], "patch 的 ts 用草稿那条的时刻，便于倒查"
    assert _zh(lane, 11) == "夜晚。"


def test_apply_twice_is_noop(tmp_path):
    """幂等键 (id, ts)：重复清关不得重复落 patch。"""
    repo, lane = _repo(tmp_path, [CLEAN])
    read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False)
    assert read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False) == []
    assert len(read_jsonl(lane / "patches.jsonl")) == 1


def test_same_id_edited_twice_only_last_lands(tmp_path):
    """草稿 append-only，同 id 取最后一条——中间态没有落地的意义。"""
    repo, lane = _repo(tmp_path, [
        {**CLEAN, "zh": "第一版", "ts": "t1"},
        {**CLEAN, "zh": "第二版", "ts": "t2"}])
    read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False)
    pats = read_jsonl(lane / "patches.jsonl")
    assert [p["zh"] for p in pats] == ["第二版"]


# ---- 2. 漂移默认拒写 ----

def test_stale_edit_is_refused_by_default(tmp_path, capsys):
    """草稿写下后车道又被别处动过 → 默认拒写，且**说出来**。"""
    repo, lane = _repo(tmp_path, [CLEAN])
    append_jsonl(lane / "patches.jsonl", [
        {"id": 11, "zh": "别处改的", "reason": "recall", "glossary_v": 8, "ts": "t9"}])
    rows = read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False)
    assert rows == []
    err = capsys.readouterr().err
    assert "漂移" in err and "别处改的" in err
    assert _zh(lane, 11) == "别处改的", "别人的改动不得被静默抹掉"


def test_stale_can_be_forced(tmp_path):
    repo, lane = _repo(tmp_path, [CLEAN])
    append_jsonl(lane / "patches.jsonl", [
        {"id": 11, "zh": "别处改的", "reason": "recall", "glossary_v": 8, "ts": "t9"}])
    read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False, allow_stale=True)
    assert _zh(lane, 11) == "夜晚。"


# ---- 3. 机械体检未过默认拒写 ----

DIRTY = {**CLEAN, "id": 10, "zh": "编【彩野】「啊」", "base_zh": "【彩野】「啊」",
         "jp": "【彩野】「あ」"}


def test_edit_with_warnings_is_refused_by_default(tmp_path, capsys):
    repo, lane = _repo(tmp_path, [DIRTY])
    assert read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False) == []
    assert "机械体检未过" in capsys.readouterr().err
    assert _zh(lane, 10) == "【彩野】「啊」"


def test_warnings_can_be_forced(tmp_path):
    repo, lane = _repo(tmp_path, [DIRTY])
    read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False, allow_warn=True)
    assert _zh(lane, 10) == "编【彩野】「啊」"


def test_empty_diff_is_skipped(tmp_path):
    """改完与车道现值逐字相同 → 不落空 diff patch。"""
    repo, lane = _repo(tmp_path, [{**CLEAN, "zh": "夜。"}])
    assert read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False) == []
    assert read_jsonl(lane / "patches.jsonl") == []


def test_skipped_ids_stay_in_draft_for_next_round(tmp_path):
    """`--skip`：这一轮不清的 id 不写 patch、不进 committed.json，其余照常落地；
    下一轮不带 skip 时它照常清关（2026-09-21：几条要先商量的行不该拖住其余几十条）。"""
    other = {**CLEAN, "id": 10, "zh": "【彩野】「呀」", "base_zh": "【彩野】「啊」",
             "jp": "【彩野】「あ」"}
    repo, lane = _repo(tmp_path, [CLEAN, other])
    rows = read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False, skip={10})
    assert [r["id"] for r in rows] == [11]
    assert _zh(lane, 10) == "【彩野】「啊」" and _zh(lane, 11) == "夜晚。"
    rows = read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False)
    assert [r["id"] for r in rows] == [10]
    assert _zh(lane, 10) == "【彩野】「呀」"


# ---- 4. 车道模式拒绝闸（2026-08-02 事故的复用） ----

def test_cli_refuses_without_data_dir_in_lane_mode(tmp_path, monkeypatch):
    repo, lane = _repo(tmp_path, [CLEAN])
    monkeypatch.delenv("ZND_DATA", raising=False)
    with pytest.raises(SystemExit) as e:
        read_commit.main(["--repo", str(repo)])
    # `add_patch.resolve_data_dir` 把拒绝理由整段塞进 SystemExit（不是退出码 2），
    # 因为这条信息本身才是防事故的东西——照它抄的命令行就是对的那条。
    assert "没有显式指定数据目录" in str(e.value)
    assert read_jsonl(lane / "patches.jsonl") == [], "拒绝时不得有任何文件被写"


def test_cli_dry_run_default(tmp_path, capsys):
    repo, lane = _repo(tmp_path, [CLEAN])
    read_commit.main(["--repo", str(repo), "--data-dir", str(lane)])
    assert "DRY-RUN" in capsys.readouterr().out
    assert read_jsonl(lane / "patches.jsonl") == []


# ---- 5. 与通读服务的接线 ----

def test_round_trip_from_server_to_lane(tmp_path):
    """在服务里改一条 → 清关 → 车道现值就是它；服务重开后 pending 归零。"""
    repo, lane = _repo(tmp_path, [])
    r = Reader(repo=repo, lane=LANE)
    r.record_edit({"id": 11, "zh": "夜晚。", "note": "更顺"})
    read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False)
    assert _zh(lane, 11) == "夜晚。"
    # 清关后同一条草稿不再重复落地
    assert read_commit.commit(lane, repo=repo, lane=LANE, dry_run=False) == []
    # 车道追上之后，pending 不再报 stale（base 与现值仍相等？——现值已变，
    # 故 stale=True，这正是「清关完了草稿还留着」时该有的提示）
    r2 = Reader(repo=repo, lane=LANE)
    assert r2.unit_payload(1)["lines"][1]["pending"]["stale"] is True
