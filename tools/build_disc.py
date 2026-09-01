#!/usr/bin/env -S uv run python
"""组装中文化测试盘目录并引导验证——「注入→回编→目录引导」管线编排器。

阶段（--stage 逗号分隔，缺省 all；产物全部落 build/，不碰任何原件）：
  lua    A 译文注入 lua → build/inject/script/          （回写路线定案前为空转）
  gim    B 烤字 png 量化+模板回填 → build/inject/<面>/<名>.gim
  font   C 中文字体成员 → build/inject/pgf/LXGWWenKai-Regular.pgf（新成员）
  stage  D 组装封包树：build/databin --APFS clone--> build/stage，
           覆入 build/inject，新成员追加 manifest
  pack   E databin pack build/stage → build/dist/DATA.BIN
  disc   F 刷新盘目录 build/game（首次自 assets/orig.iso 解出）+ 覆入 DATA.BIN
  iso    F2 实机盘：新 DATA.BIN 就地塞回原盘 → build/dist/game_zh.iso（tools/umdiso.py）
  boot   G PPSSPP 引导冒烟 + 连按 CROSS 推进的截图序列 → build/emu/bootseq/

依据：docs/ops/{ppsspp-local-setup,pgf-font-research,bake-progress}-2026-08-31 与
tools/emu/README。烤字产物目录→封包成员前缀的映射表按 bake 工具族现状写死于
GIM_SOURCES；谢幕章新增成员（crd_201+/title_14_a/snr_finale.lua）属后续扩展，
本编排器 v1 只注入原包已有成员 + 字体新成员。
"""
from __future__ import annotations

import argparse
import bisect
import json
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.emu.imgdiff import perceptual_mse  # noqa: E402
from tools.gimcodec import Gim  # noqa: E402
from PIL import Image  # noqa: E402

DATABIN_SRC = REPO / "assets" / "DATA.BIN"
ORIG_ISO = REPO / "assets" / "orig.iso"
BASE = REPO / "build" / "databin"      # 原包解包镜像（databin.py unpack 产物）
INJECT = REPO / "build" / "inject"     # 本管线的成员级替换/新增件
STAGE = REPO / "build" / "stage"       # 封包树 = BASE 快照 + INJECT 覆盖
DIST = REPO / "build" / "dist"
GAME = REPO / "build" / "game"         # PPSSPP 目录引导用盘目录

# (build/ 下烤字产物目录, 封包成员前缀)；成员名 = 前缀/相对路径(.png→.gim)。
# 前缀为空 = 产物目录自带子目录（mode_zh/music/..、memory_thumb_zh/graphic/..）。
GIM_SOURCES = [
    ("card_zh", "card"), ("select_zh", "select"), ("scene_zh", "scene"),
    ("plot_zh", "plot"), ("sysgim", "sysgim"), ("sysgim_title_zh", "sysgim"),
    ("sysgim_note_zh", "sysgim"), ("sysgim_panel_zh", "sysgim"),
    ("event_zh", "event"), ("cutin_zh", "cutin"), ("cutin_tut_zh", "cutin"),
    ("mode_zh", ""), ("memory_thumb_zh", ""),
]

# 两个字体槽（tools/build_font.py 裁剪产物 → 封包成员名）。
# 槽 0 = 正文 17px（snr_common.lua:5007 已写死该名）；
# 槽 1 = ruby/小字 9px（inject_lua.py 在注入期把 fontLoad(1,…) 改到该名）——
# 实测 ruby 走槽 1，不换就没有中文拼音注音。
FONTS = [
    (REPO / "build" / "font" / "lxgw17.pgf", "pgf/LXGWWenKai-Regular.pgf"),
    (REPO / "build" / "font" / "lxgw09.pgf", "pgf/LXGWWenKai-Regular-09.pgf"),
]

FONT_SIZE_WARN = 1_195_092   # 原 tsukuminpro_e_17.pgf 大小，经验上限


def log(msg: str) -> None:
    print(f"[build_disc] {msg}", flush=True)


def die(msg: str) -> None:
    sys.exit(f"[build_disc] 错误: {msg}")


# ---------- A 译文注入 ----------

#: 测试引导（tools/make_test_boot.py）注入的**新成员**，绝不能进发布盘。
TESTBOOT_MEMBER = "script/snr_test.lua"
#: 译文注入的明文源；发布自检拿它当基准重编译一遍逐字节对。
INJECT_SRC = REPO / "build" / "inject_src"
LUAC = REPO.parent / "pyluadec-refactor" / "build" / "luac_sz4"


def stage_lua() -> None:
    """译文注入 + luac_sz4 重编译（tools/inject_lua.py 全权负责，产物直落 INJECT/script）。

    ⚠ 顺手删掉测试引导留下的新成员：`inject_lua.py` 会清空明文源目录
    （`build/inject_src`）但**不清字节码目录**，于是 `snr_test.lua` 会一直活着
    ——它不属于译文管线的产物，没人会覆盖它，也没人会删它。
    """
    subprocess.run([sys.executable, str(REPO / "tools" / "inject_lua.py")], check=True)
    stray = INJECT / TESTBOOT_MEMBER
    if stray.exists():
        stray.unlink()
        log(f"lua: 清掉测试引导残留 {TESTBOOT_MEMBER}")
    n = len(list((INJECT / "script").glob("*.lua")))
    log(f"lua: {n} 个字节码就位")


def check_release_clean() -> list[str]:
    """发布自检：封包树里的 script 一律等于译文管线的产物，一个测试补丁都没有。

    **查的是 `build/stage`（真正被打进 DATA.BIN 的那份），不是 `build/inject`。**
    两者会不同步——`--stage iso` 可以单独跑，那时 stage 树是上一轮留下的。

    判法是**逐字节重编译比对**，不是查特征串：把 `build/inject_src/*.lua` 用同一个
    luac 重编一遍，与封包树里的对。这样无论测试引导改了什么（剥 IPL、改引导交接、
    短路某张卡的递卡），只要与译文管线的产物不一致就会被抓住，不必逐个模式去认。
    """
    bad: list[str] = []
    manifest = STAGE / "manifest.jsonl"
    if not manifest.exists():
        return [f"{STAGE} 未组装（先跑 stage 阶段）"]
    names = {json.loads(l)["name"] for l in manifest.read_text().splitlines() if l}
    if TESTBOOT_MEMBER in names or (STAGE / TESTBOOT_MEMBER).exists():
        bad.append(f"封包树里有测试引导成员 {TESTBOOT_MEMBER}")
    if not INJECT_SRC.exists():
        return bad + [f"缺 {INJECT_SRC}，无法逐字节核对 script（先跑 lua 阶段）"]
    if not LUAC.exists():
        return bad + [f"缺 {LUAC}，无法逐字节核对 script"]
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        for src in sorted(INJECT_SRC.glob("*.lua")):
            ref = Path(td) / src.name
            proc = subprocess.run([str(LUAC), "-s", "-o", str(ref), str(src)],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                bad.append(f"{src.name} 重编译失败：{proc.stderr.strip()}")
                continue
            packed = STAGE / "script" / src.name
            if not packed.exists():
                bad.append(f"封包树缺 script/{src.name}")
            elif packed.read_bytes() != ref.read_bytes():
                bad.append(f"script/{src.name} 与译文管线产物不一致（疑似测试补丁）")
    return bad


# ---------- B 烤字 → gim ----------

def quantize_for_template(im: Image.Image, cap: int) -> Image.Image:
    """RGBA 烤字图 → P 模式、调色板 ≤cap（模板色板容量）。

    颜色数本就 ≤cap 时走无损精确调色板；否则 FASTOCTREE 量化（RGBA 感知）。
    量化损耗按 CLAUDE.md 规约需目检——产物即最终进包像素，QA 看 build/inject。
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


QUANT_MSE_WARN = 15.0   # 经验阈：>256 色烤字图落 256 色板的典型损耗在 5–10


def stage_gim(force: bool) -> None:
    manifest_names = {json.loads(l)["name"] for l in
                      (BASE / "manifest.jsonl").read_text().splitlines() if l}
    done = skipped = missing = 0
    losses: list[tuple[float, str]] = []
    for src_dir, prefix in GIM_SOURCES:
        root = REPO / "build" / src_dir
        if not root.is_dir():
            log(f"gim: {src_dir}/ 不存在，跳过整面")
            continue
        for png in sorted(root.rglob("*.png")):
            if png.name.startswith("_"):
                continue  # 烤字器的 QA 对照图（_compare/_cellzoom/…），按约定非入包件
            rel = png.relative_to(root).with_suffix(".gim")
            member = str(Path(prefix) / rel) if prefix else str(rel)
            if member not in manifest_names:
                log(f"gim: ⚠ {src_dir}/{png.relative_to(root)} 无对应封包成员 {member}，跳过")
                missing += 1
                continue
            out = INJECT / member
            if out.exists() and not force and out.stat().st_mtime >= png.stat().st_mtime:
                skipped += 1
                continue
            tpl = Gim((BASE / member).read_bytes())
            im = Image.open(png)
            blk = tpl.image
            if blk.fmt in (4, 5):  # index4/8
                im = quantize_for_template(im, tpl.palette.w * tpl.palette.h)
            out.parent.mkdir(parents=True, exist_ok=True)
            blob = tpl.encode_from_pil(im)
            out.write_bytes(blob)
            # 量化损耗自检：解回来与源图做 alpha 感知比对（透明像素不计）
            loss = perceptual_mse(Gim(blob).to_pil(), Image.open(png))
            if loss > 0:
                losses.append((loss, member))
            done += 1
    losses.sort(reverse=True)
    over = [x for x in losses if x[0] > QUANT_MSE_WARN]
    log(f"gim: 编码 {done}，未变跳过 {skipped}，无成员 {missing}；"
        f"有量化损耗 {len(losses)} 张，超阈({QUANT_MSE_WARN}) {len(over)} 张")
    for loss, member in losses[:5]:
        log(f"gim:   最大损耗 MSE={loss:8.2f}  {member}")


# ---------- C 字体 ----------

def stage_font() -> None:
    for src, member in FONTS:
        if not src.exists():
            die(f"字体缺失: {src}（先跑 uv run python tools/build_font.py）")
        out = INJECT / member
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
        size = out.stat().st_size
        log(f"font: {member} <- {src.name} ({size:,} B)")
        if size > FONT_SIZE_WARN:
            log(f"font: ⚠ 体积超过原正文字体 {FONT_SIZE_WARN:,} B——引擎字体缓冲可能"
                f"装不下（症状：sceFontOpenUserMemory addr=0）。建议裁剪字集。")


# ---------- D 组装封包树 ----------

def stage_stage() -> None:
    if not (BASE / "manifest.jsonl").exists():
        die("build/databin 未解包（python3 tools/databin.py unpack assets/DATA.BIN build/databin）")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    # APFS clonefile 秒级快照，不占双份磁盘
    subprocess.run(["cp", "-Rc", str(BASE), str(STAGE)], check=True)
    manifest = [json.loads(l) for l in
                (STAGE / "manifest.jsonl").read_text().splitlines() if l]
    names = {m["name"] for m in manifest}
    replaced = added = 0
    for f in sorted(INJECT.rglob("*")):
        if not f.is_file():
            continue
        member = str(f.relative_to(INJECT))
        dst = STAGE / member
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        if member in names:
            replaced += 1
        else:
            # ⚠ 新成员必须插到**按名排序**的位置，绝不能追加到表尾。
            # 原包文件表 9231 项严格按成员名升序（实测），引擎按名二分查找；
            # 表一乱，新成员就查不到。2026-08-31 三次实测定论：
            #   E1 追加表尾           → sceFontOpenUserMemory(addr=0) ×169，字体不生效
            #   E2 插到 e_17 处(1557) → 同样失败（该位破坏了有序性）
            #   E3 排序位(1556)       → 零错误，中文正常渲染
            idx = bisect.bisect_left([m["name"] for m in manifest], member)
            manifest.insert(idx, {"name": member, "lzss": False, "sha1": ""})
            names.add(member)
            added += 1
            log(f"stage: 新成员 {member} 插到排序位 {idx}")
    order = [m["name"] for m in manifest]
    if order != sorted(order):
        die("文件表失序——引擎二分查找会失败，检查新成员插入逻辑")
    (STAGE / "manifest.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manifest))
    log(f"stage: 覆盖 {replaced} 成员，新增 {added} 成员（manifest {len(manifest)} 行，有序✓）")


# ---------- E 封包 ----------

def stage_pack() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / "DATA.BIN"
    subprocess.run([sys.executable, str(REPO / "tools" / "databin.py"),
                    "pack", str(STAGE), str(out)], check=True)
    log(f"pack: {out} ({out.stat().st_size} B)")


# ---------- F 盘目录 ----------

def stage_disc() -> None:
    if not (GAME / "PSP_GAME").exists():
        if not ORIG_ISO.exists():
            die(f"缺 {ORIG_ISO}，无法组装盘目录")
        log("disc: 首次自 assets/orig.iso 解出盘目录…")
        mnt = Path("/tmp/sndl_iso_mnt")
        out = subprocess.run(["hdiutil", "attach", str(ORIG_ISO), "-mountpoint",
                              str(mnt), "-nobrowse", "-readonly", "-plist"],
                             check=True, capture_output=True)
        try:
            GAME.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", "-R", f"{mnt}/", str(GAME)], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], check=False)
        _ = plistlib.loads(out.stdout)  # 校验挂载回报可解析
    src = DIST / "DATA.BIN"
    if not src.exists():
        die("build/dist/DATA.BIN 不存在（先跑 pack 阶段）")
    shutil.copyfile(src, GAME / "PSP_GAME" / "USRDIR" / "DATA.BIN")
    log(f"disc: DATA.BIN 已覆入 {GAME}")


# ---------- F2 实机盘（ISO 就地替换） ----------

def stage_iso() -> None:
    """把新 DATA.BIN 就地塞回原盘 → build/dist/game_zh.iso。

    实机（CFW）走 ISO，且固件的 isofs 比 PPSSPP 严格得多；故**不重建镜像**，
    只替换该文件并平移尾部，其余字节保持原样。机理见
    docs/ops/umd-iso-repack-research-2026-08-31.md。
    """
    from tools.umdiso import DATA_BIN_PATH, replace, verify

    # ⚠ **发布闸**：ISO 是交到志愿者手里的那个东西，测试引导绝不能混进去。
    # 带着 snr_test.lua 或剥了 IPL 的盘发出去，人家一开机就直接掉进探针，
    # 而且看不出哪里不对——只会以为汉化版坏了。故这里宁可拒绝也不产物。
    bad = check_release_clean()
    if bad:
        for b in bad:
            log(f"iso: ✗ {b}")
        die("iso: 封包树里有测试改动，拒绝出盘。"
            "跑 `--stage lua,gim,font,stage,pack` 重建干净的封包树再来。")
    log("iso: 发布自检通过（script 逐字节等于译文管线产物，无测试引导成员）")

    if not ORIG_ISO.exists():
        die(f"缺 {ORIG_ISO}，无法产实机盘")
    src = DIST / "DATA.BIN"
    if not src.exists():
        die("build/dist/DATA.BIN 不存在（先跑 pack 阶段）")
    out = DIST / "game_zh.iso"
    replace(str(ORIG_ISO), str(out), [(DATA_BIN_PATH, str(src))], log=log)
    if not verify(str(out), against=str(ORIG_ISO), log=log):
        die("iso: 结构自检未过")
    log(f"iso: {out}（{out.stat().st_size} B）")


# ---------- G 引导冒烟 ----------

def stage_boot() -> None:
    import asyncio

    from tools.emu.launcher import Emulator, session

    seq_dir = REPO / "build" / "emu" / "bootseq"
    if seq_dir.exists():
        shutil.rmtree(seq_dir)
    seq_dir.mkdir(parents=True)

    async def run() -> None:
        async with session(lambda: Emulator.app(GAME, graphics="software")) as (emu, cli):
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


STAGES = {"lua": stage_lua, "gim": None, "font": stage_font, "stage": stage_stage,
          "pack": stage_pack, "disc": stage_disc, "iso": stage_iso,
          "boot": stage_boot}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", default="all", help="逗号分隔阶段名或 all")
    ap.add_argument("--force", action="store_true", help="gim 阶段忽略 mtime 全量重编")
    args = ap.parse_args()
    wanted = list(STAGES) if args.stage == "all" else args.stage.split(",")
    unknown = set(wanted) - set(STAGES)
    if unknown:
        die(f"未知阶段: {unknown}（可选 {list(STAGES)}）")
    for name in STAGES:
        if name not in wanted:
            continue
        log(f"=== 阶段 {name} ===")
        if name == "gim":
            stage_gim(args.force)
        else:
            STAGES[name]()
    log("完成")


if __name__ == "__main__":
    main()
