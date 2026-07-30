#!/usr/bin/env bash
# 云端环境初始化的「真逻辑」，被两处调用：
#   1) UI setup script（首次建环境，root，约 5 分钟预算，之后整机快照）→ --mode setup
#   2) .claude/settings.json 的 SessionStart hook（每次会话，须快且幂等）→ --mode session
# 因此本脚本必须幂等：重复运行只做增量，不重复下载。
#
# 设计约束（据 code.claude.com/docs/en/cloud-environments）：
#   * UI setup 脚本非零退出会让整个环境创建失败，而其日志位置无文档 —— 故本脚本
#     **永远 exit 0**，一切问题写进报告文件，由 SessionStart 阶段显式呈现。
#   * setup 阶段的工作目录、仓库是否已 clone、环境变量是否已注入，均无文档 ——
#     故仓库路径靠探测，缺仓库时自动降级为「只做机器级预热」。
set -uo pipefail

MODE="session"
[[ "${1:-}" == "--mode" ]] && MODE="${2:-session}"

REPORT_SYS="/var/log/claude-cloud-setup.log"
MARKER="lua_scripts/snr_common.lua"   # 本仓库指纹（配合 tools/pipelib.py 双重确认）
WARNINGS=()

log()  { printf '[cloud-setup:%s] %s\n' "$MODE" "$*"; }
warn() { WARNINGS+=("$*"); printf '[cloud-setup:%s] WARN %s\n' "$MODE" "$*" >&2; }

# ---------- 1. 定位仓库（路径无文档，逐级退让探测） ----------
find_repo() {
  local c
  for c in "${CLAUDE_PROJECT_DIR:-}" "$PWD" "$(dirname "${BASH_SOURCE[0]}")/.."; do
    [[ -n "$c" && -f "$c/$MARKER" && -f "$c/tools/pipelib.py" ]] && { (cd "$c" && pwd); return 0; }
  done
  # 兜底：在常见挂载根下限深搜索，避免全盘遍历
  for root in /workspace /repo /srv /home /root; do
    [[ -d "$root" ]] || continue
    c=$(find "$root" -maxdepth 6 -type f -path "*/$MARKER" -print -quit 2>/dev/null) || true
    [[ -n "$c" ]] && { (cd "$(dirname "$(dirname "$c")")" && pwd); return 0; }
  done
  return 1
}

# ---------- 2. 机器级预热（无需仓库，成果进快照） ----------
prewarm_machine() {
  command -v uv >/dev/null || { warn "uv 未预装且未安装成功，云端镜像契约有变，需人工介入"; return; }
  log "$(uv --version 2>/dev/null)"
  if [[ "$MODE" == "setup" ]]; then
    # 仅建环境时做机器级改动：root 建的仓库要能被会话用户操作
    git config --global --add safe.directory '*' 2>/dev/null || true
    # 本项目只设 Python 下限（pyproject `>=3.12`，不入 .python-version），
    # 基镜像自带的解释器即可满足 —— 故此处不预取、不下载、无归属问题。
    local sysver
    sysver=$(python3 -V 2>/dev/null) || sysver="未知"
    log "系统 Python：$sysver（下限 >=3.12，无需托管解释器）"
  fi
}

# ---------- 3. 仓库级准备（幂等，setup 与 session 共用） ----------
prepare_repo() {
  cd "$REPO" || { warn "无法进入仓库 $REPO"; return; }
  # 依赖：先严（锁一致性即可复现），失败再宽（保证环境可用）
  if uv sync --locked >/dev/null 2>&1; then
    log "uv sync --locked OK（依赖与 uv.lock 一致）"
  else
    warn "uv.lock 与 pyproject.toml 漂移（--locked 退出 1）；已回退 uv sync 重解析，请在本地 uv lock 后提交"
    uv sync >/dev/null 2>&1 || warn "uv sync 失败：依赖未就绪，多数工具将无法运行"
  fi
  # root 建的 .venv 不能挡住非 root 会话
  [[ -d .venv ]] && chown -R --reference=pyproject.toml .venv 2>/dev/null || true

  # 流水线预期目录（work/ 已 gitignore，不会污染工作树）
  mkdir -p work/ctx work/out

  # 冒烟：只诊断、不决定退出码
  local t0=$SECONDS
  local gen
  for gen in build_ledger build_dag; do
    if uv run python "tools/$gen.py" --check 2>/dev/null | grep -q 'check: OK'; then
      log "$gen --check OK（生成物与 lua 源一致）"
    else
      warn "$gen --check 非 OK：入库生成物与 lua/解析器不同步，动它之前须先重建"
    fi
  done
  if uv run pytest -q >work/setup-pytest.log 2>&1; then
    log "pytest 全绿（$(tail -1 work/setup-pytest.log)）"
  else
    warn "pytest 未全绿：$(grep -E '^[0-9]+ (failed|error)' work/setup-pytest.log | tail -1)（详见 work/setup-pytest.log）"
  fi
  log "冒烟耗时 $((SECONDS - t0))s"

  # SDD 证据保全：.superpowers/sdd/ 被插件重写为 .gitignore='*'，新建的 brief/report
  # 不 git add -f 就永远不出现在 git status —— 云端环境销毁即永久丢失（CLAUDE.md 规约）。
  local lost
  lost=$(git ls-files --others --ignored --exclude-standard -- .superpowers 2>/dev/null | grep -c '\.md$') || lost=0
  ((lost > 0)) && warn "$lost 份 SDD 证据（*.md）未入库且被忽略，环境销毁即丢失：git add -f .superpowers/sdd/*/*.md"

  # 基线快照，供会话开场自检
  {
    echo "repo=$REPO"
    echo "head=$(git rev-parse --short HEAD 2>/dev/null) $(git log -1 --format=%s 2>/dev/null)"
    echo "dirty=$(git status --porcelain 2>/dev/null | wc -l) 个未提交改动"
    echo "python=$(uv run python -V 2>/dev/null)"
    for f in data/ledger.jsonl data/forward.jsonl data/patches.jsonl; do
      [[ -f $f ]] && echo "$f=$(wc -l <"$f") 行" || echo "$f=（不存在）"
    done
    # 跨环境接力的实际入口：最新计划的执行台账（memory 也指向它）
    local ledger_md
    ledger_md=$(ls -t .superpowers/sdd/*/progress.md 2>/dev/null | head -1)
    if [[ -n "$ledger_md" ]]; then
      echo "--- 台账 $ledger_md（末 6 行）---"
      tail -6 "$ledger_md"
    fi
  } > work/setup-baseline.txt
}

# ---------- 主流程 ----------
REPO="$(find_repo || true)"
prewarm_machine
if [[ -n "$REPO" ]]; then
  prepare_repo
else
  warn "未找到仓库（setup 阶段可能尚未 clone）；已只做机器级预热，仓库级准备留给 SessionStart"
fi

# ---------- 报告（日志位置无文档 → 双写，且 session 阶段打到 stdout） ----------
{
  echo "=== claude cloud setup 报告 mode=$MODE ==="
  [[ -n "$REPO" && -f "$REPO/work/setup-baseline.txt" ]] && cat "$REPO/work/setup-baseline.txt"
  if ((${#WARNINGS[@]})); then
    printf '需要注意 %d 项：\n' "${#WARNINGS[@]}"
    printf '  - %s\n' "${WARNINGS[@]}"
  else
    echo "无告警：环境就绪"
  fi
} | tee -a "$REPORT_SYS" 2>/dev/null || true

exit 0   # 刻意始终为 0：非零会让环境创建整体失败，而那比带告警的可用环境更糟
