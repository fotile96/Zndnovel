# paseo `antigravity-acp` 通道摸底（2026-08-12）

> 用户 2026-08-12 在 paseo 里新增了 antigravity provider，要求实测「怎么发射」并评估
> `gemini-3.5-pro` 的产出质量，供后续在开发轨正式适配。
>
> **结论先说：发射路径已完全摸清并记录在下；产出质量没能评估——该 provider 在本账号
> /本地区被 Google 侧的资格校验挡死，一次也没跑起来。** 另外「`gemini-3.5-pro`」这个
> 型号**在真实模型表里不存在**（详见 §3）。

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
