"""提案预聚类：notes/*.md 散提案 → 按词族聚合的裁决卷宗（P3 spec §4 新工具）。"""
from tools.cluster_notes import parse_notes, cluster, extract_terms, item_terms
from tools.saturation import is_clean_key

NOTES = """# 术语提案 · s1s（opus 车道）

> 说明行。

## batch 4

### 1. 寝癖 → 睡翘的头发（**跨轨复现**）
- id 7327、7329
- 理由：略。

### 2. 菜单名的拉丁形态需要一条形态判据
- id 6632

### 3. 『ことば』(7302) → 『话语』
- 建议沿用。

## batch 7

### 1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质
- id 6351

### 2. ★存疑（非术语）：7374 的行宽警告
- 不是术语。

### 3. 寝癖 → 头发睡翘了
- 又一处。
"""


def test_parse_notes_blocks_and_batches():
    ps = parse_notes(NOTES, "s1s")
    assert len(ps) == 6
    assert [p["batch"] for p in ps] == [4, 4, 4, 7, 7, 7]
    assert ps[0]["chapter"] == "s1s" and ps[0]["num"] == 1
    assert "id 7327" in ps[0]["body"]
    assert ps[4]["starred"] is True


def test_extract_terms_variants():
    assert extract_terms("1. 寝癖 → 睡翘的头发（**跨轨复现**）") == ["寝癖"]
    assert extract_terms("3. 『ことば』(7302) → 『话语』") == ["ことば"]
    assert extract_terms("1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质") == ["海馬", "内嗅皮質"]
    assert extract_terms("2. 菜单名的拉丁形态需要一条形态判据") == []


def test_extract_terms_multi_arrow_returns_empty():
    # 顿号分隔的多词小族：多个 → 不当成一个词键解析，直接归未归词待人工过目
    assert extract_terms("5. 押し入れ→壁橱、付箋紙→便签") == []
    assert extract_terms("5. 押し入れ→壁橱、付箋紙→便签、リビング→客厅") == []


def test_extract_terms_single_arrow_regression_unaffected():
    # 回归闸：单箭头（含 / 并列）不受多箭头 guard 影响，行为不变
    assert extract_terms("1. 寝癖 → 睡翘的头发（**跨轨复现**）") == ["寝癖"]
    assert extract_terms("1. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质") == ["海馬", "内嗅皮質"]


def test_cluster_multi_arrow_title_buckets_unkeyed():
    ps = parse_notes(
        "## batch 1\n\n### 5. 押し入れ→壁橱、付箋紙→便签、リビング→客厅\n- 三词一并处理。\n",
        "s1s",
    )
    c = cluster(ps)
    assert ps[0]["terms"] == []
    assert len(c["（未归词）"]) == 1


def test_cluster_merges_across_batches_and_buckets_unkeyed():
    ps = parse_notes(NOTES, "s1s")
    c = cluster(ps)
    assert len(c["寝癖"]) == 2                       # batch 4 与 batch 7 合簇
    assert len(c["海馬"]) == 1 and len(c["内嗅皮質"]) == 1
    assert len(c["（未归词）"]) == 2                  # 无箭头 + ★存疑


def test_extract_terms_strips_backticks_and_desc_prefix():
    # 终审 C1：反引号/描述性冒号前缀不剥，键就成了 `首译定名：意識` 这种脏串，
    # 拿去 count 必得 0/0，而真词 意識 在 ledger 出现 55 次。
    assert extract_terms("1. 术语提案：`視聴覚室` → 视听教室") == ["視聴覚室"]
    assert extract_terms("2. 首译定名：`意識` → 意识") == ["意識"]
    assert extract_terms("3. 登记：`分岐` → 分岔") == ["分岐"]
    assert extract_terms("4. ≪結末≫ → 结局") == ["結末"]


def test_extract_terms_splits_fullwidth_slash():
    # 全角 ／ 此前留在键里，はい／いいえ 整串去 count 得 0，真词 はい 396 次
    assert extract_terms("1. はい／いいえ → 是／否") == ["はい", "いいえ"]
    assert extract_terms("2. 海馬 / 内嗅皮質 → 海马体 / 内嗅皮质") == ["海馬", "内嗅皮質"]


def test_is_clean_key_rejects_extraction_debris():
    # 语料字符集：本作原文里出现过的字符。简体中文字/裸 id/空白/纯标点都不该成键。
    corpus = set("寝癖意識はい物語カード")
    assert is_clean_key("寝癖", corpus, 3) is True
    assert is_clean_key("意識", corpus, 0) is True            # 短键零出现仍保留成词族
    assert is_clean_key("选项名", corpus, 0) is False          # 简体中文（语料里没有）
    assert is_clean_key("2470", corpus, 0) is False           # 裸 id
    assert is_clean_key("班级表记 ２のＤ", corpus, 0) is False   # 空白 + 中文
    assert is_clean_key("【】", set("【】"), 0) is False         # 纯标点，一个字都没有
    assert is_clean_key("物語カードはい意識寝癖", corpus, 0) is False  # 长键 + 零出现


def test_is_clean_key_total_gt_zero_short_circuits_whitespace_key():
    # P1 复评：`いつか きみが みる お話。` 带空格是绘本标题原文本身如此，
    # ledger 里出现 3 次——total>0 即有真实证据，不该被空白判据降级。
    corpus = set("いつかきみがみるお話。")
    assert is_clean_key("いつか きみが みる お話。", corpus, 3) is True


def test_is_clean_key_whitespace_key_zero_total_stays_dirty():
    # 反向：同样带空白，但 total==0（没有证据支撑）时，短路不生效，
    # 原有的空白判据照常把它判脏——回归闸防止短路被写宽。
    corpus = set("いつかきみがみるお話。")
    assert is_clean_key("いつか きみが みる お話。", corpus, 0) is False


def test_is_clean_key_ascii_gate_not_bypassed_by_total():
    # P3 devwave1 复评 Important 2：total>0 短路不能整体跳过 is_clean_key 的
    # 全部判据——ASCII_RE 保护的是「纯 ASCII/数字提取残渣」这另一类脏键，跟
    # 「有没有出现在语料里」是两件事。评审实测：ledger 里混有半角数字表达
    # （`12時`），子串 `"12"` 真能测出 total=1，若 ASCII 门也被豁免，`12` 这种
    # 一个字都不是词的裸 id 键会被判 clean。这里不依赖真实车道数据，直接构造
    # 「语料含半角数字、键是纯数字且 total>0」的最小复现。
    corpus = set("12時ですね")  # 语料含半角数字（对应真实 ledger 的「12時」现象）
    assert is_clean_key("12", corpus, 1) is False       # 命中「12時」的「12」，total>0 仍 dirty
    assert is_clean_key("882", corpus, 0) is False
    assert is_clean_key("2470", corpus, 0) is False


def test_five_review_cases_shape_check():
    # 复评点名的五个案例集中钉一遍，防止未来任何一次改动同时破坏其中几个。
    corpus_a = set("いつかきみがみるお話。ＴｒｕｅＣｏｌｏｒ")
    assert is_clean_key("いつか きみが みる お話。", corpus_a, 3) is True
    assert is_clean_key("ＴｒｕｅＣｏｌｏｒ", corpus_a, 1) is True
    corpus_b = set("12時ですね")
    assert is_clean_key("12", corpus_b, 1) is False
    assert is_clean_key("882", corpus_b, 0) is False
    assert is_clean_key("2470", corpus_b, 0) is False
    assert is_clean_key("【】", set("【】"), 0) is False
    assert is_clean_key("いつか きみが みる お話。", corpus_a, 0) is False


def test_batch_title_with_parenthetical_still_parsed():
    # 终审 I5：真实标题是 `## batch 33（scene_s2s_40「…」＋ …）`，锚死行尾会让
    # 提案丢批号，更坏的是**挂到上一个匹配上的批号**（外观正常但错）。
    ps = parse_notes(
        "## batch 33（scene_s2s_40「また、いつもの生活」＋ crd_41）\n\n"
        "### 1. 寝癖 → 睡翘的头发\n- x\n", "s2s")
    assert [p["batch"] for p in ps] == [33]


def test_main_never_renders_dirty_key_as_normal_family(tmp_path, capsys):
    import json
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(
        "## batch 4（附注）\n\n"
        "### 1. 登记：`寝癖` → 睡翘的头发\n- id 7327\n\n"
        "### 2. 建议入 active.json：选项名 → 选项名称\n- id 9999\n", encoding="utf-8")
    (lane / "data" / "ledger.jsonl").write_text(json.dumps(
        {"id": 7327, "jp": "寝癖がなおらない", "chapter": "s1s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 7327, "zh": "x"}), encoding="utf-8")
    assert main(["--lane-dir", str(lane)]) == 0
    out = capsys.readouterr().out
    assert "## 寝癖（1 条提案 | 饱和度 1/1=1.000 → **可裁决**）" in out  # 前缀剥干净
    assert "选项名（" not in out                                    # 脏键不成族
    assert "（未归词）" in out
    assert "无出现" not in out                                      # 措辞已改
    assert "bNone" not in out


def test_main_warns_on_empty_dossier(tmp_path, capsys):
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(
        "# 术语提案\n\n- 散记体 bullet：寝癖 → 睡翘的头发\n", encoding="utf-8")
    (lane / "data" / "ledger.jsonl").write_text("", encoding="utf-8")
    assert main(["--lane-dir", str(lane)]) == 0     # advisory 工具，仍 rc=0
    out = capsys.readouterr().out
    assert "解析出 0 条提案" in out
    assert "forward.jsonl 不存在" in out
    assert "已扫描 1 个 md" in out


def test_main_warns_on_empty_ledger(tmp_path, capsys):
    # P2 复评：ledger 为空/缺失时 corpus_chars 是空集，会让每个键都含
    # 「语料外字符」而全体降级——此前无任何点名 ledger 的告警，看起来像
    # 「本段提案都没法归词」，实际是数据源没读到。
    import json
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(
        "## batch 4\n\n### 1. 寝癖 → 睡翘的头发\n- id 7327\n", encoding="utf-8")
    (lane / "data" / "ledger.jsonl").write_text("", encoding="utf-8")  # 存在但空
    (lane / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 7327, "zh": "x"}), encoding="utf-8")
    assert main(["--lane-dir", str(lane)]) == 0
    out = capsys.readouterr().out
    assert "ledger.jsonl" in out and "没读到或为空" in out
    assert "全部词键将被降级" in out


def test_main_warns_on_missing_ledger_file(tmp_path, capsys):
    # 反面：ledger.jsonl 文件干脆不存在（新车道还没跑 build_ledger），
    # 同样要报警而不是 FileNotFoundError 崩溃。
    import json
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(
        "## batch 4\n\n### 1. 寝癖 → 睡翘的头发\n- id 7327\n", encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 7327, "zh": "x"}), encoding="utf-8")
    assert main(["--lane-dir", str(lane)]) == 0
    out = capsys.readouterr().out
    assert "ledger.jsonl" in out and "没读到或为空" in out


def test_main_renders_dossier(tmp_path, capsys):
    import json
    from tools.cluster_notes import main
    lane = tmp_path / "lane"
    (lane / "data" / "notes").mkdir(parents=True)
    (lane / "data" / "notes" / "s1s.md").write_text(NOTES, encoding="utf-8")
    (lane / "data" / "ledger.jsonl").write_text(json.dumps(
        {"id": 7327, "jp": "寝癖がなおらない", "chapter": "s1s"},
        ensure_ascii=False), encoding="utf-8")
    (lane / "data" / "forward.jsonl").write_text(
        json.dumps({"id": 7327, "zh": "x"}), encoding="utf-8")
    rc = main(["--lane-dir", str(lane), "--gate", "0.8"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "寝癖" in out and "可裁决" in out          # 1/1 覆盖 → ratio 1.0 ≥ gate
    assert "（未归词）" in out


# ---- 长对话（会话组）模式：容器标题之下的有序列表提案 ----
# 逐批 notes 一词一标题；长对话 notes 一批一节，提案落在
# `### 5. 术语提案（留给术语委员会）` 之下的有序列表里，标题一个词都没有。
# SEG-3 段末实测：s4s/s4fa/s4fb 的 34 条真提案在卷宗里一条都不成词。

CONTAINER = """## batch 115

### 5. 术语提案（留给术语委员会）

1. **`エンドロール`→片尾字幕**（12985，全库首次）。本句是比喻——
   建议登记为定译。
2. **`苦手` 建议进「按义二分词」表**：默认读**不擅长**（7222）；另一读**害怕**
   （对象是恐怖或生理性厌恶物，11658、本批 12714 `雷は苦手`）。
3. **首次出现、建议登记的一般名词**（全库此前无译例）：`銀婚式`→**银婚纪念**（12536）｜`シュノーケル`→**呼吸管**（12668）｜`ココア`→**可可**（12507）
4. **`まいった／参った`→统一「真伤脑筋」**（本批四处）。
5. **`【千秋】「はい」` 的分治口径**：肯定/确认前句→**「是」**；应承提议→**「好的」**。

### 6. 自查记录

| 批 | 行数 |
|---|---|
| 115 | 374 |
"""


def test_container_list_items_become_proposals():
    ps = parse_notes(CONTAINER, "s4fb")
    nums = [p["num"] for p in ps]
    assert nums == ["5.1", "5.2", "5.3", "5.4", "5.5", 6]   # 容器标题 5 自身不成条
    assert all(p["batch"] == 115 and p["chapter"] == "s4fb" for p in ps)
    assert ps[0]["terms"] == ["エンドロール"]
    assert "建议登记为定译" in ps[0]["body"]                # 续行归本条，不丢


def test_container_heading_itself_never_becomes_a_term_family():
    """「术语提案（留给术语委员会）」「自查记录」是分节名，不该成词族/成条。"""
    ps = parse_notes(CONTAINER, "s4fb")
    assert not any("术语提案" in str(p["title"]) for p in ps)
    c = cluster(ps)
    assert not any("术语提案" in k or "自查" in k for k in c)


def test_item_terms_structural_criterion():
    # (a) 粗体内的反引号片段
    assert item_terms("**`エンドロール`→片尾字幕**（12985）。") == ["エンドロール"]
    # (b) 反引号片段后紧跟 →**译文**（并列写法，一条列表项多个词）
    assert item_terms("**一般名词**：`銀婚式`→**银婚纪念**｜`ココア`→**可可**") \
        == ["銀婚式", "ココア"]
    # 两条都不满足 = 正文里随手引用的原文，不成词
    assert item_terms("默认读**不擅长**；另一读**害怕**（11658、12714 `雷は苦手`）。") == []
    assert item_terms("（13137 `現実が物語のストーリーを追う`→「现实追着情节」）") == []
    # 并列分隔与说话人标签
    assert item_terms("**`まいった／参った`→统一「真伤脑筋」**") == ["まいった", "参った"]
    assert item_terms("**`【千秋】「はい」` 的分治口径**：肯定→**「是」**") == ["はい"]


def test_container_item_multi_term_all_clustered():
    ps = parse_notes(CONTAINER, "s4fb")
    c = cluster(ps)
    for k in ("エンドロール", "苦手", "銀婚式", "シュノーケル", "ココア",
              "まいった", "参った", "はい"):
        assert len(c[k]) == 1, k
    assert "雷は苦手" not in c            # 正文引用不成词


PLAIN = """## batch 4

### 1. 寝癖 → 睡翘的头发
- id 7327

### 2. 处理步骤（散文编号列表，不是提案）

1. 先核对 id 集合。
2. 再跑 check_batch。
3. 最后入库。
"""


def test_plain_ordered_list_without_convention_is_left_as_body():
    """无「反引号原文＋粗体译文」约定的编号列表照旧只当正文——
    这是逐批模式不受影响的结构性保证（不靠关键词白名单）。"""
    ps = parse_notes(PLAIN, "s1s")
    assert [p["num"] for p in ps] == [1, 2]
    assert "先核对 id 集合" in ps[1]["body"]
    assert ps[1]["terms"] == []


def test_batchwise_notes_parse_byte_identical():
    """逐批体 notes 的解析结果逐字不变（回归闸：新分支恒等映射）。"""
    ps = parse_notes(NOTES, "s1s")
    assert [(p["num"], p["title"], p["terms"], p["body"], p["batch"]) for p in ps] == [
        (1, "寝癖 → 睡翘的头发（**跨轨复现**）", ["寝癖"], "- id 7327、7329\n- 理由：略。\n\n", 4),
        (2, "菜单名的拉丁形态需要一条形态判据", [], "- id 6632\n\n", 4),
        # 末条 body 多吞一个空行是既有行为（`## batch` 行只更新批号、不断开 body），
        # 这里照实钉住——回归闸的意义在于「不变」，不在于「好看」。
        (3, "『ことば』(7302) → 『话语』", ["ことば"], "- 建议沿用。\n\n\n", 4),
        (1, "海馬 / 内嗅皮質 → 海马体 / 内嗅皮质", ["海馬", "内嗅皮質"], "- id 6351\n\n", 7),
        (2, "★存疑（非术语）：7374 的行宽警告", [], "- 不是术语。\n\n", 7),
        (3, "寝癖 → 头发睡翘了", ["寝癖"], "- 又一处。\n", 7),
    ]


def test_container_with_own_term_in_title_keeps_both():
    """标题自带词（`### 6. 术语提案｜`カウンター` 建议…` 实况）时标题不被吞掉。"""
    ps = parse_notes(
        "## batch 1\n\n### 6. `カウンター` → 吧台\n\n"
        "1. **`ウイスキー`→威士忌**（13268）。\n", "s4fb")
    assert [p["num"] for p in ps] == [6, "6.1"]
    assert ps[0]["terms"] == ["カウンター"] and ps[1]["terms"] == ["ウイスキー"]


def test_container_intro_prose_is_not_dropped():
    ps = parse_notes(
        "## batch 1\n\n### 5. 术语提案\n\n本节共 1 条，均为全库首次。\n\n"
        "1. **`ウイスキー`→威士忌**（13268）。\n", "s4fb")
    assert [p["num"] for p in ps] == ["5.1"]
    assert "本节共 1 条" in ps[0]["body"]


# ---- 表格体（第三种书写结构，2026-08-05 新增）----

_TABLE_MD = """# s6s 译者手记

## 术语提案

| 批次 | id | 原文关键词 | 建议译法 | 理由 |
|---|---|---|---|---|
| 139 | 15523 | `『いつもの』` | **『老样子』** | 全库首见 |
| 145 | 15638 | `『お話の案』` | **『故事的草案』** | 封面题字 |

## 【维护者记录】段末裁决回改

| 批次 | id | 原文 | 本批译法 | 依据 |
|---|---|---|---|---|
| 139 | 1 | `テスト` | **测试** | 记录性，不请求裁决 |
"""


def test_table_proposals_are_parsed_and_classified_by_container():
    from tools.cluster_notes import parse_tables
    props, unparsed = parse_tables(_TABLE_MD, "s6s")
    assert unparsed == []
    props_kind = [p for p in props if p["kind"] == "proposal"]
    records = [p for p in props if p["kind"] == "record"]
    assert len(props_kind) == 2, props
    assert len(records) == 1, "【维护者记录】容器下的表必须判为记录性，不进裁决面"
    assert props_kind[0]["terms"] == ["いつもの"], props_kind[0]["terms"]
    assert props_kind[1]["terms"] == ["お話の案"], props_kind[1]["terms"]


def test_table_batch_comes_from_the_batch_column():
    """表格常写在不带 `## batch N` 的容器下，只靠 BATCH_RE 会整表渲染成 bNone。"""
    from tools.cluster_notes import parse_tables
    props, _ = parse_tables(_TABLE_MD, "s6s")
    assert [p["batch"] for p in props if p["kind"] == "proposal"] == [139, 145]


def test_unrecognised_table_is_reported_not_silently_dropped():
    """认不出列结构时必须给出诊断——静默才是表格体五个段无人察觉的原因。"""
    from tools.cluster_notes import parse_tables
    md = "## 自查记录\n\n| 批 | 行数 | warn |\n|---|---|---|\n| 139 | 22 | 0 |\n"
    props, unparsed = parse_tables(md, "s6s")
    assert props == []
    assert len(unparsed) == 1 and unparsed[0]["rows"] == 1
    assert unparsed[0]["header"] == ["批", "行数", "warn"]


def test_classify_container_defaults_to_unknown_not_a_guess():
    from tools.cluster_notes import classify_container
    assert classify_container("术语提案") == "proposal"
    assert classify_container("1. 术语提案（请裁）") == "proposal"
    assert classify_container("【维护者记录】段末裁决回改") == "record", \
        "同时含「裁决」与「记录」时必须判记录——记录性关键词优先"
    assert classify_container("6. 自查记录（四批）") == "record"
    assert classify_container("batch 127（109 行）") == "unknown", \
        "认不出就说不知道，不许默认猜成 proposal 或 record"


def test_table_parsing_does_not_disturb_title_or_list_forms():
    """既有两条判据必须逐字不受影响：表格行两条都匹配不到。"""
    from tools.cluster_notes import parse_notes
    assert parse_notes(_TABLE_MD, "s6s") == []
