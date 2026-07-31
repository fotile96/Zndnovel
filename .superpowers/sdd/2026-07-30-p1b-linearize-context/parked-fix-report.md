# Park 项落地报告（A + B）

用户裁决：两项 park 议题都要做。本报告记录实现、判别性测试的 RED/GREEN 证据、
真实数据验收、回归结果、自评审与遗留顾虑。

commits：
- `0793e98` `fix: build_context 的 api-B/cc 前缀改用时间轴位置窗口，不再按 chapter 相等过滤`
- `1ab5a74` `fix: recall 按生效译文（含 patches 覆盖）的术语表版本判断陈旧`

---

## A. `build_context.py`：api-B/cc 前缀改用时间轴位置窗口

### 改法

`tools/build_context.py`：

- **18**：新增模块级常量 `CHAPTER_CARD_SRCS = {f"snr_crd_{n}" for n in range(133, 146)}`——章梗概卡的 script 单元 `src` 集合（crd_133..145），窗口边界识别专用；注释里明确写了"与 Task 7 删掉的 SYN_CARDS 是两回事，不要复活后者"。
- **56-62**：新增 `_id_to_seq(timeline) -> dict`——把 `timeline` 里每个 unit 的 `ids` 映射到该 unit 的 `seq`（marker 行没有 `ids`，不参与）。
- **67-91**：新增 `_window_start_seq(env, batch_no)`——核心窗口起点算法：
  - 本批 `seqs` 为空（extra/ambient 车道，无时间轴位置）→ 返回 `None`；docstring 与内联注释都写明这是刻意选择（extra 车道装的是卡面/UI 文本，正文由骨架卡组本身承载），不是 chapter 比较失配的副产物。
  - 否则取 `min(本批 seqs)`，在 `env["timeline"]` 里找 `src ∈ CHAPTER_CARD_SRCS` 且 `seq < min_seq` 的 unit，取这些候选里 `seq` 最大的一个作为窗口起点（**含边界自身**，用 `>=` 收窄——边界单元自身的正文是该章收尾的现实层框架剧情，不是骨架卡组已经承载的卡面梗概，仍需保留；真实数据核对见下）。
  - 一个候选都没有 → 返回 `0`（全书开头，序章批次的情形，窗口退化为"全部前序"）。
- **96-117**：重写 `_render_prefix`——**窗口过滤在"未译则报错"循环之前完成**（brief 特别提醒的顺序问题）：
  ```python
  if profile in ("api-B", "cc"):
      window_start = _window_start_seq(env, batch_no)
      if window_start is None:
          prior_ids = []          # 无时间轴位置：前缀只留骨架
      else:
          id2seq = _id_to_seq(env["timeline"])
          prior_ids = [i for i in prior_ids if id2seq.get(i, -1) >= window_start]
  resolved = {}
  for i in prior_ids:      # 循环只会看到已经按窗口收窄后的 id
      ...
  ```
  `prior_ids` 先按窗口收窄，随后的"是否已译"循环只遍历收窄后的子集——窗口外的 id 根本不会进入这个循环，因此也不会因未译触发 `return None, i`（对应退出码 2）。`api-A` 完全不进入这个分支，`prior_ids` 保持原样（全部已译 timeline 前缀，语义不变）。
  - 结构渲染（marker/标题穿插）部分**未改动语义**，只更新了两处引用"chapter 过滤"的注释措辞为"窗口过滤"（原逻辑本就是通用的、按 `resolved` 集合渲染，不关心过滤依据是 chapter 还是窗口）。
- **38-42**：顺手订正了 `_render_skeleton` 头部一处过时注释（"profile 差异只体现在 `_render_prefix` 对**别章细文**的丢弃"→"对**窗口外细文**的丢弃"），避免自评审时发现的注释与实现脱节。
- `_render_prefix` 签名保持 `(env, batch_no, profile, jp_fallback)`，**没有**接回 `baseline` 参数（brief 明确要求维持这条性质）。

### 判别性测试（`tests/test_build_context.py`）

4 条新用例 + 1 条改写，共享新增的样板构造器 `_mk_env`/`_ledger_row`/`_unit_row`/`_batch_row`/`_fwd_row`（222-263 行）。

| 测试 | 行号 | 覆盖的 brief 语义 |
|---|---|---|
| `test_window_prefix_keeps_only_content_after_last_chapter_card` | 265 | 测试 1 + 5：有边界——cc 只拿边界（含边界自身）之后的正文，api-A 拿全部，且 cc 更短；同时是旧 `test_apiB_and_cc_skip_other_chapter_prefix` 的改写 |
| `test_window_start_is_zero_when_no_chapter_card_precedes_batch` | 317 | 测试 2：无边界——起点为 0，窗口＝全部前序 |
| `test_empty_seqs_batch_cc_prefix_is_skeleton_only` | 334 | 测试 3：`seqs` 为空（extra 车道形态）——前缀只剩骨架，不报错不退出 2 |
| `test_untranslated_id_outside_window_does_not_trigger_exit_2` | 357 | 测试 4（"最容易写错"那条）：窗口外未译 id 不触发退出码 2 |

四条用例的夹具都刻意让"旧 chapter 相等语义"与"新窗口语义"在同一份数据上给出**不同**答案（详见各测试 docstring），因此不仅对"去掉窗口逻辑"判红，对"整个改回旧实现"也判红。

此外为兼容真实 schema（`timeline.jsonl` 每行必有 `seq`，`batches.jsonl` 每行必有 `seqs`），给 `_env`/`_multi_unit_env` 及另外 4 个原地构造 `batches.jsonl` 的既有测试补了 `seq`/`seqs` 字段（这些字段此前完全不存在，纯 schema 补全，不改变原测试的断言/行为）。

### RED/GREEN 证据

**第一轮（补 `seq`/`seqs` schema 字段，未改产码）**：确认 11 个既有测试仍全绿（无回归）：
```
$ uv run pytest -q tests/test_build_context.py
...........                                                              [100%]
11 passed in 0.39s
```

**第二轮 RED（写好 4 条新用例 + 改写第 5 条，产码仍是原 chapter 实现）**：
```
$ uv run pytest -q tests/test_build_context.py
...
FAILED tests/test_build_context.py::test_window_prefix_keeps_only_content_after_last_chapter_card
FAILED tests/test_build_context.py::test_window_start_is_zero_when_no_chapter_card_precedes_batch
FAILED tests/test_build_context.py::test_empty_seqs_batch_cc_prefix_is_skeleton_only
FAILED tests/test_build_context.py::test_untranslated_id_outside_window_does_not_trigger_exit_2
4 failed, 10 passed in 0.48s
```
（10 passed = 11 条既有用例中，被替换掉的 `test_apiB_and_cc_skip_other_chapter_prefix` 已不存在，其余 10 条不受影响仍绿。）

**第三轮 GREEN（落地窗口实现后）**：
```
$ uv run pytest -q tests/test_build_context.py
..............                                                           [100%]
14 passed in 0.17s
```

**第四轮：专项验证"顺序敏感"这条最容易写错的语义**——临时把 `_render_prefix` 改成 brief 警告的反例写法（先对**全部** `prior_ids` 跑"是否已译"循环得到 `resolved`，**之后**才用窗口过滤 `resolved`，即"先判未译再过滤"）：
```
$ uv run pytest -q tests/test_build_context.py
FAILED tests/test_build_context.py::test_empty_seqs_batch_cc_prefix_is_skeleton_only
FAILED tests/test_build_context.py::test_untranslated_id_outside_window_does_not_trigger_exit_2
2 failed, 12 passed in 0.18s
```
精确命中测试 3、4（两条都构造了"窗口外/无时间轴位置 + 未译"的场景），其余 12 条（含测试 1、2）因夹具里窗口外内容本就已译而未受这条顺序 bug 影响——恰好证明测试 3、4 是专门盯防这条顺序问题的判别性用例。验证后用 `git diff`/`git checkout` 核对并把文件还原为正确实现（`git checkout` 顺带把当时尚未 add 的产码改动整个重置回 HEAD，随后重新应用了与还原前逐字节相同的正确实现——已用 `uv run pytest -q` 与人工比对源码确认一致，无遗漏）。

---

## B. `recall.py`：按生效译文的术语表版本判断陈旧

### 改法

`tools/recall.py::find`（9-66 行）：

- **9-17**：docstring 重写，明确"生效版本/生效译文"的定义——与 `tools.resolve` 的覆盖语义一致：forward 先铺，patches（若存在）后写覆盖，同 id 多条 patch 取最后一条（append-only）。
- **40-48**：新增"生效译文"构建：
  ```python
  effective = {}
  for row in read_jsonl(fwd_path):
      effective[row["id"]] = {"zh": row["zh"], "glossary_v": row["glossary_v"]}
  patches_path = data / "patches.jsonl"
  if patches_path.exists():
      for row in read_jsonl(patches_path):
          effective[row["id"]] = {"zh": row["zh"], "glossary_v": row["glossary_v"]}
  ```
  没有直接复用 `resolve.resolve_map`（只保留 `zh`），因为这里还需要与 `zh` **配对**的 `glossary_v`——两者必须来自同一条（forward 或 patch）行，不能分别取"最新版本号"与"最新 zh"错配（这一点在代码注释里写明了）。
- **50-66**：查询循环改为遍历 `effective.items()`，版本判断与命中输出都从 `eff["glossary_v"]`/`eff["zh"]` 取，不再读 `row["glossary_v"]`/`row["zh"]`（forward 原始行）。
- `find(term, glossary_v, data=None)` 签名不变；`main()` 的 `--emit-batch`/`--data-dir`/退出码逻辑未触碰；`patches.jsonl` 缺失时 `patches_path.exists()` 为假，直接跳过，行为与改前一致（优雅返回 `[]`，由 `fwd_path`/`ledger_path` 存在性检查覆盖）。

### 判别性测试（`tests/test_patch_recall.py`）

| 测试 | 行号 | 覆盖的 brief 语义 |
|---|---|---|
| `test_recall_excludes_id_patched_to_newer_version` | 34 | 测试 1：id 被 patch 到 v2 后，对 v2 查询不再召回，对 v3 仍召回 |
| `test_recall_uses_last_patch_when_multiple` | 54 | 测试 2：多条 patch 取最后一条（不误取第一条） |
| （既有）`test_recall_finds_stale_rows` | 13 | 测试 3：无 `patches.jsonl` 时行为不变——未改动，继续绿 |
| `test_recall_hit_zh_is_effective_translation_not_forward` | 75 | 测试 4：命中的 `zh` 是生效译文（patch 的），不是 forward 的 |

### RED/GREEN 证据

**RED（产码未改，即 brief 描述的原始行为）**：
```
$ uv run pytest -q tests/test_patch_recall.py
...
FAILED tests/test_patch_recall.py::test_recall_excludes_id_patched_to_newer_version
FAILED tests/test_patch_recall.py::test_recall_uses_last_patch_when_multiple
FAILED tests/test_patch_recall.py::test_recall_hit_zh_is_effective_translation_not_forward
3 failed, 2 passed in 0.08s
```
（2 passed = `test_add_patch_appends` 与既有的 `test_recall_finds_stale_rows`，均不受影响。）

具体失败信息（节选，`test_recall_uses_last_patch_when_multiple`）：
```
>       assert find(term="手帳", glossary_v=3, data=d / "data") == []
E       AssertionError: assert [{'id': 1, 'z...pter': 's1s'}] == []
E         Left contains one more item: {'id': 1, 'zh': '首译', 'chapter': 's1s'}
```
（`test_recall_hit_zh_is_effective_translation_not_forward`）：
```
>       assert hits[0]["zh"] == "新译"
E       AssertionError: assert '旧译' == '新译'
```

**GREEN（落地生效译文逻辑后）**：
```
$ uv run pytest -q tests/test_patch_recall.py
.....                                                                    [100%]
5 passed in 0.06s
```

---

## 真实数据验收

```bash
uv run python tools/build_context.py --batch 81  --profile cc    --baseline none --jp-fallback
uv run python tools/build_context.py --batch 81  --profile api-A --baseline none --jp-fallback
uv run python tools/build_context.py --batch 174 --profile cc    --baseline none      # extra 车道
uv run python tools/build_context.py --batch 1   --profile cc    --baseline none      # 序章，窗口起点 0
```
四条命令 exit=0。

### 批 81：cc vs api-A 的 `## 二、前缀正文` 段对比

| | cc | api-A |
|---|---|---|
| 正文行（每行一个 id 的译文/占位符，与 brief 锚点数字对应） | **1073** | **7350** |
| `### 【场景】` 标题行数 | 41 | 202 |
| marker 块数（每块 2 行：`text`+`recap`） | 12（24 行） | 41（82 行） |
| `## 二、前缀正文` 段落非空行总数 | 1138 | 7634 |

**1073 vs 7350 与 brief 已核实的真实数据锚点（"窗口内 1073；前序 id 7350"）逐一相符**，cc 前缀显著变小（约为 api-A 的 15%）。另外用 `--profile api-B` 对批 81 跑了一次同参数验证：`api-B` 与 `cc` 走同一分支，正文行数同为 1073，两者一致。

### 批 174（extra 车道，`lane=extra chapter=snr_common seqs=[] ids=195`）

`cc` 下 `## 二、前缀正文` 段落 `.strip()` 为空（`repr` 为 `'\n\n'`）——只有骨架，没有任何正文/占位符泄漏，且 exit=0（不报错、不因窗口外未译内容触发退出码 2）。

### 批 1（序章，`lane=main chapter=s0f seqs=[1,2,3,4,5] ids=339`，是最早的 main 批，没有任何 prior batch）

`cc` 下前缀同样为空（窗口起点算出来是 0，等价于"全部前序"，而"全部前序"本来就是空集，因为它是第一个 main 批），exit=0，行为与改动前完全一致——manifest 里的 `ctx_sha` 与本轮改动前 `work/` 里已有的 `batch_1/context.md` 哈希**逐字节相同**（`f884e29d1ddb6a25b9486c09e830628f34194be346eeb742315b9f311d5ef04b`），因为 batch 1 无论新旧逻辑 `prior_ids` 都是空集，不受窗口/chapter 过滤影响。同理 `batch_174` 的 `ctx_sha` 也与改动前逐字节相同（`c64b71e3...`）——旧逻辑下它是"chapter 恰好不匹配导致前缀恰好也是空"，新逻辑下是"无时间轴位置→刻意置空"，殊途同归，观感不变，但成因从 brief 指出的"语义失配的副产物"变成了"有意选择"。

---

## `check_timeline.py` + 三个生成器双跑字节确定性

```
$ uv run python tools/check_timeline.py
OK   (exit=0)

$ sha256sum data/dag.json data/timeline.jsonl data/batches.jsonl data/scene2card.json   # 改动前
5304fefb7c0c42e082a9c1e5ef511cd5af01e691b2625a3fde45a4412fc71607  data/dag.json
23933e9bf3c2dfac45aba7f33f509ea44dec3e98611a9b5a85e0be91f3cd995f  data/timeline.jsonl
1a8b661e74be8d594dae64a9905c1e03b39735ecb1c49f9082291b95b42355f3  data/batches.jsonl
8f0dc693cc5a0dc37059f25e647c57608196f29f3058d236ab71626103a990bc  data/scene2card.json

$ uv run python tools/build_dag.py        # states=405 scene_meta=527 crds=196, exit=0
$ uv run python tools/gen_timeline.py     # scene2card=157 moves=226 unit=457 marker=76 covered_ids=16693, exit=0
$ uv run python tools/gen_batches.py      # batches: 339 {'main': 173, 'extra': 165, 'ambient': 1}, exit=0

$ sha256sum data/dag.json data/timeline.jsonl data/batches.jsonl data/scene2card.json   # 双跑后
（四行哈希与"改动前"逐字节相同）

$ git status --short data/
（空——data/ 无任何漂移）
```
本轮完全没有触碰 `dag.json`/`timeline.jsonl`/`batches.jsonl`/`scene2card.json` 的生成逻辑（`tools/build_dag.py`、`tools/gen_timeline.py`、`tools/gen_batches.py` 均未改动），双跑只是按 brief 要求确认"没误伤"，结果确认无误伤。

---

## `work/` 树未被改动的验证

方法与最终修复轮报告一致：记录 `work/` 全树 sha256+mtime，跑 `uv run pytest -q`，再记一次，逐行 diff。本轮做了 4 次，覆盖不同阶段：

**第 1 次（改动开始前，作为会话基线）**：`work/` 里已有 Task 11 遗留的 `batch_1/30/70/174` 的 ctx 产物与 `batch_1.{check,draft,pass}.json`——`uv run pytest -q` → 105 passed → diff 空。

**第 2 次（落地 A+B 产码与全部新测试之后，尚未跑真实数据验收命令）**：
```
$ uv run pytest -q
111 passed in 3.42s
（work/ 全树 15 个文件的 sha256+mtime 逐行 diff → 空）
```

**第 3 次（关键场景：跑完 brief 要求的真实数据验收命令之后——这一步会真实写 `work/ctx/batch_1`、`batch_81`、`batch_174`，是预期内的、由我主动触发的产物更新，不是 pytest 造成的）**：先记录跑完验收命令后的 `work/` 状态（新增 `batch_81/{context.md,manifest.json,source.jsonl}`），再跑一次 `uv run pytest -q`：
```
$ uv run pytest -q
111 passed in 3.60s
（跑验收命令后 vs 跑这次 pytest 后，work/ 全树 sha256+mtime 逐行 diff → 空）
```

**第 4 次（提交后，含一次额外的 `--profile api-B` 真实数据 spot check，用于旁证 api-B 与 cc 走同一分支）**：spot check 会再次写 `work/ctx/batch_81`（写入 api-B 版本的 context.md，覆盖第 3 次时留下的 cc 版本，这是预期内的产物更新）；随后跑 `uv run pytest -q`：
```
$ uv run pytest -q
111 passed in 3.73s
（work/ 全树 sha256+mtime 逐行 diff → 空，CONFIRMED）
```

四次记录中，**`uv run pytest -q` 本身从未改动过 `work/` 树的任何字节或 mtime**；`work/` 里内容的变化全部来自我主动执行的 `build_context.py` 验收/spot-check 命令，且每次都发生在对应那次 pytest 快照**之前**。新增的 4+3 条测试全部通过 `repo=tmp_path`（`build()`）或 `data=tmp_path/"data"`（`find()`）传参，没有一条落到真实 `work/`/`data/` 上（已用 grep 核对：所有 `build(batch=...)` 调用都带 `repo=`，所有 `find(term=...)` 调用都带 `data=`）。

---

## 全套回归

```
$ uv run pytest -q
........................................................................ [ 64%]
.......................................                                  [100%]
111 passed in 3.4~4.7s（多次运行，时间有抖动，用例数稳定 111）
```
基线 105 passed → 111 passed（+6：A 净增 3 条【新增 4 条、改写替换 1 条】，B 净增 3 条），无回归。

`git status --short`：提交后为空；`git diff --stat`（提交前）确认改动范围严格限定在 `tools/build_context.py`、`tools/recall.py`、`tests/test_build_context.py`、`tests/test_patch_recall.py` 四个文件，未触碰 `data/`、`lua_scripts/`、`png/`、`skeleton/`、`glossary/`、`config/`、`prompts/`、`docs/`，也未触碰 `tools/` 下其余脚本。

---

## 自评审

**完整性**：
- A 的四种情形（有边界/无边界/`seqs` 为空/窗口外未译）均已实现（`_window_start_seq` 的三个返回分支 + `_render_prefix` 的过滤先于翻译检查）且均有专属判别性用例，逐条用 RED→GREEN 验证过；额外用"临时引入顺序反例"的方式专项验证了第 4 种情形（窗口外未译不报错）对"过滤顺序"这一最容易写错的点确实有判别力。
- B 的两处都改了：生效**版本**（`glossary_v`）与生效**译文**（`zh`）都从同一个 `effective[id]` 字典条目取出，避免"版本取最新、zh 取旧的"这类错配（已用专门测试解耦验证：`test_recall_hit_zh_is_effective_translation_not_forward` 把两个 `glossary_v` 设成相等，只让 `zh` 不同，专测这一点）。

**质量**：
- 命名：`CHAPTER_CARD_SRCS`/`_id_to_seq`/`_window_start_seq` 语义明确，与 brief 用词（"章梗概卡"、"时间轴位置"）对应。
- 注释：`_window_start_seq` docstring 与 `_render_prefix` 内联注释都写清了"extra/ambient 只给骨架是刻意选择，不是语义失配副产物"；`recall.find` 也写清了"与 resolve 覆盖语义一致"。自评审时额外发现并订正了两处遗留的"chapter 过滤"措辞（`_render_skeleton` 头部注释、`_render_prefix` 的 marker 门槛注释），避免注释与新实现脱节——这属于本轮改动直接牵涉的代码，不算越界重构。
- `_render_prefix` 未改签名、未接回 `baseline` 参数，`"## 五、本批任务"` 之前逐字节不受 `baseline` 影响的不变量继续由既有的 `test_baseline_only_touches_tail` 守护（该测试未改动，本轮验证仍绿）。

**纪律**：
- YAGNI：没有为"可能用到"的场景加参数或分支；`_id_to_seq`/`_window_start_seq` 都是 `_render_prefix` 直接需要的最小拆分（brief 建议里点名的两个助手函数）。
- 未触碰 `data/`、`lua_scripts/`、`png/`、`skeleton/`、`glossary/`、`config/`、`prompts/`、`docs/`，未触碰 `tools/` 下 A/B 之外的脚本（已用 `git diff --stat` 核对）。
- 没有复活 `SYN_CARDS`：`CHAPTER_CARD_SRCS` 锚定的是 script 单元的 `src`（"这一章已被压成一张あらすじ卡"的边界识别），不是 chapter→卡号的映射；代码注释里显式点明两者是两回事。

**测试**：
- 测的是真实行为（真实 schema 字段 `seq`/`seqs`，真实 `CHAPTER_CARD_SRCS` 命名模式 `snr_crd_1xx`），不是实现细节的镜像断言。
- 判别性：8 条新/改写测试逐条做过 RED（对未改动或刻意错误的产码）→ GREEN（对正确产码）验证，其中 A 的测试 3、4 额外做了"顺序反例"专项验证。
- 不写真实 `work/`：已用 grep 核对全部新增/改写测试调用都显式传 `repo=`/`data=` 到 `tmp_path`。
- 输出干净：`uv run pytest -q -W error::DeprecationWarning` 对改动的两个测试文件跑通无告警；全套 `pytest -q` 输出里没有 warning 行。

**未发现需要进一步修复的问题**——上面两处注释措辞已在本轮内直接订正，不作为遗留项。

---

## 遗留顾虑

1. **`_render_prefix` 内联注释里"批次 70"的旧数字（"34 条、58 行"）已被移除、改为不点名具体数字的定性描述**——因为窗口过滤与原 chapter 过滤对批次 70 给出的"排除范围"不同（用真实数据重新核过：新窗口语义下批次 70 有 29 条 marker 会在没有"至少渲染过一个 unit"这道门槛时泄漏到前缀最前面，不是原先的 34 条），继续沿用旧数字会造成误导。这不影响任何断言或产码正确性，纯粹是注释表述层面的取舍，供复核时知悉。
2. brief"问题"一节提到"main 车道 173 个批里有 121 段 chapter 切换"，本轮用真实 `batches.jsonl` 独立重算得到 120（相邻 main 批 chapter 变化次数）。这只是问题陈述里的背景数字，不是任何测试或产码依赖的值，怀疑是计数口径差 1（例如是否把"第一个批次视为从空 chapter 切入"计入），未深究，不影响本轮结论。
3. `_window_start_seq` 里 `id2seq.get(i, -1)` 的 `-1` 默认值是防御性写法——按现有不变量（main 车道 id 必被某个 timeline unit 覆盖，已在 Task 6 controller 复核中验证过），真实数据下这个默认值分支不会被触发；保留它是为了在假设被破坏时"失败关闭"（该 id 因 `-1 < window_start` 而被排除出前缀）而不是静默产生不可预期的行为，未额外为它写判别性测试（触发条件在真实数据/现有测试夹具下不可达）。
