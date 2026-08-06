# Task 9 report：tools/polish_amplify.py（裁决意图归纳 + 放大扫描装配）

状态：DONE。

## 文件

- `tools/polish_amplify.py`（新增）——`digest(label, repo=None) -> str`，
  `scan_prompt(label, repo=None) -> str`；CLI `--seg <label> --digest` /
  `--seg <label> --scan-prompt [--out <path>]`。
- `tests/test_polish_amplify.py`（新增，11 个用例）。

未改动任何既有文件（`polish_ingest.py`/`polish_triage.py`/`polish_commit.py`/
`polish_context.py`/`polish_setup.py` 全部原样复用；`OUTPUT_CONTRACT_HEADER`
从 `polish_context` 直接 import，不复制文本）。

## 接口

- `digest(label, repo=None) -> str`：把 `decisions.jsonl` 里的人工裁决按
  `reason_code` 归纳成意图纪要（原因码分布表 + 每码 ≤3 个代表例：
  jp/opus/候选/最终 zh/裁决语），**追加**写入 `frozen/rulings.md`（不覆盖），
  返回纪要文本。可重复调用，不受轮数闸约束。
- `scan_prompt(label, repo=None) -> str`：纪要 + 整 SEG 四桶结果全景（含
  桶 3 落选句全文）+ 锁定 id 清单 + 术语/风格/口调/锚点 + 与生产批一致的
  输出契约（channel 固定 `amplify`，raw 落 `raw/amplify/b<N>.out`，每批
  一个）。装配成功后在 `frozen/rulings.md` 追加一条轮数标记；若本 SEG
  已达到 `CFG["amplify_rounds"]`（默认 1）上限，抛
  `AmplifyRoundLimitError`，不做任何写入。
- `AmplifyRoundLimitError(RuntimeError)`：轮数闸拒绝时的显式异常类型。

## 一、`verdict="auto"` 的取舍：排除，不计入人裁意图分布

`decisions.jsonl` 里 `verdict="auto"` 的记录是 `polish_commit.commit()`
对 autoclear-and-not-sampled 候选**自动铸造**的（`reason_code` 恒为字面量
`"autoclear"`，`edited_zh` 恒为 `None`，见 `tools/polish_commit.py:305-310`
与 task-8-report.md）——这条记录里没有任何人的判断，只是"机械闸+配额算法
批准通过"这件事本身的存档。裁定：`digest()` 只统计
`verdict in {"adopt", "edit", "keep_opus"}`（brief 给的 `decisions.jsonl`
verdict 枚举 `adopt|keep_opus|edit|auto` 里，唯三种真正代表人工判断的
取值）。理由：
1. 把 `"autoclear"` 计入分布表，会用一个不代表任何审美/术语/语序取舍的
   类别冲淡真正有信息量的类别（量词/语序/补主语/术语/…）的占比；
2. auto 记录没有任何裁决语来源（`edited_zh=None`），若被抽为"代表例"，
   会产出一条无法解释"为什么这么改"的案例，破坏"代表例=可读的裁决案例"
   这个契约。

变异自检②验证了这一点（见下）：把 `human = [dec for dec in decisions if
dec.get("verdict") in HUMAN_VERDICTS]` 改成不做过滤，混入一条
`verdict="auto"` 记录后分布表立刻出现 `| autoclear | 1 | 25.0% |`，人工
裁决总数从 3 变成 4——测试真红。

## 二、轮数闸标记的形态与检测方式

标记：`<!-- amplify-round:N -->`（单行 HTML 注释语法，`rulings.md` 是纯
markdown，人工/模型正常写作不会产出字面意义上的 HTML 注释，不会被普通
中文正文误撞）。检测：`AMPLIFY_MARKER_RE = re.compile(r"^<!-- amplify-
round:(\d+) -->$", re.MULTILINE)` 锚定整行匹配（`^...$` + `MULTILINE`），
对 `frozen/rulings.md` 全文 `findall` 计数，与 `CFG["amplify_rounds"]`
比较——**`>=` 判死**（`amplify_rounds=1` 时，已出现 1 条标记就该拒绝
第 2 次装配，不是等出现第 2 条才拦）。

标记的写入时机：`scan_prompt()` **组装完成、确定要返回之前**才追加
（gate 检查通过 → 读 frozen 各文件 → 组装完整文本 → append 标记 →
`return text`）。选在这一步而不是"检查通过就先写"的理由：如果提前写，
一次因为其他原因（比如 `triage.json` 缺失）中途抛异常的调用也会消耗掉
本该属于"真正装配成功一次"的轮次配额，是不诚实的记账。

`digest()` 本身不受这道闸约束、也不写这个标记——它只是纪要写入，可以
被调用任意次；真正稀缺、要限流的是"发给模型的整 SEG 装配 prompt"这个
动作本身（`scan_prompt()`），不是"看一眼纪要"。

变异自检①验证了这一点：把闸判断改成 `if False:`（恒放行），
`test_scan_prompt_round_gate_blocks_second_call` 与
`test_cli_scan_prompt_second_call_rejected` 两条测试真红。

## 三、raw 落盘粒度：按批（`raw/amplify/b<N>.out`），不是整段一个文件

`polish_ingest.ingest(label, channel, batch)` 的批级幂等
（`ingested.<channel>.json` 记的是"批号"）与覆盖完整性检查（"批内非锁定
id 是否在这份 raw 里全部出现过"）**都是按批做的**，且 raw 路径本身写死
是 `raw/<channel>/b<batch>.out`——这是既有的、本任务被要求"直接复用、
不改动"的契约，不是本模块可以自由选择的接口。若把整段输出成一个文件，
`ingest()` 会在 `d / "raw" / "amplify" / f"b{batch}.out"` 这个路径上找
不到文件，对每一个批都判"raw 不存在"、整批失败——放大扫描产的东西会
一行都进不了保税仓。

故 `scan_prompt()` 的输出契约末尾按 SEG 全部批号（`frozen/source.jsonl`
里出现过的 batch，按首次出现顺序去重）逐一列出 `raw/amplify/b<N>.out`，
要求模型对**每个批**、批内**每个非锁定 id**都产出恰好一行——即"重扫
整个 SEG"字面意义上的重扫（桶 0/1/2 里已经确认没问题的行也要求原样抄
一遍现行 zh，与常规批次同一份契约），不是只扫桶 3。`OUTPUT_CONTRACT_
HEADER` 直接从 `tools.polish_context` import 复用（不复制文本），保证
字段契约（`id`/`jp_tail`/`zh`/`score`/`note`/`adjudicate`）与生产批
逐字一致，不会因为两处各自维护而漂移。

### 已知、不新增的粗糙点：`plan.json`/`prompt_hash` 的 channel 无关性

`polish_ingest.ingest()` 用 `plan.json` 反查某批所属会话的 `prompt_hash`
（`_find_prompt_hash`，按批号在记录列表里找**第一个**匹配，函数签名
本身不接受 channel 参数）。真实流水线里，`polish_context.render()`
早于本模块运行、已经为该 SEG 全部批次写过至少一条 session 记录（不同
channel 执行的是同一份 prompt 文字，`render()` 本身不按 channel 参数化，
session 记录天然是"channel 无关"的）。**本模块因此不再往 `plan.json`
写任何新记录**：既有记录已经能让 `_find_prompt_hash` 对 SEG 的每个批号
都返回一个非空哈希，`ingest(label, "amplify", batch)` 可以正常跑通。

代价：`candidates.amplify.jsonl` 里记的 `prompt_hash` 指向的是"某次
普通会话"渲染出的哈希，不是"这次放大扫描 prompt 本身"的哈希——真实存在
但只影响审计精确度、不影响 ingest 是否成功的粗糙点。修 `_find_prompt_
hash` 使其按 channel 区分记录超出本任务范围，也违反"直接复用、不改动
`polish_ingest.py`"的既定分工，已作为 concern 记入下方"待复核"。若该
SEG 从未跑过任何 `polish_context.render()`+`--out` 流程（`plan.json`
完全为空），`ingest("amplify", batch)` 会按既有逻辑正确地判"整批失败：
查不到 prompt_hash"——这与其余 channel 遇到同一情形的行为完全一致，不是
本模块引入的新缺口。

## 纪要与 scan_prompt 的结构大纲

`digest()`／`_build_digest_text()`：
```
## 放大扫描意图纪要（<label>，<ts>，人工裁决 N 条，M 类原因码）

### 原因码分布
| 原因码 | 计数 | 占比 |
|---|---:|---:|
| ... | n | pct% |

### 代表例（每类原因码 ≤3 条）
#### <原因码>
- id <cid>（verdict=<verdict>）
  - JP：...
  - opus：...
  - 候选（<channel>）：...
  - 最终 zh：...（adopt→候选原文 / edit→edited_zh / keep_opus→opus 原译）
  - 裁决语：...（decisions.jsonl 无自由文本字段时，按 verdict/reason_code/
    chosen_channel 合成一句可读摘要；若记录带 `note` 则优先原样使用）
```

`scan_prompt()`：
```
# <label> 放大扫描（第 N 轮，共 <批数> 批）
## 零、本轮说明——这是一次「放大扫描」          (AMPLIFY_PREAMBLE)
## 一、裁决意图纪要                              (= _build_digest_text())
## 二、全 SEG 四桶结果全景
### 桶 0（锁定 id，禁止改动）——id 列表
### 桶 1（零改动）——每条 id(channel): opus 原文
### 桶 2（已进入本轮人工裁决队列）——jp/opus/候选 + 裁决结果（若已裁决）
### 桶 3（有改动但本轮落选——重点复核对象）——jp/opus/落选候选全文/落选原因
## 三、锁定 id 清单（禁止在输出中出现这些 id）
## 四、术语 / 风格 / 口调 / 锚点（frozen 冻结面）
## 五、输出契约                                   (= OUTPUT_CONTRACT_HEADER
                                                     + raw/amplify/b<N>.out 列表)
```
（成功返回后，另在 `frozen/rulings.md` 追加一条独立的轮数标记，不掺进
返回值里。）

### 真实渲染样例（来自 `test_cli_scan_prompt_writes_out_file` 生成的文件，节选）

```
# segAmp 放大扫描（第 1 轮，共 2 批）
## 零、本轮说明——这是一次「放大扫描」
...
## 一、裁决意图纪要

## 放大扫描意图纪要（segAmp，2026-08-07T..., 人工裁决 3 条，2 类原因码）

### 原因码分布

| 原因码 | 计数 | 占比 |
|---|---:|---:|
| 语序 | 2 | 66.7% |
| 过度归化 | 1 | 33.3% |
...
## 二、全 SEG 四桶结果全景（`polish_triage.triage()` 的分流快照）

### 桶 0（锁定 id，禁止改动，共 1 个）

10

### 桶 1（零改动——已确认这些行的候选与 opus 逐字相同，共 1 条）

- id 11（chA）：彩野静静地点了点头。

### 桶 2（已进入本轮人工裁决队列，共 3 条候选行）

- id 12（chA）
  - JP：教室の時計が動いていることに気づいた。
  - opus：我注意到教室里的时钟还在走动。
  - 候选：教室里弥漫着令人窒息的寂静，仿佛连时间都为之停滞了一般。
  - 裁决结果：verdict=edit，原因=语序
...
### 桶 3（有改动但本轮落选，共 2 条——**本次放大扫描的重点复核对象，候选全文完整列出**）

- id 14（chA）
  - JP：ユカリは眼鏡を押し上げた。
  - opus（现行生产车道译文，除非下方另有说明）：由加里推了推眼镜。
  - 落选候选全文：由加里扶了扶眼镜。
  - 落选原因：已判定安全、自动清关（未抽中复核样本）——生产车道当前译文...
- id 15（chA）
  - JP：彩野はいつもの笑顔を見せた。
  - opus（现行生产车道译文，除非下方另有说明）：彩野露出了熟悉的微笑。
  - 落选候选全文：彩野忽然浮现出了熟悉的微笑呢。
  - 落选原因：有真实改动，但本轮未挤进人工裁决队列（K 配额已满）——生产车道当前译文**仍是 opus 原文**...
...
## 五、输出契约
...
- `raw/amplify/b1.out`
- `raw/amplify/b2.out`
```

## 三个变异的红绿实况

方法与 Task 7/8 一致：用 Edit 在源码里精确引入一处改动、跑
`uv run pytest tests/test_polish_amplify.py -q`、记录、再用 Edit 精确
还原（全程未使用 `git checkout`/`stash`/`restore`）；每次还原后单独跑
该测试文件确认恢复到 11 passed；全部完成后跑一次全量确认 678 passed，
并 `grep MUTATION tools/polish_amplify.py` 确认源码干净。

**变异①（brief 给定）：轮数闸恒放行**（`if round_count >= limit:` 改成
`if False:`）→ 2 条真红：
```
FAILED tests/test_polish_amplify.py::test_scan_prompt_round_gate_blocks_second_call
FAILED tests/test_polish_amplify.py::test_cli_scan_prompt_second_call_rejected
2 failed, 9 passed in 0.39s
```

**变异②（指令额外要求）：digest 把 `verdict="auto"` 也算进人裁意图分布**
（`human = [dec for dec in decisions if dec.get("verdict") in HUMAN_
VERDICTS]` 改成 `human = [dec for dec in decisions]`）→
`test_auto_verdict_excluded_from_digest` 真红，且失败信息直接展示了
问题本身（分布表多出 `| autoclear | 1 | 25.0% |` 一行，总数从 3 变 4）：
```
FAILED tests/test_polish_amplify.py::test_auto_verdict_excluded_from_digest
1 failed, 10 passed in 0.34s
```

**变异③（指令额外要求）：scan_prompt 漏掉桶 3 落选句**（`b3 = sorted(...)`
改成 `b3 = []`）→ 2 条真红（既有专项测试，也连带命中了 CLI 的 `--out`
文件内容测试，证明"漏掉桶 3"这件事在两条独立路径上都会被抓到）：
```
FAILED tests/test_polish_amplify.py::test_scan_prompt_includes_bucket3_full_text
FAILED tests/test_polish_amplify.py::test_cli_scan_prompt_writes_out_file
2 failed, 9 passed in 0.10s
```

三个变异全部按预期真红，均已用 Edit 精确还原（`grep MUTATION tools/
polish_amplify.py` 无输出，源码干净）；每次还原后单独跑
`tests/test_polish_amplify.py` 确认恢复到 11 passed，最终跑一次全量
确认 678 passed。

## 测试输出

```
$ uv run pytest tests/test_polish_amplify.py -q
...........                                                              [100%]
11 passed in 0.09s

$ uv run pytest -q
678 passed in 3.42s      # 667（Task 8 完成后基线）+ 11（本任务新增）
```

## 与 brief 的一切偏差

1. **CLI 参数与接口描述的字面对应**：brief 写 `--seg <label> --digest` /
   `--seg <label> --scan-prompt --out <path>`；实现里 `--out` 对
   `--scan-prompt` 是可选的（省略时打印到 stdout，而不是强制要求
   `--out`）——理由是 `polish_context.py` 的 `--session` 同样允许省略
   `--out`（只打印 hash），本模块延续同一 CLI 习惯，且测试
   `test_cli_scan_prompt_second_call_rejected` 依赖"不带 --out 也能跑"
   来验证轮数闸在纯 CLI 层面的行为，不是计划外的接口膨胀。
2. **`digest()`/`scan_prompt()` 都加了 `repo=None` 参数**：与 Task 3-8
   一致的既定惯例（tmp_path 测试隔离要求），brief 接口签名里没写但补充
   信息明确要求"上游模块都有 repo=None 参数，本模块照此约定加上"。
3. **`scan_prompt()` 不写 `plan.json`**：brief 与补充信息都没有明确要求
   本模块维护 `plan.json`；见上方"三、raw 落盘粒度"专节的详细论证——
   复用既有 session 记录即可让 `ingest()` 正常工作，新增写入反而会因为
   `_find_prompt_hash` 不区分 channel 而制造潜在的记录覆盖歧义。已作为
   concern 记录，不是本任务遗漏的实现步骤。
4. **`scan_prompt()` 额外内嵌了完整的术语/风格/口调/锚点/锁定 id 清单**
   （brief 原文只写"纪要 + 四桶全景 + 输出契约"三项）：这是为了保证放大
   扫描的模型调用具备与首轮润色同等的质量约束（否则模型可能在没有术语
   表/锚点对照的情况下重新引入错误），且这类内容本来就已经在 frozen/
   里现成存在，直接复用 `polish_context.py` 的 `_render_anchors`/
   `_render_voices` 两个 helper，没有引入新的耦合面。已在"设计点"部分
   写明这是主动的质量取舍，非计划外的范围膨胀。

## 生产数据安全核查

- 全程未创建/写入真实 `pilot/polish/` 目录（`ls pilot/polish` 报
  "No such file or directory"）——全部测试均用 `repo=` 参数指向
  `tmp_path` 造的替身仓库。
- 未使用 `git add -A`；未触碰 `.claude/settings.json` 与
  `data/api_ledger.jsonl`（`git status --short` 确认这两个文件仍是会话
  开始前的未暂存改动，本任务未 stage、未修改）。
- `git status --short` 显示本任务只新增了两个文件：
  `tools/polish_amplify.py`、`tests/test_polish_amplify.py`。

## Concerns（供后续任务参考，非阻塞）

1. `candidates.amplify.jsonl` 的 `prompt_hash` 字段在真实多通道 SEG 里
   会指向"某次普通会话"渲染出的哈希，而不是"这次放大扫描 prompt 本身"
   的哈希——审计精确度的已知粗糙点，不影响 `ingest()`/`triage()`/
   `commit()` 任何一步的正确性（详见上方专节）。若未来需要精确追溯"某条
   amplify 候选到底出自哪次装配"，需要改 `polish_ingest._find_prompt_
   hash` 的签名（加 channel 参数、按 channel 过滤记录），那是一次跨模块
   改动，超出本任务范围。
2. `scan_prompt()` 对 `triage.json` 存在性做了硬性要求（不存在则
   `FileNotFoundError`）——这是有意的（没有四桶分流结果就没有"全景"可
   展示），但也意味着调用顺序被隐性锁定为"先 triage()、再 scan_prompt()"，
   若未来有人跳过 triage 直接调用 scan_prompt，会得到一条读文件失败的
   报错而不是更友好的"请先跑 triage"提示；当前报错信息已经写明原因，
   判定为足够清楚，未做额外的用户友好化处理。
