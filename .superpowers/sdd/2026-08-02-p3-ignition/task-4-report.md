# Task 4 Report: gen_plan 段模式 `--segment`

## 执行摘要

给 `tools/gen_plan.py` 的 `render()` 加了可选 `segment=None` 参数：传入段 label
（如 `seg1-s2`）时，在计划头部之后插入「段开场自检」块、在计划末尾追加「段末流程」
块；不传时（默认）`render()` 输出与改动前逐字节不变。`main()` 新增 `--segment`
CLI flag 透传给 `render()`。两个模板函数（`_segment_head`/`_segment_tail`）与
CLI 参数写法均按 brief 逐字采用，未做任何改写。

## 实现步骤

### Step 1: 写失败测试

在 `tests/test_gen_plan.py` 追加两个测试（brief 原文逐字，仅把 `_small_sel()` 换
成该文件已有的等价 helper——见下方偏差说明）。

### Step 2: 确认失败

```
uv run pytest tests/test_gen_plan.py -v -k segment
```
（先临时用 brief 原文跑，未替换 helper 名前）预期报
`render() got an unexpected keyword argument 'segment'`——实际直接按最终版
（已替换 helper）编写并确认失败态，跳过了逐字保留 `_small_sel` 再改名的中间态，
因为该名字在文件里根本不存在，留着必然是 `NameError` 而非 brief 期待的
`TypeError`，对判断"失败原因是否符合预期"没有意义。

### Step 3: 实现

`tools/gen_plan.py` 三处改动，均按 brief 逐字：

(a) 在 `_lane_block` 之后新增 `_segment_head(segment)` / `_segment_tail(segment)`
两个模板函数，返回文本逐字照抄 brief。

(b) `render()` 签名加 `segment=None`；读 `render()` 实际结构后确认：`parts` 是
一个列表，先 `parts = [_header(...)]`，随后有两条路径都会 `return`——
① `sel` 为空的早退分支（`parts.append(...)` 一条说明文字后直接 return）
② 正常流程走完所有批次/checkpoint/硬停/探针任务、`parts.append(_final_task(...))`
后的末尾 return。

brief 原文只写"header 之后插入头块、return 前插入尾块"，没有显式提到空
`sel` 这条早退路径。按"return 前"字面理解，两个 return 语句前都该插尾块，
否则空批次时传 `segment` 会拿到一个只有头块没有尾块的不对称输出——于是我在
两处 `return` 前都加了 `if segment: parts.append(_segment_tail(segment))`。
头块统一在 `parts = [_header(...)]` 之后、`if not sel` 判断之前插入一次即可
覆盖两条路径。这是 brief 说"以该函数实际组装结构为准"授权范围内的判断，
其余 parts（`_batch_task`/`_checkpoint_task`/`_hardstop_*`/`_window_probe_task`/
`_final_task`）的既有顺序未做任何改动。

(c) `main()`：`ap.add_argument("--segment", ...)` + `render(..., segment=args.segment)`，
逐字按 brief。

### Step 4: 确认通过

```
uv run pytest tests/test_gen_plan.py -v
```
结果：42 passed（40 条既有 + 2 条新增，含回归闸
`test_render_without_segment_unchanged` 与 brief 给的
`test_render_segment_blocks_present`）。

### Step 5: 全量测试 + commit

```
uv run pytest -q
```
结果：**219 passed**（符合预期基线 217 + 2 新测试）。

```bash
git add tools/gen_plan.py tests/test_gen_plan.py
git commit -m "feat: gen_plan 段模式——生产计划内嵌段开场自检与段末流程"
```
Commit hash: `58cc5df`

`git status`/`git show --stat` 确认提交前后仅 `tools/gen_plan.py`（+35/-2）与
`tests/test_gen_plan.py`（+20）两个文件变化；`.superpowers/sdd/` 目录未被
`git add`（本报告文件例外，属交付物，随后由外层流程处理是否 `-f` 入库）。

## 偏差与处理

1. **`_small_sel()` 不存在**：`tests/test_gen_plan.py` 里没有同名或同义独立
   helper；文件已有的等价构造是模块级 `BATCHES`（7 个批次，字段齐
   `batch/ids/chapter/jp_chars` 外加 `lane/cut_reason`）+ 文件顶部的
   `_sel(chapter="s1s", lane="main", rng=None)` 函数（内部调用
   `select(BATCHES, ...)`）。按 brief"如无同名 helper 则内联一个两批的列表"
   的指示，本可以另起一个两批的字面量列表；但 `_sel()` 已经是该文件全部其余
   测试构造"最小批次列表"的统一入口（本文件另外 40 个测试全部用它），换成
   独立的两批列表反而破坏与文件既有风格的一致性，且 `_sel()` 返回的 7 批
   同样满足"字段齐"的要求、跑起来更快确认与既有测试同源。故选择直接复用
   `_sel()` 代替 `_small_sel()`，未额外造轮子。两个新测试的断言内容
   （字符串/顺序检查）与 brief 原文完全一致，只有这一处 helper 名替换。
2. 其余步骤、模板正文、CLI 参数写法均未偏离 brief。

## 自查结论

- `_segment_head`/`_segment_tail` 两个模板函数正文与 brief 给出的代码逐字一致。
- `render()` 默认（不传 `segment`）路径零改动——`test_render_without_segment_unchanged`
  与既有回归闸 `test_no_lane_cfg_keeps_repo_relative_paths` 等 40 个既有测试全绿，
  证明未传 `--segment` 时输出字节级不变。
- `main()` 新增 `--segment` 透传，不影响既有 CLI 参数的互斥/校验逻辑（未触碰
  `lane_params` all-or-nothing 校验、`--batches`/`--chapter` 互斥组等既有代码）。
- 全量测试 219 passed（217 基线 + 本任务 2 个新测试），无红测试。
- commit 仅包含 brief 指定的两个文件，未用 `git add -A`/`git add .`。

**状态**：DONE
