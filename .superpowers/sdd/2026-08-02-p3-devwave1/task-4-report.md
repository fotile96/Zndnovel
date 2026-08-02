# Task 4 报告：gen_plan 段模式收口（parked 两项）

**状态**：完成。
**commit**：`0d8e6bf`（fix: 段模式强制 --tools-root 并由段表推导/校验 lane）。
**测试**：`255 passed`（基线 251 + 本任务新增 4 条）。
**逐字节回归**：**一致**——3 组非段模式输入（chapter 模式 / 车道+连续段 / 纯 `--lane main --batches` 无车道）新旧 `render()`/`select()` 输出 sha256 全部相同。
**SEG-2 实跑**：**通过**——`docs/ops/p3-production-handoff.md` 换段命令模板对 `seg2-s3` 原样可用（`--lane main` 与段表 `lane: main` 校验通过，四件套 Run 行正确带生产树前缀），验证后已删除产物、未留痕。

---

## 背景与两个缺口

上一轮终审 parked：
① 段模式下漏传 `--tools-root` 会产出「自称已钉死、实则用主仓相对路径」的计划；
② `--lane` 与 `--segment` 无交叉校验，错配时 `select()` 按 lane 过滤会静默产出空计划（段号对但车道错，选中批次恰好是空集）。

`gen_plan.py` 是生产会话会直接从主仓调用的工具（换段时用），不在钉死的生产树保护范围内，本次改动即时生效到生产。全程与另一并发生产会话（SEG-1，b41 前后）共享同一工作树，按纪律只改 4 个指定路径。

## Step 1–2：先写失败测试，跑红

按 brief 原样在 `tests/test_gen_plan.py`、`tests/test_segments.py` 追加 4 条测试后跑：

```
$ uv run pytest tests/test_gen_plan.py tests/test_segments.py -v -k 'tools_root or lane_from or still_requires or lane_field'
```

4 条全红（`segments.yaml` 无 `lane` 字段导致 `test_segments_lane_field_matches_batches` KeyError；`gen_plan` 尚无 tools-root/lane 校验，`--lane` 仍 `required=True` 使 `test_segment_mode_requires_tools_root`/`test_segment_mode_lane_from_table_and_mismatch_errors` 因缺 `--lane` 直接被 argparse 拦下、报错形态与预期的 `SystemExit(match=...)` 不符）——与 brief 预告的「以实际失败形态为准，只要 4 条全红」一致。

## Step 3：实现

### `config/segments.yaml`

9 段各加一行 `lane`，按对 `data/batches.jsonl` 的实算（脚本核对，见下）：seg1–7 = `main`，seg8-extra = `extra`，seg9-ambient = `ambient`——与任务上下文给出的提示吻合，未凭空照抄，是脚本对 `data/batches.jsonl` 逐段求 `{by[b]["lane"] for b in range(lo, hi+1)}` 的结果：

```
1 seg1-s2 main   2 seg2-s3 main   3 seg3-s4 main   4 seg4-s3tail-s5 main
5 seg5-s6-s7f main   6 seg6-s8-e1 main   7 seg7-e2 main
8 seg8-extra extra   9 seg9-ambient ambient
```

### `tools/gen_plan.py`

- `--lane` 改 `required=False`。
- 新增 `segment_entry(label, repo=None)`（返回段表完整条目，含 `lane`），`segment_range()` 改为基于它取批号（对外行为不变，未被任何测试直接调用，重构安全）。
- `main()` 分支重写：
  - **段模式**（`args.segment`）：先取 `seg_entry = segment_entry(args.segment)`（未知 label 在此报错，先于其余校验）；`seg_lane = seg_entry.get("lane")`；`args.lane` 为 `None` 时取 `seg_lane`（若段表也未登记则报「--lane 必填」防御性兜底）；`args.lane` 非 `None` 且与 `seg_lane` 不等时 `SystemExit(f"--lane {args.lane} 与段表 {label} 的 lane={seg_lane} 不符")`；随后校验 `args.tools_root` 非空，缺失报 `SystemExit("--segment 模式必须给 --tools-root（...docs/ops/p3-production-runbook.md §3）——漏传会产出未钉死的计划")`。
  - **非段模式**（`--batches` / `--chapter`）：`args.lane is None` 时各自报 `SystemExit("--lane 必填")`，其余逻辑一字不动。
  - `render()` 调用改用局部解析出的 `lane` 变量（原先是 `args.lane`），三个分支现在都显式赋值 `lane`。

### 与既有测试的必要冲突处理（偏离 brief 之处，已记录）

brief 只要求「追加」测试，但字面实现「段模式下 `--tools-root` 必填」后，`tests/test_gen_plan.py` 里**改动前就存在**的两条测试与新规则直接冲突：

- `test_main_segment_derives_batches_from_segments_yaml`
- `test_main_segment_batches_override_wins`

两者都调用 `main(["--lane", "main", "--segment", "seg1-s2", ...])` 但未传 `--tools-root`，改动前用的 fixture `SEGMENTS_YAML`（该测试文件内联的段表文本）也没有 `lane` 字段。字面实现新规则后二者会从 `assert ... == 0` 变成 `SystemExit`。因为 Step 5 要求整个测试文件全绿（`uv run pytest tests/test_gen_plan.py tests/test_segments.py -v` → 全 passed），只追加不改会导致这两条转红，与「已两次用此法」的逐字节回归纪律不冲突（它们是段模式新语义下必然过时的用例，不在"非段模式"回归范围内）——处置：给这两条测试补上 `--tools-root "/tmp/prod"`，其余断言不动。`test_main_segment_unknown_label_exits`（未知 label，未传 tools-root）不受影响：`segment_entry()` 对未知 label 的报错发生在 tools-root 校验之前，`pytest.raises(SystemExit)` 不带消息匹配，两种报错路径都满足。
`test_main_segment_forwards_tools_root`、`test_main_requires_one_of_chapter_batches_segment` 无需改动。

fixture `SEGMENTS_YAML` 本身未加 `lane` 字段（保持最小改动）：`main()` 对 `seg_entry.get("lane")` 返回 `None` 时跳过错配校验、只信 `args.lane`——这是刻意的防御性宽松（段表条目缺 `lane` 时不阻断，只是放弃交叉校验），因为这几条测试用 `--lane main` 显式给出，不依赖段表推导。

## Step 4：跑测试 + 非段模式逐字节回归

```
$ uv run pytest tests/test_gen_plan.py tests/test_segments.py -v
======================== 63 passed in 0.16s ========================
```

逐字节回归：取 `git show HEAD:tools/gen_plan.py`（本任务改动前的提交 `c786945`）到
`/private/tmp/.../scratchpad/gen_plan_old.py`，用 `importlib.util.spec_from_file_location`
分别加载新旧模块（`tools.pipelib`/`tools.build_context` 的导入未变，两者共用当前仓库的
同一份），对 3 组**不传 `--segment`** 的输入调用 `select()`+`render()`，比较 sha256：

| 用例 | 说明 | old sha256(16) | new sha256(16) | 结果 |
|---|---|---|---|---|
| chapter-mode | `--chapter s1s --lane main`，无 lane_cfg | `83a971a8b4df0da1` | `83a971a8b4df0da1` | 一致 |
| lane-batches-1-35 | 车道模式 `--batches 1-35`（`lane_cfg` 非空，brief 点名的车道模式） | `82a42d6869253c0a` | `82a42d6869253c0a` | 一致 |
| plain-batches-1-35-no-lane-cfg | `--lane main --batches 1-35`，无 `lane_cfg` | `3b5188bb2d7b15a3` | `3b5188bb2d7b15a3` | 一致 |

```
[OK] chapter-mode: old=83a971a8b4df0da1 new=83a971a8b4df0da1
[OK] lane-batches-1-35: old=82a42d6869253c0a new=82a42d6869253c0a
[OK] plain-batches-1-35-no-lane-cfg: old=3b5188bb2d7b15a3 new=3b5188bb2d7b15a3
ALL OK
```

脚本：`/private/tmp/claude-501/-Users-fotile96-Zndnovel/dc6840f4-0865-4977-a49b-81d37c23e706/scratchpad/regress_gen_plan.py`（scratchpad 内，不入库）。

## SEG-2 实跑验证（`docs/ops/p3-production-handoff.md` 换段命令模板）

用 brief 与生产交接文档给出的完整命令模板，段名换成 `seg2-s3`（未占用、不影响在产的 `seg1-s2`）：

```
$ uv run python tools/gen_plan.py --lane main --segment seg2-s3 --label seg2-s3 \
    --tools-root /Users/fotile96/Zndnovel-prod \
    --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus \
    --model opus --effort max --append-model-id claude-opus-5
docs/superpowers/plans/translate-seg2-s3.md: 34 个任务
rc=0
```

核验：
- 批次范围 63–90（28 批，`grep -o "batch [0-9]*" ... | sort -u -n` 首尾为 63 / 90），与 `config/segments.yaml` seg2-s3 的 `batches: [63, 90]` 一致。
- 四件套 Run 行正确带 `/Users/fotile96/Zndnovel-prod/tools/…` 前缀，`grep -c "python tools/build_context"`（裸主仓相对形态）= 0——无残留。
- 段开场自检 / 段末流程块均生成，`prod-opus-seg2-s3-done`、`lane_setup.py --lane opus --verify` 均出现。

失败模式实测（同一条命令，分别去掉 `--tools-root` 与改用不匹配的 `--lane extra`）：

```
$ ...(缺 --tools-root)...
--segment 模式必须给 --tools-root（生产 worktree 绝对路径，见 docs/ops/p3-production-runbook.md §3）——漏传会产出未钉死的计划
rc=1
$ ...(--lane extra)...
--lane extra 与段表 seg2-s3 的 lane=main 不符
rc=1
```

验证后立即 `rm -f docs/superpowers/plans/translate-seg2-s3.md`；`git status --porcelain docs/superpowers/plans/` 干净，未留任何 SEG-2 产物。全程未生成、未触碰 `pilot/lanes/`、`prompts/`、`.superpowers/sdd/2026-08-02-p3-seg1-s2/`、`docs/superpowers/plans/translate-seg1-s2.md`。

（过程中曾误跑一次 `main(["--lane", "main", "--chapter", "s0f", "--label", "s0f-smoke-check"])` 做 smoke check——`--chapter` 模式下 `--label` 被忽略、按 brief 指出的既有行为写到了 `translate-s0f.md`，是未跟踪的新文件，已当场 `rm` 清理，`git status` 确认无残留。这次误操作未涉及任何 `--segment` 路径，不影响上面的 SEG-2 验证结论。）

## Step 5：全量测试 + commit

```
$ uv run pytest -q
255 passed in 1.50s
```

（基线 251 + 本任务 4 条：`test_segment_mode_requires_tools_root`、
`test_segment_mode_lane_from_table_and_mismatch_errors`、
`test_nonsegment_mode_still_requires_lane`、`test_segments_lane_field_matches_batches`。）

`git status --porcelain` 改动前后对比：只有指定 4 个路径被改动。另检出
`.superpowers/sdd/2026-08-02-p3-seg1-s2/progress.md` 被并发生产会话修改（新增批 41 记录，
`git diff` 核实为纯追加，非本任务所改）——按纪律**未 `git add`**，未触碰。

```bash
git add tools/gen_plan.py config/segments.yaml tests/test_gen_plan.py tests/test_segments.py
git commit -m "fix: 段模式强制 --tools-root 并由段表推导/校验 lane（点火终审 parked 两项）"
```

全程只 `git add` 这 4 个具体路径，未用 `git add -A`/`.`；未碰 `pilot/lanes/`、`prompts/`、
`.superpowers/sdd/2026-08-02-p3-seg1-s2/`、`docs/superpowers/plans/translate-seg1-s2.md`。

---

## 偏差汇总

1. **修改了两条 brief 未提及的既有测试**（`test_main_segment_derives_batches_from_segments_yaml`、
   `test_main_segment_batches_override_wins`，各加一个 `--tools-root "/tmp/prod"` 参数）——
   原因见 Step 3 小节，属实现新增强制校验后的必然连带，不改会导致 Step 5 无法全绿。
   除新增这一个参数外未改动其余断言逻辑。
2. `SEGMENTS_YAML`（`tests/test_gen_plan.py` 内联 fixture）未加 `lane` 字段，`main()` 对此
   防御性地跳过错配校验（只信 `--lane`）——真实 `config/segments.yaml` 9 段均已加
   `lane`，生产路径不受影响。
3. Step 5 brief 原文写「248 passed」，与任务下达时给出的基线（251 passed，+4 应为
   255）不一致；以后者为准，本报告以 255 通过为最终判定。

## 顾虑

- `SEGMENTS_YAML` fixture 缺 `lane` 字段时错配校验被跳过，理论上如果未来有人往真实
  `config/segments.yaml` 加一个漏填 `lane` 的段，`--lane` 传参错误只会静默通过而非报错——
  但 `test_segments_lane_field_matches_batches` 会在同一测试文件里拦下"段表 lane 与
  batches.jsonl 实算不符"的情形（前提是 `lane` 字段本身存在）；若段表整段漏填 `lane`
  键，目前没有测试专门盯这一点。风险很低（9 段已全部补齐），仅记录以备将来扩表时留意。
