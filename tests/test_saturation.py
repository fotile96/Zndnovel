"""饱和度计算器：词族「全书出现数中已译批次覆盖比」——段末裁决的证据闸门（spec §2）。"""
from pathlib import Path

from tools.saturation import saturation, main, DIRTY_KEY_VERDICT


LEDGER = [
    {"id": 1, "jp": "十円玉を置く", "chapter": "s1s"},
    {"id": 2, "jp": "十円玉と十円玉", "chapter": "s1s"},   # 一行两次，按次数计
    {"id": 3, "jp": "十円玉です", "chapter": "s6s"},
    {"id": 4, "jp": "無関係の行", "chapter": "s1s"},
    # is_clean_key 的语料字符集来源：ナ/ハ/メ 三字散落在此行里（不连续拼成
    # 「ナハメ」，故不影响 total==0 的既有断言），让「ナハメ」在下面的 main()
    # 测试里判定为「干净键、真零出现」而非「脏键」——同一批字符也用来钉
    # test_main_clean_key_zero_total_still_reports_no_occurrence。
    {"id": 5, "jp": "ナポリタンとハンバーガーのメニュー", "chapter": "s1s"},
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


# ── 脏键判据（is_clean_key）也要挡住 main() 这道门，不止 cluster_notes.py ──
# 同一个误读——把「词键没提干净」读成「原文里没这词」——原先只在 cluster_notes
# 里被挡，saturation.py 自己的 main() 没有这道判据，手抄词表带一点残渣就又能
# 从这道门进来。以下三条钉住 main() 侧的新行为。

def test_main_reports_dirty_key_as_unmatched_not_no_occurrence(tmp_path, capsys):
    import json
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in LEDGER), encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}), encoding="utf-8")
    # "2470" 是裸 ASCII/数字残渣（ASCII_RE 硬门），即便 total==0 也不该报「无出现」
    rc = main(["--term", "2470", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "未匹配到该词键（可能提取不干净，请人工核对）" in out
    assert "| 2470 | 0 | 0 | - | 未匹配到该词键" in out


def test_main_clean_key_zero_total_still_reports_no_occurrence(tmp_path, capsys):
    # 反面：键干净（逐字都在语料字符集内、非 ASCII、非空白、长度合规）但确实
    # 真零出现——仍要报「无出现」，不能被脏键判据误伤。
    import json
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in LEDGER), encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}), encoding="utf-8")
    rc = main(["--term", "ナハメ", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "| ナハメ | 0 | 0 | - | 无出现 | - |" in out
    assert "未匹配到该词键" not in out


def test_main_warns_on_missing_ledger_file(tmp_path, capsys):
    # ledger.jsonl 干脆不存在（此前会在 read_jsonl 里 FileNotFoundError 崩溃，
    # 与 cluster_notes.py 的存在性判断不一致）——同 cluster_notes 口径给告警，
    # rc 仍为 0。
    import json
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}), encoding="utf-8")
    assert not (tmp_path / "ledger.jsonl").exists()
    rc = main(["--term", "十円玉", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ledger.jsonl" in out and "没读到或为空" in out
    assert "全部词键将被判脏" in out
    assert "未匹配到该词键（可能提取不干净，请人工核对）" in out  # 唯一词也被判脏


def test_main_warns_on_empty_ledger_file(tmp_path, capsys):
    # 反面：ledger.jsonl 文件存在但为空（0 条记录）——同样要告警。
    import json
    (tmp_path / "ledger.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}), encoding="utf-8")
    rc = main(["--term", "十円玉", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ledger.jsonl" in out and "没读到或为空" in out
    assert "全部词键将被判脏" in out


def test_runbook_step2_wording_matches_dirty_key_verdict_constant():
    # 跨文件一致性靠注释约束不可靠（本仓库刚吃过一次亏，见 cluster_notes.py
    # task-1 的教训）：runbook §5 第 2 步引用的措辞必须与代码里实际打印的
    # DIRTY_KEY_VERDICT 常量逐字一致，否则未来只改了代码没改文档、或反过来，
    # 都会在这条测试上炸，而不是悄悄分家。
    runbook = Path(__file__).resolve().parent.parent / "docs/ops/p3-production-runbook.md"
    text = runbook.read_text(encoding="utf-8")
    assert DIRTY_KEY_VERDICT in text
    # 且确实出现在「裁决会话清单」第 2 步（saturation.py 那条）附近，不是随便
    # 哪里提了一句同名字符串。
    idx_step2 = text.index("uv run python tools/saturation.py --terms-file")
    idx_wording = text.index(DIRTY_KEY_VERDICT, idx_step2)
    assert 0 < idx_wording - idx_step2 < 800
