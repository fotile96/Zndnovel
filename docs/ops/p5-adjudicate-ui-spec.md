# P5 逐条裁决 Web UI —— 开发规格（demo）

> 2026-08-19。用户口述需求 + 四点拍板。开发者：独立 subagent。
> 本文是唯一需求源；有歧义处按「设计原则」自行判断并在报告里写明。

## 0. 一句话

给 P5 润色的人工裁决阶段做一个本地 Web 小工具：左边栏选条目，右边等分两栏对照
**日文原文**与**最新落盘译文**（各带前文上下文），在合适位置展示各通道的提案与批注，
人做出选择或手工编辑后自动跳到队列下一条。

## 1. 已拍板的四条（不要改动这些决定）

1. **写草稿文件，不碰生产文件**：裁决结果写 `pilot/polish/<seg>/decisions.draft.jsonl`。
   **绝对不许**写 `decisions.jsonl`、`patches.jsonl`、`candidates.*.jsonl` 或任何 `frozen/` 下文件。
   草稿由主控会话事后检查并落盘。
2. **本地 Python 服务 + 单页前端**：`tools/adjudicate_server.py`，stdlib `http.server` 起服务
   （**零新依赖**——项目 deps 仅 pillow/pyyaml/jieba，不得增加）。**listen `0.0.0.0`**，
   默认端口取 **8788**（`--port` 可覆盖）。**不要自动打开浏览器**，启动后把 URL 打印到 stdout。
3. **队列直读 `candidates.*.jsonl` 自算**，不依赖 `triage.json`/`queue.md`（那两个要先跑 triage、
   且受 K 配额截断）。glm 通道日后补齐候选后，重启服务即自动纳入。
4. **手工编辑框不做任何机械校验**。理由（重要，影响设计）：编辑框内容**可能不是纯译文**——
   用户可能写得松散、附上给主控会话的批注、或写「这条再行讨论」之类的指示。
   **原样保存，不清洗、不 trim 内部空白、不校验控制码**。

## 2. 数据源（全部只读）

| 用途 | 路径 | 结构 |
|---|---|---|
| 原文与批号 | `pilot/polish/<seg>/frozen/source.jsonl` | `{id, jp, batch}` |
| 冻结面译文 | `pilot/polish/<seg>/frozen/opus.jsonl` | `{id, zh}` |
| 锁定信息 | `pilot/polish/<seg>/frozen/locked.json` | `{hard_ids, soft_ids, why}` |
| 各通道候选 | `pilot/polish/<seg>/candidates.<channel>.jsonl` | 见下 |
| **最新落盘译文** | `pilot/lanes/opus/data/{forward,patches}.jsonl` | 用 `tools.resolve.resolve_map(forward_rows, patch_rows)` 合并，**这才是右栏要显示的"现行译文"** |
| 阅读顺序 | `data/batches.jsonl` | `{batch, lane, ids: [...]}`，`lane=="main"` 的批按 batch 升序、批内按 ids 原序＝玩家阅读顺序 |

候选行结构（append-only，**同 id 取最后一条**）：
```json
{"id":6118,"channel":"fable-wf","batch":1,"zh":"…","score":72,"note":"…",
 "adjudicate":false,"alts":[{"zh":"…","note":"…"}],"noop":false,"jp_tail":"…","ts":"…"}
```
`alts` 可缺省或为空数组；`noop=true` 表示该通道照抄未改。

通道名从文件名解出：`candidates.fable-wf.jsonl` → `fable-wf`。目前有
`fable-wf` / `ds-flash` / `opus46-wf` / `glm-5.2` / `glm-5.3`（后两条目前只覆盖批 1–3，属正常）。

## 3. 队列计算

对每个 id，收集全部通道的**最后一条**候选。满足任一条即进队列：
- 该通道 `zh.strip() != frozen_opus[id].strip()`（提了改动）
- 或 `adjudicate == true`（显式请裁，哪怕没改）
- 或 `alts` 非空（给了备选）

队列按 **阅读顺序**排序（batches.jsonl 的 batch 升序 + 批内 ids 原序），不是 id 数值序。
当前 p5seg0-s0-s1 应算出 **381** 条左右（可用作自检基准，数字有出入不算错，说明依据即可）。

**漂移标记**：若 `frozen_opus[id] != current_lane[id]`，该条目要打「⚠ 冻结后车道已更新」标记
（现有 `pilot/polish/<seg>/lane_drift.json` 有现成结论可读，读不到就自己比对）。目前 p5seg0 有 1 条（id 6118）。

## 4. 界面

### 4.1 左边栏（队列）
- 列出全部队列条目，显示：id、批号、提案通道数（如 `3/5`）、状态标记。
- **状态标记要一眼可辨**：未处理 / 已处理（并区分 采纳·编辑·保留 三种结果）/ 有漂移警告 / 软锁。
  颜色+图标皆可，自行设计，但必须能在长列表里快速扫。
- **已处理的条目仍可点选并改判**（用户明确要求）。
- 支持键盘上下选择与滚动定位到当前条；列表要能应付 400+ 条不卡。
- 顶部给个进度（已处理 N / 总 M）与筛选（全部 / 未处理 / 已处理 / 有警告）。

### 4.2 右主体（等分左右两栏）
- **左栏：日文原文**。显示当前条目的 jp，**并在其上方按阅读顺序展示前文数十行**（默认 30 行，
  可配置）。当前行要显著高亮。
- **右栏：最新落盘译文**（`resolve_map` 的结果，不是 frozen 的），同样带**前文数十行**，
  当前行高亮。两栏的行要**逐行对齐**（同一 id 在左右同高度），便于对读。
- **各通道提案与批注**：放在右栏当前行的正下方（那是它们的语义位置——它们是这一行的替代译法）。
  每条提案显示：通道名、score、`adjudicate` 标记、提案译文、批注 note；有 `alts` 的把备选也列出来。
  与现行译文逐字相同的通道（`noop`）不必占地方，折叠或只显示一个小标记即可。
- 若该条目有漂移警告，在右栏当前行附近显著提示，并**同时显示冻结面文本与车道最新文本**。

### 4.3 提案「填入编辑框」按钮（用户明确要求）
- **每一条**提案译文（含每条 `alts` 备选）旁边都有一个按钮，点击把该文本填进编辑框。
- **仅当编辑框为空时生效**（防止误触覆盖用户写了一半的内容）；编辑框非空时按钮置灰或提示。

### 4.4 裁决动作
四种，做完**自动跳到队列中的下一条未处理项**：
- **采纳某通道**（`adopt`，记 `chosen_channel`）——每条提案旁一个「采纳」按钮。
- **采纳某备选**（`adopt_alt`，记 `chosen_channel` + `chosen_alt`＝1-based 序号）。
- **保留现译**（`keep`）——一个按钮。
- **手工编辑**（`edit`）——编辑框内容保存进 `edited_zh`，**原样保存**（见 §1.4）。
- 另需一个「跳过（暂不处理）」，不写草稿、只跳下一条。

`reason_code` 可选，给个自由输入框即可（P4 用过的值：语序/其他/补主语/口调/漂移/过度归化/术语/量词）。

## 5. 草稿文件格式

`pilot/polish/<seg>/decisions.draft.jsonl`，append-only，一行一条：
```json
{"id":6118,"verdict":"adopt","chosen_channel":"fable-wf","chosen_alt":null,
 "edited_zh":null,"reason_code":"其他","note":"","ts":"2026-08-19T12:00:00+00:00"}
```
- `verdict ∈ {adopt, adopt_alt, keep, edit}`。
- 改判：**追加新行**，不改写旧行（与生产 decisions.jsonl 同为 append-only 语义）；
  读取时同 id 取最后一条。**不要删除或重写已有行**。
- 服务启动时读回该文件，恢复"已处理"状态。

## 6. 设计原则与仓库惯例

- **纯 stdlib**，不加依赖；Python ≥3.12。
- 前端单页：一个 HTML（内联 CSS/JS 即可，或 `tools/adjudicate_ui/` 下拆几个静态文件）。
  **不引 CDN、不引外部框架**（离线环境要能用）。
- 服务只读仓库数据 + 只写草稿文件一处。任何写操作前确认目标路径就是草稿文件。
- **必须有 pytest 测试**（放 `tests/test_adjudicate_server.py`）：至少覆盖
  ①队列计算（含 adjudicate/alts/noop 三种进队理由）②阅读顺序排序 ③草稿读写与改判取最后一条
  ④漂移标记 ⑤HTTP 端点的基本响应。前端 JS 不要求测试。
- 现有可复用件：`tools/pipelib.py`（read_jsonl/dumps）、`tools/resolve.py`（resolve_map）、
  `tools/polishlib.py`。**不要重新实现它们**。
- 代码注释与文档写中文，风格参照 `tools/polish_triage.py`（说清"为什么这么判"而不只是"做了什么"）。
- commit 规范：`type: 中文摘要`（feat/fix/docs/data/test…）。

## 7. 交付与验收

1. `uv run python tools/adjudicate_server.py --seg p5seg0-s0-s1` 能起服务，打印访问 URL。
2. 浏览器打开后能看到 381 条左右的队列，能逐条对读、看提案、做四种裁决、自动跳下一条。
3. 关掉服务重启，已处理状态从草稿文件恢复。
4. `uv run pytest tests/test_adjudicate_server.py -q` 全绿；`uv run pytest -q` 不引入新失败。
5. **不得修改**本文件列出的任何生产数据文件；`git status` 里只应出现新增的工具/测试/草稿文件。

报告请简短：做了什么、关键设计取舍、测试结果、已知限制。不要贴大段代码。
