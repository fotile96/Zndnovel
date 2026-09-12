#!/usr/bin/env -S uv run python
"""按给定字集产 PGF——`docs/ops/pgf-font-research-2026-08-31.md` 生产管线第 1–3 步。

为什么必须裁剪（2026-08-31 实机取证）：全字库 43478 字形的 17px PGF 有 5.3MB，
是原成员 tsukuminpro_e_17.pgf（1.2MB）的 4.4 倍，装进 DATA.BIN 后游戏
`sceFontOpenUserMemory(addr=0, size=-1)` 连报 169 次，裁到语料实需字集后问题即消失。
归因更正（2026-09-04 逆向 EBOOT，docs/ops/eboot-kinsoku-research-2026-09-04.md §6.2）：
size=-1 是 `pack_file_size` 的"索引与散文件都没找到"返回值，不是缓冲不够；当时的
封包状态已不可复核。裁剪字集仍然必要（内存与加载时间），只是理由不是那一条。

字集不再由本模块自己算：2026-09-02 缺字事故（谢幕章 6 字 + s7f 递卡旁白 1 字，
共 7 处空白）的根因正是旧版 `corpus_chars()` 只看译文车道与消息账本，编外的
谢幕章源（`layers/scripts/snr_finale.lua`）不在它的视野里。字集现由
`tools/layers.py` 从 release 剖面的最终源（基座 + 全部层 + 编外脚本）机械算出，
本模块只管拿一份字集文件产 PGF——谁都藏不住了。
"""
from __future__ import annotations

import argparse
import os
import re
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
# 需要把拉丁步进撑成整数像素的尺寸（只有 ruby/小字槽需要，正文槽保持比例拉丁）
WIDEN_SIZES = {9}
#: ruby 槽的半角步进（px）。引擎 ruby 居中公式的估宽常数已由 layers/eboot/ruby-p5.toml
#: 从 9 改成 5，且 font_draw_string 的推进是 advanceH>>6 **截断成整数像素**——所以拼音
#: 字母与空格的步进必须正好是整数 px：5/9 em = 556/1000（原 Mono 500 会截成 4 px）。
#: 全角字符仍是 1000（9 px），引擎按 2 单位估宽。
RUBY_PITCH_PX = 5
RUBY_FONT_PX = 9
#: 字体配方版本戳：影响 PGF 产物但不改变字集的参数（步进、声调加粗）变了就改这里，
#: build_disc.stage_font 据此强制重建——字集不变时它原本只看 ucs.txt 有没有变。
RECIPE = "lxgw17-regular-proportional-narrowfix / lxgw09-mono-pitch5-diacritic500 / 2026-09-12"

WIDEN_BODY_CHARS = '\u201c\u201d\u00b7'   # ""· — 在 LXGW Regular 里只有 5 px，挤在一起难看
WIDEN_BODY_SIZES = {17}                      # 只改正文字体（17px），ruby 不受影响
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
    """派生一份 TTF：把拼音/拉丁码位与空格的步进撑成 RUBY_PITCH_PX 像素（P=5 → 556/1000 em），
    字形在框内居中。

    来龙去脉：2026-08-31 游戏内实测发现引擎按"每个 ruby 字符 9 px"估宽居中，半角拼音
    整串左偏，于是当时把字母撑成全角 1000。2026-09-04 逆向 EBOOT 后改了引擎侧
    （layers/eboot/ruby-p5.toml：估宽常数 9→5、半角/全角按 1/2 单位计数、空格不再跳过），
    字母只需撑到 5 px 即可精确居中，注音紧凑得多；步进必须是整数像素，因为引擎推进
    时 advanceH>>6 截断（Mono 天然 500 = 4.5 px 会走成 4 px）。空格一并撑到同一步进，
    这样多音节拼音的词距与居中估算一致。数字/标点不在此列（ruby 里不该出现）。
    """
    from fontTools.ttLib import TTFont

    font = TTFont(str(ttf))
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    glyf = font.get("glyf")
    widened = 0
    target = round(upm * RUBY_PITCH_PX / RUBY_FONT_PX)      # 556 @ upm 1000
    for ch in PINYIN_CHARS + " ":
        name = cmap.get(ord(ch))
        if name is None:
            continue
        adv, lsb = hmtx[name]
        if adv == target:
            continue
        ink = 0
        if glyf is not None and name in glyf:
            g = glyf[name]
            ink = (g.xMax - g.xMin) if g.numberOfContours else 0
        # 字形在步进框内水平居中：FreeType 会把轮廓平移到 xMin == lsb，
        # 故 lsb = (步进 − 墨宽)/2 即居中；空格无墨迹，lsb 无关紧要。
        hmtx[name] = (target, int((target - ink) / 2))
        widened += 1
    bolded = embolden_diacritics(font, glyf)
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(out))
    print(f"[font] 派生 ruby 字体: 步进撑到 {target}/{upm} em（{RUBY_PITCH_PX}px@{RUBY_FONT_PX}px）"
          f" {widened} 个，声调加粗 {bolded} 个 -> {out.name}")
    return out


# 声调轮廓的判定与目标厚度（font units，em=1000）。
# 依据：LXGW Mono 的声调是**独立轮廓**（非复合部件），可单独变形而不动字母本体。
# 实测 9px 下阴平横线只有 62 units = 0.56px——渲染成一条淡灰线，几乎看不见；
# 二/四声 139 units=1.25px、三声 160 units=1.44px。1px ≈ 111 units。
DIACRITIC_Y_MIN = 520      # 高于此的轮廓视为声调（'a' 本体 yMax=486、'i' 含点 495）
DIACRITIC_TARGET_H = 250   # 目标纵向尺寸 ≈ 2.2px @9px
DIACRITIC_MAX_W = 500      # 横向上限：步进 556、字母墨迹约 400 居中，相邻字母墨迹间距约 156，
                           # 声调 ≤ 500 居中后离邻字墨迹仍有 28 units，不相碰
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


#: write_charset() 唯一会产出的行形状：四位小写十六进制，无注释无空行。
#: 比 ttf_pgf 自己的 load_ucs_list()（/tmp/pgftool/libpgf.c）宽松得多的解析器
#: 严格得多——它只要首字节不是 '#'/'\n'/'\r'/NUL 就计入返回的行数 i，哪怕
#: sscanf("%x") 什么都没解析出来（ucs 留在初值 0）。两边"合规"标准不同是刻意的：
#: 这里从严，能拦下的坏文件更多；真正兜底两边分歧的是 build() 里的第三道检查
#: （比对 ttf_pgf 自报的 N）。
_UCS_LINE_RE = re.compile(r"^[0-9a-f]{4}$")
#: ttf_pgf 把这行打到 **stderr**（不是 stdout——2026-09-03 用 subprocess 分流实测
#: 确认过，用 2>&1 在终端里看不出区别，容易记错）。
_LOAD_LIST_RE = re.compile(r"Load list from .* : (\d+)")



def widen_body_narrow(ttf: Path, out: Path, cell_px: int = 17) -> Path:
    """派生一份 TTF：把 WIDEN_BODY_CHARS 里的窄字形撑到 cell_px 像素，字形居中。

    这些字在 LXGW Regular 里是比例宽（5.75 px），引擎按 advance>>6 截断到 5 px，
    跟相邻汉字（17 px 一格）挤在一起。撑到 17 px = 与汉字同宽，视觉上不再拥挤。
    """
    from fontTools.ttLib import TTFont

    font = TTFont(str(ttf))
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    glyf = font.get("glyf")
    target = upm * cell_px // 17          # 17px 字体 upm=1000 → target=1000
    widened = 0
    for ch in WIDEN_BODY_CHARS:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        adv, lsb = hmtx[name]
        if adv == target:
            continue
        ink = 0
        if glyf is not None and name in glyf:
            g = glyf[name]
            ink = (g.xMax - g.xMin) if g.numberOfContours else 0
        hmtx[name] = (target, int((target - ink) / 2))
        widened += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(out))
    print(f"[font] 撑宽正文窄字形: {WIDEN_BODY_CHARS!r} → {target}/{upm} em（{cell_px}px）"
          f" {widened} 个 -> {out.name}")
    return out


def _read_charset(charset_path: Path) -> tuple[int, list[int]]:
    """按 write_charset() 的格式解析字集文件。

    返回 (物理行数, 成功解析出的码位列表)。两者之差就是不合规行数——空行、
    注释、位数或大小写不对。这一步只是从严的第一道防线；ttf_pgf 自己的解析器
    不会拒绝这些形状怪异的行（见 `_UCS_LINE_RE` 的注释），所以文件"看似能读"
    不代表 ttf_pgf 读到的就是同一批码位，真正兜底的是 build() 里第三道检查。
    """
    lines = charset_path.read_text(encoding="utf-8").splitlines()
    codes = [int(line, 16) for line in lines if _UCS_LINE_RE.fullmatch(line)]
    return len(lines), codes


def build(charset_path: Path, out_dir: Path, sizes=(17, 9), ruby_size=None) -> list[Path]:
    """按给定字集文件产 PGF。字集由 tools/layers.py 从 release 最终源算出。

    ⚠ 不再自己算字集：2026-09-02 缺字事故（共 7 处空白，见模块开头段）里，
    「编外的谢幕章源不在视野里」这一条根因单独造成了其中 6 字——这正是
    corpus_chars() 必须删除的原因。
    """
    if not TTF_PGF.exists():
        sys.exit(f"缺 ttf_pgf: {TTF_PGF}（见 docs/ops/pgf-font-research-2026-08-31.md 重建；"
                 f"或设 SNDL_TTF_PGF）")
    if not charset_path.exists():
        sys.exit(f"缺字集文件: {charset_path}")
    # ⚠ 「文件存在且字节数非零」不足以说明字集是好的：2026-09-03 复核实测，
    # 一份全空白/全注释、或被截断到只剩几行的字集文件，ttf_pgf 同样会静默
    # 退化——libpgf.c::load_ucs_list() 返回的有效行数 i 一旦是 0，调用方
    # ttfont_znd.c::main() 就 `memset(ucs_list, 1, 65536*4)`，把全部 65536 个
    # 码位标记为"要"，渲染出 43478 字形、5,319,396 字节的全字库；就算 i 不为 0
    # 但只有寥寥几个，产物是一份体积正常、看着人畜无害、实则漏掉几乎全部字符
    # 的 pgf——两种情况 exit code 都是 0、pgf 都会落盘，「返回码非零或输出不
    # 存在」那道闸都看不出来。下面三道检查依次堵这三种情形。
    total_lines, codes = _read_charset(charset_path)
    # 第一道：一个合规码位都没解析出来——最严重的情形，等价于空/缺文件。
    if not codes:
        sys.exit(f"字集文件解析出 0 个码位: {charset_path}"
                 f"（读到 {total_lines} 行，没有一行是合规的四位十六进制）——"
                 f"ttf_pgf 遇到这种输入会静默退化成全字库 5.3MB，撑爆引擎字体缓冲")
    # 第二道：下限不是拍脑袋定的——ALWAYS 无条件并入 charset_of()（tools/layers.py）
    # 算出的每一份字集，是任何合法字集都必然包含的最小公共集合，字数低于它只能是
    # 截断或损坏。用 set() 去重而不是直接 len(ALWAYS)：ALWAYS 列表本身有 23 个
    # 重复码位（如全角括号，同时出现在手写符号串与 range(0xFF01,0xFF5F) 里），
    # charset_of() 最终经 `set(always) | ...` 去重成 472 个而非 495 个——用未去重
    # 的 495 当下限会把一份恰好只含 ALWAYS、不多不少的合法字集也拒掉，是过严
    # 而非过宽，与这里"宁滥勿缺"的方向正好相反。
    min_codes = len(set(ALWAYS))
    if len(codes) < min_codes:
        sys.exit(f"字集文件只解析出 {len(codes)} 个码位（读到 {total_lines} 行）: "
                 f"{charset_path}——少于 ALWAYS 常驻表去重后的 {min_codes} 个，"
                 f"任何合法字集都不可能比这更小，判定为截断或损坏")
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for size in sizes:
        ttf = TTF_BY_SIZE.get(size, TTF_DEFAULT)
        if not ttf.exists():
            sys.exit(f"缺字体源: {ttf}")
        if size in WIDEN_SIZES:
            ttf = widen_latin(ttf, out_dir / f"_widened{size:02d}.ttf")
        if size in WIDEN_BODY_SIZES:
            ttf = widen_body_narrow(ttf, out_dir / f"_body{size:02d}.ttf")
        render = ruby_size if (size in WIDEN_SIZES and ruby_size) else size
        out = out_dir / f"lxgw{size:02d}.pgf"
        proc = subprocess.run([str(TTF_PGF), str(ttf), str(out), str(charset_path),
                               str(render)], capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            sys.exit(f"ttf_pgf 失败({size}px): {proc.stdout[-500:]} {proc.stderr[-500:]}")
        # 第三道：前两道检查只看我们自己解析出的码位数，堵不住"文件本身没问题，
        # 但 ttf_pgf 实际读到的和我们以为的不一样"这种分歧（比如它的宽松解析器
        # 把我们判定为不合规、没计入 codes 的行也算了进去）。ttf_pgf 会在 stderr
        # 自报"Load list from ... : N"，直接拿来跟 len(codes) 对账；找不到这行
        # 本身也当失败处理——output 格式变了，沉默地不比对不是通过，是失明。
        m = _LOAD_LIST_RE.search(proc.stderr)
        if not m:
            sys.exit(f"ttf_pgf({size}px) 没打印「Load list from ...: N」，"
                     f"无法核对它实际读到几个码位——输出格式可能变了，不能假装通过\n"
                     f"stdout: {proc.stdout[-300:]}\nstderr: {proc.stderr[-300:]}")
        loaded = int(m.group(1))
        if loaded != len(codes):
            sys.exit(f"ttf_pgf({size}px) 实际读到 {loaded} 个码位，"
                     f"与我们解析出的 {len(codes)} 个不一致: {charset_path}——"
                     f"两边对这份字集的理解分歧了，不能放行")
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
