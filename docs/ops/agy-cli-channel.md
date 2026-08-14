# `agy` CLI 通道对接（2026-08-14）

> 执行 `docs/ops/agy-cli-channel-handoff.md` 所述任务。本文是该 handoff §9
> 验收清单要求的结论文档。
>
> 前置背景在 `docs/ops/paseo-antigravity-probe.md`（四轮探针）。**那份文档的
> §一（失败全部 rc=0）与 §9.6（经 paseo 派发）两条结论在本轮被修正/作废**，见 §4、§1.2。

---

## 0. 结论先说

**通道已接通并跑通一段真实彩野测试，成绩不劣于 `ds-flash`。** 代码是
`tools/agy_client.py`（新）+ `tools/ayano_test.py` 的 `--channel` 接线。

| 验收项（handoff §9） | 状态 |
|---|---|
| 官方文档要点写进 docstring，查不到的标注 | ✅ §1 |
| 架构选择已定并写明理由 | ✅ **选（乙）**，§2 |
| `stream-json` 实测事件 schema 入库 | ✅ §3 |
| 判据不依赖退出码，三种失败形态各有测试 | ✅ §4，`tests/test_agy_client.py` |
| 模型回读机制 | ⚠ **只有回声，不是独立确认**——§4.3 如实记录 |
| 离线可测（不 spawn 真 agy） | ✅ 48 个用例全部注入假 runner |
| 彩野测试跑通、与 ds-flash 可横比 | ✅ §6，**15/15 对**（ds-flash 同段基线 13 对 2 部分对） |
| 仓库隔离方案 + `git status` 回归检查 | ✅ §5，约 45 次真实调用后零污染 |
| `uv run pytest -q` 全绿 | ✅ **1228 passed, 1 skipped**（§7 有一条环境注意事项） |

**但有一件事必须先看**：§1.2 —— **`search_web` 关不掉**。这条通道能上网查
《セカンドノベル》剧情，而彩野测试正是考这个。本次靠**事后检测**兜住了，
但那是止损不是预防。**这是本轮最重要的发现，优先级高于其余所有内容。**

---

## 1. 官方文档查证结果

来源：<https://antigravity.google/docs/cli/headless>、`/docs/cli/permissions`、
`/docs/cli/settings`、`/docs/cli/sandbox`、`/docs/cli/using`。

### 1.1 查到的

| 项 | 结论 |
|---|---|
| `--output-format` | `text`（正文进 stdout、诊断进 stderr）/ `json`（单个对象）/ `stream-json`（NDJSON） |
| `result` 载荷 | `conversation_id`/`status`/`response`/`error`/`duration_seconds`/`num_turns`/`structured_output`/`usage` |
| `status` 枚举 | `SUCCESS｜ERROR｜CANCELED｜INTERRUPTED｜INVALID｜WAITING｜RUNNING` |
| `usage` | `input_tokens`/`output_tokens`/`thinking_tokens`/`cache_read_tokens`/`total_tokens` |
| `--json-schema` | 收 schema 串/文件路径/基元类型名；结果落 `structured_output`；**对 stream-json 只作用于最终 result** |
| `--continue` / `--conversation <id>` | 续接会话 |
| `--sandbox` | = 设置项 `enableTerminalSandbox`，**只管 agent 发起的终端命令**；macOS 走 `sandbox-exec`，限制绝对路径文件访问与裸 TCP |
| 权限模型 | `deny > ask > allow`；action 类别只有 `read_file`/`write_file`/`read_url`/`execute_url`/`command`/`unsandboxed`/`mcp` |
| workspace | 「active project directory 内的读写自动放行」，其外默认 Ask；headless 无法弹窗，故**外部写默认软拒** |
| 配置文件 | 只有用户级 `~/.gemini/antigravity-cli/settings.json`，**没有 per-project 配置** |

**⚠ 关于 `usage`：订阅制通道居然给了 token 数。** 故 handoff §6 设想的「拿不到
token 就整列不写」降级**用不上**——台账四列全部有真值。

### 1.2 ⚠⚠ 最重要：`search_web` 无法用配置关闭

`agy` 的工具表有 **56** 项（`init.tools` 实测），其中能引入外部知识的至少有
`search_web` / `read_url_content` / `open_browser_url` / `read_browser_page` /
`browser_subagent` / `execute_browser_javascript` / `call_mcp_tool`。

这正是 `api_client._validate_tools` 拼死防守的失效模式：**受试模型上网查剧情，
不看译文也能答对，彩野测试静默失效**。三次实测（隔离 HOME + 自带 settings.json）：

| 关法 | 结果 |
|---|---|
| `permissions.deny: ["read_url(*)","execute_url(*)","mcp(*)","command(*)"]` | ❌ `search_web` 照跑 |
| 追加 `deny: ["search_web(*)","read_url_content(*)","open_browser_url(*)"]` | ❌ 且 agy 回写 settings 时**静默丢弃**这三条（不是合法 action 名） |
| `toolPermission: "strict"`（`init.permission_mode` 回读确认已生效） | ❌ `search_web` 照跑 |

两次它都真的搜到了并复述出「15 分钟顺行性遗忘／五年前事故／亲友之死」——
**恰好就是题库要考的东西**。根因：官方 action 类别里根本没有 `search_web` 这一类。

**故本通道的立场是「预防不可得，检测必须有」**：`agy_client.chat()` 扫描事件流里
每一次工具调用，命中 `FORBIDDEN_TOOLS` 即抛 `AgyContaminated` 作废本次调用。

⚠ **检测消不掉已经发生的污染**，只能让它可见且不进结论。也**不要**因为「提示词里
没让它搜」就删掉这道闸——它防的正是模型**自发**去搜。
（本次两轮真实全跑共 45 次调用，`tools_used` 里零命中，即它没有自发搜索。
这是好消息，但不能当成保证。）

### 1.3 查不到的

- `--add-dir` / `--project` / `--new-project` 的确切 workspace 语义。官方站**没有
  CLI flag 参考页**（`/docs/cli/reference` 只讲斜杠命令与配置键），只有
  `agy --help` 那一句话。**本轮未使用这三个 flag**，理由见 §5。
- **配额/计费口径**：只有 TUI 的 `/credits`、`/usage` 斜杠命令，**无 headless 等价物**。
  故台账里记不了「滚动用量 %」，改记 `wall_seconds`（§8）。

---

## 2. 架构选择：**（乙）另起 `tools/agy_client.py`**

handoff §4.1 给了甲（扩 `PROVIDERS`）／乙（另起模块）两条路，倾向乙但要求自行判断。
**确认选乙**，理由：

1. `PROVIDERS` 表项形状是 `{url, key_env, default_model}`——三个键对 subprocess
   通道**一个都不成立**。
2. `api_client` 的 docstring 与大半注释在讲 Responses API、SSE 逐 chunk 静默超时、
   429 `Retry-After`、`cached_tokens` 命中率——**对本通道全不适用**。塞进去会让那份
   写得很准的文档变成半真半假，而这个项目已经吃过一次「一条声称在防守、实际不防守的
   注释比没有注释更坏」的亏（`ayano_test.VERDICT_WORDS` 上方的记录）。
3. 两边的**失败分类学完全不同**：那边是 HTTP 码/流中断/重试；这边是退出码、
   权限软拒、工具污染、模型冲突。混在一个 `chat()` 里只会互相污染语义。

**没有重复造轮子的地方**：台账**读侧**口径（`ledger_token`/`summarize_ledger`）直接
从 `api_client` import——消费口径必须只有一份。只有写侧多一列 `wall_seconds`，自成一份。

调用方代价（handoff 预见的那条）：`ayano_test` 加了一个 `--channel` 开关，
默认 `deepseek`，既有调用方一字不用改（有回归用例守着）。

---

## 3. `--output-format stream-json` 实测事件 schema

以下是**真机捕获**（agy 1.1.12，2026-08-14），不是照文档抄的。

```jsonc
// ① 一条 init（早期失败时可能**根本没有**，见下）
{"event":"init","conversation_id":"a5565d8b-…",
 "init":{"model":"gemini-3.7-flash-low",           // ← 请求串的回声，非解析后型号
         "cwd":"/…/probe1",
         "tools":["ask_permission",…56 项…],
         "permission_mode":"request-review"}}

// ② 若干 step_update。同一 step_index 会出现 ACTIVE→DONE 两条（或 →ERROR）
{"event":"step_update","step_update":{"step_index":0,"state":"DONE","step_type":"user_input"}}
{"event":"step_update","step_update":{"step_index":2,"state":"DONE","step_type":"agent_response",
   "text_delta":"收到\n","duration_seconds":1.955,"usage":{…}}}
{"event":"step_update","step_update":{"step_index":3,"state":"ACTIVE","step_type":"tool",
   "tool_name":"write_to_file","tool_info":{"name":"write_to_file","parameters":{"TargetFile":"…"}}}}
{"event":"step_update","step_update":{"step_index":6,"state":"ERROR","step_type":"tool",
   "tool_name":"write_to_file",
   "tool_info":{"name":"write_to_file","parameters":{…},
                "error":{"type":"TOOL_ERROR",
                         "message":"User denied permission for write_file(/…/x.txt)."}}}}

// ③ 一条终结 result（载荷 == `--output-format json` 档的整个输出）
{"event":"result","result":{"conversation_id":"a5565d8b-…","status":"SUCCESS",
  "response":"收到\n","duration_seconds":3.189,"num_turns":1,
  "usage":{"input_tokens":16365,"output_tokens":23,"thinking_tokens":19,
           "cache_read_tokens":0,"total_tokens":16388}}}
```

实测出来的、**文档没写**的几条：

- **早期失败只有一条 `result`，没有 `init`**（模型名非法、参数冲突都属此类）。
  解析器不能假定 `init` 一定先到。
- `step_type` 实际见过 `user_input` / `agent_response` / `tool` / `checkpoint` /
  **`unknown`**（文档的「closed vocabulary」说法要打折扣）。
- `text_delta` 挂在 `step_type=="agent_response"` 的 step 上；短输出会**一次给完**，
  长输出才分多条。故「按 delta 计数估算 token」在这里不可靠（本模块不这么做，
  usage 恒从 result 取）。
- `usage` 在 `step_update` 上也会出现（分步计量），但**只有 result 上的是全量**。

---

## 4. 判据：退出码可用，但远远不够

### 4.1 ⚠ 修正探针 §一

handoff §5 依据探针 §一断言「这条链上的失败**全部**返回退出码 0，绝不能用退出码判断」。
**该结论在 agy 1.1.12 上已不成立**：

| 形态 | rc | status | 错误在哪 |
|---|---|---|---|
| `--model __bogus_model_id__` | **1** | `ERROR` | stderr（text 档）／`result.error`（json 档） |
| `--model <带档位后缀> --effort <档>` 冲突 | **1** | `ERROR` | 同上 |

探针记的 `rc=0` 多半是被 `$(...)`／管道吞掉了退出码。**但结论方向仍然对**——
最危险的那一类照样 rc=0：

| 形态 | rc | status | 实况 |
|---|---|---|---|
| 工具权限被拒、**一个字没产出** | **0** | **SUCCESS** | `response` 为空串，真相只在 stderr 的 `no output produced` |
| 上网查了答案再作答 | **0** | **SUCCESS** | 看 `response` 完全正常 |
| 探针 §8.1 的「零改动」 | **0** | **SUCCESS** | 形式完美、实质为空 |

### 4.2 故判据是**多层与**

`agy_client.chat()` 依次校验，任何一层不过即抛并写一行 `failed` 台账：

1. `rc == 0`
2. 收到了 `result` 事件（否则＝流被截断）
3. `result.status == "SUCCESS"`
4. **未命中 `FORBIDDEN_TOOLS`**（→ `AgyContaminated`）
5. `result.response` 去空白后非空（＝零产出闸）
6. `init.model` 与请求值一致

三种已知失败形态各有一条离线用例：`test_bogus_model_id_is_rejected`、
`test_eligibility_failure_is_rejected`（刻意造 **rc=0** 型，逼 status 那层独立生效）、
`test_zero_output_is_rejected`。

### 4.3 ⚠ 模型「回读」只是回声

`init.model` 回读的是**我们请求的那个字符串**，不是远端解析后的真实型号。
探针 §7.1 那次「静默落到别的模型」正是回声看不出来的形态。本模块仍比对它
（不符即抛），但**它证明不了远端真用了这个模型**。

真正的强证据是**假 id 现在会被拒**——说明 flag 确实被校验了。另有一条弱旁证：
`--effort low` vs `high` 的 `thinking_tokens` 实测 19 vs 76，effort 确实在起作用。

**官方不提供独立的模型回读手段**，这是当前能做到的上限，风险如实记录在此。

### 4.4 顺手实测出来的两条硬约束

- **模型档位后缀与 `--effort` 互斥**：`--model gemini-3.7-flash-low --effort high`
  → `conflicts with`。故本模块**只发裸模型名 + `--effort`**，并在组装参数前就拒绝
  带后缀的模型名（`test_suffixed_model_with_effort_is_refused`）。
- **`--print` 是带值参数，必须放最后**（探针 §7.4 那个吞掉正文的事故）。
  `test_argv_invariants` 把这条钉死。

---

## 5. 仓库隔离：靠机制，不靠提示词

探针 §9.3(a)：派发词写了「不要在仓库下改任何文件」，它照样跑 `polish_context.py`
覆盖了已 tag 段的 `plan.json`，而且报告里一个字没提。

**根因定位到 `--dangerously-skip-permissions`**——探针历轮都带着它，而它的作用正是
「auto-approve all tools」。本模块的做法：

1. **绝不传 `--dangerously-skip-permissions`。** 实测不带它时，workspace 之外的
   `write_to_file` 被拒：`User denied permission for write_file(/Users/fotile96/Zndnovel/…)`。
2. **workspace 默认是临时目录，用完即删**，绝不用仓库目录（`test_repo_is_never_the_workspace`）。
3. **`--sandbox` 默认开**：macOS 走 `sandbox-exec`，限制 agent 发起的**终端命令**的
   文件访问与裸 TCP。§9.3(a) 那次污染正是终端命令造成的，这道闸对症。
   ⚠ 但它只管终端命令，不管 `write_to_file` 工具——后者靠第 1、2 条。
4. **不让它写文件，产物一律从 `result.response` 取回**，由调用方自己落盘。

第 4 条同时绕开了探针 §9.2「它把文件内容打进 stdout 而不落盘」：**对本模块而言，
打进 stdout 本来就是唯一约定的交付方式。**

**顺带一个反直觉的实测**：agent 眼里的「当前目录」**不是进程 cwd**。让它写相对路径
`inside.txt`，文件落在了 `~/.gemini/antigravity-cli/scratch/`。所以「把 cwd 设成输出
目录再让它写相对路径」这条路走不通——这也是第 4 条的另一个理由。

### 回归检查

- 机械层：`test_repo_is_never_the_workspace` 断言 workspace 不在 `REPO` 下、且用完即删。
- 真机层：**每次真实调用后 `git status`**。本轮约 45 次真实 agy 调用（探针 9 次 +
  彩野两轮全跑 30+15）之后，worktree `git status` 只有本次改动的 4 个文件，
  故意投放的两个越权写目标 `POLLUTION_FILEWRITE.txt` / `POLLUTION_SHELL.txt`
  **均未生成**。

---

## 6. 彩野测试成绩：与 `ds-flash` 横比

段 `seg1-s2`（15 题，上下文 48,039 字符，缺译 0 行）。

| 受试通道 | 判分通道 | 对 | 部分对 | 错 |
|---|---|---:|---:|---:|
| **agy / gemini-3.7-flash (effort=high)** | **deepseek**（与基线同判分员） | **15** | 0 | 0 |
| agy / gemini-3.7-flash | agy（自判） | 13 | 2 | 0 |
| deepseek-v4-flash（2026-08-02 归档基线） | deepseek | 13 | 2 | 0 |

**即在判分员钉死的前提下，agy 通道 15/15，不劣于 ds-flash 的 13/15。**

### ⚠ 一个必须记的方法学问题：判分通道要钉死

首轮我让受试与判分**走同一条通道**，得到 13 对 2 部分对——与基线数字**完全相同**，
看起来是漂亮的「持平」。但那是**两个变量一起动**（受试换了、判分员也换了），
分数差说不清是谁造成的。把判分钉回 deepseek 之后，结论从「持平」变成「更好」。

故本轮给 `ayano_test` 加了 `--judge-channel`，并让报告在**判分与受试同通道时自动打一句
免责**（`test_same_channel_judging_is_flagged_in_the_report`）。**做通道横比时请始终
`--judge-channel deepseek`。**

### ⚠ 这条通道判不了「真读出来 vs 猜」

`agy` **不下发推理正文**（只给 `thinking_tokens` 计数），故 `reasoning_text` 恒为空串，
报告里「CoT 摘要」一栏恒为「无 CoT」。而彩野测试的设计目的之一正是**看 CoT 判断受试者
是从译文读出来的还是猜的**（`api_client` docstring 第 1 条理由）。

**这是通道能力差异，不是 bug，但它意味着 agy 通道的彩野报告比 deepseek 的少一维证据。**
`--channel` 的帮助文本里写明了这一点。

---

## 7. 测试与环境

`uv run pytest -q` → **1228 passed, 1 skipped, 0 failed**。

⚠ **新 worktree 的一个坑（与本次改动无关，但会让人误判）**：初次在全新 worktree 跑全量
测试会红 **19** 条。全部是 `real_data`/`real_lane`/`real_corpus` 类用例，因为它们读的是
**gitignore 掉的生成物**，只存在于主工作树：

```
pilot/lanes/opus/data/{batches,final,ledger,ledger_extra}.jsonl、dag.json、scene2card.json
build/{select_option_map.json,select_ink_verify.json,extra_derived.jsonl}
```

补齐后 19 条全绿（已实测）。**注意 `build/` 不要整目录软链到主工作树**——那是工具的写入
目标，链过去等于让 worktree 里的任何一次 bake 写进主树。本次只复制了那三个**输入**文件。

新增用例 **48** 条（`tests/test_agy_client.py` 22 + `tests/test_ayano_test.py` 追加 5，
其余为既有）。**全部注入假 runner，不 spawn 真 agy。**

---

## 8. 台账

`data/api_ledger.jsonl` 的列名与 HTTP 通道保持一致（同一个账本，`summarize_ledger`
按列汇总，列名一漂就统计不到一起去），多两列：

```jsonc
// 真实行（本轮 seg1-s2 首题）
{"ts":"2026-08-14T11:41:21+0800","provider":"antigravity","model":"gemini-3.7-flash",
 "purpose":"ayano:seg1-s2:q1",
 "prompt_tokens":89316,"completion_tokens":962,"cached_tokens":0,
 "reasoning_tokens":840,"wall_seconds":15.74,"effort":"high"}
```

- `wall_seconds`：agy 是订阅制、拿不到配额百分比（§1.3），耗时是判费效比的替代依据。
- `failed: true`：只在失败行上出现。**失败也入账**——请求已发出、token 已花掉，
  不记就系统性低估（与 `api_client` 的 `partial` 行同理）。
- `usage` 缺失时写 `-1` 哨兵 + `estimated`，交给 `ledger_token` 算 unknown，
  **不写 0**（写 0 会被 `summarize_ledger` 当真实值求和＝静默低估）。

⚠ **通道评测/探针一律用 `--ledger` 指向别处**（本次新增的 CLI 参数），
不要把实验数据灌进生产账本。本轮两次全跑都写在 `work/out/` 下。

本轮实耗（30 + 30 次调用，两轮全跑）：agy 侧 in 1,145,675 / out 37,451 /
thinking 33,344 / cached 441,933，墙钟合计 354.6s。

---

## 9. 下一步（润色轨，本轮**未做**）

handoff §8 的推进顺序明确要求「先接彩野测试，跑通并可横比之后**再谈润色轨**」。
故润色轨没有动。接它之前至少还要解决：

1. **`jp_tail` 70% 不合规**（探针 §9.3(b)）。本轮没碰。现在多了一个工具：
   `--json-schema` 能强制**结构**，但管不了「必须等于末 8 字」这种**内容**约束——
   所以它救不了 `jp_tail`，别指望。倾向 handoff 给的第 2 条（派发词里给可执行的取法）。
   ⚠ 第 3 条（ingest 侧放宽）**要慎重**：`jp_tail` 是回显完整性校验，放宽等于拆掉一道
   防错位的闸，得先想清楚拿什么替代。
2. **760KB prompt 走 argv 的可行性**。实测本机 `ARG_MAX` = 1,048,576 字节（argv+envp
   共享，当前 env 仅 1,936 字节），用 `/bin/echo` 逐档探到 **1000 KB 仍 OK**。
   故 760 KB **字节**的 prompt 有约 25% 余量；但若那是 760 K **个 CJK 字符**
   （UTF-8 ≈3 字节/字 ≈ 2.2 MB）**必然 E2BIG**。接润色轨前先量准这个数。
   真超了的话，`--continue` 分段投喂是现成的出路。
3. **静默角色名损坏**（探针 §9.3(c)，`アヤノ`→`アヤ野`）。本轮**未处理**，
   它需要 glossary v17 把五个片假名角色名登记进 `active.json`，
   **那是控制会话/用户的裁量，不该由本轨自行改 glossary**。探针已测好代价
   （新增 W2 警仅 2 条，且都是正当的呼名换代词）。
4. **`--json-schema` 的真实约束力未实测**。本轮只查了文档没有真发过——
   接润色轨（334 行 JSONL 契约）之前值得单独探一次。

---

## 10. 与 paseo 的关系

**本轮完全没走 paseo**，按用户 2026-08-14 的裁定（社区 extension、非官方支持、
功能不完整）。探针 §9.6 那张表里「经 paseo 派发：❓ 未复测，值得复测」一行**作废**。

对应地，探针 §7.2（`bypassPermissions` 建不出 agent）与 §7.3（`default` 档写文件静默
无效）**不必再修**——它们是 paseo 侧的缺陷，而直连 `agy` 这条路已经证明可用。
这条也写进了 `tools/agy_client.py` 的模块 docstring，免得后人读探针文档时以为那是路线。
