# Task 11 报告：SEG-1 点火准备（冻结实跑 + runbook + handoff）

状态：**DONE**。commits：`f644e16`（两条 minor 修复）、`ffcd6b4`（runbook/handoff + SEG-1 冻结产物）、
`b51426a`（SDD 证据）、评审修复轮 commit（见文末"修复轮"一节）。
全量测试：**702 passed**（评审修复轮之后；此前一轮 700 passed）。

---

## 一、两条挂起 minor 的修法

### 1.1 `polish_setup.verify()` 忽略名单（`.DS_Store` 伪报）

**问题**：反向扫描（frozen 里凭空多出的文件报漂移，Task 3 补的防线）没有任何忽略名单，
macOS Finder 翻一眼 `frozen/` 就会生成 `.DS_Store` 并被误报成"未登记（凭空多出）"。

**修法**：`tools/polishlib.py` 新增：

```python
IGNORE_BASENAMES = {".DS_Store", "Thumbs.db"}
IGNORE_SUFFIXES = (".pyc",)
IGNORE_DIR_NAMES = {"__pycache__"}

def is_ignored_extra(p: Path) -> bool:
    if p.name in IGNORE_BASENAMES: return True
    if p.suffix in IGNORE_SUFFIXES: return True
    if IGNORE_DIR_NAMES & set(p.parts): return True
    return False
```

`tools/polish_setup.py::verify()` 反向扫描循环里加一行 `if is_ignored_extra(p): continue`
（放在"是否已登记"判断之前）。名单**逐字面/后缀精确匹配**，不用通配符/前缀匹配，故意窄——
用户点名的风险是"伪报淹没真信号"（ruby 闸 104→5、数字闸 212→1 的同类教训），但收窄的名单
同样不能宽到藏住真文件。

**测试**（`tests/test_polishlib.py` + `tests/test_polish_setup.py`，共 5 条新增）：
- `test_is_ignored_extra_matches_known_fs_noise` / `test_is_ignored_extra_does_not_match_real_files`：
  单元级正反用例。
- `test_verify_ignores_ds_store_and_friends`：真实 `verify()` 场景，塞入
  `.DS_Store`（顶层+子目录）/`Thumbs.db`/`__pycache__/*.pyc` 四种噪声，`verify() == []`。
- `test_verify_without_ignore_list_would_report_ds_store`（**变异证明名单有牙**）：
  `monkeypatch.setattr(ps_mod, "is_ignored_extra", lambda p: False)` 打回"名单不存在"，
  同一个 `.DS_Store` 立刻被判漂移——证明上一条测试确实是靠忽略名单过关，不是反向扫描本来
  就漏了它的巧合。
- `test_ignore_list_does_not_hide_real_extra_file`：一个正常命名的多余文件
  （`sneaky_not_noise.md`）必须继续被判漂移，证明名单没有宽到能藏真文件。

**实测输出**（变异，跑完已还原代码）：
```
FAILED tests/test_polish_context.py::test_render_has_no_duplicate_or_skipped_chapter_numbers
```
（这条是章节编号那个变异的输出，见下节；`.DS_Store` 那条变异的实测过程见 1.1 节测试本身
——`test_verify_without_ignore_list_would_report_ds_store` 直接把"去掉忽略名单"的效果内嵌
进用例本身跑一次红一次绿，运行 `uv run pytest tests/test_polish_setup.py -v` 可见其常态是
绿（因为它在测试内部先 monkeypatch 再断言应该失败的行为确实失败），已在开发中人工核实过
若移除 monkeypatch 该测试会变得毫无意义（不再验证任何东西），故此测试的"红/绿"验证方式是
内嵌对抗而非外部临时改代码。

### 1.2 `polish_context.render()` 章节编号撞号与跳号

**问题**：`render()` 自己给"术语/风格/口调/锚点"编号"## 三、…"，同时又整段复用
`build_context._render_anchors()`——后者内部硬编码"## 三、锚点行"（在 `build_context.py`
自己的编号体系里，那确实是第三节，合法）。两处"三"撞在一起，渲染出的文档里"三"出现两次后
跳到"四"；另外 `notes_text`/`rulings_text` 为空时对应小节被跳过，编号也会跳号。

**决策（本任务自行裁定，写明理由）**：**本工具（`polish_context.py`）自己的顶层标题一律
不带序号**，改用纯描述性标题（"## 任务说明（润色契约）"、"## 锁定 id 清单…"、
"## 术语 / 风格 / 口调 / 锚点…"、"## 章节纪要…"、"## 裁决与前序纪要…"、"## 逐批正文…"、
"## 输出契约"）；`_render_anchors()` 返回的文本在拼进本工具输出前做一次局部字符串替换
（`anchors.replace("## 三、锚点行", "### 锚点行", 1)`），把它从顶层标题降级成
"术语/风格/口调/锚点"节下的子块。

**为什么这样修最干净（评估过的另外两条路及其问题）**：
1. **重新编号**（让本工具的序号动态跟随哪些小节真的出现）：治不好"两个'三'撞号"这个根因
   ——`_render_anchors()` 硬编码的"三"来自 `build_context.py` 自己的编号体系，与本工具的
   编号是两套独立计数，除非同时改 `_render_anchors()` 本身，否则重新编号本工具也仍会撞上
   它。而且这个模块每次渲染都要按 `notes_text`/`rulings_text` 是否为空重算序号，边界一多
   就脆（未来再加一个条件小节又要重新走一遍这个逻辑）。
2. **去改 `_render_anchors()` 里那行硬编码文案**：它是 `build_context.py` 生产链路
   （`build_context.build()`）在用的**共享函数**，且那段代码本身也已经过评审、是 P3
   「按批四件套」钉死面的一部分（生产树独立 pin 版本、canary 覆盖）。为了本工具的一个
   装订问题去动它，等于让一个跟 P4 无关的改动去牵动 P3 的升级/canary 判定流程，不成比例。
3. 最终选择的方案（顶层不编号 + 局部降级复用文本）**只改 `polish_context.py` 一个文件**，
   不碰 `build_context.py`，也从根上同时消掉"撞号"（顶层不再有自己的"三"去撞）与"跳号"
   （顶层压根没有数字序列可跳）两个问题，且对未来增删条件小节天然稳健。

**测试**（`tests/test_polish_context.py`，新增 2 条）：
- `test_render_has_no_duplicate_or_skipped_chapter_numbers`：断言 `"## 三、"` 不出现在渲染
  文本里、`"### 锚点行"` 出现、且全部 `"## <汉字数字>、"` 形态的标题都不出现。
- `test_render_chapter_titles_stable_regardless_of_optional_sections`：notes/rulings 都
  缺席时既有各节标题文字不受影响（没有序号可跳，天然稳定）。

**变异实测（还原前跑过，证明测试有牙）**：临时把 `## 术语 / 风格 / 口调 / 锚点` 那行改回
`## 三、术语 / 风格 / 口调 / 锚点`、把 `anchors.replace(...)` 改回直接 `anchors`（相当于撤销
本次修复），重跑：
```
FAILED tests/test_polish_context.py::test_render_has_no_duplicate_or_skipped_chapter_numbers
AssertionError: assert '## 三、' not in '...## 三、术语 / 风格 / 口调 / 锚点...'
```
另把 `TASK_INSTRUCTIONS` 的标题行改回 `## 一、任务说明（润色契约）`（相当于只撤销标题去
序号那一半），重跑：
```
FAILED tests/test_polish_context.py::test_render_has_no_duplicate_or_skipped_chapter_numbers
FAILED tests/test_polish_context.py::test_render_chapter_titles_stable_regardless_of_optional_sections
```
两次变异后已用 `git checkout -- tools/polish_context.py` 还原、重新逐字应用本次修复
（中途误把整份修复撤销过一次，已发现并重做，详见下方"与 brief 的偏差/中途插曲"）。
还原后 `tests/test_polish_context.py` 19 项全绿，全量测试 700 passed。

---

## 二、SEG-1 实跑记录（真实数据）

```bash
uv run python tools/polish_setup.py --seg seg1-s2 --opus-data pilot/lanes/opus/data
# → 冻结完成：/Users/fotile96/Zndnovel/pilot/polish/seg1-s2

uv run python tools/polish_setup.py --verify seg1-s2
# → 冻结校验：无漂移

uv run python tools/polish_context.py --seg seg1-s2 --plan
# → {"session":1,"batches":[36..45],"lines":568}
#   {"session":2,"batches":[46..55],"lines":488}
#   {"session":3,"batches":[56,57],"lines":371}
#   {"session":4,"batches":[58..62],"lines":569}

uv run python tools/polish_calibrate.py --seg seg1-s2 --make
# → 已知偏差告警 + pilot/polish/seg1-s2/calib/seg1-s2.batch.jsonl
```

命令形态与 brief 逐字一致（`--opus-data`/`--verify LABEL`/`--plan`/`--make` 均以 `--help`
核对过）。**预期兑现**：frozen 全套生成、verify 绿、4 组会话（brief 预计 3–5 组，命中）、
校准批就绪。

### 2.1 核对 `frozen/locked.json`

`locked.json`：8 个锁定 id，4 个 `why=anchor`、4 个 `why=patched`。逐条对照
`skeleton/anchors.yaml`（用 `yaml.safe_load` 收集全部 `items[].id`）与
`pilot/lanes/opus/data/patches.jsonl`：

| id | locked.json 的 why | 实际在 anchors.yaml？ | 实际在 patches.jsonl？ |
|---|---|---|---|
| 2743 | patched | 否 | 是 |
| 2782 | patched | 否 | 是 |
| 2822 | anchor | 是 | 否 |
| 9448 | patched | 否 | 是 |
| 9475 | patched | 否 | 是 |
| 9785 | anchor | 是 | 否 |
| 9793 | anchor | 是 | 否 |
| 9804 | anchor | 是 | 否 |

**8/8 分类正确**（`_locked_payload()` 的"两者都命中优先标 anchor"规则本次数据未触发，因为
这 8 个 id 恰好互斥分布）。

### 2.2 会话分组核对

用 `frozen/source.jsonl` 逐批行数手算验证双帽切分逻辑：

```
b36..b45: 88+64+75+16+81+28+101+5+7+103 = 568（10 批，命中 session_size=10 帽）
b46..b55: 32+158+76+31+64+71+2+43+3+8   = 488（10 批，同上）
b56,b57 : 233+138 = 371（若含 b58 则 371+326=697>600，命中 session_lines=600 帽，故在 57 处收组）
b58..b62: 326+103+8+57+75 = 569（段尾，5 批）
```
四组的切分点分别由"批数帽"（组1、组2）与"行数帽"（组3）触发，组4 是段尾自然收尾——
双帽机制按设计工作，无异常。

### 2.3 渲染并通读一份真实 prompt（session 1）

```bash
uv run python tools/polish_context.py --seg seg1-s2 --session 1 \
    --out <scratchpad>/p4s1-s1.md
```
产出 709,990 字节 / 4,883 行。逐节通读（任务说明 → 锁定 id 清单 → 术语/风格/口调/锚点 →
章节纪要 → 裁决与前序纪要 → 逐批正文 → 输出契约），以"我是要干活的模型"视角的结论：

- **可执行性总体良好**：任务说明清楚区分"强制约束"与"润色建议"，`score`/`adjudicate` 语义
  说明到位，输出契约字段与取值方式（`jp_tail` 计算规则）解释清晰，逐批正文的 `[bN] id: JP:
  … / ZH(opus): …` 格式简单可靠，不与游戏原生控制码（`【】`/`「」`/`≪≫`/`≦≧`）冲突（已有
  Task 4 的专项测试钉死这点，本次通读复核未见回归）。
- **style.md 全文嵌入极其详尽**（本 SEG glossary v14，约 56KB）：包含大量具名判例、边界条件、
  已知反例——这是好事（术语/风格判断的证据链完整），但意味着**输入体量本身就很大**，与
  spec §8 "成本量级 input≈翻译 pass 的 2 倍上下"的预期一致，不是异常。
- **anchors.yaml 全篇（120 条锚点，覆盖全书 s0f 到 e2f）整体嵌入，不按本 SEG/本 session
  裁剪**——这是"译者全知"设计原则的直接体现（style.md 全知纪律第一条：可参考骨架卡组与
  任意已译章节），确认为有意设计，不是信息泄露/范围错误。
- **`notes/crd.md` 单文件 308KB，覆盖全书 crd 章节跨度（batch 3 到 173+）**：因为 notes 是
  按**章**存储（不是按批），而 seg1-s2 的 `chapters` 包含 `crd`，`_copy_notes()` 会把整份
  crd.md 整体拷入冻结面并整篇嵌入每一个 session 的 prompt——即便 session 1 只涉及 b36-45
  （早期 s2s 剧情），notes 里仍会带出远至 s7f/e2f 附近 crd 批次的内容。这是设计文档已经
  承认的既有行为（`polish_setup._copy_notes()` 的 docstring 明写"notes 是按章存的，没有
  批号维度"），且与"译者全知"原则一致（这些是本项目此前生产轨已经产生的术语提案清单，
  不含未入线的正文），**不构成信息泄露或范围错误**，但**是一项值得记台账的成本事实**：
  单个 SEG 若涉及 `crd` 章节，每个 session 的 prompt 都会额外带上约 300KB 的跨全书提案
  文本。frozen 总量的 45%（307771/682526 字节，含全部 glossary+notes）来自这一份文件。
  建议未来若发现执行通道对超长 prompt 有截断/遗漏风险，第一个该检查的就是这里。
- **输出契约里 `<channel>` 是字面占位符**（"放在 `raw/<channel>/` 目录下（`<channel>` 由
  实际执行你的模型/车道决定…)"）：若不在派发指令里显式替换成真实通道名，执行子代理可能
  直接照抄字面 `<channel>` 当目录名。**已在 handoff 文档里逐条把绝对路径写死**
  （`/Users/fotile96/Zndnovel/pilot/polish/seg1-s2/raw/fable-wf/b<N>.out` 等），规避这个
  风险，但这是渲染层本身值得记录的一个"看起来会绊人"的细节。
- 未发现控制码丢失、说话人前缀嵌套、编号错乱（已修）等结构性问题。

### 2.4 frozen 大小与入库决定

```
pilot/polish/seg1-s2/frozen 总计 1.0M
  glossary/style.md        55,978 B
  glossary/polish.md       11,075 B
  glossary/anchors.yaml    51,817 B
  glossary/voices/*.md   （7 份，共约 54,663 B）
  notes/crd.md            307,771 B
  notes/s2f.md             10,556 B
  notes/s2s.md            135,491 B
  source.jsonl / opus.jsonl / locked.json / rulings.md（合计较小）
```

**决定：`frozen/` 不入库**（`.gitignore` 新增 `pilot/polish/*/frozen/`），沿用 opus 车道
既有惯例——`pilot/lanes/opus/skeleton/` 与 `pilot/lanes/opus/glossary/` 同样是被
`.gitignore` 忽略的"冻结拷贝"（第 23-24 行既有规则），理由写在既有 `.gitignore` 注释里：
"体量大，可由 manifest 哈希追溯"。P4 的 `frozen/` 与它们是同一性质——内容全部来自别处已经
入库的文件（车道 `data/`、仓库 `glossary/`、`skeleton/anchors.yaml`）的某个时间点整体拷贝，
`manifest.json` 记了逐文件 sha256，理论上任何时候都能重放 `polish_setup.setup()` 精确重建
（只要对应时点的车道数据与 glossary 版本还在）。1.0M 本身不算大（仓库已有 6.3M 的
`pilot/lanes/opus/` 数据），但"是否入库"的判据是**可再生性**，不是体量——沿用既有原则，
不为 SEG-1 的具体大小另开先例。

`manifest.json`、`plan.json`、`calib/*.jsonl`/`*.json` **入库**（brief 建议项，已执行）：
三者都含哈希/时间戳/随机抽样结果，**不可**从别处重新推出，是本次实跑唯一的可追溯性证据。

---

## 三、runbook / handoff 结构大纲

### `docs/ops/p4-polish-runbook.md`

一、命名与目录约定（`pilot/polish/<label>/` 全量文件清单 + 入库/忽略标注、channel 命名
约定、raw 路径绝对化要求）→ 二、SEG 冻结（`polish_setup`）→ 三、通道准入小考
（`polish_calibrate --make/--score`）→ 四、会话点火（回指 handoff）→ 五、逐批 ingest
（`polish_ingest`，判死 vs 整批失败两类）→ 六、机械闸（`polish_check`，W4 分工说明）→
七、四桶分流（`polish_triage`，`meta` 字段解读）→ 八、段末裁决（`queue.md` 逐条定夺 +
append `decisions.jsonl` 具体命令形态，用 `pipelib.append_jsonl` 的 python 片段，因为
`decisions.jsonl` 没有专属写入 CLI）→ 九、放大扫描（`polish_amplify`，每 SEG 限一轮）→
十、清关（`polish_commit`，dry-run→`--apply`，`--data-dir` 强制）→ 十一、清关后必跑
（`check_batch` 全段 W4 复检 + `check_qa_quotes.py` + 题库更新）→ 十二、阈值调整记台账 +
推翻率闸操作说明 → 末尾"纪律速记"六条（对齐 P3 runbook 的同类板块）。

### `docs/ops/p4-seg1-polish-handoff.md`

角色与边界（控制会话 vs 两条执行通道）→ 开工前确认 → 会话分组（四组实际批号/行数/
prompt_hash，SEG-1 真实数据）→ 通道一 `fable-wf`（Workflow `agent(prompt, {"model":"fable",
"effort":"high"})`，逐字派发提示词模板，绝对路径写死）→ 通道二 `ds-flash`（paseo
`list_providers` 核实 provider 实名的强制前置步骤、独立 workspace、计费入
`data/api_ledger.jsonl`、心跳=raw 目录 mtime）→ 并行安全条款（四条）→ 准入小考（两通道
各跑一次，决定自动清关权初值）→ 落地后命令序列 → 段末流程（回指 runbook，不复述）→
收尾确认（生产数据 diff / 入库范围 / 全量测试）。

---

## 四、变异红绿实况汇总

| 变异 | 预期 | 实测 |
|---|---|---|
| `polishlib.is_ignored_extra` 打回恒 `False` | `.DS_Store` 场景转红 | ✅ 红（`test_verify_without_ignore_list_would_report_ds_store` 内嵌验证） |
| 正常命名多余文件（非噪声名单） | 仍应报漂移 | ✅ 红即为通过（`test_ignore_list_does_not_hide_real_extra_file` 断言"必须报"，验证名单没有藏住真文件） |
| `polish_context.render()` 顶层标题改回带编号（`## 三、术语…`）+ 不降级 anchors 标题 | `test_render_has_no_duplicate_or_skipped_chapter_numbers` 转红 | ✅ 红（`assert '## 三、' not in p` 失败，实测输出见上） |
| 仅撤销 `TASK_INSTRUCTIONS` 标题去序号（其余不变） | 两条新测试均应转红 | ✅ 两条皆红 |
| 变异复核后还原代码 | 19 项 `test_polish_context.py` 应全绿 | ✅ 全绿；全量 700 passed |

---

## 五、与 brief 的偏差

1. **命令形态**：brief 给出的四条命令与实际 `--help` 完全一致（`--seg`/`--opus-data`/
   `--verify LABEL`/`--plan`/`--session N --out`/`--make`），**无需调整**——这是九个任务
   里第一次 brief 与实现零偏差的命令形态，此前几个任务多次出现 brief 与实现不符（如 Task 7
   的种子 key、Task 3 的按批号取 notes 写法等），本任务提前逐个 `--help` 核对后未发现类似
   问题。
2. **`decisions.jsonl` 没有专属 CLI**：brief Step 3 提到"段末裁决 queue.md 逐条 verdict+
   原因码 append decisions.jsonl 的命令形态"，隐含期待存在某种命令；实测九个工具里没有
   `polish_decide.py` 这一类专属写入工具（`polish_commit.py` 的模块 docstring 与
   `tests/test_polish_commit.py` 注释明确写"decisions.jsonl 是人工在裁决会话里手写的
   固件"）。runbook §八按此写成用 `tools.pipelib.append_jsonl` 的 python 片段，并非缺失
   而是如实反映现状。
3. **`frozen/` 入库范围**：brief 只给了"参照 opus 车道既有惯例"的方向性指示，未给出结论。
   本任务通过检查 `.gitignore` 现行规则 + `git ls-files pilot/lanes/opus/` 实测确认惯例
   是"冻结拷贝忽略、真相源数据入库"，据此决定不入库 `frozen/`，并把这条规则显式写进
   `.gitignore` 注释与 runbook §一。
4. **四份 session prompt 全部实渲染**（brief 只要求 session 1，本任务额外渲染了
   session 2-4）：目的是让 handoff 文档能给出全部四组的真实 `prompt_hash`（已写入
   `plan.json`，随 manifest.json/plan.json 一并入库），使 handoff 文档对四组会话都有据
   可查，不止第一组。这几份 prompt 文件本身落在 `work/ctx/`（已被 `.gitignore` 的 `work/`
   规则忽略），不额外增加入库体积。
5. **中途操作插曲（已订正，不影响最终交付）**：在做章节编号变异验证时，误用
   `git checkout -- tools/polish_context.py` 把当时尚未提交的修复整体撤销（该命令的本意
   是"跑完变异后把临时改动还原"，但目标文件是修复本身所在的文件，而非只有临时改动）。
   随即通过 `git diff --stat` 发现文件回到未修复状态，重新逐字应用了 §一 1.2 节的完整
   修复并复核测试全绿后才继续。此后所有变异验证均改为"改一处、跑测试、立刻用同一份
   python 脚本原地写回原文本"的方式，不再对该文件使用 `git checkout --`。

---

## 六、测试输出（最终态）

```
uv run pytest -q
700 passed in 3.6s
```

```
git status --short pilot/lanes/opus/data/
（空）
```

```
git log --oneline -2
ffcd6b4 docs: P4 润色 runbook + SEG-1 双通道点火 handoff（冻结与计划实跑产物）
f644e16 fix: P4 挂起两条 minor —— verify() 忽略名单 + polish_context 章节编号
```

## 七、未执行事项（按指令刻意不做）

- 未执行 `polish_ingest`/`polish_check`/`polish_triage`/`polish_commit`——这些需要真实模型
  输出，是点火之后的事。
- 未执行 `polish_commit --apply`——本任务绝不写入任何 patch。
- 未修改 `.claude/settings.json`、`data/api_ledger.jsonl`——工作树里这两个文件本次会话
  开始前已有其他会话的未提交改动，全程未碰。
- 未更新 `.superpowers/sdd/2026-08-07-p4-polish-pass/progress.md`——brief 只要求写
  `task-11-report.md`，未见其他任务在实施阶段本身写 progress.md 台账的先例（该文件的
  "Task N: complete…"行看起来是评审/收尾阶段追加的），故本报告不越权改动。

---

## 八、评审修复轮（Finding A/B + git checkout 事件的处置）

评审对实跑产物做了**全量核对**（不是抽查）：1996 个 id 全部逐一比对 resolve 结果、8 个
locked id 的 why 分类 8/8 正确、会话分组自己重算与 `plan.json` 完全一致、`manifest.json`
19 个 `files` 条目双向覆盖且哈希全匹配；runbook/handoff 的命令形态逐个 `--help` 比对无
偏差。报回两条要修（Finding A Important、Finding B Minor），并对本报告自陈的
`git checkout --` 事件做了单独裁定（见 §8.3）。

### 8.1 Finding A：章节去编号漏了正文里的交叉引用

**问题**：`tools/polish_context.py` 的 `TASK_INSTRUCTIONS` 常量里，第一条强制约束仍写着
"下面「二、锁定 id 清单」里带【锁】标记的 id"——这是修复前（`## 二、锁定id清单`）的旧
标题引用。§一 1.2 节的修复把顶层标题改成不带编号的"## 锁定 id 清单"后，这句散文引用
没有跟着改，指向一个已经不存在的编号。评审在真实渲染的 session 1 prompt 第 13 行核实
到它原样存在。

**修法**：
```python
# 修复前
1. **锁定 id 绝对不能动。** 下面「二、锁定 id 清单」里带【锁】标记的 id
# 修复后
1. **锁定 id 绝对不能动。** 下面「锁定 id 清单」里带【锁】标记的 id
```

**自查结果（grep 全文，按评审要求"顺带查一遍还有没有别的「几、某某」式编号引用"）**：

```bash
grep -n '「[一二三四五六七八九十][、][^」]*」' tools/polish_context.py tools/polish_amplify.py
```
修复前只命中 `polish_context.py:99`（上面这一处），修复后归零。另外用更宽的模式
`第[一二三四五六七八九十][节章]|[节章][一二三四五六七八九十]|「[一二三四五六七八九十]」`
扫过一遍，唯一命中是 `polish_context.py:204` 的一行**开发者注释**（"它在那边确实是
第三节"），说的是 `build_context.py` 自己的编号体系（该文件里"三"确实是第三节，注释本身
准确），不进入渲染输出，不需要改。

**发现但明确不在本轮修复范围内的同类残留（如实记录，供协调者决定是否需要另开任务）**：
自查过程中顺带看了 `tools/polish_amplify.py::scan_prompt()`——它自己独立维护一套顶层编号
（`AMPLIFY_PREAMBLE` 的"## 零、本轮说明"→`digest`前"## 一、裁决意图纪要"→
`_build_panorama()` 的"## 二、全 SEG 四桶结果全景"→"## 三、锁定 id 清单"→
"## 四、术语/风格/口调/锚点"→"## 五、输出契约"），**同样整段复用
`build_context._render_anchors()`**，其硬编码"## 三、锚点行"标题嵌在"## 四、术语..."
节内部，与该文档自己的"## 三、锁定 id 清单"重复出现"三"——这是**同一根因在另一个文件里
的一次独立发生**（不是本次两条 Finding 覆盖的范围：Finding A 明确说的是
`TASK_INSTRUCTIONS` 里的散文交叉引用，不是 `polish_amplify.py` 的顶层编号本身）。协调者的
指示是"1. 修 A 和 B"，两条都限定在 `polish_context.py`/`polishlib.py`，故本轮**未touch**
`polish_amplify.py`——只如实记录在这里，留给协调者判断是否要开一个后续任务处理。

**新测试**（`tests/test_polish_context.py::test_render_has_no_stale_numbered_cross_references`）：
用通用正则 `r"「[一二三四五六七八九十]+、[^」]*」"` 扫整份渲染文本，断言不出现任何形如
"「X、...」"的编号式引用——不满足于只测已知出过问题的那一处，覆盖"以后又在别的常量里
引入同类残留"这个泛化场景，这正是评审指出的盲点（此前两条测试都只断言标题层面，没有
覆盖正文散文引用）。

**变异实测**（用 Edit 改回旧文案、跑测试、再用 Edit 改回来，全程未用任何 git 命令）：
```
# 改回：1. **锁定 id 绝对不能动。** 下面「二、锁定 id 清单」里带【锁】标记的 id
uv run pytest tests/test_polish_context.py::test_render_has_no_stale_numbered_cross_references -q
FAILED — AssertionError: 发现指向带编号旧标题的散文引用：['「二、锁定 id 清单」']
# 用 Edit 改回"锁定 id 清单"（无编号）后重跑：
1 passed
```

### 8.2 Finding B：`is_ignored_extra` 的目录名判据缝隙

**问题**：`IGNORE_DIR_NAMES & set(p.parts)` 对路径的**全部**段一视同仁，包括 `p` 自己的
basename。评审实测构造：`frozen/__pycache__`——一个**普通文件**（无扩展名，文件名恰好
就叫 `__pycache__`）——会被判定为"落在 `__pycache__` 目录之下"而错误忽略。这道闸存在的
唯一意义就是"不能宽到藏住真文件"，这条缝隙虽然现实中不会撞上真正的 glossary/notes 文件名，
但原则上不该留着。

**修法**：目录名判据只看祖先路径段（`p.parts[:-1]`），不含 `p` 自己的 basename：
```python
# 修复前
if IGNORE_DIR_NAMES & set(p.parts):
    return True
# 修复后
if IGNORE_DIR_NAMES & set(p.parts[:-1]):
    return True
```
basename 层面的判定继续单独交给 `IGNORE_BASENAMES`（`.DS_Store`/`Thumbs.db`）与
`IGNORE_SUFFIXES`（`.pyc`）两条规则，互不影响——真正落在 `__pycache__` 目录之下的文件
（哪怕不是 `.pyc` 后缀）仍然被正确忽略，只是"文件自己就叫这个名字"这一种情况不再被目录
判据顺带放过。

**新测试**（`tests/test_polishlib.py::test_is_ignored_extra_directory_match_excludes_own_basename`）：
```python
assert not pl.is_ignored_extra(Path("/a/b/__pycache__"))       # 文件自身叫这个名字
assert not pl.is_ignored_extra(Path("frozen/__pycache__"))
assert pl.is_ignored_extra(Path("/a/b/__pycache__/somefile.txt"))  # 真落在该目录下，仍应忽略
```

**变异实测**（用 Edit 改回 `set(p.parts)`、跑测试、再用 Edit 改回来）：
```
# 改回：if IGNORE_DIR_NAMES & set(p.parts): return True
uv run pytest tests/test_polishlib.py::test_is_ignored_extra_directory_match_excludes_own_basename -q
FAILED — AssertionError: assert not True
  where True = is_ignored_extra(PosixPath('/a/b/__pycache__'))
# 用 Edit 改回 set(p.parts[:-1]) 后重跑：
1 passed
```

### 8.3 关于 `git checkout --` 事件

协调者已独立核实：其他会话未提交的改动完好（`data/api_ledger.jsonl` 的 74 行新增仍在），
生产数据零改动，未造成实际损失；同时明确指出**该命令类操作在本项目里一律禁止**（无论是否
限定单文件），本轮修复过程**全程未使用任何 git 回滚类命令**——两处变异验证都改用"Edit
改坏 → 跑测试确认转红 → 立刻用同一个 Edit 调用把原文改回来"的方式核对，过程记录见 §8.1/
§8.2 的变异实测块。

### 8.4 测试输出

```bash
uv run pytest tests/test_polish_context.py tests/test_polishlib.py tests/test_polish_setup.py -q
# 45 passed（修复前）→ 47 passed（补测试后，含 2 条新增）

uv run pytest -q
# 702 passed（700 基线 + 2 条新增：test_render_has_no_stale_numbered_cross_references +
#   test_is_ignored_extra_directory_match_excludes_own_basename）
```

### 8.5 重新渲染 SEG-1 真实 prompt 并处理 `prompt_hash` 变化

`tools/polish_context.py` 的 `TASK_INSTRUCTIONS` 常量是**全 SEG 共享**的（每个 session 的
渲染输出都会整段嵌入它），Finding A 的修复因此会改变**全部四个 session**的 prompt 字节内容，
不只是被评审读到的 session 1。重新渲染全部四组并确认 `plan.json` 自动更新：

```bash
for n in 1 2 3 4; do
  uv run python tools/polish_context.py --seg seg1-s2 --session $n --out work/ctx/p4s1-s$n.md
done
```

`plan.json` 里四条记录的 `prompt_hash` 全部变化（`--session --out` 的 CLI 逻辑本身就是
"按 session 号替换旧记录"，属工具既有幂等设计，不需要额外手工干预）：

| session | 旧 hash（前 12 位） | 新 hash（前 12 位） |
|---|---|---|
| 1 | `a8f247cea72d` | `c78c88c613ff` |
| 2 | `5457fa37f4f1` | `63c6b096991e` |
| 3 | `a33cc073204a` | `d06e842ba382` |
| 4 | `c39bc9ee62f3` | `60ba1dc93534` |

**为什么这一步不能漏**（想清楚后确认无风险）：`polish_ingest.py` 的覆盖完整性检查依赖
`plan.json` 里记录的 `prompt_hash` 来反查某批所属会话（`_find_prompt_hash`），若不重渲染，
`plan.json` 里留着的会是修复前（含旧编号引用）那份文本的哈希——而 SEG-1 尚未点火、没有任何
`raw/<channel>/` 输出落盘，也没有任何 `candidates.*.jsonl`/`gates.*.json` 引用过旧哈希，
所以**这次更新没有任何下游数据需要跟着迁移**，是一次干净的覆盖。`manifest.json`
（`frozen/` 的逐文件哈希）完全不受影响——本轮修复只改了 `tools/polish_context.py`/
`tools/polishlib.py` 两个代码文件，没有触碰 `frozen/` 下任何一份文件，`git diff --stat
pilot/polish/seg1-s2/manifest.json` 为空可证。

重渲染后逐节复核 session 1（`work/ctx/p4s1-s1.md`）：
```bash
grep -n "锁定 id 清单\|「[一二三四五六七八九十]" work/ctx/p4s1-s1.md
```
只命中第 13 行"下面「锁定 id 清单」"（与第 48 行"## 锁定 id 清单"标题一致）与若干
**内容性**引用（如"三顿一行"这类绘本诗行结构描述、`voices/*.md` 各自独立的"1. 角色定位"
…"6. 特殊注意"局部编号——后者是每份口调表文件自己的既有体例，与 render() 自身的顶层编号
是两套互不相关的方案，本次修复范围不含它们，不构成残留）。`grep -n "^## "` 全文扫描确认
不再出现任何 `"## 三、"` 或 `"## <汉字数字>、"` 形态的顶层标题。

### 8.6 commit

```
0d0a4d8 fix: Task 11 评审修复轮 —— 章节交叉引用残留 + is_ignored_extra 目录判据缝隙
```

