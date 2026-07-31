# Task 8 报告：prompts 三件（真实全文入库）

## 产出

- `prompts/translator_cc.md`（87 行）
- `prompts/reviewer_cc.md`（53 行）
- `prompts/api_system.md`（62 行）
- commit `cc18365 feat: 翻译/评审/API 三份 prompt 模板`（3 files changed, 202 insertions(+)，`git add prompts/ && git commit` 未触碰任何既有文件）

## 我读了哪些真实文件、取了什么事实

- `CLAUDE.md`（本次系统提示内已含全文）——双层叙事/双层人名对照表、「ユウイチ其实是直哉」等世界观真相、`_n/_r`、`<漢字,かな>`、`【】○■≪≫≦≧` 控制码清单、`cBrStr` 24 字符硬折行的已知坑。用于三份 prompt 的世界观引用与控制码举例。
- `glossary/style.md`（51 行，全文读）——确认真实小节数为 **7 节**「##」（全知纪律/伏笔锚点与润色尺度/叙述声音/双层人名规则/称呼后缀默认表/控制码与格式/UI 与系统文本），而非任务描述里说的"8 个"——三份 prompt 里枚举小节名时按实际的 7 个写，没有沿用任务描述的错误计数。控制码与格式一节确认 ♪ 在 style.md 里也要求保留。
- `tools/check_batch.py`（92 行，全文读，逐条核对）——见下方"硬规则对照表"。
- `glossary/speakers.json`（全文读，49 条映射）——确认含 "私"→"我"、"教師"→"教师" 等非专名映射；确认 `check_batch.check()` 在 `speakers` 字典非空时只检查 jp 侧**有**【】前缀的行，且只在该说话人**在表里**才硬性比对（表外说话人不被 R2b 拦，但仍要求译者自行给出合理译名——三份文件都写明了这个"表未覆盖不代表可以乱译"的边界）。
- `skeleton/anchors.yaml`（全文读；`grep -c '^\s*- id:'` = **120**，与 CLAUDE.md 所述一致）——取用文件头纪律说明（锚点 zh 逐字沿用）；用其中 `chapter: s0f, id: 6067` 这一条真实锚点（jp『【私】「どうぞ。……遅かったわね。道、混んでた？」』/ zh『【我】「请进。……来晚了呀，路上堵车？」」』）做三份文件共用的贯穿示例——同时验证了它确实落在 `work/ctx/batch_1/source.jsonl` 里（第 8 行）、且用 `speakers.json` 的 "私"→"我" 能对上，一个例子同时坐实了"锚点逐字沿用"和"【】按 speakers.json"两条规则。
- `work/ctx/batch_1/context.md`（1129 行，分页读全）+ `source.jsonl`（339 行）+ `manifest.json`——确认「三件」= context.md/source.jsonl/manifest.json；确认 context.md 五节结构、第四节确实内嵌了 `active.json`（JSON dump）与 `style.md`**全文**（这一点直接决定了 api_system.md 里"你没有文件系统权限，但 style.md 全文已经在 user 消息里"这一段的写法）；确认第四节**没有**内嵌 `speakers.json`——据此在 api_system.md 里专门写了一段"已知缺口，如实告知"，没有假装 API 后端能拿到这张表。
- `tools/build_context.py`（全文读）——确认 `--baseline` 四档 `none/ref/revise/judge`、`none` 档 source 行无 `base` 字段、其余档有；确认 `SECTION5="## 五、本批任务"` 的渲染格式 `[id] jp` / `base: …`。据此设计 api_system.md 的 none/revise 两档输出契约，并如实注明 `ref`/`judge` 暂不覆盖（没有编造这两档的行为）。
- `tools/append_forward.py`、`tools/pipelib.py`——确认 `data/forward.jsonl` 真实存在于设计中但**当前仓库尚未生成**（`task-7-report.md` 原话："真实仓库尚无 `data/forward.jsonl`（未开翻）"）；确认 `append_jsonl`/写入格式；确认 append_forward 对 draft 的 id 原样透传、不做类型校验——这是 translator_cc.md 里强调"id 类型錯了没人替你纠正"的依据。
- `data/ledger.jsonl`、`data/ledger_extra.jsonl`（各读样例行）——确认 `ledger.jsonl` 每行有 `file` 字段（如 `snr_common`），对应 `analysis/text_digest/<file>.txt`；确认 extra 车道 id 形如 `"plotTitle:1"`、`"snr_crd_100:35"` 等字符串。
- `analysis/text_digest/`、`png/event/`、`png/pose/` 目录实际列出——确认摘要文件命名与立绘文件命名（`po1_aya_*`）真实存在，避免编造查找路径。
- `glossary/voices/`（`ls` + `wc -l`）——确认真实 7 个文件名：`ayano_real.md ayano_story.md chiaki.md naoya.md sakura.md yuichi.md yukari.md`；并逐一用 `anchors.yaml` 里的 `recall` 字段核对每个文件对应哪个角色（如 `yuichi.md §3` 对应 id 7656 的"緻密な計算"梗），写进 reviewer_cc.md 的口调表偏离示例时用的就是这条真实复现句。
- `skeleton/cards.zh.yaml`（`python3 -c "import yaml; ..."`）——确认真实卡数 **196**（不是 CLAUDE.md 目录树描述里容易读错的"197"，197 是 `cards.jp/` 的转写数）；translator_cc.md 人设段按 196 写。
- `.superpowers/sdd/2026-07-30-p1b-linearize-context/task-7/9/10-brief.md` + `progress.md`——确认 `tools/gen_plan.py` 尚未实现（Task 9 还没做），translator_cc.md 提到它时明确标"未来是"，不是当前可调用的工具。
- `work/`、`.gitignore`（`grep work .gitignore`）——确认整个 `work/` 目录都被 gitignore，`work/out/` 在全新 checkout 上可能不存在，据此在 translator_cc.md / reviewer_cc.md 的输出契约里都加了 `mkdir -p work/out`。

## brief 要点 → 落点对照表

### translator_cc.md

| brief 要点 | 落在哪一节 |
|---|---|
| 译者人设=本作骨架译者 | "你是谁"（引用 skeleton/cards.zh 196 卡 + anchors.yaml 120 条锚点，明确"同一人设同一笔感"） |
| 先读 work/ctx/batch_N 三件 | "开工前：读三件材料"（context.md 五节逐节说明 / source.jsonl / manifest.json） |
| 全知纪律引用 style.md | "全知纪律"（点路径+小节名，不复述规则原文，仅留一句预防针并明确"不要靠转述套用"） |
| 控制码硬规则 | "控制码规则"——**见下方硬规则对照表，_n/_r 被改判为软规则**，ruby/【】/≪≫≦≧○■ 三条按硬规则写 |
| 输出 draft.jsonl 行 {"id","zh"} 且 id 集合=source | "输出契约"（含 mkdir -p、真实示例行、id 类型不转型的告诫） |
| 允许用工具（rg forward.jsonl / text_digest / CG立绘） | "可以用的工具" 三条逐一对应 |
| 返回前自跑 check_batch 到 PASS | "交付前自检"（含真实 CLI、真实终端输出格式、check.json 结构、pass.json 哈希锁定说明） |
| 禁止 git commit | "不要做的事" 第一条 |
| 术语提案写 data/notes/<chapter>.md 尾部 | "术语提案"（含 `<chapter>` 取值来源：`data/batches.jsonl` 对应行的 chapter 字段） |

### reviewer_cc.md

| brief 要点 | 落在哪一节 |
|---|---|
| 对照 source jp 逐行挑刺：术语漂移/剧透措辞/控制码/口调表偏离 | "你是谁" 总述 + "四类挑刺点" 逐条展开（每条都点了具体对照对象：active.json+anchors.yaml / style.md全知纪律+CLAUDE.md剧情核心 / 硬软规则同下节 / voices 7 份口调表） |
| 输出 {"id","verdict":"keep\|fix","zh":…,"reason":…} 到 batch_N.review.jsonl | "输出契约"（真实示例两行：一条 keep 命中锚点、一条 fix 示意控制码丢失，均明确标注示例性质） |
| 不改 draft 本体 | "不要做的事" 第一条 |

### api_system.md

| brief 要点 | 落在哪一节 |
|---|---|
| revise 档按 keep/fix 输出 | "按 baseline 分两种输出模式" 的 revise 小节 |
| none 档全量输出 | 同节的 none 小节 |
| JSON lines 格式契约 | "JSON Lines 格式契约"（纯文本回复、UTF-8、id 集合完全对应、id 类型不转型、顺序无关但不可重复） |
| 控制码规则同上 | "控制码规则"，与另外两份分类完全一致，并额外处理了"API 无工具、speakers.json 未内嵌"这个真实缺口 |

### 补充要求对照

| 补充要求 | 落实情况 |
|---|---|
| 三份都用中文，保留必须原样的日/英术语 | 三份全中文撰写；【】○■≪≫≦≧、True Color、Happy End、片假名人名、`forward.jsonl` 等原样保留 |
| 开头一行「本文件是 P2 试点的调参对象，首版不追求完美」 | 三份开头逐字含此句（`grep` 已核对，见下方自评审） |
| id 集合契约写死 | 三份输出契约里都单独成句强调"完全相同，不缺不多不重复" |
| extra 车道 id 是字符串，原样回写 | 三份都在输出契约/格式契约里提醒，并各给一个 `"plotTitle:1"` 例子 |
| work/out/ 可能不存在，先建 | translator_cc.md、reviewer_cc.md 均写 `mkdir -p work/out`；**api_system.md 故意不写**——该受众是无文件系统权限的纯文本 API 模型，写"先 mkdir"对它是无意义指令，已在文件开头"你没有文件系统或工具调用权限"一段解释清楚，落盘由未来的调用方脚本负责 |
| 不塞 style.md 全文，只引用路径 | 三份都只点路径+小节名，没有整段照抄；`grep` 校验过几条 style.md 独有的长句（如"ね／よ／わね"「身体词、动作词按中文惯用搭配取词」）不在三份文件里出现 |

## 硬规则与 `tools/check_batch.py` 的逐条对照（本任务最容易出错、也是自查重点的一处）

逐行读了 `check_batch.py` 的 `check()` 函数（第 24–58 行）后确认：

| 规则 | 代码位置 | 触发条件 | 是否阻断（进 hard） | 三份文件里的分类 |
|---|---|---|---|---|
| R1 id 集合 | 28–31 行 | `set(src)!=set(drf)` 或去重后行数不等 | 阻断，且短路后续所有检查 | 硬规则 |
| R2a ruby 良构 | 34–35 行（`_ruby_ok`） | 剔除良构 `<a,b>` 后仍有孤立 `<`/`>` | 阻断 | 硬规则 |
| R2b 【】说话人 | 36–44 行 | jp 有【名】且该名在 speakers.json 表里、zh 没对上 | 阻断 | 硬规则 |
| R2c 符号丢失 | 45–47 行（`MARKS="≪≫≦≧○■"`，共 6 个字符） | jp 含某符号而 zh 不含 | 阻断 | 硬规则 |
| W1 断行差 | 49–50 行 | `abs(_n/_r 计数差) >= 2` | **不阻断**，只进 warn | **软规则** |
| W2 术语漂移 | 51–55 行 | active.json 定译词在 jp 出现、zh 未含译词 | 不阻断 | 软规则（reviewer 的"术语漂移"判断标准与之对齐，但 reviewer 的 verdict 是编辑判断，不等于机器 warn） |
| W3 行宽 | 56 行 | zh 最长断行片段 > jp 最长片段×1.15（下限 10） | 不阻断 | 软规则 |

**关键纠偏**：orchestrator 给出的任务描述原文把 `_n/_r` 总量差和 ruby/【】/≪≫≦≧○■ 并列写在同一句"控制码硬规则"里——但读代码后确认 `_n/_r` 差值判定（W1）实际写在 `warn` 列表里，不影响 `hard`、不阻断 PASS。三份文件都**没有照抄这句话**，而是按代码实测把 `_n/_r` 单独归入"软规则"一段，并在 translator_cc.md 里显式写"下面的分类是照 check_batch.py 源码逐条核对过的，不是凭印象写的"，避免评审时被当成"抄错类别"。另外确认 `MARKS` 常量本身只有 6 个符号、不含 style.md 额外要求的 ♪——三份文件都在 R2c 描述后加了一句"♪ style.md 要求保留但不在自动校验范围"的括注，既不夸大代码能力，也不漏掉 style.md 的真实要求。

代码里另一个容易漏读的分支：R2b 只在 jp **有**【】前缀时才检查，且只在该说话人**在** speakers.json 表里时才强制对齐——表外说话人不受机器检查约束。三份文件都把这个"表未覆盖≠可以乱译"的边界写清楚了（translator_cc.md 控制码规则一节的"注意"句、reviewer_cc.md 同段）。

## 自评审（发布前）

- **完整性**：brief 每条要点逐一核对，见上方两张对照表；四张"softrule/hardrule"来源交叉表额外核对过一遍代码。
- **纪律**：`grep` 核对过开头逐字句、id 集合契约句、extra 字符串提醒句均三份齐全；`grep` 反向核对过 style.md 里几句有辨识度的长句没有被整段复制进三份文件。三份文件里出现的每一个仓库路径都逐一核实过是否真实存在（`data/forward.jsonl`、`tools/gen_plan.py` 两个例外——均在文中明确标注"尚未生成/未来才有"，不是冒充现存）。
- **一致性**：三份文件的控制码分类（硬：ruby/【】/≪≫≦≧○■；软：_n_r/术语/行宽）逐字段比对过，互不矛盾；三份共用同一条真实锚点 id=6067 作为贯穿示例，jp/zh 文本三处完全一致（`grep -n "6067" prompts/*.md` 可核）。
- **质量/可执行性**：id 6067 示例是从 `anchors.yaml`+`source.jsonl` 双重验证过的真实数据，不是编造；`check_batch.py` 的真实 CLI 输出格式（含两个空格的 `PASS  warn=`）照抄源码字符串，避免子代理因为格式猜测错误而找不到判定依据。

## 遗留顾虑

1. **api_system.md 的 speakers.json 缺口是我在写作过程中发现的真实设计空白**（`build_context.py` 的 `_load()` 只嵌 `active.json`+`style.md`，没嵌 `speakers.json`），不是我杜撰的问题。目前给的应对是"退回一般规则 + 事后靠 check_batch R2b 兜底"，这只是权宜写法——如果 P2 真的要跑 api-A/api-B profile，更彻底的修法应该是让未来的 API 调用脚本在拼装 user 消息时把 `speakers.json` 也带上（或者改 `build_context.py` 内嵌它），但这超出了本任务"只新建 prompts/ 三个文件"的范围，没有动 `tools/`。留给后续任务或用户裁决。
2. **reviewer_cc.md 的 review.jsonl "id 集合=draft"约束是我类比 R1 外推出来的**，brief 原文没有对 reviewer 的输出显式提这条（只对 translator 的 draft 提了）。我认为不外推的话"没写的行到底是 keep 还是漏检"会有歧义，所以补了这条纪律，但这是我的设计判断，不是 brief 逐字要求，特此说明以便你复核是否认可。
3. `prompts/gen_plan.py` 派发译者/评审子代理时具体怎么把 batch 编号和这两份模板拼接成最终 prompt（是整份文件当 system prompt，还是摘录），本任务没有实现调用方，留给 Task 9。

---

## 修复轮 1（评审 2 条 Important）

commit `b0bb74e fix: prompts 三份修正 R2b 说话人边界描述与 api_system 的 baseline 判定信号`。

### Finding 1：【说话人】硬规则的描述超出了 R2b 的实际校验范围

再次核对 `tools/check_batch.py:36-44`：

```python
sm, dm = SPEAKER_RE.match(jp), SPEAKER_RE.match(zh)
if speakers:
    if sm:
        want = speakers.get(sm.group(1))
        if want is not None and (not dm or dm.group(1) != want):
            hard.append(...)          # 唯一真会拦的分支
elif bool(sm) != bool(dm):
    hard.append(...)                  # 结构对齐兜底——speakers 非空时永远走不到
```

`main()`（第 73-74 行）总是加载 `glossary/speakers.json`，该文件在本仓库真实存在 → `if speakers:` 恒真 → `elif` 分支死代码。真实校验范围收窄为**唯一一种**情形：jp 有【某人】、且"某人"在表里、且 zh 没对上。"jp 无【】却被 zh 加了""说话人不在表里"这两种情形，R2b 完全不检查。

三处改动，均为同一改法：保留规则本身（仍要求译者/评审/模型遵守），但把"会被拦下"限定到唯一真实生效的情形，另外两种情形改为明确标注"机器拦不到、靠自律"，与已有的 ♪ 符号、表外说话人两处诚实口径并列成同一风格。

**`prompts/translator_cc.md:41`**

- 改前："…；原文没有【】前缀的行，译文也别加。**注意**：某个说话人如果不在 `speakers.json` 表里，脚本不会替你把关这一条，但仍要给出合理、前后一致的译名。"（暗示"没有【】不该加"这条本身会被拦）
- 改后："…——**这是 R2b 真正会拦下的唯一情形**。原文没有【】前缀时译文也不要画蛇添足加上、说话人不在表里时也要给出合理、前后一致的译名——这两条规则依然要遵守，但**如实说明：check_batch 目前拦不到**。`glossary/speakers.json` 在本仓库真实存在，`check_batch` 的 `main()` 每次都会加载它，导致源码里"jp 无【】时比对 zh 是否也无【】"那条兜底分支（只在没有 speakers 表时才会走到）永远不可达；说话人不在表里时同样不会触发任何比对。两处都是机器管不到、纯靠自律的角落，不是脚本疏漏可以钻的空子。"

**`prompts/reviewer_cc.md:28`**

- 改前："…；原文没有【】的行也不该被加上。"
- 改后："…——**这是 check_batch 真正拦下的部分**。原文没有【】的行也不该被加上、说话人不在表里时也要给出合理一致的译名——这两条判断时依旧按硬规则来（发现了直接判 fix），但 check_batch **拦不到**：`glossary/speakers.json` 在本仓库恒存在，源码里对应的两条兜底分支因此永远走不到。抓这类机器测不出来的问题，正是评审存在的意义。"（顺带点出这正是"评审为什么需要存在"的正面理由，而不只是一条免责声明）

**`prompts/api_system.md:23`**（以及顺带修正的 `:11`）

- `:23` 改前："结构上，原文有【】前缀译文就要有，原文没有就不要加。"
- `:23` 改后："…这部分猜错了会被 R2b 拦下；原文没有【】前缀译文也不要画蛇添足加、说话人不在表里时也要给出合理一致的译名，这两条依然要遵守，但**如实告知：check_batch 拦不到**（`glossary/speakers.json` 在仓库里恒存在，源码对应的两条兜底分支因此永远不可达）——不要因为"反正机器测不出来"就放松。"
- 顺带发现并修的邻近问题：`:11`"已知缺口"段原本收尾一句"这条最终由 `tools/check_batch.py` 的 R2b 规则事后校验兜底"，把 R2b 的兜底能力说成覆盖了整段指引（含"生僻/泛称类标签给合理译名"那部分），与 Finding 1 核实到的真实校验范围矛盾——生僻/泛称类标签根本不在 R2b 检查范围内。改为："**这条兜底并不完整，如实说明**：`tools/check_batch.py` 的 R2b 只在"原文【某人】、且某人在 `speakers.json` 表里"时才会拦下猜错的译名——常见角色名走的是这条，猜错了会被拦；生僻/泛称类标签不在表里、或原文本来就没有【】前缀，这两种情形 R2b 都不检查，猜错了、加错了都不会被拦，全靠你自己一致、克制。"（这处不在评审逐字点名的行号里，是我顺着 Finding 1 的代码分析在同一文件里发现的直接连带问题，一并修掉，避免修完 `:23` 后 `:11` 仍留一句自相矛盾的话）

### Finding 2：`api_system.md` 用「有无 `base:` 行」判定 revise 档，信号对 ref/judge 同样成立

重新核对 `tools/build_context.py:73` 与 `:81-90`：

```python
tail = [..., f"\n{SECTION5}（baseline={baseline}）"]   # 第五节标题——无条件带上实际 baseline 值
...
if baseline != "none" and i in env["zh"]:
    row["base"] = env["zh"][i]
...
tail.append(f"[{i}] {row['jp']}" +
            (f"\n    base: {row.get('base','')}" if baseline != "none" else ""))
```

确认了两件事：① `base:` 出现条件是 `baseline != "none"`，对 `ref`/`revise`/`judge` 三档一视同仁，原文用它判定"是不是 revise 档"确实不完备；② 但同时发现了一个比 Finding 1 讨论范围更好的解法——**第五节标题本身就无条件把 `baseline` 的实际值明文写出来**（如 `## 五、本批任务（baseline=revise）`），这个信号是精确的、不需要靠 `base:` 字段反推。

于是没有照搬 Finding 1 建议的"未显式声明时降级为 none 档 + 输出前一行 prose 声明"（那样会与文件后面「JSON Lines 格式契约」一节"整个回复就是 JSON Lines、不要输出任何解释"的强约束打架），而是把判定信号换成标题里的 `baseline=X`，把原本相隔 12 行的检测逻辑（`:42` 附近）与免责声明（`:54` 的独立斜体段）合并成「按 baseline 分两种输出模式」小节开头的一个统一列表：

```
**先看 context.md「五、本批任务」这一节的标题怎么写**——`build_context.py` 会把实际的 baseline 值
直接写进标题文字，例如 `## 五、本批任务（baseline=none）` 或 `（baseline=revise）`。**这是判断走哪条
协议的唯一依据**，不要靠"这一行有没有带 `base:` "去反推：`base:` 字段只说明 baseline 不是 `none`，
`ref`/`revise`/`judge` 三档都会带它，光看这个分不出具体是哪一档。

- **`baseline=none`** → 全量翻译协议（见下）。
- **`baseline=revise`** → keep/fix 协议（见下）。
- **`baseline=ref` 或 `baseline=judge`**：`build_context.py` 定义了这两档（同样会带 `base:`），但本指令
  目前没有单独给它们写协议——**统一按 keep/fix 协议处理**（都是"已有候选译文，你来把关"的场景，形状相
  同）。这是当前的占位处理，不是确认过的语义等同；等 P2 试点真正用到 ref/judge 时再回来拆分、校准。
- 防御性地写一句（正常不会发生）：`build_context.py` 无条件渲染这行标题，如果 user 消息里连它都没有，
  按全量翻译协议处理，不要猜。
```

后续 `none`/`revise` 两条协议正文内容不变，只是标题从"只有 `[id] jp`，没有 `base:` 行 → `none` 档…"/"每行还带一个 `base: ……` → `revise` 档…"分别改成"`none` 档，全量翻译"/"`revise`（以及占位处理的 `ref`/`judge`），按 keep/fix 输出"，与新的判定列表衔接，不再各自重复一遍判定条件。原本文末的独立免责斜体段落已删除（内容并入上面的列表，不再有"隔着十几行"的问题）。

### 验收结果

- `uv run pytest -q`：**90 passed**（本轮只改了 `prompts/*.md`，未碰 `tools/`/`tests/`/`config/`/`data/`/`skeleton/`/`glossary/`/`CLAUDE.md`/`work/`，`git status --short` 在提交前只显示三份 prompt 文件被修改）。
- 三份文件表述互相核对：`grep -n "拦不到\|永远不可达\|永远走不到" prompts/*.md` 三处命中、口径一致（均落在"speakers.json 恒存在→ main() 加载→ elif 分支不可达"这条同一推理链上）；`grep -n "没有【"` 确认没有遗留未加限定语的旧措辞。
- 行数变化：`translator_cc.md` 87 行（不变，同段内改写）；`reviewer_cc.md` 53 行（不变，同段内改写）；`api_system.md` 62→65 行（Finding 2 的判定列表展开新增 3 行，净增）。
- 4 条 Minor（style.md 四条硬约束的对应关系 / revise 与 review.jsonl 字段集差异未注明缘由 / `ledger_extra.jsonl` 也带 file 字段未提 / W3 未提 `max(10, …)` 下限）已由控制器记入台账、明确不进本修复轮，本轮未改动，如需要请另行指示。

### 修复轮遗留说明

- 评审同时指出：Finding 1 暴露的其实是 `tools/check_batch.py` 自身的一处缺陷（R2b 的结构对齐分支因为 `speakers.json` 恒非空而永远是死代码，"jp 无【】却被 zh 加了【某人】"这一类真实缺陷目前没有任何自动化机制拦截）。这超出本任务"只新建 prompts/ 三个文件、不动 tools/"的范围，我没有改 `check_batch.py`，只在 prompts 里如实反映了这个限制；该缺陷本身是否要开新任务修复，留给用户/控制器裁决。
