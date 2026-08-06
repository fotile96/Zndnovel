

def test_add_announces_when_the_id_already_has_a_patch(tmp_path, capsys):
    """把「先 grep 查有没有被裁过」这条靠记忆的纪律换成工具自己出声。

    grep 式查重实测对 17 条带空格体的老 patch 恒返回 0（`{"id": 10662,`），
    据此判「没被裁过」再补一条 patch，就是 SEG-5 那次 id 1600 误覆盖已裁定稿的
    同一失败模式。
    """
    from tools.add_patch import add
    d = tmp_path / "data"
    d.mkdir()
    add(7, "旧译", "review", 9, data=d)
    capsys.readouterr()
    prior = add(7, "新译", "recall", 13, data=d)
    err = capsys.readouterr().err
    assert len(prior) == 1
    assert "已有 1 条 patch" in err and "旧译" in err, err


def test_add_is_quiet_for_a_fresh_id(tmp_path, capsys):
    from tools.add_patch import add
    d = tmp_path / "data"
    d.mkdir()
    assert add(7, "首次", "review", 9, data=d) == []
    assert capsys.readouterr().err == ""


def test_existing_patches_parses_json_and_ignores_separator_style(tmp_path):
    """带空格体与紧凑体必须一视同仁——分隔符混用正是 grep 漏判的成因。"""
    from tools.add_patch import existing_patches
    d = tmp_path / "data"
    d.mkdir()
    (d / "patches.jsonl").write_text(
        '{"id": 10662, "zh": "带空格体", "reason": "recall", "glossary_v": 9}\n'
        '{"id":2378,"zh":"紧凑体","reason":"review","glossary_v":10}\n', encoding="utf-8")
    assert [r["zh"] for r in existing_patches(10662, d)] == ["带空格体"]
    assert [r["zh"] for r in existing_patches(2378, d)] == ["紧凑体"]


def test_has_patch_query_mode_writes_nothing(tmp_path, monkeypatch):
    from tools.add_patch import main
    d = tmp_path / "data"
    d.mkdir()
    (d / "patches.jsonl").write_text(
        '{"id":5,"zh":"甲","reason":"review","glossary_v":9}\n', encoding="utf-8")
    before = (d / "patches.jsonl").read_text(encoding="utf-8")
    assert main(["--id", "5", "--has-patch", "--data-dir", str(d)]) == 0
    assert main(["--id", "6", "--has-patch", "--data-dir", str(d)]) == 1
    assert (d / "patches.jsonl").read_text(encoding="utf-8") == before
