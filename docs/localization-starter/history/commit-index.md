# 逐 commit 证据索引

固定基线：`a3977b52ee20cda9291e8103b62b50030a62fb67`；共 1162 个 reachable commit，含 merge。

按反向拓扑顺序列出；日期为作者日期，不是投入工时。变更按父提交对比，merge 按第一父提交；A/M/D/R 为 Git 状态。

每项的‘做了什么’保留提交标题；规格/工装新增来自真实文件增量，完整路径状态见 commits.json。它不是逐 diff 语义审计。

查看细节：`git show <sha> -- <path>`。历史路径可能已迁移或删除。

## 0001 · a798fb0 · 2026-07-30

add png resources files and scripts

- 变更：2382 个路径；lua_scripts 229、png 2153
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0002 · 5de7e0d · 2026-07-30

feat: 剧本分析提取三件套脚本（DAG/文本摘要/卡片谜题）

- 变更：3 个路径；tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/extract_crd.py`、`tools/extract_dag.py`、`tools/extract_text.py`
- 相关实现/计划变更：A `tools/extract_crd.py`、A `tools/extract_dag.py`、A `tools/extract_text.py`

## 0003 · 67f1c49 · 2026-07-30

analysis: 首次生成提取产物归档

- 变更：231 个路径；analysis 231
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0004 · 039368d · 2026-07-30

docs: CLAUDE.md 全脚本通读知识库与开发规约

- 变更：1 个路径；CLAUDE.md 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0005 · 6d48dcc · 2026-07-30

chore: 建立 uv 项目环境（Python 3.14 + pillow）与 .gitignore

- 变更：4 个路径；.gitignore 1、.python-version 1、pyproject.toml 1、uv.lock 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0006 · 3f90a86 · 2026-07-30

docs: 翻译流水线核心设计 spec（单线时间轴/双后端/D3 数据层）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-07-30-translation-pipeline-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-07-30-translation-pipeline-design.md`

## 0007 · 633464d · 2026-07-30

docs: spec 增补 API-A 档 baseline 四档与 v1→v2 主路径定位

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-30-translation-pipeline-design.md`

## 0008 · 3149555 · 2026-07-30

docs: P0 骨架与 P1a 数据地基两份实施计划

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-07-30-p0-skeleton.md`、A `docs/superpowers/plans/2026-07-30-p1a-data-foundation.md`

## 0009 · e6f28ec · 2026-07-30

chore: 骨架目录脚手架与校验脚本（P0 T1）

- 变更：7 个路径；docs 1、pyproject.toml 1、skeleton 3、tools 1、uv.lock 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_skeleton.py`
- 相关实现/计划变更：M `docs/superpowers/plans/2026-07-30-p0-skeleton.md`、A `tools/check_skeleton.py`

## 0010 · b8f1b98 · 2026-07-30

data: 术语表 v1 与说话人映射（用户裁决：片假名保留/悠一/第二物语/咒语）

- 变更：4 个路径；glossary 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0011 · 52026b2 · 2026-07-30

data: 卡面转写 1-19 入库（P0 T3）

- 变更：3 个路径；docs 1、skeleton 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-07-30-p0-skeleton.md`、M `tools/check_skeleton.py`

## 0012 · a8000b8 · 2026-07-30

data: 卡面转写 20-39 入库（P0 T4）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0013 · e8b3c12 · 2026-07-30

data: 卡面转写 40-59 入库（P0 T5）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0014 · f600168 · 2026-07-30

data: 卡面转写 120-139 入库（P0 T9）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0015 · ffe5f4a · 2026-07-30

data: 卡面转写 160-179 入库（P0 T11）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0016 · 268d5a3 · 2026-07-30

data: 卡面转写 180-195+编外200 入库（P0 T12）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0017 · 5f87b68 · 2026-07-30

data: 卡面转写 100-119 入库（P0 T8）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0018 · 4d774ae · 2026-07-30

data: 卡面转写 80-99 入库（P0 T7，空格记法归一）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0019 · 53bd649 · 2026-07-30

data: 卡面转写 140-159 入库（P0 T10）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0020 · 167d4b4 · 2026-07-30

data: 卡面转写 60-79 入库（P0 T6，十批转写完成）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0021 · 4183214 · 2026-07-30

data: 卡面转写总表合并（197 条，plotTitle 全量零失配）（P0 T13）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0022 · 67724c8 · 2026-07-30

data: 术语表 v2 落地与下游同步

- 变更：5 个路径；glossary 4、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_skeleton.py`

## 0023 · 75cc5c3 · 2026-07-30

data: 中文卡组 1-39 入库（P0 T14，用户抽阅通过）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0024 · 74991a0 · 2026-07-30

feat: pipelib 共享底座与 pytest 脚手架

- 变更：5 个路径；pyproject.toml 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/__init__.py`、`tools/pipelib.py`
- 相关实现/计划变更：A `tools/__init__.py`、A `tools/pipelib.py`

## 0025 · fa5af0f · 2026-07-30

feat: ledger 解析核心（vms 行提取与函数归属）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/build_ledger.py`
- 相关实现/计划变更：A `tools/build_ledger.py`

## 0026 · d88c25d · 2026-07-30

feat: 章别推导与 ambient 规则表分类

- 变更：3 个路径；tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/ambient_rules.py`
- 相关实现/计划变更：A `tools/ambient_rules.py`、M `tools/build_ledger.py`

## 0027 · d6c8e62 · 2026-07-30

feat: ledger_extra 四类结构文本提取

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`

## 0028 · 8834a44 · 2026-07-30

fix: card_msg 正则改抓末位字符串参数；16750 计数勘误为 16749（实测两处动态 vms）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`

## 0029 · 3d1e5fb · 2026-07-30

data: 生成 ledger 原文账本与 extra 结构文本

- 变更：2 个路径；data 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0030 · 28c84d4 · 2026-07-30

feat: resolve 生效译文合并与 final 物化

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/resolve.py`
- 相关实现/计划变更：A `tools/resolve.py`

## 0031 · 09331ac · 2026-07-30

feat: check_batch 硬软规则校验与 pass 标记

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_batch.py`
- 相关实现/计划变更：A `tools/check_batch.py`

## 0032 · 15a689d · 2026-07-30

feat: append_forward 入库握手（pass标记/哈希/防重）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/append_forward.py`
- 相关实现/计划变更：A `tools/append_forward.py`

## 0033 · 8e99884 · 2026-07-30

feat: build_ledger --report ambient 审定报告

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`

## 0034 · 8028d9a · 2026-07-30

data: ambient 例外清单人工审定入账

- 变更：4 个路径；data 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ambient_rules.py`、M `tools/build_ledger.py`

## 0035 · dc2c292 · 2026-07-30

data: 术语表 v3（字条/笔记本/书名neta对齐形/手臂母题）

- 变更：3 个路径；CLAUDE.md 1、glossary 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0036 · d828f81 · 2026-07-30

data: 七份角色口调表定稿（P0 T19，四项称呼裁决落定）

- 变更：7 个路径；glossary 7
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0037 · fa960f9 · 2026-07-30

fix: naoya 口调表被称呼栏漏改的「直哉哥」统一为全期「直哉哥哥」

- 变更：1 个路径；glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0038 · faf5be6 · 2026-07-30

data: 术语表 v4（物語→故事、ナゾトキ→谜题）与口调表/风格同步

- 变更：10 个路径；glossary 10
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0039 · 788bce4 · 2026-07-30

data: 中文卡组五批全部入库（v4 召回修订+用户通读反馈）

- 变更：5 个路径；skeleton 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0040 · aeb8c6d · 2026-07-30

data: 中文卡组总表合并（196 条，全量校验 OK）（P0 T18 完成）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0041 · 290b713 · 2026-07-30

docs: P1b 线性化与上下文组装实施计划（附 work/ 入 gitignore）

- 变更：2 个路径；.gitignore 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-07-30-p1b-linearize-context.md`

## 0042 · fe3e028 · 2026-07-30

data: 术语表 v5（ハッピーエンド→Happy End 保留英文）

- 变更：2 个路径；glossary 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0043 · 30d2fef · 2026-07-30

feat: dag.json 结构化剧情图生成器

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/build_dag.py`
- 相关实现/计划变更：A `tools/build_dag.py`

## 0044 · 4fdff8f · 2026-07-30

fix: choice 事件仅追踪 comDlgSelectItem 变量并消费后清零

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_dag.py`

## 0045 · 81f42ef · 2026-07-30

feat: 时间轴展开器 story 步进核心

- 变更：3 个路径；config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/gen_timeline.py`
- 相关实现/计划变更：A `config/unit_funcs.yaml`、A `tools/gen_timeline.py`

## 0046 · 2dda37e · 2026-07-30

fix: ledger 函数归属改为嵌套栈追踪，vms 回归所属场景函数

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`

## 0047 · 6f04620 · 2026-07-30

docs: 修正 vms 静态调用计数 16750→16749（按源码 finditer 实测；ledger 全量核对无缺行）

- 变更：2 个路径；CLAUDE.md 1、analysis 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0048 · 0a03599 · 2026-07-30

fix: 移除死代码 ran、对齐 skip 契约与实现

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_timeline.py`

## 0049 · 2dbdd2a · 2026-07-30

feat: 展开器 sweep/replay/script/pool 与回溯标记

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_timeline.py`

## 0050 · f5f0f8c · 2026-07-30

chore: 补展开器语义回归测试（阻断/only 过滤/fscene 紧随/route 单写）

- 变更：1 个路径；tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0051 · c34a606 · 2026-07-30

chore: 修正 fscene 位置回归用例——runs 卡移出扫描序末位以判别批尾实现

- 变更：1 个路径；tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0052 · 63ce938 · 2026-07-30

data: anchors 伏笔锚点入库（120 条/19 组，用户整体润色定稿）

- 变更：1 个路径；skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0053 · 1e3849c · 2026-07-30

data: glossary v6（腕按语境/回家的歌谣/千秋高中期称呼直哉哥）+ 下游召回同步与润色尺度记

- 变更：7 个路径；CLAUDE.md 1、glossary 5、skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0054 · 45b93b9 · 2026-07-30

docs: skeleton-v1 冻结收尾——CLAUDE.md 骨架指针与目录、口调表版本头对齐 v6、anchors 裁决注记落定化

- 变更：7 个路径；CLAUDE.md 1、glossary 5、skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0055 · f5422c0 · 2026-07-30

chore: SDD 工作台持久工件入库（台账/简报/报告），评审包保持忽略

- 变更：11 个路径；.superpowers 10、CLAUDE.md 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0056 · 18efbd9 · 2026-07-30

feat: build_dag 增加 --check/--out-dir，dag.json 可非破坏性校验

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_dag.py`

## 0057 · c74920f · 2026-07-30

chore: Python 下限放宽至 >=3.12 并移除 .python-version 精确钉

- 变更：4 个路径；.python-version 1、CLAUDE.md 1、pyproject.toml 1、uv.lock 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0058 · 7e3831a · 2026-07-30

feat: 云端环境初始化脚本入库（两层：UI 薄引导 + 库内真逻辑）

- 变更：3 个路径；.claude 2、CLAUDE.md 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0059 · 2d59bed · 2026-07-30

manually add .claude/settings.json

- 变更：1 个路径；.claude 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0060 · b99f292 · 2026-07-30

docs: 云端环境首次验收记录入库

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0061 · 92a24d8 · 2026-07-30

fix: 云端脚本与规约按首次验收实测订正

- 变更：3 个路径；.claude 2、CLAUDE.md 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0062 · 105dafa · 2026-07-30

feat: 云端诊断补探插件载体（~/.claude/plugins）

- 变更：2 个路径；.claude 1、CLAUDE.md 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0063 · 3ff724a · 2026-07-30

docs: 云端验收记录补记 §七（ListPlugins 读数变化 + skill 直接调用实测）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0064 · 9780946 · 2026-07-30

feat: 云端补装 superpowers/mattpocock 插件，绕开 SKIP_PLUGIN_MARKETPLACE

- 变更：2 个路径；.claude 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0065 · 5eae683 · 2026-07-30

docs: 云端插件留存实测——不留存，根因为每会话快照冷启（§八.6–8）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0066 · b5b84b4 · 2026-07-30

feat: 云端现场取证固化进 setup 脚本，并定位 flag 的真实注入点（§九）

- 变更：2 个路径；.claude 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0067 · e030cf8 · 2026-07-30

docs: 云端插件根治成功实测入库（§十），订正 CLAUDE.md 两处过时结论

- 变更：3 个路径；.claude 1、CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0068 · 6dfccaf · 2026-07-31

feat: check_timeline 覆盖/crd/门控三组断言（P1b Task 4）

- 变更：4 个路径；.superpowers 1、config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_timeline.py`
- 相关实现/计划变更：A `config/gates.yaml`、A `tools/check_timeline.py`

## 0069 · c1117a5 · 2026-07-31

feat: gen_timeline 路线执行入口与 sceneId2aCard 解析（P1b Task 5 Step 1）

- 变更：4 个路径；.superpowers 1、config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/route_plan.yaml`、M `tools/gen_timeline.py`

## 0070 · cd86e2c · 2026-07-31

data: 全书正典路线与孤儿函数附挂表入库（P1b Task 5 Step 2）

- 变更：14 个路径；.superpowers 11、config 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/gates.yaml`、M `config/route_plan.yaml`、M `config/unit_funcs.yaml`

## 0071 · 7820985 · 2026-07-31

fix: 展开器与校验器的发卡口径统一，timeline 全局 id 去重（Hotfix B/C）

- 变更：7 个路径；data 1、tests 3、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_dag.py`、M `tools/check_timeline.py`、M `tools/gen_timeline.py`

## 0072 · df71266 · 2026-07-31

data: 全书 timeline 与 scene2card 入库（P1b Task 5 收尾）

- 变更：11 个路径；.superpowers 4、config 1、data 2、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/gates.yaml`、M `tools/check_timeline.py`、M `tools/gen_timeline.py`

## 0073 · 1e78a5e · 2026-07-31

data: 批次规划三车道生成并冻结（P1b Task 6）

- 变更：4 个路径；.superpowers 1、data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/gen_batches.py`
- 相关实现/计划变更：A `tools/gen_batches.py`

## 0074 · 39f95aa · 2026-07-31

feat: build_context 三 profile×四 baseline 组装（P1b Task 7）

- 变更：4 个路径；.superpowers 2、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/build_context.py`
- 相关实现/计划变更：A `tools/build_context.py`

## 0075 · b746a9d · 2026-07-31

feat: 翻译/评审/API 三份 prompt 模板（P1b Task 8）

- 变更：5 个路径；.superpowers 2、prompts 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `prompts/api_system.md`、A `prompts/reviewer_cc.md`、A `prompts/translator_cc.md`

## 0076 · 4642a3d · 2026-07-31

feat: gen_plan CC 批次计划生成器（P1b Task 9）

- 变更：5 个路径；.superpowers 3、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/gen_plan.py`
- 相关实现/计划变更：A `tools/gen_plan.py`

## 0077 · e8e8328 · 2026-07-31

feat: add_patch 与 recall 召回查询（P1b Task 10）

- 变更：5 个路径；.superpowers 2、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/add_patch.py`、`tools/recall.py`
- 相关实现/计划变更：A `tools/add_patch.py`、A `tools/recall.py`

## 0078 · ce2c7ef · 2026-07-31

test: 端到端 dry-run（context→假草稿→check_batch）（P1b Task 11）

- 变更：3 个路径；.superpowers 2、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0079 · 06173c0 · 2026-07-31

fix: 全分支评审修复轮（e2e hermetic、前缀渲染结构、resolve 混合 id）

- 变更：16 个路径；.superpowers 3、config 2、tests 6、tools 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/gates.yaml`、M `config/route_plan.yaml`、M `tools/build_context.py`、M `tools/check_timeline.py`、M `tools/gen_plan.py`、M `tools/pipelib.py`、M `tools/resolve.py`

## 0080 · dececb6 · 2026-07-31

feat: 前缀改用时间轴位置窗口，recall 按生效译文版本判断陈旧

- 变更：7 个路径；.superpowers 3、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_context.py`、M `tools/recall.py`

## 0081 · b03d6cc · 2026-07-31

fix: check_batch R2b 结构检查恒执行并支持装饰括号说话人，recall 净化 term 文件名（P1c 硬化）

- 变更：5 个路径；.superpowers 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_batch.py`、M `tools/recall.py`

## 0082 · c9eb140 · 2026-07-31

docs: P2 试点设计 spec（双模型独立双链对照，batch 1-35）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-07-31-p2-pilot-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0083 · 5f23a6d · 2026-07-31

docs: P2 spec 补实 append_forward 参数来源，消除最后一处占位符

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0084 · af8ffe1 · 2026-07-31

docs: P2 spec 补子代理隔离纪律与译者模板路径基准节

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0085 · cad484d · 2026-07-31

docs: P2 spec 修正 §6.1 标题与内容不一致（三层→两层+单元级校验）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0086 · 9304da5 · 2026-07-31

docs: P2 spec 消除陷阱表对 §6 分层的过时指代

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0087 · ffff527 · 2026-07-31

docs: P2 spec 补 §4.4——译者拿不到角色口调表的缺口与修法

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0088 · ea4e317 · 2026-07-31

docs: P2 试点工装实施计划（8 任务，含口调表内嵌）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-07-31-p2-pilot-tooling.md`

## 0089 · b2d05d6 · 2026-07-31

docs: P2 计划 pre-flight 修正——依赖约束措辞（纯标准库→不新增第三方依赖，可用既有 pyyaml）

- 变更：2 个路径；.superpowers 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-07-31-p2-pilot-tooling.md`

## 0090 · 3fcc6b6 · 2026-07-31

feat: build_context 暴露 --repo，支持车道隔离调用

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_context.py`

## 0091 · 06ce37d · 2026-07-31

feat: context 内嵌角色口调表并压缩锚点节为 id/jp/zh

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_context.py`

## 0092 · 16d75e2 · 2026-07-31

feat: gen_plan 选批渲染分离，新增连续段模式与车道感知

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0093 · e2ac88b · 2026-07-31

fix: 连续段计划的章别文案与批号复核口径，补车道模式路径断言

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0094 · 3d7d7a2 · 2026-07-31

docs: 译者模板新增路径基准节与试点隔离纪律

- 变更：1 个路径；prompts 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `prompts/translator_cc.md`

## 0095 · ba1028f · 2026-07-31

docs: 补全译者模板路径基准的只读数据文件归属

- 变更：1 个路径；prompts 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `prompts/translator_cc.md`

## 0096 · 3d5f789 · 2026-07-31

feat: 车道搭建与冻结校验工具

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/lane_setup.py`
- 相关实现/计划变更：A `tools/lane_setup.py`

## 0097 · bd6b1a9 · 2026-07-31

docs: 修正 P2 计划 Task 5 的测试计数笔误（8→7，接口覆盖本就完整）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-07-31-p2-pilot-tooling.md`

## 0098 · 9bc037d · 2026-07-31

fix: verify 对车道损坏与冻结文件缺失改为可诊断漂移而非栈回溯

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/lane_setup.py`

## 0099 · 1c91c02 · 2026-07-31

test: 补双车道用例钉住 verify 不因单条损坏中断校验

- 变更：1 个路径；tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0100 · 8a73b45 · 2026-07-31

feat: 语义崩溃探测（残留假名/长度比离群/复读循环）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/detect_collapse.py`
- 相关实现/计划变更：A `tools/detect_collapse.py`

## 0101 · 7dc2a94 · 2026-07-31

fix: 复读探测单元下限取 4 字符，避开中文合法情绪重复

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/detect_collapse.py`

## 0102 · 909185b · 2026-07-31

feat: 双车道分层统计与盲评对照材料生成

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/compare_lanes.py`
- 相关实现/计划变更：A `tools/compare_lanes.py`

## 0103 · f6a0a05 · 2026-07-31

docs: 修正 P2 计划 Task 7 接口表的 anchor_ids 返回类型（set→dict）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-07-31-p2-pilot-tooling.md`

## 0104 · b3f612b · 2026-07-31

data: 生成 P2 试点两条车道的逐批执行计划（batch 1-35）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-pilot-fable.md`、A `docs/superpowers/plans/translate-pilot-opus.md`

## 0105 · 2a449dc · 2026-07-31

fix: 终任务按真实章别表述，check_batch 支持 --lane-dir 读车道术语快照

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_batch.py`、M `tools/gen_plan.py`

## 0106 · cab0497 · 2026-07-31

data: 按修复后的生成器重出两份 P2 试点执行计划

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-pilot-fable.md`、M `docs/superpowers/plans/translate-pilot-opus.md`

## 0107 · b124450 · 2026-07-31

docs: 入库 Hotfix D 简报与报告（SDD 证据）

- 变更：2 个路径；.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0108 · 3c73c86 · 2026-07-31

docs: P2 工装台账收尾（8 任务 + Hotfix D 全部完成）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0109 · 70cdef6 · 2026-07-31

fix: 试点执行计划补齐四道验收闸门与安全网假防护修复

- 变更：6 个路径；tests 3、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/compare_lanes.py`、M `tools/gen_plan.py`、M `tools/lane_setup.py`

## 0110 · daae5e6 · 2026-07-31

fix: 车道根迁出 work/，改 pilot/lanes/ 以让译文线可入库

- 变更：4 个路径；.gitignore 1、pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0111 · e29cdc8 · 2026-07-31

data: 重出两份试点执行计划（四道闸门 + pilot/lanes 路径）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-pilot-fable.md`、M `docs/superpowers/plans/translate-pilot-opus.md`

## 0112 · 03a7af9 · 2026-07-31

docs: 译者模板同步车道根迁移、check_batch 车道参数与第四节改名

- 变更：1 个路径；prompts 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `prompts/translator_cc.md`

## 0113 · 82efd69 · 2026-07-31

docs: 终审修复波执行报告入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0114 · cba6645 · 2026-07-31

docs: P2 spec 同步车道根迁移（work/lanes → pilot/lanes）并记录 C2 裁决理由

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-07-31-p2-pilot-design.md`

## 0115 · a4adef2 · 2026-07-31

fix: gitignore 放行车道 data/notes（spec §8 术语提案清单产出物）

- 变更：3 个路径；.gitignore 1、.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0116 · 407e879 · 2026-07-31

fix: record() 跳过纯克隆里尚未重建的车道而非崩溃

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/lane_setup.py`

## 0117 · de4f2f2 · 2026-07-31

docs: hotfix-e 车道纯克隆崩溃修复执行报告入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0118 · 029795a · 2026-07-31

chore: cloud-setup 探测未搭建的试点车道并给出重建命令

- 变更：1 个路径；.claude 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0119 · 441c91f · 2026-08-01

chore: P2 试点车道在本机重建（lane_dir 指向本机路径）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0120 · 5b638e3 · 2026-07-31

chore: P2 试点 opus 车道开跑（云端重建两条车道 + 执行台账）

- 变更：3 个路径；.superpowers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0121 · 8b41790 · 2026-07-31

data: s0f 批次1 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0122 · fdedf11 · 2026-07-31

docs: 试点台账记入 batch 1 结果与两条流水线缺陷

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0123 · 2591abc · 2026-07-31

docs: 台账回填 batch1 sha 并记录签名假阳性排查结论

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0124 · 21ac9e1 · 2026-07-31

data: fable 车道 batch 1 入线（spec §3.3 隔离验收对照组）

- 变更：3 个路径；.superpowers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0125 · 615b0ef · 2026-07-31

data: s0f 批次2 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0126 · da9d2cc · 2026-07-31

docs: Task 4 硬停——崩溃阈值按 568 行真实译文标定，维持默认值

- 变更：2 个路径；.superpowers 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0127 · 290d383 · 2026-07-31

data: crd 批次3 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0128 · b4b06b9 · 2026-07-31

docs: 台账记入 batch 3

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0129 · 77c94e3 · 2026-07-31

data: s1s 批次4 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0130 · ee56282 · 2026-07-31

docs: 台账记入 batch 4（双层人名机器复核通过）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0131 · 7ae7099 · 2026-07-31

data: sys 批次5 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0132 · 48ed2d1 · 2026-07-31

docs: 台账记入 batch 5 与批次 1-5 检查点（28 条提案留档未裁决）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0133 · d6d2b34 · 2026-07-31

data: crd 批次6 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0134 · 2060285 · 2026-07-31

docs: 台账记入 batch 6，新增 F6（anchors 与 voices 例句系统性冲突）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0135 · 79cb0b8 · 2026-07-31

data: s1s 批次7 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0136 · 971c802 · 2026-07-31

docs: 台账记入 batch 7，新增 F7（单元内 id 序非脚本行序，后补行错位）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0137 · 3bda3eb · 2026-07-31

data: s1s 批次8 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0138 · b8b1a62 · 2026-07-31

docs: 台账记入 batch 8——跨批复现句一致性全量复核 100%

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0139 · 3e2738b · 2026-07-31

data: s1s 批次9 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0140 · 0bb7318 · 2026-07-31

docs: 台账记入 batch 9

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0141 · 0f23ba5 · 2026-07-31

data: crd 批次10 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0142 · 1cde92f · 2026-07-31

docs: 台账记入 batch 10 与批次 6-10 检查点，新增 F8（W2 词性盲区）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0143 · 78fce66 · 2026-07-31

data: s1s 批次11 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0144 · 10c0286 · 2026-07-31

docs: 台账记入 batch 11，新增 F9（C1 白名单漏作品内引用的日文原文）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0145 · 127f73c · 2026-07-31

data: crd 批次12 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0146 · 442aa44 · 2026-07-31

docs: 台账记入 batch 12，新增「译者自述可信度」方法论观察

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0147 · 672c638 · 2026-07-31

data: s1s 批次13 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0148 · d8e4c76 · 2026-07-31

docs: 台账记入 batch 13（自评语域摇摆经复核为忠实复现原文）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0149 · 14ffb94 · 2026-07-31

data: crd 批次14 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0150 · 3feffe0 · 2026-07-31

docs: 台账记入 batch 14（同名诡计关键句 716 对照锚点 1841 复核通过）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0151 · 4a1de1d · 2026-07-31

data: s1s 批次15 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0152 · 9cdbf34 · 2026-07-31

docs: 台账记入 batch 15 与批次 11-15 检查点

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0153 · 747dc26 · 2026-07-31

data: crd 批次16 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0154 · d12b981 · 2026-07-31

docs: 台账记入 batch 16——お話/物語 合并规则的实证反例（847-852 双关段）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0155 · 0f504d1 · 2026-07-31

data: s1s 批次17 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0156 · 4fcedc3 · 2026-07-31

docs: 台账记入 batch 17（8144 汉字名闯入故事层，实测 342:2）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0157 · d5b3ae0 · 2026-07-31

data: sys 批次18 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0158 · 3f6105a · 2026-07-31

docs: 台账记入 batch 18——该批 30 行疑为不可达内容（函数零调用点）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0159 · 8c942e8 · 2026-07-31

data: s1s 批次19 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0160 · 9b2848a · 2026-07-31

docs: 台账记入 batch 19（17 条 collapse 全部误报，C1 单批超此前总和）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0161 · d7b1686 · 2026-07-31

data: crd 批次20 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0162 · 7b001d6 · 2026-07-31

docs: 台账记入 batch 20 与批次 16-20 检查点，归拢「补引号」待裁决项

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0163 · f205df6 · 2026-07-31

data: s1s 批次21 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0164 · 91a171d · 2026-07-31

docs: 台账记入 batch 21 及内容层重大发现（サクラ 汉字呼名的作者级装置）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0165 · 37726ef · 2026-07-31

data: s1s 批次22 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0166 · 10cd9d5 · 2026-07-31

docs: 台账记入 batch 22（W3 第二次起正面作用，F5 表述需修正）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0167 · f19c3ce · 2026-07-31

data: s1s 批次23 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0168 · eb7977d · 2026-07-31

docs: 台账记入 batch 23（书写系统层损失应在报告中单列）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0169 · de339fa · 2026-07-31

data: crd 批次24 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0170 · 6929d63 · 2026-07-31

docs: 台账记入 batch 24

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0171 · 95bc018 · 2026-07-31

data: s1s 批次25 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0172 · 533d2a5 · 2026-07-31

docs: 台账记入 batch 25 与批次 21-25 检查点（首个同 jp 异 zh 经查为正确消歧）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0173 · 58d5e47 · 2026-07-31

data: s1s 批次26 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0174 · db95155 · 2026-07-31

docs: 台账记入 batch 26，新增 F10（锚点表对母题句族覆盖不全 3/12）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0175 · f4b12be · 2026-07-31

data: crd 批次27 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0176 · 1a7692c · 2026-07-31

docs: 台账记入 batch 27（F8 词性盲区第三次复现）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0177 · 897ea5a · 2026-07-31

data: crd 批次28 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0178 · 2cab722 · 2026-07-31

docs: 台账记入 batch 28，新增待裁决项 3（数字跟随原文 vs 同物同名）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0179 · 46be8d2 · 2026-07-31

data: s1f 批次29 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0180 · 5d600a1 · 2026-07-31

docs: 台账记入 batch 29（6853 补回溯叙述读法，佐证「不修复原作」规则）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0181 · d0d624f · 2026-07-31

data: s1f 批次30 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0182 · e8a2acb · 2026-07-31

docs: 台账记入 batch 30 与检查点，新增 F11/F12 与「距离-漂移」量化发现

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0183 · 3ddff7e · 2026-07-31

data: s1f 批次31 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0184 · cd043de · 2026-07-31

docs: 台账记入 batch 31——F12 严重度实证上调（系统说明批 67% 行误报）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0185 · 8010ff4 · 2026-07-31

data: crd 批次32 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0186 · 3a5280d · 2026-07-31

docs: 台账记入 batch 32 与压缩窗口跃迁实测（383371 → 108560，降至 28%）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0187 · 431a0d8 · 2026-07-31

data: s2s 批次33 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0188 · 4a507c7 · 2026-07-31

docs: 台账记入 batch 33 与压缩边界一致性实测（13/15 一致）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0189 · 01190b7 · 2026-08-01

docs: 记录容器回收事件与全量恢复（译文零损失）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0190 · 7de74e2 · 2026-08-01

chore: pilot-manifest 归一为 lane_setup 的写入格式（纯格式，语义不变）

- 变更：2 个路径；.superpowers 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0191 · d35adbf · 2026-08-01

data: crd 批次34 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0192 · e7d4c2f · 2026-08-01

docs: 台账记入 batch 34；修正「同批内零分歧」的适用粒度

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0193 · ce25d79 · 2026-08-01

data: s2s 批次35 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0194 · 8d7c695 · 2026-08-01

docs: 台账记入 batch 35 与 Task 44 检查点——全 35 批完成

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0195 · 0cb3947 · 2026-08-01

docs: Task 45 窗口对撞探针结论——未测出窗口效应，但探针功效有限

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0196 · 8cad4a8 · 2026-08-01

docs: P2 试点执行报告（opus 车道 35 批）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0197 · 91b1021 · 2026-08-01

docs: Task 46 本地续做的交接提示词

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0198 · 918aa7b · 2026-08-01

Merge branch 'claude/second-novel-p2-pilot-u7mf7n' into main

- 变更：13 个路径；.superpowers 2、docs 1、pilot 10
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0199 · c9d6e01 · 2026-08-02

data: 术语表 v7 裁决与召回令（P2 试点收尾，术语层解冻）

- 变更：5 个路径；glossary 3、pilot 1、skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0200 · c9872e1 · 2026-08-02

docs: P2 试点 Task 46 收尾评审记录（Step 1 补做 + Step 2 放行，计划完结）

- 变更：2 个路径；.superpowers 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0201 · 1e0c053 · 2026-08-02

docs: P3 方针 spec——opus 侦察全量 + 检查点裁决 + 并行开发

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-08-02-p3-fullrun-policy-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-08-02-p3-fullrun-policy-design.md`

## 0202 · 226e87f · 2026-08-02

docs: P3 点火实施计划（7 任务：段表/饱和度/canary/段模式/v7 再冻结/worktree/首段计划）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-08-02-p3-ignition.md`

## 0203 · 49d85a3 · 2026-08-02

feat: P3 检查段切分表（8 段覆盖 b36-339，测试锁定）

- 变更：2 个路径；config 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/segments.yaml`

## 0204 · 5480681 · 2026-08-02

feat: 词族饱和度计算器（段末裁决证据闸门）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/saturation.py`
- 相关实现/计划变更：A `tools/saturation.py`

## 0205 · e4e8378 · 2026-08-02

feat: canary 陷阱批回验（工具升级回归闸）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/canary.py`
- 相关实现/计划变更：A `tools/canary.py`

## 0206 · 58cc5df · 2026-08-02

feat: gen_plan 段模式——生产计划内嵌段开场自检与段末流程

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0207 · a4fb603 · 2026-08-02

chore: 车道再冻结至 glossary v7（P3 首次段边界版本切换）

- 变更：2 个路径；.superpowers 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0208 · fc0e284 · 2026-08-02

docs: P3 生产运行手册（并行纪律/自检/canary 升级闸/裁决清单）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/ops/p3-production-runbook.md`
- 新增工装入口/模块：无

## 0209 · e8ef830 · 2026-08-02

docs: SEG-1（s2 完结段，b36-62）生产计划

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg1-s2.md`

## 0210 · 1fd107c · 2026-08-02

fix: 段模式不再生成 P2 试点专属的硬停任务

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0211 · 9725864 · 2026-08-02

docs: SEG-1 生产计划重生成（修复后不再含试点硬停任务）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-seg1-s2.md`

## 0212 · 7fb7598 · 2026-08-02

fix: 生产/开发并行的命令形态划分 + saturation 失败开 + 段模式措辞

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`、M `tools/saturation.py`

## 0213 · 0e949b3 · 2026-08-02

fix: 检查段切分表拆出 ambient 段并补齐 chapters

- 变更：2 个路径；config 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/segments.yaml`

## 0214 · bac9f3f · 2026-08-02

docs: runbook 树/cwd 划分与 canary 覆盖边界；P2 报告崩溃命中数订正为 45

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0215 · c786945 · 2026-08-02

fix: 段模式崩溃探测步不再引用不存在的硬停任务

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0216 · 266829b · 2026-08-02

docs: SEG-1 生产计划重生成（四件套带生产树前缀、段语汇、批号由段表读出）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-seg1-s2.md`

## 0217 · 0aaee66 · 2026-08-02

docs: canary 免跑判定留痕补全 saturation（prod-run-v2 已打并切至生产树）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0218 · b3f3aea · 2026-08-02

docs: P3 点火 SDD 执行证据入库（台账/brief/report）

- 变更：16 个路径；.superpowers 16
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0219 · e014dd4 · 2026-08-02

docs: P3 生产会话交接提示词

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0220 · fd81aca · 2026-08-02

docs: P3 开发轨第一波实施计划（8 任务：预聚类/降噪/F7/gen_plan 收口/补锁/API/彩野测试/题库）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-08-02-p3-devwave1.md`

## 0221 · 30c234a · 2026-08-02

feat: 提案预聚类卷宗生成器（段末裁决输入整理）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/cluster_notes.py`
- 相关实现/计划变更：A `tools/cluster_notes.py`

## 0222 · cab3d46 · 2026-08-02

data: s2s 批次36 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0223 · 6d91aec · 2026-08-02

docs: P3 seg1-s2 段台账建立（开场自检 + 批36 记录与派发 bug 留痕）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0224 · e4b7468 · 2026-08-02

fix: 多箭头标题不再产出乱码词键（归入未归词待人工过目）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/cluster_notes.py`

## 0225 · 1d64054 · 2026-08-02

data: s2s 批次37 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0226 · 225f7e9 · 2026-08-02

fix: detect_collapse 降噪——假名标点剔除/引用豁免/C3 阈值开关（F12/F9/F4）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/detect_collapse.py`

## 0227 · 51a3dfa · 2026-08-02

data: crd 批次38 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0228 · 567a323 · 2026-08-02

fix: F9 豁免加预算 gate（修复近似复制漏报）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/detect_collapse.py`

## 0229 · f27897f · 2026-08-02

data: s2s 批次39 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0230 · b285048 · 2026-08-02

fix: ledger 增记 lua 行号 line 字段（F7 前半，全局序不变）

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`

## 0231 · 42472c3 · 2026-08-02

fix: timeline 单元内按 (file,line) 行序（F7 后半，数据再生留段边界）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_timeline.py`

## 0232 · 3d00563 · 2026-08-02

docs: runbook §4 补段边界数据再生成条目（F7 timeline 行序）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0233 · 3e9eb62 · 2026-08-02

docs: P3 devwave1 task-3 执行报告入库（F7 行序）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0234 · 0b11f1b · 2026-08-02

data: s2s 批次40 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0235 · bff5588 · 2026-08-02

docs: P3 seg1-s2 台账更新（批37-40 + CHECKPOINT-1 批36-40）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0236 · 9e3fd63 · 2026-08-02

docs: F7 覆盖面残留说明与逆序口径订正

- 变更：4 个路径；.superpowers 1、docs 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`、M `tools/gen_timeline.py`

## 0237 · ae45ff9 · 2026-08-02

data: s2s 批次41 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0238 · 0d8e6bf · 2026-08-02

fix: 段模式强制 --tools-root 并由段表推导/校验 lane（点火终审 parked 两项）

- 变更：4 个路径；config 1、tests 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/segments.yaml`、M `tools/gen_plan.py`

## 0239 · 5cce3a5 · 2026-08-02

docs: P3 devwave1 task-4 执行报告入库（段模式收口）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0240 · 7599beb · 2026-08-02

data: crd 批次42 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0241 · a22a9a5 · 2026-08-02

chore: 点火遗留测试补锁三条 + canary 头注措辞订正

- 变更：4 个路径；tests 3、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/canary.py`

## 0242 · 39f4d89 · 2026-08-02

data: s2s 批次43 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0243 · db8d44f · 2026-08-02

feat: API 薄客户端（deepseek/stdlib/可注入 transport/计费台账）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/api_client.py`
- 相关实现/计划变更：A `tools/api_client.py`

## 0244 · e1640e0 · 2026-08-02

data: crd 批次44 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0245 · 6753bef · 2026-08-02

feat: 彩野测试 harness（卡组梗概前缀+段译文/读者-判分双调用/dry-run）

- 变更：3 个路径；docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/ayano_test.py`
- 相关实现/计划变更：A `tools/ayano_test.py`

## 0246 · 36b6cd6 · 2026-08-02

data: s2s 批次45 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0247 · 38e59c4 · 2026-08-02

docs: P3 seg1-s2 台账更新（批41-45 + CHECKPOINT-2）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0248 · 37c2762 · 2026-08-02

fix: 彩野测试反剧透闸——卡组前缀只取严格早于当前段的卡

- 变更：4 个路径；config 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/card_chapter.yaml`、M `tools/ayano_test.py`

## 0249 · 30cf02d · 2026-08-02

data: s2s 批次46 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0250 · f65dd45 · 2026-08-02

fix: 彩野测试补数据闸与 fallback 安全方向 + plan 勘误

- 变更：4 个路径；config 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/card_chapter.yaml`、M `docs/superpowers/plans/2026-08-02-p3-devwave1.md`、M `tools/ayano_test.py`

## 0251 · a7c2e9d · 2026-08-02

data: s2s 批次47 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0252 · 59bdbc2 · 2026-08-02

data: crd 批次48 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0253 · a4e2317 · 2026-08-02

data: s2s 批次49 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0254 · 691362e · 2026-08-02

data: s2s 批次50 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0255 · 6c38a21 · 2026-08-02

data: crd 批次51 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0256 · fa2b4e7 · 2026-08-02

docs: P3 seg1-s2 台账更新（批46-51 逐批记录与一致性债结清）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0257 · 66ef9e1 · 2026-08-02

data: s2s 批次52 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0258 · 37bbfbf · 2026-08-02

data: crd 批次53 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0259 · 0ade928 · 2026-08-02

data: s2s 批次54 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0260 · 1637cb2 · 2026-08-02

data: crd 批次55 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0261 · 2170c53 · 2026-08-02

docs: P3 seg1-s2 台账更新（批52-55 + CHECKPOINT-3/4）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0262 · ffed0a0 · 2026-08-02

data: 彩野测试 SEG-1 题库（15 题，用户抽核通过）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg1-s2.yaml`

## 0263 · 668f256 · 2026-08-02

data: s2s 批次56 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0264 · 33d4a54 · 2026-08-02

feat: api_client 超时/重试可配置化 + ayano_test 模型透传

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`、M `tools/ayano_test.py`

## 0265 · 25d57f9 · 2026-08-02

data: 彩野测试 seg1-s2 题库修评审 I2/M1（q13 题面 + info_point 译况标注）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`

## 0266 · 3eb153c · 2026-08-02

chore: deepseek 连通冒烟 + 彩野测试端到端小样计费台账

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0267 · f0f8746 · 2026-08-02

docs: Task 9 执行报告（api_client 重试/超时、ayano_test 模型透传、题库修评审、deepseek 冒烟）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0268 · bbf7ff1 · 2026-08-02

data: crd 批次57 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0269 · 55c9bda · 2026-08-02

feat: api_client 换 deepseek Responses API 流式调用（CoT 可看 + 抗超时）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`

## 0270 · 9534179 · 2026-08-02

feat: ayano_test 报告写入受试者 CoT 摘要 + --effort 透传

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ayano_test.py`

## 0271 · 41762f7 · 2026-08-02

chore: Responses 流式改造实测台账入库 + task-10 报告

- 变更：2 个路径；.superpowers 1、data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0272 · da602a3 · 2026-08-02

data: s2f 批次58 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0273 · a7db79b · 2026-08-02

fix: api_client 修复评两条 Important（部分记账门槛 / 多 part 拼接）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`

## 0274 · 955f666 · 2026-08-02

feat: ayano_test 机械分诊标记（可复现的「照抄未理解」信号）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ayano_test.py`

## 0275 · 49cc0ae · 2026-08-02

data: s2f 批次59 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0276 · 55d9846 · 2026-08-02

data: s2s 批次60 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0277 · e48a60d · 2026-08-02

fix: cluster_notes 词键提取与卷宗护栏（终审 C1/I5/I7）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/cluster_notes.py`

## 0278 · 8093a13 · 2026-08-02

data: s2s 批次61 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0279 · cd977ab · 2026-08-02

fix: 段末流程收口——彩野测试进计划、--batches 不再覆盖段表（终审 I3/I6/M2/M8）

- 变更：5 个路径；docs 3、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-08-02-p3-devwave1.md`、M `tools/gen_plan.py`

## 0280 · 935b4ff · 2026-08-02

fix: 彩野题库绑定段 + 判分格式契约放宽（终审 I4/M3）

- 变更：3 个路径；config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`、M `tools/ayano_test.py`

## 0281 · fa2dcaa · 2026-08-02

docs: detect_collapse F9 召回净损写进 runbook §4.0 + 缺口测试固化（终审 I2）

- 变更：2 个路径；docs 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0282 · c28680a · 2026-08-02

feat: api_ledger 脏值安全汇总入口 ledger_token/summarize_ledger（终审 M7）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`

## 0283 · f588925 · 2026-08-02

docs: 标注在产计划 seg1-s2 的段末清单编号例外（I3 收尾）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0284 · f14bd8b · 2026-08-02

docs: P3 开发轨第一波终审修正波报告与台账入库

- 变更：2 个路径；.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0285 · a1beadc · 2026-08-02

data: crd 批次62 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0286 · 456e598 · 2026-08-02

docs: P3 seg1-s2 台账收尾（批56-62 + 段末机检复核与裁决清单）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0287 · 1bf098e · 2026-08-02

docs: P3 开发轨第一波 SDD 执行证据入库（台账/brief/report）

- 变更：15 个路径；.superpowers 15
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0288 · a6242b6 · 2026-08-02

fix: 清掉三条终审后 parked 的 Minor（恒绿/静默失效收尾）

- 变更：6 个路径；.superpowers 1、docs 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ayano_test.py`、M `tools/cluster_notes.py`

## 0289 · 3720ebb · 2026-08-02

fix: 复评修正波——同步 _segment_tail 文案 + 收窄 P1 短路的 ASCII 硬门

- 变更：6 个路径；.superpowers 2、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/cluster_notes.py`、M `tools/gen_plan.py`

## 0290 · 39a4a95 · 2026-08-02

docs: P3 开发轨第一波收尾证据入库（parked 清理与复评留痕）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0291 · 223f728 · 2026-08-02

fix: saturation.py 补齐脏键判据，与 cluster_notes 共用同一判据

- 变更：6 个路径；.superpowers 1、docs 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/cluster_notes.py`、M `tools/saturation.py`

## 0292 · 21ea489 · 2026-08-02

docs: P3 seg1-s2 人工评审通过留痕（裏技 裁定回改、プール 段列 tr_note 候选）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0293 · b34827f · 2026-08-02

fix: saturation.py 增补并列词串探测，堵住斜杠巧合漏洞

- 变更：4 个路径；.superpowers 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/saturation.py`

## 0294 · ada1d5d · 2026-08-02

fix: 并列词串探测测试改用合成 fixture，脱钩持续增长的生产译文

- 变更：3 个路径；.superpowers 1、docs 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0295 · 0207c3b · 2026-08-02

docs: P3 开发轨第一波 saturation 脏键门收尾证据入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0296 · 4b06979 · 2026-08-02

feat: glossary v8 —— P3 seg1-s2 段末小裁决与召回令

- 变更：8 个路径；glossary 5、skeleton 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0297 · e84ad0b · 2026-08-02

data: opus 车道 4 条召回回改（glossary_v=8）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0298 · f0ed4c5 · 2026-08-02

docs: seg1-s2 段末裁决台账入库 + 双车道版本切换到 glossary v8

- 变更：3 个路径；.superpowers 2、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0299 · 18cc77c · 2026-08-02

docs: F9 召回取舍的用户签字留痕（接受现状，只留痕不加闸）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0300 · bb65909 · 2026-08-02

data: 段边界再生 timeline.jsonl（F7 单元内行序修正）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0301 · 6ad593f · 2026-08-02

docs: 段边界升级判定记录 + 当前生产 tag 切到 prod-run-v3

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0302 · 5ac043a · 2026-08-02

docs: 段边界 prod-run-v3 升级执行证据入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0303 · 2d72215 · 2026-08-02

fix: gen_timeline/check_timeline 加 argparse，未知参数不再被静默忽略

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_timeline.py`、M `tools/gen_timeline.py`

## 0304 · 4938d47 · 2026-08-02

docs: runbook 补 gen_timeline 写入风险 + 评审修正轮三条 Minor

- 变更：2 个路径；.superpowers 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0305 · 89aed34 · 2026-08-02

data: 彩野测试首次全跑（SEG-1，15 题）报告与计费台账

- 变更：3 个路径；.superpowers 2、data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0306 · cd4f4ce · 2026-08-02

chore: DeepSeek 调用默认档位改为 effort=max、max_output_tokens=256K

- 变更：4 个路径；.superpowers 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`

## 0307 · c0f8061 · 2026-08-02

chore: max_output_tokens 上限与 effort=max 代价的实测台账行

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0308 · 5bcf7eb · 2026-08-02

docs: 订正 runbook 里失实的 uv 排障说明（--help 实为 rc=0）

- 变更：2 个路径；.superpowers 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0309 · d86c9c0 · 2026-08-02

docs: SEG-2（seg2-s3，b63-90）生产计划与交接提示词

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg2-s3.md`

## 0310 · 5421859 · 2026-08-02

fix: 彩野测试机械分诊标记降级为纯测量遥测

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ayano_test.py`

## 0311 · 6810857 · 2026-08-02

data: s3s 批次63 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0312 · fa202b1 · 2026-08-02

fix: C3 复读检测改为以原文重复程度为基线（F4 重做）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/detect_collapse.py`

## 0313 · 021ddd6 · 2026-08-02

data: s3s 批次64 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0314 · 564c4b1 · 2026-08-02

data: s3s 批次65 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0315 · 954a7d9 · 2026-08-02

fix: _max_repeat_run 加扫描窗口硬上限（C3 评审必修一）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/detect_collapse.py`

## 0316 · 83d607c · 2026-08-02

docs: 订正两处「真阳性 0 条」为按规则分列（C3 重做后据实，裁决维持）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0317 · d8adbdf · 2026-08-02

data: s3s 批次66 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0318 · e6c0055 · 2026-08-02

docs: C3 判据重做与分诊标记降级的执行证据入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0319 · a4f6395 · 2026-08-02

test: card_chapter.yaml 全量交叉校验（补 8 卡硬编码之外的 188 条守护）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/verify_card_chapter.py`
- 相关实现/计划变更：A `tools/verify_card_chapter.py`

## 0320 · 33e6127 · 2026-08-02

data: crd 批次67 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0321 · 4bf7021 · 2026-08-02

docs: card_chapter 交叉校验证据入库 + devwave1 完结留痕

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0322 · 3dea2b0 · 2026-08-02

docs: P3 seg2-s3 台账建立（开场自检 + 批63-67 + patches 覆盖层前瞻登记）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0323 · c7a32a2 · 2026-08-02

data: s3s 批次68 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0324 · d1bdd3a · 2026-08-02

data: s3s 批次69 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0325 · 6c8b178 · 2026-08-02

data: s3s 批次70 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0326 · 573e22c · 2026-08-02

docs: DeepSeek 审计能力 spec（自建最小 agent loop，固定流程优先）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-08-02-deepseek-audit-capability-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-08-02-deepseek-audit-capability-design.md`

## 0327 · 96ca011 · 2026-08-02

docs: DeepSeek 审计能力实施计划（6 任务）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-08-02-deepseek-audit-capability.md`

## 0328 · 4884958 · 2026-08-02

feat: 领域只读工具层（四工具 + 注册表 + CLI 面）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/agent_tools.py`
- 相关实现/计划变更：A `tools/agent_tools.py`

## 0329 · 22944ae · 2026-08-02

data: crd 批次71 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0330 · 5ecefcb · 2026-08-02

feat: api_client 支持白名单内的 function tools（守卫收紧非删除）

- 变更：7 个路径；.superpowers 5、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`

## 0331 · 235d9ca · 2026-08-02

feat: 有界工具循环（只读工具面 + 到顶不静默）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/agent_loop.py`
- 相关实现/计划变更：A `tools/agent_loop.py`

## 0332 · 81be5f0 · 2026-08-02

fix: 只读断言黑名单补齐 + web_search 串级闸升级为运行时不变量

- 变更：5 个路径；.superpowers 2、tests 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/api_client.py`

## 0333 · a215d32 · 2026-08-02

data: s3s 批次72 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0334 · 42a5c65 · 2026-08-02

chore: agent_loop 冒烟的计费台账行（get_anchor 工具调用两轮）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0335 · 7c2c710 · 2026-08-02

data: crd 批次73 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0336 · 27b4d75 · 2026-08-02

docs: P3 seg2-s3 台账更新（批68-73 + CHECKPOINT-1 + カイダン 双关裁定项）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0337 · ccf8b4d · 2026-08-02

fix: 截断轮次不再静默为 finished + 工具执行失败可计数 + token 哨兵不再毒化合计

- 变更：7 个路径；.superpowers 2、tests 3、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/agent_loop.py`、M `tools/api_client.py`

## 0338 · 5e38fb0 · 2026-08-02

feat: 手记审计步骤 1——硬承诺抽取（软倾向不审）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/audit_notes_promises.py`
- 相关实现/计划变更：A `tools/audit_notes_promises.py`

## 0339 · 0866a1d · 2026-08-02

docs: 手记审计步骤 1 执行证据入库（task-4-report）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0340 · 6709818 · 2026-08-02

data: s3s 批次74 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0341 · 1e55211 · 2026-08-02

fix: DS-T4 手记承诺抽取修复解析失败恒绿、跨子句 id 污染与 prewire 边角

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0342 · 5068f4b · 2026-08-02

data: s3s 批次75 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0343 · ce32f95 · 2026-08-02

feat: 手记审计步骤 2/3——履行核对与报告（三条机械闸 + 分母不失踪）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0344 · 7515a05 · 2026-08-02

data: crd 批次76 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0345 · 6f5800e · 2026-08-02

fix: 手记审计 main() 崩溃隔离与预拼路径取材闸（DS-T5 复评修复）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0346 · be70631 · 2026-08-02

data: s3s 批次77 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0347 · 6871bb9 · 2026-08-02

docs: P3 seg2-s3 台账更新（批74-77 + バランス/夕日 母题前瞻）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0348 · c98095c · 2026-08-02

test: 手记审计播种检验（硬门）+ 计时试跑证据入库

- 变更：3 个路径；.superpowers 2、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0349 · edded47 · 2026-08-02

data: crd 批次78 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0350 · 3c77150 · 2026-08-02

data: s3s 批次79 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0351 · f40fc8b · 2026-08-02

fix: 手记审计三条实质缺陷（区间 id 不展开／正文不传模型／evidence_ids 口径分家）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0352 · 50d9f05 · 2026-08-02

data: crd 批次80 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0353 · 82b3523 · 2026-08-02

data: s3s 批次81 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0354 · 83f4387 · 2026-08-02

data: crd 批次82 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0355 · 1876dfa · 2026-08-02

data: s3s 批次83 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0356 · 281d364 · 2026-08-02

data: s3s 批次84 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0357 · a60dea2 · 2026-08-02

data: crd 批次85 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0358 · 108e789 · 2026-08-02

docs: P3 seg2-s3 台账更新（批78-85 + 夕日/夕焼け 边界 + 双层人名跨批模式）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0359 · 3db7362 · 2026-08-02

data: s3s 批次86 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0360 · e4f7a38 · 2026-08-02

data: crd 批次87 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0361 · ccdffe2 · 2026-08-02

data: s3fa 批次88 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0362 · 5115045 · 2026-08-02

data: s3fa 批次89 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0363 · 6727dc6 · 2026-08-02

data: crd 批次90 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0364 · ab15755 · 2026-08-02

docs: P3 seg2-s3 台账收尾（批86-90 + 段末机检复核与裁决清单）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0365 · 1e1ba3c · 2026-08-03

data: seg2-s3 彩野测试题库（18 题，段绑定闸经对照验证）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg2-s3.yaml`

## 0366 · 6b33fc1 · 2026-08-03

docs: P3 seg2-s3 彩野测试补跑结果（18题 16对/2部分对/0错，两处部分对经核对非译文丢信息）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0367 · 9f0ab58 · 2026-08-03

docs: P3 seg2-s3 人工评审 gate 留痕（6 项抽读裁定 + 12244/12166 两条回改入裁决清单）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0368 · 5716a2f · 2026-08-03

docs: P3 seg2-s3 裁决清单用户逐组反馈落定（含 2 处需复议的我方核实）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0369 · 180e940 · 2026-08-03

docs: P3 seg2-s3 裁决终定（11565 改话题反转版、射的→打气枪 及其 speakers.json 连带）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0370 · c45ae5d · 2026-08-03

feat: glossary v9 —— P3 seg2-s3 段末小裁决与召回令

- 变更：4 个路径；glossary 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0371 · e2da47e · 2026-08-03

data: opus 车道 9 条召回回改（glossary_v=9）+ notes/s3s 维护者回填

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0372 · ed7709e · 2026-08-03

docs: seg2-s3 段末裁决台账入库 + 双车道版本切换到 glossary v9

- 变更：4 个路径；.superpowers 2、docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0373 · 50faf6d · 2026-08-03

ops: 生产树升级 prod-run-v3→v4（C3 原文侧分母）+ 审计发现的 4 条译文回改

- 变更：4 个路径；.superpowers 1、data 1、docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0374 · 6df4776 · 2026-08-03

docs: SEG-3（seg3-s4，b91-117）生产计划

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg3-s4.md`

## 0375 · fc023fc · 2026-08-03

fix: add_patch 车道模式缺省数据目录改为拒绝执行，杜绝静默写错主仓

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/add_patch.py`

## 0376 · dc82f8b · 2026-08-03

fix: 审计加 --max-rounds 与定点重跑，把预算耗尽从「无法判断」里摘出去

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0377 · 9f86b9e · 2026-08-03

docs: task-7 工装修复报告入库（add_patch 车道护栏 + 审计定点重跑）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0378 · c43ff12 · 2026-08-03

data: s4s 批次91 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0379 · e99d89a · 2026-08-03

docs: P3 seg3-s4 台账建立（开场自检 + 上段交接复核 + C3 修复观察点）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0380 · 85b38e7 · 2026-08-03

data: s4s 批次92 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0381 · 6496e00 · 2026-08-03

data: crd 批次93 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0382 · a927b32 · 2026-08-03

docs: P3 seg3-s4 台账（批91-93）+ 锚点机制结构性缺口的全局扫描留痕

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0383 · 673f5df · 2026-08-03

docs: extra 车道生产坍缩设计（seg8，165 批 829 行 → 523 行零 LLM + 3 组会话）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-08-03-extra-lane-collapse-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-08-03-extra-lane-collapse-design.md`

## 0384 · 36a032d · 2026-08-03

data: s4s 批次94 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0385 · 3beba2e · 2026-08-03

data: s4s 批次95 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0386 · 0e3ca1e · 2026-08-03

data: s4s 批次96 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0387 · 631899d · 2026-08-03

docs: P3 seg3-s4 台账更新（批94-96 + CHECKPOINT-1）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0388 · c8c5056 · 2026-08-03

data: crd 批次97 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0389 · 9bfbf75 · 2026-08-03

data: s4s 批次98 译文入线

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0390 · ec53ee1 · 2026-08-03

docs: 长对话多批生产模式设计（实验进行中，待续跑数据定稿）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`

## 0391 · b4dfb3b · 2026-08-03

docs: 长对话多批 spec 定稿（续跑推翻上一轮结论 + W4 机械闸）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`

## 0392 · 468c3ec · 2026-08-03

feat: check_batch 增加顾问级 W4（复现句族内逐字一致）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_batch.py`

## 0393 · 3c0ab9c · 2026-08-03

fix: W4 未启用时显式播报，不与「跑了没报」同形

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_batch.py`

## 0394 · 6248c57 · 2026-08-03

docs: 长对话多批生产模式实施计划（4 任务）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-08-03-long-conversation-batching.md`

## 0395 · 8c2c63a · 2026-08-03

feat: 手记「未履行」审计报告呈现回改车道机械证据（不自动归类）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0396 · 45161a4 · 2026-08-03

docs: 「未履行」四类归因落 spec + Task 9 执行报告

- 变更：2 个路径；.superpowers 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-08-02-deepseek-audit-capability-design.md`

## 0397 · aee2def · 2026-08-03

fix: 异常兜底的「无法判断」纳入 --rerun-gates all 可重跑范围

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/audit_notes_promises.py`

## 0398 · ee6b893 · 2026-08-03

docs: W4 存量 19 组裁决入档——不统一、不建白名单

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`

## 0399 · 7993237 · 2026-08-03

docs: DS-T6 全量审计最终账（定点重跑后可信度 7.6%→5.4%）

- 变更：2 个路径；.superpowers 1、data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0400 · 743798e · 2026-08-03

docs: 长对话 plan 改用双重上限（批数 ≤10 且 行数 ≤600）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-08-03-long-conversation-batching.md`

## 0401 · fa4d045 · 2026-08-03

feat: gen_plan 支持会话组（--session-size/--session-lines 双重上限，默认 1 行为不变）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0402 · 995ca13 · 2026-08-03

docs: 译者指令增加长对话会话模式契约

- 变更：1 个路径；prompts 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `prompts/translator_cc.md`

## 0403 · ba7b512 · 2026-08-03

docs: runbook 增补长对话会话模式条款

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0404 · 4c1c220 · 2026-08-03

docs: 长对话会话模式 Task 1-3 执行报告入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0405 · 6e67cac · 2026-08-03

fix: canary 补传 siblings，此前对 W4 结构性失明

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/canary.py`

## 0406 · 33f49c4 · 2026-08-03

ops: 生产树升级 prod-run-v4→v5（W4 + 长对话会话模式）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0407 · 9845df8 · 2026-08-03

docs: SEG-3 剩余批次改用会话组计划（b99-117，4 组）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-seg3-s4.md`

## 0408 · 556afe1 · 2026-08-03

docs: SEG-3 续跑交接（b99-117，长对话会话模式）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0409 · 0b62317 · 2026-08-03

fix: 会话组补齐崩溃探测与 FAIL 的处置指引 + 堵 6 处恒绿

- 变更：3 个路径；docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-seg3-s4.md`、M `tools/gen_plan.py`

## 0410 · 7a72b9e · 2026-08-03

docs: SEG-3 台账补 b97/98 记录 + 会话组结构性偏离与 b99 交接遗漏留痕

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0411 · 8c8d05c · 2026-08-03

data: s4s 批次99 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0412 · 4655e9a · 2026-08-03

data: crd 批次100 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0413 · 55d2d75 · 2026-08-03

data: s4s 批次101 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0414 · d709c6b · 2026-08-03

data: s4s 批次102 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0415 · 5ef3cda · 2026-08-03

data: crd 批次103 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0416 · 62dfba9 · 2026-08-03

data: s4s 批次104 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0417 · 008bd1c · 2026-08-03

data: crd 批次105 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0418 · d720662 · 2026-08-03

data: s4s 批次106 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0419 · 548e556 · 2026-08-03

data: crd 批次107 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0420 · 07ed0ab · 2026-08-03

data: s4s 批次108 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0421 · 059f10a · 2026-08-03

data: seg3-s4 批次99-108 术语提案与逐批登记（notes）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0422 · 2768536 · 2026-08-03

docs: SEG-3 会话组1（b99-108）逐批记录与 §17 观察入台账

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0423 · 361a365 · 2026-08-03

data: s4s 批次109 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0424 · 8873a6e · 2026-08-03

data: crd 批次110 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0425 · eac97d0 · 2026-08-03

data: s4fa 批次111 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0426 · a754841 · 2026-08-03

data: seg3-s4 批次109-111 术语提案与逐批登记（notes，新增 s4fa.md）

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0427 · c2154f0 · 2026-08-03

docs: SEG-3 会话组2（b109-111）逐批记录与 §18 观察入台账

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0428 · 9c2074a · 2026-08-03

data: s4fa 批次112 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0429 · 1945cbf · 2026-08-03

data: s4s 批次113 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0430 · 57dbc8a · 2026-08-03

data: crd 批次114 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0431 · 86ccc4e · 2026-08-03

data: seg3-s4 批次112-114 术语提案与跨层留痕（notes）

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0432 · 5153a05 · 2026-08-03

docs: SEG-3 会话组3（b112-114）逐批记录与 §19 观察入台账

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0433 · 5974a43 · 2026-08-04

data: s4fb 批次115 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0434 · 7e5a22a · 2026-08-04

data: s4fb 批次116 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0435 · eb52872 · 2026-08-04

data: crd 批次117 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0436 · 4609b9a · 2026-08-04

data: seg3-s4 批次115-117 术语提案与姊妹分支处置清单（notes，新增 s4fb.md）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0437 · a0e0a66 · 2026-08-04

docs: SEG-3 会话组4 与段末机检、全知纪律自检、裁决输入清单入台账

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0438 · 3d55a06 · 2026-08-04

data: seg3-s4 彩野测试题库（18 题，段绑定闸经对照验证）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg3-s4.yaml`

## 0439 · 5e141f5 · 2026-08-04

data: seg3-s4 彩野测试首跑 17/18 + q12 标准答案收窄

- 变更：2 个路径；.superpowers 1、config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg3-s4.yaml`

## 0440 · 3ba0ba5 · 2026-08-04

data: seg3-s4 人工评审 4 条语感回改入 patches（13567/784/13930/14148）+ 维护者留痕

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0441 · c062115 · 2026-08-04

docs: SEG-3 §21 人工评审反馈入台账（gate 通过；12999 判断更正、1430 降级为开放项）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0442 · 8083671 · 2026-08-04

docs: SEG-3 台账更新彩野测试实况（开发轨补跑 17/18）+ 记 q18 标准答案与回改的字面失同步

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0443 · 9d3c856 · 2026-08-04

fix: notes 新建文件的批次标题改为 cluster_notes 认的 '## batch N' 形（修 28 条提案丢批号）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0444 · 7a03319 · 2026-08-04

docs: seg3-s4 段末小裁决会话交接指南

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0445 · b0f771d · 2026-08-04

data: seg3-s4 段末裁决产出 glossary v10 + 召回令

- 变更：3 个路径；glossary 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0446 · 851fa66 · 2026-08-04

data: seg3-s4 裁决回改 1 条入 patches + notes 留痕与批次标题修正

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0447 · 843d7da · 2026-08-04

docs: seg3-s4 裁决记录 + 双车道再冻结 + runbook 术语登记纪律增补

- 变更：4 个路径；.superpowers 2、docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0448 · 8dcb138 · 2026-08-04

fix: cluster_notes 识别长对话 notes 的容器体提案

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/cluster_notes.py`

## 0449 · 0b45cf9 · 2026-08-04

fix: gen_plan 会话组计划写明 ctx 的两段式生成

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/gen_plan.py`

## 0450 · b5045a4 · 2026-08-04

docs: 记档 W4 在会话组组内失明（实测零命中，不修）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`

## 0451 · afb1537 · 2026-08-04

docs: task-12 执行报告入库（notes 容器体解析 / 会话组 ctx / W4 组内失明）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0452 · 39f0f54 · 2026-08-04

docs: 登记 ctx_sha 在会话模式下的语义漂移（§4.4）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-08-03-long-conversation-batching-design.md`

## 0453 · ca89c4e · 2026-08-04

docs: 记 ruby 注音的引擎实况 + 绘本段童谣体的可执行判据

- 变更：2 个路径；CLAUDE.md 1、glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0454 · 5a4507b · 2026-08-04

docs: SEG-4 开工前记录（冻结闸缺口处置 + 绘本单独成组的裁决）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0455 · 2a2d20f · 2026-08-04

fix: 冻结校验补齐 style/voices 覆盖，堵住闸门恒绿的缺口

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/lane_setup.py`

## 0456 · a13513a · 2026-08-04

data: 双车道冻结基准补齐 style/voices（--force 重新冻结）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0457 · 4ac59dc · 2026-08-04

docs: SEG-4 生产交接 + 会话组计划（绘本 b123 机械隔离）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg4-s3tail-s5.md`

## 0458 · 1f118ea · 2026-08-04

data: s3s 批次118 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0459 · 0922cb2 · 2026-08-04

data: s3s 批次119 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0460 · c3f1fcb · 2026-08-04

data: crd 批次120 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0461 · 33a9956 · 2026-08-04

data: s3fb 批次121 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0462 · ec8afc8 · 2026-08-04

data: crd 批次122 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0463 · 147ccf1 · 2026-08-04

data: s3fc 批次123 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0464 · 2a2d0b7 · 2026-08-04

feat: 汉字分级字表 + 用字难度扫描工装 check_charlevel

- 变更：9 个路径；config 8、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_charlevel.py`
- 相关实现/计划变更：A `config/charlists/README.md`、A `config/charlists/gf0025-chudeng-900.txt`、A `config/charlists/gf0025-erji-600.txt`、A `config/charlists/gf0025-yiji-300.txt`、A `config/charlists/jiaoyu-changyong1-2500.txt`、A `config/charlists/jiaoyu-changyong2-1000.txt`、A `config/charlists/jiaoyu-jibenzi-300.txt`、A `config/charlists/tongyong-yiji-3500.txt`、A `tools/check_charlevel.py`

## 0465 · 52d0a23 · 2026-08-04

data: SEG-4 批次 118-123 术语提案入库（crd/s3s/s3fb/s3fc）

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0466 · 295ba8f · 2026-08-04

docs: SEG-4 台账 b118-123 + 绘本专节 + 锚点 ruby 欠账（待外部会话审议）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0467 · 9cd94a5 · 2026-08-04

data: crd 批次124 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0468 · 13fdb60 · 2026-08-04

data: s5s 批次125 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0469 · d3e8811 · 2026-08-04

data: s5s 批次126 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0470 · ff1f249 · 2026-08-04

docs: SEG-4 台账 b124-126 + 术语提案

- 变更：2 个路径；.superpowers 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0471 · 82dd01b · 2026-08-04

data: s3fc 绘本段用字下沉重跑，80 条 review 补丁入线

- 变更：2 个路径；.superpowers 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0472 · 0b3bbed · 2026-08-04

data: crd 批次127 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0473 · 37a6b33 · 2026-08-04

data: s5s 批次128 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0474 · 720674c · 2026-08-04

data: s5s 批次129 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0475 · ff6eb31 · 2026-08-04

docs: SEG-4 台账 b127-129 + CHECKPOINT b123-129

- 变更：3 个路径；.superpowers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0476 · 6c24180 · 2026-08-04

data: s5s 批次130 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0477 · ee26ad7 · 2026-08-04

data: s5s 批次131 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0478 · 2bdb7f1 · 2026-08-04

data: s5s 批次132 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0479 · c9466e0 · 2026-08-04

data: s5s 批次133 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0480 · d8e84d4 · 2026-08-04

docs: SEG-4 台账 b130-133 + 浜千鳥全 8 行留档

- 变更：2 个路径；.superpowers 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0481 · 18de702 · 2026-08-04

data: s5s 批次134 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0482 · ce4c282 · 2026-08-04

data: s5s 批次135 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0483 · 9c7329b · 2026-08-04

data: crd 批次136 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0484 · 67b9ce3 · 2026-08-04

docs: SEG-4 台账 b134-136 + 冻结基准内部不自洽（voices vs anchors）

- 变更：3 个路径；.superpowers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0485 · e1d6ced · 2026-08-04

data: s5f 批次137 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0486 · ab9754a · 2026-08-04

data: crd 批次138 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0487 · e7529ae · 2026-08-04

docs: SEG-4 段末台账（b137-138 + 机检复核 + 段末流程）

- 变更：3 个路径；.superpowers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0488 · 43e3dd9 · 2026-08-04

fix: W3 行宽按屏幕实际占位算，ruby 注音不计宽

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_batch.py`

## 0489 · 4f70c9e · 2026-08-04

docs: translator_cc 补「W3 真触发了怎么办」的默认动作

- 变更：1 个路径；prompts 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `prompts/translator_cc.md`

## 0490 · 0d9ac3b · 2026-08-04

docs: task-14 执行报告入库（W3 剥 ruby + prompt 口径）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0491 · 4e4cccb · 2026-08-04

feat: 加 glossary/voices 示范译例与 skeleton/anchors 定稿自洽机械闸

- 变更：5 个路径；.superpowers 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_voices_anchors.py`
- 相关实现/计划变更：A `tools/check_voices_anchors.py`、M `tools/lane_setup.py`

## 0492 · 0a0e2e0 · 2026-08-04

data: seg4-s3tail-s5 彩野测试题库（18 题，段绑定闸经对照验证）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg4-s3tail-s5.yaml`

## 0493 · 501dee9 · 2026-08-04

data: 锚点行 ruby 注音豁免落地（用户裁决）+ style.md 写死 ruby 的定性

- 变更：3 个路径；glossary 1、pilot 1、skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0494 · 9597f00 · 2026-08-04

docs: SEG-4 段末补记（彩野测试补跑 + 开发轨并行落地的交接缝）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0495 · 9ccc65e · 2026-08-04

data: voices 示范译例对齐 anchors 定稿（4 条，补全 4e4cccb）

- 变更：4 个路径；glossary 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0496 · 4f73865 · 2026-08-04

docs: extra 坍缩 spec 补 §7.1——main 车道实测留档

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-08-03-extra-lane-collapse-design.md`

## 0497 · 575ab2e · 2026-08-04

data: seg4 彩野测试 API 调用入账（生产会话产出）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0498 · 90fa957 · 2026-08-04

fix: seg4 彩野测试 q6 标准答案改正——互斥分支被缝成了一条时间线

- 变更：2 个路径；config 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`、M `config/ayano_qa/seg4-s3tail-s5.yaml`

## 0499 · 0c2b364 · 2026-08-04

docs: style.md 定死 ruby 注音频次判据（单字逐次全注 / 专名只在引入处注）

- 变更：1 个路径；glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0500 · c8cb04e · 2026-08-04

feat: lane_setup --verify 播报「车道冻结拷贝落后于仓库侧」

- 变更：3 个路径；docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/lane_setup.py`

## 0501 · baf8c4e · 2026-08-04

docs: SEG-4 段末小裁决交接件 + 纳哈梅去重 patch + 收尾登记

- 变更：3 个路径；.superpowers 1、docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0502 · 2c99ba7 · 2026-08-04

docs: 台账勘误（纳哈梅注音串写错一个声调）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0503 · 7e17f1c · 2026-08-04

docs: 新增 glossary/style_refine.md——汉语母语感六条细则（用户口述）

- 变更：2 个路径；docs 1、glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0504 · 827ccdb · 2026-08-04

feat: 车道级 freeze_exclude——opus 重冻结不再带上 style_refine.md

- 变更：5 个路径；docs 1、glossary 1、pilot 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/lane_setup.py`

## 0505 · 8ad27e5 · 2026-08-04

data: glossary v11 —— P3 seg4-s3tail-s5 段末小裁决与召回令

- 变更：9 个路径；.superpowers 2、glossary 3、pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0506 · 178401e · 2026-08-05

ops: 生产树升级 prod-run-v5→v6（W3 行宽剥 ruby）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0507 · ffe09d3 · 2026-08-05

docs: SEG-5 生产计划 + 点火 handoff（b139–154，seg5-s6-s7f）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg5-s6-s7f.md`

## 0508 · 35cdc9f · 2026-08-05

docs: SEG-5 开工台账（开场自检 + 会话组划分 + b139–148 派发记录）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0509 · 8b79f22 · 2026-08-05

data: s6s/crd 批次139–148 译文入线（会话组，536 行）

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0510 · 220a9bf · 2026-08-05

docs: SEG-5 台账 —— 会话组 1（b139–148）复核记录与两条流程偏差登记

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0511 · f97eee9 · 2026-08-05

data: crd 批次149 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0512 · dc0cea0 · 2026-08-05

data: s6f 批次150 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0513 · d80a720 · 2026-08-05

data: crd 批次151 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0514 · e5012db · 2026-08-05

data: 会话组 b149–151 术语提案归档（crd 追加 + s6f 新建）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0515 · db4d1c9 · 2026-08-05

docs: SEG-5 台账 —— 会话组 2（b149–151）复核记录；锚点子串位经验登记

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0516 · fae5e84 · 2026-08-05

data: s7f 批次152 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0517 · 8c2445a · 2026-08-05

data: s7f 术语提案归档（b152，11 条）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0518 · f9c0aec · 2026-08-05

docs: SEG-5 台账 —— b152 递卡段逐张核对结论（单列供 P4 复用）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0519 · 6b9ac02 · 2026-08-05

data: s7f 批次153 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0520 · c86f407 · 2026-08-05

data: crd 批次154 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0521 · 3a63dfc · 2026-08-05

data: 会话组 b153–154 术语提案归档（s7f/crd 追加）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0522 · 7131a53 · 2026-08-05

docs: SEG-5 段末台账 —— 机检复核、W4 失明自检、梗概回译自检与抽读靶子

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0523 · ac06a04 · 2026-08-05

data: seg5-s6-s7f 彩野测试题库（18 题，段绑定闸经对照验证）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg5-s6-s7f.yaml`

## 0524 · 535fb9f · 2026-08-05

docs: SEG-5 彩野测试结果（16/2/0）+ 查实题库 q14 场景归属错误

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0525 · 68afb78 · 2026-08-05

data: seg5 彩野测试 API 调用入账（生产会话产出）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0526 · 2b09abc · 2026-08-05

data: seg5 抽读裁决落地 5 条 patch（review, glossary_v=11）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0527 · 6da47ec · 2026-08-05

docs: SEG-5 台账 —— 用户抽读裁决与落地记录

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0528 · ceaa712 · 2026-08-05

fix: 恢复 id 1600 的 SEG-4 已裁定稿『章节３Ａ的梗概是――』

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0529 · 8b37131 · 2026-08-05

docs: SEG-5 段末小裁决会话交接件

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0530 · a6a627a · 2026-08-05

docs: SEG-5 台账 —— 修正 1600 误覆盖的复盘记录

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0531 · c532d7c · 2026-08-05

docs: SEG-5 人工评审 gate 放行，计划完成（b139–154 全部入线）

- 变更：2 个路径；.superpowers 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/translate-seg5-s6-s7f.md`

## 0532 · 4a1f603 · 2026-08-05

docs: SEG-5 段末小裁决 —— glossary v12 + 召回令（active 39→44，style v11→v12）

- 变更：3 个路径；glossary 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0533 · 8321b1d · 2026-08-05

data: seg5 裁决回改 6 条 patch（recall, glossary_v=12）+ 5 份 notes 维护者记录

- 变更：6 个路径；pilot 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0534 · ff6d145 · 2026-08-05

chore: 双车道按 v12 再冻结 + SEG-5 裁决记录与台账收口

- 变更：3 个路径；.superpowers 2、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0535 · 5c5778d · 2026-08-05

fix: cluster_notes 认表格体提案，并对认不出的表出声（五段静默丢失）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/cluster_notes.py`

## 0536 · b9d602b · 2026-08-05

fix: 彩野测试判分解析认「判定|对|…」漂移 + 修 seg5 q14 场景归属

- 变更：3 个路径；config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg5-s6-s7f.yaml`、M `tools/ayano_test.py`

## 0537 · 0b568a3 · 2026-08-05

docs: SEG-6 生产计划 + 点火 handoff（b155–166，seg6-s8-e1）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg6-s8-e1.md`

## 0538 · d1c3178 · 2026-08-05

docs: SEG-6 开工台账（开场自检通过，b155–160 ctx 就位）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0539 · 7ffe384 · 2026-08-05

data: s8s 批次155 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0540 · 8edb52e · 2026-08-05

data: crd 批次156 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0541 · 9cbc164 · 2026-08-05

data: s8f 批次157 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0542 · 19e967e · 2026-08-05

data: crd 批次158 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0543 · df6b72d · 2026-08-05

data: s4s 批次159 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0544 · 4f6b939 · 2026-08-05

data: crd 批次160 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0545 · a59e91f · 2026-08-05

data: 会话组 b155–160 术语提案归档

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0546 · fc35ed8 · 2026-08-05

docs: SEG-6 台账 —— 会话组 b155–160 复核记录与待裁决项

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0547 · 863eaaa · 2026-08-05

data: e1s 批次161 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0548 · fbad492 · 2026-08-05

data: e1s 批次161 术语提案归档

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0549 · 65d5fe1 · 2026-08-05

docs: SEG-6 台账 —— b161 复核记录与 e1s 语域参数表

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0550 · eb25378 · 2026-08-05

data: e1s 批次162 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0551 · 0d698aa · 2026-08-05

data: e1s 批次163 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0552 · 5b71dc5 · 2026-08-05

data: crd 批次164 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0553 · 390f800 · 2026-08-05

data: e1f 批次165 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0554 · ef2f556 · 2026-08-05

data: crd 批次166 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0555 · 3b8ca8b · 2026-08-05

data: 会话组 b162–166 术语提案归档

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0556 · e1e7634 · 2026-08-05

docs: SEG-6 台账 —— 会话组 b162–166 复核、段末机检与 e1s 语域自评

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0557 · 1e9bb6b · 2026-08-05

data: seg6-s8-e1 彩野测试题库（18 题，出题方法改为「先读原文、再核验译文」）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg6-s8-e1.yaml`

## 0558 · fa4c95f · 2026-08-05

data: SEG-6 抽读裁定 —— id 4697『走出了天台』→『走下了天台』

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0559 · 43a5bef · 2026-08-05

docs: SEG-6 台账 —— 用户抽读裁定（4697 改译入 patches、嫉妒/吃醋二分）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0560 · 648c4a3 · 2026-08-05

docs: SEG-6 台账 —— 彩野测试补跑（16/2/0）与两条部分对的核对结论

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0561 · 87e8e02 · 2026-08-05

docs: SEG-6 段末小裁决会话交接件

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0562 · 6e0898c · 2026-08-05

docs: SEG-6 段末裁决 —— glossary v13 + 召回令

- 变更：4 个路径；glossary 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0563 · 23836d0 · 2026-08-05

data: SEG-6 v13 召回令回改 —— 10 条 patch + 3 份 notes 维护者记录

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0564 · ac0d1cf · 2026-08-05

chore: SEG-6 段边界双车道按 v13 再冻结

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0565 · 0c1e441 · 2026-08-05

docs: SEG-6 段末小裁决记录与台账收口

- 变更：2 个路径；.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0566 · c7c9b88 · 2026-08-05

fix: SEG-6 四条反馈处置 —— 题库全知补名、resolve 静默空表、锚点子串、撤销多余禁令

- 变更：5 个路径；config 2、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`、M `config/ayano_qa/seg6-s8-e1.yaml`、M `tools/resolve.py`

## 0567 · 8ff400f · 2026-08-05

docs: SEG-7 生产计划 + 点火 handoff（b167–173，seg7-e2，main 车道收官段）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/translate-seg7-e2.md`

## 0568 · facfee2 · 2026-08-05

docs: SEG-7 开工台账（收官段；三处无机械闸位置已实测确认）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0569 · d540ec9 · 2026-08-05

data: e2s 批次167 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0570 · bbe5305 · 2026-08-05

data: e2s 批次168 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0571 · 4dcb2fd · 2026-08-05

data: crd 批次169 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0572 · 45e113b · 2026-08-05

data: 会话组 b167–169 术语提案归档

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0573 · 338b016 · 2026-08-05

docs: SEG-7 台账 —— 会话组 b167–169 复核、崩解开篇定稿与单边独白反推记录

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0574 · 586d470 · 2026-08-05

data: e2f 批次170 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0575 · 4bee7d5 · 2026-08-05

data: e2f 批次170 术语提案归档

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0576 · b5b9eb9 · 2026-08-05

docs: SEG-7 台账 —— b170 复核记录（开篇对位 7/7、锚点 5/5）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0577 · e32164b · 2026-08-06

data: e2f 批次171 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0578 · 78885b6 · 2026-08-06

data: e2f 批次172 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0579 · c0aed94 · 2026-08-06

data: crd 批次173 译文入线

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0580 · 7a06b95 · 2026-08-06

docs: SEG-7 台账 —— 会话组 b171–173 入线、执行事故复盘与独立核验记录

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0581 · a21990f · 2026-08-06

data: 会话组 b171–173 术语提案归档（事后补录）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0582 · fe55dcd · 2026-08-06

docs: SEG-7 台账 —— b171–173 补录结果与两处疑似问题

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0583 · e159f8c · 2026-08-06

data: SEG-7 抽读裁定 —— 5540『海马』→『海马体』、5442 枚举位『故事』→『物语』

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0584 · 369c8f6 · 2026-08-06

docs: SEG-7 段末流程 —— 机检、梗概自检、收官合计与两条流程教训

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0585 · 41c45f5 · 2026-08-06

data: seg7-e2 彩野测试题库（18 题，main 车道收官段）

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/ayano_qa/seg7-e2.yaml`

## 0586 · 274994f · 2026-08-06

data: SEG-7 抽读裁定 —— 5481/5482/5483/5491 千秋侧『ユウイチ学长』、5648 补足音节

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0587 · 56be2f9 · 2026-08-06

data: SEG-7 抽读裁定 —— 5683/5684 きく 三换字改用同音别字（汀→厅→听）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0588 · 2ba4ffb · 2026-08-06

docs: SEG-7 台账 —— 崩解开篇 きく 三换字改版为同音别字（汀/厅/听）及备选存档

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0589 · 3dab647 · 2026-08-06

docs: SEG-7 段末小裁决会话交接件（含 main 轨收官与下一轨切换）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0590 · 29c4eb9 · 2026-08-06

data: glossary v14 —— seg7-e2 段末裁决（main 车道收官版）+ 双车道再冻结

- 变更：8 个路径；glossary 7、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0591 · 25514fe · 2026-08-06

data: seg7-e2 段末裁决回改 2 条 + notes 维护者记录

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0592 · 11e9ea5 · 2026-08-06

docs: SEG-7 段末小裁决记录（ruling-seg7-e2.md）+ 台账收口

- 变更：2 个路径；.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0593 · 47faea6 · 2026-08-06

feat: 题库↔译文失同步闸 + add_patch 查重播报（SEG-7 反馈处置）

- 变更：9 个路径；config 4、docs 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_qa_quotes.py`
- 相关实现/计划变更：M `config/ayano_qa/seg3-s4.yaml`、M `config/ayano_qa/seg4-s3tail-s5.yaml`、M `config/ayano_qa/seg5-s6-s7f.yaml`、M `config/ayano_qa/seg7-e2.yaml`、M `tools/add_patch.py`、A `tools/check_qa_quotes.py`

## 0594 · 76c7bbb · 2026-08-07

docs: P4 润色 pass 设计 spec（四桶分流+保税仓+双派发+放大扫描）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`

## 0595 · fbdaeda · 2026-08-07

docs: P4 润色 pass 实施计划（11 任务：polishlib→setup→context→ingest→check→triage→commit→amplify→calibrate→SEG-1 点火）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-08-07-p4-polish-pass.md`

## 0596 · 624af06 · 2026-08-07

chore: style_refine.md 统一更名 polish.md（含 opus 车道排除集迁移）

- 变更：5 个路径；docs 1、glossary 1、pilot 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/lane_setup.py`

## 0597 · 45d192d · 2026-08-07

docs: task-1-report.md（style_refine→polish 改名任务证据存档）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0598 · 3f1dfc2 · 2026-08-07

feat: P4 润色公共层 polishlib + 集中阈值配置

- 变更：3 个路径；config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polishlib.py`
- 相关实现/计划变更：A `config/polish.yaml`、A `tools/polishlib.py`

## 0599 · 6133908 · 2026-08-07

docs: task-2-report.md（polishlib 公共层任务证据存档）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0600 · 5257cf7 · 2026-08-07

feat: polish_setup——SEG 级冻结+锁定面+opus 固化时点

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_setup.py`
- 相关实现/计划变更：A `tools/polish_setup.py`

## 0601 · 5cafc68 · 2026-08-07

fix: polish_setup.verify——补反向扫描，抓凭空多出的未登记文件

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_setup.py`

## 0602 · 4e27df7 · 2026-08-07

feat: polish_context——SEG-1 会话分组补齐+润色 prompt 拼接

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_context.py`
- 相关实现/计划变更：A `tools/polish_context.py`

## 0603 · d45eee6 · 2026-08-07

fix: polish_context——补 rulings 读取通路+正文行去括号嵌套（评审 Important×2）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0604 · 0ce109b · 2026-08-07

feat: polish_ingest——回执核验+锁定判死+批级幂等的唯一入仓口

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_ingest.py`
- 相关实现/计划变更：A `tools/polish_ingest.py`

## 0605 · a63631d · 2026-08-07

fix: polish_ingest——补 zh↔jp 错位侦测 + 空zh判死（评审Critical）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_ingest.py`

## 0606 · 038856f · 2026-08-07

fix: polish_ingest——非字符串zh判死不崩溃+错位闸收窄防短句伪报

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_ingest.py`

## 0607 · 357c68a · 2026-08-07

feat: polish_check——候选级机械闸（复用 check_batch）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_check.py`
- 相关实现/计划变更：A `tools/polish_check.py`

## 0608 · 46fe40b · 2026-08-07

fix: polish_check speakers——补齐冻结面，去掉活仓库回落

- 变更：9 个路径；.superpowers 1、docs 2、tests 4、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-08-07-p4-polish-pass.md`、M `docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`、M `tools/polish_check.py`、M `tools/polish_setup.py`

## 0609 · 5422266 · 2026-08-07

feat: polish_triage——四桶分流+条件自动清关+确定性抽检

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_triage.py`
- 相关实现/计划变更：A `tools/polish_triage.py`

## 0610 · 83bc438 · 2026-08-07

docs: progress.md 台账入库（含 Task 7 记录）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0611 · 8c03388 · 2026-08-07

fix: polish_triage——抽检数封顶于 K，压缩必须播报（评审 Important）

- 变更：4 个路径；.superpowers 2、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_triage.py`

## 0612 · 6d2c99e · 2026-08-07

feat: polish_commit——保税仓唯一清关口（dry-run 默认+prov 倒查链）

- 变更：4 个路径；.superpowers 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_commit.py`
- 相关实现/计划变更：M `tools/add_patch.py`、A `tools/polish_commit.py`

## 0613 · b71ba2d · 2026-08-07

docs: SDD 台账更新（Task 7 修复轮结论 + Task 8 完成）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0614 · 2749460 · 2026-08-07

feat: polish_amplify——裁决意图纪要+放大扫描装配（每段一轮）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_amplify.py`
- 相关实现/计划变更：A `tools/polish_amplify.py`

## 0615 · f961f5d · 2026-08-07

fix: polish_amplify——桶2补渲染裁决最终zh+amplify专属prompt_hash（评审修复轮）

- 变更：6 个路径；.superpowers 2、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_amplify.py`、M `tools/polish_ingest.py`

## 0616 · c070ca5 · 2026-08-07

docs: SDD 台账（Task 9 完成）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0617 · b684b82 · 2026-08-07

feat: polish_calibrate——金标准入小考（门槛制，播报已知偏差）

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_calibrate.py`
- 相关实现/计划变更：A `tools/polish_calibrate.py`

## 0618 · 58b0656 · 2026-08-07

docs: SDD 台账（Task 10 完成）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0619 · f644e16 · 2026-08-07

fix: P4 挂起两条 minor —— verify() 忽略名单 + polish_context 章节编号

- 变更：6 个路径；tests 3、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`、M `tools/polish_setup.py`、M `tools/polishlib.py`

## 0620 · ffcd6b4 · 2026-08-07

docs: P4 润色 runbook + SEG-1 双通道点火 handoff（冻结与计划实跑产物）

- 变更：7 个路径；.gitignore 1、docs 2、pilot 4
- 新增规格/运行手册：`docs/ops/p4-polish-runbook.md`
- 新增工装入口/模块：无

## 0621 · b51426a · 2026-08-07

docs: SDD 证据（Task 11 报告）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0622 · 0d0a4d8 · 2026-08-07

fix: Task 11 评审修复轮 —— 章节交叉引用残留 + is_ignored_extra 目录判据缝隙

- 变更：7 个路径；.superpowers 2、pilot 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`、M `tools/polishlib.py`

## 0623 · 9a01a76 · 2026-08-07

docs: 回填 Task 11 修复轮报告的 commit 哈希

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0624 · 152496c · 2026-08-07

fix: Finding C —— polish_amplify.scan_prompt() 同根因编号撞号

- 变更：6 个路径；.superpowers 1、tests 2、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_amplify.py`、M `tools/polish_context.py`、M `tools/polishlib.py`

## 0625 · 8f3115b · 2026-08-07

docs: 回填 Finding C 修复轮报告的 commit 哈希

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0626 · 6e5dd1c · 2026-08-07

docs: SDD 台账（Task 11 完成，11/11）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0627 · 825ab2c · 2026-08-07

fix: P4 三条 Critical —— gates 覆盖面记录 + 控制码计数硬闸 + 全段 W4 模式

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_check.py`、M `tools/polish_triage.py`

## 0628 · 74af7dd · 2026-08-07

fix: P4 I4/I5 —— 冻结基线首次被消费 + 已在产 SEG 拒绝重冻结

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_commit.py`、M `tools/polish_setup.py`

## 0629 · f262455 · 2026-08-07

feat: polish_audit——抽检推翻率闸（I7）+ 准入小考不得解冻

- 变更：3 个路径；tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_audit.py`
- 相关实现/计划变更：A `tools/polish_audit.py`、M `tools/polish_calibrate.py`

## 0630 · 1c4bd22 · 2026-08-07

feat: polish_context --calib——校准批渲染器（I9）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0631 · eb78158 · 2026-08-07

docs: P4 I1/I2/I3/I8 —— polish.md §7 如实反映接入现状 + runbook/handoff 修正

- 变更：3 个路径；docs 2、glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0632 · b889e97 · 2026-08-07

data: SEG-1 冻结面随 polish.md 改动重冻结 + 四个 session prompt 重渲染

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0633 · 96897c9 · 2026-08-07

data: SEG-1 全段 W4 复检基线（点火前，9 处既有复现句族不一致）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0634 · 05ec053 · 2026-08-07

docs: SDD 证据——P4 最终评审修复轮报告 + 台账

- 变更：2 个路径；.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0635 · 82ae68b · 2026-08-07

docs: SDD 证据归档——最终评审 + 修复波 + 残留项裁定（P4 交付）

- 变更：12 个路径；.superpowers 12
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0636 · 2f9f322 · 2026-08-07

docs: handoff 补点火速查 + runbook §七 补齐自动清关的五条前置

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0637 · 8a4ade3 · 2026-08-07

fix: 点火速查的校准输出路径对齐 prompt 输出契约

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0638 · e917f57 · 2026-08-07

fix: P4 润色准入小考裁定落地——锚点行改软锁 + score() 判卷缺陷修复

- 变更：23 个路径；.superpowers 1、config 1、docs 2、pilot 5、tests 8、tools 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/polish.yaml`、M `docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md`、M `tools/polish_amplify.py`、M `tools/polish_calibrate.py`、M `tools/polish_context.py`、M `tools/polish_ingest.py`、M `tools/polish_setup.py`、M `tools/polish_triage.py`

## 0639 · 243dd0e · 2026-08-07

docs: SEG-1 准入小考实测结论入 handoff + 校准原始输出归档

- 变更：5 个路径；.superpowers 1、docs 1、pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0640 · 9cb0fe4 · 2026-08-07

chore: SEG-1 请裁配额 K 150→500 + 通道反馈台账

- 变更：4 个路径；config 1、docs 1、pilot 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/polish.yaml`

## 0641 · c24812c · 2026-08-07

docs: SEG-1 通道反馈台账补 S2/S3 + 首例实弹事故 E1

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0642 · e505b90 · 2026-08-07

data: SEG-1 双通道全段候选入仓 + 四桶分流（233 个待裁 id）

- 变更：62 个路径；pilot 62
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0643 · 0aa7464 · 2026-08-07

data: SEG-1 段末裁决落地——233 条裁决、233 条 patch 清关

- 变更：7 个路径；config 1、docs 2、pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`

## 0644 · c404d60 · 2026-08-07

feat: P4 SEG-2 准备三件套——补开头段表、题库引文抑制清单、修 amplify 轮数标记语义

- 变更：11 个路径；.superpowers 1、config 2、docs 1、tests 4、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/qa_quote_suppressions.yaml`、M `config/segments.yaml`、M `tools/check_qa_quotes.py`、M `tools/polish_amplify.py`、M `tools/polish_ingest.py`

## 0645 · 0f8b945 · 2026-08-07

fix: 段表新段改用 seg:0 消除与 seg1-s2 的 label 歧义

- 变更：5 个路径；.superpowers 1、config 1、tests 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/segments.yaml`、M `tools/ayano_test.py`

## 0646 · 6c0de64 · 2026-08-07

data: polish.md 追加 §0 抓出错译 + §5(d) 判断单位是上下文（用户裁定）

- 变更：1 个路径；glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0647 · d39ac06 · 2026-08-07

data: SEG-0（seg0-s0-s1，b1-35）冻结面建立

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0648 · 3553541 · 2026-08-07

docs: SEG-0 点火 handoff + K 500→700 + runbook 阈值变更记录

- 变更：6 个路径；config 1、docs 2、pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/polish.yaml`

## 0649 · 2aeef3f · 2026-08-07

data: SEG-0 第一轮（b1-24）双通道候选入仓 + 312 条裁决

- 变更：58 个路径；pilot 58
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0650 · 8e10ff3 · 2026-08-07

data: SEG-0 段末裁决落地——506 条裁决、419 条 patch 清关

- 变更：35 个路径；pilot 35
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0651 · 90ff6f1 · 2026-08-07

data: polish.md 追加 §5(e)——名字重复可能是演出机关本身

- 变更：1 个路径；glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0652 · 71f918c · 2026-08-07

fix: P4 润色工装两处缺口——请裁行强制进队列 + W4 报全族成员

- 变更：8 个路径；.superpowers 1、docs 1、tests 3、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_check.py`、M `tools/polish_commit.py`、M `tools/polish_triage.py`

## 0653 · a50a75a · 2026-08-07

feat: extra 轨机械派生工具——从冻结骨架派生 plot_title/scene_title/card_msg

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/derive_extra.py`
- 相关实现/计划变更：A `tools/derive_extra.py`

## 0654 · 7fe6d6b · 2026-08-07

data: 11479 错别字回改「渗人」→「瘆人」（跨段，用户裁定）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0655 · 8721969 · 2026-08-07

feat: plot/ 卡名缩略图集烤字回填试片——工具+测试+版面规格

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_plot.py`
- 相关实现/计划变更：A `tools/bake_plot.py`

## 0656 · 16bb305 · 2026-08-08

fix: plot/ 烤字背景处理方案 v2——逐格墨迹实测色带，废除固定 TEXT_BOX

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_plot.py`

## 0657 · 5256eff · 2026-08-08

fix: 卡162 回退格色带高度改按中文实际行数算，废除固定回退值

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_plot.py`

## 0658 · ea41623 · 2026-08-08

chore: 入库霞鹜文楷 TTF（烤字链路依赖，SIL OFL）

- 变更：1 个路径；third_party 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0659 · 9e3e044 · 2026-08-08

feat: 共用中文折行模块 tools/zh_wrap.py——词边界感知 + 禁则 + 全局最优 DP

- 变更：7 个路径；.superpowers 1、pyproject.toml 1、tests 2、tools 2、uv.lock 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/zh_wrap.py`
- 相关实现/计划变更：M `tools/bake_plot.py`、A `tools/zh_wrap.py`

## 0660 · 9c06206 · 2026-08-09

docs: sysgim 烤字清点台账（用户人工过眼 62 张）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0661 · 9d43947 · 2026-08-09

data: extra 轨 829 条落盘 forward_extra.jsonl + derive_extra 补全 card_msg 派生规则

- 变更：8 个路径；.gitignore 1、.superpowers 1、data 1、pilot 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/land_extra.py`
- 相关实现/计划变更：M `tools/derive_extra.py`、A `tools/land_extra.py`

## 0662 · c4b1704 · 2026-08-09

docs: select/ 烤字清点——141 个按钮里 73 个中文已现成，零补译

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0663 · 17ccb7a · 2026-08-09

feat: png/scene/ 场景名条集烤字回填——195 张卡标题，纯色底居中版式

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_scene.py`
- 相关实现/计划变更：A `tools/bake_scene.py`

## 0664 · a00d8b6 · 2026-08-09

feat: scene/ 卡名条带字号调档 9px→10px（用户看过对照后选定）

- 变更：4 个路径；.superpowers 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_scene_size_ab.py`
- 相关实现/计划变更：M `tools/bake_scene.py`、A `tools/bake_scene_size_ab.py`

## 0665 · b19966f · 2026-08-09

feat: scene/ 卡名条带字号——单一 10px 改为逐格 11px 级联回落 10px

- 变更：5 个路径；.superpowers 1、tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_scene_size_ab2.py`
- 相关实现/计划变更：M `tools/bake_scene.py`、M `tools/bake_scene_size_ab.py`、A `tools/bake_scene_size_ab2.py`

## 0666 · 178a3ea · 2026-08-09

docs: 烤字裁决台账 + plot/scene 版面规格快照入库

- 变更：3 个路径；docs 3
- 新增规格/运行手册：`docs/ops/bake-specs/plot-layout-spec.md`、`docs/ops/bake-specs/scene-layout-spec.md`
- 新增工装入口/模块：无

## 0667 · 35f4b60 · 2026-08-10

data: 卡面右栏 section_label 中译 20 种（草案，单独存不动骨架）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0668 · 36c016e · 2026-08-10

docs: png/card/ 版面测绘（第三块烤字，仅测绘不渲染）

- 变更：4 个路径；.superpowers 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：`docs/ops/bake-specs/card-layout-spec.md`
- 新增工装入口/模块：`tools/measure_card.py`
- 相关实现/计划变更：A `tools/measure_card.py`

## 0669 · 0b053bf · 2026-08-10

feat: png/card/ 烤字渲染——聚类背景重建 + 卡94白名单 + 右栏非均匀行距

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_card.py`
- 相关实现/计划变更：A `tools/bake_card.py`

## 0670 · 0080ded · 2026-08-10

docs: card/ 烤字裁决入台账（C1-C7），用户验收通过

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0671 · eab5bdf · 2026-08-10

data: select 烤字第四块——解析器改进 + 墨迹核验 + 版面测绘 + 异形10张查明

- 变更：5 个路径；.superpowers 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/derive_select.py`、`tools/select_layout.py`
- 相关实现/计划变更：A `tools/derive_select.py`、A `tools/select_layout.py`

## 0672 · 5a92e69 · 2026-08-10

docs: 更正 select/ 清点的错误结论——推导法错误率 46%，非零补译

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0673 · 1a7fd3b · 2026-08-10

data: select/ 选项按钮译文——92 张读图确认 + 双通道翻译合并

- 变更：2 个路径；data 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0674 · d8e8dee · 2026-08-10

feat: png/select/ 烤字渲染——134 按钮 268 张，18/17px 级联 + 描边实测取色

- 变更：3 个路径；.superpowers 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_select.py`
- 相关实现/计划变更：A `tools/bake_select.py`

## 0675 · 24b1a33 · 2026-08-10

feat: sel_map_1_a 探索地图地点表烤字——网格测绘+渲染+lua 交叉核验

- 变更：4 个路径；.superpowers 1、data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_select_map.py`
- 相关实现/计划变更：A `tools/bake_select_map.py`

## 0676 · 73842cb · 2026-08-10

docs: select/ 烤字裁决入台账（L1-L10）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0677 · 141f343 · 2026-08-10

feat: UI 术语一致性闸——61 条定译取自已入线正文，首跑即抓出 物語→物语

- 变更：5 个路径；config 2、data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_ui_terms.py`
- 相关实现/计划变更：A `config/ui_term_suppressions.yaml`、A `config/ui_terms.yaml`、A `tools/check_ui_terms.py`

## 0678 · 093df7a · 2026-08-10

feat: sysgim 描边字族烤字——20 张 86 行，族边界与逐行状态全部实测

- 变更：4 个路径；data 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_sysgim_outline.py`、`tools/measure_sysgim.py`
- 相关实现/计划变更：A `tools/bake_sysgim_outline.py`、A `tools/measure_sysgim.py`

## 0679 · 58439ce · 2026-08-10

feat: sysgim 发光字族烤字——13 张 17 行，发光曲线逐盒实测

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_sysgim_glow.py`
- 相关实现/计划变更：A `tools/bake_sysgim_glow.py`

## 0680 · e19d6c5 · 2026-08-10

chore: sysgim 烤字字体与填充增益改为可换（ZND_UI_FONT / ZND_UI_FILL_GAIN）

- 变更：2 个路径；tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_outline.py`

## 0681 · 4c8ac79 · 2026-08-10

data: extra 车道用词统一——物語→故事 15 处、ゲームオーバー→游戏结束 16 处

- 变更：2 个路径；data 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0682 · d7742b5 · 2026-08-10

docs: sysgim 逐张情况入台账 + Y1–Y14 裁决

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0683 · 1610c2b · 2026-08-10

docs: 烤字总进度台账 + P4 SEG-2 点火 handoff + 补记阈值 T3

- 变更：7 个路径；docs 3、pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0684 · 3436387 · 2026-08-10

feat: 发光模型推广为「相对底色」——三张暂缓件回收，C 类的路也通了

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_sysgim_glow.py`

## 0685 · ad6e3e2 · 2026-08-10

data: SEG-2 双通道候选入仓（含 ds-flash 的 jp_tail 漂移证据）

- 变更：66 个路径；pilot 66
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0686 · 38ed2b6 · 2026-08-10

data: SEG-2 段末裁决落地——128 条裁决、124 条 patch 清关

- 变更：13 个路径；config 1、docs 1、pilot 11
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/qa_quote_suppressions.yaml`

## 0687 · adabad0 · 2026-08-11

docs: P4 SEG-3 点火 handoff + T4 取消准入小考

- 变更：4 个路径；docs 2、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0688 · 23f2a23 · 2026-08-11

data: SEG-3 双通道候选入仓——2571×2 行零判死，队列 241 条

- 变更：63 个路径；pilot 63
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0689 · ec2bc19 · 2026-08-11

data: SEG-3 段末裁决落地——241 条裁决、226 条 patch 清关

- 变更：6 个路径；docs 1、pilot 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0690 · b56bccf · 2026-08-11

fix: SEG-3 改判 14202——采纳稿撑破 W3 行宽，换等义短稿

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0691 · e1fdeee · 2026-08-12

data: SEG-3 用户复核改判 58 条

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0692 · e453e68 · 2026-08-12

docs: polish.md 追加三条语感细则（标点/授受/从句位置）

- 变更：10 个路径；glossary 1、tests 7、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_amplify.py`、M `tools/polish_context.py`

## 0693 · 4880310 · 2026-08-12

feat: sweep_punct 标点清扫工具 + 全库 532 行落地（polish.md §7(a)）

- 变更：3 个路径；pilot 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/sweep_punct.py`
- 相关实现/计划变更：A `tools/sweep_punct.py`

## 0694 · ba0aa88 · 2026-08-12

feat: sweep_punct 加 --include-patched，扫掉最后 13 条已 patch 行

- 变更：3 个路径；pilot 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/sweep_punct.py`

## 0695 · 974a3da · 2026-08-12

feat: 锁清单补锚点孪生行 + P4 SEG-4 点火 handoff

- 变更：5 个路径；docs 1、pilot 2、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_setup.py`

## 0696 · 1d0b777 · 2026-08-12

docs: paseo antigravity-acp 通道摸底——发射路径已通，质量未评估（资格门挡死）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0697 · b119c87 · 2026-08-12

data: SEG-4 双通道候选入仓——1621×2 行零判死，队列 164 条

- 变更：50 个路径；pilot 50
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0698 · 15eafaf · 2026-08-12

fix: rulings.md 跨段承接——runbook 承诺的「前馈进下一 SEG」此前是假的

- 变更：3 个路径；docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_setup.py`

## 0699 · 34a0564 · 2026-08-12

data: SEG-4 段末裁决落地——164 条裁决、162 条 patch 清关

- 变更：5 个路径；pilot 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0700 · 2e49b5d · 2026-08-12

docs: antigravity 摸底第二轮——资格已解除，又撞三道独立的墙

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0701 · b8c8a41 · 2026-08-12

docs: antigravity 第三轮——直连 agy 跑通，质量结论：零改动

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0702 · 49251bd · 2026-08-13

data: SEG-4 用户复核改判 40 条 + glossary v15（润色轨的第一个版本）

- 变更：7 个路径；glossary 3、pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0703 · 95e5d39 · 2026-08-13

docs: P4 SEG-5 点火 handoff（seg5-s6-s7f，1505 行/4 会话）

- 变更：3 个路径；docs 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0704 · 314502c · 2026-08-13

data: SEG-5 双通道候选入仓——1441×2 行零判死，队列 150 条

- 变更：40 个路径；pilot 40
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0705 · 68cde8d · 2026-08-13

data: SEG-5 段末裁决落地——150 条裁决、150 条 patch 清关

- 变更：6 个路径；config 1、pilot 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg5-s6-s7f.yaml`

## 0706 · e913485 · 2026-08-13

feat: polish_bench 通道评测工具 + SEG-5 台账建议加 kimi-k2.6 为第三条通道

- 变更：3 个路径；pilot 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_bench.py`
- 相关实现/计划变更：A `tools/polish_bench.py`

## 0707 · e5b112b · 2026-08-14

feat: glossary v16 + polish.md §9(b) + polish_lint 检测器

- 变更：5 个路径；glossary 3、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/polish_lint.py`
- 相关实现/计划变更：A `tools/polish_lint.py`

## 0708 · fed2d40 · 2026-08-14

data: SEG-5 用户复核落地——35 条改判 + 21 行全库清扫

- 变更：6 个路径；config 2、pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg2-s3.yaml`、M `config/ayano_qa/seg5-s6-s7f.yaml`

## 0709 · 5f63e2e · 2026-08-14

fix: rulings 承接重复计入 + P4 SEG-6 点火 handoff（新增第三条通道 kimi-k2.6）

- 变更：6 个路径；docs 1、pilot 2、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/check_ui_terms.py`、M `tools/polish_setup.py`

## 0710 · 85d0bb9 · 2026-08-14

data: SEG-6 三通道候选入仓——1168×3 行零判死，队列 120 条

- 变更：47 个路径；pilot 47
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0711 · 5507afd · 2026-08-14

data: SEG-6 段末裁决落地——120 条裁决、93 条 patch 清关

- 变更：6 个路径；config 1、pilot 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg6-s8-e1.yaml`

## 0712 · f3ff699 · 2026-08-14

docs: gemini-3.7-flash 探针第四轮——质量结论翻转，建议改为「值得适配」

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0713 · 19e9102 · 2026-08-14

docs: agy CLI 通道对接 handoff（供独立开发会话）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0714 · 85e5d3d · 2026-08-14

feat: agy CLI 通道客户端 + 彩野测试通道开关

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/agy_client.py`
- 相关实现/计划变更：A `tools/agy_client.py`、M `tools/ayano_test.py`

## 0715 · c93956c · 2026-08-14

docs: agy 通道对接结论 + probe 文档结论修正

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0716 · 2864644 · 2026-08-14

merge: agy CLI 通道对接（feat/agy-cli-channel）

- 变更：6 个路径；docs 2、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/agy_client.py`
- 相关实现/计划变更：A `tools/agy_client.py`、M `tools/ayano_test.py`

## 0717 · 95e5f91 · 2026-08-14

docs: 重大更正——agy 通道会读本地仓库，此前全部质量结论作废

- 变更：4 个路径；docs 3、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_bench.py`

## 0718 · bbc90a6 · 2026-08-16

data: SEG-6 用户复核落地——42 条改判 + 镜像句连带对齐

- 变更：5 个路径；config 1、pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg6-s8-e1.yaml`

## 0719 · 5bbddb7 · 2026-08-16

data: SEG-6 三处最终确认——4010 笔误订正、4216 维持用户版、4065 放行 W3

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0720 · 40caf82 · 2026-08-16

feat: polish_check --bare-full（W4 的记号盲区补扫）+ P4 SEG-7 点火 handoff

- 变更：8 个路径；docs 3、pilot 3、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_check.py`

## 0721 · 3e833b2 · 2026-08-16

data: SEG-7 候选入仓——双通道 1268×2，kimi-k2.6 整体作废

- 变更：33 个路径；pilot 33
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0722 · 380a577 · 2026-08-16

data: SEG-7 段末裁决落地 + glossary v17 —— **正文轨全段完成**

- 变更：9 个路径；config 1、glossary 2、pilot 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg7-e2.yaml`

## 0723 · 8951daf · 2026-08-16

data: SEG-7 用户复核落地 + W3 校准 + glossary v18 —— 正文轨收官

- 变更：11 个路径；config 1、glossary 3、pilot 4、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`、M `tools/check_batch.py`、M `tools/polish_bench.py`

## 0724 · 908854f · 2026-08-19

feat: mine_dump.py——P5 预研·全作通读语料编织工具

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/mine_dump.py`
- 相关实现/计划变更：A `tools/mine_dump.py`

## 0725 · d6184ce · 2026-08-19

docs: P5 预研·全作通读 pattern 报告——16693 行三层痕迹通读的合并结论

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0726 · f47528c · 2026-08-19

docs: P5 裁定第一批落档——呐/小さく/姿/情報/物語动词/C1 + yuichi 禁则修订

- 变更：2 个路径；docs 1、glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0727 · ab0d640 · 2026-08-19

docs: P5 裁定第二批落档——密度规则全套/感叹词表升格/引号语用派/数字口径/カタカナ先生/sakura小写/呟く三分

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0728 · 5d8a7b6 · 2026-08-19

feat: polish.md P5 改版——守门三问前置 + §11-§18 新条款 + 八节 P5 补块

- 变更：1 个路径；glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0729 · 10c72e1 · 2026-08-19

feat: glossary v19——P5 修订窗口宪章（三项修订+感叹词总表+已裁词族+skeleton 召回令）

- 变更：3 个路径；glossary 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0730 · 89331b8 · 2026-08-19

data: P5 修订窗口正文批量落地——C1 罗马音化 4828 行 + C2/C3/词族 370 行

- 变更：3 个路径；data 1、glossary 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0731 · 03643df · 2026-08-19

data: skeleton v19 召回——anchors/cards.zh 罗马音化 + 天象馆连动（skeleton-v2）

- 变更：7 个路径；skeleton 7
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0732 · 63bf0d3 · 2026-08-19

data: P5 修订窗口收尾——题库 7 份同步 + bake_scene 夹具随实测更新 + 执行台账

- 变更：9 个路径；config 7、docs 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`、M `config/ayano_qa/seg2-s3.yaml`、M `config/ayano_qa/seg3-s4.yaml`、M `config/ayano_qa/seg4-s3tail-s5.yaml`、M `config/ayano_qa/seg5-s6-s7f.yaml`、M `config/ayano_qa/seg6-s8-e1.yaml`、M `config/ayano_qa/seg7-e2.yaml`

## 0733 · d33a103 · 2026-08-19

data: extra 衍生文本 zh/note 侧罗马音化同步（15 行）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0734 · 5b50db7 · 2026-08-19

docs: 修订窗口台账——extra 同步项结案

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0735 · 80e0ccf · 2026-08-19

test: bake_plot 金标随 v19 实测更新——两行卡 70→65、卡 115/170 descender +1

- 变更：1 个路径；tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0736 · 18333c2 · 2026-08-19

docs: P5 任务书与派发设计定稿草案——输出契约 v2（1-3 候选）+ 通道矩阵（双正式+三测试影子批）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/ops/p5-polish-design.md`
- 新增工装入口/模块：无

## 0737 · 911d36d · 2026-08-19

docs: P5 设计定稿——四决策点拍板（八段沿用/fable high/autoclear 全关/p5seg0-s1 影子批）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0738 · ebd225f · 2026-08-19

feat: polish_ingest 契约 v2——alts 备选候选 + noop 标记（P5 §三）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_ingest.py`

## 0739 · 3023707 · 2026-08-19

feat: polish_triage 契约 v2——queue.md 渲染编号备选 + noop 透传

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_triage.py`

## 0740 · ad8b3df · 2026-08-19

feat: polish_commit 契约 v2——chosen_alt 采纳路径（越界/坏 ruby 拒收，prov 留痕）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_commit.py`

## 0741 · 10fae32 · 2026-08-19

feat: polish_check --human-twins——人改孪生传播扫描（jp 面+bare 面，方向性报警）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_check.py`

## 0742 · 41d6f8a · 2026-08-19

feat: polish_context P5 元素——三问/两遍读/豁免提醒入任务说明，alts 入输出契约

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0743 · 1aaa7eb · 2026-08-19

feat: P5 段别名机制——p5segN-… 剥前缀复用 P4 段表行（段表分区闸不破）

- 变更：4 个路径；tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ayano_test.py`、M `tools/polish_setup.py`、M `tools/polishlib.py`

## 0744 · dd6234f · 2026-08-19

feat: P5 终稿轮锁口径——硬锁空、人裁 patch 降软锁（p4_human）、机械 recall 不锁

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_setup.py`

## 0745 · f33b799 · 2026-08-19

docs: P5 SEG-0 点火 handoff + p5seg0 冻结产物（manifest/plan）

- 变更：3 个路径；docs 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0746 · a579eb2 · 2026-08-19

fix: 6118 对齐精确孪生 15832——v19 孪生修复引入的劈叉

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0747 · 2e6db49 · 2026-08-19

docs: P5 测试通道影子批评估——glm-5.2/5.3 建议进正式矩阵，opus46 派发形态差异重大发现

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0748 · 2f5207e · 2026-08-19

feat: 冻结面漂移体检 --lane-drift + queue.md 漂移警示

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_check.py`、M `tools/polish_triage.py`

## 0749 · 857ae44 · 2026-08-19

data: p5seg0 fable-wf 全量候选入仓（4282 行，判死 0，hard 0）

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0750 · b526e6c · 2026-08-19

docs: P5 五通道正式矩阵定案 + SEG-0 点火实况（含队列规模实测与漂移处置）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0751 · f7d1463 · 2026-08-19

feat: W5 『』保真闸——候选须随 opus 或随原文，落在两者之外即告警

- 变更：5 个路径；pilot 3、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_check.py`

## 0752 · e15635c · 2026-08-19

feat: 契约配平条款——守门三条不是「不确定就别动」的许可证，零改动批须附批末说明

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0753 · 0b4d291 · 2026-08-19

docs: P5 逐条裁决 Web UI 开发规格（供 subagent 实现）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/ops/p5-adjudicate-ui-spec.md`
- 新增工装入口/模块：无

## 0754 · 4acbdf1 · 2026-08-19

feat: P5 逐条裁决 Web UI（本地 http.server，只写 decisions.draft.jsonl）

- 变更：5 个路径；tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/adjudicate_server.py`、`tools/adjudicate_ui/app.js`、`tools/adjudicate_ui/index.html`
- 相关实现/计划变更：A `tools/adjudicate_server.py`、A `tools/adjudicate_ui/app.css`、A `tools/adjudicate_ui/app.js`、A `tools/adjudicate_ui/index.html`

## 0755 · 5720dcc · 2026-08-19

fix: 裁决 UI 的 verdict 词汇对齐生产——adopt/keep_opus/edit，不留映射层

- 变更：3 个路径；tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/adjudicate_server.py`、M `tools/adjudicate_ui/app.js`

## 0756 · 12722a9 · 2026-08-19

fix: 「采纳备选N」按钮丢 chosen_alt——第二条 else-if 永远够不着

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/adjudicate_ui/app.js`

## 0757 · aa84b4f · 2026-08-19

feat: 裁决 UI 支持「自选行」——队列之外的行也能就地改

- 变更：5 个路径；tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/adjudicate_server.py`、M `tools/adjudicate_ui/app.css`、M `tools/adjudicate_ui/app.js`、M `tools/adjudicate_ui/index.html`

## 0758 · 279cdee · 2026-08-19

data: p5seg0 四通道候选与闸产物入库

- 变更：10 个路径；pilot 10
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0759 · 954ef52 · 2026-08-19

data: glm-5.2 / glm-5.3 全段候选入库——p5seg0 五通道满覆盖

- 变更：6 个路径；pilot 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0760 · c7d8849 · 2026-08-19

data: 漂移体检复跑（含 glm 两通道候选）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0761 · 31c4cea · 2026-08-19

feat: 右栏显示敲定文本 + 编辑框回填上次内容 + 候选并列差分/成品两行

- 变更：4 个路径；tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/adjudicate_server.py`、M `tools/adjudicate_ui/app.css`、M `tools/adjudicate_ui/app.js`

## 0762 · 9ef0059 · 2026-08-20

data: P5 SEG-0 裁决落盘——472 条全裁，442 条 patch 清关

- 变更：9 个路径；config 1、pilot 6、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg3-s4.yaml`、M `tools/polish_commit.py`

## 0763 · cffcce7 · 2026-08-20

feat: ingest 保全批末说明（id:0）——不再随 dead 蒸发

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_ingest.py`

## 0764 · ce14233 · 2026-08-20

feat: 章节纪要加时效声明——手记是历史记录，不作现行口径

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0765 · f3d6034 · 2026-08-20

docs: v19 三项修订漏网扫描结论——366 行候选压到 36 行，真漏网 1 处

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0766 · b1322c5 · 2026-08-20

data: P5 SEG-1 冻结与三通道候选入库（glm-5.3 会话3 重跑中）

- 变更：17 个路径；pilot 17
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0767 · 5dae2e7 · 2026-08-20

data: SEG-1 glm-5.3 会话3 重跑入库——四通道满覆盖，裁决队列 297

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0768 · 7e3ea4f · 2026-08-20

feat: alts 触发例具体化——四类真实案例取代抽象名目

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0769 · f382e35 · 2026-08-20

fix: jp_tail 契约补第 4 条——行尾闭合引号算一个字符

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0770 · 7ed5bfe · 2026-08-20

data: SEG-1 ds-flash 入库——五通道满编

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0771 · a1d673e · 2026-08-20

fix: polish_commit 支持改判撤回（同 id 取最后一条 + keep 撤已落 patch）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_commit.py`

## 0772 · add4788 · 2026-08-20

data: P5 SEG-1 裁决落库（248 条 patch）+ SEG-0 六条撤回追回

- 变更：11 个路径；config 2、pilot 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg1-s2.yaml`、M `config/qa_quote_suppressions.yaml`

## 0773 · 528424d · 2026-08-21

docs: P5 SEG-1 段末待裁定开放项（W4 27 条 + 三个口径项）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0774 · 5770105 · 2026-08-21

data: P5 SEG-1 段末用户裁定落地（A3/D11-D13/E1/E3，15 条 patch）

- 变更：2 个路径；docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0775 · 9550010 · 2026-08-21

data: P5 SEG-1 段末第二批裁定落地（26 条 patch，段末闸收尾）

- 变更：5 个路径；config 1、docs 1、pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg4-s3tail-s5.yaml`

## 0776 · f0007c5 · 2026-08-21

data: P5 SEG-2（p5seg2-s3）冻结 + SEG-0/1 段末裁决纪要入 rulings 链

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0777 · b0b29cb · 2026-08-21

fix: prompt 结尾补换行——最后一个批的输出文件名会被整行吞掉

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_context.py`

## 0778 · ae71244 · 2026-08-21

data: P5 SEG-2 五通道满编入仓 + 裁决队列（132 条）

- 变更：163 个路径；pilot 163
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0779 · 167e6fc · 2026-08-23

fix: 两处静默写错的口子——plan.json 溯源被覆盖 / 撤回 no-op 假警

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/polish_commit.py`、M `tools/polish_context.py`

## 0780 · 9c8cf9d · 2026-08-23

data: P5 SEG-2 裁决落库（118 条 patch）+ 段末闸收尾

- 变更：12 个路径；config 2、docs 1、pilot 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg2-s3.yaml`、M `config/qa_quote_suppressions.yaml`

## 0781 · 5ba25ec · 2026-08-23

data: P5 SEG-3（p5seg3-s4）冻结 + SEG-2 段末裁决纪要入 rulings 链

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0782 · 628e505 · 2026-08-23

fix: 把 v19 C2「小千秋废止」补进 style.md 与四份口调表（修订窗口漏执行）

- 变更：6 个路径；glossary 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0783 · 027fb0c · 2026-08-23

data: P5 SEG-3 四通道满编入仓 + 裁决队列（216 条）

- 变更：128 个路径；docs 1、pilot 127
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0784 · c4ba813 · 2026-08-24

data: P5 SEG-3 补入 fable-wf 会话 1（批 91–99，540 行），队列 216→220

- 变更：16 个路径；docs 1、pilot 15
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0785 · 6407971 · 2026-08-24

data: P5 SEG-3 fable-wf 补齐会话 2–5，五通道满编；队列 220→248

- 变更：25 个路径；docs 1、pilot 24
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0786 · 4a37685 · 2026-08-25

data: P5 SEG-3 裁决落库（207 条 patch）+ 段末闸收尾

- 变更：12 个路径；config 2、docs 1、pilot 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg3-s4.yaml`、M `config/qa_quote_suppressions.yaml`

## 0787 · fb28cfe · 2026-08-25

data: 12503 改用 glm-5.2 的最终稿（用户裁定）

- 变更：2 个路径；docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0788 · 77726d5 · 2026-08-25

docs: P5 复现句族合并裁定表（SEG-0~3 累积的 W4 开放项按族重组）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0789 · 9fa1b07 · 2026-08-25

feat: W4 复现句族豁免清单——按 (jp, forms) 匹配，新形照常报

- 变更：3 个路径；config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/w4_exemptions.yaml`、M `tools/polish_check.py`

## 0790 · 7f9921f · 2026-08-25

data: 复现句族裁定落地——C2/C5 两族统一（4 行），其余登记豁免

- 变更：4 个路径；pilot 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0791 · e33c7fe · 2026-08-25

data: P5 SEG-4（p5seg4-s3tail-s5）冻结 + SEG-3 段末补记入 rulings 链

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0792 · 2b723cf · 2026-08-25

data: P5 SEG-4 五通道满编入仓 + 裁决队列（155 条）

- 变更：130 个路径；docs 1、pilot 129
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0793 · 163b2d7 · 2026-08-25

feat: 通读 Web UI（tools/read_server.py）——按正典路线序看全书原文与现行译文

- 变更：5 个路径；tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/read_server.py`、`tools/read_ui/app.js`、`tools/read_ui/index.html`
- 相关实现/计划变更：A `tools/read_server.py`、A `tools/read_ui/app.css`、A `tools/read_ui/app.js`、A `tools/read_ui/index.html`

## 0794 · d66b8e9 · 2026-08-25

feat: 通读 UI 折叠 v19 C1 的片假名→罗马音机械改名

- 变更：4 个路径；tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/read_server.py`、M `tools/read_ui/app.css`、M `tools/read_ui/app.js`

## 0795 · d92c251 · 2026-08-26

data: P5 SEG-4 裁决落库（141 条 patch）

- 变更：12 个路径；config 2、pilot 10
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg4-s3tail-s5.yaml`、M `config/w4_exemptions.yaml`

## 0796 · 8d58f2a · 2026-08-26

data: 15051 回退「容易深信」→「容易相信」（用户裁定）+ SEG-4 待裁表

- 变更：2 个路径；docs 1、pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0797 · e1ec782 · 2026-08-26

data: SEG-4 段末 5 条待裁全部落地，四闸归零

- 变更：6 个路径；docs 1、pilot 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0798 · bbbf7a4 · 2026-08-26

data: P5 SEG-5（p5seg5-s6-s7f）冻结

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0799 · 8eda933 · 2026-08-26

docs: polish.md §18 的孪生台账已过期，标注为历史记录

- 变更：1 个路径；glossary 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0800 · 2ced6d1 · 2026-08-26

data: P5 SEG-5 五通道满编入仓 + 裁决队列（106 条）

- 变更：104 个路径；docs 1、pilot 103
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0801 · fb0be5e · 2026-08-26

feat: 通读 UI 支持人工修改——只写草稿，另设唯一清关口

- 变更：7 个路径；tests 2、tools 5
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/read_commit.py`
- 相关实现/计划变更：A `tools/read_commit.py`、M `tools/read_server.py`、M `tools/read_ui/app.css`、M `tools/read_ui/app.js`、M `tools/read_ui/index.html`

## 0802 · 52b4f81 · 2026-08-26

data: P5 SEG-5 裁决落库（99 条 patch）

- 变更：9 个路径；config 2、pilot 7
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg5-s6-s7f.yaml`、M `config/w4_exemptions.yaml`

## 0803 · f737ada · 2026-08-26

docs: P5 SEG-5 段末待裁（复现句族 4 条 + 全角数字清点结论）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0804 · 46cdd1b · 2026-08-26

data: SEG-5 段末裁定落地 + glossary v20（数字形制的两条细化）

- 变更：6 个路径；config 1、docs 1、glossary 2、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg5-s6-s7f.yaml`

## 0805 · 31a8cbd · 2026-08-26

data: P5 SEG-6（p5seg6-s8-e1）冻结

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0806 · 7bd653f · 2026-08-27

data: P5 SEG-6（p5seg6-s8-e1）五通道入仓 + triage 队列 122 条

- 变更：85 个路径；docs 1、pilot 84
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0807 · a108021 · 2026-08-27

data: 补入 P5 SEG-0/1 的通道原始交卷（raw/、shadow/）

- 变更：322 个路径；pilot 322
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0808 · 928d153 · 2026-08-27

data: 存档通读 UI 的人工草稿（6082）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0809 · d11e4f2 · 2026-08-27

data: 补入 P5 SEG-5 冻结面的 rulings.md

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0810 · ac9cd97 · 2026-08-27

data: P5 SEG-6 裁决落盘 102 条 + 段末四闸收口

- 变更：11 个路径；config 2、pilot 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg6-s8-e1.yaml`、M `config/qa_quote_suppressions.yaml`

## 0811 · ddfb52f · 2026-08-27

data: C1 断名族收口（9719/14337）+ 4725 语义分层回改

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0812 · 38f5f71 · 2026-08-27

data: P5 SEG-7（p5seg7-e2）冻结

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0813 · c57dbda · 2026-08-27

data: P5 SEG-7（p5seg7-e2）五通道入仓 + triage 队列 70 条

- 变更：59 个路径；docs 1、pilot 58
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0814 · 1990199 · 2026-08-28

feat: UI 术语表自校准闸——evidence 反向运行了 9 天没人发现

- 变更：3 个路径；config 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/measure_ui_terms.py`
- 相关实现/计划变更：M `config/ui_terms.yaml`、A `tools/measure_ui_terms.py`

## 0815 · 297bf1c · 2026-08-28

data: select 按钮对齐 v19 罗马音化 + 193c「假货」回改

- 变更：3 个路径；data 2、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0816 · 95f6326 · 2026-08-28

docs: 烤字台账随 v19 重烤更新 + 四条既有裁决的追记

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0817 · b356004 · 2026-08-28

feat: 烤字字体按面可换——tools/ui_font.py

- 变更：9 个路径；docs 1、tests 1、tools 7
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/ui_font.py`
- 相关实现/计划变更：M `tools/bake_plot.py`、M `tools/bake_scene.py`、M `tools/bake_select.py`、M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_outline.py`、M `tools/measure_card.py`、A `tools/ui_font.py`

## 0818 · 2de5f23 · 2026-08-28

feat: s6s_110 座席写法对照片 + 台账补记换字体用法

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_select_seat_ab.py`
- 相关实现/计划变更：A `tools/bake_select_seat_ab.py`

## 0819 · 50c2b54 · 2026-08-28

feat: 烤字环境再开三个口——字重 / 产物目录 / 字号级联

- 变更：14 个路径；tests 1、tools 13
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_out.py`
- 相关实现/计划变更：M `tools/bake_card.py`、A `tools/bake_out.py`、M `tools/bake_plot.py`、M `tools/bake_scene.py`、M `tools/bake_scene_size_ab.py`、M `tools/bake_scene_size_ab2.py`、M `tools/bake_select.py`、M `tools/bake_select_map.py`、M `tools/bake_select_seat_ab.py`、M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_outline.py`、M `tools/measure_card.py`、M `tools/ui_font.py`

## 0820 · fc59d36 · 2026-08-28

feat: 思源黑体 SC 全五面试烤 + 逐面对照图

- 变更：3 个路径；docs 1、third_party 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_font_ab.py`
- 相关实现/计划变更：A `tools/bake_font_ab.py`

## 0821 · 6f30544 · 2026-08-28

fix: 卡面字色逐卡实测——原图的字不是黑的（裁决 C8）

- 变更：3 个路径；docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_card.py`

## 0822 · 2e8a42b · 2026-08-28

feat: 思源黑体 Medium 版 + 对照工具支持多版本并排

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_font_ab.py`

## 0823 · dae6a6b · 2026-08-28

feat: 字体定案（card/plot/scene/select = 思源黑体 Medium）+ 按墨迹居中

- 变更：16 个路径；config 1、docs 2、tests 7、tools 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `config/bake_fonts.yaml`、M `tools/bake_scene.py`、M `tools/bake_select.py`、M `tools/bake_select_map.py`、M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_outline.py`、M `tools/ui_font.py`

## 0824 · cbb6d1b · 2026-08-28

feat: sysgim 译文 schema 闸 + C 类原始语料落盘（21 行，待译）

- 变更：6 个路径；data 1、tests 2、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/check_sysgim_text.py`
- 相关实现/计划变更：M `tools/bake_sysgim_glow.py`、A `tools/check_sysgim_text.py`、M `tools/check_ui_terms.py`

## 0825 · c52e21e · 2026-08-28

data: sysgim C 类 4 张译文入库 + 段级对齐修复（裁决 Y15/Y16）

- 变更：6 个路径；config 1、data 1、docs 1、tests 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ui_terms.yaml`、M `tools/bake_sysgim_glow.py`

## 0826 · 241c1dd · 2026-08-28

docs: 五个从未清点的目录清点完毕——又翻出 60 余张含字图

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0827 · ee53588 · 2026-08-28

feat: event/op_* 原始语料落盘 + schema 闸改为全面共用

- 变更：4 个路径；data 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：R083 `tools/check_bake_text.py`、M `tools/check_ui_terms.py`

## 0828 · fadb61f · 2026-08-28

feat: event/op_* 烤字工具——段落盒 + `_b` 由虚化推导

- 变更：5 个路径；config 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_event_op.py`
- 相关实现/计划变更：M `config/bake_fonts.yaml`、A `tools/bake_event_op.py`、M `tools/ui_font.py`

## 0829 · e5e78d7 · 2026-08-28

data: 序章题词 event/op_* 译文入库（4 段 / 15 行）

- 变更：2 个路径；config 1、data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ui_terms.yaml`

## 0830 · 6a0ecd9 · 2026-08-28

fix: op 单行段被缩进两次（用户看图指出）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_event_op.py`

## 0831 · 5becddd · 2026-08-28

fix: op 段落改为复现原文块的**重心**，不是它的左缘（用户指出重心偏左）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_event_op.py`

## 0832 · ad3ed26 · 2026-08-28

feat: cutin 章节起止字幕卡 24 张（译文几乎全部已有据）+ 段落烤字核心抽出

- 变更：11 个路径；config 1、data 1、tests 3、tools 6
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_cutin_title.py`、`tools/bake_para_glow.py`
- 相关实现/计划变更：M `config/bake_fonts.yaml`、A `tools/bake_cutin_title.py`、M `tools/bake_event_op.py`、A `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`、M `tools/check_bake_text.py`、M `tools/ui_font.py`

## 0833 · 5ee00b6 · 2026-08-28

docs: 烤字工程交接（2026-08-28）——各面进度、剩余批次、工具与闸、方法教训

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0834 · 1d0d851 · 2026-08-28

feat: cutin 定字华文仿宋（F5–F7）+ ui_font 支持 TTC 子字体索引

- 变更：8 个路径；config 1、docs 3、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/bake_fonts.yaml`、M `tools/bake_font_ab.py`、M `tools/ui_font.py`

## 0835 · 66949ce · 2026-08-29

feat: cutin 加倾斜 0.10 + 字号 +1pt（F8–F10）；订正「原图是斜的」这个错判

- 变更：13 个路径；config 1、docs 3、tests 5、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/bake_fonts.yaml`、M `tools/bake_font_ab.py`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`、M `tools/ui_font.py`

## 0836 · b92dbba · 2026-08-29

data: P5 SEG-7 裁决落盘 62 条 + 弥留三连改定「盯→停→听」

- 变更：11 个路径；config 2、pilot 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg6-s8-e1.yaml`、M `config/ayano_qa/seg7-e2.yaml`

## 0837 · 7ec33e7 · 2026-08-29

data: P5 SEG-7 段末收尾——5967 回退、それは―― 入 W4 豁免

- 变更：5 个路径；config 2、pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg7-e2.yaml`、M `config/w4_exemptions.yaml`

## 0838 · 065d41d · 2026-08-29

data: 对白句末句号形制统一——去掉 6 行手打孤例，16337 保留

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0839 · 0872b29 · 2026-08-29

feat: 模式画面框 3 张烤字（music/graphic/memory 选择提示）

- 变更：6 个路径；data 1、tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_mode_frame.py`
- 相关实现/计划变更：A `tools/bake_mode_frame.py`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`、M `tools/check_bake_text.py`

## 0840 · b5be55d · 2026-08-29

data: extra 轨重新派生落盘——从 v14 拉齐到现行骨架（片假名 182→0）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0841 · 66aa405 · 2026-08-29

feat: 回想缩略图 14 个章节名（M1–M6）；修掉一处会让闸反着绿的判据

- 变更：8 个路径；data 1、docs 2、tests 3、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_memory_thumb.py`
- 相关实现/计划变更：A `tools/bake_memory_thumb.py`、M `tools/check_bake_text.py`

## 0842 · c77818c · 2026-08-29

feat: sysgim D 族 2 张（sys_5_d / sys_1_g）——保留面板、盒内替换

- 变更：5 个路径；data 1、tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_fill.py`、`tools/bake_panel.py`
- 相关实现/计划变更：A `tools/bake_fill.py`、A `tools/bake_panel.py`、M `tools/check_bake_text.py`

## 0843 · 7b4b897 · 2026-08-29

analysis: sysgim E 类版面测绘——它不是一族是三族

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0844 · e1fd752 · 2026-08-29

fix: D 族字号级联下限与字芯取样比例——都是被换字试烤照出来的

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_panel.py`

## 0845 · 4f0064d · 2026-08-29

fix: D 族字号改为按原文墨迹高分组统一，不再逐行各选

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_panel.py`

## 0846 · c73ef6f · 2026-08-29

feat: sysgim E 类 title_* 12 张的译文与盒就位；⚠ 小注仍有矩形切口未解

- 变更：4 个路径；data 1、docs 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_sysgim_title.py`
- 相关实现/计划变更：A `tools/bake_sysgim_title.py`、M `tools/check_bake_text.py`

## 0847 · d5877a2 · 2026-08-29

data: ambient 轨 56 行补译——全书译文首次 100% 覆盖

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0848 · 47a911b · 2026-08-29

data: P5 SEG-9（p5seg9-ambient）冻结

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0849 · 22abe5a · 2026-08-29

fix: title_* 小注字号偏大——锚错了高度，且级联下限卡住

- 变更：4 个路径；config 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ui_terms.yaml`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_title.py`

## 0850 · aa2b494 · 2026-08-29

fix: title_* 的盒改用精确青色范围——外扩把英文推进了盒里

- 变更：2 个路径；data 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0851 · c64ecf5 · 2026-08-29

data: P5 SEG-9（ambient 56 行）五通道入仓 + triage 队列 2 条

- 变更：23 个路径；pilot 23
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0852 · f4769dc · 2026-08-29

docs: 烤字工程交接（2026-08-29）——本轮完工四批、字体现状、卡住的那一步、十条方法教训

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0853 · 9b1bc77 · 2026-08-29

data: P5 SEG-9 裁决落盘 + 收官——全书 16749 行 100% 覆盖

- 变更：10 个路径；pilot 10
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0854 · 6924ac0 · 2026-08-29

fix: title_* 12 张改两步遮盖——英文晕半径实测只有 4.47px，上一轮的诊断是错的

- 变更：8 个路径；docs 3、tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_mask.py`
- 相关实现/计划变更：A `tools/bake_mask.py`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_title.py`

## 0855 · b4def3c · 2026-08-29

docs: 烤字交接（2026-08-29 第二轮）+ E 类剩余 5 张的实测测绘（原记录两处归属是错的）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0856 · 2c8dc7c · 2026-08-29

docs: タイムオーバー→时间耗尽（用户裁定）；bake_mask 泛化试过一版已回滚，记下三条查明的事

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0857 · aca04d8 · 2026-08-30

feat: E 类收尾五张完工——几何足迹遮盖 + 幽灵晕减法，不走上一轮回滚的泛化路

- 变更：9 个路径；data 1、docs 3、tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_sysgim_note.py`
- 相关实现/计划变更：M `tools/bake_mask.py`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`、A `tools/bake_sysgim_note.py`

## 0858 · e8e4e32 · 2026-08-30

fix: 用户反馈五条——面板幽灵清理改色度判据，12 系 alpha 与字号修复

- 变更：7 个路径；data 1、docs 3、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`、M `tools/bake_para_glow.py`

## 0859 · f9e8ac0 · 2026-08-30

fix: sys_2_a 汉字顶部被削平——保留组分软硬，加写带（E18）

- 变更：6 个路径；data 1、docs 3、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`

## 0860 · 7c07ca0 · 2026-08-30

fix: E 类五张对齐定稿——行级 ref_center/ref_right，面板短线改全角（E19）

- 变更：5 个路径；data 1、docs 2、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_para_glow.py`

## 0861 · c94d2ab · 2026-08-30

docs: 台账跟进 E 类完工——sysgim 54→59 已烤、待做清零；顺带清掉两处已被推翻的模型归属

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0862 · 2a708d7 · 2026-08-30

feat: sys_1_i 解烤——最后的暂缓清零，geo 两步法+红晕拉普斯拉重建（E20）

- 变更：9 个路径；data 2、docs 4、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`、M `tools/bake_para_glow.py`

## 0863 · 1cdc623 · 2026-08-30

fix: sys_1_i 用户反馈三条——行2/3 合并、亮弧 artifact、字体 A/B（E20′、E21/E21′）

- 变更：4 个路径；data 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_para_glow.py`

## 0864 · e1ea395 · 2026-08-30

feat: sys_1_i 用户反馈四轮迭代——填充梯度化、暗棕墨、行合并、字心 plateau（E20a–E20g）

- 变更：5 个路径；data 1、docs 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_glow.py`

## 0865 · 8c85f44 · 2026-08-30

fix: sys_1_i 填充终案——按行采样背景 ARGB 平填 + 合并行顶到原第二行（E20h）

- 变更：5 个路径；data 1、docs 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`、M `tools/bake_para_glow.py`

## 0866 · fe3ef12 · 2026-08-30

fix: sys_1_i 末轮三处——行1 底色实测为黑带、下边框保护收紧、行级 core_ratio_hi

- 变更：4 个路径；data 1、docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`

## 0867 · c05f3aa · 2026-08-30

fix: sys_12_c 回归根因——白芯判据缺无彩色约束（E20i）+ '>' 残留距离闸

- 变更：3 个路径；data 1、docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`

## 0868 · 3a0ed50 · 2026-08-30

docs: 8-30 第三轮 handoff——sysgim 收口状态、sysgim_note 机制、下一批 tut_* 入手

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0869 · 0de10da · 2026-08-30

fix: sys_1_i 后处理——消除晕尾 artifact 与旧文残影

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/fixup_sys_1_i.py`
- 相关实现/计划变更：A `tools/fixup_sys_1_i.py`

## 0870 · 322cfa1 · 2026-08-30

data: cutin/tut_* 译文数据——tut_1_a / tut_2_a-e / tut_4_b 共 13 条

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0871 · 694df47 · 2026-08-30

feat: cutin/tut_* 七张烤字——tut_1_a / tut_2_a-e / tut_4_b

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_cutin_tut.py`
- 相关实现/计划变更：A `tools/bake_cutin_tut.py`

## 0872 · 308bc47 · 2026-08-30

fix: cutin/tut_* 调色——晕改为实测环模型，顺带修出两处位置错

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_cutin_tut.py`

## 0873 · 4b1c622 · 2026-08-30

docs: 台账与交接补记 cutin/tut_* 七张（T1–T8）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0874 · b7ad210 · 2026-08-30

docs: 两项用户裁定——novel 出范围、sysgim 定霞鹜（F11）

- 变更：4 个路径；CLAUDE.md 1、config 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/bake_fonts.yaml`

## 0875 · b671f6b · 2026-08-30

docs: 更正——sysgim 五类早已全部收口，「E 类待测绘」是过期条目

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0876 · 12513b5 · 2026-08-30

docs: 更正（二）——misc 四目录早已完工；范围内烤字已全部收工

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0877 · 0f8724a · 2026-08-30

docs: graphic 范围复核已裁——graphic_01_a / memory_01_a 保留

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0878 · 518351f · 2026-08-30

data: glossary v21 + skeleton 召回——cards.zh 跨换行断名 3 处（skeleton-v3）

- 变更：2 个路径；glossary 1、skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0879 · 844f447 · 2026-08-30

data: 通读 UI 草稿清关 2 条（6082 / 9330）

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0880 · 10e19c2 · 2026-08-30

docs: 烤字台账追记——card 37/74 已随 skeleton-v3 重烤

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0881 · 037a181 · 2026-08-30

feat: 通读导出 tools/export_read.py——全书定稿按路线序摊成单文件

- 变更：3 个路径；CLAUDE.md 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/export_read.py`
- 相关实现/计划变更：A `tools/export_read.py`

## 0882 · 3dbaefb · 2026-08-30

data: ui_terms 证据串校准——サクラ / ユカリ 跟上 v21 召回

- 变更：1 个路径；config 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ui_terms.yaml`

## 0883 · 79a3c1e · 2026-08-31

data: 谢幕章 v1 统稿＋七轨谢幕卡征集件（不可再生，-f 保全）

- 变更：11 个路径；work 11
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0884 · 79167f2 · 2026-08-31

docs: 谢幕章演出设计 v1——s8f/e2f 语法调研与逐场素材对照

- 变更：1 个路径；work 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0885 · 688df33 · 2026-08-31

chore: 谢幕件迁至 docs/finale（脱离 gitignore 的 work/ 区）

- 变更：12 个路径；docs 12
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0886 · fb50a8c · 2026-08-31

feat: 谢幕卡烤字工具——bake_card 排版三件套薄复用（空白模板底+实测字色）

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_finale_cards.py`
- 相关实现/计划变更：A `tools/bake_finale_cards.py`

## 0887 · be192d2 · 2026-08-31

docs: 主菜单直达谢幕入口方案 v1——corpus/final 测绘（枚举表驱动，8 处改动+1 张新图）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0888 · c99740f · 2026-08-31

data: 谢幕感言（acknowledgement）——讲述者们执笔，切入段收录发起人递笔戏

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0889 · 892b46b · 2026-08-31

data: 谢幕章 v2——场景 0『递笔』编入（发起人 e2s 体例切入段，传递链闭合）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0890 · 1184652 · 2026-08-31

feat: 主菜单谢幕项 title_14_a——encore 字形移植+谢幕小注烤字（r 取 Prologue 同字号捐赠）

- 变更：4 个路径；docs 3、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_finale_menu.py`
- 相关实现/计划变更：A `tools/bake_finale_menu.py`

## 0891 · 4ae56a7 · 2026-08-31

feat: snr_finale.lua 谢幕章演出脚本初版（fin-0..50，vms 17300-17481，仿 s8f 结构）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0892 · ad26b49 · 2026-08-31

fix: title_14_a 亮态 r 下沉 2px 与光晕裁截——基线改逐字形实测、r 窗口保全头尾光晕

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_finale_menu.py`

## 0893 · 15b3b87 · 2026-08-31

feat: databin.py——DATA.BIN 资源包打包/解包（C++ second-novel-toolkit 的 Python 重写）

- 变更：4 个路径；.gitignore 1、CLAUDE.md 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/databin.py`
- 相关实现/计划变更：A `tools/databin.py`

## 0894 · 9410ce0 · 2026-08-31

docs: PPSSPP e2e 自动化可行性调研——WebSocket 调试器为主界面，mcp-ppsspp 与版本矩阵盘点

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0895 · 1968642 · 2026-08-31

feat: gimcodec.py——GIM 纹理编解码（gim↔png 双向 + 模板回填编码）

- 变更：3 个路径；CLAUDE.md 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/gimcodec.py`
- 相关实现/计划变更：A `tools/gimcodec.py`

## 0896 · d80084d · 2026-08-31

feat: PPSSPP e2e 本地环境搭建——master 双构建验收、WS 探针脚本、无 ISO 摸底归档

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/e2e/probe.py`
- 相关实现/计划变更：A `tools/e2e/probe.py`

## 0897 · cbaae50 · 2026-08-31

docs: TTF→PGF 字体转换调研——pgftool 补丁试产 17/9px 双尺寸全链路验证

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0898 · 3b248a1 · 2026-08-31

docs: UMD ISO 重打包调研——就地替换路线定案，UltraISO 失效机理与验证矩阵

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0899 · c7266c7 · 2026-08-31

feat: 模拟器 e2e 管线（tools/emu + tests/emu）——无 ISO 即全链路活体验证

- 变更：19 个路径；docs 2、pyproject.toml 1、tests 8、tools 7、uv.lock 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/__init__.py`、`tools/emu/client.py`、`tools/emu/fetch_testdata.sh`、`tools/emu/imgdiff.py`、`tools/emu/launcher.py`
- 相关实现/计划变更：A `tools/emu/README.md`、A `tools/emu/__init__.py`、A `tools/emu/client.py`、A `tools/emu/fetch_testdata.sh`、A `tools/emu/imgdiff.py`、A `tools/emu/launcher.py`、R100 `tools/emu/probe.py`

## 0900 · e5db453 · 2026-08-31

feat: 中文化测试盘管线贯通——译文注入/luac 回编/字体/烤字/回封/引导全链路

- 变更：8 个路径；docs 1、tests 1、tools 6
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/build_disc.py`、`tools/build_font.py`、`tools/emu/playthrough.py`、`tools/inject_lua.py`
- 相关实现/计划变更：A `tools/build_disc.py`、A `tools/build_font.py`、M `tools/emu/client.py`、M `tools/emu/imgdiff.py`、A `tools/emu/playthrough.py`、A `tools/inject_lua.py`

## 0901 · bd85aeb · 2026-08-31

feat: 测试引导脚本 + 槽1中文字体——ruby 机制实测定论

- 变更：3 个路径；tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/make_test_boot.py`
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/inject_lua.py`、A `tools/make_test_boot.py`

## 0902 · 2e49539 · 2026-08-31

feat: ruby 拼音注音落地——全角步进居中 + 声调整体放大

- 变更：3 个路径；docs 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_font.py`、M `tools/make_test_boot.py`

## 0903 · 502dc00 · 2026-08-31

refactor: 换反编译语料基座——lua_scripts ← pyluadec-refactor/corpus/final

- 变更：242 个路径；CLAUDE.md 1、data 2、docs 1、lua_scripts 229、pilot 2、tests 3、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/luac_norm.py`、`tools/migrate_base.py`
- 相关实现/计划变更：M `tools/build_ledger.py`、M `tools/inject_lua.py`、A `tools/luac_norm.py`、A `tools/migrate_base.py`

## 0904 · d319159 · 2026-08-31

docs: 迁移方法学缺口关闭——项目方确认旧基座只有字体与 s4 地图两处人工编辑

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0905 · 2b66484 · 2026-08-31

chore: 入库 LXGWWenKaiMono-Regular.ttf——ruby 槽字体源

- 变更：1 个路径；third_party 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0906 · c5d15de · 2026-08-31

fix: DAG 链适配新反编译基座——scene_meta/choice/cost/answers 四处静默降级修复

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_dag.py`

## 0907 · 9f0f7e7 · 2026-08-31

fix: select 链适配新反编译基座——derive_select 85/114、bake_select_map v0 表闸重建

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_select_map.py`、M `tools/derive_select.py`

## 0908 · 3420828 · 2026-08-31

analysis: 三件套提取器适配新基座并重跑产物

- 变更：7 个路径；analysis 4、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/extract_crd.py`、M `tools/extract_dag.py`、M `tools/extract_text.py`

## 0909 · 0b0788f · 2026-08-31

fix: sysgim 发光字落位精确化 + 段内统一字号——autosave 严格左对齐

- 变更：4 个路径；data 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_sysgim_glow.py`、M `tools/check_bake_text.py`、M `tools/make_test_boot.py`

## 0910 · ba4abcc · 2026-09-01

feat: 测试引导新增 card 模式——直入任意卡片谜题并短路递卡

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/make_test_boot.py`

## 0911 · dd35cc6 · 2026-09-01

feat: 测试引导新增 cutin 模式——章节首尾 24 张一次过目，含真实 CG 底

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/make_test_boot.py`

## 0912 · 10006bd · 2026-09-01

fix: select 两处译文修订 + 测试引导新增 mainmenu/choices/map 三模式

- 变更：4 个路径；data 2、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/make_test_boot.py`

## 0913 · c8e33ec · 2026-09-01

fix: sysgim 面按张分字体——大字号改思源黑体 Medium，极小字号小注留霞鹜

- 变更：5 个路径；config 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/bake_fonts.yaml`、M `tools/bake_sysgim_glow.py`、M `tools/bake_sysgim_outline.py`、M `tools/make_test_boot.py`、M `tools/ui_font.py`

## 0914 · 15af831 · 2026-09-01

fix: sys_22_e 语音开关七名整张重烤——补罗马音、统一晕、修盒越界

- 变更：2 个路径；data 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0915 · ab3e66e · 2026-09-01

fix: cutin/event 填充增益回 2.2——按面解析重构的附带损伤

- 变更：2 个路径；config 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/bake_fonts.yaml`

## 0916 · 67ffbfb · 2026-09-01

fix: 主菜单 12 项小注只擦不写——抹掉日文，只留英文大词

- 变更：9 个路径；config 1、data 1、docs 3、tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/bake_fonts.yaml`、M `tools/bake_para_glow.py`、M `tools/bake_sysgim_title.py`、M `tools/check_bake_text.py`

## 0917 · 70d9fc6 · 2026-09-01

fix: 孪生态重建——清掉压在英文发光里擦不掉的那几粒旧墨

- 变更：7 个路径；data 1、docs 2、tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_mask.py`、M `tools/bake_para_glow.py`、M `tools/check_bake_text.py`

## 0918 · 5df1ed5 · 2026-09-01

feat: umdiso.py + build_disc iso 阶段——实机盘就地替换产出

- 变更：5 个路径；CLAUDE.md 1、docs 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/umdiso.py`
- 相关实现/计划变更：M `tools/build_disc.py`、A `tools/umdiso.py`

## 0919 · fd20b91 · 2026-09-01

feat: 志愿者试玩盘——剔除测试改动 + 出盘前的发布闸

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`

## 0920 · ff04cbd · 2026-09-01

fix: 补上 tr_line 黑洞——51 行从未进账本，含 41 条玩家可见的漏译

- 变更：10 个路径；data 2、docs 1、pilot 1、tests 3、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_ledger.py`、M `tools/inject_lua.py`、M `tools/land_extra.py`

## 0921 · 1b26821 · 2026-09-01

data: P5·p5tr-extra 校对轮——extra 轨补译 40 行首轮润色与裁决

- 变更：9 个路径；data 1、docs 2、pilot 5、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/land_extra.py`

## 0922 · 1a60b77 · 2026-09-01

feat: 语音选择界面烤字——补漏的 6 张素材

- 变更：4 个路径；data 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_event_voice.py`、`tools/bake_select_voice.py`
- 相关实现/计划变更：A `tools/bake_event_voice.py`、A `tools/bake_select_voice.py`、M `tools/build_disc.py`

## 0923 · 69e1e46 · 2026-09-01

docs: 谢幕章演出实施 handoff——交接实施/进包/实机验证线

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0924 · 6995e42 · 2026-09-01

feat: title_14_a 无小注版定稿——encore 纯英文大词 + 117×68 模板同尺寸

- 变更：4 个路径；docs 3、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_finale_menu.py`

## 0925 · 3aae929 · 2026-09-01

fix: snr_finale fin_40 白入切图改回原作语法——layerLoad+comEffectWhiteIn+wait

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0926 · 6216d0d · 2026-09-01

feat: make_test_boot 支持 fin- 场景直入——谢幕章 O(1) 抵达任意场景

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/make_test_boot.py`

## 0927 · 47cf5ab · 2026-09-01

feat: build_disc 集成谢幕章新成员——lua 钩子 + NEW_GIM_SOURCES 面

- 变更：3 个路径；tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_finale_cards.py`、M `tools/bake_finale_menu.py`、M `tools/build_disc.py`

## 0928 · a9533a0 · 2026-09-02

feat: 主菜单谢幕直达项——卡 144 门控的 encore 入口（8 处改动照 plan 落地）

- 变更：2 个路径；lua_scripts 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0929 · 653b0ad · 2026-09-02

fix: encore 菜单图改绘制期直载——层 198 常驻方案证伪并回退

- 变更：2 个路径；lua_scripts 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0930 · 918f6aa · 2026-09-02

docs: 谢幕章实施台账 + CLAUDE.md 增补 + plan 勘误

- 变更：4 个路径；CLAUDE.md 1、docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0931 · d926c0d · 2026-09-02

fix: 通读 UI 的"已改动"不再算纯罗马音化——补上 d66b8e9 只做了一半的那一半

- 变更：4 个路径；tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/read_server.py`、M `tools/read_ui/app.css`、M `tools/read_ui/app.js`

## 0932 · bca73f9 · 2026-09-02

docs: 中文盘构建管线规范化设计稿——基座 + 层 + 剖面（路线 A）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`

## 0933 · 9ef5a7d · 2026-09-02

docs: 设计稿补记热修中实测到的两处证据——build_font 缺 fonttools 依赖、测试盘覆盖 build/dist/DATA.BIN

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/specs/2026-09-02-disc-layers-pipeline-design.md`

## 0934 · 7324804 · 2026-09-02

docs: 管线规范化实施计划——10 个任务 60 步，两道逐字节硬闸

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-09-02-disc-layers-pipeline.md`

## 0935 · 8acd288 · 2026-09-02

feat: 叠加操作引擎——五种锚定文本操作 + count/occurrence 硬断言

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/layers.py`
- 相关实现/计划变更：A `tools/layers.py`

## 0936 · e3bfdbb · 2026-09-03

docs: 计划勘误——count 守卫补进 Task 1 代码，测试基数说明订正

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-09-02-disc-layers-pipeline.md`

## 0937 · 0660e54 · 2026-09-03

fix: select_indices 必须挡住 count<1 防静默 no-op

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0938 · e75590f · 2026-09-03

feat: 清单与 id 登记的加载与校验

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0939 · f595142 · 2026-09-03

docs: 计划勘误——Task 2 的 check_ids 代码块加执行期修正说明

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `docs/superpowers/plans/2026-09-02-disc-layers-pipeline.md`

## 0940 · 0fb92d8 · 2026-09-03

fix: check_ids 补上名不副实的 test 层豁免，dead-code 嫌疑处补防线注释

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0941 · 8c45f38 · 2026-09-03

fix: 修正 check_ids 二道防线注释的自相矛盾，补 vms_ids.toml 的 profile 校验

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0942 · e95da15 · 2026-09-03

feat: 字集抽取与构建取证

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0943 · 75fc980 · 2026-09-03

docs: SDD 执行台账入库（Task 1-3 简报与报告 + progress 裁决记录）

- 变更：8 个路径；.superpowers 8
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0944 · 979ab4a · 2026-09-03

fix: provenance 补基座树哈希与工具路径环境变量覆盖

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0945 · 787e563 · 2026-09-03

docs: Task 3 报告追加 fix round（provenance 两处 Important 发现的修复记录）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0946 · af552fe · 2026-09-03

fix: provenance 空串环境变量覆盖导致 IsADirectoryError

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/layers.py`

## 0947 · 0f69caf · 2026-09-03

docs: Task 3 报告追加 fix round 2（空串环境变量崩溃 + _sha256 守卫收紧的理由）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0948 · f9b4b40 · 2026-09-03

refactor: 基座纯净化——lua_scripts 回到与原字节码等价，改动全部成层

- 变更：16 个路径；layers 7、lua_scripts 2、pyproject.toml 1、tests 2、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/layers.py`、M `tools/luac_norm.py`、M `tools/migrate_base.py`

## 0949 · a054ac5 · 2026-09-03

fix: 硬化 --compare-compiled 闸 + 更正 fonts why + 钉住 op4 落点 + 迁移期 guard

- 变更：5 个路径；layers 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/layers.py`

## 0950 · f450584 · 2026-09-03

refactor: inject_lua 收缩为纯注入——字体改写与编译各归其位

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/inject_lua.py`

## 0951 · 834a438 · 2026-09-03

refactor: build_font 改为按给定字集构建 + fonttools 入依赖

- 变更：5 个路径；layers 1、pyproject.toml 1、tests 1、tools 1、uv.lock 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_font.py`

## 0952 · 5b6cb75 · 2026-09-03

docs: Task 6 实施报告入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0953 · 61863ed · 2026-09-03

docs: SDD 台账补齐（Task 4-6 简报与报告 + progress 至 Task 6 的裁决）

- 变更：5 个路径；.superpowers 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0954 · 8c39932 · 2026-09-03

fix: build_font 字集校验改按内容而非字节数——堵住 review 抓到的两个漏网案例

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_font.py`

## 0955 · 3ae73b0 · 2026-09-03

docs: Task 6 fix round 1 报告追加

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0956 · 0319e66 · 2026-09-03

refactor: make_test_boot 改为层生成器 testboot.py

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：R056 `tools/testboot.py`

## 0957 · f8241f1 · 2026-09-03

docs: Task 7 实施报告入库

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0958 · d46669f · 2026-09-03

fix: testboot 生成器补 4 项 review 发现——结构化告警/清空产物目录/count 回归测试/覆盖穷尽

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/testboot.py`

## 0959 · 73f609f · 2026-09-03

docs: Task 7 fix round 1 报告追加

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0960 · 03fabf3 · 2026-09-03

feat: build_disc 剖面化——release/test 各自独立输出树 + 依赖建模

- 变更：7 个路径；.superpowers 2、tests 2、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/layers.py`、M `tools/testboot.py`

## 0961 · 5e1adde · 2026-09-03

fix: release 闸补五处"看着过了、其实没锁住"的漏洞

- 变更：4 个路径；.superpowers 2、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`

## 0962 · d5a4508 · 2026-09-03

docs: SDD 台账补齐至 Task 8（含五处发布闸加固的裁决与两条 caveat）

- 变更：5 个路径；.superpowers 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0963 · 9863be5 · 2026-09-03

test: 模拟器复验矩阵通过 + 驾驶脚本收纳入库

- 变更：10 个路径；.superpowers 1、docs 1、tools 8
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/_common.py`、`tools/emu/drives/finale_full.py`、`tools/emu/drives/glyph.py`、`tools/emu/drives/library.py`、`tools/emu/drives/menu.py`、`tools/emu/drives/no_card144.py`、`tools/emu/drives/release_iso.py`
- 相关实现/计划变更：A `tools/emu/drives/README.md`、A `tools/emu/drives/_common.py`、A `tools/emu/drives/finale_full.py`、A `tools/emu/drives/glyph.py`、A `tools/emu/drives/library.py`、A `tools/emu/drives/menu.py`、A `tools/emu/drives/no_card144.py`、A `tools/emu/drives/release_iso.py`

## 0964 · 5ae9460 · 2026-09-03

docs: 管线文档收口——disc-pipeline.md 成为唯一现行说明

- 变更：9 个路径；.superpowers 1、CLAUDE.md 1、docs 7
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0965 · c1fb9b8 · 2026-09-03

docs: SDD 台账收至 Task 10 完成（含两条合并前应修候选）

- 变更：1 个路径；.superpowers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0966 · 9939b1d · 2026-09-03

fix: 收口整分支评审四条 Important + 散文漂移（disc-layers-pipeline）

- 变更：9 个路径；docs 1、tests 3、tools 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/emu/drives/release_iso.py`、M `tools/emu/playthrough.py`、M `tools/layers.py`、M `tools/migrate_base.py`

## 0967 · 97e08fa · 2026-09-03

docs: SDD 台账收官——最终评审、fix 波与 re-review 记录

- 变更：2 个路径；.superpowers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0968 · f7fbc96 · 2026-09-04

docs: EBOOT 逆向——消息窗禁则表与定宽网格排版规则记录

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0969 · 14392be · 2026-09-04

feat: tools/pgf_inspect.py——PGF 头部与字形量度检视（纯 stdlib）

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/pgf_inspect.py`
- 相关实现/计划变更：A `tools/pgf_inspect.py`

## 0970 · 27cfebd · 2026-09-04

docs: EBOOT 逆向补记 ruby 语法、字体槽 1 落点公式与 PGF 量度对照

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0971 · 146acd7 · 2026-09-04

docs: ruby 使用清点与半角等宽 ruby 算式补丁（含 Allegrex 无 mul 教训）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0972 · bdf6e14 · 2026-09-04

docs: ruby 最终方案——整数步进、单位计数、不跳过空格三段补丁（撤回 ÷4 算式）

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0973 · d816991 · 2026-09-04

feat: EBOOT 补丁层——tools/eboot_patch.py + layers/eboot/{kinsoku,ruby-p5}.toml + manifest [eboot] + check 闸

- 变更：6 个路径；layers 3、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/eboot_patch.py`
- 相关实现/计划变更：A `tools/eboot_patch.py`、M `tools/layers.py`

## 0974 · 0f24a77 · 2026-09-04

feat: build_disc 增加 eboot 阶段——补丁 EBOOT 覆入 game/、iso 断言④重算核对、provenance 记哈希

- 变更：3 个路径；tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/eboot_patch.py`

## 0975 · 8b53db2 · 2026-09-04

feat: ruby 字体改 5px 整数步进（配 EBOOT ruby-p5 层）+ 字体配方戳强制重建 + widen 测试

- 变更：3 个路径；tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/build_font.py`

## 0976 · c5cc29a · 2026-09-04

docs: 管线文档与 CLAUDE.md 收入 eboot 补丁层与 eboot 阶段、两道新闸

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0977 · 062325a · 2026-09-04

fix: EBOOT 补丁层支持文件偏移补丁，ruby-p5 层中和 a4f8 的 R_MIPS_26 重定位；探针页 K1–K4/R1 与逐页驾驶脚本

- 变更：8 个路径；CLAUDE.md 1、docs 1、layers 1、tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/font_probe.py`
- 相关实现/计划变更：M `tools/eboot_patch.py`、A `tools/emu/drives/font_probe.py`、M `tools/layers.py`、M `tools/testboot.py`

## 0978 · aa3582d · 2026-09-04

fix: ruby-p5 层 C 段改为「空格跳过但笔位推进 5px」（空格走字形路径会触发 0 字节分配回调中断整串）；模拟器复验通过

- 变更：3 个路径；docs 1、layers 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0979 · 895754c · 2026-09-04

feat: 消息窗排版校验器 tools/msg_layout_check.py——按引擎规则逐格模拟，挂入 layers.py check 与 lua 阶段

- 变更：8 个路径；CLAUDE.md 1、docs 2、tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/msg_layout_check.py`
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/inject_lua.py`、M `tools/layers.py`、A `tools/msg_layout_check.py`

## 0980 · c630bef · 2026-09-04

docs: 校验器首轮结果——43 条深悬挂的实际分布（――」/……」 为主）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0981 · 2932e0f · 2026-09-04

docs: EBOOT 逆向与补丁 runbook（给后续会话）+ tools/emu/drives/regtrace.py 断点/寄存器/单步驾驶脚本

- 变更：4 个路径；CLAUDE.md 1、docs 1、tools 2
- 新增规格/运行手册：`docs/ops/eboot-hacking-runbook.md`
- 新增工装入口/模块：`tools/emu/drives/regtrace.py`
- 相关实现/计划变更：M `tools/emu/drives/README.md`、A `tools/emu/drives/regtrace.py`

## 0982 · 4c6bd34 · 2026-09-05

feat: 存档容量闸——tools/pluto_size.py（按字节码估算 Pluto 线程 blob / 解析转储）+ save_probe.py 实测驾驶脚本 + build_disc members 阶段 release 超容量拒绝

- 变更：5 个路径；tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/save_probe.py`、`tools/pluto_size.py`
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/emu/drives/README.md`、A `tools/emu/drives/save_probe.py`、A `tools/pluto_size.py`

## 0983 · 8167317 · 2026-09-05

docs: EBOOT 存档机制研究记录（sceUtilitySavedata + Pluto 序列化、结构布局、容量与实测）；runbook 补 bss 地址偏差 0x6DA40 与存档管线地图

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0984 · 5306334 · 2026-09-05

feat: tools/eboot_relscan.py——按重定位表枚举 bss 引用（寄存器流回溯 lui）+ 存档结构搬迁干跑；研究记录补 bss 尾部对象地图、搬迁改字清单与内存预算

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/eboot_relscan.py`
- 相关实现/计划变更：A `tools/eboot_relscan.py`

## 0985 · 9b74e3c · 2026-09-05

fix: eboot_relscan 让 addu/or/move 传播 lui 值——补上 lui+addu 索引访问的两处结构引用（0x721C/0x753C，lui 0x7204/0x7518），搬迁清单 35→37 个 lui 字；研究记录记入教训

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/eboot_relscan.py`

## 0986 · 03af241 · 2026-09-05

feat: 存档扩容层 layers/eboot/savebuf.toml（test 剖面，线程区 +256 KiB；relscan move-plan 机械生成，测试从纯净 ELF 重推对账）+ 容量常数从层推导接进闸门 + build_disc --bloat 翻倍模式 + save_probe --patched

- 变更：8 个路径；layers 2、tests 1、tools 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/eboot_relscan.py`、M `tools/emu/drives/save_probe.py`、M `tools/pluto_size.py`、M `tools/testboot.py`

## 0987 · 8312bf2 · 2026-09-05

docs: 存档扩容层红/绿实测——翻倍 s1s 在原布局溢出 51686 B 砸坏封包句柄、扩容布局 64% 正常

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0988 · 94d7afb · 2026-09-05

feat: testboot movie 模式（开机循环播 OP）+ tools/emu/drives/mem_probe.py 用户内存预算快照探针

- 变更：2 个路径；tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/mem_probe.py`
- 相关实现/计划变更：A `tools/emu/drives/mem_probe.py`、M `tools/testboot.py`

## 0989 · 2e89e79 · 2026-09-05

feat: tools/emu/drives/save_roundtrip.py——存档→读档往返验证（按引擎对话框标志驱动，PPSSPP 对话框按键语义取自其源码；毒化旧结构区核对）

- 变更：2 个路径；tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/save_roundtrip.py`
- 相关实现/计划变更：M `tools/emu/drives/README.md`、A `tools/emu/drives/save_roundtrip.py`

## 0990 · c0feb1d · 2026-09-05

docs: 存档扩容层落地记录——往返验证结果、搬迁 bss 对象纪律（三源互证/位移取 0x10000 倍数/PPSSPP 对话框按键语义）、实机验证清单；CLAUDE.md 指针

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0991 · 2d2c522 · 2026-09-05

docs+fix: 扩容层下影片/回归实测（C 堆后移 716 KB、空隙 6715 KB；sceMp4 在 PPSSPP 未实现的注记）；mem_probe 异步解包修正

- 变更：2 个路径；docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/emu/drives/mem_probe.py`

## 0992 · 1d4d383 · 2026-09-06

data: 探索地图底栏 sel_map_0_a 两处提示译文（「请选择要前往的地点。」「当前位置」）+ geo 遮盖实测参数

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0993 · a99ca2d · 2026-09-06

feat: tools/bake_select_map_info.py——探索地图底栏 sel_map_0_a 补烤（几何足迹两步遮盖、整张 13px）+ 驾驶脚本 map.py

- 变更：6 个路径；tests 2、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_select_map_info.py`、`tools/emu/drives/map.py`
- 相关实现/计划变更：A `tools/bake_select_map_info.py`、M `tools/check_bake_text.py`、M `tools/emu/drives/README.md`、A `tools/emu/drives/map.py`

## 0994 · 0856a62 · 2026-09-06

docs: 裁决 L12 与进度台账——sel_map_0_a 补烤记录（措辞、几何足迹 vs 裁盒、13px 四档对照、PPSSPP 五页实测）

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0995 · f921c28 · 2026-09-07

analysis: tools/research/plot_plate——plot 缩略图「干净底板」重建研究脚本（配方解析/合成/色调拟合/普查/细化 + 两个模拟器驾驶）

- 变更：6 个路径；tools 6
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/research/plot_plate/plot_recon.py`、`tools/research/plot_plate/probe_drive.py`、`tools/research/plot_plate/refine.py`、`tools/research/plot_plate/survey.py`、`tools/research/plot_plate/walk_drive.py`
- 相关实现/计划变更：A `tools/research/plot_plate/README.md`、A `tools/research/plot_plate/plot_recon.py`、A `tools/research/plot_plate/probe_drive.py`、A `tools/research/plot_plate/refine.py`、A `tools/research/plot_plate/survey.py`、A `tools/research/plot_plate/walk_drive.py`

## 0996 · 0668dab · 2026-09-07

docs: plot 缩略图方案研究报告——色带缺陷根因（卡 7/42/86/161/170）、缩略图生成模型（0.5×直缩）、195 格重建普查、模拟器路线实测、A/B/C 三方案；裁决台账与进度加指针

- 变更：9 个路径；docs 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 0997 · ae4de5a · 2026-09-07

chore: 研究模块文档串改为现行产物路径

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/plot_recon.py`

## 0998 · af1443d · 2026-09-07

feat: bake_plot 色带行数按标题字数决定（裁决 P5）——修卡 7/42/86/161 第二行漏检与 170 半漏

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_plot.py`

## 0999 · a019094 · 2026-09-07

data: plot 缩略图逐卡底板配方 data/plot_plates.jsonl（195 行：single 85 / compose 66 / flat 42 / band 2）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1000 · 398dfa8 · 2026-09-07

feat: tools/bake_plot_plate.py——plot 缩略图干净底板重建烤字（方案 B，裁决 P6–P8）+ 配方生成器 + 时间轴驾驶

- 变更：6 个路径；tests 1、tools 5
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_plot_plate.py`、`tools/emu/drives/plot_timeline.py`、`tools/research/plot_plate/emit_plates.py`
- 相关实现/计划变更：A `tools/bake_plot_plate.py`、A `tools/emu/drives/plot_timeline.py`、A `tools/research/plot_plate/emit_plates.py`、A `tools/research/plot_plate/hunts.json`、M `tools/research/plot_plate/plot_recon.py`

## 1001 · 499945a · 2026-09-07

feat: build_disc 二值 alpha 的图改走 MEDIANCUT 量化（plot sheet 损耗 37→9）；testboot mainmenu 支持 --no-cards

- 变更：3 个路径；tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/testboot.py`

## 1002 · 4eb3682 · 2026-09-07

docs: plot 干净底板落地的裁决 P5–P8、进度台账、版面规格附录与研究报告附记

- 变更：4 个路径；docs 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1003 · 2c95352 · 2026-09-07

fix: testboot story_route 一直返回空路线（scene_meta 键带 scene_ 前缀）；plot_timeline 驾驶改为 Story/Fragment 各一段

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/testboot.py`

## 1004 · 46433a3 · 2026-09-07

docs: plot 底板游戏内时间轴实测截图与台账

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1005 · 64dcc0b · 2026-09-07

data: plot 配方按修正后的合成器重算（4 行 ≤0.12 微调）；研究 README 补 emit/hunts 入口

- 变更：2 个路径；data 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/README.md`

## 1006 · 6bbb307 · 2026-09-07

data: plot 配方——双立绘教室格 3/9/146–149 套用猎手偏移与空教室 bg（10 → 7.5–8.8）

- 变更：2 个路径；data 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/hunts.json`

## 1007 · 7bcc5f6 · 2026-09-07

data: plot 配方——探索地图格 20/74/156/169 底图下移 4 px 边缘延伸（10.4–10.9 → 5.7）

- 变更：2 个路径；data 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/hunts.json`

## 1008 · 77ca2b1 · 2026-09-07

data: plot 配方——整帧位移普查仅 16/69/70/83 四格获益 ≥1（其余无系统性偏移），一并采用

- 变更：2 个路径；data 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/hunts.json`

## 1009 · a37a5d2 · 2026-09-07

feat: bake_plot_plate 支持整帧裁切框（crop）与局部异物复核标记；猎手二轮配方入库（41/158/34/30/35/56/82/162）

- 变更：4 个路径；tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_plot_plate.py`、M `tools/research/plot_plate/emit_plates.py`、M `tools/research/plot_plate/hunts.json`

## 1010 · 4d4ef8d · 2026-09-07

data: plot 配方——猎手二轮并入，band 兜底归零（single 87 / compose 66 / flat 42）

- 变更：1 个路径；data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1011 · ee979fd · 2026-09-07

docs: plot 底板——猎手二轮战果与兜底归零写入裁决 P6–P8、进度台账与报告附记

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1012 · d9b70bd · 2026-09-07

data: plot 配方——复核带探针：11–14/65–67/146–149 立绘按画布中心缩放 0.86–0.98 再定位

- 变更：2 个路径；data 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/hunts.json`

## 1013 · 55bb2cf · 2026-09-07

docs: plot 底板复核带更新为 8 格

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1014 · 6ee4ef1 · 2026-09-07

feat: bake_plot_plate 增加宽掩膜（非墨迹全像素）复核判据；卡 146 去掉伪 cutin 层

- 变更：4 个路径；data 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_plot_plate.py`、M `tools/research/plot_plate/hunts.json`

## 1015 · 0c2d2d1 · 2026-09-07

docs: plot 底板裁决 P9（宽掩膜复核判据）与 P10（色调模型维持 round，暗化带假设证否）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1016 · 60b5ee3 · 2026-09-07

data: plot 配方按宽掩膜精修 11 格（2/52/53/92/103/163/164/166/167/168/178），复核带回到 8 格

- 变更：3 个路径；data 1、docs 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/hunts.json`

## 1017 · e44f400 · 2026-09-07

data: plot 配方——158 猎手三轮（底图下移 5px + 0.93 倍自身拷贝，9.4→7.9）、146/147 底图换 bg_6_a_0（8.0→4.4/4.7）；复核带 6 格

- 变更：4 个路径；data 1、docs 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/hunts.json`

## 1018 · c84c9cb · 2026-09-07

docs: 裁决 P12——12 种重采样方案实测，BILINEAR 最优且地板不可压

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1019 · 3624e87 · 2026-09-07

docs: plot 底板研究报告附记 3——通宵深挖的机制清单、证否的五条假设、最终 195 格人读拼图

- 变更：5 个路径；docs 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1020 · 475534d · 2026-09-07

docs: 记下卡 184 全素材专攻搜索确认现行配方即最优

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1021 · 18cc49d · 2026-09-07

docs: 裁决表 P9–P12 按编号排序

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1022 · a5fb04c · 2026-09-07

docs: plot 底板收尾验证——全量测试 1869 绿、发布盘出盘与开机、两条时间轴游戏内截图（最终配方）

- 变更：3 个路径；docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1023 · a7db1a7 · 2026-09-07

feat: plot 复核清单区分「机械命中」与「待人裁定」；6 张复核格按用户裁定标为 accepted（P13）

- 变更：5 个路径；data 1、docs 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_plot_plate.py`、M `tools/research/plot_plate/emit_plates.py`

## 1024 · ec5d4e8 · 2026-09-07

data: plot 配方按对抗性复核改正 26 处（裁决 P14）——过拟合的缩放、截断的搜索、凭空造出的天空

- 变更：4 个路径；data 1、docs 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/research/plot_plate/emit_plates.py`、M `tools/research/plot_plate/hunts.json`

## 1025 · 2ed1faf · 2026-09-07

docs: 刷新 195 格人读拼图（对抗性复核改正后）

- 变更：4 个路径；docs 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1026 · bd3cfc6 · 2026-09-07

docs: 研究报告附记 4——对抗性复核的三类真错误、两处挡下的改动、合成器审计结论

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1027 · 7c9b305 · 2026-09-07

docs: 复核后的复查——148/149 换对底图后缩放仍必要（审计那条结论是按旧底图量的）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1028 · 669e556 · 2026-09-08

data: 通读修改清关 9 条（read_commit）——15523 的『/TODO』占位暂留草稿未落

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1029 · b925ae8 · 2026-09-08

docs: 「孩子」系复审 + 卡 1 改题『有个女孩子来学校的故事』——裁定表与落地方案（待用户拍板）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1030 · 30de4d8 · 2026-09-08

data: skeleton 分体批文件与合并版对齐——v21 漏改分体的卡 37/74 body_zh 回写

- 变更：2 个路径；skeleton 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1031 · e44b0e6 · 2026-09-08

data: glossary v22 + skeleton 召回——卡 1 改题『有个女孩子来学校的故事』、あの子＝Sakura 族「那个女孩」（skeleton-v4）

- 变更：6 个路径；glossary 1、skeleton 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1032 · fc32aee · 2026-09-08

data: v22 召回落地——主轨 43 行 + extra 4 键 + 谢幕章 2 行 + 题库 3 处引文同步

- 变更：6 个路径；config 2、data 1、layers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg2-s3.yaml`、M `config/ayano_qa/seg3-s4.yaml`

## 1033 · d0a8f23 · 2026-09-08

docs: 「孩子」系复审裁定表补执行台账（v22 召回已落地，skeleton-v4）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1034 · 2e882ad · 2026-09-11

chore: .gitignore 的 assets 规则锚定到仓库根——不再误吞 docs/finale/assets/ 入库美术源

- 变更：1 个路径；.gitignore 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1035 · bf0f8bd · 2026-09-11

fix: 主菜单 encore 项左移 10 px 与主列墨迹中轴对齐（194→184）

- 变更：2 个路径；layers 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_finale_menu.py`

## 1036 · f414ff3 · 2026-09-11

feat: 谢幕章读完后标题题名换中文——finaleReadFlag 系统旗标 + title_01_c 新成员 + 两个叠加层

- 变更：10 个路径；docs 2、layers 4、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_finale_title.py`、`tools/emu/drives/title_logo.py`
- 相关实现/计划变更：A `tools/bake_finale_title.py`、A `tools/emu/drives/title_logo.py`

## 1037 · 1771671 · 2026-09-11

docs: 题名 logo 双态与 title_logo 驾驶脚本入 CLAUDE.md 谢幕段与 drives README

- 变更：2 个路径；CLAUDE.md 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/emu/drives/README.md`

## 1038 · fa12f68 · 2026-09-11

feat: 中文攻略生成工具——tools/build_guide.py（定译字典/附录表/选卡界面格位 swatch 生成 + typst 编译）、Typst 模板与附录、守门测试、runbook

- 变更：8 个路径；CLAUDE.md 1、docs 1、guide 4、tests 1、tools 1
- 新增规格/运行手册：`docs/ops/guide-runbook.md`
- 新增工装入口/模块：`tools/build_guide.py`
- 相关实现/计划变更：A `tools/build_guide.py`

## 1039 · 6d72d94 · 2026-09-11

docs: 中文攻略正文（序章至 EX2 全流程、完全收集）与生成产物、成品 PDF 落盘

- 变更：212 个路径；guide 212
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1040 · 38b064a · 2026-09-12

fix: 攻略递卡顺序改以 crd 脚本比较顺序为准并常驻校验（pdf/check/测试）；表格关闭两端对齐

- 变更：4 个路径；docs 1、guide 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_guide.py`

## 1041 · ca73875 · 2026-09-12

docs: 攻略修正 4 处多卡递卡顺序（对咒语的兴趣/谜题/出去玩的地方/田径部的传闻）并重出 PDF

- 变更：3 个路径；guide 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1042 · 47e2f2c · 2026-09-12

fix: 递卡顺序校验器——带句号的卡名不再截断；重出 PDF

- 变更：2 个路径；guide 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_guide.py`

## 1043 · 5475418 · 2026-09-12

docs: EBOOT 逆向——正文/名牌/卡名拉丁宽度机制差异与半角化补丁评估（§9）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1044 · 31579b9 · 2026-09-12

feat: 排版校验器改像素模型——拉丁按 17px 字体真实步进（步进表 data/font_advances_17.json、pgf_inspect export-advances、latin-split/narrow-glyph 告警）

- 变更：5 个路径；data 1、tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/msg_layout_check.py`、M `tools/pgf_inspect.py`

## 1045 · 281e42a · 2026-09-12

feat: 正文/卡名拉丁半角化——EBOOT 层 msgcol-px（列计数改像素、col += 真实步进、ruby 先画 base 取宽）+ 叠加层 cardname-halfwidth（去 cHan2Zen）；mips_asm 汇编器与 msgcol_px 生成器（纯净段往返验证）

- 变更：8 个路径；layers 3、tests 3、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/mips_asm.py`、`tools/msgcol_px.py`
- 相关实现/计划变更：A `tools/mips_asm.py`、A `tools/msgcol_px.py`

## 1046 · ccf7926 · 2026-09-12

docs: 拉丁半角化落地记录（研究记录 §9.6、runbook 汇编器/重定位事实、CLAUDE.md）+ 探针页重切为语料内字（K1–K4/L1/L2）

- 变更：4 个路径；CLAUDE.md 1、docs 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/testboot.py`

## 1047 · 7f8fff9 · 2026-09-12

fix: 撑宽正文字体窄字形""·→17px（build_font.widen_body_narrow），步进表与校验器测试同步

- 变更：5 个路径；data 1、tests 3、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_font.py`

## 1048 · d9d3a51 · 2026-09-12

feat: 拉丁人名折行修复——行头禁则表加半角连字符 + inject_lua 注入后自动整词换行（策略 A）

- 变更：4 个路径；layers 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/latin_wrap.py`
- 相关实现/计划变更：M `tools/inject_lua.py`、A `tools/latin_wrap.py`

## 1049 · 711973c · 2026-09-12

chore: 探针页重整——删 6 页对齐/行宽探针（腾空间）+ 加 8 页 latin-split A/B 对比探针

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/testboot.py`

## 1050 · 52abe46 · 2026-09-12

data: 题名中文 logo 换第二版素材——加强光晕、15分钟改橙金、居中修正

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1051 · ede8417 · 2026-09-12

data: 题名中文 logo 接入配色后处理版（C）——按日文原版校准明度/浓度/色相

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1052 · 2ebd6bf · 2026-09-12

chore: 归档题名配色后处理工具链到 tools/research/title_recolor

- 变更：10 个路径；tools 10
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/research/title_recolor/probe.py`、`tools/research/title_recolor/recolor_title.py`、`tools/research/title_recolor/snapshot_inputs.py`、`tools/research/title_recolor/validate.py`
- 相关实现/计划变更：A `tools/research/title_recolor/.gitignore`、A `tools/research/title_recolor/README.md`、A `tools/research/title_recolor/calibration.json`、A `tools/research/title_recolor/measurements.json`、A `tools/research/title_recolor/probe.py`、A `tools/research/title_recolor/recolor_title.py`、A `tools/research/title_recolor/requirements.txt`、A `tools/research/title_recolor/snapshot_inputs.py`、A `tools/research/title_recolor/validate.py`、A `tools/research/title_recolor/validation.json`

## 1053 · 6787299 · 2026-09-12

fix: title_logo 驾驶脚本截图容错——break_cpu 广播超时不再废掉整轮 15 分钟

- 变更：1 个路径；tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/emu/drives/title_logo.py`

## 1054 · 382e259 · 2026-09-12

data: glossary v23 + skeleton 召回——「名＋ちゃん」一律「～酱」，「小～」形废止（skeleton-v5）

- 变更：4 个路径；glossary 1、skeleton 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1055 · be60723 · 2026-09-12

data: v23 召回落地——主轨 13 行「小～」→「～酱」+ 口调表/通读闸同步

- 变更：7 个路径；config 1、glossary 3、pilot 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/qa_quote_suppressions.yaml`、M `tools/read_server.py`

## 1056 · e76321e · 2026-09-12

docs: 「名＋ちゃん」称呼族拉平的清点、裁定与落地台账（2026-09-12）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1057 · f3276f1 · 2026-09-12

docs: CLAUDE.md 不再钉死 glossary 版本号（现已 v23）

- 变更：1 个路径；CLAUDE.md 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1058 · 5e6ada5 · 2026-09-12

data: 谢幕卡文案「人」标作『人』（具名例外）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1059 · 9440cf7 · 2026-09-13

fix: parse_crd_answers 不再把卡 1 当哨兵滤掉——卡 1 是 crd_2/30/108 的合法答案

- 变更：4 个路径；data 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_dag.py`、M `tools/extract_crd.py`

## 1060 · f0e2ee8 · 2026-09-13

fix: 攻略递卡校验扩到全部 103 个需递卡谜题，口径改绑定返回变量；附录递卡列改有序

- 变更：3 个路径；docs 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_guide.py`

## 1061 · 1b761df · 2026-09-13

docs: 攻略补回 crd_30 开头的卡 1、crd_108 由「无需递卡」改为递卡 1，教程段改 make-cards 表

- 变更：4 个路径；guide 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1062 · 3c2f28f · 2026-09-14

feat: 攻略新增 story-box/frag-box——故事模式框内不标卡片格位

- 变更：2 个路径；docs 1、guide 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1063 · ab1f123 · 2026-09-14

docs: 攻略 43 处故事模式框改用 story-box（去掉格位），48 处片段模式框改 frag-box；记法说明同步

- 变更：11 个路径；guide 11
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1064 · e2fb68a · 2026-09-17

docs: 谢幕章新增 BGM 调研与方案（SOUND.BIN 同构 pack、引擎只吃 ATRAC3+、atracdenc-744 + 自写 RIFF 头）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：`docs/superpowers/specs/2026-09-17-encore-bgm-injection-design.md`
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/specs/2026-09-17-encore-bgm-injection-design.md`

## 1065 · c13fcbf · 2026-09-19

fix: select 派生层拒收场景标题形状的原文——sel_s4s_170_sel_a 烤成了下一分支名

- 变更：3 个路径；data 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_select.py`

## 1066 · e15e746 · 2026-09-19

docs: 攻略「选择：看到字条时」的解锁选项改为定译「被勾起了兴趣」并重生成

- 变更：5 个路径；guide 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1067 · 233567b · 2026-09-19

fix: PGF 头部竖向量度改由 build_font 自己写——ttf_pgf 重编丢头部补丁致 ruby 下沉 6 px 压进正文

- 变更：6 个路径；CLAUDE.md 1、docs 2、tests 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_font.py`

## 1068 · ef86842 · 2026-09-19

feat: 攻略路线校验器——按引擎规则重放正文的故事/片段交替，走不通拒绝出盘

- 变更：6 个路径；CLAUDE.md 1、docs 1、guide 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/guide_route_check.py`
- 相关实现/计划变更：M `tools/build_guide.py`、A `tools/guide_route_check.py`

## 1069 · 025fee5 · 2026-09-19

docs: 攻略正文按引擎模拟重排全部故事/片段轮次并重出 PDF

- 变更：11 个路径；guide 11
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1070 · 49235dd · 2026-09-20

docs: 攻略章节 3 绕开『颇有意思的传闻』——章节 3/4 每轮沙漏起点 25→0，两段探索不再重走，各省 3 轮

- 变更：4 个路径；guide 4
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1071 · 9848436 · 2026-09-20

docs: guide runbook 记「别把做不了的选择卡留在路线前缀上」与探索重走的逐处判断法

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1072 · 34f2714 · 2026-09-20

docs: guide runbook 事实速记去掉已过时的「章节 3 每轮扣 25／章节 4 探索走两遍」

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1073 · bcd433b · 2026-09-20

feat: 攻略路线校验器加死胡同探针——沙漏用完处紧接 Game Over 的轮次必须标 #deadend

- 变更：3 个路径；docs 1、guide 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/guide_route_check.py`

## 1074 · 2a5518f · 2026-09-20

docs: 攻略 4 处沙漏用完即 Game Over 的轮次加 #deadend 说明（天台/天台的人影/抓住手臂/Sakura的来信），第 1 章记法解释该标注

- 变更：5 个路径；guide 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1075 · 840702b · 2026-09-20

docs: 攻略章节 4B 现实层导语改正——是彩野告诉直哉故事讲不下去了，不是直哉告诉彩野（s4fb_10 原文）

- 变更：2 个路径；guide 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1076 · 1d24ee2 · 2026-09-21

docs: 攻略章节 EX2 补上结尾剧本里的递卡——做成『第二物语』后自动播放的 e2f 天台一场要递『冬天的告白会失败』

- 变更：2 个路径；guide 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1077 · 8f5998f · 2026-09-21

feat: read_commit 加 --skip——几条要先商量的行不拖住其余几十条清关

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/read_commit.py`

## 1078 · 5a183dd · 2026-09-21

data: 通读草稿清关 81 条——含 16590/5491 千秋「结局里的Yuichi」句重译与同族补齐

- 变更：4 个路径；config 1、pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ui_terms.yaml`

## 1079 · 7bd7685 · 2026-09-21

feat: read_commit 把「与车道逐字相同」的草稿行记为已处理

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/read_commit.py`

## 1080 · 5cca4d6 · 2026-09-21

data: 3171『听』→『打听』落地；字条句「就能明白」5 条撤回（用户 2026-09-21 裁定）

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1081 · 337d4c9 · 2026-09-21

data: glossary v24——エンドロール／スタッフロール→End Roll，Staff Roll 作废（与语音一致）

- 变更：8 个路径；config 1、data 1、glossary 3、layers 1、pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ayano_qa/seg6-s8-e1.yaml`

## 1082 · da32711 · 2026-09-21

docs: 攻略与谢幕章现行稿随 glossary v24 改 End Roll，重出 PDF

- 变更：5 个路径；docs 2、guide 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1083 · 00473a2 · 2026-09-21

feat: 通读草稿归档——read_commit --prune 把已关账行搬进 archive，UI 待办视图不再显示已清关行

- 变更：5 个路径；tests 2、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/voice_transcribe.py`
- 相关实现/计划变更：M `tools/read_commit.py`、M `tools/read_server.py`、A `tools/voice_transcribe.py`

## 1084 · aee39c8 · 2026-09-21

data: 通读草稿 120 行全部归档（99 个 id 均已清关），草稿清空

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1085 · 94e6001 · 2026-09-21

docs: e2f 4838– 「字与声不一致」演出——语音转写留档、全库同类清点与汉化呈现方案

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1086 · 1f3a04c · 2026-09-21

data: e2f 4838–4847 十行按「字与声不一致」演出补出配音内容——≪≫ 内字幕不动，_r 后以「」补配音实际念的话

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1087 · 478254b · 2026-09-21

docs: e2f 字与声不一致演出——记录「」壳裁定与落地；CLAUDE.md 已知坑加一条

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1088 · 8db9548 · 2026-09-21

docs: e2f 4845/4847 两条半秒片段经用户人耳复核无误，去掉待复核标记

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1089 · 39e27cb · 2026-09-21

fix: build_disc 字体阶段的字集并入本剖面自己的 lua/final——test 盘新层的字不再漏出字集

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`

## 1090 · fd658fb · 2026-09-21

feat: 文库（游戏内小说）不烤字的玩家侧说明——章节 1 读完八条【■汉化说明】+ 文库入口一次性两条

- 变更：7 个路径；layers 4、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/novel_notice.py`、`tools/emu/drives/novel_notice_s1f.py`
- 相关实现/计划变更：A `tools/emu/drives/novel_notice.py`、A `tools/emu/drives/novel_notice_s1f.py`

## 1091 · b605a7b · 2026-09-21

docs: 文库说明的方案/措辞/目检台账；disc-pipeline 走查示例改指实物层；CLAUDE.md 登记

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1092 · 3d55569 · 2026-09-21

docs: disc-pipeline 阶段表 font 行随字集取材改动更新；文库说明台账标记已采纳并提交

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1093 · 1e30fc7 · 2026-09-21

feat: 开机链第五卡 IPL03——汉化组署名与献词（层 boot-dedication + 纯排版烤图 + 逐帧驾驶验证）

- 变更：15 个路径；CLAUDE.md 1、docs 6、layers 2、tests 2、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_boot_dedication.py`、`tools/emu/drives/boot_dedication.py`
- 相关实现/计划变更：A `tools/bake_boot_dedication.py`、M `tools/emu/drives/README.md`、A `tools/emu/drives/boot_dedication.py`、M `tools/emu/drives/release_iso.py`

## 1094 · 97e0e25 · 2026-09-21

docs: 谢幕章 v3 工作稿——鲸客人 CG 与文化祭段对白（用户执笔）、新 BGM 整曲循环、千秋转述所思所想的落位提案与样稿；收入 eve_74_z 源图

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1095 · 6d38ec1 · 2026-09-21

docs: 谢幕章 v3 稿补入千秋转述七张卡的全稿（101 条，排版模拟 ≤2 行）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1096 · c22461b · 2026-09-21

docs: 谢幕章转述全稿按用户改定（卡 201 重演绎为考古/誊抄意象）；决定 D7 卡面与原话不改；07 文档附转述版指引

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1097 · 31a9d73 · 2026-09-22

feat: 鲸客人 CG 新成员 event/eve_74_z——bake_finale_event 降采样+预量化（MEDIANCUT MSE 15.4），[gim].new 登记，画廊叠加层 finale-gallery-cg 把 eve_74 格扩成双变体

- 变更：6 个路径；docs 1、layers 2、tests 2、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_finale_event.py`
- 相关实现/计划变更：A `tools/bake_finale_event.py`

## 1098 · 139c07e · 2026-09-22

feat: 谢幕章 v3 脚本落地——fin-35『讲述者们』千秋转述七张卡（vms 17600–17700）、fin-40 鲸客人 CG 溶解与文化祭段全文、fin-50 尾巴对话、翻卡段 BGM 与延时；id 段 17600–17799 登记；finale_scene 驾驶脚本

- 变更：5 个路径；layers 2、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/finale_scene.py`
- 相关实现/计划变更：M `tools/emu/drives/finale_full.py`、A `tools/emu/drives/finale_scene.py`

## 1099 · e135c5c · 2026-09-22

feat: 新增音频管线——at3p.py（AT3+ 编码/检视/核对，本作同款 RIFF 头）、build_atracdenc.sh+744 补丁、manifest [sound] 清单与 layers 闸、build_disc sound 阶段/断言⑤/ISO 接线、bgm_probe 驾驶；首曲 bgm_fin_1（用户 remix，整曲循环、裁 3:16、−21 LUFS）进包，模拟器实测回绕；文档与 CLAUDE.md 同步

- 变更：16 个路径；CLAUDE.md 1、data 1、docs 3、layers 2、tests 2、tools 7
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/at3p.py`、`tools/build_atracdenc.sh`、`tools/emu/drives/bgm_probe.py`
- 相关实现/计划变更：M `docs/superpowers/specs/2026-09-17-encore-bgm-injection-design.md`、A `tools/at3p.py`、A `tools/atracdenc-744.patch`、A `tools/build_atracdenc.sh`、M `tools/build_disc.py`、M `tools/emu/drives/README.md`、A `tools/emu/drives/bgm_probe.py`、M `tools/layers.py`

## 1100 · 7a0a9f3 · 2026-09-22

feat: 谢幕章演出增强——fin-35 每张卡挂出配做卡「递对卡」白光爆闪与按键音（finAnswerFlash），fin-40 彩野出拳配 s4s 同款 se_79+黄闪；finale_scene 驾驶加连拍抓帧

- 变更：4 个路径；docs 1、layers 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/emu/drives/README.md`、M `tools/emu/drives/finale_scene.py`

## 1101 · bb2ff69 · 2026-09-22

docs: 攻略隐去 Sakura 真名——第 1 章人名说明去掉「佐仓雪乃」，EX2 导语改用 Sakura（游戏到章节 5 现实层才揭晓）

- 变更：3 个路径；guide 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1102 · a613273 · 2026-09-22

test: 攻略守门测试新增 test_no_real_name_spoiler（不写「雪乃／佐仓」）；runbook 记入不剧透规则

- 变更：2 个路径；docs 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1103 · 1a9e62f · 2026-09-23

data: glossary v25 + skeleton 召回——卡 93 末句「あったね」由「真的有过呢」改「还记得吧」（skeleton-v6）

- 变更：3 个路径；glossary 1、skeleton 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1104 · 6479095 · 2026-09-23

docs: 卡 93「あったね」解读与召回台账（剧情链条、候选裁定、载体落点、验证；bake-progress 追记 skeleton-v6 与单卡召回的 MSE 告警说明）

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1105 · e8515d0 · 2026-09-23

feat: 谢幕章 fin-0 递笔加 e2 写手层同款动笔音效——翻页 se_101 → 按笔芯 se_51 →「……笔，接过来了。」；se_probe 录音互相关探针

- 变更：5 个路径；CLAUDE.md 1、docs 1、layers 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/se_probe.py`
- 相关实现/计划变更：M `tools/emu/drives/README.md`、A `tools/emu/drives/se_probe.py`

## 1106 · 690b040 · 2026-09-24

docs: OP/ED 影片在 PPSSPP 不播的根因与上游修复实测（sceMp4 空桩；开发版 ≥1841 LLE + 盘内 6.20 固件自动安装后 OP 音画正常）

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1107 · ea2394a · 2026-09-24

docs: OP 主题歌『残照』歌词中文拟稿第二版——逐行互文取证、影片文字卡实况、拍数表

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1108 · 08b3e50 · 2026-09-24

docs: iOS 商店版 1.20.4 无法经补 prx 走 LLE 播 OP/ED 的源码核查结论

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1109 · 692f9ea · 2026-09-24

docs: iOS（PPSSPP 1.20.4）播放 OP/ED 的改库名 LLE 方案实验跑通——推翻早先「无解」结论，记录全部改动、根因与实测

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1110 · e1dc24b · 2026-09-24

docs: iOS 变体盘产品化实施计划（umdiso 增文件、固件模块补丁、44.1k 影片、EBOOT ios 层、--ios 出盘、影片驾驶、CFW 评估）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-09-24-ios-movie-variant.md`

## 1111 · dcae6bc · 2026-09-24

feat: umdiso 新增 add——往既有目录追加新文件（数据追加卷尾、克隆兄弟记录格式、按名插入）

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/umdiso.py`

## 1112 · 10b66be · 2026-09-24

feat: ios_fwmod——固件 libmp4/mp4msv 改库名与 1.20.x 兼容补丁（AAC 输入长度跳板、GP 桩兜底），type-B 重定位解码

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/ios_fwmod.py`
- 相关实现/计划变更：A `tools/ios_fwmod.py`

## 1113 · 65857f4 · 2026-09-24

feat: ios_movie——op/ed 音轨重采样 44.1k（视频原样拷贝、bitexact），产物指纹钉 manifest

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/ios_movie.py`
- 相关实现/计划变更：A `tools/ios_movie.py`

## 1114 · feb898d · 2026-09-24

feat: EBOOT 层支持 profile=ios（仅 --ios 施加）+ ios_eboot 生成器（E1–E4）

- 变更：5 个路径；tests 2、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/ios_eboot.py`
- 相关实现/计划变更：M `tools/eboot_patch.py`、A `tools/ios_eboot.py`、M `tools/layers.py`

## 1115 · 2f8fbc9 · 2026-09-24

data: layers/eboot/ios-movie——iOS 变体 EBOOT 层入库并登记 [eboot].order

- 变更：2 个路径；layers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1116 · dfaf9bd · 2026-09-24

feat: build_disc --ios 出 iOS 变体（release→game_zh_ios.iso、test→game_ios/），testboot 影片参数 --movie/--skippable

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/testboot.py`

## 1117 · b5aeb80 · 2026-09-24

data: manifest 新增 [ios]（模块清单、44.1k 影片指纹）

- 变更：1 个路径；layers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1118 · 1115170 · 2026-09-24

feat: 影片音画驾驶 movie_probe（DumpAudio+截帧→分段互相关/漂移/音画差判定）与 PPSSPP 1.20.x ini 调试器会话

- 变更：5 个路径；tests 1、tools 4
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/movie_probe.py`、`tools/emu/legacy.py`、`tools/emu/movielab.py`
- 相关实现/计划变更：M `tools/emu/drives/README.md`、A `tools/emu/drives/movie_probe.py`、A `tools/emu/legacy.py`、A `tools/emu/movielab.py`

## 1119 · 70ae737 · 2026-09-24

fix: iOS EBOOT 层把共用洞内 LO16 的死代码 HI16（0x62B74）也改 NONE，重定位表不留悬空 HI16

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/ios_eboot.py`

## 1120 · 7c0b3c7 · 2026-09-24

data: layers/eboot/ios-movie 重生成（重定位 NONE 三条）

- 变更：1 个路径；layers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1121 · 65cbbfb · 2026-09-24

docs: iOS 变体盘产品化——命令面、实测、固件模块取得、CFW 行为评估与玩家说明要点

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1122 · 5b2b90c · 2026-09-24

docs: E4 保 pts 包装栈帧的 EABI 依据补入 CFW 评估（终审）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1123 · 7c62453 · 2026-09-24

chore: iOS 变体盘产品化 SDD 台账与任务简报入库

- 变更：9 个路径；.superpowers 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1124 · 66dec8b · 2026-09-24

feat: release 出盘总是同出 game_zh_ios.iso——跑了 iso 就自动追加 ios 阶段，开跑前核对固件模块与 ffmpeg

- 变更：4 个路径；tests 2、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/ios_movie.py`

## 1125 · 73603cb · 2026-09-24

chore: iOS 变体相关注释与报错文案随「release 出盘必出」更新

- 变更：3 个路径；tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/eboot_patch.py`、M `tools/ios_eboot.py`

## 1126 · d77dc74 · 2026-09-24

data: ios-movie 层 why 与 manifest 注释改为「ios 阶段施加 / release 随 iso 必出」（补丁字节不变）

- 变更：2 个路径；layers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1127 · 976dc06 · 2026-09-24

docs: runbook 与 CLAUDE.md——release 出盘总是同出 game_zh_ios.iso，test 剖面仍需 --ios，前置条件开跑前核对

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1128 · 558f01d · 2026-09-24

docs: 登场角色 MBTI 人格侧写——总论（12 人一览、逐人侧写、跨层观察、勘误）＋八卷子代理采证原文

- 变更：9 个路径；docs 9
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1129 · ba3678d · 2026-09-24

feat: 攻略路线校验器支持 quit:（□ 切片段模式）并加 idle_tail 探针——目标场景到手后的持卡尾巴 ≥2 场必须提前退出

- 变更：3 个路径；docs 1、guide 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/guide_route_check.py`

## 1130 · 625afab · 2026-09-24

docs: 攻略 7 处轮次改为目标场景到手即切片段模式；章节 7 九张零容错、章节 5 递错代价按脚本写准；封面署名

- 变更：10 个路径；guide 10
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1131 · 1f73f13 · 2026-09-24

docs: 攻略章节 5 递错代价措辞按档说清（50 档错两次到顶），不再笼统说全章只容一次

- 变更：2 个路径；guide 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1132 · e17b8d2 · 2026-09-24

fix: 量化器把最透明色排到色板 0 号——GIM 对齐填充区不再是不透明纹素（encore 菜单图右缘竖缝）

- 变更：3 个路径；CLAUDE.md 1、tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`

## 1133 · 16bf8df · 2026-09-25

docs: 谢幕第二段工作稿 v0——『声』选择画面复用为入口、fin-60..90 分镜、用户稿切分全文（116 条排版模拟 ≤2 行）、资产与待决清单；收入三张少女 CG 源图与选择画面 mock

- 变更：5 个路径；docs 5
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1134 · 7d24321 · 2026-09-25

docs: 谢幕第二段工作稿回填第二轮决定（题名『远方的朋友』、署名照录、sec7 保留）＋ Γ⊢φ 一句五案候选

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1135 · 2d587a6 · 2026-09-25

docs: 谢幕第二段工作稿回填第三轮决定——Γ⊢φ 取『证毕』案、选择画面标点与引号、cut_62 切入电脑段、E8/E9 采纳、新曲 bgm_fin_2 规格与落位；mock 重出

- 变更：2 个路径；docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1136 · 2f6da56 · 2026-09-25

docs: 谢幕第二段『远方的朋友』实施计划——七个任务（少女 CG 清单化、『声』选择画面六图、bgm_fin_2 进包、脚本与守门测试、--finale-read 捷径、模拟器验证、出盘与文档）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：A `docs/superpowers/plans/2026-09-25-encore-second-story.md`

## 1137 · 03bb10a · 2026-09-25

feat: bake_finale_event 清单化——鲸客人＋三位少女 CG（eve_47_f/d/g，母本 eve_47_x）同一流程产出

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/bake_finale_event.py`

## 1138 · f795323 · 2026-09-25

data: 谢幕第二段三位少女 CG 入库成品（480×272 预量化 256 色，MEDIANCUT MSE 14.1/13.3/12.7）

- 变更：4 个路径；.superpowers 1、docs 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1139 · 068ccd9 · 2026-09-25

feat: 谢幕『声』选择画面六张图——bake_finale_voice（提示 eve_0_j／脚注 eve_0_k／sel_fin1/2 光晕按钮），bake_event_voice 参数化＋擦框羽化＋eve_0_g 压暗重建补底，manifest 登记 finale_voice/finale_select 两面

- 变更：5 个路径；.superpowers 1、layers 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/bake_finale_voice.py`
- 相关实现/计划变更：M `tools/bake_event_voice.py`、A `tools/bake_finale_voice.py`

## 1140 · e4a3347 · 2026-09-25

data: 谢幕选择画面六张图入库成品

- 变更：6 个路径；docs 6
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1141 · 1ce719a · 2026-09-25

data: 谢幕第二段 BGM bgm_fin_2 进包——用户第二支 bgm_5_x remix，整曲循环不裁尾，−21 LUFS

- 变更：3 个路径；.superpowers 1、layers 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1142 · e35d07f · 2026-09-25

feat: 谢幕第二段『远方的朋友』——序章同款『声』选择画面入口（读过第一个故事后）、fin-60..90 四场景（vms 17800–17999）、画廊 eve_47 四变体；守门测试

- 变更：5 个路径；.superpowers 1、layers 3、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1143 · 87b9dbb · 2026-09-25

feat: testboot/build_disc 加 --finale-read——测试盘预置 finaleReadFlag，主菜单直达谢幕『声』选择画面

- 变更：4 个路径；.superpowers 1、tests 1、tools 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/testboot.py`

## 1144 · 73f8cec · 2026-09-25

feat: 谢幕『声』选择画面驾驶 finale_choice——主菜单 encore → 提示/按钮帧 → 选项分支与无旗标直入验证（系统数据备份到 OUT 外、跑完放回）

- 变更：2 个路径；.superpowers 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：`tools/emu/drives/finale_choice.py`
- 相关实现/计划变更：A `tools/emu/drives/finale_choice.py`

## 1145 · da8ac1d · 2026-09-25

data: 17px 步进表补 Γ φ——谢幕第二段新字进字集后按 pgf_inspect export-advances 重生成

- 变更：2 个路径；.superpowers 1、data 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1146 · fdca19a · 2026-09-25

fix: 排版校验器窄字形告警不报字母类——希腊/带附加符号的拉丁按比例宽排与 ASCII 同理，只报 × “” · 这类该占满一格的符号

- 变更：2 个路径；tests 1、tools 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/msg_layout_check.py`

## 1147 · dac1d34 · 2026-09-25

docs: 谢幕第二段『远方的朋友』落地——CLAUDE.md 增补、id 段落、工作稿落地记录

- 变更：4 个路径；.superpowers 1、CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1148 · 56fbe19 · 2026-09-25

fix: 谢幕第二段读完 autoSystemSave(0)——三张少女 CG 的画廊解锁与已读标记落盘（旗标不动，fin-50 同款）；守门测试同步

- 变更：3 个路径；.superpowers 1、layers 1、tests 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1149 · e6eb73a · 2026-09-25

docs: 谢幕第二段终审补修记录——CLAUDE.md 与工作稿 D8 补记读完落盘画廊 cgFlag

- 变更：2 个路径；CLAUDE.md 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1150 · 9b0924c · 2026-09-25

chore: 谢幕第二段 SDD 台账与任务简报入库（执行证据）

- 变更：8 个路径；.superpowers 8
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1151 · 351fc43 · 2026-09-25

fix: 谢幕第二段 fin-70 储藏室段不换背景——去掉误引入的换鞋处 bg_18_a_0，纸箱特写 cut_62 直接盖在彩野房间 bg_25_a_0 上（用户实机复看后更正；spec 补 D15，台账记 hotfix）

- 变更：3 个路径；.superpowers 1、docs 1、layers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1152 · 1e9d315 · 2026-09-26

fix: 谢幕第二段 fin-70 音效更正——来电改 se_133 座机铃响两秒后 se_131 拿起听筒（首版的 se_131 只是 0.3 s 轻响）、翻找改 se_101 翻纸（se_92 约 105 Hz 闷响小喇叭听不见）；17903 措辞按用户改（spec D16）

- 变更：2 个路径；docs 1、layers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1153 · f233c98 · 2026-09-26

feat: 影片层 [[movies]]——用户压制的影片素材替换盘内 movie/ 成员，两张盘都用

- 变更：4 个路径；tests 1、tools 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `tools/build_disc.py`、M `tools/ios_movie.py`、M `tools/layers.py`

## 1154 · 6ddb3c7 · 2026-09-26

data: manifest 登记中文字幕版 OP（[[movies]] op.mp4 → assets/movie/op_zh.mp4，用户 2026-09-26 第三版）

- 变更：1 个路径；layers 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1155 · 569eb53 · 2026-09-26

docs: 影片层与字幕版 OP 进盘——runbook 改动落点、CLAUDE.md、movie 文档（重压参数与三版记录、用户实机结果）

- 变更：3 个路径；CLAUDE.md 1、docs 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1156 · 599ad0d · 2026-09-26

data: 通读草稿积累 814 行（试玩朋友 2026-09-21～26 的修改，含用户初筛回退成同文的 46 条）

- 变更：1 个路径；pilot 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1157 · 64471bc · 2026-09-26

data: 通读草稿清关 511 条（reason=review）——朋友修改 + 复核修订 41 行 + 同串沿用 10 行

- 变更：3 个路径；pilot 3
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1158 · fffa33e · 2026-09-26

data: glossary v26——場面 语域分立召回 161 行、锚点 5 条更新（skeleton-v7）、extra 轨 1 条、通读草稿归档

- 变更：10 个路径；data 1、glossary 2、guide 1、pilot 5、skeleton 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1159 · bf83fe8 · 2026-09-26

docs: 通读队列落地与「場面」语域分立台账（2026-09-26）——复核三档、裁定、v26 召回范围与验证

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1160 · 767e76a · 2026-09-26

data: ui_terms 校准对齐 v26——場面 除名进 not_terms（语域分立），お話／選択肢／千秋 证据串刷新

- 变更：2 个路径；config 1、docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
- 相关实现/计划变更：M `config/ui_terms.yaml`

## 1161 · 5c73fd0 · 2026-09-26

data: 15432 由加里「忘れものと落とし物……」按用户指定改「忘物，和失物……忘却之物与遗落之物……」（review，v26）

- 变更：2 个路径；pilot 2
- 新增规格/运行手册：无
- 新增工装入口/模块：无

## 1162 · a3977b5 · 2026-09-27

docs: iOS 盘 OP 在 Windows 旧版 PPSSPP 不播——升到 stable 1.20.4 即正常；字幕版 OP 第三版补驾驶 1.20.4 PASS（2026-09-27）

- 变更：1 个路径；docs 1
- 新增规格/运行手册：无
- 新增工装入口/模块：无
