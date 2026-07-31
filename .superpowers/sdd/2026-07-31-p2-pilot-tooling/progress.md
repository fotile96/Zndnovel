# SDD ledger — plan: docs/superpowers/plans/2026-07-31-p2-pilot-tooling.md
# 工作台：main 直提交（仓库 CLAUDE.md 规约「main 分支直提交」，用户已批准；本会话无并行写树）
# BASE(T1 前)=ea4e317
# spec: docs/superpowers/specs/2026-07-31-p2-pilot-design.md
# 规约提醒：本工作台下的 *.md 需 `git add -f` 入库携带（CLAUDE.md「SDD 工作台」节）
# pre-flight 扫描：计划自身一处措辞矛盾已修——Global Constraints 原写「纯标准库」，
#   与 Tech Stack「依赖仅 pillow/pyyaml/pytest」及 T5/T6/T7 实际用 yaml.safe_load 冲突，
#   照字面读会诱使实现者手写 YAML 解析；已改为「不得新增第三方依赖，可用既有 pyyaml」
