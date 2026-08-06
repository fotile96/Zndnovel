# P4 润色 pass 设计（spec）

日期：2026-08-07。状态：v1 已用户口头确认，实施中可修。
前置：P3 opus 翻译车道已完成正文 SEG-1..7；`glossary/style_refine.md`（六条汉语母语感细则）已入库；
题库↔译文失同步闸 `check_qa_quotes.py` 已上线。

## 1. 目标与非目标

**目标**：对 opus 车道的现行译文做一遍模型润色 pass，按「四桶客观分流」把改动落为
`reason="polish"` 的 patch；执行通道可以是 workflow 子代理（Claude fable）或经 paseo
派发的第三方 API（deepseek v4 flash 等，1M 上下文），且同一 SEG 允许多通道并行。

**非目标**：
- 不重跑对标 opus 车道的 fable 翻译 lane（已否决）。
- extra 段（b174–338）不在 P4 范围。
- 车道内实时润色 subagent 另行设计，不在本 spec。

**核心决策记录**（澄清阶段定案）：
1. score 语义＝四桶客观分流：自报分**只做同档排序**，绝无绝对阈值——跨模型不可比问题不存在。
2. 多通道关系＝分段分担为主，但**任一 SEG 保留多通道（≥2）齐跑的余地**；工作目录设计须让通道高度独立并行。
3. 人工请裁配额 K≈**100–150 句/SEG**（SEG 总额，多通道共享，含抽检占用）。
4. 改动句有**有条件自动入库通道**（小改+闸全绿+非冻结面），10% 随机抽检兜底，推翻率超线冻结该通道自动清关权。
5. 冻结面行**照常喂给模型**做上下文（锚点译法约束邻句），只是标记锁定、不得出稿——「不喂省 token」被用户否决。
6. 段末裁决具备**意图归纳+放大扫描**能力：从 K 句人裁归纳意图纪要，再发模型调用对整 SEG 二次扫描。

## 2. 命名统一：polish（§0）

- `glossary/style_refine.md` → **`glossary/polish.md`**（git mv，文内 §7 自述同步改）。
- ⚠ **连带必改**：opus 车道 `lane.json` 的 `freeze_exclude` 存的是旧路径。改名 commit 必须同时
  `lane_setup --set-exclude` 更新为新路径并跑 `--verify`，否则下次重冻结会把 `polish.md`
  带进 opus 车道，违反「opus 重冻结不带润色细则」的既有裁决。
- 数据层 `pilot/polish/<seg>/`；工具 `tools/polish_*.py`；patch `reason="polish"`（枚举已存在）。

## 3. SEG 冻结（§1，`tools/polish_setup.py`）

冻结单位是 **SEG 而非通道**——同 SEG 所有通道读同一份输入快照，候选才可比。

```
pilot/polish/<seg>/
  frozen/
    source.jsonl        该 SEG 日文原文（含 id）
    opus.jsonl          opus 现行译文固化＝resolve 在冻结时点的输出
    notes/              该 SEG 的 opus 生产 notes
    rulings.md          该 SEG 相关裁决台账摘录 ＋ 前序 SEG 的润色意图纪要（§6 前馈）
    glossary/           active.json + voices/ + style.md + polish.md + anchors.yaml
  manifest.json         逐文件哈希 + glossary_v + opus 固化时点（forward/patches 行数与内容哈希）
  raw/<channel>/<batch>.out      通道原始输出（§5）
  candidates.<channel>.jsonl     每通道各自的保税仓候选（§4）
  decisions.jsonl                裁决记录（§4）
```

- 冻结校验沿 `lane_setup` 三段式播报：无漂移＝唯一闸；落后于仓库＝播报不拦；有意排除＝播报。
- **opus 固化时点入 manifest** 是安全承重点：润色期间若有新裁决 patch 落库，过期候选由
  §4 回执核验机械失败，不靠人记。

## 4. 保税仓与单据链（§2）

原则：**产出与生效解耦**。候选永不直接碰 `patches.jsonl`；三个文件全部 append-only，
改判也是追加新记录，绝不就地改。

**候选**（`candidates.<channel>.jsonl`，每通道只写自己的文件——并行安全的全部依据）：

```json
{"id": 5683, "jp_hash": "…", "opus_hash": "…", "zh": "润色稿", "score": 87,
 "note": "句级批注(可空)", "flag_adjudicate": false, "channel": "fable-wf",
 "prompt_hash": "…", "ts": "…"}
```

- **回执核验**（机械闸第一道）：`id+jp_hash+opus_hash` 与 frozen/ 三对不上→整句判死。
  长上下文错位在写入前自爆。
- **裁决记录**（`decisions.jsonl`）：`{id, verdict: adopt|keep_opus|edit, chosen_channel,
  edited_zh, reason_code, ts}`。原因码枚举（可扩展）：量词/语序/补主语/过度归化/术语/口调/漂移/其他。
- **清关**（`tools/polish_commit.py`）＝写 `patches.jsonl` 的**唯一入口**：读 decisions（人裁）
  或自动清关判定，写 `reason="polish"` patch，附 `prov` 字段回指 `{channel, candidate_ts}`
  （resolve 只读已知键，向后兼容）。任何现行译文可 patch→candidate→prompt_hash/glossary_v 一路倒查。
  首次接通前先跑**清关 dry-run**：只打印将写入的 patch 与回指链，人工核对可倒查后再放行。

## 5. 四桶分流与自动清关（§3）

| 桶 | 判据 | 去向 |
|---|---|---|
| 0 冻结面 | anchors 锚点句族行、已有人裁 patch 的行 | 喂给模型做上下文，批内标 `【锁】`+任务说明列锁定 id 清单；**不得出稿**，锁定 id 的候选 ingest 时判死并记入通道纪律画像 |
| 1 零改动 | 归一后 `zh == opus` | 不产生 patch（维持现状零风险）；score 只记录供画像 |
| 2 请裁 | 有改动，按（改动幅度 × score × 显式 `flag_adjudicate`）排序取 SEG 总配额 K 内 | 段末人工裁决，多通道候选并排 |
| 3 配额外 | 有改动但没挤进 K | 保留 opus，记录在案（放大扫描可捞回） |

**自动清关道**（从桶 2/3 前截流）：非冻结面 + 机械闸全绿 + 改动幅度小 → 自动入库。
- 改动幅度初值：归一后字符级编辑距离 ≤ max(4, opus 行长的 15%)。实施期按首 SEG 实测调。
- **10% 随机抽检**混入裁决会话（占 K 额度）；单通道抽检推翻率 >20% → 冻结该通道本 SEG
  自动清关权，存量自动清关 patch 全部回滚复审（保税仓单据链使回滚可精确定位）。
- 已知残余风险（记录并接受）：「零改动＝安全」无法区分审慎与偷懒，opus 存量硬伤会原样放过。
  可接受：桶 1 语义是维持现状，现状已过 P3 全部闸与裁决；润色的失败模式是「没变好」而非「变坏」。

## 6. 双派发适配（§4）

关键原则：**模型输出是数据，写保税仓的是代码**。模型（任何通道）只产 raw 文件，入仓走确定性工具：

- `tools/polish_context.py`：拼接器。任务说明+锁定清单+frozen 全套+大批内 jp/opus/notes/rulings
  → 每大批一份 prompt。大批合并与长对话双帽（≤10 批/≤600 行）沿用 P3 方案。
- `tools/polish_ingest.py`：**唯一入仓工具**。解析 raw → 回执核验 → append candidates。
  按批幂等（已入仓的批重跑＝no-op）；覆盖不完整（截断）→ 整批判失败待重跑。
- workflow 通道（fable）：Workflow script 每会话一个子代理，schema 强制 JSON，落 raw 后 ingest。
- paseo 通道（deepseek 等）：`create_agent` 在独立 workspace/worktree 跑，同一 raw 契约；
  计费调用照旧入 `data/api_ledger.jsonl`；心跳＝最近 raw 落盘时间戳（防假死流）。
- 接第 N 个模型＝新增一个 `<channel>` 名，零结构改动。

## 7. 裁决意图归纳与放大扫描（§5）

1. 段末裁决每条 verdict 必贴原因码（见 §4 枚举）。
2. 裁决结束后 `tools/polish_amplify.py`：从 decisions.jsonl 自动起草**意图纪要**
   （原因码分布+每码代表例的改前/改后/裁决语），发一次模型调用：
   纪要 + 整 SEG 结果（jp+opus+候选+四桶去向，含桶 3 落选句）→ 补充问题句清单+改稿建议。
3. 放大产物以 `channel="amplify"` 回炉保税仓，**只进追加小裁决、永不自动清关**；
   每 SEG 限一轮（防循环）。
4. 纪要入库并**前馈**进下一 SEG 的 frozen/rulings.md；原因码分布积累后由开发轨蒸馏成
   `polish.md` 新版条目——六条细则长出数据支撑的回路。

## 8. 校准、机械闸、断点、题库联动（§6）

- **通道准入小考**：每通道每 SEG 先跑独立校准批（约 20 句＝10 句人裁定稿现行文本+10 句普通句，
  不带锁标，与生产批分离故无泄露）。金标句「实质改写」比例 >30% → 该通道本 SEG 自动清关权
  初始关闭（仍可产候选进桶 2/3）。已知偏差（金标是「曾出过问题」的非随机子集）记录在案，
  只做门槛不做精细校准。
- **机械闸**（`tools/polish_check.py`，复用 check_batch 组件）：回执核验、锁定面判死、
  控制码保全（`_n/_r`/ruby/【】/○/■/≪≫/≦≧）、W3 行宽、R2b 说话人、active.json 强制术语；
  清关后全 SEG 跑 W4（润色只改同 jp 兄弟句之一是真实风险）。
- **断点续跑**：批级。凭 raw/ 文件存在性 + ingest 幂等；截断批整批重跑，不做句级。
- **题库联动**：润色 patch 落库必然触发彩野题库失同步——每 SEG 清关后**强制跑
  `check_qa_quotes.py`** 并更新题库引文。
- **成本量级**：input ≈ 翻译 pass 的 2 倍上下（多带 opus 译文+notes+台账），
  输出远小于翻译 pass（多数句零改动只回 score）。

## 9. 测试与工装纪律

- 每个新工具带 pytest + 变异自检（3–6 个变异，绿变异必须区分「测试无牙」与「变异没打中」）。
- `polish_ingest` 幂等性、回执核验判死、锁定面判死各有专测。
- `polish_commit` 上线前清关 dry-run 人工核对倒查链。
- 所有阈值（改动幅度、抽检率 10%、推翻率 20%、准入 30%、K=150）集中放一处配置，
  首 SEG 实测后允许调整并记入台账；**任何阈值调整不得以「自动入库率」为优化目标**，
  只认抽检推翻率与裁决实感。

## 10. 开放事项

- 首个润色 SEG 选哪段起步（建议从剧情密度较低的段开始试运行）。
- 改动幅度阈值、K 的批内分配细则待首 SEG 实测回填。
- paseo 侧接入第二/第三中文模型的时点由用户决定。
