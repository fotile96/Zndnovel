### Task 1: `umdiso.add_files` —— 往既有目录追加新文件

**Files:**
- Modify: `tools/umdiso.py`（`replace()` 之后新增 `add_files()`；`main()` 注册 `add` 子命令；模块 docstring 用法段加一行）
- Test: `tests/test_umdiso.py`

**Interfaces:**
- Produces: `add_files(iso_path: str, adds: list[tuple[str, str]], log=print) -> None` —— **就地**修改 `iso_path`；`adds=[(盘内路径, 本地文件)]`，盘内路径的父目录必须已存在、文件名不得已存在。新记录克隆父目录里第一条文件记录（日期、XA 尾、命名风格：兄弟名带 `;1` 就加 `;1`，否则原样），按名字节序插入；数据按 2048 对齐追加到原卷尾；PVD 卷总扇区相应增加。目录区（单扇区）放不下时 `raise ValueError`。

- [ ] **Step 1: 写失败测试**（接在 `test_replace_in_subdir` 之后）

```python
def test_add_file_into_subdir(tmp_path):
    from tools.umdiso import add_files
    iso_path = tmp_path / "t.iso"
    contents = make_iso(iso_path)
    new = tmp_path / "NEW.BIN"
    payload = bytes((i * 31 + 5) % 256 for i in range(5000))
    new.write_bytes(payload)
    before_sectors = os.path.getsize(iso_path) // SECTOR
    add_files(str(iso_path), [("/SUB/FILE_A2.BIN", str(new))], log=lambda *_: None)
    got = all_files(iso_path)
    assert got["/SUB/FILE_A2.BIN"] == payload
    for k, v in contents.items():
        assert got[k] == v
    assert os.path.getsize(iso_path) // SECTOR == before_sectors + 3   # 5000 B → 3 扇区
    assert verify(str(iso_path), log=lambda *_: None)
    with Iso(str(iso_path)) as iso:
        names = [r.name for r in iso.records if r.path.startswith("/SUB/")]
    assert names == ["FILE_A2.BIN;1", "FILE_B.BIN;1"]            # 按名字节序、克隆 ;1 风格


def test_add_file_rejects_existing_name(tmp_path):
    from tools.umdiso import add_files
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    f = tmp_path / "x"; f.write_bytes(b"x")
    with pytest.raises(ValueError, match="已存在"):
        add_files(str(iso_path), [("/SUB/FILE_B.BIN", str(f))], log=lambda *_: None)


def test_add_file_rejects_missing_parent(tmp_path):
    from tools.umdiso import add_files
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    f = tmp_path / "x"; f.write_bytes(b"x")
    with pytest.raises(ValueError, match="父目录"):
        add_files(str(iso_path), [("/NOPE/A.BIN", str(f))], log=lambda *_: None)


def test_add_file_rejects_full_directory_sector(tmp_path):
    from tools.umdiso import add_files
    iso_path = tmp_path / "t.iso"
    make_iso(iso_path)
    f = tmp_path / "x"; f.write_bytes(b"x")
    adds = [(f"/SUB/F{i:04d}_{'X' * 60}.BIN", str(f)) for i in range(40)]  # ~100 B/条 × 40 > 2048
    with pytest.raises(ValueError, match="放不下"):
        add_files(str(iso_path), adds, log=lambda *_: None)
    assert verify(str(iso_path), log=lambda *_: None)             # 失败时不得写坏原盘


@needs_iso
def test_real_module_dir_record_style():
    """真盘 module/ 目录：小写名、无 ;1、每条带 14 字节 XA 尾——add_files 靠克隆兄弟记录保持同款。"""
    with Iso(str(ORIG_ISO)) as iso:
        rec = iso.find("/PSP_GAME/USRDIR/module/libfont.prx")
        assert rec.name == "libfont.prx"
        iso.f.seek(rec.pos)
        raw = iso.f.read(58)
    assert raw[0] == 58 and raw[33 + 11:][-14:][4:8] == b"\x0dUXA"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_umdiso.py -k "add_file or module_dir" -v`
Expected: 前四条 FAIL（`ImportError: cannot import name 'add_files'`），第五条 PASS（只读真盘）。

- [ ] **Step 3: 实现**（`tools/umdiso.py`，`_copy_range` 之前）

```python
def _clone_record(template: bytes, name: bytes, lba: int, size: int) -> bytes:
    """按兄弟文件记录的格式造一条新记录：日期/标志/卷序号/系统使用区（XA 尾）照抄，只换名字、LBA、大小。"""
    tnlen = template[DR_NAMELEN]
    sys_use = template[DR_NAME + tnlen + ((tnlen + 1) & 1):]      # 名字后的对齐填充之后
    head = bytearray(template[:DR_NAME])
    body = bytearray(head) + name
    if len(body) % 2:
        body += b"\0"
    body += sys_use
    _put_both(body, DR_EXTENT, lba)
    _put_both(body, DR_SIZE, size)
    body[DR_NAMELEN] = len(name)
    body[0] = len(body)
    return bytes(body)


def add_files(iso_path: str, adds: list[tuple[str, str]], log=print) -> None:
    """就地往既有目录追加新文件：数据按 2048 对齐追加到卷尾，父目录（单扇区）插入按名排序的新记录，
    PVD 卷总扇区相应增加。其余字节一律不动——追加在卷尾，不需要平移任何扇区号引用。"""
    with Iso(iso_path) as iso:
        vol = iso.volume_sectors
        if iso.size != vol * SECTOR:
            raise ValueError(f"文件大小 {iso.size} 与卷总扇区 {vol} 不符，拒绝追加")
        by_dir: dict[int, list] = {}
        plan = []
        next_lba = vol
        for inner, local in adds:
            parent, _, leaf = inner.rstrip("/").rpartition("/")
            parent = parent or "/"
            if parent == "/":
                dir_lba, dir_size = iso.root_lba, iso.root_size
            else:
                d = [r for r in iso.records if r.is_dir and r.path == parent]
                if not d:
                    raise ValueError(f"父目录不存在: {parent}")
                dir_lba, dir_size = d[0].lba, d[0].size
            siblings = [r for r in iso.records if not r.is_dir and r.dir_lba == dir_lba]
            if any(r.path == inner.split(";")[0] for r in siblings) or \
               any(p[0] == inner for p in plan):
                raise ValueError(f"盘内已存在: {inner}")
            if not siblings:
                raise ValueError(f"{parent} 里没有可克隆格式的兄弟文件记录")
            size = os.path.getsize(local)
            style_v1 = siblings[0].name.endswith(";1")
            name = (leaf + (";1" if style_v1 else "")).encode("ascii")
            rlen = iso._read_at(siblings[0].pos, 1)[0]
            template = iso._read_at(siblings[0].pos, rlen)
            rec = _clone_record(template, name, next_lba, size)
            plan.append((inner, local, size, next_lba))
            by_dir.setdefault((dir_lba, dir_size), []).append((name, rec))
            next_lba += (size + SECTOR - 1) // SECTOR

        new_dirs = {}
        for (dir_lba, dir_size), new_recs in by_dir.items():
            if dir_size != SECTOR:
                raise ValueError(f"目录区 LBA {dir_lba} 占 {dir_size} 字节，本工具只支持单扇区目录")
            data = iso._read_at(dir_lba * SECTOR, SECTOR)
            recs, off = [], 0
            while off < SECTOR and data[off]:
                recs.append(data[off:off + data[off]])
                off += data[off]
            dots, files = recs[:2], recs[2:]
            key = lambda r: r[DR_NAME:DR_NAME + r[DR_NAMELEN]]
            merged = sorted(files + [r for _, r in new_recs], key=key)
            blob = b"".join(dots + merged)
            if len(blob) > SECTOR:
                raise ValueError(f"目录区 LBA {dir_lba} 放不下新记录（需要 {len(blob)} 字节）")
            new_dirs[dir_lba] = blob.ljust(SECTOR, b"\0")
        pvd = bytearray(iso.pvd)
        _put_both(pvd, PVD_VOL_SPACE, next_lba)

    with open(iso_path, "r+b") as out:
        out.seek(vol * SECTOR)
        for inner, local, size, lba in plan:
            assert out.tell() == lba * SECTOR
            with open(local, "rb") as g:
                written = _copy_stream(g, out)
            out.write(b"\0" * ((-written) % SECTOR))
            log(f"  + {inner}: {size} 字节 @ LBA {lba}")
        for dir_lba, blob in new_dirs.items():
            out.seek(dir_lba * SECTOR)
            out.write(blob)
        out.seek(PVD_LBA * SECTOR)
        out.write(pvd)
    log(f"  卷总扇区 {vol} → {next_lba}")
```

`main()` 里注册子命令（照 `replace` 的写法）：

```python
    p = sub.add_parser("add", help="就地往既有目录追加新文件（数据追加卷尾）")
    p.add_argument("iso")
    p.add_argument("items", nargs="+", help="<盘内路径> <本地文件> 成对给出")
    p.set_defaults(func=cmd_add)
```

```python
def cmd_add(args):
    if len(args.items) % 2:
        sys.exit("add 需要成对的 <盘内路径> <本地文件>")
    pairs = list(zip(args.items[::2], args.items[1::2]))
    add_files(args.iso, pairs)
    return 0 if verify(args.iso) else 1
```

模块 docstring 用法段追加：`python3 tools/umdiso.py add     <iso> <盘内路径> <本地文件> [...]   # 就地追加新文件`

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_umdiso.py -v`
Expected: 全部 PASS（含原有用例）。

- [ ] **Step 5: 提交**

```bash
git add tools/umdiso.py tests/test_umdiso.py
git commit -m "feat: umdiso 新增 add——往既有目录追加新文件（数据追加卷尾、克隆兄弟记录格式、按名插入）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

