# Task 4 报告：tools/polish_context.py（大批划分 + prompt 拼接）

状态：**DONE**

## 交付文件

- `tools/polish_context.py`（新建）：`plan()` / `render()` / `main()`（CLI）+
  内部辅助 `_dir_for` + 常量 `TASK_INSTRUCTIONS`/`OUTPUT_CONTRACT_HEADER`。
- `tests/test_polish_context.py`（新建）：14 个测试，覆盖 plan 双帽切组、
  render 的锁定标注/opus 嵌入/输出契约/glossary 全套/任务说明语义/未知会话
  报错/frozen-vs-live 回归锁，以及 CLI 的 `--plan`/`--session --out` 两条路径。

## 用户已裁定的两处修正（已按裁定实现）

**修正 1**：brief Step 1 里 `assert "b<批号>.out" not in p or True` 是恒真
断言（`or True` 使其永远通过）。已删除，替换为
`test_render_output_contract_uses_real_batch_numbers`：断言输出契约里出现
本会话**实际**批次的具体文件名（`raw/<channel>/b1.out`、`raw/<channel>/b2.out`），
且**不**出现字面占位符 `"b<批号>.out"`。落地时顺带发现一处自我矛盾：
`OUTPUT_CONTRACT_HEADER` 最初在说明性文字里也用了通用模板句
`` `raw/<channel>/b<批号>.out` ``（作为格式说明），与"不得出现字面占位符"
冲突——已改写为不含占位符的说明句（"文件名按批号命名，具体文件名见本节末尾
列表"），批号只在末尾的具体文件列表里出现，且都是实名。

**修正 2**：`plan` 签名按测试用例为准，定为
`plan(label, session_lines=None, session_size=None, repo=None)`，两个 None
时从 `polishlib.CFG` 取（`session_size=10`、`session_lines=600`，已用
`test_plan_defaults_from_cfg` 钉住："不传参"与"显式传 CFG 同值"结果一致）。
`render(label, session_no, repo=None)` 同样加了 `repo` 参数（brief 接口签名
没写，但与 `plan`/`polish_setup.setup/verify` 保持一致，且是测试隔离真实
仓库 `pilot/polish/` 的唯一手段）。

## plan() 的切组算法（长对话双帽）

```python
sessions, cur_batches, cur_lines = [], [], 0
for b in order:                      # order = frozen/source.jsonl 里批次首次出现顺序
    n = lines_by_batch[b]            # 该批次的 id 数（=行数）
    if cur_batches and (cur_lines + n > session_lines
                        or len(cur_batches) + 1 > session_size):
        sessions.append({"session": len(sessions)+1, "batches": cur_batches, "lines": cur_lines})
        cur_batches, cur_lines = [], 0
    cur_batches.append(b)
    cur_lines += n
if cur_batches:
    sessions.append({"session": len(sessions)+1, "batches": cur_batches, "lines": cur_lines})
```

贪心累加，任一帽超限（`>`，`==` 视为未超限，沿用 P3 语义）即收组另起。
批次的行数统计**只读 `frozen/source.jsonl`**（不读 `data/batches.jsonl`）——
`source.jsonl` 本身就是 Task 3 `setup()` 时从 `data/batches.jsonl` 按段表
批号区间收集来的 id 全集，保留了批次出现顺序与批内原序，信息等价且只有
一个读入面，与"render 只读 frozen"的隔离原则一致（brief Interfaces 里写的
"consumes data/batches.jsonl" 在此体现为"通过 frozen/source.jsonl 间接消费"，
而非重新直接读取活仓库的 `data/batches.jsonl`）。

单批自身即超过任一帽的极端情形（真实语料 27 批×~20 行/批不会出现）：算法
仍会把该批独立放进一组，不会死循环或丢批——因为超限判断的前置条件是
`cur_batches` 非空，孤批总能先被放入空组再触发下一批的收组判断。

## render() 的 prompt 结构大纲

```
# <label> 会话 N/M（批次 lo–hi，共 K 行）
## 一、任务说明（润色契约）           ← TASK_INSTRUCTIONS 常量，见下
## 二、锁定 id 清单（【锁】标记…）     ← 逐条：【锁】id（anchor|patched）：「jp」→「zh」
## 三、术语 / 风格 / 口调 / 锚点（frozen 冻结面，强制遵守）
   ### active.json（术语表）          ← json.dumps 内联
   ### style.md                      ← 全文
   ### polish.md（六条细则）          ← 全文（非摘要）
   （voices/*.md 全文，复用 build_context._render_voices）
   （anchors.yaml 渲染，复用 build_context._render_anchors）
## 四、章节纪要（背景参考）           ← notes/*.md 全文，目录为空则跳过整节
## 五、逐批正文（仅列非锁定 id…）
   ### 批次 b<N>
   [b<N>] <id>: 【<jp>】 / 【<opus zh>】   ← 每个非锁定 id 一行；全锁定的批次
                                            打印占位说明而非空段落
## 六、输出契约
   OUTPUT_CONTRACT_HEADER + 逐批 `- \`raw/<channel>/b<N>.out\`` 列表
```

四大数据源：`frozen/source.jsonl`（jp+batch）、`frozen/opus.jsonl`（现行译文）、
`frozen/locked.json`（锁定 id + why）、`frozen/glossary/*`（术语/风格/口调/
细则/锚点）+ `frozen/notes/*.md`——全部只读 `_dir_for(label, repo)/frozen`
下的文件，不触碰 `repo/glossary`、`repo/skeleton/anchors.yaml` 等活面。

`voices`/`anchors` 渲染直接 `import` 复用 `tools/build_context.py` 的
`_render_voices(voices_dir)` / `_render_anchors(anchors_path)`（brief 与补充
说明第 2 条要求），未做任何改写。

## 输出契约原文（写进 prompt 正文，逐字见 `OUTPUT_CONTRACT_HEADER` + 逐批列表）

```
本会话每个批次各产出一个 JSONL 文件，放在 `raw/<channel>/` 目录下
（`<channel>` 由实际执行你的模型/车道决定，如 `fable`/`deepseek`）；文件名
按批号命名，本会话需要产出的具体文件名见本节末尾列表。每个文件里：

- 批内每个非锁定 id 恰好一行——不多不少，不得合并，不得跳过。
- 锁定 id 绝对不能出现在这个文件的任何一行里。
- 每行是一个 JSON 对象，字段：
  {"id": <int>, "jp_tail": "<原文控制码剥离后末 8 字>", "zh": "<润色稿或原样抄 opus>",
  "score": <0-100 整数>, "note": "<可留空>", "adjudicate": <true/false>}
- jp_tail：你回显用的核对回执……取该行原文剥离 _n/_r/ruby 注音
  （<漢字,かな> 取前半段）后的最后 8 个字符。
- 不改的行：zh 逐字等于本会话给你的 opus 现行译文；score/note 仍要给
  （比如给高分表示"我确认这行不用动"）。

本会话需要产出的文件：
- `raw/<channel>/b1.out`
- `raw/<channel>/b2.out`
```

## TASK_INSTRUCTIONS 内容要点（任务说明质量要求逐项落地）

- **目标**：让译文读起来像汉语母语者写的，对白要像当代汉语口语；总纲
  "读出声，别扭就改，顺口就留着"。
- **强制约束**（5 条，编号列出）：锁定 id 不可动、术语/口调/锚点强制、
  "不改"是合法结论（zh 须逐字抄 opus）、控制码原样保留、片假名/汉字人名
  区分不可混用。
- **`score` 语义**：明确写"只用于同一批次内部按改动幅度/把握程度排序"、
  "不是入库阈值，也不是质量认证"。
- **`adjudicate: true` 触发时机**：与六条细则/style.md/术语/口调/锚点冲突、
  判断不了该不该动、涉及双层叙事真相措辞担心泄密——三类情形列出，且
  明确"不要自己下判断硬改或硬不改"。
- `polish.md`（六条细则）**整篇嵌入**（非摘要），与 `style.md` 全文一并
  嵌入，冲突时以 `style.md` 为准的分工在任务说明里重申一次（与 `polish.md`
  自身第一段的分工声明呼应）。

## 与 brief 的偏差汇总

1. 恒真断言按用户裁定删除替换（见上"修正 1"），并顺带修掉了
   `OUTPUT_CONTRACT_HEADER` 里与新断言矛盾的通用模板句。
2. `plan`/`render` 签名按用户裁定（见上"修正 2"）；`render` 额外加
   `repo=None`（brief 未写，工程必要——见下"CLI --repo"一节同理）。
3. `render()` 输出格式里的 `(note…)` 占位：brief Interfaces 描述的正文行
   格式是 `[b36] id: 【jp】 / 【opus zh】 / (note…)`，但 frozen 数据面
   （`source.jsonl`/`opus.jsonl`）里**没有任何逐 id 的 note 字段**可填——
   `rulings.md` 是段级追加式台账，不是逐 id 结构化数据。核实后确认
   "(note…)" 在 brief 里没有对应数据源，已省略这一段（正文行只保留
   `[b<N>] <id>: 【jp】 / 【opus zh】`），未杜撰数据填充。**如后续发现
   这是指向某个尚未落地的数据面（例如 Task 3 附带的逐 id 批注），需要
   回头补上。**
4. CLI 增加 `--repo`（brief 只写 `--seg`/`--plan`/`--session`/`--out`）：
   与 `tools/build_context.py` 现有 CLI 的 `--repo` 参数同一动机——没有它
   就无法在不碰真实仓库 `pilot/polish/` 的前提下对 CLI 做端到端测试
   （本任务说明第 10 条明令"不要对真实 SEG-1 跑任何命令"）。省略时行为
   与 brief 描述完全一致（落到仓库根）。
5. `plan.json` 落盘格式：brief 只说"记 `{session, batches, prompt_hash}`
   记进 plan.json"，未指定单会话覆盖 vs 多会话累积。已实现为**列表**，
   按 `session` 去重后追加/替换、按 session 排序——同一 session 重新渲染
   （`--session 1` 跑两次）替换而非重复追加（`test_cli_session_rerender_replaces_same_session_record`
   钉住），因为一个 SEG 通常有多个会话，CLI 会话式逐个渲染时应当在同一份
   `plan.json` 里累积全部会话记录，而不是每次覆盖整个文件。

## 跑测

```
$ uv run pytest -q tests/test_polish_context.py
14 passed in 0.12s

$ uv run pytest -q   （全量）
599 passed in 3.17s   （基线 585 + 本任务 14 = 599，吻合）
```

## 变异自检（两个，逐一记录命令 + 红/绿实况）

两次变异均只用 Edit 工具改动 `tools/polish_context.py` 源码后立即用 Edit
改回原文本（未用 `git checkout`/`restore`/`stash`）。

### 变异①：双帽只查其一

先测"丢批数帽"（只留行数帽 `cur_lines + n > session_lines`）：

```
$ uv run pytest -q tests/test_polish_context.py::test_plan_size_cap tests/test_polish_context.py::test_plan_respects_double_cap
F.
assert len(sessions[0]["batches"]) == 10
E   assert 11 == 10
```
**RED**——`test_plan_size_cap` 抓住（11 个 10 行小批不再在第 10 批处收组）。

再测反方向"丢行数帽"（只留批数帽 `len(cur_batches)+1 > session_size`）：

```
$ uv run pytest -q tests/test_polish_context.py::test_plan_size_cap tests/test_polish_context.py::test_plan_respects_double_cap
.F
assert [s["batches"] for s in sessions] == [[1, 2], [3]]
E   assert [[1, 2, 3]] == [[1, 2], [3]]
```
**RED**——`test_plan_respects_double_cap` 抓住（300+300+100=700 行本该在
600 处切开，丢了行数帽后三批被并成一组）。

两个方向都命中，说明 `plan` 的双帽条件不是"实为单帽的装饰性写法"——
brief Step1 给的两条测试（`test_plan_respects_double_cap`/`test_plan_size_cap`）
本身就是这条变异的天然回归锁，不需要额外新增用例。已用 Edit 逐次还原为
`cur_lines + n > session_lines or len(cur_batches) + 1 > session_size`。

### 变异②：render 从仓库活 glossary 读而非 frozen

把 `style` 那一行改成读 `_live_repo / "glossary" / "style.md"`（`_live_repo`
= 传入的 `repo` 或默认 `REPO`），其余仍读 frozen：

```
$ uv run pytest -q tests/test_polish_context.py::test_render_reads_frozen_glossary_not_live
F
assert 'ZZZFROZENMARK' in p
E   assert 'ZZZFROZENMARK' in '# segX 会话 1/1……'
```
**RED**——测试夹具在 `frozen/glossary/style.md` 写入独有标记
`ZZZFROZENMARK`，活仓库 `glossary/style.md` 内容是另一句（"活仓库版本。"）；
mutation 改成读活仓库后 `ZZZFROZENMARK` 从 prompt 里消失，测试如实抓住。
已用 Edit 还原为读 `fz / "glossary" / "style.md"`。

**判断**：两处变异都真正命中对应测试（不是"测试无牙"，也不是"变异没打中"）。
还原后跑了一次全量 `uv run pytest -q`（599 passed）确认现场干净。

## 安全核对

- 未执行任何写入真实 `pilot/polish/` 的命令；`ls pilot/polish` 在真实仓库
  下报 `No such file or directory`（预期）。
- `git status` 显示 `.claude/settings.json`、`data/api_ledger.jsonl` 仍是
  会话开始时的未暂存改动，未被本任务触碰、未被 add。
- 未对真实 SEG-1（`seg5-s6-s7f` 及其他任何段）运行 `plan()`/`render()`/
  CLI；全部测试固定用 `tmp_path` 造的 `segX` 替身仓库。

---

# 修复轮 1/N：评审 Important×2（均为真实语料实测发现）

状态：**DONE**

评审用真实 `polish_setup.setup()` 管线与真实 `data/ledger.jsonl`/
`pilot/lanes/opus/data/forward.jsonl` 抽样实测出两条问题，均非推测。逐一修复。

## Finding 1：`frozen/rulings.md` 完全没进 prompt

**问题**：`render()` 只读了 source/opus/locked/glossary/notes，从未 open
`fz / "rulings.md"`。spec §6 明写拼接器要读 jp/opus/notes/**rulings**；
spec §7.4：从 SEG-2 起 `polish_amplify.digest()` 会把裁决意图纪要前馈写进
下一段的 `rulings.md`——没有读取通路等于这些纪要被永久静默丢弃，且没有
任何机械信号会响（恒绿闸：闸不存在，永远不会触发）。

**修法**：`render()` 新增读取

```python
rulings_path = fz / "rulings.md"
rulings_text = rulings_path.read_text(encoding="utf-8").strip() if rulings_path.exists() else ""
```

仿 `notes` 的"目录为空则跳过"处理，改为"内容整体为空白则跳过"（`rulings.md`
在 `polish_setup.setup()` 阶段总会写入占位标题行，因此正常情况下**总是非空**
并总会出现在 prompt 里——这是设计内行为：SEG-1 阶段占位内容本身也值得让
执行模型看到"目前无前序裁决"，而不是完全消失不见）：

```python
if rulings_text:
    out.append("\n## 五、裁决与前序纪要（rulings.md；跨会话/跨段传递的用户裁定，"
                "与下方六条细则/style.md 冲突时以此为准——它记录的是已经拍板的具体案例）")
    out.append(rulings_text)
```

插入位置在「四、章节纪要」之后、「逐批正文」之前，原「五、逐批正文」「六、
输出契约」相应改号为「六」「七」（`tools/polish_context.py` 全文的编号
现为：一 任务说明 / 二 锁定 id / 三 术语风格口调锚点 / 四 章节纪要 /
五 裁决与前序纪要 / 六 逐批正文 / 七 输出契约）。

## Finding 2：正文行 `【jp】/【opus zh】` 包裹与游戏原生 `【名字】` 控制码嵌套

**问题**：评审用真实数据抽样 id=27 核实（`data/ledger.jsonl`：
`jp = "【アヤノ】「教室に来たよ」"`；`pilot/lanes/opus/data/forward.jsonl`
经 resolve 后 `zh = "【アヤノ】「到教室了哦」"`）——旧格式渲染出
`[b1] 27: 【【アヤノ】「教室に来たよ」】 / 【【アヤノ】「到教室了哦」】`，
双层方括号，而任务说明第 4 条又明令模型"【…】一律不得增删或挪位"，模型
无法判断外层是排版噪声还是控制码本身。全库绝大多数对白行都带
`【名字】` 前缀，这不是边角案例。

**修法**：正文行改用不与本库任何正文标记（`【】`『』`「」`≪≫`≦≧`○`■`）
冲突的纯 ASCII 标签：

```python
out.append(f"[b{b}] {i}: JP: {id2jp.get(i, '')} / ZH(opus): {opus.get(i, '')}")
```

顺带核查并修掉了同类风险点——「二、锁定 id 清单」一节原先用
`「{jp}」→「{opus}」` 包裹现行译文（`「」` 同样是本库对白引号的一部分，
与 jp 内容里已有的 `「」` 会产生同款嵌套），已同步改为同一套 ASCII 标签：

```python
out.append(f"- 【锁】{i}（{why.get(str(i), '?')}）："
            f"JP: {id2jp.get(i, '')} / ZH(opus): {opus.get(i, '')}")
```

（`【锁】` 本身是前置状态标记，不包裹粘贴的原文内容，保留。）

全文逐行核对：`tools/polish_context.py` 里除 `TASK_INSTRUCTIONS` 静态说明
文字（引用/解释控制码本身，不包裹动态拼入的语料）与 `【锁】` 前置标记外，
不再有任何位置用 `【】`/`「」`/`『』`/`≪≫`/`≦≧` 包裹动态拼入的 jp/zh 内容：

```
$ grep -n '「\|」\|【\|】\|『\|』\|≪\|≫\|≦\|≧' tools/polish_context.py
91: ……下面每一行的「opus zh」都已经是可用译文……          ← 静态说明文字
99: ……下面「二、锁定 id 清单」里带【锁】标记的 id……      ← 静态说明文字（提及节名/标记名，非包裹语料）
109:    ≪…≫、≦…≧、【…】、行首 ○/■，一律不得增删或挪位。  ← 静态说明文字（列举控制码集合本身）
110-111: （【アヤノ】=故事内角色 / 【彩野】=现实人物……）  ← 静态说明文字（举例说明区分规则）
201: ## 二、锁定 id 清单（【锁】标记；……）                ← 节标题里的固定标记词
205: f"- 【锁】{i}（...）："                                ← 前置状态标记，不包裹粘贴内容
```

## 真实语料自查（用户/评审要求：改完须用真实语料抽样自查一遍）

用 `data/ledger.jsonl` 与 `pilot/lanes/opus/data/forward.jsonl`（经
`resolve_map` 消化 patches）里 id=27 的**真实字面内容**（只读取值，未对
真实仓库跑任何 `polish_setup`/`polish_context` 命令、未在真实
`pilot/polish/` 下产生任何文件），塞进一个隔离的 `tmp_path` 替身仓库
自查渲染结果：

```
$ uv run python3 -c "
import json
print(json.loads([l for l in open('data/ledger.jsonl') if '\"id\": 27,' in l][0]))"
{'id': 27, 'jp': '【アヤノ】「教室に来たよ」', 'voice': 'AYA00180', ...}

$ uv run python3 -c "
import sys; sys.path.insert(0,'.')
from tools.pipelib import read_jsonl
from tools.resolve import resolve_map
fwd = read_jsonl('pilot/lanes/opus/data/forward.jsonl')
pat = read_jsonl('pilot/lanes/opus/data/patches.jsonl')
print(resolve_map(fwd, pat)[27])"
【アヤノ】「到教室了哦」
```

把这两个真实字符串塞进隔离 tmp 仓库、渲染并抽出正文行：

```
正文行： [b1] 1: JP: 【アヤノ】「教室に来たよ」 / ZH(opus): 【アヤノ】「到教室了哦」
嵌套自查：通过（无 【【 / 】】 / 「「 / 」」）
```

控制码 `【アヤノ】「教室に来たよ」` 原样完整出现、无额外包裹，`JP:`/`ZH(opus):`
标签与其零交集——与 `tests/test_polish_context.py::test_render_body_line_has_no_bracket_nesting_with_speaker_prefix`
的固定用例断言一致（该测试用的是同一句真实语料，写死进夹具，不依赖临时脚本）。

## 新增测试（4 条）

1. `test_rulings_content_appears_in_prompt`：改写 `frozen/rulings.md` 为
   模拟"跨段前馈裁决纪要"文本，断言其内容出现在渲染出的 prompt 里。
2. `test_rulings_section_skipped_when_placeholder_stripped_empty`：
   `rulings.md` 整体为空白时不应产出空标题节（回归防呆，非评审直接要求，
   顺手补上）。
3. `test_render_body_line_has_no_bracket_nesting_with_speaker_prefix`：
   `mini_seg_speaker` 夹具用真实形态 `【アヤノ】「教室に来たよ」` /
   `【彩野】「到教室了哦」`（评审 id=27 抽样的复现形态），断言渲染结果
   不出现 `【【`/`】】`/`「「`/`」」` 嵌套，且改用 `JP:`/`ZH(opus):` 标签。
4. （配套新增）`_build_mini_seg` 加 `jp_override` 参数（原先只有
   `zh_override`），用于构造带真实说话人前缀的原文样本。

## 变异自检（两个，逐一记录命令 + 红/绿实况）

均只用 Edit 改动 `tools/polish_context.py` 源码，改后立即用 Edit 逐字还原
（未用 `git checkout`/`restore`/`stash`）。

### 变异 Finding1：注释掉 rulings 读取/拼接（模拟评审发现的原始缺陷）

```
$ uv run pytest -q tests/test_polish_context.py::test_rulings_content_appears_in_prompt tests/test_polish_context.py::test_rulings_section_skipped_when_placeholder_stripped_empty
F.
assert '【裁决】b1#7' in '# segX 会话 1/1……'
```
**RED**——`test_rulings_content_appears_in_prompt` 抓住（改写进 frozen 的
裁决纪要文本从 prompt 里消失）；`test_rulings_section_skipped_when_placeholder_stripped_empty`
仍绿（该用例本就断言"不出现"，丢掉整个读取通路后自然仍不出现，属于同一
缺陷的另一面，不构成假阴性）。已用 Edit 还原为读取+条件拼接 rulings 一节。

### 变异 Finding2：正文行改回 `【jp】/【opus】` 包裹

```
$ uv run pytest -q tests/test_polish_context.py::test_render_body_line_has_no_bracket_nesting_with_speaker_prefix
F
assert '【【' not in p
E   '【【' is contained here:
E     [b1] 1: 【【アヤノ】「教室に来たよ」】 / 【【彩野】「到教室了哦」】
```
**RED**——精确复现了评审报告里的嵌套形态（`【【…】】`）。已用 Edit 还原为
`JP: {jp} / ZH(opus): {opus}`。

**判断**：两处变异都真正命中对应测试，不是"测试无牙"也不是"变异没打中"。
还原后重跑全量确认现场干净。

## 跑测

```
$ uv run pytest tests/test_polish_context.py -q
17 passed in 0.27s

$ uv run pytest -q   （全量）
602 passed in 3.09s   （修复轮前 599 + 本轮新增 3 条（第 4 条是夹具参数扩展，
                        不是独立测试用例）= 602，吻合）
```

## 安全核对（本轮）

- `git status`：仅 `tools/polish_context.py`、`tests/test_polish_context.py`
  显示为修改；`.claude/settings.json`、`data/api_ledger.jsonl` 未被本轮触碰。
- `ls pilot/polish` 在真实仓库下仍报 `No such file or directory`——真实
  语料自查全程只读取 `data/ledger.jsonl`/`pilot/lanes/opus/data/forward.jsonl`
  的字面值，塞进隔离的 `tmp_path` 替身仓库渲染，未对真实 SEG 跑任何
  `polish_setup`/`polish_context` 命令。
