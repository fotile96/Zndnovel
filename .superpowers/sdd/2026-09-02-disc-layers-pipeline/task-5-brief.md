## Task 5: inject_lua 瘦身与补测试

**Files:**
- Modify: `tools/inject_lua.py`
- Create: `tests/test_inject_lua.py`

**Interfaces:**
- Consumes: 无
- Produces: `inject_tree(base_dir: Path, ledger_rows: list[dict], zh: dict[int, str], extra: dict[str, str]) -> tuple[dict[str, str], dict]` — 返回 `(文件名→注入后源, 统计)`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_inject_lua.py`：

```python
"""注入核心的封闭测试。今日为零——而这是整条译文管线的心脏。"""
import pytest

from tools.inject_lua import inject_text, lua_quote, merge_adjacent_ruby


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
```

- [ ] **Step 2: 跑测试确认表现**

Run: `uv run pytest tests/test_inject_lua.py -q`
Expected: 大部分 PASS（这些函数已存在），若有 FAIL 说明现有实现与预期不符，先查明再改测试或改实现。

- [ ] **Step 3: 抽出 inject_tree，删掉字体改写与编译**

在 `tools/inject_lua.py` 里：删除 `FONT_SLOT1_FROM` / `FONT_SLOT1_TO` 两个常量、`main()` 里的
`if stem == "snr_common" and FONT_SLOT1_FROM in text:` 三行（改由 `layers/overlays/fonts.toml` 承担）、
`compile_bytecode()` 函数、`LANE` / `OUT_SRC` / `OUT_BC` / `LUAC` / `PSP_LUAC_HEADER` 常量。新增：

```python
def inject_tree(base_dir: Path, ledger_rows: list[dict], zh: dict[int, str],
                extra: dict[str, str]) -> tuple[dict[str, str], dict]:
    """注入整棵基座，返回 (文件名→注入后源, 统计)。行数与行号严格不变。

    ⚠ 不做字体改写、不编译、不写盘——那些分别是 layers/overlays/fonts.toml 与
    build_disc 的职责。本函数是纯函数，好测。
    """
    by_file: dict[str, dict[int, dict]] = {}
    for row in ledger_rows:
        by_file.setdefault(row["file"], {})[row["line"]] = row
    stats = dict(vms=0, vms_missing=0, vms_unledgered=0, extra=0, extra_missing=0,
                 ruby_merged=0)
    out: dict[str, str] = {}
    for f in sorted(Path(base_dir).glob("*.lua")):
        out[f.name] = inject_text(f.stem, f.read_text(encoding="utf-8"),
                                  by_file.get(f.stem, {}), zh, extra, stats)
    return out, stats
```

`main()` 改为调用 `inject_tree` 并把结果写到 `--out` 指定目录（缺省
`build/release/lua/injected`），保留 `--only` 调试参数，去掉 `--no-compile`。

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/test_inject_lua.py -q
uv run python tools/inject_lua.py --out /tmp/inj_check
```

Expected: 测试全绿；注入报告 `vms 替换 16749（缺译 0，账本外 0）；extra 替换 875`。

- [ ] **Step 5: 提交**

```bash
git add tools/inject_lua.py tests/test_inject_lua.py
git commit -m "refactor: inject_lua 收缩为纯注入——字体改写与编译各归其位

抽出 inject_tree()（纯函数：基座 + 账本 + 译文 → 文件名到源的字典），删掉槽 1 字体
改写（迁 layers/overlays/fonts.toml）、luac 编译（迁 build_disc）、车道路径写死
（迁 manifest.toml）。补上今日缺失的注入核心测试：行数不变、id 不符硬失败、
literal=false 整表达式替换、tr_line 注释保真、ruby 合并两种情形。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

