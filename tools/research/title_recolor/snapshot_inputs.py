#!/usr/bin/env python3
"""把调色研究要的 4 张输入填进 inputs/，逐张核对 sha256。

为什么需要这个脚本：`probe.py` 的 `paths` 表记的是「输入原本来自仓库哪个文件」，但其中
两张**不能**按那张表从工作区取——`docs/finale/assets/title_01_c.{src,}png` 现在已经是
**调色成品**，再跑一次调色就是二次处理。调色前的那一版完整存在于 git，这里按提交号取。

日文参照与菜单底图取自只读基座 `png/`，直接从工作区拿；哈希对不上会硬失败（基座本该
逐字节不变，对不上说明出事了，不是该悄悄放过的事）。
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
IN = ROOT / "inputs"

#: 调色前输入所在的提交。52abe46 = 「题名中文 logo 换第二版素材」，即本次调色的输入态。
PRE_RECOLOR_REF = "52abe46"

#: (目标文件名, 来源, sha256)。来源 "git:<路径>" 走 `git show`，"work:<路径>" 取工作区。
INPUTS = [
    ("japanese.png", "work:png/sysgim/title_01_a.png",
     "a8c361a3a2c6ed27a00f02865058128305f1ebbf6c13808e9e7e8e16f781e849"),
    ("menu_bg.png", "work:png/bg/bg_4_a_0.png",
     "a6475fc14ba0494806ee24484fb7f3fcb3fc9a2e04dd9abf50e11e063bc2f335"),
    ("chinese_source.png", "git:docs/finale/assets/title_01_c.src.png",
     "fc16d60b721b4556c6d1e086b2a73abf6c513f4391f5ecb327ae2eea12ecb97b"),
    ("chinese_baked.png", "git:docs/finale/assets/title_01_c.png",
     "85fa1966a91ea1ed9ca5f4671bfb06633f5745c7bb14f2b3742c6c6459db3baa"),
]


def fetch(source: str) -> bytes:
    kind, path = source.split(":", 1)
    if kind == "work":
        return (REPO / path).read_bytes()
    out = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE_RECOLOR_REF}:{path}"],
                         capture_output=True)
    if out.returncode != 0:
        sys.exit(f"git show {PRE_RECOLOR_REF}:{path} 失败：{out.stderr.decode().strip()}")
    return out.stdout


def main() -> None:
    IN.mkdir(parents=True, exist_ok=True)
    for name, source, want in INPUTS:
        blob = fetch(source)
        got = hashlib.sha256(blob).hexdigest()
        if got != want:
            sys.exit(f"{name} 来自 {source} 的内容 sha256 不符\n  期望 {want}\n  实得 {got}\n"
                     f"——基座被动过、或 {PRE_RECOLOR_REF} 这个提交不是调色前那一版了，先查清楚再跑")
        (IN / name).write_bytes(blob)
        print(f"{name:20s} ← {source:46s} {got[:16]}… ✓")
    print(f"\n输入就位：{IN}")


if __name__ == "__main__":
    main()
