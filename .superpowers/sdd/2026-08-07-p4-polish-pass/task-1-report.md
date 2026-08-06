# Task 1 报告：命名统一 polish

状态：**DONE**
commit：`624af06`

## 做了什么

1. `git mv glossary/style_refine.md glossary/polish.md`
2. 编辑 `glossary/polish.md` 自述路径三处：
   - 标题 `# 汉语母语感细则（style_refine）` → `（polish）`
   - §7 「`style_refine.md` 不在其中」→「`polish.md` 不在其中」
   - §7.1 示例 `"freeze_exclude": ["glossary/style_refine.md"]` → `["glossary/polish.md"]`
3. 编辑 `docs/ops/p3-production-runbook.md:558`（唯一的**活引用**——描述译者可见面现状，非历史叙述）：
   `glossary/style_refine.md 是 2026-08-04 新增的…` → `glossary/polish.md 是…`
4. 编辑 `tools/lane_setup.py` 两处 docstring/CLI help 示例路径（`lane_exclusions()` 文档字符串、`--freeze-exclude` help 文本）：`glossary/style_refine.md` → `glossary/polish.md`。这两处不是历史叙述，是当前代码的用法示例，若不改会指向一个已不存在的文件名，误导后续读者。
5. 编辑 `tests/test_lane_setup.py`：20 处 `style_refine` 全部替换为 `polish`（含文件名字面量与断言字符串）。这些测试用临时仓库夹具，`style_refine.md` 只是通用 freeze_exclude 机制的示例文件名，功能上不依赖真实仓库文件，改动前后测试都能过；但既然本任务是"命名统一"，保留旧名字面量在代码里没有意义，一并统一。
6. 用 CLI（非手编）迁移 opus 车道排除集，并跑 `--verify` 校验。
7. 跑全量测试。
8. `git add` 显式列出的 5 个文件（不含 `.claude/settings.json` / `data/api_ledger.jsonl`，这两个是其他并行会话的未提交改动，按规约不碰）后提交。

## Step 1：引用清单全文

```
grep -rn "style_refine" --include="*.py" --include="*.md" --include="*.json" /Users/fotile96/Zndnovel --exclude-dir=.git
```

结果（提交前）：

| 文件 | 处理 |
|---|---|
| `glossary/style_refine.md`（自身，3 处内部自述） | rename + 内容改写 |
| `tools/lane_setup.py:69`（docstring 示例） | 改写（当前代码用法示例，非史料） |
| `tools/lane_setup.py:365`（`--freeze-exclude` help 文本示例） | 改写 |
| `tests/test_lane_setup.py`（20 处，6 个测试函数的夹具/断言） | 改写（合成夹具，非真实文件引用，但统一命名） |
| `docs/ops/p3-seg7-handoff.md:26` | **保留**——历史叙述（该段生产当时 `--verify` 的实际输出记录） |
| `docs/ops/p3-seg5-s6-s7f-adjudication-handoff.md:57,188` | **保留**——同上 |
| `docs/ops/p3-seg5-handoff.md:30,123` | **保留**——同上 |
| `docs/ops/p3-seg6-s8-e1-adjudication-handoff.md:59,199` | **保留**——同上 |
| `docs/ops/p3-seg6-handoff.md:30` | **保留**——同上 |
| `docs/ops/p3-seg7-e2-adjudication-handoff.md:77,210` | **保留**——同上 |
| `docs/ops/p3-production-runbook.md:558` | **改写**——描述"译者可见面现状"的活引用，brief 明确点名 |
| `docs/superpowers/plans/2026-08-07-p4-polish-pass.md`（本任务的计划文档自身） | **保留**——描述本次重命名任务本身，属于计划史料 |
| `docs/superpowers/specs/2026-08-07-p4-polish-pass-design.md` | **保留**——设计规格文档，描述"重命名前"状态与本次改动计划，属于规格史料 |
| `pilot/lanes/opus/lane.json` | 改写（经 CLI，非手编） |

额外核实：无 `--include` 限制的全仓库 `grep -rln "style_refine"`（排除 .git）额外发现 `pilot/lanes/fable/glossary/style_refine.md`——这是 fable 车道的**冻结拷贝构建产物**，`git check-ignore` 确认被 `.gitignore:24` (`pilot/lanes/*/glossary/`) 忽略、`git ls-files` 确认未跟踪，不在版本控制范围内，不处理（见下文"遗留观察"）。

判断依据（对应用户补充信息第 4 点）：`docs/ops/*handoff*.md` 六处均是**叙述过去某段生产 `--verify` 实际输出/用户裁决**的既成记录（"用户 2026-08-04 决定"、当时的排除播报原文），改写会篡改史料；`plans/` 与 `specs/` 下的两份文档本身就是**本任务的上游计划/规格**，其中的 `style_refine.md` 字样是在描述"改名前"的既有状态和"要把它改成什么"，同样是叙述性史料，不属于"当前有效的路径引用"。这些文档里没有发现"既是史料又是活引用"需要括注新名的情况——所有提及都是纯粹的过去时态描述。

## lane_setup.py CLI 实际形态

`--help` 输出与 brief 假设不同：`--freeze-exclude` 与 `--set-exclude` 是**两个独立参数**，不是 brief 示例里的组合形态。`--set-exclude` **本身就是逗号分隔的路径值**（不再需要额外的 `--freeze-exclude` 参数配合），需同时给 `--lane`：

```bash
uv run python tools/lane_setup.py --lane opus --set-exclude glossary/polish.md
```

（brief Step 3 写的 `--set-exclude opus --freeze-exclude glossary/polish.md` 与实际 CLI 不符，已按 `--help` 与 `main()` 源码——`ap.add_argument("--set-exclude", ...)` 的分支在 `a.set_exclude is not None` 时直接 `a.set_exclude.split(",")` 取路径列表——按实际形态执行。）

## verify 输出

```
$ uv run python tools/lane_setup.py --lane opus --set-exclude glossary/polish.md
opus: freeze_exclude = ['glossary/polish.md']

$ uv run python tools/lane_setup.py --verify
冻结校验：无漂移
⚠ 车道冻结拷贝落后于仓库侧 2 处（**不是漂移**，段中途正常；但译者读的是车道拷贝，这些改动对生产端尚未生效，段边界须 --force 重冻结）：
  fable: glossary/style_refine.md 仓库侧已不存在（车道仍冻结着）
  fable: glossary/polish.md 仓库侧新增，未进车道
ℹ 有意排除 1 项（不是缺陷，但每次出声——排除是静默丢文件的机制，藏起来才危险）：
  opus: glossary/polish.md 按 lane.json:freeze_exclude 有意排除，该车道看不到它
```

`pilot/lanes/opus/lane.json` 最终内容：
```json
{"lane":"opus","lane_dir":"/Users/fotile96/Zndnovel/pilot/lanes/opus","model":"opus","effort":"max","append_model_id":"claude-opus-5","freeze_exclude":["glossary/polish.md"]}
```

Gate 达成：「冻结校验：无漂移」✅；「ℹ 有意排除」列表含 `glossary/polish.md`、不含旧名 ✅。

## 测试结果

`uv run pytest -q` → **567 passed**（与基线一致，无回归；`tests/test_lane_setup.py` 的夹具改名后仍全绿）。

## 遇到的问题与判断

1. **brief 里的 CLI 命令形态与实际不符**（见上）——已按用户补充信息第 2 点要求，先 `--help` 核对，再按 `main()` 源码确认 `--set-exclude` 的值就是路径列表本身，按实际形态执行，未照抄 brief 原文。
2. **brief Step 5 的文件名 `pilot/lanes/lanes-manifest.json` 确认不存在**，实际文件是 `pilot/lanes/pilot-manifest.json`——但本次改动实际未涉及该 manifest（`--set-exclude` 走的是只改 `lane.json` 的分支，不触发 `record()`/`freeze_hashes` 重算，`pilot-manifest.json` 未被 touch，`git status` 也未显示该文件有改动），所以最终 commit 里没有它，无需处理这一条差异。
3. **`fable` 车道因本次 rename 出现新的 `stale_vs_repo` 播报**（"落后于仓库侧 2 处"：旧文件仓库侧已删、新文件仓库侧新增未进车道）。这是 `--verify` 设计上明确"不算漂移、退出码仍 0"的正常提示（`test_main_verify_prints_stale_block_but_still_exits_zero` 同款语义），不是本任务范围内的缺陷——`fable/lane.json` 本身没有 `freeze_exclude`，下次该车道段边界 `--force` 重冻结时会自然拿到 `glossary/polish.md`（这正是设计意图：润色轨要看得见这份细则，只有 opus 排除）。未做任何处理，留给该车道自己的下次重冻结周期。
4. **`pilot/lanes/fable/glossary/style_refine.md`（旧文件的车道内冻结拷贝）** 经 `git check-ignore -v` 确认命中 `.gitignore:24`（`pilot/lanes/*/glossary/`）、`git ls-files` 确认未跟踪——不在版本控制范围，未处理，等同上一条，靠 fable 车道下次重冻结自然更新。
5. **测试夹具改名的必要性判断**：`tests/test_lane_setup.py` 里的 `style_refine.md` 字样严格说不是"引用"（测试用临时仓库自建同名文件，与真实 `glossary/` 无关，改不改都不影响测试通过与否），但鉴于任务名是"命名统一"且这些字面量与本次改名的对象完全同名，容易让未来读者误以为测试在校验真实文件路径，故一并改为 `polish.md` 以保持仓库内除历史文档外无残留旧名。
6. 未发现任何"既是史料又是活引用"、需要"保留原文并括注新名"的情况——六份 handoff 与 plan/spec 里的提法均为纯历史叙述。
7. 工作树里 `.claude/settings.json` 与 `data/api_ledger.jsonl` 的未提交改动（其他并行会话产生）全程未碰、未 add、未提交，`git status` 复核确认提交后仍保持原状（modified，未纳入本次 commit）。
