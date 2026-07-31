# Task 7 报告：build_context（三 profile × 四 baseline）

## 实现了什么

新建两个文件，按 `task-7-brief.md` 的 Step 1（测试）与 Step 3（实现）**逐字节照抄**：

- `tools/build_context.py`：CLI `--batch N --profile {api-A|api-B|cc} --baseline {none|ref|revise|judge} [--jp-fallback]`，产出 `work/ctx/batch_N/{context.md,source.jsonl,manifest.json}`。渲染顺序＝context.md 章节顺序：一/冻结骨架（全部 196 卡）→ 二/前缀正文（api-A 含全部已译前缀 zh；api-B/cc 跳过非当前章的行，靠骨架里已含的章梗概卡 133-145 压缩）→ 三/锚点行（anchors.yaml 全文或"暂缺"）→ 四/术语与风格（active.json + style.md）→ `SECTION5="## 五、本批任务"`（本批逐行 `[id] jp`，baseline≠none 时附 `base:` 行）。
- `tests/test_build_context.py`：brief Step 1 给定的 3 个测试，原样落地。

**唯一的实现偏离**：brief 末尾明确点名的一处待决——`gv = max(...)` 对空 glob 会抛 `ValueError`——按 brief 给出的结论「实现取后者」，在 `build()` 里把这段改成先收集版本号列表、空列表回退 `gv = 0`：

```python
versions = [int(_re.search(r"v(\d+)", p.stem).group(1))
            for p in (repo / "glossary").glob("glossary.v*.yaml")]
gv = max(versions) if versions else 0
```

其余代码（含 `SYN_CARDS` 表、`SECTION5` 常量、章节标题字符串、退出码 2、文件名）与 brief 提供的参考实现逐字节比对一致（见下方"自评审"的 diff 证据）。

## TDD 证据

**RED**（Step 1 落地后、Step 3 实现前）：

```
$ uv run pytest tests/test_build_context.py -v
...
ERROR collecting tests/test_build_context.py
ImportError while importing test module '/home/user/Zndnovel/tests/test_build_context.py'.
tests/test_build_context.py:3: in <module>
    from tools.build_context import build
E   ModuleNotFoundError: No module named 'tools.build_context'
=========================== short test summary info ============================
ERROR tests/test_build_context.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.10s ===============================
```

失败原因符合预期：brief Step 2 就是预告这个 `ModuleNotFoundError`（模块尚未创建），不是巧合失败。

**GREEN**（写完 `tools/build_context.py` 后）：

```
$ uv run pytest tests/test_build_context.py -v
tests/test_build_context.py::test_ctx_files_and_manifest PASSED          [ 33%]
tests/test_build_context.py::test_baseline_only_touches_tail PASSED      [ 66%]
tests/test_build_context.py::test_untranslated_prefix_requires_fallback PASSED [100%]
============================== 3 passed in 0.07s ===============================
```

**全套回归**：

```
$ uv run pytest -q
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 2.00s
```

83（基线）+ 3（新增）= 86，零回归。

## 真实数据冒烟

### 命令 1：`uv run python tools/build_context.py --batch 1 --profile cc --baseline none`

退出码 0，未加 `--jp-fallback`（批次 1 无前缀，符合预判）。

**`context.md`**：1129 行（`wc -l` 报 1128，因文件末尾无换行符，`wc -l` 少计 1；用 Python 按 `\n` 切分验证为 1129），105861 字节。章节标题与行号：

| 行号 | 内容 |
|---|---|
| 1 | `# 批次 1（profile=cc）` |
| 2 | `# 一、冻结骨架（中文卡组）`（196 张卡，逐张一行，到 198 行） |
| 200 | `## 二、前缀正文`（内容为空——批次 1 是全书首批，无更早的 main 批次） |
| 202 | `## 三、锚点行（日中对照）`（`skeleton/anchors.yaml` 全文，到约 735 行） |
| 736 | `## 四、术语与风格`（`glossary/active.json` 单行 dump + `glossary/style.md` 全文，到约 789 行） |
| 790 | `## 五、本批任务（baseline=none）`（后接 339 行 `[id] jp`，无 `base:` 行——baseline=none） |

人工抽查内容（卡 1/2/3、卡 194/195/200、术语 dump、任务区首尾行）均可读、字段完整，无乱码/截断。

**`source.jsonl`**：339 行。首行 `{"id":6060,"jp":"……なんてね。"}`，末行 id=6401（与批次 1 的 ids 范围吻合）。全部无 `base` 字段（baseline=none 的预期行为）。

**`manifest.json`**：

```json
{
 "batch": 1,
 "profile": "cc",
 "baseline": "none",
 "glossary_v": 6,
 "skeleton": "f5edfcd18ff52c9f07c5f036f1032304a5ccaa966258d084f495732f321b2399",
 "anchors": "2ea7a6235040d25eed6350486098a2f9f98f4ee8f757c37872069f9aaa2599b7",
 "ctx_sha": "190411aaed9bdbfb32e34a30e67bbebda0f1c536c37cdd397de3a92edc0789d6"
}
```

`glossary_v=6` 与 CLAUDE.md 所述现行最高版本一致（真实 `glossary/` 下 v1..v6 齐全，非空 glob 分支）。三个 sha256 已用独立的 `hashlib.sha256(...).hexdigest()` 重算核对，三值完全一致。

### 命令 2：`uv run python tools/build_context.py --batch 1 --profile api-A --baseline none`

退出码 0。与命令 1 输出 diff：

- `context.md`：仅第 1 行 `profile=cc`→`profile=api-A` 不同，其余 1128 行字节相同。
- `manifest.json`：仅 `profile` 与 `ctx_sha`（因 context.md 变了）不同。
- `source.jsonl`：完全相同（source 只依赖 baseline，不依赖 profile）。

**这是批次 1 场景下的正确结果，但需要说明成因**：`_render_prefix` 里 api-B/cc 专属的跨章跳过逻辑（`if profile in ("api-B","cc") and ch != cur_ch: continue`）只在存在"更早批次"时才有输入可跳；批次 1 是全书首批，`prior_ids` 恒为空，三个 profile 在批次 1 的"前缀正文"小节天然都是空——profile 差异因此只体现在标题行/manifest，不体现在前缀压缩逻辑本身。为确认这条分支的真实行为（而不是只看批次 1 这个平凡样例），另写了一个不入库的诊断脚本（`/tmp/.../scratchpad/probe_profile_diff.py`，2 章 2 批的合成夹具）：

```
profile=api-A  rc=0  含章a前缀译文=True
profile=api-B  rc=0  含章a前缀译文=False
profile=cc     rc=0  含章a前缀译文=False
```

即 api-A 保留跨章已译前缀原文，api-B/cc 正确省略——机制本身是生效的，只是批次 1 的样例天然不触发它。

### 补充验证（自评审延伸，超出 brief 字面 Step 列表但覆盖"完成定义"要求的范围）

1. **exit code 2 契约在真实数据上复现**（不只是 tmp_path 夹具）：真实仓库尚无 `data/forward.jsonl`（未开翻），批次 2 与批次 1 同章（`s0f`），故批次 2 的前缀必然命中未译行：
   ```
   $ uv run python tools/build_context.py --batch 2 --profile cc --baseline none
   前缀行 6060 未译（--jp-fallback 可放行）
   EXIT CODE: 2
   $ uv run python tools/build_context.py --batch 2 --profile cc --baseline none --jp-fallback
   EXIT CODE: 0
   ```
2. **baseline-only-touches-tail 不变量在真实全量数据上复核**（brief 的单测只覆盖 2 行的玩具夹具，这里在 1129 行的真实批次 1 上重验）：`baseline=none` 与 `baseline=revise --jp-fallback` 两次运行的 context.md，`"## 五、本批任务"` 之前的前缀**字节完全相同**（33851 字节），之后的尾部不同。
3. **3 profile × 4 baseline 全矩阵冒烟**（12 组合，合成小夹具）：全部返回码 0，且 `base` 字段的有无与 `baseline!="none"` 严格对应，无一例外。

结论：批次 1/2 均无报错性质的实现缺陷；命令 2 的"看起来没差异"是数据前提（批次 1 是首批）导致，非实现缺陷，已用独立场景证实差异机制生效。

## 改了哪些文件

- 新建 `tools/build_context.py`
- 新建 `tests/test_build_context.py`
- 新建本报告 `.superpowers/sdd/2026-07-30-p1b-linearize-context/task-7-report.md`
- 未改动任何其它既有文件（`git status` 全程只有上述新文件；`skeleton/`、`glossary/`、`config/`、`data/`、`tools/` 下其它脚本、`tests/` 下其它测试均未触碰）。
- `work/` 下产生的 `ctx/batch_1/`、`ctx/batch_2/` 是运行产物，已在 `.gitignore`，未入库。

commit：`3ab66fc feat: build_context 三 profile×四 baseline 组装`（`tools/build_context.py` + `tests/test_build_context.py`，177 行新增，brief Step 5 指定的原始提交信息）。

## 自评审发现

1. **逐字节核对"照抄"契约**：用脚本把本文件与 brief 里两段 fenced python 代码块做 `diff`——测试文件完全一致（仅文末换行符差异，与 Write 工具行为有关，非内容差异）；实现文件仅在 `gv` 计算那一处（brief 明确指示要改的地方）有出入，其余逐字节相同。SYN_CARDS 常量、SECTION5 常量、退出码 2、四个章节标题字符串均按要求保留。
2. **契约本身带的未用元素，遵指示原样保留、未做"顺手清理"**：
   - `SYN_CARDS` 表定义后在 `_render_skeleton`/`_render_prefix`/`build` 里均未被引用（api-B/cc 的章节压缩是靠"骨架小节本就含全部 196 卡"这条路径隐式达成，不查这张表）；
   - `_load()` 读入的 `env["timeline"]` 全程未被读取；
   - `_render_prefix` 里的 `missing` 计数器只自增、从未被返回或使用。
   三者均为 brief Step 3 参考实现自带，按任务说明"照抄...都是契约"原样保留，未改动、未删除。记录在此供后续任务/评审判断是否需要在未来变更中处理。
3. **测试覆盖的一处真实缺口（brief Step 1 自带，非本次引入）**：3 个既定测试里没有一条真正跑到 `profile in ("api-B","cc") and ch != cur_ch` 这条分支——test1/2 的批次 1 无前缀（分支体从不执行），test3 用的是 profile="api-A"（条件恒假）。已用不入库的诊断脚本（报告正文"命令 2"小节）独立证实该分支行为正确。是否要为这条分支补一条落库回归测试，超出了 brief Step 1 明文给的三个测试，比照本计划 Task 3 的先例（brief 测试内容本身的覆盖缺口按人裁处理，不由实现者单方面扩大范围），留给评审/控制器判断，本次未擅自新增。
4. **CLI 无 `--repo` 覆盖参数**：`main()` 从不传 `repo=` 给 `build()`，命令行调用永远针对真实仓库根目录；只有直接 Python 调用（测试用）才能覆盖 `repo`。这是 brief 接口表本身的设计（未列 `--repo` flag），非遗漏，此处仅作记录。
5. 未发现需要立即修复的正确性问题；`git status` 确认改动范围严格限定在两个新文件 + 本报告。

## 遗留顾虑

- 上述发现 3（api-B/cc 跨章跳过分支缺少落库回归测试）是唯一值得后续关注的点——当前行为已用诊断脚本证实正确，但没有常驻测试防止未来改动悄悄破坏这条分支。按任务指示未擅自扩测试范围，留待评审裁决。
- 发现 2 的三处未用元素（`SYN_CARDS`/`env["timeline"]`/`missing`）如果后续任务（Task 8/9/10）预期会用到 `SYN_CARDS` 做更精细的章节-卡号映射，目前的实现完全没有接这张表，若后续任务假定它已被消费，需要注意。

---

## 修复轮：评审 2 条 Important（plan-mandated）

评审确认执行忠实度（与 brief Step 3 只差控制器指定的 `gv=0` 处）、baseline 尾部不变量结构性成立、只读约束/退出码 2/`--jp-fallback`/`ctx_sha` 求值顺序均无问题，这些未再改动。以下是控制器裁决要求修复的 2 条 Important 及其落实。

### Finding 1：extra 车道被静默丢空，且 exit 0

**问题**：`_load` 从不读 `data/ledger_extra.jsonl`；取行循环 `if isinstance(i, int):` 把 extra 批次（ids 为 str）的每个 id 都跳过，`source.jsonl` 写成只含 `"\n"` 的文件，`build()` 仍返回 0。真实数据 339 批中 165 批（48.7%）是 `lane:"extra"`，全部受影响；`"\n".splitlines() == ['']`，下游 `json.loads('')` 直接 `JSONDecodeError`。

**修复**（按控制器裁决"按接口总表实现"）：
1. `_load` 新增读取 `data/ledger_extra.jsonl`（沿用既有 `.exists()` 容错风格），建 `{key: row}` 字典存入 `env["extra"]`。
2. `build()` 的取行循环改为按类型分派：`int` 且在 `env["ledger"]` → 走 main/ambient 路径（可带 `base`）；`str` 且在 `env["extra"]` → 走 extra 路径（`{"id": <str key>, "jp": <jp>}`，**不带** `base`，因 `resolve_map` 只按 int id 建）；两者都不满足 → `raise ValueError`，消息含批号、`id!r`、类型名。不再有静默丢行的分支。
3. `source.jsonl` 零行时写空串（`"" `）而不是 `"\n"`，使 `.splitlines()` 得到 `[]` 而不是 `['']`。

### Finding 2：`SYN_CARDS` 死代码，「已完结章的章梗概卡」机制未接线

**控制器已核实的事实**：`skeleton/cards.zh.yaml` 196 条含全部卡 133–145，`_render_skeleton` 对任何 profile/批次都完整渲染全部卡——「已完结章的章梗概卡」本就已被骨架小节覆盖，接口那句话是描述骨架提供了什么，不是要求额外挑选机制。

**修复**：
1. 删除未使用的 `SYN_CARDS` 表。
2. 在 `_render_skeleton` 上方加注释说明上述事实（骨架恒定完整渲染 → 已完结章梗概卡天然在内；profile 差异只体现在 `_render_prefix` 丢弃别章细文）。
3. 顺带清理同源死元素：`_render_prefix` 里只增不读的 `missing` 计数器；`_load` 里读入后从未消费的 `env["timeline"]`（连带去掉这次没必要的 `read_jsonl(data / "timeline.jsonl")` IO）。

这条本身不改变任何行为（新增的判别性测试在修复前后都应为绿——用于确认这一点，见下）。

### 新增判别性测试（4 条，既有 3 条零改动）

修复前逐条跑（除 api-B/cc 一条外应为 RED，验证测试确实在测对应产码）：

```
$ uv run pytest tests/test_build_context.py -v
tests/test_build_context.py::test_ctx_files_and_manifest PASSED
tests/test_build_context.py::test_baseline_only_touches_tail PASSED
tests/test_build_context.py::test_untranslated_prefix_requires_fallback PASSED
tests/test_build_context.py::test_extra_lane_produces_readable_source FAILED
tests/test_build_context.py::test_zero_row_batch_yields_empty_source FAILED
tests/test_build_context.py::test_unknown_id_raises_with_context FAILED
tests/test_build_context.py::test_apiB_and_cc_skip_other_chapter_prefix PASSED
=================== 3 failed, 4 passed in 0.13s ===================
```

三处失败均为预期原因（不是巧合失败）：
- `test_extra_lane_produces_readable_source`：`json.loads('')` → `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`（source.jsonl 被写成空壳）。
- `test_zero_row_batch_yields_empty_source`：`text == '\n'`，断言 `text == ""` 失败。
- `test_unknown_id_raises_with_context`：裸 `KeyError: 999`（无批号/类型上下文，也不是 `ValueError`），命中 `tools/build_context.py:75`。

`test_apiB_and_cc_skip_other_chapter_prefix` 修复前就 PASSED——印证 Finding 2 是纯死代码问题、不是行为缺陷，这条测试的作用是补上此前缺失的回归覆盖，而非验证一次修复。

修复后（GREEN）：

```
$ uv run pytest tests/test_build_context.py -v
tests/test_build_context.py::test_ctx_files_and_manifest PASSED          [ 14%]
tests/test_build_context.py::test_baseline_only_touches_tail PASSED      [ 28%]
tests/test_build_context.py::test_untranslated_prefix_requires_fallback PASSED [ 42%]
tests/test_build_context.py::test_extra_lane_produces_readable_source PASSED [ 57%]
tests/test_build_context.py::test_zero_row_batch_yields_empty_source PASSED [ 71%]
tests/test_build_context.py::test_unknown_id_raises_with_context PASSED  [ 85%]
tests/test_build_context.py::test_apiB_and_cc_skip_other_chapter_prefix PASSED [100%]
============================== 7 passed in 0.08s ===============================
```

全套回归：

```
$ uv run pytest -q
90 passed in 2.28s
```

83（Task 6 基线）+ 3（Task 7 首轮）+ 4（本轮新增）= 90，零回归。既有 3 条用例的测试体与共享 `_env()` 夹具**逐字节零改动**（`git diff` 只在文件末尾追加新函数，已核对）。

### 真实数据验收

```bash
$ uv run python tools/build_context.py --batch 1 --profile cc --baseline none
exit 0；work/ctx/batch_1/source.jsonl 仍 339 行（不受影响）

$ uv run python tools/build_context.py --batch 174 --profile cc --baseline none
exit 0（修复前会静默产出坏文件，现在真实产出）
```

**batch 174**（`lane:"extra"`，`chapter:"snr_common"`）：

- `source.jsonl`：**195 行**，全部可 `json.loads`，`id` 全为 str，**均不含** `base`。首行：
  ```json
  {"id":"plotTitle:1","jp":"ある子が学校にくる物語"}
  ```
  末行：`{"id":"plotTitle:99","jp":"セクション６：アヤノ"}`
- `context.md` 的 `"## 五、本批任务"` 段前两行：
  ```
  ## 五、本批任务（baseline=none）
  [plotTitle:1] ある子が学校にくる物語
  ```
- `manifest.json`：`{"batch":174,"profile":"cc","baseline":"none","glossary_v":6,"skeleton":"f5edfcd1...b2399","anchors":"2ea7a623...2599b7","ctx_sha":"5b136727...05c5d3"}`（skeleton/anchors 哈希与 batch 1 时相同——同一份骨架/锚点文件，符合预期）。

**baseline 尾部不变量复核**（修复后，真实全量数据，覆盖 main 与 extra 两种车道）：

```bash
# batch 1（main 车道）
uv run python tools/build_context.py --batch 1 --profile cc --baseline none
uv run python tools/build_context.py --batch 1 --profile cc --baseline revise --jp-fallback
# batch 174（extra 车道）
uv run python tools/build_context.py --batch 174 --profile cc --baseline none
uv run python tools/build_context.py --batch 174 --profile cc --baseline revise
```

用 Python 按 `"## 五、本批任务"` 切分两次运行的 `context.md` 并比较前半段：

```
batch1   prefix head byte-identical: True  len=33851
batch1   tail differs: True
batch174 prefix head byte-identical: True  len=33853
batch174 tail differs: True
```

两条车道下不变量均成立：`baseline` 切换只改变 `"## 五、本批任务"` 之后的内容，之前的字节完全相同。

### 改了哪些文件（本轮）

- `tools/build_context.py`：`_load` 增读 `ledger_extra.jsonl`；取行循环按类型分派并对未知 id 报错；`source.jsonl` 零行写空串；删除 `SYN_CARDS`；`_render_skeleton` 加注释；清理 `missing`/`env["timeline"]`。
- `tests/test_build_context.py`：追加 `import pytest` 与 4 条新测试函数；既有内容零改动。
- 未触碰 `config/`、`data/`、`skeleton/`、`glossary/`、`tools/` 下其它脚本、`tests/` 下其它测试。

commit：`6fabe0c fix: build_context 评审修复轮（extra 车道读取 + SYN_CARDS 死代码清理）`

### 自评审（本轮）

- 两条 Finding 均按控制器裁决的具体改法逐项落实，未发挥、未扩大范围。
- 新增异常选型为 `ValueError`（`raise ValueError(...)`），与本仓库既有先例（`tools/gen_timeline.py` 的 `run_plan` 对未知移动键同样 `raise ValueError` 并在测试里用 `pytest.raises(ValueError, match=...)`）保持一致，未发明新风格。
- `source.jsonl` 的零行防御性修复虽然是由 extra 车道触发发现的，但改动本身是通用的（任何车道 0 行都受益），未过度设计出额外分支。
- extra 行的 `tail.append` 复用了与 main 行相同的 `f"[{i}] {row['jp']}"` 格式（`baseline!="none"` 时因 extra 行没有 `base`，`row.get('base','')` 落到 `''`，即 `\n    base: `——空白但存在的一行，行为与"未译且无 base"的 main 行一致，未额外分支处理，符合"尾部对 extra 行同样输出一行，沿用 `[{id}] {jp}` 样式"的裁决原意）。
- 全程未修改 `progress.md`（历史上由控制器/协调会话记账，非实现者职责范围）。

### 遗留顾虑（本轮新增，无）

无新增顾虑；首轮报告里的"api-B/cc 分支此前无回归测试"顾虑已随本轮新增的 `test_apiB_and_cc_skip_other_chapter_prefix` 解决。
