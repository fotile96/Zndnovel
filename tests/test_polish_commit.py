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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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
    (repo / "glossary" / "polish.md").write_text("# 语感细则", encoding="utf-8")
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


# ---- 最终评审 I4：冻结基线之后新落的人裁 patch，自动清关一律拒写 ----

def _land_human_patch(mini, cid, zh, reason="review", ts="2026-08-06T00:00:00+00:00"):
    """冻结**之后**往生产车道落一条人裁 patch（模拟"润色期间另一个会话把这
    一行裁决过了"）。刻意用 append，保持 patches.jsonl 的 append-only 语义。"""
    append_jsonl(mini.data_dir / "patches.jsonl",
                 [{"id": cid, "zh": zh, "reason": reason, "glossary_v": 1, "ts": ts}])


def test_autoclear_refuses_to_overwrite_post_freeze_ruling(mini, capsys):
    """spec §3 承诺 `manifest.opus_at` 是"安全承重点"：润色期间若有新裁决
    patch 落库，过期候选**机械失败**、不靠人记。评审 grep 全仓发现 `opus_at`
    只写不读，并实测：冻结后落一条 `reason=review` 人裁 patch，`commit
    --apply` 的自动清关照样写 `reason=polish` 盖上去，只有一行 stderr ⚠、
    **不阻断**——与 CLAUDE.md 记的「SEG-5 id 1600 误覆盖已裁定稿」同一失败
    模式，区别只在于这次执行者是无人值守的自动清关。
    """
    _land_human_patch(mini, 14, "由加里推了推那副旧眼镜。")
    result = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert 14 not in {r["id"] for r in result}, "自动清关不得覆盖冻结后的人裁 patch"
    assert 11 in {r["id"] for r in result}, "同一次 commit 里别的 id 不受牵连"

    # 生产车道里 id 14 仍然只有那条人裁 patch，没有被 polish 盖掉。
    p14 = [r for r in read_jsonl(mini.data_dir / "patches.jsonl") if r["id"] == 14]
    assert [r["reason"] for r in p14] == ["review"]
    # 也不该为它铸造 auto 决策（拒写发生在写 decisions 之前）。
    autos = [r for r in read_jsonl(mini.d / "decisions.jsonl")
             if r.get("verdict") == "auto"]
    assert not autos
    err = capsys.readouterr().err
    assert "拒绝写入" in err and "14" in err


def test_dry_run_also_refuses(mini, capsys):
    """dry-run 的预览清单里同样不得出现它——评审对 C1 的实测正是"dry-run
    把它列进了将写入的 patch"，预览与实写必须给同一个答案。"""
    _land_human_patch(mini, 14, "由加里推了推那副旧眼镜。")
    result = pc.commit(LABEL, mini.data_dir, dry_run=True, repo=mini.root)
    assert 14 not in {r["id"] for r in result}
    assert "拒绝写入" in capsys.readouterr().err


def test_human_verdict_path_allowed_but_announced(tmp_path, capsys):
    """人裁路径放行、但显著播报——那条路径上有人正看着这个 id，他有权在
    知情前提下覆盖；无人值守的自动清关没有这个资格。"""
    m = _build_mini(tmp_path, decisions=[
        {"id": 11, "verdict": "adopt", "chosen_channel": "chA", "edited_zh": None,
         "reason_code": "语序", "ts": ADOPT_TS_11}])
    _land_human_patch(m, 11, "我发现教室里的钟还在走。")
    result = pc.commit(LABEL, m.data_dir, dry_run=True, repo=m.root)
    assert 11 in {r["id"] for r in result}
    err = capsys.readouterr().err
    assert "人工裁决路径覆盖" in err


def test_pre_freeze_patch_does_not_block(tmp_path):
    """反向锁（判据不能过宽）：冻结**之前**就存在的 review patch 不该拦住
    任何东西——那些 id 本来就在 locked 面里，也证明基线比对不是"只要有过
    review patch 就拦"。"""
    m = _build_mini(tmp_path)
    manifest = json.loads((m.d / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["opus_at"]["patches_lines"] == 0
    # 把一条 review patch 塞进"冻结时点已有"的位置：直接改 manifest 基线，
    # 等价于"冻结时 patches.jsonl 本来就有这一行"。
    _land_human_patch(m, 14, "冻结前就有的人裁稿")
    manifest["opus_at"]["patches_lines"] = 1
    (m.d / "manifest.json").write_text(dumps(manifest), encoding="utf-8")
    result = pc.commit(LABEL, m.data_dir, dry_run=True, repo=m.root)
    assert 14 in {r["id"] for r in result}


def test_polish_patch_after_freeze_does_not_block(mini):
    """只有 reason∈{review,recall} 算"人的裁决"——本流水线自己先前落的
    `reason=polish` patch 不该触发拒写（否则同一 SEG 第二次 commit 就寸步
    难行）。"""
    _land_human_patch(mini, 14, "上一轮润色稿", reason="polish")
    result = pc.commit(LABEL, mini.data_dir, dry_run=True, repo=mini.root)
    assert 14 in {r["id"] for r in result}


def test_missing_opus_at_is_conservative(mini, capsys):
    """manifest 缺 `opus_at` → 建不起基线 → **保守放大**：把全部 review/
    recall patch 都当成冻结后的，自动清关一律拒写并告警。宁可多拦不可漏拦
    ——"算不出来"绝不能等于"放行"。"""
    manifest = json.loads((mini.d / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("opus_at")
    (mini.d / "manifest.json").write_text(dumps(manifest), encoding="utf-8")
    _land_human_patch(mini, 14, "人裁稿")
    result = pc.commit(LABEL, mini.data_dir, dry_run=True, repo=mini.root)
    assert 14 not in {r["id"] for r in result}
    err = capsys.readouterr().err
    assert "无法确定冻结基线" in err


def test_shrunken_patches_file_is_conservative(mini, capsys):
    """patches.jsonl 比基线还短（append-only 被破坏，或 --data-dir 指向了
    别的车道）→ 同样保守放大。"""
    manifest = json.loads((mini.d / "manifest.json").read_text(encoding="utf-8"))
    manifest["opus_at"]["patches_lines"] = 99
    (mini.d / "manifest.json").write_text(dumps(manifest), encoding="utf-8")
    _land_human_patch(mini, 14, "人裁稿")
    result = pc.commit(LABEL, mini.data_dir, dry_run=True, repo=mini.root)
    assert 14 not in {r["id"] for r in result}
    assert "append-only 约定被破坏" in capsys.readouterr().err


# ---- D3 收尾：零改动+请裁的行若被人工裁成 adopt，必须安全落地 ----
# （pilot/polish/seg0-s0-s1/channel_feedback.md D3 节 + polish_triage.py
#  模块 docstring"polish_commit 侧的对应处理"专节：正常归宿是 keep_opus，
#  但 adopt 这条路径不能因为候选文本与 opus 逐字相同就出错或产生损坏数据）

def test_adopt_zero_edit_candidate_writes_safe_noop_patch(tmp_path, capsys):
    """id 10 是零改动候选（`CAND_CHA[10] == OPUS[10]`）——若裁决者仍然选择
    adopt（比如想显式留一条"人工确认过"的痕迹，而不是留白的 keep_opus），
    commit() 必须：不崩溃、写出一条 zh 与 opus 逐字相同的合法 patch、prov
    倒查链完整、`resolve_map()` 消费这条 patch 是幂等的（现行译文不变），
    并额外打一条信息级提示（不阻断——人已经做了决定，工具只负责提醒）。"""
    m = _build_mini(tmp_path, decisions=[
        {"id": 10, "verdict": "adopt", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "queue_review",
         "ts": "2026-08-01T00:00:00+00:00"},
    ])
    result = pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)

    p10 = by_id(result, 10)
    assert p10["zh"] == OPUS[10] == CAND_CHA[10]
    assert p10["reason"] == "polish"
    assert p10["prov"]["channel"] == "chA"
    assert p10["prov"]["candidate_ts"]

    patches = read_jsonl(m.data_dir / "patches.jsonl")
    p10_disk = by_id(patches, 10)
    assert p10_disk["zh"] == OPUS[10]

    # 幂等性：叠加这条"空 diff" patch 之后，现行译文与叠加之前完全一样。
    forward = read_jsonl(m.data_dir / "forward.jsonl")
    cur = resolve_map(forward, patches)
    assert cur[10] == OPUS[10]

    err = capsys.readouterr().err
    assert "空 diff" in err
    assert "keep_opus" in err

    # 重复 --apply 仍然是 no-op（幂等键不受"内容未变"影响）。
    result2 = pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    assert 10 not in {r["id"] for r in result2}


def test_adopt_changed_candidate_does_not_print_noop_note(mini, capsys):
    """对照组：id 11 是真实大改，adopt 落地的文本与 opus 不同——不应该触发
    D3 那条"空 diff"提示，证明这条提示是有差别地打印，不是无脑贴在每条
    adopt/edit 上。"""
    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    err = capsys.readouterr().err
    assert "空 diff" not in err


# --- P5 契约 v2：chosen_alt 采纳路径 ---

def _with_alt_candidate(tmp_path, chosen_alt, alt_zh="备选二号文本"):
    m = _build_mini(tmp_path, decisions=[
        {"id": 12, "verdict": "adopt", "chosen_channel": "chA",
         "chosen_alt": chosen_alt, "edited_zh": None,
         "reason_code": "queue_review", "ts": ADOPT_TS_11},
    ])
    append_jsonl(m.d / "candidates.chA.jsonl", [{
        "id": 12, "channel": "chA", "batch": 1, "prompt_hash": "hash-1",
        "jp_hash": "x", "opus_hash": "x", "zh": "主候选文本",
        "score": 60, "note": "两可", "adjudicate": True,
        "jp_tail": jp_tail(JP[12]), "ts": "t-alt",
        "alts": [{"zh": "备选一号文本", "note": ""},
                 {"zh": alt_zh, "note": "更贴"}],
    }])
    return m


def test_adopt_chosen_alt_writes_alt_text_and_prov(tmp_path):
    m = _with_alt_candidate(tmp_path, chosen_alt=2)
    pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    patches = read_jsonl(m.data_dir / "patches.jsonl")
    p12 = by_id(patches, 12)
    assert p12["zh"] == "备选二号文本"
    assert p12["prov"]["chosen_alt"] == 2
    assert p12["prov"]["channel"] == "chA"


def test_adopt_chosen_alt_out_of_range_skipped(tmp_path, capsys):
    m = _with_alt_candidate(tmp_path, chosen_alt=5)
    pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    patches = read_jsonl(m.data_dir / "patches.jsonl")
    assert not [r for r in patches if r["id"] == 12]
    assert "chosen_alt=5 越界" in capsys.readouterr().err


def test_adopt_chosen_alt_bad_ruby_skipped(tmp_path, capsys):
    m = _with_alt_candidate(tmp_path, chosen_alt=2, alt_zh="坏注音<汉字,>文本")
    pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    patches = read_jsonl(m.data_dir / "patches.jsonl")
    assert not [r for r in patches if r["id"] == 12]
    assert "ruby 不良构" in capsys.readouterr().err


def test_adopt_without_chosen_alt_unchanged_behavior(tmp_path):
    """无 chosen_alt 的 adopt 走主候选——回归护栏。"""
    m = _with_alt_candidate(tmp_path, chosen_alt=None)
    pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    patches = read_jsonl(m.data_dir / "patches.jsonl")
    p12 = by_id(patches, 12)
    assert p12["zh"] == "主候选文本"
    assert "chosen_alt" not in p12["prov"]


def test_edit_without_chosen_channel_is_committed(tmp_path):
    """纯人工编辑（不以任何通道候选为底本）没有 chosen_channel，必须照常清关。

    2026-08-20 修复的真缺陷：旧逻辑把 chosen_channel 当 adopt/edit 共同必填，
    于是 P5 裁决 UI 产出的纯人工编辑被**静默跳过**——p5seg0 实测 35 条编辑里
    32 条这样丢掉，dry-run 只在 stderr 刷一行「跳过」，是总数对不上才发现的。
    """
    m = _build_mini(tmp_path, decisions=[
        {"id": 12, "verdict": "edit", "chosen_channel": None, "edited_zh": "人手写的一版",
         "reason_code": "其他", "ts": ADOPT_TS_11},
    ])
    pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    p12 = by_id(read_jsonl(m.data_dir / "patches.jsonl"), 12)
    assert p12["zh"] == "人手写的一版"
    assert p12["prov"]["channel"] is None       # 无通道来源，如实记录
    assert p12["prov"]["candidate_ts"] is None


def test_adopt_without_chosen_channel_still_skipped(tmp_path, capsys):
    """adopt 缺 chosen_channel 仍必须跳过——它的语义就是「采纳某通道的那一版」。"""
    m = _build_mini(tmp_path, decisions=[
        {"id": 12, "verdict": "adopt", "chosen_channel": None, "edited_zh": None,
         "reason_code": "", "ts": ADOPT_TS_11},
    ])
    pc.commit(LABEL, m.data_dir, dry_run=False, repo=m.root)
    assert not [r for r in read_jsonl(m.data_dir / "patches.jsonl") if r["id"] == 12]
    assert "缺 chosen_channel" in capsys.readouterr().err


# ---- 改判与撤回：同 id 取最后一条，keep 能撤掉已经落地的 patch ----
# 2026-08-20 从 p5seg0-s0-s1 真实数据里发现：7 个 id 被人从 adopt 改判成
# keep_opus，但 keep 不产生 patch，撤不掉前面那条已经落地的——6 条车道文本
# 一直停在被撤回的那一版上，全程零告警。下面四条测试钉住修好后的语义。

KEEP_TS = "2026-08-02T00:00:00+00:00"


def _keep_row(cid, ts=KEEP_TS):
    return {"id": cid, "verdict": "keep_opus", "chosen_channel": None,
            "edited_zh": None, "reason_code": "", "ts": ts}


def test_superseded_adopt_never_lands(tmp_path):
    """adopt 后改判 keep，且 adopt 从没落过地——一条 patch 都不该写。"""
    mini = _build_mini(tmp_path, decisions=[
        {"id": 11, "verdict": "adopt", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "queue_review", "ts": ADOPT_TS_11},
        _keep_row(11),
    ])
    result = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert 11 not in [r["id"] for r in result]
    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    assert [p for p in patches if p["id"] == 11] == []


def test_keep_after_landed_adopt_retracts(mini):
    """adopt 已经落地之后才改判 keep——必须补一条回退到冻结面的 patch。"""
    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    landed = [p for p in read_jsonl(mini.data_dir / "patches.jsonl") if p["id"] == 11]
    assert len(landed) == 1 and landed[0]["zh"] == CAND_CHA[11]

    append_jsonl(mini.d / "decisions.jsonl", [_keep_row(11, ts="2099-01-01T00:00:00+00:00")])
    result2 = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert [r["id"] for r in result2] == [11]

    patches = read_jsonl(mini.data_dir / "patches.jsonl")
    id11 = [p for p in patches if p["id"] == 11]
    assert len(id11) == 2
    assert id11[-1]["zh"] == OPUS[11]
    assert id11[-1]["prov"]["retract"] is True
    # resolve 的"后写者胜"：最终生效译文回到冻结面 opus 原文
    assert resolve_map([], patches)[11] == OPUS[11]

    # 幂等：再跑一次不再追加
    assert pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root) == []


def test_retract_refuses_when_line_drifted(mini, capsys):
    """撤回只管本 SEG 自己落的那条；这一行在润色期间被别的会话改过就拒绝。"""
    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    (mini.d / "lane_drift.json").write_text(dumps(
        {"lane": "x", "drifted": 1,
         "findings": [{"id": 11, "frozen_zh": OPUS[11], "current_zh": "别的会话改的"}]}),
        encoding="utf-8")
    append_jsonl(mini.d / "decisions.jsonl", [_keep_row(11, ts="2099-01-01T00:00:00+00:00")])

    result2 = pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    assert 11 not in [r["id"] for r in result2]
    assert "lane_drift.json" in capsys.readouterr().err


def test_repeated_adopt_only_last_lands(tmp_path):
    """同 id 连着两条 adopt（改判改回来）：只落最后一条，不留中间态。"""
    mini = _build_mini(tmp_path, decisions=[
        {"id": 11, "verdict": "adopt", "chosen_channel": "chA",
         "edited_zh": None, "reason_code": "", "ts": ADOPT_TS_11},
        {"id": 11, "verdict": "edit", "chosen_channel": None,
         "edited_zh": "人工最终版。", "reason_code": "", "ts": KEEP_TS},
    ])
    pc.commit(LABEL, mini.data_dir, dry_run=False, repo=mini.root)
    id11 = [p for p in read_jsonl(mini.data_dir / "patches.jsonl") if p["id"] == 11]
    assert len(id11) == 1
    assert id11[0]["zh"] == "人工最终版。"
