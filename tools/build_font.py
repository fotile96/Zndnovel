#!/usr/bin/env -S uv run python
"""按语料裁剪字库并产 PGF——`docs/ops/pgf-font-research-2026-08-31.md` 生产管线第 1–3 步。

为什么必须裁剪（2026-08-31 实机取证）：全字库 43478 字形的 17px PGF 有 5.3MB，
是原成员 tsukuminpro_e_17.pgf（1.2MB）的 4.4 倍，装进 DATA.BIN 后游戏
`sceFontOpenUserMemory(addr=0, size=-1)` 连报 169 次——引擎的字体缓冲装不下，
拿到空指针，正文改用后备渲染。裁到语料实需字集后体积回落，问题即消失。

字集 = 译文全字集 ∪ 原文残留字（未译面仍要显示日文）∪ ASCII ∪ 全角形 ∪
CJK 标点 ∪ 假名 ∪ 拼音声调元音 ∪ 游戏控制符。宁滥勿缺：漏一个字游戏里就是
一个豆腐块，而每字成本只有几十字节。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.pipelib import read_jsonl  # noqa: E402
from tools.resolve import resolve_map  # noqa: E402

LANE = REPO / "pilot" / "lanes" / "opus" / "data"
TTF = REPO / "third_party" / "LXGWWenKai-Regular.ttf"
OUT = REPO / "build" / "font"
TTF_PGF = Path(os.environ.get("SNDL_TTF_PGF", "/tmp/pgftool/ttf_pgf"))

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


def corpus_chars() -> set[int]:
    """译文 ∪ 原文 的全字集。原文也要——未译面（如 39 条 tr_line 缺口）仍渲染日文。"""
    chars: set[int] = set()

    def eat(s: str | None) -> None:
        if s:
            chars.update(ord(c) for c in s)

    zh = resolve_map(read_jsonl(LANE / "forward.jsonl"), read_jsonl(LANE / "patches.jsonl"))
    for v in zh.values():
        eat(v)
    for row in read_jsonl(LANE / "forward_extra.jsonl"):
        eat(row.get("zh"))
    for name in ("ledger.jsonl", "ledger_extra.jsonl"):
        for row in read_jsonl(REPO / "data" / name):
            eat(row.get("jp"))
    return chars


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", default="17,9", help="像素尺寸，逗号分隔")
    args = ap.parse_args()

    if not TTF_PGF.exists():
        sys.exit(f"缺 ttf_pgf: {TTF_PGF}（见 docs/ops/pgf-font-research-2026-08-31.md 重建；"
                 f"或设 SNDL_TTF_PGF）")
    if not TTF.exists():
        sys.exit(f"缺字体源: {TTF}")

    codes = sorted(corpus_chars() | set(ALWAYS))
    codes = [c for c in codes if 0x20 <= c <= 0xFFFF]   # PGF charmap 只到 BMP
    OUT.mkdir(parents=True, exist_ok=True)
    ucs = OUT / "ucs.txt"
    ucs.write_text("".join(f"{c:04x}\n" for c in codes))
    print(f"[font] 字集 {len(codes)} 码位 -> {ucs}")

    for size in args.sizes.split(","):
        out = OUT / f"lxgw{int(size):02d}.pgf"
        proc = subprocess.run([str(TTF_PGF), str(TTF), str(out), str(ucs), size],
                              capture_output=True, text=True)
        if proc.returncode != 0 or not out.exists():
            sys.exit(f"ttf_pgf 失败({size}px): {proc.stdout[-500:]} {proc.stderr[-500:]}")
        print(f"[font] {size}px -> {out} ({out.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
