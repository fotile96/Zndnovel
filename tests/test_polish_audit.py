"""tools/polish_audit.py：抽检推翻率闸的单测（最终评审 I7）。

夹具不复用真实上游（`polish_triage` 的抽样受 K 帽/种子影响，构造"恰好抽中
这几条"很脆），直接手写 `triage.json` + `decisions.jsonl` + `channel_state.
json` 三份输入——本模块的职责边界就是"读这三份、算一个比率、写一个键"，
用真上游反而会让被测面被抽样随机性稀释。三份输入的字段形状与真实产物逐字
一致（`triage.json` 的 rows 取自 `polish_triage.triage()` 的 `out_rows`
结构；decisions 取自 runbook §八 给的手写模板）。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import polish_audit as pa
from tools import polish_triage as pt
from tools.pipelib import dumps, write_jsonl

LABEL = "segA"


def _row(cid, ch, *, autoclear=True, sampled=False, bucket=3, edit=2):
    return {"id": cid, "channel": ch, "bucket": bucket, "edit": edit,
            "autoclear": autoclear, "sampled": sampled}


def _build(tmp_path, rows, decisions, state=None):
    repo = tmp_path / "repo"
    d = repo / "pilot" / "polish" / LABEL
    d.mkdir(parents=True)
    (d / "triage.json").write_text(dumps({"rows": rows, "queue_ids": [], "meta": {}}),
                                    encoding="utf-8")
    write_jsonl(d / "decisions.jsonl", decisions)
    if state is not None:
        (d / "channel_state.json").write_text(dumps(state), encoding="utf-8")
    return SimpleNamespace(root=repo, d=d)


def _dec(cid, verdict, ch="chA", ts="t1"):
    return {"id": cid, "verdict": verdict, "chosen_channel": ch,
            "edited_zh": ("改稿" if verdict == "edit" else None),
            "reason_code": "语序", "ts": ts}


# ---- 超线 → 关权 ----

def test_overturn_over_line_freezes_channel(tmp_path, capsys):
    """4 条抽检里 2 条被推翻（50% ≥ 20%）→ 该通道自动清关权立即关闭。

    这条闸是自动清关这条免检通道**唯一**的事后反馈回路（spec §5），此前
    只有 runbook 一段散文、零代码；而 `polish_triage` 本身还会主动压缩抽检
    覆盖率（K 帽），出口再靠人记等于没有闭环。
    """
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in (1, 2, 3, 4)]
    rows += [_row(9, "chA")]      # 真正被自动清关掉的（未抽中）→ 回滚清单
    m = _build(tmp_path, rows,
               [_dec(1, "adopt"), _dec(2, "adopt"), _dec(3, "keep_opus"), _dec(4, "edit")],
               {"chA": {"autoclear": True}})
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["decided"] == 4
    assert stats["chA"]["overturned"] == 2
    assert stats["chA"]["rate"] == 0.5
    assert stats["chA"]["frozen"]
    assert stats["chA"]["rollback_ids"] == [9]

    state = json.loads((m.d / "channel_state.json").read_text(encoding="utf-8"))
    assert state["chA"]["autoclear"] is False
    assert state["chA"]["autoclear_frozen_by"] == "overturn"
    # 关权必须真的对下游生效——直接问 polish_triage 自己的读取函数，不自造解析。
    assert pt._channel_autoclear_power("chA", state) is False

    err = capsys.readouterr().err
    assert "冻结线" in err and "回滚复审" in err


def test_under_line_leaves_state_untouched(tmp_path):
    """5 条里 1 条被推翻（20%…）——注意 `overturn_freeze` 的边界取 `>=`
    （与 `config/polish.yaml` 该行注释一致），故 20% 恰好命中即冻结；这里
    用 10 条 1 条（10%）验证未超线时**一个字节都不改**。"""
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in range(1, 11)]
    decs = [_dec(i, "adopt") for i in range(1, 10)] + [_dec(10, "edit")]
    m = _build(tmp_path, rows, decs, {"chA": {"autoclear": True}})
    before = (m.d / "channel_state.json").read_bytes()
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["rate"] == pytest.approx(0.1)
    assert not stats["chA"]["frozen"]
    assert (m.d / "channel_state.json").read_bytes() == before


def test_boundary_exactly_at_line_freezes(tmp_path):
    """恰好等于冻结线（20%）→ 冻结。闸的边界向安全侧取：临界点上宁可响。"""
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in range(1, 6)]
    decs = [_dec(i, "adopt") for i in range(1, 5)] + [_dec(5, "keep_opus")]
    m = _build(tmp_path, rows, decs, {"chA": {"autoclear": True}})
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["rate"] == pytest.approx(0.2)
    assert stats["chA"]["frozen"]


# ---- 判据细节 ----

def test_adopt_of_another_channel_counts_as_overturn(tmp_path):
    """人裁选了别家的候选 → 对本通道算推翻：本通道那一行若没被抽中，就会
    被原样自动清关进库，而人明确不要它。"""
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in (1, 2)]
    m = _build(tmp_path, rows, [_dec(1, "adopt", ch="chB"), _dec(2, "adopt", ch="chA")],
               {"chA": {"autoclear": True}})
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["overturned"] == 1


def test_last_decision_wins(tmp_path):
    """同一 id 多条人裁 → 取最后一条（append-only"后来者为现行"）。"""
    rows = [_row(1, "chA", sampled=True, bucket=2)]
    m = _build(tmp_path, rows,
               [_dec(1, "keep_opus", ts="t1"), _dec(1, "adopt", ts="t2")],
               {"chA": {"autoclear": True}})
    assert pa.audit(LABEL, repo=m.root)["chA"]["overturned"] == 0


def test_auto_verdict_is_not_a_human_judgement(tmp_path, capsys):
    """`verdict="auto"` 是 `polish_commit` 自己铸造的记录，不是人的判断——
    不得拿它当"人已确认"，否则抽检会**自我背书**：工具铸造的 auto 记录会把
    每一条抽检样本都算成"通过"，推翻率恒 0，这条闸变成恒绿。"""
    rows = [_row(1, "chA", sampled=True, bucket=2)]
    m = _build(tmp_path, rows,
               [{"id": 1, "verdict": "auto", "chosen_channel": "chA",
                 "edited_zh": None, "reason_code": "autoclear", "ts": "t1"}],
               {"chA": {"autoclear": True}})
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["decided"] == 0 and stats["chA"]["pending"] == 1
    assert stats["chA"]["rate"] is None and not stats["chA"]["frozen"]
    assert "尚未裁决" in capsys.readouterr().err


def test_pending_samples_reported_not_swallowed(tmp_path, capsys):
    """裁决没做完时：待裁样本不进分母，但必须**响**——否则"分母只有 1 条、
    率虚低"会被无声吞掉。"""
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in (1, 2, 3)]
    m = _build(tmp_path, rows, [_dec(1, "adopt")], {"chA": {"autoclear": True}})
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["decided"] == 1 and stats["chA"]["pending"] == 2
    assert "尚未裁决" in capsys.readouterr().err


def test_only_sampled_autoclear_rows_count(tmp_path):
    """分母只认 `autoclear and sampled` 的行——普通人裁候选（非自动清关）
    的 verdict 与本闸无关，混进去会把推翻率整体稀释掉。"""
    rows = [_row(1, "chA", sampled=True, bucket=2),
            _row(2, "chA", autoclear=False, bucket=2),   # 普通排队候选
            _row(3, "chA")]                              # 已自动清关、未抽中
    m = _build(tmp_path, rows, [_dec(1, "adopt"), _dec(2, "keep_opus")],
               {"chA": {"autoclear": True}})
    stats = pa.audit(LABEL, repo=m.root)
    assert stats["chA"]["sampled"] == 1 and stats["chA"]["overturned"] == 0


def test_per_channel_isolation(tmp_path):
    """一条通道超线不牵连另一条。"""
    rows = ([_row(i, "chA", sampled=True, bucket=2) for i in (1, 2)]
            + [_row(i, "chB", sampled=True, bucket=2) for i in (3, 4)])
    m = _build(tmp_path, rows,
               [_dec(1, "keep_opus", ch="chA"), _dec(2, "keep_opus", ch="chA"),
                _dec(3, "adopt", ch="chB"), _dec(4, "adopt", ch="chB")],
               {"chA": {"autoclear": True}, "chB": {"autoclear": True}})
    pa.audit(LABEL, repo=m.root)
    state = json.loads((m.d / "channel_state.json").read_text(encoding="utf-8"))
    assert state["chA"]["autoclear"] is False
    assert state["chB"]["autoclear"] is True


def test_dry_run_reports_but_does_not_write(tmp_path):
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in (1, 2)]
    m = _build(tmp_path, rows, [_dec(1, "keep_opus"), _dec(2, "keep_opus")],
               {"chA": {"autoclear": True}})
    before = (m.d / "channel_state.json").read_bytes()
    stats = pa.audit(LABEL, repo=m.root, apply=False)
    assert stats["chA"]["frozen"]
    assert (m.d / "channel_state.json").read_bytes() == before


def test_missing_triage_is_loud(tmp_path):
    repo = tmp_path / "repo"
    (repo / "pilot" / "polish" / LABEL).mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        pa.audit(LABEL, repo=repo)


# ---- 与准入小考的互锁：冻结不得被一次重跑小考悄悄解开 ----

def test_calibrate_cannot_silently_reopen_frozen_channel(tmp_path, capsys):
    """`polish_calibrate.score()` 每次判卷都会重写该通道条目。若它照旧整条
    覆盖，"重跑一次准入小考"就能把本闸刚落的冻结悄悄解掉——一道能被无意中
    撤销的闸等于没有闸。"""
    from tools import polish_calibrate as pcal

    rows = [_row(i, "chA", sampled=True, bucket=2) for i in (1, 2)]
    m = _build(tmp_path, rows, [_dec(1, "keep_opus"), _dec(2, "keep_opus")],
               {"chA": {"autoclear": True}})
    pa.audit(LABEL, repo=m.root)

    # 造一场"满分"的准入小考：金标零改动 → pass 本该为 True。
    calib = m.d / "calib"
    calib.mkdir()
    write_jsonl(calib / f"{LABEL}.batch.jsonl",
                [{"id": 1, "batch": f"calib-{LABEL}", "jp": "テスト。", "opus_zh": "测试。"}])
    (calib / f"{LABEL}.truth.json").write_text(dumps({"1": {"is_gold": True}}),
                                                encoding="utf-8")
    raw = m.d / "raw.jsonl"
    write_jsonl(raw, [{"id": 1, "jp_tail": "テスト。", "zh": "测试。",
                       "score": 99, "note": "", "adjudicate": False}])

    result = pcal.score(LABEL, raw, "chA", repo=m.root)
    assert result["gold_substantive"] == 0          # 小考本身是满分
    assert result["pass"] is False                  # 但不予重开
    assert result["blocked_by"] == "overturn"
    state = json.loads((m.d / "channel_state.json").read_text(encoding="utf-8"))
    assert state["chA"]["autoclear"] is False
    assert "不予重新开启" in capsys.readouterr().err


# ---- CLI ----

def test_cli(tmp_path, capsys):
    rows = [_row(i, "chA", sampled=True, bucket=2) for i in (1, 2)]
    m = _build(tmp_path, rows, [_dec(1, "keep_opus"), _dec(2, "adopt")],
               {"chA": {"autoclear": True}})
    rc = pa.main(["--seg", LABEL, "--repo", str(m.root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "推翻率 50.0%" in out and "已冻结自动清关权" in out


def test_cli_no_samples(tmp_path, capsys):
    m = _build(tmp_path, [_row(1, "chA")], [])
    assert pa.main(["--seg", LABEL, "--repo", str(m.root)]) == 0
    assert "没有任何抽检样本" in capsys.readouterr().out
