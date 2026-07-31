# P2 试点执行台账 · opus 车道（计划 docs/superpowers/plans/translate-pilot-opus.md，46 任务）

开跑：2026-07-31（云端会话，分支 claude/second-novel-p2-pilot-u7mf7n）

## 开场自检

- `bash .claude/cloud-setup.sh --mode session`：pytest 208 passed，build_ledger/build_dag --check OK，uv sync --locked OK。告警 3 项（两条车道未搭建 + 无 tag），均属纯克隆预期。
- 车道重建：opus（model=opus effort=max append=claude-opus-5）、fable（model=fable effort=high append=claude-fable-5）。
- `lane_setup.py --verify` → `冻结校验：无漂移`（exit 0）。

## 偏离记录（相对用户交办口径）

- **D1｜fable 车道提前搭建**：用户口径是「opus batch 1 跑完后再临时建 fable」。实际在开跑前就建好两条车道。理由：`verify()` 的跨车道一致性检查（CROSS_LANE_KEYS）**只在 ≥2 条健康车道时才运行**，只建一条时该检查静默跳过，而它正是 spec §0「术语泄漏」陷阱的唯一机器防线；且计划里每个 CHECKPOINT 的 Step 0 都期望 `冻结校验：无漂移`，单车道下会恒定报错、把真实漂移淹没在噪声里。仅建目录不改变任何译文语义，fable 的 batch 1 仍按计划在 opus batch 1 之后单独跑。
- **D2｜单车道试点**：本次只跑 opus 全 35 批；fable 仅跑 batch 1 用于 spec §3.3 隔离验收。故 spec §6 的双车道对照（区分度统计、盲评 rubric）本次**不产出**，试点报告须记为未完成项。

## 流水线缺陷清单（spec §8 产出物之一，随发现随记）

- **F2｜Workflow 的 `args` 以 JSON 字符串形态到达脚本，批号静默变 `undefined`**：batch 1 派发时 `args.batch` 取到 `undefined`，prompt 被模板成「批次编号 N = undefined」、路径变 `work/ctx/batch_undefined/`。子代理**没有报错**，而是自行 `ls` ctx/ 发现只有 `batch_1` 一个目录、读其 manifest 反推出批号与章别，最终产出正确（339 id 集合精确匹配、check PASS、notes 正确落 `s0f.md`）。**但这个自愈只在 ctx/ 下恰好只有一个批次目录时成立**——batch 2 起目录变多，猜测必然出错且无声。已修派发脚本：`args` 兼容字符串/对象两种形态，并加硬断言（批号/章别/条数任一缺失即抛错，宁可整个 workflow 失败也不派出坏 prompt）。同时修掉 prompt 里硬编码的「opus 车道」字样（改按车道根推导），否则派 fable 时会自称 opus。
- **F1｜`lane.json` 存绝对路径，跨环境必然抖动**：`lane_setup.setup()` 把 `lane_dir` 写成绝对路径（本地 `/home/fotile96/claude/2ndnovel-translation/...`，云端 `/home/user/Zndnovel/...`），而该文件入库。每次换环境重建车道都产生一条无意义 diff，且两环境来回翻。实测**无任何生产代码读取该字段**（`record()` 只用 lane.json 的存在性判定车道，其余全是测试引用），即纯文档字段。修法：改存仓库相对路径（`pilot/lanes/<lane>`）。记为 P3 输入，本次不修（试点期不动工装）。

## 逐批记录

| batch | chapter | ids | check | collapse (C1/C2/C3) | commit |
|---|---|---|---|---|---|
| 1 | s0f | 339 | PASS hard=0 warn=1 | 4 (0/0/4)，**全部误报** | 34e32db |

### batch 1 细节

- warn=1 是 6069 的 W3 行宽——该行是锚点行，zh 由骨架定稿锁死，无法在不违反锚点规则的前提下消除。属结构性冲突，记为 P3 输入（锚点行应豁免 W3）。
- collapse 4 条 C3 全为误报，人眼逐条过目：
  - 6242：原文本身就是 `ぱつ、_nぱつ、_nぱつ、_n`（拖鞋声拟声三连），译文「啪嗒、_n啪嗒、_n啪嗒、_n」忠实对应。
  - 6297/6332/6383：三条各自独立的 `【彩野】「……」` 沉默行，译文当然相同。C3 的批内重复规则（DUP_MIN_LEN=8 / DUP_MIN_COUNT=3）对这类短固定行必然误报——**这是 Task 4 阈值标定的第一份真实证据**。
- 锚点遵从：**total=16 verbatim=16 rate=1.000**（分母＝本批命中的锚点数，非全表 120）。
- 术语抽查：6231「手帳」→「笔记」与 `active.json` 定译一致；6080/6155/6311/6393 中文自然、`彩野同学` 称呼贯穿一致。
- 译者手记要点（原文见 workflow journal）：①`glossary/voices/naoya.md` 的例句与 `anchors.yaml` 对 6092 给出**不同**定译，译者从 anchors（正确）——15104/15178/1887 同类不一致（不在本批），**建议试点后校准 voices 文档**；②6351「扁桃体」是中日假朋友，已译「杏仁核」；③点名待复核 id：6060/6224/6244/6396/6130/6268。
