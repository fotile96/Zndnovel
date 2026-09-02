#!/usr/bin/env -S uv run python
"""按给定字集产 PGF——`docs/ops/pgf-font-research-2026-08-31.md` 生产管线第 1–3 步。

为什么必须裁剪（2026-08-31 实机取证）：全字库 43478 字形的 17px PGF 有 5.3MB，
是原成员 tsukuminpro_e_17.pgf（1.2MB）的 4.4 倍，装进 DATA.BIN 后游戏
`sceFontOpenUserMemory(addr=0, size=-1)` 连报 169 次——引擎的字体缓冲装不下，
拿到空指针，正文改用后备渲染。裁到语料实需字集后体积回落，问题即消失。

字集不再由本模块自己算：2026-09-02 缺字事故（谢幕章 6 字 + s7f 递卡旁白 1 字，
共 7 处空白）的根因正是旧版 `corpus_chars()` 只看译文车道与消息账本，编外的
谢幕章源（`layers/scripts/snr_finale.lua`）不在它的视野里。字集现由
`tools/layers.py` 从 release 剖面的最终源（基座 + 全部层 + 编外脚本）机械算出，
本模块只管拿一份字集文件产 PGF——谁都藏不住了。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# 逐尺寸的字体源：正文用 Regular（比例拉丁更好看），
# 9px 的 ruby/小字槽用 Mono——拉丁步进统一为半角 500/1000，
# 而 Regular 是变宽（j=301、ā=575），注音串宽度不可预测。
TTF_BY_SIZE = {
    17: REPO / "third_party" / "LXGWWenKai-Regular.ttf",
    9: REPO / "third_party" / "LXGWWenKaiMono-Regular.ttf",
}
TTF_DEFAULT = REPO / "third_party" / "LXGWWenKai-Regular.ttf"
# 需要把拉丁步进撑成全角的尺寸（只有 ruby/小字槽需要，正文槽保持比例拉丁）
WIDEN_SIZES = {9}
OUT = REPO / "build" / "font"
# 用 `or` 不用 os.environ.get(key, default) 的双参数形式：后者只看键在不在
# os.environ 里，`export SNDL_TTF_PGF=`（值设成空串）时键是在的，拿到 ""——
# Path("").expanduser() 会归一化成当前目录 `.`，一个真实存在的目录，
# 后续 `.exists()` 判断会被这个假阳性骗过去（同款惯例见 tools/layers.py::provenance
# 与 tools/inject_lua.py，均已按此修过）。空串在此语义上等于没设。
TTF_PGF = Path(os.environ.get("SNDL_TTF_PGF") or "/tmp/pgftool/ttf_pgf")

# 语料之外必须常驻的码位（游戏控制符/版式符/可能的动态拼接）
ALWAYS = (
    [ord(c) for c in
     "≪≫≦≧【】〔〕「」『』（）《》〈〉○●■□◆◇★☆←→↑↓…‥・、。，．：；！？"
     "＋－＝／＼｜～＿＾％＆＃＠＊"]
    + list(range(0x20, 0x7F))            # ASCII 可见
    + list(range(0xFF01, 0xFF5F))        # 全角形
    + list(range(0x3040, 0x30FF))        # 平假名 + 片假名
    + list(range(0x2460, 0x2474))        # 圈数字
    + [ord(c) for c in "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹḿ"]   # 拼音声调
    + [ord(c) for c in "™©®°±×÷§¶†‡"]
)


PINYIN_CHARS = ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹ")


def widen_latin(ttf: Path, out: Path) -> Path:
    """派生一份 TTF：把拼音/拉丁码位的步进撑成全角（em），字形在框内居中。

    为什么必须这么做（2026-08-31 游戏内像素实测）：ruby 的居中由 C 侧 stub 计算，
    实测规律是**按「每个注音字符占一个全角步进」估算宽度**——半角拉丁实际只占半格，
    于是整串注音左偏（Regular −13.5px、Mono −10.0px），而全角假名（−2.0）与全角
    拉丁（+3.5）都基本居中。补空格反而更糟：空格计入字符数、起点继续左移，
    3 个空格时注音已被屏幕左缘截断（实测 −20.5 / −22.5）。
    唯一的解是让拼音字母的步进 = 全角步进，这里在字体层做掉。
    """
    from fontTools.ttLib import TTFont

    font = TTFont(str(ttf))
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    glyf = font.get("glyf")
    widened = 0
    for ch in PINYIN_CHARS:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        adv, lsb = hmtx[name]
        if adv >= upm:
            continue
        ink = 0
        if glyf is not None and name in glyf:
            g = glyf[name]
            ink = (g.xMax - g.xMin) if g.numberOfContours else 0
        # 字形在全角框内水平居中：新 lsb = (em - 墨宽)/2 − 原墨迹起点偏移
        hmtx[name] = (upm, int((upm - (ink or adv)) / 2))
        widened += 1
    bolded = embolden_diacritics(font, glyf)
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(out))
    print(f"[font] 派生 ruby 字体: 步进撑全角 {widened} 个，声调加粗 {bolded} 个 -> {out.name}")
    return out


# 声调轮廓的判定与目标厚度（font units，em=1000）。
# 依据：LXGW Mono 的声调是**独立轮廓**（非复合部件），可单独变形而不动字母本体。
# 实测 9px 下阴平横线只有 62 units = 0.56px——渲染成一条淡灰线，几乎看不见；
# 二/四声 139 units=1.25px、三声 160 units=1.44px。1px ≈ 111 units。
DIACRITIC_Y_MIN = 520      # 高于此的轮廓视为声调（'a' 本体 yMax=486、'i' 含点 495）
DIACRITIC_TARGET_H = 250   # 目标纵向尺寸 ≈ 2.2px @9px
DIACRITIC_MAX_W = 700      # 横向上限（步进已是 1000，留边距）
DIACRITIC_LIFT = 40        # 放大后整体再上移，拉开与字母本体的距离


def embolden_diacritics(font, glyf, target_h: int = DIACRITIC_TARGET_H,
                        max_w: int = DIACRITIC_MAX_W, lift: int = DIACRITIC_LIFT) -> int:
    """把声调轮廓整体等比放大，字母本体与步进不动。

    - **等比**（x 与 y 同倍率）：四个声调靠形状区分（横/斜上/勾/斜下），只加粗纵向
      仍分不出来（2026-08-31 实测：āáǎà 在 9px 下是四个几乎相同的墨块）。
    - **以底边为锚点向上长**：避免压到下方字母本体（'a' 本体 yMax=486，声调底边
      569 起）；上方到 em 顶还有空间。
    - 横向能放开，是因为步进已被 widen_latin 撑成全角 1000 而字母墨迹只占约 400。
    """
    cmap = font.getBestCmap()
    n = 0
    for ch in PINYIN_CHARS:
        name = cmap.get(ord(ch))
        if name is None or glyf is None or name not in glyf:
            continue
        g = glyf[name]
        if g.numberOfContours <= 0:
            continue
        g.expand(glyf)
        coords, ends = g.coordinates, g.endPtsOfContours
        start, touched = 0, False
        for end in ends:
            idx = range(start, end + 1)
            xs = [coords[i][0] for i in idx]
            ys = [coords[i][1] for i in idx]
            ylo, yhi = min(ys), max(ys)
            xlo, xhi = min(xs), max(xs)
            if ylo > DIACRITIC_Y_MIN and yhi > ylo:
                k = target_h / (yhi - ylo)
                if xhi > xlo:
                    k = min(k, max_w / (xhi - xlo))     # 横向不越界
                if k > 1.0:
                    cx = (xlo + xhi) / 2
                    for i in idx:                        # 等比：x 绕中心、y 绕底边
                        x, y = coords[i]
                        coords[i] = (int(round(cx + (x - cx) * k)),
                                     int(round(ylo + (y - ylo) * k + lift)))
                    touched = True
            start = end + 1
        if touched:
            g.recalcBounds(glyf)
            n += 1
    return n


def build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]:
    """按给定字集文件产 PGF。字集由 tools/layers.py 从 release 最终源算出。

    ⚠ 不再自己算字集：2026-09-02 的缺字事故就是因为它只看车道与账本，
    编外的谢幕章源不在视野里，6 个字进了盘却没有字形。
    """
    if not TTF_PGF.exists():
        sys.exit(f"缺 ttf_pgf: {TTF_PGF}（见 docs/ops/pgf-font-research-2026-08-31.md 重建；"
                 f"或设 SNDL_TTF_PGF）")
    # ⚠ 缺字集文件/空字集文件不是「少几个字」那种量级的问题：2026-09-03 实测，
    # ttf_pgf 收到不存在或空的字集文件时，既不报错也不空手而归——它会静默退化成
    # 渲染整个字库（43478 字形、5,319,396 字节），exit code 仍是 0、输出文件仍会
    # 落盘，下面 `proc.returncode != 0 or not out.exists()` 那道闸完全看不出来。
    # 这正是模块 docstring 开头那次引擎崩溃（字体缓冲装不下 5.3MB）的原样复现，
    # 比漏几个字严重得多，必须在喂给 ttf_pgf 之前自己挡住。
    if not charset_path.exists() or charset_path.stat().st_size == 0:
        sys.exit(f"字集文件缺失或为空: {charset_path}"
                 f"（ttf_pgf 遇到这种输入会静默退化成全字库 5.3MB，撑爆引擎字体缓冲，"
                 f"不是变小而是更危险，不能放行）")
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--charset", type=Path, default=REPO / "build" / "release" / "charset.txt",
                    help="字集文件（tools/layers.py 的 write_charset 产物，"
                         "一行一个四位小写十六进制码位）")
    ap.add_argument("--out", type=Path, default=OUT, help="输出目录（默认 build/font）")
    ap.add_argument("--sizes", default="17,9", help="像素尺寸，逗号分隔")
    ap.add_argument("--ruby-size", type=int, default=None,
                    help="ruby/小字槽的实际渲染像素（默认同 9）——声调符在 9px 下只有 1px，调大可提升辨识度，代价是注音变宽")
    args = ap.parse_args()

    sizes = tuple(int(s) for s in args.sizes.split(","))
    build(args.charset, args.out, sizes=sizes, ruby_size=args.ruby_size)


if __name__ == "__main__":
    main()
