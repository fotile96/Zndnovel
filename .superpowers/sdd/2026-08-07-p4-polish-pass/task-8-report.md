# Task 8 report：tools/polish_commit.py（保税仓唯一清关口）

状态：DONE。

## 文件

- `tools/polish_commit.py`（新增）——`commit(label, data_dir, dry_run=True,
  repo=None, ts=None) -> list[patch_row]`；CLI `--seg <label> --data-dir
  <dir> [--apply] [--repo <repo>]`。
- `tools/add_patch.py`（改动，4 行 + 注释）——`add()` 新增可选参数
  `prov=None`，向后兼容，见下方"prov 接口选择"。
- `tests/test_polish_commit.py`（新增，11 个用例，含 brief Step 1 给的
  4 类场景 + 自行补充的 idempotency/edit/glossary_v/CLI 场景）。

## 接口（与 brief 一致，另加 `repo=`/`ts=` 参数，同 Task 3–7 先例）

`commit(label, data_dir, dry_run=True, repo=None, ts=None) -> list`：返回
本次处理的 patch 行列表（`{"id","zh","reason":"polish","glossary_v","ts",
"prov"}`）。`dry_run=True` 时是"将会写入"的预览（不碰任何文件）；
`dry_run=False` 时是实际已写入 `patches.jsonl` 的行。`repo=`（测试用
tmp_path 替身仓库）与 `ts=`（测试注入固定时间戳，仅影响本次调用铸造的
`verdict="auto"` 新决策）都是本任务按既有惯例自行加的，不改变省略时的
默认行为。

## `prov` 接口选择：方案①——给 `add_patch.add()` 加 `prov=None` 可选参数

**没有选方案②（本模块自己用 `pipelib.append_jsonl` 写行）**，理由：

1. `add_patch.add()` 已经把"写前查 `existing_patches` + 有前科就播报到
   stderr + 追加写入"这三件事封装得很紧凑。如果本模块自己另起一套写入
   路径，就必须**重新实现**一遍查重播报逻辑——变成"两套写入路径，一套
   有查重一套没有"的分裂局面，这正是补充信息里明确警告要避免的。
2. 改动量小（4 行）且严格向后兼容：`prov=None`（默认）时 patch 行完全
   不带这个键，`tests/test_add_patch.py` 原有 4 个测试未作任何改动、
   全部保持通过（已重跑确认，见下方"测试输出"）。
3. `resolve.resolve_map()` 只读 `id`/`zh` 两个键（`tools/resolve.py:9-15`
   实测确认），`prov` 这个多余的键对它和其余既有下游消费者都是向后
   兼容的，不会引入任何回归。

代价：这是"改 Task 之外的既有文件"，但补充信息第 2 条明确把这条路列为
可选项之一（"那是它自己的模块，且改动小而向后兼容"），且改动只加了一个
默认值为 `None` 的可选关键字参数，是标准的、无风险的接口扩展方式。

## `glossary_v` 取哪个时点：清关时点（现行），不是冻结时点（manifest 快照）

`pilot/polish/<label>/manifest.json` 顶层的 `glossary_v` 是 `polish_
setup.setup()` **冻结那一刻**的快照（调用一次 `build_context.
glossary_version(repo)` 后就不再变）。润色是跨天的多阶段流程，glossary
是 append-only 的，版本号在冻结→裁决→清关这段时间里完全可能继续上涨。

**裁定：`commit()` 在执行的那一刻重新调用 `glossary_version(repo)`，取
仓库当前现行版本，不读 manifest 冻结快照。** 依据（有实测证据，不是纯
理论选择）：翻查真实生产 `pilot/lanes/opus/data/patches.jsonl` 尾部，
同一天之内 `reason=review`/`recall` 的 patch 的 `glossary_v` 从 13 跳到
14——**现有的唯一入库口 `add_patch.py` 的调用方本来就是这么用的**：每次
调用传"当前这一刻"的现行版本，不是某个更早的冻结快照。本模块作为同一
条生产链路上另一个入库口，理应延续同一约定，否则同一份 `patches.jsonl`
里会出现两种互相矛盾的 `glossary_v` 语义，下游无法区分。

`tests/test_polish_commit.py::test_glossary_v_uses_current_repo_not_
frozen_manifest` 构造了明确的对抗场景验证：SEG 冻结时仓库只有
`glossary.v1.yaml`（manifest 里的 `glossary_v` 记为 1），冻结完成后
**不重新 `setup()`**、只是往 `repo/glossary/` 追加一份 `glossary.v2.
yaml`，随后 `commit()` 产出的全部 patch 的 `glossary_v` 都是 2——证明
读的是"现行"而非"冻结快照"。

## 幂等键的粒度：`(id, decision_ts)`

`committed.json`（`pilot/polish/<label>/committed.json`）记录
`{"committed": [{"id":.., "decision_ts":..}, ...]}`。**不能只用 `id`**：
同一 id 可能先被 `triage()` 判定 `autoclear and not sampled` 自动清关
（铸造一条 `verdict="auto"` 决策，`ts`=本次调用时刻），之后人工发现有
问题、往 `decisions.jsonl` **追加**一条新的 `verdict="edit"` 记录（不同
的 `ts`，更晚）——这是两条不同的 decision，`commit()` 下次运行时会把它
当作一条独立的新 patch 落地，`patches.jsonl` 里这个 id 会有两条 patch
（先 auto 后 edit），`resolve.resolve_map()` 的"后写者胜"语义自然让
edit 版本生效，不需要任何特殊处理。反过来，同一条 decision（同一个
`ts`）被处理第二次（重复 `--apply`），`(id, decision_ts)` 已在
`committed.json` 里，直接跳过——这才是"幂等"真正要防的事。

**额外的自行裁定**（brief 未明确提及，但设计上必须处理）：避免同一个
"自动清关事实"在 `commit()` 每次重跑时被反复铸造成新的 `verdict="auto"`
决策（`ts` 每次都不同会让幂等键永远"看起来是新的"，导致重复 patch 堆
积）。铸造新决策前先查 `decisions.jsonl` 里是否已存在一条
`(id, chosen_channel, candidate_ts)` 三元组完全一致的 `auto` 记录——
一致就复用它的 `ts` 走幂等检查，不铸造新的；若 `candidate_ts` 变了
（该通道针对这个 id 重新提交过候选），才视为新的自动清关事实。用
`test_same_id_auto_then_human_override_both_land` 验证了"先 auto 后
人工改判都落地"这条链路的完整正确性（含 `resolve_map` 最终生效译文
确实是人工改判后的版本）。

## 多通道同一 id 都自动清关时选谁：取 `edit` 最小者（自行裁定）

`triage()` 的"id 级 all-or-nothing"规则允许同一 id 下多个通道的候选
同时满足 autoclear 资格（P4 常态，不是边缘情况）。brief 未规定此时该
写入哪个通道的 zh，本模块裁定：**取 `edit`（相对 opus 的编辑距离，
spec §9 认可的客观、可跨通道比较的信号）最小的那个通道**，同分按通道
名字典序打散作确定性兜底。理由：多个通道都被判定"安全可自动清关"时，
选离 opus 现行译文最近的那个是这批"安全"候选里风险最低的一个——万一
某通道的 autoclear 资格判定本身有系统性偏差，保守的那个造成的下游影响
也最小。（未单独为此写高强度测试，因当前实测语料里未触发多通道同 id
都自动清关的场景；已在模块 docstring 里记录该规则供未来复核。）

## dry-run 输出完整样例

```
$ uv run python -m tools.polish_commit --seg segX --data-dir /tmp/opus_data --repo /tmp/repo
```
stderr（倒查链）：
```
[dry-run] id=11 verdict=adopt 渠道=chA glossary_v=1 ts=2026-08-01T00:00:00+00:00
[dry-run]   倒查链：id 11 → 候选(chA, ts=2026-08-06T20:24:43.289599+00:00) → prompt_hash=hash-1
[dry-run]   zh：教室里弥漫着令人窒息的寂静,仿佛连时间都为之停滞了一般。
[dry-run] id=14 verdict=auto 渠道=chA glossary_v=1 ts=2026-08-06T20:24:43+00:00
[dry-run]   倒查链：id 14 → 候选(chA, ts=2026-08-06T20:24:43.289599+00:00) → prompt_hash=hash-1
[dry-run]   zh：由加里扶了扶眼镜。
```
若某 id 在润色期间已被别的会话写过 patch，额外会打印（dry-run 与 apply
两种模式下都会出现，见"写前查重播报"一节）：
```
[dry-run] ⚠ id 11 已有 1 条 patch（最近一条 reason=recall glossary_v=9 ts=...)
[dry-run]   现行译文：别的会话已经写过的旧译文
[dry-run]   ——本次清关将追加新的一条，不覆盖历史；若你以为这一行在润色期间没被别的会话动过，请先核对。
```
stdout（汇总）：
```
polish_commit[DRY-RUN]: segX 共 2 条 patch（未写入任何文件——加 --apply 才真写）
```

## 写前查重播报：dry-run 与 apply 两种模式都不缺席

`--apply` 路径直接复用 `add_patch.add()` 内部自带的 `existing_patches`
查重+播报（`announce=True`），不重复实现；dry-run 路径不调用 `add()`
（不能有任何副作用），故另用只读的 `add_patch.existing_patches()` 在
`_announce_prior()` 里打印同款告警（含现行译文前 60 字），保证两种模式
下这条播报都不会缺席——`test_new_patch_during_polish_triggers_announce`
同时覆盖了两种模式。

## 五个变异的红绿实况

方法与 Task 7 一致：用 Edit 在源码里精确引入一处改动、跑
`uv run pytest tests/test_polish_commit.py -q`、记录、再用 Edit 精确
还原（全程未使用 `git checkout`/`stash`/`restore`）。每次还原后单独跑
该测试文件确认恢复到 11 passed；全部完成后跑一次全量确认 667 passed。

**变异①（brief 给定）：dry_run 也落盘**（把 `if dry_run:` 改成
`if False:`，即无论 dry_run 与否都走写入分支）→ 3 条真红：
```
FAILED test_dry_run_no_write_but_two_rows
FAILED test_new_patch_during_polish_triggers_announce
FAILED test_cli_dry_run_default
3 failed, 8 passed in 0.10s
```

**变异②（brief 给定）：autoclear 且 sampled 的也清关**（触发条件从
`r.get("autoclear") and not r.get("sampled")` 改成只判 `r.get
("autoclear")`）→ 专门补的 `test_sampled_autoclear_not_committed` 真红：
```
FAILED test_sampled_autoclear_not_committed
1 failed, 10 passed in 0.09s
```

**变异③（brief 给定）：prov 丢 channel**（`prov` 字典构造去掉
`"channel"` 键）→ 2 条真红：
```
FAILED test_apply_writes_and_prov_correct
FAILED test_edit_verdict_uses_edited_zh_and_prov_channel
2 failed, 9 passed in 0.31s
```

**变异④（指令额外要求）：绕过 `resolve_data_dir` 直接用缺省 data 目录**
（`main()` 里把 `add_patch.resolve_data_dir(args.data_dir, repo=args.
repo)` 换成 `Path(args.data_dir) if args.data_dir else DATA`）→
`test_cli_lane_mode_without_data_dir_or_env_rejects` 真红（`DID NOT
RAISE SystemExit`）：
```
FAILED test_cli_lane_mode_without_data_dir_or_env_rejects
1 failed, 10 passed in 0.09s
```

**变异⑤（指令额外要求）：去掉 `existing_patches` 查重播报**（apply
分支绕开 `add_patch.add()`，直接 `append_jsonl(data_dir / "patches.
jsonl", [patch_row])`）→
`test_new_patch_during_polish_triggers_announce` 真红（apply 模式的
播报断言失败，dry-run 模式的播报不受影响，因为那条走的是独立的
`_announce_prior()`）：
```
FAILED test_new_patch_during_polish_triggers_announce
1 failed, 10 passed in 0.09s
```

五个变异全部按预期真红，均已用 Edit 精确还原（`grep MUTATION` 复核源码
干净）；每次还原后单独跑 `tests/test_polish_commit.py` 确认恢复到 11
passed，最终跑一次全量确认 667 passed（见下方"测试输出"）。

## 与 brief 的一切偏差

1. **`commit()` 签名加 `repo=`/`ts=`**：`repo=` 与 Task 3–7 同一先例
   （测试隔离要求）；`ts=` 是本任务为了让"铸造新 auto 决策"这一步在
   测试里可注入固定时间戳而加的（不影响省略时的默认行为——默认走
   `datetime.now(timezone.utc)`）。
2. **`add_patch.add()` 加 `prov=None`**：见上方专节，是补充信息给的
   两个可选路线之一，非计划外改动。
3. **decisions.jsonl 的 `verdict="auto"` 记录多带 3 个字段**
   （`zh`/`candidate_ts`/`prompt_hash`，brief 原文只给了
   `id`/`verdict`/`chosen_channel`/`edited_zh`/`reason_code`/`ts` 六个）
   ——为了让 `decisions.jsonl` 自身就能支撑倒查链审计，不需要再去交叉
   引用 `candidates.*.jsonl`；`edited_zh` 固定填 `None`。Task 9
   `polish_amplify.py` 按计划只读 `reason_code`，多出的键向后兼容。
4. **`committed.json` 不是 append-only**：CLAUDE.md/计划里点名
   append-only 的是 `patches.jsonl`/`candidates.*.jsonl`/
   `decisions.jsonl`/`forward.jsonl`，`committed.json` 未被列入，本模块
   把它当作一个可整体重写的幂等缓存（`_save_committed()` 每次落地成功
   后整体重写一次），这是合理的读—改—写模式，不违反 append-only 约束。

## 测试输出

```
$ uv run pytest tests/test_polish_commit.py -q
...........                                                              [100%]
11 passed in 0.11s

$ uv run pytest -q
667 passed in 3.39s      # 656（Task 7 完成后基线）+ 11（本任务新增）
```

## 生产数据安全核查

- 全程未写入真实 `pilot/lanes/opus/data/patches.jsonl`（`git status`
  未见该文件变动）。
- 真实仓库的 `pilot/polish/` 目录全程不存在（`ls pilot/polish` 报
  "No such file or directory"）——本任务全部测试均用 `repo=` 参数
  指向 `tmp_path` 造的替身仓库。
- 未使用 `git add -A`；未触碰 `.claude/settings.json` 与
  `data/api_ledger.jsonl`（这两个文件在工作树里已有其他会话的未提交
  改动，本任务原样保留，未 stage、未修改）。
- `.superpowers/sdd/2026-08-07-p4-polish-pass/progress.md` 在本任务
  开工前已有一份不属于本次会话写入的 Task 7 完成记录（内容与 Task 7
  报告逐字对应），本任务未触碰、未覆盖该文件。

## Concerns（供后续任务参考，非阻塞）

- Task 9（`polish_amplify.py`）若要新增读取 `decisions.jsonl` 里
  `verdict="auto"` 记录的逻辑，需要知道本模块额外带的 `zh`/
  `candidate_ts`/`prompt_hash` 三个字段——已在模块 docstring 里记录，
  但未同步到计划文本，供协调流程留意。
- 多通道同一 id 都自动清关时的 `edit` 最小值选择规则尚无专项测试覆盖
  （当前实测语料未触发该场景），已在模块 docstring 里写明规则与理由，
  建议后续若真实 SEG 出现该场景，评审时优先核实这条规则的实际表现。
