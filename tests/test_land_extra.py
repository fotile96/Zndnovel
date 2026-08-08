import pytest

from tools.derive_extra import build_card_indexes
from tools.land_extra import (
    assemble_rows,
    validate_forward_extra,
    load_translated_by_jp,
    land,
    main,
)
from tools.pipelib import read_jsonl, write_jsonl, REPO


# ---------------------------------------------------------------------------
# 夹具：小规模但覆盖 4 种 kind 的合成 ledger，含一条空 jp 的 savedata（真实库里的
# 3 条空串 savedata 之一），用于钉住"空串不能被当成缺失跳过"这条安全闸。
# ---------------------------------------------------------------------------

CARDS_JP = [
    {"card": 1, "title_jp": "ある子が学校にくる物語"},
]
CARDS_ZH = [
    {"card": 1, "title_zh": "有个孩子来学校的故事"},
]

LEDGER_ROWS = [
    {"key": "plotTitle:1", "jp": "ある子が学校にくる物語", "kind": "plot_title", "file": "x"},
    {"key": "snr_x:1", "jp": "ある子が学校にくる物語", "kind": "scene_title", "file": "x"},
    {"key": "snr_x:2", "jp": "モデル訳が必要なシーンタイトル", "kind": "scene_title", "file": "x"},
    {"key": "snr_crd_1:1", "jp": "『ある子が学校にくる物語』のあらすじを作成しました。",
     "kind": "card_msg", "file": "x"},
    {"key": "snr_mainmenu:1:1", "jp": "タイトル", "kind": "savedata", "file": "x"},
    {"key": "snr_mainmenu:1:2", "jp": "", "kind": "savedata", "file": "x"},   # 空串——安全闸③
]

TRANSLATED_ROWS = [
    {"jp": "モデル訳が必要なシーンタイトル", "zh": "需要模型译文的场景标题", "note": ""},
    {"jp": "タイトル", "zh": "标题", "note": ""},
    {"jp": "", "zh": "", "note": "空串存档标题不译"},
]


@pytest.fixture
def idx():
    return build_card_indexes(CARDS_JP, CARDS_ZH)


@pytest.fixture
def translated_by_jp():
    return load_translated_by_jp(TRANSLATED_ROWS)


# ---------------------------------------------------------------------------
# load_translated_by_jp：jp 唯一性校验。
# ---------------------------------------------------------------------------

def test_load_translated_by_jp_builds_dict():
    d = load_translated_by_jp(TRANSLATED_ROWS)
    assert d["タイトル"]["zh"] == "标题"
    assert d[""]["zh"] == ""


def test_load_translated_by_jp_rejects_duplicate_jp():
    rows = [{"jp": "重复", "zh": "甲", "note": ""}, {"jp": "重复", "zh": "乙", "note": ""}]
    with pytest.raises(ValueError, match="重复"):
        load_translated_by_jp(rows)


# ---------------------------------------------------------------------------
# assemble_rows：derive_extra 能解的直接用；解不出的查 translated_by_jp；
# 查不到就 raise（不允许静默产出空 zh 冒充已译）。
# ---------------------------------------------------------------------------

def test_assemble_rows_covers_all_kinds_and_never_drops_a_row(idx, translated_by_jp):
    jp_by_card, zh_by_card, title_to_cards = idx
    rows = assemble_rows(LEDGER_ROWS, jp_by_card, zh_by_card, title_to_cards,
                          translated_by_jp, glossary_v=9, ts="2026-01-01T00:00:00+00:00")
    assert len(rows) == len(LEDGER_ROWS) == 6
    by_key = {r["key"]: r for r in rows}

    assert by_key["plotTitle:1"]["zh"] == "有个孩子来学校的故事"
    assert by_key["plotTitle:1"]["source"].startswith("cards.zh:card=1")

    assert by_key["snr_x:1"]["zh"] == "有个孩子来学校的故事"  # scene_title 精确匹配冻结卡名

    assert by_key["snr_x:2"]["zh"] == "需要模型译文的场景标题"
    assert by_key["snr_x:2"]["source"] == "model+review:data/extra_translated.jsonl"

    assert by_key["snr_crd_1:1"]["zh"] == "已写下『有个孩子来学校的故事』的梗概。"

    assert by_key["snr_mainmenu:1:1"]["zh"] == "标题"
    assert by_key["snr_mainmenu:1:1"]["source"] == "model+review:data/extra_translated.jsonl"


def test_assemble_rows_empty_savedata_string_is_kept_not_skipped(idx, translated_by_jp):
    """安全闸③核心用例：jp=="" 的 savedata 行必须仍然出现在输出里，zh=""，
    source 要能体现"这是复核裁定的合法空串"而不是"漏查"。"""
    jp_by_card, zh_by_card, title_to_cards = idx
    rows = assemble_rows(LEDGER_ROWS, jp_by_card, zh_by_card, title_to_cards,
                          translated_by_jp, glossary_v=9, ts="2026-01-01T00:00:00+00:00")
    by_key = {r["key"]: r for r in rows}
    assert "snr_mainmenu:1:2" in by_key
    row = by_key["snr_mainmenu:1:2"]
    assert row["zh"] == ""
    assert row["source"]  # source 非空——即便 zh 是空串
    assert "reviewed-empty" in row["source"]


def test_assemble_rows_raises_when_neither_derivable_nor_in_translated_map(idx, translated_by_jp):
    jp_by_card, zh_by_card, title_to_cards = idx
    bad_rows = LEDGER_ROWS + [
        {"key": "snr_x:99", "jp": "谁都没裁定过的场景标题", "kind": "scene_title", "file": "x"},
    ]
    with pytest.raises(ValueError, match="查不到"):
        assemble_rows(bad_rows, jp_by_card, zh_by_card, title_to_cards,
                      translated_by_jp, glossary_v=9, ts="2026-01-01T00:00:00+00:00")


# ---------------------------------------------------------------------------
# validate_forward_extra：行数 / key 集合 / 无重复 / source 非空。
# ---------------------------------------------------------------------------

def test_validate_forward_extra_happy_path(idx, translated_by_jp):
    jp_by_card, zh_by_card, title_to_cards = idx
    rows = assemble_rows(LEDGER_ROWS, jp_by_card, zh_by_card, title_to_cards,
                          translated_by_jp, glossary_v=9, ts="2026-01-01T00:00:00+00:00")
    assert validate_forward_extra(rows, LEDGER_ROWS) is True


def test_validate_forward_extra_rejects_row_count_mismatch():
    ledger = [{"key": "a:1", "jp": "x", "kind": "savedata"},
              {"key": "a:2", "jp": "y", "kind": "savedata"}]
    rows = [{"key": "a:1", "kind": "savedata", "zh": "", "source": "s", "glossary_v": 1, "ts": "t"}]
    with pytest.raises(AssertionError, match="行数不符"):
        validate_forward_extra(rows, ledger)


def test_validate_forward_extra_rejects_key_set_mismatch():
    """核心用例：key 集合与 ledger 不一致（这里 rows 用了一个 ledger 里没有的 key）
    却照样落盘——必须 raise，绝不能让"数字对得上但 key 对不上"蒙混过关。"""
    ledger = [{"key": "a:1", "jp": "x", "kind": "savedata"}]
    rows = [{"key": "a:WRONG", "kind": "savedata", "zh": "", "source": "s",
             "glossary_v": 1, "ts": "t"}]
    with pytest.raises(AssertionError, match="key 集合与 ledger_extra 不一致"):
        validate_forward_extra(rows, ledger)


def test_validate_forward_extra_rejects_duplicate_key():
    ledger = [{"key": "a:1", "jp": "x", "kind": "savedata"},
              {"key": "a:2", "jp": "y", "kind": "savedata"}]
    rows = [
        {"key": "a:1", "kind": "savedata", "zh": "", "source": "s", "glossary_v": 1, "ts": "t"},
        {"key": "a:1", "kind": "savedata", "zh": "", "source": "s", "glossary_v": 1, "ts": "t"},
    ]
    with pytest.raises(AssertionError, match="重复 key"):
        validate_forward_extra(rows, ledger)


def test_validate_forward_extra_rejects_missing_source():
    ledger = [{"key": "a:1", "jp": "x", "kind": "savedata"}]
    rows = [{"key": "a:1", "kind": "savedata", "zh": "", "source": "", "glossary_v": 1, "ts": "t"}]
    with pytest.raises(AssertionError, match="缺 source"):
        validate_forward_extra(rows, ledger)


# ---------------------------------------------------------------------------
# land()：append-only 落盘 + 冲突检测 + 落盘后回读校验。
# ---------------------------------------------------------------------------

def test_land_writes_new_file(tmp_path):
    path = tmp_path / "forward_extra.jsonl"
    rows = [{"key": "a:1", "kind": "savedata", "zh": "标题", "source": "s",
             "glossary_v": 1, "ts": "t"}]
    out = land(rows, path)
    assert out == path
    landed = read_jsonl(path)
    assert landed == rows


def test_land_appends_to_existing_file_without_key_overlap(tmp_path):
    path = tmp_path / "forward_extra.jsonl"
    write_jsonl(path, [{"key": "a:1", "kind": "savedata", "zh": "标题", "source": "s",
                          "glossary_v": 1, "ts": "t"}])
    new_rows = [{"key": "a:2", "kind": "savedata", "zh": "标题2", "source": "s",
                  "glossary_v": 1, "ts": "t"}]
    land(new_rows, path)
    landed = read_jsonl(path)
    assert [r["key"] for r in landed] == ["a:1", "a:2"]


def test_land_rejects_key_overlap_with_existing_file(tmp_path):
    """append-only 硬约束：与已落盘 key 重叠一律拒绝，不覆写。"""
    path = tmp_path / "forward_extra.jsonl"
    write_jsonl(path, [{"key": "a:1", "kind": "savedata", "zh": "旧译文", "source": "s",
                          "glossary_v": 1, "ts": "t"}])
    dup_rows = [{"key": "a:1", "kind": "savedata", "zh": "新译文（试图覆写）", "source": "s",
                  "glossary_v": 1, "ts": "t"}]
    with pytest.raises(ValueError, match="append-only 冲突"):
        land(dup_rows, path)
    # 拒绝后文件内容必须原封不动。
    landed = read_jsonl(path)
    assert len(landed) == 1
    assert landed[0]["zh"] == "旧译文"


# ---------------------------------------------------------------------------
# main()：CLI 端到端，跑在 tmp_path 上，绝不碰生产目录。
# ---------------------------------------------------------------------------

def test_main_check_mode_does_not_write(tmp_path):
    ledger_p = tmp_path / "ledger_extra.jsonl"
    write_jsonl(ledger_p, LEDGER_ROWS)
    cards_jp_p, cards_zh_p = tmp_path / "cards.jp.yaml", tmp_path / "cards.zh.yaml"
    cards_jp_p.write_text("- card: 1\n  title_jp: ある子が学校にくる物語\n", encoding="utf-8")
    cards_zh_p.write_text("- card: 1\n  title_zh: 有个孩子来学校的故事\n", encoding="utf-8")
    translated_p = tmp_path / "extra_translated.jsonl"
    write_jsonl(translated_p, TRANSLATED_ROWS)
    out_p = tmp_path / "forward_extra.jsonl"

    rc = main(["--ledger", str(ledger_p), "--cards-jp", str(cards_jp_p),
               "--cards-zh", str(cards_zh_p), "--translated", str(translated_p),
               "--out", str(out_p), "--check"])
    assert rc == 0
    assert not out_p.exists()


def test_main_lands_all_rows_with_matching_key_set(tmp_path):
    ledger_p = tmp_path / "ledger_extra.jsonl"
    write_jsonl(ledger_p, LEDGER_ROWS)
    cards_jp_p, cards_zh_p = tmp_path / "cards.jp.yaml", tmp_path / "cards.zh.yaml"
    cards_jp_p.write_text("- card: 1\n  title_jp: ある子が学校にくる物語\n", encoding="utf-8")
    cards_zh_p.write_text("- card: 1\n  title_zh: 有个孩子来学校的故事\n", encoding="utf-8")
    translated_p = tmp_path / "extra_translated.jsonl"
    write_jsonl(translated_p, TRANSLATED_ROWS)
    out_p = tmp_path / "forward_extra.jsonl"

    rc = main(["--ledger", str(ledger_p), "--cards-jp", str(cards_jp_p),
               "--cards-zh", str(cards_zh_p), "--translated", str(translated_p),
               "--out", str(out_p), "--ts", "2026-01-01T00:00:00+00:00"])
    assert rc == 0
    landed = read_jsonl(out_p)
    assert len(landed) == len(LEDGER_ROWS)
    assert {r["key"] for r in landed} == {r["key"] for r in LEDGER_ROWS}
    for r in landed:
        assert r["source"]
        assert "glossary_v" in r and isinstance(r["glossary_v"], int)
        assert r["ts"] == "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# 真实数据冒烟：对着真实 ledger_extra.jsonl + skeleton + data/extra_translated.jsonl
# 跑一遍 assemble+validate（只写 tmp_path，绝不碰 pilot/lanes/opus/data/），钉住
# "829 条一条不少不多、key 集合完全吻合" 这一硬约束。
# ---------------------------------------------------------------------------

def test_real_data_assemble_and_validate_829_rows_no_dup_no_missing():
    import yaml
    from tools.derive_extra import build_card_indexes as _bci

    ledger_rows = read_jsonl(REPO / "pilot/lanes/opus/data/ledger_extra.jsonl")
    cards_jp = yaml.safe_load((REPO / "skeleton/cards.jp.yaml").read_text(encoding="utf-8"))
    cards_zh = yaml.safe_load((REPO / "skeleton/cards.zh.yaml").read_text(encoding="utf-8"))
    jp_by_card, zh_by_card, title_to_cards = _bci(cards_jp, cards_zh)
    translated = load_translated_by_jp(read_jsonl(REPO / "data/extra_translated.jsonl"))

    rows = assemble_rows(ledger_rows, jp_by_card, zh_by_card, title_to_cards,
                          translated, glossary_v=1, ts="2026-01-01T00:00:00+00:00")
    assert validate_forward_extra(rows, ledger_rows) is True
    assert len(rows) == 829
    assert {r["key"] for r in rows} == {r["key"] for r in ledger_rows}
    assert all(r["zh"] == "" or r["zh"] for r in rows)  # 每行都是字符串（含合法空串）
    empty_zh = [r for r in rows if r["zh"] == ""]
    assert len(empty_zh) == 3  # 已知：仅 3 条 savedata 空串是合法的空 zh
