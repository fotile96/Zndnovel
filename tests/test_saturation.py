"""饱和度计算器：词族「全书出现数中已译批次覆盖比」——段末裁决的证据闸门（spec §2）。"""
from tools.saturation import saturation, main


LEDGER = [
    {"id": 1, "jp": "十円玉を置く", "chapter": "s1s"},
    {"id": 2, "jp": "十円玉と十円玉", "chapter": "s1s"},   # 一行两次，按次数计
    {"id": 3, "jp": "十円玉です", "chapter": "s6s"},
    {"id": 4, "jp": "無関係の行", "chapter": "s1s"},
]


def test_saturation_counts_occurrences_not_rows():
    r = saturation("十円玉", LEDGER, done_ids={1, 2})
    assert r["total"] == 4 and r["covered"] == 3
    assert r["ratio"] == 3 / 4
    assert r["uncovered_by_chapter"] == {"s6s": 1}


def test_saturation_zero_occurrence_term():
    r = saturation("ナハメ", LEDGER, done_ids={1})
    assert r["total"] == 0 and r["ratio"] is None


def test_main_reads_data_dir_and_gates(tmp_path, capsys):
    import json
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in LEDGER), encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}) + "\n" + json.dumps({"id": 2, "zh": "y"}),
        encoding="utf-8")
    rc = main(["--term", "十円玉", "--term", "ナハメ",
               "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0.750" in out and "滚存" in out   # 0.75 < 0.8 → 滚存
    assert "无出现" in out                     # total=0 单列
    # 终审 I2：表头前必须自述统计口径（已入线条数 + 实际 data-dir）
    assert "done=2 条已入线译文" in out
    assert str(tmp_path) in out


def test_main_warns_loudly_when_forward_missing(tmp_path, capsys):
    """终审 I2：漏传 --data-dir 时仓库根 data/ 没有 forward.jsonl，旧实现静默
    当成「零条已译」，输出一张全列 0.000/滚存 的完全合理的表——闸门失效方向
    最难发现。缺 forward 必须有醒目告警。"""
    import json
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in LEDGER), encoding="utf-8")
    assert not (tmp_path / "forward.jsonl").exists()
    rc = main(["--term", "十円玉", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "告警" in out
    assert "forward.jsonl" in out
    assert "done=0 条已入线译文" in out


def test_extra_rows_use_key_field_not_id():
    rows = [{"key": "snr_crd_0:35", "jp": "寝癖の話", "kind": "card_msg", "file": "snr_crd_0"}]
    r = saturation("寝癖", rows, done_ids={"snr_crd_0:35"})
    assert r["total"] == 1 and r["covered"] == 1
