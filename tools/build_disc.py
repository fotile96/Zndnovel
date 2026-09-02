#!/usr/bin/env -S uv run python
"""中文化盘构建编排器——release/test 两个独立剖面，各自独立输出树。

设计见 docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md。

**剖面**（`--profile release|test`）决定输出树根 `build/<profile>/`：release 与 test
从 lua 注入开始就是两棵完全独立的树（`lua/injected`、`lua/final`、`members/`、
`stage/`、`game/`、`DATA.BIN`、`provenance.json` 全部各自一份）。test 的任何产物
不可能落进 release 的树，也不可能落进 `build/dist/`——那是仅 release 使用的最终
交付位置（`DATA.BIN`、`game_zh.iso`、`game_zh.iso.provenance.json`），且 iso 阶段
本身拒绝在 test 剖面运行。这就是本次改造的核心：此前两个剖面共用一棵
`build/inject`/`build/stage`，2026-09-02 一次测试盘构建就把 `build/dist/DATA.BIN`
换成了带探针的封包，只有 ISO 因未跑该阶段而幸免——现在这种事故结构上不可能发生。

阶段（`--stage` 逗号分隔，缺省 all；release 到 iso、test 到 disc，均不含 boot）：
  lua      译文注入 lua_scripts → 按剖面施加叠加层（release 层两剖面都施加，
           test 层只在 test；test 剖面还会先跑 tools.testboot.generate 产
           root/generated/，其 snr_test.lua 与递卡短路等层随后一并施加）
           → id 登记检查 → 写 build/<profile>/lua/final/
  font     永远从 **release** 剖面的 lua/final 算字集（test 复用 release 字体，
           探针文本不计入字集）→ 与 build/font/ucs.txt 比对，不等或 pgf 缺失
           才重建 → build/font/{lxgw17,lxgw09}.pgf（跨剖面共享）
  members  build/<profile>/members/：先清空再重建。编译 lua/final/*.lua（校
           PSP ABI 头）；gim 按 layers/manifest.toml 的 [gim] 两表编码（经
           build/cache/gim/ 内容哈希缓存，--force 绕过）；字体拷入。
  stage    build/databin --APFS clone--> build/<profile>/stage，覆入 members，
           新成员按名排序位插入（assemble_stage）。
  pack     databin pack stage → build/<profile>/DATA.BIN（release 另拷
           build/dist/DATA.BIN）。
  disc     刷新 build/<profile>/game/（首次自 assets/orig.iso 解出）+ 覆入
           DATA.BIN，供 PPSSPP 目录引导。
  iso      仅 release：release_assertions 通过后 umdiso 就地替换 →
           build/dist/game_zh.iso + provenance 副本；不过就拒绝出盘。
  boot     PPSSPP 引导冒烟 + 截图序列（opt-in，不在缺省阶段集合内）。

不论这次跑了哪些阶段，结束时都会写 build/<profile>/provenance.json。
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools import build_font, inject_lua, layers, testboot  # noqa: E402
from tools.emu.imgdiff import perceptual_mse  # noqa: E402
from tools.gimcodec import Gim  # noqa: E402
from tools.pipelib import read_jsonl  # noqa: E402
from PIL import Image  # noqa: E402

ORIG_ISO = REPO / "assets" / "orig.iso"
BASE = REPO / "build" / "databin"      # 原包解包镜像（databin.py unpack 产物，跨剖面共享）
DIST = REPO / "build" / "dist"         # 仅 release：DATA.BIN / game_zh.iso / 其 provenance 副本
CACHE_GIM = REPO / "build" / "cache" / "gim"   # 内容哈希键 gim 缓存，跨剖面共享
FONT_OUT = REPO / "build" / "font"     # build_font 产物，跨剖面共享

FONT_SIZE_WARN = 1_195_092   # 原 tsukuminpro_e_17.pgf 大小，经验上限
QUANT_MSE_WARN = 15.0        # 经验阈：>256 色烤字图落 256 色板的典型损耗在 5–10

#: 测试引导（tools/testboot.py）注入的**新成员**，绝不能进发布盘。
TESTBOOT_MEMBER = "script/snr_test.lua"


def log(msg: str) -> None:
    print(f"[build_disc] {msg}", flush=True)


def die(msg: str) -> None:
    sys.exit(f"[build_disc] 错误: {msg}")


@dataclass
class BuildContext:
    profile: str            # release | test
    root: Path              # build/<profile>
    manifest: dict
    switches: dict
    mode_opts: dict         # test 剖面的 --mode/--scene/--card 等
    force: bool = False


# ---------- A 译文注入 + 叠加层 + 编外脚本 ----------

def stage_lua(ctx: BuildContext) -> dict:
    """读账本与车道 → inject_lua.inject_tree → 写 root/lua/injected/；
    test 剖面先调 testboot.generate(...) 产 root/generated/；
    layers.build_final_sources 施加静态层，再把 root/generated/overlays/*.toml
    按文件名序追加施加；layers.check_ids；写 root/lua/final/。
    """
    base_dir = REPO / ctx.manifest["base"]["dir"]
    ledger_rows = read_jsonl(REPO / ctx.manifest["base"]["ledger"])
    zh, extra = inject_lua.load_translations()
    injected, stats = inject_lua.inject_tree(base_dir, ledger_rows, zh, extra)

    inj_dir = ctx.root / "lua" / "injected"
    if inj_dir.exists():
        shutil.rmtree(inj_dir)
    inj_dir.mkdir(parents=True)
    for name, text in injected.items():
        (inj_dir / name).write_text(text, encoding="utf-8")
    log(f"lua: 注入 {len(injected)} 文件（vms={stats['vms']} 缺译={stats['vms_missing']}"
        f" extra={stats['extra']} 缺译={stats['extra_missing']}）")

    gen_dir = ctx.root / "generated"
    testboot_result = None
    if ctx.profile == "test":
        opts = dict(ctx.mode_opts)
        mode = opts.pop("mode")
        testboot_result = testboot.generate(mode, gen_dir, **opts)
        for w in testboot_result["warnings"]:
            log(f"lua: ⚠ {w}")

    sources, applied, added = layers.build_final_sources(
        ctx.profile, ctx.switches, injected=injected)

    if testboot_result is not None:
        test_script = gen_dir / "scripts" / "snr_test.lua"
        if test_script.exists():
            name = test_script.name
            if name in sources:
                die(f"testboot 生成的成员名 {name} 与既有最终源同名")
            sources[name] = test_script.read_text(encoding="utf-8")
            added.append(TESTBOOT_MEMBER)
        for f in sorted((gen_dir / "overlays").glob("*.toml")):
            ov = layers.load_overlay(f)
            if ov["target"] not in sources:
                die(f"testboot 生成的层 {f.name} 的 target={ov['target']} 不在最终源里")
            sources[ov["target"]] = layers.apply_overlay(sources[ov["target"]], ov)
            applied.append(ov)

    ledger_ids = {r["id"] for r in ledger_rows}
    layers.check_ids(ctx.manifest, layers.LAYERS, ledger_ids)

    final_dir = ctx.root / "lua" / "final"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)
    for name, text in sources.items():
        (final_dir / name).write_text(text, encoding="utf-8")
    log(f"lua: 最终源 {len(sources)} 文件（施加 {len(applied)} 层，新增 {len(added)} 成员）"
        f" → {final_dir}")
    return {"stats": stats, "applied": applied, "scripts_added": added}


# ---------- B 字体 ----------

def stage_font(ctx: BuildContext) -> dict:
    """永远从 release 剖面的 lua/final 算字集（test 复用 release 字体）。

    release 剖面若 lua/final 不存在则先跑 stage_lua（对 test 调用而言，是
    先跑一遍 release 的 lua 阶段——两者互不干扰，各写各的 build/<profile>/）。
    """
    release_root = REPO / "build" / "release"
    final_dir = release_root / "lua" / "final"
    if not final_dir.exists():
        release_ctx = ctx if ctx.profile == "release" else replace(
            ctx, profile="release", root=release_root, switches={})
        stage_lua(release_ctx)

    sources = [p.read_text(encoding="utf-8") for p in sorted(final_dir.glob("*.lua"))]
    ledger_jp = [r["jp"] for r in read_jsonl(REPO / ctx.manifest["base"]["ledger"])]
    ledger_jp += [r["jp"] for r in read_jsonl(REPO / ctx.manifest["base"]["ledger_extra"])]
    codes = layers.charset_of(sources, ledger_jp, list(build_font.ALWAYS))

    charset_path = release_root / "charset.txt"
    layers.write_charset(codes, charset_path)

    ucs_path = FONT_OUT / "ucs.txt"
    font_members = ctx.manifest["fonts"]     # [{"size":17,"member":"pgf/..."}, ...]
    fonts_missing = any(
        not (FONT_OUT / f"lxgw{f['size']:02d}.pgf").exists() for f in font_members)
    stale = (not ucs_path.exists()
             or ucs_path.read_text(encoding="utf-8") != charset_path.read_text(encoding="utf-8"))

    rebuilt = False
    if stale or fonts_missing:
        if not build_font.TTF_PGF.exists():
            die(f"字集有变化或字体产物缺失，需要重建，但缺 ttf_pgf: {build_font.TTF_PGF}"
                f"（见 docs/ops/pgf-font-research-2026-08-31.md 重建；或设 SNDL_TTF_PGF）。"
                f"重建指令：uv run python tools/build_font.py --charset {charset_path} "
                f"--out {FONT_OUT}")
        sizes = tuple(sorted(f["size"] for f in font_members))
        build_font.build(charset_path, FONT_OUT, sizes=sizes)
        shutil.copyfile(charset_path, ucs_path)
        rebuilt = True
        log(f"font: 字集 {len(codes)} 码位，{'字体缺失' if fonts_missing else '字集变化'}"
            f"——已重建 {sizes}")
    else:
        log(f"font: 字集 {len(codes)} 码位，未变——复用现役 {FONT_OUT}")
    return {"charset_codes": len(codes), "rebuilt": rebuilt}


# ---------- C 成员树：编译 + gim + 字体 ----------

def _compile_lua(src: Path, dst: Path, ctx: BuildContext) -> None:
    """编译单个 lua 源到 PSP 字节码，校 ABI 头。"""
    luac = Path(os.environ.get("SNDL_LUAC") or ctx.manifest["compiler"]["luac"]).expanduser()
    if not luac.exists():
        die(f"缺 {luac}（先装 luac_sz4，或设 SNDL_LUAC 指到别处）")
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([str(luac), "-s", "-o", str(dst), str(src)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        die(f"{src.name} 编译失败：{proc.stderr.strip()}")
    header = bytes.fromhex(ctx.manifest["compiler"]["header_hex"])
    if dst.read_bytes()[:len(header)] != header:
        die(f"{src.name} 编译产物头部非 PSP ABI（应为 {ctx.manifest['compiler']['header_hex']}）")


def quantize_for_template(im: Image.Image, cap: int) -> Image.Image:
    """RGBA 烤字图 → P 模式、调色板 ≤cap（模板色板容量）。

    颜色数本就 ≤cap 时走无损精确调色板；否则 FASTOCTREE 量化（RGBA 感知）。
    量化损耗按 CLAUDE.md 规约需目检——产物即最终进包像素，QA 看 build/<profile>/members。
    """
    im = im.convert("RGBA")
    colors = im.getcolors(cap)
    if colors is not None:
        pal_img = Image.new("P", (1, 1))
        palette, lut = [], {}
        for i, (_, rgba) in enumerate(colors):
            palette.extend(rgba)
            lut[rgba] = i
        pal_img.putpalette(palette, rawmode="RGBA")
        out = Image.new("P", im.size)
        out.putdata([lut[px] for px in im.getdata()])
        out.putpalette(palette, rawmode="RGBA")
        return out
    return im.quantize(colors=cap, method=Image.Quantize.FASTOCTREE)


def _encode_gim_cached(png: Path, tpl_path: Path, out: Path, force: bool,
                       losses: list[tuple[float, str]], member: str) -> None:
    """gim 编码，经 build/cache/gim/ 内容哈希缓存。--force 绕过缓存（仍会刷新它）。"""
    key = hashlib.sha256(png.read_bytes() + tpl_path.read_bytes()).hexdigest()[:16]
    cache = CACHE_GIM / f"{key}.gim"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not force and cache.exists():
        shutil.copyfile(cache, out)
        return
    tpl = Gim(tpl_path.read_bytes())
    im = Image.open(png)
    if tpl.image.fmt in (4, 5):    # index4/8
        im = quantize_for_template(im, tpl.palette.w * tpl.palette.h)
    blob = tpl.encode_from_pil(im)
    loss = perceptual_mse(Gim(blob).to_pil(), Image.open(png))
    if loss > 0:
        losses.append((loss, member))
    out.write_bytes(blob)
    CACHE_GIM.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(blob)


def stage_members(ctx: BuildContext) -> dict:
    """成员树：先清空再重建。编译 lua/final → members/script/；gim 按
    layers/manifest.toml 的 [gim] 两表（replace/new）编码（经缓存）→
    members/<面>/；字体按 [[fonts]] 拷入 members/pgf/。

    顺手把这次构建里『相对原包是新增』的成员名记到 root/new_members.json——
    release_assertions 的 expected_new 就是从这里来的。不在 stage_iso 里现算
    一遍，是因为 iso 阶段常单独跑（`--stage iso`），那时 members 阶段的内存
    状态早就没了，只有磁盘上的这份记录还在；且这里是唯一实际写盘、能确权
    "这次真的新增了什么" 的地方，不必在别处重新扫一遍 build/<烤字目录> 猜。
    """
    members_dir = ctx.root / "members"
    if members_dir.exists():
        shutil.rmtree(members_dir)
    members_dir.mkdir(parents=True)

    base_names = {json.loads(l)["name"] for l in
                  (BASE / "manifest.jsonl").read_text().splitlines() if l}
    new_members: set[str] = set()

    final_dir = ctx.root / "lua" / "final"
    if not final_dir.exists():
        die(f"缺 {final_dir}（先跑 lua 阶段）")
    n_lua = 0
    for src in sorted(final_dir.glob("*.lua")):
        member = f"script/{src.name}"
        _compile_lua(src, members_dir / member, ctx)
        if member not in base_names:
            new_members.add(member)
        n_lua += 1
    log(f"members: 编译 {n_lua} 个脚本")

    losses: list[tuple[float, str]] = []
    n_gim = 0
    for src_dir, prefix in ctx.manifest["gim"]["replace"]:
        root = REPO / "build" / src_dir
        if not root.is_dir():
            log(f"members: {src_dir}/ 不存在，跳过整面")
            continue
        for png in sorted(root.rglob("*.png")):
            if png.name.startswith("_"):
                continue    # 烤字器的 QA 对照图（_compare/_cellzoom/…），按约定非入包件
            rel = png.relative_to(root).with_suffix(".gim")
            member = str(Path(prefix) / rel) if prefix else str(rel)
            if member not in base_names:
                die(f"{src_dir}/{png.relative_to(root)} 无对应封包成员 {member}——"
                    f"检查烤字工具输出或 layers/manifest.toml 的 [gim].replace 表")
            _encode_gim_cached(png, BASE / member, members_dir / member, ctx.force,
                              losses, member)
            n_gim += 1
    for src_dir, prefix, tpl_member in ctx.manifest["gim"]["new"]:
        root = REPO / "build" / src_dir
        if not root.is_dir():
            log(f"members: {src_dir}/ 不存在，跳过整面（新增件，先跑对应 bake 工具）")
            continue
        for png in sorted(root.rglob("*.png")):
            if png.name.startswith("_"):
                continue
            member = str(Path(prefix) / png.relative_to(root).with_suffix(".gim"))
            if member in base_names:
                die(f"{member} 已是原包成员——layers/manifest.toml 的 [gim].new 表只管新增件")
            _encode_gim_cached(png, BASE / tpl_member, members_dir / member, ctx.force,
                              losses, member)
            new_members.add(member)
            n_gim += 1
    losses.sort(reverse=True)
    over = [x for x in losses if x[0] > QUANT_MSE_WARN]
    log(f"members: gim 编码 {n_gim} 张；有量化损耗 {len(losses)} 张，超阈"
        f"({QUANT_MSE_WARN}) {len(over)} 张")
    for loss, member in losses[:5]:
        log(f"members:   最大损耗 MSE={loss:8.2f}  {member}")

    for f in ctx.manifest["fonts"]:
        src = FONT_OUT / f"lxgw{f['size']:02d}.pgf"
        if not src.exists():
            die(f"缺字体 {src}（先跑 font 阶段）")
        dst = members_dir / f["member"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if f["member"] not in base_names:
            new_members.add(f["member"])
        if src.stat().st_size > FONT_SIZE_WARN:
            log(f"members: ⚠ {f['member']} 体积超过原正文字体 {FONT_SIZE_WARN:,} B——"
                f"引擎字体缓冲可能装不下（症状：sceFontOpenUserMemory addr=0）")
    log(f"members: 字体 {len(ctx.manifest['fonts'])} 个成员就位")

    (ctx.root / "new_members.json").write_text(
        json.dumps(sorted(new_members), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"lua": n_lua, "gim": n_gim, "losses": len(losses), "new_members": new_members}


# ---------- D 组装封包树 + 发布断言（模块级纯函数，测试直接 import）----------

def assemble_stage(base: Path, members: Path, stage_dir: Path) -> Path:
    """封包树 = 基座镜像快照 + members 覆入。新成员按名插到排序位。

    ⚠ 新成员**必须**插到按名排序的位置，绝不能追加表尾。原包文件表严格按成员名
    升序，引擎按名二分查找；表一乱新成员就查不到。2026-08-31 三次实测定论：
    追加表尾 → sceFontOpenUserMemory(addr=0) ×169；插到 e_17 处 → 同样失败；
    排序位 → 零错误。

    ⚠ 2026-09-03 复核追加：`members` 若传成不存在的路径，`Path.rglob()` 在其上
    不报错、只静默返回空——不加下面两行检查，这个函数会悄悄产出一棵『看着正常、
    实则一个成员都没覆盖』的封包树，不报任何错。这正是本任务通篇要堵的那类
    静默失败，用一次真实构造复现过（传错 members 目录名）。
    """
    base, members = Path(base), Path(members)
    if not base.is_dir():
        die(f"assemble_stage: 基座镜像不是目录或不存在: {base}")
    if not members.is_dir():
        die(f"assemble_stage: members 树不是目录或不存在: {members}——"
            f"传错路径会静默产出零覆盖的封包树而不报错")
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    subprocess.run(["cp", "-Rc", str(base), str(stage_dir)], check=True)  # APFS clone，秒级
    manifest = [json.loads(l) for l in
                (stage_dir / "manifest.jsonl").read_text().splitlines() if l]
    names = {m["name"] for m in manifest}
    for f in sorted(Path(members).rglob("*")):
        if not f.is_file():
            continue
        member = str(f.relative_to(members))
        dst = stage_dir / member
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        if member not in names:
            idx = bisect.bisect_left([m["name"] for m in manifest], member)
            manifest.insert(idx, {"name": member, "lzss": False, "sha1": ""})
            names.add(member)
    order = [m["name"] for m in manifest]
    if order != sorted(order):
        die("文件表失序——引擎二分查找会失败，检查新成员插入逻辑")
    (stage_dir / "manifest.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manifest))
    return stage_dir


def release_assertions(stage: Path, base: Path, expected_new: set[str],
                       compiled: Path) -> list[str]:
    """出盘前的结构断言。返回问题列表，空 = 放行。

    与旧 check_release_clean 的区别：那个只查「inject_src 里有的脚本是否一致」，
    查不出**多出来的**成员；这个正查成员集合，测试引导的新成员一个也藏不住。
    """
    bad: list[str] = []
    base_names = {json.loads(l)["name"] for l in
                  (base / "manifest.jsonl").read_text().splitlines() if l}
    stage_names = {json.loads(l)["name"] for l in
                   (stage / "manifest.jsonl").read_text().splitlines() if l}
    allowed = base_names | expected_new
    for extra in sorted(stage_names - allowed):
        bad.append(f"封包树有未声明的成员 {extra}（testboot 残留？）")
    for missing in sorted(allowed - stage_names):
        bad.append(f"封包树缺声明的成员 {missing}")
    if "script/snr_test.lua" in stage_names:
        bad.append("封包树里有测试引导成员 script/snr_test.lua")
    for p in sorted((stage / "script").glob("*.lua")):
        ref = Path(compiled) / p.name
        if not ref.exists():
            bad.append(f"script/{p.name} 不在本次编译产物里")
        elif ref.read_bytes() != p.read_bytes():
            bad.append(f"script/{p.name} 与本次编译产物不一致")
    return bad


def _load_new_members(ctx: BuildContext) -> set[str]:
    path = ctx.root / "new_members.json"
    if not path.exists():
        die(f"缺 {path}（先跑 members 阶段）")
    return set(json.loads(path.read_text(encoding="utf-8")))


def stage_stage(ctx: BuildContext) -> dict:
    if not (BASE / "manifest.jsonl").exists():
        die("build/databin 未解包（python3 tools/databin.py unpack assets/DATA.BIN build/databin）")
    members_dir = ctx.root / "members"
    if not members_dir.exists():
        die(f"缺 {members_dir}（先跑 members 阶段）")
    base_names = {json.loads(l)["name"] for l in
                  (BASE / "manifest.jsonl").read_text().splitlines() if l}
    assemble_stage(BASE, members_dir, ctx.root / "stage")
    stage_names = {json.loads(l)["name"] for l in
                  ((ctx.root / "stage") / "manifest.jsonl").read_text().splitlines() if l}
    added = len(stage_names - base_names)
    member_files = sum(1 for f in members_dir.rglob("*") if f.is_file())
    replaced = member_files - added
    log(f"stage: 覆盖 {replaced} 成员，新增 {added} 成员（manifest {len(stage_names)} 行，有序✓）")
    return {"replaced": replaced, "added": added}


# ---------- E 封包 ----------

def stage_pack(ctx: BuildContext) -> dict:
    stage_dir = ctx.root / "stage"
    if not (stage_dir / "manifest.jsonl").exists():
        die(f"缺 {stage_dir}（先跑 stage 阶段）")
    out = ctx.root / "DATA.BIN"
    subprocess.run([sys.executable, str(REPO / "tools" / "databin.py"),
                    "pack", str(stage_dir), str(out)], check=True)
    log(f"pack: {out} ({out.stat().st_size} B)")
    if ctx.profile == "release":
        DIST.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, DIST / "DATA.BIN")
        log(f"pack: 已同步 {DIST / 'DATA.BIN'}")
    return {"DATA.BIN": str(out)}


# ---------- F 盘目录 ----------

def stage_disc(ctx: BuildContext) -> dict:
    game = ctx.root / "game"
    if not (game / "PSP_GAME").exists():
        if not ORIG_ISO.exists():
            die(f"缺 {ORIG_ISO}，无法组装盘目录")
        log("disc: 首次自 assets/orig.iso 解出盘目录…")
        mnt = Path(f"/tmp/sndl_iso_mnt_{ctx.profile}")
        out = subprocess.run(["hdiutil", "attach", str(ORIG_ISO), "-mountpoint",
                              str(mnt), "-nobrowse", "-readonly", "-plist"],
                             check=True, capture_output=True)
        try:
            game.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", "-R", f"{mnt}/", str(game)], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], check=False)
        _ = plistlib.loads(out.stdout)      # 校验挂载回报可解析
    src = ctx.root / "DATA.BIN"
    if not src.exists():
        die(f"缺 {src}（先跑 pack 阶段）")
    shutil.copyfile(src, game / "PSP_GAME" / "USRDIR" / "DATA.BIN")
    log(f"disc: DATA.BIN 已覆入 {game}")
    return {"game": str(game)}


# ---------- F2 实机盘（ISO 就地替换，release only）----------

def stage_iso(ctx: BuildContext) -> dict:
    """把新 DATA.BIN 就地塞回原盘 → build/dist/game_zh.iso。

    实机（CFW）走 ISO，且固件的 isofs 比 PPSSPP 严格得多；故**不重建镜像**，
    只替换该文件并平移尾部，其余字节保持原样。机理见
    docs/ops/umd-iso-repack-research-2026-08-31.md。

    ⚠ **发布闸**：ISO 是交到志愿者手里的那个东西，测试引导绝不能混进去。
    profile != release 直接拒绝——test 剖面的产物结构上到不了这里（各自独立
    输出树），但入口仍显式挡一道，报错要比「凭空找不到文件」更明确。
    """
    if ctx.profile != "release":
        die("iso 阶段仅限 release 剖面——test 产物绝不能出现在 build/dist/")

    stage_dir = ctx.root / "stage"
    members_script = ctx.root / "members" / "script"
    if not (stage_dir / "manifest.jsonl").exists():
        die(f"缺 {stage_dir}（先跑 stage 阶段）")
    if not members_script.is_dir():
        die(f"缺 {members_script}（先跑 members 阶段）")

    expected_new = _load_new_members(ctx)
    bad = release_assertions(stage_dir, BASE, expected_new, members_script)
    if bad:
        for b in bad:
            log(f"iso: ✗ {b}")
        die("iso: 发布断言未过，拒绝出盘。跑 "
            "`--stage lua,font,members,stage,pack` 重建干净的封包树再来。")
    log("iso: 发布断言通过（成员集合、脚本逐字节核对均正常，无测试引导成员）")

    if not ORIG_ISO.exists():
        die(f"缺 {ORIG_ISO}，无法产实机盘")
    src = ctx.root / "DATA.BIN"
    if not src.exists():
        die(f"缺 {src}（先跑 pack 阶段）")

    from tools.umdiso import DATA_BIN_PATH, replace, verify

    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / "game_zh.iso"
    replace(str(ORIG_ISO), str(out), [(DATA_BIN_PATH, str(src))], log=log)
    if not verify(str(out), against=str(ORIG_ISO), log=log):
        die("iso: 结构自检未过")
    log(f"iso: {out}（{out.stat().st_size} B）")
    return {"game_zh.iso": str(out)}


# ---------- G 引导冒烟 ----------

def stage_boot(ctx: BuildContext) -> dict:
    import asyncio

    from tools.emu.launcher import Emulator, session

    game = ctx.root / "game"
    seq_dir = ctx.root / "emu" / "bootseq"
    if seq_dir.exists():
        shutil.rmtree(seq_dir)
    seq_dir.mkdir(parents=True)

    async def run() -> None:
        async with session(lambda: Emulator.app(game, graphics="software")) as (emu, cli):
            for _ in range(60):
                st = await cli.game_status()
                if st.get("game"):
                    log(f"boot: game={st['game']}")
                    break
                await asyncio.sleep(1)
            else:
                die("boot: 游戏未进入运行态")
            await asyncio.sleep(8)
            for i in range(10):
                await cli.buttons_press("cross", duration=3)
                await asyncio.sleep(3)
                await cli.break_cpu()
                img = await cli.vram_screenshot()
                await cli.resume()
                img.save(seq_dir / f"seq_{i:02d}.png")
            errors = [d["message"] for d in cli.drain_broadcasts("log")
                      if d.get("level") == 2]
            log(f"boot: ERROR 日志 {len(errors)} 条: {errors[:5]}")
    asyncio.run(run())
    log(f"boot: 截图序列 -> {seq_dir}")
    return {"bootseq": str(seq_dir)}


# ---------- provenance ----------

def _hash_or_absent(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"


def _write_provenance(ctx: BuildContext, results: dict[str, dict]) -> None:
    if "lua" in results:
        applied, scripts_added = results["lua"]["applied"], results["lua"]["scripts_added"]
    else:
        _, applied, scripts_added = layers.build_final_sources(ctx.profile, ctx.switches)

    if "stage" in results:
        members_stat = {"replaced": results["stage"]["replaced"],
                        "added": results["stage"]["added"]}
    else:
        members_stat = {"replaced": 0, "added": 0}

    outputs = {"DATA.BIN": _hash_or_absent(ctx.root / "DATA.BIN")}
    if ctx.profile == "release":
        outputs["game_zh.iso"] = _hash_or_absent(DIST / "game_zh.iso")

    prov = layers.provenance(ctx.profile, ctx.manifest, layers.LAYERS, applied,
                             scripts_added, members_stat, outputs)
    out_path = ctx.root / "provenance.json"
    layers.write_provenance(prov, out_path)
    log(f"provenance: {out_path}")
    # ⚠ 只在 iso 阶段**这次真的跑过**时才另拷——否则会在半截 stage 子集
    # （比如只跑 lua,font,members,stage）后产出自相矛盾的记录：dist/ 里摆着一份
    # 旧的、真实的 game_zh.iso，旁边却配一份声称 "DATA.BIN": "absent" 的
    # provenance（因为这次调用压根没跑到 pack/iso，ctx.root/DATA.BIN 还不存在）。
    # 2026-09-03 实测踩中过一次：先跑 `--stage lua,font,members,stage`，
    # build/dist/game_zh.iso.provenance.json 被换成了这份自相矛盾的记录，
    # 而 build/dist/game_zh.iso 本身字节没变——sidecar 撒了谎，本体没事。
    # 只有 "iso" in results 时，stage_iso 才刚验证过 ctx.root/DATA.BIN 存在
    # 且发布断言通过，此时的 provenance 才真正配得上 dist/ 里那份 iso。
    if ctx.profile == "release" and "iso" in results:
        DIST.mkdir(parents=True, exist_ok=True)
        (DIST / "game_zh.iso.provenance.json").write_text(
            out_path.read_text(encoding="utf-8"), encoding="utf-8")
        log(f"provenance: 另拷 {DIST / 'game_zh.iso.provenance.json'}")


# ---------- CLI ----------

STAGE_ORDER = ["lua", "font", "members", "stage", "pack", "disc", "iso", "boot"]
STAGES = {"lua": stage_lua, "font": stage_font, "members": stage_members,
          "stage": stage_stage, "pack": stage_pack, "disc": stage_disc,
          "iso": stage_iso, "boot": stage_boot}
#: 缺省 all 时各剖面跑到哪一站——均不含 boot（opt-in）。
DEFAULT_STOP = {"release": "iso", "test": "disc"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="release", choices=layers.PROFILES)
    ap.add_argument("--stage", default="all",
                    help=f"逗号分隔阶段名（{','.join(STAGE_ORDER)}）或 all")
    ap.add_argument("--force", action="store_true", help="members 阶段绕过 gim 内容哈希缓存")
    ap.add_argument("--no-fast-boot", action="store_true",
                    help="test 剖面保留 IPL 开场演出（不施加 strip-ipl 层）")
    ap.add_argument("--mode", default="font", choices=testboot._MODES,
                    help="test 剖面：testboot 生成模式")
    ap.add_argument("--scene", default="s1s_20", help="test 剖面 scene 模式的目标场景 ID")
    ap.add_argument("--card", type=int, help="test 剖面 card 模式的卡号")
    ap.add_argument("--hold", type=int, default=180, help="test 剖面 font/cutin 每页停留帧数")
    ap.add_argument("--no-cards", action="store_true", help="test 剖面 scene 模式不预置全卡")
    args = ap.parse_args()

    manifest = layers.load_manifest()
    switches = {"fast-boot": False} if args.no_fast_boot else {}
    mode_opts = {"mode": args.mode, "scene": args.scene, "card": args.card,
                "hold": args.hold, "no_cards": args.no_cards}
    ctx = BuildContext(profile=args.profile, root=REPO / "build" / args.profile,
                       manifest=manifest, switches=switches, mode_opts=mode_opts,
                       force=args.force)

    if args.stage == "all":
        stop = DEFAULT_STOP[ctx.profile]
        wanted = STAGE_ORDER[:STAGE_ORDER.index(stop) + 1]
    else:
        wanted = args.stage.split(",")
    unknown = set(wanted) - set(STAGES)
    if unknown:
        die(f"未知阶段: {unknown}（可选 {STAGE_ORDER}）")

    results: dict[str, dict] = {}
    for name in STAGE_ORDER:
        if name not in wanted:
            continue
        log(f"=== 剖面 {ctx.profile} · 阶段 {name} ===")
        results[name] = STAGES[name](ctx) or {}

    _write_provenance(ctx, results)
    log("完成")


if __name__ == "__main__":
    main()
