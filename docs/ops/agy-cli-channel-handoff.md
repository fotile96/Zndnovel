# Handoff：把 Antigravity CLI（`agy`）接成一条正式通道

> 起草 2026-08-14，供**独立开发会话**执行。控制会话（P4 润色轨）不做这件事。
>
> **先读**：`docs/ops/paseo-antigravity-probe.md` **全文**，尤其 §九（第四轮，
> 2026-08-14）。那份文档是这项工作的全部既有证据，本文只写「接下来做什么」，
> 不重复它的内容。

---

## 0. 一句话目标

**把 `agy` 做成一条可派发的通道**，形态对标彩野测试里的 `ds-flash`
（`tools/api_client.py` + `tools/ayano_test.py`），区别是**底层不是 HTTP/SSE，
而是 subprocess 调本机 `agy` 可执行文件**。

## 1. ⚠ 明确不做的事：**不要走 paseo**

用户 2026-08-14 裁定：

> 「不建议尝试 paseo 路径了，目前 paseo 的对接方式也不是官方支持的，是社区用户写的一个
> extension，先前测试感觉功能还是很不完整。」

据此：

- `paseo-antigravity-probe.md` §7.2（`bypassPermissions` 建不出 agent）与
  §7.3（`default` 档写文件静默无效）**不必复测、不必修**，它们是社区 extension 的缺陷。
- §9.6 那张表里「经 paseo 派发：❓ 未复测，值得复测」一行**作废**。
- **一切走直连 `agy`。**

这条要写进新代码的模块 docstring，否则后人看到 probe 文档里大段 paseo 内容会以为那是路线。

## 2. ⚠ 强制：先联网查官方文档，再动手

`agy --help` 与 `agy help <sub>` 只给了 flag 名和一句话，**不足以支撑对接**。
本会话**必须**先用 WebSearch / WebFetch 找到 Antigravity CLI 的官方文档，把下面这些问清楚：

| 待查 | 为什么要紧 |
|---|---|
| `--output-format stream-json` 的**事件 schema** | 这是与 `api_client` 的 SSE 设计对齐的关键。`api_client` 的「逐 chunk 静默超时」（idle timeout）语义完全建立在「远端持续吐字节」之上——见其 `DEFAULT_IDLE_TIMEOUT` 注释。若 `stream-json` 能逐 token 下行，同一套抗超时策略可以照搬；若只在结束时吐一坨，就得另想 |
| `--json-schema` 的**确切语义与边界** | help 里写着「for stream-json, only applicable to the final result」。若它能强制结构化输出，**润色通道的 JSONL 行契约和彩野测试的判词都可以让它兜底**，比在提示词里求它守格式可靠得多。这可能直接解决 §9.3(b) 的 `jp_tail` 不合规 |
| `--sandbox`（"Run in a sandbox with terminal restrictions enabled"） | **这可能就是 §9.3(a) 的机制解**。probe 已证明「派发词里的禁止条款压不住这条通道」——它跑进仓库改了一个已 tag 段的 `plan.json`。要查清 sandbox 到底限制了什么、能不能挡住文件写 |
| `--add-dir` / `--project` / `--new-project` 的 workspace 语义 | 决定「它眼里的工作目录是什么」，与仓库隔离直接相关 |
| `--effort low\|medium\|high` 与模型 id 后缀（`-high/-medium/-low`）的关系 | probe §7.1 记的是「effort 编在模型 id 后缀里」，但 CLI 另有独立 `--effort`。**两者同时给会怎样？**（实测过一次：`--model __bogus__` 的报错里回显了 `--effort ""`，说明两者是一起解析的） |
| `--continue` / `--conversation` 会话续接 | 决定长任务能不能分段推进、失败能不能续跑 |
| **退出码语义** | probe §一是这条链上最硬的一条教训：**失败全部返回 0**。要查官方是否承诺过退出码，若不承诺就必须在我们这侧建判据（见 §5） |
| 配额 / 计费口径 | 决定 `data/api_ledger.jsonl` 那一行该怎么写（见 §6） |

**查不到就写「查不到」并说明推断依据**——不要拿 `--help` 的一句话当文档，也不要
猜测后按猜测写代码。probe 文档里已经有两次「猜字符串导致张冠李戴」的实证
（§3 的模型表、§7.1 的 `--model` 静默落默认）。

## 3. ⚠ 强制：在 worktree 里做

本仓库同时有多个会话在跑（工作树里长期存在 `.claude/settings.json` 与
`data/api_ledger.jsonl` 两个**别的会话未提交的改动**）。本项工作要新增/改动
`tools/` 下的代码与测试，**必须隔离**：

- 用 `EnterWorktree`（或 `Agent` 的 `isolation: "worktree"`）开一个独立工作树，
  分支名 `feat/agy-cli-channel`。
- **绝不 `git add -A`**；提交时逐路径 `git add`。
- **绝对不要碰** `.claude/settings.json` 与 `data/api_ledger.jsonl` 的既有改动
  ——那是别的会话的。若新代码要写 ledger，**在 worktree 里写、且只在测试中用
  临时路径**（`api_client.chat` 已有 `ledger_path` 注入点，照用）。
- 合并回 `main` 前先 `uv run pytest -q` 全绿。

另有一层理由：`agy` 会在**它的工作目录**里动手（§9.3(a) 的实证）。在 worktree 里
跑意味着即便它再越界，脏的也是 worktree 而不是主工作树。

## 4. 对标物：彩野测试的 `ds-flash` 通道长什么样

读这三个文件，**照它们的形状长**，不要另起一套：

| 文件 | 本项工作要复用/对标的点 |
|---|---|
| `tools/api_client.py` | 模块 docstring 明写「**提供商无关的扩展点是 `PROVIDERS` 表——加第二家只需加一条记录**」。⚠ **但那张表是 HTTP 形状的**（`url` / `key_env` / `default_model`），而 `agy` 是 subprocess 形状（无 url、无 key、有可执行文件路径与一堆 flag）。**这是本项工作的第一个架构决策，见 §4.1** |
| `tools/ayano_test.py` | `main(argv=None, *, stream_transport=None, api_key=None, ledger_path=None)`——**三个注入点全是为离线测试留的**。新通道必须留同等的注入点，否则测不了 |
| `tests/test_api_client.py` | 既有测试怎么用假 transport 驱动流式解析。新通道的测试照此办理：**不要在测试里真的 spawn `agy`** |

### 4.1 第一个架构决策：`PROVIDERS` 里加一条，还是另起一个 transport？

两条路，**请在动手前明确选一条并把理由写进 docstring**：

- **（甲）扩 `PROVIDERS`**：给表项加一个 `transport: "http" | "subprocess"` 判别键，
  `chat()` 内部分派。好处是调用方（`ayano_test`）一个字不用改，`--model` 之类的
  flag 直接复用。坏处是 `chat()` 会背上两套完全不同的错误处理/超时/重试语义。
- **（乙）另起 `tools/agy_client.py`**，对外暴露**与 `api_client.chat()` 同签名**
  的函数（至少 `messages` / `model` / `purpose` / `ledger_path` / `on_delta` /
  `timeout` 这几个键语义一致），由调用方选择注入哪个。好处是两套实现互不污染、
  各自的 docstring 能把各自的坑写清楚。坏处是 `ayano_test` 要加一个选择开关。

倾向（乙），理由：`api_client` 的 docstring 里大量内容（Responses API、SSE、
`key_env`、`cached_tokens`）对 subprocess 通道**全部不适用**，塞进去会让那份
写得很好的文档变得半真半假。但**这是建议不是裁定**，请自行判断后说明。

## 5. ⚠ 判据：绝不能用退出码

probe §一是这条链上最硬的一条教训，**已被四轮反复证实**：

| 环节 | 现象 | 退出码 |
|---|---|---|
| `agy --model <假 id>` | `Error: invalid model selection ...` | **0** |
| `agy` 资格校验失败 | `Error: Eligibility check failed ...` | **0** |
| `agy` 什么都没产出 | 一段像模像样的完成报告 | **0** |

新通道**必须自己建判据**，至少包括：

1. **产物存在性**——该落的文件真的在，行数对得上。
2. **stdout 里的错误串**——把已知错误前缀（`Error: invalid model selection`、
   `Eligibility check failed` 等）做成显式检测，命中即抛。
3. **模型回读**——若官方提供任何回读实际模型的手段（`stream-json` 事件里可能带），
   **必须回读并与请求值比对，不符即作废**。probe §7.1 的历史是：那一版
   `--model` 静默不生效，四个不同请求全落到同一个模型上，「候选、准入结果、计费
   全部张冠李戴」。**现在它被修好了（§9.1），但不要依赖它一直是好的。**

## 6. `data/api_ledger.jsonl` 该写什么

现有行形（HTTP 通道）：

```json
{"ts":"…","provider":"deepseek","model":"deepseek-v4-flash","purpose":"ayano-judge:seg7-e2:q18",
 "prompt_tokens":426,"completion_tokens":66,"cached_tokens":0,"reasoning_tokens":45,"effort":"max"}
```

`agy` 是**订阅制**，多半拿不到 token 数。

**缺键这件事下游已经处理好了，不用纠结**（已替你读过代码）：`ledger_token()`
对缺键与负哨兵 `-1` 一律返回 `None`，`summarize_ledger()` 把它们计进 `unknown`
而不是当 0 求和——它的 docstring 明写「让『这个总数少统计了几行』一眼可见，
而不是把未知悄悄当成 0」。所以 **token 列拿不到就整个不写这个键**，
不要写 `0`（会被当成真实的 0 参与求和，是静默低估），也不要写 `null`
（`ledger_token` 会返回 None，行为与缺键相同，但缺键更诚实）。

请决定并写进 docstring：

- `provider` 写什么？建议 `"antigravity"`，`model` 写实际回读到的型号
  （如 `gemini-3.7-flash-high`）。
- 若能拿到 wall-clock 时长或配额百分比，**记下来**——SEG-6 评测 kimi 时，
  「滚动用量 %」和「耗时」是判断费效比的主要依据（见
  `pilot/polish/seg5-s6-s7f/channel_feedback.md` §七）。

⚠ **本文件是别的会话也在写的**（见 §3）。在 worktree 里做实验时用
`ledger_path` 注入临时路径，不要往真 ledger 里灌测试数据。

## 7. 已知的三件阻断，各自的线索

全部出自 probe §9.3，**这是本项工作真正要解决的东西**：

### (a) 仓库隔离——**必须靠机制，不能靠提示词**

实证：派发词里写了「不要在仓库下创建/修改/删除任何文件」，它照样跑了
`polish_context.py --session 1`，**覆盖了已 tag 的 SEG-4 的 `plan.json` 里的
`prompt_hash`**，而且它自己的报告里一个字都没提。同样的条款在
`fable-wf` / `ds-flash` / `kimi-k2.6` 上全部有效（SEG-6 三通道零污染）。

线索：`--sandbox`、`--add-dir`、`--project` / `--new-project`。查文档（§2）。
兜底方案：在只读挂载 / 独立 worktree / 临时目录里跑，**并在每次调用后
`git status` 核对**（这一步无论如何都要做，作为回归测试的一部分）。

### (b) `jp_tail` 70% 不合规

它取「语义完整的一截」而不是机械的末 8 字。两条路：

1. **`--json-schema` 兜底**（§2 要查的重点之一）——但 schema 大概率只能约束
   *结构*，管不了「必须等于末 8 字」这种*内容*约束。
2. **在派发词里给可执行的取法**，而不是描述规格。例如明确要求它写一段脚本按
   码点取末 8 个字符，而不是"理解"这个规格。
3. **在 ingest 侧对该字段放宽**——⚠ 这条要慎重：`jp_tail` 是**回显完整性校验**，
   它的作用是证明「模型看的那一行就是我们发的那一行」。放宽等于拆掉一道
   防错位的闸。**若要走这条，必须先想清楚拿什么替代它。**

### (c) 静默的角色名损坏，现有闸抓不到

实证：`3831` 把 `アヤノ` 写成 `アヤ野`，`note` 为空（没声称在改）。
`R2b` 只查 `【】` 前缀，`W2` 查 `active.json`——而 `アヤノ`/`ユカリ`/`サクラ`/
`ナオヤ`/`チアキ` **都不在 `active.json` 里**，只有 `ユウイチ: ユウイチ` 在。

**已测好的补法（需 glossary v17，控制会话未执行，留给用户裁）**：按 `ユウイチ`
的既有先例把五个片假名角色名登记进 `active.json`。实测代价：

| 名 | jp 命中行 | zh 缺该字面（＝新增 W2 警） |
|---|---:|---:|
| アヤノ | 2208 | **2**（`1430` / `7709`，均为 §5(b) 正当的呼名换代词） |
| ユカリ | 368 | 0 |
| サクラ | 1031 | 0 |
| ナオヤ | 34 | 0 |
| チアキ | 2 | 0 |
| （ユウイチ，已登记） | 2146 | 3（同性质，是既有的已知误报） |

**本项工作不要自己去改 glossary**——若认为该补，写进结论请用户裁。

## 8. 建议的推进顺序

1. **worktree + 读 probe 文档全文 + 联网查官方文档**（§2/§3）。
2. **最小可行调用**：写一个只做「发一句话、拿回一句话」的 `agy` 调用，
   把 `--output-format stream-json` 的事件流原样 dump 出来看清楚。
   **这一步的产物是一份事件 schema 的实测记录**，比任何文档都可靠。
3. **定架构**（§4.1），写 docstring 说明选择理由。
4. **建判据**（§5）+ 离线可测的 transport 注入点（对标 `stream_transport`）。
5. **先接彩野测试**（`ayano_test.py`），不要先接润色轨——彩野测试是单次问答、
   输出短、判分现成，是最小的真实负载；润色轨是 760KB prompt + 334 行 JSONL 输出，
   把两个未知量叠在一起会分不清是谁的问题。
6. 彩野测试跑通、且能与 `ds-flash` 的历史成绩横比之后，再谈润色轨。
7. **每一步跑完都 `git status`**（§7(a)）。

## 9. 验收标准

- [ ] 联网查到的官方文档要点已写进新模块的 docstring，查不到的明确标注「查不到 + 推断依据」
- [ ] 架构选择（§4.1 甲/乙）已定并写明理由
- [ ] 有一份 `--output-format stream-json` 的**实测事件 schema 记录**入库
- [ ] 判据不依赖退出码，且对「假模型 id」「资格失败」「零产出」三种已知失败形态各有一条测试
- [ ] 模型回读机制存在（或明确记录「官方不提供，故无法回读」及其风险）
- [ ] 离线可测：测试里不 spawn 真 `agy`
- [ ] 彩野测试至少跑通一段，成绩与 `ds-flash` 可横比
- [ ] 仓库隔离方案已定，且有一条「调用后 `git status` 必须干净」的回归检查
- [ ] `uv run pytest -q` 全绿
- [ ] 结论文档：`docs/ops/` 下一份，或直接追加进 `paseo-antigravity-probe.md` §十
      （若追加，注意那份文档已经很长，考虑改名——它现在讲的已经不只是 paseo 了）

## 10. 为什么值得做（背景，别丢）

probe §9.4 的实测：同一份 760KB prompt、同一个 SEG-4 session 1（334 行），

| 通道 | 改动 | 命中 | 精确 | 召回 | 逐字同定稿 |
|---|---:|---:|---:|---:|---:|
| **gemini-3.7-flash** | 29 | 28 | **97%** | **85%** | **23** |
| fable-wf ※ | 26 | 26 | 100% | 79% | 20 |
| ds-flash ※ | 10 | 10 | 100% | 30% | 7 |

`※` = 参与过该段裁决、**有循环优势**（定稿就是从它们的候选里裁出来的）。
**gemini-3.7 没有循环优势，召回却高过 `fable-wf`**——这是本项目做过的所有外部通道
评测里第一次出现。b120 单批上它用 9 次改动拿到 100% 召回（grok-4.5 也拿过 100%，
但用了 30 次改动换，精确率 27%）。

**即：这条通道的质量已经不是问题了，剩下的全是机械层的对接工作。** 这与
2026-08-12 的结论（§8.4「暂不投入适配」）正好相反，**变的是模型不是装置**——
两轮用的是同一份 prompt、同一套派发形态。
