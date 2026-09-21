#!/usr/bin/env bash
# 构建本项目用的 atracdenc（ATRAC3+ 编码器）→ build/atracdenc/build/src/atracdenc。幂等，可重跑。
#
# 钉在 upstream cb17070（2026-09-08），施加 tools/atracdenc-744.patch 两处改动：
#   1. CMakeLists.txt：macOS 只编 arm64（上游强制 universal，本机没有 x86_64 的 libsndfile）；
#   2. src/atrac/at3p/at3p.cpp：AT3+ 帧长 2048 → 744 B（= 128 kbps，与原版 99 首相同；
#      `--bitrate` 对 AT3+ 无效，只能改源）。
# 依赖：git、cmake、C++ 工具链、libsndfile（macOS: brew install libsndfile）。
# 用法：bash tools/build_atracdenc.sh   （环境变量 SNDL_ATRACDENC_DIR 可换目录）
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DST="${SNDL_ATRACDENC_DIR:-$REPO/build/atracdenc}"
COMMIT=cb170709f836cb43dc0312455188c791159d81dc
PATCH="$REPO/tools/atracdenc-744.patch"

if [ ! -d "$DST/.git" ]; then
  git clone --quiet https://github.com/dcherednik/atracdenc.git "$DST"
fi
git -C "$DST" fetch --quiet origin
git -C "$DST" checkout --quiet --force "$COMMIT"
git -C "$DST" submodule update --init --recursive --quiet
git -C "$DST" apply --check "$PATCH" 2>/dev/null && git -C "$DST" apply "$PATCH"
# 幂等：已打过补丁时 apply --check 失败，用 reverse 校验确认在位
git -C "$DST" apply --check --reverse "$PATCH"

cmake -S "$DST" -B "$DST/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$DST/build" --parallel >/dev/null
BIN="$DST/build/src/atracdenc"
test -x "$BIN"
echo "atracdenc @ $COMMIT (+744 patch) -> $BIN"
