# P3 点火 — 终审修正波 最终报告

日期：2026-08-02　分支：main　基线：`9725864`（终审对象 `226e87f..9725864`）
结果：**全部 finding 已处置**，`uv run pytest -q` → **234 passed**（修前 221）。
生产 tag 已滚至 `prod-run-v2`（= HEAD `0aaee66`），生产 worktree 已切过去。

## 0. commit 清单

| commit | 内容 |
|---|---|
| `7fb7598` | fix: 生产/开发并行的命令形态划分 + saturation 失败开 + 段模式措辞（C1/I2/I3/M6，工具+测试） |
| `0e949b3` | fix: 检查段切分表拆出 ambient 段并补齐 chapters（I4/M5，配置+测试） |
| `bac9f3f` | docs: runbook 树/cwd 划分与 canary 覆盖边界；P2 报告崩溃命中数订正为 45（C1/I1/I5/I6/M7） |
| `c786945` | fix: 段模式崩溃探测步不再引用不存在的硬停任务（M6 补漏，重生成时发现） |
| `266829b` | docs: SEG-1 生产计划重生成（生成物） |
| `0aaee66` | docs: canary 免跑判定留痕补全 saturation |

只 `git add` 显式路径，未使用 `git add -A`/`.`；`.superpowers/sdd/` 下的工作文件未改动、未提交（本报告除外，见文末）。

---

## 1. C1（Critical）生产/开发并行机制自相矛盾

### 1.1 先做的核实：四件套在「主仓 cwd + 生产树绝对路径 + 数据参数指向主仓车道」姿势下能否工作

**结论：四件套全部可用，且钉死语义真实成立。** 逐条实测（在 `/private/tmp/.../scratchpad/lane-probe`——`cp -a` 出来的车道副本上跑，避免污染生产车道；副本内 `data/*.jsonl` 仍是指向主仓 `data/` 的符号链接）：

```
$ cd /Users/fotile96/Zndnovel
$ uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py \
    --batch 35 --profile cc --baseline none --repo <lane-probe>
EXIT=0     → 产出 context.md / source.jsonl / manifest.json（落在 <lane-probe>/work/ctx/batch_35/）

$ ZND_WORK=<lane-probe>/work ZND_DATA=<lane-probe>/data \
  uv run python /Users/fotile96/Zndnovel-prod/tools/check_batch.py --batch 35 --lane-dir <lane-probe>
batch_35: PASS  warn=1        EXIT=0

$ ZND_WORK=… ZND_DATA=… uv run python /Users/fotile96/Zndnovel-prod/tools/detect_collapse.py \
    --batch 35 --lane-dir <lane-probe>
batch_35: 崩溃探测 0 条 (C1=0 C2=0 C3=0)   EXIT=0

$ ZND_WORK=… ZND_DATA=… uv run python /Users/fotile96/Zndnovel-prod/tools/append_forward.py \
    --batch 35 --backend cc --model claude-opus-5 --ctx deadbeef --glossary-v 7
batch_35: 已在正向线，拒绝重复入库   EXIT=4     （forward.jsonl 行数 4282 → 4282，未写入）
```

（batch 35 的 draft 由 forward.jsonl 反构，与 canary 的 `_draft_from_forward` 同法。）

**模块解析核实**——被调脚本自己做 `sys.path.insert(0, __file__/../..)`，Python 又把脚本目录置于 `sys.path[0]`，故加载的是生产树自己的 `tools/`：

```
pipelib from: /Users/fotile96/Zndnovel-prod/tools/pipelib.py
```

即「用绝对路径调生产树脚本」不会被主仓 `tools/` 影子覆盖，**段内冻结是真的**。

**逐工具的路径来源审查（是否有 `__file__` 推路径的硬伤）：**

| 工具 | 数据/骨架路径来源 | 从主仓 cwd 调生产树版本是否安全 |
|---|---|---|
| `build_context` | `--repo`（省略才回落 `pipelib.REPO`）；产物落 `<repo>/work` | ✅ 安全，参数全覆盖 |
| `check_batch` | `pipelib.WORK`（=`ZND_WORK`）+ `--lane-dir` 取 glossary | ✅ 安全（`REPO` 仅在不给 `--lane-dir` 时才用） |
| `detect_collapse` | `--lane-dir` 同时给出 work 与 glossary | ✅ 安全 |
| `append_forward` | `pipelib.WORK`/`DATA`（=`ZND_WORK`/`ZND_DATA`） | ✅ 安全 |
| `lane_setup` | **模块级 `LANES_ROOT = REPO/pilot/lanes`，由 `__file__` 推出，无 CLI 覆盖** | ❌ **有硬伤** → 规则里固定走主仓 |
| `canary` | `--lane-dir`；`_ensure_ctx` 用 `Path(__file__).parent/build_context.py`（同树，是想要的语义） | 只在 dev/升级流程用，本轮不改 |
| `resolve` | 只认 `ZND_DATA`，无 `--data-dir` | 段末裁决用，固定走主仓 + `ZND_DATA`（见 M7） |
| `saturation` | `--data-dir`（默认 `pipelib.DATA`） | 段末裁决用，固定走主仓 |
| `gen_plan` | `REPO`/`DATA` 由 `__file__` 推出 | 计划生成器，固定走主仓 |

**两处硬失败已实证复现：**

```
$ cd /Users/fotile96/Zndnovel-prod && uv run python tools/lane_setup.py --lane opus --verify
fable: 冻结文件缺失或车道损坏（… '/Users/fotile96/Zndnovel-prod/pilot/lanes/fable/skeleton/cards.zh.yaml'）
opus:  冻结文件缺失或车道损坏（… '/Users/fotile96/Zndnovel-prod/pilot/lanes/opus/skeleton/cards.zh.yaml'）
EXIT=1

$ cd /Users/fotile96/Zndnovel-prod && git add /Users/fotile96/Zndnovel/pilot/lanes/opus/data/forward.jsonl
fatal: … is outside repository at '/Users/fotile96/Zndnovel-prod'      EXIT=128
$ git -C /Users/fotile96/Zndnovel-prod rev-parse --abbrev-ref HEAD  →  HEAD（detached）
```

### 1.2 修法（已落地）

**规则（三处一致表述：runbook §1.1 表格、`_segment_head` 第 1 项、计划 Global Constraints 首条）：**

- **cwd 恒为主仓 `/Users/fotile96/Zndnovel`，任何时候不 `cd` 到生产 worktree。**
- 只有**按批四件套** `build_context` / `check_batch` / `detect_collapse` / `append_forward` 用生产树绝对路径。
- `lane_setup` / `gen_plan` / `saturation` / `resolve` **与全部 git 操作**固定用主仓 `tools/`。

**代码：** `tools/gen_plan.py` 新增 `--tools-root`（默认空）与 `_tools_prefix()`；`_paths()` 多一个 `"tools"` 键，仅四件套的 Run 行消费它。空值 → 裸 `tools`，非段模式输出一字不变（见 §9 自证）。

**生成物核实**（`docs/superpowers/plans/translate-seg1-s2.md`）：

```
prod-prefixed build_context: 27   bare: 0
prod-prefixed check_batch:   27   bare: 0
prod-prefixed detect_collapse:27  bare: 0
prod-prefixed append_forward:27   bare: 0
bare  lane_setup: 6              prod lane_setup: 0
```

计划里的 `git add`/`git commit` 用主仓绝对路径 + 主仓 cwd，与 §1.1 规则一致。

**端到端冒烟**——把计划 Task 1 Step 1 的 Run 行**逐字**执行（对真实生产车道）：

```
$ uv run python /Users/fotile96/Zndnovel-prod/tools/build_context.py --batch 36 --profile cc \
    --baseline none --repo /Users/fotile96/Zndnovel/pilot/lanes/opus
EXIT=0 → context.md / manifest.json / source.jsonl
```

（冒烟产物随后删除，未留下 `pilot/lanes/opus/work/ctx/batch_36/`；`build_context` 确定性，生产时重生即得。）

---

## 2. I1 生产 tag 仍钉在含已修缺陷的版本上

- 本轮全部代码/文档修正提交完成后打 `prod-run-v2` → **`0aaee66`**（HEAD），并 `git -C /Users/fotile96/Zndnovel-prod checkout --detach prod-run-v2`；`git -C … describe --tags` → `prod-run-v2`，工作树干净、`tools/build_context.py` 与 tag 内容一致。
- runbook「当前生产 tag」行已改为 `prod-run-v2`（§1 提到的示例 tag 一并改）。
- runbook 新增 **§4.1 canary 的覆盖边界**：canary 只重算 `check_batch.check` + `detect_collapse.scan`（`--regen-ctx` 时另含 `build_context`）；`gen_plan`/`append_forward`/`lane_setup`/`resolve`/`build_ledger` 与 `prompts/` 的升级**不在覆盖面内**，需人工判定并在 git log/台账留痕。
- **本次判定留痕**：`git diff prod-run-v1 prod-run-v2 -- tools/ prompts/` = `gen_plan.py` + `saturation.py` 两个文件（`prompts/` 零改动）。gen_plan 是计划生成器；saturation 只**新增**两行说明性输出、饱和度算法一字未动。两者都不在 canary 的三个被重算工具内，对已入线批次判定与产出恒等 → **免跑 canary**。
  - 注：终审原文记「diff 只有 gen_plan.py 一个文件」，那是本轮修 I2 之前的实况；`0aaee66` 已把 saturation 一并写进留痕。

---

## 3. I2 saturation 漏传 `--data-dir` 时静默「失败开」

`tools/saturation.py:main()` 现在在表头**之前**打印统计口径，`forward.jsonl` 缺失时另打醒目告警。真实对照（同一份词表、同一台机器）：

```
$ uv run python tools/saturation.py --terms-file terms.txt --data-dir pilot/lanes/opus/data --gate 0.8
done=4282 条已入线译文（data-dir=pilot/lanes/opus/data）
| 词 | 出现 | 已覆盖 | 饱和度 | 判定 | … |
| あらすじ | 394 | 61 | 0.155 | 滚存 | … |
| 手帳     |  69 | 51 | 0.739 | 滚存 | … |

$ uv run python tools/saturation.py --terms-file terms.txt --gate 0.8        # 漏传 --data-dir
done=0 条已入线译文（data-dir=/Users/fotile96/Zndnovel/data）
!! 告警：/Users/fotile96/Zndnovel/data/forward.jsonl 不存在——本次按「零条已译」计算，
   全部词族必然判为「滚存」，闸门等于失效。是否漏传 --data-dir？（车道数据在 pilot/lanes/<lane>/data）
| 手帳     | 69  | 0 | 0.000 | 滚存 | … |
| あらすじ | 394 | 0 | 0.000 | 滚存 | … |
```

修前第二条命令的输出与第一条**在结构上无法区分**（就是一张全 0.000/滚存 的合理表）。

测试：`tests/test_saturation.py::test_main_warns_loudly_when_forward_missing`（锁「告警」+ 文件名 + `done=0`）；既有 `test_main_reads_data_dir_and_gates` 追加锁 `done=2 条已入线译文` 与 data-dir 回显。
runbook §5.2 与计划段末流程第 4 条也各加了一句「`--data-dir` 是最容易漏抄的一节 / N=0 即漏传」。

---

## 4. I3 `segments.yaml` 与 `--segment` 无程序耦合

`tools/gen_plan.py` 新增 `segment_range(label, repo)`：从 `config/segments.yaml` 按 label 取 `batches` 闭区间；label 不存在 → `SystemExit` 并列出全部已有 label。`--batches` 降为可选覆盖，`--label` 缺省取 segment 名，`--segment` 与 `--chapter` 互斥。CLI 分支改为「segment → batches → chapter → 报错」，三者都不给时给出可读错误（原来是 argparse 的 `required=True` 组）。

测试 4 条：`test_main_segment_derives_batches_from_segments_yaml`、`..._unknown_label_exits`、`..._batches_override_wins`、`test_main_requires_one_of_chapter_batches_segment`。

---

## 5. I4 SEG-8 跨 lane 会静默漏批

**数据实况**：b174–338 全部 `lane=extra`（jp_chars 合计 9019），**b339 是 `lane=ambient`**（jp_chars 1363，chapter=`sys`，`seqs` 为空，全书唯一一批 ambient）。`gen_plan.select()` 只按单一 lane 过滤 → `--lane extra --batches 174-339` 得 165 批、静默漏 b339。

**选择：拆段**（新 `seg9-ambient`），而非并入前一段。理由：
1. 段是「一次生产计划」的单位，而计划生成必须指定唯一 `--lane`；只要段内 lane 不唯一，无论怎么拼都会漏批。
2. b339 在语料性质上也自成一类（ambient 轨 = 环境/氛围与系统串，无 timeline 位置，前缀窗口退化为「只有骨架卡组」），抽读焦点与 extra 的 UI/tr_line 串不同。
3. 并入 seg7（main 轨 e2）会把 lane 冲突原样搬过去。

`config/segments.yaml` 现为 9 段：`seg8-extra` = b174–338 / jp 9019，`seg9-ambient` = b339 / jp 1363 / chapters `[sys]`。分区仍恰好覆盖 b36–339 各一次（原 3 条测试全绿）。
新增测试 `test_each_segment_covers_exactly_one_lane`。

---

## 6. I5 `prompts/` 不在钉死面内

runbook §1 第 1 条改为「**钉死面 = `tools/` + `prompts/`**」，并写明理由（计划正文 27 处派发指令引用 `prompts/translator_cc.md`，解析到 main 实时版本；canary 完全测不到），要改走与工具升级同一个段边界流程。§4.1 的「不在 canary 覆盖面内」清单也含 `prompts/`。

---

## 7. I6 P2 报告的数字错误

`docs/superpowers/reports/2026-08-01-p2-pilot-report.md` `:131` 与 `:229` 的「44 条」→「45 条」，并加脚注 `[^collapse45]`：

- 来源一：`.superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md` 逐批台账求和 4+3+1+17+6+6+4+4 = 45（脚本重算逐批表得 28，再加表外单列的 batch 19 的 17 条 = 45，与手算一致）。
- 来源二：P3 Task 3 canary 对 b1–35 重算 `collapse=45 / warn=30`。
- 脚注同时写明：该基线随车道 glossary 版本变化（C1 规则要读车道 `glossary.vN.yaml` 的「原样保留」角色名，v6→v7 再冻结后同批命中数可能不同），**canary 必须成对、同时刻、同一份车道数据跑，不可拿这个历史数字当基准**。

---

## 8. M5 `chapters` 字段全段漏 crd / M6 段模式仍输出试点措辞

### M5

实算补齐（seg1–7 每段都含 `crd`；seg8 原为空列表，extra 轨的「章别」就是源 lua 脚本名，165 个，如实列出；新 seg9 为 `[sys]`）。文件头加注说明 chapters 的语义与 extra 轨的形态。
新增测试 `test_segments_chapters_match_actual_chapters`（集合相等 + 无重复），故此后再改段表必须同步 chapters。

### M6

段模式（`segment` 非 None）改用段语汇，逐处：

| 位置 | 非段模式（不变） | 段模式 |
|---|---|---|
| `_header` Architecture | 「章末插一个人工评审 gate」 | 「段末插一个人工评审 gate」 |
| `_header` Global Constraints | 「`--baseline` 试点期固定 `none`」 | 「`--baseline` 本段固定 `none`」 |
| `_header` 首条约束 | 「运行 `uv run python tools/<x>.py`」 | 换成 C1 的树/cwd 划分表述 |
| `_lane_block` | 「试点期间提案只追加进…」 | 「本段进行中提案只追加进…」 |
| `_checkpoint_task` Step 0 | 「**立即停止试点**，报告人工裁决」 | 「**立即停止本段**，报告人工裁决」（并加「（在主仓执行）」） |
| `_checkpoint_task` Step 1 | 「…裁决推迟到试点结束」 | 「…裁决集中到本计划末尾『段末流程』指向的段末小裁决会话」 |
| `_final_task` 标题 | 「章末——梗概回译自检 + 人工评审 gate」 | 「段末——…」 |
| `_batch_task` Step 4 尾句 | 「供后面的检查点/**硬停任务**汇总参考」 | 「供后面的检查点/**段末流程**汇总参考」 |

最后一条是**重生成后复核时才发现的悬空引用**（段模式不生成硬停任务，却仍指向它，27 处），单独修在 `c786945`。

段计划实测：`试点` 0 次、`章末` 0 次、`硬停` 0 次、`窗口对撞` 0 次。
测试：`test_segment_mode_drops_pilot_vocabulary`（禁用词表 + 正向断言）与回归闸 `test_pilot_mode_keeps_pilot_vocabulary`。

---

## 9. 非段模式「一字不变」的自证

方法：**取出改动前版本的 `render()`，对同一组不传 `segment` 的输入跑出全部输出，序列化后与改动后逐字节比对。**

用例矩阵 16 条（`scratchpad/golden/gen.py`），覆盖：`--chapter` 模式 / `--batches` 连续段模式 / 车道模式（相对 lane_dir 与绝对 lane_dir 两种）/ 非车道模式 / 空 `sel` / 跨章别 mixed / `glossary_v` 变体 / 阈值全给与部分给 / 默认 `every` / **以及真实 `data/batches.jsonl` 的 b1–35（P2 试点计划原型）、b36–62、extra 轨 b174–338**。

```
改动前： cases: 16 sha256: 9a8278cc3f5c8555882b4dc22f481cf1747152489ad64500c481cbb50d71fd37
改动后： cases: 16 sha256: 9a8278cc3f5c8555882b4dc22f481cf1747152489ad64500c481cbb50d71fd37
$ cmp before.json after.json  → IDENTICAL
```

M6 补丁（`c786945`）之后再跑一次：仍 `IDENTICAL`。
另有既有回归闸继续把守：`test_no_lane_cfg_keeps_repo_relative_paths`、`test_non_lane_mode_gate_markers_are_completely_absent`（含任务总数 10）、`test_full_pilot_task_count_in_lane_mode`（46）、`test_pilot_mode_lane_cfg_without_segment_still_has_hardstop_tasks`、新增 `test_tools_root_default_is_bare_tools_path`。

---

## 10. 重新生成后的逐项复核

生成命令（主仓执行，已写入 runbook §3 与 commit message）：

```
uv run python tools/gen_plan.py --lane main --segment seg1-s2 \
  --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus --model opus --effort max \
  --append-model-id claude-opus-5 --tools-root /Users/fotile96/Zndnovel-prod
→ docs/superpowers/plans/translate-seg1-s2.md: 33 个任务
```

| 项 | 结果 |
|---|---|
| 批次区间 b36–62 共 27 批、连续 | PASS |
| glossary_v=7（全文唯一取值） | PASS |
| 段开场自检在正文任务之前 | PASS |
| 段末流程在最尾（在最后一个 `### Task` 之后、文件结尾） | PASS |
| tag 名 `prod-opus-seg1-s2-done` | PASS |
| 车道配置表 model=opus / effort=max / append_model_id=claude-opus-5 / lane_dir 绝对路径 | PASS |
| 隔离纪律块在（且全文无对方车道 `fable` 字样） | PASS |
| 无试点硬停任务（`硬停`/`试点`/`窗口对撞` 全 0） | PASS |
| 任务编号连续 1..33 | PASS |
| 四件套 Run 行 27×4 全带生产树前缀、零主仓相对残留 | PASS |
| `lane_setup`（6 处）/`saturation`/git 全为主仓形态 | PASS |
| 重复生成幂等（再跑一次无 diff） | PASS |

---

## 11. 明确未做（按指令）

M1（canary 不读 manifest 阈值）、M2 的代码改动（只在 runbook §4 加了 `--regen-ctx` 覆写 `work/ctx` 的提醒）、M3（diff 摘要计数相同时的措辞）、M4（extra 轨 chapter 落 `?`）、Task 2/3/4 台账里的四条文档笔误。

`lua_scripts/`、`png/`、`analysis/`、`data/` 未触碰；`pilot/lanes/*/data/forward.jsonl` 未编辑（append_forward 探针命中 append-only 保护、行数不变）。

---

## 12. 遗留顾虑（不阻断，供下一轮考虑）

1. **`--lane` 与 `--segment` 仍无交叉校验**：段内 lane 现已由测试保证唯一，但 `gen_plan --lane extra --segment seg1-s2` 仍会产出「无事可做」的空计划（不是静默错，但也没报错）。可在 `segment_range` 顺带返回段的 lane 并校验——本轮未做，属新增行为、超出指令范围。
2. **`seg8-extra` 的 `chapters` 有 165 项**，YAML 体量显著变大；它对「用户抽读范围认知」的帮助有限（都是源脚本名）。若将来觉得碍事，可改为在测试里比对而在文件里存一个折叠形态——但那会引入第二真相源，本轮选择了如实列出。
3. **`resolve.py` 仍只认 `ZND_DATA`**（无 `--data-dir`），与四件套的参数风格不一致；本轮按指令只在 runbook 写全命令，未改代码。
4. **`canary._ensure_ctx` 用 `Path(__file__).parent/build_context.py`**：在「旧树跑一次、新树跑一次」的升级流程里这是想要的语义，但它同时意味着 canary 在旧树上跑时**必须以旧树 cwd 或至少旧树脚本路径调用**——与本轮确立的「cwd 恒为主仓」规则是两套姿势。canary 只在 dev 段边界流程用、不在生产会话用，runbook §4 的命令原本就写了 `cd /Users/fotile96/Zndnovel-prod`，本轮未动它；若将来把 §4 也统一到「不 cd」，需要一并处理。
5. **本报告文件本身**（`.superpowers/sdd/2026-08-02-p3-ignition/final-fix-report.md`）位于插件自忽略目录，按 CLAUDE.md 规约属「入库携带」的执行状态证据，需 `git add -f` 一次。本轮未替调用方决定是否提交。
