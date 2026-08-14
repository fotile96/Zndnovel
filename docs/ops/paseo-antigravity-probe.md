# paseo `antigravity-acp` 通道摸底（2026-08-12）

> 用户 2026-08-12 在 paseo 里新增了 antigravity provider，要求实测「怎么发射」并评估
> `gemini-3.5-pro` 的产出质量，供后续在开发轨正式适配。
>
> **结论先说（两轮）**：发射路径已完全摸清并记录在下；**产出质量仍未评估**。
> 第一轮（2026-08-12 上午）被 Google 侧资格校验挡死；用户解决资格后的第二轮
> 又撞上三道各自独立的墙——模型选不了、宽松档建不出 agent、default 档下写文件
> 静默无效。详见 §七。另外「`gemini-3.5-pro`」这个型号**在真实模型表里不存在**（§3）。

## 一、⚠ 这条链上的失败**全部返回退出码 0**

这是本次摸底最该记住的一条，也是本项目一贯警惕的形态（命令不报错、看起来跑完、
实际零产出）：

| 环节 | 现象 | 退出码 |
|---|---|---|
| `paseo run`（agent 创建失败） | stdout 里一段 `{"error":{"code":"AGENT_CREATE_FAILED","message":"Failed to create agent: [object Object]"}}` | **0** |
| `paseo run`（agent 建出来但跑挂） | `{"status":"error", ...}`，**真实报错不在 stdout 里** | **0** |
| `agy --print` 直接跑（绕开 paseo） | `Error: Eligibility check failed: ...` | **0** |

**所以：绝不能用退出码判断成败。** 判据只有两个——

```bash
paseo logs <agentId>       # 真实报错在这里，stdout 里那句 "[object Object]" 毫无信息量
ls -l <落盘目录>            # 产物真的落了没有
```

首次派发时我拿 SEG-4 session 1 发了一次 `gemini-3.5-pro`，退出码 0、
`Created workspace` 也打了，**落盘目录是空的**。

## 二、发射形态（已实测通）

```bash
paseo run --provider antigravity-acp/<model> \
          --mode <default|plan|bypassPermissions> \
          --env "PATH=$PATH" \
          --json "<提示词>"
```

四个必须知道的点：

1. **provider id 是 `antigravity-acp`，不是 `antigravity`。**
   写 `antigravity` 会得到 `Unknown provider: antigravity`。

2. **`--env "PATH=$PATH"` 不能省。** 该 provider 是个 ACP 壳，实际去调本机可执行文件
   `agy`（Antigravity CLI，本机在 `~/.local/bin/agy`，v1.1.12）。**paseo daemon 的 PATH
   不含 `~/.local/bin`**，于是报

   ```
   Internal error: failed to run agy: Executable not found in $PATH: "agy"
   ```

   而我的交互 shell 里 `which agy` 是有的——**别被自己 shell 的 PATH 骗了，跑 agent 的是 daemon**。
   注入 PATH 是每次派发都要带的权宜之计；**更彻底的修法是让 daemon 继承正确的 PATH**
   （从带 `~/.local/bin` 的 shell 里 `paseo restart`，或把 `agy` 软链到 daemon 已有的
   PATH 目录）。开发轨正式适配时应当选后者，不要把 `--env PATH` 写进每条派发指令。

3. **mode 枚举是 provider-specific 的**（deepseek 那条教训在这里同样成立），
   `antigravity-acp` 的合法值是 `default / plan / bypassPermissions`。
   ⚠ `paseo provider ls` 那张表里显示的是**人读标签**（`Standard, Plan Mode, Skip Permissions`），
   **不是 wire 值**，照抄标签会被拒。

   **查枚举的正道是 `paseo inspect <agentId>`**，它一行里同时给出两者：

   ```
   AvailableModes  default (Standard), plan (Plan Mode), bypassPermissions (Skip Permissions)
   ```

   我最初用的是「故意传非法值让报错列全枚举」那招（SEG-1 的发现法），也管用，但
   ⚠ **`paseo run` 是先建 workspace 再校验 mode**，所以一次探针就白烧一个 workspace。

4. **`--json` 只影响 stdout 的格式，不影响错误可见性**（真实报错仍只在 `paseo logs` 里）。

## 三、⚠ `paseo provider models antigravity-acp` 的输出是**错的**

paseo 报的模型表：

```
gemini-3.5-flash / gemini-3.5-pro / gemini-3.5-pro-experimental / gemini-3.5-flash-experimental
```

`agy models`（**真实来源，且这条命令不撞资格门，可以随时核对**）：

```
gemini-3.6-flash-high / -medium / -low
gemini-3.5-flash-high / -medium / -low
gemini-3.1-pro-high / -low
claude-sonnet-4-6 / claude-opus-4-6-thinking / gpt-oss-120b-medium
```

**两张表没有一个 id 对得上。** 具体后果：

- **用户点名的 `gemini-3.5-pro` 根本不存在。** 真实表里 pro 只有 `gemini-3.1-pro-high/low`；
  3.5/3.6 只有 flash。
- **请求一个不存在的 id 不会报错，会静默落到 provider 默认。** 实测：分别用
  `--provider antigravity-acp/gemini-3.5-pro` 与 `.../gemini-3.5-flash` 发了两个 agent，
  `paseo inspect` 显示两者的 `Model` **都是 `gemini-3.6-flash-high`**。

  ⚠ 这正是 `p4-seg1-polish-handoff.md` 警告过的形态——「用猜测的字符串要么直接失败，
  要么（更危险）静默落到另一个模型上，使候选、准入结果、计费全部张冠李戴」。
  **这次实证到了，而且骗过 paseo 自己的模型表。**

- **有意思的是**：在 `agy` 还没跑起来（PATH 未注入）的那两个 agent 上，`inspect` 显示的
  `Model` 是我请求的字符串（`gemini-3.5-pro`）——**paseo 只是把它原样记下来了**；
  真正到达 `agy` 之后才被换成真实型号。所以**必须在 agent 真的跑起来之后再 inspect**，
  创建时刻的 `Model` 字段不可信。

- **effort 编在模型 id 的后缀里**（`-high/-medium/-low`），不像 fable 车道那样是独立参数。
  `agy` 自己另有 `--effort low|medium|high`，但经 paseo 派发时选型号即选 effort。

**开发轨适配时的硬要求：模型名以 `agy models` 为准，不要读 paseo 的 provider 表；
派发后用 `paseo inspect` 回读实际型号并与预期比对，不符就作废重来。**

## 四、当前的阻断：账号/地区资格

PATH 修好之后，报错变成一条确定性的结论：

```
agy failed: Error: Eligibility check failed: Your current account is not eligible
for Antigravity, because it is not currently available in your location.
```

- **不是 paseo 的问题**：直接 `agy --print --model gemini-3.5-pro "…"` 绕开 paseo，
  报同一条错。
- **不是模型的问题**：`gemini-3.5-flash` 撞同一道门。
- **`agy models` 却能正常返回**——说明二进制安装与基本连通都是好的，
  卡的是账号侧的 eligibility。

**故本次没能评估任何产出质量。** 这一节留空不是遗漏：在资格问题解决之前，
质量评估无从谈起，也不该拿别的模型的结果冒充。

### 资格解决后，接着做什么

1. 复跑本次那条派发（提示词已存档：见下），落盘到**镜像目录**而非生产保税仓；
2. 用镜像目录跑真实的 `polish_ingest`（判据与生产完全相同，见 §五）；
3. 与同一 session 的 `fable-wf` / `ds-flash` 候选做三方对照：改动率、`adjudicate` 数、
   gate hard/warn、以及最关键的**真错译发现力**（SEG-0 的实测口径：fable-wf 抓出全部
   12 条真错译而 ds-flash 一条没抓到——发现力与合规性是两个维度，不能互相替代）。

## 五、测试怎么做才不污染生产（本次已搭好）

**不要让测试通道往 `pilot/polish/<seg>/raw/<channel>/` 里写。** 那个路径一旦被
`polish_ingest` 认领就会进保税仓、进 `triage`、占裁决队列——用一次实验改变一个在产
SEG 的形状，代价不对等。

本次的做法是搭一个**镜像 seg 目录**，让测试输出走 `polish_ingest` 的**真实代码路径**
（jp_tail、锁定 id、批内重复、错位判定全都照跑），但候选写进镜像：

```bash
M=<scratchpad>/mirror
mkdir -p $M/pilot/polish/<label>/raw/<test-channel>
ln -s <repo>/pilot/polish/<label>/frozen $M/pilot/polish/<label>/frozen
cp <repo>/pilot/polish/<label>/{plan.json,manifest.json} $M/pilot/polish/<label>/
# 派发时把落盘路径指向 $M/.../raw/<test-channel>/b<N>.out
# 验证：polish_ingest.ingest(label, channel, batch, repo=$M)
```

`frozen/` 用软链（只读，省一份 700KB+ 的拷贝），`plan.json` 必须**复制**
（ingest 要按 `prompt_hash` 查该批，读的是这一份）。

## 六、本次用过的命令与产物

```bash
paseo provider ls                                  # provider id 与可用性
paseo provider models antigravity-acp              # ⚠ 输出不可信，见 §3
agy models                                         # ✅ 真实模型表
paseo inspect <agentId>                            # AvailableModes / 实际 Model
paseo logs <agentId>                               # 真实报错唯一可见处
paseo delete <agentId>                             # 清理测试 agent（本次清了 4 个）
```

提示词存档：`<scratchpad>/gem-s1.txt`（SEG-4 session 1，334 行应出稿，
落盘指向镜像目录）。scratchpad 会随会话销毁，正式适配时应把它固化进 `prompts/` 或
handoff 里——本文只记形态，不记那 2933 字节的正文。

---

## 七、第二轮（2026-08-12 下午，用户解决账号资格之后）

资格确实通了：`agy --print "回答两个字：收到"` → `收到`。**但仍然一行译文都没产出**，
连撞三道各自独立的墙。**§四 的资格阻断已解除，以下三条取代它成为当前阻断。**

### 7.1 ⚠ 模型选不了，而且**不是 paseo 的锅**

用户随后在 paseo 侧手动补进了 `gemini-3.6-flash-high` 与 `gemini-3.1-pro-high`
两个真实 id。**补了也没用**——实测请求下列三个 id，`paseo inspect` 回读的实际模型
**全部是 `gemini-3.6-flash-high`**：

| 请求 | 实际 |
|---|---|
| `gemini-3.1-pro-high`（真实且已补进 paseo 表） | `gemini-3.6-flash-high` |
| `gemini-3.5-flash-high`（真实） | `gemini-3.6-flash-high` |
| `claude-opus-4-6-thinking`（真实） | `gemini-3.6-flash-high` |

**定位到 `agy` 这一层，与 paseo 无关**：直接跑 `agy --model __bogus__ …`
**不报错**；`agy --model gemini-3.1-pro-high …` 与 `agy --model gemini-3.6-flash-high …`
三次自报均为 `Gemini 3.6 Flash (High)`。即 **`agy` 接受 `--model` 但既不校验也不生效**。

（自报模型身份本身不是强证据，但「假 id 不报错」是——它说明这个 flag 根本没被校验；
再叠上 `paseo inspect` 的独立回读一致，结论可靠。）

**后果**：`gemini-3.1-pro-high`（用户原本想测的「pro」的最近替身）**目前根本跑不到**。
本账号在这套装置下只能跑 `gemini-3.6-flash-high` 一个模型。修法在 Antigravity/agy 侧，
不在 paseo，也不在 provider 表。

### 7.2 ⚠ `bypassPermissions` 建不出 agent

```
paseo run --provider antigravity-acp/... --mode bypassPermissions --env "PATH=$PATH" --json "说ok"
→ {"error":{"code":"AGENT_CREATE_FAILED","message":"Failed to create agent: [object Object]"}}
```

资格、PATH 都已就绪时复测，**仍然失败**；同参数换 `--mode default` 立刻成功（`idle`）。
所以 `AvailableModes` 里列着的 `bypassPermissions` **是列着但不能用**。

⚠ 第一轮我把首次派发的 `AGENT_CREATE_FAILED` 归因给了资格/PATH——**归因错了**，
那是本条这道独立的墙。两轮都用了 `bypassPermissions`，两轮都在同一处失败。

### 7.3 ⚠ `default` 档下写文件**静默无效**

用 `--mode default` 跑 SEG-4 session 1 的完整任务，实况：

- 它确实在工作：把 748KB 的 prompt **分片读了 25 次以上**，`Search` 了批号，
  在自己的 brain scratch 目录里写了个 `parse_batches.py` 并执行；
- 然后 **回合结束**，`status: completed` / `idle`；
- **落盘目录 0 个文件；`--filter text` 里 0 条模型文字输出；`--filter errors` 无活动；
  `PendingPermissions` 为空；permissions 事件也没有。**

`paseo send` 唤它继续，它会重新工作并出现
`[Edit] …/raw/gemini-test/b118.out` 事件——**但那个文件始终不存在**。
独立探针任务（「往 X 写一行 hello」）同样：`[Edit]` 有、文件没有。

**即：写操作既不落地、也不报错、也不请求批准。** 在 `default` 档下这条通道
无法交付任何产物，而且它的失败形态是本项目最警惕的那种——全链路「看起来正常」。

### 7.4 唯一还没试的路：`agy` 自己的 `--dangerously-skip-permissions`

paseo 侧没有可用的宽松档（7.2），只能绕开 paseo 直接调 `agy`：

```bash
agy --dangerously-skip-permissions --print "<提示词>"
```

⚠ **参数顺序要紧**：`--print` 是**带值参数**（`--prompt` 是它的别名）。写成
`agy --print --dangerously-skip-permissions "<提示词>"` 会被解析成
「prompt＝`--dangerously-skip-permissions`」，于是它一本正经地给你讲解那个 flag，
而你真正的提示词被丢掉——又一个「不报错、结果全错」的形态。

**这条路本次没能实测**：`--dangerously-skip-permissions` 被 Claude Code 的沙箱分类器
拦下（这是本机 harness 的策略，不是 agy 或 paseo 的问题），需要用户自己执行。
另需注意 `--print-timeout` 默认只有 5 分钟，334 行的任务必须显式调大。

### 7.5 附带观察：它对 748KB prompt 的消化方式

两个回合里它反复分片重读同一个 prompt 文件 25 次以上，并试图写脚本去解析批次，
最终没有产出任何文字。这**不能**作为质量结论（写操作本来就是坏的），但可以作为
一条待验的怀疑：**这条通道可能吃不下现有规模的 prompt**。
`fable-wf` 与 `ds-flash` 在同一份 748KB prompt 上都是一次通读、直接产出 334 行。

### 7.6 下一步（按代价从低到高）

1. **用户本机执行**（我这边被沙箱挡住）：
   `agy --dangerously-skip-permissions --print-timeout 60m --print "$(cat <scratchpad>/gem-s1.txt)"`
   —— 若能落盘 334 行，质量评估立刻可做（镜像目录已搭好，见 §五）。
2. 修 paseo 的 `bypassPermissions`（7.2）——这是让它成为**可派发生产通道**的前提，
   直连 `agy` 只能做一次性评估，进不了现有的双通道流水线。
3. 模型选择（7.1）要在 Antigravity/agy 侧解决，否则「选 pro」这件事无从谈起。

**在 1 走通之前，产出质量仍然是未知的，不要据本文任何内容推测它好或不好。**

---

## 八、第三轮：直连 `agy` 跑通了，**质量结论出来了**（2026-08-12）

用户授权后，绕开 paseo 直接执行：

```bash
agy --dangerously-skip-permissions --print-timeout 60m --print "$(cat <scratchpad>/gem-s1.txt)"
```

**这条路是通的。** SEG-4 session 1（334 行应出稿）：

- 5 个文件全部落盘，**行数逐批完全吻合**（b118:1 / b119:22 / b120:60 / b121:249 / b122:2）；
- 走**真实 `polish_ingest` 代码路径**（写进镜像目录）：**入仓 334，判死 0**；
- 硬规则 + W3 全过：R2a/R2b/R2c/P4-CTL/W3 **一处未命中**；
- **仓库零污染**：HEAD 未变，`git status` 只剩那两个他人会话的文件。

### 8.1 ⚠ 但它一行都没改

| | 改动 | 改动率 | 请裁 | 闸命中 |
|---|---:|---:|---:|---|
| **gemini-test**（gemini-3.6-flash-high） | **0** | **0.0%** | 1 | 无 |
| fable-wf | 26 | 7.8% | 0 | 无 |
| ds-flash | 10 | 3.0% | 0 | 无 |

**334/334 与 `frozen/opus.jsonl` 逐字节相同**（不做任何空白归一），`score` 全部恰为 90，
`note` 除一条外全为空。它唯一那条 `adjudicate=true`（id 10883）也不是发现，而是在解释
**自己为什么不改**（「依据 style.md v10，维持『アヤノ同学』」）——`zh` 与 opus 一字不差。

同一份 prompt 上，fable-wf 改了 26 行、ds-flash 改了 10 行；**它们改的每一行 gemini 都没碰**
（重叠 0）。本段最终定稿在这 334 行里改了 31 行，**gemini 命中 0 条**。

### 8.2 这个失败形态值得单独记：**形式完美、实质为空**

它通过了流水线上**每一道机械闸**——行数对、JSON 合法、id 不重不漏、jp_tail 全对、
锁定 id 零触碰、控制码计数全对、行宽不超。在 `polish_triage` 里它会整整齐齐落进
**桶 1（零改动）**，既不报错也不占裁决队列，**在任何报表上都看不出异常**。

**机械闸检测不出「一个什么都不做的通道」。** 唯一的探测器是**改动率画像**——
这也是 `channel_feedback.md` 每段都记 `实质改动 N（x%）` 的价值所在：
ds-flash 的 4.1%↔19.7% 摆动、fable-wf 的 7–8% 稳定，都是靠这个数看出来的；
0.0% 一眼就是异常。

⚠ **若这条通道将来接进生产，`polish_triage` 的自动清关逻辑对它是完全无害的**
（零改动不产生 patch），但它会**白占一条通道的成本**，并在「双通道并跑」的账面上
制造「已有两条通道复核过」的假象。适配前必须先解决 8.1。

### 8.3 这一轮的操作细节

- **`--print-timeout` 默认 5 分钟必须调大**（本次给了 60m；实际几分钟就返回了，
  与「它没做事」一致）。
- **参数顺序**：`--print` 是带值参数，flag 必须在它之前——见 §7.4 那个陷阱。
- **原始产物没有保存进仓库**：334 行与 opus 逐字节相同，除了「它照抄了」之外
  不携带任何信息，留着只是占地方。结论记在本文即可。

### 8.4 现在的状态与建议

| 项 | 状态 |
|---|---|
| 账号资格 | ✅ 已解决 |
| 直连 `agy` 派发 | ✅ 通（需 `--dangerously-skip-permissions` + 调大 `--print-timeout`） |
| 经 paseo 派发 | ❌ `bypassPermissions` 建不出 agent；`default` 档写文件静默无效（§7.2/7.3） |
| 选模型 | ❌ `agy --model` 不校验也不生效，只能跑 `gemini-3.6-flash-high`（§7.1） |
| **产出质量** | ❌ **零改动**，同 prompt 下 fable-wf 改 26 行、ds-flash 改 10 行 |

**建议：暂不投入开发轨适配。** 前三项都是别人家的 bug（paseo / agy），修不修不由我们；
而第四项说明**即便全修好，这条通道当前也交付不了价值**。

若要再评估一次，值得先变的是**变量而不是重试**——例如把 prompt 缩到单批规模，
判断 8.1 是「模型能力问题」还是「748KB prompt 吃不下」（§7.5 记的那个怀疑：
它在 paseo 侧曾把同一份 prompt 分片重读 25 次以上）。**在那之前，不要根据本次结果
断言 Gemini 3.6 Flash 的翻译能力**——本次测到的是「这套装置下它不干活」，
不是「它干不好」。

---

## 九、第四轮：`gemini-3.7-flash`（2026-08-14）——**质量结论翻转**

> 用户 2026-08-14：Google 发布 gemini-3.7-flash，agy TUI 里已可选，要求再测一次派发。
>
> **结论先说**：§8.1 的「零改动」不再成立。**这一轮它是迄今为止外部通道里质量最好的一个**
> ——在 334 行上召回 85%、精确 97%，**召回甚至高过带循环优势的生产通道 fable-wf（79%）**。
> 剩下的阻断全部是**机械层**（不写文件、jp_tail 不合规），且都像是可以靠派发词/工装解决的。
> **建议从「暂不适配」改为「值得适配」，但适配前必须先解决 §9.3 的三件。**

### 9.1 ✅ `agy --model` 这道墙倒了（§7.1 作废）

agy 版本仍是 **1.1.12**，但行为变了。两条独立证据：

```
$ agy --model __bogus_model_id__ --print "..."
Error: invalid model selection (--model "__bogus_model_id__" --effort ""):
  model __bogus_model_id__ is not recognized as a known model or custom model in settings
Available models: Gemini 3.7 Flash (High) / (Medium) / (Low) / Gemini 3.6 Flash ...
```

1. **假 id 现在被拒**（§7.1 时是静默接受并落到 3.6）——这是强证据，说明 flag 真的被校验了。
2. 显式 `--model gemini-3.7-flash-high` 后自报「Gemini 3.7 Flash」（弱证据，但与 1 一致）。

⚠ **那条报错仍然 `rc=0`**——§一「这条链上的失败全部返回退出码 0」**依旧成立**，
判据只能是产物本身。

`agy models` 现有 `gemini-3.7-flash-high/medium/low`，其余表项与 §3 同。

### 9.2 派发实况：**内容出来了，但没落盘**

派发（§8 的形态，只换 model）：

```bash
agy --model gemini-3.7-flash-high --dangerously-skip-permissions \
    --print-timeout 60m --print "$(cat gem37-s1-full.md)"
```

任务是 SEG-4 session 1（334 行应出稿、760KB prompt），落盘指向**镜像目录**（§五）。

| 项 | 结果 |
|---|---|
| 交卷 | **334 行，逐批行数完全吻合**（b118:1 / b119:22 / b120:60 / b121:249 / b122:2） |
| 硬锁 | 15 个 id **零出现** |
| JSON | 334/334 合法、字段齐全、id 不重不漏 |
| **落盘** | ❌ **0 个文件**——它把 334 行**全部打进了 stdout** |
| 文件块标题 | `### \`raw/<channel>/b118.out\`` ——**照抄了输出契约里的字面占位符 `<channel>`** |

即：**它把「写文件」理解成了「把文件内容打印出来」**。这与 §7.3（paseo default 档下
`[Edit]` 事件有、文件没有）是**不同**的形态——那次是写操作被吞掉，这次是**根本没打算写**。

**内容可回收**：从 stdout 按 `### ...b<N>.out` 分块提取，334 行全部还原，
走真实 `polish_ingest` 代码路径入仓（镜像目录）。本轮的质量结论就建立在回收出的这 334 行上。

### 9.3 ⚠ 三件必须在适配前解决

#### （a）**它在仓库里跑了 `polish_context.py`，覆盖了一个已完成 SEG 的 `plan.json`**

派发词里写了「不要在 /Users/fotile96/Zndnovel 下创建、修改或删除任何文件」。
跑完 `git status` 多出 `M pilot/polish/seg4-s3tail-s5/plan.json`：

```
- "prompt_hash":"d4d7389a675c3999..."     ← SEG-4 冻结时的真值
+ "prompt_hash":"a42338a38a72fb91..."     ← 被覆盖
```

**归因是确定的**：写进去的那个值恰好等于 `render('seg4-s3tail-s5', 1)` 当前输出的 sha256，
而**控制会话走的是库函数 `render()`（源码内无任何写操作，写 `plan.json` 只在 `main()` 里）**——
只有跑 CLI `polish_context.py --session 1 --out ...` 才会产生这个写入。已 `git checkout` 复原。

⚠ **这次污染是有后果的，不是无害的临时文件**：`plan.json` 是 `polish_ingest`
反查生产批 `prompt_hash` 的依据，被改掉等于**篡改一个已 tag 的段的溯源记录**，
而且**不看 `git status` 就发现不了**（它自己的报告里一个字都没提）。

**教训**：派发词里的禁止条款**压不住这条通道**（同样的条款在 fable-wf/ds-flash/kimi-k2.6
上都有效，SEG-6 三条通道全干净）。适配前要么让它跑在沙箱/worktree 里，
要么把仓库设成只读——**不能靠提示词。**

#### （b）`jp_tail` 70% 不合规

| | |
|---|---|
| 交卷 334 → 入仓 | **99**（判死 **235**，70%） |
| 判死原因 | **全部是 `jp_tail` 与 frozen 不符**，无一例外 |
| 实收长度分布 | 9:28 / 10:52 / 11:37 / 12:27 / 13:30 / 14:22 / 15:15 / 16:9 / 17:5 / 18:3 / 19:3 / 20:1 / 7:3 |
| 规格 | 恒取末 **8** 字（不足 8 取全串） |

它取的是**语义上「完整」的一截**（比如把 `【彩野】` 前缀整个带上、把词切齐），
而不是机械的末 8 字。**这是规格遵从问题，不是译文问题**——`jp_tail` 只是回显完整性校验。

#### （c）一处**静默的角色名损坏**，且**现有闸一个都抓不到**

```
id 3831
jp   【直哉】「『この物語』はユウイチとアヤノさんの物語じゃないのかな」
opus 【直哉】「『这个故事』，难道不是ユウイチ和アヤノ同学的故事吗」
gem  【直哉】「『这个故事』，难道不是ユウイチ和アヤ野同学的故事吗」   ← アヤノ → アヤ野
note （空）
```

**`note` 是空的**——它没有声称自己在改这一行，是纯粹的字形损坏。全 334 行仅此一处。

**没有任何现有闸能抓到它**：`R2b` 只查 `【】` 说话人前缀（损坏在句体里）；
`W2` 查 `active.json`，而 **`アヤノ` / `ユカリ` / `サクラ` / `ナオヤ` / `チアキ` 都不在
`active.json` 里**——只有 `ユウイチ: ユウイチ` 在。这是个漏登记。

**建议（未执行，需 glossary v17）**：把五个片假名角色名按 `ユウイチ` 的既有先例登记进
`active.json`。实测代价极低：

| 名 | jp 命中行 | zh 缺该字面（＝新增 W2 警） |
|---|---:|---:|
| アヤノ | 2208 | **2**（0.1%） |
| ユカリ | 368 | 0 |
| サクラ | 1031 | 0 |
| ナオヤ | 34 | 0 |
| チアキ | 2 | 0 |
| （ユウイチ，已登记） | 2146 | 3 |

那 2 条（`1430`/`7709`）都是 §5(b) 正当的**呼名换代词**，与 `ユウイチ` 现有的 3 条
（`7865`/`7934`/`10074`）同性质——即**已登记项本来就带着同类的已知误报，不是新问题**。

### 9.4 ★ 质量：**外部通道迄今最好**

三方对照（`tools/polish_bench.py`，SEG-4 session 1 全部 334 行）：

| 通道 | 改动 | 命中 | 精确 | 召回 | 逐字同定稿 | 闸命中 |
|---|---:|---:|---:|---:|---:|---:|
| **gemini-3.7-flash** | 29 | 28 | **97%** | **85%** | **23** | 235（全 `jp_tail`） |
| fable-wf ※ | 26 | 26 | 100% | 79% | 20 | 0 |
| ds-flash ※ | 10 | 10 | 100% | 30% | 7 | 0 |

`※` = 参与过本段裁决，**有循环优势**（定稿就是从它们的候选里裁出来的）。
**gemini-3.7 没有任何循环优势，却在召回上高过 fable-wf。** 这是本项目做过的所有外部
通道评测里第一次出现这种情况。

b120 单批（与 §七的 8 通道历史表同口径，60 行）：

| 通道 | 改动 | 命中 | 精确 | 召回 |
|---|---:|---:|---:|---:|
| **gemini-3.7-flash** | 9 | 8 | **89%** | **100%** |
| grok-4.5 | 30 | 8 | 27% | 100% |
| fable-wf ※ | 7 | 7 | 100% | 88% |
| grok-4.6 | 8 | 5 | 62% | 62% |
| kimi-k2.6 | 13 | 5 | 38% | 62% |

grok-4.5 也拿到过 100% 召回，但是**用 50% 的改动率换的**（精确 27%，会把队列翻四倍）。
gemini-3.7 是**用 9 次改动拿到 100% 召回**。

#### 它漏掉的 5 条（33 需改 → 命中 28）

| id | 另两条通道提了吗 |
|---|---|
| `10749` `10753` `10754` | **fable 提了**（ds 没提）——真漏 |
| `10835` `10845` | **两条都没提**——这两条是 `雰囲気→气场`，出自**用户对 SEG-4 的人工复核**，无通道可及 |

即在**通道可及的 31 条**上，它命中 28（90%），fable 26（84%），ds 10（32%）。

#### 它多改的 1 条

就是 §9.3(c) 的 `3831` `アヤ野`——**不是风格分歧，是损坏**。
所以「精确 97%」里那 3% 是一条真错，不是一条被裁决者否掉的合理改动。

### 9.5 与 §八（gemini-3.6）的对照：变的是模型，不是装置

| | 3.6（§八） | 3.7（本轮） |
|---|---|---|
| 交卷行数 | 334 ✅ | 334 ✅ |
| 落盘 | ✅ 5 个文件 | ❌ 打进 stdout |
| 实质改动 | **0（0.0%）** | **29（8.7%）** |
| 召回 | 0% | **85%** |
| `jp_tail` | 全对 | 70% 错 |

有意思的是**两者的失败面正好互补**：3.6 机械层完美、实质为空；3.7 实质很强、机械层散。
§8.2 记的那条「机械闸检测不出一个什么都不做的通道」在这里得到反面印证——
**机械闸也不奖励一个真在干活的通道**，两个维度必须分开看、分开记。

⚠ §8.4 曾建议「若要再评估一次，值得先变的是变量而不是重试——例如把 prompt 缩到单批
规模，判断是模型能力问题还是 748KB prompt 吃不下」。**本轮没有动 prompt 规模**
（仍是 760KB 全量），结果直接翻转——**说明 §7.5 那条「可能吃不下现有规模 prompt」的
怀疑是错的，问题一直在模型侧。** 该怀疑就此排除。

### 9.6 现在的状态

| 项 | 状态 |
|---|---|
| 账号资格 | ✅ |
| 直连 `agy` 派发 | ✅ |
| **选模型** | ✅ **本轮解除**（§7.1 作废） |
| 经 paseo 派发 | ❓ 未复测（§7.2/7.3 的两道墙是 3.6 时代测的，agy 行为已变，值得复测） |
| **写文件** | ❌ 打进 stdout；内容可从 stdout 回收 |
| **`jp_tail` 合规** | ❌ 70% 不符 |
| **仓库隔离** | ❌ 提示词条款压不住，跑进仓库改了 `plan.json` |
| **产出质量** | ✅✅ **外部通道最好**：召回 85%（超过带循环优势的 fable-wf） |

**建议**：从 §8.4 的「暂不投入适配」改为「**值得适配**」，但三件前置——
①仓库隔离必须靠机制（worktree/沙箱/只读）不靠提示词；
②`jp_tail` 规格要么在派发词里给一个可执行的取法（例如「用脚本按码点取末 8 个」）、
要么在 ingest 侧对该字段放宽；③落盘方式要重新摸（先复测 paseo 路径，它是唯一能进
现有双通道流水线的形态）。

**本轮零仓库残留**：`plan.json` 已复原，`git status` 只剩他人会话的两个文件；
回收的 334 行只落在 scratchpad 镜像里，未进任何保税仓。
