from tools.check_voices_anchors import check, extract_citations, load_anchors, main


def _write_anchors(path, items):
    """items: [(id, zh), ...] -> 单章嵌套 yaml（真实 schema：
    [{chapter, items: [{id, zh, ...}]}]，不是平铺列表）。"""
    lines = ["- chapter: global", "  items:"]
    for cid, zh in items:
        lines.append(f"    - id: {cid}")
        lines.append(f'      zh: "{zh}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_anchors_reads_nested_chapter_items_schema(tmp_path):
    """anchors.yaml 是 [{chapter, items:[...]}] 嵌套结构——早前生产会话曾按平铺
    列表解析导致恒返回 0 命中，此处钉住正确的嵌套读法。"""
    p = tmp_path / "anchors.yaml"
    _write_anchors(p, [(10, "甲"), (20, "乙")])
    assert load_anchors(p) == {10: "甲", 20: "乙"}


def test_extract_citations_two_line_shape(tmp_path):
    md = tmp_path / "x.md"
    md.write_text(
        "1. [10]【甲】「にほんご」\n"
        "   → 【甲】「中文」\n",
        encoding="utf-8")
    assert extract_citations(md) == [(2, 10, "【甲】「中文」")]


def test_extract_citations_skips_multi_id_line(tmp_path):
    """多 id 合引行（如 [10][11]）是多句合译/旁注引用，无法安全拆分对应到单一
    zh——即便下一行确实以 → 开头，也必须跳过。"""
    md = tmp_path / "x.md"
    md.write_text(
        "1. [10][11]【甲】「にほんご」「べつのぶん」\n"
        "   → 【甲】「中文一」「中文二」\n",
        encoding="utf-8")
    assert extract_citations(md) == []


def test_extract_citations_skips_when_next_line_is_not_arrow(tmp_path):
    """三行体（id 行 / 日文另起一行 / → 译文再另起一行）不在本模块判据范围内——
    只认"下一行"，不去追第三行，避免跨行回溯带来的歧义。"""
    md = tmp_path / "x.md"
    md.write_text(
        "1. [10]（旁白）\n"
        "   にほんごだけのぶん。\n"
        "   → 中文只在第三行\n",
        encoding="utf-8")
    assert extract_citations(md) == []


def test_check_id_not_in_anchors_is_not_comparable(tmp_path):
    """anchors 里根本没有这个 id——没有比对对象，不算冲突，也不计入 comparable。"""
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "x.md").write_text(
        "1. [999]【甲】「にほんご」\n   → 【甲】「中文」\n", encoding="utf-8")
    anchors = tmp_path / "anchors.yaml"
    _write_anchors(anchors, [(10, "【甲】「甲」")])
    mismatches, n = check(voices, anchors)
    assert mismatches == []
    assert n == 0


def test_check_matches_when_zh_identical(tmp_path):
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "x.md").write_text(
        "1. [10]【甲】「にほんご」\n   → 【甲】「中文」\n", encoding="utf-8")
    anchors = tmp_path / "anchors.yaml"
    _write_anchors(anchors, [(10, "【甲】「中文」")])
    mismatches, n = check(voices, anchors)
    assert mismatches == []
    assert n == 1


def test_check_reports_mismatch_with_file_line_id_and_both_zh(tmp_path):
    """报错必须可操作：文件:行号、锚点 id、voices 写的、anchors 定稿的，四样
    都要能在报错文本里找到。"""
    voices = tmp_path / "voices"
    voices.mkdir()
    md = voices / "naoya.md"
    md.write_text(
        "1. [10]【甲】「にほんご」\n   → 【甲】「voices写的」\n", encoding="utf-8")
    anchors = tmp_path / "anchors.yaml"
    _write_anchors(anchors, [(10, "【甲】「anchors定稿」")])
    mismatches, n = check(voices, anchors)
    assert n == 1
    assert len(mismatches) == 1
    msg = mismatches[0]
    assert f"{md}:2:" in msg
    assert "10" in msg
    assert "voices写的" in msg
    assert "anchors定稿" in msg


def test_check_multi_id_line_not_reported_even_if_content_differs(tmp_path):
    """"多 id 合引行"情形：即便译文明显与 anchors 不同也不能报——判据须在
    "能否确定对应单一锚点 id"这一步就拦下，而不是先比对内容再决定报不报。"""
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "x.md").write_text(
        "1. [10][11]【甲】「にほんご」「もういっこ」\n"
        "   → 【甲】「和 anchors 完全不同的中文」\n",
        encoding="utf-8")
    anchors = tmp_path / "anchors.yaml"
    _write_anchors(anchors, [(10, "【甲】「中文」")])
    mismatches, n = check(voices, anchors)
    assert mismatches == []
    assert n == 0


def test_check_id_in_anchors_but_voices_only_quotes_japanese_not_reported(tmp_path):
    """"anchors 有该 id 但 voices 引的是日文"情形：voices 只引了原文、没给出
    对应译文示范（下一行不是 → 开头）——不算冲突，不计入 comparable。"""
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "x.md").write_text(
        "1. [10]【甲】「にほんご」（只引原文，未给译文示范）\n"
        "   这一行只是补充说明，不是译文\n",
        encoding="utf-8")
    anchors = tmp_path / "anchors.yaml"
    _write_anchors(anchors, [(10, "【甲】「anchors定稿」")])
    mismatches, n = check(voices, anchors)
    assert mismatches == []
    assert n == 0


def test_check_scans_all_md_files_in_voices_dir(tmp_path):
    voices = tmp_path / "voices"
    voices.mkdir()
    (voices / "b.md").write_text(
        "1. [20]【乙】「にほんご」\n   → 【乙】「乙中文」\n", encoding="utf-8")
    (voices / "a.md").write_text(
        "1. [10]【甲】「にほんご」\n   → 【甲】「甲中文」\n", encoding="utf-8")
    anchors = tmp_path / "anchors.yaml"
    _write_anchors(anchors, [(10, "【甲】「甲中文」"), (20, "【乙】「乙中文」")])
    mismatches, n = check(voices, anchors)
    assert mismatches == []
    assert n == 2


def test_main_returns_0_and_prints_ok_when_no_mismatch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("tools.check_voices_anchors.REPO", tmp_path)
    (tmp_path / "glossary" / "voices").mkdir(parents=True)
    (tmp_path / "skeleton").mkdir()
    (tmp_path / "glossary" / "voices" / "x.md").write_text(
        "1. [10]【甲】「にほんご」\n   → 【甲】「中文」\n", encoding="utf-8")
    _write_anchors(tmp_path / "skeleton" / "anchors.yaml", [(10, "【甲】「中文」")])
    assert main([]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_returns_1_and_prints_conflict_when_mismatch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("tools.check_voices_anchors.REPO", tmp_path)
    (tmp_path / "glossary" / "voices").mkdir(parents=True)
    (tmp_path / "skeleton").mkdir()
    (tmp_path / "glossary" / "voices" / "x.md").write_text(
        "1. [10]【甲】「にほんご」\n   → 【甲】「不同的中文」\n", encoding="utf-8")
    _write_anchors(tmp_path / "skeleton" / "anchors.yaml", [(10, "【甲】「中文」")])
    assert main([]) == 1
    assert "冲突" in capsys.readouterr().out
