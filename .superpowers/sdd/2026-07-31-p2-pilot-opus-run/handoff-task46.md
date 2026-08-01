# Handoff：P2 试点 Task 46（人工评审 gate）本地续做

> 云端会话已于 2026-08-01 结束，全部工作已 push 到 `claude/second-novel-p2-pilot-u7mf7n`（HEAD `8cad4a8`，领先 main 77 个 commit，其中 36 个 `data:` 译文入线 commit）。
> 本文件是给下一个会话的交接提示词，可整段粘贴。

---

## 交接提示词（粘贴以下全部内容）

接手《セカンドノベル》汉化项目 P2 试点的**收尾评审**。上一段（云端会话）已把 opus 车道 batch 1–35 全部译完入线，现在要做的是 `docs/superpowers/plans/translate-pilot-opus.md` 的 **Task 46 Step 2：人工评审 gate**，以及试点结束后才允许进行的术语裁决。

### 先读三份材料（按顺序，不要跳）

1. `docs/superpowers/reports/2026-08-01-p2-pilot-report.md` —— 试点执行报告。**§1 边界声明、§8 待裁决项、§10 方法论观察**三节是本次工作的直接输入。
2. `.superpowers/sdd/2026-07-31-p2-pilot-opus-run/progress.md` —— 逐批执行台账（含 13 条缺陷 F1–F13、每批细节、所有复核结论）。**它是权威进度记录**；计划文件里的 markdown 复选框**没有逐个勾选**，不要拿复选框判断进度。
3. `docs/superpowers/specs/2026-07-31-p2-pilot-design.md` —— 试点设计，尤其 §6（评分与对照）与 §8（产出物与验收）。

### 环境重建（本地首次接手必做）

车道目录里只有 `lane.json`、`data/forward.jsonl`、`data/notes/*.md` 入库；`work/`、`skeleton/`、`glossary/` 冻结拷贝、符号链接都是 gitignore 的，需要本地重建：

```bash
git fetch origin claude/second-novel-p2-pilot-u7mf7n
git checkout claude/second-novel-p2-pilot-u7mf7n
uv sync
```

**重建车道前必须先做安全检查**（这一步不可省）：`lane_setup --force` 会覆盖 `pilot/lanes/pilot-manifest.json` 里已记录的冻结基准哈希。若仓库侧的 skeleton/glossary 在试点后被改过，强制重建会**销毁漂移证据**。先比对：

```bash
uv run python -c "
import sys, json, re; sys.path.insert(0,'.')
from tools.pipelib import REPO, sha256_file
from pathlib import Path
rec=json.load(open('pilot/lanes/pilot-manifest.json',encoding='utf-8'))['lanes']['opus']
gmax=max((int(re.search(r'v(\d+)',p.stem).group(1)),p) for p in (REPO/'glossary').glob('glossary.v*.yaml'))[1]
now={'batches':sha256_file(REPO/'data'/'batches.jsonl'),'cards_zh':sha256_file(REPO/'skeleton'/'cards.zh.yaml'),
     'anchors':sha256_file(REPO/'skeleton'/'anchors.yaml'),'active':sha256_file(REPO/'glossary'/'active.json'),
     'glossary_max':sha256_file(gmax)}
bad=[k for k,v in now.items() if v!=rec[k]]
print('全部一致，可安全 --force 重建' if not bad else f'**漂移** {bad} —— 停下来人工裁决，不要 --force')
"
```

**只有输出「全部一致」才执行重建**：

```bash
uv run python tools/lane_setup.py --lane opus  --model opus  --effort max  --append-model-id claude-opus-5  --force
uv run python tools/lane_setup.py --lane fable --model fable --effort high --append-model-id claude-fable-5 --force
uv run python tools/lane_setup.py --verify        # 期望：冻结校验：无漂移
```

两条车道都要建：`verify()` 的**跨车道一致性检查只在 ≥2 条健康车道时才运行**，只建一条时该检查静默跳过。

**预期的两处无害 diff**（不是问题，别去"修"）：
- `lane.json` 的 `lane_dir` 是绝对路径（云端 `/home/user/Zndnovel/...`，本地会变成你的路径）——缺陷 F1，纯文档字段，无生产代码读取。
- `pilot-manifest.json` 会被重写成 `lane_setup` 的紧凑格式（人工写入过 `collapse_thresholds` 时用的是缩进格式）——两个写入方格式不一致，已记为运维缺陷。

`work/ctx/` 可按需用 `build_context.py --repo pilot/lanes/opus --batch N` 确定性重生（云端实测重生后 `ctx_sha` 与原值逐字节相同）。`work/out/` 的中间产物无法重生，但已入线批次不再需要。

### Task 46 Step 2 要做什么

复核 35 个 `data: <chapter> 批次N 译文入线` commit（batch 1–35）。**计划明确规定不自动放行**——人工确认无误后本计划才算完成，之后才能对后续批次跑 `tools/gen_plan.py` 生成新计划。

评审时按 spec §6.5 的三栏 rubric：中文可读性 / 术语与口调一致性 / **全知纪律**（第三栏必须由知晓 s7f 全部真相的人专项反查代词与称呼）。

**已经机器化验过、不必重做的项**（结论见报告 §6）：`check_batch` 35/35 hard=0；锚点 total=32 verbatim=32 rate=1.0000；六个角色名的「译文含该名但原文无对应形式」扫描全部 0 行、`雪乃` 出现 0 次；44 条崩溃探测命中逐条过目后真崩溃 0 条。**人工评审应把精力放在机器测不到的地方**：语感、笑点是否成立、语域是否贴人物。

**重点抽读清单**（台账里逐条记了理由，评审时优先看这些）：
- 7296–7304：身份未明的【私】开场独白，刻意不给性别代词；说话人一旦确定可能需回调语气。
- 7486：把原文省略的宾语补成「好像是没约」，而"记不清放学后的约定"正是第 1 章机关（关键词卡 131），含混度本身是伏笔材料。
- 7535「放·学·后」：间隔号拆字模拟平假名降解，全部 4282 行里唯一用中点的一处。
- 7705「はうっ！」→「唔咕！」：挨打闷哼，7704–7706 是一个物理笑点，这声不像挨打则 7706 落空。
- 9304/9308「ユウイチ先生」：系统性偏离 `style.md` 默认表，见下方裁决项 4。
- 847–852：`お話`/`物語` 双关段，见裁决项 1。

### 试点结束后才允许做的：术语裁决

试点期 glossary 冻结，**216 条提案全部未裁决**，现在解冻。提案在 `pilot/lanes/opus/data/notes/{crd,s1s,s1f,s2s,s0f,sys}.md`（81/85/19/13/12/6 条）。译者自标最高优先级四条：扁桃体→杏仁核（假朋友）、寝癖（跨轨复现）、『あらすじ』を作成する（动词缺口）、メモ↔手帳（与现行定译冲突）。

裁决须走 `CLAUDE.md` 规定的版本化流程：新增 `glossary/glossary.v7.yaml` + 召回令，**不要直接改 `active.json` 或已入库的 `forward.jsonl`**（后者是 append-only 正向线）。若裁决结果要求回改已入线译文，走 `patches.jsonl` 机制。

**七项体例/术语裁决**（报告 §8 有完整证据，这里只列题）：

1. **`お話`/`物語` 合并规则的结构性反例**：v6 按你的裁决合并同译「故事」，但 847–852 的笑点正是由加里把 `お話があって` 听成日常义、直哉再更正为『物語』；严格合并会让直哉用「故事」更正「故事」。全线 51/55 守合并、4 处例外。建议加一条"双关/元指称语境局部豁免"。
2. **补 `『』` 的体例**：8192 `はい、いいえ`、8369 `お前？`、1994/1997/2030 裸 `彼女`。建议口径「仅限（a）原文近旁已用该体例、或（b）不补则中文不成句」。第三例有额外正当性——原文自己在 1996/2014 就写 `『彼女』`。
3. **"数字跟随原文"vs"同物同名"**：全库 `十円玉` 11 处 / `１０円玉` 1 处（仅 2378），后者按规则译成「１０日元硬币」，成为母题道具全书唯一异形。裁决时请一并写清该 style 规则的适用边界。
4. **`ユウイチさん`→「ユウイチ先生」**（9304/9308/7913/7791）：偏离 〜さん→〜同学 默认表。理由是 9308 需ユウイチ嫌弃该称呼"恶心"。若判回默认表，须连带回改 7791/7913。
5. **`モチーフ`**：17008「题材」vs 2033「原型」，后者是全篇诡计关键词，16208 还会再撞。
6. **8547/8707「手臂」vs 锚点母题「手」**：故事层救援是 s7f 结局的镜像，用词不同会削弱镜像。**需先定 s7f 兑现句的译法**（在本段之外）才能定夺。
7. **8144 汉字「由加里」闯入故事层**：`_s` 脚本里 342:2 的孤例（另一处 5696 在 e2s 属正常）。可能是有意的层次渗透（图书室＝现实层相拥场所），也可能是原作笔误，现照原样保留待判。

### 强烈建议顺手做的一件事（骨架侧）

**サクラ 全篇 696 条语音行里仅 2 处用汉字「彩野さん」**：8478（`s1s_300`）与 15775（`s6s_290`），其余 100 处均为片假名 `アヤノさん`。15775 明写「和**彩野さん**一起做『お話』很开心」——指现实中共同创作 True Color 的雪乃×彩野，即サクラ 越过故事层直呼现实层的彩野，作者用书写切换标记面具滑落。

**两处目前都不在 `anchors.yaml`**，全量翻译时必被不同批次的译者各自"统一"掉。建议成对补锚锁定。同类问题还有腕/手母题族（本段 12 条仅 3 条在表内）——见报告 §9 第 1 条「按母题成族补锚」。

### 不要做的事

- 不要动 `lua_scripts/`、`png/`、`analysis/`（只读）。
- 不要直接编辑 `pilot/lanes/*/data/forward.jsonl`（append-only 正向线，回改走 `patches.jsonl`）。
- 不要为了让 `check_batch`/`detect_collapse` 通过而放宽规则；13 条缺陷已记录在案，修工装是 P3 的事，**修完要重跑受影响批次的校验并在台账留痕**。
- 不要读 `pilot/lanes/fable/` 下的译文再回头改 opus 的译文——fable 只跑了 batch 1 作隔离验收对照，混看会污染尚未做的双车道对照结论。

### 如果打算补齐双车道对照

本次**未产出** spec §6.1 分层区分度统计、§6.5 三栏盲评 rubric——它们都依赖 fable 车道跑完同样 35 批。fable 现在只有 batch 1。补齐的话：

- 派发**只能**走 Workflow 的 `agent(prompt, {model: "fable", effort: "high"})`，`append_forward --model claude-fable-5`。Agent 工具设不了 reasoning effort，用它会静默回落到会话默认档并使该批次失去可比性。
- 跑完后 `uv run python tools/compare_lanes.py --lane-a pilot/lanes/opus --lane-b pilot/lanes/fable` 出分层统计与盲评材料。
- **锚点遵从率须同时记 total 与 rate**；两车道覆盖批次不同则分母不同，rate 不可直接横比。

### 一条影响评审方法的提醒

译者子代理的 `observations` 是**高价值的注意力指针，但其中的事实性断言必须复核**。云端会话逐条核实了 13 项自述：**译文本体 13/13 正确**，但理由错了 3 次、自责过严 3 次。若照单执行这些自评，至少会在三处**劣化**译文：给同名诡计关键句 716 加进原文没有的推测语气、撤销冻结卡 128 tr_note 的明文指令、抹平原文自带的语域切换。台账已逐条记了复核结论，评审时可直接跳过已判定的。
