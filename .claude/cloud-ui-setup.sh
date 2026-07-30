#!/bin/bash
# 粘贴到 claude.ai/code → 环境选择器 → 设置 → “Setup script”。
# 刻意写得极薄且稳定：改动此处会让整机快照重建，而改仓库里的 cloud-setup.sh 不会。
# 本体逻辑一律进仓库（.claude/cloud-setup.sh），走 git 演进而非 UI 文本框。

set -uo pipefail
echo "== 探测上下文（工作目录/仓库位置无官方文档，先记录实况以便日后收紧） =="
echo "PWD=$PWD  HOME=$HOME  USER=$(id -un)"

# 仓库若已 clone，直接交给库内脚本；否则只做机器级预热（解释器进快照）。
SELF=""
for c in "${CLAUDE_PROJECT_DIR:-}" "$PWD" /workspace/* /repo /home/*/*; do
  [[ -n "$c" && -f "$c/.claude/cloud-setup.sh" ]] && { SELF="$c/.claude/cloud-setup.sh"; break; }
done

if [[ -n "$SELF" ]]; then
  bash "$SELF" --mode setup
else
  # 仓库尚未 clone：只做机器级准备。本项目只设 Python 下限 >=3.12，
  # 基镜像自带解释器即可满足，无需预取任何托管 CPython。
  echo "仓库尚未就绪；系统 Python：$(python3 -V 2>&1)"
  git config --global --add safe.directory '*' || true
fi

# 可选（图片烤字工作流启动后再开，会触发一次缓存重建）：
#   中文字库 LXGW WenKai —— png 卡面/选项重制需要，装进快照可省会话内下载
# mkdir -p /usr/share/fonts/truetype/lxgw && cd /usr/share/fonts/truetype/lxgw \
#   && curl -fsSL -o lxgw.ttf https://github.com/lxgw/LxgwWenKai/releases/latest/download/LXGWWenKai-Regular.ttf \
#   && fc-cache -f >/dev/null && echo "字库就绪"

exit 0   # 必须：非零会让环境创建失败
