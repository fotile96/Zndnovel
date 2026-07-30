#!/usr/bin/env bash
# 云端环境初始化的「真逻辑」。两个入口：
#   1) UI setup script（首次建环境，root，约 5 分钟预算，之后整机快照）→ --mode setup
#   2) 每次新会话开场**手动**执行 → --mode session
#
# ⚠ 为什么是手动：仓库级 .claude/settings.json 在云端整体不被采纳（hooks/enabledPlugins/
#   extraKnownMarketplaces/permissions 四项皆失效，实证见 docs/ops/cloud-acceptance-2026-07-30.md
#   §二.8），SessionStart hook 永不派生。该结论已定案，本脚本不再重复验证它；
#   诊断改为探测家目录下真正生效的用户级配置与账户同步的 skills（见 §1.5）。
#   settings.json 仍保留，因为本地会话有效。
# 因此本脚本必须幂等：重复运行只做增量，不重复下载。
#
# 其余设计约束（据 code.claude.com/docs/en/cloud-environments）：
#   * UI setup 脚本非零退出会让整个环境创建失败，而其日志位置无文档 —— 故本脚本
#     **永远 exit 0**，一切问题写进报告文件。
#   * setup 阶段的工作目录、仓库是否已 clone、环境变量是否已注入，均无文档 ——
#     故仓库路径靠探测（并把命中路径记进报告），缺仓库时降级为只做机器级准备。
set -uo pipefail

MODE="session"
[[ "${1:-}" == "--mode" ]] && MODE="${2:-session}"

REPORT_SYS="/var/log/claude-cloud-setup.log"
MARKER="lua_scripts/snr_common.lua"   # 本仓库指纹（配合 tools/pipelib.py 双重确认）
WARNINGS=()

log()  { printf '[cloud-setup:%s] %s\n' "$MODE" "$*"; }
warn() { WARNINGS+=("$*"); printf '[cloud-setup:%s] WARN %s\n' "$MODE" "$*" >&2; }

# ---------- 1. 定位仓库（路径无文档，逐级退让探测） ----------
# 输出 "命中方式|仓库绝对路径"（未找到则路径为空）。之所以把两者塞进一行：
# 本函数在命令替换的子 shell 里运行，普通变量赋值传不回父 shell。
# 记录命中方式是为了留证——首次验收只能靠反推探测路径（验收记录 §二.3）。
find_repo() {
  local c name
  for name in CLAUDE_PROJECT_DIR PWD SCRIPT_DIR; do
    case $name in
      CLAUDE_PROJECT_DIR) c="${CLAUDE_PROJECT_DIR:-}" ;;
      PWD)                c="$PWD" ;;
      SCRIPT_DIR)         c="$(dirname "${BASH_SOURCE[0]}")/.." ;;
    esac
    if [[ -n "$c" && -f "$c/$MARKER" && -f "$c/tools/pipelib.py" ]]; then
      echo "$name|$(cd "$c" && pwd)"; return 0
    fi
  done
  # 兜底：在常见挂载根下限深搜索，避免全盘遍历
  for root in /workspace /repo /srv /home /root; do
    [[ -d "$root" ]] || continue
    c=$(find "$root" -maxdepth 6 -type f -path "*/$MARKER" -print -quit 2>/dev/null) || true
    [[ -n "$c" ]] && { echo "find:$root|$(cd "$(dirname "$(dirname "$c")")" && pwd)"; return 0; }
  done
  echo "未找到|"
  return 1
}

# ---------- 1.5 用户级配置：技能的两个可能载体 ----------
# 仓库级 .claude/settings.json 不被采纳（结论已定案，不再验证），故技能只可能来自家目录：
#   载体一 ~/.claude/skills/            —— 账户级独立 skill，经 CLAUDE_CODE_SYNC_SKILLS 同步
#   载体二 ~/.claude/plugins/cache/…    —— 插件形态（本机即如此），技能体在 <市场>/<插件>/<版本>/
# 首次验收时 SKIP_PLUGIN_MARKETPLACE=true 掐死了载体二；账户级安装后是否改观，正是要测的。
# 注意 plugins/data/ 只是每插件运行时目录（本机为空），**不能**当作「插件已装」的判据。
USER_CFG=""
inspect_user_config() {
  local hc="${HOME:-/root}/.claude" pd="${HOME:-/root}/.claude/plugins"
  local n_skill=0 n_plugin_skill=0
  [[ -d "$hc/skills" ]] && n_skill=$(find "$hc/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
  [[ -d "$pd/cache" ]] && n_plugin_skill=$(find "$pd/cache" -name SKILL.md 2>/dev/null | wc -l)
  USER_CFG="$(
    echo "user_config_dir=$hc（$([[ -d "$hc" ]] && echo 存在 || echo 不存在)）"
    echo "user_settings.json=$([[ -f "$hc/settings.json" ]] && echo 有 || echo 无)"
    echo "user_launcher-settings.json=$([[ -f "$hc/launcher-settings.json" ]] && echo 有 || echo 无)"
    # 载体一：账户同步的独立 skill（CLAUDE_CODE_SYNC_SKILLS）
    if [[ -d "$hc/skills" ]]; then
      echo "user_skills=$n_skill 个：$(ls -1 "$hc/skills" 2>/dev/null | tr '\n' ' ')"
    else
      echo "user_skills=（$hc/skills 不存在）"
    fi
    # 载体二：插件（本机形态；技能体在 cache/<市场>/<插件>/<版本>/，data/ 只是每插件运行时目录、
    # 常为空，故不能拿它当「已装」判据）
    if [[ -d "$pd" ]]; then
      echo "user_plugins_installed=$(find "$pd/cache" -mindepth 3 -maxdepth 3 -type d 2>/dev/null | sed "s|$pd/cache/||" | tr '\n' ' ')"
      echo "user_plugin_skills=$n_plugin_skill 份 SKILL.md"
      echo "user_plugins_data=$(ls -1 "$pd/data" 2>/dev/null | tr '\n' ' ')"
    else
      echo "user_plugins=（$pd 不存在）"
    fi
    echo "SKIP_PLUGIN_MARKETPLACE=${SKIP_PLUGIN_MARKETPLACE:-（未设置）}  CLAUDE_CODE_SYNC_SKILLS=${CLAUDE_CODE_SYNC_SKILLS:-（未设置）}"
  )"
  while IFS= read -r line; do log "$line"; done <<< "$USER_CFG"
  # 两个载体任一到位即可；都空才是真不可用
  ((n_skill == 0 && n_plugin_skill == 0)) \
    && warn "账户级 skill 与插件均未到位（~/.claude/skills 与 plugins 都没有技能体）：superpowers 等流程技能不可用，SDD 需手工执行"
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
  # extract_*.py 规约是「系统 python3 直接可跑」：云端镜像默认 python3 为 3.11，
  # 比 venv 的 3.12 更严，故用系统解释器校验而非 uv run（2026-07-30 验收 §五.12）。
  if python3 -m py_compile tools/extract_*.py 2>/dev/null; then
    log "extract_*.py 在系统 $(python3 -V 2>&1) 下可编译（纯 stdlib 规约成立）"
  else
    warn "extract_*.py 在系统 $(python3 -V 2>&1) 下编译失败：违反「系统 python3 直接可跑」规约"
  fi
  rm -rf tools/__pycache__ 2>/dev/null || true
  log "冒烟耗时 $((SECONDS - t0))s"

  # 云端是浅克隆且不带 tag：CLAUDE.md 反复引用的 skeleton-v1 冻结点在那边不存在
  if [[ -z "$(git tag -l 2>/dev/null)" ]]; then
    warn "本克隆无任何 tag（skeleton-v1 冻结点不可解析）：需要时先 git fetch --tags origin"
  fi
  [[ -f .git/shallow ]] && log "浅克隆（$(git rev-list --count HEAD 2>/dev/null) 个 commit），完整历史需 git fetch --unshallow"

  # SDD 证据保全：.superpowers/sdd/ 被插件重写为 .gitignore='*'，新建的 brief/report
  # 不 git add -f 就永远不出现在 git status —— 云端环境销毁即永久丢失（CLAUDE.md 规约）。
  local lost
  lost=$(git ls-files --others --ignored --exclude-standard -- .superpowers 2>/dev/null | grep -c '\.md$') || lost=0
  ((lost > 0)) && warn "$lost 份 SDD 证据（*.md）未入库且被忽略，环境销毁即丢失：git add -f .superpowers/sdd/*/*.md"

  # 基线快照，供会话开场自检。首行自述 mode 与时间：
  # 「文件存在 ⇒ session hook 已跑过」是错的（它可能是 --mode setup 留下的），
  # 2026-07-30 验收即栽在这个判据上。
  {
    echo "generated_by=--mode $MODE at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "repo=$REPO (found_by=$FOUND_BY)"
    echo "head=$(git rev-parse --short HEAD 2>/dev/null) $(git log -1 --format=%s 2>/dev/null)"
    echo "dirty=$(git status --porcelain 2>/dev/null | wc -l) 个未提交改动"
    echo "python=$(uv run python -V 2>/dev/null)"
    echo "$USER_CFG"
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
PROBE="$(find_repo || true)"
FOUND_BY="${PROBE%%|*}"
REPO="${PROBE#*|}"
prewarm_machine
inspect_user_config
if [[ -n "$REPO" ]]; then
  prepare_repo
else
  warn "未找到仓库（setup 阶段可能尚未 clone）；已只做机器级预热；仓库级准备留给会话开场手动执行 --mode session"
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
