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
`build/dist/` 同样**只能由通过发布断言的 iso 阶段写入**（2026-09-03 review 加固）：
`pack` 阶段只写 `build/<profile>/` 内部，不再顺手同步一份到 `build/dist/`——否则
`--stage pack` 单独跑一次就能在不经过任何断言的情况下换掉发布产物，是同一类事故
换了个阶段重新出现。

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
  pack     databin pack stage → build/<profile>/DATA.BIN，记下这次打包对应的
           stage 树指纹（build/<profile>/stage_fingerprint.txt）。**不碰
           build/dist/**——那是发布产物，只能由通过发布断言的 iso 阶段写入。
  eboot    按 layers/manifest.toml [eboot] 给解密引擎 ELF（assets/，版权物不入库，
           指纹钉在 manifest）施加 layers/eboot/*.toml 的字节补丁 →
           build/<profile>/EBOOT.BIN（tools/eboot_patch.py；无 [eboot] 节则空转）。
  disc     刷新 build/<profile>/game/（首次自 assets/orig.iso 解出）+ 覆入
           DATA.BIN 与（若有）EBOOT.BIN，供 PPSSPP 目录引导。
  iso      仅 release：三道断言（stage 树指纹与 DATA.BIN 对应同一次 pack、
           lua/final 独立重编译后与 stage/script 逐字节核对、成员集合与测试
           引导成员检查；有 [eboot] 时第四道：EBOOT.BIN 与「对登记的纯净源
           重新施加当前层」逐字节相同）全过，才把 DATA.BIN/EBOOT.BIN 拷到
           build/dist/、umdiso 就地替换 → build/dist/game_zh.iso + provenance
           副本；任一断言不过就拒绝出盘，不写任何 build/dist/ 文件。
  ios      iOS 变体（只推荐 iOS 商店版 PPSSPP 1.20.x，见
           docs/ops/movie-playback-ppsspp-2026-09-24.md「追记：iOS」）。release：只要跑了 iso
           就自动跟着跑——dist 里的现行盘与 iOS 盘总是同出（2026-09-24 用户裁定）；test：--ios
           才跑。只复用**同一次调用**里刚产出的盘（release 须本次跑过 iso、test 须本次跑过
           disc），EBOOT 多施加 profile=ios 的层，加两个改名固件模块（tools/ios_fwmod.py）与
           44.1k op/ed（tools/ios_movie.py）→ release：build/dist/game_zh_ios.iso + provenance；
           test：build/test/game_ios/。现行盘一字不变。前置条件（assets/fw 两个模块、影片缓存
           无效时的 ffmpeg）在任何阶段动手前就核对，缺了立刻失败。
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
import tempfile
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

#: gim 编码缓存的版本戳。缓存键 = sha256(版本 ‖ png 字节 ‖ 模板 gim 字节)，覆盖
#: 不到 tools/gimcodec.py 的编解码逻辑、quantize_for_template 的量化算法、或
#: Pillow 版本本身——这三者任一变化都可能改变同一份 (png, 模板) 输入编出的字节，
#: 但内容哈希键对它们视而不见。改了这三者中任何一个、可能影响编码输出时，把这个
#: 数手动 +1：旧缓存条目从此在键空间里再也不会被命中，会被当作未命中重新编码。
#: 不这样做的后果：改了编码器却忘了清缓存，687 张图会静默继续用旧编码器的产物，
#: release_assertions 也查不出来——它只逐字节核对 script/*.lua，不比对任何 gim 成员。
GIM_CACHE_VERSION = 2      # 2：二值 alpha 的图改走 MEDIANCUT（2026-09-07），旧缓存作废

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
        opts.pop("bloat", None)            # --bloat 由本函数在最终源上施加，不是 testboot 模式参数
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

    # test 剖面 --bloat：把目标场景所在章节脚本的每条 vms 翻倍（复刻"中日双语"盘），用来
    # 复现/验证存档线程 blob 超容量（docs/ops/eboot-savedata-research-2026-09-05.md §8a 路线图阶段 1）。
    if ctx.profile == "test" and ctx.mode_opts.get("bloat"):
        target = testboot.scene_to_script(ctx.mode_opts["scene"])
        target = target if target.endswith(".lua") else target + ".lua"
        if target not in sources:
            die(f"lua: --bloat 目标脚本 {target} 不在最终源里")
        sources[target], n_dup = testboot.bloat_script(sources[target])
        log(f"lua: --bloat 把 {target} 的 {n_dup} 条 vms 翻倍（原文前插入 NONVOICE 标记副本）")

    # 消息窗排版校验：release 有错误即拒绝（第 5 行停滞/缓冲写穿/注音读穿会直接坏盘），
    # test 剖面只告警——探针文本本来就可能故意越界（tools/testboot.py）。
    from tools import msg_layout_check as mlc
    findings, stats = mlc.check_sources(sources)
    for ln in mlc.format_report(findings, stats, limit=5).splitlines():
        log(ln)
    if stats["errors"] and ctx.profile == "release":
        die(f"lua: 消息窗排版校验有 {stats['errors']} 处错误——"
            f"`uv run python tools/msg_layout_check.py --show <id>` 看版面")

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

def _font_source_dirs(ctx: BuildContext) -> list[Path]:
    """字集取材的 lua/final 目录：**本剖面自己的** + release 的（去重，存在的才算）。

    2026-09-21 事故：test 盘上新加的两层中文说明里「译」画成了下划线——stage_font 只看
    release 的 lua/final，而那棵树是上一次 release 构建留下的、不含新层；test 剖面自己
    刚由 stage_lua 写好的 final 里明明有这个字，却没被算进字集，于是走了「字集未变，
    复用现役字体」。本剖面的 final 是同一次调用里 stage_lua 刚写的，永远是新的；release
    的仍然并进来是「宁滥勿缺」——字集只许变大。
    """
    dirs = [ctx.root / "lua" / "final", REPO / "build" / "release" / "lua" / "final"]
    out: list[Path] = []
    for d in dirs:
        if d.exists() and d not in out:
            out.append(d)
    return out


def stage_font(ctx: BuildContext) -> dict:
    """从本剖面 + release 的 lua/final 并集算字集（test 复用 release 字体产物）。

    两棵树都不存在（裸跑 `--stage font`）则先跑 release 的 stage_lua。
    ⚠ `--stage font` 单独跑不会刷新 lua/final；字集要反映新文本，按阶段序 `lua,font` 跑。
    """
    release_root = REPO / "build" / "release"
    if not _font_source_dirs(ctx):
        release_ctx = ctx if ctx.profile == "release" else replace(
            ctx, profile="release", root=release_root, switches={})
        stage_lua(release_ctx)

    sources = [p.read_text(encoding="utf-8")
               for d in _font_source_dirs(ctx) for p in sorted(d.glob("*.lua"))]
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
    # 配方戳：步进/声调加粗等不改字集却改产物的参数变了，也必须重建（build_font.RECIPE）
    recipe_path = FONT_OUT / "recipe.txt"
    recipe_stale = (not recipe_path.exists()
                    or recipe_path.read_text(encoding="utf-8") != build_font.RECIPE)

    rebuilt = False
    if stale or fonts_missing or recipe_stale:
        if not build_font.TTF_PGF.exists():
            die(f"字集有变化或字体产物缺失，需要重建，但缺 ttf_pgf: {build_font.TTF_PGF}"
                f"（见 docs/ops/pgf-font-research-2026-08-31.md 重建；或设 SNDL_TTF_PGF）。"
                f"重建指令：uv run python tools/build_font.py --charset {charset_path} "
                f"--out {FONT_OUT}")
        sizes = tuple(sorted(f["size"] for f in font_members))
        build_font.build(charset_path, FONT_OUT, sizes=sizes)
        shutil.copyfile(charset_path, ucs_path)
        recipe_path.write_text(build_font.RECIPE, encoding="utf-8")
        rebuilt = True
        why = "字体缺失" if fonts_missing else "字集变化" if stale else "配方变化"
        log(f"font: 字集 {len(codes)} 码位，{why}——已重建 {sizes}")
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


def _check_save_size(script_dir: Path, ctx: BuildContext) -> None:
    """存档序列化容量闸（tools/pluto_size.py）。

    引擎存档时用 Pluto 把整个 mainThread 协程写进存档结构里 0x50000 B 的定长区——协程栈上
    挂着正在运行的章节脚本的主 chunk 闭包，Pluto 会把它的整棵 Proto 树（全部指令 + 常量，
    即整份脚本）都写进去；写入回调逐字节拷贝、无边界检查，超容量即溢出砸坏后续字段乃至
    别的全局（docs/ops/eboot-savedata-research-2026-09-05.md）。原版最大的 s1s 章已占 78%，
    把 vms 翻倍的双语版正是这样崩的。这里按刚编出的字节码逐个估算"它作为 mainThread 时
    的 blob 大小"，release 超容量即拒绝出盘，test 只告警。
    """
    from tools import pluto_size as ps
    rows: list[tuple[int, str]] = []
    for f in sorted(script_dir.glob("*.lua")):
        try:
            _, est, _ = ps.estimate_file(f)
        except ValueError as e:
            die(f"members: {f.name} 字节码解析失败：{e}")
        rows.append((est.total + ps.DEFAULT_EXTRA, f.name))
    if not rows:
        return
    rows.sort(reverse=True)
    worst, name = rows[0]
    cap = ps.thread_cap(ctx.profile)        # savebuf 扩容层生效时容量随之变大
    log(f"members: 存档线程 blob 估算最大 {worst} B / {cap} B"
        f"（{100 * worst / cap:.1f}%，{name}；容量含层 Δ={cap - ps.THREAD_CAP:#x}）")
    over = [(t, n) for t, n in rows if t > cap]
    if over:
        detail = "、".join(f"{n} {t} B" for t, n in over[:5])
        if ctx.profile == "release":
            die(f"members: 脚本超过存档线程 blob 容量 {cap} B：{detail}——"
                f"存档时会溢出（`uv run python tools/pluto_size.py estimate --members {script_dir}`）")
        log(f"members: ⚠ 脚本超过存档线程 blob 容量：{detail}")


def _compile_tree(src_dir: Path, out_dir: Path, ctx: BuildContext) -> None:
    """把 src_dir 下全部 .lua 独立编译进 out_dir（同名 .lua，逐个调 _compile_lua）。

    ⚠ 这是 release_assertions 的 compiled 参照的**唯一**正确来源，`stage_iso`
    绝不能改传 `ctx.root/"members"/"script"`：那份目录本就是 `stage/script/*`
    的拷贝来源（`assemble_stage`把 `members/` 逐字节拷进 `stage/`），拿它去跟
    `stage/script/*` 比，比的是同一份字节抄了两遍，逐字节相同是同义反复，
    测不出任何漂移——2026-09-03 review 实测复现：`--stage iso` 单独跑一次，
    `members/script` 与 `stage/script` 双双停在上一轮的旧内容，逐字节比对
    照样报"正常"，而实际打进 DATA.BIN 的是任意旧的字节码。这里把
    `lua/final/*.lua`（唯一的源头真相）在断言现场重新编译一遍、产出一份与
    `members/` 毫无瓜葛的第二份参照，"stage 里的字节码确实是编译当前
    lua/final 源得到的"才成为一个有内容的断言。
    """
    for src in sorted(src_dir.glob("*.lua")):
        _compile_lua(src, out_dir / src.name, ctx)


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
    alphas = {a for _n, a in im.getchannel("A").getcolors(256)}
    if alphas <= {0, 255}:
        return _quantize_binary_alpha(im, cap, transparent=0 in alphas)
    return im.quantize(colors=cap, method=Image.Quantize.FASTOCTREE)


def _quantize_binary_alpha(im: Image.Image, cap: int, transparent: bool) -> Image.Image:
    """alpha 只有 0/255 的图：RGB 走 MEDIANCUT，透明另占一个色板项。

    FASTOCTREE 把 alpha 当第四维一起量化，对「大面积不透明照片 + 少量全透明」的图
    （plot 四张 sheet：干净底板重建后 4 万多色）落 256 色的损耗 MSE 37；只对 RGB 做
    MEDIANCUT 同一张图 9.1（2026-09-07 实测）。半透明晕（sysgim/card）不走这里。
    """
    n = cap - (1 if transparent else 0)
    q = im.convert("RGB").quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:3 * n]
    data = list(q.getdata())
    palette = []
    for i in range(n):
        palette.extend((pal[3 * i], pal[3 * i + 1], pal[3 * i + 2], 255))
    if transparent:
        palette.extend((0, 0, 0, 0))
        data = [n if a == 0 else v for v, a in zip(data, im.getchannel("A").getdata())]
    out = Image.new("P", im.size)
    out.putdata(data)
    out.putpalette(palette, rawmode="RGBA")
    return out


def _encode_gim_cached(png: Path, tpl_path: Path, out: Path, force: bool,
                       losses: list[tuple[float, str]], member: str) -> bool:
    """gim 编码，经 build/cache/gim/ 内容哈希缓存。--force 绕过缓存（仍会刷新它）。

    返回是否命中缓存。⚠ 量化损耗（perceptual_mse）只在**未命中、真正编码**时
    计算——命中直接拷贝缓存里的字节，不解码回去验证。调用方必须把"缓存命中"与
    "新编码"分开计数：损耗数字只覆盖新编码的那些，绝不能在全部命中时读成一句
    骗人的『0 张有损耗』——那听起来像是"测过 587 张、一张都没损耗"，实际是
    "一张都没测"。这是量化损耗保留为警告（而非硬失败）这条例外背后的前提：
    警告必须诚实，不能在什么都没测的时候报出一个看着安心的数字。
    """
    key = hashlib.sha256(
        f"v{GIM_CACHE_VERSION}\0".encode() + png.read_bytes() + b"\0" + tpl_path.read_bytes()
    ).hexdigest()[:16]
    cache = CACHE_GIM / f"{key}.gim"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not force and cache.exists():
        shutil.copyfile(cache, out)
        return True
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
    return False


def _require_bake_face(ctx: BuildContext, root: Path, src_dir: str) -> bool:
    """`build/<src_dir>/`（某个烤字面的源 PNG 目录）缺失时该怎么办。

    release 剖面：硬失败。`release_assertions` 看不到这种缺失——它比对的是
    `new_members.json`，而那份记录本就是在这里"跳过整面"之后才写出的，缺失的
    成员干脆不会出现在期望集合里，全部发布闸都测不出来。志愿者拿到的盘不允许
    带着某个烤字面完全空缺发布。

    test 剖面：日志告警后跳过整面——test 剖面允许只烤过部分面就走查其余阶段
    （`--stage members,stage,pack,iso` 这类局部重跑很常见），这是合法状态。

    返回 True 表示调用方应当跳过整面（只有 test 剖面会走到这个分支——release
    分支永远经 `die()` 退出，不会返回）。
    """
    if root.is_dir():
        return False
    if ctx.profile == "release":
        die(f"release 剖面：{src_dir}/ 不存在——先跑生成 build/{src_dir}/ 的 "
            f"tools/bake_*.py（在候选脚本源码里搜 out_dir(\"{src_dir}\") 定位具体是"
            f"哪一个；也可查 layers/manifest.toml 里 [gim] 表旁的注释），"
            f"产出 PNG 后重跑 members 阶段——release 盘不允许带着某个烤字面"
            f"完全空缺发布")
    log(f"members: test 剖面：{src_dir}/ 不存在，跳过整面（部分烤字面缺失在 "
        f"test 剖面是合法状态）")
    return True


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
                  (BASE / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l}
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
    _check_save_size(members_dir / "script", ctx)

    losses: list[tuple[float, str]] = []
    n_gim = n_cached = 0
    for src_dir, prefix in ctx.manifest["gim"]["replace"]:
        root = REPO / "build" / src_dir
        if _require_bake_face(ctx, root, src_dir):
            continue
        for png in sorted(root.rglob("*.png")):
            if png.name.startswith("_"):
                continue    # 烤字器的 QA 对照图（_compare/_cellzoom/…），按约定非入包件
            rel = png.relative_to(root).with_suffix(".gim")
            member = str(Path(prefix) / rel) if prefix else str(rel)
            if member not in base_names:
                die(f"{src_dir}/{png.relative_to(root)} 无对应封包成员 {member}——"
                    f"检查烤字工具输出或 layers/manifest.toml 的 [gim].replace 表")
            if _encode_gim_cached(png, BASE / member, members_dir / member, ctx.force,
                                 losses, member):
                n_cached += 1
            n_gim += 1
    for src_dir, prefix, tpl_member in ctx.manifest["gim"]["new"]:
        root = REPO / "build" / src_dir
        if _require_bake_face(ctx, root, src_dir):
            continue
        for png in sorted(root.rglob("*.png")):
            if png.name.startswith("_"):
                continue
            member = str(Path(prefix) / png.relative_to(root).with_suffix(".gim"))
            if member in base_names:
                die(f"{member} 已是原包成员——layers/manifest.toml 的 [gim].new 表只管新增件")
            if _encode_gim_cached(png, BASE / tpl_member, members_dir / member, ctx.force,
                                 losses, member):
                n_cached += 1
            new_members.add(member)
            n_gim += 1
    losses.sort(reverse=True)
    over = [x for x in losses if x[0] > QUANT_MSE_WARN]
    n_fresh = n_gim - n_cached
    # ⚠ 损耗数字只覆盖"新编码"的 n_fresh 张——缓存命中的 n_cached 张没有被
    # perceptual_mse 测过。两个数分开报，"0 张有损耗"才不会在全部命中时被
    # 误读成"587 张全测过、一张都没损耗"（实际是一张都没测）。
    log(f"members: gim {n_gim} 张（{n_fresh} 新编码，{n_cached} 缓存命中）；"
        f"损耗仅覆盖新编码：有损耗 {len(losses)} 张，超阈({QUANT_MSE_WARN}) {len(over)} 张")
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
                (stage_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l]
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
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manifest), encoding="utf-8")
    return stage_dir


def release_assertions(stage: Path, base: Path, expected_new: set[str],
                       compiled: Path) -> list[str]:
    """出盘前的结构断言。返回问题列表，空 = 放行。

    与旧 check_release_clean 的区别：那个只查「inject_src 里有的脚本是否一致」，
    查不出**多出来的**成员；这个正查成员集合，测试引导的新成员一个也藏不住。
    """
    bad: list[str] = []
    base_names = {json.loads(l)["name"] for l in
                  (base / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l}
    stage_names = {json.loads(l)["name"] for l in
                   (stage / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l}
    allowed = base_names | expected_new
    for extra in sorted(stage_names - allowed):
        bad.append(f"封包树有未声明的成员 {extra}（testboot 残留？）")
    for missing in sorted(allowed - stage_names):
        bad.append(f"封包树缺声明的成员 {missing}")
    if TESTBOOT_MEMBER in stage_names:
        bad.append(f"封包树里有测试引导成员 {TESTBOOT_MEMBER}")
    for p in sorted((stage / "script").glob("*.lua")):
        ref = Path(compiled) / p.name
        if not ref.exists():
            bad.append(f"script/{p.name} 不在本次编译产物里")
        elif ref.read_bytes() != p.read_bytes():
            bad.append(f"script/{p.name} 与本次编译产物不一致")
    return bad


def _stage_fingerprint(stage_dir: Path) -> str:
    """整棵封包树的确定性哈希：按相对路径升序遍历全部文件，把「路径 + 内容」
    一起喂进摘要（与 tools/layers.py::_tree_sha256 同一手法）。`stage_pack` 在
    打包时记一份，`stage_iso` 在断言时重算一份核对——只有两者相同，才能确认
    `iso` 阶段要 splice 的 `DATA.BIN` 真的是从**这一棵**、而不是某个更早、
    后来又被重新 stage 过但没重新 pack 的树打出来的（2026-09-03 review：
    `stage_iso` 断言的是 `ctx.root/"stage"`，splice 的却是 `ctx.root/"DATA.BIN"`，
    此前两者之间没有任何东西把它们锁在一起——漏跑一次 pack，这两者就可能
    互不相干，断言通过也不能说明 DATA.BIN 是"这次"这棵 stage 树打出来的）。
    """
    h = hashlib.sha256()
    names = sorted(p.relative_to(stage_dir).as_posix()
                   for p in stage_dir.rglob("*") if p.is_file())
    for name in names:
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update((stage_dir / name).read_bytes())
        h.update(b"\n")
    return h.hexdigest()


def _check_stage_fingerprint(ctx: BuildContext, stage_dir: Path) -> list[str]:
    """核对 `ctx.root/"DATA.BIN"` 确实是打包**这一棵** stage 树得到的。"""
    fp_path = ctx.root / "stage_fingerprint.txt"
    if not fp_path.exists():
        return [f"缺 {fp_path}（先跑 pack 阶段——iso 需要核对 DATA.BIN 与当前 "
                f"stage 树是否对应同一次打包）"]
    recorded = fp_path.read_text(encoding="utf-8").strip()
    current = _stage_fingerprint(stage_dir)
    if current != recorded:
        return ["DATA.BIN 与当前 stage 树指纹不一致——stage 阶段在上一次 pack 之后"
                "被重新跑过（或这份 DATA.BIN 来自更早一次 pack），两者已经不对应"
                "同一棵树。重新跑 `--stage pack` 用当前 stage 树重新打包再来。"]
    return []


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
                  (BASE / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l}
    assemble_stage(BASE, members_dir, ctx.root / "stage")
    stage_names = {json.loads(l)["name"] for l in
                  ((ctx.root / "stage") / "manifest.jsonl").read_text(encoding="utf-8")
                  .splitlines() if l}
    added = len(stage_names - base_names)
    member_files = sum(1 for f in members_dir.rglob("*") if f.is_file())
    replaced = member_files - added
    log(f"stage: 覆盖 {replaced} 成员，新增 {added} 成员（manifest {len(stage_names)} 行，有序✓）")
    return {"replaced": replaced, "added": added}


# ---------- E 封包 ----------

def stage_pack(ctx: BuildContext) -> dict:
    """databin pack stage → root/DATA.BIN，并记下这次打包对应的 stage 树指纹。

    ⚠ **不碰 build/dist/**（2026-09-03 review Finding 1）：此前这里在 release
    剖面直接同步一份到 `build/dist/DATA.BIN`，于是 `--profile release --stage
    pack` 单独跑一次——不经过 `stage_iso` 的任何断言——就会把发布产物换掉；
    一次完整流程若在 `iso` 阶段的断言处失败，`dist/DATA.BIN` 也早已在这一步
    被换成了未经验证的新包，只是 `game_zh.iso`（连同它的 provenance 副本）还
    没跟上——这正是本任务要杜绝的"半更新的 build/dist/"状态，只是换了个阶段
    重新出现。发布只能来自"断言通过之后"，因此只能是 `stage_iso` 的职责。
    """
    stage_dir = ctx.root / "stage"
    if not (stage_dir / "manifest.jsonl").exists():
        die(f"缺 {stage_dir}（先跑 stage 阶段）")
    fingerprint = _stage_fingerprint(stage_dir)
    out = ctx.root / "DATA.BIN"
    subprocess.run([sys.executable, str(REPO / "tools" / "databin.py"),
                    "pack", str(stage_dir), str(out)], check=True)
    (ctx.root / "stage_fingerprint.txt").write_text(fingerprint, encoding="utf-8")
    log(f"pack: {out} ({out.stat().st_size} B)")
    return {"DATA.BIN": str(out), "stage_fingerprint": fingerprint}


# ---------- F 盘目录 ----------

# ---------- E1 音频包 ----------

SOUND_ORIG = REPO / "build" / "sound" / "orig" / "SOUND.BIN"


def _orig_sound_bin() -> Path:
    """原版 SOUND.BIN：首次自 assets/orig.iso 解出到 build/sound/orig/（99 成员，名单钉在
    data/sound_members.json，layers.py 的 _check_sound 靠那份名单在无资产环境也能过闸）。"""
    if SOUND_ORIG.exists():
        return SOUND_ORIG
    if not ORIG_ISO.exists():
        die(f"缺 {ORIG_ISO}，无法解出原版 SOUND.BIN")
    from tools.umdiso import Iso, SECTOR
    SOUND_ORIG.parent.mkdir(parents=True, exist_ok=True)
    with Iso(str(ORIG_ISO)) as iso:
        rec = iso.find("/PSP_GAME/USRDIR/SOUND.BIN")
        iso.f.seek(rec.lba * SECTOR)
        SOUND_ORIG.write_bytes(iso.f.read(rec.size))
    log(f"sound: 首次自 {ORIG_ISO.name} 解出 SOUND.BIN（{SOUND_ORIG.stat().st_size} B）")
    return SOUND_ORIG


def build_sound_container(orig_bin: Path, tracks: list[tuple[str, bytes]]) -> tuple[bytes, list[str]]:
    """原成员逐字节原样 + 新成员按名有序插入（引擎按名二分查找，与 DATA.BIN 同律）→ 容器字节。

    返回 (容器字节, 有序成员名)。新成员与原成员撞名即拒绝：本项目不改原曲。
    """
    import io
    from tools.databin import read_toc, write_container
    with open(orig_bin, "rb") as f:
        entries = read_toc(f)
        merged: dict[str, bytes] = {}
        for name, off, length in entries:
            f.seek(off)
            merged[name] = f.read(length)
    names = list(merged)
    if names != sorted(names):
        die("原 SOUND.BIN 成员不是按名升序——与已知格式不符，拒绝装配")
    for name, blob in tracks:
        if name in merged:
            die(f"sound: {name} 已是原 SOUND.BIN 成员——本项目不改原曲，换个成员名")
        merged[name] = blob
    ordered = sorted(merged)
    buf = io.BytesIO()
    write_container([(n, merged[n]) for n in ordered], buf)
    return buf.getvalue(), ordered


def _sound_tracks(ctx: BuildContext) -> list[tuple[str, bytes]]:
    cfg = ctx.manifest.get("sound")
    if not cfg or not cfg.get("tracks"):
        return []
    return [(t["member"], (layers.LAYERS / t["artifact"]).read_bytes()) for t in cfg["tracks"]]


def stage_sound(ctx: BuildContext) -> dict:
    """按 manifest [sound] 把新曲装进 SOUND.BIN → build/<profile>/SOUND.BIN。无曲目则空转。"""
    tracks = _sound_tracks(ctx)
    if not tracks:
        log("sound: manifest 无 [sound] 曲目，跳过（沿用原 SOUND.BIN）")
        return {"skipped": True}
    layers._check_sound(ctx.manifest)      # 与 layers.py check 同一道闸：指纹/头部规则/撞名
    blob, ordered = build_sound_container(_orig_sound_bin(), tracks)
    out = ctx.root / "SOUND.BIN"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    fp = hashlib.sha256(blob).hexdigest()
    log(f"sound: {len(tracks)} 首新曲（{', '.join(n for n, _ in tracks)}）→ {out}"
        f"（{len(blob)} B，成员 {len(ordered)}，有序✓）")
    return {"SOUND.BIN": str(out), "members": len(ordered), "added": len(tracks), "sha256": fp}


def _expected_sound(ctx: BuildContext) -> bytes:
    """stage_iso 断言⑤用的独立重算：原版 + 当前 layers/audio 产物重新装配。"""
    blob, _ = build_sound_container(_orig_sound_bin(), _sound_tracks(ctx))
    return blob


# ---------- E2 引擎补丁 ----------

def stage_eboot(ctx: BuildContext) -> dict:
    """按 manifest [eboot] 给解密 EBOOT 打补丁 → build/<profile>/EBOOT.BIN。

    源是 PPSSPP dump 出的解密 PRX 型 ELF（取得步骤：
    docs/ops/eboot-kinsoku-research-2026-09-04.md §1），版权物、不入库，指纹钉在
    manifest，不符拒绝。补丁本体在 layers/eboot/*.toml（tools/eboot_patch.py：
    原字节锚点 + 新字节，幂等，锚点不中整体失败）。没有 [eboot] 节则空转，
    盘里沿用原加密 EBOOT。
    """
    from tools import eboot_patch

    cfg = ctx.manifest.get("eboot")
    if not cfg:
        log("eboot: manifest 无 [eboot] 节，跳过（沿用原 EBOOT.BIN）")
        return {"skipped": True}
    src = REPO / cfg["source"]
    if not src.exists():
        die(f"缺 {src}（解密 EBOOT；取得步骤见 docs/ops/eboot-kinsoku-research-2026-09-04.md §1）")
    data = src.read_bytes()
    if eboot_patch.sha256(data) != cfg["sha256"]:
        die(f"{src} 的 sha256 与 manifest [eboot].sha256 不符——不是登记的纯净源，拒绝施加")
    patches = eboot_patch.load_layers(cfg["order"], profile=ctx.profile)
    out, _report = eboot_patch.apply(data, patches)
    dst = ctx.root / "EBOOT.BIN"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    applied = [n for n in cfg["order"] if any(p.layer == n for p in patches)]
    log(f"eboot: {len(patches)} 条补丁（{', '.join(applied)}）→ {dst}（{len(out)} B）")
    return {"EBOOT.BIN": str(dst), "patches": len(patches), "sha256": eboot_patch.sha256(out)}


def _expected_eboot(cfg: dict) -> bytes:
    """对登记的纯净源重新施加当前层——stage_iso 断言④与 stage_disc 共用的独立重算。"""
    from tools import eboot_patch

    pristine = (REPO / cfg["source"]).read_bytes()
    if eboot_patch.sha256(pristine) != cfg["sha256"]:
        die(f"{cfg['source']} 的 sha256 与 manifest [eboot].sha256 不符")
    out, _ = eboot_patch.apply(pristine, eboot_patch.load_layers(cfg["order"], profile="release"))
    return out


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
    if ctx.manifest.get("eboot"):
        eboot = ctx.root / "EBOOT.BIN"
        if not eboot.exists():
            die(f"缺 {eboot}（先跑 eboot 阶段）")
        shutil.copyfile(eboot, game / "PSP_GAME" / "SYSDIR" / "EBOOT.BIN")
        log(f"disc: EBOOT.BIN（已补丁）已覆入 {game}")
    if _sound_tracks(ctx):
        sound = ctx.root / "SOUND.BIN"
        if not sound.exists():
            die(f"缺 {sound}（先跑 sound 阶段）")
        shutil.copyfile(sound, game / "PSP_GAME" / "USRDIR" / "SOUND.BIN")
        log(f"disc: SOUND.BIN（含新曲）已覆入 {game}")
    return {"game": str(game)}


# ---------- F2 实机盘（ISO 就地替换，release only）----------

def stage_iso(ctx: BuildContext) -> dict:
    """发布断言全过后，把新 DATA.BIN 就地塞回原盘 → build/dist/game_zh.iso。

    实机（CFW）走 ISO，且固件的 isofs 比 PPSSPP 严格得多；故**不重建镜像**，
    只替换该文件并平移尾部，其余字节保持原样。机理见
    docs/ops/umd-iso-repack-research-2026-08-31.md。

    ⚠ **发布闸**：ISO 是交到志愿者手里的那个东西，测试引导绝不能混进去。
    profile != release 直接拒绝——test 剖面的产物结构上到不了这里（各自独立
    输出树），但入口仍显式挡一道，报错要比「凭空找不到文件」更明确。

    三道断言，2026-09-03 review 加固后全部相互独立、缺一不可：
    ① `_check_stage_fingerprint`：`ctx.root/"DATA.BIN"` 确实打包自**这一棵**
       stage 树，不是上一轮遗留、`pack` 被漏跑后还留在磁盘上的旧包（Finding 2）。
    ② `release_assertions` 的 `compiled` 参照来自**独立重编译** `lua/final`
       （`_compile_tree` 现编到一个临时目录），不是 `members/script`——后者与
       `stage/script` 本就是同一次 `assemble_stage` 拷贝的两份副本，逐字节
       相同是同义反复，测不出任何漂移（Finding 3）。
    ③ `release_assertions` 自身的成员集合 / 测试引导成员两项检查。
    只有这三道全过，才真的能说"这次要出的 DATA.BIN 就是编译当前 lua/final 源、
    组装当前 stage 树打出来的那一份"——也只有这时才允许写 build/dist/（Finding 1：
    发布只能是断言通过之后的动作，不能提前发生在 pack 阶段）。
    """
    if ctx.profile != "release":
        die("iso 阶段仅限 release 剖面——test 产物绝不能出现在 build/dist/")

    stage_dir = ctx.root / "stage"
    final_dir = ctx.root / "lua" / "final"
    if not (stage_dir / "manifest.jsonl").exists():
        die(f"缺 {stage_dir}（先跑 stage 阶段）")
    if not final_dir.exists():
        die(f"缺 {final_dir}（先跑 lua 阶段）")

    expected_new = _load_new_members(ctx)
    bad = _check_stage_fingerprint(ctx, stage_dir)
    with tempfile.TemporaryDirectory() as td:
        _compile_tree(final_dir, Path(td), ctx)
        bad += release_assertions(stage_dir, BASE, expected_new, Path(td))
    if bad:
        for b in bad:
            log(f"iso: ✗ {b}")
        die("iso: 发布断言未过，拒绝出盘。跑 "
            "`--stage lua,font,members,stage,pack` 重建干净的封包树再来。")
    log("iso: 发布断言通过（stage 树指纹与 DATA.BIN 对应同一次 pack、成员集合、"
        "脚本与独立重编译产物逐字节核对均正常，无测试引导成员）")

    if not ORIG_ISO.exists():
        die(f"缺 {ORIG_ISO}，无法产实机盘")
    src = ctx.root / "DATA.BIN"
    if not src.exists():
        die(f"缺 {src}（先跑 pack 阶段）")

    from tools.umdiso import DATA_BIN_PATH, replace, verify

    pairs = [(DATA_BIN_PATH, str(src))]
    cfg = ctx.manifest.get("eboot")
    if cfg:
        # 断言④：要出盘的 EBOOT.BIN 必须逐字节等于「对登记的纯净源重新施加当前
        # layers/eboot」的结果——与 lua 的独立重编译核对同一思路，防止 eboot 阶段
        # 漏跑后拿旧产物、或层改了产物没跟上。
        eboot = ctx.root / "EBOOT.BIN"
        if not eboot.exists():
            die(f"缺 {eboot}（先跑 eboot 阶段）")
        if eboot.read_bytes() != _expected_eboot(cfg):
            die("iso: EBOOT.BIN 与当前 layers/eboot 重新施加纯净源的结果不一致——重跑 eboot 阶段")
        log("iso: 断言④通过（EBOOT.BIN 与层重算结果逐字节相同）")
        pairs.append((cfg["iso_path"], str(eboot)))

    snd = ctx.manifest.get("sound")
    if _sound_tracks(ctx):
        # 断言⑤：要出盘的 SOUND.BIN 必须逐字节等于「原版 + 当前 layers/audio 产物重新装配」
        # ——原 99 成员未动、新成员就是清单登记的那份（layers._check_sound 已核指纹与头部）。
        sound = ctx.root / "SOUND.BIN"
        if not sound.exists():
            die(f"缺 {sound}（先跑 sound 阶段）")
        layers._check_sound(ctx.manifest)
        if sound.read_bytes() != _expected_sound(ctx):
            die("iso: SOUND.BIN 与原版+当前音频层重新装配的结果不一致——重跑 sound 阶段")
        log("iso: 断言⑤通过（SOUND.BIN 与音频层重算结果逐字节相同，原成员未动）")
        pairs.append((snd["iso_path"], str(sound)))

    DIST.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, DIST / "DATA.BIN")     # Finding 1：只有闸过了才能发布
    if cfg:
        shutil.copyfile(ctx.root / "EBOOT.BIN", DIST / "EBOOT.BIN")
    if _sound_tracks(ctx):
        shutil.copyfile(ctx.root / "SOUND.BIN", DIST / "SOUND.BIN")
    out = DIST / "game_zh.iso"
    replace(str(ORIG_ISO), str(out), pairs, log=log)
    if not verify(str(out), against=str(ORIG_ISO), log=log):
        die("iso: 结构自检未过")
    log(f"iso: {out}（{out.stat().st_size} B）")
    _drop_stale_ios(ctx)
    return {"game_zh.iso": str(out)}


# ---------- F3 iOS 变体盘（release 随 iso 必出；test 要 --ios）----------

IOS_BUILD = REPO / "build" / "ios"      # 模块/影片产物（跨剖面共享、带指纹核对）
IOS_FW = REPO / "assets" / "fw"         # 解密固件模块原件（版权物不入库），tools/ios_fwmod.py 的输入


def _drop_stale_ios(ctx: BuildContext) -> None:
    """新 game_zh.iso 一旦写出，dist/ 里既有的 iOS 变体盘就与它不同源了——连同 provenance 先删掉。
    release 下 ios 阶段紧接着按新盘重出；这里是兜底：万一 ios 阶段失败，dist 里也不会摆着一对不匹配的盘。"""
    name = (ctx.manifest.get("ios") or {}).get("iso_name")
    if not name:
        return
    for stale in (DIST / name, DIST / f"{name}.provenance.json"):
        if stale.exists():
            stale.unlink()
            log(f"iso: 删除旧的 {stale.name}（与新 game_zh.iso 不同源；ios 阶段随后按新盘重出）")


def _preflight_ios(ctx: BuildContext) -> None:
    """ios 阶段的前置条件在任何阶段动手之前核对：release 下 ios 紧跟 iso，缺东西若拖到那时才失败，
    dist 里的现行盘已经重写、iOS 盘却出不来。"""
    from tools import ios_movie
    missing = [p for p in (IOS_FW / "libmp4.dec.prx", IOS_FW / "mp4msv.dec.prx") if not p.exists()]
    if missing:
        die(f"iOS 盘需要解密固件模块 {', '.join(str(p) for p in missing)}——取得方法见 "
            "docs/ops/movie-playback-ppsspp-2026-09-24.md「固件模块的取得」")
    if not ios_movie.cached(IOS_BUILD / "movie", ctx.manifest["ios"]["movies"]):
        ios_movie.require_ffmpeg()


def stage_ios(ctx: BuildContext, results: dict) -> dict:
    """iOS 变体：EBOOT 多施加 profile=ios 的层，加两个改名固件模块与 44.1k 影片。

    release 由 iso 阶段自动带出（_wanted_stages），test 要 --ios。
    只复用**同一次调用里**已产出并（release）通过发布断言的 DATA.BIN/SOUND.BIN——
    release 要求本次跑过 iso、test 要求本次跑过 disc，否则拒绝，防旧产物冒充。
    两个剖面的 EBOOT 都按 release 层 + ios 层施加：test 目录盘驾驶验证的就是要发的那份 EBOOT。
    """
    need = "iso" if ctx.profile == "release" else "disc"
    if need not in results:
        die(f"ios 阶段需要本次调用同时跑 {need} 阶段（防止拿旧产物出 iOS 盘）")
    from tools import eboot_patch, ios_fwmod, ios_movie
    from tools.umdiso import DATA_BIN_PATH, add_files, replace, verify

    cfg, ios = ctx.manifest["eboot"], ctx.manifest["ios"]
    pristine = (REPO / cfg["source"]).read_bytes()
    if eboot_patch.sha256(pristine) != cfg["sha256"]:
        die(f"{cfg['source']} 的 sha256 与 manifest [eboot].sha256 不符")
    eb, _ = eboot_patch.apply(pristine, eboot_patch.load_layers(cfg["order"], profile="release", ios=True))
    eb_path = ctx.root / "EBOOT.ios.BIN"
    eb_path.write_bytes(eb)
    mods = ios_fwmod.build(IOS_BUILD / "module", fw_dir=IOS_FW)
    movies = ios_movie.build(IOS_BUILD / "movie", ios["movies"], ORIG_ISO)
    log(f"ios: EBOOT.ios.BIN（{eboot_patch.sha256(eb)[:12]}…）、模块 {list(mods)}、影片 {list(movies)}")

    if ctx.profile == "test":
        game, dst = ctx.root / "game", ctx.root / "game_ios"
        if dst.exists():
            shutil.rmtree(dst)
        subprocess.run(["cp", "-Rc", str(game), str(dst)], check=True)   # APFS clone，秒级
        shutil.copyfile(eb_path, dst / "PSP_GAME" / "SYSDIR" / "EBOOT.BIN")
        for name in ios["modules"]:
            shutil.copyfile(mods[name], dst / ios["module_dir"].lstrip("/") / name)
        for name, p in movies.items():
            shutil.copyfile(p, dst / "PSP_GAME" / "USRDIR" / "movie" / name)
        log(f"ios: 目录盘 {dst}")
        return {"game_ios": str(dst)}

    pairs = [(DATA_BIN_PATH, str(DIST / "DATA.BIN")), (cfg["iso_path"], str(eb_path))]
    if _sound_tracks(ctx):
        pairs.append((ctx.manifest["sound"]["iso_path"], str(DIST / "SOUND.BIN")))
    pairs += [(f"/PSP_GAME/USRDIR/movie/{n}", str(p)) for n, p in movies.items()]
    out = DIST / ios["iso_name"]
    partial = DIST / f"{ios['iso_name']}.partial"      # 自检过了才改名，失败不在 dist/ 留半成品
    replace(str(ORIG_ISO), str(partial), pairs, log=log)
    add_files(str(partial), [(f"{ios['module_dir']}/{n}", str(mods[n])) for n in ios["modules"]], log=log)
    if not verify(str(partial), against=str(ORIG_ISO), log=log):
        die(f"ios: 结构自检未过（半成品留在 {partial}）")
    partial.replace(out)
    (DIST / f"{ios['iso_name']}.provenance.json").write_text(json.dumps({
        "base_iso": _hash_or_absent(DIST / "game_zh.iso"),
        "EBOOT.ios.BIN": eboot_patch.sha256(eb),
        "modules": {n: _hash_or_absent(p) for n, p in mods.items()},
        "movies": {n: _hash_or_absent(p) for n, p in movies.items()},
        "iso": _hash_or_absent(out)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"ios: {out}（{out.stat().st_size} B）")
    return {ios["iso_name"]: str(out)}


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
    if ctx.manifest.get("eboot"):
        outputs["EBOOT.BIN"] = _hash_or_absent(ctx.root / "EBOOT.BIN")
    if _sound_tracks(ctx):
        outputs["SOUND.BIN"] = _hash_or_absent(ctx.root / "SOUND.BIN")
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

STAGE_ORDER = ["lua", "font", "members", "stage", "pack", "sound", "eboot", "disc", "iso", "ios", "boot"]
STAGES = {"lua": stage_lua, "font": stage_font, "members": stage_members,
          "stage": stage_stage, "pack": stage_pack, "sound": stage_sound, "eboot": stage_eboot,
          "disc": stage_disc, "iso": stage_iso, "ios": stage_ios, "boot": stage_boot}
#: 缺省 all 时各剖面跑到哪一站——均不含 boot（opt-in）；release 跑到 iso 时自动追加 ios（见 _wanted_stages）。
DEFAULT_STOP = {"release": "iso", "test": "disc"}


def _wanted_stages(profile: str, stage: str, *, ios: bool) -> list[str]:
    """要跑的阶段。release 只要跑 iso（写 dist）就必跑 ios：dist 里现行盘与 iOS 盘总是同出
    （用户 2026-09-24 裁定，不设关闭开关）；test 剖面的 ios 仍是 opt-in（--ios）。"""
    if stage == "all":
        wanted = STAGE_ORDER[:STAGE_ORDER.index(DEFAULT_STOP[profile]) + 1]
    else:
        wanted = stage.split(",")
    if (ios or (profile == "release" and "iso" in wanted)) and "ios" not in wanted:
        wanted.append("ios")
    return wanted


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
    ap.add_argument("--no-cards", action="store_true", help="test 剖面 scene/mainmenu 模式不预置全卡")
    ap.add_argument("--bloat", action="store_true",
                    help="test 剖面 scene 模式：把目标章节脚本的 vms 翻倍，复现存档线程 blob 超容量")
    ap.add_argument("--movie", default="op", choices=["op", "ed"], help="test 剖面 movie 模式：循环播哪一部")
    ap.add_argument("--skippable", action="store_true", help="test 剖面 movie 模式：以可跳过方式调用 playMovie")
    ap.add_argument("--ios", action="store_true",
                    help="test 剖面另出 iOS 目录盘 build/test/game_ios/（release 只要跑 iso 就总会同出 "
                         "build/dist/game_zh_ios.iso，不需要此项）")
    args = ap.parse_args()

    manifest = layers.load_manifest()
    switches = {"fast-boot": False} if args.no_fast_boot else {}
    mode_opts = {"mode": args.mode, "scene": args.scene, "card": args.card,
                "hold": args.hold, "no_cards": args.no_cards, "bloat": args.bloat,
                "movie": args.movie, "skippable": args.skippable}
    ctx = BuildContext(profile=args.profile, root=REPO / "build" / args.profile,
                       manifest=manifest, switches=switches, mode_opts=mode_opts,
                       force=args.force)

    wanted = _wanted_stages(ctx.profile, args.stage, ios=args.ios)
    unknown = set(wanted) - set(STAGES)
    if unknown:
        die(f"未知阶段: {unknown}（可选 {STAGE_ORDER}）")
    if "ios" in wanted:
        _preflight_ios(ctx)

    results: dict[str, dict] = {}
    for name in STAGE_ORDER:
        if name not in wanted:
            continue
        log(f"=== 剖面 {ctx.profile} · 阶段 {name} ===")
        results[name] = (STAGES[name](ctx, results) if name == "ios" else STAGES[name](ctx)) or {}

    _write_provenance(ctx, results)
    log("完成")


if __name__ == "__main__":
    main()
