# Task 9 报告：api_client 可配置化+重试 / ayano_test 模型透传 / 题库两处评审修复 / deepseek 连通冒烟

**状态：完成，已 commit（3 个逻辑提交）。**

commit：
- `33d4a54` feat: api_client 超时/重试可配置化 + ayano_test 模型透传
- `25d57f9` data: 彩野测试 seg1-s2 题库修评审 I2/M1（q13 题面 + info_point 译况标注）
- `3eb153c` chore: deepseek 连通冒烟 + 彩野测试端到端小样计费台账

全量测试 `uv run pytest -q` → **274 passed**（基线 267 + 本任务新增 7 条：
`tests/test_api_client.py` 6 条、`tests/test_ayano_test.py` 1 条）。

未碰 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`；
`.superpowers/sdd/2026-08-02-p3-seg1-s2/progress.md` 在工作树里显示为
modified，那是另一并行会话（SEG-1 生产）留下的，本任务从未 `git add` 它。

---

## A. `tools/api_client.py` 可配置化 + 重试

### 改动点

| 项 | 改前 | 改后 |
|---|---|---|
| timeout | `urlopen(req, timeout=300)` 硬编码 | `DEFAULT_TIMEOUT = 600` 常量，`chat(timeout=None)` 走常量，`_http_transport(url, headers, payload, *, timeout=DEFAULT_TIMEOUT)` |
| model | `default_model: "deepseek-chat"` 固定 | 不变（表仍在，`--model`/`model=` 覆盖即可，本身就是可配置的，这条评审项本质在 B 里落地：ayano_test 之前没有 `--model` 参数，模型进不去） |
| max_tokens | 固定 2048 | 默认提到 **4096**（防推理型模型截断） |
| 重试 | 无 | `DEFAULT_RETRIES = 3`，指数退避 2s/4s/8s |

### 重试设计说明

- **判定规则** `_is_retryable(exc)`：`urllib.error.HTTPError` 且 `code >= 500` 或
  `code == 429` → 重试；`urllib.error.URLError` / `socket.timeout` /
  `TimeoutError` / `ConnectionError`（网络类）→ 重试；其余（含 4xx 的
  `HTTPError`）→ **立即失败，不重试**——鉴权错/模型名错/请求格式错重试没有意义，
  只会白等最长 `2+4+8=14s`。
- **循环**：`attempt` 从 1 计数，失败且可重试且 `attempt <= retries` 时
  `sleep_fn(delay)` 后 `delay *= 2` 再试；否则把最终异常原样 `raise`（不吞掉，
  调用方仍能拿到原始错误类型/信息）。`retries=3` → 最多 1 次首发 + 3 次重试
  = 4 次尝试，退避 2/4/8s。`retries=0` 时首次失败即抛，不 sleep——测试可以
  完全不用管 sleeper 注入。
- **可观测性**：每次失败在 `stderr` 打一行「第 N 次尝试失败，Xs 后重试：错误」
  或「……不重试/已达重试上限：错误」；重试后成功再打一行「第 N 次尝试后成功」。
  全部走 stderr，不污染 stdout（CLI 的 `print(r["content"])` 仍是唯一 stdout
  产出）。
- **`sleep` 可绕过**：新增 `sleeper=None` 参数，测试注入 `list.append` 或
  `lambda s: pytest.fail(...)` 验证退避序列且零真实等待；不注入时用
  `time.sleep`。
- **timeout 与 transport 注入契约不冲突**：`transport` 参数**仍是三参**
  `(url, headers, payload)`，未改签名。当调用方不注入 transport 时，
  `chat()` 用 `functools.partial(_http_transport, timeout=timeout)` 把
  timeout 通过闭包塞进默认 transport，`_http_transport` 本身的第 4 个参数是
  **关键字参数带默认值**（`*, timeout=DEFAULT_TIMEOUT`），历史上不存在别的
  调用方按位置传参会撞车的可能。既有三条测试的 fake transport（三参、无
  timeout 概念）**未改一行**、全部继续通过。

### CLI

`tools/api_client.py` 新增 `--timeout`、`--max-tokens`（默认 4096）、
`--retries`。

---

## B. `tools/ayano_test.py` 透传模型与超时

`main()` 新增 `--model`（默认 None，即走 `api_client` 的 provider 默认模型）、
`--timeout`、`--max-tokens`，透传给 **reader 与 judge 两次 `chat()` 调用**
（此前完全没有 `--model`，用户指定的 `deepseek-v4-flash` 进不去，是硬伤，现已
补上并有专门测试 `test_model_and_timeout_passthrough` 验证两次调用都拿到）。

---

## C. 修 I1：答题预算与标准答案长度错配

- `READER_SYS` 由「用中文简答，两三句以内」改为「把问题涉及的每个点都完整答到，
  但只写要点本身，不要逐句复述或大段抄录原文」——放开字数硬顶，同时明确禁止
  抄书，避免受试者靠贴原文投机拿分。
- `JUDGE_SYS` 补上判定标准：「受试回答答出了标准答案里的主要事实点，即使措辞
  不同也判『对』；只答出部分主要事实点、或遗漏了次要细节，判『部分对』；
  关键事实错误、答非所问、或答『不知道』而标准答案本可从文本推出，判『错』」。
- 15 条 `reference` 内容**未改一字**。

F 步的端到端小样（见下）里两题都判「对」，且判分依据引用了具体事实点
（「アヤノ因先与サクラ同学约好而无法当场答应」「两题正确答案及核心原因」），
说明新判据在真实调用里按预期工作——不是靠字数判，是靠事实点判。

---

## D. 修 I2：q13 题面与原文不符

`config/ayano_qa/seg1-s2.yaml` q13：

- 题面改前：「千秋向直哉问了**哪两个问题**」（锁死数量，但 `s2f_40` 原文实际
  连问四处：CHI00480「为什么不在故事里」、CHI00520「和彩野关系好吧」、
  CHI00530「你怎么看彩野」、CHI00540「没告白吗」）。
- 题面改后：「千秋**最后追问到了什么**？直哉分别怎么回答？」——不锁数量。
- `reference` 只在首句加了「千秋追问到两处：」做衔接，两处关键问答内容**未增
  未删**。

---

## E. 顺手修 M1：info_point 译况标注过时

**先核实译况现状**（只读 `pilot/lanes/opus/data/batches.jsonl` +
`forward.jsonl`，未碰车道数据）：

```
b36–55 全部已译（batches 36 到 55 每批 ids ⊆ forward 已译集合）
b56–62 全部未译
```

即 q6/q11/q12 引用的 b47 **确实已译完**（评审 M1 判断准确），q13/q14/q15
引用的 b58/b59（s2f）**确实仍未译**，批号本身无误，只是「已译/未译」这层
标注过期了。

修法：把 15 处 `info_point` 末尾的 `已译` / `未译（bNN+）` 全部换成**只标批次
号**（如 `b47`、`b58/b59`），不再标译况；文件头注释同步说明理由——译况该运行
时看 `ayano_test` 报告里的「缺译 N 行」提示，不该写死在题库里、随进度必然
过期。

---

## F. deepseek 连通冒烟（真实请求）

### F.1 模型可用性探针

```
$ uv run python tools/api_client.py --prompt "回复两个字：连通" \
    --model deepseek-v4-flash --purpose connectivity-smoke
连通
[deepseek/deepseek-v4-flash tokens 87+15]
```

**结论：`deepseek-v4-flash` 可用**，管道与鉴权均正常，未触发任何 4xx/5xx，
无需回退 `deepseek-chat` 复测。跑了两次（探针本身 + 复核），token 数
87+24 / 87+15（浮动属正常）。已写入 `data/api_ledger.jsonl`（隐去 key，仅记
token 与用途）。

### F.2 彩野测试端到端小样

临时题库（仅 q1、q4，取自 `config/ayano_qa/seg1-s2.yaml`，未改内容）落在
scratchpad：`/private/tmp/claude-501/.../scratchpad/smoke-qa.yaml`；输出落
`/private/tmp/claude-501/.../scratchpad/ayano-smoke-report.md`（均不在仓库
内，未 `git add`）。

```
$ uv run python tools/ayano_test.py --segment seg1-s2 --qa <scratch>/smoke-qa.yaml \
    --lane-dir pilot/lanes/opus --out <scratch>/ayano-smoke-report.md \
    --model deepseek-v4-flash
报告已写 <scratch>/ayano-smoke-report.md
```

无重试提示行（零失败），退出码 0。**完整报告原文**：

> ⚠ 本段缺译 707 行（段未译完，结论仅供参考）——这是因为按 seg1-s2 的
> batches 区间 [36,62] 全量组装正文，而车道现已推进到 b339，b56 之后这段
> 区间本身尚有大量未译；q1/q4 涉及的信息点（b36 附近）均在已译范围内，不
> 受影响。

#### q1

- **题面**：ユウイチ约アヤノ这个周六出去玩，アヤノ为什么没能当场答应？两人
  最后把出去玩的日子改到了什么时候？
- **标准答案**：因为アヤノ在这之前已经先和另一个女孩子（隔壁班的サクラ同学）
  说好，这次休息日要是有空就两个人一起去买东西；虽然还没等到对方的回复，但
  毕竟是她这边先约的人家。ユウイチ听后说「有约在先那也没办法」，于是两人把
  出去玩改到下周。
- **受试回答（deepseek-v4-flash 原文）**：アヤノ没能当场答应，是因为她之前
  跟隔壁班的サクラ同学说好，周末要是有空的话，两个人一起去买东西。两人最后
  把出行的日子改到了下周。
- **判分（deepseek-v4-flash 原文）**：对|受试回答准确答出了アヤノ因先与
  サクラ同学约好而无法当场答应，以及两人把出行改到下周。

#### q4

- **题面**：サクラ在教咒语之前先出了两道推理题。这两道题的正确答案分别是
  什么？
- **标准答案**：第一题「小小的女孩」：女孩打开阁楼门后看到的那幅有冲击力的
  光景，只不过是房间的外面——因为那个女孩一直都生活在阁楼房间里。第二题
  「赝品的男人」：赝品本身的做工完全没有问题，问题出在被仿的原作上（アヤノ
  答「原因在于原作」，サクラ判定答对）。
- **受试回答（deepseek-v4-flash 原文）**：第一题「小小的女孩」的正确答案：
  女孩看到的光景只是普通的家、房间的外面；原因是女孩一直生活在阁楼房间里，
  从未见过正常的生活空间。
  第二题「赝品的男人」的正确答案：赝品的做工完全没有问题，被识破的原因在于
  原作本身。
- **判分（deepseek-v4-flash 原文）**：对|受试回答完整答出两题正确答案及核心
  原因，与标准答案一致。

两题判分均落在「对」，判据具体点名了事实点而非泛泛而谈——是 C 步修改判分
标准后第一次看到的真实产出，符合预期。

台账新增 6 行（连通探针 2 + q1/q4 各 reader/judge 2×2 = 4），已入库：
`data/api_ledger.jsonl`。

---

## 顾虑 / 待用户关注

- F.2 的「缺译 707 行」提示是 `assemble_context` 按 seg1-s2 声明的
  `batches:[36,62]` 全量组装的固有行为（不是本任务引入的新问题）——只想跑
  「已译部分」的端到端小样时这条警告必然出现，可忽略；如果希望冒烟报告更
  干净，未来可以考虑给 `ayano_test` 加一个只组装到某批次的选项，但本任务
  范围未要求，未做。
- `deepseek-v4-flash` 两次探针的 completion_tokens 有小幅波动（24 vs 15），
  正常的模型输出非确定性，非管道问题。
