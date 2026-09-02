## Task 6: build_font 改造与 fonttools 依赖

**Files:**
- Modify: `tools/build_font.py`, `pyproject.toml`
- Modify: `tests/test_layers.py`

**Interfaces:**
- Consumes: Task 3 的 `write_charset`
- Produces: `build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]`

- [ ] **Step 1: 加依赖并确认可导入**

```bash
uv add fonttools
uv run python -c "import fontTools; print('fontTools', fontTools.version)"
```

Expected: 打印版本号。2026-09-02 实测 venv 里没有它，`widen_latin()` 当场 ImportError——
此前靠什么环境跑通没有记录。

- [ ] **Step 2: 写失败测试**

追加到 `tests/test_layers.py`：

```python
def test_build_font_reads_charset_file_not_lane(tmp_path, monkeypatch):
    """build() 的字集必须来自参数指定的文件——车道依赖已经拆掉了。"""
    import tools.build_font as bf
    ucs = tmp_path / "ucs.txt"
    ucs.write_text("0020\n4e00\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(bf, "TTF_PGF", tmp_path / "fake_ttf_pgf")
    (tmp_path / "fake_ttf_pgf").write_text("#!/bin/sh\ntouch \"$2\"\n", encoding="utf-8")
    (tmp_path / "fake_ttf_pgf").chmod(0o755)
    monkeypatch.setattr(bf, "widen_latin", lambda ttf, out: (calls.append(out), ttf)[1])
    out = bf.build(ucs, tmp_path / "out", sizes=(17,))
    assert out and out[0].name == "lxgw17.pgf"
    assert not hasattr(bf, "corpus_chars"), "corpus_chars 应当已删除（字集改由 layers 算）"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_layers.py -q -k build_font`
Expected: FAIL — `AttributeError: module 'tools.build_font' has no attribute 'build'`

- [ ] **Step 4: 实现**

在 `tools/build_font.py` 里删除 `corpus_chars()` 与 `LANE` 常量及对 `resolve_map` / `read_jsonl`
的 import（`ALWAYS` 保留，供 `tools/layers.py` 引用）。把 `main()` 的循环体抽成：

```python
def build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]:
    """按给定字集文件产 PGF。字集由 tools/layers.py 从 release 最终源算出。

    ⚠ 不再自己算字集：2026-09-02 的缺字事故就是因为它只看车道与账本，
    编外的谢幕章源不在视野里，6 个字进了盘却没有字形。
    """
    if not TTF_PGF.exists():
        sys.exit(f"缺 ttf_pgf: {TTF_PGF}（见 docs/ops/pgf-font-research-2026-08-31.md 重建；"
                 f"或设 SNDL_TTF_PGF）")
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for size in sizes:
        ttf = TTF_BY_SIZE.get(size, TTF_DEFAULT)
        if not ttf.exists():
            sys.exit(f"缺字体源: {ttf}")
        if size in WIDEN_SIZES:
            ttf = widen_latin(ttf, out_dir / f"_widened{size:02d}.ttf")
        render = ruby_size if (size in WIDEN_SIZES and ruby_size) else size
        out = out_dir / f"lxgw{size:02d}.pgf"
        proc = subprocess.run([str(TTF_PGF), str(ttf), str(out), str(charset_path),
                               str(render)], capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            sys.exit(f"ttf_pgf 失败({size}px): {proc.stdout[-500:]} {proc.stderr[-500:]}")
        print(f"[font] {size}px(渲染 {render}px) <- {ttf.name} -> {out} "
              f"({out.stat().st_size:,} B)")
        made.append(out)
    return made
```

`main()` 改为：解析 `--charset`（缺省 `build/release/charset.txt`）、`--out`、`--sizes`、
`--ruby-size`，调 `build()`。

- [ ] **Step 5: 跑测试与真实构建**

```bash
uv run pytest tests/test_layers.py -q -k build_font
uv run python tools/build_font.py --charset build/font/ucs.txt --out /tmp/font_check --sizes 17
cmp /tmp/font_check/lxgw17.pgf build/font/lxgw17.pgf && echo "与现役字体逐字节相同 ✓"
```

Expected: 测试 PASS；`cmp` 无输出并打印那句话——证明改造没有改变产物。

- [ ] **Step 6: 提交**

```bash
git add tools/build_font.py tests/test_layers.py pyproject.toml uv.lock
git commit -m "refactor: build_font 改为按给定字集构建 + fonttools 入依赖

删掉 corpus_chars()——它只看车道与账本，编外的谢幕章源不在视野里，这正是 2026-09-02
六个字进了盘却没字形的根因。字集改由 tools/layers.py 从 release 最终源算，build()
只管拿字集产 PGF。同时把 fonttools 补进 pyproject：venv 里一直没有它，widen_latin()
当场 ImportError，此前靠什么环境跑通没有记录。
改造后用现役字集重编，产物与现役 lxgw17.pgf 逐字节相同。

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

