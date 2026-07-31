# Park 项落地（用户已裁决，2026-07-31）

用户看过最终评审后拍板：两项 park 的议题**都要做**，且明确「patch 内的文本条目退出召回列表比较有道理」。

---

## A. `build_context` 的 api-B/cc 前缀改用「时间轴位置窗口」，不再用 chapter 相等

### 问题（最终评审 Important 3/4）

`tools/build_context.py` 现在用 `led[i]["chapter"] == cur_ch` 过滤前缀。但 `chapter` 是 **lua 文件家族码**、不是叙事章节：

- 全书 16693 行里 **3887 行（23%）的 chapter 是 `"crd"`**（196 个卡片脚本全被压成一个伪章）；main 车道 173 个批里有 **121 段 chapter 切换**。于是 crd 批的前缀＝「全书 crd、零故事」，故事批则丢掉全部现实层框架——恰是 CLAUDE.md 点名最依赖全局剧情知识的那部分材料。
- extra 车道批次的 `chapter` 是 lua 文件名（如 `snr_common`），永不等于任何 ledger chapter → cc/api-B 下前缀**恒空**（实测批次 174）。

### 改法：窗口由「上一个章梗概卡」界定

游戏机制本身就给了正确的压缩边界：章梗概卡 133–145 代表「这一章已经被压成一张あらすじ卡」。骨架卡组（`skeleton/cards.zh.yaml`，196 条，**已含全部 133–145**）是每个 profile 都全量渲染的，所以边界之前的内容**本来就由骨架承载**——这正是计划接口表里 api-B/cc 那句「骨架 + 已完结章的章梗概卡 + 当前章已译 zh」的真正含义，也与 CLAUDE.md 的「DAG 组装规则」第 4 条（已做卡场景以卡面梗概替代全文实现前缀 compact）一致。

具体规则：

- **api-A**：不变——全部已译 timeline 前缀。
- **api-B / cc**：前缀 = 骨架 + **自「本批第一个时间轴位置之前、最近的一个章梗概卡单元」起**的已译 timeline 内容。
- **无时间轴位置的批次**（`seqs` 为空，即 extra / ambient 车道）：api-B/cc 下前缀**只给骨架**。这现在是一个**有意的选择**而非 chapter 比较失配的副产物——extra 车道装的是卡面/UI 文本，骨架卡组本身就是这些卡的正文，术语一致性靠尾部活动层的术语表保证。请在代码里用一句注释写清这是刻意为之。

已核实的真实数据（可直接用作用例的锚点）：

```
章梗概卡 script 单元（边界）共 13 个：
  seq=100 snr_crd_133   seq=193 snr_crd_134   seq=344 snr_crd_137  seq=345 snr_crd_138
  seq=354 snr_crd_135   seq=355 snr_crd_136   seq=366 snr_crd_145  seq=407 snr_crd_139
  seq=439 snr_crd_140   seq=488 snr_crd_141   seq=499 snr_crd_142  seq=507 snr_crd_143
  seq=517 snr_crd_144
173 个 main 批的 seqs 全部非空；extra/ambient 批的 seqs 全部为空。
窗口效果：batch 81（chapter=s3s）前序 id 7350 → 窗口内 1073；batch 173（chapter=crd）前序 16659 → 窗口内 1255。
```

### 实现要点

- 章梗概卡的识别用 **script 单元的 `src`**：`{f"snr_crd_{n}" for n in range(133, 146)}`。别再引入 chapter→卡号 的映射表（Task 7 已删掉的 `SYN_CARDS` 是另一回事，不要复活它）。
- 窗口起点：遍历 `env["timeline"]`，取所有 `seq < min(本批 seqs)` 的章梗概卡单元里 `seq` 最大的那个；一个都没有则起点为 0（＝全书开头，序章那 32 个批次就是这种情况）。
- 过滤前缀 id 时需要 `id → 所属 unit 的 seq` 映射，从 `env["timeline"]` 一次построй即可。
- **`--jp-fallback` 与「未译则退出码 2」的语义不许变**：窗口**外**的 id 根本不该进入前缀，因此也不该因为未译而触发退出码 2（它们由骨架承载）。窗口**内**的未译 id 仍按原规则处理。这一条请特别当心——现在的 `_render_prefix` 是先判未译再过滤，顺序错了会让 cc 档在窗口外的未译行上误报 2。
- 刚落地的「前缀渲染 timeline 结构（场景标题 + 回溯标记）」不要动语义；窗口只影响哪些 unit 的正文进前缀，标题/marker 仍按现有规则跟着实际渲染的内容走。
- `_render_prefix` 已经不接 `baseline` 参数——**保持这个性质**，`"## 五、本批任务"` 之前逐字节不受 baseline 影响的不变量必须继续成立。

### 测试（判别性，去掉产码必须变红）

1. 窗口边界：构造含两个章梗概卡 script 单元的 timeline 夹具，断言 `cc` 档只拿到最后一个边界之后的正文，边界之前的不出现；`api-A` 同批仍拿到全部。
2. 无边界时（本批之前没有任何章梗概卡）起点为 0，即窗口＝全部前序。
3. `seqs` 为空的批次（extra 车道形态）在 `cc` 档下前缀只有骨架、且**不报错、不退出 2**。
4. 窗口外的未译 id **不**触发退出码 2（这条最容易写错，务必单独一条）。
5. 既有的 `test_baseline_only_touches_tail` 与结构渲染用例保持绿；`test_apiB_and_cc_skip_other_chapter_prefix` 断言的是旧的 chapter 语义，**改写**成窗口语义（不要简单删掉——要让它继续守住「api-B/cc 的前缀比 api-A 短」这条性质）。

### 真实数据验收（把输出贴进报告）

```bash
uv run python tools/build_context.py --batch 81  --profile cc    --baseline none --jp-fallback
uv run python tools/build_context.py --batch 81  --profile api-A --baseline none --jp-fallback
uv run python tools/build_context.py --batch 174 --profile cc    --baseline none      # extra 车道
uv run python tools/build_context.py --batch 1   --profile cc    --baseline none      # 序章，窗口起点 0
```
报告里给出：批 81 在 cc 与 api-A 下 `## 二、前缀正文` 段的行数对比（应显著变小，量级参考上面的 1073 vs 7350）、批 174 的前缀是否只有骨架、批 1 是否仍正常。

---

## B. `recall.py` 参照 `patches.jsonl`：已在新版本改过的 id 退出召回列表

### 问题（最终评审 Minor 9，用户判为要做）

`tools/recall.py` 只看 `forward.jsonl` 自身的 `glossary_v`，不看 `patches.jsonl`。于是一个 id 只要首译是旧版本的，**每次对更高 `--glossary-v` 跑 recall 都会被反复召回**，即便它早已被 `add_patch` 用新版术语表修订过——召回列表永远不会随着你把活干完而缩短，而这正是这个工具唯一的可用性来源。

### 改法

判定改用**生效译文的版本**，与 `tools/resolve.py` 的覆盖语义保持一致（forward 先铺、patches 后写覆盖、同 id 多条 patch 取最后一条）：

- 对每个 id，取其**最后一条** patch 的 `glossary_v`（有 patch 时）或 forward 行的 `glossary_v`（无 patch 时），记作生效版本；
- 只召回**生效版本 < K** 且 ledger.jp 含 term 的行；
- 返回条目里的「旧译」`zh` 同样取**生效译文**（有 patch 取最后一条 patch 的 `zh`，否则取 forward 的），因为那才是你要拿来对照重译的东西。

`patches.jsonl` 与 `forward.jsonl` 一样**当前都不存在**，缺失时按现有写法优雅返回 `[]`。`find(term, glossary_v, data=None)` 的签名不变；`--emit-batch`、`--data-dir`、退出码语义都不变。

在函数 docstring 里写清这条语义（「按生效译文的术语表版本判断陈旧，与 resolve 的覆盖语义一致」）。

### 测试（判别性）

1. 一个 id 首译在 v1、后被 patch 到 v2，`find(term=…, glossary_v=2)` **不**召回它；同一夹具下 `glossary_v=3` 仍召回（因为生效版本 2 < 3）。
2. 同一 id 有多条 patch 时取**最后一条**（append-only 语义）。
3. 无 `patches.jsonl` 时行为与改前一致（既有用例应继续绿）。
4. 被召回条目的 `zh` 是生效译文（有 patch 时是 patch 的 zh，不是 forward 的）。

---

## 通用约束

- 当前基线 `uv run pytest -q` → **105 passed**；改完应更多且无回归。
- `uv run python tools/check_timeline.py` 仍须 OK 退出码 0；三个生成器双跑仍字节确定（本轮不该改到它们，跑一遍确认没误伤）。
- **不要动**：`data/`、`lua_scripts/`、`png/`、`skeleton/`、`glossary/`、`config/`、`prompts/`、`docs/`。
- 跑完 `uv run pytest -q` 后真实 `work/` 树不得被改动（Critical 1 刚修好的性质，别破坏——e2e 测试已经 hermetic，你新加的测试也不要写真实 `work/`）。
- 按逻辑拆 commit（`type: 中文摘要`）：建议 A 与 B 各一个。不要 push、不要建分支。
