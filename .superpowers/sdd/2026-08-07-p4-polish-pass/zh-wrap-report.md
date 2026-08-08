# 中文断行（折行）优化模块 — 报告

## 任务

`plot/` 卡名烤字的 `wrap_title`（`tools/bake_plot.py`）是纯贪心逐行填满算法：只看"这一行还
塞不塞得下"，不管断点是否落在一个词中间。用户实测点出坏例：卡56「回荡在走廊的声音」被断成
「…的声」/「音」——"声音"从中间拆开，末行还留了个孤字。目标：造一个共用折行模块
（`tools/zh_wrap.py`），把 `wrap_title` 换掉，并为将来的 `card/` 正文烤字调研 `skeleton/
cards.zh.yaml` 的重排可行性（只调研不改骨架）。

## 一、`tools/zh_wrap.py` 的设计

核心函数 `wrap(text, max_width, max_lines=None, measurer=None, use_jieba=True) ->
(lines, info)`。用字符级 DP（O(n²) 断点候选 × O(L) 行数，n/L 均是文本长度量级的小数，性能
足够）取代逐行贪心填满，在**所有合法断点组合**里选总代价最小的方案，而不是"能塞就塞"。

### 宽度

默认 measurer 是 `tools/pipelib.display_width`（复用，未重写——半角=1、全角/宽/中性=2）；
渲染场景（`bake_plot.py`）传入基于 PIL 字体 `textlength` 的像素 measurer。DP 对每个候选
`(i, j)` 断点区间调用一次 measurer，不做"字符宽度可加性"假设（不用前缀和差分），代价是
O(n²) 次 measurer 调用，但 n（卡名/正文单句长度）通常 <150，实测可接受（195 张卡名全量重跑
`bake_plot.py --check` 数秒内完成）。

### 惩罚权重与依据

| 常量 | 取值 | 依据 |
|---|---|---|
| `WORD_BREAK_PENALTY` | 5,000 | 单行 24 显示宽度单位时欠满平方项理论上限约 576（一整行全空）；5,000 保证"哪怕牺牲全场最均衡的排布也换不回一次词内断点"，但仍是有限数，不会在退让链里造成无解。 |
| `ORPHAN_LINE_PENALTY` | 20,000 | 必须重于 `WORD_BREAK_PENALTY`——用户点名的坏例"声音"同时触发词内断点与孤字两个问题；若孤字罚分更轻，DP 可能为躲词内断点反而制造孤字，本末倒置。`tests/test_zh_wrap.py::test_mutation_orphan_penalty_removed_is_detected` 用真实语料"在图书室读"（`skeleton/cards.zh.yaml`）实测钉死了这个优先级：DP 宁可切开"图书室"这个词也要避开孤字。 |
| `KINSOKU_RELAX_PENALTY` | 1,000,000 | 比前两项高两个数量级——退让链第2步专用的"万不得已"代价，且一旦触发必须在 `info["kinsoku_relaxed"]` 里显式报出。 |

`test_penalty_weight_ordering_matches_documented_priority` 把
`KINSOKU_RELAX_PENALTY > ORPHAN_LINE_PENALTY > WORD_BREAK_PENALTY > 0` 这条优先级钉成一条
可执行断言，防止未来改权重时无声破坏顺序。

### 硬约束 vs 重罚（原始任务表格里"硬禁止/重罚"的取舍）

- **真正硬禁**（候选断点直接被剔除，不参与代价比较，不是"罚很多分"）：
  - 禁则标点（行首收尾类、行尾起始类）——既有行为，本轮**未退化**，四条变异测试之一直接盯着它。
  - ASCII/数字连续串内部（如"10月3日"里的"10"）——迁移自 `bake_plot` 旧 `_tokenize` 的既有
    保证。
  - **假名（平/片假名）连续串内部——本轮新增，见下方"意外发现"**。
- **重罚而非硬禁**：中文词内部（jieba 分词边界）。理由见模块 docstring：① jieba 分词本身有
  歧义/噪音，当成物理约束太武断；② 理论上可能出现"任何词边界都放不下 max_lines"的文本，硬禁
  会导致无解；重罚保证 DP 总有解，且退让是可观测的（`info["word_breaks"]`）。

### 退让链（放不下 max_lines 绝不静默截断）

1. 正常 DP（禁则硬约束 + ASCII/数字/假名硬禁 + 词内断点重罚）。
2. 若无解：禁则从"硬剔除"降级为"重罚"（`KINSOKU_RELAX_PENALTY`），重跑；ASCII/数字/假名硬禁
   永不放松。触发时 `info["kinsoku_relaxed"]=True`。
3. 仍无解（文本在 `max_lines × max_width` 画布里根本装不下）：退回旧式"贪心填满 + 末行截断加
   省略号"，`info["truncated"]=True`、`info["dropped"]` 给出被丢弃的原文子串。**任何调用方都
   必须检查 `truncated`**，见 `wrap_title` 迁移后仍保留原语义（第三节）。

## 二、jieba 对照实验：实际数据与取舍结论

按要求先做"规则版 vs 规则+jieba"的对照实验再定，样本 = `skeleton/cards.zh.yaml` 的 195 条
`title_zh` + 196 段 `body_zh`（按 `\n\n` 拆段、段内去 `\n` 拼接），共 **391 个真实语料样本**。

### 结论：用 jieba。

理由不是"感觉更好"，是量化对比：

- **391 个样本里 71 个的重排结果因是否启用 jieba 而不同**。
- 逐样本检查"规则版（仅宽度+孤字+均衡+禁则，无分词）选出的断点是否落在一个真实词（用 jieba
  本身识别）内部"：**规则版产生 97 处词内断点违规**；启用 jieba 后同一批样本 **0 处残留**。
  典型例子（均为真实数据）：
  - 卡1正文：规则版把"起自己以"/"前写过"断在"以前"中间；jieba 版整句改断在"课桌"/"上的涂鸦"
    等词边界处，不再切开"以前"。
  - 卡56「回荡在走廊的声音」：规则版本身（仅靠孤字重罚+均衡）在这条样本上**碰巧**也避开了
    "声音"被切开（4/4 平衡断法本身不落在"声音"内部），但这是运气——见下条反例。
  - 卡25「选择：声音的主人」：规则版（无词边界信息）在 max_width 收紧到 15 时会选择"选择：
    声"/"音的主人"这个**均衡分最优但切开"声音"**的断点；jieba 版识别出"声音"是一个词，改选
    "选择："/"声音的主人"（虽然更不均衡，但不切词）。**这就是"jieba 多解决了什么"的直接证据
    ——纯规则版无法区分"两个独立汉字恰好相邻"和"一个双字词"，会在宽度压力下随手切开后者。**
- 反过来，jieba 也不是没有代价：391 个样本里没有发现任何 jieba 主动引入新问题的案例（0 处
  jieba 版比规则版更差）。

### 意外发现：jieba 对假名（片假名人名）完全无感，这不是 jieba 能力范围内的问题

对照实验过程中，把新算法接入 `bake_plot.py` 重跑全部 195 张卡名后做人工抽查，发现卡12
「选择：ユウイチ的答卷」被新算法断成"选择：ユウ"/"イチ的答卷"——**把人名"ユウイチ"从中间
切开**，比旧贪心算法（碰巧整段没切）还差。追查原因：

```python
>>> list(jieba.cut("选择：ユウイチ的答卷", HMM=False))
['选择', '：', 'ユ', 'ウ', 'イ', 'チ', '的', '答卷']
```

**jieba 是纯中文分词器，对连续片假名会退化成逐字符 1-token 切分**——"ユウイチ"被当成4个独立
"单字"，`WORD_BREAK_PENALTY` 对它完全不起保护作用。这不是 jieba 的 bug，是它的设计范围之外
（它没有日文假名词典）。本库大量嵌入未翻译的日文人名/专名（ユウイチ、アヤノ、サクラ、
ユカリ——见 CLAUDE.md「片假名角色名 vs 汉字角色名两套写法」），这个盲区如果不补，新算法在
这类卡上反而不如旧算法。

**修复**：加一条独立于 jieba 的硬约束——连续平/片假名串（`_KANA_RE =
re.compile(r"[぀-ヿㇰ-ㇿ]+")`）内部断点与 ASCII/数字串同等对待，**硬禁**而非重罚（见
`tools/zh_wrap.py::_kana_hard_positions`）。修复后全库 195 张卡名重新扫描：所有涉及
ユウイチ/アヤノ 等假名人名的卡片断行都不再切开人名（详见下方"三、bake_plot 迁移统计"与
`build/plot_zh/_wrap_diff.md`）。

`tests/test_zh_wrap.py::test_kana_run_never_split_even_though_jieba_cannot_see_it` 把
"jieba 对假名无感"这件事本身钉成断言前提（先证明前提成立，再证明修复生效），防止未来 jieba
版本更新后这条防线的必要性判断过时而没人发现。

### 取舍结论

**用 jieba**（`pyproject.toml`/`uv.lock` 已加 `jieba>=0.42.1`，diff 见文末）。规则版本身已能
解决孤字与均衡问题，但**无法解决词内断点**这一类——97 处真实违规是规则版力所不及、jieba 能
解决的实证。同时 jieba 有一个明确盲区（假名），已用独立机制补齐，不依赖它。

## 三、`bake_plot.py` 迁移统计

`wrap_title(text, font, max_width, max_lines, measurer)` 保留原签名/语义（`(lines,
truncated)`），内部改为委托 `zh_wrap.wrap()`。`_tokenize` 保留（仍被
`test_tokenize_keeps_ascii_digit_runs_atomic` 直接测试，`wrap_title` 本身不再用它）。

- 全量重跑 `uv run python3 tools/bake_plot.py`：195 张卡名，**0 条触发截断**（旧/新算法都是
  0），**0 处像素保真违规**（色带区域外逐字节不变）。
- **195 个卡名里，断行位置发生变化的有 67 个**（128 个未变化）——完整新旧对照表见
  `build/plot_zh/_wrap_diff.md`（195 行全量，供人复核）。
- 用户点名卡56：旧「回荡在走廊的声」/「音」→ 新「回荡在」/「走廊的声音」（"声音"完整落在
  同一行，无孤字）；已加入 `CELLZOOM_CARDS`（第一位）并生成独立对比图
  `build/plot_zh/_card56_before_after.png`（同一张卡的旧断法/新断法并排渲染，视觉上一眼可见
  差异）。
- 现有 `tests/test_bake_plot.py` 44 个测试里，只有 **1 处金标值需要更新**：
  `_NONFALLBACK_GOLDEN[170]`（卡170「选择：将アヤノ――」）的 `content_bottom/band_bottom` 从
  `(22, 26)` 变为 `(26, 30)`。根因：旧贪心断成"选择：将アヤノ"/"――"（第二行只有两个破折号，
  墨迹很浅）；新算法为了不拆开人名"アヤノ"、且两行更均衡，断成"选择：将"/"アヤノ――"（第二
  行多了"アヤノ"三个假名字符，实际渲染像素高度更深）——这是断行质量提升的预期副作用，`
  hard_range`（原文日文墨迹侧，与折行算法无关）**逐字节不变**，已在测试文件里写明根因并更新
  金标值。其余 12 张金标卡片、以及"195条title_zh零截断""70条需2行"等其它回归钉子**全部不变**
  （这些量只取决于"整句是否超宽"，不取决于断点算法本身，属于设计上就应保持稳定的量）。

## 四、`skeleton/cards.zh.yaml` 正文重排调研

独立报告 `build/cards_rewrap_report.md`（**只调研，`skeleton/` 零改动**）。摘要：

- **无损性验证**：194 张含 `body_zh` 的卡、195 个段落，逐卡验证"去 `\n`（按 `\n\n` 保留段落
  边界）+ 用 `zh_wrap.wrap(max_width=24, max_lines=None)` 重排"后内容与原文逐字符一致——
  **0 处不一致，0 处触发截断，全部通过**。
- **`\n\n` 段落卡**：全库唯一一张是卡41（两道谜题的答案，空行分隔），已在报告里给出处理方式。
- **超出原始任务预期的发现**：`\n\n` 不是唯一的"非机械折行"信号——还有 **22 张卡（28 处
  断点）** 用单个 `\n` 表达"一个选项一行"这类结构性约定（如卡4的三个「选择」逐行排列，拼起来
  显示宽度明明还没到 24 上限）。这批卡如果直接套用"去 `\n` 再按宽度重排"会把结构信息拼碎，
  报告里列出了完整 22 张卡片清单与建议的后续处理方式（人工标记，不在本轮做）。
- **改进前后对照（可客观判定的部分）**：现有 `body_zh`（人工手工折行，无工具辅助）里，
  **98 处（73 处切中文词 + 25 处切假名人名）断点落在一个完整词/专名内部**，分布在 67 张卡
  （约三分之一）——用户在任务提示词里点出的"以|前"例子就是卡1的真实数据。新算法重排后同一批
  检查点 **0 处残留**。全库断点位置变化统计：旧 388 处、新 374 处，对称差合计 606 处，涉及
  155 张卡（含大量结构性例外卡的断点重新分布，不能简单等同于"155张卡质量有问题"，详见报告
  4.1 节的说明）。
- **建议**：倾向"骨架冻结、重排在渲染侧做"（与用户倾向一致），理由与反方论据的权衡见报告
  第六节。

## 五、变异测试红/绿实况

四条任务要求的变异目标，全部**先手工在源码里应用真实变异（用 Edit 工具改常量/函数体，不是
只在测试里 monkeypatch）、跑测试确认真红、再用 Edit 还原**，过程中**未使用任何 git 回滚命令**：

| 变异 | 应用方式 | 结果 |
|---|---|---|
| 词边界惩罚被去掉 | `WORD_BREAK_PENALTY = 5_000` → `0` | 3 个测试真红（含专门的词边界测试 + 优先级钉子测试 + 孤字测试的连带失败，因为两个权重互相影响） |
| 孤字重罚被去掉 | `ORPHAN_LINE_PENALTY = 20_000` → `0` | 2 个测试真红 |
| 禁则退化 | `_kinsoku_block` 恒 `return False` | 2 个测试真红（含一条本来无关的既有禁则测试） |
| 超 `max_lines` 静默截断 | `wrap()` 里丢弃 `_greedy_truncate` 返回的 `truncated`（改用局部变量吞掉） | **4 个测试真红**，包括 `tests/test_bake_plot.py` 里两个既有的、与本次改动无直接关系的旧测试（`test_wrap_title_truncates_and_flags_when_it_does_not_fit`、`test_collect_overflow_surfaces_truncated_titles`）——说明这条防线的价值不局限于新模块自身，下游调用方的截断保护也依赖它。 |

每次变异都是"应用 → 跑测试确认失败原因与预期一致 → Edit 还原 → 跑测试确认恢复绿"，逐条独立
验证，不是一次性全改。这四条排查过程中还额外发现并修了一个真实 bug（见下）。

### 排查中发现的真实 bug：词内部断点位置 off-by-one

`_jieba_word_internal_positions` 与 `_ascii_digit_hard_positions` 最初实现里，"词/串跨度
`[pos, pos+L)`"对应的内部边界算成了 `range(pos, pos+L-1)`（结果 `{pos, ..., pos+L-2}`），
但 DP/`_kinsoku_block` 用的边界下标约定是"`j` 表示 `text[:j]`/`text[j:]`"，一个跨度
`[pos, pos+L)` 的词，真正的内部边界应该是 `{pos+1, ..., pos+L-1}`——两者错开一位。后果：
"10"（`pos`起长度2）该保护的边界是 `pos+1`（切在"1"和"0"之间），旧代码保护的是 `pos`（切在
"10"前一个字符和"1"之间，根本不在串内部）——保护形同虚设，只是因为当时的既有测试样本没有
触发这个位置才没被抓到（`test_wrap_title_never_splits_inside_a_number` 恰好靠其它因素侥幸
通过）。用卡25「选择：声音的主人」实测发现（新算法一度仍把"声音"切开），定位后修复，并加了
`test_ascii_digit_hard_positions_boundary_convention` / `test_jieba_word_internal_positions_
boundary_convention` 两条位置约定回归钉子。

## 六、测试与产物清单

- `uv run pytest -q`：**898 passed**（基线 877 + `tests/test_zh_wrap.py` 21 个新测试）。
- 新增：`tools/zh_wrap.py`（432 行）、`tests/test_zh_wrap.py`（364 行，21 个测试，含 6 处对
  真实语料的手工计算校准注释，避免"看起来对但样本选得不够刁钻"）。
- 改动：`tools/bake_plot.py`（`wrap_title` 换实现，保留签名；`CELLZOOM_CARDS` 加入卡56并置顶；
  加 `sys.path` 兜底以支持 `python3 tools/bake_plot.py` 直接调用内部 `tools.` 包导入）、
  `tests/test_bake_plot.py`（`_NONFALLBACK_GOLDEN[170]` 更新 + 根因注释）。
- 依赖：`pyproject.toml`/`uv.lock` 新增 `jieba>=0.42.1`（diff 已在上方"取舍结论"处交代）。
- `build/`（gitignore，不入库，人工复核用）：
  - `build/plot_zh/plot_{1..4}_a.png`、`_compare.png`、`_cellzoom.png`、`manifest.json`——
    全量重新生成。
  - `build/plot_zh/_wrap_diff.md`——195 个卡名新旧断法全量对照表。
  - `build/plot_zh/_card56_before_after.png`——用户点名坏例的专用并排对比图。
  - `build/cards_rewrap_report.md`——`cards.zh.yaml` 正文重排调研报告（只读调研，`skeleton/`
    零改动）。

## 七、硬约束自查

- `skeleton/`、`png/`、`lua_scripts/` 全程只读，未做任何写入（`cards_rewrap_report.md` 的生成
  脚本只 `yaml.safe_load` 读取，未调用任何写文件到 `skeleton/` 的代码路径）。
- 未碰 `.claude/settings.json`、`data/api_ledger.jsonl`、`pilot/`——这两个文件在 `git status`
  里显示的改动是会话开始前就存在的（`.claude/settings.json` 见会话起始 gitStatus 快照；
  `data/api_ledger.jsonl` 的新增行时间戳是 2026-08-05，早于本轮工作），提交时会逐路径显式
  `git add`，不会带上这两个文件。
- 未使用任何 `git` 回滚类命令；四条变异全部用 Edit 应用与还原。
