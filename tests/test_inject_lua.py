"""注入核心的封闭测试。今日为零——而这是整条译文管线的心脏。"""
import pytest

from tools.inject_lua import inject_text, inject_tree, lua_quote, load_translations, merge_adjacent_ruby


def _rows(*specs):
    return {line: {"id": i, "literal": lit} for line, i, lit in specs}


def test_line_count_never_changes():
    src = 'a()\nvms(1, "NONVOICE", "あ")\nb()\n'
    out = inject_text("f", src, _rows((2, 1, True)), {1: "啊"}, {}, _stats())
    assert len(out.splitlines()) == len(src.splitlines())
    assert out.splitlines()[1].strip() == 'vms(1, "NONVOICE", "啊")'


def _stats():
    return dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0,
                font_slot1=0, ruby_merged=0)


def test_id_mismatch_between_source_and_ledger_is_hard_failure():
    src = 'vms(7, "NONVOICE", "あ")\n'
    with pytest.raises(SystemExit) as e:
        inject_text("f", src, _rows((1, 1, True)), {1: "啊"}, {}, _stats())
    assert "不同步" in str(e.value)


def test_missing_translation_leaves_source_untouched():
    src = 'vms(1, "NONVOICE", "あ")\n'
    st = _stats()
    out = inject_text("f", src, _rows((1, 1, True)), {}, {}, st)
    assert out == src and st["vms_missing"] == 1


def test_non_literal_row_substitutes_whole_expression():
    src = 'vms(1, "NONVOICE", "■デバッグ：" .. msg)\n'
    out = inject_text("f", src, _rows((1, 1, False)), {1: '"■调试：" .. msg'}, {}, _stats())
    assert out.strip() == 'vms(1, "NONVOICE", "■调试：" .. msg)'


def test_tr_line_comment_is_preserved():
    src = 'plotTitle[1] = "あ" -- tr_line:1\n'
    out = inject_text("f", src, {}, {}, {"plotTitle:1": "啊"}, _stats())
    assert out.strip() == 'plotTitle[1] = "啊" -- tr_line:1'


def test_lua_quote_escapes_backslash_and_quote():
    assert lua_quote(r'a"b\c') == r'"a\"b\\c"'


def test_merge_adjacent_ruby_joins_touching_groups():
    out, n = merge_adjacent_ruby("<胡,hú><萝,luó><卜,bo>")
    assert out == "<胡萝卜,húluóbo>" and n == 2


def test_merge_adjacent_ruby_leaves_separated_groups_alone():
    out, n = merge_adjacent_ruby("<哐,kuāng>当<哐,kuāng>当")
    assert n == 0 and out == "<哐,kuāng>当<哐,kuāng>当"


# ---- inject_tree：brief 只给了函数体没给测试，但它是本任务要「产出」的接口 ----

def test_inject_tree_walks_base_dir_and_aggregates_stats(tmp_path):
    """两个文件、一个有译文一个缺译——钉住 by_file 是按 (file,line) 分组，
    而不是把全部 ledger 行错配到每个文件上；stats 是整棵树的汇总而不是最后一个
    文件的孤本（_injected_sources 那种「每文件新建一份就地丢弃」是反例，不要学）。
    """
    (tmp_path / "a.lua").write_text('vms(1, "NONVOICE", "あ")\n', encoding="utf-8")
    (tmp_path / "b.lua").write_text('vms(2, "NONVOICE", "い")\n', encoding="utf-8")
    ledger_rows = [
        {"file": "a", "line": 1, "id": 1, "literal": True},
        {"file": "b", "line": 1, "id": 2, "literal": True},
    ]
    out, stats = inject_tree(tmp_path, ledger_rows, {1: "啊"}, {})

    assert set(out) == {"a.lua", "b.lua"}
    assert out["a.lua"].strip() == 'vms(1, "NONVOICE", "啊")'
    assert out["b.lua"].strip() == 'vms(2, "NONVOICE", "い")'   # 2 缺译，原样留下
    assert stats["vms"] == 1 and stats["vms_missing"] == 1


def test_inject_tree_is_pure_no_disk_writes_no_compile(tmp_path):
    """接口约束（task 描述原话）：不做字体改写、不编译、不写盘。用一个没有
    luac/不可写的目录都能跑通来证明——它只读源文件、返回内存字典。"""
    (tmp_path / "only.lua").write_text('x = 1\n', encoding="utf-8")
    out, stats = inject_tree(tmp_path, [], {}, {})
    assert out == {"only.lua": "x = 1\n"}
    assert list(tmp_path.iterdir()) == [tmp_path / "only.lua"]   # 没有新文件被创建
    assert "font_slot1" not in stats                             # 字体改写已不归这里管


# ---- load_translations：车道路径不再硬编码，改由 layers/manifest.toml 的 ----
# ---- [lane].dir 决定（tools.layers.load_manifest()）——这是本任务里，brief ----
# ---- 只说「删掉 LANE 常量」却没交代替代方案的那处缺口，补一个回归测试钉住。 ----

def test_load_translations_reads_lane_dir_from_manifest(tmp_path, monkeypatch):
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / "forward.jsonl").write_text('{"id": 1, "zh": "啊"}\n', encoding="utf-8")
    (lane / "patches.jsonl").write_text("", encoding="utf-8")
    (lane / "forward_extra.jsonl").write_text('{"key": "k", "zh": "乙"}\n', encoding="utf-8")

    import tools.inject_lua as inject_lua_mod
    monkeypatch.setattr(inject_lua_mod, "load_manifest",
                        lambda: {"lane": {"dir": str(lane)}})

    zh, extra = load_translations()
    assert zh == {1: "啊"}
    assert extra == {"k": "乙"}
