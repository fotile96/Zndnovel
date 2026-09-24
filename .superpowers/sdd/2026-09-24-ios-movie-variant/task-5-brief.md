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

