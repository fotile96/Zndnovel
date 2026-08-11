"""P4 润色 pass：大批划分（长对话双帽）+ prompt 拼接。

上游 `tools/polish_setup.py` 已把一个 SEG 的全部输入冻结进
`pilot/polish/<label>/frozen/`（source/opus/locked/glossary/notes/rulings）。
本模块只做两件事：

1. `plan(label)`：把该段的批号区间按**长对话双帽**（≤session_size 批 /
   ≤session_lines 行，沿用 P3 `session_size`/`session_lines` 阈值，见
   `config/polish.yaml`）贪心切成会话组——SEG-1（b36–62）在 opus 时代是
   逐批跑的，这里补上会话分组，减少执行模型的往返次数。
2. `render(label, session_no)`：把一个会话组渲染成执行模型（fable/deepseek
   等）要读的完整 prompt——任务说明（润色契约）+ 锁定 id 清单 + frozen/
   glossary 全套（术语/风格/口调/锚点/语感细则）+ 逐批正文（jp/现行 opus
   译文对照）+ 输出契约。

**只读 frozen/，绝不读仓库里的活 glossary**——`pilot/polish/<label>/frozen/`
是该 SEG 润色输入的唯一真相源（`polish_setup.setup()` 已把术语/风格/口调/
锚点/notes 全部拷贝进冻结面并记进 manifest.json 的逐文件哈希）；活仓库的
`glossary/`、`skeleton/anchors.yaml` 之后如何演进，都不该影响一个已冻结
SEG 的润色 prompt——否则同一个 SEG 在不同时间渲染出的 prompt 会互相漂移，
复现与追责都无从谈起。

`repo` 参数化：与 `polish_setup._dir_for` 同样的理由——`polishlib.seg_dir()`
硬编码用 `pipelib.REPO`（真实仓库根），不接受覆盖；本模块另起 `_dir_for`，
只在 repo 落空时才退化到该默认路径逻辑，使 `plan()`/`render()`/CLI 都能被
tmp_path 造的替身仓库完全接管（测试要求：不得在单测里写进真实仓库的
`pilot/polish/`）。
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_context import _render_anchors, _render_voices
from tools.pipelib import REPO, dumps, read_jsonl
from tools.polishlib import CFG, demote_anchors_heading


def _dir_for(label, repo) -> Path:
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def plan(label, session_lines=None, session_size=None, repo=None) -> list:
    """按批号出现顺序，把该 SEG 的批次贪心切成会话组。

    双帽：累计行数超过 session_lines，或会话内批数超过 session_size，二者
    任一触发即收组、另起一组（`>` 触发、`==` 视为未超限——沿用 P3 的
    "≤" 语义）。批次的行数按 `frozen/source.jsonl` 里该批次的 id 数统计
    （该文件本身就是 `data/batches.jsonl` 按段表批号区间收集来的 id 全集，
    保留了批次出现顺序与批内原序）。

    单个批次自身即超过任一帽的极端情形（真实语料里 27 批×~20 行/批不会
    出现，但防御性处理）：该批次仍会被独立放进一个会话——不会因为"放不
    进任何一组"而丢批或死循环。
    """
    session_lines = CFG["session_lines"] if session_lines is None else session_lines
    session_size = CFG["session_size"] if session_size is None else session_size

    d = _dir_for(label, repo)
    rows = read_jsonl(d / "frozen" / "source.jsonl")

    order = []
    lines_by_batch = {}
    for r in rows:
        b = r["batch"]
        if b not in lines_by_batch:
            lines_by_batch[b] = 0
            order.append(b)
        lines_by_batch[b] += 1

    sessions = []
    cur_batches, cur_lines = [], 0
    for b in order:
        n = lines_by_batch[b]
        if cur_batches and (cur_lines + n > session_lines or len(cur_batches) + 1 > session_size):
            sessions.append({"session": len(sessions) + 1, "batches": cur_batches, "lines": cur_lines})
            cur_batches, cur_lines = [], 0
        cur_batches.append(b)
        cur_lines += n
    if cur_batches:
        sessions.append({"session": len(sessions) + 1, "batches": cur_batches, "lines": cur_lines})
    return sessions


TASK_INSTRUCTIONS = """\
## 任务说明（润色契约）

你正在给《セカンドノベル 〜彼女の夏、15分の記憶〜》官方中文本地化做**润色
pass**——不是从头翻译。下面每一行的「opus zh」都已经是可用译文（来自本项目
此前的翻译轨），你的工作是让它读起来更像**汉语母语者写的**，尤其是对白要像
当代汉语口语。总纲只有一句话：**读出声，别扭就改，顺口就留着。**判断细则见
下方整篇嵌入的 `polish.md`（汉语母语感细则）；它与 `style.md`（对/错、
术语、控制码、全知纪律）分工不同——**两者冲突时以 `style.md` 为准**。

**强制约束（不可协商，不是风格建议）：**

1. **硬锁 id 绝对不能动。** 下面「硬锁 id 清单」里带【硬锁】标记的 id是
   这个 SEG 冻结时点已经有人裁 patch 定过的行——这里把它们的现行译文
   列出来只是为了让你读懂上下文——**你产出的输出文件里绝不能出现这些 id
   对应的行**，哪怕你觉得"一字不改也该确认一下"也不行。
2. **软锁 id 可以斟酌，但改动门槛更高。** 下面「软锁 id 清单」里带
   【软锁】标记的 id 来自 `anchors.yaml` 锚点定译——这是翻译轨结束时的
   认知，不是不可动摇的铁律，润色阶段允许再议。它们和普通行一样**必须**
   在你的输出里各占一行：认为不用改，`zh` 逐字照抄 opus 即可，跟普通行
   同等对待；如果你确实认为这一行现在读起来别扭、值得改，**必须**把
   `adjudicate` 设为 `true`，并在 `note` 里写清楚你为什么觉得这处锚点
   值得再议——**不写理由的改动会被机械判死**，不会静默入库。
3. **术语表（active.json）、角色口调表（voices/*.md）、锚点定译对照都是
   强制性的**，不是参考——命中锚点的行、术语表里出现的词、角色专属的
   语气，一律按给定的走，不得凭个人语感覆盖。
4. **判断"这行不用改"本身就是合法结论**：认为不需要润色的行，`zh` 字段
   必须**逐字**照抄给你的 opus 现行译文，不要为了"看起来有产出"硬改。
5. **控制码原样保留**：`_n`、`_r`、`<漢字,かな>` 这类 ruby 注音、
   `≪…≫`、`≦…≧`、`【…】`、行首 `○`/`■`，一律不得增删或挪位。
6. **片假名角色名与汉字角色名的区分是剧情机关**（【アヤノ】=故事内角色 /
   【彩野】=现实人物，其余角色同理），润色时不得混用、不得替换掉这层
   区分。

**`score` 字段语义**：0–100 整数，**只用于同一批次内部按改动幅度/把握
程度排序**，**不是入库阈值，也不是质量认证**——下游会拿它做抽检与排序
参考，不会因为分数高低直接决定这一行进不进库。给分时不必纠结"够不够
格"，能反映"这处改动我有多大把握"即可；判断这行不用动，同样要给分
（分数可以给高，表示"我确认这行没问题"）。

**`adjudicate: true` 时 `zh` 该放什么**：放**你认为更好的那一版建议稿**
（可以是你想改成的样子，也可以是"我觉得不该改但按规则我不确定"时维持
opus 不变的样子），不要为了"避免出错"就机械照抄 opus 敷衍了事——opus
原文本来就已经在 prompt 里给裁决者对照，你给出的是你的判断依据，裁决者
会连同 `note` 一起参照决定最终怎么定，不是要你"猜哪个安全就抄哪个"。

**什么时候必须显式 `adjudicate: true`**：

- 你认为某处**不该**按语感细则改，或语感细则与 `style.md`/术语表/口调表/
  锚点对照之间有冲突；
- 涉及片假名/汉字人名区分、可能触及"复现句族"（同一句式反复出现、疑似
  已入 anchors 但你不确定）——你判断不了到底该不该动的情形；
- 涉及双层叙事真相（现实层/故事层）的措辞，你担心润色会改变信息量或
  提前泄露伏笔；
- **软锁 id（见上面第 2 条）任何改动**，无一例外；
- **你怀疑这一行本身就是错译或错字**（不是"读着别扭"，而是"这句翻错了/
  打错字了"）——润色契约本身假定 opus 是可用译文、只管母语感，你不负责
  校对，但真撞上明显的错译/错字时不能视而不见，也不该自己动手改判定：
  把 `adjudicate` 设为 `true`，`note` 里写清楚"疑似错译/错字"以及具体
  在哪、为什么这么判断，交给裁决者核实。

出现以上情形，把该行 `adjudicate` 设为 `true`，并在 `note` 里写清楚
你犹豫的具体理由——**不要自己下判断硬改或硬不改**。普通的"顺手把量词/
语序/连词理顺"不需要 `adjudicate: true`，直接给出润色稿即可。
"""

OUTPUT_CONTRACT_HEADER = """\
本会话每个批次各产出一个 JSONL 文件，放在 `raw/<channel>/` 目录下
（`<channel>` 由实际执行你的模型/车道决定，如 `fable`/`deepseek`）；文件名
按批号命名，本会话需要产出的具体文件名见本节末尾列表。每个文件里：

- 批内**每个非硬锁 id 恰好一行**——不多不少，不得合并，不得跳过。**软锁
  id 也要出现一行**（像普通行一样：不改就照抄 opus，改了必须
  `adjudicate: true`）——只有硬锁 id 才是真正要排除的。
- 硬锁 id **绝对不能出现**在这个文件的任何一行里。
- 每行是一个 JSON 对象，字段：
  `{"id": <int>, "jp_tail": "<原文控制码剥离后末 8 字>", "zh": "<润色稿或原样抄 opus>",
  "score": <0-100 整数>, "note": "<可留空>", "adjudicate": <true/false>}`
- `jp_tail`：你回显用的核对回执（下游不会重新计算哈希核对你写的是哪一行，
  只靠这个尾串核对）——取该行原文剥离 `_n`/`_r`/ruby 注音（`<漢字,かな>`
  取前半段）后的**最后 8 个字符**。三条边界规则：
  ①原文剥离控制码后不足 8 字的，**取剥离后的全串**（不是报错，也不是
  补空格补齐）；
  ②行首 `【説話人】` 这类说话人前缀**算原文的一部分**，一并参与"剥离
  控制码"与"取末 8 字"，不要跳过它单独从台词正文算起；
  ③空格**算一个字符**，不要在计数或取尾串前先去掉空格。
- 不改的行：`zh` 逐字等于本会话给你的 opus 现行译文；`score`/`note` 仍要
  给（比如给高分表示"我确认这行不用动"）。

本会话需要产出的文件：
"""


def _frozen_blocks(fz: Path) -> list:
    """冻结面里"每一份 prompt 都该带的那几节"：术语表 / style.md / polish.md
    语感细则 / 口调表 / 锚点行 / 章节纪要 / 裁决与前序纪要。

    抽成共享 helper 是 `render_calib()`（最终评审 I9）的前提——校准批 prompt
    必须与生产 prompt **同构**，否则那场"准入小考"考的就不是生产行为，而它的
    产物直接决定该通道有没有免检权。同构靠共用同一段代码保证，不靠两处各自
    维护一份长得差不多的拼接。
    """
    active = json.loads((fz / "glossary" / "active.json").read_text(encoding="utf-8"))
    style = (fz / "glossary" / "style.md").read_text(encoding="utf-8")
    polish_md = (fz / "glossary" / "polish.md").read_text(encoding="utf-8")
    voices = _render_voices(fz / "glossary" / "voices")
    anchors = _render_anchors(fz / "glossary" / "anchors.yaml")

    out = ["\n## 术语 / 风格 / 口调 / 锚点（frozen 冻结面，强制遵守）",
           "### active.json（术语表）",
           json.dumps(active, ensure_ascii=False),
           "\n### style.md（对/错标准，与下方语感细则冲突时以此为准）",
           style,
           "\n### polish.md（汉语母语感细则）",
           polish_md]
    if voices:
        out.append(voices)
    out.append(demote_anchors_heading(anchors))

    notes_dir = fz / "notes"
    if notes_dir.is_dir():
        notes_text = "".join(
            f"\n### 纪要：{p.stem}\n{p.read_text(encoding='utf-8')}\n"
            for p in sorted(notes_dir.glob("*.md")))
        if notes_text:
            out.append("\n## 章节纪要（背景参考）")
            out.append(notes_text)

    rulings_path = fz / "rulings.md"
    rulings_text = rulings_path.read_text(encoding="utf-8").strip() if rulings_path.exists() else ""
    if rulings_text:
        out.append("\n## 裁决与前序纪要（rulings.md；跨会话/跨段传递的用户裁定，"
                    "与下方语感细则/style.md 冲突时以此为准——它记录的是已经拍板的具体案例）")
        out.append(rulings_text)
    return out


CALIB_OUTPUT_CONTRACT = """\
本校准批只产出**一个** JSONL 文件（不分批），路径由派发方给定，约定为：

  `pilot/polish/<label>/calib/raw.<channel>.jsonl`

文件里：

- 校准批里**每个 id 恰好一行**——不多不少，不得合并，不得跳过。
- 每行是一个 JSON 对象，字段与生产批完全一致：
  `{"id": <int>, "jp_tail": "<原文控制码剥离后末 %d 字>", "zh": "<润色稿或原样抄 opus>",
  "score": <0-100 整数>, "note": "<可留空>", "adjudicate": <true/false>}`
- `jp_tail`：回执尾串，取该行原文剥离 `_n`/`_r`/ruby 注音（`<漢字,かな>` 取
  前半段）后的**最后 %d 个字符**。
- 不改的行：`zh` 逐字等于给你的 opus 现行译文；`score`/`note` 仍要给。
"""


def render_calib(label, repo=None) -> str:
    """渲染**校准批**（准入小考）的 prompt——与生产 prompt 同构（最终评审 I9）。

    此前 handoff/runbook 只说"把 `calib/<label>.batch.jsonl` 分别喂给两条通道
    （同一套派发方式）"，但生产的派发方式是"读 `work/ctx/p4s1-sN.md` 这份渲染
    好的 prompt 文件"——校准批既没有对应的 prompt 文件，也没有任何工具能生成。
    操作者只能自己拼一份；**拼得跟生产 prompt 不等价，这场小考就测不到生产
    行为**，而它的产物（`channel_state.json`）直接决定该通道有没有自动清关的
    免检权。

    与 `render()` 的差异只有两处，其余（任务说明、术语表、style.md、语感细则、
    口调表、锚点、纪要、裁决）逐字共用 `_frozen_blocks()`：

    1. **正文换成 `calib/<label>.batch.jsonl` 的行**，且**不带任何锁标**——
       `polish_calibrate.make()` 已经把锁定 id 排除在校准批之外，校准批里不
       存在需要标【锁】的行；锁定 id 清单一节仍然保留（任务说明第 1 条要引用
       它），内容明写"本校准批不含锁定 id"。
    2. **输出契约换成单文件**（校准批不分批号，用的是合成批号 `calib-<label>`，
       结构上不可能被 `polish_ingest` 认领）。

    ⚠ **`calib/<label>.truth.json` 绝不进这份 prompt**——它是判卷答案，进了
    prompt 这场考试当场作废。本函数只读 `<label>.batch.jsonl`，`truth` 字样在
    整个渲染路径上不出现；`tests/test_polish_context.py` 有一条专测钉死这件事。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"
    rows = read_jsonl(d / "calib" / f"{label}.batch.jsonl")

    out = [f"# {label} 通道准入小考（校准批，共 {len(rows)} 行）",
           TASK_INSTRUCTIONS]
    out.append("\n## 硬锁 / 软锁 id 清单（仅供上下文参照，禁止在输出的 "
                "raw/*.out 中出现硬锁 id）")
    # 2026-08-07 措辞修正（fable-wf 实测报告指出批内出现的金标 id 与随发的
    # 全局锚点表冲突）：旧文案"本校准批不含锁定 id"过度概括，实际只对
    # **普通陪考句**成立——`polish_calibrate.make()` 的 norm_candidates 确实
    # 排除了本 SEG 冻结面的全部锁定 id（硬锁+软锁）。但**金标句**抽自全车道
    # 人工裁决历史（`patches.jsonl` reason∈review/recall 的现行文本，见
    # `polish_calibrate._gold_pool()`），这是与"本 SEG 锁定面"完全独立的
    # 另一个维度——金标句可能恰好也是某条锚点/锁定行（两个筛选维度巧合
    # 重叠），这不是矛盾，只是两件事不该被混为一谈。锁定语义与生产批一致：
    # 硬锁不得出稿，软锁可以出稿但改动须 adjudicate=true。
    out.append("（本校准批的**普通陪考句**取样时已排除本 SEG 冻结面里的全部"
                "锁定 id（硬锁+软锁）；但**金标句**抽自全车道人工裁决历史，"
                "与「本 SEG 锁定面」是两个独立维度，金标句可能恰好也是某条"
                "锚点/锁定行——这不算矛盾，只是巧合重叠。）")
    out.extend(_frozen_blocks(fz))

    out.append("\n## 正文（ZH(opus) 为现行译文，即润色起点）")
    for r in rows:
        out.append(f"[{r['batch']}] {r['id']}: JP: {r['jp']} / ZH(opus): {r['opus_zh']}")

    out.append("\n## 输出契约")
    out.append(CALIB_OUTPUT_CONTRACT % (CFG["jp_tail_n"], CFG["jp_tail_n"]))
    return "\n".join(out)


def render(label, session_no, repo=None) -> str:
    """渲染一个会话组的完整 prompt。只读 `frozen/`——不接触活仓库的
    `glossary/`、`skeleton/anchors.yaml`：一个 SEG 一旦冻结，其润色 prompt
    不应随活仓库后续演进而漂移。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"

    sessions = plan(label, repo=repo)
    sess = next((s for s in sessions if s["session"] == session_no), None)
    if sess is None:
        raise KeyError(f"{label} 没有会话 {session_no}（共 {len(sessions)} 组）")
    batches = sess["batches"]

    source_rows = read_jsonl(fz / "source.jsonl")
    id2jp = {r["id"]: r["jp"] for r in source_rows}
    ids_by_batch = {}
    for r in source_rows:
        if r["batch"] in batches:
            ids_by_batch.setdefault(r["batch"], []).append(r["id"])

    opus = {r["id"]: r["zh"] for r in read_jsonl(fz / "opus.jsonl")}
    locked = json.loads((fz / "locked.json").read_text(encoding="utf-8"))
    why = locked["why"]
    # 旧格式兼容：没有 hard_ids/soft_ids 键的冻结面（改版之前落盘的产物）
    # 整体当硬锁——同 `polish_ingest`/`polish_triage` 的兼容口径。
    if "hard_ids" in locked or "soft_ids" in locked:
        hard_ids = set(locked.get("hard_ids", []))
        soft_ids = set(locked.get("soft_ids", []))
    else:
        hard_ids = set(locked.get("ids", []))
        soft_ids = set()

    out = [f"# {label} 会话 {session_no}/{len(sessions)}"
           f"（批次 {batches[0]}–{batches[-1]}，共 {sess['lines']} 行）",
           TASK_INSTRUCTIONS]

    # 章节标题不带序号（Task 4/Task 11 挂起的 minor 的最终修法）：本节列表里
    # 「章节纪要」「裁决与前序纪要」两节视 notes/rulings 是否为空条件性出现，
    # 而「术语/风格/口调/锚点」一节又整段复用 `build_context._render_anchors`
    # ——那段代码在 build_context.py 自己的编号体系里正确地自称"## 三、锚点行"
    # （它在那边确实是第三节），但直接照搬进本工具会撞上本工具自己的"三"。
    # 两条路都试过：①把本工具的标题也重新编号——治不好条件性小节导致的跳号，
    # 且这个模块每渲染一次都要按 notes_text/rulings_text 是否为空重算序号，
    # 边界一多就脆；②去改 `_render_anchors` 里那行硬编码文案——它是
    # build_context.py 生产链路在用的共享函数，为了这里的装订问题去动它，
    # 等于让一个跟 P4 无关的改动去牵动 P3 的按批四件套（那边改动需要
    # canary 回验）。故选：**本工具自己的顶层标题一律不编号**，只用描述性
    # 标题——条件小节出现与否不再需要维护任何序号；`_render_anchors` 返回的
    # "## 三、锚点行"文本原样保留，但在拼进本工具输出前经
    # `polishlib.demote_anchors_heading()` 降一级注为 "### 锚点行"（共享
    # helper，不改 `_render_anchors` 本身——`tools/polish_amplify.py::
    # scan_prompt()` 复用同一个函数同一份处理，两处不再各自维护一份
    # `.replace(...)`，见评审 Finding C），使其读起来是"术语/风格/口调/
    # 锚点"节下的一个子块，而不是一段孤零零带着"三"字的顶层标题。
    session_hard = [i for b in batches for i in ids_by_batch.get(b, []) if i in hard_ids]
    session_soft = [i for b in batches for i in ids_by_batch.get(b, []) if i in soft_ids]

    out.append("\n## 硬锁 id 清单（【硬锁】标记；仅供上下文参照，"
                "禁止在输出的 raw/*.out 中出现这些 id）")
    if session_hard:
        for i in session_hard:
            out.append(f"- 【硬锁】{i}（{why.get(str(i), '?')}）："
                        f"JP: {id2jp.get(i, '')} / ZH(opus): {opus.get(i, '')}")
    else:
        out.append("（本会话无硬锁 id）")

    out.append("\n## 软锁 id 清单（【软锁】标记；锚点行，可以斟酌——"
                "不改就照抄 opus，改了必须 adjudicate=true 并在 note 里写清楚理由）")
    if session_soft:
        for i in session_soft:
            out.append(f"- 【软锁】{i}：JP: {id2jp.get(i, '')} / ZH(opus): {opus.get(i, '')}")
    else:
        out.append("（本会话无软锁 id）")

    out.extend(_frozen_blocks(fz))

    out.append("\n## 逐批正文（仅排除硬锁 id；软锁 id 像普通行一样列出，前面带"
                "【软锁】标记；ZH(opus) 为现行 opus 译文，即润色起点）")
    for b in batches:
        ids = ids_by_batch.get(b, [])
        body_ids = [i for i in ids if i not in hard_ids]
        out.append(f"\n### 批次 b{b}")
        if not body_ids:
            out.append("（本批全部为硬锁 id，无需产出正文——对应 raw/*.out 应为空文件）")
            continue
        for i in body_ids:
            prefix = f"[b{b}] {i} 【软锁】" if i in soft_ids else f"[b{b}] {i}"
            out.append(f"{prefix}: JP: {id2jp.get(i, '')} / ZH(opus): {opus.get(i, '')}")

    out.append("\n## 输出契约")
    out.append(OUTPUT_CONTRACT_HEADER)
    for b in batches:
        out.append(f"- `raw/<channel>/b{b}.out`")

    return "\n".join(out)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="P4 润色会话分组 + prompt 拼接")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--plan", action="store_true", help="打印会话表（JSON Lines）")
    ap.add_argument("--session", type=int, help="渲染指定会话号的 prompt")
    ap.add_argument("--calib", action="store_true",
                     help="渲染校准批（准入小考）prompt——与生产 prompt 同构，"
                          "正文换成 calib/<label>.batch.jsonl 的行，不带锁标")
    ap.add_argument("--out", help="配合 --session/--calib：写出 prompt 文件路径")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    if args.plan:
        for s in plan(args.seg, repo=args.repo):
            print(dumps(s))
        return 0

    if args.calib:
        p = render_calib(args.seg, repo=args.repo)
        digest = hashlib.sha256(p.encode("utf-8")).hexdigest()
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(p, encoding="utf-8")
        # 刻意**不**写 plan.json：那份记录是给 polish_ingest 反查生产批
        # prompt_hash 用的（`_find_prompt_hash` 按 session/batch 索引），
        # 而校准批的输出绝不入仓（见 polish_calibrate 模块 docstring
        # "校准批与生产批分离"）。哈希打到 stdout 供人工留痕即可。
        print(digest)
        return 0

    if args.session is not None:
        p = render(args.seg, args.session, repo=args.repo)
        digest = hashlib.sha256(p.encode("utf-8")).hexdigest()
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(p, encoding="utf-8")

            sess = next(s for s in plan(args.seg, repo=args.repo) if s["session"] == args.session)
            plan_path = _dir_for(args.seg, args.repo) / "plan.json"
            records = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else []
            records = [r for r in records if r.get("session") != args.session]
            records.append({"session": args.session, "batches": sess["batches"], "prompt_hash": digest})
            records.sort(key=lambda r: r["session"])
            plan_path.write_text(dumps(records), encoding="utf-8")
        print(digest)
        return 0

    ap.error("需要 --plan 或 --session 之一")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
