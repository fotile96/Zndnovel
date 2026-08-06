"""tools/polish_commit.py：保税仓唯一清关口的单测。

夹具复用真实上游模块（与 test_polish_triage.py 同一惯例）：
`polish_setup.setup()` 造 frozen/、`polish_ingest.ingest()` 灌真候选、
`polish_check.gate()` 跑真机械闸、`polish_triage.triage()` 产出真
`triage.json`——只有 `decisions.jsonl`（人工裁决面）是本模块手写的固件，
因为在当前整条计划里，`decisions.jsonl` 的 adopt/edit 记录是人工在
`queue.md` 上裁决后手工 append 的（Task 11 runbook），没有代码生成它。

单 SEG "segX"，channel "chA"，4 个非锁定 id：
  - 10：候选与 opus 逐字相同 → bucket 1（零改动，不产生任何 patch 来源）。
  - 11：大改写（edit=26，远超 autoclear_limit）→ bucket 2（人工排队）。
    夹具默认在 decisions.jsonl 里给它一条 verdict=adopt 的裁决。
  - 12：中改（edit=7）→ bucket 2（K 默认 150 足够大，不需要挤桶）。
    默认不带任何裁决，留给"edit 裁决"专项测试用。
  - 14：小改（edit=2 ≤ autoclear_limit=4）→ 开启 chA 自动清关权、
    sample_rate 强制压到 0（确定性：sampled 恒 False）→ autoclear=True。

`opus_data`（`ps.setup()` 的第二个参数）就是"生产车道 data 目录"本身
（真实链路里对应 `pilot/lanes/opus/data/`），本测试直接把它当
`polish_commit.commit()` 的 `data_dir` 用——与真实用法完全一致，不是
额外发明的抽象。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_check as pcheck
from tools import polish_commit as pc
from tools import polish_ingest as pi
from tools import polish_setup as ps
from tools import polish_triage as pt
from tools.add_patch import existing_patches
from tools.pipelib import append_jsonl, dumps, read_jsonl, write_jsonl
from tools.polishlib import jp_tail
from tools.resolve import resolve_map

LABEL = "segX"

JP = {
    10: "アヤノは静かに微笑んだ。",
    11: "教室の時計が動いていることに気づいた。",
    12: "廊下の奥から足音が聞こえた。",
    14: "ユカリは眼鏡を押し上げた。",
}
OPUS = {
    10: "彩野静静地微笑着。",
    11: "我注意到教室里的时钟还在走动。",
    12: "走廊尽头传来了脚步声。",
    14: "由加里推了推眼镜。",
}
CAND_CHA = {
    10: OPUS[10],                                                # 零改动
    11: "教室里弥漫着令人窒息的寂静,仿佛连时间都为之停滞了一般。",  # 大改（edit=26）
    12: "走廊尽头忽然传来一阵奇怪的脚步声。",                       # 中改（edit=7）
    14: "由加里扶了扶眼镜。",                                      # 小改（edit=2）
}

ADOPT_TS_11 = "2026-08-01T00:00:00+00:00"


def _build_mini(tmp_path, *, decisions=None, extra_glossary_versions=()):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)

    ids = [10, 11, 12, 14]
    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": LABEL, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1],
         "jp_chars": len(ids), "chapter": "s2s", "cut_reason": "budget"},
    ])
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([]), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": JP[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"}
        for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": OPUS[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"} for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])

    d = ps.setup(LABEL, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([
        {"session": 1, "batches": [1], "prompt_hash": "hash-1"},
    ]), encoding="utf-8")

    raw_cha = d / "raw" / "chA"
    raw_cha.mkdir(parents=True)
    lines = [dumps({"id": i, "jp_tail": jp_tail(JP[i]), "zh": CAND_CHA[i],
                     "score": 90, "note": "", "adjudicate": False})
             for i in ids]
    (raw_cha / "b1.out").write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = pi.ingest(LABEL, "chA", 1, repo=repo)
    assert r["ok"], f"chA ingest 失败：{r}"

    pcheck.gate(LABEL, "chA", repo=repo)

    def enable_autoclear(channel="chA"):
        p = d / "channel_state.json"
        state = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        state[channel] = {"autoclear": True}
        p.write_text(dumps(state), encoding="utf-8")

    enable_autoclear("chA")
    import tools.polishlib as polishlib
    old_rate = polishlib.CFG["sample_rate"]
    polishlib.CFG["sample_rate"] = 0.0  # 确定性：autoclear 候选 sampled 恒 False
    try:
        pt.triage(LABEL, repo=repo)
    finally:
        polishlib.CFG["sample_rate"] = old_rate

    if decisions is None:
        decisions = [{"id": 11, "verdict": "adopt", "chosen_channel": "chA",
                      "edited_zh": None, "reason_code": "queue_review", "ts": ADOPT_TS_11}]
    write_jsonl(d / "decisions.jsonl", decisions)

    for v in extra_glossary_versions:
        (repo / "glossary" / f"glossary.v{v}.yaml").write_text(f"version: {v}", encoding="utf-8")

    return SimpleNamespace(root=repo, d=d, data_dir=opus_data, label=LABEL,
                            enable_autoclear=enable_autoclear)


@pytest.fixture
def mini(tmp_path):
    return _build_mini(tmp_path)


def by_id(rows, cid):
    matches = [r for r in rows if r["id"] == cid]
    assert len(matches) == 1, f"id={cid} 匹配 {len(matches)} 行：{matches}"
    return matches[0]


# ---- brief Step 1 核心场景 ----

def test_dry_run_no_write_but_two_rows(mini, capsys):
    before_patches = (mini.data_dir / "patches.jsonl").read_text(encoding="utf-8")
    before_decisions = (mini.d / "decisions.jsonl").read_text(encoding="utf-8")

    result = pc.commit(LABEL, mini.data_dir, dry_run=True, repo=mini.root)

    assert len(result) == 2
    assert {r["id"] for r in result} == {11, 14}
    assert not (mini.d / "committed.json").exists()
    assert (mini.data_dir / "patches.jsonl").read_text(encoding="utf-8") == before_patches
    assert (mini.d / "decisions.jsonl").read_text(encoding="utf-8") == before_decisions

    err = capsys.readouterr().err
    assert "倒查链" in err and "prompt_hash" in err


def test_apply_writes_and_prov_correct(mini):
    result = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert len(result) == 2

    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    assert len(patches) == 2

    p11 = by_id(patches, 11)
    assert p11["zh"] == CAND_CHA[11]
    assert p11["reason"] == "polish"
    assert p11["ts"] == ADOPT_TS_11
    assert p11["prov"] == {"channel": "chA", "candidate_ts": p11["prov"]["candidate_ts"],
                            "seg": LABEL}
    assert p11["prov"]["candidate_ts"]  # 非空，回指到候选行的 ts

    p14 = by_id(patches, 14)
    assert p14["zh"] == CAND_CHA[14]
    assert p14["prov"]["channel"] == "chA"

    decisions = read_jsonl(mini.d / "decisions.jsonl")
    auto_decisions = [r for r in decisions if r.get("verdict") == "auto"]
    assert len(auto_decisions) == 1
    assert auto_decisions[0]["id"] == 14
    assert auto_decisions[0]["reason_code"] == "autoclear"

    committed = json.loads((mini.d / "committed.json").read_text(encoding="utf-8"))
    assert {(c["id"], c["decision_ts"]) for c in committed["committed"]} == {
        (11, ADOPT_TS_11), (14, auto_decisions[0]["ts"]),
    }


def test_repeat_apply_is_noop(mini):
    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    n_patches_after_first = len(read_jsonl(mini.data_dir / "patches.jsonl"))
    n_decisions_after_first = len(read_jsonl(mini.d / "decisions.jsonl"))

    result2 = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)

    assert result2 == []
    assert len(read_jsonl(mini.data_dir / "patches.jsonl")) == n_patches_after_first
    assert len(read_jsonl(mini.d / "decisions.jsonl")) == n_decisions_after_first


def test_new_patch_during_polish_triggers_announce(mini, capsys):
    """润色期间另一个会话已经手工回改过 id=11——写前查重播报必须响。"""
    from tools.add_patch import add as add_patch_row
    add_patch_row(11, "别的会话已经写过的旧译文", "recall", 9, data=mini.data_dir)
    capsys.readouterr()

    pc.commit(LABEL, mini.data_dir, dry_run=True, repo=mini.root)
    err = capsys.readouterr().err
    assert "已有" in err and "1 条 patch" in err and "旧译文" in err

    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    err2 = capsys.readouterr().err
    assert "已有" in err2 and "旧译文" in err2

    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    id11_patches = [p for p in patches if p["id"] == 11]
    assert len(id11_patches) == 2  # 旧的一条 + 本次新追加的一条，未覆盖历史


# ---- edit 裁决路径 ----

def test_edit_verdict_uses_edited_zh_and_prov_channel(tmp_path):
    mini = _build_mini(tmp_path, decisions=[
        {"id": 11, "verdict": "adopt", "chosen_channel": "chA", "edited_zh": None,
         "reason_code": "queue_review", "ts": ADOPT_TS_11},
        {"id": 12, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "人工改写后的走廊尽头声音描述。",
         "reason_code": "manual_edit", "ts": "2026-08-01T00:05:00+00:00"},
    ])
    result = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert {r["id"] for r in result} == {11, 12, 14}

    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    p12 = by_id(patches, 12)
    assert p12["zh"] == "人工改写后的走廊尽头声音描述。"
    assert p12["prov"]["channel"] == "chA"
    # candidate_ts 回指到候选行本身的 ts，而不是 decision 的 ts
    cand12 = by_id(read_jsonl(mini.d / "candidates.chA.jsonl"), 12)
    assert p12["prov"]["candidate_ts"] == cand12["ts"]


# ---- 同一 id 先 auto 后人工改判：两条 decision 都要落地 ----

def test_same_id_auto_then_human_override_both_land(mini):
    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    decisions_after_auto = read_jsonl(mini.d / "decisions.jsonl")
    auto_ts_14 = by_id([r for r in decisions_after_auto if r.get("verdict") == "auto"], 14)["ts"]

    # 人工发现自动清关的 14 有问题，追加一条改判（ts 晚于 auto）
    append_jsonl(mini.d / "decisions.jsonl", [
        {"id": 14, "verdict": "edit", "chosen_channel": "chA",
         "edited_zh": "人工改判后的版本。", "reason_code": "auto_overturned",
         "ts": "2099-01-01T00:00:00+00:00"},
    ])

    result2 = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert [r["id"] for r in result2] == [14]

    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    id14_patches = [p for p in patches if p["id"] == 14]
    assert len(id14_patches) == 2
    assert id14_patches[0]["ts"] == auto_ts_14
    assert id14_patches[1]["zh"] == "人工改判后的版本。"

    # resolve 的"后写者胜"语义：最终生效译文是人工改判后的版本
    m = resolve_map([], patches)
    assert m[14] == "人工改判后的版本。"


# ---- sampled 的 autoclear 候选绝不直接清关 ----

def test_sampled_autoclear_not_committed(tmp_path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    (repo / "skeleton").mkdir(parents=True)
    (repo / "glossary" / "voices").mkdir(parents=True)
    ids = [14]
    (repo / "config" / "segments.yaml").write_text(yaml.safe_dump([
        {"seg": 1, "label": LABEL, "lane": "main", "batches": [1, 1],
         "chapters": ["s2s"], "jp_chars": 1, "review_focus": "测试段"},
    ], allow_unicode=True), encoding="utf-8")
    write_jsonl(repo / "data" / "batches.jsonl", [
        {"batch": 1, "lane": "main", "ids": ids, "seqs": [1],
         "jp_chars": len(ids), "chapter": "s2s", "cut_reason": "budget"},
    ])
    (repo / "skeleton" / "anchors.yaml").write_text(yaml.safe_dump([]), encoding="utf-8")
    (repo / "glossary" / "active.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "speakers.json").write_text("{}", encoding="utf-8")
    (repo / "glossary" / "style.md").write_text("# 风格", encoding="utf-8")
    (repo / "glossary" / "polish.md").write_text("# 六条细则", encoding="utf-8")
    (repo / "glossary" / "glossary.v1.yaml").write_text("version: 1", encoding="utf-8")

    opus_data = tmp_path / "opus_data"
    (opus_data / "notes").mkdir(parents=True)
    write_jsonl(opus_data / "ledger.jsonl", [
        {"id": i, "jp": JP[i], "voice": "NONVOICE", "file": "f", "func": "f",
         "literal": False, "line": i, "chapter": "s2s", "kind": "story"} for i in ids
    ])
    write_jsonl(opus_data / "forward.jsonl", [
        {"id": i, "zh": OPUS[i], "batch": 1, "backend": "cc", "model": "m",
         "ctx": "x", "glossary_v": 1, "ts": "t"} for i in ids
    ])
    write_jsonl(opus_data / "patches.jsonl", [])
    d = ps.setup(LABEL, opus_data, repo=repo)
    (d / "plan.json").write_text(dumps([{"session": 1, "batches": [1], "prompt_hash": "hash-1"}]),
                                  encoding="utf-8")
    raw_cha = d / "raw" / "chA"
    raw_cha.mkdir(parents=True)
    (raw_cha / "b1.out").write_text(
        dumps({"id": 14, "jp_tail": jp_tail(JP[14]), "zh": CAND_CHA[14],
               "score": 90, "note": "", "adjudicate": False}) + "\n", encoding="utf-8")
    assert pi.ingest(LABEL, "chA", 1, repo=repo)["ok"]
    pcheck.gate(LABEL, "chA", repo=repo)

    p = d / "channel_state.json"
    p.write_text(dumps({"chA": {"autoclear": True}}), encoding="utf-8")

    import tools.polishlib as polishlib
    old_rate = polishlib.CFG["sample_rate"]
    polishlib.CFG["sample_rate"] = 1.0  # 强制 sampled=True
    try:
        t = pt.triage(LABEL, repo=repo)
    finally:
        polishlib.CFG["sample_rate"] = old_rate
    row14 = by_id(t["rows"], 14)
    assert row14["autoclear"] and row14["sampled"]  # 前提：确实是"已清关但抽中复核"

    write_jsonl(d / "decisions.jsonl", [])
    result = pc.commit(LABEL, opus_data, dry_run=False, repo=repo)
    assert result == []
    assert read_jsonl(opus_data / "patches.jsonl") == []


# ---- glossary_v：清关时点（现行），不是冻结时点（manifest 快照） ----

def test_glossary_v_uses_current_repo_not_frozen_manifest(tmp_path):
    mini = _build_mini(tmp_path, extra_glossary_versions=[2])
    manifest = json.loads((mini.d / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["glossary_v"] == 1  # 冻结时点快照仍是 1

    result = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert all(r["glossary_v"] == 2 for r in result)  # 清关时点已是现行的 2

    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    assert all(p["glossary_v"] == 2 for p in patches)


# ---- CLI：resolve_data_dir 闸原样复用 ----

def test_cli_dry_run_default(mini, capsys):
    rc = pc.main(["--seg", LABEL, "--data-dir", str(mini.data_dir), "--repo", str(mini.root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert read_jsonl(mini.data_dir / "patches.jsonl") == []


def test_cli_apply_writes(mini):
    rc = pc.main(["--seg", LABEL, "--data-dir", str(mini.data_dir), "--repo", str(mini.root),
                  "--apply"])
    assert rc == 0
    assert len(read_jsonl(mini.data_dir / "patches.jsonl")) == 2


def test_cli_lane_mode_without_data_dir_or_env_rejects(mini, monkeypatch):
    monkeypatch.delenv("ZND_DATA", raising=False)
    (mini.root / "pilot" / "lanes" / "opus" / "data").mkdir(parents=True)
    with pytest.raises(SystemExit):
        pc.main(["--seg", LABEL, "--repo", str(mini.root)])
    # 拒绝发生在任何文件被创建之前——repo/data/ 本身是夹具搭建时就有的
    # （batches.jsonl 等），真正要防的是"缺省落进主仓 data/patches.jsonl"。
    assert not (mini.root / "data" / "patches.jsonl").exists()
