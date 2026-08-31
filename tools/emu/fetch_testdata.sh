#!/usr/bin/env bash
# 下载 pspautotests 的少量现成 PRX 到 build/emu/testdata/（GPL 二进制，不入库）。
# 幂等：已存在且非空即跳过；-f 强制重下。
set -euo pipefail
BASE="https://raw.githubusercontent.com/hrydgard/pspautotests/master/tests"
DEST="$(cd "$(dirname "$0")/../.." && pwd)/build/emu/testdata"
FORCE="${1:-}"
mkdir -p "$DEST"

fetch() {
    local rel="$1" out="$DEST/$(basename "$1")"
    if [[ -s "$out" && "$FORCE" != "-f" ]]; then echo "skip $out"; return; fi
    curl -fsSL "$BASE/$rel" -o "$out"
    echo "ok   $out"
}

fetch cpu/cpu_alu/cpu_alu.prx        # 纯 CPU 测试：传输/断点用例的替身游戏
fetch cpu/cpu_alu/cpu_alu.expected
fetch ctrl/sampling/sampling.prx     # 打印按键位掩码：输入注入验证

# GE 帧转储（官方 frametest CI 测试集里最小的一个）：像素回归通路验证
DUMP_URL="https://raw.githubusercontent.com/hrydgard/ppsspp-frametest-ci/master/dumps/Depth/21797%20Taiko%20no%20Tatsujin%20NPJH50426_0002.zip"
if [[ ! -s "$DEST/frame.ppdmp" || "$FORCE" == "-f" ]]; then
    curl -fsSL "$DUMP_URL" -o "$DEST/frame.zip"
    (cd "$DEST" && unzip -qo frame.zip && rm frame.zip)
    # zip 内文件名带空格，归一化成 frame.ppdmp
    find "$DEST" -name "*.ppdmp" ! -name "frame.ppdmp" -exec mv {} "$DEST/frame.ppdmp" \;
    echo "ok   $DEST/frame.ppdmp"
else
    echo "skip $DEST/frame.ppdmp"
fi
