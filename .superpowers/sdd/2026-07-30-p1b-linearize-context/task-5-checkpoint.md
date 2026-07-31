# Task 5 CHECKPOINT 材料（计划要求「呈用户抽查」）

> 用户于本次会话中途去睡，并指示：未完成/待确认的改动也要提交并推到远端，在 `.superpowers/sdd` 与 commit message 里留下充分说明。
> 因此本检查点**未阻塞**，路线已按下述结果入库；以下是请你醒来后复核的材料与两处需要你拍板的裁决。

## 一、全书路线达成情况

`config/route_plan.yaml`（226 条移动，人工可审）经 `gen_timeline` 展开后：

- **覆盖**：16693 条 narrative vms **恰好各出现一次**（全局缺口 0 行、重复 0 行、ambient 混入 0 行）
- **卡片**：195 张卡全部入手（`held` = 1..195）
- **门控**：`config/gates.yaml` 全部通过（`s2s_10` 那条因该状态自身无 play、不产生 unit，被 check_timeline 跳过）

## 二、分段统计

| 段 | unit | marker | id 数 |
|---|---|---|---|
| s0f | 8 | 0 | 569 |
| s1s | 62 | 12 | 2831 |
| s1f | 18 | 0 | 669 |
| s2s | 75 | 16 | 1780 |
| s2f | 1 | 1 | 429 |
| s3s | 61 | 17 | 1667 |
| s3fa | 2 | 0 | 424 |
| s4s | 63 | 12 | 1537 |
| s4fa | 1 | 1 | 600 |
| s4fb | 3 | 1 | 449 |
| s3fb | 3 | 0 | 265 |
| s3fc | 11 | 0 | 317 |
| s5s | 29 | 9 | 938 |
| s5f | 6 | 0 | 240 |
| s6s | 24 | 6 | 605 |
| s6f | 2 | 0 | 237 |
| s7f | 52 | 0 | 663 |
| s8s | 6 | 0 | 64 |
| s8f | 2 | 1 | 250 |
| e1s | 3 | 0 | 850 |
| e1f | 2 | 0 | 27 |
| e2s | 7 | 0 | 382 |
| e2f | 19 | 0 | 900 |
| **合计** | **460** | **76** | **16693** |

unit_kind 分布: {'scene': 248, 'script': 59, 'pool': 2, 'card': 140, 'fscene': 11}

章序：序(s0f) → s1 → s2 → s3 主体 → s4 → 回补 s3 终局(需卡138) → s3fc 强制段 → s5 → s6 → s7f → s8 → 回补 s4s_100_sel(需卡142) → EX1 → EX2 → 收尾 sweep。
（`_f` 现实层章节除 s0f / s3fc / s7f 外，都是由对应终卡的 `runs` 带出来的整文件 `fscene` 单元，位置紧跟在该卡之后——与游戏内「做出终卡即播该章现实层」一致。）

## 三、需要你拍板的两处（我已按判断先行，可随时推翻）

### 1. `config/gates.yaml` 的 `s5s_20` 门控被我改了

计划给的初值是 `{unit_state: s5s_20, requires_cards: [177]}`。但 `snr_common.lua` 里 `sceneId2aCard.s5s_20 = 177`——**卡 177 正是 s5s_20 自己的场景卡**，按构造不可能在该场景「首次出现前」已持有，这条门控恒不满足、会让 `check_timeline` 永远红。

我改成了 crd_177 的前置卡集合：`[133, 134, 135, 136, 137, 138, 145]`，语义即 CLAUDE.md 写的「向彩野上交全部章节梗概后……开启第 5 章」。计划原文允许「Task 5 编路线时可增补」gates.yaml，故按 Task 5 的内容工作处理。

### 2. 展开器/校验器的发卡语义改了三轮（Hotfix B / C）

全书验证暴露出「持卡集合 held」的推导缺口，不补则大量卡片做不成、章梗概卡永不入手、`check_timeline` 对合法 timeline 大面积误报。详见 `hotfix-b-brief.md` / `hotfix-c-brief.md` 与各自的 report。要点：

- crd 脚本自身会发别的卡（做卡10 得卡126、卡51→115、卡56→97），`dag.json` 的 `crds` 补了 `gets` 字段；
- `emit_unit` 统一对「实际取到 id 的全部函数」（含 `unit_funcs.yaml` 附挂）生效 `scene_meta.gets`——这条同时解决了 `_f` 章梗概卡 133-145 与 s7f 的卡 141（授予它的 `scene_s7f_dispatch_v52` 是 dispatcher 带参调用，正则抓不到、只能靠附挂）；
- timeline 全局 id 去重（s4 两个探索场景共用 dispatch 函数、「物音」被两个状态各 play 一次，约 180 行重复）；
- `check_timeline` 的 held 推导改成「只依赖 check() 入参、由 timeline 自身可导出」的超集（签名里没有 unit_funcs，不能照抄展开器口径）。

## 四、路线编写规约（改路线前请先读）

写在 `config/route_plan.yaml` 文件头，共 6 条。最容易踩的三条：

1. 每章首讲用 `story`，其后一律 `replay`——`story` 不去重，`replay` 才折叠已讲状态。
2. `replay` 的 `pick` 只对 `at` 那个状态生效；更深的选择点要另发一条 `replay`，并用 `until` 卡住边界（否则默认支会把指针带进别的章，例如 `s1s_260_sel` 默认支直接 `RUN s5`）。
3. `route` 是累积的（重讲不截断），所以 `_makeable` 的「路线前缀全部已做卡」规则要求**同一选择点的兄弟分支先讲完做完卡再前进**（req 链常跨兄弟分支，例：卡6 的 req 是卡7）；且 `route_has`（本轮讲过）只增不减，需要「没讲过 X」那条支的场景必须排在讲 X 之前。

## 五、`config/unit_funcs.yaml`（孤儿函数附挂表）

共 12 条附挂，每条都带一句归属理由。它们是 `tools/build_dag.py` 的两条正则（`PLAY_RE` 只认 `(doScriptScene|p0), "..."`、`SUBCALL_RE` 只认零参调用）抓不到的函数：dispatcher 里的带参调用、多个场景共用的段落、以及一处全库无调用点的反编译残留（`scene_s3s_helper_v35`）。**这份表请重点抽查**——它决定了这些文本挂在哪个叙事单元里。
