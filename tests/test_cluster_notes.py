"""提案预聚类：notes/*.md 散提案 → 按词族聚合的裁决卷宗（P3 spec §4 新工具）。"""
from tools.cluster_notes import parse_notes, cluster, extract_terms
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
