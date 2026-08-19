"""P4 润色 pass：保税仓机械闸——候选级复用 `check_batch.check()`。

薄封装：把已经成熟的批校验（R2a/R2b/R2c 硬规则、W1/W2/W3 软规则，见
`tools/check_batch.py`）套用到某个 SEG 某个通道当前保税仓（`candidates.<channel>
.jsonl`，`tools/polish_ingest.py` 的唯一入仓口）里的候选上，产出
`gates.<channel>.json`。

**hard 非空的候选后续一切分流不得自动清关**（Task 7 消费本模块产出时的硬
约束，brief 原文）。

## 落盘结构：`checked_ids` + `findings`（最终评审 C1 修复，破坏性改版）

```json
{"checked_ids": [10, 11, 12], "findings": {"12": {"hard": [...], "warn": [...]}}}
```

初版只落 `{id: {"hard":…, "warn":…}}` 一层，**只收有问题的 id**。这在
`polish_triage` 那一侧造成了一个**恒绿闸**：`gates.get(cid) is None` 同时表示
"查过、干净"和"从来没查过这个 id"，二者不可区分。最终评审实测复现——b1 入仓
后跑 gate，再入仓 b2（说话人被换名的真 hard 违规），**不重跑 gate** 就跑
triage：新候选的 id 在旧 `gates.json` 里查无此人 → 被当成"干净" → `autoclear
=True`，`polish_commit` dry-run 已将其列入写入计划；事后补跑 gate 才报出
R2b hard。`load_gates()` 在**文件**层已经做到了"没有证据就不放行"（文件不存在
→ 该通道一律不 eligible），**id 层却没有同等待遇**。

修法就是把"这次检查覆盖了哪些 id"如实落盘：`checked_ids` 是本次 `gate()` 真正
送进 `check_batch.check()` 的 id 全集（含全绿的），`findings` 只收有问题的 id
（沿用初版语义，避免为几千个全绿 id 各写一个空壳对象）。`polish_triage` 改判
**"id 不在 checked_ids 里 → 不 eligible"**——陈旧 gates 文件从此只会让新候选
排队进人裁，不会让它直通免检。

⚠ 旧格式（无 `checked_ids` 键的裸字典）被 `polish_triage.load_gates()` 读到时，
`checked_ids` 视为**空集**（不是"全部"）——同一条"没有证据就不放行"的哲学，
并且会 stderr 播报要求重跑 gate。

## P4-CTL：`_n`/`_r`/ruby 计数必须与 **opus 现行译文**一致（最终评审 C2 修复）

`check_batch.check()` 的全部规则都是"jp vs zh"，且控制码保全只覆盖到
【】(R2b)、`○■≪≫≦≧`(R2c)、ruby 良构(R2a)。**`_n`/`_r` 只有 W1 一条软规则、
阈值还是「差 ≥2」**——润色把一行里唯一的 `_n` 删掉，连一条 warn 都不响。最终
评审实测：opus `是啊_n不过，等一下_n再说一遍`，候选把 `_n` 删光 →
`polish_triage._content_edit()` 先 `strip_ctl` 得 **edit=0**（比任何真实润色都
更像"安全小改"）→ gate 只有 W1/W3 warn、hard 为空 → `autoclear=True` 直通入库。
`_n` 决定消息窗断行，丢了就是游戏内文本溢出。ruby 同理：R2a 只管"写出来的
ruby 良构不良构"，**整个 ruby 被删掉**它一声不吭。

故本模块（**不动 `tools/check_batch.py`——那是 P3 生产在用的钉死面**）另加一
条 P4 专属**硬**规则 `P4-CTL`：候选 `zh` 与 `frozen/opus.jsonl` 里该 id 的现行
译文相比，`_n` 条数、`_r` 条数、ruby 组数**三者各自必须相等**。

判据宽窄的两处刻意选择（"判据过宽会用伪报淹没真信号"）：

- **只卡计数，不卡位置。** 润色改了中文字数之后把断行点前后挪一两个字是完全
  正当的排版动作（甚至是必要的），卡位置会让几乎每一条真实润色都变红，一周
  之内这条闸就会被当噪音无视——那是"恒绿闸的镜像形态"。位置挪动带来的真实
  风险是"某一行变得过长"，那正是 W3 行宽 warn 的管辖面，而 W3 现在已被列入
  autoclear 的前置条件（见下），不存在无人看管的缺口。
- **`_n` 与 `_r` 分开数，不合并成总数。** 两者是引擎里不同的断行语义（见
  CLAUDE.md「`_n` 换行、`_r` 另一种断行……勿删」），`_n`→`_r` 的对换会让总数
  不变而行为改变，且它明确违反 prompt 任务说明第 4 条"控制码不得增删或挪位"。
  分开数不引入任何伪报（正当润色本来就不该换断行码种类），却堵住一整类静默
  篡改。

`P4-CTL` 落在 `hard` 里（不是 warn）：warn 在整条 P4 流水线上此前**零消费者**，
把这条判据放进 warn 等于没写。

## W3 行宽 warn 现在参与 autoclear 前置（最终评审 C2 第二半）

`gates.<channel>.json` 的 `warn` 谁也没读。W1/W2/W4 保持"不阻断"是合理的
（W1 是 jp↔zh 断行数差的粗略提示、W2 是术语提示、W4 属清关后全段复检），但
**W3 行宽是真实的游戏内故障**（中文比日文占宽，溢出就是玩家看得见的破图），
不该享受免检。判定写在 `polish_triage._row_eligible` 一侧（本模块只负责如实
产出 warn），见那边的 docstring。

## W4 全段复检模式（最终评审 C3 修复）——`w4_full()`

见本文件下方 `w4_full()` 的 docstring。原 runbook §十一 第 1 步给的
`check_batch.py --batch N --lane-dir …` **在 P4 语境下根本跑不起来**（它读
`work/ctx/batch_N/source.jsonl` 这套 P3 按批四件套，`work/` 是 gitignore 的
临时目录，P3 跑完早已不存在；即便重建，它读的草稿是 P3 **首译稿**而不是清关
后的现行译文）——spec §8 点名的"润色只改同 jp 兄弟句之一"全程无闸。

### D4 修复：每条 finding 报出全族成员，不只报一个（SEG-0 实测缺陷）

**实测缺陷**（`pilot/polish/seg0-s0-s1/channel_feedback.md` D4 节）：SEG-0
清关后 W4 复检，7894 的复现句族其实有**三个**成员（7894/9186/11407），但
finding 只点名了 9186；同步完 9186 重跑才暴露 11407——"同步→重跑"循环了
两轮才收敛。

**根因不在"漏扫"，在消息汇总的截断/去重**：`others`（该 jp 句族里、与本
行现行译文不同的其它成员）这一步本身已经是**全量**的（`w4_full()` 逐 id
遍历时对 `siblings.get(jp, [])` 不做任何截断）；问题出在旧代码复用
`check_batch._w4_msg()` 生成人读 `msg`——那个函数**按 `zh` 文本去重**
（`seen.add(szh)`）、只挑前 3 种文本变体各展示一个代表 id，这在 P3"批内
交互复核"的语境下是合理的克制（避免消息过长），但在 P4"全段收敛检查"的
语境下是缺陷：**当两个不同 id 恰好带着完全相同的（错的）译法时，去重会
把其中一个 id 的存在感抹掉**——裁决者只看见"id=9186 作「…」"，据此同步了
9186，完全不知道 11407 也带着同一段文字、同样需要单独同步（`patches.jsonl`
是按 id 落 patch 的，两个 id 各自需要一条）。7894/9186/11407 正是这个模式：
9186 与 11407 的旧译文字面相同，`_w4_msg` 的按文本去重只留下了先出现的
9186。

**不能改 `check_batch._w4_msg`/`check_batch.check()` 本身**——那是 P3 生产
在用的钉死面（CLAUDE.md「三类操作强制开分支」之外的另一条硬约束：这两个
文件本轮任务明确不让碰），且它在"按批交互复核"场景下截断/去重本身没有错，
问题只出在 P4 的"全段收敛"场景对它的复用不合适。修法：`w4_full()` 改用
本文件自己的 `_w4_full_msg()`——**不按文本去重、不截断**，逐个成员列出
`id`/`zh`/`所属段`（后者按该 id 首译时的 `batch` 号落进
`config/segments.yaml` 的 `batches` 区间解出，查不到时标"未知段"，不阻断
——这是顾问级标注，缺了不影响告警本身是否触发）。finding 结构同时新增
`siblings` 字段（`[{"id","zh","seg"}, ...]`，全族成员的结构化列表），`msg`
字段保留（人读摘要，格式改为逐个列出，不再是"...共 N 种异译"的截断句）。

**下游消费者检查**（"想清楚会不会破坏 `w4_full.json` 的既有读者"，全仓
grep 过）：`w4_full.json` 除本模块自身与 `tests/test_polish_check.py` 外
**无任何其它消费者**（`polish_commit.py`/`polish_audit.py`/`polish_triage.py`
都不读这个文件），`msg` 字段格式改变、新增 `siblings` 字段对现有生产流程
零风险。

**"循环直到收敛"这条纪律还需不需要**——仍需要，但循环次数会显著下降：
报全一族之后，单轮同步就能看全 7894/9186/11407 三者，不用等第二轮才暴露
11407；但"同步伙伴行"这个动作本身会改写文本、可能触发新的族内不一致
（比如把 A 改成跟 B 一致后，族里第三个从未被提及的 C 现在又与新文本不一致
了——这与"报全一族"是否落地无关，是"编辑行为本身产生新差异"这一层因果，
报全一族解决不了它），故 runbook §十一 仍保留"循环重跑直到本轮引入项归零"
这条纪律，只是更新说明"现在一遍能看全一个族，循环次数应显著下降"。

## 与 check_batch.check() 的接口对齐——id 集裁剪（本模块最关键的一步）

`check_batch.check(source_rows, draft_rows, ...)` 开头就断言两者 id 集合
完全一致，不一致立刻返回一条 R1 硬伤并**放弃后续全部检查**（见其源码开头
`if set(src) != set(drf) or len(draft_rows) != len(drf): ...; return`）。
`frozen/source.jsonl` 含该 SEG 全部 id（含锁定 id），而候选 `candidates.
<channel>.jsonl` 天生只含**非锁定** id（`polish_ingest.ingest()` 判死锁定
id 出稿，锁定 id 从不出现在候选里）——两个集合按定义就不相等。如果不按
候选实际覆盖的 id 集裁剪 `source_rows`，`gate()` 每次都只会得到孤零零一条
`R1`，R2a/R2b/R2c/W1/W2/W3 一条都跑不出来——闸看起来跑了（有输出、有
`gates.<channel>.json` 文件），实际什么也没查，是本项目反复吃过亏的"恒绿闸"
的又一种形态（参见 `check_batch.py`/`polish_ingest.py` 里同类告诫）。本模块
的自检变异②专门验证"不裁剪会导致这种恒绿闸重新出现"（见测试文件）。

## speakers 的取法——frozen-only，无回落（评审修复轮定案）

初版实现在 `frozen/glossary/speakers.json` 缺失时退化读 `<repo>/glossary/
speakers.json`（活仓库）。**评审判定这条退化本身就是缺陷（Important）**：
它复现了 `polish_context.render()` 专门用变异测试钉死过的同一类问题（"润色
输入只认冻结面，不读活仓库"，见 spec §3/`docs/superpowers/specs/
2026-08-07-p4-polish-pass-design.md`）——R2b 的说话人映射是**影响判定
结果**的输入，一旦某 SEG 冻结之后活仓库的 `glossary/speakers.json` 被
修订，该 SEG 的机械闸结论会**静默漂移**，而 `polish_setup.verify()` 对此
完全失明（它只哈希 frozen 里已登记的文件，不知道"活仓库又变了"这件事）。
初版能跑对纯粹是因为仓库根恰好有这份文件，不是设计上的保证。

**根因不在本模块，在 `tools/polish_setup.py` 的冻结清单本身漏了
`speakers.json`**（spec §3 的 frozen glossary 清单与 §8 机械闸依赖 R2b
两处对不上）——已回填：`_copy_glossary()` 现在会把 `glossary/speakers.json`
一并拷进 `frozen/glossary/`（连带更新了 spec §3 清单、计划文本 Task 3
描述、`tests/test_polish_setup.py` 的 mini 夹具与新增回归测试）。

本模块现在**只读 `frozen/glossary/speakers.json`，不做任何回落**：文件
不存在时 `_load_speakers()` 返回 `None`（`check()` 内部对应分支会跳过
名字映射校验，但 R2b 的**结构对齐**检查恒查、不受影响，见 `check_batch.py`
的 P1c 硬化）。这与 `polish_context.render()` 已确立的"frozen-only，无
回落"约定一致，也用变异④验证了"回落"这条老代码路径一旦被误改回来，测试
必须真正抓到（见测试文件 `test_polish_check.py`）。

## W4 不在此跑——分工说明

`check_batch.check()` 的 `siblings` 参数（W4：复现句族逐字一致）需要
`check_batch.load_siblings(root)` 建立的**全库**兄弟索引（依赖车道
`data/ledger.jsonl` + `forward.jsonl`/`patches.jsonl`），这是"清关后全段
复检"的范畴（Task 11 runbook），不是候选级机械闸的职责——保税仓阶段还没
有清关，谈不上"全段"。本模块调用 `check()` 时恒传 `siblings=None`，W4 在
这一层**完全不跑**（不是"跑了但没查出问题"）。**别把这一点和"W4 已被
Task 6 覆盖"搞混**——Task 5 `polish_ingest.py` 的模块 docstring 在"错位
侦测"一节点名引用了本模块的 R2b 作为下游兜底之一，两边的分工描述要对得
上：本模块负责 R2a/R2b/R2c/W1/W2/W3，W4 由 Task 11 负责。

## W4 的记号盲区与 `bare_full()`——SEG-7 冻结时发现

W4 的族键是 **jp 整行字面**，含说话人前缀与外层括号。本作有一整类结构会
因此从它眼皮底下溜过去：**同一句台词在不同章里换了记号壳**。

`e2f`（雪乃弥留之际"编纂"的 if 幸福线）与 `e2s` 是重灾区——它把 `s5s`
（サクラ日记）与 `s8f`（五年后尾声）大段重演，同时把人物匿名化：

```
16599 【千秋】「……。ひとつ、先生に聞いて欲しい事があるんです」      ← s8f，已定稿
 5500 【≦女子生徒≧】「……。ひとつ、先生に聞いて欲しい事があるんです」 ← e2f
15010 【ユウイチ】「夕方になると人も多くなるし、…気になってくるから」  ← s5s
 4843 【≦ユウイチ≧】≪夕方になると人も多くなるし、…気になってくるから≫ ← e2f
```

**引号里的字一个不差，W4 却一声不吭**，因为整行不等。实测代价已经发生：
SEG-4（`seg4-s3tail-s5`，通道 fable-wf）的润色 patch 改了 `15007`/`15010`，
对侧 `4840`/`4843` 原封不动——**这是 P4 自己制造的单向劈叉，而且此后永远
不会有闸报它**（seg7 跑 `--w4-full` 同样看不见）。第三族 `5500/16599`
两侧都无 patch，是 P3 首译就带下来的存量。

`bare_full()` 把族键放宽成"**剥掉说话人前缀 `【…】` 与最外层
`「」`/`≪≫` 之后的正文**"，只报 W4 报不到的那一部分（原始 jp 已全同的
族是 W4 的活，这里排除，避免两处重复告警）。

### 长度门槛 `BARE_MIN_LEN = 10`——凭实测，不凭语感

剥壳会把说话人合并掉，短感叹词因此会大量成族而它们的异译**本来就是正当
的**（`大丈夫？` 的语境分治是 SEG-6 §5.2 明文动用过的 W4 例外条款、
`直哉さん` 的「直哉哥/直哉哥哥」是 glossary v6 的具名裁定）。全库实测
（2026-08-16，main 车道 16693 行，剥壳后同句、原始 jp 不全同、现行译文
有分歧的族）：

| 剥壳长度门槛 | 报出族数 |
|---|---:|
| 0 | 51 |
| 6 | 22 |
| 8 | 8 |
| **10** | **3** |
| 15 | 3 |

门槛 10 报出的 3 族（`5500/16599`、`4843/15010`、`4840/15007`）**逐条
人工核对，全部是真的**；被门槛挡掉的全部是 `はい`/`ふむ……`/`ごめんね`
这类短应答，其异译要么已有裁定、要么本就属语境分治。10→15 之间报出条数
不变，说明这不是一条"调到刚好没告警"的曲线，10 落在实测的平台上。

**这是顾问级扫描，不阻断**——与 W4 同级同待遇：它报的是"两边该不该一起
动"，而"该动哪一边"只有人能判。
## R2b 与 Task 5 错位侦测的关系

`polish_ingest.ingest()` 的错位侦测只抓一种确切指纹——"`zh` 逐字等于本批
另一 id 的 opus"；模型如果把错挂的 `zh` 又顺手润色改写过（不再与任何 opus
逐字相同），那道闸抓不住，会放行入仓。**本模块的 R2b（【】说话人结构对齐
+ 名字映射）是这一残留面的主要兜底**：错位挂过来的文本大概率带着错误场景
的说话人前缀（原文说话人对不上），R2b 会把它报成 hard，挡在自动清关之外。

## 同 id 多条候选——取最后一条（gate）

理论上同一 (label, channel) 下同一 id 不应有多条候选（`ingest()` 对同批
重跑是幂等的），但 amplify 等场景会以不同 batch/轮次向同一个
`candidates.<channel>.jsonl` 继续 append。若真出现同 id 多条，取**最后一
条**——append-only 文件里"后来者为现行"是通篇一致的语义（同一约定见
`check_batch.py` 对 forward/patches 的处理方式）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.check_batch import check, load_siblings
from tools.pipelib import REPO, dumps, read_jsonl
from tools.resolve import resolve_map


def _dir_for(label, repo) -> Path:
    """同 `polish_setup._dir_for` / `polish_ingest._dir_for` 的理由：
    `polishlib.seg_dir()` 硬编码用仓库根，不接受覆盖；这里另起一份，只在
    `repo` 落空时才退化到默认路径，使 `gate()`/CLI 都能被 tmp_path 造的替身
    仓库完全接管（测试要求：不得写进真实仓库的 `pilot/polish/`）。"""
    repo = Path(repo) if repo is not None else REPO
    return repo / "pilot" / "polish" / label


def _load_speakers(fz: Path) -> dict | None:
    """见模块 docstring"speakers 的取法"一节：frozen-only，无回落——不存在
    就是 None，绝不去读活仓库（`polish_context.render()` 已确立的同一约定；
    评审判定"回落读活仓库"本身是缺陷，见 docstring）。"""
    frozen_p = fz / "glossary" / "speakers.json"
    if frozen_p.exists():
        return json.loads(frozen_p.read_text(encoding="utf-8"))
    return None


N_RE = re.compile(r"_n")
R_RE = re.compile(r"_r")
RUBY_RE = re.compile(r"<([^<>,]+),([^<>,]+)>")

# `P4-CTL` 逐项判据：(人读名, 计数函数)。三项各自独立报一条，报文里直接给出
# "opus N 个 / 候选 M 个"，让人一眼看出是删了还是加了。
_CTL_COUNTERS = (
    ("_n", lambda s: len(N_RE.findall(s))),
    ("_r", lambda s: len(R_RE.findall(s))),
    ("ruby 注音", lambda s: len(RUBY_RE.findall(s))),
)


def ctl_violations(cid, zh, opus_zh) -> list:
    """P4-CTL：候选 `zh` 与 opus 现行译文的 `_n`/`_r`/ruby **计数**比对，返回
    hard 违规列表（见模块 docstring "P4-CTL" 一节的判据宽窄理由）。

    `zh` 非字符串（`polish_ingest` 已在入仓时判死这类行，这里是兜底）视为空
    串参与比较——opus 里但凡有一个控制码就会被报出来，不会静默放过。
    """
    z = zh if isinstance(zh, str) else ""
    o = opus_zh if isinstance(opus_zh, str) else ""
    out = []
    for name, count in _CTL_COUNTERS:
        cz, co = count(z), count(o)
        if cz != co:
            out.append({"id": cid, "rule": "P4-CTL",
                        "msg": f"{name} 计数与 opus 现行译文不一致"
                               f"（opus {co} 个，候选 {cz} 个）——控制码保全是"
                               "硬约束，位置可调、总数不可改"})
    return out


def quote_drift(cid, jp, zh, opus_zh) -> list:
    """W5：候选的 `『』` 计数须等于 **opus**（这一轮没动它）或 **jp**（对齐原文），
    落在两者之外即告警。

    为什么不是硬闸、也不是「jp vs zh 逐字相等」：`『』` 在本作里两种来源混杂——
    原文自带（`それは『落書き』なのだ`）与译者为标记名目而补（原文无引号）。
    删掉译者补的是**正当修正**（p5seg0 `6268`：jp 0 对 opus 1，候选删回 0）；
    删掉原文自带的是**保真事故**（同段 `6542`：jp 1 对 opus 1，候选删成 0，
    批注还称「此处不是引用」——事实错误）。两者的差别只有把 jp 一起看才判得出。

    冻结面本身就有 21 行 jp/zh 不等（历史既有，不在本轮职权内），所以判据锚在
    「相对 opus 的**变化**」上，不追究存量。顾问级：确有正当删除的情形。
    """
    j = jp if isinstance(jp, str) else ""
    z = zh if isinstance(zh, str) else ""
    o = opus_zh if isinstance(opus_zh, str) else ""
    cz, co, cj = z.count("『"), o.count("『"), j.count("『")
    if cz == co or cz == cj:
        return []
    return [{"id": cid, "rule": "W5",
             "msg": f"『』计数既不等于 opus（{co}）也不等于原文（{cj}），候选为 {cz}"
                    "——原文自带的引号不得删除，译者补的引号可删但须删到与原文一致"}]


def gate(label, channel, repo=None) -> dict:
    """对该 SEG/通道当前保税仓里的全部候选跑 `check_batch.check()` + P4-CTL，
    返回 `{"checked_ids": [...], "findings": {id: {"hard": [...], "warn": [...]}}}`
    并原样落盘成 `gates.<channel>.json`（`findings` 落盘时 key 转 str）。

    `checked_ids` 是本次真正被检查过的 id 全集（**含全绿的**），`findings`
    只收有问题的 id——两者的分工与"陈旧 gates ＝ 恒绿闸"这条修复的理由见模块
    docstring。

    `candidates.<channel>.jsonl` 不存在（该通道还没入仓过任何东西）时，
    等同于"零候选"：`checked_ids` 为空、`findings` 为空，照常落盘（不
    报错——尚未入仓是正常的中间状态，不是异常）。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen"
    source_rows = read_jsonl(fz / "source.jsonl")
    src_jp = {r["id"]: r["jp"] for r in source_rows}
    opus_zh = {r["id"]: r["zh"] for r in read_jsonl(fz / "opus.jsonl")}

    cand_path = d / f"candidates.{channel}.jsonl"
    candidates = read_jsonl(cand_path) if cand_path.exists() else []

    # 同一 id 多条 → 取最后一条（见模块 docstring）。
    last_by_id = {}
    for row in candidates:
        last_by_id[row["id"]] = row
    ids = list(last_by_id.keys())

    stray = [i for i in ids if i not in src_jp]
    if stray:
        print(f"!! polish_check.gate: {label}/{channel} 的候选里有 "
              f"{len(stray)} 个 id 不在 frozen/source.jsonl 里（{sorted(stray)}），"
              "已跳过——正常的 polish_ingest 入仓流程不会产生这种候选，出现"
              "说明 candidates 文件与这份 frozen 快照不属于同一个 SEG",
              file=sys.stderr)
        ids = [i for i in ids if i in src_jp]

    # 关键一步：source_rows 按候选实际覆盖的 id 集裁剪，理由见模块 docstring
    # 顶部专节——不裁剪会让 check() 每次都只吐一条 R1 就放弃，是恒绿闸的一种
    # 形态。
    cropped_source = [{"id": i, "jp": src_jp[i]} for i in ids]
    draft_rows = [{"id": i, "zh": last_by_id[i]["zh"]} for i in ids]

    speakers = _load_speakers(fz)
    glossary_path = fz / "glossary" / "active.json"
    glossary = (json.loads(glossary_path.read_text(encoding="utf-8"))
                if glossary_path.exists() else None)

    # W4 本任务不跑，siblings 恒 None——见模块 docstring"W4 不在此跑"一节。
    result = check(cropped_source, draft_rows, speakers=speakers, glossary=glossary,
                    siblings=None)

    findings = {}
    for v in result["hard"]:
        findings.setdefault(v["id"], {"hard": [], "warn": []})["hard"].append(v)
    for v in result["warn"]:
        findings.setdefault(v["id"], {"hard": [], "warn": []})["warn"].append(v)

    # P4 专属硬规则：控制码计数保全（vs opus 现行译文，不是 vs jp）。
    for i in ids:
        for v in ctl_violations(i, last_by_id[i]["zh"], opus_zh.get(i, "")):
            findings.setdefault(i, {"hard": [], "warn": []})["hard"].append(v)
    # W5（P5 追加）：『』既不随 opus 也不随原文——见 quote_drift 的判据说明。
    for i in ids:
        for v in quote_drift(i, src_jp.get(i, ""), last_by_id[i]["zh"], opus_zh.get(i, "")):
            findings.setdefault(i, {"hard": [], "warn": []})["warn"].append(v)

    d.mkdir(parents=True, exist_ok=True)
    # JSON 对象键只能是字符串，id 在这里是 int——落盘前显式转 str（与
    # tools/check_charlevel.py 的 per_id 输出同一约定），排序保证输出确定性；
    # gate() 的返回值里 findings 仍是 int 键的字典，与仓库里其它按 id 建索引
    # 的字典（如 check_batch.check() 内部的 src/drf）保持同一类型习惯。
    gates = {"checked_ids": sorted(ids),
             "findings": {k: v for k, v in sorted(findings.items())}}
    (d / f"gates.{channel}.json").write_text(
        dumps({"checked_ids": gates["checked_ids"],
               "findings": {str(k): v for k, v in gates["findings"].items()}}),
        encoding="utf-8")
    return gates


class W4NotAvailable(RuntimeError):
    """兄弟索引建不起来（车道 data 缺 ledger 或全无译文）——**必须与"查过、
    没问题"可区分**，绝不返回空清单冒充绿。见 `check_batch.main()` 里同一条
    告诫（"闸没跑"必须与"闸跑了没报"在输出上可区分）。"""


def _load_segment_ranges(repo) -> list:
    """`config/segments.yaml` → `[(label, batch_lo, batch_hi), ...]`，供
    `_id_to_label_map()` 把 id 解到"所属段"用。文件缺失或解析失败时返回空
    列表——W4 的"所属段"标注因此退化为「未知段」，这是顾问级信息，缺了不
    影响 W4 告警本身是否触发（见模块 docstring D4 修复专节）。"""
    import yaml
    p = Path(repo) / "config" / "segments.yaml"
    if not p.exists():
        return []
    try:
        rows = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    out = []
    for r in rows:
        b = r.get("batches")
        if r.get("label") and isinstance(b, list) and len(b) == 2:
            out.append((r["label"], b[0], b[1]))
    return out


def _id_to_label_map(repo, lane_dir) -> dict:
    """`{id: label}`——经 `<lane_dir>/data/forward.jsonl` 的 `batch` 字段
    （首译批号；润色 patch 不带 `batch` 字段、也不改这个历史事实）落进
    `config/segments.yaml` 的 `batches` 区间解出该 id 原本属于哪个 SEG。

    任何一步数据缺失（`forward.jsonl` 不存在、`segments.yaml` 解不出区间）
    都返回空字典——调用方按"查不到"统一处理（呈现为"未知段"），不需要
    再区分"到底是哪一步查不到"，那不影响 W4 告警本身。
    """
    fwd_p = Path(lane_dir) / "data" / "forward.jsonl"
    if not fwd_p.exists():
        return {}
    ranges = _load_segment_ranges(repo)
    if not ranges:
        return {}
    id2batch = {}
    for r in read_jsonl(fwd_p):
        # 同 id 理论上不会在 forward.jsonl 里重复（那是 P3 首译落盘、不是
        # 润色 patch），这里用 setdefault 兜底取最先出现的一条，不需要
        # "后写者胜"那套语义（那是给 zh 内容用的，这里只要批号）。
        id2batch.setdefault(r["id"], r.get("batch"))
    out = {}
    for cid, batch in id2batch.items():
        if batch is None:
            continue
        for label, lo, hi in ranges:
            if lo <= batch <= hi:
                out[cid] = label
                break
    return out


def _w4_full_msg(others, id2label=None) -> str:
    """全段 W4 复检专用的人读消息——**报出全部成员，不按 zh 文本去重、不
    截断**（D4 修复，见模块 docstring 专节）。与 P3 钉死面
    `check_batch._w4_msg()` 刻意不同：那个函数为"批内交互复核"场景按文本
    去重、只挑 3 个代表——在这里复用会把"两个不同 id 恰好带着同一段错译"
    压成一条，隐藏其中一个 id 的存在（seg0-s0-s1 的 7894/9186/11407 实测
    正是如此：9186、11407 文本相同，旧代码去重后只报了 9186）。
    """
    id2label = id2label or {}
    parts = [f"id={sid}@{id2label.get(sid) or '未知段'} 作「{szh}」"
             for sid, szh in others]
    return (f"复现句族内不一致（同一 jp 另有译法，共 {len(others)} 个其他"
            f"成员）：" + "；".join(parts))


def w4_full(label, lane_dir, repo=None) -> list:
    """**清关后全段 W4 复检**：对该 SEG 的全部 id，用车道**现行**译文
    （`resolve.resolve_map(forward, patches)`，即已经叠加过本轮 polish patch
    的那一版）在**全库**复现句族索引里查"同一 jp 另有别的译法"。

    为什么必须另起一个模式，而不是照 runbook 原样跑 `check_batch.py --batch N`
    （最终评审 C3）：
    - `check_batch.main()` 读 `work/ctx/batch_<N>/source.jsonl` +
      `work/out/batch_<N>.draft.jsonl`——P3 的按批四件套。`work/` 是 gitignore
      的临时目录，P3 生产跑完早已不存在，实跑直接 `FileNotFoundError`；
    - 即便有人重建那套四件套，`draft.jsonl` 是 P3 的**首译稿**，不是清关后的
      现行译文——查的是错的文本，"绿"毫无意义。

    本函数的判定面因此是：**id 集 = frozen/source.jsonl（整段，不只本轮清关的
    id）**——spec §8 明写风险是"润色只改同 jp 兄弟句之一"，被改的那条和没被改
    的兄弟条都要能被报出来；**文本 = 车道现行译文**；**索引 = 全库兄弟索引**
    （`check_batch.load_siblings`，跨 SEG，因为复现句族本来就散布全书）。

    返回 `[{"id":…, "rule": "W4", "msg":…, "siblings": […]}, …]`（按 id 升序）。
    `siblings` 是该 jp 句族**全部**其他成员的结构化列表
    （`[{"id","zh","seg"}, ...]`，D4 修复——见模块 docstring 专节，此前
    `msg` 借用 `check_batch._w4_msg()` 按文本去重、只挑 3 个代表，会漏报
    "两个不同 id 恰好带着同一段错译"里的其中一个）。索引建不起来时抛
    `W4NotAvailable`——不返回空列表。
    """
    d = _dir_for(label, repo)
    lane_dir = Path(lane_dir)
    siblings = load_siblings(lane_dir)
    if siblings is None:
        raise W4NotAvailable(
            f"{lane_dir}/data 下无 ledger.jsonl 或无任何译文，复现句族索引建不"
            "起来——W4 **未被检查**，这与「查过、没问题」是两回事，不予冒充绿")

    seg_ids = [r["id"] for r in read_jsonl(d / "frozen" / "source.jsonl")]
    ledger = {r["id"]: r for r in read_jsonl(lane_dir / "data" / "ledger.jsonl")}
    fwd_p, pat_p = lane_dir / "data" / "forward.jsonl", lane_dir / "data" / "patches.jsonl"
    cur = resolve_map(read_jsonl(fwd_p) if fwd_p.exists() else [],
                      read_jsonl(pat_p) if pat_p.exists() else [])
    id2label = _id_to_label_map(repo if repo is not None else REPO, lane_dir)

    out = []
    for i in seg_ids:
        if i not in ledger or i not in cur:
            continue
        jp, zh = ledger[i]["jp"], cur[i]
        others = [(sid, szh) for sid, szh in siblings.get(jp, [])
                  if sid != i and szh != zh]
        if others:
            out.append({
                "id": i, "rule": "W4",
                "msg": _w4_full_msg(others, id2label),
                "siblings": [{"id": sid, "zh": szh, "seg": id2label.get(sid)}
                             for sid, szh in others],
            })
    (d / "w4_full.json").write_text(dumps({"lane": str(lane_dir), "findings": out}),
                                     encoding="utf-8")
    return out


#: `bare_full()` 的剥壳正文最短长度。低于此的族不报——剥壳把说话人合并掉之后，
#: 短应答会大量成族而其异译本来就正当。取值依据是全库实测，见模块 docstring
#: "W4 的记号盲区与 bare_full()" 一节的分布表：0→51 族、6→22、8→8、**10→3**、
#: 15→3。门槛 10 报出的 3 族逐条核对全部为真，且 10→15 平台不变。
BARE_MIN_LEN = 10

_SPEAKER_RE = re.compile(r"^【[^】]*】")
_OPEN_RE = re.compile(r"^[「≪]")
_CLOSE_RE = re.compile(r"[」≫]$")


def bare_text(s: str) -> str:
    """剥掉说话人前缀 `【…】` 与最外层 `「」`/`≪≫`，返回台词正文。

    只剥**最外**一层：内层的 `『…』`（本作用来标记「物語」「ドーナツの人」
    这类被引用的名目）是正文的一部分，剥了就会把两个真正不同的句子并成一族。
    """
    s = _SPEAKER_RE.sub("", s or "").strip()
    s = _OPEN_RE.sub("", s)
    return _CLOSE_RE.sub("", s)


def bare_full(label, lane_dir, repo=None, min_len: int = BARE_MIN_LEN) -> list:
    """**W4 的记号盲区补扫**：剥壳后同句、原始 jp 却不全同的族里，现行译文
    有分歧的报出来。设计与取舍见模块 docstring 专节。

    与 `w4_full()` 的分工是**互斥**的：本函数只看"原始 jp 不全同"的族
    （`len(raw_forms) >= 2`），原始 jp 已全同的那部分是 W4 的管辖面，在这里
    显式排除，两道扫描不会对同一族各报一次。

    判定面与 `w4_full()` 同规格：id 集 = `frozen/source.jsonl` 整段；
    文本 = 车道**现行**译文（forward+patches 叠加）；索引 = **全库** main 车道。
    索引建不起来时抛 `W4NotAvailable`——不返回空列表冒充绿。
    """
    d = _dir_for(label, repo)
    lane_dir = Path(lane_dir)
    led_p = lane_dir / "data" / "ledger.jsonl"
    fwd_p, pat_p = (lane_dir / "data" / "forward.jsonl",
                    lane_dir / "data" / "patches.jsonl")
    if not led_p.exists():
        raise W4NotAvailable(
            f"{lane_dir}/data 下无 ledger.jsonl，剥壳族索引建不起来——本扫描"
            "**未被执行**，这与「查过、没问题」是两回事，不予冒充绿")
    ledger = {r["id"]: r for r in read_jsonl(led_p)}
    cur = resolve_map(read_jsonl(fwd_p) if fwd_p.exists() else [],
                      read_jsonl(pat_p) if pat_p.exists() else [])
    if not cur:
        raise W4NotAvailable(
            f"{lane_dir}/data 下无任何译文，剥壳族索引建不起来——本扫描"
            "**未被执行**，不予冒充绿")
    id2label = _id_to_label_map(repo if repo is not None else REPO, lane_dir)

    fam = {}
    for i, r in ledger.items():
        if i not in cur:
            continue
        fam.setdefault(bare_text(r["jp"]), []).append(i)

    seg_ids = [r["id"] for r in read_jsonl(d / "frozen" / "source.jsonl")]
    out = []
    for i in seg_ids:
        if i not in ledger or i not in cur:
            continue
        key = bare_text(ledger[i]["jp"])
        if len(key) < min_len:
            continue
        members = fam.get(key, [])
        if len({ledger[m]["jp"] for m in members}) < 2:
            continue          # 原始 jp 全同——W4 的管辖面，这里不重复告警
        mine = bare_text(cur[i])
        others = [m for m in members if m != i and bare_text(cur[m]) != mine]
        if not others:
            continue
        out.append({
            "id": i, "rule": "BARE",
            "msg": (f"剥壳同句族内不一致（记号壳不同、正文相同，W4 看不见；"
                    f"共 {len(others)} 个其他成员）："
                    + "；".join(f"id={m}@{id2label.get(m) or '未知段'} "
                                f"作「{bare_text(cur[m])}」" for m in others)),
            "bare_jp": key,
            "siblings": [{"id": m, "jp": ledger[m]["jp"], "zh": cur[m],
                          "seg": id2label.get(m)} for m in others],
        })
    (d / "bare_full.json").write_text(
        dumps({"lane": str(lane_dir), "min_len": min_len, "findings": out}),
        encoding="utf-8")
    return out


def lane_drift(label, lane_dir, repo=None) -> list:
    """**冻结面漂移体检**：冻结之后车道现行文本又变过的行。

    背景：SEG 冻结后车道并不冻——phase 内的 glossary 迭代（recall 召回、
    孪生修复、术语回改）会继续改现行文本。此时该 SEG 的候选是**对着旧基线**
    产出的，若裁决直接采纳，就会把冻结后的新修正**静默回退**掉，而既有闸
    一个都不会响（jp_tail 只核原文、gates 只看候选自身、triage 拿冻结面当
    唯一基准）。

    2026-08-19 首次实证：p5seg0 冻结后 `6118` 由孪生修复改过（v19 劈叉的
    修正），而四条通道都对这一行提了改动提案——采纳任一条都会退回旧形。

    返回 `[{id, frozen_zh, current_zh, proposals: [{channel, zh}...]}, ...]`，
    并落盘 `lane_drift.json`。**顾问级**：漂移本身不是错，它只要求裁决者
    按**现行文本**重判这些行，而不是按冻结面。
    """
    d = _dir_for(label, repo)
    fz = d / "frozen" / "opus.jsonl"
    if not fz.exists():
        raise W4NotAvailable(f"{fz} 不存在——该 SEG 尚未冻结")
    frozen = {r["id"]: r["zh"] for r in read_jsonl(fz)}
    lane_dir = Path(lane_dir)
    fwd_p, pat_p = (lane_dir / "data" / "forward.jsonl",
                    lane_dir / "data" / "patches.jsonl")
    if not fwd_p.exists():
        raise W4NotAvailable(f"{fwd_p} 不存在，读不到车道现行文本")
    cur = resolve_map(read_jsonl(fwd_p),
                      read_jsonl(pat_p) if pat_p.exists() else [])
    # 候选面：该 id 上各通道提了什么（有提案的漂移行才是真风险）
    props = {}
    for cp in sorted(d.glob("candidates.*.jsonl")):
        ch = cp.name[len("candidates."):-len(".jsonl")]
        last = {}
        for r in read_jsonl(cp):
            last[r["id"]] = r
        for i, r in last.items():
            if r.get("zh") is not None:
                props.setdefault(i, []).append({"channel": ch, "zh": r["zh"]})

    out = []
    for i, fz_zh in sorted(frozen.items()):
        if i in cur and cur[i] != fz_zh:
            out.append({"id": i, "frozen_zh": fz_zh, "current_zh": cur[i],
                        "proposals": props.get(i, [])})
    (d / "lane_drift.json").write_text(
        dumps({"lane": str(lane_dir), "drifted": len(out), "findings": out}),
        encoding="utf-8")
    return out


def human_twin_scan(label, lane_dir, repo=None) -> list:
    """**人改孪生传播扫描**：本段人工亲手动过的行（verdict=edit、edited_zh
    非空、或同 id 复核轮二次裁决），其改动是否传播到了全库孪生。

    背景（P4 实证漏洞，docs/ops/p5-polish-pattern-report.md §六工装缺口 1）：
    人工复核的改动不会自动出现在不在裁决队列里的孪生行上——`15758`（人裁
    「鸣蝉…闹起了脾气」）与近孪生 `15832` 曾就此分叉，直到修订窗口才补上。
    W4/bare 的全段复检按「族内是否一致」报警，但**不知道哪一侧是对的**；
    本扫描以人工改动行为基准侧，报出「孪生还停在旧形」的方向性结论。

    孪生两个面：jp 全等（W4 面）与剥壳全等（bare 面，len≥BARE_MIN_LEN 且
    排除 jp 已全等者——两面不重复报）。数据不可用时 raise `W4NotAvailable`。
    顾问级：报出的行仍须人判（同 jp 不同语境的正当分治按台账豁免）。
    """
    d = _dir_for(label, repo)
    dec_p = d / "decisions.jsonl"
    if not dec_p.exists():
        raise W4NotAvailable(
            f"{dec_p} 不存在——本段尚无任何裁决，谈不上「人工改动的传播」")
    decs = read_jsonl(dec_p)
    id_counts = {}
    for r in decs:
        id_counts[r["id"]] = id_counts.get(r["id"], 0) + 1
    human_ids = ({r["id"] for r in decs
                  if r.get("verdict") == "edit" or r.get("edited_zh")}
                 | {i for i, c in id_counts.items() if c >= 2})
    lane_dir = Path(lane_dir)
    led_p = lane_dir / "data" / "ledger.jsonl"
    if not led_p.exists():
        raise W4NotAvailable(f"{led_p} 不存在，孪生索引建不出来")
    ledger = {r["id"]: r for r in read_jsonl(led_p)}
    fwd_p, pat_p = (lane_dir / "data" / "forward.jsonl",
                    lane_dir / "data" / "patches.jsonl")
    cur = resolve_map(read_jsonl(fwd_p) if fwd_p.exists() else [],
                      read_jsonl(pat_p) if pat_p.exists() else [])
    if not cur:
        raise W4NotAvailable(f"{lane_dir}/data 下无任何译文，无从核对现行文本")
    id2label = _id_to_label_map(repo if repo is not None else REPO, lane_dir)

    by_jp, by_bare = {}, {}
    for i in ledger:
        if i not in cur:
            continue
        by_jp.setdefault(ledger[i]["jp"], []).append(i)
        by_bare.setdefault(bare_text(ledger[i]["jp"]), []).append(i)

    out = []
    for i in sorted(human_ids):
        if i not in ledger or i not in cur:
            continue
        jp, zh = ledger[i]["jp"], cur[i]
        twins = []
        for m in by_jp.get(jp, []):
            if m != i and cur.get(m) != zh:
                twins.append({"id": m, "face": "jp", "jp": ledger[m]["jp"],
                              "zh": cur.get(m), "seg": id2label.get(m)})
        bkey = bare_text(jp)
        if len(bkey) >= BARE_MIN_LEN:
            mine_bare = bare_text(zh)
            for m in by_bare.get(bkey, []):
                if m == i or ledger[m]["jp"] == jp:
                    continue          # jp 全等面已报过，不重复
                if bare_text(cur.get(m, "")) != mine_bare:
                    twins.append({"id": m, "face": "bare", "jp": ledger[m]["jp"],
                                  "zh": cur.get(m), "seg": id2label.get(m)})
        if twins:
            out.append({
                "id": i, "rule": "HT", "zh": zh,
                "msg": (f"人工改动行的孪生未同步（{len(twins)} 处）："
                        + "；".join(f"id={t['id']}[{t['face']}]@{t['seg'] or '未知段'}"
                                    f" 作「{t['zh']}」" for t in twins)),
                "twins": twins,
            })
    (d / "human_twins.json").write_text(
        dumps({"lane": str(lane_dir), "human_ids": sorted(human_ids),
               "findings": out}), encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="P4 保税仓机械闸：候选级复用 check_batch.check()")
    ap.add_argument("--seg", required=True, help="段表 label（如 seg1-s2）")
    ap.add_argument("--channel", help="执行通道（如 fable-wf/ds-flash）；候选级机械闸必需")
    ap.add_argument("--w4-full", action="store_true",
                     help="清关后全段 W4 复检模式（与 --channel 互斥，需要 --lane-dir）")
    ap.add_argument("--bare-full", action="store_true",
                     help="清关后全段**剥壳同句**复检（W4 的记号盲区补扫，"
                          "与 --channel 互斥，需要 --lane-dir）")
    ap.add_argument("--lane-drift", action="store_true",
                     help="冻结面漂移体检（冻结后车道又变过的行；与 --channel 互斥，需要 --lane-dir）")
    ap.add_argument("--human-twins", action="store_true",
                     help="人改孪生传播扫描（人工改动行的孪生是否同步，"
                          "与 --channel 互斥，需要 --lane-dir）")
    ap.add_argument("--bare-min-len", type=int, default=BARE_MIN_LEN,
                     help=f"配合 --bare-full：剥壳正文最短长度（默认 {BARE_MIN_LEN}）")
    ap.add_argument("--lane-dir", default=None,
                     help="配合 --w4-full：生产车道**根**目录（如 pilot/lanes/opus，"
                          "不是它下面的 data/）")
    ap.add_argument("--repo", default=None,
                     help="车道根目录（省略时用仓库根；测试用 tmp_path 传替身仓库）")
    args = ap.parse_args(argv)

    if args.lane_drift:
        if not args.lane_dir:
            ap.error("--lane-drift 需要 --lane-dir（生产车道根，如 pilot/lanes/opus）")
        try:
            findings = lane_drift(args.seg, args.lane_dir, repo=args.repo)
        except W4NotAvailable as e:
            print(f"⚠ 冻结面漂移体检**未能执行**：{e}", file=sys.stderr)
            return 2
        risky = [v for v in findings if v["proposals"]]
        for v in findings:
            tag = f"，且有 {len(v['proposals'])} 条候选提案——裁决须按现行文本重判" if v["proposals"] else ""
            print(f"  - id {v['id']}：冻结后车道已更新{tag}\n"
                  f"      冻结|{v['frozen_zh'][:48]}\n      现行|{v['current_zh'][:48]}",
                  file=sys.stderr)
        print(f"lane-drift: {args.seg} 冻结后车道已变 {len(findings)} 行"
              f"（其中 {len(risky)} 行有候选提案；顾问级，明细见 "
              f"pilot/polish/{args.seg}/lane_drift.json）")
        return 0

    if args.human_twins:
        if not args.lane_dir:
            ap.error("--human-twins 需要 --lane-dir（生产车道根，如 pilot/lanes/opus）")
        try:
            findings = human_twin_scan(args.seg, args.lane_dir, repo=args.repo)
        except W4NotAvailable as e:
            print(f"⚠ 人改孪生扫描**未能执行**：{e}", file=sys.stderr)
            return 2
        for v in findings:
            print(f"  - id {v['id']}：{v['msg']}", file=sys.stderr)
        print(f"human-twins: {args.seg} 人工改动行孪生未同步 {len(findings)} 处"
              f"（顾问级；明细见 pilot/polish/{args.seg}/human_twins.json）")
        return 0

    if args.bare_full:
        if not args.lane_dir:
            ap.error("--bare-full 需要 --lane-dir（生产车道根，如 pilot/lanes/opus）")
        try:
            findings = bare_full(args.seg, args.lane_dir, repo=args.repo,
                                 min_len=args.bare_min_len)
        except W4NotAvailable as e:
            print(f"⚠ 剥壳同句复检**未能执行**：{e}", file=sys.stderr)
            return 2
        for v in findings:
            print(f"  - id {v['id']}：{v['msg']}", file=sys.stderr)
        print(f"bare-full: {args.seg} 剥壳同句族不一致 {len(findings)} 处"
              f"（顾问级；明细见 pilot/polish/{args.seg}/bare_full.json）")
        return 0

    if args.w4_full:
        if not args.lane_dir:
            ap.error("--w4-full 需要 --lane-dir（生产车道根，如 pilot/lanes/opus）")
        try:
            findings = w4_full(args.seg, args.lane_dir, repo=args.repo)
        except W4NotAvailable as e:
            print(f"⚠ W4 全段复检**未能执行**：{e}", file=sys.stderr)
            return 2
        if findings:
            print(f"!! W4 全段复检：{args.seg} 有 {len(findings)} 处复现句族不一致"
                  "（顾问级，不自动阻断——逐条人工核对该改哪一边）", file=sys.stderr)
            for v in findings:
                print(f"  - id {v['id']}：{v['msg']}", file=sys.stderr)
        print(f"w4-full: {args.seg} 复现句族不一致 {len(findings)} 处"
              f"（明细见 pilot/polish/{args.seg}/w4_full.json）")
        return 0

    if not args.channel:
        ap.error("需要 --channel（候选级机械闸），或 --w4-full（清关后全段复检）")
    gates = gate(args.seg, args.channel, repo=args.repo)
    findings = gates["findings"]
    n_hard = sum(1 for v in findings.values() if v["hard"])
    n_warn = sum(1 for v in findings.values() if v["warn"] and not v["hard"])
    print(f"gate: {args.seg}/{args.channel} 检查 {len(gates['checked_ids'])} 个 id，"
          f"有问题 {len(findings)} 个（hard {n_hard}，仅 warn {n_warn}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
