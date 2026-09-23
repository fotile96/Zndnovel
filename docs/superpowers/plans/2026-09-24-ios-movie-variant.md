# iOS 变体盘（PPSSPP 1.20.x 可播 OP/ED）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `build/movie_debug/` 里实验跑通的「改库名走 LLE」方案落成仓库内可复现的出盘流程：`build_disc.py --ios` 在现行发布盘之外另出 `build/dist/game_zh_ios.iso`（仅推荐 iOS 商店版 PPSSPP 用户），并附 CFW 实机行为的轻量评估。

**Architecture:** 现行发布盘一字不变；iOS 变体只在 `--ios` 时产生，复用同一次调用里已过发布断言的 DATA.BIN/SOUND.BIN，另加三样东西：①EBOOT 多施加一层 `layers/eboot/ios-movie.toml`（层 profile = `ios`，只有 `--ios` 才施加）；②两个改名并打补丁的固件模块（源为本作 UMD 自带 6.20 升级包解密出的 `assets/fw/*.dec.prx`，不入库、指纹钉 manifest）；③音轨重采样为 44.1 kHz 的 op/ed（视频流原样拷贝，FFmpeg 配方与产物指纹钉 manifest）。ISO 侧 `umdiso.replace` 换 EBOOT/DATA/SOUND/两部影片，新写的 `umdiso.add_files` 把两个模块追加到卷尾并插入 `module/` 目录记录。

**Tech Stack:** Python ≥3.12（uv）、纯 stdlib + 现有 `tools/mips_asm.py`；FFmpeg（本机 9.0.1，Homebrew）；PPSSPP v1.20.4 本机构建 `~/ppsspp-1204` 与最新 master `~/ppsspp-new` 供驾驶验证；驾驶分析用 `uv run --with numpy`。

**Spec:** `docs/ops/movie-playback-ppsspp-2026-09-24.md` 的「追记：iOS（商店版 1.20.4）——改库名走 LLE，实验已跑通」一节（M1–M3、E1–E4、V1 表与实测）+ 用户 2026-09-24 裁定：①产品化；②接受随 iOS 盘分发改过的 Sony 固件模块；③两个平行版本，hack 版只推荐 iOS 商店版 PPSSPP，其余平台与实机用现行版；CFW 行为做轻量评估，用户稍后亲测实机。

## Global Constraints

- 现行发布盘（`build_disc.py` 缺省）产物必须与本计划开工前**逐字节相同**：`ios` 层不得进入 release/test 两个剖面的 EBOOT。
- `lua_scripts/`、`png/` 只读；EBOOT 改动只经 `layers/eboot/*.toml`；替换带重定位条目的字必须同时把条目改成 R_MIPS_NONE（runbook §0 第 2 条）。
- 版权物（解密 EBOOT、解密固件模块、原盘影片）只放 `assets/`（gitignore），以 sha256 钉在 `layers/manifest.toml`；不入库。
- 新增工具保持纯 stdlib（+ 仓库既有 `tools/mips_asm.py`）；numpy 只在驾驶分析里用，调用方式 `uv run --with numpy`。
- iOS 盘文件名固定 `build/dist/game_zh_ios.iso`，只能由 `--ios` 且同一次调用里 `iso` 阶段断言通过后写出。
- commit 规范：`type: 中文摘要`，末尾 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`；工具代码与数据分开提交；不 push。

## Review Focus

1. **iOS 层泄漏进现行盘**：任何人只跑 `build_disc.py`（不带 `--ios`）时 EBOOT 必须与开工前相同——Task 4 加测试：`load_layers(order, profile="release")` 不含 ios 层、且对纯净源施加的结果 sha256 等于开工前记录值。
2. **目录扇区放不下 / 名字排序错**：`add_files` 在父目录扇区剩余不足或重名时必须硬失败而不是写坏 ISO——Task 1 加「塞满目录后再加」与「重名」两条失败测试，并测插入后按名字节序排列。
3. **FFmpeg 升级导致影片字节漂移**：产物 sha256 与 manifest 不符时要给出「FFmpeg 版本变了，重跑 1.20.4 驾驶后再更新指纹」的明确报错，而不是静默出盘——Task 3 加 monkeypatch 测试。
4. **iOS 盘跑在装了固件的新版 PPSSPP 上**：条件包装必须原样传 NULL ringbuffer——Task 7 驾驶在新版上读 `sceMpegCreate` 调用点的 `$a6`，断言 ≠ 0x10000000。
5. **旧产物冒充**：`--ios` 却没在同一次调用里跑 `iso`（release）/`disc`（test）时必须拒绝——Task 5 加测试。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `tools/umdiso.py` | 改 | 新增 `add_files()` 与 CLI `add`：数据追加卷尾、父目录插记录（按兄弟记录的格式克隆）、改 PVD 卷大小 |
| `tests/test_umdiso.py` | 改 | 合成 ISO 上测 add；真盘门控测 `module/` 目录格式（小写无 `;1`、带 XA 尾） |
| `tools/ios_fwmod.py` | 新 | PRX 表解析（导出/导入、type-B 重定位解码）+ `patch_mp4msv()` / `patch_libmp4()` + CLI `build` |
| `tests/test_ios_fwmod.py` | 新 | 有 `assets/fw/` 时核对重定位统计、补丁后表项与跳板字、产物指纹 |
| `tools/ios_movie.py` | 新 | 从原盘抽 op/ed → FFmpeg 配方重采样 44.1k（视频 copy）→ 结构核验 + 指纹核对 |
| `tests/test_ios_movie.py` | 新 | 配方常量、指纹不符报错（monkeypatch）、门控的真产物核验 |
| `tools/eboot_patch.py` | 改 | 层 profile 增 `ios`；`load_layers(..., ios=False)` |
| `tools/ios_eboot.py` | 新 | 生成 `layers/eboot/ios-movie.toml`（E1–E4 + 两条重定位 NONE） |
| `layers/eboot/ios-movie.toml` | 新（生成） | iOS 专用 EBOOT 层 |
| `tests/test_ios_eboot.py` | 新 | 重生成与入库逐字相同、洞内重定位全部 NONE、调用点仍带 R26、release 不含本层 |
| `tools/layers.py` | 改 | `_MANIFEST_KEYS` 加 `ios`；`_check_eboot` 另核 ios 层锚点 |
| `layers/manifest.toml` | 改 | `[eboot].order` 末尾加 `ios-movie`；新增 `[ios]` 节 |
| `tools/testboot.py`、`tools/build_disc.py` | 改 | movie 模式加 `--movie op|ed`、`--skippable`；`--ios` 开关与 `ios` 阶段 |
| `tests/test_testboot.py`、`tests/test_build_disc.py` | 改 | 上述参数与前置条件测试 |
| `tools/emu/legacy.py` | 新 | PPSSPP 1.20.x 会话（ini 开调试器、固定端口、可选核心/开机暂停），退出还原 ini |
| `tools/emu/movielab.py` | 新 | 影片音画分析：帧匹配、录音局部对齐、汇总判定 |
| `tools/emu/drives/movie_probe.py` | 新 | 驾驶：DumpAudio + 定时截 fb0/fb1 + 录音长度 → movielab 判定 PASS/FAIL |
| `tests/test_movielab.py` | 新 | 合成信号上测对齐与判定（无 numpy 时 skip） |
| `docs/ops/disc-pipeline.md`、`docs/ops/movie-playback-ppsspp-2026-09-24.md`、`tools/emu/drives/README.md`、`CLAUDE.md` | 改 | 命令面、实测记录、CFW 评估、玩家说明要点 |

资产（不入库）：`assets/fw/libmp4.dec.prx`（sha256 `ffa4c7e46f0be68e653b7230e39049b78013b8172bb43f5482bae5d7f10c240e`）、`assets/fw/mp4msv.dec.prx`（`f9639c746ba4690cfea0342bdd62ad3c68f2d911a5985c4303d200b08a880bf5`），首次从 `build/movie_debug/fw/` 拷入；重取方法写进 Task 8 的文档。

---

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

### Task 2: 固件模块补丁工具 `tools/ios_fwmod.py`

**Files:**
- Create: `tools/ios_fwmod.py`
- Test: `tests/test_ios_fwmod.py`

**Interfaces:**
- Produces:
  - `relocs_b(elf: bytes) -> list[tuple[int, int]]`：type-B（PT 0x700000A1）重定位的 `(site_va, type)` 列表（type：2=R32、4=HI16、5=LO16、6=J26、7=JAL26）。
  - `patch_mp4msv(data: bytes) -> bytes`、`patch_libmp4(data: bytes) -> bytes`：输入 sha256 不符即 `raise ValueError`。
  - 常量 `LIBMP4_IN_SHA`、`MP4MSV_IN_SHA`、`LIBMP4_OUT_SHA`、`MP4MSV_OUT_SHA`、`LIB_EXPORT = "zndMp4"`、`MSV_EXPORT = "zndmsv"`。
  - `build(out_dir: Path, fw_dir: Path = REPO/"assets"/"fw") -> dict[str, Path]` → `{"libmp4.prx": …, "mp4msv.prx": …}`，写出后核对输出指纹。

- [ ] **Step 1: 放资产**

```bash
mkdir -p assets/fw && cp build/movie_debug/fw/libmp4.dec.prx build/movie_debug/fw/mp4msv.dec.prx assets/fw/
shasum -a 256 assets/fw/*.dec.prx
```
Expected: 两行指纹分别为 `ffa4c7e4…240e`（libmp4）与 `f9639c74…0bf5`（mp4msv）。

- [ ] **Step 2: 写失败测试** `tests/test_ios_fwmod.py`

```python
"""tools/ios_fwmod.py：固件 libmp4/mp4msv 改库名 + 1.20.x 兼容补丁（有 assets/fw/ 才跑真件）。"""
import struct
from pathlib import Path

import pytest

from tools import ios_fwmod as fm

FW = Path(__file__).resolve().parents[1] / "assets" / "fw"
needs_fw = pytest.mark.skipif(not (FW / "libmp4.dec.prx").exists(), reason="assets/fw 不在（版权物）")


def test_input_sha_mismatch_is_hard_error():
    with pytest.raises(ValueError, match="sha256"):
        fm.patch_libmp4(b"\0" * 64)


@needs_fw
def test_relocs_b_decodes_libmp4():
    rs = fm.relocs_b((FW / "libmp4.dec.prx").read_bytes())
    assert len(rs) == 903
    sites = dict(rs)
    assert sites[0x487C] == 7                   # jal sceAudiocodecDecode（JAL26）
    assert not any(0x6054 <= s < 0x6054 + 4 * 14 for s, _ in rs)   # 跳板区无重定位


@needs_fw
def test_patched_tables_and_trampoline():
    out = fm.patch_libmp4((FW / "libmp4.dec.prx").read_bytes())
    ex, im = fm.exports(out), fm.imports(out)
    assert fm.LIB_EXPORT in ex and "sceMp4" not in ex
    assert fm.MSV_EXPORT in im and "mp4msv" not in im
    assert im["ModuleMgrForUser"]["count"] == 0
    w = lambda va: struct.unpack_from("<I", out, fm.text_off(out) + va)[0]
    assert w(0x487C) == 0x0C000000 | (0x6054 >> 2)          # jal → 跳板
    assert w(0x72A8) == 0x03E00008 and w(0x72AC) == 0x2402FFFF  # jr ra; li v0,-1
    assert fm.sha256(out) == fm.LIBMP4_OUT_SHA


@needs_fw
def test_mp4msv_export_renamed():
    out = fm.patch_mp4msv((FW / "mp4msv.dec.prx").read_bytes())
    assert fm.MSV_EXPORT in fm.exports(out)
    assert fm.sha256(out) == fm.MP4MSV_OUT_SHA
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_ios_fwmod.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'tools.ios_fwmod'`）。

- [ ] **Step 4: 实现** `tools/ios_fwmod.py`（`relocs_b` 移植自已验证的 `build/movie_debug/prx_relocs.py`；补丁逻辑移植自 `build/movie_debug/patch_libmp4.py`）

```python
#!/usr/bin/env python3
"""iOS 变体用的固件模块补丁：libmp4.prx / mp4msv.prx（本作 UMD 自带 6.20 升级包解密出的 Sony 模块）。

为什么（docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」M1–M3）：
  M1 PPSSPP 1.20.x 的 HLE 表里有 sceMp4/mp4msv（空桩），EBOOT 的导入会被钉死在上面。两侧改库名
     （sceMp4→zndMp4、mp4msv→zndmsv，同长度原地改）后，1.20.x 把导入暂存、真模块加载时补绑。
  M2 1.20.x 的 sceAudiocodecDecode 拿输出字段 srcBytesRead(0x1C) 当 AAC 输入长度，首帧为 0 → 永远静音。
     把 0x487C 的 jal sceAudiocodecDecode 改指向跳板（游戏不用的导出 sceMp4GetAvcAuWithoutSampleBuf 入口
     0x6054，前 14 字无重定位）：srcBytesRead = byte[0x2C] ? 0x609 : 0x600（同上游 b561de3f），再 b 回导入桩。
  M3 ModuleMgrForUser::0xD2FBC957（取回调 gp，1.20.x 缺）导入计数清零、桩改 jr ra; li v0,-1 → libmp4 走
     自带兜底（取当前 gp）。

用法：uv run python tools/ios_fwmod.py build [--out build/ios/module]
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.mips_asm import assemble  # noqa: E402

LIBMP4_IN_SHA = "ffa4c7e46f0be68e653b7230e39049b78013b8172bb43f5482bae5d7f10c240e"
MP4MSV_IN_SHA = "f9639c746ba4690cfea0342bdd62ad3c68f2d911a5985c4303d200b08a880bf5"
LIBMP4_OUT_SHA = "55916c14e7eee56a13f33af0e82eed9145ee328cc249bfdccedec36999908298"
MP4MSV_OUT_SHA = "cf9e3df024f7a56544bcb5146cd12155387e857caa4e5ab4db0b7750500c5ccd"
LIB_EXPORT, MSV_EXPORT = "zndMp4", "zndmsv"

AAC_CALL, AAC_STUB, TRAMP = 0x487C, 0x7450, 0x6054
GP_NID, GP_STUB = 0xD2FBC957, 0x72A8


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ph(b: bytes) -> list[tuple]:
    phoff, = struct.unpack_from("<I", b, 0x1C)
    phnum, = struct.unpack_from("<H", b, 0x2C)
    return [struct.unpack_from("<8I", b, phoff + 32 * i) for i in range(phnum)]


def text_off(b: bytes) -> int:
    return _ph(b)[0][1]


def _modinfo(b: bytes) -> tuple[int, int, int, int]:
    mi = _ph(b)[0][3] & 0x7FFFFFFF
    _gp, et, ee, st, se = struct.unpack_from("<5I", b, mi + 32)
    return et, ee, st, se


def _cstr(b: bytes, va: int) -> str:
    o = text_off(b) + va
    return b[o:b.index(b"\0", o)].decode()


def exports(b: bytes) -> dict[str, dict]:
    et, ee, _, _ = _modinfo(b)
    out, va, t = {}, et, text_off(b)
    while va < ee:
        nm, _v, _a, elen, vc, fc, tab = struct.unpack_from("<IHHBBHI", b, t + va)
        if nm:
            out[_cstr(b, nm)] = {"entry": va, "name_va": nm, "funcs": fc, "vars": vc, "tab": tab}
        va += elen * 4
    return out


def imports(b: bytes) -> dict[str, dict]:
    _, _, st, se = _modinfo(b)
    out, va, t = {}, st, text_off(b)
    while va < se:
        nm, _v, _a, elen, _vc, sc, nidtab, stubtab = struct.unpack_from("<IHHBBHII", b, t + va)
        out[_cstr(b, nm)] = {"entry": va, "name_va": nm, "count": sc, "nidtab": nidtab, "stubtab": stubtab}
        va += elen * 4
    return out


def relocs_b(b: bytes) -> list[tuple[int, int]]:
    """PT 0x700000A1（type-B）重定位解码，移植自 PPSSPP ElfReader::LoadRelocations2。"""
    ph = _ph(b)
    rel_seg = next(i for i, p in enumerate(ph) if p[0] == 0x700000A1)
    seg_va = [p[2] for p in ph]
    buf = b[ph[rel_seg][1]:ph[rel_seg][1] + ph[rel_seg][4]]
    flag_bits, type_bits = buf[2], buf[3]
    seg_bits = 1
    while (1 << seg_bits) < rel_seg:
        seg_bits += 1
    i = 4
    flag_table = buf[i:i + buf[i]]; i += buf[i]
    type_table = buf[i:i + buf[i]]; i += buf[i]
    rel_base = off_seg = 0
    out = []
    while i < len(buf):
        cmd = struct.unpack_from("<H", buf, i)[0]; i += 2
        flag = flag_table[((cmd << (16 - flag_bits)) & 0xFFFF) >> (16 - flag_bits)]
        seg = ((cmd << (16 - seg_bits - flag_bits)) & 0xFFFF) >> (16 - seg_bits)
        typ = type_table[((cmd << (16 - type_bits - seg_bits - flag_bits)) & 0xFFFF) >> (16 - type_bits)]
        if (flag & 1) == 0:
            off_seg = seg
            if (flag & 6) == 0:
                rel_base = cmd >> (seg_bits + flag_bits)
            elif (flag & 6) == 4:
                rel_base = struct.unpack_from("<I", buf, i)[0]; i += 4
            continue
        shift = type_bits + seg_bits + flag_bits
        signed = cmd - 0x10000 if cmd & 0x8000 else cmd
        if (flag & 6) == 0:
            rel_base += signed >> shift
        elif (flag & 6) == 2:
            rel_base += ((signed >> shift) << 16) | buf[i] | (buf[i + 1] << 8); i += 2
        elif (flag & 6) == 4:
            rel_base = struct.unpack_from("<I", buf, i)[0]; i += 4
        if (flag & 0x38) == 0x10:
            i += 2                                          # 行内 lo16，本工具只需站点
        out.append(((rel_base + seg_va[off_seg]) & 0xFFFFFFFF, typ))
    return out


def _rename(b: bytearray, name_va: int, old: str, new: str) -> None:
    assert len(old) == len(new)
    o = text_off(b) + name_va
    if bytes(b[o:o + len(old) + 1]) != old.encode() + b"\0":
        raise ValueError(f"库名锚点不符：{name_va:#x} 处不是 {old!r}")
    b[o:o + len(new)] = new.encode()


def patch_mp4msv(data: bytes) -> bytes:
    if sha256(data) != MP4MSV_IN_SHA:
        raise ValueError("mp4msv 输入 sha256 与登记不符")
    b = bytearray(data)
    _rename(b, exports(data)["mp4msv"]["name_va"], "mp4msv", MSV_EXPORT)
    return bytes(b)


def patch_libmp4(data: bytes) -> bytes:
    if sha256(data) != LIBMP4_IN_SHA:
        raise ValueError("libmp4 输入 sha256 与登记不符")
    b = bytearray(data)
    t = text_off(data)
    rel = dict(relocs_b(data))
    _rename(b, exports(data)["sceMp4"]["name_va"], "sceMp4", LIB_EXPORT)
    _rename(b, imports(data)["mp4msv"]["name_va"], "mp4msv", MSV_EXPORT)
    # M2：AAC 输入长度跳板
    assert not any(TRAMP <= s < TRAMP + 32 for s in rel), "跳板区含重定位"
    lines = ["li t6, 0x600", "lbu t7, 0x2C(a0)", f"beqz t7, {TRAMP + 0x14:#x}", "nop",
             "li t6, 0x609", f"b {AAC_STUB:#x}", "sw t6, 0x1C(a0)"]
    for k, line in enumerate(lines):
        pc = TRAMP + 4 * k
        struct.pack_into("<I", b, t + pc, struct.unpack("<I", assemble([line], pc))[0])
    old = struct.unpack_from("<I", b, t + AAC_CALL)[0]
    if rel.get(AAC_CALL) != 7 or old != (0x0C000000 | (AAC_STUB >> 2)):
        raise ValueError(f"{AAC_CALL:#x} 不是带 JAL26 重定位的 jal sceAudiocodecDecode")
    struct.pack_into("<I", b, t + AAC_CALL, 0x0C000000 | (TRAMP >> 2))
    # M3：0xD2FBC957 导入去掉、桩改 jr ra; li v0,-1
    mm = imports(data)["ModuleMgrForUser"]
    if mm["count"] != 1 or struct.unpack_from("<I", data, t + mm["nidtab"])[0] != GP_NID \
            or mm["stubtab"] != GP_STUB:
        raise ValueError("ModuleMgrForUser 导入不是预期的单条 0xD2FBC957")
    struct.pack_into("<H", b, t + mm["entry"] + 10, 0)
    struct.pack_into("<II", b, t + GP_STUB, 0x03E00008, 0x2402FFFF)
    return bytes(b)


def build(out_dir: Path, fw_dir: Path = REPO / "assets" / "fw") -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, fn, want in (("libmp4.prx", patch_libmp4, LIBMP4_OUT_SHA),
                           ("mp4msv.prx", patch_mp4msv, MP4MSV_OUT_SHA)):
        src = fw_dir / name.replace(".prx", ".dec.prx")
        if not src.exists():
            raise SystemExit(f"缺 {src}（取得方法见 docs/ops/movie-playback-ppsspp-2026-09-24.md「固件模块的取得」）")
        out = fn(src.read_bytes())
        if sha256(out) != want:
            raise SystemExit(f"{name} 产物 sha256 {sha256(out)} 与登记 {want} 不符")
        (out_dir / name).write_bytes(out)
        res[name] = out_dir / name
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--out", type=Path, default=REPO / "build" / "ios" / "module")
    a = ap.parse_args(argv)
    for k, v in build(a.out).items():
        print(f"{k} → {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_ios_fwmod.py -v`
Expected: 4 PASS。若 `test_patched_tables_and_trampoline` 的产物指纹不等于 `55916c14…8298`，逐字比对 `build/movie_debug/fw/libmp4.ios.prx` 找差异，修代码而不是改指纹。

- [ ] **Step 6: 提交**

```bash
git add tools/ios_fwmod.py tests/test_ios_fwmod.py
git commit -m "feat: ios_fwmod——固件 libmp4/mp4msv 改库名与 1.20.x 兼容补丁（AAC 输入长度跳板、GP 桩兜底），type-B 重定位解码

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 44.1 kHz 影片 `tools/ios_movie.py`

**Files:**
- Create: `tools/ios_movie.py`
- Test: `tests/test_ios_movie.py`

**Interfaces:**
- Produces:
  - `FFMPEG_ARGS: list[str]`（不含输入输出）= `["-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", "-brand", "MSNV", "-fflags", "+bitexact", "-flags:a", "+bitexact", "-f", "mp4"]`
  - `resample(src: Path, dst: Path) -> None`（跑 FFmpeg）
  - `probe(mp4: Path) -> dict`（`{"video": "h264 480x272", "audio_rate": 44100, "audio_codec": "aac", "channels": 2}`，用 ffprobe JSON）
  - `video_md5(mp4: Path) -> str`（`ffmpeg -i X -map 0:v:0 -c copy -f md5 -`）
  - `build(out_dir: Path, pins: dict[str, str], orig_iso: Path) -> dict[str, Path]`：从原盘抽 `movie/op.mp4`、`movie/ed.mp4` → 重采样 → 核验（音轨 44100/aac/2ch、视频 md5 与原片相同）→ 产物 sha256 与 `pins[名]` 比对，不符 `SystemExit`，报错里带 FFmpeg 版本。产物已存在且指纹相符则跳过（缓存）。

- [ ] **Step 1: 写失败测试** `tests/test_ios_movie.py`

```python
"""tools/ios_movie.py：op/ed 音轨重采样 44.1k（视频原样）+ 指纹钉住。"""
import shutil
from pathlib import Path

import pytest

from tools import ios_movie as im

ORIG = Path(__file__).resolve().parents[1] / "assets" / "orig.iso"
needs_media = pytest.mark.skipif(not ORIG.exists() or not shutil.which("ffmpeg"),
                                 reason="需要 assets/orig.iso 与 ffmpeg")


def test_recipe_keeps_video_and_resamples_audio():
    a = im.FFMPEG_ARGS
    assert a[a.index("-c:v") + 1] == "copy" and a[a.index("-ar") + 1] == "44100"
    assert "+bitexact" in a


def test_pin_mismatch_names_ffmpeg_version(tmp_path, monkeypatch):
    monkeypatch.setattr(im, "_extract", lambda iso, inner, dst: dst.write_bytes(b"src"))
    monkeypatch.setattr(im, "resample", lambda s, d: d.write_bytes(b"out"))
    monkeypatch.setattr(im, "probe", lambda p: {"audio_rate": 44100, "audio_codec": "aac", "channels": 2,
                                                "video": "h264 480x272"})
    monkeypatch.setattr(im, "video_md5", lambda p: "same")
    monkeypatch.setattr(im, "ffmpeg_version", lambda: "ffmpeg version 99.9")
    with pytest.raises(SystemExit, match="99.9"):
        im.build(tmp_path, {"op.mp4": "0" * 64, "ed.mp4": "0" * 64}, ORIG)


@needs_media
def test_real_op_resample_structure(tmp_path):
    src = tmp_path / "op.mp4"
    im._extract(ORIG, "/PSP_GAME/USRDIR/movie/op.mp4", src)
    dst = tmp_path / "op44.mp4"
    im.resample(src, dst)
    p = im.probe(dst)
    assert (p["audio_rate"], p["audio_codec"], p["channels"]) == (44100, "aac", 2)
    assert im.video_md5(dst) == im.video_md5(src)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_ios_movie.py -v`
Expected: FAIL（`No module named 'tools.ios_movie'`）。

- [ ] **Step 3: 实现** `tools/ios_movie.py`

```python
#!/usr/bin/env python3
"""iOS 变体的 op/ed：音轨重采样 AAC-LC 44.1 kHz，视频流原样拷贝。

为什么（docs/ops/movie-playback-ppsspp-2026-09-24.md V1）：PPSSPP 1.20.x 的混音器对 48 kHz vaudio 做 SRC
时按 128 值一块弹出 139 值（截断且为奇数）→ 慢 0.229% 且每 1.45 ms 左右声道错位＝破音。游戏按音轨采样率开
vaudio（全局 IDA 0x39CE3C），音轨是 44.1k 时不走 SRC。产物指纹钉在 layers/manifest.toml [ios.movies]；
FFmpeg 升级导致字节变化时硬失败，先用 tools/emu/drives/movie_probe.py 在 1.20.4 上复测再更新指纹。

用法：uv run python tools/ios_movie.py build
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

MOVIES = {"op.mp4": "/PSP_GAME/USRDIR/movie/op.mp4", "ed.mp4": "/PSP_GAME/USRDIR/movie/ed.mp4"}
FFMPEG_ARGS = ["-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-ar", "44100",
               "-ac", "2", "-b:a", "160k", "-brand", "MSNV", "-fflags", "+bitexact",
               "-flags:a", "+bitexact", "-f", "mp4"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ffmpeg_version() -> str:
    return subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True,
                          check=True).stdout.splitlines()[0]


def _extract(iso: Path, inner: str, dst: Path) -> None:
    from tools.umdiso import Iso, SECTOR
    with Iso(str(iso)) as f:
        rec = f.find(inner)
        f.f.seek(rec.lba * SECTOR)
        dst.write_bytes(f.f.read(rec.size))


def resample(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    *FFMPEG_ARGS, str(dst)], check=True)


def probe(mp4: Path) -> dict:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(mp4)],
                                  capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    return {"video": f"{v['codec_name']} {v['width']}x{v['height']}", "audio_codec": a["codec_name"],
            "audio_rate": int(a["sample_rate"]), "channels": int(a["channels"])}


def video_md5(mp4: Path) -> str:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-map", "0:v:0", "-c", "copy",
                          "-f", "md5", "-"], capture_output=True, text=True, check=True).stdout
    return out.strip()


def build(out_dir: Path, pins: dict[str, str], orig_iso: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, inner in MOVIES.items():
        dst = out_dir / name
        if dst.exists() and _sha(dst) == pins[name]:
            res[name] = dst
            continue
        src = out_dir / f"{name}.orig"
        _extract(orig_iso, inner, src)
        resample(src, dst)
        p = probe(dst)
        if (p["audio_rate"], p["audio_codec"], p["channels"]) != (44100, "aac", 2):
            raise SystemExit(f"{name}: 音轨不是 44.1k AAC 立体声：{p}")
        if video_md5(dst) != video_md5(src):
            raise SystemExit(f"{name}: 视频流与原片不一致（应为原样拷贝）")
        got = _sha(dst)
        if got != pins[name]:
            raise SystemExit(f"{name}: 产物 sha256 {got} 与登记 {pins[name]} 不符（{ffmpeg_version()}）——"
                             "FFmpeg 变了就先在 PPSSPP 1.20.4 上跑 movie_probe 复测，再更新 manifest [ios.movies]")
        src.unlink()
        res[name] = dst
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--out", type=Path, default=REPO / "build" / "ios" / "movie")
    a = ap.parse_args(argv)
    from tools import layers
    pins = layers.load_manifest()["ios"]["movies"]
    for k, v in build(a.out, pins, REPO / "assets" / "orig.iso").items():
        print(f"{k} → {v}（{_sha(v)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_ios_movie.py -v`
Expected: 3 PASS（第三条约 20 s）。

- [ ] **Step 5: 取得产物指纹**（Task 5 写 manifest 时用；这一步只记录，不写文件）

```bash
uv run python -c "
from pathlib import Path; import hashlib
from tools import ios_movie as im
d = Path('build/ios/movie'); d.mkdir(parents=True, exist_ok=True)
for n, inner in im.MOVIES.items():
    s = d / (n + '.orig'); im._extract(Path('assets/orig.iso'), inner, s); im.resample(s, d / n); s.unlink()
    print(n, hashlib.sha256((d / n).read_bytes()).hexdigest())
print(im.ffmpeg_version())"
```
Expected: 打印 op/ed 两个 sha256 与 FFmpeg 版本行，抄入 Task 5 Step 3 的 manifest。

- [ ] **Step 6: 提交**

```bash
git add tools/ios_movie.py tests/test_ios_movie.py
git commit -m "feat: ios_movie——op/ed 音轨重采样 44.1k（视频原样拷贝、bitexact），产物指纹钉 manifest

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: EBOOT iOS 层（`eboot_patch` 支持 `ios` 层 + 生成器 + 层文件）

**Files:**
- Modify: `tools/eboot_patch.py`（`_LAYER_KEYS` 不变；新增 `LAYER_PROFILES = ("release", "test", "ios")`；`load_layer` 校验改用它；`load_layers(order, root=None, profile="release", *, ios=False)`：层 profile 为 `ios` 时只在 `ios=True` 施加）
- Modify: `tools/layers.py`（`_check_eboot` 额外 `load_layers(..., ios=True)` 核对锚点；`_MANIFEST_KEYS` 加 `"ios"`）
- Create: `tools/ios_eboot.py`、`layers/eboot/ios-movie.toml`（生成）
- Modify: `layers/manifest.toml`（`[eboot].order` 末尾加 `"ios-movie"`）
- Test: `tests/test_ios_eboot.py`、`tests/test_eboot_patch.py`

**Interfaces:**
- Consumes: `tools/mips_asm.assemble`；`tools/eboot_patch.load_layers/apply/sha256`。
- Produces: `tools/ios_eboot.render_layer(pristine: bytes) -> str`；常量 `CAVE = 0x624C8`、`WRAP_AVC = 0x625D8`、`WRAP_CREATE = 0x6262C`、`CALLS = {0xB470: CAVE, 0xB4F4: WRAP_CREATE, 0xEA94: WRAP_AVC}`、`RELOC_NONE = (0x84188, 0x84198)`、`IMPORT_NAME_VA = 0x657D0`；`eboot_patch.load_layers(..., ios=True)`。

- [ ] **Step 1: 记下开工前现行 EBOOT 指纹**（Review Focus 1 的基准）

```bash
uv run python -c "
from tools import eboot_patch as ep, layers
m = layers.load_manifest()['eboot']
out, _ = ep.apply(open(m['source'],'rb').read(), ep.load_layers(m['order'], profile='release'))
print(ep.sha256(out))"
```
Expected: 一行 sha256，抄进 Step 2 测试的 `RELEASE_EBOOT_SHA`。

- [ ] **Step 2: 写失败测试** `tests/test_ios_eboot.py`

```python
"""layers/eboot/ios-movie.toml 由 tools/ios_eboot.py 生成（E1–E4，见 movie-playback 文档「追记：iOS」）。"""
import struct
from pathlib import Path

import pytest

from tools import eboot_patch as ep
from tools import ios_eboot as ie
from tools import layers

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "assets" / "EBOOT.dec.elf"
needs_src = pytest.mark.skipif(not SRC.exists(), reason="assets/EBOOT.dec.elf 不在")
RELEASE_EBOOT_SHA = "<Step 1 打印的值>"


def _relocs(elf: bytes):
    shoff, = struct.unpack_from("<I", elf, 32)
    shentsize, shnum = struct.unpack_from("<HH", elf, 46)
    for i in range(shnum):
        _, t, _, _, off, size = struct.unpack_from("<6I", elf, shoff + i * shentsize)
        if t == 0x700000A0:
            for j in range(size // 8):
                r_off, r_info = struct.unpack_from("<II", elf, off + 8 * j)
                yield off + 8 * j, r_off, r_info & 0xFF


@needs_src
def test_regenerated_layer_matches_committed():
    assert ie.render_layer(SRC.read_bytes()) == (REPO / "layers/eboot/ios-movie.toml").read_text(encoding="utf-8")


@needs_src
def test_release_profile_excludes_ios_layer_and_is_unchanged():
    m = layers.load_manifest()["eboot"]
    rel = ep.load_layers(m["order"], profile="release")
    assert not any(p.layer == "ios-movie" for p in rel)
    out, _ = ep.apply(SRC.read_bytes(), rel)
    assert ep.sha256(out) == RELEASE_EBOOT_SHA


@needs_src
def test_ios_build_neutralizes_every_reloc_in_used_cave_and_keeps_call_relocs():
    m = layers.load_manifest()["eboot"]
    out, _ = ep.apply(SRC.read_bytes(), ep.load_layers(m["order"], profile="release", ios=True))
    used_end = ie.WRAP_CREATE + 4 * len(ie.CREATE_LISTING)
    for fo, r_off, typ in _relocs(out):
        if ie.CAVE <= r_off < used_end:
            assert typ == 0, f"洞内 {r_off:#x} 的重定位（表项 {fo:#x}）没有改成 NONE"
        if r_off in ie.CALLS:
            assert typ == 4, f"调用点 {r_off:#x} 必须保留 R_MIPS_26"
    for site, target in ie.CALLS.items():
        w = struct.unpack_from("<I", out, site + 0xC0)[0]
        assert w == 0x0C000000 | (target >> 2)
    assert out[ie.IMPORT_NAME_VA + 0xC0: ie.IMPORT_NAME_VA + 0xC0 + 7] == b"zndMp4\0"
```

`tests/test_eboot_patch.py` 追加：

```python
def test_ios_layers_only_with_ios_flag(tmp_path):
    (tmp_path / "a.toml").write_text('why = "x"\nprofile = "ios"\n[[patches]]\nva = "0x10"\nfrom = "00"\nto = "01"\n',
                                     encoding="utf-8")
    assert ep.load_layers(["a"], root=tmp_path, profile="release") == []
    assert len(ep.load_layers(["a"], root=tmp_path, profile="release", ios=True)) == 1
```

（`ep` 为该测试文件既有的 `from tools import eboot_patch as ep` 别名；若既有别名不同，照用既有别名。）

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_ios_eboot.py tests/test_eboot_patch.py -v`
Expected: FAIL（`No module named 'tools.ios_eboot'`；`load_layers() got an unexpected keyword argument 'ios'`）。

- [ ] **Step 4: 改 `tools/eboot_patch.py`**

```python
LAYER_PROFILES = ("release", "test", "ios")   # 层的适用范围；构建剖面仍是 PROFILES
```

`load_layer` 中把 `if profile not in PROFILES:` 改为 `if profile not in LAYER_PROFILES:`（报错文案同步列出三值）。`load_layers` 签名与过滤：

```python
def load_layers(order: list[str], root: Path | None = None, profile: str = "release",
                *, ios: bool = False) -> list[Patch]:
    ...
        if layer["profile"] == "test" and profile != "test":
            continue
        if layer["profile"] == "ios" and not ios:
            continue
```

模块 docstring 的层格式说明里 `profile` 一行改为：`profile = "release"   # release：两剖面都打；test：只在 test 剖面打；ios：只在 build_disc --ios 的 iOS 变体打`。

- [ ] **Step 5: 改 `tools/layers.py`**

`_MANIFEST_KEYS` 加 `"ios"`。`_check_eboot` 在现有核对之后追加：

```python
    ios_patches = eboot_patch.load_layers(cfg["order"], profile=profile, ios=True)
    bad = [r for r in eboot_patch.check(data, ios_patches) if r["state"] != "pristine"]
    if bad:
        raise OverlayError("iOS 变体 eboot 补丁锚点在纯净源上不匹配: " +
                           ", ".join(f"{r['layer']}@{r['where']}" for r in bad))
    print(f"[layers] eboot（iOS 变体）: {len(ios_patches)} 条补丁锚点全部命中 ✓")
```

（`check()` 返回项的键名以该文件现有实现为准；若不是 `layer`/`where`，照现有 `_check_eboot` 的拼法改。）

- [ ] **Step 6: 写生成器 `tools/ios_eboot.py`**（代码逐条移植自已实测的 `build/movie_debug/cave_loader.py`、`cave_avcwrap.py`、`cave_createwrap.py`）

```python
#!/usr/bin/env python3
"""生成 layers/eboot/ios-movie.toml：iOS 变体（PPSSPP 1.20.x）播放 OP/ED 的四处 EBOOT 改动。

  E1 导入库名 sceMp4→zndMp4（VA 0x657D0），配合 tools/ios_fwmod.py 改过名的 libmp4。
  E2 洞（sceGumLookAt 0x624C8，零引用死代码）里写加载例程：bal 取 PC、addiu 算导入桩地址 jalr，
     依次 sceKernelLoadModule/StartModule disc0:/PSP_GAME/USRDIR/module/{mp4msv,libmp4}.prx；
     sub_B444 里 0xB470 的 jal sceUtilityLoadModule(0x308) 改指向这里；洞内被新代码覆盖的 HI16/LO16
     两个重定位条目（表项文件偏移 0x84188、0x84198）改 R_MIPS_NONE。
  E3 sceMpegCreate 条件包装（0x6262C）：$a6（DecTopAddr）== 0x10000000（1.20.x HLE 伪值）才把 ringbuffer
     设为 mpeg 工作区 +0x7000；0xB4F4 的 jal 改指向它。
  E4 sceMpegAvcDecode 保 pts 包装（0x625D8）：存/恢复 AU 前 8 字节；0xEA94 的 jal 改指向它。
依据与实测：docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。

用法：uv run python tools/ios_eboot.py      # 写 layers/eboot/ios-movie.toml
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools.mips_asm import assemble  # noqa: E402

SRC = REPO / "assets" / "EBOOT.dec.elf"
LAYER = REPO / "layers" / "eboot" / "ios-movie.toml"
FILE_BASE = 0xC0
CAVE, WRAP_AVC, WRAP_CREATE = 0x624C8, 0x625D8, 0x6262C
STUB_LOAD, STUB_START, STUB_AVCDEC, STUB_CREATE = 0x65170, 0x65160, 0x65520, 0x65578
CALLS = {0xB470: CAVE, 0xB4F4: WRAP_CREATE, 0xEA94: WRAP_AVC}
CALL_OLD = {0xB470: 0x65230, 0xB4F4: STUB_CREATE, 0xEA94: STUB_AVCDEC}
RELOC_NONE = (0x84188, 0x84198)            # r_offset 0x62570（HI16）/0x62574（LO16）
IMPORT_NAME_VA = 0x657D0
PATHS = (b"disc0:/PSP_GAME/USRDIR/module/mp4msv.prx\0", b"disc0:/PSP_GAME/USRDIR/module/libmp4.prx\0")


def _bal(pc: int, target: int) -> int:
    return (1 << 26) | (0x11 << 16) | (((target - (pc + 4)) >> 2) & 0xFFFF)   # bgezal zero


def _enc(lines: list, base: int) -> list[int]:
    """listing 元素：汇编文本，或 ("bal", 目标)/("bltz_v0", 目标)/("raw", 字)。"""
    out = []
    for i, x in enumerate(lines):
        pc = base + 4 * i
        if isinstance(x, tuple):
            kind, arg = x
            if kind == "bal":
                out.append(_bal(pc, arg))
            elif kind == "bltz_v0":
                out.append((1 << 26) | (2 << 21) | (((arg - (pc + 4)) >> 2) & 0xFFFF))
            else:
                out.append(arg)
        else:
            out.append(struct.unpack("<I", assemble([x], pc))[0])
    return out


def loader_listing() -> tuple[list, bytes]:
    l0 = CAVE + 6 * 4
    n_words = 7 + 2 * 17 + 6
    s1 = CAVE + 4 * n_words
    s2 = s1 + len(PATHS[0])
    fail = CAVE + 4 * (n_words - 5)
    src: list = ["addiu sp, sp, -32", "sw ra, 28(sp)", "sw s0, 24(sp)", "sw s1, 20(sp)",
                 ("bal", l0), "nop", "move s0, ra"]
    for s in (s1, s2):
        src += [f"addiu a0, s0, {s - l0}", "move a1, zero", "move a2, zero",
                f"addiu t9, s0, {STUB_LOAD - l0}", ("raw", 0x0320F809), "nop", ("bltz_v0", fail),
                "move a0, v0", "move a1, zero", "move a2, zero", "move a3, zero", "move a4, zero",
                f"addiu t9, s0, {STUB_START - l0}", ("raw", 0x0320F809), "nop", ("bltz_v0", fail), "nop"]
    src += ["move v0, zero", "lw s1, 20(sp)", "lw s0, 24(sp)", "lw ra, 28(sp)", ("raw", 0x03E00008),
            "addiu sp, sp, 32"]
    assert len(src) == n_words
    return src, PATHS[0] + PATHS[1]


def avc_listing() -> list:
    l2 = WRAP_AVC + 10 * 4
    return ["addiu sp, sp, -16", "sw ra, 12(sp)", "sw s0, 8(sp)", "lw t4, 0(a1)", "lw t5, 4(a1)",
            "sw t4, 0(sp)", "sw t5, 4(sp)", "move s0, a1", ("bal", l2), "nop",
            f"addiu t9, ra, {STUB_AVCDEC - l2}", ("raw", 0x0320F809), "nop", "lw t4, 0(sp)", "lw t5, 4(sp)",
            "sw t4, 0(s0)", "sw t5, 4(s0)", "lw s0, 8(sp)", "lw ra, 12(sp)", ("raw", 0x03E00008),
            "addiu sp, sp, 16"]


CREATE_LISTING: list = []


def create_listing() -> list:
    l3 = WRAP_CREATE + 0x1C
    return ["lui t4, 0x1000", f"bne a6, t4, {WRAP_CREATE + 0x10:#x}", "nop", "addiu a3, a1, 0x7000",
            "move t5, ra", ("bal", l3), "nop", f"addiu t9, ra, {STUB_CREATE - l3}", ("raw", 0x03200008),
            "move ra, t5"]


CREATE_LISTING = create_listing()


def cave_bytes() -> bytes:
    loader, strings = loader_listing()
    blob = b"".join(struct.pack("<I", w) for w in _enc(loader, CAVE)) + strings
    assert CAVE + len(blob) <= WRAP_AVC
    blob = blob.ljust(WRAP_AVC - CAVE, b"\0")
    blob += b"".join(struct.pack("<I", w) for w in _enc(avc_listing(), WRAP_AVC))
    assert CAVE + len(blob) == WRAP_CREATE
    blob += b"".join(struct.pack("<I", w) for w in _enc(CREATE_LISTING, WRAP_CREATE))
    return blob


def _hex(b: bytes) -> str:
    return "\n" + "\n".join("    " + b[i:i + 16].hex(" ") for i in range(0, len(b), 16)) + "\n"


WHY = """iOS 变体（仅推荐 iOS 商店版 PPSSPP 1.20.x）播放 OP/ED：配合 tools/ios_fwmod.py 改过库名的固件
libmp4/mp4msv（EBOOT 自行从盘上加载）与 tools/ios_movie.py 的 44.1k 影片。E1 导入改名、E2 洞内加载例程
（sceGumLookAt 死代码，洞内两个 HI16/LO16 条目改 NONE）、E3 sceMpegCreate 条件假 ringbuffer（仅 1.20.x
HLE 的 DecTopAddr 伪值 0x10000000 生效）、E4 sceMpegAvcDecode 保 pts。只在 build_disc.py --ios 施加。
生成器 tools/ios_eboot.py；依据 docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」。"""


def render_layer(pristine: bytes) -> str:
    def at(va, n):
        return pristine[va + FILE_BASE: va + FILE_BASE + n]
    new_cave = cave_bytes()
    parts = [f'why = """{WHY}"""\nprofile = "ios"\n']

    def patch(key, where, frm, to, note):
        parts.append(f'\n[[patches]]\n{key} = "{where:#x}"\nnote = "{note}"\n'
                     f'from = """{_hex(frm)}"""\nto   = """{_hex(to)}"""\n')

    patch("va", IMPORT_NAME_VA, at(IMPORT_NAME_VA, 7), b"zndMp4\0", "E1 导入库名 sceMp4→zndMp4")
    patch("va", CAVE, at(CAVE, len(new_cave)), new_cave,
          "E2 加载例程 + 路径串 / E4 保 pts 包装 / E3 条件 ringbuffer 包装（覆盖 sceGumLookAt 死代码）")
    for site, target in CALLS.items():
        old = struct.unpack("<I", at(site, 4))[0]
        assert old == 0x0C000000 | (CALL_OLD[site] >> 2), f"{site:#x} 不是预期的 jal"
        patch("va", site, at(site, 4), struct.pack("<I", 0x0C000000 | (target >> 2)),
              f"jal {CALL_OLD[site]:#x} → {target:#x}（R_MIPS_26 条目保留，目标仍在段内）")
    for fo in RELOC_NONE:
        entry = pristine[fo:fo + 8]
        assert entry[4] in (5, 6), f"表项 {fo:#x} 不是 HI16/LO16"
        patch("off", fo, entry, entry[:4] + b"\0" + entry[5:], "洞内被覆盖字的重定位条目 → R_MIPS_NONE")
    return "".join(parts)


def main() -> int:
    LAYER.write_text(render_layer(SRC.read_bytes()), encoding="utf-8")
    print(f"写出 {LAYER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: 生成层并登记**

```bash
uv run python tools/ios_eboot.py
```
`layers/manifest.toml` 的 `[eboot]` 改为：`order    = ["kinsoku", "ruby-p5", "msgcol-px", "savebuf", "ios-movie"]     # …（ios-movie 层 profile="ios"，只在 --ios 施加）`

- [ ] **Step 8: 跑测试与闸**

Run: `uv run pytest tests/test_ios_eboot.py tests/test_eboot_patch.py tests/test_msgcol_px.py -v && uv run python tools/layers.py check --profile release`
Expected: 全 PASS；闸打印「eboot（iOS 变体）: N 条补丁锚点全部命中 ✓」。

- [ ] **Step 9: 与实验盘 EBOOT 对账**（实验盘 EBOOT 是 test 剖面层 + E1–E4；这里只比洞与四处改动的字节）

```bash
uv run python -c "
from tools import eboot_patch as ep, layers
m = layers.load_manifest()['eboot']
out, _ = ep.apply(open(m['source'],'rb').read(), ep.load_layers(m['order'], profile='test', ios=True))
exp = open('build/movie_debug/iosdisc/PSP_GAME/SYSDIR/EBOOT.BIN','rb').read()
for lo, hi in ((0x624C8+0xC0, 0x62654+0xC0), (0x657D0+0xC0, 0x657D7+0xC0), (0x84188, 0x841a0)):
    assert out[lo:hi] == exp[lo:hi], hex(lo)
for s in (0xB470, 0xB4E8, 0xB4F4, 0xEA94):
    assert out[s+0xC0:s+0xC4] == exp[s+0xC0:s+0xC4], hex(s)
print('与实验盘逐字节一致')"
```
Expected: `与实验盘逐字节一致`。

- [ ] **Step 10: 提交**（工具与层分开）

```bash
git add tools/eboot_patch.py tools/layers.py tools/ios_eboot.py tests/test_ios_eboot.py tests/test_eboot_patch.py
git commit -m "feat: EBOOT 层支持 profile=ios（仅 --ios 施加）+ ios_eboot 生成器（E1–E4）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git add layers/eboot/ios-movie.toml layers/manifest.toml
git commit -m "data: layers/eboot/ios-movie——iOS 变体 EBOOT 层入库并登记 [eboot].order

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `build_disc.py --ios` 与 testboot 影片参数

**Files:**
- Modify: `tools/testboot.py`（`MOVIE_TEMPLATE` 参数化；`_render_mode(..., movie="op", skippable=False)`）
- Modify: `tools/build_disc.py`（CLI `--movie`、`--skippable`、`--ios`；新阶段 `stage_ios`；`STAGE_ORDER` 在 `iso` 与 `boot` 之间插入 `"ios"`；provenance 记 `game_zh_ios.iso`）
- Modify: `layers/manifest.toml`（新增 `[ios]` 节）
- Test: `tests/test_testboot.py`、`tests/test_build_disc.py`

**Interfaces:**
- Consumes: `ios_fwmod.build(out_dir) -> dict[str, Path]`；`ios_movie.build(out_dir, pins, orig_iso) -> dict[str, Path]`；`eboot_patch.load_layers(..., ios=True)`；`umdiso.replace/add_files/verify`。
- Produces: `stage_ios(ctx, results) -> dict`；release 写 `build/dist/game_zh_ios.iso` 与 `.provenance.json`；test 写 `build/test/game_ios/`；两剖面都写 `build/<profile>/EBOOT.ios.BIN`。

- [ ] **Step 1: 写失败测试**

`tests/test_testboot.py` 追加：

```python
def test_movie_mode_can_play_ed_skippably(out_dir):
    generate("movie", out_dir, movie="ed", skippable=True)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'playMovie("movie/ed.mp4", true)' in src


def test_movie_mode_defaults_to_op(out_dir):
    generate("movie", out_dir)
    src = (out_dir / "scripts" / "snr_test.lua").read_text(encoding="utf-8")
    assert 'playMovie("movie/op.mp4", false)' in src
```

`tests/test_build_disc.py` 追加（沿用该文件里构造 `BuildContext` 的既有写法）：

```python
def test_ios_stage_requires_prerequisite_in_same_invocation(tmp_path):
    from tools.build_disc import BuildContext, stage_ios
    ctx = BuildContext(profile="release", root=tmp_path, manifest={}, switches={}, mode_opts={})
    with pytest.raises(SystemExit, match="iso"):
        stage_ios(ctx, results={})
    ctx_t = BuildContext(profile="test", root=tmp_path, manifest={}, switches={}, mode_opts={})
    with pytest.raises(SystemExit, match="disc"):
        stage_ios(ctx_t, results={})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_testboot.py tests/test_build_disc.py -k "movie or ios" -v`
Expected: FAIL（`_render_mode() got an unexpected keyword argument 'movie'`；`cannot import name 'stage_ios'`）。

- [ ] **Step 3: manifest `[ios]` 节**（放在 `[sound]` 之前；sha 用 Task 2/3 的值）

```toml
[ios]
# iOS 变体盘（build_disc.py --ios）：仅推荐 iOS 商店版 PPSSPP（1.20.x）。现行盘不受影响。
# 依据 docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」；固件模块取自本作 UMD 自带 6.20 升级包（解密）。
iso_name   = "game_zh_ios.iso"
module_dir = "/PSP_GAME/USRDIR/module"          # 加载例程写死的 disc0 路径与此一致
modules    = ["mp4msv.prx", "libmp4.prx"]       # tools/ios_fwmod.py 产物（输入/输出指纹钉在该工具常量里）

[ios.movies]                                     # tools/ios_movie.py 产物指纹（FFmpeg 9.0.1）
"op.mp4" = "<Task 3 Step 5 打印的 op sha256>"
"ed.mp4" = "<Task 3 Step 5 打印的 ed sha256>"
```

- [ ] **Step 4: 改 `tools/testboot.py`**

```python
MOVIE_TEMPLATE = '''-- 自动生成（tools/testboot.py）：开机直接循环播放影片（内存峰值 / 影片回归探针）
-- 替换 script/snr_mainmenu.lua。影片解码是引擎 heap16 用量的峰值场合之一。
main = function()
    cardIDFlag = true
    gameSave.startMenuState = 2
    while true do
        playMovie("movie/{movie}.mp4", {skippable})
        wait(60)
    end
end
'''
```

`_render_mode` 签名加 `movie: str = "op", skippable: bool = False`；movie 分支：

```python
    if mode == "movie":
        if movie not in ("op", "ed"):
            sys.exit(f"movie 只能是 op/ed，得到 {movie!r}")
        print(f"[testboot] 开机循环播放 movie/{movie}.mp4（skippable={skippable}）")
        return MOVIE_TEMPLATE.format(movie=movie, skippable="true" if skippable else "false")
```

- [ ] **Step 5: 改 `tools/build_disc.py`**

CLI：

```python
    ap.add_argument("--movie", default="op", choices=["op", "ed"], help="test 剖面 movie 模式：循环播哪一部")
    ap.add_argument("--skippable", action="store_true", help="test 剖面 movie 模式：以可跳过方式调用 playMovie")
    ap.add_argument("--ios", action="store_true",
                    help="另出 iOS 变体（release：build/dist/game_zh_ios.iso；test：build/test/game_ios/）")
```

`mode_opts` 加 `"movie": args.movie, "skippable": args.skippable`；`wanted` 计算后：`if args.ios: wanted.append("ios")`（`ios` 不进缺省集合）。`STAGE_ORDER` 改为 `[..., "disc", "iso", "ios", "boot"]`，`STAGES["ios"] = stage_ios`；主循环对 `ios` 传入 `results`：

```python
        results[name] = (STAGES[name](ctx, results) if name == "ios" else STAGES[name](ctx)) or {}
```

`stage_ios`（放在 `stage_iso` 之后）：

```python
IOS_BUILD = REPO / "build" / "ios"      # 模块/影片产物（跨剖面共享、带指纹核对）


def stage_ios(ctx: BuildContext, results: dict) -> dict:
    """iOS 变体：EBOOT 多施加 profile=ios 的层，加两个改名固件模块与 44.1k 影片。

    只复用**同一次调用里**已产出并（release）通过发布断言的 DATA.BIN/SOUND.BIN——
    release 要求本次跑过 iso、test 要求本次跑过 disc，否则拒绝，防旧产物冒充。
    """
    need = "iso" if ctx.profile == "release" else "disc"
    if need not in results:
        die(f"--ios 需要本次调用同时跑 {need} 阶段（防止拿旧产物出 iOS 盘）")
    from tools import eboot_patch, ios_fwmod, ios_movie
    from tools.umdiso import add_files, replace, verify

    cfg, ios = ctx.manifest["eboot"], ctx.manifest["ios"]
    pristine = (REPO / cfg["source"]).read_bytes()
    if eboot_patch.sha256(pristine) != cfg["sha256"]:
        die(f"{cfg['source']} 的 sha256 与 manifest [eboot].sha256 不符")
    eb, _ = eboot_patch.apply(pristine, eboot_patch.load_layers(cfg["order"], profile="release", ios=True))
    eb_path = ctx.root / "EBOOT.ios.BIN"
    eb_path.write_bytes(eb)
    mods = ios_fwmod.build(IOS_BUILD / "module")
    movies = ios_movie.build(IOS_BUILD / "movie", ios["movies"], ORIG_ISO)
    log(f"ios: EBOOT.ios.BIN（{eboot_patch.sha256(eb)[:12]}…）、模块 {list(mods)}、影片 {list(movies)}")

    if ctx.profile == "test":
        game, dst = ctx.root / "game", ctx.root / "game_ios"
        if dst.exists():
            shutil.rmtree(dst)
        subprocess.run(["cp", "-c", "-R", str(game), str(dst)], check=True)
        shutil.copyfile(eb_path, dst / "PSP_GAME" / "SYSDIR" / "EBOOT.BIN")
        for name, p in mods.items():
            shutil.copyfile(p, dst / ios["module_dir"].lstrip("/") / name)
        for name, p in movies.items():
            shutil.copyfile(p, dst / "PSP_GAME" / "USRDIR" / "movie" / name)
        log(f"ios: 目录盘 {dst}")
        return {"game_ios": str(dst)}

    from tools.umdiso import DATA_BIN_PATH
    pairs = [(DATA_BIN_PATH, str(DIST / "DATA.BIN")), (cfg["iso_path"], str(eb_path))]
    if _sound_tracks(ctx):
        pairs.append((ctx.manifest["sound"]["iso_path"], str(DIST / "SOUND.BIN")))
    pairs += [(f"/PSP_GAME/USRDIR/movie/{n}", str(p)) for n, p in movies.items()]
    out = DIST / ios["iso_name"]
    replace(str(ORIG_ISO), str(out), pairs, log=log)
    add_files(str(out), [(f"{ios['module_dir']}/{n}", str(mods[n])) for n in ios["modules"]], log=log)
    if not verify(str(out), against=str(ORIG_ISO), log=log):
        die("ios: 结构自检未过")
    (DIST / f"{ios['iso_name']}.provenance.json").write_text(json.dumps({
        "base_iso": _hash_or_absent(DIST / "game_zh.iso"),
        "EBOOT.ios.BIN": eboot_patch.sha256(eb),
        "modules": {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in mods.items()},
        "movies": {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in movies.items()},
        "iso": _hash_or_absent(out)}, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"ios: {out}（{out.stat().st_size} B）")
    return {ios["iso_name"]: str(out)}
```

- [ ] **Step 6: 跑测试**

Run: `uv run pytest tests/test_testboot.py tests/test_build_disc.py -v`
Expected: 全 PASS。

- [ ] **Step 7: 出 test 目录盘冒烟**

```bash
uv run python tools/build_disc.py --profile test --mode movie --ios
ls build/test/game_ios/PSP_GAME/USRDIR/module build/test/game_ios/PSP_GAME/USRDIR/movie
```
Expected: `module/` 下 `libfont.prx libmp4.prx mp4msv.prx`；`movie/` 下 44.1k 的 op/ed；日志含 `ios: 目录盘`。

- [ ] **Step 8: 提交**

```bash
git add tools/testboot.py tools/build_disc.py tests/test_testboot.py tests/test_build_disc.py
git commit -m "feat: build_disc --ios 出 iOS 变体（release→game_zh_ios.iso、test→game_ios/），testboot 影片参数 --movie/--skippable

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git add layers/manifest.toml
git commit -m "data: manifest 新增 [ios]（模块清单、44.1k 影片指纹）

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 驾驶工具——PPSSPP 1.20.x 会话、音画分析、`movie_probe.py`

**Files:**
- Create: `tools/emu/legacy.py`（移植 `build/movie_debug/ppsspp1204.py`）
- Create: `tools/emu/movielab.py`（移植 `movie_sync_analyze.py` 与 `audio_local_align.py` 的核心为函数）
- Create: `tools/emu/drives/movie_probe.py`（移植 `movie_sync_probe.py`，分析改调 movielab）
- Test: `tests/test_movielab.py`
- Modify: `tools/emu/drives/README.md`

**Interfaces:**
- Produces:
  - `legacy.session(disc: Path, *, app: Path = ~/ppsspp-1204/…/PPSSPPSDL, port=45699, core: int | None = None, start_break=False)` → 异步上下文，产出 `(proc, EmuClient, log_path)`；进入时改 ini（`RemoteDebuggerOnStartup=True`、`RemoteISOPort`、`GraphicsBackend=0 (OPENGL)`、`SoftwareRenderer=True`、可选 `CPUCore`、`AutoRun=False`），退出时原样写回。
  - `movielab.local_align(dump: np.ndarray, ref: np.ndarray, sr: int, approx_s: float, step_s=5.0) -> list[tuple[float, float, float]]`（ref 时刻、偏移秒、相关系数）
  - `movielab.match_frames(frames: list[np.ndarray], ref_gray: np.ndarray) -> list[tuple[int, float, int]]`（帧号、mse、平台宽）
  - `movielab.verdict(align_rows, av_diffs) -> dict`：`{"audio_ok": 相关≥0.99 的段 ≥90%, "drift_ok": 偏移跨度 < 0.05 s, "av_ok": |中位音画差| < 0.2 s, "pass": 三者皆真}`

- [ ] **Step 1: 写失败测试** `tests/test_movielab.py`

```python
"""tools/emu/movielab.py：影片音画探针的纯分析部分（合成信号）。"""
import pytest

np = pytest.importorskip("numpy")
from tools.emu import movielab as ml  # noqa: E402


def test_local_align_recovers_constant_offset():
    sr = 8000
    rng = np.random.default_rng(1)
    ref = rng.standard_normal(sr * 30).astype(np.float32) * 1000
    dump = np.concatenate([np.zeros(int(1.25 * sr), np.float32), ref])
    rows = ml.local_align(dump, ref, sr, approx_s=1.2, step_s=5.0)
    assert all(abs(o - 1.25) < 1e-3 and c > 0.99 for _, o, c in rows)


def test_local_align_stops_where_dump_ends():
    sr = 8000
    rng = np.random.default_rng(2)
    ref = rng.standard_normal(sr * 60).astype(np.float32) * 1000
    dump = np.concatenate([np.zeros(sr, np.float32), ref[: sr * 20]])     # 只录到 20 s
    rows = ml.local_align(dump, ref, sr, approx_s=1.0, step_s=5.0)
    assert rows and all(c > 0.99 for _, _, c in rows) and rows[-1][0] < 20


def test_verdict_flags_drift_and_distortion():
    good = [(t, 2.0, 0.999) for t in range(0, 200, 5)]
    drift = [(t, 2.0 + t * 0.0023, 0.999) for t in range(0, 200, 5)]
    bad = [(t, 2.0, 0.5) for t in range(0, 200, 5)]
    assert ml.verdict(good, [-0.06] * 40)["pass"]
    assert not ml.verdict(drift, [-0.06] * 40)["drift_ok"]
    assert not ml.verdict(bad, [-0.06] * 40)["audio_ok"]
    assert not ml.verdict(good, [-0.5] * 40)["av_ok"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --with numpy pytest tests/test_movielab.py -v`
Expected: FAIL（`No module named 'tools.emu.movielab'`）。

- [ ] **Step 3: 实现 `tools/emu/movielab.py`**

```python
"""影片音画探针的分析部分（需要 numpy：uv run --with numpy …）。

录音与参照音轨逐 step_s 秒取 1 s 片段就近互相关 → (ref 时刻, 偏移, 相关)；截帧与参照影片 48×27 灰度逐帧
MSE 匹配 → 片中时刻；两者相减得音画差。判定阈值取 2026-09-24 实测：健康时分段相关 ≥0.999、偏移跨度 <2 ms、
音画差中位 −0.05…−0.10 s；1.20.4 的 48k 破音是相关 0.3–0.76 + 每分钟漂 0.14 s。
"""
from __future__ import annotations

import numpy as np

FPS = 30000 / 1001


def _best(seg: np.ndarray, region: np.ndarray) -> tuple[int, float]:
    n, m = len(seg), len(region) - len(seg)
    if m <= 0:
        return 0, 0.0
    fs = 1 << int(np.ceil(np.log2(len(region) + n)))
    c = np.fft.irfft(np.fft.rfft(region, fs) * np.conj(np.fft.rfft(seg, fs)), fs)[:m]
    k = int(np.argmax(c))
    x = region[k:k + n]
    cc = float(np.dot(x - x.mean(), seg - seg.mean()) / (np.std(x) * np.std(seg) * n + 1e-9))
    return k, cc


def local_align(dump: np.ndarray, ref: np.ndarray, sr: int, approx_s: float,
                step_s: float = 5.0) -> list[tuple[float, float, float]]:
    rows, off = [], int(approx_s * sr)
    t = 1.0
    while (t + 1) * sr <= len(ref) and int(t * sr) + off + int(1.5 * sr) <= len(dump):   # 录音覆盖不到就停
        a = int(t * sr)
        seg = ref[a:a + sr]
        if np.std(seg) >= 50:
            lo = max(0, a + off - sr // 2)
            k, cc = _best(seg, dump[lo:a + off + int(1.5 * sr)])
            loc = lo + k - a
            rows.append((t, loc / sr, cc))
            off = loc
        t += step_s
    return rows


def match_frames(frames: list[np.ndarray], ref_gray: np.ndarray) -> list[tuple[int, float, int]]:
    out = []
    for g in frames:
        mse = ((ref_gray - g) ** 2).mean(axis=(1, 2))
        k = int(mse.argmin())
        out.append((k, float(mse[k]), int((mse <= mse[k] * 1.15 + 2).sum())))
    return out


def verdict(align_rows: list[tuple[float, float, float]], av_diffs: list[float]) -> dict:
    core = align_rows[:-1] if len(align_rows) > 2 else align_rows      # 末段常落在片尾/循环交界
    corr_ok = sum(1 for _, _, c in core if c >= 0.99) >= 0.9 * max(1, len(core))
    offs = [o for _, o, c in core if c >= 0.9]
    drift_ok = bool(offs) and (max(offs) - min(offs)) < 0.05
    av_ok = bool(av_diffs) and abs(float(np.median(av_diffs))) < 0.2
    return {"audio_ok": corr_ok, "drift_ok": drift_ok, "av_ok": av_ok,
            "pass": corr_ok and drift_ok and av_ok}
```

- [ ] **Step 4: 实现 `tools/emu/legacy.py` 与 `tools/emu/drives/movie_probe.py`**

`tools/emu/legacy.py`：

```python
"""PPSSPP 1.20.x（iOS 商店版同版本）的驾驶会话：该版 SDL 构建没有 --debugger= 参数，远程调试器只能由 ini 的
RemoteDebuggerOnStartup + RemoteISOPort 打开；软渲染同样经 ini。进入时改 ini、退出时原样写回。
二进制缺省 ~/ppsspp-1204/build/PPSSPPSDL.app（本机 v1.20.4 构建），SNDL_PPSSPP_1204 覆盖。"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import time
from pathlib import Path

from tools.emu.client import EmuClient

APP = Path(os.environ.get("SNDL_PPSSPP_1204",
                          Path.home() / "ppsspp-1204/build/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL"))
INI = Path.home() / ".config/ppsspp/PSP/SYSTEM/ppsspp.ini"
LOG_DIR = Path(__file__).resolve().parents[2] / "build" / "emu" / "logs"


def _set(text: str, key: str, val: str) -> str:
    new, n = re.subn(rf"^{key} = .*$", f"{key} = {val}", text, flags=re.M)
    if n != 1:
        raise RuntimeError(f"ppsspp.ini 里找不到唯一的 {key}")
    return new


@contextlib.asynccontextmanager
async def session(disc: Path, *, app: Path = APP, port: int = 45699, core: int | None = None,
                  start_break: bool = False, extra: dict[str, str] | None = None):
    orig = INI.read_text(encoding="utf-8")
    t = orig
    for k, v in {"RemoteDebuggerOnStartup": "True", "RemoteISOPort": str(port),
                 "GraphicsBackend": "0 (OPENGL)", "SoftwareRenderer": "True", **(extra or {})}.items():
        t = _set(t, k, v)
    if core is not None:
        t = _set(t, "CPUCore", str(core))
    if start_break:
        t = _set(t, "AutoRun", "False")
    INI.write_text(t, encoding="utf-8")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logp = LOG_DIR / f"{time.strftime('%H%M%S')}-app1204.log"
    proc = None
    try:
        with open(logp, "w") as lf:
            proc = subprocess.Popen([str(app), str(Path(disc).resolve())], stdout=lf, stderr=subprocess.STDOUT)
        cli = EmuClient(port=port)
        await cli.connect(retry_seconds=20, alive=lambda: proc.poll() is None)
        try:
            yield proc, cli, logp
        finally:
            await cli.aclose()
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(3)
        INI.write_text(orig, encoding="utf-8")
```

`tools/emu/drives/movie_probe.py`（移植自已实测的 `build/movie_debug/movie_sync_probe.py` / `movie_sync_analyze.py`；参照媒体取盘上那份影片，所以 iOS 盘对照的是 44.1k 版本身）：

```python
#!/usr/bin/env -S uv run --with numpy python
"""影片音画探针：开 DumpAudio → 引导「开机循环播影片」的测试盘 → 每 dt 秒断 CPU 截 fb0/fb1 并记下录音文件长度
（=模拟时间）→ 与盘上那份影片的画面/音轨比对 → movielab.verdict 判 PASS/FAIL（退出码 0/1）。

前置：build_disc.py --profile test --mode movie [--movie ed --skippable] [--ios]
    uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 1 --movie op --seconds 225 --disc build/test/game_ios
    uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp new --movie ed --seconds 70 --check-dectop --disc build/test/game_ios
--ppsspp 1204 走 tools/emu/legacy.py（ini 开调试器）；new 走现有 launcher（SNDL_PPSSPP_APP 指定新版二进制）。
--check-dectop：ini 设 AutoRun=False 开机即停，在 VA 0xB4F4（sceMpegCreate 调用点）读 $a6，≠0x10000000 说明
iOS 层的条件包装走原样 NULL 分支（新版/实机应如此）。ini 改动一律 try/finally 还原。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO, TEST_GAME, Emulator, session, wait_game  # noqa: E402

from tools.emu import legacy, movielab  # noqa: E402

INI = Path.home() / ".config/ppsspp/PSP/SYSTEM/ppsspp.ini"
AUDIO_DIR = Path.home() / ".config/ppsspp/PSP/AUDIO"
BASE = 0x08804000


def _ini_set(pairs: dict[str, str]) -> str:
    orig = INI.read_text(encoding="utf-8")
    t = orig
    for k, v in pairs.items():
        t, n = re.subn(rf"^{k} = .*$", f"{k} = {v}", t, flags=re.M)
        if n != 1:
            sys.exit(f"ppsspp.ini 里找不到唯一的 {k}")
    INI.write_text(t, encoding="utf-8")
    return orig


def _movie_file(disc: Path, movie: str, work: Path) -> Path:
    if disc.is_dir():
        return disc / "PSP_GAME" / "USRDIR" / "movie" / f"{movie}.mp4"
    from tools.umdiso import SECTOR, Iso
    dst = work / f"{movie}.mp4"
    with Iso(str(disc)) as iso:
        rec = iso.find(f"/PSP_GAME/USRDIR/movie/{movie}.mp4")
        iso.f.seek(rec.lba * SECTOR)
        dst.write_bytes(iso.f.read(rec.size))
    return dst


def _ref(mp4: Path, work: Path) -> tuple[np.ndarray, np.ndarray, int]:
    raw, wav = work / "ref.raw", work / "ref.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", "scale=48:27:flags=area,format=gray",
                    "-f", "rawvideo", str(raw)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vn", "-ac", "2", "-ar", "44100",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    gray = np.fromfile(raw, dtype=np.uint8).reshape(-1, 27, 48).astype(np.float32)
    audio, sr = _wav_mono(wav)
    return gray, audio, sr


def _wav_mono(p: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(p)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    return a.reshape(-1, ch).mean(axis=1), sr


async def _capture(cli, out: Path, seconds: float, dt: float, before: set[Path], dectop: bool) -> list[dict]:
    await wait_game(cli, 0.2)
    if dectop:
        await cli.bp_add(BASE + 0xB4F4)
        mark = cli.seq_mark()
        await cli.resume()
        await cli.wait_broadcast("cpu.stepping", after_seq=mark, timeout=60)
        a6 = (await cli.request("cpu.getReg", name="a6"))["uintValue"]
        print(f"sceMpegCreate 调用点 $a6 = {a6:#x}" +
              ("（1.20.x HLE 伪值：条件包装会传假 ringbuffer）" if a6 == 0x10000000 else "（走原样 NULL 分支）"), flush=True)
        await cli.bp_remove(BASE + 0xB4F4)
        await cli.resume()
    caps, t0, i = [], time.monotonic(), 0
    while time.monotonic() - t0 < seconds:
        await cli.break_cpu()
        dumps = sorted((p for p in AUDIO_DIR.glob("*.wav") if p not in before), key=lambda p: p.stat().st_mtime)
        size = dumps[-1].stat().st_size if dumps else 0
        for name, addr in (("fb0", cli.VRAM_FB0), ("fb1", cli.VRAM_FB1)):
            (await cli.vram_screenshot(addr)).save(out / f"c{i:03d}_{name}.png")
        await cli.resume()
        caps.append({"i": i, "wall": time.monotonic() - t0, "dump_bytes": size})
        i += 1
        await asyncio.sleep(dt)
    return caps


def _analyze(out: Path, caps: list[dict], gray: np.ndarray, ref: np.ndarray, sr: int) -> dict:
    dump, dsr = _wav_mono(out / "dump.wav")
    if dsr != sr:
        sys.exit(f"录音采样率 {dsr} ≠ 参照 {sr}")
    env = lambda a: np.log(np.sqrt((a[: len(a) // 882 * 882].reshape(-1, 882) ** 2).mean(axis=1)) + 1)  # noqa: E731
    de, re_ = env(dump), env(ref)
    L = min(len(re_), 1000)                                   # 参照前 20 s 的包络
    q = (re_[:L] - re_[:L].mean()) / (re_[:L].std() + 1e-9)
    scores = [float(((de[o:o + L] - de[o:o + L].mean()) / (de[o:o + L].std() + 1e-9) * q).mean())
              for o in range(0, max(1, min(len(de) - L, 3000)))]
    approx = int(np.argmax(scores)) * 882 / sr
    rows = movielab.local_align(dump, ref, sr, approx_s=approx)
    off = rows[0][1] if rows else approx
    frames = []
    for c in caps:
        best = None
        for fb in ("fb0", "fb1"):
            g = np.asarray(Image.open(out / f"c{c['i']:03d}_{fb}.png").convert("L").resize((48, 27), Image.BOX),
                           dtype=np.float32)
            if g.max() >= 1 and (best is None or g.std() > best.std()):
                best = g
        frames.append(best)
    matched = movielab.match_frames([f for f in frames if f is not None], gray)
    dur = len(ref) / sr
    av, k = [], 0
    for c, f in zip(caps, frames):
        if f is None:
            continue
        idx, mse, plateau = matched[k]
        k += 1
        t_audio = (c["dump_bytes"] - 44) / (sr * 4) - off
        if plateau <= 6 and mse < 60 and 0 < t_audio < dur:
            av.append(idx / movielab.FPS - t_audio)
    v = movielab.verdict(rows, av)
    v.update({"audio_offset_s": off, "chunks": len(rows), "frames_judged": len(av),
              "av_median_s": float(np.median(av)) if av else None,
              "corr_min": min((c for _, _, c in rows), default=None)})
    return v


async def _run(a: argparse.Namespace) -> int:
    out = a.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    before = set(AUDIO_DIR.glob("*.wav")) if AUDIO_DIR.exists() else set()
    pairs = {"DumpAudio": "True"}
    if a.check_dectop:
        pairs["AutoRun"] = "False"
    orig = _ini_set(pairs)
    try:
        if a.ppsspp == "1204":
            ctx = legacy.session(a.disc, core=a.core)
        else:
            ctx = session(lambda: Emulator.app(a.disc, graphics="software"))
        async with ctx as tup:
            cli = tup[1]
            caps = await _capture(cli, out, a.seconds, a.dt, before, a.check_dectop)
    finally:
        INI.write_text(orig, encoding="utf-8")
    dumps = sorted((p for p in AUDIO_DIR.glob("*.wav") if p not in before), key=lambda p: p.stat().st_mtime)
    if not dumps:
        sys.exit("没有新的录音落盘（DumpAudio 未生效？）")
    shutil.copy(dumps[-1], out / "dump.wav")
    for p in dumps:
        p.unlink()
    (out / "captures.json").write_text(json.dumps(caps, indent=1))
    with tempfile.TemporaryDirectory() as td:
        gray, ref, sr = _ref(_movie_file(a.disc, a.movie, Path(td)), Path(td))
    v = _analyze(out, caps, gray, ref, sr)
    (out / "verdict.json").write_text(json.dumps(v, indent=1, ensure_ascii=False))
    print(json.dumps(v, ensure_ascii=False, indent=1))
    print("PASS" if v["pass"] else "FAIL")
    return 0 if v["pass"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disc", type=Path, default=TEST_GAME)
    ap.add_argument("--ppsspp", choices=["new", "1204"], default="new")
    ap.add_argument("--core", type=int, default=None, help="仅 1204：CPUCore（1 JIT / 2 IR 解释器）")
    ap.add_argument("--movie", choices=["op", "ed"], default="op")
    ap.add_argument("--seconds", type=float, default=225)
    ap.add_argument("--dt", type=float, default=4.0)
    ap.add_argument("--check-dectop", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "emu" / "drives" / "movie_probe")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑测试**

Run: `uv run --with numpy pytest tests/test_movielab.py -v`
Expected: 3 PASS。

- [ ] **Step 6: drives/README 表格加一行**

`| movie_probe.py | 影片音画：DumpAudio + fb0/fb1 截帧 → 分段互相关/漂移/音画差 → PASS/FAIL；--ppsspp 1204 走 ini 调试器会话（tools/emu/legacy.py） | --profile test --mode movie [--movie ed --skippable] [--ios]，--disc build/test/game_ios | 分段相关 ≥0.99 占 ≥90%、偏移跨度 <0.05 s、音画差中位 <0.2 s |`

- [ ] **Step 7: 提交**

```bash
git add tools/emu/legacy.py tools/emu/movielab.py tools/emu/drives/movie_probe.py tools/emu/drives/README.md tests/test_movielab.py
git commit -m "feat: 影片音画驾驶 movie_probe（DumpAudio+截帧→分段互相关/漂移/音画差判定）与 PPSSPP 1.20.x ini 调试器会话

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 端到端验证（驾驶）与 iOS 发布盘

**Files:** 无代码改动；产物 `build/dist/game_zh_ios.iso`。结果写进 Task 8 的文档。

- [ ] **Step 1: test 目录盘 OP，1.20.4 JIT 与 IR**

```bash
uv run python tools/build_disc.py --profile test --mode movie --ios
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 1 --movie op --seconds 225 --disc build/test/game_ios
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --core 2 --movie op --seconds 225 --disc build/test/game_ios
```
Expected: 两次都 `PASS`（实验值：相关 1.000、零漂移、音画差中位 −0.067/−0.095 s）。

- [ ] **Step 2: ED 可跳过调法 + 跳过**

```bash
uv run python tools/build_disc.py --profile test --mode movie --movie ed --skippable --ios
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp 1204 --movie ed --seconds 262 --disc build/test/game_ios
```
Expected: `PASS`。跳过：照 `build/movie_debug/skip1204.py` 的做法（15 s 时按 CIRCLE，之后 +10/+15/+20 s 截帧应推进到片中约 8.7/13.9/18.9 s）手动跑一次并记录。

- [ ] **Step 3: 同一目录盘在最新 master 上（Review Focus 4）**

```bash
uv run --with numpy python tools/emu/drives/movie_probe.py --ppsspp new --movie ed --seconds 70 --check-dectop --disc build/test/game_ios
```
Expected: `PASS`，且打印 `$a6 != 0x10000000`（条件包装走原样 NULL 分支）。

- [ ] **Step 4: 现行盘不变（Review Focus 1）+ 出 iOS 发布盘**

```bash
shasum -a 256 build/dist/game_zh.iso > /tmp/before.sha
uv run python tools/build_disc.py --ios
shasum -a 256 -c /tmp/before.sha
uv run python tools/umdiso.py verify --against assets/orig.iso build/dist/game_zh_ios.iso
uv run python tools/umdiso.py list build/dist/game_zh_ios.iso | grep -E "module/|movie/"
```
Expected: `game_zh.iso: OK`（现行盘逐字节不变）；iOS 盘 verify 通过；列表含 `module/libmp4.prx`、`module/mp4msv.prx` 与新尺寸的 op/ed。

- [ ] **Step 5: iOS 发布盘在 1.20.4 上开机冒烟**

用 `tools/emu/legacy.session` 引导 `build/dist/game_zh_ios.iso`，等 60 s 到标题画面：`hle.module.list` 须含 `sceMp4_library` 与 `mp4msv_module`，日志无 `Unknown syscall`、无崩溃；截图确认标题画面正常。

---

### Task 8: 文档、CFW 评估与收尾

**Files:**
- Modify: `docs/ops/movie-playback-ppsspp-2026-09-24.md`（「产品化」一节：命令面、Task 7 实测表、固件模块的取得、CFW 评估、玩家说明要点）
- Modify: `docs/ops/disc-pipeline.md`（新增「iOS 变体」一节：`--ios` 两剖面行为、产物路径、断言、层 profile=ios）
- Modify: `CLAUDE.md`（「已知坑」该条改为「已产品化：`build_disc.py --ios` → game_zh_ios.iso」，并在常用操作里加一行）
- Modify: memory `ppsspp-movie-lle.md`

- [ ] **Step 1: 固件模块的取得（写进 movie 文档）**

内容要点：①新版 PPSSPP（≥ v1.20.4-1841）开一次本作，自动从盘内 6.20 升级包装固件到 NAND；②`ppsspp.ini` 临时 `DumpFileTypes = 2`，开本作到影片播放；③PPSSPP 以 `~PSP` 头的模块名命名 dump，mp4msv/libmp4/mpeg 三者同为空白名会互相覆盖——本机做法是临时把 `Core/HLE/sceKernelModule.cpp` 的 PRX dump 名改成「文件名_模块名」重编一次（改完还原）；④产物改名为 `assets/fw/{libmp4,mp4msv}.dec.prx`，sha256 须等于 `tools/ios_fwmod.py` 的 `*_IN_SHA`。

- [ ] **Step 2: CFW 实机行为评估（写进 movie 文档，结论 + 用户亲测清单）**

逐项写明依据：
- 明文 EBOOT 与明文用户 PRX：现行盘已是明文 EBOOT；CFW 的模块加载补丁接受明文 PRX（汉化补丁常见做法）→ 预期可加载，**待实测**。
- 迟绑定：本作 EBOOT 本就在运行时 `sceKernelLoadModule` 加载 `libfont.prx` 并由此接上 7 个 `sceLibFont` 导入 → 实机支持「导入库晚于 EBOOT 注册」，`zndMp4` 同理。
- libmp4 的依赖：`sceMpegbase`、`sceAudiocodec` 由游戏原有的 `sceUtilityLoadModule(0x303)`（及其依赖）提供；本变体只替换了 0x308 这一次加载。
- E3 在实机：`sceMpegAvcResourceGetAvcDecTopAddr` 返回真实地址（新版 PPSSPP LLE 实测 `$a6 != 0x10000000`，Task 7 Step 3）→ 走原样 NULL 分支；E4 恢复的 pts 与实机解码器写回值同源，无副作用。
- 44.1k MP4：新版 PPSSPP 跑的就是固件真 libmp4 代码、已正常解复用本变体影片 → 实机 libmp4 同样可接受（强证据）。
- M2 跳板：实机 ME 解码器按 0x2C 定输入长度，0x1C 是输出字段、会被覆盖 → 无副作用；M3：返回 −1 → libmp4 取当前 gp 调回调，EBOOT 回调不用 gp → 无副作用。
- 风险：`libmp4` 模块属性 0x0006（独占加载/启动），本变体只在开机加载一次（`sub_B444` 仅由 main_loop 初始化段调用一次）；退出时 `sub_B560`/`sub_CEB8` 会 `sceUtilityUnloadModule(0x308)`，而 0x308 从未加载 → 返回错误、游戏不检查。
- 用户亲测清单：开机到标题 → 新游戏走到做完第一张卡（crd_2）看 OP → 有无声、有无破音/花屏 → 回标题再进一次；有 s7f/s8f 进度的存档看 ED；s8f 的 ED 按任意键可跳过。

- [ ] **Step 3: 玩家说明要点（写进 movie 文档）**

两个平行版本：`game_zh.iso`（Windows/Android/macOS 的 PPSSPP 与实机）与 `game_zh_ios.iso`（仅 iOS 商店版 PPSSPP，1.20.x）；iOS 版在 PPSSPP 升级到 1.21+ 后也能播（Task 7 Step 3 实测），但仍推荐届时换回现行版；两版存档互通（游戏 ID 与存档格式相同）；iOS 版的影片音轨为 44.1k 重采样，画面无改动。

- [ ] **Step 4: 全量测试与闸**

Run: `uv run pytest -q && uv run python tools/layers.py check --profile release`
Expected: 全 PASS；闸通过。

- [ ] **Step 5: 提交**

```bash
git add docs/ops/movie-playback-ppsspp-2026-09-24.md docs/ops/disc-pipeline.md CLAUDE.md
git commit -m "docs: iOS 变体盘产品化——命令面、实测、固件模块取得、CFW 行为评估与玩家说明要点

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
