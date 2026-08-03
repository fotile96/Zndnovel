# P3 seg3-s4 生产台账

- 段：`seg3-s4`（`config/segments.yaml` seg=3），批号 **91–117**，共 27 批，**2579 条**（本段迄今最大）
- 章别：s4s / s4fa / s4fb / crd；`jp_chars` 合计 61226
- 剧情：第 4 章（**ユウイチ 视点开场**）
  `review_focus`：ユウイチ视点开场的人称与口吻；s4s_30_sel「私じゃない」回 s3s_340；
  s4s_100_sel→e1、s4s_490_sel→s8 门控；4A（消えたサクラ）/4B（サクラを待つ）双结局
- 车道：opus（`/Users/fotile96/Zndnovel/pilot/lanes/opus`），model=opus，effort=max，append_model_id=`claude-opus-5`
- **glossary 版本：v9**（append_forward 用 `--glossary-v 9`）
- 计划：`docs/superpowers/plans/translate-seg3-s4.md`（33 个任务，commit `6df4776`）
- 生产工具树：`/Users/fotile96/Zndnovel-prod` @ **`prod-run-v4`**
- cwd 恒为主仓 `/Users/fotile96/Zndnovel`

## 段开场自检（2026-08-03）

| # | 项 | 命令 | 结果 |
|---|---|---|---|
| 1 | 工具树版本 | `git -C /Users/fotile96/Zndnovel-prod describe --tags` | **`prod-run-v4`** ✅ 与 runbook §2 末「当前生产 tag」行一致 |
| 2 | 车道冻结 | `uv run python tools/lane_setup.py --lane opus --verify`（主仓） | `冻结校验：无漂移` ✅（已按 v9 再冻结） |
| 3 | 工作树清洁 | `git status --short` | 空输出 ✅ |
| 4 | 额度余量 | — | 见下「额度」节 |

**断点推导**（不信任记忆/进度文件）：读 `pilot/lanes/opus/data/forward.jsonl`（**8285** 条 unique id）
逐批对照 `data/batches.jsonl` 批 91–117 → **27 批全部 done=0**，起点 = **批次 91**。

### 计划生成核验（本段由生产会话执行 `gen_plan`）

```
uv run python tools/gen_plan.py --lane main --segment seg3-s4 --label seg3-s4 \
  --tools-root /Users/fotile96/Zndnovel-prod \
  --lane-dir /Users/fotile96/Zndnovel/pilot/lanes/opus \
  --model opus --effort max --append-model-id claude-opus-5
```
- 33 个任务（27 批 + 5 检查点 + 段末）✅
- **Run 行带生产树前缀 110 处；裸相对形态的四件套 0 处** ✅（`--tools-root` 未漏传）
- `--glossary-v 9` ✅（gen_plan 无该参数，版本自动取当前最高）
- 批号范围 91–117 ✅

### 上一段（seg2-s3）交接状态确认 —— 我方逐项复核

| 项 | 状态 |
|---|---|
| glossary | **v9 已出**（`glossary.v9.yaml`，commit `c45ae5d`） |
| 双车道再冻结 | ✅ `lane_setup --verify` 无漂移（commit `ed7709e`） |
| patches | **18 条**（v7×1 / v8×4 / **v9×13**）；**我段末交办的 8 条全部到位**：<br>11565 话题反转 ✅／12244 咻——嘭 ✅／12166 立人设 ✅／12128 胸口 ✅／12129 胸膛 ✅／10654 打气枪 ✅／10662 打气枪摊老板 ✅／11911 签字笔 ✅ |
| `speakers.json` | **49 → 51 条**：`射的屋の親父`→**打气枪摊老板** ✅（原「打靶摊老板」）、`（ヒント）`→**（提示）** ✅、`＊＊＊` **已登记** ✅；`出店の親父` 维持「小摊老板」（裁决未连带调整） |
| **工装升级** | **`prod-run-v3` → `prod-run-v4`**（commit `50faf6d`）：**C3 改为统计原文侧分母** + 审计发现的 4 条译文回改 |

**★本段最重要的工装变化**：SEG-2 段末 D 组提的「C3 应统计原文侧分母」**已实装于 `prod-run-v4`**。
SEG-2 的 30 条 C3 **全部**因原文侧同样重复而误报（沉默行「……」、分支共用段、行内三连重复），
**本段起这类噪声应大幅消失**。→ **观察点：若 C3 仍成片命中，需回看是否新形态；若命中数骤降，是预期。**

### 额度

2026-08-03（新一周起算）。SEG-1 约 8%、SEG-2 约 8%，均在上周。本段 27 批 2579 条，
体量约为 SEG-2 的 1.29 倍，预估 **≈10%**，远低于 ≤50%/周 的生产目标。
用户带着额度项把段派下来，据此判定余量充足、开跑全段。
（额度无程序化查询入口；若实际余量与此不符，随时叫停。）

## 逐批记录

| 批 | 章 | 条数 | ctx_sha | check | collapse (C1/C2/C3) | commit | 备注 |
|---|---|---|---|---|---|---|---|

## 本段开工即登记的注意点

1. **★人称与口吻的整段切换（review_focus 首项）**：s4s 是**ユウイチ 视点开场**——
   与前三章的アヤノ/直哉视点不同。`voices/yuichi.md` 是主依据；
   SEG-2 §33 已记 s3s 有「叙述人称整段倒向第一人称」的手法先例（8374/11890 段），**本段应属常态而非例外**。
2. **跨章门控句**（review_focus）：s4s_30_sel「私じゃない」→ 回 s3s_340；
   s4s_100_sel（需卡 142）→ **RUN e1**；s4s_490_sel（需卡 141）→ **RUN s8**。
   这些句子是玩家路线分叉的入口，**措辞须与目标章的既有译法对得上**。
3. **双结局 4A（消えたサクラ）/4B（サクラを待つ）**——两支的共用段落须逐字沿用，差异段不可反向拉齐
   （同 SEG-2 §29 的姊妹分支处理）。
4. **SEG-2 移交的前瞻清单**（台账 seg2-s3「G 组」）在本段可能落点：
   `バランスを崩す`→失去平衡、`キス`→接吻／`口づけ`→亲吻（**16162 是锚点勿反向拉齐**）、
   `夕焼け`→晚霞、`ドーナツ`→甜甜圈、`創作`→创作、`示唆`→暗示、`見せてみよう`→拿给她看看吧、
   `転落`→坠落、9 行脚本模板段（余 crd_167/176/193）、`≪关键词卡片≫`（余 15 处）、
   17022（３Ｂ）UI 串、`いつかは別れが` 省略/全称两形勿统一、
   **挖空型提示行 crd_103/104/177/167/110/176/193 改动前须能拼回卡名**。
   → **逐批入线后由我按落点复核，不注入派发词。**

## 异常与工装噪声留痕

（基线预期已变：C3 于 `prod-run-v4` 修复。W2 子串误报、C1 白名单、C2 与跨批一致性互斥
三条仍未修，照实记录，不改校验器、不放宽规则。）

## 段末

（待执行：按计划「段末流程」五步 → 机检复核 → 用户按 review_focus 抽读 → 彩野测试
（题库 `config/ayano_qa/seg3-s4.yaml` 现不存在，若段末仍无则 rc=2 跳过属预期，**不得拿别段顶替**）
→ `git tag prod-opus-seg3-s4-done` → 提醒开裁决会话）
