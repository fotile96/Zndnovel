"""饱和度计算器：词族「全书出现数中已译批次覆盖比」——段末裁决的证据闸门（spec §2）。"""
from pathlib import Path

from tools.saturation import saturation, main, DIRTY_KEY_VERDICT, COMPOUND_VERDICT_PREFIX


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


# ── 并列词串探测：`はい／いいえ` 是当初那个 Critical 的头号例子 ──
# is_clean_key 本身逐字检查会放行「はい／いいえ」（全角 ／ 本身也出现在游戏
# 原文标点里，所以在 corpus_chars 内）——但 total==0 被读成「无出现、可以随便
# 定」，而真实 はい/いいえ 各自都有几十到几百次出现。main() 现在会在 total==0
# 时按并列分隔符拆开子串各查一次，只要有子串 total>0 就报「疑似并列词串」并
# 摆出真实数字，不再报「无出现」。
#
# P3 devwave1 复评 Important：此前这里直接断言了真实 opus 车道 forward.jsonl
# 里 はい/いいえ 的精确 covered 数（167/13）——covered 来自持续增长的生产译文，
# 车道每推进一段这两个数字就可能变、测试会红在与被测逻辑无关的原因上（并列
# 探测本身没坏，只是生产又译了几批）。改用合成 fixture：与
# test_main_compound_split_all_zero_falls_back_to_existing_verdict 同一手法，
# 让子串各自有由 fixture 数据现算出来、可复现的命中次数，断言的 ratio 直接
# 来自这份固定 fixture，不随生产推进变化。
PILOT_OPUS_DATA = Path(__file__).resolve().parent.parent / "pilot/lanes/opus/data"


def test_main_flags_compound_term_with_synthetic_lane_evidence(tmp_path, capsys):
    # 合成 fixture：子串「アイ」命中 2 次（1 覆盖/1 未覆盖，done_ids 只含 id=1）、
    # 「ウエ」命中 1 次（未覆盖）；拼起来的整词「アイ／ウエ」本身从不以连续
    # 子串出现在任何一行里，total==0。断言的 ratio 由这份固定数据现算得出
    # （アイ=1/2=0.500、ウエ=0/1=0.000），与生产数据完全解耦。
    import json
    ledger = [
        {"id": 1, "jp": "アイスをたべる", "chapter": "s1s"},   # 「アイ」命中 1 次（覆盖）
        {"id": 2, "jp": "アイコンを押す", "chapter": "s1s"},   # 「アイ」再命中 1 次（未覆盖）
        {"id": 3, "jp": "ウエストが痛い", "chapter": "s2s"},   # 「ウエ」命中 1 次（未覆盖）
    ]
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in ledger), encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}), encoding="utf-8")
    rc = main(["--term", "アイ／ウエ", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    expected = f"{COMPOUND_VERDICT_PREFIX}（アイ=1/2=0.500、ウエ=0/1=0.000）"
    assert expected in out
    assert "无出现" not in out
    assert "未匹配到该词键" not in out


def test_main_compound_detection_structural_on_real_lane_data(capsys):
    # 独立价值（P3 devwave1 复评认可保留）：至少一条测试真的踩过真实车道数据，
    # 确认拆分/子串查询/全角半角等价这条管线在真实数据形状上真的能跑通——但
    # 只断言**结构性质**（前缀出现、含两个子串词名、全角/半角两种抄法输出
    # 完全相同），不断言任何具体分子分母，这三条都不随生产推进变化。
    assert (PILOT_OPUS_DATA / "ledger.jsonl").exists(), "需要真实 opus 车道数据"
    rc = main(["--term", "はい／いいえ", "--term", "はい/いいえ",
               "--data-dir", str(PILOT_OPUS_DATA), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    lines = [l for l in out.splitlines()
             if l.startswith("| はい／いいえ ") or l.startswith("| はい/いいえ ")]
    assert len(lines) == 2
    for line in lines:
        assert COMPOUND_VERDICT_PREFIX in line
        assert "はい=" in line and "いいえ=" in line
    # 全角/半角两种抄法要得到完全相同的判定——去掉最前的词名列后逐字比对，
    # 不比较具体数字是不是某个值，只比较两者*彼此*是否一致。
    cols = [line.split("|", 2)[2] for line in lines]   # 去掉开头空列与词名列
    assert cols[0] == cols[1]


def test_main_compound_split_all_zero_falls_back_to_existing_verdict(tmp_path, capsys):
    # 反面：词键含并列分隔符，但拆开后每个子串也都是零出现——不能被误报成
    # 「疑似并列词串」，仍按原有判据走（这里子串与整词都干净，报「无出现」）。
    # 字符分散布置在不同行，保证「タニ」「バタ」都不作为连续子串出现在语料里。
    import json
    ledger = [
        {"id": 1, "jp": "タの音", "chapter": "s1s"},
        {"id": 2, "jp": "ニの字", "chapter": "s1s"},
        {"id": 3, "jp": "／区切り", "chapter": "s1s"},
        {"id": 4, "jp": "バラの花", "chapter": "s1s"},
    ]
    (tmp_path / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in ledger), encoding="utf-8")
    (tmp_path / "forward.jsonl").write_text(
        json.dumps({"id": 1, "zh": "x"}), encoding="utf-8")
    rc = main(["--term", "タニ／バタ", "--data-dir", str(tmp_path), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "| タニ／バタ | 0 | 0 | - | 无出现 | - |" in out
    assert "疑似并列词串" not in out


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


def test_runbook_step2_wording_matches_compound_verdict_constant():
    # 同上一条的教训，这次钉 COMPOUND_VERDICT_PREFIX：并列词串探测是本轮
    # 追加的修正（`はい／いいえ` 是当初 Critical 的头号例子），runbook 里
    # 说明这道判据的措辞必须与代码常量逐字一致。
    runbook = Path(__file__).resolve().parent.parent / "docs/ops/p3-production-runbook.md"
    text = runbook.read_text(encoding="utf-8")
    idx_step2 = text.index("uv run python tools/saturation.py --terms-file")
    idx_wording = text.index(COMPOUND_VERDICT_PREFIX, idx_step2)
    assert 0 < idx_wording - idx_step2 < 800
